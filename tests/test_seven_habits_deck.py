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


def test_declares_its_own_boundary(deck_path):
    """钉住这个构建器的**性质**：它是判据基准，不是交付路径。

    它直接用 python-pptx 画坐标，**没有**逐页六维简报，也不经 `compose()`。
    所以它 `audit_design` 不过 `ok=True` 只能说明「判据所描述的水平真能做到」，
    不能说明「逐页当设计师」这条规则被满足了。把它当交付样例引用就是错的。
    """
    import inspect
    from engine import seven_habits_deck as mod

    src = inspect.getsource(mod)
    # 明确不 import 六维闸门 —— 一旦有人把它接进交付路径，这条会提醒他补简报
    assert "design_spec" not in src
    assert "require_deck" not in src
