#!/usr/bin/env python3
import unittest

from engine import page_spec


def note_page(**kw):
    base = {"kind": "content", "title": "T", "lead": "L"}
    base.update(kw)
    return base


class TestPageSpec(unittest.TestCase):
    def test_basic_content_fields(self):
        page = note_page(points=[{"head": "h1", "body": "b1"}])
        sp = page_spec.build_page_spec(page, "editorial-spread", 0, [])
        self.assertEqual(sp["title"], "T")
        self.assertEqual(sp["lead"], "L")
        self.assertEqual(sp["points"], [{"head": "h1", "body": "b1"}])
        self.assertEqual(sp["capacity"], 3)
        self.assertEqual(sp["density_hint"], "mid")
        self.assertEqual(sp["index"], 0)
        self.assertEqual(sp["datasets"], [])

    def test_chart_becomes_dataset(self):
        page = note_page(chart={"kind": "bar", "categories": ["a", "b"],
                                "series": [[1, 2]], "unit": "%"})
        sp = page_spec.build_page_spec(page, "chart-story", 1, [])
        self.assertEqual(len(sp["datasets"]), 1)
        ds = sp["datasets"][0]
        self.assertEqual(ds["type"], "bar")
        self.assertEqual(ds["categories"], ["a", "b"])
        self.assertEqual(ds["unit"], "%")

    def test_kpi_becomes_dataset(self):
        page = note_page(value=50, label="毛利率", unit="%")
        sp = page_spec.build_page_spec(page, "data-focus", 2, [])
        self.assertEqual(sp["datasets"], [{"type": "kpi", "series": [50],
                                           "title": "毛利率", "unit": "%"}])

    def test_compare_page(self):
        page = note_page(left={"head": "A", "body": "x"},
                         right={"head": "B", "body": "y"})
        sp = page_spec.build_page_spec(page, "split-contrast", 3, [])
        self.assertEqual(sp["compare"]["left"], {"head": "A", "body": "x"})
        self.assertEqual(len(sp["points"]), 2)

    def test_sources(self):
        page = note_page(source="书")
        self.assertEqual(page_spec.build_page_spec(page, "editorial-spread",
                                                   0, [])["sources"], ["书"])
        page2 = note_page(sources=["a", "b"])
        self.assertEqual(page_spec.build_page_spec(page2, "editorial-spread",
                                                   0, [])["sources"], ["a", "b"])

    def test_build_deck_plan_top_level(self):
        notes = {"book": {"title": "Deck", "language": "zh-CN"},
                 "pages": [note_page(kind="cover", title="C"),
                           note_page(points=[{"head": "h", "body": "b"}])]}
        plan = ["cover-editorial", "editorial-spread"]
        d = page_spec.build_deck_plan(notes, plan, None, base="magazine")
        self.assertEqual(d["canvas"], {"width": 1280, "height": 720, "dpi": 96})
        self.assertEqual(d["deck"]["title"], "Deck")
        self.assertEqual(d["deck"]["total_pages"], 2)
        self.assertEqual(len(d["pages"]), 2)
        self.assertEqual(d["pages"][0]["chapter"], "封面")


if __name__ == "__main__":
    unittest.main()
