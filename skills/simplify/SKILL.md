---
name: simplify
description: "Review the current git diff for reuse, dead code, over-abstraction, premature optimization, and needless complexity, then apply fixes in place. ACTIVATE when the user says 'simplify', '/simplify', 'clean this up', 'polish', 'review your own work', or 'tighten this diff'. Do NOT use for: docs-only changes, pure renames, whole-codebase refactors (this skill is scoped to the current diff only), or when no code has changed yet. Scans `git diff` (default: HEAD) — if there is no diff, exits without action."
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# simplify — self-review for changed code

**Purpose**: Catch the easy wins that a first-pass implementation usually
misses — reuse, deletion, quality, efficiency — and fix them in place before
the user has to ask.

## When to run

- Immediately after finishing a non-trivial edit, before declaring the task
  done
- When the user types `/simplify`, says "simplify", "clean this up",
  "polish", or "review your own work"
- When a diff has grown larger than you expected and you suspect
  over-engineering

## What to look for

Scan the **diff** (not the whole codebase — the goal is changed code only).
Flag anything in these categories:

### 1. Reuse — did you reinvent something?

- Is there an existing helper / utility / library function that does this
  already? (`grep` the repo for the obvious names.)
- Is a pattern copy-pasted from another file? If so, either use the
  original or extract a shared helper — but only if it already appears 3+
  times. Two occurrences is not duplication, it is coincidence.

### 2. Dead code and cruft

- Unused imports, variables, parameters
- Commented-out blocks ("just in case")
- TODO / FIXME notes added in this diff but not actually resolved
- Debug prints / `console.log` / `pp()` / `dbg!`
- Try/except blocks that can never fire or that swallow errors silently
- Error handling for cases that cannot happen given the caller's contract
- Backwards-compat shims for code paths that no longer exist

### 3. Over-abstraction

- A new class, interface, or decorator that has exactly one caller
- A "for future extension" parameter that is never set to anything but its
  default
- An abstraction layer introduced alongside its first implementation, with
  no second implementation in sight
- A config flag for behavior that does not actually vary

**Rule of thumb**: three similar lines are better than a premature
abstraction. Collapse back to the concrete code if there is only one caller.

### 4. Over-commentary

- Comments that explain what well-named code already says
- Multi-paragraph docstrings on functions <10 lines
- Comments referencing the current task, PR, or commit ("fix for issue
  #123") — those belong in the commit message, not the code
- Blocks of removed code left as `// removed` comments

**Keep a comment only when it explains a non-obvious WHY**: a hidden
constraint, a subtle invariant, a workaround for a named bug, behavior that
would surprise a reader.

### 5. Efficiency (only if the delta is obvious)

- O(n²) loops over lists that are clearly going to be large
- Re-reading a file in a loop instead of caching
- `len(list)` repeatedly in a hot loop
- String concatenation in a loop (use join / builder)
- Repeated DB queries inside a loop (batch instead)

**Do not** rewrite working code for speculative performance gains. Only fix
efficiency issues that are obvious from the diff.

### 6. Edge cases that actually matter

- Off-by-one in the loop bound
- Empty-input case untested
- `None` / `null` / `undefined` propagation where the type system does not
  guarantee absence
- Unicode / timezone assumptions

## Execution

1. `git diff` (or `git diff <base>` if the user specified a base) — read it.
2. For each hunk, walk the checklist above.
3. Collect findings. Group by category.
4. **Fix the findings directly.** Do not just report them — this skill is
   for fixing, not auditing. If a finding needs a user decision, flag it as
   a question at the end.
5. Report: "Simplified X files. Removed Y lines. N findings addressed, M
   flagged for user review."

## Anti-patterns (do NOT do these in the name of "simplifying")

- **Do not delete tests** to reduce line count.
- **Do not rename variables** for style preference — only if the current
  name is actively misleading.
- **Do not reformat** untouched code — stay inside the diff.
- **Do not introduce new dependencies** to "simplify" — that is a trade, not
  a simplification.
- **Do not rewrite working code** because you would have written it
  differently. Scope: the issues you actually found, nothing more.

## Scope limit

This skill only looks at the current diff, not the whole codebase. If a
broader refactor is needed, say so at the end and let the user decide —
do not silently expand scope.
