from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "src" / "app" / "ui" / "images"
OUT = Path(__file__).resolve().parent / "preview.png"

sheets = [
    ("#FFFFFF (app center card)", (255, 255, 255)),
    ("#F5F6F8 (page bg)", (245, 246, 248)),
    ("#E9EDF4 (gray tile)", (233, 237, 244)),
    ("#1F2430 (dark)", (31, 36, 48)),
]
cell = 200
canvas = Image.new("RGB", (cell * 4, cell + 40), (255, 255, 255))
draw = ImageDraw.Draw(canvas)
for i, (label, color) in enumerate(sheets):
    draw.rectangle([i * cell, 0, i * cell + cell - 1, cell - 1], fill=color)
    # 大图标（128）与小图标（64）并排，模拟卡片与列表里的实际尺寸
    big = Image.open(IMG / "icon_128.png")
    canvas.paste(big, (i * cell + 20, 36), big)
    small = Image.open(IMG / "icon_64.png")
    canvas.paste(small, (i * cell + 118, 68), small)
    tiny = Image.open(IMG / "icon_48.png")
    canvas.paste(tiny, (i * cell + 126, 136), tiny)
    fg = (255, 255, 255) if sum(color) < 380 else (60, 66, 78)
    draw.text((i * cell + 12, 12), label, fill=fg)
canvas.save(OUT)
print("wrote", OUT)
