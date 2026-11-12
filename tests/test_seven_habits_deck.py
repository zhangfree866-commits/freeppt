# -*- coding: utf-8 -*-
"""完整 10 页 deck 构建器的回归测试。

这个构建器是「拿参照语法做一本完整的书」的产物，直接服务于最高目标。钉住三件事：
1. 产出确实是 10 页；
2. audit_design 判 ok（含 0 字压字、0 出界）；
3. 每页都有真实结构件，不是 10 个白页。
"""

import os
import tempfile

import pytest

from engine.seven_habits_deck import build_seven_habits_deck
from engine.design_audit import audit_design


@pytest.fixture(scope="module")
def deck_path():
    prs = build_seven_habits_deck()
    assert len(prs.slides) == 10
    fd, path = tempfile.mkstemp(suffix=".pptx")
    os.close(fd)
    prs.save(path)
    yield path
    os.remove(path)


def test_deck_has_ten_pages(deck_path):
    r = audit_design(deck_path)
    assert r["slide_count"] == 10
    assert len(r["per_page"]) == 10


def test_deck_passes_design_audit(deck_path):
    r = audit_design(deck_path)
    assert r["ok"] is True
    assert r["collisions"] == []
    assert r["clipped"] == []


def test_every_page_has_structure(deck_path):
    r = audit_design(deck_path)
    for p in r["per_page"]:
        assert p["shapes"] >= 10, f"第 {p['page']} 页形状过少"
        assert p["dividers"] >= 1, f"第 {p['page']} 页缺分隔线"
