---
name: literature-review
description: Conduct comprehensive, systematic literature reviews following PRISMA methodology. Use when the user asks for a systematic review, meta-analysis, scoping review, research synthesis, or the literature-review section of a paper/thesis. Produces a structured Markdown document with documented search strategy, PRISMA flow counts, thematic synthesis, quality assessment, and verified citations.
allowed-tools: Read Write Edit Bash Grep Glob WebFetch
license: MIT
---

# Literature Review

## Overview

Conduct a systematic literature review following rigorous academic methodology: define a focused question, search multiple databases with a documented strategy, screen results against explicit criteria, extract and quality-assess each included study, synthesize findings thematically, and verify every citation before finalizing the document.

This skill is self-contained. It does not depend on any other skill, script, or external helper — everything runs out of `Read`, `Write`, `Edit`, `Bash`, `Grep`, `WebFetch`, and the user's own browser/API access.

## When to Use This Skill

Activate when the user asks for any of:

- A systematic review, scoping review, or narrative review of a topic
- A meta-analysis literature-collection phase
- The "Related Work" or "Literature Review" section of a paper, thesis, or grant
- A state-of-the-art survey of a research area
- An audit of research gaps and future directions
- A reproducible, citation-verified synthesis of multiple studies

Do NOT use this skill for:
- Reading / critiquing a single paper (use a paper-reader workflow)
- Searching for one specific reference (a direct database query is enough)
- Brainstorming ideas without synthesis of existing work

## Phase-Gated Workflow

Work through the phases in order. Each phase has an explicit **Exit gate** — do not advance until the gate is satisfied. This mirrors PRISMA's recommended flow and prevents the most common failure mode of "writing before searching."

### Phase 1 — Planning and Scoping

1. **Formulate the question.** For clinical / biomedical topics use PICO (Population, Intervention, Comparison, Outcome). For methods / CS / stats topics use a simpler "concept × method × context" frame.
   - Example (PICO): "In adults with sickle cell disease (P), does CRISPR-Cas9 gene editing (I) compared with standard hydroxyurea therapy (C) reduce vaso-occlusive crises (O)?"
   - Example (non-clinical): "How are community detection methods evaluated on temporal networks (concept × method × context)?"

2. **Choose review type.** Narrative, scoping, systematic, or meta-analytic. Systematic and meta-analytic reviews require strict PRISMA adherence; narrative reviews may relax documentation but should still record search steps.

3. **Set inclusion / exclusion criteria** BEFORE searching. At minimum:
   - Date range (e.g., 2015-01-01 to today)
   - Language (usually English)
   - Publication type (peer-reviewed journal, conference, preprint, thesis)
   - Study design (RCT, observational, simulation, theoretical)
   - Any domain-specific constraints

4. **Pick 2–4 concept blocks.** For each block, list synonyms, acronyms, and spelling variants. These become the OR-groups of your Boolean query.

**Exit gate:** A written protocol file exists containing the question, review type, criteria, concept blocks, and synonym lists. Do not start searching without it.

### Phase 2 — Systematic Literature Search

The goal of this phase is a single deduplicated list of candidate records, each with title, authors, year, venue, DOI (if available), and abstract.

1. **Pick at least 3 complementary databases.** A good default mix:
   - One broad index: Semantic Scholar, OpenAlex, or Google Scholar
   - One domain index: PubMed (biomed), arXiv (physics/math/CS/stat), IEEE Xplore (engineering), ACM DL (computing), EconLit (economics)
   - One preprint server: bioRxiv, medRxiv, arXiv, SSRN

2. **Construct the Boolean query.** Combine concept blocks with `AND`, and synonyms within a block with `OR`. Anchor terms to title / abstract fields when the database supports it to cut noise. Thematic tips:
   - **PubMed:** prefer MeSH terms (`"sickle cell disease"[MeSH]`) plus `[Title/Abstract]` for newer concepts MeSH has not caught up with.
   - **arXiv:** use full-text search; restrict by category (`cat:stat.ME`) rather than field tags.
   - **Semantic Scholar / OpenAlex:** use their REST APIs for reproducible dumps; both return JSON with citation counts.
   - **Google Scholar:** no stable API; treat it as a supplementary check, not a primary source, because results are not reproducible.

3. **Run each query and save raw results.** Export each database's hits to its own file (`results_pubmed.json`, `results_arxiv.json`, …). Record for every database:
   - Date searched
   - Exact query string
   - Number of records returned

4. **Deduplicate manually.** Merge files into a single list, then dedupe in this order:
   1. By DOI (lowercase, stripped of `https://doi.org/` prefix) — fastest and most reliable
   2. By (normalized title, first-author surname, year) for records missing a DOI
   A short Bash one-liner or a few lines of Python (`json.load` → `dict` keyed by DOI) is sufficient. Record how many duplicates you removed.

**Exit gate:** A single merged file of unique records exists, and you can state the per-database counts plus total unique records.

### Phase 3 — Screening and Selection (PRISMA Flow)

Screen in three passes. Record counts at every step so you can draw a PRISMA diagram.

1. **Title screen.** Exclude obvious non-matches (wrong species, wrong domain, off-topic). Be generous — keep anything plausible.
2. **Abstract screen.** Apply the full inclusion / exclusion criteria. For each excluded record, record a reason code (e.g., `E1 = wrong population`, `E2 = no outcome of interest`).
3. **Full-text screen.** Obtain PDFs for the survivors.
   - **PDF reading rule:** For long or complex PDFs (>20 pages, scanned, math-heavy, figure-dense), use `cnai flash` to extract the text before reading. For short, simple, text-based PDFs (≤20 pages), use `Read` directly. Always use `cnai flash` for images. When unsure, prefer `cnai flash` — the cost of a wrong flash call is small; the cost of blowing context is larger.
   - Apply the criteria strictly and again record exclusion reasons.

Record the counts in this PRISMA-style block and paste it into the review:

```
Identified (all databases):        n = ___
After deduplication:               n = ___
After title screen:                n = ___
After abstract screen:             n = ___
After full-text screen (INCLUDED): n = ___
```

**Exit gate:** You have a concrete list of included studies and a filled-in PRISMA count block.

### Phase 4 — Data Extraction and Quality Assessment

Build a simple extraction table (Markdown or CSV) with one row per included study. Suggested columns:

| Col | Content |
|---|---|
| Citation | First author, year, DOI |
| Design | RCT / cohort / simulation / theoretical / … |
| Sample / setting | n, population, dataset |
| Method | Intervention, model, or technique |
| Key findings | Numerical results where possible |
| Limitations | Author-reported + your own notes |
| Quality | See below |

**Quality appraisal** — pick the appropriate tool:
- RCTs → Cochrane RoB 2
- Observational studies → Newcastle–Ottawa Scale
- Systematic reviews → AMSTAR 2
- Simulation / methods papers → custom checklist (reproducibility, code availability, benchmarks)

Rate each study **High / Moderate / Low / Very Low**. Flag (but do not necessarily exclude) Very Low studies.

**Exit gate:** Extraction table is complete for every included study and each row has a quality rating.

### Phase 5 — Thematic Synthesis

Write the Results section by **theme**, not by study. A study-by-study recap is the single most common failure mode of bad reviews.

1. Read the extraction table and cluster studies into 3–5 themes.
2. For each theme, write 1–3 paragraphs that:
   - State the consensus finding (if any), with supporting citations
   - Surface disagreements and likely reasons (method differences, populations, eras)
   - Weight claims by study quality — a Very Low study and a Landmark study do not carry equal evidence
   - Cite effect sizes / numerical results, not just "study X found that…"

Example phrasing:

> Viral vectors were the dominant delivery route in early work, with AAV-based approaches reporting 65–85% transduction efficiency across 15 studies [1–15] but repeatedly raising immunogenicity concerns [3, 7, 12]. Lipid-nanoparticle methods, introduced later, showed lower efficiency (40–60%) but a cleaner safety profile [16–23].

Follow the Results with a Discussion that interprets the synthesis, names the gaps you found, and proposes follow-up work.

**Exit gate:** A draft Markdown document with all thematic sections written and every claim supported by at least one citation from the extraction table.

### Phase 6 — Citation Verification

Every DOI in the final document should resolve and match the claimed metadata. This is done manually — spot-check is fine for narrative reviews, but systematic reviews should verify all.

1. Extract every DOI from the draft with `Grep` (`10\.\d{4,}/[^\s)\]]+`).
2. For each DOI (or a random sample of 5–10 for spot-checks), query the CrossRef REST API:

   ```bash
   curl -s "https://api.crossref.org/works/<DOI>" | jq '.message | {title, author, container: ."container-title", issued}'
   ```

3. Compare the returned title, first author, year, and venue against what the draft claims. Fix mismatches in place.
4. For arXiv-only references without a DOI, use the arXiv API instead: `https://export.arxiv.org/api/query?id_list=<arxiv_id>`.

Pick **one** citation style and apply it consistently. Quick references:

- **APA 7:** `(Smith et al., 2023)` → `Smith, J. D., Johnson, M. L., & Williams, K. R. (2023). Title. Journal, 22(4), 301–318. https://doi.org/10.xxx/yyy`
- **Nature:** superscript numerals → `Smith, J. D., Johnson, M. L. & Williams, K. R. Title. Nat. Rev. Drug Discov. 22, 301–318 (2023).`
- **Vancouver:** superscript numerals → `Smith JD, Johnson ML, Williams KR. Title. Nat Rev Drug Discov. 2023;22(4):301-18.`

**Exit gate:** Every verified DOI matches CrossRef metadata, and the reference list uses one consistent style.

### Phase 7 — Final Document and Delivery

The primary deliverable is the Markdown review document. A PDF is optional and the user should not be blocked if PDF tooling is missing.

- **Markdown is the canonical format.** Keep the `.md` file as the source of truth.
- **If the user asks for a PDF**, two common options:
  - `pandoc review.md -o review.pdf --citeproc` — requires `pandoc` and a LaTeX engine (`xelatex`). Check with `pandoc --version` and `which xelatex`. Install via `brew install pandoc` and `brew install --cask mactex` on macOS.
  - A Markdown preview export (VS Code, Obsidian, Typora) — no extra tooling, good enough for informal deliverables.
- **Do not prescribe PDF generation** if the user did not ask for it.

Run this final checklist before handing the document over:

- [ ] Research question stated up front
- [ ] Inclusion / exclusion criteria explicit
- [ ] Search strategy documented per database (query, date, count)
- [ ] PRISMA flow counts filled in
- [ ] Every included study appears in the extraction table with a quality rating
- [ ] Results organized by theme, not by study
- [ ] Discussion names at least one concrete research gap
- [ ] Every DOI verified (or spot-check documented) against CrossRef
- [ ] One citation style used consistently throughout
- [ ] Limitations of the review itself acknowledged

## Template

Start every review from `assets/review_template.md` in this skill's directory. It contains the section skeleton, a PRISMA block, and extraction-table headers. Copy it into the user's working directory and fill it in as you progress through the phases:

```bash
cp "$CLAUDE_SKILL_DIR/assets/review_template.md" ./my_review.md
```

(If `$CLAUDE_SKILL_DIR` is not set, use the absolute path to the skill's `assets/review_template.md`.)

## Prioritizing High-Impact Papers

Quality beats quantity. When screening and synthesizing, bias toward influential papers — readers trust reviews that lean on seminal work.

Rough citation thresholds (always compare within the same field; CS and biomed scale very differently):

| Paper age | "Notable" | "Landmark" |
|---|---|---|
| 0–3 years | 20+ citations | 100+ |
| 3–7 years | 100+ | 500+ |
| 7+ years | 500+ | 1000+ |

Prefer papers from top-tier venues (Nature / Science / Cell / NEJM / Lancet / JAMA / PNAS for biomed; NeurIPS / ICML / ICLR / JMLR / Annals of Statistics / JRSS-B for stats+ML) when available, and give weight to authors with a track record in the specific subfield.

This is a bias, not a filter. Do not exclude a paper just because its venue is obscure — especially for new methods or niche topics where the best work may live on arXiv.

## Common Pitfalls

1. **Searching one database only.** Always use at least three.
2. **Forgetting to record counts.** Without PRISMA counts the review is not reproducible.
3. **Summarizing study-by-study** instead of synthesizing by theme.
4. **Skipping quality appraisal** and treating all evidence equally.
5. **Unverified DOIs.** A wrong citation is worse than no citation.
6. **No preprints.** Missing bioRxiv / arXiv misses the last 12–18 months of work in fast-moving fields.
7. **Too-broad query** → thousands of hits, most off-topic. Narrow with field tags and concept blocks.
8. **Too-narrow query** → misses synonyms. Always brainstorm alternate terms.
9. **Writing before searching.** If you already know the conclusions you expect, the search will confirm them. Do Phase 1 and the gate before touching the draft.
10. **Stale search.** Record the search date and re-run before submission if more than a few months have passed.

## External Resources

- PRISMA statement and flow diagram: http://www.prisma-statement.org/
- Cochrane Handbook: https://training.cochrane.org/handbook
- AMSTAR 2: https://amstar.ca/
- MeSH browser: https://meshb.nlm.nih.gov/search
- CrossRef REST API: https://api.crossref.org/swagger-ui/index.html
- OpenAlex API: https://docs.openalex.org/
- arXiv API: https://info.arxiv.org/help/api/index.html

## Summary

A literature review produced with this skill is systematic (documented search), transparent (PRISMA counts and exclusion reasons), thematic (synthesized, not listed), quality-weighted (appraisal table), and verifiable (checked DOIs). The workflow is phase-gated — each phase must satisfy its exit gate before you move on — because the hardest part of a review is resisting the urge to write before you have read.
