import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import server
from state_store import load_user_state


class PlaybackQueueTests(unittest.TestCase):
    def test_compact_track_ids_are_accepted_and_persisted(self):
        with tempfile.TemporaryDirectory() as root:
            response, status = server.playback_queue(
                {"cache_dir": root},
                {
                    "queue": ["track-1", "", "track-2"],
                    "current_id": "track-2",
                    "repeat": "all",
                    "shuffle": True,
                },
            )

            self.assertEqual(status, 200)
            self.assertTrue(response["ok"])
            self.assertEqual(response["core"]["queue"], ["track-1", "track-2"])
            self.assertEqual(response["core"]["current"], "track-2")
            playback = load_user_state({"cache_dir": root})["playback"]
            self.assertEqual(playback["queue"], ["track-1", "track-2"])
            self.assertEqual(playback["current_id"], "track-2")

    def test_legacy_track_objects_remain_supported(self):
        with tempfile.TemporaryDirectory() as root:
            response, status = server.playback_queue(
                {"cache_dir": root},
                {"queue": [{"id": "legacy", "title": "Legacy", "duration": 12.5}], "current_id": "legacy"},
            )

            self.assertEqual(status, 200)
            self.assertEqual(response["core"]["queue"], ["legacy"])
            self.assertEqual(response["core"]["duration"], 12.5)

    def test_queue_selection_prioritizes_current_metadata_without_affecting_save(self):
        class Metadata:
            def __init__(self):
                self.track_ids = []

            def prioritize_track(self, track_id):
                self.track_ids.append(track_id)

        with tempfile.TemporaryDirectory() as root:
            metadata = Metadata()
            previous = server.METADATA_SERVICE
            server.METADATA_SERVICE = metadata
            try:
                response, status = server.playback_queue(
                    {"cache_dir": root},
                    {"queue": ["current"], "current_id": "current"},
                )
            finally:
                server.METADATA_SERVICE = previous

            self.assertEqual(status, 200)
            self.assertTrue(response["ok"])
            self.assertEqual(metadata.track_ids, ["current"])


if __name__ == "__main__":
    unittest.main()
