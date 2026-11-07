"""Read and minimally edit an EXISTING .pptx while preserving its formatting.

Scope is deliberately narrow and honest:
- `inspect()` reports structure (slides, shapes, text, coordinates).
- `retext()` replaces text in existing text frames by editing the first run,
  keeping that run's font/paragraph formatting. It does NOT reflow, resize,
  restyle, or reconstruct the deck.
- It does not parse an existing pptx back into FreePPT's DSL. That round-trip
  is not implemented; see references/edit-existing.md.

This module is the "edit an existing pptx" capability's first, verifiable step.
"""

import os

from pptx import Presentation

EMU_PER_PX = 9525  # 96 dpi; python-pptx stores EMU


def _px(v):
    return round(v / EMU_PER_PX, 1) if v is not None else None


def inspect(path):
    """Return a JSON-serialisable structural report of a .pptx file."""
    prs = Presentation(path)
    slides = []
    for i, slide in enumerate(prs.slides):
        shapes = []
        for sh in slide.shapes:
            item = {
                "id": sh.shape_id,
                "name": sh.name,
                "type": str(sh.shape_type),
                "rect_px": [_px(sh.left), _px(sh.top),
                            _px(sh.width), _px(sh.height)],
                "has_text_frame": bool(sh.has_text_frame),
            }
            if sh.has_text_frame:
                item["text"] = sh.text
                item["runs"] = [
                    {"text": r.text,
                     "size_pt": r.font.size.pt if r.font.size else None,
                     "bold": r.font.bold,
                     "name": r.font.name}
                    for p in sh.text_frame.paragraphs for r in p.runs
                ]
            shapes.append(item)
        slides.append({"slide": i + 1, "shape_count": len(shapes),
                       "shapes": shapes})
    return {
        "source": os.path.abspath(path),
        "slide_count": len(prs.slides),
        "canvas_px": [_px(prs.slide_width), _px(prs.slide_height)],
        "slides": slides,
        "note": "Text replacement keeps the first run's formatting; no DSL round-trip.",
    }


def _find_shape(slide, edit):
    shapes = list(slide.shapes)
    if edit.get("shape_id") is not None:
        for sh in shapes:
            if sh.shape_id == int(edit["shape_id"]):
                return sh
        return None
    if edit.get("shape"):
        for sh in shapes:
            if sh.name == edit["shape"]:
                return sh
        return None
    if edit.get("match"):
        for sh in shapes:
            if sh.has_text_frame and edit["match"] in sh.text:
                return sh
        return None
    return None


def retext(src, edits, out):
    """Replace text in existing shapes; returns a report dict.

    Each edit: {"slide": 1-based, "shape"|"shape_id"|"match": locator,
                "text": replacement}. Everything else in the pptx is untouched.
    """
    prs = Presentation(src)
    applied, missed = [], []
    for n, e in enumerate(edits):
        idx = int(e.get("slide", 0)) - 1
        if not (0 <= idx < len(prs.slides)):
            missed.append({"edit": n, "reason": "slide out of range", "detail": e})
            continue
        sh = _find_shape(prs.slides[idx], e)
        if sh is None:
            missed.append({"edit": n, "reason": "shape not found", "detail": e})
            continue
        if not sh.has_text_frame:
            missed.append({"edit": n, "reason": "shape has no text frame",
                           "detail": e})
            continue
        new_text = str(e.get("text", ""))
        runs = [r for p in sh.text_frame.paragraphs for r in p.runs]
        if runs:
            # Keep the original run's font; additional runs are emptied.
            runs[0].text = new_text
            for r in runs[1:]:
                r.text = ""
        else:
            sh.text_frame.paragraphs[0].add_run().text = new_text
        # Emptying runs can leave empty paragraphs behind; shape.text would
        # then report a trailing newline that was never in the replacement.
        tf = sh.text_frame
        for p in list(tf.paragraphs)[1:]:
            if not p.text.strip():
                p._element.getparent().remove(p._element)
        applied.append({"edit": n, "slide": idx + 1, "shape": sh.name,
                        "shape_id": sh.shape_id, "new_length": len(new_text)})
    prs.save(out)
    return {
        "source": os.path.abspath(src),
        "output": os.path.abspath(out),
        "requested": len(edits),
        "applied": len(applied),
        "missed": missed,
        "items": applied,
        "warning": ("Longer replacement text may overflow its original box; "
                    "FreePPT does not reflow existing pptx shapes."),
    }
