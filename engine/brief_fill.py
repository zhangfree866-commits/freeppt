"""Pure-CLI brief -> deck spec filler. No LLM, no invented facts.

`reports.build_skeleton()` emits a structurally valid deck whose fields are all
placeholders. The host agent normally fills them with written prose. When there
is no agent at all (plain CLI / CI), this module fills the same fields using
ONLY the user's own words plus explicitly labelled empty-state notes.

Contract:
- Every `reports.PLACEHOLDER` string is replaced; `content_ai.check_content`
  therefore reports no PLACEHOLDER_LEFT errors.
- No numeric value is invented. Chart series use numbers found in the brief,
  padded with 0 where absent, and the source field says the raw data was not
  supplied.
- Card/body text is padded to lint's minimum length with a sentence that says
  the detail was not supplied. That is a statement about missing input, not a
  fabricated business fact.
"""

import datetime
import re

from engine import content_ai, reports

NUM = re.compile(r"-?\d+(?:\.\d+)?%?")
EMPTY_NOTE = ("本条来自用户输入的原始要点，未提供更多背景、量化口径或数据来源；"
              "如需完整论述，请直接在 PowerPoint 中补充。")


def _pad(text, floor=48):
    """Reach a lint-safe length without inventing content."""
    text = str(text or "").strip()
    if not text:
        return ("此处未收到用户要点，属于待补充位置。"
                "请在 PowerPoint 中直接填写具体内容、数据与来源。")[:max(floor, 48)]
    if len(text) >= floor:
        return text
    return text + "。" + EMPTY_NOTE


def _short(text, limit=12):
    text = str(text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _title(point, role):
    if point:
        t = str(point).strip()
        if len(t) < 6:
            t = f"{role}：{t}"
        return t if len(t) <= 30 else t[:29] + "…"
    return f"{role}：要点待补充"


def _numbers(points):
    out = []
    for p in points:
        out += NUM.findall(str(p))
    return out


def _fill_cover(data, meta, points):
    label = meta["label"]
    first = _short(points[0], 20) if points else "由命令行要点生成"
    data["title"] = meta.get("title") or f"{label}｜{first}"
    data["subtitle"] = meta.get("subtitle") or (
        f"基于 {len(points)} 条命令行要点生成，内容未经扩写" if points
        else "未提供要点，页面内容需手动补充")
    data["org"] = meta.get("org") or "命令行生成（未署名）"
    data["date"] = meta.get("date") or datetime.date.today().isoformat()
    return data


def _fill_agenda(data, plan, bucket):
    roles = [s["role"] for s in plan
             if s["template"] not in ("cover", "agenda", "closing")]
    items = []
    for i, role in enumerate(roles[:3]):
        notes = bucket.get(i, [])
        # section index in `plan` differs from agenda order; use role as truth
        summary = _pad(notes[0], 40) if notes else f"{role}：未收到对应要点，内容需手动补充。"
        items.append({"title": _short(role, 14), "summary": summary})
    while len(items) < 3:
        items.append({"title": f"板块{len(items) + 1}",
                      "summary": "未提供该板块的输入要点，请在 PowerPoint 中补充具体内容与结论。"})
    data["title"] = "目录"
    data["items"] = items
    return data


def _fill_cards(data, points, role):
    data["title"] = _title(points[0] if points else "", role)
    cards = []
    for i in range(3):
        p = points[i] if i < len(points) else ""
        cards.append({
            "title": _short(p, 14) if p else f"要点{i + 1}（未提供）",
            "body": _pad(p, 60),
        })
    data["cards"] = cards
    return data


def _fill_kpis(data, points, role):
    data["title"] = _title(points[0] if points else "", role)
    nums = _numbers(points)
    kpis = []
    for i in range(3):
        p = points[i] if i < len(points) else ""
        value = NUM.search(str(p)).group(0) if p and NUM.search(str(p)) else "—"
        kpis.append({"value": value,
                     "label": _short(p, 12) if p else f"指标{i + 1}（未提供）"})
    data["kpis"] = kpis
    data["note"] = ("数值从命令行要点中直接提取，未做任何推算；"
                    "未标注口径与来源，请在交付前补充。" if nums else
                    "输入要点中未出现数值，指标位留空，请在交付前补充真实数据。")
    return data


def _fill_chart(data, points, role):
    data["title"] = _title(points[0] if points else "", role)
    nums = _numbers(points)
    vals = []
    for raw in nums[:4]:
        try:
            vals.append(float(raw.replace("%", "")))
        except ValueError:
            continue
    while len(vals) < 4:
        vals.append(0.0)
    data["chart"] = {
        "kind": "column",
        "categories": [f"要点{i + 1}" for i in range(4)],
        "series": [{"name": "要点中的数值", "values": vals[:4]}],
    }
    data["insight"] = _pad("；".join(str(p) for p in points), 70)
    data["kpi"] = {"value": nums[0] if nums else "—", "label": "要点中的数值"}
    data["source"] = ("用户输入要点（命令行未提供原始数据表或第三方来源；"
                      "零值表示未提供，不代表真实业务数值）")
    return data


def _fill_process(data, points, role):
    data["title"] = _title(points[0] if points else "", role)
    steps = []
    for i in range(4):
        p = points[i] if i < len(points) else ""
        steps.append({"title": _short(p, 14) if p else f"步骤{i + 1}（未提供）",
                      "desc": _pad(p, 60)})
    data["steps"] = steps
    return data


def _fill_timeline(data, points, role):
    data["title"] = _title(points[0] if points else "", role)
    items = []
    for i in range(4):
        p = points[i] if i < len(points) else ""
        items.append({"label": f"要点{i + 1}" if p else f"阶段{i + 1}（未提供）",
                      "text": _pad(p, 60)})
    data["points"] = items
    return data


def _fill_image_text(data, points, role):
    data["title"] = _title(points[0] if points else "", role)
    data["image"] = ""
    data["heading"] = _short(points[0], 14) if points else "未提供小标题"
    data["body"] = _pad("；".join(str(p) for p in points), 60)
    data["source"] = "命令行未提供配图，图片位留空"
    return data


def _fill_section(data, role, index):
    data["no"] = f"{index:02d}"
    data["title"] = _short(role, 20)
    data["en"] = ""
    return data


def _fill_closing(data, meta):
    data["title"] = "谢谢"
    data["subtitle"] = meta.get("subtitle") or "内容由命令行要点生成，未经语言扩写"
    data["org"] = meta.get("org") or "命令行生成（未署名）"
    return data


FILLERS = {
    "three_cards": _fill_cards,
    "kpi_row": _fill_kpis,
    "chart_insight": _fill_chart,
    "process": _fill_process,
    "timeline": _fill_timeline,
    "image_text": _fill_image_text,
}


def build_from_brief(report_type, brief, meta=None):
    """Return a fully filled `{template,data}` deck spec.

    `brief` is a string or a list of points. `meta` may carry
    title/subtitle/org/date/theme overrides.
    """
    meta = dict(meta or {})
    points = content_ai.parse_brief(brief) if isinstance(brief, str) \
        else [str(p).strip() for p in brief if str(p).strip()]
    spec = reports.build_skeleton(report_type, theme=meta.get("theme"))
    plan = reports.section_plan(report_type)
    bucket = content_ai.assign_points(report_type, points)
    # assign_points routes by section index; spread unrouted points so every
    # page has some of the user's own words instead of only empty-state text.
    used = sum(len(v) for v in bucket.values())
    if used < len(points):
        leftovers = points[used:]
        for i, p in enumerate(leftovers):
            candidates = [j for j, s in enumerate(plan)
                          if s["template"] in FILLERS]
            if candidates:
                bucket.setdefault(candidates[i % len(candidates)], []).append(p)

    for i, slide in enumerate(spec["slides"]):
        tpl = slide["template"]
        data = slide["data"]
        role = plan[i]["role"]
        pts = bucket.get(i, [])
        if tpl == "cover":
            data = _fill_cover(data, {**meta, "label":
                                      reports.get_report(report_type)["label"]}, points)
        elif tpl == "agenda":
            data = _fill_agenda(data, plan, bucket)
        elif tpl == "section":
            data = _fill_section(data, role, i)
        elif tpl == "closing":
            data = _fill_closing(data, meta)
        elif tpl in FILLERS:
            data = FILLERS[tpl](data, pts, role)
        slide["data"] = data

    # last-resort sweep: never let a placeholder reach lint/build
    def sweep(obj):
        if isinstance(obj, str):
            return obj.replace(reports.PLACEHOLDER, "").strip() or "未提供"
        if isinstance(obj, dict):
            return {k: sweep(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sweep(v) for v in obj]
        return obj

    spec["slides"] = sweep(spec["slides"])
    spec["_cli_brief"] = {"report_type": report_type,
                          "points": points, "generated_by": "cli.make",
                          "no_llm": True}
    return spec
