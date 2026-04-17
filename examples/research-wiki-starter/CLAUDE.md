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
    entities/        # people, algorithms, datasets, proof techniques, inequalities
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
9. **Update `wiki/synthesis/research_roadmap.md`** if you maintain one —
   does this source fill a gap, introduce a new tool, or reveal a new gap?
   See "Research roadmap" below.
10. `git add -A && git commit -m "ingest: <source>"`
11. **Synthesis prompt** — after the ingest is complete, ask the user a
    targeted comparison question naming 1–2 specific existing wiki pages
    and asking about a concrete relationship or difference. Example:
    "How does this paper's bound compare to the one in [[existing_page]] —
    stronger conditions, or a different regime?" If the answer reveals a
    comparison worth keeping, suggest creating a comparison page.

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

Checks:

1. **Contradictions** — claims that conflict across pages. Flag with
   `> **Contradiction**:` blockquotes on both pages.
2. **Stale content** — claims citing older sources when newer sources
   supersede them. Update, or annotate with `(superseded by [[newer]])`.
3. **Orphan pages** — pages with no incoming `[[wikilinks]]`.
4. **Phantom links** — `[[foo]]` where `wiki/**/foo.md` does not exist.
   Either create the page or fix the link.
5. **Missing concepts** — terms appearing in 3+ pages without their own
   concept page. Suggest creation.
6. **Missing cross-references** — semantically related pages that do not
   link to each other. Add `[[wikilinks]]` in both directions.
7. **Thin pages** — fewer than 3 sections or under ~200 words. Expand or
   merge.
8. **Synthesis gaps** — clusters of 3+ related pages sharing a theme but
   lacking a unifying comparison / synthesis page. Suggest creation.
9. **Mathematical spot-check** — for entity pages with subtype `inequality`
   or `proof_technique`, sample one theorem statement per page and cross-
   verify against its cited source: conditions, constants, asymptotic
   notation. Report discrepancies as `> **Math check**:` blockquotes.

Report grouped by category; do not auto-fix. Surface issues for the user
to decide.

---

## Page types and frontmatter

Every page has YAML frontmatter:

```yaml
---
title: "Page Title"
type: source | concept | entity | comparison | synthesis
subtype:             # entity pages only
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: []          # raw/ filenames or source page filenames this draws from
related: []          # related page filenames
tags: []
---
```

### Entity subtypes

Every entity page must declare a `subtype`:

- **`algorithm`** — computational procedures with inputs / outputs /
  complexity (e.g. spectral clustering, belief propagation, Louvain).
- **`math_object`** — mathematical structures, distributions, matrices
  (e.g. ε-net, sub-gaussian distribution, non-backtracking matrix).
- **`proof_technique`** — reusable proof strategies with templates and
  applicability conditions (e.g. Le Cam's two-point method, exponential
  tilting, Chernoff).
- **`inequality`** — named bounds, theorems, and identities with precise
  statements (e.g. Bernstein, Davis–Kahan, matrix concentration bounds).

Grouping entities by subtype in `wiki/index.md` keeps navigation sane as
the wiki grows.

---

## Page rules

- **Frontmatter**: bump `updated` on every edit.
- **File names**: `snake_case.md`. Lowercase. Underscores. No spaces, no
  punctuation except the leading path segment.
- **Math**: LaTeX. `$inline$` and `$$display$$`. Obsidian renders both.
- **Wikilinks**: mandatory when a concept has its own page.
  `[[page_name]]`, no `.md` suffix.
- **Sources cited**: every factual claim in a concept page links to at
  least one source page.
- **No hedging in wiki pages.** Wiki pages state what the sources say. If
  sources disagree, the page lists both positions — it does not equivocate.
- **Provenance-tag key claims.** After important statements (theorem
  results, rate bounds, algorithmic guarantees, cross-source connections),
  add inline attribution:
  - `(Author Year, Thm N.N)` for direct extraction from a single source.
  - `(cf. [[page_a]], [[page_b]])` for cross-source inference by the LLM.
  Not every sentence needs tagging — focus on claims a reader might want
  to verify or trace back.
- **Flag contradictions** explicitly: `> **Contradiction**: ...` blockquote
  on **both** pages involved.

---

## Tool integration

The skill is LLM-agnostic, but if the user has these tools the wiki
operations benefit from them. Choose whichever fits the environment:

| Task | Recommended tool | When |
|---|---|---|
| Extract PDF / image content | Dedicated extractor (`pdftotext`, `pdfplumber`, LLM-based extractor with long context) | Every `ingest` with a PDF or image source |
| Structured paper analysis | A `paper-reader` skill or the Task / Challenge / Insight / Flaw / Motivation framework | Every `ingest` of a research paper |
| Search for new sources | A `paper-lookup` skill (multi-database academic search) | When `lint` suggests gaps, or exploring a new subtopic |
| Systematic literature search | A `literature-review` skill | When building a new topic area from scratch |
| Write manuscripts from wiki | A `scientific-writing` skill | When drafting papers using wiki content |
| Rigorous review of synthesis | Multi-model pipeline (adversarial review + arbitration) | For important synthesis or comparison pages |

---

## Index scalability

`wiki/index.md` is the primary navigation aid. To keep it useful as the
wiki grows:

- **Group entities by subtype** (Algorithms, Math Objects, Proof
  Techniques, Inequalities) rather than a flat list.
- **Keep each entry to one line** — title + one-clause summary.
- **At ~100 pages**: consider adding a local search MCP (e.g. `qmd` with
  BM25 + vector) so the LLM can search without reading the full index.
- **At ~200 pages**: the index alone will not fit in context. Search
  becomes mandatory, and the index becomes a human-browsable TOC only.

---

## Research roadmap (optional but recommended)

If this wiki serves an active research project, maintain
`wiki/synthesis/research_roadmap.md` as a living document tracking how
wiki content serves your open problems. Each proof chain / experiment /
open question lists tools needed (covered vs. missing) and wiki pages
that supply them.

On every `ingest`, update the roadmap:

- Does this source fill a gap (❌ → ⚠️ → ✅)? Update the status column.
- Does it introduce a new tool the project could use? Add a row.
- Does it reveal a new gap? Add it to the Gaps section.
- Add a one-line entry to "What Each Source Gives This Project".

If the source has zero relevance, note that explicitly rather than
skipping silently — that negative evidence is itself useful.

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
