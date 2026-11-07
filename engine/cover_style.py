#!/usr/bin/env python3
"""Derive a reproducible visual language from a reference book-cover image.

Why this exists: a "theme" only swaps a fixed palette into a fixed master.
A reading-notes deck should instead inherit the actual book's color climate,
contrast and dominant composition, then express it differently on every page.

Output is a `derived_theme` spec understood by engine.themes.activate(), plus
a provenance ledger (cover SHA256, extracted swatches, dominant color block,
motif choice). Same cover + same book title => byte-identical spec; no clocks,
no randomness, no network.

Only dependency: Pillow (already required by FreePPT).
"""

import argparse
import hashlib
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

MOTIF_BY_POS = {
    "top": "band", "top-left": "band", "top-right": "vertical-rule",
    "left": "vertical-rule", "bottom-left": "vertical-rule",
    "center": "arc", "right": "dots", "bottom": "grid",
    "bottom-right": "grid",
}


def as_hex(c):
    return "#{:02X}{:02X}{:02X}".format(*[max(0, min(255, int(v))) for v in c])


def as_rgb(hx):
    s = str(hx).lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    """t=0 -> a, t=1 -> b."""
    if isinstance(a, str):
        a = as_rgb(a)
    if isinstance(b, str):
        b = as_rgb(b)
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def luminance(c):
    if isinstance(c, str):
        c = as_rgb(c)
    lin = [v / 255.0 / 12.92 if v / 255.0 <= 0.04045
           else ((v / 255.0 + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(fg, bg, floor, darken=True):
    """Nudge fg darker/lighter until it is legible on bg (deterministic)."""
    c = as_rgb(fg) if isinstance(fg, str) else tuple(fg)
    for _ in range(24):
        if contrast(c, bg) >= floor:
            return c
        c = mix(c, BLACK if darken else WHITE, 0.07)
    return c


def _saturation(c):
    return max(c) - min(c)


def extract_swatches(path, limit=8):
    """Median-cut quantize; drop near-white/near-black/flat-gray fills."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((160, 220))
        q = im.quantize(colors=14, method=Image.Quantize.MEDIANCUT).convert("RGB")
        counts = q.getcolors(maxcolors=14 * 256) or []
        raw = q.tobytes()  # 3 bytes/pixel; avoids the deprecated getdata()
        pixels = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
        w, h = q.size
    counts.sort(key=lambda x: -x[0])
    swatches = []
    for cnt, col in counts:
        c = tuple(col)
        lum = luminance(c)
        if lum > 0.93 or lum < 0.045 or _saturation(c) < 12:
            continue
        swatches.append({"hex": as_hex(c), "share": round(cnt / (w * h), 4)})
        if len(swatches) >= limit:
            break
    if not swatches:
        # flat/near-monochrome cover: use its most chromatic quantized color
        cands = [tuple(c) for _, c in counts
                 if 0.05 < luminance(tuple(c)) < 0.93]
        best = max(cands, key=_saturation) if cands else (140, 58, 43)
        swatches = [{"hex": as_hex(best), "share": 1.0}]

    # The most frequent color is usually the PAPER, not the book's signature
    # color. Score by chroma x coverage x mid-tone to find the real accent.
    def _score(s):
        c = as_rgb(s["hex"])
        return (_saturation(c) * min(1.0, s["share"] * 3.0)
                * (1.0 - abs(luminance(c) - 0.45)))

    main_hex = max(swatches, key=_score)["hex"]
    main = as_rgb(main_hex)
    grid = {}
    for y in range(h):
        for x in range(w):
            p = pixels[y * w + x]
            if sum(abs(p[i] - main[i]) for i in range(3)) < 105:
                key = (min(2, y * 3 // h), min(2, x * 3 // w))
                grid[key] = grid.get(key, 0) + 1
    if grid:
        (gy, gx), _ = max(grid.items(), key=lambda kv: kv[1])
        row = ["top", "bottom"][gy // 2]
        col = ["left", "right"][gx // 2]
        if (gy, gx) == (1, 1):
            pos = "center"
        elif gx == 1:
            pos = row
        elif gy == 1:
            pos = col
        else:
            pos = f"{row}-{col}"
    else:
        pos = "center"
    return swatches, pos, main_hex


def derive(path, book_title="", base="magazine"):
    """Return (derived_theme_spec, ledger). Deterministic, offline."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    swatches, pos, main_hex = extract_swatches(path)
    main = as_rgb(main_hex)
    others = [s["hex"] for s in swatches if s["hex"] != main_hex]
    secondary = as_rgb(others[0]) if others else mix(main, BLACK, 0.32)
    avg_lum = luminance(mix(main, secondary, 0.5))
    dark_cover = avg_lum < 0.22

    # paper inherits the cover's actual light swatch, not a synthetic white
    light_sw = next((s["hex"] for s in swatches
                     if luminance(as_rgb(s["hex"])) > 0.60), None)
    paper = mix(WHITE, as_rgb(light_sw) if light_sw else main, 0.42)
    deep = ensure_contrast(mix(main, BLACK, 0.62), WHITE, 7.0, darken=True)
    ink = ensure_contrast(mix(main, BLACK, 0.72), paper, 7.0, darken=True)
    # accent must stay vivid but be usable for large display type
    accent = mix(main, BLACK if luminance(main) > 0.55 else WHITE,
                 0.18 if luminance(main) > 0.55 else 0.12)
    accent = ensure_contrast(as_hex(accent), as_hex(paper), 4.6,
                             darken=luminance(paper) > 0.5)
    accent2 = ensure_contrast(as_hex(mix(secondary, BLACK, 0.10)),
                              as_hex(paper), 4.6, darken=True)

    warm = _saturation(main) < 90 and luminance(main) > 0.25
    serif = warm or base in ("magazine", "oriental")
    visual = {
        "latin_heading": "Georgia" if serif else "Arial",
        "ea_heading": "Songti SC" if serif else "PingFang SC",
        "latin_body": "Arial", "ea_body": "PingFang SC",
        "serif_heading": bool(serif),
        "radius": 0 if serif else 6,
        "line_spacing": 1.32 if serif else 1.18,
        "density": "relaxed",
        "accent_budget": 0.14,
    }
    semantic = {
        "surface_light": as_hex(paper),
        "surface_dark": as_hex(deep),
        "card_fill": as_hex(mix(paper, WHITE, 0.45)),
        "ink": as_hex(ink),
        "ink_on_dark": as_hex(paper),
        "body": as_hex(mix(ink, paper, 0.28)),
        "muted": as_hex(ensure_contrast(as_hex(mix(ink, paper, 0.50)),
                                        as_hex(paper), 4.5, darken=True)),
        "line": as_hex(mix(ink, paper, 0.84)),
        "accent": as_hex(accent),
        "accent_2": as_hex(accent2),
        "accent_soft": as_hex(mix(accent, paper, 0.80)),
        "decor_on_dark": as_hex(mix(deep, paper, 0.17)),
    }
    motif = MOTIF_BY_POS.get(pos, "band")
    name = "cover-" + sha[:8]
    spec = {
        "name": name,
        "label": f"《{book_title}》封面派生" if book_title else "封面派生主题",
        "base": base,
        "semantic": semantic,
        "visual": visual,
        "palette_extra": ["#FFFFFF", "#000000"] + [s["hex"] for s in swatches],
        "min_body": 16,
        "source": {
            "cover_file": os.path.basename(path),
            "cover_sha256": sha,
            "book": book_title,
            "swatches": swatches,
            "dominant_position": pos,
            "cover_tone": "dark" if dark_cover else "light",
            "motif": motif,
            "serif": bool(serif),
            "contrast_ink_on_paper": round(contrast(ink, paper), 2),
            "contrast_paper_on_deep": round(contrast(paper, deep), 2),
        },
    }
    ledger = dict(spec["source"])
    ledger["derived_theme"] = name
    return spec, ledger


def main(argv=None):
    ap = argparse.ArgumentParser(description="FreePPT cover-image style derivation")
    ap.add_argument("cover")
    ap.add_argument("--book", default="")
    ap.add_argument("--base", default="magazine")
    ap.add_argument("--out", help="write the derived_theme spec here")
    ap.add_argument("--ledger", help="write the provenance ledger here")
    args = ap.parse_args(argv)
    spec, ledger = derive(args.cover, args.book, args.base)
    out = json.dumps(spec, ensure_ascii=False, indent=2)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(out + "\n")
    if args.ledger:
        open(args.ledger, "w", encoding="utf-8").write(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(ledger, ensure_ascii=False, indent=2) if not args.out else
          f"derived theme -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
