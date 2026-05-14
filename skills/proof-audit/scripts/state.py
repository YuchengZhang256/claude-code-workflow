#!/usr/bin/env python3
"""
proof-audit state management.

Provides StateManager class for the cross-round durable state at
`<cwd>/proof_audit/state.json`. Each finding tracks its full lifecycle
(first-round → fix attempts → closed | open-problem | stable-recurring),
so personas/codex receive prior context on every subsequent round and
the convergence engine can decide when to stop.

Schema: see schema/state.schema.json (schema_version 2).

CLI:
    state.py init     <manuscript>          # create empty state
    state.py show     [<finding_id>]        # dump state or one finding
    state.py round    <metric.json>         # append a round_metric
    state.py update-finding <finding.json>  # upsert a finding
    state.py migrate  <synthesized.json>    # bootstrap state from a v1 synthesized.json
    state.py prior    <out.json>            # emit prior_round_state for persona prompts
"""

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 2
DEFAULT_STATE = "proof_audit/state.json"


def _normalize_gap_type(gt: str) -> str:
    """Lowercase, collapse hyphens/underscores/whitespace. Used for fuzzy
    matching across rounds where extractors emit slightly different gap_type
    strings for the same conceptual concern."""
    if not gt:
        return ""
    return gt.lower().replace("-", "_").replace(" ", "_").strip("_")


# ---------------------------------------------------------------------------
# Core state container
# ---------------------------------------------------------------------------
class State:
    """Mutable in-memory representation of state.json.

    Use StateManager to load/save. State exposes the raw dict via .data and
    convenience accessors. Treat as a thin wrapper — no business logic here
    beyond schema-shaped construction.
    """

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @classmethod
    def empty(cls, manuscript: str) -> "State":
        now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        return cls(
            {
                "schema_version": SCHEMA_VERSION,
                "manuscript": manuscript,
                "first_audit_date": now,
                "last_audit_date": now,
                "current_round": 0,
                "iteration_status": "initialized",
                "stop_recommendation": "",
                "findings": [],
                "round_metrics": [],
                "open_problems": [],
            }
        )

    # --- finding lookups ------------------------------------------------
    def find_by_id(self, finding_id: str) -> Optional[Dict[str, Any]]:
        for f in self.data["findings"]:
            if f["finding_id"] == finding_id:
                return f
        for f in self.data["open_problems"]:
            if f["finding_id"] == finding_id:
                return f
        return None

    def find_by_label_and_type(self, claim_label: str, gap_type: str) -> Optional[Dict[str, Any]]:
        """Match by (claim_label, normalized_gap_type). Normalization collapses
        casing/hyphens/underscores so 'wrong-converse-exponent' and
        'wrong_converse_exponent' merge; this is intentional because extractors
        across rounds rarely use identical gap_type strings."""
        norm_target = _normalize_gap_type(gap_type)
        for f in self.data["findings"] + self.data["open_problems"]:
            if f.get("claim_label") == claim_label and _normalize_gap_type(f.get("gap_type", "")) == norm_target:
                return f
        return None

    def claim_level_recurring_count(self, claim_label: str) -> int:
        """Count distinct rounds in which ANY finding on this claim_label was
        surfaced. Captures recurring conceptual concerns even when gap_type
        labels drift across rounds."""
        rounds: set = set()
        for f in self.data["findings"] + self.data["open_problems"]:
            if f.get("claim_label") == claim_label:
                rounds.update(f.get("rounds_flagged", []))
        return len(rounds)

    def next_finding_id(self) -> str:
        all_findings = self.data["findings"] + self.data["open_problems"]
        max_n = 0
        for f in all_findings:
            try:
                n = int(f["finding_id"][1:])
                if n > max_n:
                    max_n = n
            except (KeyError, ValueError):
                continue
        return f"F{max_n + 1:03d}"

    # --- mutations ------------------------------------------------------
    def upsert_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """Insert if new (matched by claim_label + gap_type), else update."""
        existing = None
        if finding.get("finding_id"):
            existing = self.find_by_id(finding["finding_id"])
        if existing is None:
            existing = self.find_by_label_and_type(
                finding.get("claim_label", ""), finding.get("gap_type", "")
            )

        round_n = finding.get("last_round") or finding.get("first_round") or self.data["current_round"]
        sev = finding.get("current_severity", finding.get("max_severity", 0))

        if existing is None:
            # New finding — assign id, populate lifecycle fields
            new = dict(finding)
            new.setdefault("finding_id", self.next_finding_id())
            new.setdefault("first_round", round_n)
            new.setdefault("last_round", round_n)
            new.setdefault("rounds_flagged", [round_n])
            new.setdefault("first_severity", sev)
            new.setdefault("current_severity", sev)
            new.setdefault("max_severity", sev)
            new.setdefault("current_tier", "unclassified")
            new.setdefault("tier_history", [])
            new.setdefault("fix_attempts", [])
            new.setdefault("lifecycle_status", "open")
            new.setdefault("sources", [])
            new["recurring_round_count"] = 1
            self.data["findings"].append(new)
            return new

        # Update existing
        if round_n not in existing.get("rounds_flagged", []):
            existing.setdefault("rounds_flagged", []).append(round_n)
        existing["last_round"] = max(existing.get("last_round", round_n), round_n)
        existing["current_severity"] = sev
        existing["max_severity"] = max(existing.get("max_severity", 0), sev)
        existing["recurring_round_count"] = len(existing["rounds_flagged"])
        # Merge sources
        for s in finding.get("sources", []):
            if s not in existing.setdefault("sources", []):
                existing["sources"].append(s)
        # Update excerpt to latest
        if finding.get("excerpt"):
            existing["excerpt"] = finding["excerpt"]
        # Recurring detection
        if existing["recurring_round_count"] >= 3 and existing.get("lifecycle_status") == "open":
            existing["lifecycle_status"] = "stable_recurring"
        return existing

    def record_fix_attempt(
        self, finding_id: str, round_n: int, approach: str,
        commit: str = "", anchor: str = "", outcome: str = "still_flagged"
    ) -> None:
        f = self.find_by_id(finding_id)
        if not f:
            raise KeyError(f"finding {finding_id} not found")
        f.setdefault("fix_attempts", []).append({
            "round": round_n,
            "commit": commit,
            "anchor": anchor,
            "approach": approach,
            "outcome": outcome,
        })

    def set_tier(self, finding_id: str, tier: str, rationale: str, round_n: int) -> None:
        if tier not in ("L", "S", "O"):
            raise ValueError(f"tier must be L/S/O, got {tier}")
        f = self.find_by_id(finding_id)
        if not f:
            raise KeyError(f"finding {finding_id} not found")
        f["current_tier"] = tier
        f.setdefault("tier_history", []).append({
            "round": round_n,
            "tier": tier,
            "rationale": rationale,
        })
        if tier == "O":
            f["lifecycle_status"] = "open_problem"
            # Move to open_problems list
            if f in self.data["findings"]:
                self.data["findings"].remove(f)
                self.data["open_problems"].append(f)

    def close_finding(self, finding_id: str, round_n: int, reason: str) -> None:
        f = self.find_by_id(finding_id)
        if not f:
            return
        f["lifecycle_status"] = "closed"
        f["closed_in_round"] = round_n
        f["close_reason"] = reason

    def append_round_metric(self, metric: Dict[str, Any]) -> None:
        metric.setdefault("date", _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"))
        self.data["round_metrics"].append(metric)
        self.data["current_round"] = max(self.data["current_round"], metric["round"])
        self.data["last_audit_date"] = metric["date"]
        if metric.get("convergence_decision"):
            self._apply_convergence_decision(metric)

    def _apply_convergence_decision(self, metric: Dict[str, Any]) -> None:
        decision = metric["convergence_decision"]
        rationale = metric.get("convergence_rationale", "")
        mapping = {
            "CONTINUE": "iterating",
            "STOP_CONVERGED": "converged",
            "STOP_STUCK": "stuck_on_recurring",
            "PAUSE_HUMAN": "escalated_to_human",
        }
        if decision in mapping:
            self.data["iteration_status"] = mapping[decision]
            self.data["stop_recommendation"] = rationale

    # --- per-round summary computations --------------------------------
    def compute_round_summary(self, round_n: int) -> Dict[str, Any]:
        """Reduce findings to per-round summary metrics (used by convergence engine)."""
        all_f = self.data["findings"] + self.data["open_problems"]
        flagged_this_round = [f for f in all_f if round_n in f.get("rounds_flagged", [])]
        new = sum(1 for f in flagged_this_round if f.get("first_round") == round_n)
        recurring = len(flagged_this_round) - new
        new_sev4_plus = sum(
            1 for f in flagged_this_round
            if f.get("first_round") == round_n and f.get("current_severity", 0) >= 4
        )
        # Tier-aware: only Tier L (actionable, auto-fixable) sev>=4 findings count
        # toward "more work to do". Tier S/O findings are queued for human review
        # and should not trigger another iteration of the auto-fix loop.
        new_sev4_plus_actionable = sum(
            1 for f in flagged_this_round
            if f.get("first_round") == round_n
            and f.get("current_severity", 0) >= 4
            and f.get("current_tier") == "L"
        )
        tier_dist: Dict[str, int] = {"L": 0, "S": 0, "O": 0}
        sev_dist: Dict[str, int] = {f"sev{i}": 0 for i in range(1, 6)}
        for f in flagged_this_round:
            t = f.get("current_tier", "unclassified")
            if t in tier_dist:
                tier_dist[t] += 1
            sv = int(f.get("current_severity", 0))
            if 1 <= sv <= 5:
                sev_dist[f"sev{sv}"] += 1
        closed_this_round = sum(
            1 for f in all_f
            if f.get("lifecycle_status") == "closed" and f.get("closed_in_round") == round_n
        )
        # Actionable backlog: any open Tier-L findings still pending fix.
        # This is what auto-fix loop should drain before stopping.
        open_tier_L_pending = sum(
            1 for f in all_f
            if f.get("current_tier") == "L"
            and f.get("lifecycle_status") in ("open", None)
        )
        return {
            "round": round_n,
            "total_findings": len(flagged_this_round),
            "new_findings": new,
            "recurring_findings": recurring,
            "closed_findings": closed_this_round,
            "tier_distribution": tier_dist,
            "severity_distribution": sev_dist,
            "new_sev4_plus": new_sev4_plus,
            "new_sev4_plus_actionable": new_sev4_plus_actionable,
            "open_tier_L_pending": open_tier_L_pending,
        }

    # --- prior-context export for persona prompts ----------------------
    def emit_prior_context(
        self,
        max_findings: int = 30,
        packages_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Produce a compact summary of prior-round outcomes for new-round prompts.

        Excludes closed findings; focuses on open + stable-recurring + open-problems.
        Each entry has `claim_label`, `gap_type`, `recurring_round_count`,
        `prior_fix_attempts` (last 3), and `current_tier`.
        Personas MUST see this and acknowledge prior work before re-flagging.

        If `packages_dir` is provided, also resolves a `package_path` for each
        finding by consulting `<packages_dir>/_manifest.json`. This lets
        subagents read the small per-claim package (~150 lines) instead of the
        full manuscript (~4000+ lines).
        """
        # Build label -> package_path index from the manifest, if available
        label_to_pkg: Dict[str, str] = {}
        manifest_meta: Optional[Dict[str, Any]] = None
        if packages_dir:
            mpath = Path(packages_dir) / "_manifest.json"
            if mpath.exists():
                try:
                    manifest = json.loads(mpath.read_text())
                    manifest_meta = {
                        "manuscript": manifest.get("manuscript"),
                        "context_lines": manifest.get("context_lines"),
                        "total_packages": manifest.get("total_packages"),
                    }
                    for entry in manifest.get("entries", []):
                        cid = entry.get("claim_id")
                        label = entry.get("label")
                        if cid:
                            # Always link by claim_id; also link by label if present
                            pkg_rel = str(Path(packages_dir) / f"{cid}.json")
                            if label:
                                label_to_pkg[label] = pkg_rel
                            label_to_pkg[cid] = pkg_rel
                except (OSError, json.JSONDecodeError):
                    manifest_meta = {"error": f"could not parse {mpath}"}

        def _attach_pkg(entry: Dict[str, Any]) -> Dict[str, Any]:
            label = entry.get("claim_label") or ""
            cid = entry.get("claim_id") or ""
            pkg = label_to_pkg.get(label) or label_to_pkg.get(cid)
            if pkg:
                entry["package_path"] = pkg
            return entry

        summary: List[Dict[str, Any]] = []
        for f in self.data["findings"]:
            if f.get("lifecycle_status") not in ("open", "stable_recurring", "deferred_human"):
                continue
            entry = {
                "finding_id": f["finding_id"],
                "claim_label": f.get("claim_label"),
                "claim_id": f.get("claim_id"),
                "gap_type": f.get("gap_type"),
                "first_round": f.get("first_round"),
                "rounds_flagged_count": len(f.get("rounds_flagged", [])),
                "claim_level_recurring_count": self.claim_level_recurring_count(f.get("claim_label", "")),
                "current_severity": f.get("current_severity"),
                "current_tier": f.get("current_tier"),
                "lifecycle_status": f.get("lifecycle_status"),
                "prior_fix_attempts": f.get("fix_attempts", [])[-3:],
                "excerpt_short": (f.get("excerpt") or "")[:120],
            }
            summary.append(_attach_pkg(entry))
        # Also include open problems so personas don't re-flag them
        for f in self.data["open_problems"]:
            summary.append(_attach_pkg({
                "finding_id": f["finding_id"],
                "claim_label": f.get("claim_label"),
                "claim_id": f.get("claim_id"),
                "gap_type": f.get("gap_type"),
                "open_problem": True,
                "current_severity": f.get("current_severity"),
                "rationale": (f.get("tier_history") or [{}])[-1].get("rationale", ""),
            }))
        # Sort: most recurring first, then highest severity
        summary.sort(
            key=lambda e: (
                -e.get("rounds_flagged_count", 0),
                -e.get("current_severity", 0),
            )
        )

        instr = (
            "Each entry below has been flagged in prior audit rounds. "
            "If you would surface the same claim_label + gap_type, you MUST: "
            "(a) explicitly acknowledge the prior fix attempts, "
            "(b) explain why the prior fix is insufficient, "
            "(c) propose a CONCRETELY DIFFERENT approach — not a re-phrasing. "
            "If you cannot satisfy (b) and (c), DO NOT re-flag this finding."
        )
        if manifest_meta and not manifest_meta.get("error"):
            instr += (
                " For every finding with a `package_path`, READ THAT FILE INSTEAD "
                "of the full manuscript — it contains the statement, proof, and "
                "surrounding context already pre-sliced. Only fall back to the "
                "manuscript .tex if the package warns about staleness."
            )

        out: Dict[str, Any] = {
            "current_round": self.data["current_round"],
            "iteration_status": self.data["iteration_status"],
            "active_findings_count": len(summary),
            "instructions": instr,
            "active_findings": summary[:max_findings],
        }
        if manifest_meta is not None:
            out["packages"] = manifest_meta
        return out


# ---------------------------------------------------------------------------
# Disk I/O
# ---------------------------------------------------------------------------
class StateManager:
    """Load/save state.json with schema-version migration."""

    def __init__(self, path: str = DEFAULT_STATE):
        self.path = Path(path)

    def load(self) -> State:
        if not self.path.exists():
            raise FileNotFoundError(f"state file {self.path} does not exist; run `state.py init` first")
        data = json.loads(self.path.read_text())
        sv = data.get("schema_version", 1)
        if sv != SCHEMA_VERSION:
            data = self._migrate(data, sv)
        return State(data)

    def load_or_init(self, manuscript: str) -> State:
        if self.path.exists():
            return self.load()
        s = State.empty(manuscript)
        self.save(s)
        return s

    def save(self, state: State) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state.data, indent=2, ensure_ascii=False))

    def _migrate(self, data: Dict[str, Any], from_version: int) -> Dict[str, Any]:
        if from_version == 1:
            # v1 was a freeform dict; warn but try to preserve
            print(
                f"WARNING: migrating state from v{from_version} to v{SCHEMA_VERSION}; "
                "review state.json after migration",
                file=sys.stderr,
            )
            data["schema_version"] = SCHEMA_VERSION
            data.setdefault("findings", [])
            data.setdefault("round_metrics", [])
            data.setdefault("open_problems", [])
            data.setdefault("iteration_status", "initialized")
            data.setdefault("current_round", 0)
        return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cmd_init(args):
    sm = StateManager(args.state)
    if sm.path.exists() and not args.force:
        print(f"ERROR: {sm.path} already exists; use --force to overwrite", file=sys.stderr)
        sys.exit(2)
    s = State.empty(args.manuscript)
    sm.save(s)
    print(f"Initialized {sm.path} for manuscript {args.manuscript}")


def _cmd_show(args):
    sm = StateManager(args.state)
    s = sm.load()
    if args.finding_id:
        f = s.find_by_id(args.finding_id)
        if not f:
            print(f"finding {args.finding_id} not found", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(f, indent=2, ensure_ascii=False))
    else:
        # Compact summary
        print(f"Manuscript:         {s.data['manuscript']}")
        print(f"Current round:      {s.data['current_round']}")
        print(f"Iteration status:   {s.data['iteration_status']}")
        print(f"Findings (active):  {len(s.data['findings'])}")
        print(f"Open problems:      {len(s.data['open_problems'])}")
        print(f"Round metrics:      {len(s.data['round_metrics'])}")
        if s.data.get("stop_recommendation"):
            print(f"\nStop recommendation:\n  {s.data['stop_recommendation']}")


def _cmd_round(args):
    sm = StateManager(args.state)
    s = sm.load()
    metric = json.loads(Path(args.metric).read_text())
    s.append_round_metric(metric)
    sm.save(s)
    print(f"Appended round {metric['round']} metric; iteration_status={s.data['iteration_status']}")


def _cmd_update_finding(args):
    sm = StateManager(args.state)
    s = sm.load()
    finding = json.loads(Path(args.finding).read_text())
    if isinstance(finding, list):
        for f in finding:
            s.upsert_finding(f)
        print(f"Upserted {len(finding)} findings")
    else:
        result = s.upsert_finding(finding)
        print(f"Upserted finding {result['finding_id']}")
    sm.save(s)


def _cmd_migrate(args):
    """Bootstrap state from an existing v1 synthesized.json (Phase 2d output)."""
    sm = StateManager(args.state)
    syn = json.loads(Path(args.synthesized).read_text())
    s = sm.load_or_init(args.manuscript)
    round_n = args.round
    s.data["current_round"] = max(s.data["current_round"], round_n)
    count = 0
    for tier_key in ("tier_A_strong", "tier_B_cross_validated", "tier_C_solo", "tier_D_disputed"):
        for entry in syn.get(tier_key, []):
            f = {
                "claim_label": entry.get("label", ""),
                "claim_id": entry.get("claim_id", ""),
                "gap_type": entry.get("gap_type", "unspecified"),
                "first_round": round_n,
                "current_severity": entry.get("severity", 0),
                "max_severity": entry.get("severity", 0),
                "excerpt": entry.get("issue", entry.get("excerpt", ""))[:200],
                "sources": entry.get("surfaced_by", []),
            }
            s.upsert_finding(f)
            count += 1
    sm.save(s)
    print(f"Migrated {count} findings from {args.synthesized} into {sm.path}")


def _cmd_prior(args):
    sm = StateManager(args.state)
    s = sm.load()
    ctx = s.emit_prior_context(max_findings=args.max, packages_dir=args.packages_dir)
    Path(args.out).write_text(json.dumps(ctx, indent=2, ensure_ascii=False))
    n_with_pkg = sum(1 for e in ctx["active_findings"] if e.get("package_path"))
    note = f" ({n_with_pkg} with package_path)" if args.packages_dir else ""
    print(f"Wrote prior_round_state to {args.out} with {len(ctx['active_findings'])} entries{note}")


def main():
    ap = argparse.ArgumentParser(description="proof-audit state management")
    ap.add_argument("--state", default=DEFAULT_STATE, help="path to state.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create empty state file")
    p.add_argument("manuscript", help="path to manuscript .tex")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("show", help="dump state or one finding")
    p.add_argument("finding_id", nargs="?", default=None)
    p.set_defaults(func=_cmd_show)

    p = sub.add_parser("round", help="append a round_metric")
    p.add_argument("metric", help="path to round_metric.json")
    p.set_defaults(func=_cmd_round)

    p = sub.add_parser("update-finding", help="upsert one finding (or array of findings)")
    p.add_argument("finding", help="path to finding.json")
    p.set_defaults(func=_cmd_update_finding)

    p = sub.add_parser("migrate", help="bootstrap state from v1 synthesized.json")
    p.add_argument("synthesized", help="path to synthesized.json (v1)")
    p.add_argument("manuscript", help="path to manuscript .tex")
    p.add_argument("--round", type=int, default=1, help="round number to assign")
    p.set_defaults(func=_cmd_migrate)

    p = sub.add_parser("prior", help="emit prior_round_state for the next round's persona prompts")
    p.add_argument("out", help="output path for prior_round_state.json")
    p.add_argument("--max", type=int, default=30, help="max active findings to include")
    p.add_argument(
        "--packages-dir", default=None,
        help="path to claim_packages/ dir (with _manifest.json) to attach package_path "
             "per finding so subagents can read pre-sliced packages instead of full tex",
    )
    p.set_defaults(func=_cmd_prior)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
