import sys
import unittest

sys.path.insert(0, "app/server")

from diagnostics_playback import playback_summary


class DiagnosticsPlaybackTests(unittest.TestCase):
    def test_summary_projects_only_safe_playback_fields(self):
        self.assertEqual(
            playback_summary({
                "target_id": "dac:one",
                "transport": "PLAYING",
                "queue_length": 4,
                "current": {"path": "/private/song.flac"},
                "private": "omit",
            }),
            {"target_id": "dac:one", "transport": "PLAYING", "queue_length": 4, "has_current_track": True},
        )

    def test_summary_isolates_broken_mapping_and_current_length(self):
        class BrokenDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken state")

            def __len__(self):
                raise RuntimeError("broken length")

        self.assertEqual(
            playback_summary(BrokenDict()),
            {"target_id": "", "transport": "", "queue_length": 0, "has_current_track": False},
        )
        self.assertFalse(playback_summary({"current": BrokenDict()})["has_current_track"])


if __name__ == "__main__":
    unittest.main()
