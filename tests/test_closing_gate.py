"""Tests for the deck-level closing-consistency gate (warning-level).

Two cross-slide, layout-agnostic checks mirror the final QA pass before a deck
ships: explicit footer page numbers must match the real slide order, and
on-stage text must not still carry TODO/placeholder/template-variable markers
or a stray hex color. Both are warnings, so they never block a valid build and
the existing test baseline stays green.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import layout, lint  # noqa: E402

NAVY = "#061F32"


def lint_deck(slides):
    deck = {"theme": "consulting", "composed": False, "slides": slides}
    layout.layout_deck(deck)
    return lint.lint_deck(deck)


def freeform_slide(text=None, footer=None):
    children = []
    if text is not None:
        children.append({"t": "text", "rect": [100, 120, 600, 60],
                         "text": text, "size": 24, "color": NAVY,
                         "on": "#FFFFFF"})
    slide = {"type": "content", "composition": "freeform", "tone": "light",
             "children": children}
    if footer is not None:
        slide["footer"] = footer
    return slide


def codes(res):
    return [w["code"] for w in res["warnings"]]


class TestPageNumber(unittest.TestCase):
    def test_matching_page_numbers_are_quiet(self):
        res = lint_deck([
            freeform_slide("第一页", footer={"page": "1"}),
            freeform_slide("第二页", footer={"page": "02 / 02"}),
            freeform_slide("第三页", footer={"page": "第3页"}),
        ])
        self.assertNotIn("PAGE_NUMBER", codes(res))

    def test_wrong_page_number_is_flagged(self):
        # slide 2 footer still says 5 (copied from another deck) -> mismatch
        res = lint_deck([
            freeform_slide("一", footer={"page": "1"}),
            freeform_slide("二", footer={"page": "5"}),
        ])
        hits = [w for w in res["warnings"] if w["code"] == "PAGE_NUMBER"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["slide"], 2)
        self.assertTrue(res["ok"])  # warning never blocks

    def test_empty_or_absent_page_is_not_flagged(self):
        res = lint_deck([
            freeform_slide("无页码"),
            freeform_slide("空页码", footer={"page": "  "}),
            freeform_slide("仅来源", footer={"source": "来源：内部资料"}),
        ])
        self.assertNotIn("PAGE_NUMBER", codes(res))


class TestPlaceholderText(unittest.TestCase):
    def test_todo_and_template_variables_are_flagged(self):
        res = lint_deck([
            freeform_slide("这里还有 TODO 待处理"),
            freeform_slide("变量 {{client_name}} 未替换"),
        ])
        self.assertEqual(codes(res).count("PLACEHOLDER_TEXT"), 2)

    def test_chinese_placeholders_and_hex_leak_are_flagged(self):
        res = lint_deck([
            freeform_slide("本页内容待补充"),
            freeform_slide("强调色用 #08A6F6 这个值"),
        ])
        self.assertEqual(codes(res).count("PLACEHOLDER_TEXT"), 2)

    def test_clean_prose_is_quiet(self):
        res = lint_deck([
            freeform_slide("资源有限时，分配规则决定协作效率。"),
            freeform_slide("结论：用明确规范替代临场博弈。"),
        ])
        self.assertNotIn("PLACEHOLDER_TEXT", codes(res))

    def test_decorative_signature_text_is_exempt(self):
        # the composed chrome marks its page signature decor=True; even if it
        # carried template-like glyphs it must not be scanned as body prose
        deck = {"theme": "consulting", "composed": False, "slides": [{
            "type": "content", "composition": "freeform", "tone": "light",
            "children": [
                {"t": "text", "rect": [100, 640, 300, 24],
                 "text": "01 / 09 {{signature}}", "size": 14,
                 "color": "#9AA5B1", "decor": True},
            ]}]}
        layout.layout_deck(deck)
        res = lint.lint_deck(deck)
        self.assertNotIn("PLACEHOLDER_TEXT", codes(res))

    def test_richcard_and_kpi_strings_are_scanned(self):
        deck = {"theme": "consulting", "composed": False, "slides": [{
            "type": "content", "composition": "freeform", "tone": "light",
            "children": [
                {"t": "kpi", "rect": [100, 120, 300, 140], "value": "88%",
                 "label": "TODO 覆盖率", "color": NAVY, "on": "#FFFFFF"},
                {"t": "richcard", "rect": [100, 300, 500, 200],
                 "fill": "#FFFFFF", "blocks": [
                     {"text": "正常卡片正文内容", "size": 18, "color": NAVY}]},
            ]}]}
        layout.layout_deck(deck)
        res = lint.lint_deck(deck)
        self.assertIn("PLACEHOLDER_TEXT", codes(res))


if __name__ == "__main__":
    unittest.main()
