#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the «مفلتر السيرفرات» icon set (PNG) used by the desktop entry.

Run:  python3 desktop/make-icons.py
Needs Pillow (already used by the bundle build).  No SVG tooling required.
"""
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icons")
SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
S = 1024


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


def build():
    top, bottom = (16, 30, 52), (5, 9, 16)
    bg = Image.new("RGB", (S, S))
    d = ImageDraw.Draw(bg)
    for y in range(S):
        d.line([(0, y), (S, y)], fill=lerp(top, bottom, y / (S - 1)))

    # soft teal glow behind the funnel
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((170, 120, 854, 804), fill=(46, 196, 182, 46))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    bg = Image.alpha_composite(bg.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(bg)

    # inner hairline border
    d.rounded_rectangle((18, 18, S - 19, S - 19), radius=205, outline=(35, 66, 102), width=6)

    # funnel (the "filter")
    funnel = [(248, 286), (776, 286), (566, 566), (566, 700), (458, 772), (458, 566)]
    d.polygon(funnel, fill=(242, 247, 255))
    # funnel rim highlight
    d.line([(248, 286), (776, 286)], fill=(255, 255, 255), width=10)

    # three "servers" entering the funnel
    for cx, col in ((372, (61, 220, 151)), (512, (46, 196, 182)), (652, (91, 140, 255))):
        r = 34
        d.ellipse((cx - r, 356 - r, cx + r, 356 + r), fill=col)
        d.ellipse((cx - r + 8, 356 - r + 8, cx + r - 8, 356 + r - 8),
                  fill=tuple(min(255, c + 45) for c in col))

    # filtered output: three clean bars under the spout
    for y, w, col in ((826, 168, (61, 220, 151)), (884, 118, (46, 196, 182)), (942, 74, (91, 140, 255))):
        d.rounded_rectangle((512 - w // 2, y, 512 + w // 2, y + 26), radius=13, fill=col)

    icon = bg.convert("RGBA")
    icon.putalpha(rounded_mask(S, 205))

    os.makedirs(OUT, exist_ok=True)
    for size in SIZES:
        img = icon.resize((size, size), Image.LANCZOS)
        img.save(os.path.join(OUT, "mofilter-%d.png" % size), optimize=True)
    icon.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "mofilter.png"), optimize=True)
    print("icons ->", OUT)


if __name__ == "__main__":
    build()
