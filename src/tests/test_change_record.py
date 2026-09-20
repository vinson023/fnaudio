"""Keep the root change records well formed and mutually consistent.

The project rule is that every change round leaves an entry at the top of
``CHANGELOG_AI.md``, ``TODO.md`` and ``PROJECT_CONTEXT.md``.  Dates and formatting
drift silently once that happens, so this gate checks the leading flat run of all
three instead of trusting a reviewer to notice.
"""

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = REPO_ROOT / "CHANGELOG_AI.md"
TODO = REPO_ROOT / "TODO.md"
CONTEXT = REPO_ROOT / "PROJECT_CONTEXT.md"

DATE_PATTERN = r"(\d{4})-(\d{2})-(\d{2})"
ENTRY_PATTERNS = {
    "CHANGELOG_AI.md": re.compile(r"^- " + DATE_PATTERN + r" \u2014 \S"),
    "TODO.md": re.compile(r"^- \[[^\]]+\] " + DATE_PATTERN + r"[： ]\S"),
    # The rule file spells its entries two ways ("：text" and "： **rule**"), so the
    # separator may be followed by blanks; every entry still has to be dated.
    "PROJECT_CONTEXT.md": re.compile(r"^- " + DATE_PATTERN + r"[：: ]\s*\S"),
}
DATE_ONLY = re.compile(r"^- (?:\[[^\]]+\] )?" + DATE_PATTERN)


def flat_entries(path):
    """Return (line number, text) for the leading entry run after the title."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines, "%s must not be empty" % path.name
    assert lines[0].startswith("# "), "%s must start with a title line" % path.name
    entries = []
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            break
        entries.append((number, line))
    return lines, entries


class ChangeRecordTests(unittest.TestCase):
    def test_every_flat_entry_is_dated_and_newest_first(self):
        for name in ("CHANGELOG_AI.md", "TODO.md", "PROJECT_CONTEXT.md"):
            path = REPO_ROOT / name
            with self.subTest(record=name):
                _lines, entries = flat_entries(path)
                self.assertGreater(len(entries), 0, "%s has no recorded entry" % name)
                pattern = ENTRY_PATTERNS[name]
                seen = []
                for number, line in entries:
                    self.assertTrue(
                        pattern.match(line),
                        "%s line %d is not a dated entry: %s" % (name, number, line[:60]),
                    )
                    seen.append(DATE_ONLY.match(line).groups())
                inversions = [
                    "%s line %d: %s follows %s" % (name, number, entries[number - 2][1][:40], seen[index - 1])
                    for index, (number, _line) in enumerate(entries)
                    if index and seen[index] > seen[index - 1]
                ]
                self.assertEqual(inversions, [], "records must stay newest-first")

    def test_no_entry_is_recorded_twice(self):
        """Records are written by scripted prepends, so a repeated block is a
        real failure mode and not only a formatting slip: two rounds back the
        2026-09-05 and 2026-09-07 entries were each pasted twice, and a re-run
        of a prepend step reproduces that immediately. Date order stays valid
        either way, so this has to be checked on its own.

        The rule file is not checked here: its entries are prose paragraphs that
        legitimately quote one another, and only the ordering invariant applies.
        """
        for name in ("CHANGELOG_AI.md", "TODO.md"):
            path = REPO_ROOT / name
            with self.subTest(record=name):
                _lines, entries = flat_entries(path)
                texts = [line for _number, line in entries]
                repeated = sorted({
                    line[:70] for line in texts if texts.count(line) > 1
                })
                self.assertEqual(
                    repeated, [], "%s records the same entry more than once" % name
                )

    def test_every_record_agrees_on_the_latest_round(self):
        """A round is only recorded when the log, the todo list and the rule file
        agree: three files are prepended by the same scripted step, and one of them
        quietly missing a round is how a takeover loses the plot.
        """
        newest = {}
        for name in ("CHANGELOG_AI.md", "TODO.md", "PROJECT_CONTEXT.md"):
            _lines, entries = flat_entries(REPO_ROOT / name)
            dates = [DATE_ONLY.match(line).groups() for _number, line in entries if DATE_ONLY.match(line)]
            self.assertTrue(dates, name)
            newest[name] = max(dates)
        self.assertEqual(
            set(newest.values()),
            {newest["CHANGELOG_AI.md"]},
            "add the missing entry: %r" % (newest,),
        )


if __name__ == "__main__":
    unittest.main()