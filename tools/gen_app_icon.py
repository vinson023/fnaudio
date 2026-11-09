"""生成 fnAudio 的应用图标：白底圆角方块 + 蓝色双八分音符。

用法：
  python tools/gen_app_icon.py                # 写到 src/ 与 src/app/ui/images/
  python tools/gen_app_icon.py --preview DIR  # 只出预览，不动源码

为什么要有这个脚本：
  这枚图标以前是临时脚本画的，没留档，于是每轮调整都在重新猜参数（R515 蓝底白音符、
  R516 改回白底蓝音符并加描边），结果笔画比例一直不协调——符头偏小、符干偏粗、
  斜梁与符干的交角是硬拐角，缩到 48px 就是一团蓝。现在把几何写成参数，
  改动可见、可回退。

为什么超采样：
  PIL 的 `ellipse` / `polygon` 没有抗锯齿，256 直接画出来边缘是台阶，
  应用中心再把 256 缩到 60 左右显示，台阶会变成毛边。这里在 8 倍画布上画，
  最后按目标尺寸 LANCZOS 收，边缘才是干净的。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
UI_IMAGES = ROOT / "src" / "app" / "ui" / "images"

# 底色与描边。fnOS 应用中心把图标放在白色卡片上，所以本体必须是白底、
# 靠一圈很淡的蓝灰描边把自己和卡片分开；纯白无描边会糊进背景里（R515 的问题）。
CANVAS = 256
SUPERSAMPLE = 8
CORNER_RADIUS = 58
BACKGROUND_TOP = (255, 255, 255)
BACKGROUND_BOTTOM = (240, 245, 255)
OUTLINE = (214, 224, 240)
SYMBOL_TOP = (56, 116, 240)
SYMBOL_BOTTOM = (28, 76, 205)

# 音符几何，全部以 256 画布为坐标系。
#
# 梁是**水平**的，两个符头同高。这不是偷懒：双八分音符在乐谱里只在两音不同高时
# 才斜梁，同音高就是平梁；而且第一版试过 -7° 的斜梁，垂直符干与斜梁上边缘
# 不可能严丝合缝，符干顶部会各露出一小块三角形台阶——8 倍超采样下反而更显眼。
# 平梁让「梁 + 两根符干」融成一个干净的 U 形，缩到 16px 也不散。
# 头身比照着乐谱来：符头高约 33、宽约 42，符干宽 10（≈符头的 1/4），
# 梁厚 19（≈符干的 2 倍）。第一版梁厚给到 26，与符头几乎等粗，
# 缩到 64px 就成了「方块 + 两个点」。
HEAD_RX = 20.0
HEAD_RY = 14.5
HEAD_TILT = -22.0
HEAD_LEFT = (96.0, 177.0)
HEAD_RIGHT = (158.0, 177.0)
STEM_WIDTH = 11.0
STEM_TOP = 66.0
BEAM_HEIGHT = 16.0
# 符干在符头中心右移 rx 的这个比例上：0.55 时符干右缘正好被符头在
# 「下探到 ry*0.62」的那一点包住，交界处看不到直角缺口。
STEM_OFFSET = 0.55
STEM_OVERLAP = 0.62
# 小尺寸下按比例加粗笔画。16px 时符干只有 0.6 个像素宽，不加粗就是一团模糊
# 的蓝点；这是所有细节图标在 16/24 的通病，只能靠加粗换一点可读性。
STEM_MIN_PX = 1.6
# 符号相对整块图标的占比。按 108/256 画出来只占 42% 宽，放进应用中心的
# 60px 卡片里显得缩手缩脚；1.20 之后约 52% 宽、64% 高，和同类音乐 App 接近。
SYMBOL_SCALE = 1.20
# 24px 及以下再放大一档：整块图标只有 24 像素时，符号按 52% 画出来只有
# 12px 宽，符头会被压成小方块。放到 68% 宽，形状才还认得出是音符。
SYMBOL_SCALE_SMALL = 1.55


def _s(v: float) -> float:
    return v * SUPERSAMPLE


def _background(size: int, target: int) -> Image.Image:
    """白到极淡蓝的纵向渐变，裁成圆角。

    ``target`` 是最终落盘的像素尺寸：描边宽度按它反算，这样文件从 16 到 256
    都恰好有一条约 1.2 物理像素的淡边。按设计尺寸给固定 1px 是不行的——
    256 上的 1px 缩到 60（应用中心卡片里的实际显示尺寸）只剩 0.2px，边就没了。
    """
    gradient = Image.new("RGB", (1, size), BACKGROUND_TOP)
    pixels = gradient.load()
    for y in range(size):
        t = y / max(1, size - 1)
        pixels[0, y] = tuple(
            round(BACKGROUND_TOP[i] + (BACKGROUND_BOTTOM[i] - BACKGROUND_TOP[i]) * t)
            for i in range(3)
        )
    gradient = gradient.resize((size, size), Image.BILINEAR)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=_s(CORNER_RADIUS), fill=255
    )

    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(gradient, (0, 0), mask)

    # 描边画在圆角内侧，且只描一圈很淡的线：压在渐变上面而不是外面，
    # 否则圆角外侧会出现一层比背景更白的毛边。
    stroke = max(1, round(_s(1.2 * CANVAS / target)))
    outline = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(outline).rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=_s(CORNER_RADIUS),
        outline=OUTLINE + (255,),
        width=stroke,
    )
    layer = Image.alpha_composite(layer, Image.composite(outline, Image.new("RGBA", layer.size, (0, 0, 0, 0)), mask))
    return layer


def _scaled(x: float, y: float, scale: float) -> tuple[float, float]:
    """把设计坐标围绕画布中心缩放。"""
    half = CANVAS / 2
    return (half + (x - half) * scale, half + (y - half) * scale)


def _head(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    color: tuple[int, int, int, int],
) -> None:
    """椭圆符头。单独一层画完再转，避免 rotate 把整个画布带偏。"""
    # 旋转后的包围盒留一点余量，否则 -20° 的两端会被裁掉。
    pad = max(rx, ry) * 1.6
    box = (
        int(_s(cx - pad)),
        int(_s(cy - pad)),
        int(_s(cx + pad)),
        int(_s(cy + pad)),
    )
    layer = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    local = ImageDraw.Draw(layer)
    lcx = (box[2] - box[0]) / 2
    lcy = (box[3] - box[1]) / 2
    local.ellipse(
        (lcx - _s(rx), lcy - _s(ry), lcx + _s(rx), lcy + _s(ry)),
        fill=color,
    )
    layer = layer.rotate(HEAD_TILT, resample=Image.BICUBIC, center=(lcx, lcy))
    draw._image.alpha_composite(layer, (box[0], box[1]))


def _weight_for(size: int) -> float:
    """目标尺寸越小，笔画按设计值放大得越多。"""
    if size >= 48:
        return 1.0
    stem_px = STEM_WIDTH * size / CANVAS
    return max(1.0, STEM_MIN_PX / max(stem_px, 1e-6))


def _symbol_mask(size: int, weight: float = 1.0, scale: float = SYMBOL_SCALE) -> Image.Image:
    """音符的形状蒙版，白色不透明；颜色另外用渐变贴上去。"""
    mask = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(mask)
    white = (255, 255, 255, 255)

    rx, ry = HEAD_RX * scale, HEAD_RY * scale
    stem_w = STEM_WIDTH * scale * weight
    beam_h = BEAM_HEIGHT * scale * weight
    stem_top = _scaled(0, STEM_TOP, scale)[1]
    heads = [_scaled(HEAD_LEFT[0], HEAD_LEFT[1], scale), _scaled(HEAD_RIGHT[0], HEAD_RIGHT[1], scale)]

    for cx, cy in heads:
        _head(draw, cx, cy, rx, ry, white)
        # 符干贴着符头右侧、往下伸进符头，接头藏在符头里，不会露出直角。
        stem_x = cx + rx * STEM_OFFSET
        draw.rectangle(
            (_s(stem_x - stem_w / 2), _s(stem_top),
             _s(stem_x + stem_w / 2), _s(cy + ry * STEM_OVERLAP)),
            fill=white,
        )

    draw.rectangle(
        (_s(heads[0][0] + rx * STEM_OFFSET - stem_w / 2), _s(stem_top),
         _s(heads[1][0] + rx * STEM_OFFSET + stem_w / 2), _s(stem_top + beam_h)),
        fill=white,
    )
    return mask


def _symbol_color(size: int, weight: float = 1.0, scale: float = SYMBOL_SCALE) -> Image.Image:
    gradient = Image.new("RGB", (1, size), SYMBOL_TOP)
    pixels = gradient.load()
    for y in range(size):
        t = y / max(1, size - 1)
        pixels[0, y] = tuple(
            round(SYMBOL_TOP[i] + (SYMBOL_BOTTOM[i] - SYMBOL_TOP[i]) * t) for i in range(3)
        )
    gradient = gradient.resize((size, size), Image.BILINEAR)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(gradient, (0, 0), _symbol_mask(size, weight, scale).split()[3])
    return out


def render(size: int) -> Image.Image:
    work = _s(CANVAS)
    weight = _weight_for(size)
    scale = SYMBOL_SCALE if size > 24 else SYMBOL_SCALE_SMALL
    icon = _background(work, size)

    # 极淡的落影：让音符从背景上「浮」起来一点点。alpha 压得很低，
    # 因为应用中心的小尺寸会把任何深色都放大成脏边。
    shadow = Image.new("RGBA", (work, work), (0, 0, 0, 0))
    shadow.paste(
        (24, 52, 132, 46),
        (0, 0),
        _symbol_mask(work, weight, scale).split()[3],
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=_s(2.2)))
    icon = Image.alpha_composite(icon, shadow)

    icon = Image.alpha_composite(icon, _symbol_color(work, weight, scale))
    return icon.resize((size, size), Image.LANCZOS)


def write(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)
    try:
        shown = path.resolve().relative_to(ROOT)
    except ValueError:
        shown = path
    print(f"{shown} {image.size[0]}x{image.size[1]} {path.stat().st_size} B")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", help="只输出预览到这个目录，不改源码")
    args = parser.parse_args()

    sizes = (16, 24, 48, 64, 72, 96, 128, 256)
    if args.preview:
        out = Path(args.preview)
        for size in sizes:
            write(out / f"icon_{size}.png", render(size))
        write(out / "icon_256_sheet.png", render(1024))
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
