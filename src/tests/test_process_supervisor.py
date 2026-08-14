import sys
import time
import unittest

sys.path.insert(0, "app/server")

from services.process_supervisor import ProcessSupervisor


class ProcessSupervisorTests(unittest.TestCase):
    def test_optional_nice_policy_is_visible_without_changing_default(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("idle", [sys.executable, "-c", "import time; time.sleep(0.2)"], restart=False, nice=3)
        self.assertEqual(supervisor.status("idle")["nice"], 3)

    def test_crashing_process_is_eventually_capped(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register(
            "crasher",
            [sys.executable, "-c", "raise SystemExit(1)"],
            restart=True,
            max_restarts=2,
            restart_window=10,
            restart_backoff=0.01,
        )
        self.assertTrue(supervisor.start("crasher")["ok"])
        deadline = time.time() + 5
        status = supervisor.status("crasher")
        while time.time() < deadline and not status.get("restart_exhausted"):
            time.sleep(0.05)
            status = supervisor.status("crasher")
        self.assertTrue(status.get("restart_exhausted"))
        self.assertFalse(status.get("desired"))
        self.assertLessEqual(status.get("restart_count", 99), 2)


if __name__ == "__main__":
    unittest.main()
