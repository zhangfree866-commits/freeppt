#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Model-driven design-system extraction from a reference image.

The engine cannot "look" at an image itself. What it CAN do is
make the host model's per-image design judgment repeatable and hard to skip:

  1. `scaffold()` emits a structured Design System Card (JSON) whose every
     field carries the exact question the model must answer, plus a parallel
     Markdown checklist for the human to watch the process.
  2. `validate()` checks a filled card is complete and maps onto reusable
     FreePPT primitives (theme spec + spec_lock roles). It never invents the
     answers — absent answers are reported, not guessed.

No randomness. Only stdlib.
"""

import argparse
import json
import os

# Each dimension: (json_key, question the model must answer, sub-fields).
# sub-fields are (key, prompt) pairs the model fills with concrete evidence.
DIMENSIONS = [
    ("color_climate", "这张图整体的色彩气候是什么？主色、辅助色、点缀色分别是什么情绪？",
     [("palette_hex", "给出 3-6 个十六进制色值，并标注主/辅/点缀角色"),
      ("temperature", "冷调 / 暖调 / 中性，以及饱和度高低"),
      ("signature_color", "最能代表这张图的'签名色'是哪个，为什么")]),
    ("tone", "明暗基调与对比关系如何？",
     [("dominant_tone", "以浅底为主还是深底为主"),
      ("contrast", "强对比 / 柔和 / 高长调，文字与底的对比大概多强"),
      ("dark_page_use", "什么情况下适合用深色页")]),
    ("typography", "字体搭配、字重与字号层级是怎样的？",
     [("latin_face", "西文偏衬线(serif)还是无衬线(sans)，气质关键词"),
      ("ea_face", "中文偏宋体/明朝还是黑体，建议的本机可用字体名"),
      ("weight_contrast", "标题与正文的字重对比强不强"),
      ("size_hierarchy", "建议的大标题/小标题/正文字号层级（px）")]),
    ("layout", "版式骨架与栅格如何组织？",
     [("grid", "能看出几栏栅格？规整网格还是自由排版"),
      ("focal_point", "视觉主角通常落在什么位置，视线如何被引导"),
      ("whitespace", "留白比例与气质（紧凑 / 舒展 / 大呼吸感"),
      ("asymmetry", "是否使用非对称、出血、错位等手法")]),
    ("shape_language", "图形语言是什么？",
     [("geometry", "偏直角 / 圆角 / 有机曲线 / 手绘感，圆角大概多大"),
      ("stroke_vs_fill", "以描边为主还是面块为主，线条粗细气质"),
      ("icon_style", "若有图标，是线性、面性还是拟物")]),
    ("motifs", "有哪些可复用的装饰母题与材质？",
     [("recurring_motif", "反复出现的母题：色带/竖线/圆点/网格/弧线等"),
      ("texture", "是否有纸张、颗粒、渐变、光感等材质"),
      ("do", "哪些手法值得在全本复用"),
      ("dont", "哪些元素只属于这张图、不应照搬")]),
]

# Fields that map directly onto FreePPT reusable primitives.
REUSE_FIELDS = [
    ("theme_tokens", "映射为主题语义色：surface_light/surface_dark/ink/accent/accent_2/line（键: 十六进制值）"),
    ("spec_lock_roles", "需要新增的字号命名角色：{角色名: px}，仅列反复出现(>=3次)的字号"),
    ("rules", "保证'同一本书'的 2-5 条可执行规则（统一什么、允许每页变什么）"),
]


def _blank_entry(prompt):
    return {"_prompt": prompt, "value": None, "confidence": None,
            "evidence": None}


def scaffold(reference_path="", book_title=""):
    """Return (card_dict, markdown_checklist). Deterministic."""
    card = {
        "schema": "freeppt-design-system-card/v1",
        "status": "draft",
        "reference": {
            "file": os.path.basename(reference_path) if reference_path else None,
            "path": reference_path or None,
            "book": book_title or None,
        },
        "how_to_fill": (
            "宿主大模型逐维度目检参考图后填写 value；confidence 用 "
            "high/medium/low 标注把握；evidence 写你在图里看到的具体依据，"
            "不要写'好看/高级'这类无证据词。看不清就留 null 并在 "
            "open_questions 里提出。填完跑 validate，再交用户定稿。"
        ),
        "dimensions": {},
        "reuse": {},
        "open_questions": [],
        "user_confirmation": {"approved": False, "notes": None},
    }
    md = [f"# 设计系统提炼清单",
          f"- 参考图：`{reference_path or '(待提供)'}`",
          f"- 关联书名：{book_title or '(无)'}",
          "",
          "> 模型须逐项看图作答，并给证据；把握不足标注 confidence。",
          ""]
    for key, question, subs in DIMENSIONS:
        card["dimensions"][key] = {
            "_question": question,
            "fields": {sk: _blank_entry(sp) for sk, sp in subs},
        }
        md.append(f"## {key}")
        md.append(f"{question}")
        for sk, sp in subs:
            md.append(f"- [ ] **{sk}**：{sp}")
        md.append("")
    card["reuse"] = {rk: _blank_entry(rp) for rk, rp in REUSE_FIELDS}
    md.append("## reuse（映射为可复用构件）")
    for rk, rp in REUSE_FIELDS:
        md.append(f"- [ ] **{rk}**：{rp}")
    md.append("")
    md.append("## 定稿")
    md.append("- [ ] 全部维度填完并通过 validate")
    md.append("- [ ] 用户确认 approved=true 后才铺全本")
    return card, "\n".join(md) + "\n"


def _missing_blank(node):
    """Return list of unfilled field paths within a _blank_entry-like node."""
    missing = []
    if isinstance(node, dict) and set(("_prompt", "value")) <= set(node):
        if node.get("value") in (None, "", []):
            missing.append("")
        return missing
    if isinstance(node, dict) and "fields" in node:
        for sk, sub in node["fields"].items():
            for m in _missing_blank(sub):
                missing.append(f"{sk}{('.' + m) if m else ''}")
    return missing


def validate(card):
    """Return (ok, missing_list). Reports blanks; never fills them."""
    if not isinstance(card, dict):
        return False, ["card is not an object"]
    missing = []
    dims = card.get("dimensions", {})
    for key, _, _ in DIMENSIONS:
        block = dims.get(key)
        if not block:
            missing.append(f"dimensions.{key} (整块缺失)")
            continue
        for m in _missing_blank(block):
            label = m.rstrip(".")
            missing.append(f"dimensions.{key}.{label}" if label else
                           f"dimensions.{key}")
    for rk, _ in REUSE_FIELDS:
        block = card.get("reuse", {}).get(rk)
        if block is None or _missing_blank(block):
            missing.append(f"reuse.{rk}")
    open_q = card.get("open_questions")
    approved = card.get("user_confirmation", {}).get("approved")
    notes = []
    if missing:
        notes.append(f"还有 {len(missing)} 项未填，不能定稿。")
    if not approved:
        notes.append("用户尚未 approved；提炼结果只能预览，不能铺全本。")
    return (not missing), {"missing": missing, "notes": notes,
                           "open_questions": open_q or []}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="FreePPT model-driven design-system scaffold/validate")
    sub = ap.add_subparsers(dest="action", required=True)
    p_sc = sub.add_parser("scaffold", help="emit a blank design-system card")
    p_sc.add_argument("reference", nargs="?", default="")
    p_sc.add_argument("--book", default="")
    p_sc.add_argument("--out", default="design_system_card.json")
    p_sc.add_argument("--checklist", default="design_system_checklist.md")
    p_va = sub.add_parser("validate", help="check a filled card is complete")
    p_va.add_argument("card")
    args = ap.parse_args(argv)

    if args.action == "scaffold":
        card, md = scaffold(args.reference, args.book)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=2)
            f.write("\n")
        with open(args.checklist, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"design-system card -> {args.out}")
        print(f"checklist -> {args.checklist}")
        return 0

    with open(args.card, "r", encoding="utf-8") as f:
        card = json.load(f)
    ok, report = validate(card)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
