#!/usr/bin/env python3
"""FreePPT art direction: compose a deck page-by-page instead of filling a master.

The old pipeline was: pick one of 10 masters -> inject text -> every content
page ends up with the same title rule, same three equal cards, same footer.
This module replaces that step for creative decks:

    content semantics + reference cover -> per-page composition archetype
    -> absolute rects -> standard DSL -> the SAME layout/lint/build pipeline

Guarantees (all deterministic, no LLM in this path):
  * adjacent pages never reuse an archetype (lint LAYOUT_REPETITION blocks it)
  * each chapter needs >= half its content pages to be visually distinct;
    beyond CHAPTER_PAGE_CAP pages a deck MUST declare chapters or compose()
    refuses to run (the 14-archetype pool cannot carry a long flat file)
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

# Sentinel archetype meaning "the host model renders this page itself"
# (e.g. a hand-authored SVG). compose() emits a placeholder slide and leaves
# the children empty so the host can fill it. This is the concrete hook that
# makes the "model as per-page designer" first principle executable: the engine
# obeys the designer's brief instead of auto-assigning from the archetype pool.
HOST_RENDERED = "__host__"

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


def _wrap_h(text, w, size):
    """一段文字在给定宽度下占多高（含 _t 的 +6 余量）。

    用于「先量字、再定容器」——批注块、卡片这类容器的尺寸应当由内容决定，
    不能写死。写死就是文字溢出容器的来源。
    """
    node = {"t": "text", "text": str(text), "size": size, "color": "#000000"}
    return math.ceil(L.leaf_text_h(node, max(w, 1))) + 6


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


def _ic(x, y, size, name, color, **kw):
    """Native-shape icon node (editable, theme-accent tinted)."""
    n = {"t": "icon", "name": name, "color": str(color).upper(),
         "rect": [round(x, 1), round(y, 1), round(size, 1), round(size, 1)]}
    n.update({k: v for k, v in kw.items() if v is not None})
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
# speaker-notes generation (deterministic; no LLM in this path)
# ---------------------------------------------------------------------------

# Connective tissue for turning bullet content into spoken prose. The notes
# restate only what the page already contains — they never invent data — so a
# deck stays reproducible and the presenter gets a ready, on-message script.
_NOTE_OPENERS = ["首先", "其次", "再次", "另外", "还有一点", "最后要强调的是"]


def _speaker_notes(page, arch, ctx):
    """Build a presentable, deterministic speaker script from page content."""
    kind = page.get("kind", "content")
    book = ctx.get("book", {})
    title = _head(page)
    parts = []

    if kind == "cover":
        parts.append("各位好，今天分享的是《" + str(book.get("title", "本书")) + "》。")
        if book.get("subtitle"):
            parts.append("这本书围绕「" + book["subtitle"] + "」展开。")
        if page.get("lead"):
            parts.append(str(page["lead"]))
        parts.append("下面我们正式进入内容。")
        return "".join(parts)

    if kind == "chapter":
        no = str(page.get("no") or f"{ctx['idx'] + 1:02d}")
        parts.append("接下来进入第 " + no + " 部分：" + title + "。")
        if page.get("en"):
            parts.append("这一章对应的英文主题是 " + str(page["en"]) + "。")
        if page.get("lead"):
            parts.append(str(page["lead"]))
        parts.append("我们先建立整体认识，再逐个展开关键概念。")
        return "".join(parts)

    if kind == "closing":
        parts.append("最后做一个收束。" + (title + "。" if title else ""))
        if page.get("quote"):
            parts.append("留一句话给大家：" + str(page["quote"]))
        parts.append("建议把今天的要点带回实际工作，挑一条立刻实践。谢谢大家。")
        return "".join(parts)

    if kind == "quote" or page.get("quote"):
        parts.append("这一页想传达的核心观点是：" + str(_quote(page)) + "。")
        att = page.get("attribution") or book.get("author")
        if att:
            parts.append("这句话出自" + str(att) + "，值得结合自身处境体会。")
        return "".join(parts)

    # generic content page: title lead-in, then each point as spoken prose
    if title:
        parts.append("这一页的主题是「" + title + "」。")
    if page.get("lead"):
        parts.append(str(page["lead"]))
    pts = _points(page)
    real = [pt for pt in pts if pt.get("head") or pt.get("body")][:4]
    for i, pt in enumerate(real):
        lead = _NOTE_OPENERS[min(i, len(_NOTE_OPENERS) - 1)]
        if pt.get("head") and pt.get("body"):
            parts.append(lead + "是" + pt["head"] + "，" + pt["body"])
        elif pt.get("body"):
            parts.append(lead + "，" + pt["body"])
        elif pt.get("head"):
            parts.append(lead + "看" + pt["head"])
    if page.get("value") or page.get("kpi"):
        parts.append("关键数字是 " + str(page.get("value") or page.get("kpi"))
                     + ("（" + str(page.get("label")) + "）" if page.get("label") else ""))
    if not real and not page.get("lead"):
        parts.append("我们结合这一页的结构，梳理其中的逻辑关系与重点。")
    parts.append("讲解时可以结合实际案例，帮助大家理解。")
    return "".join(parts)


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
    # ------------------------------------------------------------------
    # 先量、再排版。这一页的构件全部由内容决定位置，没有一处写死 y。
    #
    # 为什么要「先量」：原实现边排边推 y，排到批注块时才发现没地方了，
    # 只好从底边 630 倒推批注位置 —— 于是正文被挤到批注块底下（实测渲染
    # p03：正文最后一行「可反复使用的互动秩序。」下沿被切掉）。
    # 先量一遍总需求，再决定间距，就不会出现「排到最后发现放不下」。
    # ------------------------------------------------------------------
    lead = p.get("lead") or ""
    pts = _points(p)[:3]
    body_w = rw - 20
    lead_h = _wrap_h(lead, rw, 23) if lead else 0
    head_hs = [_wrap_h(pt["head"], rw, 24) if pt["head"] else 0 for pt in pts]
    body_hs = [_wrap_h(pt["body"], body_w, 18) if pt["body"] else 0 for pt in pts]
    note_h16 = _wrap_h(p["note"], rw - 32, 16) + 24 if p.get("note") else 0

    top = 110 + r.randint(-10, 20)
    page_bottom = 630                     # 648 是页码行，630 是硬上限
    fixed = lead_h + sum(head_hs) + sum(body_hs)
    # 间距分三段：导语后 gap_lead、每组标题→正文 gap_h2b、组间 gap_item。
    # 默认值来自参照 deck 的实测节奏；总高不够时按同一比例一起收紧，
    # 而不是只砍最后一处（那样会有一处突然变挤，版面节奏就断了）。
    gap_lead, gap_h2b, gap_item, gap_note = 34, 10, 22, 16
    want = (fixed + (gap_lead if lead else 0) + gap_h2b * sum(head_hs)
            + gap_item * len(pts) + (gap_note + note_h16 if note_h16 else 0))
    avail = page_bottom - top
    if want > avail and note_h16:
        # 先收批注：它是辅助信息，可以更贴近正文。
        gap_note = 10
        want = (fixed + (gap_lead if lead else 0) + gap_h2b * sum(head_hs)
                + gap_item * len(pts) + gap_note + note_h16)
    if want > avail:
        # 还超就整体压缩「组间 / 导语后」这类弹性间距。
        # 保底 14 而不是 8：rect 高度是按 LINE_FACTOR 算的，而渲染用的是主题
        # 自己的 line_spacing（magazine 是 1.32），每行实际比 rect 高一点。
        # 压到 8 会让相邻两块按真实行高算时叠在一起（实测 p03 就是这么翻的）。
        flex = ((gap_lead if lead else 0) + gap_item * len(pts)
                + (gap_note + note_h16 if note_h16 else 0))
        fixed2 = fixed + gap_h2b * sum(head_hs)
        floor = 14 * (1 if lead else 0) + 14 * len(pts)
        if fixed2 + flex > avail:
            squash = max(floor + (gap_note + note_h16 if note_h16 else 0),
                         avail - fixed2)
            ratio = squash / flex if flex else 1.0
            if lead:
                gap_lead = max(14, int(gap_lead * ratio))
            gap_item = max(14, int(gap_item * ratio))
            if note_h16:
                gap_note = max(10, int(gap_note * ratio))

    y = top
    if lead:
        n = _t(rx, y, rw, lead, 23, S["body"], on=S["paper"])
        kids.append(n)
        y = n["rect"][1] + n["rect"][3] + gap_lead
    for pt in pts:
        if pt["head"]:
            n = _t(rx, y, rw, pt["head"], 24, S["accent"],
                   weight="bold", on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + gap_h2b
        if pt["body"]:
            n = _t(rx, y, body_w, pt["body"], 18, S["body"],
                   max_h=110, on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + gap_item
    if p.get("note"):
        note_w = rw - 32
        note_line = _wrap_h(p["note"], note_w, 16)
        note_h = note_line + 24
        body_bottom = y - gap_item            # 循环末尾多加的那段不算正文
        note_y = body_bottom + gap_note
        # 兜底：真正塞不下时把批注块压进 630 以内，宁可离正文近一点。
        # 绝不越过 630 —— 648 是页码行，越过就是「色块压页码」。
        if note_y + note_h > page_bottom:
            note_y = max(body_bottom + 8, page_bottom - note_h)
        kids.append(_b(rx, note_y, rw, note_h, S["soft"]))
        kids.append(_t(rx + 16, note_y + 12, note_w, p["note"], 16, S["ink"],
                       max_h=note_line, on=S["soft"]))
    kids += _source(S, p, 64, 648, 700, on=S["paper"])
    kids += _chrome(S, c, 1060, 648, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "mid"


def a_offset_triptych(p, S, c):
    r = c["rng"]
    pts = _points(p)[:3]
    n = len(pts)
    layouts = {
        1: ([64], [700], [196], [S["soft"]]),
        2: ([64, 700], [572, 516], [196, 246], [S["soft"], S["accent"]]),
        3: ([64, 466, 856], [344, 342, 356],
            [196, 246, 188],
            [S["soft"], None, S["accent"]]),
    }
    xs, ws, ys, fills = layouts[n]
    title = _t(64, 62, 900, _head(p), 36, S["ink"], max_h=70,
               min_size=26, weight="bold", on=S["paper"])
    kids = [title]
    kids += _motif(S, 1050, 68, 0.9, 3)

    # 编号必须落在标题**实际**底边之下。这里不用标题框的 53px，因为 36pt
    # 一行的真实占高是 36×1.333×1.28 ≈ 61px，框比字矮——原来把编号硬编码在
    # 卡片上方 46px 处，标题两行时编号就压进标题了（成品审计实测第 5 页
    # collisions: 标题 ↔「01」）。标题框高是排版留位，不是视觉边界。
    title_bottom = title["rect"][1] + title["rect"][3]
    num_size = 30
    num_h = num_size * 1.333 * 1.32             # 编号真实行高（与渲染同口径）
    num_gap = 18                                # 编号底边到卡片顶边
    min_card_y = title_bottom + 14 + num_h + num_gap

    # 卡片高度由**内容**决定，不是写死 340。
    # 写死会出现两个问题（都在《人情与面子》p05 实测到）：
    #   * 内容只有三行时，卡片底部 40% 全空 —— 看着像没做完
    #   * 内容变多时，_rc 会按 measured 撑高，反而压住下面的批注行
    # 量法直接按块累加，不用 L.hug_h —— 实测 hug_h 对 richcard 的 padding
    # 口径与 _rc 不一致（传 356 宽算 163，_rc 实际要 190），会少算一行。
    card_pad = 22
    space_before = 12

    # 深色强调卡的标题：中文 + 拼音混排时容易折成两行，把正文挤出块外。
    # 实测（p05 第三张卡）：「关系 guanxi 与报 bao」在 312px 内实际折两行，
    # 而 _wrap_h 只算出一行（拼音按 0.56em 估宽，Georgia 实际更宽）。
    # 折行估不准就别赌 —— 直接按「能不能放进一行」降字号，控住结果。
    def _head_size(i, pt):
        if fills[i] != S["accent"]:
            return 23
        inner = ws[i] - 2 * card_pad
        # 一行的判定必须留余量，不能刚好卡在边界上。
        # 实测（p05 第三张卡）：「关系 guanxi 与报 bao」按 0.56em 估宽刚好
        # 判定成一行，但 Georgia 的拼音比估算宽，渲染折成了两行，正文被挤出
        # 深色块。所以用一个 1.12 的保守系数：估算宽度乘它仍在框内，才算一行。
        for size in (30, 26, 23):
            single = _wrap_h("中", inner, size)
            if _wrap_h(pt["head"], inner / 1.12, size) <= single + 2:
                return size
        return 23

    def _card_need(i, pt):
        inner = ws[i] - 2 * card_pad
        total = 2 * card_pad
        if pt["head"]:
            total += _wrap_h(pt["head"], inner, _head_size(i, pt))
        if pt["body"]:
            total += space_before + _wrap_h(pt["body"], inner, 18)
        return total

    needs = [_card_need(i, pt) for i, pt in enumerate(pts)]
    # 底部边界：有批注时批注在 626，卡片底边要留 18px 呼吸；没有就到 660。
    bottom_limit = (626 - 18) if p.get("note") else 660
    # 三张卡取同一高度（视觉齐平），上限是整页剩余空间。
    card_h = min(max(needs), max(bottom_limit - min_card_y, 140))

    # 整组在可用区里垂直居中。
    # 实测（《人情与面子》p05）：卡片高度从写死 340 改成按内容算之后，三张卡
    # 只有 173 高，顶边 200–260、底边 373–433，而可用区一直到 608 —— 页面下半
    # 部空出 190px，比上半部还空，看着像内容没写完就交稿了。
    # 错落偏移（三张卡刻意错开）必须保留，所以要居中的是**外接框**，不是每张卡：
    # 先取相对偏移，整组居中，再把偏移加回去。
    ys = [max(y + r.randint(0, 16), min_card_y) for y in ys]
    delta = [y - min(ys) for y in ys]
    group_h = max(delta) + card_h
    avail_top = min_card_y
    avail_bot = bottom_limit
    group_top = avail_top + max(0, (avail_bot - avail_top - group_h)) // 2
    # 分组居中后再兜一次底：内容特别高时仍不许越到批注/页脚下面。
    group_top = min(group_top, max(avail_bot - group_h, avail_top))
    ys = [group_top + d for d in delta]

    for i, (pt, x, w_, y) in enumerate(zip(pts, xs, ws, ys)):
        # 编号放在卡片顶边之上 num_gap 处，用**实测**编号行高定位，
        # 不用写死偏移 —— 写死会让编号压住卡片上沿（实测 p05：01 底边
        # 221 与卡片顶边 222 只差 1px，渲染图里编号像被卡片切了一刀）。
        kids.append(_t(x, y - num_gap - num_h, 100, f"{i + 1:02d}",
                       num_size, S["accent"], decor=True, weight="bold",
                       on=S["paper"]))
        dark_card = fills[i] == S["accent"]
        blocks = []
        if pt["head"]:
            blocks.append(_blk(pt["head"], _head_size(i, pt),
                               S["paper"] if dark_card else S["ink"],
                               "bold"))
        if pt["body"]:
            blocks.append(_blk(pt["body"], 18,
                               S["paper"] if dark_card else S["body"], space=12))
        kids.append(_rc(x, y, w_, card_h, blocks,
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
    kids.append(_t(64, 52, 200, "“", 130, S["accent"], decor=True, on=surface))
    q = _quote(p)
    n = _t(150, 236, 940, q, 44, fg, max_h=290, min_size=28,
           weight="bold", on=surface)
    kids.append(n)
    # 这条短粗线**不能放在引言下面**。实测两版都被穿过最后一行：
    # 先按 rect 底边 +34，再按 +26，渲染出来都是「线压文字」——因为
    # LibreOffice 与 PowerPoint 的 44pt 行盒都比几何估算高，任何「贴着
    # 文字底边」的装饰线都会碰到最后一行。
    #
    # 换一个设计判断：这条线的作用是「引言的起手式」，不是「下划线」。
    # 放在引言**上方**——既不会碰字，又保住了「一句话前面有一道重笔」的
    # 视觉重量。同一条线，位置一改，从缺陷变成设计。
    kids.append(_d(150, 186, 260, S["accent"], thickness=4))
    att = p.get("attribution") or c["book"].get("author", "")
    if att:
        kids.append(_t(150, n["rect"][1] + n["rect"][3] + 44, 800,
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
    pts = _points(p)[:4]
    # 四个「标题+正文」双行块时垂直预算吃紧，自动切紧凑参数；<=3 点保持原样。
    dense = len(pts) >= 4
    head_sz = 21 if dense else 23
    body_sz = 16 if dense else 19
    head_gap = 6 if dense else 8
    body_gap = 16 if dense else 30
    body_maxh = 64 if dense else 100
    for pt in pts:
        if pt["head"]:
            n = _t(64, y, 820, pt["head"], head_sz, S["accent"],
                   weight="bold", on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + head_gap
        if pt["body"]:
            n = _t(64, y, 800, pt["body"], body_sz, S["body"],
                   max_h=body_maxh, on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + body_gap
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
    """阶梯：每级台阶是实体色块，向右上抬升，级数=要点数。

    为什么要改（2026-11-13）：原来只是每行缩进 34px 的编号列表——四行累计
    偏移 100px，外加一条细线。名字叫 stair，画面上却没有台阶，用户一眼就看
    出「没按说好的做」。现在真的画台阶：实体色块逐级加宽、逐级抬升，左缘与
    上缘同步移动（累计偏移远超 80px 的台阶识别阈值），第一级最深、末级最亮。
    """
    kids = [_t(64, 58, 1080, _head(p), 33, S["ink"], max_h=76,
               min_size=23, weight="bold", on=S["paper"])]
    kids += _motif(S, 1080, 62, 0.9, 0)

    pts = _points(p)[:4]
    n = max(1, len(pts))

    # 台阶几何：底部对齐同一条基线，**高度逐级递增**、左缘逐级右移。
    # 于是左上角连成一条向上抬升的楼梯线——「从依赖到互赖」是往上的，
    # 视觉方向必须跟着内容方向走，反了就变成「越走越低」。
    #
    # 关键约束（踩过三次）：
    #   1) 高度必须递增，不能递减（递减画出来是往下走，语义相反）；
    #   2) 每一级只占自己的水平区间，不能都铺到右缘（否则后级盖住前级文字）；
    #   3) 底部对齐才有「台阶」感，顶部对齐会变成柱状图。
    base_y = 610                      # 基线（各级底边都落在这里）
    step_rise = 74                    # 每级高 74px
    page_r = 1216
    x0 = 92
    n_gap = 8                         # 台阶之间的细缝，让层级更清楚

    # 每一级的高度都必须由**这一级自己的内容**决定。
    # 原来只按最窄的第一级算一次 short_h，然后每级 +74 —— 于是内容少的级
    # 底部会空出一大片（实测 p07：三个色块底部约 50% 是空的，而色块高度差
    # 又是写死的 74，跟内容完全无关，看着像随便拉高了几个方块）。
    # 台阶仍要抬升（语义上「往上走」），但抬升量从「内容差」里取：
    # 内容多的级自然更高，抬升就自然发生，不需要再外挂一个固定增量。
    def _wrap_lines(text, width, size):
        """粗略折行数：按字宽加权，和审计用的同一套口径。"""
        import unicodedata
        em = size * 1.333
        cap = max(width / em, 1.0)
        units = 0.0
        for ch in text:
            if ch == " ":
                units += 0.30
            elif unicodedata.east_asian_width(ch) in ("W", "F"):
                units += 1.0
            elif ch.isalnum():
                units += 0.56
            else:
                units += 0.52
        return max(1, -(-int(round(units * 100)) // int(round(cap * 100))))

    span = (page_r - x0) // n         # 每级占的宽度
    xs = [x0 + i * span for i in range(n)]

    def _w_of(i):
        return (page_r - xs[i]) if i == n - 1 else (span - n_gap)

    def _need_of(i):
        """这一级装下编号 + 标题 + 正文需要多高（含上下内边距）。"""
        inner = _w_of(i) - 36
        h = 14 + (20 * 1.333 * 1.32)          # 顶内边距 + 编号行
        head = pts[i]["head"]
        if head:
            h += 8 + _wrap_lines(head, inner, 20) * 20 * 1.333 * 1.32
        body = pts[i]["body"]
        if body:
            h += 10 + _wrap_lines(body, inner, 16) * 16 * 1.333 * 1.32
        return h + 16                          # 底内边距

    needs = [_need_of(i) for i in range(n)]
    # 台阶感来自「高度递增」。内容本身已递增时直接用内容高度；
    # 内容差不多高时补一个最小抬升，保证仍然看得出是台阶。
    min_rise = 22
    heights = [needs[0]]
    for i in range(1, n):
        heights.append(max(needs[i], heights[-1] + min_rise))
    # 顶部不能顶到标题：最高一级的顶边要落在标题底边之下。
    # 基线不写死 610 —— 内容少时写死会让整组沉到页面下半部，
    # 上面留一大片空白（实测 p07：三块内容约 200 高，却从 y≈310 才开始）。
    # 先按基线 610 试，装得下就用；装不下再把基线上移，让整组居中在
    # 「标题底边 ~ 页脚上沿」这段可用区域里。
    head_bottom = 58 + (76 if _head(p) else 0)     # 标题最大占位
    top_limit = head_bottom + 26
    foot_top = 664                                  # 页脚行上沿
    tallest = max(heights)
    if base_y - tallest < top_limit:
        base_y = top_limit + tallest
    else:
        # 竖向居中，别把台阶贴着页脚堆
        avail_top, avail_bot = top_limit, foot_top - 8
        slack = (avail_bot - avail_top) - tallest
        if slack > 40:
            base_y = avail_top + int(slack / 2) + tallest

    fills = [S["deep"], S["accent"], S["accent2"], S["soft"]][:n]
    if len(fills) < n:
        fills += [S["soft"]] * (n - len(fills))

    def _fg_on(bg):
        """按底色亮度选前景色。

        不能写死：deep/accent/accent2 都是深色（用纸色字），soft 是浅色
        （得用墨色字）。写死成 ink 会出现 #1C1917 on #1E3A5F 对比度 1.52
        这种「几乎看不见」的组合——lint 的 CONTRAST 会当场拦下。
        """
        h = bg.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        return S["ink"] if lum > 0.6 else S["paper"]

    fgs = [_fg_on(f) for f in fills]

    for i in range(n):
        h = heights[i]
        x = xs[i]
        w = _w_of(i)
        y = base_y - h
        kids.append(_b(x, y, w, h, fills[i]))
        kids.append(_t(x + 18, y + 14, 52, f"{i + 1:02d}", 20,
                       fgs[i], decor=True, weight="bold", on=fills[i]))
        head = pts[i]["head"]
        if head:
            kids.append(_t(x + 18, y + 44, w - 36, head, 20, fgs[i],
                           max_h=32, weight="bold", on=fills[i]))
        body = pts[i]["body"]
        if body:
            kids.append(_t(x + 18, y + 80, w - 36, body, 16, fgs[i],
                           max_h=72, on=fills[i]))

    kids += _chrome(S, c, 1060, 664, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "dense"


def a_data_focus(p, S, c):
    value = str(p.get("value") or p.get("kpi") or "01")
    label = p.get("label") or p.get("lead") or ""
    kids = [_t(64, 74, 1000, _head(p), 32, S["ink"], max_h=80,
               min_size=24, weight="bold", on=S["paper"])]
    kids.append(_b(64, 200, 640, 360, S["soft"]))
    kids += _motif(S, 92, 226, 1.2, 2)
    num = _t(92, 286, 580, value, 150, S["accent"], max_h=190,
             min_size=60, weight="bold", on=S["soft"], decor=True)
    kids.append(num)
    if label:
        # 说明标签的位置必须由数字**实际**底边推出来。原来写死 y=480：
        # 150pt 数字加 _t 的 +6 余量，底边实际到 482，说明标签就压在数字下沿
        # （渲染图里「黄光国提出…的年份」和 1987 粘在一起）。
        label_y = num["rect"][1] + num["rect"][3] + 18
        label_y = min(label_y, 200 + 360 - 62)      # 别超出浅色块
        kids.append(_t(92, label_y, 560, label, 21, S["ink"],
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


def _explicit_points(page):
    """Like _points() but without the kind/lead fallback for empty pages."""
    out = []
    for it in (page.get("points") or page.get("items") or []):
        if isinstance(it, str):
            out.append({"head": "", "body": it})
        elif isinstance(it, dict):
            out.append({"head": it.get("head") or it.get("title") or "",
                        "body": it.get("body") or it.get("text") or ""})
    return out


def a_chart_story(p, S, c):
    """Native editable chart on the left, conclusion column on the right."""
    kids = [_t(64, 62, 1080, _head(p), 34, S["ink"], max_h=80,
               min_size=24, weight="bold", on=S["paper"])]
    kids += _motif(S, 1090, 68, 0.8, 2)
    spec = p.get("chart") or {}
    if spec.get("series"):
        colors = [S["accent"], S["deep"], S["soft"], S["accent2"]]
        kids.append({
            "t": "chart", "rect": [64, 150, 680, 430],
            "kind": spec.get("kind", "column"),
            "categories": spec.get("categories", []),
            "series": spec.get("series", []),
            "colors": colors[:max(1, len(spec.get("series", [])))],
            "legend": spec.get("legend", len(spec.get("series", [])) > 1),
            "_name": "chart1",
        })
    else:
        kids.append(_b(64, 150, 680, 430, S["soft"]))
        kids.append(_t(92, 330, 620, "未提供 chart 数据（categories/series）",
                       20, S["muted"], on=S["soft"]))
    x, y = 800, 160
    lead = p.get("lead") or ""
    if lead:
        n = _t(x, y, 416, lead, 22, S["ink"], max_h=140,
               weight="bold", on=S["paper"])
        kids.append(n)
        y = n["rect"][1] + n["rect"][3] + 24
    # only real point blocks; no kind/lead fallback (that would duplicate lead)
    for pt in _explicit_points(p)[:2]:
        if pt["head"]:
            n = _t(x, y, 416, pt["head"], 20, S["accent"],
                   weight="bold", on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 8
        if pt["body"]:
            n = _t(x, y, 400, pt["body"], 17, S["body"],
                   max_h=120, on=S["paper"])
            kids.append(n)
            y = n["rect"][1] + n["rect"][3] + 22
    kids += _source(S, p, 64, 610, 700, on=S["paper"])
    kids += _chrome(S, c, 1060, 648, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "mid"


def a_table_board(p, S, c):
    """Native editable table plus a takeaway strip underneath."""
    kids = [_t(64, 56, 1100, _head(p), 34, S["ink"], max_h=80,
               min_size=24, weight="bold", on=S["paper"])]
    kids += _motif(S, 1100, 62, 0.7, 3)
    # 表格数据允许两种写法：嵌套在 p["table"] 里，或直接写在页面顶层。
    # 只认前一种会把「模型已经很直白地给了 headers/rows」判成空表——
    # 实测就踩过：页面写了 headers/rows，lint 报 TABLE_SHAPE 缺表格数据，
    # 而产物里那个 table 节点的 headers/rows 都是空数组。
    spec = p.get("table") or {}
    headers = spec.get("headers") or p.get("headers") or []
    rows = spec.get("rows") or p.get("rows") or []
    kids.append({
        "t": "table", "rect": [64, 140, 1152, 400],
        "headers": headers,
        "rows": rows,
        "header_fill": S["deep"], "header_color": S["paper"],
        "body_color": S["ink"], "zebra": S["soft"],
        "border": S["line"], "_name": "table1",
    })
    note = p.get("note") or p.get("lead") or ""
    if note:
        kids.append(_b(64, 570, 1152, 64, S["soft"]))
        kids.append(_t(84, 584, 1112, note, 17, S["ink"],
                       max_h=44, on=S["soft"]))
    kids += _source(S, p, 64, 652, 800, on=S["paper"])
    kids += _chrome(S, c, 1060, 652, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "dense"


# Deterministic icon cycle for card archetypes (no semantic guessing, no rng).
ICON_CYCLE = ["target", "chart", "bulb", "gear", "shield", "users", "clock",
              "rocket", "book", "flag", "search", "layers", "check", "folder"]


def _card_icon(i, color):
    return ICON_CYCLE[i % len(ICON_CYCLE)]


def a_glass_panel(p, S, c):
    """Frosted-glass cards over a dark gradient (the benchmark's hero language)."""
    pts = _points(p)[:3]
    n = max(1, len(pts))
    kids = [_t(64, 60, 1080, _head(p), 36, S["ondark"], max_h=80,
               min_size=26, weight="bold", on=S["deep"])]
    kids += _motif(S, 1090, 66, 0.8, 2)
    gap = 30
    cw = (W - 128 - gap * (n - 1)) / n
    cy, chh = 196, 388
    for i, pt in enumerate(pts):
        cx = 64 + i * (cw + gap)
        card = _b(cx, cy, cw, chh, S["white"], opacity=8,
                  border=S["white"], border_opacity=20, radius=16)
        inner = [_ic(32, 34, 64, _card_icon(i, S["accent"]), S["accent"])]
        ty = 128
        if pt["head"]:
            hn = _t(32, ty, cw - 64, pt["head"], 24, S["ondark"],
                    max_h=72, min_size=18, weight="bold", on=S["deep"])
            inner.append(hn)
            ty += hn["rect"][3] + 14
        if pt["body"]:
            inner.append(_t(32, ty, cw - 64, pt["body"], 17, S["ondark"],
                            max_h=chh - (ty - 0) - 28, min_size=17,
                            opacity=80, on=S["deep"]))
        card["children"] = inner
        kids.append(card)
    if p.get("note"):
        kids.append(_t(64, 610, 1100, p["note"], 16, S["soft"],
                       max_h=44, on=S["deep"]))
    kids += _chrome(S, c, 1060, 666, on=S["deep"], align="right", w=160)
    return kids, S["deep"], "dark", "dense"


def a_icon_grid(p, S, c):
    """Light card grid, each cell led by a native editable icon."""
    pts = _points(p)[:4]
    n = max(1, len(pts))
    kids = [_t(64, 56, 1100, _head(p), 36, S["ink"], max_h=76,
               min_size=26, weight="bold", on=S["paper"])]
    kids += _motif(S, 1100, 64, 0.7, 3)
    gap = 28
    if n <= 3:
        cw = (W - 128 - gap * (n - 1)) / n
        cols, rows = n, 1
    else:
        cw = (W - 128 - gap) / 2
        cols, rows = 2, 2
    chh = 200 if rows == 1 else 214
    cy0 = 168
    for i, pt in enumerate(pts):
        col, row = (i % cols, i // cols)
        cx = 64 + col * (cw + gap)
        cy = cy0 + row * (chh + gap)
        card = _b(cx, cy, cw, chh, S["card"], border=S["line"], radius=14)
        inner = [_ic(28, 28, 58, _card_icon(i, S["accent"]), S["accent"])]
        ty = 104
        if pt["head"]:
            hn = _t(28, ty, cw - 56, pt["head"], 22, S["ink"],
                    max_h=56, min_size=18, weight="bold", on=S["card"])
            inner.append(hn)
            ty += hn["rect"][3] + 8
        if pt["body"]:
            inner.append(_t(28, ty, cw - 56, pt["body"], 17, S["body"],
                            max_h=chh - ty - 20, min_size=17, on=S["card"]))
        card["children"] = inner
        kids.append(card)
    kids += _chrome(S, c, 64, 666, on=S["paper"])
    return kids, S["paper"], "light", "dense"


def a_numbered_cards(p, S, c):
    """Editorial numbered cards with an accent rail (strong serif-magazine feel)."""
    pts = _points(p)[:3]
    n = max(1, len(pts))
    kids = [_t(64, 58, 1080, _head(p), 36, S["ink"], max_h=80,
               min_size=26, weight="bold", on=S["paper"])]
    kids += _motif(S, 1090, 64, 0.8, 1)
    gap = 28
    cw = (W - 128 - gap * (n - 1)) / n
    cy, chh = 184, 404
    for i, pt in enumerate(pts):
        cx = 64 + i * (cw + gap)
        card = _b(cx, cy, cw, chh, S["card"], border=S["line"], radius=12)
        inner = [
            _b(0, 0, 6, chh, S["accent"]),  # accent rail
            _t(28, 28, 120, f"{i + 1:02d}", 54, S["accent"], decor=True,
               weight="bold", on=S["card"]),
        ]
        ty = 118
        if pt["head"]:
            hn = _t(28, ty, cw - 56, pt["head"], 23, S["ink"],
                    max_h=64, min_size=18, weight="bold", on=S["card"])
            inner.append(hn)
            ty += hn["rect"][3] + 14
        if pt["body"]:
            inner.append(_t(28, ty, cw - 56, pt["body"], 17, S["body"],
                            max_h=chh - ty - 24, min_size=17, on=S["card"]))
        card["children"] = inner
        kids.append(card)
    kids += _source(S, p, 64, 628, 760, on=S["paper"])
    kids += _chrome(S, c, 1060, 660, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "dense"


def a_six_board(p, S, c):
    """2x3 editorial board for exactly six short blocks.

    Every other list archetype hard-slices to <=5, so a six-item page used to
    lose its last block(s). This layout takes up to six, laid out as two rows
    of three flat light cards; an accent rail + numeral carry the brand colour
    while the fills stay light, so no bright-cyan contrast case is introduced.
    """
    pts = _points(p)[:6]
    kids = [_t(64, 44, 1100, _head(p), 34, S["ink"], max_h=72,
               min_size=24, weight="bold", on=S["paper"])]
    kids += _motif(S, 1100, 50, 0.7, 2)
    x0, y0 = 64, 132
    gap_x, gap_y = 24, 22
    cw = (W - 128 - gap_x * 2) / 3      # 368
    chh = (648 - y0 - gap_y) / 2        # 247
    for i, pt in enumerate(pts):
        col, row = i % 3, i // 3
        cx = x0 + col * (cw + gap_x)
        cy = y0 + row * (chh + gap_y)
        card = _b(cx, cy, cw, chh, S["card"], border=S["line"], radius=10)
        inner = [_b(0, 0, 5, chh, S["accent"])]  # accent rail
        inner.append(_t(22, 18, 90, f"{i + 1:02d}", 24, S["accent"],
                        decor=True, weight="bold", on=S["card"]))
        ty = 60
        if pt["head"]:
            hn = _t(22, ty, cw - 44, pt["head"], 20, S["ink"],
                    max_h=52, min_size=16, weight="bold", on=S["card"])
            inner.append(hn)
            ty = hn["rect"][1] + hn["rect"][3] + 8
        if pt["body"]:
            inner.append(_t(22, ty, cw - 44, pt["body"], 16, S["body"],
                            max_h=chh - ty - 16, min_size=16,
                            on=S["card"]))
        card["children"] = inner
        kids.append(card)
    kids += _chrome(S, c, 1060, 668, on=S["paper"], align="right", w=160)
    return kids, S["paper"], "light", "dense"


ARCHETYPES = {
    "cover-editorial": {"density": "airy", "build": a_cover_editorial},
    "chapter-opener": {"density": "airy", "build": a_chapter_opener},
    "editorial-spread": {"density": "mid", "build": a_editorial_spread},
    "offset-triptych": {"density": "dense", "build": a_offset_triptych},
    "quote-bleed": {"density": "airy", "build": a_quote_bleed},
    "split-contrast": {"density": "mid", "build": a_split_contrast},
    "margin-notes": {"density": "mid", "build": a_margin_notes},
    "stair-list": {"density": "dense", "build": a_stair_list},
    "six-board": {"density": "dense", "build": a_six_board},
    "data-focus": {"density": "airy", "build": a_data_focus},
    "grid-mosaic": {"density": "dense", "build": a_grid_mosaic},
    "timeline-ribbon": {"density": "mid", "build": a_timeline_ribbon},
    "closing-echo": {"density": "airy", "build": a_closing_echo},
    "chart-story": {"density": "mid", "build": a_chart_story},
    "table-board": {"density": "dense", "build": a_table_board},
    # Card-system archetypes (post-benchmark): registered as valid layouts but
    # kept out of the default shuffle so legacy decks stay byte-identical. They
    # enter the candidate pool only when compose(..., card_system=True).
    "glass-panel": {"density": "dense", "build": a_glass_panel, "card": True},
    "icon-grid": {"density": "dense", "build": a_icon_grid, "card": True},
    "numbered-cards": {"density": "dense", "build": a_numbered_cards, "card": True},
}

# The card-system pool, used only when explicitly enabled.
CARD_ARCHETYPES = ["glass-panel", "icon-grid", "numbered-cards"]

# A single 12+2 archetype file can only carry so many pages before the
# pigeonhole principle forces repeats. Beyond the cap, chapter pages are
# mandatory: they reset the variety budget so archetypes may recur in a
# different chapter.
CHAPTER_PAGE_CAP = 24
SPECIAL_ARCHETYPES = {"cover-editorial", "chapter-opener", "closing-echo"}

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
              "stair-list": 3, "timeline-ribbon": 3, "six-board": 6}
# card-system archetypes need a couple of real blocks to read as intentional
MIN_POINTS.update({"glass-panel": 2, "icon-grid": 2, "numbered-cards": 2})

# Hard capacities of the card archetypes (they slice _points, so routing more
# blocks than this would silently drop content).
CARD_MAX_POINTS = {"glass-panel": 3, "icon-grid": 4, "numbered-cards": 3}

# Hard capacities of every list archetype (each slices _points in its builder).
# Archetypes that render rich/flexible panels without slicing are treated as
# effectively unbounded. Used only in the scoring path so candidate layouts can
# never be assigned more blocks than they actually display.
MAX_POINTS = {
    "editorial-spread": 3, "offset-triptych": 3, "stair-list": 5,
    "data-focus": 3, "grid-mosaic": 4, "timeline-ribbon": 5,
    "six-board": 6, "margin-notes": 4,
}
MAX_POINTS.update(CARD_MAX_POINTS)


def chapter_of(index, boundaries):
    """Chapter ordinal (0-based); a chapter page starts a new chapter."""
    return sum(1 for b in boundaries if index >= b)


def _archetype_score(page, arch, kind_rank, n_points):
    """Deterministic content-fit score of one archetype for one page.

    Higher is better. Every input is an objective feature of the page, so the
    same content always yields the same ranking regardless of the RNG seed.

    kind_rank  : the archetype's position in the hand-authored KIND_PREFS list
                 for this page kind (0 = strongest human preference).
    n_points   : number of real content blocks on the page (from _points).
    """
    score = 0
    # 1. The hand-authored kind contract dominates; each rank step costs 10,
    #    so a more specific archetype always beats a generic one on equal cues.
    score -= 10 * kind_rank
    # 2. Capacity fit: pair the archetype's density with the page's block count,
    #    so a content-rich page is not squeezed into an airy single-focus layout
    #    and a thin page is not spread across a mosaic it cannot fill.
    density = ARCHETYPES[arch]["density"]
    if n_points >= 4:
        score += 6 if density == "dense" else (-6 if density == "airy" else 2)
    elif n_points == 3:
        score += 4 if density in ("dense", "mid") else 0
    else:  # 1-2 blocks
        score += 5 if density == "airy" else (2 if density == "mid" else -3)
    # 3. Structural specialization keyed off explicit page fields.
    if page.get("quote") and arch == "quote-bleed":
        score += 12
    if (page.get("left") or page.get("right")) and arch == "split-contrast":
        score += 12
    if (page.get("value") or page.get("kpi")) and arch == "data-focus":
        score += 10
    if page.get("kind") == "timeline" and arch == "timeline-ribbon":
        score += 10
    return score


def _rank_candidates(page, cand, n_points):
    """Sort candidates by deterministic content fitness (no RNG involved)."""
    kind_list = KIND_PREFS.get(page.get("kind"), DEFAULT_PREFS)
    rank_of = {a: i for i, a in enumerate(kind_list)}
    fallback = len(kind_list)  # card archetypes sit below the hand-authored list
    return sorted(
        cand,
        key=lambda a: (
            -_archetype_score(page, a, rank_of.get(a, fallback), n_points),
            rank_of.get(a, fallback),  # tiebreak 1: human preference order
            a,                        # tiebreak 2: name, total determinism
        ))


def _resolve_brief(design_briefs, i, page):
    """Pick the brief dict for page i from a design_briefs mapping.

    Accepts keys as str index, int index, or the page's own id. Returns None
    when no brief applies, so the caller can fall back to the pool.
    """
    if not isinstance(design_briefs, dict):
        return None
    for key in (str(i), i, page.get("id")):
        if key is not None and key in design_briefs:
            return design_briefs[key]
    return None


def plan_archetypes(pages, rng, card_system=False, scoring=False):
    """Greedy diversity, chapter-aware.

    Within a chapter: prefer unused archetypes, never repeat a neighbour.
    Across chapters the used-set resets, so a long deck can reuse an
    archetype legitimately as long as each chapter stays varied. Pages that
    carry native chart/table data are routed to the matching archetype first.

    When card_system is True, the card archetypes (glass/icon/numbered) join
    the candidate pool for ordinary content pages; they remain excluded from
    the default path so legacy output is byte-identical.

    When scoring is True (opt-in), the generic candidate pool is ranked by a
    deterministic content-fit score instead of rng.shuffle. The same notes
    then produce the same archetype plan under every seed; the RNG is still
    used later for per-shape geometric jitter, which stays reproducible. The
    default (scoring=False) keeps the legacy shuffle byte-for-byte.
    """
    prefs = []
    for p in pages:
        cand = list(KIND_PREFS.get(p.get("kind"), DEFAULT_PREFS))
        # Data-bearing pages are routed to their native archetype BEFORE the
        # generic shuffle; absent data never lands on these archetypes.
        if p.get("chart"):
            cand = ["chart-story"] + [a for a in cand if a != "chart-story"]
        if p.get("table"):
            cand = ["table-board"] + [a for a in cand if a != "table-board"]
        n = len(_points(p))
        if card_system and p.get("kind") not in ("cover", "chapter", "closing"):
            # Match on BOTH the minimum (needs enough blocks to look intentional)
            # and the archetype's hard capacity, otherwise a 4-block page could
            # be pre-routed to a 3-capacity card and silently lose a block.
            cand = [a for a in CARD_ARCHETYPES
                    if MIN_POINTS.get(a, 0) <= n <= CARD_MAX_POINTS.get(a, n)] + cand
        min_pts = MIN_POINTS
        if scoring and n == 2 and (p.get("left") or p.get("right")) \
                and "offset-triptych" in cand:
            # A two-block comparison reads naturally as two panels. Let
            # offset-triptych in so repeated compare pages are not all forced
            # into split-contrast; diversity de-dup then alternates the two.
            min_pts = {**MIN_POINTS, "offset-triptych": 2}
        cand = [a for a in cand if min_pts.get(a, 0) <= n]
        if scoring:
            # Also enforce each archetype's hard capacity, so a page is never
            # assigned a layout that would slice off its extra blocks.
            cand = [a for a in cand if n <= MAX_POINTS.get(a, n)]
        if not cand:
            cand = list(DEFAULT_PREFS)
        if scoring:
            cand = _rank_candidates(p, cand, n)
            if n >= 6:
                # Six-item pages have no room anywhere else (every list
                # archetype slices to <=5). Pin six-board after scoring so the
                # fit ranker cannot demote it; opt-in via scoring keeps the
                # legacy shuffle path byte-identical.
                cand = ["six-board"] + [a for a in cand if a != "six-board"]
        else:
            rng.shuffle(cand)
        # data-bearing archetypes are an explicit routing decision; they must
        # stay first regardless of how the generic pool was ordered
        if p.get("chart"):
            cand = ["chart-story"] + [a for a in cand if a != "chart-story"]
        if p.get("table"):
            cand = ["table-board"] + [a for a in cand if a != "table-board"]
        prefs.append(cand)
    boundaries = [i for i, p in enumerate(pages) if p.get("kind") == "chapter"]
    plan, prev = [], None
    used_by_chapter = {}
    count_by_chapter = {}
    for i, cand in enumerate(prefs):
        # A six-item page has no truncation-free alternative, so content
        # integrity wins over the no-adjacent-repeat rule: force six-board
        # even if the previous/used set already contains it.
        if scoring and len(_points(pages[i])) >= 6 and "six-board" in cand:
            pick = "six-board"
            plan.append(pick)
            ch = chapter_of(i, boundaries)
            used_by_chapter.setdefault(ch, set()).add(pick)
            count_by_chapter.setdefault(ch, {})[pick] = \
                count_by_chapter.setdefault(ch, {}).get(pick, 0) + 1
            prev = pick
            continue
        ch = chapter_of(i, boundaries)
        used = used_by_chapter.setdefault(ch, set())
        counts = count_by_chapter.setdefault(ch, {})
        fresh = [a for a in cand if a not in used and a != prev]
        if fresh:
            pick = fresh[0]
        else:
            nonprev = [a for a in cand if a != prev]
            pool = nonprev or cand
            if scoring:
                # Every layout is already used in this chapter. Rebalance by
                # reusing the candidate seen least so far, breaking ties by the
                # candidate's fit-ranked order; avoids over-favouring one
                # archetype whenever the pool must repeat.
                rank = {a: j for j, a in enumerate(cand)}
                pick = min(pool, key=lambda a: (counts.get(a, 0), rank.get(a, 0)))
            else:
                pick = pool[0]
            if pick == prev:
                pick = next((a for a in DEFAULT_PREFS if a != prev),
                            "editorial-spread")
        plan.append(pick)
        used.add(pick)
        counts[pick] = counts.get(pick, 0) + 1
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


def compose(notes, notes_dir="", cover_path=None, base="magazine", seed=None,
            card_system=False, speaker_notes=True, scoring=False,
            design_briefs=None):
    """Return (deck DSL, provenance ledger). Pure function of its inputs.

    card_system opt-in: adds the glass-panel / icon-grid / numbered-cards
    archetypes to the planning pool. Off by default to preserve determinism.
    speaker_notes: generate a speaker script for every page (a page's
    own `notes` field always wins). Default on for composed decks.
    scoring opt-in: rank archetypes by deterministic content fitness instead
    of rng.shuffle, so the same notes yield the same layout plan under every
    seed. Off by default; the legacy shuffled plan stays byte-identical.
    design_briefs: optional dict keyed by page index (int/str) or page id,
    carrying the HOST MODEL's per-page design decision (the "model as per-page
    designer" first principle). Each value may set:
      - "archetype": a pool archetype name to pin, or "__host__" to defer the
        page to host rendering (engine emits an empty placeholder slide);
      - "carrier" / "structure" / "visual_anchor" / "image_decision" /
        "rationale": the designer's reasoning, recorded onto the slide for
        auditability and preserved verbatim in the output.
    When a page has no brief, compose() falls back to the deterministic
    archetype pool. design_briefs is additive: it never changes the no-brief
    behavior, so existing deterministic decks are unaffected.
    """
    book = notes.get("book") or {}
    pages = notes.get("pages") or []
    if not pages:
        raise ValueError("notes.pages is empty")

    # Long-deck guard: a flat 14-archetype file cannot satisfy the variety
    # gate past the chapter cap. Require chapter pages (or an explicit
    # override) BEFORE any geometry work, so the failure is a planning error
    # instead of a 40-error lint dump at build time.
    chapter_count = sum(1 for p in pages if p.get("kind") == "chapter")
    forced = bool(notes.get("allow_long_deck"))
    if len(pages) > CHAPTER_PAGE_CAP and chapter_count == 0 and not forced:
        raise ValueError(
            f"notes.pages has {len(pages)} pages but no chapter pages "
            f"(kind='chapter'); the {len(ARCHETYPES)}-archetype pool caps a "
            f"single flat file at {CHAPTER_PAGE_CAP} pages. Split the notes "
            f"into chapters, or set notes.allow_long_deck=true to accept the "
            f"lint diagnostics and build with --force.")

    # ---- 逐页设计闸门（第一性原理的可执行落点） ----
    # 创作类 deck 由宿主大模型先逐页写设计简报，引擎才接手。没有简报就调
    # compose，等于把「读懂内容 → 判断怎么表达」整个跳过，退回「从原型池
    # 挑一个往里填」——那正是被否定的做法，所以在入口直接失败，而不是产出
    # 一本百页同构 deck 之后由人发现。
    #
    # 两条合法出路：
    #   1) 传 design_briefs（推荐：逐页写清载体/结构/主视觉/配图/理由）；
    #   2) notes 顶层写 brief_pool="prototype"（显式声明这批页确实适合原型，
    #      接受兜底；留痕进 ledger 与 lint 报告，不静默）。
    pool_declared = str(notes.get("brief_pool") or "").strip().lower() in (
        "prototype", "pool", "fallback")
    if not design_briefs and not pool_declared:
        raise ValueError(
            "compose() 需要逐页设计简报（design_briefs）。\n"
            "第一性原理要求先读懂这一页的内容、再判断怎么表达最有效；"
            "载体（图 / 原生 SVG / 纯字版面 / 数据可视化）是想清楚之后的结果，"
            "不是从模板库里挑一个往里填。没有简报就编排，会退回"
            "「按内容条数选原型」的套版路径。\n"
            "两种做法（任选其一）：\n"
            "  1) 传 design_briefs：{页索引或页id: {carrier, structure, "
            "visual_anchor, image_decision, rationale}}；\n"
            "     需要宿主亲手画某页时把该页 archetype 设为 \"__host__\"；\n"
            "  2) 若这批页确实就是标准原型（固定报告/纯数据页），"
            "在 notes 顶层写 \"brief_pool\": \"prototype\" 显式声明走兜底。\n"
            f"本次 notes 共 {len(pages)} 页，未收到任何 design_briefs。")

    # resolve cover relative to the notes file
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
    plan = plan_archetypes(pages, rng, card_system=card_system, scoring=scoring)

    # Overlay host-model design briefs (the "model as per-page designer" first
    # principle). A brief may pin a pool archetype or mark the page HOST_RENDERED
    # to defer rendering to the host (e.g. a hand-authored SVG). Pages with no
    # brief keep the deterministic pool assignment.
    plan_final = list(plan)
    host_pages = set()
    briefs_by_idx = {}
    if design_briefs:
        for i, page in enumerate(pages):
            b = _resolve_brief(design_briefs, i, page)
            if not b:
                continue
            briefs_by_idx[i] = b
            choice = b.get("archetype")
            if choice == HOST_RENDERED:
                plan_final[i] = HOST_RENDERED
                host_pages.add(i)
            elif choice in ARCHETYPES:
                plan_final[i] = choice
            # else: leave pool plan[i] (engine fallback)
    S = _style(derived, base)
    # In card mode, dark slides may borrow the base theme's signature gradient
    # (derived themes inherit the base visual tokens unless they override them).
    theme_grad = T.get_theme(base)["visual"].get("background_gradient")

    slides = []
    for i, page in enumerate(pages):
        arch = plan_final[i]
        brief = briefs_by_idx.get(i)
        ctx = {"idx": i, "total": len(pages), "rng": rng, "book": book,
               "cover_file": cover_file, "cover_credit": page.get("source")}
        if i in host_pages:
            # Host model renders this page itself (e.g. hand-authored SVG).
            # Emit a placeholder so deck structure stays intact; children empty.
            slide = {
                "type": "content", "tone": "light", "surface": "paper",
                "composition": "freeform", "archetype": HOST_RENDERED,
                "density": "custom", "role": page.get("kind", "content"),
                "children": [], "host_rendered": True,
                "design_brief": brief,
            }
        else:
            kids, surface, tone, density = ARCHETYPES[arch]["build"](page, S, ctx)
            slide = {
                "type": "content", "tone": tone, "surface": surface,
                "composition": "freeform", "archetype": arch, "density": density,
                "role": page.get("kind", "content"),
                "children": kids, "design_brief": brief,
            }
        if card_system and tone == "dark" and theme_grad:
            slide["gradient"] = "theme"
        # A page may carry its own verbatim notes; otherwise the
        # generator derives a deterministic spoken script from its content.
        if speaker_notes:
            slide["notes"] = page.get("notes") or _speaker_notes(page, arch, ctx)
        # Research demand and provenance pass through to the slide level so
        # the lint gate can verify them.
        if page.get("research") is not None:
            slide["research"] = page["research"]
        if page.get("sources"):
            slide["sources"] = page["sources"]
        if page.get("source"):
            slide["source"] = page["source"]
        slides.append(slide)

    boundaries = [i for i, p in enumerate(pages) if p.get("kind") == "chapter"]
    deck = {
        "composed": True,
        "composition": "freeform",
        # 顶层留痕：lint 与审计读顶层字段，不能只写在 art_direction 子对象里，
        # 否则「显式声明走兜底」在闸门看来等于没声明（会自相矛盾地拦下来）。
        "brief_pool": bool(pool_declared),
        "theme": base,
        "assets_base": assets_base,
        "slides": slides,
        "art_direction": {
            "seed": seed, "archetypes": plan_final,
            "distinct": len(set(plan_final)), "pages": len(plan_final),
            "chapters": len(boundaries) + (1 if pages else 0),
            "chapter_boundaries": boundaries,
            "long_deck_forced": forced and len(pages) > CHAPTER_PAGE_CAP,
            "motif": S["motif"],
            "cover": ledger.get("cover_path"),
            "card_system": bool(card_system),
            "speaker_notes": bool(speaker_notes),
            "scoring": bool(scoring),
            "brief_pool": bool(pool_declared),
            "design_briefs_applied": len(briefs_by_idx),
            "engine_version": 3,
        },
    }
    deck["derived_theme"] = derived
    ledger["archetypes"] = plan_final
    ledger["distinct"] = len(set(plan_final))
    if host_pages:
        ledger["host_rendered_pages"] = sorted(host_pages)
    if briefs_by_idx:
        ledger["design_briefs_applied"] = len(briefs_by_idx)
    ledger["seed"] = seed
    ledger["chapter_boundaries"] = boundaries
    ledger["chapters"] = len(boundaries) + (1 if pages else 0)
    ledger["long_deck_forced"] = forced and len(pages) > CHAPTER_PAGE_CAP
    ledger["scoring"] = bool(scoring)

    # ---- 六维设计规格闸门（最高原则的执行体） ----
    # 前面只保证了「有 design_briefs」，但一个 brief 可能只有 5 个字。这里用
    # 六维规格逐页校验：布局结构 / 视觉层级 / 组件拆分与状态 / 响应式 /
    # 可访问性 / 设计一致性。缺任一项直接失败，不提供 --force。
    # 例外：显式声明 brief_pool="prototype" 的标准原型 deck 不走六维闸门——
    # 但该声明会进 ledger 留痕，且 audit-design/audit-pptx 仍会拦套版。
    #
    # 关键修复（2026-11-13）：design_system 必须**写进产物**再校验。
    # 之前这里是 `deck.get("design_system")`，可 compose 从来没往 deck 里放过
    # 这个键——于是每页 consistency 引用的令牌都是在跟 None 比对，
    # 「统一设计语言」这条判据实际上一直空转。现在先落到 deck 上，再校验。
    if isinstance(notes.get("design_system"), dict):
        deck["design_system"] = notes["design_system"]

    if briefs_by_idx and not pool_declared:
        from engine import design_spec
        spec_stats = design_spec.require_deck(
            slides, design_system=deck.get("design_system"))
        ledger["design_spec"] = {
            "pages_with_spec": spec_stats["with_spec"],
            "structure_counts": {k: len(v) for k, v
                                 in spec_stats["structure_counts"].items()},
            "tokens_declared": sorted(
                (deck.get("design_system") or {}).keys()),
        }

    return deck, ledger


def main(argv=None):
    ap = argparse.ArgumentParser(description="FreePPT creative composition")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("compose")
    p.add_argument("notes")
    p.add_argument("--cover")
    p.add_argument("--base", default="magazine")
    p.add_argument("--seed")
    p.add_argument("--card-system", action="store_true",
                   help="enable glass-panel / icon-grid / numbered-cards archetypes")
    p.add_argument("--scoring", action="store_true",
                   help="rank archetypes by deterministic content-fit score")
    p.add_argument("--brief",
                   help="JSON file: per-page design briefs (model as per-page "
                        "designer). Keyed by page index (int/str) or page id.")
    p.add_argument("--out")
    p.add_argument("--ledger")
    args = ap.parse_args(argv)

    notes_path = os.path.abspath(args.notes)
    notes = json.load(open(notes_path, encoding="utf-8"))
    design_briefs = None
    if args.brief:
        with open(os.path.abspath(args.brief), encoding="utf-8") as bf:
            design_briefs = json.load(bf)
    deck, ledger = compose(notes, os.path.dirname(notes_path), args.cover,
                           args.base, args.seed, card_system=args.card_system,
                           scoring=args.scoring, design_briefs=design_briefs)
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
