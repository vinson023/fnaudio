"""Keep the "still not deep-read" scope ledger counted exactly once.

The audit-scope queue was restated and never retired: R59 recorded that its
quantified list *replaced* the 2026-09-17 "file names only" entry, yet the
replaced entry stayed open.  Two open entries describing one queue is precisely
how the per-round counters drift away from the real bucket size, so this gate
recomputes the relationship from disk on every run:

* the superseded entry is found by a date-anchored marker, exists once, is
  closed, and still names all 16 audited faces in the text it was written with
  (emptying it would make the other checks vacuous),
* the drained face list may only be carried by closed entries: no open code-bucket
  entry may schedule it again, and exactly two closed rows carry it -- the
  superseded entry and the ledger that shut it.  A face counts under either its
  class or its file spelling, a shut entry keeps growing its notes, and the
  superseded entry's list is pinned to its own text so a note cannot move the
  yardstick,
* no face was dropped on the floor: each one has to be named again either by
  the successor entry or by the device segment, and
* the retirement guards the successor entry cites are still in the tree --
  whether a retired module really left it is the dedicated guards' business,
  and this file deliberately never names one of them.

"""

from pathlib import Path
import re
import tempfile
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

# R169 moved the round-by-round evidence these two open accounts accumulate into a
# file of its own, because a TODO line that carries every registration grows until
# rewriting it costs more than reading the code does.  The accounts stay open and
# keep their judgement text; only the accumulating detail moved, so the pointer and
# the single-carriage rule below are what keep the move honest.
AUDIT_LEDGER = "docs/AUDIT_LEDGER.md"
# The symbol account is the other open entry, pinned by the same phrase the bucket
# ledger uses to find it, so the two guards can never drift onto different lines.
SYMBOL_ACCOUNT_MARKER = "\u5269\u4f59\u7ea6 92% \u7b26\u53f7\u4ecd\u662f\u6d45\u8bfb\u9762"
NOTE_CLOSER = "\u3015"
# Registered blocks are long; their first characters agreeing is the block agreeing.
BLOCK_FINGERPRINT = 60


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


def read_lf_only(path, label):
    """Text of a naming source, rejecting anything that carries a carriage return.

    Both the TODO ledger and docs/AUDIT_LEDGER.md are parsed line-anchored, so a
    stray CRLF would silently defeat every regex rather than announce itself.
    ``read_text()`` cannot express that check: its universal-newline translation
    strips the CR before any assertion can see it.  Byte-level reads are therefore
    the only form of this rule that can fail, which the fixture below relies on.
    """
    raw = path.read_bytes()
    if b"\r" in raw:
        raise AssertionError("%s must stay LF-only" % label)
    return raw.decode("utf-8")


def note_blocks(text):
    """The per-round 「〔RNNN …〕」 blocks carried by some text, in order.

    These blocks are how a round registers what it read.  Before R169 they piled up
    inside the two open TODO accounts; now they belong to docs/AUDIT_LEDGER.md, which
    makes "one block, one carrier" checkable instead of merely intended.
    """
    return [
        chunk.split(NOTE_CLOSER)[0].strip()
        for chunk in text.split(NOTE_DELIMITER)[1:]
        if chunk.split(NOTE_CLOSER)[0].strip()
    ]


def face_set(line, reader=entry_faces):
    """The distinct faces one entry line names, aliased and de-duplicated."""
    return {canonical(face) for face in reader(line)}


class ScopeEntrySubsumptionTests(unittest.TestCase):
    def setUp(self):
        self.lines = read_lf_only(TODO, "TODO.md").split("\n")
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
            if SUCCESSOR_MARKER in line
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
            "the scope ledger must be one code-bucket entry, found %s"
            % [number for number, _line in self.successor],
        )
        number, line = self.successor[0]
        self.assertTrue(
            CLOSED_ITEM.match(line),
            "TODO.md line %d is the shut scope ledger; an open copy here is the "
            "drained queue coming back" % number,
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

    def test_the_drained_audit_scope_is_carried_only_by_closed_entries(self):
        # Pinned to the closed entry as written, notes excluded.  The law is
        # two-sided: an open carrier means the drained queue is scheduled again,
        # and a third closed carrier means one queue is counted twice -- which is
        # exactly how the per-round counters drifted away from the real bucket size.
        wanted = face_set(self.closed_entry()[1])
        carriers = [
            (number, line)
            for number, line in enumerate(self.lines[: self.device_start], start=1)
            if len(wanted & face_set(line, carried_faces)) >= CARRIER_THRESHOLD
        ]
        self.assertEqual(
            [number for number, line in carriers if OPEN_ITEM.match(line)], [],
            "no open code-bucket entry may carry the audit-scope face list any more",
        )
        self.assertEqual(
            sorted(number for number, _line in carriers),
            sorted([self.successor_entry()[0], self.closed_entry()[0]]),
            "the audit-scope face list belongs to the shut ledger and the entry it "
            "superseded, got %s" % [number for number, _line in carriers],
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


    def deep_read_accounts(self):
        """Both deep-read accounts, located the way the sibling guards pin them.

        R173 drained the queue they measure and shut both, so the shape returned
        here is a closed pair: one row per marker, on two different lines, and no
        open row carrying either marker.  A shut account found open again puts one
        queue under two ledgers, which is the double count this file exists to stop.
        """
        accounts = [self.successor_entry()]
        symbol = [
            (number, line)
            for number, line in enumerate(self.lines[: self.device_start], start=1)
            if SYMBOL_ACCOUNT_MARKER in line
        ]
        self.assertEqual(
            len(symbol), 1,
            "the app.js symbol account must be exactly one code-bucket entry, found %d" % len(symbol),
        )
        self.assertTrue(
            CLOSED_ITEM.match(symbol[0][1]),
            "TODO.md line %d is the shut symbol account; an open copy here is the "
            "symbol queue coming back" % symbol[0][0],
        )
        accounts.append(symbol[0])
        self.assertEqual(
            len({number for number, _line in accounts}), len(accounts),
            "the two deep-read accounts collapsed onto one line",
        )
        for marker in (SUCCESSOR_MARKER, SYMBOL_ACCOUNT_MARKER):
            reopened = [
                number
                for number, line in enumerate(self.lines[: self.device_start], start=1)
                if marker in line and OPEN_ITEM.match(line)
            ]
            self.assertEqual(
                reopened, [],
                "an open code-bucket entry re-schedules the shut account %r" % marker,
            )
        return accounts

    def test_the_external_ledger_exists_and_is_named_by_both_deep_read_accounts(self):
        # The ledger is now a naming source for tools/audit_coverage.py, so a reader who
        # follows either account has to be able to find it.  An account that stops
        # pointing at the file it delegated its detail to would send the next round
        # back to appending inside TODO.md, which is the growth this move prevents.
        ledger = REPO_ROOT / AUDIT_LEDGER
        self.assertTrue(ledger.is_file(), "%s is missing from the tree" % AUDIT_LEDGER)
        text = read_lf_only(ledger, AUDIT_LEDGER)
        self.assertTrue(text.lstrip().startswith("# "), "%s lost its heading" % AUDIT_LEDGER)
        for number, line in self.deep_read_accounts():
            with self.subTest(account=number):
                self.assertIn(
                    "`%s`" % AUDIT_LEDGER, line,
                    "TODO.md line %d no longer names the ledger holding its detail" % number,
                )

    def test_no_registered_block_is_carried_twice(self):
        # Copying without deleting is how an externalisation silently fails: the detail
        # would live in two places, and the TODO line it was supposed to leave would keep
        # growing.  Deleting without copying is the other half of the same accident, and
        # the tools/audit_coverage.py side of this pair re-computes the symbols, so a
        # block lost by both carriers cannot be hidden here.
        ledger_blocks = note_blocks((REPO_ROOT / AUDIT_LEDGER).read_text(encoding="utf-8"))
        self.assertGreater(
            len(ledger_blocks), 1,
            "%s carries no migrated registrations" % AUDIT_LEDGER,
        )
        fingerprints = {
            block[:BLOCK_FINGERPRINT]
            for block in ledger_blocks
            if len(block) >= BLOCK_FINGERPRINT
        }
        self.assertEqual(
            len(fingerprints), len([b for b in ledger_blocks if len(b) >= BLOCK_FINGERPRINT]),
            "the ledger registers the same block twice",
        )
        for number, line in self.deep_read_accounts():
            for block in note_blocks(line):
                with self.subTest(account=number, block=block[:24]):
                    self.assertNotIn(
                        block[:BLOCK_FINGERPRINT], fingerprints,
                        "TODO.md line %d still carries a block the ledger already holds" % number,
                    )


    def test_the_lf_rule_rejects_a_ledger_that_carries_carriage_returns(self):
        # Positive control for the reader above.  Without it the rule is only a
        # statement about a file that happens to be clean today: a future round
        # that rewrites docs/AUDIT_LEDGER.md through a Windows-flavoured editor,
        # or a guard that quietly regresses to read_text(), would keep passing.
        clean = (REPO_ROOT / AUDIT_LEDGER).read_bytes()
        self.assertNotIn(b"\r", clean, "the fixture needs the ledger to start LF-only")
        with tempfile.TemporaryDirectory() as scratch:
            lf_path = Path(scratch) / "ledger.md"
            crlf_path = Path(scratch) / "ledger-crlf.md"
            lf_path.write_bytes(clean)
            crlf_path.write_bytes(clean.replace(b"\n", b"\r\n"))
            self.assertEqual(
                read_lf_only(lf_path, "clean fixture"),
                clean.decode("utf-8"),
                "the reader rejects a file it should accept",
            )
            with self.assertRaises(AssertionError) as caught:
                read_lf_only(crlf_path, "CRLF fixture")
            self.assertIn("LF-only", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
