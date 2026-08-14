import sys
import threading
import time
import unittest

sys.path.insert(0, "app/server")

from playback.core import PlaybackCore
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


class PlaybackCoreStateTests(unittest.TestCase):
    def test_failed_load_does_not_publish_optimistic_playing_state(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput(), FailingOutput()]))
        core.set_target("failing", "failing")
        track = TrackRef.from_mapping({"id": "track-1", "title": "Track 1", "duration": 12})

        result = core.dispatch(PlaybackCommand("load", track=track, context={"item": track.item}))

        self.assertFalse(result["state"]["playing"])
        self.assertEqual(result["state"]["error"], "output rejected track")

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

        self.assertTrue(result["ok"])
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

    if __name__ == "__main__":
        unittest.main()
