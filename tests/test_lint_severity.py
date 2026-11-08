"""Tests for the three-tier severity model and human adjudication (`lint_ack`).

The acceptance language a deck is signed off in distinguishes "blocking
errors" from "non-blocking notes that are intentional whitespace". These tests
pin that contract:

* every diagnostic carries a severity tier;
* `errors` / `warnings` keep their historical meaning (advisories that are not
  yet adjudicated), so old callers and tests stay correct;
* an advisory can be adjudicated only with a written reason;
* a blocker can never be adjudicated;
* a stale ack surfaces instead of silently accumulating.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import layout, lint  # noqa: E402

NAVY = "#061F32"
WHITE = "#FFFFFF"


def _surface(rect, fill=NAVY):
    return {"t": "shape", "kind": "rect", "rect": list(rect), "fill": fill}


def _deck(children, acks=None):
    deck = {"theme": "consulting", "composed": False, "slides": [{
        "type": "content", "composition": "freeform", "tone": "light",
        "children": children}]}
    if acks is not None:
        deck["lint_ack"] = acks
    layout.layout_deck(deck)
    return lint.lint_deck(deck)


def _near_touch_children():
    """Two surfaces 4px apart vertically -> one GEOMETRY_NEAR_TOUCH advisory."""
    return [_surface([200, 200, 300, 200]),
            _surface([200, 404, 300, 200], fill=WHITE)]


def _overflow_deck():
    """A shape running past the canvas -> one OUT_OF_CANVAS blocker."""
    return _deck([_surface([1100, 200, 400, 200])])


class TestSeverityTiers(unittest.TestCase):
    def test_every_diagnostic_carries_a_severity(self):
        res = _deck(_near_touch_children())
        for item in res["errors"] + res["warnings"]:
            self.assertIn(item["severity"], {"blocker", "advisory", "info"})

    def test_hard_defect_is_a_blocker_and_blocks(self):
        res = _overflow_deck()
        self.assertFalse(res["ok"])
        blockers = [e for e in res["errors"] if e["severity"] == "blocker"]
        self.assertEqual([b["code"] for b in blockers], ["OUT_OF_CANVAS"])

    def test_geometric_suspicion_is_an_advisory_not_a_blocker(self):
        res = _deck(_near_touch_children())
        self.assertTrue(res["ok"])  # advisories never block
        self.assertEqual([w["code"] for w in res["warnings"]],
                         ["GEOMETRY_NEAR_TOUCH"])
        self.assertEqual(res["warnings"][0]["severity"], "advisory")

    def test_summary_counts_match_the_lists(self):
        res = _deck(_near_touch_children())
        s = res["severity_summary"]
        self.assertEqual(s["blockers"], len(res["errors"]))
        self.assertEqual(s["advisories"],
                         len([w for w in res["warnings"]
                              if w["severity"] == "advisory"]))
        self.assertEqual(s["acked"], len(res["acked"]))

    def test_ok_true_when_only_advisories_remain(self):
        self.assertTrue(_deck(_near_touch_children())["ok"])


class TestAdjudication(unittest.TestCase):
    def test_ack_with_reason_clears_the_advisory(self):
        res = _deck(_near_touch_children(), acks=[
            {"code": "GEOMETRY_NEAR_TOUCH",
             "reason": "刻意的 4px 密排，视觉上是同一条带的分段"}])
        self.assertEqual(res["warnings"], [])            # nothing left open
        self.assertEqual(len(res["acked"]), 1)           # but it is on record
        self.assertEqual(res["acked"][0]["code"], "GEOMETRY_NEAR_TOUCH")
        self.assertIn("刻意的", res["acked"][0]["acked_reason"])
        self.assertTrue(res["ok"])

    def test_ack_without_reason_is_rejected(self):
        # a bare suppression is not an adjudication
        res = _deck(_near_touch_children(),
                    acks=[{"code": "GEOMETRY_NEAR_TOUCH"}])
        self.assertEqual(len([w for w in res["warnings"]
                              if w["code"] == "GEOMETRY_NEAR_TOUCH"]), 1)
        self.assertIn("LINT_ACK_INVALID",
                      [w["code"] for w in res["warnings"]])

    def test_ack_on_blocker_is_refused(self):
        res = _deck([_surface([1100, 200, 400, 200])],
                    acks=[{"code": "OUT_OF_CANVAS", "reason": "我觉得没问题"}])
        self.assertFalse(res["ok"])                      # still blocked
        self.assertIn("LINT_ACK_ON_BLOCKER",
                      [w["code"] for w in res["warnings"]])
        self.assertEqual(res["acked"], [])

    def test_ack_is_scoped_by_slide(self):
        deck = {"theme": "consulting", "composed": False, "slides": [
            {"type": "content", "composition": "freeform", "tone": "light",
             "children": _near_touch_children()},
            {"type": "content", "composition": "freeform", "tone": "light",
             "children": _near_touch_children()},
        ], "lint_ack": [{"code": "GEOMETRY_NEAR_TOUCH", "slide": 1,
                         "reason": "第一页刻意密排"}]}
        layout.layout_deck(deck)
        res = lint.lint_deck(deck)
        # slide 1 adjudicated, slide 2 still open
        self.assertEqual([w["slide"] for w in res["warnings"]
                          if w["code"] == "GEOMETRY_NEAR_TOUCH"], [2])
        self.assertEqual([a["slide"] for a in res["acked"]], [1])

    def test_unscoped_ack_covers_every_occurrence(self):
        deck = {"theme": "consulting", "composed": False, "slides": [
            {"type": "content", "composition": "freeform", "tone": "light",
             "children": _near_touch_children()},
            {"type": "content", "composition": "freeform", "tone": "light",
             "children": _near_touch_children()},
        ], "lint_ack": [{"code": "GEOMETRY_NEAR_TOUCH",
                         "reason": "全篇统一的密排节奏"}]}
        layout.layout_deck(deck)
        res = lint.lint_deck(deck)
        self.assertEqual(res["warnings"], [])
        self.assertEqual(len(res["acked"]), 2)

    def test_stale_ack_is_reported_not_silently_dropped(self):
        res = _deck([_surface([200, 200, 300, 200])], acks=[
            {"code": "GEOMETRY_NEAR_TOUCH", "reason": "早就修掉了"}])
        codes = [w["code"] for w in res["warnings"]]
        self.assertIn("LINT_ACK_UNUSED", codes)
        info = [w for w in res["warnings"] if w["code"] == "LINT_ACK_UNUSED"][0]
        self.assertEqual(info["severity"], "info")   # a note, not a complaint

    def test_single_ack_object_is_tolerated(self):
        res = _deck(_near_touch_children(),
                    acks={"code": "GEOMETRY_NEAR_TOUCH", "reason": "单条写法"})
        self.assertEqual(res["warnings"], [])
        self.assertEqual(len(res["acked"]), 1)


class TestBackwardCompatibility(unittest.TestCase):
    def test_errors_and_warnings_keep_historical_meaning(self):
        """`ok` is exactly "no blocker", `warnings` is exactly "not yet acked"."""
        res = _overflow_deck()
        self.assertEqual(res["ok"], len(res["errors"]) == 0)
        self.assertEqual(
            res["ok"],
            res["severity_summary"]["blockers"] == 0)

    def test_report_groups_by_tier(self):
        from engine.cli import _verify_report
        deck = {"theme": "consulting", "composed": False,
                "slides": [{"type": "content", "composition": "freeform",
                            "tone": "light", "children": _near_touch_children()}]}
        res = _deck(_near_touch_children(), acks=[
            {"code": "GEOMETRY_NEAR_TOUCH", "reason": "刻意密排"}])
        text = _verify_report(deck, res)
        self.assertIn("ADJUDICATED (1)", text)
        self.assertIn("[ok]", text)
        self.assertIn("adjudicated with reasons", text)
        self.assertNotIn("BLOCKERS", text)


if __name__ == "__main__":
    unittest.main()
