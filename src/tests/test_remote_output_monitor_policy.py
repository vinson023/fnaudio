import sys
import unittest

sys.path.insert(0, "app/server")

from remote_output_monitor_policy import (
    stalled_track_expired,
    stop_is_suppressed,
    track_id_from_renderer_uri,
)


class RemoteOutputMonitorPolicyTests(unittest.TestCase):
    def test_uri_extracts_only_text_upnp_media_track_ids(self):
        self.assertEqual(track_id_from_renderer_uri("http://example.test/upnp/media/a%20b/song.flac"), "a b")
        self.assertEqual(track_id_from_renderer_uri("http://example.test/song.flac"), "")
        self.assertEqual(track_id_from_renderer_uri(object()), "")

    def test_uri_rejects_oversized_input_or_decoded_track_identity(self):
        self.assertEqual(track_id_from_renderer_uri("http://example.test/upnp/media/" + ("x" * 9000)), "")
        self.assertEqual(
            track_id_from_renderer_uri("http://example.test/upnp/media/" + ("x" * 257) + "/song.flac"),
            "",
        )

    def test_stop_guard_refuses_non_text_and_non_finite_inputs(self):
        guard = {"target_id": "renderer-1", "suppress_stop_until": 50.0}
        self.assertTrue(stop_is_suppressed(guard, "renderer-1", "STOPPED", 49.0))
        self.assertFalse(stop_is_suppressed(guard, "renderer-1", "STOPPED", float("nan")))
        self.assertFalse(stop_is_suppressed(guard, object(), "STOPPED", 49.0))

    def test_stalled_guard_is_bounded_to_the_matching_playing_track(self):
        self.assertTrue(stalled_track_expired("one", "one", "PLAYING", 0, 0, 100, 12, 114))
        self.assertFalse(stalled_track_expired("one", "two", "PLAYING", 0, 0, 100, 12, 114))
        self.assertFalse(stalled_track_expired("one", "one", "PLAYING", 0, 0, 100, float("inf"), 114))


if __name__ == "__main__":
    unittest.main()
