"""Guard the evidence cards added to the external-acceptance ledger by R2.

``docs/external-acceptance.md`` holds the 45 device and externally-blocked items
that were moved out of ``TODO.md``.  Before this round every one of them was
written as a wish: it named no device, no material, no observable result, so no
round could ever tell "not yet verifiable" apart from "verifiable and failing".
Each entry now carries one fixed-format evidence card immediately after its
``<!-- END Lnnn -->`` marker, stating the device or material the check needs,
what has to be captured, the line that decides pass or fail, and what to record
when the material can never be produced.

These tests keep that contract.  They stay shape-only: nothing in this file
decides an item, a card only states how to decide it.  R4 closed nine entries,
R5 closed one more whose material can never be produced on this host, R6 closed
the one whose material is a build-time file nobody kept, and every one of those
ticks is bound to a four-line note repeating the cannot-be-evidenced verdict
written on its own card, so a tick here can never be read as "the judgement
line passed".

R7 added a second closure shape.  L1866 asked for a measurement instead of a
device, the measurement arrived, and it disproved the verdict the card had
prescribed for the no-evidence case -- so that tick may not quote its own card
phrase, and must instead cite the counters it read.  The same round measured
L1860 and L1867 and both failed their judgement line, so their boxes stayed
unticked and carry a 「取证记录」 in exactly the slot a closure note would use:
the guard is what keeps those two readings apart.
"""

from pathlib import Path
import re
import unittest

from test_device_todos_migrated import FROZEN_ENTRY_DIGESTS


REPO_ROOT = Path(__file__).resolve().parents[2]
TODO = REPO_ROOT / "TODO.md"
LEDGER = REPO_ROOT / "docs" / "external-acceptance.md"

BLOCK_START = re.compile(r"^<!-- BEGIN L(\d+) -->$")
BLOCK_END = re.compile(r"^<!-- END L(\d+) -->$")
CARD_HEAD = re.compile(r"^> \*\*取证单 L(\d+)\*\*$")
CHECKLIST = re.compile(r"^- \[[ xX]\] ")

FIELD_LABELS = (
    "设备／材料：",
    "抓取：",
    "判定线：",
    "不可取证时结案口径：",
)

# Wording that would let a card quietly declare its own item finished.
CLOSING_WORDS = ("已结案", "视为完成", "视同完成", "不必验证", "无需验证", "已闭环")

# ---- closure bookkeeping: entries whose material can never be produced ----
# R4 closes nine ledger entries, and R5 and R6 close one more each as "not
# evidenceable on this host".  A bare tick would read as "someone verified this", so every tick
# is bound to a four-line note placed directly under its own card: the note must
# quote the verdict phrase that very card prescribes, must carry a real
# measurement, the missing material and a reopening condition, must be labelled
# with the round that made the decision, and must never claim the judgement line
# passed.  The record section at the foot of the file states the same set once
# more per round; any disagreement between the three readings -- ticks, notes,
# record -- is red.
R4_CLOSED_IDS = frozenset({1838, 1852, 1853, 1854, 1855, 1856, 1857, 1872, 1873})
R5_CLOSED_IDS = frozenset({1836})
# R7 splits the eight remaining 「观感/外部性」 items into three outcomes.  Five ask
# for a carrier this host can never hold -- there is no Android or WebView device
# at all (``adb devices -l`` returns an empty table) and the NAS is a VMware guest
# with no rotational disk and no network share -- so they close on the verdict
# written on their own card.  One, L1866, asks for a measurement rather than a
# device, and that measurement has now been taken: its card verdict is therefore
# disproved, and a note repeating it would record the opposite of what was seen,
# so it closes under a different rule.  Two, L1860 and L1867, were measured too and
# failed their judgement line, so they stay open and carry an evidence record in
# place of a closure note.
R6_CLOSED_IDS = frozenset({1184})
R7_UNEVIDENCED_CLOSED_IDS = frozenset({1868, 1869, 1870, 1871, 1874})
R7_EVIDENCED_CLOSED_IDS = frozenset({1866})
R7_CLOSED_IDS = R7_UNEVIDENCED_CLOSED_IDS | R7_EVIDENCED_CLOSED_IDS
R7_OPEN_WITH_EVIDENCE_IDS = frozenset({1860, 1867})
CLOSURES_BY_ROUND = {
    "R4": R4_CLOSED_IDS,
    "R5": R5_CLOSED_IDS,
    "R6": R6_CLOSED_IDS,
    "R7": R7_CLOSED_IDS,
}
CLOSED_IDS = (
    R4_CLOSED_IDS | R5_CLOSED_IDS | R6_CLOSED_IDS | R7_CLOSED_IDS
)
CLOSURE_ROUND_OF = {nid: label for label, ids in CLOSURES_BY_ROUND.items() for nid in ids}
CLOSURE_DATE = "2026-09-21"
CLOSURE_HEAD = re.compile(
    r"^> \*\*结案（(?P<round>R\d+)·(?P<date>\d{4}-\d{2}-\d{2})）\*\*：(?P<body>.*)$"
)
CLOSURE_FIELDS = ("实测：", "缺料：", "重开条件：")
# An entry that was measured but failed its judgement line keeps its box open and
# gets this shape instead: same slot, same three sub-fields, different head word,
# so no reader can mistake it for a closure.
EVIDENCE_HEAD = re.compile(
    r"^> \*\*取证记录（(?P<round>R\d+)·(?P<date>\d{4}-\d{2}-\d{2})）\*\*：(?P<body>.*)$"
)
EVIDENCE_FIELDS = ("实测：", "缺口：", "后续动作：")
DURATION = re.compile(r"\d[\d,]* (?:ms|秒)")
CLOSURE_SUB = "> - "
RECORD_HEAD = re.compile(r"^## (R\d+) 结案记录")
RECORD_SECTION_STOP = "## "
RECORD_ID = re.compile(r"^- L(\d+)$")
TICKED_STATE = re.compile(r"^- \[[xX]\] ")
VERDICT_PHRASE = re.compile(r"「([^」]+)」")
VERDICT_FIELD = "不可取证时结案口径"
# Wording that leaves a verdict undecided and hands it to some later round.
DEFERRAL = re.compile(r"待 R\d+|待定|重新给方向")
ENTRY_TOTAL = 45
# The section note that hands L1836 to a round is found by the entry id it
# covers: naming the TODO.md line it migrates from would put a citation into
# the moved-out device segment, which test_device_todos_migrated forbids.
SECTION_NOTE = "> 源节："
R5_SECTION_ENTRY = "L1836"
R6_SECTION_ENTRY = "L1184"
R7_SECTION_ENTRY = "L1866"
# Every closed or measured entry has to cite the concrete thing its own card asked
# for; a generic probe would let one note stand in for another.
R7_MEASUREMENT_TOKENS = {
    1860: ("15014 ms", "15013 ms", "5129 ms", "timeout=3"),
    1866: ("SigCgt", "KillMode", "1min 30s", "shutdown_runtime", "10 秒"),
    1867: ("SIGTERM", "31 秒", "10 秒", "90 秒"),
    1868: ("adb devices", "500 ms"),
    1869: ("adb devices", "--seek-fill"),
    1870: ("adb devices", "#nowCover"),
    1871: ("adb devices", "metadata/artwork"),
    1874: ("ROTA=0", "findmnt"),
}
R7_VERDICT_FALSIFIED = {1866: "设备停止路径未知"}
# R7 took its readings over ssh without writing anything to the device but four
# throwaway probes under `/tmp`.  A record that says "read-only" while listing
# deployed, restarted or upgraded software is self-contradictory, so the promise
# is anchored on two literals and policed on every device-side change verb.
READ_ONLY_PROMISE = "全程只读取证"
READ_ONLY_HOSTKEY = "SHA256:7PMkKVzFzH7a8"
WRITE_PATTERNS = (
    "已部署", "已重启", "已替换", "已改配置", "已升级", "已安装", "已写入配置",
)
# Words that would turn a 「后续动作」 -- a question put to the user -- into a
# claim that the code has already been changed.
CODE_ACTION_WORDS = (
    "已补", "已安装信号", "已实现", "已修复", "已改写", "已改投送", "已压缩上限",
)
NOT_CODE_ACTION = "不改"
GRACE_CLOSURE_WORDS = ("宽限", "对齐")
R7_SECTION_LABEL = "R7"
# A closure note has to cite something an actual run could have printed.
EVIDENCE_ANCHOR = re.compile(
    r"\d{4}-\d{2}-\d{2}|192\.168\.100\.24|/proc/|/sys/|/vol1/|/var/log/|uname|lsusb"
    r"|adb|command -v|`[^`]+`"
)
NOT_PASSED_PROMISE = "不表示判据已通过"
# A card may only ask for something a real check could actually hold.
DEVICE_TOKENS = (
    "真机", "三星 S9+", "小米 15 Pro", "WebView", "飞牛", "fnOS", "198.51.100.24",
    "DAC", "DoP", "DSD", "Renderer", "shairport-sync", "nqptp", "AirPlay",
    "UAPP", "中子", "BubbleUPnP", "DLNA", "MPD", "Gradle", "JDK", "ARM64",
    "macOS", "Xcode", "HarmonyOS", "DevEco", "NAS", "SMB", "NFS", "App Center",
    "SOURCE_PROVENANCE", "远程仓库", "CI", "构建号", "快照",
)

NOT_APPLICABLE_ID = 1847  # the standing-maintenance entry: no device involved


class LedgerEvidenceCardTests(unittest.TestCase):
    def setUp(self):
        self.text = LEDGER.read_text(encoding="utf-8")
        self.lines = self.text.split("\n")

    def _cards(self):
        """Yield (entry_id, four field values) for every card in file order."""
        found = []
        for index, line in enumerate(self.lines):
            head = CARD_HEAD.match(line)
            if not head:
                continue
            fields = {}
            for offset in range(1, len(FIELD_LABELS) + 1):
                row = self.lines[index + offset]
                match = re.match(r"^> - ([^：]+)：(.+)$", row)
                if match:
                    fields[match.group(1)] = match.group(2)
            found.append((int(head.group(1)), fields))
        return found

    def test_every_entry_end_marker_is_followed_by_exactly_one_card(self):
        ends = [i for i, l in enumerate(self.lines) if BLOCK_END.match(l)]
        self.assertEqual(len(ends), 45, "the ledger must still hold 45 entries")
        for i in ends:
            block = self.lines[i + 1:i + 8]
            heads = [b for b in block if CARD_HEAD.match(b)]
            self.assertEqual(len(heads), 1, "expected one card after " + self.lines[i])
        self.assertEqual(len(self._cards()), 45)

    def test_card_ids_match_the_markers_and_the_frozen_digests(self):
        marker_ids = {int(BLOCK_END.match(l).group(1)) for l in self.lines if BLOCK_END.match(l)}
        cards = self._cards()
        card_ids = [cid for cid, _ in cards]
        self.assertEqual(len(card_ids), len(set(card_ids)), "duplicate card id")
        self.assertEqual(set(card_ids), marker_ids)
        self.assertEqual(set(card_ids), set(FROZEN_ENTRY_DIGESTS))

    def test_every_card_carries_four_non_empty_fields(self):
        for cid, fields in self._cards():
            self.assertEqual(len(fields), 4, "card L%d must hold 4 fields, got %s" % (cid, fields))
            for label in FIELD_LABELS:
                key = label.rstrip("：")
                self.assertIn(key, fields, "card L%d lacks %s" % (cid, label))
                self.assertTrue(fields[key].strip(), "card L%d has an empty %s" % (cid, label))

    def test_no_card_leaks_inside_a_frozen_block(self):
        for match in re.finditer(
            r"^<!-- BEGIN L(\d+) -->$(.*?)^<!-- END L\1 -->$", self.text, re.M | re.S
        ):
            self.assertNotIn(
                "> **取证单",
                match.group(2),
                "card written inside the frozen block of L" + match.group(1),
            )

    def test_judgement_lines_never_declare_the_item_closed(self):
        for cid, fields in self._cards():
            line = fields.get("判定线", "")
            for word in CLOSING_WORDS:
                self.assertNotIn(word, line, "card L%d closes its own item via %r" % (cid, word))

    def test_device_field_names_real_material_or_declares_it_inapplicable(self):
        cards = dict(self._cards())
        for cid, fields in cards.items():
            device = fields.get("设备／材料", "")
            if cid == NOT_APPLICABLE_ID:
                self.assertIn("不适用", device, "L1847 is the one entry with no device")
                continue
            self.assertNotIn("不适用", device, "only L1847 may waive the device")
            self.assertTrue(
                self._names_material(device, cards, (cid,)),
                "card L%d names no identifiable material: %r" % (cid, device),
            )
        applicable = [cid for cid, f in cards.items() if "不适用" in f.get("设备／材料", "")]
        self.assertEqual(applicable, [NOT_APPLICABLE_ID])

    def _names_material(self, device, cards, trail):
        """True if the field names real material, directly or via one ``同 Lnnn`` hop.

        A card may point at a sibling entry instead of repeating its device list,
        but the pointer must land on a card that itself names something concrete,
        must not skip L1847 (which has no device at all), and must not cycle.
        """
        if any(token in device for token in DEVICE_TOKENS):
            return True
        for target in (int(x) for x in re.findall(r"\bL(\d+)\b", device)):
            if target in trail:
                continue
            if target not in cards or target == NOT_APPLICABLE_ID:
                continue
            if self._names_material(cards[target].get("设备／材料", ""), cards, trail + (target,)):
                return True
        return False

    def test_todo_device_segment_holds_no_open_item_still(self):
        lines = [l.rstrip("\r") for l in TODO.read_text(encoding="utf-8").split("\n")]
        starts = [i for i, l in enumerate(lines) if l.startswith("## 宿主 MediaSession")]
        stops = [i for i, l in enumerate(lines) if l.startswith("# 当前持续优化目标")]
        self.assertEqual(len(starts), 1, "the device segment heading must stay unique")
        self.assertEqual(len(stops), 1, "the device segment end heading must stay unique")
        start, stop = starts[0], stops[0]
        self.assertGreater(stop - start, 1, "the device segment collapsed to nothing")
        open_rows = [
            start + 1 + offset
            for offset, line in enumerate(lines[start:stop])
            if CHECKLIST.match(line) and line.startswith("- [ ] ")
        ]
        self.assertEqual(
            open_rows, [],
            "TODO.md lines %s grew a device item back; it belongs to the ledger" % open_rows,
        )

    # ---- R3 merge bookkeeping: device items that share one evidence run ----
    # Same-cause entries are audited together, but each keeps its own checkbox.
    # The ledger states the grouping twice: once as a family declaration at the
    # foot of the file, once as a merge note inside every involved evidence card.
    # If those two readings ever disagree, the grouping is fiction, so it is red.
    FAMILY_DECL = re.compile(r"^> 族 (\S+) · (.+?)：主条 L(\d+)；并条 ([^。]+)。$")
    NOT_MERGED_DECL = re.compile(r"^> 不并入：(.+)$")
    MERGE_HEAD = re.compile(r"^> 并案：")
    MASTER_LINE = re.compile(r"^> 并案：本条为「(.+?)」族的主条，.*?覆盖 ((?:L\d+、?)+)；")
    MEMBER_LINE = re.compile(r"^> 并案：并入主条 L(\d+)")
    ANY_ID = re.compile(r"L(\d+)")

    def _card_index(self, nid):
        want = "> **取证单 L%d**" % nid
        hits = [i for i, line in enumerate(self.lines) if line == want]
        self.assertEqual(len(hits), 1, "ledger must hold exactly one card for L%d" % nid)
        return hits[0]

    def _families(self):
        out = []
        for line in self.lines:
            match = self.FAMILY_DECL.match(line)
            if match:
                out.append((match.group(2), int(match.group(3)),
                            [int(x) for x in self.ANY_ID.findall(match.group(4))]))
        return out

    def _not_merged(self):
        ids = []
        for line in self.lines:
            match = self.NOT_MERGED_DECL.match(line)
            if match:
                ids += [int(x) for x in re.findall(r"L(\d+)（", match.group(1))]
        return ids

    def _merge_notes(self):
        """Map every entry id to the merge notes written under its card."""
        notes = {}
        for index, line in enumerate(self.lines):
            head = CARD_HEAD.match(line)
            if not head:
                continue
            tail = []
            for row in self.lines[index + 1 + len(FIELD_LABELS):]:
                if row.strip() == "":
                    break
                if self.MERGE_HEAD.match(row):
                    tail.append(row)
            notes[int(head.group(1))] = tail
        return notes

    def test_r3_declares_exactly_two_merge_families(self):
        families = self._families()
        self.assertEqual(len(families), 2, "R3 registers exactly two same-cause families")
        masters = [master for _, master, _ in families]
        members = [mid for _, _, merged in families for mid in merged]
        self.assertEqual(len(members), 7, "R3 merges seven entries behind two masters")
        self.assertEqual(sorted(masters + members), sorted(set(masters + members)),
                         "an entry is declared in more than one family")
        self.assertFalse(set(masters) & set(members), "a master may not also be a member")
        for entry in masters + members:
            self.assertIn(entry, FROZEN_ENTRY_DIGESTS,
                          "the merge bookkeeping names an unknown entry L%d" % entry)

    def test_family_declaration_and_card_merge_notes_agree_both_ways(self):
        families = self._families()
        self.assertEqual(len(families), 2, "R3 registers exactly two same-cause families")
        notes = self._merge_notes()
        self.assertEqual(len(notes), 45, "the ledger must still hold 45 cards")
        declared = {}
        for _name, master, merged in families:
            for member in merged:
                declared[member] = master
        from_cards = {}
        for nid, rows in notes.items():
            targets = [self.MEMBER_LINE.match(row) for row in rows]
            targets = [t for t in targets if t]
            self.assertLessEqual(len(targets), 1,
                                 "card L%d points at more than one master" % nid)
            if targets:
                from_cards[nid] = int(targets[0].group(1))
                self.assertEqual(self.lines[self._card_index(nid) + 1 + len(FIELD_LABELS)], rows[0],
                                 "merge note in card L%d is not placed after the four fields" % nid)
        self.assertEqual(declared, from_cards,
                         "family declaration and per-card merge notes disagree")
        covered = set(declared) | set(declared.values())
        for nid, rows in notes.items():
            if rows:
                self.assertIn(nid, covered | set(self._not_merged()),
                              "card L%d carries a merge note that no family declares" % nid)
        for member, master in declared.items():
            self.assertNotEqual(master, member, "entry L%d merges into itself" % member)

    def test_master_cards_name_their_family_and_coverage_list(self):
        families = self._families()
        self.assertEqual(len(families), 2, "R3 registers exactly two same-cause families")
        notes = self._merge_notes()
        for name, master, merged in families:
            rows = [self.MASTER_LINE.match(row) for row in notes[master]]
            rows = [r for r in rows if r]
            self.assertEqual(len(rows), 1,
                             "master card L%d must carry exactly one family line" % master)
            self.assertEqual(rows[0].group(1), name,
                             "master card L%d names another family" % master)
            self.assertEqual([int(x) for x in self.ANY_ID.findall(rows[0].group(2))], merged,
                             "master card L%d lists another coverage set" % master)

    def test_merge_notes_never_close_or_tick_an_item(self):
        notes = self._merge_notes()
        rows = [(nid, line) for nid, card_rows in notes.items() for line in card_rows]
        self.assertEqual(len(rows), 10,
                         "R3 writes ten merge notes: two masters, seven members, one refusal")
        for nid, row in rows:
            for word in CLOSING_WORDS:
                self.assertNotIn(word, row,
                                 "merge note in card L%d closes its item via %r" % (nid, word))
            self.assertNotIn("- [", row,
                             "merge note in card L%d edits a checkbox" % nid)
            self.assertTrue(row.startswith("> 并案："),
                            "unexpected merge note shape in card L%d" % nid)
        for nid in self._not_merged():
            self.assertFalse([row for row in notes[nid] if self.MEMBER_LINE.match(row)],
                             "L%d is declared as not merged yet carries a merge note" % nid)

    # ---- R4 closures: ticks that carry their evidence gap with them ----

    def _ticked_ids(self):
        """Fixed ids whose own frozen block carries a checked box."""
        ids = []
        current = None
        for line in self.lines:
            head = BLOCK_START.match(line)
            if head:
                current = int(head.group(1))
                continue
            if BLOCK_END.match(line):
                current = None
                continue
            if current is not None and TICKED_STATE.match(line):
                ids.append(current)
        return ids

    def _closure_notes(self):
        """Map every card id to the closure note under it, empty when it has none."""
        notes = {}
        for index, line in enumerate(self.lines):
            head = CARD_HEAD.match(line)
            if not head:
                continue
            first = self.lines[index + 1 + len(FIELD_LABELS)]
            if not CLOSURE_HEAD.match(first):
                notes[int(head.group(1))] = []
                continue
            rows = [first]
            for row in self.lines[index + 2 + len(FIELD_LABELS):]:
                if not row.startswith(CLOSURE_SUB):
                    break
                rows.append(row)
            notes[int(head.group(1))] = rows
        return notes

    def _evidence_notes(self):
        """Map every card id to the 取证记录 under it, empty when it has none."""
        notes = {}
        for index, line in enumerate(self.lines):
            head = CARD_HEAD.match(line)
            if not head:
                continue
            first = self.lines[index + 1 + len(FIELD_LABELS)]
            if not EVIDENCE_HEAD.match(first):
                notes[int(head.group(1))] = []
                continue
            rows = [first]
            for row in self.lines[index + 2 + len(FIELD_LABELS):]:
                if not row.startswith(CLOSURE_SUB):
                    break
                rows.append(row)
            notes[int(head.group(1))] = rows
        return {nid: rows for nid, rows in notes.items() if rows}

    def _verdict_phrase(self, nid):
        """The single verdict phrase the card itself prescribes for this entry."""
        fields = dict(self._cards()).get(nid, {})
        phrases = VERDICT_PHRASE.findall(fields.get(VERDICT_FIELD, ""))
        self.assertEqual(
            len(phrases), 1,
            "card L%d must prescribe exactly one verdict phrase, got %s" % (nid, phrases),
        )
        return phrases[0]

    def test_ticks_and_their_notes_are_the_same_set(self):
        notes = self._closure_notes()
        ticked = self._ticked_ids()
        noted = [nid for nid, rows in notes.items() if rows]
        self.assertEqual(
            sorted(ticked), sorted(CLOSED_IDS),
            "the ledger must tick R4's nine entries, R5's and R6's one each and "
            "R7's six",
        )
        self.assertEqual(sorted(noted), sorted(CLOSED_IDS),
                         "a tick without its note, or a note without its tick")
        self.assertEqual(sorted(CLOSURE_ROUND_OF), sorted(CLOSED_IDS),
                         "a closed entry is not attributed to exactly one round")
        open_rows = [l for l in self.lines if l.startswith("- [ ] ")]
        done_rows = [l for l in self.lines if TICKED_STATE.match(l)]
        self.assertEqual(
            len(CLOSED_IDS), 17,
            "R4 closes nine device items, R5 and R6 one each, R7 six",
        )
        self.assertEqual(
            R7_CLOSED_IDS, R7_UNEVIDENCED_CLOSED_IDS | R7_EVIDENCED_CLOSED_IDS,
            "R7 closure sets must partition cleanly",
        )
        self.assertFalse(
            R7_OPEN_WITH_EVIDENCE_IDS & CLOSED_IDS,
            "an entry that failed its judgement line cannot also be closed",
        )
        self.assertEqual(len(done_rows), len(CLOSED_IDS), "a box outside the closure set was ticked")
        self.assertEqual(len(open_rows), ENTRY_TOTAL - len(CLOSED_IDS),
                         "the remaining device entries must stay open")

    def test_closure_note_quotes_the_verdict_of_its_own_card(self):
        notes = self._closure_notes()
        phrases = {}
        for nid in sorted(CLOSED_IDS - R7_EVIDENCED_CLOSED_IDS):
            self.assertTrue(notes.get(nid), "closed entry L%d carries no closure note" % nid)
            phrases[nid] = self._verdict_phrase(nid)
            self.assertIn("「%s」" % phrases[nid], notes[nid][0],
                          "the note for L%d does not repeat the verdict its own card prescribes" % nid)
        for nid in sorted(R7_EVIDENCED_CLOSED_IDS):
            # This entry closed because the measurement arrived, not because it could
            # not: quoting its own 「unknown」 verdict here would be a false record.
            self.assertTrue(notes.get(nid), "closed entry L%d carries no closure note" % nid)
            phrases[nid] = self._verdict_phrase(nid)
            self.assertEqual(
                phrases[nid], R7_VERDICT_FALSIFIED[nid],
                "L%d's card verdict changed wording, so the falsification record is stale" % nid,
            )
            self.assertNotIn(
                "「%s」" % phrases[nid], notes[nid][0],
                "L%d closed on evidence; its note must not repeat the verdict the evidence disproved" % nid,
            )
        self.assertEqual(sorted(set(phrases.values())), sorted(phrases.values()),
                         "two closed entries share one verdict phrase, so quoting is not discriminating")
        for nid, rows in notes.items():
            if not rows:
                continue
            for other, phrase in phrases.items():
                if other != nid:
                    self.assertNotIn("「%s」" % phrase, rows[0],
                                     "the note for L%d borrows the verdict of L%d" % (nid, other))

    def test_closure_notes_carry_measurement_gap_and_reopening(self):
        notes = self._closure_notes()
        for nid in sorted(CLOSED_IDS):
            rows = notes[nid]
            self.assertEqual(len(rows), 4,
                             "note for L%d must be one head plus three sub-fields: %s" % (nid, rows))
            head = CLOSURE_HEAD.match(rows[0])
            self.assertTrue(head, "note head for L%d does not match the closure shape" % nid)
            self.assertEqual(head.group("date"), CLOSURE_DATE,
                             "note for L%d carries a date other than the closing round" % nid)
            self.assertEqual(head.group("round"), CLOSURE_ROUND_OF[nid],
                             "note for L%d is signed by a round that never closed it" % nid)
            for label, row in zip(CLOSURE_FIELDS, rows[1:]):
                self.assertTrue(row.startswith(CLOSURE_SUB + label),
                                "note for L%d lacks or misplaces the field %s" % (nid, label))
                self.assertTrue(row[len(CLOSURE_SUB + label):].strip(),
                                "note for L%d leaves %s empty" % (nid, label))
            self.assertTrue(EVIDENCE_ANCHOR.search(rows[1]),
                            "the measurement line of L%d cites nothing a real run could print" % nid)
            index = self._card_index(nid)
            self.assertEqual(self.lines[index + 1 + len(FIELD_LABELS)], rows[0],
                             "note for L%d is not written after the four card fields" % nid)
        for nid, rows in notes.items():
            for row in rows:
                for word in CLOSING_WORDS:
                    self.assertNotIn(word, row,
                                     "the closure note of L%d declares the item settled via %r" % (nid, word))
                self.assertNotIn("- [", row, "the closure note of L%d edits a checkbox" % nid)

    def test_closure_record_sections_match_the_ticked_sets(self):
        heads = [(i, RECORD_HEAD.match(l).group(1))
                 for i, l in enumerate(self.lines) if RECORD_HEAD.match(l)]
        self.assertEqual(sorted(label for _, label in heads), sorted(CLOSURES_BY_ROUND),
                         "the ledger needs exactly one record section per closure round")
        ticked = self._ticked_ids()
        listed = []
        for index, label in heads:
            body, ids = [], []
            for row in self.lines[index + 1:]:
                if row.startswith(RECORD_SECTION_STOP):
                    break
                body.append(row)
                match = RECORD_ID.match(row)
                if match:
                    ids.append(int(match.group(1)))
            self.assertEqual(sorted(ids), sorted(CLOSURES_BY_ROUND[label]),
                             "the %s record lists another set than %s ticked" % (label, label))
            self.assertEqual(len(ids), len(set(ids)), "the %s record repeats an entry" % label)
            text = "\n".join(body)
            self.assertIn(
                NOT_PASSED_PROMISE, text,
                "the %s record must state that closing an entry is not passing its "
                "judgement line" % label,
            )
            for nid in ids:
                self.assertIn(nid, ticked,
                              "the %s record lists an entry that is not ticked" % label)
            listed += ids
        self.assertEqual(sorted(listed), sorted(CLOSED_IDS),
                         "a ticked entry appears in no record section")

    # ---- R5: the one entry whose blocker is a decision, not a device ----

    def _entry_block(self, nid):
        """Every ledger line from an entry heading up to the next one."""
        want = "### 固定编号 L%d" % nid
        hits = [i for i, line in enumerate(self.lines) if line == want]
        self.assertEqual(len(hits), 1, "the ledger must hold exactly one heading for L%d" % nid)
        stop = hits[0] + 1
        while stop < len(self.lines) and not re.match(r"^(?:### 固定编号|## )", self.lines[stop]):
            stop += 1
        return self.lines[hits[0]:stop]

    def test_r5_closes_L1836_on_the_no_hosting_ruling(self):
        fields = dict(self._cards())[1836]
        verdict = fields[VERDICT_FIELD]
        self.assertIn("远程仓库", verdict,
                      "the L1836 verdict must name what can never be produced")
        self.assertIn("不可取证", verdict,
                      "L1836 must close as not evidenceable, never as passing")
        phrase = self._verdict_phrase(1836)
        self.assertIn("「%s」" % phrase, self._closure_notes()[1836][0],
                      "the R5 note must repeat the verdict written on its own card")
        ruling = [l for l in self._entry_block(1836) if l.startswith("> 性质标注：")]
        self.assertEqual(len(ruling), 1, "L1836 must carry exactly one nature note")
        self.assertIn("R5", ruling[0], "the nature note must name the round that ruled")
        self.assertIn("暂不托管", ruling[0],
                      "the nature note must keep the ruling this entry rests on")
        self.assertIn("不表示", ruling[0],
                      "the nature note must say what the closure does not mean")
        section = [l for l in self.lines
                   if l.startswith(SECTION_NOTE) and R5_SECTION_ENTRY in l]
        self.assertEqual(len(section), 1, "the section note covering L1836 must stay findable")
        self.assertIn("R5 结案 L1836", section[0],
                      "the section note still forwards L1836 to a later round")

    def test_r6_closes_L1184_on_the_unrecoverable_provenance_ruling(self):
        fields = dict(self._cards())[1184]
        verdict = fields[VERDICT_FIELD]
        self.assertIn("不可恢复", verdict,
                      "the L1184 verdict must name the only way this entry can close")
        self.assertIn("不可伪造", verdict,
                      "L1184 must close as unrecoverable, never as reconstructed")
        phrase = self._verdict_phrase(1184)
        self.assertIn("「%s」" % phrase, self._closure_notes()[1184][0],
                      "the R6 note must repeat the verdict written on its own card")
        nature = [l for l in self._entry_block(1184) if l.startswith("> 性质标注：")]
        self.assertEqual(len(nature), 1, "L1184 must carry exactly one nature note")
        self.assertIn("R6", nature[0], "the nature note must name the round that ruled")
        self.assertIn("LEGACY_EVIDENCE", nature[0],
                      "the nature note must keep the on-disk self-statement it rests on")
        self.assertIn("不表示", nature[0],
                      "the nature note must say what the closure does not mean")
        section = [l for l in self.lines
                   if l.startswith(SECTION_NOTE) and R6_SECTION_ENTRY in l]
        self.assertEqual(len(section), 1, "the section note covering L1184 must stay findable")
        self.assertIn("R6 结案 L1184", section[0],
                      "the section note still forwards L1184 to a later round")

    # ---- R7: five carriers this host cannot hold, one measurement, two failures ----

    def _note_rows_at_card(self, nid, head_re, what):
        """Read the four note rows that sit directly under a card, whatever they are."""
        index = self._card_index(nid)
        first = self.lines[index + 1 + len(FIELD_LABELS)]
        self.assertTrue(head_re.match(first),
                        "card L%d has no %s in its note slot: %r" % (nid, what, first))
        rows = [first]
        for row in self.lines[index + 2 + len(FIELD_LABELS):]:
            if not row.startswith(CLOSURE_SUB):
                break
            rows.append(row)
        return rows

    def test_r7_closes_the_view_items_whose_carrier_this_host_cannot_hold(self):
        notes = self._closure_notes()
        for nid in sorted(R7_UNEVIDENCED_CLOSED_IDS):
            rows = notes[nid]
            self.assertEqual(len(rows), 4, "L%d needs one note head plus three fields" % nid)
            self.assertEqual(CLOSURE_HEAD.match(rows[0]).group("round"), "R7",
                             "L%d is signed by a round other than the one that closed it" % nid)
            self.assertIn("本机", rows[0],
                          "the note for L%d must state the gap is local to this host" % nid)
            for token in R7_MEASUREMENT_TOKENS[nid]:
                self.assertIn(token, rows[1],
                              "the measurement line of L%d does not cite %r" % (nid, token))
        for nid in sorted(R7_UNEVIDENCED_CLOSED_IDS - {1874}):
            self.assertIn("空表", notes[nid][1],
                          "L%d must record that the device census came back empty" % nid)
        self.assertIn("sr0", notes[1874][1],
                      "L1874 must record that the only removable media here is an optical drive")

    def test_r7_closes_L1866_on_the_measured_stop_path(self):
        rows = self._closure_notes()[1866]
        for token in R7_MEASUREMENT_TOKENS[1866]:
            self.assertIn(token, rows[1],
                          "the L1866 measurement must cite %r to answer its card" % token)
        self.assertIn("不表示", rows[0] + rows[2] + rows[3],
                      "the L1866 note must say what its tick does not mean")
        nature = [l for l in self._entry_block(1866) if l.startswith("> 性质标注：")]
        self.assertEqual(len(nature), 1, "L1866 must carry exactly one nature note")
        for want in ("R7", "L1867", "不表示"):
            self.assertIn(want, nature[0],
                          "the nature note of L1866 must keep %r" % want)

    def test_r7_measured_L1860_and_L1867_without_closing_them(self):
        ticked = self._ticked_ids()
        for nid in sorted(R7_OPEN_WITH_EVIDENCE_IDS):
            self.assertNotIn(nid, ticked,
                             "L%d failed its judgement line and must stay open" % nid)
            self.assertFalse(self._closure_notes()[nid],
                             "L%d carries a closure note it has not earned" % nid)
            rows = self._note_rows_at_card(nid, EVIDENCE_HEAD, "evidence record")
            self.assertEqual(len(rows), 4, "the record under L%d must be a head plus three fields" % nid)
            head = EVIDENCE_HEAD.match(rows[0])
            self.assertEqual(head.group("round"), "R7", "the record under L%d is signed by another round" % nid)
            self.assertEqual(head.group("date"), CLOSURE_DATE, "the record under L%d carries another date" % nid)
            self.assertIn("保持开放", rows[0], "the record head of L%d must state the entry stays open" % nid)
            for label, row in zip(EVIDENCE_FIELDS, rows[1:]):
                self.assertTrue(row.startswith(CLOSURE_SUB + label),
                                "the record under L%d lacks or misplaces %s" % (nid, label))
                self.assertTrue(row[len(CLOSURE_SUB + label):].strip(),
                                "the record under L%d leaves %s empty" % (nid, label))
            self.assertTrue(DURATION.search(rows[1]),
                            "the measurement under L%d must give a real duration" % nid)
            self.assertTrue(EVIDENCE_ANCHOR.search(rows[1]),
                            "the measurement under L%d cites nothing a run could print" % nid)
            for token in R7_MEASUREMENT_TOKENS[nid]:
                self.assertIn(token, rows[1],
                              "the measurement under L%d does not cite %r" % (nid, token))
            for row in rows:
                for word in CLOSING_WORDS:
                    self.assertNotIn(word, row,
                                     "the record under L%d declares the item settled via %r" % (nid, word))
                self.assertNotIn("- [", row, "the record under L%d edits a checkbox" % nid)

    def test_r7_section_note_reports_the_split_outcome(self):
        hits = [l for l in self.lines if l.startswith(SECTION_NOTE) and R7_SECTION_ENTRY in l]
        self.assertEqual(len(hits), 1, "the note under the fifth section must stay findable")
        self.assertIn("R7 结案 L1866", hits[0], "the section note must name the item closed on evidence")
        self.assertIn("R7 结案 L1868-L1871、L1874", hits[0],
                      "the section note must name the items closed for want of a carrier")
        self.assertIn("R7 保留开放 L1860、L1867", hits[0],
                      "the section note must keep the two measured-but-failing entries visible")
        self.assertNotIn("戊类观感 8 条", hits[0],
                         "the section note must not still forward all eight items to a later round")

    def test_no_closed_entry_still_defers_its_verdict(self):
        for nid in sorted(CLOSED_IDS):
            for line in self._entry_block(nid):
                self.assertIsNone(
                    DEFERRAL.search(line),
                    "closed entry L%d leaves a verdict to a later round: %r" % (nid, line),
                )


    def _record_section_body(self, label):
        """Every line of one 结案记录 section, excluding its own heading."""
        start = [i for i, l in enumerate(self.lines)
                 if RECORD_HEAD.match(l) and RECORD_HEAD.match(l).group(1) == label]
        self.assertEqual(len(start), 1, "the ledger needs exactly one %s record section" % label)
        body = []
        for row in self.lines[start[0] + 1:]:
            if row.startswith(RECORD_SECTION_STOP):
                break
            body.append(row)
        return body

    def test_the_read_only_promise_survives_in_the_record_section(self):
        """R7 closed device items on ssh readings taken without touching the device.

        The record has to keep saying so, and no entry it closed may read as
        though a deployment, a restart or a configuration change had happened.
        """
        body = self._record_section_body(R7_SECTION_LABEL)
        text = "\n".join(body)
        self.assertIn(READ_ONLY_PROMISE, text,
                      "the R7 record no longer states that the run was read-only")
        self.assertIn(READ_ONLY_HOSTKEY, text,
                      "the R7 record no longer pins the host key it connected through")
        for line in text.split("\n"):
            for pattern in WRITE_PATTERNS:
                self.assertNotIn(pattern, line,
                                 "the read-only R7 record claims %r on the device: %r" % (pattern, line))
        for nid in sorted(CLOSED_IDS):
            for line in self._entry_block(nid):
                for pattern in WRITE_PATTERNS:
                    self.assertNotIn(
                        pattern, line,
                        "closed entry L%d claims %r although R7 wrote nothing to the device"
                        % (nid, pattern),
                    )

    def test_ledger_records_never_claim_a_pending_code_action(self):
        """The two open records ask whether a code change belongs in the code bucket.

        Until the user rules, a 「后续动作」 may describe a candidate change but may
        never report it as done, and must keep the standing promise that this
        round changed no code.
        """
        notes = self._closure_notes()
        evidence = self._evidence_notes()
        for nid, rows in sorted(notes.items()):
            for row in rows:
                for word in CODE_ACTION_WORDS:
                    self.assertNotIn(word, row,
                                     "the note of L%d claims a code action via %r" % (nid, word))
        self.assertEqual(sorted(evidence), sorted(R7_OPEN_WITH_EVIDENCE_IDS),
                         "only the measured-but-failing entries carry a 后续动作")
        for nid in sorted(R7_OPEN_WITH_EVIDENCE_IDS):
            rows = evidence[nid]
            self.assertEqual(len(rows), 4, "the record of L%d is not a full four-row note" % nid)
            action = rows[3]
            self.assertTrue(action.startswith(CLOSURE_SUB + "后续动作："),
                            "the fourth row of L%d is not its 后续动作" % nid)
            self.assertIn(NOT_CODE_ACTION, action,
                          "the 后续动作 of L%d no longer promises that this round changed no code" % nid)
            for word in CODE_ACTION_WORDS:
                self.assertNotIn(word, action,
                                 "the 后续动作 of L%d reports %r as already done" % (nid, word))

    def test_a_stopping_path_entry_cannot_claim_the_grace_gap_is_closed(self):
        """L1867 is open because 31 s of drain does not fit 10 s of host grace.

        Measuring the gap is not closing it.  Should a later round tick L1867, it
        has to say in the note that the grace period was aligned, that tick has
        to be announced in the source-section note, and the round that announces
        it may not also be a round that left the entry open.
        """
        self.assertFalse(
            CLOSED_IDS & R7_OPEN_WITH_EVIDENCE_IDS,
            "an entry recorded as measured-but-failing cannot also be closed",
        )
        ticked = self._ticked_ids()
        if 1867 in ticked:
            rows = self._note_rows_at_card(1867, CLOSURE_HEAD, "closure note")
            for word in GRACE_CLOSURE_WORDS:
                self.assertIn(word, rows[0],
                              "a ticked L1867 must say its %r gap was aligned" % word)
            announced = [l for l in self.lines
                         if l.startswith(SECTION_NOTE)
                         and re.search(r"R\d+ 结案 L1867", l)]
            self.assertEqual(len(announced), 1,
                             "a ticked L1867 must be announced once in the source-section note")
        else:
            self.assertFalse(self._closure_notes().get(1867),
                             "L1867 is open and must not carry a closure note")

if __name__ == "__main__":
    unittest.main()
