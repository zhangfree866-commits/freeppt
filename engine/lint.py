"""Deterministic layout lint. Produces diagnostics; ok = no error-level issues."""

import json
import os
import re

from . import layout as layout_mod
from . import themes as _themes
from . import icons as _icons
from .compiler import SHAPE_KINDS
from .layout import CANVAS_W, CANVAS_H, PAD, _img_path, char_w


def _gradient_colors(node):
    """All stop colors declared by a node's gradient (uppercased hex)."""
    grad = node.get("gradient")
    if not grad:
        return []
    return [str(st.get("color", "")).lstrip("#").upper()
            for st in grad.get("stops", []) if st.get("color")]


# Shadow levels accepted by compiler.SHADOW_PRESETS. Booleans are also legal
# (True -> soft, False -> none); None means "inherit the theme token".
SHADOW_LEVELS = {"none", "soft", "medium"}


# --- Severity tiers ---------------------------------------------------------
# Three tiers, mirroring the acceptance language a finished deck is signed off
# in: "0 blocking errors, N non-blocking notes (intentional whitespace)".
#
#   blocker   a hard defect. The build is refused until the source is fixed;
#             no acknowledgement can suppress it.
#   advisory  a detector's suspicion that needs a human call. The geometric
#             checks are estimates and *do* produce false positives, so this
#             tier is explicitly adjudicable via `lint_ack`.
#   info      a measured fact requiring no action (e.g. an ack that matched
#             nothing because the issue was already fixed).
#
# `errors` / `warnings` keep their historical meaning so every existing caller
# and test stays correct: warnings lists every advisory that has NOT been
# adjudicated yet.
SEVERITY_BLOCKER = "blocker"
SEVERITY_ADVISORY = "advisory"
SEVERITY_INFO = "info"

# Warning codes that are pure measurements rather than judgements.
INFO_CODES = frozenset({"LINT_ACK_UNUSED"})

# Warning codes that a human may legitimately adjudicate as intentional.
# Anything not listed here and not in INFO_CODES defaults to advisory too, so
# a newly added warning is adjudicable without touching this table.
BLOCKING_CODES = frozenset({
    "ASSET_MISSING", "CJK_KINSHOKU", "COMPOSED_METADATA", "CONTRAST",
    "FOOTER_POS", "FONT_SIZE", "FREEFORM_RECT", "GRID_COLUMN", "ICON_NAME",
    "LAYOUT_REPETITION", "LAYOUT_VARIETY", "NOTES_COVERAGE", "OUT_OF_CANVAS",
    "PALETTE", "RESEARCH_LEDGER", "RICHCARD_OVERFLOW", "SAFE_AREA",
    "SHADOW_VALUE", "SHAPE_KIND", "TABLE_SHAPE", "TEXT_OVERFLOW",
    "WEB_CREDIT",
})


def severity_of(code, is_error):
    """Tier of a diagnostic code. Errors are always blockers."""
    if is_error:
        return SEVERITY_BLOCKER
    if code in INFO_CODES:
        return SEVERITY_INFO
    return SEVERITY_ADVISORY


def _apply_acks(warns, acks, blocker_codes):
    """Split warnings into adjudicated (`acked`) and still open.

    An ack is a record that a human looked at one specific advisory and
    decided it was intentional. Three rules make it an adjudication rather
    than a mute button:

    * a written `reason` is mandatory — a bare suppression is rejected;
    * only advisories can be acked; a blocker is fixed at the source, and an
      ack aimed at one is reported back as a complaint;
    * an ack that matches nothing is reported as info, so stale adjudications
      surface instead of silently accumulating.

    Returns (kept, acked, complaints).
    """
    valid, complaints = [], []
    for ack in acks or []:
        if not isinstance(ack, dict):
            complaints.append({"slide": 0, "code": "LINT_ACK_INVALID",
                               "msg": f"lint_ack 条目必须是对象，收到 {type(ack).__name__}"})
            continue
        code = str(ack.get("code") or "").strip()
        reason = str(ack.get("reason") or "").strip()
        if not code:
            complaints.append({"slide": 0, "code": "LINT_ACK_INVALID",
                               "msg": "lint_ack 条目缺少 code"})
            continue
        if not reason:
            complaints.append({
                "slide": 0, "code": "LINT_ACK_INVALID",
                "msg": f"lint_ack「{code}」缺少 reason：裁定必须写明为何它不是问题"})
            continue
        if code in blocker_codes:
            complaints.append({
                "slide": 0, "code": "LINT_ACK_ON_BLOCKER",
                "msg": f"lint_ack 不能豁免阻断错误「{code}」："
                       "阻断项必须修源头（改 DSL / 补内容），不能靠裁定放过"})
            continue
        valid.append((code, ack.get("slide"), reason))

    kept, acked, used = [], [], set()
    for w in warns:
        hit = None
        for idx, (code, slide, reason) in enumerate(valid):
            if w["code"] != code:
                continue
            if slide in (None, 0, ""):
                hit = (idx, reason)
                break
            try:
                same_slide = int(slide) == int(w["slide"])
            except (TypeError, ValueError):
                same_slide = False
            if same_slide:
                hit = (idx, reason)
                break
        if hit:
            used.add(hit[0])
            rec = dict(w)
            rec["acked_reason"] = hit[1]
            acked.append(rec)
        else:
            kept.append(w)

    for idx, (code, slide, reason) in enumerate(valid):
        if idx not in used:
            scope = f"第 {slide} 页" if slide not in (None, 0, "") else "全篇"
            complaints.append({
                "slide": 0, "code": "LINT_ACK_UNUSED",
                "msg": f"lint_ack「{code}」({scope}) 未匹配任何诊断，"
                       "可能已修复或 code 拼写有误，建议清理"})
    return kept, acked, complaints


def _shadow_invalid(node):
    """True when a node explicitly declares an unsupported shadow value."""
    raw = node.get("shadow")
    if raw is None or isinstance(raw, bool):
        return False
    return not (isinstance(raw, str) and raw in SHADOW_LEVELS)


def _visible_chars(slide):
    """Count non-decorative on-slide characters (text + richcard blocks)."""
    total = 0
    for node in walk(slide["_root"]):
        if node.get("decor"):
            continue
        if node.get("t") == "text":
            total += len("".join(str(node.get("text", "")).split()))
        elif node.get("t") == "richcard":
            for b in node.get("blocks", []):
                total += len("".join(str(b.get("text", "")).split()))
    return total


# Archetypes where low word count is intentional, not a density defect.
DENSITY_EXEMPT = {
    "cover-editorial", "chapter-opener", "closing-echo", "quote-bleed",
    "chart-story", "table-board",
}


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


# --- Freeform geometric-integrity thresholds (all warning-level) -----------
# Two visible surfaces closer than this (but not overlapping) read as a
# near-touch / tangent: visually "sticky" rather than deliberately spaced.
GEOMETRY_NEAR_GAP = 8.0
# A single-line label whose glyph run fills more than this fraction of its box
# is one font-metric nudge away from an unintended wrap. Multi-line body text
# is intentionally excluded: filling the line width is good paragraph setting.
TIGHT_WIDTH_RATIO = 0.98
# Hand-authored line weights live in this Pt band. The engine itself draws thin
# rules (divider default 1.25, icon stroke 1.75), so this is a sanity range, not
# an integer constraint.
LINE_WIDTH_MIN, LINE_WIDTH_MAX = 0.5, 6.0
# Node types that paint a visible surface and therefore participate in
# collision checks (text-only nodes are covered by TEXT_OVERLAP instead).
GEOMETRY_SURFACE_TYPES = (
    "shape", "richcard", "image", "card", "box", "kpi", "chart", "table")


def _parent_map(root):
    """Map id(node) -> its parent node across children and _float floats."""
    pmap = {}

    def rec(node, parent):
        pmap[id(node)] = parent
        for k in node.get("children", []):
            rec(k, node)
        for k in node.get("_float", []):
            rec(k, node)
    rec(root, None)
    return pmap


def _is_ancestor(maybe_ancestor, node, pmap):
    cur = pmap.get(id(node))
    while cur is not None:
        if cur is maybe_ancestor:
            return True
        cur = pmap.get(id(cur))
    return False


def _has_surface(node):
    return bool(node.get("fill") or node.get("gradient") or node.get("border"))


def _is_background_slab(node):
    """An edge-to-edge band is structural background (split-contrast panels,

    full-bleed strips), not a floating shape, so its intentional seams are
    exempt from collision/near-touch checks."""
    x, y, w, h = node.get("_rect", [0, 0, 0, 0])
    return h >= CANVAS_H - 1.0 or w >= CANVAS_W - 1.0


def _line_width_invalid(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return True
    return not (LINE_WIDTH_MIN <= float(value) <= LINE_WIDTH_MAX)


def _geometry_integrity(root, warn):
    """Near-touch / overlap, line-weight range, and tight single-line width.

    Mirrors the manual QA pass a designer runs on hand-drawn freeform slides.
    Every diagnostic is a warning: layout already guarantees hard bounds and
    text fit, so these flag taste-level collision risk without blocking build.
    Native charts/tables render themselves and are only checked for placement
    collisions, never for internal glyph geometry.
    """
    pmap = _parent_map(root)
    pool = [n for n in walk(root)
            if n.get("t") in GEOMETRY_SURFACE_TYPES
            and _has_surface(n)
            and not n.get("decor") and not n.get("bleed")
            and not _is_background_slab(n)
            # data-viz foreground marks (line markers, data-label pills) are
            # meant to sit on top of bars/points, so they opt out of collision
            # checks while still bounded, palette- and contrast-checked.
            and n.get("role") != "data-marker"
            and n.get("_rect") and n["_rect"][2] > 0 and n["_rect"][3] > 0]

    for i, a in enumerate(pool):
        ra = a["_rect"]
        for b in pool[i + 1:]:
            # nested parent/child surfaces are deliberate containment
            if _is_ancestor(a, b, pmap) or _is_ancestor(b, a, pmap):
                continue
            rb = b["_rect"]
            if rects_overlap(ra, rb):
                warn("GEOMETRY_OVERLAP",
                     f"两个可见形状非嵌套压盖: {a['t']}{ra} 与 {b['t']}{rb}")
                continue
            ax, ay, aw, ah = ra
            bx, by, bw, bh = rb
            gap_x = (bx - (ax + aw)) if ax + aw <= bx else (ax - (bx + bw))
            gap_y = (by - (ay + ah)) if ay + ah <= by else (ay - (by + bh))
            overlap_x = ax < bx + bw and bx < ax + aw
            overlap_y = ay < by + bh and by < ay + ah
            if overlap_x and 0 <= gap_y < GEOMETRY_NEAR_GAP:
                warn("GEOMETRY_NEAR_TOUCH",
                     f"两形状竖向近距相切(间隙 {round(gap_y, 1)}px"
                     f" < {GEOMETRY_NEAR_GAP:g}): {a['t']} 与 {b['t']}")
            elif overlap_y and 0 <= gap_x < GEOMETRY_NEAR_GAP:
                warn("GEOMETRY_NEAR_TOUCH",
                     f"两形状横向近距相切(间隙 {round(gap_x, 1)}px"
                     f" < {GEOMETRY_NEAR_GAP:g}): {a['t']} 与 {b['t']}")

    for n in walk(root):
        if n.get("t") == "divider":
            thickness = n.get("thickness", 1.25)
            if _line_width_invalid(thickness):
                warn("LINE_WIDTH_VALUE",
                     f"divider thickness={thickness!r} 非法，"
                     f"需为 {LINE_WIDTH_MIN:g}–{LINE_WIDTH_MAX:g}pt 数值")
        elif n.get("t") == "line":
            thickness = n.get("thickness", n.get("stroke_w", 2))
            if _line_width_invalid(thickness):
                warn("LINE_WIDTH_VALUE",
                     f"line thickness={thickness!r} 非法，"
                     f"需为 {LINE_WIDTH_MIN:g}–{LINE_WIDTH_MAX:g}pt 数值")
        elif n.get("t") == "icon" and n.get("stroke_w") is not None:
            if _line_width_invalid(n["stroke_w"]):
                warn("LINE_WIDTH_VALUE",
                     f"icon stroke_w={n['stroke_w']!r} 非法，"
                     f"需为 {LINE_WIDTH_MIN:g}–{LINE_WIDTH_MAX:g}pt 数值")
        elif n.get("t") == "text" and not n.get("decor") \
                and n.get("wrap", True):
            lines = n.get("_lines") or []
            w = n["_rect"][2]
            if w > 0 and len(lines) == 1:
                size = n.get("size", 20)
                glyph_w = sum(char_w(c, size) for c in lines[0])
                if glyph_w / w > TIGHT_WIDTH_RATIO:
                    warn("TEXT_TIGHT_WIDTH",
                         f"单行标签宽度占框 {round(glyph_w / w * 100)}%，"
                         "接近换行临界，建议加宽文本框或缩短文案")


# --- Closing-consistency gate (deck-level, warning-level) ------------------
# Residual markers a finished deck must not still carry on stage. These are
# deterministic patterns; speaker notes are deliberately excluded (working
# notes may legitimately contain TODO-style prompts).
PLACEHOLDER_PATTERNS = (
    re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b", re.IGNORECASE),
    re.compile(r"\{\{.*?\}\}|\$\{.*?\}", re.DOTALL),
    re.compile(r"placeholder|lorem\s+ipsum|待补充|待填|占位|示例文字",
               re.IGNORECASE),
    # a raw hex color leaking into prose is almost always a copy-paste slip
    re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b"),
)


def _visible_texts(root):
    """On-stage, non-decorative strings that the audience actually reads."""
    for n in walk(root):
        if n.get("decor"):
            continue
        t = n.get("t")
        if t == "text" and isinstance(n.get("text"), str):
            yield n["text"]
        elif t == "kpi":
            for key in ("value", "label"):
                if isinstance(n.get(key), str):
                    yield n[key]
        elif t == "richcard":
            for block in n.get("blocks", []):
                if isinstance(block.get("text"), str):
                    yield block["text"]
        elif t == "shape" and isinstance(n.get("text"), str):
            yield n["text"]


def _closing_gate(deck, all_warn):
    """Page-number order and residual placeholder/debug markers.

    Runs once per deck after per-slide lint so it can reason across slides.
    Warning-level: catches hand-authoring slips without blocking a build.
    """
    slides = deck["slides"]
    for i, slide in enumerate(slides, start=1):
        footer = slide.get("footer")
        if not footer:
            continue
        page = footer.get("page")
        if page is None or not str(page).strip():
            continue
        digits = re.findall(r"\d+", str(page))
        # A footer page token is expected to carry the slide's 1-based ordinal.
        # Formats like "3", "03 / 12", "第3页" all expose it via digit groups;
        # compare on integers so leading zeros ("01") still match slide 1.
        nums = {int(d) for d in digits}
        if not nums or i not in nums:
            all_warn.append({
                "slide": i, "code": "PAGE_NUMBER",
                "msg": f"页脚页码 {page!r} 与实际页序 {i} 不一致"
                       "（检查 footer.page 是否漏改或串页）"})

    for i, slide in enumerate(slides, start=1):
        root = slide.get("_root")
        if not root:
            continue
        for text in _visible_texts(root):
            for pat in PLACEHOLDER_PATTERNS:
                hit = pat.search(text)
                if hit:
                    all_warn.append({
                        "slide": i, "code": "PLACEHOLDER_TEXT",
                        "msg": f"上台文本疑似残留占位/调试标记 {hit.group(0)!r}："
                               f"「{text[:24]}」"})
                    break  # one report per text node is enough


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
        "text", "kpi", "chart", "table", "divider", "image", "shape", "richcard",
        "icon", "line")]

    def err(code, msg): errs.append({"slide": s_idx + 1, "code": code, "msg": msg})
    def warn(code, msg): warns.append({"slide": s_idx + 1, "code": code, "msg": msg})

    for n in nodes:
        if n.get("_freeform_error"):
            err("FREEFORM_RECT", f"{n['t']} {n['_freeform_error']}")
        if n["t"] == "icon" and not _icons.resolve(n.get("name", "")):
            err("ICON_NAME", f"未知图标名: {n.get('name')!r}（见 engine.icons 库）")
        if n["t"] == "shape" and n.get("kind", "rect") not in SHAPE_KINDS:
            err("SHAPE_KIND",
                f"未知形状 kind: {n.get('kind')!r}（合法值 {sorted(SHAPE_KINDS)}）")
        if _shadow_invalid(n):
            err("SHADOW_VALUE",
                f"阴影级别非法: {n.get('shadow')!r}（合法值 none/soft/medium）")

    for n in leaves:
        x, y, w, h = n["_rect"]
        if n.get("bleed"):
            continue
        if x < -0.5 or y < -0.5 or x + w > CANVAS_W + 0.5 \
                or y + h > CANVAS_H + 0.5:
            err("OUT_OF_CANVAS", f"{n['t']} 超出画布: {n['_rect']}")

    _freeform_assets(root, slide, ledger, err)

    # Declarative column grid: col_start/col_span are honored only on top-level
    # freeform nodes and must stay inside the theme's grid_columns budget.
    grid_cols = int(th.get("visual", {}).get("grid_columns", 12) or 12)
    top_ids = {id(k) for k in root.get("children", [])}
    for n in root.get("children", []):
        start, span = n.get("col_start"), n.get("col_span")
        if start is None and span is None:
            continue
        bad_type = isinstance(start, bool) or isinstance(span, bool) \
            or (start is not None and not isinstance(start, int)) \
            or (span is not None and not isinstance(span, int))
        if bad_type:
            err("GRID_COLUMN",
                f"col_start/col_span 必须是整数: {start!r}/{span!r}")
            continue
        s, sp = (1 if start is None else start), (1 if span is None else span)
        if s < 1 or sp < 1 or s + sp - 1 > grid_cols:
            err("GRID_COLUMN",
                f"列定位越界: col_start={s} col_span={sp} 超出 {grid_cols} 列网格")
    for n in nodes:
        if id(n) not in top_ids and (n.get("col_start") is not None
                                     or n.get("col_span") is not None):
            warn("GRID_COLUMN_NESTED",
                 "嵌套节点的 col_start/col_span 会被忽略（网格仅对顶层节点生效）")

    # Native table: the DSL carries plain cells; the compiler builds the
    # table, so lint must guarantee the shape before compilation is attempted.
    for n in nodes:
        if n["t"] != "table":
            continue
        headers, rows = n.get("headers", []), n.get("rows", [])
        if not headers:
            err("TABLE_SHAPE", "表格缺少 headers")
        if not rows:
            err("TABLE_SHAPE", "表格缺少 rows")
        bad = [i + 1 for i, r in enumerate(rows) if len(r) != len(headers)]
        if bad:
            err("TABLE_SHAPE", f"第 {bad} 行列数与表头不一致（{len(headers)} 列）")

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
            for key in ("color", "fill", "border", "text_color", "lcolor", "on",
                        "knock_color"):
                if n.get(key):
                    used.add(str(n[key]).upper())
            used |= {c for c in _gradient_colors(n) if c}
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

    # Geometric integrity of hand-drawn freeform surfaces: near-touch seams,
    # non-nested overlaps, out-of-range line weights, and wrap-critical labels.
    # Warning-only so valid decks never fail; mirrors a manual designer QA pass.
    _geometry_integrity(root, warn)
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
        "text", "kpi", "chart", "table", "divider", "image", "shape", "richcard",
        "icon", "line")]

    def err(code, msg): errs.append({"slide": s_idx + 1, "code": code, "msg": msg})
    def warn(code, msg): warns.append({"slide": s_idx + 1, "code": code, "msg": msg})

    for n in nodes:
        if n["t"] == "icon" and not _icons.resolve(n.get("name", "")):
            err("ICON_NAME", f"未知图标名: {n.get('name')!r}（见 engine.icons 库）")
        if _shadow_invalid(n):
            err("SHADOW_VALUE",
                f"阴影级别非法: {n.get('shadow')!r}（合法值 none/soft/medium）")

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
            for key in ("color", "fill", "border", "text_color", "lcolor",
                        "knock_color"):
                if n.get(key):
                    used.add(n[key].upper())
            used |= {c for c in _gradient_colors(n) if c}
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

        # Chapter-aware variety: archetypes may legitimately recur across
        # chapters, so the half-pages budget applies per chapter, not to the
        # whole file. Chapter pages themselves (chapter-opener) are excluded
        # from the content budget.
        meta = deck.get("art_direction") or {}
        boundaries = meta.get("chapter_boundaries")
        if not boundaries:
            boundaries = [i for i, s in enumerate(slides)
                          if s.get("archetype") == "chapter-opener"
                          or s.get("role") == "chapter"]
        bounds = boundaries + [len(arch)]
        start = 0
        for b in bounds:
            seg = [a for j, a in enumerate(arch[start:b], start)
                   if a and a not in ("cover-editorial", "chapter-opener",
                                      "closing-echo")]
            if seg:
                uniq = len(set(seg))
                # the floor of 3 must stay satisfiable: a chapter shorter
                # than 3 content pages cannot conjure 3 distinct archetypes
                need = min(len(seg), max(3, (len(seg) + 1) // 2))
                if uniq < need:
                    derr("LAYOUT_VARIETY",
                         f"第 {start + 1}-{b} 页章节仅 {uniq} 种构图原型，"
                         f"{len(seg)} 个内容页至少需要 {need} 种；请拆分章节或增加原型")
            start = b
        dens = [s.get("density", "mid") for s in slides]
        if len(dens) >= 4 and len(set(dens)) < 2:
            dwarn("DENSITY_FLAT", "全篇密度一致，缺少疏密节奏")

        # Research ledger: a page that declares a research demand must carry
        # at least one verifiable source; the engine never researches itself.
        for i, s in enumerate(slides):
            demand = s.get("research")
            if not demand:
                continue
            sources = s.get("sources") or []
            valid = [x for x in sources
                     if isinstance(x, dict) and x.get("title")
                     and (x.get("url") or x.get("publisher"))]
            if not valid and not s.get("source"):
                all_err.append({
                    "slide": i + 1, "code": "RESEARCH_LEDGER",
                    "msg": "该页声明了 research 但没有可用来源台账"
                           "（sources 需含 title 与 url/publisher）"})
        if meta.get("long_deck_forced"):
            all_warn.append({
                "slide": 0, "code": "LONG_DECK_FORCED",
                "msg": "长 deck 护栏被 allow_long_deck 显式绕过；"
                       "build 时仍需 --force，且产物会带 FORCED_BUILD 标记"})

    # Speaker-notes coverage. Triggered by an explicit deck flag or by a
    # composed deck whose art-direction metadata promised generated scripts.
    meta = deck.get("art_direction") or {}
    require_notes = bool(deck.get("require_notes")) or (
        deck.get("composed") and meta.get("speaker_notes"))
    if require_notes:
        for i, s in enumerate(deck["slides"]):
            text = (s.get("notes") or "").strip()
            if not text:
                all_err.append({
                    "slide": i + 1, "code": "NOTES_COVERAGE",
                    "msg": "该页缺少演讲者备注（notes）；开启讲稿覆盖后每页都需有讲稿"})
            elif len(text) < 40:
                all_warn.append({
                    "slide": i + 1, "code": "NOTES_THIN",
                    "msg": f"演讲者备注仅 {len(text)} 字，建议补充到 40 字以上的完整讲稿"})

    # Content-density advisory (composed decks only, warning-level so it never
    # blocks a valid sparse page). The benchmark decks average 200+ on-slide
    # chars per content page; a thin page signals under-developed research.
    if deck.get("composed"):
        for i, s in enumerate(deck["slides"]):
            arch = s.get("archetype", "")
            if arch in DENSITY_EXEMPT:
                continue
            chars = _visible_chars(s)
            if chars < 60:
                all_warn.append({
                    "slide": i + 1, "code": "CONTENT_DENSITY",
                    "msg": f"内容页仅 {chars} 个可见字，建议结合研究台账补充阐述、"
                           "案例或数据，向页均 150-250 字的信息密度靠拢"})

    # Closing-consistency gate: page-number order and leftover placeholder /
    # debug markers in on-stage text. Warning-level and layout-agnostic.
    _closing_gate(deck, all_warn)

    # Severity tiers + human adjudication of advisories. Blockers are tagged
    # first (they can never be suppressed); the remaining warnings are split
    # into adjudicated and still-open by the deck's `lint_ack` records.
    acks = deck.get("lint_ack") or []
    if isinstance(acks, dict):          # tolerate a single record, not a list
        acks = [acks]
    open_warn, acked, ack_complaints = _apply_acks(all_warn, acks, BLOCKING_CODES)
    all_warn = open_warn

    for item in all_err:
        item["severity"] = severity_of(item["code"], True)
    for item in all_warn + ack_complaints:
        item["severity"] = severity_of(item["code"], False)
    all_warn += ack_complaints

    extras = [w for w in all_warn if w["severity"] == SEVERITY_ADVISORY]
    blockers = [e for e in all_err if e["severity"] == SEVERITY_BLOCKER]
    summary = {
        "blockers": len(blockers),
        "advisories": len(extras),
        "infos": len([w for w in all_warn if w["severity"] == SEVERITY_INFO]),
        "acked": len(acked),
    }
    return {
        "ok": len(blockers) == 0,
        "errors": all_err,
        "warnings": all_warn,
        "acked": acked,
        "severity_summary": summary,
    }
