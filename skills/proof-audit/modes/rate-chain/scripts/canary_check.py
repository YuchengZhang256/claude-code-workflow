#!/usr/bin/env python3
"""
Phase B.4 — Canary self-check.

Parses references/known_rates.md for ground-truth rate_dicts, then compares
against the extracted rate_table.json entries that the Claude/GPT extractor
also produced for the same canary claims.

Aborts the skill (exit 3) if ≥ --fail-threshold canaries mismatch.
"""

import argparse, json, re, sys
from pathlib import Path


CANARY_RE = re.compile(
    r'^###\s*(?P<name>[^\n]+?)\s*\n'
    r'(?:.*?Rate:\s*`(?P<latex>[^`]+)`\s*\n)?'
    r'.*?Exponents:\s*(?P<json>\{[^\n]+\})',
    re.MULTILINE | re.DOTALL
)


def load_known_rates(path):
    """Parse known_rates.md sections of the form:

    ### <Name>
    ... prose ...
    Rate: `<LaTeX>`
    Exponents: {"log": 0.5, "underline_mu": -0.5}
    """
    text = Path(path).read_text()
    known = {}
    for m in CANARY_RE.finditer(text):
        name = m.group('name').strip().lower().replace(' ', '_')
        try:
            exps = json.loads(m.group('json'))
            known[name] = {'rate_dict': exps, 'latex': m.group('latex') or ''}
        except json.JSONDecodeError:
            pass
    return known


def normalize(d):
    return {k: round(float(v), 2) for k, v in (d or {}).items() if abs(float(v)) > 1e-9}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted', required=True, help='canary_extractions.json (produced by Claude '
                                                     'applying the Extractor-A prompt on each canary claim)')
    ap.add_argument('--known', required=True, help='references/known_rates.md')
    ap.add_argument('--out', required=True)
    ap.add_argument('--fail-threshold', type=int, default=3,
                    help='Abort the skill if >= this many canaries mismatch')
    args = ap.parse_args()

    known = load_known_rates(args.known)
    if not known:
        print('ERROR: no canaries parsed from known_rates.md', file=sys.stderr)
        sys.exit(2)

    extracted = json.load(open(args.extracted))
    # extracted is a list of {name, rate_dict}
    ext_by_name = {e['name'].lower().replace(' ', '_'): e for e in extracted}

    results = []
    mismatches = []
    for name, gt in known.items():
        ex = ext_by_name.get(name)
        if ex is None:
            results.append({'name': name, 'status': 'MISSING',
                            'expected': gt['rate_dict'], 'got': None})
            mismatches.append(name)
            continue
        if normalize(ex.get('rate_dict', {})) == normalize(gt['rate_dict']):
            results.append({'name': name, 'status': 'PASS',
                            'expected': gt['rate_dict'], 'got': ex['rate_dict']})
        else:
            results.append({'name': name, 'status': 'FAIL',
                            'expected': gt['rate_dict'], 'got': ex['rate_dict']})
            mismatches.append(name)

    passed = sum(1 for r in results if r['status'] == 'PASS')
    total = len(results)
    report = {
        'total': total,
        'passed': passed,
        'failed': total - passed,
        'pass_rate': round(passed / total, 3) if total else 0,
        'fail_threshold': args.fail_threshold,
        'aborted': len(mismatches) >= args.fail_threshold,
        'results': results,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(args.out, 'w'), indent=2, ensure_ascii=False)

    print(f'Canary: {passed}/{total} passed. '
          f'{"ABORTING" if report["aborted"] else "OK to proceed"}.')

    if report['aborted']:
        print('The extraction pipeline failed the canary. Skill aborting to prevent '
              'garbage chain-break reports. See canary_report.json for details.',
              file=sys.stderr)
        sys.exit(3)


if __name__ == '__main__':
    main()
