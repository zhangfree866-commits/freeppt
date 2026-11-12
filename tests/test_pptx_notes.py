"""audit-notes / fill-notes 的判据测试：只读成品 pptx，不看 DSL。

重点保护四件事：
1. 绕开 compose() 手写的 pptx 备注 0/91 必须被抓住（历史上真实漏掉的形态）。
2. 档位是按 deck 自身均长推出来的，不是一刀切 40 字——随笔档的短注不能被判过薄。
3. 回填只重组页内文字，不许出现页面外的事实；且必须幂等、确定性。
4. 仪式页（封面/章节/封底）豁免，正常产物不能误伤。

测试全部用 python-pptx 现造 deck，不依赖任何外部样本文件。
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import pptx_notes, pptx_notes_fill  # noqa: E402


def _make_deck(path, pages, notes=None):
    """造一份 pptx。pages 是每页的文字块列表；notes 是每页备注（可用 None）。"""
    from pptx import Presentation
    from pptx.util import Emu

    prs = Presentation()
    prs.slide_width = Emu(12192000)   # 13.333in = 1280px
    prs.slide_height = Emu(6858000)   # 7.5in    = 720px
    blank = prs.slide_layouts[6]

    for i, blocks in enumerate(pages):
        s = prs.slides.add_slide(blank)
        top = 300000
        for j, text in enumerate(blocks):
            box = s.shapes.add_textbox(Emu(400000), Emu(top + j * 700000),
                                       Emu(9000000), Emu(600000))
            box.text_frame.text = text
        if notes and i < len(notes) and notes[i]:
            s.notes_slide.notes_text_frame.text = notes[i]

    prs.save(path)
    return path


# 内容页：文字足够多，不会被当成仪式页
def _content_blocks(tag):
    return [
        f"第 {tag} 页标题",
        "这是正文说明，讲清一件事的来龙去脉，长度远超仪式页的文字总量阈值，"
        "所以这一页会被当成真正的内容页来判定。",
    ]


class TestMissingNotesCaught(unittest.TestCase):
    """备注全空的 deck 必须被判不通过——这是 0/91 那个真实事故的复现。"""

    def test_empty_notes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _make_deck(os.path.join(d, "a.pptx"),
                           [_content_blocks(i) for i in range(6)])
            r = pptx_notes.audit_notes(p)
        self.assertFalse(r["ok"])
        self.assertEqual(r["covered"], 0)
        self.assertEqual(len(r["missing_pages"]), 6)

    def test_full_coverage_passes(self):
        note = "这是一段足够长的讲稿，用来通过研究档的下限判定，让整本 deck 落在" \
               "可以被接受的位置上，不至于因为太短被判过薄。"
        with tempfile.TemporaryDirectory() as d:
            p = _make_deck(os.path.join(d, "a.pptx"),
                           [_content_blocks(i) for i in range(6)],
                           notes=[note] * 6)
            r = pptx_notes.audit_notes(p)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["coverage"], 1.0)

    def test_whitespace_only_note_counts_as_missing(self):
        """只写空格的备注等于没写，不能算覆盖。"""
        with tempfile.TemporaryDirectory() as d:
            p = _make_deck(os.path.join(d, "a.pptx"),
                           [_content_blocks(i) for i in range(6)],
                           notes=["   \n  "] * 6)
            r = pptx_notes.audit_notes(p)
        self.assertEqual(r["covered"], 0)
        self.assertFalse(r["ok"])


class TestTierNotFlatCutoff(unittest.TestCase):
    """档位由 deck 自身均长推断，不能一刀切。"""

    def test_tier_thresholds(self):
        self.assertEqual(pptx_notes._tier_of(30), "essay")
        self.assertEqual(pptx_notes._tier_of(70), "essay")
        self.assertEqual(pptx_notes._tier_of(120), "standard")
        self.assertEqual(pptx_notes._tier_of(180), "research")
        self.assertEqual(pptx_notes._tier_of(260), "research")

    def test_essay_deck_with_short_notes_passes(self):
        """随笔档：20 字短注成立。若用统一的 40 字线会被误判过薄。"""
        note = "这一页只讲一个判断，短一点就够。"
        self.assertLess(len(note), 40)
        with tempfile.TemporaryDirectory() as d:
            p = _make_deck(os.path.join(d, "a.pptx"),
                           [_content_blocks(i) for i in range(6)],
                           notes=[note] * 6)
            r = pptx_notes.audit_notes(p)
        self.assertEqual(r["tier"], "essay")
        self.assertTrue(r["ok"], r)

    def test_research_deck_with_short_note_is_thin(self):
        """研究档：均长 210（≥180），其中夹一页 60 字要判过薄（下限 80）。"""
        long_note = "长" * 240
        short_note = "短" * 60
        notes = [long_note] * 5 + [short_note]
        with tempfile.TemporaryDirectory() as d:
            p = _make_deck(os.path.join(d, "a.pptx"),
                           [_content_blocks(i) for i in range(6)], notes=notes)
            r = pptx_notes.audit_notes(p)
        self.assertEqual(r["tier"], "research")
        self.assertFalse(r["ok"])
        self.assertEqual([t["page"] for t in r["thin_pages"]], [6])


class TestRitualExempt(unittest.TestCase):
    """封面/章节/封底文字极少，没备注不算缺陷。"""

    def test_sparse_page_exempted(self):
        pages = [_content_blocks(i) for i in range(5)]
        pages.insert(0, ["封面"])          # 文字极少 → 豁免
        notes = [None] + ["讲稿" * 40] * 5
        with tempfile.TemporaryDirectory() as d:
            p = _make_deck(os.path.join(d, "a.pptx"), pages, notes=notes)
            r = pptx_notes.audit_notes(p)
        self.assertIn(1, r["exempted"])
        self.assertNotIn(1, r["missing_pages"])
        self.assertEqual(r["judged_slides"], 5)
        self.assertTrue(r["ok"], r)

    def test_content_page_not_exempt(self):
        """文字多的页不能借豁免逃掉。"""
        pages = [_content_blocks(i) for i in range(6)]
        with tempfile.TemporaryDirectory() as d:
            p = _make_deck(os.path.join(d, "a.pptx"), pages)
            r = pptx_notes.audit_notes(p)
        self.assertEqual(r["exempted"], [])
        self.assertEqual(len(r["missing_pages"]), 6)


class TestFillNotes(unittest.TestCase):
    """回填：只重组页内文字、幂等、确定性。"""

    def _deck(self, d):
        return _make_deck(os.path.join(d, "a.pptx"),
                          [_content_blocks(i) for i in range(5)])

    def test_fill_closes_the_gap(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._deck(d)
            out = os.path.join(d, "out.pptx")
            pptx_notes_fill.fill_notes(src, out_path=out)
            before = pptx_notes.audit_notes(src)
            after = pptx_notes.audit_notes(out)
        self.assertEqual(before["covered"], 0)
        self.assertEqual(after["coverage"], 1.0)
        self.assertTrue(after["ok"], after)

    def test_idempotent_by_default(self):
        """已有备注的页不覆盖，二次运行应 0 回填。"""
        with tempfile.TemporaryDirectory() as d:
            src = self._deck(d)
            once = os.path.join(d, "once.pptx")
            twice = os.path.join(d, "twice.pptx")
            pptx_notes_fill.fill_notes(src, out_path=once)
            r = pptx_notes_fill.fill_notes(once, out_path=twice)
            from pptx import Presentation
            a = [s.notes_slide.notes_text_frame.text
                 for s in Presentation(once).slides]
            b = [s.notes_slide.notes_text_frame.text
                 for s in Presentation(twice).slides]
        self.assertEqual(r["filled"], 0)
        self.assertEqual(a, b)

    def test_overwrite_rewrites(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._deck(d)
            out = os.path.join(d, "o.pptx")
            r = pptx_notes_fill.fill_notes(src, out_path=out, overwrite=True)
        self.assertEqual(r["filled"], 5)

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._deck(d)
            a_out = os.path.join(d, "a2.pptx")
            b_out = os.path.join(d, "b2.pptx")
            pptx_notes_fill.fill_notes(src, out_path=a_out)
            pptx_notes_fill.fill_notes(src, out_path=b_out)
            from pptx import Presentation
            a = [s.notes_slide.notes_text_frame.text
                 for s in Presentation(a_out).slides]
            b = [s.notes_slide.notes_text_frame.text
                 for s in Presentation(b_out).slides]
        self.assertEqual(a, b)

    def test_no_invented_facts(self):
        """讲稿里的实词必须来自页面本身，不能凭空冒出来。"""
        with tempfile.TemporaryDirectory() as d:
            src = self._deck(d)
            out = os.path.join(d, "o.pptx")
            pptx_notes_fill.fill_notes(src, out_path=out)
            from pptx import Presentation
            prs = Presentation(out)
            for s in prs.slides:
                note = s.notes_slide.notes_text_frame.text
                page = "".join(sh.text_frame.text for sh in s.shapes
                               if sh.has_text_frame)
                # 剥掉模板化的连接语，剩下的每个正文块都要能在页内找到
                for body in pptx_notes_fill._page_texts(s)[1]:
                    key = "".join(body.split())[:20]
                    self.assertIn(key.replace("…", ""), "".join(page.split()))


class TestNoiseFilter(unittest.TestCase):
    """章编号/页码不是标题，否则讲稿会变成「这一页讲的是 02」。"""

    def test_numbers_are_noise(self):
        for t in ["02", "P26", "p.26", "26 / 91", "MODULE 04 / THE LEAP",
                  "PART TWO", "CHAPTER 3"]:
            self.assertTrue(pptx_notes_fill._is_noise(t), t)

    def test_real_titles_are_not_noise(self):
        for t in ["为什么 CUDA 是一次豪赌", "The Leap", "1993 年的那间餐厅"]:
            self.assertFalse(pptx_notes_fill._is_noise(t), t)

    def test_chapter_page_head_is_not_a_number(self):
        """章节页第一块是 "02" 时，标题要取到真正的小标题。"""
        blocks = ["02", "MODULE 04 / BOUNDARIES", "序章：一家公司的四十年"]
        with tempfile.TemporaryDirectory() as d:
            p = _make_deck(os.path.join(d, "a.pptx"), [blocks])
            from pptx import Presentation
            slide = list(Presentation(p).slides)[0]
            head, _bodies = pptx_notes_fill._page_texts(slide)
        self.assertEqual(head, "序章：一家公司的四十年")


class TestDedup(unittest.TestCase):
    """同一句话被切进多个文本框时，讲稿里不能出现两遍。"""

    def test_mutual_containment(self):
        head = "标题"
        bodies = ["完整的一句话说明", "完整的一句话说明"]
        note = pptx_notes_fill._compose_note(head, bodies, 1, 1)
        self.assertEqual(note.count("完整的一句话说明"), 1)

    def test_prefix_relation(self):
        """半句 + 全句（被不同宽度文本框切断）要去重。"""
        note = pptx_notes_fill._compose_note(
            "标题", ["英伟达在红利之前完成了组织设计", "英伟达在红利之前完成了组织设计，这才是一切的前提"], 1, 1)
        self.assertEqual(note.count("英伟达在红利之前完成了组织设计"), 1)

    def test_blocks_get_terminal_punctuation(self):
        """多块拼接不能连成一串没有停顿的长句。"""
        note = pptx_notes_fill._compose_note("标题", ["第一件事", "第二件事"], 1, 1)
        self.assertIn("第一件事。", note)
        self.assertIn("第二件事。", note)


if __name__ == "__main__":
    unittest.main()
