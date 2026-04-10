#!/usr/bin/env bash
# new-wiki.sh — bootstrap a new research wiki from the starter template.
#
# Usage:
#   new-wiki.sh <target-directory> [<domain-name>]
#
# Example:
#   new-wiki.sh ~/research/causal-inference "causal inference"
set -euo pipefail

TARGET="${1:-}"
DOMAIN="${2:-TODO-fill-in-domain}"

if [ -z "$TARGET" ]; then
  cat >&2 <<EOF
Usage: $0 <target-directory> [<domain-name>]

Bootstraps a new Karpathy-style research wiki at <target-directory> by
copying the starter from this repo. The target directory must not exist.
EOF
  exit 1
fi

if [ -e "$TARGET" ]; then
  echo "Error: $TARGET already exists. Refusing to overwrite." >&2
  exit 2
fi

# Locate the starter relative to this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STARTER="$(cd "$SCRIPT_DIR/../../../examples/research-wiki-starter" 2>/dev/null && pwd)" || {
  echo "Error: cannot locate examples/research-wiki-starter relative to $SCRIPT_DIR" >&2
  echo "Expected layout: <repo>/examples/research-wiki-starter and <repo>/skills/research-wiki/scripts/" >&2
  exit 3
}

mkdir -p "$TARGET"
cp -r "$STARTER"/. "$TARGET"/

# Fill in the domain name in CLAUDE.md and wiki/index.md. sed is POSIX so it
# is always available. Fail loudly if substitution breaks — a half-populated
# template is worse than a clear error.
sed -i.bak "s|<DOMAIN>|$DOMAIN|g" "$TARGET/CLAUDE.md" "$TARGET/wiki/index.md"
rm -f "$TARGET/CLAUDE.md.bak" "$TARGET/wiki/index.md.bak"

# Initialize git. Optional — if git is not installed or commit fails, warn
# but do not fail the bootstrap (the user still has a populated directory).
if command -v git >/dev/null 2>&1; then
  if ! ( cd "$TARGET" && git init -q && git add -A && git commit -q -m "bootstrap $DOMAIN wiki" ); then
    echo "warning: git init/commit failed. Your wiki is populated but not versioned." >&2
    echo "         Investigate with: cd $TARGET && git status" >&2
  fi
else
  echo "warning: git not found — wiki populated but not versioned." >&2
fi

echo "Wiki bootstrapped at: $TARGET"
echo "Next steps:"
echo "  1. cd $TARGET"
echo "  2. Drop a paper into raw/"
echo "  3. Tell Claude: 'ingest raw/<paper>.pdf'"
