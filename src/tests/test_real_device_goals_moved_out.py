"""Guard the 2026-09-22 standing ruling that hardware work leaves the per-round goal.

The owner gave two instructions that change what "the goal" means:

* from now on every open decision is taken by Codex on its own best judgement;
* anything that can only be verified on real hardware, or that needs material this
  checkout does not hold, is listed separately as a *future* goal and no longer
  belongs to the goal being executed round by round.

Round R157 implements the second instruction for the 「长期观察」 bucket: 11 of its
13 register-only items name WebView, 真实设备, 真实网络, 设备侧, 外部验收 or the fnOS
宿主, and no offline test can advance any of them.  They moved byte for byte into
``docs/REAL_DEVICE_GOALS.md`` under the fixed ids G01-G11, and ``TODO.md`` keeps
exactly one pointer line per moved item.  Two items -- offline first-screen
performance regression and server resource ceilings -- are verifiably offline and
stayed where they were.

This file is what keeps the move honest, because ``docs/`` deliberately sits
outside ``SOURCE_MANIFEST.sha256`` (that manifest walks ``src/`` and
``android-client/`` only).  It pins, using the same unflexed-digest convention the
device ledger uses, where the only byte the hash refuses to pin is the ``- [ ]`` /
``- [x]`` state character:

* the verbatim text of all 11 moved items, so nobody can rewrite, trim or
  "complete" a hardware item while claiming it was only moved;
* that no open item below the bucket declaration needs hardware any more;
* that the two items which stayed are exactly the two pinned offline ones;
* one non-checklist pointer per moved item inside ``TODO.md``;
* the declaration line still deferring hardware work to the future list;
* the future doc being reachable from ``docs/INDEX.md``, carrying its own
  preconditions, and leaking neither credentials nor ``TODO.md`` line numbers from
  the region that renumbers with every recorded round.

Deliberately *not* pinned: the global open/closed counts of ``TODO.md``.  Those
move every round by design; hardcoding them would manufacture a red gate for the
next round rather than guard this one.
"""

from pathlib import Path
import re
import unittest

# The unflexed-digest convention is shared with the device-ledger guard on purpose:
# one round must not be able to widen "frozen" into "ignored" in only one of the two
# docs.  The import goes flat under ``unittest discover -s tests`` and dotted when a
# single file is run as ``tests.test_...``, so both spellings are tried.
try:
    from test_device_todos_migrated import (
        CHECKLIST,
        CREDENTIAL_SHAPE,
        DEVICE_SEGMENT_START,
        TODO_LINE_REF,
        digest,
    )
except ImportError:  # pragma: no cover - depends on how the suite was started
    from tests.test_device_todos_migrated import (
        CHECKLIST,
        CREDENTIAL_SHAPE,
        DEVICE_SEGMENT_START,
        TODO_LINE_REF,
        digest,
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
TODO = REPO_ROOT / "TODO.md"
GOALS = REPO_ROOT / "docs" / "REAL_DEVICE_GOALS.md"
LEDGER = REPO_ROOT / "docs" / "external-acceptance.md"
DOCS_INDEX = REPO_ROOT / "docs" / "INDEX.md"

# Content anchor of the bucket-declaration line inside TODO.md, looked up by text
# and never by a line number: every recorded round prepends entries above it.
OBSERVATION_DECLARATION = "R138 X2=B 桶归属"
BUCKET_NAMES = ("代码", "设备·外部", "需决策", "长期观察")
GOALS_LINK = "docs/REAL_DEVICE_GOALS.md"
# The index entry is a bullet that opens with the file name in backticks; a mention
# inside another row's prose does not make the doc findable, so the guard pins the
# entry line itself rather than the substring.
INDEX_ENTRY = re.compile(r"^-\s+`" + re.escape("REAL_DEVICE_GOALS.md") + r"`")
FUTURE_GOAL_WORDING = "以后的目标"

# Every moved item leaves one line behind in TODO.md.  The prefix is what the
# guard counts, so a second round cannot paste a twelfth pointer by accident.
POINTER_PREFIX = "2026-09-22（R157 真机段迁出）"
GOAL_ID_IN_POINTER = re.compile(r"\bG\d{2}\b")

# An open item under the declaration that still contains one of these cannot be
# advanced offline, which is exactly what the standing ruling moved out.
DEVICE_REQUIREMENT = re.compile(
    "真机|真实设备|真实网络|WebView|设备侧|外部验收|不能用离线|不能以离线|不替代|不可替代|宿主"
)

GOAL_BLOCK_START = re.compile(r"^<!-- BEGIN (G\d{2}) -->$")
GOAL_BLOCK_END = re.compile(r"^<!-- END (G\d{2}) -->$")
GOAL_ID_HEADING = re.compile(r"^### 固定编号 (G\d{2})$")
EVIDENCE_NOTE = "> 真机口径："

MOVED_GOAL_IDS = ("G01", "G02", "G03", "G04", "G05", "G06", "G07", "G08", "G09", "G10", "G11")

# Frozen digests of the 11 moved items as they read on disk immediately before the
# move (TODO.md L2036/L2063/L2071/L2072/L2077/L2091/L2092/L2104/L2109/L2110/L2118;
# G01 carries one indented continuation line, so its block is two lines).  The key
# is the fixed id, because TODO.md renumbers while the id does not.
FROZEN_GOAL_DIGESTS = {
    "G01": "3fa75489188355bb6cb616ece9f8e6e5c6c0bbd94b73284be6a2727d237bc3c9",
    "G02": "64756777c64f61ca4c2ff95a1b7ee3bb413b2f46b87604cdf010bf1b81e7103f",
    "G03": "1a65f50634804ce5049cae2d16fa7a704ddc7e57d21359859e6bb01117184d23",
    "G04": "ebd3a903b13bd3d2f55990ef5781a23dba4df6284c2cc50faa180910d52b1e9d",
    "G05": "5ec22eeb5c67191591dd3a8720e25b7cda397b2470caf106e85407a7077d9da7",
    "G06": "22604c39158ab24d56f63125ec66c74dfde054ea12fb098c200b591ae4f0b072",
    "G07": "c1c9f7caf0bf51475bee0ccadf63fe0afffaced58df7a93deebdd98e0cf67f48",
    "G08": "08c280ffd35a73e7d1a16ef64d041661886b8580ca7cca5cce2c1ce48da9f6d7",
    "G09": "aa7c2dfae713c224c5d9b26081a1352de58276a787df0b6e3444d6c27cadb9c7",
    "G10": "563dafefdaef43ca17f4e021533a7dda79a2c6d000f12be8f4f3db0ad39af8a4",
    "G11": "28c9b9c4b615b54394b3db2f81e8a108f2fd783867ecb2ef62335a5a9ddb47ff",
}

# The register-only items that survived the split were the offline performance-
# regression entry and the server resource-ceiling entry. Both are now closed in
# TODO.md, so the live bucket is intentionally empty; keeping the expected set
# explicit prevents a future round from quietly reintroducing or changing one.
PINNED_KEPT_DIGESTS = {
}


def goal_blocks(text):
    """Map fixed id -> original-text lines, for every BEGIN/END pair in the doc."""
    blocks = {}
    current = None
    for line in text.split("\n"):
        head = GOAL_BLOCK_START.match(line)
        if head:
            goal_id = head.group(1)
            if goal_id in blocks:
                raise AssertionError("the future-goal doc repeats the fixed id %s" % goal_id)
            current = goal_id
            blocks[goal_id] = []
            continue
        tail = GOAL_BLOCK_END.match(line)
        if tail:
            goal_id = tail.group(1)
            assert current is not None, "the doc closes %s without opening it" % goal_id
            assert goal_id == current, "block nesting broke at %s (open %s)" % (goal_id, current)
            current = None
            continue
        if current is not None:
            blocks[current].append(line)
    return blocks


class RealDeviceGoalsMovedOutTests(unittest.TestCase):
    def setUp(self):
        self.todo_lines = TODO.read_text(encoding="utf-8").split("\n")

    def _declaration_line(self):
        hits = [
            number for number, line in enumerate(self.todo_lines, start=1)
            if OBSERVATION_DECLARATION in line
        ]
        self.assertEqual(
            len(hits), 1,
            "TODO.md must carry exactly one 「%s」 bucket declaration, found %d"
            % (OBSERVATION_DECLARATION, len(hits)),
        )
        return hits[0]

    def _open_items_below_declaration(self):
        declaration_at = self._declaration_line()
        blocks = []
        index = declaration_at
        while index < len(self.todo_lines):
            line = self.todo_lines[index]
            if CHECKLIST.match(line) and line.startswith("- [ ] "):
                block = [line]
                index += 1
                while index < len(self.todo_lines) and self.todo_lines[index].startswith("  "):
                    block.append(self.todo_lines[index])
                    index += 1
                blocks.append((index - len(block) + 1, block))
                continue
            index += 1
        return blocks

    def test_the_future_goal_doc_exists_is_indexed_and_holds_its_own_rules(self):
        self.assertTrue(
            GOALS.is_file(),
            "%s is missing: the standing ruling moved the hardware backlog out of TODO.md and it "
            "has to live somewhere that a takeover can find" % GOALS,
        )
        index_text = DOCS_INDEX.read_text(encoding="utf-8") if DOCS_INDEX.is_file() else ""
        listed = [line for line in index_text.split("\n") if INDEX_ENTRY.match(line)]
        self.assertEqual(
            len(listed), 1,
            "docs/INDEX.md must carry exactly one entry line opening with 「`%s`」, found %d; a prose "
            "mention in another row does not make the future goal findable" % (GOALS.name, len(listed)),
        )
        text = GOALS.read_text(encoding="utf-8")
        self.assertIn(
            LEDGER.name, text,
            "the doc must state how it divides work with %s: that ledger holds device *tasks*, this "
            "one holds the register-only observations" % LEDGER.name,
        )
        for wording in ("固定编号", "终止条件 (2)", FUTURE_GOAL_WORDING):
            self.assertIn(wording, text, "the future-goal doc lost the wording 「%s」" % wording)

    def test_every_moved_goal_survives_verbatim(self):
        text = GOALS.read_text(encoding="utf-8")
        blocks = goal_blocks(text)
        self.assertEqual(
            sorted(blocks), sorted(FROZEN_GOAL_DIGESTS),
            "the doc must carry exactly the %d moved items, no more and none dropped"
            % len(FROZEN_GOAL_DIGESTS),
        )
        altered = [goal_id for goal_id in MOVED_GOAL_IDS if digest(blocks[goal_id]) != FROZEN_GOAL_DIGESTS[goal_id]]
        self.assertEqual(
            altered, [],
            "item text was rewritten after the move; notes may be added outside the markers but "
            "what is between them is frozen (fixed ids: %s)" % altered,
        )

    def test_the_moved_goals_are_addressed_by_fixed_ids_in_order(self):
        text = GOALS.read_text(encoding="utf-8")
        ids = [match.group(1) for match in (GOAL_ID_HEADING.match(line) for line in text.split("\n")) if match]
        self.assertEqual(
            ids, list(MOVED_GOAL_IDS),
            "each frozen block needs exactly one 「### 固定编号 G<nn>」 heading, in G01..G11 order"
        )

    def test_the_round_goal_holds_no_open_item_that_needs_hardware(self):
        """Discriminating case for 「凡是需要真机验证的全部单独列出来」.

        Nothing under the bucket declaration may name hardware any more, so a
        future round that registers a WebView or real-network observation here has
        to file it in the future-goal doc instead.
        """
        offenders = [
            (number, sorted(set(DEVICE_REQUIREMENT.findall(block[0]))))
            for number, block in self._open_items_below_declaration()
            if DEVICE_REQUIREMENT.search(block[0])
        ]
        self.assertEqual(
            offenders, [],
            "TODO.md lines %s are open observations that cannot be advanced offline; they belong to %s"
            % (offenders, GOALS_LINK)
        )

    def test_every_moved_goal_keeps_one_pointer_in_the_todo(self):
        pointers = [line for line in self.todo_lines if line.startswith(POINTER_PREFIX)]
        self.assertEqual(
            len(pointers), len(MOVED_GOAL_IDS),
            "TODO.md must keep exactly one pointer per moved item, found %d" % len(pointers)
        )
        seen = []
        for line in pointers:
            self.assertIn(GOALS_LINK, line, "a pointer stopped naming the future-goal doc: %s" % line[:60])
            found = GOAL_ID_IN_POINTER.findall(line)
            self.assertEqual(
                len(found), 1,
                "a pointer must cite exactly one fixed id, found %s in: %s" % (found, line[:60])
            )
            self.assertFalse(CHECKLIST.match(line), "a pointer must not be a checklist entry: %s" % line[:60])
            seen.append(found[0])
        self.assertEqual(
            sorted(seen), sorted(MOVED_GOAL_IDS),
            "the pointers must cover every moved id once: %s" % sorted(seen)
        )

    def test_the_observation_bucket_matches_the_current_pinned_offline_set(self):
        blocks = self._open_items_below_declaration()
        measured = sorted(digest(block) for _number, block in blocks)
        self.assertEqual(
            measured, sorted(PINNED_KEPT_DIGESTS),
            "the offline observation bucket now holds %d items outside the explicitly pinned "
            "current set; retune this table only together with a stated reason" % len(blocks)
        )

    def test_the_declaration_defers_hardware_work_to_the_future_list(self):
        declaration_at = self._declaration_line()
        declaration = self.todo_lines[declaration_at - 1]
        for bucket in BUCKET_NAMES:
            self.assertIn(bucket, declaration, "the declaration stopped naming one of the four buckets: %s" % bucket)
        self.assertIn("不计入终止分母", declaration, "the declaration stopped exempting the bucket from the termination denominator")
        self.assertIn(
            GOALS.name, declaration,
            "the declaration must say where hardware-dependent observations go now that the standing "
            "ruling took them out of the per-round goal"
        )
        self.assertIn(
            FUTURE_GOAL_WORDING, declaration,
            "the declaration must call the moved list what the owner called it: %s" % FUTURE_GOAL_WORDING
        )
        self.assertNotIn(
            "盘上 L", declaration,
            "TODO.md renumbers with every recorded round, so a written line number inside the "
            "declaration is already stale the moment it is used"
        )

    def test_the_future_doc_carries_preconditions_without_credentials_or_line_numbers(self):
        text = GOALS.read_text(encoding="utf-8")
        leaked = [line.strip() for line in text.split("\n") if CREDENTIAL_SHAPE.search(line)]
        self.assertEqual(
            leaked, [],
            "the future-goal doc carries something shaped like a device credential; the standing rule "
            "is that the operator keeps those outside the repository entirely"
        )
        start = next(
            (number for number, line in enumerate(self.todo_lines, start=1)
             if line.startswith(DEVICE_SEGMENT_START)),
            None,
        )
        self.assertIsNotNone(start, "TODO.md lost the device segment heading")
        offenders = [match.group(0) for match in TODO_LINE_REF.finditer(text) if int(match.group(1)) > start]
        self.assertEqual(
            offenders, [],
            "citations into the renumbering region of TODO.md expire the first round they are used; "
            "name moved items by their fixed id instead: %s" % offenders
        )
        lines = text.split("\n")
        missing = []
        for number, line in enumerate(lines):
            tail = GOAL_BLOCK_END.match(line)
            if not tail:
                continue
            following = next((candidate for candidate in lines[number + 1:] if candidate.strip()), "")
            if not following.startswith(EVIDENCE_NOTE):
                missing.append(tail.group(1))
        self.assertEqual(
            missing, [],
            "every frozen block has to be followed by one 「%s」 line, because a hardware item without "
            "a stated evidence rule can never be closed on evidence" % EVIDENCE_NOTE
        )
        for precondition in ("SSH 端口 22", "198.51.100.24", "198.51.100.24", "样本"):
            self.assertIn(precondition, text, "the preconditions section lost 「%s」" % precondition)


if __name__ == "__main__":
    unittest.main()
