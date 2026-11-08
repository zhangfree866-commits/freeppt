"""Tests for freeform geometric-integrity lint (warning-level QA pass).

These mirror the manual checks a designer runs on hand-drawn freeform slides:
near-touch/tangent seams, non-nested overlaps, out-of-range line weights, and
single-line labels sitting at the wrap threshold. Every diagnostic is a
warning, so a well-formed deck stays buildable (ok stays True) and the legacy
181-test baseline is untouched. Master-template decks never reach this code.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import layout, lint  # noqa: E402
from engine.layout import char_w  # noqa: E402

NAVY = "#061F32"
WHITE = "#FFFFFF"
ORANGE = "#F47B39"
LINE_C = "#E5E7EB"


def surface(rect, fill=WHITE, kind="rect"):
    """A freeform shape leaf: leaves keep their explicit rect (no hug)."""
    return {"t": "shape", "kind": kind, "rect": rect, "fill": fill}


def lint_children(children, theme="consulting"):
    deck = {"theme": theme, "composed": False, "slides": [{
        "type": "content", "composition": "freeform", "tone": "light",
        "children": children}]}
    layout.layout_deck(deck)
    return lint.lint_deck(deck)


def warn_codes(res):
    return {w["code"] for w in res["warnings"]}


class TestNearTouchAndOverlap(unittest.TestCase):
    def test_vertical_gap_under_threshold_is_near_touch(self):
        # x ranges coincide; A bottom=300, B top=304 -> 4px vertical seam
        res = lint_children([
            surface([100, 100, 300, 200]),
            surface([100, 304, 300, 200], fill=NAVY),
        ])
        self.assertIn("GEOMETRY_NEAR_TOUCH", warn_codes(res))
        self.assertTrue(res["ok"])  # warning never blocks

    def test_horizontal_gap_under_threshold_is_near_touch(self):
        # y ranges coincide; A right=300, B left=305 -> 5px horizontal seam
        res = lint_children([
            surface([100, 100, 200, 200]),
            surface([305, 100, 200, 200], fill=NAVY),
        ])
        self.assertIn("GEOMETRY_NEAR_TOUCH", warn_codes(res))

    def test_two_four_gap_spacing_is_clean(self):
        # canonical 24px gutter: no collision signal at all
        res = lint_children([
            surface([100, 100, 300, 200]),
            surface([100, 324, 300, 200], fill=NAVY),
        ])
        self.assertNotIn("GEOMETRY_NEAR_TOUCH", warn_codes(res))
        self.assertNotIn("GEOMETRY_OVERLAP", warn_codes(res))

    def test_intersecting_sibling_surfaces_are_overlap(self):
        res = lint_children([
            surface([100, 100, 300, 200]),
            surface([100, 250, 300, 200], fill=NAVY),  # top=250 < A bottom=300
        ])
        self.assertIn("GEOMETRY_OVERLAP", warn_codes(res))

    def test_nested_parent_child_surfaces_are_not_flagged(self):
        parent = surface([100, 100, 600, 400])
        parent["children"] = [surface([24, 24, 200, 120], fill=NAVY)]
        res = lint_children([parent])
        self.assertNotIn("GEOMETRY_OVERLAP", warn_codes(res))
        self.assertNotIn("GEOMETRY_NEAR_TOUCH", warn_codes(res))

    def test_full_height_background_panels_are_exempt(self):
        # split-contrast: two edge-to-edge panels plus a 12px seam strip, all
        # full-height structural slabs — their intentional touch must be quiet
        res = lint_children([
            {"t": "box", "rect": [0, 0, 620, 720], "fill": "#3C1410",
             "children": []},
            {"t": "box", "rect": [620, 0, 660, 720], "fill": "#F8F4ED",
             "children": []},
            {"t": "box", "rect": [614, 0, 12, 720], "fill": "#AA4C44",
             "children": []},
        ])
        self.assertNotIn("GEOMETRY_OVERLAP", warn_codes(res))
        self.assertNotIn("GEOMETRY_NEAR_TOUCH", warn_codes(res))

    def test_decorative_and_bleed_nodes_are_exempt(self):
        deco = surface([100, 100, 400, 400])
        deco["decor"] = True
        bleed = surface([0, 0, 300, 300], fill=NAVY)
        bleed["bleed"] = True
        res = lint_children([deco, bleed])
        self.assertEqual(warn_codes(res), set())


class TestDataMarkerWhitelist(unittest.TestCase):
    def _bar(self, rect=(100, 300, 80, 260), fill=NAVY):
        return {"t": "shape", "kind": "rect", "rect": list(rect), "fill": fill}

    def test_data_marker_over_bar_is_quiet(self):
        # foreground line marker intentionally layered on top of a column
        marker = {"t": "shape", "kind": "oval",
                  "rect": [131, 420, 18, 18], "fill": WHITE, "border": ORANGE,
                  "role": "data-marker"}
        res = lint_children([self._bar(), marker])
        self.assertNotIn("GEOMETRY_OVERLAP", warn_codes(res))
        self.assertNotIn("GEOMETRY_NEAR_TOUCH", warn_codes(res))

    def test_same_overlay_without_role_still_warns(self):
        # identical geometry but no semantic role -> a real collision still
        # fires, proving the exemption is opt-in, not a blanket loosening
        bare = {"t": "shape", "kind": "oval",
                "rect": [131, 420, 18, 18], "fill": WHITE, "border": ORANGE}
        res = lint_children([self._bar(), bare])
        self.assertIn("GEOMETRY_OVERLAP", warn_codes(res))

    def test_data_label_pill_near_marker_is_quiet(self):
        # marker and its label pill sitting 2px apart (the Q6 case)
        marker = {"t": "shape", "kind": "oval", "rect": [200, 400, 18, 18],
                  "fill": WHITE, "border": ORANGE, "role": "data-marker"}
        pill = {"t": "shape", "kind": "roundrect", "rect": [167, 420, 84, 26],
                "fill": WHITE, "border": LINE_C, "role": "data-marker"}
        res = lint_children([self._bar(), marker, pill])
        self.assertNotIn("GEOMETRY_NEAR_TOUCH", warn_codes(res))

    def test_marker_still_bounds_checked(self):
        # opting out of collision checks must not opt out of canvas bounds
        marker = {"t": "shape", "kind": "oval",
                  "rect": [1250, 400, 80, 80], "fill": WHITE,
                  "role": "data-marker"}
        deck = {"theme": "consulting", "composed": False, "slides": [{
            "type": "content", "composition": "freeform", "tone": "light",
            "children": [marker]}]}
        layout.layout_deck(deck)
        res = lint.lint_deck(deck)
        self.assertIn("OUT_OF_CANVAS", {e["code"] for e in res["errors"]})


class TestLineWidth(unittest.TestCase):
    def _divider(self, **kw):
        node = {"t": "divider", "rect": [100, 100, 400, 1.5], "color": NAVY}
        node.update(kw)
        return node

    def test_thin_engine_weights_are_valid(self):
        res = lint_children([
            self._divider(),                              # default 1.25
            self._divider(thickness=1.5),
            self._divider(thickness=3),
        ])
        self.assertNotIn("LINE_WIDTH_VALUE", warn_codes(res))

    def test_non_numeric_and_out_of_range_thickness_warn(self):
        res = lint_children([
            self._divider(thickness="2pt"),               # non-numeric
            self._divider(thickness=0.2),                 # below floor
            self._divider(thickness=9),                   # above ceiling
            self._divider(thickness=True),                # bool rejected
        ])
        self.assertIn("LINE_WIDTH_VALUE", warn_codes(res))

    def test_default_thickness_absent_is_implicitly_valid(self):
        res = lint_children([self._divider()])
        self.assertNotIn("LINE_WIDTH_VALUE", warn_codes(res))

    def test_icon_stroke_weight_range(self):
        ok = lint_children([
            {"t": "icon", "name": "target", "rect": [100, 100, 64, 64],
             "color": NAVY, "stroke_w": 1.75},
        ])
        self.assertNotIn("LINE_WIDTH_VALUE", warn_codes(ok))
        bad = lint_children([
            {"t": "icon", "name": "target", "rect": [100, 100, 64, 64],
             "color": NAVY, "stroke_w": 12},
        ])
        self.assertIn("LINE_WIDTH_VALUE", warn_codes(bad))


class TestTightWidth(unittest.TestCase):
    def _text(self, text, width, size=20):
        return {"t": "text", "rect": [100, 100, width, 200], "text": text,
                "size": size}

    def test_single_line_filling_box_warns(self):
        text = "临界宽度的单行标题文字"
        glyph_w = sum(char_w(c, 20) for c in text)
        # box just wide enough to hold one line, ratio ~0.99 (> 0.98 threshold)
        width = glyph_w / 0.99
        res = lint_children([self._text(text, width)])
        self.assertIn("TEXT_TIGHT_WIDTH", warn_codes(res))

    def test_comfortable_single_line_is_clean(self):
        text = "宽松标题"
        res = lint_children([self._text(text, 600)])
        self.assertNotIn("TEXT_TIGHT_WIDTH", warn_codes(res))

    def test_multi_line_body_that_fills_width_is_not_flagged(self):
        # wrapping body text legitimately fills the line width; must stay quiet
        text = "这是一段会被排成多行的正文，它的每一行都可能接近框宽，" \
               "但多行排版本就该填满行宽，因此不应触发单行临界宽度警告。"
        deck = {"theme": "consulting", "composed": False, "slides": [{
            "type": "content", "composition": "freeform", "tone": "light",
            "children": [self._text(text, 240)]}]}
        layout.layout_deck(deck)
        text_node = next(n for n in lint.walk(deck["slides"][0]["_root"])
                         if n.get("t") == "text")
        self.assertGreaterEqual(len(text_node["_lines"]), 2)  # fixture really wraps
        res = lint.lint_deck(deck)
        self.assertNotIn("TEXT_TIGHT_WIDTH", warn_codes(res))


if __name__ == "__main__":
    unittest.main()
