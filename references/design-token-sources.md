# 设计令牌借鉴来源与映射台账

本文件记录 FreePPT 从第三方开源设计文档借鉴的**公开数值**，以及每一步映射的依据。目的：让每个色值都可追溯，杜绝编造。

## 一、来源与许可（MLA）

VoltAgent. "Awesome DESIGN.md." *GitHub*, 2026, github.com/VoltAgent/awesome-design-md. Accessed 8 Nov. 2026.

VoltAgent. "stripe/DESIGN.md." *Awesome DESIGN.md*, raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/stripe/DESIGN.md. Accessed 8 Nov. 2026.

VoltAgent. "linear.app/DESIGN.md." *Awesome DESIGN.md*, raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/linear.app/DESIGN.md. Accessed 8 Nov. 2026.

VoltAgent. "vercel/DESIGN.md." *Awesome DESIGN.md*, raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/vercel/DESIGN.md. Accessed 8 Nov. 2026.

VoltAgent. "wired/DESIGN.md." *Awesome DESIGN.md*, raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/wired/DESIGN.md. Accessed 8 Nov. 2026.

VoltAgent. "ibm/DESIGN.md." *Awesome DESIGN.md*, raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/ibm/DESIGN.md. Accessed 8 Nov. 2026.

VoltAgent. "notion/DESIGN.md." *Awesome DESIGN.md*, raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/notion/DESIGN.md. Accessed 8 Nov. 2026.

仓库 README 的 License 段声明为 MIT，并说明：这些文档是从公开网站提取的设计系统文档，令牌代表公开可见的 CSS 值，仓库不主张对任何站点视觉识别的所有权，文档按「原样」提供。FreePPT 据此借鉴数值，且明确标注其非官方规范属性。

## 二、借鉴了什么、没借鉴什么

| 类别 | 处理 |
|---|---|
| 借鉴 | 6 份 DESIGN.md 的 YAML frontmatter 中的公开数值：色值 hex、圆角尺度、间距尺度、字号/行距层级；以及「语义角色 → 令牌键」的组织方法 |
| 未借鉴 | 上游代码、`preview.html`、文档正文全文、品牌 Logo、商标、文案、任何图像资产 |
| 自有实现 | `engine/design_md_import.py` 解析器、角色映射表、4 套主题定义、lint 契约、渲染逻辑 |

工程内**不存放原文**，只存抽取后的数值、来源键名、URL 与 SHA256（`references/imported/design_tokens.json`）。FreePPT 运行时不依赖该仓库，也不引用任何其他产品的 skill。

## 三、数据档案（2026-11-08 抓取）

| 源文件 | colors | rounded | spacing | type roles | SHA256 |
|---|---|---|---|---|---|
| stripe | 20 | 6 | 8 | 15 | `5c8806b7dd3e0c2554ccba9d1e2a7c78e7c6e50e44fcf6ff5daea6026f8a9ed9` |
| linear.app | 23 | 8 | 8 | 13 | `30bd30e72c48a16e4bdbd010f2d1c85fab657c6fae3cc85389399aab10f9cb5f` |
| vercel | 36 | 9 | 12 | 14 | `d0951b93c2b4ce9840c715c9f9b3e58a386c6c58ae5cc0f804dec3b116b95bd8` |
| wired | 9 | 2 | 9 | 14 | `eb439dcc573401dc30583f40e7eef8a60b769232da59e524de6dce56d5c3593e` |
| ibm | 21 | 7 | 8 | 13 | `46f6fd65b5e7524fed1133b9b3c0dd619f9a0f145fbb2b87f3675c701a88f3bd` |
| notion | 47 | 8 | 12 | 17 | `fa9d6e78216d8f3e5d3990709ca2de6bc2e268e945bb94f255fd1bfb15455266` |

`linear.app` 与 `notion` 已入档，但**未注册主题**：两者内容页为深色系统，而 FreePPT 当前骨架是「深色封面 + 浅色内容页」，强行套用会让浅色页文字不可读；等引擎支持全深色版式再接入。这是可验证的版面约束，不是数据缺失。

## 四、语义映射决策（4 套已注册主题）

完整 11 角色映射见 `references/imported/theme_mapping.json`；下表列出关键角色与尺度来源。

| 主题 id | 源键：surface_dark | ink | accent | 卡片圆角来源 |
|---|---|---|---|---|
| `stripe` | `brand-dark-900` #1C1E54 | `ink` #0D253D | `primary` #533AFD | `rounded.md` = 8px |
| `vercel` | `primary` #171717 | `ink` #171717 | `link` #0070F3 | `rounded.sm` = 6px |
| `wired` | `ink` #000000 | `ink` #000000 | `link` #057DBC | `rounded.none` = 0px |
| `ibm` | `inverse-canvas` #161616 | `ink` #161616 | `primary` #0F62FE | `rounded.sm` = 4px |

图表色同样取自源色值：stripe 用 `primary-soft` #665EFD，vercel 用 `hairline-strong` #A1A1A1，wired / ibm 直接复用语义角色色。`tests/test_design_md_import.py` 会断言每个 hex 都能在对应源文件的 colors 里找到，杜绝臆造。

## 五、FreePPT 侧判定（不声称来自数据）

- `line_spacing`、`density`、`accent_budget`、`shadow`：这些是 FreePPT 的排版护栏参数，由本工程按版面需要设定，不属于数据源字段。
- **字体**：源文档里的 `sohne-var` / `Geist` / `WiredDisplay` / `IBM Plex Sans` 多为专有或平台字体。OOXML 写入规则：stripe 与 vercel 用源文档明确提到的开源替代 Inter（stripe 文档在 Typography 段明确推荐 Inter）；ibm 用 IBM Plex Sans；wired 的展示衬线用 FreePPT 已有的 Songti SC / Georgia 回退栈。打开端缺字体时由 FreePPT 回退栈兜底。
- **衬线判定**：wired 的 `serif_heading=True` 依据源文档对窄体衬线展示字体的描述；具体字体名用回退栈，不复制专有字体。

## 六、边界

- 这些令牌是公开可见的 CSS 值，**不是品牌官方 VI 规范**；上游文档自身即标注为「受启发的设计语言分析」（例如 Stripe 的文件名是 `Stripi-Inspired-design-analysis`）。
- 4 套主题以品牌名作风格检索 id，不含任何商标或 Logo，与既有 6 套「企业风格主题」同一口径。
- 品牌改版会让数值漂移，本档案固定到 2026-11-08 抓取的 SHA256；后续更新需重跑导入器并重跑验收。
- FreePPT 保持独立原创：借鉴的是数值与组织方法，不是代码，也不构成对任何 PPT 产品或 skill 的依赖。

## 七、复现命令

```bash
# 1) 抓取 6 份源文件（示例）
curl -o /tmp/stripe.md https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/stripe/DESIGN.md

# 2) 重建数值档案
python3 engine/design_md_import.py /tmp/stripe.md /tmp/vercel.md /tmp/wired.md /tmp/ibm.md \
  /tmp/linear.app.md /tmp/notion.md --out references/imported/design_tokens.json

# 3) 复现某主题的语义映射
python3 engine/design_md_import.py /tmp/stripe.md \
  --mapping references/imported/theme_mapping.json --source-key stripe

# 4) 校验
python3 tests/test_design_md_import.py
```
