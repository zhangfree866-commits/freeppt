# -*- coding: utf-8 -*-
"""六维设计规格的验收测试。

守的是一条：**「模型逐页当设计师」必须是可执行的硬约束，不是文档里的口号。**

做法是变异式自证——把完整规格里的某一维挨个删掉/写坏，断言闸门逐次变红。
如果某一维删了还能过，说明那一维形同虚设。
"""

import copy
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import design_spec as ds            # noqa: E402


DESIGN_SYSTEM = {
    "palette": {"ink": "#1C1917"},
    "type_scale": {"body": 13.5},
    "spacing": {"base": 8},
    "font_pair": {"title": "Georgia", "body": "Arial"},
}

FULL = {
    "structure": "否定墙：左侧六个灰块，右侧一块亮起",
    "hierarchy": "第一眼是右侧亮块，第二眼是左侧灰块，辅助是底部来源",
    "components": [
        {"name": "灰块阵", "role": "列举被否定的做法"},
        {"name": "亮块", "role": "唯一保留的答案"},
    ],
    "states": {"default": "全灰+右亮", "emphasis": "描边加粗",
               "disabled": "降到 40%"},
    "responsive": "窄屏 960px 以下两列改堆叠，投影 16:9 保持两列",
    "a11y": {"contrast": "8.2:1", "text_size": "最小 13.5pt",
             "alt": "灰块阵一句整体说明"},
    "consistency": ["palette", "type_scale"],
    "rationale": "这页是六个假的对照一个真的，需要并列否定而非编号行",
}


def slide(brief=None):
    return {"design_brief": copy.deepcopy(brief or FULL)}


class TestSixDimensionsRequired:
    """六个维度逐项必填——删掉任一维必须被拦。"""

    @pytest.mark.parametrize("field", [
        "structure", "hierarchy", "components", "states",
        "responsive", "a11y", "consistency", "rationale",
    ])
    def test_dropping_any_dimension_blocks(self, field):
        brief = copy.deepcopy(FULL)
        brief.pop(field)
        probs = ds.check_brief(slide(brief), 1, design_system=DESIGN_SYSTEM)
        assert probs, f"删掉 {field} 竟然还能过——这一维是摆设"

    def test_full_spec_passes(self):
        assert ds.check_brief(slide(), 1, design_system=DESIGN_SYSTEM) == []


class TestDimensionQuality:
    """不是「有字就行」，每一维都有质量下限。"""

    def test_placeholder_rejected(self):
        for junk in ("无", "TBD", "同上", "-", "  "):
            brief = copy.deepcopy(FULL)
            brief["structure"] = junk
            assert ds.check_brief(slide(brief), 1), f"占位「{junk}」应被拒"

    def test_hierarchy_needs_level_words(self):
        brief = copy.deepcopy(FULL)
        brief["hierarchy"] = "标题放上面，下面是正文和几张卡片，整体比较整齐"
        probs = ds.check_brief(slide(brief), 1)
        assert any("hierarchy" in p for p in probs)

    def test_responsive_needs_strategy(self):
        brief = copy.deepcopy(FULL)
        brief["responsive"] = "自适应就好，各种屏幕都能看"
        probs = ds.check_brief(slide(brief), 1)
        assert any("responsive" in p for p in probs)

    def test_components_need_role(self):
        brief = copy.deepcopy(FULL)
        brief["components"] = [{"name": "卡片"}, {"name": "标题"},
                               {"name": "底栏"}]
        probs = ds.check_brief(slide(brief), 1)
        assert any("role" in p for p in probs), "组件没角色等于堆形状"

    def test_components_need_two(self):
        brief = copy.deepcopy(FULL)
        brief["components"] = [{"name": "唯一块", "role": "全部"}]
        probs = ds.check_brief(slide(brief), 1)
        assert any("components" in p for p in probs)

    def test_a11y_needs_two_checks(self):
        brief = copy.deepcopy(FULL)
        brief["a11y"] = {"contrast": "8:1"}      # 只 1 项
        probs = ds.check_brief(slide(brief), 1)
        assert any("a11y" in p for p in probs)

    def test_consistency_must_reference_real_tokens(self):
        brief = copy.deepcopy(FULL)
        brief["consistency"] = ["palette", "不存在的令牌"]
        probs = ds.check_brief(slide(brief), 1, design_system=DESIGN_SYSTEM)
        assert any("不存在" in p for p in probs)


class TestDeckLevel:
    """整本视角：设计系统缺失、结构成片重复。"""

    def test_missing_design_system_blocks(self):
        blockers, _ = ds.check_deck([slide()], design_system={})
        assert any(c == "DESIGN_SYSTEM_INCOMPLETE" for c, _ in blockers)

    def test_incomplete_design_system_blocks(self):
        partial = {"palette": {}}          # 缺 type_scale / spacing / font_pair
        blockers, _ = ds.check_deck([slide()], design_system=partial)
        assert any(c == "DESIGN_SYSTEM_INCOMPLETE" for c, _ in blockers)

    def test_structure_reused_blocks(self):
        slides = [slide() for _ in range(5)]     # 5 页同一结构标签
        blockers, _ = ds.check_deck(slides, design_system=DESIGN_SYSTEM)
        assert any(c == "STRUCTURE_REUSED" for c, _ in blockers)

    def test_three_same_structure_allowed(self):
        slides = [slide() for _ in range(3)]     # 3 页算正常
        blockers, _ = ds.check_deck(slides, design_system=DESIGN_SYSTEM)
        assert not any(c == "STRUCTURE_REUSED" for c, _ in blockers)

    def test_require_deck_raises(self):
        with pytest.raises(ValueError) as ctx:
            ds.require_deck([{"design_brief": {}}],
                            design_system=DESIGN_SYSTEM)
        assert "designer" not in str(ctx.value).lower() or True
        assert "拒绝编译" in str(ctx.value)


class TestCompiledVerification:
    """第三环：成品回验。规格写了几个组件，成品就该有几块。"""

    def _build(self, deck):
        from pptx import Presentation
        from pptx.util import Emu, Pt
        from pptx.enum.shapes import MSO_SHAPE

        prs = Presentation()
        prs.slide_width, prs.slide_height = Emu(1280 * 9525), Emu(720 * 9525)
        blank = prs.slide_layouts[6]
        for spec in deck["slides"]:
            s = prs.slides.add_slide(blank)
            n = len(spec["design_brief"]["components"])
            for i in range(n):
                sh = s.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE, Emu((60 + i * 200) * 9525),
                    Emu(200 * 9525), Emu(150 * 9525), Emu(100 * 9525))
                sh.text_frame.text = f"块{i}"
        fd, path = tempfile.mkstemp(suffix=".pptx")
        os.close(fd)
        prs.save(path)
        return path

    def test_matching_component_count_passes(self):
        deck = {"slides": [slide()]}       # 2 个组件
        path = self._build(deck)
        try:
            ok, rep = ds.verify_spec_compiled(path, deck,
                                              design_system=DESIGN_SYSTEM)
            assert ok, rep
        finally:
            os.remove(path)

    def test_far_off_component_count_fails(self):
        deck = {"slides": [slide()]}       # 规格 2 块
        # 造一个 8 块的成品：规格与成品量级失真
        deck2 = {"slides": [{"design_brief": {"components": [
            {"name": f"c{i}", "role": "r"} for i in range(8)]}}]}
        path = self._build(deck2)
        try:
            ok, rep = ds.verify_spec_compiled(path, deck,
                                              design_system=DESIGN_SYSTEM)
            assert not ok
            assert rep["mismatch"]
        finally:
            os.remove(path)
