#!/usr/bin/env python3
"""Reproducible self-benchmark for FreePPT.

Measures ONLY this repository. It does not fabricate competitor numbers;
see docs/BENCHMARK.md for the cross-project comparison template and method.

Metrics per deck:
  layout_errors   - lint hard errors
  overflow_rate   - (TEXT_OVERFLOW + RICHCARD_OVERFLOW) / text nodes
  editable_ratio  - native editable shapes / all shapes in the built pptx
  lint_seconds / build_seconds
Repo-wide:
  offline_readiness - static scan of engine/ for network client usage
"""

import argparse
import glob
import json
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import cli  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE_TYPE  # noqa: E402

SKIP_NAMES = ("web_manifest.json",)
SKIP_PREFIX = ("notes_", "style_", "structure_", "edits_")
OVERFLOW_CODES = {"TEXT_OVERFLOW", "RICHCARD_OVERFLOW"}
NETWORK_RE = re.compile(
    r"urlopen|requests\.(get|post)|httpx|aiohttp|socket\.create_connection|"
    r"urllib\.request\.Request")


def deck_files():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "examples", "*.json"))):
        b = os.path.basename(p)
        if b in SKIP_NAMES or b.startswith(SKIP_PREFIX):
            continue
        out.append(p)
    return out


def count_text_nodes(slide):
    n = 0
    stack = [slide.get("_root", {})]
    while stack:
        node = stack.pop()
        if node.get("t") == "text":
            n += 1
        stack.extend(node.get("children", []))
    return n


def shape_stats(path):
    prs = Presentation(path)
    total = text = pictures = charts = 0
    for s in prs.slides:
        for sh in s.shapes:
            total += 1
            if sh.has_text_frame and sh.text.strip():
                text += 1
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                pictures += 1
            if getattr(sh, "has_chart", False):
                charts += 1
    editable = total - pictures
    return {"slides": len(prs.slides), "shapes": total,
            "text_shapes": text, "picture_shapes": pictures,
            "chart_shapes": charts,
            "editable_shapes": editable,
            "editable_ratio": round(editable / total, 4) if total else 0.0}


def offline_readiness():
    """Static scan, NOT a runtime proof of offline behaviour."""
    hits = []
    for p in sorted(glob.glob(os.path.join(ROOT, "engine", "*.py"))):
        with open(p, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if NETWORK_RE.search(line):
                    hits.append({"file": os.path.basename(p), "line": i,
                                 "code": line.strip()[:120]})
    with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as f:
        deps = [l.strip() for l in f
                if l.strip() and not l.strip().startswith("#")]
    optional = ("web_images.py", "web_search.py")
    core_hits = [h for h in hits if h["file"] not in optional]
    return {
        "runtime_dependencies": deps,
        "engine_network_call_hits": len(hits),
        "core_pipeline_network_hits": len(core_hits),
        "optional_web_image_channel_files": sorted(
            {h["file"] for h in hits if h["file"] in optional}),
        "hits": hits,
        "method": "static regex scan of engine/*.py; not a network trace",
        "note": ("Network calls live only in the opt-in web-image search "
                 "channel. The five-stage core (DSL/layout/lint/compiler) "
                 "and the default vector/licensed-image path make none."),
    }


def run_one(path):
    t0 = time.perf_counter()
    spec = cli.load(path)
    deck = cli.prepare(spec)
    from engine.lint import lint_deck
    result = lint_deck(deck)
    t1 = time.perf_counter()
    nodes = sum(count_text_nodes(s) for s in deck["slides"])
    overflow = sum(1 for e in result["errors"] if e["code"] in OVERFLOW_CODES)
    with tempfile.TemporaryDirectory() as td:
        pptx = os.path.join(td, "bench.pptx")
        t2 = time.perf_counter()
        from engine.compiler import build_pptx
        build_pptx(deck, pptx)
        t3 = time.perf_counter()
        stats = shape_stats(pptx)
    return {
        "deck": os.path.basename(path),
        "slides": len(deck["slides"]),
        "text_nodes": nodes,
        "layout_errors": len(result["errors"]),
        "layout_warnings": len(result["warnings"]),
        "error_codes": sorted({e["code"] for e in result["errors"]}),
        "overflow_errors": overflow,
        "overflow_rate": round(overflow / nodes, 4) if nodes else 0.0,
        "lint_seconds": round(t1 - t0, 4),
        "build_seconds": round(t3 - t2, 4),
        **stats,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write JSON report here")
    ap.add_argument("--decks", nargs="*", help="override the deck list")
    args = ap.parse_args()
    paths = args.decks or deck_files()
    rows = [run_one(p) for p in paths]
    report = {
        "tool": "FreePPT self-benchmark",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "python": sys.version.split()[0],
        "scope": "this repository only; no competitor data",
        "decks": rows,
        "summary": {
            "deck_count": len(rows),
            "total_layout_errors": sum(r["layout_errors"] for r in rows),
            "mean_editable_ratio": round(
                sum(r["editable_ratio"] for r in rows) / len(rows), 4) if rows else 0,
            "mean_lint_seconds": round(
                sum(r["lint_seconds"] for r in rows) / len(rows), 4) if rows else 0,
            "mean_build_seconds": round(
                sum(r["build_seconds"] for r in rows) / len(rows), 4) if rows else 0,
        },
        "offline": offline_readiness(),
        "limitations": [
            "editable_ratio counts native shapes; it does not judge visual quality",
            "overflow_rate is derived from lint diagnostics, not from pixels",
            "offline readiness is a static scan, not a runtime network trace",
            "no competitor was executed; cross-project numbers must be measured separately",
        ],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"benchmark: {args.out} | decks={len(rows)} | "
              f"layout_errors={report['summary']['total_layout_errors']} | "
              f"mean_editable_ratio={report['summary']['mean_editable_ratio']}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
