import threading
import time
import unittest

import sys

sys.path.insert(0, "app/server")

from resource_limits import ConcurrencyGate, MAX_COUNTER_VALUE, MAX_RESOURCE_NAME_CHARS, MAX_RESOURCE_PATH_CHARS, MAX_WAIT_SECONDS, ResourceLimitError, _increment_counter, bounded_int, disk_has_reserve


class ResourceLimitTests(unittest.TestCase):
    def test_wait_seconds_metric_is_capped_for_long_running_processes(self):
        gate = ConcurrencyGate("bounded")
        gate._add_wait_seconds(MAX_WAIT_SECONDS + 123.0)
        gate._add_wait_seconds(999999.0)
        self.assertEqual(gate.snapshot()["wait_seconds"], float(MAX_WAIT_SECONDS))
        gate._add_wait_seconds(10 ** 10000)
        self.assertEqual(gate.snapshot()["wait_seconds"], float(MAX_WAIT_SECONDS))

    def test_long_running_counters_are_capped(self):
        gate = ConcurrencyGate("bounded")
        self.assertEqual(_increment_counter(MAX_COUNTER_VALUE), MAX_COUNTER_VALUE)
        self.assertEqual(_increment_counter(MAX_COUNTER_VALUE + 1), MAX_COUNTER_VALUE)
        gate._acquired = _increment_counter(gate._acquired)
        gate._waited = _increment_counter(gate._waited)
        gate._rejected = _increment_counter(gate._rejected)
        gate._waiter_rejected = _increment_counter(gate._waiter_rejected)
        gate._timed_out = _increment_counter(gate._timed_out)
        self.assertEqual(gate.snapshot()["acquired"], 1)
        self.assertEqual(gate.snapshot()["waited"], 1)
        self.assertEqual(gate.snapshot()["rejected"], 1)
        self.assertEqual(gate.snapshot()["waiter_rejected"], 1)
        self.assertEqual(gate.snapshot()["timed_out"], 1)

    def test_counter_increment_recovers_from_corrupted_values(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("counter must not coerce custom values")

        self.assertEqual(_increment_counter(True), 1)
        self.assertEqual(_increment_counter(Explosive()), 1)
        self.assertEqual(_increment_counter(-10), 1)

    def test_gate_rejects_waiter_at_limit_and_releases_after_exception(self):
        gate = ConcurrencyGate("test")
        entered = threading.Event()
        release = threading.Event()

        def holder():
            with gate.slot(1):
                entered.set()
                release.wait(1)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(entered.wait(1))
        waiter_ready = threading.Event()
        waiter_done = threading.Event()

        def waiting_request():
            waiter_ready.set()
            with gate.slot(1, timeout=0.5):
                waiter_done.set()

        waiter = threading.Thread(target=waiting_request)
        waiter.start()
        self.assertTrue(waiter_ready.wait(1))
        deadline = time.monotonic() + 0.5
        while gate.snapshot()["waiting"] != 1 and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(gate.snapshot()["waiting"], 1)
        self.assertEqual(gate.snapshot()["peak_waiting"], 1)
        started = time.monotonic()
        with self.assertRaises(ResourceLimitError):
            with gate.slot(1, timeout=0.02):
                pass
        self.assertLess(time.monotonic() - started, 0.5)
        release.set()
        thread.join(1)
        waiter.join(1)
        self.assertTrue(waiter_done.is_set())

        with self.assertRaisesRegex(RuntimeError, "body failed"):
            with gate.slot(1):
                raise RuntimeError("body failed")
        self.assertEqual(gate.snapshot()["active"], 0)
        self.assertEqual(gate.snapshot()["peak"], 1)
        self.assertEqual(gate.snapshot()["acquired"], 3)
        self.assertGreaterEqual(gate.snapshot()["waited"], 2)
        self.assertEqual(gate.snapshot()["waiting"], 0)
        self.assertGreaterEqual(gate.snapshot()["peak_waiting"], 1)
        self.assertEqual(gate.snapshot()["rejected"], 1)
        self.assertEqual(gate.snapshot()["timed_out"], 1)
        self.assertGreaterEqual(gate.snapshot()["wait_seconds"], 0.02)

    def test_bounded_int_handles_invalid_and_out_of_range_values(self):
        self.assertEqual(bounded_int({"workers": "bad"}, "workers", 2, 1, 8), 2)
        self.assertEqual(bounded_int({"workers": -1}, "workers", 2, 1, 8), 1)
        self.assertEqual(bounded_int({"workers": 99}, "workers", 2, 1, 8), 8)
        self.assertEqual(bounded_int({"workers": 10 ** 10000}, "workers", 2, 1, 8), 2)

    def test_bounded_int_does_not_coerce_untrusted_config_values(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("config values must not be coerced")
            def __float__(self):
                raise AssertionError("config values must not be coerced")

        self.assertEqual(bounded_int({"workers": Explosive()}, "workers", 2, 1, 8), 2)
        self.assertEqual(bounded_int(Explosive(), "workers", 2, 1, 8), 2)
        self.assertEqual(bounded_int({}, "workers", Explosive(), 1, 8), 1)

    def test_bounded_int_isolates_broken_config_mapping(self):
        class Broken(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken config")

        self.assertEqual(bounded_int(Broken(), "workers", 2, 1, 8), 2)

    def test_disk_reserve_rejects_untrusted_inputs_without_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("disk checks must not stringify custom paths")
            def __int__(self):
                raise AssertionError("disk checks must not coerce custom sizes")
            def __float__(self):
                raise AssertionError("disk checks must not coerce custom sizes")

        self.assertFalse(disk_has_reserve(Explosive(), 0, 0))
        self.assertFalse(disk_has_reserve(".", Explosive(), 0))
        self.assertFalse(disk_has_reserve(".", 0, Explosive()))

    def test_disk_reserve_rejects_overlong_paths_before_filesystem_access(self):
        self.assertFalse(disk_has_reserve("x" * (MAX_RESOURCE_PATH_CHARS + 1), 0, 0))

    def test_disk_reserve_rejects_invalid_paths_without_raising(self):
        self.assertFalse(disk_has_reserve(".\x00invalid", 0, 0))

    def test_gate_rejects_untrusted_numeric_objects_without_coercion(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("resource limits must not coerce custom values")
            def __float__(self):
                raise AssertionError("resource limits must not coerce custom values")
            def __str__(self):
                raise AssertionError("resource limits must not stringify custom values")

        gate = ConcurrencyGate(Explosive(), Explosive())
        self.assertEqual(gate.name, "resource")
        with gate.slot(Explosive(), timeout=Explosive(), max_waiters=Explosive()):
            self.assertEqual(gate.snapshot()["active"], 1)
        huge_gate = ConcurrencyGate("huge", 10 ** 10000)
        with huge_gate.slot(1, timeout=10 ** 10000):
            self.assertEqual(huge_gate.snapshot()["active"], 1)

    def test_gate_name_is_bounded_and_empty_names_use_default(self):
        self.assertEqual(ConcurrencyGate("x" * (MAX_RESOURCE_NAME_CHARS + 10)).name, "x" * MAX_RESOURCE_NAME_CHARS)
        self.assertEqual(ConcurrencyGate("").name, "resource")

    def test_gate_snapshot_isolates_corrupt_internal_metrics(self):
        gate = ConcurrencyGate("snapshot")
        gate._active = object()
        gate._peak = -3
        gate._acquired = float("nan")
        gate._waited = 10**30
        gate._waiting = object()
        gate._peak_waiting = float("inf")
        gate._rejected = -1
        gate._waiter_rejected = object()
        gate._timed_out = float("nan")
        gate._wait_seconds = float("nan")
        snapshot = gate.snapshot()
        self.assertEqual(snapshot["active"], 0)
        self.assertEqual(snapshot["peak"], 0)
        self.assertEqual(snapshot["waited"], MAX_COUNTER_VALUE)
        self.assertEqual(snapshot["peak_waiting"], 0)
        self.assertEqual(snapshot["wait_seconds"], 0.0)

    def test_wait_seconds_accumulation_recovers_from_corrupt_internal_value(self):
        gate = ConcurrencyGate("accumulate")
        gate._wait_seconds = object()
        gate._add_wait_seconds(1.25)
        self.assertEqual(gate.snapshot()["wait_seconds"], 1.25)

    def test_gate_rejects_when_waiter_bound_is_full(self):
        gate = ConcurrencyGate("bounded", max_waiters=1)
        entered = threading.Event()
        release = threading.Event()

        def holder():
            with gate.slot(1):
                entered.set()
                release.wait(1)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(entered.wait(1))
        waiting = threading.Thread(target=lambda: self._hold_waiter(gate))
        waiting.start()
        deadline = time.monotonic() + 0.5
        while gate.snapshot()["waiting"] != 1 and time.monotonic() < deadline:
            time.sleep(0.005)
        with self.assertRaisesRegex(ResourceLimitError, "waiting queue is full"):
            with gate.slot(1, timeout=0.5):
                pass
        snapshot = gate.snapshot()
        self.assertEqual(snapshot["waiter_limit"], 1)
        self.assertEqual(snapshot["waiter_rejected"], 1)
        self.assertEqual(snapshot["timed_out"], 0)
        release.set()
        thread.join(1)
        waiting.join(1)

    def test_try_acquire_rejects_without_admitting_a_waiting_thread(self):
        gate = ConcurrencyGate("http", max_waiters=0)
        self.assertTrue(gate.try_acquire(1))
        self.assertFalse(gate.try_acquire(1))
        snapshot = gate.snapshot()
        self.assertEqual(snapshot["active"], 1)
        self.assertEqual(snapshot["rejected"], 1)
        self.assertEqual(snapshot["waiting"], 0)
        gate.release()
        self.assertEqual(gate.snapshot()["active"], 0)

    def test_gate_accepts_per_request_waiter_limit(self):
        gate = ConcurrencyGate("configurable")
        entered = threading.Event()
        release = threading.Event()

        def holder():
            with gate.slot(1):
                entered.set()
                release.wait(1)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaisesRegex(ResourceLimitError, "waiting queue is full"):
            with gate.slot(1, timeout=0.5, max_waiters=0):
                pass
        release.set()
        thread.join(1)

    def test_admitted_waiter_survives_spurious_wakeup(self):
        gate = ConcurrencyGate("spurious", max_waiters=1)
        entered = threading.Event()
        release = threading.Event()
        completed = threading.Event()

        def holder():
            with gate.slot(1):
                entered.set()
                release.wait(1)

        def waiter():
            with gate.slot(1, timeout=0.5):
                completed.set()

        holder_thread = threading.Thread(target=holder)
        holder_thread.start()
        self.assertTrue(entered.wait(1))
        waiter_thread = threading.Thread(target=waiter)
        waiter_thread.start()
        deadline = time.monotonic() + 0.5
        while gate.snapshot()["waiting"] != 1 and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(gate.snapshot()["waiting"], 1)
        with gate._condition:
            gate._condition.notify_all()
        time.sleep(0.01)
        release.set()
        holder_thread.join(1)
        waiter_thread.join(1)
        self.assertTrue(completed.is_set())

    @staticmethod
    def _hold_waiter(gate):
        with gate.slot(1, timeout=0.5):
            pass


if __name__ == "__main__":
    unittest.main()
