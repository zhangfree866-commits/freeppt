"""把「逐页设计」变成编译前提：两条确定性判据。

原则原文（SKILL.md 创作第一性原理）：
    让大模型先做这一页的「设计师」——先读懂内容，再判断怎么表达最有效；
    载体是这之后的结果，不是预设。被否定的只有「先有固定模板、再往里填」。

这句话以前只是文档里的一段话。下面的两条判据把它变成「不过就编译不出来」：

1. **简报必须写全**：composed deck 的每一页都要有 `design_brief`，且五个
   字段齐全、非空、不是占位话术。缺一页就 blocker。这样「跳过设计直接选
   模板」在物理上无法完成——没有简报，连 compose 的输出都过不了闸。

2. **结构声明不许成片重复**：每页简报里的 `structure` 是一个短标签（如
   "否定墙" / "证据阶梯" / "因果链"），它是对「这页用什么结构」的显式判断。
   同一个 structure 出现在过多页上，说明模型没在逐页判断、而是在复用同一
   个答案。这条不需要看几何，纯文本比对，没有阈值争议。

两条都是 blocker，都不能用 `lint_ack` 豁免——理由见 `_apply_acks`：阻断项
必须修源头。这正是「强制」与「建议」的分界。
"""

import re

# 简报必填字段。少一个都算没做设计。
REQUIRED_FIELDS = (
    "carrier",         # 载体：svg / photo / pure-type / data-viz / prototype / ...
    "structure",       # 这页的结构：一个短标签，如「否定墙」
    "visual_anchor",   # 主视觉是什么
    "image_decision",  # 配图决策：ai / real-photo / svg / none
    "rationale",       # 为什么这样表达最有效
)

# 字段最短有效长度（按字符）。低于这个长度基本是敷衍，比如写了「svg」但
# 没写清楚是什么结构、什么主视觉。
MIN_LEN = {
    "carrier": 2,
    "structure": 2,
    "visual_anchor": 4,
    "image_decision": 2,
    "rationale": 10,
}

# 一句「随便填填」的占位话术。命中即视为没填。
PLACEHOLDER = re.compile(
    r"^\s*(?:"
    r"tbd|todo|n/?a|none|null|无|待定|待补|略|同上|"
    r"见上|见前|see above|same as (?:above|previous)|"
    r"[\-—_.·\s]+"
    r")\s*$",
    re.IGNORECASE,
)

# 允许的 image_decision 取值。other 之外的值都算非法，防止自由发挥。
IMAGE_DECISIONS = frozenset({
    "ai", "real-photo", "real_photo", "photo", "svg", "none",
    "programmatic", "chart", "map", "icon",
})

# 每页简报的结构标签允许重复的上限。3 页同结构（如两页表格 + 一页对照）
# 是正常的；4 页开始说明在复用同一个判断。
MAX_SAME_STRUCTURE = 3


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


def check_brief(slide, page_no, is_host_rendered=False):
    """单页简报校验。返回问题列表（空列表 = 通过）。"""
    problems = []
    brief = slide.get("design_brief")

    if not brief or not isinstance(brief, dict):
        problems.append(
            f"第 {page_no} 页没有 design_brief：这一页没有经过「设计师」判断，"
            f"退回模板池直接套版。请先读懂这页内容，再写清载体/结构/主视觉/"
            f"配图决策/理由五项")
        return problems

    missing = []
    short = []
    for field in REQUIRED_FIELDS:
        val = _text(brief.get(field))
        if not val:
            missing.append(field)
        elif PLACEHOLDER.match(val):
            missing.append(field)
        elif len(val) < MIN_LEN[field]:
            short.append((field, len(val), MIN_LEN[field]))

    if missing:
        problems.append(
            f"第 {page_no} 页的 design_brief 缺 {len(missing)} 项有效内容："
            f"{' / '.join(missing)}。这五项是「想清楚了」的最低证据，"
            f"缺任一项等于没做这页的设计")
    for field, got, need in short:
        problems.append(
            f"第 {page_no} 页的 design_brief.{field} 只有 {got} 字"
            f"（至少 {need} 字）：太短说明这一维没有真正判断")

    dec = _text(brief.get("image_decision")).lower()
    if dec and not PLACEHOLDER.match(dec) and dec not in IMAGE_DECISIONS:
        problems.append(
            f"第 {page_no} 页的 image_decision「{dec}」不在允许取值内："
            f"应为 {' / '.join(sorted(IMAGE_DECISIONS))}；"
            f"配图是手段不是目的，必须明确这一页到底要不要配、配什么")

    return problems


def check_deck(slides):
    """整本简报校验。返回 (blockers, stats)。

    blockers: [(code, msg), ...]
    stats:    诊断统计，写进报告方便对照
    """
    blockers = []
    stats = {
        "pages": len(slides),
        "with_brief": 0,
        "without_brief": [],
        "structure_counts": {},
    }

    for i, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            continue
        brief = slide.get("design_brief")
        if isinstance(brief, dict):
            stats["with_brief"] += 1
        else:
            stats["without_brief"].append(i)
        for msg in check_brief(slide, i):
            blockers.append(("DESIGN_BRIEF_MISSING", msg))
        if isinstance(brief, dict):
            key = _text(brief.get("structure")).lower()
            if key and not PLACEHOLDER.match(key):
                stats["structure_counts"].setdefault(key, []).append(i)

    # 结构标签成片重复：那不是在逐页判断，是在复用同一个答案。
    for key, pages in sorted(stats["structure_counts"].items(),
                             key=lambda kv: -len(kv[1])):
        if len(pages) > MAX_SAME_STRUCTURE:
            shown = "、".join(str(p) for p in pages[:8])
            more = f" 等 {len(pages)} 页" if len(pages) > 8 else ""
            blockers.append((
                "STRUCTURE_REUSED",
                f"{len(pages)} 页都用了同一个结构标签「{key}」"
                f"（第 {shown}{more}）：同一副骨架出现在这么多不同内容的页上，"
                f"说明这些页没有各自判断表达方式。请逐页重新判断，"
                f"内容逻辑不同的页不该共用同一结构",
            ))

    return blockers, stats
