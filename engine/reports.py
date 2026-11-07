"""Enterprise report-scenario registry and deterministic deck skeleton builder.

Each report type is a fixed, consulting-style narrative (pyramid + MECE) made
of sections. A section maps to one master template in engine/templates.py and
declares the data fields the writer (the agent, following the content
playbook) must fill. `build_skeleton` emits a valid, ready-to-expand deck spec
with explicit placeholder content — the engine never fabricates real data.

The skeleton is the deterministic half of "smart content creation": it decides
structure, page sequence and template fit. Actual expansion/polish of the
user's rough notes is done by the agent per references/content-playbook.md.
"""

# A section = (template id, page role title, writing hint, key data fields).
# Templates: cover/agenda/section/three_cards/kpi_row/chart_insight/
#            image_text/process/timeline/closing


def _s(template, role, hint, fields):
    return {"template": template, "role": role, "hint": hint, "fields": fields}


REPORT_TYPES = {
    "weekly": {
        "label": "周报",
        "default_theme": "mckinsey",
        "sections": [
            _s("cover", "封面", "报告周期 + 团队/姓名 + 一句话主题",
               ["title", "subtitle", "org", "date"]),
            _s("agenda", "本期目录", "3–4 个板块，MECE 不重叠", ["items"]),
            _s("kpi_row", "本周核心指标", "3–4 个可量化结果，带环比/同比",
               ["title", "kpis", "note"]),
            _s("three_cards", "本周重点进展", "三件最重要的事，按价值排序",
               ["title", "cards"]),
            _s("process", "下周工作计划", "分步骤行动，明确负责人/时间点",
               ["title", "steps"]),
            _s("closing", "结束页", "致谢或一句承诺", ["title"]),
        ],
    },
    "monthly": {
        "label": "月报",
        "default_theme": "mckinsey",
        "sections": [
            _s("cover", "封面", "月份 + 业务线 + 报告主题",
               ["title", "subtitle", "org", "date"]),
            _s("agenda", "目录", "经营概览/数据/复盘/计划", ["items"]),
            _s("kpi_row", "月度核心指标", "收入/增长/效率等北极星指标",
               ["title", "kpis", "note"]),
            _s("chart_insight", "关键经营数据", "图表 + 一句结论 + 一个记忆点数字",
               ["title", "chart", "insight", "kpi", "source"]),
            _s("three_cards", "重点工作复盘", "做了什么/结果如何/差异原因",
               ["title", "cards"]),
            _s("process", "下月行动计划", "目标拆解为可执行步骤", ["title", "steps"]),
            _s("closing", "结束页", "致谢", ["title"]),
        ],
    },
    "quarterly": {
        "label": "季度报告",
        "default_theme": "bcg",
        "sections": [
            _s("cover", "封面", "季度 + 业务单元 + 主题",
               ["title", "subtitle", "org", "date"]),
            _s("agenda", "目录", "总览/指标/数据/举措/规划", ["items"]),
            _s("section", "季度总览章节页", "一句话定调本季度", ["no", "title", "en"]),
            _s("kpi_row", "季度核心指标", "季度目标达成与同比", ["title", "kpis", "note"]),
            _s("chart_insight", "趋势数据分析", "环比趋势 + 拐点解读",
               ["title", "chart", "insight", "kpi", "source"]),
            _s("three_cards", "关键战略举措", "三项驱动结果的核心动作",
               ["title", "cards"]),
            _s("process", "下季度规划", "优先级排序的行动路线", ["title", "steps"]),
            _s("closing", "结束页", "致谢", ["title"]),
        ],
    },
    "annual": {
        "label": "年度报告",
        "default_theme": "rolandberger",
        "sections": [
            _s("cover", "封面", "年度 + 组织 + 年度主题",
               ["title", "subtitle", "org", "date"]),
            _s("agenda", "目录", "回顾/成绩/数据/里程碑/展望", ["items"]),
            _s("section", "年度回顾章节页", "年度关键词定调", ["no", "title", "en"]),
            _s("kpi_row", "年度成绩指标", "全年最重要的 3–4 个战果数字",
               ["title", "kpis", "note"]),
            _s("chart_insight", "年度数据表现", "全年走势 + 结构性结论",
               ["title", "chart", "insight", "kpi", "source"]),
            _s("three_cards", "战略成果总结", "三大战略主线的落地成果",
               ["title", "cards"]),
            _s("timeline", "年度里程碑", "按时间顺序的关键事件", ["title", "points"]),
            _s("section", "来年展望章节页", "过渡到新一年目标", ["no", "title", "en"]),
            _s("process", "来年重点规划", "新一年的行动主线", ["title", "steps"]),
            _s("closing", "结束页", "致谢与愿景", ["title", "subtitle"]),
        ],
    },
    "performance": {
        "label": "述职报告",
        "default_theme": "pwc",
        "sections": [
            _s("cover", "封面", "述职周期 + 岗位 + 姓名",
               ["title", "subtitle", "org", "date"]),
            _s("agenda", "目录", "职责/业绩/项目/成长/规划", ["items"]),
            _s("section", "岗位职责章节页", "简述职责边界", ["no", "title", "en"]),
            _s("kpi_row", "关键业绩指标", "用数字证明履职结果",
               ["title", "kpis", "note"]),
            _s("three_cards", "核心业绩成果", "三项最有说服力的成果",
               ["title", "cards"]),
            _s("process", "重点项目推进", "项目阶段与个人贡献", ["title", "steps"]),
            _s("three_cards", "能力成长与不足", "成长/短板/改进，诚恳具体",
               ["title", "cards"]),
            _s("process", "下期工作规划", "可衡量的下阶段目标", ["title", "steps"]),
            _s("closing", "结束页", "致谢", ["title"]),
        ],
    },
    "competition": {
        "label": "竞聘报告",
        "default_theme": "pwc",
        "sections": [
            _s("cover", "封面", "竞聘岗位 + 姓名 + 一句话主张",
               ["title", "subtitle", "org", "date"]),
            _s("agenda", "目录", "岗位理解/优势/战绩/思路/规划", ["items"]),
            _s("section", "岗位理解章节页", "对岗位价值的认知", ["no", "title", "en"]),
            _s("three_cards", "个人核心优势", "人岗匹配的三大优势",
               ["title", "cards"]),
            _s("timeline", "过往关键战绩", "按时间呈现可信履历成果",
               ["title", "points"]),
            _s("three_cards", "履职思路", "若上任将如何开展工作", ["title", "cards"]),
            _s("process", "上任行动规划", "短期/中期可落地路线", ["title", "steps"]),
            _s("closing", "结束页", "表达决心与致谢", ["title"]),
        ],
    },
    "retrospective": {
        "label": "复盘报告",
        "default_theme": "bcg",
        "sections": [
            _s("cover", "封面", "项目/事件名称 + 复盘周期",
               ["title", "subtitle", "org", "date"]),
            _s("agenda", "目录", "概述/结果/亮点/问题/改进", ["items"]),
            _s("section", "项目概述章节页", "背景与目标回顾", ["no", "title", "en"]),
            _s("kpi_row", "结果指标达成", "目标 vs 实际的量化差距",
               ["title", "kpis", "note"]),
            _s("three_cards", "做得好的亮点", "可复用的成功经验", ["title", "cards"]),
            _s("three_cards", "问题与根因", "现象→根因，5Why 深挖",
               ["title", "cards"]),
            _s("process", "改进行动计划", "具体 action + 负责人 + 期限",
               ["title", "steps"]),
            _s("closing", "结束页", "总结一句方法论", ["title"]),
        ],
    },
    "business": {
        "label": "经营分析报告",
        "default_theme": "mckinsey",
        "sections": [
            _s("cover", "封面", "经营周期 + 主体 + 分析主题",
               ["title", "subtitle", "org", "date"]),
            _s("agenda", "目录", "指标/收入/成本/诊断/举措", ["items"]),
            _s("kpi_row", "经营核心指标", "收入/利润/现金流/增长",
               ["title", "kpis", "note"]),
            _s("chart_insight", "收入与利润分析", "量价拆解 + 结论",
               ["title", "chart", "insight", "kpi", "source"]),
            _s("chart_insight", "成本与结构分析", "结构占比 + 异常点",
               ["title", "chart", "insight", "kpi", "source"]),
            _s("three_cards", "经营问题诊断", "三个关键问题及影响",
               ["title", "cards"]),
            _s("process", "经营改善举措", "可执行的降本增效动作",
               ["title", "steps"]),
            _s("closing", "结束页", "决策建议收束", ["title"]),
        ],
    },
}

PLACEHOLDER = "【待填】"


def list_types():
    return [(k, v["label"]) for k, v in REPORT_TYPES.items()]


def get_report(report_type):
    if report_type not in REPORT_TYPES:
        raise ValueError(
            f"unknown report type {report_type}; choose {list(REPORT_TYPES)}")
    return REPORT_TYPES[report_type]


# ---- minimal valid skeleton data per template (placeholders, not fake data) -
def _skeleton_data(template, role, hint):
    if template == "cover":
        return {"title": f"{PLACEHOLDER}{role}：报告主标题（结论式）",
                "subtitle": f"{PLACEHOLDER}一句话副标题",
                "org": f"{PLACEHOLDER}团队/姓名", "date": f"{PLACEHOLDER}日期"}
    if template == "agenda":
        return {"title": "目录",
                "items": [{"title": f"{PLACEHOLDER}板块{i + 1}",
                           "summary": f"{PLACEHOLDER}用一句话概括该板块的核心内容与结论"}
                          for i in range(3)]}
    if template == "section":
        return {"no": "01", "title": f"{PLACEHOLDER}{role}",
                "en": f"{PLACEHOLDER}英文/关键词（可留空）"}
    if template == "three_cards":
        return {"title": f"{PLACEHOLDER}{role}：用一句完整结论做标题",
                "cards": [{"title": f"{PLACEHOLDER}要点{i + 1}（相互独立、完全穷尽）",
                           "body": f"{PLACEHOLDER}此处填写支撑该要点的具体事实、数据或案例，"
                                   f"要求可验证、有量化口径，避免空泛形容词，正文不少于四十字。"}
                          for i in range(3)]}
    if template == "kpi_row":
        return {"title": f"{PLACEHOLDER}{role}：结论句标题",
                "kpis": [{"value": f"{PLACEHOLDER}数值",
                          "label": f"{PLACEHOLDER}指标名{i + 1}"} for i in range(3)],
                "note": f"{PLACEHOLDER}指标口径/数据来源说明"}
    if template == "chart_insight":
        return {
            "title": f"{PLACEHOLDER}{role}：结论句标题",
            "chart": {"kind": "column",
                      "categories": [f"{PLACEHOLDER}类别{i + 1}" for i in range(4)],
                      "series": [{"name": f"{PLACEHOLDER}指标",
                                  "values": [0, 0, 0, 0]}]},
            "insight": f"{PLACEHOLDER}用一句完整结论说明图表反映的趋势、拐点或结构变化，"
                       f"并点出背后的业务含义与建议动作，避免只复述数字，正文不少于六十字。",
            "kpi": {"value": f"{PLACEHOLDER}关键数", "label": "记忆点指标"},
            "source": f"{PLACEHOLDER}数据来源（必填，如：公司财报/内部系统/第三方机构）"}
    if template == "process":
        return {"title": f"{PLACEHOLDER}{role}：用一句完整结论做标题",
                "steps": [{"title": f"{PLACEHOLDER}步骤{i + 1}",
                           "desc": f"{PLACEHOLDER}写清该步骤的具体动作、责任人与完成时间点，"
                                   f"确保可执行可追踪，避免只写方向性口号，正文不少于四十字。"}
                          for i in range(4)]}
    if template == "timeline":
        return {"title": f"{PLACEHOLDER}{role}：用一句完整结论做标题",
                "points": [{"label": f"{PLACEHOLDER}阶段{i + 1}",
                            "text": f"{PLACEHOLDER}该阶段的关键事件、量化结果与影响，按时间顺序陈述"}
                           for i in range(4)]}
    if template == "image_text":
        return {"title": f"{PLACEHOLDER}{role}",
                "image": f"{PLACEHOLDER}图片文件名.png",
                "heading": f"{PLACEHOLDER}小标题",
                "body": f"{PLACEHOLDER}正文说明", "source": f"{PLACEHOLDER}图片来源"}
    if template == "closing":
        return {"title": "谢谢", "subtitle": f"{PLACEHOLDER}一句结语（可留空）",
                "org": f"{PLACEHOLDER}署名（可留空）"}
    return {}


def build_skeleton(report_type, theme=None, transition="fade"):
    """Return a ready-to-expand deck spec dict with placeholder content."""
    spec_def = get_report(report_type)
    slides = []
    for sec in spec_def["sections"]:
        data = _skeleton_data(sec["template"], sec["role"], sec["hint"])
        slides.append({"template": sec["template"], "data": data})
    deck = {"theme": theme or spec_def["default_theme"],
            "transition": transition, "slides": slides}
    return deck


def section_plan(report_type):
    """Expose the ordered section plan for the writer/agent."""
    return [{"template": s["template"], "role": s["role"],
             "hint": s["hint"], "fields": s["fields"]}
            for s in get_report(report_type)["sections"]]
