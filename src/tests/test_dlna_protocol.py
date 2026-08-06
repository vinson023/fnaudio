import sys
import threading
import time
import unittest

sys.path.insert(0, "app/server")

from dlna.renderer import DlnaRenderer
from dlna.service import AVTRANSPORT, CONNECTION_MANAGER, DlnaProtocolService


class DlnaProtocolTests(unittest.TestCase):
    def setUp(self):
        self.loads = []
        self.controls = []
        self.renderer = DlnaRenderer(self._load, self._control, self._status)
        self.service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view: [],
            lambda item: item.get("mime", "audio/mpeg"),
            output_capabilities=lambda: {
                "pcm_rates": [44100, 96000, 192000],
                "pcm_max_bits": 24,
                "dsd_native": True,
            },
        )

    def _load(self, uri, position):
        self.loads.append((uri, position))
        return {"ok": True}

    def _control(self, action, position):
        self.controls.append((action, position))
        return {"ok": True}

    @staticmethod
    def _status():
        return {"transport": {"state": "STOPPED"}, "position": {"rel_seconds": 0, "duration_seconds": 0}}

    def test_renderer_description_and_profiles(self):
        description = self.service.description("renderer").decode("utf-8")
        self.assertIn("fnAudio Renderer", description)
        self.assertIn("MediaRenderer:1", description)
        profiles = self.service.protocol_info("renderer")
        self.assertIn("http-get:*:audio/L24;rate=192000;channels=2:*", profiles)
        self.assertIn("http-get:*:audio/x-dsf:*", profiles)

    def test_connection_manager_protocol_info(self):
        status, body = self.service.control(
            "renderer",
            "connection",
            b'<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:GetProtocolInfo xmlns:u="urn:schemas-upnp-org:service:ConnectionManager:1"/></s:Body></s:Envelope>',
            '"urn:schemas-upnp-org:service:ConnectionManager:1#GetProtocolInfo"',
        )
        self.assertEqual(status, 200)
        self.assertIn(CONNECTION_MANAGER.encode("utf-8"), body)
        self.assertIn(b"audio/L16;rate=96000", body)

    def test_didl_metadata_is_exposed_to_renderer_state(self):
        metadata = (
            '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
            '<item><dc:title>Example Track</dc:title><upnp:artist>Example Artist</upnp:artist>'
            '<upnp:albumArtURI>http://example.test/cover.jpg</upnp:albumArtURI></item></DIDL-Lite>'
        )
        self.renderer.set_uri("http://example.test/track.flac", metadata)
        state = self.renderer.snapshot()
        self.assertEqual(state["title"], "Example Track")
        self.assertEqual(state["artist"], "Example Artist")
        self.assertEqual(state["art_url"], "http://example.test/cover.jpg")

    def test_avtransport_set_uri_returns_standard_soap_response(self):
        body = (
            '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Body><u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID><CurrentURI>http://example.test/test.mp3</CurrentURI>'
            '<CurrentURIMetaData></CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>'
        ).encode("utf-8")
        status, response = self.service.control("renderer", "avtransport", body, '"%s#SetAVTransportURI"' % AVTRANSPORT)
        self.assertEqual(status, 200)
        self.assertIn(b"SetAVTransportURIResponse", response)
        self.assertEqual(self.renderer.snapshot()["uri"], "http://example.test/test.mp3")

    def test_next_uses_the_next_transport_uri(self):
        self.renderer.set_uri("http://example.test/first.flac")
        self.renderer.set_next_uri("http://example.test/second.flac", "")

        result = self.renderer.command("next")

        self.assertTrue(result["ok"])
        self.assertEqual(self.renderer.snapshot()["uri"], "http://example.test/second.flac")
        self.assertEqual(self.renderer.snapshot()["next_uri"], "")
        self.assertTrue(self._wait_for(lambda: self.loads == [("http://example.test/second.flac", 0.0)]))
        self.assertEqual(self.renderer.snapshot()["transport"], "PLAYING")

    def test_stop_after_play_does_not_allow_an_old_load_to_restart(self):
        started = threading.Event()
        release = threading.Event()
        controls = []

        def slow_load(uri, position):
            started.set()
            release.wait(2)
            return {"ok": True}

        def control(action, position):
            controls.append((action, position))
            return {"ok": True}

        renderer = DlnaRenderer(slow_load, control, self._status)
        renderer.set_uri("http://example.test/slow.flac")
        self.assertTrue(renderer.command("play")["ok"])
        self.assertTrue(started.wait(1))

        self.assertTrue(renderer.command("stop")["ok"])
        release.set()

        self.assertTrue(self._wait_for(lambda: ("stop", None) in controls))
        self.assertEqual(renderer.snapshot()["transport"], "STOPPED")
        self.assertEqual(renderer.snapshot()["position"], 0.0)

    def test_pause_then_play_reloads_the_paused_uri(self):
        renderer = DlnaRenderer(self._load, self._control, self._status)
        renderer.set_uri("http://example.test/resume.flac")

        renderer.command("play")
        self.assertTrue(self._wait_for(lambda: len(self.loads) == 1))
        renderer.command("pause")
        self.assertTrue(self._wait_for(lambda: ("pause", None) in self.controls))
        self.assertEqual(renderer.snapshot()["transport"], "PAUSED_PLAYBACK")

        renderer.command("play")
        self.assertTrue(self._wait_for(lambda: len(self.loads) == 2))
        self.assertEqual(renderer.snapshot()["transport"], "PLAYING")

    def test_backend_output_error_stops_the_renderer_session(self):
        renderer = DlnaRenderer(
            self._load,
            self._control,
            lambda: {
                "transport": {"state": "PAUSED"},
                "position": {"rel_seconds": 0, "duration_seconds": 12},
                "raw": {"error": "Failed to open ALSA device"},
            },
        )
        renderer.set_uri("http://example.test/failure.flac")
        renderer.command("play")
        self.assertTrue(self._wait_for(lambda: len(self.loads) == 1))

        state = renderer.snapshot()

        self.assertEqual(state["transport"], "STOPPED")
        self.assertIn("Failed to open ALSA device", state["last_error"])

    @staticmethod
    def _wait_for(predicate, timeout=1.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return bool(predicate())


if __name__ == "__main__":
    unittest.main()
