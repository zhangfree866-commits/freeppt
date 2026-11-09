#!/usr/bin/env python3
"""M4：规划层 -> 无坐标 Deck Plan（Page Spec 集合）。

四层融合管线的衔接件：compose() 做完 archetype 规划后，调用 build_deck_plan()
把 (notes, plan, S) 三个【无坐标】结构固化成 plan.json，供：
  · SVG 创作面逐页取内容（不自己猜标题/要点/数据）
  · svg_guard 做 CONTRAST/CAPACITY/DENSITY/FACT 校验

与旧 JSON DSL 的区别：这里不含任何坐标，只描述"这页讲什么、装多少、密度档位"，
怎么排版完全交给 SVG 创作层。
"""
from engine import art_direction as AD
from engine import themes as T

W, H, DPI = 1280, 720, 96


def _datasets(page, arch):
    """从 page 的数据字段提取归一化数据集；识别不到返回空列表。

    覆盖：chart（原生图表）、value/kpi（单 KPI）、kind=timeline（时间轴）。
    """
    out = []
    ch = page.get("chart")
    if isinstance(ch, dict) and ch.get("series"):
        ds = {"type": ch.get("kind", "column"),
              "series": ch["series"]}
        if ch.get("categories"):
            ds["categories"] = ch["categories"]
        if ch.get("unit"):
            ds["unit"] = ch["unit"]
        if ch.get("title"):
            ds["title"] = ch["title"]
        out.append(ds)
    # 单 KPI（data-focus 的输入：value/kpi + label）
    val = page.get("value", page.get("kpi"))
    if val is not None and not ch:
        ds = {"type": "kpi", "series": [val]}
        lab = page.get("label")
        if lab:
            ds["title"] = lab
        if page.get("unit"):
            ds["unit"] = page["unit"]
        out.append(ds)
    # 时间轴页（年份/事件序列）
    if page.get("kind") == "timeline":
        years = page.get("years") or page.get("events")
        if years:
            out.append({"type": "timeline", "series": years})
    return out


def _chapter_name(page, index, boundaries, chapter_no):
    """章节标签：优先显式 chapter 字段；封面/章节页给可读名，其余用序号。"""
    if page.get("chapter"):
        return page["chapter"]
    kind = page.get("kind", "content")
    if kind == "cover":
        return "封面"
    if kind == "closing":
        return "结语"
    if kind == "chapter":
        return page.get("title") or f"第 {chapter_no} 章"
    return f"第 {chapter_no} 章"


def _sources(page):
    if isinstance(page.get("sources"), list):
        return page["sources"]
    if page.get("source"):
        return [page["source"]]
    return []


def build_page_spec(page, arch, index, boundaries):
    """单页 -> 归一化 Page Spec（无坐标）。"""
    kind = page.get("kind", "content")
    chapter_no = AD.chapter_of(index, boundaries)
    # 数据页：KPI/图表进 datasets，正文要点只取显式 points（不让 KPI 混入要点）
    datasets = _datasets(page, arch)
    points = AD._explicit_points(page)
    # compare 页（left/right）在无显式 points 时仍保留两侧语义
    if not points:
        points = [{"head": pt["head"], "body": pt["body"]}
                  for pt in AD._points(page)
                  if pt["head"] or pt["body"]] \
            if (page.get("left") or page.get("right")) else []
    return {
        "index": index,
        "kind": kind,
        "chapter": _chapter_name(page, index, boundaries, chapter_no),
        "archetype": arch,
        "title": page.get("title", ""),
        "kicker": page.get("kicker", ""),
        "lead": page.get("lead", ""),
        "points": points,
        "quote": page.get("quote", ""),
        "compare": ({"left": page.get("left"), "right": page.get("right")}
                    if (page.get("left") or page.get("right")) else {}),
        "datasets": datasets,
        "capacity": AD.MAX_POINTS.get(arch),
        "density_hint": AD.ARCHETYPES[arch]["density"],
        "sources": _sources(page),
        "notes": page.get("notes", ""),
    }


def _style_lock(S, base):
    if S is None:
        S = AD._style(None, base)
    th = T.get_theme(base)
    font_stack = (th.get("typography") or {}).get("font", "")
    return {
        "colors": {
            "ink": S["ink"], "body": S["body"], "muted": S["muted"],
            "accent": S["accent"], "accent_bright": S.get("accent2", S["accent"]),
            "paper": S["paper"], "card": S["card"], "line": S["line"],
        },
        "fonts": {"stack": font_stack},
    }


def build_deck_plan(notes, plan, S, base="magazine"):
    """整份 notes + archetype plan -> Deck Plan 字典（可直接 json.dump）。"""
    pages_in = notes.get("pages") or []
    boundaries = [i for i, p in enumerate(pages_in) if p.get("kind") == "chapter"]
    specs = [build_page_spec(p, a, i, boundaries)
             for i, (p, a) in enumerate(zip(pages_in, plan))]
    book = notes.get("book") or {}
    return {
        "canvas": {"width": W, "height": H, "dpi": DPI},
        "deck": {
            "title": book.get("title", ""),
            "author": book.get("author", ""),
            "language": book.get("language", "zh-CN"),
            "total_pages": len(specs),
        },
        "style_lock": _style_lock(S, base),
        "chapter_boundaries": boundaries,
        "pages": specs,
    }
