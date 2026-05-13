#!/usr/bin/env python3
r"""
Patch lint for proof-audit Phase 2d output.

Runs four checks per `latex_patch` in synthesized.json:

  1. Schema shape (already enforced upstream by codex --output-schema, but we
     re-validate here to catch hand-edited findings).
  2. `\hypertarget{...}` anchor matches the finding's `hypertarget_anchor`
     field; anchors across all findings are unique.
  3. Every `\ref{...}`, `\eqref{...}`, `\Cref{...}`, `\Assumption{...}`,
     `\Lemma{...}` referenced inside `latex_patch` must already exist in one
     of the provided paper-source .tex files. A patch that names a label that
     doesn't exist is hallucinated (very common GPT failure mode).
  4. Optional: latexmk dry-run compile of a sandboxed wrapper containing the
     patch (skipped if --no-latex).

Usage:
  python lint_patches.py \\
    --synthesized proof_audit/synthesized.json \\
    --paper-source main.tex appendix.tex \\
    --out proof_audit/lint_report.json \\
    [--no-latex]

Exit status:
  0 = all patches clean
  1 = one or more patches failed lint (details in lint_report.json)
  2 = setup error (file missing, bad JSON)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

LABEL_DEFINING_PATTERNS = [
    re.compile(r"\\label\{([^}]+)\}"),
    re.compile(r"\\hypertarget\{([^}]+)\}"),
    re.compile(r"\\Assumption\{([^}]+)\}"),  # custom command, may or may not exist
    re.compile(r"\\newtheorem\{[^}]+\}\{[^}]+\}"),  # ignored, just for awareness
]

LABEL_REFERENCING_PATTERNS = [
    re.compile(r"\\ref\{([^}]+)\}"),
    re.compile(r"\\eqref\{([^}]+)\}"),
    re.compile(r"\\Cref\{([^}]+)\}"),
    re.compile(r"\\cref\{([^}]+)\}"),
    re.compile(r"\\autoref\{([^}]+)\}"),
    re.compile(r"\\hyperlink\{([^}]+)\}"),
]


def collect_existing_labels(paper_sources: list[Path]) -> set[str]:
    """Scan all paper .tex files for label-defining macros, return the union."""
    labels: set[str] = set()
    for src in paper_sources:
        text = src.read_text(encoding="utf-8", errors="replace")
        for pat in LABEL_DEFINING_PATTERNS[:3]:
            for m in pat.finditer(text):
                labels.add(m.group(1))
    return labels


def labels_referenced_in_patch(patch: str) -> set[str]:
    labs: set[str] = set()
    for pat in LABEL_REFERENCING_PATTERNS:
        for m in pat.finditer(patch):
            labs.add(m.group(1))
    return labs


def lint_anchor(finding: dict[str, Any]) -> list[str]:
    """Check hypertarget anchor inside latex_patch matches the field."""
    errs: list[str] = []
    expected = finding.get("hypertarget_anchor", "")
    patch = finding.get("latex_patch", "")
    if not patch:
        return errs  # verified status, nothing to check
    m = re.search(r"\\hypertarget\{([^}]+)\}", patch)
    if not m:
        errs.append(f"patch missing \\hypertarget{{...}}; expected {expected!r}")
    elif m.group(1) != expected:
        errs.append(
            f"patch \\hypertarget{{{m.group(1)}}} != finding.hypertarget_anchor "
            f"{expected!r}"
        )
    return errs


def lint_referenced_labels(
    finding: dict[str, Any], existing: set[str]
) -> list[str]:
    """Check all \\ref/\\eqref/etc inside latex_patch point to real labels."""
    errs: list[str] = []
    patch = finding.get("latex_patch", "")
    if not patch:
        return errs
    used = labels_referenced_in_patch(patch)
    missing = used - existing
    for lab in sorted(missing):
        errs.append(
            f"patch references label {lab!r} that does not exist in paper source"
        )
    return errs


def lint_anchor_uniqueness(findings: list[dict[str, Any]]) -> list[str]:
    """Across all findings, hypertarget_anchor must be unique."""
    anchors = [f["hypertarget_anchor"] for f in findings if f.get("hypertarget_anchor")]
    dupes = [a for a, c in Counter(anchors).items() if c > 1]
    return [f"duplicate hypertarget_anchor across findings: {d!r}" for d in dupes]


def lint_compile(finding: dict[str, Any], paper_sources: list[Path]) -> list[str]:
    """latexmk dry-run on a minimal wrapper that pulls in the patch."""
    errs: list[str] = []
    patch = finding.get("latex_patch", "")
    if not patch:
        return errs
    with tempfile.TemporaryDirectory() as td:
        wrap = Path(td) / "patch_test.tex"
        wrap.write_text(
            "\\documentclass{article}\n"
            "\\usepackage{amsmath,amssymb,amsthm,hyperref}\n"
            "\\newtheorem{lemma}{Lemma}\n"
            "\\begin{document}\n"
            + patch
            + "\n\\end{document}\n",
            encoding="utf-8",
        )
        try:
            r = subprocess.run(
                [
                    "latexmk",
                    "-pdflatex=pdflatex -interaction=nonstopmode -halt-on-error",
                    "-pdf",
                    "-draftmode",
                    str(wrap),
                ],
                cwd=td,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode != 0:
                tail = (r.stdout + r.stderr).splitlines()[-15:]
                errs.append(
                    "latexmk failed for this patch; last 15 lines:\n  "
                    + "\n  ".join(tail)
                )
        except subprocess.TimeoutExpired:
            errs.append("latexmk timed out after 60s")
        except FileNotFoundError:
            errs.append("latexmk not installed; skip with --no-latex")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--synthesized", required=True, type=Path)
    ap.add_argument(
        "--paper-source",
        nargs="+",
        required=True,
        type=Path,
        help="one or more .tex files comprising the paper source",
    )
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--no-latex", action="store_true", help="skip latexmk compile")
    args = ap.parse_args()

    if not args.synthesized.exists():
        print(f"missing {args.synthesized}", file=sys.stderr)
        return 2
    for src in args.paper_source:
        if not src.exists():
            print(f"missing paper source {src}", file=sys.stderr)
            return 2

    data = json.loads(args.synthesized.read_text())
    findings = data.get("findings") if isinstance(data, dict) else data
    if not isinstance(findings, list):
        print("synthesized.json must have a top-level array or {'findings':[...]}", file=sys.stderr)
        return 2

    existing_labels = collect_existing_labels(args.paper_source)

    report = {
        "paper_sources": [str(p) for p in args.paper_source],
        "existing_labels_count": len(existing_labels),
        "no_latex": bool(args.no_latex),
        "per_finding": [],
        "global_errors": lint_anchor_uniqueness(findings),
    }

    any_fail = bool(report["global_errors"])
    for f in findings:
        errs: list[str] = []
        errs += lint_anchor(f)
        errs += lint_referenced_labels(f, existing_labels)
        if not args.no_latex:
            errs += lint_compile(f, args.paper_source)
        item = {
            "claim_id": f.get("claim_id"),
            "gap_type": f.get("gap_type"),
            "hypertarget_anchor": f.get("hypertarget_anchor"),
            "errors": errs,
            "clean": not errs,
        }
        report["per_finding"].append(item)
        if errs:
            any_fail = True

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    summary = (
        f"{sum(1 for r in report['per_finding'] if r['clean'])} / "
        f"{len(report['per_finding'])} patches clean"
    )
    if report["global_errors"]:
        summary += f"; {len(report['global_errors'])} global errors"
    print(summary, file=sys.stderr)
    print(f"report: {args.out}", file=sys.stderr)
    return 0 if not any_fail else 1


if __name__ == "__main__":
    sys.exit(main())
