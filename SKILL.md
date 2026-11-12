---
name: freeppt
display_name: "FreePPT"
display_name_en: "FreePPT"
description: "FreePPT：创建专业 PowerPoint。输入主题/大纲/数据、零散要点或读书笔记（可附参考封面图），产出逐页创作编排、原生可编辑的 .pptx；内置 17 种构图原型（含原生图表/表格页与玻璃卡/图标卡/编号卡）、渐变与毛玻璃 alpha、原生形状图标库、演讲者备注自动生成、封面图配色派生、16 套视觉主题、8 类企业固定报告、长 deck 分章护栏、版式账本零重复硬闸（layout_id 全局唯一/相邻不同族/同族页码间隔）、研究来源台账与内容密度校验、纯 CLI 出片与已有 pptx 文字改稿。触发词：FreePPT、freeppt、做PPT、生成PPT、改PPT、读书笔记、幻灯片、pptx。"
description_zh: "按「规划 → 生成 DSL → 布局 → lint 校验 → 编译渲染」五阶段产出原生可编辑 PPTX；读书笔记等非报告类内容走逐页创作编排，可从封面图派生专属配色与母题，避免所有页面套同一模板。"
description_en: "Create native editable PPTX decks through a five-stage pipeline. Creative content such as reading notes is composed page by page with 17 layout archetypes (including native chart/table pages and glass/icon/numbered cards), gradient and frosted-glass alpha fills, a native-shape icon library, generated speaker notes, chapter-based long-deck guardrails, a research-source ledger and a content-density check, while structured reports use 16 themes, 10 masters and 8 templates."
category: document
version: "20261112.6"
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

**内容厚度**（数字来自 12 份豆包样本实测）

| # | 标准 | 实测参照 |
|---|---|---|
| 7 | 内容要够厚 | 页均可见 144–360 字；我方《英伟达之道》91 页已达 294.6 字 |
| 8 | 允许峰值 | 单页峰值 500–778 字是正常的，不要为了「淡雅」砍内容 |
| 9 | 有真论点论据 | 数据、案例、引文、来源齐备，不是口号拼接 |
| 10 | 时效数字联网核实 | `research:true` 的页必须有 `sources` 台账 |
| 11 | 演讲者备注全覆盖 | 目标 ≈100%（12 份样本 11 份满分）。**我方 91 页实测 0/91，最大未补缺口** |
| 12 | 备注分档位 | 随笔 25–60 / 常规 100–160 / 研究 200+，不能一刀切 |

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
| 27 | 产物侧也要查 | 手写脚本生成的 pptx 一样跑 `audit-pptx` |

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

**为什么几何判据必须听坐标**：实测把 12 页同构页的 `archetype` 改成 12 个不同名字、几何一字不动，旧闸门照样 `ok=True` 放行。自报标签是靠不住的，所以兜底判据只读坐标。同一份实测也校准了阈值：正常产物最大同骨架组是 4 页，翻车样本是 11/8/8/7/7 页，所以取 5。仪式页（封面/章节/封底）豁免——一本书 11 个章节页长得一样是对的。

**回归锚点**：`tests/test_design_brief_gate.py::TestRealWorldTemplateDeckRejected` 用一本真实的 122 页同构 deck 当样本，断言它必然被拒。以后谁把闸门改松，这条测试会红，而不是等成品拿到手才发现。

**自己验，别听汇报**——跑这一条就够：

```bash
python3 engine/cli.py selfcheck
```

它不读文档、不看配置，而是**当场造样本跑一遍**：生成一份 122 页同构、每页只有版式名没有设计简报的 deck，交给 lint 判，同时生成一份正常产物做对照，再测「改名能否骗过判据」「占位话术是否算没填」「不传简报是否失败」，最后**真的用 python-pptx 手写一份 12 页同构 pptx 存到磁盘**，再让 `audit-pptx` 判它——端到端跑通，不是模拟。预期输出 `8/8 项通过 —— 闸门确实生效`；任何一道闸门被改松，它会当场报 `[FAIL]` 并以退出码 1 结束。

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
- `NOTES_COVERAGE`：开启讲稿覆盖的页缺演讲者备注 → 错误；`NOTES_THIN`：讲稿不足 40 字 → 警告（随笔/语录类 deck 可用短注档位，例外条件见 `docs/DESIGN_GRAMMAR.md` §9）；
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
  --cover examples/assets/book_cover_demo.png \
  --out examples/deck_notes_composed.json --ledger examples/style_notes_derived.json
python3 engine/cli.py lint  examples/deck_notes_composed.json
python3 engine/cli.py build examples/deck_notes_composed.json out.pptx
python3 engine/debug_render.py examples/deck_notes_composed.json /tmp/preview
```

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
- **演讲者备注**：compose 确定性生成每页讲稿（只重组页面已有文字，不编造数据），编译为真实 notesSlide；`NOTES_COVERAGE`/`NOTES_THIN` 闸门管覆盖与厚度，`speaker_notes:false` 可关。
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
