"""版面设计审计——判「这一页有没有被设计过」，而不是「有没有配图」。

来历：用户拿出一份 10 页的参照（《高效能人士的七个习惯》精读），说「这个接近我的
要求，页面设计才是核心，备注可有可无」。实测解剖后发现，我之前一直在追的方向错了：

    参照 10 页          配图 0 张 | 每页 38.7 个形状 | 45 条分隔线 | 同骨架最多 3 页
    我方 91 页          配图 1 张 | 每页 26.0 个形状 |  0 条分隔线 | 同骨架最多 16 页

参照一张图都没有。它的版面质量来自三件事，跟图片完全无关：

1. **固定的页面框架**（chrome）：几乎每页都有同一套骨架件——横向页眉细线、
   页眉下的全长分隔线、左下角来源行、右下角页码。这让人觉得是「一本书」，
   而不是 10 张各画各的幻灯片。
2. **高密度结构件**：每页 10 个左右的色块/徽章/条带，45 条分隔线全篇铺开
   （水平线切分条目、竖线切分左右栏、8px 细条做项目符号）。
3. **每页一个不同的视觉论证**：阶梯（依赖→独立→互赖）、同心圆（关注圈/
   影响圈）、2×2 矩阵（时间管理四象限）、水平柱（毛利率对比）、
   三层递进带（1+1>2）……每个版面形状都是这页内容的论证结构，不是装饰。

所以判据不能是「配图数」。这里改判四件事：
    chrome      有没有那套页眉/页脚框架
    density     结构件密度够不够（区别于文字块数量）
    dividers    有没有真的用分隔线组织信息
    variety     视觉论证有没有变化（同骨架不能扎堆）
"""

import collections

# 结构件密度门槛。参照实测每页 38.7 个形状、其中结构件中位 17 个（最少 7 个：
# P6 那页用一条 22px 进度条表达「760/1160」，极简但成立）。
#
# 注意这两条的**性质**：密度是风格选择，不是缺陷。一份原生图表撑满一页的业务
# 报告只有 9 个形状，可它视觉上完全成立（图表本身就是版面结构）。而参照那种
# 密集编辑风是另一种成立的风格。把「密度」当硬拦条件，等于逼所有 deck 长成
# 同一副样子——那恰好是「逐页当设计师」要反对的。
# 所以密度降级为提示（advisory），只保留一条**极低的绝对下限**：连 3 个结构件
# 都不到、整页只有文字框在堆，那是真没做版面，仍然硬拦。
MIN_SHAPES_PER_PAGE = 20          # 提示用（不是硬拦）
MIN_STRUCTURE_PER_PAGE = 7        # 提示用（不是硬拦）
FLOOR_STRUCTURE_PER_PAGE = 2      # 硬拦下限：低于此值 = 纯文字堆叠
FLOOR_SHAPES_PER_PAGE = 4         # 硬拦下限：散布性兜底，防「一两个形状 + 大段文字」

# 同骨架允许的最大页数。参照 10 页里最大重复是 2–3（两三页用同一种论证是正常的，
# 比如「左图右栏编号条目」），我方 91 页最大重复 16。一本书里同一种论证复用
# 3–4 次可接受。
MAX_SAME_SKELETON = 4

# chrome 判定：页眉区（top < 120px）与页脚区（top > 640px）是否都有内容
HEADER_BAND = 120
FOOTER_BAND = 640

# 分隔线：参照全篇 45 条（每页 4.5 条），我方 91 页 **0 条**。
# 这不是「有没有都行」的装饰——水平线切分条目、竖线切分左右栏、细条做项目符号，
# 是它把信息组织起来的主要手段。全篇一条都没有，说明页面靠文字块堆叠，
# 没有用几何手段建立层级。
MIN_DIVIDER_PAGES_RATIO = 0.5

# 但「每页都要有分隔线」是**参照那一种风格**的组织手段，不是普适规则：
# 一刀 table-board、一页 split-contrast（靠色块对撞分栏）、一页
# numbered-cards（靠卡片本身分开），都不需要横线。用 50% 去判它们，
# 等于逼所有版式都长成密集编辑风。
# 所以：**零分隔线**才是硬缺陷（说明完全没用几何手段建立层级）；
# 覆盖率偏低只作为提示。
FLOOR_DIVIDER_PAGES = 1

# 仪式页（封面/封底/章节扉页）豁免密度判据。
# 依据：这类页的存在意义就是「少」——封面只有标题、署名、日期，密排结构反而是
# 设计错误。但识别不能只看「字少」：一份 4 个文字块的裸排布正文页字也少，
# 若一并豁免，密度判据就形同虚设。仪式页的真正特征是**巨型标题**——
# 最大字号 ≥28pt（封面主标题 40pt 起），且文字块不超过 5 个。
CEREMONIAL_MIN_FONT = 28.0
CEREMONIAL_MAX_BLOCKS = 5


def _px(v):
    return (v or 0) / 9525.0


def _slides_of(pptx_path):
    from pptx import Presentation
    return list(Presentation(pptx_path).slides)


def _shape_kind(sh):
    """按 pptx 形状类型分三类：structure（可视结构件）/ text / 其它。

    原生图表与表格算 structure，不算「数据」以外的旁支：一张撑满版面的图表
    **就是**这页的版面结构。之前把它们排除在外，导致「标题 + 大图表 + 来源行」
    这种干净的业务页被算成「结构件=0」，判成没做设计——判据把成立的设计判死，
    是比漏判更严重的错误。
    """
    t = str(getattr(sh, "shape_type", ""))
    if "TEXT_BOX" in t:
        return "text"
    if "LINE" in t or "AUTO_SHAPE" in t or "FREEFORM" in t:
        return "structure"
    if "PICTURE" in t:
        return "picture"
    if "TABLE" in t or "CHART" in t:
        return "data"
    return "other"


def _has_visible_text(sh):
    return sh.has_text_frame and bool(sh.text.strip())


def _text_boxes(slide):
    """取出每块可见文字的实际占位（已按字号估算真实高度）。

    question：为什么要估算而不是用 shape.height？
    因为 add_textbox 给的 h 只是「框」，文字实际占多少由字号和行数决定。
    PowerPoint 不会裁掉超出的字，它会溢出来盖住别人——所以判断重叠必须用
    真实文字高度，用框高会漏掉「框很小、字溢出来」这一整类问题。
    """
    import unicodedata
    out = []

    def _char_unit(ch):
        """一个字占多少 em：全宽中日韩字 1.0，西文与数字约 0.55，空格更窄。

        必须按字宽加权，不能把所有字符都算 1.0——参照 deck 的来源行含大量英文
        （Covey、FranklinCovey、MBA），按全宽算会凭空多出一行，于是黄金标准
        被自己的判据判成出界，假阳性会让判据失去信誉。
        """
        if ch == " ":
            return 0.30
        if ch == "\t":
            return 0.60
        ea = unicodedata.east_asian_width(ch)
        if ea in ("W", "F"):
            return 1.0
        if ch.isalnum():
            return 0.56
        return 0.52

    for sh in slide.shapes:
        if not (sh.has_text_frame and sh.text.strip()):
            continue
        txt = sh.text.strip()
        w = _px(sh.width)

        # 高度必须**逐段按该段自己的字号**累加，不能拿首段字号算整块。
        # 反例（实测）：封面大数字「+23%\n收入同比增速」，首段 60pt、次段 13.5pt，
        # 按 60pt 算整块得 205px，实际只有 98px——于是这个明明落在页面内的
        # 数字被判「出界」。判据把正常产物判死，就等于没有判据。
        total_h = 0.0
        max_w = 0.0
        max_size = 0.0                 # 块内最大字号，供「咬进多深算压住」换算行高
        for p in sh.text_frame.paragraphs:
            psize = None
            for r in p.runs:
                if r.font.size:
                    psize = r.font.size.pt
                    break
            if psize is None:
                psize = 14.25          # 未显式设字号时用正文默认值
            max_size = max(max_size, psize)
            em = psize * 1.333
            cap = max(w / em, 1.0)     # 该段每行容得下多少 em
            ptext = p.text if p.text.strip() else ""
            lines = 0
            seg_w = 0.0
            for seg in ptext.split("\n"):
                units = sum(_char_unit(c) for c in seg)
                lines += max(1, -(-int(round(units * 100))
                                  // int(round(cap * 100))))
                # 这一段**实际**占了多宽（不超框宽）。碰撞检测必须用实际宽度，
                # 不能用框宽：标题框常比标题字宽出一倍，按框宽判会凭空造出
                # 「标题压住右上角页码」这类假碰撞。
                seg_w = max(seg_w, min(units * em, w))
            # 行距必须读**这份文件自己的** line_spacing，不能用固定系数。
            # 实测（20261113，《人情与面子》p03）：主题 magazine 渲染时写的是
            # 1.32，而这里原写死 1.28。两行 13.5pt 正文估算 46.07px，实际
            # 47.51px —— 差 1.4px，正好让一块压住下一行的批注块以「oy = +0.1」
            # 逃过压字判据，渲染图里那行字被吃掉一半。
            # 判据和渲染器用两套行高口径，就等于判据在自说自话。
            ls = p.line_spacing
            if not isinstance(ls, (int, float)):
                ls = 1.28              # 文件没写行距时的保守默认（偏大不偏小）
            total_h += max(lines, 0) * em * float(ls)
            max_w = max(max_w, seg_w)

        out.append({
            "text": txt,
            "x": _px(sh.left), "y": _px(sh.top),
            "w": max_w or w, "box_w": w,
            "h": total_h or 14.25 * 1.333 * 1.28,
            "size": max_size or 14.25,
        })
    return out


def _text_overflow(slide, pad=8.0):
    """色块内所有文字的实际总占高超出色块可用高度 → 文字溢出容器。

    为什么这条必须单独立判据：PowerPoint 不裁切溢出文字。它会让最后一行
    悄悄落到色块外面，或者盖住下面那块的标题。三种实测缺陷同一个根因：
      * 阶梯第 1 级正文 4 行，色块只放得下 3 行 —— 末尾「演。」掉出色块
      * 批注块文字多出一行 —— 最后一个词落在外框之外
      * 1987 的说明标签压在数字下沿

    ## 为什么不能「逐块文字找它所在的色块」

    第一版那么写，返回空列表。原因是文字框和色块并不嵌套：色块 [64,163,344,340]，
    文字框 [86,207,300,140] —— 文字框只是落在色块**附近**，中心点恰好命中时
    才判。而且一个色块里常有多块文字（编号/标题/正文），逐块判永远判不出
    「加起来放不下」。

    ## 现在的判法

    对每个大色块，把几何上落在它内部的文字**全部聚合**，按各自字号算总占高，
    再和「色块高 - 2×内边距」比。这才是排版的实际约束。
    """
    import unicodedata

    def _unit(ch):
        if ch == " ":
            return 0.30
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            return 1.0
        return 0.56 if ch.isalnum() else 0.52

    def _need_h(sh):
        w = _px(sh.width)
        total = 0.0
        for para in sh.text_frame.paragraphs:
            size = None
            for r in para.runs:
                if r.font.size:
                    size = r.font.size.pt
                    break
            if size is None:
                size = 14.25
            em = size * 1.333
            cap = max(w / em, 1.0)
            lines = 0
            for seg in (para.text if para.text.strip() else "").split("\n"):
                units = sum(_unit(c) for c in seg)
                lines += max(1, -(-int(round(units * 100)) // int(round(cap * 100))))
            # 与 _text_boxes 同口径：读文件真实行距，别用固定系数。
            ls = para.line_spacing
            if not isinstance(ls, (int, float)):
                ls = 1.28
            total += max(lines, 0) * em * float(ls)
        return total

    # 容器：无色可当卡片的实心形状
    containers = []
    for sh in slide.shapes:
        if getattr(sh, "has_text_frame", False) and sh.text.strip():
            continue
        w, h = _px(sh.width), _px(sh.height)
        # 门槛只要「够托住文字」就行，不能高到把真正的容器筛掉。
        # 实测（20261113）：批注块 558×72 被 h>=90 排除，而它恰好是溢出的那一块。
        # 72px 高完全托得住三行 16pt 文字，是标准容器尺寸，不是装饰。
        if w < 120 or h < 48:
            continue
        try:
            if sh.fill.type is None:
                continue
        except (AttributeError, TypeError):
            continue
        containers.append((_px(sh.left), _px(sh.top), w, h))

    problems = []
    for (bx, by, bw, bh) in containers:
        inside = []
        for sh in slide.shapes:
            if not (getattr(sh, "has_text_frame", False) and sh.text.strip()):
                continue
            tx, ty = _px(sh.left), _px(sh.top)
            tw = _px(sh.width)
            # 文字框中心落在色块内即视为该色块的文字
            if not (bx - 8 <= tx + tw / 2 <= bx + bw + 8
                    and by - 8 <= ty <= by + bh - 8):
                continue
            inside.append((sh, tx, ty, tw))
        if not inside:
            continue
        inside.sort(key=lambda t: t[2])          # 按纵向顺序
        top = min(t[2] for t in inside)
        bottom = max(t[2] + _need_h(t[0]) for t in inside)
        used = bottom - top
        avail = bh - 2 * pad
        # 容差 6px：估算折行用的是「按字宽加权」的平均口径，标点、避头尾、
        # 字体实际字宽都会让真实行数差一行。判据的职责是抓「明显放不下」，
        # 不是替代排版引擎做像素级验收——把正常产物判死比漏判更糟。
        if used > avail + 6.0:
            problems.append({
                "text": inside[0][0].text.strip()[:28],
                "used": round(used, 1),
                "avail": round(avail, 1),
                "over_by": round(used - avail, 1),
            })
    return problems


def _overlaps(a, b, pad=2.0):
    """两块文字的实际占位是否相交（各边内缩 pad，避免贴边误报）。"""
    ax1, ay1 = a["x"] + pad, a["y"] + pad
    ax2, ay2 = a["x"] + a["w"] - pad, a["y"] + a["h"] - pad
    bx1, by1 = b["x"] + pad, b["y"] + pad
    bx2, by2 = b["x"] + b["w"] - pad, b["y"] + b["h"] - pad
    return ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2


def _page_stats(slide):
    """量一页的版面构成。"""
    n_shape = 0
    structure = 0
    dividers = 0
    pics = 0
    header = footer = False
    bands = set()

    for sh in slide.shapes:
        n_shape += 1
        kind = _shape_kind(sh)
        top = _px(sh.top)
        left = _px(sh.left)
        w = _px(sh.width)

        if kind == "structure":
            structure += 1
            if "LINE" in str(getattr(sh, "shape_type", "")):
                dividers += 1
        elif kind == "picture":
            pics += 1
        elif kind == "data":
            # 原生图表/表格**占着版面**，是这页的视觉主体。它不提供分隔线，
            # 但必须计入结构件——否则「一页一张大图」的干净业务页会被判成
            # 「只有文字、没做版面」。
            structure += 1

        if top < HEADER_BAND:
            header = True
        if top > FOOTER_BAND:
            footer = True

        # 骨架指纹：按中心横坐标分 10 带，记 (带, 类别)，忽略 y
        try:
            cx = left + w / 2.0
            bands.add((int(cx / 128.0), kind))
        except (TypeError, ValueError):
            pass

    return {
        "shapes": n_shape,
        "structure": structure,
        "dividers": dividers,
        "pictures": pics,
        "header": header,
        "footer": footer,
        "skeleton": tuple(sorted(bands)),
    }


def _fonts_used(pptx_path):
    """成品里声明了哪些字体，以及「东亚字形」由哪个字体承担。

    返回 (ea_fonts, latin_fonts)。只读 XML，不依赖本机装了什么字体。

    为什么必须在交付前查这件事：中文 deck 的 `a:ea` 如果指向一个没有中文字形
    的西文字体，PowerPoint 打开会显示成豆腐块（□□□），而所有现有判据都查不出
    ——形状数、结构件、分隔线、压字全部正常，视觉上就是一堆方框。实测把参照
    deck 的 Georgia/Arial 令牌直接搬到中文内容上就复现了。
    """
    import re
    import zipfile

    ea, latin = set(), set()
    try:
        with zipfile.ZipFile(pptx_path) as z:
            for name in z.namelist():
                if not re.match(r"ppt/slides/slide\d+\.xml$", name):
                    continue
                xml = z.read(name).decode("utf-8", "ignore")
                ea.update(re.findall(r'<a:ea typeface="([^"]*)"', xml))
                latin.update(re.findall(r'<a:latin typeface="([^"]*)"', xml))
    except (zipfile.BadZipFile, OSError):
        return set(), set()
    return {f for f in ea if f}, {f for f in latin if f}


#: 已知没有中文字形的字体族。命中即拦——这些名字出现在 a:ea 上一定是错的。
_NO_CJK_FONTS = (
    "arial", "helvetica", "georgia", "times new roman", "times",
    "courier", "courier new", "verdana", "tahoma", "trebuchet",
    "liberation sans", "liberation serif", "dejavu sans", "dejavu serif",
    "linux libertine", "calibri", "cambria", "segoe ui", "roboto",
    "inter", "helvetica neue", "frank ruhl", "frankruehl",
)


def _cjk_font_problems(pptx_path):
    """a:ea 指向无中文字形的西文字体 → 中文全部变豆腐块。返回问题页描述。

    只拦「确定没有中文字形」的字族。未知字体放行——判据不该因为我不认识
    某个字体名就判死一份正常的 deck。
    """
    ea, _ = _fonts_used(pptx_path)
    bad = []
    for f in sorted(ea):
        low = f.strip().lower()
        if any(low == n or low.startswith(n + " ") for n in _NO_CJK_FONTS):
            bad.append(f)
    if not bad:
        return []
    return [{"fonts": bad,
             "why": "这些字体没有中文字形，中文会全部渲染成方框"}]


def audit_design(pptx_path, min_shapes=MIN_SHAPES_PER_PAGE,
                 min_structure=MIN_STRUCTURE_PER_PAGE,
                 max_same=MAX_SAME_SKELETON):
    """审计一份成品 pptx 的版面设计质量。

    返回 dict：
        ok            四项判据全部通过
        slide_count   总页数
        per_page      每页统计 [{"page","shapes","structure","dividers","pictures"}]
        thin_pages    形状数低于下限的页
        bare_pages    结构件低于下限的页
        no_dividers   全篇没有任何分隔线的页数（0 也正常，但整本为 0 说明没组织）
        chrome        有页眉的页数 / 有页脚的页数
        skeleton_groups  同骨架页组 [{"count","pages"}]
        max_repeat    最大同骨架页数
        verdict       人话结论
    """
    slides = _slides_of(pptx_path)
    total = len(slides)
    if not total:
        return {"ok": False, "slide_count": 0, "verdict": "空文件"}

    per_page = []
    skel = collections.defaultdict(list)
    header_n = footer_n = 0
    total_dividers = 0
    collisions = []
    clipped = []
    overflows = []

    for i, s in enumerate(slides, 1):
        st = _page_stats(s)
        for ov in _text_overflow(s):
            ov["page"] = i
            overflows.append(ov)
        # 仪式页识别：巨型标题 + 极少文字块。只看「字少」不够——裸排布正文页
        # 字也少，那类是必须拦的缺陷，不能被豁免掉。
        blocks = 0
        max_font = 0.0
        for sh in s.shapes:
            if not (sh.has_text_frame and sh.text.strip()):
                continue
            blocks += 1
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    if r.font.size:
                        max_font = max(max_font, r.font.size.pt)
        st["ceremonial"] = (max_font >= CEREMONIAL_MIN_FONT
                            and blocks <= CEREMONIAL_MAX_BLOCKS)
        per_page.append({
            "page": i,
            "shapes": st["shapes"],
            "structure": st["structure"],
            "dividers": st["dividers"],
            "pictures": st["pictures"],
            "ceremonial": st["ceremonial"],
        })
        skel[st["skeleton"]].append(i)
        if st["header"]:
            header_n += 1
        if st["footer"]:
            footer_n += 1
        total_dividers += st["dividers"]

        # 文字重叠：这是几何测量唯一看不见、而人一眼就看见的缺陷。
        boxes = _text_boxes(s)
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                if _overlaps(boxes[a], boxes[b]):
                    collisions.append({
                        "page": i,
                        "a": boxes[a]["text"][:18],
                        "b": boxes[b]["text"][:18],
                    })
        # 色块压字：实心色块盖住别人的文字，比文字压文字更隐蔽——
        # 文字还"在"，只是被盖住看不见了。实测：批注块底边 636 压住 648
        # 处的页码，渲染图里「03 / 09」被浅色块吃掉一半，而纯文字碰撞
        # 判据完全查不出（页码文字自己没和谁重叠）。
        for sh in s.shapes:
            if getattr(sh, "has_text_frame", False) and sh.text.strip():
                continue
            bw, bh = _px(sh.width), _px(sh.height)
            if bw < 120 or bh < 60:      # 细线、小装饰不算
                continue
            try:
                if sh.fill.type is None:
                    continue
            except (AttributeError, TypeError):
                continue
            bx, by = _px(sh.left), _px(sh.top)
            for tbx in boxes:
                # 判「这块文字不属于本块，却被本块压住」——用**重合比例**，
                # 不用「中心在不在块内」，也不用「是否完全包含」：
                #   * 完全包含 → 太严：文字框常刻意比色块多出 2px 贴视觉边距，
                #     实测 78 vs 80 就被判死，正常产物被误伤。
                #   * 只看中心 → 太松：页码文字整体被色块吞掉时，中心正好在
                #     块内，于是「压住页码」被当成正常设计放过。
                # 重合比例两头都对：属于本块的文字通常 ≥85% 在块内；
                # 被压住的页码只有约一半在里面。
                ox = min(bx + bw, tbx["x"] + tbx["w"]) - max(bx, tbx["x"])
                oy = min(by + bh, tbx["y"] + tbx["h"]) - max(by, tbx["y"])
                if ox <= 0 or oy <= 0:
                    continue
                area = max(tbx["w"] * tbx["h"], 1.0)
                covered = (ox * oy) / area
                if covered >= 0.85:
                    continue                 # 这块文字基本都在色块内 = 正常
                # 重叠面积小，不代表没压住。实测（20261113，《人情与面子》
                # p03）：正文最后一行底边 559.5，批注块顶边 558 —— 只咬进
                # 1.5px、占该块文字面积 3.2%，渲染出来正是**最后一行的下沿
                # 被切掉**，那行字看着像被划了一道。
                # 面积判据天生看不见「切一条边」，得补一条**按行高**的口径：
                # 咬进去的深度够到字身的一部分（0.25 行高）就算压住。
                bite = oy / max(1.0, _line_h(tbx["size"]))
                if (ox > 6 and oy > 6) or (ox > 6 and bite >= 0.25):
                    collisions.append({
                        "page": i,
                        "a": f"色块[{round(bx)},{round(by)},{round(bw)},{round(bh)}]",
                        "b": tbx["text"][:18],
                    })

        # 出界：文字框超出画布安全区（右下页码区与左下来源行都在这条线上）
        for bx in boxes:
            if bx["y"] + bx["h"] > 719 or bx["x"] + bx["w"] > 1276:
                clipped.append({
                    "page": i, "text": bx["text"][:18],
                    "bottom": round(bx["y"] + bx["h"], 1),
                    "right": round(bx["x"] + bx["w"], 1),
                })

    # 硬拦：整页只有文字框在堆，连版面框架都没有。这是客观缺陷。
    # 仪式页（封面/封底/扉页）豁免——它们本来就该「空」。
    body_pages = [p for p in per_page if not p.get("ceremonial")]
    bare_floor = [p["page"] for p in body_pages
                  if p["structure"] < FLOOR_STRUCTURE_PER_PAGE]
    thin_floor = [p["page"] for p in body_pages
                  if p["shapes"] < FLOOR_SHAPES_PER_PAGE]

    # 提示：密度低于参照风格的水准。风格选择，不拦，只说。
    thin = [p["page"] for p in body_pages if p["shapes"] < min_shapes]
    bare = [p["page"] for p in body_pages if p["structure"] < min_structure]

    groups = [{"count": len(v), "pages": v}
              for k, v in skel.items() if len(v) > 1]
    groups.sort(key=lambda g: -g["count"])
    max_repeat = max((g["count"] for g in groups), default=1)
    over = [g for g in groups if g["count"] > max_same]

    with_dividers = sum(1 for p in per_page if p["dividers"] > 0)
    divider_ratio = with_dividers / total
    # 硬拦：全篇一条分隔线都没有（说明完全没用几何手段组织信息）。
    # 覆盖率高不高只作提示——不同版式本来就用不同的分隔手段。
    dividers_thin = with_dividers < FLOOR_DIVIDER_PAGES
    dividers_sparse = divider_ratio < MIN_DIVIDER_PAGES_RATIO

    # 字体可读性：a:ea 指向无中文字形的西文字体时，整本中文都是空方框。
    # 这不是「风格」问题，是成品直接不可读，一律硬拦。
    font_problems = _cjk_font_problems(pptx_path)

    ok = (not bare_floor and not thin_floor and not over
          and not dividers_thin and not collisions and not clipped
          and not overflows and not font_problems)

    # 人话结论：说清差在哪，不只给分数
    if ok:
        verdict = "版面成立：结构件密度够、有框架、视觉论证有变化、没有文字压字"
        notes_out = []
        if thin or bare:
            notes_out.append(f"{len(bare)} 页密度低于参照风格")
        if dividers_sparse:
            notes_out.append(f"分隔线只在 {divider_ratio:.0%} 的页面上")
        if notes_out:
            verdict += "（提示：" + "、".join(notes_out) + "，属风格选择可忽略）"
    else:
        bits = []
        if bare_floor:
            bits.append(f"{len(bare_floor)} 页只有文字堆叠、没有任何版面结构"
                        + f"（结构件 <{FLOOR_STRUCTURE_PER_PAGE}）")
        if thin_floor:
            bits.append(f"{len(thin_floor)} 页形状少到连框架都没有"
                        + f"（<{FLOOR_SHAPES_PER_PAGE}）")
        if over:
            worst = over[0]
            bits.append(f"{worst['count']} 页共用同一副骨架（上限 {max_same}）")
        if dividers_thin:
            bits.append("全篇一条分隔线都没有——没用手线/竖线/细条建立层级")
        if collisions:
            pages = sorted({c["page"] for c in collisions})
            bits.append(f"{len(collisions)} 处文字压字，涉及第 "
                        + "、".join(str(p) for p in pages[:8]) + " 页")
        if clipped:
            pages = sorted({c["page"] for c in clipped})
            bits.append(f"{len(clipped)} 处文字出界或被裁，涉及第 "
                        + "、".join(str(p) for p in pages[:8]) + " 页")
        if overflows:
            pages = sorted({o["page"] for o in overflows})
            bits.append(f"{len(overflows)} 处文字溢出所在色块，涉及第 "
                        + "、".join(str(p) for p in pages[:8]) + " 页")
        if font_problems:
            names = "、".join(font_problems[0]["fonts"][:4])
            bits.append(f"中文字体不可用（{names}）——中文会全部显示成方框")
        verdict = "版面不成立：" + "；".join(bits)

    return {
        "ok": ok,
        "slide_count": total,
        "per_page": per_page,
        "thin_pages": thin,
        "bare_pages": bare,
        "bare_floor_pages": bare_floor,
        "thin_floor_pages": thin_floor,
        "advisory": {
            "thin_pages": thin,
            "bare_pages": bare,
            "note": "密度低于参照密集编辑风的水准；属风格选择，不作硬拦。",
        },
        "dividers_total": total_dividers,
        "divider_pages": with_dividers,
        "divider_ratio": round(divider_ratio, 4),
        "chrome": {"header": header_n, "footer": footer_n},
        "skeleton_groups": groups,
        "max_repeat": max_repeat,
        "collisions": collisions,
        "clipped": clipped,
        "font_problems": font_problems,
        "overflows": overflows,
        "limits": {
            "min_shapes": min_shapes,
            "min_structure": min_structure,
            "floor_shapes": FLOOR_SHAPES_PER_PAGE,
            "floor_structure": FLOOR_STRUCTURE_PER_PAGE,
            "max_same_skeleton": max_same,
            "min_divider_ratio": MIN_DIVIDER_PAGES_RATIO,
        },
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# 参照语法的可执行版本
# ---------------------------------------------------------------------------
# 上面是「判」，这里是「做」。两者必须对得上：判据描述的语汇，得有一份真能
# 通过的样本，否则阈值就是拍脑袋。所以把参照 deck 的设计系统写成可调用的
# 构件，`selfcheck` 用它现造一份 5 页，要求 audit_design 判 ok=True。
#
# 注意边界：这里给的是**语汇**（页眉框架、徽章、标签条、细条、分隔线的尺寸与
# 颜色），不是**模板**。每页的论证结构仍然各自不同——5 页 5 种，没有一页是
# 另一页换个字。

_TERRACOTTA = "9A3412"
_NAVY = "1E3A5F"
_INK = "1C1917"
_PAPER = "FAF7F2"
_SAND = "E7D8C9"
_BRONZE = "C8A27C"

# 尺寸来源：参照 deck 实测
_EMU = 9525                      # 1px
W, H = 1280, 720
_MARGIN_L = 60
_CONTENT_W = 1160

_FONT_CN = "Arial"
_FONT_SERIF = "Georgia"


def _emu(v):
    from pptx.util import Emu
    return Emu(int(round(v * _EMU)))


def _rect(slide, x, y, w, h, fill=None, line=None, line_w=1.0):
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Pt
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, _emu(x), _emu(y),
                                _emu(max(w, 1)), _emu(max(h, 1)))
    if fill:
        sh.fill.solid()
        from pptx.dml.color import RGBColor
        sh.fill.fore_color.rgb = RGBColor.from_string(fill)
    else:
        sh.fill.background()
    if line:
        from pptx.dml.color import RGBColor
        sh.line.color.rgb = RGBColor.from_string(line)
        sh.line.width = Pt(line_w)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def _hline(slide, x, y, w, color=_SAND, weight=1.0):
    from pptx.enum.shapes import MSO_CONNECTOR
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                    _emu(x), _emu(y), _emu(x + w), _emu(y))
    ln.line.color.rgb = RGBColor.from_string(color)
    ln.line.width = Pt(weight)
    return ln


def _vline(slide, x, y, h, color=_SAND, weight=1.0):
    from pptx.enum.shapes import MSO_CONNECTOR
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                    _emu(x), _emu(y), _emu(x), _emu(y + h))
    ln.line.color.rgb = RGBColor.from_string(color)
    ln.line.width = Pt(weight)
    return ln


def _text(slide, x, y, w, h, s, size=14.25, color=_INK, bold=False,
          font=_FONT_CN, align="l", spacing=1.25):
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    tb = slide.shapes.add_textbox(_emu(x), _emu(y), _emu(w), _emu(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER,
                   "r": PP_ALIGN.RIGHT}[align]
    p.line_spacing = spacing
    r = p.add_run()
    r.text = s
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = font
    r.font.color.rgb = RGBColor.from_string(color)
    return tb


def _line_h(size, spacing=1.25):
    """一个 pt 号的中文字，占多高（px）。

    为什么需要这个函数：中文字身约等于字号（1pt ≈ 1.333px），再乘行距。
    之前凭感觉给「24pt 字配 32px 高」，实际需要 24×1.333×1.25 ≈ 40px，
    结果每一处上下叠放的两行文字都压在一起。凡是「两块文字上下排」的地方，
    都得用这个函数算位置，不能写死偏移。
    """
    return size * 1.333 * spacing


def _chrome(slide, page_no, total, source, chapter_no, chapter_name):
    """页面框架：参照每一页都有的那一套。

    实测参照：页眉短竖线 60,52 0×38；页眉下全长线 60,150 1160×0；
    左上角小徽章 34×34 放章节号；左下角来源行；右下角页码。
    这四件让人认出「这是同一本书的连续页」，而不是散装幻灯片。
    """
    _vline(slide, _MARGIN_L, 52, 38, _TERRACOTTA, 2.25)
    _text(slide, _MARGIN_L + 14, 50, 460, 22, chapter_name,
          size=13.5, color=_NAVY, bold=True)
    _text(slide, _MARGIN_L + 500, 50, 560, 22, source,
          size=13.5, color=_BRONZE, align="r")
    _hline(slide, _MARGIN_L, 150, _CONTENT_W, _SAND, 1.0)

    # 底部框架：左下来源行 + 右下页码块。
    # 注意画布高只有 720，页码块必须整体落在 720 以内——第一版写在
    # 690 + 18 高，实际字底到了 736，"/ 05" 被裁掉一半，靠渲染才发现。
    _hline(slide, _MARGIN_L, 640, 120, _BRONZE, 1.5)
    _text(slide, _MARGIN_L, 652, 700, 22, "《高效能人士的七个习惯》· 精读笔记",
          size=13.5, color=_BRONZE)
    badge = _rect(slide, 1172, 644, 38, 30, _TERRACOTTA)
    _fill_text(badge, f"{page_no:02d}", size=14.25, color="FFFFFF", bold=True,
               align="c")
    _text(slide, 1172, 670, 38, 22, f"/ {total:02d}", size=13.5,
          color=_BRONZE, align="c")
    _text(slide, 60, 108, 60, 24, f"{chapter_no:02d}", size=14.25,
          color=_TERRACOTTA, bold=True)


def _fill_text(sh, s, size=13.5, color="FFFFFF", bold=False, align="c",
               font=_FONT_CN):
    """往已有形状里写一段文字，四边留白清零、垂直居中。"""
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.dml.color import RGBColor
    from pptx.util import Pt
    tf = sh.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER,
                   "r": PP_ALIGN.RIGHT}[align]
    r = p.add_run()
    r.text = s
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = font
    r.font.color.rgb = RGBColor.from_string(color)
    return sh



def _label(slide, x, y, s, w=118, h=30, fill=_SAND, color=_TERRACOTTA):
    """标签条 118×30，参照里出现 5 次——同尺寸复用，位置各不相同。"""
    sh = _rect(slide, x, y, w, h, fill)
    _fill_text(sh, s, size=13.5, color=color, bold=True, align="c")
    return sh


def _tick(slide, x, y, w=8, h=18, color=_TERRACOTTA):
    """8px 细条，当项目符号用。参照里到处是它。"""
    return _rect(slide, x, y, w, h, color)


def _bullets(slide, x, y, w, items, gap=44):
    """竖排条目：细条 + 文字 + 条目间分隔线。这是参照最常用的组织手法。"""
    for i, s in enumerate(items):
        yy = y + i * gap
        _tick(slide, x, yy + 4)
        _text(slide, x + 20, yy, w - 20, 26, s, size=15)
        if i < len(items) - 1:
            _hline(slide, x, yy + gap - 12, w, _SAND, 0.75)


# 统一的内容区起点：页眉线在 150，标题块占 172–300，正文从 306 起。
# 之前没设这条基线，标题和正文都贴着 216 起，直接用字符压在一起。

# 版心网格。5 页共用，避免每页各拍一次坐标——上一版就是这么压字的。
GRID_L = 60                 # 左边界
GRID_R = 1220               # 右边界
COL_L_W = 660               # 主栏宽（左）
GUTTER = 76                 # 栏间距
COL_R_X = GRID_L + COL_L_W + GUTTER      # 736，右栏起点
COL_R_W = GRID_R - COL_R_X               # 484，右栏宽
HEAD_Y = 214                # 标题起点
BODY_Y = 356                # 内容区起点（标题 + 最多两行引言之后）
BODY_BOTTOM = 628           # 内容区下界（再往下是来源行与页码）


def _head(slide, label, title, lede=None, title_size=33):
    """页头三件套：标签条 → 主标题 → 引言。三者纵向严格不交叠。

    上一版的毛病：标题文本框 216 起、高 40，引言也写 268 起，可 33pt 中文字
    实际行高约 55px，标题直接压到引言上。现在按真实行高留位，并让引言
    只用主栏宽度——它一旦写满 760px 就会伸进右栏。
    """
    _label(slide, GRID_L, 172, label)
    _text(slide, GRID_L, HEAD_Y, COL_L_W, _line_h(title_size, 1.15) * 1.2,
          title, size=title_size, color=_NAVY, bold=True, font=_FONT_SERIF,
          spacing=1.15)
    if lede:
        ly = HEAD_Y + _line_h(title_size, 1.15) * 1.15
        _text(slide, GRID_L, ly, COL_L_W, BODY_Y - ly - 12, lede, size=15,
              color=_INK, spacing=1.5)


def _page_staircase(s):
    """论证一：阶梯。依赖期→独立期→互赖期，三级台阶向右上抬升。"""
    _head(s, "成长三阶", "从依赖到互赖",
          "成熟不是性格变好，是可选范围变大。三级台阶各解决一个问题。")

    axis_x, base = 148, 596
    steps = [("依赖", "你", axis_x + 30, 126, _SAND, _NAVY),
             ("独立", "我", axis_x + 206, 186, _BRONZE, "FFFFFF"),
             ("互赖", "我们", axis_x + 382, 246, _TERRACOTTA, "FFFFFF")]

    # 轴先画、标签先写，色块后画——顺序决定谁盖住谁。
    # "成熟度" 写在轴左侧 20px 处，竖直方向贴着轴顶端，不再落到标题带上。
    _vline(s, axis_x, base - 258, 258, _INK, 1.5)
    _hline(s, axis_x, base, 560, _INK, 1.5)
    _text(s, axis_x - 92, BODY_Y - 26, 84, 22, "成熟度", size=13.5,
          color=_BRONZE, align="r")
    _text(s, axis_x, base + 12, 200, 22, "时间", size=13.5, color=_BRONZE)

    for i, (name, tag, x, h, col, fg) in enumerate(steps):
        top = base - h
        _rect(s, x, top, 166, h, col)
        _text(s, x + 18, top + 20, 132, _line_h(24), name, size=24, color=fg,
              bold=True)
        _text(s, x + 18, top + 20 + _line_h(24) + 4, 132, _line_h(13.5), tag,
              size=13.5, color=fg)
        if i:
            prev_top = base - steps[i - 1][3]
            _hline(s, x - 34, min(top, prev_top), 34, _BRONZE, 1.5)

    _vline(s, COL_R_X - 36, BODY_Y, 372, _SAND, 1.0)
    _bullets(s, COL_R_X, BODY_Y + 4, COL_R_W, [
        "依赖期：事情成不成看别人",
        "独立期：能自己扛住一件事",
        "互赖期：能和人一起扛更大的事",
    ], gap=64)


def _page_bands(s):
    """论证二：三段递进带。三条横向色带，长度递增 = 影响范围扩大。"""
    _head(s, "影响圈", "关注什么，不如影响什么",
          "把注意力从「发生了什么」挪到「我能改什么」，是这套体系里最省力的一步。")

    # 色带内的行距按真实行高算：名称 20pt、说明 13.5pt，两块上下排。
    rows = [("关注圈", "天气、行业、别人的评价", 460, _SAND, _NAVY),
            ("影响圈", "今天的安排、手上的活", 760, _BRONZE, "FFFFFF"),
            ("可控圈", "自己的判断与反应", 1060, _TERRACOTTA, "FFFFFF")]
    name_h = _line_h(20)
    desc_h = _line_h(13.5)
    band_h = name_h + desc_h + 18
    for i, (name, desc, w, col, fg) in enumerate(rows):
        y = BODY_Y + 4 + i * (band_h + 10)
        _rect(s, GRID_L, y, w, band_h, col)
        _text(s, GRID_L + 18, y + 8, 170, name_h, name, size=20, color=fg,
              bold=True)
        _text(s, GRID_L + 18, y + 8 + name_h + 2, w - 40, desc_h, desc,
              size=13.5, color=fg)
        _text(s, GRID_L + w + 16, y + band_h / 2 - 12, 90, 24,
              f"{int(w / 1160 * 100)}%", size=14.25, color=_BRONZE, bold=True)
    foot_y = BODY_Y + 4 + 3 * (band_h + 10) + 4
    _hline(s, GRID_L, foot_y, 1060, _INK, 1.5)
    _text(s, GRID_L, foot_y + 8, 1060, 20, "越往里越能改，越往外越只能接受",
          size=13.5, color=_BRONZE)


def _page_rings(s):
    """论证三：同心圆（关注圈→影响圈）+ 右栏四象限条目。

    圆环标注的坑：三圈写三个名字必然挤，用引线又容易指向不明。最终办法是
    把名字直接写在对应环带上——环带够宽（外环 50px 带宽）就能放下，
    不需要引线，也就没有指向问题。
    """
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.dml.color import RGBColor
    _head(s, "精力投放", "先做重要的，不是先做急的")

    cx, cy = 340, 464
    for r, col in [(150, _SAND), (100, _BRONZE), (52, _TERRACOTTA)]:
        el = s.shapes.add_shape(MSO_SHAPE.OVAL, _emu(cx - r), _emu(cy - r),
                                _emu(r * 2), _emu(r * 2))
        el.fill.solid()
        el.fill.fore_color.rgb = RGBColor.from_string(col)
        el.line.fill.background()
        el.shadow.inherit = False

    # 名字写在环带上：外环带中径 125、内环带中径 76，字放在圆环顶部
    _text(s, cx - 60, cy - 150 + 30, 120, 22, "关注圈", size=13.5,
          color=_NAVY, bold=True, align="c")
    _text(s, cx - 60, cy - 100 + 30, 120, 22, "影响圈", size=13.5,
          color=_INK, bold=True, align="c")
    _text(s, cx - 44, cy - 12, 88, 24, "最该做", size=14.25, color="FFFFFF",
          bold=True, align="c")

    _vline(s, COL_R_X - 36, BODY_Y, 340, _SAND, 1.0)
    _bullets(s, COL_R_X, BODY_Y + 2, COL_R_W, [
        "重要且急：立刻做，别拖",
        "重要不急：排进日程，这是复利区",
        "急不重要：能委托就委托",
        "不重要不急：直接删掉",
    ], gap=84)


def _page_matrix(s):
    """论证四：2×2 矩阵 + 中央十字线。

    轴标的教训：用箭头符号（↑ →）在 Arial 里常缺字形，用旋转文本框会以中心
    为锚点溢出到隔壁栏，用独立轴线又容易贴到页脚。最后改成最稳的做法——
    轴的含义写进格内文字（"重要·紧急"），轴名用一句引导语放在矩阵上方，
    矩阵下方只留一行来源说明。零符号、零旋转、零溢出。
    """
    _head(s, "四象限", "把事按两个维度切开",
          "两个维度一交叉，同一件事的性质就变了。")

    x0, y0 = GRID_L, BODY_Y + 6
    cw, ch = 330, 104
    t_h = _line_h(15)
    h_h = _line_h(13.5)
    cells = [("重要 · 紧急", _TERRACOTTA, "FFFFFF", "立刻做"),
             ("重要 · 不急", _BRONZE, "FFFFFF", "排进日程"),
             ("不重要 · 紧急", _SAND, _NAVY, "能委托就委托"),
             ("不重要 · 不急", _PAPER, _INK, "直接删掉")]
    for i, (t, bg, fg, hint) in enumerate(cells):
        x = x0 + (i % 2) * cw
        y = y0 + (i // 2) * ch
        _rect(s, x, y, cw, ch, bg, _SAND, 1.0)
        _text(s, x + 20, y + 14, cw - 40, t_h, t, size=15, color=fg, bold=True)
        _text(s, x + 20, y + 14 + t_h + 2, cw - 40, h_h, hint, size=13.5,
              color=fg)
    _vline(s, x0 + cw, y0, ch * 2, _INK, 1.5)
    _hline(s, x0, y0 + ch, cw * 2, _INK, 1.5)

    # 轴的交点标一个小十字，替代轴名——省掉所有方向符号
    _text(s, x0 + cw * 2 + 12, y0 + ch - 10, 24, 20, "+", size=13.5,
          color=_BRONZE, align="c")
    note_y = y0 + ch * 2 + 14
    _text(s, x0, note_y, cw * 2, h_h,
          "横轴：紧急度　　纵轴：重要度", size=13.5, color=_BRONZE)

    _vline(s, COL_R_X - 36, y0, ch * 2, _SAND, 1.0)
    _bullets(s, COL_R_X, y0 + 10, COL_R_W, [
        "九成时间花在左上格，因为它在喊",
        "右上格才决定三年后的位置",
        "右下的诱惑最难拒绝",
    ], gap=88)


def _page_bars(s):
    """论证五：水平柱 + 右侧数值。极简，但仍是完整论证。"""
    _head(s, "复利", "1+1 什么时候大于 2",
          "协作不是把两个人的产出相加，而是让判断互相校准。校准对了是乘法，错了是内耗。")

    rows = [("各干各的", 0.42, _SAND, "42"),
            ("各让一步", 0.58, _BRONZE, "58"),
            ("统合综效", 0.92, _TERRACOTTA, "92")]
    for i, (name, ratio, col, val) in enumerate(rows):
        y = BODY_Y + 12 + i * 82
        _text(s, GRID_L, y + 2, 140, 26, name, size=15, color=_NAVY, bold=True)
        # 轨道 + 实际长度的条；条右端留出数值位，不与数字重叠
        _rect(s, GRID_L + 154, y + 2, 660, 22, _PAPER, _SAND, 0.75)
        _rect(s, GRID_L + 154, y + 2, 660 * ratio, 22, col)
        _text(s, GRID_L + 836, y - 2, 80, 26, val, size=20, color=col,
              bold=True, align="r")
        if i < len(rows) - 1:
            _hline(s, GRID_L, y + 54, 916, _SAND, 0.75)
    _text(s, GRID_L, 596, 700, 20, "数值为示意，用于比较相对关系", size=13.5,
          color=_BRONZE)


_REFERENCE_PAGES = [
    ("依赖 / 独立 / 互赖", "习惯总览", _page_staircase),
    ("关注圈 / 影响圈", "习惯一 · 积极主动", _page_bands),
    ("时间管理四象限", "习惯三 · 要事第一", _page_rings),
    ("要事第一", "习惯三 · 要事第一", _page_matrix),
    ("统合综效", "习惯六 · 统合综效", _page_bars),
]


def build_reference_sample():
    """按参照语法造一份 5 页 pptx（未保存），给 selfcheck 当「应当通过」的样本。

    返回 python-pptx 的 Presentation，调用方自己 save。之所以返回对象而不直接
    落盘，是为了让测试能拿去改坏（删掉所有分隔线）再验判据有约束力。
    """
    from pptx import Presentation
    from pptx.util import Emu

    prs = Presentation()
    prs.slide_width = Emu(int(W * _EMU))
    prs.slide_height = Emu(int(H * _EMU))
    blank = prs.slide_layouts[6]
    total = len(_REFERENCE_PAGES)
    for i, (source, chapter, body) in enumerate(_REFERENCE_PAGES, 1):
        s = prs.slides.add_slide(blank)
        bg = s.background.fill
        bg.solid()
        from pptx.dml.color import RGBColor
        bg.fore_color.rgb = RGBColor.from_string(_PAPER)
        _chrome(s, i, total, source, i, chapter)
        body(s)
    return prs

