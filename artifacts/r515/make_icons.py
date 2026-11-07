"""R515：把白底图标改成实心蓝底 + 白色音符。

负责人的原话是「在飞牛 app 的应用中心 fnaudio 没有图标」，追问后确认形态是
「白色方块 + 蓝音符，和白底融在一起」——图标其实一直在加载（
`/app-center-static/serviceicon/fnaudio/ui/images/icon_{0}.png` 每次 200），
只是原图是「白底圆角方块 + 蓝色音符」，放在应用中心的白色卡片上时方块边界
彻底消失，只剩一个悬空的音符，看起来就像没有图标。

做法不是重画，而是**保形换色**：
  * 用 alpha 通道照抄原来的圆角方块轮廓，形状一个像素都不动；
  * 用「蓝度」(B - R) 当音符的蒙版，白底处为 0、音符处为 1，
    抗锯齿边缘自然落在 0 和 1 之间；
  * 背景换成品牌蓝的竖向渐变，音符填白。

这样 64px 下笔画与原图一致，不会因为重画而变粗或糊掉。

用法：python artifacts/r515/make_icons.py
产出：src/app/ui/images/icon_{16,24,48,64,72,96,128,256,{0}}.png 与 src/ICON.PNG / src/ICON_256.PNG
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
# 源图必须是「白底 + 蓝音符」的原始图。脚本会覆盖 ui/images/icon_256.png，
# 所以每次都从 artifacts/r515 里这份备份读，别指向产出本身：
# 对着蓝底图再跑一遍会把蓝底当成白底、把音符当成底色，出来是一张纯蓝方块。
SRC_256 = Path(__file__).resolve().parent / "source_icon_256_white.png"
OUT_DIR = ROOT / "src" / "app" / "ui" / "images"
SIZES = (16, 24, 48, 64, 72, 96, 128, 256)

# 品牌蓝：上浅下深，和原来音符的 #2F6BFF 同一色系。
TOP = (59, 130, 246)
BOTTOM = (29, 78, 216)


def note_mask(image: Image.Image) -> list[list[float]]:
    """按「蓝度」取出音符蒙版：白底约 0，音符约 1，抗锯齿边落在中间。"""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    mask = [[0.0] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            strength = (b - r) / 190.0
            # 纯白底 B-R 约 1~2，除以 190 后接近 0；音符 B-R 在 150 以上。
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
        base = tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3))
        for x in range(width):
            m = mask[y][x]
            color = tuple(round(base[i] + (255 - base[i]) * m) for i in range(3))
            target[x, y] = (*color, 255)
    out.putalpha(alpha)
    return out


def main() -> None:
    master = build(Image.open(SRC_256))
    # 64px 直接从 256 缩会略软，先放大到 1024 再用 LANCZOS 逐档缩，
    # 每档都从同一张大图来，避免「64 由 128 缩、128 由 256 缩」的累积模糊。
    big = master.resize((1024, 1024), Image.LANCZOS)
    for size in SIZES:
        path = OUT_DIR / f"icon_{size}.png"
        big.resize((size, size), Image.LANCZOS).save(path, "PNG", optimize=True)
        print("wrote", path.relative_to(ROOT), os.path.getsize(path))
    # 飞牛微应用会用字面量文件名 `icon_{0}.png` 请求图标，官方应用也是这么做的一张。
    literal = OUT_DIR / "icon_{0}.png"
    big.resize((256, 256), Image.LANCZOS).save(literal, "PNG", optimize=True)
    print("wrote", literal.relative_to(ROOT), os.path.getsize(literal))
    # FPK 根层的两个图标与 ui 里是同一张图，一起换掉，否则应用中心卡片
    # 用的是 ICON.PNG、桌面用的是 ui/images，会出现两套颜色。
    big.resize((256, 256), Image.LANCZOS).save(ROOT / "src" / "ICON_256.PNG", "PNG", optimize=True)
    big.resize((64, 64), Image.LANCZOS).save(ROOT / "src" / "ICON.PNG", "PNG", optimize=True)
    print("wrote src/ICON_256.PNG and src/ICON.PNG")


if __name__ == "__main__":
    main()
