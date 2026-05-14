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


def find_proof_cross_file(
    target_label: str,
    extra_files: List[Tuple[Path, List[str]]],
) -> Optional[Tuple[Path, int, int]]:
    """Find a `\\begin{proof}[Proof of <Kind>~\\ref{target_label}]...\\end{proof}`
    block across other files. Returns (file_path, 0-idx start, 0-idx end) or None.

    Common pattern in math papers with statement/proof split:
        statements live in supp/theory_full.tex
        proofs live in supp/theory_proofs.tex
        each proof opens with `\\begin{proof}[Proof of Lemma~\\ref{lem:foo}]`
    """
    # Match `\begin{proof}[ ... \ref{<label>} ... ]` (allow Cref/cref/eqref too)
    proof_for_label = re.compile(
        r"\\begin\{proof\}\[[^\]]*\\(?:ref|Cref|cref|eqref)\{"
        + re.escape(target_label) + r"\}[^\]]*\]"
    )
    for path, file_lines in extra_files:
        for i, line in enumerate(file_lines):
            if proof_for_label.search(line):
                try:
                    end = find_matching_end(file_lines, i, "proof")
                    return (path, i, end)
                except ValueError:
                    continue
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
def parse_file_line(file_line_str: str) -> Tuple[Optional[str], Optional[int]]:
    """Split `file_line` into (path_or_None, line_or_None).

    Accepts:
      "sections/foo.tex:42"  -> ("sections/foo.tex", 42)
      "42"                   -> (None, 42)
      ""                     -> (None, None)
    Multi-file aware. The path part lets package_claims read the right file
    when a manuscript is composed of many \\input'd sub-files.
    """
    if not file_line_str:
        return None, None
    if ":" not in file_line_str:
        try:
            return None, int(file_line_str)
        except ValueError:
            return None, None
    head, tail = file_line_str.rsplit(":", 1)
    try:
        return head, int(tail)
    except ValueError:
        return file_line_str, None


def build_package(claim: Dict[str, Any], lines: List[str],
                  manuscript_path: str,
                  context_lines: int,
                  extra_files: Optional[List[Tuple[Path, List[str]]]] = None,
                  ) -> Dict[str, Any]:
    """Build one package dict for `claim`.

    `lines` are the lines of the FILE that contains this claim (as parsed
    from `file_line`). For single-file manuscripts this is the same as the
    global manuscript; for multi-file manuscripts the caller passes in the
    sub-file's lines for each claim. `manuscript_path` is recorded in the
    package for human readers.
    """
    warnings: List[str] = []
    label = claim.get("label", "")
    kind = claim.get("kind", "")
    file_line_str = claim.get("file_line", "")

    file_path_in_str, file_line_1 = parse_file_line(file_line_str)
    if file_line_1 is None:
        # Fall back to scanning whole file for the label
        file_line_1 = 1
        warnings.append(
            "no parseable line in file_line; scanning whole manuscript for label"
        )

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

    # Step 4: find subsequent proof block (in-file)
    proof = find_proof_after(lines, stmt_end_idx, max_skip=30)
    proof_start_idx = proof[0] if proof else None
    proof_end_idx = proof[1] if proof else None
    proof_lines = lines  # which file's lines correspond to proof_start/end
    proof_file_path = manuscript_path  # default: proof in same file as statement

    # Step 4b: if no in-file proof and we have extra_files to search, look for
    # a `\begin{proof}[Proof of <Kind>~\ref{<label>}]` block elsewhere.
    # Skip kinds that conventionally have no proof (definition/assumption/etc).
    NEEDS_PROOF = {"lemma", "theorem", "proposition", "corollary"}
    info: List[str] = []
    if proof is None and kind in NEEDS_PROOF and extra_files and label:
        cross = find_proof_cross_file(label, extra_files)
        if cross is not None:
            xfile, xstart, xend = cross
            proof_start_idx = xstart
            proof_end_idx = xend
            proof_lines = None  # marker: proof lives in a different file
            proof_file_path = str(xfile)
            # Informational, not a warning — found cross-file proof successfully
            info.append(
                f"proof located in separate file {xfile.name} "
                f"(lines {xstart + 1}-{xend + 1}); statement-proof split detected"
            )

    if proof_start_idx is None and kind not in {"definition", "remark", "assumption", "fact"}:
        warnings.append(f"no \\begin{{proof}} found within 30 lines of \\end{{{env_name}}} "
                        "(and no cross-file proof block referenced this label)")

    return _assemble_package(
        claim, lines, manuscript_path, context_lines,
        stmt_start_idx, stmt_end_idx,
        proof_start=proof_start_idx, proof_end=proof_end_idx,
        warnings=warnings,
        info=info,
        proof_lines=proof_lines,
        proof_file_path=proof_file_path if proof_lines is None else manuscript_path,
        extra_files=extra_files,
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
    info: Optional[List[str]] = None,
    proof_lines: Optional[List[str]] = None,
    proof_file_path: Optional[str] = None,
    extra_files: Optional[List[Tuple[Path, List[str]]]] = None,
) -> Dict[str, Any]:
    """Build the final package dict from already-resolved 0-indexed line ranges.

    `proof_lines is None` means the proof lives in a different file than the
    statement (cross-file pairing); we look it up in `extra_files`. If
    `proof_lines is the SAME object as `lines`, the proof is in-file.
    """
    n = len(lines)
    cross_file_proof = proof_lines is None

    # Resolve cross-file proof_lines for slicing
    if cross_file_proof and proof_file_path and extra_files:
        for path, file_lines in extra_files:
            if str(path) == proof_file_path:
                proof_lines = file_lines
                break
    if proof_lines is None:
        proof_lines = lines  # fallback (should not happen if extra_files set)

    # Context windows (clamp to FILE bounds; cross-file proofs use proof file's
    # context_after, in-file proofs use statement file's context_after)
    ctx_before_start = max(0, stmt_start - context_lines)
    ctx_before_end = max(ctx_before_start, stmt_start - 1)
    if cross_file_proof:
        # Statement file context_after is just after stmt_end
        ctx_after_start = min(n - 1, stmt_end + 1)
        ctx_after_end = min(n - 1, stmt_end + context_lines)
        # Proof file context comes around the proof
        proof_n = len(proof_lines)
        proof_ctx_before_start = max(0, (proof_start or 0) - context_lines)
        proof_ctx_before_end = max(proof_ctx_before_start, (proof_start or 0) - 1)
        proof_ctx_after_start = min(proof_n - 1, (proof_end or 0) + 1)
        proof_ctx_after_end = min(proof_n - 1, (proof_end or 0) + context_lines)
    else:
        body_end = proof_end if proof_end is not None else stmt_end
        ctx_after_start = min(n - 1, body_end + 1)
        ctx_after_end = min(n - 1, body_end + context_lines)
        proof_ctx_before_start = proof_ctx_before_end = None
        proof_ctx_after_start = proof_ctx_after_end = None

    # Collect hypertargets: statement always from `lines`, proof from `proof_lines`
    hypers = collect_hypertargets(lines, stmt_start, stmt_end)
    if proof_start is not None and proof_end is not None:
        hypers = hypers + collect_hypertargets(proof_lines, proof_start, proof_end)

    # Phase β.1.1 — auto-extract depends_on from \ref/\eqref/\Cref of
    # claim-like labels in statement+proof. Merge with any depends_on already
    # in claims.json (manual or LLM-extracted), preserving manual order.
    self_lbl = claim.get("label", "")
    auto_deps = collect_referenced_claim_labels(
        lines, stmt_start, stmt_end, self_label=self_lbl
    )
    if proof_start is not None and proof_end is not None:
        proof_deps = collect_referenced_claim_labels(
            proof_lines, proof_start, proof_end, self_label=self_lbl
        )
        seen = set(auto_deps)
        for d in proof_deps:
            if d not in seen:
                auto_deps.append(d)
                seen.add(d)
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

    def _slice(arr: List[str], a: int, b: int) -> str:
        if b < a:
            return ""
        return "\n".join(arr[a : b + 1])

    pkg: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "claim_id": claim.get("claim_id", ""),
        "label": claim.get("label", ""),
        "kind": claim.get("kind", ""),
        "title": claim.get("title", ""),
        "manuscript": manuscript_path,
        "proof_file": proof_file_path or manuscript_path,
        "cross_file_proof": bool(cross_file_proof),
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
        "statement_text": _slice(lines, stmt_start, stmt_end),
        "proof_text": (
            _slice(proof_lines, proof_start, proof_end)
            if proof_start is not None else ""
        ),
        "context_before_text": _slice(lines, ctx_before_start, ctx_before_end),
        "context_after_text": _slice(lines, ctx_after_start, ctx_after_end),
        "warnings": warnings,
        "info": info or [],
    }
    if cross_file_proof and proof_ctx_before_start is not None:
        # Surface the proof file's surrounding context too — the auditor often
        # needs to see what's around the proof, not just around the statement.
        pkg["proof_context_before_text"] = _slice(
            proof_lines, proof_ctx_before_start, proof_ctx_before_end
        )
        pkg["proof_context_after_text"] = _slice(
            proof_lines, proof_ctx_after_start, proof_ctx_after_end
        )

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
    # The "root" for resolving file_line paths is the directory containing the
    # root manuscript. For single-file mode this is just where the .tex lives;
    # for multi-file mode, sub-files are referenced relative to this dir.
    root_dir = tex_path.parent.resolve()

    # Per-file line cache. Read each .tex on demand (claims may live in
    # different sub-files for multi-file manuscripts).
    lines_cache: Dict[str, List[str]] = {}

    def _lines_for(rel_path: Optional[str]) -> Tuple[Path, List[str]]:
        """Return (resolved_path, lines) for the file referenced by rel_path.
        rel_path=None means use the global manuscript."""
        if rel_path is None or rel_path == "":
            key = str(tex_path.resolve())
            if key not in lines_cache:
                lines_cache[key] = tex_path.read_text(
                    encoding="utf-8", errors="replace"
                ).split("\n")
            return tex_path, lines_cache[key]
        # Resolve sub-file relative to root_dir
        cand = (root_dir / rel_path).resolve()
        key = str(cand)
        if key in lines_cache:
            return cand, lines_cache[key]
        if cand.exists():
            lines_cache[key] = cand.read_text(
                encoding="utf-8", errors="replace"
            ).split("\n")
            return cand, lines_cache[key]
        # Fallback: try the path as-is from cwd
        cand2 = Path(rel_path).resolve()
        if cand2.exists():
            key2 = str(cand2)
            if key2 not in lines_cache:
                lines_cache[key2] = cand2.read_text(
                    encoding="utf-8", errors="replace"
                ).split("\n")
            return cand2, lines_cache[key2]
        # Last resort: use root manuscript and let build_package warn
        key3 = str(tex_path.resolve())
        if key3 not in lines_cache:
            lines_cache[key3] = tex_path.read_text(
                encoding="utf-8", errors="replace"
            ).split("\n")
        return tex_path, lines_cache[key3]

    only_set = set()
    if args.only:
        only_set = {x.strip() for x in args.only.split(",") if x.strip()}

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    manifest_entries: List[Dict[str, Any]] = []
    n_built = 0
    n_warned = 0
    # Pre-load all files referenced by claims so cross-file proof search has
    # them available. This is a single-pass enrichment (not lazy) because
    # the proof finder needs the whole list anyway.
    referenced_files: Set[str] = set()
    for claim in claims_list:
        fp_str, _ = parse_file_line(claim.get("file_line", ""))
        if fp_str:
            referenced_files.add(fp_str)
    # Also bring in any "files" field from claims.json (extract_claims.py
    # writes one). This ensures we know about proof-only files like
    # `supp/theory_proofs.tex` that don't host any statement.
    if isinstance(claims_doc, dict):
        for f in claims_doc.get("files") or []:
            referenced_files.add(f)
    for fp_str in referenced_files:
        _lines_for(fp_str)
    extra_files: List[Tuple[Path, List[str]]] = [
        (Path(k), v) for k, v in lines_cache.items()
    ]

    n_subfile_packages = 0
    for claim in claims_list:
        cid = claim.get("claim_id", "")
        if only_set and cid not in only_set:
            continue
        # Multi-file: pick the right tex for THIS claim from its file_line path
        file_path_in_str, _ = parse_file_line(claim.get("file_line", ""))
        actual_tex, actual_lines = _lines_for(file_path_in_str)
        if actual_tex != tex_path:
            n_subfile_packages += 1
        try:
            pkg = build_package(claim, actual_lines, str(actual_tex),
                                args.context_lines,
                                extra_files=extra_files)
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
        "subfile_packages": n_subfile_packages,
        "files_read": sorted(lines_cache.keys()),
        "entries": manifest_entries,
    }
    (outdir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    print(f"Built {n_built} package(s) -> {outdir}")
    print(f"  warnings: {n_warned} package(s)")
    if n_subfile_packages:
        print(f"  multi-file: {n_subfile_packages} package(s) sourced from "
              f"{len(lines_cache) - 1} sub-file(s) (not the root manuscript)")
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
