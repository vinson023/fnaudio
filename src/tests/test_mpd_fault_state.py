import threading
import sys
import os
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from services.mpd_service import MpdService


class MpdFaultStateTests(unittest.TestCase):
    def make_service(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with mock.patch.object(MpdService, "_select_port", return_value=56660), mock.patch.object(
            MpdService, "_find_binary", return_value="/usr/bin/mpd"
        ), mock.patch.object(MpdService, "_data_root", return_value=temp.name):
            return MpdService({"mpd_port": 56660, "library_path": "/music"}, app_root=temp.name)

    def test_unexpected_stop_requires_confirmation(self):
        service = self.make_service()
        service._observe_fault("PLAYING")
        service._observe_fault("STOPPED")
        self.assertEqual(service.fault_status()["state"], "SUSPECT")
        service._observe_fault("STOPPED")
        self.assertEqual(service.fault_status()["state"], "DEGRADED")

    def test_suppressed_stop_is_idle_not_fault(self):
        service = self.make_service()
        service._observe_fault("PLAYING")
        service._observe_fault("STOPPED", suppressed=True)
        state = service.fault_status()
        self.assertEqual(state["state"], "IDLE")
        self.assertEqual(state["consecutive_failures"], 0)

    def test_recovery_clears_fault_and_counts_recovery(self):
        service = self.make_service()
        service._observe_fault("PLAYING")
        service._observe_fault(error="alsa error")
        service._mark_recovering()
        service._mark_recovered("PLAYING")
        state = service.fault_status()
        self.assertEqual(state["state"], "PLAYING")
        self.assertEqual(state["consecutive_failures"], 0)
        self.assertEqual(state["recovery_count"], 1)
        self.assertEqual(state["last_error"], "")

    def test_corrupt_fault_counters_are_normalized(self):
        service = self.make_service()
        service._fault_state.update(
            {
                "status_samples": object(),
                "status_latency_ms": float("nan"),
                "consecutive_failures": "not-a-number",
                "recovery_count": float("inf"),
            }
        )

        service._record_status_latency(float("nan"))
        service._observe_fault(error="alsa error")
        service._mark_recovered("PLAYING")

        state = service.fault_status()
        self.assertEqual(state["status_samples"], 1)
        self.assertEqual(state["status_latency_ms"], 0.0)
        self.assertEqual(state["consecutive_failures"], 0)
        self.assertEqual(state["recovery_count"], 1)

    def test_corrupt_playback_error_counters_are_normalized(self):
        service = self.make_service()
        service._queue_entries = [{"track_id": "one"}]
        service._playback_error_state.update({"count": object(), "by_category": {"output_io_failed": float("nan")}})
        service._underrun_state.update({"count": object(), "restart_suppressed": "invalid"})
        with open(service.log_path, "w", encoding="utf-8") as handle:
            handle.write("output: buffer underrun\n")

        with mock.patch.object(service, "restart", return_value={"running": False}):
            service._watch_for_playback_errors()

        self.assertEqual(service._playback_error_state["count"], 1)
        self.assertEqual(service._underrun_state["count"], 1)

    def test_corrupt_source_is_recorded_without_becoming_output_fault_or_underrun(self):
        service = self.make_service()
        service._queue_entries = [{"track_id": "one"}]
        with open(service.log_path, "w", encoding="utf-8") as handle:
            handle.write("flac: invalid sync code\n")

        service._watch_for_playback_errors()

        self.assertEqual(service._playback_error_state["last_category"], "source_corrupt")
        self.assertEqual(service._underrun_state["count"], 0)
        self.assertEqual(service.fault_status()["state"], "IDLE")

    def test_generic_alsa_error_is_output_fault_but_not_underrun(self):
        service = self.make_service()
        service._queue_entries = [{"track_id": "one"}]
        with open(service.log_path, "w", encoding="utf-8") as handle:
            handle.write("output: ALSA error: broken pipe\n")

        with mock.patch.object(service, "restart", return_value={"running": False}) as restart:
            service._watch_for_playback_errors()

        self.assertEqual(service._playback_error_state["last_category"], "output_io_failed")
        self.assertEqual(service._underrun_state["count"], 0)
        self.assertEqual(service.fault_status()["state"], "SUSPECT")
        restart.assert_called_once()

    def test_real_buffer_underrun_keeps_legacy_counter(self):
        service = self.make_service()
        service._queue_entries = [{"track_id": "one"}]
        with open(service.log_path, "w", encoding="utf-8") as handle:
            handle.write("output: buffer underrun\n")

        with mock.patch.object(service, "restart", return_value={"running": False}):
            service._watch_for_playback_errors()

        self.assertEqual(service._underrun_state["count"], 1)
        self.assertEqual(service._playback_error_state["last_category"], "buffer_underrun")


    def test_first_underrun_restarts_early_in_the_monotonic_clock(self):
        service = self.make_service()
        service._queue_entries = [{"track_id": "one"}]
        with open(service.log_path, "w", encoding="utf-8") as handle:
            handle.write("output: buffer underrun\n")

        # A NAS can boot, start MPD and underrun inside the first 30 seconds of
        # uptime. The debounce must not treat that as "restarted just now".
        with mock.patch.object(service, "restart", return_value={"running": False}) as restart, \
             mock.patch("services.mpd_service.time.monotonic", return_value=5.0):
            service._watch_for_playback_errors()

        restart.assert_called_once()
        self.assertEqual(service._underrun_state["restart_suppressed"], 0)

    def test_idle_status_waits_for_the_error_state_lock(self):
        service = self.make_service()
        observed = []

        def reader():
            observed.append(service.idle_status())

        self.assertTrue(service._error_state_lock.acquire())
        worker = threading.Thread(target=reader)
        worker.start()
        try:
            worker.join(timeout=0.5)
            self.assertTrue(worker.is_alive(), "idle_status copied the shared error state unlocked")
        finally:
            service._error_state_lock.release()
        worker.join(timeout=5)

        self.assertFalse(worker.is_alive())
        self.assertIn("underrun", observed[0])
        self.assertIn("playback_errors", observed[0])


if __name__ == "__main__":
    unittest.main()
