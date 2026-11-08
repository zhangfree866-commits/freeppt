"""Tests for the `verify` acceptance CLI (human report + exit codes).

cmd_verify is a thin aggregate over lint_deck, so these tests pin the contract
that an automation pipeline relies on: 0 = pass, 1 = build-blocking errors,
2 = --strict with advisory warnings, plus the --json passthrough.
"""

import json
import os
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.cli import cmd_verify  # noqa: E402

NAVY = "#061F32"
WHITE = "#FFFFFF"


def _write_deck(children):
    deck = {"theme": "consulting", "composed": False, "slides": [{
        "type": "content", "composition": "freeform", "tone": "light",
        "children": children}]}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(deck, f, ensure_ascii=False)
    return path


def _args(path, strict=False, as_json=False):
    return types.SimpleNamespace(deck=path, strict=strict, json=as_json)


def _surface(rect, fill=NAVY):
    return {"t": "shape", "kind": "rect", "rect": list(rect), "fill": fill}


class TestVerifyCli(unittest.TestCase):
    def test_clean_deck_exits_zero(self):
        path = _write_deck([_surface([200, 200, 300, 200])])
        self.assertEqual(cmd_verify(_args(path)), 0)

    def test_error_deck_exits_one(self):
        # shape runs past the 1280x720 canvas -> OUT_OF_CANVAS error
        path = _write_deck([_surface([1100, 200, 400, 200])])
        self.assertEqual(cmd_verify(_args(path)), 1)

    def test_strict_warning_exits_two(self):
        # two surfaces 4px apart vertically -> GEOMETRY_NEAR_TOUCH warning
        children = [_surface([200, 200, 300, 200]),
                    _surface([200, 404, 300, 200], fill=WHITE)]
        path = _write_deck(children)
        self.assertEqual(cmd_verify(_args(path)), 0)            # warning alone passes
        self.assertEqual(cmd_verify(_args(path, strict=True)), 2)

    def test_strict_info_only_passes(self):
        # a fact-like statement without a source is info-level: a measurement,
        # not a defect. --strict must not fail on it.
        deck = {"theme": "consulting", "composed": False, "slides": [{
            "type": "content", "composition": "freeform", "tone": "light",
            "children": [{"t": "text", "rect": [100, 120, 600, 60],
                          "text": "已服务超过 100 万用户。", "size": 24,
                          "color": NAVY, "on": "#FFFFFF"}]}]}
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(deck, f, ensure_ascii=False)
        self.assertEqual(cmd_verify(_args(path, strict=True)), 0)

    def test_json_mode_still_returns_zero(self):
        path = _write_deck([_surface([200, 200, 300, 200])])
        self.assertEqual(cmd_verify(_args(path, as_json=True)), 0)


if __name__ == "__main__":
    unittest.main()
