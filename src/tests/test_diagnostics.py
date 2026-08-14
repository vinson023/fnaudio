import sys
import unittest

sys.path.insert(0, "app/server")

from diagnostics import support_snapshot


class DiagnosticsTests(unittest.TestCase):
    def test_snapshot_is_bounded_and_redacts_sensitive_values(self):
        snapshot = support_snapshot(
            server_name="fnAudio test",
            mpd={"running": True, "fault": {"state": "PLAYING"}, "playback_errors": {"last_category": ""}},
            scan_state={"running": False, "errors": ["one"]},
            metadata={"running": True, "pending": 2, "dropped": 1},
            transcode={"active": 1, "queued": 3},
            dlna_available=True,
            renderer_count=2,
            metrics={"token": "must-not-leak"},
            playback={"target_id": "dac:one", "transport": "PLAYING", "queue_length": 8, "current": {"path": "/private/song.flac"}},
        )
        self.assertEqual(snapshot["schema"], 1)
        self.assertEqual(snapshot["playback"]["queue_length"], 8)
        self.assertNotIn("path", str(snapshot))
        self.assertEqual(snapshot["metrics"]["token"], "[REDACTED]")

    def test_snapshot_does_not_degrade_health_for_recoverable_playback_warning(self):
        snapshot = support_snapshot(
            server_name="fnAudio test",
            mpd={
                "running": True,
                "fault": {"state": "IDLE"},
                "playback_errors": {
                    "last_category": "queue_stale",
                    "items": [{"category": "queue_stale", "severity": "warning"}],
                },
            },
            scan_state={}, metadata={}, transcode={}, dlna_available=False,
            renderer_count=0, metrics={}, playback={},
        )

        self.assertEqual(snapshot["components"]["mpd"]["error_category"], "")


if __name__ == "__main__":
    unittest.main()
