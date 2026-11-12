"""对已生成的 .pptx 做演讲者备注审计——读最终产物，不看 DSL。

存在的理由与 `pptx_audit.py` 相同：备注闸门 `NOTES_COVERAGE` 挂在 lint 里、
只吃 DSL，而 `require_notes` 还是一个需要主动打开的开关。绕开 `compose()`、
自己写脚本拼出来的 deck 两者都不满足，闸门全程静默。

实测证据：那本 91 页《英伟达之道》（`nvidia-deck-91/v2/` 下 6 个 builder
脚本手写生成）备注覆盖 **0 / 91**，连一个 notesSlide 都没有，而 lint 从未报错。

所以判据必须落在**成品文件**上。这里只读 `slide.has_notes_slide` 与
`notes_text_frame.text`，与 DSL 侧共用同一套阈值口径。

档位（数据来自 12 份豆包样本实测，见 doubao-benchmark/TWELVE_SAMPLE_BENCHMARK.md）：
    随笔  25–60 字      （张一鸣管理日志 均 25.3，区间 9–61）
    常规  100–160 字    （多数样本 99–150）
    研究  200+ 字       （1号位思维 252.9、麦肯锡7S 227.8）
所以「过薄」不是一刀切 40 字，而是按 deck 自身的档位判。
"""

# 仪式页同样豁免：封面/章节/封底的一句话提示是正常做法。
RITUAL_TEXT_MAX = 24

# 档位判定：用全 deck 备注均长反推它属于哪一档，再用该档下限判「过薄」。
TIERS = {
    "essay": (10, 60),        # 随笔：短注也成立，下限只防空白
    "standard": (40, 160),    # 常规
    "research": (80, None),   # 研究型：长讲稿，下限抬高
}

# 全 deck 备注均长低于此值 → 判为随笔档；高于 → 研究档；中间 → 常规档
ESSAY_CEILING = 70
RESEARCH_FLOOR = 180

# 模板化阈值。标定依据（12 份豆包样本 + 我方实测，见
# doubao-benchmark/TWELVE_SAMPLE_BENCHMARK.md）：
#   结尾 12 字最高重复率   豆包 1.0%–17.4%（models20 是异常本 17.4%，其余 ≤3.5%）
#   开头 8 字最高重复率    豆包 1.0%–17.4%
# 我方第一版 fill-notes 是 100% / 5.5%——字数达标、结构全同。所以「够长」不等于
# 「讲得出口」。取 25% 作线：高于它说明有同一句话反复出现在过半平方的页上，
# 那就是模板，不是逐页设计的讲法。
TEMPLATE_REPEAT_LIMIT = 0.25
_TEMPLATE_HEAD = 8
_TEMPLATE_TAIL = 12


def _tier_of(mean_len):
    if mean_len <= ESSAY_CEILING:
        return "essay"
    if mean_len >= RESEARCH_FLOOR:
        return "research"
    return "standard"


def _is_ritual_by_text(slide_text_len):
    """文字极少的页按仪式页处理（与 pptx_audit 同一启发式）。"""
    return slide_text_len <= RITUAL_TEXT_MAX


def _template_signature(texts):
    """找出「同一句话反复出现在多页」的滑痕。

    为什么需要它：字数、覆盖、档位都达标的讲稿仍可能是模板产物。实测第一版
    fill-notes 交出 91 页，结尾 12 字 100% 相同（"…对照自己手上的材料想一想"），
    开头 91 页全一样，87 页连接词序列一字不差——字数审计给绿灯，人一读就知道
    没人在设计。所以模板化必须单独判。

    只看最靠近两端的定长片段：它抓的是"每页都用同一句开场/收尾"，这正是
    模板最藏不住的地方，且对正文内容差异不敏感（不会误伤合理复用）。
    """
    if not texts:
        return {"head_repeat": 0.0, "tail_repeat": 0.0,
                "top_head": "", "top_tail": ""}
    n = len(texts)
    heads = {}
    tails = {}
    for t in texts:
        h = t[:_TEMPLATE_HEAD]
        tl = t[-_TEMPLATE_TAIL:]
        heads[h] = heads.get(h, 0) + 1
        tails[tl] = tails.get(tl, 0) + 1
    top_head, top_head_n = max(heads.items(), key=lambda kv: kv[1])
    top_tail, top_tail_n = max(tails.items(), key=lambda kv: kv[1])
    return {
        "head_repeat": round(top_head_n / n, 4),
        "tail_repeat": round(top_tail_n / n, 4),
        "top_head": top_head,
        "top_tail": top_tail,
    }


def audit_notes(pptx_path):
    """审计一份成品 pptx 的演讲者备注。

    返回 dict：
        ok               覆盖达标且无明显过薄
        slide_count      总页数
        covered          有非空备注的页数
        coverage         覆盖率（0–1）
        mean_len         有备注页的均长
        tier             判定出的档位（essay / standard / research）
        thin_pages       过薄页 [{"page":n,"len":m}]
        missing_pages    无备注页 [n, ...]
        exempted         按仪式页豁免的页码
    """
    from pptx import Presentation

    prs = Presentation(pptx_path)
    slides = list(prs.slides)
    total = len(slides)

    missing, thin, covered_lens, exempted = [], [], [], []
    covered_texts = []
    for i, s in enumerate(slides, 1):
        # 页内可见文字量：用来判仪式页，必须在读备注前算
        visible = 0
        for sh in s.shapes:
            if sh.has_text_frame:
                visible += len(sh.text.strip())

        text = ""
        if s.has_notes_slide:
            try:
                text = (s.notes_slide.notes_text_frame.text or "").strip()
            except (AttributeError, KeyError):
                text = ""

        if not text:
            if _is_ritual_by_text(visible):
                exempted.append(i)
            else:
                missing.append(i)
        else:
            covered_lens.append(len(text))
            covered_texts.append(text)

    covered = len(covered_lens)
    mean_len = round(sum(covered_lens) / covered, 1) if covered else 0.0
    tier = _tier_of(mean_len)
    floor = TIERS[tier][0]

    for i, s in enumerate(slides, 1):
        if i in missing or i in exempted:
            continue
        text = (s.notes_slide.notes_text_frame.text or "").strip()
        if len(text) < floor:
            thin.append({"page": i, "len": len(text)})

    judged = total - len(exempted)
    coverage = round(covered / judged, 4) if judged else 1.0

    tpl = _template_signature(covered_texts)
    templated = (tpl["tail_repeat"] > TEMPLATE_REPEAT_LIMIT
                 or tpl["head_repeat"] > TEMPLATE_REPEAT_LIMIT)

    return {
        "ok": not missing and not thin and not templated,
        "slide_count": total,
        "judged_slides": judged,
        "covered": covered,
        "coverage": coverage,
        "mean_len": mean_len,
        "tier": tier,
        "tier_floor": floor,
        "thin_pages": thin,
        "missing_pages": missing,
        "exempted": exempted,
        "templated": templated,
        "template": tpl,
        "template_limit": TEMPLATE_REPEAT_LIMIT,
    }
