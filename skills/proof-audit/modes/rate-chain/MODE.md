---
name: rate-chain-audit
description: Symbolically compose a math/statistics paper's lemma-chain rates end-to-end and diff against a top-level "explicit rate" corollary, reporting exponent-level chain-breaks the author missed. Activate when the user says /rate-chain-audit, "check the rate composition", "does the stated rate match the lemma chain", or "verify end-to-end rate". Do NOT use for claim-local formal correctness (that is proof-audit), for teaching proofs (explain-paper), or for papers whose main result is not a composed big-O rate (one-shot bounds, numerical tables).
---

# rate-chain-audit

唯一职责：给定一篇论文里某条 "explicit rate" 顶层 corollary，把它依赖的 lemma 链 **符号化地** 代数合成一次，和该 corollary 的声明式逐变量对比，发现 exponent 级失配。

本 skill 做 `proof-audit` 原理上做不到的事：**跨 10+ lemma 的代数合成**。Persona-based 切片审计看不到这种跨章节的 rate exponent 错位——需要 sympy 级代数合成才能抓。

## 与邻近 skill 的边界

| 任务 | 用这个 skill | 用别的 |
|---|---|---|
| lemma 链合成 vs 声明式失配 | **rate-chain-audit** | — |
| 单条 claim 形式正确性 | — | `proof-audit` |
| σ-代数 / measurability 细节 | — | `proof-audit` (pedantic persona) |
| 教懂一个证明 | — | `explain-paper` |
| 跨模型交叉验证 | — | `multi-model-review` |
| 纯计算论文 / 数值 benchmark | **不适用** (反触发) | — |

## 触发

- `/rate-chain-audit <paper.tex> <target-label>` — 显式指定目标 corollary。
- 自动侦测 `cor:.*rate.*`, `cor:.*consistency.*`, `thm:misclustering` 等常见 rate-claim 命名。
- 自然语言触发："check the rate composition"、"verify end-to-end rate"、"does cor X's rate match its proof chain"。

## 反触发（遇到这些立刻拒绝）

- Paper 没有至少 5 条 lemma 的合成链（一次性定理不适用）。
- 顶层声明不是 big-O / $\lesssim$ / 渐近形式（纯数值 bound 不适用）。
- 论文用 Lean / Coq 形式化过（这种 skill 就是为未形式化的 LaTeX 稿设计的）。

## 工件路径

```
<cwd>/
├── rate_chain/                    # skill 的所有中间件写入这里
│   ├── dag.json                   # Phase A 输出
│   ├── rate_table_A.json          # Phase B 抽取 A
│   ├── rate_table_B.json          # Phase B 抽取 B
│   ├── rate_table.json            # Phase B 裁决后最终版
│   ├── canary_report.json         # Phase B 自检
│   ├── composition_trace.json     # Phase C 合成轨迹
│   └── walked_vs_stated.json      # Phase C 最终对照
└── RATE_CHAIN_AUDIT.md            # Phase D 主交付物
```

如果 `<cwd>/rate_chain/` 已存在，skill 会提示用户确认是否覆盖。

---

## Phase A — Chain discovery (deterministic, 0 tokens)

从 target label 出发向上 trace `\ref` / `\eqref` / `\Cref`，建最小祖先 DAG。

```bash
python3 ~/.claude/skills/rate-chain-audit/scripts/discover_chain.py \
    --target <label> \
    --paper <paper.tex> \
    [--supplement <sup1.tex> --supplement <sup2.tex> ...] \
    --out rate_chain/dag.json
```

输出的 DAG JSON 格式见 `schema/dag.schema.json`。每个 node 带 `claim_id`, `label`, `file_line`, `kind`, `statement_text_span`, `proof_text_span`；每条 edge 标 `<childclaim> uses <parentclaim> via (<line>:<ref_label>)`。

**若 target 的祖先 DAG < 5 个 claim → skill abort with "chain too short, not applicable"。**

---

## Phase B — Double-blind rate extraction (Claude 子代理并行执行)

这一阶段 skill 用 Claude 的 **Agent 工具并行派发两路抽取**，然后裁决。没有人工 checkpoint——所有判断在 skill 内部完成。

### B.1 · 双盲抽取（核心防御）

**对 DAG 里每个 claim，在一轮 tool-use 消息里并行派发两个 subagent**：

- **Agent A — Statement-only extractor**
  > You will be given the VERBATIM statement (theorem/lemma text, NOT proof) of claim `<claim_id>` from a mathematical paper. Extract its output "rate" as a dict of exponents per variable in the fixed schema `rate_table.schema.json`. Do NOT read the proof body. If the statement gives only a qualitative bound, emit `kind: "qualitative"` with empty exponent dict. Return JSON matching the schema, nothing else.

- **Agent B — Proof-body-walker extractor**
  > You will be given the VERBATIM proof body (NOT the theorem statement) of claim `<claim_id>`. Re-derive the output rate from the proof steps, ignoring what the theorem claims. Extract exponents per variable in the same schema. If the proof body uses another lemma's result as a black box, cite that lemma's claim_id in `black_box_dependencies`. Return JSON matching the schema, nothing else.

两份输出写到 `rate_chain/rate_table_A.json` 和 `rate_chain/rate_table_B.json`。

**Agent A 和 Agent B 必须在同一条 tool-use 消息里并行发**（独立 subagent，互不可见对方输出），否则无效。

### B.2 · 裁决

```bash
python3 ~/.claude/skills/rate-chain-audit/scripts/reconcile_tables.py \
    --a rate_chain/rate_table_A.json \
    --b rate_chain/rate_table_B.json \
    --out rate_chain/rate_table.json \
    --disagreements rate_chain/disagreements.json
```

对每个 claim：
- A 和 B 的 rate_dict 相等 → `confidence=0.95`，进合成。
- 不相等 → 写入 `disagreements.json`，等待 B.3 arbitration。

### B.3 · Arbitration（仅当 B.2 有分歧时）

对每条 disagreement，再派一个 subagent：

- **Agent C — Adversarial arbitrator**
  > Claim `<claim_id>`: Extractor A said `<rate_A>`, Extractor B said `<rate_B>`. Read the FULL claim environment (statement + proof body). Decide which extractor is correct and why, OR declare both plausible if you cannot rule either out. If you rule, emit `{"verdict": "A|B", "reason": "<1-sentence>"}`. If both plausible, emit `{"verdict": "dual-path", "reason": "..."}`.

Verdict 为 `dual-path` 的条目进 Phase C 做**双路径合成**——两条 walked rate 并列输出。

### B.4 · Canary self-check（强制前置守门）

```bash
python3 ~/.claude/skills/rate-chain-audit/scripts/canary_check.py \
    --extracted rate_chain/rate_table.json \
    --known ~/.claude/skills/rate-chain-audit/references/known_rates.md \
    --out rate_chain/canary_report.json
```

Canary 从 `references/known_rates.md` 抽 20 条教科书 rate（Bernstein、Davis-Kahan、Wedin 等），对同一 Extractor A prompt 抽取它们，和硬编码的 ground truth 比对。

**≥ 3 条错就立刻 abort 整个 skill**，写 `RATE_CHAIN_AUDIT.md` 顶部一行 "SKILL ABORTED: extraction canary failed"，附失败明细。不允许带着坏抽取进 Phase C。

---

## Phase C — Symbolic composition (sympy, deterministic)

```bash
python3 ~/.claude/skills/rate-chain-audit/scripts/compose.py \
    --dag rate_chain/dag.json \
    --rates rate_chain/rate_table.json \
    --target <label> \
    --out rate_chain/walked_vs_stated.json \
    --trace rate_chain/composition_trace.json
```

按 DAG 拓扑序施加四类合成规则：

| 规则 | 触发标记 | sympy 操作 |
|---|---|---|
| **Sequential** | `uses` edge + 后代在 rate_dict.template 里引用 `<upstream>` | 代入：`rate_child = rate_child_template(rate_parent)` |
| **Triangle sum** | 后代 rate_dict.merge_mode = "triangle" | per-entry max |
| **Squared concat** | merge_mode = "concat_square" | per-entry × 2 then 加 $M^1$ |
| **Union bound** | merge_mode = "union" + `union_variable` 给定 | log exponent +1（per variable 也可） |

每条合成写入 `composition_trace.json`，**每行带 provenance**（这条 rate 怎么来的）。

双路径条目（Phase B.3 dual-path）产出两条平行合成。

Phase C 是**纯确定性**的——同一 `rate_table.json` + `dag.json` 输入永远给同一输出。任何审稿人可以重跑验证。

---

## Phase D — Diff + report (sympy + Python)

```bash
python3 ~/.claude/skills/rate-chain-audit/scripts/diff_report.py \
    --walked rate_chain/walked_vs_stated.json \
    --trace rate_chain/composition_trace.json \
    --canary rate_chain/canary_report.json \
    --disagreements rate_chain/disagreements.json \
    --out RATE_CHAIN_AUDIT.md
```

报告结构：
1. **顶部**：Walked vs Stated 对照表。一眼看清楚。
2. **Chain-breaks**：每条失配配两个 LaTeX patch option（"relax corollary" / "tighten upstream lemma X"），锚 `\hypertarget{gap_ratechain_<var>_<claim_id>}`。
3. **Double-path findings**（若 Phase B.3 有 dual-path）：两条 walked rate 并列，标明"若 Extractor A 正确 → 结论 1；若 B 正确 → 结论 2"。
4. **Provenance table**：每条 walked rate entry 的出处（claim_id + file:line + raw excerpt）。
5. **Canary pass rate**：20 条 canary 里过了几条，失败的列出来。
6. **Confidence decay**：每条 chain-break 的 posterior confidence = prior × $0.95^{depth}$。
7. **Hard CAVEAT**：`## Limits of this audit` 一节，列 10 条 skill 本质上抓不到的事（见 `references/limits.md`）。

## Phase E — Post-hoc ReAct oversight (optional, Claude in-context)

合成结果生成后，Claude 把 walked vs stated 表反喂给自己，问 "from first principles, does this composition make sense? any missing sympy rule?"。若发现代数疏漏（例如 union bound 漏 $\log M$），在 `RATE_CHAIN_AUDIT.md` 末尾追加 `## Post-hoc oversight notes`。不覆盖主表。

---

## 成本估算（以一篇 200 KB 主稿 + 70 KB 补充、20 祖先 claim 为例）

| Phase | LLM 调用 | Input tokens | Output tokens |
|---|---:|---:|---:|
| A | 0 | 0 | 0 |
| B.1 | 40 (20 × 2 双盲) | ~120k | ~16k |
| B.3 | ~2 (10% 分歧) | ~6k | ~1k |
| B.4 canary | 20 | ~30k | ~6k |
| C | 0 | 0 | 0 |
| D | 1 | ~5k | ~5k |
| E | 1 | ~5k | ~2k |
| **合计** | ~64 | **~166k** | **~30k** |

按 Opus $15/M in + $75/M out：单次约 $4-5。Sonnet 约 $0.5。

---

## 硬 CAVEAT — 本 skill 不能做的事

见 `references/limits.md`。摘要：

1. 常数级错误（只验 exponent）。
2. Lemma statement vs proof-body 漂移——双盲部分 cover，但 Extractor B 自身可能和作者同错。
3. Lemma 本身逻辑错误（skill 假定 lemma 对）。
4. 隐式 assumption 沿 lemma 链泄漏。
5. 作者引入的新证明技术本身的对错。
6. 论文整体 off-by-truth（声明和链合成都错但一致）。
7. Measurability / σ-代数细节。
8. 自然语言 vs 公式 quantifier 漂移。
9. Proof body 内循环引用（不走 \ref）。
10. 外部引文（Davis-Kahan 等）的正确性。

对上述盲区，唯一完备解是 Lean / Coq 级形式化——超出本 skill 定位。
