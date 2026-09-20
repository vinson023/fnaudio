import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "server"))

from playback_session_projection import MAX_SESSION_QUEUE_ITEMS, project_playback_session


class PlaybackSessionProjectionTests(unittest.TestCase):
    def test_projects_aliases_and_copies_bounded_queue(self):
        queue = [{"id": "1"}, {"id": "2"}]
        result = project_playback_session(
            {"queue": queue, "current": " 1 ", "target_id": "browser", "target_kind": "", "playing": 1},
            safe_float=lambda value: float(value),
        )
        self.assertEqual(result["current_id"], "1")
        self.assertEqual(result["target_id"], "local")
        self.assertEqual(result["target_kind"], "browser")
        self.assertEqual(result["queue"], queue)
        self.assertIsNot(result["queue"], queue)

    def test_rejects_malformed_mapping_and_bounds_sequence(self):
        class Broken:
            def get(self, *_):
                raise RuntimeError("broken")

        result = project_playback_session(Broken(), safe_float=lambda value: 9.0)
        self.assertEqual(result["queue"], [])
        self.assertEqual(result["position"], 9.0)
        self.assertEqual(result["target_id"], "local")

        queue = list(range(MAX_SESSION_QUEUE_ITEMS + 10))
        result = project_playback_session({"queue": queue}, safe_float=lambda value: 0.0)
        self.assertEqual(len(result["queue"]), MAX_SESSION_QUEUE_ITEMS)

    def test_does_not_truthiness_coerce_persisted_boolean_fields(self):
        class Explosive:
            def __bool__(self):
                raise AssertionError("session booleans must not use arbitrary truthiness")

        result = project_playback_session(
            {"playing": "false", "shuffle": "0"},
            safe_float=lambda value: 0.0,
        )
        self.assertFalse(result["playing"])
        self.assertFalse(result["shuffle"])

        result = project_playback_session(
            {"playing": Explosive(), "shuffle": Explosive()},
            safe_float=lambda value: 0.0,
        )
        self.assertFalse(result["playing"])
        self.assertFalse(result["shuffle"])


if __name__ == "__main__":
    unittest.main()
