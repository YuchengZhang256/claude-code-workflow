#!/usr/bin/env python3
"""
Phase B.2 — Reconcile the two double-blind extraction tables.

Given rate_table_A.json (statement-only) and rate_table_B.json (proof-body-walker),
produce rate_table.json with per-entry confidence + disagreements.json.
"""

import argparse, json, sys
from pathlib import Path


def canonicalize_rate_dict(d):
    """Normalize a rate_dict so small differences don't cause false disagreement:
    - drop entries with exponent 0
    - sort keys
    - round numeric exponents to 2 decimals
    """
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, (int, float)):
            if abs(v) < 1e-9:
                continue
            v = round(float(v), 2)
        out[k] = v
    return dict(sorted(out.items()))


def dicts_equal(a, b):
    return canonicalize_rate_dict(a) == canonicalize_rate_dict(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--disagreements', required=True)
    args = ap.parse_args()

    A = {e['claim_id']: e for e in json.load(open(args.a))}
    B = {e['claim_id']: e for e in json.load(open(args.b))}

    final = []
    disagreements = []
    for cid in sorted(set(A) | set(B)):
        a, b = A.get(cid), B.get(cid)
        if a is None:
            # only B has it — keep B's, low confidence
            final.append({**b, 'confidence': 0.5, 'source': 'B-only',
                          'note': 'statement-only extractor missed this claim'})
            continue
        if b is None:
            final.append({**a, 'confidence': 0.5, 'source': 'A-only',
                          'note': 'proof-body extractor missed this claim'})
            continue
        if dicts_equal(a.get('rate_dict', {}), b.get('rate_dict', {})):
            final.append({**a, 'confidence': 0.95, 'source': 'A=B'})
        else:
            disagreements.append({
                'claim_id': cid,
                'label': a.get('label') or b.get('label'),
                'rate_A': a.get('rate_dict'),
                'rate_B': b.get('rate_dict'),
                'excerpt_A': (a.get('excerpt') or '')[:200],
                'excerpt_B': (b.get('excerpt') or '')[:200],
            })
            # Mark as PENDING — will be filled after Phase B.3 arbitration.
            final.append({'claim_id': cid, 'label': a.get('label'),
                          'rate_dict': None, 'source': 'DISAGREE_PENDING',
                          'confidence': 0.0,
                          'note': 'awaiting Phase B.3 arbitration'})

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(final, open(args.out, 'w'), indent=2, ensure_ascii=False)
    json.dump(disagreements, open(args.disagreements, 'w'), indent=2, ensure_ascii=False)

    print(f'Reconciled {len(final)} claims. '
          f'{len(final) - len(disagreements)} agreed, {len(disagreements)} disagree (need Phase B.3).')


if __name__ == '__main__':
    main()
