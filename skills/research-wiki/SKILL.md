---
name: research-wiki
description: "In an existing research wiki, ingest papers, answer wiki queries, or lint compiled Markdown pages."
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

Each wiki can be an independent `git` repo. Use commits when the user asks or when the project convention requires it; do not auto-commit silently.

A new wiki is bootstrapped via `scripts/new-wiki.sh` (see "Creating a new wiki" below); the per-wiki schema lives at `templates/per_wiki_CLAUDE.md`.

## The three operations

### 1. Ingest — compile a new source into the wiki

**Trigger**: "ingest `raw/pearl_2009.pdf`", "add this paper to the wiki".

**Flow**:

1. **Read the source.** For PDFs, use `pdftotext` (preferred) or `ocrmypdf`
   for scanned ones — do not rely on `WebFetch` or inline `Read` on a large
   scientific PDF. If both fail, report the blocker.
2. **Read `wiki/index.md` first** to see what concepts already exist. Every
   subsequent decision depends on this.
3. **Structured analysis via `paper-reader`.** When the source is a research
   paper, dispatch the `paper-reader` skill (Task / Challenge / Insight /
   Flaw / Motivation framework) — do not re-implement the framework inline.
   For non-paper sources (textbook chapter, technical note), produce the same
   five-axis analysis directly.
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
11. **Offer a commit.** If the user wants versioned wiki operations, commit with `git add -A && git commit -m "ingest: {source title}"`; otherwise leave the changes uncommitted.

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

**Quick lint** (deterministic, ~2 sec across a 100-page wiki):

```bash
python3 ~/.claude/skills/research-wiki/scripts/lint.py <wiki-dir>
```

The script runs six mechanical checks and prints a grouped stdout report:

- **Orphan pages**: no incoming `[[wikilinks]]` from elsewhere (excluding
  `index`, `log`, and pages under `synthesis/`)
- **Broken wikilinks**: `[[foo]]` where `wiki/**/foo.md` does not exist
- **Stub pages**: under ~150 words
- **Frontmatter drift**: missing required fields (`title`, `type`, `created`,
  `updated`)
- **Source-less concepts**: concept pages whose `sources:` frontmatter is
  empty (signals "pre-seeded scaffolding never grounded in a real source")
- **Untagged pages**: pages with empty or missing `tags:` (escapes
  tag-based search; common with bulk-ingested early pages)

**Full audit** (LLM-driven, only on request — these need judgment):

- Contradictions across related pages
- Stale claims superseded by newer sources
- Missing cross-references between semantically related pages
- Duplicate concepts under different names
- Math spot-checks for `inequality` / `proof_technique` entities

Do **not** auto-fix orphan / merge / dedup issues — surface them for the
user to decide.

**Tag canonicalization** (read-only analysis, run when singleton tag count
gets high):

```bash
python3 ~/.claude/skills/research-wiki/scripts/tag_canon.py <wiki-dir> > tag_canon_report.md
```

Produces a markdown report grouping rare tags (used ≤3 times) by their
likely canonical merge target from the top-tag pool (used ≥5 times).
Matching is purely syntactic (substring + token-overlap, no semantic
similarity) so false positives are easy to spot in review. The script
NEVER modifies pages — apply selected merges by hand or via Claude with
explicit instructions. Recommended trigger: when `len(unique_tags) > 3 ×
len(pages)` or singleton ratio exceeds ~50%.

## Creating a new wiki

```bash
~/.claude/skills/research-wiki/scripts/new-wiki.sh ~/research/<domain> "<domain>"
```

The script assembles the wiki layout entirely from this skill's
`templates/per_wiki_CLAUDE.md` plus inline minimal seeds for `index.md` /
`log.md`. It refuses to overwrite an existing target. After bootstrap:

1. Drop source PDFs / notes into `~/research/<domain>/raw/`.
2. Edit the "Domain-Specific Notes" section of the new `CLAUDE.md` as
   conventions emerge (preferred notation, citation style, exclusions).
3. Tell Claude `"ingest raw/<file>"` to compile the first source.

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
- **Do not auto-commit.** Offer one commit per ingest or lint pass when useful, but only run `git commit` when the user explicitly wants it.
