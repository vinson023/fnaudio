"""Guard the evidence cards added to the external-acceptance ledger by R2.

``docs/external-acceptance.md`` holds the 45 device and externally-blocked items
that were moved out of ``TODO.md``.  Before this round every one of them was
written as a wish: it named no device, no material, no observable result, so no
round could ever tell "not yet verifiable" apart from "verifiable and failing".
Each entry now carries one fixed-format evidence card immediately after its
``<!-- END Lnnn -->`` marker, stating the device or material the check needs,
what has to be captured, the line that decides pass or fail, and what to record
when the material can never be produced.

These tests keep that contract.  They are deliberately shape-only: nothing here
can close a device item, because the items themselves stay unchecked -- the card
says how to decide, not what was decided.
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

    def test_ledger_checkboxes_are_untouched_by_the_cards(self):
        open_rows = [l for l in self.lines if l.startswith("- [ ] ")]
        done_rows = [l for l in self.lines if l.startswith("- [x]")]
        self.assertEqual(len(open_rows), 45, "an item was ticked off by the cards")
        self.assertEqual(len(done_rows), 0, "no device item may be closed by this round")

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


if __name__ == "__main__":
    unittest.main()
