import unittest

from app.server.metadata_request_budget import (
    DEFAULT_JOB_BUDGET_SECONDS,
    LYRICS_JOB_BUDGET_SECONDS,
    MAX_JOB_BUDGET_SECONDS,
    bounded_job_budget,
    provider_timeout,
)


class MetadataRequestBudgetTests(unittest.TestCase):
    def test_budget_is_finite_and_bounded(self):
        self.assertEqual(bounded_job_budget(LYRICS_JOB_BUDGET_SECONDS), float(LYRICS_JOB_BUDGET_SECONDS))
        self.assertEqual(bounded_job_budget(10**9), float(MAX_JOB_BUDGET_SECONDS))
        self.assertEqual(bounded_job_budget(object()), float(DEFAULT_JOB_BUDGET_SECONDS))

    def test_timeout_never_exceeds_remaining_budget(self):
        self.assertEqual(provider_timeout(10.2, 10.0, 10), 1)
        self.assertEqual(provider_timeout(20.0, 10.0, 3), 3)
        self.assertEqual(provider_timeout(10.0, 10.0, 10), 0)
        self.assertEqual(provider_timeout(None, 10.0, 10), 10)
        self.assertEqual(provider_timeout(None, 10.0, 3), 3)
        self.assertEqual(provider_timeout(None, 10.0, object()), 10)


if __name__ == "__main__":
    unittest.main()
