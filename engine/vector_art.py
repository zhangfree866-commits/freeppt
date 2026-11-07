#!/usr/bin/env python3
"""Procedural vector illustration: one shape model, two backends (SVG + PNG).

Why: generated/photos carry licensing and AI-label risk. These motifs are fully
programmatic (deterministic, editable SVG, no watermark, no attribution needed)
and locked to the consulting palette so they match the deck.

Motifs: growth | dashboard | network | funnel | cycle | shield
"""

import math
import os

from PIL import Image, ImageDraw

VW, VH = 1200, 800  # logical canvas (3:2), matches image boxes

PALETTE = {
    "navy": "#061F32", "royal": "#001965", "cyan": "#08A6F6",
    "light": "#99BDED", "gray": "#44546A", "mid": "#808080",
    "line": "#E5E7EB", "white": "#FFFFFF",
}


# ---- shape IR ---------------------------------------------------------------
def rect(x, y, w, h, fill, rx=0, op=1.0):
    return {"k": "rect", "x": x, "y": y, "w": w, "h": h, "fill": fill,
            "rx": rx, "op": op}


def circle(cx, cy, r, fill, stroke=None, sw=2, op=1.0):
    return {"k": "circle", "cx": cx, "cy": cy, "r": r, "fill": fill,
            "stroke": stroke, "sw": sw, "op": op}


def line(x1, y1, x2, y2, stroke, width=3):
    return {"k": "line", "pts": [(x1, y1), (x2, y2)], "stroke": stroke,
            "width": width}


def polyline(pts, stroke, width=6, dash=False):
    return {"k": "poly", "pts": pts, "stroke": stroke, "width": width,
            "dash": dash}


def polygon(pts, fill):
    return {"k": "polygon", "pts": pts, "fill": fill}


def text(x, y, content, size, color, anchor="start", bold=False):
    return {"k": "text", "x": x, "y": y, "content": content, "size": size,
            "color": color, "anchor": anchor, "bold": bold}


def _p(c, P):
    hx = P[c].lstrip("#")
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


# ---- motifs -----------------------------------------------------------------
def _axes():
    return [line(110, 680, 1100, 680, "line", 3),
            line(110, 120, 110, 680, "line", 3)]


def motif_growth(P):
    s = _axes()
    bars = [(180, 470, 90), (330, 400, 160), (480, 330, 230),
            (630, 250, 310), (780, 190, 370), (930, 140, 420)]
    for x, y, h in bars:
        s.append(rect(x, y, 70, h, "light", rx=6))
    pts = [(215, 430), (365, 360), (515, 290), (665, 215), (815, 160), (965, 115)]
    s.append(polyline(pts, "cyan", 8))
    for x, y in pts:
        s.append(circle(x, y, 11, "cyan"))
    s.append(circle(965, 115, 20, "white", stroke="cyan", sw=5))
    return s


def motif_dashboard(P):
    s = []
    cards = [(110, 130, 300, 180), (450, 130, 300, 180), (790, 130, 300, 180)]
    for i, (x, y, w, h) in enumerate(cards):
        s.append(rect(x, y, w, h, "white", rx=16))
        s.append(rect(x, y, w, 12, ["cyan", "light", "navy"][i], rx=6))
    # big KPI block
    s.append(rect(110, 360, 600, 300, "navy", rx=18))
    s.append(rect(150, 420, 240, 34, "cyan", rx=8))
    s.append(rect(150, 480, 360, 18, "light", rx=6))
    s.append(rect(150, 520, 300, 18, "light", rx=6))
    # mini donut
    cx, cy, r = 880, 510, 120
    s.append(circle(cx, cy, r, "line"))
    s.append(circle(cx, cy, r - 44, "white"))
    s.append(circle(cx, cy, 26, "cyan"))
    # small bars on cards
    for x, y, w, h in cards:
        for k in range(3):
            bh = 40 + k * 22
            s.append(rect(x + 36 + k * 70, y + h - 30 - bh, 40, bh,
                          "light", rx=4))
    return s


def motif_network(P):
    import random
    random.seed(11)
    pts = [(random.randint(160, 1040), random.randint(150, 650)) for _ in range(16)]
    s = []
    for i, (x1, y1) in enumerate(pts):
        order = sorted(pts, key=lambda q: (q[0] - x1) ** 2 + (q[1] - y1) ** 2)
        for (x2, y2) in order[1:3]:
            d = math.hypot(x2 - x1, y2 - y1)
            if d < 320:
                s.append(line(x1, y1, x2, y2, "line", 2))
    for i, (x, y) in enumerate(pts):
        s.append(circle(x, y, 15 if i % 4 else 22,
                        "cyan" if i % 4 == 0 else "light"))
    return s


def motif_funnel(P):
    s = []
    stages = [
        [(200, 140), (1000, 140), (900, 240), (300, 240)],
        [(300, 268), (900, 268), (812, 360), (388, 360)],
        [(388, 388), (812, 388), (736, 472), (464, 472)],
        [(464, 500), (736, 500), (668, 580), (532, 580)],
        [(532, 608), (668, 608), (628, 672), (572, 672)],
    ]
    cols = ["navy", "royal", "cyan", "light", "gray"]
    for pts, c in zip(stages, cols):
        s.append(polygon(pts, c))
    return s


def motif_cycle(P):
    s = []
    cx, cy, r = 600, 400, 240
    for i, c in enumerate(["cyan", "light", "navy"]):
        a0 = math.radians(i * 120 - 90)
        a1 = math.radians(i * 120 + 70 - 90)
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        large = 0
        s.append({"k": "arc", "cx": cx, "cy": cy, "r": r,
                  "a0": a0, "a1": a1, "stroke": c, "width": 46})
        # arrow head at arc end
        s.append(circle(x1, y1, 16, c))
    s.append(circle(cx, cy, 70, "white", stroke="line", sw=4))
    s.append(circle(cx, cy, 26, "cyan"))
    return s


def motif_shield(P):
    s = []
    shield = [(600, 120), (920, 230), (920, 470), (600, 700),
              (280, 470), (280, 230)]
    s.append(polygon(shield, "navy"))
    inner = [(600, 190), (850, 278), (850, 462), (600, 632),
             (350, 462), (350, 278)]
    s.append(polygon(inner, "royal"))
    # check mark
    s.append(polyline([(470, 420), (565, 510), (760, 300)], "cyan", 34))
    return s


def motif_matrix(P):
    # 2x2 strategy matrix with axis arrows and quadrant labels
    s = []
    x0, y0, cell = 280, 170, 330
    cols = ["light", "cyan", "navy", "royal"]
    labels = [("Q1", "优先投入"), ("Q2", "快速试点"),
              ("Q3", "维持观察"), ("Q4", "果断退出")]
    for i in range(2):
        for j in range(2):
            idx = i * 2 + j
            s.append(rect(x0 + j * cell, y0 + i * cell, cell - 12, cell - 12,
                          cols[idx], rx=14))
            s.append(text(x0 + j * cell + 26, y0 + i * cell + 56,
                          labels[idx][0], 40, "white", bold=True))
            s.append(text(x0 + j * cell + 26, y0 + i * cell + 120,
                          labels[idx][1], 30, "white"))
    # axis arrows
    s.append(polyline([(250, 660), (250, 120)], "gray", 4))
    s.append(polyline([(250, 660), (980, 660)], "gray", 4))
    s.append(polygon([(250, 108), (238, 132), (262, 132)], "gray"))
    s.append(polygon([(992, 660), (968, 648), (968, 672)], "gray"))
    s.append(text(150, 150, "重要性", 28, "gray"))
    s.append(text(880, 700, "紧迫度", 28, "gray"))
    return s


def motif_org(P):
    # top-down org chart: 1 root, 3 managers, 6 leaves
    s = []

    def node(cx, y, w, h, fill, label, tcol="white", ts=26):
        s.append(rect(cx - w / 2, y, w, h, fill, rx=14))
        s.append(text(cx, y + h / 2 + ts * 0.35, label, ts, tcol,
                      anchor="middle", bold=True))

    root_cx, top_y = 600, 110
    node(root_cx, top_y, 260, 86, "navy", "管理层")
    m_y, leaf_y = 300, 520
    mxs = [280, 600, 920]
    for mx in mxs:
        s.append(line(root_cx, top_y + 86, root_cx, 240, "mid", 3))
        s.append(line(mx, 240, root_cx, 240, "mid", 3))
        s.append(line(mx, 240, mx, m_y, "mid", 3))
        node(mx, m_y, 220, 80, "royal", "业务线")
    for k, mx in enumerate(mxs):
        for off in (-78, 78):
            lx = mx + off
            s.append(line(mx, m_y + 80, mx, 470, "line", 3))
            s.append(line(lx, 470, mx, 470, "line", 3))
            s.append(line(lx, 470, lx, leaf_y, "line", 3))
            node(lx, leaf_y, 150, 72, "cyan", "团队", tcol="white", ts=22)
    return s


def motif_map(P):
    # abstract world map: dotted landmasses + route arcs with hub nodes
    import random
    random.seed(5)
    s = [rect(120, 130, 960, 540, "white", rx=24)]
    # dotted landmass clusters (three abstract continents)
    centers = [(360, 360, 150), (660, 320, 190), (880, 480, 110)]
    for cx0, cy0, rad in centers:
        for _ in range(70):
            ang = random.uniform(0, 6.283)
            rr = rad * math.sqrt(random.random())
            x = cx0 + rr * math.cos(ang)
            y = cy0 + rr * math.sin(ang) * 0.7
            s.append(circle(x, y, 7, "light"))
    hubs = [(280, 340), (620, 300), (900, 470)]
    # route arcs (quadratic approximation via short polyline segments)
    for a in range(len(hubs)):
        for b in range(a + 1, len(hubs)):
            (x1, y1), (x2, y2) = hubs[a], hubs[b]
            mx, my = (x1 + x2) / 2, min(y1, y2) - 90
            pts = []
            for t in range(21):
                u = t / 20
                x = (1 - u) ** 2 * x1 + 2 * (1 - u) * u * mx + u ** 2 * x2
                y = (1 - u) ** 2 * y1 + 2 * (1 - u) * u * my + u ** 2 * y2
                pts.append((x, y))
            s.append(polyline(pts, "cyan", 4))
    for x, y in hubs:
        s.append(circle(x, y, 20, "white", stroke="cyan", sw=5))
        s.append(circle(x, y, 9, "cyan"))
    return s


def motif_venn(P):
    # three overlapping translucent circles
    s = []
    centers = [(500, 380), (700, 380), (600, 240)]
    cols = ["cyan", "royal", "navy"]
    for (cx, cy), c in zip(centers, cols):
        s.append(circle(cx, cy, 200, c, op=0.42))
    s.append(text(600, 430, "交集", 34, "white", anchor="middle", bold=True))
    s.append(text(320, 400, "A", 40, "gray", bold=True))
    s.append(text(860, 400, "B", 40, "gray", bold=True))
    s.append(text(600, 120, "C", 40, "gray", bold=True))
    return s


MOTIFS = {
    "growth": motif_growth, "dashboard": motif_dashboard, "network": motif_network,
    "funnel": motif_funnel, "cycle": motif_cycle, "shield": motif_shield,
    "matrix": motif_matrix, "org": motif_org, "map": motif_map, "venn": motif_venn,
}


# ---- SVG backend ------------------------------------------------------------
def _svg_el(el, P):
    c = lambda k: P[el.get(k, "white")]
    if el["k"] == "rect":
        return (f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["w"]}" '
                f'height="{el["h"]}" rx="{el["rx"]}" fill="{c("fill")}" '
                f'fill-opacity="{el.get("op", 1.0)}"/>')
    if el["k"] == "circle":
        st = f' stroke="{c("stroke")}" stroke-width="{el["sw"]}"' if el.get("stroke") else ""
        return (f'<circle cx="{el["cx"]}" cy="{el["cy"]}" r="{el["r"]}" '
                f'fill="{c("fill")}" fill-opacity="{el.get("op", 1.0)}"{st}/>')
    if el["k"] == "text":
        anchor = {"middle": "middle", "end": "end"}.get(el.get("anchor"), "start")
        weight = ' font-weight="700"' if el.get("bold") else ""
        return (f'<text x="{el["x"]}" y="{el["y"]}" fill="{c("color")}" '
                f'font-size="{el["size"]}" text-anchor="{anchor}" '
                f'font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif"{weight}>'
                f'{el["content"]}</text>')
    if el["k"] in ("line", "poly"):
        pts = " ".join(f"{x},{y}" for x, y in el["pts"])
        dash = ' stroke-dasharray="14 12"' if el.get("dash") else ""
        tag = "polyline" if el["k"] == "poly" else "line"
        if tag == "line":
            (x1, y1), (x2, y2) = el["pts"]
            return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                    f'stroke="{c("stroke")}" stroke-width="{el["width"]}" '
                    f'stroke-linecap="round"/>')
        return (f'<polyline points="{pts}" fill="none" stroke="{c("stroke")}" '
                f'stroke-width="{el["width"]}" stroke-linecap="round" '
                f'stroke-linejoin="round"{dash}/>')
    if el["k"] == "polygon":
        pts = " ".join(f"{x},{y}" for x, y in el["pts"])
        return f'<polygon points="{pts}" fill="{c("fill")}"/>'
    if el["k"] == "arc":
        x0 = el["cx"] + el["r"] * math.cos(el["a0"])
        y0 = el["cy"] + el["r"] * math.sin(el["a0"])
        x1 = el["cx"] + el["r"] * math.cos(el["a1"])
        y1 = el["cy"] + el["r"] * math.sin(el["a1"])
        large = 1 if (el["a1"] - el["a0"]) > math.pi else 0
        return (f'<path d="M {x0:.1f} {y0:.1f} A {el["r"]} {el["r"]} 0 {large} 1 '
                f'{x1:.1f} {y1:.1f}" fill="none" stroke="{c("stroke")}" '
                f'stroke-width="{el["width"]}" stroke-linecap="round"/>')
    return ""


def to_svg(shapes, P, bg="white"):
    body = "\n  ".join(_svg_el(el, P) for el in shapes)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{VW}" height="{VH}" '
            f'viewBox="0 0 {VW} {VH}">\n'
            f'<rect width="{VW}" height="{VH}" fill="{P[bg]}"/>\n  {body}\n</svg>\n')


# ---- Pillow backend ---------------------------------------------------------
def _scale(pt, scale):
    return int(round(pt * scale))


_FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def _vfont(px_size):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, max(8, int(px_size)))
        except Exception:
            continue
    return ImageFont.load_default()


def to_png(shapes, P, bg, out, size=(1536, 1024)):
    img = Image.new("RGBA", size, _p(bg, P) + (255,))
    d = ImageDraw.Draw(img)
    sx, sy = size[0] / VW, size[1] / VH
    S = lambda v, ax: int(round(v * (sx if ax == "x" else sy)))

    def R(box):
        x, y, w, h = box
        return [S(x, "x"), S(y, "y"), S(x + w, "x"), S(y + h, "y")]

    def rgba(key, op=1.0):
        return _p(key, P) + (int(round(255 * op)),)

    for el in shapes:
        if el["k"] == "rect":
            d.rounded_rectangle(R((el["x"], el["y"], el["w"], el["h"])),
                                radius=S(el["rx"], "x"),
                                fill=rgba(el["fill"], el.get("op", 1.0)))
        elif el["k"] == "circle":
            cx, cy, r = S(el["cx"], "x"), S(el["cy"], "y"), S(el["r"], "x")
            d.ellipse([cx - r, cy - r, cx + r, cy + r],
                      fill=rgba(el["fill"], el.get("op", 1.0)),
                      outline=_p(el["stroke"], P) if el.get("stroke") else None,
                      width=S(el["sw"], "x") if el.get("stroke") else 1)
        elif el["k"] in ("line", "poly"):
            pts = [(S(x, "x"), S(y, "y")) for x, y in el["pts"]]
            d.line(pts, fill=_p(el["stroke"], P), width=S(el["width"], "x"),
                   joint="curve")
            if el["k"] == "line":
                x, y = pts[-1]
                rr = max(2, S(el["width"], "x") // 2)
                d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=_p(el["stroke"], P))
        elif el["k"] == "polygon":
            d.polygon([(S(x, "x"), S(y, "y")) for x, y in el["pts"]],
                      fill=rgba(el["fill"], el.get("op", 1.0)))
        elif el["k"] == "arc":
            bbox = [S(el["cx"] - el["r"], "x"), S(el["cy"] - el["r"], "y"),
                    S(el["cx"] + el["r"], "x"), S(el["cy"] + el["r"], "y")]
            d.arc(bbox, start=math.degrees(el["a0"]), end=math.degrees(el["a1"]),
                  fill=_p(el["stroke"], P), width=S(el["width"], "x"))
        elif el["k"] == "text":
            f = _vfont(el["size"] * sy)
            anchor = "mm" if el.get("anchor") == "middle" else "ls"
            d.text((S(el["x"], "x"), S(el["y"], "y")), el["content"],
                   fill=_p(el["color"], P), font=f, anchor=anchor)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    img.convert("RGB").save(out)
    return out


def build(motif, out_png, out_svg=None, palette=None, bg="white", size=(1536, 1024)):
    if motif not in MOTIFS:
        raise ValueError(f"unknown motif {motif}; choose {list(MOTIFS)}")
    P = {**PALETTE, **(palette or {})}
    shapes = MOTIFS[motif](P)
    to_png(shapes, P, bg, out_png, size)
    if out_svg:
        os.makedirs(os.path.dirname(out_svg) or ".", exist_ok=True)
        with open(out_svg, "w", encoding="utf-8") as f:
            f.write(to_svg(shapes, P, bg))
    return out_png, out_svg


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Procedural vector illustration.")
    ap.add_argument("motif", choices=list(MOTIFS))
    ap.add_argument("out_png")
    ap.add_argument("--svg")
    ap.add_argument("--bg", default="white", choices=list(PALETTE))
    a = ap.parse_args()
    png, svg = build(a.motif, a.out_png, a.svg, bg=a.bg)
    print("png:", png)
    if svg:
        print("svg:", svg)
