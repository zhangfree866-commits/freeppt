"""Tests for the declarative 12-column grid on freeform canvases.

Top-level freeform nodes may declare col_start/col_span instead of an absolute
x/width; layout maps those onto the theme's grid_columns over the master content
band. Nodes without the fields keep their explicit rect byte-for-byte, so the
feature is opt-in and legacy decks are untouched.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import layout, lint, compiler  # noqa: E402

NAVY = "#061F32"
ACCENT = "#08A6F6"
WHITE = "#FFFFFF"


def freeform_deck(children, theme="consulting"):
    return {"theme": theme, "composed": False, "slides": [{
        "type": "content", "composition": "freeform", "tone": "light",
        "children": children}]}


def laid_out(children, theme="consulting"):
    d = freeform_deck(children, theme)
    layout.layout_deck(d)
    return d["slides"][0]["_root"]["children"], d


def card(rect, **kw):
    node = {"t": "card", "rect": rect, "fill": WHITE, "children": []}
    node.update(kw)
    return node


class TestGridGeometry(unittest.TestCase):
    def test_grid_spec_matches_master_content_band(self):
        spec = layout.grid_spec()
        self.assertEqual(spec["cols"], 12)
        self.assertEqual(spec["x0"], layout.PAD)              # 60
        # 12 columns + 11 gutters fill the 1160px content band
        total = 12 * spec["col_w"] + 11 * spec["gutter"]
        self.assertAlmostEqual(total, 1160.0, places=1)

    def test_symmetric_two_columns_meet_with_one_gutter(self):
        kids, _ = laid_out([
            card([0, 120, 10, 300], col_start=1, col_span=6),
            card([0, 120, 10, 300], col_start=7, col_span=6),
        ])
        left, right = kids[0]["_rect"], kids[1]["_rect"]
        self.assertEqual(left[0], 60.0)
        self.assertEqual(left[2], 568.0)
        self.assertEqual(right[0], 652.0)     # 60 + 568 + 24 gutter
        self.assertEqual(right[2], 568.0)
        self.assertEqual(right[0] + right[2], 1220.0)  # ends at CANVAS_W - 60
        # grid only drives horizontal geometry; y/h still come from rect
        self.assertEqual(left[1], 120.0)
        self.assertEqual(left[3], 300.0)

    def test_asymmetric_seven_five_split(self):
        kids, _ = laid_out([
            card([0, 120, 10, 300], col_start=1, col_span=7),
            card([0, 120, 10, 300], col_start=8, col_span=5),
        ])
        wide, narrow = kids[0]["_rect"], kids[1]["_rect"]
        self.assertAlmostEqual(wide[2], 666.7, places=1)
        self.assertAlmostEqual(narrow[0], 750.7, places=1)
        self.assertAlmostEqual(narrow[2], 469.3, places=1)
        # no horizontal overlap and both stay inside the content band
        self.assertGreaterEqual(narrow[0], wide[0] + wide[2] + layout.GRID_GUTTER - 0.5)
        self.assertLessEqual(narrow[0] + narrow[2], 1220.5)

    def test_full_span_col_occupies_whole_band(self):
        kids, _ = laid_out([card([0, 80, 10, 80], col_start=1, col_span=12)])
        r = kids[0]["_rect"]
        self.assertEqual(r[0], 60.0)
        self.assertAlmostEqual(r[2], 1160.0, places=1)

    def test_default_span_is_one_column(self):
        kids, _ = laid_out([card([0, 80, 10, 80], col_start=4)])
        spec = layout.grid_spec()
        r = kids[0]["_rect"]
        self.assertAlmostEqual(r[0], spec["x0"] + 3 * (spec["col_w"] + spec["gutter"]),
                               places=1)
        self.assertAlmostEqual(r[2], spec["col_w"], places=1)


class TestGridRegressionAndNesting(unittest.TestCase):
    def test_node_without_grid_fields_keeps_explicit_rect(self):
        rect = [200, 150, 320, 240]
        kids, _ = laid_out([card(rect)])
        self.assertEqual(kids[0]["_rect"], [200.0, 150.0, 320.0, 240.0])

    def test_mixed_grid_and_absolute_nodes_coexist(self):
        kids, _ = laid_out([
            card([0, 100, 10, 200], col_start=1, col_span=6),
            card([700, 100, 300, 200]),  # absolute, untouched
        ])
        self.assertEqual(kids[0]["_rect"][0], 60.0)
        self.assertEqual(kids[1]["_rect"], [700.0, 100.0, 300.0, 200.0])

    def test_nested_grid_fields_are_ignored_local_rect_kept(self):
        parent = card([100, 100, 800, 400], col_start=1, col_span=12)
        parent["children"] = [
            card([20, 20, 120, 80], col_start=9, col_span=2),
        ]
        kids, d = laid_out([parent])
        nested = kids[0]["children"][0]
        # nested node keeps its local rect offset by the parent origin
        self.assertEqual(nested["_rect"][0], kids[0]["_rect"][0] + 20.0)
        self.assertEqual(nested["_rect"][2], 120.0)
        # and lint flags the ignored nested declaration as a warning
        res = lint.lint_deck(d)
        self.assertIn("GRID_COLUMN_NESTED", {w["code"] for w in res["warnings"]})
        self.assertTrue(res["ok"])  # warning never blocks


class TestGridLint(unittest.TestCase):
    def _lint(self, children):
        _, d = laid_out(children)
        return lint.lint_deck(d)

    def test_valid_columns_pass(self):
        res = self._lint([
            card([0, 100, 10, 200], col_start=1, col_span=12),
            card([0, 320, 10, 200], col_start=12, col_span=1),
        ])
        self.assertNotIn("GRID_COLUMN", {e["code"] for e in res["errors"]})
        self.assertTrue(res["ok"])

    def test_column_overflow_is_an_error(self):
        res = self._lint([card([0, 100, 10, 200], col_start=11, col_span=3)])
        self.assertIn("GRID_COLUMN", {e["code"] for e in res["errors"]})
        self.assertFalse(res["ok"])

    def test_non_positive_start_is_an_error(self):
        res = self._lint([card([0, 100, 10, 200], col_start=0, col_span=1)])
        self.assertIn("GRID_COLUMN", {e["code"] for e in res["errors"]})


class TestGridEndToEnd(unittest.TestCase):
    def test_grid_deck_builds_to_pptx(self):
        d = freeform_deck([
            {"t": "card", "rect": [0, 120, 10, 300], "fill": WHITE,
             "col_start": 1, "col_span": 7, "children": [
                 {"t": "text", "rect": [24, 24, 400, 40], "text": "宽栏标题",
                  "size": 24, "color": NAVY, "on": WHITE}]},
            {"t": "card", "rect": [0, 120, 10, 300], "fill": NAVY,
             "col_start": 8, "col_span": 5, "children": []},
        ])
        layout.layout_deck(d)
        self.assertTrue(lint.lint_deck(d)["ok"])
        out = os.path.join(tempfile.mkdtemp(), "grid.pptx")
        compiler.build_pptx(d, out, force=True)
        self.assertGreater(os.path.getsize(out), 5000)


if __name__ == "__main__":
    unittest.main()
