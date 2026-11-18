"""R587: one navigation table, checked from Python and from JavaScript.

``queue_order_policy.py`` is the rule the core uses; ``queue_order_policy.js`` is
the same rule for the page.  Both suites read ``tests/queue_order_table.json``,
so a change made on one side fails on the other instead of shipping two
behaviours behind one button.

This file also pins the two facts the table cannot express:

* the old behaviour is really gone -- ``PlaybackCore`` must not draw a random
  row for "next" any more (that is what made "shuffle" mean three things);
* ``normalize_repeat`` refuses unknown modes instead of silently accepting them,
  because it is the guard in front of ``state.repeat``.
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, "app/server")

import queue_order_policy as policy
from playback.core import PlaybackCore
from playback.models import TrackRef

ROOT = Path(__file__).resolve().parent.parent
TABLE = json.loads((ROOT / "tests" / "queue_order_table.json").read_text(encoding="utf-8"))
JS_POLICY = ROOT / "app" / "ui" / "queue_order_policy.js"


class QueueOrderTableTest(unittest.TestCase):
    def test_table_file_is_the_shared_one(self):
        self.assertEqual(TABLE["max_items"], policy.MAX_ITEMS)
        self.assertEqual(tuple(TABLE["repeat_modes"]), policy.REPEAT_MODES)
        self.assertGreaterEqual(len(TABLE["cases"]), 15, "the table must stay worth reading")

    def test_every_row_matches_the_python_rule(self):
        for case in TABLE["cases"]:
            with self.subTest(why=case["why"]):
                self.assertEqual(
                    policy.next_index(case["index"], case["length"], case["repeat"]),
                    case["next"],
                    "next: " + case["why"],
                )
                self.assertEqual(
                    policy.previous_index(case["index"], case["length"], case["repeat"]),
                    case["previous"],
                    "previous: " + case["why"],
                )

    def test_repeat_defaults_to_off(self):
        # The core calls these with two arguments when the client sent no mode.
        self.assertEqual(policy.next_index(0, 3), 1)
        self.assertEqual(policy.previous_index(0, 3), -1)

    def test_normalize_repeat_refuses_unknown_modes(self):
        self.assertEqual(policy.normalize_repeat("all"), "all")
        self.assertEqual(policy.normalize_repeat("one"), "one")
        self.assertIsNone(policy.normalize_repeat("shuffle"))
        self.assertIsNone(policy.normalize_repeat(None))
        self.assertIsNone(policy.normalize_repeat(1))


class QueueOrderJsCopyTest(unittest.TestCase):
    """Cheap drift guard that needs no node: the JS copy must still say 50000/off/all/one."""

    def test_js_copy_declares_the_same_constants(self):
        source = JS_POLICY.read_text(encoding="utf-8")
        self.assertIn("const MAX_ITEMS = %d;" % policy.MAX_ITEMS, source)
        self.assertIn('const REPEAT_MODES = ["off", "all", "one"];', source)

    def test_js_copy_exposes_the_same_helpers(self):
        source = JS_POLICY.read_text(encoding="utf-8")
        for name in ("nextIndex", "previousIndex", "orderIds", "shuffleQueue", "restoreQueue"):
            self.assertRegex(source, r"\bfunction %s\(" % re.escape(name), name + " must exist")
            self.assertIn(name, source.split("window.fnAudioQueueOrderPolicy")[1], name + " must be exported")


class NoRandomNextTest(unittest.TestCase):
    """The bug R587 removed: "next" used to re-roll a random row every press."""

    def test_core_no_longer_imports_random(self):
        source = (ROOT / "app" / "server" / "playback" / "core.py").read_text(encoding="utf-8")
        self.assertNotIn("import random", source)
        # A comment may mention the removed call; the code must not make it.
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                self.assertNotEqual(node.value.id, "random", "no random draw may pick a track any more")

    def test_core_next_track_follows_the_table(self):
        core = PlaybackCore()
        core.state.queue = [TrackRef(track_id=name) for name in ("a", "b", "c")]
        core.state.current_index = 1
        core.state.repeat = "off"
        self.assertEqual(core.next_track().track_id, "c")
        self.assertEqual(core.state.current_index, 2, "next moves the cursor")
        self.assertEqual(core.previous_track().track_id, "b")
        self.assertEqual(core.state.current_index, 1, "previous moves it back")

        core.state.current_index = 2
        self.assertIsNone(core.next_track(), "repeat off ends the queue")
        self.assertEqual(core.state.current_index, 2, "a dead end must not move the cursor")
        self.assertEqual(core.previous_track().track_id, "b")

        core.state.current_index = 2
        core.state.repeat = "all"
        self.assertEqual(core.next_track().track_id, "a")
        core.state.current_index = 2
        core.state.repeat = "one"
        self.assertEqual(core.next_track().track_id, "c")
        self.assertEqual(core.previous_track().track_id, "c", "repeat one restarts the same row")


class ShuffleHandoffTest(unittest.TestCase):
    """The page shuffles the queue; the host player must not shuffle it again.

    Before R587 both layers shuffled -- the page with ``Math.random`` per press
    and ExoPlayer with its own order -- so the highlighted row and the playing
    row drifted apart on Android.  The queue now arrives in play order, and both
    hand-offs say so.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / "app" / "ui" / "app.js").read_text(encoding="utf-8")
        cls.bridge = (
            ROOT.parent
            / "android-client"
            / "app"
            / "src"
            / "main"
            / "java"
            / "com"
            / "fnaudio"
            / "client"
            / "web"
            / "NativePlaybackBridge.java"
        ).read_text(encoding="utf-8")

    def test_the_toggle_applies_an_order_instead_of_re_rolling(self):
        body = re.search(r"async function toggleShuffle\([\s\S]*?^\}", self.app, re.M).group(0)
        self.assertIn("applyShuffleOrder(", body)
        self.assertNotIn("Math.random", body)
        self.assertIn('nativePlaybackCall("setShuffle", false)', body)

    def test_switching_shuffle_on_remembers_the_original_order(self):
        body = re.search(r"async function applyShuffleOrder\([\s\S]*?^\}", self.app, re.M).group(0)
        self.assertIn("state.shuffleOriginal = policy.orderIds(state.queue);", body)
        self.assertIn("policy.shuffleQueue(", body)
        self.assertIn("policy.restoreQueue(", body)
        self.assertIn("{ shuffle: true }", body)
        self.assertIn("{ shuffle: false }", body)

    def test_the_host_player_is_never_told_to_shuffle(self):
        body = re.search(r"function nativeLoadQueue\([\s\S]*?^\}", self.app, re.M).group(0)
        self.assertNotIn('nativePlaybackCall("setShuffle", state.shuffle)', body)
        self.assertIn('nativePlaybackCall("setShuffle", false)', body)
        self.assertRegex(
            body,
            r'nativePlaybackCall\("setQueue",[\s\S]*?state\.repeat,\s*false\);',
            "the setQueue shuffle argument is always false",
        )

    def test_the_bridge_forces_shuffle_off(self):
        self.assertIn("controller.setShuffleModeEnabled(false);", self.bridge)
        set_shuffle = re.search(r"public void setShuffle\(boolean enabled\) \{[\s\S]*?\n    \}", self.bridge).group(0)
        self.assertNotIn("setShuffleModeEnabled(enabled)", set_shuffle)
        self.assertIn("setShuffleModeEnabled(false)", set_shuffle)

    def test_a_confirmed_queue_keeps_the_remembered_order_in_step(self):
        body = re.search(r"function reconcileShuffleOrder\([\s\S]*?^\}", self.app, re.M).group(0)
        self.assertIn("state.shuffleOriginal", body)
        confirmed = re.search(r"function applyConfirmedQueue\([\s\S]*?^\}", self.app, re.M).group(0)
        self.assertIn("reconcileShuffleOrder(", confirmed)


if __name__ == "__main__":
    unittest.main()
