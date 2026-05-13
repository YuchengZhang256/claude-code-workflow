# Limits of proof-audit

The 4-phase debate audit (Claude pedantic / adversarial / generous personas + Codex cross-model + cross-critique + deterministic tier synthesis) catches a wide class of common probability/statistics proof gaps. It is **not complete**. The following classes of error are out of scope; do not promise the user that proof-audit will catch them.

## 1. Shared-base-model blind spots

Even with Claude + Codex cross-model, both sides are LLMs trained on overlapping corpora. Gaps that the **entire LLM training distribution** misses (e.g., subtle abuse of a specific concentration constant that no textbook calls out) will be missed by both, and the cross-check will silently agree. Lean / Coq formal verification is the only complete answer for this class; see Phase C in `modes/rate-chain/MODE.md` and the optional `--lean-verify` exit door in SKILL.md.

## 2. Implicit assumption inheritance across sections

A common pattern: Assumption A1 is defined in Section 2, used in Lemma 5 (Section 4) without re-statement. If the appendix is sliced for context-window reasons, the slice containing Lemma 5 may not contain A1, and Phase 2a/2b will flag a fake gap. Mitigation: Phase 1 collects all Assumption / Setup blocks into a global preamble that is prepended to every slice. **But**: when an assumption is declared mid-proof inline (not in an Assumption environment), this preamble approach silently misses it.

## 3. Citation correctness

If the paper cites "Davis–Kahan with constant √2", proof-audit assumes the citation is correct. It does not check:

- whether Davis–Kahan actually gives that constant (it depends on the variant — sin Θ vs the operator-norm bound)
- whether the cited paper actually proves what is claimed
- whether the cited constant has been superseded by a tighter result

This requires bibliography-level checking, currently out of scope.

## 4. Statement-vs-proof quantifier drift

Rate-chain mode (`modes/rate-chain/`) catches **exponent** drift between Theorem statement and proof body. The main proof-audit pipeline does **not** check `∀`/`∃` quantifier drift. If Theorem 3 says "for every ε > 0" but the proof body silently assumes ε > 1/n, neither pedantic nor adversarial persona is reliably going to spot it from claim-local view.

## 5. Numerical constant errors

The audit checks exponent-level rates (in rate-chain mode) and qualitative correctness. It does **not** check whether a constant like "C = 2.71828..." matches its computation; e-vs-π typos in numerical constants are below the resolution of this tool.

## 6. Author-introduced novel techniques

If the paper invents a new proof technique (e.g., a custom martingale coupling that the literature has not yet evaluated), proof-audit cannot tell whether the technique is correct. Both personas and Codex will at best say "I do not have prior knowledge of this construction; the local steps look formally consistent." This is not a verification — it is a "no immediate red flag" signal.

## 7. Off-by-truth (statement and proof both wrong, consistently)

If the paper's Theorem statement is wrong, and the proof body is wrong in exactly the same way, the pedantic persona will say "the proof formally entails the statement; verified." Rate-chain mode partially addresses this for exponents (it re-derives from the proof body) but the main pipeline does not.

## 8. Measurability / σ-algebra details at PhD-thesis depth

The Pedantic persona has measurability on its watchlist (gap_types 1–7 in `common_proof_gaps.md`), but LLMs are notoriously hand-wavy about measurability in product spaces, projective limits, and Polish-space pathologies. For thesis-level scrutiny on these classes, treat proof-audit's measurability findings as a **starting point**, not a verdict. Expect 30–50% false negative rate on subtle measurability.

## 9. Internal proof-body cross-references not via `\ref`

If a proof body refers to "the inequality above" or "by the previous display" without `\ref`/`\eqref`, the Phase A DAG discovery in rate-chain mode cannot trace the dependency, and the main pipeline cannot match the assumption to the use site.

## 10. PDF math semantics

`pdftotext -layout` mangles inline math, subscripts, and Greek letters. The main pipeline refuses scanned PDFs and **caps confidence at 0.6** for any finding extracted from a digital PDF (vs .tex source). If the user insists on PDF input, the report header includes a `pdf_extraction_warning` note.

---

## What we deliberately accept

- The 5-tier classification can put a real gap into Tier E (RESIDUAL) if both reviewers happen to confidently reject it with a wrong counter-argument. Human override path: read `RESIDUAL.md` after every audit; tier E is **not** silently discarded.
- Single-source findings (Tier C) are surfaced in the main report, not auto-dropped. The user decides.
- We trust the OpenAI structured-output schema to keep responses within `gap_type` enum. If a future codex-cli change relaxes this, the postflight script re-validates against the schema and drops non-conforming items.

## When to escalate beyond proof-audit

| Situation | Tool |
|---|---|
| End-to-end rate composition across 10+ lemmas | `proof-audit --rate-chain` |
| Need formal certificate (publishable as supplementary) | Lean 4 via `lean-lsp-mcp` (manual; out of skill scope) |
| Cross-model adversarial review of one claim | Run `/codex:adversarial-review` directly with focused prompt |
| Iterative close-the-gap loop (audit → patch → re-audit) | `/review-proof` skill |
