---
name: handoff
description: "Compress the current session into a HANDOFF.md in the working directory so the next agent can resume without loss of context. Run this at the end of any significant session."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Handoff — Session Continuity Skill

**Purpose**: Capture everything the next agent needs to continue this work
seamlessly, even though it will have no memory of this conversation.

## When to run

- Before ending a long or complex session
- When the user says `/handoff`, `handoff`, or "save context"
- When the user is about to close the conversation and wants to resume later

## What to produce

Write (or overwrite) a file named `HANDOFF.md` in the **current working directory**.

The document must be written from the perspective of a **briefing note to a
future agent** — not a conversation summary. The reader has never seen this
conversation. Every fact must be self-contained.

---

## Output template

Use the following structure. Omit any section that has no meaningful content.
Do not leave empty sections.

```markdown
# Handoff — {project or task name}

**Last updated**: {YYYY-MM-DD}
**Working directory**: {absolute path}
**Status**: {In Progress | Blocked | Ready for next step}

---

## Goal

{1–3 sentences. What is the user trying to accomplish overall? Why does it matter?}

## Current State

{What is the actual state of the system/code/task right now? Be specific. Name files, branches, services, configs. Write what IS true, not what was changed.}

## Completed

{Bullet list of concrete things that are done and verified. Past tense. No process narration — just outcomes.}

## In Progress / Unfinished

{What was actively being worked on when the session ended? Be precise enough that the next agent can pick it up immediately.}

## Next Steps

{Ordered list of what should be done next. Most important first. Be specific enough to act on.}

## Key Decisions

{Decisions made during this session and their rationale. Include why alternatives were rejected if relevant.}

## Do Not

{Things that were tried and failed, approaches to avoid, known pitfalls. Start each item with "Do not..." or "Avoid..."}

## Important Files

{List of files central to this work, with a one-line description of their role.}

## Context & Caveats

{Anything else the next agent must know: constraints, dependencies, environment quirks, user preferences for this project.}
```

---

## Compression rules

- **No conversation traces**: Never write "we tried", "the user asked",
  "I noticed". Write what is true now.
- **No process narration**: Omit failed attempts, back-and-forth, or
  exploration unless it becomes a "Do Not" warning.
- **No hedging**: Do not write "it seems like" or "probably". If unsure,
  flag it explicitly: `(unverified)`.
- **Merge duplicates**: If the same fact was established multiple times,
  write it once — the final, most complete version.
- **Concrete over vague**: "Modified `src/api/auth.ts` line 42 to use Bearer
  tokens" beats "updated authentication".

---

## Execution

1. Review the full conversation context.
2. Extract all facts relevant to continuing the work.
3. Write `HANDOFF.md` to the current working directory using the template above.
4. Confirm to the user: "Handoff saved to `{path}/HANDOFF.md`."

If `HANDOFF.md` already exists, read it first and merge — keep any sections
still valid, update sections that have changed, add new sections.

---

## Pairing with CLAUDE.md

For the handoff loop to close, add this rule to your `~/.claude/CLAUDE.md`
(already included in `dotclaude/CLAUDE.md.template`):

> **At the start of every conversation, check if `HANDOFF.md` exists in the
> working directory. If it exists, read it immediately before doing anything
> else.**

Without that rule, handoff files produce no automatic effect — the next agent
will not know to look for them.
