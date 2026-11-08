"""Tests for the inspect report's picture/shape-kind summary (lesson #91 guard).

The PNG preview and the OOXML compiler are two independent drawing paths and
once diverged silently (a rect rendered as rectangle in PIL but compiled to an
oval). ``inspect`` now aggregates real pptx shape kinds and a PICTURE total so
the hand-built loop can cross-check the actual file instead of trusting the
preview. These tests pin the new fields while keeping the legacy report shape.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import layout, compiler  # noqa: E402
from engine.pptx_edit import inspect  # noqa: E402

NAVY = "#061F32"
ORANGE = "#F47B39"


def _build(children):
    deck = {"theme": "consulting", "composed": False, "slides": [{
        "type": "content", "composition": "freeform", "tone": "light",
        "children": children}]}
    layout.layout_deck(deck)
    path = tempfile.mktemp(suffix=".pptx")
    compiler.build_pptx(deck, path, force=True)
    return path


class TestInspectShapeSummary(unittest.TestCase):
    def setUp(self):
        self.path = _build([
            {"t": "shape", "kind": "rect", "rect": [200, 200, 300, 160],
             "fill": NAVY},
            {"t": "shape", "kind": "oval", "rect": [600, 220, 80, 80],
             "fill": ORANGE},
            {"t": "line", "p1": [200, 420], "p2": [500, 420],
             "color": ORANGE, "thickness": 3},
        ])
        self.report = inspect(self.path)

    def test_top_level_picture_count_and_totals(self):
        self.assertEqual(self.report["picture_count"], 0)
        totals = self.report["shape_kind_totals"]
        self.assertIn("RECTANGLE (1)", totals)   # authored rect + background
        self.assertIn("OVAL (9)", totals)
        self.assertIn("LINE connector", totals)
        self.assertGreaterEqual(totals["RECTANGLE (1)"], 1)
        self.assertGreaterEqual(totals["OVAL (9)"], 1)
        self.assertGreaterEqual(totals["LINE connector"], 1)

    def test_per_slide_summary_present(self):
        slide = self.report["slides"][0]
        self.assertEqual(slide["picture_count"], 0)
        # single-slide deck: per-slide kinds equal the top-level totals
        self.assertEqual(slide["shape_kinds"],
                         self.report["shape_kind_totals"])
        self.assertIn("OVAL (9)", slide["shape_kinds"])

    def test_legacy_fields_remain(self):
        # backwards compatibility: original report contract is untouched
        self.assertEqual(self.report["slide_count"], 1)
        self.assertEqual(len(self.report["canvas_px"]), 2)
        self.assertGreater(self.report["slides"][0]["shape_count"], 0)
        self.assertIn("shapes", self.report["slides"][0])
        self.assertTrue(
            all("type" in s for s in self.report["slides"][0]["shapes"]))


if __name__ == "__main__":
    unittest.main()
