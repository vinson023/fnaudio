"""Guard the device-segment migration done by round R141 (device disposition R1).

The per-round ledger had been carrying 45 items that no offline test can advance:
they need real hardware, a real NAS, a phone, or material that does not exist in
this checkout.  Those items now live in one place, ``docs/external-acceptance.md``,
and ``TODO.md`` keeps only a pointer per source section.  This file is the only
thing that keeps the migration honest, because ``docs/`` is deliberately outside
``SOURCE_MANIFEST.sha256`` (that manifest walks ``src/`` and ``android-client/``
only).

What is pinned here:

* the frozen original text of all 45 entries, one SHA-256 each, so nobody can
  rewrite, trim, or "complete" a device item while claiming it was only moved --
  the hash covers the entry line plus its indented continuation lines, joined by
  LF with a trailing newline, and the only byte the hash refuses to pin is the
  `- [ ]`/`- [x]` state character, because the ledger is where a closed device
  item is meant to be ticked off;
* the device segment of ``TODO.md`` holds no open checklist item any more, which
  is the termination condition this round buys;
* each of the five source sections carries exactly one migration note, and that
  note is not itself a checklist entry;
* source comments stop citing ``TODO.md`` line numbers inside the device segment,
  because the text they pointed at no longer lives there.

Deliberately *not* pinned: the global open/closed counts of ``TODO.md``.  Those
move every round by design; hard-coding them would manufacture a red gate for
the next round rather than guard this one.
"""

from pathlib import Path
import hashlib
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
TODO = REPO_ROOT / "TODO.md"
LEDGER = REPO_ROOT / "docs" / "external-acceptance.md"
SRC = REPO_ROOT / "src"

DEVICE_SEGMENT_START = "## 宿主 MediaSession"
DEVICE_SEGMENT_END = "# 当前持续优化目标"
MIGRATION_NOTE = "2026-09-21（R141 设备段处置 R1）"
LEDGER_LINK = "docs/external-acceptance.md"

# The five sections whose device items were moved out, in ledger order.
LEDGER_SECTIONS = 5

BLOCK_START = re.compile(r"^<!-- BEGIN L(\d+) -->$")
BLOCK_END = re.compile(r"^<!-- END L(\d+) -->$")
ENTRY_ID = re.compile(r"^### 固定编号 L(\d+)$")
CHECKLIST = re.compile(r"^- \[[ xX]\] ")
TODO_LINE_REF = re.compile(r"TODO\.md:(\d+)")

# Frozen digests of the migrated entries as they read on disk immediately before
# the move.  The key is the entry's fixed id: its pre-migration ``TODO.md`` line
# number, which stays its name in the ledger even though ``TODO.md`` renumbered.
FROZEN_ENTRY_DIGESTS = {
    821: "ee4d87be6068394b48e53c327c02dc79f37851b407d8971b4aa24c729865a914",
    827: "f7957bb06fdf62e760885df127307dd8a7292d8d139e44c0d37b1e2da3004caf",
    830: "2d74a8c91fdb5b8fed3b320e2af558d7ad2392a58f9b032a0a4da7bcdd94631e",
    834: "0e2009d897a3b567cb1d5d8d64c4bffc4eb1840ba6747bc511f3e2ede66a170b",
    835: "d08e49ba08aca9e9cd89b7646c387568d2a9797220360fd67d8f9965375725b7",
    838: "fc54e48e91cb22509a79cfa8db7e71a416de45174ec8ee10e07f56db226be5fe",
    841: "50fa12f0ce1b40506552cbfdc181eb2818efd7012cb8abdf950e3de77f1c004b",
    843: "2a5f397935332daa4a41558dfc5fc15ae5f7949ce8d8e3a0349a207fb45887aa",
    845: "5767815e75a852e0eee398116e87b2df06b56316c8531ee3dae0bc777da1e8db",
    853: "0bf70d3b5bc821fd30846c89518ebbe62bdd1d9656732d82bd92bc927cd641da",
    984: "649f4bac4b37c66f20b518238396c858a1bb5a9f8366319e3df362938e6ceab8",
    986: "56d8c57fc0649553f988829e688c9c2293220b79be6ff03d83b4e25a8ce4c7d3",
    988: "64b111eb54637a81e3a9f81c11d5ab8f8c2dc5c0b5a2920ae1f9a4642e35dcc1",
    990: "e8bdd5824d1b1f341ed2cc8d24723ed23387ed4dad0ae968079288ea1c333cc7",
    992: "8e8af90b0b5f60cee5d3673b0b9395468b9e33db85a0027f9ac71961c1654ad5",
    1184: "5e5552cddc680dd344330ff68a76fd2d225d637b70e961306d949c0330bd36cb",
    1836: "195c44336571c8049a54fde6a396cb4edbcaaf1d70fbe537e28e67ea2fb34177",
    1837: "49ee474755f4ab63356a3028e4c7baaebe7485fb1fa240acc87b977e30a045b6",
    1838: "e9bcba1a9d1d65f31032e7f721cc9208ca0fc3601d27064f0310b8fb9fcd6a6a",
    1847: "7634d472e0e702e24dcf5da9596a1e770ad0c0621c0ccf468ce2ba60820a313f",
    1852: "aabba21816a284890efcf7fb993d1878b7f5fc78a001a2c848ae3da1a2e8046c",
    1853: "53951440c9676415913f2d28054d9366a601b95727ff5d36124e740c1fc763c8",
    1854: "d9bc59acc092459b340a474bd2227adff4a0d8a0ceb961393bb73b04446bca7b",
    1855: "c98a02588e81e878ec5eec7b69dea989aa4a0126c2ad2e98dfe1c56512504145",
    1856: "a4814c196ee02ce6f8341c11e680cb0284f863d76b3062754e12a92bf24633fe",
    1857: "80cc7934b54b181a5235443fdf394e244ddc1bd13cb699f61245b6f5d69a7d3d",
    1858: "791fa1009f88b822557c02bde782f7cc6c73a9f277f14c80942606c1374ba5ef",
    1859: "4e13e8dacd5394fdfc4035f82a657d05894033bb8079fe4f3307d271225a7762",
    1860: "bc8eb8b757a0c45cea67e3b425904b23555ceefa1eb7d0c5d430755bd04b316b",
    1861: "27dc5622e071aa38f8be7741ad8c7c5a653370eab92b818b1c9ab8f532fbdfae",
    1862: "d3c72710666ad485946974070b9f75ab9d997e7f6cc1fee5c980d348b332020e",
    1863: "cfae7868c98324e48e3487a0c24d0916065108c19c75323fcd0e41f18eb7fb55",
    1864: "833c486ef23f12e1f89505cc58faba11b59bd3a103d7224662f7940cc6052cb9",
    1865: "daf0d3bb04ff5da92aff7995b77eb7f3fd9bf2f89d799de134abd663e564686b",
    1866: "5df06abd063e429e05d1a40c01d84f1603da38948e43fda0eccecde840bf3f5a",
    1867: "e5a7780fc3b5c67e32f8ae249eb8de2b729add9325327b1103f1860482ba6530",
    1868: "ba569dfef673c8a5bdf24755a3b791fb3a096e7c747285a16c517b68f8051a58",
    1869: "13066767b3a614037066a2713620a544e3210e33d327c9a5e5c24101fe959595",
    1870: "a093b19208f656914b18575f7e274fc19b6082d5e0e0548ed9a0cc1c4e8f5b6c",
    1871: "004cf77500a1ed52057284ffa3921a9cc8094a688e7b016211a5fb7e439dce61",
    1872: "3f17c74f4af3e4ee91467e9ce09542b3fb2d4b1df2c75bf385efb44ae41164e8",
    1873: "d803b0c81e44b0d01eccb0f5ac5a485396439993559b492715403290defb3e35",
    1874: "3df4d1982071c91349fa0d096b924de496b059a049c40f5c1aa9a86ed72baa4d",
    1876: "73d0b17a01dd23da92a33c90eba76971e50fd75ec5485032d35ef413e5de67db",
    1878: "6f0dcc9de0a231e62dfdc4ca15289aed9ffa960bcd14fad22f4fe109be095eee",
}


CHECKBOX_STATE = re.compile(r"^(- )\[([ xX])\]( .*)$")


def unflexed_block_lines(block_lines):
    """Blank out the checkbox state of an entry block, nothing else.

    The ledger states its own recording rule as 「勾选状态只在本文件内推进」: when a
    later round finally gets hardware evidence for a device item, it has to be able
    to write `- [x]` here.  If the state character were part of the frozen bytes,
    that round would turn the gate red for doing its job, so the digest pins the
    wording, the indentation and the line structure while granting exactly this
    one freedom.
    """
    lines = []
    for line in block_lines:
        match = CHECKBOX_STATE.match(line)
        lines.append("%s[ ]%s" % (match.group(1), match.group(3)) if match else line)
    return lines


def digest(block_lines):
    """SHA-256 of one entry block: LF-joined lines plus a trailing newline."""
    return hashlib.sha256(("\n".join(unflexed_block_lines(block_lines)) + "\n").encode("utf-8")).hexdigest()


def ledger_blocks(text):
    """Map fixed id -> original-text lines, for every BEGIN/END pair in the ledger."""
    blocks = {}
    current = None
    for line in text.split("\n"):
        head = BLOCK_START.match(line)
        if head:
            number = int(head.group(1))
            if number in blocks:
                raise AssertionError("ledger repeats the fixed id L%d" % number)
            current = number
            blocks[number] = []
            continue
        tail = BLOCK_END.match(line)
        if tail:
            number = int(tail.group(1))
            assert current is not None, "ledger closes L%d without opening it" % number
            assert number == current, "ledger nesting is broken at L%d (open L%d)" % (number, current)
            current = None
            continue
        if current is not None:
            blocks[current].append(line)
    return blocks


def device_segment(lines):
    """TODO lines from the device heading up to the standing-goal heading."""
    start = next((i for i, line in enumerate(lines) if line.startswith(DEVICE_SEGMENT_START)), None)
    assert start is not None, "TODO.md lost the device segment heading"
    stop = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(DEVICE_SEGMENT_END)), len(lines))
    return start, stop, lines[start:stop]


class DeviceTodosMigratedTests(unittest.TestCase):
    def setUp(self):
        self.todo_lines = TODO.read_text(encoding="utf-8").split("\n")
        self.assertTrue(LEDGER.is_file(), "%s is missing: the device backlog has no home" % LEDGER)
        self.ledger_text = LEDGER.read_text(encoding="utf-8")

    def test_every_frozen_entry_survives_the_move_verbatim(self):
        blocks = ledger_blocks(self.ledger_text)
        self.assertEqual(
            sorted(blocks), sorted(FROZEN_ENTRY_DIGESTS),
            "the ledger must carry exactly the %d migrated entries, no more and none dropped"
            % len(FROZEN_ENTRY_DIGESTS),
        )
        altered = [n for n in sorted(blocks) if digest(blocks[n]) != FROZEN_ENTRY_DIGESTS[n]]
        self.assertEqual(
            altered, [],
            "entry text was rewritten after migration; the ledger may append notes outside the "
            "markers but must not touch what is between them (fixed ids: %s)" % altered,
        )

    def test_ledger_headings_agree_with_the_frozen_blocks(self):
        ids = [int(m.group(1)) for m in (ENTRY_ID.match(line) for line in self.ledger_text.split("\n")) if m]
        self.assertEqual(
            ids, sorted(FROZEN_ENTRY_DIGESTS),
            "each frozen block needs exactly one 「### 固定编号 L<n>」 heading, in the same order",
        )

    def test_the_frozen_digest_pins_words_but_not_the_checkbox(self):
        """Discriminating case for 「勾选状态只在本文件内推进」.

        Ticking a device item must keep the gate green; changing one character of
        the entry text must not.  Both directions are asserted so this test fails
        if the normalisation is widened into "ignore the line entirely".
        """
        original = ["- [ ] \u9700\u8981\u771f\u673a\u9a8c\u8bc1\u7684\u6761\u76ee", "  \u7eed\u884c\u8bf4\u660e"]
        for state in ("x", "X"):
            self.assertEqual(
                digest(["- [%s] %s" % (state, original[0][6:])] + original[1:]),
                digest(original),
                "a later round that closes %s on hardware would break this gate" % original[0][6:],
            )
        altered = [
            ["- [ ] \u9700\u8981\u771f\u673a\u9a8c\u8bc1\u7684\u6761\u76ee ", "  \u7eed\u884c\u8bf4\u660e"],
            ["- [ ] \u9700\u8981\u771f\u673a\u9a8c\u8bc1\u7684\u6761\u76ee", "  \u7eed\u884c\u8bf4\u660e\u3002"],
            ["- [x] \u9700\u8981\u771f\u673a\u9a8c\u8bc1"],
            ["[ ] \u9700\u8981\u771f\u673a\u9a8c\u8bc1\u7684\u6761\u76ee", "  \u7eed\u884c\u8bf4\u660e"],
        ]
        for candidate in altered:
            self.assertNotEqual(digest(candidate), digest(original), "the digest stopped pinning: %r" % candidate)

    def test_device_segment_of_the_todo_holds_no_open_item(self):
        start, stop, segment = device_segment(self.todo_lines)
        open_lines = [start + 1 + offset for offset, line in enumerate(segment) if CHECKLIST.match(line) and line.startswith("- [ ] ")]
        self.assertEqual(
            open_lines, [],
            "TODO.md lines %s are still-open device items; they belong to %s" % (open_lines, LEDGER_LINK),
        )
        self.assertGreater(
            stop - start, 1,
            "the device segment collapsed to nothing -- the section headings and migration notes "
            "have to stay so the pointer survives",
        )

    def test_each_source_section_keeps_one_pointer_note(self):
        notes = [line for line in self.todo_lines if line.startswith(MIGRATION_NOTE)]
        self.assertEqual(
            len(notes), LEDGER_SECTIONS,
            "the device segment must keep one migration note per source section, found %d" % len(notes),
        )
        for line in notes:
            self.assertIn(LEDGER_LINK, line, "a migration note stopped pointing at the ledger")
            self.assertFalse(line.startswith("- ["), "a migration note must not be a checklist entry")
        sections = [
            (i, line) for i, line in enumerate(self.todo_lines)
            if line.startswith("## ") and i + 1 < len(self.todo_lines)
            and self.todo_lines[i + 2].startswith(MIGRATION_NOTE)
        ]
        self.assertEqual(
            len(sections), LEDGER_SECTIONS,
            "every note has to sit directly under its own 「## 」 heading",
        )

    def test_source_comments_stop_citing_moved_todo_lines(self):
        heading_line = next(
            (i + 1 for i, line in enumerate(self.todo_lines) if line.startswith(DEVICE_SEGMENT_START)),
            None,
        )
        offenders = []
        for path in sorted(SRC.rglob("*")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_number, line in enumerate(text.split("\n"), start=1):
                for match in TODO_LINE_REF.finditer(line):
                    if int(match.group(1)) >= heading_line:
                        offenders.append("%s:%d cites TODO.md line %s" % (path.relative_to(REPO_ROOT).as_posix(), line_number, match.group(1)))
        self.assertEqual(
            offenders, [],
            "the device segment starts at TODO.md line %d and its items moved out, so a citation "
            "at or after it now points at a different entry: %s" % (heading_line, offenders),
        )


if __name__ == "__main__":
    unittest.main()
