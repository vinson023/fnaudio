import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_queue_policy import MAX_QUEUE_COUNTER, project_queue_state, saturating_counter


class MetadataQueuePolicyTests(unittest.TestCase):
    def test_projects_valid_state_and_clamps_pending(self):
        self.assertEqual(project_queue_state({"limit": 200, "pending": 250}), (200, 200))

    def test_invalid_state_values_fall_back_without_object_coercion(self):
        self.assertEqual(project_queue_state({"limit": object(), "pending": object()}, 300), (300, 0))
        self.assertEqual(project_queue_state(None, 300), (300, 0))

    def test_boolean_and_extreme_limits_are_safe(self):
        self.assertEqual(project_queue_state({"limit": True, "pending": True}, 300), (300, 0))
        self.assertEqual(project_queue_state({"limit": 999999999, "pending": 1}), (200000, 1))

    def test_counter_saturates_and_recovers_invalid_values(self):
        self.assertEqual(saturating_counter(MAX_QUEUE_COUNTER), MAX_QUEUE_COUNTER)
        self.assertEqual(saturating_counter(object()), 1)
        self.assertEqual(saturating_counter(4, True), 4)


if __name__ == "__main__":
    unittest.main()
