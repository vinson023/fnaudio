import sys
import unittest

sys.path.insert(0, "app/server")

from dlna.backend_schedule import BackendOperation, MAX_BACKEND_COALESCED, schedule_latest, take_latest


class DlnaBackendScheduleTests(unittest.TestCase):
    def test_first_operation_starts_worker_and_later_operation_coalesces(self):
        first = BackendOperation("control", 1, action="pause")
        active, pending, coalesced, start = schedule_latest(False, None, 0, first)
        self.assertEqual((active, pending, coalesced, start), (True, first, 0, True))
        latest = BackendOperation("control", 2, action="stop")
        active, pending, coalesced, start = schedule_latest(active, pending, coalesced, latest)
        self.assertEqual((active, pending, coalesced, start), (True, latest, 1, False))
        self.assertEqual(take_latest(pending), latest)

    def test_invalid_state_and_counter_are_safe(self):
        active, pending, coalesced, start = schedule_latest(False, "bad", "bad", BackendOperation("load", 1))
        self.assertTrue(active)
        self.assertIsInstance(pending, BackendOperation)
        self.assertEqual(coalesced, 0)
        self.assertTrue(start)
        self.assertIsNone(take_latest("bad"))
        active, pending, coalesced, start = schedule_latest(True, BackendOperation("load", 1), MAX_BACKEND_COALESCED, BackendOperation("load", 2))
        self.assertEqual(coalesced, MAX_BACKEND_COALESCED)
        self.assertFalse(start)
