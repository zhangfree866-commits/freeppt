# -*- coding: utf-8 -*-
"""完整 10 页《高效能人士的七个习惯》精读 deck 构建器。

为什么单独有这个文件：`design_audit.build_reference_sample()` 只造 5 页，用来验证
判据；它证明的是「判与做对得上」。真正要追赶豆包，得拿参照语法做一本完整的书。
这里把参照 deck 逐页实测的几何坐标还原成 10 页，四种布局、十种左侧视觉论证，
没有两页内容页共用同一骨架。

坐标全部来自对参照 pptx 的形状级测量（单位 px，画布 1280x720），不是重新拍的。
图元（_rect/_hline/_vline/_text/_line_h）直接复用 design_audit，保证和判据同源。
"""

from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from engine.design_audit import (
    W, H,
    _TERRACOTTA, _NAVY, _INK, _PAPER, _SAND, _BRONZE,
    _rect, _hline, _vline, _text, _fill_text, _line_h,
)

L = 60          # 内容页左界
FULL = 1160     # 内容区全宽
RX = 1220       # 右界


# --------------------------------------------------------------------------- #
# 页面框架
# --------------------------------------------------------------------------- #

def _paper_bg(slide):
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = RGBColor.from_string(_PAPER)


def _content_header(s, kicker, title):
    """内容页页头：短竖线 + kicker(50) + 主标题句(88) + 全长分隔线(150)。"""
    _vline(s, L, 52, 26, _TERRACOTTA, 2.0)
    _text(s, 78, 50, 1000, 26, kicker, size=13.5, color=_NAVY, bold=True)
    _text(s, L, 86, FULL, 52, title, size=24, color=_NAVY, bold=True,
          font="Georgia", spacing=1.15)
    _hline(s, L, 150, FULL, _SAND, 1.0)


def _content_footer(s, page, source):
    _text(s, L, 672, 940, 26, source, size=13.5, color=_BRONZE)
    _text(s, 1080, 672, 140, 26, f"{page:02d} / 10", size=13.5,
          color=_BRONZE, align="r")


def _card(s, x, y, w, h, accent=True, fill="FFFFFF"):
    """白卡 + 细沙边，左侧 5px 强调条（参照底部信息卡的做法）。"""
    _rect(s, x, y, w, h, fill, _SAND, 0.75)
    if accent:
        _rect(s, x, y, 5, h, _TERRACOTTA)


def _numbered_rows(s, items, x0=540, y0=176, pitch=92,
                   label_x=594, body_x=722, body_w=498, line_x=594,
                   line_w=626, vline_x=514, vline=True):
    """右侧带编号的条目列：徽章 + 小标题 + 正文 + 行间分隔线。P3/P5/P9 用。"""
    if vline:
        _vline(s, vline_x, y0, pitch * len(items) - 10, _SAND, 1.0)
    for i, (label, body) in enumerate(items):
        y = y0 + i * pitch
        badge = _rect(s, x0, y, 34, 34, _TERRACOTTA)
        _fill_text(badge, f"{i + 1:02d}", size=13.5, color="FFFFFF", bold=True)
        _text(s, label_x, y - 2, 118, 28, label, size=15, color=_NAVY,
              bold=True)
        _text(s, body_x, y - 4, body_w, pitch - 12, body, size=13.5,
              color=_INK, spacing=1.28)
        if i < len(items) - 1:
            _hline(s, line_x, y + pitch - 10, line_w, _SAND, 1.0)


def _full_rows(s, items, y0=342, pitch=62, num_x=60, label_x=84,
                body_x=200, body_w=1020, tick_w=8):
    """全宽横排条目：细条/序号 + 小标题 + 正文。P6/P7 用。"""
    for i, (label, body) in enumerate(items):
        y = y0 + i * pitch
        if tick_w:
            _rect(s, num_x, y, tick_w, 48, _TERRACOTTA)
        _text(s, label_x, y - 2, 110, 28, label, size=15, color=_NAVY,
              bold=True)
        _text(s, body_x, y - 4, body_w, pitch - 8, body, size=13.5,
              color=_INK, spacing=1.25)


# --------------------------------------------------------------------------- #
# P1 封面
# --------------------------------------------------------------------------- #

def _p1_cover(s):
    # 装饰圆（参照右上角两个）
    _oval(s, 880, -160, 420, 420, _SAND)
    _oval(s, 1060, 110, 120, 120, _BRONZE)

    _vline(s, 80, 96, 34, _TERRACOTTA, 2.0)
    _text(s, 100, 94, 800, 30, "精读笔记  ·  THE 7 HABITS",
          size=14.2, color=_NAVY, bold=True)

    _text(s, 80, 168, 1000, 92, "高效能人士的七个习惯",
          size=43.5, color=_NAVY, bold=True, font="Georgia", spacing=1.1)
    _text(s, 80, 276, 980, 76,
          "从依赖到独立，再到互赖：一套以原则为中心、由内而外的成长体系",
          size=15.8, color=_INK, spacing=1.5)
    _hline(s, 80, 372, 520, _BRONZE, 1.5)

    # 三级台阶卡
    stairs = [(80, 466, 114, _SAND, _NAVY),
              (300, 426, 154, _BRONZE, "FFFFFF"),
              (530, 386, 194, _TERRACOTTA, "FFFFFF")]
    names = [("依赖", "以「你」为核心"),
             ("独立", "以「我」为核心"),
             ("互赖", "以「我们」为核心")]
    for (x, y, h, col, fg), (name, tag) in zip(stairs, names):
        _rect(s, x, y, 200, h, col)
        _text(s, x + 18, y + 18, 170, 34, name, size=20, color=fg, bold=True)
        _text(s, x + 18, y + 58, 170, 28, tag, size=13.5, color=fg)

    # 右侧三条信息
    infos = [("作者与首版",
              "史蒂芬·R·柯维（Stephen R. Covey），1989 年首版；中文通行译本由中国青年出版社出版。"),
             ("一条主线",
              "习惯 1–3 完成个人成功，习惯 4–6 完成公众成功，习惯 7 持续为前六个供能。"),
             ("阅读方式",
              "10 页按定义、原则、误区、示例、行动逐层展开，适合独立阅读与自查。")]
    for i, (k, v) in enumerate(infos):
        y = 400 + i * 82
        _text(s, 760, y, 460, 26, k, size=15, color=_NAVY, bold=True)
        _text(s, 760, y + 28, 460, 50, v, size=13.5, color=_INK, spacing=1.25)

    _text(s, 80, 660, 940, 26,
          "依据：Covey (1989)；FranklinCovey 官方习惯释义；中文译本书目信息",
          size=13.5, color=_BRONZE)
    _text(s, 1080, 660, 140, 26, "01 / 10", size=13.5, color=_BRONZE,
          align="r")


def _oval(slide, x, y, w, h, fill, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Emu as _E
    el = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(int(x * 9525)),
                               Emu(int(y * 9525)), Emu(int(w * 9525)),
                               Emu(int(h * 9525)))
    el.fill.solid()
    el.fill.fore_color.rgb = RGBColor.from_string(fill)
    if line:
        el.line.color.rgb = RGBColor.from_string(line)
        el.line.width = Pt(1.0)
    else:
        el.line.fill.background()
    el.shadow.inherit = False
    return el


# --------------------------------------------------------------------------- #
# P2 全书框架
# --------------------------------------------------------------------------- #

def _p2(s):
    _content_header(s, "全书框架  ·  MATURITY CONTINUUM",
                    "七个习惯不是七个技巧，而是一条从依赖走向互赖的成熟路径")

    top = [("依赖期  ·  以「你」为核心", "习惯 1–3 个人成功", 60, 330, _SAND, _NAVY),
           ("独立期  ·  以「我」为核心", "习惯 1–3 完成独立", 420, 340, _BRONZE, "FFFFFF"),
           ("互赖期  ·  以「我们」为核心", "习惯 4–6 公众成功 · 7 更新", 780, 420,
            _TERRACOTTA, "FFFFFF")]
    for t, sub, x, w, col, fg in top:
        _rect(s, x, 176, w, 92, col)
        _text(s, x + 18, 190, w - 36, 34, t, size=15, color=fg, bold=True)
        _text(s, x + 18, 228, w - 36, 28, sub, size=13.5, color=fg)

    _text(s, L, 286, FULL, 26,
          "由内而外  →  先修品德与思维定式，再谈技巧与结果",
          size=13.5, color=_TERRACOTTA, bold=True)
    _hline(s, L, 320, FULL, _SAND, 1.0)

    row1 = [("成熟模式图",
             "依赖期以「你」为核心，独立期以「我」为核心，互赖期以「我们」为核心；互赖是更高阶段，不是退回依赖。", 60, 360),
            ("前三个习惯",
             "习惯 1–3 是个人成功（Private Victory）：从被动接受转向自我负责，先赢下自己。", 450, 360),
            ("后三个习惯",
             "习惯 4–6 是公众成功（Public Victory）：在独立与信任的基础上，与人协作取得更大成果。", 840, 360)]
    row2 = [("习惯 7",
             "不断更新保护并提升「自己」这项资产，为前六个习惯提供持续产能，形成螺旋上升。", 60, 560),
            ("底层逻辑",
             "由内而外：柯维反对只改行为的个人魅力论，主张先修品德与思维定式；习惯是知识、技巧、意愿三者的交集。",
             660, 560)]
    for t, b, x, w in row1:
        _card(s, x, 342, w, 122)
        _text(s, x + 18, 354, w - 36, 28, t, size=15, color=_NAVY, bold=True)
        _text(s, x + 18, 386, w - 36, 74, b, size=13.5, color=_INK, spacing=1.25)
    for t, b, x, w in row2:
        _card(s, x, 476, w, 122)
        _text(s, x + 18, 488, w - 36, 28, t, size=15, color=_NAVY, bold=True)
        _text(s, x + 18, 520, w - 36, 74, b, size=13.5, color=_INK, spacing=1.25)

    _content_footer(s, 2,
                    "依据：Covey (1989) 成熟模式图；MBA 智库「成熟模式图」条目；FranklinCovey 官方释义")


# --------------------------------------------------------------------------- #
# P3 习惯一
# --------------------------------------------------------------------------- #

def _p3(s):
    _content_header(s, "习惯 01  ·  BE PROACTIVE",
                    "积极主动：在刺激与回应之间，你仍有选择的自由")

    # 同心圆
    _oval(s, 80, 196, 380, 380, _SAND)
    _oval(s, 150, 266, 240, 240, "FFFFFF", _BRONZE)
    _text(s, 78, 210, 240, 30, "关注圈  Concern", size=14.2,
          color=_NAVY, bold=True)
    _text(s, 170, 364, 200, 30, "影响圈", size=16.5, color=_TERRACOTTA,
          bold=True, align="c")
    _text(s, 170, 404, 200, 30, "Circle of Influence", size=13.5,
          color=_BRONZE, align="c")
    _text(s, 80, 590, 400, 30, "把精力放在内圈，内圈会逐步扩大",
          size=13.5, color=_BRONZE)

    rows = [
        ("准确定义",
         "对自己的选择负责，把精力放在可以影响的事情上；官方称其为「个人责任」的习惯。"),
        ("关键原则",
         "关注圈是你在意却管不了的事，影响圈是你能改变的事；专注影响圈会让它扩大。把「我不得不」换成「我选择」。"),
        ("常见误区",
         "不等于态度积极、抢着加班或强行控制别人；原著讲的是在客观限制面前，仍为自己的回应负责。"),
        ("应用示例",
         "上游延期导致项目受阻：不反复抱怨协作方，而是列出自己能改的三件事——调整排期、备好中间版本、提前同步风险，并约一次对齐会。"),
        ("行动建议",
         "连续 7 天记录一次「被触发—我的回应」，把「没办法」改写成「我可以先」，并当天兑现一个小承诺。"),
    ]
    _numbered_rows(s, rows)
    _content_footer(s, 3,
                    "依据：FranklinCovey, Habit 1: Be Proactive；Covey (1989), 习惯一")


# --------------------------------------------------------------------------- #
# P4 习惯二
# --------------------------------------------------------------------------- #

def _p4(s):
    _content_header(s, "习惯 02  ·  BEGIN WITH THE END IN MIND",
                    "以终为始：先在心里创造一次，再在现实里创造一次")

    # 两次创造两条全宽带
    _rect(s, 60, 176, FULL, 42, _SAND)
    _text(s, 80, 182, 1120, 30,
          "第一次创造 · 心智创造：先定义方向、角色与成功标准",
          size=14.2, color=_NAVY, bold=True)
    _text(s, 600, 218, 80, 30, "↓", size=18, color=_TERRACOTTA,
          bold=True, align="c")
    _rect(s, 60, 252, FULL, 42, _TERRACOTTA)
    _text(s, 80, 258, 1120, 30,
          "第二次创造 · 实际创造：再排目标、资源与行动，把方向落到日程",
          size=14.2, color="FFFFFF", bold=True)
    _hline(s, 60, 302, FULL, _SAND, 1.0)

    left = [
        ("1  准确定义",
         "所有事物都有两次创造：第一次是心智创造，第二次是实际创造。先定义清晰的成功标准与人生方向，再开始行动。"),
        ("2  关键原则",
         "以原则为中心，写个人使命宣言；先想清楚要成为什么样的人、承担哪些角色，再设目标。领导负责第一次创造，管理负责第二次。"),
        ("3  常见误区",
         "被简化成设 KPI 或写一句口号；原著强调把生活重心放在不变的原则上，而非工作、金钱或他人评价。"),
    ]
    right = [
        ("4  应用示例",
         "接手新项目时，先写「结项时希望客户如何评价这次合作」，再倒推验收标准、角色分工与明确不做的事，比直接排任务更少返工。"),
        ("5  行动建议",
         "用 30 分钟列 3–5 个长期角色，各写一句「我希望被记住的做法」，合成一版使命宣言，每季度复核一次。"),
    ]
    for i, (t, b) in enumerate(left):
        y = 312 + i * 116
        _card(s, 60, y, 560, 112)
        _text(s, 78, y + 8, 524, 26, t, size=15, color=_NAVY, bold=True)
        _text(s, 78, y + 38, 524, 70, b, size=13.5, color=_INK, spacing=1.25)
    for i, (t, b) in enumerate(right):
        y = 312 + i * 116
        _card(s, 640, y, 580, 112)
        _text(s, 658, y + 8, 544, 26, t, size=15, color=_NAVY, bold=True)
        _text(s, 658, y + 38, 544, 70, b, size=13.5, color=_INK, spacing=1.25)
    _card(s, 640, 544, 580, 112)
    _text(s, 660, 556, 540, 28, "贯穿两次创造的一条线", size=15,
          color=_NAVY, bold=True)
    _text(s, 660, 588, 540, 60,
          "以不变的原则为生活重心；领导负责第一次创造，管理负责第二次创造。",
          size=13.5, color=_INK, spacing=1.25)

    _content_footer(s, 4,
                    "依据：FranklinCovey, Habit 2；Covey (1989), 习惯二")


# --------------------------------------------------------------------------- #
# P5 习惯三
# --------------------------------------------------------------------------- #

def _p5(s):
    _content_header(s, "习惯 03  ·  PUT FIRST THINGS FIRST",
                    "要事第一：把愿景变成日程，守住重要但不紧急的第二象限")

    cells = [("I  重要 · 紧急", "立即处理：危机、临近的截止", 60, 176, _TERRACOTTA, "FFFFFF"),
             ("II  重要 · 不紧急", "高效能核心：规划、预防、关系、能力", 260, 176, _BRONZE, "FFFFFF"),
             ("III  不重要 · 紧急", "多为别人的优先事项，尽量压缩", 60, 356, _SAND, _NAVY),
             ("IV  不重要 · 不紧急", "多为消遣与琐事，应当删减", 260, 356, _PAPER, _INK)]
    for t, b, x, y, col, fg in cells:
        _rect(s, x, y, 190, 170, col, _SAND, 0.75)
        _text(s, x + 12, y + 14, 168, 46, t, size=14.2, color=fg, bold=True,
              spacing=1.15)
        _text(s, x + 12, y + 68, 168, 92, b, size=13.5, color=fg, spacing=1.28)
    _text(s, 60, 548, 400, 30, "第二象限决定长期产出与产能",
          size=14.2, color=_NAVY, bold=True)
    _text(s, 60, 580, 400, 26, "按「重要 / 紧急」两轴切分日程",
          size=13.5, color=_BRONZE)

    rows = [
        ("准确定义",
         "这是「个人管理」的习惯，也是习惯 2 的执行环节：把最重要的事排进时间，而不是不断对紧急事件做出反应。"),
        ("关键原则",
         "时间管理矩阵按重要 / 紧急分四象限；第二象限（重要不紧急）包含规划、预防、关系与能力建设。每周按角色排「大石头」。"),
        ("常见误区",
         "被理解成把待办清单重新排序；原著重点是删掉不重要的事、用责任型授权（讲清结果、资源与责任，把方法交给对方）释放时间。"),
        ("应用示例",
         "周一先为每个角色排 1–2 件第二象限大石头并锁进日历；把随时响应消息改成两个固定时段，其余留给深度工作。"),
        ("行动建议",
         "本周列一张四象限表，圈出被挤掉的第二象限事项；至少删掉一项低价值任务，并把一项完整授权出去。"),
    ]
    _numbered_rows(s, rows)
    _content_footer(s, 5,
                    "依据：FranklinCovey, Habit 3 / One-Day Outline；Covey (1989), 习惯三")


# --------------------------------------------------------------------------- #
# P6 习惯四
# --------------------------------------------------------------------------- #

def _p6(s):
    _content_header(s, "习惯 04  ·  THINK WIN-WIN",
                    "双赢思维：在互赖关系里寻求互惠，也要敢于好聚好散")

    # 双赢两栏
    _rect(s, 60, 176, FULL, 96, _SAND)
    _rect(s, 600, 188, 4, 72, _BRONZE)
    _text(s, 80, 190, 480, 30, "我方的「赢」", size=15, color=_NAVY, bold=True)
    _text(s, 660, 190, 480, 30, "对方的「赢」", size=15, color=_NAVY, bold=True)
    _text(s, 80, 224, 480, 28, "必须保住的结果", size=13.5, color=_INK)
    _text(s, 660, 224, 480, 28, "同样必须被满足", size=13.5, color=_INK)

    _text(s, 60, 286, 900, 30, "情感账户  ·  Emotional Bank Account",
          size=14.2, color=_NAVY, bold=True)
    _rect(s, 60, 322, 1160, 22, _PAPER, _SAND, 0.75)
    _rect(s, 60, 322, 760, 22, _BRONZE)
    _text(s, 60, 350, 1160, 26,
          "存款：理解他人 · 注意小节 · 信守承诺 · 明确期望 · 正直诚信 · 勇于致歉",
          size=13.5, color=_INK)

    rows = [
        ("准确定义",
         "以高信任关系开展协作、寻求共同利益；柯维把它列为公众成功的起点，前提是双方都能自主选择。"),
        ("关键原则",
         "六种交往模式中，利人利己与谈不拢时的好聚好散最可持续。双赢靠诚信、成熟（勇气与体谅平衡）、富足心态。"),
        ("常见误区",
         "把双赢等同于各让一步的折中，或当成讨好对方；原著明确区分妥协与互惠，也反对口称双赢、实则求自己赢。"),
        ("应用示例",
         "跨部门争资源：双方先写「必须保住的结果」与「可以让渡的部分」，再找同时满足两边关键结果的方案；不兼容就体面暂不合作。"),
        ("行动建议",
         "选一段重要关系，两周内做三次「存款」：兑现小承诺、把期望写成可核对的文字、主动澄清一次误解。"),
    ]
    _full_rows(s, rows, y0=382, pitch=58)
    _content_footer(s, 6,
                    "依据：FranklinCovey, Habit 4 / One-Day Outline；Covey (1989), 习惯四")


# --------------------------------------------------------------------------- #
# P7 习惯五
# --------------------------------------------------------------------------- #

def _p7(s):
    _content_header(s, "习惯 05  ·  SEEK FIRST TO UNDERSTAND",
                    "知彼解己：先诊断再开方，先理解对方再争取被理解")

    _rect(s, 60, 176, 500, 96, _SAND)
    _text(s, 80, 192, 460, 32, "① 先理解  ·  移情聆听", size=15,
          color=_NAVY, bold=True)
    _text(s, 80, 230, 460, 28, "站进对方的参照框架，听内容也听情绪",
          size=13.5, color=_INK)

    _rect(s, 700, 176, 520, 96, _TERRACOTTA)
    _text(s, 720, 192, 480, 32, "② 再表达  ·  争取被理解", size=15,
          color="FFFFFF", bold=True)
    _text(s, 720, 230, 480, 28, "理解到位后，用品行、关系与逻辑表达自己",
          size=13.5, color="FFFFFF")
    _text(s, 570, 200, 120, 46, "→", size=18, color=_BRONZE, bold=True,
          align="c")

    _text(s, 60, 288, 400, 28, "诊断在前，开方在后", size=14.2,
          color=_NAVY, bold=True)
    _text(s, 480, 288, 740, 28,
          "避开自传式回应：价值判断 · 追根究底 · 好为人师 · 自以为是",
          size=13.5, color=_TERRACOTTA, bold=True)
    _hline(s, 60, 326, FULL, _SAND, 1.0)

    rows = [
        ("准确定义",
         "先倾听、理解并尊重对方视角，再有勇气得体地表达自己的想法与感受；官方称之为移情沟通的习惯。"),
        ("关键原则",
         "移情聆听要站进对方的参照框架，听内容也听情绪；先理解到位，再谈表达自己的判断。上方横幅列出的四类自传式回应都要避开。"),
        ("常见误区",
         "把复述句式当成移情聆听；原著区分技巧与「真想理解」的动机，只模仿话术容易被察觉成操控。"),
        ("应用示例",
         "下属交付延期：先请对方讲清卡点与顾虑，用自己的话复述并确认，再一起看排期，比立刻给建议更容易拿到真实信息。"),
        ("行动建议",
         "本周选三次重要对话，规定自己对方说完前不提建议；先复述处境与感受并请对方确认，再陈述判断。"),
    ]
    _full_rows(s, rows, y0=342, pitch=62)
    _content_footer(s, 7,
                    "依据：FranklinCovey, Habit 5；Covey (1989), 习惯五")


# --------------------------------------------------------------------------- #
# P8 习惯六
# --------------------------------------------------------------------------- #

def _p8(s):
    _content_header(s, "习惯 06  ·  SYNERGIZE",
                    "统合综效：珍视差异，创造谁都没单独想过的第三方案")

    # 1+1>2 大字块
    _rect(s, 60, 176, 440, 120, _SAND)
    _text(s, 80, 196, 400, 70, "1 + 1  >  2", size=43.5, color=_NAVY,
          bold=True, font="Georgia", align="c")

    # 三级信任柱
    cols = [("提防", "低信任", 60, 420, 100, _SAND, _NAVY),
            ("妥协", "1+1≈1.5", 200, 370, 150, _BRONZE, "FFFFFF"),
            ("统合综效", "高信任", 340, 320, 200, _TERRACOTTA, "FFFFFF")]
    for name, sub, x, y, h, col, fg in cols:
        _rect(s, x, y, 130, h, col)
        _text(s, x + 10, y + h - 70, 110, 30, name, size=14.2, color=fg,
              bold=True, align="c")
        _text(s, x + 10, y + h - 38, 110, 30, sub, size=13.5, color=fg,
              align="c")
    _text(s, 60, 536, 440, 30, "差异是资源，不是需要抹平的噪音",
          size=14.2, color=_NAVY, bold=True)
    _text(s, 60, 568, 440, 60,
          "低信任只能互相提防，中等信任止于妥协；高信任才可能产出两边都没想到的第三选择。",
          size=13.5, color=_INK, spacing=1.28)

    rows = [
        ("准确定义",
         "借助不同视角解决问题与创新，取得任何个人单独做不到的成果；柯维称之为创造性合作，整体大于部分之和。"),
        ("关键原则",
         "核心动作是珍视差异，把不同看法当资源。低信任只能互相提防，中等信任止于妥协，高信任才可能产出第三选择。"),
        ("常见误区",
         "把「大家都同意的折中」当成统合综效；妥协是双方各损失一点，统合综效是产出比两边原方案都更好的新方案。"),
        ("应用示例",
         "产品与销售对上线节奏分歧：不在各让一周之间取中，而是共同设计「核心功能先上、培训同步、反馈内嵌」。"),
        ("行动建议",
         "下次分歧先请各方写下绝不放弃的条件，再要求提出至少两个不同于双方原案的第三方案，前 10 分钟禁止评价。"),
    ]
    _numbered_rows(s, rows, x0=540, label_x=586, body_x=714, body_w=506,
                   line_x=586, line_w=634, vline=False)
    _content_footer(s, 8,
                    "依据：FranklinCovey, Habit 6；Covey (1989), 习惯六")


# --------------------------------------------------------------------------- #
# P9 习惯七
# --------------------------------------------------------------------------- #

def _p9(s):
    _content_header(s, "习惯 07  ·  SHARPEN THE SAW",
                    "不断更新：保护并提升最重要的资产——你自己")

    dims = [("身体", "运动 · 营养 ·\n休息", 60, 176),
            ("心智", "阅读 · 学习 ·\n写作", 290, 176),
            ("情感 / 社会", "共情 · 服务 ·\n关系投入", 60, 356),
            ("精神", "价值澄清 · 反思 ·\n自然", 290, 356)]
    for name, b, x, y in dims:
        _rect(s, x, y, 180, 130, "FFFFFF", _SAND, 0.75)
        _text(s, x + 16, y + 16, 150, 30, name, size=15, color=_NAVY,
              bold=True)
        _text(s, x + 16, y + 56, 150, 64, b, size=13.5, color=_INK,
              spacing=1.3)
    _oval(s, 235, 301, 60, 60, _TERRACOTTA)
    _text(s, 238, 315, 54, 30, "自己", size=13.5, color="FFFFFF", bold=True,
          align="c")

    _text(s, 60, 504, 420, 30, "学习 → 坚持 → 实践：产能持续上升的螺旋",
          size=14.2, color=_NAVY, bold=True)
    _text(s, 60, 538, 420, 86,
          "四个维度都需要定期更新；只补一个维度，其余仍会拖住前六个习惯的发挥。",
          size=13.5, color=_INK, spacing=1.3)

    rows = [
        ("准确定义",
         "留出更新时间以提升动力、精力与工作生活平衡；柯维用「磨锯子」作比——钝工具再用力也低效。"),
        ("关键原则",
         "四个维度均衡更新：身体（运动、营养、休息）、心智（阅读、学习、写作）、情感与社会关系（共情、服务、关系投入）、精神（价值澄清、反思）。"),
        ("常见误区",
         "把更新等同于放松或透支后补救；原著讲的是围绕产出 / 产能平衡持续投入产能，而不是崩溃后才休假。"),
        ("应用示例",
         "把每周两次运动、一次深度阅读、一次与重要的人好好相处写进周计划，视为不可随意挤掉的第二象限大石头。"),
        ("行动建议",
         "四个维度各选一个 20–30 分钟的最小动作，排进未来四周日历；每周日检查哪个维度缺席，缺哪个补哪个。"),
    ]
    _numbered_rows(s, rows, x0=540, label_x=586, body_x=714, body_w=506,
                   line_x=586, line_w=634)
    _content_footer(s, 9,
                    "依据：FranklinCovey, Habit 7: Sharpen the Saw；Covey (1989), 习惯七")


# --------------------------------------------------------------------------- #
# P10 总结与落地
# --------------------------------------------------------------------------- #

def _p10(s):
    _content_header(s, "总结与落地  ·  FROM READING TO DOING",
                    "把七个习惯用起来：一条主线、三阶段、四周落地清单")

    _rect(s, 60, 176, 520, 70, _SAND)
    _text(s, 80, 190, 480, 40, "依赖  →  独立  →  互赖", size=18.8,
          color=_NAVY, bold=True)

    steps = [("1  主线回顾",
              "依赖 → 独立 → 互赖：先个人成功（1–3），再公众成功（4–6），由习惯 7 持续供能。顺序不能跳级。"),
             ("2  判断标准",
              "既看结果是否可持续，也看产能是否被消耗；柯维反对只求短期产出的技巧，主张以原则为中心、由内而外。"),
             ("3  最小起步",
              "不必一次改七个习惯。先选一个当前最卡住你的环节，连续做四周，再回头看主线是否往前挪了一格。")]
    for i, (t, b) in enumerate(steps):
        y = 258 + i * 108
        _card(s, 60, y, 520, 100)
        _text(s, 80, y + 10, 480, 26, t, size=15, color=_NAVY, bold=True)
        _text(s, 80, y + 40, 480, 54, b, size=13.5, color=_INK, spacing=1.28)

    # 右侧四周清单表
    _text(s, 620, 176, 600, 28, "四周落地清单", size=15, color=_NAVY,
          bold=True)
    _rect(s, 620, 214, 600, 44, _NAVY)
    _text(s, 634, 224, 110, 26, "时间", size=13.5, color="FFFFFF", bold=True)
    _text(s, 750, 224, 200, 26, "对应习惯", size=13.5, color="FFFFFF",
          bold=True)
    _text(s, 960, 224, 250, 26, "本周动作", size=13.5, color="FFFFFF",
          bold=True)

    table = [
        ("第 1 周", "积极主动", "记录一次主动回应；当天兑现一个小承诺。"),
        ("第 2 周", "以终为始 + 要事第一", "写一版使命宣言；把第二象限大石头锁进日历。"),
        ("第 3 周", "双赢 + 知彼解己", "情感账户存款三次；三次对话先复述再表达。"),
        ("第 4 周", "统合综效 + 不断更新", "做一次第三方案讨论；四维度各完成一次更新。"),
    ]
    for i, (wk, habit, act) in enumerate(table):
        y = 258 + i * 78
        bg = "FFFFFF" if i % 2 == 0 else _PAPER
        _rect(s, 620, y, 600, 78, bg, _SAND, 0.75)
        _text(s, 634, y + 12, 110, 28, wk, size=13.5, color=_NAVY, bold=True)
        _text(s, 750, y + 12, 200, 52, habit, size=13.5, color=_INK,
              spacing=1.25)
        _text(s, 960, y + 8, 250, 64, act, size=13.5, color=_INK,
              spacing=1.25)

    # 底部复盘三问条
    _rect(s, 60, 590, FULL, 60, _TERRACOTTA)
    _text(s, 80, 602, 1120, 40,
          "每周复盘三问：我是否在影响圈里行动？日程是否体现最重要的事？关系的信任余额是增加还是减少？",
          size=14.2, color="FFFFFF", bold=True)

    _content_footer(s, 10,
                    "依据：Covey (1989) 全书框架；FranklinCovey 官方释义；行动清单为本页整理")


# --------------------------------------------------------------------------- #
# 构建入口
# --------------------------------------------------------------------------- #

_PAGE_FUNCS = [_p1_cover, _p2, _p3, _p4, _p5, _p6, _p7, _p8, _p9, _p10]


def build_seven_habits_deck():
    """造完整 10 页 deck，返回未保存的 Presentation。调用方负责 save。"""
    prs = Presentation()
    prs.slide_width = Emu(int(W * 9525))
    prs.slide_height = Emu(int(H * 9525))
    blank = prs.slide_layouts[6]
    for func in _PAGE_FUNCS:
        s = prs.slides.add_slide(blank)
        _paper_bg(s)
        func(s)
    return prs


def main(out_path="artifacts/七个习惯_精读10页.pptx"):
    import os
    prs = build_seven_habits_deck()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    prs.save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "artifacts/七个习惯_精读10页.pptx"
    print(main(path))

