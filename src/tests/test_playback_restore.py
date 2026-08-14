import sys
import io
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import server


class FakeMpdService:
    host = "127.0.0.1"
    port = 56660

    def __init__(self):
        self.calls = []

    def sync_playback_queue(self, tracks, current, **kwargs):
        self.calls.append((list(tracks), current, kwargs))
        return {"ok": True, "queue_count": len(tracks)}


class FailingMpdService(FakeMpdService):
    def sync_playback_queue(self, tracks, current, **kwargs):
        self.calls.append((list(tracks), current, kwargs))
        raise RuntimeError("MPD database is not ready")


class StoppedMpdService(FakeMpdService):
    def refresh_status(self):
        return {"status": {"transport": {"state": "STOPPED"}}}


class PlaybackRestoreTests(unittest.TestCase):
    def test_playback_event_endpoint_writes_an_initial_sse_snapshot(self):
        class FakeCore:
            def wait_for_version(self, version, timeout):
                return 7

            def snapshot(self):
                return {
                    "state_version": 7,
                    "target_id": "mpd:test-dac",
                    "target_kind": "mpd",
                    "transport": "PLAYING",
                    "position": 3.5,
                    "duration": 120.0,
                }

        class DisconnectingBuffer(io.BytesIO):
            def flush(self):
                raise BrokenPipeError()

        handler = object.__new__(server.Handler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.wfile = DisconnectingBuffer()
        with mock.patch.object(server, "PLAYBACK_CORE", FakeCore()):
            handler.stream_playback_events({"target_id": ["mpd:test-dac"]})

        frame = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("id: 7", frame)
        self.assertIn("event: playback", frame)
        self.assertIn('"target_id":"mpd:test-dac"', frame)

    def test_playback_event_payload_uses_core_as_the_authoritative_snapshot(self):
        core = {
            "target_id": "mpd:usb-dac",
            "target_kind": "mpd",
            "transport": "PLAYING",
            "position": 12.25,
            "duration": 245.5,
            "state_version": 42,
        }

        payload = server.playback_event_payload(core, "mpd:usb-dac")

        self.assertEqual(payload["state_version"], 42)
        self.assertEqual(payload["target_id"], "mpd:usb-dac")
        self.assertEqual(payload["transport"]["state"], "PLAYING")
        self.assertEqual(payload["position"], {"rel_seconds": 12.25, "duration_seconds": 245.5})
        self.assertIs(payload["core"], core)

    def test_playback_control_command_id_is_idempotent_for_retry_safe_transport(self):
        handler = mock.Mock()
        handler.server.config = {}
        response = {"ok": True, "core": {"state_version": 9, "transport": "PLAYING"}}
        server.PLAYBACK_COMMAND_RESULTS.clear()
        with mock.patch.object(server, "playback_control", return_value=(response, 200)) as control:
            first, first_status = server.playback_control_idempotent(handler, {"command_id": "same-gesture", "action": "next"})
            second, second_status = server.playback_control_idempotent(handler, {"command_id": "same-gesture", "action": "next"})

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first["command_id"], "same-gesture")
        self.assertEqual(second["state_version"], 9)
        control.assert_called_once()

    def test_targets_marks_stale_renderer_as_unavailable_without_losing_local_target(self):
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "stale-renderer"}
        fake_plugin = mock.Mock()
        fake_plugin.capabilities.return_value = {}
        fake_core.registry.get.return_value = fake_plugin
        fake_core.registry.describe.return_value = []
        cache = {"items": [], "stamp": __import__("time").time(), "refreshing": False}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server.MPD_OUTPUT, "status", return_value={"available": False, "output_capabilities": {"devices": []}}
        ), mock.patch.object(server, "UPNP_CACHE", cache), mock.patch.object(
            server, "upmpdcli_probe", return_value={}
        ), mock.patch.object(server, "airplay_probe", return_value={}):
            payload = server.playback_targets_payload()

        self.assertEqual(payload["current_target"], "stale-renderer")
        self.assertFalse(payload["current_target_available"])
        self.assertEqual(payload["targets"][0]["id"], "local")

    def test_forced_target_refresh_rebuilds_mpd_output_capabilities(self):
        class CapabilityService:
            def __init__(self):
                self.calls = []

            def output_capabilities(self, force=False):
                self.calls.append(force)
                return {"devices": []}

        service = CapabilityService()
        output = mock.Mock()
        output.service = service
        output.status.return_value = {"available": False, "output_capabilities": {"devices": []}}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "local"}
        fake_plugin = mock.Mock()
        fake_plugin.capabilities.return_value = {}
        fake_core.registry.get.return_value = fake_plugin
        fake_core.registry.describe.return_value = []
        cache = {"items": [], "stamp": __import__("time").time(), "refreshing": False}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "MPD_OUTPUT", output
        ), mock.patch.object(server, "UPNP_CACHE", cache), mock.patch.object(
            server, "upmpdcli_probe", return_value={}
        ), mock.patch.object(server, "airplay_probe", return_value={}):
            server.playback_targets_payload(force_refresh=True)

        self.assertEqual(service.calls, [True])

    def test_playback_control_persists_stop_state_for_restart(self):
        handler = mock.Mock()
        handler.server.config = {}
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"playing": False, "transport": "STOPPED"}
        fake_core.dispatch.return_value = {"result": {}, "state": {}}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "playback_target_kind", return_value="browser"
        ), mock.patch.object(server, "save_current_playback_session", return_value=27) as save_session:
            response, status = server.playback_control(handler, {"target_id": "local", "action": "stop"})
        self.assertEqual(status, 200)
        self.assertEqual(response["revision"], 27)
        save_session.assert_called_once_with(handler.server.config)

    def test_restore_mirrors_saved_mpd_queue_and_position(self):
        with tempfile.TemporaryDirectory() as root:
            fake = FakeMpdService()
            saved = {
                "playback": {
                    "queue": ["a", "b"],
                    "current_id": "b",
                    "position": 17.5,
                    "playing": True,
                    "repeat": "all",
                    "shuffle": False,
                    "target_id": "mpd:usb:dac",
                }
            }
            items = [
                {"id": "a", "path": "/music/a.flac", "duration": 30},
                {"id": "b", "path": "/music/b.flac", "duration": 40},
            ]
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=items
                ), mock.patch.object(server, "mpd_control") as control:
                    server.restore_playback_session({"cache_dir": root})
                self.assertGreaterEqual(len(fake.calls), 1)
                tracks, current, options = fake.calls[-1]
                self.assertEqual([track.track_id for track in tracks], ["a", "b"])
                self.assertEqual(current, "b")
                self.assertEqual(options["start"], 17.5)
                self.assertEqual(options["repeat"], "all")
                control.assert_called_once_with("stop", host=fake.host, port=fake.port)
                self.assertEqual(server.PLAYBACK_CORE.state.current_track_id, "b")
                self.assertEqual(server.PLAYBACK_CORE.state.position, 17.5)
                self.assertFalse(server.PLAYBACK_CORE.state.playing)
                self.assertFalse(options["play"])
            finally:
                server.MPD_SERVICE = old_service

    def test_restore_mirrors_stopped_session_then_stops_mpd(self):
        with tempfile.TemporaryDirectory() as root:
            fake = FakeMpdService()
            saved = {
                "playback": {
                    "queue": ["a"],
                    "current_id": "a",
                    "position": 3,
                    "playing": False,
                    "target_id": "mpd:usb:dac",
                }
            }
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=[{"id": "a", "path": "/music/a.flac"}]
                ), mock.patch.object(server, "mpd_control") as control:
                    server.restore_playback_session({"cache_dir": root})
                control.assert_called_once_with("stop", host=fake.host, port=fake.port)
                self.assertFalse(server.PLAYBACK_CORE.state.playing)
                self.assertEqual(server.PLAYBACK_CORE.state.transport, "STOPPED")
            finally:
                server.MPD_SERVICE = old_service

    def test_restore_retries_after_transient_mpd_startup_failure(self):
        with tempfile.TemporaryDirectory() as root:
            fake = FailingMpdService()
            saved = {
                "playback": {
                    "queue": ["a"],
                    "current_id": "a",
                    "target_id": "mpd:usb:dac",
                }
            }
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                timer = mock.Mock()
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=[{"id": "a", "path": "/music/a.flac"}]
                ), mock.patch.object(server.threading, "Timer") as timer_factory:
                    timer_factory.return_value = timer
                    server.restore_playback_session({"cache_dir": root})
                timer_factory.assert_called_once_with(2.0, server.restore_playback_session, args=({"cache_dir": root}, 1))
                timer.start.assert_called_once_with()
                self.assertEqual(len(fake.calls), 1)
            finally:
                server.MPD_SERVICE = old_service

    def test_restore_does_not_publish_playing_when_mpd_stops_on_open(self):
        with tempfile.TemporaryDirectory() as root:
            fake = StoppedMpdService()
            saved = {
                "playback": {
                    "queue": ["a"],
                    "current_id": "a",
                    "playing": True,
                    "target_id": "mpd:usb:dac",
                }
            }
            old_service = server.MPD_SERVICE
            try:
                server.MPD_SERVICE = fake
                with mock.patch.object(server, "load_user_state", return_value=saved), mock.patch.object(
                    server, "query_library_items_by_ids", return_value=[{"id": "a", "path": "/music/a.flac"}]
                ), mock.patch.object(server, "mpd_control"), mock.patch.object(server, "save_current_playback_session") as save_session:
                    server.restore_playback_session({"cache_dir": root})
                self.assertFalse(server.PLAYBACK_CORE.state.playing)
                self.assertEqual(server.PLAYBACK_CORE.state.transport, "STOPPED")
                save_session.assert_called_once()
            finally:
                server.MPD_SERVICE = old_service


if __name__ == "__main__":
    unittest.main()
