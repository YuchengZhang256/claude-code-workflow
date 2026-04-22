#!/usr/bin/env python3
"""
Phase D — Report generation.

Reads all Phase A-C artifacts and writes RATE_CHAIN_AUDIT.md.
"""

import argparse, json
from pathlib import Path


PRETTY = {
    'log': r'\log(N+n_m)', 'K': 'K', 'N': 'N', 'M': 'M', 'n_m': 'n_m',
    'lambda_min': r'\lambda_{\min}', 'underline_mu': r'\underline\mu_{\taureg}',
    'gamma_pil': r'\gamma_{\mathrm{pil}}', 'l': 'l', 'Delta': r'\Delta',
    'c_row': r'c_{\mathrm{row}}', 'delta_W': r'\delta_W',
    'C_P': 'C_P', 'mu': r'\mu', 'epsilon': r'\varepsilon',
}


def fmt_latex(rate):
    num, den = [], []
    for v, e in rate.items():
        if abs(e) < 1e-9:
            continue
        n = PRETTY.get(v, v)
        if e > 0:
            num.append(f'{n}^{{{e:g}}}' if e != 1 else n)
        else:
            den.append(f'{n}^{{{-e:g}}}' if -e != 1 else n)
    num_str = ' '.join(num) or '1'
    return f'\\frac{{{num_str}}}{{{" ".join(den)}}}' if den else num_str


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--walked', required=True)
    ap.add_argument('--trace', required=True)
    ap.add_argument('--canary', required=True)
    ap.add_argument('--disagreements', required=True)
    ap.add_argument('--dag', required=True)
    ap.add_argument('--rates', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default='Rate Chain Audit')
    args = ap.parse_args()

    walked = json.load(open(args.walked))
    trace = json.load(open(args.trace))
    canary = json.load(open(args.canary))
    disagreements = json.load(open(args.disagreements))
    dag = json.load(open(args.dag))
    rates = {r['claim_id']: r for r in json.load(open(args.rates))}

    out = []
    out.append(f'# {args.title} — target `{walked["target_label"]}`\n')

    # Canary banner
    pass_rate = canary.get('pass_rate', 0)
    out.append(f'**Canary pass rate**: {canary["passed"]}/{canary["total"]} ({int(pass_rate*100)}%).  '
               f'{"✅ Proceed." if not canary.get("aborted") else "🛑 Pipeline aborted."}\n')

    # Top table
    out.append('## Walked vs. Stated\n')
    out.append('| variable | walked exponent | stated exponent | Δ |')
    out.append('|---|---:|---:|---:|')
    for v in sorted(set(walked['walked']) | set(walked['stated'])):
        w = walked['walked'].get(v, 0)
        s = walked['stated'].get(v, 0)
        d = w - s
        marker = ' **←**' if abs(d) > 1e-9 else ''
        out.append(f'| `${PRETTY.get(v,v)}$` | {w:g} | {s:g} | {d:+g}{marker} |')
    out.append('')
    out.append(f'**Verdict**: `{walked["verdict"]}`.  '
               f'Walked rate: `${walked["walked_latex"]}$`. '
               f'Stated rate: `${walked["stated_latex"]}$`.\n')

    # Chain-breaks section
    if walked['discrepancies']:
        out.append('## Chain-breaks\n')
        for v, d in walked['discrepancies'].items():
            out.append(f'### Variable `${PRETTY.get(v,v)}$` — Δ = {d:+g}')
            out.append(f'- **Walked**: exponent {walked["walked"].get(v,0)}')
            out.append(f'- **Stated**: exponent {walked["stated"].get(v,0)}')
            out.append(f'- **Discrepancy**: {"over-stated (appendix proves less)" if d>0 else "under-stated (appendix proves more)"}')
            out.append(f'- **Patch options**:\n')
            out.append('```latex')
            out.append(f'\\hypertarget{{gap_ratechain_{v}_{walked["target_id"]}}}{{}}% ')
            out.append(f'% Option A (relax corollary): increase the exponent on ${PRETTY.get(v,v)}$ by {d:+g}')
            out.append(f'% Option B (tighten upstream): find the lemma contributing the '
                       f'missing {v}^{{{d}}} factor and prove the sharper bound')
            out.append('```\n')

    # Dual-path section
    dual = [r for r in rates.values() if r.get('source') == 'dual-path']
    if dual:
        out.append('## Dual-path entries (Phase B.3 arbitrator declared both plausible)\n')
        for r in dual:
            out.append(f'- **{r["claim_id"]}** (`{r.get("label")}`): A said `{r.get("rate_A")}`, '
                       f'B said `{r.get("rate_B")}`. Both walked paths appear in the composition '
                       f'trace; consult `rate_chain/composition_trace.json`.')
        out.append('')

    # Provenance
    out.append('## Provenance — how each walked rate was built\n')
    out.append('| claim_id | label | merge_mode | parents | own_rate | walked_rate |')
    out.append('|---|---|---|---|---|---|')
    for t in trace:
        if t.get('status') == 'missing_rate':
            out.append(f'| {t["claim_id"]} | — | — | — | — | *missing* |')
            continue
        parents = ','.join(t.get('parents', [])) or '—'
        own = fmt_latex(t.get('own_rate', {})) or '—'
        wk = fmt_latex(t.get('walked_rate', {})) or '—'
        out.append(f'| {t["claim_id"]} | `{t.get("label","—")}` | {t.get("merge_mode","—")} | '
                   f'{parents} | ${own}$ | ${wk}$ |')
    out.append('')

    # Confidence decay
    max_depth = max((n.get('depth', 0) for n in dag['nodes']), default=0)
    post_conf = 0.95 ** max_depth
    out.append(f'## Posterior confidence\n')
    out.append(f'Chain depth = {max_depth}.  Posterior confidence on every chain-break is '
               f'`prior × 0.95^{max_depth} = prior × {post_conf:.3f}`. '
               f'Temper interpretations accordingly.\n')

    # Canary detail
    out.append('## Canary self-check detail\n')
    out.append('| canary | status | expected | got |')
    out.append('|---|---|---|---|')
    for r in canary.get('results', [])[:20]:
        out.append(f'| {r["name"]} | {r["status"]} | `{r["expected"]}` | `{r.get("got","—")}` |')
    out.append('')

    # Disagreements detail
    if disagreements:
        out.append('## Phase B extractor disagreements\n')
        for d in disagreements:
            out.append(f'- **{d["claim_id"]}** (`{d.get("label")}`): statement-only said '
                       f'`{d["rate_A"]}`; proof-body said `{d["rate_B"]}`. See `disagreements.json` for excerpts.')
        out.append('')

    # Limits
    out.append('## Limits of this audit (what this skill cannot catch)\n')
    out.append('See `~/.claude/skills/rate-chain-audit/references/limits.md`. Summary:\n')
    out.append('1. Constant-level errors (this skill checks exponents only).\n'
               '2. Lemma statement vs. proof-body drift where BOTH extractors would make the same mistake as the author.\n'
               '3. A lemma that is itself logically wrong (requires Lean-level formalization to catch).\n'
               '4. Implicit assumption leakage propagating silently through the chain.\n'
               '5. Novel proof-technique correctness.\n'
               '6. Uniform off-by-truth (stated rate and walked rate agree but both diverge from ground truth).\n'
               '7. Measurability / σ-algebra subtleties.\n'
               '8. Quantifier drift between prose and formula.\n'
               '9. Proof-body cycles that do not go through `\\ref`.\n'
               '10. Errors in cited external results (Davis-Kahan constants etc.).\n')

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text('\n'.join(out))
    print(f'Wrote {args.out}')


if __name__ == '__main__':
    main()
