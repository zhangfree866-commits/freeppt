---
name: freeppt
display_name: "FreePPT"
display_name_en: "FreePPT"
description: "FreePPT：创建专业 PowerPoint。输入主题/大纲/数据、零散要点或读书笔记（可附参考封面图），产出逐页创作编排、原生可编辑的 .pptx；内置 17 种构图原型（含原生图表/表格页与玻璃卡/图标卡/编号卡）、渐变与毛玻璃 alpha、原生形状图标库、演讲者备注自动生成、封面图配色派生、16 套视觉主题、8 类企业固定报告、长 deck 分章护栏、版式账本零重复硬闸（layout_id 全局唯一/相邻不同族/同族页码间隔）、研究来源台账与内容密度校验、纯 CLI 出片与已有 pptx 文字改稿。触发词：FreePPT、freeppt、做PPT、生成PPT、改PPT、读书笔记、幻灯片、pptx。"
description_zh: "按「规划 → 生成 DSL → 布局 → lint 校验 → 编译渲染」五阶段产出原生可编辑 PPTX；读书笔记等非报告类内容走逐页创作编排，可从封面图派生专属配色与母题，避免所有页面套同一模板。"
description_en: "Create native editable PPTX decks through a five-stage pipeline. Creative content such as reading notes is composed page by page with 17 layout archetypes (including native chart/table pages and glass/icon/numbered cards), gradient and frosted-glass alpha fills, a native-shape icon library, generated speaker notes, chapter-based long-deck guardrails, a research-source ledger and a content-density check, while structured reports use 16 themes, 10 masters and 8 templates."
category: document
version: "20261113.1"
author: "张三峯"
---

# FreePPT

## 版权说明

**作者：张三峯** ｜ 公众号：**AI龙卷风**

© 2026 张三峯。开源双许可：**代码 MIT**、**文档与设计资料 CC BY 4.0**（见 `LICENSE` / `LICENSE-DOCS`）。他人使用、修改、分发时须保留作者署名与公众号信息。

> 面向用户的产品介绍见 `README.md`（含功能清单、实测状态、合规边界与核查依据）；本文件是 skill 的执行规范。

## 最高目标与裁决规则

**唯一目标：成品效果追赶豆包。**

任何技术选择，只要有助于追赶豆包效果 → 就做；只要与这条目标冲突 → 就放弃。

「纯离线」「确定性」「引擎自动生成」「架构洁癖」「可复现」这些**都只是手段，不是约束**，永远不得拿来当限制条件，也不得升级成需要用户拍板的命题。别拿手段的纯洁性去换成品效果——这条比下面任何一条都高。

## 首要执行规则：逐页设计、逐页交付、逐页校验

> **优先级声明**：本节是「创作第一性原理」的执行体，**优先级高于本文档其余一切通用建议**。与任何通用建议冲突时（模板更快、套原型更省 token、响应式在 PPT 里没意义、先出草稿再补设计…），一律以本节为准。本节不提供 `--force` 旁路。

**规则**：在每一页的设计环节，模型必须以**设计师身份逐页独立产出完整方案**，而不是给整本定一个版式再套。方案必须覆盖六个维度，缺一维即编译失败。

### 六维规格（`engine/design_spec.py`）

| 维度 | 字段 | 判定口径 | 缺了会怎样 |
|---|---|---|---|
| 布局结构 | `structure` | ≥2 字，非占位话术；同一标签全书 ≤3 页 | 骨架没逐页判断，退回套版 |
| 视觉层级 | `hierarchy` | ≥8 字，且须含层级词（主/次/辅/第一/焦点…） | 说不出谁第一眼 = 所有元素一样重 |
| 组件拆分 | `components` | list ≥2 项，每项须有 `name` + `role` | 组件没角色 = 在堆形状 |
| 交互状态 | `states` | 非空；须覆盖 default / emphasis / disabled 类判断 | 成品无法承载强调与高亮 |
| 响应式适配 | `responsive` | ≥6 字，且须含断点/折叠/堆叠/缩放等具体策略 | 换尺寸就塌，是排版不是设计 |
| 可访问性 | `a11y` | dict，`contrast` / `text_size` / `alt` 至少命中 2 项 | 对比度与字号无据，投影不可读 |
| 设计一致性 | `consistency` | 引用 deck 令牌键名，且键必须在 `design_system` 里真实存在 | 各页自造一套，整本不像一本书 |
| 自证理由 | `rationale` | ≥12 字 | 说不出「为什么这样最有效」 |

**统一设计语言由 deck 级令牌锁定**：`design_system` 必须在 notes 顶层声明一次，含 `palette` / `type_scale` / `spacing` / `font_pair` 四项。每页 `consistency` 只能**引用**这些键，不能各写一套——这就是「各页面之间保持统一设计语言」的可检查形态。

### 三环闭环：设计 → 交付 → 校验

```
① 逐页设计  模型写 design_briefs（六维）
              ↓
② 逐页交付  compose() 编译；入口调 design_spec.require_deck()，缺项即 ValueError
              ↓
③ 逐页校验  lint 再跑一遍六维（防手写 DSL 绕过）；
             verify_spec_compiled() 拿成品 pptx 回验「写了几块就有几块」
```

三环任何一环失败都**不产出成品**。第三环尤其重要：前两环只看 DSL，手写 python-pptx 能完全绕过去——所以必须有一环读成品文件。

**第三环现在是强制关卡，不是可选命令。** `build` 写完文件会立刻对**成品**跑 `audit_design()`，不成立就以退出码 1 结束并明确写「这份文件不能当交付物」。2026-11-13 之前的漏洞是：`audit-design` 只能手动跑、零自动触发点，于是模型手写 pptx 一路无人拦——12 页同构翻车就是这么发生的。判据挂在交付路径之外，等于没有判据。

**密度判据分两层，别搞混**：

| 层 | 判什么 | 性质 |
|---|---|---|
| 硬拦 | 文字堆叠无结构（结构件 <2）、形状 <4、文字压字、文字出界、**文字溢出色块**、**色块压住文字**、**中文字体无中文字形**、同骨架 >4 页、全篇零分隔线 | **缺陷**，必须修 |
| 提示 | 形状数 <20 或结构件 <7（低于参照那种密集编辑风） | **风格**，可忽略 |

分层理由：一份原生图表撑满一页的业务报告只有 9 个形状，视觉上完全成立。把密度当硬拦，等于逼所有 deck 都长成同一副密集编辑样——那恰好是「逐页当设计师」要反对的。**判据把成立的设计判死，比漏判更糟。** 仪式页（封面/封底）另有豁免：识别条件是「巨型标题 ≥28pt 且文字块 ≤5」，不是「字少」——只看字少会把裸排布正文页也当封面放过。

**「能不能读」归硬拦，「够不够密」归提示。** 分界线是：读者拿不到信息 = 缺陷；读者拿得到、只是不如参照那么讲究 = 风格。中文变方框、字溢出色块、页码被吃掉，都属于前者。

### 怎么写（最小可用示例）

```python
# notes 顶层：全书统一设计令牌，只声明一次
notes = {
    "design_system": {
        "palette":    {"ink": "#1C1917", "accent": "#9A3412", "paper": "#FAF7F2"},
        "type_scale": {"h1": 33, "h2": 24, "body": 13.5},
        "spacing":    {"base": 8, "gutter": 76},
        "font_pair":  {"title": "Georgia", "body": "Arial"},
    },
    "pages": [...],
}

# 每一页：六维完整方案，不许复用上一页的答案
design_briefs = {
    0: {
        "structure":   "否定墙：左列六个灰块，右侧一块亮起",
        "hierarchy":   "第一眼右侧亮块，第二眼左侧灰块，辅助是底部来源行",
        "components":  [{"name": "灰块阵", "role": "列举被否定的做法"},
                        {"name": "亮块",   "role": "唯一保留的答案"}],
        "states":      {"default": "全灰+右亮", "emphasis": "描边加粗",
                        "disabled": "降到 40% 不透明度"},
        "responsive":  "窄屏 960px 以下两列改堆叠，投影 16:9 保持两列",
        "a11y":        {"contrast": "正文 8.2:1", "text_size": "最小 13.5pt",
                        "alt": "灰块阵给一句整体说明，不逐块配"},
        "consistency": ["palette", "type_scale", "font_pair"],
        "rationale":   "六个假的对照一个真的，需要并列否定；编号行会丢掉对照关系",
    },
    # 1: {...}, 2: {...}   ← 每页都要重新判断，不许 copy 改字
}
```

```bash
python3 engine/cli.py compose notes.json --briefs briefs.json --out deck.json
```

### 为什么没有旁路

`engine/design_brief.py` 的旧版只有 5 个字段，而且 `check_deck()` **全仓无人调用**——判据写了却没人调，等于文档。这次改名为 `design_spec.py` 并真接进 `compose()` 与 `lint`，就是为了让原则从「建议」变成「约束」。

实测证据：接入当天，`tests/test_design_brief_gate.py` 立刻有 4 个用例变红——它们用的是旧 5 维数据。**按本规则，该改的是测试数据，不是放宽闸门**，已一并升级为六维。

### 已知的一处例外（必须知道，别当范例）

`engine/seven_habits_deck.py` 是 610 行、184 处硬编码坐标的**判据基准**：它证明「参照语法那种密度与版面，判据真的判得过」。但它**不是**交付路径的样例——

- 它直接用 python-pptx 画坐标，不 import `design_spec`、不过 `compose()`；
- 它没有逐页六维简报，因为它的页面是按参照 deck 的实测坐标**复刻**的，不是当页设计的；
- 它 `audit_design` 过 `ok=True`，但那只能说明「这个水位做得到」，不能说明「逐页当设计师」被满足了。

所以：**要学怎么写逐页设计，看 `examples/briefs_renqing_mianzi.json`；要看判据水平，看 `seven_habits_deck.py`。两者别混。** `tests/test_seven_habits_deck.py` 里有一条测试专门钉住这个边界。

## 创作第一性原理（最高准则）

**核心一句**：让大模型先做这一页的「设计师」——先读懂这一页的内容（论点、关键词、名人名言、著名理论、数据），想清楚怎么表达最有效；载体是这**之后**的结果，不是预设。

- **载体随内容长出来，千页千面**：可能有图、可能是原生 SVG、可能是纯字体大字版面、可能是数据可视化，也可能几者混合。被否定的只有一种做法——「先有固定模板、再往里填内容」。
- **统一的是审美语言 / 质量底线，不统一的是结构**：整本可以共用一套配色与气质（看起来是同一本书），但每一页的版面结构都为这页内容重新决定。封面「既是这套风格、又独一份」就是这个标准。
- **配图只是手段，不是目的**，按性价比选载体：
  - 简单概念 / 框架 → 优先原生 SVG（省 credit、更干净、可编辑）；
  - 真实存在的人、事、物（CUDA、DGX、黄仁勋、某款芯片、某次收购）→ 优先联网搜真实照片（更有说服力，几乎不花 AI credit）；
  - 抽象、确实需要氛围的概念 → 才上 AI 量身画的主视觉；
  - 不为配图而配图。
- **判断标准回到「这页怎么表达最有效」**：一句追问用大字最有力，一个框架用结构图最清楚，一组数据用场景大数字最直观——一切手段服务于「让观众秒懂并记住」。

**17 种构图原型、版式账本、概念→图形映射，在这条原理下的定位**：它们是设计师可随手调用的**构件库与底线检查**，不是创作起点，也不是「选一个往里填」的模板库。版式零重复是兜底护栏（防止偷懒套版），不是追求目标；真正的目标是每页表达最优。

**职责边界（诚实标注）**：引擎不会自动「当设计师」；「逐页读懂内容 → 判断载体 → 取素材」这一步由宿主大模型承担（见下方 SVG 融合管线与 `docs/PIPELINE_CONTRACT.md`），引擎负责把决定好的页面忠实编译为原生可编辑 PPTX，并用护栏拦截溢出、重叠、套版等底线问题。**载体需要什么手段就用什么手段**——原生 SVG、真实照片检索、生成式主视觉、纯字体版面，网络和外部服务都不是禁区；唯一标准是这页表达是否更有效。

## 交付自检红线（开工前对一遍，交付前再对一遍）

上面两段是「为什么」，这张表是「怎么判断自己有没有跑偏」。每条都能落到证据上，不是感觉。

### 应该做成什么样

**单页质量**

| # | 标准 | 怎么算达标 |
|---|---|---|
| 1 | 每页先判断载体再动手 | 每页有 `design_brief`，写明载体/结构/主视觉/配图决策/理由 |
| 2 | 千页千面，结构不统一 | 单副几何骨架 ≤4 页；仪式页（封面/章节/封底）豁免 |
| 3 | 统一审美、不统一结构 | 全书同一配色气质；但任意两页内容页的版面骨架不同 |
| 4 | 载体按性价比选 | 简单概念先 SVG；真实人事先搜真实照片；抽象氛围才 AI 画 |
| 5 | 每页一个视觉锚点 | 这一页拿掉文字后，仍有一个东西在表达主张 |
| 6 | 判断标准是「表达最有效」 | 能用一句话说出「这页为什么这么排」，且理由不是「这样好看」 |

**版面设计（用户 2026-11-12 用一份参照 deck 亲自校准，优先级高于上面 6 条）**

用户拿出《高效能人士的七个习惯》10 页精读，说「这个接近我的要求，**页面设计才是核心**」。
解剖结论推翻了我原先的判断——**它零配图**：

| 指标 | 参照 10 页 | 我方 91 页（同口径复测） |
|---|---|---|
| 配图 | **0 张** | 1 张 |
| 形状/页（中位） | **39** | 26 |
| 结构件/页（中位） | **17** | 11 |
| 分隔线 | **45 条，100% 页面** | **0 条，0% 页面** |
| 同骨架最大重复 | **2 页** | 3 页 |
| 版面色数 / 字号种类 / 字体 | **7 / 5 / 2** | — |

所以版面质量靠这四件事，**跟配图无关**（别再拿「配图几张」当指标）：

| # | 标准 | 怎么算达标 |
|---|---|---|
| L1 | 有页面框架 | 页眉细线 + 页眉下全长分隔线 + 左下来源行 + 右下页码；封面/封底可用另一套，但必须成体系 |
| L2 | 结构件要够密 | 每页 ≥20 个形状、≥7 个可视结构件（色块/徽章/条带/线条）；文字块不算 |
| L3 | 用分隔线组织信息 | ≥50% 的页面出现分隔线。水平线切条目、竖线切左右栏、8px 细条做项目符号 |
| L4 | 每页一个不同的视觉论证 | 递进→阶梯；对比→两栏；分类→矩阵；占比→条形；同心关系→圆环；时间→轴。同骨架 ≤4 页 |
| L5 | 一个组件反复用 | 编号徽章 34×34、标签条 118×30、正文块 498×84 这类**尺寸固定**的件，每页复用 4–6 次。这是「可复用的基本组件」，不是「模板」——组件相同、组合不同 |
| L6 | 克制 | 全篇 ≤7 色、≤5 级字号、≤2 种字体。密而不乱靠的是重复与对齐，不是花样 |
| L7 | **不许字压字、不许出界** | 任何两块文字的真实占位不得相交；任何文字不得掉出 1280×720 画布 |
| L8 | **文字不许溢出色块** | 色块内所有文字**聚合**后按各自字号算总占高 ≤ 色块高 − 2×8px。逐块判永远判不出「加起来放不下」 |
| L9 | **中文字体必须有中文字形** | `a:ea` 指向的字族不能是纯西文字体（Arial / Georgia / Helvetica…）；容器高度由内容算，不写死 |
| L10 | **实心色块不许压住文字** | 色块与任一文字框的重合面积 / 文字框面积 ≥85% 视为「在块内正常」，否则算压住。文字还在文件里、只是被盖住，比字压字更隐蔽 |

**L7 的来历（2026-11-12，血的教训）**：这套参照语法第一版做完，L1–L6 全部达标
（结构件 26–37、分隔线 34 条、5 页 5 种骨架），但截图一看是**烂的**：
标题压在正文上、色带里的名称和说明叠成一团、右下角 `/ 05` 掉出画布一半、
矩阵的轴标反复压页脚。L1–L6 数的是"有几个件"，数不出"这两个字是不是叠在一起"。

所以有两条规矩：

1. **`audit-design` 必须审文字占位**（`collisions` / `clipped` 两项），
   按字号×行数估算真实文字高度，而不是用 `shape.height`（框小字大时，
   PowerPoint 不裁字、让字溢出来盖人，用框高判会漏掉整类问题）。
2. **判据通过之后必须看一眼**：`python3 engine/cli.py preview 成品.pptx 输出目录`
   渲染成 PNG。判据能证明"没退化"，证明不了"好看"。
3. **判据必须判黄金参照通过（校准铁律）**：拿参照 deck 跑 `audit-design`，
   必须 0 碰撞、0 出界。若判据连要追赶的目标都判不通过，先改判据、别改目标。
   20261112.9 就踩过：占位估算把每个英文字母/数字/空格都按全宽中文字算，
   导致黄金参照被判 3 碰撞 + 5 出界。修正办法是按 Unicode 东亚字宽加权
   （全宽字 1.0em、字母数字 ≈0.56、空格 0.30），手动换行符 `\n` 单独折行。

**L8–L10 的来历（2026-11-13，《人情与面子》9 页全流程验收）**：
走完 compose → lint → build → 渲染 → **逐页看 PNG**，发现三个 L1–L7 一条都查不出的问题：

- 阶梯第 1 级正文 4 行、色块只放得下 3 行，末尾「演。」掉在块外；
  批注块写死 58px、文字 `max_h=44`，第 3 行落在块外；
  1987 的说明标签写死 `y=480`、数字实际底边 482，说明压在数字下沿。
  **三类症状、同一个根因：容器高度写死，而 PowerPoint 不裁字。**
- 封面批注块底边 636 压住 648 处的页码，「03 / 09」在渲染图里被吃掉一半。
  文字没丢、形状没少、没有碰撞——**色块压字比文字压文字更隐蔽**。
- 整本中文渲染成 `□□□`。查 XML 发现 `a:ea` 指向 `Georgia`/`Arial`（照搬了
  参照 deck 的字体令牌，而那是英文内容）。形状数、结构件、分隔线、压字
  全部正常，只能主动读 XML 查字体名。

这三条确立了一条方法论：**判据的来源必须是渲染图的肉眼验收，不是想象。**
每写一条新判据，都要能指回「哪一页、哪个字、哪张图」。

**校准纪律（新判据必须先自证两条）**：

- 能拦住缺陷：构造最小样本，确认判据真的报警（不只看 `ok=True`）。
- 不误杀正常产物：拿已经肉眼确认过的 deck 跑一遍，`ok` 必须为 `True`。
  2026-11-13 的溢出判据第一版就把《七个习惯》10 页全判死，渲染图逐页看
  完全正常——判据错，不是成品错。**判据把成立的设计判死，比漏判更糟。**

**排版实现纪律**（否则一定压字，我自己踩了 10 次）：

- 两块文字上下叠放，位置一律用 `_line_h(size)` 算，不写死偏移。
  中文字身 ≈ 字号 ×1.333px，行高再乘 1.25。
- 33pt 标题实际行高约 55px，不是 40px。按 40px 留位，标题就压在引言上。
- 不用 `↑ →` 这类箭头字符（Arial 常缺字形，渲染成空白），用轴线或「横轴：紧急度」这种说明文字。
- 不用旋转文本框做竖排轴标（PowerPoint 以中心为锚点旋转，容易溢到隔壁栏）。
- 画布只有 720 高，页码区必须整体落在 720 内，别写在 `690 + 18`。
- **容器高度由内容算，不写死**：`_wrap_h(text, w, size)` 复用
  `layout.leaf_text_h()`，返回实测行高 +6。写死 58px / 156px / 380px
  就是溢出的来源。
- **别把装饰线贴在文字底边**：LibreOffice 与 PowerPoint 的 44pt 行盒都比
  几何估算高，`rect 底边 +34` 和 `+26` 两版都会被穿。改设计位置（移到引言
  上方），别继续调数值。

自检命令：`python3 engine/cli.py audit-design 成品.pptx`（只读成品文件，退出码 0/1）
肉眼看：`python3 engine/cli.py preview 成品.pptx ./预览图`

`audit-design` 失败时会按 `thin_pages` / `bare_pages` / `collisions` /
`clipped` / `overflows` / `font_problems` 逐项列明细，**别只看退出码**：
`overflows` 告诉你是哪个色块放不下，`collisions` 里 `a`/`b` 会写出双方坐标
（如 `色块[900,560,400,100]` vs `03 / 09`），照着改那一处就能过。

**内容厚度**（数字来自 12 份豆包样本实测）

| # | 标准 | 实测参照 |
|---|---|---|
| 7 | 内容要够厚 | 页均可见 144–360 字；我方《英伟达之道》91 页已达 294.6 字 |
| 8 | 允许峰值 | 单页峰值 500–778 字是正常的，不要为了「淡雅」砍内容 |
| 9 | 有真论点论据 | 数据、案例、引文、来源齐备，不是口号拼接 |
| 10 | 时效数字联网核实 | `research:true` 的页必须有 `sources` 台账 |
| 11 | 演讲者备注**不是核心** | 用户明确：备注可有可无。参照 deck 备注本身也有 70% 模板化。成品用 `audit-notes` 判字数与模板化，缺口用 `fill-notes --notes-file` 补 |
| 12 | 备注分档位 | 随笔 25–60 / 常规 100–160 / 研究 200+，由 deck 自身均长推断，不能一刀切 |

**技术产物**

| # | 标准 | 判定方式 |
|---|---|---|
| 13 | 原生可编辑，不是截图 | 可编辑形状占比 >0.95（我方实测 0.9996） |
| 14 | 图表用原生 chart | 不贴图代替图表 |
| 15 | 双字体 | 标题衬线 + 正文黑体 |
| 16 | 字号分层 | 正文 10–14pt、标题 24–34pt、图注 8–9pt |
| 17 | 功能色全书一致 | 同一体系色重复出现（如 PDCA 四色） |
| 18 | 渐变按需 | 集中封面/章节页，内容页保持扁平 |
| 19 | 章节呼吸页 + 页码 | 长 deck 必备 |
| 20 | 来源印在可见处 | 不在备注里藏来源 |

**工序**

| # | 标准 | 依据 |
|---|---|---|
| 21 | 长 deck 分章、逐批校验 | 30 页以上走 `docs/LONGFORM_SOP.md` |
| 22 | `lint error=0` 才交付 | 有 blocker 不交付 |
| 23 | 误报人工裁定留痕 | 用 `lint_ack`，不用 `--force` 顶 |
| 24 | 附件框架图原生重绘 | 不贴图、也不丢图 |
| 25 | 首版不达标如实说 | 续做到达标再交付，不拿半成品交差 |
| 26 | 每页留设计简报 | `design_briefs` 是编译前提，不是建议 |
| 27 | 产物侧也要查 | 手写脚本生成的 pptx 一样跑 `audit-pptx`，备注跑 `audit-notes` |

### 不应该做成什么样

**绝对不做**

| # | 禁止项 | 为什么 |
|---|---|---|
| 1 | 先有固定模板再往里填 | 这是唯一被否定的做法，是整套准则的靶心 |
| 2 | 内容不同却套同一版式 | 122 页翻车产物就是这么来的（12 页同一副「编号方块+小标题+右侧说明」） |
| 3 | 每页都配图 | 那只是换了个新模板；配图是手段不是目的 |
| 4 | 分章复用版式 | 分章复用只会产生毫无设计感的东西 |
| 5 | 流水账（标题+几个要点） | 没表达，只是把目录摊开 |
| 6 | 换版式名骗闸门 | 自报标签不可信，判据只认坐标 |

**曾经被错当目标的**

| # | 禁止项 | 现状 |
|---|---|---|
| 7 | 纯离线 | 已于 20261112.5 从 skill 删除 |
| 8 | 零位图 / 全手绘 | 已确认是手段，「架构洁癖要彻底丢」 |
| 9 | 把确定性、可复现当目标 | 它们是工程属性，不是成品效果 |
| 10 | 把「引擎自动生成」当卖点 | 引擎不会当设计师，判断在宿主模型 |
| 11 | 为架构纯洁牺牲效果 | 与最高目标直接冲突 |
| 12 | **拿「配图几张」当版面质量指标** | 用户 2026-11-12 亲自纠正：参照 deck 零配图却达标。版面质量 = 框架 + 结构件密度 + 分隔线 + 每页不同论证，与图片无关 |
| 13 | **把备注覆盖率当成品达标线** | 用户原话「备注可有可无」。备注只是交付附件，版面才是核心 |
| 14 | **只跑判据、不渲染就交付** | 2026-11-12 实测：L1–L6 全绿的 5 页样本，实际渲染有 10 处压字/出界。几何判据证明不了「能看」 |

**不许有的行为**

| # | 禁止项 | 说明 |
|---|---|---|
| 12 | 自己写 Python 绕开 `compose()` 拼 pptx | 122 页翻车根因：闸门全挂在 DSL 上，绕过就全程静默 |
| 13 | 只改文档不改代码 | 造一份坏样本喂进去还拦不住，就说明闸门是假的 |
| 14 | 用 `--force` 代替真修 | `--force` 会写入强制构建标记，是最后手段 |
| 15 | 把推断说成实测 | 每句话都要标清是实测 / 推断 / 未验证 |
| 16 | 改某个 PPT 而不是改 skill | 用户要的是能力提升，不是某一本书变好看 |
| 17 | 把架构问题甩给用户拍板 | 需要决策时只给「哪个选项成品效果更好」的明确主张 |

**本质定位（不是什么东西）**

| # | 不是 | 是 |
|---|---|---|
| 18 | 模板库 | 构件库：17 原型可随手调用，也可完全不用 |
| 19 | 「选一个原型再填」 | 「读完内容再决定怎么排」 |
| 20 | 截图/拼图工具 | 原生可编辑 PPTX 生成器 |
| 21 | 套壳抄别人产品 | 独立原创实现 |

## 任务路由

| 任务 | 路径 |
|---|---|
| **追求成品级效果（每页又美又有内容，对标豆包 PPT）** | **「逐页设计师」判断优先**（见上方第一性原理）：先逐页读懂内容、决定载体，再走 SVG 融合管线 `compose --emit-plan` → 逐页 SVG → `svgguard` → `compile-svg`，契约见 `docs/PIPELINE_CONTRACT.md`；17 原型只是构件库，长项目用 `cli.py ledger layout_ledger.json` 把「全本版式零重复」卡成兜底硬闸 |
| 从零 / 基于材料生成 | 遵循本文件五阶段主干（6 步落地） |
| **长内容（30 页以上 / 分章 / 培训课件 / 读书笔记 / 方法论手册）** | **走 `docs/LONGFORM_SOP.md` 12 道工序**，不按 6 步裸跑 |
| 读书笔记 / 品牌叙事 / 演讲稿（要版式变化、可附封面图） | 走「创作式编排」：`cli.py compose` → `lint` → `build` |
| **给参考图、想要"同款设计风格"（不止配色）** | 走「**参考图 → 设计系统（模型驱动）**」工序（见下）：`cli.py design-system scaffold <图>` → 逐维度读图填卡 → `validate` → 用户定稿 → 映射主题 + spec_lock |
| **定风格位 / 配色 / 封面 / 页眉页脚 / 内容页构图** | 查 `docs/DESIGN_GRAMMAR.md` 设计语法库 |
| **单页不知道画什么 / 要"去 AI 味"** | 查 `docs/CONTENT_GRAPHICS.md` 逐单元图形化（40 条概念→图形映射） |
| 周报 / 月报 / 经营分析等结构稳定报告 | 走 `reports.py` 骨架 + 10 套母版；无宿主可用 `cli.py make` 纯 CLI 出片 |
| 编辑已有 pptx | `cli.py inspect` 导出结构 → `cli.py retext` 改文字；边界见 references/edit-existing.md |
| 单节点局部改稿 | `cli.py patch deck.json --set "path=value" --build out.pptx`（改完仍走 lint） |
| 安装到其他宿主 | `./install.sh --host claude\|codex\|cursor\|dsh\|workbuddy --scope user\|project` |
| 开源协作 / 规范 | `CONTRIBUTING.md`、`references/dsl-spec.md`、`docs/THEME_CONTRIBUTION.md` |

## 开源工具链（纯 CLI，不依赖大模型）

**适用范围**：没有 AI 宿主、CI 环境，或只想用命令行出片。以下链路（无 AI 宿主时）确定性、不编造数据。

```bash
# SVG 融合管线（对标豆包成品，落原生可编辑 pptx）：
#   notes → 无坐标 plan.json → 逐页 SVG → 护栏 → 编译
# ⚠️ 创作类 deck 的强制第一环：宿主大模型先逐页当设计师、写出 design_briefs
#    （每页：载体+结构+主视觉+配图决策+理由），再交给引擎。art_direction 的
#    17 原型自动分配只是「宿主没给简报」时的兜底，不是创作起点。
#    写简报：手写 JSON（key=页索引或 page id），或复用 design-system 工序：
python3 engine/cli.py design-system scaffold ref.png --book "书名"
#    把简报传给 compose（缺省则不传，回退到原型池兜底）：
python3 engine/cli.py compose notes.json --emit-plan plan.json --brief design_briefs.json
python3 engine/cli.py svgguard plan.json svg_output/
python3 engine/cli.py ledger layout_ledger.json   # 版式零重复硬闸：唯一 id/相邻不同族/同族间隔
python3 engine/cli.py compile-svg <project_dir> out.pptx --strict
# ppt-master 为外部前置依赖；路径可用环境变量 FREEPPT_PPTMASTER 覆盖。详见
# docs/PIPELINE_CONTRACT.md

# 一句话/零散要点 → 8 类报告任一 → lint → pptx（内容闸门 + 版面闸门）
python3 engine/cli.py make "本周完成 3 项交付；满意度提升到 92%" \
  --type weekly --out out.pptx --out-deck out.json

# 参考图 -> 设计系统（模型驱动）：脚手架 -> 读图填卡 -> 校验 -> 用户定稿
python3 engine/cli.py design-system scaffold ref.png --book "书名"
python3 engine/cli.py design-system validate design_system_card.json

# 已有 pptx：结构导出 + 保留 run 字体的文字替换
python3 engine/cli.py inspect old.pptx --out structure.json
python3 engine/cli.py retext old.pptx --map edits.json --out revised.pptx

# freeform 逐页手搓：DSL -> PNG 视觉回读（lint 有问题也照常出图，便于边修边看）
python3 engine/cli.py render deck.json out_png_dir/
# 定稿交叉验证：inspect 报告含 picture_count（手搓 deck 须为 0）与 shape_kind_totals
python3 engine/cli.py inspect out.pptx
# 手搓 SOP（坐标约定、icon chip、decor/bleed/role 语义标记、双端渲染避坑）见
# docs/FREEFORM_PLAYBOOK.md，可运行样例见 examples/deck_freeform_handbuilt.json

# 三级验收报告：blocker / advisory / info 分组 + 已裁定项
python3 engine/cli.py verify deck.json            # 人类可读，按严重级别分组
python3 engine/cli.py verify deck.json --strict   # advisory 未裁定则退出码 2
python3 engine/cli.py verify deck.json --json     # severity_summary 机器可读

# 改一个节点就重编译（仍受 lint 闸门约束）
python3 engine/cli.py patch out.json --set "slides.0.data.title=新结论" --build revised.pptx

# 全量闸门 / 可量化基准 / 五宿主一键安装
bash tools/check_all.sh
python3 tools/benchmark.py --out bench.json
./install.sh --host all --scope user
```

## 三份方法论文档（长篇 deck 的作业规程）

三份文档构成一套完整工序：**怎么做（SOP）→ 长什么样（设计语法）→ 每页画什么（图形化）**。写 30 页以上的内容前先读，能把返工挡在开头。

| 文档 | 解决什么 | 核心内容 |
|---|---|---|
| [`docs/LONGFORM_SOP.md`](docs/LONGFORM_SOP.md) | **做的顺序** | 12 道工序：读规范 → 读素材 → 出大纲（先同步缺口）→ 定设计系统（含**禁用清单**）→ 先做样本页截图核对 → 分章批量（校验通过才写入）→ lint 闸门 → **误报裁定** → 回读核对 → **素材核验** → 截图抽查 → **缺口如实上报** → 交付自述。含每步判据、失败处理、最小可行 8 步版 |
| [`docs/DESIGN_GRAMMAR.md`](docs/DESIGN_GRAMMAR.md) | **长什么样** | 风格光谱（9.8–31.1 形状/页按选题选位）、语义色编码（色数由维度数派生）、仪式页用图内容页用形状、页眉页脚三件套、封面文字框四范式、内容页六种经典构图、视觉基因提取、渐变/阴影正确口径、六条铁律、数值速查表 |
| [`docs/CONTENT_GRAPHICS.md`](docs/CONTENT_GRAPHICS.md) | **每页画什么** | 「这个概念天然长什么样」主问题 + 三追问、**20 种原生图形原型**（金字塔/漏斗/台阶/嵌套框/四象限/编号卡链/chevron/时间轴/循环回路/S曲线/柱状降序/区间带/占比条/天平/双卡对照/异质双栏/引线/表格/全景地图/超级编号）、**40 条概念→图形映射表**、附件框架图原生重绘五步法、去 AI 味检查清单 |
| [`docs/GAP_ASSESSMENT.md`](docs/GAP_ASSESSMENT.md) | **还差多少** | 六维加权评分（当前约 42/100）、已追平项清单、四项真实差距、下一步唯一该做的事 |

这三份文档的依据是 11 份 85–115 页高完成度成品的结构解剖 + 9 条制作过程取证，非推测；每条实测结论都在文档内标注了出处。


| 模块 | 职责 |
|---|---|
| `engine/page_spec.py` | 规划层 → 无坐标 Deck Plan/Page Spec（融合管线①→②③交接物） |
| `engine/svg_guard.py` | 直接读 SVG 的护栏：对比度/容量/密度/事实来源 |
| `engine/layout_ledger.py` | 版式账本硬闸：layout_id 全局唯一、相邻不同 family/chrome、同族页码间隔 ≥ gap（与几何解耦） |
| `engine/pptmaster_bridge.py` | 定位外部 ppt-master、修 mkdir 平台 bug、串联质检与编译（不改其源码） |
| `engine/brief_fill.py` | brief → 报告骨架填充；未提供的字段写明确的空态说明，图表数值只取自输入，零值代表未提供 |
| `engine/typography.py` | 避头尾禁则、标点悬挂、`——/……` 不拆行、可选中英混排窄空格、声明式字体回退栈；`CJK_KINSHOKU` 进 lint |
| `engine/pptx_edit.py` | 已有 pptx 的结构导出与保留格式的文字替换（**不做 DSL 往返**） |
| `engine/deck_patch.py` | 按点号路径改 DSL 单节点 |
| `tools/benchmark.py` | 版面错误数 / 可编辑形状占比 / 溢出率 / 耗时；只测本仓库，不编造竞品数据 |
| `tools/render_check.py` | LibreOffice pptx→PDF→PNG 回归；缺 `soffice` 时明确 `skipped`，CI 强制断言 `ok` |
| `install.sh` | WorkBuddy / Claude Code / Codex CLI / Cursor / DSH 五宿主安装，幂等引导块，卸载先备份不删文件 |

**许可**：代码 MIT、文档与设计资料 CC BY 4.0（`LICENSE` / `LICENSE-DOCS`）；作者署名与公众号 AI龙卷风须保留。仓库已公开在 GitHub（`https://github.com/zhangfree866-commits/freeppt`），本机安装副本位于 `~/.workbuddy/skills/freeppt/`；发布清单与宿主路径来源见 `docs/PUBLISHING.md`。

## 核心设计原则（FreePPT 原创）

1. **不直接写 OOXML**：用受限 JSON DSL 描述每页，引擎做确定性布局，再编译成原生 .pptx。
2. **五阶段主干不可打乱**：规划 → 生成 DSL → 布局 → lint 校验 → 编译渲染。渲染永远在最后，且被 lint 闸门拦截（见下节）。
3. **审美数值化、可判定**：所有规范见 references/design-principle.md，lint 不通过即回 DSL 返工，不做「先出页面再看图审美返工」。
4. **风格先路由**：按受众/场合选 scenario，锁死配色、字体、字号梯度、密度下限。
5. **确定性优先**：版面合格由 lint 程序判定，不依赖肉眼截图或模型临场发挥。
6. **内容决定构图，不是模板决定构图**：报告类可走固定母版；读书笔记、品牌叙事、演讲稿等创作类内容走 `composition: freeform`，逐页选择构图原型，并把「相邻页/全篇版式重复」写成 lint 硬错误。

## 参考图 → 设计系统（模型驱动）

当用户给参考图并希望"沿用这套设计"时，**不只跑引擎自动抽色，而是由宿主大模型当设计师，把图抽象成一套可复用设计系统**。引擎不会看图，所以这道工序把"必须看图回答的维度"卡成不可跳过的结构。

**工序（强制顺序）**：

1. 生成空白卡：
   `python3 engine/cli.py design-system scaffold <参考图> --book "书名" --out card.json --checklist list.md`
2. 大模型**逐维度目检参考图**填卡，每个结论都要写 `evidence`（图里看到的具体依据），把握不足标 `confidence`，看不清就留空并记入 `open_questions`。禁止"高级/好看"这类无证据判断。
3. 六个必答维度：
   - **color_climate 色彩气候**：主/辅/点缀色、冷暖与饱和度、签名色及理由；
   - **tone 明暗基调**：深浅主导、对比强度、何时用深色页；
   - **typography 字体气质**：中西文衬线/无衬线、建议的本机可用字体名、字重对比、字号层级；
   - **layout 版式骨架**：栅格栏数、视觉主角位置与视线引导、留白比例、非对称/出血/错位；
   - **shape_language 图形语言**：直角/圆角/有机/手绘、描边还是面块、图标风格；
   - **motifs 装饰母题**：可复用母题（色带/竖线/点/网格/弧）、材质、该复用什么(do)、只属于这张图不该照搬什么(dont)。
4. 映射为可复用构件（`reuse`）：`theme_tokens`（语义配色）、`spec_lock_roles`（反复出现的新字号角色）、`rules`（统一什么、允许每页变什么）。
5. `python3 engine/cli.py design-system validate card.json`：未填全 → 列出缺项、退出码 1，需补齐；引擎只报缺、不代填。
6. **确认闸**：把提炼出的设计系统（配色/字体/母题/样例页）给用户看，`approved=true` 后才铺全本。

**诚实边界**：字体只能从图里推断气质、无法精确识别字体名（需用户确认或指定本机可用字体）；参考图里的具体插画/受版权装饰不会被复制，只能按同气质用原生 SVG/图标重绘；低清/强滤镜/多主体图提炼可能偏差，偏差项如实标 `low` 并提示用户补素材。

## 创作式编排（非固定模板）

**适用场景**：读书笔记、书评、品牌故事、演讲稿、课程讲义等需要视觉变化的内容。固定母版（10 套）仍保留给周报/月报/经营分析这类结构稳定的报告。

> 定位提醒：本节的「17 原型自动分配」是**引擎在没有逐页人工设计时的高质量兜底**——它让相邻页不重样，但仍属于「从构件库里选」。追求对标豆包的成品级效果时，按顶部「创作第一性原理」由宿主大模型**逐页判断载体**（可直接调用这些原型，也可完全不按原型），原型是素材而非起点。

**强制工序（创作类 deck 必走，且已做成编译前提）**：宿主大模型在调用 `compose` 之前，先**逐页产出 `design_briefs`**——每页一条：`carrier`（svg / photo / pure-type / data-viz / prototype）、`structure`（这页用什么结构，一个短标签如「否定墙」「证据阶梯」「因果链」）、`visual_anchor`（主视觉是什么）、`image_decision`（ai / real-photo / svg / none）、`rationale`（为什么这样表达最有效）。通过 `compose(notes, design_briefs=...)` 或 CLI `compose --brief briefs.json` 传入；给定原型就钉用该原型，给定 `__host__` 就留空占位交宿主手绘。简报原文原样写进每张 slide 的 `design_brief` 字段，可追溯。

**这不是建议，是闸门——三道都编译不过就出不了文件**：

| 闸门 | 判据 | 行为 |
|---|---|---|
| 入口 | `compose()` 没收到 `design_briefs` | 直接 `ValueError`，报出两种合法做法 |
| 简报完整性 | 任一页缺 `design_brief`，或五字段有空/占位话术（"无" "TBD" "同上"）/ 过短 / `image_decision` 非法 | `DESIGN_BRIEF_MISSING` **blocker** |
| 结构复用 | 同一 `structure` 标签超过 3 页 | `STRUCTURE_REUSED` **blocker** |
| 几何兜底 | 单副几何骨架出现 ≥5 页（**不听自报的版式名，直接比对坐标**） | `LAYOUT_SKELETON_REPEAT` **blocker** |

四条都不可 `lint_ack` 豁免。若某批页确实就是标准原型（固定报告/纯数据页），在 notes 顶层写 `"brief_pool": "prototype"` 显式声明走兜底——放行但留下 `BRIEF_POOL_FALLBACK` 痕迹，不静默。

**第五道闸门：产物侧，落在 pptx 坐标上（这是曾经最大的漏口）**

上面四道都挂在 DSL / `compose()` 上。只要有人绕开 `compose()`、自己写 Python 拼 pptx，它们一次都不会执行。历史上那套 122 页「顾问式营销」就是这么来的——1011 行 `lib.py`、22 个 `p_*` 页面函数、`deck.json` 里 122 页 `design_brief` 全空，四道闸门全程静默，产物照样交付。

所以另开一个直接读终稿的命令：

```bash
python3 engine/cli.py audit-pptx 成品.pptx
```

它只读 `rect_px` 坐标，不看 DSL、不读 `archetype`、不需要简报，因此对「手写脚本拼出来的 pptx」一样有效。判据与 DSL 侧共用同一套分带指纹，判准也一致：单副骨架 ≥5 页即不通过，文字极少页（封面/章节/封底）自动豁免。

实测对照：那套 122 页产物 → `不通过`，抓出 9 组同构（12/11/11/8/8/7/7/7/5 页）；111 页的正常产物 → `通过`。命令行退出码 0/1，可直接进 CI。

**什么时候必须跑它**：只要交付物不是由 `compose()` 生成（手写脚本、别人的 pptx、外部工具产物），`audit-pptx` 就是唯一有效的一道。`compose()` 生成的产物也建议跑一次——它是终稿视角的最后一道。

**同一道闸门的另一半：演讲者备注**

版面能被抽查，备注同样会漏。那本 91 页《英伟达之道》也是绕开 `compose()` 手写的（`v2/` 下 6 个 builder 脚本），备注 **0/91**，一个 notesSlide 都没有，而 DSL 侧的 `NOTES_COVERAGE` 从头到尾没响过。所以备注也补了成品侧的一判一补：

```bash
python3 engine/cli.py audit-notes 成品.pptx          # 判：覆盖 + 分档厚度，退出码 0/1
python3 engine/cli.py fill-notes  成品.pptx --out fixed.pptx   # 补：只重组页内文字
```

`audit-notes` 的判法与 `audit-pptx` 同源：只读成品文件，不看 DSL。**档位不是一刀切** —— 先用全篇备注均长推断这本 deck 属于哪一档（≤70 随笔 / 70–180 常规 / ≥180 研究），再按本档下限判「过薄」，所以一篇 20 字短注的语录型 deck 不会被误判，而研究型 deck 里夹一页 60 字会被告警。分档阈值来自 12 份豆包样本实测（随笔均 25.3、常规 99–150、研究 227.8/252.9）。

`fill-notes` 刻意克制：**只重组该页已有文字**，不生成新事实、不编造数字；**幂等**（已有非空备注默认跳过，要重写加 `--overwrite`）；**确定性**（同一输入两次结果逐字一致）。实测 91 页：`0/91 → 91/91`，均长 202.6 字，0 页过薄，档位自动落到 research。它是急救版讲稿，交付前仍应人工打磨成真的讲法。

**为什么几何判据必须听坐标**：实测把 12 页同构页的 `archetype` 改成 12 个不同名字、几何一字不动，旧闸门照样 `ok=True` 放行。自报标签是靠不住的，所以兜底判据只读坐标。同一份实测也校准了阈值：正常产物最大同骨架组是 4 页，翻车样本是 11/8/8/7/7 页，所以取 5。仪式页（封面/章节/封底）豁免——一本书 11 个章节页长得一样是对的。

**回归锚点**：`tests/test_design_brief_gate.py::TestRealWorldTemplateDeckRejected` 用一本真实的 122 页同构 deck 当样本，断言它必然被拒。以后谁把闸门改松，这条测试会红，而不是等成品拿到手才发现。

**自己验，别听汇报**——跑这一条就够：

```bash
python3 engine/cli.py selfcheck
```

它不读文档、不看配置，而是**当场造样本跑一遍**：生成一份 122 页同构、每页只有版式名没有设计简报的 deck，交给 lint 判，同时生成一份正常产物做对照，再测「改名能否骗过判据」「占位话术是否算没填」「不传简报是否失败」，最后**真的用 python-pptx 手写一份 12 页同构 pptx 存到磁盘**，再让 `audit-pptx` 判版面、让 `audit-notes` 判备注、让 `fill-notes` 补一版再判一次——端到端跑通，不是模拟。预期输出 `11/11 项通过 —— 闸门确实生效`；任何一道闸门被改松，它会当场报 `[FAIL]` 并以退出码 1 结束。

这条命令存在的理由很直白：文档可以写得漂亮、汇报可以说得好听，但**造一份坏样本喂进去还拦不住，就说明闸门是假的**。


老问题：`{template,data}` 展开后，每一页都被 `layout_slide` 强制套上「标题 + 横线 + 内容区 + 页脚」，而且 lint 的 SAFE_AREA / DENSITY / GAP 规则会把自由构图判成错误，于是多页内容看起来一模一样。现在这条链路被替换：

| 层 | 新机制 |
|---|---|
| 画布 | `composition: freeform`：每个节点自带 `rect:[x,y,w,h]` 绝对定位，子矩形以父矩形左上角为局部原点；不再自动加标题横线与页脚带 |
| 构图 | `engine/art_direction.py` 17 种原型（封面编辑式 / 章节页 / 跨页编辑式 / 整页引文 / 错位三栏 / 左右对开 / 页边批注 / 阶梯列表 / 数字焦点 / 不等网格 / 时间轴 / 封底呼应 / 原生图表叙事 / 原生表格看板，以及卡片体系的玻璃卡 `glass-panel` / 图标网格 `icon-grid` / 编号卡 `numbered-cards`）。**默认行为**：按内容语义候选 + 确定性 seed 逐页分配，相邻页不重样，作为「宿主未给设计简报」时的兜底；**创作模式**：宿主通过 `design_briefs` 逐页指定载体/结构/主视觉后，引擎服从简报，原型池只兜底未指定的页。页面携带 `chart`/`table` 数据时自动路由到对应数据原型，编译为原生可编辑图表与表格 |
| 参考图 | `engine/cover_style.py` 从图书封面/品牌主视觉提取主色（按彩度×占比×中间调打分，避开大面积纸底色）、浅色纸底、主色块位置 → 派生调色板、字体气质与贯穿全篇的母题（band / vertical-rule / arc / dots / grid） |
| 几何 | 文本节点高度由自身分词换行实测得出，长文自动缩字号；栏数/格数随实际内容块数变化，不填空卡片 |
| 色彩一致性 | 派生主题由 `themes.build_derived()` 注册，PALETTE 规则仍强制所有色落在派生调色板内 |

**长 deck 分章护栏（防止 88 页式重复事故的前置闸门）**：

- 单个扁平文件的容量上限为 `CHAPTER_PAGE_CAP = 24` 页：`compose` 在做任何几何工作前先检查，超过上限且没有 `kind:"chapter"` 章节页时直接 `COMPOSE BLOCKED` 退出，报出修复方式（分章或显式 `allow_long_deck:true`），把失败挡在规划阶段而不是 build 时抛几十条 lint 错误。
- 分章后多样性预算按章节重置：同一原型可在不同章节合法复用，`LAYOUT_VARIETY` 按每章内容页独立计算（章节页本身不计入预算）；`LAYOUT_REPETITION` 相邻页硬错误保持不变。
- 显式绕过留痕：`allow_long_deck:true` 会在 DSL 写入 `long_deck_forced` 并产生 `LONG_DECK_FORCED` 警告；build 时仍需 `--force`，且编译器在产物内写入 `FreePPTForcedBuildMarker` 文本框与文档 subject，绕过行为在文件本身可见。

**研究来源台账（引擎只做校验，研究由宿主完成）**：

- notes 页面可声明 `research:true`（或研究问题字符串）与 `sources:[{title,url,publisher}]`；compose 透传到 slide 级。
- lint 规则 `RESEARCH_LEDGER`：声明了 research 的页必须带来源台账（含 title 且至少有 url 或 publisher），否则阻断 build。引擎不代做研究，研究动作仍是宿主 agent 在 Step 2 的职责，这条规则把该职责变成可判定的交付物。

**视觉设计系统（对标商业生成式 PPT 的设计语言，原生可编辑）**：

- **渐变填充**：节点或页面可写 `gradient:{stops:[{color,pos,opacity?}],angle}`，编译为真实 OOXML `a:gradFill`（角度单位 1/60000 度）；页面写 `gradient:"theme"` 时解析为当前主题的标志性渐变。`magazine`/`tech`/`oriental` 三主题内置调色板内安全的背景渐变，其余主题默认平面（零回归）。
- **三类透明度（毛玻璃基础）**：形状填充 `opacity`、文字 run `opacity`、描边 `border_opacity`，统一注入 OOXML `a:alpha`。玻璃卡典型值为白填充 `opacity:8` + 白描边 `border_opacity:20`。
- **原生形状图标库**（`engine/icons.py`）：14 个图标用 PowerPoint 原生形状在 100×100 逻辑网格拼合，另带 27 个语义别名（`goal`→target、`risk`→shield 等）；DSL 节点 `{"t":"icon","name":"gear"}`，主题 accent 单色驱动，无位图/SVG 素材、无授权面；`ICON_NAME` 校验图标名，布局保证图标恒为正方形不被拉伸。
- **卡片体系（opt-in）**：`compose --card-system`（或 `card_system:true`）才把玻璃卡/图标网格/编号卡三个原型纳入编排候选，默认关闭以保持历史产物逐字节不变。深色卡片页在该模式下自动套用主题渐变背景。
- **受控外阴影**：节点/卡片/richcard 可写 `shadow:"none"|"soft"|"medium"`（或布尔），未声明回落到主题 `visual.shadow`（默认 none，tech/microsoft/stripe 为 soft）；soft/medium 编译为真实 OOXML `a:outerShdw`（90° 正下方，`shadow_color` 可覆盖投影色）。none 仅关继承阴影、与旧产物字节一致；图标与页面背景保持扁平。非法值由 `SHADOW_VALUE` 拦截，debug_render 给偏移近似。
- **确定性评分选版（opt-in）**：`compose --scoring`（或 `scoring:true`）把选版从 `rng.shuffle` 换成内容特征评分（KIND_PREFS 人工偏好序 + 要点容量 + 金句/左右对比/指标/时间线结构信号），同一份 notes 在任意 seed 下产出同一套原型计划；rng 仍负责逐形状几何微调。默认关闭保留旧 shuffle。
- **12 列声明式网格**：freeform 顶层节点可用 `col_start`（1 基）+ `col_span` 声明水平定位，消费主题 `grid_columns`（默认 12）映射到内容带（60→1220、列距 24px），`rect` 仍负责 y/h，支持 7+5 非对称错位；嵌套节点写 col 会被忽略并警告，越界由 `GRID_COLUMN` 拦截，无字段节点走旧绝对 rect 路径。
- 以上原语贯穿 layout / lint / compiler / debug_render 全链路；调试接触表（`debug_render.py`）支持渐变近似、alpha 混合与图标/圆角绘制。

**演讲者备注（speaker notes）**：

- compose 默认对每页生成**确定性**的讲稿（`_speaker_notes`）：只把该页已有的标题/导语/要点/引文重组为口语化串场，不编造数据；页面自带 `notes` 字段时原样优先。讲稿编译为真实 `notesSlide`，不出现在画面上。
- lint：开启讲稿覆盖时（composed deck 默认），缺讲稿触发阻断规则 `NOTES_COVERAGE`；讲稿不足 40 字给 `NOTES_THIN` 提示（非阻断）。可用 `speaker_notes:false` 关闭生成。
- **成品侧的判与补（重要）**：上面两条都挂在 DSL 上，绕开 `compose()` 手写 pptx 时全程静默——真实事故是 91 页那本备注 0/91、lint 从没响过。所以另有两个只看成品文件的命令：
  - `audit-notes deck.pptx` —— 判。读 `has_notes_slide`，档位（随笔/常规/研究）由**该 deck 自身均长**推断，再按本档下限判「过薄」，仪式页（文字 ≤24）豁免。不通过退出码 1。
  - `fill-notes deck.pptx --out fixed.pptx` —— 补。只重组该页已有文字，不引入页面外信息；**幂等**（已有备注默认不覆盖，要重写加 `--overwrite`）；**确定性**（同一输入两次结果逐字一致）。这是急救版讲稿，交付前仍应人工打磨成真的讲法。
- 内容密度：composed 内容页可见文字少于 60 字时给 `CONTENT_DENSITY` 警告，引导结合研究台账向页均 150–250 字靠拢；封面/章节/封底/引文/图表/表格原型豁免，警告不阻断构建。

**新增硬闸门（阶段 4，不通过就回到 DSL 返工）**：

- **三级严重度**（`engine/lint.py`）：每条诊断带 `severity` 字段，分 `blocker`（硬缺陷，必须修源头，**不可豁免**）/ `advisory`（检测器存疑，需人裁定）/ `info`（纯测量，无需动作）。`ok` 恒等于「零 blocker」；返回结构保留 `errors`/`warnings` 原意（`warnings` = 尚未裁定的 advisory），另加 `acked`（已裁定项）与 `severity_summary`（各级计数），旧调用方与旧测试不受影响。
- **advisory 人工裁定（`lint_ack`）**：deck 顶层写 `lint_ack:[{code, slide?, reason}]` 可把某条 advisory 判为"设计意图"。三条约束让它成为「裁定」而非「静音」：① `reason` 必填，裸压制直接判 `LINT_ACK_INVALID`；② 只能裁定 advisory，对 blocker 写 ack 会被 `LINT_ACK_ON_BLOCKER` 驳回（阻断项必须改源头）；③ 未匹配任何诊断的 ack 报 `LINT_ACK_UNUSED`（info 级），防止过期裁定累积。裁定理由会出现在 `verify` 报告的 ADJUDICATED 段落，随交付一起可见。
- `LAYOUT_REPETITION`：相邻两页构图原型相同 → 错误；
- `LAYOUT_VARIETY`：按章节计算，每章内容页原型数少于 `min(章页数, max(3, ⌈章页数/2⌉))` → 错误；
- `RESEARCH_LEDGER`：声明 research 的页缺来源台账 → 错误；
- `TABLE_SHAPE`：原生表格缺 headers/rows 或行列数不一致 → 错误；
- `LONG_DECK_FORCED`：长 deck 护栏被显式绕过 → 警告（非阻断）；
- `DENSITY_FLAT`：全篇密度一致 → 警告；
- `NOTES_COVERAGE`：开启讲稿覆盖的页缺演讲者备注 → 错误；`NOTES_THIN`：讲稿不足 40 字 → 警告（随笔/语录类 deck 可用短注档位，例外条件见 `docs/DESIGN_GRAMMAR.md` §9）。**成品侧另有 `audit-pptx` / `audit-notes` 两道只看文件的闸门，专治 DSL 闸门静默的绕道产物**；
- `TYPO_FOUND`：上台文本命中常见错别字词对（登陆/登录、帐户/账户等）→ 警告（确定性词典，可 `lint_ack` 裁定）；
- `TEXT_DUP`：≥ 10 字的整句在不同页重复出现 → 警告（跨页复制粘贴滑痕）；
- `FACT_UNSOURCED`：含事实型表述（数字/年份/占比/排名）的页未登记 `sources`/`source` 台账 → **info 级提醒**（引擎只提醒不代核实；`verify --strict` 不因 info 失败）；
- `ICON_NAME`：icon 节点引用了图标库不存在的名字 → 错误；
- `SHADOW_VALUE`：节点 `shadow` 取值不在 none/soft/medium（布尔合法）→ 错误；
- `GRID_COLUMN`：freeform 顶层节点 `col_start`/`col_span` 非整数或越过主题 `grid_columns` 列界 → 错误；`GRID_COLUMN_NESTED`：嵌套节点的 col 字段被忽略 → 警告；
- `CONTENT_DENSITY`：composed 内容页可见文字过薄（< 60 字）→ 警告（非阻断，特殊/数据原型豁免）；
- `FREEFORM_RECT` / `OUT_OF_CANVAS` / `TEXT_OVERFLOW` / `RICHCARD_OVERFLOW` / `CONTRAST` / `PALETTE` / `FONT_SIZE`：几何、溢出、可读性、配色照旧拦；
- 自由画布**不受**旧母版教条约束（安全区、固定间距、底部留白、32–40px 标题），但仍可用 `on` 字段声明文字底色以做 WCAG 对比度校验。

**误报裁定的作业口径**（详见 `docs/LONGFORM_SOP.md` §8）：几何类 advisory 是**估算**，会误报。裁定流程固定三步——`render` 出该页 PNG → 看图判断是真缺陷还是假阳性 → 真缺陷改 DSL、假阳性写 `lint_ack` 留痕。**禁止用 `--force` 代替裁定**（`--force` 会往产物写入 `FreePPTForcedBuildMarker`，是最后手段而非常规路径）。

**从笔记到成片**（五阶段顺序不变，compose 属于阶段 1–2，编译仍在阶段 5）：

```bash
python3 engine/cli.py compose examples/notes_renqing_mianzi.json \
  --briefs examples/briefs_renqing_mianzi.json \
  --cover examples/assets/book_cover_demo.png \
  --out examples/deck_notes_composed.json --ledger examples/style_notes_derived.json
python3 engine/cli.py lint  examples/deck_notes_composed.json
python3 engine/cli.py build examples/deck_notes_composed.json out.pptx
python3 engine/debug_render.py examples/deck_notes_composed.json /tmp/preview
```

`--briefs` 不是可选项。`examples/briefs_renqing_mianzi.json` 是一份**可直接对照的
逐页设计写法**：9 页 9 份答案，每页的 `structure`/`rationale` 都不一样。要看
「模型当设计师」长什么样，读这个文件比读任何说明都快。

也可单独派生主题：`python3 engine/cli.py style cover.jpg --book "书名" --out style.json`。

**可复现**：同一份 notes + 同一张封面 → 同一份 DSL（seed = 书名 + 内容 + 封面 SHA256）；`style.json` 台账记录封面 SHA256、提取色板、主色块位置与对比度。抽色这一步（cover_style.py）不调用大模型、确定性可复现；而整本「逐页怎么表达」的设计判断由宿主大模型承担，见上方「创作第一性原理」。

**示例**：`examples/notes_renqing_mianzi.json`（9 页读书笔记）、`examples/deck_notes_composed.json`（9 页 9 种构图）、`examples/composition_compare.png`（九页拼版）、`examples/FreePPT_读书笔记_创作编排示例.pptx`、`examples/style_notes_derived.json`（来源台账）。封面图为示意重绘，可直接替换为真实封面重跑。

## 视觉主题系统（换肤）

deck 顶层用 `"theme": "<id>"` 选主题（兼容旧 `"scenario"`，theme 优先）。主题是 scenario 的视觉超集，统一定义语义色、中英文字体配对、圆角、阴影档、行距、图表色序列、强调色预算、密度策略；layout/templates/lint/compiler 全部只读主题 token，不写死颜色。

**通用设计主题**

| theme id | 风格 | 气质要点 | 标题字体 |
|---|---|---|---|
| `consulting` | 咨询商务（默认，直角蓝） | 经典海军蓝，零回归基线 | 黑体/Arial |
| `magazine` | 杂志编辑风 | 暖纸底 + 赤陶 + 强网格留白 | 衬线/Georgia+宋体 |
| `tech` | 深色科技 | 冷灰蓝 + 霓虹青 + 圆角柔阴影 | 黑体 |
| `swiss` | 瑞士极简 | 纯白黑白灰 + 单点红，直角 | 黑体 |
| `oriental` | 新中式人文 | 宣纸米 + 朱砂 + 黛蓝，留白气韵 | 衬线/Georgia+宋体 |
| `general` | 通用不锁色 | 仅约束几何，不强制调色板 | 黑体 |

**企业风格主题（风格化参考，非官方 VI，不含商标）**

| theme id | 风格 | 气质要点 |
|---|---|---|
| `mckinsey` | 麦肯锡风 | 深海军蓝、直角、严谨，默认配经营/周月报 |
| `bcg` | 波士顿咨询风 | 墨绿、分析感，默认配季度/复盘 |
| `pwc` | 普华永道风 | 石墨灰 + 小面积橙红，默认配述职/竞聘 |
| `rolandberger` | 罗兰贝格风 | 青蓝、强结构化，默认配年度报 |
| `microsoft` | 微软风 | Fluent 中性灰 + 蓝、小圆角柔阴影 |
| `apple` | 苹果风 | 近黑极简、大留白、极小强调色 |

**数据驱动主题（借鉴公开 DESIGN.md 令牌）**

| theme id | 来源 | 气质要点 |
|---|---|---|
| `stripe` | Stripe DESIGN.md | 靛紫 #533AFD + 墨蓝 #0D253D + 近白卡片 |
| `vercel` | Vercel DESIGN.md | 黑白双色 + 单点链接蓝 #0070F3 |
| `wired` | WIRED DESIGN.md | 纯黑白 + 衬线标题 + 墨蓝链接 #057DBC |
| `ibm` | IBM DESIGN.md | Carbon 蓝 #0F62FE + 4px 直角 |

这 4 套的色值与圆角取自 `references/imported/design_tokens.json`（VoltAgent/awesome-design-md，MIT，公开可见 CSS 令牌），语义映射见 `references/imported/theme_mapping.json`，来源与许可台账见 `references/design-token-sources.md`。导入器 `engine/design_md_import.py` 只抽取源文件中真实存在的数值，缺键直接报错、不猜测语义；`tests/test_design_md_import.py` 断言每个 hex 都能追溯到来源。边界：这些是提取令牌而非官方 VI，工程内不存原文、不含商标、运行时不依赖该仓库。

约束：主题内所有语义色必须落在该主题调色板内（lint PALETTE 保证自洽）；企业主题为行业通用近似配色而非品牌官方规范；新增主题在 `engine/themes.py` 注册，consulting 的 token 已锁定为历史值，改动会破坏零回归测试。

## 企业报告场景 + 智能内容创作

固定报告类型（`engine/reports.py`），每类内置咨询式叙事结构与模板映射，agent 按 `references/content-playbook.md` 扩写：

| 类型 id | 报告 | 默认主题 | 页数 |
|---|---|---|---|
| `weekly`/`monthly` | 周报/月报 | mckinsey | 6/7 |
| `quarterly`/`annual` | 季度报/年度报 | bcg/rolandberger | 8/10 |
| `performance`/`competition` | 述职/竞聘 | pwc | 9/8 |
| `retrospective`/`business` | 复盘/经营分析 | bcg/mckinsey | 8/8 |

智能创作链路（`engine/content_ai.py`，确定性结构 + agent 语言创作，无内置模型客户端）：
1. `skeleton <类型>` 生成带占位与写作提示的结构化骨架；
2. `route <类型> --brief-file 要点.txt` 把零散要点按关键词自动路由到对应页面（指标→KPI、趋势→图表、问题→诊断卡、计划→举措）；
3. agent 依据 playbook 做扩写/润色/MECE 梳理，**禁止编造数据**，缺数据保留占位或向用户索要；
4. `check` 内容把关（占位残留 PLACEHOLDER、套话 CLICHE、无据主张 WEAK_CLAIM、非结论标题 ACTION_TITLE、图表缺来源 MISSING_SOURCE），再走 `cli.py lint` 版面校验，两关通过才 build。

## 已具备能力

- 原生图形/文本/图表 + KPI + 卡片 + 原生形状流程图（oval/chevron/arrow）+ 程序化原生图标节点（`icon`，14 图标 / 27 别名，零素材可编辑）。
- **自动配图（三通道，优先级从高到低）**：
  1. 程序化矢量 `engine/vector_art.py`：PNG+可编辑 SVG，10 个 motif（growth/dashboard/network/funnel/cycle/shield + matrix/org/map/venn），无水印无授权问题；
  2. 网页授权图：`engine/web_search.py` 按关键词检索 Wikimedia Commons（出直链/授权/作者/来源页，可 `--manifest` 直接产清单，`--permissive` 只留 CC/CC0/公有领域），再由 `engine/web_images.py` 下载到本地 + `sources.json` 台账，lint 强制来源标注（WEB_CREDIT）；
  3. 生成式 ImageGen（需显式选用）：标识由生成服务方按法规添加，FreePPT 不修改、不擦除；仅在前两条通道无法覆盖写实场景时使用。
  封面可用背景图+蒙层；image 节点 center-cover 裁剪。
- **母版版式库**：10 套模板（cover/agenda/section/three_cards/kpi_row/chart_insight/image_text/process/timeline/closing），写数据即出片，见 engine/templates.py。
- **自由画布 + 创作式编排**：`composition:freeform` 绝对定位、节点 `rect/rotate/opacity/border_opacity/valign/on/decor/bleed/shadow` 与顶层 `col_start/col_span`（12 列网格）、竖向分隔线；17 种逐页构图原型（含玻璃卡/图标网格/编号卡三个 opt-in 卡片原型）、封面图派生配色与母题、版式重复硬拦截、长 deck 分章护栏、`--scoring` 确定性选版，见 engine/art_direction.py 与 engine/cover_style.py。
- **渐变/毛玻璃/阴影视觉系统**：节点/页面 `gradient`（含 `"theme"` 哨兵）编译为真实 OOXML `gradFill`；形状/文字/描边三类 alpha 通道统一注入，可做毛玻璃卡；深色卡片页自动套主题渐变；`shadow` 注入可编辑 `outerShdw` 外阴影。
- **演讲者备注**：compose 确定性生成每页讲稿（只重组页面已有文字，不编造数据），编译为真实 notesSlide；`NOTES_COVERAGE`/`NOTES_THIN` 闸门管覆盖与厚度，`speaker_notes:false` 可关。**成品侧**另有 `audit-notes`（只读文件判覆盖与分档厚度）与 `fill-notes`（幂等、确定性地补一版只重组页内文字的急救讲稿），专治绕开 `compose()` 的产物。
- **原生数据原语**：页面携带 `chart`（kind/categories/series）或 `table`（headers/rows）数据时，compose 自动路由到 chart-story / table-board 原型，编译为 PowerPoint 原生可编辑图表与表格（非贴图、非文本框伪装）；inspect 可回读图表/表格结构。
- **动画与转场**：slide 级 `transition:"fade"` 与 `anims`（fade / fly-up，按 `_name` 定位），由 engine/animator.py 注入 OOXML（python-pptx 本身不支持）。
- **内容质量闸门**：`CONTENT_DENSITY` 警告薄内容页（< 60 字，引导向页均 150–250 字靠拢）、`RESEARCH_LEDGER` 拦截有研究标记无来源台账的页、`ICON_NAME` 拦截非法图标名。
- 免 Office 验收：`python3 engine/debug_render.py deck.json outdir` 出全页 PNG（接触表支持渐变近似、alpha 混合与图标/圆角绘制）。

### 配图标识合规边界（强制）

- **默认无 AI 标识**：程序化矢量与授权网图不是生成合成内容，它们本身不带标识，也不需要删除任何东西。FreePPT 的默认配图路径就是这两条。
- **FreePPT 不实现「去除 / 擦除 AI 标识」**。已添加的生成合成内容标识不得恶意删除、篡改、伪造、隐匿；为他人实施上述行为提供工具或服务，同样被禁止（《人工智能生成合成内容标识办法》第十条）。
- **合规的无标识生成图路径**：用户向生成服务方申请「未添加显式标识」的原件，由服务方在用户协议明确标识义务与使用责任、并依法留存相关日志不少于六个月的前提下提供（该办法第九条）。FreePPT 只引用该原件，不参与生成或去标。
- **义务仍然存在**：文件元数据中的隐式标识不得移除（该办法第五条）；用户对外发布生成合成内容时，应主动声明并添加显式标识（该办法第十条）。
- FreePPT 是本地 PPT 生成工具，不是网络信息服务提供者；它不代替用户或生成服务方履行协议、留痕与声明义务。以上为工程侧对条文的理解，不构成法律意见。

## 推荐输入：模板规格

优先用 `{template,data}` 形式而非裸 DSL（examples/deck_v2.json）：版式、间距、字号、动画时机全部锁定，调用方只填内容。

## 五阶段主干（强制顺序，不可打乱）

| # | 阶段 | 职责 | 引擎 / 产物 | 闸门 |
|---|---|---|---|---|
| 1 | **规划** | 需求六维对齐、素材核实、风格路由、逐页结构 | SKILL 流程 + references/scenarios/* | 未对齐禁止开工 |
| 2 | **生成 DSL** | 逐页写受限 JSON（不直接写 pptx/OOXML） | 产物 `deck.json`，语法见 references/dsl.md | 节点必须在 DSL 白名单内 |
| 3 | **布局** | 固定矩形 + 行列约束，确定性算出每个元素坐标 | `engine/layout.py`（模板先经 `templates.expand_deck`） | 无越界坐标 |
| 4 | **lint 校验** | 数值化规范逐条判定 | `engine/lint.py`，命令 `cli.py lint` | 必须 `ok:true`，否则回第 2 阶段改 DSL |
| 5 | **编译渲染** | 生成原生可编辑 .pptx + 动画/转场 | `engine/compiler.py` + `animator.py`，命令 `cli.py build` | lint 不过则 `BUILD BLOCKED`，不产出文件 |

关键约束：**第 5 阶段被第 4 阶段硬拦截**——`cli.py build` 内部先跑 `lint_deck`，非 `ok` 且未显式 `--force` 时直接返回，不调用编译器。因此渲染只在通过后发生一次，「优化」= 第 4 阶段诊断驱动的回第 2 阶段数据返工，而非渲染后审美返工。

## 操作流程（五阶段的落地步骤，闸门制）

- **Step 1 需求对齐（阶段 1）**：主题 / 受众 / 目的 / 页数 / 风格 / 素材 六维。缺失项一轮问完（≤3 问）；未对齐禁止开工。创作式编排页数超过 24 页时，必须同步规划章节结构（每章一个 `kind:"chapter"` 页），否则 compose 会在规划阶段被护栏拦截，禁止靠 `--force` 硬出长文件。
- **Step 2 收集素材（阶段 1）**：提取上传材料；涉时效数字/陌生术语 → 联网核实并记录 Source。需要外部研究的页在 notes 标 `research:true` 并附 `sources:[{title,url,publisher}]` 台账；引擎不代研究，`RESEARCH_LEDGER` 闸门会拦截有 research 标记却无来源的页。
- **Step 3 风格路由（阶段 1）**：读对应 scenario（如 references/scenarios/consulting.md）+ design-principle.md，产出每页结构。
- **Step 4 逐页写 DSL（阶段 2）**：每页一个 JSON，结构见 references/dsl.md。
- **Step 5 布局 + lint（阶段 3、4）**：`python3 engine/cli.py lint deck.json`（内部先布局后校验）；按 diagnostics 回 Step 4 修 DSL 至 `ok:true`。
- **Step 6 编译交付（阶段 5）**：`python3 engine/cli.py build deck.json out.pptx`；可选 `debug_render.py` 出全页 PNG 做视觉复核（不需要装 Office）。

## 严格约束

- 对用户只说「内容大纲 / 风格设计 / 逐页制作 / 检查页面 / 交付」，不暴露 DSL / lint / OOXML 等内部实现。
- lint 报错必须修源头（改 DSL / 补内容），禁止靠拉伸间距、放大字号、加装饰色块硬撑版面。
- 每页只允许一个视觉主角；区域数 ≤ 4。

## 独立性与原创性声明

- FreePPT 是**独立、原创**的 skill：全部 DSL 设计、布局算法、lint 规则、模板、矢量图形、动画注入与检索下载代码均为本工程自有实现，目录内自包含。
- **版权归属与许可**：作者张三峯（公众号：AI龙卷风），© 2026。代码 MIT、文档与设计资料 CC BY 4.0（见 `LICENSE`、`LICENSE-DOCS`），再分发须保留作者署名与公众号信息。第三方公开设计令牌的数值借鉴已单独标注来源，见 `references/design-token-sources.md`；这不改变本工程原创部分的版权归属。
- **不引用、不依赖、不修改任何其他产品或厂商的 skill**；工程内不存在对外部 skill 的 import 或调用。
- 仅依赖通用开源基础库（见 `requirements.txt`）：python-pptx、Pillow、lxml，以及 Python 标准库；这些是公开通用工具，不构成对任何 PPT 产品的依赖。
- 架构与模块职责见 `references/architecture.md`。
