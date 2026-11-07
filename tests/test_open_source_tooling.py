"""Tests for the open-source tooling layer: pure CLI, typography, editing,
patching, benchmark, installer. No network, no external services.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import (brief_fill, content_ai, deck_patch, lint, reports,  # noqa: E402
                    typography)
from engine import cli, pptx_edit  # noqa: E402
from tools import benchmark, render_check  # noqa: E402


class TestBriefFill(unittest.TestCase):
    BRIEF = "Q3 收入 1.86 亿，同比增长 12%；毛利率 31.5%；客户满意度 92%；" \
            "成本结构出现异常；下周推进 A/B 测试与渠道复盘"

    def test_all_report_types_have_no_placeholder(self):
        for key, _ in reports.list_types():
            spec = brief_fill.build_from_brief(key, self.BRIEF)
            with self.subTest(report=key):
                self.assertNotIn(reports.PLACEHOLDER,
                                 json.dumps(spec, ensure_ascii=False))
                self.assertTrue(spec["slides"])

    def test_content_gate_passes_for_every_type(self):
        for key, _ in reports.list_types():
            spec = brief_fill.build_from_brief(key, self.BRIEF)
            with self.subTest(report=key):
                self.assertEqual(content_ai.check_content(spec)["errors"], [])

    def test_all_types_pass_layout_lint(self):
        for key, _ in reports.list_types():
            spec = brief_fill.build_from_brief(key, self.BRIEF)
            deck = cli.prepare(spec)
            with self.subTest(report=key):
                result = lint.lint_deck(deck)
                self.assertTrue(result["ok"], result["errors"])

    def test_no_invented_numbers(self):
        spec = brief_fill.build_from_brief("business", "营收 12 万；成本 8 万")
        chart = next(s["data"]["chart"] for s in spec["slides"]
                     if s["template"] == "chart_insight")
        vals = chart["series"][0]["values"]
        # every value is either a number from the brief or the explicit
        # "not supplied" zero marker; nothing is fabricated
        self.assertTrue(all(v in (12.0, 8.0, 0.0) for v in vals), vals)
        self.assertEqual(len(vals), 4)

    def test_empty_brief_still_builds(self):
        spec = brief_fill.build_from_brief("weekly", "")
        deck = cli.prepare(spec)
        self.assertTrue(lint.lint_deck(deck)["ok"])

    def test_cli_brief_metadata_marks_no_llm(self):
        spec = brief_fill.build_from_brief("weekly", "一条要点")
        self.assertTrue(spec["_cli_brief"]["no_llm"])
        self.assertEqual(spec["_cli_brief"]["generated_by"], "cli.make")
        self.assertIn("kinsoku", typography.metadata())


class TestTypography(unittest.TestCase):
    def test_no_start_hangs_onto_previous_line(self):
        out = typography.apply_kinsoku(["这是一段话", "。下一句"])
        self.assertEqual(out, ["这是一段话。", "下一句"])

    def test_no_end_moves_to_next_line(self):
        out = typography.apply_kinsoku(["他说：“", "这是一句完整的话。”"])
        self.assertEqual(typography.find_kinsoku_violations(out), [])
        self.assertEqual(out[1][0], "“")
        self.assertNotEqual(out[0][-1:], "“")

    def test_atomic_pairs_are_not_split(self):
        for a, b in [("破折号—", "—后接下半句"), ("省略号…", "…后接下半句")]:
            out = typography.apply_kinsoku([a, b])
            self.assertEqual(out[0][-2:], a[-1] + b[0])
            self.assertEqual(typography.find_kinsoku_violations(out), [])

    def test_single_glyph_decoration_is_exempt(self):
        self.assertEqual(typography.apply_kinsoku(["“"]), ["“"])
        self.assertEqual(typography.find_kinsoku_violations(["“"]), [])

    def test_violation_detector_works(self):
        self.assertTrue(typography.find_kinsoku_violations(["正", "。错误"]))

    def test_latin_cjk_spacing_and_font_stack(self):
        self.assertEqual(typography.latin_cjk_spacing("Q3收入12%"),
                         "Q3\u2009收入\u200912%")
        stack = typography.font_stack("sans", "PingFang SC")
        self.assertEqual(stack[0], "PingFang SC")
        self.assertEqual(len(stack), len(set(stack)))


class TestDeckPatch(unittest.TestCase):
    def test_set_nested_path(self):
        doc = {"slides": [{"data": {"title": "old"}}]}
        deck_patch.set_path(doc, "slides.0.data.title", "new")
        self.assertEqual(doc["slides"][0]["data"]["title"], "new")

    def test_parse_value(self):
        self.assertEqual(deck_patch.parse_value("5"), 5)
        self.assertEqual(deck_patch.parse_value("true"), True)
        self.assertEqual(deck_patch.parse_value("文本"), "文本")

    def test_bad_path_raises(self):
        with self.assertRaises(KeyError):
            deck_patch.set_path({"slides": []}, "slides.9.title", "x")
        with self.assertRaises(KeyError):
            deck_patch.set_path({"a": {}}, "a.missing.x", "x")

    def test_patch_build_is_gated_by_lint(self):
        with tempfile.TemporaryDirectory() as td:
            spec = cli.load(os.path.join(ROOT, "examples",
                                        "deck_notes_composed.json"))
            deck_patch.set_path(spec, "slides.2.children.3.size", 5)
            deck = cli.prepare(spec)
            result = lint.lint_deck(deck)
            self.assertFalse(result["ok"])
            self.assertIn("FONT_SIZE", {e["code"] for e in result["errors"]})


class TestPptxEdit(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.td.name, "src.pptx")
        from engine.compiler import build_pptx
        build_pptx(cli.prepare(cli.load(
            os.path.join(ROOT, "examples", "demo.json"))), self.src)

    def tearDown(self):
        self.td.cleanup()

    def test_inspect_structure(self):
        rep = pptx_edit.inspect(self.src)
        self.assertGreater(rep["slide_count"], 0)
        self.assertEqual(rep["canvas_px"], [1280.0, 720.0])
        self.assertTrue(any(s["shapes"] for s in rep["slides"]))

    def test_retext_keeps_formatting_and_shape_count(self):
        rep = pptx_edit.inspect(self.src)
        target = next((s["slide"], sh) for s in rep["slides"]
                      for sh in s["shapes"]
                      if sh.get("has_text_frame") and sh.get("text", "").strip()
                      and sh.get("runs"))
        slide, sh = target
        out = os.path.join(self.td.name, "out.pptx")
        result = pptx_edit.retext(self.src, [
            {"slide": slide, "shape_id": sh["id"], "text": "替换后的文字"}], out)
        self.assertEqual(result["applied"], 1)
        self.assertEqual(result["missed"], [])
        after = pptx_edit.inspect(out)
        self.assertEqual(after["slide_count"], rep["slide_count"])
        self.assertEqual(sum(s["shape_count"] for s in after["slides"]),
                         sum(s["shape_count"] for s in rep["slides"]))
        new_sh = next(x for s in after["slides"] if s["slide"] == slide
                      for x in s["shapes"] if x["id"] == sh["id"])
        self.assertEqual(new_sh["text"], "替换后的文字")
        self.assertEqual(new_sh["runs"][0]["name"], sh["runs"][0]["name"])
        self.assertEqual(new_sh["runs"][0]["size_pt"], sh["runs"][0]["size_pt"])

    def test_missing_shape_is_reported(self):
        out = os.path.join(self.td.name, "miss.pptx")
        result = pptx_edit.retext(self.src, [
            {"slide": 1, "shape": "不存在的形状", "text": "x"}], out)
        self.assertEqual(result["applied"], 0)
        self.assertEqual(len(result["missed"]), 1)


class TestBenchmarkAndInstaller(unittest.TestCase):
    def test_offline_static_scan(self):
        off = benchmark.offline_readiness()
        self.assertEqual(off["core_pipeline_network_hits"], 0)
        self.assertEqual(len(off["runtime_dependencies"]), 3)

    def test_shape_stats_on_example(self):
        p = os.path.join(ROOT, "examples",
                         "FreePPT_读书笔记_创作编排示例.pptx")
        stats = benchmark.shape_stats(p)
        self.assertEqual(stats["slides"], 9)
        self.assertGreater(stats["editable_ratio"], 0.9)
        self.assertLessEqual(stats["editable_ratio"], 1.0)

    def test_render_check_tool_is_importable(self):
        soffice = render_check.find_soffice()
        self.assertTrue(soffice is None or isinstance(soffice, str))

    def test_installer_dry_run_covers_five_hosts(self):
        out = subprocess.run(
            [os.path.join(ROOT, "install.sh"), "--host", "all",
             "--scope", "user", "--dry-run"],
            capture_output=True, text=True, check=True).stdout
        for host in ("workbuddy", "claude", "codex", "cursor", "dsh"):
            self.assertIn(f"[{host}]", out)
        self.assertIn("DRY-RUN", out)

    def test_installer_accepts_refresh_cache_in_dry_run(self):
        out = subprocess.run(
            [os.path.join(ROOT, "install.sh"), "--host", "workbuddy",
             "--scope", "user", "--refresh-cache", "--dry-run"],
            capture_output=True, text=True, check=True).stdout
        self.assertIn("DRY-RUN", out)
        self.assertIn("workbuddy", out)

    def test_license_files_exist(self):
        with open(os.path.join(ROOT, "LICENSE"), encoding="utf-8") as f:
            mit = f.read()
        with open(os.path.join(ROOT, "LICENSE-DOCS"), encoding="utf-8") as f:
            cc = f.read()
        self.assertIn("MIT License", mit)
        self.assertIn("张三峯", mit)
        self.assertIn("CC BY 4.0", cc)


if __name__ == "__main__":
    unittest.main()
