# Research Wiki — <DOMAIN>

This directory is a Karpathy-style LLM-compiled knowledge wiki for the
**<DOMAIN>** research area. Claude Code reads this file every time you work
inside this directory and uses it as the schema for all wiki operations.

---

## Layout

```
./
  CLAUDE.md          # this file — rules and workflows
  raw/               # immutable: original PDFs, HTML, notes
  wiki/              # LLM-maintained, browsable in Obsidian
    index.md         # table of contents — read FIRST
    log.md           # append-only operation log
    sources/         # one page per paper / document
    concepts/        # one page per concept
    entities/        # people, algorithms, datasets
    comparisons/     # head-to-head analyses
    synthesis/       # cross-source big-picture pages
```

**Key principle**: `raw/` is sacred. Never modify files under `raw/`. All
compilation, understanding, and cross-linking happens in `wiki/`.

This directory should be a standalone `git` repo. Every ingest / query
(that archives) / lint should be one commit.

---

## Three operations

### `ingest` — add a new source

Triggered by "ingest raw/<file>" or "add this paper".

1. Extract the content (for PDFs, use a dedicated extraction tool).
2. Read `wiki/index.md` first.
3. Structured analysis of the paper (task / challenge / insight / method /
   results / limitations).
4. **Discuss with the user** — ask what they want emphasized, what
   connections they see. Do not skip this step.
5. Create `wiki/sources/{firstauthor}_{year}_{slug}.md` from
   `<repo>/skills/research-wiki/templates/source.md`.
6. Update / create all relevant `concepts/`, `entities/`, `comparisons/`,
   `synthesis/` pages. Flag agreements and contradictions with existing
   pages explicitly.
7. Add bidirectional `[[wikilinks]]` everywhere.
8. Update `wiki/index.md` and append to `wiki/log.md`.
9. `git add -A && git commit -m "ingest: <source>"`

A single ingest typically touches 5–15 pages.

### `query` — answer a question

Triggered by any domain question asked inside this directory, or "query
the wiki about X".

1. Read `wiki/index.md`.
2. Read the relevant pages and their 1-hop neighbors.
3. Answer using only wiki content, citing pages as `[[wikilinks]]`.
4. Archive the answer as a new page **only if** it synthesizes 3+ sources,
   reveals a gap, or is likely to be asked again. Most queries do not
   archive.

### `lint` — audit the wiki

Triggered by "lint the wiki", "audit", "what's stale".

Checks: orphan pages, broken wikilinks, frontmatter drift, stub pages,
index staleness, duplicate concepts. Report; do not auto-fix.

---

## Page rules

- **Frontmatter**: every page has YAML frontmatter with `title`, `type`,
  `created`, `updated`, `sources`, `related`, `tags`. Bump `updated` on
  every edit.
- **File names**: `snake_case.md`. Lowercase. Underscores. No spaces, no
  punctuation except the leading path segment.
- **Math**: LaTeX. `$inline$` and `$$display$$`. Obsidian renders both.
- **Wikilinks**: mandatory when a concept has its own page. `[[page_name]]`,
  no `.md` suffix.
- **Sources cited**: every factual claim in a concept page links to at
  least one source page.
- **No hedging in wiki pages.** Wiki pages state what the sources say. If
  sources disagree, the page lists both positions — it does not equivocate.

---

## Domain-specific rules

<Add any rules specific to this domain here. Examples:>

- <Preferred notation (e.g. "use $Y(a)$ for potential outcomes, not $Y_a$")>
- <Citation style (e.g. "inline `[[author_year_keyword]]`")>
- <Excluded topics (e.g. "no applications outside observational studies")>
- <Seed concepts the wiki should eventually cover>

---

## On the first ingest

This wiki starts empty. On your first ingest:

1. `wiki/index.md` has only placeholder sections — fill them in as new
   pages get created.
2. `wiki/log.md` is empty — append the first entry after the first commit.
3. Don't worry about cross-linking density yet; it grows naturally as the
   wiki fills in.
