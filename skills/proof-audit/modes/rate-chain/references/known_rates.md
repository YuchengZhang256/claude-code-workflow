# Canary rates — ground truth for Phase B.4 self-check

Each section is parseable by `scripts/canary_check.py` via the regex:

```
### <Name>
...
Rate: `<LaTeX>`
Exponents: {JSON dict}
```

The extractor is asked to supply a `rate_dict` for each canary claim. If ≥ 3 fail to match, the skill aborts.

---

### Bernstein Matrix Inequality (symmetric)

The operator norm of a sum of i.i.d. zero-mean bounded random symmetric matrices of size $d\times d$, each bounded by $R$ in operator norm with variance proxy $\sigma^2$, has tail bound $P(\|S\|\ge t) \le 2d\exp(-t^2/(2\sigma^2+Rt/3))$, implying the typical deviation is of order $\sqrt{\sigma^2\log d}+R\log d$.

Rate: `\sqrt{\log d}`
Exponents: {"log": 0.5}

### Davis–Kahan sin Θ theorem

Given symmetric matrices $A, A+E$ with eigengap $\gamma$, the sine of the canonical angle between their top-$k$ subspaces satisfies $\|\sin\Theta\| \le \|E\|/\gamma$.

Rate: `\varepsilon / \lambda_{\min}`
Exponents: {"epsilon": 1, "lambda_min": -1}

### Wedin sin Θ theorem (rectangular)

For rectangular matrices with singular-value gap $\sigma$, $\|\sin\Theta\|\le\|E\|/\sigma$ analogously.

Rate: `\varepsilon / \lambda_{\min}`
Exponents: {"epsilon": 1, "lambda_min": -1}

### Hoeffding concentration (bounded)

Sum of $n$ bounded iid variables of width $b$ deviates from mean by at most $b\sqrt{2\log(2/\delta)/n}$ with probability $1-\delta$.

Rate: `\sqrt{\log / n_m}`
Exponents: {"log": 0.5, "n_m": -0.5}

### Regularized-degree operator concentration (DCSBM)

Under standard degree-floor conditions, the regularized Laplacian operator norm perturbation is $\lesssim \sqrt{\log(N+n_m)/\underline\mu_{\taureg}}$.

Rate: `\sqrt{\log / \underline\mu}`
Exponents: {"log": 0.5, "underline_mu": -0.5}

### Yu–Wang–Samworth sin Θ (Frobenius)

Frobenius-norm version of Davis–Kahan with $\|\sin\Theta\|_F \le \sqrt{2K}\|E\|_F/\gamma$.

Rate: `\sqrt{K} \varepsilon / \lambda_{\min}`
Exponents: {"K": 0.5, "epsilon": 1, "lambda_min": -1}

### Matrix Chernoff (expected)

Sum of independent psd matrices $X_i$ with $\|X_i\|\le R$, $\lambda_{\min}(\mathbb{E}[S])\ge\mu$: $P(\lambda_{\min}(S)\le(1-\delta)\mu)\le d e^{-\delta^2\mu/(2R)}$, giving typical relative deviation $\sqrt{R\log d/\mu}$.

Rate: `\sqrt{\log / \underline\mu}`
Exponents: {"log": 0.5, "underline_mu": -0.5}

### Hanson–Wright (quadratic)

For $X$ sub-Gaussian with parameter $\sigma$ and deterministic $A$: $\|X^\top A X - \mathbb E[X^\top A X]\|$ deviates by $\sigma^2(\|A\|_F\sqrt{\log(1/\delta)}+\|A\|\log(1/\delta))$.

Rate: `\sqrt{\log}`
Exponents: {"log": 0.5}

### Scalar Bernstein (one-sided)

Sum of $n$ iid variables with variance $\sigma^2$ and bound $b$: deviation $\le\sqrt{2\sigma^2\log(1/\delta)/n}+2b\log(1/\delta)/(3n)$.

Rate: `\sqrt{\log / n_m}`
Exponents: {"log": 0.5, "n_m": -0.5}

### Li polar factor stability

For $A$ with $\sigma_{\min}(A)\ge\tau$, the polar factor $\text{polar}(A+E)-\text{polar}(A)$ has Frobenius norm $\le\sqrt 2\|E\|_F/\tau$.

Rate: `\varepsilon / \gamma_{\mathrm{pil}}`
Exponents: {"epsilon": 1, "gamma_pil": -1}

### Weyl singular-value perturbation

$|\sigma_k(A+E)-\sigma_k(A)|\le\|E\|$ for every $k$.

Rate: `\varepsilon`
Exponents: {"epsilon": 1}

### Abbe–Fan–Wang–Zhong rowwise eigenvector (general)

Under incoherence $\mu$ and $d$-row random perturbation, the rowwise $\ell_2$ error of the top-$K$ eigenspace scales as $\mu\sqrt{K/N}\varepsilon/\lambda_{\min}$ plus a second-order remainder $\varepsilon^2/\lambda_{\min}^2$.

Rate: `\mu \sqrt{K/N} \varepsilon / \lambda_{\min}`
Exponents: {"mu": 1, "K": 0.5, "N": -0.5, "epsilon": 1, "lambda_min": -1}

### Incoherence rowwise projector identity

Under $\mu$-incoherence, $\|e_i^\top V^*\|_2\le\mu\sqrt{K/N}$.

Rate: `\mu \sqrt{K/N}`
Exponents: {"mu": 1, "K": 0.5, "N": -0.5}

### Union bound over $N$ events

Taking union of $N$ events of probability $\le N^{-c}$ each gives at most $N^{1-c}$ total failure probability; tightening requires $c>1$ and equivalent to adding one $\log N$ inside each event's concentration bound.

Rate: `\log`
Exponents: {"log": 1}

### Frobenius to operator (square)

$\|X\|_F^2=\sum_i\sigma_i^2(X)$ so $\|X\|_F^2\le K\|X\|^2$ for rank $\le K$.

Rate: `K`
Exponents: {"K": 1}

### Cai–Zhang rectangular perturbation

Frobenius right-singular-vector perturbation for rectangular matrices: $\|W\widetilde O-W^*\|_F\lesssim\sqrt K\,\varepsilon/\gamma$.

Rate: `\sqrt{K} \varepsilon / \lambda_{\min}`
Exponents: {"K": 0.5, "epsilon": 1, "lambda_min": -1}

### Frobenius triangle

$\|X+Y\|_F\le\|X\|_F+\|Y\|_F$ — no rate change, used as merge rule.

Rate: `1`
Exponents: {}

### Operator-to-Frobenius (identity)

$\|X\|\le\|X\|_F$ — no rate change.

Rate: `1`
Exponents: {}

### Cauchy–Schwarz for rate chains

$\|\langle u, Xv\rangle\|\le\|u\|_2\|Xv\|_2$, used to peel off rowwise quantities.

Rate: `1`
Exponents: {}

### Lei–Rinaldo spectral clustering rate

Misclustering rate for spectral clustering in SBM with $K$ communities: $\Mis/N\lesssim K\log N/(N\Delta^2\lambda_{\min}^2)$ in the balanced dense regime.

Rate: `K \log / (N \Delta^2 \lambda_{\min}^2)`
Exponents: {"K": 1, "log": 1, "N": -1, "Delta": -2, "lambda_min": -2}
