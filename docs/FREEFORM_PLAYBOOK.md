# Freeform 逐页手搓 Playbook（豆包式在线手绘 SOP）

> 适用场景：宿主多模态 agent 当「逐页手绘设计师」，引擎退居「手艺人工具箱」。
> 目标是做出**全原生可编辑、零贴图、逐页不重样**、对标豆包成品设计水准的 deck。
> 配套可运行样例：[`examples/deck_freeform_handbuilt.json`](../examples/deck_freeform_handbuilt.json)。

---

## 1. 分工与边界

- **大脑（宿主 agent）**：定选题、排母题、逐页写绝对坐标 DSL、看图研判、回修。引擎不内置 LLM、不管 API key。
- **工具箱（本引擎）**：
  - `render`：deck DSL → PNG 联系表（视觉回读，不用开 PowerPoint）。
  - `lint` / `verify`：版面/几何/对比度/调色板/收尾一致性闸门。
  - `build`：DSL → 真正的 .pptx（OOXML 原生形状）。
  - `inspect`：解剖真实 .pptx 的形状类型与 PICTURE 计数（交叉验证）。
- **铁律**：PNG 预览和 .pptx 是两套独立绘制逻辑，历史上曾静默分叉（见 §9）。**每页定稿前必须用 `inspect` 交叉验证真实形状，不能只信 PNG。**

---

## 2. 画布与坐标系

- 逻辑画布固定 **1280 × 720**（`layout.CANVAS_W/H`），原点左上，单位 px。
- 安全边距 `PAD = 60`；正文内容下沿建议不超过 660，页脚放在 y≈674。
- 每个 slide **必须带** `"composition": "freeform"`，否则会被当成骨架页走 rows 自动布局，绝对坐标全部失效（典型症状：本该贴边的元素报 `OUT_OF_CANVAS x=60`）。
- 所有节点用绝对 `rect: [x, y, w, h]`；`line` 节点例外，用 `p1/p2` 两点。

最小骨架：

```json
{
  "theme": "consulting",
  "composed": false,
  "slides": [
    {"type": "content", "tone": "light", "composition": "freeform",
     "children": [ /* 绝对坐标节点 */ ]}
  ]
}
```

---

## 3. 节点 DSL 速查

| 节点 `t` | 关键字段 | 用途 |
| --- | --- | --- |
| `text` | `text, size, color, on, weight, align, valign, opacity, decor` | 文本框；`on` 是背景色，用于对比度校验 |
| `shape` | `kind, rect, fill, opacity, border, radius, shadow, decor, bleed, role` | 几何面；`kind ∈ rect/oval/roundrect/chevron/arrow` |
| `divider` | `rect, color, thickness, vertical` | 横/竖细线（用 rect 的短边表达粗细） |
| `line` | `p1, p2, color, thickness, dash` | 任意角度连接线（编译为 connector） |
| `icon` | `name, rect, color, stroke_w, knock_color` | 原生形状拼合的图标，**非贴图** |

- 阴影仅允许 `shadow ∈ soft/medium`（非法值触发 `SHADOW_VALUE`）。
- 文字/填充透明度用 `opacity: 0..100`，PIL 预览与 OOXML 两端都生效。
- `icon` 名称走 `engine/icons.py` 的 14 个规范名 + 别名；未知名触发 `ICON_NAME`。

### 图标承载块（icon chip）模式

图标本身不进几何碰撞池，但**承载图标的色块**是普通 shape，压在卡片上时要标 `decor: true` 才豁免「非嵌套压盖」检查。先 append 承载块、再 append icon，保证压盖顺序：

```python
chip = {"t": "shape", "kind": "roundrect", "rect": [x, y, 52, 52],
        "fill": ROYAL, "radius": 11, "decor": True}
glyph = {"t": "icon", "name": "chart", "rect": [x+11, y+11, 30, 30],
         "color": WHITE}
```

---

## 4. 推荐的薄 helper（不进引擎，随脚本取用）

helper 只是对节点 dict 的薄包装，引擎的稳定接口是节点 DSL 本身，因此**不把 helper 做成引擎 API**，在每个手搓脚本里按需定义即可：

```python
def txt(rect, text, size, color, on, bold=False, align="left",
        valign="top", decor=False, opacity=None): ...
def rect(xy, fill, kind="rect", border=None, radius=None, decor=False, **kw): ...
def hline(x, y, w, color=LINE_C, thickness=1.5): ...      # divider
def vline(x, y, h, color=LINE_C, thickness=1.5): ...
def connector(p1, p2, color=ORANGE, thickness=3, dash=False): ...  # line
def icon(xy, name, color=ROYAL, stroke_w=2.0, knock_color=WHITE): ...
def icon_chip(cx, cy, size, name, chip_fill=ROYAL, glyph_color=WHITE,
              glyph_ratio=0.56): ...   # 返回 (承载块, icon)，均为 decor 安全
```

完整参考实现见 8 页样章工程 `scratch/deck8/build_deck.py`（会话工作区，不入库）。

---

## 5. 统一报告页眉 / 页脚（整本一致性）

浅页统一页眉四件套 + 页脚两件套，保证不同母题的页面仍是同一本 deck：

```python
# 页眉：cyan 竖条 + eyebrow + 32 号标题 + 分隔线
vline(60, 52, 26, color=CYAN, thickness=4)
txt([78, 50, 800, 26], eyebrow, 18, GRAY, WHITE)
txt([60, 86, 1160, 44], title, 32, NAVY, WHITE, bold=True)
hline(60, 142, 1160, color=LINE_C)
# 页脚：Source + 页码
txt([60, 674, 860, 24], "Source：…", 18, GRAY, WHITE)
txt([1080, 674, 140, 24], f"{n:02d} / {total:02d}", 18, GRAY, WHITE, align="right")
```

深页（封面/收尾）把 `on` 换成深色底、文字换白/浅蓝，竖条与强调色保持 cyan 不变。

---

## 6. 三个语义标记（用语义而非几何猜测换豁免）

| 标记 | 含义 | 豁免什么 | 仍受什么约束 |
| --- | --- | --- | --- |
| `decor: true` | 纯装饰（承载块、编号圆、水印、点缀） | 对比度、几何表面压盖 | 越界、调色板 |
| `bleed: true` | 有意出血伸出画布 | 越界检查 | 其余全部 |
| `role: "data-marker"` | 数据可视化前景标记（折线点、标签胶囊） | 几何碰撞 | 越界、调色板、对比度 |

- 平级圆形/色条**有意压在卡片上** → 给该 shape 标 `decor`（编号圆、图标承载块都靠它）。
- 装饰圆伸出画布边缘 → 标 `bleed`，不要为了过闸门把它硬拉回画布。
- 折线数据点叠在柱子上是**有意层级**，给点和胶囊标 `role="data-marker"`；普通形状压盖仍会照常报警，别滥用。

---

## 7. 调色板与对比度铁律（consulting 主题）

11 色锁定：`navy #061F32 / royal #001965 / cyan #08A6F6 / light #99BDED / wine #5A0E13 / green #177B57 / orange #F47B39 / gray #44546A / mid #808080 / line #E5E7EB / white #FFFFFF`。

- **cyan / orange / mid 不可做白底文字**（对比度 < 4.5），只用于图形、强调线、深底上的元素。
- 白卡压白底会「隐形」：统一用 `light(#99BDED) + opacity=14` 的淡蓝底卡 + `soft/medium` 阴影做分层，不要靠浅灰硬边。
- 深底正文用白或浅蓝；绿色 `#177B57` 表达正向增量，wine 表达风险/负向。
- 任何不在调色板内的色值触发 `PALETTE` error，包括 icon 的 `color/knock_color`。

---

## 8. 逐页手搓闭环（标准作业循环）

```
写/改 DSL  →  render 出 PNG  →  多模态看图研判  →  回修 DSL
       ↘ 每页定稿：lint/verify 清零 → build → inspect 交叉验证 ↙
```

CLI 命令（均可 `python3 -m engine.cli …`）：

```bash
# 视觉回读：DSL -> 每页 slideNN.png（lint 有问题也照常出图，方便边修边看）
python3 -m engine.cli render deck.json out_png_dir/

# 闸门：人类可读验收报告（--strict 时 warning 也判失败，退出码 2）
python3 -m engine.cli verify deck.json --strict

# 编译真实 pptx
python3 -m engine.cli build deck.json out.pptx

# 交叉验证：真实形状类型汇总 + PICTURE 计数（#91 防护网）
python3 -m engine.cli inspect out.pptx
```

`inspect` 顶层给出 `picture_count`（手搓 deck 必须为 **0**）与 `shape_kind_totals`，每页另有 `shape_kinds/picture_count`。母题规划上让每页构图互不重复（封面/KPI 矩阵/双轴组合/占比条/时间轴/同比对照/编号卡/深色收尾），用深—浅…—深包裹节奏。

---

## 9. 双端渲染已知坑（踩过，固化为清单）

1. **rect 曾被静默编译成 oval**：`SHAPE_KINDS` 漏 `rect` 且 `.get` 默认 oval，PIL 却画矩形，导致预览直角、成品椭圆。现已修复并由 `tests/test_shape_kind_mapping.py` 钉死；未知 `kind` 现在直接报错而非回退。
2. **shape 内嵌文字 PIL 不渲染**：编号圆等一律用「独立 oval/shape + 独立 text 节点叠加」，不要用 shape 自带 text。
3. **gear6 图标 PIL 无廉价近似**：预览只画成圆环+白点，小尺寸显空；小 chip 优先选 check/target/chart/layers 等预览可辨识图标，gear 留给大尺寸，并以 inspect 的真实 `GEAR_6` 为准。
4. **LINE 形状访问 `auto_shape_type` 会抛异常**：inspect 已先按 `shape_type` 分流（LINE/PICTURE/AUTO_SHAPE）再取类型，自定义脚本解剖时照此处理。
5. **大字号文本框要留足行高**：行高约 `size × 1.3`，框高不足触发 `TEXT_OVERFLOW`（如 46 号字需 ≥60px 框高）。
6. **装饰元素与文字碰撞要肉眼复核**：半透明大数字水印旁的小圆点可能被误读成小数点（2026 → 20.26）；内容填满后及时删减冗余装饰。

---

## 10. 交付验收清单

- [ ] 每个 slide 带 `composition: freeform`，无 `OUT_OF_CANVAS`（有意出血标 `bleed`）。
- [ ] `verify --strict` 退出码 0：零 error、零 warning。
- [ ] `inspect` 的 `picture_count == 0`，形状全是 TEXT_BOX/AUTO_SHAPE/LINE connector。
- [ ] 所有颜色在主题调色板内；cyan/orange/mid 未用于白底文字。
- [ ] 图标承载块、编号圆等有意压盖均标 `decor`；数据标记标 `role="data-marker"`。
- [ ] 页码连续、无占位/调试残留（收尾闸门 `PAGE_NUMBER/PLACEHOLDER_TEXT`）。
- [ ] 全量测试不回归：`python3 -m unittest discover -s tests`、`bash tools/check_all.sh`。
