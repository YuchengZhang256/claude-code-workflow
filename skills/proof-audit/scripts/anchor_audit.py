#!/usr/bin/env python3
r"""
proof-audit anchor audit + rename tool (Phase δ.4).

Manages `\hypertarget{gap_*}` anchors that the iterative audit accumulates
in a manuscript. Across rounds the naming convention drifts:

    gap_C1               (round 1, first finding)
    gap_C1v3_uniformity  (round 3, refined finding)
    gap_C1v11_undirected_dependence
    gap_C45_d1_short
    gap_C56_d2_short

After many rounds you end up with:
  - duplicates (two `\hypertarget{gap_C20v8}` from a botched copy-paste)
  - orphans (`\hypertarget{X}` defined but no `\hyperlink{X}` reference)
  - stale anchors (references to a `gap_*` that was removed in a refactor)
  - inconsistent style mixing v##, _major, _dN suffixes

`anchor_audit.py inspect` prints an audit report.
`anchor_audit.py rename --map rename_map.json` applies a user-curated rename
map to BOTH definitions and references in one or more .tex files. Idempotent;
supports `--dry-run`.

CLI:
  anchor_audit.py inspect --manuscript src/paper.tex [--manuscript ...]
                          [--out anchor_report.json]

  anchor_audit.py rename  --manuscript src/paper.tex [--manuscript ...]
                          --map rename_map.json
                          [--dry-run] [--strict]

The rename map is a JSON object: { "old_name": "new_name", ... }. Names are
the bare anchor strings (no `gap_` prefix needed if your map is consistent).
With --strict, the script fails if any key in the map doesn't appear in the
manuscript (catches typos in the map).
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


RE_HYPER_DEF = re.compile(r"\\hypertarget\{([^}]+)\}")
RE_HYPER_REF = re.compile(r"\\hyperlink\{([^}]+)\}")


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------
def collect(manuscripts: List[Path]) -> Dict[str, Any]:
    """Walk all manuscript files and collect anchor definitions + references."""
    defs: List[Tuple[str, str, int]] = []   # (anchor, file, line)
    refs: List[Tuple[str, str, int]] = []
    for m in manuscripts:
        text = m.read_text(encoding="utf-8", errors="replace")
        for line_idx, line in enumerate(text.splitlines(), start=1):
            for mt in RE_HYPER_DEF.finditer(line):
                defs.append((mt.group(1), str(m), line_idx))
            for mt in RE_HYPER_REF.finditer(line):
                refs.append((mt.group(1), str(m), line_idx))
    return {"defs": defs, "refs": refs}


def parse_anchor(name: str) -> Dict[str, Any]:
    """Best-effort decomposition: gap_<cid>[v<ver>][_<suffix>]."""
    parts: Dict[str, Any] = {"raw": name, "claim_id": None, "version": None,
                             "suffix": None, "is_gap": False}
    m = re.match(r"^gap_([Cc]\d+)(?:v(\d+))?(?:_(.*))?$", name)
    if not m:
        m2 = re.match(r"^gap_([Cc]\d+)_([^_]+)_(.*)$", name)  # _major_short / _d1_short
        if m2:
            parts["is_gap"] = True
            parts["claim_id"] = m2.group(1)
            parts["suffix"] = f"{m2.group(2)}_{m2.group(3)}"
        return parts
    parts["is_gap"] = True
    parts["claim_id"] = m.group(1)
    if m.group(2):
        parts["version"] = int(m.group(2))
    if m.group(3):
        parts["suffix"] = m.group(3)
    return parts


def inspect(manuscripts: List[Path], out_path: Path) -> int:
    coll = collect(manuscripts)
    defs = coll["defs"]
    refs = coll["refs"]

    # Duplicates among definitions (same anchor defined at >1 site)
    def_counts = Counter(a for a, _, _ in defs)
    duplicate_defs = {a: c for a, c in def_counts.items() if c > 1}

    # Orphans (anchor defined but not referenced anywhere)
    referenced = {a for a, _, _ in refs}
    defined = {a for a, _, _ in defs}
    orphans = sorted(defined - referenced)

    # Stale references (anchor referenced but not defined)
    stale_refs = sorted(referenced - defined)

    # Group anchors by claim_id
    by_claim: Dict[str, List[str]] = defaultdict(list)
    for a in sorted(defined):
        cid = parse_anchor(a).get("claim_id") or "_other"
        by_claim[cid].append(a)

    # Style audit: look for the four naming styles and count
    style_counts: Counter = Counter()
    for a in defined:
        p = parse_anchor(a)
        if not p["is_gap"]:
            style_counts["non_gap"] += 1
            continue
        if p["version"] is not None and p["suffix"]:
            style_counts["gap_C##v##_short"] += 1
        elif p["version"] is not None:
            style_counts["gap_C##v##"] += 1
        elif p["suffix"] and p["suffix"].startswith(("major_", "d1_", "d2_", "d3_")):
            style_counts["gap_C##_major_short / _d#_short"] += 1
        elif p["suffix"]:
            style_counts["gap_C##_<suffix>"] += 1
        else:
            style_counts["gap_C##"] += 1

    report = {
        "manuscripts": [str(m) for m in manuscripts],
        "total_definitions": len(defs),
        "total_references": len(refs),
        "unique_anchors_defined": len(defined),
        "duplicate_definitions": [
            {"anchor": a, "count": c} for a, c in sorted(duplicate_defs.items())
        ],
        "orphan_anchors": orphans,
        "stale_references": stale_refs,
        "style_distribution": dict(style_counts),
        "by_claim_top20": [
            {"claim_id": cid, "count": len(anchors), "anchors": anchors[:8]}
            for cid, anchors in sorted(
                by_claim.items(),
                key=lambda kv: -len(kv[1])
            )[:20]
        ],
    }
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # Pretty-print summary
    print(f"=== anchor audit: {len(manuscripts)} file(s) ===")
    print(f"definitions:  {len(defs)}")
    print(f"references:   {len(refs)}  "
          + ("(note: proof-audit anchors are usually 0-width landmarks; "
             "audit JSON references them via hypertarget_anchor field, "
             "not via \\hyperlink{} — so 0 refs here is expected)"
             if len(refs) == 0 else ""))
    print(f"unique anchors defined: {len(defined)}")
    print(f"duplicate definitions:  {len(duplicate_defs)}  "
          + (f"(e.g. {list(duplicate_defs)[:3]})" if duplicate_defs else ""))
    print(f"orphan anchors:         {len(orphans)}  "
          + ("(see references note above — usually false positives for "
             "proof-audit anchors)" if len(refs) == 0
             else (f"(e.g. {orphans[:3]})" if orphans else "")))
    print(f"stale references:       {len(stale_refs)}  "
          + (f"(e.g. {stale_refs[:3]})" if stale_refs else ""))
    print()
    print("style distribution:")
    for style, n in style_counts.most_common():
        print(f"  {style:<35} {n}")
    print()
    print(f"top 5 claims by anchor count:")
    for entry in report["by_claim_top20"][:5]:
        print(f"  {entry['claim_id']:<6} {entry['count']:>3}  anchors: {entry['anchors'][:5]}")
    print()
    print(f"full report -> {out_path}")
    return 0


# ---------------------------------------------------------------------------
# Renaming
# ---------------------------------------------------------------------------
def rename(
    manuscripts: List[Path],
    rename_map: Dict[str, str],
    dry_run: bool,
    strict: bool,
) -> int:
    if not rename_map:
        print("ERROR: empty rename map", file=sys.stderr)
        return 2
    # Pre-flight: verify keys (sources) exist somewhere
    coll = collect(manuscripts)
    defined = {a for a, _, _ in coll["defs"]}
    referenced = {a for a, _, _ in coll["refs"]}
    seen = defined | referenced
    missing = [k for k in rename_map if k not in seen]
    # Filter out renames that are already applied (source missing AND target
    # present). These are idempotent no-ops, NOT errors.
    already_applied = {
        k: v for k, v in rename_map.items()
        if k not in seen and v in seen
    }
    if already_applied:
        print(f"INFO: {len(already_applied)} rename(s) already applied "
              "(source missing, target present); skipping those.")
    effective_map = {
        k: v for k, v in rename_map.items()
        if k not in already_applied
    }
    # Recompute missing/collision against the effective map
    missing = [k for k in effective_map if k not in seen]
    if missing and strict:
        print(f"ERROR: --strict and {len(missing)} key(s) in map not found in "
              f"manuscript(s): {missing[:5]}", file=sys.stderr)
        return 1
    if missing:
        print(f"WARN: {len(missing)} rename keys absent from manuscripts (continuing): "
              f"{missing[:5]}", file=sys.stderr)
    # Pre-flight: check for collisions among targets that already exist
    # but only count as collision if the source ALSO still exists in the file
    target_collisions = [
        (k, v) for k, v in effective_map.items()
        if v in seen and v != k and k in seen
    ]
    if target_collisions:
        print(f"ERROR: {len(target_collisions)} target name(s) already exist; "
              f"would create duplicate definitions:", file=sys.stderr)
        for k, v in target_collisions[:5]:
            print(f"  {k} -> {v} (target already in use)", file=sys.stderr)
        return 1
    rename_map = effective_map

    total_changes = 0
    for m in manuscripts:
        text = m.read_text(encoding="utf-8", errors="replace")
        new_text = text
        per_file = 0
        for old, new in rename_map.items():
            # Replace inside both \hypertarget{...} and \hyperlink{...}
            for tpl in (r"\hypertarget{", r"\hyperlink{"):
                old_full = tpl + old + "}"
                new_full = tpl + new + "}"
                if old_full in new_text:
                    cnt = new_text.count(old_full)
                    new_text = new_text.replace(old_full, new_full)
                    per_file += cnt
        if per_file:
            print(f"{m}: {per_file} replacement(s)")
            total_changes += per_file
            if not dry_run:
                m.write_text(new_text, encoding="utf-8")
    if dry_run:
        print(f"\n[DRY RUN] would have applied {total_changes} replacement(s); "
              "no files written")
    else:
        print(f"\nApplied {total_changes} replacement(s) across "
              f"{len(manuscripts)} file(s)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="proof-audit anchor audit + rename")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inspect", help="audit anchors in one or more .tex files")
    p.add_argument("--manuscript", action="append", required=True, type=Path,
                   help="path to .tex (can repeat)")
    p.add_argument("--out", type=Path, default=Path("proof_audit/anchor_report.json"))
    p.set_defaults(func=lambda a: inspect(a.manuscript, a.out))

    p = sub.add_parser("rename", help="apply a rename map to anchors and references")
    p.add_argument("--manuscript", action="append", required=True, type=Path,
                   help="path to .tex (can repeat); operates on EACH listed file")
    p.add_argument("--map", required=True, type=Path,
                   help="JSON rename map: { 'old': 'new', ... }")
    p.add_argument("--dry-run", action="store_true",
                   help="print intended changes; do not write")
    p.add_argument("--strict", action="store_true",
                   help="fail if any rename-map key is absent from manuscripts")
    p.set_defaults(func=lambda a: rename(
        a.manuscript, json.loads(a.map.read_text()),
        a.dry_run, a.strict,
    ))

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
