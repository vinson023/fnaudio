"""R201 - bounded decisions for a metadata queue that never drains.

Device evidence: ``pending`` sat at 19988 of a 20000 limit with 375387 dropped
jobs, because every fifteen-second reconcile flipped expired terminal jobs back
to pending and the same number was dropped again.  These helpers are the whole
policy: no SQLite, no threads, no config objects, and they fail open.
"""

import sys
import unittest

sys.path.insert(0, "app/server")

import metadata_queue_backlog_policy as policy


class QueueBacklogRatioTests(unittest.TestCase):
    def test_ratio_is_bounded_to_one(self):
        self.assertEqual(policy.queue_backlog_ratio(10000, 20000), 0.5)
        self.assertEqual(policy.queue_backlog_ratio(99999, 20000), 1.0)

    def test_unusable_limit_reads_as_no_backlog(self):
        for limit in (0, -1, None, "x", True):
            with self.subTest(limit=limit):
                self.assertEqual(policy.queue_backlog_ratio(5, limit), 0.0)

    def test_an_absurd_limit_is_capped_instead_of_overflowing(self):
        # The cap is what keeps a hostile counter from turning the ratio into
        # an arbitrary-precision division on a worker thread.
        self.assertEqual(policy.queue_backlog_ratio(5, 10 ** 40), 5e-12)
        self.assertTrue(0.0 <= policy.queue_backlog_ratio(10 ** 40, 10 ** 40) <= 1.0)

    def test_unusable_pending_reads_as_zero(self):
        for pending in (None, -3, "abc", True):
            with self.subTest(pending=pending):
                self.assertEqual(policy.queue_backlog_ratio(pending, 20000), 0.0)


class BacklogTests(unittest.TestCase):
    def test_headroom_stops_the_sweep_before_the_ceiling(self):
        self.assertFalse(policy.queue_is_backlogged(15999, 20000))
        self.assertTrue(policy.queue_is_backlogged(16000, 20000))
        self.assertTrue(policy.queue_is_backlogged(20000, 20000))

    def test_requeue_allowed_is_the_mirror_decision(self):
        self.assertTrue(policy.requeue_allowed(100, 20000))
        self.assertFalse(policy.requeue_allowed(20000, 20000))
        self.assertTrue(policy.requeue_allowed(0, 0), "an unknown limit must fail open")

    def test_headroom_is_clamped_not_trusted(self):
        # Zero, NaN and above-one headrooms all collapse to the built-in 0.8 or
        # to 1.0, never to "always backlogged" or "never backlogged".
        self.assertFalse(policy.queue_is_backlogged(79, 100, headroom=0.0))
        self.assertTrue(policy.queue_is_backlogged(80, 100, headroom=0.0))
        self.assertTrue(policy.queue_is_backlogged(80, 100, headroom=float("nan")))
        self.assertFalse(policy.queue_is_backlogged(99, 100, headroom=2))
        self.assertTrue(policy.queue_is_backlogged(100, 100, headroom=2))


class CadenceTests(unittest.TestCase):
    def test_quiet_queue_keeps_the_historical_interval(self):
        self.assertEqual(policy.reconcile_interval_seconds(), 15.0)
        self.assertTrue(policy.should_run_reconcile(15.0))
        self.assertFalse(policy.should_run_reconcile(14.9))

    def test_backlogged_queue_slows_down(self):
        self.assertEqual(
            policy.reconcile_interval_seconds(backlogged=True),
            policy.RECONCILE_BACKLOG_INTERVAL_SECONDS,
        )
        self.assertFalse(policy.should_run_reconcile(30.0, backlogged=True))
        self.assertTrue(policy.should_run_reconcile(120.0, backlogged=True))

    def test_force_always_runs_immediately(self):
        self.assertEqual(policy.reconcile_interval_seconds(force=True, backlogged=True), 0.0)
        self.assertTrue(policy.should_run_reconcile(0.0, force=True, backlogged=True))

    def test_a_missing_clock_fails_open(self):
        for elapsed in (None, "x", float("nan"), float("inf")):
            with self.subTest(elapsed=elapsed):
                self.assertTrue(policy.should_run_reconcile(elapsed, backlogged=True))

    def test_a_rewound_clock_is_not_treated_as_a_missing_one(self):
        # A negative interval is a real reading, and the safe answer to "less
        # than nothing has passed" is to wait, not to start whole-library work.
        self.assertFalse(policy.should_run_reconcile(-1, backlogged=True))
        self.assertFalse(policy.should_run_reconcile(-1))
        self.assertTrue(policy.should_run_reconcile(-1, force=True))


if __name__ == "__main__":
    unittest.main()
