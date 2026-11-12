#!/usr/bin/env python3
"""CLI: layout -> lint -> build."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import layout as layout_mod
from engine.layout import layout_deck
from engine.lint import lint_deck
from engine.compiler import build_pptx
from engine.templates import expand_deck
from engine import reports


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def prepare(doc):
    # template spec -> raw deck
    if doc.get("slides") and isinstance(doc["slides"][0], dict) \
            and "template" in doc["slides"][0]:
        doc = expand_deck(doc)
    base = doc.get("assets_base")
    if base:
        layout_mod.ASSETS_BASE = base
    return layout_deck(doc)


def cmd_lint(args):
    deck = prepare(load(args.deck))
    result = lint_deck(deck)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _group_by_slide(items):
    grouped = {}
    for item in items:
        grouped.setdefault(item["slide"], []).append(item)
    return grouped


def _verify_report(deck, result):
    """Human-readable acceptance report aggregating every lint gate.

    Covers layout, geometry integrity and the closing-consistency gate in one
    read, mirroring the final QA sign-off before a deck ships. Diagnostics are
    grouped by severity tier so a reader can separate "must fix" from "needs a
    human call" from "just a measurement".
    """
    errors, warnings = result["errors"], result["warnings"]
    acked = result.get("acked") or []
    summary = result.get("severity_summary") or {}
    lines = [f"FreePPT verify — {len(deck['slides'])} slide(s)", "=" * 52]

    def emit(items, badge, heading):
        if not items:
            return
        lines.append(f"{heading} ({len(items)})")
        for slide, group in sorted(_group_by_slide(items).items()):
            where = f"slide {slide}" if slide else "deck"
            for it in group:
                lines.append(f"  {badge} {where:>9}  {it['code']}: {it['msg']}")

    def tier(items, want):
        return [it for it in items if it.get("severity") == want]

    blockers = tier(errors, "blocker")
    advisories = tier(warnings, "advisory")
    infos = tier(warnings, "info")

    emit(blockers, "[B]", "BLOCKERS — build refused until fixed at the source")
    emit(advisories, "[A]", "ADVISORIES — needs a human call (see lint_ack)")
    emit(infos, "[I]", "INFOS — measurements, no action needed")

    if acked:
        lines.append(f"ADJUDICATED ({len(acked)}) — reviewed and accepted as-is")
        for slide, group in sorted(_group_by_slide(acked).items()):
            where = f"slide {slide}" if slide else "deck"
            for it in group:
                lines.append(f"  [ok] {where:>9}  {it['code']}: "
                             f"{it.get('acked_reason', '')}")

    if summary:
        lines.append("-" * 52)
        lines.append(
            f"{summary.get('blockers', 0)} blocker / "
            f"{summary.get('advisories', 0)} advisory / "
            f"{summary.get('infos', 0)} info / "
            f"{summary.get('acked', 0)} adjudicated")

    lines.append("-" * 52)
    if blockers:
        lines.append(f"FAIL — {len(blockers)} blocking error(s) must be fixed before build")
    elif advisories:
        lines.append(f"PASS — 0 blockers; {len(advisories)} advisor"
                     f"{'y' if len(advisories) == 1 else 'ies'} awaiting a call")
    elif acked:
        lines.append(f"PASS — 0 blockers, 0 open advisories; "
                     f"{len(acked)} adjudicated with reasons")
    else:
        lines.append("PASS — 0 blockers, 0 advisories, nothing adjudicated")
    return "\n".join(lines)


def cmd_verify(args):
    """Acceptance gate: run all lint checks and render a readable report.

    Exit codes: 0 = pass (warnings allowed unless --strict), 1 = errors present,
    2 = --strict and advisory warnings remain (info-level measurements pass).
    """
    deck = prepare(load(args.deck))
    result = lint_deck(deck)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_verify_report(deck, result))
    if result["errors"]:
        return 1
    if args.strict and any(
            w.get("severity") != "info" for w in result["warnings"]):
        return 2
    return 0


def cmd_build(args):
    deck = prepare(load(args.deck))
    result = lint_deck(deck)
    if not result["ok"] and not args.force:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("BUILD BLOCKED: fix diagnostics or pass --force", file=sys.stderr)
        return 1
    out = build_pptx(deck, args.out, force=bool(args.force))
    print(f"built: {out} ({len(deck['slides'])} slides)")

    # ---- 成品侧强制审计（交付前最后一关）----
    # 为什么必须在这里再查一遍：lint_deck 只读 DSL。模型完全可以自己写
    # python-pptx 拼出 pptx，一声不响地交付——12 页同构翻车就是这么发生的。
    # 判据存在但不挂在交付路径上，等于没有。所以 build 出片后立刻读成品文件，
    # 设计不成立就明确报失败（退出码 1），不让「已交付」这个假象成立。
    from engine.design_audit import audit_design
    design = audit_design(out)
    if not design["ok"]:
        print(f"\n[成品审计未通过] {design['verdict']}", file=sys.stderr)
        for key in ("thin_pages", "bare_pages", "collisions", "clipped"):
            val = design.get(key)
            if val:
                print(f"  {key}: {val}", file=sys.stderr)
        if design.get("skeleton_groups"):
            print(f"  骨架重复组: {design['skeleton_groups']}", file=sys.stderr)
        print("成品已写出但不达标：这份文件不能当交付物。"
              "修 DS/版面后重跑 build。", file=sys.stderr)
        return 1

    print(f"audit-design: OK  {design['verdict']}")
    if args.force:
        print("WARNING: built with --force; marker written into the pptx",
              file=sys.stderr)
    return 0


def cmd_render(args):
    """Render a deck DSL to a folder of PNG contact sheets (no pptx needed).

    This is the per-page visual readback half of the hand-built freeform loop:
    edit DSL -> `render` -> look at the PNG -> revise, without opening
    PowerPoint. Lint is informational here (a --strict caller can gate on it);
    PNGs are always written so geometry can be inspected even mid-fix.
    """
    from engine import debug_render
    deck = prepare(load(args.deck))
    result = lint_deck(deck)
    if not result["ok"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("RENDER NOTE: lint errors present; PNGs emitted anyway for "
              "debugging", file=sys.stderr)
    paths = debug_render.render(deck, args.out_dir)
    print(f"rendered {len(paths)} slide(s) -> {os.path.abspath(args.out_dir)}")
    for p in paths:
        print(p)
    return 0


def cmd_compose(args):
    """Stage 1-2: notes + reference cover -> per-page composed DSL."""
    from engine import art_direction
    notes_path = os.path.abspath(args.notes)
    notes = load(notes_path)

    # 六维设计规格：优先 --briefs；否则读 notes 里的 design_briefs。
    # 两处都没有时交给 compose() 报错（它会区分「没传」和「声明走原型兜底」）。
    design_briefs = None
    briefs_path = getattr(args, "briefs", None)
    if briefs_path:
        design_briefs = load(os.path.abspath(briefs_path))
    elif isinstance(notes.get("design_briefs"), dict):
        design_briefs = notes["design_briefs"]

    try:
        deck, ledger = art_direction.compose(
            notes, os.path.dirname(notes_path), args.cover, args.base, args.seed,
            card_system=getattr(args, "card_system", False),
            scoring=getattr(args, "scoring", False),
            design_briefs=design_briefs)
    except ValueError as exc:
        print(f"COMPOSE BLOCKED: {exc}", file=sys.stderr)
        return 1
    out = args.out or os.path.splitext(notes_path)[0] + "_composed.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(deck, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if args.ledger:
        with open(args.ledger, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
            f.write("\n")
    plan_out = getattr(args, "emit_plan", None)
    if plan_out:
        from engine import page_spec
        S = art_direction._style(deck.get("derived_theme"), args.base)
        deck_plan = page_spec.build_deck_plan(
            notes, ledger["archetypes"], S, base=args.base)
        with open(plan_out, "w", encoding="utf-8") as f:
            json.dump(deck_plan, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"plan: {plan_out} ({len(deck_plan['pages'])} page specs)")
    print(f"composed: {out} ({len(deck['slides'])} pages, "
          f"{deck['art_direction']['distinct']} distinct archetypes)")
    return 0


def cmd_svgguard(args):
    from engine import svg_guard
    return svg_guard.run(args.plan, args.svg_dir)


def cmd_ledger(args):
    """校验版式账本：重复 layout_id / 相邻同族 / family 间隔硬闸。"""
    from engine import layout_ledger
    result = layout_ledger.validate_file(args.ledger)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def cmd_compile_svg(args):
    import os as _os
    from engine import pptmaster_bridge
    project = _os.path.abspath(args.project)
    out = _os.path.abspath(args.out)
    if not _os.path.isdir(project):
        print(f"COMPILE-SVG BLOCKED: not a directory: {project}", file=sys.stderr)
        return 1
    root = pptmaster_bridge.require_root()
    if not args.skip_quality:
        # 通用质检默认；--strict 走 ppt-master canonical/final 硬闸
        checker = root / "scripts" / "svg_quality_checker.py"
        qargv = [project]
        if args.strict:
            qargv += ["--canonical-authoring", "--stage", "final", "--json"]
        code = pptmaster_bridge._run_script(checker, qargv)
        if code != 0:
            print("COMPILE-SVG BLOCKED: quality gate failed", file=sys.stderr)
            return code
    compiler = root / "scripts" / "svg_to_pptx.py"
    pptmaster_bridge._run_script(compiler, [project, "-o", out])
    return 0


def cmd_inspect(args):
    """Structure report for an existing .pptx (read-only)."""
    from engine import pptx_edit
    report = pptx_edit.inspect(args.pptx)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"inspected: {args.out} ({report['slide_count']} slides)")
    else:
        print(text)
    return 0


def cmd_audit_pptx(args):
    """检查已成型的 pptx 有没有照抄版面——只读坐标，不看 DSL。

    这个命令存在的唯一理由：所有挂在 DSL 上的闸门，遇到「绕开 compose()、
    自己写 Python 拼 pptx」的产物就完全失效。历史上有过 122 页这样的交付
    物（lib.py 1011 行、22 个 p_* 函数、deck.json 里 design_brief 全空），
    闸门一次都没执行。判据必须能落在最终产物的坐标上。
    """
    from engine import pptx_audit, pptx_edit
    report = pptx_edit.inspect(args.pptx)
    result = pptx_audit.audit_pptx(report, max_pages=args.max_pages)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"审计对象: {os.path.basename(args.pptx)}")
        print(f"页数: {result['slide_count']}   阈值: 单副骨架 ≥{result['threshold']} 页")
        if result["exempted"]:
            shown = "、".join(str(p) for p in result["exempted"][:10])
            more = f" 等 {len(result['exempted'])} 页" if len(result["exempted"]) > 10 else ""
            print(f"按仪式页豁免（文字极少）: 第 {shown}{more}")
        print("-" * 60)
        if result["ok"]:
            print("通过：没有发现成片照抄同一副骨架的页面")
        else:
            print("不通过：以下页面共用同一副几何骨架")
            for g in result["groups"]:
                shown = "、".join(str(p) for p in g["pages"][:12])
                more = f" 等 {g['count']} 页" if g["count"] > 12 else ""
                print(f"  {g['count']:>3} 页  第 {shown}{more}")
            print()
            print("内容不同的页必须真的排出不同结构。这组页面的坐标骨架一样，"
                  "说明是先有模板再往里填，不是读完内容再决定怎么排。")
        if result["unreadable"]:
            print(f"\n注意：{result['unreadable']} 个形状读不到坐标，未纳入判定")
    return 0 if result["ok"] else 1


def cmd_audit_notes(args):
    """检查已成型的 pptx 有没有演讲者备注——只读成品，不看 DSL。

    与 audit-pptx 同源：DSL 侧的 NOTES_COVERAGE 闸门对「绕开 compose() 手写
    pptx」的产物静默失效。实测那本 91 页《英伟达之道》备注 0/91，lint 从没响过。
    """
    from engine import pptx_notes
    result = pptx_notes.audit_notes(args.pptx)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    print(f"审计对象: {os.path.basename(args.pptx)}")
    print(f"页数: {result['slide_count']}   参与判定: {result['judged_slides']}"
          f"   备注覆盖: {result['covered']}/{result['judged_slides']}"
          f" ({result['coverage']:.1%})")
    print(f"档位: {result['tier']}   均长: {result['mean_len']} 字"
          f"   过薄线: {result['tier_floor']} 字")
    if result["exempted"]:
        shown = "、".join(str(p) for p in result["exempted"][:10])
        more = f" 等 {len(result['exempted'])} 页" if len(result["exempted"]) > 10 else ""
        print(f"按仪式页豁免（文字极少）: 第 {shown}{more}")
    print("-" * 60)
    if result["ok"]:
        print("通过：每页都有足够讲稿，且没有成片模板化")
    else:
        if result["missing_pages"]:
            shown = "、".join(str(p) for p in result["missing_pages"][:15])
            more = (f" 等 {len(result['missing_pages'])} 页"
                    if len(result["missing_pages"]) > 15 else "")
            print(f"缺备注: 第 {shown}{more}")
        if result["thin_pages"]:
            shown = "、".join(f"第{t['page']}页({t['len']}字)"
                             for t in result["thin_pages"][:10])
            more = (f" 等 {len(result['thin_pages'])} 页"
                    if len(result["thin_pages"]) > 10 else "")
            print(f"过薄: {shown}{more}")
        if result["templated"]:
            t = result["template"]
            print(f"模板化: 同一句话反复出现，超过 {result['template_limit']:.0%} 的线")
            if t["tail_repeat"] > result["template_limit"]:
                print(f"  结尾 12 字重复 {t['tail_repeat']:.1%} → {t['top_tail']!r}")
            if t["head_repeat"] > result["template_limit"]:
                print(f"  开头 8 字重复 {t['head_repeat']:.1%} → {t['top_head']!r}")
            print("  字数凑够了不等于讲得出口。每页该怎么讲，取决于这一页讲的是什么，"                  "不能套同一个模子。")
        if result["missing_pages"] or result["thin_pages"] or result["templated"]:
            print()
            print("演讲者备注是交付物的一部分，不是可选项。`fill-notes` 只能"
                  "出一版只重组页内文字的急救稿；要交货，讲稿得逐页写。")
    return 0 if result["ok"] else 1


def cmd_fill_notes(args):
    """把讲稿写进成品 pptx。

    两种模式，能力边界完全不同：
      --notes-file  正路。模型逐页写好讲稿，引擎只负责写进去。
      不给          急救。引擎只能重组页内已有文字，必然带模板痕迹，
                    audit-notes 会判「模板化」。
    """
    from engine import pptx_notes_fill

    if args.notes_file:
        r = pptx_notes_fill.fill_notes_from_file(
            args.pptx, args.notes_file, out_path=args.out,
            overwrite=args.overwrite)
        print(f"写入 {r['written']}/{r['total']} 页讲稿"
              f"（跳过已有讲稿 {r['skipped']} 页）→ {r['out']}")
        if r["missing"]:
            shown = "、".join(str(p) for p in r["missing"][:20])
            more = f" 等 {len(r['missing'])} 页" if len(r["missing"]) > 20 else ""
            print(f"注意：讲稿没覆盖到第 {shown}{more}——这些页保持原样，"                  f"引擎不会拿模板顶上")
        return 0

    r = pptx_notes_fill.fill_notes(
        args.pptx, out_path=args.out, overwrite=args.overwrite)
    print(f"急救稿回填 {r['filled']}/{r['total']} 页"
          f"（跳过已有备注 {r['skipped']} 页）→ {r['out']}")
    print("提醒：这是只重组页内文字的急救稿，必然带模板痕迹。"
          "正路是模型逐页写好讲稿后用 --notes-file 写入。")
    return 0


def cmd_audit_design(args):
    """检查成品 pptx 的版面设计——判「这一页有没有被设计过」。

    存在的理由：我长期把「配图数量」当成版面质量的指标，方向是错的。用户拿出
    一份 10 页的参照（零配图、每页 38.7 个形状、45 条分隔线），明说「页面设计
    才是核心」。实测对照后确认：版面质量来自页面框架、结构件密度、分隔线组织、
    以及每页不同的视觉论证，跟有没有图片无关。
    """
    from engine import design_audit
    r = design_audit.audit_design(args.pptx)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1

    pp = r["per_page"]
    shapes = sorted(p["shapes"] for p in pp)
    structs = sorted(p["structure"] for p in pp)
    print(f"审计对象: {os.path.basename(args.pptx)}")
    print(f"页数: {r['slide_count']}")
    print(f"形状/页: 中位 {shapes[len(shapes) // 2]}  最少 {shapes[0]}  最多 {shapes[-1]}")
    print(f"结构件/页（色块/线条等）: 中位 {structs[len(structs) // 2]}  最少 {structs[0]}")
    print(f"分隔线: {r['dividers_total']} 条，覆盖 {r['divider_ratio']:.0%} 的页面")
    print(f"页面框架: 页眉 {r['chrome']['header']}/{r['slide_count']} 页"
          f"，页脚 {r['chrome']['footer']}/{r['slide_count']} 页")
    print(f"配图: {sum(p['pictures'] for p in pp)} 张"
          f"（不参与判定——参照 deck 是零配图）")
    print("-" * 60)
    print(("通过：" if r["ok"] else "不通过：") + r["verdict"])
    if r["skeleton_groups"]:
        print()
        print("同骨架页组（视觉论证重复）:")
        for g in r["skeleton_groups"][:6]:
            shown = "、".join(str(p) for p in g["pages"][:10])
            print(f"  {g['count']:>3} 页  第 {shown}")
    if not r["ok"]:
        print()
        print("每一页的版面形状应该是这页内容的论证结构：递进就用阶梯，对比就用")
        print("两栏，分类就用矩阵，占比就用条形。形状重复意味着没在读内容。")
    return 0 if r["ok"] else 1


def cmd_preview(args):
    """把 pptx 渲染成 PNG，一页一张——几何判据看不见「字压字」。

    存在的理由（教训）：audit-design 曾给一份 5 页样本判 ok=True，而实际渲染
    出来标题压在正文上、色带里的标签和说明叠成一团、右下角页码被裁掉一半。
    几何测量能数清「有几个结构件」，数不出「这两个字是不是叠在一起」。

    所以判据通过之后必须再看一眼。这条命令就是那一眼。
    """
    import shutil
    import subprocess
    import tempfile

    src = os.path.abspath(args.pptx)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        print("需要 LibreOffice 才能渲染。装好后重试，或直接打开 pptx 看。",
              file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                            "--outdir", tmp, src],
                           capture_output=True, text=True, timeout=180)
        pdfs = [f for f in os.listdir(tmp) if f.endswith(".pdf")]
        if not pdfs:
            print("转换失败：" + (r.stderr or r.stdout)[-400:], file=sys.stderr)
            return 1
        pdf = os.path.join(tmp, pdfs[0])

        try:
            import pymupdf
        except ImportError:
            # 没有 pymupdf 就保留 PDF，让人自己翻
            shutil.copy(pdf, os.path.join(out_dir, "deck.pdf"))
            print(f"未装 pymupdf，已保留 PDF: {os.path.join(out_dir, 'deck.pdf')}")
            return 0

        doc = pymupdf.open(pdf)
        written = []
        for i, page in enumerate(doc, 1):
            p = os.path.join(out_dir, f"p{i:02d}.png")
            page.get_pixmap(dpi=args.dpi).save(p)
            written.append(p)
        doc.close()

    print(f"渲染 {len(written)} 页 -> {out_dir}")
    for p in written:
        print(p)
    return 0


def cmd_retext(args):
    """Replace text in an existing .pptx, preserving run formatting."""
    from engine import pptx_edit
    with open(args.map, encoding="utf-8") as f:
        spec = json.load(f)
    edits = spec.get("edits", []) if isinstance(spec, dict) else spec
    report = pptx_edit.retext(args.pptx, edits, args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["missed"] else 1


def cmd_patch(args):
    """Revise one or more DSL nodes, then re-run the lint gate."""
    from engine import deck_patch
    spec = load(args.deck)
    try:
        changes = deck_patch.apply_sets(spec, args.set)
    except (KeyError, ValueError) as exc:
        print(f"PATCH REJECTED: {exc}", file=sys.stderr)
        print("Check the dotted path against the deck JSON first.", file=sys.stderr)
        return 1
    text = json.dumps(spec, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"patched: {args.out} ({len(changes)} nodes)")
    if args.build:
        deck = prepare(spec)
        result = lint_deck(deck)
        if not result["ok"] and not args.force:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("PATCH BUILD BLOCKED: fix diagnostics", file=sys.stderr)
            return 1
        out = build_pptx(deck, args.build, force=bool(args.force))
        print(f"rebuilt: {out} ({len(deck['slides'])} slides)")
    if not args.out and not args.build:
        print(text)
    print(json.dumps({"changes": changes}, ensure_ascii=False))
    return 0


def cmd_make(args):
    """Pure CLI: rough text -> filled deck spec -> lint -> PPTX (no LLM)."""
    from engine import brief_fill, content_ai, reports
    text = args.brief
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as f:
            text = f.read()
    if text is None:
        text = sys.stdin.read()
    meta = {"theme": args.theme, "title": args.title,
            "subtitle": args.subtitle, "org": args.org, "date": args.date}
    spec = brief_fill.build_from_brief(args.type, text, meta)
    from engine import typography
    if args.cjk_spacing:
        def add_spacing(obj):
            if isinstance(obj, str):
                return typography.latin_cjk_spacing(obj)
            if isinstance(obj, dict):
                return {k: add_spacing(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [add_spacing(v) for v in obj]
            return obj
        spec["slides"] = add_spacing(spec["slides"])
    spec["typography"] = typography.metadata()
    spec["typography"]["latin_cjk_spacing"] = bool(args.cjk_spacing)
    if args.out_deck:
        with open(args.out_deck, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
            f.write("\n")
    content = content_ai.check_content(spec)
    if content["errors"] and not args.force:
        print(json.dumps(content, ensure_ascii=False, indent=2))
        print("MAKE BLOCKED: content gate failed", file=sys.stderr)
        return 1
    deck = prepare(spec)
    result = lint_deck(deck)
    if not result["ok"] and not args.force:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("MAKE BLOCKED: fix diagnostics or pass --force", file=sys.stderr)
        return 1
    out = build_pptx(deck, args.out, force=bool(args.force))
    print(f"made: {out} ({len(deck['slides'])} slides, "
          f"type={args.type}, llm=off, network=off)")
    return 0


def cmd_style(args):
    """Derive a reproducible theme spec from a reference cover image."""
    from engine import cover_style
    spec, ledger = cover_style.derive(args.cover, args.book, args.base)
    out = args.out or os.path.splitext(args.cover)[0] + "_style.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"derived: {out} | accent {spec['semantic']['accent']} | "
          f"motif {spec['source']['motif']}")
    return 0


def cmd_selfcheck(args):
    """验闸门本身是否真的存在、真的能拦。

    做法不是读文档、也不是罗列配置，而是**当场造样本跑一遍**：
    故意生成一份「122 页同构、每页只有版式名没有设计简报」的 deck，
    交给 lint 判；再生成一份正常产物做对照，确认没有误伤。

    任何人（包括不信这套说法的人）都可以跑这条命令自己看结果，
    不需要相信任何人的汇报。
    """
    from engine import design_spec, layout_fingerprint

    checks = []

    # --- 样本零：六维设计规格闸门本身 ---
    # 造一份六维齐全的规格 → 必须过；再逐维删一个 → 必须被拦。
    # 这是「模型逐页当设计师」这条最高原则的执行体，它失效等于原则失效。
    _ds = {"palette": {}, "type_scale": {}, "spacing": {}, "font_pair": {}}
    _full = {
        "structure": "否定墙：左六灰块，右一亮块",
        "hierarchy": "第一眼亮块，第二眼灰块阵，辅助是来源行",
        "components": [{"name": "灰块阵", "role": "列举被否定做法"},
                       {"name": "亮块", "role": "唯一保留答案"}],
        "states": {"default": "全灰+右亮", "emphasis": "描边加粗"},
        "responsive": "窄屏 960px 以下两列改堆叠",
        "a11y": {"contrast": "8.2:1", "text_size": "最小 13.5pt"},
        "consistency": ["palette", "type_scale"],
        "rationale": "六个假的对照一个真的，需并列否定而非编号行",
    }
    _ok_brief = not design_spec.check_brief(
        {"design_brief": _full}, 1, design_system=_ds)
    checks.append((
        "六维规格齐全 → 放行", _ok_brief, "无问题项" if _ok_brief else "被误伤"))

    _dropped = []
    for _dim in ("structure", "hierarchy", "components", "states",
                 "responsive", "a11y", "consistency", "rationale"):
        _b = dict(_full)
        _b.pop(_dim)
        if design_spec.check_brief({"design_brief": _b}, 1, design_system=_ds):
            _dropped.append(_dim)
    checks.append((
        "八维任一维缺失 → 必被拦",
        len(_dropped) == 8,
        f"{len(_dropped)}/8 维能拦住" + ("" if len(_dropped) == 8
                                        else f"，漏了 {_dropped}"),
    ))

    # --- 样本一：122 页手写模板（复刻真实翻车形态）---
    bad = {"composed": True, "theme": "consulting", "slides": []}
    for i in range(122):
        bad["slides"].append({
            "type": "content", "tone": "light", "surface": "#FFFFFF",
            "composition": "freeform",
            # 每页自报一个不同的版式名——旧闸门就是这么被骗过去的
            "archetype": f"自造版式-{i % 6}",
            "density": "mid",
            "children": [
                {"t": "shape", "kind": "rect", "rect": [60, 184, 30, 30],
                 "fill": "#12263A", "decor": True},
                {"t": "text", "rect": [60, 86, 1080, 44],
                 "text": f"第 {i} 页标题", "size": 32},
                {"t": "text", "rect": [104, 190, 200, 24],
                 "text": f"标签{i}", "size": 14},
                {"t": "text", "rect": [340, 190, 860, 60],
                 "text": f"说明文字{i}", "size": 11},
            ],
        })
    res = lint_deck(prepare(bad))
    codes = {e["code"] for e in res["errors"]}
    checks.append((
        "同构 deck（122 页、无设计简报）必须编译不过",
        not res["ok"],
        f"ok={res['ok']}, blockers={res['severity_summary']['blockers']}, "
        f"codes={sorted(codes)}",
    ))
    checks.append((
        "必须报出「缺六维设计规格」",
        "DESIGN_SPEC_MISSING" in codes, "DESIGN_SPEC_MISSING",
    ))
    checks.append((
        "必须报出「几何骨架重复」（不听自报版式名）",
        "LAYOUT_SKELETON_REPEAT" in codes, "LAYOUT_SKELETON_REPEAT",
    ))

    # --- 样本二：改标签能不能骗过判据 ---
    base = {"children": [
        {"t": "text", "rect": [60, 80, 600, 40], "text": "标题"},
        {"t": "text", "rect": [60, 200, 300, 24], "text": "标签"},
    ]}
    a = dict(base, archetype="名字甲")
    b = dict(base, archetype="名字乙")
    checks.append((
        "换版式名但几何不变 → 判据仍认定同骨架",
        layout_fingerprint.skeleton(a) == layout_fingerprint.skeleton(b),
        "两页指纹相同",
    ))

    # --- 样本三：占位话术算不算没填 ---
    junk_rejected = all(
        design_spec.check_brief(
            {"design_brief": dict(_full, structure=junk)}, 1,
            design_system=_ds)
        for junk in ("无", "TBD", "同上", "  ")
    )
    checks.append(("规格里写「无 / TBD / 同上」算没填", junk_rejected,
                   "占位话术被拒"))

    # --- 样本四：正常产物不能被误伤 ---
    notes_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "examples", "notes_renqing_mianzi.json")
    if os.path.exists(notes_path):
        from engine import art_direction as _ad
        with open(notes_path, encoding="utf-8") as f:
            ok_notes = json.load(f)
        ok_notes["brief_pool"] = "prototype"
        deck_ok, _ = _ad.compose(ok_notes,
                                 os.path.dirname(notes_path))
        res_ok = lint_deck(prepare(deck_ok))
        checks.append(("正常产物不能被误伤", res_ok["ok"],
                       f"ok={res_ok['ok']}, "
                       f"blockers={res_ok['severity_summary']['blockers']}"))

    # --- 样本五：入口闸门 ---
    try:
        _ad.compose({"book": {"title": "x"},
                     "pages": [{"kind": "concept", "title": "测试页",
                                "points": [{"head": "甲", "body": "内容"}]}]})
        entry_ok = False
    except ValueError:
        entry_ok = True
    checks.append(("compose() 没收到设计简报就失败", entry_ok, "抛出 ValueError"))

    # --- 样本六：绕开 compose() 直接手写 pptx，闸门还能不能拦 ---
    # 这是这套闸门曾经最大的漏口：所有 DSL 闸门对「自己写 Python 拼 pptx」
    # 的产物完全失效，而那正是 122 页翻车产物的生成方式。所以这里真的
    # 生成一份 pptx 文件，交给 audit-pptx 判——不是模拟，是端到端跑一遍。
    try:
        from pptx import Presentation
        from pptx.util import Emu
        from engine import pptx_audit, pptx_edit

        prs = Presentation()
        prs.slide_width = Emu(12192000)      # 16:9，与 DSL 画布 1280×720 对齐
        prs.slide_height = Emu(6858000)
        blank = prs.slide_layouts[6]
        emu_per_px = 9525

        def _box(slide, x, y, w, h, text=""):
            tb = slide.shapes.add_textbox(
                Emu(int(x * emu_per_px)), Emu(int(y * emu_per_px)),
                Emu(int(w * emu_per_px)), Emu(int(h * emu_per_px)))
            if text:
                tb.text_frame.text = text
            return tb

        for i in range(12):
            s = prs.slides.add_slide(blank)
            _box(s, 60, 86, 1080, 44, f"第 {i} 页标题：这一页讲一件完全不同的事")
            _box(s, 104, 190, 200, 24, f"标签{i}")
            _box(s, 340, 190, 860, 60,
                 "这是一整段说明文字，用来确保这一页被判定为内容页而不是"
                 "文字极少的仪式页，长度故意超过豁免阈值。")
            _box(s, 60, 300, 520, 120, "左下要点甲，内容各不相同")
            _box(s, 620, 300, 520, 120, "右下要点乙，内容各不相同")

        tmp_pptx = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scratch", "_selfcheck_handwritten.pptx")
        os.makedirs(os.path.dirname(tmp_pptx), exist_ok=True)
        prs.save(tmp_pptx)

        rep = pptx_edit.inspect(tmp_pptx)
        hand = pptx_audit.audit_pptx(rep, max_pages=5)
        checks.append((
            "绕开 compose() 手写 pptx → audit-pptx 仍能抓住照抄版面",
            not hand["ok"] and bool(hand["groups"]),
            f"12 页同构结果 groups={[g['count'] for g in hand['groups']]}",
        ))

        # --- 样本七：备注。同一份手写 pptx 一个 notesSlide 都没有，
        # DSL 侧的 NOTES_COVERAGE 全程静默（真实事故：91 页那本备注 0/91）。
        # 这里同样端到端跑：先判它不通过，再回填，再判它通过。
        from engine import pptx_notes, pptx_notes_fill

        n_before = pptx_notes.audit_notes(tmp_pptx)
        checks.append((
            "绕开 compose() 手写 pptx → audit-notes 仍能判出备注缺失",
            not n_before["ok"] and n_before["covered"] == 0,
            f"0 备注结果 covered={n_before['covered']}/"
            f"{n_before['judged_slides']}, ok={n_before['ok']}",
        ))

        fill_out = os.path.join(os.path.dirname(tmp_pptx), "_selfcheck_notes.pptx")
        pptx_notes_fill.fill_notes(tmp_pptx, out_path=fill_out)
        n_after = pptx_notes.audit_notes(fill_out)
        # 急救通道的定位：把空备注补满（覆盖 100%），但不假装它达标。
        # 上一版这里断言 n_after["ok"] —— 加了模板化判据后它必然为 False，
        # 断言的其实是旧认知（"填满就算过"）。现在如实拆成两条。
        checks.append((
            "fill-notes 能把备注缺口补满（覆盖率到 100%）",
            n_after["coverage"] == 1.0 and n_after["missing_pages"] == [],
            f"回填后覆盖={n_after['coverage']:.1%} 均长={n_after['mean_len']} "
            f"档位={n_after['tier']}",
        ))

        # 幂等：对已回填的文件再跑一次，应当一页都不改
        n_idem = pptx_notes_fill.fill_notes(fill_out, out_path=fill_out)
        checks.append((
            "fill-notes 默认幂等（已有备注不被覆盖）",
            n_idem["filled"] == 0,
            f"二次运行回填了 {n_idem['filled']} 页",
        ))

        # 急救通道本身带模板痕迹，审计必须拦下它——这是刻意设的红灯。
        checks.append((
            "fill-notes 的产物被判「模板化」（急救通道就该拦）",
            n_after["templated"] and not n_after["ok"],
            f"结尾重复率={n_after['template']['tail_repeat']:.0%}",
        ))

        # --- 样本八：版面设计。三组对照，全部端到端造文件：
        #   ① 只有文字块的裸排布 → 必须判不成立（我方 91 页翻车形态）
        #   ② 参照语法（页眉框架+徽章+细条+分隔线+每页不同论证）→ 必须判成立
        #   ③ 把②的分隔线全删掉 → 必须重新判不成立（证明分隔线判据有约束力）
        from engine import design_audit

        def _bare_page(s, i):
            _box(s, 60, 86, 1080, 44, f"第 {i} 页标题")
            _box(s, 104, 190, 900, 60, "一整段说明文字，用来把这一页变成内容页。")
            _box(s, 60, 300, 520, 120, "要点甲")
            _box(s, 620, 300, 520, 120, "要点乙")

        bare_prs = Presentation()
        bare_prs.slide_width = Emu(12192000)
        bare_prs.slide_height = Emu(6858000)
        for i in range(6):
            _bare_page(bare_prs.slides.add_slide(blank), i)
        bare_path = os.path.join(os.path.dirname(tmp_pptx), "_selfcheck_bare.pptx")
        bare_prs.save(bare_path)
        d_bare = design_audit.audit_design(bare_path)
        checks.append((
            "只有文字块、没有版面结构 → audit-design 判不成立",
            not d_bare["ok"],
            f"结构件中位={sorted(p['structure'] for p in d_bare['per_page'])[len(d_bare['per_page']) // 2]}, "
            f"分隔线页占比={d_bare['divider_ratio']:.0%}",
        ))

        designed = design_audit.build_reference_sample()   # 用参照语法现造一份
        designed_path = os.path.join(os.path.dirname(tmp_pptx), "_selfcheck_designed.pptx")
        designed.save(designed_path)
        d_ok = design_audit.audit_design(designed_path)
        checks.append((
            "参照语法（框架+徽章+细条+分隔线+每页不同论证）→ 判成立",
            d_ok["ok"],
            f"每页形状 {min(p['shapes'] for p in d_ok['per_page'])}–"
            f"{max(p['shapes'] for p in d_ok['per_page'])}，"
            f"分隔线 {d_ok['dividers_total']} 条，同骨架最多 {d_ok['max_repeat']} 页",
        ))

        for p in (tmp_pptx, fill_out, bare_path, designed_path):
            if os.path.exists(p):
                os.remove(p)
    except Exception as exc:                    # 环境缺 python-pptx 等
        checks.append((
            "绕开 compose() 手写 pptx → audit-pptx 仍能抓住照抄版面",
            False, f"无法完成端到端验证：{type(exc).__name__}: {exc}",
        ))

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print("FreePPT 闸门自检 —— 现场造样本跑一遍，不读文档")
    print("=" * 60)
    for name, ok, detail in checks:
        print(("  [PASS] " if ok else "  [FAIL] ") + name)
        print("         " + detail)
    print("-" * 60)
    print(f"{passed}/{total} 项通过 —— "
          + ("闸门确实生效" if passed == total else "有闸门未生效，需要修"))
    return 0 if passed == total else 1


def cmd_design_system(args):
    """Scaffold/validate a model-driven design-system card from a reference."""
    from engine import design_system
    if args.ds_action == "scaffold":
        card, md = design_system.scaffold(args.reference or "", args.book)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=2)
            f.write("\n")
        with open(args.checklist, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"design-system card -> {args.out} | checklist -> {args.checklist}")
        return 0
    card_path = args.card or args.reference
    if not card_path:
        print("design-system validate needs a card path", file=sys.stderr)
        return 2
    with open(card_path, "r", encoding="utf-8") as f:
        card = json.load(f)
    ok, report = design_system.validate(card)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_lint = sub.add_parser("lint")
    p_lint.add_argument("deck")
    p_lint.set_defaults(func=cmd_lint)
    p_vf = sub.add_parser(
        "verify", help="acceptance report aggregating layout/geometry/closing checks")
    p_vf.add_argument("deck")
    p_vf.add_argument("--json", action="store_true",
                      help="emit the raw lint JSON instead of the readable report")
    p_vf.add_argument("--strict", action="store_true",
                      help="treat advisory warnings as failure (exit 2)")
    p_vf.set_defaults(func=cmd_verify)
    p_build = sub.add_parser("build")
    p_build.add_argument("deck")
    p_build.add_argument("out")
    p_build.add_argument("--force", action="store_true")
    p_build.set_defaults(func=cmd_build)
    p_rd = sub.add_parser(
        "render", help="render a deck DSL to PNG contact sheets (visual readback)")
    p_rd.add_argument("deck")
    p_rd.add_argument("out_dir", help="folder to write slideNN.png into")
    p_rd.set_defaults(func=cmd_render)
    p_cp = sub.add_parser("compose", help="creative page-by-page composition")
    p_cp.add_argument("notes", help="notes JSON (book + pages)")
    p_cp.add_argument("--cover", help="reference cover image (overrides notes)")
    p_cp.add_argument("--briefs",
                      help="per-page design specs JSON (six dimensions). "
                           "Required unless notes declares brief_pool=prototype")
    p_cp.add_argument("--base", default="magazine")
    p_cp.add_argument("--seed", help="override the deterministic seed")
    p_cp.add_argument("--card-system", action="store_true",
                      help="enable glass-panel / icon-grid / numbered-cards archetypes")
    p_cp.add_argument("--scoring", action="store_true",
                      help="rank archetypes by deterministic content fit instead of shuffle")
    p_cp.add_argument("--out", help="output composed deck DSL")
    p_cp.add_argument("--ledger", help="output style provenance ledger")
    p_cp.add_argument("--emit-plan",
                      help="emit coordinate-free Deck Plan (plan.json) for the "
                           "SVG authoring layer + svg_guard")
    p_cp.set_defaults(func=cmd_compose)
    p_st = sub.add_parser("style", help="derive a theme from a cover image")
    p_st.add_argument("cover")
    p_st.add_argument("--book", default="")
    p_st.add_argument("--base", default="magazine")
    p_st.add_argument("--out")
    p_st.set_defaults(func=cmd_style)
    p_sc = sub.add_parser(
        "selfcheck",
        help="verify the per-page design gates actually fire (builds bad "
             "samples and runs them, instead of trusting documentation)")
    p_sc.set_defaults(func=cmd_selfcheck)
    p_ds = sub.add_parser(
        "design-system",
        help="scaffold/validate a model-driven design-system card from a reference image")
    p_ds.add_argument("ds_action", choices=["scaffold", "validate"])
    p_ds.add_argument("reference", nargs="?", help="reference image (scaffold) or card json (validate)")
    p_ds.add_argument("--book", default="")
    p_ds.add_argument("--out", default="design_system_card.json")
    p_ds.add_argument("--checklist", default="design_system_checklist.md")
    p_ds.add_argument("--card", help="filled card path for validate")
    p_ds.set_defaults(func=cmd_design_system)
    p_mk = sub.add_parser("make", help="plain text -> PPTX, no LLM")
    p_mk.add_argument("brief", nargs="?", help="rough notes; reads stdin if omitted")
    p_mk.add_argument("--from-file", help="read the brief from a UTF-8 text file")
    p_mk.add_argument("--type", default="weekly",
                      choices=[k for k, _ in reports.list_types()])
    p_mk.add_argument("--theme", help="override the report's default theme")
    p_mk.add_argument("--title")
    p_mk.add_argument("--subtitle")
    p_mk.add_argument("--org")
    p_mk.add_argument("--date")
    p_mk.add_argument("--out", required=True, help="output .pptx path")
    p_mk.add_argument("--out-deck", help="also save the filled deck DSL")
    p_mk.add_argument("--cjk-spacing", action="store_true",
                      help="insert thin spaces between CJK and Latin/digit runs")
    p_mk.add_argument("--force", action="store_true")
    p_mk.set_defaults(func=cmd_make)
    p_in = sub.add_parser("inspect", help="structural report for an existing pptx")
    p_in.add_argument("pptx")
    p_in.add_argument("--out")
    p_in.set_defaults(func=cmd_inspect)
    p_au = sub.add_parser(
        "audit-pptx",
        help="check a finished pptx for copied layouts (reads coordinates, "
             "so it catches decks that bypassed compose() and wrote pptx by hand)")
    p_au.add_argument("pptx")
    p_au.add_argument("--max-pages", type=int, default=5,
                      help="a skeleton shared by this many pages is a defect "
                           "(default 5, calibrated on real output)")
    p_au.add_argument("--json", action="store_true")
    p_au.set_defaults(func=cmd_audit_pptx)
    p_an = sub.add_parser(
        "audit-notes",
        help="check speaker notes on a finished pptx (reads the file, so it "
             "catches decks that bypassed compose() and wrote pptx by hand)")
    p_an.add_argument("pptx")
    p_an.add_argument("--json", action="store_true")
    p_an.set_defaults(func=cmd_audit_notes)
    p_ad = sub.add_parser(
        "audit-design",
        help="check whether each page was actually designed (frame, structure "
             "density, dividers, variety) — images are NOT part of the judgement")
    p_ad.add_argument("pptx")
    p_ad.add_argument("--json", action="store_true")
    p_ad.set_defaults(func=cmd_audit_design)
    p_pv = sub.add_parser(
        "preview",
        help="render a pptx to one PNG per page — the check geometry can't do: "
             "whether text actually overlaps")
    p_pv.add_argument("pptx")
    p_pv.add_argument("out_dir")
    p_pv.add_argument("--dpi", type=int, default=110)
    p_pv.set_defaults(func=cmd_preview)
    p_fn = sub.add_parser(
        "fill-notes",
        help="write speaker notes into a finished pptx: --notes-file for "
             "model-written scripts (the real path), or no flag for an "
             "emergency re-organisation of page text")
    p_fn.add_argument("pptx")
    p_fn.add_argument("--out", help="output pptx (default: overwrite in place)")
    p_fn.add_argument("--notes-file", help="JSON of model-written notes, the "
                                          "real path; engine writes, never invents")
    p_fn.add_argument("--overwrite", action="store_true",
                      help="rewrite pages that already have notes")
    p_fn.set_defaults(func=cmd_fill_notes)
    p_rt = sub.add_parser("retext", help="replace text in an existing pptx")
    p_rt.add_argument("pptx")
    p_rt.add_argument("--map", required=True, help="JSON edit map")
    p_rt.add_argument("--out", required=True, help="output pptx")
    p_rt.set_defaults(func=cmd_retext)
    p_pt = sub.add_parser("patch", help="revise DSL nodes and re-run lint")
    p_pt.add_argument("deck")
    p_pt.add_argument("--set", action="append", default=[],
                      help="path=value (repeatable), e.g. slides.0.data.title=新标题")
    p_pt.add_argument("--out", help="write the patched DSL here")
    p_pt.add_argument("--build", help="also rebuild a pptx at this path")
    p_pt.add_argument("--force", action="store_true")
    p_pt.set_defaults(func=cmd_patch)
    p_sg = sub.add_parser(
        "svgguard", help="FreePPT guard over SVG (contrast/capacity/density/fact)")
    p_sg.add_argument("plan", help="coordinate-free Deck Plan (plan.json)")
    p_sg.add_argument("svg_dir", help="folder of page SVGs")
    p_sg.set_defaults(func=cmd_svgguard)
    p_ld = sub.add_parser(
        "ledger", help="validate a layout ledger (unique/no-repeat hard gate)")
    p_ld.add_argument("ledger", help="layout_ledger.json")
    p_ld.set_defaults(func=cmd_ledger)
    p_cs2 = sub.add_parser(
        "compile-svg", help="quality-check then compile an SVG project to pptx")
    p_cs2.add_argument("project", help="SVG project directory (has svg_output/)")
    p_cs2.add_argument("out", help="output .pptx path")
    p_cs2.add_argument("--strict", action="store_true",
                       help="use ppt-master canonical/final hard gate")
    p_cs2.add_argument("--skip-quality", action="store_true",
                       help="compile without running the quality checker")
    p_cs2.set_defaults(func=cmd_compile_svg)
    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
