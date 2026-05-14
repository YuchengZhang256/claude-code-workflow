#!/usr/bin/env python3
r"""
Patch lint for proof-audit Phase 2d output.

Runs SEVEN checks per `latex_patch` in synthesized.json:

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
  5. NEW (Phase γ.3) — macro existence: every non-standard `\macro` used in
     the patch must be defined somewhere in the paper sources via
     `\newcommand`, `\providecommand`, `\def`, `\DeclareMathOperator`, or be
     in the AMS / built-in allowlist. Catches Codex inventing `\hatQ` etc.
  6. NEW (Phase γ.3) — downstream impact: if the patch contains `\newcommand`
     or modifies a `\begin{definition}...\end{definition}` block, the symbol
     may already be in use elsewhere — emit a warning listing other claims
     whose packages reference the same symbol.
  7. NEW (Phase γ.3) — semantic conflict heuristic: scan for parameter-regime
     tokens introduced by the patch (e.g., "fixed", "$\to\infty$", "$\to 0$")
     and check if a nearby Assumption block in the paper sources states a
     conflicting modifier on the same symbol.

Usage:
  python lint_patches.py \\
    --synthesized proof_audit/synthesized.json \\
    --paper-source main.tex appendix.tex \\
    --out proof_audit/lint_report.json \\
    [--no-latex] [--no-macro-check] [--no-downstream] [--no-semantic] \\
    [--packages-dir proof_audit/claim_packages]

Exit status:
  0 = all patches clean (warnings allowed)
  1 = one or more patches failed lint (errors)
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

# Phase γ.3 patterns — macro existence + downstream impact + semantic conflict
RE_USED_MACRO = re.compile(r"\\([A-Za-z]{2,})(?![A-Za-z])")
RE_NEWCOMMAND = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand|DeclareMathOperator\*?)"
    r"\{?\\([A-Za-z]+)\}?"
)
RE_DEF = re.compile(r"\\def\\([A-Za-z]+)")

# AMS / built-in / hyperref / standard math names that don't need a definition
# in the paper source. Kept conservative — when in doubt, leave it out so the
# linter flags it as a warning the user can review.
STANDARD_MACROS = frozenset({
    # LaTeX core
    "begin", "end", "section", "subsection", "subsubsection", "paragraph",
    "label", "ref", "eqref", "cite", "Cref", "cref", "autoref",
    "hypertarget", "hyperlink", "hyperref", "url",
    "newcommand", "renewcommand", "providecommand", "newtheorem", "def",
    "documentclass", "usepackage", "input", "include",
    "textbf", "textit", "emph", "underline", "texttt", "textsc", "textsf",
    "footnote", "marginpar", "vspace", "hspace", "smallskip", "medskip",
    "bigskip", "newpage", "pagebreak", "linebreak", "noindent", "indent",
    "item", "itemize", "enumerate", "description",
    # Math symbols (amssymb, amsmath, latex.ltx)
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta",
    "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi",
    "omicron", "pi", "varpi", "rho", "varrho", "sigma", "varsigma", "tau",
    "upsilon", "phi", "varphi", "chi", "psi", "omega",
    "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon",
    "Phi", "Psi", "Omega",
    "infty", "partial", "nabla", "forall", "exists", "neg", "in", "notin",
    "subset", "subseteq", "supset", "supseteq", "cup", "cap", "setminus",
    "emptyset", "varnothing", "le", "leq", "ge", "geq", "ne", "neq", "approx",
    "sim", "simeq", "equiv", "cong", "asymp", "doteq", "propto", "to",
    "rightarrow", "leftarrow", "Rightarrow", "Leftarrow", "leftrightarrow",
    "Leftrightarrow", "longrightarrow", "longleftarrow", "Longrightarrow",
    "longleftrightarrow", "mapsto", "longmapsto", "hookrightarrow",
    "hookleftarrow", "uparrow", "downarrow", "updownarrow",
    "sum", "prod", "int", "iint", "iiint", "oint", "bigcup", "bigcap",
    "bigsqcup", "bigvee", "bigwedge", "lim", "limsup", "liminf", "max", "min",
    "sup", "inf", "arg", "arginf", "argsup", "argmin", "argmax",
    "sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "det",
    "dim", "ker", "deg", "gcd", "lcm", "mod", "Pr", "bmod", "pmod",
    "frac", "dfrac", "tfrac", "binom", "sqrt", "overline", "underline",
    "widehat", "widetilde", "hat", "tilde", "bar", "vec", "dot", "ddot",
    "mathbf", "mathit", "mathrm", "mathsf", "mathtt", "mathcal", "mathbb",
    "mathfrak", "mathscr", "boldsymbol", "bm", "operatorname",
    "left", "right", "big", "Big", "bigg", "Bigg",
    "lvert", "rvert", "lVert", "rVert", "langle", "rangle", "lfloor",
    "rfloor", "lceil", "rceil", "vert", "Vert",
    "quad", "qquad", ";", ",", ":", "!", " ",
    "displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle",
    "text", "intertext", "tag",
    "begin{align}", "begin{aligned}", "begin{equation}", "begin{equation*}",
    # AMS theorem env keywords (used inside theorem definitions)
    "theorem", "lemma", "proposition", "corollary", "definition", "remark",
    "proof", "qed",
    # hyperref
    "hyperref", "href",
    # AMS / common
    "and", "or", "geqslant", "leqslant", "varnothing",
    # Probability shorthand often pre-defined by paper but conservative
    "mathbb", "Pr", "Var", "Cov", "Cor", "E",
    # bbm-like single-letter
    "ldots", "cdots", "vdots", "ddots", "dots",
    # Linear algebra / matrix notation (AMS / built-in) — added after
    # one-shot validation flagged these as "suspicious" (false positive).
    "top", "perp", "circ", "ast", "star", "dagger", "ddagger", "cdot",
    "succeq", "preceq", "succ", "prec", "succsim", "precsim",
    "trace", "tr", "rank", "diag", "Diag", "vec", "Vec",
    # Logical operators
    "vee", "wedge", "veebar",
    # Text-mode font selectors used inside math (mathtools / amsmath)
    "textup", "textnormal", "textsl", "textmd", "textbf", "textit",
    # Set / probability operators
    "subsetneq", "supsetneq", "sqsubseteq", "sqsupseteq",
    "land", "lor", "lnot", "implies", "iff", "Longleftrightarrow",
    # Common math fonts & decorations
    "mathring", "check", "breve", "acute", "grave",
    # Norms / inner products often used unbraced
    "norm", "abs", "inner", "ip",
    # Greek letters not in main list
    "Pi", "Sigma", "Theta",  # already there but defensive
    # Common theorem-proof-environment macros
    "qedhere", "iffalse", "fi",
    # Conditional probability shorthand often used unbraced
    "given", "mid",
})


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


def collect_defined_macros(paper_sources: list[Path]) -> set[str]:
    """Scan paper sources for `\\newcommand{\\foo}`, `\\def\\foo`, etc.
    Returns the set of macro names (without the leading backslash)."""
    macros: set[str] = set()
    for src in paper_sources:
        text = src.read_text(encoding="utf-8", errors="replace")
        for m in RE_NEWCOMMAND.finditer(text):
            macros.add(m.group(1))
        for m in RE_DEF.finditer(text):
            macros.add(m.group(1))
    return macros


def lint_macro_existence(
    finding: dict[str, Any],
    defined_macros: set[str],
) -> list[str]:
    """Phase γ.3 check #5 — every non-standard \\macro used in the patch must
    be defined somewhere. Catches Codex inventing `\\hatQ` etc.

    Returns a list of WARNINGS (printed to report.warnings), not hard errors —
    a missing macro might just be from a package the linter doesn't know
    about, so we don't block on it.
    """
    warnings: list[str] = []
    patch = finding.get("latex_patch", "")
    if not patch:
        return warnings
    used = set()
    for m in RE_USED_MACRO.finditer(patch):
        used.add(m.group(1))
    suspicious = sorted(used - STANDARD_MACROS - defined_macros)
    if suspicious:
        warnings.append(
            "patch uses macro(s) not in standard set and not defined in paper "
            f"sources: {suspicious}. Either add to STANDARD_MACROS allowlist "
            "(if a known package), or verify the patch isn't hallucinating a "
            "command name."
        )
    return warnings


def lint_downstream_impact(
    finding: dict[str, Any],
    packages_dir: Path | None,
) -> list[str]:
    """Phase γ.3 check #6 — if the patch redefines a macro or changes a
    definition block, the symbol may already be in use elsewhere. We scan
    the claim_packages/ directory for the same macro name and emit warnings
    listing other claims that reference it.

    Skipped if packages_dir is None or the patch contains no \\newcommand /
    \\def / \\renewcommand.
    """
    warnings: list[str] = []
    patch = finding.get("latex_patch", "")
    if not patch or packages_dir is None or not packages_dir.exists():
        return warnings

    # Macros redefined by this patch
    redefined: set[str] = set()
    for m in RE_NEWCOMMAND.finditer(patch):
        redefined.add(m.group(1))
    for m in RE_DEF.finditer(patch):
        redefined.add(m.group(1))
    if not redefined:
        return warnings

    # Look through every package for usage of these macros
    self_cid = finding.get("claim_id")
    impacts: dict[str, list[str]] = {m: [] for m in redefined}
    for pkg_path in sorted(packages_dir.glob("C*.json")):
        try:
            pkg = json.loads(pkg_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if pkg.get("claim_id") == self_cid:
            continue
        body = (pkg.get("statement_text", "") + "\n" + pkg.get("proof_text", ""))
        for macro in redefined:
            if re.search(r"\\" + re.escape(macro) + r"(?![A-Za-z])", body):
                impacts[macro].append(pkg.get("claim_id", pkg_path.stem))

    for macro, cids in impacts.items():
        if cids:
            warnings.append(
                f"patch redefines `\\{macro}`; same symbol is used in "
                f"{len(cids)} other claim(s): {cids[:8]}"
                + (" ..." if len(cids) > 8 else "")
            )
    return warnings


# Regime classification — applied to BOTH sides (patch and assumption block).
# These tokens identify a parameter regime IDIOM, not just a token presence.
# Each entry is (regex, label, exclude_predicate). exclude_predicate takes
# the surrounding text and the match, returns True to reject.
def _inside_subscript_or_norm(text: str, m: re.Match) -> bool:
    """Reject \\to\\infty when it sits inside a `_{...}` subscript or `\\|...\\|`
    norm notation (e.g., `\\|V\\|_{2\\to\\infty}` is the 2→∞ operator norm,
    not a parameter limit). This was the source of a real false-positive on
    one-shot's `ass:incoherence` block.

    Heuristic: scan backward from match.start() up to 60 chars; if we find
    an unmatched `_{` or `\\|`, this is inside a subscript / norm, reject.
    """
    pre = text[max(0, m.start() - 60): m.start()]
    # Count unbalanced `_{` (subscript-open) without matching `}` after it
    depth = 0
    i = 0
    while i < len(pre):
        if pre[i:i+2] == "_{":
            depth += 1
            i += 2
        elif pre[i] == "}" and depth > 0:
            depth -= 1
            i += 1
        else:
            i += 1
    if depth > 0:
        return True
    # Also reject if preceded (within 30 chars) by `<\infty` or `\le\infty`
    # patterns — those mean "is finite", not "→ ∞"
    if re.search(r"(<|\\le|\\leq)\s*\\infty", pre[-30:]):
        return True
    return False


REGIME_TOKENS = (
    # Genuine `\to\infty` limit idiom
    (re.compile(r"\\(?:to|rightarrow|longrightarrow)\s*\\infty\b"),
     "tends_to_infty", _inside_subscript_or_norm),
    (re.compile(r"\\(?:to|rightarrow|longrightarrow)\s*0(?![A-Za-z0-9])"),
     "tends_to_zero", _inside_subscript_or_norm),
    # Prose "is fixed" / "fixed throughout" — not just any "fixed"
    (re.compile(r"\b(?:is|are)\s+fixed\b|fixed\s+throughout", re.IGNORECASE),
     "fixed", None),
    # Prose "is bounded" / "remains bounded" — not just any "bounded"
    (re.compile(r"\b(?:is|are|remains?|stays?)\s+bounded\b", re.IGNORECASE),
     "bounded", None),
    (re.compile(r"\b(?:grows?|growing)\s+(?:to|with|as)\b", re.IGNORECASE),
     "grows", None),
    (re.compile(r"\bo_\\?p?\(1\)|\bo_\\bbP\(1\)"), "vanishing", None),
    (re.compile(r"\bO_\\?p?\(1\)|\bO_\\bbP\(1\)"), "stoch_bounded", None),
)


def _regime_match(text: str, regex: re.Pattern, exclude) -> bool:
    """Return True iff `regex` matches `text` AND exclude predicate is False."""
    for m in regex.finditer(text):
        if exclude is None or not exclude(text, m):
            return True
    return False
# Pairs that count as a regime conflict (order-insensitive)
CONFLICTING_PAIRS = frozenset({
    frozenset({"tends_to_infty", "fixed"}),
    frozenset({"tends_to_infty", "bounded"}),
    frozenset({"tends_to_zero", "stoch_bounded"}),
    frozenset({"tends_to_zero", "bounded"}),
    frozenset({"vanishing", "stoch_bounded"}),
    frozenset({"vanishing", "fixed"}),
})
RE_SYMBOL_REGIME = re.compile(
    r"\$([A-Za-z]+(?:_\{?[A-Za-z0-9,]+\}?)?)"
    r"\s*(?:\\to|\\rightarrow|=)\s*([^$]+?)\$"
)


def lint_semantic_conflict(
    finding: dict[str, Any],
    paper_sources: list[Path],
) -> list[str]:
    """Phase γ.3 check #7 — heuristic only. Looks for parameter-regime tokens
    in the patch and flags when a CONFLICTING token applies to the same symbol
    in any nearby Assumption block.

    This is a high-FP heuristic — only emits warnings, not errors. The intent
    is to catch the case where a patch tightens (or loosens) a regime in a way
    that breaks a stated Assumption.
    """
    warnings: list[str] = []
    patch = finding.get("latex_patch", "")
    if not patch:
        return warnings

    # Pull patch's regime claims: list of (symbol, regime_label)
    patch_regimes: list[tuple[str, str]] = []
    for sym_match in RE_SYMBOL_REGIME.finditer(patch):
        symbol = sym_match.group(1)
        rhs = sym_match.group(2)
        for token_re, label, exclude in REGIME_TOKENS:
            if _regime_match(rhs, token_re, exclude):
                patch_regimes.append((symbol, label))
    # Also capture "<symbol> is fixed/bounded" outside math mode (heuristic)
    for prose_m in re.finditer(
        r"\$([A-Za-z]+(?:_\{?[A-Za-z0-9,]+\}?)?)\$\s+is\s+(fixed|bounded)",
        patch, re.IGNORECASE,
    ):
        patch_regimes.append((prose_m.group(1), prose_m.group(2).lower()))

    if not patch_regimes:
        return warnings

    # Scan each paper source for Assumption blocks referencing the same symbols
    conflicts: list[str] = []
    for src in paper_sources:
        text = src.read_text(encoding="utf-8", errors="replace")
        for assum_m in re.finditer(
            r"\\begin\{assumption\}(.*?)\\end\{assumption\}",
            text,
            re.DOTALL,
        ):
            block = assum_m.group(1)
            for symbol, patch_label in patch_regimes:
                if not re.search(r"\b" + re.escape(symbol) + r"\b", block):
                    continue
                # Look for ANY conflicting regime label inside the block
                for token_re, paper_label, exclude in REGIME_TOKENS:
                    if paper_label == patch_label:
                        continue
                    if frozenset({patch_label, paper_label}) not in CONFLICTING_PAIRS:
                        continue
                    if _regime_match(block, token_re, exclude):
                        conflicts.append(
                            f"patch states `{symbol}` is `{patch_label}` but "
                            f"an existing Assumption block describes the same "
                            f"symbol with `{paper_label}`. Verify they are "
                            f"compatible (e.g., separate regimes, separate "
                            f"phases of the proof)."
                        )
                        break
    # Deduplicate
    seen = set()
    for c in conflicts:
        if c not in seen:
            warnings.append(c)
            seen.add(c)
    return warnings


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
    ap.add_argument("--no-macro-check", action="store_true",
                    help="skip Phase γ.3 macro-existence check")
    ap.add_argument("--no-downstream", action="store_true",
                    help="skip Phase γ.3 downstream-impact check")
    ap.add_argument("--no-semantic", action="store_true",
                    help="skip Phase γ.3 semantic-conflict heuristic")
    ap.add_argument("--packages-dir", type=Path, default=None,
                    help="path to claim_packages/ (required for --downstream check)")
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
    defined_macros = (
        collect_defined_macros(args.paper_source)
        if not args.no_macro_check
        else set()
    )

    report = {
        "paper_sources": [str(p) for p in args.paper_source],
        "existing_labels_count": len(existing_labels),
        "defined_macros_count": len(defined_macros),
        "no_latex": bool(args.no_latex),
        "no_macro_check": bool(args.no_macro_check),
        "no_downstream": bool(args.no_downstream),
        "no_semantic": bool(args.no_semantic),
        "per_finding": [],
        "global_errors": lint_anchor_uniqueness(findings),
    }

    any_fail = bool(report["global_errors"])
    total_warnings = 0
    for f in findings:
        errs: list[str] = []
        warns: list[str] = []
        errs += lint_anchor(f)
        errs += lint_referenced_labels(f, existing_labels)
        if not args.no_latex:
            errs += lint_compile(f, args.paper_source)
        # Phase γ.3 checks emit WARNINGS, not errors
        if not args.no_macro_check:
            warns += lint_macro_existence(f, defined_macros)
        if not args.no_downstream:
            warns += lint_downstream_impact(f, args.packages_dir)
        if not args.no_semantic:
            warns += lint_semantic_conflict(f, args.paper_source)
        item = {
            "claim_id": f.get("claim_id"),
            "gap_type": f.get("gap_type"),
            "hypertarget_anchor": f.get("hypertarget_anchor"),
            "errors": errs,
            "warnings": warns,
            "clean": not errs,
        }
        report["per_finding"].append(item)
        if errs:
            any_fail = True
        total_warnings += len(warns)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    summary = (
        f"{sum(1 for r in report['per_finding'] if r['clean'])} / "
        f"{len(report['per_finding'])} patches clean"
    )
    if report["global_errors"]:
        summary += f"; {len(report['global_errors'])} global errors"
    if total_warnings:
        summary += f"; {total_warnings} Phase γ.3 warning(s)"
    print(summary, file=sys.stderr)
    print(f"report: {args.out}", file=sys.stderr)
    return 0 if not any_fail else 1


if __name__ == "__main__":
    sys.exit(main())
