# 编辑已有 .pptx

**作者：张三峯** ｜ 公众号：**AI龙卷风**

## 现状（如实说明）

已实现：`inspect`（结构导出）与 `retext`（保留格式的文字替换），以及
`patch`（对自己生成的 DSL 做单节点改稿后重编译）。

**未实现**：把任意已有 .pptx 反向解析成 FreePPT DSL 的完整往返。也就是说，
你拿一份别处做的 PPT，可以让 FreePPT 读它、改里面的文字，但不能让 FreePPT
「理解它的版式并用 16 套主题重排」。这是明确的边界，不是隐含承诺。

## 1. 结构导出

```bash
python3 engine/cli.py inspect old.pptx --out structure.json
```

输出每页的 `shape_id`、`name`、`type`、`rect_px`（1280×720 坐标系）、
文本与每个 run 的字号/字体/粗体。`rect_px` 由 EMU ÷ 9525 换算。
这个文件是只读报告，不是 DSL。

## 2. 文字替换

先写编辑映射（字段三选一：`shape_id` / `shape` 名称 / `match` 文本片段）：

```json
{
  "edits": [
    { "slide": 1, "shape_id": 5, "text": "改稿后的标题文字" },
    { "slide": 3, "match": "旧口径", "text": "新口径说明" }
  ]
}
```

再执行：

```bash
python3 engine/cli.py retext old.pptx --map edits.json --out revised.pptx
```

行为：

- 只改 `text_frame` 里第一个 run 的 `text`，其余 run 清空；**第一个 run 的
  字体、字号、粗体保留**（本机实测：Georgia / 48pt / bold 替换前后一致）。
- 页数、形状数、坐标、图片、图表、动画全部不动。
- 未命中的编辑会列进报告的 `missed`，命令返回 1。
- 示例映射见 `examples/edits_example.json`。真实文件的 `shape_id` 不同，
  务必先用 `inspect` 取当前值。

风险：新文字比原文字长很多时可能溢出原文本框。FreePPT **不重排**已有
形状，报告里会给出 warning。请打开 `.pptx` 目视确认。

## 3. 局部改稿（FreePPT 自己生成的 deck）

```bash
python3 engine/cli.py patch deck.json \
  --set "slides.0.data.title=改后的结论句" \
  --out patched.json --build patched.pptx
```

`--set` 可重复，路径用点号 + 数字索引（`slides.3.children.2.text`）。改完
仍走阶段 4 的 lint 闸门；本机实测把某个 text 节点 `size` 改为 5 会被
`FONT_SIZE` 拦下、不产出 pptx。错误路径会返回 `PATCH REJECTED`，不抛栈。

## 4. 想做整体重排怎么办

当前唯一支持的路径是：把内容整理成 FreePPT 的输入（一份 brief 或一份
notes JSON），走 `make` / `compose` 重新生成。这不是「编辑原文件」，而是
「用内容重新做一份」，文档措辞上不混用。

## 5. 后续可做（尚未排期）

- 把已有 pptx 的文字/图片/层级抽成结构化内容大纲（不是版式 DSL）；
- 针对替换后的文本做自适应字号（`compiler._fit_size` 已有，可复用）；
- 保留原主题色的局部换肤。
