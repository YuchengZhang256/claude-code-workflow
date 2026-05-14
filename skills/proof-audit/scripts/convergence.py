#!/usr/bin/env python3
"""
proof-audit convergence engine.

Reads state.json, computes the per-round metric (or one passed in), and
emits a decision: CONTINUE | STOP_CONVERGED | STOP_STUCK | PAUSE_HUMAN.

Decision rules (deterministic, ordered top-down):

  R1 STOP_STUCK
     If round_count >= max_rounds (default 12).

  R2 STOP_STUCK
     If new_sev4_plus == 0 for 3 consecutive rounds AND there are still
     stable_recurring open problems being re-flagged. Means iteration is
     spinning on style/citation taste; further patches won't help.

  R3 STOP_CONVERGED
     If new_sev4_plus == 0 for 2 consecutive rounds AND no stable_recurring
     open findings remain. The loop has actually finished discovering bugs.

  R4 PAUSE_HUMAN
     If persona false-positive rate (codex refute / total Claude findings)
     > 0.6 over the most recent round AND >= 5 findings to compare.
     The Claude personas are noise-dominated; ask user to re-tune.

  R5 STOP_CONVERGED
     If iteration_status == "converged" was already set previously and
     current round added no new findings.

  R6 CONTINUE
     Default: more iteration may help.

CLI:
    convergence.py decide --state state.json
        Compute and print decision for current state. Optionally writes
        a metric entry back to state.json with --commit-decision.

    convergence.py compute --state state.json --round N --out metric.json
        Compute the round-N summary metric (subset of state-derived data
        + any extra critique-aware fields passed via --critique).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_MAX_ROUNDS = 12
DEFAULT_FP_THRESHOLD = 0.6
DEFAULT_FP_MIN_SAMPLE = 5


# ---------------------------------------------------------------------------
# Decision rules
# ---------------------------------------------------------------------------
def decide(
    state_data: Dict[str, Any],
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    fp_threshold: float = DEFAULT_FP_THRESHOLD,
    fp_min_sample: int = DEFAULT_FP_MIN_SAMPLE,
) -> Dict[str, str]:
    """Return {'decision': ..., 'rationale': ..., 'matched_rule': ...}.

    decision: one of CONTINUE | STOP_CONVERGED | STOP_STUCK | PAUSE_HUMAN
    """
    rounds = state_data.get("round_metrics", [])
    current_round = state_data.get("current_round", 0)

    # R1: hard cap
    if current_round >= max_rounds:
        return _decision(
            "STOP_STUCK",
            f"Hit hard iteration cap (round {current_round} >= max {max_rounds}). "
            "Remaining issues likely require new technique or human judgment.",
            "R1-hard-cap",
        )

    # Need at least 2 rounds to apply the consecutive-zero rules
    if len(rounds) < 2:
        return _decision(
            "CONTINUE",
            f"Only {len(rounds)} round(s) so far; need >=2 to evaluate convergence.",
            "R6-default-early",
        )

    # Look at the most recent rounds
    last2 = rounds[-2:]
    last3 = rounds[-3:] if len(rounds) >= 3 else None

    # Use tier-aware count: only Tier-L (auto-fixable) sev>=4 count toward
    # "still iterating worth it". Tier-S/O findings are queued for human review
    # and should not block convergence. Fall back to total if tier-aware not present.
    last_new_sev4 = last2[-1].get("new_sev4_plus_actionable", last2[-1].get("new_sev4_plus", 0))
    prev_new_sev4 = last2[-2].get("new_sev4_plus_actionable", last2[-2].get("new_sev4_plus", 0))
    # Pending Tier-L backlog — the auto-fix loop's actual workload
    last_open_L = last2[-1].get("open_tier_L_pending", 0)

    stable_recurring_open = sum(
        1 for f in state_data.get("findings", [])
        if f.get("lifecycle_status") == "stable_recurring"
    )

    # R2: spinning on style/recurring after 3 rounds with no new substantive findings
    if last3 is not None:
        recent_new_sev4 = [r.get("new_sev4_plus_actionable", r.get("new_sev4_plus", 0)) for r in last3]
        if all(n == 0 for n in recent_new_sev4) and stable_recurring_open > 0:
            return _decision(
                "STOP_STUCK",
                f"3 consecutive rounds with no new sev>=4 findings, but "
                f"{stable_recurring_open} stable-recurring finding(s) remain. "
                "Iteration is spinning on citation/style concerns. "
                "Promote remaining items to Tier S/O for human review.",
                "R2-spinning",
            )

    # R3: clean convergence — no actionable Tier-L backlog AND no new sev>=4 last round
    if last_open_L == 0 and last_new_sev4 == 0:
        return _decision(
            "STOP_CONVERGED",
            f"No open Tier-L (auto-fixable) findings remain and no new sev>=4 "
            "this round. Audit has drained the auto-fix backlog. "
            f"({stable_recurring_open} stable-recurring still open for human review.)",
            "R3-no-actionable",
        )

    # R4: persona false-positive overflow
    last_metric = last2[-1]
    fp_rate = last_metric.get("persona_fp_rate")
    if (
        fp_rate is not None
        and fp_rate > fp_threshold
        and last_metric.get("total_findings", 0) >= fp_min_sample
    ):
        return _decision(
            "PAUSE_HUMAN",
            f"Persona false-positive rate {fp_rate:.0%} exceeds threshold "
            f"{fp_threshold:.0%} over {last_metric.get('total_findings')} findings. "
            "Claude personas are noise-dominated; re-tune prompts or weight personas down.",
            "R4-fp-overflow",
        )

    # R5: previously converged + nothing new
    if state_data.get("iteration_status") == "converged" and last_new_sev4 == 0:
        return _decision(
            "STOP_CONVERGED",
            "State already marked converged in previous round; no new sev>=4 this round either.",
            "R5-stay-converged",
        )

    # R6: default — keep iterating
    return _decision(
        "CONTINUE",
        f"Last round produced {last_new_sev4} new sev>=4 finding(s); "
        f"{stable_recurring_open} stable-recurring still open. Keep iterating.",
        "R6-default-continue",
    )


def _decision(decision: str, rationale: str, rule: str) -> Dict[str, str]:
    return {"decision": decision, "rationale": rationale, "matched_rule": rule}


# ---------------------------------------------------------------------------
# Round-metric construction
# ---------------------------------------------------------------------------
def compute_round_metric(
    state_data: Dict[str, Any],
    round_n: int,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Aggregate state findings into a round_metric for round_n.

    Caller can pass additional fields via `extra` (e.g. persona_fp_rate from
    cross-critique results, commit hash from git, wall-clock timing).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from state import State  # type: ignore
    s = State(state_data)
    metric = s.compute_round_summary(round_n)
    if extra:
        metric.update(extra)
    return metric


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cmd_decide(args):
    state_path = Path(args.state)
    if not state_path.exists():
        print(f"ERROR: {state_path} does not exist", file=sys.stderr)
        sys.exit(2)
    state_data = json.loads(state_path.read_text())
    result = decide(
        state_data,
        max_rounds=args.max_rounds,
        fp_threshold=args.fp_threshold,
        fp_min_sample=args.fp_min_sample,
    )
    print(f"Decision: {result['decision']}")
    print(f"Rule:     {result['matched_rule']}")
    print(f"Rationale: {result['rationale']}")

    if args.commit_decision and state_data.get("round_metrics"):
        # Update last round metric with the decision and persist
        state_data["round_metrics"][-1]["convergence_decision"] = result["decision"]
        state_data["round_metrics"][-1]["convergence_rationale"] = result["rationale"]
        state_data["iteration_status"] = {
            "CONTINUE": "iterating",
            "STOP_CONVERGED": "converged",
            "STOP_STUCK": "stuck_on_recurring",
            "PAUSE_HUMAN": "escalated_to_human",
        }[result["decision"]]
        state_data["stop_recommendation"] = result["rationale"]
        state_path.write_text(json.dumps(state_data, indent=2, ensure_ascii=False))
        print(f"\nWrote decision back to {state_path}")


def _cmd_compute(args):
    state_data = json.loads(Path(args.state).read_text())
    extra: Dict[str, Any] = {}
    if args.critique:
        critique = json.loads(Path(args.critique).read_text())
        # Compute persona_fp_rate from critique outcomes
        verdicts = [c.get("verdict", "") for c in critique]
        if verdicts:
            refute_count = sum(1 for v in verdicts if v == "refute")
            extra["persona_fp_rate"] = refute_count / len(verdicts)
            extra["persona_findings_critiqued"] = len(verdicts)
    if args.commit:
        extra["commit"] = args.commit
    metric = compute_round_metric(state_data, args.round, extra=extra)
    Path(args.out).write_text(json.dumps(metric, indent=2, ensure_ascii=False))
    print(f"Wrote round-{args.round} metric to {args.out}")
    print(json.dumps(metric, indent=2, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description="proof-audit convergence engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("decide", help="compute decision from state.json")
    p.add_argument("--state", required=True)
    p.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    p.add_argument("--fp-threshold", type=float, default=DEFAULT_FP_THRESHOLD)
    p.add_argument("--fp-min-sample", type=int, default=DEFAULT_FP_MIN_SAMPLE)
    p.add_argument(
        "--commit-decision", action="store_true",
        help="write decision back into state.json's last round_metric and update iteration_status",
    )
    p.set_defaults(func=_cmd_decide)

    p = sub.add_parser("compute", help="compute a round_metric for round N")
    p.add_argument("--state", required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--critique", default=None, help="optional critique.json for persona_fp_rate")
    p.add_argument("--commit", default=None, help="git commit short hash")
    p.set_defaults(func=_cmd_compute)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
