"""几何骨架指纹：兜底判据，抓「简报写了但版面还是抄上一页」的情况。

判据设计上的取舍（实测记录，见 tests/test_design_brief.py）：

* **不听自报标签**。实验证明把 12 页同构页的 `archetype` 改成 12 个不同
  名字、几何一字不动，旧闸门仍 `ok=True`。所以这里只读坐标。
* **不做精确指纹比对**。精确比对会被「内容长短不同导致文字宽度不同」干扰，
  真同构页反而分到不同组。改成宽松指纹 + 允许少量重复（见 `find_repeats`
  的 `max_pages`），宁可漏一点，不要误伤正常版式。
* **仪式页豁免**。一本书 11 个章节页长得一样是对的，那不是套模板。

这套判据是兜底，不是主判据：主判据是「每页必须写设计简报」和「结构声明
不许大面积为同一个值」，两者都是确定性判定，没有阈值。
"""

DEFAULT_BANDS = 10

# 单一节点参与指纹计算的最大跨度（占画布宽度比例）。整宽背景块只标记
# 起点所在分区，不会把整页刷成"全覆盖"从而遮蔽真实结构差异。
SPAN_CAP_RATIO = 0.125

# 仪式页：同构是设计要求本身，必须排除在「版式重复」判定之外。
RITUAL_ROLES = frozenset({"cover", "chapter", "closing", "section"})


def _rect(node):
    r = node.get("rect")
    if not (isinstance(r, (list, tuple)) and len(r) >= 4):
        return None
    try:
        return float(r[0]), float(r[1]), float(r[2]), float(r[3])
    except (TypeError, ValueError):
        return None


def _kind(node):
    """节点在骨架里的角色：有字的色块和没字的装饰条对版式意义不同。"""
    t = node.get("t") or "?"
    if t == "shape":
        return "slab" if str(node.get("text") or "").strip() else "deco"
    return t


def _iter_nodes(slide):
    """只遍历顶层与一层嵌套：更深嵌套属于同一块内容内部，不构成版式差异。"""
    for node in slide.get("children") or []:
        if not isinstance(node, dict):
            continue
        yield node
        for kid in node.get("children") or []:
            if isinstance(kid, dict):
                yield kid


def _infer_canvas_width(slide):
    """从节点坐标推断画布宽度，避免对 1280/1920 硬编码。"""
    right = 0.0
    for node in _iter_nodes(slide):
        r = _rect(node)
        if r:
            right = max(right, r[0] + r[2])
    if right <= 0:
        return None
    for w in (1280, 1440, 1600, 1920, 2560, 3840):
        if right <= w * 1.02:
            return w
    return right


def skeleton(slide, canvas_w=None, bands=DEFAULT_BANDS):
    """该页的几何骨架指纹。相同指纹 = 同一副版面骨架。

    指纹 = 排序后的 (起点带, 终点带, 节点角色) 集合。
    刻意不含纵向坐标：同一副骨架上下平移仍是同构，那正是套模板的形态。
    """
    if canvas_w is None:
        canvas_w = _infer_canvas_width(slide)
    if not canvas_w:
        return None
    band_w = float(canvas_w) / bands
    span_cap = float(canvas_w) * SPAN_CAP_RATIO
    cells = set()
    for node in _iter_nodes(slide):
        r = _rect(node)
        if not r:
            continue
        x, _y, w, _h = r
        start = int(x / band_w)
        end = int((x + min(w, span_cap)) / band_w)
        start = max(0, min(bands - 1, start))
        end = max(start, min(bands - 1, end))
        cells.add((start, end, _kind(node)))
    return tuple(sorted(cells)) or None


def is_ritual(slide):
    """封面 / 章节页 / 封底属于仪式页，允许同构。"""
    role = str(slide.get("role") or "").strip().lower()
    if role in RITUAL_ROLES:
        return True
    arch = str(slide.get("archetype") or "").strip().lower()
    return arch in ("cover-editorial", "chapter-opener", "closing-echo")


def find_repeats(slides, max_pages=None, bands=DEFAULT_BANDS):
    """找出单组页数超限的骨架分组。

    **实测结论（重要，别再改回比例判据）**：
    试过「骨架密度（内容页数 / 骨架数）」做判据，被数据否掉了——
    正常产物 16 页落进 5 个骨架（3.2 页/骨架），翻车样本 109 页落进
    38 个骨架（2.87 页/骨架），两个数字几乎一样，密度分不开好坏。
    原因也合理：一个正常 deck 的 16 页本来就只会用到五六种原型。

    真正分得开的是**单组绝对页数**：正常样本最大一组 4 页，翻车样本
    11 / 8 / 8 / 7 / 7 页。所以只用这一条，默认阈值 5。

    这个判据是兜底，不是主判据——主判据是「每页必须写设计简报」和
    「structure 标签不许成片重复」，两者都不依赖阈值。骨架判据只负责
    抓「简报写得花哨、版面照抄」这种绕过行为。

    返回 [(骨架, [页码...]), ...]，只返回超限的组，无问题返回空列表。
    """
    groups = {}
    for i, slide in enumerate(slides, 1):
        if not isinstance(slide, dict) or is_ritual(slide):
            continue
        fp = skeleton(slide, bands=bands)
        if fp is None:
            continue
        groups.setdefault(fp, []).append(i)

    if not groups:
        return []

    limit = max_pages if max_pages is not None else 5
    return sorted(
        ((fp, pages) for fp, pages in groups.items() if len(pages) >= limit),
        key=lambda kv: -len(kv[1]))
