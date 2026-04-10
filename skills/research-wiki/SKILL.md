---
name: research-wiki
description: "Maintain a persistent, Karpathy-style research wiki per domain via three operations: ingest (compile a paper into the wiki), query (answer a question against the wiki), lint (audit pages). ACTIVATE when the user says 'ingest this paper', 'add to wiki', 'query the wiki', 'lint the wiki', 'what does my wiki say about X', or when working inside a directory that already contains a `raw/` + `wiki/` + `CLAUDE.md` layout. Do NOT use for: general literature search (use a paper-lookup skill); one-off paper reading where persistence is not wanted; any directory that does NOT already have the `raw/` + `wiki/` + `CLAUDE.md` layout (bootstrap a new wiki via `scripts/new-wiki.sh` first). Not a RAG system — the wiki is LLM-compiled Markdown, browsable in Obsidian."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# research-wiki — Karpathy-style persistent knowledge

Inspired by Andrej Karpathy's LLM Wiki gist: instead of re-reading and
re-understanding a paper every time you need it, **compile the understanding
once** into a Markdown wiki that persists across sessions, cross-links itself,
and grows compounding value as you add more sources.

This skill is **not a RAG system**. RAG retrieves chunks at query time; the
wiki is structured, hand-curated (by the LLM under human review) Markdown
with explicit `[[wikilinks]]` between concepts. Every source leaves a trace.
Every concept has one page. Every contradiction is flagged.

## When to trigger

- The user says "ingest this paper", "add to wiki", "wiki this"
- The user asks a domain question inside a directory that contains a
  `wiki/` + `raw/` layout, e.g. `~/research/causal-inference/`
- The user says "lint the wiki", "audit the wiki", "what's missing"
- The user says "query the wiki about X"

**Do NOT use this skill for**:
- General literature search — use a paper-lookup skill
- One-off paper reading where the user does not want persistence
- Anything outside a directory that has the `raw/ + wiki/ + CLAUDE.md` layout
  (bootstrap one first; see "Creating a new wiki" below)

## Architecture (three layers)

```
~/research/<domain>/
  CLAUDE.md          # Per-wiki schema: rules, page types, workflows
  raw/               # Immutable: original PDFs, HTML, notes, datasets
  wiki/              # LLM-maintained compiled knowledge
    index.md         # Table of contents — read FIRST on every operation
    log.md           # Append-only operation log
    sources/         # One page per paper / document
    concepts/        # One page per concept
    entities/        # People, algorithms, datasets
    comparisons/     # Head-to-head analyses
    synthesis/       # Cross-source big-picture pages
```

**Key principle: `raw/` is sacred.** You never modify files under `raw/`.
All understanding, analysis, and cross-linking happens in `wiki/`. This
means you can always rebuild the wiki from scratch without losing data.

Each wiki is an independent `git` repo — `git log` is the wiki's growth
story, and every ingest is a commit.

See `examples/research-wiki-starter/` in this repo for a clone-ready skeleton.

## The three operations

### 1. Ingest — compile a new source into the wiki

**Trigger**: "ingest `raw/pearl_2009.pdf`", "add this paper to the wiki".

**Flow**:

1. **Read the source.** For PDFs, use a dedicated PDF extractor
   (`pdftotext` / `pdfplumber` / an LLM-based extractor) — do not rely on
   `WebFetch` or inline `Read` on a large scientific PDF.
2. **Read `wiki/index.md` first** to see what concepts already exist. Every
   subsequent decision depends on this.
3. **Structured analysis.** Produce, internally: title, authors, year, the
   paper's task, the challenge, the key insight, the methodology, the main
   results, limitations. (The `paper-reader` framing is a reasonable default
   if you have that skill; otherwise do it yourself.)
4. **Discuss with the user.** Present the core findings and ask what they
   want emphasized, what connections they see, what contradicts existing
   wiki pages. **Do not skip this step** — the wiki encodes the user's
   perspective, not just the paper's content.
5. **Create the source page** at `wiki/sources/{firstauthor}_{year}_{slug}.md`
   using the source template (see `templates/source.md`).
6. **Update or create concept pages.** For each concept the paper touches:
   - If a page exists, append the new source's treatment and flag any
     agreement or contradiction with existing treatments.
   - If no page exists, create one at `wiki/concepts/{concept_snake}.md`
     using `templates/concept.md`.
7. **Update or create entity pages** (people, algorithms, datasets) the
   same way.
8. **Add bidirectional `[[wikilinks]]`** between the new source page and
   every concept / entity page it touched.
9. **Update `wiki/index.md`** to list the new source and any new
   concept/entity pages.
10. **Append to `wiki/log.md`**: `{date} | ingest | {source} | {N pages touched}`.
11. **Commit.** `git add -A && git commit -m "ingest: {source title}"`

A single ingest typically touches 5–15 pages. The compounding value is the
point: every new paper not only gets its own page but enriches every
existing concept page it touches.

### 2. Query — answer a question against the wiki

**Trigger**: any domain question inside a wiki directory, or "query the
wiki about X".

**Flow**:

1. Read `wiki/index.md` to locate the relevant pages.
2. Read those pages (and their linked neighbors, 1 hop).
3. Synthesize an answer using only the wiki content, citing page names as
   `[[wikilinks]]`.
4. **Decision: archive the answer as a new wiki page?** Create a new page
   (usually under `synthesis/` or `comparisons/`) only if the answer:
   - Synthesizes 3+ existing pages
   - Reveals a gap, contradiction, or pattern not already documented
   - Is likely to be asked again, or cited in future work
5. If you created a new page, update `wiki/index.md` and append to `log.md`.

Most queries do **not** produce new pages. Resist the temptation to
over-document.

### 3. Lint — audit the wiki

**Trigger**: "lint the wiki", "what's stale", "audit".

**Checks**:

- **Orphan pages**: pages with no incoming `[[wikilinks]]` from elsewhere
- **Broken wikilinks**: `[[foo]]` where `wiki/**/foo.md` does not exist
- **Frontmatter drift**: `updated:` older than the newest source that cites
  the page, or missing fields
- **Short pages**: stubs under ~150 words that were probably meant to be
  expanded
- **Index staleness**: entries in `wiki/index.md` that no longer exist, or
  files in `wiki/` not listed in the index
- **Duplicate concepts**: two concept pages that seem to describe the same
  thing under different names — ask the user before merging

Produce a report grouped by category. Do **not** auto-fix orphan/merge
issues — surface them for the user to decide.

## Creating a new wiki

Use the starter in `examples/research-wiki-starter/`:

```bash
cp -r <path-to-this-repo>/examples/research-wiki-starter ~/research/<domain>
cd ~/research/<domain>
git init && git add -A && git commit -m "bootstrap <domain> wiki"
```

Then edit `CLAUDE.md` at the root to add any domain-specific rules
(preferred notation, citation style, exclusions). That file is read by
Claude every time you work inside this directory.

## Page templates

See the `templates/` subdirectory for the five page types:

- `source.md` — Citation, key contributions, methodology, results, limitations
- `concept.md` — Definition, formal statement, properties, relationships
- `entity.md` — Person / algorithm / dataset with short bio and references
- `comparison.md` — What is compared, table, trade-offs, when-to-use
- `synthesis.md` — Thesis, evidence across sources, open questions, directions

All pages use YAML frontmatter with `title`, `type`, `created`, `updated`,
`sources`, `related`, `tags`. File names are `snake_case.md` (lowercase,
underscores, no spaces).

## Rules

- **Math uses LaTeX.** `$inline$` and `$$display$$`. Obsidian renders both.
- **Cross-links are mandatory.** When a page mentions a concept that has
  its own page, use `[[concept_name]]` — never prose-only.
- **Sources are cited.** Every factual claim in a concept page cites at
  least one source page.
- **Updates refresh frontmatter.** Whenever you edit a page, bump
  `updated: YYYY-MM-DD`.
- **Never modify `raw/`.** If the user wants to correct a typo in an
  extracted paper, that lives in `wiki/`, not `raw/`.
- **Commit after every operation.** One ingest = one commit, one lint pass
  with fixes = one commit.
