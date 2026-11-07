# Changelog

All notable changes to FreePPT are documented here. Dates use YYYY-MM-DD.
Version strings follow the project's date-based scheme (`YYYYMMDD[.n]`).

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
