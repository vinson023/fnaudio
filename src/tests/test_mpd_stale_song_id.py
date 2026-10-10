import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.models import PlaybackState, TrackRef
from playback.mpd_client import (
    MPD_ENTRY_LOOKUP_COMMANDS,
    MPD_SONG_ID_COMMANDS,
    MpdError,
    MpdQueueEntryError,
    mpd_ack_command,
    mpd_is_stale_song_id_error,
)
from playback.mpd_output import MpdOutput
from services.mpd_service import MpdService

# Reproduced twice on the fnOS host 198.51.100.24 while MPD demonstrably held the
# file: fnAudio reused a cached queue id, MPD had already dropped that entry
# after its own ``update``, and the answer was this standalone ``playid`` ACK.
STALE_PLAYID_ACK = "ACK [50@0] {playid} No such song"
STALE_PLAYID_IN_COMMAND_LIST = "ACK [50@1] {playid} No such song"
STALE_SEEKID_ACK = "ACK [50@0] {seekid} No such song"
MISSING_ADDID_ACK = "ACK [50@1] {addid} No such song"
MISSING_STANDALONE_ADDID_ACK = "ACK [50@0] {addid} No such song"
MISSING_ADD_DIR_ACK = "ACK [2@0] {add} Directory or file not found"
UNRELATED_ACK = "ACK [2@0] {update} Malformed path"
NO_SUCH_SONG_WITHOUT_ACK = "No such song"
QUEUE_ENTRIES = [
    {"track_id": "a", "uri": "新专辑/未命名 1.flac"},
    {"track_id": "b", "uri": "旧专辑/曲目 2.flac"},
]


class MpdAckCommandNameTests(unittest.TestCase):
    """The command slot of an ACK is what separates the two ``No such song``s."""

    def test_the_ack_command_name_is_extracted(self):
        self.assertEqual(mpd_ack_command(STALE_PLAYID_ACK), "playid")
        self.assertEqual(mpd_ack_command(MISSING_ADDID_ACK), "addid")

    def test_the_command_name_is_read_even_at_a_command_list_slot(self):
        self.assertEqual(mpd_ack_command(STALE_PLAYID_IN_COMMAND_LIST), "playid")

    def test_an_ack_that_names_no_command_yields_an_empty_name(self):
        self.assertEqual(mpd_ack_command('ACK [5@0] {} unknown command "wait"'), "")

    def test_text_without_an_ack_yields_an_empty_name(self):
        self.assertEqual(mpd_ack_command(NO_SUCH_SONG_WITHOUT_ACK), "")
        self.assertEqual(mpd_ack_command(""), "")
        self.assertEqual(mpd_ack_command(None), "")

    def test_a_library_lookup_and_a_queue_id_are_never_the_same_command(self):
        self.assertFalse(MPD_ENTRY_LOOKUP_COMMANDS & MPD_SONG_ID_COMMANDS)
        self.assertIn("addid", MPD_ENTRY_LOOKUP_COMMANDS)
        self.assertIn("playid", MPD_SONG_ID_COMMANDS)


class MpdStaleSongIdErrorTests(unittest.TestCase):
    def test_playid_refusal_is_a_stale_queue_id(self):
        self.assertTrue(mpd_is_stale_song_id_error(MpdError(STALE_PLAYID_ACK)))

    def test_seekid_refusal_is_a_stale_queue_id(self):
        self.assertTrue(mpd_is_stale_song_id_error(MpdError(STALE_SEEKID_ACK)))

    def test_stale_detection_is_case_insensitive(self):
        self.assertTrue(mpd_is_stale_song_id_error("ACK [50@0] {playid} NO SUCH SONG"))

    def test_addid_refusal_is_not_a_stale_queue_id(self):
        self.assertFalse(mpd_is_stale_song_id_error(MpdError(MISSING_ADDID_ACK)))
        self.assertFalse(mpd_is_stale_song_id_error(MpdError(MISSING_STANDALONE_ADDID_ACK)))

    def test_a_playid_refusal_about_something_else_is_not_a_stale_queue_id(self):
        self.assertFalse(mpd_is_stale_song_id_error("ACK [50@0] {playid} Permission denied"))

    def test_an_unblamed_refusal_is_not_treated_as_a_stale_queue_id(self):
        self.assertFalse(mpd_is_stale_song_id_error(NO_SUCH_SONG_WITHOUT_ACK))
        self.assertFalse(mpd_is_stale_song_id_error(UNRELATED_ACK))
        self.assertFalse(mpd_is_stale_song_id_error(""))


class MpdMissingEntryClassifierTests(unittest.TestCase):
    """Only a refusal to resolve a *uri* may enter the library-refresh path."""

    def test_addid_blames_the_database(self):
        self.assertTrue(MpdOutput._is_missing_mpd_library_entry(MpdError(MISSING_ADDID_ACK)))

    def test_standalone_addid_blames_the_database(self):
        self.assertTrue(
            MpdOutput._is_missing_mpd_library_entry(MpdError(MISSING_STANDALONE_ADDID_ACK))
        )

    def test_add_blames_the_database_for_an_unmounted_directory(self):
        self.assertTrue(MpdOutput._is_missing_mpd_library_entry(MpdError(MISSING_ADD_DIR_ACK)))

    def test_annotated_queue_entry_error_still_blames_the_database(self):
        self.assertTrue(
            MpdOutput._is_missing_mpd_library_entry(
                MpdQueueEntryError(MISSING_ADDID_ACK, QUEUE_ENTRIES[0]["uri"])
            )
        )

    def test_playid_refusal_is_not_a_missing_library_entry(self):
        # Discriminating: before R196 the bare "no such song" substring sent this
        # into the folder-refresh -> whole-library catch-up path and produced the
        # permanent "MPD index lags, wait for the scan" refusal.
        self.assertFalse(MpdOutput._is_missing_mpd_library_entry(MpdError(STALE_PLAYID_ACK)))

    def test_seekid_and_deleteid_refusals_are_not_missing_library_entries(self):
        self.assertFalse(MpdOutput._is_missing_mpd_library_entry(MpdError(STALE_SEEKID_ACK)))
        self.assertFalse(
            MpdOutput._is_missing_mpd_library_entry(
                MpdError("ACK [50@0] {deleteid} No such song")
            )
        )

    def test_an_ack_without_a_command_keeps_the_previous_meaning(self):
        self.assertTrue(
            MpdOutput._is_missing_mpd_library_entry(MpdError(NO_SUCH_SONG_WITHOUT_ACK))
        )

    def test_an_unrelated_ack_is_still_not_a_library_failure(self):
        self.assertFalse(MpdOutput._is_missing_mpd_library_entry(MpdError(UNRELATED_ACK)))


class MpdStaleIdServiceTests(unittest.TestCase):
    """fnAudio owns the queue, so a stale id is rebuilt, not reported."""

    def make_service(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with mock.patch.object(MpdService, "_select_port", return_value=56660), mock.patch.object(
            MpdService, "_find_binary", return_value="/usr/bin/mpd"
        ), mock.patch.object(MpdService, "_data_root", return_value=temp.name):
            service = MpdService({"mpd_port": 56660, "library_path": "/music"}, app_root=temp.name)
        self.addCleanup(service.supervisor.shutdown)
        return service

    @staticmethod
    def _queue():
        return [
            TrackRef.from_mapping({"id": "a", "path": "/music/a.flac"}),
            TrackRef.from_mapping({"id": "b", "path": "/music/b.flac"}),
        ]

    @mock.patch("services.mpd_service.mpd_play_queue_item")
    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_a_stale_id_rebuilds_the_queue_instead_of_refusing_playback(
        self, replace_queue, play_item
    ):
        service = self.make_service()
        replace_queue.side_effect = [
            {"ok": True, "song_ids": {"a": "11", "b": "12"}},
            {"ok": True, "song_ids": {"a": "21", "b": "22"}},
        ]
        play_item.side_effect = [MpdError(STALE_PLAYID_ACK), {"ok": True, "song_id": "22"}]

        service.sync_playback_queue(self._queue(), "a")
        second = service.sync_playback_queue(self._queue(), "b")

        self.assertFalse(second["queue_reused"])
        self.assertEqual(replace_queue.call_count, 2)
        # The stale id is never replayed: the retry is a fresh mirror, not a loop.
        self.assertEqual(play_item.call_count, 1)

    @mock.patch("services.mpd_service.mpd_play_queue_item")
    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_the_rebuilt_ids_replace_the_stale_cache(self, replace_queue, play_item):
        service = self.make_service()
        replace_queue.side_effect = [
            {"ok": True, "song_ids": {"a": "11", "b": "12"}},
            {"ok": True, "song_ids": {"a": "21", "b": "22"}},
        ]
        play_item.side_effect = [MpdError(STALE_PLAYID_ACK), {"ok": True, "song_id": "22"}]

        service.sync_playback_queue(self._queue(), "a")
        service.sync_playback_queue(self._queue(), "b")
        third = service.sync_playback_queue(self._queue(), "b")

        self.assertEqual(service._queue_song_ids, {"a": "21", "b": "22"})
        self.assertTrue(third["queue_reused"])
        self.assertEqual(replace_queue.call_count, 2)
        # A dropped entry must stop resolving to a track id, otherwise a late
        # MPD status could still be mapped onto a song that is gone.
        self.assertEqual(service.track_id_for_status({"status": {"song": {"Id": "12"}}}), "")
        self.assertEqual(service.track_id_for_status({"status": {"song": {"Id": "22"}}}), "b")

    @mock.patch("services.mpd_service.mpd_play_queue_item")
    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_a_non_stale_refusal_is_not_swallowed_by_the_recovery(self, replace_queue, play_item):
        service = self.make_service()
        replace_queue.return_value = {"ok": True, "song_ids": {"a": "11", "b": "12"}}
        # The reuse path is the only caller of playid here, so the refusal below
        # cannot be an unconsumed first element of a side_effect list.
        play_item.side_effect = MpdError("ACK [50@0] {playid} Permission denied")

        service.sync_playback_queue(self._queue(), "a")
        with self.assertRaises(MpdError) as caught:
            service.sync_playback_queue(self._queue(), "b")

        self.assertIn("Permission denied", str(caught.exception))
        self.assertEqual(replace_queue.call_count, 1)

    @mock.patch("services.mpd_service.mpd_play_queue_item")
    @mock.patch("services.mpd_service.mpd_replace_queue")
    def test_a_genuine_missing_entry_still_surfaces_with_the_blamed_uri(
        self, replace_queue, play_item
    ):
        service = self.make_service()
        replace_queue.side_effect = [
            {"ok": True, "song_ids": {"a": "11", "b": "12"}},
            MpdQueueEntryError(MISSING_ADDID_ACK, QUEUE_ENTRIES[0]["uri"]),
        ]
        play_item.side_effect = MpdError(STALE_PLAYID_ACK)

        service.sync_playback_queue(self._queue(), "a")
        with self.assertRaises(MpdQueueEntryError) as caught:
            service.sync_playback_queue(self._queue(), "b")

        self.assertEqual(caught.exception.uri, QUEUE_ENTRIES[0]["uri"])
        self.assertTrue(MpdOutput._is_missing_mpd_library_entry(caught.exception))
        # The rebuild failed, so nothing MPD was asked to hold is known any more:
        # a stale id must not be advertised as preloaded nor mapped back to a
        # track id, or the next status poll would name a song MPD dropped.
        self.assertFalse(service.preload_status("b")["preloaded"])
        self.assertEqual(service._queue_current_track_id, "")
        self.assertEqual(service.track_id_for_status({"status": {"song": {"Id": "12"}}}), "")
        # And the queue must not be treated as reusable afterwards.
        replace_queue.side_effect = None
        replace_queue.return_value = {"ok": True, "song_ids": {"a": "31", "b": "32"}}
        retry = service.sync_playback_queue(self._queue(), "b")
        self.assertFalse(retry["queue_reused"])
        self.assertEqual(replace_queue.call_count, 3)


class MpdStaleIdOutputTests(unittest.TestCase):
    """Defense in depth: a stale id must never reach the index-lag sentence."""

    @staticmethod
    def _output(service):
        output = MpdOutput(service)
        output.start_service = mock.Mock(return_value={"ok": True, "running": True})
        output._output_ready = mock.Mock(return_value={"ok": True})
        return output

    @staticmethod
    def _state():
        state = PlaybackState(target_id="mpd", target_kind="mpd")
        track = TrackRef.from_mapping({"id": "cur", "path": "/vol2/1000/music/当前播放/曲目.flac"})
        state.queue = [track]
        state.current_track_id = "cur"
        return state, track

    class QueueService:
        host = "127.0.0.1"
        port = 56660

        def __init__(self):
            self.catchup_calls = 0

        def prepare_track_output(self, _item):
            return {"ok": True}

        def uri_for_path(self, _path):
            return "当前播放/曲目.flac"

        def request_index_catchup(self, *_args, **_kwargs):
            self.catchup_calls += 1
            return {"accepted": True}

        def index_status(self):
            return {"running": False}

        def sync_playback_queue(self, *_args, **_kwargs):
            raise MpdError(STALE_PLAYID_ACK)

    def test_a_stale_id_refusal_refreshes_no_folder(self):
        service = self.QueueService()
        output = self._output(service)
        state, track = self._state()
        with mock.patch("playback.mpd_output.mpd_update_and_wait") as update, \
             mock.patch("playback.mpd_output.mpd_library_state") as library_state:
            result = output.open(track, state, {"item": track.item})

        self.assertFalse(result["ok"])
        update.assert_not_called()
        library_state.assert_not_called()
        self.assertEqual(service.catchup_calls, 0)
        self.assertNotIn("索引落后", result["message"])
        self.assertIn(STALE_PLAYID_ACK, result["message"])


class MpdStaleIdWiringTests(unittest.TestCase):
    """Source-level guards: the fix has to stay wired into both callers."""

    def _source(self, relative):
        path = os.path.join(os.path.dirname(__file__), "..", "app", "server", *relative.split("/"))
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_the_service_uses_the_stale_predicate_on_the_reuse_path(self):
        source = self._source("services/mpd_service.py")
        self.assertIn("mpd_is_stale_song_id_error(exc)", source)
        reuse = source[source.index("if selected_song_id and play:"):]
        reuse = reuse[:reuse.index("result = mpd_replace_queue(")]
        self.assertIn("except MpdError as exc:", reuse)
        self.assertIn("raise", reuse)
        # A blanket catch would hide real MPD faults behind a queue rebuild.
        self.assertNotIn("except Exception", reuse)

    def test_the_classifier_gates_on_the_ack_command_name(self):
        source = self._source("playback/mpd_output.py")
        start = source.index("def _is_missing_mpd_library_entry")
        tail = source[start + len("def "):]
        classifier = tail[:tail.index("\ndef ")]
        self.assertIn("mpd_ack_command", classifier)
        self.assertIn("MPD_ENTRY_LOOKUP_COMMANDS", classifier)
        self.assertIn("no such song", classifier)

    def test_the_output_module_still_imports_the_predicates_it_uses(self):
        source = self._source("playback/mpd_output.py")
        self.assertIn("    mpd_ack_command,\n", source)
        self.assertIn("    MPD_ENTRY_LOOKUP_COMMANDS,\n", source)


if __name__ == "__main__":
    unittest.main()