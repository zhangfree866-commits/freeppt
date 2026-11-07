#!/usr/bin/env python3
"""Tests for the FreePPT theme registry and the zero-regression contract.

The consulting theme must stay pixel-identical to the legacy hard-coded
consulting palette; new themes must be self-consistent (every semantic color
is inside their own lint palette).

    python3 tests/test_themes.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import themes  # noqa: E402

LEGACY = {
    "navy": "#061F32", "royal": "#001965", "cyan": "#08A6F6",
    "light": "#99BDED", "wine": "#5A0E13", "green": "#177B57",
    "orange": "#F47B39", "gray": "#44546A", "mid": "#808080",
    "line": "#E5E7EB", "white": "#FFFFFF",
}

REQUIRED_SEMANTIC = [
    "surface_dark", "surface_light", "card_fill", "ink", "ink_on_dark",
    "body", "muted", "line", "accent", "accent_2", "accent_soft",
]
REQUIRED_VISUAL = [
    "latin_heading", "ea_heading", "latin_body", "ea_body", "radius",
    "shadow", "line_spacing", "chart_colors", "density", "accent_budget",
]


class TestZeroRegression(unittest.TestCase):
    def setUp(self):
        self.c = themes.get_theme("consulting")

    def test_consulting_semantic_matches_legacy(self):
        sem = self.c["semantic"]
        self.assertEqual(sem["surface_dark"], LEGACY["navy"])
        self.assertEqual(sem["ink"], LEGACY["navy"])
        self.assertEqual(sem["accent"], LEGACY["cyan"])
        self.assertEqual(sem["accent_2"], LEGACY["royal"])
        self.assertEqual(sem["accent_soft"], LEGACY["light"])
        self.assertEqual(sem["body"], LEGACY["gray"])
        self.assertEqual(sem["muted"], LEGACY["mid"])
        self.assertEqual(sem["line"], LEGACY["line"])
        self.assertEqual(sem["ink_on_dark"], LEGACY["white"])
        self.assertEqual(sem["card_fill"], LEGACY["white"])

    def test_consulting_is_square_cards(self):
        # legacy engine rendered square cards; radius must stay 0
        self.assertEqual(self.c["visual"]["radius"], 0)

    def test_consulting_palette_contains_all_legacy_colors(self):
        for hx in LEGACY.values():
            self.assertIn(hx.upper(), self.c["palette"])

    def test_consulting_lint_contract_keys(self):
        for key in ("palette", "font", "min_body",
                    "layout_min_chars", "no_footer"):
            self.assertIn(key, self.c)
        self.assertEqual(self.c["min_body"], 18)


class TestNewThemes(unittest.TestCase):
    NEW = ["magazine", "tech", "swiss", "oriental"]
    ENTERPRISE = ["mckinsey", "bcg", "pwc", "rolandberger", "microsoft", "apple"]
    DATA_DRIVEN = ["stripe", "vercel", "wired", "ibm"]

    def test_all_registered(self):
        for name in self.NEW + self.ENTERPRISE + self.DATA_DRIVEN:
            self.assertIn(name, themes.THEMES)

    def test_required_tokens_present(self):
        for name in self.NEW + self.ENTERPRISE + self.DATA_DRIVEN:
            th = themes.THEMES[name]
            for role in REQUIRED_SEMANTIC:
                self.assertIn(role, th["semantic"], f"{name} missing {role}")
            for key in REQUIRED_VISUAL:
                self.assertIn(key, th["visual"], f"{name} missing {key}")

    def test_palette_self_consistent(self):
        # every semantic color must be inside the theme's own lint palette
        for name in self.NEW + self.ENTERPRISE + self.DATA_DRIVEN:
            th = themes.THEMES[name]
            for role, hx in th["semantic"].items():
                self.assertIn(hx.upper(), th["palette"],
                              f"{name}.{role} {hx} outside its palette")
            for hx in th["visual"]["chart_colors"]:
                self.assertIn(hx.upper(), th["palette"],
                              f"{name} chart color {hx} outside palette")

    def test_consulting_houses_are_square_and_strict(self):
        # professional consulting tone: square corners, strict density
        for name in ["mckinsey", "bcg", "pwc", "rolandberger"]:
            vis = themes.THEMES[name]["visual"]
            self.assertEqual(vis["radius"], 0, f"{name} must use square cards")
            self.assertEqual(vis["density"], "strict")

    def test_distinct_visual_languages(self):
        # the four editorial themes must not share the same accent
        accents = {themes.THEMES[n]["semantic"]["accent"] for n in self.NEW}
        self.assertEqual(len(accents), 4)

    def test_enterprise_accents_distinct_within_set(self):
        accents = {themes.THEMES[n]["semantic"]["accent"]
                   for n in self.ENTERPRISE}
        self.assertEqual(len(accents), len(self.ENTERPRISE))

    def test_serif_pairing_for_editorial_themes(self):
        self.assertTrue(themes.THEMES["magazine"]["visual"]["serif_heading"])
        self.assertTrue(themes.THEMES["oriental"]["visual"]["serif_heading"])
        self.assertFalse(themes.THEMES["tech"]["visual"]["serif_heading"])


class TestResolution(unittest.TestCase):
    def test_theme_wins_over_scenario(self):
        self.assertEqual(
            themes.resolve_name({"theme": "tech", "scenario": "consulting"}),
            "tech")

    def test_legacy_scenario_still_resolves(self):
        self.assertEqual(themes.resolve_name({"scenario": "consulting"}),
                         "consulting")
        self.assertEqual(themes.resolve_name({}), "general")

    def test_aliases(self):
        self.assertEqual(themes.resolve_name({"theme": "editorial"}), "magazine")
        self.assertEqual(themes.resolve_name({"theme": "minimal"}), "swiss")
        self.assertEqual(themes.resolve_name({"theme": "dark-tech"}), "tech")
        self.assertEqual(themes.resolve_name({"theme": "chinese"}), "oriental")
        self.assertEqual(themes.resolve_name({"theme": "bgc"}), "bcg")
        self.assertEqual(themes.resolve_name({"theme": "mck"}), "mckinsey")
        self.assertEqual(themes.resolve_name({"theme": "msft"}), "microsoft")
        self.assertEqual(themes.resolve_name({"theme": "rb"}), "rolandberger")
        self.assertEqual(themes.resolve_name({"theme": "carbon"}), "ibm")
        self.assertEqual(themes.resolve_name({"theme": "geist"}), "vercel")
        self.assertEqual(themes.resolve_name({"theme": "stripi"}), "stripe")
        self.assertEqual(themes.resolve_name({"theme": "editorial-bw"}), "wired")

    def test_unknown_falls_back_to_general(self):
        self.assertEqual(themes.resolve_name({"theme": "nope"}), "general")
        self.assertEqual(themes.get_theme("nope")["name"], "general")

    def test_activate_switches_active_theme(self):
        themes.activate({"theme": "swiss"})
        self.assertEqual(themes.get_active()["name"], "swiss")
        self.assertEqual(themes.semantic("accent"), "#E63312")
        themes.activate("consulting")  # restore default
        self.assertEqual(themes.get_active()["name"], "consulting")
        self.assertEqual(themes.semantic("accent"), "#08A6F6")


if __name__ == "__main__":
    unittest.main(verbosity=2)
