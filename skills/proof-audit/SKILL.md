---
name: proof-audit
description: Audit the theoretical appendix of a math/statistics paper or thesis for logical gaps, unjustified steps, missing assumptions, and edge cases. Output a structured fix plan with copy-pasteable LaTeX patches anchored by gap IDs. Use when the user says "audit this proof", "check appendix rigor", "find gaps in the proofs", or invokes /proof-audit. Best for pre-submission thesis review. NOT for teaching proofs (use explain-paper) or full-paper critique (use paper-reader).
---

# proof-audit

审计数学/统计论文理论附录的**逻辑严谨性**，产出一份团队可执行的 LaTeX 补丁计划。本技能做且只做"找漏洞 + 给补丁"这一件事。

## 与邻近 skill 的边界

- **`explain-paper`**: 教会用户读懂一个证明 —— 本技能**不做**教学。
- **`paper-reader`**: 对整篇论文做 5 层批判性解读 —— 本技能**不做**全文评论。
- **`multi-model-review`**: 跨模型家族对抗评审 —— 本技能做**单模型多 persona** 评审。

触发词: `/proof-audit <file>`、"audit the proofs in X"、"check appendix rigor"、"find gaps in the appendix"、"审阅附录严谨性"、"审计这篇论文的证明"。

## 输入

- 一份论文/毕业论文的理论附录：PDF 或 LaTeX 源码。
- 可选：主文正文（用于核对记号与假设的引用一致性）。

## Phase 1 — Atomic decomposition

1. **读入附录内容**
   - PDF → 按 global CLAUDE.md `## PDF and Image Reading` 规则路由：**长于 20 页或版式复杂**（附录常常如此）用 `cnai flash` 完整提取；**短小简单** PDF（≤ 20 页、主要是文本）可以直接 `Read`。论文附录默认偏复杂、嵌满公式，建议默认 `cnai flash` 更稳妥。
   - `.tex` 源码 → 用 `Read` 工具直接读取。
   - 若正文里有关键记号/假设定义，补读相关章节。
2. **解析为原子 claim**。附录中每一个独立推理步骤（显式编号的 Lemma/Theorem/Proposition/Corollary **以及** 证明体中的非平凡 intermediate step）都是一个 claim。
3. 给每个 claim 分配稳定 ID: `C1, C2, ...`，并建立如下 JSON 档案：

```json
{
  "claim_id": "C3",
  "claim_text": "verbatim statement",
  "preconditions": ["A1 regularity", "Assumption 2.1 (iid)"],
  "invoked_lemmas": ["Lemma A.1", "Slutsky"],
  "status": "verified | gap | missing_assumption | unjustified_step | symbol_abuse",
  "gap_type": "limit-exchange | measurability | iid-undeclared | regularity | tail-bound | boundary-case | symbol-reuse | ...",
  "severity": 1,
  "latex_patch": "...",
  "confidence": 0.0
}
```

- `severity`: 1 (cosmetic) — 5 (证明崩塌)
- `confidence`: 0.0–1.0, 模型对"这里确有 gap"的把握度

Phase 1 的输出是一份完整的 claim 清单（ID + claim_text + preconditions + invoked_lemmas），尚未评估 status。此清单会作为**只读上下文**传给 Phase 2 的三个 persona subagent。

## Phase 2 — Three parallel persona audits

按 global CLAUDE.md 的 `## Subagent 并行调用判断准则`，三路任务相互独立、无数据依赖、合并阶段在 Phase 3 显式处理——**默认通过 Agent 工具并行派发三个 persona subagent**。例外：

- 若 claim 数 < 5 且附录提取文本 < 10k token → 主线程可以顺序处理三个 persona，跳过 Agent 调用（该准则下"整个任务在主上下文里塞得下"的情形）
- 若附录提取文本 > 50k token → 按证明/定理章节切片，每片独立跑一轮三 persona 审计，避免单个 persona subagent 的 context 被一次性塞满

每个 subagent 收到：
1. Phase 1 的 claim 清单（完整）
2. 附录原文（完整；PDF 情况下是 `cnai flash` 的提取结果）
3. 自己的 persona brief（见下）
4. 输出要求：一个 JSON array，元素为 Phase 1 中定义的 gap schema

三个 persona brief：

### Persona A — Pedantic reviewer（咬文嚼字型）
> 你是一位以严苛著称的概率论教授。你只关心**形式正确性**：符号是否被重用、记号是否未定义就出现、σ-代数/可测性是否被忽略、regularity 条件（连续性、可微性、有界性）是否在使用前明确陈述、公式里是否有 typo 或维度不匹配。**不**考虑 claim 是否"直觉上对" —— 只看字面是否无懈可击。对每个 claim 返回 gap JSON；无问题则 `status: "verified"`。

### Persona B — Adversarial reviewer（对抗型）
> 你是一位想让作者证明崩塌的审稿人。对每个 claim，主动构造**反例、极端情形、退化输入、极限 regime**，尝试让 claim 在某个边界上失败。典型攻击点：$n \to \infty$ 与 $d \to \infty$ 的次序、退化分布（常数、点质量、重尾）、trivial case（$n=1$、空集、零方差）、独立性被隐式假设的地方、concentration 不等式常数是否随维度爆炸。每个成功攻击记为一个 gap，`gap_type` 填"counterexample-*"，并在 `latex_patch` 中写出需要补入的条件。

### Persona C — Generous reviewer（补救型）
> 你是一位同情作者、愿意把证明修好的同行。对每个看起来有 gap 的 claim，**给出让它成立所需的最小充分 regularity**，而不是直接打回。产出 `status: "missing_assumption"` 并在 `latex_patch` 中写出：(i) 应当添加到 Assumption block 的条件、(ii) 该条件为何是最小充分的一句话论证。

每个 persona 返回自己的 gap JSON 数组；三者之间不通信。

## Phase 3 — Consolidation

在主 agent 中合并三路输出：

1. **Dedupe**: 按 `(claim_id, gap_type)` 键去重。
2. **Conflict resolution**:
   - 若 ≥2 个 persona 在同一 `(claim_id, gap_type)` 上都报告了 gap → **保留**，`confidence` 取三者最大值。
   - 若只有 1/3 persona 报告 → 保留但标记 `"low-confidence, human judgment needed"`，`confidence` 下调 0.3。
   - 若同一 claim 被 Persona A 标 `symbol_abuse` 而 Persona C 标 `missing_assumption` → 合并为两条独立条目，不算冲突。
3. **Rank**: 按 `severity` 降序，`confidence` 作为次序打破 tie。

## Phase 4 — Fix plan output

在**当前工作目录**写 `THESIS_AUDIT.md`，结构如下：

```markdown
# Thesis Appendix Audit — <paper title>

## Summary
| metric | count |
|---|---|
| total atomic claims | N |
| verified | ... |
| gap (any type) | ... |
| worst severity | ... |

Gap breakdown by type: measurability=…, limit-exchange=…, iid-undeclared=…, ...

## Quick action list (top 3–5 highest-impact fixes)
1. **[C7, severity 5]** ...
2. ...

## Prioritized gap list

### Gap on C3 — limit-exchange, severity 4, confidence 0.82
**Claim excerpt**: > ...verbatim...
**Gap**: 在把 $\lim_{n\to\infty}$ 与 $\mathbb{E}[\cdot]$ 交换时未核对 DCT 的 dominating 条件。
**LaTeX patch** (insert before the exchange step in Appendix A.2):
\`\`\`latex
\hypertarget{gap_C3}{}%
By Assumption A1(iii), $|f_n(X)| \le g(X)$ with $\mathbb{E}[g(X)] < \infty$, so the
dominated convergence theorem applies and
$$\lim_{n\to\infty} \mathbb{E}[f_n(X)] = \mathbb{E}\bigl[\lim_{n\to\infty} f_n(X)\bigr].$$
\`\`\`
**Insertion hint**: 紧接 "interchange limit and expectation" 那一行之前。
```

**关键规则 — 每个 patch 必须携带 `\hypertarget{gap_<claim_id>}{}` 锚**，作为 backward-traceable ID，方便团队成员一眼从正文跳回审计报告。

报告末尾追加一段 "Residual low-confidence items"，列出 1/3 persona 报告但未达成共识的条目，供人类判断。

## Format rules (hard)

- 所有数学表达式使用 LaTeX：行内 `$...$`，行间 `$$...$$`。禁止把数学写成纯文本。
- Markdown 用于结构；JSON schema / LaTeX 代码块保持英文。
- 解释性散文用中文。
- 不写 `scripts/` 目录 —— PDF 读取走 global CLAUDE.md 的 size-gated 规则（长/复杂 PDF 用 `cnai flash`，短 PDF 直接 `Read`），无需本地脚本。

## References

- `references/common_proof_gaps.md` — 概率/统计证明中 ~50 个常见 gap 模式的 checklist，三个 persona 在审计时会参考此清单。
