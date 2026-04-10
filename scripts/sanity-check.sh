#!/usr/bin/env bash
# sanity-check.sh — verify environment and installation state.
#
# Usage:
#   sanity-check.sh
#
# Prints:
#   ✓  required dependency present
#   ~  optional dependency absent (feature may be degraded)
#   ✗  required dependency missing
#
# Exits 0 if all required dependencies are present, 1 otherwise.
set -uo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
ANY_MISSING=0

check_required() {
  local name="$1"
  local cmd="$2"
  if command -v "$name" >/dev/null 2>&1; then
    printf '✓ %-18s %s\n' "$name" "($($cmd 2>&1 | head -1))"
  else
    printf '✗ %-18s NOT FOUND (required)\n' "$name"
    ANY_MISSING=1
  fi
}

check_optional() {
  local name="$1"
  local cmd="$2"
  local reason="$3"
  if command -v "$name" >/dev/null 2>&1; then
    printf '✓ %-18s %s\n' "$name" "($($cmd 2>&1 | head -1))"
  else
    printf '~ %-18s not found (optional — %s)\n' "$name" "$reason"
  fi
}

check_curl_impersonate() {
  for cand in /opt/homebrew/bin/curl_chrome* /usr/local/bin/curl_chrome* ; do
    if [ -x "$cand" ]; then
      printf '✓ %-18s %s\n' "curl-impersonate" "$cand"
      return
    fi
  done
  printf '~ %-18s not found (optional — install via: brew install curl-impersonate)\n' "curl-impersonate"
}

echo "== Required dependencies =="
check_required bash    "bash --version"
check_required curl    "curl --version"
check_required python3 "python3 --version"
check_required git     "git --version"
echo ""

echo "== Optional dependencies =="
check_optional pandoc "pandoc --version" "web-access falls back to html2text.py"
check_optional jq     "jq --version"     "web-access falls back to python for JSON"
check_curl_impersonate
echo ""

echo "== Skills installed at $CLAUDE_DIR/skills/ =="
# Expected skills are whatever skills/ in this repo provides (checked via SKILL.md).
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
shopt -s nullglob
if [ -d "$CLAUDE_DIR/skills" ]; then
  for skill_md in "$REPO_DIR/skills"/*/SKILL.md; do
    name="$(basename "$(dirname "$skill_md")")"
    if [ -d "$CLAUDE_DIR/skills/$name" ]; then
      printf '  ✓ %s\n' "$name"
    else
      printf '  ~ %s (not installed)\n' "$name"
    fi
  done
else
  printf '  (skills directory does not exist yet — run scripts/install.sh --apply)\n'
fi
echo ""

echo "== Global rules =="
if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
  printf '  ✓ %s present (%d lines)\n' "$CLAUDE_DIR/CLAUDE.md" "$(wc -l < "$CLAUDE_DIR/CLAUDE.md")"
else
  printf '  ~ %s missing (copy from dotclaude/CLAUDE.md.template)\n' "$CLAUDE_DIR/CLAUDE.md"
fi
echo ""

if [ "$ANY_MISSING" = "1" ]; then
  echo "FAIL — required dependencies missing."
  exit 1
fi
echo "OK — required dependencies present."
exit 0
