# 样张画廊

**作者：张三峯** ｜ 公众号：**AI龙卷风**

本页只列出仓库里**实际存在**的文件。所有 `.pptx` 都是原生可编辑形状，可以
直接用 PowerPoint / WPS / Keynote 打开改字；PNG 是离线渲染的预览，不是产物。

## 逐页创作编排（版式不重复）

| 预览 | 产物 | 说明 |
|---|---|---|
| [composition_compare.png](composition_compare.png) | [FreePPT_读书笔记_创作编排示例.pptx](FreePPT_读书笔记_创作编排示例.pptx) | 同一份《人情与面子》9 页笔记 → 9 种构图、4 档密度；封面图派生朱红＋米色纸＋竖线母题 |
| — | [notes_renqing_mianzi.json](notes_renqing_mianzi.json) | 9 页输入素材 |
| — | [deck_notes_composed.json](deck_notes_composed.json) | 编排后的标准 DSL |
| — | [style_notes_derived.json](style_notes_derived.json) | 封面 SHA256、色板、对比度台账 |
| — | [assets/book_cover_demo.png](assets/book_cover_demo.png) | 示意重绘封面（非真实书封，可替换） |

复现：

```bash
python3 engine/cli.py compose examples/notes_renqing_mianzi.json \
  --cover examples/assets/book_cover_demo.png \
  --out deck.json --ledger style.json
python3 engine/cli.py lint  deck.json
python3 engine/cli.py build deck.json out.pptx
python3 engine/debug_render.py deck.json /tmp/preview
```

## 主题对比

| 预览 | 覆盖主题 |
|---|---|
| [theme_compare.png](theme_compare.png) | consulting / magazine / tech / swiss / oriental |
| [enterprise_theme_compare.png](enterprise_theme_compare.png) | mckinsey / bcg / pwc / rolandberger / microsoft / apple |
| [data_driven_theme_compare.png](data_driven_theme_compare.png) | stripe / vercel / wired / ibm（公开 DESIGN.md 令牌） |
| [motif_overview.png](motif_overview.png) | 10 组程序化矢量母题 |

对应可打开的文件：

- [FreePPT_科技风主题示例.pptx](FreePPT_科技风主题示例.pptx) · [deck_theme_tech.json](deck_theme_tech.json)
- [FreePPT_麦肯锡风主题示例.pptx](FreePPT_麦肯锡风主题示例.pptx) · [deck_theme_mckinsey.json](deck_theme_mckinsey.json)
- [FreePPT_Stripe令牌主题示例.pptx](FreePPT_Stripe令牌主题示例.pptx) · [deck_theme_stripe.json](deck_theme_stripe.json)

## 报告与配图

| 产物 | 说明 |
|---|---|
| [FreePPT_经营分析报告示例.pptx](FreePPT_经营分析报告示例.pptx) · [deck_business_demo.json](deck_business_demo.json) | 8 页经营分析，结论式标题 + 数据 + 来源，走完内容把关与版面校验 |
| [咨询风示例.pptx](咨询风示例.pptx) · [demo.json](demo.json) | 最小可运行 deck |
| [咨询风全特性示例.pptx](咨询风全特性示例.pptx) · [deck_v2.json](deck_v2.json) | 10 类母版字段全覆盖 |
| [三通道配图示例.pptx](三通道配图示例.pptx) · [deck_v3.json](deck_v3.json) | 程序化矢量 / 授权网图 / 生成式通道的合规说明 |
| [web_manifest.json](web_manifest.json) | 网图素材清单（不是 deck，lint 时须排除） |
| [edits_example.json](edits_example.json) | `cli.py retext` 的编辑映射示例 |

## 纯 CLI 出片（无大模型、无联网）

```bash
python3 engine/cli.py make "本周完成 3 项交付；客户满意度提升到 92%" \
  --type weekly --out out.pptx --out-deck out.json
python3 engine/cli.py inspect old.pptx --out structure.json
python3 engine/cli.py patch out.json --set "slides.0.data.title=改后的标题" --build out2.pptx
```

## 边界

- 预览 PNG 由 `engine/debug_render.py` 用 Pillow 离线绘制，**不模拟 PowerPoint 的
  圆角、衬线字体渲染与动画**；真实效果以打开的 .pptx 为准。
- 动画/转场 XML 尚未在 Microsoft PowerPoint 中实测。
- 本页不声称任何视觉效果优于其他项目；横评方法见 `docs/BENCHMARK.md`。
