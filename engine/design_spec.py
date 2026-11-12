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


def require_deck(slides, design_system=None):
    """硬闸门：不通过就抛异常。compose() 用它。

    与「只返回问题列表」的区别：调用方无法忽略返回值。这是原则从「建议」
    变成「约束」的关键——没有旁路，没有 --force。
    """
    blockers, stats = check_deck(slides, design_system=design_system)
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
