#!/usr/bin/env python3
"""Tests for the DESIGN.md token importer and data-driven themes.

The key contract: every hex used by a data-driven theme must be present in
the imported source archive. This makes it impossible to smuggle in invented
colors.

    python3 tests/test_design_md_import.py
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import design_md_import as imp  # noqa: E402
from engine import themes  # noqa: E402

# Synthetic frontmatter in the same shape as real DESIGN.md files.
# It is NOT copied from the upstream repository.
SAMPLE = """---
version: alpha
name: Sample-design-analysis
description: Synthetic parser fixture.
colors:
  primary: "#123456"
  canvas: "#FFFFFF"
  ink: "#0D253D"
typography:
  display-lg:
    fontFamily: "Inter, sans-serif"
    fontSize: 32px
    lineHeight: 1.1
    fontWeight: 300
rounded:
  sm: 6px
spacing:
  md: 16px
---
# Body text is ignored by the parser.
"""

DATA_DRIVEN = ["stripe", "vercel", "wired", "ibm"]


def _archive():
    with open(os.path.join(ROOT, "references/imported/design_tokens.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _mapping():
    with open(os.path.join(ROOT, "references/imported/theme_mapping.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


class TestParser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8")
        self.tmp.write(SAMPLE)
        self.tmp.close()
        self.parsed = imp.parse_design_md(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_colors_extracted(self):
        self.assertEqual(self.parsed["colors"],
                         {"primary": "#123456", "canvas": "#FFFFFF",
                          "ink": "#0D253D"})

    def test_typography_metrics_extracted(self):
        display = self.parsed["typography"]["display-lg"]
        self.assertEqual(display["fontSize"], 32.0)
        self.assertEqual(display["lineHeight"], 1.1)
        self.assertEqual(display["fontWeight"], 300.0)
        self.assertEqual(display["fontFamily"], "Inter, sans-serif")

    def test_scales_extracted(self):
        self.assertEqual(self.parsed["rounded"], {"sm": 6.0})
        self.assertEqual(self.parsed["spacing"], {"md": 16.0})

    def test_sha256_is_stable(self):
        self.assertEqual(len(self.parsed["sha256"]), 64)
        self.assertEqual(self.parsed["sha256"],
                         imp.parse_design_md(self.tmp.name)["sha256"])

    def test_mapping_is_exact(self):
        colors = self.parsed["colors"]
        self.assertEqual(
            imp.semantic_from_mapping(colors, {"accent": "primary",
                                               "surface_light": "canvas"}),
            {"accent": "#123456", "surface_light": "#FFFFFF"})

    def test_missing_token_raises(self):
        with self.assertRaises(KeyError):
            imp.semantic_from_mapping(self.parsed["colors"],
                                      {"accent": "does-not-exist"})


class TestImportedArchive(unittest.TestCase):
    def setUp(self):
        self.archive = _archive()

    def test_license_and_repository(self):
        self.assertEqual(self.archive["license"], "MIT")
        self.assertEqual(self.archive["repository"],
                         "VoltAgent/awesome-design-md")

    def test_all_six_sources_present_with_hashes(self):
        self.assertEqual(len(self.archive["files"]), 6)
        for name, entry in self.archive["files"].items():
            self.assertEqual(len(entry["sha256"]), 64, name)
            self.assertTrue(entry["colors"], name)
            self.assertTrue(entry["url"].endswith(
                f"design-md/{name}/DESIGN.md"), name)

    def test_mapping_keys_exist_in_source(self):
        for source, mapping in _mapping().items():
            if source.startswith("_"):
                continue
            colors = self.archive["files"][source]["colors"]
            for role, key in mapping.items():
                self.assertIn(key, colors,
                              f"{source}.{role} -> missing key {key}")

    def test_mapping_reproduces_registered_semantics(self):
        for source, mapping in _mapping().items():
            if source.startswith("_"):
                continue
            expected = imp.semantic_from_mapping(
                self.archive["files"][source]["colors"], mapping)
            actual = themes.THEMES[source]["semantic"]
            self.assertEqual({k: v.upper() for k, v in actual.items()},
                             {k: v.upper() for k, v in expected.items()},
                             source)


class TestDataDrivenThemes(unittest.TestCase):
    def setUp(self):
        self.archive = _archive()

    def test_all_registered(self):
        for name in DATA_DRIVEN:
            self.assertIn(name, themes.THEMES)

    def test_every_hex_is_traceable_to_source(self):
        for name in DATA_DRIVEN:
            allowed = set(self.archive["files"][name]["colors"].values())
            th = themes.THEMES[name]
            for role, hx in th["semantic"].items():
                self.assertIn(hx.upper(), allowed,
                              f"{name}.{role} {hx} not in source")
            for hx in th["visual"]["chart_colors"]:
                self.assertIn(hx.upper(), allowed,
                              f"{name} chart color {hx} not in source")

    def test_radius_matches_source_rounded_scale(self):
        for name in DATA_DRIVEN:
            rounded = self.archive["files"][name]["rounded"]
            self.assertIn(float(themes.THEMES[name]["visual"]["radius"]),
                          set(rounded.values()), name)

    def test_wired_is_serif_and_wireframe_square(self):
        vis = themes.THEMES["wired"]["visual"]
        self.assertTrue(vis["serif_heading"])
        self.assertEqual(vis["radius"], 0)

    def test_aliases_resolve(self):
        self.assertEqual(themes.resolve_name({"theme": "carbon"}), "ibm")
        self.assertEqual(themes.resolve_name({"theme": "geist"}), "vercel")
        self.assertEqual(themes.resolve_name({"theme": "stripi"}), "stripe")
        self.assertEqual(themes.resolve_name({"theme": "editorial-bw"}), "wired")


if __name__ == "__main__":
    unittest.main(verbosity=2)
