import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from services.airplay_service import AirplayService, airplay_probe


class AirplayServiceTests(unittest.TestCase):
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

    @mock.patch("services.airplay_service.AUDIO_OUTPUT_LEASE")
    @mock.patch.object(AirplayService, "_probe")
    def test_start_requires_and_releases_audio_lease(self, probe, lease):
        probe.return_value = {"available": True, "binaries": {"shairport_sync": "/usr/bin/shairport-sync"}}
        lease.acquire.return_value = {"ok": False, "message": "audio device is owned by mpd"}
        service = AirplayService({})
        result = service.start()
        self.assertFalse(result["ok"])
        self.assertIn("owned", result["message"])
        lease.acquire.assert_called_once()

    @mock.patch("services.airplay_service.AUDIO_OUTPUT_LEASE")
    @mock.patch.object(AirplayService, "_probe")
    @mock.patch.object(AirplayService, "_command", return_value=["/bin/true"])
    def test_stop_releases_lease(self, _command, probe, lease):
        probe.return_value = {"available": True, "binaries": {"shairport_sync": "/bin/true"}}
        lease.acquire.return_value = {"ok": True}
        lease.snapshot.return_value = {"owner": ""}
        service = AirplayService({})
        service.supervisor.start = mock.Mock(return_value={"ok": True, "running": True, "pid": 1})
        started = service.start()
        self.assertTrue(started["ok"])
        stopped = service.stop()
        self.assertTrue(stopped["ok"])
        lease.release.assert_called_with("airplay")


if __name__ == "__main__":
    unittest.main()
