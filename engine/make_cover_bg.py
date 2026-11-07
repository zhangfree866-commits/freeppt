#!/usr/bin/env python3
"""Procedural (non-AI) consulting-cover background: navy gradient, faint
network mesh, ascending data curve with cyan glow. No generated-content label."""

import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

W, H = 1536, 1024
NAVY_TOP = (8, 24, 42)
NAVY_BOT = (6, 31, 50)
CYAN = (8, 166, 246)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def build(out_path):
    random.seed(7)
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        c = lerp(NAVY_TOP, NAVY_BOT, y / H)
        for x in range(W):
            px[x, y] = c

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # faint network mesh (left/center), avoiding bottom-right label zone
    nodes = []
    for _ in range(46):
        nx = random.randint(40, int(W * 0.72))
        ny = random.randint(int(H * 0.18), int(H * 0.9))
        nodes.append((nx, ny))
    for i, (x1, y1) in enumerate(nodes):
        near = sorted(nodes, key=lambda p: (p[0] - x1) ** 2 + (p[1] - y1) ** 2)[1:4]
        for (x2, y2) in near:
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < 300:
                a = int(38 * (1 - dist / 300))
                d.line([x1, y1, x2, y2], fill=(120, 170, 210, a), width=1)
    for (x, y) in nodes:
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(130, 180, 220, 60))

    # ascending data curve sweeping to upper-right, cyan glow
    pts = []
    for i in range(60):
        t = i / 59
        x = int(W * 0.16 + t * W * 0.82)
        # keep the curve below the title band (y > ~0.42H on the right)
        y = int(H * 0.88 - math.sin(t * math.pi * 0.5) * H * 0.40
                - t * H * 0.04)
        pts.append((x, y))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line(pts, fill=CYAN + (90,), width=10, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    layer = Image.alpha_composite(layer, glow)

    d2 = ImageDraw.Draw(layer)
    d2.line(pts, fill=(150, 205, 245, 210), width=3, joint="curve")
    for (x, y) in pts[::12]:
        d2.ellipse([x - 5, y - 5, x + 5, y + 5], fill=CYAN + (230,))

    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, quality=95)
    print(out_path)


if __name__ == "__main__":
    build(sys.argv[1])
