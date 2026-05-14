#!/usr/bin/env python3
r"""
proof-audit Phase 1 — auto-extract claims.json from a (possibly multi-file)
LaTeX manuscript.

The orchestrating Claude session normally produces claims.json with judgment
(curated titles, dependency graph, etc.). This script is a deterministic
fallback that handles the typical case: walk the root .tex, follow every
`\input{path}` / `\include{path}` recursively, find every `\begin{<env>}` of
a known claim kind that has a `\label{...}` nearby, and emit one claim per
match.

Each claim's `file_line` is qualified with the actual sub-file:
    "file_line": "supp/theory_full.tex:42"

This lets `package_claims.py` slice the right file even when the root
manuscript only `\input`s its content from elsewhere — solving the multi-file
limitation surfaced during one-shot validation.

Usage:
    extract_claims.py --root main.tex --out proof_audit/claims.json
                      [--include-kinds lemma,theorem,proposition,corollary,...]
                      [--exclude-remarks]
                      [--max-label-search 8]

The output validates against the claim shape package_claims.py reads:
    {
      "manuscript": "main.tex",                 # root, for legacy compatibility
      "files": ["main.tex", "sections/...", ...],
      "total_lines": 4500,                      # virtual sum across files
      "claims": [
        {"claim_id": "C1", "label": "...", "kind": "lemma", "title": "...",
         "file_line": "supp/theory_full.tex:42",
         "appendix_section": "...", "depends_on": []}
      ]
    }
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


DEFAULT_KINDS = (
    "lemma", "proposition", "theorem", "corollary",
    "definition", "assumption", "fact", "claim", "remark",
)

RE_INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")
RE_SECTION = re.compile(r"\\(section|subsection|subsubsection|paragraph)\*?\{([^}]+)\}")
RE_LABEL = re.compile(r"\\label\{([^}]+)\}")
# Claim env: \begin{lemma}[Optional title]
RE_BEGIN_TEMPLATE = r"\\begin\{(%s)\}(?:\[([^\]]*)\])?"
# Cross-claim refs (used to populate depends_on)
RE_REF = re.compile(r"\\(?:ref|eqref|Cref|cref|autoref)\{([^}]+)\}")
CLAIM_LABEL_PREFIXES = (
    "lem:", "thm:", "prop:", "cor:", "def:",
    "ass:", "assu:", "fact:", "rem:", "claim:",
)


# ---------------------------------------------------------------------------
# Multi-file resolution
# ---------------------------------------------------------------------------
def resolve_input_path(root_dir: Path, raw: str) -> Path:
    """Resolve a `\\input{path}` argument to an actual .tex file path.

    Tries (in order): exact path, path+'.tex'.  Returns None-equivalent
    (path that doesn't exist) on failure — caller should check.
    """
    candidate = (root_dir / raw).resolve()
    if candidate.exists():
        return candidate
    if not raw.endswith(".tex"):
        candidate2 = (root_dir / (raw + ".tex")).resolve()
        if candidate2.exists():
            return candidate2
    return candidate  # return the bad path; caller checks .exists()


def walk_inputs(root_tex: Path, root_dir: Path,
                seen: Set[Path] = None) -> List[Tuple[Path, List[str]]]:
    """Walk the root .tex following \\input{} recursively. Returns a list of
    (file_path, lines) tuples in DOCUMENT ORDER (i.e., the order each file
    actually appears in the rendered output).

    Cycle protection via `seen`. Missing files emit a warning (printed to
    stderr) and are skipped.
    """
    if seen is None:
        seen = set()
    out: List[Tuple[Path, List[str]]] = []
    if not root_tex.exists():
        print(f"WARN: input file {root_tex} not found, skipping", file=sys.stderr)
        return out
    if root_tex in seen:
        return out
    seen.add(root_tex)

    lines = root_tex.read_text(encoding="utf-8", errors="replace").split("\n")
    # Walk lines; for each line, emit the line; if it has \input, splice in
    # the included file's contents BEFORE continuing.
    out.append((root_tex, lines))
    for raw_line in lines:
        for m in RE_INPUT.finditer(raw_line):
            inc = resolve_input_path(root_dir, m.group(1))
            if inc.exists() and inc not in seen:
                out.extend(walk_inputs(inc, root_dir, seen))
            elif not inc.exists():
                print(f"WARN: \\input{{{m.group(1)}}} not found "
                      f"(tried {inc}), skipping", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------
def extract_from_file(
    file_path: Path,
    root_dir: Path,
    kinds_pattern: re.Pattern,
    max_label_search: int,
) -> List[Dict[str, Any]]:
    """Scan one .tex file for claim envs and return their structured form.

    file_line is `relative/path.tex:LINE` (1-indexed) — relative to root_dir
    so the resulting claims.json is portable.
    """
    rel = file_path.relative_to(root_dir) if file_path.is_relative_to(root_dir) else file_path
    rel_str = str(rel)
    lines = file_path.read_text(encoding="utf-8", errors="replace").split("\n")
    out: List[Dict[str, Any]] = []
    current_section: str = ""
    for i, line in enumerate(lines):  # 0-indexed
        # Update section context from any \section/\subsection on this line
        sm = RE_SECTION.search(line)
        if sm:
            current_section = sm.group(2)

        bm = kinds_pattern.search(line)
        if not bm:
            continue
        kind, title = bm.group(1), bm.group(2) or ""
        # Search current line + next `max_label_search` lines for \label
        label = ""
        for j in range(i, min(len(lines), i + max_label_search + 1)):
            lm = RE_LABEL.search(lines[j])
            if lm:
                label = lm.group(1)
                break
        if not label:
            continue
        out.append({
            "label": label,
            "kind": kind,
            "title": title,
            "file_line": f"{rel_str}:{i + 1}",
            "appendix_section": current_section,
        })
    return out


def extract_all(
    root_tex: Path,
    kinds: List[str],
    max_label_search: int,
) -> Dict[str, Any]:
    """Extract claims across the root tex and all \\input'd files."""
    root_dir = root_tex.parent.resolve()
    # `walk_inputs` returns files in document order, possibly with duplicates
    # when a sub-file is `\input`'d more than once.  Dedup by realpath.
    files_in_order = walk_inputs(root_tex, root_dir)
    seen_paths: Set[Path] = set()
    unique_files: List[Tuple[Path, List[str]]] = []
    for fp, lines in files_in_order:
        rp = fp.resolve()
        if rp in seen_paths:
            continue
        seen_paths.add(rp)
        unique_files.append((fp, lines))

    pattern = re.compile(RE_BEGIN_TEMPLATE % "|".join(re.escape(k) for k in kinds))

    claims: List[Dict[str, Any]] = []
    cid = 1
    for fp, _lines in unique_files:
        for c in extract_from_file(fp, root_dir, pattern, max_label_search):
            c["claim_id"] = f"C{cid}"
            c["depends_on"] = []  # filled in by the post-pass below
            claims.append(c)
            cid += 1

    # Build a label -> claim_id index for the depends_on post-pass
    label_to_cid = {c["label"]: c["claim_id"] for c in claims}

    # Post-pass: for each claim, scan its statement+proof in its own file for
    # \ref/\eqref/\Cref of OTHER claim labels. We don't have package boundaries
    # yet (package_claims.py figures those out), so we approximate: take 200
    # lines starting at the claim's file_line as the search window.
    for c in claims:
        try:
            file_part, line_part = c["file_line"].rsplit(":", 1)
            claim_line = int(line_part)
        except (ValueError, KeyError):
            continue
        full_path = root_dir / file_part
        if not full_path.exists():
            continue
        body = "\n".join(
            full_path.read_text(encoding="utf-8", errors="replace")
            .split("\n")[max(0, claim_line - 1): claim_line + 200]
        )
        deps: List[str] = []
        seen_local: Set[str] = set()
        for m in RE_REF.finditer(body):
            lab = m.group(1)
            if lab == c["label"] or lab in seen_local:
                continue
            if not any(lab.startswith(p) for p in CLAIM_LABEL_PREFIXES):
                continue
            if lab in label_to_cid:
                deps.append(lab)
                seen_local.add(lab)
        c["depends_on"] = deps

    return {
        "manuscript": str(root_tex.relative_to(Path.cwd())
                           if root_tex.is_relative_to(Path.cwd())
                           else root_tex),
        "files": [
            str(fp.relative_to(root_dir)) if fp.is_relative_to(root_dir) else str(fp)
            for fp, _ in unique_files
        ],
        "total_lines": sum(len(lines) for _, lines in unique_files),
        "claims": claims,
        "_extraction_note": (
            "Auto-extracted by extract_claims.py. Titles are taken verbatim "
            "from \\begin{<env>}[<title>]; depends_on is the union of \\ref / "
            "\\eqref / \\Cref of claim-like labels in the next 200 lines after "
            "each claim. For curated titles + deeper dependency analysis, run "
            "Phase 1 with LLM judgment in the orchestrating session."
        ),
    }


def _cmd_extract(args):
    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: {root} does not exist", file=sys.stderr)
        sys.exit(2)
    kinds = [k.strip() for k in args.include_kinds.split(",") if k.strip()]
    if args.exclude_remarks and "remark" in kinds:
        kinds.remove("remark")
    doc = extract_all(root, kinds, args.max_label_search)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    n_files = len(doc["files"])
    n_claims = len(doc["claims"])
    n_with_deps = sum(1 for c in doc["claims"] if c.get("depends_on"))
    from collections import Counter
    by_kind = Counter(c["kind"] for c in doc["claims"])
    print(f"Wrote {args.out}: {n_claims} claims across {n_files} files "
          f"({doc['total_lines']} total lines)")
    print(f"  by kind: {dict(by_kind)}")
    print(f"  with non-empty depends_on: {n_with_deps}/{n_claims}")


def main():
    ap = argparse.ArgumentParser(
        description="proof-audit Phase 1 auto-extractor"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("extract", help="walk root tex and emit claims.json")
    p.add_argument("--root", required=True,
                   help="root .tex file (entry point; e.g. main.tex)")
    p.add_argument("--out", default="proof_audit/claims.json")
    p.add_argument("--include-kinds", default=",".join(DEFAULT_KINDS),
                   help=f"comma-separated env names (default: {','.join(DEFAULT_KINDS)})")
    p.add_argument("--exclude-remarks", action="store_true",
                   help="convenience: drop 'remark' from include-kinds")
    p.add_argument("--max-label-search", type=int, default=8,
                   help="how many lines after \\begin{<env>} to search for \\label")
    p.set_defaults(func=_cmd_extract)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
