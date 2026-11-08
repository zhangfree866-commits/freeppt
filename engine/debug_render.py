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


def _round(draw, rect, radius, **kw):
    """Rounded rectangle when a radius is set, else a plain rectangle."""
    if radius:
        draw.rounded_rectangle(rect, radius=radius, **kw)
    else:
        draw.rectangle(rect, **kw)


def _blend(fg, bg, opacity):
    """Approximate alpha compositing on an RGB canvas (opacity 0..100)."""
    if opacity is None:
        return fg
    a = max(0.0, min(100.0, float(opacity))) / 100.0
    return tuple(int(round(b * (1 - a) + f * a)) for f, b in zip(fg, bg))


def _grad_stops(grad):
    stops = grad.get("stops") or []
    out = []
    n = max(1, len(stops) - 1)
    for i, st in enumerate(stops):
        pos = st.get("pos")
        if pos is None:
            pos = int(100000 * i / n)
        out.append((pos / 100000.0, rgb(st["color"]),
                    st.get("opacity", 100)))
    return out


def _sample_grad(stops, t):
    """Color at parameter t in 0..1 along the gradient axis."""
    if not stops:
        return (200, 200, 200)
    if t <= stops[0][0]:
        return stops[0][1]
    for (p0, c0, _), (p1, c1, _) in zip(stops, stops[1:]):
        if t <= p1:
            f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(int(round(c0[k] + (c1[k] - c0[k]) * f)) for k in range(3))
    return stops[-1][1]


def gradient_box(grad, w, h):
    """Build an RGB gradient tile; angle follows the OOXML convention (deg)."""
    w, h = max(1, int(w)), max(1, int(h))
    stops = _grad_stops(grad)
    tile = Image.new("RGB", (w, h))
    px = tile.load()
    angle = float(grad.get("angle", 90))
    # 0 deg = left->right, 90 deg = top->bottom; default to a vertical axis.
    horizontal = (angle % 180) < 45 or (angle % 180) >= 135
    span = w if horizontal else h
    for yy in range(h):
        for xx in range(w):
            t = (xx if horizontal else yy) / max(1, span - 1)
            px[xx, yy] = _sample_grad(stops, t)
    return tile


def _node_fill(node, base_rgb):
    """Representative fill RGB for a shape on an RGB contact sheet."""
    grad = node.get("gradient")
    if grad:
        stops = _grad_stops(grad)
        col = _sample_grad(stops, 0.5)
        op = (stops[0][2] if stops else 100)
        return _blend(col, base_rgb, op)
    if node.get("fill"):
        return _blend(rgb(node["fill"]), base_rgb, node.get("opacity"))
    return None


# Contact-sheet approximation of compiler.SHADOW_PRESETS. The real renderer
# emits a blurred outerShdw; here a single offset, alpha-blended dark rectangle
# is enough to signal elevation on the RGB preview.
SHADOW_DEBUG = {
    "soft": {"dist": 3, "alpha": 18},
    "medium": {"dist": 5, "alpha": 26},
}


def _shadow_level(node):
    """Mirror compiler._shadow_level: node field wins, else theme token."""
    raw = node.get("shadow")
    if raw is None:
        raw = _themes.get_active()["visual"].get("shadow", "none")
    if raw is True:
        return "soft"
    if raw is False or raw in (None, "none"):
        return "none"
    return str(raw)


def _draw_shadow(draw, node, bg_rgb):
    """Paint a flat drop shadow under the shape before its own fill lands."""
    preset = SHADOW_DEBUG.get(_shadow_level(node))
    if not preset:
        return
    x, y, w, h = node["_rect"]
    d = preset["dist"]
    col = _blend(rgb(node.get("shadow_color", "#1F2937")), bg_rgb,
                 preset["alpha"])
    _round(draw, [x, y + d, x + w, y + h + d], node.get("radius"), fill=col)


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


def _draw_icon(draw, node, x, y, w, h):
    """Lightweight glyph mirror of compiler.add_icon for the contact sheet."""
    from engine import icons as _icons
    specs = _icons.specs(node.get("name", ""))
    if not specs:
        return
    color = rgb(node.get("color", _themes.semantic("accent", "#08A6F6")))
    knock = rgb(node.get("knock_color", "#FFFFFF"))
    sx, sy = w / _icons.GRID, h / _icons.GRID
    for sp in specs:
        if sp.get("k") == "line":
            draw.line([x + sp["x1"] * sx, y + sp["y1"] * sy,
                       x + sp["x2"] * sx, y + sp["y2"] * sy], fill=color, width=2)
            continue
        bx, by = x + sp["x"] * sx, y + sp["y"] * sy
        bw, bh = max(1.0, sp["w"] * sx), max(1.0, sp["h"] * sy)
        rect = [bx, by, bx + bw, by + bh]
        fillc = knock if sp.get("knock") else (
            None if sp.get("mode") == "stroke" else color)
        k = sp.get("k")
        outline_c = color if not fillc else None
        if k == "oval" or k == "gear6":
            # gear6 has no cheap PIL analogue; approximate with its ring/hub
            draw.ellipse(rect, fill=fillc, outline=outline_c, width=2)
        elif k == "diamond":
            cx, cy = bx + bw / 2, by + bh / 2
            draw.polygon([(cx, by), (bx + bw, cy), (cx, by + bh), (bx, cy)],
                         fill=fillc, outline=outline_c)
        elif k == "triangle":
            draw.polygon([(bx + bw / 2, by), (bx + bw, by + bh), (bx, by + bh)],
                         fill=fillc, outline=outline_c)
        elif k == "shield":
            draw.polygon([(bx + bw / 2, by), (bx + bw, by + bh * 0.28),
                          (bx + bw, by + bh * 0.6), (bx + bw / 2, by + bh),
                          (bx, by + bh * 0.6), (bx, by + bh * 0.28)],
                         fill=fillc, outline=outline_c)
        elif k == "roundrect":
            draw.rounded_rectangle(rect, radius=min(bw, bh) * 0.18,
                                   fill=fillc, outline=outline_c, width=2)
        else:  # rect / chevron: rectangle placeholder
            draw.rectangle(rect, fill=fillc, outline=outline_c, width=2)


def draw_node(draw, node, default_color, img=None, bg_rgb=(255, 255, 255)):
    t = node["t"]
    x, y, w, h = node["_rect"]
    if t == "image":
        _paste_image(img, node)
    elif t in ("card", "richcard"):
        _draw_shadow(draw, node, bg_rgb)
        if node.get("gradient") and img is not None:
            img.paste(gradient_box(node["gradient"], w, h), (int(x), int(y)))
        else:
            fillc = _node_fill(node, bg_rgb)
            if fillc is not None:
                _round(draw, [x, y, x + w, y + h], node.get("radius"), fill=fillc)
        if node.get("border"):
            _round(draw, [x, y, x + w, y + h], node.get("radius"),
                   outline=_blend(rgb(node["border"]), bg_rgb,
                                  node.get("border_opacity", 100)), width=2)
    elif t == "icon":
        _draw_icon(draw, node, x, y, w, h)
    elif t == "shape":
        _draw_shadow(draw, node, bg_rgb)
        if node.get("gradient") and img is not None:
            img.paste(gradient_box(node["gradient"], w, h), (int(x), int(y)))
            fill = None
        else:
            raw = node.get("fill", default_color)
            fill = _blend(rgb(raw), bg_rgb, node.get("opacity")) if raw else None
        if node.get("kind") == "oval":
            d = min(w, h)
            draw.ellipse([x, y, x + d, y + d], fill=fill)
        elif node.get("kind") == "roundrect":
            draw.rounded_rectangle([x, y, x + w, y + h], radius=node.get("radius", 12),
                                   fill=fill)
        elif fill is not None:
            draw.rectangle([x, y, x + w, y + h], fill=fill)
    elif t == "box" and (node.get("fill") or node.get("gradient")
                         or node.get("border")):
        _draw_shadow(draw, node, bg_rgb)
        fillc = None
        if node.get("gradient") and img is not None:
            img.paste(gradient_box(node["gradient"], w, h), (int(x), int(y)))
        else:
            fillc = _node_fill(node, bg_rgb)
        border_c = _blend(rgb(node["border"]), bg_rgb,
                          node.get("border_opacity", 100)) if node.get("border") else None
        rounded = node.get("kind") == "roundrect" or node.get("radius")
        if rounded:
            draw.rounded_rectangle([x, y, x + w, y + h],
                                   radius=node.get("radius", 12),
                                   fill=fillc, outline=border_c, width=2)
        else:
            draw.rectangle([x, y, x + w, y + h], fill=fillc, outline=border_c)
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
        col = _blend(rgb(node.get("color", default_color)), bg_rgb,
                     node.get("opacity", 100))
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
            bcol = _blend(rgb(b.get("color", default_color)), bg_rgb,
                          b.get("opacity", 100))
            for ln in lines:
                draw.text((x + pad, ty), ln, fill=bcol, font=fb)
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
    elif t == "table":
        headers, rows = node.get("headers", []), node.get("rows", [])
        ncols = max(len(headers), 1)
        nrows = len(rows) + 1
        rh = h / max(nrows, 1)
        cw = w / ncols
        hfill = rgb(node.get("header_fill", "#061F32"))
        draw.rectangle([x, y, x + w, y + rh], fill=hfill)
        if node.get("zebra"):
            zc = rgb(node["zebra"])
            for i in range(1, nrows):
                if i % 2 == 0:
                    draw.rectangle([x, y + i * rh, x + w, y + (i + 1) * rh], fill=zc)
        for i in range(nrows + 1):
            gy = y + i * rh
            draw.line([x, gy, x + w, gy], fill=(150, 150, 150))
        for j in range(ncols + 1):
            gx = x + j * cw
            draw.line([gx, y, gx, y + h], fill=(150, 150, 150))
        f_hd, f_bd = font(14, True), font(13, False)
        for j, head in enumerate(headers):
            draw.text((x + j * cw + 6, y + 4), str(head),
                      fill=rgb(node.get("header_color", "#FFFFFF")), font=f_hd)
        for i, row in enumerate(rows, start=1):
            for j in range(ncols):
                val = row[j] if j < len(row) else ""
                draw.text((x + j * cw + 6, y + i * rh + 4), str(val),
                          fill=rgb(node.get("body_color", "#061F32")), font=f_bd)

    for k in node.get("children", []):
        draw_node(draw, k, default_color, img, bg_rgb=bg_rgb)


def render(deck, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, slide in enumerate(deck["slides"]):
        root = slide["_root"]
        base_rgb = rgb(root.get("fill", "#FFFFFF"))
        img = Image.new("RGB", (CANVAS_W, CANVAS_H), base_rgb)
        if root.get("gradient") and not root.get("bg_image"):
            img.paste(gradient_box(root["gradient"], CANVAS_W, CANVAS_H), (0, 0))
            base_rgb = _sample_grad(_grad_stops(root["gradient"]), 0.5)
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
            draw_node(d, c, default, img, bg_rgb=base_rgb)
        for fl in root.get("_float", []):
            draw_node(d, fl, default, img, bg_rgb=base_rgb)
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
