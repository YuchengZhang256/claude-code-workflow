---
name: proof-audit
description: "Audit math/stat proof rigor via 4-phase Claude+Codex debate; produce LaTeX patches with deterministic tier ranking. Use also for rate-chain composition with --rate-chain."
---

# proof-audit

审计数学/统计论文理论附录的**逻辑严谨性**，产出一份团队可执行的 LaTeX 补丁计划。本技能做且只做"找漏洞 + 给补丁"这一件事。

## 与邻近 skill 的边界

- **`explain-paper`**: 教会用户读懂一个证明 —— 本技能**不做**教学。
- **`paper-reader`**: 对整篇论文做 5 层批判性解读 —— 本技能**不做**全文评论。
- **`multi-model-review`**: 跨模型家族对抗评审 —— 本技能在 Phase 2 内**已经**做了 Claude+Codex 跨模型评审，不需要再调 multi-model-review。
- **`review-proof`**: 迭代式修复闭环 —— audit 完后，把 `THESIS_AUDIT.md` 喂给 `/review-proof` 做 audit → patch → 再 audit 循环。

触发词: `/proof-audit <file>`、"audit the proofs in X"、"check appendix rigor"、"find gaps in the appendix"、"审阅附录严谨性"、"审计这篇论文的证明"。

## 输入

- 一份论文/毕业论文的理论附录：**优先 .tex 源码**；数字 PDF 仅作 fallback（见下 PDF policy）。
- 可选：主文正文（用于核对记号与假设的引用一致性）。

## 工件路径

```
<cwd>/
└── proof_audit/
    ├── state.json                           # Cross-round durable state (Phase α, NEW)
    ├── claims.json                          # Phase 1
    ├── findings_claude_pedantic.json        # Phase 2a
    ├── findings_claude_adversarial.json     # Phase 2a
    ├── findings_claude_generous.json        # Phase 2a
    ├── findings_codex.json                  # Phase 2b
    ├── critiques_claude_on_codex.json       # Phase 2c-i
    ├── critiques_codex_on_claude.json       # Phase 2c-ii
    ├── synthesized.json                     # Phase 2d
    ├── classified.json                      # Phase 2d.5 (NEW): tier L/S/O per finding
    ├── prior_round_state.json               # Round-N entry: prior context for personas
    ├── round_metric.json                    # Round-N output: metrics + convergence decision
    ├── lint_report.json                     # Phase 3 (patch lint)
    └── RESIDUAL.md                          # Phase 2d Tier-E findings
└── THESIS_AUDIT.md                          # Phase 4 (main deliverable)
└── OPEN_PROBLEMS.md                         # Tier-O findings (NEW)
```

---

## Phase 0 — Canary preflight (mandatory, gate)

Run before Phase 1 on every fresh session. Costs ~$1 on gpt-5.5 xhigh, ~5 min.

```bash
bash ~/.claude/skills/proof-audit/canary/run_canary.sh
```

5 known-buggy minimal proofs (DCT, Hoeffding, iid, n=1, cross-fitting) checked against expected `gap_type`. **Gate: ≥ 3 / 5 must HIT.** If fewer, skill aborts and writes a one-line `THESIS_AUDIT.md` saying "SKILL ABORTED: canary failed" with the failure details. Do not proceed with a bad extractor.

Skip Phase 0 only if a clean canary report from the same day exists at `~/.claude/skills/proof-audit/canary/runs/<today>/canary_report.json` with `pass=true`.

---

## Phase 1 — Atomic decomposition

1. **Read appendix**:
   - `.tex` → use Read tool directly.
   - Math-heavy digital PDF → use `pdftotext -layout` for relevant pages or Read small page ranges; never OCR (it mangles LaTeX). **Confidence is auto-capped at 0.6 for all PDF-extracted findings.**
   - Scanned / handwritten / image-based PDF → **REJECT**; instruct user to obtain .tex or mathpix.
2. **Collect global preamble**: scan whole paper for `\begin{assumption}` / `\begin{setup}` / `\newtheorem*{}{Assumption}` environments and any inline "Assume that ..." declarations in Section 1-2. Save as `proof_audit/global_assumptions.txt`. This is prepended to every persona prompt so cross-section assumption inheritance does not produce false-positive "undeclared" gaps.
3. **Parse into atomic claims**: every numbered Lemma/Theorem/Proposition/Corollary **plus** every non-trivial intermediate step in proof bodies. Assign stable IDs `C1, C2, ...`. Each claim's record:

```json
{
  "claim_id": "C7",
  "claim_text": "verbatim statement",
  "depends_on": ["C3", "C5", "Slutsky"],
  "appendix_section": "A.2",
  "file_line": "appendix.tex:412"
}
```

Output: `proof_audit/claims.json`. This is **read-only context** for Phase 2.

---

## Phase 2 — Multi-source debate audit

Replaces the old "3-persona ensemble + magic confidence merge" design. Four sub-phases, two Claude-side and two Codex-side. Full spec in [`references/phase2_debate.md`](references/phase2_debate.md); copy-paste prompt skeletons in [`references/persona_prompt_skeleton.md`](references/persona_prompt_skeleton.md); high-level recap below.

**Mandatory preamble** for every persona prompt (Pedantic / Adversarial / Generous / codex): the *Manuscript access protocol* in `phase2_debate.md`. It tells the persona to read `claim_packages/{Cxx}.json` instead of opening the full manuscript. Without this, subagents hit the socket-fail loop after 9-15 Read calls (observed 4/4 in osaa).

| Sub-phase | Side | Action |
|---|---|---|
| **2a** | Claude | 3 personas (pedantic / adversarial / generous) audit `claims.json` independently. Each produces a JSON file conforming to `schema/gap.schema.json`. Subagent fan-out if `len(claims) >= 5`; main-thread serial otherwise. **Personas use corrected briefs (with "positive companion" clauses, see phase2_debate.md §2a)** to avoid the `feedback_subagent_negative_constraints` trap. |
| **2b** | Codex | One independent cross-model audit via `codex exec --output-schema schema/gap.schema.json -m gpt-5.5 -c model_reasoning_effort=xhigh`. Codex does **not** see Claude's findings. |
| **2c** | Both | Cross-critique: Claude critiques `findings_codex.json`; Codex critiques the union of three Claude persona outputs. Each side emits a JSON conforming to `schema/critique.schema.json` with verdict ∈ {uphold, refute, partial-uphold, uphold-but-recategorize}. |
| **2d** | Python | **Deterministic synthesis** by tier (A/B/C/D/E). No magic numbers. See tier table below. |

### Phase 2d synthesis tiers (no magic numbers)

For each (claim_id, gap_type) pair, the tier is a deterministic function of (claude_sources, codex_sources, codex_verdict_on_claude, claude_verdict_on_codex):

```
Tier A — STRONG          ≥2 Claude personas + Codex agree, no refute
Tier B — CROSS_VALIDATED 1 Claude + 1 Codex agree, OR ≥2 Claude only
Tier C — SOLO            single source, other side did not critique
Tier D — DISPUTED        surfaced + other side returned partial-uphold
Tier E — RESIDUAL        surfaced + other side returned refute with concrete reason
```

`synthesized.json` keeps A-D in tier+severity descending order. Tier E goes to `RESIDUAL.md` only (not silently dropped — user can re-promote on human review).

---

## Phase 2.5 — Triage classification (NEW: Phase α addition)

Each finding from Tier A-D is further classified into **L / S / O** by `scripts/triage.py`. This separates concerns into three qualitatively different handling paths:

| Tier | Meaning | Routing |
|---|---|---|
| **L** Logical bug | Fixable by ≤30 lines of LaTeX without changing model assumptions | Auto-fix queue (Phase 6, codex apply) |
| **S** Style/citation/exposition | Fixable by single-pass human review (citation, wording, notation) | Queue to LATEST_AUDIT.md "human review" section |
| **O** Open problem | Requires new mathematical theorem / scope reduction | Archive to OPEN_PROBLEMS.md |

```bash
python3 ~/.claude/skills/proof-audit/scripts/triage.py classify \
    proof_audit/findings_v<N>.json \
    --state proof_audit/state.json \
    --out proof_audit/classified.json
```

Hard rules (first-match wins, ordered):
1. **claim-level recurring ≥3 rounds** → Tier S (concept re-discovered under different framings; iteration unlikely to help).
2. **gap_type ∈ open-problem catalog** → Tier O.
3. **issue text contains "open"/"requires new"** → Tier O.
4. **citation-strength concerns** → Tier S.
5. **scope/closure concerns at sev≥4** → Tier O; at sev≤3 → Tier S.
6. **gap_type ∈ logical-bug catalog with severity≥3** → Tier L.
7. Default by severity + patch size.

See `python3 scripts/triage.py rules` for the full catalog.

**Empirical validation (osaa_ultrasparse_refinement.tex 11-round replay)**: with triage active from round 1, the auto-fix loop converges at round 7 instead of round 11 (4 rounds saved). LLV citation concerns auto-promote to Tier S after 3 rounds; DCSBM closure auto-promotes to Tier O.

---

## Phase α + β subsystem — Cross-round memory, convergence & dashboard

Five CLI tools introduced together (Phase α: state/triage/convergence; Phase β: package_claims, metrics).

### End-to-end round flow (canonical sequence)

After Phase 1 has produced `proof_audit/claims.json`, the per-round loop is:

```bash
# Once per session: build per-claim packages (Phase β.1)
python3 scripts/package_claims.py build --claims proof_audit/claims.json

# Once per session: bootstrap state (skip if already exists)
python3 scripts/state.py init src/<manuscript>.tex
# OR migrate from a v1 synthesized.json after the first round
# python3 scripts/state.py migrate proof_audit/synthesized.json src/<manuscript>.tex --round 1

# --- per-round loop ---
# (Phase 2 — see persona_prompt_skeleton.md for prompt templates)
#   personas read proof_audit/prior_round_state.json + claim_packages/{Cxx}.json
#   they emit findings_*.json and critiques_*.json into proof_audit/

# Phase 2d: synthesize tiers (existing pipeline) -> proof_audit/synthesized.json
# Phase 2.5: triage classify -> findings_classified.json
python3 scripts/triage.py classify proof_audit/findings_classified_input.json \
    --state proof_audit/state.json --out proof_audit/findings_classified.json
python3 scripts/triage.py update-state \
    --state proof_audit/state.json --round N \
    proof_audit/findings_classified.json

# Compute & commit round metric
python3 scripts/convergence.py compute --state proof_audit/state.json \
    --round N --out proof_audit/round_N_metric.json
python3 scripts/state.py round proof_audit/round_N_metric.json

# Decide whether to keep iterating
python3 scripts/convergence.py decide --state proof_audit/state.json --commit-decision

# Look at the dashboard before deciding the next move
python3 scripts/metrics.py --state proof_audit/state.json show

# Emit prior context for round N+1 (with package paths attached)
python3 scripts/state.py prior proof_audit/prior_round_state.json \
    --packages-dir proof_audit/claim_packages
# --- end loop ---
```

Three independent CLI tools (introduced in Phase α):

### `scripts/state.py` — Durable cross-round state

Maintains `proof_audit/state.json` (schema v2, see `schema/state.schema.json`) with per-finding lifecycle: `first_round → fix_attempts → closed | open_problem | stable_recurring`. Critical for preventing the "codex re-discovers same concern across 6 rounds" failure mode observed in the osaa case study.

```bash
# Init at start of session
python3 scripts/state.py init <manuscript.tex>

# Bootstrap from existing v1 synthesized.json (one-time migration)
python3 scripts/state.py migrate proof_audit/synthesized.json <manuscript.tex> --round 1

# Each new round: ingest findings + emit prior context for next round's prompts
python3 scripts/state.py update-finding <findings.json>
python3 scripts/state.py prior proof_audit/prior_round_state.json --max 30
```

`prior_round_state.json` is **mandatory input** to all Phase 2 personas / codex prompts in rounds ≥ 2. Each entry includes `claim_level_recurring_count`, `prior_fix_attempts` (last 3), and explicit instructions: *if you would re-flag this concern, you MUST acknowledge prior fixes and propose a CONCRETELY DIFFERENT approach, not a re-phrasing.*

### `scripts/triage.py` — Tier L/S/O classifier (see Phase 2.5 above)

### `scripts/package_claims.py` — Per-claim pre-slicing (Phase β.1)

Pre-slices the manuscript .tex into per-claim packages so subagents can read a 100-300 line window per claim instead of the full 4000+ line manuscript. Addresses the recurring socket-fail mode where the Adversarial persona dies after 9-15 Read tool calls (observed 4/4 times in the osaa case study).

```bash
# Build all packages from claims.json
python3 scripts/package_claims.py build \
    --claims proof_audit/claims.json \
    --outdir proof_audit/claim_packages \
    --context-lines 50

# Inspect one package (debugging)
python3 scripts/package_claims.py inspect \
    --package proof_audit/claim_packages/C20.json --show-text

# Print manifest table
python3 scripts/package_claims.py manifest --outdir proof_audit/claim_packages
```

Each `claim_packages/{Cxx}.json` contains: `statement_text`, `proof_text`, `context_before_text`, `context_after_text`, `hypertargets[]`, `section_header`, `depends_on[]`, plus 1-indexed line ranges for traceability. The builder uses label-based anchoring (with full-file fallback when `claims.json` is stale relative to the current manuscript), and tracks `warnings[]` for any heuristic mismatches.

`scripts/state.py prior --packages-dir proof_audit/claim_packages` injects a `package_path` into every active finding in `prior_round_state.json`. Persona prompts then read that small package directly (~150 lines) instead of opening the manuscript. **Validated on osaa: 22× token reduction per claim** (205 lines for C20 vs 4612-line manuscript).

### `scripts/metrics.py` — Per-round dashboard (Phase β.3)

```bash
# ASCII tables to stdout (after-round triage)
python3 scripts/metrics.py --state proof_audit/state.json show

# Markdown report (drops into project root or proof_audit/)
python3 scripts/metrics.py --state proof_audit/state.json report --out proof_audit/metrics_report.md

# Machine-readable summary
python3 scripts/metrics.py --state proof_audit/state.json json --out proof_audit/metrics.json
```

Five blocks per snapshot: round trajectory (one row per round, with `openL` Tier-L backlog and `ΔL` round-over-round delta), lifecycle counts, Tier-L pending backlog table (the actual auto-fix work), source breakdown across open findings, and a convergence preview that runs `convergence.py decide` read-only against the current state. The convergence preview lets you see *what the engine would decide right now* before running it with `--commit-decision`.

### `scripts/convergence.py` — Auto-stop decision engine

```bash
# Compute round-N metric (tier-aware, includes open Tier-L backlog)
python3 scripts/convergence.py compute --state state.json --round N --out round_metric.json

# Decide whether to continue iteration
python3 scripts/convergence.py decide --state state.json --commit-decision
```

Decision rules (deterministic, ordered):
- **R1 STOP_STUCK** at hard cap (default 12 rounds).
- **R2 STOP_STUCK** if 3 consecutive rounds with 0 new actionable Tier-L sev≥4 AND stable-recurring open. Iteration is spinning on style.
- **R3 STOP_CONVERGED** if no open Tier-L pending AND no new sev≥4 this round. Auto-fix backlog drained.
- **R4 PAUSE_HUMAN** if persona false-positive rate > 0.6.
- **R5/R6** stay-converged or default-continue.

Decision writes back to `state.json`'s `iteration_status` field if `--commit-decision`.

---

## Phase 3 — Patch lint (mandatory before final report)

```bash
python3 ~/.claude/skills/proof-audit/scripts/lint_patches.py \
    --synthesized proof_audit/synthesized.json \
    --paper-source main.tex appendix.tex \
    --out proof_audit/lint_report.json
```

Three checks per `latex_patch`:
1. `\hypertarget{...}` anchor inside the patch matches `finding.hypertarget_anchor`.
2. Every `\ref{...}`, `\eqref{...}`, `\Cref{...}` referenced inside the patch points to a label that **actually exists** in the paper source. Hallucinated labels are dropped.
3. `latexmk -draftmode` dry-run on a minimal wrapper containing the patch (skipped with `--no-latex`).

Plus one global check: `hypertarget_anchor` uniqueness across all findings.

Findings that fail lint are demoted to `RESIDUAL.md` with the specific error; they do **not** go in the main report.

---

## Phase 4 — Fix plan output (THESIS_AUDIT.md)

```markdown
# Thesis Appendix Audit — <paper title>

## Summary
| metric | count |
|---|---|
| total atomic claims | N |
| Tier A (STRONG)     | ... |
| Tier B (CROSS_VALIDATED) | ... |
| Tier C (SOLO)       | ... |
| Tier D (DISPUTED)   | ... |
| Tier E (RESIDUAL — see RESIDUAL.md) | ... |
| canary pass rate    | k / 5 |
| pdf_extraction_warning | yes/no |

## Quick action list (top 5 from Tier A+B by severity)
1. **[C7 / Tier A / severity 5 / DCT-no-dominating-function]** ...
2. ...

## Prioritized findings (Tier A → D)

### [C3 / Tier A / severity 4 / limit-derivative-no-Leibniz]
**Claim excerpt** (verbatim): > ...
**Surfaced by**: pedantic, adversarial, codex-cross-model
**Critique verdicts**: codex→claude=uphold, claude→codex=uphold
**Gap**: 交换 $\partial_\theta$ 与 $\mathbb{E}$ 时未给 dominating function。
**LaTeX patch** (insert before equation (A.7) in Appendix A.2):
\`\`\`latex
\hypertarget{gap_C3_limit-derivative-no-Leibniz}{}%
...
\`\`\`
**Lint**: all checks passed.

(Tier D entries include `dispute summary: ...` line.)

## Residual low-confidence items
See RESIDUAL.md.
```

## Format rules (hard)

- All math expressions in LaTeX: inline `$...$`, display `$$...$$`. Never plain text.
- Markdown for structure; JSON schema / LaTeX code blocks stay English.
- Explanatory prose in Chinese.
- Never write ad-hoc PDF reader scripts. PDF routing: see Phase 1 step 1.

## References

- [`references/phase2_debate.md`](references/phase2_debate.md) — full 4-phase debate spec, persona briefs, tier classifier.
- [`references/common_proof_gaps.md`](references/common_proof_gaps.md) — 52 gap-type checklist (1-to-1 with `schema/gap.schema.json` enum).
- [`references/limits.md`](references/limits.md) — 10 classes of error the audit **cannot** catch. Read before claiming "no gaps."
- [`schema/gap.schema.json`](schema/gap.schema.json) — strict OpenAI structured-output schema for persona findings.
- [`schema/critique.schema.json`](schema/critique.schema.json) — strict schema for cross-critique.
- [`canary/snippets.json`](canary/snippets.json) — 5 known-buggy minimal proofs.
- [`canary/run_canary.sh`](canary/run_canary.sh) — preflight runner.
- [`scripts/lint_patches.py`](scripts/lint_patches.py) — Phase 3 lint.
- [`scripts/state.py`](scripts/state.py) — Phase α: cross-round durable state.
- [`scripts/triage.py`](scripts/triage.py) — Phase α: Tier L/S/O classifier.
- [`scripts/convergence.py`](scripts/convergence.py) — Phase α: auto-stop decision engine.
- [`schema/state.schema.json`](schema/state.schema.json) — Phase α: state.json schema v2.

---

## Rate-chain mode (`/proof-audit --rate-chain`)

When the audit target is a **composed big-O rate corollary** (e.g. `thm:misclustering`, `cor:*-consistency`, `cor:*-rate`) rather than per-claim formal correctness, switch to this mode.

This mode does what the default 4-phase pipeline cannot: **symbolic exponent-vector composition across 10+ lemmas**. Persona-based slice audit cannot see this kind of cross-section rate-exponent drift; deterministic exponent-vector composition catches it.

### Trigger

- `/proof-audit --rate-chain <paper.tex> <target-label>` — explicit target corollary.
- 自然语言: "check the rate composition", "verify end-to-end rate", "does cor X's rate match its proof chain", "验证 rate 链合成"。
- 反触发: 一次性 bound、数值 benchmark、非 rate 型 corollary → 回退默认 Phase 1–4。

### 工作流 & 脚本

完整工作流（Phase A 提取、Phase B 双盲 extractor、Phase B.2/B.4 一致性检查、Phase C 确定性 exponent-vector 合成、Phase D walked-vs-stated diff 报告）见 [`modes/rate-chain/MODE.md`](modes/rate-chain/MODE.md)。关联脚本、schema、reference material、example runs 都在 `modes/rate-chain/` 子目录下：

- `modes/rate-chain/MODE.md` — 完整 phase 说明
- `modes/rate-chain/scripts/` — `compose.py` 等确定性脚本
- `modes/rate-chain/schema/` — rate-table JSON schema
- `modes/rate-chain/references/` — rate-composition pattern 清单
- `modes/rate-chain/example_runs/` — 历史运行样例

### 跨模型冗余

Phase B.1 的两个 extractor subagent 可以换成 `codex exec --output-schema rate_table.schema.json -m gpt-5.5` 调用，compose/diff 阶段仍走同一份 `modes/rate-chain/scripts/compose.py`。两轮输出 rate-table 一致则合并置信度高；不一致则自动列为 flagged entry 交人类判断。
