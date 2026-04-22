# Composition rules reference

Four canonical merge modes for rate_table entries. Each lemma in `rate_table.json` must declare its merge_mode and contribution_mode; `compose.py` then deterministically combines parent rates.

## `sequential` (most common)

**Trigger phrase in proof body**: "By Lemma A, ...", "Substituting (X) into (Y)", "plugging in the bound from Lemma A".

**Operation**: multiplicative — exponents add.

$$
\text{rate}_{\text{child}} = \text{rate}_{\text{own}} \cdot \text{rate}_{\text{parent}}
$$

Example: $\|V_m-V_m^*\Omega_m\|_F \lesssim \sqrt K \varepsilon_m / \lambda_{\min}$ where $\varepsilon_m$ comes from upstream concentration. The child adds $\sqrt K / \lambda_{\min}$ on top of the parent's $\sqrt{\log/\underline\mu}$.

## `triangle_sum`

**Trigger**: "$\|X+Y\| \le \|X\| + \|Y\|$", "three-term decomposition", bias + variance + remainder.

**Operation**: pointwise max of parent rates — only the dominant term survives asymptotically.

Example: rowwise error = Bernstein term + transfer term + quadratic remainder. Each has its own rate; the combined rate is whichever dominates in the stated regime.

## `concat_square`

**Trigger**: Frobenius concatenation identity $\|X_{\text{global}}\|_F^2 = \sum_m \|X_m\|_F^2$.

**Operation**: per-entry exponent × 2, then add $M^1$ (one factor of worker count from the sum).

Example: global embedding error from per-worker errors.

## `union_bound`

**Trigger**: "with probability $\ge 1 - N^{-c}$, for all $i$ / for all $m$".

**Operation**: add $+1$ to the `log` exponent (conservative — a $\log N$ factor appears inside concentration bounds whenever a union is taken over $N$ events).

## `contribution_mode` modifier

Orthogonal to merge_mode. Set per entry.

- `absolute` (default): the `rate_dict` of this lemma IS the full composed rate at this step; parents are ignored (the lemma restates / absorbs the upstream bound).
- `delta`: the `rate_dict` is only the NEW factor this step adds on top of upstream; composer must multiply parents in explicitly.

Example: `thm:rowwise-perturbation` — the stated bound already includes $\varepsilon_m$ from upstream, so `contribution_mode: absolute`. In contrast, `thm:subspace-perturbation` says "$\|V_m-V_m^*\Omega_m\|_F \le 2\sqrt K \varepsilon_m / \lambda_{\min}$" where $\varepsilon_m$ is left symbolic — `contribution_mode: delta` with only $\{K: 0.5, \lambda_{\min}: -1\}$ as own_rate.

## How the extractor decides

When Extractor A (statement-only) and Extractor B (proof-body) fill out `rate_dict`:

- If the statement writes the rate with ALL upstream factors inlined (e.g., directly $\log/\sqrt n$ rather than $\varepsilon \cdot$ ...) → mark `contribution_mode: absolute`.
- If the statement has a symbolic upstream variable (like $\varepsilon_m$) → `contribution_mode: delta`, and the own_rate captures only the NEW factor.

The merge_mode is read from the proof body:

- Single `\ref{Lemma X}` substituted into a computation → `sequential`.
- Two or more terms summed with triangle inequality → `triangle_sum`.
- $\|\cdot\|_F^2 = \sum_m \|\cdot\|_F^2$ pattern → `concat_square`.
- "taking union bound over all $m$, all $i$" → `union_bound`.
