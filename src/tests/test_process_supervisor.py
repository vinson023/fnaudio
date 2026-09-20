import sys
import time
import unittest
import os
import tempfile
import threading
from unittest import mock

sys.path.insert(0, "app/server")

from services.process_supervisor import ProcessSupervisor


class ProcessSupervisorTests(unittest.TestCase):
    def test_restart_flag_does_not_coerce_non_boolean_values(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("flags", [sys.executable, "-c", "pass"], restart="false")
        with supervisor._lock:
            self.assertFalse(supervisor._entries["flags"]["restart"])

    def test_persisted_boolean_fields_do_not_coerce_strings(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("flags", [sys.executable, "-c", "pass"], restart=False)
        with supervisor._lock:
            supervisor._entries["flags"]["desired"] = "false"
            supervisor._entries["flags"]["restart_exhausted"] = "false"
        status = supervisor.status("flags")
        self.assertFalse(status["desired"])
        self.assertFalse(status["restart_exhausted"])
    def test_service_log_is_trimmed_to_bounded_tail(self):
        from services.process_supervisor import MAX_SERVICE_LOG_BYTES, _trim_service_log
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = handle.name
            handle.write(b"a" * (MAX_SERVICE_LOG_BYTES + 300000))
        try:
            _trim_service_log(path)
            self.assertEqual(os.path.getsize(path), MAX_SERVICE_LOG_BYTES)
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(1), b"a")
        finally:
            os.unlink(path)

    def test_monitor_start_failure_does_not_leave_phantom_thread(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        with mock.patch("services.process_supervisor.threading.Thread", side_effect=RuntimeError("no threads")):
            with self.assertRaises(RuntimeError):
                supervisor.register("idle", [sys.executable, "-c", "pass"])
        self.assertIsNone(supervisor._thread)
        self.assertFalse(supervisor._stopping)

    def test_failed_restart_uses_backoff_instead_of_retrying_every_poll(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("missing", [sys.executable, "-c", "pass"], restart=True, restart_backoff=2)
        with supervisor._lock:
            entry = supervisor._entries["missing"]
            entry["desired"] = True
            entry["restart_after"] = 0
        with mock.patch.object(supervisor, "_start_locked", return_value={"ok": False, "running": False, "message": "missing"}) as start:
            deadline = time.monotonic() + 0.5
            while start.call_count < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(start.call_count, 1)
            with supervisor._lock:
                self.assertGreater(supervisor._entries["missing"]["restart_after"], time.time() + 1.5)
                self.assertGreater(supervisor._entries["missing"]["restart_after_monotonic"], time.monotonic() + 1.5)
            time.sleep(0.05)
            self.assertEqual(start.call_count, 1)

    def test_restart_deadline_and_history_use_monotonic_clock(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("missing", [sys.executable, "-c", "pass"], restart=True, restart_backoff=2)
        with supervisor._lock:
            entry = supervisor._entries["missing"]
            entry["desired"] = True
            entry["restart_after"] = 0
            entry["restart_after_monotonic"] = 0
        with mock.patch.object(supervisor, "_start_locked", return_value={"ok": False, "running": False, "message": "missing"}):
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                with supervisor._lock:
                    if supervisor._entries["missing"]["restart_after_monotonic"] > 0:
                        break
                time.sleep(0.01)
        with supervisor._lock:
            self.assertGreater(supervisor._entries["missing"]["restart_after_monotonic"], time.monotonic())

    def test_failed_starts_are_capped_and_report_exhaustion(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        self.addCleanup(supervisor.shutdown)
        exhausted = mock.Mock()
        supervisor.register(
            "missing",
            [sys.executable, "-c", "pass"],
            restart=True,
            max_restarts=1,
            restart_window=10,
            restart_backoff=0.01,
            on_exhaust=exhausted,
        )
        with supervisor._lock:
            entry = supervisor._entries["missing"]
            entry["desired"] = True
            entry["restart_after"] = 0.0
            entry["restart_after_monotonic"] = 0.0
        with mock.patch.object(supervisor, "_start_locked", return_value={"ok": False, "running": False, "message": "missing"}) as start:
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and not supervisor.status("missing")["restart_exhausted"]:
                time.sleep(0.01)
        status = supervisor.status("missing")
        self.assertTrue(status["restart_exhausted"])
        self.assertFalse(status["desired"])
        self.assertEqual(start.call_count, 2)
        self.assertLessEqual(status["restart_count"], 1)
        exhausted.assert_called_once_with("missing", status)

    def test_manual_start_clears_monotonic_restart_state(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("manual", [sys.executable, "-c", "import time; time.sleep(2)"], restart=True)
        with supervisor._lock:
            entry = supervisor._entries["manual"]
            entry["restart_times"] = [time.time()]
            entry["restart_times_monotonic"] = [time.monotonic()]
            entry["restart_after"] = time.time() + 30
            entry["restart_after_monotonic"] = time.monotonic() + 30
        result = supervisor.start("manual")
        self.assertTrue(result["ok"])
        with supervisor._lock:
            self.assertEqual(supervisor._entries["manual"]["restart_times_monotonic"], [])
            self.assertEqual(supervisor._entries["manual"]["restart_after_monotonic"], 0.0)

    def test_stop_reaps_process_after_term_escalation(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("stuck", [sys.executable, "-c", "pass"])
        process = mock.Mock()
        process.poll.return_value = None
        process.pid = 123
        process.wait.side_effect = [TimeoutError("still running"), 0]
        with supervisor._lock:
            supervisor._entries["stuck"]["process"] = process
        with mock.patch("services.process_supervisor.os.name", "nt"):
            result = supervisor.stop("stuck")
        self.assertTrue(result["ok"])
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_count, 2)

    def test_monitor_reaps_naturally_exited_process_before_dropping_handle(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("exited", [sys.executable, "-c", "pass"], restart=False)
        process = mock.Mock()
        process.poll.return_value = 1
        process.wait.return_value = 1
        with supervisor._lock:
            supervisor._entries["exited"]["process"] = process
        deadline = time.time() + 1
        while time.time() < deadline:
            with supervisor._lock:
                if supervisor._entries["exited"]["process"] is None:
                    break
            time.sleep(0.01)
        process.wait.assert_called_with(timeout=0)
        with supervisor._lock:
            self.assertIsNone(supervisor._entries["exited"]["process"])

    def test_shutdown_joins_and_clears_monitor_thread(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        supervisor.register("idle", [sys.executable, "-c", "pass"], restart=False)
        thread = supervisor._thread
        self.assertIsNotNone(thread)
        supervisor.shutdown()
        self.assertFalse(thread.is_alive())
        self.assertIsNone(supervisor._thread)

    def test_shutdown_wakes_a_long_poll_without_restarting_processes(self):
        supervisor = ProcessSupervisor(poll_interval=30)
        supervisor.register("idle", [sys.executable, "-c", "pass"])
        with supervisor._lock:
            entry = supervisor._entries["idle"]
            entry["desired"] = True
            entry["restart"] = True
            entry["restart_after"] = 0.0
        started = time.monotonic()
        supervisor.shutdown()
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertIsNone(supervisor._thread)

    def test_monitor_drops_callbacks_after_shutdown_begins(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        callback = mock.Mock()
        supervisor._stopping = True
        supervisor._monitor_generation = 2

        supervisor._dispatch_callback_events(
            2, [(callback, "service", {"ok": True}, "callback failed: %s")]
        )

        callback.assert_not_called()

    def test_shutdown_waits_for_callback_gate_before_marking_stopped(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        entered = threading.Event()
        release = threading.Event()

        def callback(_name, _payload):
            entered.set()
            release.wait(1)

        with supervisor._callback_gate:
            dispatch = threading.Thread(
                target=supervisor._dispatch_callback_events,
                args=(0, [(callback, "service", {}, "callback failed: %s")]),
            )
            dispatch.start()
            self.assertFalse(entered.wait(0.05))
        self.assertTrue(entered.wait(1))

        stopping = threading.Thread(target=supervisor.shutdown)
        stopping.start()
        time.sleep(0.05)
        self.assertTrue(stopping.is_alive())
        release.set()
        dispatch.join(1)
        stopping.join(1)
        self.assertFalse(stopping.is_alive())
        self.assertTrue(supervisor._stopping)

    def test_callback_can_request_shutdown_without_deadlocking(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        called = threading.Event()

        def callback(_name, _payload):
            supervisor.shutdown()
            called.set()

        supervisor._dispatch_callback_events(
            supervisor._monitor_generation,
            [(callback, "service", {}, "callback failed: %s")],
        )
        self.assertTrue(called.is_set())
        self.assertTrue(supervisor._stopping)

    def test_restart_after_shutdown_timeout_replaces_old_monitor_generation(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        old_thread = mock.Mock()
        old_thread.is_alive.return_value = True
        supervisor._thread = old_thread
        supervisor._stopping = True
        supervisor._monitor_generation = 4
        with mock.patch.object(supervisor, "_monitor") as monitor, \
             mock.patch("services.process_supervisor.threading.Thread") as thread_class:
            new_thread = thread_class.return_value
            new_thread.is_alive.return_value = True
            supervisor._ensure_monitor()
        self.assertIs(supervisor._thread, new_thread)
        self.assertEqual(supervisor._monitor_generation, 5)
        thread_class.assert_called_once()
        self.assertEqual(thread_class.call_args.kwargs["args"], (5,))

    def test_restart_history_projection_is_bounded(self):
        from services.process_supervisor import MAX_RESTART_HISTORY, _bounded_restart_history
        self.assertEqual(_bounded_restart_history([1, "bad", 1, 2], 10), [1.0, 2.0])
        self.assertEqual(len(_bounded_restart_history(range(MAX_RESTART_HISTORY + 10), MAX_RESTART_HISTORY + 10)), MAX_RESTART_HISTORY)

    def test_poll_interval_is_bounded_and_finite(self):
        self.assertEqual(ProcessSupervisor(float("nan")).poll_interval, 2.0)
        self.assertEqual(ProcessSupervisor(float("inf")).poll_interval, 2.0)
        self.assertEqual(ProcessSupervisor(-1).poll_interval, 2.0)
        self.assertEqual(ProcessSupervisor(999).poll_interval, 2.0)
        self.assertEqual(ProcessSupervisor(0.05).poll_interval, 0.05)

    def test_register_rejects_unbounded_or_object_configuration(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register(
            "bounded",
            [sys.executable, "-c", "import time; time.sleep(0.1)"],
            max_restarts=10**1000,
            restart_window=float("inf"),
            restart_backoff=float("nan"),
            nice=999,
        )
        status = supervisor.status("bounded")
        self.assertEqual(status["nice"], 19)
        self.assertEqual(status["restart_count"], 0)
        self.assertTrue(supervisor.start("bounded")["ok"])

    def test_invalid_command_shape_is_reported_without_stringifying(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("bad", object())
        result = supervisor.start("bad")
        self.assertFalse(result["ok"])
        self.assertIn("executable not found", result["message"])

    def test_optional_nice_policy_is_visible_without_changing_default(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("idle", [sys.executable, "-c", "import time; time.sleep(0.2)"], restart=False, nice=3)
        self.assertEqual(supervisor.status("idle")["nice"], 3)

    def test_status_exposes_bounded_restart_observability(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("idle", [sys.executable, "-c", "import time; time.sleep(0.2)"], restart=False)
        with supervisor._lock:
            entry = supervisor._entries["idle"]
            entry["restart_times"] = list(range(100)) + [object()]
            entry["restart_count"] = object()
            entry["restart_window"] = float("nan")
            entry["restart_after"] = float("inf")
        status = supervisor.status("idle")
        self.assertLessEqual(len(status["recent_restart_times"]), 32)
        self.assertEqual(status["restart_count"], 0)
        self.assertEqual(status["restart_window"], 60.0)
        self.assertEqual(status["restart_after"], 0.0)

    def test_status_reports_the_newest_restart_stamps(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("idle", [sys.executable, "-c", "pass"], restart=False)
        with supervisor._lock:
            supervisor._entries["idle"]["restart_times"] = [float(index) for index in range(100)]

        recent = supervisor.status("idle")["recent_restart_times"]

        self.assertEqual(recent, [float(index) for index in range(68, 100)])

    def test_re_registering_keeps_the_newest_restart_history(self):
        # A crash loop has to survive a re-register, which every explicit
        # service start performs. Keeping the oldest stamps leaves the window
        # filter nothing recent, so max_restarts is never reached.
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        command = [sys.executable, "-c", "pass"]
        supervisor.register("svc", command, restart=True, max_restarts=2)
        now = time.time()
        mono = time.monotonic()
        with supervisor._lock:
            entry = supervisor._entries["svc"]
            entry["restart_times"] = [now - 500.0, now - 400.0, now - 3.0, now - 2.0, now - 1.0]
            entry["restart_times_monotonic"] = [mono - 500.0, mono - 400.0, mono - 3.0, mono - 2.0, mono - 1.0]

        supervisor.register("svc", command, restart=True, max_restarts=2)

        with supervisor._lock:
            kept = supervisor._entries["svc"]["restart_times"]
            kept_monotonic = supervisor._entries["svc"]["restart_times_monotonic"]
        self.assertEqual(kept, [now - 2.0, now - 1.0])
        self.assertEqual(kept_monotonic, [mono - 2.0, mono - 1.0])

    def test_service_log_trim_does_not_block_status(self):
        import services.process_supervisor as supervisor_module

        supervisor = ProcessSupervisor(poll_interval=0.01)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("logged", [sys.executable, "-c", "pass"], log_path="logs/mpd.log", restart=False)

        started = threading.Event()
        release = threading.Event()

        def slow_trim(_path):
            started.set()
            release.wait(2)

        done = threading.Event()
        with mock.patch.object(supervisor_module, "_trim_service_log", side_effect=slow_trim):
            self.assertTrue(started.wait(1))
            watcher = threading.Thread(target=lambda: (supervisor.status("logged"), done.set()))
            watcher.start()
            self.assertTrue(done.wait(1))
            release.set()
            watcher.join(2)
        self.assertFalse(watcher.is_alive())

    def test_register_recovers_a_corrupt_previous_restart_count(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("idle", [sys.executable, "-c", "pass"], restart=False)
        with supervisor._lock:
            supervisor._entries["idle"]["restart_count"] = object()
        supervisor.register("idle", [sys.executable, "-c", "pass"], restart=False)
        self.assertEqual(supervisor.status("idle")["restart_count"], 0)

    def test_register_replaces_running_process_when_launch_configuration_changes(self):
        supervisor = ProcessSupervisor(poll_interval=0.05)
        self.addCleanup(supervisor.shutdown)
        supervisor.register(
            "reloadable", [sys.executable, "-c", "pass"],
            log_path="old.log", restart=False, nice=0,
        )
        process = mock.Mock()
        process.poll.return_value = None
        process.pid = 123
        process.wait.return_value = 0
        with supervisor._lock:
            supervisor._entries["reloadable"]["process"] = process

        supervisor.register(
            "reloadable",
            [sys.executable, "-c", "different"],
            cwd=os.getcwd(),
            env={"FNAUDIO_RELOAD": "1"},
            log_path="new.log",
            restart=False,
            nice=3,
        )

        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=3)
        with supervisor._lock:
            self.assertIsNone(supervisor._entries["reloadable"]["process"])
            self.assertEqual(supervisor._entries["reloadable"]["command"][2], "different")
            self.assertEqual(supervisor._entries["reloadable"]["log_path"], "new.log")
            self.assertEqual(supervisor._entries["reloadable"]["nice"], 3)

    def test_monitor_recovers_corrupt_restart_fields_without_exiting(self):
        supervisor = ProcessSupervisor(poll_interval=0.01)
        self.addCleanup(supervisor.shutdown)
        supervisor.register("missing", [sys.executable, "-c", "pass"], restart=True)
        with supervisor._lock:
            entry = supervisor._entries["missing"]
            entry.update({
                "desired": True,
                "restart_after": object(),
                "restart_window": object(),
                "restart_backoff": object(),
                "max_restarts": object(),
                "restart_count": object(),
                "restart_times": [object(), 1.0],
            })
        with mock.patch.object(supervisor, "_start_locked", return_value={"ok": False, "running": False}):
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                with supervisor._lock:
                    restart_after = supervisor._entries["missing"]["restart_after"]
                    if isinstance(restart_after, (int, float)) and restart_after > time.time():
                        break
                time.sleep(0.01)
        self.assertTrue(supervisor._thread.is_alive())
        with supervisor._lock:
            self.assertGreater(supervisor._entries["missing"]["restart_after"], time.time())

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

    def test_restart_exhaustion_invokes_lifecycle_callback_once(self):
        supervisor = ProcessSupervisor(poll_interval=0.02)
        self.addCleanup(supervisor.shutdown)
        exhausted = mock.Mock()
        supervisor.register(
            "crasher",
            [sys.executable, "-c", "raise SystemExit(1)"],
            restart=True,
            max_restarts=1,
            restart_window=10,
            restart_backoff=0.01,
            on_exhaust=exhausted,
        )
        self.assertTrue(supervisor.start("crasher")["ok"])
        deadline = time.time() + 5
        while time.time() < deadline and not supervisor.status("crasher").get("restart_exhausted"):
            time.sleep(0.02)
        status = supervisor.status("crasher")
        self.assertTrue(status["restart_exhausted"])
        exhausted.assert_called_once_with("crasher", status)

    def test_lifecycle_callback_runs_without_holding_supervisor_lock(self):
        supervisor = ProcessSupervisor(poll_interval=0.02)
        self.addCleanup(supervisor.shutdown)
        callback_finished = threading.Event()

        def exhausted(_name, _status):
            status_finished = threading.Event()

            def read_status():
                supervisor.status("crasher")
                status_finished.set()

            thread = threading.Thread(target=read_status)
            thread.start()
            self.assertTrue(status_finished.wait(0.5))
            thread.join(timeout=0.5)
            callback_finished.set()

        supervisor.register(
            "crasher",
            [sys.executable, "-c", "raise SystemExit(1)"],
            restart=True,
            max_restarts=1,
            restart_window=10,
            restart_backoff=0.01,
            on_exhaust=exhausted,
        )
        self.assertTrue(supervisor.start("crasher")["ok"])
        deadline = time.time() + 5
        while time.time() < deadline and not callback_finished.is_set():
            time.sleep(0.02)
        self.assertTrue(callback_finished.is_set())


if __name__ == "__main__":
    unittest.main()
