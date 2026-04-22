# Limits of rate-chain-audit

The skill performs **exponent-level** symbolic composition of a lemma chain in big-O / $\lesssim$ notation. This catches a specific, well-defined class of bugs. It does **not** constitute formal verification.

## What the skill catches reliably

- Big-O exponent mismatches between the composed chain and the stated top-level rate.
- Missing $\log$ / $K$ / $\lambda_{\min}$ / $\underline\mu$ factors on named branches of the composition.
- Dropped union bounds over $N$ or $M$.
- Main-paper / supplement duplicates diverging in their own rate statement.

## What the skill cannot catch, and why

### 1. Constant-level errors

Big-O hides constants. If lemma states $\le 3\sqrt{\log/\underline\mu}$ and proof yields $7\sqrt{\log/\underline\mu}$, the exponent dict is identical and the skill passes. Finite-sample guarantees fail silently.

### 2. Statement-vs-proof drift where both extractors are fooled

Phase B uses double-blind extraction (statement-only vs. proof-body). If the proof body has a latent error AND the statement reflects that error (the author made both consistent with the wrong answer), both extractors agree and the skill reports no disagreement. Skill sees internal coherence, misses external falsity.

### 3. A lemma that is logically wrong

The skill trusts each lemma's conclusion. If a lemma itself is wrong (invoked Bernstein under a hypothesis where Bernstein does not apply), the skill composes wrongly-justified rates consistently and reports no break. Only Lean/Coq-level proof verification fixes this.

### 4. Implicit assumption leakage

Lemma A holds under "bounded moments"; Lemma B uses A but needs sub-Gaussian for its own proof; author forgot to push sub-Gaussian upstream. Skill reads the stated hypotheses; both rates compose; nothing flags that B is actually unproved under its own listed hypotheses. `proof-audit`'s generous persona has a shot, but not guaranteed.

### 5. Novel proof-technique correctness

If the paper introduces a new resolvent expansion / leave-one-out decoupling / contour integral, the skill can verify the stated intermediate rates compose into the stated end rate. It cannot verify the new technique is valid.

### 6. Uniform off-by-truth

Stated rate and composed chain agree, but both disagree with the correct answer from first principles. Skill reports CONSISTENT. Requires a ground-truth oracle (Lean, or a second independent derivation).

### 7. Measurability / σ-algebra

Conditional independence arguments hinge on σ-algebra claims (e.g., "this quantity is measurable w.r.t. $\mathcal F_{-i}$"). The skill's big-O machinery says nothing about measurability.

### 8. Quantifier drift between prose and formula

Prose: "for all $m$, with high probability". Formula: only proves "for each fixed $m$, then take max". The max-over-$m$ step needs a union bound. Skill's extractor reads the formula and the stated "for all $m$" but does not audit whether the proof actually executed the union. `proof-audit` adversarial persona is the correct lens.

### 9. Proof-body cycles that do not go through `\ref`

DAG is built from `\ref` / `\eqref` / `\Cref` inside proof bodies. If Lemma A's proof uses B silently (copies B's argument without citing) and B's proof uses A, the skill misses the cycle. Pathological but possible.

### 10. Errors in external citations

Lemma proof says "by Davis-Kahan, $\|\sin\Theta\|\le\varepsilon/\gamma$". If Davis-Kahan is misquoted (wrong constant, wrong hypothesis version, different theorem by the same author), skill treats as atomic truth. External rate correctness is out of scope.

## How to use these limits

For high-stakes submissions:

- Run `rate-chain-audit` (this skill) → catches exponent-level bugs.
- Run `proof-audit` → catches local formal issues and assumption gaps.
- Run `rate-chain-audit-gpt` → redundant extraction via different model family.
- Final independent human read of Section 3-4 main-body theorems vs. appendix proofs for **1-6 above**.

The above five-stage gauntlet is what 2026 LLM tooling can reliably deliver. For category 1-6 complete coverage, Lean / Coq formalization is the only answer and has a cost 1-2 orders of magnitude higher.
