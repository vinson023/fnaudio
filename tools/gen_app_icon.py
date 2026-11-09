"""生成 fnAudio 的应用图标：白底圆角方块 + 蓝色双八分音符。

用法：
  python tools/gen_app_icon.py                # 写到 src/ 与 src/app/ui/images/
  python tools/gen_app_icon.py --preview DIR  # 只出预览，不动源码

为什么要有这个脚本：
  这枚图标以前是临时脚本画的，没留档，于是每轮调整都在重新猜参数（R515 蓝底白音符、
  R516 改回白底蓝音符、R526 凭印象重画成「平梁 + 小符头」，结果缩略图里读作一个方框）。
  现在几何全部**从基线版本逐个像素量出来**，写在常量里，改动可见、可回退。

原版是什么：
  两个**圆形**符头（不是压扁的椭圆），符干垂直、宽约符头直径的 1/4，紧跟符头右缘；
  横梁是斜的（下倾约 13°），厚度约为符干 1.3 倍；右音符整体比左音符低 12px。
  底色是纯白（#FEFEFE），无描边、无渐变、无投影；蓝色是单一实色（#1071FD）。

为什么要超采样：
  PIL 的 `ellipse` / `polygon` 没有抗锯齿，256 直接画出来边缘是台阶。这里在 8 倍
  画布上画，最后按目标尺寸 LANCZOS 收，16px 档才是干净的。
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
UI_IMAGES = ROOT / "src" / "app" / "ui" / "images"

CANVAS = 256
SUPERSAMPLE = 8
# 圆角半径从原图量出：y=0 处首个不透明像素在 x≈46，圆角是直径 92 的圆弧。
CORNER_RADIUS = 48
# 原图背景是 254,254,254 的纯色，没有渐变——应用中心把它放在白卡片上仍然分得清，
# 因为圆角外侧是透明的，靠的是投影留给卡片的留白。
BACKGROUND = (254, 254, 254)
# 原图符号内部取样恒为 16,113,253，是实色，不是渐变。
SYMBOL = (16, 113, 253)

# ---- 几何（全部以 256 画布为坐标，来自对 0.2.x 基线 ICON_256.PNG 的逐像素测量）----
# 左符头：圆心 (82,178)、半径 29.5 → 覆盖 x 52.5..111.5、y 148.5..207.5
HEAD_LEFT = (82.0, 178.0)
HEAD_LEFT_R = 29.5
# 右符头比左边低 12px、小 1.5px（原图就是不对称的，照抄）
HEAD_RIGHT = (158.0, 190.0)
HEAD_RIGHT_R = 28.0
# 符干宽 16，右缘与符头右缘对齐（乐谱里符干贴在符头右侧）
STEM_WIDTH = 16.0
# 符干画到符头圆心就停：符头是实心圆，圆心以下的符干本来就被盖住；而符干右缘
# 与符头最右点相切，只要往下多伸一点，圆已经变窄，那截就会从符头底下探出个小方脚。
STEM_INSIDE = 0.0
# 横梁：平行四边形，两端是**垂直**切口（不是垂直于梁轴），上边缘实测斜率 0.2155，
# 在 x=114/150/186 处为 48/56/64；竖直厚度 21。
BEAM_TOP_LEFT = (95.5, 44.5)
BEAM_TOP_RIGHT = (186.0, 64.0)
BEAM_BOTTOM_RIGHT = (186.0, 85.0)
BEAM_BOTTOM_LEFT = (95.5, 65.5)
# 原图是描边类字形，上边缘两个外角是圆的（半径约 4.5）；下面两个角与符干相接，
# 是内凹拼接，保持直角——倒圆反而会在梁底开出一个口子。
BEAM_CORNER = 4.5

# 小尺寸下按比例加粗：16px 时符干只有 1px，不加粗就是一条虚边。
STEM_MIN_PX = 1.3
STEM_WEIGHT_MAX = 1.30

# 原图的符号并不居中：包围盒是 x 52.5..186、y 44.5..218，横向偏左 8.75、
# 纵向偏下 3.25。形状比例一律不动，只把包围盒摆到画布正中——应用中心里
# 一排图标并排时，偏左的那个一眼就能看出歪。
GLYPH_LEFT = HEAD_LEFT[0] - HEAD_LEFT_R
GLYPH_RIGHT = BEAM_BOTTOM_RIGHT[0]
GLYPH_TOP = BEAM_TOP_LEFT[1]
GLYPH_BOTTOM = HEAD_RIGHT[1] + HEAD_RIGHT_R
CENTER_DX = (CANVAS - (GLYPH_RIGHT - GLYPH_LEFT)) / 2 - GLYPH_LEFT
CENTER_DY = (CANVAS - (GLYPH_BOTTOM - GLYPH_TOP)) / 2 - GLYPH_TOP

# 图形占画布的比：原版量出来是 52% 宽、68% 高，而 fnOS 自家图标多在 60~77%
# （设置图标那只齿轮约 76%，机器上 16 个应用的中位数约 66%）。
# 1.15 把主体放大到 60% x 78%，与系统那排图标并排时不再显得缩；再多就顶到边了。
# 想让它显得更饱满就调这个值——以画布中心等比缩放，比例不变，只改大小。
# 1.0 表示与 0.2.144 那版逐像素对齐。
GLYPH_SCALE = 1.15


def _s(v: float) -> float:
    return v * SUPERSAMPLE


def _gx(x: float) -> float:
    """设计坐标 -> 超采样像素坐标（横向），含整体居中。"""
    return _s(x + CENTER_DX)


def _gy(y: float) -> float:
    """设计坐标 -> 超采样像素坐标（纵向），含整体居中。"""
    return _s(y + CENTER_DY)


def _background(size: int) -> Image.Image:
    """纯白圆角方块，圆角外全透明。"""
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=_s(CORNER_RADIUS), fill=255
    )
    layer = Image.new("RGBA", (size, size), BACKGROUND + (255,))
    layer.putalpha(mask)
    return layer


def _weight_for(size: int) -> float:
    """目标尺寸越小，符干与横梁按比例加粗得越多。"""
    stem_px = STEM_WIDTH * size / CANVAS
    if stem_px >= STEM_MIN_PX:
        return 1.0
    return min(STEM_WEIGHT_MAX, STEM_MIN_PX / max(stem_px, 1e-6))


def _rounded_polygon(points: list[tuple[float, float]], radii: list[float]) -> list[tuple[float, float]]:
    """把多边形的顶点按半径倒圆，返回可直接交给 ``ImageDraw.polygon`` 的点序列。

    ``radii[i]`` 为 0 表示该顶点保留直角。圆角用圆弧点采样（每 90° 取 10 段），
    在 8 倍画布上已经看不出折线。
    """
    out: list[tuple[float, float]] = []
    count = len(points)
    for i, corner in enumerate(points):
        radius = radii[i]
        if radius <= 0:
            out.append(corner)
            continue
        prev = points[(i - 1) % count]
        nxt = points[(i + 1) % count]
        # 由顶点指向两侧邻点的单位向量
        ux, uy = prev[0] - corner[0], prev[1] - corner[1]
        vx, vy = nxt[0] - corner[0], nxt[1] - corner[1]
        lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
        ux, uy, vx, vy = ux / lu, uy / lu, vx / lv, vy / lv
        # 两条边的夹角 -> 切点到顶点的距离
        cos_phi = max(-1.0, min(1.0, ux * vx + uy * vy))
        phi = math.acos(cos_phi)
        if phi <= 1e-6 or phi >= math.pi - 1e-6:
            out.append(corner)
            continue
        tangent = radius / math.tan(phi / 2)
        # 圆心在角平分线上
        bis_x, bis_y = ux + vx, uy + vy
        bis_len = math.hypot(bis_x, bis_y)
        if bis_len < 1e-9:
            out.append(corner)
            continue
        center_dist = radius / math.sin(phi / 2)
        cx = corner[0] + bis_x / bis_len * center_dist
        cy = corner[1] + bis_y / bis_len * center_dist

        start = (corner[0] + ux * tangent, corner[1] + uy * tangent)
        end = (corner[0] + vx * tangent, corner[1] + vy * tangent)
        out.append(start)
        a0 = math.atan2(start[1] - cy, start[0] - cx)
        a1 = math.atan2(end[1] - cy, end[0] - cx)
        delta = a1 - a0
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta < -math.pi:
            delta += 2 * math.pi
        steps = 10
        for step in range(1, steps):
            angle = a0 + delta * step / steps
            out.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        out.append(end)
    return out


def render(size: int) -> Image.Image:
    work = _s(CANVAS)
    weight = _weight_for(size)
    symbol = Image.new("L", (work, work), 0)
    draw = ImageDraw.Draw(symbol)

    beam = _rounded_polygon(
        [BEAM_TOP_LEFT, BEAM_TOP_RIGHT, BEAM_BOTTOM_RIGHT, BEAM_BOTTOM_LEFT],
        [BEAM_CORNER, BEAM_CORNER, 0.0, 0.0],
    )
    draw.polygon([(_gx(x), _gy(y)) for x, y in beam], fill=255)

    # 符干：从横梁下缘往上退 2px 再往下画，上端那截藏在梁里看不见；
    # 下端停在符头圆心，圆心以下会被符头盖住，露不出来。
    for (cx, cy), radius in ((HEAD_LEFT, HEAD_LEFT_R), (HEAD_RIGHT, HEAD_RIGHT_R)):
        stem_right = cx + radius
        stem_left = stem_right - STEM_WIDTH * weight
        top = BEAM_BOTTOM_LEFT[1] + (stem_left - BEAM_BOTTOM_LEFT[0]) * (
            BEAM_BOTTOM_RIGHT[1] - BEAM_BOTTOM_LEFT[1]
        ) / (BEAM_BOTTOM_RIGHT[0] - BEAM_BOTTOM_LEFT[0])
        draw.rectangle(
            (_gx(stem_left), _gy(top - 2),
             _gx(stem_right), _gy(cy + radius * STEM_INSIDE)),
            fill=255,
        )
        draw.ellipse(
            (_gx(cx - radius), _gy(cy - radius),
             _gx(cx + radius), _gy(cy + radius)),
            fill=255,
        )

    if GLYPH_SCALE != 1.0:
        # 以画布中心等比放大：几何比例一律不动，只是整体变大变小。
        # 在 8 倍画布上重采样，落到目标尺寸仍然干净。
        scaled = round(work * GLYPH_SCALE)
        grown = symbol.resize((scaled, scaled), Image.LANCZOS)
        symbol = Image.new("L", (work, work), 0)
        offset = round((work - scaled) / 2)
        symbol.paste(grown, (offset, offset))

    icon = _background(work)
    colored = Image.new("RGBA", (work, work), SYMBOL + (255,))
    colored.putalpha(symbol)
    return Image.alpha_composite(icon, colored).resize((size, size), Image.LANCZOS)


def write(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)
    try:
        shown = path.resolve().relative_to(ROOT)
    except ValueError:
        shown = path
    print(f"{shown} {image.size[0]}x{image.size[1]} {path.stat().st_size} B")


def main() -> int:
    global GLYPH_SCALE
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", help="只输出预览到这个目录，不改源码")
    parser.add_argument(
        "--scale",
        type=float,
        help="临时覆盖 GLYPH_SCALE（只影响本次运行，用来对比不同主体占比）",
    )
    args = parser.parse_args()
    if args.scale:
        GLYPH_SCALE = args.scale

    sizes = (16, 24, 48, 64, 72, 96, 128, 256)
    if args.preview:
        out = Path(args.preview)
        for size in sizes:
            write(out / f"icon_{size}.png", render(size))
        write(out / "icon_1024.png", render(1024))
        return 0

    for size in sizes:
        write(UI_IMAGES / f"icon_{size}.png", render(size))
    # `icon_{0}.png` 是 fnOS 的图标占位约定，尺寸与 256 档相同。
    write(UI_IMAGES / "icon_{0}.png", render(256))
    # 包根层两枚：64 是列表里的小图，256 是详情页的大图。
    write(ROOT / "src" / "ICON.PNG", render(64))
    write(ROOT / "src" / "ICON_256.PNG", render(256))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
