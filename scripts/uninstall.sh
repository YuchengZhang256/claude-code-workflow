#!/usr/bin/env bash
# uninstall.sh — remove claude-code-workflow skills from ~/.claude/
#
# Usage:
#   uninstall.sh              # dry-run: prints what would be removed
#   uninstall.sh --apply      # actually remove
#
# This script removes ONLY the skills and templates that this repo
# installed. It never touches:
#   - ~/.claude/CLAUDE.md  (your own rules, potentially modified)
#   - ~/.claude/settings.json
#   - any memory files
#   - any other skills you installed separately
#
# If you want to remove CLAUDE.md, do it by hand.
set -euo pipefail
shopt -s nullglob

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
APPLY=0

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
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

# Owned skills = every directory under this repo's skills/ that has a SKILL.md.
# Derived from the filesystem so adding a new skill never requires editing
# this file.
OWNED_SKILLS=()
for skill_md in "$REPO_DIR/skills"/*/SKILL.md; do
  OWNED_SKILLS+=("$(basename "$(dirname "$skill_md")")")
done

say "claude-code-workflow uninstaller"
say "  target: $CLAUDE_DIR"
if [ "$APPLY" = "0" ]; then
  say "  mode:   DRY-RUN  (pass --apply to actually remove)"
else
  say "  mode:   APPLY"
fi
say ""

for skill in "${OWNED_SKILLS[@]}"; do
  dir="$CLAUDE_DIR/skills/$skill"
  if [ -d "$dir" ]; then
    say "  $(dryrun_tag)rm -rf $dir"
    [ "$APPLY" = "1" ] && rm -rf "$dir"
  else
    say "  $(dryrun_tag)skip   $dir  (not present)"
  fi
done
say ""

say "Note: ~/.claude/CLAUDE.md, settings.json, and memory files were NOT touched."
say "      Remove them by hand if you want a complete cleanup."
