"""The launcher tile has to keep air around its four corners.

The tile *is* the icon's shape on Android, so the mark cannot be sized like the
fnOS app-centre one - there it competes for space in a grid, here it has to leave
the rounded corners visible. At the fnOS scale the note filled 77% of the tile's
height and the corners looked pinched (reported 2026-11-16); it is now ~61%.

These are pixel measurements of the files that actually ship, not of the generator,
so a hand-edited PNG is caught too.
"""

import unittest
from pathlib import Path

from PIL import Image

RES = Path(__file__).resolve().parents[2] / "android-client" / "app" / "src" / "main" / "res"
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def ink_box(image, is_mark):
    pixels = image.convert("RGB").load()
    width, height = image.size
    xs, ys = [], []
    for y in range(height):
        for x in range(width):
            if is_mark(pixels[x, y]):
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), max(xs), min(ys), max(ys)


def is_blue(pixel):
    r, g, b = pixel
    return b > 150 and b - r > 60


class LauncherTileTests(unittest.TestCase):
    def test_every_density_leaves_the_corners_visible(self):
        for density, expected in DENSITIES.items():
            with self.subTest(density=density):
                path = RES / ("mipmap-" + density) / "ic_launcher.png"
                self.assertTrue(path.is_file(), path)
                image = Image.open(path)
                self.assertEqual(image.size, (expected, expected))
                box = ink_box(image, is_blue)
                self.assertIsNotNone(box, "the tile has to contain the mark")
                left, right, top, bottom = box
                width = (right - left) * 100 / expected
                height = (bottom - top) * 100 / expected
                self.assertLessEqual(width, 55, "symbol is too wide for the tile: %.1f%%" % width)
                self.assertLessEqual(height, 66, "symbol is too tall for the tile: %.1f%%" % height)
                self.assertGreaterEqual(height, 52, "symbol shrank into a dot: %.1f%%" % height)
                # Symmetry of the margin is what makes the corners read as equal.
                self.assertLessEqual(abs((left + right) - expected), 3, "mark is off-centre horizontally")
                self.assertLessEqual(abs((top + bottom) - expected), 3, "mark is off-centre vertically")

    def test_tile_corners_are_transparent_so_the_tile_shape_is_the_icon(self):
        for density in DENSITIES:
            with self.subTest(density=density):
                image = Image.open(RES / ("mipmap-" + density) / "ic_launcher.png").convert("RGBA")
                alpha = image.split()[3]
                self.assertEqual(alpha.getpixel((0, 0)), 0, "corner must be outside the rounded tile")
                self.assertEqual(alpha.getpixel((image.width // 2, image.height // 2)), 255,
                                 "the tile itself must be opaque")

    def test_adaptive_foreground_is_ink_only_and_inside_the_safe_circle(self):
        image = Image.open(RES / "mipmap-xxxhdpi" / "ic_launcher_foreground.png").convert("RGBA")
        self.assertEqual(image.size, (432, 432))
        alpha = image.split()[3]
        self.assertEqual(alpha.getpixel((0, 0)), 0, "the background belongs to the launcher, not the foreground")
        # 66/108dp is the guaranteed visible circle: radius 132 of 432.
        box = ink_box(image, lambda p: p[3] > 40) if False else alpha.getbbox()
        radius = 432 * 66 / 108 / 2
        centre = 216
        worst = 0.0
        for y in range(0, 432, 4):
            for x in range(0, 432, 4):
                if alpha.getpixel((x, y)) > 40:
                    worst = max(worst, ((x - centre) ** 2 + (y - centre) ** 2) ** 0.5)
        self.assertLessEqual(worst, radius * 1.02,
                             "mark reaches %.0fpx from centre, safe circle is %.0fpx" % (worst, radius))


if __name__ == "__main__":
    unittest.main()
