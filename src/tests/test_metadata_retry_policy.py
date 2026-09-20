import unittest

from app.server.metadata_retry_policy import should_auto_retry_failed


class MetadataRetryPolicyTests(unittest.TestCase):
    def test_only_stale_failed_jobs_are_retried(self):
        self.assertFalse(should_auto_retry_failed("pending", 100, 200))
        self.assertFalse(should_auto_retry_failed("failed", 100, 150))
        self.assertTrue(should_auto_retry_failed("failed", 100, 100 + 60))
        self.assertTrue(should_auto_retry_failed("no_match", 100, 100 + 60))
        self.assertFalse(should_auto_retry_failed("no_match", 100, 150))

    def test_malformed_values_fail_closed(self):
        self.assertTrue(should_auto_retry_failed("failed", object(), 1000))
        self.assertTrue(should_auto_retry_failed("no_match", 0, 1000))
        self.assertFalse(should_auto_retry_failed("failed", 1000, 900))
        self.assertFalse(should_auto_retry_failed("failed", 1000, 1100, 0))


if __name__ == "__main__":
    unittest.main()
