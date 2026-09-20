import sys
import os
import signal
import time
import tempfile
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, "app/server")

from playback.alsa_output import (
    ALSA_CAPS_CACHE,
    ALSA_CAPS_CACHE_LIMIT,
    MAX_DAC_TEXT_BYTES,
    alsa_device_identity,
    choose_dac_strategy,
    dac_public_status,
    empty_dac_caps,
    enrich_dac_device,
    preserve_verified_busy_probe,
    start_dac_playback,
    seconds_to_upnp_time,
    safe_int,
    safe_float,
)
from playback import alsa_output


class AlsaOutputTests(unittest.TestCase):

    def test_playback_elapsed_uses_monotonic_stamp(self):
        with patch("playback.alsa_output.time.monotonic", return_value=105.0):
            self.assertEqual(alsa_output._playing_elapsed({"started_at": 1000.0, "started_monotonic": 100.0}), 5.0)

    def test_capability_cache_is_bounded_and_ignores_corrupt_entries(self):
        original = dict(ALSA_CAPS_CACHE)
        try:
            ALSA_CAPS_CACHE.clear()
            ALSA_CAPS_CACHE["corrupt"] = object()
            for index in range(ALSA_CAPS_CACHE_LIMIT + 2):
                alsa_output._store_alsa_caps("device-%d" % index, {"probed_at": index})
            self.assertLessEqual(len(ALSA_CAPS_CACHE), ALSA_CAPS_CACHE_LIMIT)
            self.assertNotIn("corrupt", ALSA_CAPS_CACHE)
        finally:
            ALSA_CAPS_CACHE.clear()
            ALSA_CAPS_CACHE.update(original)
    def test_safe_float_rejects_non_finite_and_boolean_values(self):
        self.assertEqual(safe_float(float("nan")), 0.0)
        self.assertEqual(safe_float(float("inf"), 2.0), 2.0)
        self.assertEqual(safe_float(True, 2.0), 2.0)

    def test_safe_int_rejects_non_finite_and_boolean_values(self):
        self.assertEqual(safe_int(float("nan"), 2), 2)
        self.assertEqual(safe_int(float("inf"), 2), 2)
        self.assertEqual(safe_int(True, 2), 2)

    def test_upnp_time_rejects_non_finite_values(self):
        self.assertEqual(seconds_to_upnp_time(float("nan")), "00:00:00")
        self.assertEqual(seconds_to_upnp_time(float("inf")), "00:00:00")

    def test_device_uses_driver_reported_pcm_capabilities(self):
        detected = {
            "source": "/proc/asound/card0/stream*",
            "pcm_rates": [44100, 192000, 352800, 384000],
            "pcm_max_rate": 384000,
            "pcm_max_bits": 32,
            "dsd": True,
            "dsd_rates": ["DSD_U32"],
        }
        with patch("playback.alsa_output.parse_dac_stream_caps", return_value=detected):
            device = enrich_dac_device({"name": "Any USB DAC", "alsa_id": "hw:0,0"})
        caps = device["caps"]
        self.assertEqual(caps["pcm_max_rate"], 384000)
        self.assertEqual(caps["pcm_max_bits"], 32)
        self.assertEqual(caps["pcm_rates"], [44100, 192000, 352800, 384000])
        self.assertTrue(caps["dsd"])

    def test_unmeasured_capabilities_invent_no_rate_or_bit_depth(self):
        # Unknown used to arrive as 192000/24. That object is published through
        # the local renderer UPnP GetProtocolInfo and printed as the DAC
        # capability line, so a plausible default here is a claim about hardware
        # that was never read.
        caps = empty_dac_caps()
        self.assertEqual(caps["source"], "unknown")
        self.assertEqual(caps["pcm_rates"], [])
        self.assertEqual(caps["pcm_max_rate"], 0)
        self.assertEqual(caps["pcm_max_bits"], 0)

    def test_driver_text_without_rates_stays_unmeasured(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "card0"))
            with open(os.path.join(root, "card0", "stream0"), "w", encoding="utf-8") as handle:
                handle.write("Playback: #0\n\tFormats: S16_LE S24_LE\n")
            with patch.dict(os.environ, {"FNAUDIO_ASOUND_ROOT": root}):
                device = enrich_dac_device({"name": "Obscure USB DAC", "alsa_id": "hw:0,0"})
        caps = device["caps"]
        self.assertEqual(caps["pcm_rates"], [])
        self.assertEqual(caps["pcm_max_rate"], 0)
        # A stream file was readable, so the source still says where it looked.
        self.assertTrue(caps["source"].endswith("stream*"))
        # The consequence that matters: a 44.1 kHz track is played as it is
        # instead of being resampled to a fabricated 192 kHz, while the
        # conservative ceiling above the guess still applies.
        direct = choose_dac_strategy({"sample_rate": 44100, "bit_depth": 16}, device)
        self.assertEqual(direct["rate"], 44100)
        self.assertFalse(direct["needs_transcode"])
        ceiling = choose_dac_strategy({"sample_rate": 384000, "bit_depth": 32}, device)
        # The ceiling is the conservative one, not 192000. `start_dac_playback()` hands this
        # rate to `aplay -D` with a `hw:` identifier (alsa_output.py:498/:620/:652, applied at
        # :929), and `hw:` carries no resampling plugin: a fabricated 192 kHz ceiling is not a
        # graceful fallback there, it is a device that cannot be opened. Measured rates still
        # win, which is what the next test holds.
        self.assertEqual(ceiling["rate"], 44100)
        self.assertTrue(ceiling["needs_transcode"])

    def test_an_unmeasured_device_gets_the_same_answer_as_an_unknown_one(self):
        # Two shapes mean the same thing - "nothing was read" - and used to be answered
        # differently: a device whose caps say `unknown` was handled conservatively, while one
        # whose stream file existed but listed no parsable rate inherited a literal 192000/24.
        # Measured before the fix: a 176.4 kHz file went out at 176400 against a device that
        # reports nothing, and a 384 kHz file at 192000.
        unmeasured = {
            "name": "Obscure USB DAC",
            "caps": {"source": "/proc/asound/card0/stream*", "pcm_rates": [],
                     "pcm_max_rate": 0, "pcm_max_bits": 0, "dsd": False,
                     "dsd_rates": [], "notes": []},
        }
        unknown = {"name": "Obscure USB DAC", "caps": empty_dac_caps()}
        for item in ({"sample_rate": 44100, "bit_depth": 16},
                     {"sample_rate": 96000, "bit_depth": 24},
                     {"sample_rate": 176400, "bit_depth": 32},
                     {"sample_rate": 384000, "bit_depth": 32}):
            left = choose_dac_strategy(item, unmeasured)
            right = choose_dac_strategy(item, unknown)
            self.assertEqual(
                (left["rate"], left["bits"], left["mode"]), (right["rate"], right["bits"], right["mode"]),
                "unmeasured caps answered differently from unknown caps for %s" % item["sample_rate"])
        # The other half: a device that *did* report rates must not be flattened to 44.1 kHz,
        # or this fix would trade a possible failure for a guaranteed quality loss on every
        # capable DAC whose driver reports widths but no explicit `pcm_max_rate`.
        measured = {
            "name": "Real DAC",
            "caps": {"source": "/proc/asound/card1/stream*", "pcm_rates": [44100, 48000],
                     "pcm_max_rate": 0, "pcm_max_bits": 0, "dsd": False,
                     "dsd_rates": [], "notes": []},
        }
        high = choose_dac_strategy({"sample_rate": 176400, "bit_depth": 24}, measured)
        self.assertEqual(high["rate"], 48000)
        self.assertTrue(high["needs_transcode"])
        self.assertNotEqual(high["rate"], choose_dac_strategy(
            {"sample_rate": 176400, "bit_depth": 24}, unmeasured)["rate"])
        # The shape real hardware actually produces: many drivers print
        # `Rates  : 0x33 (44100 48000 ...)`, which neither rate regex matches, while their
        # `Formats:` line is read and yields a real width (see TODO.md:1831). Conserving the
        # rate must not throw that one measured fact away, or a 24-bit DAC gets 16-bit audio
        # for no reason.
        formats_only = {
            "name": "Formats but no rates",
            "caps": {"source": "/proc/asound/card2/stream*", "pcm_rates": [],
                     "pcm_max_rate": 0, "pcm_max_bits": 24, "dsd": False,
                     "dsd_rates": [], "notes": []},
        }
        strategy = choose_dac_strategy({"sample_rate": 96000, "bit_depth": 24}, formats_only)
        self.assertEqual((strategy["rate"], strategy["bits"]), (44100, 24))
        stated = choose_dac_strategy({"sample_rate": 96000, "bit_depth": 24}, unmeasured)
        self.assertEqual((stated["rate"], stated["bits"]), (44100, 16))
        self.assertNotEqual(stated["bits"], strategy["bits"], "an unmeasured width was guessed")

    def test_unknown_capabilities_use_the_same_conservative_fallback_for_all_names(self):
        item = {"sample_rate": 96000, "bit_depth": 24, "is_dsd": False}
        for name in ("TEAC UD-301", "Generic USB DAC"):
            strategy = choose_dac_strategy(item, {"name": name, "caps": {"source": "unknown"}})
            self.assertEqual(strategy["rate"], 44100)
            self.assertEqual(strategy["bits"], 16)
            self.assertTrue(strategy["needs_transcode"])

    def test_usb_stable_identity_survives_numeric_card_index_change(self):
        with tempfile.TemporaryDirectory() as root:
            proc_root = os.path.join(root, "proc")
            sys_root = os.path.join(root, "sys")
            usb_root = os.path.join(root, "usb-device")
            os.makedirs(usb_root)
            for name, value in {
                "idVendor": "1234",
                "idProduct": "5678",
                "serial": "DAC-SERIAL-1",
                "product": "Reference DAC",
            }.items():
                with open(os.path.join(usb_root, name), "w", encoding="utf-8") as handle:
                    handle.write(value)
            for card in ("0", "3"):
                os.makedirs(os.path.join(proc_root, "card" + card))
                with open(os.path.join(proc_root, "card" + card, "id"), "w", encoding="utf-8") as handle:
                    handle.write("RefDAC")
                os.makedirs(os.path.join(sys_root, "card" + card))
                os.symlink(usb_root, os.path.join(sys_root, "card" + card, "device"), target_is_directory=True)
            with patch.dict(
                os.environ,
                {"FNAUDIO_ASOUND_ROOT": proc_root, "FNAUDIO_SYS_SOUND_ROOT": sys_root},
            ):
                first = alsa_device_identity("0", "0")
                reconnected = alsa_device_identity("3", "0")

        self.assertEqual(first["stable_id"], reconnected["stable_id"])
        self.assertEqual(first["stable_alsa_id"], "hw:CARD=RefDAC,DEV=0")
        self.assertEqual(reconnected["card_index"], 3)

    def test_direct_alsa_dsd_never_falls_back_to_pcm(self):
        device = {
            "id": "dac:usb:test",
            "alsa_id": "hw:2,0",
            "stable_alsa_id": "hw:CARD=DAC,DEV=0",
            "caps": {"source": "driver", "dsd": True},
        }
        item = {"id": "dsd", "path": "/music/test.dsf", "is_dsd": True}
        with patch("playback.alsa_output.dac_device_by_id", return_value=device), patch(
            "playback.alsa_output.subprocess.Popen"
        ) as popen:
            ok, message = start_dac_playback(device["id"], item, {})

        self.assertFalse(ok)
        self.assertIn("MPD", message)
        popen.assert_not_called()

    def test_aplay_start_failure_terminates_already_started_ffmpeg(self):
        device = {
            "id": "dac:usb:test",
            "alsa_id": "hw:2,0",
            "stable_alsa_id": "hw:CARD=DAC,DEV=0",
            "caps": {"source": "driver", "pcm_rates": [44100], "pcm_max_rate": 44100, "pcm_max_bits": 16},
        }
        item = {"id": "pcm", "path": "/music/test.flac", "sample_rate": 44100, "bit_depth": 16, "is_dsd": False}

        class Process:
            def __init__(self):
                self.terminated = False
                self.stdout = Mock()
            def poll(self): return 0 if self.terminated else None
            def terminate(self): self.terminated = True
            def kill(self): self.terminated = True
            def wait(self, **_kwargs): return 0

        ffmpeg = Process()
        with patch("playback.alsa_output.dac_device_by_id", return_value=device), \
             patch("playback.alsa_output.find_aplay", return_value="/usr/bin/aplay"), \
             patch("playback.alsa_output.dac_ffmpeg_pcm_command", return_value=([], {}, {"sample_format": "s16le", "rate": 44100, "channels": 2})), \
             patch("playback.alsa_output.subprocess.Popen", side_effect=[ffmpeg, OSError("aplay failed")]):
            ok, message = start_dac_playback(device["id"], item, {})

        self.assertFalse(ok)
        self.assertIn("aplay failed", message)
        self.assertTrue(ffmpeg.terminated)
        ffmpeg.stdout.close.assert_called_once_with()

    def test_start_publishes_pipeline_atomically_against_concurrent_control(self):
        device = {
            "id": "dac:usb:test",
            "alsa_id": "hw:2,0",
            "stable_alsa_id": "hw:CARD=DAC,DEV=0",
            "caps": {"source": "driver", "pcm_rates": [44100], "pcm_max_rate": 44100, "pcm_max_bits": 16},
        }
        item = {"id": "pcm", "path": "/music/test.flac", "sample_rate": 44100, "bit_depth": 16, "is_dsd": False}

        class Process:
            def __init__(self):
                self.terminated = False
                self.stdout = Mock()
            def poll(self): return 0 if self.terminated else None
            def terminate(self): self.terminated = True
            def kill(self): self.terminated = True
            def wait(self, **_kwargs): return 0

        ffmpeg = Process()
        aplay = Process()
        with patch("playback.alsa_output.dac_device_by_id", return_value=device), \
             patch("playback.alsa_output.find_aplay", return_value="/usr/bin/aplay"), \
             patch("playback.alsa_output.dac_ffmpeg_pcm_command", return_value=([], {}, {"sample_format": "s16le", "rate": 44100, "channels": 2})), \
             patch("playback.alsa_output.subprocess.Popen", side_effect=[ffmpeg, aplay]), \
             patch("playback.alsa_output.process_failure_message", return_value=""):
            previous = dict(alsa_output.DAC_STATE)
            try:
                ok, message = start_dac_playback(device["id"], item, {})
                self.assertTrue(ok, message)
                self.assertIs(alsa_output.DAC_STATE["processes"][0], ffmpeg)
                self.assertIs(alsa_output.DAC_STATE["processes"][1], aplay)
            finally:
                with alsa_output.DAC_LOCK:
                    alsa_output.stop_dac_locked()
                    alsa_output.DAC_STATE.clear()
                    alsa_output.DAC_STATE.update(previous)

    def test_immediate_pipeline_failure_closes_ffmpeg_pipe(self):
        device = {
            "id": "dac:usb:test",
            "alsa_id": "hw:2,0",
            "stable_alsa_id": "hw:CARD=DAC,DEV=0",
            "caps": {"source": "driver", "pcm_rates": [44100], "pcm_max_rate": 44100, "pcm_max_bits": 16},
        }
        item = {"id": "pcm", "path": "/music/test.flac", "sample_rate": 44100, "bit_depth": 16, "is_dsd": False}

        class Process:
            def __init__(self, exited=False):
                self.exited = exited
                self.terminated = False
                self.stdout = Mock()

            def poll(self):
                return 1 if self.exited or self.terminated else None

            def terminate(self):
                self.terminated = True

            def kill(self):
                self.terminated = True

            def wait(self, **_kwargs):
                return 0

        ffmpeg = Process()
        failed_aplay = Process(exited=True)
        with patch("playback.alsa_output.dac_device_by_id", return_value=device), \
             patch("playback.alsa_output.find_aplay", return_value="/usr/bin/aplay"), \
             patch("playback.alsa_output.dac_ffmpeg_pcm_command", return_value=([], {}, {"sample_format": "s16le", "rate": 44100, "channels": 2})), \
             patch("playback.alsa_output.subprocess.Popen", side_effect=[ffmpeg, failed_aplay]):
            ok, _message = start_dac_playback(device["id"], item, {})

        self.assertFalse(ok)
        self.assertTrue(ffmpeg.terminated)
        # The pipeline handoff closes the parent's pipe once; the common
        # failure cleanup closes it again idempotently after terminating ffmpeg.
        self.assertGreaterEqual(ffmpeg.stdout.close.call_count, 2)

    def test_status_reaps_live_pipeline_peer_after_another_process_exits(self):
        class Process:
            def __init__(self, exited=False):
                self.exited = exited
                self.terminated = False
                self.waited = 0

            def poll(self):
                return 1 if self.exited or self.terminated else None

            def terminate(self):
                self.terminated = True

            def kill(self):
                self.terminated = True

            def wait(self, **_kwargs):
                self.waited += 1
                return 0

        failed = Process(exited=True)
        survivor = Process()
        with alsa_output.DAC_LOCK:
            previous = dict(alsa_output.DAC_STATE)
            alsa_output.DAC_STATE.update({"processes": [failed, survivor], "playing": True, "started_at": 0.0})
        try:
            status = dac_public_status()
        finally:
            with alsa_output.DAC_LOCK:
                alsa_output.DAC_STATE.clear()
                alsa_output.DAC_STATE.update(previous)

        self.assertEqual(status["transport"]["state"], "STOPPED")
        self.assertTrue(survivor.terminated)
        self.assertGreaterEqual(failed.waited, 1)

    def test_busy_probe_preserves_a_previous_verified_result(self):
        result = preserve_verified_busy_probe(
            {
                "source": "alsa-hw-params",
                "verified": True,
                "available": True,
                "native_dsd": True,
                "native_dsd_formats": ["DSD_U32_LE"],
                "pcm_rates": [44100, 192000],
            },
            {
                "busy": True,
                "available": False,
                "error": "ALSA open failed (-16)",
                "probed_at": 10,
            },
        )
        self.assertTrue(result["verified"])
        self.assertTrue(result["native_dsd"])

        self.assertTrue(result["busy"])
        self.assertIn("(-16)", result["error"])

    def test_dsd_strategy_does_not_coerce_string_capability(self):
        result = choose_dac_strategy(
            {"is_dsd": True, "sample_rate": 2822400, "bit_depth": 1},
            {"caps": {"source": "driver", "dsd": "false"}},
        )
        self.assertFalse(result["direct_possible"])

    def test_busy_probe_does_not_promote_unverified_result(self):
        result = preserve_verified_busy_probe(
            {
            "verified": True,
            },
            {"busy": False, "verified": False},
        )
        self.assertFalse(result["verified"])

    def test_dac_proc_text_reads_are_bounded(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            path = handle.name
            handle.write("x" * (MAX_DAC_TEXT_BYTES + 100))
        try:
            from playback.alsa_output import _read_text
            self.assertEqual(len(_read_text(path)), MAX_DAC_TEXT_BYTES)
        finally:
            os.unlink(path)

    def test_aplay_discovery_uses_a_bounded_process_output(self):
        from playback.alsa_output import alsa_devices

        with patch("playback.alsa_output.alsa_devices_from_proc", return_value=[]), \
             patch("playback.alsa_output.find_aplay", return_value="/usr/bin/aplay"), \
             patch("playback.alsa_output.check_output_bounded", return_value=b"") as output:
            self.assertEqual(alsa_devices(), [])

        self.assertEqual(output.call_args.args[0], ["/usr/bin/aplay", "-l"])
        self.assertEqual(output.call_args.kwargs, {"max_bytes": MAX_DAC_TEXT_BYTES, "timeout": 5})

    def test_aplay_discovery_rejects_oversized_output(self):
        from playback.alsa_output import alsa_devices
        from process_output import ProcessOutputTooLarge

        with patch("playback.alsa_output.alsa_devices_from_proc", return_value=[]), \
             patch("playback.alsa_output.find_aplay", return_value="/usr/bin/aplay"), \
             patch("playback.alsa_output.check_output_bounded", side_effect=ProcessOutputTooLarge):
            self.assertEqual(alsa_devices(), [])


    def test_stream_caps_read_kilohertz_rates_written_by_the_driver(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "card0"))
            with open(os.path.join(root, "card0", "stream0"), "w", encoding="utf-8") as handle:
                handle.write(
                    "Playback: #0\n\tSampling Frequency: 44.1 kHz, 48 kHz, 96 kHz\n"
                    "\tFormats: S16_LE S24_LE S32_LE\n"
                )
            with patch.dict(os.environ, {"FNAUDIO_ASOUND_ROOT": root}):
                caps = alsa_output.parse_dac_stream_caps("0")
        self.assertEqual(caps["pcm_rates"], [44100, 48000, 96000])
        self.assertEqual(caps["pcm_max_rate"], 96000)
        self.assertEqual(caps["pcm_max_bits"], 32)

    def test_probe_cache_ages_on_the_monotonic_clock(self):
        original = dict(ALSA_CAPS_CACHE)
        key = "usb:1:2:3:dev0"
        try:
            ALSA_CAPS_CACHE.clear()
            ALSA_CAPS_CACHE[key] = {
                "source": "alsa-hw-params",
                "verified": True,
                "available": True,
                "error": "",
                "pcm_rates": [44100],
                "pcm_formats": ["S16_LE"],
                "probed_at": 1700000000.0,
                "probed_at_monotonic": 1000.0,
            }
            device = {"stable_id": key, "alsa_id": "hw:0,0"}
            clocks = [
                patch("playback.alsa_output.time.time", return_value=1700000000.0 - 6000.0),
                patch("playback.alsa_output.ctypes.util.find_library", return_value=""),
                patch("playback.alsa_output.find_libasound", return_value=""),
            ]
            with clocks[0], clocks[1], clocks[2], \
                 patch("playback.alsa_output.time.monotonic", return_value=1060.0):
                fresh = alsa_output.probe_alsa_hw_params(device)
            self.assertTrue(fresh["verified"], "60 monotonic seconds is inside the 300s window")
            self.assertEqual(fresh["pcm_rates"], [44100])
            with clocks[0], clocks[1], clocks[2], \
                 patch("playback.alsa_output.time.monotonic", return_value=1400.0):
                stale = alsa_output.probe_alsa_hw_params(device)
            self.assertFalse(stale["verified"], "a 400s-old probe must be rebuilt")
            self.assertIn("libasound", stale["error"])
        finally:
            ALSA_CAPS_CACHE.clear()
            ALSA_CAPS_CACHE.update(original)

    def test_dac_control_only_signals_the_pipeline_owned_by_its_lock_window(self):
        stale = Mock(pid=400)
        stale.poll.return_value = None
        live = Mock(pid=500)
        live.poll.return_value = None

        class TrackedLock:
            """Count lock entries so the test can place a swap between two windows."""

            def __init__(self):
                self.acquisitions = 0

            def __enter__(self):
                self.acquisitions += 1
                return self

            def __exit__(self, *_args):
                return False

        class ReplacedPipeline(dict):
            """Another start replaced the pipeline after the first lock window."""

            def __init__(self, initial, lock):
                dict.__init__(self, initial)
                self._lock = lock

            def get(self, key, default=None):
                if key == "processes":
                    return [stale] if self._lock.acquisitions <= 1 else [live]
                return dict.get(self, key, default)

        lock = TrackedLock()
        state = ReplacedPipeline({
            "device_id": "dac:usb:test",
            "item_id": "track",
            "playing": True,
            "offset": 0.0,
            "started_monotonic": time.monotonic() - 12.0,
            "processes": [stale],
        }, lock)
        signals = Mock()
        signals.SIGSTOP = "SIGSTOP"
        signals.SIGCONT = "SIGCONT"
        killer = Mock()
        operating_system = Mock()
        operating_system.name = "posix"
        operating_system.kill = killer
        with patch.object(alsa_output, "DAC_LOCK", lock), \
             patch.object(alsa_output, "DAC_STATE", state), \
             patch.object(alsa_output, "os", operating_system), \
             patch.object(alsa_output, "signal", signals):
            ok, _message = alsa_output.dac_control("pause")

        self.assertTrue(ok)
        self.assertGreaterEqual(lock.acquisitions, 2, "the control path takes the lock in more than one window")
        self.assertEqual(killer.call_args_list, [call(500, "SIGSTOP")])
        self.assertFalse(state["playing"])

    def test_duplicated_play_does_not_rewind_the_position(self):
        state = {
            "device_id": "dac:usb:test",
            "item_id": "track",
            "playing": True,
            "offset": 5.0,
            "started_monotonic": 100.0,
            "processes": [],
        }
        operating_system = Mock()
        operating_system.name = "posix"
        with patch.object(alsa_output, "DAC_STATE", state), \
             patch.object(alsa_output, "os", operating_system), \
             patch("playback.alsa_output.time.monotonic", return_value=180.0):
            ok, _message = alsa_output.dac_control("play")

        self.assertTrue(ok)
        self.assertEqual(state["started_monotonic"], 100.0, "a play on a running pipeline must not restart the clock")
        with patch("playback.alsa_output.time.monotonic", return_value=180.0):
            self.assertEqual(round(alsa_output._playing_elapsed(state)), 80)


if __name__ == "__main__":
    unittest.main()