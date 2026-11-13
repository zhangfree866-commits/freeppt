# -*- coding: utf-8 -*-
"""原型必须是「构件」，不是「模板」。

守的一条：**同一个 archetype 装不同内容，必须排出不同的几何。**

来历（2026-11-13，用户第三次追问「做到 skill 要求了吗」）：
拿两本成品的几何骨架做哈希对比，《人情与面子》和《11枚戒指》的封面、章节页、
引言页、左右对照、大数字、收束页**骨架哈希完全相同**——逐像素一样。
书内不重复只是因为换了原型名，原型本身的坐标全是常量。
这就是「先从模板库里挑一个、再往里填字」，只是把模板叫成了 archetype。

修法是把「固定坐标」换成「由这一页内容算出的骨架参数」。下面每条测试
钉住一个原型：两页内容不同 → 骨架必须不同；内容相同 → 必须可复现。
"""

import copy
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import art_direction as ad          # noqa: E402
from engine import themes as T                  # noqa: E402


S = None


def setUpModule():
    global S
    S = ad._style(T.get_theme("magazine"), "magazine")


def geometry(children):
    """几何骨架指纹：只取非文字结构件的坐标，不看文字内容。"""
    rects = []
    for c in children:
        kind = f"{c.get('t', '')} {c.get('kind', '')}".lower()
        if "text" in kind:
            continue
        r = c.get("rect") or c.get("box")
        if r:
            rects.append(tuple(round(float(v) / 4) for v in r[:4]))
    return hashlib.md5(str(sorted(rects)).encode()).hexdigest()


def ctx(i=0, total=10, book=None, rng=None):
    import random
    return {"idx": i, "total": total, "rng": rng or random.Random(7),
            "book": book or {"title": "书", "author": "作者"},
            "cover_file": None}


# 两组内容：一组「轻」（短标题、少条目、少字），一组「重」（长标题、
# 多条、近满版）。同一原型喂这两组，几何必须不同。
LIGHT = {
    "title": "短标题",
    "lead": "一句话。",
    "points": [{"head": "甲", "body": "略。"}, {"head": "乙", "body": "略。"}],
    "note": "短注。",
    "value": "1987",
    "label": "一个年份",
    "quote": "一句话的追问。",
    "left": {"head": "左", "body": "短。"},
    "right": {"head": "右", "body": "短。"},
}

HEAVY = {
    "title": "这是一个明显更长的标题，长到必然改变版面的骨架与呼吸节奏",
    "lead": "导语也长得多，需要占掉整行甚至两行的宽度，"
            "于是版面必须重新分配空间，而不能沿用短导语时的坐标。",
    "points": [
        {"head": "第一条比较长的命题标题", "body": "正文相当长，" * 6},
        {"head": "第二条比较长的命题标题", "body": "正文相当长，" * 6},
        {"head": "第三条比较长的命题标题", "body": "正文相当长，" * 6},
        {"head": "第四条比较长的命题标题", "body": "正文相当长，" * 6},
    ],
    "note": "批注也长：" + "这里是一段需要换行的说明文字。" * 4,
    "value": "1996-1998",
    "label": "一个更长的说明标签，需要换行才能放下",
    "quote": "当一句话变得足够长，它就不能再用四十四磅占据页面中部，"
             "否则一定会折成六行并越过版心，所以字号和起点都必须重新算。",
    "left": {"head": "左半的标题", "body": "左侧正文。" * 14},
    "right": {"head": "右半的标题", "body": "右侧正文少些。" * 5},
}


def _build(fn, page, **kw):
    import random
    c = ctx(rng=random.Random(11), **kw)
    kids, *_ = fn(copy.deepcopy(page), S, c)
    return geometry(kids)


class TestSameArchetypeDifferentContent:
    """每个原型：轻内容 vs 重内容 → 几何必须不同。"""

    def _check(self, fn, page_light, page_heavy):
        g1 = _build(fn, page_light)
        g2 = _build(fn, page_heavy)
        assert g1 != g2, (
            f"{fn.__name__} 对轻重两种内容排出了完全相同的几何——"
            f"这就是「先有固定模板、再往里填」")

    def test_cover_editorial(self):
        import random
        a = ad.a_cover_editorial({"title": "短"}, S,
                                 ctx(book={"title": "人情与面子",
                                           "author": "黄光国"}))
        b = ad.a_cover_editorial({"title": "长"}, S,
                                 ctx(book={"title": "一个非常非常长的书名用来测试",
                                           "author": "某作者"}))
        assert geometry(a[0]) != geometry(b[0])

    def test_chapter_opener(self):
        self._check(ad.a_chapter_opener,
                    dict(LIGHT, no="01", en="EN"),
                    dict(HEAVY, no="01", en="A LONG ENGLISH SUBTITLE HERE"))

    def test_quote_bleed(self):
        import random
        a = ad.a_quote_bleed({"quote": "短句。"}, S, ctx(rng=random.Random(3)))
        b = ad.a_quote_bleed({"quote": "长句。" * 30}, S, ctx(rng=random.Random(3)))
        assert geometry(a[0]) != geometry(b[0])

    def test_split_contrast(self):
        self._check(ad.a_split_contrast, LIGHT, HEAVY)

    def test_data_focus(self):
        self._check(ad.a_data_focus, LIGHT, HEAVY)

    def test_closing_echo(self):
        a = ad.a_closing_echo({"title": "一句短结语"}, S, ctx())
        b = ad.a_closing_echo({"title": "一句明显更长的结语，长到必须让右色块变窄"},
                              S, ctx())
        assert geometry(a[0]) != geometry(b[0])


class TestDeterminism:
    """内容相同必须可复现——变体是内容驱动的，不是随机抖动。"""

    def test_same_content_same_geometry(self):
        import random
        g = [geometry(ad.a_split_contrast(copy.deepcopy(LIGHT), S,
                                          ctx(rng=random.Random(5)))[0])
             for _ in range(3)]
        assert len(set(g)) == 1

    def test_two_books_do_not_share_a_skeleton(self):
        """端到端回归：两本示例书里共用的原型，骨架不能有相同的。

        这条正是用户第三次追问时实测出来的缺陷：
        8 个共用原型里有 6 个骨架哈希完全相同。
        """
        import json
        import subprocess
        import tempfile

        pairs = [("examples/notes_renqing_mianzi.json",
                  "examples/briefs_renqing_mianzi.json"),
                 ("examples/notes_eleven_rings.json",
                  "examples/briefs_eleven_rings.json")]
        decks = []
        with tempfile.TemporaryDirectory() as td:
            for i, (notes, briefs) in enumerate(pairs):
                out = os.path.join(td, f"d{i}.json")
                subprocess.run(
                    [sys.executable, "engine/cli.py", "compose", notes,
                     "--briefs", briefs, "--out", out],
                    cwd=ROOT, check=True, capture_output=True)
                decks.append(json.load(open(out, encoding="utf-8")))

        a = {s["archetype"]: geometry(s["children"]) for s in decks[0]["slides"]}
        b = {s["archetype"]: geometry(s["children"]) for s in decks[1]["slides"]}
        shared = set(a) & set(b)
        assert shared, "两本书没有共用原型，这条测试失去意义"
        same = {k for k in shared if a[k] == b[k]}
        assert not same, (
            f"这些原型在两本书里排出了逐像素相同的几何：{sorted(same)}；"
            f"说明它们还是固定模板，不是构件")
