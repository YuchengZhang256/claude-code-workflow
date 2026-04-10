# Case Study: Building a Causal-Inference Research Wiki

A concrete walkthrough of the first four weeks of building a
Karpathy-style research wiki from scratch, using the `research-wiki`
skill and the `examples/research-wiki-starter/` template. The specific
domain is causal inference, but the workflow is domain-agnostic — swap
"Pearl 2009" for any foundational text in your field.

## Week 0 — bootstrap

```bash
bash ~/.claude/skills/research-wiki/scripts/new-wiki.sh \
    ~/research/causal-inference "causal inference"
cd ~/research/causal-inference
```

The starter template creates:

```
causal-inference/
  CLAUDE.md        ← per-wiki schema (copy of the starter with <DOMAIN> replaced)
  raw/             ← empty, with a .gitkeep explaining the rule
  wiki/
    index.md       ← five empty section headers
    log.md         ← empty
```

Open `CLAUDE.md` and add domain-specific rules under the
"Domain-specific rules" section:

```markdown
- Use $Y(a)$ notation for potential outcomes, not $Y_a$.
- Prefer "ATE" over "average treatment effect" in page titles.
- Do not ingest applied papers unless they introduce a new method.
- Seed concepts to reach in month 1: potential outcomes, ATE, ATT,
  confounding, exchangeability, propensity score, IPW, g-formula,
  doubly robust, SCMs, do-calculus, front-door criterion.
```

Commit the bootstrap:

```bash
git add -A && git commit -m "bootstrap causal-inference wiki"
```

## Week 1 — first ingest (Pearl 2009)

Drop the PDF into `raw/`:

```bash
cp ~/Downloads/pearl_2009_causality.pdf raw/
```

Then ask Claude, inside the wiki directory:

> ingest raw/pearl_2009_causality.pdf

Claude's flow:

1. Reads `CLAUDE.md` (loaded automatically when entering the directory).
2. Extracts the PDF via a dedicated extractor (pdftotext, pdfplumber, or
   an LLM-based tool — configurable).
3. Reads `wiki/index.md`, sees it's empty, notes this is the first ingest.
4. Runs structured analysis. Returns a 6-section summary: task,
   challenge, insight, method, results, limitations.
5. **Asks the user** what to emphasize. I said: "foundational SCM text,
   do-calculus is the novel piece, potential outcomes chapter is
   included but treated as a separate framework".
6. Creates:
   - `wiki/sources/pearl_2009_causality.md`
   - Concept pages: `wiki/concepts/structural_causal_model.md`,
     `confounding.md`, `do_operator.md`, `backdoor_criterion.md`,
     `frontdoor_criterion.md`, `do_calculus.md`, `potential_outcomes.md`
   - Entity: `wiki/entities/judea_pearl.md`
7. All pages cross-linked via `[[wikilinks]]`.
8. Updates `wiki/index.md` with the new entries.
9. Appends to `wiki/log.md`:
   ```
   2026-03-05 | ingest | pearl_2009_causality.pdf | +1 source, +7 concepts, +1 entity
   ```
10. `git commit -m "ingest: Pearl 2009 Causality"`.

**Stats from this ingest**: 10 new files, ~3000 words of compiled
content. Most of the content is in the source page and the three headline
concepts (SCM, do-operator, do-calculus); the other concepts start as
short stubs that will be expanded later.

## Week 2 — second ingest (Hernan & Robins 2020)

```bash
cp ~/Downloads/hernan_robins_2020_what_if.pdf raw/
```

> ingest raw/hernan_robins_2020_what_if.pdf

This is where the compounding effect shows up. The second paper uses the
potential-outcomes framing instead of SCM, and it covers ground Pearl
didn't: g-methods, inverse probability weighting, marginal structural
models, target trial emulation.

What happened:

**New pages** (9):
- Source: `wiki/sources/hernan_robins_2020_what_if.md`
- Concepts: `inverse_probability_weighting.md`, `g_formula.md`,
  `g_estimation.md`, `marginal_structural_model.md`,
  `propensity_score.md`, `doubly_robust.md`, `target_trial.md`
- Entities: `miguel_hernan.md`, `james_robins.md`

**Updated pages** (8): Pearl had already introduced the basic concepts
under SCM framing. Hernan-Robins treats them under potential outcomes.
Each existing page got:

- A second section header: "Treatment in Hernan & Robins (2020)"
- The potential-outcomes formulation next to the SCM one
- Cross-links to `[[potential_outcomes_vs_scm]]` (new comparison page)
- An "Agreements / Contradictions" note — in this case, full agreement
  on the substance, just different notation

**New comparison page**:
`wiki/comparisons/potential_outcomes_vs_scm.md` — a head-to-head table
of the two formalisms, with Pearl's chapter 7 and Hernan-Robins chapters
1–3 as the two sources.

**log.md entry**:
```
2026-03-12 | ingest | hernan_robins_2020_what_if.pdf | +1 source, +7 concepts, +2 entities, +1 comparison, 8 pages updated
```

**Total page count after week 2**: 20 pages. Most of the value came from
the updates to existing pages, not the new pages.

## Week 3 — first query

I needed to write an email comparing IPW and g-formula for a
methodological question. Inside the wiki directory:

> which of IPW vs g-formula is more efficient asymptotically, and under
> what conditions is one preferred?

Claude's flow:

1. Reads `wiki/index.md`, finds `[[inverse_probability_weighting]]`,
   `[[g_formula]]`, and flags that a comparison page might be useful.
2. Reads those two concept pages and the Hernan-Robins source page.
3. Synthesizes an answer: under correct model specification they are
   both consistent; efficiency depends on the variance of the relevant
   quantities; IPW is more sensitive to positivity violations; g-formula
   requires a correct outcome model; doubly robust estimators combine
   both.
4. Decides: this answer synthesizes 3 existing pages, addresses a
   concrete efficiency question, and is likely to be needed again. It
   qualifies for archiving.
5. Creates `wiki/comparisons/ipw_vs_g_formula.md` from the comparison
   template, populates the table, cites the two source pages.
6. Updates `wiki/index.md` and appends to `wiki/log.md`.
7. `git commit -m "query→comparison: ipw vs g-formula"`.

Later queries — most of them — will **not** produce a new page. Only the
ones that synthesize, reveal gaps, or are likely to be re-asked.

## Week 4 — first lint pass

> lint the wiki

Claude walked the audit checklist:

**Orphans** (0): every concept page has at least one incoming wikilink
from a source page. Good.

**Broken wikilinks** (2): I had referenced `[[randomized_trial]]` in
two places but never created the page. Claude flagged both. I asked it
to stub the page from the Pearl + Hernan-Robins treatment, which it did.

**Frontmatter drift** (3): three concept pages had `updated:` dates
older than the Hernan-Robins ingest even though that ingest had modified
them. Claude bumped the dates.

**Stub pages** (1): `wiki/concepts/frontdoor_criterion.md` was <100
words — Pearl introduces it briefly and Hernan-Robins doesn't discuss it
at all. I decided to leave it as a stub until I ingest a paper that
actually exercises the front-door criterion.

**Duplicate concepts** (1): Claude flagged `propensity_score.md` and
`propensity_matching.md` as possibly duplicative. I looked at both and
confirmed they are distinct (the score is a quantity; matching is a
downstream estimation technique that uses the score). I asked Claude to
cross-link them more clearly instead of merging.

**Index staleness** (0): all good.

Lint commit:
```
git commit -m "lint: stub randomized_trial, refresh frontmatter, crosslink propensity pages"
```

## What the wiki looks like after a month

```
~/research/causal-inference/
  raw/                  (2 PDFs)
  wiki/
    index.md            (complete TOC, ~60 entries)
    log.md              (5 operations)
    sources/            (2 pages)
    concepts/           (15 pages)
    entities/           (3 pages)
    comparisons/        (2 pages)
    synthesis/          (0 pages — too early)
```

**Total commits**: 6 (bootstrap + 2 ingests + 1 query-archive + 1 lint +
1 manual edit).

**Observation**: the second ingest was much more valuable than the first,
because the first one had nothing to link into. By the fifth ingest, a
single ingest typically touches 15+ existing pages.

## When to create a `synthesis/` page

I haven't created one yet because two sources isn't enough synthesis.
Synthesis pages are for cross-source big-picture claims — things like
"the field of community detection has evolved through three phases
between 2002 and 2018" or "IPW and g-formula are really the same
estimator viewed through different decompositions under a correct
outcome model". You need ≥3 sources and a real observation about the
field, not just per-source notes.

## Lessons from month 1

1. **The "discuss with user" step on ingest is load-bearing.** If I
   skipped it, the wiki would be generic summaries instead of my
   understanding of the papers. The wiki value compounds because it
   encodes your perspective, not the paper's.
2. **Most queries don't deserve a new page.** I have asked ~20 questions
   against the wiki; only 2 became archived pages. Resist the urge to
   over-document.
3. **Lint catches real issues.** The broken wikilinks I had would have
   compounded into more broken wikilinks if I hadn't caught them week 4.
   Run lint after every 3–5 ingests.
4. **Obsidian is the right browser.** I tried reading the wiki directly
   in VS Code for the first week — unpleasant. Pointing Obsidian at the
   wiki root and opening the graph view is where the value lives.
5. **Per-wiki `CLAUDE.md` > global `CLAUDE.md`.** Domain-specific rules
   (notation conventions, citation style) go in the per-wiki file. The
   global `~/.claude/CLAUDE.md` should only have cross-cutting rules.
