import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from services.airplay_service import AirplayService, MAX_PROC_CMDLINE_BYTES, _process_running, airplay_probe


class AirplayServiceTests(unittest.TestCase):
    def _service(self, config):
        """Build a service whose supervisor monitor is guaranteed to be shut down.

        `ProcessSupervisor` starts its monitor thread in its constructor, and the monitor
        only drains once something stops or shuts the supervisor down.  Without this, a test
        that exercises `start()` and never reaches `service.stop()` leaves a live
        `fnaudio-process-supervisor` for the rest of the suite; the R88 audit found one
        still running at interpreter exit.
        """
        service = AirplayService(config)
        self.addCleanup(service.supervisor.shutdown)
        return service
    @mock.patch("services.airplay_service._process_running", return_value=False)
    @mock.patch("services.airplay_service._first_binary", side_effect=["", ""])
    def test_missing_dependencies_are_not_reported_as_supported(self, _binary, _running):
        result = airplay_probe({})

        self.assertFalse(result["available"])
        self.assertFalse(result["airplay1"])
        self.assertFalse(result["airplay2"])
        self.assertIn("shairport-sync", result["message"])

    @mock.patch("services.airplay_service._process_running", return_value=True)
    @mock.patch("services.airplay_service._first_binary", side_effect=["/usr/bin/shairport-sync", "/usr/bin/nqptp"])
    def test_airplay2_requires_both_binaries(self, _binary, _running):
        result = airplay_probe({"airplay_enabled": True})

        self.assertTrue(result["available"])
        self.assertTrue(result["configured"])
        self.assertTrue(result["running"])
        self.assertTrue(result["airplay2"])

    @mock.patch("services.airplay_service._process_running", return_value=False)
    @mock.patch("services.airplay_service._first_binary", side_effect=["/usr/bin/shairport-sync", ""])
    def test_probe_does_not_coerce_string_configuration(self, _binary, _running):
        self.assertFalse(airplay_probe({"airplay_enabled": "false"})["configured"])

    def test_process_probe_reads_cmdline_with_a_bound(self):
        class Handle:
            def __init__(self):
                self.size = None

            def read(self, size=-1):
                self.size = size
                return b"x" * (MAX_PROC_CMDLINE_BYTES + 100)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        handle = Handle()
        with mock.patch("services.airplay_service.os.name", "posix"), \
             mock.patch("services.airplay_service.os.path.isdir", return_value=True), \
             mock.patch("services.airplay_service.os.listdir", return_value=["123"]), \
             mock.patch("services.airplay_service.open", return_value=handle):
            self.assertFalse(_process_running("shairport"))
        self.assertEqual(handle.size, MAX_PROC_CMDLINE_BYTES + 1)

    @mock.patch("services.airplay_service.AUDIO_OUTPUT_LEASE")
    @mock.patch.object(AirplayService, "_probe")
    def test_start_requires_and_releases_audio_lease(self, probe, lease):
        probe.return_value = {"available": True, "binaries": {"shairport_sync": "/usr/bin/shairport-sync"}}
        lease.acquire.return_value = {"ok": False, "message": "audio device is owned by mpd"}
        service = self._service({})
        result = service.start()
        self.assertFalse(result["ok"])
        self.assertIn("owned", result["message"])
        lease.acquire.assert_called_once()

    @mock.patch("services.airplay_service.AUDIO_OUTPUT_LEASE")
    @mock.patch.object(AirplayService, "_probe")
    def test_invalid_custom_command_fails_before_acquiring_audio_lease(self, probe, lease):
        probe.return_value = {"available": True, "binaries": {"shairport_sync": "/usr/bin/shairport-sync"}}
        service = self._service({"airplay_command": 'shairport-sync --name "unterminated'})

        result = service.start()

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "invalid AirPlay command")
        lease.acquire.assert_not_called()

    @mock.patch("services.airplay_service.AUDIO_OUTPUT_LEASE")
    @mock.patch.object(AirplayService, "_probe")
    @mock.patch.object(AirplayService, "_command", return_value=["/bin/true"])
    def test_stop_releases_lease(self, _command, probe, lease):
        probe.return_value = {"available": True, "binaries": {"shairport_sync": "/bin/true"}}
        lease.acquire.return_value = {"ok": True}
        lease.snapshot.return_value = {"owner": ""}
        service = self._service({})
        service.supervisor.start = mock.Mock(return_value={"ok": True, "running": True, "pid": 1})
        started = service.start()
        self.assertTrue(started["ok"])
        stopped = service.stop()
        self.assertTrue(stopped["ok"])
        lease.release.assert_called_with("airplay")

    @mock.patch("services.airplay_service.AUDIO_OUTPUT_LEASE")
    @mock.patch.object(AirplayService, "_probe")
    @mock.patch.object(AirplayService, "_command", return_value=["/bin/true"])
    def test_start_normalizes_malformed_supervisor_status(self, _command, probe, lease):
        probe.return_value = {"available": True, "binaries": {"shairport_sync": "/bin/true"}}
        lease.acquire.return_value = {"ok": True}
        lease.snapshot.return_value = {"owner": ""}
        service = self._service({})
        service.supervisor.start = mock.Mock(return_value={"ok": "false", "running": "false"})

        result = service.start()

        self.assertIs(result["ok"], False)
        self.assertIs(result["running"], False)
        lease.release.assert_called_once_with("airplay")

    @mock.patch("services.airplay_service.AUDIO_OUTPUT_LEASE")
    def test_stop_normalizes_malformed_supervisor_status(self, lease):
        lease.snapshot.return_value = {"owner": ""}
        service = self._service({})
        service._registered = True
        service.supervisor.stop = mock.Mock(return_value={"ok": "false", "running": "true"})

        result = service.stop()

        self.assertIs(result["ok"], False)
        self.assertIs(result["running"], False)
        lease.release.assert_called_once_with("airplay")

    @mock.patch("services.airplay_service.AUDIO_OUTPUT_LEASE")
    def test_restart_exhaustion_releases_lease(self, lease):
        service = self._service({})
        service._release_audio_output("airplay", {"restart_exhausted": True})
        lease.release.assert_called_once_with("airplay")

    @mock.patch("services.airplay_service._process_running", return_value=False)
    @mock.patch("services.airplay_service._first_binary", side_effect=["", ""])
    def test_probe_rejects_non_text_binary_paths(self, _binary, _running):
        result = airplay_probe({"shairport_sync_path": object(), "nqptp_path": []})
        self.assertFalse(result["available"])
        first_candidates = _binary.call_args_list[0].args[0]
        self.assertEqual(first_candidates[0], "")

    def test_command_rejects_non_text_device_without_stringifying_it(self):
        service = self._service({"airplay_alsa_device": object()})
        self.assertEqual(service._command("/usr/bin/shairport-sync"), ["/usr/bin/shairport-sync"])


if __name__ == "__main__":
    unittest.main()
