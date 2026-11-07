# FreePPT｜把零散想法做成专业、可编辑的 PPT

## 版权说明

**作者：张三峯** ｜ 公众号：**AI龙卷风**

© 2026 张三峯。**代码 MIT 许可，文档与设计资料 CC BY 4.0 许可**（见 `LICENSE`、`LICENSE-DOCS`）；再分发须保留作者署名与公众号信息。

> 面向用户的产品介绍 · 状态更新于 2026-11-08 · 英文版见 `README.en.md`
> 独立原创，不引用、不依赖、不修改任何其他产品的技能。

## 它是什么

FreePPT 是一套 PPT 生成技能。你给它一个主题、一份材料，或者几行零散要点，它交回一份**原生可编辑**的 .pptx 文件——文字、图表、形状在 PowerPoint 里都能直接改，不是一页页截图拼起来的图片。

它同时解决两件事：**内容**从零散要点变成结构完整的专业表述，**版式**从头到尾符合数值化的设计规范。

工作流有两条，按内容性质选：结构稳定的周报、经营分析走固定母版；读书笔记、品牌叙事、演讲稿走**逐页创作编排**——引擎读内容语义后逐页选构图（跨页编辑式、整页引文、错位三栏、左右对开、页边批注、阶梯列表、不等网格……），并可从你给的图书封面或品牌主视觉里提取配色和视觉母题。**同一份笔记不会九页长一个样**，这件事由程序硬拦，不靠提示词自觉。

## 它凭什么稳

制作顺序固定为五步：**规划 → 写结构化内容 → 计算版面 → 规则校验 → 生成文件**。

校验不通过时，程序直接拦住，文件根本不会生成；要改就回到内容层改数据，改完重新检查。安全区、最小字号、间距档位、配色、密度、文字溢出、图片来源标注等要求都写成了数值条件，由程序逐条判定，不靠临场看图审美。所以质量是「工程保证的下限」，不是「碰运气的上限」。

创作编排不是把校验关掉换自由：它换的是规则集。自由画布改用几何、溢出、文字对比度、配色自洽做闸门，同时新增两条硬错误——**相邻页构图重复**、**全篇构图种类不足**。换句话说，「所有页面都套同一个模板」现在是会被 `lint` 拦下的缺陷。

## 功能一览

| 板块 | 内容 |
|---|---|
| **视觉主题（16 套）** | 改一个 `theme` 字段即整体换肤，配色、中英文字体配对、圆角、行距、图表色一次性切换。<br>· 通用 6 套：咨询商务（默认）、杂志编辑、深色科技、瑞士极简、新中式、通用不锁色<br>· 企业风格 6 套：麦肯锡、BCG、普华永道、罗兰贝格、微软、苹果<br>· 数据驱动 4 套：Stripe、Vercel、WIRED、IBM（取自公开设计令牌，色值可追溯） |
| **固定报告场景（8 类）** | 周报、月报、季度报、年度报、述职、竞聘、复盘、经营分析。每类自带咨询式叙事结构与 6–10 页页面规划，并按报告性质自动匹配主题 |
| **内容智能创作辅助** | 零散要点自动归位：指标进 KPI 页、趋势进图表页、问题进诊断页、计划进举措页。随后按创作手册做扩写、逻辑梳理与专业润色（结论式标题、金字塔/MECE、数据→结论、套话黑名单、禁止编造数据）。成品再经内容把关 + 版面校验双关 |
| **逐页创作编排（12 种构图原型）** | 内容语义决定每页版式：封面编辑式、章节页、跨页编辑式、整页引文、错位三栏、左右对开、页边批注、阶梯列表、数字焦点、不等网格、时间轴、封底呼应。相邻页不重样，密度有疏密节奏，文字高度按实际换行量计算 |
| **参考图派生视觉语言** | 给一张图书封面/品牌主视觉，自动提取主色（避开大面积纸底色）、浅色纸底、主色块位置，派生全套语义色、字体气质与贯穿全篇的母题（色带/竖线/圆弧/圆点/网格）；封面 SHA256 与提取色板写进台账，可复现、可追溯 |
| **母版版式（10 套）** | 封面、目录、章节、三卡片、KPI 行、图表洞察、图文、流程、时间轴、结尾；填数据即出片，适合结构稳定的企业报告 |
| **自由画布 DSL** | `composition: freeform`：节点绝对定位、色块出血、竖线、旋转、半透明、垂直对齐；不再强制每页「标题＋横线＋页脚」 |
| **自动配图（三通道）** | ① 程序化矢量：10 种图形（增长、仪表盘、网络、漏斗、循环、安全、矩阵、组织树、地图航线、韦恩图），同时输出 PNG 与可编辑 SVG，无水印、无授权问题<br>② 授权网图：关键词检索 → 下载到本地 → 生成来源台账 → 所在页强制标注来源<br>③ 生成式图片：需显式选用，仅在前两条无法覆盖写实场景时使用 |
| **动效** | 页面淡入转场、元素淡入与上浮入场，写入文件后仍是普通可编辑形状 |
| **离线验收** | 没有 Office 也能导出全页 PNG，复核版面；CI 另装 LibreOffice 做 PDF/PNG 渲染回归 |
| **纯 CLI 出片** | `cli.py make` 一句话/零散要点 → 骨架 → 内容把关 → lint → .pptx，**全程不调用大模型、不联网、不编造数据**；8 类报告均可直接出片 |
| **编辑已有 pptx** | `inspect` 导出形状/文本/坐标结构，`retext` 替换文字并保留原 run 字体；`patch` 改 DSL 单节点后自动重跑 lint |
| **中文排版** | 避头尾禁则（标点悬挂）、破折号/省略号不拆行、可选中英混排窄空格、声明式字体回退栈；`CJK_KINSHOKU` 写入 lint |
| **可量化基准** | `tools/benchmark.py` 输出版面错误数、可编辑形状占比、文字溢出率、离线就绪与耗时；方法见 `docs/BENCHMARK.md` |
| **一键安装** | `install.sh` 支持 WorkBuddy / Claude Code / Codex CLI / Cursor / DSH（DeepSeek Harness），用户级或项目级，带幂等引导块、自检与卸载备份 |

## 关于 AI 标识

**默认成品不带 AI 标识，且不需要删除任何东西。** 默认配图走程序化矢量与授权网图，这两类不是生成合成内容，本身就不带标识。

FreePPT 不提供「去除 / 擦除已添加标识」的功能。按《人工智能生成合成内容标识办法》第十条，已添加的生成合成内容标识不得恶意删除、篡改、伪造、隐匿，为他人实施上述行为提供工具或服务同样被禁止。若确需无显式标识的生成图，合规路径是由生成服务方依第九条在用户协议明确标识义务与使用责任、依法留存日志不少于六个月后**直接提供未添加显式标识的原件**；FreePPT 只引用该原件，不参与生成或去标。文件元数据中的隐式标识不得移除，对外发布时仍应主动声明并添加显式标识。

以上为工程侧对条文的理解，不构成法律意见；FreePPT 属于本地生成工具，不代替用户或服务方履行协议、留痕与声明义务。

## 怎么用

1. 说明主题、受众、页数和风格，或直接丢一段零散要点 / 一份读书笔记；要贴合某本书的视觉气质，把封面图一起给。
2. FreePPT 规划结构、梳理并撰写内容、逐页编排；规则校验没过就回到内容层修正。
3. 校验通过后生成 .pptx 并交付，可附带全页 PNG 供复核。

命令行（全程离线、无需大模型）：

```bash
# 创作类：笔记 + 参考封面 → 逐页编排
python3 engine/cli.py compose notes.json --cover cover.jpg --out deck.json --ledger style.json
python3 engine/cli.py lint  deck.json
python3 engine/cli.py build deck.json out.pptx

# 报告类：纯 CLI，无大模型、无联网
python3 engine/cli.py make "本周完成 3 项交付；满意度提升到 92%" --type weekly --out weekly.pptx

# 改稿与已有文件
python3 engine/cli.py patch deck.json --set "slides.0.data.title=新标题" --build revised.pptx
python3 engine/cli.py inspect old.pptx --out structure.json
python3 engine/cli.py retext old.pptx --map edits.json --out revised.pptx

# 一键安装到五种 AI 宿主 / 全量自检
./install.sh --host all --scope user
bash tools/check_all.sh
python3 tools/benchmark.py --out bench.json
```

进阶用法：指定报告类型（如经营分析）可一次拿到完整章节结构；指定主题 id 可整体换肤；工程自带示例 .pptx、`examples/GALLERY.md` 样张索引与 `examples/composition_compare.png` 九页拼版。开源协作见 `CONTRIBUTING.md`，DSL 规范见 `references/dsl-spec.md`，发布清单与宿主路径来源见 `docs/PUBLISHING.md`。

## 实测状态（2026-11-08 本地运行）

- **101 项离线单测全部通过**（主题、网图检索解析、内容创作、设计令牌导入、创作编排与封面派生、开源工具链六组）。
- **8 份示例 deck 规则校验全部零错误**；其中经营分析报告走完「内容把关 → 版面校验 → 编译 → 渲染」全链路，读书笔记走完「封面派生 → 逐页编排 → lint → 编译 → 九页 PNG 验收」全链路。
- 纯 CLI 对 **8 类报告**（含空输入、短输入、文件输入）全部通过内容闸门 + lint 并产出可打开 pptx；`bash tools/check_all.sh` 四段全绿。
- 自测基准：平均可编辑形状占比 **0.9647**、版面硬错误 **0**、文字溢出率 **0.0**、核心管线联网调用静态扫描 **0 处**；数字与口径见 `docs/BENCHMARK.md`。
- 16 套主题、8 类报告、10 套母版、12 种构图原型、10 组矢量资产（PNG + SVG）均已就位；14 套非默认主题逐套完成换肤校验与视觉验收。
- 创作编排示例同一份笔记产出 9 页 9 种构图、4 档密度节奏，派生主题墨色/纸底对比度 16.2:1。

## 需要如实说明的边界

- 6 套企业风格主题采用行业通用近似配色；4 套数据驱动主题取自公开提取的设计令牌。两者**都不是品牌官方视觉规范**，文件里也不含任何商标或 Logo。
- 内容的语言扩写由执行 FreePPT 的 AI 助手按创作手册完成；工程本身提供结构规划、要点路由和质量把关，**没有内置独立的大模型 API 客户端**。
- 动画与转场已写入文件并通过 XML 解析验证，但**尚未在 Microsoft PowerPoint 里实测播放**。
- 网图检索的联网部分在本环境不可达；检索结果的解析逻辑已用真实数据样本离线验证，下载 → 校验 → 留痕链路已用本地服务端到端验证。
- 已入档的 Linear、Notion 令牌**尚未注册为主题**：两者内容页为深色系统，当前骨架是「深色封面 + 浅色内容页」，强行套用会让文字不可读。
- 编辑已有 .pptx **只支持结构导出与保留格式的文字替换**；任意 pptx 反向解析成 FreePPT DSL 的完整往返尚未实现，见 `references/edit-existing.md`。渐变填充、受控阴影、12 列网格、图表信息图化仍在开发清单里。
- LibreOffice 渲染回归本机因未装 `soffice` 而 **skipped（跳过不等于通过）**；GitHub Actions 会安装依赖后强制断言 `status=ok`，像素级基线 diff 尚未实现。
- 五个宿主的安装路径来自官方文档/官方仓库，其中仅 WorkBuddy 在本机实测安装过；Claude Code / Codex CLI / Cursor / DSH 的路径属「有官方依据、未本机实测」，见 `docs/PUBLISHING.md`。
- 创作编排是**确定性规则驱动**，不是端到端生成式设计模型：构图原型为 12 种有限库，由 seed 与内容语义组合变化；参考图只提取色值与构图特征，不复制封面图像资产，也不识别封面文字。要无限自由的版式仍需手写 freeform DSL。

## 独立原创与依赖

FreePPT 的布局算法、校验规则、母版模板、矢量图形、动画注入与检索下载代码全部由本工程自行实现。目录内自包含，仅依赖三个通用开源库（python-pptx、Pillow、lxml）与 Python 标准库；核心生成流程不联网。

设计数据借鉴说明：4 套数据驱动主题参考 VoltAgent/awesome-design-md（MIT）收录的公开 CSS 设计令牌，**只取数值**（色值、圆角尺度），不取原文、代码、Logo 或图像资产；每个色值都能通过 `references/imported/theme_mapping.json` → `design_tokens.json` → 源文件 SHA256 追溯。来源、许可与映射决策见 `references/design-token-sources.md`。运行时不依赖该仓库。

**版权与许可**：本工程原创部分归作者张三峯（公众号：AI龙卷风）所有，**代码 MIT、文档与设计资料 CC BY 4.0**（见 `LICENSE`、`LICENSE-DOCS`）；再分发须保留作者署名与公众号信息。上述第三方数据仅借鉴公开数值，其权利仍属各自权利人；这不改变本工程原创部分的版权归属。

---

## 附：维护者核查依据

以下为上述数字与结论的核查来源，供刷新介绍时复核，不是面向终端用户的说明。

### 运行记录

主题、报告、模板、原型、资产数量，101 项单测与 8 份 deck 校验结果，来自 2026-11-08 在本工程目录本地运行 `tests/test_*.py`、`engine/cli.py lint`、`tools/benchmark.py` 及主题/报告/原型注册表的输出；该运行记录无出版载体，故以运行说明标注。复现命令：

```bash
for t in tests/test_*.py; do python3 "$t"; done
# web_manifest.json 是配图素材清单，不是 deck，需排除
for f in examples/*.json; do
  case "$(basename "$f")" in
    web_manifest.json|notes_*.json|style_*.json|edits_*.json|structure_*.json) continue;;
  esac
  python3 engine/cli.py lint "$f"
done
bash tools/check_all.sh
python3 tools/benchmark.py --out bench.json
python3 -c "from engine.themes import THEMES; from engine.reports import list_types; from engine.art_direction import ARCHETYPES; print(len(THEMES), len(list_types()), len(ARCHETYPES))"
python3 -m unittest discover -s tests -q
```

### 工程文件（MLA 格式）

张三峯. "SKILL.md." *FreePPT*, version 20261108.3, 2026, ppt-skill/SKILL.md.

张三峯. "architecture.md." *FreePPT*, 2026, ppt-skill/references/architecture.md.

张三峯. "themes.py." *FreePPT*, 2026, ppt-skill/engine/themes.py.

张三峯. "reports.py." *FreePPT*, 2026, ppt-skill/engine/reports.py.

张三峯. "content_ai.py." *FreePPT*, 2026, ppt-skill/engine/content_ai.py.

张三峯. "art_direction.py." *FreePPT*, 2026, ppt-skill/engine/art_direction.py.

张三峯. "cover_style.py." *FreePPT*, 2026, ppt-skill/engine/cover_style.py.

张三峯. "test_art_direction.py." *FreePPT*, 2026, ppt-skill/tests/test_art_direction.py.

张三峯. "brief_fill.py." *FreePPT*, 2026, ppt-skill/engine/brief_fill.py.

张三峯. "typography.py." *FreePPT*, 2026, ppt-skill/engine/typography.py.

张三峯. "pptx_edit.py." *FreePPT*, 2026, ppt-skill/engine/pptx_edit.py.

张三峯. "deck_patch.py." *FreePPT*, 2026, ppt-skill/engine/deck_patch.py.

张三峯. "benchmark.py." *FreePPT*, 2026, ppt-skill/tools/benchmark.py.

张三峯. "render_check.py." *FreePPT*, 2026, ppt-skill/tools/render_check.py.

张三峯. "install.sh." *FreePPT*, 2026, ppt-skill/install.sh.

张三峯. "test_open_source_tooling.py." *FreePPT*, 2026, ppt-skill/tests/test_open_source_tooling.py.

张三峯. "content-playbook.md." *FreePPT*, 2026, ppt-skill/references/content-playbook.md.

张三峯. "design-token-sources.md." *FreePPT*, 2026, ppt-skill/references/design-token-sources.md.

张三峯. "requirements.txt." *FreePPT*, 2026, ppt-skill/requirements.txt.

### 外部来源

VoltAgent. "Awesome DESIGN.md." *GitHub*, 2026, github.com/VoltAgent/awesome-design-md. Accessed 8 Nov. 2026.

国家互联网信息办公室, et al. "人工智能生成合成内容标识办法." *中国网信网*, 14 Mar. 2025, www.cac.gov.cn/2025-03/14/c_1743654684782215.htm. Accessed 8 Nov. 2026.

### 本机安装与更新

用户级 skill 安装位置：`~/.workbuddy/skills/freeppt/`（目录名与 `SKILL.md` 的 `name: freeppt` 一致）。开发源码在本工作区 `ppt-skill/`，两者是**副本关系**，改完源码需同步一次才生效。

```bash
# 首次安装 / 后续「更新为最新」（--delete 仅作用于 freeppt 目录，不动其他 skill）
rsync -a --delete \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.DS_Store' \
  /Users/lico/WorkBuddy/2026-11-03-18-38-56/ppt-skill/ \
  /Users/lico/.workbuddy/skills/freeppt/

# 安装后自检（在安装目录内执行）
cd /Users/lico/.workbuddy/skills/freeppt
for t in tests/test_*.py; do python3 "$t"; done
python3 engine/cli.py lint examples/demo.json
```

版本号写在 `SKILL.md` frontmatter 的 `version`，格式为 `YYYYMMDD`；每次同步最新版时一并更新。
