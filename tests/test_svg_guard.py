#!/usr/bin/env python3
"""单元测试：engine.svg_guard（WCAG / 分流 / 容量 / 事实来源）。"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import svg_guard as G


def make_svg(body, lang="zh-CN"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" lang="{lang}" '
            f'width="1280" height="720" viewBox="0 0 1280 720">'
            f'<defs></defs>{body}</svg>')


class TestWCAG(unittest.TestCase):
    def test_parse_color_hex(self):
        self.assertEqual(G.parse_color("#FFFFFF"), (255, 255, 255))
        self.assertEqual(G.parse_color("#000"), (0, 0, 0))
        self.assertIsNone(G.parse_color("rgb(1,2,3)"))

    def test_contrast_extremes(self):
        w, b = (255, 255, 255), (0, 0, 0)
        self.assertAlmostEqual(G.contrast(w, b), 21, places=1)
        self.assertEqual(G.contrast(w, w), 1)

    def test_muted_gray_passes_on_paper(self):
        paper = G.parse_color("#F4F7FB")
        self.assertGreaterEqual(G.contrast(G.parse_color("#5D6B80"), paper), 4.5)


class TestContains(unittest.TestCase):
    def test_basic(self):
        box = (10, 20, 100, 50)
        self.assertTrue(G.contains(box, 50, 40))
        self.assertFalse(G.contains(box, 5, 40))
        self.assertFalse(G.contains(box, 50, 5))
        self.assertFalse(G.contains(box, 50, 80))


class TestCheckPage(unittest.TestCase):
    def _write(self, tmp, name, svg, spec=None):
        d = Path(tmp)
        out = d / "svg_output"
        out.mkdir(exist_ok=True)
        p = out / f"{name}.svg"
        p.write_text(svg, encoding="utf-8")
        return p

    def test_contrast_body_blocker(self):
        # 浅灰文字在纸面上，正文级（20px）→ blocker
        svg = make_svg(
            '<text x="64" y="100" font-size="20" fill="#94A3B8">一些正文内容</text>')
        with tempfile.TemporaryDirectory() as t:
            p = self._write(t, "01", svg, )
            f, a, ns, nt = G.check_page({"density_hint": "mid", "capacity": 3}, p)
        self.assertTrue(any(x["code"] == "CONTRAST" for x in f))

    def test_decorative_number_is_advisory(self):
        # 卡片角落淡编号（20px，纯数字）→ advisory，不是 blocker
        svg = make_svg(
            '<text x="300" y="300" font-size="15" fill="#B6C6D6">01</text>')
        with tempfile.TemporaryDirectory() as t:
            p = self._write(t, "01", svg)
            f, a, ns, nt = G.check_page({"density_hint": "mid"}, p)
        self.assertEqual(f, [])
        self.assertTrue(any(x["code"] == "CONTRAST_DECOR" for x in a))

    def test_photo_text_is_advisory(self):
        svg = make_svg(
            '<image x="0" y="0" width="1280" height="720" href="../images/x.png"/>'
            '<text x="100" y="200" font-size="20" fill="#FFFFFF">照片上的标题</text>')
        with tempfile.TemporaryDirectory() as t:
            p = self._write(t, "01", svg)
            f, a, ns, nt = G.check_page({"density_hint": "airy"}, p)
        self.assertEqual(f, [])
        self.assertTrue(any(x["code"] == "CONTRAST_PHOTO" for x in a))

    def test_footer_not_flagged(self):
        svg = make_svg(
            '<text x="64" y="680" font-size="13" fill="#5D6B80">Source：某书</text>'
            '<text x="1100" y="680" font-size="13" fill="#5D6B80">P4 / 91</text>')
        with tempfile.TemporaryDirectory() as t:
            p = self._write(t, "01", svg)
            f, a, ns, nt = G.check_page({"density_hint": "mid"}, p)
        self.assertEqual(f, [])

    def test_capacity_and_sources(self):
        spec = {"capacity": 2, "density_hint": "mid",
                "points": [{"head": "a", "body": ""},
                          {"head": "b", "body": ""},
                          {"head": "c", "body": ""}]}
        svg = make_svg('<text x="64" y="100" font-size="20" fill="#0F1B2D">'
                       '数字 50 的论断</text>')
        with tempfile.TemporaryDirectory() as t:
            p = self._write(t, "01", svg)
            f, a, ns, nt = G.check_page(spec, p)
        codes = [x["code"] for x in f]
        self.assertIn("CAPACITY", codes)
        self.assertIn("FACT_UNSOURCED", codes)


if __name__ == "__main__":
    unittest.main()
