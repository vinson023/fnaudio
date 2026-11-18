"""R587: the browser half of the position loop.

The server has stored ``position`` in the session for a long time; nothing ever
read it back, so a reload restarted the track at 0:00 while the queue, the row
and the transport state all came back correctly.  Two things had to exist for
that to work:

* a client that *reports* where it is (pause, tab hidden, page leaving, and every
  30s while playing) -- the server cannot know, it is not the one playing;
* a restore path that *consumes* the number, once, for the row it belongs to.

These are wiring assertions, not behaviour tests: app.js has no module boundary
here, so the cheapest honest guard is that the events stay connected and the
payload stays a report rather than a transport command.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "ui" / "app.js"


class ReportTriggerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")

    def test_pause_reports_immediately(self):
        line = next(
            (line for line in self.source.splitlines() if line.startswith("audio.onpause")),
            "",
        )
        self.assertIn("reportPlaybackPosition(true)", line, "pausing is the moment a session ends")

    def test_leaving_the_page_reports_with_keepalive(self):
        # `pagehide` is the last chance: the document is going away, so the
        # request has to be allowed to outlive it.
        self.assertIn('window.addEventListener("pagehide"', self.source)
        self.assertRegex(
            self.source,
            r'window\.addEventListener\("pagehide",\s*\(\)\s*=>\s*\{[^}]*reportPlaybackPosition\(true,\s*true\)',
        )

    def test_hiding_the_tab_reports(self):
        # A phone switches apps without firing pagehide; a hidden tab is the
        # same thing from the listener's point of view.
        self.assertRegex(self.source, r"visibilitychange[\s\S]{0,400}reportPlaybackPosition\(true\)")

    def test_the_interval_report_only_runs_while_playing(self):
        match = re.search(r"setInterval\(\(\)\s*=>\s*\{([^}]*reportPlaybackPosition[^}]*)\}", self.source)
        self.assertIsNotNone(match, "the 30s report must stay on an interval")
        self.assertIn("audio.paused", match.group(1), "a paused player has nothing new to report")

    def test_reporting_is_cheap_when_nothing_plays(self):
        match = re.search(r"function reportPlaybackPosition\([\s\S]*?^\}", self.source, re.M)
        self.assertIsNotNone(match)
        body = match.group(0)
        self.assertIn('state.playTarget !== "local"', body, "a renderer reports its own position")
        self.assertIn("!state.queue.length", body)
        self.assertIn("Math.max(5000,", body, "the floor keeps the report from becoming a write per second")


class ReportPayloadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")
        match = re.search(r"function reportPlaybackPosition\([\s\S]*?^\}", cls.source, re.M)
        cls.body = match.group(0) if match else ""

    def test_the_payload_is_a_progress_report(self):
        self.assertIn('action: "progress"', self.body)
        self.assertIn("position: seconds", self.body)
        self.assertIn("/api/playback/control", self.body)

    def test_the_payload_carries_no_session_identity(self):
        # A progress report is not a transport command. Carrying a command_id or
        # the ticket would let a background tab take ownership of the session
        # that the playing tab owns.
        for forbidden in ("command_id", "command_ticket", "generation", "engine_epoch"):
            self.assertNotIn(forbidden, self.body, "a report must not claim the session: " + forbidden)

    def test_the_keepalive_path_does_not_use_the_bridge(self):
        # `apiFetch` waits on a response chain the document no longer has.
        self.assertRegex(
            self.body,
            r'if \(keepalive\) \{[\s\S]*?fetch\("api/playback/control", \{ \.\.\.init, keepalive: true \}\)',
        )


class RestoreConsumptionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")

    def test_the_restore_path_keeps_the_saved_position(self):
        self.assertRegex(
            self.source,
            r"const savedPosition = playbackSeconds\(playback\.position\);",
            "the stored position must actually be read",
        )
        self.assertRegex(
            self.source,
            r'if \(state\.playTarget === "local" && savedPosition > 1 && state\.index >= 0\)',
            "only the local target resumes; a renderer would be fought by a seek",
        )
        self.assertIn("state.restoreSeekTime = savedPosition;", self.source)

    def test_both_load_paths_consume_it(self):
        # The native host and the <audio> element are different players; a resume
        # that only works on one of them is a bug report waiting for the other.
        calls = re.findall(r"(?<!function )consumeRestoreSeekTime\(item\)", self.source)
        self.assertEqual(
            len(calls),
            2,
            "native load and audio load must both ask where the listener was",
        )

    def test_it_is_consumed_once_and_only_for_its_own_row(self):
        match = re.search(r"function consumeRestoreSeekTime\([\s\S]*?^\}", self.source, re.M)
        self.assertIsNotNone(match)
        body = match.group(0)
        self.assertIn("state.restoreSeekTrackId", body, "another row must not be seeked")
        self.assertEqual(body.count("state.restoreSeekTime = null;"), 2, "used once, or expired")
        self.assertIn("600000", body, "a stale restore must not seek a song picked ten minutes later")

    def test_a_restore_does_not_override_the_host_player(self):
        match = re.search(r"const resumeSeconds = shouldResume[\s\S]*?;", self.source)
        self.assertIsNotNone(match)
        self.assertIn("state.nativePlayback.position", match.group(0), "a loaded host player knows better")


if __name__ == "__main__":
    unittest.main()
