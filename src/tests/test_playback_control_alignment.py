import sys
import unittest

sys.path.insert(0, "app/server")

from playback.core import PlaybackCore
from playback.http_contract import control_track_alignment
from playback.models import PlaybackCommand
from playback.plugins import BrowserOutput, OutputRegistry


QUEUE = ["a", "b", "c"]


class ControlTrackAlignmentTests(unittest.TestCase):
    def test_browser_target_steps_from_the_track_the_client_reports(self):
        # The client is playing "b" while the core still sits on "a" (a
        # client-side CUE tail walk or a second window got it there). Stepping
        # from the core's cursor returned "b" for "next" -- the song that was
        # already playing -- and "previous" returned nothing.
        self.assertEqual(control_track_alignment("browser", "next", "b", "a", QUEUE), "b")
        self.assertEqual(control_track_alignment("browser", "next", "c", "a", QUEUE), "c")

    def test_alignment_is_skipped_when_nothing_would_change(self):
        self.assertEqual(control_track_alignment("browser", "next", "a", "a", QUEUE), "")
        self.assertEqual(control_track_alignment("browser", "next", "", "a", QUEUE), "")
        self.assertEqual(control_track_alignment("browser", "next", None, "a", QUEUE), "")

    def test_alignment_requires_a_queue_member(self):
        self.assertEqual(control_track_alignment("browser", "next", "zz", "a", QUEUE), "")
        self.assertEqual(control_track_alignment("browser", "next", "b", "a", None), "")
        self.assertEqual(control_track_alignment("browser", "next", "b", "a", "abc"), "")

    def test_only_relative_transport_commands_align(self):
        for action in ("play", "pause", "stop", "seek", "repeat", "shuffle", "load", ""):
            self.assertEqual(control_track_alignment("browser", action, "b", "a", QUEUE), "", action)
        self.assertEqual(control_track_alignment("browser", None, "b", "a", QUEUE), "")
        self.assertEqual(control_track_alignment("browser", {"action": "next"}, "b", "a", QUEUE), "")

    def test_devices_that_play_on_their_own_keep_the_authority(self):
        # A DAC/DLNA target reports its own position; a client's idea of the
        # current row must not rewind it before the step.
        for kind in ("alsa", "mpd", "dlna_push"):
            self.assertEqual(control_track_alignment(kind, "next", "b", "a", QUEUE), "", kind)

    def test_action_text_is_normalized(self):
        self.assertEqual(control_track_alignment("browser", " NEXT ", "b", "a", QUEUE), "b")
        self.assertEqual(control_track_alignment("browser", "Previous", "b", "a", QUEUE), "b")


class AlignedStepTests(unittest.TestCase):
    """The step that follows an alignment is the neighbour of the audible track."""

    def setUp(self):
        self.core = PlaybackCore(OutputRegistry([BrowserOutput()]))
        self.core.set_queue(
            [{"id": track_id, "title": track_id.upper(), "duration": 10} for track_id in QUEUE],
            current="a",
        )

    def step(self, action):
        result = self.core.dispatch(PlaybackCommand(action, context={}))
        return result["state"]["current"]

    def test_next_after_alignment_lands_on_the_neighbour(self):
        # Without the alignment the core steps a -> b while the listener hears b.
        self.core.select_current("c")
        self.assertEqual(self.step("next"), "c")

    def test_previous_after_alignment_lands_on_the_neighbour(self):
        self.core.select_current("c")
        self.assertEqual(self.step("previous"), "b")

    def test_alignment_is_a_no_op_for_a_foreign_track(self):
        before = self.core.snapshot()
        self.core.select_current("not-in-queue")
        after = self.core.snapshot()
        self.assertEqual(before["current"], after["current"])
        self.assertEqual(before["current_index"], after["current_index"])


if __name__ == "__main__":
    unittest.main()
