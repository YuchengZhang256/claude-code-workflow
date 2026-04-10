---
name: multi-model-review
description: "Run an adversarial multi-model review on a proof, non-trivial diff, or architecture decision: primary verifier → adversarial stress-tester (different model family) → primary arbitrator. ACTIVATE ONLY when the user explicitly asks for 'rigorous review', 'adversarial review', 'stress test', 'multi-model review', 'check this proof', or names a specific high-stakes artifact (migration, security fix, proof, algorithm) that must not ship with a silent bug. Do NOT use for: trivial edits, formatting changes, docs-only PRs, exploratory prototypes, general 'can you take a look' requests, or cases where a single-model self-review is clearly sufficient. Works with any external-model CLI that can attach files or a git diff."
allowed-tools: Read, Bash, Grep, Glob
---

# multi-model-review — adversarial cross-model review

**Purpose**: Catch the class of bugs a single model will miss because they
live in its blind spots. Different models fail differently; pairing a
precise verifier with an adversarial stress-tester catches more real issues
than either alone.

## When to run

- The user asks for a "rigorous review", "adversarial review", "stress
  test", or "second opinion"
- The user is about to ship a proof, algorithm, migration, or security fix
  where a silent bug is expensive
- A diff is large enough that self-review feels insufficient

**Not worth running for**: trivial changes, style edits, docs-only PRs,
exploratory prototypes.

## Model roles

| Role | Who | Strengths | Weaknesses |
|---|---|---|---|
| **Verifier** (primary) | The currently-active model (you) | Systematic coverage, algebraic/probabilistic precision, low false-positive rate | Can miss "looks right but isn't" bugs in its own work |
| **Adversarial reviewer** | A **different** external model, invoked via a CLI that accepts `--diff`, `--files`, or `-f <file>` | Fresh eyes, assumes bugs exist, good at structural logic flaws and implicit-assumption breaks | Higher false-positive rate (~30% in practice) — its findings need arbitration |
| **Arbitrator** (primary, second pass) | The verifier again, re-reading adversarial findings against the original work | Reconciles conflict, distinguishes real bugs from false positives | None beyond the verifier's baseline |

The adversarial reviewer **must be a different model family** than the
verifier. Same-family models share blind spots.

## Protocol

### Step 1 — Verifier pass (self)

Before invoking anything external, do one careful pass yourself. Check:

- Algebraic / type-level correctness
- Boundary conditions
- Assumptions the proof or code makes about its inputs
- Stated invariants that the code actually maintains

Write these findings down so you can compare against the adversarial pass.

### Step 2 — Adversarial pass (external model)

Invoke an external-model CLI with the work attached. **Critical rule: the
external model cannot read your filesystem.** You must attach the content
explicitly. Common ways, depending on your CLI:

```bash
# Preferred: attach the current git diff (always fresh)
<cli> review --diff --mode adversarial "Find every bug you can. Assume bugs exist."

# Or attach specific files
<cli> review -f src/module.py -f tests/test_module.py "Adversarial review."

# Or attach by glob
<cli> review --files 'src/**/*.rs' "Stress-test this implementation."
```

**Prompt template** for the adversarial model:

```
You are an adversarial code reviewer. Assume there ARE bugs in this code or
proof — your job is to find them. Do not validate. Do not summarize. For
each issue you find:

1. Point to the exact line or step.
2. Describe the bug.
3. Give a concrete input / scenario that triggers it.
4. Rate severity: critical / major / minor.

Focus on: boundary conditions, implicit assumptions, error paths, race
conditions, encoding / locale issues, integer overflow, off-by-one,
dependency-chain breaks, silently-swallowed errors. Be blunt.
```

### Step 3 — Arbitration (self, second pass)

Take the adversarial findings and, **for each one**, decide:

- **Real bug** — add to the fix list.
- **False positive** — note why (e.g. "the caller guarantees this"), so the
  user can see your reasoning.
- **Unclear** — flag for the user to decide, do not guess.

**Do not blindly apply adversarial findings.** ~30% of them will be wrong.
The verifier's job in step 3 is to distinguish signal from noise.

### Step 4 — Fix and loop

Apply the real fixes. If the fix is non-trivial, run step 2 again on the
fixed version — a fix can introduce new bugs.

Stop when the adversarial pass returns no new critical findings (or after
three rounds — diminishing returns after that).

## Output format

Report to the user:

```
Multi-model review complete.

Verifier findings:      N   (all addressed)
Adversarial findings:   M   (K real / J false positives / L unclear)
Rounds:                 R
Final verdict:          SHIP / NEEDS REWORK / NEEDS USER DECISION

Real bugs fixed:
  - ...
False positives (no action, recorded for transparency):
  - ...
User decisions needed:
  - ...
```

## Cost management

Adversarial passes cost real API calls. To keep cost down:

- Start with the smallest diff that makes sense — review commit by commit,
  not branch vs main
- Cap at 3 rounds unless the user asks for more
- Use `--diff` rather than `--files '**/*.py'` when possible — smaller
  payload, faster response

## Integration with CLAUDE.md

Consider adding to `~/.claude/CLAUDE.md` a short rule like:

```markdown
## Multi-Model Review Protocol

When the user asks for rigorous review (proofs, code, architecture) using
multiple models, follow the pipeline in
`~/.claude/skills/multi-model-review/SKILL.md`.
```

This primes you to reach for this skill at the right moment without the
user having to name it every time.

## Historical note — why this works

In practice (see `docs/case-studies/web-access-15-bugs.md` in this repo), a
single skill accumulated 15 real bugs during development. The bug-finding
attribution was:

- 60% self-review
- 13% smoke test
- 27% adversarial review by a different-family model

The adversarial 27% included the most subtle bugs (shell `pipefail` +
`SIGPIPE` interaction, case-sensitive PDF detection, un-percent-encoded URL
parameters). Self-review and smoke tests cannot substitute for this —
adversarial review finds a different class of bug.
