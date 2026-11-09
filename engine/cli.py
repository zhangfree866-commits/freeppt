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
    try:
        deck, ledger = art_direction.compose(
            notes, os.path.dirname(notes_path), args.cover, args.base, args.seed,
            card_system=getattr(args, "card_system", False),
            scoring=getattr(args, "scoring", False))
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
        pptmaster_bridge._run_script(checker, qargv)
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
    p_mk = sub.add_parser("make", help="plain text -> PPTX, no LLM and no network")
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
