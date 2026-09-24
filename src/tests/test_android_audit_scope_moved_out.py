"""Bound the 2026-09-23 ruling that takes the Android audit out of the per-round goal.

The owner's standing instructions are that (a) every open judgement is taken by
Codex on its own best judgement, and (b) anything that no longer belongs to the
round-by-round queue leaves it *as a future goal* rather than vanishing.  R167
applies (b) to the Android client: the owner states that the Android code is
finished and is not to be audited by these rounds, so the four classes R130
folded into the code ledger leave the review scope and land in
``docs/FUTURE_GOALS.md``.

A scope move like this fails in six different ways, so all six are pinned:

* it silently comes back -- at most one open code-bucket entry may name the four
  classes, and it is the debt ledger, which has to keep naming them because its
  sibling guard requires those names;
* history gets rewritten instead of appended to -- the 18,225-line and 9,695-line
  registrations stay verbatim while the new note states the recomputed remainder;
* the new home is unreachable or duplicated -- ``docs/INDEX.md`` carries exactly
  one entry for it, and that entry is a bullet, not a prose mention;
* the move is mistaken for a deletion -- the release manifest still hashes every
  tracked Java file, so "not reviewed this round" cannot become "gone";
* the scope is smuggled into the hardware doc instead -- that doc keeps exactly
  its 11 frozen ids and none of them names an audited class;
* the future doc leaks a credential or cites a line number into the region of
  ``TODO.md`` that renumbers with every recorded round.

The remainder stated by the note is deliberately *frozen* rather than recomputed:
``app.js`` changes on most rounds, and a documentation guard that reddens every
time a source file grows manufactures a red gate for the next round instead of
guarding this one.  Recomputable quantities -- the per-class line counts and the
43-file / 9,695-line total -- are measured from disk on every run.
"""

from pathlib import Path
import re
import unittest

# One convention, imported rather than copied: the credential shape and the
# line-number pattern come from the device-migration guard, the frozen-block
# reader from the hardware-goal guard, and the file walk from the manifest
# guard, because "tracked" for a counting rule means exactly what the release
# manifest hashes -- not whatever a machine that has run Gradle happens to hold
# under ``app/build``.
try:
    from test_device_todos_migrated import (
        CREDENTIAL_SHAPE,
        DEVICE_SEGMENT_START,
        TODO_LINE_REF,
    )
    from test_real_device_goals_moved_out import MOVED_GOAL_IDS, goal_blocks
    from test_scope_entry_subsumption import (
        CLOSED_ITEM,
        NOTE_DELIMITER,
        OPEN_ITEM,
        SUCCESSOR_MARKER,
        content_lines,
    )
    from test_source_manifest import manifest_scoped_files
except ImportError:  # pragma: no cover - depends on how the suite was started
    from tests.test_device_todos_migrated import (
        CREDENTIAL_SHAPE,
        DEVICE_SEGMENT_START,
        TODO_LINE_REF,
    )
    from tests.test_real_device_goals_moved_out import MOVED_GOAL_IDS, goal_blocks
    from tests.test_scope_entry_subsumption import (
        CLOSED_ITEM,
        NOTE_DELIMITER,
        OPEN_ITEM,
        SUCCESSOR_MARKER,
        content_lines,
    )
    from tests.test_source_manifest import manifest_scoped_files


REPO_ROOT = Path(__file__).resolve().parents[2]
TODO = REPO_ROOT / "TODO.md"
FUTURE_DOC = REPO_ROOT / "docs" / "FUTURE_GOALS.md"
DEVICE_DOC = REPO_ROOT / "docs" / "REAL_DEVICE_GOALS.md"
DEVICE_DOC_NAME = "REAL_DEVICE_GOALS.md"
LEDGER_DOC_NAME = "external-acceptance.md"
DOCS_INDEX = REPO_ROOT / "docs" / "INDEX.md"
MANIFEST = REPO_ROOT / "SOURCE_MANIFEST.sha256"

# The four classes R130 folded into the code ledger.  ``test_scope_entry_subsumption``
# already insists that the ledger names them and that their registered sizes match
# disk, so this file never asks the ledger to drop them: it only insists that they
# stop being work these rounds schedule.
AUDIT_CLASSES = (
    "RemotePlaybackPlayer",
    "PlaybackService",
    "AuthenticatedBitmapLoader",
    "FnConnectRelayConfigClient",
)

INDEX_ENTRY = re.compile(r"^-\s+`" + re.escape(FUTURE_DOC.name) + r"`")
FUTURE_GOAL_WORDING = "\u4ee5\u540e\u7684\u76ee\u6807"  # the owner's own words for the new home
MOVED_OUT_WORDING = "\u79fb\u51fa\u672c\u6b21\u76ee\u6807"  # "removed from this goal"
RULING_WORDING = "\u4e0d\u9700\u8981\u4f60\u5ba1\u67e5"  # the owner's reason, quoted verbatim
# The note that records the move is found by this anchor and nothing else: round
# numbers renumber nothing, but prose gets reworded, so the anchor is the phrase
# that states what the remainder is measured over.
REMAINDER_ANCHOR = "\u5269\u4f59\u6b20\u8bfb\u603b\u91cf"  # "remaining not-yet-deep-read total"
REMAINDER = re.compile(REMAINDER_ANCHOR + r"[^\d]{0,12}([\d,]+) \u884c")

# What the ledger said immediately before the move, and what the note says
# immediately after it.  18,225 lines = app.js 8,530 + 43 tracked Java files
# 9,695; 8,530 is app.js alone, i.e. exactly the Android remainder taken out.
DEBT_BEFORE_MOVE_OUT = 18225
DEBT_AFTER_MOVE_OUT = 8530
# Frozen on purpose: these two numbers are the arithmetic identity of the move,
# not a measurement of a living file.
JAVA_TOTAL_FILES = 43
JAVA_TOTAL_LINES = 9695

# Historical figures the note must keep quoting instead of correcting.
PRESERVED_FIGURES = ("18,225", "9,695")


def tracked_java(repo_root):
    """Every ``.java`` the release manifest walks: the tracked Android surface."""
    return sorted(
        (relative, path)
        for relative, path in manifest_scoped_files(repo_root)
        if relative.startswith("android-client/") and relative.endswith(".java")
    )


def manifest_paths():
    rows = MANIFEST.read_text(encoding="ascii").splitlines()
    found = set()
    for row in rows:
        parts = row.split("  ")
        if len(parts) == 2:
            found.add(parts[1])
    return found


class AndroidAuditScopeMovedOutTests(unittest.TestCase):
    def setUp(self):
        text = TODO.read_text(encoding="utf-8")
        self.assertNotIn("\r", text, "TODO.md must stay LF-only before it is parsed")
        self.lines = text.split("\n")
        self.device_start = next(
            (index for index, line in enumerate(self.lines) if line.startswith(DEVICE_SEGMENT_START)),
            None,
        )
        self.assertIsNotNone(self.device_start, "the device segment must exist to bound the code bucket")
        open_code = [
            (number, line)
            for number, line in enumerate(self.lines[: self.device_start], start=1)
            if OPEN_ITEM.match(line)
        ]
        # Located by marker and not by state: R173 shut the ledger, so requiring an
        # open row here would only make this guard blind the moment the debt it
        # records was actually paid.
        ledger = [
            (number, line)
            for number, line in enumerate(self.lines[: self.device_start], start=1)
            if SUCCESSOR_MARKER in line
        ]
        self.assertEqual(
            len(ledger), 1,
            "this guard locates the debt ledger the same way its sibling does, and found %d" % len(ledger),
        )
        self.ledger_number, self.ledger_text = ledger[0]
        self.assertTrue(
            CLOSED_ITEM.match(self.ledger_text),
            "TODO.md line %d is the shut debt ledger; an open row carrying the moved-out "
            "Android scope would schedule it again" % self.ledger_number,
        )
        self.open_code_entries = open_code

    def classes_named_by(self, line):
        return [name for name in AUDIT_CLASSES if name in line]

    def test_only_the_debt_ledger_still_names_the_audited_classes(self):
        """Discriminating case for the move: re-scheduling Android turns this red.

        Two halves.  No *open* code-bucket entry may name the audited classes -- that
        is the move-out being quietly reversed -- while the shut ledger must keep
        naming all four, so paying the debt cannot be made to look like deleting it.
        """
        carriers = [
            (number, self.classes_named_by(line))
            for number, line in self.open_code_entries
            if len(self.classes_named_by(line)) >= 3
        ]
        self.assertEqual(
            carriers, [],
            "the audited Android classes may be named by no open code-bucket entry: doing so puts "
            "the moved-out scope back on the per-round queue -- got %s" % carriers,
        )
        self.assertEqual(
            sorted(self.classes_named_by(self.ledger_text)), sorted(AUDIT_CLASSES),
            "TODO.md line %d must keep naming every audited Android class the move-out covered"
            % self.ledger_number,
        )

    def test_the_ledger_note_keeps_the_history_and_states_the_remainder(self):
        self.assertIn(
            MOVED_OUT_WORDING, self.ledger_text,
            "TODO.md line %d no longer says the Android scope left this goal" % self.ledger_number,
        )
        self.assertIn(
            FUTURE_DOC.name, self.ledger_text,
            "the ledger must say where the scope went, and %s is the only place it went"
            % FUTURE_DOC.name,
        )
        for figure in PRESERVED_FIGURES:
            self.assertIn(
                figure, self.ledger_text,
                "the pre-move figure %s has been rewritten; recorded debt is appended to, never "
                "corrected in place" % figure,
            )
        match = REMAINDER.search(self.ledger_text)
        self.assertIsNotNone(
            match,
            "the ledger lost the 「%s …行」 sentence that states what is left after the move-out"
            % REMAINDER_ANCHOR,
        )
        stated = int(match.group(1).replace(",", ""))
        self.assertEqual(
            stated, DEBT_AFTER_MOVE_OUT,
            "the ledger states a remainder of %d lines; the move-out takes exactly Java %d lines out "
            "of %d, so anything else is a re-derivation rather than a record"
            % (stated, JAVA_TOTAL_LINES, DEBT_BEFORE_MOVE_OUT),
        )
        self.assertNotIn(
            "剩余欠读总量 %s" % DEBT_BEFORE_MOVE_OUT, self.ledger_text,
            "the ledger still adds the Android lines back into the remainder it claims to have moved out",
        )

    def test_the_future_doc_exists_is_indexed_once_and_states_its_scope(self):
        self.assertTrue(
            FUTURE_DOC.is_file(),
            "%s is missing: the ruling moved the Android audit out of the per-round goal and it has "
            "to live somewhere a takeover can find" % FUTURE_DOC.name,
        )
        text = FUTURE_DOC.read_text(encoding="utf-8")
        index_text = DOCS_INDEX.read_text(encoding="utf-8") if DOCS_INDEX.is_file() else ""
        listed = [line for line in index_text.split("\n") if INDEX_ENTRY.match(line)]
        self.assertEqual(
            len(listed), 1,
            "docs/INDEX.md must carry exactly one entry line opening with 「`%s`」, found %d"
            % (FUTURE_DOC.name, len(listed)),
        )
        for wording in (MOVED_OUT_WORDING, FUTURE_GOAL_WORDING, RULING_WORDING):
            self.assertIn(wording, text, "the future-goal doc lost the wording 「%s」" % wording)
        self.assertIn(DEVICE_DOC_NAME, text, "the doc must point at the hardware list it is not")
        self.assertIn(LEDGER_DOC_NAME, text, "the doc must say where device tasks live instead")
        java = tracked_java(REPO_ROOT)
        by_name = {}
        for relative, path in java:
            by_name.setdefault(path.name, []).append((relative, path))
        total_lines = sum(content_lines(path) for _relative, path in java)
        aggregate = "%d \u4e2a\u6587\u4ef6 / %s \u884c" % (len(java), format(total_lines, ","))
        self.assertIn(
            aggregate, text,
            "the doc states a Java accounting that no longer matches disk; it must read \u300c%s\u300d"
            % aggregate,
        )
        self.assertEqual(
            total_lines, JAVA_TOTAL_LINES,
            "the tracked Java surface totals %d lines while the moved-out scope registered %d"
            % (total_lines, JAVA_TOTAL_LINES),
        )
        for name in AUDIT_CLASSES:
            with self.subTest(face=name):
                self.assertIn(name, text, "the doc does not carry over the audited face %s" % name)
                rows = by_name.get(name + ".java", [])
                self.assertEqual(len(rows), 1, "%s.java is not unique in the tree" % name)
                counted = content_lines(rows[0][1])
                self.assertIn(
                    "%s.java`\uff08%s \u884c\uff09" % (name, format(counted, ",")), text,
                    "the doc must register %s.java with its on-disk count of %s lines"
                    % (name, format(counted, ",")),
                )

    def test_the_future_doc_leaks_no_credentials_and_no_renumbering_citations(self):
        text = FUTURE_DOC.read_text(encoding="utf-8")
        leaked = [line.strip()[:80] for line in text.split("\n") if CREDENTIAL_SHAPE.search(line)]
        self.assertEqual(leaked, [], "the future-goal doc carries something shaped like a credential")
        start = next(
            (number for number, line in enumerate(self.lines, start=1)
             if line.startswith(DEVICE_SEGMENT_START)),
            None,
        )
        self.assertIsNotNone(start, "TODO.md lost the device segment heading")
        offenders = [match.group(0) for match in TODO_LINE_REF.finditer(text) if int(match.group(1)) > start]
        self.assertEqual(
            offenders, [],
            "citations into the renumbering region of TODO.md expire the first round they are used: %s"
            % offenders,
        )

    def test_the_hardware_doc_did_not_absorb_the_android_scope(self):
        blocks = goal_blocks(DEVICE_DOC.read_text(encoding="utf-8"))
        self.assertEqual(
            sorted(blocks), sorted(MOVED_GOAL_IDS),
            "the frozen hardware ids must stay exactly the %d moved items; the Android scope belongs "
            "in %s, not as a twelfth hardware goal" % (len(MOVED_GOAL_IDS), FUTURE_DOC.name),
        )
        offenders = [
            name
            for name in AUDIT_CLASSES
            if any(name in line for block in blocks.values() for line in block)
        ]
        self.assertEqual(
            offenders, [],
            "an audited Android class turned up inside a frozen hardware block: %s" % offenders,
        )

    def test_moving_the_scope_out_did_not_move_the_code_out_of_the_release(self):
        java = tracked_java(REPO_ROOT)
        self.assertEqual(len(java), JAVA_TOTAL_FILES, "the tracked Android surface is no longer 43 files")
        total = sum(content_lines(path) for _relative, path in java)
        self.assertEqual(
            total, JAVA_TOTAL_LINES,
            "the tracked Android surface is %d lines while the moved-out scope was registered at %d; "
            "an audit freeze does not license silent edits -- update the doc, the ledger note and "
            "this constant together" % (total, JAVA_TOTAL_LINES),
        )
        listed = manifest_paths()
        missing = [relative for relative, _path in java if relative not in listed]
        self.assertEqual(
            missing, [],
            "%s stopped hashing Android sources; the ruling took them out of review scope, not out of "
            "the release" % MANIFEST.name,
        )


if __name__ == "__main__":
    unittest.main()