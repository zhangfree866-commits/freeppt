# Publishing checklist and host path provenance

**作者：张三峯** ｜ 公众号：**AI龙卷风**

This repository is published as a **public** GitHub repository at
<https://github.com/zhangfree866-commits/freeppt>. It was prepared locally
(git initialized, history rewritten before publishing) and first pushed on
2026-11-08. Items marked **Done** below were completed during that push; the
remaining items are manual web-UI steps.

## First-push record

0. This repository was initialized locally with a **placeholder git identity**
   (`user.name` = 张三峯, `user.email` = `freeppt@localhost`). On 2026-11-08 the
   repository-level identity was set to the GitHub-provided noreply address:
   `git config user.email "338116425+zhangfree866-commits@users.noreply.github.com"`.
   The address follows GitHub's documented `ID+USERNAME` format for accounts
   created after 18 July 2017; it combines the public numeric user id
   `338116425` with the public login `zhangfree866-commits` (public
   `created_at` is 2026-10-05). The account owner selected this address
   instead of a personal mailbox, so no personal email address is recorded
   here. **Confirmed 2026-11-08**: the account owner's screenshot of
   <https://github.com/settings/emails> shows **Keep my email addresses
   private = On** and displays the exact noreply address above. The page states
   that command-line Git operations use the address configured in Git (GitHub),
   which matches the setting above; GitHub attributes commits only when the
   author email is connected to the account or is the noreply address provided
   in email settings (GitHub Docs). **Block command line pushes that expose my
   email** was **Off** in that screenshot; the account owner subsequently
   switched it **On** before authorising the first push, which adds a
   push-time guard against future commits authored with a private mailbox.
   **History rewritten 2026-11-08**: the page also notes that previously
   authored commits associated with a public email remain public (GitHub).
   Because the repository had never been pushed, the local history was
   rewritten before publishing: every commit now carries the noreply identity,
   and the personal mailbox no longer appears in any historical version of this
   file. A full pre-rewrite `git bundle` was kept locally as a recovery copy;
   it is not part of the repository and must not be published.
1. **Done 2026-11-08**: the placeholder Discussions URL in
   `.github/ISSUE_TEMPLATE/config.yml` now points to
   `https://github.com/zhangfree866-commits/freeppt/discussions`, using the
   repository name approved by the account owner. An authenticated API check
   before creation returned 404, and the public repository was then created at
   that path. The link resolves in a browser only once Discussions is enabled
   (item 4).
2. **Done 2026-11-08**: CI badges were added to `README.md` and
   `README.en.md` only after the repository existed; both point at
   `.github/workflows/ci.yml`. No badge was published against a
   non-existent repository.
3. Set repository topics (GitHub web UI → About → topics):
   `pptx`, `powerpoint`, `slides`, `presentation`, `python-pptx`,
   `design-system`, `chinese`, `ai-agent`, `agent-skills`, `skill`,
   `ppt`, `deck`, `lint`, `offline`, `editable-pptx`.
4. Enable GitHub Discussions. Suggested categories:
   `Announcements`, `Show and tell` (deck gallery), `Q&A`,
   `Themes & masters`, `Ideas`.
5. Set branch protection on `main`: require the `CI` workflow to pass.
6. Create the first release tag after CI is green on the remote.

The public repository was created and pushed with the GitHub CLI using an
OAuth device-flow token scoped `repo,workflow`; `gh auth setup-git` installed
the Git credential helper. The token lives only in the local
`~/.config/gh/hosts.yml` (mode 0600) and is never part of the repository.
The local branch is `main` and every pushed commit carries the noreply
identity described in item 0.

## After the first push

**Done 2026-11-08, run `42423667649` (commit `be35af8`)**: CI succeeded on all
five jobs — `tests / py3.10`, `py3.11`, `py3.12`, `py3.13` and
`LibreOffice render regression`. The `freeppt-rendered-*` artifact was
downloaded: 9 PNG pages, and page 1 (editorial cover) and page 5 (offset
triptych) were checked by eye — Chinese text renders completely, with no
blank columns, clipping or garbled glyphs. The very first run
(`42423131961`) failed at `Lint every example deck` and `Build deck` because
`examples/deck_notes_composed.json` pinned the author's absolute
`assets_base`; `be35af8` fixed the example, made `compose()` emit portable
paths, added a portability test, and stopped hiding lint diagnostics in CI.

Still manual (verified not yet done on 2026-11-08):

- Items 3–6 above: repository topics are empty, `has_discussions` is `false`,
  `main` is not protected, and no release tag exists.
- Fill `docs/BENCHMARK.md` with the numbers produced by CI. Never paste
  competitor numbers you have not measured yourself.

## Host path provenance

`install.sh` copies the skill into the paths below. Verification status is
stated honestly: "measured" means a real install was verified on this machine
(2026-11-08, macOS); "documented" means an official doc or official repository
source was consulted but no local install of that host was performed.

| Host | User scope | Project scope | Bootstrap file | Status |
|---|---|---|---|---|
| WorkBuddy | `~/.workbuddy/skills/freeppt/` | — | — | **measured** |
| Claude Code | `~/.claude/skills/freeppt/` | `.claude/skills/freeppt/` | `~/.claude/CLAUDE.md`, `./CLAUDE.md` | documented |
| Codex CLI | `~/.agents/skills/freeppt/` | `.agents/skills/freeppt/` | `~/.codex/AGENTS.md`, `./AGENTS.md` | documented |
| Cursor | `~/.cursor/skills/freeppt/` | `.cursor/skills/freeppt/` | `./AGENTS.md`, `./CLAUDE.md` | documented |
| DeepSeek Harness (DSH) | `~/.dsh/skills/freeppt/` | `.dsh/skills/freeppt/` | `~/.dsh/AGENTS.md`, `./AGENTS.md` | documented |

Notes:

- Codex CLI, Cursor and DSH also read the shared `~/.agents/skills/` /
  `.agents/skills/` root. `install.sh --host all` writes the primary path for
  each host and deduplicates shared roots, so it does not install the same
  skill twice into one directory.
- DSH resolves `dshHome` from `$DSH_HOME` (default `~/.dsh`) and
  `agentsHome` from `$DSH_AGENTS_HOME` (default `~/.agents`). The installer
  honours both environment variables.
- WorkBuddy keeps a skill-list cache (`~/.workbuddy/.skill-list-cache.json`).
  It only rescans when the signature of paths in its `watch` list changes.
  **Measured 2026-11-08**: the watch list sometimes does NOT contain the user
  skills directory (it was rebuilt without it at 04:15), so even editing
  `freeppt/SKILL.md` did not trigger a rescan — the cache still reported
  version `20261108.2` until a watched plugin SKILL.md was touched. Therefore:
  - after install/update, check whether `watch` contains `freeppt`;
  - if not, run `./install.sh --host workbuddy --refresh-cache` (touches one
    watched plugin SKILL.md, changing only its mtime) or refresh the skill list
    in settings;
  - when `watch` already contains `freeppt`, editing its SKILL.md does trigger
    a rescan on its own.
  This nuance supersedes the earlier, over-optimistic "updates always
  auto-refresh" claim.
- These paths reflect the cited documentation at the time of writing. Host
  products change; if your client does not see the skill, check its current
  docs before assuming the installer is wrong.

### Sources (MLA)

Anthropic. "Skills." *Claude Code Docs*, code.claude.com/docs/en/skills.
Accessed 8 Nov. 2026.

Anthropic. "Memory." *Claude Code Docs*, code.claude.com/docs/en/memory.
Accessed 8 Nov. 2026.

OpenAI. "Build skills." *Codex Docs*, developers.openai.com/codex/skills.
Accessed 8 Nov. 2026.

OpenAI. "Customization." *Codex Docs*,
developers.openai.com/codex/concepts/customization. Accessed 8 Nov. 2026.

OpenAI. "skills.md." *openai/codex*, GitHub,
github.com/openai/codex/blob/main/docs/skills.md. Accessed 8 Nov. 2026.

Cursor. "Skills." *Cursor Docs*, cursor.com/docs/context/skills.
Accessed 8 Nov. 2026.

Cursor. "Rules." *Cursor Docs*, cursor.com/docs/rules. Accessed 8 Nov. 2026.

DeepSeek. "Skills." *DeepSeek Harness Reference*,
deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/skills.
Accessed 8 Nov. 2026.

DeepSeek. "Config catalog." *DeepSeek Harness Reference*,
deepseek-harness.github.io/deepseek-harness/en/reference/config-catalog.
Accessed 8 Nov. 2026.

DeepSeek. "skill-filesystem README." *deepseek-ai/deepseek-harness*, GitHub,
github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md.
Accessed 8 Nov. 2026.

DeepSeek. "agent-instructions README." *deepseek-ai/deepseek-harness*, GitHub,
github.com/deepseek-ai/deepseek-harness/blob/master/packages/context/agent-instructions/README.md.
Accessed 8 Nov. 2026.

The path table was assembled from these sources by a research pass on
2026-11-08. The WorkBuddy path was verified by a local install; the other four
were not installed locally on this machine, so their runtime behaviour remains
unverified here.

## Commit identity sources (MLA)

GitHub. "Setting Your Commit Email Address." *GitHub Docs*,
docs.github.com/zh/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address.
Accessed 8 Nov. 2026.

GitHub. "Email Addresses Reference." *GitHub Docs*,
docs.github.com/zh/account-and-profile/reference/email-addresses-reference.
Accessed 8 Nov. 2026.

GitHub. "User Response for zhangfree866-commits." *GitHub REST API*,
api.github.com/users/zhangfree866-commits. Accessed 8 Nov. 2026.

Google. "Manage Your Email Addresses." *Google Account Help*,
support.google.com/accounts/answer/6316959. Accessed 8 Nov. 2026.

GitHub. "Emails." *GitHub Settings*, github.com/settings/emails. Accessed 8
Nov. 2026 (content supplied as an account-owner screenshot).
