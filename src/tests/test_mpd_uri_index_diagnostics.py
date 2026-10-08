import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.models import PlaybackState, TrackRef
from playback.mpd_client import (
    MpdError,
    local_file_uri,
    mpd_library_state,
    mpd_library_state_message,
    mpd_update_and_wait,
    mpd_update_hint,
)
from playback.mpd_output import MpdOutput
from services.mpd_service import MpdService


# Measured on the fnOS test host: the library is entirely CJK folder names with
# spaces, and MPD answers ``addid`` without percent-decoding the uri.
CJK_TRACK = "/vol2/1000/music/未整理/索尼精选Hi-Res/春野 - The Lover/Up In The Clouds.flac"
CJK_RELATIVE = "未整理/索尼精选Hi-Res/春野 - The Lover/Up In The Clouds.flac"
MISSING_ACK = "ACK [50@1] {addid} No such song"


def make_service(library_paths):
    temp = tempfile.TemporaryDirectory()
    config = {
        "library_path": library_paths[0],
        "library_paths": list(library_paths),
        "mpd_port": 56660,
        "cache_dir": temp.name,
    }
    with mock.patch.object(MpdService, "_select_port", return_value=56660), mock.patch.object(
        MpdService, "_find_binary", return_value="/usr/bin/mpd"
    ), mock.patch.object(MpdService, "_data_root", return_value=temp.name):
        service = MpdService(config)
    service._cleanup_temp = temp
    return service


class MpdUriFormTests(unittest.TestCase):
    def test_local_file_uri_is_not_percent_encoded(self):
        uri = local_file_uri(CJK_TRACK)
        self.assertEqual(uri, "file://" + os.path.abspath(CJK_TRACK))
        self.assertNotIn("%", uri)

    def test_uri_outside_every_library_root_is_not_percent_encoded(self):
        service = make_service(["/vol2/1000/music"])
        self.addCleanup(service._cleanup_temp.cleanup)
        uri = service.uri_for_path("/vol1/1000/其他/未整理/a b.flac")
        self.assertEqual(uri, "file://" + os.path.abspath("/vol1/1000/其他/未整理/a b.flac"))
        self.assertNotIn("%", uri)
        self.assertIn("a b.flac", uri)

    def test_uri_inside_the_root_stays_database_relative(self):
        service = make_service(["/vol2/1000/music"])
        self.addCleanup(service._cleanup_temp.cleanup)
        self.assertEqual(service.uri_for_path(CJK_TRACK), CJK_RELATIVE)


class MpdUpdateScopeTests(unittest.TestCase):
    def test_hint_uses_the_folder_of_a_database_relative_uri(self):
        self.assertEqual(mpd_update_hint(CJK_RELATIVE), "未整理/索尼精选Hi-Res/春野 - The Lover")

    def test_hint_refuses_to_narrow_a_non_relative_uri(self):
        self.assertEqual(mpd_update_hint("file:///vol1/x.flac"), "")
        self.assertEqual(mpd_update_hint("top.flac"), "")
        self.assertEqual(mpd_update_hint(None), "")

    def test_targeted_update_asks_mpd_for_one_folder_only(self):
        connection = mock.MagicMock()
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), mock.patch(
            "playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1]
        ), mock.patch("playback.mpd_client.mpd_pairs", return_value={}):
            result = mpd_update_and_wait(path="未整理/春野")
        connection.__enter__.return_value.command.assert_called_once_with("update", "未整理/春野")
        self.assertEqual(result["scope"], "未整理/春野")

    def test_bare_update_still_refreshes_the_whole_library(self):
        connection = mock.MagicMock()
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), mock.patch(
            "playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1]
        ), mock.patch("playback.mpd_client.mpd_pairs", return_value={}):
            result = mpd_update_and_wait()
        connection.__enter__.return_value.command.assert_called_once_with("update")
        self.assertEqual(result["scope"], "all")


class MpdLibraryStateTests(unittest.TestCase):
    def test_state_reports_indexed_songs_and_rebuild_flag(self):
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.side_effect = [
            ["state: stop", "updating_db: 1"],
            ["artists: 2926", "songs: 23751"],
        ]
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection):
            self.assertEqual(
                mpd_library_state(), {"available": True, "indexed": 23751, "updating": True}
            )

    def test_state_stays_quiet_when_mpd_does_not_answer(self):
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.side_effect = MpdError("connection closed")
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection):
            self.assertEqual(
                mpd_library_state(), {"available": False, "indexed": 0, "updating": False}
            )

    def test_message_distinguishes_a_cold_database_from_a_missing_file(self):
        self.assertIn("MPD 索引仍在建立中，当前已收录 23751 首", mpd_library_state_message(
            {"available": True, "indexed": 23751, "updating": True}))
        self.assertIn("MPD 索引已完成，当前收录 62684 首", mpd_library_state_message(
            {"available": True, "indexed": 62684, "updating": False}))
        self.assertIn("不可读取", mpd_library_state_message({"available": False}))
        self.assertIn("不可读取", mpd_library_state_message(None))


class MpdFailureDiagnosticsTests(unittest.TestCase):
    def test_single_track_failure_names_uri_scope_and_index_progress(self):
        output = MpdOutput()
        with mock.patch("playback.mpd_output.mpd_load_uri", side_effect=[MpdError(MISSING_ACK), MpdError(MISSING_ACK)]), \
             mock.patch("playback.mpd_output.mpd_update_and_wait",
                        return_value={"ok": True, "updated": False, "scope": "未整理/春野"}) as update, \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 23751, "updating": True}):
            with self.assertRaises(MpdError) as caught:
                output._load_uri_with_retry("未整理/春野/a b.flac", 0.0)
        message = str(caught.exception)
        self.assertEqual(update.call_args.kwargs["path"], "未整理/春野")
        self.assertIn(MISSING_ACK, message)
        self.assertIn("已请求 MPD 收录 未整理/春野 后重试仍失败", message)
        self.assertIn("uri=未整理/春野/a b.flac", message)
        self.assertIn("MPD 索引仍在建立中，当前已收录 23751 首", message)

    def test_queue_failure_is_wrapped_the_same_way(self):
        class QueueService:
            host = "127.0.0.1"
            port = 56660

            def __init__(self):
                self.sync_calls = 0

            def prepare_track_output(self, _item):
                return {"ok": True}

            def uri_for_path(self, path):
                return "未整理/春野/up.flac"

            def sync_playback_queue(self, *_args, **_kwargs):
                self.sync_calls += 1
                raise MpdError(MISSING_ACK)

        output = MpdOutput(QueueService())
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        track = TrackRef.from_mapping({"id": "new", "path": "/vol2/1000/music/未整理/春野/up.flac"})
        state.queue = [track]
        state.current_track_id = "new"
        with mock.patch.object(output, "start_service", return_value={"ok": True, "running": True}), \
             mock.patch.object(output, "_output_ready", return_value={"ok": True}), \
             mock.patch("playback.mpd_output.mpd_update_and_wait",
                        return_value={"ok": True, "updated": False, "scope": "未整理/春野"}) as update, \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 23751, "updating": True}):
            result = output.open(track, state, {"item": track.item})
        self.assertFalse(result["ok"])
        self.assertEqual(update.call_args.kwargs["path"], "未整理/春野")
        self.assertIn("已请求 MPD 收录 未整理/春野 后重试仍失败", result["message"])
        self.assertIn("uri=未整理/春野/up.flac", result["message"])
        self.assertIn("当前已收录 23751 首", result["message"])

    def test_generated_transcode_is_indexed_as_one_folder(self):
        service = make_service(["/music"])
        self.addCleanup(service._cleanup_temp.cleanup)
        queue = [TrackRef.from_mapping({"id": "ape", "path": "/music/source.ape", "mime": "audio/ape"})]
        with mock.patch("services.mpd_service.transcode_to_audio",
                        return_value=("/music/fnaudio-transcode/ape.ape-source.flac", "audio/flac")), \
             mock.patch("services.mpd_service.mpd_update_and_wait") as update, \
             mock.patch("services.mpd_service.mpd_replace_queue", return_value={"ok": True, "song_ids": {"ape": "5"}}):
            service.sync_playback_queue(queue, "ape")
        self.assertEqual(update.call_args.kwargs["path"], "fnaudio-transcode")

    def test_unresolvable_entry_uri_still_gives_the_actionable_message(self):
        """A service that cannot name the uri must not replace the diagnosis."""
        class QueueService:
            host = "127.0.0.1"
            port = 56660

            def prepare_track_output(self, _item):
                return {"ok": True}

            def uri_for_path(self, _path):
                raise RuntimeError("index is being rebuilt")

            def sync_playback_queue(self, *_args, **_kwargs):
                raise MpdError(MISSING_ACK)

        output = MpdOutput(QueueService())
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        track = TrackRef.from_mapping({"id": "new", "path": "/vol2/1000/music/未整理/春野/up.flac"})
        state.queue = [track]
        state.current_track_id = "new"
        with mock.patch.object(output, "start_service", return_value={"ok": True, "running": True}), \
             mock.patch.object(output, "_output_ready", return_value={"ok": True}), \
             mock.patch("playback.mpd_output.mpd_update_and_wait",
                        return_value={"ok": True, "updated": False, "scope": ""}), \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 23751, "updating": True}):
            result = output.open(track, state, {"item": track.item})
        self.assertFalse(result["ok"])
        message = result["message"]
        self.assertNotIn("index is being rebuilt", message)
        self.assertIn("已请求 MPD 收录 整个曲库 后重试仍失败", message)
        self.assertIn("MPD 索引仍在建立中，当前已收录 23751 首", message)


if __name__ == "__main__":
    unittest.main()
