"""The maintenance panel is an ordered repair, not three equal buttons.

R564 replaced a flex row of three same-weight buttons with two numbered steps and a
separate danger zone. That order is the point: pruning stale ids first is what makes
the identity migration land on a clean set, and "clear everything" must not sit in
the same row as "tidy up" where a mis-tap costs the whole library.

These assertions exist so a later layout pass cannot quietly flatten the panel back
into three equal buttons, or drop the aria-labels that keep the action names legible
to a screen reader once the visible text is shortened to "清理" / "重建并迁移".
"""

import re
import unittest
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "app" / "ui"


def read(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


class MaintenancePanelTests(unittest.TestCase):
    def setUp(self):
        self.html = read("index.html")
        start = self.html.index('data-settings-block="advanced-maintenance"')
        # The next settings block ("关于") closes this one, nested divs and all.
        end = self.html.index('data-settings-block="advanced-about"', start)
        self.block = self.html[start:end]
        self.css = read("app.css")

    def test_two_steps_are_numbered_and_ordered(self):
        steps = re.findall(r'<li class="maintenance-step">(.*?)</li>', self.block, re.S)
        self.assertEqual(len(steps), 2, "exactly two repair steps")
        numbers = re.findall(r'class="maintenance-step-no"[^>]*>(\d)<', self.block)
        self.assertEqual(numbers, ["1", "2"], "steps carry their order in the markup")
        self.assertLess(
            self.block.index("pruneFavoritesBtn"),
            self.block.index("reindexIdentityBtn"),
            "pruning comes before the migration: migrating first would carry the stale ids over",
        )

    def test_danger_zone_is_separate_and_last(self):
        self.assertIn("maintenance-danger-zone", self.block)
        self.assertLess(
            self.block.index("maintenance-steps"),
            self.block.index("maintenance-danger-zone"),
            "the irreversible action sits below the repair steps",
        )
        zone = self.block[self.block.index("maintenance-danger-zone"):]
        self.assertIn("resetUserStateBtn", zone, "clearing lives in the danger zone, not in the steps")
        self.assertNotIn("resetUserStateBtn", self.block[: self.block.index("maintenance-danger-zone")])

    def test_buttons_keep_the_full_action_as_their_accessible_name(self):
        pairs = {
            "pruneFavoritesBtn": "清理失效收藏",
            "reindexIdentityBtn": "重建曲目标识并迁移收藏",
            "resetUserStateBtn": "清空收藏与播放列表",
        }
        for button_id, action in pairs.items():
            with self.subTest(button=button_id):
                match = re.search(
                    r'<button\b[^>]*id="%s"[^>]*>(.*?)</button>' % re.escape(button_id),
                    self.block,
                    re.S,
                )
                self.assertIsNotNone(match, button_id + " must be a button with text")
                tag = match.group(0)[: match.group(0).index(">")]
                self.assertIn('aria-label="%s"' % action, tag)
                visible = re.sub(r"<[^>]*>", "", match.group(1)).strip()
                self.assertLess(len(visible), len(action), "the face of the button is the short form")
                self.assertTrue(visible, "short is not empty")

    def test_layout_is_a_stacked_step_list_with_a_narrow_rule(self):
        self.assertIn(".maintenance-steps{list-style:none", self.css)
        self.assertIn("grid-template-columns:22px minmax(0,1fr) auto", self.css)
        narrow = self.css[self.css.index("@media(max-width:760px){", self.css.index(".maintenance-steps")):]
        self.assertIn(".maintenance-step-action{grid-column:1/-1", narrow,
                      "phones stack the button under the copy instead of squeezing it into a column")
        self.assertNotIn(".data-maintenance-actions", self.css,
                         "the old equal-width grid is gone; a leftover rule would fight this one")
        self.assertNotIn("data-maintenance-actions", self.html)


if __name__ == "__main__":
    unittest.main()
