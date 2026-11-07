#!/usr/bin/env python3
"""Offline tests for engine/web_search.py against a recorded Commons fixture.

Runs with no network: the Wikimedia response shape in tests/fixtures mirrors
the real generator=search + imageinfo/extmetadata schema, so the pure parsing
layer is fully exercised even when commons.wikimedia.org is unreachable.

    python3 tests/test_web_search.py
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import web_search as ws  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__),
                       "fixtures", "commons_search_sample.json")


def load_payload():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


class TestParse(unittest.TestCase):
    def setUp(self):
        self.cands = ws.parse_search_response(load_payload())

    def test_skips_record_without_imageinfo(self):
        # 6 pages, one has no imageinfo -> 5 candidates
        self.assertEqual(len(self.cands), 5)
        self.assertFalse(
            any("Broken record" in c["file_title"] for c in self.cands))

    def test_orders_by_search_index(self):
        # lowest index=1 is the 1900 hydro map
        self.assertEqual(self.cands[0]["file_title"],
                         "File:Old hydro map 1900.jpg")
        indexes = [1, 2, 3, 4, 5]
        titles_in_order = [c["file_title"] for c in self.cands]
        self.assertEqual(titles_in_order[1], "File:Solar panel array.png")
        self.assertEqual(len(indexes), 5)

    def test_html_and_entities_cleaned(self):
        wind = next(c for c in self.cands
                    if c["file_title"] == "File:Wind turbines Iowa.jpg")
        self.assertEqual(wind["author"], "Jane Roe")          # <a> tags stripped
        self.assertNotIn("<", wind["title"])
        solar = next(c for c in self.cands
                     if c["file_title"] == "File:Solar panel array.png")
        # &nbsp; -> space, &amp; -> &
        self.assertEqual(solar["title"],
                         "Utility-scale solar PV array & inverters")
        hydro = next(c for c in self.cands
                     if "water station" in c["file_title"])
        self.assertEqual(hydro["title"], "Pumped-storage hydro station")

    def test_license_flags(self):
        by = {c["file_title"]: c for c in self.cands}
        self.assertTrue(by["File:Solar panel array.png"]["permissive"])       # CC0
        self.assertTrue(by["File:Old hydro map 1900.jpg"]["permissive"])      # PD
        self.assertTrue(by["File:Wind turbines Iowa.jpg"]["permissive"])      # CC BY-SA
        self.assertFalse(
            by["File:Vendor proprietary chart.jpg"]["permissive"])            # ARR

    def test_thumb_fallback_to_original(self):
        old = next(c for c in self.cands
                   if c["file_title"] == "File:Old hydro map 1900.jpg")
        # no thumburl present -> must fall back to full url and its dimensions
        self.assertTrue(old["url"].endswith("Old_hydro_map_1900.jpg"))
        self.assertEqual(old["width"], 2000)
        self.assertEqual(old["height"], 1500)

    def test_source_page_present(self):
        for c in self.cands:
            self.assertTrue(c["source_page"].startswith(
                "https://commons.wikimedia.org/wiki/File:"))


class TestQueryAndFilter(unittest.TestCase):
    def test_build_query_url(self):
        url = ws.build_query_url("wind energy", limit=3, width=1024)
        self.assertIn("generator=search", url)
        self.assertIn("gsrnamespace=6", url)
        self.assertIn("gsrlimit=3", url)
        self.assertIn("iiurlwidth=1024", url)
        self.assertIn("wind+energy", url.replace("%20", "+"))

    def test_permissive_filter(self):
        payload = load_payload()
        all_c = ws.parse_search_response(payload)
        kept = [c for c in all_c if c["permissive"]]
        self.assertEqual(len(kept), 4)
        self.assertFalse(
            any("Vendor proprietary" in c["file_title"] for c in kept))

    def test_search_with_injected_fetcher(self):
        # proves search() decouples network from parsing via fetcher injection
        cands = ws.search("anything", fetcher=lambda url: load_payload())
        self.assertEqual(len(cands), 5)
        self.assertEqual(cands[0]["file_title"], "File:Old hydro map 1900.jpg")


class TestManifestMapping(unittest.TestCase):
    def setUp(self):
        self.cands = ws.parse_search_response(load_payload())
        self.items = ws.to_manifest_items(self.cands)

    def test_schema_matches_web_images(self):
        required = {"name", "url", "title", "author", "license", "source_page"}
        self.assertEqual(len(self.items), 5)
        for it in self.items:
            self.assertTrue(required.issubset(it.keys()))
            self.assertTrue(it["url"].startswith("https://"))

    def test_safe_name_strips_thumb_prefix_and_sanitizes(self):
        wind = next(i for i in self.items
                    if "Wind_turbines_Iowa" in i["url"])
        # 1280px- thumb prefix removed, web- prefixed, lowercased
        self.assertNotIn("1280px", wind["name"])
        self.assertTrue(wind["name"].startswith("web-"))
        self.assertTrue(wind["name"].endswith(".jpg"))

    def test_name_dedup(self):
        # force two identical urls -> names must not collide
        dup = [self.cands[0], dict(self.cands[0])]
        items = ws.to_manifest_items(dup)
        names = [i["name"] for i in items]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 2)

    def test_write_manifest_roundtrip(self):
        path = "/tmp/_ws_manifest_test.json"
        manifest = ws.write_manifest(self.cands, "examples/assets", path)
        self.assertEqual(manifest["out_dir"], "examples/assets")
        with open(path, encoding="utf-8") as f:
            reloaded = json.load(f)
        self.assertEqual(len(reloaded["items"]), 5)
        os.remove(path)


class TestRobustness(unittest.TestCase):
    def test_empty_and_malformed_payloads(self):
        self.assertEqual(ws.parse_search_response(None), [])
        self.assertEqual(ws.parse_search_response({}), [])
        self.assertEqual(ws.parse_search_response({"query": {}}), [])
        self.assertEqual(ws.parse_search_response({"query": {"pages": {}}}), [])

    def test_clean_html_directly(self):
        self.assertEqual(ws.clean_html("<b>Hi</b> &amp; <i>bye</i>"), "Hi & bye")
        self.assertEqual(ws.clean_html(""), "")
        self.assertEqual(ws.clean_html(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
