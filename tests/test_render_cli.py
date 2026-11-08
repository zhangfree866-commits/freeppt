"""Tests for the `render` CLI (deck DSL -> PNG contact sheets).

cmd_render is the visual-readback half of the hand-built freeform loop, so the
contract pinned here is: a valid deck writes one PNG per slide into the target
folder and always returns 0 (lint diagnostics are surfaced but never block PNG
output, since rendering mid-fix is a core use case).
"""

import json
import os
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.cli import cmd_render  # noqa: E402

NAVY = "#061F32"
WHITE = "#FFFFFF"


def _write_deck(slides):
    deck = {"theme": "consulting", "composed": False, "slides": slides}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(deck, f, ensure_ascii=False)
    return path


def _freeform_slide(children, tone="light"):
    return {"type": "content", "composition": "freeform", "tone": tone,
            "children": children}


def _surface(rect, fill=NAVY):
    return {"t": "shape", "kind": "rect", "rect": list(rect), "fill": fill}


class TestRenderCli(unittest.TestCase):
    def test_renders_one_png_per_slide(self):
        deck_path = _write_deck([
            _freeform_slide([_surface([200, 200, 300, 200])]),
            _freeform_slide([_surface([120, 120, 200, 160])], tone="dark"),
        ])
        out_dir = tempfile.mkdtemp()
        rc = cmd_render(types.SimpleNamespace(deck=deck_path, out_dir=out_dir))
        self.assertEqual(rc, 0)
        pngs = sorted(f for f in os.listdir(out_dir) if f.endswith(".png"))
        self.assertEqual(pngs, ["slide01.png", "slide02.png"])
        for name in pngs:
            self.assertGreater(os.path.getsize(os.path.join(out_dir, name)), 0)

    def test_renders_even_when_lint_has_diagnostics(self):
        # shape past the canvas edge is a lint error, but readback must still
        # emit a PNG so the hand-built loop can debug geometry visually.
        deck_path = _write_deck([
            _freeform_slide([_surface([1100, 200, 400, 200])]),
        ])
        out_dir = tempfile.mkdtemp()
        rc = cmd_render(types.SimpleNamespace(deck=deck_path, out_dir=out_dir))
        self.assertEqual(rc, 0)
        self.assertTrue(
            os.path.exists(os.path.join(out_dir, "slide01.png")))


if __name__ == "__main__":
    unittest.main()
