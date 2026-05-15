#!/usr/bin/env python3
"""
research-wiki tag canonicalization analysis (read-only, no auto-fix).

Long-running wikis accumulate one-shot tags ("tag drift"). This script
reads all tags across a wiki, groups them by frequency, and for each rare
tag (singleton or 2-3 uses) suggests a candidate merge target from the set
of high-frequency tags.

It DOES NOT modify any pages. Output is a markdown report you review,
edit, and apply by hand (or via Claude with explicit instructions).

Matching strategy (conservative — judgment errors should be obvious):
  - exact_substring     rare tag contains an existing top tag as substring
                        ("matrix-concentration" contains "concentration")
  - token_overlap       rare tag shares a hyphen-token with a top tag
                        ("information-theoretic" shares "information" with
                         "information-theory")
  - no_match            no syntactic candidate; leave for human judgment

Semantic similarity is NOT used (too aggressive — "isoperimetry" should
not be merged into "concentration" even though they're related concepts).

Usage:
    tag_canon.py <wiki-dir> [--top-threshold 5] [--rare-threshold 3]
        Default: a tag is "top" if used 5+ times, "rare" if used <=3 times.

The report goes to stdout. Pipe to a file if you want.
"""

import argparse
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

# Reuse the mini frontmatter parser from lint.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint import load_pages  # noqa: E402


def collect_tags(pages):
    """Return (tag_freq Counter, tag_pages dict[tag -> list[page_name]])."""
    freq = Counter()
    pages_for = defaultdict(list)
    for name, (_, _, fm, _) in pages.items():
        if name in ("log", "index"):
            continue
        for t in fm.get("tags") or []:
            freq[t] += 1
            pages_for[t].append(name)
    return freq, pages_for


def tokens(tag: str) -> set:
    """Hyphen-split tokens, lowercased."""
    return set(t for t in tag.lower().split("-") if t)


def suggest_merge(rare_tag: str, top_tags: list) -> tuple:
    """Return (suggestion, kind) where kind is one of:
        'exact_substring' | 'token_overlap' | 'no_match'
    suggestion is the recommended top tag (or None if no_match).
    """
    rl = rare_tag.lower()
    rt = tokens(rare_tag)
    # Tier 1: rare contains a top tag as substring (or vice versa for hyphenated)
    for top in top_tags:
        tl = top.lower()
        if tl == rl:
            continue
        # rare tag contains top tag as a token-aligned substring
        if tl in rl and (rl.startswith(tl + "-") or rl.endswith("-" + tl) or "-" + tl + "-" in rl):
            return (top, "exact_substring")
        # rare tag IS a substring of a top tag (less common)
        if rl in tl and (tl.startswith(rl + "-") or tl.endswith("-" + rl) or "-" + rl + "-" in tl):
            return (top, "exact_substring")
    # Tier 2: token overlap
    best = None
    best_score = 0
    for top in top_tags:
        tt = tokens(top)
        common = rt & tt
        if not common:
            continue
        # Score: number of shared tokens, prefer higher-frequency top tag
        score = len(common)
        if score > best_score:
            best_score = score
            best = top
    if best:
        return (best, "token_overlap")
    return (None, "no_match")


def main():
    ap = argparse.ArgumentParser(description="research-wiki tag canonicalization analysis")
    ap.add_argument("wiki_dir", help="path to wiki/ directory")
    ap.add_argument("--top-threshold", type=int, default=5,
                    help="tags used >= this many times are 'top' (default 5)")
    ap.add_argument("--rare-threshold", type=int, default=3,
                    help="tags used <= this many times are 'rare' (default 3)")
    args = ap.parse_args()

    wiki_dir = Path(args.wiki_dir).expanduser().resolve()
    if not wiki_dir.is_dir():
        print(f"ERROR: {wiki_dir} not a directory", file=sys.stderr)
        sys.exit(2)

    pages = load_pages(wiki_dir)
    freq, pages_for = collect_tags(pages)
    top_tags = sorted([t for t, n in freq.items() if n >= args.top_threshold],
                      key=lambda t: -freq[t])
    rare_tags = sorted([t for t, n in freq.items() if n <= args.rare_threshold],
                       key=lambda t: (freq[t], t))
    mid_tags = [t for t, n in freq.items()
                if args.rare_threshold < n < args.top_threshold]

    # Bucket suggestions
    by_suggestion = defaultdict(list)  # suggested_top_tag -> list of (rare_tag, kind, count, page)
    no_match = []
    for r in rare_tags:
        suggestion, kind = suggest_merge(r, top_tags)
        if suggestion is None:
            no_match.append((r, freq[r], pages_for[r]))
        else:
            by_suggestion[suggestion].append((r, kind, freq[r], pages_for[r]))

    # Print report
    print(f"# Tag canonicalization report — {wiki_dir}")
    print()
    print(f"- total unique tags: **{len(freq)}**")
    print(f"- top tags (used ≥{args.top_threshold}× ): **{len(top_tags)}**")
    print(f"- mid-frequency tags ({args.rare_threshold + 1}–{args.top_threshold - 1}× ): **{len(mid_tags)}**")
    print(f"- rare tags (≤{args.rare_threshold}× ): **{len(rare_tags)}**")
    print()
    print("## Top tags (the canonical pool)")
    print()
    for t in top_tags[:25]:
        print(f"- `{t}` ({freq[t]}×)")
    if len(top_tags) > 25:
        print(f"- _… +{len(top_tags) - 25} more_")
    print()

    print("## Suggested merges (rare → top)")
    print()
    print("Sorted by canonical target. **Each row is a suggestion only — review before applying.**")
    print()
    for tgt in sorted(by_suggestion, key=lambda t: -freq[t]):
        rares = by_suggestion[tgt]
        print(f"### → `{tgt}` ({freq[tgt]}×)")
        print()
        print("| rare tag | kind | uses | on page(s) |")
        print("|---|---|---:|---|")
        for r, kind, n, pgs in rares:
            pg_str = ", ".join(f"`{p}`" for p in pgs[:3])
            if len(pgs) > 3:
                pg_str += f", _+{len(pgs) - 3}_"
            print(f"| `{r}` | {kind} | {n} | {pg_str} |")
        print()

    print(f"## No-match rare tags ({len(no_match)})")
    print()
    print("These have no syntactic overlap with any top tag — likely genuinely unique.")
    print("Either keep as-is, promote to top tag if the concept recurs, or delete.")
    print()
    print("| rare tag | uses | on page(s) |")
    print("|---|---:|---|")
    for r, n, pgs in no_match:
        pg_str = ", ".join(f"`{p}`" for p in pgs[:3])
        if len(pgs) > 3:
            pg_str += f", _+{len(pgs) - 3}_"
        print(f"| `{r}` | {n} | {pg_str} |")


if __name__ == "__main__":
    main()
