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
decides an item, a card only states how to decide it.  R4 later closed nine
entries whose material can never be produced on this host, and each of those
ticks is bound to a note repeating the cannot-be-evidenced verdict written on
its own card, so a tick here can never be read as "the judgement line passed".
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

# ---- R4 closure bookkeeping: entries whose material can never be produced ----
# R4 closes nine ledger entries as "not evidenceable on this host".  A bare tick
# would read as "someone verified this", so every R4 tick is bound to a four-line
# note placed directly under its own card: the note must quote the verdict phrase
# that very card prescribes, must carry a real measurement, the missing material
# and a reopening condition, and must never claim the judgement line passed.  The
# record section at the foot of the file states the same set a third time; any
# disagreement between the three readings -- ticks, notes, record -- is red.
R4_CLOSED_IDS = frozenset({1838, 1852, 1853, 1854, 1855, 1856, 1857, 1872, 1873})
R4_CLOSURE_DATE = "2026-09-21"
CLOSURE_HEAD = re.compile(r"^> \*\*结案（R4·(\d{4}-\d{2}-\d{2})）\*\*：(.*)$")
CLOSURE_FIELDS = ("实测：", "缺料：", "重开条件：")
CLOSURE_SUB = "> - "
R4_RECORD_HEAD = "## R4 结案记录"
R4_RECORD_HEAD_END = "## "
R4_RECORD_ID = re.compile(r"^- L(\d+)$")
TICKED_STATE = re.compile(r"^- \[[xX]\] ")
VERDICT_PHRASE = re.compile(r"「([^」]+)」")
VERDICT_FIELD = "不可取证时结案口径"
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
DEFERRED_ID = 1836        # its closing line is re-ruled by R5, card stays shape-valid


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

    def _verdict_phrase(self, nid):
        """The single verdict phrase the card itself prescribes for this entry."""
        fields = dict(self._cards()).get(nid, {})
        phrases = VERDICT_PHRASE.findall(fields.get(VERDICT_FIELD, ""))
        self.assertEqual(
            len(phrases), 1,
            "card L%d must prescribe exactly one verdict phrase, got %s" % (nid, phrases),
        )
        return phrases[0]

    def test_r4_ticks_and_their_notes_are_the_same_set(self):
        notes = self._closure_notes()
        ticked = self._ticked_ids()
        noted = [nid for nid, rows in notes.items() if rows]
        self.assertEqual(sorted(ticked), sorted(R4_CLOSED_IDS),
                         "R4 must tick exactly its nine entries, no more and no less")
        self.assertEqual(sorted(noted), sorted(R4_CLOSED_IDS),
                         "a tick without its note, or a note without its tick")
        open_rows = [l for l in self.lines if l.startswith("- [ ] ")]
        done_rows = [l for l in self.lines if TICKED_STATE.match(l)]
        self.assertEqual(len(done_rows), 9, "R4 closes nine device items")
        self.assertEqual(len(open_rows), 45 - 9, "the other 36 entries stay open")

    def test_closure_note_quotes_the_verdict_of_its_own_card(self):
        notes = self._closure_notes()
        phrases = {}
        for nid in sorted(R4_CLOSED_IDS):
            self.assertTrue(notes.get(nid), "closed entry L%d carries no closure note" % nid)
            phrases[nid] = self._verdict_phrase(nid)
            self.assertIn("「%s」" % phrases[nid], notes[nid][0],
                          "the note for L%d does not repeat the verdict its own card prescribes" % nid)
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
        for nid in sorted(R4_CLOSED_IDS):
            rows = notes[nid]
            self.assertEqual(len(rows), 4,
                             "note for L%d must be one head plus three sub-fields: %s" % (nid, rows))
            head = CLOSURE_HEAD.match(rows[0])
            self.assertTrue(head, "note head for L%d does not match the R4 shape" % nid)
            self.assertEqual(head.group(1), R4_CLOSURE_DATE,
                             "note for L%d carries a date other than the closing round" % nid)
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

    def test_r4_record_section_matches_the_ticked_set(self):
        heads = [i for i, l in enumerate(self.lines) if l.startswith(R4_RECORD_HEAD)]
        self.assertEqual(len(heads), 1, "the ledger needs exactly one R4 record section")
        start = heads[0]
        body, ids = [], []
        for row in self.lines[start + 1:]:
            if row.startswith(R4_RECORD_HEAD_END):
                break
            body.append(row)
            match = R4_RECORD_ID.match(row)
            if match:
                ids.append(int(match.group(1)))
        self.assertEqual(sorted(ids), sorted(R4_CLOSED_IDS),
                         "the R4 record section lists another set than the ledger ticks")
        self.assertEqual(len(ids), len(set(ids)), "the R4 record repeats an entry")
        text = "\n".join(body)
        self.assertIn(NOT_PASSED_PROMISE, text,
                      "the R4 record must state that closing an entry is not passing its judgement line")
        for nid in sorted(R4_CLOSED_IDS):
            self.assertIn("- L%d" % nid, text, "the R4 record omits L%d" % nid)


if __name__ == "__main__":
    unittest.main()
