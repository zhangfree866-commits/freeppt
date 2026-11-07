#!/usr/bin/env bash
# FreePPT one-command installer.
#
# Hosts: workbuddy | claude | codex | cursor | dsh | all
# Scope: user (global) | project (inside --project-root)
#
# Path provenance and verification status: docs/PUBLISHING.md
# This script never deletes user files. Uninstall MOVES the installed directory
# to a timestamped backup under $HOME.

set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
HOST="workbuddy"
SCOPE="user"
PROJECT_ROOT="$(pwd)"
BOOTSTRAP=0
UNINSTALL=0
DRY_RUN=0
SELF_CHECK=1
REFRESH_CACHE=0
BACKUP_DIR="$HOME/.freeppt-uninstalled"

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --host NAME        workbuddy | claude | codex | cursor | dsh | all  (default: workbuddy)
  --scope SCOPE      user | project                                   (default: user)
  --project-root DIR project root for --scope project                (default: cwd)
  --bootstrap        append an idempotent FreePPT block to the host's
                     AGENTS.md / CLAUDE.md (never overwrites existing content)
  --uninstall        move installed FreePPT dirs to a timestamped backup
  --refresh-cache    if WorkBuddy's skill-list cache does not watch freeppt,
                     touch one watched plugin SKILL.md (mtime only) to force
                     a full rescan
  --dry-run          print the plan, change nothing
  --no-check         skip the post-install unit/lint self-check
  -h, --help         show this help

Examples:
  ./install.sh --host all --scope user
  ./install.sh --host dsh --scope project --bootstrap
  ./install.sh --host claude --dry-run
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }
log() { printf '[freeppt] %s\n' "$*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST="${2:-}"; shift 2 ;;
    --scope) SCOPE="${2:-}"; shift 2 ;;
    --project-root) PROJECT_ROOT="${2:-}"; shift 2 ;;
    --bootstrap) BOOTSTRAP=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --refresh-cache) REFRESH_CACHE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-check) SELF_CHECK=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

case "$HOST" in
  workbuddy|claude|codex|cursor|dsh|all) ;;
  *) die "--host must be workbuddy|claude|codex|cursor|dsh|all" ;;
esac
case "$SCOPE" in
  user|project) ;;
  *) die "--scope must be user|project" ;;
esac
[ -f "$SRC/SKILL.md" ] || die "SKILL.md not found next to install.sh ($SRC)"
[ -d "$SRC/engine" ] || die "engine/ not found next to install.sh ($SRC)"

ALL_HOSTS="workbuddy claude codex cursor dsh"
[ "$HOST" = "all" ] || ALL_HOSTS="$HOST"

# Per-host path resolution. Sets: P_USER, P_PROJECT, B_USER, B_PROJECT, VERIFIED
resolve_host() {
  local h="$1" dsh_home agents_home
  case "$h" in
    workbuddy)
      P_USER="$HOME/.workbuddy/skills/freeppt"
      P_PROJECT=""
      B_USER=""; B_PROJECT=""
      VERIFIED="measured" ;;
    claude)
      P_USER="$HOME/.claude/skills/freeppt"
      P_PROJECT="$PROJECT_ROOT/.claude/skills/freeppt"
      B_USER="$HOME/.claude/CLAUDE.md"; B_PROJECT="$PROJECT_ROOT/CLAUDE.md"
      VERIFIED="documented" ;;
    codex)
      P_USER="${HOME}/.agents/skills/freeppt"
      P_PROJECT="$PROJECT_ROOT/.agents/skills/freeppt"
      B_USER="$HOME/.codex/AGENTS.md"; B_PROJECT="$PROJECT_ROOT/AGENTS.md"
      VERIFIED="documented" ;;
    cursor)
      P_USER="$HOME/.cursor/skills/freeppt"
      P_PROJECT="$PROJECT_ROOT/.cursor/skills/freeppt"
      B_USER=""; B_PROJECT="$PROJECT_ROOT/AGENTS.md"
      VERIFIED="documented" ;;
    dsh)
      dsh_home="${DSH_HOME:-$HOME/.dsh}"
      agents_home="${DSH_AGENTS_HOME:-$HOME/.agents}"
      P_USER="$dsh_home/skills/freeppt"
      P_PROJECT="$PROJECT_ROOT/.dsh/skills/freeppt"
      B_USER="$dsh_home/AGENTS.md"; B_PROJECT="$PROJECT_ROOT/AGENTS.md"
      VERIFIED="documented"
      # DSH also discovers the shared ~/.agents/skills root; install there too
      # so both discovery ranks resolve to the same version.
      P_USER_EXTRA="$agents_home/skills/freeppt"
      return 0 ;;
    *) die "internal: unknown host $h" ;;
  esac
  P_USER_EXTRA=""
}

# Safety: only touch directories whose basename is freeppt and that live under
# a skills/ directory. This prevents a mistyped path from nuking something else.
assert_safe_target() {
  local p="$1"
  [ "$(basename "$p")" = "freeppt" ] || die "unsafe target (basename): $p"
  case "$p" in
    */skills/freeppt) ;;
    *) die "unsafe target (not under skills/): $p" ;;
  esac
}

copy_skill() {
  local dst="$1"
  assert_safe_target "$dst"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "DRY-RUN would install -> $dst"
    return 0
  fi
  mkdir -p "$dst"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.git/' --exclude '__pycache__/' --exclude '*.pyc' \
      --exclude '.DS_Store' --exclude '.pytest_cache/' \
      "$SRC/" "$dst/"
  else
    # portable fallback: overlay without deleting pre-existing files
    ( cd "$SRC" && tar -cf - \
        --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
        --exclude '.DS_Store' --exclude '.pytest_cache' . ) \
      | ( cd "$dst" && tar -xf - )
  fi
  log "installed -> $dst ($(find "$dst" -type f | wc -l | tr -d ' ') files)"
}

move_to_backup() {
  local dst="$1" stamp backup
  assert_safe_target "$dst"
  [ -d "$dst" ] || { log "not installed, skip: $dst"; return 0; }
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup="$BACKUP_DIR/freeppt-$stamp-$(printf '%s' "$dst" | cksum | cut -d' ' -f1)"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "DRY-RUN would move $dst -> $backup"
    return 0
  fi
  mkdir -p "$BACKUP_DIR"
  mv "$dst" "$backup"
  log "uninstalled: moved -> $backup (nothing deleted)"
}

BEGIN_MARK='<!-- BEGIN FreePPT bootstrap -->'
END_MARK='<!-- END FreePPT bootstrap -->'

append_bootstrap() {
  local f="$1" skill_path="$2"
  [ -n "$f" ] || return 0
  if [ "$DRY_RUN" -eq 1 ]; then
    log "DRY-RUN would append bootstrap block -> $f"
    return 0
  fi
  if [ -f "$f" ] && grep -qF "$BEGIN_MARK" "$f"; then
    log "bootstrap already present, skipped: $f"
    return 0
  fi
  mkdir -p "$(dirname "$f")"
  {
    [ -f "$f" ] && printf '\n' >> "$f"
    printf '%s\n' "$BEGIN_MARK"
    printf '%s\n' "- FreePPT (freeppt) is installed at \`$skill_path\`. Read its SKILL.md when the user asks for PPT/PPTX/slides, says \"FreePPT\", provides reading notes, or supplies a book cover image."
    printf '%s\n' "- FreePPT pipeline is fixed: planning -> generate DSL -> layout -> lint -> compile/render. Run \`python3 engine/cli.py lint <deck.json>\` before \`build\`; do not bypass the lint gate."
    printf '%s\n' "- Pure CLI (no LLM, no network): \`python3 engine/cli.py make \"<brief>\" --type weekly --out out.pptx\`."
    printf '%s\n' "$END_MARK"
  } >> "$f"
  log "bootstrap appended -> $f"
}

# Several hosts share ~/.agents/skills/. Install each distinct path once.
INSTALLED_PATHS=""

install_once() {
  local dst="$1"
  if printf '%s\n' "$INSTALLED_PATHS" | grep -Fxq "$dst"; then
    log "already installed this run, skipped: $dst"
    return 0
  fi
  copy_skill "$dst"
  INSTALLED_PATHS="$(printf '%s\n%s\n' "$INSTALLED_PATHS" "$dst")"
}

# WorkBuddy's skill-list cache is only invalidated by changes to paths in its
# watch list. That list does not always include the user skills dir, so we
# check it explicitly instead of assuming an update is auto-discovered.
workbuddy_cache_check() {
  local cache="$HOME/.workbuddy/.skill-list-cache.json" state
  [ -f "$cache" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  python3 - "$cache" <<'PY' >/dev/null 2>&1
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    paths = d.get("watch", {}).get("dirs", []) + d.get("watch", {}).get("files", [])
    sys.exit(0 if any("freeppt" in p for p in paths) else 1)
except Exception:
    sys.exit(2)
PY
  state=$?
  [ "$state" -eq 0 ] && { log "skill-list cache already watches freeppt"; return 0; }
  [ "$state" -eq 2 ] && { log "skill-list cache unreadable; skipping check"; return 0; }
  if [ "$REFRESH_CACHE" -eq 1 ]; then
    local f
    f="$(python3 - "$cache" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for p in d.get("watch", {}).get("files", []):
    if p.endswith("SKILL.md") and not p.startswith("/Applications/"):
        print(p)
        break
PY
)"
    if [ -n "$f" ] && [ -f "$f" ]; then
      touch -m "$f"
      log "cache signature invalidated via $f (mtime only); refresh the skill list"
    else
      log "could not find a watched SKILL.md; refresh the skill list manually"
    fi
  else
    log "NOTE: skill-list cache does not watch freeppt yet."
    log "      Re-run with --refresh-cache, or refresh the skill list in settings."
  fi
}

self_check() {
  local dst="$1"
  [ "$SELF_CHECK" -eq 1 ] || return 0
  [ "$DRY_RUN" -eq 1 ] && return 0
  command -v python3 >/dev/null 2>&1 || {
    log "python3 not found; skipping self-check"; return 0; }
  log "self-check: unit tests"
  ( cd "$dst" && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q ) \
    || die "unit tests failed in $dst"
  log "self-check: lint example deck"
  ( cd "$dst" && PYTHONDONTWRITEBYTECODE=1 python3 engine/cli.py lint examples/demo.json >/dev/null ) \
    || die "lint failed in $dst"
  log "self-check: OK"
}

echo "FreePPT installer | source: $SRC | host: $HOST | scope: $SCOPE"
[ "$DRY_RUN" -eq 1 ] && echo "DRY-RUN: no files will be changed"
echo

CHECKED=""
for h in $ALL_HOSTS; do
  resolve_host "$h"
  if [ "$SCOPE" = "project" ]; then
    TARGET="$P_PROJECT"
    BOOT="$B_PROJECT"
    [ -n "$TARGET" ] || {
      log "$h has no project-scope skill path; skipping (use --scope user)"; continue; }
    if [ "$DRY_RUN" -eq 0 ]; then
      mkdir -p "$PROJECT_ROOT" || die "cannot create project root: $PROJECT_ROOT"
    fi
  else
    TARGET="$P_USER"
    BOOT="$B_USER"
  fi
  echo "[$h] status: $VERIFIED (see docs/PUBLISHING.md)"
  echo "[$h] target: $TARGET"
  [ "$VERIFIED" = "measured" ] || \
    echo "[$h] note: path from official docs, not locally installed/verified on this machine"

  if [ "$UNINSTALL" -eq 1 ]; then
    move_to_backup "$TARGET"
    [ -n "${P_USER_EXTRA:-}" ] && [ "$SCOPE" = "user" ] && move_to_backup "$P_USER_EXTRA"
    continue
  fi

  install_once "$TARGET"
  if [ -n "${P_USER_EXTRA:-}" ] && [ "$SCOPE" = "user" ]; then
    echo "[$h] shared root: $P_USER_EXTRA"
    install_once "$P_USER_EXTRA"
  fi
  if [ "$BOOTSTRAP" -eq 1 ]; then
    append_bootstrap "$BOOT" "$TARGET"
  fi
  # Only run the (slow) self-check once for the first real install.
  if [ -z "$CHECKED" ] && [ "$DRY_RUN" -eq 0 ]; then
    self_check "$TARGET"
    CHECKED="$TARGET"
  fi
done

echo
if [ "$UNINSTALL" -eq 1 ]; then
  echo "Uninstall done. Backups are under $BACKUP_DIR (nothing was deleted)."
else
  echo "Install done."
  echo "  --dry-run to preview paths; --bootstrap to append AGENTS.md/CLAUDE.md hints."
  echo "  WorkBuddy: a skill-list cache may need a refresh (use --refresh-cache"
  echo "  if the cached version is stale)."
  echo "  Verify: python3 engine/cli.py lint examples/demo.json"
fi

if [ "$UNINSTALL" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  for h in $ALL_HOSTS; do
    [ "$h" = "workbuddy" ] && { workbuddy_cache_check; break; }
  done
fi
