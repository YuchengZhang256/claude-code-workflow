# <DOMAIN> Research Wiki

Persistent, compounding knowledge base for <DOMAIN>. Karpathy-style: knowledge
is compiled once into a Markdown wiki and grows compounding value as sources
are added. This is a research wiki, not a code project.

## Purpose & Boundaries

- `raw/` contains source documents and attachments. Treat it as immutable evidence.
- `wiki/` contains maintained knowledge pages. Edits should improve long-term retrieval, cross-reference quality, or research usefulness.
- `CLAUDE.md` (this file) is the local operating guide. Prefer judgment over ritual: do the smallest correct wiki maintenance that preserves consistency.
- The wiki is browsed in Obsidian. Use `[[wikilinks]]` for internal references and keep `wiki/index.md` useful as the human table of contents.
- Conversation with the user is in Chinese by default (per global CLAUDE.md). Wiki pages are written in English.

Directory shape:

```text
raw/                     <- source documents; do not edit
wiki/
  index.md               <- master catalog
  log.md                 <- operation log
  sources/               <- one page per ingested source
  concepts/              <- reusable concepts and topics
  entities/              <- methods, math objects, proof techniques, inequalities, named results
  comparisons/           <- side-by-side analyses
  synthesis/             <- cross-source overviews and research roadmaps
CLAUDE.md                <- this guide
```

## Page Schema & Types

Every page uses this frontmatter:

```yaml
---
title: "Page Title"
type: source | concept | entity | comparison | synthesis
subtype:             # entity only: algorithm | math_object | proof_technique | inequality
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: []          # raw filenames or source pages this page draws from
related: []          # related page filenames, without .md
tags: []
---
```

Filenames: lowercase, underscores, no spaces.

- `wiki/sources/{first_author}_{year}_{slug}.md` — Citation, Key Contributions, Setting, Methodology, Main Results, Connections, Limitations.
- `wiki/concepts/{snake}.md` — Definition, Formal Statement, Properties, Relationships, Open Questions, Key References.
- `wiki/entities/{snake}.md` — algorithm / math_object / proof_technique / inequality (set `subtype`).
- `wiki/comparisons/{snake}.md` — What's Compared, Comparison Table, Trade-off, When to Use.
- `wiki/synthesis/{snake}.md` — Thesis, Evidence, Open Questions, Future Directions.

## Operating Modes

### Ingest

Trigger: user provides a source, says "ingest", or drops a file in `raw/`.

1. **Extract** the source. For PDFs use `pdftotext` (preferred) or `ocrmypdf` for scans. If both fail, report the blocker.
2. **Apply the `paper-reader` skill** for structured analysis (Task / Challenge / Insight / Flaw / Motivation) when the source is a research paper. Do not re-implement the framework.
3. **Discuss** with the user before writing — surface what's worth emphasizing, contradictions with existing pages, and which connections matter.
4. **Create the source page** under `wiki/sources/`.
5. **Update or create** the concept / entity / comparison / synthesis pages the source genuinely improves. One narrow source does not need to touch every related page.
6. **Add bidirectional `[[wikilinks]]`** where they help navigation.
7. **Update `wiki/index.md`** for created, renamed, or deleted pages.
8. **Append to `wiki/log.md`** for persistent wiki changes.

### Query

Trigger: user asks a domain question or says "query the wiki".

- Answer first using `wiki/index.md` and relevant pages. Cite as `[[wikilinks]]`.
- Do **not** create a page by default. File only if the answer (a) synthesizes 3+ pages, (b) reveals a gap or contradiction, or (c) is likely to be cited again.
- If a page is created, update `wiki/index.md` and append to `wiki/log.md`.

### Lint

Quick lint (run via `python3 ~/.claude/skills/research-wiki/scripts/lint.py wiki/`) catches:
broken `[[wikilinks]]`, orphan pages, frontmatter drift, stub pages, source-less concept pages.

Full audit (LLM-driven, on request): contradictions across related pages, stale claims superseded by newer sources, missing cross-references, math spot-checks for `inequality` and `proof_technique` entities.

Group issues by type. Apply fixes only when explicitly asked; otherwise report and ask.

## Tool Policy

- Local, inspectable tools first: `rg`, `pdftotext`, OCR utilities, direct file reads.
- Use academic skills (`paper-reader`, `paper-lookup`, `literature-review`) when present in the environment.
- Do not rely on unverified external model CLIs. External review is opt-in only.
- For web claims that may have changed, verify with current sources before writing them in.

## Core Rules

1. Never modify `raw/` unless the user explicitly asks.
2. Protect user work: do not revert, overwrite, commit, push, or amend without explicit instruction.
3. Wiki content in English; conversation with the user in Chinese per global config.
4. Maintain valid frontmatter. Refresh `updated` whenever a page changes.
5. Use `[[wikilinks]]` when mentioning an existing wiki page's concept, source, or entity.
6. Update `wiki/index.md` when pages are created, deleted, renamed, or materially reclassified.
7. Append to `wiki/log.md` when ingest / query-filing / lint creates persistent changes.
8. Do not pre-populate speculative pages. Create only from real sources, durable synthesis, or explicit user requests.
9. Flag contradictions explicitly with a `> **Contradiction**:` blockquote and link both sides.
10. Provenance-tag important claims (theorems, rates, algorithmic guarantees) with a source citation or `(cf. [[page1]], [[page2]])`.
11. Math formatting: Obsidian wiki pages use MathJax `$...$` and `$$...$$`; chat responses follow global CLAUDE.md (no inline `$...$` in chat); plain text in terminals.
12. Filenames: lowercase, underscores, no spaces, no special characters.

## Domain-Specific Notes

<!-- Edit this section to capture per-wiki conventions:
     - Preferred notation (e.g., $A_n \to a$ vs $A_n \xrightarrow{p} a$)
     - Citation style (e.g., "Author (Year)" vs "[Year]")
     - Specific exclusions (e.g., "do not ingest non-peer-reviewed preprints")
     - Domain-specific entity subtypes
     - Special page-type extensions
-->

(none yet)
