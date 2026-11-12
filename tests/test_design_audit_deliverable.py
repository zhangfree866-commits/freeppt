# -*- coding: utf-8 -*-
"""成品可读性判据：文字溢出容器、中文字体可用。

这两个判据都来自**肉眼验收时看到的真实缺陷**，而不是想象出来的边界情况：

1. 文字溢出容器 —— 阶梯第 1 级正文的「演。」掉到色块外面、批注块最后一个词
   落在框外、1987 的说明标签压在数字下沿。三者症状不同，根因相同：PowerPoint
   不裁切溢出文字，它会让字悄悄溢出去盖住别的东西。
2. 中文字体 —— 把参照 deck 的 Georgia/Arial 令牌直接搬到中文内容上，形状数、
   结构件、分隔线、压字全部正常，但整页中文是空方框。所有原判据都查不出。

写成独立的 unittest 文件（而不是塞进 test_design_audit.py），是为了让「成品可读性」
这一类判据有自己的名字——它判的不是版面密度，是「打开文件能不能读」。
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import design_audit  # noqa: E402

PS = 9525  # EMU per px


def _tmp(name):
    """在系统临时目录建一个文件路径。

    不用 pytest 的 tmp_path：本机沙箱下 mkdir pytest-of-unknown 会 EEXIST，
    那是环境的 shim 行为，不是被测代码的问题。
    """
    import tempfile
    d = tempfile.mkdtemp()
    return os.path.join(d, name)


def _deck_with_text(text, box_h=120, box_w=300, size=16):
    """一页：一个实心色块 + 一块叠在上面的文字。"""
    from pptx import Presentation
    from pptx.util import Emu, Pt
    from pptx.dml.color import RGBColor

    prs = Presentation()
    prs.slide_width = Emu(int(1280 * PS))
    prs.slide_height = Emu(int(720 * PS))
    s = prs.slides.add_slide(prs.slide_layouts[6])
    box = s.shapes.add_shape(1, Emu(64 * PS), Emu(100 * PS),
                             Emu(box_w * PS), Emu(box_h * PS))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0xE7, 0xD8, 0xC9)
    box.line.fill.background()
    tb = s.shapes.add_textbox(Emu(80 * PS), Emu(110 * PS),
                              Emu((box_w - 32) * PS), Emu(100 * PS))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = text
    for para in tf.paragraphs:
        for r in para.runs:
            r.font.size = Pt(size)
    return prs


class TestTextOverflowsContainer(unittest.TestCase):
    def test_text_that_does_not_fit_is_caught(self):
        prs = _deck_with_text("这一块文字明显比色块能装的多得多。" * 4)
        found = design_audit._text_overflow(list(prs.slides)[0])
        assert found, "文字明显溢出却没被拦下"
        assert found[0]["over_by"] > 10

    def test_text_that_fits_passes(self):
        prs = _deck_with_text("三行以内的短句不会超出这个色块。")
        assert design_audit._text_overflow(list(prs.slides)[0]) == []

    def test_tall_enough_box_passes(self):
        """同样长的文字，给足高度就不算溢出。

        判据判的是「放不下」，不是「字多」。字多但盒子够大是正常设计——
        把密度当缺陷拦，等于逼所有 deck 长成同一副稀疏样子。
        """
        prs = _deck_with_text("这一块文字明显比色块能装的多得多。" * 4,
                              box_h=400)
        assert design_audit._text_overflow(list(prs.slides)[0]) == []


class TestCjkFontUsable(unittest.TestCase):
    @staticmethod
    def _deck_with_ea(ea_font, path):
        from pptx import Presentation
        from pptx.util import Emu, Pt
        from pptx.oxml.ns import qn

        prs = Presentation()
        prs.slide_width = Emu(int(1280 * PS))
        prs.slide_height = Emu(int(720 * PS))
        s = prs.slides.add_slide(prs.slide_layouts[6])
        tb = s.shapes.add_textbox(Emu(64 * PS), Emu(64 * PS),
                                  Emu(900 * PS), Emu(80 * PS))
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = "人情与面子"
        r.font.size = Pt(33)
        r.font.name = ea_font
        rPr = r._r.get_or_add_rPr()
        ea = rPr.makeelement(qn("a:ea"), {})
        ea.set("typeface", ea_font)
        rPr.append(ea)
        prs.save(path)
        return path

    def test_latin_font_on_cjk_run_is_blocked(self):
        path = _tmp("bad.pptx")
        self._deck_with_ea("Arial", path)
        probs = design_audit._cjk_font_problems(path)
        assert probs, "a:ea=Arial 却没被拦下——中文会全部显示成方框"
        assert "Arial" in probs[0]["fonts"]

    def test_cjk_font_passes(self):
        path = _tmp("good.pptx")
        self._deck_with_ea("PingFang SC", path)
        assert design_audit._cjk_font_problems(path) == []

    def test_unknown_font_is_not_judged(self):
        """不认识的名字一律放行。

        判据不该因为「我没见过这个字体」就判死一份正常的 deck——那是最伤
        信誉的一类假阳性，比漏判更糟：没人会再信它。
        """
        path = _tmp("unknown.pptx")
        self._deck_with_ea("Some Brand Font 2026", path)
        assert design_audit._cjk_font_problems(path) == []




class TestSolidBlockCoversText(unittest.TestCase):
    """实心色块压住别人的文字 → 必须拦。

    比「文字压文字」更隐蔽：文字还在文件里，只是被盖住看不见了。实测：
    批注块底边 636 压住 648 处的页码，渲染图里「03 / 09」被吃掉一半，
    而纯文字碰撞判据完全查不出——页码自己没跟谁重叠。
    """

    PS = 9525

    def _deck(self, page_y, block_y, block_h):
        from pptx import Presentation
        from pptx.util import Emu, Pt
        from pptx.dml.color import RGBColor

        prs = Presentation()
        prs.slide_width = Emu(int(1280 * self.PS))
        prs.slide_height = Emu(int(720 * self.PS))
        s = prs.slides.add_slide(prs.slide_layouts[6])
        tb = s.shapes.add_textbox(Emu(1060 * self.PS), Emu(page_y * self.PS),
                                  Emu(160 * self.PS), Emu(25 * self.PS))
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = "03 / 09"
        r.font.size = Pt(14)
        box = s.shapes.add_shape(1, Emu(900 * self.PS), Emu(block_y * self.PS),
                                 Emu(400 * self.PS), Emu(block_h * self.PS))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(0xE7, 0xD8, 0xC9)
        box.line.fill.background()
        # 补足结构件，让「形状太少」不干扰这条测试
        for k in range(8):
            b = s.shapes.add_shape(
                1, Emu((80 + k * 90) * self.PS), Emu(120 * self.PS),
                Emu(70 * self.PS), Emu(60 * self.PS))
            b.fill.solid()
            b.fill.fore_color.rgb = RGBColor(0x9A, 0x34, 0x12)
            b.line.fill.background()
        s.shapes.add_connector(1, Emu(64 * self.PS), Emu(300 * self.PS),
                               Emu(1200 * self.PS), Emu(300 * self.PS))
        fd, path = tempfile.mkstemp(suffix=".pptx")
        os.close(fd)
        prs.save(path)
        return path

    def test_block_covering_page_number_is_caught(self):
        path = self._deck(page_y=648, block_y=560, block_h=100)
        try:
            r = design_audit.audit_design(path)
            assert r["collisions"], "色块压住页码却没被拦下"
        finally:
            os.remove(path)

    def test_block_clear_of_text_passes(self):
        path = self._deck(page_y=648, block_y=380, block_h=120)
        try:
            r = design_audit.audit_design(path)
            assert r["collisions"] == []
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
