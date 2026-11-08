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


def cmd_compose(args):
    """Stage 1-2: notes + reference cover -> per-page composed DSL."""
    from engine import art_direction
    notes_path = os.path.abspath(args.notes)
    notes = load(notes_path)
    try:
        deck, ledger = art_direction.compose(
            notes, os.path.dirname(notes_path), args.cover, args.base, args.seed)
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
    print(f"composed: {out} ({len(deck['slides'])} pages, "
          f"{deck['art_direction']['distinct']} distinct archetypes)")
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
    p_build = sub.add_parser("build")
    p_build.add_argument("deck")
    p_build.add_argument("out")
    p_build.add_argument("--force", action="store_true")
    p_build.set_defaults(func=cmd_build)
    p_cp = sub.add_parser("compose", help="creative page-by-page composition")
    p_cp.add_argument("notes", help="notes JSON (book + pages)")
    p_cp.add_argument("--cover", help="reference cover image (overrides notes)")
    p_cp.add_argument("--base", default="magazine")
    p_cp.add_argument("--seed", help="override the deterministic seed")
    p_cp.add_argument("--out", help="output composed deck DSL")
    p_cp.add_argument("--ledger", help="output style provenance ledger")
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
    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
