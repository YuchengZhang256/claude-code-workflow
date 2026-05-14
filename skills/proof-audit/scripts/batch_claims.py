#!/usr/bin/env python3
"""
proof-audit claim batching (Phase γ.2).

Groups per-claim packages into batches for the Pedantic / Generous personas.
Instead of N=56 separate persona invocations (one per claim), we dispatch
~8 invocations of size ~7 claims each. This:

  * Cuts per-invocation overhead (~7× fewer LLM calls)
  * Lets the persona spot cross-claim notation conflicts within a batch
  * Keeps each subagent's context bounded (8 packages × 150 lines = ~1200 lines)

Batching heuristics (ordered):

  1. Group by `section_header` from the manifest. Claims under the same
     section share notation and reasoning style — they belong together.
  2. Within a section, keep `depends_on` chains together. A claim and the
     dependency it cites should fall in the same batch when feasible.
  3. Cap each batch at `--max-batch-claims` (default 8) and `--max-batch-lines`
     (default 1200). Large sections get split into multiple sub-batches.

Outputs:
  proof_audit/claim_batches.json

CLI:
    batch_claims.py build --manifest proof_audit/claim_packages/_manifest.json \\
                          [--max-batch-claims 8] [--max-batch-lines 1200] \\
                          [--out proof_audit/claim_batches.json]
    batch_claims.py show --batches proof_audit/claim_batches.json
"""

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_MAX_BATCH_CLAIMS = 8
DEFAULT_MAX_BATCH_LINES = 1200
DEFAULT_OUT = "proof_audit/claim_batches.json"


def _section_key(header: Optional[str]) -> str:
    """Normalize a section header for grouping."""
    if not header:
        return "_no_section"
    # Strip \section{...} markers and trailing whitespace
    h = header.strip()
    if h.startswith("\\"):
        # e.g. "\\section{Communication accounting}" -> "Communication accounting"
        i = h.find("{")
        j = h.rfind("}")
        if i != -1 and j != -1 and j > i:
            h = h[i + 1 : j]
    return h.strip() or "_no_section"


def _split_oversize_section(
    entries: List[Dict[str, Any]],
    max_claims: int,
    max_lines: int,
) -> List[List[Dict[str, Any]]]:
    """Split a section's entries into sub-batches that respect both caps.

    Tries to keep depends_on edges intact: a claim and an immediate dependency
    are added to the same sub-batch when possible.
    """
    by_id = {e["claim_id"]: e for e in entries}
    # First, build a quick depends_on adjacency restricted to this section.
    deps: Dict[str, List[str]] = {}
    for e in entries:
        deps[e["claim_id"]] = [
            d for d in (e.get("depends_on") or []) if d in by_id
        ]

    placed: set = set()
    out: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cur_lines = 0

    def _open_new_batch():
        nonlocal cur, cur_lines
        if cur:
            out.append(cur)
        cur = []
        cur_lines = 0

    def _try_add(eid: str) -> bool:
        nonlocal cur_lines
        if eid in placed:
            return True
        e = by_id[eid]
        line_cost = e.get("total_span_lines") or 0
        if cur and (len(cur) >= max_claims or cur_lines + line_cost > max_lines):
            return False
        cur.append(e)
        cur_lines += line_cost
        placed.add(eid)
        return True

    # Walk entries in order; for each, also try to place its in-section deps first
    for e in entries:
        cid = e["claim_id"]
        if cid in placed:
            continue
        # Try to put deps into the current batch before the claim itself
        for dep in deps.get(cid, []):
            if dep not in placed:
                if not _try_add(dep):
                    _open_new_batch()
                    _try_add(dep)
        if not _try_add(cid):
            _open_new_batch()
            _try_add(cid)
    if cur:
        out.append(cur)
    return out


def build_batches(
    manifest: Dict[str, Any],
    max_claims: int,
    max_lines: int,
) -> List[Dict[str, Any]]:
    """Group manifest entries into batches.

    Returns a list of batch dicts: {batch_id, section, claim_ids, total_lines,
    total_claims, depends_on_external}.
    """
    entries = manifest.get("entries", [])

    # We need each entry to know its depends_on. The manifest doesn't carry
    # depends_on directly; reload from each package JSON to enrich.
    enriched: List[Dict[str, Any]] = []
    for e in entries:
        pkg_path_str = e.get("package_path")
        depends_on: List[str] = []
        section_header: Optional[str] = None
        # Resolve package path relative to manifest's parent (the outdir)
        if pkg_path_str:
            pkg_path = Path(pkg_path_str)
            if not pkg_path.is_absolute():
                pkg_path = Path.cwd() / pkg_path
            if pkg_path.exists():
                try:
                    pkg = json.loads(pkg_path.read_text())
                    depends_on = pkg.get("depends_on") or []
                    section_header = pkg.get("section_header")
                except (OSError, json.JSONDecodeError):
                    pass
        enriched.append({
            "claim_id": e["claim_id"],
            "label": e.get("label"),
            "kind": e.get("kind"),
            "section_header": section_header,
            "total_span_lines": e.get("total_span_lines") or 0,
            "depends_on": depends_on,
            "warnings_count": e.get("warnings_count", 0),
        })

    # Group by section, preserving manifest order
    sections: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for e in enriched:
        key = _section_key(e.get("section_header"))
        sections.setdefault(key, []).append(e)

    batches: List[Dict[str, Any]] = []
    batch_idx = 0
    for sec_key, sec_entries in sections.items():
        sub_batches = _split_oversize_section(sec_entries, max_claims, max_lines)
        for sub in sub_batches:
            cids = [e["claim_id"] for e in sub]
            total_lines = sum(e.get("total_span_lines") or 0 for e in sub)
            # Find depends_on edges that point OUTSIDE this batch
            cid_set = set(cids)
            ext_deps: List[Tuple[str, str]] = []
            for e in sub:
                for dep in e.get("depends_on") or []:
                    if dep not in cid_set:
                        ext_deps.append((e["claim_id"], dep))
            batch_idx += 1
            batches.append({
                "batch_id": f"B{batch_idx:02d}",
                "section": sec_key,
                "claim_ids": cids,
                "total_claims": len(cids),
                "total_lines": total_lines,
                "depends_on_external": ext_deps,
                "package_paths": [
                    f"proof_audit/claim_packages/{cid}.json" for cid in cids
                ],
            })

    return batches


def _cmd_build(args):
    mpath = Path(args.manifest)
    if not mpath.exists():
        print(f"ERROR: {mpath} not found", file=sys.stderr)
        sys.exit(2)
    manifest = json.loads(mpath.read_text())
    batches = build_batches(manifest, args.max_batch_claims, args.max_batch_lines)
    out = {
        "schema_version": 1,
        "manuscript": manifest.get("manuscript"),
        "max_batch_claims": args.max_batch_claims,
        "max_batch_lines": args.max_batch_lines,
        "total_batches": len(batches),
        "total_claims": sum(b["total_claims"] for b in batches),
        "batches": batches,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Wrote {len(batches)} batches covering "
          f"{out['total_claims']} claims -> {args.out}")
    print(f"  avg batch size: {out['total_claims'] / len(batches):.1f} claims, "
          f"avg lines/batch: {sum(b['total_lines'] for b in batches) / len(batches):.0f}")


def _cmd_show(args):
    bpath = Path(args.batches)
    if not bpath.exists():
        print(f"ERROR: {bpath} not found", file=sys.stderr)
        sys.exit(2)
    bundle = json.loads(bpath.read_text())
    print(f"Manuscript:  {bundle.get('manuscript')}")
    print(f"Batches:     {bundle['total_batches']} covering "
          f"{bundle['total_claims']} claims")
    print(f"Caps:        max_batch_claims={bundle['max_batch_claims']}, "
          f"max_batch_lines={bundle['max_batch_lines']}")
    print()
    print(f"{'BATCH':<6}{'#CLAIMS':<9}{'#LINES':<8}{'EXT_DEPS':<10}SECTION / CLAIMS")
    for b in bundle["batches"]:
        cid_str = ", ".join(b["claim_ids"][:6])
        if len(b["claim_ids"]) > 6:
            cid_str += f", … ({len(b['claim_ids'])} total)"
        ext = len(b.get("depends_on_external") or [])
        print(
            f"{b['batch_id']:<6}{b['total_claims']:<9}{b['total_lines']:<8}"
            f"{ext:<10}{b['section'][:40]:<40} [{cid_str}]"
        )


def main():
    ap = argparse.ArgumentParser(description="proof-audit claim batching")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="build claim_batches.json from a manifest")
    p.add_argument("--manifest", required=True,
                   help="path to proof_audit/claim_packages/_manifest.json")
    p.add_argument("--max-batch-claims", type=int, default=DEFAULT_MAX_BATCH_CLAIMS)
    p.add_argument("--max-batch-lines", type=int, default=DEFAULT_MAX_BATCH_LINES)
    p.add_argument("--out", default=DEFAULT_OUT)
    p.set_defaults(func=_cmd_build)

    p = sub.add_parser("show", help="pretty-print a claim_batches.json")
    p.add_argument("--batches", required=True)
    p.set_defaults(func=_cmd_show)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
