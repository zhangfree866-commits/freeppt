#!/usr/bin/env python3
"""Render laid-out deck to PNG contact sheet for offline visual verification."""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import layout as layout_mod
from engine import themes as _themes  # noqa: E402
from engine.layout import layout_deck, CANVAS_W, CANVAS_H, _img_path  # noqa: E402
from engine.templates import expand_deck  # noqa: E402

FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]
SCALE = 1


def font(size, bold=False):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, max(8, int(size)), index=0)
        except Exception:
            continue
    return ImageFont.load_default()


def rgb(hx):
    hx = hx.lstrip("#")
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def _paste_image(img, node):
    x, y, w, h = node["_rect"]
    try:
        src = Image.open(_img_path(node)).convert("RGB")
        sw, sh = src.size
        target_ar = w / h
        src_ar = sw / sh
        if target_ar > src_ar:  # crop top/bottom
            keep_h = int(sw / target_ar)
            top = (sh - keep_h) // 2
            src = src.crop((0, top, sw, top + keep_h))
        else:
            keep_w = int(sh * target_ar)
            left = (sw - keep_w) // 2
            src = src.crop((left, 0, left + keep_w, sh))
        src = src.resize((int(w), int(h)))
        img.paste(src, (int(x), int(y)))
    except Exception as e:
        ImageDraw.Draw(img).rectangle([x, y, x + w, y + h], outline=(255, 0, 0))


def draw_node(draw, node, default_color, img=None):
    t = node["t"]
    x, y, w, h = node["_rect"]
    if t == "image":
        _paste_image(img, node)
    elif t in ("card", "richcard"):
        if node.get("fill"):
            draw.rectangle([x, y, x + w, y + h], fill=rgb(node["fill"]))
        if node.get("border"):
            draw.rectangle([x, y, x + w, y + h], outline=rgb(node["border"]))
    elif t == "shape":
        fill = rgb(node.get("fill", default_color))
        if node.get("kind") == "oval":
            d = min(w, h)
            draw.ellipse([x, y, x + d, y + d], fill=fill)
        elif node.get("kind") == "roundrect":
            draw.rounded_rectangle([x, y, x + w, y + h], radius=node.get("radius", 12),
                                   fill=fill)
        else:
            draw.rectangle([x, y, x + w, y + h], fill=fill)
    elif t == "box" and node.get("fill"):
        if node.get("kind") == "roundrect":
            draw.rounded_rectangle([x, y, x + w, y + h],
                                   radius=node.get("radius", 12),
                                   fill=rgb(node["fill"]))
        else:
            draw.rectangle([x, y, x + w, y + h], fill=rgb(node["fill"]))
    elif t == "divider":
        col = rgb(node.get("color", _themes.semantic("ink", "#000000")))
        width = max(1, int(node.get("thickness", 1)))
        if node.get("vertical"):
            draw.line([x, y, x, y + h], fill=col, width=width)
        else:
            draw.line([x, y, x + w, y], fill=col, width=width)

    if t == "text":
        lines = node.get("_lines") or [node.get("text", "")]
        size = node.get("size", 20)
        f = font(size, node.get("weight") == "bold")
        col = rgb(node.get("color", default_color))
        ty = y
        va = node.get("valign", "top")
        if va == "middle":
            ty = y + max(0, (h - len(lines) * size * 1.3) / 2)
        elif va == "bottom":
            ty = y + max(0, h - len(lines) * size * 1.3)
        for ln in lines:
            tx = x
            if node.get("align") == "right":
                tx = x + max(0, w - sum(size * (1.02 if ord(c) >= 0x2E80 else 0.56)
                                        for c in ln))
            elif node.get("align") == "center":
                tx = x + max(0, (w - sum(size * (1.02 if ord(c) >= 0x2E80 else 0.56)
                                         for c in ln)) / 2)
            draw.text((tx, ty), ln, fill=col, font=f)
            ty += size * 1.3
    elif t == "kpi":
        vsize = node.get("vsize", node.get("size", 96))
        val = str(node.get("value", ""))

        def _w(s, sz):
            return sum(sz * (1.02 if ord(c) >= 0x2E80 else 0.56) for c in s)

        if _w(val, vsize) > w * 0.92:  # mirror compiler._fit_size
            vsize = max(36, int(vsize * (w * 0.92) / _w(val, vsize)))
        fv = font(vsize, True)
        draw.text((x, y), val,
                  fill=rgb(node.get("color", default_color)), font=fv)
        if node.get("label"):
            fl = font(node.get("lsize", 18), False)
            draw.text((x, y + vsize * 1.3), node["label"],
                      fill=rgb(node.get("lcolor", _themes.semantic("body", "#44546A"))), font=fl)
    elif t == "richcard":
        pad = node.get("padding", 24)
        avail = w - 2 * pad
        ty = y + pad
        for b in node.get("blocks", []):
            bsize = b.get("size", 18)
            txt = b.get("text", "")

            def _bw(s, sz):
                return sum(sz * (1.02 if ord(c) >= 0x2E80 else 0.56) for c in s)

            display = bsize >= 48  # KPI display run: shrink to a single line
            if display and _bw(txt, bsize) > avail:
                bsize = max(36, int(bsize * avail / _bw(txt, bsize)))
            fb = font(bsize, b.get("weight") == "bold")
            # token-aware wrap: keep latin words intact, like the real renderer
            lines = [txt] if display else layout_mod.wrap_lines(
                txt, bsize, max(avail, 1))
            ty += b.get("space_before", 0)
            for ln in lines:
                draw.text((x + pad, ty), ln,
                          fill=rgb(b.get("color", default_color)), font=fb)
                ty += bsize * 1.3
    elif t == "chart":
        draw.rectangle([x, y, x + w, y + h], outline=(150, 150, 150))
        # simple bars from first series for shape check
        cats = node.get("categories", [])
        series = node.get("series", [])
        colors = node.get("colors", _themes.visual("chart_colors", ["#061F32"]))
        if series and node.get("kind") in ("column", "bar"):
            vals = series[-1].get("values", [])
            mx = max(vals) if vals else 1
            bw = w / max(len(vals), 1) * 0.6
            for i, v in enumerate(vals):
                bh = (v / mx) * (h - 40)
                bx = x + 10 + i * (w / max(len(vals), 1))
                draw.rectangle([bx, y + h - 20 - bh, bx + bw, y + h - 20],
                               fill=rgb(colors[i % len(colors)]))

    for k in node.get("children", []):
        draw_node(draw, k, default_color, img)


def render(deck, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, slide in enumerate(deck["slides"]):
        root = slide["_root"]
        img = Image.new("RGB", (CANVAS_W, CANVAS_H), rgb(root.get("fill", "#FFFFFF")))
        if root.get("bg_image"):
            try:
                bg = Image.open(_img_path({"src": root["bg_image"]})).convert("RGB")
                bg = bg.resize((CANVAS_W, CANVAS_H))
                overlay = Image.new("RGB", (CANVAS_W, CANVAS_H), rgb(root.get("fill", "#061F32")))
                a = (root.get("bg_overlay", 60)) / 100.0
                img = Image.blend(bg, overlay, a)
            except Exception:
                pass
        d = ImageDraw.Draw(img)
        sem = _themes.get_active()["semantic"]
        default = sem["ink_on_dark"] if root["dark"] else sem["ink"]
        for c in root.get("children", []):
            draw_node(d, c, default, img)
        for fl in root.get("_float", []):
            draw_node(d, fl, default, img)
        p = os.path.join(out_dir, f"slide{i + 1:02d}.png")
        img.save(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    import json
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    if doc.get("slides") and "template" in doc["slides"][0]:
        if doc.get("assets_base"):
            layout_mod.ASSETS_BASE = doc["assets_base"]
        deck = layout_deck(expand_deck(doc))
    else:
        if doc.get("assets_base"):
            layout_mod.ASSETS_BASE = doc["assets_base"]
        deck = layout_deck(doc)
    for p in render(deck, sys.argv[2]):
        print(p)
