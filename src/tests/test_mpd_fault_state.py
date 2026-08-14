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


if __name__ == "__main__":
    unittest.main()
