import sys
import threading
import time
import unittest

sys.path.insert(0, "app/server")

from dlna.renderer import DlnaRenderer
from dlna.service import AVTRANSPORT, CONNECTION_MANAGER, CONTENT_DIRECTORY, DlnaProtocolService, UpnpActionError
from dlna.control_point import device_protocol_info
from unittest import mock


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

    def test_mute_and_unmute_are_applied_to_the_backend_volume(self):
        self.renderer.set_volume(63)
        self.controls.clear()

        self.assertTrue(self.renderer.set_mute(True)["ok"])
        self.assertTrue(self.renderer.snapshot()["muted"])
        self.assertEqual(self.controls, [("volume", 0.0)])

        self.controls.clear()
        self.renderer.set_volume(41)
        self.assertEqual(self.controls, [])
        self.assertEqual(self.renderer.snapshot()["volume"], 41)

        self.assertTrue(self.renderer.set_mute(False)["ok"])
        self.assertEqual(self.controls, [("volume", 41.0)])
        self.assertFalse(self.renderer.snapshot()["muted"])

    def test_avtransport_set_uri_returns_standard_soap_response(self):
        body = (
            '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Body><u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID><CurrentURI>http://198.51.100.20/test.mp3</CurrentURI>'
            '<CurrentURIMetaData></CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>'
        ).encode("utf-8")
        status, response = self.service.control("renderer", "avtransport", body, '"%s#SetAVTransportURI"' % AVTRANSPORT)
        self.assertEqual(status, 200)
        self.assertIn(b"SetAVTransportURIResponse", response)
        self.assertEqual(self.renderer.snapshot()["uri"], "http://198.51.100.20/test.mp3")

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

    @mock.patch("dlna.control_point.soap_request")
    def test_renderer_protocol_info_is_parsed_into_mime_capabilities(self, request):
        request.return_value = (
            b'<Envelope><Source></Source><Sink>'
            b'http-get:*:audio/flac:*,http-get:*:audio/x-dsf:*'
            b'</Sink></Envelope>'
        )

        result = device_protocol_info("http://renderer.test/connection")

        self.assertTrue(result["supports_dsd"])
        self.assertIn("audio/flac", result["mime_types"])
        self.assertIn("audio/x-dsf", result["mime_types"])

    def test_event_subscriptions_are_bounded(self):
        events = self.service.events
        events._callback_url = lambda value: value
        for index in range(64):
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/%s" % index, "", "Second-60")
        with self.assertRaisesRegex(ValueError, "too many"):
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/overflow", "", "Second-60")

    def test_content_directory_honors_metadata_filter_sort_and_update_id(self):
        calls = []
        item = {"id": "track-1", "title": "Example", "artist": "Artist", "album": "Album", "format": "FLAC", "mime": "audio/flac", "duration": 12}

        def page(params):
            calls.append(dict(params))
            return {"items": [item], "count": 1}

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            page,
            lambda view: [],
            lambda value: value.get("mime", "audio/mpeg"),
            library_item=lambda item_id: item if item_id == "track-1" else None,
            system_update_id=lambda: 42,
        )
        children = service._browse({
            "ObjectID": "music",
            "BrowseFlag": "BrowseDirectChildren",
            "Filter": "dc:title,upnp:artist",
            "StartingIndex": "0",
            "RequestedCount": "0",
            "SortCriteria": "-upnp:artist",
        })
        self.assertEqual(children["UpdateID"], "42")
        self.assertEqual(children["NumberReturned"], "1")
        self.assertEqual(calls[0]["sort"], "artist")
        self.assertEqual(calls[0]["dir"], "desc")
        self.assertIn("<upnp:artist>Artist</upnp:artist>", children["Result"])
        self.assertNotIn("<upnp:album>", children["Result"])
        self.assertNotIn("<res ", children["Result"])

        metadata = service._browse({"ObjectID": "track-1", "BrowseFlag": "BrowseMetadata", "Filter": "*"})
        self.assertEqual(metadata["NumberReturned"], "1")
        self.assertIn("audio/flac", metadata["Result"])
        self.assertEqual(service._dispatch("server", CONTENT_DIRECTORY, "GetSystemUpdateID", {}), {"Id": "42"})

    def test_content_directory_rejects_unknown_objects_and_sort_criteria(self):
        with self.assertRaises(UpnpActionError) as unknown:
            self.service._browse({"ObjectID": "missing", "BrowseFlag": "BrowseDirectChildren"})
        self.assertEqual(unknown.exception.code, 701)
        with self.assertRaises(UpnpActionError) as invalid_sort:
            self.service._browse({"ObjectID": "music", "BrowseFlag": "BrowseDirectChildren", "SortCriteria": "+dc:date"})
        self.assertEqual(invalid_sort.exception.code, 709)

    def test_content_directory_browse_metadata_returns_one_root_object(self):
        result = self.service._browse({"ObjectID": "0", "BrowseFlag": "BrowseMetadata", "Filter": "dc:title"})
        self.assertEqual(result["NumberReturned"], "1")
        self.assertEqual(result["TotalMatches"], "1")
        self.assertIn('parentID="-1"', result["Result"])

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
