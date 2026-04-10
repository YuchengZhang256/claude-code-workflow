#!/usr/bin/env bash
# install.sh — install claude-code-workflow into ~/.claude/
#
# Usage:
#   install.sh              # dry-run: prints what would happen, touches nothing
#   install.sh --apply      # actually copy files
#   install.sh --force      # overwrite existing files (dangerous — backs them up first)
#
# Idempotent and safe by default. Never overwrites without --force. Always
# backs up existing files to <file>.backup.<timestamp> before overwriting.
set -euo pipefail
shopt -s nullglob

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
APPLY=0
FORCE=0
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

say() { printf '%s\n' "$*"; }
dryrun_tag() { [ "$APPLY" = "1" ] && printf '' || printf '[dry-run] '; }

do_copy() {
  local src="$1"
  local dst="$2"
  if [ -e "$dst" ] && [ "$FORCE" = "0" ]; then
    say "  $(dryrun_tag)skip   $dst  (already exists — use --force to overwrite)"
    return
  fi
  if [ -e "$dst" ] && [ "$FORCE" = "1" ]; then
    say "  $(dryrun_tag)backup $dst -> $dst.backup.$TIMESTAMP"
    [ "$APPLY" = "1" ] && cp -a "$dst" "$dst.backup.$TIMESTAMP"
  fi
  say "  $(dryrun_tag)copy   $src -> $dst"
  if [ "$APPLY" = "1" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
  fi
}

do_copy_tree() {
  local src="$1"
  local dst="$2"
  if [ -e "$dst" ] && [ "$FORCE" = "0" ]; then
    say "  $(dryrun_tag)skip   $dst  (already exists — use --force to overwrite)"
    return
  fi
  if [ -e "$dst" ] && [ "$FORCE" = "1" ]; then
    # Atomic overwrite: (1) copy new tree to a staging path next to the target,
    # (2) rename the existing dst to a timestamped backup, (3) rename staging
    # into place. If any step fails the previous state is preserved.
    local staging="$dst.staging.$TIMESTAMP"
    local backup="$dst.backup.$TIMESTAMP"
    say "  $(dryrun_tag)stage  $src/ -> $staging/"
    say "  $(dryrun_tag)backup $dst -> $backup"
    say "  $(dryrun_tag)swap   $staging -> $dst"
    if [ "$APPLY" = "1" ]; then
      mkdir -p "$(dirname "$dst")"
      cp -a "$src" "$staging"
      mv "$dst" "$backup"
      mv "$staging" "$dst"
    fi
    return
  fi
  say "  $(dryrun_tag)copy   $src/ -> $dst/"
  if [ "$APPLY" = "1" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
  fi
}

say "claude-code-workflow installer"
say "  repo:       $REPO_DIR"
say "  target:     $CLAUDE_DIR"
if [ "$APPLY" = "0" ]; then
  say "  mode:       DRY-RUN  (pass --apply to actually install)"
else
  say "  mode:       APPLY"
fi
say ""

# --- Skills -------------------------------------------------------------------
say "Skills -> $CLAUDE_DIR/skills/"
for skill_dir in "$REPO_DIR/skills"/*/; do
  name="$(basename "$skill_dir")"
  # Only treat a directory as a skill if it contains SKILL.md. Prevents future
  # non-skill directories (assets/, testdata/, examples/) from being installed
  # as skills by mistake.
  if [ ! -f "$skill_dir/SKILL.md" ]; then
    say "  skip   $name  (no SKILL.md — not a skill directory)"
    continue
  fi
  do_copy_tree "$REPO_DIR/skills/$name" "$CLAUDE_DIR/skills/$name"
done
say ""

# --- Global CLAUDE.md ---------------------------------------------------------
say "Global CLAUDE.md -> $CLAUDE_DIR/CLAUDE.md"
if [ -e "$CLAUDE_DIR/CLAUDE.md" ] && [ "$FORCE" = "0" ]; then
  say "  $(dryrun_tag)skip   $CLAUDE_DIR/CLAUDE.md  (already exists)"
  say "           → review dotclaude/CLAUDE.md.template and merge by hand,"
  say "             or re-run with --force to back up and replace."
else
  do_copy "$REPO_DIR/dotclaude/CLAUDE.md.template" "$CLAUDE_DIR/CLAUDE.md"
fi
say ""

# --- settings.json (only if missing) ------------------------------------------
say "Settings -> $CLAUDE_DIR/settings.json"
if [ -e "$CLAUDE_DIR/settings.json" ]; then
  say "  $(dryrun_tag)skip   $CLAUDE_DIR/settings.json  (already exists — never overwritten)"
else
  do_copy "$REPO_DIR/dotclaude/settings.json.example" "$CLAUDE_DIR/settings.json"
fi
say ""

# --- Memory templates (add-only, never overwrite) -----------------------------
say "Memory templates (add-only) -> $CLAUDE_DIR/projects/<yourproject>/memory/"
say "  Memory files are project-scoped and should be placed under the correct"
say "  project directory. This installer does not auto-detect the project;"
say "  see dotclaude/memory/ for templates you can copy into place manually."
say ""

# --- Executable bits on skill scripts -----------------------------------------
say "Marking skill scripts executable"
for script in "$REPO_DIR/skills"/*/scripts/*.sh "$REPO_DIR/skills"/*/scripts/*.py; do
  [ -e "$script" ] || continue
  rel="${script#"$REPO_DIR/skills/"}"
  target="$CLAUDE_DIR/skills/$rel"
  if [ "$APPLY" = "1" ] && [ -e "$target" ]; then
    chmod +x "$target"
    say "  chmod +x $target"
  else
    say "  $(dryrun_tag)chmod +x $target"
  fi
done
say ""

if [ "$APPLY" = "0" ]; then
  say "Dry-run complete. Re-run with --apply to actually install."
else
  say "Install complete."
  say "Next steps:"
  say "  1. Edit $CLAUDE_DIR/CLAUDE.md and fill in the top user-context section"
  say "  2. Run: $REPO_DIR/scripts/sanity-check.sh"
  say "  3. Smoke-test: bash $CLAUDE_DIR/skills/web-access/scripts/fetch.sh https://example.com"
fi
