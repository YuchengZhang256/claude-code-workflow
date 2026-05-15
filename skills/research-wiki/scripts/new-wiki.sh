#!/usr/bin/env bash
# new-wiki.sh — bootstrap a new Karpathy-style research wiki.
#
# Usage:
#   new-wiki.sh <target-directory> [<domain-name>]
#
# Example:
#   new-wiki.sh ~/research/causal-inference "causal inference"
#
# Builds the wiki layout entirely from this skill's own templates/.  Previous
# versions tried to copy a `<repo>/examples/research-wiki-starter` directory
# that doesn't exist when the skill is installed standalone — those failed at
# step "locate starter".  This version assembles the wiki from templates +
# minimal inline skeletons, so it works from any install location.

set -euo pipefail

TARGET="${1:-}"
DOMAIN="${2:-research}"

if [ -z "$TARGET" ]; then
  cat >&2 <<EOF
Usage: $0 <target-directory> [<domain-name>]

Bootstraps a new Karpathy-style research wiki at <target-directory>:
  CLAUDE.md      <- per-wiki schema (from templates/per_wiki_CLAUDE.md)
  raw/           <- immutable source documents (you fill this)
  wiki/
    index.md     <- master catalog (minimal seed)
    log.md       <- operation log (with bootstrap entry)
    sources/    concepts/    entities/    comparisons/    synthesis/

The target directory must not already exist.

Example:
  $0 ~/research/community-detection "community detection"
EOF
  exit 1
fi

if [ -e "$TARGET" ]; then
  echo "Error: $TARGET already exists. Refusing to overwrite." >&2
  exit 2
fi

# Locate the skill's templates/ relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_DIR="$SKILL_DIR/templates"
PER_WIKI_TPL="$TEMPLATE_DIR/per_wiki_CLAUDE.md"

if [ ! -f "$PER_WIKI_TPL" ]; then
  echo "Error: per-wiki template not found at $PER_WIKI_TPL" >&2
  echo "       (skill install at $SKILL_DIR is incomplete)" >&2
  exit 3
fi

# Build directory skeleton
mkdir -p "$TARGET/raw"
mkdir -p "$TARGET/wiki/sources"
mkdir -p "$TARGET/wiki/concepts"
mkdir -p "$TARGET/wiki/entities"
mkdir -p "$TARGET/wiki/comparisons"
mkdir -p "$TARGET/wiki/synthesis"

# Per-wiki CLAUDE.md from template (substitute <DOMAIN>)
sed "s|<DOMAIN>|$DOMAIN|g" "$PER_WIKI_TPL" > "$TARGET/CLAUDE.md"

# Capitalized human title from domain for index.md
TITLE="$(echo "$DOMAIN" | awk '{for(i=1;i<=NF;i++)$i=toupper(substr($i,1,1))substr($i,2)}1')"
TODAY="$(date +%Y-%m-%d)"

# Minimal index.md
cat > "$TARGET/wiki/index.md" <<INDEX_EOF
---
title: "Wiki Index"
type: synthesis
created: $TODAY
updated: $TODAY
sources: []
related: []
tags: [meta, index]
---

# $TITLE Wiki — Index

> Master catalog of all wiki pages. Updated on every ingest.
> Read this first to find relevant pages before answering queries.

## Sources

_(empty — drop a paper into raw/ and ask Claude to ingest it)_

## Concepts

_(empty)_

## Entities

_(empty)_

## Comparisons

_(empty)_

## Synthesis

_(empty)_
INDEX_EOF

# Minimal log.md with bootstrap entry
cat > "$TARGET/wiki/log.md" <<LOG_EOF
# Operation Log

Append-only chronological log of wiki operations (ingest, query-filing, lint, structural changes).

## [$TODAY] bootstrap | $DOMAIN wiki created

Initialized empty wiki layout via \`new-wiki.sh\`:
- CLAUDE.md (from per-wiki template)
- raw/, wiki/{sources,concepts,entities,comparisons,synthesis}/
- wiki/index.md, wiki/log.md (this file)

Next steps:
1. Drop source PDFs / notes into \`raw/\`.
2. Tell Claude: "ingest raw/<file>" to compile it into the wiki.
3. Edit the "Domain-Specific Notes" section of CLAUDE.md as conventions emerge.

LOG_EOF

# Initialize git (best-effort, not fatal). Use existing repo identity if any.
if command -v git >/dev/null 2>&1; then
  (
    cd "$TARGET"
    git init -q
    git add -A
    git -c user.email="${GIT_AUTHOR_EMAIL:-$(git config --get user.email 2>/dev/null || echo nobody@local)}" \
        -c user.name="${GIT_AUTHOR_NAME:-$(git config --get user.name 2>/dev/null || echo nobody)}" \
        commit -q -m "bootstrap $DOMAIN wiki" || true
  )
fi

echo "Wiki bootstrapped at: $TARGET"
echo ""
echo "Layout:"
echo "  $TARGET/CLAUDE.md      <- per-wiki schema (edit Domain-Specific Notes as needed)"
echo "  $TARGET/raw/           <- drop sources here (immutable)"
echo "  $TARGET/wiki/          <- Claude will maintain pages here"
echo ""
echo "Next: cd $TARGET && drop a PDF into raw/ && tell Claude 'ingest raw/<file>'"
