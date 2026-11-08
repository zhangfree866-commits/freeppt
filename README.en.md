# FreePPT

[![CI](https://github.com/zhangfree866-commits/freeppt/actions/workflows/ci.yml/badge.svg)](https://github.com/zhangfree866-commits/freeppt/actions/workflows/ci.yml)

**Author: 张三峯** · WeChat publication: **AI龙卷风**

© 2026 张三峯. Code: MIT. Documentation and design references: CC BY 4.0 (see `LICENSE`, `LICENSE-DOCS`). Keep the author and publication attribution when redistributing. Chinese README: [README.md](README.md).

## What it does

FreePPT takes a topic, a set of rough notes, or a reading-notes file (optionally with a book cover image) and writes a native editable .pptx. Text, charts, and shapes stay editable in PowerPoint. The engine does not flatten pages into images.

Two paths, chosen by content type:

- Fixed-structure reports (weekly, monthly, quarterly, annual, performance reviews, retrospectives, business analysis) use 10 masters.
- Reading notes, brand narratives, and talks use page-by-page composition. The engine assigns one of 14 layout archetypes to each page from content semantics and a deterministic seed, and can derive a palette and motif from a supplied cover image; pages carrying chart/table data compile to native editable charts and tables. `lint` treats adjacent-page repetition and insufficient per-chapter archetype variety as hard errors; flat files longer than 24 pages are rejected at the planning stage until split into chapters.

## Five stages

`planning → generate DSL → layout → lint → compile/render`

`cli.py build` exits without writing a file when lint fails. The user edits the DSL and runs lint again. Safe area, minimum font size, spacing steps, palette, density, text overflow, and image-source credits are numeric conditions evaluated by `engine/lint.py`. `composition: freeform` switches to geometry, overflow, contrast, and palette-consistency rules; the two anti-repetition rules still apply. The rework happens in the data, not in a post-render visual polish pass.

## Features

| Area | Details |
|---|---|
| Themes (16) | Changing `theme` switches palette, CJK/Latin font pairs, corner radius, line spacing, and chart colors. Six general themes (consulting default, magazine, dark tech, Swiss minimal, new-Chinese, unlocked); six enterprise-style themes (McKinsey, BCG, PwC, Roland Berger, Microsoft, Apple); four data-driven themes (Stripe, Vercel, WIRED, IBM) built from public design tokens with traceable color values. |
| Report types (8) | Weekly, monthly, quarterly, annual, performance review, competition, retrospective, business analysis. Each has a narrative structure, a 6–10 page plan, and a matched theme. |
| Content assistance | The engine routes rough notes to KPI, trend, diagnosis, and action pages. Prose expansion is done by the host agent following `references/content-playbook.md`; the code supplies constraints (conclusion-style headings, MECE, data-to-conclusion, a cliché blacklist, no invented numbers) and a content gate. |
| Page-by-page composition | 14 archetypes: editorial cover, section page, cross-page spread, full-page quote, offset three-column, split spread, margin annotation, stepped list, number focus, uneven grid, timeline, closing echo, native chart story, native table board. Text height is computed from actual line wrapping; the variety budget is evaluated per chapter so the same archetype may legitimately recur across chapters. |
| Long-deck guardrails | A flat file is capped at 24 pages; beyond that, compose refuses to run without chapter pages and prints the fix. An explicit override leaves a forced-build marker inside the produced pptx, so `--force` is no longer a silent back door. |
| Research source ledger | Pages can declare a `research` demand with a `sources` ledger (title plus URL/publisher); lint blocks any researched page without a usable source. The engine stays offline; the host still performs the actual research. |
| Cover-derived art direction | `engine/cover_style.py` scores the accent by chroma × coverage × mid-tone so large paper areas do not win, then derives semantic colors, type personality, and a recurring motif (band, rule, arc, dot, grid). The cover SHA256 and extracted palette are written to a provenance ledger. |
| Masters (10) | Cover, contents, section, three cards, KPI row, chart insight, image + text, process, timeline, closing. |
| Freeform DSL | `composition: freeform` supports absolute `rect`, bleed blocks, vertical rules, rotation, opacity, and vertical alignment. The engine does not impose a title + rule + footer skeleton. |
| Artwork (three channels) | Procedural vectors: 10 diagram families, emitted as both PNG and editable SVG. Licensed web images: keyword search → local download → source ledger → mandatory credit on the page that uses them. Generative images: opt-in, used only when the first two cannot cover a photographic scene. |
| Motion | Page fade transitions and element fade/rise entrances are written as ordinary editable shapes. |
| Offline verification | Full-page PNG export works without Office; remote CI installs LibreOffice for PDF/PNG render regression. |
| Pure CLI | `cli.py make` turns a brief into a skeleton, a content gate, lint, and .pptx with no LLM and no network. All 8 report types work this way. |
| Editing existing .pptx | `inspect` exports shape, text, and coordinate structure; `retext` replaces text while preserving run fonts; `patch` revises one DSL node and re-runs lint. |
| CJK typography | Kinsoku line-break prohibitions, hanging punctuation, unbreakable dash/ellipsis runs, optional CJK/Latin hair spacing, and a declarative font fallback stack; `CJK_KINSHOKU` is a lint rule. |
| Benchmark | `tools/benchmark.py` reports layout errors, editable-shape ratio, text overflow, offline readiness, and runtime. Method: `docs/BENCHMARK.md`. |
| Install | `install.sh` covers WorkBuddy, Claude Code, Codex CLI, Cursor, and DSH (DeepSeek Harness), at user or project scope, with idempotent bootstrap blocks, self-check, and uninstall backup. |

## AI labels and compliance

Default artwork is procedural vectors or licensed web images with a source ledger. Neither is generative synthetic content, so default output carries no label that needs removing. FreePPT provides no tool for removing or erasing an added label. The Chinese README cites the regulatory basis; this paragraph is an engineering description, not legal advice.

## Install and use

```bash
git clone https://github.com/zhangfree866-commits/freeppt.git
cd freeppt
pip install -r requirements.txt
bash tools/check_all.sh
```

`./install.sh --host workbuddy --scope user` installs to one host; `--host all` covers all five. `./install.sh --host dsh --scope project --bootstrap` sets up a project scope. Host path provenance and verification status: `docs/PUBLISHING.md`. The development source and the user-level install at `~/.workbuddy/skills/freeppt/` are copies, so source changes need a sync.

```bash
# pure CLI, no LLM, no network
python3 engine/cli.py make "Q3 revenue up 12%; churn fell to 1.8%; launch onboarding v2" \
  --type weekly --theme consulting --out out.pptx

# creative path: notes + reference cover
python3 engine/cli.py compose examples/notes_renqing_mianzi.json \
  --cover examples/assets/book_cover_demo.png \
  --out deck.json --ledger style.json
python3 engine/cli.py lint  deck.json
python3 engine/cli.py build deck.json out.pptx

# edit an existing pptx and revise one DSL node
python3 engine/cli.py inspect old.pptx --out structure.json
python3 engine/cli.py retext old.pptx --map edits.json --out revised.pptx
python3 engine/cli.py patch examples/demo.json \
  --set "slides.0.children.0.children.1.text=New title" --build revised.pptx
```

A report type gives you the full chapter structure; a theme id changes the visual system. Example .pptx files, the `examples/GALLERY.md` index, and `examples/composition_compare.png` are in the repository. Contribution rules: `CONTRIBUTING.md`. DSL reference: `references/dsl-spec.md`.

## Measured status (2026-11-08)

- `python3 -m unittest discover -s tests -q`: 104 offline tests pass.
- `engine/cli.py lint`: all 8 example decks pass with zero errors.
- `bash tools/check_all.sh`: all four stages green, including compose → lint → build (9 pages, 9 archetypes) and a pure-CLI 6-page deck.
- `tools/benchmark.py`: 0 layout errors, mean editable-shape ratio 0.9647, 0.0 overflow rate, 0 network hits in the core pipeline (static scan). Method: `docs/BENCHMARK.md`.
- Registered: 16 themes, 8 report types, 10 masters, 14 archetypes, 10 vector sets (PNG + SVG). All 14 non-default themes passed a switch-and-lint check.
- The 9-page reading-notes example yields 9 distinct archetypes and 4 density levels; derived ink-on-paper contrast is 16.2:1.
- Remote GitHub Actions: two successful workflow runs on 2026-11-08 across a 4-version Python matrix and a LibreOffice render regression. The first run failed because an example deck contained the author's local absolute path; commit `be35af8` fixed it.

Reproduce with `bash tools/check_all.sh` and `python3 tools/benchmark.py --out bench.json`.

## Known limits

- The 6 enterprise-style themes use industry-standard approximations; the 4 data-driven themes use public extracted design tokens. Neither is an official brand guideline, and the repository contains no third-party logos.
- Prose expansion is done by the host agent following `references/content-playbook.md`. The code provides structural planning, note routing, and a quality gate. No LLM client or API key is bundled.
- Animation XML passes XML parsing but has not been played back in Microsoft PowerPoint on this machine.
- The live web-image search endpoint is unreachable in this environment. Its response parser was verified offline against real data samples, and the download → verify → ledger chain was verified end to end against a local server.
- Archived Linear and Notion tokens are not registered as themes. Both systems use dark content pages, while the current skeleton is a dark cover plus light content pages; applying those tokens would make text unreadable.
- Editing an existing .pptx means structure export and format-preserving text replacement. A full existing-pptx → DSL round trip is not implemented (`references/edit-existing.md`). Gradient fills, controlled shadows, a 12-column grid, and chart-to-infographic conversion remain on the backlog.
- `soffice` is absent locally, so the LibreOffice regression is skipped here; skipped is not passed. Remote CI installs the dependency and asserts `status=ok`. Pixel-level baseline diffing is not implemented.
- Host install paths come from official documentation or official repositories. Only WorkBuddy was installed and tested on this machine; the other four have official sources behind them but were not tested locally (`docs/PUBLISHING.md`).
- Page-by-page composition is deterministic rule-driven, not an end-to-end generative design model. The archetype library has 14 entries, varied by seed and content semantics. The reference image contributes color values and compositional position only; the engine neither copies the cover artwork nor OCRs its text. Unbounded layouts still require hand-written freeform DSL.

## Implementation and dependencies

The layout algorithm, lint rules, masters, vector artwork, animation injection, and search/download code are implemented in this repository. The directory is self-contained. Runtime dependencies are `python-pptx`, `Pillow`, `lxml`, and the Python standard library; the core generation path makes no network calls. The project is independently authored and does not reference, depend on, or modify another product's skill.

The four data-driven themes reference public CSS design tokens collected by VoltAgent/awesome-design-md (MIT). Only numeric values (colors, corner radius) are used; no prose, code, logo, or image asset is copied (VoltAgent). Each value is traceable via `references/imported/theme_mapping.json` → `design_tokens.json` → source SHA256; see `references/design-token-sources.md`. The upstream repository is not a runtime dependency.

## Sources (MLA)

VoltAgent. "Awesome DESIGN.md." *GitHub*, 2026, github.com/VoltAgent/awesome-design-md. Accessed 8 Nov. 2026.

国家互联网信息办公室, et al. "人工智能生成合成内容标识办法." *中国网信网*, 14 Mar. 2025, www.cac.gov.cn/2025-03/14/c_1743654684782215.htm. Accessed 8 Nov. 2026.
