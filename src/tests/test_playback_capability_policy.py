"""R587: what the server tells a client about its own playback limits.

Two facts are worth guarding here:

* the numbers are *stated* rather than guessed, so a client that never asks keeps
  the old behaviour instead of inventing a cap;
* the remote queue cap in this file and the one in ``PlaybackService.java`` are
  the same number.  When they drifted, the Android remote snapshot cut the queue
  at 500 rows and the listener was never told -- the truncation was the bug, not
  the cap.

``progress`` is checked here too: it is the other half of the position loop (the
client reports, the server stores, a reload resumes), and the point of the
command is that it must *not* reach an output plugin.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, "app/server")

import playback_capability_policy as policy
from playback.core import MAX_QUEUE_TRACKS, PlaybackCore
from playback.models import PlaybackCommand
from playback.plugins import OutputPlugin, OutputRegistry

ROOT = Path(__file__).resolve().parent.parent
ANDROID_PLAYBACK_SERVICE = (
    ROOT.parent
    / "android-client"
    / "app"
    / "src"
    / "main"
    / "java"
    / "com"
    / "fnaudio"
    / "client"
    / "playback"
    / "PlaybackService.java"
)


class CapabilityBlockTest(unittest.TestCase):
    def test_block_has_every_section_a_client_reads(self):
        block = policy.playback_capabilities()
        self.assertEqual(block["version"], policy.CAPABILITY_VERSION)
        self.assertEqual(set(block), {"version", "queue", "position", "shuffle"})
        self.assertEqual(set(block["queue"]), {"max_items", "remote_max_items", "truncation_notice"})
        self.assertEqual(set(block["position"]), {"report", "min_interval_ms"})
        self.assertEqual(set(block["shuffle"]), {"mode"})

    def test_queue_limits_are_the_real_ones(self):
        queue = policy.playback_capabilities()["queue"]
        self.assertEqual(queue["max_items"], MAX_QUEUE_TRACKS)
        self.assertEqual(queue["remote_max_items"], policy.REMOTE_QUEUE_MAX_ITEMS)
        self.assertIs(queue["truncation_notice"], True, "a cap without a notice is a silent truncation")
        self.assertLessEqual(queue["remote_max_items"], queue["max_items"])

    def test_position_interval_is_an_interval_not_a_write_per_second(self):
        position = policy.playback_capabilities()["position"]
        self.assertIs(position["report"], True)
        self.assertGreaterEqual(position["min_interval_ms"], 5000)
        self.assertEqual(position["min_interval_ms"], policy.POSITION_REPORT_MIN_INTERVAL_MS)

    def test_shuffle_is_declared_as_an_order(self):
        # A client that still randomises per press would disagree with the
        # server about what "next" means; the block says which one is meant.
        self.assertEqual(policy.playback_capabilities()["shuffle"]["mode"], "queue-order")


class AndroidAgreementTest(unittest.TestCase):
    def test_remote_cap_matches_playback_service(self):
        source = ANDROID_PLAYBACK_SERVICE.read_text(encoding="utf-8")
        match = re.search(r"MAX_REMOTE_QUEUE_ITEMS\s*=\s*(\d+)", source)
        self.assertIsNotNone(match, "PlaybackService must still declare MAX_REMOTE_QUEUE_ITEMS")
        self.assertEqual(
            int(match.group(1)),
            policy.REMOTE_QUEUE_MAX_ITEMS,
            "the client-side and native-side caps must be the same number",
        )

    def test_android_slices_at_that_constant(self):
        source = ANDROID_PLAYBACK_SERVICE.read_text(encoding="utf-8")
        self.assertIn("Math.min(array.length(), MAX_REMOTE_QUEUE_ITEMS)", source)


class RecordingOutput(OutputPlugin):
    plugin_id = "recording"
    target_kind = "recording"

    def __init__(self):
        self.commands = []

    def open(self, track, state, context=None):
        return {"ok": True}

    def command(self, command, state, context=None):
        self.commands.append(command.action)
        return {"ok": True}

    def close(self, state):
        return None

    def capabilities(self):
        return {}


class ProgressCommandTest(unittest.TestCase):
    """The client's position report must update state and stop there."""

    def setUp(self):
        self.output = RecordingOutput()
        self.core = PlaybackCore(OutputRegistry([self.output]))
        self.core.set_queue(
            [{"id": name, "title": name, "duration": 200} for name in ("a", "b", "c")],
            current="b",
        )

    def test_progress_updates_the_position(self):
        result = self.core.dispatch(PlaybackCommand(action="progress", position=42.5))
        self.assertTrue(result["ok"])
        self.assertEqual(self.core.state.position, 42.5)
        self.assertEqual(result["result"], {"ok": True, "position": 42.5})

    def test_progress_never_reaches_an_output_plugin(self):
        # A seek to the position already playing is a no-op at best and an
        # audible stutter on a renderer that restarts its stream at worst.
        self.core.dispatch(PlaybackCommand(action="progress", position=12))
        self.assertEqual(self.output.commands, [])

    def test_progress_does_not_change_the_track_or_transport(self):
        before = self.core.state.current_track_id
        self.core.dispatch(PlaybackCommand(action="progress", position=12))
        self.assertEqual(self.core.state.current_track_id, before)
        self.assertEqual(self.core.state.transport, "STOPPED", "a report is not a play")

    def test_progress_rejects_a_position_that_is_not_a_position(self):
        for value in (None, -5, float("nan"), float("inf"), "12", True):
            with self.subTest(position=value):
                self.core.dispatch(PlaybackCommand(action="progress", position=7))
                self.core.dispatch(PlaybackCommand(action="progress", position=value))
                self.assertEqual(self.core.state.position, 0.0, value)

    def test_progress_needs_no_queue(self):
        # The report arrives on page hide, after a queue may already be gone.
        empty = PlaybackCore(OutputRegistry([RecordingOutput()]))
        result = empty.dispatch(PlaybackCommand(action="progress", position=9))
        self.assertTrue(result["ok"])
        self.assertEqual(empty.state.position, 9.0)


class ControlActionSurfaceTest(unittest.TestCase):
    """The HTTP layer must accept the action the page sends."""

    def test_progress_is_an_allowed_control_action(self):
        source = (ROOT / "app" / "server" / "server.py").read_text(encoding="utf-8")
        match = re.search(r"PLAYBACK_CONTROL_ACTIONS\s*=\s*(?:frozenset\()?\{(.*?)\}", source, re.S)
        self.assertIsNotNone(match, "PLAYBACK_CONTROL_ACTIONS must stay a literal set")
        body = "\n".join(line.split("#", 1)[0] for line in match.group(1).splitlines())
        actions = set(re.findall(r'"([a-z_]+)"', body))
        self.assertIn("progress", actions)

    def test_capabilities_route_is_served(self):
        source = (ROOT / "app" / "server" / "server.py").read_text(encoding="utf-8")
        self.assertIn('if path == "/api/playback/capabilities":', source)
        self.assertIn("return self.send_json(playback_capabilities())", source)


if __name__ == "__main__":
    unittest.main()
