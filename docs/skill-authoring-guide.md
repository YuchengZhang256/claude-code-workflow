# Skill Authoring Guide

A practical methodology for writing Claude Code skills that actually
change behavior. Drawn from real debugging stories — see
[case-studies/web-access-15-bugs.md](./case-studies/web-access-15-bugs.md)
for the full war story.

## When to write a skill

Write a skill when:

- A built-in Claude Code capability is too weak for your use case
- You find yourself repeating the same multi-step instruction to Claude
  across sessions
- You want Claude to reach for a specific tool reliably when a specific
  situation arises

Do **not** write a skill when:

- A CLAUDE.md rule would do — rules are hard, skills are soft
- The task only matters within one session — just ask directly
- A memory entry would do — if you just want Claude to remember something

## Anatomy

Minimum:

```
skills/my-skill/
  SKILL.md
```

Typical:

```
skills/my-skill/
  SKILL.md
  scripts/
    run.sh
    helper.py
  templates/
    output.md
```

### `SKILL.md` frontmatter

```yaml
---
name: my-skill
description: "<trigger rule — see below>"
allowed-tools: Read, Edit, Bash, Grep    # optional
---
```

The **`description` field is the most important thing you write.** Claude
reads it to decide whether to fire the skill on a given turn. Bad
descriptions produce unreliable skills. Write it as a trigger rule, not a
product blurb.

Good description structure:

```
<one-sentence purpose>.
Use when: <list of trigger conditions — user phrases, situations>.
Do NOT use when: <list of anti-triggers — prevents skill collisions>.
Entry point: <how Claude should invoke it>.
```

### `SKILL.md` body

The body is read **after** the skill has already been matched. At that
point you don't need to convince Claude to use it — you need to tell
Claude how. Structure:

1. **When to trigger** — short list, redundant with the description but
   more specific
2. **When NOT to use** — list the adjacent skills and what they own
3. **Coordination table** — for any situation where another skill could
   plausibly apply
4. **Primary entry point** — the one command the skill exists to wrap
5. **Exit codes / return values** — what each outcome means
6. **Parameters / knobs** — only the ones Claude is likely to tune
7. **Common traps** — things that look right but aren't
8. **Quick reference** — copy-pasteable snippets

Do not put 200 lines of code in the markdown. Extract it.

## The `scripts/` subdirectory

**Why**: long inline commands in `SKILL.md` force Claude to reconstruct
them from prose on every invocation. That is slow, error-prone, and
opaque. Extract anything nontrivial into a script.

**Contract**: the script takes parameters on the command line, writes
content to stdout, progress / errors to stderr, and signals outcome via
exit code. Example from `web-access/scripts/fetch.sh`:

| Exit code | Meaning |
|---|---|
| `0` | Success. Content on stdout. |
| `1` | Usage error. |
| `2` | URL is a PDF — caller should defer to a PDF extractor. |
| `3` | All layers failed — caller should escalate. |

Claude can branch on the exit code in one line:

```bash
OUT=$(bash run.sh "$ARG"); case $? in
  0) use "$OUT" ;;
  2) defer_to_other_skill ;;
  3) escalate ;;
esac
```

Compare that to parsing English-sentence errors out of stderr. Exit codes
are machine-readable and stable.

## The development loop

1. **Write v1** — `SKILL.md` + `scripts/run.sh`. Run it yourself.
2. **Self-review** — read the diff as if you didn't write it. Walk the
   categories from [`philosophy.md`](./philosophy.md) — reuse, dead code,
   over-abstraction, skill-boundary gaps.
3. **Smoke test** — run the script against at least one real input and
   at least one edge case. Verify the exit code is what you expected on
   each. **Do not skip this step** — environment bugs only surface here.
4. **Adversarial review** — paste the script into a different-family
   model and prompt: "Assume there ARE bugs. Find them." See
   [multi-model-review.md](./multi-model-review.md).
5. **Arbitrate adversarial findings** — roughly ~30% will be false
   positives. Distinguish real bugs from noise.
6. **Fix + repeat from step 3** — new fixes can introduce new bugs.

On the `web-access` skill, bug-finding attribution was 60% self-review,
13% smoke test, 27% adversarial review. Skipping any of the three would
have shipped known bugs.

## Authoring checklist

Before declaring a skill done, verify each item:

- [ ] Description is a trigger rule (lists triggers + anti-triggers)
- [ ] Body has a "Do NOT use when" section naming adjacent skills
- [ ] Coordination table present if ≥2 skills could apply
- [ ] Long logic extracted into `scripts/`
- [ ] Script uses exit codes (not English errors) for outcomes
- [ ] Script has a `--help` / usage when no args given
- [ ] Smoke-tested on at least one real input
- [ ] Adversarial-reviewed by a different-family model
- [ ] If a hard rule is needed, written into `CLAUDE.md` (not left as
      skill description only)

## Tests that catch different bug classes

| Test type | Catches | Misses |
|---|---|---|
| Self-review | Logic errors, missing edge cases, dead code | Environment assumptions, implicit-assumption breaks |
| Smoke test | Environment assumptions, runtime errors, encoding issues | Bugs in branches you didn't trigger |
| Adversarial review (different family) | Implicit assumptions, shell gotchas, regex case sensitivity, encoding edge cases | Bugs that only manifest under load or timing |
| User report | Everything the above missed | — |

Run the first three before shipping. Skipping any of them shifts bug
discovery to the user.

## Common mistakes

- **Description written as marketing**: "A powerful new skill for ..." —
  Claude cannot tell when to use this.
- **No anti-triggers**: two skills fight for the same task.
- **Logic in markdown**: Claude reconstructs a 50-line curl every time.
- **English-sentence errors from scripts**: Claude has to parse prose
  instead of branching on exit codes.
- **Declaring done without smoke-testing**: the brotli / NUL truncation
  bug in `web-access` only showed up when the script was actually run.
- **Skipping adversarial review**: ~27% of bugs live in this category and
  cannot be caught any other way.
- **Soft rule where a hard rule was needed**: if Claude must do X, put it
  in CLAUDE.md, not the skill description.
