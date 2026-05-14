#!/usr/bin/env python3
"""
proof-audit metrics dashboard.

Aggregates `state.json`'s round_metrics + findings into a per-round trajectory
view. Designed for quick after-round triage:

  * Did this round actually find new bugs, or just churn?
  * Are we converging (Tier-L backlog draining) or stuck (recurring stable)?
  * What's the source breakdown — is one persona producing all the noise?
  * Lifecycle delta vs prior round — anything closed, anything regressed?

Outputs:
  - default: ASCII tables to stdout
  - --out report.md: markdown report (suitable for the project root)
  - --json: machine-readable summary

CLI:
    metrics.py show [--state state.json]
    metrics.py report --out proof_audit/metrics_report.md
    metrics.py json --out proof_audit/metrics.json

`metrics.py show` prints four blocks:
  Block 1: Round trajectory table (one row per round)
  Block 2: Lifecycle status counts (open / closed / stable / open_problem)
  Block 3: Tier-L pending backlog (the actual work-in-progress)
  Block 4: Convergence signal — what the engine would decide right now
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_STATE = "proof_audit/state.json"


def _load_state(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: {p} not found", file=sys.stderr)
        sys.exit(2)
    return json.loads(p.read_text())


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------
def lifecycle_counts(state: Dict[str, Any]) -> Dict[str, int]:
    out = {
        "open": 0,
        "closed": 0,
        "stable_recurring": 0,
        "deferred_human": 0,
        "open_problem": 0,
    }
    for f in state.get("findings", []):
        st = f.get("lifecycle_status", "open")
        out[st] = out.get(st, 0) + 1
    out["open_problem"] += len(state.get("open_problems", []))
    return out


def tier_L_pending(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tier-L findings still open — the actual auto-fix backlog."""
    rows: List[Dict[str, Any]] = []
    for f in state.get("findings", []):
        if (
            f.get("current_tier") == "L"
            and f.get("lifecycle_status") in ("open", "deferred_human")
        ):
            rows.append({
                "finding_id": f.get("finding_id"),
                "claim_label": f.get("claim_label"),
                "gap_type": f.get("gap_type"),
                "current_severity": f.get("current_severity"),
                "rounds_flagged": len(f.get("rounds_flagged", [])),
                "first_round": f.get("first_round"),
            })
    rows.sort(key=lambda r: (-(r.get("current_severity") or 0),
                              -(r.get("rounds_flagged") or 0)))
    return rows


def source_breakdown(state: Dict[str, Any]) -> Dict[str, int]:
    """Across all open findings, how many came from each persona/source."""
    out: Dict[str, int] = {}
    for f in state.get("findings", []):
        if f.get("lifecycle_status") == "closed":
            continue
        for src in f.get("sources", []) or ["unattributed"]:
            out[src] = out.get(src, 0) + 1
    return out


def round_deltas(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compute per-round deltas (new vs closed vs net change in open backlog)."""
    rounds = state.get("round_metrics", [])
    out: List[Dict[str, Any]] = []
    prev_open_L = None
    for r in rounds:
        cur_open_L = r.get("open_tier_L_pending")
        delta_L = (
            cur_open_L - prev_open_L
            if (cur_open_L is not None and prev_open_L is not None)
            else None
        )
        out.append({
            "round": r.get("round"),
            "total": r.get("total_findings"),
            "new": r.get("new_findings"),
            "recurring": r.get("recurring_findings"),
            "closed": r.get("closed_findings"),
            "new_sev4": r.get("new_sev4_plus"),
            "new_sev4_act": r.get("new_sev4_plus_actionable"),
            "open_L": cur_open_L,
            "delta_L": delta_L,
            "tier_L": (r.get("tier_distribution") or {}).get("L", 0),
            "tier_S": (r.get("tier_distribution") or {}).get("S", 0),
            "tier_O": (r.get("tier_distribution") or {}).get("O", 0),
            "decision": r.get("convergence_decision"),
        })
        if cur_open_L is not None:
            prev_open_L = cur_open_L
    return out


def convergence_preview(state: Dict[str, Any]) -> Dict[str, str]:
    """Run the convergence engine read-only on the current state."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from convergence import decide  # type: ignore
    return decide(state)


# ---------------------------------------------------------------------------
# Pretty-printers
# ---------------------------------------------------------------------------
def _fmt_cell(v: Any, width: int) -> str:
    s = "-" if v is None else str(v)
    return s.ljust(width)[:width]


def show_text(state: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"=== proof-audit metrics — {state.get('manuscript', '?')} ===")
    lines.append(f"Current round: {state.get('current_round')}    "
                 f"Status: {state.get('iteration_status')}")
    if state.get("stop_recommendation"):
        lines.append(f"Stop note:     {state.get('stop_recommendation')}")
    lines.append("")

    # Block 1: Round trajectory
    lines.append("--- Round trajectory ---")
    deltas = round_deltas(state)
    if not deltas:
        lines.append("(no round_metrics recorded yet)")
    else:
        header = (
            f"{'rd':<4}{'tot':<6}{'new':<6}{'recur':<6}{'closed':<7}"
            f"{'sev4':<6}{'sev4*':<7}{'openL':<7}{'ΔL':<5}"
            f"{'L':<4}{'S':<4}{'O':<4}{'decision'}"
        )
        lines.append(header)
        lines.append("-" * len(header))
        for d in deltas:
            lines.append(
                f"{_fmt_cell(d['round'], 4)}"
                f"{_fmt_cell(d['total'], 6)}"
                f"{_fmt_cell(d['new'], 6)}"
                f"{_fmt_cell(d['recurring'], 6)}"
                f"{_fmt_cell(d['closed'], 7)}"
                f"{_fmt_cell(d['new_sev4'], 6)}"
                f"{_fmt_cell(d['new_sev4_act'], 7)}"
                f"{_fmt_cell(d['open_L'], 7)}"
                f"{_fmt_cell(d['delta_L'], 5)}"
                f"{_fmt_cell(d['tier_L'], 4)}"
                f"{_fmt_cell(d['tier_S'], 4)}"
                f"{_fmt_cell(d['tier_O'], 4)}"
                f"{_fmt_cell(d['decision'], 16)}"
            )
        lines.append("")
        lines.append("  legend: sev4* = NEW sev>=4 in actionable (Tier-L) only;")
        lines.append("          openL  = Tier-L still open at end of round (auto-fix backlog);")
        lines.append("          ΔL     = change in openL vs previous round (negative = backlog draining)")

    # Block 2: Lifecycle counts
    lines.append("")
    lines.append("--- Lifecycle status (current snapshot) ---")
    lc = lifecycle_counts(state)
    for k in ("open", "stable_recurring", "deferred_human", "open_problem", "closed"):
        lines.append(f"  {k:<20} {lc.get(k, 0)}")

    # Block 3: Tier-L pending backlog
    lines.append("")
    lines.append("--- Tier-L pending backlog (the actual work) ---")
    tl = tier_L_pending(state)
    if not tl:
        lines.append("  (empty — no auto-fixable findings open)")
    else:
        lines.append(
            f"  {'id':<6}{'sev':<5}{'rds':<5}{'fr':<4}{'label':<35}{'gap_type'}"
        )
        for r in tl:
            lines.append(
                f"  {r['finding_id']:<6}"
                f"{_fmt_cell(r['current_severity'], 5)}"
                f"{_fmt_cell(r['rounds_flagged'], 5)}"
                f"{_fmt_cell(r['first_round'], 4)}"
                f"{(r.get('claim_label') or '')[:34]:<35}"
                f"{(r.get('gap_type') or '')[:50]}"
            )

    # Block 4: Source breakdown
    lines.append("")
    lines.append("--- Source breakdown (all open findings) ---")
    sb = source_breakdown(state)
    if not sb:
        lines.append("  (no open findings)")
    else:
        for src, n in sorted(sb.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {src:<20} {n}")

    # Block 5: Convergence preview
    lines.append("")
    lines.append("--- Convergence preview (what `convergence.py decide` would say) ---")
    try:
        cp = convergence_preview(state)
        lines.append(f"  decision:  {cp['decision']}")
        lines.append(f"  rule:      {cp['matched_rule']}")
        lines.append(f"  rationale: {cp['rationale']}")
    except Exception as e:  # pragma: no cover
        lines.append(f"  (convergence engine error: {e})")

    return "\n".join(lines)


def show_markdown(state: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# proof-audit metrics report")
    lines.append("")
    lines.append(f"- **Manuscript**: `{state.get('manuscript', '?')}`")
    lines.append(f"- **Current round**: {state.get('current_round')}")
    lines.append(f"- **Iteration status**: {state.get('iteration_status')}")
    if state.get("stop_recommendation"):
        lines.append(f"- **Stop note**: {state['stop_recommendation']}")
    lines.append("")

    # Round trajectory as markdown table
    lines.append("## Round trajectory")
    lines.append("")
    deltas = round_deltas(state)
    if not deltas:
        lines.append("_no round_metrics recorded yet_")
    else:
        lines.append(
            "| rd | tot | new | recur | closed | sev4 | sev4* | openL | ΔL | L | S | O | decision |"
        )
        lines.append(
            "|----|----:|----:|------:|-------:|-----:|------:|------:|---:|--:|--:|--:|----------|"
        )
        for d in deltas:
            cells = [d["round"], d["total"], d["new"], d["recurring"],
                     d["closed"], d["new_sev4"], d["new_sev4_act"],
                     d["open_L"], d["delta_L"], d["tier_L"], d["tier_S"],
                     d["tier_O"], d["decision"]]
            lines.append("| " + " | ".join("-" if c is None else str(c) for c in cells) + " |")
        lines.append("")
        lines.append("- `sev4*` = NEW sev≥4 in actionable Tier-L only")
        lines.append("- `openL` = Tier-L still open at end of round (auto-fix backlog)")
        lines.append("- `ΔL` = change in openL vs previous round (negative = backlog draining)")

    # Lifecycle
    lines.append("")
    lines.append("## Lifecycle status (current snapshot)")
    lines.append("")
    lc = lifecycle_counts(state)
    lines.append("| status | count |")
    lines.append("|---|---:|")
    for k in ("open", "stable_recurring", "deferred_human", "open_problem", "closed"):
        lines.append(f"| {k} | {lc.get(k, 0)} |")

    # Tier-L pending
    lines.append("")
    lines.append("## Tier-L pending backlog (the actual work)")
    lines.append("")
    tl = tier_L_pending(state)
    if not tl:
        lines.append("_(empty — no auto-fixable findings open)_")
    else:
        lines.append("| id | sev | rds | first_rd | claim_label | gap_type |")
        lines.append("|----|----:|----:|---------:|-------------|----------|")
        for r in tl:
            lines.append(
                f"| {r['finding_id']} | {r['current_severity']} | "
                f"{r['rounds_flagged']} | {r['first_round']} | "
                f"`{r.get('claim_label')}` | {r.get('gap_type')} |"
            )

    # Source breakdown
    lines.append("")
    lines.append("## Source breakdown (all open findings)")
    lines.append("")
    sb = source_breakdown(state)
    if not sb:
        lines.append("_(no open findings)_")
    else:
        lines.append("| source | open count |")
        lines.append("|---|---:|")
        for src, n in sorted(sb.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {src} | {n} |")

    # Convergence preview
    lines.append("")
    lines.append("## Convergence preview")
    lines.append("")
    try:
        cp = convergence_preview(state)
        lines.append(f"- **decision**: `{cp['decision']}`")
        lines.append(f"- **rule**: `{cp['matched_rule']}`")
        lines.append(f"- **rationale**: {cp['rationale']}")
    except Exception as e:  # pragma: no cover
        lines.append(f"_convergence engine error: {e}_")

    return "\n".join(lines)


def show_json(state: Dict[str, Any]) -> Dict[str, Any]:
    lc = lifecycle_counts(state)
    tl = tier_L_pending(state)
    sb = source_breakdown(state)
    deltas = round_deltas(state)
    try:
        conv = convergence_preview(state)
    except Exception as e:  # pragma: no cover
        conv = {"decision": "ERROR", "matched_rule": "-", "rationale": str(e)}
    return {
        "manuscript": state.get("manuscript"),
        "current_round": state.get("current_round"),
        "iteration_status": state.get("iteration_status"),
        "stop_recommendation": state.get("stop_recommendation"),
        "round_trajectory": deltas,
        "lifecycle_counts": lc,
        "tier_L_pending": tl,
        "source_breakdown": sb,
        "convergence_preview": conv,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cmd_show(args):
    state = _load_state(args.state)
    print(show_text(state))


def _cmd_report(args):
    state = _load_state(args.state)
    md = show_markdown(state)
    Path(args.out).write_text(md)
    print(f"Wrote markdown report to {args.out}")


def _cmd_json(args):
    state = _load_state(args.state)
    j = show_json(state)
    Path(args.out).write_text(json.dumps(j, indent=2, ensure_ascii=False))
    print(f"Wrote JSON metrics to {args.out}")


def main():
    ap = argparse.ArgumentParser(description="proof-audit metrics dashboard")
    ap.add_argument("--state", default=DEFAULT_STATE)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="print ASCII metrics tables to stdout")
    p.set_defaults(func=_cmd_show)

    p = sub.add_parser("report", help="write markdown report")
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_report)

    p = sub.add_parser("json", help="write JSON summary")
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_json)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
