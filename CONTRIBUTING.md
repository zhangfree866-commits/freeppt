# Contributing to FreePPT

**作者：张三峯** ｜ 公众号：**AI龙卷风**

Thanks for contributing. FreePPT is an independent, original project: do not
copy code, prompts, assets, or skill definitions from other products' skills.
Cite any external data you use, with an MLA-style source entry and a SHA256
ledger when you import numeric values.

## Non-negotiable rules

1. **Five stages stay intact**: planning → generate DSL → layout → lint →
   compile/render. `build` must keep running lint first. Never add a
   `--skip-lint` shortcut.
2. **Every new capability ships with a lint rule and a test.** A theme, master,
   or layout archetype without a test is not merged.
3. **Determinism over improvisation.** Same input → same DSL → same .pptx.
   Randomness must come from an explicit, recorded seed.
4. **No fabricated facts.** Example decks may contain clearly labelled sample
   data, never invented real-world figures presented as facts. Charts require a
   `source` field.
5. **Attribution stays.** Keep the author and publication credit in `SKILL.md`,
   `README.md`, and `references/architecture.md`. New files inherit the dual
   license: code MIT, docs CC BY 4.0.
6. **No new runtime dependencies** without discussion. Current runtime deps:
   `python-pptx`, `Pillow`, `lxml`. Importers and tooling should prefer the
   standard library.
7. **No watermark/AI-label removal tooling.** See the compliance section in
   `SKILL.md`.

## Before you open a PR

```bash
python3 -m pip install -r requirements.txt
bash tools/check_all.sh
python3 tools/benchmark.py --out /tmp/bench.json
```

`tools/check_all.sh` runs the unit suite, lints every example deck, and runs the
compose → lint → build smoke test. All three must pass.

Then, for whatever you changed:

| Change | Required evidence |
|---|---|
| New theme | `tests/test_themes.py` case, palette self-consistency, a built + rendered sample |
| New master | example deck JSON, lint zero errors, PNG preview |
| New layout archetype | `tests/test_art_direction.py` case proving diversity and determinism; data archetypes also need a `tests/test_long_deck_guard.py` case with a built pptx |
| New lint rule | a fixture that FAILS without the rule and PASSES with it |
| Compiler change | before/after PNG or PPTX shape-count comparison |
| Imported design tokens | source URL, license, SHA256, mapping rationale |

## Commit and PR convention

- Commit subject: `type: short imperative summary` (`feat`, `fix`, `docs`,
  `test`, `chore`).
- In the PR body, state what changed, how you verified it, and which lint rule
  or test covers it.
- Do not bundle unrelated themes or features into one PR.

## Adding a theme / master / archetype

Read `docs/THEME_CONTRIBUTION.md` and `references/dsl-spec.md` first. The short
version: register it, give it a stable id and aliases, keep all colors inside
its palette, add a lint contract, and document the source of every value.

## Reporting bugs

Use `.github/ISSUE_TEMPLATE/bug_report.yml`. Include the deck JSON, the exact
command, the full lint output, your Python version, and your OS. A reproducible
minimal deck is worth more than a screenshot.

## License of contributions

By contributing you agree that your code is licensed under MIT and your prose
under CC BY 4.0, and that you have the right to submit it. The project's
copyright notice and author attribution remain unchanged.
