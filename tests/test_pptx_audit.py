"""audit-pptx 的判据测试：只读坐标，不看 DSL。

重点保护两件事：
1. 绕开 compose() 手写的 pptx 必须能被抓住（这是历史上真实漏掉的形态）。
2. 正常产物不能被误伤（false positive 会让整条闸门被关掉）。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import pptx_audit  # noqa: E402


def _shape(x, y, w, h, text="", stype="TEXT_BOX (17)"):
    return {"type": stype, "rect_px": [x, y, w, h], "text": text}


def _report(pages, canvas=(1280.0, 720.0)):
    return {
        "slide_count": len(pages),
        "canvas_px": list(canvas),
        "slides": [{"slide": i + 1, "shapes": p} for i, p in enumerate(pages)],
    }


# 内容页：文字足够多，不会被当成仪式页
def _content_page(tag):
    return [
        _shape(60, 86, 1080, 44, f"第 {tag} 页标题，讲一件具体的事"),
        _shape(104, 190, 200, 24, f"标签{tag}"),
        _shape(340, 190, 860, 60, "这是说明文字，长度超过仪式页的文字总量阈值，"
                                  "因此这一页会被当成真正的内容页来判定。"),
        _shape(60, 300, 520, 120, "左下要点，内容各不相同"),
        _shape(620, 300, 520, 120, "右下要点，内容各不相同"),
    ]


class TestHandwrittenDeckCaught(unittest.TestCase):
    """绕开 DSL、手写坐标生成的同构 deck 必须被判不通过。"""

    def test_twelve_identical_pages_rejected(self):
        rep = _report([_content_page(i) for i in range(12)])
        res = pptx_audit.audit_pptx(rep, max_pages=5)
        self.assertFalse(res["ok"], "12 页坐标完全一样必须判不通过")
        self.assertTrue(res["groups"])
        self.assertEqual(res["groups"][0]["count"], 12)

    def test_labels_do_not_save_it(self):
        """给每页起不同名字不能改变判定——这里根本没有名字可读。"""
        pages = []
        for i in range(12):
            p = _content_page(i)
            # 名字写进名字字段也没用，判据只看 rect_px
            for sh in p:
                sh["name"] = f"完全不同的版式名-{i}"
            pages.append(p)
        res = pptx_audit.audit_pptx(_report(pages), max_pages=5)
        self.assertFalse(res["ok"])

    def test_122_page_shape_rejected(self):
        """复刻那套 122 页产物的规模，确认不会因为页数多而失效。"""
        rep = _report([_content_page(i) for i in range(122)])
        res = pptx_audit.audit_pptx(rep, max_pages=5)
        self.assertFalse(res["ok"])
        self.assertEqual(res["slide_count"], 122)
        self.assertGreaterEqual(res["groups"][0]["count"], 100)


class TestNormalDeckNotHarmned(unittest.TestCase):
    """正常产物不能被误伤。"""

    def test_distinct_layouts_pass(self):
        pages = [
            _content_page(0),
            [_shape(60, 86, 1080, 44, "另一页标题，位置相同但结构不同"),
             _shape(60, 200, 1180, 400, "左右通栏，一整块内容，和上一页结构不同")],
            [_shape(60, 86, 1080, 44, "第三页"),
             _shape(60, 200, 560, 400, "左块"),
             _shape(660, 200, 560, 400, "右块")],
            [_shape(200, 86, 880, 44, "居中标题，起点不同"),
             _shape(200, 300, 880, 300, "居中内容块")],
        ]
        res = pptx_audit.audit_pptx(_report(pages), max_pages=5)
        self.assertTrue(res["ok"], f"误伤了：{res['groups']}")

    def test_group_below_threshold_passes(self):
        """4 页同构是可以的（实测正常产物最大一组就是 4 页）。"""
        pages = [_content_page(i) for i in range(4)]
        res = pptx_audit.audit_pptx(_report(pages), max_pages=5)
        self.assertTrue(res["ok"])

    def test_five_pages_is_the_line(self):
        """阈值 5 的意思是「达到 5 页就报」，4 页放过、5 页拦下。"""
        four = _report([_content_page(i) for i in range(4)])
        five = _report([_content_page(i) for i in range(5)])
        self.assertTrue(pptx_audit.audit_pptx(four, max_pages=5)["ok"])
        self.assertFalse(pptx_audit.audit_pptx(five, max_pages=5)["ok"])


class TestRitualExemption(unittest.TestCase):
    """封面 / 章节页长得像是对的，不能被算成套模板。"""

    def test_low_text_pages_exempted(self):
        cover = [_shape(400, 300, 480, 60, "书名")]
        chapters = [[_shape(400, 320, 480, 40, "第一章")] for _ in range(10)]
        rep = _report([cover] + chapters)
        res = pptx_audit.audit_pptx(rep, max_pages=5)
        self.assertTrue(res["ok"], f"仪式页被误判：{res['groups']}")
        self.assertGreaterEqual(len(res["exempted"]), 10)

    def test_content_pages_not_exempted(self):
        """文字多的页不能靠「像仪式页」溜过去。"""
        res = pptx_audit.audit_pptx(
            _report([_content_page(i) for i in range(8)]), max_pages=5)
        self.assertFalse(res["ok"])
        self.assertEqual(res["exempted"], [])


class TestReportHonesty(unittest.TestCase):
    """报告必须如实反映覆盖范围，不能静默丢证据。"""

    def test_unreadable_shapes_counted(self):
        pages = [_content_page(i) for i in range(6)]
        pages[0].append({"type": "TEXT_BOX (17)", "rect_px": None})
        res = pptx_audit.audit_pptx(_report(pages), max_pages=5)
        self.assertEqual(res["unreadable"], 1)

    def test_empty_deck_passes_without_crash(self):
        res = pptx_audit.audit_pptx(_report([]), max_pages=5)
        self.assertTrue(res["ok"])
        self.assertEqual(res["slide_count"], 0)


if __name__ == "__main__":
    unittest.main()
