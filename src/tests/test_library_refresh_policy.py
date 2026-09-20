import unittest

from app.server.library_refresh_policy import cancel_refresh, enqueue_refresh, take_refresh


class LibraryRefreshPolicyTests(unittest.TestCase):
    def test_first_request_starts_worker(self):
        self.assertEqual(enqueue_refresh(False, False, False), (True, True, True, False, True))

    def test_request_while_queued_can_upgrade_to_force(self):
        self.assertEqual(enqueue_refresh(True, False, True, True), (True, False, True, True, True))

    def test_duplicate_request_is_ignored(self):
        self.assertEqual(enqueue_refresh(True, True, True, False), (False, False, True, True, True))

    def test_take_clears_queue_and_preserves_force(self):
        self.assertEqual(take_refresh(True, True), (True, False, False))
        self.assertEqual(take_refresh(False, False), (None, False, False))

    def test_cancel_reports_running_or_queued_and_only_signals_running(self):
        self.assertEqual(cancel_refresh(False, True), (True, False, False, False))
        self.assertEqual(cancel_refresh(True, False), (True, False, False, True))
        self.assertEqual(cancel_refresh(False, False, True), (True, False, False, False))
        self.assertEqual(cancel_refresh(False, False), (False, False, False, False))


if __name__ == "__main__":
    unittest.main()
