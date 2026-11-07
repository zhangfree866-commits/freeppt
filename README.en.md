# FreePPT — native, editable PPTX from a deterministic pipeline

**Author: 张三峯** · WeChat publication: **AI龙卷风**

© 2026 张三峯. **Code: MIT · Documentation and design references: CC BY 4.0**
(see `LICENSE`, `LICENSE-DOCS`). Keep the author and publication attribution when
redistributing. Chinese README: [README.md](README.md).

## What it is

FreePPT is a self-contained PPT generation skill. Give it a topic, a pile of
rough notes, or a reading-notes file (optionally with a book cover image) and it
returns a **native editable .pptx**: text, charts and shapes remain editable in
PowerPoint, not flattened into page images.

Two things are enforced by code rather than by prompt discipline: **content
structure** and **numeric design rules**. A `lint` gate blocks compilation
unless the deck passes. Quality is a guaranteed floor, not a lucky ceiling.

## Five stages (fixed order)

`planning → generate DSL → layout → lint → compile/render`

"Optimization" is not a post-render visual polish pass. It is the loop in which
lint diagnostics send you back to stage 2 to edit the DSL.

## Two generation paths

| | A. Master specification | B. Creative composition |
|---|---|---|
| For | weekly / monthly / quarterly / annual reports, performance reviews, retrospectives, business analysis | reading notes, book reviews, brand narratives, talks, course material |
| Layout source | 10 fixed masters | 12 layout archetypes assigned page by page from content semantics + a deterministic seed |
| Visual language | 16 registered themes | palette, type personality and motif derived from a reference cover image |
| Skeleton | fixed title + rule + content + footer | no imposed skeleton; every element has an absolute `rect` |
| Lint | safe area, density, spacing, font size, palette | geometry, overflow, WCAG contrast, palette + `LAYOUT_REPETITION` / `LAYOUT_VARIETY` |

Path B exists because "ten pages that all look the same" is a defect, not a
style. Adjacent-page repetition is a hard lint error.

## Highlights

- **Editable by construction** — python-pptx native shapes, not screenshots.
- **Cover-derived art direction** — `engine/cover_style.py` extracts the accent
  (scored by chroma × coverage × mid-tone so large paper areas do not win),
  the light paper, and the dominant color block's position. Every derived
  theme carries a SHA256 provenance ledger and passes a contrast check.
- **Offline / deterministic** — same notes + same cover → same DSL. No LLM API,
  no network call. Runtime dependencies: `python-pptx`, `Pillow`, `lxml`.
- **Pure CLI** — `cli.py make` works without any AI host.
- **Compliance-minded** — no watermark-removal tool. Default artwork is
  procedural vectors or licensed web images with a source ledger.

## Install

```bash
git clone <repo-url> && cd ppt-skill
pip install -r requirements.txt
bash tools/check_all.sh
```

One-command host install (WorkBuddy / Claude Code / Codex CLI / Cursor / DSH):

```bash
./install.sh --host all --scope user
./install.sh --host dsh --scope project --bootstrap
```

See `docs/PUBLISHING.md` for host path provenance and the verification status
of each path.

## Use

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

# edit an existing pptx and revise a single node
python3 engine/cli.py inspect old.pptx --out structure.json
python3 engine/cli.py retext old.pptx --map edits.json --out revised.pptx
python3 engine/cli.py patch deck.json --set "slides.0.title=New title" --build out.pptx
```

## Measured status

Numbers below come from local runs on 2026-11-08; reproduce with
`bash tools/check_all.sh` and `python3 tools/benchmark.py`.

- 100 offline unit tests pass.
- All 8 example decks pass `lint` with zero errors; `bash tools/check_all.sh` is green.
- Self-benchmark: 0 layout errors, mean editable-shape ratio 0.9647, 0.0 overflow rate, 0 network hits in the core pipeline (static scan). See `docs/BENCHMARK.md`.
- 16 themes, 8 report types, 10 masters, 12 layout archetypes, 10 vector sets.
- The 9-page reading-notes example yields 9 distinct archetypes and 4 density
  levels; derived ink-on-paper contrast is 16.2:1.

## Boundaries (stated plainly)

- Creative composition is **deterministic rule-driven**, not an end-to-end
  generative design model. The archetype library has 12 entries. The reference
  image contributes color values and compositional position only; it is not
  copied into the deck and its text is not OCR'd.
- "Smart content creation" is structural planning plus a quality gate. Prose
  expansion is done by the host agent following `references/content-playbook.md`;
  no LLM client or API key is bundled.
- Enterprise-style themes are stylistic approximations, not official brand
  guidelines; no third-party logo is included.
- Animation XML has not been verified in Microsoft PowerPoint on this machine.
- LibreOffice rendering regression is skipped locally when `soffice` is absent;
  CI installs LibreOffice and runs it. Pixel-level baseline diffing is not implemented.
- Editing an existing .pptx currently means structure inspection and
  format-preserving text replacement. A full existing-pptx → DSL round trip is
  NOT implemented. Host paths other than WorkBuddy have official documentation
  behind them but were not installed on this machine.

## Contributing

Read `CONTRIBUTING.md`, `references/dsl-spec.md` and
`docs/THEME_CONTRIBUTION.md`. Every new capability needs a lint rule and a
test. No change may weaken the stage-4 gate.
