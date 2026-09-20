import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_job_policy import final_status, result_is_local_fallback, retry_attempt, retry_delay_seconds, worker_status


class MetadataJobPolicyTests(unittest.TestCase):
    def test_final_status_distinguishes_skip_success_failure_and_no_match(self):
        self.assertEqual(final_status("skipped"), "skipped")
        self.assertEqual(final_status({"ok": True}), "done")
        self.assertEqual(final_status(None), "no_match")
        self.assertEqual(final_status(None, True), "failed")
        self.assertTrue(result_is_local_fallback({"source": "filename"}))
        self.assertEqual(final_status({"source": "filename"}, True), "failed")
        self.assertEqual(final_status({"source": "qq", "image_url": "x"}, True), "done")

    def test_retry_attempt_is_bounded_and_rejects_invalid_values(self):
        self.assertTrue(retry_attempt(1, 5))
        self.assertFalse(retry_attempt(5, 5))
        self.assertFalse(retry_attempt(-1, 5))
        self.assertFalse(retry_attempt("bad", 5))

    def test_retry_delay_caps_before_exponentiation(self):
        self.assertEqual(retry_delay_seconds(0), 60)
        self.assertEqual(retry_delay_seconds(5), 1920)
        self.assertEqual(retry_delay_seconds(999999999), 3600)
        self.assertEqual(retry_delay_seconds(object()), 0)

    def test_worker_status_is_safe_for_malformed_payloads_and_lyric_outages(self):
        self.assertEqual(worker_status({"lyrics": "ok"}, True, True, "lyrics"), "done")
        self.assertEqual(worker_status({}, False, True, "lyrics"), "failed")
        self.assertEqual(worker_status([], False, False, "track"), "no_match")
        self.assertEqual(worker_status({"source": "filename"}, True, False, "track"), "failed")


if __name__ == "__main__":
    unittest.main()
