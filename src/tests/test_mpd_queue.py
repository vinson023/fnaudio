import sys
import tempfile
import unittest
import time
import threading
import os
from unittest import mock

sys.path.insert(0, "app/server")

from playback.models import TrackRef
from services.mpd_service import MAX_MPD_PROC_CMDLINE_BYTES, MAX_MPD_QUEUE_ENTRIES, MpdService, _config_int, _config_text


class MpdQueueTests(unittest.TestCase):
    def test_playback_modes_do_not_coerce_string_shuffle(self):
        mpd = mock.Mock()
        from playback.mpd_client import _set_playback_modes
        _set_playback_modes(mpd, "off", "false")
        mpd.command.assert_any_call("random", 0)
    def test_mpd_service_config_text_rejects_object_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("configuration object was stringified")

        hostile = Explosive()
        self.assertEqual(_config_text(hostile), "")
        service = self.make_service()
        service.config.update({
            "mpd_data_dir": hostile,
            "library_paths": [hostile],
            "library_path": hostile,
            "mpd_mixer_type": hostile,
            "mpd_mixer_control": hostile,
        })
        self.assertEqual(service._data_root(), os.path.join(service.app_root, "share", "mpd"))
        self.assertEqual(service._library_paths(), ["/"])
        self.assertEqual(service.mixer_policy({}, {"available": True, "controls": ["Master"]})["mode"], "none")
        source = (os.path.join(os.path.dirname(__file__), "..", "app", "server", "services", "mpd_service.py"))
        with open(source, encoding="utf-8") as handle:
            self.assertNotIn("str(self.config.get", handle.read())

    def test_mpd_service_numeric_inputs_reject_nonfinite_values(self):
        from services.mpd_service import _safe_float

        self.assertEqual(_safe_float(float("nan")), 0.0)
        self.assertEqual(_safe_float(float("inf")), 0.0)
        self.assertEqual(_safe_float(True), 0.0)
        self.assertEqual(_safe_float("12.5"), 12.5)
        self.assertEqual(_safe_float("x"), 0.0)

    def test_mpd_service_config_integers_reject_object_coercion_and_use_config_bounds(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("configuration object was coerced")

        hostile = Explosive()
        self.assertEqual(_config_int(hostile, 2, 1, 5), 2)
        self.assertEqual(_config_int(True, 2, 1, 5), 2)
        self.assertEqual(_config_int("99", 2, 1, 5), 5)
        with mock.patch.object(MpdService, "_select_port", return_value=56660), \
             mock.patch.object(MpdService, "_find_binary", return_value="/usr/bin/mpd"), \
             mock.patch.object(MpdService, "_data_root", return_value=tempfile.gettempdir()):
            service = MpdService({
                "mpd_port": hostile,
                "mpd_device_presence_samples": hostile,
                "mpd_nice": hostile,
            })
        self.addCleanup(service.supervisor.shutdown)
        self.assertEqual(service.port, 56660)
        self.assertEqual(service._device_presence_threshold, 2)
        self.assertEqual(_config_int(service.config["mpd_nice"], 0, -5, 10), 0)

    def make_service(self, persist=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        config_path = temp.name + "/config.json" if persist else None
        with mock.patch.object(MpdService, "_select_port", return_value=56660), mock.patch.object(
            MpdService, "_find_binary", return_value="/usr/bin/mpd"
        ), mock.patch.object(MpdService, "_data_root", return_value=temp.name):
            service = MpdService(
                {"mpd_port": 56660, "library_path": "/music"},
                app_root=temp.name,
                app_config_path=config_path,
            )
        # The supervisor starts its monitor thread in its constructor, and only `stop()` or
        # `shutdown()` drains it.  R88's suite audit found a monitor still alive a second
        # after the test that built it, which is what cross-test interference is made of.
        self.addCleanup(service.supervisor.shutdown)
        return service

    def test_pid_probe_reads_cmdline_with_a_bound(self):
        service = self.make_service()

        class Handle:
            def __init__(self):
                self.size = None

            def read(self, size=-1):
                self.size = size
                return b"mpd" + (b"x" * (MAX_MPD_PROC_CMDLINE_BYTES + 100))

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        handle = Handle()
        with mock.patch("services.mpd_service.open", return_value=handle):
            self.assertFalse(service._pid_matches_mpd(123))
        self.assertEqual(handle.size, MAX_MPD_PROC_CMDLINE_BYTES + 1)

    def test_output_capability_refresh_start_failure_releases_refresh_latch(self):
        service = self.make_service()
        service._output_caps_cache = {"devices": [{"id": "cached"}]}
        service._output_caps_cache_at = 0
        with mock.patch.object(threading, "Thread", side_effect=RuntimeError("no threads")):
            result = service.output_capabilities()
        self.assertEqual(result, {"devices": [{"id": "cached"}]})
        self.assertEqual(service._output_caps_builders, 0)
        self.assertTrue(service._output_caps_idle.is_set())

    def test_cold_output_capability_scan_is_shared_by_concurrent_callers(self):
        service = self.make_service()
        builds = []
        building = threading.Event()
        release = threading.Event()

        def slow_build():
            builds.append(1)
            building.set()
            self.assertTrue(release.wait(timeout=5))
            return {"devices": [{"id": "hw:1,0"}], "dsd_native": True}

        service._build_output_capabilities = slow_build
        results = {}

        def call(index):
            results[index] = service.output_capabilities()

        first = threading.Thread(target=call, args=(0,))
        first.start()
        self.assertTrue(building.wait(timeout=5))
        second = threading.Thread(target=call, args=(1,))
        second.start()
        release.set()
        first.join(timeout=10)
        second.join(timeout=10)

        self.assertEqual(builds, [1], "a cold scan must run exactly once")
        self.assertEqual(results[0], {"devices": [{"id": "hw:1,0"}], "dsd_native": True})
        self.assertEqual(results[1], results[0])
        self.assertEqual(service._output_caps_builders, 0)
        self.assertTrue(service._output_caps_idle.is_set())

    def test_cold_caller_reuses_the_result_of_an_inflight_scan(self):
        service = self.make_service()
        builds = []
        # Another thread already owns the single scan slot.
        service._begin_output_caps_build_locked()

        def build():
            builds.append(1)
            return {"devices": [{"id": "late"}]}

        service._build_output_capabilities = build

        def publisher():
            time.sleep(0.05)
            service._publish_output_capabilities({"devices": [{"id": "shared"}]})
            with service._output_caps_lock:
                service._end_output_caps_build_locked()

        worker = threading.Thread(target=publisher)
        worker.start()
        result = service.output_capabilities()
        worker.join(timeout=5)

        self.assertEqual(result, {"devices": [{"id": "shared"}]})
        self.assertEqual(builds, [], "the waiting caller must not scan ALSA again")
        self.assertEqual(service._output_caps_builders, 0)

    def test_wedged_cold_capability_scan_builds_locally_instead_of_serving_empty(self):
        service = self.make_service()
        # A slot owner that never publishes must not be able to block playback.
        service._begin_output_caps_build_locked()
        builds = []
        service._build_output_capabilities = lambda: (builds.append(1), {"devices": [{"id": "hw:0,0"}]})[1]

        with mock.patch("services.mpd_service.MAX_OUTPUT_CAPS_COLD_SHARE_SECONDS", 0.05):
            result = service.output_capabilities()

        self.assertEqual(builds, [1])
        self.assertEqual(result, {"devices": [{"id": "hw:0,0"}]})
        # The stuck owner keeps its own slot; this caller must not release it.
        self.assertEqual(service._output_caps_builders, 1)


    def test_explicit_stop_disables_dac_monitor_and_service_restart_on_hotplug(self):
        service = self.make_service()
        service._device_monitor_thread = mock.Mock()
        service._device_monitor_thread.is_alive.return_value = True
        service._idle_thread = mock.Mock()
        service._idle_thread.is_alive.return_value = False
        service.supervisor.stop = mock.Mock(return_value={"ok": True, "running": False})
        service._cleanup_stale_instances = mock.Mock()

        with mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.release"):
            service.stop()

        self.assertTrue(service._service_stop.is_set())
        self.assertTrue(service._device_monitor_stop.is_set())
        service._selected_device_missing = True
        service.config["mpd_output_stable_id"] = "usb:stable"
        service._device_monitor_stop.clear()
        service._find_output_device = mock.Mock(return_value={"alsa_id": "hw:1"})
        service.start = mock.Mock()
        with mock.patch.object(service._device_monitor_stop, "wait", side_effect=[False, True]):
            service._device_monitor_loop()
        service.start.assert_not_called()

    def test_hotplug_restart_checks_stop_flag_atomically_with_start(self):
        service = self.make_service()
        service._selected_device_missing = True
        service.config["mpd_output_stable_id"] = "usb:stable"
        service._find_output_device = mock.Mock(return_value={"alsa_id": "hw:1"})
        service._device_presence = {"missing": True, "missing_samples": 2, "present_samples": 0}
        service._device_presence_threshold = 1
        service._start_locked = mock.Mock(return_value={"running": True})
        service._schedule_playback_recovery = mock.Mock()
        service._service_stop.set()
        service._device_monitor_stop.clear()
        with mock.patch.object(service._device_monitor_stop, "wait", side_effect=[False, True]):
            service._device_monitor_loop()
        service._start_locked.assert_not_called()
        service._schedule_playback_recovery.assert_not_called()

    def test_idle_listener_does_not_reuse_a_thread_that_is_still_stopping(self):
        service = self.make_service()
        old_thread = mock.Mock()
        old_thread.is_alive.return_value = True
        service._idle_thread = old_thread
        service._idle_stop.set()

        with self.assertRaisesRegex(RuntimeError, "still stopping"):
            service._start_idle_listener()

        old_thread.join.assert_called_once_with(timeout=1.0)

    def test_device_monitor_does_not_reuse_a_thread_that_is_still_stopping(self):
        service = self.make_service()
        old_thread = mock.Mock()
        old_thread.is_alive.return_value = True
        service._device_monitor_thread = old_thread
        service._device_monitor_stop.set()

        with self.assertRaisesRegex(RuntimeError, "still stopping"):
            service._start_device_monitor()

        old_thread.join.assert_called_once_with(timeout=1.0)

    def test_device_monitor_survives_a_failing_tick(self):
        service = self.make_service()
        ticks = [False, True]

        class FakeStop:
            def wait(self, _timeout):
                return ticks.pop(0)

            def is_set(self):
                return False

        service._device_monitor_stop = FakeStop()
        with mock.patch.object(
            service, "_watch_for_playback_errors", side_effect=RuntimeError("amixer exploded")
        ) as watcher:
            service._device_monitor_loop()

        self.assertEqual(watcher.call_count, 1)
        self.assertEqual(ticks, [], "the loop should have reached the next tick")
        self.assertEqual(service.fault_status()["last_error"], "amixer exploded")


    @staticmethod
    def _dac(stable, runtime, name):
        return {
            "id": "dac:" + stable,
            "stable_id": stable,
            "alsa_id": runtime,
            "stable_alsa_id": "hw:CARD=%s,DEV=0" % stable,
            "name": name,
            "is_usb": True,
        }

    @mock.patch("services.mpd_service.probe_alsa_hw_params")
    @mock.patch("services.mpd_service.alsa_devices")
    def test_rejected_output_selection_is_not_persisted_by_a_concurrent_poll(self, devices, probe):
        original = self._dac("usb:1:1:orig:dev0", "hw:0,0", "Built-in")
        rejected = self._dac("usb:1:2:bad:dev0", "hw:9,0", "Flaky DAC")
        devices.return_value = [original, rejected]
        service = self.make_service(persist=True)
        service.config.update({
            "mpd_output_alsa_id": original["alsa_id"],
            "mpd_output_stable_id": original["stable_id"],
        })
        service._persist_app_config()
        during = []

        def unavailable(*_args, **_kwargs):
            # A replug renumbers the card mid-switch, so a status poll that
            # resolves the selection now wants to persist a correction for the
            # device that is still being verified.
            service.config["mpd_output_alsa_id"] = "hw:3,0"
            service._selected_alsa_output()
            with open(service.app_config_path, "r", encoding="utf-8") as handle:
                during.append(handle.read())
            return {"available": False, "verified": False}

        probe.side_effect = unavailable
        service.supervisor.status = mock.Mock(return_value={"running": False})
        service.ensure_config = mock.Mock(return_value={"ok": True, "running": False})

        result = service.select_output(rejected["stable_id"])

        self.assertFalse(result["ok"])
        self.assertEqual(len(during), 1, "the poll should have run mid-switch")
        self.assertNotIn(
            rejected["stable_id"], during[0], "a mid-switch poll must not persist an unverified device"
        )
        self.assertEqual(service.config["mpd_output_stable_id"], original["stable_id"])
        with open(service.app_config_path, "r", encoding="utf-8") as handle:
            persisted = handle.read()
        self.assertIn(original["stable_id"], persisted)
        self.assertNotIn(rejected["stable_id"], persisted)

    @mock.patch("services.mpd_service._write_test_wav")
    @mock.patch("services.mpd_service.mpd_load_uri")
    @mock.patch("services.mpd_service.alsa_devices")
    def test_output_test_restores_the_selection_it_temporarily_replaced(
        self, devices, load_uri, write_wav
    ):
        original = self._dac("usb:1:1:orig:dev0", "hw:0,0", "Built-in")
        tested = self._dac("usb:1:2:test:dev0", "hw:9,0", "Test DAC")
        devices.return_value = [original, tested]
        service = self.make_service(persist=True)
        service.config.update({
            "mpd_output_alsa_id": original["alsa_id"],
            "mpd_output_stable_id": original["stable_id"],
        })
        service._persist_app_config()
        service._library_paths = mock.Mock(return_value=[service.data_root])
        load_uri.return_value = {"ok": True}
        service.supervisor.status = mock.Mock(return_value={"running": True})
        service.start = mock.Mock(return_value={"ok": True, "running": True})
        service.stop = mock.Mock(return_value={"ok": True, "running": False})
        service._mixer_for_device = mock.Mock(return_value={"available": False, "controls": []})
        samples = []

        def restart_back_to_real_output():
            # MPD rewrites its config on restart, which resolves the selection
            # through the same read path a status poll uses.
            samples.append(str(service.config.get("mpd_output_stable_id")))
            service._selected_alsa_output()
            return {"ok": True, "running": True}

        service.restart = mock.Mock(side_effect=restart_back_to_real_output)
        with mock.patch("services.mpd_service.time.sleep"):
            result = service.test_output(tested["stable_id"])

        self.assertTrue(result["ok"], result.get("message"))
        self.assertEqual(samples, [original["stable_id"]], "restore the whole selection before the restore restart")
        self.assertEqual(service.config["mpd_output_alsa_id"], original["alsa_id"])
        self.assertEqual(service.config["mpd_output_stable_id"], original["stable_id"])
        self.assertEqual(service.restart.call_count, 1, "one restore is enough")
        with open(service.app_config_path, "r", encoding="utf-8") as handle:
            persisted = handle.read()
        self.assertIn(original["stable_id"], persisted)
        self.assertNotIn(tested["stable_id"], persisted)

    def test_output_selection_persistence_waits_for_the_change_window(self):
        transitional = {
            "mpd_output_alsa_id": "hw:9,0",
            "mpd_output_stable_id": "usb:1:2:test:dev0",
        }
        service = self.make_service(persist=True)
        service.config.update({
            "mpd_output_alsa_id": "hw:0,0",
            "mpd_output_stable_id": "usb:1:1:orig:dev0",
        })
        service._persist_app_config()

        def on_disk():
            with open(service.app_config_path, "r", encoding="utf-8") as handle:
                return handle.read()

        service.config.update(transitional)
        with service._exclusive_output_selection():
            service._persist_output_selection()
            self.assertNotIn(transitional["mpd_output_stable_id"], on_disk())
            with service._exclusive_output_selection():
                pass
            # The nested window is the caller's own rollback restart; leaving it
            # must not hand persistence back before the outer change is done.
            service._persist_output_selection()
            self.assertNotIn(transitional["mpd_output_stable_id"], on_disk())

        service._persist_output_selection()
        self.assertIn(transitional["mpd_output_stable_id"], on_disk())



    def test_start_rolls_back_mpd_when_companion_worker_cannot_start(self):
        service = self.make_service()
        setup = {
            "ok": True,
            "output_device": {},
            "config_changed": False,
            "dac_profile": {},
        }
        service.supervisor.status = mock.Mock(return_value={"running": False})
        service.supervisor.start = mock.Mock(return_value={"ok": True, "running": True, "pid": 123})
        service._cleanup_stale_instances = mock.Mock()
        with mock.patch.object(service, "ensure_config", return_value=setup), \
             mock.patch.object(service, "_wait_ready", return_value={"running": True}), \
             mock.patch.object(service, "_start_idle_listener", side_effect=RuntimeError("no threads")), \
             mock.patch.object(service, "shutdown") as shutdown, \
             mock.patch.object(MpdService, "_release_audio_output"):
            with mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.acquire", return_value={"ok": True}), \
                 mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.release") as release:
                with self.assertRaises(RuntimeError):
                    service.start()
        shutdown.assert_called_once_with()
        release.assert_not_called()

    def test_start_releases_audio_lease_when_supervisor_registration_fails(self):
        service = self.make_service()
        setup = {"ok": True, "output_device": {}, "config_changed": False, "dac_profile": {}}
        service.supervisor.register = mock.Mock(side_effect=RuntimeError("monitor unavailable"))
        service.supervisor.stop = mock.Mock(return_value={"ok": False, "running": False})
        with mock.patch.object(service, "ensure_config", return_value=setup), \
             mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.acquire", return_value={"ok": True}), \
             mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.release") as release:
            with self.assertRaisesRegex(RuntimeError, "monitor unavailable"):
                service.start()
        service.supervisor.stop.assert_called_once_with("mpd")
        release.assert_called_once_with("mpd")

    def test_restart_releases_audio_lease_when_supervisor_registration_fails(self):
        service = self.make_service()
        setup = {"ok": True, "output_device": {}, "config_changed": False, "dac_profile": {}}
        service.supervisor.register = mock.Mock(side_effect=RuntimeError("monitor unavailable"))
        service.supervisor.stop = mock.Mock(return_value={"ok": False, "running": False})
        with mock.patch.object(service, "ensure_config", return_value=setup), \
             mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.acquire", return_value={"ok": True}), \
             mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.release") as release:
            with self.assertRaisesRegex(RuntimeError, "monitor unavailable"):
                service.restart()
        service.supervisor.stop.assert_called_once_with("mpd")
        release.assert_called_once_with("mpd")

    def test_start_tolerates_malformed_supervisor_nice_status(self):
        service = self.make_service()
        setup = {
            "ok": True,
            "output_device": {},
            "config_changed": False,
            "dac_profile": {},
        }
        service.supervisor.status = mock.Mock(return_value={"running": False, "nice": object()})
        service.supervisor.start = mock.Mock(return_value={"ok": True, "running": True, "pid": 123})
        with mock.patch.object(service, "ensure_config", return_value=setup), \
             mock.patch.object(service, "_wait_ready", return_value={"running": True}), \
             mock.patch.object(service, "_start_idle_listener"), \
             mock.patch.object(service, "_start_device_monitor"), \
             mock.patch.object(service, "refresh_status"), \
             mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.acquire", return_value={"ok": True}), \
             mock.patch("services.mpd_service.AUDIO_OUTPUT_LEASE.release"):
            result = service.start()
        self.assertTrue(result["running"])

    def test_public_lifecycle_start_is_serialized(self):
        service = self.make_service()
        entered = threading.Event()
        release = threading.Event()
        barrier = threading.Barrier(3)
        active = []
        peak = []
        active_lock = threading.Lock()

        def delayed_start():
            with active_lock:
                active.append(1)
                peak.append(len(active))
            entered.set()
            release.wait(1)
            with active_lock:
                active.pop()
            return {"ok": True, "running": True}

        def start_service():
            barrier.wait()
            service.start()

        with mock.patch.object(service, "_start_locked", side_effect=delayed_start):
            first = threading.Thread(target=start_service)
            second = threading.Thread(target=start_service)
            first.start()
            second.start()
            barrier.wait()
            self.assertTrue(entered.wait(1))
            time.sleep(0.03)
            self.assertEqual(max(peak), 1)
            release.set()
            first.join(1)
            second.join(1)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())

    @mock.patch("services.mpd_service.alsa_devices", return_value=[])
    def test_mpd_output_allows_software_resampling_for_pcm(self, _devices):
        service = self.make_service()
        result = service.ensure_config()
        self.assertTrue(result["ok"], result)
        with open(service.config_path, "r", encoding="utf-8") as fh:
            config_text = fh.read()
        self.assertIn('auto_resample "yes"', config_text)
        self.assertIn('auto_format "no"', config_text)
        self.assertIn('auto_channels "no"', config_text)

    @mock.patch.object(MpdService, "_selected_alsa_output")
    @mock.patch.object(MpdService, "_mixer_for_device")
    def test_unavailable_hardware_mixer_falls_back_to_fixed_bitperfect_output(self, mixer, selected):
        service = self.make_service()
        service.config["mpd_mixer_type"] = "hardware"
        selected.return_value = {"alsa_id": "hw:2,0", "stable_alsa_id": "hw:CARD=DAC,DEV=0", "name": "DAC"}
        mixer.return_value = {"available": False, "controls": [], "message": "no playback volume"}

        result = service.ensure_config()

        self.assertEqual(result["mixer_type"], "none")
        self.assertTrue(result["mixer"]["fallback"])
        with open(service.config_path, "r", encoding="utf-8") as fh:
            config_text = fh.read()
        self.assertIn('mixer_type "none"', config_text)
        self.assertNotIn("mixer_control", config_text)

    @mock.patch.object(MpdService, "_selected_alsa_output")
    @mock.patch.object(MpdService, "_mixer_for_device")
    def test_hardware_mixer_uses_selected_playback_control_and_card(self, mixer, selected):
        service = self.make_service()
        service.config.update({"mpd_mixer_type": "hardware", "mpd_mixer_control": "Master"})
        selected.return_value = {"alsa_id": "hw:2,0", "stable_alsa_id": "hw:CARD=DAC,DEV=0", "name": "DAC"}
        mixer.return_value = {"available": True, "controls": ["PCM", "Master"], "message": ""}

        result = service.ensure_config()

        self.assertEqual(result["mixer_type"], "hardware")
        self.assertEqual(result["mixer"]["control"], "Master")
        with open(service.config_path, "r", encoding="utf-8") as fh:
            config_text = fh.read()
        self.assertIn('mixer_device "hw:CARD=DAC"', config_text)
        self.assertIn('mixer_control "Master"', config_text)

    @mock.patch("services.mpd_service.subprocess.check_output")
    @mock.patch("services.mpd_service.shutil.which", return_value="/usr/bin/amixer")
    def test_mixer_probe_ignores_switch_only_controls(self, _which, check_output):
        service = self.make_service()
        check_output.return_value = (
            "Simple mixer control 'IEC958',0\n"
            "  Capabilities: pswitch pswitch-joined\n"
            "  Mono: Playback [on]\n"
            "Simple mixer control 'PCM',0\n"
            "  Capabilities: pvolume\n"
            "  Front Left: Playback 200 [78%]\n"
        ).encode("utf-8")

        result = service._mixer_for_device({"alsa_id": "hw:2,0"})

        self.assertTrue(result["available"])
        self.assertEqual(result["controls"], ["PCM"])
        self.assertEqual(result["preferred_control"], "PCM")

    @mock.patch("services.mpd_service.probe_alsa_hw_params")
    @mock.patch.object(MpdService, "_selected_alsa_output")
    def test_unsupported_pcm_rate_is_delegated_to_mpd_resampler(self, selected, probe):
        service = self.make_service()
        selected.return_value = {
            "alsa_id": "hw:CARD=DAC,DEV=0",
            "caps": {"pcm_rates": [44100, 352800]},
        }
        probe.return_value = {
            "verified": True,
            "pcm_rates": [44100, 352800],
            "native_dsd": True,
        }
        result = service.prepare_track_output({"sample_rate": 384000, "is_dsd": False})
        self.assertTrue(result["ok"])
        self.assertTrue(result["resample_required"])
        self.assertEqual(result["source_rate"], 384000)
        self.assertEqual(result["supported_rates"], [44100, 352800])

        probe.assert_not_called()

    @mock.patch("services.mpd_service.probe_alsa_hw_params")
    @mock.patch.object(MpdService, "stop")
    @mock.patch.object(MpdService, "_selected_alsa_output")
    def test_busy_probe_does_not_stop_active_mpd(self, selected, stop, probe):
        service = self.make_service()
        selected.return_value = {"alsa_id": "hw:CARD=DAC,DEV=0", "caps": {"pcm_rates": [44100, 192000]}}
        probe.return_value = {"busy": True, "verified": False, "pcm_rates": []}
        result = service.prepare_track_output({"sample_rate": 192000, "is_dsd": False})
        self.assertTrue(result["ok"])
        self.assertTrue(result["probe_deferred"])
        stop.assert_not_called()

    @mock.patch("services.mpd_service.alsa_devices")
    def test_preferred_output_persists_stable_identity(self, devices):
        device = {
            "id": "dac:usb:1:2:serial:dev0",
            "stable_id": "usb:1:2:serial:dev0",
            "alsa_id": "hw:4,0",
            "stable_alsa_id": "hw:CARD=DAC,DEV=0",
            "name": "USB DAC",
            "is_usb": True,
        }
        devices.return_value = [device]
        service = self.make_service(persist=True)

        selected = service._selected_alsa_output()

        self.assertEqual(selected["stable_id"], device["stable_id"])
        self.assertEqual(service.config["mpd_output_stable_id"], device["stable_id"])
        with open(service.app_config_path, "r", encoding="utf-8") as fh:
            persisted = fh.read()
        self.assertIn(device["stable_id"], persisted)

    @mock.patch("services.mpd_service.mpd_play_queue_item")
    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_same_queue_switches_with_playid_without_replacing_queue(self, replace_queue, play_item):
        service = self.make_service()
        queue = [
            TrackRef.from_mapping({"id": "a", "path": "/music/a.flac"}),
            TrackRef.from_mapping({"id": "b", "path": "/music/b.flac"}),
        ]
        replace_queue.return_value = {"ok": True, "song_ids": {"a": "11", "b": "12"}}
        play_item.return_value = {"ok": True, "song_id": "12"}

        first = service.sync_playback_queue(queue, "a")
        second = service.sync_playback_queue(queue, "b")

        self.assertFalse(first["queue_reused"])
        self.assertTrue(second["queue_reused"])
        replace_queue.assert_called_once()
        play_item.assert_called_once_with(
            "12", start=0.0, repeat="off", shuffle=False, host=service.host, port=service.port
        )

    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_stopped_queue_sync_replaces_without_starting_audio(self, replace_queue):
        service = self.make_service()
        queue = [TrackRef.from_mapping({"id": "a", "path": "/music/a.flac"})]
        replace_queue.return_value = {"ok": True, "song_ids": {"a": "17"}}

        result = service.sync_playback_queue(queue, "a", play=False)

        self.assertEqual(result["queue_reused"], False)
        replace_queue.assert_called_once_with(
            mock.ANY,
            current_track_id="a",
            start=0.0,
            repeat="off",
            shuffle=False,
            play=False,
            host=service.host,
            port=service.port,
        )

    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_queue_sync_stops_reading_an_oversized_generator_at_the_budget(self, replace_queue):
        service = self.make_service()
        seen = []

        def tracks():
            for index in range(MAX_MPD_QUEUE_ENTRIES + 1):
                seen.append(index)
                yield TrackRef.from_mapping({"id": "track-%d" % index, "path": "/music/%d.flac" % index})

        replace_queue.return_value = {"ok": True, "song_ids": {"track-0": "1"}}
        result = service.sync_playback_queue(tracks(), "track-0", play=False)

        self.assertEqual(len(seen), MAX_MPD_QUEUE_ENTRIES)
        self.assertEqual(result["queue_count"], MAX_MPD_QUEUE_ENTRIES)
        self.assertEqual(len(replace_queue.call_args.args[0]), MAX_MPD_QUEUE_ENTRIES)

    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_cue_tracks_use_single_item_queue(self, replace_queue):
        service = self.make_service()
        queue = [
            TrackRef.from_mapping({"id": "cue-1", "path": "/music/album.flac", "cue_track": 1}),
            TrackRef.from_mapping({"id": "cue-2", "path": "/music/album.flac", "cue_track": 2}),
        ]
        replace_queue.return_value = {"ok": True, "song_ids": {"cue-2": "3"}}

        result = service.sync_playback_queue(queue, "cue-2", current_item=queue[1].item, start=30.0)

        entries = replace_queue.call_args.args[0]
        self.assertEqual([entry["track_id"] for entry in entries], ["cue-2"])
        self.assertTrue(result["cue_single_mode"])

    @mock.patch("services.mpd_service.transcode_to_audio")
    @mock.patch("services.mpd_service.mpd_update_and_wait")
    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_ape_queue_entry_is_decoded_to_lossless_flac_before_mpd(self, replace_queue, update, transcode_audio):
        service = self.make_service()
        queue = [TrackRef.from_mapping({"id": "ape", "path": "/music/source.ape", "mime": "audio/ape"})]
        # Real MPD transcodes land inside the music root (see the cache_dir
        # assertion below), which is what makes a folder-scoped update possible.
        transcode_audio.return_value = ("/music/fnaudio-transcode/ape.ape-source.flac", "audio/flac")
        replace_queue.return_value = {"ok": True, "song_ids": {"ape": "5"}}

        service.sync_playback_queue(queue, "ape")

        transcode_audio.assert_called_once_with(
            queue[0].item, {**service.config, "cache_dir": "/music/fnaudio-transcode"}, "ape_flac"
        )
        self.assertTrue(replace_queue.call_args.args[0][0]["uri"].endswith("ape.ape-source.flac"))
        # A folder-scoped update is a silent no-op for a folder MPD has never
        # mounted, so the refresh has to be settled by the generated uri it is
        # about to hand to ``addid``.
        update.assert_called_once_with(
            host=service.host, port=service.port, path="fnaudio-transcode",
            verify_uri="fnaudio-transcode/ape.ape-source.flac",
        )

    @mock.patch("services.mpd_service.transcode_to_audio")
    @mock.patch("services.mpd_service.mpd_update_and_wait")
    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_cue_ape_uses_lossless_segment_and_starts_it_at_zero(self, replace_queue, update, transcode_audio):
        service = self.make_service()
        track = TrackRef.from_mapping({
            "id": "cue-ape", "path": "/music/album.ape", "mime": "audio/ape",
            "cue_track": True, "cue_start": 120.0, "duration": 240.0,
        })
        transcode_audio.return_value = ("/cache/cue-ape.cue-segment.flac", "audio/flac")
        replace_queue.return_value = {"ok": True, "song_ids": {"cue-ape": "6"}}

        result = service.sync_playback_queue([track], "cue-ape", current_item=track.item, start=120.0)

        transcode_audio.assert_called_once_with(
            track.item, {**service.config, "cache_dir": "/music/fnaudio-transcode"}, "cue_flac"
        )
        self.assertEqual(replace_queue.call_args.kwargs["start"], 0.0)
        self.assertTrue(replace_queue.call_args.args[0][0]["uri"].endswith("cue-ape.cue-segment.flac"))
        self.assertTrue(result["cue_transcoded"])

    def test_mpd_ape_cache_is_placed_inside_its_music_root(self):
        service = self.make_service()

        config = service._mpd_transcode_config("/music/album/source.ape")

        self.assertEqual(config["cache_dir"], "/music/fnaudio-transcode")

    def test_music_alias_directory_rejects_symlink_replacement(self):
        service = self.make_service()
        service.music_root = os.path.join(tempfile.gettempdir(), "fnaudio-mpd-music-link-test")
        outside = tempfile.mkdtemp()
        self.addCleanup(lambda: os.path.exists(outside) and __import__("shutil").rmtree(outside, ignore_errors=True))
        try:
            os.symlink(outside, service.music_root, target_is_directory=True)
        except OSError as exc:
            self.skipTest("symlinks are unavailable: %s" % exc)
        self.addCleanup(lambda: os.path.lexists(service.music_root) and os.unlink(service.music_root))
        with self.assertRaisesRegex(OSError, "alias directory"):
            service._prepare_music_directory(["/music", "/other"])

    def test_music_alias_cleanup_ignores_unmanaged_symlink(self):
        service = self.make_service()
        os.makedirs(service.music_root, exist_ok=True)
        outside = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(outside, ignore_errors=True))
        unmanaged = os.path.join(service.music_root, "user-link")
        try:
            os.symlink(outside, unmanaged, target_is_directory=True)
        except OSError as exc:
            self.skipTest("symlinks are unavailable: %s" % exc)
        service._prepare_music_directory(["/music", "/other"])
        self.assertTrue(os.path.islink(unmanaged))

    def test_backend_song_id_maps_back_to_logical_track(self):
        service = self.make_service()
        service._queue_song_tracks = {"21": "track-b"}
        probe = {"status": {"song": {"Id": "21"}}}

        self.assertEqual(service.track_id_for_status(probe), "track-b")

    def test_status_poll_updates_restart_position_checkpoint(self):
        service = self.make_service()
        service._queue_song_tracks = {"21": "track-b"}
        projected = service._project_cached_probe({
            "cached_at": time.time(),
            "status": {
                "song": {"Id": "21"},
                "transport": {"state": "PLAYING"},
                "position": {"rel_seconds": 12.5, "duration_seconds": 120},
            },
        })

        self.assertEqual(service._queue_current_track_id, "track-b")
        self.assertAlmostEqual(service._last_position, projected["status"]["position"]["rel_seconds"], places=2)

    def test_cached_probe_uses_monotonic_stamp_for_age_and_position(self):
        service = self.make_service()
        probe = {
            "cached_at": time.time() + 86400,
            "cached_monotonic": 100.0,
            "status": {
                "transport": {"state": "PLAYING"},
                "position": {"rel_seconds": 12.5, "duration_seconds": 120},
            },
        }
        with mock.patch("services.mpd_service.time.monotonic", return_value=105.0):
            self.assertEqual(service._probe_age_seconds(probe), 5.0)
            projected = service._project_cached_probe(probe)
        self.assertAlmostEqual(projected["status"]["position"]["rel_seconds"], 17.5, places=2)

    def test_output_capability_cache_uses_monotonic_time(self):
        with open(os.path.join("app", "server", "services", "mpd_service.py"), encoding="utf-8") as handle:
            source = handle.read()
        output_method = source[source.index("def output_capabilities"):source.index("def _refresh_output_capabilities")]
        self.assertIn("now = time.monotonic()", output_method)
        self.assertNotIn("_output_caps_cache_at = time.time()", output_method)

    def test_recovering_process_cannot_erase_restart_checkpoint_with_zero(self):
        service = self.make_service()
        service._last_position = 12.5
        service._queue_current_track_id = "track-b"
        service._mark_recovering()

        service._project_cached_probe({
            "cached_at": time.time(),
            "status": {
                "song": {"Id": "1"},
                "transport": {"state": "PLAYING"},
                "position": {"rel_seconds": 0, "duration_seconds": 120},
            },
        })

        self.assertEqual(service._queue_current_track_id, "track-b")
        self.assertEqual(service._last_position, 12.5)

    @mock.patch("services.mpd_service.mpd_control")
    def test_transport_command_waits_for_restart_queue_recovery(self, control):
        service = self.make_service()
        service._recovery_active.set()
        completed = threading.Event()

        worker = threading.Thread(target=lambda: (service.control("play"), completed.set()))
        worker.start()
        time.sleep(0.08)
        self.assertFalse(completed.is_set())
        control.assert_not_called()

        service._recovery_active.clear()
        worker.join(timeout=1.0)
        self.assertTrue(completed.is_set())
        control.assert_called_once_with("play", None, host=service.host, port=service.port)

    @mock.patch("services.mpd_service.mpd_replace_queue")
    @mock.patch.object(MpdService, "_wait_ready", return_value={"running": True})
    def test_empty_restart_queue_leaves_recovering_state(self, _ready, replace_queue):
        service = self.make_service()
        service._mark_recovering()

        service._recover_playback_after_restart()

        replace_queue.assert_not_called()
        self.assertEqual(service.fault_status()["state"], "STOPPED")
        self.assertFalse(service._recovery_active.is_set())

    @mock.patch("services.mpd_service.mpd_replace_queue")
    @mock.patch.object(MpdService, "_wait_ready", return_value={"running": True})
    def test_shutdown_cancels_recovery_before_rebuilding_queue(self, _ready, replace_queue):
        service = self.make_service()
        service._service_stop.set()
        service._mark_recovering()

        service._recover_playback_after_restart()

        replace_queue.assert_not_called()
        self.assertFalse(service._recovery_active.is_set())

    @mock.patch("services.mpd_service.mpd_replace_queue")
    @mock.patch.object(MpdService, "_wait_ready", return_value={"running": True})
    def test_stale_recovery_generation_cannot_rebuild_a_newer_runtime_queue(self, _ready, replace_queue):
        service = self.make_service()
        service._recovery_generation = 2
        service._recovery_active.set()

        service._recover_playback_after_restart(1)

        replace_queue.assert_not_called()
        self.assertTrue(service._recovery_active.is_set())

    def test_shutdown_joins_tracked_recovery_thread(self):
        service = self.make_service()
        recovery = mock.Mock()
        recovery.is_alive.return_value = True
        service._recovery_thread = recovery
        service.supervisor.shutdown = mock.Mock()
        service._cleanup_stale_instances = mock.Mock()
        service.shutdown()
        recovery.join.assert_called_once()

    def test_recovery_callback_does_not_create_duplicate_live_thread(self):
        service = self.make_service()
        existing = mock.Mock()
        existing.is_alive.return_value = True
        service._recovery_thread = existing
        with mock.patch.object(threading, "Thread") as thread_class:
            service._schedule_playback_recovery("mpd", {})
        thread_class.assert_not_called()

    def test_concurrent_recovery_callbacks_register_only_one_thread(self):
        service = self.make_service()
        created = []
        start = threading.Barrier(3)
        real_thread = threading.Thread

        class RecoveryThread:
            def __init__(self, *args, **kwargs):
                created.append(self)
                # The old split check/create path lets both callers reach here.
                time.sleep(0.03)
                self.started = False

            def start(self):
                self.started = True

            def is_alive(self):
                return self.started

        def schedule():
            start.wait()
            service._schedule_playback_recovery("mpd", {})

        with mock.patch("services.mpd_service.threading.Thread", RecoveryThread):
            first = real_thread(target=schedule)
            second = real_thread(target=schedule)
            first.start()
            second.start()
            start.wait()
            first.join(1)
            second.join(1)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(len(created), 1)
        self.assertIs(service._recovery_thread, created[0])
        service._recovery_active.clear()

    def test_recovery_start_failure_clears_recovery_state(self):
        service = self.make_service()
        with mock.patch("services.mpd_service.threading.Thread", side_effect=RuntimeError("no threads")):
            with self.assertRaises(RuntimeError):
                service._schedule_playback_recovery("mpd", {})
        self.assertIsNone(service._recovery_thread)
        self.assertFalse(service._recovery_active.is_set())

    @mock.patch("services.mpd_service.probe_alsa_hw_params")
    @mock.patch("services.mpd_service.alsa_devices")
    def test_dsd_is_rejected_instead_of_silently_converting_to_pcm(self, devices, probe):
        service = self.make_service()
        device = {
            "id": "dac:usb:1:2:x:dev0",
            "stable_id": "usb:1:2:x:dev0",
            "alsa_id": "hw:2,0",
            "stable_alsa_id": "hw:CARD=DAC,DEV=0",
            "caps": {"pcm_rates": [192000], "dsd_rates": []},
        }
        devices.return_value = [device]
        service.config["mpd_output_stable_id"] = device["stable_id"]
        probe.return_value = {"verified": True, "native_dsd": False, "pcm_rates": [192000]}

        result = service.prepare_track_output({"is_dsd": True})

        self.assertFalse(result["ok"])
        self.assertIn("PCM", result["message"])

    @mock.patch("services.mpd_service.probe_alsa_hw_params")
    @mock.patch("services.mpd_service.alsa_devices")
    def test_native_dsd_is_preferred_over_dop(self, devices, probe):
        service = self.make_service()
        device = {
            "stable_id": "usb:1:2:x:dev0",
            "alsa_id": "hw:2,0",
            "stable_alsa_id": "hw:CARD=DAC,DEV=0",
            "caps": {"pcm_rates": [176400], "dsd_rates": ["DoP"]},
        }
        devices.return_value = [device]
        service.config.update({"mpd_output_stable_id": device["stable_id"], "mpd_dop": True})
        probe.return_value = {"verified": True, "native_dsd": True, "pcm_rates": [176400]}

        result = service.prepare_track_output({"is_dsd": True})

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "native")
        self.assertFalse(service.config["mpd_dop"])

    @mock.patch("services.mpd_service.probe_alsa_hw_params")
    @mock.patch("services.mpd_service.alsa_devices")
    def test_output_switch_rolls_back_when_new_device_cannot_open(self, devices, probe):
        service = self.make_service()
        original = {
            "stable_id": "usb:old",
            "alsa_id": "hw:1,0",
            "stable_alsa_id": "hw:CARD=OLD,DEV=0",
        }
        replacement = {
            "stable_id": "usb:new",
            "alsa_id": "hw:2,0",
            "stable_alsa_id": "hw:CARD=NEW,DEV=0",
        }
        devices.return_value = [original, replacement]
        service.config.update({"mpd_output_stable_id": "usb:old", "mpd_output_alsa_id": "hw:1,0"})
        probe.return_value = {"available": False, "error": "busy"}

        result = service.select_output("usb:new")

        self.assertFalse(result["ok"])
        self.assertEqual(service.config["mpd_output_stable_id"], "usb:old")
        self.assertEqual(service.config["mpd_output_alsa_id"], "hw:1,0")

    def test_output_selection_rejects_untrusted_identifier_without_stringifying(self):
        service = self.make_service()

        class ExplodingText:
            def __str__(self):
                raise AssertionError("must not stringify output identifier")

        result = service.select_output(ExplodingText())
        self.assertFalse(result["ok"])
        self.assertEqual(result["alsa_id"], "")

    def test_output_test_rejects_untrusted_identifier_without_device_probe(self):
        service = self.make_service()

        class ExplodingText:
            def __str__(self):
                raise AssertionError("must not stringify output identifier")

        with mock.patch("services.mpd_service.alsa_devices") as devices:
            result = service.test_output(ExplodingText())
        self.assertFalse(result["ok"])
        devices.assert_not_called()

    @mock.patch("services.mpd_service.alsa_devices")
    def test_output_test_uses_unique_temp_file_and_cleans_it_on_failure(self, devices):
        service = self.make_service()
        device = {"stable_id": "usb:test", "alsa_id": "hw:2,0", "stable_alsa_id": "hw:CARD=TEST,DEV=0"}
        devices.return_value = [device]
        service.start = mock.Mock(return_value={"running": True})
        with mock.patch("services.mpd_service.tempfile.mkstemp", return_value=(123, "/music/.fnaudio-output-test-unique.wav")) as mkstemp, \
             mock.patch("services.mpd_service.os.close") as close, \
             mock.patch("services.mpd_service._write_test_wav"), \
             mock.patch("services.mpd_service.mpd_load_uri", side_effect=RuntimeError("load failed")), \
             mock.patch("services.mpd_service.os.unlink") as unlink:
            result = service.test_output("hw:2,0")
        self.assertFalse(result["ok"])
        mkstemp.assert_called_once()
        close.assert_called_once_with(123)
        unlink.assert_called_once_with("/music/.fnaudio-output-test-unique.wav")

    @mock.patch("services.mpd_service.alsa_devices")
    def test_output_test_retries_descriptor_cleanup_when_initial_close_fails(self, devices):
        service = self.make_service()
        device = {"stable_id": "usb:test", "alsa_id": "hw:2,0", "stable_alsa_id": "hw:CARD=TEST,DEV=0"}
        devices.return_value = [device]
        service.start = mock.Mock(return_value={"running": True})
        close_calls = []

        def close_once(value):
            close_calls.append(value)
            if len(close_calls) == 1:
                raise OSError("close failed")

        with mock.patch("services.mpd_service.tempfile.mkstemp", return_value=(123, "/music/.fnaudio-output-test-close.wav")), \
             mock.patch("services.mpd_service.os.close", side_effect=close_once), \
             mock.patch("services.mpd_service._write_test_wav"), \
             mock.patch("services.mpd_service.mpd_load_uri", side_effect=RuntimeError("load failed")), \
             mock.patch("services.mpd_service.os.unlink") as unlink:
            result = service.test_output("hw:2,0")
        self.assertFalse(result["ok"])
        self.assertEqual(close_calls, [123, 123])
        unlink.assert_called_once_with("/music/.fnaudio-output-test-close.wav")

    @mock.patch("services.mpd_service.alsa_devices")
    def test_output_test_restores_a_previously_stopped_mpd(self, devices):
        service = self.make_service()
        device = {"stable_id": "usb:test", "alsa_id": "hw:2,0", "stable_alsa_id": "hw:CARD=TEST,DEV=0"}
        devices.return_value = [device]
        service.supervisor.status = mock.Mock(return_value={"running": False})
        service.start = mock.Mock(return_value={"ok": True, "running": True})
        service.stop = mock.Mock(return_value={"ok": True, "running": False})
        with mock.patch("services.mpd_service.tempfile.mkstemp", return_value=(123, "/music/.fnaudio-output-test-stopped.wav")), \
             mock.patch("services.mpd_service.os.close"), \
             mock.patch("services.mpd_service._write_test_wav"), \
             mock.patch("services.mpd_service.mpd_load_uri", return_value={"ok": True}), \
             mock.patch("services.mpd_service.time.sleep"), \
             mock.patch("services.mpd_service.os.unlink"):
            result = service.test_output("hw:2,0")
        self.assertTrue(result["ok"], result)
        service.start.assert_called_once()
        service.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
