# Phase 2 — Multi-source debate audit

This document specifies the **new** Phase 2 design that replaces the old "3 persona ensemble + magic-confidence merge" approach. The change addresses three issues identified in the audit of the previous design:

1. **Shared base model = correlated errors**. Three Claude personas do not give independent evidence; their errors are not statistically independent. The new design adds a Codex cross-model side.
2. **`-0.3` magic number and `max(confidence)` in merge**. The new design replaces all magic numbers with a **deterministic 5-tier classification** based on which sides surfaced and survived critique.
3. **Persona briefs were negative-only** (`feedback_subagent_negative_constraints`). The new briefs include explicit "positive companion" clauses.

---

## Files produced by Phase 2

```
<cwd>/proof_audit/
├── claims.json                          # from Phase 1
├── claim_packages/                      # NEW (Phase β.1) — pre-sliced per-claim windows
│   ├── _manifest.json
│   ├── C1.json
│   └── ...
├── prior_round_state.json               # NEW (Phase α) — required input for rounds ≥ 2
├── findings_claude_pedantic.json        # 2a
├── findings_claude_adversarial.json     # 2a
├── findings_claude_generous.json        # 2a
├── findings_codex.json                  # 2b
├── critiques_claude_on_codex.json       # 2c-i
├── critiques_codex_on_claude.json       # 2c-ii
├── synthesized.json                     # 2d (decision-tiered)
└── RESIDUAL.md                          # 2d (rejected items, human readable)
```

All `findings_*.json` validate against `schema/gap.schema.json`. All `critiques_*.json` validate against `schema/critique.schema.json`.

---

## Manuscript access protocol (mandatory preamble for ALL persona prompts)

**Every persona prompt — Pedantic, Adversarial, Generous, codex cross-model — MUST begin with this access protocol.** It eliminates the "subagent dies after 9-15 Read calls on a 4000-line tex" failure mode (observed 4/4 in osaa case study).

> **How to read the manuscript.** Do NOT open the full `.tex` file. For each claim in `claims.json`, the per-claim window has been pre-sliced into `proof_audit/claim_packages/{claim_id}.json`. That file contains `statement_text`, `proof_text`, `context_before_text`, `context_after_text`, `hypertargets[]`, `section_header`, and `depends_on[]`. **Read that one file** for each claim you audit (typical size ≈150 lines). Only fall back to the full `.tex` if the package's `warnings[]` field reports a stale anchor.
>
> **How to use prior context (rounds ≥ 2).** Before flagging any finding, check `proof_audit/prior_round_state.json`. Each entry there has been raised in a previous round; many include a `package_path` that resolves to the same package files above. If you would re-flag the same `(claim_label, gap_type)` pair, you MUST (a) acknowledge the prior fix attempts in your `reasoning` field, (b) explain why the prior fix is insufficient with a concrete pointer (line, equation, missing condition), and (c) propose a CONCRETELY DIFFERENT approach — not a re-phrasing. If you cannot satisfy (b) and (c), DO NOT re-flag.
>
> **Cross-claim references.** When a claim's `depends_on[]` lists another claim id, you may also `Read proof_audit/claim_packages/{dep_id}.json` to consult the dependency's statement.

This block belongs verbatim above each persona's role-specific brief in the prompt body.

---

## Phase 2a — Three Claude personas (local)

Same three personas as before, **but with corrected briefs**. Run in main thread when `len(claims) < 5` or `appendix_tokens < 10k`; otherwise dispatch three parallel `Agent` subagents.

**Important**: prepend the *Manuscript access protocol* (above) to every persona prompt before the role-specific brief. Without it, subagents will try to Read the full .tex and will hit the socket-fail loop after 9-15 calls.

### Pedantic brief (corrected)

> You are a strict probability-theory professor. Focus on formal correctness: symbol reuse, undeclared notation, σ-algebra / measurability gaps, missing regularity (continuity, differentiability, boundedness) before use, typos, dimension mismatches. **However**, baseline rigor still applies: do not flag an assumption that the paper has clearly stated earlier in the Setup or Assumption block — you must read those sections too. Do not flag well-known textbook results (e.g. Slutsky) as "unjustified" simply because no citation is given. For each claim emit findings in the required JSON shape; if no issue, emit one finding with `status="verified"`, `gap_type="none"`, `severity=0`.

### Adversarial brief (corrected)

> You are a hostile reviewer trying to collapse the proof. Construct counterexamples, extreme regimes, degenerate inputs, limit boundaries. Typical attack points: `n → ∞` vs `d → ∞` order, degenerate distributions (constant, point mass, heavy tail), trivial cases (`n=1`, empty set, zero variance), implicit independence, concentration constants that blow up with dimension. **However**, your counterexamples must lie inside the regime the paper actually claims to address. Do not invent counterexamples in the `n=0` or empty-support case if the paper restricts to `n ≥ 2` and non-degenerate distributions. Each successful attack is one finding with `gap_type="counterexample-..."` or the most specific enum value; `latex_patch` should state the condition that must be added to the Assumption block.

### Generous brief (corrected)

> You are a sympathetic colleague who wants to repair the proof. For each apparent gap, give the **minimum sufficient regularity** that would make it correct, instead of rejecting outright. **However**, "minimum sufficient" must not collapse to "minimum vacuous": if the paper's main result depends on a strong condition (e.g., sub-Gaussian moments), do not propose a weaker condition (finite second moment) that would break later steps. Emit `status="missing_assumption"` with a `latex_patch` listing: (i) the condition that should be added; (ii) a 1-sentence argument why it is minimal.

### Persona output

Each persona produces **one** JSON file conforming to `schema/gap.schema.json`. One persona may emit **multiple findings per claim** if multiple distinct issues exist. `claim_audit_count` must equal `len(claims)`.

### Adversarial routing (Phase γ.1)

The Adversarial brief was the most failure-prone in the osaa case study (4/4 socket-fails after 9-15 Read calls). Phase β.1's claim packaging removed the *cause* (large-tex Read loops), but the brief itself remains the most expensive — for every claim it must construct an attack, which scales worst.

Routing rule:

| Condition | Route |
|---|---|
| `claim_packages/` exist AND no prior socket-fail this session | **Route A**: Claude subagent (default) |
| Route A produced ≥2 socket errors / timeout retries on a single round | **Route B**: dispatch Adversarial brief to a SECOND `codex exec` invocation (`codex.adversarial`), in addition to the existing `codex.neutral` (Phase 2b) |

Both routes use the identical brief; only the dispatch differs. See `persona_prompt_skeleton.md` for the codex-adversarial prompt template.

When Route B is used, Phase 2c critique pairs become **Claude critiques (codex.neutral ∪ codex.adversarial)** and **codex critiques (Pedantic ∪ Generous)**. The synthesis tier table (below) treats `codex.neutral` and `codex.adversarial` as two independent codex sources — agreement between them counts the same as agreement between two Claude personas.

---

## Phase 2b — Codex cross-model (one persona, true cross-model)

Run **after** Phase 2a in main thread:

```bash
codex exec \
  --skip-git-repo-check \
  --sandbox read-only \
  --output-schema ~/.claude/skills/proof-audit/schema/gap.schema.json \
  --output-last-message proof_audit/findings_codex.json \
  -m gpt-5.5 \
  -c model_reasoning_effort=xhigh \
  < phase2b_prompt.txt
```

Prompt content (`phase2b_prompt.txt`):

> You are an independent cross-model reviewer (persona = `codex-cross-model`). You will see the full claim list (Phase 1 output) and the appendix text. You will **not** see what the three Claude personas concluded — your job is to produce an independent audit. For each claim emit one or more findings; choose `gap_type` from the enum; use `status="verified"` only when actively checked.
>
> Inputs (attached): `<claims.json>`, `<appendix.tex>` (verbatim).

The Codex side intentionally does not get to see Claude's findings — this preserves error independence.

---

## Phase 2c — Cross-critique

**Two parallel `codex exec` calls** producing structured critiques. Each side critiques the *other* side.

### 2c-i: Claude critiques Codex (main Claude thread)

Main Claude reads `findings_codex.json` and produces `critiques_claude_on_codex.json` (one critique per finding, including "I uphold this" for findings Claude agrees with).

The critique must include a 1-3 sentence `reasoning`, and for refute verdicts, a concrete counter-argument (a counter-example, a paper section the Codex side missed, or a misread of the claim text).

### 2c-ii: Codex critiques Claude (codex exec)

```bash
codex exec --output-schema ~/.claude/skills/proof-audit/schema/critique.schema.json \
  --output-last-message proof_audit/critiques_codex_on_claude.json \
  < phase2c_codex_prompt.txt
```

The prompt feeds Codex the union of the three Claude persona outputs (one critique per (claim_id, gap_type) tuple — Codex sees Claude findings in aggregate without persona attribution to avoid biasing).

---

## Phase 2d — Synthesis (deterministic tier classification)

This phase is **pure Python, deterministic**. No more LLM call. Given the four findings files and two critique files, every finding ends up in exactly one of five tiers.

### Inputs (per (claim_id, gap_type) pair)

For each (claim_id, gap_type) combination, count evidence on two axes:

- `claude_sources` ∈ {0, 1, 2, 3} — how many Claude personas surfaced it
- `codex_sources`  ∈ {0, 1}      — did the Codex side surface it
- `codex_verdict_on_claude` ∈ {uphold, partial-uphold, uphold-but-recategorize, refute, not-critiqued}
- `claude_verdict_on_codex` ∈ {uphold, partial-uphold, uphold-but-recategorize, refute, not-critiqued}

### Tier table

```
Tier A — STRONG
  Condition: (claude_sources >= 2 AND codex_sources == 1 AND no refute on either side)
          OR (claude_sources >= 1 AND codex_sources == 1 AND both sides upheld)
  Meaning: Cross-model + multi-persona agreement.

Tier B — CROSS_VALIDATED
  Condition: (claude_sources == 1 AND codex_sources == 1 AND no refute)
          OR (claude_sources >= 2 AND codex_sources == 0 AND no refute by Codex)
  Meaning: Same gap caught by two routes, but not the strongest possible signal.

Tier C — SOLO
  Condition: Exactly one side surfaced, and the other side did NOT critique it
             (because they did not see this gap type).
  Meaning: Single-source; needs human eyeballs.

Tier D — DISPUTED
  Condition: One side surfaced, other side critiqued with verdict "partial-uphold"
             or "uphold-but-recategorize" (i.e., real but reframed).
  Meaning: Real concern, exact framing in dispute.

Tier E — RESIDUAL
  Condition: One side surfaced, other side returned verdict "refute" with a concrete reason.
  Meaning: Likely false positive; moved to RESIDUAL.md for human override.
```

### Output ordering

Findings are emitted in `synthesized.json` ordered by:

1. Tier (A > B > C > D > E)
2. Severity (5 > 1)
3. Claim_id ascending

Tier E findings go **only** to `RESIDUAL.md`, not the main audit report.

### Why this is better than the old design

- **No magic numbers**: tier is a deterministic function of explicit evidence counts and explicit critique verdicts.
- **No `max(confidence)` Bayes-violation**: confidence is no longer averaged or maxed; it is a categorical tier.
- **Refutes are first-class**: a finding that the other side actively refutes goes to RESIDUAL, not silently filtered.
- **Cross-model bonus is structural, not numeric**: a finding surfaced by both Claude and Codex is automatically Tier A or B, regardless of self-reported confidence.

---

## Cost estimate per audit run (gpt-5.5 xhigh)

For a typical thesis appendix (~20 atomic claims, ~30k tokens):

| Phase | LLM calls | Approx tokens | Approx cost |
|---|---:|---:|---:|
| 2a (3 Claude personas) | 3 main-thread | 90k in, 15k out | — (Claude side) |
| 2b (Codex cross-model) | 1 codex exec | 32k in, 5k out | $0.45 |
| 2c-i (Claude critique) | 1 main-thread | 12k in, 4k out | — |
| 2c-ii (Codex critique) | 1 codex exec | 12k in, 4k out | $0.15 |
| 2d (Synthesis) | 0 (pure Python) | — | — |
| **Codex-side total** | — | — | **~$0.60** |

Canary preflight adds 5 × $0.20 = $1 on first run (cacheable for subsequent runs in the same session).

---

## Failure modes and abort conditions

| Condition | Action |
|---|---|
| Canary `pass=false` (< 3/5 hits) | Abort Phase 2. Write `RATE_CHAIN_AUDIT.md` style note: "SKILL ABORTED: canary failed". |
| `codex exec` returns non-zero exit | Retry 1× with same prompt; if still failing, abort and write fallback note. |
| Schema validation failure on persona output | Log to `proof_audit/schema_errors.log`, drop the finding, continue. |
| Phase 2c-ii Codex critique times out (>10 min) | Treat all unreviewed Codex findings as `not-critiqued` (i.e., they go to Tier C/D, not auto-rejected). |
| `appendix_tokens > 50k` | Switch to per-section slicing; merge synthesized.json across slices. Document slice boundaries in `proof_audit/slice_map.json`. |
