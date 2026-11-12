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
from engine.design_audit import (  # noqa: E402
    _slides_of,
    _text_boxes,
    audit_design,
)

from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.util import Emu as E  # noqa: E402
from pptx.util import Pt  # noqa: E402

PS = 9525  # EMU per px


def _e(px):
    """像素 → EMU。

    注意：`pptx.util.Emu` 不是换算函数，它只是 int 的子类。`Emu(1280)` 会
    原样当成 1280 EMU 传给 slide_width，然后抛
    「value must be in range(914400, 51206400)」。必须先乘 PS 再包。
    """
    return E(int(round(px * PS)))


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


class TestLineSpacingComesFromTheFile(unittest.TestCase):
    """判据的行高必须读文件里真实的 line_spacing，不能用固定系数。

    实测（20261113，《人情与面子》p03）：主题 magazine 写的是 1.32，判据原
    写死 1.28。两行 13.5pt 正文估算 46.07px、实际 47.51px —— 差 1.4px，
    正好让「正文底边 559.5 咬进批注块顶边 558」这件事以 oy=+0.1 逃过判据，
    渲染图里那行字的下沿被切掉。判据和渲染器用两套行高口径，等于自说自话。
    """

    def _pptx_with(self, spacing):
        prs = Presentation()
        prs.slide_width, prs.slide_height = _e(1280), _e(720)
        s = prs.slides.add_slide(prs.slide_layouts[6])
        # 一块正文，强制折两行
        tb = s.shapes.add_textbox(_e(100), _e(100), _e(400), _e(40))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.line_spacing = spacing
        r = p.add_run()
        r.text = "一二三四五六七八九十一二三四五六七八九十" * 2
        r.font.size = Pt(13.5)
        out = _tmp("sp.pptx")
        prs.save(out)
        return out

    def test_taller_spacing_yields_taller_box(self):
        tight = _text_boxes(_slides_of(self._pptx_with(1.28))[0])[0]["h"]
        loose = _text_boxes(_slides_of(self._pptx_with(1.60))[0])[0]["h"]
        self.assertGreater(loose, tight + 1.0,
                           "行距变大而判据算出的高度没变，说明它没用文件里的值")

    def test_missing_spacing_still_measures(self):
        """文件没写行距时要能算出高度，不能崩。"""
        h = _text_boxes(_slides_of(self._pptx_with(None))[0])[0]["h"]
        self.assertGreater(h, 20)


class TestSmallContainerStillChecked(unittest.TestCase):
    """容器的尺寸门槛不能高到把真正的容器筛掉。

    实测：批注块 558×72 被原来的 h>=90 排除，而它恰好是文字溢出的那一块。
    72px 高完全托得住三行 16pt 文字，是标准容器尺寸，不是装饰。
    """

    def _deck(self, block_h, text):
        prs = Presentation()
        prs.slide_width, prs.slide_height = _e(1280), _e(720)
        s = prs.slides.add_slide(prs.slide_layouts[6])
        # 只留这一块，不铺全幅背景。
        # 铺了背景就等于给判据递了一个 1280×720 的大容器，文字必然也算在它名下，
        # 于是「批注块被门槛筛掉」这件事会被背景兜住，测试就失去了隔离性。
        blk = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, _e(100), _e(300),
                                 _e(558), _e(block_h))
        blk.fill.solid(); blk.fill.fore_color.rgb = RGBColor(0xE7, 0xD8, 0xC9)
        tb = s.shapes.add_textbox(_e(116), _e(310), _e(526), _e(40))
        tb.text_frame.word_wrap = True
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = text
        r.font.size = Pt(16)
        out = _tmp("c.pptx")
        prs.save(out)
        return out

    def test_72px_block_is_still_a_container(self):
        """72px 高的批注块里塞 6 行字，必须报溢出。"""
        path = self._deck(72, "很长的一段批注文字，" * 20)
        probs = audit_design(path)["overflows"]
        self.assertTrue(probs, "72px 高的容器被跳过了，溢出查不出来")

    def test_roomy_block_passes(self):
        path = self._deck(300, "短批注。")
        self.assertEqual(audit_design(path)["overflows"], [])


if __name__ == "__main__":
    unittest.main()
