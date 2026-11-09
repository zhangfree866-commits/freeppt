#!/usr/bin/env python3
"""M3：FreePPT 护栏（SVG 输入）。

ppt-master 的质量器管 XML 契约/越界；本模块补它不管的四件事：
  · CONTRAST   文字与其(最近底板)的 WCAG 对比度
  · CAPACITY   叶子要点数不超过 Page Spec 容量
  · DENSITY    叶子形状数落在密度区间
  · FACT       含数字的文本在 Page Spec 的 sources 有对应来源

视觉层级分流：轴标签/脚注/页脚按"非正文"口径（阈值 3.0、字号可小），
跨页重复页脚不重复报。

用法:
  python3 -m engine.svg_guard <plan.json> <svg_output_dir>
退出码 0 = 零 blocker。
"""
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2003/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# WCAG 阈值
AA_BODY, AA_LARGE, AA_GRAPHIC = 4.5, 3.0, 3.0
LARGE_PX = 24            # ≥24px 视作大字（约18pt）
FOOTNOTE_MAXPX = 14      # ≤14px 且在脚注区 → 非正文标签

DENSITY_RANGE = {
    "airy": (3, 15),
    "mid": (10, 25),
    "dense": (25, 90),
}

# 底板候选：填充图形（rect/circle/ellipse/path），叶子计数
SHAPE_TAGS = {"rect", "circle", "ellipse", "path", "polygon"}
TEXT_TAG = "text"

NUM_RE = re.compile(r"\d")
FOOTER_RE = re.compile(r"^\s*(source|来源|\d+\s*/\s*\d+|P\d+\s*/)", re.I)


# ---------------- WCAG ----------------
def _chan(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def parse_color(s):
    if not s:
        return None
    s = s.strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) == 6:
            try:
                return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return None
    return None


def lum(rgb):
    r, g, b = (_chan(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1, c2):
    l1, l2 = lum(c1), lum(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# ---------------- SVG 解析 ----------------
def localname(el):
    return el.tag.split("}", 1)[1] if "}" in el.tag else el.tag


def style_fill(el, grad_map=None):
    """取 fill 属性；none/继承标识分别处理；渐变取首停色作近似底板。"""
    f = el.get("fill")
    if f is None:
        return None          # 继承
    f = f.strip()
    if f.lower() == "none":
        return "none"
    m = re.match(r"url\(#([^)]+)\)", f)
    if m:
        gid = m.group(1)
        if grad_map and gid in grad_map:
            return grad_map[gid]      # 近似有效底色（首停色）
        return "gradient"
    return parse_color(f)


def geometry(el):
    """返回元素包围盒 (x,y,w,h)，支持 rect/circle/ellipse；其它返回 None。"""
    t = localname(el)
    def gf(k, d=None):
        v = el.get(k)
        try:
            return float(v) if v is not None else d
        except ValueError:
            return d
    if t == "rect" or t == "image":
        x, y = gf("x", 0), gf("y", 0)
        w, h = gf("width", 0), gf("height", 0)
        return (x, y, w, h)
    if t in ("circle", "ellipse"):
        cx, cy = gf("cx", 0), gf("cy", 0)
        if t == "circle":
            r = gf("r", 0)
            return (cx - r, cy - r, 2 * r, 2 * r)
        rx, ry = gf("rx", 0), gf("ry", 0)
        return (cx - rx, cy - ry, 2 * rx, 2 * ry)
    return None


def text_of(el):
    parts = [el.text or ""]
    for c in el:
        parts.append(c.text or "")
        parts.append(c.tail or "")
    return "".join(parts).strip()


def font_size(el):
    v = el.get("font-size")
    if not v:
        return None
    m = re.match(r"([\d.]+)", v)
    return float(m.group(1)) if m else None


def contains(box, x, y):
    bx, by, bw, bh = box
    in_x = (x >= bx) and (x <= bx + bw)
    in_y = (y >= by) and (y <= by + bh)
    return in_x and in_y


# ---------------- 单页检查 ----------------
def check_page(spec, svg_path):
    findings = []          # blocker
    advisories = []
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # 先建渐变表（id → 首停色，作为底板有效色近似）
    grad_map = {}
    for el in root.iter():
        if localname(el) == "linearGradient":
            gid = el.get("id")
            for st in el:
                if localname(st) == "stop" and st.get("stop-color"):
                    c = parse_color(st.get("stop-color"))
                    if c:
                        grad_map[gid] = c
                        break

    # 收集叶子元素：本护栏按文档顺序取“最近的前置底板”
    panels = []            # (box, fill)
    photo_boxes = []       # 位图照片区域（无法读明暗，文字在此 → 人工确认）
    shape_leaves = 0
    text_nodes = []
    for el in root.iter():
        t = localname(el)
        if t in SHAPE_TAGS:
            shape_leaves += 1
            box = geometry(el)
            fill = style_fill(el, grad_map)
            if box and isinstance(fill, tuple):
                panels.append((box, fill))
        elif t == "image":
            box = geometry(el)
            if box:
                photo_boxes.append(box)
        elif t == TEXT_TAG:
            text_nodes.append(el)

    # 默认底色：浅纸面（Page Spec 若给 paper 用它），保守按白
    paper = parse_color(spec.get("style_lock", {}).get("colors", {}).get("paper")) \
        if isinstance(spec, dict) else None
    default_bg = paper or (244, 247, 251)

    def backdrop(x, y):
        hit = default_bg
        for box, fill in panels:
            if contains(box, x, y):
                hit = fill          # 文档顺序，后者覆盖
        return hit

    # ---- 对比度 ----
    for el in text_nodes:
        txtstr = text_of(el)
        if not txtstr:
            continue
        # 跨页页脚：放行
        if FOOTER_RE.match(txtstr):
            continue
        col = parse_color(el.get("fill"))
        if col is None:
            continue
        fs = font_size(el) or 16
        # 定位：用元素首个 x/y（text 显式 y，tspan 可能覆盖），粗略取 x, baseline-
        try:
            tx = float(el.get("x"))
            ty = float(el.get("y"))
        except (TypeError, ValueError):
            tx, ty = 0, 0
        bg = backdrop(tx, ty)
        ratio = contrast(col, bg)
        if fs >= LARGE_PX:
            need, tier = AA_LARGE, "large"
        elif fs <= FOOTNOTE_MAXPX:
            # 轴刻度 / 类别名 / 脚注等非正文标签
            need, tier = AA_GRAPHIC, "label"
        else:
            need, tier = AA_BODY, "body"
        if ratio < need:
            on_photo = (not any(contains(b, tx, ty) for b, _ in panels)) and \
                       any(contains(pb, tx, ty) for pb in photo_boxes)
            pure_num = bool(re.fullmatch(r"[\d.,]+", txtstr))
            if on_photo:
                advisories.append({
                    "code": "CONTRAST_PHOTO", "text": txtstr[:18],
                    "ratio": round(ratio, 2), "note": "落在照片上，需人工确认明暗"})
            elif pure_num:
                advisories.append({
                    "code": "CONTRAST_DECOR", "text": txtstr[:18],
                    "ratio": round(ratio, 2), "note": "装饰序号/短数字，需人工确认"})
            else:
                findings.append({
                    "code": "CONTRAST", "text": txtstr[:18],
                    "ratio": round(ratio, 2), "need": need, "tier": tier})

    # ---- 容量：叶子要点 = points 条目（以 spec 为准，这里核对 spec 自洽）----
    cap = spec.get("capacity")
    npts = len(spec.get("points", []) or [])
    if cap is not None and npts > cap:
        findings.append({"code": "CAPACITY", "points": npts, "capacity": cap})

    # ---- 密度 ----
    hint = spec.get("density_hint")
    if hint in DENSITY_RANGE:
        lo, hi = DENSITY_RANGE[hint]
        if not (lo <= shape_leaves <= hi):
            advisories.append({"code": "DENSITY", "shape_leaves": shape_leaves,
                               "range": [lo, hi]})

    # ---- 事实来源：正文叙述含数字（非纯装饰/非页脚）需有 sources ----
    sources = spec.get("sources") or []
    def is_claim_with_number(e):
        t = text_of(e)
        if not t or FOOTER_RE.match(t):
            return False
        if re.fullmatch(r"[\d.,% ]+", t):
            return False          # 纯数字标签（装饰序号/轴标）
        return bool(NUM_RE.search(t))
    has_num_text = any(is_claim_with_number(e) for e in text_nodes)
    if has_num_text and not sources:
        findings.append({"code": "FACT_UNSOURCED"})

    return findings, advisories, shape_leaves, len(text_nodes)


# ---------------- 入口 ----------------
def run(plan_path, svg_dir):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    pages = plan.get("pages", [])
    svg_dir = Path(svg_dir)
    svgs = sorted(svg_dir.glob("*.svg"))

    all_blockers, all_advisories = [], []
    print(f"SVG guard: {len(pages)} page spec(s), {len(svgs)} svg(s)")
    for i, spec in enumerate(pages):
        if i >= len(svgs):
            break
        f, a, ns, nt = check_page(spec, svgs[i])
        tag = f"P{i+1}"
        for x in f:
            all_blockers.append((tag, x))
        for x in a:
            all_advisories.append((tag, x))
        print(f"  {tag} {svgs[i].name}: shapes={ns} texts={nt} "
              f"blockers={len(f)} advisories={len(a)}")

    print("\n=== BLOCKERS ===")
    for tag, x in all_blockers:
        print(f"  [{tag}] {x}")
    print("=== ADVISORIES ===")
    for tag, x in all_advisories:
        print(f"  [{tag}] {x}")

    ok = not all_blockers
    print(f"\nok: {'true' if ok else 'false'} "
          f"({len(all_blockers)} blockers, {len(all_advisories)} advisories)")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python3 -m engine.svg_guard <plan.json> <svg_output_dir>")
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2]))
