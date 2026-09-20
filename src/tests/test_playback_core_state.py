import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.core import MAX_QUEUE_TRACKS, PlaybackCore
from playback.models import PlaybackCommand, TrackRef
from playback.plugins import BrowserOutput, OutputPlugin, OutputRegistry


class FailingOutput(OutputPlugin):
    plugin_id = "failing"
    target_kind = "failing"

    def open(self, track, state, context=None):
        return {"ok": False, "message": "output rejected track"}

    def command(self, command, state, context=None):
        return {"ok": False, "message": "output rejected command"}

    def close(self, state):
        return None

    def capabilities(self):
        return {}


class MalformedOutput(FailingOutput):
    plugin_id = "malformed"
    target_kind = "malformed"

    def open(self, track, state, context=None):
        return {"ok": "false", "message": "malformed response"}

    def command(self, command, state, context=None):
        return None


class PlaybackCoreStateTests(unittest.TestCase):
    def test_session_identity_is_part_of_authoritative_snapshot(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_session_identity(9, 4, "ticket-abc")
        snapshot = core.snapshot()
        self.assertEqual(snapshot["generation"], 9)
        self.assertEqual(snapshot["engine_epoch"], 4)
        self.assertEqual(snapshot["command_ticket"], "ticket-abc")

    def test_session_identity_changes_publish_one_state_event(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        before = core.state.state_version
        core.set_session_identity(1, 2, "ticket")
        self.assertEqual(core.state.state_version, before + 1)
        core.set_session_identity(1, 2, "ticket")
        self.assertEqual(core.state.state_version, before + 1)

    def test_failed_load_does_not_publish_optimistic_playing_state(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput(), FailingOutput()]))
        core.set_target("failing", "failing")
        track = TrackRef.from_mapping({"id": "track-1", "title": "Track 1", "duration": 12})

        result = core.dispatch(PlaybackCommand("load", track=track, context={"item": track.item}))

        self.assertFalse(result["state"]["playing"])
        self.assertEqual(result["state"]["error"], "output rejected track")

    def test_malformed_plugin_results_do_not_commit_state(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput(), MalformedOutput()]))
        core.set_target("malformed", "malformed")
        track = TrackRef.from_mapping({"id": "track-1", "title": "Track 1", "duration": 12})

        result = core.dispatch(PlaybackCommand("load", track=track, context={"item": track.item}))

        self.assertFalse(result["ok"])
        self.assertFalse(result["state"]["playing"])
        self.assertEqual(result["state"]["error"], "malformed response")

        result = core.dispatch(PlaybackCommand("stop"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"]["error"], "output returned an invalid response")

    def test_async_status_updates_only_the_selected_backend(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput(), FailingOutput()]))
        core.set_target("failing", "failing")

        core.sync_output_status("mpd", "PLAYING", 5, 10)
        self.assertFalse(core.state.playing)

        core.sync_output_status("failing", "PLAYING", 5, 10)
        self.assertTrue(core.state.playing)
        self.assertEqual(core.state.transport, "PLAYING")
        self.assertEqual(core.state.position, 5)
        self.assertGreater(core.state.state_version, 0)

    def test_duplicate_output_status_does_not_publish_a_new_event(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput(), FailingOutput()]))
        core.set_target("failing", "failing")
        core.sync_output_status("failing", "STOPPED", 0, 0)
        version = core.state.state_version

        core.sync_output_status("failing", "STOPPED", 0, 0)

        self.assertEqual(core.state.state_version, version)

    def test_async_output_status_rejects_nonfinite_position_and_duration(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.sync_output_status("browser", "PLAYING", float("inf"), float("nan"))
        self.assertEqual(core.state.position, 0.0)
        self.assertEqual(core.state.duration, 0.0)

    def test_external_session_rejects_nonfinite_position_and_duration(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.sync_external_session("source", "Title", "http://example/track", "PLAYING", float("inf"), float("nan"))
        self.assertEqual(core.state.position, 0.0)
        self.assertEqual(core.state.duration, 0.0)

    def test_external_session_publishes_transport_and_does_not_coerce_untrusted_text(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("external session must not stringify objects")

        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.sync_external_session(Explosive(), Explosive(), "http://example/track", "PAUSED_PLAYBACK", error=Explosive())

        self.assertEqual(core.state.transport, "PAUSED_PLAYBACK")
        self.assertFalse(core.state.playing)
        self.assertEqual(core.state.current_track_id, "external:input")
        self.assertEqual(core.state.queue[0].title, "")
        self.assertEqual(core.state.error, "")

    def test_load_adds_track_missing_from_frontend_queue(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        track = TrackRef.from_mapping({"id": "library-click", "title": "Library click", "duration": 12})

        result = core.dispatch(PlaybackCommand("load", track=track, context={"item": track.item}))

        self.assertTrue(result["state"]["playing"])
        self.assertEqual(result["state"]["queue"], ["library-click"])
        self.assertEqual(result["state"]["current_index"], 0)

    def test_load_preserves_existing_queue_when_selecting_another_track(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue([
            {"id": "first", "title": "First", "duration": 10},
            {"id": "second", "title": "Second", "duration": 20},
        ], "first")
        result = core.dispatch(PlaybackCommand(
            "load",
            track=TrackRef.from_mapping({"id": "second", "title": "Second", "duration": 20}),
            context={"item": {"id": "second", "title": "Second", "duration": 20}},
        ))
        self.assertEqual(result["state"]["queue"], ["first", "second"])
        self.assertEqual(result["state"]["current"], "second")
        self.assertEqual(result["state"]["current_index"], 1)

    def test_load_preserves_the_requested_start_position(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        track = TrackRef.from_mapping({"id": "track-1", "title": "Track 1", "duration": 60})

        result = core.dispatch(PlaybackCommand("load", 12.5, track, {"item": track.item}))

        self.assertEqual(result["state"]["position"], 12.5)

    def test_next_resolver_cannot_replace_queue_track_identity(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue([
            {"id": "first", "title": "First"},
            {"id": "second", "title": "Second", "duration": 20},
        ], "first")

        result = core.dispatch(PlaybackCommand(
            "next",
            context={"resolve_track": lambda _track_id: {"id": "different", "title": "Wrong"}},
        ))

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["current"], "second")
        self.assertEqual(result["state"]["current_index"], 1)
        self.assertEqual(result["state"]["duration"], 20.0)

    def test_next_resolver_with_missing_id_keeps_queue_track(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue([
            {"id": "first", "title": "First"},
            {"id": "second", "title": "Second", "duration": 20},
        ], "first")

        result = core.dispatch(PlaybackCommand(
            "next",
            context={"resolve_track": lambda _track_id: {"title": "No identity"}},
        ))

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["current"], "second")
        self.assertEqual(result["state"]["duration"], 20.0)

    def test_load_rejects_non_finite_requested_start_position(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        track = TrackRef.from_mapping({"id": "track-1", "title": "Track 1", "duration": 60})

        result = core.dispatch(PlaybackCommand("load", float("nan"), track, {"item": track.item}))

        self.assertEqual(result["state"]["position"], 0.0)

    def test_seek_rejects_non_finite_requested_position(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.state.position = 5.0

        result = core.dispatch(PlaybackCommand("seek", float("inf")))

        self.assertEqual(result["state"]["position"], 0.0)


    def test_failed_load_restores_previous_state(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput(), FailingOutput()]))
        core.set_target("failing", "failing")
        previous = TrackRef.from_mapping({"id": "playing", "title": "Playing", "duration": 42})
        core.state.queue = [previous]
        core.state.current_track_id = "playing"
        core.state.current_index = 0
        core.state.position = 12
        core.state.duration = 42
        core.state.playing = True
        core.state.transport = "PLAYING"
        result = core.dispatch(PlaybackCommand("load", track=TrackRef.from_mapping({"id": "bad", "duration": 10}), context={}))
        self.assertEqual(result["state"]["current"], "playing")
        self.assertEqual(result["state"]["queue"], ["playing"])
        self.assertEqual(result["state"]["position"], 12)
        self.assertTrue(result["state"]["playing"])
        self.assertEqual(result["state"]["transport"], "PLAYING")

    def test_repeat_command_accepts_explicit_remote_target_value(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.state.repeat = "all"
        result = core.dispatch(PlaybackCommand("repeat", context={"repeat_value": "off"}))
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["repeat"], "off")

    def test_repeat_command_cycles_through_all_three_repeat_modes(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))

        self.assertEqual(core.dispatch(PlaybackCommand("repeat"))["state"]["repeat"], "all")
        self.assertEqual(core.dispatch(PlaybackCommand("repeat"))["state"]["repeat"], "one")
        self.assertEqual(core.dispatch(PlaybackCommand("repeat"))["state"]["repeat"], "off")

    def test_failed_repeat_change_restores_the_previous_mode(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput(), FailingOutput()]))
        core.set_target("failing", "mpd")
        core.state.repeat = "all"

        result = core.dispatch(PlaybackCommand("repeat", context={"repeat_value": "one"}))

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"]["repeat"], "all")

    def test_next_track_respects_off_all_and_one_repeat_modes(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue([
            {"id": "first", "title": "First"},
            {"id": "last", "title": "Last"},
        ], "last")

        core.state.repeat = "off"
        self.assertIsNone(core.next_track())
        self.assertEqual(core.state.current_track_id, "last")

        core.state.repeat = "all"
        self.assertEqual(core.next_track().track_id, "first")

        core.state.repeat = "one"
        self.assertEqual(core.next_track().track_id, "first")
        self.assertEqual(core.state.current_track_id, "first")

    def test_shuffle_command_accepts_explicit_remote_target_value(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.state.shuffle = True
        result = core.dispatch(PlaybackCommand("shuffle", context={"shuffle_value": False}))
        self.assertTrue(result["ok"])
        self.assertFalse(result["state"]["shuffle"])

    def test_wait_for_version_wakes_event_consumers_on_state_change(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        before = core.state.state_version
        observed = []
        waiter = threading.Thread(target=lambda: observed.append(core.wait_for_version(before, 1.0)))
        waiter.start()
        time.sleep(0.03)
        core.set_queue([{"id": "event-track", "title": "Event track", "duration": 8}], "event-track")
        waiter.join(timeout=1.0)

        self.assertFalse(waiter.is_alive())
        self.assertEqual(observed, [core.state.state_version])

    def test_wait_for_version_rejects_nonfinite_timeout(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        with mock.patch.object(core._changed, "wait") as wait:
            core.wait_for_version(core.state.state_version, float("nan"))
        wait.assert_called_once_with(15.0)

    def test_set_queue_bounds_large_or_broken_iterables(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue(({"id": str(index), "title": str(index)} for index in range(MAX_QUEUE_TRACKS + 100)))
        self.assertEqual(len(core.state.queue), MAX_QUEUE_TRACKS)

        class Broken:
            def __iter__(self):
                yield {"id": "ok", "title": "OK"}
                raise RuntimeError("broken")

        core.set_queue(Broken())
        self.assertEqual([item.track_id for item in core.state.queue], ["ok"])

    def test_track_projection_rejects_untrusted_fields_and_nonfinite_duration(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("track fields must not stringify arbitrary objects")

        track = TrackRef.from_mapping({
            "id": Explosive(),
            "track_id": "fallback-id",
            "title": Explosive(),
            "format": ["FLAC"],
            "duration": float("nan"),
            "is_dsd": "true",
        })
        self.assertEqual(track.track_id, "fallback-id")
        self.assertEqual(track.title, "")
        self.assertEqual(track.format, "")
        self.assertEqual(track.duration, 0.0)
        self.assertFalse(track.is_dsd)

    def test_queue_skips_malformed_track_refs(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue([
            {"id": object(), "title": "bad"},
            {"id": "valid", "duration": float("inf")},
        ])
        self.assertEqual([track.track_id for track in core.state.queue], ["valid"])
        self.assertEqual(core.state.duration, 0.0)

    def test_load_keeps_queue_within_bound_when_appending_missing_track(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue(({"id": str(index), "title": str(index)} for index in range(MAX_QUEUE_TRACKS)))
        command = PlaybackCommand("load", track=TrackRef.from_mapping({"id": "new", "title": "New"}))
        result = core.dispatch(command)
        self.assertTrue(result["ok"])
        self.assertEqual(len(core.state.queue), MAX_QUEUE_TRACKS)
        self.assertEqual(core.state.queue[-1].track_id, "new")

    def test_sync_frontend_uses_the_same_queue_bound(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        payload = {"queue": [{"id": str(index), "title": str(index)} for index in range(MAX_QUEUE_TRACKS + 1)]}
        core.sync_frontend(payload)
        self.assertEqual(len(core.state.queue), MAX_QUEUE_TRACKS)

    def test_sync_frontend_ignores_broken_payload_fields(self):
        class Broken(dict):
            def get(self, key, default=None):
                if key == "duration":
                    raise RuntimeError("broken duration")
                return super().get(key, default)

        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue([{"id": "safe", "title": "Safe", "duration": 3}], "safe")
        core.sync_frontend(Broken({
            "queue": [{"id": "safe", "title": "Safe", "duration": 3}],
            "current": Broken({"id": "safe", "duration": object()}),
            "repeat": object(),
            "shuffle": object(),
            "playing": object(),
        }))
        self.assertEqual(core.state.current_track_id, "safe")
        self.assertEqual(core.state.duration, 3.0)

    def test_legacy_sync_rejects_explosive_current_and_boolean_values(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("legacy state must not stringify arbitrary objects")

            def __bool__(self):
                raise AssertionError("legacy state must not use arbitrary truthiness")

        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue([{"id": "safe", "title": "Safe"}], "safe", shuffle=False)
        core.sync_frontend({
            "current": Explosive(),
            "shuffle": Explosive(),
            "playing": Explosive(),
        })
        self.assertEqual(core.state.current_track_id, "safe")
        self.assertFalse(core.state.shuffle)
        self.assertFalse(core.state.playing)

        core.set_queue([{"id": "safe", "title": "Safe"}], Explosive(), shuffle=Explosive())
        self.assertEqual(core.state.current_track_id, "safe")
        self.assertFalse(core.state.shuffle)
        self.assertIs(core.select_current(Explosive()), core.state)
    def test_current_item_exposes_the_queue_mapping_that_carries_cue_offsets(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        cue = {"id": "cue-2", "title": "Cue 2", "duration": 30, "cue_track": True, "cue_start": 100.0}
        core.set_queue([{"id": "a", "title": "A", "duration": 10}, cue], "cue-2")
        self.assertEqual(core.state.current_index, 1)
        self.assertEqual(core.current_item().get("cue_start"), 100.0)
        # A stale index must not lose the item: the identity scan still finds it.
        core.state.current_index = 0
        self.assertEqual(core.current_item().get("cue_start"), 100.0)
        core.state.current_index = -1
        self.assertIs(core.current_item().get("cue_track"), True)

    def test_current_item_stays_empty_when_no_track_is_current(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        self.assertEqual(core.current_item(), {})
        core.set_queue([{"id": "a", "title": "A"}], "a")
        core.state.current_track_id = ""
        self.assertEqual(core.current_item(), {})
        core.state.current_track_id = "missing"
        self.assertEqual(core.current_item(), {})

    def test_a_non_mapping_queue_item_is_not_projected(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.state.queue = [TrackRef(track_id="a", item="not-a-mapping")]
        core.state.current_track_id = "a"
        core.state.current_index = 0
        self.assertEqual(core.current_item(), {})

    def test_snapshot_with_item_pairs_one_version_with_its_own_units(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        core.set_queue([{"id": "a", "title": "A", "cue_track": True, "cue_start": 100.0}], "a")
        before = core.state.state_version
        snapshot, item = core.snapshot_with_item()
        self.assertEqual(snapshot["state_version"], before)
        self.assertIn("output", snapshot)
        self.assertEqual(item.get("id"), "a")
        self.assertEqual(item.get("cue_start"), 100.0)
        # Reading must not publish: the version is bumped by mutations only.
        self.assertEqual(core.state.state_version, before)
        snapshot["state_version"] = 99
        self.assertEqual(core.state.state_version, before)

    def test_snapshot_with_item_matches_snapshot_for_an_empty_queue(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        snapshot, item = core.snapshot_with_item()
        self.assertEqual(item, {})
        self.assertEqual(snapshot, core.snapshot())


if __name__ == "__main__":
    unittest.main()
