# 贡献主题 / 母版 / 构图原型

**作者：张三峯** ｜ 公众号：**AI龙卷风**

FreePPT 的视觉能力分三层，贡献入口不同：

| 层 | 注册处 | 影响范围 | 主要文件 |
|---|---|---|---|
| 主题（16 套） | `engine/themes.py` | 全局语义色、字体、圆角、行距、密度 | `themes.py`, `tests/test_themes.py` |
| 母版（10 套） | `engine/templates.py` | 结构稳定报告的页面骨架 | `templates.py`, `examples/deck_*.json` |
| 构图原型（12 种） | `engine/art_direction.py` | 创作类内容的逐页版式 | `art_direction.py`, `tests/test_art_direction.py` |

## 通用门槛

1. **一个稳定 id**：小写英文 + 连字符，不改已有 id；别名只增不删。
2. **每个值有来源**：原创设计决策要写明；引用的数值令牌要附 URL、许可证、
   SHA256 与映射理由（见 `references/design-token-sources.md`）。
3. **一套 lint 契约**：新增颜色必须进 `palette`；新增字号要满足 `min_body`；
   新增构图要能被 `LAYOUT_VARIETY` 与 `LAYOUT_REPETITION` 统计。
4. **一项单测**：至少覆盖「注册成功 + 自洽 + 可复现」。
5. **一份视觉证据**：构建出的 .pptx / PNG 预览，附在 PR 里。
6. **不降低闸门**：不得新增 `--skip-lint` 之类的绕行开关。

## 新增主题

`themes.py` 的 `_theme()` 需要：

- `semantic`：`surface_dark / surface_light / card_fill / ink / ink_on_dark /
  body / muted / line / accent / accent_2 / accent_soft`；
- `visual`：`latin / ea` 字体配对、`radius`、`shadow`、`line_spacing`、
  `chart_colors`、`accent_budget`、`density`、`grid_columns`；
- `palette`：所有允许出现的 hex；`PALETTE` lint 会拦任何越界颜色；
- `min_body`、`layout_min_chars`、`no_footer`：lint 契约键。

强制检查：

```bash
python3 engine/cli.py lint examples/deck_v2.json          # 零回归基线
python3 engine/cli.py lint examples/deck_theme_<new>.json
python3 -m unittest discover -s tests -q
```

企业风格主题只允许「风格化近似」：不得写入官方商标、Logo、完整 VI 色板，
`SKILL.md` 与 README 的边界说明必须同步保留。

## 新增母版

- 在 `templates.py` 增加展开函数，页面骨架复用固定几何，不引入自由浮动坐标。
- 在 `reports.py` 的 `section_plan()` 里声明它属于哪些报告类型的哪一节。
- 提供一份最小 `examples/deck_*.json`，`lint` 零错误。
- 若新增数据字段，同步 `reports._skeleton_data()` 与 `content_ai.check_content()`。

## 新增构图原型

`art_direction.py` 里：

1. 在 `ARCHETYPES` 注册函数与 id；
2. 在 `KIND_PREFS` / `DEFAULT_PREFS` 声明它适合哪些内容语义；
3. 在 `MIN_POINTS` 声明最少需要几个内容块（防止空格子）；
4. 所有几何用 `_t() / _rc() / _box() / _d()` 生成，文本高度按实测换行量算；
5. 派生主题色只用 `S[...]` 语义色，不写死 hex；
6. `tests/test_art_direction.py` 增加：确定性（同 seed 同 DSL）、相邻页不重复、
   内容块不足时不产生空卡片。

## 提交清单

- [ ] `CHANGELOG.md` 已更新
- [ ] `bash tools/check_all.sh` 通过
- [ ] 新增单测覆盖该能力与其失效路径
- [ ] 预览图 / pptx 已附
- [ ] 来源以 MLA 格式列出；SHA256 台账已更新
- [ ] 作者署名与双许可声明未被改动

## 不接受的贡献

- 复制其他产品 skill 的代码、提示词、素材或版式文件；
- 编造真实企业数据充当示例；
- 删除/隐匿 AI 生成内容标识的工具；
- 让 `build` 绕过 `lint` 的任何快捷方式。
