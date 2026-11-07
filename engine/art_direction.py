#!/usr/bin/env python3
"""FreePPT art direction: compose a deck page-by-page instead of filling a master.

The old pipeline was: pick one of 10 masters -> inject text -> every content
page ends up with the same title rule, same three equal cards, same footer.
This module replaces that step for creative decks:

    content semantics + reference cover -> per-page composition archetype
    -> absolute rects -> standard DSL -> the SAME layout/lint/build pipeline

Guarantees (all deterministic, no LLM, no network):
  * adjacent pages never reuse an archetype (lint LAYOUT_REPETITION blocks it)
  * a whole deck needs >= half its pages to be visually distinct
  * geometry is derived from the actual text length (auto-fit), not fixed boxes
  * a book cover yields a derived palette/motif that recurs at different
    scales and positions, so the deck feels branded without being repetitive
  * same notes + same cover => byte-identical DSL

Usage:
  python3 engine/art_direction.py compose notes.json --out deck.json \
      --cover cover.jpg --ledger style.json
"""

import argparse
import hashlib
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import layout as L  # noqa: E402
from engine import themes as T  # noqa: E402
from engine import cover_style as CS  # noqa: E402

W, H = 1280, 720

# ---------------------------------------------------------------------------
# DSL node helpers — every helper computes its own height from the text
# ---------------------------------------------------------------------------

def _t(x, y, w, text, size, color, max_h=None, min_size=16, **kw):
    """Text node whose rect height is measured from its own wrapped lines."""
    text = str(text)
    n = {"t": "text", "text": text, "size": size, "color": str(color).upper()}
    h = L.leaf_text_h(n, max(w, 1))
    if max_h:
        while h > max_h and size > min_size:
            size -= 2
            n["size"] = size
            h = L.leaf_text_h(n, max(w, 1))
    n["rect"] = [round(x, 1), round(y, 1), round(w, 1), math.ceil(h) + 6]
    for k, v in kw.items():
        if v is not None:
            n[k] = v
    return n


def _b(x, y, w, h, fill=None, **kw):
    n = {"t": "box", "rect": [round(x, 1), round(y, 1), round(w, 1), round(h, 1)],
         "children": []}
    if fill:
        n["fill"] = str(fill).upper()
    n.update({k: v for k, v in kw.items() if v is not None})
    return n


def _d(x, y, w, color, vertical=False, h=0, thickness=1.5, **kw):
    n = {"t": "divider", "color": str(color).upper(),
         "rect": [round(x, 1), round(y, 1), round(w, 1), round(h if vertical else 1.5, 1)]}
    if vertical:
        n["vertical"] = True
    if thickness != 1.5:
        n["thickness"] = thickness
    n.update(kw)
    return n


def _o(x, y, d, fill, **kw):
    n = {"t": "shape", "kind": "oval", "fill": str(fill).upper(),
         "rect": [round(x, 1), round(y, 1), round(d, 1), round(d, 1)]}
    n.update(kw)
    return n


def _rc(x, y, w, h, blocks, fill=None, border=None, pad=24, **kw):
    n = {"t": "richcard", "blocks": blocks, "padding": pad}
    if fill:
        n["fill"] = str(fill).upper()
    if border:
        n["border"] = str(border).upper()
    measured = L.hug_h(n, w) + 2
    n["rect"] = [round(x, 1), round(y, 1), round(w, 1), round(max(h, measured), 1)]
    n.update({k: v for k, v in kw.items() if v is not None})
    return n


def _blk(text, size, color, weight=None, space=0, align=None):
    b = {"text": str(text), "size": size, "color": str(color).upper()}
    if weight:
        b["weight"] = weight
    if space:
        b["space_before"] = space
    if align:
        b["align"] = align
    return b


# ---------------------------------------------------------------------------
# content accessors
# ---------------------------------------------------------------------------

def _points(page):
    out = []
    # comparison pages store content in left/right rather than a point list
    for side in ("left", "right"):
        v = page.get(side)
        if isinstance(v, dict):
            out.append({"head": v.get("head") or v.get("title") or "",
                        "body": v.get("body") or v.get("text") or ""})
        elif isinstance(v, str) and v.strip():
            out.append({"head": "", "body": v})
    for it in (page.get("points") or page.get("items") or []):
        if isinstance(it, str):
            out.append({"head": "", "body": it})
        elif isinstance(it, dict):
            out.append({"head": it.get("head") or it.get("title") or "",
                        "body": it.get("body") or it.get("text") or ""})
    if not out:
        out = [{"head": page.get("kind", ""),
                "body": page.get("lead") or page.get("title") or ""}]
    return out


def _quote(page):
    return page.get("quote") or page.get("lead") or page.get("title") or ""


def _head(page, fallback=""):
    return page.get("title") or fallback


def _chrome(S, ctx, x, y, on=None, align="left", w=360):
    # keep the signature inside the canvas no matter where a composition
    # decides to place it
    w = max(80, min(w, W - x - 24))
    y = min(y, H - 56)
    book = ctx["book"]
    idx, total = ctx["idx"] + 1, ctx["total"]
    parts = [
        _t(x, y, w, f"{idx:02d} / {total:02d}", 14, S["muted"], align=align,
           decor=True, on=on),
    ]
    if book.get("title"):
        parts.append(_t(x, y + 22, w, "读书笔记 · " + book["title"], 14,
                        S["muted"], align=align, decor=True, on=on))
    return parts


def _source(S, page, x, y, w=560, on=None, align="left"):
    w = max(80, min(w, W - x - 24))
    src = page.get("source") or ""
    return [_t(x, y, w, src, 14, S["muted"], align=align, decor=True, on=on)] if src else []


def _motif(S, x, y, scale=1.0, variant=0):
    """Recurring visual signature, expressed differently on each page."""
    k = S["motif"]
    s = scale
    if k == "band":
        return [_b(x, y, 190 * s, 10 * s, S["accent"])]
    if k == "vertical-rule":
        return [_d(x, y, 3, S["accent"], vertical=True, h=150 * s, thickness=3)]
    if k == "arc":
        return [_o(x, y, 130 * s, S["soft"]),
                _o(x + 40 * s, y + 40 * s, 50 * s, S["accent"], opacity=45)]
    if k == "dots":
        return [_o(x + i * 34 * s, y + (i % 2) * 14 * s, 12 * s, S["accent"])
                for i in range(3)]
    # grid
    return [_d(x, y + i * 34 * s, 150 * s, S["line"], thickness=1)
            for i in range(3)] + [
           _d(x + i * 50 * s, y, 1, S["line"], vertical=True, h=80 * s)
           for i in range(4)]


# ---------------------------------------------------------------------------
# composition archetypes — each returns (children, surface, tone, density)
# ---------------------------------------------------------------------------

def a_cover_editorial(p, S, c):
    kids = []
    if c.get("cover_file"):
        kids.append({"t": "image", "src": c["cover_file"], "fit": "cover",
                     "rect": [0, 0, 548, H], "credit": c.get("cover_credit")})
    else:
        kids.append(_b(0, 0, 548, H, S["deep"]))
        kids += _motif(S, 90, 180, 2.4, 0)
    kids.append(_d(596, 88, 2, S["accent"], vertical=True, h=540, thickness=4))
    title = c["book"].get("title", "")
    kids.append(_t(640, 168, 570, title, 64, S["ink"],
                   max_h=210, min_size=38, weight="bold", on=S["paper"]))
    sub = c["book"].get("subtitle", "")
    if sub:
        kids.append(_t(642, 390, 560, sub, 26, S["accent"], on=S["paper"]))
    au = c["book"].get("author", "")
    if au:
        kids.append(_t(642, 452, 560, au + " 著", 20, S["body"], on=S["paper"]))
    kids += _motif(S, 642, 120, 1.1, 1)
    kids.append(_d(642, 600, 500, S["line"], thickness=1))
    kids += _chrome(S, c, 642, 616, on=S["paper"])
    return kids, S["paper"], "light", "airy"


def a_chapter_opener(p, S, c):
    no = str(p.get("no") or f"{c['idx']:02d}")
    kids = [_b(0, 0, W, H, S["deep"]),
            _t(70, 70, 600, no, 230, S["decor"], decor=True,
               on=S["deep"], weight="bold")]
    kids += _motif(S, 900, 120, 2.6, 2)
    kids.append(_d(70, 430, 520, S["accent"], thickness=4))
    kids.append(_t(70, 462, 900, _head(p, "章节"), 52, S["ondark"],
                   max_h=140, min_size=34, weight="bold", on=S["deep"]))
    if p.get("en"):
        kids.append(_t(72, 588, 800, p["en"], 18, S["soft"], on=S["deep"]))
    kids += _chrome(S, c, 1060, 640, on=S["deep"], align="right", w=160)
    return kids, S["deep"], "dark", "airy"


def a_editorial_spread(p, S, c):
    r = c["rng"]
    left_w = 500 + r.randint(-20, 30)
    kids = [_t(64, 96, left_w, _head(p), 50, S["ink"], max_h=250,
               min_size=32, weight="bold", on=S["paper"])]
    kids += _motif(S, 64, 366, 1.4, 0)
    kids.append(_d(64 + left_w + 40, 90, 2, S["line"], vertical=True,
                   h=540, thickness=2))
    rx = 64 + left_w + 78
    rw = W - rx - 72
    y = 110 + r.randint(-10, 20)
    lead = p.get("lead") or ""
    if lead:
        n = _t(rx, y, rw, lead, 23, S["body"], max_h=170, on=S["paper"])
        kids.append(n)
        y = n["rect"][1] + n["rect"][3] + 34
    for pt in _points(p)[:3]:
        if pt["head"]:
            n = _t(rx, y, rw, pt["head"], 24, S["accent"],
                   weight="bold", on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 10
        if pt["body"]:
            n = _t(rx, y, rw - 20, pt["body"], 18, S["body"],
                   max_h=110, on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 22
    if p.get("note"):
        kids.append(_b(rx, 590, rw, 58, S["soft"]))
        kids.append(_t(rx + 16, 602, rw - 32, p["note"], 16, S["ink"],
                       max_h=44, on=S["soft"]))
    kids += _source(S, p, 64, 648, 700, on=S["paper"])
    kids += _chrome(S, c, 1060, 648, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "mid"


def a_offset_triptych(p, S, c):
    r = c["rng"]
    pts = _points(p)[:3]
    n = len(pts)
    layouts = {
        1: ([64], [700], [178], [S["soft"]]),
        2: ([64, 700], [572, 516], [168, 248], [S["soft"], S["accent"]]),
        3: ([64, 466, 856], [344, 342, 356],
            [140 + r.randint(0, 40), 214 + r.randint(0, 40), 112 + r.randint(0, 40)],
            [S["soft"], None, S["accent"]]),
    }
    xs, ws, ys, fills = layouts[n]
    kids = [_t(64, 62, 900, _head(p), 36, S["ink"], max_h=70,
               min_size=26, weight="bold", on=S["paper"])]
    kids += _motif(S, 1050, 68, 0.9, 3)
    for i, (pt, x, w_, y) in enumerate(zip(pts, xs, ws, ys)):
        kids.append(_t(x, y - 46, 100, f"{i + 1:02d}", 30, S["accent"],
                       decor=True, weight="bold", on=S["paper"]))
        dark_card = fills[i] == S["accent"]
        blocks = []
        if pt["head"]:
            blocks.append(_blk(pt["head"], 30 if dark_card else 23,
                               S["paper"] if dark_card else S["ink"],
                               "bold"))
        if pt["body"]:
            blocks.append(_blk(pt["body"], 18,
                               S["paper"] if dark_card else S["body"], space=12))
        kids.append(_rc(x, y, w_, 380 if n == 3 else 420, blocks,
                        fill=fills[i], border=None if dark_card else S["line"],
                        pad=22, on=S["accent"] if dark_card else None))
    if p.get("note"):
        kids.append(_t(64, 626, 1100, p["note"], 16, S["body"],
                       max_h=40, on=S["paper"]))
    kids += _chrome(S, c, 1060, 676, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "dense"


def a_quote_bleed(p, S, c):
    r = c["rng"]
    dark = r.random() < 0.45
    surface = S["deep"] if dark else S["paper"]
    fg = S["ondark"] if dark else S["ink"]
    sub = S["soft"] if dark else S["body"]
    kids = [_b(0, 0, W, H, surface)]
    kids += _motif(S, 940, 80, 2.2 if not dark else 1.6, 2)
    kids.append(_t(64, 66, 200, "“", 130, S["accent"], decor=True, on=surface))
    q = _quote(p)
    n = _t(150, 220, 940, q, 44, fg, max_h=290, min_size=28,
           weight="bold", on=surface)
    kids.append(n)
    kids.append(_d(150, n["rect"][1] + n["rect"][3] + 34, 260, S["accent"],
                   thickness=4))
    att = p.get("attribution") or c["book"].get("author", "")
    if att:
        kids.append(_t(150, n["rect"][1] + n["rect"][3] + 56, 800,
                       "— " + att, 19, sub, on=surface))
    kids += _chrome(S, c, 64, 650, on=surface)
    return kids, surface, "dark" if dark else "light", "airy"


def a_split_contrast(p, S, c):
    left = p.get("left") or {}
    right = p.get("right") or {}
    pts = _points(p)
    if not left and pts:
        left = {"head": pts[0]["head"], "body": pts[0]["body"]}
    if not right and len(pts) > 1:
        right = {"head": pts[1]["head"], "body": pts[1]["body"]}
    split = 620
    kids = [_b(0, 0, split, H, S["deep"]), _b(split, 0, W - split, H, S["paper"]),
            _b(split - 6, 0, 12, H, S["accent"])]
    kids.append(_t(64, 92, 480, _head(p), 32, S["ondark"], max_h=90,
                   min_size=24, weight="bold", on=S["deep"]))
    y = 240
    for key, val in (("head", left.get("head", "")), ("body", left.get("body", ""))):
        if val:
            n = _t(64, y, 480, val, 30 if key == "head" else 19,
                   S["ondark"] if key == "head" else S["soft"],
                   max_h=190, on=S["deep"], weight="bold" if key == "head" else None)
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 24
    y = 200
    for key, val in (("head", right.get("head", "")), ("body", right.get("body", ""))):
        if val:
            n = _t(split + 56, y, W - split - 120, val,
                   30 if key == "head" else 19,
                   S["accent"] if key == "head" else S["body"],
                   max_h=210, on=S["paper"], weight="bold" if key == "head" else None)
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 24
    kids += _motif(S, split + 56, 560, 1.0, 4)
    kids += _chrome(S, c, split + 56, 650, on=S["paper"])
    return kids, S["paper"], "light", "mid"


def a_margin_notes(p, S, c):
    kids = [_b(940, 64, 276, 580, S["soft"])]
    kids += _motif(S, 966, 92, 0.8, 1)
    kids.append(_t(64, 90, 820, _head(p), 42, S["ink"], max_h=130,
                   min_size=28, weight="bold", on=S["paper"]))
    kids.append(_d(64, 242, 820, S["line"], thickness=1))
    y = 282
    lead = p.get("lead") or ""
    if lead:
        n = _t(64, y, 820, lead, 21, S["body"], max_h=110, on=S["paper"])
        kids.append(n)
        y = n["rect"][1] + n["rect"][3] + 26
    for pt in _points(p)[:4]:
        if pt["head"]:
            n = _t(64, y, 820, pt["head"], 23, S["accent"],
                   weight="bold", on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 8
        if pt["body"]:
            n = _t(64, y, 800, pt["body"], 19, S["body"],
                   max_h=100, on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 30
    note = p.get("note") or p.get("context") or ""
    if note:
        kids.append(_t(966, 210, 220, "批注", 18, S["ink"],
                       weight="bold", on=S["soft"]))
        kids.append(_t(966, 246, 220, note, 17, S["ink"],
                       max_h=330, on=S["soft"]))
    kids += _source(S, p, 64, 650, 800, on=S["paper"])
    kids += _chrome(S, c, 966, 596, on=S["soft"])
    return kids, S["paper"], "light", "mid"


def a_stair_list(p, S, c):
    r = c["rng"]
    kids = [_t(64, 60, 1080, _head(p), 34, S["ink"], max_h=80,
               min_size=24, weight="bold", on=S["paper"])]
    kids += _motif(S, 1080, 66, 0.9, 0)
    pts = _points(p)[:5]
    y = 158
    for i, pt in enumerate(pts):
        x = 90 + i * 34
        w_ = 1040 - i * 34
        kids.append(_d(x, y, w_, S["line"], thickness=1))
        kids.append(_t(x, y + 12, 60, f"{i + 1:02d}", 24, S["accent"],
                       decor=True, weight="bold", on=S["paper"]))
        if pt["head"]:
            kids.append(_t(x + 66, y + 12, w_ - 80, pt["head"], 22,
                           S["ink"], weight="bold", on=S["paper"]))
        if pt["body"]:
            kids.append(_t(x + 66, y + 46, w_ - 90, pt["body"], 17,
                           S["body"], max_h=52, on=S["paper"]))
        y += 96 + r.randint(0, 12)
    kids += _chrome(S, c, 1060, 668, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "dense"


def a_data_focus(p, S, c):
    value = str(p.get("value") or p.get("kpi") or "01")
    label = p.get("label") or p.get("lead") or ""
    kids = [_t(64, 74, 1000, _head(p), 32, S["ink"], max_h=80,
               min_size=24, weight="bold", on=S["paper"])]
    kids.append(_b(64, 200, 640, 360, S["soft"]))
    kids += _motif(S, 92, 226, 1.2, 2)
    kids.append(_t(92, 286, 580, value, 150, S["accent"], max_h=190,
                   min_size=60, weight="bold", on=S["soft"], decor=True))
    if label:
        kids.append(_t(92, 480, 560, label, 21, S["ink"],
                       max_h=62, on=S["soft"]))
    y = 210
    for pt in _points(p)[:3]:
        if pt["head"]:
            n = _t(760, y, 440, pt["head"], 22, S["ink"],
                   weight="bold", on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 6
        if pt["body"]:
            n = _t(760, y, 440, pt["body"], 17, S["body"],
                   max_h=90, on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 26
    kids += _source(S, p, 64, 650, 900, on=S["paper"])
    kids += _chrome(S, c, 1060, 650, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "airy"


def a_grid_mosaic(p, S, c):
    pts = _points(p)[:4]
    n = len(pts)
    grid4 = [(64, 132, 560, 380, S["accent"], True),
             (646, 132, 570, 224, S["soft"], False),
             (646, 376, 278, 250, S["card"], False),
             (944, 376, 272, 250, S["paper"], False)]
    grid3 = [(64, 132, 560, 494, S["accent"], True),
             (646, 132, 570, 240, S["soft"], False),
             (646, 392, 570, 234, S["card"], False)]
    grid2 = [(64, 132, 700, 494, S["accent"], True),
             (786, 132, 430, 494, S["soft"], False)]
    cells = grid4 if n >= 4 else (grid3 if n == 3 else grid2)
    kids = [_t(64, 62, 1100, _head(p), 36, S["ink"], max_h=76,
               min_size=26, weight="bold", on=S["paper"])]
    kids += _motif(S, 1100, 68, 0.7, 3)
    for i, ((x, y, w_, h_, fill, dark), pt) in enumerate(zip(cells, pts)):
        kids.append(_b(x, y, w_, h_, fill))
        fg = S["paper"] if dark else S["ink"]
        body = S["paper"] if dark else S["body"]
        kids.append(_t(x + 24, y + 20, 80, f"{i + 1:02d}", 22,
                       S["paper"] if dark else S["accent"], decor=True,
                       weight="bold", on=fill))
        ty = y + 56
        if pt["head"]:
            n = _t(x + 24, ty, w_ - 48, pt["head"],
                   26 if i == 0 else 21, fg, max_h=76, min_size=18,
                   weight="bold", on=fill)
            kids.append(n)
            ty = n["rect"][1] + n["rect"][3] + 12
        if pt["body"]:
            kids.append(_t(x + 24, ty, w_ - 48, pt["body"], 17, body,
                           max_h=max(60, h_ - (ty - y) - 20), on=fill))
    kids += _chrome(S, c, 64, 656, on=S["paper"])
    return kids, S["paper"], "light", "dense"


def a_timeline_ribbon(p, S, c):
    pts = _points(p)[:5]
    kids = [_t(64, 62, 1100, _head(p), 36, S["ink"], max_h=76,
               min_size=26, weight="bold", on=S["paper"])]
    kids += _motif(S, 1080, 70, 0.8, 4)
    kids.append(_d(90, 372, 1100, S["line"], thickness=3))
    n = max(len(pts), 2)
    for i, pt in enumerate(pts):
        x = 110 + i * (1040 / max(n - 1, 1))
        up = i % 2 == 0
        cy = 372
        kids.append(_o(x - 9, cy - 9, 18, S["accent"]))
        kids.append(_d(x, cy - (110 if up else -110), 1, S["line"],
                       vertical=True, h=110))
        ty = cy - 168 if up else cy + 46
        label = pt["head"] or str(p.get("labels", [""])[i] if i < len(p.get("labels", [])) else "")
        if label:
            kids.append(_t(x - 90, ty, 190, label, 22, S["ink"],
                           max_h=60, weight="bold", on=S["paper"], align="center"))
        if pt["body"]:
            kids.append(_t(x - 100, ty + 62, 210, pt["body"], 16,
                           S["body"], max_h=90, on=S["paper"], align="center"))
    kids += _chrome(S, c, 64, 660, on=S["paper"])
    return kids, S["paper"], "light", "mid"


def a_closing_echo(p, S, c):
    kids = [_b(900, 0, 380, H, S["accent"])]
    kids += _motif(S, 958, 90, 1.8, 1)
    msg = p.get("title") or p.get("quote") or "读完之后，留一个问题给自己"
    kids.append(_t(72, 220, 760, msg, 48, S["ink"], max_h=230,
                   min_size=30, weight="bold", on=S["paper"]))
    kids.append(_d(72, 480, 420, S["accent"], thickness=4))
    book = c["book"]
    kids.append(_t(72, 510, 760,
                   "《" + book.get("title", "") + "》 · 读书笔记", 20,
                   S["body"], on=S["paper"]))
    kids += _chrome(S, c, 72, 640, on=S["paper"])
    kids.append(_t(958, 600, 300, "END", 60, S["paper"], decor=True,
                   on=S["accent"], weight="bold"))
    return kids, S["paper"], "light", "airy"


ARCHETYPES = {
    "cover-editorial": {"density": "airy", "build": a_cover_editorial},
    "chapter-opener": {"density": "airy", "build": a_chapter_opener},
    "editorial-spread": {"density": "mid", "build": a_editorial_spread},
    "offset-triptych": {"density": "dense", "build": a_offset_triptych},
    "quote-bleed": {"density": "airy", "build": a_quote_bleed},
    "split-contrast": {"density": "mid", "build": a_split_contrast},
    "margin-notes": {"density": "mid", "build": a_margin_notes},
    "stair-list": {"density": "dense", "build": a_stair_list},
    "data-focus": {"density": "airy", "build": a_data_focus},
    "grid-mosaic": {"density": "dense", "build": a_grid_mosaic},
    "timeline-ribbon": {"density": "mid", "build": a_timeline_ribbon},
    "closing-echo": {"density": "airy", "build": a_closing_echo},
}

KIND_PREFS = {
    "cover": ["cover-editorial"],
    "chapter": ["chapter-opener"],
    "closing": ["closing-echo"],
    "quote": ["quote-bleed", "editorial-spread", "split-contrast"],
    "concept": ["editorial-spread", "margin-notes", "offset-triptych", "grid-mosaic"],
    "framework": ["offset-triptych", "grid-mosaic", "stair-list", "margin-notes"],
    "compare": ["split-contrast", "offset-triptych", "grid-mosaic"],
    "enum": ["stair-list", "grid-mosaic", "offset-triptych", "margin-notes"],
    "timeline": ["timeline-ribbon", "stair-list", "editorial-spread"],
    "data": ["data-focus", "split-contrast", "editorial-spread"],
    "notes": ["margin-notes", "editorial-spread", "stair-list"],
}
DEFAULT_PREFS = ["editorial-spread", "margin-notes", "offset-triptych",
                 "stair-list", "grid-mosaic", "split-contrast"]


# archetypes that genuinely need several content blocks to look intentional
MIN_POINTS = {"offset-triptych": 3, "grid-mosaic": 3,
              "stair-list": 3, "timeline-ribbon": 3}


def plan_archetypes(pages, rng):
    """Greedy diversity: prefer unused archetypes, never repeat a neighbour."""
    prefs = []
    for p in pages:
        cand = list(KIND_PREFS.get(p.get("kind"), DEFAULT_PREFS))
        n = len(_points(p))
        cand = [a for a in cand if MIN_POINTS.get(a, 0) <= n]
        if not cand:
            cand = list(DEFAULT_PREFS)
        rng.shuffle(cand)
        prefs.append(cand)
    used, plan, prev = set(), [], None
    for cand in prefs:
        fresh = [a for a in cand if a not in used and a != prev]
        if fresh:
            pick = fresh[0]
        else:
            nonprev = [a for a in cand if a != prev]
            pick = nonprev[0] if nonprev else cand[0]
            if pick == prev:
                pick = next((a for a in DEFAULT_PREFS if a != prev),
                            "editorial-spread")
        plan.append(pick)
        used.add(pick)
        prev = pick
    return plan


# ---------------------------------------------------------------------------
# composition entry point
# ---------------------------------------------------------------------------

def _style(derived, base):
    sem = (derived or {}).get("semantic") or T.get_theme(base)["semantic"]
    src = (derived or {}).get("source") or {}
    u = lambda k: str(sem[k]).upper()
    return {
        "paper": u("surface_light"), "deep": u("surface_dark"),
        "card": u("card_fill"), "ink": u("ink"), "ondark": u("ink_on_dark"),
        "body": u("body"), "muted": u("muted"), "line": u("line"),
        "accent": u("accent"), "accent2": u("accent_2"),
        "soft": u("accent_soft"),
        "decor": str(sem.get("decor_on_dark") or sem["accent_soft"]).upper(),
        "white": "#FFFFFF", "black": "#000000",
        "motif": src.get("motif", "band"),
    }


def compose(notes, notes_dir="", cover_path=None, base="magazine", seed=None):
    """Return (deck DSL, provenance ledger). Pure function of its inputs."""
    book = notes.get("book") or {}
    pages = notes.get("pages") or []
    if not pages:
        raise ValueError("notes.pages is empty")

    # resolve cover relative to the notes file (offline, no network)
    cover = cover_path or notes.get("cover") or book.get("cover")
    if cover and not os.path.isabs(cover):
        cover = os.path.join(notes_dir or ".", cover)
    derived, ledger = None, {}
    if cover and os.path.exists(cover):
        derived, ledger = CS.derive(cover, book.get("title", ""), base)
        ledger["cover_path"] = os.path.relpath(cover, notes_dir) if notes_dir else cover
    cover_file = os.path.basename(cover) if cover and os.path.exists(cover) else None
    if derived is None:
        # No reference image: still build a derived spec so the freeform
        # palette contract is explicit and #FFFFFF/#000000 stay legal.
        bt = T.get_theme(base)
        sem = dict(bt["semantic"])
        sem["decor_on_dark"] = CS.as_hex(CS.mix(
            CS.as_rgb(bt["semantic"]["surface_dark"]),
            CS.as_rgb(bt["semantic"]["ink_on_dark"]), 0.17))
        derived = {
            "name": base + "-creative", "label": "创作编排主题", "base": base,
            "semantic": sem, "visual": {},
            "palette_extra": sorted(set(bt["palette"]) | {"#FFFFFF", "#000000"}),
            "min_body": 16,
            "source": {"motif": "band", "cover_tone": "light",
                       "cover_file": None, "note": "无封面图，沿用基础主题令牌"},
        }
        ledger["fallback"] = "no cover image; base theme tokens reused"
    # Keep the emitted DSL portable. An absolute directory baked in here would
    # only resolve on the machine that ran `compose`, and breaks CI / other
    # checkouts with ASSET_MISSING. `cli.py` resolves assets_base against the
    # current working directory, so a cwd-relative path is both correct on
    # this machine and reproducible elsewhere.
    if cover_file:
        cover_dir = os.path.dirname(cover)
        try:
            assets_base = os.path.relpath(cover_dir, os.getcwd()) or "."
        except ValueError:  # different drives on Windows
            assets_base = cover_dir
    else:
        assets_base = ""

    raw = json.dumps(notes, ensure_ascii=False, sort_keys=True)
    seed = seed or hashlib.sha256((book.get("title", "") + raw +
                                   (ledger.get("cover_sha256", ""))).encode()).hexdigest()[:16]
    rng = random.Random(int(seed, 16))
    plan = plan_archetypes(pages, rng)
    S = _style(derived, base)

    slides = []
    for i, (page, arch) in enumerate(zip(pages, plan)):
        ctx = {"idx": i, "total": len(pages), "rng": rng, "book": book,
               "cover_file": cover_file, "cover_credit": page.get("source")}
        kids, surface, tone, density = ARCHETYPES[arch]["build"](page, S, ctx)
        slides.append({
            "type": "content", "tone": tone, "surface": surface,
            "composition": "freeform", "archetype": arch, "density": density,
            "role": page.get("kind", "content"),
            "children": kids,
        })

    deck = {
        "composed": True,
        "composition": "freeform",
        "theme": base,
        "assets_base": assets_base,
        "slides": slides,
        "art_direction": {
            "seed": seed, "archetypes": plan,
            "distinct": len(set(plan)), "pages": len(plan),
            "motif": S["motif"],
            "cover": ledger.get("cover_path"),
            "engine_version": 2,
        },
    }
    deck["derived_theme"] = derived
    ledger["archetypes"] = plan
    ledger["distinct"] = len(set(plan))
    ledger["seed"] = seed
    return deck, ledger


def main(argv=None):
    ap = argparse.ArgumentParser(description="FreePPT creative composition")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("compose")
    p.add_argument("notes")
    p.add_argument("--cover")
    p.add_argument("--base", default="magazine")
    p.add_argument("--seed")
    p.add_argument("--out")
    p.add_argument("--ledger")
    args = ap.parse_args(argv)

    notes_path = os.path.abspath(args.notes)
    notes = json.load(open(notes_path, encoding="utf-8"))
    deck, ledger = compose(notes, os.path.dirname(notes_path), args.cover,
                           args.base, args.seed)
    out = json.dumps(deck, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        open(args.out, "w", encoding="utf-8").write(out)
    if args.ledger:
        open(args.ledger, "w", encoding="utf-8").write(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    if not args.out:
        print(out)
    else:
        print(f"composed {len(deck['slides'])} pages / "
              f"{len(set(deck['art_direction']['archetypes']))} distinct "
              f"archetypes -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
