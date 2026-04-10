# claude-code-workflow

> A battle-tested Claude Code workflow for researchers and power users:
> skills, global hard rules, memory templates, and a Karpathy-style
> persistent knowledge wiki — packaged as a single reproducible repo.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-workflow-blueviolet)](https://docs.anthropic.com/en/docs/claude-code)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)
[![Made with ❤ on macOS](https://img.shields.io/badge/tested-macOS-lightgrey)](#)

```
            ┌─────────────────────────────────────────┐
            │     HARD RULES  ~/.claude/CLAUDE.md     │   injected every turn
            └────────────────────┬────────────────────┘
                                 │
                                 ▼
            ┌─────────────────────────────────────────┐
            │      SKILLS  ~/.claude/skills/*         │   description-matched on demand
            │  web-access · handoff · simplify        │
            │  research-wiki · multi-model-review     │
            └────────────────────┬────────────────────┘
                                 │
                                 ▼
            ┌─────────────────────────────────────────┐
            │  MEMORY  ~/.claude/projects/*/memory/   │   persists across sessions
            │     user · feedback · project · ref     │
            └─────────────────────────────────────────┘
```

---

## Why this repo

Claude Code ships with powerful primitives — `WebFetch`, `Bash`, a skill
system, a memory system, a hook system — but most people use under 5% of
them. The difference between "Claude Code is a better autocomplete" and
"Claude Code runs my entire research workflow" is not the model. It is
the **skills + rules + memory** you layer on top.

This repo is an opinionated, reproducible bundle of that layer, built
from real debugging stories and two philosophy articles:

1. **Extensions past the built-in limits** — e.g. `web-access` punches
   through Cloudflare / SPAs / paywalls where `WebFetch` gives up.
2. **A `CLAUDE.md` template** encoding *hard rules* that actually change
   Claude's behavior — web-fetch escalation, session handoff, PDF
   extraction routing, multi-model review.
3. **A memory system template** covering the four memory types Claude's
   auto-memory spec supports.
4. **A Karpathy-style persistent research wiki** you can clone per
   domain — compile papers into a browsable Obsidian knowledge graph
   instead of re-reading them every session.
5. **An adversarial cross-model review protocol**. In the
   [`web-access` case study](docs/case-studies/web-access-15-bugs.md),
   adversarial review found 27% of the bugs we eventually fixed — a
   class of bug neither self-review nor smoke testing had caught.

Everything here is designed to be **copy-pastable**. The repo is
self-contained; optional companion skills for adjacent workflows (PDF
extraction, Office document manipulation, browser performance testing)
are listed in the "Companion skills" section below with pointers to
their upstream sources.

---

## Quick Start

```bash
git clone https://github.com/YuchengZhang256/claude-code-workflow.git
cd claude-code-workflow

# Dry-run first — prints what would happen, touches nothing
./scripts/install.sh

# Apply
./scripts/install.sh --apply

# Verify
./scripts/sanity-check.sh

# Smoke-test the flagship skill
bash ~/.claude/skills/web-access/scripts/fetch.sh "https://example.com"
```

See [`docs/quickstart.md`](docs/quickstart.md) for the 10-minute tour.

---

## What's inside

### Skills

| Skill | Purpose | External deps |
|---|---|---|
| [**web-access**](skills/web-access/) | Punch through Cloudflare / SPAs / paywalls with a Jina Reader → stealth curl → Wayback → Chrome DevTools MCP fallback chain | `curl`, `python3`; optional `pandoc`, `jq`, `curl-impersonate` |
| [**handoff**](skills/handoff/) | Compress a session into `HANDOFF.md` so the next agent resumes with full context | none |
| [**simplify**](skills/simplify/) | Review changed code for reuse, dead code, over-abstraction, and fix in place | `git` |
| [**research-wiki**](skills/research-wiki/) | Karpathy-style per-domain persistent knowledge wiki — `ingest` / `query` / `lint` operations | `git`; recommended: Obsidian |
| [**multi-model-review**](skills/multi-model-review/) | Adversarial review protocol across model families — verifier → stress-tester → arbitrator | any external-model CLI with `--diff` or `-f` |

### Templates

| File | What it is |
|---|---|
| [`dotclaude/CLAUDE.md.template`](dotclaude/CLAUDE.md.template) | Global hard rules — drop into `~/.claude/CLAUDE.md` and fill in the user section |
| [`dotclaude/settings.json.example`](dotclaude/settings.json.example) | Example `settings.json` with a LaTeX auto-compile hook |
| [`dotclaude/memory/*.template`](dotclaude/memory/) | Memory templates for the four types (user / feedback / project / reference) |
| [`examples/research-wiki-starter/`](examples/research-wiki-starter/) | A clone-ready empty research wiki — `raw/ + wiki/ + CLAUDE.md` |

### Docs

| Doc | Read it when |
|---|---|
| [`docs/quickstart.md`](docs/quickstart.md) | You just cloned and want to be running in 10 minutes |
| [`docs/architecture.md`](docs/architecture.md) | You want to understand how skills + CLAUDE.md + memory interact |
| [`docs/philosophy.md`](docs/philosophy.md) | You want the seven methodology principles in one place |
| [`docs/skill-authoring-guide.md`](docs/skill-authoring-guide.md) | You want to write your own skill |
| [`docs/research-wiki-guide.md`](docs/research-wiki-guide.md) | You want the Karpathy wiki workflow in detail |
| [`docs/multi-model-review.md`](docs/multi-model-review.md) | You want the adversarial review protocol |
| [`docs/case-studies/web-access-15-bugs.md`](docs/case-studies/web-access-15-bugs.md) | You want the war story behind the philosophy |
| [`docs/case-studies/research-wiki-build.md`](docs/case-studies/research-wiki-build.md) | You want a concrete month-by-month wiki walkthrough |

---

## Architecture

Three layers of persistence, each with a different reliability guarantee:

```
HARD RULES        ~/.claude/CLAUDE.md              every turn, forced
   │
   ▼
SKILLS            ~/.claude/skills/<name>/         on-demand, description-matched
   │
   ▼
MEMORY            ~/.claude/projects/*/memory/     across sessions, Claude-curated
```

**Rule of thumb**: things Claude **must** do → `CLAUDE.md`; things Claude
**can** do → skill; persistent facts → memory.

See [`docs/architecture.md`](docs/architecture.md) for the full picture.

---

## Featured: the `web-access` skill

Built-in `WebFetch` fails on Cloudflare, SPAs, and paywalls. `web-access`
is a layered fallback chain with honest exit codes:

```
 Layer 1:  Jina Reader       →  headless browser as a service (80% of cases)
 Layer 2:  Stealth curl      →  Chrome 131 headers + optional curl-impersonate
 Layer 3:  Wayback Machine   →  deleted / paywalled pages
 Layer 4:  Chrome DevTools   →  real browser for auth-gated / interactive pages
```

Single entry point, machine-readable exit codes:

```bash
OUT=$(bash ~/.claude/skills/web-access/scripts/fetch.sh "$URL"); case $? in
  0) use "$OUT" ;;                       # success
  2) hand_to_pdf_extractor ;;            # URL is a PDF
  3) escalate_to_chrome_devtools ;;      # all layers failed
esac
```

**15 bugs, 3 review passes** went into making this skill trustworthy.
Read the full story at
[`docs/case-studies/web-access-15-bugs.md`](docs/case-studies/web-access-15-bugs.md)
— it's the most concrete illustration of the methodology in this repo.

---

## Featured: the research wiki

Inspired by Andrej Karpathy's April-2026
[LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
Instead of re-reading a paper every session, **compile your understanding
once** into a Markdown wiki that persists, cross-links itself, and grows
compounding value as you add sources.

```
~/research/<domain>/
  CLAUDE.md        ← per-wiki schema (loaded when you cd in)
  raw/             ← immutable original PDFs
  wiki/            ← LLM-maintained, browsable in Obsidian
    index.md       ← TOC
    log.md         ← operation log
    sources/
    concepts/
    entities/
    comparisons/
    synthesis/     ← ← ← the highest-value layer
```

Three operations:

- **Ingest**: drop a PDF, say "ingest raw/pearl_2009.pdf" — Claude
  extracts, analyzes, discusses with you, creates a source page, updates
  every related concept page, and commits. Typically touches 5–15 pages
  per ingest.
- **Query**: ask any domain question inside the wiki directory — Claude
  answers from the wiki content, optionally archiving high-value
  syntheses as new pages.
- **Lint**: audit for orphan pages, broken wikilinks, stale frontmatter.

See [`docs/research-wiki-guide.md`](docs/research-wiki-guide.md) and
[`docs/case-studies/research-wiki-build.md`](docs/case-studies/research-wiki-build.md)
for the full workflow.

Bootstrap a new wiki:

```bash
bash ~/.claude/skills/research-wiki/scripts/new-wiki.sh \
    ~/research/my-domain "my domain"
```

---

## Installation

### Option A — scripted (recommended)

```bash
./scripts/install.sh          # dry-run
./scripts/install.sh --apply  # copy into ~/.claude/
./scripts/sanity-check.sh
```

The installer is **safe by default**: it never overwrites existing files
without `--force`, and `--force` makes timestamped backups before
overwriting.

### Option B — manual

```bash
# Skills
cp -r skills/web-access skills/handoff skills/simplify \
      skills/research-wiki skills/multi-model-review \
      ~/.claude/skills/
chmod +x ~/.claude/skills/*/scripts/*.sh

# Global rules (do not overwrite if you already have a CLAUDE.md)
cp dotclaude/CLAUDE.md.template ~/.claude/CLAUDE.md

# Memory templates — place under the project directory you want them in
# (Claude auto-creates one per working-directory project)
```

### Option C — cherry-pick

Every skill is independent. Copy just the one you want:

```bash
cp -r skills/web-access ~/.claude/skills/
chmod +x ~/.claude/skills/web-access/scripts/*.sh
```

No restart required. Claude Code picks up new skills at the start of the
next conversation.

> ⚠️ **If you cherry-pick only some skills, do not copy
> `dotclaude/CLAUDE.md.template` verbatim.** The template's "Technical
> Rules" sections reference `~/.claude/skills/web-access/scripts/fetch.sh`
> and `~/.claude/skills/multi-model-review/SKILL.md`. If those skills
> aren't installed, the rules point to non-existent paths. Either install
> all the referenced skills, or delete the corresponding rule sections
> before copying the template.

---

## Philosophy (the seven principles)

Distilled from real debugging stories — see
[`docs/philosophy.md`](docs/philosophy.md) for the full essay.

1. **Build your own skill when the built-in is too weak.** Complaining
   about `WebFetch` takes five seconds; building `web-access` takes an
   afternoon and returns 100× value per year.
2. **Skills get a `scripts/` subdirectory.** Don't put 50 lines of bash
   in `SKILL.md` markdown — extract it so Claude invokes a parameterized
   script instead of reconstructing long commands from prose.
3. **Multi-layer fallback beats single-point hardening.** Jina + stealth
   curl + Wayback + Chrome DevTools each covers a different failure
   mode.
4. **Skill descriptions must include explicit boundaries.** Without an
   "Do NOT use when" section, two skills will fight over the same
   triggers.
5. **Smoke-test before declaring done.** Environment assumptions (brotli
   support, shell NUL truncation) only surface at runtime.
6. **Adversarial review with a different-family model.** 27% of the bugs
   in `web-access` were found this way — bugs no self-review could ever
   catch.
7. **Hard rules go in `CLAUDE.md`.** Skill descriptions are soft matches;
   `CLAUDE.md` is injected every turn and is the only reliable hard
   constraint.

---

## Companion skills (not shipped here — install separately)

- **Anthropic official four-pack** (`docx` / `xlsx` / `pdf` / `pptx`)
  from https://github.com/anthropics/skills. If you install `pdf`
  alongside a PDF *extraction* tool, edit its description to scope it
  to *manipulation only* so the two skills don't collide.
- **`chrome-devtools`** (Anthropic official) for performance testing,
  Core Web Vitals, Lighthouse.
- **A PDF extraction tool** — `pdftotext`, `pdfplumber`, or an LLM-based
  extractor. `web-access` defers to one via exit code 2.

See [`skills/README.md`](skills/README.md) for the full list and
integration notes.

---

## FAQ

**Does this require a specific Claude plan?**
No. Every skill here works on any Claude Code installation.

**Do I need an API key for anything?**
No. `web-access` uses Jina Reader's anonymous free tier and the public
Wayback API. `multi-model-review` needs whatever CLI you use for your
adversarial model, and those usually need their own key — but that's
external to this repo.

**Is there any personal data in this repo?**
No. All user-specific content (paths, names, tokens, research interests)
has been extracted into templates with `<placeholder>` markers. Run
`grep -ri 'your-placeholder' dotclaude/` to see what you should fill in.

**Can I use only one skill without the rest?**
Yes. Every skill is a standalone directory under `skills/`. `cp -r` the
one you want; the others are independent.

**Does `install.sh` overwrite my existing `CLAUDE.md`?**
No. The installer skips any file that already exists unless you pass
`--force`, and `--force` makes a timestamped backup before overwriting.

**How do I write my own skill?**
See [`docs/skill-authoring-guide.md`](docs/skill-authoring-guide.md).
The short version: start with a `SKILL.md`, extract long logic into
`scripts/`, write explicit boundaries, smoke-test, then adversarial-
review with a different-family model.

**What if a skill collides with one I already have?**
Edit the `description` field of either skill to include a "Do NOT use
when the task involves X" clause naming the other skill. Descriptions
are how Claude decides which skill to fire — narrowing them is the
intended fix.

**Why not RAG for the research wiki?**
See [`docs/research-wiki-guide.md`](docs/research-wiki-guide.md) for the
long answer. Short version: RAG retrieves chunks and re-reasons every
query; the wiki is compiled structured knowledge with explicit
cross-links, and the value compounds as you add more sources.

---

## Contributing

PRs welcome — especially new skills, more case studies, and translations
of the docs.

Before submitting a skill PR:

1. Read [`docs/skill-authoring-guide.md`](docs/skill-authoring-guide.md)
2. Include a `SKILL.md` with explicit skill boundaries
3. Extract long logic into `scripts/`
4. Include a "smoke test" section in the PR description describing how
   you verified the skill works
5. Ideally, run a multi-model adversarial review and list the bugs found

---

## License

[MIT](./LICENSE). The Anthropic official skills referenced here
(`docx` / `xlsx` / `pdf` / `pptx` / `chrome-devtools`) are **not**
redistributed — see [the Anthropic skills repo](https://github.com/anthropics/skills)
for those.

---

## Acknowledgments

- **Andrej Karpathy** for the
  [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  that inspired the research-wiki skill.
- **Anthropic** for Claude Code and the skill architecture that makes
  this whole workflow possible.
- The authors of the two reference essays that shaped this repo's
  philosophy (the `web-access` 15-bug story and the Karpathy-wiki
  implementation guide).
