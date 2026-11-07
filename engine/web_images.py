#!/usr/bin/env python3
"""Web-image channel: download licensed photos into assets with a source ledger.

Workflow
  1. Pick a theme, search a permissively-licensed source (Wikimedia Commons /
     Unsplash License / CC repos). Record the real page URL and license.
  2. Put entries in a manifest JSON:
       {"out_dir": "examples/assets",
        "items": [{"name":"earth.jpg","url":"https://...",
                   "title":"...","author":"...","license":"Unsplash License",
                   "source_page":"https://unsplash.com/photos/..."}]}
  3. Run: python3 engine/web_images.py manifest.json
  Files are validated as real images; sources.json is the attribution ledger.
The deck only ever references LOCAL files, and web-sourced images must carry a
credit (lint rule WEB_CREDIT), so licensing stays auditable.
"""

import json
import os
import subprocess
import sys
import urllib.request

from PIL import Image

UA = {"User-Agent": "FreePPT/1.0 (+research; contact local)"}


def fetch(url, dest):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except Exception:
        # sandbox fallback: curl
        subprocess.run(["curl", "-sL", "--max-time", "40", "-o", dest, url],
                       check=True)
        data = open(dest, "rb").read()
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def run(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    out_dir = manifest["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    ledger_path = os.path.join(out_dir, "sources.json")
    ledger = json.load(open(ledger_path, encoding="utf-8")) \
        if os.path.exists(ledger_path) else {"images": []}
    known = {e["file"] for e in ledger["images"]}

    for it in manifest["items"]:
        dest = os.path.join(out_dir, it["name"])
        fetch(it["url"], dest)
        # hard validation: must open as an image
        with Image.open(dest) as im:
            im.verify()
        with Image.open(dest) as im:
            w, h = im.size
        if it["name"] not in known:
            ledger["images"].append({
                "file": it["name"], "title": it.get("title", ""),
                "author": it.get("author", ""),
                "license": it.get("license", ""),
                "source_page": it.get("source_page", ""),
                "download_url": it["url"], "width": w, "height": h,
            })
        print(f"ok {it['name']} {w}x{h} [{it.get('license','')}]")

    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
    print("ledger:", ledger_path)


if __name__ == "__main__":
    run(sys.argv[1])
