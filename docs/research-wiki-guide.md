# Research Wiki Guide

A Karpathy-style, LLM-compiled, persistent knowledge wiki for academic
research. This doc is the user-facing guide; the machine-readable schema
lives in `skills/research-wiki/SKILL.md` and
`examples/research-wiki-starter/CLAUDE.md`.

## Inspiration

Andrej Karpathy's April-2026 gist laid out a simple observation: most LLM
conversations start from zero every time. You read a paper, ask the model
about it, get a good answer, close the window — and the understanding
evaporates. Next time, you re-read, re-ask, re-understand.

His solution: **compile** the understanding into a persistent wiki. Not a
RAG index, but human-readable Markdown pages with explicit cross-links,
maintained by the LLM under human supervision.

This repo packages that idea into a reusable skill + starter template.

## Why not RAG?

| Dimension | RAG | Wiki |
|---|---|---|
| Query cost | Re-retrieves + re-reasons every time | Precompiled, reads a few pages |
| Cross-refs | Implicit, chunk-level | Explicit `[[wikilinks]]` |
| Contradictions | Invisible — two chunks can disagree without anyone noticing | Surfaced on ingest: LLM must decide how to reconcile |
| Browsability | Not really — you query, you don't browse | Full Obsidian graph view |
| Compounding | None — more chunks, same retrieval | Real — each new source enriches existing pages |
| Human role | Consume outputs | Curate + direct — LLM drafts, human decides emphasis |

RAG is a search engine. A wiki is your second brain.

## The three-layer architecture

```
~/research/<domain>/
  CLAUDE.md         Schema + rules for this wiki       ← human maintains
  raw/              Original papers / PDFs             ← immutable
  wiki/             Compiled knowledge pages           ← LLM maintains
    index.md        Table of contents
    log.md          Append-only operation log
    sources/        One page per document
    concepts/       One page per concept
    entities/       People, algorithms, datasets
    comparisons/    Head-to-head analyses
    synthesis/      Cross-source big-picture pages
```

**Key rule**: `raw/` is sacred. You never edit it. You can always
re-derive `wiki/` from `raw/` + `CLAUDE.md` — no data is lost if `wiki/`
is thrown away.

## Bootstrapping a new wiki

```bash
# Via the skill's helper script
bash ~/.claude/skills/research-wiki/scripts/new-wiki.sh \
    ~/research/causal-inference "causal inference"

# Or manually
cp -r <repo>/examples/research-wiki-starter ~/research/causal-inference
cd ~/research/causal-inference
git init && git add -A && git commit -m "bootstrap causal-inference wiki"
```

Edit `CLAUDE.md` at the wiki root to fill in domain-specific rules
(preferred notation, citation style, exclusions, seed concepts).

## The three operations

### Ingest

```
> ingest raw/pearl_2009_causality.pdf
```

Claude will:

1. Extract the PDF content via your PDF extraction tool
2. Read `wiki/index.md` to see what concepts already exist
3. Run a structured analysis (task / challenge / insight / method /
   results / limitations)
4. **Ask you** what to emphasize, what connections you see, what
   contradicts existing pages
5. Create the source page at `wiki/sources/pearl_2009_causality.md`
6. Update or create every concept / entity / comparison page the paper
   touches
7. Add bidirectional `[[wikilinks]]`
8. Update `wiki/index.md` and append to `wiki/log.md`
9. `git commit`

Expect 5–15 pages touched per ingest. The compounding matters: a new
paper doesn't only add its own page, it enriches every existing concept
page it references.

**Real example** (Hernan & Robins 2020, *Causal Inference: What If?*,
ingested against a wiki that already had Pearl 2009):

- 1 new source page
- 7 new concept pages (IPW, g-formula, g-estimation, MSM, propensity
  score, doubly robust, target trial)
- 8 existing concept pages updated (potential outcomes, ATE,
  exchangeability, confounding, ...) because Pearl had already introduced
  them under the SCM framing and Hernan-Robins treats them under the
  potential-outcomes framing — the update added the alternative framing
  and cross-linked
- 2 new entity pages (Hernan, Robins)
- 1 new comparison page (potential-outcomes vs SCM)

Total: 19 pages touched from a single ingest. That is the compounding
effect.

### Query

Ask any domain question inside the wiki directory. Claude will:

1. Read `wiki/index.md`
2. Read the relevant pages (+1 hop of wikilinks)
3. Answer, citing pages as `[[wikilinks]]`
4. Decide whether to archive the answer as a new page — **usually not**

A new page is created only if the answer:

- Synthesizes 3+ sources
- Reveals a gap or contradiction
- Is likely to be asked again
- Could be cited in your future writing

Resist the temptation to over-archive. Most queries are throwaway.

### Lint

```
> lint the wiki
```

Claude audits for:

- **Orphan pages** — no incoming wikilinks
- **Broken wikilinks** — `[[foo]]` where `foo.md` doesn't exist
- **Frontmatter drift** — `updated:` older than newest citing source
- **Stub pages** — <150 words, probably abandoned drafts
- **Index staleness** — entries in `index.md` that no longer exist, or
  files in `wiki/` not indexed
- **Duplicate concepts** — two pages that seem to describe the same thing

Claude reports findings; it does not auto-merge duplicates (that needs
your judgment).

## Browsing with Obsidian

Point Obsidian at the wiki root as a vault. Obsidian natively renders:

- `[[wikilinks]]` with click-to-navigate
- The full graph view (each page a node, each wikilink an edge)
- LaTeX math via MathJax (`$inline$` and `$$display$$`)
- Tag index

No plugins required.

## Page-type quick reference

| Type | Directory | Purpose |
|---|---|---|
| `source` | `wiki/sources/` | One per document. Citation, contributions, methodology, results, limitations. |
| `concept` | `wiki/concepts/` | One per idea. Definition, formal statement, properties, key references. |
| `entity` | `wiki/entities/` | People, algorithms, datasets. Short bio, appearances. |
| `comparison` | `wiki/comparisons/` | Head-to-head. Table, trade-offs, when-to-use. |
| `synthesis` | `wiki/synthesis/` | Cross-source big-picture. **Highest value pages.** |

Templates for each live in
`skills/research-wiki/templates/`.

## Rules

- **Math is LaTeX.** `$inline$`, `$$display$$`.
- **Wikilinks are mandatory** when a concept has its own page.
- **Every factual claim cites a source page** via wikilink.
- **Frontmatter `updated:` field** gets bumped on every edit.
- **File names** are `snake_case.md`, lowercase, no spaces.
- **Never modify `raw/`**.
- **Commit after every ingest / lint-with-fixes**.

## Common mistakes

- **Treating the wiki like note-taking** — it's for compiled understanding,
  not raw notes. Raw notes go in `raw/`.
- **Skipping the "discuss with user" step on ingest** — the wiki encodes
  *your* perspective, not just the paper's content. If Claude ingests
  without asking, the wiki becomes generic summaries.
- **Over-archiving queries** — most queries don't deserve a new page. Only
  archive if the answer has durable value.
- **Orphan pages** — every concept page should have at least one incoming
  wikilink from a source page or a synthesis page.
- **Equivocation** — when sources disagree, the page should list both
  positions with citations, not hedge. "X says A; Y says B (see
  [[x_2020]], [[y_2023]])", not "some argue A, others argue B".

## Seed reading

- Karpathy's original gist on LLM Wikis:
  https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- [`architecture.md`](./architecture.md) — how this fits with the rest
  of the workflow
- [`case-studies/research-wiki-build.md`](./case-studies/research-wiki-build.md)
  — a concrete walkthrough
