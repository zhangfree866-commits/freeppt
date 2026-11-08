"""Tests for the deck-level text-quality gate (advisory/info-level).

Mirrors the acceptance criteria a user holds a generated deck to: no typos,
no copy-paste duplicates across slides, and fact-like statements that carry
a research-ledger source. All deterministic — the gate never "understands"
prose, it flags well-known slip classes:

* TYPO_FOUND     advisory  — deterministic Chinese typo pair hit.
* TEXT_DUP       advisory  — the same >= 10-char sentence recurs on two
                            different slides.
* FACT_UNSOURCED info      — a fact-like statement on a slide without a
                            `sources`/`source` record. Info-level by design:
                            the engine cannot verify facts itself.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import layout, lint  # noqa: E402

NAVY = "#061F32"


def lint_deck(slides):
    deck = {"theme": "consulting", "composed": False, "slides": slides}
    layout.layout_deck(deck)
    return lint.lint_deck(deck)


def freeform_slide(text, source=None):
    children = [{"t": "text", "rect": [100, 120, 600, 60],
                 "text": text, "size": 24, "color": NAVY, "on": "#FFFFFF"}]
    slide = {"type": "content", "composition": "freeform", "tone": "light",
             "children": children}
    if source is not None:
        slide["sources"] = source
    return slide


def codes(res):
    return [w["code"] for w in res["warnings"]]


class TestTypoFound(unittest.TestCase):
    def test_common_typo_pair_is_flagged(self):
        res = lint_deck([freeform_slide("请先登陆系统再操作。")])
        self.assertIn("TYPO_FOUND", codes(res))

    def test_typo_reported_once_per_slide(self):
        res = lint_deck([freeform_slide("请登陆后使用帐户信息。")])
        self.assertEqual(codes(res).count("TYPO_FOUND"), 2)  # 登陆 + 帐户

    def test_clean_prose_is_quiet(self):
        res = lint_deck([freeform_slide("请先登录系统，再使用账户信息。")])
        self.assertNotIn("TYPO_FOUND", codes(res))

    def test_typo_is_advisory_and_never_blocks(self):
        res = lint_deck([freeform_slide("请先登陆系统。")])
        self.assertTrue(res["ok"])
        hits = [w for w in res["warnings"] if w["code"] == "TYPO_FOUND"]
        self.assertTrue(all(h["severity"] == "advisory" for h in hits))


class TestTextDup(unittest.TestCase):
    def test_long_duplicate_across_slides_is_flagged(self):
        res = lint_deck([
            freeform_slide("资源有限时，分配规则决定协作效率。"),
            freeform_slide("资源有限时，分配规则决定协作效率。"),
        ])
        self.assertIn("TEXT_DUP", codes(res))

    def test_short_shared_strings_are_ignored(self):
        # "小结" and similar short labels legitimately recur
        res = lint_deck([
            freeform_slide("小结"),
            freeform_slide("小结"),
        ])
        self.assertNotIn("TEXT_DUP", codes(res))

    def test_duplicate_reported_on_later_slide_only(self):
        res = lint_deck([
            freeform_slide("资源有限时，分配规则决定协作效率。"),
            freeform_slide("资源有限时，分配规则决定协作效率。"),
        ])
        hits = [w for w in res["warnings"] if w["code"] == "TEXT_DUP"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["slide"], 2)


class TestFactUnsourced(unittest.TestCase):
    def test_figure_without_source_is_info(self):
        res = lint_deck([freeform_slide("该方案已服务超过 100 万用户。")])
        self.assertIn("FACT_UNSOURCED", codes(res))

    def test_year_statement_without_source_is_info(self):
        res = lint_deck([freeform_slide("公司于 2015 年成立。")])
        self.assertIn("FACT_UNSOURCED", codes(res))

    def test_rank_words_without_source_are_info(self):
        res = lint_deck([freeform_slide("市场份额排名第一。")])
        self.assertIn("FACT_UNSOURCED", codes(res))

    def test_sourced_slide_is_quiet(self):
        res = lint_deck([freeform_slide(
            "该方案已服务超过 100 万用户。",
            source=[{"title": "内部年报", "publisher": "公司"}]),
        ])
        self.assertNotIn("FACT_UNSOURCED", codes(res))

    def test_plain_prose_is_quiet(self):
        res = lint_deck([freeform_slide("资源有限时，分配规则决定协作效率。")])
        self.assertNotIn("FACT_UNSOURCED", codes(res))

    def test_fact_unsourced_is_info_tier(self):
        res = lint_deck([freeform_slide("该方案已服务超过 100 万用户。")])
        self.assertTrue(res["ok"])
        hits = [w for w in res["warnings"] if w["code"] == "FACT_UNSOURCED"]
        self.assertTrue(all(h["severity"] == "info" for h in hits))


class TestGateIntegration(unittest.TestCase):
    def test_new_diagnostics_respect_three_tier_contract(self):
        deck = {"theme": "consulting", "composed": False, "slides": [
            freeform_slide("请登陆系统，已服务超过 100 万用户。"),
            freeform_slide("请登陆系统，已服务超过 100 万用户。"),
        ]}
        layout.layout_deck(deck)
        res = lint.lint_deck(deck)
        for item in res["errors"] + res["warnings"]:
            self.assertIn(item["severity"], {"blocker", "advisory", "info"})
        self.assertTrue(res["ok"])  # nothing here is a blocker


if __name__ == "__main__":
    unittest.main()
