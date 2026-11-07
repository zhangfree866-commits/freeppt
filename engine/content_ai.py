"""Smart content-creation assistant for FreePPT.

The actual language expansion/polish is performed by the host agent following
references/content-playbook.md (there is no bundled LLM client/API key). This
module provides the deterministic machinery around that creative step:

  1. parse_brief      - split rough notes / scattered bullets into clean points
  2. assign_points    - route each point to the right report section (MECE)
  3. build_brief_deck - skeleton + the routed notes attached per page, so the
                        agent expands them in place instead of starting blank
  4. check_content    - deterministic quality gate (placeholders, cliches,
                        unsupported claims, non-action titles, missing sources)

Run `python3 engine/content_ai.py --help` for the CLI.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import reports  # noqa: E402

# ---- cliche / AI-taste vocabulary (warning level, not a hard block) --------
CLICHE_PATTERNS = [
    r"在.{0,12}背景下", r"综上所述", r"赋能", r"抓手", r"闭环", r"保驾护航",
    r"砥砺前行", r"凝心聚力", r"高质量发展", r"全方位", r"多维度", r"深度赋能",
    r"强势", r"重磅", r"引领行业", r"行业领先(?!.*[0-9])", r"打造.*生态圈",
    r"总的来说", r"众所周知", r"不言而喻",
]
CLICHE_RE = re.compile("|".join(CLICHE_PATTERNS))
NUM_RE = re.compile(r"[0-9０-９]|%|％|[一二三四五六七八九十百千万亿]+")
BULLET_RE = re.compile(r"^\s*(?:[-*•·]|\d+[.、)]|[（(]?\d+[)）.])\s*")

# section routing: role-keyword -> report roles (see reports.REPORT_TYPES)
ROUTE_KEYWORDS = [
    ("kpi_row", ["指标", "kpi", "达成", "完成率", "收入", "利润", "营收",
                 "增长", "额", "率", "数字", "业绩", "占比"]),
    ("chart_insight", ["趋势", "同比", "环比", "图表", "走势", "结构",
                       "对比", "变化", "数据表现", "成本"]),
    ("process", ["计划", "下一步", "行动", "举措", "规划", "安排", "措施",
                 "方案", "落地", "推进", "改善", "改进"]),
    ("timeline", ["里程碑", "节点", "历程", "时间线", "阶段成果", "履历"]),
    ("section", ["背景", "概述", "目标", "职责", "理解", "定调", "展望"]),
]
# three_cards is the catch-all content bucket (achievements / problems / etc.)
CARD_HINTS = ["成果", "亮点", "问题", "不足", "风险", "根因", "优势", "成绩",
              "进展", "经验", "诊断", "思路", "差距"]


def parse_brief(text):
    """Split free-form rough notes into a clean list of non-empty points."""
    if not text:
        return []
    # normalize: split on newlines, semicolons (CJK + ASCII), and bullets
    chunks = re.split(r"[\n；;]+", text)
    points = []
    for ch in chunks:
        ch = BULLET_RE.sub("", ch).strip()
        if ch:
            points.append(ch)
    return points


def _match_roles(point):
    low = point.lower()
    hits = []
    for role, kws in ROUTE_KEYWORDS:
        if any(kw.lower() in low for kw in kws):
            hit_role = role
            hits.append(hit_role)
    if any(kw in point for kw in CARD_HINTS):
        hits.append("three_cards")
    return hits


def assign_points(report_type, points):
    """Route points to existing section roles in this report type.

    Returns {section_index: [points...]}; unmatched points go to the first
    three_cards section, or the agenda if the report has none.
    """
    plan = reports.section_plan(report_type)
    roles = [s["template"] for s in plan]
    card_idx = next((i for i, t in enumerate(roles) if t == "three_cards"), None)
    agenda_idx = next((i for i, t in enumerate(roles) if t == "agenda"), 0)
    bucket = {}

    def put(idx, p):
        bucket.setdefault(idx, []).append(p)

    for p in points:
        matched = [i for i, t in enumerate(roles)
                   if t in _match_roles(p)]
        if matched:
            put(matched[0], p)          # first matching section wins
        elif card_idx is not None:
            put(card_idx, p)
        else:
            put(agenda_idx, p)
    return bucket


def build_brief_deck(report_type, brief, theme=None):
    """Skeleton plus routed raw notes attached as `_notes` for the agent."""
    deck = reports.build_skeleton(report_type, theme=theme)
    points = parse_brief(brief) if isinstance(brief, str) else list(brief)
    bucket = assign_points(report_type, points)
    for idx, notes in bucket.items():
        deck["slides"][idx]["_notes"] = notes
    deck["_unassigned_count"] = 0  # every point is routed; kept for diagnostics
    return deck


# ---- deterministic content quality gate ------------------------------------
def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def check_content(deck_spec):
    """Return {ok, errors, warnings} for a (possibly filled) deck spec."""
    errors, warnings = [], []
    slides = deck_spec.get("slides", [])
    for i, slide in enumerate(slides):
        tpl = slide.get("template", "?")
        data = slide.get("data", {})
        page = i + 1

        for s in _walk_strings(data):
            if reports.PLACEHOLDER in s:
                errors.append({"slide": page, "code": "PLACEHOLDER_LEFT",
                               "msg": f"{tpl} 仍有未填占位"})
                break

        if tpl == "chart_insight":
            if not str(data.get("source", "")).strip() \
                    or reports.PLACEHOLDER in str(data.get("source", "")):
                errors.append({"slide": page, "code": "MISSING_SOURCE",
                               "msg": "图表页缺少真实数据来源"})

        title = data.get("title", "")
        if title and reports.PLACEHOLDER not in title \
                and tpl not in ("cover", "agenda", "section", "closing"):
            bare = re.sub(r"[：:，,。.！!？?（）()\s]", "", title)
            if len(bare) < 8:
                warnings.append({"slide": page, "code": "ACTION_TITLE",
                                 "msg": f"标题疑似关键词而非结论句：{title}"})

        for s in _walk_strings(data):
            m = CLICHE_RE.search(s)
            if m:
                warnings.append({"slide": page, "code": "CLICHE",
                                 "msg": f"疑似套话「{m.group(0)}」，建议替换为具体表述"})

        # body-level claims should carry evidence (numbers) for card/process
        if tpl == "three_cards":
            for c in data.get("cards", []):
                body = c.get("body", "")
                if body and reports.PLACEHOLDER not in body and not NUM_RE.search(body):
                    warnings.append(
                        {"slide": page, "code": "WEAK_CLAIM",
                         "msg": f"「{c.get('title', '')[:12]}」正文缺量化证据"})

    return {"ok": not errors, "errors": errors, "warnings": warnings}


# ---- CLI --------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="FreePPT content assistant")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_sk = sub.add_parser("skeleton", help="emit a report deck skeleton")
    p_sk.add_argument("report_type", choices=[k for k, _ in reports.list_types()])
    p_sk.add_argument("--theme")
    p_sk.add_argument("--out")

    p_rt = sub.add_parser("route", help="parse a brief and route its points")
    p_rt.add_argument("report_type", choices=[k for k, _ in reports.list_types()])
    p_rt.add_argument("--brief-file")
    p_rt.add_argument("--out", help="write a brief-seeded deck spec here")

    p_ck = sub.add_parser("check", help="quality-check a filled deck spec")
    p_ck.add_argument("deck")

    args = ap.parse_args(argv)

    if args.cmd == "skeleton":
        deck = reports.build_skeleton(args.report_type, theme=args.theme)
        out = json.dumps(deck, ensure_ascii=False, indent=2)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(out)
            print(f"skeleton ({len(deck['slides'])} pages) -> {args.out}")
        else:
            print(out)
        return 0

    if args.cmd == "route":
        text = open(args.brief_file, encoding="utf-8").read() \
            if args.brief_file else sys.stdin.read()
        points = parse_brief(text)
        deck = build_brief_deck(args.report_type, points)
        plan = reports.section_plan(args.report_type)
        for idx, notes in assign_points(args.report_type, points).items():
            print(f"[p{idx + 1} {plan[idx]['template']} {plan[idx]['role']}]")
            for n in notes:
                print("   -", n)
        if args.out:
            json.dump(deck, open(args.out, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            print(f"\nbrief deck -> {args.out}")
        return 0

    if args.cmd == "check":
        spec = json.load(open(args.deck, encoding="utf-8"))
        result = check_content(spec)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
