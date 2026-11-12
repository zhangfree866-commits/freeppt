"""逐页设计闸门的验收测试。

这些测试守的是**第一性原理能不能被机器执行**，不是某个函数的返回值：

* 没写设计简报的 deck 必须编译不过——「跳过设计、从模板库挑一个往里填」
  要成为物理上产不出的东西；
* 简报写了但结构标签成片重复，必须被拦住——重复说明没逐页判断；
* 简报写得花哨但版面照抄上一页（几何骨架重复），必须被拦住——这是唯一
  能抓「绕过流程直接手写模板」的判据；
* 仪式页（封面/章节/封底）同构不能被误伤——一本书 11 个章节页长得一样
  是对的；
* 显式声明走原型兜底时放行，但要留下可见痕迹，不许静默。

回归锚点：`test_real_world_template_deck_is_rejected` 用一本真实的 122 页
同构 deck（每页只有 archetype、没有 design_brief）当样本，断言它必然被拒。
以后谁把闸门改松，这条测试会红，而不是等到用户拿到成品才发现。
"""

import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import art_direction as ad          # noqa: E402
from engine import design_spec as db           # noqa: E402
from engine import layout_fingerprint as lf    # noqa: E402
from engine.cli import prepare                 # noqa: E402
from engine.lint import lint_deck              # noqa: E402


# deck 级设计令牌：六维里的 consistency 只能引用这些键。
DESIGN_SYSTEM = {
    "palette": {"ink": "#1C1917", "accent": "#9A3412", "paper": "#FAF7F2"},
    "type_scale": {"h1": 33, "h2": 24, "body": 13.5},
    "spacing": {"base": 8, "gutter": 76},
    "font_pair": {"title": "Georgia", "body": "Arial"},
}

# 一页完整设计方案：六维齐全。这是「设计师想过」的最小证据。
GOOD_BRIEF = {
    "structure": "否定墙：左列六个灰块，右侧一块亮起",
    "hierarchy": "第一眼是右侧亮块，第二眼是左侧六个灰块，辅助信息是底部来源",
    "components": [
        {"name": "左侧灰块阵", "role": "列举被否定的做法"},
        {"name": "右侧亮块", "role": "唯一被保留的答案，视觉焦点"},
        {"name": "底部来源行", "role": "依据，弱化处理"},
    ],
    "states": {
        "default": "六块全灰、右块高亮",
        "emphasis": "讲某一条时该块描边加粗",
        "disabled": "已排除的块降到 40% 不透明度",
    },
    "responsive": "窄屏 960px 以下两列改堆叠，灰块阵折成 2×3；投影 16:9 保持两列",
    "a11y": {
        "contrast": "正文对纸色 8.2:1，灰块文字 4.6:1",
        "text_size": "最小字号 13.5pt，高于投影可读下限",
        "alt": "灰块阵提供一句整体说明，不逐块配 alt",
    },
    "consistency": ["palette", "type_scale", "font_pair"],
    "rationale": "这页是「六个假的对照一个真的」，需要并列否定，"
                 "用编号行会丢掉对照关系，所以做成左右两列墙",
}


def notes(pages, **extra):
    doc = {"book": {"title": "闸门测试", "author": "测试"},
           "design_system": DESIGN_SYSTEM,
           "pages": pages}
    doc.update(extra)
    return doc


def page(title, kind="concept"):
    return {
        "kind": kind,
        "title": title,
        "lead": "这是导语，用于交代背景与论证起点。",
        "points": [
            {"head": "要点甲", "body": "第一个要点的展开说明，保持具体。"},
            {"head": "要点乙", "body": "第二个要点的展开说明，形成呼应。"},
        ],
        "source": "来源：测试资料",
    }


def briefs(n, structures=None):
    out = {}
    for i in range(n):
        b = dict(GOOD_BRIEF)
        if structures:
            b["structure"] = structures[i % len(structures)]
        else:
            b["structure"] = f"结构{i}"
        out[i] = b
    return out


class TestComposeRequiresBriefs(unittest.TestCase):
    """没有简报就不许编排——入口闸门。"""

    def test_compose_without_briefs_raises(self):
        doc = notes([page("封面甲", "cover"), page("正文一")])
        with self.assertRaises(ValueError) as ctx:
            ad.compose(doc)
        msg = str(ctx.exception)
        self.assertIn("design_briefs", msg)
        self.assertIn("brief_pool", msg)

    def test_compose_with_briefs_succeeds(self):
        doc = notes([page("封面甲", "cover"), page("正文一")])
        deck, ledger = ad.compose(doc, design_briefs=briefs(2))
        self.assertEqual(ledger["design_briefs_applied"], 2)
        self.assertFalse(deck["art_direction"]["brief_pool"])

    def test_explicit_pool_fallback_is_allowed_but_recorded(self):
        doc = notes([page("封面甲", "cover"), page("正文一")],
                    brief_pool="prototype")
        deck, _ = ad.compose(doc)
        self.assertTrue(deck["art_direction"]["brief_pool"])


class TestBriefGate(unittest.TestCase):
    """简报本身的完整性判据。"""

    def test_missing_brief_blocks(self):
        deck, _ = ad.compose(notes([page("封面甲", "cover"), page("正文一")]),
                             design_briefs=briefs(2))
        deck["slides"][1].pop("design_brief")
        res = lint_deck(prepare(copy.deepcopy(deck)))
        self.assertFalse(res["ok"])
        self.assertIn("DESIGN_SPEC_MISSING",
                      {e["code"] for e in res["errors"]})

    def test_placeholder_brief_blocks(self):
        for junk in ("无", "TBD", "同上", "-", "  "):
            b = dict(GOOD_BRIEF)
            b["structure"] = junk
            probs = db.check_brief({"design_brief": b}, 7)
            self.assertTrue(probs, f"占位话术「{junk}」应被判为没填")

    def test_short_rationale_blocks(self):
        b = dict(GOOD_BRIEF)
        b["rationale"] = "好看"          # 3 字，远低于下限
        probs = db.check_brief({"design_brief": b}, 3)
        self.assertTrue(any("rationale" in p for p in probs))

    def test_complete_brief_passes(self):
        self.assertEqual(db.check_brief({"design_brief": GOOD_BRIEF}, 1), [])

    def test_invalid_hierarchy_blocks(self):
        """hierarchy 没有层级词 = 所有元素一样重，必须拦。"""
        b = dict(GOOD_BRIEF)
        b["hierarchy"] = "把标题放上面，下面是正文和几个卡片，整体排得比较整齐"
        probs = db.check_brief({"design_brief": b}, 2)
        self.assertTrue(any("hierarchy" in p for p in probs),
                        f"无层级词应被拦，实际返回 {probs}")

    def test_structure_reused_across_pages_blocks(self):
        """6 页同一结构标签：在 compose 入口就被拒（比 lint 更早）。"""
        with self.assertRaises(ValueError) as ctx:
            ad.compose(
                notes([page("封面甲", "cover")]
                      + [page(f"正文{i}") for i in range(5)]),
                design_briefs=briefs(6, structures=["编号行"]))
        self.assertIn("STRUCTURE_REUSED", str(ctx.exception))

    def test_distinct_structures_pass(self):
        deck, _ = ad.compose(
            notes([page("封面甲", "cover")] + [page(f"正文{i}") for i in range(5)]),
            design_briefs=briefs(6))
        res = lint_deck(prepare(copy.deepcopy(deck)))
        codes = {e["code"] for e in res["errors"]}
        self.assertNotIn("STRUCTURE_REUSED", codes)
class TestSkeletonGate(unittest.TestCase):
    """兜底判据：几何骨架重复。核心是它不听自报标签。"""

    def test_ritual_pages_are_exempt(self):
        self.assertTrue(lf.is_ritual({"archetype": "cover-editorial"}))
        self.assertTrue(lf.is_ritual({"archetype": "chapter-opener"}))
        self.assertTrue(lf.is_ritual({"archetype": "closing-echo"}))
        self.assertTrue(lf.is_ritual({"role": "chapter"}))
        self.assertFalse(lf.is_ritual({"archetype": "stair-list"}))

    def test_relabeling_does_not_hide_repeats(self):
        """把版式名改成不同名字，几何没变——仍必须被抓住。"""
        slide = {
            "children": [
                {"t": "text", "rect": [60, 80, 600, 40], "text": "标题"},
                {"t": "text", "rect": [60, 200, 200, 24], "text": "左标签"},
                {"t": "text", "rect": [600, 200, 600, 24], "text": "右说明"},
            ]
        }
        s = copy.deepcopy(slide)
        s["archetype"] = "完全不同的名字-甲"
        t = copy.deepcopy(slide)
        t["archetype"] = "完全不同的名字-乙"
        self.assertEqual(lf.skeleton(s), lf.skeleton(t))

    def test_different_geometry_is_not_grouped(self):
        a = {"children": [{"t": "text", "rect": [60, 80, 600, 40], "text": "x"}]}
        b = {"children": [{"t": "text", "rect": [700, 80, 500, 40], "text": "x"}]}
        self.assertNotEqual(lf.skeleton(a), lf.skeleton(b))

    def test_repeats_detected_beyond_tolerance(self):
        base = {"children": [
            {"t": "text", "rect": [60, 80, 600, 40], "text": "标题"},
            {"t": "text", "rect": [60, 200, 300, 24], "text": "标签"},
        ]}
        slides = [copy.deepcopy(base) for _ in range(5)]
        hits = lf.find_repeats(slides, max_pages=2)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][1], [1, 2, 3, 4, 5])


class TestRealWorldTemplateDeckRejected(unittest.TestCase):
    """回归锚点：真实的 122 页同构 deck 必须被拒。

    样本取自一次真实翻车：122 页里 102 页落在重复骨架上，但当时的闸门
    `ok=True` 放行。这里用它的结构特征（每页只有 archetype、没有简报）
    重建最小复现，确保同类产物以后编译不过。
    """

    def _template_deck(self, n=40):
        # 一本「手写模板库」式 deck：每页只有自报的版式名和固定几何
        slides = []
        for i in range(n):
            slides.append({
                "type": "content", "tone": "light", "surface": "#FFFFFF",
                "composition": "freeform",
                "archetype": f"自造版式-{i % 6}",      # 名字各不相同
                "density": "mid",
                "children": [
                    {"t": "shape", "kind": "rect", "rect": [60, 184, 30, 30],
                     "fill": "#12263A", "decor": True},
                    {"t": "text", "rect": [60, 86, 1080, 44],
                     "text": f"第 {i} 页标题", "size": 32},
                    {"t": "text", "rect": [104, 190, 200, 24],
                     "text": f"标签{i}", "size": 14},
                    {"t": "text", "rect": [340, 190, 860, 60],
                     "text": f"说明文字{i}", "size": 11},
                ],
            })
        return {"composed": True, "theme": "consulting", "slides": slides}

    def test_real_world_template_deck_is_rejected(self):
        res = lint_deck(prepare(self._template_deck(40)))
        self.assertFalse(res["ok"], "122 页同构 deck 那种产物必须编译不过")
        codes = {e["code"] for e in res["errors"]}
        self.assertIn("DESIGN_SPEC_MISSING", codes)
        self.assertIn("LAYOUT_SKELETON_REPEAT", codes)

    def test_same_deck_with_briefs_still_caught_by_skeleton(self):
        """简报补齐了，但版面照抄——骨架判据仍要拦住（这才是兜底的价值）。"""
        deck = self._template_deck(12)
        for i, s in enumerate(deck["slides"]):
            b = dict(GOOD_BRIEF)
            b["structure"] = f"自称结构{i}"      # 名字不同，几何相同
            s["design_brief"] = b
        res = lint_deck(prepare(deck))
        codes = {e["code"] for e in res["errors"]}
        self.assertNotIn("DESIGN_BRIEF_MISSING", codes)
        self.assertIn("LAYOUT_SKELETON_REPEAT", codes)


class TestBuildIsOnTheDeliveryPath(unittest.TestCase):
    """回归锚点：成品审计必须挂在 build 上，不能只是可选手动命令。

    来历（2026-11-13，用户报「生成的 PPT 又完全没按 skill 做」）：查根因时发现
    `audit_design` 全仓只有命令行入口一个调用点，`build` 出片后**不审计**。
    于是模型手写 python-pptx、或跑一个自己写的构建脚本，就能一声不响地交付
    「12 页同构」的产物——判据存在但不在交付路径上，等于没有判据。

    这两个测试直接调 cmd_build，断言退出码：劣质必 1，成立必 0。
    """

    def _write(self, tmpdir, deck, name):
        import json
        import os
        p = os.path.join(tmpdir, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(deck, f, ensure_ascii=False)
        return p

    def test_homogeneous_deck_fails_build(self):
        """12 页里 10 页用同一个模板 → build 必须以退出码 1 结束。"""
        import argparse
        import os
        import tempfile
        from engine.cli import cmd_build

        slides = [{"template": "cover",
                   "data": {"title": "季度经营报告", "subtitle": "示例"}}]
        for i in range(1, 11):
            slides.append({"template": "three_cards", "data": {
                "title": f"第 {i} 个主题",
                "cards": [{"title": "要点一", "body": "说明文字"},
                          {"title": "要点二", "body": "说明文字"},
                          {"title": "要点三", "body": "说明文字"}]}})
        slides.append({"template": "closing", "data": {"title": "谢谢"}})

        with tempfile.TemporaryDirectory() as d:
            src = self._write(d, {"theme": "business", "slides": slides},
                              "bad.json")
            out = os.path.join(d, "bad.pptx")
            args = argparse.Namespace(deck=src, out=out, force=False)
            rc = cmd_build(args)
        self.assertEqual(rc, 1, "同构 deck 不能让 build 报成功")

    def test_healthy_deck_passes_build(self):
        """正常产物不能被这道强制关卡误伤——否则没人会再跑 build。"""
        import argparse
        import os
        import tempfile
        from engine.cli import cmd_build

        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "examples",
                "deck_business_demo.json")
            out = os.path.join(d, "ok.pptx")
            args = argparse.Namespace(deck=src, out=out, force=False)
            rc = cmd_build(args)
        self.assertEqual(rc, 0, "官方业务示例必须通过成品审计")


class TestDesignSystemReachesTheGate(unittest.TestCase):
    """回归锚点：design_system 必须真的传进六维闸门。

    来历（2026-11-13）：compose 里写的是
        design_spec.require_deck(slides, design_system=deck.get("design_system"))
    可 compose 从来没往 deck 里放过这个键——`deck.get()` 恒为 None，于是
    `check_brief` 里那段「引用不存在的令牌」的校验被 `elif design_system is
    not None` 整个跳过。「统一设计语言」这条判据写在文档里、写在代码里，
    却从来没有真正执行过一次。

    这正是本项目反复出现的失败形态：判据存在，但没有拿到判据需要的输入。
    """

    def _notes(self):
        pages = [{"kind": "content", "title": f"第 {i} 页标题",
                  "points": ["第一层含义", "第二层含义", "怎么落地"]}
                 for i in range(4)]
        briefs = {}
        for i in range(4):
            b = copy.deepcopy(GOOD_BRIEF)
            b["structure"] = f"结构{i}"      # 结构标签各不相同
            briefs[str(i)] = b
        return {"book": {"title": "测试"}, "design_system": DESIGN_SYSTEM,
                "design_briefs": briefs, "pages": pages}

    def _compose(self, notes):
        """design_briefs 是 compose() 的参数，不是 notes 里的键。"""
        return ad.compose(notes, design_briefs=notes["design_briefs"])

    def test_design_system_is_written_into_the_composed_deck(self):
        notes = self._notes()
        deck, _ = self._compose(copy.deepcopy(notes))
        self.assertIn("design_system", deck,
                      "design_system 必须落进产物，否则下游校验拿不到令牌表")
        self.assertEqual(sorted(deck["design_system"]),
                         sorted(DESIGN_SYSTEM))

    def test_bogus_token_reference_is_blocked(self):
        """引用一个 deck 里不存在的令牌键 → compose 必须失败。"""
        notes = self._notes()
        notes["design_briefs"]["0"]["consistency"] = {"fake_token_abc": "x"}
        with self.assertRaises(ValueError) as ctx:
            self._compose(copy.deepcopy(notes))
        self.assertIn("fake_token_abc", str(ctx.exception))

    def test_valid_token_reference_passes(self):
        """正常引用存在的令牌 → 通过。不能因为修严了就误伤正路。"""
        notes = self._notes()
        deck, ledger = self._compose(copy.deepcopy(notes))
        self.assertTrue(deck.get("design_system"))
        self.assertEqual(ledger["design_spec"]["pages_with_spec"], 4)
        self.assertIn("palette", ledger["design_spec"]["tokens_declared"],
                      "ledger 要记下这一本声明了哪些令牌，供事后追溯")

    def test_empty_consistency_blocks(self):
        """consistency 写空 → 拦。没声明沿用哪些令牌就等于各页自造一套。"""
        notes = self._notes()
        notes["design_briefs"]["0"]["consistency"] = {}
        with self.assertRaises(ValueError) as ctx:
            self._compose(copy.deepcopy(notes))
        self.assertIn("consistency", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
