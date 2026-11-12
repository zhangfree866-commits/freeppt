"""Tests for the post-benchmark visual/content primitives.

Covers the native-shape icon set, OOXML gradient fills, the three alpha
channels (fill / text run / outline), speaker notes, and their full
layout -> lint -> compiler -> debug-render wiring. Nothing hits the network
and deterministic; no bitmap or SVG assets are involved.
"""

import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import icons, layout, lint, compiler, debug_render, themes  # noqa: E402

# consulting theme palette colors (safe for the PALETTE lint gate)
NAVY = "#061F32"
ROYAL = "#001965"
ACCENT = "#08A6F6"
SOFT = "#99BDED"
WHITE = "#FFFFFF"
BODY = "#44546A"


def freeform_slide(children, **kw):
    slide = {
        "type": "content",
        "composition": "freeform",
        "tone": "dark",
        "children": children,
    }
    slide.update(kw)
    return slide


def deck(slides):
    return {"theme": "consulting", "composed": False, "slides": slides}


def build(deck_obj):
    layout.layout_deck(deck_obj)
    tmp = tempfile.mktemp(suffix=".pptx")
    compiler.build_pptx(deck_obj, tmp, force=True)
    return tmp


def slide_xml(path, index=1):
    with zipfile.ZipFile(path) as z:
        return z.read(f"ppt/slides/slide{index}.xml").decode("utf-8")


class TestIconLibrary(unittest.TestCase):
    def test_canonical_and_alias_resolution(self):
        self.assertEqual(icons.resolve("target"), "target")
        self.assertEqual(icons.resolve("GOAL"), "target")  # case-insensitive
        self.assertEqual(icons.resolve("  target "), "target")  # trimmed
        self.assertEqual(icons.resolve("KPI"), "chart")
        self.assertEqual(icons.resolve("risk"), "shield")
        self.assertIsNone(icons.resolve("not-a-real-icon"))
        self.assertIsNone(icons.resolve(""))

    def test_every_icon_has_renderable_specs(self):
        for name in icons.ICONS:
            specs = icons.specs(name)
            self.assertTrue(specs, f"icon {name} has no specs")
            for sp in specs:
                self.assertIn(sp["k"], set(compiler.ICON_SHAPES) | {"line"})

    def test_aliases_point_to_existing_icons(self):
        for alias, target in icons.ALIASES.items():
            self.assertIn(target, icons.ICONS, f"alias {alias} dangles")


class TestGradientFill(unittest.TestCase):
    def test_gradient_reaches_ooxml_with_angle_in_60000ths(self):
        grad = {"stops": [{"color": ROYAL, "pos": 0},
                          {"color": NAVY, "pos": 100000}], "angle": 90}
        d = deck([freeform_slide(
            [{"t": "card", "rect": [80, 80, 400, 300], "gradient": grad,
              "children": []}],
            gradient=grad)])
        path = build(d)
        xml = slide_xml(path)
        # background rect + card each carry a gradient -> two gradFills,
        # each with two stops (4 gs total), angle 90deg -> 5,400,000 EMU
        self.assertEqual(xml.count("<a:gradFill"), 2)
        self.assertEqual(xml.count("<a:gs "), 4)
        self.assertIn('ang="5400000"', xml)
        self.assertIn(ROYAL.lstrip("#").upper(), xml)

    def test_layout_propagates_slide_gradient_to_root(self):
        grad = {"stops": [{"color": ROYAL}, {"color": NAVY}], "angle": 45}
        d = deck([freeform_slide([], gradient=grad)])
        layout.layout_deck(d)
        self.assertEqual(d["slides"][0]["_root"]["gradient"], grad)


class TestAlphaChannels(unittest.TestCase):
    def test_fill_alpha_injected_as_ooxml_alpha(self):
        d = deck([freeform_slide([
            {"t": "card", "rect": [80, 80, 300, 200], "fill": WHITE,
             "opacity": 8, "border": WHITE, "border_opacity": 20,
             "children": []}])])
        path = build(d)
        xml = slide_xml(path)
        # 8% opacity -> val 8000 ; 20% outline -> val 20000
        self.assertIn('val="8000"', xml)
        self.assertIn('val="20000"', xml)

    def test_text_run_alpha(self):
        d = deck([freeform_slide([
            {"t": "text", "rect": [80, 80, 500, 40], "text": "次级文字",
             "size": 20, "color": WHITE, "opacity": 70, "on": NAVY}])])
        path = build(d)
        self.assertIn('val="70000"', slide_xml(path))


class TestSpeakerNotes(unittest.TestCase):
    def test_notes_written_to_notes_slide(self):
        d = deck([freeform_slide([], notes="这是讲稿，不显示在画面上。")])
        path = build(d)
        with zipfile.ZipFile(path) as z:
            notes = [n for n in z.namelist() if "notesSlide" in n
                     and n.endswith(".xml")]
            self.assertTrue(notes)
            body = z.read(notes[0]).decode("utf-8")
            self.assertIn("讲稿", body)

    def test_slide_without_notes_has_no_notes_slide(self):
        d = deck([freeform_slide([])])
        path = build(d)
        with zipfile.ZipFile(path) as z:
            self.assertFalse(any("notesSlide" in n for n in z.namelist()))


class TestIconRenderAndLint(unittest.TestCase):
    def _icon_deck(self, name):
        return deck([freeform_slide([
            {"t": "icon", "rect": [100, 100, 96, 96], "name": name,
             "color": ACCENT}])])

    def test_icon_compiles_to_native_shapes(self):
        d = self._icon_deck("gear")
        path = build(d)
        xml = slide_xml(path)
        self.assertIn('prst="gear6"', xml)

    def test_shield_uses_plaque_preset(self):
        d = self._icon_deck("shield")
        path = build(d)
        self.assertIn('prst="plaque"', slide_xml(path))

    def test_alias_icon_compiles(self):
        d = self._icon_deck("goal")  # -> target (rings + bullseye, all ovals)
        path = build(d)
        # bullseye is three concentric ovals; assert native autoshape presets
        self.assertEqual(slide_xml(path).count('prst="ellipse"'), 3)

    def test_lint_accepts_known_icon_name(self):
        d = self._icon_deck("rocket")
        layout.layout_deck(d)
        res = lint.lint_deck(d)
        self.assertNotIn("ICON_NAME",
                         [e["code"] for e in res["errors"]])

    def test_lint_rejects_unknown_icon_name(self):
        d = self._icon_deck("nonsense")
        layout.layout_deck(d)
        res = lint.lint_deck(d)
        self.assertIn("ICON_NAME", [e["code"] for e in res["errors"]])

    def test_icon_kept_square_in_row_layout(self):
        # regression: a fixed-size icon must not be stretched to row width
        d = deck([{
            "type": "content",
            "title": "图标版式",
            "children": [{"t": "box", "layout": "rows", "gap": 24,
                          "padding": 16, "children": [
                              {"t": "icon", "size": 56, "name": "bulb",
                               "color": ACCENT},
                              {"t": "text", "text": "标题文字", "size": 20,
                               "color": NAVY}]}],
            "footer": {"page": "1"},
        }])
        layout.layout_deck(d)
        icon_node = next(
            n for n in lint.walk(d["slides"][0]["_root"]) if n["t"] == "icon")
        w, h = icon_node["_rect"][2], icon_node["_rect"][3]
        self.assertEqual(w, h)
        self.assertEqual(w, 56)


class TestGradientPaletteAndDebugRender(unittest.TestCase):
    def test_gradient_colors_pass_palette_gate(self):
        grad = {"stops": [{"color": ROYAL}, {"color": NAVY}], "angle": 90}
        d = deck([freeform_slide(
            [{"t": "card", "rect": [80, 80, 300, 200], "gradient": grad,
              "children": []}], gradient=grad)])
        layout.layout_deck(d)
        res = lint.lint_deck(d)
        self.assertNotIn("PALETTE", [e["code"] for e in res["errors"]])

    def test_debug_render_handles_gradient_and_icon(self):
        grad = {"stops": [{"color": ROYAL}, {"color": NAVY}], "angle": 90}
        d = deck([freeform_slide(
            [{"t": "icon", "rect": [100, 100, 96, 96], "name": "clock",
              "color": ACCENT}], gradient=grad)])
        layout.layout_deck(d)
        tile = debug_render.gradient_box(grad, 120, 80)
        self.assertEqual(tile.size, (120, 80))
        out_dir = tempfile.mkdtemp()
        pngs = debug_render.render(d, out_dir)
        self.assertEqual(len(pngs), 1)
        self.assertTrue(os.path.exists(pngs[0]))


class TestSpeakerNotes(unittest.TestCase):
    def _book(self):
        # 本组测讲稿生成与确定性，不测逐页设计判断，声明走原型兜底。
        return {
            "brief_pool": "prototype",
            "book": {"title": "管理的常识", "author": "陈春花"},
            "pages": [
                {"kind": "cover", "title": "管理的常识", "lead": "让管理发挥绩效"},
                {"kind": "chapter", "title": "理解管理", "no": "01"},
                {"kind": "concept", "title": "管理要指令清晰",
                 "lead": "管理的起点是明确。",
                 "points": [{"head": "指令清晰", "body": "把期望转成可执行的明确指令。"},
                            {"head": "目标对齐", "body": "个人目标与组织目标保持一致。"}]},
                {"kind": "closing", "title": "把常识变成习惯"}],
        }

    def test_notes_generated_for_every_page_and_deterministic(self):
        from engine import art_direction as AD
        a, _ = AD.compose(self._book(), base="magazine")
        b, _ = AD.compose(self._book(), base="magazine")
        notes_a = [s.get("notes", "") for s in a["slides"]]
        notes_b = [s.get("notes", "") for s in b["slides"]]
        self.assertEqual(notes_a, notes_b)  # deterministic, no rng
        self.assertTrue(all(n and len(n.strip()) > 0 for n in notes_a))
        # restates real content rather than inventing data
        self.assertIn("指令清晰", notes_a[2])
        self.assertIn("管理的常识", notes_a[0])

    def test_speaker_notes_switch_off(self):
        from engine import art_direction as AD
        d, _ = AD.compose(self._book(), base="magazine", speaker_notes=False)
        self.assertFalse(d["art_direction"]["speaker_notes"])
        self.assertTrue(all("notes" not in s for s in d["slides"]))

    def test_page_own_notes_take_precedence(self):
        from engine import art_direction as AD
        book = self._book()
        book["pages"][2]["notes"] = "这是作者手写的逐字稿，必须原样保留。"
        d, _ = AD.compose(book, base="magazine")
        self.assertEqual(d["slides"][2]["notes"],
                         "这是作者手写的逐字稿，必须原样保留。")

    def test_notes_coverage_lint_blocks_missing_script(self):
        from engine import art_direction as AD
        import copy
        d, _ = AD.compose(self._book(), base="magazine")
        layout.layout_deck(d)
        self.assertTrue(lint.lint_deck(d)["ok"])
        broken = copy.deepcopy(d)
        broken["slides"][2]["notes"] = ""
        layout.layout_deck(broken)
        codes = {e["code"] for e in lint.lint_deck(broken)["errors"]}
        self.assertIn("NOTES_COVERAGE", codes)

    def test_thin_notes_warn_but_do_not_block(self):
        from engine import art_direction as AD
        d, _ = AD.compose(self._book(), base="magazine")
        layout.layout_deck(d)
        res = lint.lint_deck(d)
        # cover/chapter scripts are intentionally short -> warning, not error
        self.assertTrue(res["ok"])
        self.assertIn("NOTES_THIN", {w["code"] for w in res["warnings"]})

    def test_generated_notes_reach_pptx_notes_slides(self):
        from engine import art_direction as AD
        d, _ = AD.compose(self._book(), base="magazine")
        path = build(d)
        with zipfile.ZipFile(path) as z:
            note_files = [n for n in z.namelist()
                          if "notesSlides/notesSlide" in n and n.endswith(".xml")]
        self.assertEqual(len(note_files), len(d["slides"]))


class TestContentDensityAndResearch(unittest.TestCase):
    def _freeform(self, archetype, text, extra=None):
        slide = {
            "type": "content", "tone": "light", "surface": "#FFFFFF",
            "composition": "freeform", "archetype": archetype,
            "density": "mid",
            "children": [{"t": "text", "rect": [80, 80, 900, 50], "text": text,
                          "size": 24, "color": NAVY, "on": "#FFFFFF"}],
        }
        if extra:
            slide.update(extra)
        return slide

    def _lint(self, slides, composed=True):
        d = deck(slides)
        d["composed"] = composed
        d["art_direction"] = {"speaker_notes": False}
        # 本组是 lint 规则的单元测试，手工构造单页 DSL，测的是密度/对比度/
        # 讲稿等具体规则，不是逐页设计判断；按设计意图声明走原型兜底，
        # 免得简报闸门在这里产生噪声。逐页设计闸门由
        # tests/test_design_brief_gate.py 专门覆盖。
        d["brief_pool"] = "prototype"
        layout.layout_deck(d)
        return lint.lint_deck(d), d

    def test_thin_content_page_warns_but_does_not_block(self):
        res, _ = self._lint([self._freeform("editorial-spread", "寥寥数字")])
        self.assertIn("CONTENT_DENSITY",
                      {w["code"] for w in res["warnings"]})
        self.assertTrue(res["ok"])  # warnings never block the build

    def test_exempt_archetypes_skip_density_rule(self):
        for arch in ("cover-editorial", "chapter-opener", "quote-bleed",
                     "chart-story"):
            res, _ = self._lint([self._freeform(arch, "短")])
            self.assertNotIn(
                "CONTENT_DENSITY",
                {w["code"] for w in res["warnings"]},
                f"{arch} should be density-exempt")

    def test_density_rule_only_for_composed_decks(self):
        res, _ = self._lint([self._freeform("editorial-spread", "短")],
                            composed=False)
        self.assertNotIn("CONTENT_DENSITY",
                         {w["code"] for w in res["warnings"]})

    def test_research_demand_without_sources_is_an_error(self):
        slide = self._freeform("editorial-spread", "需要研究支撑的论点",
                               {"research": "需核实行业数据"})
        res, _ = self._lint([slide])
        self.assertIn("RESEARCH_LEDGER",
                      {e["code"] for e in res["errors"]})

    def test_research_demand_with_valid_sources_passes(self):
        slide = self._freeform(
            "editorial-spread", "有来源支撑的论点",
            {"research": "行业数据",
             "sources": [{"title": "年度行业报告", "publisher": "研究机构"}]})
        res, _ = self._lint([slide])
        self.assertNotIn("RESEARCH_LEDGER",
                         {e["code"] for e in res["errors"]})

    def test_visible_char_counter_counts_text_and_richcards(self):
        slide = self._freeform("editorial-spread", "标题文字")
        slide["children"].append({
            "t": "richcard", "rect": [80, 200, 400, 120], "fill": "#FFFFFF",
            "blocks": [{"text": "卡片正文", "size": 18, "color": BODY}]})
        _, d = self._lint([slide])
        self.assertEqual(lint._visible_chars(d["slides"][0]), 8)


class TestThemeGradientAndTypeface(unittest.TestCase):
    def test_legacy_theme_has_no_gradient_token(self):
        th = themes.get_theme("consulting")
        self.assertIsNone(th["visual"].get("background_gradient"))

    def test_magazine_family_carries_palette_safe_gradient(self):
        for name in ("magazine", "tech", "oriental"):
            th = themes.get_theme(name)
            grad = th["visual"].get("background_gradient")
            self.assertIsNotNone(grad, f"{name} missing gradient token")
            for st in grad["stops"]:
                self.assertIn("#" + st["color"].lstrip("#").upper(),
                              th["palette"],
                              f"{name} gradient color outside its palette")

    def test_theme_sentinel_resolves_to_active_gradient(self):
        d = deck([freeform_slide([], tone="dark", gradient="theme")])
        d["theme"] = "tech"
        layout.layout_deck(d)
        grad = d["slides"][0]["_root"]["gradient"]
        self.assertIsNotNone(grad)
        self.assertEqual(grad, themes.get_theme("tech")["visual"]["background_gradient"])

    def test_serif_themes_pair_serif_heading_with_sans_body(self):
        for name in ("magazine", "oriental", "wired"):
            vis = themes.get_theme(name)["visual"]
            self.assertTrue(vis["serif_heading"])
            self.assertNotEqual(vis["latin_heading"], vis["latin_body"])
        # consulting stays sans throughout (zero regression)
        cv = themes.get_theme("consulting")["visual"]
        self.assertFalse(cv["serif_heading"])


class TestCardArchetypes(unittest.TestCase):
    def _notes(self, n=6):
        # 本组测卡片原型的确定性，不测逐页设计判断，声明走原型兜底。
        return {
            "brief_pool": "prototype",
            "book": {"title": "卡片体系测试书"},
            "pages": [{
                "kind": "concept",
                "title": f"概念页 {i}",
                "points": [{"head": f"要点 {j}", "body": "这是要点的具体阐述，"
                            "用于检验卡片的内边距、图标与文字层级排版。"}
                           for j in range(3)],
            } for i in range(n)],
        }

    def test_card_system_off_keeps_legacy_plan(self):
        from engine import art_direction as AD
        d1, _ = AD.compose(self._notes(), base="magazine", card_system=False)
        d2, _ = AD.compose(self._notes(), base="magazine")  # default off
        self.assertEqual(d1["art_direction"]["archetypes"],
                         d2["art_direction"]["archetypes"])
        used = set(d1["art_direction"]["archetypes"])
        self.assertFalse(used & set(AD.CARD_ARCHETYPES))
        self.assertFalse(d1["art_direction"]["card_system"])

    def test_card_system_on_uses_card_archetypes_deterministically(self):
        from engine import art_direction as AD
        a, _ = AD.compose(self._notes(), base="magazine", card_system=True)
        b, _ = AD.compose(self._notes(), base="magazine", card_system=True)
        self.assertEqual(a["art_direction"]["archetypes"],
                         b["art_direction"]["archetypes"])  # deterministic
        self.assertTrue(a["art_direction"]["card_system"])
        self.assertTrue(
            set(a["art_direction"]["archetypes"]) & set(AD.CARD_ARCHETYPES))

    def test_each_card_archetype_builds_icons_and_passes_lint(self):
        from engine import art_direction as AD
        import random
        themes.activate({"theme": "consulting"})
        sem = themes.get_active()["semantic"]
        u = lambda k: sem[k].upper()
        S = {k: u(v) for k, v in {
            "paper": "surface_light", "deep": "surface_dark", "card": "card_fill",
            "ink": "ink", "ondark": "ink_on_dark", "body": "body",
            "muted": "muted", "line": "line", "accent": "accent",
            "accent2": "accent_2", "soft": "accent_soft"}.items()}
        S.update({"decor": u("accent_soft"), "white": "#FFFFFF",
                  "black": "#000000", "motif": "band"})
        ctx = {"idx": 0, "total": 1, "rng": random.Random(3),
               "book": {"title": "x"}, "cover_file": None, "cover_credit": None}
        page = {"kind": "concept", "title": "卡片原型",
                "points": [{"head": f"标题 {i}", "body": "卡片正文阐述文字，"
                            "检验排版与层级是否正常工作。"} for i in range(3)]}
        for name in AD.CARD_ARCHETYPES:
            fn = AD.ARCHETYPES[name]["build"]
            kids, surface, tone, density = fn(page, S, ctx)
            all_nodes = list(lint.walk({"t": "box", "children": kids}))
            if name == "numbered-cards":
                # numbered cards are led by a big ordinal, not an icon
                self.assertTrue(any(n.get("text", "").strip() in ("01", "02", "03")
                                    for n in all_nodes if n["t"] == "text"))
                self.assertTrue(any(n.get("fill") == u("accent")
                                    for n in all_nodes if n["t"] == "box"))
            else:
                self.assertTrue(any(n["t"] == "icon" for n in all_nodes),
                                f"{name} produced no icon nodes")
            slide = {"type": "content", "tone": tone, "surface": surface,
                     "composition": "freeform", "archetype": name,
                     "density": density, "children": kids}
            d = deck([slide])
            layout.layout_deck(d)
            res = lint.lint_deck(d)
            self.assertNotIn("ICON_NAME",
                             [e["code"] for e in res["errors"]],
                             f"{name}: {res['errors']}")


class TestOuterShadow(unittest.TestCase):
    def _card(self, **kw):
        node = {"t": "card", "rect": [80, 80, 320, 200], "fill": WHITE,
                "children": []}
        node.update(kw)
        return freeform_slide([node])

    def test_none_emits_no_effect_list(self):
        # consulting theme token is "none": the legacy path only flips
        # shadow.inherit=False, which python-pptx serializes as an EMPTY
        # self-closing effectLst. The zero-regression contract is therefore
        # "no outerShdw child", not "no effectLst element at all".
        path = build(deck([self._card()]))
        xml = slide_xml(path)
        self.assertNotIn("outerShdw", xml)
        self.assertIn("<a:effectLst/>", xml)

    def test_soft_shadow_injects_outer_shadow_preset(self):
        path = build(deck([self._card(shadow="soft")]))
        xml = slide_xml(path)
        self.assertIn("<a:outerShdw", xml)
        self.assertIn('blurRad="90000"', xml)
        self.assertIn('dist="25000"', xml)
        self.assertIn('dir="5400000"', xml)  # 90deg, straight down
        self.assertIn('<a:alpha val="18000"/>', xml)  # 18% opacity
        self.assertIn('val="1F2937"', xml)  # default shadow color

    def test_medium_preset_and_custom_shadow_color(self):
        path = build(deck([self._card(shadow="medium",
                                      shadow_color="#112233")]))
        xml = slide_xml(path)
        self.assertIn('blurRad="140000"', xml)
        self.assertIn('dist="40000"', xml)
        self.assertIn('<a:alpha val="26000"/>', xml)
        self.assertIn('val="112233"', xml)

    def test_boolean_true_resolves_to_soft(self):
        path = build(deck([self._card(shadow=True)]))
        self.assertIn("<a:outerShdw", slide_xml(path))

    def test_theme_soft_token_applies_without_node_field(self):
        d = deck([self._card()])
        d["theme"] = "tech"  # tech visual.shadow == "soft"
        path = build(d)
        self.assertIn("<a:outerShdw", slide_xml(path))

    def test_node_none_overrides_soft_theme_token(self):
        d = deck([self._card(shadow="none")])
        d["theme"] = "tech"
        path = build(d)
        self.assertNotIn("outerShdw", slide_xml(path))

    def test_node_soft_overrides_none_theme_token(self):
        d = deck([self._card(shadow="soft")])  # consulting token is none
        path = build(d)
        self.assertIn("<a:outerShdw", slide_xml(path))

    def test_shadow_on_richcard_and_shape_nodes(self):
        slides = freeform_slide([
            {"t": "richcard", "rect": [80, 80, 300, 140], "fill": WHITE,
             "shadow": "soft",
             "blocks": [{"text": "卡片", "size": 18, "color": NAVY}]},
            {"t": "shape", "kind": "roundrect", "rect": [80, 260, 200, 120],
             "fill": ACCENT, "shadow": "soft"},
        ])
        path = build(deck([slides]))
        self.assertEqual(slide_xml(path).count("<a:outerShdw"), 2)

    def test_lint_rejects_unknown_shadow_level(self):
        d = deck([self._card(shadow="heavy")])
        layout.layout_deck(d)
        codes = {e["code"] for e in lint.lint_deck(d)["errors"]}
        self.assertIn("SHADOW_VALUE", codes)

    def test_lint_accepts_every_legal_shadow_value(self):
        for val in ("none", "soft", "medium", True, False):
            d = deck([self._card(shadow=val)])
            layout.layout_deck(d)
            codes = {e["code"] for e in lint.lint_deck(d)["errors"]}
            self.assertNotIn("SHADOW_VALUE", codes, f"rejected legal value {val!r}")

    def test_debug_render_draws_soft_shadow_without_error(self):
        d = deck([self._card(shadow="soft")])
        layout.layout_deck(d)
        out_dir = tempfile.mkdtemp()
        pngs = debug_render.render(d, out_dir)
        self.assertEqual(len(pngs), 1)
        self.assertTrue(os.path.exists(pngs[0]))


if __name__ == "__main__":
    unittest.main()
