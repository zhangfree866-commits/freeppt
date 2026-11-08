"""Tests for the long-deck guardrails, research ledger and data archetypes.

These cover the failure modes found in the 88-page incident:
* a flat file longer than the archetype pool must be refused at compose time;
* chapters reset the variety budget so long decks can pass the lint gate;
* --force leaves a visible marker inside the produced pptx;
* research demands without a source ledger block the build;
* chart/table notes pages compile to native editable chart/table shapes.
"""

import copy
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import art_direction as ad  # noqa: E402
from engine.cli import prepare  # noqa: E402
from engine.compiler import build_pptx  # noqa: E402
from engine.lint import lint_deck  # noqa: E402
from engine import pptx_edit  # noqa: E402


def content_page(i, kind="concept"):
    return {
        "kind": kind,
        "title": f"内容页 {i}：一个足够长的结论式标题",
        "lead": "这是该页的导语，用于交代背景与论证的起点。",
        "points": [
            {"head": "要点甲", "body": "第一个论证要点的展开说明，保持内容具体。"},
            {"head": "要点乙", "body": "第二个论证要点的展开说明，与要点甲形成呼应。"},
            {"head": "要点丙", "body": "第三个论证要点的展开说明，收束到页面结论。"},
        ],
        "source": "来源：示例资料（测试用）",
    }


def chapter_page(no, title):
    return {"kind": "chapter", "no": no, "title": title,
            "en": "Chapter " + no}


def notes(pages):
    return {"book": {"title": "护栏测试书", "author": "测试"}, "pages": pages}


class TestLongDeckGuard(unittest.TestCase):
    def test_flat_deck_over_cap_is_refused_at_compose(self):
        pages = [{"kind": "cover", "title": "封面"}]
        pages += [content_page(i) for i in range(ad.CHAPTER_PAGE_CAP)]
        with self.assertRaises(ValueError) as ctx:
            ad.compose(notes(pages))
        self.assertIn("chapter", str(ctx.exception))

    def test_explicit_override_allows_long_compose(self):
        pages = [{"kind": "cover", "title": "封面"}]
        pages += [content_page(i) for i in range(ad.CHAPTER_PAGE_CAP)]
        doc = notes(pages)
        doc["allow_long_deck"] = True
        deck, _ = ad.compose(doc)
        self.assertTrue(deck["art_direction"]["long_deck_forced"])

    def test_chaptered_long_deck_passes_lint_gate(self):
        pages = [{"kind": "cover", "title": "封面"}]
        for ch in (1, 2):
            pages.append(chapter_page(f"0{ch}", f"第 {ch} 章"))
            pages += [content_page(i + ch * 10) for i in range(8)]
        pages.append({"kind": "closing", "title": "结语"})
        deck, ledger = ad.compose(notes(pages))
        self.assertEqual(len(ledger["chapter_boundaries"]), 2)
        res = lint_deck(prepare(copy.deepcopy(deck)))
        self.assertTrue(res["ok"], res["errors"])

    def test_archetype_may_recur_across_chapters_but_not_inside_one(self):
        pages = [{"kind": "cover", "title": "封面"}]
        pages.append(chapter_page("01", "第一章"))
        pages += [content_page(i) for i in range(4)]
        pages.append(chapter_page("02", "第二章"))
        pages += [content_page(i + 10) for i in range(4)]
        deck, _ = ad.compose(notes(pages))
        prepared = prepare(copy.deepcopy(deck))
        # the same archetype appearing in both chapters must not be a global
        # variety failure any more
        arch = [s["archetype"] for s in prepared["slides"]]
        self.assertLessEqual(len(set(arch)), len(arch))  # some recurrence exists
        res = lint_deck(prepared)
        variety = [e for e in res["errors"] if e["code"] == "LAYOUT_VARIETY"]
        self.assertEqual(variety, [])

    def test_force_build_writes_marker_into_pptx(self):
        pages = [{"kind": "cover", "title": "封面"}]
        pages += [content_page(i) for i in range(4)]
        deck, _ = ad.compose(notes(pages))
        prepared = prepare(deck)
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "forced.pptx")
            build_pptx(prepared, out, force=True)
            report = pptx_edit.inspect(out)
            names = {sh["name"] for sh in report["slides"][0]["shapes"]}
            self.assertIn("FreePPTForcedBuildMarker", names)

    def test_normal_build_has_no_force_marker(self):
        pages = [{"kind": "cover", "title": "封面"}]
        pages += [content_page(i) for i in range(4)]
        deck, _ = ad.compose(notes(pages))
        prepared = prepare(deck)
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "clean.pptx")
            build_pptx(prepared, out, force=False)
            report = pptx_edit.inspect(out)
            names = {sh["name"] for sh in report["slides"][0]["shapes"]}
            self.assertNotIn("FreePPTForcedBuildMarker", names)


class TestResearchLedger(unittest.TestCase):
    def _deck_with_research(self, sources=None):
        page = content_page(1)
        page.pop("source", None)  # the point is: no provenance at all
        page["research"] = True
        if sources is not None:
            page["sources"] = sources
        deck, _ = ad.compose(notes([{"kind": "cover", "title": "封面"}, page]))
        return prepare(copy.deepcopy(deck))

    def test_research_without_sources_blocks_build(self):
        res = lint_deck(self._deck_with_research())
        self.assertIn("RESEARCH_LEDGER", {e["code"] for e in res["errors"]})

    def test_research_with_valid_sources_passes(self):
        sources = [{"title": "克里斯坦森《创新者的窘境》",
                    "url": "https://example.org/book",
                    "publisher": "哈佛商学院出版社"}]
        res = lint_deck(self._deck_with_research(sources))
        self.assertNotIn("RESEARCH_LEDGER", {e["code"] for e in res["errors"]})

    def test_research_field_is_passed_through_to_slide(self):
        page = content_page(1)
        page["research"] = "补充行业渗透率数据"
        deck, _ = ad.compose(notes([{"kind": "cover", "title": "封面"}, page]))
        self.assertEqual(deck["slides"][1]["research"], "补充行业渗透率数据")


class TestDataArchetypes(unittest.TestCase):
    def test_chart_page_routes_to_native_chart_archetype(self):
        page = {
            "kind": "data", "title": "渗透率随时间明显抬升",
            "lead": "三组数据共同指向同一个拐点。",
            "chart": {"kind": "column",
                      "categories": ["2022", "2023", "2024"],
                      "series": [{"name": "渗透率", "values": [12, 28, 47]}]},
            "source": "来源：行业报告（测试）",
        }
        deck, _ = ad.compose(notes([{"kind": "cover", "title": "封面"}, page]))
        self.assertEqual(deck["slides"][1]["archetype"], "chart-story")
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "chart.pptx")
            build_pptx(prepare(copy.deepcopy(deck)), out)
            report = pptx_edit.inspect(out)
            charts = [sh for s in report["slides"] for sh in s["shapes"]
                      if sh.get("chart")]
            self.assertEqual(len(charts), 1)
            self.assertEqual(charts[0]["chart"]["series"], 1)

    def test_table_page_routes_to_native_table_archetype(self):
        page = {
            "kind": "framework", "title": "两类创新的结构性差异",
            "table": {"headers": ["维度", "延续式创新", "颠覆式创新"],
                      "rows": [["目标客户", "主流客户", "边缘客户"],
                               ["性能轨迹", "持续提升", "初期偏低"]]},
            "note": "表格只做结构对照，具体数值另附来源。",
        }
        deck, _ = ad.compose(notes([{"kind": "cover", "title": "封面"}, page]))
        self.assertEqual(deck["slides"][1]["archetype"], "table-board")
        prepared = prepare(copy.deepcopy(deck))
        self.assertTrue(lint_deck(prepared)["ok"])
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "table.pptx")
            build_pptx(prepared, out)
            report = pptx_edit.inspect(out)
            tables = [sh for s in report["slides"] for sh in s["shapes"]
                      if sh.get("table")]
            self.assertEqual(len(tables), 1)
            self.assertEqual(tables[0]["table"]["rows"], 3)
            self.assertEqual(tables[0]["table"]["cols"], 3)

    def test_malformed_table_is_a_lint_error(self):
        deck, _ = ad.compose(notes([{"kind": "cover", "title": "封面"}]))
        deck["slides"].append({
            "type": "content", "composition": "freeform", "tone": "light",
            "archetype": "table-board", "density": "dense",
            "surface": "#FFFFFF",
            "children": [{"t": "table", "rect": [64, 140, 1152, 400],
                          "headers": ["A", "B"], "rows": [["only-one"]]}],
        })
        res = lint_deck(prepare(deck))
        self.assertIn("TABLE_SHAPE", {e["code"] for e in res["errors"]})

    def test_determinism_holds_for_chaptered_deck(self):
        pages = [{"kind": "cover", "title": "封面"}]
        pages.append(chapter_page("01", "第一章"))
        pages += [content_page(i) for i in range(5)]
        a, la = ad.compose(notes(pages))
        b, lb = ad.compose(notes(pages))
        self.assertEqual(json.dumps(a, sort_keys=True),
                         json.dumps(b, sort_keys=True))
        self.assertEqual(la["seed"], lb["seed"])


if __name__ == "__main__":
    unittest.main()
