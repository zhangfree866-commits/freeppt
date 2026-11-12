# DSL 说明

一份 deck = 一个 JSON：`{ "scenario": "consulting", "slides": [ ... ] }`。
引擎先做 Flexbox 布局算出每元素绝对 px 矩形，再 lint，再编译。

## slide 类型
- `cover` / `toc` / `section` / `content` / `chart` / `closing`

## 通用字段
```json
{
  "type": "content",
  "layout": "rows",
  "title": "动作标题必须是完整结论句",
  "footer": {"source": "来源：……", "page": "05"},
  "children": [ <node> ]
}
```
- `layout`: `rows`（纵向）/ `cols`（横向）/ `stack`（绝对定位，少见）
- 容器可设 `gap`（24|32）、`padding`、`fill`（背景色）、`radius`、`border`、`border_opacity`（描边不透明度 0–100）。
- 渐变：容器或页面可写 `gradient:{"stops":[{"color":"#1E3A5F","pos":0},{"color":"#1C1917","pos":1}],"angle":90}`，编译为真实 OOXML 渐变填充（角度单位 1/60000 度，90° 即自上而下）；页面写字符串 `"theme"` 时解析为当前主题内置的标志性渐变（仅 magazine/tech/oriental 三主题有定义，其余主题视为无渐变）。
- 透明度：形状 `opacity`（填充 0–100）、文字 run `opacity`、描边 `border_opacity` 分别注入 OOXML alpha；毛玻璃卡典型写法为白填充 `opacity:8` + 白描边 `border_opacity:20`。
- 阴影：形状/卡片/richcard 可写 `shadow:"none"|"soft"|"medium"`（或布尔 `true`→soft），未声明时回落到主题 `visual.shadow`（默认 none，tech/microsoft/stripe 为 soft）；soft/medium 编译为真实 OOXML `a:outerShdw`（90° 正下方），`shadow_color` 可覆盖投影色（默认 `#1F2937`）。none 仅关闭继承阴影，与旧产物逐字节一致；图标与页面背景保持扁平。

## 节点类型
- `text`: `{"t":"text","text":"…","size":20,"weight":"bold|regular","color":"#061F32","align":"left","wrap":true}`
- `kpi`: 大数字 `{"t":"kpi","value":"38%","label":"…","size":96,"color":"#061F32"}`
- `card`: 容器 `{"t":"card","fill":"#FFFFFF","border":"#E5E7EB","children":[…]}`
- `box`: 纯布局容器 `{"t":"box","layout":"cols","gap":32,"children":[…]}`
- `chart`: 见下
- `divider`: `{"t":"divider","color":"#061F32"}` 1px 细线
- `spacer`: `{"t":"spacer","grow":1}` 弹性留白

## 尺寸控制
- 容器默认 hug content；需要铺满时父级 `layout` 会给子项分配交叉轴尺寸。
- `flex`: 数字，按比例分配主轴剩余空间（类似 flex-grow）。
- 文本默认 `wrap:true`，引擎按字号×字数估算高度并做溢出检查。

## chart
```json
{"t":"chart","kind":"bar|column|line|pie","flex":1,
 "series":[{"name":"Q1","values":[12,18,9]}],
 "categories":["A","B","C"],"colors":["#061F32","#08A6F6"]}
```
颜色必须在 scenario 调色板内。

## image（配图，三条通道）
```json
{"t":"image","src":"vec-growth.png","flex":1,"fit":"cover"}
```
- 相对路径相对 deck 顶层 `assets_base`；封面/章节/封底用 `"background":{"image":"x.png","overlay":62}`（navy 蒙层不透明度%）。
- lint 校验文件存在、越界；网图（在 assets/sources.json 登记过的）额外强制页面带来源（WEB_CREDIT）。

配图优先级与工具：
1. **程序化矢量（首选）**：`engine/vector_art.py`，同一图形模型输出 PNG + 可编辑 SVG，锁咨询调色板，无水印无授权问题。
   `python3 engine/vector_art.py growth out.png --svg out.svg`，10 个 motif：
   商务类 growth/dashboard/funnel/cycle/shield/network；结构图 matrix（象限矩阵）/org（组织树）/map（点阵地图航线）/venn（韦恩交集）。
2. **网页授权图片**：先用 `engine/web_search.py` 按关键词在 Wikimedia Commons 检索候选（返回直链/授权/作者/来源页），选中后把真实 URL/授权/来源页写进 `examples/web_manifest.json`，再
   `python3 engine/web_images.py manifest.json` 下载、校验并写 `assets/sources.json`；deck 只引用本地文件，该页脚必须标来源。
3. **生成式图片（需显式选用）**：ImageGen。标识由生成服务方按法规添加，FreePPT 不修改、不擦除；仅在前两条通道无法覆盖写实场景时使用。

**关于「不要 AI 标识」**：走第 1、2 条通道即可——矢量图与授权网图不是生成合成内容，成品天然没有 AI 标识，无需删除任何东西。FreePPT 不提供擦除已添加标识的能力；已添加的标识不得恶意删除、篡改、伪造、隐匿，为他人提供此类工具同样被禁止（《人工智能生成合成内容标识办法》第十条）。确需无显式标识的生成图时，应由生成服务方依该办法第九条在协议明确责任、留存日志不少于六个月后直接提供原件，FreePPT 只引用。详见 SKILL.md「配图标识合规边界」。

## shape（原生形状，流程图/徽标）
`{"t":"shape","kind":"oval|chevron|arrow|roundrect","size":58,"fill":"#08A6F6","text":"01"}`

## icon（程序化原生图标，零素材）
`{"t":"icon","name":"gear","size":56,"color":"#08A6F6"}`
- 图标在 100×100 逻辑网格上用 PowerPoint 原生形状拼合，可编辑、可改色，无位图/SVG 素材与授权面。
- `name` 支持 14 个规范名（target/chart/check/bulb/gear/shield/users/clock/folder/rocket/book/flag/search/layers）与 27 个语义别名（如 `goal`→target、`risk`→shield、`kpi`→chart），权威列表见 `engine/icons.py` 的 `ALIASES`。
- 非法名字触发 `ICON_NAME` 错误；布局保证图标恒为正方形，无显式 width 时按 `size`（默认 56）取正方形，不会被行宽拉扁。

## richcard（单形状多段文本，可整体做动画）
```json
{"t":"richcard","fill":"#FFFFFF","border":"#E5E7EB","padding":24,"_name":"card1",
 "blocks":[{"text":"标题","size":24,"weight":"bold","color":"#061F32"},
           {"text":"正文…","size":18,"color":"#44546A","space_before":10}]}
```

## 动画与转场（slide 级）
- `transition`: `"fade"`（整页切换）。
- `anims`: `[{"target":"card1","effect":"fade|fly-up","start":"click|after|with"}]`，按 `_name` 定位形状；首个默认点击触发，其余自动跟随。
- 注意：`box` 不产生形状，动画目标必须是 richcard / image / chart / shape 等真实形状。

## 模板规格（结构稳定的报告入口）
deck 可写成模板形式，`slides:[{template,data}]`，由 engine/templates.py 展开，版式与间距由模板锁定：
`cover / agenda / section / three_cards / kpi_row / chart_insight / image_text / process / timeline / closing`。示例见 examples/deck_v2.json。

**边界**：模板规格适合周报、经营分析这类结构稳定的报告；读书笔记、品牌叙事等需要逐页变化的创作类内容请走下面的自由画布，否则每页都会继承同一套「标题＋横线＋页脚」骨架。

## 自由画布 / 创作编排（内容决定构图）

```json
{
  "composed": true,
  "derived_theme": { "...": "由 cover_style.py 或从基础主题生成的派生规格" },
  "slides": [{
    "type": "content",
    "composition": "freeform",
    "tone": "light",
    "surface": "#F8F4ED",
    "archetype": "editorial-spread",
    "density": "mid",
    "children": [
      {"t": "text", "rect": [64, 96, 500, 150], "text": "大标题",
       "size": 50, "weight": "bold", "color": "#2C0F0C", "on": "#F8F4ED"},
      {"t": "box", "rect": [0, 0, 1280, 12], "fill": "#AA4C44", "children": []},
      {"t": "divider", "rect": [600, 90, 2, 540], "color": "#D9D3D2",
       "vertical": true, "thickness": 2}
    ]
  }]
}
```

- **slide 级**：`composition:"freeform"` 关闭固定骨架；`tone`（light/dark）决定默认文字色；`surface` 指定整页底色；`gradient` 指定整页背景渐变（或写 `"theme"` 用主题渐变，与 `surface` 二选一）；`archetype` 标记构图原型；`density`（airy/mid/dense）记录疏密节奏；`research` 声明研究需求、`sources` 附来源台账；`notes` 是该页演讲者备注（字符串），compose 未显式给定时会按页面已有文字确定性生成。`composed:true` 会启用分章版式多样性校验与研究台账校验。
- **节点级 `rect:[x,y,w,h]`**：freeform 下每个节点必填；子节点坐标**以父矩形左上角为局部原点**，布局时换算为绝对坐标。文本节点高度由分词换行实测自动收缩，不需要手工算。
- **自由画布新增字段**：`rotate`（旋转角度）、`opacity`（填充不透明度 0–100）、`border_opacity`（描边不透明度 0–100）、`gradient`（渐变填充，与 fill 同时存在时渐变优先）、`valign`（top/middle/bottom）、`on`（声明文字所在底色，用于 WCAG 对比度校验）、`decor`（装饰性文字，豁免字号/对比度）、`bleed`（允许出血、豁免越界）、divider 的 `vertical`/`thickness`、box 的 `kind:"roundrect"`/`radius`、`shadow`/`shadow_color`（外阴影，见上）、`col_start`/`col_span`（仅顶层节点的 12 列声明式定位：`col_start` 为 1 基起始列、`col_span` 为连续跨列数，缺省 1；水平 x/width 由网格算出，`rect` 仍负责 y/h，列间距 24px、内容带 60→1220）。
- **box 带 fill 在 freeform 下会被真实渲染为色块**（旧母版里 box 仅作透明布局容器，行为不变）。
- **lint 规则切换**：freeform 页仍强制越界、缺 rect、文本/卡片溢出、最小字号、对比度、调色板自洽（含渐变色标与图标色）、图片资产与网图来源、TABLE_SHAPE、`ICON_NAME`（图标名非法）、`SHADOW_VALUE`（shadow 取值非法，合法 none/soft/medium/布尔）、`GRID_COLUMN`（col_start/col_span 非整数或越过主题 grid_columns 列界）；不再套用 SAFE_AREA / DENSITY / GAP / TITLE_SIZE / REGIONS / CARD_CHARS 这些母版教条。全篇另查 `LAYOUT_REPETITION`（相邻页同原型）、分章 `LAYOUT_VARIETY`（每章内原型种类不足）、`RESEARCH_LEDGER`（research 页缺来源台账）、`DENSITY_FLAT`（密度无起伏，警告）；composed deck 还查 `NOTES_COVERAGE`（缺演讲者备注，错误）、`NOTES_THIN`（备注不足 40 字，警告）、`CONTENT_DENSITY`（内容页可见文字 < 60 字，警告，封面/章节/封底/引文/图表/表格原型豁免）、`GRID_COLUMN_NESTED`（嵌套节点的 col 字段被忽略，警告，网格仅对顶层节点生效）。
- **长 deck 护栏**：单个扁平文件超过 24 页且无 `kind:"chapter"` 章节页时，compose 直接 `COMPOSE BLOCKED`；分章后每章独立计算多样性预算，跨章可复用原型。`allow_long_deck:true` 可显式绕过但会产生 `LONG_DECK_FORCED` 警告，build 仍需 `--force` 且产物带 `FreePPTForcedBuildMarker`。
- **数据原语**：notes 页面携带 `chart`（kind/categories/series）或 `table`（headers/rows）时，自动路由到 chart-story / table-board 原型，编译为原生可编辑图表/表格。
- **生成方式**：`engine/art_direction.py` 按内容语义 + seed 逐页选 17 种原型之一（14 个常规原型 + 玻璃卡 `glass-panel` / 图标网格 `icon-grid` / 编号卡 `numbered-cards` 三个卡片原型），`engine/cover_style.py` 从参考封面派生 `derived_theme`；两者都只产出标准 DSL，后续仍走同一套 layout → lint → build 管线。
- **三个 compose 开关**：`--card-system`（或 `card_system:true`）把三个卡片原型纳入候选池并让深色卡片页自动套主题渐变，默认关闭以保持历史产物逐字节不变；`speaker_notes:false` 关闭演讲者备注自动生成（默认开启，生成逻辑只重组本页已有文字、不编造数据）；`--scoring`（或 `scoring:true`）把选版从 `rng.shuffle` 换成内容特征确定性评分（要点容量/金句/对比/指标/时间线等信号 + KIND_PREFS 人工偏好序），同一份 notes 在任意 seed 下产出同一套原型计划，rng 仍用于逐形状几何微调，默认关闭以保留旧 shuffle 产物。
- CLI：`python3 engine/cli.py compose notes.json --briefs briefs.json --cover cover.jpg --out deck.json --ledger style.json [--card-system] [--scoring]`；单独派生主题用 `cli.py style cover.jpg --book "书名"`。`--briefs` 是六维设计规格的必传入口（也可写在 notes 顶层的 `design_briefs`），不传会被 `design_spec` 闸门拦死；简报文件是**扁平映射**（key = 页索引或 page id），不要在外面再包一层 `{"design_briefs": ...}`，否则会静默回退到原型池。示例见 `examples/notes_renqing_mianzi.json` 与 `examples/briefs_renqing_mianzi.json`。
