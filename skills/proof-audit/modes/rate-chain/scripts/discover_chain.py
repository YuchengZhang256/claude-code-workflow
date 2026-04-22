#!/usr/bin/env python3
"""
Phase A — Chain discovery.

From a target corollary/theorem label, build the minimal ancestor DAG by
tracing \\ref / \\eqref / \\Cref backlinks inside proof bodies.

Pure text processing. No LLM. Deterministic.
"""

import argparse, json, re, sys
from pathlib import Path
from collections import defaultdict

ENV_BEGIN = re.compile(r'\\begin\{(theorem|lemma|proposition|corollary|definition)\}(?:\[[^\]]*\])?')
ENV_END = re.compile(r'\\end\{(theorem|lemma|proposition|corollary|definition)\}')
PROOF_BEGIN = re.compile(r'\\begin\{proof\}(?:\[[^\]]*\])?')
PROOF_END = re.compile(r'\\end\{proof\}')
LABEL = re.compile(r'\\label\{([^}]+)\}')
REF = re.compile(r'\\(?:ref|eqref|Cref|cref|autoref)\{([^}]+)\}')


def parse_file(path):
    """Return list of (claim_id_counter, kind, label, file, stmt_start, stmt_end,
    proof_start, proof_end) records for each labeled environment."""
    text = Path(path).read_text()
    lines = text.split('\n')
    records = []

    i = 0
    n = len(lines)
    while i < n:
        m = ENV_BEGIN.search(lines[i])
        if not m:
            i += 1
            continue
        kind = m.group(1)
        stmt_start = i
        # find matching \end{kind}
        depth = 1
        j = i + 1
        while j < n and depth > 0:
            if ENV_BEGIN.search(lines[j]) and ENV_BEGIN.search(lines[j]).group(1) == kind:
                depth += 1
            if ENV_END.search(lines[j]) and ENV_END.search(lines[j]).group(1) == kind:
                depth -= 1
            j += 1
        stmt_end = j  # exclusive
        # label
        stmt_text = '\n'.join(lines[stmt_start:stmt_end])
        lbl_m = LABEL.search(stmt_text)
        if not lbl_m:
            i = stmt_end
            continue
        label = lbl_m.group(1)

        # associated proof: the next \begin{proof} block (optionally after blank lines, refs
        # to an external proof, or a remark). Scan forward up to 15 lines.
        proof_start = proof_end = None
        for look in range(stmt_end, min(stmt_end + 50, n)):
            if PROOF_BEGIN.search(lines[look]):
                proof_start = look
                for jj in range(look + 1, n):
                    if PROOF_END.search(lines[jj]):
                        proof_end = jj + 1
                        break
                break

        records.append({
            'kind': kind,
            'label': label,
            'file': str(path),
            'stmt_start': stmt_start + 1,  # 1-indexed
            'stmt_end': stmt_end,
            'proof_start': (proof_start + 1) if proof_start is not None else None,
            'proof_end': proof_end,
        })
        i = proof_end if proof_end else stmt_end
    return records


def refs_in_span(path, start, end):
    """Return set of labels referenced in lines[start-1:end]."""
    if start is None or end is None:
        return set()
    lines = Path(path).read_text().split('\n')
    refs = set()
    for ln in lines[start - 1:end]:
        for m in REF.finditer(ln):
            refs.add(m.group(1))
    return refs


def build_dag(records, target_label, max_depth=8):
    """BFS upward from target_label through proof-body \\ref edges."""
    by_label = {r['label']: r for r in records}
    if target_label not in by_label:
        print(f'ERROR: target label {target_label!r} not found in any parsed file', file=sys.stderr)
        print(f'Available labels (first 40): {list(by_label.keys())[:40]}', file=sys.stderr)
        sys.exit(2)

    visited = set()
    frontier = {target_label}
    edges = []
    depth_map = {target_label: 0}

    while frontier:
        next_frontier = set()
        for lbl in frontier:
            if lbl in visited:
                continue
            visited.add(lbl)
            rec = by_label[lbl]
            if rec.get('proof_start') is None:
                continue
            proof_refs = refs_in_span(rec['file'], rec['proof_start'], rec['proof_end'])
            # only keep refs that resolve to other records in our pool
            proof_refs &= set(by_label.keys())
            # drop self-refs
            proof_refs.discard(lbl)
            for pr in proof_refs:
                edges.append({'child': lbl, 'parent': pr})
                if pr not in depth_map:
                    depth_map[pr] = depth_map[lbl] + 1
                if pr not in visited and depth_map[pr] < max_depth:
                    next_frontier.add(pr)
        frontier = next_frontier

    # nodes = visited labels that are in our pool
    nodes = []
    for i, lbl in enumerate(sorted(visited, key=lambda x: depth_map.get(x, 0))):
        rec = by_label[lbl].copy()
        rec['claim_id'] = f'RC{i:02d}'
        rec['depth'] = depth_map.get(lbl, 0)
        nodes.append(rec)

    label_to_id = {n['label']: n['claim_id'] for n in nodes}
    resolved_edges = [
        {'child_id': label_to_id[e['child']], 'parent_id': label_to_id[e['parent']],
         'child_label': e['child'], 'parent_label': e['parent']}
        for e in edges
        if e['child'] in label_to_id and e['parent'] in label_to_id
    ]

    return {'nodes': nodes, 'edges': resolved_edges,
            'target_label': target_label,
            'target_id': label_to_id[target_label]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', required=True, help='Target corollary/theorem label')
    ap.add_argument('--paper', required=True, help='Main .tex file')
    ap.add_argument('--supplement', action='append', default=[],
                    help='Supplementary .tex files (repeatable)')
    ap.add_argument('--out', required=True, help='Output dag.json path')
    ap.add_argument('--min-chain-size', type=int, default=5,
                    help='Abort if chain has fewer claims than this')
    args = ap.parse_args()

    files = [args.paper] + args.supplement
    all_records = []
    for f in files:
        all_records.extend(parse_file(f))

    # de-dupe labels across files (supplement duplicates of main claims): keep main
    seen = {}
    for rec in all_records:
        if rec['label'] in seen:
            # prefer main paper over supplement
            if rec['file'] == args.paper:
                seen[rec['label']] = rec
        else:
            seen[rec['label']] = rec
    deduped = list(seen.values())

    dag = build_dag(deduped, args.target)

    if len(dag['nodes']) < args.min_chain_size:
        print(f'ABORT: chain has only {len(dag["nodes"])} claims (min {args.min_chain_size}). '
              f'Paper may not be a rate-composition target.', file=sys.stderr)
        sys.exit(3)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(dag, f, indent=2, ensure_ascii=False)

    print(f'Wrote {args.out}: {len(dag["nodes"])} nodes, {len(dag["edges"])} edges, '
          f'target depth {max(n["depth"] for n in dag["nodes"])}')


if __name__ == '__main__':
    main()
