"""Deterministic Flexbox-style layout for the PPT DSL (px, canvas 1280x720).

Rule model (deliberately simple, no circular sizing):
- Every box/card is laid out inside a FIXED rect assigned by its parent.
- rows: children stretch to content width; heights are hug-content, except
  flex children which share leftover height.
- cols: heights stretch to content height; widths come from explicit `width`,
  else `flex`, else containers/charts implicitly flex:1 (equal split), while
  text leaves hug their one-line width.
- The slide skeleton (title / content region / footer) is positioned with
  fixed geometry, not generic flex.
"""

CANVAS_W, CANVAS_H = 1280, 720
PAD = 60
CONTENT_BOTTOM = 660
LINE_FACTOR = 1.3

CONTAINERS = {"box", "card", "slide"}

_IMG_RATIO_CACHE = {}


ASSETS_BASE = ""


def _img_path(node):
    src = node.get("src", "")
    import os
    if os.path.isabs(src) or not ASSETS_BASE:
        return src
    return os.path.join(ASSETS_BASE, src)


def image_ratio(src):
    """width/height of an image file (cached)."""
    if src in _IMG_RATIO_CACHE:
        return _IMG_RATIO_CACHE[src]
    ratio = 1.5
    try:
        from PIL import Image
        with Image.open(src) as im:
            iw, ih = im.size
        ratio = iw / ih if ih else 1.5
    except Exception:
        pass
    _IMG_RATIO_CACHE[src] = ratio
    return ratio


def char_w(ch, size):
    if ord(ch) >= 0x2E80 or ch in "，。、；：？！（）【】“”‘’—…·":
        return size * 1.02
    if ch == " ":
        return size * 0.3
    return size * 0.56


def _is_cjk(ch):
    return ord(ch) >= 0x2E80 or ch in "，。、；：？！（）【】“”‘’—…·"


def _tokenize(para):
    # CJK chars are individually breakable; latin/digit runs stay as one word
    tokens, buf = [], ""
    for ch in para:
        if _is_cjk(ch):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        else:
            buf += ch
    if buf:
        tokens.append(buf)
    return tokens


def wrap_lines(text, size, width):
    lines = []
    for para in str(text).split("\n"):
        cur, cur_w = "", 0.0
        for tok in _tokenize(para):
            w = sum(char_w(c, size) for c in tok)
            if not cur or cur_w + w <= width:
                cur += tok
                cur_w += w
            elif w > width:  # single token wider than line: hard split
                lines.append(cur.rstrip())
                part, pw = "", 0.0
                for ch in tok:
                    cw = char_w(ch, size)
                    if part and pw + cw > width:
                        lines.append(part)
                        part, pw = ch, cw
                    else:
                        part += ch
                        pw += cw
                cur, cur_w = part, pw
            else:  # whole latin word wraps to next line
                lines.append(cur.rstrip())
                cur, cur_w = tok.lstrip(), w - sum(
                    char_w(c, size) for c in tok[:len(tok) - len(tok.lstrip())])
        lines.append(cur)
    lines = [ln if ln else "" for ln in lines] or [""]
    from . import typography as _typo
    if _typo.is_enabled():
        lines = _typo.apply_kinsoku(lines)
    return lines


def leaf_text_h(node, width):
    size = node.get("size", 20)
    n = len(wrap_lines(node.get("text", ""), size, max(width, 1)))
    return n * size * LINE_FACTOR


def kpi_h(node, width):
    vs = node.get("vsize", node.get("size", 96))
    h = vs * LINE_FACTOR
    if node.get("label"):
        h += leaf_text_h({**node, "size": node.get("lsize", 18),
                          "text": node["label"]}, width)
    return h


def hug_h(node, width):
    """Intrinsic height of node when given a fixed content width."""
    t = node["t"]
    if t == "spacer":
        return 0.0
    if t == "divider":
        return 1.5
    if t == "image":
        if node.get("height"):
            return float(node["height"])
        return width / image_ratio(_img_path(node))
    if t == "shape":
        if node.get("kind") == "oval":
            return float(node.get("size", min(width, 56)))
        return width * 0.5  # chevron / arrow
    if t == "richcard":
        pad = node.get("padding", 24)
        inner = width - 2 * pad
        h = 2 * pad
        for i, b in enumerate(node.get("blocks", [])):
            h += leaf_text_h(b, inner) + (10 if i else 0)
        return h
    if t == "chart":
        return min(width * 0.52, 460)
    if t == "text":
        return leaf_text_h(node, width)
    if t == "kpi":
        return kpi_h(node, width)
    # container
    p = node.get("padding", 16)
    gap = node.get("gap", 24)
    kids = node.get("children", [])
    cw = width - 2 * p
    if node.get("layout", "rows") == "rows":
        total = 2 * p
        for i, k in enumerate(kids):
            total += hug_h(k, cw) + (gap if i else 0)
        return total
    widths = alloc_widths(cw, kids, gap)
    inner = max((hug_h(k, wd) for k, wd in zip(kids, widths)), default=0)
    return 2 * p + inner


def hug_w(node, height):
    """One-line intrinsic width for text-like leaves in cols."""
    if node["t"] == "text":
        size = node.get("size", 20)
        return min(sum(char_w(c, size) for c in node.get("text", "")), 1160)
    if node["t"] == "kpi":
        return sum(char_w(c, node.get("vsize", node.get("size", 96)))
                   for c in str(node.get("value", "")))
    return 0.0


def alloc_widths(cw, kids, gap):
    fixed, flex_idx = {}, []
    for i, k in enumerate(kids):
        if "width" in k:
            fixed[i] = float(k["width"])
        elif k.get("flex"):
            flex_idx.append((i, float(k["flex"])))
        elif k["t"] in CONTAINERS or k["t"] in ("chart", "image", "richcard"):
            flex_idx.append((i, 1.0))  # implicit equal split
    free = cw - sum(fixed.values()) - gap * max(0, len(kids) - 1)
    total_flex = sum(f for _, f in flex_idx)
    widths = [0.0] * len(kids)
    for i, w in fixed.items():
        widths[i] = w
    for i, f in flex_idx:
        widths[i] = max(0.0, free * f / total_flex) if total_flex else 0.0
    for i, k in enumerate(kids):
        if i not in fixed and not any(ix == i for ix, _ in flex_idx):
            widths[i] = hug_w(k, 0)  # hugging text leaf
    return widths


def place(node, x, y, w, h):
    """Assign rect to node and lay out its children within the fixed rect."""
    node["_rect"] = [round(x, 1), round(y, 1), round(w, 1), round(h, 1)]
    t = node["t"]

    if t == "text":
        node["_lines"] = wrap_lines(node.get("text", ""), node.get("size", 20),
                                    max(w, 1))
        node["_content_h"] = round(leaf_text_h(node, w), 1)
        node["_content_w"] = round(
            min(sum(char_w(c, node.get("size", 20)) for c in node.get("text", "")),
                w), 1)
        return
    if t == "kpi":
        node["_content_h"] = round(kpi_h(node, w), 1)
        return
    if t in ("chart", "divider", "spacer", "image", "shape", "richcard"):
        return

    p = node.get("padding", 16)
    gap = node.get("gap", 24)
    kids = node.get("children", [])
    cx, cy = x + p, y + p
    cw, ch = w - 2 * p, h - 2 * p
    direction = node.get("layout", "rows")

    if not kids:
        node["_rect"][3] = round(2 * p, 1)
        return

    if direction == "rows":
        fixed_h, flex_idx = [], []
        for i, k in enumerate(kids):
            if k["t"] == "spacer" or k.get("flex"):
                flex_idx.append((i, float(k.get("flex", 1))))
            else:
                fixed_h.append((i, hug_h(k, cw)))
        used = sum(hh for _, hh in fixed_h) + gap * (len(kids) - 1)
        free = ch - used
        heights = [0.0] * len(kids)
        for i, hh in fixed_h:
            heights[i] = hh
        tf = sum(f for _, f in flex_idx)
        for i, f in flex_idx:
            heights[i] = max(0.0, free * f / tf) if tf and free > 0 else 0.0
        oy = cy
        for k, kh in zip(kids, heights):
            kw = float(k["width"]) if "width" in k else cw
            kx = cx if "width" not in k else cx + (cw - kw) * {
                "left": 0, "center": 0.5, "right": 1.0
            }.get(k.get("align", "left"), 0)
            place(k, kx, oy, kw, kh)
            oy += kh + gap
    else:  # cols
        widths = alloc_widths(cw, kids, gap)
        ox = cx
        for k, kw in zip(kids, widths):
            stretch = k["t"] in CONTAINERS or k["t"] in (
                "chart", "kpi", "image", "richcard")
            if stretch and k["t"] in ("card", "box"):
                k["_stretch"] = True
            kh = ch if stretch else hug_h(k, kw)
            place(k, ox, cy, kw, kh)
            ox += kw + gap


# ---- freeform canvas ---------------------------------------------------------

def _assign_rect(node, x, y, w, h):
    """Assign an absolute rect to ONE node (no recursive flex sizing).

    Freeform slides describe geometry explicitly, so we only need the leaf
    bookkeeping that lint/compiler/debug_render expect (_lines, _content_h).
    """
    node["_rect"] = [round(x, 1), round(y, 1), round(w, 1), round(h, 1)]
    t = node["t"]
    if t == "text":
        node["_lines"] = wrap_lines(node.get("text", ""), node.get("size", 20),
                                    max(w, 1))
        node["_content_h"] = round(leaf_text_h(node, w), 1)
        node["_content_w"] = round(
            min(sum(char_w(c, node.get("size", 20)) for c in node.get("text", "")),
                w), 1)
    elif t == "kpi":
        node["_content_h"] = round(kpi_h(node, w), 1)
    elif t == "richcard":
        node["_content_h"] = round(hug_h(node, w), 1)
    return node


def _place_free(node, ox=0.0, oy=0.0):
    """Place a freeform node; child rects are LOCAL to the parent's rect."""
    r = node.get("rect")
    if not (isinstance(r, (list, tuple)) and len(r) == 4):
        node["_freeform_error"] = "missing rect [x,y,w,h]"
        return _assign_rect(node, ox, oy, 0, 0)
    x, y, w, h = ox + float(r[0]), oy + float(r[1]), float(r[2]), float(r[3])
    _assign_rect(node, x, y, w, h)
    for kid in node.get("children", []):
        _place_free(kid, x, y)
    return node


# ---- slide skeleton ----------------------------------------------------------

def layout_slide(slide):
    from . import themes as _themes
    sem = _themes.get_active()["semantic"]
    stype = slide.get("type", "content")
    bg = slide.get("background") or {}

    if slide.get("composition") == "freeform":
        # No imposed skeleton: no auto title, no rule, no footer band.
        # Every element carries its own absolute rect; the art-direction layer
        # decides the composition instead of a master template.
        dark = slide.get("tone", "light") == "dark" \
            or stype in ("cover", "section", "closing")
        fill = slide.get("surface") or (
            sem["surface_dark"] if dark else sem["surface_light"])
        kids = slide.get("children", [])
        root = {"t": "slide", "stype": stype, "dark": dark,
                "composition": "freeform", "fill": fill,
                "bg_image": bg.get("image"), "bg_overlay": bg.get("overlay"),
                "layout": "rows", "padding": 0, "gap": 0, "children": kids}
        root["_rect"] = [0, 0, CANVAS_W, CANVAS_H]
        for child in kids:
            _place_free(child, 0, 0)
        slide["_root"] = root
        return

    dark = stype in ("cover", "section", "closing")
    root = {"t": "slide", "stype": stype, "dark": dark,
            "fill": sem["surface_dark"] if dark else sem["surface_light"],
            "bg_image": bg.get("image"),
            "bg_overlay": bg.get("overlay"),
            "layout": "rows", "padding": 0, "gap": 0, "children": []}

    if dark:
        wrap = {"t": "box", "layout": "rows", "gap": slide.get("gap", 32),
                "padding": PAD, "role": "system",
                "children": slide.get("children", [])}
        root["children"] = [wrap]
        place(root, 0, 0, CANVAS_W, CANVAS_H)
        slide["_root"] = root
        return

    # light slide: fixed title / content / footer geometry
    top = PAD
    if slide.get("title"):
        tnode = {"t": "text", "text": slide["title"],
                 "size": slide.get("title_size", 34), "weight": "bold",
                 "color": sem["ink"], "role": "title"}
        place(tnode, PAD, top, 1160, leaf_text_h(tnode, 1160))
        root.setdefault("_float", []).append(tnode)
        top = tnode["_rect"][1] + tnode["_rect"][3] + 10
        dnode = {"t": "divider", "color": sem["ink"], "role": "title"}
        place(dnode, PAD, top, 1160, 1.5)
        root["_float"].append(dnode)
        top += 1.5 + 12

    content = {"t": "box", "layout": slide.get("layout", "rows"),
               "gap": slide.get("gap", 32), "padding": 0, "role": "region",
               "children": slide.get("children", [])}
    place(content, PAD, top, 1160, CONTENT_BOTTOM - top)
    root["children"].append(content)

    footer = slide.get("footer")
    if footer:
        fy = 670
        if footer.get("source"):
            sn = {"t": "text", "text": footer["source"], "size": 14,
                  "color": sem["muted"], "role": "footer"}
            place(sn, PAD, fy, 900, leaf_text_h(sn, 900))
            root.setdefault("_float", []).append(sn)
        pn = {"t": "text", "text": str(footer.get("page", "")), "size": 14,
              "color": sem["muted"], "align": "right", "role": "footer"}
        place(pn, 1120, fy, 100, leaf_text_h(pn, 100))
        root.setdefault("_float", []).append(pn)

    # light slides use fixed skeleton geometry; do NOT re-layout through root
    root["_rect"] = [0, 0, CANVAS_W, CANVAS_H]
    slide["_root"] = root


def layout_deck(deck):
    from . import themes as _themes
    from . import typography as _typo
    # CJK kinsoku is on by default; a deck may opt out explicitly.
    _typo.set_enabled((deck.get("typography") or {}).get("kinsoku", True))
    # activate theme for raw decks; template specs already activated in expand_deck
    _themes.activate(deck)
    for slide in deck["slides"]:
        layout_slide(slide)
    return deck
