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



class RecordingMpdService:
    """Control-plane fake with only the attributes every command path needs.

    It deliberately has no select_output, mixer_policy or refresh_status, so
    MpdOutput.command takes its early-return paths and the single recorded call
    is the whole observation.
    """

    host = "127.0.0.1"
    port = 56660

    def __init__(self):
        self.controls = []

    def control(self, action, position=None):
        self.controls.append((action, position))
        return {"ok": True}

    def refresh_status(self):
        raise AssertionError("transport commands must not synchronously refresh MPD status")


# 100s into a 210s source file, this segment is 30s long.  MPD is driven in
# source seconds, so a client seek of 30s must reach it as 130s.
NATIVE_CUE_ITEM = {
    "id": "cue-2",
    "path": "/music/disc.flac",
    "cue_track": True,
    "cue_start": 100.0,
    "cue_end": 130.0,
    "duration": 30.0,
}
TRANSCODED_CUE_ITEM = dict(NATIVE_CUE_ITEM, id="cue-3", path="/music/disc.ape")
PLAIN_ITEM = {"id": "plain", "path": "/music/one.flac", "duration": 30.0}


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
        # The fake service has no uri_for_path, so there is no narrower scope
        # than the whole library and the fallback keeps its "all" behaviour --
        # and with no uri named, the wait verifies nothing instead of verifying
        # a uri this service cannot produce.
        update.assert_called_once_with(host="127.0.0.1", port=56660, path="", verify_uri="")

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

    def test_control_returns_without_a_second_status_round_trip(self):
        service = RecordingMpdService()
        output = MpdOutput(service)
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        with mock.patch.object(output, "start_service", return_value={"ok": True, "running": True}):
            result = output.command(PlaybackCommand(action="play"), state)
        self.assertTrue(result["ok"])
        self.assertEqual(service.controls, [("play", None)])

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

    def _seek_call(self, action, position, item=None, queue_item=None):
        service = RecordingMpdService()
        output = MpdOutput(service)
        state = PlaybackState(target_id="mpd:local", target_kind="mpd")
        context = {}
        if queue_item is not None:
            track = TrackRef.from_mapping(queue_item)
            state.queue = [track]
            state.current_track_id = track.track_id
            # Deliberately wrong so the O(1) hit fails and the identity scan runs.
            state.current_index = 9
        if item is not None:
            context = {"item": item}
        with mock.patch.object(output, "start_service", return_value={"ok": True, "running": True}):
            result = output.command(PlaybackCommand(action=action, position=position), state, context)
        self.assertTrue(result["ok"], result)
        return service.controls[-1]

    def test_seek_on_a_native_cue_segment_is_folded_back_to_source_seconds(self):
        self.assertEqual(self._seek_call("seek", 30.0, item=NATIVE_CUE_ITEM), ("seek", 130.0))

    def test_transcoded_and_plain_seeks_reach_mpd_in_their_own_seconds(self):
        self.assertEqual(self._seek_call("seek", 30.0, item=TRANSCODED_CUE_ITEM), ("seek", 30.0))
        self.assertEqual(self._seek_call("seek", 30.0, item=PLAIN_ITEM), ("seek", 30.0))

    def test_only_a_seek_is_folded(self):
        self.assertEqual(self._seek_call("pause", 30.0, item=NATIVE_CUE_ITEM), ("pause", 30.0))
        self.assertEqual(self._seek_call("play", 30.0, item=NATIVE_CUE_ITEM), ("play", 30.0))

    def test_a_seek_falls_back_to_the_queue_reference_without_an_item(self):
        self.assertEqual(self._seek_call("seek", 30.0, queue_item=NATIVE_CUE_ITEM), ("seek", 130.0))
        self.assertEqual(self._seek_call("seek", 30.0, queue_item=TRANSCODED_CUE_ITEM), ("seek", 30.0))

    def test_an_unresolved_item_never_invents_an_offset(self):
        self.assertEqual(self._seek_call("seek", 30.0), ("seek", 30.0))
        self.assertEqual(self._seek_call("seek", None, item=NATIVE_CUE_ITEM), ("seek", 100.0))
        self.assertEqual(self._seek_call("seek", -5.0, item=NATIVE_CUE_ITEM), ("seek", 100.0))


if __name__ == "__main__":
    unittest.main()
