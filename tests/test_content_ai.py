#!/usr/bin/env python3
"""Offline tests for the smart content pipeline (reports + content_ai).

Covers the deterministic half: report registry, skeleton validity, brief
parsing/routing, and the content quality gate. Language expansion itself is
done by the agent and is not unit-tested here.

    python3 tests/test_content_ai.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import reports, content_ai as ca  # noqa: E402

EIGHT = ["weekly", "monthly", "quarterly", "annual", "performance",
         "competition", "retrospective", "business"]


class TestReportRegistry(unittest.TestCase):
    def test_eight_types_registered(self):
        self.assertEqual(set(reports.REPORT_TYPES), set(EIGHT))

    def test_every_section_maps_to_real_template(self):
        from engine.templates import TEMPLATES
        for rt in EIGHT:
            for sec in reports.section_plan(rt):
                self.assertIn(sec["template"], TEMPLATES,
                              f"{rt} uses unknown template {sec['template']}")
                self.assertTrue(sec["role"] and sec["hint"] and sec["fields"])

    def test_default_theme_exists(self):
        from engine.themes import THEMES
        for rt in EIGHT:
            th = reports.REPORT_TYPES[rt]["default_theme"]
            self.assertIn(th, THEMES)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            reports.get_report("nope")


class TestSkeleton(unittest.TestCase):
    def test_skeleton_expands_and_is_structured(self):
        for rt in EIGHT:
            deck = reports.build_skeleton(rt)
            self.assertIn("theme", deck)
            self.assertGreaterEqual(len(deck["slides"]), 6)
            for s in deck["slides"]:
                self.assertIn("template", s)
                self.assertIsInstance(s["data"], dict)

    def test_skeleton_starts_with_cover_ends_with_closing(self):
        deck = reports.build_skeleton("annual")
        self.assertEqual(deck["slides"][0]["template"], "cover")
        self.assertEqual(deck["slides"][-1]["template"], "closing")


class TestBriefParsing(unittest.TestCase):
    def test_split_newlines_semicolons_bullets(self):
        brief = "- 收入增长20%\n；利润达标\n* 客户满意度 92%\n3. 上线新功能"
        pts = ca.parse_brief(brief)
        self.assertEqual(len(pts), 4)
        self.assertNotIn("-", pts[0])
        self.assertNotIn("3.", pts[-1])

    def test_empty(self):
        self.assertEqual(ca.parse_brief(""), [])
        self.assertEqual(ca.parse_brief(None), [])

    def test_routing_business_report(self):
        pts = ca.parse_brief(
            "收入增长23%\n毛利率41%\n环比新签走高\n"
            "交付周期偏长\n下一步客户分层\n9月上线CRM")
        bucket = ca.assign_points("business", pts)
        routed = sum(len(v) for v in bucket.values())
        self.assertEqual(routed, len(pts))  # every point lands somewhere
        plan = reports.section_plan("business")
        # numeric metric points should reach the kpi page
        kpi_idx = next(i for i, s in enumerate(plan)
                       if s["template"] == "kpi_row")
        self.assertTrue(any("收入" in p for p in bucket.get(kpi_idx, [])))

    def test_routing_covers_all_report_types(self):
        # no crash and full assignment for every report type
        pts = ca.parse_brief("指标达成95%\n存在交付问题\n下季度行动计划\n背景概述")
        for rt in EIGHT:
            bucket = ca.assign_points(rt, pts)
            self.assertEqual(sum(len(v) for v in bucket.values()), len(pts))


class TestQualityGate(unittest.TestCase):
    def test_placeholder_detected(self):
        deck = reports.build_skeleton("weekly")
        r = ca.check_content(deck)
        self.assertFalse(r["ok"])
        self.assertTrue(any(e["code"] == "PLACEHOLDER_LEFT" for e in r["errors"]))

    def test_missing_source_on_chart(self):
        deck = {"slides": [{"template": "chart_insight",
                            "data": {"title": "收入连续三季度保持增长态势",
                                     "chart": {}, "insight": "x",
                                     "kpi": {}, "source": ""}}]}
        r = ca.check_content(deck)
        self.assertTrue(any(e["code"] == "MISSING_SOURCE" for e in r["errors"]))

    def test_cliche_warning(self):
        deck = {"slides": [{"template": "three_cards",
                            "data": {"title": "三大核心抓手驱动业务持续增长兑现",
                                     "cards": [{"title": "客户运营",
                                                "body": "通过分层运营提升留存率至92%"}]}}]}
        r = ca.check_content(deck)
        self.assertTrue(any(w["code"] == "CLICHE" for w in r["warnings"]))

    def test_weak_claim_warning(self):
        deck = {"slides": [{"template": "three_cards",
                            "data": {"title": "三项举措改善了客户的整体留存表现",
                                     "cards": [{"title": "服务升级",
                                                "body": "显著提升了客户满意度和忠诚度"}]}}]}
        r = ca.check_content(deck)
        self.assertTrue(any(w["code"] == "WEAK_CLAIM" for w in r["warnings"]))

    def test_action_title_warning(self):
        deck = {"slides": [{"template": "three_cards",
                            "data": {"title": "经营情况", "cards": []}}]}
        r = ca.check_content(deck)
        self.assertTrue(any(w["code"] == "ACTION_TITLE" for w in r["warnings"]))

    def test_clean_deck_passes(self):
        deck = {"slides": [
            {"template": "cover", "data": {"title": "2026 Q3 经营分析报告"}},
            {"template": "chart_insight", "data": {
                "title": "收入连续三个季度保持两位数增长",
                "chart": {}, "insight": "结构性升级带动毛利改善",
                "kpi": {}, "source": "公司财务系统，2026Q3"}},
            {"template": "three_cards", "data": {
                "title": "三项举措推动客户留存率提升至92%",
                "cards": [{"title": "分层运营",
                           "body": "按价值分层后高价值客户续约率提升8个百分点至95%"}]}},
        ]}
        r = ca.check_content(deck)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["errors"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
