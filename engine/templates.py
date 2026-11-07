"""Master-layout library. Each template turns a plain `data` dict into a slide DSL.

A deck spec is a compact JSON:
  {"scenario": "consulting", "transition": "fade",
   "slides": [{"template": "three_cards", "data": {...}}, ...]}

Design tokens are locked to the consulting scenario palette.
"""

from . import themes as _themes

# Defaults equal the legacy consulting palette so any entry point keeps the
# classic look until a deck explicitly selects another theme. These module
# globals are re-bound at runtime by _apply_theme() when a deck is expanded.
NAVY = "#061F32"        # ink: dark text on light surfaces
DARK_FILL = "#061F32"   # surface_dark: filled dark cards/bands
ROYAL = "#001965"       # accent_2
CYAN = "#08A6F6"        # accent
LIGHT = "#99BDED"       # accent_soft / secondary on dark
GRAY = "#44546A"        # body text
MID = "#808080"         # muted
LINE = "#E5E7EB"        # hairline / card border
WHITE = "#FFFFFF"       # ink_on_dark: light text on dark surfaces
CARD_FILL = "#FFFFFF"   # card_fill: light card background


def _apply_theme(th):
    """Re-bind semantic color globals to the active theme's palette."""
    global NAVY, DARK_FILL, ROYAL, CYAN, LIGHT, GRAY, MID, LINE, WHITE, CARD_FILL
    sem = th["semantic"]
    NAVY = sem["ink"]
    DARK_FILL = sem["surface_dark"]
    ROYAL = sem["accent_2"]
    CYAN = sem["accent"]
    LIGHT = sem["accent_soft"]
    GRAY = sem["body"]
    MID = sem["muted"]
    LINE = sem["line"]
    WHITE = sem["ink_on_dark"]
    CARD_FILL = sem["card_fill"]


def _fade(names, effect="fade", start="after"):
    return [{"target": n, "effect": effect, "start": start, "order": i}
            for i, n in enumerate(names)]


def cover(d):
    s = {"type": "cover", "background": {"image": d.get("bg_image"),
                                         "overlay": 62} if d.get("bg_image") else None,
         "children": [
             {"t": "box", "layout": "rows", "gap": 24, "padding": 60,
              "children": [
                  {"t": "spacer", "flex": 1},
                  {"t": "text", "text": d["title"], "size": d.get("title_size", 68),
                   "weight": "bold", "color": WHITE},
                  {"t": "text", "text": d["subtitle"], "size": 24, "color": LIGHT},
                  {"t": "spacer", "flex": 1},
                  {"t": "box", "layout": "cols", "gap": 32, "padding": 0,
                   "children": [
                       {"t": "text", "text": d.get("org", ""), "size": 18, "color": WHITE},
                       {"t": "text", "text": d.get("date", ""), "size": 18,
                        "color": LIGHT, "align": "right"},
                   ]},
              ]}]}
    return s


def agenda(d):
    rows = []
    for i, it in enumerate(d["items"]):
        rows.append({"t": "box", "layout": "cols", "gap": 24, "padding": 0,
                     "children": [
                         {"t": "text", "text": f"{i + 1:02d}", "size": 30,
                          "weight": "bold", "color": CYAN, "width": 60},
                         {"t": "box", "layout": "rows", "gap": 0, "padding": 0,
                          "children": [
                              {"t": "text", "text": it["title"], "size": 22,
                               "weight": "bold", "color": NAVY},
                              {"t": "text", "text": it.get("summary", ""), "size": 18,
                               "color": GRAY},
                          ]},
                     ]})
    return {"type": "toc", "title": d.get("title", "目录"),
            "layout": "rows", "gap": 24, "children": rows}


def section(d):
    return {"type": "section",
            "background": {"image": d.get("bg_image"), "overlay": 66} if d.get("bg_image") else None,
            "children": [
                {"t": "box", "layout": "rows", "gap": 24, "padding": 60, "children": [
                    {"t": "spacer", "flex": 1},
                    {"t": "text", "text": d["no"], "size": 200, "weight": "bold",
                     "color": CYAN},
                    {"t": "text", "text": d["title"], "size": 46, "weight": "bold",
                     "color": WHITE},
                    {"t": "text", "text": d.get("en", ""), "size": 20, "color": LIGHT},
                    {"t": "spacer", "flex": 1},
                ]}]}


def three_cards(d):
    cards = []
    names = []
    for i, c in enumerate(d["cards"]):
        nm = f"card{i + 1}"
        names.append(nm)
        blocks = [{"text": f"{i + 1:02d}", "size": 18, "weight": "bold", "color": CYAN},
                  {"text": c["title"], "size": 24, "weight": "bold", "color": NAVY,
                   "space_before": 6},
                  {"text": c["body"], "size": 18, "color": GRAY, "space_before": 10}]
        cards.append({"t": "richcard", "fill": CARD_FILL, "border": LINE, "padding": 24,
                      "_name": nm, "blocks": blocks})
    return {"type": "content", "layout": "rows", "sparse": True,
            "title": d["title"],
            "anims": _fade(names),
            "children": [
                {"t": "spacer", "flex": 1},
                {"t": "box", "layout": "cols", "gap": 32, "padding": 0,
                 "children": cards},
                {"t": "spacer", "flex": 1},
            ]}


def kpi_row(d):
    cards, names = [], []
    for i, k in enumerate(d["kpis"]):
        nm = f"kpi{i + 1}"
        names.append(nm)
        cards.append({"t": "richcard", "fill": DARK_FILL, "padding": 28, "_name": nm,
                      "blocks": [
                          {"text": k["value"], "size": k.get("size", 72),
                           "weight": "bold", "color": CYAN},
                          {"text": k["label"], "size": 18, "color": WHITE,
                           "space_before": 12},
                      ]})
    return {"type": "content", "layout": "rows", "title": d["title"], "sparse": True,
            "anims": _fade(names, effect="fly-up"),
            "children": [
                {"t": "spacer", "flex": 1},
                {"t": "box", "layout": "cols", "gap": 32, "padding": 0,
                 "children": cards},
                {"t": "spacer", "flex": 1},
                {"t": "text", "text": d.get("note", ""), "size": 18, "color": GRAY},
            ]}


def chart_insight(d):
    ch = d["chart"]
    return {"type": "chart", "layout": "cols", "title": d["title"],
            "footer": {"source": d.get("source", "")},
            "anims": _fade(["chart1", "insight1"]),
            "children": [
                {"t": "chart", "kind": ch.get("kind", "column"), "flex": 1,
                 "_name": "chart1", "categories": ch["categories"],
                 "series": ch["series"],
                 "colors": ch.get("colors", [LIGHT, CYAN])},
                {"t": "box", "layout": "rows", "gap": 24, "padding": 24,
                 "width": d.get("insight_width", 360), "fill": DARK_FILL,
                 "_name": "insight1",
                 "children": [
                     {"t": "text", "text": d.get("insight_title", "核心洞察"),
                      "size": 24, "weight": "bold", "color": WHITE},
                     {"t": "text", "text": d["insight"], "size": 18, "color": WHITE},
                     {"t": "spacer", "flex": 1},
                     {"t": "kpi", "value": d["kpi"]["value"],
                      "label": d["kpi"]["label"], "vsize": d["kpi"].get("size", 80),
                      "lsize": 18, "color": CYAN, "lcolor": LIGHT},
                 ]},
            ]}


def image_text(d):
    return {"type": "content", "layout": "cols", "title": d["title"],
            "footer": {"source": d["source"]} if d.get("source") else None,
            "children": [
                {"t": "image", "src": d["image"], "flex": 1, "fit": "cover"},
                {"t": "box", "layout": "rows", "gap": 20, "padding": 24,
                 "width": d.get("text_width", 400),
                 "children": [
                     {"t": "text", "text": d["heading"], "size": 26,
                      "weight": "bold", "color": NAVY},
                     {"t": "text", "text": d["body"], "size": 19, "color": GRAY},
                 ]},
            ]}


def process(d):
    cols, names = [], []
    for i, st in enumerate(d["steps"]):
        nm = f"step{i + 1}"
        names.append(nm)
        cols.append({"t": "richcard", "fill": CARD_FILL, "border": LINE, "padding": 24,
                     "_name": nm,
                     "blocks": [
                         {"text": f"{i + 1:02d}", "size": 26, "weight": "bold",
                          "color": CYAN},
                         {"text": st["title"], "size": 21, "weight": "bold",
                          "color": NAVY, "space_before": 12},
                         {"text": st["desc"], "size": 18, "color": GRAY,
                          "space_before": 10},
                     ]})
    return {"type": "content", "layout": "rows", "title": d["title"], "sparse": True,
            "anims": _fade(names, effect="fly-up"),
            "children": [
                {"t": "spacer", "flex": 1},
                {"t": "box", "layout": "cols", "gap": 32, "padding": 0,
                 "children": cols},
                {"t": "spacer", "flex": 1},
            ]}


def timeline(d):
    cols = []
    for i, p in enumerate(d["points"]):
        cols.append({"t": "box", "layout": "rows", "gap": 12, "padding": 0,
                     "children": [
                         {"t": "divider", "color": LINE},
                         {"t": "shape", "kind": "oval", "size": 18, "width": 18,
                          "fill": CYAN},
                         {"t": "text", "text": p["label"], "size": 20,
                          "weight": "bold", "color": NAVY},
                         {"t": "text", "text": p["text"], "size": 18, "color": GRAY},
                     ]})
    return {"type": "content", "layout": "rows", "title": d["title"],
            "children": [
                {"t": "spacer", "flex": 1},
                {"t": "box", "layout": "cols", "gap": 32, "padding": 0,
                 "children": cols},
                {"t": "spacer", "flex": 1},
            ], "sparse": True}


def closing(d):
    return {"type": "closing",
            "background": {"image": d.get("bg_image"), "overlay": 66} if d.get("bg_image") else None,
            "children": [
                {"t": "box", "layout": "rows", "gap": 24, "padding": 60, "children": [
                    {"t": "spacer", "flex": 1},
                    {"t": "text", "text": d.get("title", "谢谢"), "size": 80,
                     "weight": "bold", "color": WHITE},
                    {"t": "text", "text": d.get("subtitle", ""), "size": 22,
                     "color": LIGHT},
                    {"t": "text", "text": d.get("org", ""), "size": 18, "color": WHITE},
                    {"t": "spacer", "flex": 1},
                ]}]}


TEMPLATES = {
    "cover": cover,
    "agenda": agenda,
    "section": section,
    "three_cards": three_cards,
    "kpi_row": kpi_row,
    "chart_insight": chart_insight,
    "image_text": image_text,
    "process": process,
    "timeline": timeline,
    "closing": closing,
}


def expand_deck(doc):
    th = _themes.activate(doc)
    _apply_theme(th)
    slides = []
    trans = doc.get("transition")
    for item in doc["slides"]:
        tpl = TEMPLATES[item["template"]]
        s = tpl(item["data"])
        if trans and "transition" not in s:
            s["transition"] = trans
        slides.append(s)
    return {"theme": _themes.resolve_name(doc),
            "scenario": doc.get("scenario", "consulting"),
            "assets_base": doc.get("assets_base", ""), "slides": slides}
