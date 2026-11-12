# FreePPT DSL 规范

**作者：张三峯** ｜ 公众号：**AI龙卷风** ｜ 代码 MIT / 文档 CC BY 4.0

本文件是 `deck.json` 的字段与约束规范。可执行的权威定义是 `engine/layout.py`、
`engine/lint.py`、`engine/compiler.py`；三者与本文件冲突时以代码为准，并应提 PR 修文档。

## 0. 单位与画布

| 项 | 值 |
|---|---|
| 画布 | 1280 × 720 px（16:9） |
| 坐标 | `[x, y, w, h]`，左上角为原点，向下向右为正 |
| 编译换算 | 1 px = 9525 EMU（96 dpi） |
| 输出 | `.pptx`，原生形状/文本/图表，可编辑 |

## 1. deck 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `theme` | string | 主题 id（16 套）或派生主题名；`theme` 优先于 `scenario` |
| `scenario` | string | 旧场景名，兼容保留 |
| `transition` | string | 转场类型，写入 OOXML |
| `assets_base` | string | 图片相对路径的基准目录 |
| `slides` | array | 页面数组，必填 |
| `composed` | bool | 是否由 `art_direction.compose()` 产出；开启分章版式多样性硬闸门与研究台账校验 |
| `art_direction` | object | 原型序列、seed、去重统计、`chapter_boundaries`、`chapters`、`long_deck_forced`、`card_system`、`speaker_notes`、`scoring` |
| `derived_theme` | object | 封面图派生主题规格（含 semantic / palette_extra / source） |
| `typography` | object | `kinsoku`（默认 true）、字体回退栈、`latin_cjk_spacing` |
| `_cli_brief` | object | `cli.py make` 的原始要点记录，`no_llm: true` |

## 2. 两种页面形态

### 2.1 母版规格 `{template, data}`

由 `engine/templates.py` 展开。10 个 template id：
`cover / agenda / section / three_cards / kpi_row / chart_insight /
image_text / process / timeline / closing`。
`reports.py` 的 8 类报告骨架就是这种形态，`data` 字段见各报告 `section_plan()`。

### 2.2 自由画布 `composition: freeform`

| 字段 | 类型 | 说明 |
|---|---|---|
| `composition` | `"freeform"` | 关闭自动「标题＋横线＋页脚」骨架 |
| `type` | string | `cover / section / content / closing` |
| `tone` | `"light" \| "dark"` | 决定默认文字色 |
| `surface` | hex | 显式指定整页底色 |
| `background` | object | `{image, overlay}`，支持封面图与蒙层 |
| `gradient` | object/string | 整页背景渐变 `{stops:[{color,pos,opacity?}],angle}`（angle 单位 1/60000 度）；字符串 `"theme"` 解析为当前主题的 `background_gradient`（仅 magazine/tech/oriental 有定义） |
| `archetype` | string | 构图原型 id（composed deck 必填，相邻页不得相同；共 17 种 = 14 常规 + glass-panel / icon-grid / numbered-cards 三个卡片原型，后三者仅 `card_system` 开启时入池，含 chart-story / table-board） |
| `density` | string | 疏密标记，全篇不得完全一致 |
| `research` | bool/string | 该页需要外部研究；为真时必须附 `sources` 或 `source`，否则 RESEARCH_LEDGER 阻断 |
| `sources` | array | 研究来源台账 `[{title, url, publisher}]`，每项须有 title 且至少有 url 或 publisher |
| `notes` | string | 演讲者备注，编译为 notesSlide；compose 默认确定性生成（只重组本页文字），可显式覆盖，`speaker_notes:false` 关闭 |
| `children` | array | 绝对定位节点；子节点 `rect` 以父节点左上角为局部原点 |

## 3. 节点类型

| `t` | 用途 | 关键字段 |
|---|---|---|
| `text` | 文本 | `text, size, color, weight, align, valign, rotate, on, decor, bleed` |
| `kpi` | 大数字指标 | `value, label, vsize, lsize` |
| `richcard` | 富文本卡片 | `blocks:[{text,size,weight,space_before,...}]` |
| `card` / `box` | 容器 | `fill, border, padding, radius, children`；freeform 下带 `fill` 的 box 也会渲染 |
| `image` | 图片 | `src, fit`；外部来源须登记 `sources.json` |
| `chart` | 原生图表 | `kind, categories, series, colors, legend`；`chart_insight` 页须给 `source`；创作链路经 chart-story 原型产出 |
| `table` | 原生表格 | `headers:[...], rows:[[...]]`，可选 `header_fill/header_color/body_color/zebra/border`；行列数必须一致（TABLE_SHAPE）；创作链路经 table-board 原型产出 |
| `shape` | 几何形 | `kind: rect/oval/roundrect, fill, rotate, opacity` |
| `icon` | 程序化原生图标 | `name`（14 规范名 + 27 别名，见 `engine/icons.py`）、`size`/`width`/`height`、`color`（默认主题 accent）、`rotate`；恒正方形，非法 name 触发 ICON_NAME |
| `divider` | 分隔线 | `color, thickness, vertical` |
| `spacer` | 占位 | 高度 0 |

freeform 节点通用可选字段：`rect`（必填）、`fill`、`border`、`border_opacity`
（描边不透明度 0–100）、`gradient`（渐变填充，与 fill 同时存在时渐变优先）、
`rotate`、`opacity`（0–100，写入 OOXML alpha；形状/文字 run/描边各有独立 alpha 通道）、
`valign`、`on`（声明文字底色，用于 WCAG 对比度校验）、`decor`（装饰元素，不参与部分内容规则）、`bleed`（出血）、
`shadow`（`none`/`soft`/`medium` 或布尔，默认回落到主题 `visual.shadow`）、`shadow_color`（投影色，默认 `#1F2937`）、
`col_start` / `col_span`（仅顶层节点，12 列声明式定位，见 3.2）。

### 3.1 视觉原语（渐变 / alpha / 图标）

- **渐变 `gradient`**：`{"stops":[{"color":"#1E3A5F","pos":0},{"color":"#1C1917","pos":1}],"angle":90}`。
  编译为真实 OOXML `a:gradFill`，angle 以 1/60000 度计（90° = 5400000，自上而下）；
  色标可选 `opacity`（0–100）。页面级写 `"theme"` 哨兵时由 layout 解析为主题 token，
  主题未定义则视为无渐变（旧主题默认平面，保证零回归）。
- **三类 alpha**：形状填充 `opacity` → `solidFill/srgbClr/a:alpha`；文字 run `opacity` →
  `rPr/solidFill/.../a:alpha`；描边 `border_opacity` → `ln/solidFill/.../a:alpha`。
  取值 0–100，编译为 val = opacity × 1000。毛玻璃卡典型值：白填充 `opacity:8` +
  白描边 `border_opacity:20`。
- **图标 `icon`**：`{"t":"icon","name":"gear","size":56}`。14 个图标（target/chart/
  check/bulb/gear/shield/users/clock/folder/rocket/book/flag/search/layers）在 100×100
  逻辑网格上用 MSO 原生形状拼合，零素材、可编辑、主题 accent 单色驱动；`resolve(name)`
  负责 trim/大小写归一与 27 个语义别名解析。图标无显式 width 时按 `size`（默认 56）
  取正方形，布局不会把它拉扁。
- **外阴影 `shadow`**：取值 `"none"|"soft"|"medium"` 或布尔（`true`→soft、`false`→none）；
  节点未声明时回落到主题 `visual.shadow`（默认 `none`，tech/microsoft/stripe 为 `soft`）。
  soft/medium 编译为真实 OOXML `a:effectLst/a:outerShdw`（90° 正下方，blur/dist/alpha 档位见
  `compiler.SHADOW_PRESETS`），可用 `shadow_color` 覆盖投影色。`none` 仅关闭继承阴影，与历史
  产物逐字节一致；图标节点与页面背景保持扁平、不吃阴影。

### 3.2 声明式 12 列网格（freeform 顶层）

- 主题 `visual.grid_columns`（默认 12）此前是未被消费的死 token，现由 layout 映射到母版内容带
  （x = 60 → 1220，列间距 `GRID_GUTTER = 24`px）。
- 顶层 freeform 节点可用 `col_start`（1 基起始列）+ `col_span`（连续跨列数，缺省 1）声明水平
  几何，替代绝对 `rect` 的 x/width；`rect` 仍负责 y/h。参考值：单列宽 74.7px、6 列 568px、满栏 1160px。
- 网格仅对**顶层节点**生效；嵌套节点写 col 字段会被忽略并触发 `GRID_COLUMN_NESTED` 警告。
  不写 col 字段的节点继续走绝对 `rect` 旧路径，默认产物零回归。
- `col_start < 1`、`col_span < 1` 或 `col_start + col_span - 1 > grid_columns` 触发 `GRID_COLUMN` 错误。

## 4. 五阶段与硬闸门

`planning → generate DSL → layout → lint → compile/render`

- `cli.py build` **先 lint 再编译**，不通过直接返回 1，不产出文件。
- `cli.py make` 额外先跑 `content_ai.check_content()` 的内容闸门。
- `cli.py patch` 改完节点会重新走同一套 lint。
- `--force` 仅供调试，交付件不应使用。

## 5. lint 诊断码

**错误级（阻断编译）**

| 码 | 含义 |
|---|---|
| `OUT_OF_CANVAS` / `FREEFORM_RECT` | 元素越界 / freeform 节点缺 `rect` |
| `SAFE_AREA` / `REGIONS` | 母版页安全区、区域约束 |
| `TEXT_OVERFLOW` / `RICHCARD_OVERFLOW` | 文字溢出容器 |
| `TEXT_OVERLAP` | 文字重叠 |
| `CARD_CHARS` | 等高卡片正文不足 40 字（高卡片 100 / 130 字） |
| `TITLE_LEN` / `TITLE_SIZE` / `BODY_SIZE` / `FONT_SIZE` | 标题长度与字号约束 |
| `FOOTER_POS` / `FOOTER_SIZE` / `FOOTER_FORBIDDEN` | 页脚位置、字号、禁用页 |
| `GAP` / `DENSITY` | 间距档位与密度 |
| `PALETTE` / `CONTRAST` | 颜色必须落在主题调色板内；文字/底色对比度 |
| `SOURCE` / `WEB_CREDIT` / `ASSET_MISSING` | 数据来源、网图署名、素材文件存在性 |
| `LAYOUT_REPETITION` / `LAYOUT_VARIETY` | 相邻页构图重复 / 章节内原型种类不足（按章计算） |
| `COMPOSED_METADATA` | composed deck 缺 `archetype` |
| `RESEARCH_LEDGER` | 页面声明了 research 但没有可用来源台账 |
| `TABLE_SHAPE` | 原生表格缺 headers/rows 或行列数不一致 |
| `CJK_KINSHOKU` | 换行处违反避头尾禁则或拆开 `——` / `……` |
| `ICON_NAME` | `icon` 节点的 `name` 在图标库（含别名）中解析不到 |
| `NOTES_COVERAGE` | 开启讲稿覆盖（composed deck 且 `speaker_notes` 未关）的页面缺 `notes` |
| `SHADOW_VALUE` | 节点 `shadow` 取值不在 `none`/`soft`/`medium`（布尔值合法） |
| `GRID_COLUMN` | freeform 顶层节点 `col_start`/`col_span` 非整数或越过主题 `grid_columns` 列界 |

**警告级（不阻断）**：`ACTION_TITLE`、`DENSITY_FLAT`、`LONG_DECK_FORCED`、`CLICHE`、`WEAK_CLAIM`
（后两者来自 `content_ai.check_content()`）、`NOTES_THIN`（讲稿不足 40 字）、
`CONTENT_DENSITY`（composed 内容页可见文字 < 60 字；封面/章节/封底/引文/图表/表格原型豁免）、
`GRID_COLUMN_NESTED`（嵌套节点的 col_start/col_span 被忽略，网格仅对顶层节点生效）。

## 6. 中文排版

`engine/typography.py` 默认开启避头尾：行首禁则字符悬挂到上一行末，
行末开引号推到下一行首，`——` / `……` 不拆行。单字符装饰节点豁免（没有换行
可约束）。`typography.kinsoku: false` 可显式关闭，关闭后 `CJK_KINSHOKU`
检查也随之停用。

`--cjk-spacing`（仅 `cli.py make`）在 CJK 与拉丁字母/数字之间插入 U+2009 窄空格；
默认关闭，因为改变字符串长度会改变既有 deck 的确定性布局。

字体回退栈是**声明式元数据**：FreePPT 不在构建时探测本机字体，否则同一份
DSL 在不同机器上会产出不同字体，破坏确定性。

## 7. 合规约束

- 不实现任何 AI 标识擦除/隐匿工具；默认配图为程序化矢量或已授权网图。
- 网图须写入 `examples/assets/sources.json`，lint 检查 `WEB_CREDIT`。
- 企业风格主题是风格化近似，不含第三方商标或官方 VI。
