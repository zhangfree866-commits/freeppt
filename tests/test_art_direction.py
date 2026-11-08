"""Tests for creative (non-master) composition.

The point of this module is that "every page looks the same" becomes a
machine-detectable defect instead of a matter of taste.
"""

import copy
import json
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import art_direction, cover_style, themes  # noqa: E402
from engine.cli import prepare  # noqa: E402
from engine.compiler import build_pptx  # noqa: E402
from engine.lint import lint_deck, contrast_ratio  # noqa: E402

NOTES = os.path.join(ROOT, "examples", "notes_renqing_mianzi.json")
COVER = os.path.join(ROOT, "examples", "assets", "book_cover_demo.png")
OTHER_COVER = os.path.join(ROOT, "examples", "assets", "cover-bg.png")


def load_notes():
    with open(NOTES, encoding="utf-8") as f:
        return json.load(f)


def composed():
    return art_direction.compose(load_notes(), os.path.dirname(NOTES))[0]


class TestCoverStyle(unittest.TestCase):
    def test_derived_palette_is_legible_and_deterministic(self):
        spec, ledger = cover_style.derive(COVER, "人情与面子")
        spec2, _ = cover_style.derive(COVER, "人情与面子")
        self.assertEqual(spec, spec2)
        s = spec["semantic"]
        self.assertGreaterEqual(contrast_ratio(s["ink"], s["surface_light"]), 4.5)
        self.assertGreaterEqual(contrast_ratio(s["accent"], s["surface_light"]), 4.5)
        self.assertGreaterEqual(contrast_ratio(s["surface_light"], s["surface_dark"]), 4.5)
        self.assertIn(ledger["motif"], cover_style.MOTIF_BY_POS.values())
        self.assertEqual(len(ledger["cover_sha256"]), 64)

    def test_different_cover_gives_different_signature(self):
        a, _ = cover_style.derive(COVER, "book")
        b, _ = cover_style.derive(OTHER_COVER, "book")
        self.assertNotEqual(a["semantic"]["accent"], b["semantic"]["accent"])

    def test_derived_theme_activates_with_own_palette(self):
        spec, _ = cover_style.derive(COVER, "book")
        th = themes.activate({"derived_theme": spec})
        self.assertEqual(th["semantic"]["accent"].upper(),
                         spec["semantic"]["accent"].upper())
        self.assertIn(spec["semantic"]["accent"].upper(), th["palette"])


class TestComposition(unittest.TestCase):
    def test_deterministic(self):
        a, la = art_direction.compose(load_notes(), os.path.dirname(NOTES))
        b, lb = art_direction.compose(load_notes(), os.path.dirname(NOTES))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(la["seed"], lb["seed"])

    def test_every_page_has_a_different_archetype(self):
        deck = composed()
        arch = deck["art_direction"]["archetypes"]
        self.assertEqual(len(arch), len(deck["slides"]))
        self.assertEqual(len(set(arch)), len(arch))
        for i, s in enumerate(deck["slides"]):
            self.assertEqual(s["composition"], "freeform")
            self.assertEqual(s["archetype"], arch[i])
            self.assertTrue(s["children"])

    def test_no_empty_cards_when_content_is_short(self):
        deck = composed()
        for s in deck["slides"]:
            if s["archetype"] in ("grid-mosaic", "offset-triptych"):
                cards = [n for n in s["children"]
                         if n["t"] in ("richcard", "box") and n.get("fill")]
                self.assertGreaterEqual(len(cards), 2)

    def test_composed_deck_passes_lint_gate(self):
        deck = prepare(copy.deepcopy(composed()))
        res = lint_deck(deck)
        self.assertTrue(res["ok"], res["errors"])

    def test_lint_blocks_repeated_layout(self):
        deck = prepare(copy.deepcopy(composed()))
        deck["slides"][1]["archetype"] = deck["slides"][0]["archetype"]
        res = lint_deck(deck)
        codes = {e["code"] for e in res["errors"]}
        self.assertIn("LAYOUT_REPETITION", codes)

    def test_lint_blocks_flat_variety(self):
        deck = prepare(copy.deepcopy(composed()))
        # alternating two archetypes also repeats neighbours; use a weaker
        # mutation: keep neighbours different but collapse to two archetypes
        a, b = "editorial-spread", "margin-notes"
        for i, s in enumerate(deck["slides"]):
            s["archetype"] = a if i % 2 == 0 else b
        res = lint_deck(deck)
        self.assertIn("LAYOUT_VARIETY", {e["code"] for e in res["errors"]})

    def test_lint_blocks_out_of_canvas_and_overflow(self):
        deck = prepare(copy.deepcopy(composed()))
        node = deck["slides"][2]["children"][0]
        node["_rect"] = [2000, 90, 400, 60]
        res = lint_deck(deck)
        self.assertIn("OUT_OF_CANVAS", {e["code"] for e in res["errors"]})

    def test_freeform_allows_large_whitespace(self):
        """Old master rules (DENSITY/SAFE_AREA) must not judge a freeform page."""
        spec, _ = cover_style.derive(COVER, "book")
        deck = {
            "derived_theme": spec,
            "slides": [{
                "type": "content", "composition": "freeform", "tone": "light",
                "surface": spec["semantic"]["surface_light"],
                "archetype": "editorial-spread", "density": "airy",
                "children": [{
                    "t": "text", "rect": [8, 500, 300, 40],
                    "text": "一句放在角落的短句", "size": 20,
                    "color": spec["semantic"]["ink"],
                }],
            }],
        }
        res = lint_deck(prepare(deck))
        self.assertTrue(res["ok"], res["errors"])

    def test_freeform_blocks_low_contrast(self):
        spec, _ = cover_style.derive(COVER, "book")
        paper = spec["semantic"]["surface_light"]
        deck = {
            "derived_theme": spec,
            "slides": [{
                "type": "content", "composition": "freeform",
                "archetype": "quote-bleed", "density": "airy",
                "children": [{
                    "t": "text", "rect": [60, 60, 400, 50],
                    "text": "看不清的文字", "size": 20,
                    "color": paper, "on": paper,
                }],
            }],
        }
        res = lint_deck(prepare(deck))
        self.assertIn("CONTRAST", {e["code"] for e in res["errors"]})

    def test_build_produces_editable_native_shapes(self):
        from pptx import Presentation
        deck = prepare(copy.deepcopy(composed()))
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "composed.pptx")
            build_pptx(deck, out)
            prs = Presentation(out)
            self.assertEqual(len(prs.slides), len(deck["slides"]))
            for slide in prs.slides:
                self.assertGreater(len(slide.shapes), 2)
            self.assertTrue(os.path.getsize(out) > 10000)


class TestCLIRouting(unittest.TestCase):
    def test_prepare_keeps_master_decks_on_legacy_path(self):
        path = os.path.join(ROOT, "examples", "demo.json")
        with open(path, encoding="utf-8") as f:
            deck = prepare(json.load(f))
        self.assertNotIn("composed", deck)
        self.assertTrue(lint_deck(deck)["ok"])


class TestScoringSelection(unittest.TestCase):
    """Opt-in deterministic archetype scoring (replaces rng.shuffle)."""

    def _multi_concept_pages(self, count=8):
        # ordinary concept pages with enough blocks to survive MIN_POINTS
        return [{
            "kind": "concept",
            "title": f"概念页 {i}",
            "lead": "这一页的引导句。",
            "points": [{"head": f"要点 {j}", "body": "要点的具体阐述内容。"}
                       for j in range(3)],
        } for i in range(count)]

    def test_scoring_plan_is_invariant_across_seeds(self):
        pages = self._multi_concept_pages()
        plans = {
            tuple(art_direction.plan_archetypes(
                pages, random.Random(seed), scoring=True))
            for seed in (1, 42, 999, 2026)}
        self.assertEqual(len(plans), 1)  # every seed yields the identical plan

    def test_legacy_shuffle_still_varies_with_seed(self):
        # control: the default (scoring=False) path keeps consuming the RNG, so
        # different seeds legitimately produce different plans
        pages = self._multi_concept_pages()
        legacy = {
            tuple(art_direction.plan_archetypes(
                pages, random.Random(seed), scoring=False))
            for seed in range(20)}
        self.assertGreater(len(legacy), 1)

    def test_default_path_keeps_scoring_off(self):
        deck, ledger = art_direction.compose(load_notes(), os.path.dirname(NOTES))
        self.assertFalse(deck["art_direction"]["scoring"])
        self.assertFalse(ledger["scoring"])

    def test_specialized_archetype_wins_on_structural_cues(self):
        cases = [
            ({"kind": "quote", "title": "金句", "quote": "说一句值得停在画面上的话。"},
             "quote-bleed"),
            ({"kind": "compare", "title": "两条路线",
              "left": {"head": "方案甲", "body": "稳妥"},
              "right": {"head": "方案乙", "body": "激进"}},
             "split-contrast"),
            ({"kind": "data", "title": "关键指标", "value": "92%",
              "label": "客户满意度"},
             "data-focus"),
            ({"kind": "timeline", "title": "推进节奏",
              "points": [{"head": f"阶段 {j}", "body": "该阶段的交付。"}
                         for j in range(3)]},
             "timeline-ribbon"),
        ]
        for page, expected in cases:
            plan = art_direction.plan_archetypes(
                [page], random.Random(7), scoring=True)
            self.assertEqual(plan[0], expected,
                             f"{page['kind']} should route to {expected}")

    def test_chart_and_table_routing_survives_scoring(self):
        chart_page = {"kind": "data", "title": "带图表",
                      "chart": {"kind": "column", "categories": ["a"],
                                "series": [{"name": "s", "values": [1]}]},
                      "points": [{"head": "h", "body": "b"}]}
        table_page = {"kind": "data", "title": "带表格",
                      "table": {"headers": ["列"], "rows": [["值"]]},
                      "points": [{"head": "h", "body": "b"}]}
        self.assertEqual(
            art_direction.plan_archetypes([chart_page], random.Random(7),
                                          scoring=True)[0],
            "chart-story")
        self.assertEqual(
            art_direction.plan_archetypes([table_page], random.Random(7),
                                          scoring=True)[0],
            "table-board")

    def test_scoring_compose_is_deterministic_and_passes_lint(self):
        a, la = art_direction.compose(load_notes(), os.path.dirname(NOTES),
                                      scoring=True)
        b, lb = art_direction.compose(load_notes(), os.path.dirname(NOTES),
                                      scoring=True)
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        self.assertTrue(la["scoring"] and lb["scoring"])
        arch = a["art_direction"]["archetypes"]
        self.assertTrue(all(arch[i] != arch[i + 1]
                            for i in range(len(arch) - 1)))  # no neighbour repeat
        self.assertTrue(lint_deck(prepare(copy.deepcopy(a)))["ok"])

    def test_scoring_combines_with_card_system_deterministically(self):
        # Short bodies keep every dense archetype inside the canvas; this test
        # targets selection determinism, not the geometry layer's content-height
        # envelope (exercised separately by the lint overflow tests). The book
        # intentionally has no title so _chrome emits a single-line page number
        # rather than its two-line signature (whose second line touches the
        # bottom edge on a title-less, chapter-less flat deck).
        pages = [{
            "kind": "concept", "title": f"概念页 {i}", "lead": "引导句。",
            "points": [{"head": f"要点 {j}", "body": "短阐述。"}
                       for j in range(3)],
        } for i in range(6)]
        notes = {"book": {}, "pages": pages}
        a, _ = art_direction.compose(notes, base="magazine",
                                     card_system=True, scoring=True)
        b, _ = art_direction.compose(notes, base="magazine",
                                     card_system=True, scoring=True)
        self.assertEqual(a["art_direction"]["archetypes"],
                         b["art_direction"]["archetypes"])
        self.assertTrue(
            set(a["art_direction"]["archetypes"])
            & set(art_direction.CARD_ARCHETYPES))  # scoring does pick card layouts
        self.assertTrue(lint_deck(prepare(copy.deepcopy(a)))["ok"])


if __name__ == "__main__":
    unittest.main()
