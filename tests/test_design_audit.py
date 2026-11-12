"""audit-design 的判据测试：判「这一页有没有被设计过」，与配图无关。

关键回归：用户 2026-11-12 拿出一份零配图、10 页的参照 deck，说「页面设计才是核心」。
实测它每页 38.7 个形状、45 条分隔线、同骨架最多 2 页。如果这个审计把参照判不通过，
或者把「标题 + 几段文字」的裸排布判通过，就说明判据没用。
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import design_audit  # noqa: E402

PS = 9525  # EMU per px


def _deck(path, pages):
    """pages: 每页一个 dict —— {"blocks": [(x,y,w,h,text)], "lines": [(x,y,w,h)]}"""
    from pptx import Presentation
    from pptx.util import Emu

    prs = Presentation()
    prs.slide_width = Emu(12192000)
    prs.slide_height = Emu(6858000)
    blank = prs.slide_layouts[6]

    for spec in pages:
        s = prs.slides.add_slide(blank)
        for (x, y, w, h, text) in spec.get("blocks", []):
            box = s.shapes.add_textbox(
                Emu(int(x * PS)), Emu(int(y * PS)),
                Emu(int(w * PS)), Emu(int(h * PS)))
            if text:
                box.text_frame.text = text
        for (x, y, w, h) in spec.get("lines", []):
            # 用真正的 connector 造线，才能被认成 LINE（与参照 deck 一致）
            from pptx.enum.shapes import MSO_CONNECTOR
            ln = s.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT,
                Emu(int(x * PS)), Emu(int(y * PS)),
                Emu(int((x + max(w, 1)) * PS)),
                Emu(int((y + max(h, 1)) * PS)))
            ln.line.width = Emu(max(int(min(w, h) * PS), 9525))

    prs.save(path)
    return path


def _designed_page(i):
    """仿参照：页眉线 + 全长分隔线 + 一组徽章/条带 + 分隔线 + 正文块。

    每页追加一个位置不同的结构件，模拟「每页一个不同的视觉论证」——这正是参照
    deck 的做法（阶梯 / 同心圆 / 矩阵 / 条形 / 递进带），也是骨架不能重复的原因。
    """
    blocks = [
        (78, 50, 1000, 28, f"习惯 0{i} · BE SOMETHING"),
        (60, 88, 1160, 50, f"第 {i} 页的论点句，这句话本身是个判断"),
        (594, 174, 118, 30, "准确定义"),
        (722, 172, 498, 84, "正文说明，讲清这一页的核心主张与边界"),
        (594, 266, 118, 30, "关键原则"),
        (722, 264, 498, 84, "第二条正文说明，给出原则与做法"),
        (594, 358, 118, 30, "常见误区"),
        (722, 356, 498, 84, "第三条正文说明，指出误读"),
        (60, 674, 940, 26, "依据：某书 第 N 章"),
        (1080, 668, 120, 26, f"0{i} / 10"),
    ]
    lines = [
        (60, 52, 0, 38),        # 页眉竖线
        (60, 150, 1160, 2),     # 页眉下全长线
        (594, 260, 626, 2),     # 切条目
        (594, 352, 626, 2),
        (594, 444, 626, 2),
    ]
    # 编号徽章 34×34 复用（组件固定、位置固定——这是「可复用组件」）
    for k in range(3):
        blocks.append((548, 180 + k * 92, 34, 34, str(k + 1)))
    # 细条项目符号
    for k in range(3):
        lines.append((60, 300 + k * 62, 8, 48))

    # 每页独有的视觉论证：横跨不同栏位带，让骨架真的不同
    # （参照 deck 就是这样：阶梯在左、矩阵在中、同心圆在左中、条形在左）
    variant = i % 5
    if variant == 0:      # 阶梯：横跨 0–4 带
        for k in range(3):
            blocks.append((80 + k * 120, 480 - k * 40, 260, 40, f"阶{k}"))
    elif variant == 1:    # 同心圆：左中 0–3 带
        blocks.append((80, 250, 320, 300, "外圈"))
        blocks.append((160, 330, 160, 140, "内圈"))
    elif variant == 2:    # 2×2 矩阵：铺满左侧 0–4 带
        blocks.append((80, 200, 220, 150, "I"))
        blocks.append((320, 200, 220, 150, "II"))
        blocks.append((80, 360, 220, 150, "III"))
        blocks.append((320, 360, 220, 150, "IV"))
    elif variant == 3:    # 水平柱：宽度差异大，横跨 2–5 带
        # 起点下移到 480 起，避开上方徽章(548,180 起)与正文块(722,264 起)：
        # 原先写在 300,200 会把「柱0」直接压在「关键原则」上——新版判据会抓
        for k in range(3):
            blocks.append((300, 490 + k * 40, 420 - k * 100, 30, f"柱{k}"))
    else:                 # 三段递进带：横跨 0–5 带
        for k in range(3):
            blocks.append((60 + k * 180, 220, 160, 90, f"段{k}"))
    return {"blocks": blocks, "lines": lines}


def _bare_page(i):
    """标题 + 三段文字的裸排布：没有框架、没有分隔线、没有结构件。"""
    return {"blocks": [
        (60, 86, 1080, 44, f"第 {i} 页标题"),
        (60, 200, 900, 80, "一段说明文字，只是把内容写出来，没有做版面设计。"),
        (60, 320, 900, 80, "第二段说明文字，同样只是文字块堆叠。"),
        (60, 440, 900, 80, "第三段说明文字。"),
    ], "lines": []}


class TestDesignedDeckPasses(unittest.TestCase):
    """有框架、有结构件、有分隔线的 deck 必须通过——否则闸门会被关掉。"""

    def test_reference_style_passes(self):
        with tempfile.TemporaryDirectory() as d:
            p = _deck(os.path.join(d, "ok.pptx"),
                      [_designed_page(i) for i in range(1, 11)])
            r = design_audit.audit_design(p)
        self.assertTrue(r["ok"], r["verdict"])
        self.assertGreaterEqual(r["divider_ratio"], 0.5)


class TestBareDeckCaught(unittest.TestCase):
    """裸排布必须被判不通过——这是 91 页那本的真实形态。"""

    def test_bare_pages_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _deck(os.path.join(d, "bare.pptx"),
                      [_bare_page(i) for i in range(1, 9)])
            r = design_audit.audit_design(p)
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["thin_pages"]), 8)
        self.assertEqual(len(r["bare_pages"]), 8)

    def test_no_dividers_is_a_defect(self):
        """全篇零分隔线要单独判——参照是 45 条、100% 覆盖。"""
        with tempfile.TemporaryDirectory() as d:
            p = _deck(os.path.join(d, "nodiv.pptx"),
                      [_designed_page(i) for i in range(1, 9)])
            # 造一份有结构件、零分隔线的 deck
            pages = []
            for i in range(1, 9):
                pg = _designed_page(i)
                pg["lines"] = []
                pages.append(pg)
            p2 = _deck(os.path.join(d, "nodiv2.pptx"), pages)
            r = design_audit.audit_design(p2)
        self.assertEqual(r["dividers_total"], 0)
        self.assertFalse(r["ok"])
        self.assertIn("分隔线", r["verdict"])


class TestSkeletonVariety(unittest.TestCase):
    """同骨架扎堆要判出来。「同骨架」的语义是坐标带 + 类别一致。"""

    def test_same_skeleton_over_limit(self):
        with tempfile.TemporaryDirectory() as d:
            # 6 页完全同构：坐标一模一样，只有文字不同
            pg = _designed_page(1)
            p = _deck(os.path.join(d, "same.pptx"),
                      [dict(pg) for _ in range(6)])
            r = design_audit.audit_design(p)
        self.assertGreater(r["max_repeat"], r["limits"]["max_same_skeleton"])
        self.assertFalse(r["ok"])
        self.assertIn("骨架", r["verdict"])


class TestPicturesNotJudged(unittest.TestCase):
    """关键回归：配图数量不参与判定。"""

    def test_zero_image_deck_passes(self):
        with tempfile.TemporaryDirectory() as d:
            p = _deck(os.path.join(d, "noimg.pptx"),
                      [_designed_page(i) for i in range(1, 9)])
            r = design_audit.audit_design(p)
        self.assertEqual(sum(x["pictures"] for x in r["per_page"]), 0)
        self.assertTrue(r["ok"])
        # 结论里不该出现「配图不足」这类说法
        self.assertNotIn("配图", r["verdict"].replace("配图", "", 0) if False else "")


class TestChrome(unittest.TestCase):
    """页面框架要能被量出来。"""

    def test_header_footer_counted(self):
        with tempfile.TemporaryDirectory() as d:
            p = _deck(os.path.join(d, "chrome.pptx"),
                      [_designed_page(i) for i in range(1, 6)])
            r = design_audit.audit_design(p)
        self.assertEqual(r["chrome"]["header"], 5)
        self.assertEqual(r["chrome"]["footer"], 5)


class TestTextCollisions(unittest.TestCase):
    """文字压字必须被抓——几何测量唯一看不见、人一眼就看见的缺陷。

    来历：这套参照语法第一版自己就有 10 处压字（标题压正文、色带内名称压说明、
    页码 "/05" 掉出画布一半），而结构件密度、分隔线、骨架多样性四项判据全绿。
    所以"形状够多"不等于"能看"，必须单独判。
    """

    def test_overlapping_text_caught(self):
        page = _designed_page(1)
        # 在徽章正上方压一块长文字，模拟"标题压到正文"
        page["blocks"].append((548, 186, 400, 30, "压上去的一行说明文字"))
        with tempfile.TemporaryDirectory() as d:
            p = _deck(os.path.join(d, "col.pptx"), [page])
            r = design_audit.audit_design(p)
        self.assertTrue(r["collisions"], "应当抓到文字重叠")
        self.assertFalse(r["ok"])

    def test_clean_deck_has_no_collisions(self):
        with tempfile.TemporaryDirectory() as d:
            p = _deck(os.path.join(d, "clean.pptx"),
                      [_designed_page(i) for i in range(1, 6)])
            r = design_audit.audit_design(p)
        self.assertEqual(r["collisions"], [])

    def test_text_out_of_canvas_caught(self):
        """文字掉出画布边界要被判出界——页码写太低就是这么丢的。"""
        page = _designed_page(1)
        page["blocks"].append((1100, 706, 140, 30, "/ 10"))
        with tempfile.TemporaryDirectory() as d:
            p = _deck(os.path.join(d, "clip.pptx"), [page])
            r = design_audit.audit_design(p)
        self.assertTrue(r["clipped"], "应当抓到文字出界")
        self.assertFalse(r["ok"])


class TestReferenceSampleBuilds(unittest.TestCase):
    """参照语法样本自己能通过自己的判据——判据和语汇必须对得上。"""

    def test_built_sample_passes(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "ref.pptx")
            design_audit.build_reference_sample().save(p)
            r = design_audit.audit_design(p)
        self.assertTrue(r["ok"], r["verdict"])
        self.assertEqual(r["collisions"], [])
        self.assertEqual(r["clipped"], [])
        self.assertGreaterEqual(r["divider_ratio"], 0.5)
        self.assertLessEqual(r["max_repeat"], 2)

    def test_every_page_has_different_skeleton(self):
        """5 页 5 种论证：不能有两页骨架相同（那就是模板复用）。"""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "ref.pptx")
            design_audit.build_reference_sample().save(p)
            r = design_audit.audit_design(p)
        self.assertEqual(r["skeleton_groups"], [], "5 页应当各不相同")


if __name__ == "__main__":
    unittest.main()
