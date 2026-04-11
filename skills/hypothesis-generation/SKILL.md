---
name: hypothesis-generation
description: Structured hypothesis formulation from observations. Use when you have experimental observations or data and need to formulate testable hypotheses with predictions, propose mechanisms, and design experiments to test them. Follows scientific method framework. For open-ended ideation use scientific-brainstorming; for automated LLM-driven hypothesis testing on datasets use hypogenic.
allowed-tools: Read Write Edit Bash WebFetch
license: MIT license
metadata:
    skill-author: K-Dense Inc. (adapted)
---

# Scientific Hypothesis Generation

## Overview

Turn observations into a small set of competing, testable hypotheses with concrete predictions and experimental tests. The output is a plain markdown report — no LaTeX document templates, no figure pipeline. Math expressions inside the report still use LaTeX (`$...$` inline, `$$...$$` display) per the global CLAUDE.md math-formatting rule.

## When to Use This Skill

- Developing hypotheses from observations or preliminary data
- Designing experiments to test a scientific question
- Enumerating and comparing competing explanations for a phenomenon
- Formulating quantitative, falsifiable predictions
- Planning mechanistic studies across scientific domains

## PDF Reading Rule

If a phase requires reading a PDF:

- **Long or complex PDFs** (>20 pages, scanned, heavy math, dense figures) → use `cnai flash` for extraction.
- **Short simple PDFs** (≤20 pages, clean digital text) → use the `Read` tool directly.
- **Images** → always use `cnai flash`.

## Workflow — 8 Phases

### 1. Frame the Observation

- State the core observation or pattern in one sentence.
- Define scope: which systems, conditions, populations does it cover?
- Separate what is established from what is uncertain.
- Name the relevant scientific domain(s).

### 2. Generate Candidate Hypotheses

Produce 3–5 distinct hypotheses. Each must be **mechanistic** (explains how/why), not merely a restatement of the observation. Draw from:

- Known mechanisms in analogous systems
- Different levels of explanation (molecular, cellular, systemic, population)
- Challenged assumptions behind existing accounts
- Novel combinations of established mechanisms

Make hypotheses **mutually distinguishable** — if two make the same predictions everywhere, collapse them.

### 3. Specify Mechanisms

For each hypothesis, write the causal chain in plain language:

- What is the proximate cause?
- Through which intermediate steps?
- What does the final observable effect look like?

Draw a short cause → effect arrow chain. If you cannot, the "hypothesis" is still a description, not an explanation.

### 4. Derive Predictions

For each hypothesis, produce **specific, quantitative predictions**:

- Direction and (where possible) magnitude of effect
- Conditions under which the prediction should hold
- Predictions that **distinguish** this hypothesis from its competitors
- At least one prediction whose violation would falsify the hypothesis

### 5. Check Falsifiability

Apply this 6-item quality checklist to every hypothesis:

- **Testability** — can it be empirically tested with available methods?
- **Falsifiability** — what specific observation would disprove it?
- **Parsimony** — is it the simplest explanation that fits the evidence?
- **Explanatory power** — how much of the phenomenon does it cover?
- **Scope** — across which conditions does it apply?
- **Consistency** — does it align with established principles, or does it require abandoning well-supported theory? (If the latter, flag explicitly.)

Drop any hypothesis that fails testability or falsifiability. Note strengths and weaknesses for the rest.

### 6. Design Tests

For each surviving hypothesis, propose at least one concrete test. Pick from these five patterns:

1. **Randomized controlled trial** — assign treatment vs. control; best for causal identification when intervention is feasible and ethical.
2. **Natural experiment** — exploit exogenous variation (policy change, geographic discontinuity, instrument) when randomization is impossible.
3. **Observational study with controls** — cross-sectional or case-control with explicit confounder adjustment; weakest causal claims, note limitations.
4. **Simulation / computational model** — when parameters are known but analytical solution is intractable; useful for sanity-checking mechanism plausibility.
5. **Longitudinal panel** — repeated measures on the same units over time; best for dynamics, mediation, and ruling out reverse causation.

For each test specify: what is measured, the comparison or control, expected sample size or power, and the main confounds.

### 7. Self-Critique

Before presenting, stress-test the report:

- Are any two hypotheses actually the same under different names?
- Is there a plausible hypothesis you did not list?
- Which prediction is the cheapest discriminating test?
- What would a skeptical reviewer attack first?

### 8. Refine

Revise based on the critique. Merge duplicates, add missing candidates, sharpen the decisive prediction, and tighten the test design.

## Output — Markdown Report

Produce a plain markdown file with this structure. No HTML, no color boxes, no LaTeX document packaging — but math expressions inside the markdown still use LaTeX (`$...$` inline, `$$...$$` display) per the global CLAUDE.md rule.

```markdown
# Hypothesis Report — <topic>

## Observations
One paragraph stating the phenomenon, scope, and what is already known.

## Candidate Mechanisms
Bulleted cause → effect chains, one per hypothesis.

## Competing Hypotheses

| # | Hypothesis | Prediction | Falsifiability | Evidence status |
|---|------------|------------|----------------|-----------------|
| 1 | ...        | ...        | ...            | ...             |

## Proposed Tests
One subsection per hypothesis. For each: design pattern, measurements, controls, confounds, rough sample size.

## Decision Tree
If test A shows X, conclude Y; otherwise run test B. Make the discriminating logic explicit.

## Open Questions
What remains uncertain; what the next iteration should resolve.
```

Keep it under ~4 pages when rendered. If an appendix is genuinely needed (e.g., a long evidence summary), add it as a second markdown file, not inlined.

## Quality Standards

Every finished report must be:

- **Evidence-based** — claims grounded in cited literature
- **Testable** — every hypothesis carries a concrete, quantitative prediction
- **Mechanistic** — explains how and why, not just what
- **Comparative** — at least three competing hypotheses, explicitly contrasted
- **Rigorous** — each hypothesis has a designed test, not a vague "future work"

## Literature Search

When a phase requires background literature:

- Use `WebFetch` against the relevant source (PubMed landing pages, arXiv abstract pages, journal pages, open-access aggregators).
- If `WebFetch` returns a CAPTCHA, 403/429/503, empty body, or SPA stub, escalate via `bash ~/.claude/skills/web-access/scripts/fetch.sh "<URL>"` per the global web-fetching rule.

Start broad (landscape, reviews), then narrow to specific mechanisms and contradictory findings. Cite the evidence that discriminates between competing hypotheses — not the full corpus.
