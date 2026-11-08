---
name: freeppt
display_name: "FreePPT"
display_name_en: "FreePPT"
description: "FreePPT：创建专业 PowerPoint。输入主题/大纲/数据、零散要点或读书笔记（可附参考封面图），产出逐页创作编排、原生可编辑的 .pptx；内置 17 种构图原型（含原生图表/表格页与玻璃卡/图标卡/编号卡）、渐变与毛玻璃 alpha、离线原生图标库、演讲者备注自动生成、封面图配色派生、16 套视觉主题、8 类企业固定报告、长 deck 分章护栏、研究来源台账与内容密度校验、纯 CLI 出片与已有 pptx 文字改稿。触发词：FreePPT、freeppt、做PPT、生成PPT、改PPT、读书笔记、幻灯片、pptx。"
description_zh: "按「规划 → 生成 DSL → 布局 → lint 校验 → 编译渲染」五阶段产出原生可编辑 PPTX；读书笔记等非报告类内容走逐页创作编排，可从封面图派生专属配色与母题，避免所有页面套同一模板。"
description_en: "Create native editable PPTX decks through a five-stage pipeline. Creative content such as reading notes is composed page by page with 17 layout archetypes (including native chart/table pages and glass/icon/numbered cards), gradient and frosted-glass alpha fills, an offline native-shape icon library, generated speaker notes, chapter-based long-deck guardrails, a research-source ledger and a content-density check, while structured reports use 16 themes, 10 masters and 8 templates."
category: document
version: "20261108.5"
author: "张三峯"
---

# FreePPT

## 版权说明

**作者：张三峯** ｜ 公众号：**AI龙卷风**

© 2026 张三峯。开源双许可：**代码 MIT**、**文档与设计资料 CC BY 4.0**（见 `LICENSE` / `LICENSE-DOCS`）。他人使用、修改、分发时须保留作者署名与公众号信息。

> 面向用户的产品介绍见 `README.md`（含功能清单、实测状态、合规边界与核查依据）；本文件是 skill 的执行规范。

## 任务路由

| 任务 | 路径 |
|---|---|
| 从零 / 基于材料生成 | 遵循本文件五阶段主干（6 步落地） |
| 读书笔记 / 品牌叙事 / 演讲稿（要版式变化、可附封面图） | 走「创作式编排」：`cli.py compose` → `lint` → `build` |
| 周报 / 月报 / 经营分析等结构稳定报告 | 走 `reports.py` 骨架 + 10 套母版；无宿主可用 `cli.py make` 纯 CLI 出片 |
| 编辑已有 pptx | `cli.py inspect` 导出结构 → `cli.py retext` 改文字；边界见 references/edit-existing.md |
| 单节点局部改稿 | `cli.py patch deck.json --set "path=value" --build out.pptx`（改完仍走 lint） |
| 安装到其他宿主 | `./install.sh --host claude\|codex\|cursor\|dsh\|workbuddy --scope user\|project` |
| 开源协作 / 规范 | `CONTRIBUTING.md`、`references/dsl-spec.md`、`docs/THEME_CONTRIBUTION.md` |

## 开源工具链（纯 CLI，不依赖大模型）

**适用范围**：没有 AI 宿主、CI 环境、内网/离线交付，或只想用命令行出片。以下链路全部离线、确定性、不编造数据。

```bash
# 一句话/零散要点 → 8 类报告任一 → lint → pptx（内容闸门 + 版面闸门）
python3 engine/cli.py make "本周完成 3 项交付；满意度提升到 92%" \
  --type weekly --out out.pptx --out-deck out.json

# 已有 pptx：结构导出 + 保留 run 字体的文字替换
python3 engine/cli.py inspect old.pptx --out structure.json
python3 engine/cli.py retext old.pptx --map edits.json --out revised.pptx

# 改一个节点就重编译（仍受 lint 闸门约束）
python3 engine/cli.py patch out.json --set "slides.0.data.title=新结论" --build revised.pptx

# 全量闸门 / 可量化基准 / 五宿主一键安装
bash tools/check_all.sh
python3 tools/benchmark.py --out bench.json
./install.sh --host all --scope user
```

| 模块 | 职责 |
|---|---|
| `engine/brief_fill.py` | brief → 报告骨架填充；未提供的字段写明确的空态说明，图表数值只取自输入，零值代表未提供 |
| `engine/typography.py` | 避头尾禁则、标点悬挂、`——/……` 不拆行、可选中英混排窄空格、声明式字体回退栈；`CJK_KINSHOKU` 进 lint |
| `engine/pptx_edit.py` | 已有 pptx 的结构导出与保留格式的文字替换（**不做 DSL 往返**） |
| `engine/deck_patch.py` | 按点号路径改 DSL 单节点 |
| `tools/benchmark.py` | 版面错误数 / 可编辑形状占比 / 溢出率 / 离线就绪 / 耗时；只测本仓库，不编造竞品数据 |
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

## 创作式编排（非固定模板）

**适用场景**：读书笔记、书评、品牌故事、演讲稿、课程讲义等需要视觉变化的内容。固定母版（10 套）仍保留给周报/月报/经营分析这类结构稳定的报告。

老问题：`{template,data}` 展开后，每一页都被 `layout_slide` 强制套上「标题 + 横线 + 内容区 + 页脚」，而且 lint 的 SAFE_AREA / DENSITY / GAP 规则会把自由构图判成错误，于是多页内容看起来一模一样。现在这条链路被替换：

| 层 | 新机制 |
|---|---|
| 画布 | `composition: freeform`：每个节点自带 `rect:[x,y,w,h]` 绝对定位，子矩形以父矩形左上角为局部原点；不再自动加标题横线与页脚带 |
| 构图 | `engine/art_direction.py` 17 种原型（封面编辑式 / 章节页 / 跨页编辑式 / 整页引文 / 错位三栏 / 左右对开 / 页边批注 / 阶梯列表 / 数字焦点 / 不等网格 / 时间轴 / 封底呼应 / 原生图表叙事 / 原生表格看板，以及卡片体系的玻璃卡 `glass-panel` / 图标网格 `icon-grid` / 编号卡 `numbered-cards`），按内容语义候选 + 确定性 seed 逐页分配，相邻页不重样；页面携带 `chart`/`table` 数据时自动路由到对应数据原型，编译为原生可编辑图表与表格 |
| 参考图 | `engine/cover_style.py` 从图书封面/品牌主视觉提取主色（按彩度×占比×中间调打分，避开大面积纸底色）、浅色纸底、主色块位置 → 派生调色板、字体气质与贯穿全篇的母题（band / vertical-rule / arc / dots / grid） |
| 几何 | 文本节点高度由自身分词换行实测得出，长文自动缩字号；栏数/格数随实际内容块数变化，不填空卡片 |
| 色彩一致性 | 派生主题由 `themes.build_derived()` 注册，PALETTE 规则仍强制所有色落在派生调色板内 |

**长 deck 分章护栏（防止 88 页式重复事故的前置闸门）**：

- 单个扁平文件的容量上限为 `CHAPTER_PAGE_CAP = 24` 页：`compose` 在做任何几何工作前先检查，超过上限且没有 `kind:"chapter"` 章节页时直接 `COMPOSE BLOCKED` 退出，报出修复方式（分章或显式 `allow_long_deck:true`），把失败挡在规划阶段而不是 build 时抛几十条 lint 错误。
- 分章后多样性预算按章节重置：同一原型可在不同章节合法复用，`LAYOUT_VARIETY` 按每章内容页独立计算（章节页本身不计入预算）；`LAYOUT_REPETITION` 相邻页硬错误保持不变。
- 显式绕过留痕：`allow_long_deck:true` 会在 DSL 写入 `long_deck_forced` 并产生 `LONG_DECK_FORCED` 警告；build 时仍需 `--force`，且编译器在产物内写入 `FreePPTForcedBuildMarker` 文本框与文档 subject，绕过行为在文件本身可见。

**研究来源台账（引擎离线，只做校验）**：

- notes 页面可声明 `research:true`（或研究问题字符串）与 `sources:[{title,url,publisher}]`；compose 透传到 slide 级。
- lint 规则 `RESEARCH_LEDGER`：声明了 research 的页必须带来源台账（含 title 且至少有 url 或 publisher），否则阻断 build。引擎本身不联网、不代做研究，研究动作仍是宿主 agent 在 Step 2 的职责，这条规则把该职责变成可判定的交付物。

**视觉设计系统（对标商业生成式 PPT 的设计语言，仍纯离线、原生可编辑）**：

- **渐变填充**：节点或页面可写 `gradient:{stops:[{color,pos,opacity?}],angle}`，编译为真实 OOXML `a:gradFill`（角度单位 1/60000 度）；页面写 `gradient:"theme"` 时解析为当前主题的标志性渐变。`magazine`/`tech`/`oriental` 三主题内置调色板内安全的背景渐变，其余主题默认平面（零回归）。
- **三类透明度（毛玻璃基础）**：形状填充 `opacity`、文字 run `opacity`、描边 `border_opacity`，统一注入 OOXML `a:alpha`。玻璃卡典型值为白填充 `opacity:8` + 白描边 `border_opacity:20`。
- **离线原生图标库**（`engine/icons.py`）：14 个图标用 PowerPoint 原生形状在 100×100 逻辑网格拼合，另带 27 个语义别名（`goal`→target、`risk`→shield 等）；DSL 节点 `{"t":"icon","name":"gear"}`，主题 accent 单色驱动，无位图/SVG 素材、无授权面；`ICON_NAME` 校验图标名，布局保证图标恒为正方形不被拉伸。
- **卡片体系（opt-in）**：`compose --card-system`（或 `card_system:true`）才把玻璃卡/图标网格/编号卡三个原型纳入编排候选，默认关闭以保持历史产物逐字节不变。深色卡片页在该模式下自动套用主题渐变背景。
- 以上原语贯穿 layout / lint / compiler / debug_render 全链路；调试接触表（`debug_render.py`）支持渐变近似、alpha 混合与图标/圆角绘制。

**演讲者备注（speaker notes）**：

- compose 默认对每页生成**离线、确定性**的讲稿（`_speaker_notes`）：只把该页已有的标题/导语/要点/引文重组为口语化串场，不编造数据；页面自带 `notes` 字段时原样优先。讲稿编译为真实 `notesSlide`，不出现在画面上。
- lint：开启讲稿覆盖时（composed deck 默认），缺讲稿触发阻断规则 `NOTES_COVERAGE`；讲稿不足 40 字给 `NOTES_THIN` 提示（非阻断）。可用 `speaker_notes:false` 关闭生成。
- 内容密度：composed 内容页可见文字少于 60 字时给 `CONTENT_DENSITY` 警告，引导结合研究台账向页均 150–250 字靠拢；封面/章节/封底/引文/图表/表格原型豁免，警告不阻断构建。

**新增硬闸门（阶段 4，不通过就回到 DSL 返工）**：

- `LAYOUT_REPETITION`：相邻两页构图原型相同 → 错误；
- `LAYOUT_VARIETY`：按章节计算，每章内容页原型数少于 `min(章页数, max(3, ⌈章页数/2⌉))` → 错误；
- `RESEARCH_LEDGER`：声明 research 的页缺来源台账 → 错误；
- `TABLE_SHAPE`：原生表格缺 headers/rows 或行列数不一致 → 错误；
- `LONG_DECK_FORCED`：长 deck 护栏被显式绕过 → 警告（非阻断）；
- `DENSITY_FLAT`：全篇密度一致 → 警告；
- `NOTES_COVERAGE`：开启讲稿覆盖的页缺演讲者备注 → 错误；`NOTES_THIN`：讲稿不足 40 字 → 警告；
- `ICON_NAME`：icon 节点引用了图标库不存在的名字 → 错误；
- `CONTENT_DENSITY`：composed 内容页可见文字过薄（< 60 字）→ 警告（非阻断，特殊/数据原型豁免）；
- `FREEFORM_RECT` / `OUT_OF_CANVAS` / `TEXT_OVERFLOW` / `RICHCARD_OVERFLOW` / `CONTRAST` / `PALETTE` / `FONT_SIZE`：几何、溢出、可读性、配色照旧拦；
- 自由画布**不受**旧母版教条约束（安全区、固定间距、底部留白、32–40px 标题），但仍可用 `on` 字段声明文字底色以做 WCAG 对比度校验。

**从笔记到成片**（五阶段顺序不变，compose 属于阶段 1–2，编译仍在阶段 5）：

```bash
python3 engine/cli.py compose examples/notes_renqing_mianzi.json \
  --cover examples/assets/book_cover_demo.png \
  --out examples/deck_notes_composed.json --ledger examples/style_notes_derived.json
python3 engine/cli.py lint  examples/deck_notes_composed.json
python3 engine/cli.py build examples/deck_notes_composed.json out.pptx
python3 engine/debug_render.py examples/deck_notes_composed.json /tmp/preview
```

也可单独派生主题：`python3 engine/cli.py style cover.jpg --book "书名" --out style.json`。

**可复现**：同一份 notes + 同一张封面 → 同一份 DSL（seed = 书名 + 内容 + 封面 SHA256）；`style.json` 台账记录封面 SHA256、提取色板、主色块位置与对比度。全程离线，不调用大模型、不联网。

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
- **自由画布 + 创作式编排**：`composition:freeform` 绝对定位、节点 `rect/rotate/opacity/border_opacity/valign/on/decor/bleed`、竖向分隔线；17 种逐页构图原型（含玻璃卡/图标网格/编号卡三个 opt-in 卡片原型）、封面图派生配色与母题、版式重复硬拦截、长 deck 分章护栏，见 engine/art_direction.py 与 engine/cover_style.py。
- **渐变与毛玻璃视觉系统**：节点/页面 `gradient`（含 `"theme"` 哨兵）编译为真实 OOXML `gradFill`；形状/文字/描边三类 alpha 通道统一注入，可做毛玻璃卡；深色卡片页自动套主题渐变。
- **演讲者备注**：compose 离线确定性生成每页讲稿（只重组页面已有文字，不编造数据），编译为真实 notesSlide；`NOTES_COVERAGE`/`NOTES_THIN` 闸门管覆盖与厚度，`speaker_notes:false` 可关。
- **原生数据原语**：页面携带 `chart`（kind/categories/series）或 `table`（headers/rows）数据时，compose 自动路由到 chart-story / table-board 原型，编译为 PowerPoint 原生可编辑图表与表格（非贴图、非文本框伪装）；inspect 可回读图表/表格结构。
- **动画与转场**：slide 级 `transition:"fade"` 与 `anims`（fade / fly-up，按 `_name` 定位），由 engine/animator.py 注入 OOXML（python-pptx 本身不支持）。
- **内容质量闸门**：`CONTENT_DENSITY` 警告薄内容页（< 60 字，引导向页均 150–250 字靠拢）、`RESEARCH_LEDGER` 拦截有研究标记无来源台账的页、`ICON_NAME` 拦截非法图标名。
- 离线验收：`python3 engine/debug_render.py deck.json outdir` 出全页 PNG（接触表支持渐变近似、alpha 混合与图标/圆角绘制）。

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
- **Step 2 收集素材（阶段 1）**：提取上传材料；涉时效数字/陌生术语 → 联网核实并记录 Source。需要外部研究的页在 notes 标 `research:true` 并附 `sources:[{title,url,publisher}]` 台账；引擎离线不代研究，`RESEARCH_LEDGER` 闸门会拦截有 research 标记却无来源的页。
- **Step 3 风格路由（阶段 1）**：读对应 scenario（如 references/scenarios/consulting.md）+ design-principle.md，产出每页结构。
- **Step 4 逐页写 DSL（阶段 2）**：每页一个 JSON，结构见 references/dsl.md。
- **Step 5 布局 + lint（阶段 3、4）**：`python3 engine/cli.py lint deck.json`（内部先布局后校验）；按 diagnostics 回 Step 4 修 DSL 至 `ok:true`。
- **Step 6 编译交付（阶段 5）**：`python3 engine/cli.py build deck.json out.pptx`；可选 `debug_render.py` 出全页 PNG 做离线视觉复核。

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
