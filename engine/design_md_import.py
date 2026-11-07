#!/usr/bin/env python3
"""Deterministic importer for DESIGN.md frontmatter design tokens.

This module only extracts values that literally exist in the source file. It
never guesses semantic roles: callers must supply an explicit ``role -> token
key`` mapping, and a missing key raises instead of silently falling back.

DESIGN.md is the Stitch-style plain-text design system document curated by
VoltAgent/awesome-design-md (MIT). FreePPT borrows publicly visible numeric
tokens only; the parser, the role mapping and the theme definitions are this
project's own work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_TOP = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")
_SUB = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*(.*)$")
_LEAF = re.compile(r"^    ([A-Za-z][A-Za-z0-9_.-]*):\s*(.*)$")
_SECTIONS = {"colors", "rounded", "spacing", "typography"}


def _frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return []


def _scalar(value):
    value = value.strip().strip('"').strip()
    if re.fullmatch(r"[0-9.]+px", value):
        return float(value[:-2])
    if re.fullmatch(r"[0-9.]+", value):
        return float(value)
    return value


def parse_design_md(path):
    """Return tokens literally present in one DESIGN.md file."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    meta, colors, rounded, spacing, typography = {}, {}, {}, {}, {}
    section, role = None, None
    for line in _frontmatter(text):
        m = _TOP.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            section, role = key, None
            if val:
                meta[key] = val.strip('"')
            continue
        m = _SUB.match(line)
        if m and section in _SECTIONS:
            key, val = m.group(1), m.group(2).strip()
            if section == "typography":
                role = key
                typography[role] = {}
            elif section == "colors":
                hx = _HEX.search(val)
                if hx:
                    colors[key] = hx.group(0).upper()
            else:
                px = re.match(r"([0-9.]+)\s*px", val.strip().strip('"'))
                if px:
                    (rounded if section == "rounded" else spacing)[key] = float(px.group(1))
            continue
        m = _LEAF.match(line)
        if m and section == "typography" and role:
            typography[role][m.group(1)] = _scalar(m.group(2))
    # keep only the type metrics FreePPT can consume
    slim_type = {}
    for role, props in typography.items():
        slim_type[role] = {k: v for k, v in props.items()
                           if k in ("fontFamily", "fontSize", "lineHeight",
                                    "fontWeight", "letterSpacing")}
    return {
        "name": os.path.splitext(os.path.basename(path))[0],
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "meta": {k: v for k, v in meta.items() if k != "description"},
        "colors": colors,
        "rounded": rounded,
        "spacing": spacing,
        "typography": slim_type,
    }


def semantic_from_mapping(colors, mapping):
    """Map FreePPT semantic roles to source token keys; fail loudly on gaps."""
    out = {}
    for role, key in mapping.items():
        if key not in colors:
            raise KeyError(
                f"token '{key}' for role '{role}' not present in source; "
                f"available keys: {sorted(colors)}")
        out[role] = colors[key]
    return out


def build_archive(paths, repo, branch="main", root="design-md"):
    files = {}
    for path in paths:
        parsed = parse_design_md(path)
        stem = parsed["name"]
        url = (f"https://raw.githubusercontent.com/{repo}/{branch}/"
               f"{root}/{stem}/DESIGN.md")
        parsed["url"] = url
        files[stem] = parsed
    return {
        "repository": repo,
        "license": "MIT",
        "branch": branch,
        "source_root": root,
        "files": files,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract DESIGN.md design tokens")
    ap.add_argument("files", nargs="+", help="DESIGN.md files")
    ap.add_argument("--repo", default="VoltAgent/awesome-design-md")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--root", default="design-md")
    ap.add_argument("--mapping", help="JSON file with role->token-key mapping")
    ap.add_argument("--source-key", help="which archive file the mapping applies to")
    ap.add_argument("--out", help="write archive/semantic JSON to this path")
    args = ap.parse_args(argv)

    archive = build_archive(args.files, args.repo, args.branch, args.root)

    if args.mapping:
        key = args.source_key or next(iter(archive["files"]))
        with open(args.mapping, encoding="utf-8") as fh:
            raw = json.load(fh)
        # accept either a flat role->key map or a per-source grouped map
        mapping = raw.get(key, raw)
        result = semantic_from_mapping(archive["files"][key]["colors"], mapping)
    else:
        result = archive

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        print(f"wrote {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
