import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, "app/server")

from server import DLNA_MONITOR_GUARD, _dlna_stop_is_suppressed, _upnp_track_id_from_uri, dlna_output_open


class RemoteOutputMonitorTests(unittest.TestCase):
    def test_extracts_queue_track_id_from_renderer_uri(self):
        uri = "http://198.51.100.2:5666/upnp/media/abc%201/song.flac"
        self.assertEqual(_upnp_track_id_from_uri(uri), "abc 1")

    def test_ignores_unrelated_renderer_uri(self):
        self.assertEqual(_upnp_track_id_from_uri("http://example.test/music.flac"), "")

    def test_manual_stop_suppresses_renderer_auto_advance_race(self):
        original = dict(DLNA_MONITOR_GUARD)
        try:
            DLNA_MONITOR_GUARD.update({"target_id": "renderer-1", "suppress_stop_until": 50.0})
            self.assertTrue(_dlna_stop_is_suppressed("renderer-1", "STOPPED", now=49.0))
            self.assertFalse(_dlna_stop_is_suppressed("renderer-2", "STOPPED", now=49.0))
            self.assertFalse(_dlna_stop_is_suppressed("renderer-1", "STOPPED", now=51.0))
        finally:
            DLNA_MONITOR_GUARD.clear()
            DLNA_MONITOR_GUARD.update(original)

    def test_dlna_open_does_not_preload_next_uri(self):
        track = SimpleNamespace(track_id="track-1", item={"id": "track-1"})
        state = SimpleNamespace(target_id="renderer-1")
        pushed = []

        def capture_push(device, item, handler, next_item=None):
            pushed.append(next_item)
            return True, "started"

        with patch("server.find_upnp_device", return_value={"id": "renderer-1"}), patch(
            "server.soap_push", side_effect=capture_push
        ):
            result = dlna_output_open(track, state, {"handler": object()})

        self.assertTrue(result["ok"])
        self.assertEqual(pushed, [None])


if __name__ == "__main__":
    unittest.main()
