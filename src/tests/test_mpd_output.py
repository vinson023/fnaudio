import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.models import PlaybackCommand, PlaybackState, TrackRef
from playback.mpd_client import MpdError
from playback.mpd_output import MpdOutput


class QueueService:
    host = "127.0.0.1"
    port = 56660

    def __init__(self):
        self.sync_calls = 0

    def prepare_track_output(self, _item):
        return {"ok": True}

    def sync_playback_queue(self, *_args, **_kwargs):
        self.sync_calls += 1
        if self.sync_calls == 1:
            raise MpdError("ACK [50@0] {addid} No such song")
        return {"ok": True, "song_ids": {"new": "7"}}


class FixedVolumeService:
    host = "127.0.0.1"
    port = 56660

    def output_capabilities(self):
        return {"volume_control": {"available": False, "mode": "none"}}

    def mixer_policy(self):
        return {"available": False, "message": "固定输出电平"}


class MpdOutputTests(unittest.TestCase):
    def test_open_preserves_backend_failure_message(self):
        service = mock.Mock()
        service.prepare_track_output.return_value = {"ok": True}
        service.sync_playback_queue.return_value = {"ok": False, "message": "queue rejected"}
        output = MpdOutput(service)
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        track = TrackRef.from_mapping({"id": "track-1", "path": "/music/one.flac"})

        with mock.patch.object(output, "start_service", return_value={"ok": True, "running": True}), mock.patch.object(
            output, "_output_ready", return_value={"ok": True}
        ):
            result = output.open(track, state, {"item": track.item})

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "queue rejected")

    def test_open_replaces_non_finite_positions_before_native_queue(self):
        service = mock.Mock()
        service.prepare_track_output.return_value = {"ok": True}
        service.sync_playback_queue.return_value = {"ok": True}
        output = MpdOutput(service)
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        track = TrackRef.from_mapping({"id": "cue", "path": "/music/cue.flac", "cue_track": True, "cue_start": float("inf")})
        with mock.patch.object(output, "start_service", return_value={"ok": True, "running": True}), mock.patch.object(
            output, "_output_ready", return_value={"ok": True}
        ):
            result = output.open(track, state, {"item": track.item, "position": float("nan")})
        self.assertTrue(result["ok"])
        self.assertEqual(service.sync_playback_queue.call_args.kwargs["start"], 0.0)

    @mock.patch("playback.mpd_output.mpd_update_and_wait", return_value={"ok": True, "updated": True})
    def test_native_queue_retries_once_after_mpd_database_update(self, update):
        service = QueueService()
        output = MpdOutput(service)
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        track = TrackRef.from_mapping({"id": "new", "path": "/music/new.wav"})
        state.queue = [track]
        state.current_track_id = "new"

        with mock.patch.object(output, "start_service", return_value={"ok": True, "running": True}), mock.patch.object(
            output, "_output_ready", return_value={"ok": True}
        ):
            result = output.open(track, state, {"item": track.item})

        self.assertTrue(result["ok"])
        self.assertEqual(service.sync_calls, 2)
        self.assertEqual(result["mpd_update"], {"ok": True, "updated": True})
        update.assert_called_once_with(host="127.0.0.1", port=56660)

    def test_missing_source_returns_structured_media_error(self):
        output = MpdOutput()
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        track = TrackRef.from_mapping({"id": "missing"})

        result = output.open(track, state, {"item": track.item})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "source_missing")
        self.assertEqual(result["error"]["domain"], "media")

    @mock.patch("playback.mpd_output.mpd_control", side_effect=MpdError("Failed to open ALSA device: Device or resource busy"))
    def test_control_failure_returns_structured_output_error(self, _control):
        output = MpdOutput()
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        with mock.patch.object(output, "start_service", return_value={"ok": True, "running": True}):
            result = output.command(PlaybackCommand(action="play"), state)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "output_device_busy")
        self.assertTrue(result["error"]["retryable"])

    def test_fixed_volume_output_does_not_advertise_or_accept_volume(self):
        output = MpdOutput(FixedVolumeService())
        state = PlaybackState(target_id="mpd:local", target_kind="mpd")

        self.assertFalse(output.capabilities()["volume"])
        result = output.command(PlaybackCommand(action="volume", position=25), state)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "mixer_unavailable")
        self.assertEqual(result["error"]["domain"], "output")

    def test_capabilities_do_not_coerce_string_flags(self):
        service = mock.Mock()
        service.output_capabilities.return_value = {
            "volume_control": {"available": "false"},
            "dsd_native": "false", "native_dsd_verified": "false",
            "dop": "false", "bitperfect": "false",
        }
        caps = MpdOutput(service).capabilities()
        for key in ("volume", "native_dsd", "native_dsd_verified", "dop", "bitperfect"):
            self.assertFalse(caps[key], key)


if __name__ == "__main__":
    unittest.main()
