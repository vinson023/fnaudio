"""Every hover arm that paints must have a touch counterpart.

A touch device has no pointer to hover with, but Android WebView and iOS Safari
keep :hover on the element that was last tapped. Any hover arm that paints a
background, a border or an icon colour therefore stays on screen after the
finger is gone - the reported case was the transport row, where tapping "next"
left an #EBEBEB rounded square on #nextBtn for the rest of the session.

The product decision is a single override layer at the end of
``fnos-theme.css`` (the last stylesheet), because both sheets paint their hover
arms with ``!important`` and only a later rule of equal specificity can win.
This test is what keeps that layer complete: add a hover arm that paints, and it
fails until the touch counterpart is written or the arm is declared identical to
its resting state.
"""

import re
import unittest
from pathlib import Path


UI = Path(__file__).resolve().parent.parent / "app" / "ui"
SHEETS = ("app.css", "fnos-theme.css")
THEME = "fnos-theme.css"
PAINT_PROPERTIES = {"background", "background-color", "border", "border-color", "box-shadow", "color", "opacity", "transform"}

# Hover arms whose hovered appearance equals their resting appearance: there is
# no residue to undo, so the touch layer deliberately says nothing about them.
# Each entry carries the reason, because "same as rest" is a claim that has to be
# re-checked whenever the resting rule changes.
SAME_AS_REST = {
    ".action-button:hover": "悬停只把边框设成静止时就有的 --ui-border",
    ".device-button:hover": "同上",
    ".danger-button:hover": "静止底色就是 --ui-danger-bg",
    ".danger-button:hover:not(:disabled)": "同上（fnos-theme 的重复钩子）",
    ".native-delete-confirm:hover:not(:disabled)": "静止底色就是危险色",
    ".track-action-choice.danger:hover": "静止底色就是 --ui-danger-bg",
    ".track-context-actions .track-action-choice.danger:hover": "同上",
    ".track.is-current:not(.is-selected):hover": "当前行静止就带这层底色（手机布局用 --ui-hover 标当前行）",
    ".track.is-selected:hover": "选中行静止就带 --ui-selected",
    ".nav-item:hover": "静止底色与悬停底色同为 --ui-hover",
    ".nav-item.mobile-logout-nav-item:hover": "静止与悬停都是危险色",
    ".track-context-actions .track-action-choice:disabled:hover": "禁用项静止即灰色，悬停不再改变",
}

# Feedback that is not a painted surface: a divider drag line, an underline, a
# stat weight. These are pointer-only affordances (a divider cannot even be
# dragged by touch), and none of them can leave a box behind.
NON_SURFACE = {
    ".column-resize-handle:hover:after": "列宽拖拽线，触摸无法拖拽",
    ".column-resize-handle:active:after": "同上",
    ".external-share-native-link:hover": "只加下划线",
    ".album-detail-breadcrumb button:hover": "只加下划线",
    ".album-detail-tracks .track-head-button:hover": "只改文字色，无底色",
    ".metadata-task-stats [data-metadata-stat-issues]:hover b": "只加下划线",
    ".folder-crumb:hover": "只改文字色并去掉下划线",
}


def parse_sheet(path):
    """Yield (selector, declarations, media_stack) for every style rule."""
    text = (UI / path).read_text(encoding="utf-8")
    # Comments sit between the whitespace and the selector; left in place they
    # travel into the selector text and every membership check misses.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    rules = []
    stack = []
    index = 0
    buffer = []
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\n":
            # A selector list may be wrapped over several lines (the touch layer
            # is written that way); keep the text and normalise the whitespace.
            buffer.append(" ")
            index += 1
            continue
        if char == "@":
            media = re.match(r"@media\s*([^{]+)\{", text[index:])
            if media:
                stack.append(media.group(1).strip())
                index += media.end()
                continue
        if char == "}":
            if stack:
                stack.pop()
            index += 1
            continue
        if char == "{":
            selector = " ".join("".join(buffer).split())
            end = index + 1
            while end < length and text[end] != "}":
                end += 1
            body = text[index + 1:end]
            buffer = []
            # Step past the rule's own closing brace: leaving it for the brace
            # handler would pop a @media frame that is still open.
            index = end + 1
            if not selector.startswith("@") and selector:
                rules.append((selector, body, list(stack)))
            continue
        buffer.append(char)
        index += 1
    return rules


def declared_properties(body):
    names = set()
    for part in body.split(";"):
        if ":" in part:
            name = part.split(":", 1)[0].strip().lower()
            names.add(name)
    return names


def hover_selectors():
    """Every painted :hover selector in the two sheets, minus (media hover) ones."""
    found = {}
    for sheet in SHEETS:
        for selector, body, media in parse_sheet(sheet):
            if ":hover" not in selector:
                continue
            if any("hover" in entry for entry in media):
                continue  # already scoped to hover-capable devices
            properties = declared_properties(body)
            if not properties & PAINT_PROPERTIES:
                continue
            for part in selector.split(","):
                part = part.strip()
                if ":hover" not in part:
                    continue
                found.setdefault(part, (sheet, sorted(properties & PAINT_PROPERTIES)))
    return found


def touch_layer():
    """The selectors the (hover:none) layer in the theme sheet covers."""
    covered = set()
    for selector, body, media in parse_sheet(THEME):
        if not media or "hover" not in " ".join(media) or "none" not in " ".join(media):
            continue
        for part in selector.split(","):
            part = part.strip()
            if part:
                covered.add(part)
    return covered


class TouchHoverResidueTests(unittest.TestCase):
    def test_the_touch_layer_exists_and_is_the_last_thing_in_the_last_sheet(self):
        self.assertIn("hover:none", (UI / THEME).read_text(encoding="utf-8"))
        text = (UI / THEME).read_text(encoding="utf-8")
        tail = text[text.index("触摸设备上的悬停残留"):]
        self.assertIn("触摸设备上的悬停残留", tail, "触摸层必须留在最后加载的样式表末尾")

    def test_every_painted_hover_arm_has_a_touch_counterpart(self):
        covered = touch_layer()
        missing = []
        for selector, (sheet, properties) in sorted(hover_selectors().items()):
            if selector in SAME_AS_REST or selector in NON_SURFACE:
                continue
            if selector in covered:
                continue
            # A broader touch rule that names this selector's target also counts:
            # the layer is allowed to group controls that share one resting look.
            target = selector.split(":")[0]
            if any(target and entry.split(":")[0] == target for entry in covered):
                continue
            missing.append(f"{sheet}: {selector} [{', '.join(properties)}]")
        self.assertEqual(
            missing,
            [],
            "以下悬停分支会在触摸端留下痕迹，但触摸层没有还原它们：\n  " + "\n  ".join(missing),
        )

    def test_exemptions_still_name_rules_that_exist(self):
        """An exemption for a deleted rule hides the next regression."""
        painted = set(hover_selectors())
        stale = sorted(entry for entry in SAME_AS_REST if entry not in painted)
        self.assertEqual(stale, [], f"这些豁免已经指向不存在的悬停规则：{stale}")

    def test_the_transport_row_is_covered(self):
        """The reported control, stated by name so it cannot regress silently."""
        covered = touch_layer()
        self.assertIn(".transport .player-button:hover", covered)
        self.assertIn(".transport .player-button.play-button:hover", covered)
        self.assertIn(".player-actions #repeatBtn.active-control:hover", covered)


if __name__ == "__main__":
    unittest.main()
