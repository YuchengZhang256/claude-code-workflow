#!/usr/bin/env python3
"""
proof-audit unified entry point (Phase δ.3).

Thin wrapper that composes the underlying per-task scripts into a single
`proof-audit <subcommand>` interface. The heavy LLM work (Phase 2 personas,
Phase 2b codex, Phase 2c critique) still lives in the user's Claude session
because it requires Agent / codex exec dispatch, but every deterministic
Python step is exposed here.

Subcommands:

  init        Bootstrap proof_audit/ directory: copy claims.json template
              path, build claim_packages, init state.json
  packages    Rebuild claim packages
  batches     Rebuild claim batches (Phase γ.2)
  triage      Classify findings into Tier L/S/O and update state
  verdict     Run convergence.py decide on current state
  metrics     Show the metrics dashboard
  prior       Emit prior_round_state.json for the next round
  archive     Archive THIS round's audit MD and refresh LATEST_AUDIT.md
  open-problems  Emit OPEN_PROBLEMS.md from state's Tier-O entries
  replay      Re-emit metrics + open-problems + archive without re-running
              any LLM step (useful for double-checking after a manual edit
              to state.json)

Each subcommand is a thin shim around one of the existing scripts. Any flags
not recognized here are passed through verbatim. Use `proof-audit <cmd> --help`
for the underlying script's full options.

Standard layout it expects/creates:

  proof_audit/
    state.json                 (Phase α)
    claims.json                (Phase 1, user/extractor produced)
    claim_packages/            (Phase β.1)
      _manifest.json
      C1.json ...
    claim_batches.json         (Phase γ.2)
    prior_round_state.json     (per round)
    findings_*.json            (Phase 2)
    synthesized.json           (Phase 2d)
    findings_classified.json   (Phase 2.5)
    round_<N>_metric.json      (Phase α)
    metrics_report.md          (Phase β.3)
    lint_report.json           (Phase 3)
  LATEST_AUDIT.md              (Phase δ.1)
  OPEN_PROBLEMS.md             (Phase δ.2)
  _archive/audits/round_<N>/   (Phase δ.1)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List


# Resolve sibling scripts relative to this file
SCRIPTS_DIR = Path(__file__).resolve().parent


def _run_sibling(script: str, args: List[str]) -> int:
    """Invoke a sibling script with the given args; return its exit code."""
    cmd = [sys.executable, str(SCRIPTS_DIR / script)] + args
    return subprocess.call(cmd)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------
def _cmd_init(args, extra: List[str]) -> int:
    """init: build packages + init state.json"""
    rc = 0
    # 1. packages
    pkg_args = ["build", "--claims", args.claims, "--outdir", args.packages_dir]
    if args.context_lines is not None:
        pkg_args += ["--context-lines", str(args.context_lines)]
    rc |= _run_sibling("package_claims.py", pkg_args)
    if rc:
        return rc
    # 2. state init
    state_path = Path(args.state)
    if state_path.exists() and not args.force:
        print(f"state {state_path} already exists; pass --force to recreate")
    else:
        rc |= _run_sibling(
            "state.py",
            ["--state", str(state_path), "init", args.manuscript]
            + (["--force"] if args.force else []),
        )
    return rc


def _cmd_packages(args, extra: List[str]) -> int:
    return _run_sibling("package_claims.py", ["build", "--claims", args.claims] + extra)


def _cmd_batches(args, extra: List[str]) -> int:
    return _run_sibling(
        "batch_claims.py",
        ["build", "--manifest", args.manifest, "--out", args.out] + extra,
    )


def _cmd_triage(args, extra: List[str]) -> int:
    rc = _run_sibling(
        "triage.py",
        ["classify", args.findings, "--state", args.state, "--out", args.classified]
        + extra,
    )
    if rc:
        return rc
    return _run_sibling(
        "triage.py",
        ["update-state", "--state", args.state, "--round", str(args.round),
         args.classified],
    )


def _cmd_verdict(args, extra: List[str]) -> int:
    cmd = ["decide", "--state", args.state]
    if args.commit:
        cmd.append("--commit-decision")
    return _run_sibling("convergence.py", cmd + extra)


def _cmd_metrics(args, extra: List[str]) -> int:
    return _run_sibling("metrics.py", ["--state", args.state, "show"] + extra)


def _cmd_prior(args, extra: List[str]) -> int:
    cmd = [
        "--state", args.state, "prior", args.out,
        "--max", str(args.max),
    ]
    if args.packages_dir:
        cmd += ["--packages-dir", args.packages_dir]
    return _run_sibling("state.py", cmd + extra)


def _cmd_archive(args, extra: List[str]) -> int:
    cmd = ["update", "--round", str(args.round)]
    for s in args.source:
        cmd += ["--source", s]
    if args.archive_dir:
        cmd += ["--archive-dir", args.archive_dir]
    if args.latest:
        cmd += ["--latest", args.latest]
    return _run_sibling("archive_audit.py", cmd + extra)


def _cmd_open_problems(args, extra: List[str]) -> int:
    cmd = [
        "emit", "--state", args.state, "--out", args.out,
        "--packages-dir", args.packages_dir,
    ]
    if args.include_deferred_human:
        cmd.append("--include-deferred-human")
    return _run_sibling("open_problems.py", cmd + extra)


def _cmd_replay(args, extra: List[str]) -> int:
    """Re-emit metrics + open-problems without re-running anything LLM-side.
    Useful after a hand-edit to state.json or to verify reproducibility.
    """
    rc = 0
    print("=== metrics ===")
    rc |= _run_sibling("metrics.py", ["--state", args.state, "show"])
    print("\n=== open-problems ===")
    rc |= _run_sibling(
        "open_problems.py",
        ["emit", "--state", args.state, "--out", args.out_open_problems,
         "--packages-dir", args.packages_dir]
        + (["--include-deferred-human"] if args.include_deferred_human else []),
    )
    print("\n=== verdict ===")
    rc |= _run_sibling("convergence.py", ["decide", "--state", args.state])
    return rc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        prog="proof-audit",
        description="Unified entry point for the proof-audit skill.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="bootstrap: build packages + init state.json")
    p.add_argument("--claims", default="proof_audit/claims.json")
    p.add_argument("--manuscript", required=True, help="path to manuscript .tex")
    p.add_argument("--state", default="proof_audit/state.json")
    p.add_argument("--packages-dir", default="proof_audit/claim_packages")
    p.add_argument("--context-lines", type=int, default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("packages", help="rebuild claim packages")
    p.add_argument("--claims", default="proof_audit/claims.json")
    p.set_defaults(func=_cmd_packages)

    p = sub.add_parser("batches", help="rebuild Pedantic/Generous batches")
    p.add_argument("--manifest", default="proof_audit/claim_packages/_manifest.json")
    p.add_argument("--out", default="proof_audit/claim_batches.json")
    p.set_defaults(func=_cmd_batches)

    p = sub.add_parser("triage", help="classify findings + update state.json")
    p.add_argument("--findings", required=True)
    p.add_argument("--classified", default="proof_audit/findings_classified.json")
    p.add_argument("--state", default="proof_audit/state.json")
    p.add_argument("--round", type=int, required=True)
    p.set_defaults(func=_cmd_triage)

    p = sub.add_parser("verdict", help="run convergence engine")
    p.add_argument("--state", default="proof_audit/state.json")
    p.add_argument("--commit", action="store_true",
                   help="write decision back into state.json")
    p.set_defaults(func=_cmd_verdict)

    p = sub.add_parser("metrics", help="show metrics dashboard")
    p.add_argument("--state", default="proof_audit/state.json")
    p.set_defaults(func=_cmd_metrics)

    p = sub.add_parser("prior", help="emit prior_round_state.json for next round")
    p.add_argument("--state", default="proof_audit/state.json")
    p.add_argument("--out", default="proof_audit/prior_round_state.json")
    p.add_argument("--packages-dir", default="proof_audit/claim_packages")
    p.add_argument("--max", type=int, default=30)
    p.set_defaults(func=_cmd_prior)

    p = sub.add_parser("archive", help="archive this round + refresh LATEST_AUDIT.md")
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--source", action="append", required=True)
    p.add_argument("--archive-dir", default="_archive/audits")
    p.add_argument("--latest", default="LATEST_AUDIT.md")
    p.set_defaults(func=_cmd_archive)

    p = sub.add_parser("open-problems", help="emit OPEN_PROBLEMS.md from Tier-O entries")
    p.add_argument("--state", default="proof_audit/state.json")
    p.add_argument("--out", default="OPEN_PROBLEMS.md")
    p.add_argument("--include-deferred-human", action="store_true")
    p.add_argument("--packages-dir", default="proof_audit/claim_packages")
    p.set_defaults(func=_cmd_open_problems)

    p = sub.add_parser("replay",
                       help="re-emit metrics + open-problems + verdict without LLM calls")
    p.add_argument("--state", default="proof_audit/state.json")
    p.add_argument("--out-open-problems", default="OPEN_PROBLEMS.md")
    p.add_argument("--include-deferred-human", action="store_true")
    p.add_argument("--packages-dir", default="proof_audit/claim_packages")
    p.set_defaults(func=_cmd_replay)

    args, extra = ap.parse_known_args()
    sys.exit(args.func(args, extra))


if __name__ == "__main__":
    main()
