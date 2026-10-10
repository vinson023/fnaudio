import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.models import PlaybackState, TrackRef
from playback.mpd_client import (
    MpdError,
    MpdQueueEntryError,
    local_file_uri,
    mpd_addid_failure_uri,
    mpd_library_state,
    mpd_library_state_message,
    mpd_replace_queue,
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

    def test_targeted_update_tracks_the_job_mpd_queued_and_reports_counters(self):
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        states = [
            {"available": True, "indexed": 23483, "updating": False, "job": ""},
            {"available": True, "indexed": 23483, "updating": True, "job": "7"},
            {"available": True, "indexed": 62684, "updating": False, "job": ""},
        ]
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", side_effect=states), \
             mock.patch("playback.mpd_client.time.sleep"):
            result = mpd_update_and_wait(path="未整理/春野", timeout=30.0)
        connection.__enter__.return_value.command.assert_called_once_with("update", "未整理/春野")
        self.assertEqual(result["scope"], "未整理/春野")
        self.assertEqual(result["job"], "7")
        self.assertTrue(result["updated"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["indexed_before"], 23483)
        self.assertEqual(result["indexed_after"], 62684)

    def test_bare_update_still_refreshes_the_whole_library(self):
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 3"]
        states = [
            {"available": True, "indexed": 0, "updating": False, "job": ""},
            {"available": True, "indexed": 0, "updating": True, "job": "3"},
            {"available": True, "indexed": 62684, "updating": False, "job": ""},
        ]
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", side_effect=states), \
             mock.patch("playback.mpd_client.time.sleep"):
            result = mpd_update_and_wait(timeout=30.0)
        connection.__enter__.return_value.command.assert_called_once_with("update")
        self.assertEqual(result["scope"], "all")
        self.assertTrue(result["updated"])

    def test_a_scan_that_never_shows_a_queued_job_is_not_reported_finished(self):
        """The old wait called this success, which is what made retries no-ops."""
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = []
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state",
                        return_value={"available": True, "indexed": 1775, "updating": False, "job": ""}), \
             mock.patch("playback.mpd_client.time.sleep"):
            result = mpd_update_and_wait(path="未整理/春野", timeout=30.0)
        self.assertFalse(result["updated"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["indexed_after"], 1775)
        self.assertIn("still running", result["message"])


    def test_the_first_status_read_happens_after_the_queue_grace(self):
        """Status must not be read while the queued job may still be unstarted.

        ``update`` answers with a job id before MPD has begun the scan, and a
        status read taken in that window shows no ``updating_db`` at all.  The
        first version of this wait called that "indexing finished", which made
        the targeted refresh a silent no-op on the fnOS host.
        """
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        states = [
            {"available": True, "indexed": 23483, "updating": False, "job": ""},
            {"available": True, "indexed": 23483, "updating": True, "job": "7"},
            {"available": True, "indexed": 62684, "updating": False, "job": ""},
        ]
        order = []

        def read_state(*_args, **_kwargs):
            order.append("poll")
            return states[min(len(order) - 1, len(states) - 1)]

        def nap(*_args, **_kwargs):
            order.append("sleep")

        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", side_effect=read_state), \
             mock.patch("playback.mpd_client.time.sleep", side_effect=nap), \
             mock.patch("playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1, 0.2]):
            result = mpd_update_and_wait(path="未整理/春野", timeout=30.0, poll=0.2)
        # A ``poll`` is one status read.  The first one is the pre-update
        # baseline, so the grace sleep has to land before the read that looks
        # for our job; without it the very first read is the one that used to
        # be mistaken for a finished scan.
        self.assertEqual(order[:2], ["poll", "sleep"])
        self.assertTrue(result["updated"])

    def test_a_job_that_finished_inside_the_grace_window_counts_as_done(self):
        """A short scan must not be reported as timed out just because it was fast."""
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 8"]
        states = [
            {"available": True, "indexed": 0, "updating": False, "job": ""},
            {"available": True, "indexed": 62684, "updating": False, "job": ""},
        ]
        reads = []

        def read_state(*_args, **_kwargs):
            reads.append(len(reads))
            return states[min(len(reads) - 1, len(states) - 1)]

        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", side_effect=read_state), \
             mock.patch("playback.mpd_client.time.sleep"):
            result = mpd_update_and_wait(timeout=30.0, poll=0.2)
        self.assertTrue(result["updated"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["indexed_after"], 62684)

    def test_a_database_that_goes_away_mid_wait_stops_the_wait(self):
        """A dead MPD must end the wait, not be polled until its timeout."""
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        states = [
            {"available": True, "indexed": 1775, "updating": False, "job": ""},
            {"available": False, "indexed": 0, "updating": False, "job": ""},
        ]
        index = []

        def read_state(*_args, **_kwargs):
            index.append(len(index))
            return states[min(len(index) - 1, len(states) - 1)]

        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", side_effect=read_state), \
             mock.patch("playback.mpd_client.time.sleep"):
            result = mpd_update_and_wait(timeout=30.0, poll=0.2)
        self.assertFalse(result["updated"])
        self.assertTrue(result["timed_out"])

    def test_a_newer_scan_supersedes_the_job_we_queued(self):
        """Once MPD is busy with a *later* job, ours can only be finished."""
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        states = [
            {"available": True, "indexed": 1775, "updating": True, "job": "7"},
            {"available": True, "indexed": 1775, "updating": True, "job": "9"},
        ]
        index = []

        def read_state(*_args, **_kwargs):
            index.append(len(index))
            return states[min(len(index) - 1, len(states) - 1)]

        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", side_effect=read_state), \
             mock.patch("playback.mpd_client.time.sleep"), \
             mock.patch("playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1, 0.2, 0.3]):
            result = mpd_update_and_wait(path="未整理/春野", timeout=30.0, poll=0.2)
        self.assertTrue(result["updated"])
        self.assertEqual(result["job"], "7")

    def test_an_older_running_job_is_not_mistaken_for_our_finished_job(self):
        """The measured failure: MPD answers "7", but status still shows job "4".

        R189 compared the ids as text and called ``4 != 7`` proof that the scan
        it had just queued was over.  Measured on the fnOS host the two numbers
        are MPD's own queue positions, so job 4 means an *older* scan still owns
        MPD and ours has not started -- the ten-minute convergence was reported
        as finished inside two seconds, and the retry re-issued the same
        ``addid`` that failed.
        """
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        idle = {"available": True, "indexed": 23483, "updating": True, "job": "4"}
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", return_value=idle), \
             mock.patch("playback.mpd_client.time.sleep"), \
             mock.patch("playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1, 0.2, 0.3, 0.4]):
            result = mpd_update_and_wait(path="未整理/春野", timeout=0.3, poll=0.2)
        self.assertFalse(result["updated"])
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["absent"])
        self.assertEqual(result["job"], "7")
        self.assertIn("still running", result["message"])


    def test_an_older_running_job_is_not_credited_as_our_own_scan(self):
        """Seeing *some* scan is not evidence that ours began.

        Measured on the fnOS host: ``update`` answered job "7" while an older job
        "4" still owned the database.  If that sighting is stored as "our scan
        ran", the very next idle read settles the wait and the ten-minute
        convergence is called finished in seconds -- the R189 mistake again.
        """
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        states = [
            {"available": True, "indexed": 23483, "updating": True, "job": "4"},
            {"available": True, "indexed": 23483, "updating": True, "job": "4"},
            {"available": True, "indexed": 23483, "updating": False, "job": ""},
            {"available": True, "indexed": 23483, "updating": False, "job": ""},
        ]
        reads = []

        def read_state(*_args, **_kwargs):
            reads.append(len(reads))
            return states[min(len(reads) - 1, len(states) - 1)]

        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", side_effect=read_state), \
             mock.patch("playback.mpd_client.time.sleep"), \
             mock.patch("playback.mpd_client.time.monotonic",
                        side_effect=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]):
            result = mpd_update_and_wait(path="未整理/春野", timeout=30.0, poll=0.2)
        # ``reads[0]`` is the baseline taken before ``update``.  Settling on the
        # first idle read means the older job was credited as ours, so the wait
        # has to survive to the second consecutive idle read.
        self.assertGreaterEqual(len(reads), 4)
        self.assertTrue(result["updated"])
        self.assertEqual(result["job"], "7")



    def test_the_song_resolving_is_what_settles_a_verified_wait(self):
        """``verify_uri`` is answered by MPD's own resolver, not by counters."""
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        busy = {"available": True, "indexed": 23483, "updating": True, "job": "7"}
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", return_value=busy), \
             mock.patch("playback.mpd_client.mpd_uri_indexed", side_effect=[False, True]) as indexed, \
             mock.patch("playback.mpd_client.time.sleep"), \
             mock.patch("playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1, 0.2, 0.3]):
            result = mpd_update_and_wait(
                path="未整理/春野", timeout=30.0, poll=0.2, verify_uri="未整理/春野/a b.flac"
            )
        self.assertTrue(result["updated"])
        self.assertTrue(result["resolved"])
        self.assertFalse(result["absent"])
        self.assertFalse(result["timed_out"])
        indexed.assert_called_with("未整理/春野/a b.flac", "127.0.0.1", 56660)

    def test_a_folder_refresh_that_leaves_the_song_unresolved_reports_absent(self):
        """The measured no-op: the folder update finished and the song is still gone.

        A directory MPD has never mounted answers ``updating_db`` and then does
        nothing, so "our job is past" plus "still unresolvable" must not be
        reported as a refresh that worked -- it is the signal to converge the
        whole library.
        """
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        states = [
            {"available": True, "indexed": 23483, "updating": True, "job": "7"},
            {"available": True, "indexed": 23483, "updating": True, "job": ""},
        ]
        index = []

        def read_state(*_args, **_kwargs):
            index.append(len(index))
            return states[min(len(index) - 1, len(states) - 1)]

        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", side_effect=read_state), \
             mock.patch("playback.mpd_client.mpd_uri_indexed", return_value=False), \
             mock.patch("playback.mpd_client.time.sleep"), \
             mock.patch("playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1, 0.2, 0.3]):
            result = mpd_update_and_wait(
                path="未整理/新专辑", timeout=30.0, poll=0.2, verify_uri="未整理/新专辑/a.flac"
            )
        self.assertFalse(result["updated"])
        self.assertTrue(result["absent"])
        self.assertFalse(result["timed_out"])
        self.assertIn("cannot resolve", result["message"])

    def test_a_verified_wait_that_never_clears_still_reports_a_timeout(self):
        """``absent`` is only for a refresh that proved over, never for a wait cut short."""
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.return_value = ["updating_db: 7"]
        busy = {"available": True, "indexed": 23483, "updating": True, "job": "7"}
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.mpd_library_state", return_value=busy), \
             mock.patch("playback.mpd_client.mpd_uri_indexed", return_value=False), \
             mock.patch("playback.mpd_client.time.sleep"), \
             mock.patch("playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1, 0.2, 0.3, 0.4]):
            result = mpd_update_and_wait(
                path="未整理/新专辑", timeout=0.3, poll=0.2, verify_uri="未整理/新专辑/a.flac"
            )
        self.assertFalse(result["updated"])
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["absent"])


class MpdLibraryStateTests(unittest.TestCase):
    def test_state_reports_indexed_songs_and_rebuild_flag(self):
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.side_effect = [
            ["state: stop", "updating_db: 1"],
            ["artists: 2926", "songs: 23751"],
        ]
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection):
            self.assertEqual(
                mpd_library_state(),
                {"available": True, "indexed": 23751, "updating": True, "job": "1"},
            )

    def test_state_stays_quiet_when_mpd_does_not_answer(self):
        connection = mock.MagicMock()
        connection.__enter__.return_value.command.side_effect = MpdError("connection closed")
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection):
            self.assertEqual(
                mpd_library_state(), {"available": False, "indexed": 0, "updating": False, "job": ""}
            )

    def test_message_distinguishes_a_cold_database_from_a_missing_file(self):
        self.assertIn("MPD 索引仍在建立中，当前已收录 23751 首", mpd_library_state_message(
            {"available": True, "indexed": 23751, "updating": True}))
        self.assertIn("MPD 索引已完成，当前收录 62684 首", mpd_library_state_message(
            {"available": True, "indexed": 62684, "updating": False}))
        self.assertIn("不可读取", mpd_library_state_message({"available": False}))
        self.assertIn("不可读取", mpd_library_state_message(None))

    def test_message_uses_a_third_sentence_while_a_catchup_is_queued(self):
        """A database that is merely behind must not be reported as "file missing"."""
        idle = mpd_library_state_message({"available": True, "indexed": 23483, "updating": False}, True)
        self.assertIn("MPD 索引落后于 fnAudio 曲库，当前已收录 23483 首", idle)
        self.assertIn("已请求 MPD 收录整个曲库", idle)
        self.assertNotIn("请确认文件仍存在", idle)
        busy = mpd_library_state_message({"available": True, "indexed": 1775, "updating": True}, True)
        self.assertIn("MPD 索引仍在建立中，当前已收录 1775 首", busy)
        self.assertIn("已请求 MPD 收录整个曲库", busy)

    def test_a_queued_catchup_promises_the_measured_wait(self):
        """The owner waited on "please wait for the scan" with no end in sight.

        Measured on the fnOS host the whole-library scan this sentence promises
        commits in 580 seconds, so the pending sentences say that out loud.
        """
        pending_idle = mpd_library_state_message(
            {"available": True, "indexed": 23483, "updating": False}, True
        )
        pending_busy = mpd_library_state_message(
            {"available": True, "indexed": 1775, "updating": True}, True
        )
        for sentence in (pending_idle, pending_busy):
            self.assertIn("本机实测全库收录约需十分钟", sentence)
            self.assertIn("请等待收录完成后重试播放", sentence)
        # An unprompted scan is not ours to promise a duration for.
        self.assertNotIn(
            "十分钟", mpd_library_state_message({"available": True, "indexed": 1775, "updating": True})
        )


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


# Measured on the fnOS host against MPD 0.23.5.  ``mpd_replace_queue`` sends
# ``clear`` first, so command-list slots start counting at the first ``addid``:
# the entry at queue position 0 answers ``ACK [50@1]``, position 1 answers
# ``ACK [50@2]``, and a standalone ``addid`` answers ``ACK [50@0]``.
ACK_AT_1 = "ACK [50@1] {addid} No such song"
ACK_AT_2 = "ACK [50@2] {addid} No such song"
ACK_AT_0 = "ACK [50@0] {addid} No such song"
QUEUE_ENTRIES = [
    {"track_id": "a", "uri": "新专辑/未命名 1.flac"},
    {"track_id": "b", "uri": "旧专辑/曲目 2.flac"},
]


class MpdAckRoutingTests(unittest.TestCase):
    """The ``@N`` in an ACK is a command-list slot, and it has to name the entry."""

    def test_index_one_blames_the_first_queue_entry_not_the_current_track(self):
        self.assertEqual(mpd_addid_failure_uri(QUEUE_ENTRIES, ACK_AT_1), "新专辑/未命名 1.flac")

    def test_index_two_blames_the_second_queue_entry(self):
        self.assertEqual(mpd_addid_failure_uri(QUEUE_ENTRIES, ACK_AT_2), "旧专辑/曲目 2.flac")

    def test_a_standalone_addid_names_no_entry(self):
        self.assertEqual(mpd_addid_failure_uri(QUEUE_ENTRIES, ACK_AT_0), "")

    def test_only_addid_and_an_in_range_slot_names_no_entry(self):
        self.assertEqual(mpd_addid_failure_uri(QUEUE_ENTRIES, "ACK [50@1] {playid} No such song ID"), "")
        self.assertEqual(mpd_addid_failure_uri(QUEUE_ENTRIES, "ACK [50@3] {addid} No such song"), "")
        self.assertEqual(mpd_addid_failure_uri(QUEUE_ENTRIES, "ACK [2@0] {update} Malformed path"), "")

    def test_replace_queue_keeps_the_ack_and_adds_the_blamed_uri(self):
        class RejectingConnection:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def command_list_ok(self, commands):
                self.commands = list(commands)
                raise MpdError(ACK_AT_1)

        fake = RejectingConnection()
        with mock.patch("playback.mpd_client.MpdConnection", return_value=fake):
            with self.assertRaises(MpdQueueEntryError) as caught:
                mpd_replace_queue(QUEUE_ENTRIES)
        self.assertEqual(caught.exception.uri, "新专辑/未命名 1.flac")
        # The classifier reads the protocol sentence, so it must survive intact.
        self.assertEqual(str(caught.exception), ACK_AT_1)
        self.assertIsInstance(caught.exception, MpdError)


class MpdQueueRefreshRoutingTests(unittest.TestCase):
    """A queue failure refreshes what MPD blamed, not what the user pressed."""

    @staticmethod
    def _output(service):
        output = MpdOutput(service)
        output.start_service = mock.Mock(return_value={"ok": True, "running": True})
        output._output_ready = mock.Mock(return_value={"ok": True})
        return output

    @staticmethod
    def _state(path):
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        track = TrackRef.from_mapping({"id": "cur", "path": path})
        state.queue = [track]
        state.current_track_id = "cur"
        return state, track

    def test_the_retry_refreshes_the_folder_mpd_blamed(self):
        class QueueService:
            host = "127.0.0.1"
            port = 56660

            def __init__(self):
                self.sync_calls = 0

            def prepare_track_output(self, _item):
                return {"ok": True}

            def uri_for_path(self, _path):
                return "当前播放/曲目.flac"

            def sync_playback_queue(self, *_args, **_kwargs):
                self.sync_calls += 1
                if self.sync_calls == 1:
                    raise MpdQueueEntryError(ACK_AT_1, "新专辑/未命名 1.flac")
                return {"ok": True}

        service = QueueService()
        output = self._output(service)
        state, track = self._state("/vol2/1000/music/当前播放/曲目.flac")
        with mock.patch("playback.mpd_output.mpd_update_and_wait",
                        return_value={"ok": True, "updated": True, "scope": "新专辑"}) as update, \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 63546, "updating": False}):
            result = output.open(track, state, {"item": track.item})
        self.assertTrue(result["ok"])
        self.assertEqual(service.sync_calls, 2)
        # Discriminating: the previous code refreshed 当前播放, the folder that
        # MPD never complained about, and retried the identical failure.
        self.assertEqual(update.call_args.kwargs["path"], "新专辑")
        self.assertEqual(result["mpd_refreshed_folders"], ["新专辑"])

    def test_a_queue_of_unindexed_albums_stops_after_two_folders(self):
        blamed = ["专辑一/曲 1.flac", "专辑二/曲 2.flac", "专辑三/曲 3.flac"]

        class QueueService:
            host = "127.0.0.1"
            port = 56660

            def __init__(self):
                self.sync_calls = 0

            def prepare_track_output(self, _item):
                return {"ok": True}

            def uri_for_path(self, _path):
                return "当前播放/曲目.flac"

            def sync_playback_queue(self, *_args, **_kwargs):
                uri = blamed[min(self.sync_calls, len(blamed) - 1)]
                self.sync_calls += 1
                raise MpdQueueEntryError(ACK_AT_1, uri)

        service = QueueService()
        output = self._output(service)
        state, track = self._state("/vol2/1000/music/当前播放/曲目.flac")
        with mock.patch("playback.mpd_output.mpd_update_and_wait",
                        return_value={"ok": True, "updated": False, "scope": "专辑二"}) as update, \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 63546, "updating": True}):
            result = output.open(track, state, {"item": track.item})
        self.assertFalse(result["ok"])
        self.assertEqual([call.kwargs["path"] for call in update.call_args_list], ["专辑一", "专辑二"])
        self.assertEqual(service.sync_calls, 3)
        self.assertIn("已请求 MPD 收录 专辑二 后重试仍失败", result["message"])

    def test_an_unrelated_mpd_error_never_triggers_a_library_update(self):
        class QueueService:
            host = "127.0.0.1"
            port = 56660

            def prepare_track_output(self, _item):
                return {"ok": True}

            def uri_for_path(self, _path):
                return "当前播放/曲目.flac"

            def sync_playback_queue(self, *_args, **_kwargs):
                raise MpdError("ACK [2@0] {update} Malformed path")

        output = self._output(QueueService())
        state, track = self._state("/vol2/1000/music/当前播放/曲目.flac")
        with mock.patch("playback.mpd_output.mpd_update_and_wait") as update, \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 63546, "updating": False}):
            result = output.open(track, state, {"item": track.item})
        self.assertFalse(result["ok"])
        update.assert_not_called()
        self.assertIn("Malformed path", result["message"])


class MpdFailureMessageOrderTests(unittest.TestCase):
    """A toast that starts with a protocol line is read as "playback is broken"."""

    def test_the_single_track_message_leads_with_the_actionable_sentence(self):
        output = MpdOutput()
        with mock.patch("playback.mpd_output.mpd_load_uri",
                        side_effect=[MpdError(ACK_AT_0), MpdError(ACK_AT_0)]), \
             mock.patch("playback.mpd_output.mpd_update_and_wait",
                        return_value={"ok": True, "updated": False, "scope": "未整理/春野"}), \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 23751, "updating": True}):
            with self.assertRaises(MpdError) as caught:
                output._load_uri_with_retry("未整理/春野/a b.flac", 0.0)
        message = str(caught.exception)
        self.assertEqual(
            message.split("；")[0],
            mpd_library_state_message({"available": True, "indexed": 23751, "updating": True}),
        )
        self.assertLess(message.index("MPD 索引"), message.index(ACK_AT_0))
        self.assertIn("uri=未整理/春野/a b.flac", message)
        self.assertIn(ACK_AT_0, message)

    def test_a_finished_refresh_that_timed_out_says_the_scan_is_not_done(self):
        output = MpdOutput()
        with mock.patch("playback.mpd_output.mpd_load_uri",
                        side_effect=[MpdError(ACK_AT_0), MpdError(ACK_AT_0)]), \
             mock.patch("playback.mpd_output.mpd_update_and_wait",
                        return_value={"ok": True, "updated": False, "timed_out": True,
                                      "scope": "未整理/春野"}), \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 1775, "updating": True}):
            with self.assertRaises(MpdError) as caught:
                output._load_uri_with_retry("未整理/春野/a b.flac", 0.0)
        self.assertIn("已请求 MPD 收录 未整理/春野（尚未完成）后重试仍失败", str(caught.exception))

    def test_the_queue_message_leads_with_the_finished_index_sentence(self):
        class QueueService:
            host = "127.0.0.1"
            port = 56660

            def __init__(self):
                self.sync_calls = 0

            def prepare_track_output(self, _item):
                return {"ok": True}

            def uri_for_path(self, _path):
                return "新专辑/未命名 1.flac"

            def sync_playback_queue(self, *_args, **_kwargs):
                self.sync_calls += 1
                raise MpdError(ACK_AT_1)

        service = QueueService()
        output = MpdQueueRefreshRoutingTests._output(service)
        state, track = MpdQueueRefreshRoutingTests._state("/vol2/1000/music/新专辑/未命名 1.flac")
        with mock.patch("playback.mpd_output.mpd_update_and_wait",
                        return_value={"ok": True, "updated": True, "scope": "新专辑"}), \
             mock.patch("playback.mpd_output.mpd_library_state",
                        return_value={"available": True, "indexed": 63546, "updating": False}):
            result = output.open(track, state, {"item": track.item})
        message = result["message"]
        self.assertTrue(
            message.startswith(
                "MPD 播放失败：MPD 索引已完成，当前收录 63546 首，"
                "请确认文件仍存在且位于曲库根目录内"
            ),
            message,
        )
        # The report the owner pasted started with the protocol sentence.
        self.assertFalse(message.startswith("MPD 播放失败：ACK"))
        self.assertIn("已请求 MPD 收录 新专辑 后重试仍失败", message)
        self.assertLess(message.index("MPD 索引已完成"), message.index(ACK_AT_1))


class MpdUriIndexProbeTests(unittest.TestCase):
    """``mpd_uri_indexed`` asks MPD the one question playback cares about."""

    RELATIVE = "未整理/HIRES/索尼精选HIRES/DSD/自然/【SONY·DSD】天地的回声(2.8MHz DSD)/A201911231818249.dsf"

    def _probe(self, reply=None, error=None):
        from playback.mpd_client import mpd_uri_indexed

        connection = mock.MagicMock()
        handle = connection.__enter__.return_value
        if error is not None:
            handle.command.side_effect = error
        else:
            handle.command.return_value = reply
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection):
            return mpd_uri_indexed(self.RELATIVE), handle

    def test_the_exact_uri_and_a_listed_entry_both_count_as_indexed(self):
        # MPD 0.23.5 lists the very file it will resolve for ``addid``.
        hit, handle = self._probe(reply=["file: " + self.RELATIVE])
        self.assertTrue(hit)
        self.assertEqual(handle.command.call_args.args[0], "listall")
        self.assertEqual(
            handle.command.call_args.args[1], self.RELATIVE.rsplit("/", 1)[0]
        )
        # An entry named by the same file name is the same fact for this caller.
        hit2, _ = self._probe(reply=["file: 未整理/HIRES/其他/A201911231818249.dsf"])
        self.assertTrue(hit2)

    def test_a_folder_mpd_has_never_mounted_is_reported_as_absent(self):
        """``No such directory`` is the measured reply for the album in the report."""
        miss, _ = self._probe(reply=["ACK [50@0] {listall} No such directory"])
        self.assertFalse(miss)
        other, _ = self._probe(reply=["file: 未整理/HIRES/别的曲目.flac"])
        self.assertFalse(other)

    def test_a_socket_that_does_not_answer_is_not_indexed(self):
        broken, _ = self._probe(error=MpdError("connection closed"))
        self.assertFalse(broken)

    def test_a_uri_mpd_cannot_be_asked_about_is_refused_without_a_command(self):
        from playback.mpd_client import mpd_uri_indexed

        connection = mock.MagicMock()
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection):
            self.assertFalse(mpd_uri_indexed("file:///vol2/1000/music/a.flac"))
            self.assertFalse(mpd_uri_indexed("a.flac"))
            self.assertFalse(mpd_uri_indexed(""))
        connection.__enter__.assert_not_called()


class MpdIndexVerificationWiringTests(unittest.TestCase):
    """Every refresh that precedes an ``addid`` has to verify the song it needs."""

    def _source(self, relative):
        import io
        import os

        path = os.path.join(os.path.dirname(__file__), "..", "app", "server", relative)
        with io.open(path, encoding="utf-8-sig") as handle:
            return handle.read()

    def test_both_playback_refreshes_verify_the_blamed_uri(self):
        source = self._source("playback/mpd_output.py")
        self.assertEqual(source.count("update = mpd_update_and_wait("), 2)
        self.assertEqual(source.count("verify_uri=uri"), 2)

    def test_the_generated_transcode_refresh_verifies_the_generated_uri(self):
        source = self._source("services/mpd_service.py")
        self.assertIn("path=hint, verify_uri=verify", source)


