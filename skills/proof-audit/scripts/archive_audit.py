#!/usr/bin/env python3
"""
proof-audit archive helper (Phase δ.1).

Maintains two convenience files for human readers across iteration rounds:

  LATEST_AUDIT.md                              # always the most recent
  _archive/audits/round_<N>/<audit_file>.md    # per-round history

The script does NOT overwrite any user-authored file in the project root —
it only manages `LATEST_AUDIT.md` (which it considers its own) and the
`_archive/audits/round_<N>/` tree.

Typical usage at the end of each round:

  python3 scripts/archive_audit.py update --round 7 --source THESIS_AUDIT.md

Sequence of effects on a fresh project (rounds 1, 2, 3, ...):

  Round 1: writes _archive/audits/round_1/THESIS_AUDIT.md and LATEST_AUDIT.md
  Round 2: writes _archive/audits/round_2/THESIS_AUDIT.md, refreshes LATEST_AUDIT.md
  ...

CLI:
  archive_audit.py update --round N --source FILE [--source FILE ...]
                          [--archive-dir _archive/audits]
                          [--latest LATEST_AUDIT.md]
  archive_audit.py list   [--archive-dir _archive/audits]
  archive_audit.py diff   --round-a A --round-b B --file THESIS_AUDIT.md
                          [--archive-dir _archive/audits]
"""

import argparse
import datetime as _dt
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


DEFAULT_ARCHIVE = "_archive/audits"
DEFAULT_LATEST = "LATEST_AUDIT.md"


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _round_dir(archive_dir: Path, round_n: int) -> Path:
    return archive_dir / f"round_{round_n}"


def update(
    round_n: int,
    sources: List[Path],
    archive_dir: Path,
    latest_path: Path,
) -> None:
    """Archive each source under round_<N>/ and refresh LATEST_AUDIT.md.

    LATEST_AUDIT.md is always overwritten with the FIRST source (typically
    THESIS_AUDIT.md). If you have multiple audit MDs (e.g. THESIS_AUDIT.md +
    OPEN_PROBLEMS.md), pass the primary one first.
    """
    if not sources:
        print("ERROR: no --source given", file=sys.stderr)
        sys.exit(2)
    for src in sources:
        if not src.exists():
            print(f"ERROR: source {src} does not exist", file=sys.stderr)
            sys.exit(2)

    rdir = _round_dir(archive_dir, round_n)
    rdir.mkdir(parents=True, exist_ok=True)

    archived: List[Path] = []
    for src in sources:
        dest = rdir / src.name
        shutil.copy2(src, dest)
        archived.append(dest)

    # Write a small metadata file alongside the archive
    meta_path = rdir / "_meta.txt"
    meta_lines = [
        f"round: {round_n}",
        f"archived_at: {_ts()}",
        "sources:",
    ]
    for s in sources:
        meta_lines.append(f"  - {s} -> {(rdir / s.name).name}")
    # Try to capture git commit if we're inside a git repo
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if commit.returncode == 0 and commit.stdout.strip():
            meta_lines.append(f"git_commit: {commit.stdout.strip()}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    meta_path.write_text("\n".join(meta_lines) + "\n")

    # Refresh LATEST_AUDIT.md = primary source + a tiny header noting the round
    primary = sources[0]
    primary_text = primary.read_text(encoding="utf-8", errors="replace")
    header = (
        f"<!-- proof-audit LATEST: round {round_n}, archived at {_ts()} from "
        f"{primary.name}. See {rdir}/ for the round's full archive. -->\n\n"
    )
    latest_path.write_text(header + primary_text)

    print(f"Archived {len(archived)} file(s) to {rdir}/")
    for a in archived:
        print(f"  - {a}")
    print(f"Updated {latest_path} (primary: {primary.name})")


def list_rounds(archive_dir: Path) -> None:
    if not archive_dir.exists():
        print(f"(no {archive_dir} yet)")
        return
    rounds = sorted(
        archive_dir.glob("round_*"),
        key=lambda p: int(p.name.split("_", 1)[1]) if p.name.split("_", 1)[1].isdigit() else 0,
    )
    if not rounds:
        print(f"(no rounds archived in {archive_dir})")
        return
    print(f"Archive root: {archive_dir}")
    print(f"{'ROUND':<8}{'WHEN':<27}{'FILES'}")
    for r in rounds:
        meta = r / "_meta.txt"
        when = "?"
        files = []
        if meta.exists():
            for line in meta.read_text().splitlines():
                if line.startswith("archived_at:"):
                    when = line.split(":", 1)[1].strip()
                if line.strip().startswith("- "):
                    files.append(line.strip()[2:].split(" -> ")[-1])
        else:
            files = [p.name for p in r.iterdir() if p.is_file()]
        round_n = r.name.split("_", 1)[1]
        print(f"{round_n:<8}{when:<27}{', '.join(files)}")


def diff_rounds(
    round_a: int,
    round_b: int,
    file_name: str,
    archive_dir: Path,
) -> None:
    a = _round_dir(archive_dir, round_a) / file_name
    b = _round_dir(archive_dir, round_b) / file_name
    if not a.exists():
        print(f"ERROR: {a} not found", file=sys.stderr)
        sys.exit(2)
    if not b.exists():
        print(f"ERROR: {b} not found", file=sys.stderr)
        sys.exit(2)
    try:
        subprocess.run(
            ["diff", "-u", str(a), str(b)],
            check=False,
        )
    except FileNotFoundError:
        # Fallback: tiny pure-python diff
        import difflib
        for line in difflib.unified_diff(
            a.read_text().splitlines(),
            b.read_text().splitlines(),
            fromfile=str(a), tofile=str(b), lineterm="",
        ):
            print(line)


def main():
    ap = argparse.ArgumentParser(description="proof-audit archive helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("update", help="archive THIS round + refresh LATEST_AUDIT.md")
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--source", action="append", required=True, type=Path,
                   help="audit MD file(s) to archive (can repeat). The FIRST source "
                        "becomes LATEST_AUDIT.md content.")
    p.add_argument("--archive-dir", type=Path, default=Path(DEFAULT_ARCHIVE))
    p.add_argument("--latest", type=Path, default=Path(DEFAULT_LATEST))
    p.set_defaults(func=lambda a: update(a.round, a.source, a.archive_dir, a.latest))

    p = sub.add_parser("list", help="list archived rounds")
    p.add_argument("--archive-dir", type=Path, default=Path(DEFAULT_ARCHIVE))
    p.set_defaults(func=lambda a: list_rounds(a.archive_dir))

    p = sub.add_parser("diff", help="diff one file between two rounds")
    p.add_argument("--round-a", type=int, required=True)
    p.add_argument("--round-b", type=int, required=True)
    p.add_argument("--file", required=True, help="file name within each round dir")
    p.add_argument("--archive-dir", type=Path, default=Path(DEFAULT_ARCHIVE))
    p.set_defaults(func=lambda a: diff_rounds(a.round_a, a.round_b, a.file, a.archive_dir))

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
