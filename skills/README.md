# Skills

This directory contains the skills that ship with `claude-code-workflow`.
Each skill is a directory under `skills/<name>/` with a `SKILL.md` file
(and optionally `scripts/`, `templates/`).

## Installing

Skills live at `~/.claude/skills/<name>/`. Copy individual skills, or use
the repo installer:

```bash
# Install all skills
./scripts/install.sh --apply

# Or install individual skills manually
cp -r skills/web-access ~/.claude/skills/
chmod +x ~/.claude/skills/web-access/scripts/*.sh
```

No restart is needed. Claude Code picks up new skills at the start of the
next conversation.

## Included skills

| Skill | Purpose | External dependencies |
|---|---|---|
| [web-access](./web-access/) | Fetch web pages that built-in `WebFetch` can't read (Cloudflare, SPAs, paywalls) | `curl`, `python3`; optional: `pandoc`, `jq`, `curl-impersonate`, Chrome DevTools MCP |
| [handoff](./handoff/) | Compress a session into `HANDOFF.md` for the next agent | none |
| [simplify](./simplify/) | Review and fix changed code for reuse, quality, efficiency | `git` |
| [research-wiki](./research-wiki/) | Karpathy-style per-domain persistent knowledge wiki | `git`; recommended: Obsidian (for browsing) |
| [multi-model-review](./multi-model-review/) | Adversarial review protocol across model families | any external-model CLI that accepts `--diff` or `-f` |

## Skill anatomy

Minimum viable skill — a single `SKILL.md`:

```
skills/my-skill/
  SKILL.md         # YAML frontmatter + markdown body
```

With scripts:

```
skills/my-skill/
  SKILL.md
  scripts/
    run.sh         # extracted logic, invoked from SKILL.md
```

The YAML frontmatter that Claude Code requires:

```yaml
---
name: my-skill
description: "One-sentence trigger description. Be specific about when this skill should activate vs. when it should not."
allowed-tools: Read, Edit, Bash, Grep   # optional allowlist
---
```

The `description` field is what Claude reads to decide whether to invoke
the skill on a given turn. Write it like a trigger rule, not a marketing
blurb: list the exact words / situations that should activate it, and
explicitly name the things that should NOT.

## Companion skills (not shipped here — install separately)

These are third-party or personal skills the workflow references:

- **Anthropic official four-pack** (`docx` / `xlsx` / `pdf` / `pptx`) —
  clone from https://github.com/anthropics/skills and drop into
  `~/.claude/skills/`. If you install `pdf`, edit its `description` to
  mention *manipulation only* so it does not conflict with your PDF
  *extraction* tool.
- **`chrome-devtools`** (Anthropic official) — for performance testing,
  Core Web Vitals, Lighthouse.
- **A PDF extraction skill** — e.g. a wrapper around `pdftotext` /
  `pdfplumber` / an LLM-based extractor. `web-access` defers to one via
  exit code 2.

## Authoring your own skill

See [`../docs/skill-authoring-guide.md`](../docs/skill-authoring-guide.md)
for the full methodology — the short version: start with a `SKILL.md`,
extract anything longer than a few lines into `scripts/`, write skill
boundaries explicitly, smoke-test, then adversarial-review with a
different-family model.
