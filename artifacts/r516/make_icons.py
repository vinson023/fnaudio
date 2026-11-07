"""R516：图标改回白底 + 蓝色音符，并给方块描一圈浅蓝灰边。

来历：
  * 原始图标是「白色圆角方块 + 蓝色音符」，方块边缘只有一条几乎看不见的灰线。
    放在飞牛应用中心的白色卡片上，方块凭空消失，只剩一个悬空的音符，
    看起来就像「没有图标」。
  * R515 的对策是整块换成蓝底白音符 —— 轮廓是看得见了，但负责人觉得蓝色
    太扎眼，要求改回白底蓝音符。
  * 所以这轮把底色和音符色对调回来，同时沿圆角轮廓内描一圈 #D9E1EE 的边。
    白方块放在白卡片上，靠这条边仍然能看出形状，不会再「消失」。

做法仍是**保形换色**，不重画：
  * alpha 通道照抄原来的圆角方块轮廓，形状一个像素都不动；
  * 用「蓝度」(B - R) 当音符蒙版：白底约 0，音符约 1，抗锯齿边落在中间；
  * 底色填白（带一丝向下的极浅蓝，避免整块死白）、音符填品牌蓝渐变；
  * 放大到 1024 后在 alpha 上做 8px 腐蚀，差集就是边环，填浅蓝灰。

这样 16px 下笔画形状也和原图一致，不会因为重画而变粗或糊掉。

用法：python artifacts/r516/make_icons.py
产出：src/app/ui/images/icon_{16,24,48,64,72,96,128,256,{0}}.png 与 src/ICON.PNG / src/ICON_256.PNG
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
# 源图必须是「白底 + 蓝音符」的原始图。脚本会覆盖 ui/images/icon_256.png，
# 所以每次都从 artifacts 里这份备份读，别指向产出本身：
# 对着白底成品再跑一遍，会被描边和浅蓝渐变带偏，越跑越脏。
SRC_256 = Path(__file__).resolve().parent / "source_icon_256_white.png"
OUT_DIR = ROOT / "src" / "app" / "ui" / "images"
SIZES = (16, 24, 48, 64, 72, 96, 128, 256)

# 底色：纯白 → 极浅蓝，竖向渐变。纯平白在大图标上会显得脏、也没有层次。
BG_TOP = (255, 255, 255)
BG_BOTTOM = (243, 248, 255)

# 音符：品牌蓝，上浅下深，和界面的主色同一色系。
NOTE_TOP = (59, 130, 246)
NOTE_BOTTOM = (25, 72, 208)

# 方块描边：浅蓝灰。白卡片上要能看出轮廓，又不能抢音符的视觉。
STROKE = (0xC7, 0xD4, 0xE8)
# 1024 画布上的描边宽度；缩到 256 是 2px，缩到 64 是 0.5px。
STROKE_PX = 8


def note_mask(image: Image.Image) -> list[list[float]]:
    """按「蓝度」取出音符蒙版：白底约 0，音符约 1，抗锯齿边落在中间。"""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    mask = [[0.0] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            r, _g, b = pixels[x, y]
            strength = (b - r) / 190.0
            # 白底 B-R 约 1~2，除以 190 后接近 0；音符 B-R 在 150 以上。
            if strength <= 0.03:
                continue
            mask[y][x] = min(1.0, strength)
    return mask


def build(source: Image.Image) -> Image.Image:
    source = source.convert("RGBA")
    width, height = source.size
    alpha = source.split()[3]
    mask = note_mask(source)
    out = Image.new("RGBA", (width, height))
    target = out.load()
    for y in range(height):
        t = y / max(1, height - 1)
        base = tuple(round(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        note = tuple(round(NOTE_TOP[i] + (NOTE_BOTTOM[i] - NOTE_TOP[i]) * t) for i in range(3))
        for x in range(width):
            m = mask[y][x]
            target[x, y] = (*[round(base[i] + (note[i] - base[i]) * m) for i in range(3)], 255)
    out.putalpha(alpha)
    return out


def add_stroke(image: Image.Image, radius_px: int, color: tuple[int, int, int]) -> Image.Image:
    """沿 alpha 轮廓内描一圈：腐蚀 radius_px 得到内芯，alpha 减内芯就是边环。"""
    alpha = image.split()[3]
    inner = alpha
    for _ in range(radius_px):
        inner = inner.filter(ImageFilter.MinFilter(3))
    ring = ImageChops.subtract(alpha, inner)
    layer = Image.new("RGBA", image.size, (*color, 0))
    layer.putalpha(ring)
    out = Image.alpha_composite(image, layer)
    # alpha_composite 会把外缘的抗锯齿叠实，圆角会胖一圈；恢复原 alpha 保住轮廓。
    out.putalpha(alpha)
    return out


def main() -> None:
    master = build(Image.open(SRC_256))
    # 64px 直接从 256 缩会略软，先放大到 1024 再用 LANCZOS 逐档缩，
    # 每档都从同一张大图来，避免「64 由 128 缩、128 由 256 缩」的累积模糊。
    # 描边也在这张 1024 上做，否则 256 上的一像素缩到 64 就没了。
    big = add_stroke(master.resize((1024, 1024), Image.LANCZOS), STROKE_PX, STROKE)
    for size in SIZES:
        path = OUT_DIR / f"icon_{size}.png"
        big.resize((size, size), Image.LANCZOS).save(path, "PNG", optimize=True)
        print("wrote", path.relative_to(ROOT), os.path.getsize(path))
    # 飞牛微应用会用字面量文件名 `icon_{0}.png` 请求图标，官方应用也是这么做的一张。
    literal = OUT_DIR / "icon_{0}.png"
    big.resize((256, 256), Image.LANCZOS).save(literal, "PNG", optimize=True)
    print("wrote", literal.relative_to(ROOT), os.path.getsize(literal))
    # FPK 根层的两个图标与 ui 里是同一张图，一起换掉，否则应用中心卡片
    # 用的是 ICON.PNG、桌面用的是 ui/images，会出现两套配色。
    big.resize((256, 256), Image.LANCZOS).save(ROOT / "src" / "ICON_256.PNG", "PNG", optimize=True)
    big.resize((64, 64), Image.LANCZOS).save(ROOT / "src" / "ICON.PNG", "PNG", optimize=True)
    print("wrote src/ICON_256.PNG and src/ICON.PNG")


if __name__ == "__main__":
    main()
