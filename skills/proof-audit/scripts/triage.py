#!/usr/bin/env python3
"""
proof-audit triage classifier — sort findings into Tier L/S/O.

Tier L (Logical bug):    fixable by ≤30 lines of LaTeX without changing
                          model assumptions; auto-fix loop should attempt.
Tier S (Style/citation): fixable by single-pass human review (citation
                          correction, wording tweak, cross-ref tightening,
                          notation collision); no point iterating.
Tier O (Open problem):   requires new mathematical theorem / new technique
                          / scope reduction; archive to OPEN_PROBLEMS.md.

Decision logic combines:
  1. Hard rules (recurring count, explicit gap_type matches)
  2. Heuristic scoring (severity, sources, language patterns)
  3. Optional LLM escalation for ambiguous cases (--llm flag, off by default)

Designed to run cheaply (no LLM call by default) on every audit round so
the convergence engine and persona prompts have up-to-date tier info.

CLI:
    triage.py classify <findings.json> [--state state.json] [--out classified.json]
        Reads a list of findings (gap.schema.json shape), produces
        classified.json with `tier` + `tier_rationale` per finding.
        If --state is given, also reads recurring counts from state.json.

    triage.py rules
        Print the hard-rule + heuristic table.

    triage.py update-state <classified.json> --state state.json --round N
        Apply tier assignments to state.json findings.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Hard rules — ordered, first-match wins
# ---------------------------------------------------------------------------
HARD_RULES: List[Tuple[str, str]] = [
    # (rule_name, condition_description)
    # Implemented as a Python function below; this list is documentation.
    ("recurring-3-stable",     "rounds_flagged_count >= 3 with similar fix attempts -> Tier S"),
    ("citation-strength",      "gap_type matches citation/external-input -> Tier S"),
    ("scope-reduction",        "gap_type matches model-class / scope-restriction -> Tier O"),
    ("requires-new-technique", "issue text mentions 'open', 'requires new', 'beyond current' -> Tier O"),
    ("notation-only",          "gap_type matches typo/symbol_abuse/undefined_symbol with severity<=2 -> Tier S"),
    ("clear-logical-bug",      "gap_type matches measurability/limit-interchange/dim_mismatch with severity>=3 -> Tier L"),
    ("missing-assumption",     "gap_type=missing_assumption + severity<=2 + already-in-context -> default Tier S"),
    ("default-fixable",        "severity>=3 with patch < 30 lines -> Tier L; else Tier S"),
]


# Keyword markers used by the heuristic; tuned from osaa_ultrasparse_refinement.tex 11-round corpus
CITATION_KEYWORDS = (
    "external theorem", "external input", "citation", "cited",
    "reference scope", "stated stronger", "stronger than cited",
    "literature", "see literature",
)
SCOPE_KEYWORDS = (
    "model class", "scope of", "closure", "matched local", "relaxed normalization",
    "alternatives", "TV equivalence", "risk equivalence", "beta < 1/2", "linear-size hard",
)
OPEN_KEYWORDS = (
    "open", "remains open", "requires new", "beyond current", "no known", "we do not have",
    "not in this draft", "future work", "follow-up paper",
)
LOGICAL_BUG_GAP_TYPES = {
    "measurability", "limit-interchange", "limit-derivative-no-Leibniz",
    "DCT-no-dominating-function", "MCT-monotonicity-unverified",
    "uniform-integrability-missing", "Hoeffding-constant-wrong", "Bernstein-misuse",
    "iid-undeclared", "n-equals-1-degenerate", "cross-fitting-conditioning-error",
    "independence-failure", "rotation-identifiability", "depends-on-wrong-rotation",
    "dim-mismatch", "dim_mismatch", "data-dependent-parameter-estimation",
    "loopless-population-space", "Wedin-target-mismatch", "invalid-sandwich-argument",
    "invalid-independence-input", "undirected-block-dependence",
    "reference-measurability-conflict",
}
STYLE_GAP_TYPES = {
    "typo", "symbol_abuse", "symbol-reuse", "undefined-symbol", "undefined_symbol",
    "citation-mismatch", "citation_mismatch", "citation-precision",
    "regularity-not-locally-stated", "diagonal-correction-not-spelled-out",
    "row-leverage-not-spelled-out", "abbe-sandon-regularity-matching",
    "uniform-failure-prob-not-explicit", "side-info-channel-conditional-independence",
    "union-bound-miscount-text", "union-bound-miscount", "external-input-strength",
    "external-theorem-scope", "LLV-applicability", "LLV-scope",
    "regularity-misstated", "weighted-pilot-concentration", "ordered-diagonal",
    "fold-oracle-tail", "uniform-rates", "uniform-rate", "undirected-dependence",
    "loopless-diagonal-correction", "missing-reference-fold-coverage",
}
OPEN_PROBLEM_GAP_TYPES = {
    "scope-overreach", "class-closure-normalization", "depends-on-invalid-closure",
    "wrong-converse-exponent", "buffer-alternatives-may-leak-information",
    "converse-not-matching", "inherits-converse-gap", "relaxed-normalization-tv",
    "converse-class-closure", "second-moment-proof-incomplete",
    "missing-proof", "common-permutation-not-justified", "kmeans-identifiability",
    "missing-assumptions", "depends-on-invalid-DCSBM-converse",
}


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------
def classify_finding(
    finding: Dict[str, Any],
    state_finding: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Return (tier, rationale) for one finding.

    finding: gap.schema.json shape (severity, gap_type, issue/explanation, etc.)
    state_finding: corresponding entry from state.json (for recurring count, prior fixes).
    """
    sev = int(finding.get("severity", 0))
    gap_type = (finding.get("gap_type") or finding.get("status") or "").strip()
    issue_text = (
        finding.get("issue")
        or finding.get("explanation")
        or finding.get("attack_scenario")
        or finding.get("missing_condition")
        or ""
    ).lower()

    recurring_count = 0
    claim_level_count = 0
    prior_fixes: List[Dict[str, Any]] = []
    if state_finding:
        recurring_count = state_finding.get("recurring_round_count", 0)
        claim_level_count = state_finding.get("claim_level_recurring_count", recurring_count)
        prior_fixes = state_finding.get("fix_attempts", [])

    # Rule 1a: same finding (claim_label + gap_type) re-flagged 3+ rounds with
    # prior fix attempts -> Tier S. The patch loop has tried; further iteration
    # is unlikely to satisfy the reviewer.
    if recurring_count >= 3 and len(prior_fixes) >= 2:
        return "S", (
            f"Recurring (same gap_type) in {recurring_count} rounds with "
            f"{len(prior_fixes)} fix attempts. Promote to single-pass human review."
        )

    # Rule 1b: claim-level recurring (>=3 rounds across any gap_type) -> Tier S.
    # Codex / personas have re-discovered the same conceptual concern under
    # different framings (e.g. LLV flagged as 'external-theorem-scope' then
    # 'citation-strength' then 'random-matrix-input-strength'). After 3 rounds
    # of re-discovery under different framings, the iteration is unlikely to
    # close the concern; promote to single-pass human review.
    if claim_level_count >= 3:
        return "S", (
            f"Claim '{state_finding['claim_label']}' has been flagged in "
            f"{claim_level_count} rounds (different gap_type framings each time). "
            "This is a stable conceptual concern; promote to human review."
        )

    # Rule 2: explicit "open problem" gap type -> Tier O
    if gap_type in OPEN_PROBLEM_GAP_TYPES:
        return "O", f"gap_type '{gap_type}' is in the open-problem catalog (requires new technique or scope reduction)."

    # Rule 3: open-problem language in issue text -> Tier O
    if any(kw in issue_text for kw in OPEN_KEYWORDS):
        matched = [kw for kw in OPEN_KEYWORDS if kw in issue_text][:3]
        return "O", f"Issue text contains open-problem markers: {matched}."

    # Rule 4: citation-strength concerns -> Tier S
    if any(kw in issue_text for kw in CITATION_KEYWORDS) or "citation" in gap_type.lower():
        matched = [kw for kw in CITATION_KEYWORDS if kw in issue_text][:2]
        return "S", (
            "Citation-strength concern (requires literature review / human "
            f"judgment). Markers: {matched or [gap_type]}."
        )

    # Rule 5: scope/closure concerns at sev<=3 -> Tier S; at sev>=4 -> Tier O
    if any(kw in issue_text for kw in SCOPE_KEYWORDS):
        if sev >= 4:
            return "O", "Scope/model-class restriction concern at severity >= 4 — typically requires new mathematical work."
        return "S", "Scope/closure wording concern; tighten via human single-pass review."

    # Rule 6: explicit logical-bug gap types -> Tier L
    if gap_type in LOGICAL_BUG_GAP_TYPES:
        return "L", f"gap_type '{gap_type}' is in the logical-bug catalog (auto-fixable via LaTeX patch)."

    # Rule 7: explicit style gap types -> Tier S
    if gap_type in STYLE_GAP_TYPES:
        return "S", f"gap_type '{gap_type}' is style/exposition (single-pass human review)."

    # Rule 8: severity-based default
    if sev >= 4:
        # High severity unclassified — default Tier L (auto-fix attempt) but flag
        return "L", f"Severity {sev} unclassified gap_type '{gap_type}'; default to Tier L for auto-fix attempt."
    if sev <= 1:
        return "S", f"Severity {sev}: cosmetic; Tier S."

    # sev 2-3 unclassified: default Tier L if patch is given, else Tier S
    has_patch = bool(finding.get("latex_patch"))
    if has_patch:
        patch_lines = len((finding.get("latex_patch") or "").splitlines())
        if patch_lines <= 30:
            return "L", f"Severity {sev}, has compact LaTeX patch ({patch_lines} lines); Tier L."
        return "S", f"Severity {sev}, but patch is {patch_lines} lines (large) — Tier S for human review."
    return "S", f"Severity {sev}, no patch provided; default Tier S."


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------
def _load_state_findings_index(state_path: Optional[str]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Index state findings by (claim_label, gap_type) for fast lookup.

    Also injects `claim_level_recurring_count` into each indexed finding so the
    classifier can apply Rule 1b without re-querying state.
    """
    if not state_path or not Path(state_path).exists():
        return {}
    state = json.loads(Path(state_path).read_text())
    all_findings = state.get("findings", []) + state.get("open_problems", [])

    # Pre-compute claim-level recurring counts (rounds across any gap_type)
    claim_rounds: Dict[str, set] = {}
    for f in all_findings:
        cl = f.get("claim_label", "")
        claim_rounds.setdefault(cl, set()).update(f.get("rounds_flagged", []))

    idx: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for f in all_findings:
        key = (f.get("claim_label", ""), f.get("gap_type", ""))
        f_with_claim_count = dict(f)
        f_with_claim_count["claim_level_recurring_count"] = len(claim_rounds.get(f.get("claim_label", ""), []))
        idx[key] = f_with_claim_count
    return idx


def _normalize_finding(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce different persona JSON shapes into a common minimum dict."""
    out = dict(raw)
    # Many persona outputs use status instead of gap_type
    if "gap_type" not in out and "status" in out:
        out["gap_type"] = out["status"]
    # Extract claim_label from various fields
    if "claim_label" not in out:
        out["claim_label"] = out.get("label", "")
    return out


def _cmd_classify(args):
    findings_raw = json.loads(Path(args.findings).read_text())
    if isinstance(findings_raw, dict) and "findings" in findings_raw:
        findings_raw = findings_raw["findings"]
    state_idx = _load_state_findings_index(args.state)

    classified: List[Dict[str, Any]] = []
    tier_counts = {"L": 0, "S": 0, "O": 0}
    for raw in findings_raw:
        f = _normalize_finding(raw)
        sf = state_idx.get((f.get("claim_label", ""), f.get("gap_type", "")))
        tier, rationale = classify_finding(f, sf)
        out = dict(f)
        out["tier"] = tier
        out["tier_rationale"] = rationale
        classified.append(out)
        tier_counts[tier] += 1

    Path(args.out).write_text(json.dumps(classified, indent=2, ensure_ascii=False))
    print(f"Classified {len(classified)} findings -> {args.out}")
    print(f"  Tier L (auto-fix):     {tier_counts['L']}")
    print(f"  Tier S (human review): {tier_counts['S']}")
    print(f"  Tier O (open problem): {tier_counts['O']}")


def _cmd_rules(args):
    print("proof-audit triage rules (first-match wins, top to bottom):\n")
    for rule, desc in HARD_RULES:
        print(f"  [{rule:<26s}] {desc}")
    print()
    print(f"Open-problem gap_type catalog: {len(OPEN_PROBLEM_GAP_TYPES)} entries")
    print(f"Logical-bug gap_type catalog:  {len(LOGICAL_BUG_GAP_TYPES)} entries")
    print(f"Style gap_type catalog:        {len(STYLE_GAP_TYPES)} entries")


def _cmd_update_state(args):
    classified = json.loads(Path(args.classified).read_text())
    # Lazy import so triage.py works without state.py available
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from state import StateManager  # type: ignore
    sm = StateManager(args.state)
    s = sm.load()
    n = 0
    for f in classified:
        # Find or upsert
        existing = s.find_by_label_and_type(f.get("claim_label", ""), f.get("gap_type", ""))
        if existing is None:
            existing = s.upsert_finding({
                "claim_label": f.get("claim_label", ""),
                "claim_id": f.get("claim_id", ""),
                "gap_type": f.get("gap_type", ""),
                "first_round": args.round,
                "current_severity": f.get("severity", 0),
                "max_severity": f.get("severity", 0),
                "excerpt": (f.get("issue") or f.get("explanation") or "")[:200],
                "sources": [f.get("source", "unknown")],
            })
        s.set_tier(existing["finding_id"], f["tier"], f["tier_rationale"], args.round)
        n += 1
    sm.save(s)
    print(f"Updated tier for {n} findings in {args.state}")


def main():
    ap = argparse.ArgumentParser(description="proof-audit triage classifier")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("classify", help="classify a list of findings")
    p.add_argument("findings", help="path to findings.json (gap.schema.json shape)")
    p.add_argument("--state", default=None, help="path to state.json for recurring context")
    p.add_argument("--out", required=True, help="output path for classified.json")
    p.set_defaults(func=_cmd_classify)

    p = sub.add_parser("rules", help="print hard-rule and heuristic table")
    p.set_defaults(func=_cmd_rules)

    p = sub.add_parser("update-state", help="apply tier assignments to state.json")
    p.add_argument("classified", help="path to classified.json")
    p.add_argument("--state", required=True, help="path to state.json")
    p.add_argument("--round", type=int, required=True)
    p.set_defaults(func=_cmd_update_state)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
