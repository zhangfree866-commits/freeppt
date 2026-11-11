"""对已生成的 .pptx 做几何骨架审计——不看 DSL，只看最终产物。

存在的理由（这是这套闸门曾经最大的漏口）：

原有的逐页设计闸门全部挂在 DSL / `compose()` 上。只要有人绕开
`compose()`、自己写 Python 拼 pptx（历史上那套 122 页「顾问式营销」就是
这么来的：`lib.py` 1011 行、22 个 `p_*` 页面函数、`deck.json` 里 122 页
`design_brief` 全空），闸门一次都不会执行，产物照样交付。

所以判据必须能落在**最终 pptx 的坐标**上。这里复用
`layout_fingerprint.skeleton()`（同一套分带指纹），把 python-pptx 读出的
`rect_px` 转成它认识的 slide 结构，再跑同一套分组阈值。

为什么坐标能直接用：`pptx_edit._px()` 已经把 EMU 换算成 px，画布 1280×720
与 DSL 侧一致，不需要重新标定。
"""

from . import layout_fingerprint as _lf

# 从 pptx 形状名 / 文本推断「仪式页」。手写脚本通常不起 archetype，所以
# 只能靠页内文本特征：封面页文字少、章节页通常只有短标题。宁可少豁免
# （多抓几页），也不要因为认不出仪式页而误伤——误伤会在报告里明说。
_RITUAL_TEXT_MAX = 24


def _kind_of(shape):
    """把 python-pptx 形状折算成骨架角色。

    与 DSL 侧 `_kind()` 对齐：有文字的块记 "slab"，纯装饰记 "deco"。
    图片单独记 "image"，因为它对版式的意义和色块不同。
    """
    stype = str(shape.get("type") or "")
    if "PICTURE" in stype:
        return "image"
    if "TABLE" in stype:
        return "table"
    if "CHART" in stype:
        return "chart"
    if (shape.get("text") or "").strip():
        return "slab"
    return "deco"


def slides_from_report(report):
    """把 `pptx_edit.inspect()` 的报告转成 `layout_fingerprint` 的输入。

    `rect_px` 缺失或非法的形状直接跳过——读不到坐标就不能参与几何判定，
    但会计入 `unreadable` 计数，避免静默丢失证据。
    """
    slides = []
    unreadable = 0
    for s in report.get("slides") or []:
        kids = []
        texts = []
        for sh in s.get("shapes") or []:
            rect = sh.get("rect_px")
            if not (isinstance(rect, (list, tuple)) and len(rect) >= 4):
                unreadable += 1
                continue
            try:
                rect = [float(v) for v in rect[:4]]
            except (TypeError, ValueError):
                unreadable += 1
                continue
            text = (sh.get("text") or "").strip()
            if text:
                texts.append(text)
            kids.append({"t": _kind_of(sh), "rect": rect, "text": text})
        slides.append({"children": kids, "_text_len": sum(len(t) for t in texts)})
    return slides, unreadable


def _guess_ritual(slide):
    """文本极少的页视为仪式页（封面/章节/封底）的候选，用于豁免。

    这是个启发式，故意保守：只有全页文字总量很小才算。真正的内容页
    即使只有一句大标题，通常也配有说明文字，总量超过阈值。
    """
    return slide.get("_text_len", 0) <= _RITUAL_TEXT_MAX


def audit_pptx(report, max_pages=5, bands=_lf.DEFAULT_BANDS):
    """审计一份 pptx 结构报告的骨架重复情况。

    返回 dict：
        ok            无超限骨架组
        slide_count   总页数
        groups        超限组 [{"pages": [...], "count": n}]
        unreadable    读不到坐标的形状数（0 才说明审计完整覆盖）
        exempted      被当作仪式页豁免的页码
    """
    slides, unreadable = slides_from_report(report)
    total = len(slides)

    # 先按指纹分组，仪式页在分组后再剔除——这样即使臆断错了豁免，
    # 也只是少报，不会把内容页的重复算成两组。
    groups = {}
    exempted = []
    for i, slide in enumerate(slides, 1):
        if total > 3 and _guess_ritual(slide):
            exempted.append(i)
            continue
        fp = _lf.skeleton(slide, bands=bands)
        if fp is None:
            continue
        groups.setdefault(fp, []).append(i)

    limit = max_pages if max_pages is not None else 5
    hits = sorted(((fp, pages) for fp, pages in groups.items()
                   if len(pages) >= limit),
                  key=lambda kv: -len(kv[1]))

    return {
        "ok": not hits,
        "slide_count": total,
        "groups": [{"count": len(pages), "pages": pages} for _fp, pages in hits],
        "unreadable": unreadable,
        "exempted": exempted,
        "threshold": limit,
    }
