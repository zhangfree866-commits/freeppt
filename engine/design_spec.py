"""把「模型逐页当设计师」落实成**可执行的六维规格 + 硬闸门**。

## 为什么重写

原版只有 5 个字段（载体/结构/主视觉/配图/理由），而且 `check_deck()` **没有任何
调用方**——写了判据却没人调用，等于文档。这次改成：

1. **六维规格**：原 5 项 → 布局结构、视觉层级、组件拆分与交互状态、
   响应式适配、可访问性、设计一致性。这是「一页的完整设计方案」的最小子集。
2. **真正接进流水线**：`compose()` 入口调用 `check_deck()`，任一页缺项即
   `ValueError`，与「没传 design_briefs」同级阻断。不再有「写了没人用」。
3. **三件交付物**：`design_spec`（逐页方案）→ `page_contract`（编译约束）
   → `verify_spec_compiled()`（成品回验）。逐页设计、逐页交付、逐页校验。
4. **一致性由 deck 级令牌锁定**：`design_system` 必须在 deck 顶层声明一次，
   每页只能引用，不能各写一套——这就是「统一设计语言」的可检查形态。

## 六个维度的判定口径

| 维度 | 字段 | 什么算填了 | 为什么必须 |
|---|---|---|---|
| 布局结构 | `structure` | ≥2 字，且不是「同上」 | 骨架必须逐页判断，不能复用 |
| 视觉层级 | `hierarchy` | ≥8 字，须含层级词（主/次/辅/第一/第二/焦点…） | 说不出谁第一眼，就是平铺 |
| 组件拆分 | `components` | list，≥2 项，每项有 name+role | 组件无角色 = 堆形状 |
| 交互状态 | `states` | list 或 dict，非空 | 静态页也要有 hover/强调/禁用态的判断 |
| 响应式 | `responsive` | ≥6 字，须含断点或缩放策略 | 换尺寸不塌，是设计不是排版 |
| 可访问性 | `a11y` | dict，须有 contrast/text_size/alt 里至少 2 项 | 对比度、字号、替代文本 |
| 一致性 | `consistency` | 引用 deck 令牌的键名，且这些键在 deck 里真实存在 | 防每页各造一套配色 |

`rationale` 仍保留：它是「为什么这页这样最有效」的自证，归在 structure 维度。

## 冲突时的优先级

本模块的判据是**最高原则的执行体**。与任何通用建议冲突时（例如「模板更快」
「套原型更省 token」「响应式在 PPT 里没意义」），一律以本判据为准：
缺项就编译不出来，不提供 `--force` 旁路。理由：旁路一旦存在，原则就退回建议。
"""

import re

# --------------------------------------------------------------------------- #
# 六维规格定义
# --------------------------------------------------------------------------- #

#: 每一维都是「这页想清楚了」的必要证据。顺序即汇报顺序。
SPEC_FIELDS = (
    "structure",     # 布局结构：这页用什么骨架（自由描述，不许复用标签）
    "hierarchy",     # 视觉层级：第一眼/第二眼/辅助信息分别是什么
    "components",    # 组件拆分：拆成哪几块，每块扮演什么角色
    "states",        # 交互/强调状态：默认、强调、弱化、禁用等
    "responsive",    # 响应式适配：窄屏/宽屏/投影时的伸缩策略
    "a11y",          # 可访问性：对比度、最小字号、替代文本
    "consistency",   # 设计一致性：引用 deck 令牌的哪些键
    "rationale",     # 为什么这页这样表达最有效
)

#: 必填维度（全部必填——这是一页完整方案，不是可选项清单）
REQUIRED_FIELDS = SPEC_FIELDS

#: 纯文本字段的最短有效长度。低于此值视为敷衍。
MIN_LEN = {
    "structure": 2,
    "hierarchy": 8,
    "responsive": 6,
    "rationale": 12,
}

#: 占位话术：命中即视为没填。
PLACEHOLDER = re.compile(
    r"^\s*(?:"
    r"tbd|todo|n/?a|none|null|无|待定|待补|略|同上|"
    r"见上|见前|see above|same as (?:above|previous)|"
    r"[\-—_.·\s]+"
    r")\s*$",
    re.IGNORECASE,
)

#: hierarchy 必须出现的层级词。说不出「谁第一眼」，就是所有东西一样重。
HIERARCHY_MARKERS = (
    "主", "次", "辅", "第一", "第二", "第三", "焦点", "首要", "重点",
    "primary", "secondary", "tertiary", "focus", "anchor",
)

#: responsive 必须体现的策略词。空泛写「自适应」不算。
RESPONSIVE_MARKERS = (
    "断点", "窄", "宽", "缩放", "折叠", "换行", "堆叠", "重排", "压缩",
    "breakpoint", "narrow", "wide", "scale", "stack", "reflow", "shrink",
    "%", "px", "pt",
)

#: a11y 必须覆盖的检查项，至少命中 2 项。
A11Y_KEYS = ("contrast", "text_size", "alt", "contrast_ratio",
             "min_font", "reading_order", "focus_visible")

#: 允许的交互状态词（自由填写，仅用于诊断，不做硬校验）
STATE_HINTS = ("default", "hover", "focus", "active", "disabled",
               "emphasis", "muted", "selected", "默认", "强调", "弱化",
               "禁用", "选中", "悬停")

#: 同一结构标签的页数上限。3 页算巧合，4 页说明在复用同一判断。
MAX_SAME_STRUCTURE = 3

#: deck 级设计令牌必须包含的键。每页 consistency 只能引用这些键。
REQUIRED_TOKENS = (
    "palette",       # 配色
    "type_scale",    # 字号阶梯
    "spacing",       # 间距节奏
    "font_pair",     # 双字体（标题衬线 + 正文黑体）
)


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return ""
    return str(value).strip()


def _is_filled(value):
    """非空且不是占位话术。"""
    if value is None:
        return False
    if isinstance(value, str):
        v = value.strip()
        return bool(v) and not PLACEHOLDER.match(v)
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return True


def _count_list_items(value):
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


# --------------------------------------------------------------------------- #
# 单页校验：六维
# --------------------------------------------------------------------------- #

def check_brief(slide, page_no, design_system=None, is_host_rendered=False):
    """校验单页的六维设计规格。返回问题列表（空 = 通过）。

    design_system 传入 deck 级令牌时，额外校验 consistency 引用的键真实存在。
    """
    problems = []
    brief = slide.get("design_brief") or slide.get("design_spec")

    if not brief or not isinstance(brief, dict):
        problems.append(
            f"第 {page_no} 页没有 design_spec：这一页没有经过「设计师」判断，"
            f"退回模板池直接套版。请先读懂这页内容，再写清六个维度："
            f"{' / '.join(SPEC_FIELDS)}")
        return problems

    # --- 纯文本维度 ---
    for field in ("structure", "hierarchy", "responsive", "rationale"):
        val = _text(brief.get(field))
        if not _is_filled(val):
            problems.append(
                f"第 {page_no} 页缺 {field}（或写成占位话术）："
                f"这一维没有真正判断")
            continue
        need = MIN_LEN[field]
        if len(val) < need:
            problems.append(
                f"第 {page_no} 页的 {field} 只有 {len(val)} 字"
                f"（至少 {need} 字）：太短说明这一维没有展开")

    # hierarchy 必须有层级词
    hier = _text(brief.get("hierarchy"))
    if _is_filled(hier) and len(hier) >= MIN_LEN["hierarchy"]:
        low = hier.lower()
        if not any(m in low for m in HIERARCHY_MARKERS):
            problems.append(
                f"第 {page_no} 页的 hierarchy「{hier[:24]}…」没有层级词："
                f"看不出谁是第一眼、谁是辅助信息，等于所有元素一样重")

    # responsive 必须有具体策略
    resp = _text(brief.get("responsive"))
    if _is_filled(resp) and len(resp) >= MIN_LEN["responsive"]:
        low = resp.lower()
        if not any(m in low for m in RESPONSIVE_MARKERS):
            problems.append(
                f"第 {page_no} 页的 responsive「{resp[:24]}…」没有具体策略："
                f"要写清断点、折叠还是缩放，不能只写「自适应」")

    # --- components：至少 2 块，每块要有名字和角色 ---
    comps = brief.get("components")
    if not _is_filled(comps):
        problems.append(
            f"第 {page_no} 页缺 components：没拆组件说明只是在堆形状，"
            f"没有「这块承担什么」的判断")
    else:
        n = _count_list_items(comps)
        if n < 2:
            problems.append(
                f"第 {page_no} 页的 components 只有 {n} 项："
                f"一页至少要有主结构与辅助结构两块")
        for idx, item in enumerate(_as_items(comps), 1):
            if isinstance(item, dict):
                if not _is_filled(item.get("name")) or \
                        not _is_filled(item.get("role")):
                    problems.append(
                        f"第 {page_no} 页的 components 第 {idx} 项缺 name 或 "
                        f"role：组件没有角色就是在堆形状")

    # --- states：交互/强调状态不能为空 ---
    states = brief.get("states")
    if not _is_filled(states):
        problems.append(
            f"第 {page_no} 页缺 states：即使静态页也要说明强调/弱化/禁用"
            f"时怎么变，否则成品无法承载交互或高亮")

    # --- a11y：至少覆盖 2 个检查项 ---
    a11y = brief.get("a11y")
    if not _is_filled(a11y):
        problems.append(
            f"第 {page_no} 页缺 a11y：至少写 contrast / text_size / alt")
    elif isinstance(a11y, dict):
        hit = [k for k in A11Y_KEYS if _is_filled(a11y.get(k))]
        if len(hit) < 2:
            problems.append(
                f"第 {page_no} 页的 a11y 只覆盖 {len(hit)} 项"
                f"（至少 2 项，应为 contrast / text_size / alt 中的两项）")
    else:
        txt = _text(a11y)
        if len(txt) < 8:
            problems.append(
                f"第 {page_no} 页的 a11y 太短：至少要写对比度、最小字号、"
                f"替代文本")

    # --- consistency：引用的令牌必须真实存在 ---
    cons = brief.get("consistency")
    if not _is_filled(cons):
        problems.append(
            f"第 {page_no} 页缺 consistency：没声明沿用哪些设计令牌，"
            f"就会各页自造一套，整本不像同一本书")
    elif design_system is not None:
        refs = _token_refs(cons)
        if not refs:
            problems.append(
                f"第 {page_no} 页的 consistency 没有引用任何令牌键："
                f"应为 {' / '.join(REQUIRED_TOKENS)} 中的若干项")
        else:
            missing = [r for r in refs if r not in design_system]
            if missing:
                problems.append(
                    f"第 {page_no} 页的 consistency 引用了不存在的令牌："
                    f"{' / '.join(missing)}。deck 级设计系统里只有 "
                    f"{' / '.join(sorted(design_system))}")

    return problems


def _as_items(value):
    """把 list / dict 统一成可迭代的项。"""
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _token_refs(cons):
    """从 consistency 里取出令牌键名。

    支持三种写法：list（["palette","type_scale"]）、dict（{"palette": "沿用"}）、
    字符串（"palette / type_scale"）。
    """
    if isinstance(cons, (list, tuple)):
        return [str(x).strip() for x in cons if str(x).strip()]
    if isinstance(cons, dict):
        return [str(k).strip() for k in cons if str(k).strip()]
    txt = _text(cons)
    if not txt:
        return []
    parts = re.split(r"[\s,，/、;；|]+", txt)
    return [p for p in parts if p]


# --------------------------------------------------------------------------- #
# 整本校验
# --------------------------------------------------------------------------- #

def check_deck(slides, design_system=None):
    """整本六维校验。返回 (blockers, stats)。

    除逐页六维外，还检查三件「整本才看得出来」的事：
    1. 结构标签成片重复（>MAX_SAME_STRUCTURE 页）
    2. deck 级设计令牌缺失
    3. 每页 consistency 引用的令牌是否都存在
    """
    blockers = []
    stats = {
        "pages": len(slides),
        "with_spec": 0,
        "without_spec": [],
        "structure_counts": {},
        "template_pages": [],
        "token_refs": {},
    }

    # deck 级令牌：没有它，「统一设计语言」无从谈起
    ds = design_system if isinstance(design_system, dict) else {}
    if design_system is not None:
        missing_tokens = [t for t in REQUIRED_TOKENS if t not in ds]
        if missing_tokens:
            blockers.append((
                "DESIGN_SYSTEM_INCOMPLETE",
                f"deck 级设计系统缺 {len(missing_tokens)} 项令牌："
                f"{' / '.join(missing_tokens)}。没有统一令牌，各页就会自造"
                f"一套，整本不像同一本书"))

    for i, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            continue
        brief = slide.get("design_brief") or slide.get("design_spec")
        if isinstance(brief, dict):
            stats["with_spec"] += 1
        else:
            stats["without_spec"].append(i)

        for msg in check_brief(slide, i, design_system=(ds or None)):
            blockers.append(("DESIGN_SPEC_MISSING", msg))

        if isinstance(brief, dict):
            key = _text(brief.get("structure")).lower()
            if key and not PLACEHOLDER.match(key):
                stats["structure_counts"].setdefault(key, []).append(i)
            for ref in _token_refs(brief.get("consistency")):
                stats["token_refs"].setdefault(ref, []).append(i)

    # 结构标签成片重复 → 没有逐页判断
    for key, pages in sorted(stats["structure_counts"].items(),
                             key=lambda kv: -len(kv[1])):
        if len(pages) > MAX_SAME_STRUCTURE:
            shown = "、".join(str(p) for p in pages[:8])
            more = f" 等 {len(pages)} 页" if len(pages) > 8 else ""
            blockers.append((
                "STRUCTURE_REUSED",
                f"{len(pages)} 页都用了同一个结构标签「{key}」"
                f"（第 {shown}{more}）：同副骨架出现在这么多不同内容的页上，"
                f"说明这些页没有各自判断表达方式。请逐页重新判断"))

    return blockers, stats


# --------------------------------------------------------------------------- #
# 「规格有没有真的驱动版面」——把「填字段」和「当设计师」分开
# --------------------------------------------------------------------------- #
# 来历（2026-11-13，用户第二次报「生成的 PPT 又没按 skill 做」）：
# 六维规格接上闸门之后，一个更隐蔽的问题浮出来——规格**填了，但没生效**。
# compose() 里唯一读进几何的 brief 字段只有 `archetype`；`structure` 里写的
# 「左列六个灰块、右侧一块亮起」被原样抄进 slide["design_brief"] 存档，
# 却对画面零影响。引擎照样按原型渲染出一个三条编号列表。
#
# 所以「模型逐页当设计师」的可检查形态不能只是「字段非空」，还得是
# **规格里的几何声明在成品里找得到**。这条判据就是那个断点。

# 几何语汇：规格里出现这些词，就应当能在成品里看到对应的形状特征。
GEOMETRY_VOCAB = {
    "grid": ("网格", "矩阵", "格", "grid", "matrix"),
    "circle": ("圆", "环", "同心", "circle", "ring", "radial"),
    "bar": ("柱", "条带", "横条", "bar", "band"),
    # 注意：「递进」不在词表里。它是逻辑递进，不是物理台阶——写「三段递进」
    # 的错位三联会被误判成声明了台阶。几何词只收几何词。
    "stair": ("阶梯", "台阶", "stair", "step"),
    "column": ("左列", "右列", "两列", "分栏", "column"),
    "quadrant": ("象限", "四格", "十字", "quadrant", "2×2"),
}


#: 否定语境词。判据只看「有没有说这个词」，但「不使用任何栏格」不属于声明。
#: 实测算过：quote-bleed 那页因为写了「不使用任何栏格」，被判成声明了 grid，
#: 于是「规格说网格、成品是整幅引言」——凭空造出一个脱钩。
_NEGATION_MARKERS = ("不", "无", "非", "没", "勿", "去掉", "取消", "避免",
                     "不用", "不做", "不设", "禁止", "排除")

#: 否定词生效的观察窗口（命中词往前看多少个字）。
_NEGATION_WINDOW = 8


def _in_negation(text, pos):
    """命中位置 pos 是否处在否定语境里。"""
    head = text[max(0, pos - _NEGATION_WINDOW):pos]
    return any(m in head for m in _NEGATION_MARKERS)


def _geometry_claims(text):
    """规格文本里声明了哪些几何语汇。

    带否定判定：「不使用任何栏格」「不做网格」不属于声明。早先只做子串
    匹配，于是「我决定不用网格」被读成「我要网格」，判据跟着造出假脱钩。
    """
    t = _text(text).lower()
    found = set()
    for key, words in GEOMETRY_VOCAB.items():
        for w in words:
            wl = w.lower()
            start = 0
            hit = False
            while True:
                pos = t.find(wl, start)
                if pos < 0:
                    break
                if not _in_negation(t, pos):
                    hit = True
                    break
                start = pos + len(wl)
            if hit:
                found.add(key)
                break
    return found


def _slide_geometry(slide):
    """一页成品**实际**呈现了哪些几何语汇。只看几何，不看任何自报名字。

    为什么不能用 archetype 名：`stair-list` 这个名字里有 "stair"，可它的实现
    只是每行缩进 34px 的编号列表——四行累计 100px，视觉上就是普通列表。用名字
    判断，判据会跟着一起被骗；这一版改成从坐标反推，名字说谎就会当场暴露。

    「算不算这种几何」用几何关系本身定义，而不是用阈值拍脑袋：
      stair    左缘与上缘同向严格递增，且累计偏移够大（≥80px）才有台阶感
      grid     横向和纵向都出现多个不同位置（2×2 起）
      bar      纵向位置少（1–2 行）、横向排开多个
      column   横向位置少、纵向堆叠多个
      circle   真有圆形/椭圆形状
      quadrant 有十字交叉线（横线 + 竖线都有）
    """
    found = set()
    rects = []
    shape_rects = []          # 只有「形状」的矩形，不含文字框
    kinds = []
    for c in (slide.get("children") or []):
        kind = f"{c.get('t', '')} {c.get('kind', '')}".lower()
        kinds.append(kind)
        r = c.get("rect") or c.get("box")
        if isinstance(r, (list, tuple)) and len(r) >= 4:
            try:
                t = tuple(float(v) for v in r[:4])
            except (TypeError, ValueError):
                t = None
            if t:
                rects.append(t)
                # 文字框的 rect 只是「排版留位」，不是视觉几何。把标题框
                # （y=58 一条横跨 1080px）算进内容块，会直接打乱台阶的
                # 「顶边单调」判断——实测就是它让真台阶被判成了网格。
                if "text" not in kind:
                    shape_rects.append(t)
        if any(k in kind for k in ("circle", "ellipse", "oval")):
            found.add("circle")

    if not rects:
        return found

    # 只拿「形状」说话：太细的线、太窄的装饰、页眉的小色条都不算结构。
    # 阈值取 60×48：台阶最矮的一级也有 156px 高，绝不会被误过滤。
    blocks = [r for r in shape_rects if r[2] >= 60 and r[3] >= 48]

    # 长横线 = 条带/时间轴的骨架。它太细，会被上面的 blocks 过滤掉，
    # 但「一条贯穿页面的横线」恰恰就是 bar/timeline 这类版式的几何证据。
    long_h = [r for r in rects if r[2] >= 400 and r[3] <= 8]
    if long_h:
        found.add("bar")

    # 长竖线 = 分栏线。这是最容易漏的一条：editorial-spread、cover-editorial
    # 都是「一条 2px 竖线把版面劈成左右两半」，但它们的内容块只是文字框，
    # 全被 shape_rects 排除了，于是 blocks 为空、actual 为空集，一个正常的
    # 左右分栏被判成「什么几何都没有」。实测就是这条让两页正路被误拦。
    long_v = [r for r in rects if r[3] >= 400 and r[2] <= 8]
    if long_v:
        found.add("column")

    if len(blocks) < 2:
        return found

    xs = sorted({round(r[0], 1) for r in blocks})
    ys = sorted({round(r[1], 1) for r in blocks})

    if len(xs) >= 2 and len(ys) >= 2:
        # 台阶的本质：按左缘排序后，顶边必须单调移动，且累计横移够大
        # （≥80px 才有台阶感，轻微缩进不算）。
        #
        # 方向要对：「向右上抬升」的台阶，左缘递增时顶边应当**递减**
        # （y 变小 = 更高）。所以这里判的是「严格单调」，不是「一起变大」。
        # 早先写成 top 与 left 同向递增，把真正的上升阶梯判成了普通网格。
        by_x = sorted(((r[0], r[1]) for r in blocks))
        left_up = all(by_x[i][0] <= by_x[i + 1][0]
                      for i in range(len(by_x) - 1))
        offset = abs(by_x[-1][0] - by_x[0][0]) if by_x else 0
        tops = [t for _, t in by_x]
        monotone_top = (all(tops[i] >= tops[i + 1] for i in range(len(tops) - 1))
                        or all(tops[i] <= tops[i + 1]
                               for i in range(len(tops) - 1)))
        if left_up and monotone_top and offset >= 80:
            found.add("stair")
        # 网格：横纵都要有**多个**位置（2×2 起）。早先这里是无条件
        # found.add("grid")，只要两个块位置不同就算网格——于是错位三联
        # 被判成网格，判据自己把「grid」变成了万能垃圾桶。
        if len(xs) >= 2 and len(ys) >= 2 and "stair" not in found:
            # 错落但不构成台阶、也不是单行单列 → 才是网格
            found.add("grid")
    if len(ys) <= 2 and len(xs) >= 3:
        found.add("bar")
    if len(xs) <= 2 and len(ys) >= 3:
        found.add("column")

    has_h = any("line" in k or "divider" in k for k in kinds)
    return found


def check_spec_drives_layout(slides):
    """规格声明的几何，必须在成品几何里找得到。返回 blockers。

    为什么这条比「六维非空」更要紧：六维非空只能证明模型**填了字段**，
    这条才证明模型**真的按自己说的那样排版**。前者可以被三分钟糊弄过去，
    后者不能——你要么改了版面，要么没改。
    """
    blockers = []
    for i, s in enumerate(slides, 1):
        if not isinstance(s, dict):
            continue
        brief = s.get("design_brief") or s.get("design_spec")
        if not isinstance(brief, dict):
            continue
        claims = _geometry_claims(
            " ".join(_text(brief.get(k)) for k in
                     ("structure", "components", "hierarchy")))
        if not claims:
            continue                      # 没声明几何语汇，不做此校验
        actual = _slide_geometry(s)
        children = s.get("children") or []
        # 只有「真正没有画任何东西」的页才免检（宿主手绘占位页）。
        # 早先写成 `if not actual: continue`——但那会把「规格说四象限、
        # 实际只有一个色块」这种最典型的脱钩也放过（一个块算不出任何几何，
        # actual 就是空集）。有形状却没有对应几何，恰恰是要拦的情况。
        if not children:
            continue
        # 至少要兑现声明里的一项；一项都不兑现 = 规格和版面脱钩
        if not (claims & actual):
            blockers.append((
                "SPEC_NOT_COMPILED",
                f"第 {i} 页的规格声明了 {'/'.join(sorted(claims))} 这类几何，"
                f"成品里却是 {'/'.join(sorted(actual)) or '其它'}——"
                f"规格没驱动版面，等于只填了字段没做设计"))
    return blockers


def require_deck(slides, design_system=None):
    """硬闸门：不通过就抛异常。compose() 用它。

    与「只返回问题列表」的区别：调用方无法忽略返回值。这是原则从「建议」
    变成「约束」的关键——没有旁路，没有 --force。
    """
    blockers, stats = check_deck(slides, design_system=design_system)
    # 「规格有没有真的驱动版面」——这条把「填了字段」和「当了设计师」分开。
    # 放在 require_deck 而不是 check_deck，是因为它读的是几何，属于交付时
    # 才成立的判断；lint 侧仍只看 DSL 语义。
    blockers = list(blockers) + check_spec_drives_layout(slides)
    if not blockers:
        return stats
    lines = [f"逐页设计规格未通过（{len(blockers)} 项），拒绝编译："]
    for code, msg in blockers[:20]:
        lines.append(f"  [{code}] {msg}")
    if len(blockers) > 20:
        lines.append(f"  ……另有 {len(blockers) - 20} 项")
    lines.append(
        "本闸门是最高原则的执行体：「让模型先当这一页的设计师」。"
        "不提供 --force 旁路；模板更快、省 token 等通用理由一律不成立。")
    raise ValueError("\n".join(lines))


# --------------------------------------------------------------------------- #
# 逐页校验的第三环：成品回验
# --------------------------------------------------------------------------- #
# 「逐页设计 → 逐页交付 → 逐页校验」的最后一环。前两环只在 DSL 层，手写
# python-pptx 可以完全绕过去——正如 audit-pptx 存在的理由。这里把规格里的
# 组件数与成品页上的真实结构件对齐：写了几块，就得有几块。

def verify_spec_compiled(pptx_path, deck, design_system=None, tol=1):
    """成品是否兑现了逐页规格。返回 (ok, report)。

    检查两件成品层的事实：
    1. **页数一致**：规格写的页数 == 成品页数。
    2. **组件数大致兑现**：规格 components 的项数与成品该页非文字结构件
       数量之差不超过 tol。差太多说明「规格写得很细，成品还是套了个模板」。

    不做像素级比对——那会把「合理地合并两块」也判错。这条只抓量级失真。
    """
    from engine.design_audit import audit_design

    res = audit_design(pptx_path)
    per_page = res.get("per_page", [])
    slides = [s for s in (deck.get("slides") or []) if isinstance(s, dict)]
    report = {"pages_spec": len(slides), "pages_pptx": len(per_page),
              "mismatch": [], "ok": True}

    if len(slides) != len(per_page):
        report["ok"] = False
        report["mismatch"].append({
            "page": "-", "problem": "页数不一致",
            "spec": len(slides), "pptx": len(per_page),
        })
        return False, report

    for i, (slide, stat) in enumerate(zip(slides, per_page), 1):
        brief = slide.get("design_brief") or slide.get("design_spec") or {}
        comps = brief.get("components")
        if not _is_filled(comps):
            continue
        want = _count_list_items(comps)
        got = stat.get("structure", 0)
        if abs(got - want) > tol:
            report["ok"] = False
            report["mismatch"].append({
                "page": i, "problem": "组件数未兑现",
                "spec": want, "pptx": got,
                "structure_tag": _text(brief.get("structure"))[:20],
            })

    return report["ok"], report
