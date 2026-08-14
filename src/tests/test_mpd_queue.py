import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.models import TrackRef
from services.mpd_service import MpdService


class MpdQueueTests(unittest.TestCase):
    def make_service(self, persist=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        config_path = temp.name + "/config.json" if persist else None
        with mock.patch.object(MpdService, "_select_port", return_value=56660), mock.patch.object(
            MpdService, "_find_binary", return_value="/usr/bin/mpd"
        ), mock.patch.object(MpdService, "_data_root", return_value=temp.name):
            return MpdService(
                {"mpd_port": 56660, "library_path": "/music"},
                app_root=temp.name,
                app_config_path=config_path,
            )

    @mock.patch("services.mpd_service.alsa_devices", return_value=[])
    def test_mpd_output_disables_implicit_resampling(self, _devices):
        service = self.make_service()
        result = service.ensure_config()
        self.assertTrue(result["ok"])
        with open(service.config_path, "r", encoding="utf-8") as fh:
            config_text = fh.read()
        self.assertIn('auto_resample "no"', config_text)
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
    def test_unsupported_pcm_rate_is_rejected(self, selected, probe):
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
        self.assertFalse(result["ok"])
        self.assertIn("隐式重采样", result["message"])

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
        transcode_audio.return_value = ("/cache/ape.ape-source.flac", "audio/flac")
        replace_queue.return_value = {"ok": True, "song_ids": {"ape": "5"}}

        service.sync_playback_queue(queue, "ape")

        transcode_audio.assert_called_once_with(
            queue[0].item, {**service.config, "cache_dir": "/music/fnaudio-transcode"}, "ape_flac"
        )
        self.assertTrue(replace_queue.call_args.args[0][0]["uri"].endswith("ape.ape-source.flac"))
        update.assert_called_once_with(host=service.host, port=service.port)

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

    def test_backend_song_id_maps_back_to_logical_track(self):
        service = self.make_service()
        service._queue_song_tracks = {"21": "track-b"}
        probe = {"status": {"song": {"Id": "21"}}}

        self.assertEqual(service.track_id_for_status(probe), "track-b")

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


if __name__ == "__main__":
    unittest.main()
