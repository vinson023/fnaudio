import sys
import unittest

sys.path.insert(0, "app/server")

from transcode_snapshot import transcode_summary


class TranscodeSnapshotTests(unittest.TestCase):
    def test_summary_is_bounded_and_ignores_private_or_invalid_values(self):
        snapshot = transcode_summary({
            "queued": "2",
            "tracked": None,
            "queue_limit": "bad",
            "path": "/vol1/private.flac",
            "ffmpeg": {
                "active": "1",
                "limit": 2,
                "waiting": -3,
                "peak": 4,
                "wait_seconds": "0.1239",
                "command": "ffmpeg /vol1/private.flac",
            },
        })
        self.assertEqual(snapshot["queued"], 2)
        self.assertEqual(snapshot["tracked"], 0)
        self.assertEqual(snapshot["queue_limit"], 0)
        self.assertEqual(snapshot["ffmpeg"]["active"], 1)
        self.assertEqual(snapshot["ffmpeg"]["wait_seconds"], 0.124)
        self.assertNotIn("path", str(snapshot))
        self.assertNotIn("command", str(snapshot))

    def test_summary_preserves_waiter_pressure_fields(self):
        snapshot = transcode_summary({"ffmpeg": {"waiter_rejected": 3, "timed_out": 2, "waiter_limit": 32}})
        self.assertEqual(snapshot["ffmpeg"]["waiter_rejected"], 3)
        self.assertEqual(snapshot["ffmpeg"]["timed_out"], 2)
        self.assertEqual(snapshot["ffmpeg"]["waiter_limit"], 32)


if __name__ == "__main__":
    unittest.main()
