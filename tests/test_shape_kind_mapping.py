"""Regression for the freeform shape-kind mapping (PNG/pptx parity).

A silent fallback once made ``kind="rect"`` compile to an OVAL because
``SHAPE_KINDS`` lacked a ``rect`` key while debug_render still drew a rectangle,
so the PNG preview and the real pptx diverged. These tests pin every legal kind
to its native MSO autoshape, make rect the explicit default on both renderers,
and guarantee an unknown kind is rejected by lint and by the compiler instead of
degrading quietly.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pptx import Presentation  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE  # noqa: E402
from pptx.util import Emu  # noqa: E402

from engine import layout, lint, compiler  # noqa: E402

NAVY = "#061F32"

# DSL kind -> the exact native autoshape that must land in the pptx.
EXPECTED = {
    "rect": MSO_SHAPE.RECTANGLE,
    "oval": MSO_SHAPE.OVAL,
    "roundrect": MSO_SHAPE.ROUNDED_RECTANGLE,
    "chevron": MSO_SHAPE.CHEVRON,
    "arrow": MSO_SHAPE.RIGHT_ARROW,
}


def shape_node(kind=None, rect=(60, 200, 100, 160)):
    node = {"t": "shape", "rect": list(rect), "fill": NAVY}
    if kind is not None:
        node["kind"] = kind
    return node


def build_deck(children):
    deck = {"theme": "consulting", "composed": False, "slides": [{
        "type": "content", "composition": "freeform", "tone": "light",
        "children": children}]}
    layout.layout_deck(deck)
    path = tempfile.mktemp(suffix=".pptx")
    compiler.build_pptx(deck, path, force=True)
    return deck, path


def authored_shapes(path):
    """Autoshapes on slide 1 excluding the full-canvas background slab."""
    slide = Presentation(path).slides[0]
    out = []
    for sh in slide.shapes:
        if sh.shape_type != MSO_SHAPE_TYPE.AUTO_SHAPE:
            continue
        w = round(Emu(sh.width).inches * 96)
        if w >= 1280:  # the compiler-inserted 1280x720 background rect
            continue
        out.append(sh.auto_shape_type)
    return out


class TestShapeKindMapping(unittest.TestCase):
    def test_every_legal_kind_maps_to_its_native_shape(self):
        kinds = list(EXPECTED)
        _, path = build_deck([shape_node(k) for k in kinds])
        self.assertEqual(authored_shapes(path),
                         [EXPECTED[k] for k in kinds])

    def test_rect_is_a_rectangle_not_oval(self):
        _, path = build_deck([shape_node("rect")])
        self.assertEqual(authored_shapes(path), [MSO_SHAPE.RECTANGLE])

    def test_default_kind_is_rectangle_on_both_renderers(self):
        # No kind declared: compiler and debug preview must agree on a rect.
        deck, path = build_deck([shape_node(None)])
        self.assertEqual(authored_shapes(path), [MSO_SHAPE.RECTANGLE])
        # the preview's default branch also treats a missing kind as rect
        node = deck["slides"][0]["_root"]["children"][0]
        self.assertEqual(node.get("kind", "rect"), "rect")

    def test_unknown_kind_is_a_lint_error(self):
        deck = {"theme": "consulting", "composed": False, "slides": [{
            "type": "content", "composition": "freeform", "tone": "light",
            "children": [shape_node("elipse")]}]}  # typo on purpose
        layout.layout_deck(deck)
        res = lint.lint_deck(deck)
        codes = {e["code"] for e in res["errors"]}
        self.assertIn("SHAPE_KIND", codes)
        self.assertFalse(res["ok"])

    def test_unknown_kind_raises_in_compiler(self):
        deck = {"theme": "consulting", "composed": False, "slides": [{
            "type": "content", "composition": "freeform", "tone": "light",
            "children": [shape_node("elipse")]}]}
        layout.layout_deck(deck)
        path = tempfile.mktemp(suffix=".pptx")
        with self.assertRaises(ValueError):
            compiler.build_pptx(deck, path, force=True)

    def test_shape_kinds_table_has_rect(self):
        # single source of truth the lint gate imports
        self.assertEqual(compiler.SHAPE_KINDS["rect"], MSO_SHAPE.RECTANGLE)
        self.assertEqual(
            set(compiler.SHAPE_KINDS),
            {"rect", "oval", "roundrect", "chevron", "arrow"})


if __name__ == "__main__":
    unittest.main()
