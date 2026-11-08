# FreePPT 架构与五阶段管线

> 版权说明：作者 **张三峯** ｜ 公众号 **AI龙卷风** ｜ © 2026 · 代码 MIT / 文档 CC BY 4.0（见 `LICENSE`、`LICENSE-DOCS`）

本文件说明 FreePPT 的内部结构、数据流与模块职责。FreePPT 是自包含的独立工程，
全部代码为本项目原创实现，不引用、不依赖、不修改任何其他产品或厂商的 skill。

## 一、五阶段主干（强制顺序）

```
需求/素材
   │
   ▼
[1] 规划 ────── 需求六维对齐、素材核实、scenario 风格路由、逐页结构
   │
   ▼
[2] 生成 DSL ── 受限 JSON（deck.json）。两条路径：
   │             A 母版规格 {template,data}（结构稳定的报告）
   │             B 创作编排 freeform（notes + 参考封面 → 逐页构图原型）
   ▼
[3] 布局 ────── A 固定矩形 + 行列约束；B 节点 rect 绝对定位（父矩形局部坐标）
   │
   ▼
[4] lint 校验 ─ A 母版数值规范；B 几何/溢出/对比度/配色 + 版式重复硬错误
   │              不 ok 则回到 [2] 改 DSL（数据返工）
   │  ok:true
   ▼
[5] 编译渲染 ── python-pptx 生成原生可编辑 .pptx，动画/转场注入 OOXML
```

- 渲染（阶段 5）永远在最后，且被阶段 4 硬拦截：`cli.py build` 内部先执行
  `lint_deck`，非 `ok` 且未显式 `--force` 时直接 `BUILD BLOCKED` 返回，不调用编译器。
- 「优化」不是独立的收尾环节，而是阶段 4 的诊断驱动、回阶段 2 修改数据的回路；
  不存在「先渲染出页面、再看图审美返工」。
- 两条路径只改变阶段 2/3/4 的**输入形态与规则集**，不改变五阶段顺序，也不绕过
  阶段 4 的硬闸门：`compose` 产物仍是标准 DSL，`build` 照样先 lint 再编译。

## 一之二、两条生成路径怎么选

| | A 母版规格 | B 创作编排（freeform） |
|---|---|---|
| 适用 | 周报/月报/季报/年报/述职/竞聘/复盘/经营分析 | 读书笔记、书评、品牌叙事、演讲稿、课程讲义 |
| 输入 | `{template,data}` | `notes.json`（book + pages）+ 可选封面图 |
| 版式来源 | 10 套固定母版，填数据即出片 | 14 种构图原型（含原生图表/表格页）按内容语义 + 确定性 seed 逐页分配，长 deck 按章节重置多样性预算 |
| 视觉语言 | 16 套注册主题换肤 | 封面图派生主题（主色/纸底/字体气质/母题）+ 可复现台账 |
| 骨架 | 每页固定标题 + 横线 + 内容区 + 页脚 | 不自动加骨架，每页元素自带绝对 rect |
| lint | SAFE_AREA / DENSITY / GAP / TITLE_SIZE / CARD_CHARS… | 几何、溢出、对比度、配色自洽 + LAYOUT_REPETITION / 分章 LAYOUT_VARIETY / RESEARCH_LEDGER / TABLE_SHAPE |
| 关键模块 | `templates.py` + `reports.py` + `content_ai.py` | `art_direction.py` + `cover_style.py` + `themes.build_derived()` |

B 路径解决的是「同一份材料做出来的十页都长一个样」：它把**相邻页构图重复**与
**章节内构图种类不足**写成 `lint` 的错误码，而不是交给提示词自觉。`composed:true`
的 deck 每页必须带 `archetype`；多样性预算按章节计算，每个章节的内容页原型数至少
`min(章页数, max(3, ⌈章页数/2⌉))`，章节页（chapter-opener）不计入。单个扁平文件超过
`CHAPTER_PAGE_CAP=24` 页且无章节页时，`compose` 在规划阶段直接拒绝（`COMPOSE BLOCKED`）；
显式 `allow_long_deck:true` 可绕过护栏但会留痕，build 时仍需 `--force` 并在产物内打标记。

## 二、数据流与模块职责

| 模块 | 阶段 | 职责 |
|---|---|---|
| `SKILL.md` | 1 | 任务路由、五阶段流程、scenario 选择、闸门约束 |
| `engine/scenarios.py` | 1 | 旧 scenario 注册表（保留兼容；新代码改走 themes） |
| `engine/themes.py` | 1/4/5 | **视觉主题注册表**：16 套主题（6 通用 + 6 企业风格 + 4 数据驱动）的语义色、字体配对、圆角、阴影、行距、图表色、密度 token；`activate/resolve_name` 解析 deck 的 theme/scenario，consulting 锁定历史值保证零回归；`build_derived()` 把参考图派生规格注册为一次性主题并重算调色板 |
| `references/design-principle.md` | 1/4 | 数值化设计规范，是 lint 规则的判定依据 |
| `references/dsl.md` | 2 | DSL 节点白名单与字段、动画/转场、配图三通道说明 |
| `engine/templates.py` | 2→3 | 10 套母版；`expand_deck` 把 `{template,data}` 展开成裸 deck |
| `engine/art_direction.py` | 1/2 | **创作编排**：14 种构图原型（含 chart-story/table-board 数据原型）、MIN_POINTS 内容适配、章节感知 `plan_archetypes()`（相邻不同 + 章内优先未用 + 跨章重置）、chart/table 数据页显式路由、长 deck 护栏、按文本实测高度生成绝对 rect、seed 可复现，产出 `composed:true` 的标准 DSL |
| `engine/cover_style.py` | 1 | **参考图派生**：Pillow 中位切分量化 → 彩度×占比×中间调打分选主色（避开大面积纸底）→ 纸底/墨色/强调色对比度保障 → 主色块位置决定母题 → `derived_theme` + SHA256 台账；纯离线、确定性 |
| `examples/notes_renqing_mianzi.json` | 输入 | 9 页读书笔记素材（封面图 + 逐页内容语义） |
| `examples/composition_compare.png` | 验收 | 九页拼版，直观验证逐页构图差异 |
| `engine/layout.py` | 3 | 固定矩形布局引擎：行列分配、CJK/拉丁混合换行、图片比例、坐标落位；`_place_free()` 处理 freeform 绝对 rect 与父子局部坐标 |
| `engine/lint.py` | 4 | 确定性校验：母版页查越界/安全区/文字溢出/字号/间距/配色/密度/来源/资产；`_lint_freeform_slide()` 查几何、溢出、WCAG 对比度、调色板自洽、TABLE_SHAPE；`lint_deck()` 查全篇版式重复、分章多样性、RESEARCH_LEDGER 研究台账与密度节奏 |
| `engine/compiler.py` | 5 | python-pptx 渲染：文本/KPI/卡片/原生图表/原生表格/形状/图片/蒙层；freeform 额外渲染填充色块、旋转、半透明、垂直对齐、竖向分隔线；`--force` 时在产物内写 FreePPTForcedBuildMarker，输出 .pptx |
| `engine/animator.py` | 5 | python-pptx 无动画 API，自写 `p:timing`/`p:transition` 注入 OOXML |
| `engine/cli.py` | 1–5 | 入口：`compose`（笔记→创作编排 DSL）、`style`（封面→派生主题）、`make`（纯 CLI：brief→骨架→内容闸门→lint→pptx）、`inspect`/`retext`（已有 pptx）、`patch`（单节点改稿）、`lint`、`build`（校验闸门+编译） |
| `engine/debug_render.py` | 验收 | 离线把 deck 渲染成全页 PNG，供无 Office 环境视觉复核；支持 freeform 色块、圆角、竖向线与 token 感知换行 |
| `engine/brief_fill.py` | 1/2 | 纯 CLI 填充器：brief 要点路由进 8 类报告骨架，未提供的字段写明确空态说明，图表数值只取自输入；不编造事实、不调 LLM |
| `engine/typography.py` | 3/4 | 中文避头尾禁则、标点悬挂、`——/……` 不拆行、可选中英混排窄空格、声明式字体回退栈；`CJK_KINSHOKU` 进 lint |
| `engine/pptx_edit.py` | 编辑 | 已有 pptx 结构导出与保留 run 字体的文字替换；明确不做 pptx→DSL 往返 |
| `engine/deck_patch.py` | 2 | 点号路径改 DSL 单节点，改完仍由阶段 4 复检 |
| `tools/benchmark.py` / `tools/render_check.py` | 验收 | 可量化自测基准（版面错误/可编辑率/溢出率/离线就绪/耗时）；LibreOffice PDF/PNG 回归（缺依赖明确 skipped，CI 强制 ok） |
| `install.sh` / `docs/PUBLISHING.md` | 分发 | 五宿主一键安装（WorkBuddy / Claude Code / Codex CLI / Cursor / DSH），路径来源逐条标注|
| `tests/test_art_direction.py` / `tests/test_long_deck_guard.py` | 验收 | 创作编排单测：派生配色对比度/确定性、逐页原型不重样、重复版式与缺多样性被拦、自由画布不受母版教条误判、PPTX 原生形状可编辑、旧 deck 零回归；护栏单测：长扁平文件 compose 拦截、分章 deck 过闸、跨章复用、force 产物标记、RESEARCH_LEDGER、原生 chart/table 编译与 inspect 回读 |
| `tests/test_open_source_tooling.py` | 验收 | 25 项单测：8 类报告纯 CLI 全绿、禁则修复、patch 闸门、retext 格式保留、基准口径、安装脚本 dry-run、许可文件 |
| `engine/design_md_import.py` | 1（可选） | 确定性解析第三方 DESIGN.md frontmatter 的公开数值令牌（色值/圆角/间距/字阶）；语义角色由显式映射表指定，缺键报错，不猜测 |
| `references/imported/*` | 1（可选） | `design_tokens.json` 数值档案（含来源 URL + SHA256）、`theme_mapping.json` 角色映射；台账与许可见 `references/design-token-sources.md` |
| `engine/reports.py` | 1/2 | 8 类企业报告场景注册表（页面结构→模板映射→字段→写作提示）+ 确定性骨架生成 |
| `engine/content_ai.py` | 1/4 | 智能创作：brief 解析、要点按章节路由、内容质量把关（占位/套话/无据主张/来源）；语言扩写由 agent 按 content-playbook 完成 |
| `references/content-playbook.md` | 1/4 | 内容创作手册：Action Title、金字塔/MECE、数据→结论、套话黑名单、各报告叙事主线 |

### 配图支线（产物统一落到本地 assets，deck 只引用本地文件）

| 模块 | 通道 | 职责 |
|---|---|---|
| `engine/vector_art.py` | 程序化矢量（首选） | 统一图形 IR，双后端输出 PNG + 可编辑 SVG，10 个 motif，无水印无授权问题 |
| `engine/web_search.py` | 网页授权图·检索 | Commons 关键词检索；网络层与解析层解耦，支持离线 fixture |
| `engine/web_images.py` | 网页授权图·下载 | manifest 下载 + PIL 校验 + 写 `sources.json` 来源台账 |
| `engine/make_cover_bg.py` | 程序化封面 | PIL 绘制封面背景，非 AI 生成、无标识 |
| 生成式 ImageGen | 生成式（需显式选用） | 写实场景；标识由生成服务方添加，FreePPT 不修改、不擦除 |

网图合规由 lint 的 WEB_CREDIT 规则强制：凡在 `sources.json` 登记的网图，所在页必须标注来源。

标识合规边界：默认配图走矢量与授权网图，成品天然不含 AI 标识；FreePPT 不实现擦除已添加标识的功能（《人工智能生成合成内容标识办法》第十条禁止恶意删除及提供此类工具）。合规的无显式标识生成图须由生成服务方依第九条在协议明确责任、留痕不少于六个月后直接提供，FreePPT 只引用原件；隐式标识与发布时的主动声明义务不因此免除。详见 SKILL.md「配图标识合规边界」。

## 三、目录结构

```
ppt-skill/
├── SKILL.md                 # skill 入口（name: freeppt）
├── requirements.txt         # 仅通用开源基础库
├── engine/                  # 全部原创引擎代码
├── references/              # 设计规范、DSL、scenario、本架构文档
├── examples/                # deck 示例、web_manifest、assets 资产
└── tests/                   # 离线单测与真实 schema fixture
```

## 四、独立性与依赖边界

- 内部 import 只在 `engine.*` 之间发生；没有任何对外部厂商/产品 skill 的引用或调用。
- 外部依赖仅为通用开源基础库与 Python 标准库（见 `requirements.txt`）：
  - **python-pptx**：生成 OOXML/.pptx 的通用库
  - **Pillow**：图片校验、程序化位图绘制、离线验收渲染
  - **lxml**：OOXML XML 处理（python-pptx 同栈，动画注入直接使用）
- 联网仅发生在用户显式走网图通道时（Wikimedia Commons 检索 / 图片下载），
  且检索的解析逻辑可完全离线测试；核心生成流程不依赖网络。
