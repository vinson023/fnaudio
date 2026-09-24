"""R164: pin the decision bucket to a count any future round can re-measure.

The owner has given a standing ruling that replaces per-item consultation: every
open decision is now taken by Codex on its own best judgement and recorded.  A
decision bucket which merely *reads* as still waiting is therefore actively harmful
-- worse than a code defect, because a future round will stop and ask again instead
of working.  Two prose records inside the bucket say so in as many words:

* "本段 8 条" (R77) and "本段 8 条 ... 待决 3 条" (R121): six in-bucket count
  declarations, none of which matches what the checklist rows measure today;
* "继续保留在决策段等待负责人逐条给方向" -- an instruction to stall.

The measured truth on disk is 9 checklist items and 0 open.  Historical numbers must
not be rewritten (docs/REVIEW_ROUND_DISCIPLINE.md section five: measured values are
only ever added as re-countable evidence), so R164 appends one standing-ruling
record and this guard makes the pair mechanically checkable:

1. the bucket header appears exactly once and the bucket ends at the next "## ";
2. the measured item count, and the identity of every item in order, are pinned, so
   no row can be silently deleted, renamed or smuggled in without a recorded round;
3. the measured open count is 0 -- the machine proof for termination clause (3);
4. the standing-ruling record exists exactly once and quotes both measured numbers;
5. every in-bucket count declaration that disagrees with the measurement is covered
   by that record, and the check refuses to pass vacuously;
6. every phrase telling a future round to wait for the owner sits in a dated
   historical record and is overridden by that same ruling;
7. the offline code bucket holds neither of the two deep-read debts that used to
   gate termination clause (1) -- both were shut by R173 and each survives as
   exactly one closed row -- so a decision record can never be mistaken for
   unfinished code work, and re-opening one cannot be mistaken for paying it off;
8. the ruling does not leak outside the decision bucket.

Deliberately not pinned: the wording of the historical records themselves.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TODO = REPO_ROOT / "TODO.md"

DECISION_HEADER = "## 需要项目负责人决策"
STANDING_RULING_PREFIX = "2026-09-23（R164 常设裁定"

CHECKLIST = re.compile(r"^- \[( |x)\] ")
D_ID = re.compile(r"D\d")
ROUND_ID = re.compile(r"R\d+(?= 新开| 数据面)")
COUNT_DECLARATION = re.compile(r"(?:本段|待决|关闭|保持开启|新开)\s*(\d+)\s*条")
STALLING_PHRASE = re.compile("等待负责人|待负责人给方向|需要负责人一句话|请负责人给方向|向负责人征询")
DATED_RECORD = re.compile(r"^2026-\d\d-\d\d（R\d+ ")
RECORD_TAG = re.compile(r"^2026-\d\d-\d\d（(R\d+) ")

# Measured 2026-09-23 against TODO.md: nine rows, none open.  A round that
# legitimately changes the bucket must change this list in the same commit.
PINNED_ITEM_IDS = ["D1", "D2", "D3", "D4", "R73", "R71", "R71", "R70", "D9"]

# The whole of the offline code bucket as measured on 2026-09-23: the two deep-read
# debts.  Located by text, never by line number -- every recorded round prepends
# above them.  Clearing one is the job of the round that reads the last face out.
OPEN_CODE_ITEMS = (
    "R59 把「还没审计的部分」量化成可排期的清单",
    "剩余约 92% 符号仍是浅读面",
)


def read_lines():
    return TODO.read_text(encoding="utf-8").split("\n")


def locate_bucket(all_lines):
    hits = [i for i, line in enumerate(all_lines) if line.strip() == DECISION_HEADER]
    if len(hits) != 1:
        raise AssertionError(
            "expected exactly one %r header in TODO.md, found %d" % (DECISION_HEADER, len(hits))
        )
    start = hits[0]
    end = next(
        (j for j in range(start + 1, len(all_lines)) if all_lines[j].startswith("## ")),
        len(all_lines),
    )
    return start, end, all_lines[start + 1 : end]


def rows_of(bucket):
    return [line for line in bucket if CHECKLIST.match(line)]


def open_of(bucket):
    return sum(1 for line in rows_of(bucket) if line.startswith("- [ ] "))


def ruling_of(bucket):
    return [line for line in bucket if line.startswith(STANDING_RULING_PREFIX)]


def item_id(row):
    """Stable handle for a decision row: its D-number when it has one.

    Several rows open with a dated 〔R###〕 provenance tag, so a single combined
    alternation would report the provenance round instead of the decision id: the
    D-number is looked for on its own first, and only rows that never had one
    (the 「新开」 findings R70/R71/R73) fall back to their round tag.
    """
    direct = D_ID.search(row)
    if direct:
        return direct.group(0)
    fallback = ROUND_ID.search(row)
    return fallback.group(0) if fallback else None


def stale_counts(bucket):
    """Count declarations in the bucket that disagree with the measurement.

    The standing ruling is excluded: it *quotes* the stale numbers on purpose, so
    counting its quotations as stale would make the coverage assertion in
    test_conflicting_count_declarations_are_covered circular.
    """
    measured = (len(PINNED_ITEM_IDS), open_of(bucket))
    found = []
    for line in bucket:
        if line.startswith(STANDING_RULING_PREFIX):
            continue
        for match in COUNT_DECLARATION.finditer(line):
            if int(match.group(1)) not in measured:
                found.append(match.group(0))
    return found


def stale_source_tags(bucket):
    """Round tag of every dated record that still asserts a stale count."""
    measured = (len(PINNED_ITEM_IDS), open_of(bucket))
    tags = []
    for line in bucket:
        if line.startswith(STANDING_RULING_PREFIX):
            continue
        if not any(int(m.group(1)) not in measured for m in COUNT_DECLARATION.finditer(line)):
            continue
        tag = RECORD_TAG.match(line)
        if tag:
            tags.append(tag.group(1))
    return tags


class DecisionBucketLedger(unittest.TestCase):
    def setUp(self):
        self.all_lines = read_lines()
        self.start, self.end, self.bucket = locate_bucket(self.all_lines)
        self.rows = rows_of(self.bucket)

    def test_bucket_is_located_by_text_not_line_number(self):
        self.assertLess(self.start, self.end)
        self.assertEqual(DECISION_HEADER, self.all_lines[self.start].strip())

    def test_item_count_and_identity_are_pinned(self):
        self.assertEqual(
            len(PINNED_ITEM_IDS),
            len(self.rows),
            "the decision bucket changed size without a recorded round",
        )
        found = []
        for row in self.rows:
            ident = item_id(row)
            self.assertIsNotNone(ident, "a decision row carries no stable id: " + row[:80])
            found.append(ident)
        self.assertEqual(PINNED_ITEM_IDS, found)

    def test_decision_bucket_measures_zero_open(self):
        self.assertEqual(
            0, open_of(self.bucket), "termination clause (3) needs the decision bucket at zero open"
        )

    def test_standing_ruling_record_exists_and_quotes_the_measurement(self):
        ruling = ruling_of(self.bucket)
        self.assertEqual(1, len(ruling), "expected exactly one standing-ruling record")
        text = ruling[0]
        self.assertIn("%d 条" % len(PINNED_ITEM_IDS), text)
        self.assertIn("0 条", text)
        # Pin the clauses that do the work, in the form that does it.  A bare
        # assertIn("历史口径") is worthless here: the phrase also occurs in the
        # row\'s own closing summary, so half-deleting the override sentence would
        # still read green -- that is mutation M12, which survived the first pass
        # of this guard.
        self.assertIn("均为各自轮次当时的**历史口径**", text)
        self.assertIn("也不再生效", text)
        self.assertIn("不再阻塞", text)

    def test_conflicting_count_declarations_are_covered(self):
        stale = stale_counts(self.bucket)
        self.assertTrue(stale, "guard is vacuous: no stale count declaration left to cover")
        ruling = ruling_of(self.bucket)
        self.assertEqual(
            1,
            len(ruling),
            "stale in-bucket counts are uncovered by a standing ruling: %r" % (stale,),
        )
        text = ruling[0]
        # Coverage, not presence: every number the bucket still asserts wrongly has
        # to be quoted inside the ruling, and every record that asserts one has to
        # be named by its round tag.  Without this, assertion 5 only proved that a
        # row starting with the magic prefix exists, and the ruling could keep its
        # wording while quietly stopping saying what it overrides -- that is
        # mutation M14/M15, both of which survived the first pass.
        for declaration in sorted(set(stale)):
            self.assertIn(declaration, text, "ruling does not quote the stale count: " + declaration)
        tags = sorted(set(stale_source_tags(self.bucket)))
        self.assertTrue(tags, "guard is vacuous: no dated record asserts a stale count")
        for tag in tags:
            self.assertIn(tag, text, "ruling does not name the record it overrides: " + tag)

    def test_stalling_phrases_are_historical_and_overridden(self):
        stalling = [line for line in self.bucket if STALLING_PHRASE.search(line)]
        self.assertTrue(stalling, "guard is vacuous: no stalling phrase left to bound")
        for line in stalling:
            if line.startswith(STANDING_RULING_PREFIX):
                continue
            self.assertTrue(DATED_RECORD.match(line), "stalling text must sit in a dated record: " + line[:80])
        self.assertEqual(1, len(ruling_of(self.bucket)))

    def test_offline_code_bucket_holds_exactly_the_deep_read_debts(self):
        # The anchors themselves stay: they are how this bucket states what is no
        # longer in it.  R173 shut both debts, so each has to appear as exactly one
        # closed row and in no open row at all -- a second open row would double the
        # measured bucket, and a vanished anchor would hide that it was deleted
        # rather than paid.
        open_rows = [line for line in self.all_lines if line.startswith("- [ ] ")]
        self.assertTrue(open_rows, "TODO.md has no open checklist row at all")
        for anchor in OPEN_CODE_ITEMS:
            self.assertEqual(
                0,
                len([line for line in open_rows if anchor in line]),
                "a shut deep-read debt is open again in the code bucket: " + anchor,
            )
            self.assertEqual(
                1,
                len([line for line in self.all_lines
                     if line.startswith("- [x] ") and anchor in line]),
                "deep-read debt record is missing or duplicated among closed rows: " + anchor,
            )

    def test_ruling_is_confined_to_the_decision_bucket(self):
        everywhere = sum(1 for line in self.all_lines if line.startswith(STANDING_RULING_PREFIX))
        self.assertEqual(len(ruling_of(self.bucket)), everywhere)


if __name__ == "__main__":
    unittest.main()