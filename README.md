# FreePPT

[![CI](https://github.com/zhangfree866-commits/freeppt/actions/workflows/ci.yml/badge.svg)](https://github.com/zhangfree866-commits/freeppt/actions/workflows/ci.yml)

## 版权与许可

作者：张三峯，公众号：AI龙卷风。© 2026 张三峯。代码采用 MIT 许可，文档与设计资料采用 CC BY 4.0 许可，见 `LICENSE`、`LICENSE-DOCS`。再分发请保留作者署名与公众号信息。英文版见 [README.en.md](README.en.md)。

## 它能做什么

用户给一个主题、一份材料或几行零散要点，FreePPT 输出一份 .pptx。文件里的文字、图表和形状都是 PowerPoint 原生对象，可以直接修改；引擎不把页面压成图片。

FreePPT 按内容性质选工作流：

- 周报、经营分析等结构固定的报告走 10 套母版。
- 读书笔记、品牌叙事、演讲稿走逐页创作编排。引擎按内容语义和 seed 从 12 种构图原型里给每页选版式，也可以从用户提供的封面图提取配色与母题。`lint` 把「相邻页构图重复」和「全篇构图种类不足」判为硬错误。

## 五阶段

`规划 → 生成 DSL → 布局 → lint 校验 → 编译渲染`

`cli.py build` 在校验不通过时退出，不生成文件。用户回到 DSL 改数据，再重新校验。安全区、最小字号、间距档位、配色、密度、文字溢出、配图来源标注都写成了数值条件，由 `engine/lint.py` 逐条判定。自由画布（`composition: freeform`）换用几何、溢出、文字对比度、配色自洽等规则，两条反重复规则仍然生效。校验触发的返工发生在数据层，不是渲染后修图。

## 功能

| 模块 | 说明 |
|---|---|
| 视觉主题（16 套） | 修改 `theme` 字段可整体切换配色、中英文字体配对、圆角、行距与图表色。通用 6 套（咨询商务为默认、杂志编辑、深色科技、瑞士极简、新中式、通用不锁色）；企业风格 6 套（麦肯锡、BCG、普华永道、罗兰贝格、微软、苹果）；数据驱动 4 套（Stripe、Vercel、WIRED、IBM，取自公开设计令牌，色值可追溯）。 |
| 报告场景（8 类） | 周报、月报、季度报、年度报、述职、竞聘、复盘、经营分析。每类自带咨询式叙事结构与 6–10 页页面规划，并按报告性质匹配主题。 |
| 内容辅助 | 引擎把零散要点按类型路由到 KPI、趋势、诊断、举措等页面。扩写与润色由执行 FreePPT 的宿主助手按 `references/content-playbook.md` 完成；工程提供结论式标题、MECE、数据到结论、套话黑名单、禁止编造数据等约束，并对成品做内容把关与版面校验。 |
| 逐页创作编排 | 12 种构图原型：封面编辑式、章节页、跨页编辑式、整页引文、错位三栏、左右对开、页边批注、阶梯列表、数字焦点、不等网格、时间轴、封底呼应。引擎按实际换行量计算文字高度，并控制相邻页不重样与密度节奏。 |
| 参考图派生 | 用户给图书封面或品牌主视觉，引擎按彩度 × 占比 × 中间调打分提取主色（避开大面积纸底色）、浅色纸底与色块位置，派生语义色、字体气质和贯穿全篇的母题（色带、竖线、圆弧、圆点、网格）。封面 SHA256 与提取色板写入台账。 |
| 母版（10 套） | 封面、目录、章节、三卡片、KPI 行、图表洞察、图文、流程、时间轴、结尾。用户填数据即可出片。 |
| 自由画布 DSL | `composition: freeform` 支持节点绝对定位、色块出血、竖线、旋转、半透明、垂直对齐。引擎不再强制每页「标题＋横线＋页脚」。 |
| 配图（三通道） | 程序化矢量：10 种图形（增长、仪表盘、网络、漏斗、循环、安全、矩阵、组织树、地图航线、韦恩图），同时输出 PNG 与可编辑 SVG。授权网图：关键词检索 → 下载到本地 → 生成来源台账 → 所在页强制标注来源。生成式图片：需显式选用，仅在前两条无法覆盖写实场景时使用。 |
| 动效 | 页面淡入转场、元素淡入与上浮入场，写入文件后仍是普通可编辑形状。 |
| 离线验收 | 没有 Office 也能导出全页 PNG 复核版面；远端 CI 安装 LibreOffice 做 PDF/PNG 渲染回归。 |
| 纯 CLI 出片 | `cli.py make` 把一句话或零散要点转成骨架、内容把关、lint 和 .pptx，全程不调用大模型、不联网、不编造数据；8 类报告均可直接出片。 |
| 编辑已有 pptx | `inspect` 导出形状、文本与坐标结构；`retext` 替换文字并保留原 run 字体；`patch` 改 DSL 单节点后自动重跑 lint。 |
| 中文排版 | 避头尾禁则与标点悬挂、破折号与省略号不拆行、可选中英混排窄空格、声明式字体回退栈；`CJK_KINSHOKU` 写入 lint。 |
| 可量化基准 | `tools/benchmark.py` 输出版面错误数、可编辑形状占比、文字溢出率、离线就绪与耗时，方法见 `docs/BENCHMARK.md`。 |
| 安装 | `install.sh` 支持 WorkBuddy、Claude Code、Codex CLI、Cursor、DSH（DeepSeek Harness），用户级或项目级，带幂等引导块、自检与卸载备份。 |

## AI 标识与合规

FreePPT 的默认配图是程序化矢量图和带来源台账的授权网图。这两类素材不是生成合成内容，本身不带标识，所以默认成品没有需要移除的标识。FreePPT 不提供去除或擦除已添加标识的功能。

《人工智能生成合成内容标识办法》第十条规定，已添加的生成合成内容标识不得恶意删除、篡改、伪造、隐匿，为他人实施上述行为提供工具或服务同样被禁止（国家互联网信息办公室 et al.）。若确需无显式标识的生成图，合规路径是由生成服务方依第九条在用户协议里明确标识义务与使用责任、依法留存日志不少于六个月后，直接提供未添加显式标识的原件；FreePPT 只引用该原件，不参与生成或去标。文件元数据中的隐式标识不得移除，对外发布时仍应主动声明并添加显式标识。

以上为工程侧对条文的理解，不构成法律意见。FreePPT 是本地生成工具，不代替用户或服务方履行协议、留痕与声明义务。

## 安装与使用

安装用 `./install.sh --host workbuddy --scope user`；`--host all` 一次覆盖五个宿主。各宿主路径的来源与实测状态见 `docs/PUBLISHING.md`。开发源码与用户级安装目录 `~/.workbuddy/skills/freeppt/` 是副本关系，改完源码需同步一次才生效。

使用步骤：

1. 用户给出主题、受众、页数和风格，或直接给一段零散要点、一份读书笔记；需要贴合某本书的视觉气质时附上封面图。
2. FreePPT 规划结构、整理内容、逐页编排；校验未通过时回到内容层修正。
3. 校验通过后生成 .pptx，可附带全页 PNG 供复核。

命令行（全程离线、无需大模型）：

```bash
# 创作类：笔记 + 参考封面 → 逐页编排
python3 engine/cli.py compose examples/notes_renqing_mianzi.json \
  --cover examples/assets/book_cover_demo.png \
  --out deck.json --ledger style.json
python3 engine/cli.py lint  deck.json
python3 engine/cli.py build deck.json out.pptx

# 报告类：纯 CLI，无大模型、无联网
python3 engine/cli.py make "本周完成 3 项交付；满意度提升到 92%" --type weekly --out weekly.pptx

# 改稿与已有文件
python3 engine/cli.py patch examples/demo.json \
  --set "slides.0.children.0.children.1.text=新标题" --build revised.pptx
python3 engine/cli.py inspect old.pptx --out structure.json
python3 engine/cli.py retext old.pptx --map edits.json --out revised.pptx

# 安装到五个宿主 / 全量自检
./install.sh --host all --scope user
bash tools/check_all.sh
python3 tools/benchmark.py --out bench.json
```

指定报告类型可一次拿到完整章节结构，指定主题 id 可整体换肤。仓库自带示例 .pptx、`examples/GALLERY.md` 样张索引与 `examples/composition_compare.png` 九页拼版。开源协作见 `CONTRIBUTING.md`，DSL 规范见 `references/dsl-spec.md`。

## 本机实测（2026-11-08）

- `python3 -m unittest discover -s tests -q`：104 项离线单测通过。
- `engine/cli.py lint`：8 份示例 deck 零错误。
- `bash tools/check_all.sh`：四段全绿，含 compose → lint → build 产出 9 页 9 种构图，以及纯 CLI 产出 6 页。
- `tools/benchmark.py` 自测基准：平均可编辑形状占比 0.9647、版面硬错误 0、文字溢出率 0.0、核心管线联网调用静态扫描 0 处；口径见 `docs/BENCHMARK.md`。
- 注册量：16 套主题、8 类报告、10 套母版、12 种构图原型、10 组矢量资产（PNG + SVG）；14 套非默认主题逐套完成换肤校验。
- 创作编排示例：同一份笔记产出 9 页 9 种构图、4 档密度节奏，派生主题墨色/纸底对比度 16.2:1。
- 远端 GitHub Actions：2026-11-08 两次工作流运行成功，覆盖 4 个 Python 版本矩阵与 LibreOffice 渲染回归。首次运行因示例 deck 写入了作者本机绝对路径而失败，已由提交 `be35af8` 修复。

复现命令：

```bash
bash tools/check_all.sh
python3 -m unittest discover -s tests -q
python3 tools/benchmark.py --out bench.json
```

## 已知边界

- 6 套企业风格主题采用行业通用近似配色；4 套数据驱动主题取自公开提取的设计令牌。两者都不是品牌官方视觉规范，仓库里不含商标或 Logo。
- 内容扩写由执行 FreePPT 的宿主助手按创作手册完成。工程提供结构规划、要点路由和质量把关，没有内置独立的大模型 API 客户端。
- 动画与转场已写入文件并通过 XML 解析验证，尚未在 Microsoft PowerPoint 里实测播放。
- 网图检索的联网部分在本环境不可达；检索结果的解析逻辑用真实数据样本离线验证，下载 → 校验 → 留痕链路用本地服务端到端验证。
- 已入档的 Linear、Notion 令牌尚未注册为主题。两者内容页为深色系统，当前骨架是「深色封面 + 浅色内容页」，套用会让文字不可读。
- 编辑已有 .pptx 只支持结构导出与保留格式的文字替换；任意 pptx 反向解析成 FreePPT DSL 的完整往返尚未实现，见 `references/edit-existing.md`。渐变填充、受控阴影、12 列网格、图表信息图化仍在开发清单里。
- 本机未安装 `soffice`，LibreOffice 渲染回归在本机跳过，跳过不等于通过；远端 CI 安装依赖后强制断言 `status=ok`。像素级基线 diff 尚未实现。
- 五个宿主的安装路径来自官方文档或官方仓库，其中只有 WorkBuddy 在本机实测安装过；Claude Code、Codex CLI、Cursor、DSH 属于「有官方依据、未本机实测」，见 `docs/PUBLISHING.md`。
- 创作编排由确定性规则驱动，不是端到端生成式设计模型。构图原型是 12 种有限库，由 seed 与内容语义组合变化；参考图只提取色值与构图特征，引擎不复制封面图像资产，也不识别封面文字。要无限自由的版式仍需手写 freeform DSL。

## 实现与依赖

FreePPT 的布局算法、校验规则、母版、矢量图形、动画注入与检索下载代码由本工程自行实现。目录内自包含，运行时依赖 python-pptx、Pillow、lxml 与 Python 标准库；核心生成流程不联网。本工程独立原创，不引用、不依赖、不修改其他产品的技能。

4 套数据驱动主题参考 VoltAgent/awesome-design-md（MIT）收录的公开 CSS 设计令牌，只取色值与圆角尺度，不取原文、代码、Logo 或图像资产（VoltAgent）。每个色值可通过 `references/imported/theme_mapping.json` → `design_tokens.json` → 源文件 SHA256 追溯；来源、许可与映射决策见 `references/design-token-sources.md`。运行时不依赖该仓库。上述第三方数据只借鉴公开数值，其权利仍属各自权利人。

## 资料来源（MLA）

VoltAgent. "Awesome DESIGN.md." *GitHub*, 2026, github.com/VoltAgent/awesome-design-md. Accessed 8 Nov. 2026.

国家互联网信息办公室, et al. "人工智能生成合成内容标识办法." *中国网信网*, 14 Mar. 2025, www.cac.gov.cn/2025-03/14/c_1743654684782215.htm. Accessed 8 Nov. 2026.
