"""把讲稿写进成品 pptx——两条通道，别搞混。

**正路：模型逐页写，`fill_notes_from_file()` 只负责写。**
每一页怎么开场，取决于这一页在讲什么：封面是欢迎+这本书要解决什么，数据页是
"看这个数字它反常识在哪"，案例页是"先讲情形再讲判断"。这个判断只有模型能下。
所以正路是模型先产出讲稿 JSON，再灌进 pptx——引擎不生成一个字。

**急救：`fill_notes()` 只重组页内文字。**
存在的理由是「备注空着比有草稿更糟」。但它的能力边界必须说清：既然只能重组
页内文字，每页就必然长成同一个模子。实测 91 页产物字数达标、覆盖 100%，可
结尾 12 字 91 页全同、87 页连接词序列一字不差——`audit-notes` 判它「模板化」
不通过。**这是对的行为**：字数够不等于讲得出口，模板化必须被拦下。

写作纪律（两条通道都适用）：
* 不生成页面外的事实、不编造数字。宁可讲得朴素，也不许出现页面上没有的数据。
* 已有非空备注默认不覆盖，要重写用 `overwrite=True`。
* 确定性：同一份输入两次运行结果逐字一致，便于 diff 与回归。
"""

import re

# 抽取页面文字时的分类线索（按形状名与文本特征，不依赖 DSL 语义）
_HEADISH_MAX = 30       # 短文本更可能是标题/小标题
_BODY_MIN = 8           # 正文块下限：章节页的副标题常是 15–28 字，不能滤掉

# 章编号 / 页码 / 英文小标这类「不是标题的标题」：章节页第一块常是 "02"
# 或 "MODULE 04 / BOUNDARIES"，把它当标题会让整页讲稿变成「这一页讲的是 02」。
_NOISE_RE = re.compile(
    r"""^(?:
        \d{1,3}                          # 纯数字：章节号
      | [Pp]\.?\s*\d{1,3}                # P26 / p.26
      | \d{1,3}\s*/\s*\d{1,3}            # 26 / 91
      | (?:MODULE|PART|CHAPTER|CH)\b.*   # MODULE 04 / THE LEAP
      | [A-Z][A-Z0-9 /&·\-]{2,}$         # 全大写英文小标
    )$""",
    re.VERBOSE,
)


def _is_noise(text):
    """章编号、页码、英文小标——不是这页的主张。"""
    return bool(_NOISE_RE.match(text.strip()))


def _shape_text(sh):
    if not sh.has_text_frame:
        return ""
    return "\n".join(p.text for p in sh.text_frame.paragraphs).strip()


def _page_texts(slide):
    """按纵向位置给页面文字排序，切出「标题 / 正文块」两类。

    只用几何位置与长度，不猜业务语义——这样对任何来源的 pptx 都成立。
    章编号与页码先剔除，避免章节页的讲稿变成「这一页讲的是 02」。
    """
    items = []
    for sh in slide.shapes:
        t = _shape_text(sh)
        if not t:
            continue
        try:
            top = int(sh.top or 0)
        except (TypeError, ValueError):
            top = 0
        items.append((top, t))
    items.sort(key=lambda kv: kv[0])

    texts = [t for _top, t in items]
    if not texts:
        return "", []

    # 标题 = 最靠上、且不是编号噪音、且不太长的那一块。只取一次，
    # 后面所有块都归正文——否则短副标题会被误当第二个标题。
    head = ""
    rest = list(texts)
    for idx, t in enumerate(texts):
        if not _is_noise(t) and len(t) <= _HEADISH_MAX:
            head = t
            rest = texts[:idx] + texts[idx + 1:]
            break
    if not head:
        # 没有短标题时，退一步用第一个非噪音块的前 40 字
        for idx, t in enumerate(texts):
            if not _is_noise(t):
                head = t[:40]
                rest = texts[:idx] + texts[idx + 1:]
                break
    if not head:
        return "", []

    bodies = [t for t in rest if len(t) >= _BODY_MIN and not _is_noise(t)]
    return head, bodies


def _compose_note(head, bodies, page_no, total):
    """把页面已有文字组织成口语化讲稿。不引入任何页面外信息。"""
    parts = []
    if head:
        parts.append(f"这一页讲的是「{head}」。")

    # 去重：同一段文字常同时存在于多个形状里（标题+正文重复、图表标签与
    # 说明重叠、多行文本框各持半句）。三种情形都要拦住：
    #   1) 完全包含        2) 一方是另一方的前缀（半句 + 全句）
    #   3) 前 12 字相同（同一句被不同宽度文本框切断）
    # 保留先出现的较长者。
    def _norm(s):
        return re.sub(r"\s+", "", s)

    kept = []
    for body in bodies:
        n = _norm(body)
        dup_of = None
        for k in range(len(kept)):
            kn = _norm(kept[k])
            if n in kn or kn in n:
                dup_of = k
                break
            if len(n) >= 12 and len(kn) >= 12 and n[:12] == kn[:12]:
                dup_of = k
                break
        if dup_of is None:
            kept.append(body)
        elif len(n) > len(_norm(kept[dup_of])):
            kept[dup_of] = body
    uniq = kept

    for i, body in enumerate(uniq[:4]):
        lead = ["具体来说，", "这里要注意的是，", "进一步看，", "同时，", "最后，"][min(i, 4)]
        # 页内文字常被硬换行切断（"英伟\n达"），先归一化空白再引用，
        # 否则讲稿里会出现半截词。
        clean = re.sub(r"\s+", "", body)
        if len(clean) > 160:
            clean = clean[:157] + "…"
        # 每块以句号收尾，避免多块连成一串没有停顿的长句
        if clean and clean[-1] not in "。！？…":
            clean += "。"
        parts.append(lead + clean)

    if not parts:
        parts.append(f"这是第 {page_no} 页，我们结合页面上的结构梳理要点。")

    parts.append("讲解时可以停一下，请大家对照自己手上的材料想一想。")
    return "".join(parts)


def fill_notes_from_file(pptx_path, notes_json, out_path=None, overwrite=False):
    """把**模型逐页写好**的讲稿写进 pptx——这才是正路。

    `fill_notes()` 是急救通道：它只能重组页内已有文字，因而必然带模板痕迹
    （实测 91 页结尾 100% 相同）。真讲稿的每一页开场取决于这一页在讲什么，
    这个判断只有模型能下。所以这里不生成任何文字，只做一件事：把模型给的
    讲稿按页号写进去，缺页报错而不是拿模板顶上。

    notes_json 形态（数组，按页顺序；也可用 {"pages":[{page, text}]} 显式指定页号）：
        ["第1页讲稿", "第2页讲稿", ...]
        [{"page": 1, "text": "..."}, ...]

    参数：
        overwrite  默认只填空页；已有讲稿的页保持不动
    返回 dict：written / skipped / missing（模型没给讲稿的页号）/ out
    """
    import json

    from pptx import Presentation

    with open(notes_json, encoding="utf-8") as f:
        spec = json.load(f)

    if isinstance(spec, dict):
        spec = spec.get("pages") or spec.get("notes") or []

    # 统一成 {页号: 讲稿}
    by_page = {}
    if spec and isinstance(spec[0], dict):
        for item in spec:
            no = int(item.get("page") or item.get("no") or 0)
            if no:
                by_page[no] = (item.get("text") or item.get("notes") or "").strip()
    else:
        for idx, text in enumerate(spec, 1):
            by_page[idx] = (text or "").strip()

    prs = Presentation(pptx_path)
    slides = list(prs.slides)
    total = len(slides)

    written, skipped = [], []
    for i, s in enumerate(slides, 1):
        existing = ""
        if s.has_notes_slide:
            try:
                existing = (s.notes_slide.notes_text_frame.text or "").strip()
            except (AttributeError, KeyError):
                existing = ""

        if existing and not overwrite:
            skipped.append(i)
            continue

        text = by_page.get(i, "")
        if not text:
            continue        # 模型没给这页写，就不动它——不拿模板顶上

        tf = s.notes_slide.notes_text_frame
        tf.clear()
        tf.text = text
        written.append(i)

    missing = sorted(set(range(1, total + 1)) - set(by_page))

    target = out_path or pptx_path
    prs.save(target)
    return {
        "total": total,
        "written": len(written),
        "skipped": len(skipped),
        "missing": missing,
        "written_pages": written,
        "out": target,
    }


def fill_notes(pptx_path, out_path=None, overwrite=False, min_len=10):
    """给成品 pptx 回填演讲者备注——**急救通道，不是正路**。

    ⚠ 明确它的能力边界：这里只重组页内已有文字，因此每页的讲法必带同一个
    模子的痕迹。实测 91 页产物：字数达标（均 202.6）、覆盖 100%，但结尾
    12 字 91 页全同、开头 91 页全同、87 页连接词序列一字不差——`audit-notes`
    会判它 `模板化` 不通过。这符合预期：**真讲稿只能由模型逐页判断**，
    用 `fill_notes_from_file()` 写入。本函数只用于「先把空备注补上，别空着」

    参数：
        pptx_path  源文件
        out_path   输出路径；None 时覆盖源文件
        overwrite  为真则重写已有备注；默认只补空缺
        min_len    已有备注短于此值也算空缺（默认 10，只补真正的空页）

    返回 dict：filled 页数、skipped 页数、总页数、输出路径。
    """
    from pptx import Presentation

    prs = Presentation(pptx_path)
    slides = list(prs.slides)
    total = len(slides)

    filled, skipped = [], []
    for i, s in enumerate(slides, 1):
        existing = ""
        if s.has_notes_slide:
            try:
                existing = (s.notes_slide.notes_text_frame.text or "").strip()
            except (AttributeError, KeyError):
                existing = ""

        if existing and len(existing) >= min_len and not overwrite:
            skipped.append(i)
            continue

        head, bodies = _page_texts(s)
        note = _compose_note(head, bodies, i, total)

        tf = s.notes_slide.notes_text_frame
        tf.clear()
        tf.text = note
        filled.append(i)

    target = out_path or pptx_path
    prs.save(target)
    return {
        "total": total,
        "filled": len(filled),
        "skipped": len(skipped),
        "filled_pages": filled,
        "out": target,
    }
