"""R168: the app.js deep-read queue is computed by a tool, so the tool gets tests.

Before R168 every round re-derived "which app.js symbols have the three root
records never named" with a throwaway script under %TEMP%, deleted again at the end
of the round, leaving the answer only in prose the next round had to trust.
``tools/audit_coverage.py`` makes that derivation permanent.  This file is what
keeps it honest, and each test exists to kill one specific way the derivation can
drift:

* substring naming instead of word-boundary naming (``loadLibraryResponse`` must
  not count as naming ``loadLibrary`` -- that drift moves a historical count);
* the two naming implementations disagreeing with each other;
* a symbol index that stops being line-anchored, or stops being one row per
  declaration;
* face grouping that swallows or drops a symbol, so the queue no longer partitions
  the debt;
* a face-gap boundary that is off by one;
* ranking that becomes span- or density-primary, or input-order dependent;
* identifier characters (``$``, digits) silently dropped from the tokenizer;
* a historical count frozen into either file, which would turn a working tree into
  a red gate the moment app.js changes.

No expected count is hard-coded here: every figure is recomputed from the
repository, or from a fixture whose content this file controls.
"""

import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "audit_coverage.py"
_SPEC = importlib.util.spec_from_file_location("fnaudio_audit_coverage", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

REPO_ROOT = Path(__file__).resolve().parents[2]
NL = "\n"

# The naming source R169 externalised out of the two TODO ledger lines.
LEDGER = "docs/AUDIT_LEDGER.md"

# R173 drained the queue, so this file's non-vacuity measure can no longer be "some
# symbol is still unread": the invariant is now a ratchet, and the two deep-read
# accounts it is coupled to are located by anchor phrase -- never by line number,
# because every recorded round prepends above them.
TODO = REPO_ROOT / "TODO.md"
DEEP_READ_ACCOUNTS = (
    "\u91cf\u5316\u6210\u53ef\u6392\u671f\u7684\u6e05\u5355",
    "\u5269\u4f59\u7ea6 92% \u7b26\u53f7\u4ecd\u662f\u6d45\u8bfb\u9762",
)


def deep_read_account_states():
    """(open, closed) hit counts per anchor phrase, over TODO.md checklist rows."""
    lines = TODO.read_text(encoding="utf-8").split(NL)
    states = []
    for anchor in DEEP_READ_ACCOUNTS:
        rows = [line for line in lines if anchor in line and (
            line.startswith("- [ ] ") or line.startswith("- [x] "))]
        states.append((
            anchor,
            sum(1 for line in rows if line.startswith("- [ ] ")),
            sum(1 for line in rows if line.startswith("- [x] ")),
        ))
    return states


FROZEN_COUNTS = (
    "286",
    "381",
    "461",
    "463",
    "462",
    "918",
    "175",
    "183",
    "8530",
    "9695",
)


def independent_index(text):
    """A second, deliberately different implementation of the symbol anchor."""
    names = []
    for line in text.split(NL):
        if line.startswith("function ") or line.startswith("async function "):
            match = re.match(r"^(?:async )?function +([A-Za-z_$][A-Za-z0-9_$]*)", line)
            if match:
                names.append(match.group(1))
    return names


def independent_named(names, blobs):
    """Split every document on non-identifier characters, then test membership.

    The tool answers "is this name written as its own word?" twice over: a token
    scan, and per-name lookarounds.  This uses neither.  Three implementations
    that disagree is exactly the measurement drift R165 had to re-derive by hand.
    """
    tokens = set()
    for blob in blobs:
        tokens.update(re.split(r"[^A-Za-z0-9_$]+", blob))
    return {name for name in names if name in tokens}


def make_app(spans):
    """Build app.js text with one-line function bodies at the given line numbers."""
    last = max(start for _name, start in spans)
    lines = ["// filler"] * last
    for name, start in spans:
        lines[start - 1] = "function %s() { /* one line */ }" % name
    return NL.join(lines)


def write_repo(root, app_text, records):
    target = root / _MODULE.TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(app_text.encode("utf-8"))
    # R169 grew the naming sources from three to four, and a fixture may
    # legitimately leave the newest one off disk to prove that an absent
    # source names nothing -- so the contract is "at most one record per
    # naming source", never "exactly the number this file last remembered".
    assert len(records) <= len(_MODULE.ROOT_DOCS), records
    for relative, text in zip(_MODULE.ROOT_DOCS, records):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))


class AuditCoverageRealRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _MODULE.read_text(REPO_ROOT, _MODULE.TARGET)
        cls.symbols = _MODULE.index_functions(cls.text)
        cls.names = [entry["name"] for entry in cls.symbols]
        cls.blobs = [_MODULE.read_text(REPO_ROOT, relative) for relative in _MODULE.ROOT_DOCS]
        cls.named = independent_named(cls.names, cls.blobs)
        cls.result = _MODULE.measure(REPO_ROOT)

    def test_the_two_naming_implementations_agree_on_this_repository(self):
        per_name = _MODULE.reference_named(self.names, "".join(self.blobs))
        token_scan = _MODULE.token_named(self.names, self.blobs)
        self.assertEqual(per_name, token_scan)
        self.assertEqual(self.named, set(token_scan))
        self.assertEqual(self.result["named_symbols"], len(per_name))

    def test_the_reported_zero_named_count_is_reproducible_from_first_principles(self):
        unnamed = [entry for entry in self.symbols if entry["name"] not in self.named]
        self.assertEqual(self.result["zero_named_symbols"], len(unnamed))
        self.assertGreater(self.result["named_symbols"], 0,
                           "nothing is named: this guard measures nothing")
        self.assertEqual(
            self.result["zero_named_symbols"],
            sum(face["count"] for face in self.result["faces"]),
        )
        self.assertEqual(
            self.result["symbols"],
            self.result["named_symbols"] + self.result["zero_named_symbols"],
        )

    def test_the_queue_is_drained_and_the_accounts_are_shut(self):
        # R173 closed the last deep-read face.  From here on "still unread" is not a
        # state this repository may sit in: a round that adds a declaration without
        # registering it, or deletes one without retiring its name, reddens here --
        # which is termination clause (1) measured mechanically instead of by prose.
        unnamed = sorted(entry["name"] for entry in self.symbols if entry["name"] not in self.named)
        self.assertEqual(unnamed, [], "app.js symbols the records never named came back: %s" % unnamed)
        self.assertEqual(self.result["faces"], [], "a drained queue cannot hold faces")
        for anchor, opened, closed in deep_read_account_states():
            self.assertEqual((opened, closed), (0, 1),
                             "TODO.md must record this deep-read account as shut exactly once: " + anchor)

    def test_the_symbol_index_is_line_anchored_and_unique(self):
        self.assertEqual(len(self.symbols), len(independent_index(self.text)))
        self.assertEqual(self.result["symbols"], self.result["unique_symbols"])
        self.assertEqual(self.result["target_content_lines"], len(self.text.split(NL)) - 1)
        lines = self.text.split(NL)
        for entry in self.symbols:
            self.assertFalse(lines[entry["start"] - 1][:1].isspace(), entry["name"])

    def test_the_queue_partitions_the_debt_exactly_once(self):
        ordered = sorted(self.result["faces"], key=lambda face: face["start"])
        for face, following in zip(ordered, ordered[1:]):
            self.assertLess(face["end"], following["start"], "two faces overlap")
        for face in self.result["faces"]:
            self.assertEqual(face["span"], face["end"] - face["start"] + 1)
            self.assertEqual(face["count"], face["held"], "a symbol was swallowed: %r" % face)
            in_span = [
                entry
                for entry in self.symbols
                if face["start"] <= entry["start"] <= face["end"]
            ]
            self.assertEqual(
                face["symbols"],
                [entry["name"] for entry in in_span if entry["name"] not in self.named],
            )
            self.assertEqual(face["named_inside"], len(in_span) - face["count"])
        listed = [name for face in self.result["faces"] for name in face["symbols"]]
        self.assertEqual(len(listed), len(set(listed)), "a symbol is queued twice")
        self.assertEqual(
            set(listed),
            {entry["name"] for entry in self.symbols if entry["name"] not in self.named},
        )

    def test_the_densest_face_is_queued_first(self):
        counts = [face["count"] for face in self.result["faces"]]
        self.assertEqual(counts, sorted(counts, reverse=True))
        # ``min(counts)`` raises on a drained queue; the law it stood for -- a queued
        # face always holds a symbol -- is stated directly and stays measured, while
        # the ranking itself is exercised on fixtures that own their rows.
        self.assertTrue(all(count >= 1 for count in counts), "a face was queued holding no symbol")

    def test_the_json_answer_has_the_declared_shape_and_the_same_numbers(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = _MODULE.main(["--json"])
        text = buffer.getvalue()
        self.assertEqual(code, 0, text)
        payload = json.loads(text)
        self.assertEqual(tuple(payload), _MODULE.REPORT_KEYS)
        for face in payload["faces"]:
            self.assertEqual(tuple(face), _MODULE.FACE_KEYS)
        self.assertEqual(payload, self.result)

    def test_the_text_report_prints_zero_named_rather_than_named(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = _MODULE.main(["--limit", "3"])
        text = buffer.getvalue()
        self.assertEqual(code, 0, text)
        self.assertIn("zero_named=%d" % self.result["zero_named_symbols"], text)
        self.assertIn("named=%d" % self.result["named_symbols"], text)
        self.assertIn("faces=%d" % len(self.result["faces"]), text)
        self.assertTrue(text.startswith("target="), "the report lost its header block")
        self.assertEqual(
            len([line for line in text.split(NL) if line.startswith("#")]),
            min(len(self.result["faces"]), 3),
            "--limit caps the ranked rows, it does not invent them",
        )

    def test_the_ledger_holds_naming_evidence_no_other_source_holds(self):
        # The ledger exists because the registrations left the two TODO accounts, and the
        # tool reads it as a naming source.  Two accidents defeat that: a migration that
        # deletes from both files quietly re-opens every symbol it "moved", and a copy
        # that deletes nothing leaves the ledger redundant.  Both show up the same way --
        # the ledger stops being the only carrier of any name -- so that is what is
        # asserted, without pinning how many symbols any round has ever named.
        ledger = _MODULE.read_text(REPO_ROOT, LEDGER)
        self.assertTrue(ledger.strip(), "the external ledger is empty")
        others = [
            _MODULE.read_text(REPO_ROOT, relative)
            for relative in _MODULE.ROOT_DOCS
            if relative != LEDGER
        ]
        without_ledger = independent_named(self.names, others)
        self.assertLess(
            len(without_ledger),
            len(self.named),
            "the ledger adds no naming evidence: migrated registrations are missing or duplicated",
        )

    def test_no_historical_count_is_frozen_into_either_side_of_the_tool(self):
        tool = _MODULE_PATH.read_text(encoding="utf-8")
        guard = Path(__file__).resolve().read_text(encoding="utf-8")
        head, _, tail = guard.partition("FROZEN_COUNTS = (")
        declaration, _, rest = tail.partition(")")
        self.assertTrue(declaration, "this guard lost its list of historical counts")
        outside = head + rest
        for number in FROZEN_COUNTS:
            pattern = r"(?<![0-9])" + number + r"(?![0-9])"
            self.assertIsNone(re.search(pattern, tool), "frozen into the tool: " + number)
            self.assertIsNone(re.search(pattern, outside), "frozen into this guard: " + number)
            self.assertIn('"%s",' % number, declaration, "this guard stopped checking: " + number)


class AuditCoverageFixtureTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)

    def measure(self, app_text, records, gap=None):
        write_repo(self.root, app_text, records)
        result = (
            _MODULE.measure(self.root)
            if gap is None
            else _MODULE.measure(self.root, gap)
        )
        return self.assert_queue_adds_up(result)

    def assert_queue_adds_up(self, result):
        """Apply the structural laws of the real report to every fixture too.

        These are the same three checks the repository-level guard applies to
        this working tree.  Running them on hand-made files is what keeps a
        grouping or accounting mutation from surviving just because the current
        repository happens to look consistent.
        """
        self.assertEqual(
            result["zero_named_symbols"],
            sum(face["count"] for face in result["faces"]),
            "the faces do not account for the debt: %r" % (result["faces"],),
        )
        for face in result["faces"]:
            self.assertEqual(
                face["held"],
                face["count"],
                "a symbol was swallowed or double-counted: %r" % (face,),
            )
            self.assertEqual(
                face["span"],
                face["end"] - face["start"] + 1,
                "the span does not match its own bounds: %r" % (face,),
            )
        return result

    def test_a_longer_name_does_not_name_the_shorter_one(self):
        app = NL.join(
            [
                "function loadLibrary() { /* a */ }",
                "function loadLibraryResponse() { /* b */ }",
            ]
        )
        result = self.measure(app, ("`loadLibraryResponse`", "", ""))
        self.assertEqual(result["symbols"], 2)
        self.assertEqual(result["named_symbols"], 1)
        self.assertEqual(result["zero_named_symbols"], 1)
        self.assertEqual(result["faces"][0]["symbols"], ["loadLibrary"])
        self.assertEqual(
            _MODULE.reference_named(
                ["loadLibrary", "loadLibraryResponse"], "`loadLibraryResponse`"
            ),
            frozenset({"loadLibraryResponse"}),
        )
        both = self.measure(app, ("`loadLibraryResponse` `loadLibrary`", "", ""))
        self.assertEqual(both["zero_named_symbols"], 0)
        self.assertEqual(both["faces"], [])

    def test_dollar_signs_and_digits_stay_inside_a_name(self):
        app = NL.join(
            [
                "function $foo() { /* a */ }",
                "function x9() { /* b */ }",
                "function clampTrackColumnWidth() { /* c */ }",
            ]
        )
        records = ("$foo x9y clampTrackColumnWidths", "", "")
        result = self.measure(app, records)
        self.assertEqual(result["named_symbols"], 1)
        self.assertEqual(
            sorted(name for face in result["faces"] for name in face["symbols"]),
            ["clampTrackColumnWidth", "x9"],
        )
        self.assertEqual(
            _MODULE.token_named(["$foo", "x9", "clampTrackColumnWidth"], [records[0]]),
            frozenset({"$foo"}),
        )

    def test_every_declaration_is_one_row_and_the_unique_count_is_the_name_set(self):
        app = NL.join(
            [
                "function dup() { /* first */ }",
                "function dup() { /* second */ }",
                "function other() { /* third */ }",
            ]
        )
        result = self.measure(app, ("", "", ""))
        self.assertEqual(result["symbols"], 3)
        self.assertEqual(result["unique_symbols"], 2)
        self.assertEqual(result["zero_named_symbols"], 3)
        self.assertEqual(result["faces"][0]["count"], 3)

    def test_a_named_duplicate_owes_nothing_the_queue_cannot_hold(self):
        # Two declarations share one name and that name *is* named.  Counting the
        # debt by subtracting named names from total names would report 2 here
        # while the queue can only ever hold 1, so the definition matters.
        app = NL.join(
            [
                "function dup() { /* first */ }",
                "function dup() { /* second */ }",
                "function owing() { /* third */ }",
            ]
        )
        result = self.measure(app, ("dup", "", ""))
        self.assertEqual(result["symbols"], 3)
        self.assertEqual(result["unique_symbols"], 2)
        self.assertEqual(result["named_symbols"], 1)
        self.assertEqual(result["zero_named_symbols"], 1)
        self.assertEqual([face["symbols"] for face in result["faces"]], [["owing"]])

    def test_the_face_gap_boundary_splits_on_one_more_line(self):
        gap = _MODULE.DEFAULT_GAP_LINES
        # A named function has to separate the two unread ones: without it the
        # previous face's end is literally the next symbol's start minus one, so no
        # gap can ever appear, and a bug in the boundary would be invisible.
        for extra, expected in ((gap - 2, 1), (gap - 1, 2)):
            with self.subTest(extra=extra):
                app = make_app([("alpha", 1), ("helper", 2), ("beta", 3 + extra)])
                result = self.measure(app, ("helper", "", ""))
                self.assertEqual(len(result["faces"]), expected)
                self.assertEqual(sum(face["count"] for face in result["faces"]), 2)

    def test_ranking_is_by_held_symbols_before_span_or_density(self):
        app = make_app(
            [
                ("solo_one", 1),
                ("keeper_one", 2),
                ("solo_two", 100),
                ("keeper_two", 101),
                ("big_one", 400),
                ("big_two", 401),
                ("big_three", 402),
                ("big_four", 403),
                ("big_five", 404),
            ]
        )
        result = self.measure(app, ("keeper_one keeper_two", "", ""))
        self.assertEqual([face["count"] for face in result["faces"]], [5, 1, 1])
        self.assertEqual(result["faces"][0]["symbols"][0], "big_one")
        self.assertEqual(result["faces"][1]["start"], 1)
        self.assertEqual(result["faces"][2]["start"], 100)

    def test_a_wider_gap_merges_faces_and_still_accounts_for_every_symbol(self):
        app = make_app([("alpha", 1), ("helper", 2), ("beta", 60)])
        baseline = self.measure(app, ("helper", "", ""))
        self.assertEqual([face["count"] for face in baseline["faces"]], [1, 1])
        merged = self.measure(app, ("helper", "", ""), baseline["gap_lines"] + 60)
        self.assertEqual(len(merged["faces"]), 1)
        face = merged["faces"][0]
        self.assertEqual(face["count"], 2)
        self.assertEqual(face["held"], 2)
        self.assertEqual(face["named_inside"], 1)
        self.assertEqual(face["symbols"], ["alpha", "beta"])

    def test_the_external_ledger_retires_symbols_like_a_root_record(self):
        # The deep-read evidence used to live inside two TODO lines, which grew until
        # rewriting them cost more than reading the code.  It now lives in its own
        # file, so that file has to carry the same authority: naming a symbol only in
        # the ledger must remove it from the queue even when no root record mentions it.
        self.assertEqual(_MODULE.ROOT_DOCS[-1], LEDGER)
        app = NL.join(
            [
                "function root_named() { /* a */ }",
                "function ledger_named() { /* b */ }",
                "function owing() { /* c */ }",
            ]
        )
        result = self.measure(app, ("root_named", "", "", "ledger_named"))
        self.assertEqual(result["named_symbols"], 2)
        self.assertEqual(result["zero_named_symbols"], 1)
        self.assertEqual([face["symbols"] for face in result["faces"]], [["owing"]])

    def test_the_text_report_ranks_rows_and_the_limit_caps_them(self):
        # This law used to be read off the real repository, where the queue was long
        # enough to demonstrate it.  R173 drained that queue, so a fixture owns the
        # rows now: four faces of one symbol each, and 「limit three」 must drop the
        # fourth rather than the ranking.
        # The four unread faces need a named declaration between each pair: the
        # symbol index ends a one-line function at the line before the *next*
        # declaration, so without a named neighbour every gap measures one line
        # and the four faces collapse into one.  The keepers carry the names, so
        # they stay out of the queue while still bounding their neighbours.
        app = make_app(
            [
                ("solo_one", 1),
                ("keeper_a", 2),
                ("solo_two", 60),
                ("keeper_b", 61),
                ("solo_three", 120),
                ("keeper_c", 121),
                ("solo_four", 180),
            ]
        )
        write_repo(self.root, app, ("keeper_a keeper_b keeper_c", "", ""))
        result = _MODULE.measure(self.root)
        self.assertEqual([face["count"] for face in result["faces"]], [1, 1, 1, 1])
        ranked = [line for line in _MODULE.format_report(result).split(NL) if line.startswith("#")]
        self.assertEqual([line.split()[0] for line in ranked], ["#1", "#2", "#3", "#4"])
        self.assertIn("solo_one", ranked[0])
        self.assertIn("solo_four", ranked[-1])
        limited = [line for line in _MODULE.format_report(result, 3).split(NL) if line.startswith("#")]
        self.assertEqual(len(limited), 3, "the limit printed every row")
        self.assertIn("solo_three", limited[-1])
        self.assertNotIn("solo_four", "\n".join(limited))
        drained = self.measure("function all_named() { /* a */ }", ("all_named", "", ""))
        self.assertEqual(drained["faces"], [])
        rows = [line for line in _MODULE.format_report(drained, 3).split(NL) if line.startswith("#")]
        self.assertEqual(rows, [], "an empty queue must print header lines only")
        self.assertIn("faces=0", _MODULE.format_report(drained, 3))

    def test_an_absent_ledger_names_nothing_instead_of_failing_the_measure(self):
        # A round that has not created the ledger yet must still get a queue; treating
        # a missing naming source as an error would make the externalisation itself
        # un-runnable, and treating it as an empty *string* would be the same lie.
        app = NL.join(
            ["function owing_one() { /* a */ }", "function owing_two() { /* b */ }"]
        )
        result = self.measure(app, ("", "", ""))
        self.assertFalse((self.root / LEDGER).exists())
        self.assertEqual(result["symbols"], 2)
        self.assertEqual(result["named_symbols"], 0)
        self.assertEqual(result["zero_named_symbols"], 2)

if __name__ == "__main__":
    unittest.main()