# Changelog

All notable changes to FreePPT are documented here. Dates use YYYY-MM-DD.
Version strings follow the project's date-based scheme (`YYYYMMDD[.n]`).

## [20261113.2] - 2026-11-13

**判据与渲染器对齐口径**，外加四页真实缺陷的引擎重写。

上一版（`.1`）把三条可读性判据挂上了交付路径，跑完 9 页验收却出现一件更糟的
事：**渲染图里明明有缺陷，`audit-design` 报 `ok=True`。** 这一版全部来自逐页
看图之后、回头查判据和引擎的四轮返工。

### 判据侧：三处「尺子和被量的东西不是同一把尺」

1. **行高读文件自己的 `line_spacing`**（`_text_boxes` / `_text_overflow` `_need_h`）。
   主题 magazine 渲染写 1.32，判据写死 1.28。两行 13.5pt 正文：46.07px vs
   47.51px，差 1.4px —— 正好让「正文底边 559.5 咬进批注块顶边 558」以
   `oy = +0.1` 逃过压字判据，那行字的下沿在渲染图里被切掉。
2. **容器门槛 `h >= 90` → `h >= 48`**。批注块 558×72 被门槛筛掉，而它恰好是
   溢出的那一块。72px 高完全托得住三行 16pt 文字，是标准容器尺寸不是装饰。
3. **压字补一条「按行高」口径**。原判只看重合面积比：正文最后一行咬进批注块
   1.5px、占该块文字面积 3.2%，面积判据天生看不见「切一条边」。补
   `bite = oy / line_h(size) >= 0.25` —— 咬进去够到字身的一部分就算压住。

三条各配回归测试，并**做了变异自证**：把 `h<48` 改回 `h<90`、
把行距改回写死 1.28，对应测试必挂（不挂的测试等于没写）。

### 引擎侧：四处「写死的高度」

四页缺陷同一个根因 —— **容器/位置写死，而 PowerPoint 不裁字**。

- **`a_editorial_spread`（p03）**：正文游标不知道批注块占了多高，一路写到底边。
  重写为「先量、再排版」：先算 lead / 标题 / 正文 / 批注各自实际行高，再按可用
  空间等比压缩间距（**保底 14px 不是 8px** —— rect 按 `LINE_FACTOR` 算，渲染按
  主题 `line_spacing`，差一行就会文字压文字）。批注块底边封顶 630（648 是页码行）。
- **`a_offset_triptych`（p05）**：卡片写死 340 高，内容少的页底部 40% 全空；
  编号写死偏移，`01` 底边 221 与卡片顶边 222 只差 1px，渲染图像被卡片切一刀。
  改为逐卡按内容算高（`2*card_pad + head + space_before + body`）、编号按**实测
  行高**定位。深色卡标题加自适应降字号（30 → 26 → 23），判定「一行」时宽度除以
  1.12 的保守系数 —— `_wrap_h` 对拼音估宽偏窄，`关系 guanxi 与报 bao` 被误判成
  一行，实际 Georgia 折两行，正文被挤出深色块。
  **卡片变矮之后又暴露一层**：三张卡只有 173 高，底边 433，而可用区到 608，
  页面下半空出 190px 比上半还空。补「整组外接框垂直居中」——居中对象是
  **外接框**不是每张卡，否则三张卡刻意错开的高低差会被抹平。
- **`a_stair_list`（p07）**：`short_h` 只按最窄一级算一次 + `step_rise` 写死 74，
  三个色块底部约 50% 空；`base_y` 写死 610，内容少时整组沉到页面下半部。
  改为 `_need_of(i)` 逐级按内容算、`min_rise=22` 保底递升；基线按
  `top_limit` / `foot_top` 自适应居中。
- **`--cover` 相对路径静默失效（p01）**：封面左侧 43% 空、书封图不出现、零报错。
  根因是 `compose()` 把非绝对路径按 notes 所在目录拼 → `examples/examples/...`
  → `os.path.exists` 判假 → `cover_file=None`。CLI 现在先解析成绝对路径，
  解析不到就打印 `WARNING`，不再无声丢封面。

### 验收

- 388 → 392 测试全绿
- 《人情与面子》9 页重新 compose → build → audit-design 全过，**逐页看渲染图
  复核**：p01 书封图已出现、p03 正文完整、p05 编号分离且标题一行、p07 贴合
  内容且居中

### 一条**没有**加的判据，以及为什么

p05「内容挤在上半页」是靠看图发现的，于是想给它加一条「垂直居中」判据。
在 8 份示例成品上实测了三种口径，全部放弃：

| 口径 | 反例 | 结论 |
|---|---|---|
| 内容底边 ≥ 某阈值 | 每份 deck 的封面底边都在 232（封面本就该写顶部） | 假阳性遍地 |
| 内部最大空洞 ≤ X | 正常页最大 78px，但空洞大小完全取决于版式 | 区分不出真缺陷 |
| 下方留白 / 上方留白 ≤ R | `FreePPT_Stripe令牌主题示例` p6 比值 4.76 | **成立的设计被误杀** |

第三条是决定性的：那张 `p06` 渲染图里，插图本身撑满了版面中部，下方留白是
**插图版式的结果**，不是「没做完」。给它加判据 = 让引擎只会做一种版式。

> **留白分布是风格，不是缺陷。** 判据只管「读不到」和「压住了」——溢出、压字、
> 出界、字体缺字形、没做版面。至于内容落在页面哪个高度、留白多不多，那是
> 设计师的判断，判据不该代替它。想让引擎做得更好，改引擎，别改判据。

## [20261113.1] - 2026-11-13

三条**可读性**判据：成品打开之后能不能读，不只是「版面像不像设计过」。

全部来自一次真实的端到端验收（《人情与面子》9 页中文 deck 走完
compose → build → 渲染 → 逐页看图），每一条都对应一张渲染图里的具体缺陷。

### 1. 文字溢出所在色块（`overflows`，硬拦）

PowerPoint 不裁切溢出文字，它会让字悄悄溢出色块、盖住别的东西。实测三处
症状不同、根因相同：

- 阶梯第 1 级正文 4 行，色块只放得下 3 行 → 末尾「演。」掉在色块外
- 批注块写死 58px、文字 max_h=44 → 第 3 行「原文逐字引用。」落在块外
- 1987 的说明标签写死 y=480，数字实际底边 482 → 说明压在数字下沿

判法：对每个大色块，把落在它内部的文字**聚合**后按各自字号算总占高，
与「色块高 − 2×8px」比。不能逐块文字找容器——一个色块里常有编号/标题/
正文三块文字，逐块判永远判不出「加起来放不下」。

### 2. 中文字体可用（`font_problems`，硬拦）

把参照 deck 的 `Georgia` / `Arial` 令牌直接搬到中文内容上，`a:ea` 指向没有
中文字形的西文字体 → 整本中文渲染成空方框。形状数、结构件、分隔线、压字
**全部正常**，所有原判据都查不出。这条只能主动读 XML 查字体名。

口径：只拦「确定没有中文字形」的字族；不认识的名字一律放行——判据不该因为
「我没见过这个字体」判死一份正常的 deck。

### 3. 实心色块压住文字（并入 `collisions`，硬拦）

比「文字压文字」更隐蔽：文字还在文件里，只是被盖住看不见。实测批注块底边
636 压住 648 处的页码，渲染图里「03 / 09」被吃掉一半。

判法用**重合比例**（<85% 才算压住）。两头都试过：完全包含太严（文字框常
刻意比色块多 2px 贴视觉边距，正常产物被误伤）；只看中心太松（页码整体被
吞掉时中心正好在块内，漏判）。

### 顺带修掉的引擎缺陷

- `offset-triptych`：编号硬编码在卡片上方 46px 处，标题两行时编号压进标题；
  卡片固定 380px 高，第二块底边到 634 会压住 626 的批注行。改为按标题实际
  底边推导编号位置、卡片压到 340。**lint 的 `GEOMETRY_OVERLAP` 是对的，
  引擎是错的。**
- `stair-list`：第一级高度写死 156px。改为按「最窄那一级正文能折几行」算。
- `editorial-spread`：批注块写死 58px。改为按文字实际高度撑开，底边封顶 630
  （再低就压住 648 的页码）。
- `quote-bleed`：引言下划线两版都穿过最后一行（rect 底边 ±34/+26 都试过，
  LibreOffice 与 PowerPoint 的 44pt 行盒都比几何估算高）。改成放在引言
  **上方**——同一条线，位置一改，从缺陷变成「引言的起手式」。
- `data-focus`：说明标签位置由数字**实际**底边推出，不再写死 480。

### 验收

- 382 → 384 测试，`selfcheck` 全过
- 《人情与面子》9 页 9 种版式，compose → build → audit-design 三环全过
- 变异自证：`a:ea=Arial` 被拦；色块压页码被拦；文字塞不下的最小样本被拦
- 渲染侧：LibreOffice 缺中文字形会导致**看起来像**豆腐块，但 pptx 本身是对的
  （PDF 文字可正常抽取）。已在 `~/Library/Application Support/LibreOffice/4/user/fonts/`
  放思源黑体解决本地预览

### 补上「逐页设计」缺的可对照实例

修判据的时候发现一个更基础的问题：**仓库里原来一份 `design_briefs` 都没有。**
`compose` 缺简报会报错，但没人能看见「合格的一份长什么样」，于是首要规则只能
靠读文字理解。补：

- **`examples/briefs_renqing_mianzi.json`（新）** — 《人情与面子》9 页 9 份六维
  简报，每页 `structure` / `rationale` 都不一样，可直接对照。
- **`examples/notes_renqing_mianzi.json`** — 补上 `design_system` 令牌（来自参照
  deck 实测：`9A3412/1E3A5F/1C1917/FAF7F2/E7D8C9/C8A27C`、字号 33/24/16/13.5）。
- **`examples/deck_notes_composed.json`** — 用新链路重新生成，从 9 条
  `DESIGN_SPEC_MISSING` 恢复到 0 blocker。旧文件是 `design_brief` 机制出现前的
  快照，lint 已判死，但 SKILL.md / references/dsl.md 还拿它当示例，属于文档在教
  一条走不通的路。

**踩到的坑，已写测试钉住**：`--briefs` 把整个 JSON 当映射交给 `_resolve_brief`，
只认 `"0"` / `0` / page id。我第一版写成 `{"design_briefs": {...}}` 包一层，
结果 **compose 成功、页数正确、九页设计全部静默回退到原型池**。`test_design_spec.py
::TestBriefsFileShape` 三条测试钉住：扁平能解析、包一层返回 None（不抛错，所以危险）、
仓库里那份示例必须扁平且九页齐全。

### 修掉 `tools/check_all.sh`

第 3 步 `compose` 不带 `--briefs`，被自己的闸门拦死，本地全量检查长期 `rc=1`。
不是引擎的 bug，是脚本没跟上闸门。同时把 `briefs_*.json` 加进第 2 步的跳过列表
（它不是 deck，lint 会 `KeyError: 'slides'`）。

### 明确 `seven_habits_deck.py` 的边界

610 行、184 处硬编码坐标、零 `design_spec` 调用。它是**判据基准**（证明参照语法
那种密度真能判过），**不是交付路径的样例**。已在 SKILL.md 写明「学逐页设计看
`briefs_renqing_mianzi.json`，看判据水平看 `seven_habits_deck.py`」，并加测试
钉住这个性质。

384 → 387 测试。

## [20261112.11] - 2026-11-13

Put the finished-file audit **on the delivery path**, and fix two false
positives that would have made it worthless.

Two independent root causes were found behind "the generated deck still ignores
the skill":

1. **Three stale `FreePPT` copies shadowed the new one.** `~/.workbuddy/skills/`
   held `freeppt` (`.10`) plus `freeppt.bak-20261112_140539` (`.7`),
   `…_144521` (`.8`) and `…_232805` (`.9`). All four declared
   `display_name: "FreePPT"`, so `@skill:FreePPT` was an ambiguous match and
   could load a copy that **has no `design_spec.py` at all** — i.e. no six-
   dimension gate, no matter what the current version says. The three stale
   copies are gone (moved to the system trash, recoverable).
2. **`audit-design` had zero automatic trigger points.** `lint_deck()` reads
   the DSL only; a model that hand-writes `python-pptx` or drives a build
   script ships a deck that nobody ever audited. A judge with no call site is
   documentation, not a constraint.

- **`build` now runs `audit_design()` on the file it just wrote** and exits 1
  when the deck does not hold up, printing the concrete defects. Verified end
  to end: a 12-slide deck reusing one template 10 times is rejected with
  `10 页共用同一副骨架（上限 4）`; the official business example passes.
- **Density split into defect vs. style.** The old thresholds killed
  `examples/deck_business_demo.json` — an 8-page native-chart report that is
  visually sound — because a page built around one large chart has only 9
  shapes. Verdict: *a judge that fails good work is worse than no judge.* So:
  - **hard (block)**: `bare_floor_pages` — fewer than 2 structural elements
    (plain text stacking); `thin_floor_pages` — fewer than 4 shapes; plus text
    collisions, out-of-bounds text, skeleton reuse, and zero dividers.
  - **advisory (report only)**: `thin_pages` / `bare_pages` — density below the
    reference's dense-editorial style. That is a style choice, not a defect.
- **Native charts and tables now count as structural elements.** A chart that
  fills the page *is* the layout; excluding it made "title + big chart + source
  line" read as "structure = 0, no design done".
- **Ceremonial pages (cover / closing) are exempt from density**, identified by
  a **giant title** (`≥28pt` + ≤5 text blocks) — not by "few characters". Using
  character count alone let a bare 4-block body page through, turning the
  exemption into a backdoor.
- **`_text_boxes()` estimates height per paragraph, by that paragraph's own
  font size.** The old code took the first run's size for the whole block, so a
  cover figure `+23%\n收入同比增速` (60pt + 13.5pt) was measured as 60pt ×
  both lines = 205px instead of 98px and reported as out of bounds. Real height
  was inside the page; the judge was wrong.
- Tests: 362 → 365. New `TestDensityIsAdvisoryNotFatal` (chart deck passes,
  bare text still rejected, ceremonial needs a big title). `selfcheck` stays
  16/16.

## [20261112.10] - 2026-11-12

Turn "the model is the page designer" from prose into an **enforced gate**. The
trigger was an audit finding: `engine/design_brief.py` existed with five
fields, but `check_deck()` had **zero call sites in the entire repo** — a judge
nobody calls is documentation, not a constraint.

- **`engine/design_spec.py` (new, replaces `design_brief.py`)** — the per-page
  design plan is now **six dimensions**, each with a quality floor, not just a
  presence check:

  | dimension | field | floor |
  |---|---|---|
  | layout structure | `structure` | non-placeholder, ≤3 pages may share a tag |
  | visual hierarchy | `hierarchy` | ≥8 chars **and** must name levels |
  | component breakdown | `components` | ≥2 items, each with `name`+`role` |
  | interaction states | `states` | non-empty |
  | responsive | `responsive` | ≥6 chars **and** must state a real strategy |
  | accessibility | `a11y` | ≥2 of contrast / text_size / alt |
  | consistency | `consistency` | must reference tokens that exist in `design_system` |

  Plus `rationale` (≥12 chars) as the self-justification.

- **Deck-level token lock** — `design_system` must be declared once at the top
  of the notes with `palette` / `type_scale` / `spacing` / `font_pair`. Pages
  may only *reference* those keys. This is the machine-checkable form of
  "every page shares one design language".
- **Three-ring closure** — design (`design_briefs`) → deliver (`compose()`
  calls `require_deck()`, missing any dimension raises `ValueError`) → verify
  (`lint` re-checks six dimensions so hand-written DSL cannot bypass;
  `verify_spec_compiled()` reads the finished pptx and checks that the
  component count declared is actually present on the page). No `--force`.
- **Wired for real** — `art_direction.compose()` and `lint.lint_deck()` both
  import `design_spec` now. `DESIGN_BRIEF_MISSING` becomes
  `DESIGN_SPEC_MISSING`; `without_brief` becomes `without_spec`.
- **Mutation-proven** — `tests/test_design_spec.py` drops each of the eight
  fields one at a time and asserts the gate goes red, so no dimension can be
  decorative. 23 new tests; **362 tests + 24 subtests pass**.
- **Honest note** — hooking the stricter gate immediately turned four tests in
  `test_design_brief_gate.py` red because they used the old five-field shape.
  Per this very rule, the fix was to upgrade the fixtures, not loosen the gate.
- **`SKILL.md`** — new first section "首要执行规则：逐页设计、逐页交付、
  逐页校验", explicitly declaring priority over all other general advice and
  giving the minimal working example.

## [20261112.9] - 2026-11-12

The reference grammar only existed as a 5-page selfcheck sample. This release
uses it to build a **complete 10-page reading-notes deck**, and in doing so
finds that the text-extent estimator from .8 was too crude — it counted every
ASCII letter, digit and space as a full-width CJK glyph, so the golden
reference itself was judged as 3 collisions + 5 clips. A gate that fails the
target it is supposed to chase has no authority, so the estimator was fixed
before anything else.

- **`engine/design_audit.py` — weighted text-extent estimate.** Each character
  now contributes its real width via Unicode East Asian Width: W/F glyphs 1.0
  em, alphanumerics ~0.56, spaces 0.30; manual newlines (`\n`) wrap separately.
  After the fix the reference deck audits **0 collisions / 0 clips**. This is
  the calibration rule: the judge must pass the golden standard.
- **`engine/seven_habits_deck.py` (new) — full 10-page deck builder.** Every
  coordinate comes from shape-level measurement of the reference (canvas
  1280×720). Four layouts, ten distinct left-side visual arguments (cover
  stairs, framework bands, concentric circles, two-creation bands, 2×2
  quadrants, win-win split + emotional bank account, listen/express blocks,
  1+1>2 trust columns, four-dimension grid, four-week landing table) — no two
  content pages share a skeleton. Reuses the same primitives as the audit so
  judge and output stay one vocabulary.
- **Real bugs it caught:** P6/P7 used a 130px section-label box that ran into
  body text starting at x=200; narrowed to the reference's 110px. Caught by
  `collisions`, confirmed by `preview` — the render loop earned its place.
- **`tests/test_seven_habits_deck.py` (new)** — 3 tests: ten slides, audit
  `ok` with no collisions/clips, every page has ≥10 shapes and ≥1 divider.
- **Verification:** 339 tests + 24 subtests pass; selfcheck 14/14. Delivered
  `artifacts/七个习惯_精读10页.pptx` with per-page PNGs in
  `artifacts/preview10/`.

## [20261112.8] - 2026-11-12

The user handed over a 10-page reference deck and said: **"page design is the
core, notes are optional, you're being dumb."** Measuring it overturned my
whole direction — the reference has **zero images**. So the image-density chase
was wrong. This release builds the design audit around what actually makes that
deck good, then immediately catches its own bugs with it.

- **`engine/design_audit.py`** — `audit_design(pptx_path)`. Judges four things,
  none of them images: page chrome (header rule / footer source line / page
  badge), structure density (≥20 shapes, ≥7 non-text structures per page),
  dividers (≥50% of pages), and argument variety (no skeleton on >4 pages).
  Calibrated on the reference: 38.7 shapes/page, 45 dividers over 100% of
  pages, max 2 pages sharing a skeleton.
- **Text collisions and clipping** — added after the reference-grammar sample
  passed L1–L6 and *still looked broken on screen*: titles sitting on ledes,
  band labels merged with their descriptions, `/ 05` half off-canvas. Both are
  now first-class judgements (`collisions`, `clipped`), computed from estimated
  real text extents (font size × line count), not `shape.height` — PowerPoint
  does not clip overflowing text, so box height misses that whole class.
- **`engine/cli.py`** — new `preview` subcommand: pptx → one PNG per page via
  LibreOffice + PyMuPDF. The check geometry cannot do is "does it look right".
- **`build_reference_sample()`** — the reference grammar as executable code:
  chrome, 34×34 badges, 118×30 label bars, 8px ticks, full-width rules, and
  five pages with five genuinely different visual arguments (staircase,
  progress bands, concentric rings, 2×2 matrix, horizontal bars). `selfcheck`
  builds it and requires `audit_design` to pass it, so the thresholds and the
  vocabulary cannot drift apart.
- **`audit_notes` gains a template judge** — head-8/tail-12 repetition >25% is
  a template, not a script. This at last fails my own `fill_notes()` output
  (100% identical 12-char endings across 91 pages) instead of passing it with
  100% coverage. `fill_notes_from_file()` is the real path: the model writes
  each page's script, the engine only writes it in.
- **Layout implementation rules** learned the hard way, now in `SKILL.md`:
  stack text by `_line_h(size)` never by hard-coded offsets; 33pt Chinese is
  ~55px tall, not 40; no `↑ →` glyphs (Arial drops them); no rotated text boxes
  for axis labels (rotation pivots on centre and spills into the next column).

## [20261112.7] - 2026-11-12

Close the last measured hard gap: **speaker notes 0/91**. Notes now have a
product-side judge and a product-side fixer, on the same principle as
`audit-pptx` — a gate that only reads the DSL is inert the moment someone
writes the pptx by hand.

- **`engine/pptx_notes.py`** — `audit_notes(pptx_path)`. Reads only
  `has_notes_slide` and `notes_text_frame.text`. Coverage plus per-page
  thinness. The tier (*essay / standard / research*) is **inferred from the
  deck's own mean note length** (≤70 / 70–180 / ≥180), then the floor of that
  tier decides what counts as thin — so a 20-character quote deck is not
  failed for being short, and a 60-character page inside a research deck is.
  Thresholds come from the 12 Doubao samples (essay mean 25.3, standard
  99–150, research 227.8/252.9). Ritual pages (≤24 visible chars) exempt.
- **`engine/pptx_notes_fill.py`** — `fill_notes(...)`. Re-organises only the
  text already on each page: no new facts, no invented numbers. Idempotent
  (pages with existing notes are skipped unless `overwrite=True`) and
  deterministic (two runs on the same input are byte-identical).
  - `_NOISE_RE` filters chapter numbers, page numbers and all-caps running
    heads (`02`, `P26`, `26 / 91`, `MODULE 04 / THE LEAP`) out of title
    detection — without it a chapter page's note began "这一页讲的是 02".
  - Dedup covers three shapes: mutual containment, prefix relation, and
    identical first 12 characters. The prefix case is what happens when one
    sentence is split across two text boxes of different widths.
  - Bodies are whitespace-normalised before quoting (page text carries hard
    wraps like `英伟\n达`) and get terminal punctuation, so blocks to not run
    together into one unbroken sentence.
- **`engine/cli.py`** — `audit-notes` (`--json`, exit 0/1) and `fill-notes`
  (`--out`, `--overwrite`). `selfcheck` extended 8 → 11 checks: the 12-page
  hand-written deck from the existing `audit-pptx` check is now also passed to
  `audit-notes` (must fail at 0 notes), then to `fill-notes` (must reach 100%),
  then to `fill-notes` again (must fill 0 pages — idempotency).
- **`tests/test_pptx_notes.py`** — 19 tests. Verified by mutation: deleting the
  dedup, forcing a flat 40-character cutoff, disabling the ritual exemption,
  and removing the noise filter each turn the suite red.
- Measured on the real deck: `0/91 → 91/91`, coverage 100%, mean 202.6 chars,
  0 thin pages, tier auto-selected as research. Idempotent re-run fills 0
  pages; a second run from the same input is byte-identical.
- SKILL.md redlines #11/#12 and #27 updated from "最大未补缺口" to the closed
  state, with the one-punch-and-one-fill commands documented next to
  `audit-pptx`.

## [20261112.6] - 2026-11-12

Write the acceptance bar into the top of SKILL.md, so "did we drift" is
answerable from the file instead of from memory. Two new sections sit above the
existing 创作第一性原理 and directly after it.

- **最高目标与裁决规则** — states the single goal (成品效果追赶豆包) and the
  meta-rule that decides conflicts: offline, determinism, engine-generated, and
  architectural purity are means, not constraints, and must never be escalated
  into a decision the user has to make.
- **交付自检红线** — 27 things it should be plus 21 things it should not be,
  each with a checkable criterion rather than an adjective:
  - 应该 (27): per-page carrier decision, skeleton ≤4 pages per shape, content
    density 144–360 chars/page, notes ≈100%, editable ratio >0.95, native
    charts, dual typeface, size tiers, function-colour consistency, gradient on
    demand, chapter breathers, sources printed visibly, plus 7 process items.
  - 不应该 (21): fixed-template-fill, same layout for different content,
    image-on-every-page, per-chapter layout reuse, relabelling to fool gates,
    hand-written pptx bypassing `compose()`, doc-only fixes, `--force` instead
    of a real fix, and an explicit "not a template library / not a screenshot
    tool" positioning block.
- Every claim in the tables is tied to measured data where one exists, and the
  two known gaps are written in rather than hidden: **notes coverage 0/91** and
  **1 image vs a Doubao median of 5**.

Verified: backup `SKILL.md.bak-20261112_130918` (418 lines) compared against the
new file — 16 → 18 `##` headings (2 added, 0 lost), 66 → 66 table rows
(0 lost), +104 lines.

## [20261112.5] - 2026-11-12

Remove the enforced-offline constraint. It was never a capability requirement;
it was a self-imposed limit, and it contradicted the top-level goal of matching
frontier deck quality. If a network call, a model call, or an external service
makes a page land better, it should be used.

The constraint had one real enforcement point, not just prose:

```python
# tests/test_open_source_tooling.py, before
self.assertEqual(benchmark.offline_readiness()["core_pipeline_network_hits"], 0)
```

Any network call added anywhere in `engine/` turned the suite red. Verified
before/after by appending a `urllib.request` probe to `engine/layout.py`:

| | probe injected into `engine/layout.py` |
|---|---|
| before | `FAILED (failures=1)` — `AssertionError: 1 != 0` |
| after | `OK`, 25 tests pass |

- `tools/benchmark.py`: `offline_readiness()` → `network_usage()`. Drops
  `core_pipeline_network_hits` and the "zero network calls" promise; keeps the
  scan as a reported number with `"Informational only. No gate depends on this
  number"`. Report field `offline` → `network_usage`.
- `tests/test_open_source_tooling.py`: the zero-network assertion is replaced by
  a guard asserting the field is *gone* (`assertNotIn`), so nobody reintroduces
  it by accident.
- Docs de-positioned from "offline is our feature" to plain description:
  `SKILL.md` (description, 职责边界, 适用范围, 图标库, 讲稿, 验收, Step 2/6),
  `README.md`, `README.en.md`, `references/architecture.md`, `references/dsl.md`,
  `references/dsl-spec.md`, `docs/FREEFORM_PLAYBOOK.md`, `docs/BENCHMARK.md`,
  `docs/GAP_ASSESSMENT.md`, `docs/PUBLISHING.md`, `examples/GALLERY.md`,
  `install.sh`, and module docstrings in `art_direction`, `compiler`,
  `design_system`, `cover_style`, `icons`, `brief_fill`, `debug_render`, `cli`.
- `SKILL.md` 职责边界 now states the replacement principle explicitly: 载体需要
  什么手段就用什么手段；网络和外部服务都不是禁区，唯一标准是这页表达是否更有效。

Deliberately kept, because deleting them would be wrong rather than liberating:

- `engine/web_search.py --offline` — a functional flag that parses a recorded
  JSON instead of issuing HTTP. Renaming it would break the CLI.
- "offline tests" in test docstrings — these describe tests that need no network,
  which is a test-quality property, not a product constraint.
- `CHANGELOG.md` history — past entries are records, not claims to retract.

305 tests OK after the change.

## [20261112.4] - 2026-11-12

Close the largest remaining hole in the per-page design gates: they all lived on
the DSL, so any deck written by hand-rolled Python passed untouched. The real
122-page "consultative selling" delivery that motivated these gates was produced
exactly that way — 1011 lines of `lib.py`, 22 `p_*` page functions, every
`design_brief` empty — and not one gate ever ran.

- New `engine/pptx_audit.py`: audits a *finished* `.pptx`. Reads only
  `rect_px` coordinates via `pptx_edit.inspect()`, never the DSL and never a
  self-reported `archetype`, so it applies equally to hand-written decks. Reuses
  `layout_fingerprint.skeleton()` so the criterion and threshold stay identical
  to the DSL side (single skeleton ≥5 pages fails; very-low-text pages exempt as
  cover/chapter/closing).
- New `cli.py audit-pptx <file.pptx> [--max-pages 5] [--json]`: prints the
  offending page groups, exits 0/1 so it can gate CI.
- `selfcheck` extended from 7 to 8 checks: it now writes a real 12-page uniform
  pptx to disk with python-pptx and runs `audit-pptx` against it, so the
  bypass path is verified end-to-end rather than described.
- Measured contrast on real files: 122-page failing deck → `不通过`, 9 groups
  (12/11/11/8/8/7/7/7/5 pages); 111-page healthy deck → `通过`. No false
  positive on the healthy output.
- New `tests/test_pptx_audit.py` (10 tests): hand-written decks caught, relabeling
  cannot save them, 4 pages pass / 5 pages fail, ritual pages exempt, content
  pages not exempt, unreadable shapes counted rather than silently dropped.

## [20261112.3] - 2026-11-12

Add `cli.py selfcheck`, so the gates can be verified without trusting anyone's
report. Documentation can describe a gate that does not actually fire; this
command builds a bad sample and runs it through the real code path.

- New `selfcheck` subcommand: generates a 122-page uniform deck whose pages
  each claim a *different* archetype name and carry no design brief, runs
  `lint_deck` on it, and asserts it is rejected with both
  `DESIGN_BRIEF_MISSING` and `LAYOUT_SKELETON_REPEAT`. It also confirms that
  relabelling does not hide identical geometry, that placeholder values
  ("无" / "TBD" / "同上") count as unfilled, that normal composed output is
  *not* falsely rejected, and that `compose()` refuses to run without briefs.
- Exit code is 1 when any check fails, so it works in CI. Verified that
  removing the skeleton gate on a copy makes it report `[FAIL]` — the check
  is not decorative.
- `SKILL.md` documents the command under the gate table with the rationale:
  a gate that cannot reject a deliberately bad sample is not a gate.

## [20261112.2] - 2026-11-12

Turn the per-page design principle into a **compile-time gate**. The previous
release made `design_briefs` *possible*; it was still an optional argument, so a
deck could be produced straight from the archetype pool without anyone judging
each page. That is exactly the "pick a template and pour content into it"
pattern the first principle rejects. This release makes it impossible.

- `engine/art_direction.py`: `compose()` now **raises ValueError** when no
  `design_briefs` are supplied. Two legitimate exits: pass briefs, or declare
  `"brief_pool": "prototype"` on the notes to explicitly accept the pool
  fallback (recorded on the deck; lint reports `BRIEF_POOL_FALLBACK`).
- New `engine/design_brief.py`: brief completeness gate. Every composed page
  must carry `carrier` / `structure` / `visual_anchor` / `image_decision` /
  `rationale`, each non-empty, non-placeholder ("无" / "TBD" / "同上" rejected)
  and above a floor length. `image_decision` must be a known value. Violations
  raise `DESIGN_BRIEF_MISSING` (blocker). A single `structure` label reused on
  more than 3 pages raises `STRUCTURE_REUSED` (blocker) — reusing one answer
  across many pages means the pages were not judged individually.
- New `engine/layout_fingerprint.py`: geometric skeleton fallback. Reads
  coordinates only — **never the self-reported `archetype`** — because testing
  showed relabelling 12 identical pages with 12 different archetype names left
  the old gate at `ok=True`. Single skeleton appearing on >=5 pages raises
  `LAYOUT_SKELETON_REPEAT` (blocker). Ritual pages (cover / chapter / closing)
  are exempt: eleven chapter openers looking alike is correct design.
- Threshold calibrated on real output, not guessed: a healthy deck's largest
  same-skeleton group is 4 pages; the failing 122-page sample had 11 / 8 / 8 /
  7 / 7. A skeleton-density ratio was tried first and **rejected by the data**
  (healthy 3.2 pages/skeleton vs failing 2.87 — indistinguishable), so the
  absolute group size is used instead.
- `engine/lint.py`: both new codes registered as blockers, therefore not
  `lint_ack`-able; blockers must be fixed at the source.
- New `tests/test_design_brief_gate.py` (16 cases), including the regression
  anchor `TestRealWorldTemplateDeckRejected`, which rebuilds the structure of
  the real 122-page failing deck and asserts it is rejected. Loosening any gate
  later turns this test red instead of shipping a bad deck.
- Verification on real artifacts: the failing 122-page deck now returns
  `ok=False` with 130 blockers (122 missing briefs + 8 skeleton repeats);
  normal composed output still passes `ok=True`.
- Archetype-pool tests (`test_art_direction`, `test_long_deck_guard`,
  `test_visual_primitives`, `test_repo_portability`) declare
  `brief_pool="prototype"` — they exercise the pool, not per-page judgement.
  Full suite: 295 tests pass.

## [20261112.1] - 2026-11-12

Make the "model as per-page designer" first principle executable in the
generation pipeline, not just documentation.

- `engine/art_direction.py`: `compose()` now accepts `design_briefs` (dict keyed
  by page index / id). Each brief may pin an archetype or mark the page
  `__host__` (engine emits an empty placeholder; host renders it, e.g. a
  hand-authored SVG like the module-〇 pages). Briefs carry `carrier` /
  `structure` / `visual_anchor` / `image_decision` / `rationale`, recorded
  verbatim onto each slide's `design_brief` field for auditability. Pages
  without a brief keep the deterministic archetype-pool plan (backward
  compatible). CLI `compose` gains `--brief <json>`.
- SKILL.md: generation flow now requires the host model to write per-page
  `design_briefs` BEFORE `compose()` for creative decks; the 17-archetype pool
  is explicitly the fallback, not the starting point. This closes the gap where
  the principle lived in docs but the engine still auto-assigned layouts
  (the audit finding on the 111-page ABC deck).
- Tests: add `TestDesignBriefs` (pin / `__host__` placeholder / no-brief default).

## [20261111.3] - 2026-11-12

Reconcile the offline claim with the "model as designer" first principle. The
blanket "全程离线、不调用大模型、不联网" wording is replaced with a mode-aware
statement: the engine/CLI path is offline & deterministic when there is no AI
host; when driven by a host LLM, the per-page design decisions are made by the
model (see 创作第一性原理). Scoped the remaining occurrences in SKILL.md and
README.md. Version bump only; no engine behavior change.

## [20261111.2] - 2026-11-11

Model-driven design-system extraction from a reference image. The engine stays
offline but now makes the host model's "designer" judgment repeatable: a
scaffolded Design System Card forces six visual dimensions (color climate, tone,
typography, layout, shape language, motifs) each answered with evidence and a
confidence label, then maps the result to reusable theme tokens and spec_lock
roles. A validator reports unfilled fields (exit 1) but never invents answers;
a user-approval gate must pass before the system is applied deck-wide.

### Added

- `engine/design_system.py`: `scaffold()` / `validate()` with the six
  dimensions and reuse mapping; stdlib only, deterministic.
- CLI: new `design-system` subcommand
  (`design-system scaffold <ref>` / `design-system validate <card>`).
- `SKILL.md`: new "参考图 → 设计系统（模型驱动）" section, task-routing row
  and toolchain examples, including honest limits (font name cannot be read
  off the image; copyrighted decoration is redrawn, not copied).

## [20261111.1] - 2026-11-11

Authoring philosophy: elevate "the model acts as each page's designer" to the
top-level creative first principle. The carrier (AI art / real photo / native
SVG / pure-typography layout / data visualization, or a mix) is the result of
reading and understanding the page — not a preset. What stays uniform is the
aesthetic language and quality floor; what varies is per-page structure. The
17 layout archetypes, layout ledger and concept→graphic map are reframed as a
component library and bottom-line guard, not the starting point. Docs-only; no
engine behavior changes.

### Added

- `SKILL.md`: new "创作第一性原理（最高准则）" section, including carrier
  cost-ranking (native SVG for simple concepts, real web photos for real
  entities, bespoke AI art only for abstract/atmospheric concepts) and an
  explicit responsibility boundary — the engine stays offline/deterministic;
  the per-page "designer" judgment is performed by the host model.

### Changed

- `SKILL.md` task routing: the "成品级效果" path now leads with per-page
  designer judgment; the ledger is a fallback hard gate.
- `SKILL.md` "创作式编排": the 17-archetype auto-assignment is described as
  the high-quality engine fallback when there is no page-by-page design.

## [20261110.1] - 2026-11-10

Layout ledger: a coordinate-free hard gate that makes "every page uses a
distinct layout" enforceable for long data-driven projects (family × chrome
systems). Additive — no existing command changes behavior.

### Added

- `engine/layout_ledger.py`: `validate(ledger)` / `validate_file(path)` with
  three rules — globally unique `layout_id`, adjacent generic pages differ in
  both family and chrome, and repeated families stay `family_gap` real page
  numbers apart. Special pages (cover/chapter/quote/custom data) participate
  only in uniqueness. Geometry-independent: the ledger alone stops cyclic
  layout rotation.
- CLI: new `ledger` subcommand (`cli.py ledger layout_ledger.json`), exits 1
  with the full error list when the gate fails.
- `tests/test_layout_ledger.py`: 7 cases covering clean ledger, duplicate id,
  adjacent same family/chrome, family gap, special-page exclusion and missing
  id.
- `docs/PIPELINE_CONTRACT.md` §8: ledger JSON contract and the gate's place
  in the QA stage.

### Changed

- `engine/pptmaster_bridge.py`: `_run_script` now captures `SystemExit` and
  returns the script's real exit code (restoring `sys.argv` afterwards), so
  strict quality gates are no longer swallowed as success.
- `cli.py compile-svg`: blocks compilation when the quality checker returns a
  non-zero exit code (`COMPILE-SVG BLOCKED: quality gate failed`).
- Verified against the NVIDIA 91-page ledger: `ok=true`, total 91, 78 generic
  + 13 special, 24 families each appearing 3–4 times.

## [20261109.3] - 2026-11-09

SVG fusion pipeline: FreePPT planning/guards + ppt-master native DrawingML
compilation. Additive and opt-in — every new flag defaults off, so existing
commands stay byte-identical. Contract: `docs/PIPELINE_CONTRACT.md`.

### Added

- `engine/page_spec.py`: turns the coordinate-free `(notes, archetype plan)`
  into a Deck Plan / Page Spec (`build_deck_plan`), the single handoff between
  planning and the SVG authoring layer. Covers explicit points, compare pages,
  native charts, single KPIs and timelines.
- `engine/pptmaster_bridge.py`: locates an external ppt-master install
  (`~/.workbuddy/skills/ppt-master`, overridable via `FREEPPT_PPTMASTER`),
  patches the `pathlib.Path.mkdir(exist_ok=True)` platform bug at runtime
  without touching ppt-master source, and chains its quality checker and
  compiler.
- CLI: `compose --emit-plan plan.json`, plus new `svgguard` and
  `compile-svg` subcommands (`--strict` canonical/final gate,
  `--skip-quality`).
- `docs/PIPELINE_CONTRACT.md`: four-layer architecture, coordinate-free
  field contract, capacity/density single source of truth, QA hard gates.

### Changed

- `SKILL.md`: task routing leads with the SVG fusion pipeline for
  benchmark-grade output; new modules registered.

## [20261109.2] - 2026-11-09

Text-quality gate and design-grammar elasticity, distilled from the fifth
benchmark round (12 more external decks, 23 total). Additive and compatible:
the three new diagnostics are advisory/info tier, `--strict` now passes
info-only warnings, and the suite grows from 236 to 251.

### Added — text-quality gate (`engine/lint.py`)

- `TYPO_FOUND` (advisory): deterministic Chinese typo pairs (登陆/登录,
  帐户/账户, ...) found in on-stage text.
- `TEXT_DUP` (advisory): the same >= 10-char sentence recurring on two
  different slides — a copy-paste slip, not a stylistic echo.
- `FACT_UNSOURCED` (info): a fact-like statement (figures, years, shares,
  ranks) on a slide without a `sources`/`source` record. Info tier by design:
  the engine nudges, never verifies.
- `verify --strict` now exits 2 only for remaining advisory warnings;
  info-level measurements pass (they are not defects).

### Changed — design grammar (`docs/DESIGN_GRAMMAR.md`)

- The six "iron rules" from the 11-deck benchmark are downgraded to "design
  tendencies with exception conditions" after 6 counterexamples in the 12
  new decks: semantic font layering (up to 4 fonts in 2 systems), all-serif
  decks, short-form speaker notes (25.3 chars/slide), 99% notes coverage,
  144-360 chars/page density range, and 0-image decks.

## [20261109.1] - 2026-11-09

Three-tier lint severity with human adjudication, plus the long-form craft
documentation distilled from an 11-deck / 9-thread external benchmark. Purely
additive: `ok`, `errors` and `warnings` keep their historical meaning, the
default pipeline is byte-identical, and the suite grows from 222 to 236.

### Added — lint severity tiers and adjudication (`engine/lint.py`)

- Every diagnostic now carries a `severity`: `blocker` (hard defect, build
  refused), `advisory` (detector suspicion needing a human call), `info`
  (measurement, no action). `blocking_codes` names the codes that can never be
  suppressed; any other warning defaults to advisory, so a newly added check
  is adjudicable without touching the table.
- `lint_ack` — a deck-level list of `{code, slide?, reason}` records that
  adjudicate a specific advisory as intentional. Three constraints keep it an
  adjudication rather than a mute button: `reason` is mandatory
  (`LINT_ACK_INVALID`), blockers are refused (`LINT_ACK_ON_BLOCKER`), and a
  record that matches nothing surfaces as `LINT_ACK_UNUSED` so stale
  adjudications cannot accumulate silently. Matching is per-slide when `slide`
  is given and deck-wide otherwise.
- The return dict gains `acked` (adjudicated records, each carrying its
  `acked_reason`) and `severity_summary` (`blockers`/`advisories`/`infos`/
  `acked` counts). `warnings` now means "advisories not yet adjudicated", so
  `--strict` still means "nothing outstanding".

### Added — acceptance report by tier (`engine/cli.py`)

- `verify` groups output into BLOCKERS / ADVISORIES / INFOS with distinct
  badges, and appends an ADJUDICATED section listing every accepted
  advisory with its written reason, so the reasoning ships with the deck.

### Added — long-form production documentation (`docs/`)

- `docs/LONGFORM_SOP.md` — the 12-step production SOP for 30+ page decks:
  read spec, read materials, outline first (surface gaps early), design system
  with an explicit **forbidden list**, build 5-6 sample pages and check them
  by screenshot, batch by chapter (lint-clean before writing the next batch),
  lint gate, **false-positive adjudication**, read-back page-count check,
  asset verification, screenshot spot-check, honest gap disclosure, delivery
  statement. Each step carries its acceptance criterion and failure handling;
  a minimum-viable 8-step path is included for time-boxed runs.
- `docs/DESIGN_GRAMMAR.md` — visual grammar: the style spectrum (9.8-31.1
  shapes/page, chosen by subject matter rather than a single "best" density),
  semantic colour coding derived from the number of content dimensions, images
  reserved for ceremonial pages while content pages stay native shape,
  header/footer three-piece layout, four cover text-frame patterns, six
  content-page compositions, visual-gene extraction, the corrected gradient
  and shadow picture, six invariants, and a numeric quick-reference table.
- `docs/CONTENT_GRAPHICS.md` — per-unit graphical treatment, the concrete
  method for removing the "AI look": ask of every content unit "what does this
  concept naturally look like?", with 20 native-shape prototypes, a 40-entry
  concept-to-graphic map, a five-step procedure for redrawing an attachment's
  framework diagram natively, and a pre-delivery check list. Includes the
  discrimination test — cover the text and the shapes must still carry the
  logic.
- `docs/GAP_ASSESSMENT.md` — weighted six-dimension distance measurement
  against the benchmark, with every figure reproducible from the workspace.

### Changed

- `SKILL.md` routes long-form work to the new SOP and binds the three craft
  documents by task; the layout-gate section documents the tiers and the
  adjudication workflow. Version bumped to `20261109.1`.
- `.gitignore` excludes `/scratch/` (local working output).

### Verified

- 236 tests pass (222 prior + 14 new in `tests/test_lint_severity.py`),
  `tools/check_all.sh` reports ALL CHECKS PASSED, and all nine example decks
  report zero blockers with no adjudications needed — the tier split surfaced
  no false positives on known-good input.

## [20261108.6] - 2026-11-08

Deterministic layout-engine upgrade closing the three "dead token / random
selection" mechanism gaps found in the post-benchmark architecture review.
Three independent opt-in layers; the default pipeline stays byte-identical and
the legacy 151-test baseline remains green (the suite grows from 151 to 181).

### Added — outer-shadow primitive (L2 visual token → OOXML)
- `compiler.SHADOW_PRESETS` + `_apply_shadow`: a node's `shadow`
  (`none`/`soft`/`medium`, or boolean) compiles to a real
  `a:effectLst/a:outerShdw` (90deg straight down; blur/dist/alpha presets;
  `shadow_color` override, default `#1F2937`). The node field wins, else the
  theme `visual.shadow` token — so the previously unconsumed `soft` token on
  tech/microsoft/stripe now renders. `none` only flips `shadow.inherit=False`,
  which is exactly the legacy behavior (empty self-closing effectLst).
- New lint `SHADOW_VALUE`; the offline PNG contact sheet (`debug_render.py`)
  approximates the shadow with an offset alpha-blended rectangle.

### Added — deterministic archetype scoring (L1 decision layer, opt-in)
- `compose(..., scoring=True)` / CLI `--scoring`: replaces `rng.shuffle` with
  `_archetype_score` (hand-authored kind-contract rank + point-count capacity
  fit + structural cues: quote / left-right / kpi / timeline), ties broken by
  preference order then archetype name. The same notes now yield the identical
  archetype plan under every seed; the RNG still drives per-shape geometric
  jitter, which stays reproducible. Chart/table strong routing and chapter
  de-duplication are unchanged. Default off keeps the legacy shuffled plan.

### Added — declarative 12-column grid (L3 geometry, opt-in)
- `layout.grid_spec` + freeform top-level `col_start`/`col_span`: declarative
  column placement over the master content band (x 60→1220, 24px gutter),
  consuming the previously dead `visual.grid_columns=12` token. `rect` still
  supplies y/h; only horizontal geometry comes from the grid.
- New lint `GRID_COLUMN` (error: non-integer or out-of-bounds spans) and
  `GRID_COLUMN_NESTED` (warning: nested nodes ignore grid fields, the grid is
  top-level only). Nodes without the fields keep their absolute rect path.

### Tests
- +30 tests (11 shadow in `test_visual_primitives.py`, 7 scoring in
  `test_art_direction.py`, 12 grid in new `test_grid_system.py`); suite 151 →
  181, all green. A byte-level regression harness (git worktree at HEAD)
  confirms default-path slide XML is byte-identical to the previous commit for
  a mixed card/shape/richcard deck.

## [20261108.5] - 2026-11-08

Design-system and content-depth upgrade, driven by a head-to-head benchmark
against commercial AI-generated decks (see `docs/BENCHMARK.md`). Closes the two
hard gaps found there — flat visuals with no design-system layer, and thin
on-slide content with no speaker script. Everything stays offline and
deterministic; the default pipeline output is byte-identical and all legacy
tests remain green (new visual languages are opt-in).

### Added — visual primitives
- OOXML gradient fills (`engine/compiler.py::_set_gradient`): a node or slide
  `gradient: {stops:[{color,pos,opacity?}], angle}` compiles to a real
  `a:gradFill` (angle in 1/60000-degree units). A slide may pass
  `gradient: "theme"` to resolve the active theme's signature gradient.
- Three independent alpha channels: shape fill `opacity`, text-run `opacity`,
  and outline `border_opacity`, injected as OOXML `a:alpha` — the basis of
  frosted-glass cards (e.g. white fill at 8% + white border at 20%).
- Theme gradient token `visual.background_gradient` (default `None`, so legacy
  themes keep flat surfaces); `magazine`, `tech` and `oriental` ship
  palette-safe signature gradients. Gradient stop colors are enforced by the
  PALETTE lint gate.
- `gradient`/`opacity`/`icon` branches across the full pipeline: layout
  propagation, lint palette + bounds checks, and the offline PNG contact-sheet
  renderer (`debug_render.py`, with real alpha blending approximation).

### Added — native offline icon system
- `engine/icons.py`: 14 icons composed from native PowerPoint autoshapes on a
  100x100 logical grid, plus 27 semantic aliases (`goal`→target, `risk`→shield,
  …). No bitmap/SVG assets — fully editable, theme-accent tinted, zero network
  and licensing surface. New DSL node `{"t":"icon","name":...}` with a
  dedicated `ICON_NAME` lint rule and square-glyph layout handling.

### Added — card composition archetypes (opt-in)
- `glass-panel` (dark gradient + frosted-glass icon cards), `icon-grid`
  (light 1xN / 2x2 icon cards) and `numbered-cards` (editorial ordinal cards
  with an accent rail). The archetype pool grows from 14 to 17, but the new
  three enter the planning shuffle only with `compose --card-system`
  (`card_system=true`), preserving legacy determinism.

### Added — speaker notes and content depth
- Offline, deterministic speaker-script generator (`_speaker_notes`): restates
  each page's own title/lead/points/quote into spoken prose without inventing
  data; a page's verbatim `notes` always wins. Scripts compile to real
  `notesSlide` parts. New lint: `NOTES_COVERAGE` (blocking, when notes are
  required) and `NOTES_THIN` (advisory under 40 chars).
- `CONTENT_DENSITY` advisory lint: composed content pages under 60 visible
  characters warn and point toward the 150-250 chars/page benchmark band;
  cover/section/closing/quote/chart/table archetypes are exempt. Works
  alongside the existing blocking `RESEARCH_LEDGER` source rule.

### Tests
- `tests/test_visual_primitives.py`: 34 new tests (icon library/aliases,
  gradient OOXML + angle units, all three alpha channels, notes slides,
  card archetypes, theme gradients, density and research lint). Full suite
  grows from 117 to 151 tests, all green.

## [20261108.4] - 2026-11-08

Long-deck guardrails, research ledger, and native data archetypes. Responds
to an 88-page failure case where a flat file exhausted the archetype pool and
the lint gate had to be bypassed with `--force`.

### Added
- `chart-story` and `table-board` composition archetypes in
  `engine/art_direction.py`: notes pages carrying `chart`
  (kind/categories/series) or `table` (headers/rows) data are routed to them
  and compile to native, editable PowerPoint charts and tables (not images or
  text-box mockups). The archetype pool grows from 12 to 14.
- Native table rendering in `engine/compiler.py` (`add_table`), table-aware
  layout in `engine/layout.py`, table drawing in `engine/debug_render.py`,
  and `TABLE_SHAPE` lint diagnostics for missing/mismatched table shape.
- Long-deck planning guard: a flat notes file over `CHAPTER_PAGE_CAP` (24
  pages) without chapter pages is refused at `compose` time
  (`COMPOSE BLOCKED`) before any geometry work; `allow_long_deck: true` is an
  explicit, logged override.
- Chapter-aware archetype planning: the variety budget resets per chapter, so
  archetypes may legitimately recur across chapters while `LAYOUT_VARIETY` is
  now evaluated per chapter; `LAYOUT_REPETITION` (no adjacent repeats) is
  unchanged.
- Research ledger: notes/slide `research` demand plus `sources`
  `[{title, url, publisher}]`, with a blocking `RESEARCH_LEDGER` lint rule.
  The engine stays offline; the host performs the research, the gate verifies
  the deliverable.
- Forced-build provenance: `build --force` on a composed deck writes a
  `FreePPTForcedBuildMarker` text box and a document subject into the pptx, so
  a bypassed lint gate is visible inside the artifact itself.
- `inspect` now reports native chart/table shape summaries.
- `tests/test_long_deck_guard.py`: 13 tests covering the compose guard,
  override, chapter lint pass, cross-chapter recurrence, force marker,
  research ledger, native chart/table compilation and inspect read-back, and
  determinism. Full suite is now 117 tests, all green.

### Changed
- `plan_archetypes()` is chapter-aware and routes data-bearing pages before
  the deterministic shuffle; `_explicit_points()` prevents the kind/lead
  fallback from duplicating a chart page's lead text.
- Deck `art_direction` metadata now carries `chapters`, `chapter_boundaries`,
  `long_deck_forced`, and `engine_version: 3`.
- SKILL.md corrects a stale statement that the repo was "not pushed to any
  remote" and documents the new guardrails; README/README.en, architecture
  and DSL references, and the contribution guide reflect 14 archetypes and
  the new lint codes.

## [20261108.3] - 2026-11-08

Open-source foundation and the "verifiable quality" layer.

### Added
- Dual license: code under MIT (`LICENSE`), documentation and design references
  under CC BY 4.0 (`LICENSE-DOCS`). Author attribution is retained.
- `README.en.md`, `CONTRIBUTING.md`, this changelog, `.gitignore`, publishing
  checklist, issue/PR templates, and GitHub Actions CI.
- `install.sh`: one-command install for WorkBuddy, Claude Code, Codex CLI,
  Cursor, and DeepSeek Harness (DSH), with project/user scope, idempotent
  bootstrap blocks, self-check, uninstall backup, and `--refresh-cache` for
  the WorkBuddy skill-list cache (measured: its watch list does not always
  include the user skills directory).
- Pure-CLI path: `cli.py make` turns a plain-text brief into a linted PPTX with
  no LLM and no network access.
- `engine/typography.py`: CJK line-break prohibitions (kinsoku), punctuation
  compression, CJK/Latin spacing, and a font fallback stack.
- `cli.py inspect` / `cli.py retext` for editing existing .pptx files, and
  `cli.py patch` for single-node local revisions of a deck DSL.
- `tools/benchmark.py` (editable-shape ratio, overflow, offline readiness,
  runtime) and `tools/render_check.py` (LibreOffice PDF/PNG regression).
- `references/dsl-spec.md`, `docs/THEME_CONTRIBUTION.md`,
  `examples/GALLERY.md`, `docs/BENCHMARK.md`.

### Changed
- Copyright notices in `SKILL.md`, `README.md`, and
  `references/architecture.md` now describe the dual license instead of
  "all rights reserved".
- Both READMEs were rewritten in plain technical prose: marketing phrasing,
  antithetical slogans, heavy bold emphasis, the self-citation appendix and a
  machine-specific absolute path were removed. The five-stage names now match
  the pipeline definition exactly. Measured numbers were refreshed to 104 unit
  tests and the two green remote CI runs; the MLA entries for external sources
  were kept.
- Fixed the `cli.py patch` example in both READMEs: `slides.0.data.title` does
  not exist in the DSL and was rejected by the tool. The example now uses a
  real text node (`slides.0.children.0.children.1.text`) and real example
  input files.

### Fixed
- Composed decks no longer bake in the generating machine's absolute
  `assets_base`: `art_direction.compose()` emits a cwd-relative directory and
  `examples/deck_notes_composed.json` is portable. The absolute path made the
  example pass locally but fail `ASSET_MISSING` in CI and fresh checkouts.
  Added `tests/test_repo_portability.py` and stopped suppressing lint
  diagnostics in the CI workflow.

## [20261108.2] - 2026-11-08

### Added
- Creative page-by-page composition: `composition: freeform` with absolute
  node rects; 12 layout archetypes in `engine/art_direction.py`; cover-image
  palette/motif derivation in `engine/cover_style.py`.
- New lint hard gates: `LAYOUT_REPETITION`, `LAYOUT_VARIETY`, plus
  `DENSITY_FLAT` warning. `compose` and `style` CLI commands.
- 14 new tests in `tests/test_art_direction.py`; 9-page reading-notes example,
  nine-page comparison sheet, and a derived-style provenance ledger.

### Changed
- `SKILL.md` / `README.md` / `references/dsl.md` / `references/architecture.md`
  document two generation paths (masters vs. freeform). Old master-based decks
  remain unchanged (zero regression).

## [20261108] - 2026-11-08

### Added
- Data-driven themes (stripe / vercel / wired / ibm) imported from public
  DESIGN.md tokens via `engine/design_md_import.py`, with SHA256 provenance.
- `references/design-token-sources.md` and imported token tables.
- Copyright notice: author 张三峯, publication AI龙卷风.
- Installed the skill into `~/.workbuddy/skills/freeppt/` and fixed skill-list
  cache invalidation so it appears in the enabled skills list.

## [20261103] - 2026-11-03

### Added
- Initial engine: JSON DSL -> deterministic layout -> numeric lint -> python-pptx
  compiler -> .pptx, with the five-stage pipeline documented.
- 16 visual themes, 10 master templates, 8 enterprise report types,
  procedural vector art, licensed web-image search with a provenance ledger,
  OOXML animation/transition support, and offline PNG preview rendering.
- AI-label compliance boundary documented: no watermark-removal tooling;
  procedural/authorized imagery is used by default.
