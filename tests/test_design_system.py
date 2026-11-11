"""模型驱动设计系统提炼的单元测试（scaffold / validate）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import design_system as ds


def _fill_every_value(node):
    if isinstance(node, dict):
        if set(("_prompt", "value")) <= set(node):
            node["value"] = "x"
            node["confidence"] = "high"
            node["evidence"] = "seen"
        for v in node.values():
            _fill_every_value(v)
    elif isinstance(node, list):
        for v in node:
            _fill_every_value(v)


class TestDesignSystem(unittest.TestCase):

    def test_scaffold_has_all_dimensions(self):
        card, md = ds.scaffold("/tmp/ref.png", "书")
        for key, _, _ in ds.DIMENSIONS:
            self.assertIn(key, card["dimensions"])
        for rk, _ in ds.REUSE_FIELDS:
            self.assertIn(rk, card["reuse"])
        self.assertIn("设计系统提炼清单", md)

    def test_blank_card_is_invalid(self):
        card, _ = ds.scaffold("/tmp/ref.png")
        ok, report = ds.validate(card)
        self.assertFalse(ok)
        self.assertTrue(report["missing"])
        self.assertTrue(any("approved" in n for n in report["notes"]))

    def test_filled_and_approved_is_valid(self):
        card, _ = ds.scaffold("/tmp/ref.png")
        _fill_every_value(card)
        # 填值后仍未 approved -> 内容齐了但不能铺全本；内容完整应通过 ok
        ok, report = ds.validate(card)
        self.assertTrue(ok)
        self.assertEqual(report["missing"], [])
        self.assertTrue(any("approved" in n for n in report["notes"]))


if __name__ == "__main__":
    unittest.main()
