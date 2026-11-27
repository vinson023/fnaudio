"""DSD under the software-volume switch: why the level never moved.

MPD 0.23's software mixer is a documented no-op on DSD samples
(`pcm/Volume.cxx`: "case SampleFormat::DSD: // TODO: implement this; currently,
it's a no-op"), so a DAC with no hardware mixer can never be attenuated while
it is being fed 1-bit data. The only way to keep the slider working is to hand
MPD PCM, which `volume.dsd = auto` does exactly when fnAudio is the one
attenuating. `native` keeps the DSD stream and gives the level up.
"""

import pathlib
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, "app/server")

import transcode  # noqa: E402
from services.mpd_service import MpdService  # noqa: E402


def service_with(config):
    service = object.__new__(MpdService)
    service.config = dict(config)
    return service


DAC = {"alsa_id": "hw:1", "caps": {"pcm_rates": [44100, 48000, 88200, 176400, 352800]}}


class DsdPcmPlanTests(unittest.TestCase):
    def test_the_switch_alone_does_not_convert_without_a_software_mixer(self):
        service = service_with({"volume": {"targets": {"dac": "fixed"}, "software_fallback": True}})
        plan = service.dsd_pcm_plan(DAC, mixer={"mode": "none"})
        self.assertIs(plan["convert"], False)
        self.assertEqual(plan["reason"], "mixer-none")

    def test_a_hardware_mixer_keeps_dsd_native(self):
        # The DAC attenuates in its own domain, which works on 1-bit data, so
        # converting here would throw away DSD for nothing.
        service = service_with({"volume": {"targets": {"dac": "hardware"}}})
        plan = service.dsd_pcm_plan(DAC, mixer={"mode": "hardware"})
        self.assertIs(plan["convert"], False)

    def test_software_mix_on_a_dsd_dac_converts(self):
        service = service_with({"volume": {"software_fallback": True, "targets": {"dac": "auto"}}})
        plan = service.dsd_pcm_plan(DAC, mixer={"mode": "software"})
        self.assertIs(plan["convert"], True)
        self.assertEqual(plan["rates"], (88200, 176400, 352800))

    def test_the_policy_can_opt_out_of_conversion(self):
        service = service_with({"volume": {"software_fallback": True, "dsd": "native"}})
        plan = service.dsd_pcm_plan(DAC, mixer={"mode": "software"})
        self.assertIs(plan["convert"], False)
        self.assertEqual(plan["reason"], "policy-native")

    def test_rates_are_bounded_by_the_dac_descriptor(self):
        service = service_with({"volume": {"software_fallback": True}})
        plan = service.dsd_pcm_plan({"alsa_id": "hw:1", "caps": {"pcm_rates": [44100, 88200]}},
                                    mixer={"mode": "software"})
        self.assertEqual(plan["rates"], (88200,))

    def test_a_dac_with_no_pcm_rates_still_gets_one_defensible_rate(self):
        service = service_with({"volume": {"software_fallback": True}})
        plan = service.dsd_pcm_plan({"alsa_id": "hw:1", "caps": {}}, mixer={"mode": "software"})
        self.assertEqual(plan["rates"], (176400,))

    def test_dsd64_and_dsd128_choose_different_rates(self):
        service = service_with({"volume": {"software_fallback": True}})
        plan = service.dsd_pcm_plan(DAC, mixer={"mode": "software"})
        self.assertEqual(service._dsd_pcm_rate_for({"sample_rate": 2822400}, plan), 176400)
        self.assertEqual(service._dsd_pcm_rate_for({"sample_rate": 5644800}, plan), 352800)
        # DSD256 is above what this class of DAC takes: it lands on 352800
        # instead of asking for 705600.
        self.assertEqual(service._dsd_pcm_rate_for({"sample_rate": 11289600}, plan), 352800)

    def test_a_dac_that_stops_at_88k2_gets_88k2_from_every_dsd_rate(self):
        service = service_with({"volume": {"software_fallback": True}})
        plan = service.dsd_pcm_plan({"alsa_id": "hw:1", "caps": {"pcm_rates": [44100, 88200]}},
                                    mixer={"mode": "software"})
        self.assertEqual(service._dsd_pcm_rate_for({"sample_rate": 2822400}, plan), 88200)
        self.assertEqual(service._dsd_pcm_rate_for({"sample_rate": 5644800}, plan), 88200)


class DsdCacheNamingTests(unittest.TestCase):
    def test_the_rate_is_part_of_the_cache_name(self):
        # Otherwise a DAC swap would hand MPD a file the new device cannot take.
        target, mime = transcode.transcode_cache_target(
            {"id": "abc", "sample_rate": 2822400}, {"cache_dir": "/cache"}, "dsd_pcm")
        self.assertTrue(target.endswith("abc.dsd-176k-24bit.flac"), target)
        self.assertEqual(mime, "audio/flac")

    def test_dsd256_is_capped_at_the_rate_a_usb_dac_can_take(self):
        target, _mime = transcode.transcode_cache_target(
            {"id": "abc", "sample_rate": 11289600}, {"cache_dir": "/cache"}, "dsd_pcm")
        self.assertTrue(target.endswith("abc.dsd-352k-24bit.flac"), target)

    def test_the_conversion_is_recorded_as_a_failure_mode_of_its_own(self):
        # `transcode_failure()` scans this tuple; a missing entry means a
        # permanent failure here would be retried on every play.
        source = pathlib.Path("app/server/transcode.py").read_text(encoding="utf-8")
        self.assertIn('"dsd_wav", "dsd_pcm"', source)


class DsdQueueTests(unittest.TestCase):
    def _service(self):
        service = object.__new__(MpdService)
        service.config = {"volume": {"software_fallback": True}}
        service._queue_fingerprint = ()
        service._queue_song_ids = {}
        service._queue_song_tracks = {}
        service._queue_entries = []
        service._queue_current_track_id = ""
        service._last_position = 0.0
        service._queue_repeat = "off"
        service._queue_shuffle = False
        service.host = "127.0.0.1"
        service.port = 6600
        service._queue_replace_lock = threading.Lock()
        service._queue_replace_depth = 0
        service._queue_replace_finished_at = 0.0
        service._queue_lock = threading.RLock()
        service._command_lock = threading.RLock()
        service._recovery_active = threading.Event()
        service._queue_current_track_id = ""
        service._last_position = 0.0
        return service

    def test_the_queue_entry_is_the_converted_pcm_file(self):
        service = self._service()
        item = {"id": "t1", "path": "/music/a.dsf", "is_dsd": True, "sample_rate": 2822400}
        with mock.patch.object(service, "dsd_pcm_plan",
                               return_value={"convert": True, "rates": (176400,)}), \
                mock.patch("services.mpd_service.transcode_to_audio",
                           return_value=("/music/fnaudio-transcode/t1.dsd-176k-24bit.flac", "audio/flac")) as convert, \
                mock.patch("services.mpd_service.mpd_update_and_wait"), \
                mock.patch("services.mpd_service.mpd_replace_queue",
                           return_value={"ok": True, "song_ids": {"t1": "7"}}):
            result = service.sync_playback_queue(
                [SimpleNamespace(track_id="t1", item=item)], "t1", current_item=item)
        self.assertIs(result["ok"], True)
        self.assertEqual(convert.call_args.args[2], "dsd_pcm")
        self.assertEqual(convert.call_args.args[1]["dsd_pcm_rate"], 176400)
        self.assertTrue(service._queue_entries[0]["uri"].endswith("fnaudio-transcode/t1.dsd-176k-24bit.flac"),
                        service._queue_entries[0]["uri"])

    def test_a_failed_conversion_still_plays_the_dsd_file(self):
        service = self._service()
        item = {"id": "t1", "path": "/music/a.dsf", "is_dsd": True, "sample_rate": 2822400}
        with mock.patch.object(service, "dsd_pcm_plan",
                               return_value={"convert": True, "rates": (176400,)}), \
                mock.patch("services.mpd_service.transcode_to_audio", side_effect=RuntimeError("boom")), \
                mock.patch("services.mpd_service.mpd_replace_queue",
                           return_value={"ok": True, "song_ids": {"t1": "7"}}):
            result = service.sync_playback_queue(
                [SimpleNamespace(track_id="t1", item=item)], "t1", current_item=item)
        self.assertIs(result["ok"], True)
        self.assertTrue(service._queue_entries[0]["uri"].endswith("a.dsf"),
                        "a broken converter must fall back to the original file, not block playback")


if __name__ == "__main__":
    unittest.main()
