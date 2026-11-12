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

class TestSpecMustDriveLayout:
    """规格必须真的驱动版面，不能只是把字段填满。

    来历（2026-11-13，用户第二次报「生成的 PPT 又没按 skill 做」）：
    六维闸门接上之后，一个更隐蔽的问题浮出来——规格**填了，但没生效**。
    `compose()` 里唯一读进几何的 brief 字段只有 `archetype`；`structure` 写的
    「同心圆」被原样抄进 slide["design_brief"] 存档，画面却还是引擎挑的
    `editorial-spread`。实测 6 页里 5 页的规格和版面完全脱钩。

    这条判据就是那个断点：说了什么几何，成品就得有那个几何。
    """

    def _slide(self, arch, structure, children=None):
        return {
            "archetype": arch,
            "design_brief": {"structure": structure},
            "children": children if children is not None else [
                {"t": "text", "rect": [60, 80, 1000, 44], "text": "标题"},
                {"t": "box", "rect": [60, 160, 300, 200]},
            ],
        }

    def test_spec_matching_layout_passes(self):
        """说了同心圆、渲染出 circle 类 → 通过。"""
        s = self._slide("circle-focus", "同心圆：三圈由外向内收敛",
                        [{"t": "circle", "rect": [100, 200, 240, 240]}])
        assert ds.check_spec_drives_layout([s]) == []

    def test_spec_without_geometry_word_is_skipped(self):
        """规格里没用几何语汇 → 不做这项校验，不能凭空判错。"""
        s = self._slide("stair-list", "先把结论摆出来，再用三条依据撑住")
        assert ds.check_spec_drives_layout([s]) == []

    def test_spec_claiming_quadrant_but_rendered_as_list_is_blocked(self):
        """说了四象限（grid/quadrant），渲染成普通列表 → 拦。"""
        s = self._slide("stair-list", "四象限：按重要与紧急两个维度切开")
        blockers = ds.check_spec_drives_layout([s])
        assert len(blockers) == 1
        assert blockers[0][0] == "SPEC_NOT_COMPILED"
        assert "quadrant" in blockers[0][1]

    def test_host_rendered_page_is_skipped(self):
        """宿主手绘页 children 为空，无法反推几何 → 不判错。"""
        s = self._slide("__host__", "同心圆：宿主自己画")
        s["children"] = []
        assert ds.check_spec_drives_layout([s]) == []

    def test_real_compose_blocks_when_engine_overrides_the_spec(self):
        """端到端：规格说同心圆，引擎却给了别的版式 → compose 必须失败。

        这是本次修复的核心行为，也是「逐页当设计师」与「逐页填字段」的分界。
        """
        from engine import art_direction as ad
        pages = [{"kind": "content", "title": "第 1 页",
                  "points": ["一", "二", "三"]}]
        briefs = {0: {
            "structure": "同心圆：三圈由外向内收敛，最内圈是唯一答案",
            "hierarchy": "第一眼最内圈，第二眼外环，辅助是环带名",
            "components": [{"name": "外环", "role": "背景条件"},
                           {"name": "内圈", "role": "结论"}],
            "states": {"default": "静置", "emphasis": "描边", "disabled": "淡化"},
            "responsive": "窄屏 960px 以下改纵向堆叠",
            "a11y": {"contrast": "8.2:1", "text_size": "13.5pt"},
            "consistency": {"palette": "accent", "spacing": "gutter"},
            "rationale": "同心圆能让读者从外到内读出收敛关系，比并列三条更有效",
        }}
        notes = {"book": {"title": "t"}, "design_system": DESIGN_SYSTEM,
                 "pages": pages}
        with pytest.raises(ValueError) as exc:
            ad.compose(notes, design_briefs=briefs)
        assert "SPEC_NOT_COMPILED" in str(exc.value)


class TestSlideGeometry:
    """从坐标反推几何，stair 与 grid 必须分得开。"""

    def test_true_stair_detected(self):
        """四个不同左缘、顶边单调上抬、累计横移够大 → stair。"""
        s = {"children": [
            {"t": "box", "rect": [60, 460, 200, 140]},
            {"t": "box", "rect": [270, 350, 200, 140]},
            {"t": "box", "rect": [480, 240, 200, 140]},
            {"t": "box", "rect": [690, 130, 200, 140]},
        ]}
        geo = ds._slide_geometry(s)
        assert "stair" in geo

    def test_grid_mosaic_not_misread_as_stair(self):
        """马赛克「一大两小」：左大格，右列两小格上下堆叠。

        回归（2026-11-13，《11枚戒指》p05）：旧判据只看左缘递增 + 顶边
        单调 + 横移够大，而右列两块左缘相同也照样通过，于是 grid 被误判
        成 stair，规格说 grid、成品被判 stair，正路被拦。
        """
        s = {"children": [
            {"t": "box", "rect": [64, 132, 560, 500]},    # 左大格
            {"t": "box", "rect": [646, 132, 570, 248]},   # 右上小格
            {"t": "box", "rect": [646, 392, 570, 240]},   # 右下小格
        ]}
        geo = ds._slide_geometry(s)
        assert "stair" not in geo
        assert "grid" in geo


class TestBriefsFileShape:
    """简报文件的**形态**必须是扁平映射。

    这个坑很隐蔽：`--briefs` 会把整个 JSON 当映射交给 `_resolve_brief`，
    它只认 `"0"` / `0` / page id 三种 key。如果文件在外面包了一层
    `{"design_briefs": {...}}`，`_resolve_brief` 找不到任何一页，于是**静默
    回退到原型池**——compose 照样成功、页数照样对、只是九页设计全部失效。
    """

    def test_flat_mapping_resolves(self):
        from engine import art_direction as ad
        flat = {"0": {"structure": "A"}, "1": {"structure": "B"}}
        assert ad._resolve_brief(flat, 0, {"id": "p0"})["structure"] == "A"
        assert ad._resolve_brief(flat, 1, {"id": "p1"})["structure"] == "B"

    def test_wrapped_mapping_silently_misses(self):
        from engine import art_direction as ad
        wrapped = {"design_briefs": {"0": {"structure": "A"}}}
        # 不是抛错，是返回 None —— 这正是危险之处，所以要有测试钉住。
        assert ad._resolve_brief(wrapped, 0, {"id": "p0"}) is None

    def test_shipped_example_is_flat_and_complete(self):
        """仓库里那份示例必须是扁平的，并且页数与书稿对得上。"""
        import json
        briefs_path = os.path.join(ROOT, "examples", "briefs_renqing_mianzi.json")
        notes_path = os.path.join(ROOT, "examples", "notes_renqing_mianzi.json")
        briefs = json.load(open(briefs_path, encoding="utf-8"))
        notes = json.load(open(notes_path, encoding="utf-8"))

        assert "design_briefs" not in briefs, "示例文件被包了一层，会静默失效"
        assert set(briefs) == {str(i) for i in range(len(notes["pages"]))}
        # 每页都得是完整六维，不能靠闸门兜底才发现
        for i, b in briefs.items():
            probs = ds.check_brief({"design_brief": b}, int(i) + 1,
                                   design_system=notes["design_system"])
            assert not probs, f"第 {i} 页简报不合格：{probs}"
