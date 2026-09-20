"""Keep the "still not deep-read" scope ledger counted exactly once.

The audit-scope queue was restated and never retired: R59 recorded that its
quantified list *replaced* the 2026-09-17 "file names only" entry, yet the
replaced entry stayed open.  Two open entries describing one queue is precisely
how the per-round counters drift away from the real bucket size, so this gate
recomputes the relationship from disk on every run:

* the superseded entry is found by a date-anchored marker, exists once, is
  closed, and still names all 16 audited faces in the text it was written with
  (emptying it would make the other checks vacuous),
* exactly one open code-bucket entry carries that face list -- a face counts
  under either its class or its file spelling, a live ledger may grow its list
  through the notes appended under it, and the closed entry's list is pinned to
  its own text so a note can never move the yardstick,
* no face was dropped on the floor: each one has to be named again either by
  the successor entry or by the device segment, and
* the retirement guards the successor entry cites are still in the tree --
  whether a retired module really left it is the dedicated guards' business,
  and this file deliberately never names one of them.

"""

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
TODO = REPO_ROOT / "TODO.md"
SRC = REPO_ROOT / "src"

# The bare phrase also appears inside the R120 record near the top of the
# file, so the marker carries its date: on disk today this is the one and
# only line that starts a TODO entry about the 2026-09-17 audit scope.
SUPERSEDED_MARKER = "2026-09-17 持续审查未完成范围"
SUCCESSOR_MARKER = "量化成可排期的清单"
DEVICE_HEADING = "## 宿主 MediaSession"
# 〔 opens a per-round note appended under an entry; the entry text ends there.
NOTE_DELIMITER = "\u3014"

OPEN_ITEM = re.compile(r"^- \[ \] ")
CLOSED_ITEM = re.compile(r"^- \[[xX]\] ")
BACKTICKED = re.compile(r"`([^`]+)`")
FACE_TOKEN = re.compile(r"^[A-Za-z0-9_.*+-]+$")
CLASS_NAME = re.compile(r"^[A-Z][A-Za-z0-9]+$")
# The ledger folds a file in as `<full path>`（N 行）, so the registered
# count is read from the tail of the backticked path, not a bare name.
REGISTERED = "{name}`（([\\d,]+) 行）"

# Two of the audited faces are no longer source surfaces: one entry point was
# retired outright, the other moved out of the wired tree.  Both facts belong to
# their own dedicated guards, which are stricter than anything repeated here --
# one of them forbids its retired module name across every scanned source file,
# so naming it in this file would itself break the gate.  What this ledger gate
# may check is the pointer the successor note writes: a guard it cites has to
# still exist under src/tests/.
GUARD_POINTER = re.compile(r"^src/tests/(test_[a-z0-9_]+\.py)$")

# The three Android classes were, before this round, named by nothing but the
# superseded entry, so they must now sit in the code ledger with honest sizes.
ANDROID_LEDGER_FACES = {
    "RemotePlaybackPlayer": REPO_ROOT / "android-client/app/src/main/java/com/fnaudio/client/playback/RemotePlaybackPlayer.java",
    "PlaybackService": REPO_ROOT / "android-client/app/src/main/java/com/fnaudio/client/playback/PlaybackService.java",
    "AuthenticatedBitmapLoader": REPO_ROOT / "android-client/app/src/main/java/com/fnaudio/client/playback/AuthenticatedBitmapLoader.java",
    "FnConnectRelayConfigClient": REPO_ROOT / "android-client/app/src/main/java/com/fnaudio/client/network/FnConnectRelayConfigClient.java",
}

FACE_COUNT = 16
CARRIER_THRESHOLD = 14


def content_lines(path):
    """The repo-wide line count: split on LF and do not count the final newline."""
    text = path.read_text(encoding="utf-8")
    return len(text.split("\n")) - 1


def _faces_of(text):
    """Backticked source faces (file names or class names) inside some text."""
    found = []
    for token in BACKTICKED.findall(text):
        for part in token.split("/"):
            part = part.strip()
            if not FACE_TOKEN.match(part):
                continue
            if "." in part or CLASS_NAME.match(part):
                if part not in found:
                    found.append(part)
    return found


def entry_faces(line):
    """The faces an entry was written with; its appended round notes excluded.

    Everything from the first 「〔」 onward is a note added under the entry by a
    later round.  Such a note must not widen the scope of a *closed* entry, or
    ticking a box off would move the yardstick this gate is measured against --
    that is how the ledger grew a seventeenth "face" out of a note naming this
    very test file.
    """
    return _faces_of(line.split(NOTE_DELIMITER)[0])


def carried_faces(line):
    """Every face a live entry names today, its appended notes included.

    An open ledger entry grows through those notes; that is how this queue
    records faces discovered later, so for open entries the notes do count.
    """
    return _faces_of(line)


def canonical(face):
    """Collapse the one spelling alias on disk.

    The closed entry names the Android debt by class (``RemotePlaybackPlayer``)
    while the ledger registers it by file (``.../RemotePlaybackPlayer.java``).
    Those are the same face.  Nothing else is aliased, so ``app.css`` and
    ``app.js`` cannot collapse into a single ``app``.
    """
    stem = face[:-len(".java")] if face.endswith(".java") else face
    return stem if stem in ANDROID_LEDGER_FACES else face


def face_set(line, reader=entry_faces):
    """The distinct faces one entry line names, aliased and de-duplicated."""
    return {canonical(face) for face in reader(line)}


class ScopeEntrySubsumptionTests(unittest.TestCase):
    def setUp(self):
        text = TODO.read_text(encoding="utf-8")
        self.assertNotIn("\r", text, "TODO.md must stay LF-only before it is parsed")
        self.lines = text.split("\n")
        self.device_start = next(
            (index for index, line in enumerate(self.lines) if line.startswith(DEVICE_HEADING)),
            None,
        )
        self.assertIsNotNone(self.device_start, "the device segment must exist to bound the code bucket")
        self.closed = [
            (number, line)
            for number, line in enumerate(self.lines, start=1)
            if SUPERSEDED_MARKER in line
        ]
        self.successor = [
            (number, line)
            for number, line in enumerate(self.lines[: self.device_start], start=1)
            if SUCCESSOR_MARKER in line and OPEN_ITEM.match(line)
        ]

    def closed_entry(self):
        self.assertEqual(
            len(self.closed), 1,
            "the superseded scope entry must appear exactly once, found %d time(s)" % len(self.closed),
        )
        return self.closed[0]

    def successor_entry(self):
        self.assertEqual(
            len(self.successor), 1,
            "the live scope ledger must be one open code-bucket entry, found %s"
            % [number for number, _line in self.successor],
        )
        return self.successor[0]

    def test_superseded_scope_entry_is_closed_with_its_faces_intact(self):
        number, line = self.closed_entry()
        self.assertTrue(
            CLOSED_ITEM.match(line),
            "TODO.md line %d is the entry R59 says it replaced; reopening it double-counts the audit queue" % number,
        )
        named = entry_faces(line)
        self.assertEqual(
            len(named), FACE_COUNT,
            "TODO.md line %d must keep naming all %d audited faces, found %s" % (number, FACE_COUNT, named),
        )

    def test_exactly_one_open_entry_carries_the_audit_scope(self):
        # Pinned to the closed entry as written, notes excluded.
        wanted = face_set(self.closed_entry()[1])
        carriers = [
            (number, line)
            for number, line in enumerate(self.lines[: self.device_start], start=1)
            if OPEN_ITEM.match(line)
            and len(wanted & face_set(line, carried_faces)) >= CARRIER_THRESHOLD
        ]
        self.assertEqual(
            [number for number, _line in carriers], [self.successor_entry()[0]],
            "the audit-scope queue may be carried by exactly one open code-bucket entry, got %s"
            % [number for number, _line in carriers],
        )

    def test_no_face_of_the_closed_entry_is_orphaned(self):
        successor_text = self.successor_entry()[1]
        device_text = "\n".join(self.lines[self.device_start :])
        orphans = [
            face
            for face in sorted(face_set(self.closed_entry()[1]))
            if face not in successor_text and face not in device_text
        ]
        self.assertEqual(orphans, [], "closing the superseded entry must not lose an audited face")

    def test_guard_files_cited_by_the_ledger_still_exist(self):
        faces = [token for token in BACKTICKED.findall(self.successor_entry()[1])]
        cited = [m.group(1) for m in (GUARD_POINTER.match(t) for t in faces) if m]
        self.assertTrue(cited, "the ledger stopped pointing at any retirement guard")
        for name in sorted(cited):
            with self.subTest(guard=name):
                self.assertTrue((SRC / "tests" / name).is_file(), "%s is gone" % name)

    def test_folded_android_debts_point_at_real_sources(self):
        successor_text = self.successor_entry()[1]
        for name, path in ANDROID_LEDGER_FACES.items():
            with self.subTest(face=name):
                self.assertIn(name, successor_text, "the code ledger must name %s" % name)
                self.assertTrue(path.is_file(), "%s is not in the tree any more" % path)
                match = re.search(
                    REGISTERED.format(name=re.escape(path.name)), successor_text
                )
                self.assertIsNotNone(match, "the ledger registers no line count for %s" % path.name)
                self.assertEqual(
                    int(match.group(1).replace(",", "")), content_lines(path),
                    "the ledger line count for %s is stale" % path.name,
                )


if __name__ == "__main__":
    unittest.main()
