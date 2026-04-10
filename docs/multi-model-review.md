# Multi-Model Review

A protocol for catching the bugs a single model will always miss — the ones
that live in its blind spots. Pair a precise verifier with an adversarial
stress-tester from a **different model family**, then arbitrate.

## Why different families

Models from the same family share training data, training objectives, and
therefore blind spots. Two GPT-class models reviewing each other's work
find roughly the same bugs. Two Claude-class models do the same. The
interesting delta comes from crossing family boundaries: a Claude model
verifying + a GPT-class model stress-testing (or vice versa) catches bugs
that neither would catch alone.

**Empirical attribution** from the `web-access` skill development (see
[case-studies/web-access-15-bugs.md](./case-studies/web-access-15-bugs.md)):

```
Test method                Bugs found     Percentage
────────────────────────────────────────────────────
Self-review                    9            60%
Smoke test                     2            13%
Adversarial review (GPT)       4            27%
                              ──           ────
Total                         15          100%
```

The 27% from adversarial review were the **hardest** bugs:

1. Shell `pipefail` + `SIGPIPE` interaction causing silent failure of a
   challenge-page detector
2. URL query parameter not percent-encoded, causing `&` in the input to
   corrupt an API call
3. Case-sensitive PDF extension regex missing `.PDF`, `.Pdf`, etc.
4. A comment that described a bug as acceptable when it was actually
   broken (not a code bug, but a judgment error the author couldn't
   self-catch)

No amount of self-review or smoke testing would have caught these.

## Roles

| Role | Model | Job |
|---|---|---|
| **Verifier** | Primary (you) | Systematic first-pass review. Algebraic / type / logic verification. Low false-positive rate. |
| **Adversarial reviewer** | Different family | Fresh eyes. Assumes bugs exist. Finds implicit-assumption breaks, encoding issues, shell gotchas. High (~30%) false-positive rate. |
| **Arbitrator** | Primary (second pass) | Reconciles adversarial findings against the original work. Distinguishes real bugs from false positives. |

## Protocol

### Step 1 — Verifier pass

Do a careful self-review first. Walk every checklist you know:

- Boundary conditions
- Edge cases (empty input, single element, max size)
- Failure modes of every external call
- Correctness of every assumption the code makes
- Type and algebraic sanity

Write your findings down — you will compare them against the adversarial
pass.

### Step 2 — Adversarial pass

Invoke an external-model CLI that can attach files or a diff. Critical
rule: **the external model cannot read your filesystem.** You must attach
the code explicitly:

```bash
# Preferred: attach the current git diff (always fresh, no stale files)
<cli> review --diff --mode adversarial "<adversarial prompt>"

# Or attach specific files
<cli> review -f src/module.py -f src/helper.py "<adversarial prompt>"

# Or by glob
<cli> review --files 'src/**/*.rs' "<adversarial prompt>"
```

**Adversarial prompt template**:

```
You are an adversarial code reviewer. Assume there ARE bugs in this code
or proof — your job is to find them. Do not validate. Do not summarize.

For each issue:
  1. Point to the exact line or step
  2. Describe the bug
  3. Give a concrete input / scenario that triggers it
  4. Rate severity: critical / major / minor

Focus especially on:
  - Boundary conditions
  - Implicit assumptions about inputs
  - Error paths and silently-swallowed exceptions
  - Encoding / locale / case-sensitivity issues
  - Integer overflow, off-by-one, float precision
  - Shell quoting, word splitting, pipefail + SIGPIPE
  - Race conditions, order-of-operations bugs
  - Dependency-chain breaks

Be blunt. Do not soften findings.
```

### Step 3 — Arbitration

The external model will return a list of findings. Roughly **30% of them
will be false positives**. The verifier (you) must walk each finding and
decide:

| Verdict | Action |
|---|---|
| **Real bug** | Add to fix list |
| **False positive** | Note why (e.g. "caller guarantees input is non-empty") so the user can see your reasoning |
| **Unclear** | Flag for user decision, do not silently discard |

Do not blindly apply adversarial findings — that is how false-positive
"fixes" introduce real bugs.

### Step 4 — Fix and loop

Apply the real fixes. If a fix is non-trivial, run step 2 again on the
fixed version — fixes can introduce new bugs.

**Stop conditions**:

- Adversarial pass returns no new critical findings
- Three rounds completed (diminishing returns after that)
- User decides the current state is acceptable

## Output format

Report to the user at the end:

```
Multi-model review complete.

Verifier findings:      N   (all addressed)
Adversarial findings:   M   (K real / J false positives / L unclear)
Rounds run:             R
Final verdict:          SHIP / NEEDS REWORK / NEEDS USER DECISION

Real bugs fixed:
  1. <one-line description> — <file:line>
  2. ...

False positives (no action, kept for transparency):
  1. <finding> — <reason it's wrong>

User decisions needed:
  1. <unclear finding> — <what to decide>
```

## Cost management

Adversarial passes cost real API calls. To keep the bill manageable:

- Start with the smallest diff that makes sense — review commit by commit,
  not branch vs main
- Use `--diff` rather than `--files '**/*.py'` — the diff is smaller
- Cap at 3 rounds unless the user explicitly asks for more
- Skip multi-model review for trivial changes, style edits, docs-only PRs

## Integration

The `multi-model-review` skill in this repo (`skills/multi-model-review/`)
is a self-contained prompt + protocol you can trigger directly. Pair it
with a CLAUDE.md rule so Claude reaches for it when the user asks for
"rigorous review":

```markdown
## Multi-Model Review Protocol

When the user asks for rigorous review (proofs, code, architecture),
follow `~/.claude/skills/multi-model-review/SKILL.md`.
```

The skill is CLI-agnostic — it will work with any external-model CLI
that accepts a `--diff` or `-f <file>` flag. You bring the adversarial
model; the skill brings the protocol.

## What multi-model review is NOT

- **Not a substitute for self-review** — the verifier pass still finds
  60% of bugs. Skipping it doesn't save time; it just shifts cost to the
  adversarial pass, which is more expensive per bug.
- **Not a substitute for smoke testing** — environment assumptions show
  up at runtime, not during code review.
- **Not a substitute for user judgment** — unclear findings go to the
  user. Do not guess.
- **Not for every change** — trivial changes don't need it.
