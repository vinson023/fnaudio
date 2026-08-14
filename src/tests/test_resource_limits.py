import threading
import time
import unittest

import sys

sys.path.insert(0, "app/server")

from resource_limits import ConcurrencyGate, ResourceLimitError, bounded_int


class ResourceLimitTests(unittest.TestCase):
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
        started = time.monotonic()
        with self.assertRaises(ResourceLimitError):
            with gate.slot(1, timeout=0.02):
                pass
        self.assertLess(time.monotonic() - started, 0.5)
        release.set()
        thread.join(1)

        with self.assertRaisesRegex(RuntimeError, "body failed"):
            with gate.slot(1):
                raise RuntimeError("body failed")
        self.assertEqual(gate.snapshot()["active"], 0)
        self.assertEqual(gate.snapshot()["peak"], 1)

    def test_bounded_int_handles_invalid_and_out_of_range_values(self):
        self.assertEqual(bounded_int({"workers": "bad"}, "workers", 2, 1, 8), 2)
        self.assertEqual(bounded_int({"workers": -1}, "workers", 2, 1, 8), 1)
        self.assertEqual(bounded_int({"workers": 99}, "workers", 2, 1, 8), 8)


if __name__ == "__main__":
    unittest.main()
