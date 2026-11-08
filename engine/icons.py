#!/usr/bin/env python3
"""Deterministic, editable native-shape icon set (no image assets, no network).

Each icon is a small composition of native PowerPoint shapes laid out on a
100x100 logical grid; the compiler scales the grid to the target rect. This
mirrors the "icon card" language of modern generated decks while staying fully
editable, theme-tinted (one accent color), and offline — unlike bitmap/SVG
asset packs, there is nothing to license or download.

Spec vocabulary (coordinates in the 0..100 grid):
  {"k": shape, "x","y","w","h", "mode": "fill"|"stroke", "rot": degrees?}
  {"k": "line", "x1","y1","x2","y2"}
shape is one of the MSO autoshape names handled by compiler.add_icon.
"""

GRID = 100.0

# Each icon reads top-to-bottom; later specs paint on top of earlier ones.
ICONS = {
    # concentric rings + bullseye
    "target": [
        {"k": "oval", "x": 4, "y": 4, "w": 92, "h": 92, "mode": "stroke"},
        {"k": "oval", "x": 27, "y": 27, "w": 46, "h": 46, "mode": "stroke"},
        {"k": "oval", "x": 42, "y": 42, "w": 16, "h": 16, "mode": "fill"},
    ],
    # rising bars + baseline
    "chart": [
        {"k": "line", "x1": 14, "y1": 86, "x2": 88, "y2": 86},
        {"k": "rect", "x": 20, "y": 56, "w": 14, "h": 30, "mode": "fill"},
        {"k": "rect", "x": 43, "y": 40, "w": 14, "h": 46, "mode": "fill"},
        {"k": "rect", "x": 66, "y": 24, "w": 14, "h": 62, "mode": "fill"},
    ],
    # circle with check glyph
    "check": [
        {"k": "oval", "x": 4, "y": 4, "w": 92, "h": 92, "mode": "stroke"},
        {"k": "line", "x1": 28, "y1": 52, "x2": 43, "y2": 67},
        {"k": "line", "x1": 43, "y1": 67, "x2": 74, "y2": 33},
    ],
    # lightbulb: globe + cap + base
    "bulb": [
        {"k": "oval", "x": 27, "y": 8, "w": 46, "h": 46, "mode": "stroke"},
        {"k": "rect", "x": 40, "y": 52, "w": 20, "h": 9, "mode": "fill"},
        {"k": "rect", "x": 42, "y": 63, "w": 16, "h": 7, "mode": "fill"},
        {"k": "rect", "x": 44, "y": 72, "w": 12, "h": 7, "mode": "fill"},
        {"k": "line", "x1": 50, "y1": 22, "x2": 50, "y2": 42},
    ],
    # native gear + hub
    "gear": [
        {"k": "gear6", "x": 8, "y": 8, "w": 84, "h": 84, "mode": "fill"},
        {"k": "oval", "x": 37, "y": 37, "w": 26, "h": 26, "mode": "fill", "knock": True},
    ],
    # shield silhouette: plaque + chevron check
    "shield": [
        {"k": "shield", "x": 16, "y": 6, "w": 68, "h": 80, "mode": "fill"},
        {"k": "line", "x1": 33, "y1": 46, "x2": 45, "y2": 58},
        {"k": "line", "x1": 45, "y1": 58, "x2": 68, "y2": 32},
    ],
    # two people: heads + shoulders
    "users": [
        {"k": "oval", "x": 20, "y": 16, "w": 26, "h": 26, "mode": "fill"},
        {"k": "oval", "x": 54, "y": 22, "w": 22, "h": 22, "mode": "stroke"},
        {"k": "roundrect", "x": 12, "y": 52, "w": 40, "h": 34, "mode": "fill"},
        {"k": "roundrect", "x": 50, "y": 56, "w": 32, "h": 30, "mode": "stroke"},
    ],
    # clock face + hands
    "clock": [
        {"k": "oval", "x": 6, "y": 6, "w": 88, "h": 88, "mode": "stroke"},
        {"k": "line", "x1": 50, "y1": 50, "x2": 50, "y2": 24},
        {"k": "line", "x1": 50, "y1": 50, "x2": 70, "y2": 56},
        {"k": "oval", "x": 46, "y": 46, "w": 8, "h": 8, "mode": "fill"},
    ],
    # folder: back tab + front body
    "folder": [
        {"k": "roundrect", "x": 10, "y": 28, "w": 80, "h": 56, "mode": "stroke"},
        {"k": "roundrect", "x": 10, "y": 20, "w": 34, "h": 16, "mode": "stroke"},
        {"k": "rect", "x": 10, "y": 44, "w": 80, "h": 10, "mode": "fill"},
    ],
    # rocket: body + fin + flame
    "rocket": [
        {"k": "oval", "x": 38, "y": 10, "w": 24, "h": 48, "mode": "fill"},
        {"k": "oval", "x": 44, "y": 20, "w": 12, "h": 12, "mode": "fill", "knock": True},
        {"k": "triangle", "x": 26, "y": 46, "w": 16, "h": 22, "mode": "fill", "rot": 270},
        {"k": "triangle", "x": 58, "y": 46, "w": 16, "h": 22, "mode": "fill", "rot": 90},
        {"k": "triangle", "x": 42, "y": 60, "w": 16, "h": 26, "mode": "fill", "rot": 180},
    ],
    # book: cover + spine + pages
    "book": [
        {"k": "rect", "x": 16, "y": 14, "w": 68, "h": 72, "mode": "stroke"},
        {"k": "line", "x1": 30, "y1": 14, "x2": 30, "y2": 86},
        {"k": "line", "x1": 40, "y1": 32, "x2": 74, "y2": 32},
        {"k": "line", "x1": 40, "y1": 48, "x2": 74, "y2": 48},
        {"k": "line", "x1": 40, "y1": 64, "x2": 66, "y2": 64},
    ],
    # milestone flag on a pole
    "flag": [
        {"k": "line", "x1": 26, "y1": 10, "x2": 26, "y2": 90},
        {"k": "chevron", "x": 26, "y": 14, "w": 58, "h": 30, "mode": "fill"},
    ],
    # magnifier: ring + handle
    "search": [
        {"k": "oval", "x": 12, "y": 10, "w": 56, "h": 56, "mode": "stroke"},
        {"k": "line", "x1": 56, "y1": 56, "x2": 86, "y2": 86},
    ],
    # stacked layers
    "layers": [
        {"k": "diamond", "x": 18, "y": 14, "w": 64, "h": 24, "mode": "fill"},
        {"k": "diamond", "x": 18, "y": 38, "w": 64, "h": 24, "mode": "stroke"},
        {"k": "diamond", "x": 18, "y": 62, "w": 64, "h": 24, "mode": "stroke"},
    ],
}

# semantic alias -> canonical icon, so notes can use friendly names
ALIASES = {
    "goal": "target", "objective": "target", "kpi": "chart", "data": "chart",
    "insight": "bulb", "idea": "bulb", "settings": "gear", "process": "gear",
    "risk": "shield", "security": "shield", "protect": "shield",
    "team": "users", "org": "users", "organization": "users",
    "time": "clock", "plan": "clock", "schedule": "clock",
    "resource": "folder", "assets": "folder", "growth": "rocket",
    "knowledge": "book", "learning": "book", "milestone": "flag",
    "research": "search", "explore": "search", "ecosystem": "layers",
    "structure": "layers", "done": "check", "ok": "check",
}


def resolve(name):
    """Canonical icon name or None if unknown."""
    if not name:
        return None
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    if key in ICONS:
        return key
    return ALIASES.get(key)


def specs(name):
    key = resolve(name)
    return ICONS[key] if key else []
