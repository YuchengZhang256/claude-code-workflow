#!/usr/bin/env python3
"""
Phase C — Symbolic composition.

Given dag.json + rate_table.json + target label, walk the DAG in topological
order, apply four composition rules (sequential, triangle_sum, concat_square,
union_bound), and produce walked_vs_stated.json.

Pure sympy / Python. No LLM. Deterministic.
"""

import argparse, json, sys
from collections import defaultdict, deque
from pathlib import Path

import sympy as sp


# Canonical rate variables tracked across compositions. A rate_dict maps each
# of these to a real-valued exponent (missing → 0). The composed rate is
# effectively $\prod_v v^{e_v}$ up to constants.
CANONICAL_VARS = [
    'log',            # log(N + n_m) factor
    'K',              # community count
    'N',              # global size
    'M',              # worker count
    'n_m',            # per-worker size
    'lambda_min',     # spectral gap
    'underline_mu',   # degree floor
    'gamma_pil',      # pilot conditioning
    'l',              # pilot count
    'Delta',          # center separation
    'c_row',          # row-norm floor
    'delta_W',        # weight perturbation
    'C_P',            # degree-comparability
    'mu',             # incoherence
    'epsilon',        # operator perturbation placeholder
]


def zero_rate():
    return {v: 0.0 for v in CANONICAL_VARS}


def canon(rate):
    r = zero_rate()
    for k, v in (rate or {}).items():
        if k in r:
            r[k] = float(v)
        # unknown variables silently ignored (schema enforces during extraction)
    return r


def add_rates(a, b):
    """Combine two rates by exponent-wise sum (multiplicative composition)."""
    return {v: a.get(v, 0) + b.get(v, 0) for v in CANONICAL_VARS}


def scale_rate(a, k):
    return {v: a.get(v, 0) * k for v in CANONICAL_VARS}


def triangle_sum(rates):
    """Take the pointwise max — the dominant term is what survives $\\|X\\|+\\|Y\\|$."""
    out = zero_rate()
    for r in rates:
        for v in CANONICAL_VARS:
            out[v] = max(out[v], r.get(v, 0))
    return out


def concat_square(rates):
    """Per-entry × 2, then add $M^1$ (one factor of worker count from the sum)."""
    sq = triangle_sum([scale_rate(r, 2) for r in rates])
    sq['M'] = sq.get('M', 0) + 1
    return sq


def union_bound(rate, variable='log'):
    """Union bound adds one log factor (conservative)."""
    out = dict(rate)
    out[variable] = out.get(variable, 0) + 1
    return out


MERGE_FUNCS = {
    'sequential':    lambda parents: add_rates(*parents) if parents else zero_rate(),
    'triangle_sum':  lambda parents: triangle_sum(parents),
    'concat_square': lambda parents: concat_square(parents),
    'union_bound':   lambda parents: union_bound(triangle_sum(parents)),
}


def topo_sort(nodes, edges):
    """Return claim_ids in topological order (parents before children)."""
    incoming = defaultdict(set)
    outgoing = defaultdict(set)
    node_ids = {n['claim_id'] for n in nodes}
    for e in edges:
        # DAG built with "child uses parent" — composition goes parent → child.
        outgoing[e['parent_id']].add(e['child_id'])
        incoming[e['child_id']].add(e['parent_id'])

    indeg = {nid: len(incoming[nid]) for nid in node_ids}
    queue = deque([n for n in node_ids if indeg[n] == 0])
    order = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in outgoing[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if len(order) < len(node_ids):
        missing = node_ids - set(order)
        print(f'WARN: cycle or unreachable in DAG, claims not ordered: {missing}', file=sys.stderr)
        order.extend(sorted(missing))
    return order


def rate_to_latex(rate):
    """Render a rate_dict as `$\\log^a / \\underline\\mu^b \\cdot K^c$` type string."""
    num_terms, den_terms = [], []
    pretty_map = {
        'log': r'\log(N+n_m)', 'K': 'K', 'N': 'N', 'M': 'M', 'n_m': 'n_m',
        'lambda_min': r'\lambda_{\min}', 'underline_mu': r'\underline\mu_{\taureg}',
        'gamma_pil': r'\gamma_{\mathrm{pil}}', 'l': 'l', 'Delta': r'\Delta',
        'c_row': r'c_{\mathrm{row}}', 'delta_W': r'\delta_W',
        'C_P': 'C_P', 'mu': r'\mu', 'epsilon': r'\varepsilon',
    }
    for v in CANONICAL_VARS:
        e = rate.get(v, 0)
        if abs(e) < 1e-9:
            continue
        name = pretty_map.get(v, v)
        if e > 0:
            num_terms.append(f'{name}^{{{e:g}}}' if e != 1 else name)
        else:
            den_terms.append(f'{name}^{{{-e:g}}}' if -e != 1 else name)
    num = ' '.join(num_terms) or '1'
    if den_terms:
        return fr'\frac{{{num}}}{{{" ".join(den_terms)}}}'
    return num


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dag', required=True)
    ap.add_argument('--rates', required=True)
    ap.add_argument('--target', required=True, help='Target claim LABEL (not claim_id)')
    ap.add_argument('--out', required=True, help='walked_vs_stated.json')
    ap.add_argument('--trace', required=True, help='composition_trace.json')
    args = ap.parse_args()

    dag = json.load(open(args.dag))
    rates = {r['claim_id']: r for r in json.load(open(args.rates))}

    nodes = dag['nodes']
    edges = dag['edges']
    target_label = args.target
    target_id = dag.get('target_id')
    if not target_id:
        # fallback — find by label
        for n in nodes:
            if n['label'] == target_label:
                target_id = n['claim_id']
                break
    if not target_id:
        print(f'ERROR: target label {target_label} not in DAG', file=sys.stderr)
        sys.exit(2)

    # Build parent map
    parents_of = defaultdict(list)
    for e in edges:
        parents_of[e['child_id']].append(e['parent_id'])

    order = topo_sort(nodes, edges)
    walked = {}
    trace = []

    for cid in order:
        rec = rates.get(cid)
        if rec is None or rec.get('rate_dict') is None:
            # pending / dual-path / missing → skip, will mark N/A
            trace.append({'claim_id': cid, 'status': 'missing_rate',
                          'note': 'Phase B did not produce a usable rate for this claim; '
                                  'walked rate for downstream nodes may be incomplete'})
            walked[cid] = zero_rate()
            continue

        # The walked rate of this node is:
        #   own_rate * merge(parents walked rates) — multiplicatively
        # where own_rate accounts for whatever NEW factor this lemma ADDS
        # (e.g., a new $\sqrt K$ or a new $1/\sqrt{\underline\mu}$).
        parent_rates = [walked.get(p, zero_rate()) for p in parents_of[cid]]
        merge_mode = rec.get('merge_mode', 'sequential')
        merge_fn = MERGE_FUNCS.get(merge_mode, MERGE_FUNCS['sequential'])
        merged_parents = merge_fn(parent_rates) if parent_rates else zero_rate()
        own = canon(rec.get('rate_dict', {}))
        # own contains the lemma's STATED rate; we treat it as the delta
        # contributed by this step IF the lemma says "own = delta × upstream".
        # If lemma is root-level (no parents), own is the whole rate.
        contribution_mode = rec.get('contribution_mode', 'absolute')  # 'absolute' | 'delta'
        if contribution_mode == 'delta' and parent_rates:
            composed = add_rates(own, merged_parents)
        else:
            composed = own if own else merged_parents
        walked[cid] = composed
        trace.append({
            'claim_id': cid,
            'label': rec.get('label'),
            'parents': parents_of[cid],
            'parent_rates': {p: walked.get(p) for p in parents_of[cid]},
            'own_rate': own,
            'merge_mode': merge_mode,
            'contribution_mode': contribution_mode,
            'walked_rate': composed,
            'walked_latex': rate_to_latex(composed),
        })

    # Final diff on target
    target_rec = rates.get(target_id, {})
    stated = canon(target_rec.get('rate_dict', {}))
    walked_final = walked.get(target_id, zero_rate())
    diff = {v: walked_final.get(v, 0) - stated.get(v, 0) for v in CANONICAL_VARS}
    discrepancies = {v: d for v, d in diff.items() if abs(d) > 1e-9}

    output = {
        'target_label': target_label,
        'target_id': target_id,
        'walked': walked_final,
        'stated': stated,
        'walked_latex': rate_to_latex(walked_final),
        'stated_latex': rate_to_latex(stated),
        'discrepancies': discrepancies,
        'verdict': 'CHAIN_BREAK' if discrepancies else 'CONSISTENT',
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(output, open(args.out, 'w'), indent=2, ensure_ascii=False)
    json.dump(trace, open(args.trace, 'w'), indent=2, ensure_ascii=False)

    print(f'Composition verdict: {output["verdict"]}')
    if discrepancies:
        print(f'Discrepancies: {discrepancies}')


if __name__ == '__main__':
    main()
