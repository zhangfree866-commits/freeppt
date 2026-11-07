#!/usr/bin/env python3
"""Keyword search over Wikimedia Commons -> auditable web-image manifest.

This module is the *discovery* half of the web-image channel. It is deliberately
split so the Wikimedia API schema is parsed in one pure function that never
touches the network:

    build_query_url()  -> request URL (pure)
    commons_request()  -> raw JSON dict over HTTP (only networked function)
    parse_search_response() -> normalized candidates (pure, unit-tested offline)
    search()           -> glues the three together
    to_manifest_items()/write_manifest() -> web_images.py-compatible manifest

Nothing here downloads binaries. Pick candidates, emit a manifest, then run
`python3 engine/web_images.py <manifest>` to fetch + validate + ledger them.
Sandboxes without access to commons.wikimedia.org can still exercise every
parsing rule via tests/test_web_search.py against a recorded API fixture.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "FreePPT/1.0 (+research; contact local)"}

# Licenses that need no per-use negotiation for an internal deck. CC BY/SA/NC
# and CC0/public-domain all keep attribution; the deck footer carries credit.
PERMISSIVE_HINTS = ("cc0", "cc by", "public domain", "pd-", "attribution",
                    "free art", "w3c")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


# ---- pure helpers -----------------------------------------------------------
def clean_html(value):
    """Turn an extmetadata HTML blob into plain attribution text."""
    if not value:
        return ""
    text = _TAG_RE.sub("", value)          # strip tags
    text = text.replace("&nbsp;", " ")
    text = urllib.parse.unquote(text)      # percent-encoding, if any
    import html as _html
    text = _html.unescape(text)            # &amp; &#039; &quot; ...
    return _WS_RE.sub(" ", text).strip()


def is_permissive(license_name):
    low = (license_name or "").lower()
    return any(h in low for h in PERMISSIVE_HINTS)


def build_query_url(keyword, limit=8, width=1280):
    """Construct a generator=search image query URL (no request made)."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{keyword} filetype:bitmap",
        "gsrnamespace": "6",          # File: namespace only
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": str(width),     # ask Commons to render a thumb this wide
    }
    return API + "?" + urllib.parse.urlencode(params)


def _meta(info, key):
    return (info.get("extmetadata") or {}).get(key, {}).get("value", "")


def parse_search_response(payload):
    """Normalize a raw Commons API response into flat candidate dicts.

    Pure function: same JSON in -> same candidates out, no I/O. Defensive
    against missing pages / missing imageinfo / missing metadata so one odd
    record never breaks a whole result set.
    """
    pages = ((payload or {}).get("query") or {}).get("pages") or {}
    out = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        title = page.get("title", "")
        license_name = clean_html(_meta(info, "LicenseShortName"))
        desc_url = info.get("descriptionurl") or _page_url(title)
        out.append({
            "title": clean_html(_meta(info, "ImageDescription")) or
                     _strip_file_ns(title),
            "file_title": title,
            "author": clean_html(_meta(info, "Artist")),
            "license": license_name,
            "license_url": _meta(info, "LicenseUrl"),
            "permissive": is_permissive(license_name),
            # Prefer the sized thumb (deck-friendly bytes); fall back to original.
            "url": info.get("thumburl") or info.get("url", ""),
            "width": info.get("thumbwidth") or info.get("width"),
            "height": info.get("thumbheight") or info.get("height"),
            "source_page": desc_url,
        })
    # generator=search relevance order lives in `index`; honor it when present.
    out.sort(key=lambda c: pages.get(_find_pageid(pages, c["file_title"]),
                                     {}).get("index", 9999))
    return out


def _find_pageid(pages, file_title):
    for pid, page in pages.items():
        if page.get("title") == file_title:
            return pid
    return None


def _strip_file_ns(title):
    return title.split(":", 1)[1] if title.startswith("File:") else title


def _page_url(title):
    return ("https://commons.wikimedia.org/wiki/" +
            urllib.parse.quote(title.replace(" ", "_")))


def safe_name(url, fallback_index):
    """Derive a local asset filename from a Commons/thumb URL."""
    path = urllib.parse.urlparse(url).path
    base = os.path.basename(urllib.parse.unquote(path))
    # Thumb URLs look like /thumb/..//1280px-Real Name.jpg -> drop thumb prefix
    base = re.sub(r"^\d+px-", "", base)
    base = re.sub(r"[^a-z0-9._-]", "",
                  base.replace(" ", "_").lower())
    base = re.sub(r"_{2,}", "_", base).strip("._-")  # collapse separators
    if not base or "." not in base or base.startswith("."):
        base = f"web-{fallback_index}.jpg"
    if not base.startswith("web-"):
        base = "web-" + base
    return base


def to_manifest_items(candidates, used_names=None):
    """Map normalized candidates to web_images.py manifest item schema."""
    used = set(used_names or [])
    items = []
    for i, c in enumerate(candidates, 1):
        if not c["url"]:
            continue
        name = safe_name(c["url"], i)
        stem, ext = os.path.splitext(name)
        n = 2
        while name in used:
            name = f"{stem}-{n}{ext}"
            n += 1
        used.add(name)
        items.append({
            "name": name,
            "url": c["url"],
            "title": c["title"],
            "author": c["author"],
            "license": c["license"],
            "source_page": c["source_page"],
        })
    return items


# ---- network layer (the only function that touches the network) -------------
def commons_request(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def search(keyword, limit=8, width=1280, permissive_only=False, fetcher=None):
    """Search Commons and return normalized candidates.

    `fetcher` is injectable so tests/offline runs can substitute a recorded
    response without monkeypatching urllib.
    """
    url = build_query_url(keyword, limit=limit, width=width)
    fetcher = fetcher or commons_request
    payload = fetcher(url)
    candidates = parse_search_response(payload)
    if permissive_only:
        candidates = [c for c in candidates if c["permissive"]]
    return candidates


def write_manifest(candidates, out_dir, manifest_path):
    manifest = {"out_dir": out_dir,
                "items": to_manifest_items(candidates)}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


# ---- CLI --------------------------------------------------------------------
def _print_candidates(candidates):
    if not candidates:
        print("(no candidates)")
        return
    for i, c in enumerate(candidates, 1):
        flag = "" if c["permissive"] else "  [non-permissive]"
        size = f'{c.get("width") or "?"}x{c.get("height") or "?"}'
        author = c["author"] or "unknown"
        print(f'{i:2d}. {c["title"][:70]}')
        print(f'    {c["license"] or "?"} | {author} | {size}{flag}')
        print(f'    {c["url"]}')
        print(f'    src: {c["source_page"]}')


def main(argv=None):
    ap = argparse.ArgumentParser(description="Wikimedia Commons keyword search")
    ap.add_argument("keyword", help="search terms, e.g. 'wind energy'")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--width", type=int, default=1280,
                    help="preferred thumbnail width in px")
    ap.add_argument("--permissive", action="store_true",
                    help="keep only CC/CC0/public-domain licenses")
    ap.add_argument("--manifest", help="write a web_images.py manifest here")
    ap.add_argument("--out-dir", default="examples/assets",
                    help="out_dir recorded in the manifest")
    ap.add_argument("--fixture",
                    help="offline mode: parse a recorded API JSON instead of HTTP")
    args = ap.parse_args(argv)

    if args.fixture:
        with open(args.fixture, encoding="utf-8") as f:
            payload = json.load(f)
        candidates = parse_search_response(payload)
        if args.permissive:
            candidates = [c for c in candidates if c["permissive"]]
    else:
        try:
            candidates = search(args.keyword, limit=args.limit,
                                width=args.width,
                                permissive_only=args.permissive)
        except Exception as e:  # network blocked in sandbox
            print(f"[network unavailable] {e}", file=sys.stderr)
            print("hint: re-run with --fixture tests/fixtures/"
                  "commons_search_sample.json for offline parsing, or run in an "
                  "environment that can reach commons.wikimedia.org.",
                  file=sys.stderr)
            return 2

    _print_candidates(candidates)
    if args.manifest:
        manifest = write_manifest(candidates, args.out_dir, args.manifest)
        print(f"\nwrote {len(manifest['items'])} items -> {args.manifest}")
        print("next: python3 engine/web_images.py", args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
