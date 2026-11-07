"""Deterministic layout lint. Produces diagnostics; ok = no error-level issues."""

import json
import os

from . import layout as layout_mod
from . import themes as _themes
from .layout import CANVAS_W, CANVAS_H, PAD, _img_path


def _load_ledger(deck):
    base = deck.get("assets_base") or layout_mod.ASSETS_BASE
    if not base:
        return {"images": []}
    path = os.path.join(base, "sources.json")
    if not os.path.exists(path):
        return {"images": []}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"images": []}

SAFE_X1, SAFE_Y1, SAFE_X2, SAFE_Y2 = PAD, PAD, CANVAS_W - PAD, CANVAS_H - PAD
ALLOWED_GAPS = {24, 32}
ALLOWED_TITLE_SIZES = (32, 40)


def walk(node):
    yield node
    for k in node.get("children", []):
        yield from walk(k)
    for k in node.get("_float", []):
        yield from walk(k)


def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def _lum(hx):
    """WCAG relative luminance of a #RRGGBB color."""
    hx = str(hx).lstrip("#")
    if len(hx) != 6:
        return None
    try:
        vals = [int(hx[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    except ValueError:
        return None
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
           for v in vals]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(fg, bg):
    a, b = _lum(fg), _lum(bg)
    if a is None or b is None:
        return 99.0
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _freeform_assets(root, slide, ledger, err):
    web_files = {e["file"] for e in ledger.get("images", [])}

    def _check(node):
        if node["t"] == "image":
            if not os.path.exists(_img_path(node)):
                err("ASSET_MISSING", f"图片不存在: {node.get('src')}")
            if os.path.basename(node.get("src", "")) in web_files \
                    and not slide.get("credit") and not node.get("credit"):
                err("WEB_CREDIT", f"网图 {os.path.basename(node['src'])} 缺来源标注")
        for k in node.get("children", []):
            _check(k)
    _check(root)
    if root.get("bg_image"):
        if not os.path.exists(_img_path({"src": root["bg_image"]})):
            err("ASSET_MISSING", f"背景图不存在: {root['bg_image']}")
        if os.path.basename(root["bg_image"]) in web_files and not slide.get("credit"):
            err("WEB_CREDIT", "网图背景缺来源标注")


def _lint_freeform_slide(slide, s_idx, th, ledger):
    """Freeform rules: geometry, legibility, color self-consistency.

    Deliberately NOT the master-template doctrines (safe area, fixed gaps,
    bottom density, 32–40px titles) — those are what made every page identical.
    The hard gate stays: overflow, missing rects, contrast and palette still
    block the build.
    """
    errs, warns = [], []
    root = slide["_root"]
    nodes = list(walk(root))
    leaves = [n for n in nodes if n["t"] in (
        "text", "kpi", "chart", "divider", "image", "shape", "richcard")]

    def err(code, msg): errs.append({"slide": s_idx + 1, "code": code, "msg": msg})
    def warn(code, msg): warns.append({"slide": s_idx + 1, "code": code, "msg": msg})

    for n in nodes:
        if n.get("_freeform_error"):
            err("FREEFORM_RECT", f"{n['t']} {n['_freeform_error']}")

    for n in leaves:
        x, y, w, h = n["_rect"]
        if n.get("bleed"):
            continue
        if x < -0.5 or y < -0.5 or x + w > CANVAS_W + 0.5 \
                or y + h > CANVAS_H + 0.5:
            err("OUT_OF_CANVAS", f"{n['t']} 超出画布: {n['_rect']}")

    _freeform_assets(root, slide, ledger, err)

    for n in nodes:
        if n["t"] == "text" and not n.get("decor"):
            x, y, w, h = n["_rect"]
            if n.get("_content_h", 0) > h + 1.5:
                err("TEXT_OVERFLOW",
                    f"文本竖向溢出: 需{round(n['_content_h'], 1)} > 框{round(h, 1)}"
                    f" / {n.get('text', '')[:14]}")
            if n.get("size", 20) < th["min_body"]:
                err("FONT_SIZE", f"正文字号 {n.get('size')} < {th['min_body']}")
        elif n["t"] == "richcard":
            if n.get("_content_h", 0) > n["_rect"][3] + 1.5:
                err("RICHCARD_OVERFLOW",
                    f"卡片文本溢出: 需{round(n['_content_h'], 1)}"
                    f" > 框{round(n['_rect'][3], 1)}")

    # readability: any node that declares its backing color must be legible
    # (decorative display glyphs intentionally sit at low contrast)
    for n in nodes:
        on = n.get("on")
        if not on or n.get("decor"):
            continue
        fg = n.get("color") or (n.get("blocks") or [{}])[0].get("color")
        if not fg:
            continue
        r = contrast_ratio(fg, on)
        big = n.get("size", 20) >= 28 or any(
            b.get("size", 18) >= 28 for b in n.get("blocks", []))
        floor = 3.0 if big else 4.5
        if r < floor:
            err("CONTRAST", f"文字对比度 {r:.2f} < {floor} ({fg} on {on})")

    # palette self-consistency (derived cover palette counts as a real palette)
    palette = th["palette"]
    if palette:
        used = set()
        for n in nodes:
            for key in ("color", "fill", "border", "text_color", "lcolor", "on"):
                if n.get(key):
                    used.add(str(n[key]).upper())
            if n["t"] == "richcard":
                used |= {b.get("color", "").upper()
                         for b in n.get("blocks", []) if b.get("color")}
            if n["t"] == "chart":
                used |= {c.upper() for c in n.get("colors", [])}
        illegal = {c for c in used if c.startswith("#") and c not in palette}
        if illegal:
            err("PALETTE", f"颜色不在派生调色板: {sorted(illegal)}")

    # heavy overlap between two text-bearing shapes is suspicious, not fatal
    texty = [n for n in nodes if n["t"] == "text" and not n.get("decor")]
    for i, a in enumerate(texty):
        for b in texty[i + 1:]:
            ra, rb = a["_rect"], b["_rect"]
            if not rects_overlap(ra, rb):
                continue
            ix = max(0, min(ra[0] + ra[2], rb[0] + rb[2]) - max(ra[0], rb[0]))
            iy = max(0, min(ra[1] + ra[3], rb[1] + rb[3]) - max(ra[1], rb[1]))
            small = min(ra[2] * ra[3], rb[2] * rb[3]) or 1
            if ix * iy / small > 0.5:
                warn("TEXT_OVERLAP", "两个文本节点重叠超过 50%")
    return errs, warns


def lint_slide(slide, s_idx, sc, ledger=None):
    ledger = ledger or {"images": []}
    errs, warns = [], []
    root = slide["_root"]
    if root.get("composition") == "freeform":
        return _lint_freeform_slide(slide, s_idx, sc, ledger)
    stype = root["stype"]
    dark = root["dark"]
    nodes = list(walk(root))
    leaves = [n for n in nodes if n["t"] in (
        "text", "kpi", "chart", "divider", "image", "shape", "richcard")]

    def err(code, msg): errs.append({"slide": s_idx + 1, "code": code, "msg": msg})
    def warn(code, msg): warns.append({"slide": s_idx + 1, "code": code, "msg": msg})

    # 1. canvas bounds
    for n in leaves:
        x, y, w, h = n["_rect"]
        if x < 0 or y < 0 or x + w > CANVAS_W or y + h > CANVAS_H:
            err("OUT_OF_CANVAS", f"{n['t']} 超出画布: {n['_rect']}")

    # 1b. image assets must exist; web-sourced images must be credited on slide
    web_files = {e["file"] for e in ledger.get("images", [])}

    def _check_assets(node):
        if node["t"] == "image":
            p = _img_path(node)
            if not os.path.exists(p):
                err("ASSET_MISSING", f"图片不存在: {node.get('src')}")
            if os.path.basename(node.get("src", "")) in web_files \
                    and not (slide.get("footer") or {}).get("source") \
                    and not node.get("credit"):
                err("WEB_CREDIT", f"网图 {os.path.basename(node['src'])} 缺来源标注")
        for k in node.get("children", []):
            _check_assets(k)
    _check_assets(root)
    if root.get("bg_image"):
        if not os.path.exists(_img_path({"src": root["bg_image"]})):
            err("ASSET_MISSING", f"背景图不存在: {root['bg_image']}")
        if os.path.basename(root["bg_image"]) in web_files \
                and not (slide.get("footer") or {}).get("source"):
            err("WEB_CREDIT", "网图背景缺来源标注")

    # 2. safe area on light slides (footer band exempt)
    if not dark:
        for n in leaves:
            x, y, w, h = n["_rect"]
            role = n.get("role")
            if role == "footer":
                if not (SAFE_Y2 + 10 <= y <= CANVAS_H - 20):
                    err("FOOTER_POS", f"页脚位置异常: y={y}")
                continue
            if x < SAFE_X1 - 0.5 or y < SAFE_Y1 - 0.5 or x + w > SAFE_X2 + 0.5:
                err("SAFE_AREA", f"{n['t']} 越过安全区: {n['_rect']}")

    # 3. text overflow inside its own box
    for n in nodes:
        if n["t"] == "text":
            x, y, w, h = n["_rect"]
            if n.get("_content_h", 0) > h + 1.5:
                err("TEXT_OVERFLOW",
                    f"文本竖向溢出: 需{round(n['_content_h'],1)} > 框{round(h,1)} / {n.get('text','')[:14]}")
            if not n.get("wrap", True) and n.get("_content_w", 0) > w + 0.5:
                err("TEXT_OVERFLOW", "文本横向溢出(未换行)")

    # 4. font sizes by role
    for n in nodes:
        if n["t"] != "text":
            continue
        s = n.get("size", 20)
        role = n.get("role")
        if role == "title":
            if not (ALLOWED_TITLE_SIZES[0] <= s <= ALLOWED_TITLE_SIZES[1]):
                err("TITLE_SIZE", f"页标题字号 {s} 不在 32–40")
            txt = n.get("text", "")
            if len(txt) > 30:
                err("TITLE_LEN", f"标题超 30 字: {len(txt)}")
            # heuristic for Action Title: a bare short noun tag is suspicious
            if len(txt.strip()) < 6 and stype != "toc":
                warn("ACTION_TITLE", "标题疑似关键词而非结论句")
        elif role == "footer":
            if not (14 <= s <= 16):
                err("FOOTER_SIZE", f"页脚字号 {s} 不在 14–16")
        else:
            if s < sc["min_body"]:
                err("BODY_SIZE", f"正文字号 {s} < 下限 {sc['min_body']}")

    # 5. gap discipline
    # region root must use 24/32; system wrappers are exempt; transparent
    # inner boxes may use 0 for tight title+summary packing; visible cards 24/32.
    for n in nodes:
        if n["t"] not in ("box", "card") or not n.get("children"):
            continue
        role = n.get("role")
        if role == "system":
            continue
        g = n.get("gap", 24)
        visible = n.get("fill") or n.get("border") or n["t"] == "card"
        if role == "region" or visible:
            if g not in ALLOWED_GAPS:
                err("GAP", f"间距 {g} 非 24/32")
        elif g not in (0, 8, 12, 14, 16, 20, 24, 32):
            err("GAP", f"间距 {g} 不在内部紧排档位")

    # 6. palette
    palette = sc["palette"]
    if palette:
        used = set()
        for n in nodes:
            for key in ("color", "fill", "border", "text_color", "lcolor"):
                if n.get(key):
                    used.add(n[key].upper())
            if n["t"] == "richcard":
                used |= {b.get("color", "").upper() for b in n.get("blocks", []) if b.get("color")}
            if n["t"] == "chart":
                used |= {c.upper() for c in n.get("colors", [])}
        illegal = {c for c in used if c not in palette}
        if illegal:
            err("PALETTE", f"颜色不在 scenario 调色板: {sorted(illegal)}")

    # 7. structure: regions <= 4 on content slides
    if stype == "content":
        # count direct children of the content flex box
        content_box = next((n for n in nodes
                            if n.get("t") == "box" and any(
                                c.get("role") is None for c in n.get("children", []))
                            and n.get("layout") in ("rows", "cols")), None)
        if content_box and len(content_box.get("children", [])) > 4:
            err("REGIONS", "区域数 > 4")

    # 8. density on light non-special slides (bottom gap)
    if not dark and stype not in ("toc",) and not slide.get("sparse"):
        # prefer visible containers (cards / filled boxes / charts); else leaves
        visible = [n for n in nodes
                   if n["t"] == "chart" or n["t"] == "card"
                   or (n["t"] == "box" and n.get("fill"))]
        pool = visible if visible else [n for n in leaves
                                        if n.get("role") not in ("title", "footer")
                                        and n["t"] != "divider"]
        if pool:
            bottom = max(n["_rect"][1] + n["_rect"][3] for n in pool)
            gap_bottom = SAFE_Y2 - bottom
            if gap_bottom > 45:
                err("DENSITY", f"底部留白 {round(gap_bottom)}px > 45，需补内容或合并页")

    # 9. credibility: chart needs Source; card char minimums
    if any(n["t"] == "chart" for n in nodes):
        if not slide.get("footer", {}).get("source"):
            err("SOURCE", "图表页缺少 Source/Footnote")

    for n in nodes:
        if n["t"] != "card":
            continue
        h = n["_rect"][3]
        chars = sum(len(t.get("text", "")) for t in walk(n) if t["t"] == "text")
        if n.get("_stretch"):
            # equal-height card row: per-card floor 40 chars
            if chars < 40:
                err("CARD_CHARS", f"卡片仅 {chars} 字，需≥40")
        elif h >= 480 and chars < 130:
            err("CARD_CHARS", f"高卡片仅 {chars} 字，需≥130")
        elif h >= 380 and chars < 100:
            err("CARD_CHARS", f"高卡片仅 {chars} 字，需≥100")

    # 10. footer forbidden on special slides
    if stype in sc["no_footer"] and slide.get("footer"):
        err("FOOTER_FORBIDDEN", f"{stype} 页不应有页脚")

    return errs, warns


def lint_deck(deck):
    th = _themes.activate(deck)
    ledger = _load_ledger(deck)
    all_err, all_warn = [], []
    for i, slide in enumerate(deck["slides"]):
        e, w = lint_slide(slide, i, th, ledger)
        all_err += e
        all_warn += w

    # CJK kinsoku guard. wrap_lines() repairs line breaks at stage 3; this
    # catches hand-written _lines, opted-out decks, and future regressions.
    from . import typography as _typo
    if (deck.get("typography") or {}).get("kinsoku", True):
        for i, slide in enumerate(deck["slides"]):
            root = slide.get("_root")
            if not root:
                continue
            for n in walk(root):
                if n.get("t") != "text":
                    continue
                lines = n.get("_lines") or []
                for li, code, ch in _typo.find_kinsoku_violations(lines):
                    all_err.append({
                        "slide": i + 1, "code": "CJK_KINSHOKU",
                        "msg": f"第 {li + 1} 行禁则 {code}（字符「{ch}」）："
                               f"避头尾规则要求换行处不得出现该标点"})
                    break

    # Composed decks must not fall back into "one template, N pages".
    # A repeated layout is now a build-blocking defect, not a taste complaint.
    if deck.get("composed"):
        slides = deck["slides"]
        arch = [s.get("archetype") for s in slides]

        def derr(code, msg): all_err.append({"slide": 0, "code": code, "msg": msg})
        def dwarn(code, msg): all_warn.append({"slide": 0, "code": code, "msg": msg})

        for i, a in enumerate(arch):
            if not a:
                derr("COMPOSED_METADATA", f"第 {i + 1} 页缺 archetype 标记")
            elif i and a == arch[i - 1]:
                derr("LAYOUT_REPETITION",
                     f"第 {i}、{i + 1} 页构图原型相同（{a}），相邻页必须换版式")
        uniq = len({a for a in arch if a})
        need = max(3, (len(arch) + 1) // 2)
        if uniq < need:
            derr("LAYOUT_VARIETY",
                 f"仅 {uniq} 种构图原型，{len(arch)} 页至少需要 {need} 种")
        dens = [s.get("density", "mid") for s in slides]
        if len(dens) >= 4 and len(set(dens)) < 2:
            dwarn("DENSITY_FLAT", "全篇密度一致，缺少疏密节奏")
    return {"ok": len(all_err) == 0, "errors": all_err, "warnings": all_warn}
