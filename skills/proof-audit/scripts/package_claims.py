#!/usr/bin/env python3
"""
proof-audit claim packaging.

Pre-slices a manuscript .tex into per-claim packages so subagents (Pedantic /
Adversarial / Generous personas) can read a 100-300 line window per claim
instead of a 4000+ line manuscript. This addresses the recurring socket-fail
mode where the Adversarial persona dies after 9-15 Read tool calls.

A package contains, for one claim:
  * statement env (e.g. \\begin{lemma}...\\end{lemma})
  * proof env (\\begin{proof}...\\end{proof}) if any
  * +/- N lines of preceding/following context
  * the hypertarget anchors that were attached to this claim
  * cross-refs to depended-on claims (so the subagent can pull them too)
  * the original surrounding section header

Inputs:
  proof_audit/claims.json    (or whatever --claims points at)
  src/<manuscript>.tex       (path is read from claims.json's `manuscript`)

Outputs:
  proof_audit/claim_packages/{claim_id}.json   one file per claim
  proof_audit/claim_packages/_manifest.json    summary listing

Each package JSON conforms to:
{
  "schema_version": 1,
  "claim_id": "C1",
  "label": "lem:dd-degree-proxies",
  "kind": "lemma",
  "title": "Empirical degree proxies",
  "manuscript": "src/...tex",
  "appendix_section": "Sec. Data-driven tuning",
  "depends_on": [...],
  "stmt_start": 392,            # 1-indexed line numbers, inclusive
  "stmt_end": 421,
  "proof_start": 423,           # null if no proof block
  "proof_end": 453,
  "context_before_start": 342,  # max(1, stmt_start - context_lines)
  "context_before_end": 391,
  "context_after_start": 454,
  "context_after_end": 503,     # min(total_lines, proof_end + context_lines)
  "hypertargets": ["gap_C1v3_uniformity", ...],
  "section_header": "\\subsection{Data-driven tuning}",
  "statement_text": "...",
  "proof_text": "...",          # "" if no proof
  "context_before_text": "...",
  "context_after_text": "...",
  "warnings": [...]             # any heuristic match issues
}

CLI:
  package_claims.py build --claims proof_audit/claims.json
                           [--manuscript path.tex] [--outdir DIR]
                           [--context-lines 50] [--only C1,C5,...]
  package_claims.py inspect --package proof_audit/claim_packages/C1.json
  package_claims.py manifest --outdir proof_audit/claim_packages
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = 1
DEFAULT_CONTEXT_LINES = 50
DEFAULT_OUTDIR = "proof_audit/claim_packages"

# Environments we recognize as claim statements.
CLAIM_ENVS = {
    "lemma", "proposition", "theorem", "corollary",
    "definition", "remark", "fact", "claim",
    "assumption", "conjecture",
}

# Patterns
RE_BEGIN = re.compile(r"\\begin\{([A-Za-z*]+)\}")
RE_END = re.compile(r"\\end\{([A-Za-z*]+)\}")
RE_LABEL = re.compile(r"\\label\{([^}]+)\}")
RE_HYPER = re.compile(r"\\hypertarget\{([^}]+)\}")
RE_SECTION = re.compile(r"\\(section|subsection|subsubsection|paragraph)\*?\{([^}]+)\}")
RE_PROOF_BEGIN = re.compile(r"\\begin\{proof\}")
RE_PROOF_END = re.compile(r"\\end\{proof\}")

# Phase β.1.1 — auto-extract depends_on by scanning \ref / \eqref / \Cref /
# \cref inside the statement+proof text. Useful when claims.json (e.g. from
# auto-extraction) doesn't supply depends_on. Matches labels like
# `lem:foo`, `thm:bar`, `prop:baz`, `cor:qux`, `def:spam`, `ass:eggs`,
# `eq:something`, `fact:x`, `assu:y`. Excludes section/subsection/figure
# refs (sec:, fig:, tab:, alg:) which are not claims.
RE_REF = re.compile(
    r"\\(?:ref|eqref|Cref|cref|autoref)\{([^}]+)\}"
)
CLAIM_LABEL_PREFIXES = (
    "lem:", "thm:", "prop:", "cor:", "def:",
    "ass:", "assu:", "fact:", "rem:", "claim:",
)


# ---------------------------------------------------------------------------
# Environment matching with proper nesting
# ---------------------------------------------------------------------------
def find_matching_end(lines: List[str], start_idx: int, env_name: str) -> int:
    """Return the 0-indexed line of the matching \\end{env_name}.

    Handles nested same-name environments via a depth counter.
    Raises ValueError if no match is found before EOF.
    """
    depth = 0
    n = len(lines)
    # The line at start_idx contains \begin{env_name}; count it
    for i in range(start_idx, n):
        line = lines[i]
        for m in RE_BEGIN.finditer(line):
            if m.group(1) == env_name:
                depth += 1
        for m in RE_END.finditer(line):
            if m.group(1) == env_name:
                depth -= 1
                if depth == 0:
                    return i
    raise ValueError(f"no matching \\end{{{env_name}}} after line {start_idx + 1}")


def find_label_line(lines: List[str], target_label: str,
                    center_idx: int, window: int = 80) -> Optional[int]:
    """Search [center_idx-10, center_idx+window] for \\label{target_label}.

    Returns 0-indexed line number, or None if not found.
    """
    n = len(lines)
    lo = max(0, center_idx - 10)
    hi = min(n, center_idx + window)
    for i in range(lo, hi):
        for m in RE_LABEL.finditer(lines[i]):
            if m.group(1) == target_label:
                return i
    return None


def find_label_anywhere(lines: List[str], target_label: str) -> Optional[int]:
    """Whole-file scan for \\label{target_label}. Last-resort fallback when
    the manuscript has shifted significantly since claims.json was extracted.

    Returns 0-indexed line number, or None.
    """
    for i, line in enumerate(lines):
        for m in RE_LABEL.finditer(line):
            if m.group(1) == target_label:
                return i
    return None


def walk_back_to_begin(lines: List[str], from_idx: int,
                       expected_kind: str,
                       max_walk: int = 30) -> Optional[Tuple[int, str]]:
    """From `from_idx`, walk backwards to find the enclosing \\begin{<env>}.

    Prefers a match for `expected_kind` but accepts any CLAIM_ENVS env if no
    expected match is found within `max_walk` lines.

    Returns (0-indexed line, env_name) or None.
    """
    fallback = None
    lo = max(0, from_idx - max_walk)
    for i in range(from_idx, lo - 1, -1):
        for m in RE_BEGIN.finditer(lines[i]):
            env = m.group(1)
            if env == expected_kind:
                return (i, env)
            if env in CLAIM_ENVS and fallback is None:
                fallback = (i, env)
    return fallback


def find_proof_after(lines: List[str], stmt_end_idx: int,
                     max_skip: int = 30) -> Optional[Tuple[int, int]]:
    """Look for \\begin{proof}...\\end{proof} starting within `max_skip` lines
    after stmt_end_idx. Returns (0-idx start, 0-idx end) or None.

    Skips blank lines, comments, and forward-declared cross-references.
    """
    n = len(lines)
    hi = min(n, stmt_end_idx + 1 + max_skip)
    for i in range(stmt_end_idx + 1, hi):
        if RE_PROOF_BEGIN.search(lines[i]):
            try:
                end = find_matching_end(lines, i, "proof")
                return (i, end)
            except ValueError:
                return None
        # If we hit another claim env before finding a proof, give up
        for m in RE_BEGIN.finditer(lines[i]):
            if m.group(1) in CLAIM_ENVS:
                return None
    return None


def find_section_header(lines: List[str], before_idx: int,
                        max_walk: int = 1500) -> Optional[str]:
    """Walk backward from `before_idx` to find the most recent section header.
    Returns the raw line text, or None if none found within `max_walk` lines.

    The default 1500-line walk covers the worst case in practice: a long
    appendix section with many lemmas (osaa case study had a 504-line gap
    between the section header and one of its lemmas). Scanning lines is
    cheap — bump this if you encounter a paper with sections > 1500 lines.
    """
    lo = max(0, before_idx - max_walk)
    for i in range(before_idx, lo - 1, -1):
        m = RE_SECTION.search(lines[i])
        if m:
            # Return only the matched \section{...} / \paragraph{...} invocation,
            # NOT the full line. Important for inline \paragraph{Foo.} bodies that
            # would otherwise pollute the section_header field with body math.
            return m.group(0).rstrip()
    return None


def collect_hypertargets(lines: List[str], start_idx: int, end_idx: int) -> List[str]:
    """Collect all \\hypertarget{...} anchor names within [start_idx, end_idx]."""
    names: List[str] = []
    for i in range(start_idx, end_idx + 1):
        for m in RE_HYPER.finditer(lines[i]):
            names.append(m.group(1))
    return names


def collect_referenced_claim_labels(
    lines: List[str], start_idx: int, end_idx: int,
    self_label: str = "",
) -> List[str]:
    """Phase β.1.1 — scan \\ref/\\eqref/\\Cref/\\cref inside the span and
    return labels that look like claim labels (lem:/thm:/prop:/cor:/def:/
    ass:/...). Excludes the claim's own label and non-claim labels (sec:,
    fig:, tab:, alg:, eq:).

    Used to auto-populate `depends_on` when claims.json doesn't ship it.
    The Pedantic subagent on one-shot pointed out that empty depends_on
    forces the persona to either ignore dependencies or read the full
    manuscript — neither is good.
    """
    seen: List[str] = []
    seen_set: set = set()
    for i in range(start_idx, end_idx + 1):
        for m in RE_REF.finditer(lines[i]):
            lab = m.group(1)
            if lab == self_label or lab in seen_set:
                continue
            if not any(lab.startswith(p) for p in CLAIM_LABEL_PREFIXES):
                continue
            seen.append(lab)
            seen_set.add(lab)
    return seen


# ---------------------------------------------------------------------------
# Per-claim package builder
# ---------------------------------------------------------------------------
def build_package(claim: Dict[str, Any], lines: List[str],
                  manuscript_path: str,
                  context_lines: int) -> Dict[str, Any]:
    """Build one package dict for `claim`.

    `lines` are the manuscript file split by '\\n', preserving 0-indexed access.
    """
    warnings: List[str] = []
    label = claim.get("label", "")
    kind = claim.get("kind", "")
    file_line_str = claim.get("file_line", "")

    # Parse "src/foo.tex:389" -> 389 (1-indexed)
    file_line_1 = None
    if ":" in file_line_str:
        try:
            file_line_1 = int(file_line_str.rsplit(":", 1)[-1])
        except ValueError:
            warnings.append(f"could not parse file_line: {file_line_str!r}")
    if file_line_1 is None:
        # Fall back to scanning whole file for the label
        file_line_1 = 1
        warnings.append("no file_line; scanning whole manuscript for label")

    center_idx = max(0, file_line_1 - 1)  # 0-indexed

    # Step 1: find \label{<label>} near center_idx
    label_idx = None
    if label:
        label_idx = find_label_line(lines, label, center_idx, window=120)
        if label_idx is None:
            # Search wider as fallback
            label_idx = find_label_line(lines, label, center_idx, window=400)
            if label_idx is not None:
                warnings.append(
                    f"label found {abs(label_idx - center_idx)} lines from file_line "
                    f"(wider search); file_line may be stale"
                )
        if label_idx is None:
            # Last resort: full-file scan. Manuscript likely grew/shrank since
            # claims.json was extracted. Still a clean match.
            label_idx = find_label_anywhere(lines, label)
            if label_idx is not None:
                warnings.append(
                    f"label found via full-file scan at line {label_idx + 1} "
                    f"(file_line was {file_line_1}, off by {label_idx + 1 - file_line_1}); "
                    "claims.json is stale"
                )

    # Step 2: find enclosing \begin{<kind>}
    if label_idx is not None:
        anchor_idx = label_idx
    else:
        anchor_idx = center_idx
        warnings.append(f"label {label!r} not found; using file_line as anchor")

    begin_match = walk_back_to_begin(lines, anchor_idx, kind, max_walk=20)
    if begin_match is None:
        # Try a wider walk
        begin_match = walk_back_to_begin(lines, anchor_idx, kind, max_walk=80)
    if begin_match is None:
        # Try walking forward instead (file_line may point before the env)
        for i in range(anchor_idx, min(len(lines), anchor_idx + 50)):
            for m in RE_BEGIN.finditer(lines[i]):
                env = m.group(1)
                if env == kind or env in CLAIM_ENVS:
                    begin_match = (i, env)
                    break
            if begin_match is not None:
                break

    if begin_match is None:
        warnings.append(f"could not locate \\begin{{{kind}}} near line {file_line_1}")
        # Emit a degenerate package with just context window
        stmt_start = max(0, center_idx - context_lines)
        stmt_end = min(len(lines) - 1, center_idx + context_lines)
        return _assemble_package(
            claim, lines, manuscript_path, context_lines,
            stmt_start, stmt_end,
            proof_start=None, proof_end=None,
            warnings=warnings + ["degenerate package: no env match"],
        )

    stmt_start_idx, env_name = begin_match
    if env_name != kind:
        warnings.append(
            f"expected kind={kind!r} but matched env={env_name!r} at line {stmt_start_idx + 1}"
        )

    # Step 3: find matching \end{<env>}
    try:
        stmt_end_idx = find_matching_end(lines, stmt_start_idx, env_name)
    except ValueError as e:
        warnings.append(str(e))
        stmt_end_idx = min(len(lines) - 1, stmt_start_idx + 60)

    # Step 4: find subsequent proof block (optional)
    proof = find_proof_after(lines, stmt_end_idx, max_skip=30)
    if proof is None and kind not in {"definition", "remark", "assumption", "fact"}:
        warnings.append(f"no \\begin{{proof}} found within 30 lines of \\end{{{env_name}}}")
    proof_start_idx = proof[0] if proof else None
    proof_end_idx = proof[1] if proof else None

    return _assemble_package(
        claim, lines, manuscript_path, context_lines,
        stmt_start_idx, stmt_end_idx,
        proof_start=proof_start_idx, proof_end=proof_end_idx,
        warnings=warnings,
    )


def _assemble_package(
    claim: Dict[str, Any],
    lines: List[str],
    manuscript_path: str,
    context_lines: int,
    stmt_start: int,
    stmt_end: int,
    proof_start: Optional[int],
    proof_end: Optional[int],
    warnings: List[str],
) -> Dict[str, Any]:
    """Build the final package dict from already-resolved 0-indexed line ranges."""
    n = len(lines)

    # Context windows (clamp to file bounds; expand around proof if present)
    ctx_before_start = max(0, stmt_start - context_lines)
    ctx_before_end = max(ctx_before_start, stmt_start - 1)
    body_end = proof_end if proof_end is not None else stmt_end
    ctx_after_start = min(n - 1, body_end + 1)
    ctx_after_end = min(n - 1, body_end + context_lines)

    # Collect hypertargets across statement + proof
    span_end = proof_end if proof_end is not None else stmt_end
    hypers = collect_hypertargets(lines, stmt_start, span_end)

    # Phase β.1.1 — auto-extract depends_on from \ref/\eqref/\Cref of
    # claim-like labels in statement+proof. Merge with any depends_on already
    # in claims.json (manual or LLM-extracted), preserving manual order.
    auto_deps = collect_referenced_claim_labels(
        lines, stmt_start, span_end, self_label=claim.get("label", "")
    )
    manual_deps = list(claim.get("depends_on") or [])
    # Stable union: manual first, then any auto deps not already in manual
    seen = set(manual_deps)
    merged_deps = list(manual_deps)
    for d in auto_deps:
        if d not in seen:
            merged_deps.append(d)
            seen.add(d)

    # Section header (the most recent \section/\subsection above stmt_start)
    section_header = find_section_header(lines, stmt_start)

    def _slice(a: int, b: int) -> str:
        if b < a:
            return ""
        return "\n".join(lines[a : b + 1])

    pkg: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "claim_id": claim.get("claim_id", ""),
        "label": claim.get("label", ""),
        "kind": claim.get("kind", ""),
        "title": claim.get("title", ""),
        "manuscript": manuscript_path,
        "appendix_section": claim.get("appendix_section", ""),
        "depends_on": merged_deps,
        "depends_on_auto": auto_deps,  # diagnostic: only the auto-extracted refs
        "stmt_start": stmt_start + 1,           # 1-indexed for human use
        "stmt_end": stmt_end + 1,
        "proof_start": (proof_start + 1) if proof_start is not None else None,
        "proof_end": (proof_end + 1) if proof_end is not None else None,
        "context_before_start": ctx_before_start + 1,
        "context_before_end": ctx_before_end + 1,
        "context_after_start": ctx_after_start + 1,
        "context_after_end": ctx_after_end + 1,
        "hypertargets": hypers,
        "section_header": section_header,
        "statement_text": _slice(stmt_start, stmt_end),
        "proof_text": _slice(proof_start, proof_end) if proof_start is not None else "",
        "context_before_text": _slice(ctx_before_start, ctx_before_end),
        "context_after_text": _slice(ctx_after_start, ctx_after_end),
        "warnings": warnings,
    }

    # Total span (lines actually packaged) - useful metric for the manifest
    pkg["total_span_lines"] = (
        (stmt_end - stmt_start + 1)
        + ((proof_end - proof_start + 1) if proof_start is not None else 0)
        + (ctx_before_end - ctx_before_start + 1 if ctx_before_end >= ctx_before_start else 0)
        + (ctx_after_end - ctx_after_start + 1)
    )
    return pkg


# ---------------------------------------------------------------------------
# CLI: build / inspect / manifest
# ---------------------------------------------------------------------------
def _cmd_build(args):
    claims_path = Path(args.claims)
    if not claims_path.exists():
        print(f"ERROR: {claims_path} not found", file=sys.stderr)
        sys.exit(2)
    claims_doc = json.loads(claims_path.read_text())
    if isinstance(claims_doc, list):
        # Tolerate older schemas that emit a bare list of claims.
        claims_list = claims_doc
        manuscript_in_doc = None
    else:
        claims_list = claims_doc.get("claims", [])
        manuscript_in_doc = claims_doc.get("manuscript")

    manuscript_path = args.manuscript or manuscript_in_doc
    if not manuscript_path:
        print(
            "ERROR: --manuscript not given and claims.json has no `manuscript` field",
            file=sys.stderr,
        )
        sys.exit(2)
    tex_path = Path(manuscript_path)
    if not tex_path.exists():
        # Try resolving relative to claims.json's parent
        cand = claims_path.parent.parent / manuscript_path
        if cand.exists():
            tex_path = cand
        else:
            print(f"ERROR: manuscript {manuscript_path} not found", file=sys.stderr)
            sys.exit(2)
    lines = tex_path.read_text().split("\n")

    only_set = set()
    if args.only:
        only_set = {x.strip() for x in args.only.split(",") if x.strip()}

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    manifest_entries: List[Dict[str, Any]] = []
    n_built = 0
    n_warned = 0
    for claim in claims_list:
        cid = claim.get("claim_id", "")
        if only_set and cid not in only_set:
            continue
        try:
            pkg = build_package(claim, lines, str(tex_path), args.context_lines)
        except Exception as e:  # pragma: no cover - defensive
            pkg = {
                "schema_version": SCHEMA_VERSION,
                "claim_id": cid,
                "label": claim.get("label", ""),
                "warnings": [f"package build failed: {e}"],
            }
        out = outdir / f"{cid}.json"
        out.write_text(json.dumps(pkg, indent=2, ensure_ascii=False))
        n_built += 1
        if pkg.get("warnings"):
            n_warned += 1
        manifest_entries.append({
            "claim_id": cid,
            "label": pkg.get("label"),
            "kind": pkg.get("kind"),
            "title": pkg.get("title"),
            "stmt_start": pkg.get("stmt_start"),
            "stmt_end": pkg.get("stmt_end"),
            "proof_start": pkg.get("proof_start"),
            "proof_end": pkg.get("proof_end"),
            "total_span_lines": pkg.get("total_span_lines"),
            "hypertargets_count": len(pkg.get("hypertargets", [])),
            "warnings_count": len(pkg.get("warnings", [])),
            "package_path": str(out.relative_to(outdir.parent.parent))
            if outdir.is_absolute() is False else str(out),
        })

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "manuscript": str(tex_path),
        "claims_source": str(claims_path),
        "context_lines": args.context_lines,
        "total_packages": n_built,
        "packages_with_warnings": n_warned,
        "entries": manifest_entries,
    }
    (outdir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    print(f"Built {n_built} package(s) -> {outdir}")
    print(f"  warnings: {n_warned} package(s)")
    print(f"  manifest: {outdir / '_manifest.json'}")


def _cmd_inspect(args):
    pkg_path = Path(args.package)
    if not pkg_path.exists():
        print(f"ERROR: {pkg_path} not found", file=sys.stderr)
        sys.exit(2)
    pkg = json.loads(pkg_path.read_text())
    print(f"=== {pkg.get('claim_id')} ({pkg.get('kind')}) {pkg.get('label')} ===")
    print(f"Title:   {pkg.get('title')}")
    print(f"Section: {pkg.get('section_header')}")
    print(f"Statement: lines {pkg.get('stmt_start')}-{pkg.get('stmt_end')}")
    if pkg.get("proof_start"):
        print(f"Proof:     lines {pkg.get('proof_start')}-{pkg.get('proof_end')}")
    else:
        print("Proof:     (none)")
    print(f"Span:    {pkg.get('total_span_lines')} lines total (incl context)")
    print(f"Hypertargets: {pkg.get('hypertargets')}")
    print(f"Depends on:   {pkg.get('depends_on')}")
    if pkg.get("warnings"):
        print("WARNINGS:")
        for w in pkg["warnings"]:
            print(f"  - {w}")
    if args.show_text:
        print("\n--- statement_text ---")
        print(pkg.get("statement_text", ""))
        if pkg.get("proof_text"):
            print("\n--- proof_text ---")
            print(pkg.get("proof_text", ""))


def _cmd_manifest(args):
    mpath = Path(args.outdir) / "_manifest.json"
    if not mpath.exists():
        print(f"ERROR: {mpath} not found (run `build` first)", file=sys.stderr)
        sys.exit(2)
    manifest = json.loads(mpath.read_text())
    print(f"Manuscript: {manifest['manuscript']}")
    print(f"Claims:     {manifest['claims_source']}")
    print(f"Context:    +/-{manifest['context_lines']} lines")
    print(f"Packages:   {manifest['total_packages']}  (warnings: {manifest['packages_with_warnings']})")
    print()
    print(f"{'CID':<6}{'KIND':<14}{'LABEL':<40}{'STMT':<14}{'PROOF':<14}{'SPAN':<6}{'WARN'}")
    for e in manifest["entries"]:
        proof_range = f"{e['proof_start']}-{e['proof_end']}" if e.get("proof_start") else "-"
        warn_marker = "!" * min(3, e.get("warnings_count", 0))
        print(
            f"{e['claim_id']:<6}{e['kind']:<14}{e['label'][:39]:<40}"
            f"{e['stmt_start']}-{e['stmt_end']:<7}"
            f"{proof_range:<14}"
            f"{e.get('total_span_lines', '?'):<6}"
            f"{warn_marker}"
        )


def main():
    ap = argparse.ArgumentParser(description="proof-audit claim packaging")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="build per-claim packages from claims.json")
    p.add_argument("--claims", required=True)
    p.add_argument("--manuscript", default=None,
                   help="path to .tex; defaults to claims.json's `manuscript` field")
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    p.add_argument("--context-lines", type=int, default=DEFAULT_CONTEXT_LINES)
    p.add_argument("--only", default=None,
                   help="comma-separated claim_ids to package (default: all)")
    p.set_defaults(func=_cmd_build)

    p = sub.add_parser("inspect", help="pretty-print one package")
    p.add_argument("--package", required=True)
    p.add_argument("--show-text", action="store_true",
                   help="also print statement_text and proof_text")
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("manifest", help="print the package manifest table")
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    p.set_defaults(func=_cmd_manifest)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
