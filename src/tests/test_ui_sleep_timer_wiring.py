"""R588: the sleep timer's two halves have to stay connected.

The arithmetic is in ``app/ui/sleep_timer_policy.js`` (tested there). What this
file guards is the part no unit test can reach: a deadline set in the page has to
become a pending handler inside the foreground service, and it has to survive the
WebView being suspended, destroyed, or reloaded. Every link in that chain is a
separate file, so a missing one fails silently -- the timer simply never fires.

The failure this prevents is specific: a sleep timer implemented with a page
``setTimeout`` works on a desk and fails on a nightstand, because a hidden
WebView throttles timers while the decoder keeps playing.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "ui" / "app.js"
INDEX = ROOT / "app" / "ui" / "index.html"
POLICY = ROOT / "app" / "ui" / "sleep_timer_policy.js"
BRIDGE = (
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
)
SERVICE = (
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
ACTIVITY = (
    ROOT.parent
    / "android-client"
    / "app"
    / "src"
    / "main"
    / "java"
    / "com"
    / "fnaudio"
    / "client"
    / "ui"
    / "MainActivity.java"
)


def function_body(source, name):
    match = re.search(r"^function %s\([\s\S]*?^\}" % re.escape(name), source, re.M)
    return match.group(0) if match else ""


def java_body(source, name):
    """Return one Java method, braces balanced, so a grep cannot match the caller."""
    match = re.search(r"^[ \t]*[A-Za-z@][^\n]*\b%s\(" % re.escape(name), source, re.M)
    if not match:
        return ""
    start = source.find("{", match.start())
    if start < 0:
        return ""
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():index + 1]
    return ""


class ScriptLoadingTest(unittest.TestCase):
    """The page and the APK must load the module, in the same order."""

    def test_index_declares_the_policy_next_to_the_other_playback_policies(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('src="sleep_timer_policy.js', text)
        order = re.findall(r'src="([a-z_]+\.js)', text)
        self.assertIn("sleep_timer_policy.js", order)
        self.assertEqual(
            order.index("sleep_timer_policy.js"),
            order.index("playback_capability_policy.js") + 1,
            "the sleep timer policy must follow the playback capability policy",
        )

    def test_android_bundles_it_at_the_same_position(self):
        java = ACTIVITY.read_text(encoding="utf-8")
        self.assertIn('"sleep_timer_policy.js"', java)
        scripts = re.findall(r'"([a-z_]+\.js)"', java)
        self.assertEqual(
            scripts.index("sleep_timer_policy.js"),
            scripts.index("playback_capability_policy.js") + 1,
            "index.html and additionalScripts must agree on the order",
        )


class PageWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")

    def test_a_reload_restores_the_timer(self):
        self.assertIn("restoreSleepTimer();", self.source, "the deadline must be picked up at boot")
        body = function_body(self.source, "restoreSleepTimer")
        self.assertIn("readStored", body)
        self.assertIn("isActive", body)
        self.assertIn("isFreshExpiry", body, "an expired deadline from yesterday must not pause new music")

    def test_the_deadline_reaches_the_host_player(self):
        body = function_body(self.source, "applySleepTimerDeadline")
        self.assertIn('nativePlaybackCall("scheduleSleepTimer", state.sleepTimerDeadline)', body)
        self.assertIn('nativePlaybackCall("cancelSleepTimer")', body)
        self.assertIn("writeStored", body, "the page keeps its own copy for the countdown")

    def test_the_page_tick_compares_a_deadline_instead_of_counting_down(self):
        body = function_body(self.source, "tickSleepTimer")
        self.assertIn("isExpired(state.sleepTimerDeadline, Date.now())", body)
        self.assertIn("fireSleepTimer()", body)
        arm = function_body(self.source, "armSleepTimerTick")
        self.assertIn("setInterval(tickSleepTimer", arm)
        self.assertNotIn("setTimeout", arm, "a countdown drifts as soon as the page is throttled")

    def test_firing_pauses_and_clears(self):
        body = function_body(self.source, "fireSleepTimer")
        self.assertIn("pauseForSleepTimer()", body)
        self.assertIn("applySleepTimerDeadline(0)", body)
        pause = function_body(self.source, "pauseForSleepTimer")
        for transport in ("controlIncomingRenderer", "remoteControl", "nativePlaybackCall", "audio.pause"):
            self.assertIn(transport, pause, "every output the play button handles must be pausable")
        self.assertNotIn("audio.play", pause, "the sleep timer must never start anything")

    def test_the_controls_live_in_the_playback_settings(self):
        self.assertIn("ensureSleepTimerControls();", self.source)
        self.assertIn('$("sleepTimerControls")', self.source)
        self.assertIn('$("sleepTimerStatus")', self.source)
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="sleepTimerControls"', html)
        self.assertIn('id="sleepTimerStatus"', html)
        self.assertIn('data-settings-block="playback-sleep"', html)
        self.assertIn('id="settings-pane-playback"', html, "the group belongs to the playback pane")


class BridgeWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = BRIDGE.read_text(encoding="utf-8")
        cls.service = SERVICE.read_text(encoding="utf-8")

    def test_the_bridge_exposes_both_calls(self):
        self.assertRegex(
            self.bridge,
            r"@JavascriptInterface\s+public void scheduleSleepTimer\(double deadlineEpochMs\)",
        )
        self.assertRegex(self.bridge, r"@JavascriptInterface\s+public void cancelSleepTimer\(\)")

    def test_the_bridge_forwards_to_the_service_action(self):
        body = java_body(self.bridge, "sendSleepTimerDeadline")
        self.assertIn("PlaybackService.ACTION_SLEEP_TIMER", body)
        self.assertIn("PlaybackService.EXTRA_SLEEP_TIMER_DEADLINE_MS", body)
        self.assertIn("startPlaybackService", body)
        self.assertIn("catch (RuntimeException", body, "a refused background start must not crash the WebView")

    def test_a_nonsense_deadline_cancels_instead_of_arming(self):
        body = java_body(self.bridge, "scheduleSleepTimer")
        self.assertIn("cancelSleepTimer()", body)
        self.assertIn("Double.isFinite", body)


class ServiceWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = SERVICE.read_text(encoding="utf-8")

    def test_the_service_owns_the_action(self):
        self.assertIn('ACTION_SLEEP_TIMER = "com.fnaudio.client.playback.SLEEP_TIMER"', self.service)
        self.assertIn("EXTRA_SLEEP_TIMER_DEADLINE_MS", self.service)
        on_start = java_body(self.service, "onStartCommand")
        self.assertIn("ACTION_SLEEP_TIMER.equals(action)", on_start)
        self.assertIn("armSleepTimer(", on_start)

    def test_arming_posts_a_handler_at_the_deadline(self):
        body = java_body(self.service, "armSleepTimer")
        self.assertIn("mainHandler.removeCallbacks(sleepTimerFire)", body, "re-arming must replace, not stack")
        self.assertIn("mainHandler.postDelayed(sleepTimerFire", body)
        self.assertIn("MAX_SLEEP_TIMER_MS", body, "a mis-typed deadline must not arm for a week")
        self.assertIn("persistSleepTimerDeadline", body)

    def test_firing_pauses_the_local_player(self):
        body = java_body(self.service, "fireSleepTimer")
        self.assertIn("player.pause()", body)
        self.assertIn("persistSleepTimerDeadline(0L)", body, "a fired timer must not come back after a restart")

    def test_the_deadline_survives_a_process_reclaim(self):
        self.assertIn("restoreSleepTimer();", java_body(self.service, "onCreate"))
        body = java_body(self.service, "restoreSleepTimer")
        self.assertIn("SLEEP_TIMER_PREFS", body)
        self.assertIn("armSleepTimer(deadline)", body)

    def test_destroy_drops_the_pending_handler(self):
        body = java_body(self.service, "onDestroy")
        self.assertIn("mainHandler.removeCallbacks(sleepTimerFire)", body)


class PolicyOwnershipTest(unittest.TestCase):
    def test_the_arithmetic_has_one_home(self):
        # app.js may read the deadline, but it must not re-implement the maths:
        # two copies of "how long is left" is how the label and the pause drift.
        source = APP.read_text(encoding="utf-8")
        self.assertNotIn("60000", function_body(source, "tickSleepTimer"))
        self.assertNotIn("60000", function_body(source, "updateSleepTimerStatus"))
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn("fnaudio.sleep.deadline.v1", policy)


if __name__ == "__main__":
    unittest.main()
