#!/usr/bin/env python3
"""
research-wiki lint — five mechanical checks on a Karpathy-style wiki dir.

Usage:
    lint.py <wiki-dir>          # e.g. ~/research/network-science/wiki

Checks (each runs in <1s on a 100-page wiki):

  1. orphan        page has no incoming [[wikilinks]] from any other page
                   (excluding index, log, and synthesis/* hub pages)
  2. broken_link   [[foo]] in some page where wiki/**/foo.md does not exist
  3. stub          page body has <150 words
  4. frontmatter   page missing one of: title, type, created, updated
  5. sourceless    page under concepts/ with empty `sources:` frontmatter
                   (pre-seeded scaffolding signal)

Output: plain stdout, grouped by category. No markdown decoration, no
auto-fix. Exit code 0 always (lint is informational; the LLM / user
decides what to act on).
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

RE_LINK = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]")
RE_FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
REQUIRED_FRONTMATTER_FIELDS = {"title", "type", "created", "updated"}
EXCLUDE_FROM_ORPHAN = {"index", "log"}  # plus synthesis/* via path check
STUB_WORD_THRESHOLD = 150


def parse_frontmatter(block: str) -> dict:
    """Minimal YAML-frontmatter parser. Handles the wiki's flat schema:
        key: value
        key: "string with spaces"
        key: []
        key: ["item one", "item two"]
        key: [item-one, item-two]
    Returns {} on empty or malformed input. No PyYAML dep needed.
    """
    out = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                out[key] = []
            else:
                items = [p.strip().strip('"').strip("'") for p in inner.split(",")]
                out[key] = [it for it in items if it]
        elif raw.startswith('"') and raw.endswith('"'):
            out[key] = raw[1:-1]
        elif raw.startswith("'") and raw.endswith("'"):
            out[key] = raw[1:-1]
        else:
            out[key] = raw
    return out


def load_pages(wiki_dir: Path):
    """Return dict mapping bare-name -> (path, raw_text, frontmatter_dict, body)."""
    pages = {}
    for p in wiki_dir.rglob("*.md"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = RE_FRONTMATTER.match(text)
        fm = {}
        body = text
        if m:
            fm = parse_frontmatter(m.group(1))
            body = text[m.end():]
        pages[p.stem] = (p, text, fm, body)
    return pages


def find_orphans(pages):
    """Pages with no incoming wikilink, excluding meta/synthesis hubs."""
    incoming = defaultdict(set)
    for name, (_, text, _, _) in pages.items():
        for m in RE_LINK.finditer(text):
            tgt = m.group(1).strip()
            if tgt in pages and tgt != name:
                incoming[tgt].add(name)
    out = []
    for name, (path, _, _, _) in pages.items():
        if name in EXCLUDE_FROM_ORPHAN:
            continue
        if "synthesis" in path.parts:
            continue
        if name not in incoming:
            out.append(name)
    return sorted(out)


def find_broken_links(pages):
    """[[tgt]] where tgt is not a known page name. Returns (src, tgt) pairs."""
    out = []
    for src_name, (_, text, _, _) in pages.items():
        seen = set()
        for m in RE_LINK.finditer(text):
            tgt = m.group(1).strip()
            if tgt in pages or tgt in seen:
                continue
            out.append((src_name, tgt))
            seen.add(tgt)
    return out


def find_stubs(pages):
    """Page body has <STUB_WORD_THRESHOLD words."""
    out = []
    for name, (_, _, _, body) in pages.items():
        if name in EXCLUDE_FROM_ORPHAN:
            continue
        word_count = len(body.split())
        if word_count < STUB_WORD_THRESHOLD:
            out.append((name, word_count))
    return sorted(out, key=lambda x: x[1])


def find_frontmatter_drift(pages):
    """Pages missing required frontmatter fields."""
    out = []
    for name, (_, _, fm, _) in pages.items():
        missing = REQUIRED_FRONTMATTER_FIELDS - set(fm.keys())
        if missing:
            out.append((name, sorted(missing)))
    return sorted(out)


def find_sourceless_concepts(pages):
    """Concept pages with empty `sources:` — pre-seeded scaffolding signal."""
    out = []
    for name, (path, _, fm, _) in pages.items():
        if "concepts" not in path.parts:
            continue
        sources = fm.get("sources") or []
        if not sources:
            out.append(name)
    return sorted(out)


def report(wiki_dir, results):
    """Print a grouped stdout report."""
    issue_keys = [k for k in results if not k.startswith("_")]
    n = sum(len(results[k]) for k in issue_keys)
    print(f"=== research-wiki lint: {wiki_dir} ===")
    print(f"checked {results['_n_pages']} pages, {n} issue(s) across {len(issue_keys)} categories")
    print()

    if results["orphans"]:
        print(f"# orphans ({len(results['orphans'])})  — pages with no incoming [[wikilinks]]")
        for name in results["orphans"]:
            print(f"  - {name}")
        print()

    if results["broken_links"]:
        print(f"# broken_links ({len(results['broken_links'])})  — [[tgt]] points to nonexistent page")
        for src, tgt in results["broken_links"]:
            print(f"  - in {src}.md: [[{tgt}]]")
        print()

    if results["stubs"]:
        print(f"# stubs ({len(results['stubs'])})  — body <{STUB_WORD_THRESHOLD} words")
        for name, wc in results["stubs"]:
            print(f"  - {name} ({wc} words)")
        print()

    if results["frontmatter"]:
        print(f"# frontmatter_drift ({len(results['frontmatter'])})  — missing required fields")
        for name, missing in results["frontmatter"]:
            print(f"  - {name}: missing {missing}")
        print()

    if results["sourceless"]:
        print(f"# sourceless_concepts ({len(results['sourceless'])})  — concept page with empty sources:")
        for name in results["sourceless"]:
            print(f"  - {name}")
        print()

    if n == 0:
        print("(clean)")


def main():
    if len(sys.argv) != 2:
        print("Usage: lint.py <wiki-dir>", file=sys.stderr)
        sys.exit(2)
    wiki_dir = Path(sys.argv[1]).expanduser().resolve()
    if not wiki_dir.exists() or not wiki_dir.is_dir():
        print(f"ERROR: {wiki_dir} is not a directory", file=sys.stderr)
        sys.exit(2)

    pages = load_pages(wiki_dir)
    results = {
        "_n_pages":     len(pages),
        "orphans":      find_orphans(pages),
        "broken_links": find_broken_links(pages),
        "stubs":        find_stubs(pages),
        "frontmatter":  find_frontmatter_drift(pages),
        "sourceless":   find_sourceless_concepts(pages),
    }
    report(wiki_dir, results)


if __name__ == "__main__":
    main()
