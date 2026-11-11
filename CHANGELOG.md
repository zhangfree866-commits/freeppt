# Changelog

All notable changes to FreePPT are documented here. Dates use YYYY-MM-DD.
Version strings follow the project's date-based scheme (`YYYYMMDD[.n]`).

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
