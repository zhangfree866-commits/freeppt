#!/usr/bin/env python3
"""LibreOffice-based render regression for a built .pptx.

Converts pptx -> PDF -> PNG and verifies:
  - PDF page count equals the pptx slide count
  - every page produces a non-trivial PNG (not a blank render)
  - extracted PDF text is non-empty (text was actually rasterised as text)

If LibreOffice/poppler is absent the tool reports status="skipped" and exits 0.
CI installs both and asserts status == "ok", so a skipped local run is never
mistaken for a passing render regression.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

MAC_SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def find_soffice():
    p = shutil.which("soffice") or shutil.which("libreoffice")
    if p:
        return p
    return MAC_SOFFICE if os.path.exists(MAC_SOFFICE) else None


def pdf_pages(pdf, pdfinfo, pdftotext):
    if pdfinfo:
        out = subprocess.run([pdfinfo, pdf], capture_output=True,
                             text=True, check=True).stdout
        for line in out.splitlines():
            if line.lower().startswith("pages:"):
                return int(line.split(":", 1)[1].strip())
    if pdftotext:
        out = subprocess.run([pdftotext, pdf, "-"], capture_output=True,
                             text=True, check=True).stdout
        return len([p for p in out.split("\f") if p.strip()])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("--out", help="JSON report path")
    ap.add_argument("--png-dir", help="directory to keep rendered page PNGs")
    args = ap.parse_args()

    from pptx import Presentation
    expected = len(Presentation(args.pptx).slides)
    soffice = find_soffice()
    pdftoppm = shutil.which("pdftoppm")
    pdfinfo = shutil.which("pdfinfo")
    pdftotext = shutil.which("pdftotext")

    report = {
        "tool": "FreePPT render regression",
        "pptx": os.path.abspath(args.pptx),
        "expected_slides": expected,
        "soffice": soffice,
        "pdftoppm": pdftoppm,
        "status": "skipped",
    }
    if not (soffice and pdftoppm):
        report["reason"] = "LibreOffice (soffice) or pdftoppm not installed"
        report["note"] = ("Local run is a SKIP, not a pass. CI installs "
                          "libreoffice-impress + poppler-utils and asserts ok.")
        _emit(report, args.out)
        return 0

    with tempfile.TemporaryDirectory() as td:
        conv = subprocess.run(
            [soffice, "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", td, os.path.abspath(args.pptx)],
            capture_output=True, text=True, timeout=180)
        pdfs = glob.glob(os.path.join(td, "*.pdf"))
        if conv.returncode != 0 or not pdfs:
            report.update(status="failed", reason="PDF conversion failed",
                          stderr=conv.stderr[-800:], stdout=conv.stdout[-400:])
            _emit(report, args.out)
            return 1
        pdf = pdfs[0]
        pages = pdf_pages(pdf, pdfinfo, pdftotext)
        report["pdf_pages"] = pages

        outdir = args.png_dir or os.path.join(td, "png")
        os.makedirs(outdir, exist_ok=True)
        r = subprocess.run([pdftoppm, "-png", "-r", "72", pdf,
                            os.path.join(outdir, "page")],
                           capture_output=True, text=True, timeout=180)
        pngs = sorted(glob.glob(os.path.join(outdir, "*.png")))
        sizes = [os.path.getsize(p) for p in pngs]
        report["png_files"] = [os.path.abspath(p) for p in pngs]
        report["png_bytes"] = sizes
        report["pdftoppm_returncode"] = r.returncode

        text_len = 0
        if pdftotext:
            txt = subprocess.run([pdftotext, pdf, "-"], capture_output=True,
                                 text=True).stdout
            text_len = len(txt.strip())
        report["pdf_text_chars"] = text_len

        problems = []
        if pages is not None and pages != expected:
            problems.append(f"PDF has {pages} pages, pptx has {expected} slides")
        if len(pngs) != expected:
            problems.append(f"rendered {len(pngs)} PNGs for {expected} slides")
        if any(sz < 1000 for sz in sizes):
            problems.append("one or more rendered pages look blank (<1000 bytes)")
        if text_len == 0:
            problems.append("no text extracted from PDF")
        if r.returncode != 0:
            problems.append("pdftoppm returned non-zero")
        report["problems"] = problems
        report["status"] = "ok" if not problems else "failed"

    _emit(report, args.out)
    return 0 if report["status"] == "ok" else 1


def _emit(report, out):
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"render_check: {out} | status={report['status']}")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
