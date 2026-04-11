---
name: lit-collision
description: Detect methodological collision between a draft paper and recent literature on arXiv / Semantic Scholar / OpenAlex. Extracts the draft's methodological features, runs iterative semantic search via paper-lookup, scores each candidate on 4 overlap axes, and produces a ranked collision-risk report with defense suggestions. Use when the user says "check for methodological overlap", "collision detection", "pre-submission competitive analysis", or invokes /lit-collision. NOT for full literature review (use literature-review) or generic paper search (use paper-lookup).
---

# lit-collision — 发表前方法论碰撞检测

本 skill 是一个**垂直原子 skill**，专门完成一件事：

> 把用户的 draft 论文与近期文献作"方法论碰撞检测"，输出一份**排序后的碰撞风险报告 + 防御建议**。

它不做全景式 literature review，不做 wiki 持久化，不做论文精读，也不做正向 idea 生成。那些是别的 skill 的事。本 skill 只在**投稿前**被调用一次，回答一个问题："这篇稿子跟最近的哪些论文撞车了？撞在哪个轴上？我该怎么辩护？"

## 何时触发 (Triggering)

- 用户显式命令: `/lit-collision <draft.pdf>`
- 自然语言意图:
  - "check for methodological overlap"
  - "pre-submission competitive scan"
  - "find papers that could scoop us"
  - "collision detection"
  - "方法论碰撞检测"
  - "发表前竞争态势分析"
  - "看看有没有人做过一样的东西"

**不要触发的情况**:
- 用户想要系统综述 → `literature-review`
- 用户想查某一主题的论文列表 → `paper-lookup`
- 用户想精读某一篇 → `paper-reader`
- 用户想把论文编进知识库 → `research-wiki`
- 用户想从观察生成新 hypothesis → `hypothesis-generation`

---

## 依赖工具

本 skill **不引入任何新 MCP server，不创建 `scripts/` 目录**。它只组合已有能力:

| 工具 | 用途 |
|---|---|
| `cnai flash` | 读 PDF / 图片 (遵循全局 CLAUDE.md 的 PDF 规则) |
| `paper-lookup` skill | 多数据库检索 (arXiv, Semantic Scholar, OpenAlex) |
| Task subagents | Phase 2 候选论文并行打分、Phase 4 苛刻评审 |
| `multi-model-review` (可选下游) | 对最终 report 做对抗式审稿，**本 skill 不自动调用**，仅在 report 末尾提示用户可以运行 |

---

## 工作流

### Phase 1 — Draft 特征抽取

1. 接收 draft 路径 (PDF 为主，也允许 `.tex` / `.md`)。
2. 按全局 CLAUDE.md `## PDF and Image Reading` 的 size-gated 规则读入 draft：
   - **长 / 复杂 draft PDF**（> 20 页、扫描版、公式/图表密集——绝大多数 statistics 草稿属于此类）→ 用 `cnai flash` 原文提取：
     ```bash
     cnai new flash   # 记录 hash
     cnai chat <hash> -f /path/to/draft.pdf << 'EOF'
     请将此文件中的所有内容完整逐字提取输出。不要总结，不要分析，不要省略任何部分。
     EOF
     ```
   - **短小简单 draft**（≤ 20 页、主要是文本、无扫描）→ 直接 `Read` PDF
   - `.tex` / `.md` 源码 → 直接 `Read`
3. 从提取后的原文中结构化抽取以下字段 (在上下文中构造，不落盘):

```json
{
  "problem": "1–2 sentences stating the question the draft answers",
  "method_family": "e.g. spectral clustering with distributed aggregation",
  "key_assumptions": ["iid", "sparse network", "smooth outcome regression", "..."],
  "datasets": ["synthetic SBM", "Stanford SNAP ego-facebook", "..."],
  "key_theorems": ["consistency of community labels", "minimax lower bound on SNR", "..."],
  "keywords": ["5–10 searchable terms"]
}
```

**抽取原则**:
- `method_family` 要写到"读者看一眼就能判断是否撞车"的粒度。不能只写"clustering"，要写"semi-definite relaxation of modularity on sparse networks"。
- `key_theorems` 要点出**定理的类型** (consistency / rate / minimax / identification / CLT / ...) 而不是编号。
- `keywords` 既要包含技术名 (e.g. "sparse stochastic block model")，也要包含**应用场景** (e.g. "distributed inference")。

### Phase 2 — 迭代检索（默认 1–3 轮，硬上限 10 轮）

**Round 1** — 调用 `paper-lookup` skill，用 `keywords` 向 arXiv + Semantic Scholar + OpenAlex 同时检索，每源 top-20（总共 ~60 候选，去重后约 30–50）。

**Subagent fanout 的条件判断（按全局准则，不是宗教仪式）** — 对本轮去重后的候选，按全局 CLAUDE.md `## Subagent 并行调用判断准则` 决定是否外包：

- 候选数 ≥ 6 且每条独立打分 → **并行** Task fanout，一次消息发射整轮调用
- 候选数 < 6 → 主线程直接打分即可，Agent 调用开销 > 价值
- 候选 PDF 读取：按 global PDF 规则（长/复杂用 `cnai flash`，短简单直接 `Read`，只有 abstract 时用字符串即可）

每个打分任务（并行或串行）产出一条候选打分 JSON（schema 见 Phase 3）。

**Token 预算估算（Phase 2 入口先报告）** — 估算 `预计轮数 R × 每轮候选数 N × ~2k token/候选 ≈ T token`，在启动 fanout 前先把 T 告知用户。默认 **R = 1–3** 对大多数草稿足够；只有 Round 1 未收集到 ≥ 10 篇 score ≥ 0.5 的候选时才启动 Round 2；10 轮是硬上限而非目标。若估算 T 超过用户可接受预算，降低 `R` 或 `N` 再跑。

**轮次终止条件**:
- 收集到 ≥ 10 篇打分 ≥ 0.5 的候选 → 进入 Phase 3
- 或已跑满 10 轮 → 进入 Phase 3
- 否则从本轮 top-5 的 abstract 中提取新查询词 (method family 术语、novel dataset 名、新出现的定理类型)，进入下一轮

**去重与合并** — 每轮结束后按 DOI / arXiv id / normalized title 合并。已见过的论文不重复打分。

### Phase 3 — 四轴碰撞打分

每篇候选在以下四个轴上被 subagent 独立打分 (0.0–1.0):

| 轴 | 含义 | 判据见 |
|---|---|---|
| `problem_overlap` | 回答同一个科学/统计问题 | `references/collision_taxonomy.md` |
| `method_overlap`  | 使用同一/可直接映射的技术 | 同上 |
| `theorem_overlap` | 定理类型 + 条件 + 速率可比 | 同上 |
| `dataset_overlap` | 相同经验数据或相同合成设置 | 同上 |

**加权总分**:

$$
\text{collision\_score} \;=\; 0.4 \cdot \text{method\_overlap} \;+\; 0.3 \cdot \text{theorem\_overlap} \;+\; 0.2 \cdot \text{problem\_overlap} \;+\; 0.1 \cdot \text{dataset\_overlap}
$$

**风险分级** (risk tier):

| Tier | 条件 | 语义 |
|---|---|---|
| `high`    | $\text{score} \ge 0.75$         | 直接威胁，必须在文内显式讨论并辩护 |
| `medium`  | $0.5 \le \text{score} < 0.75$   | 必须引用并说明差异 |
| `low`     | $0.25 \le \text{score} < 0.5$   | related work 一句话带过 |
| `cleared` | $\text{score} < 0.25$           | 无需处理 |

每个候选返回以下 schema (外层数组即本 skill 的主数据结构):

```json
{
  "paper_id": "arXiv:2401.XXXXX",
  "title": "...",
  "venue": "arXiv | NeurIPS | JASA | Biometrika | ...",
  "year": 2025,
  "problem_overlap": 0.0,
  "method_overlap": 0.0,
  "theorem_overlap": 0.0,
  "dataset_overlap": 0.0,
  "collision_score": 0.0,
  "risk_tier": "high | medium | low | cleared",
  "overlap_axes": ["method", "theorem"],
  "differentiators": ["your work uses X; they use Y"],
  "defense_suggestions": ["emphasize X in intro", "add corollary Y"],
  "defense_status": "not-yet-challenged | defended | undefended",
  "evidence_quote": "short literal quote from abstract/intro that justifies the scores"
}
```

**`defense_suggestions` 必须来自** `references/collision_taxonomy.md` 的 **Defense playbook**。不要自由发挥——防御动作受控词表保证一致性。

### Phase 4 — 苛刻评审 pass (harsh critic)

再派一个 Task subagent，人设:

> "你是一个刻薄的 JASA/NeurIPS 评审。你坚信 'trivial extension is NOT novelty'。你要**逐一攻击** top-5 高风险候选，论证 draft 相对于它只是 trivial extension。"

该 subagent 重新读 top-5 (如果数量不足 5，就读 top-k 高风险候选) 的 abstract + intro + 关键定理段，输出:

```json
{
  "harsh_critic_notes": [
    {
      "target_paper_id": "...",
      "attack": "The draft simply replaces assumption A with A' and rederives the same rate; the proof template is unchanged.",
      "counter_defense": "The draft's new regime requires a new concentration bound; cite Lemma X as the non-trivial ingredient."
    }
  ]
}
```

**`risk_tier` 由 `collision_score` 硬阈值决定，harsh critic 不会改写它**。harsh critic 的职责是独立地为每条 top-k 候选填充 `defense_status`：
- 若 critic 给出可用的 `counter_defense` → `defense_status = "defended"`
- 若 critic 的 attack 无法被反驳 → `defense_status = "undefended"`
- 未被 harsh critic 复审的候选 → `defense_status = "not-yet-challenged"`

因此 **`risk_tier = high` 且 `defense_status = "undefended"`** 的论文是最紧急条目，draft 里必须显式应对；而 `risk_tier = high` 且 `defended` 的条目只需在 related work 里简短交代差异。**分数高低与是否 defended 是两个正交维度**——不要相互覆盖。

### Phase 5 — 输出 `COLLISION_REPORT.md`

在**当前工作目录**写入 `COLLISION_REPORT.md`，结构如下:

```markdown
# Collision Report — <draft title>

_Generated by lit-collision on <date>_

## Executive Summary

- Papers screened: N
- Rounds executed: R
- High risk: H · Medium: M · Low: L · Cleared: C
- Undefended high-risk: U (要立即处理)

## Draft Features

- Problem: ...
- Method family: ...
- Key theorems: ...
- Datasets: ...
- Keywords: ...

## High-Risk Collisions

### 1. <Paper title> (venue, year) — score = 0.XX

- Overlap axes: method, theorem
- Evidence: "..."
- Differentiators:
  - ...
- Defense suggestions:
  - ...
- Harsh critic attack: ...
- Counter-defense: ... (or `UNDEFENDED`)

...

## Medium-Risk Collisions

| # | Paper | Venue | Year | Score | Axes | Key differentiator |
|---|---|---|---|---|---|---|
| ... |

## Low-Risk Mentions

- `arXiv:XXXX.XXXXX` — <title> — 0.XX — mention in related work as "recent work on ..."

## Harsh Critic Notes (raw)

<full harsh_critic_notes array, one bullet per target>

## Action Items

1. **Top-3 papers to discuss in related work**: ...
2. **Top-2 claims to sharpen as differentiators**: ...
3. **Optional next step**: run `/multi-model-review` on this report to adversarially validate the risk tiering before finalizing the draft.
```

---

## 输出格式硬性约束

- 所有数学公式使用 LaTeX (`$...$` / `$$...$$`)。严禁 `E[Y(1)-Y(0)]` 这样的纯文本数学。
- 代码/JSON/命令使用英文。
- 解释性散文使用中文 (用户的默认偏好)。
- Report 中引用 evidence 必须是原文 quote，用引号包裹，**不得改写**。

---

## 设计原则 (不可违反)

1. **原子性**: 本 skill 只做碰撞检测。任何扩展都不应让它变成二次综述工具。
2. **无脚本**: 没有 `scripts/` 目录。所有逻辑由 LLM + 已有 skill 组合。
3. **无新服务**: 不引入新 MCP server。
4. **并行强制**: Phase 2 的候选打分必须并行 Task fanout。
5. **防御建议来自控制词表**: `references/collision_taxonomy.md` 的 Defense playbook 是唯一来源。
6. **不自动链调其它 skill**: 本 skill 绝不自动运行 `literature-review` / `research-wiki` / `paper-reader`。`multi-model-review` 仅作为 report 末尾的"可选下游步骤"文字提示，不自动 spawn。

---

## 参考

- `references/collision_taxonomy.md` — 四轴定义、判据、正反例、Defense playbook
