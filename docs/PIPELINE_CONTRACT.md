# FreePPT × ppt-master 融合管线契约（PIPELINE CONTRACT）

> 目标：每页既有美观度又有内容度，成品效果追赶豆包 PPT。
> 本文件是四层管线的正式契约，字段以引擎实际代码为准（标注【已实测】/【推断】）。

## 1. 四层架构

```
① 规划层  FreePPT art_direction    notes → archetype plan（无坐标）
     │      engine/page_spec.py    plan  → Deck Plan / Page Spec（无坐标）
     ▼
② 创作层  SVG（1280×720 绝对矢量）   模型逐页自由发挥，内容取自 Page Spec
     │
     ▼
③ 质检层  ppt-master svg_quality_checker   XML 契约 / 越界 / 字号角色
     │      engine/svg_guard.py            对比度 / 容量 / 密度 / 事实来源
     ▼
④ 编译层  ppt-master svg_to_pptx   SVG 图元 → PowerPoint 原生 DrawingML
                                   （非贴图、非整页截图，可编辑）
```

分工原则：**ppt-master 干「表达与编译」，FreePPT 干「规划与护栏」**。
两层通过 Deck Plan（无坐标 JSON）解耦，互不 import 对方内部实现。
ppt-master 是**外部前置依赖**（独立 LICENSE），不打包进 FreePPT。

## 2. 画布口径（两引擎一致，【已实测】）

| 项 | 值 |
|---|---|
| 尺寸 | 1280 × 720（16:9） |
| DPI | 96 |
| EMU/像素 | 9525（=914400/96） |

## 3. 阶段产物边界

### 3.1 输入 notes（创作意图，无坐标）
```jsonc
{
  "book": {"title": "", "author": "", "language": "zh-CN"},
  "pages": [
    {"kind": "cover|chapter|content|timeline|closing",
     "title": "", "kicker": "", "lead": "",
     "points": [{"head": "", "body": ""}],   // 或字符串数组
     "left": {"head":"","body":""}, "right": {...},   // 对比页
     "chart": {"kind":"column","categories":[],"series":[[]]},
     "table": {"headers":[],"rows":[[]]},
     "value": 50, "label": "", "unit": "%",           // 单 KPI
     "quote": "", "source": "", "sources": [],
     "notes": ""}
  ]
}
```

### 3.2 Deck Plan / Page Spec（① → ②③ 的唯一交接物，无坐标）
由 `engine/page_spec.py: build_deck_plan()` 产出，结构：
```jsonc
{
  "canvas": {"width":1280,"height":720,"dpi":96},
  "deck": {"title":"","author":"","language":"zh-CN","total_pages":N},
  "style_lock": {"colors": {...}, "fonts": {"stack": ""}},
  "chapter_boundaries": [0],
  "pages": [{
    "index":0, "kind":"content", "chapter":"",
    "archetype":"editorial-spread",
    "title":"", "kicker":"", "lead":"",
    "points":[{"head":"","body":""}],
    "quote":"", "compare":{},
    "datasets":[{"type":"column|bar|kpi|timeline","series":[],"categories":[],"unit":""}],
    "capacity":3,                 // null = 不限
    "density_hint":"airy|mid|dense",
    "sources":[], "notes":""
  }]
}
```

### 3.3 SVG（② 创作产物）
- 根 `<svg width="1280" height="720" viewBox="0 0 1280 720">`
- **首页先铺整页 paper 底色**（否则 pptx 里内容浮在纯白上）
- 文字用 `<text>` + `<tspan>`，禁 `<foreignObject>`/HTML 实体
- 反复出现的字号须在项目 `spec_lock.md` 的 `typography` 段声明为命名角色
- 图片 href 用**相对该 SVG 文件**的相对路径

## 4. 容量与密度（单一事实源，定义在 art_direction.py）

- `MAX_POINTS`：editorial-spread/data-focus=3、stair-list/timeline-ribbon=5、
  grid-mosaic=4、six-board=6、margin-notes=4、glass-panel/numbered-cards=3、icon-grid=4
- 密度档位（叶子形状/页，svg_guard 读取）：airy 3–15、mid 10–25、dense 25–90
- 叶子 = 展开 group 后的 rect/circle/ellipse/path/polygon 去重计数

## 5. 质检硬闸

| 检查 | 负责 | 不达标 |
|---|---|---|
| XML 契约/越界/字号角色 | ppt-master quality_checker | 阻断编译 |
| CONTRAST 文字对比度 | svg_guard | blocker |
| CAPACITY 要点超容量 | svg_guard | blocker |
| DENSITY 形状密度 | svg_guard | advisory |
| FACT 含数字叙述需有 sources | svg_guard | blocker |
| LEDGER layout_id 唯一 / 相邻不同族皮 / 同族页码间隔 ≥ gap | layout_ledger（独立账本硬闸） | 阻断编译 |

对比度分流（WCAG）：正文 ≥4.5、大字（≥24px）≥3.0、
轴标签/类别名/脚注（≤14px）≥3.0；跨页页脚放行。
特殊 advisory：`CONTRAST_PHOTO`（文字落在位图、机器读不到明暗→人工确认）、
`CONTRAST_DECOR`（纯数字装饰序号→人工确认）。

## 6. CLI 操作（【已实测】）

```bash
# ① 规划：notes → composed deck + 无坐标 plan.json
python3 -m engine.cli compose notes.json --emit-plan plan.json

# ③ FreePPT 护栏
python3 -m engine.cli svgguard plan.json svg_output/

# ③ 版式账本硬闸（长项目保证全本零重复版式；layout_ledger.json 由分配器产出）
python3 -m engine.cli ledger layout_ledger.json

# ③+④ 质检并编译为原生 pptx（--strict 走 canonical/final 硬闸）
python3 -m engine.cli compile-svg <project_dir> out.pptx [--strict] [--skip-quality]
```

ppt-master 定位：`~/.workbuddy/skills/ppt-master`；
可用环境变量 `FREEPPT_PPTMASTER` 覆盖。找不到时报清晰安装提示。

## 7. 交付特性（【已实测】）

编译产物每页图元落为原生 AutoShape / Freeform / TextBox，可在 PowerPoint 编辑；
非整页位图。POSTFLIGHT `quality_gate=passed`。

## 8. 版式账本（Layout Ledger，长项目零重复的契约层）

数据驱动版式项目（family 几何家族 × chrome 皮肤）在规划阶段由分配器产出
`layout_ledger.json`，`engine/layout_ledger.py: validate()` 做与几何解耦的硬闸：

```jsonc
{
  "family_gap": 4,
  "entries": [
    {"index": 0, "pn": "P1", "layout_id": "bands__topq-m3-v1",
     "family": "bands", "chrome": "topq", "special": false}
  ]
}
```

三条规则（任一不满足 ok=false）：① layout_id 全局唯一；② 相邻通用页不同
family、不同 chrome；③ 同 family 两次出现的真实页码间隔 ≥ family_gap。
特型页（special=true，封面/章节/金句/定制数据页）只参与唯一性。
实测：英伟达 91 页账本 ok=true，78 通用页 + 13 特型页，24 家族各 3–4 次。
