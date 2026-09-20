import sys
import unittest

sys.path.insert(0, "app/server")

from playback_event_stream_policy import MAX_SSE_FRAME_BYTES, keepalive_frame, snapshot_changed, snapshot_frame


class PlaybackEventStreamPolicyTests(unittest.TestCase):
    def test_snapshot_changed_rejects_bool_and_accepts_new_integer(self):
        self.assertTrue(snapshot_changed(2, 1))
        self.assertFalse(snapshot_changed(2, 2))
        self.assertFalse(snapshot_changed(True, 1))

    def test_snapshot_frame_is_compact_and_safe(self):
        self.assertEqual(snapshot_frame(3, {"transport": "PLAYING"}), b'id: 3\nevent: playback\ndata: {"transport":"PLAYING"}\n\n')
        self.assertEqual(snapshot_frame("bad", ["ignored"]), b'id: 0\nevent: playback\ndata: {}\n\n')

    def test_keepalive_frame_is_stable(self):
        self.assertEqual(keepalive_frame(), b": keepalive\n\n")

    def test_oversized_snapshot_is_replaced_by_a_bounded_marker(self):
        frame = snapshot_frame(9, {"payload": "x" * MAX_SSE_FRAME_BYTES})
        self.assertLessEqual(len(frame), MAX_SSE_FRAME_BYTES)
        self.assertIn(b'"truncated":true', frame)

    def test_unserializable_snapshot_is_replaced_by_a_safe_marker(self):
        class Explosive:
            pass
        frame = snapshot_frame(4, {"bad": Explosive()})
        self.assertEqual(frame, b'id: 4\nevent: playback\ndata: {"type":"playback","state_version":0,"truncated":true}\n\n')

    def test_recursive_snapshot_is_replaced_by_a_safe_marker(self):
        payload = {}
        payload["self"] = payload
        frame = snapshot_frame(5, payload)
        self.assertIn(b'"truncated":true', frame)

if __name__ == "__main__":
    unittest.main()
