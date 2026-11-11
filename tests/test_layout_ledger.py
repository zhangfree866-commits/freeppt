"""版式账本重复检测硬闸的单元测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import layout_ledger as ll


def e(index, pn, lid, family, chrome, special=False):
    return {"index": index, "pn": pn, "layout_id": lid,
            "family": family, "chrome": chrome, "special": special}


class TestLayoutLedger(unittest.TestCase):

    def test_clean_ledger_passes(self):
        ledger = {
            "family_gap": 2,
            "entries": [
                e(0, "P1", "cov", "cover", "cover", special=True),
                e(1, "P2", "a__1", "famA", "topq"),
                e(2, "P3", "b__1", "famB", "qband"),
                e(3, "P4", "a__2", "famA", "toponly"),
            ],
        }
        r = ll.validate(ledger)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["total"], 4)
        self.assertEqual(r["generic"], 3)

    def test_duplicate_layout_id_detected(self):
        ledger = {
            "family_gap": 0,
            "entries": [
                e(0, "P1", "same-id", "famA", "topq"),
                e(1, "P2", "same-id", "famB", "qband"),
            ],
        }
        r = ll.validate(ledger)
        self.assertFalse(r["ok"])
        self.assertTrue(any("duplicate layout_id" in x for x in r["errors"]))

    def test_adjacent_same_family_detected(self):
        ledger = {
            "family_gap": 0,
            "entries": [
                e(0, "P1", "a__1", "famA", "topq"),
                e(1, "P2", "a__2", "famA", "qband"),
            ],
        }
        r = ll.validate(ledger)
        self.assertFalse(r["ok"])
        self.assertTrue(any("adjacent same family" in x for x in r["errors"]))

    def test_adjacent_same_chrome_detected(self):
        ledger = {
            "family_gap": 0,
            "entries": [
                e(0, "P1", "a__1", "famA", "topq"),
                e(1, "P2", "b__1", "famB", "topq"),
            ],
        }
        r = ll.validate(ledger)
        self.assertFalse(r["ok"])
        self.assertTrue(any("adjacent same chrome" in x for x in r["errors"]))

    def test_family_gap_violation_detected(self):
        ledger = {
            "family_gap": 5,
            "entries": [
                e(0, "P1", "a__1", "famA", "topq"),
                e(1, "P2", "b__1", "famB", "qband"),
                e(2, "P3", "a__2", "famA", "toponly"),   # gap = 2 < 5
            ],
        }
        r = ll.validate(ledger)
        self.assertFalse(r["ok"])
        self.assertTrue(any("gap" in x for x in r["errors"]))

    def test_special_pages_excluded_from_gap(self):
        # special 页不参与间隔与相邻判断
        ledger = {
            "family_gap": 5,
            "entries": [
                e(0, "P1", "a__1", "famA", "topq"),
                e(1, "P2", "chap", "chapter", "chapter", special=True),
                e(2, "P3", "a__2", "famA", "toponly"),   # 通用间隔=2 < 5
            ],
        }
        r = ll.validate(ledger)
        # 两个通用页仍算间隔不足（special 不占位）
        self.assertFalse(r["ok"])

    def test_missing_layout_id_detected(self):
        ledger = {
            "family_gap": 0,
            "entries": [{"index": 0, "pn": "P1", "family": "a",
                         "chrome": "topq"}],
        }
        r = ll.validate(ledger)
        self.assertFalse(r["ok"])
        self.assertTrue(any("missing layout_id" in x for x in r["errors"]))


if __name__ == "__main__":
    unittest.main()
