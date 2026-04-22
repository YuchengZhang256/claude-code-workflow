## Section A — Stepwise algebraic walk

**Op-Concentration [C10].**  
起点就是 C10 的输入输出本身：  
$$
\varepsilon_m:=\|L_{\tau,m}-L_{\tau,m}^*\|_{\mathrm{op}}
\lesssim
\sqrt{\frac{\log(N+n_m)}{\underline\mu_\tau}}.
$$
这一项直接送入下一阶段，所以进入 Subspace-Pert 的输入率是
$$
\varepsilon_m \lesssim \sqrt{\frac{\log(N+n_m)}{\underline\mu_\tau}}.
$$

**Subspace-Pert [C11].**  
输入率是上一阶段的
$$
\varepsilon_m \lesssim \sqrt{\frac{\log(N+n_m)}{\underline\mu_\tau}}.
$$
这一阶段新插入的因子是
$$
\frac{\sqrt K}{\lambda_{\min}}.
$$
逐项相乘：
$$
\|V_m-V_m^*\Omega_m\|_F
\lesssim
\frac{\sqrt K}{\lambda_{\min}}\varepsilon_m
\lesssim
\frac{\sqrt K}{\lambda_{\min}}
\sqrt{\frac{\log(N+n_m)}{\underline\mu_\tau}}.
$$
所以进入 Rowwise-Pert 的子空间率是
$$
\|V_m-V_m^*\Omega_m\|_F
\lesssim
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\sqrt{\underline\mu_\tau}}.
$$

**Rowwise-Pert(Step4) [C12, C13].**  
这一阶段从上一阶段继承子空间率
$$
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\sqrt{\underline\mu_\tau}},
$$
同时新插入一个 LOO 耦合尺度
$$
\frac{\sqrt K}{\lambda_{\min}\sqrt{\underline\mu_\tau}}.
$$
这里没有新的对数幂，也没有新的 $\underline\mu_\tau$ 之外的乘法；因此进入 Procrustes(Step5) 时携带的是两类量：
$$
\text{子空间主项 } \frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\sqrt{\underline\mu_\tau}},
\qquad
\text{LOO 耦合项 } \frac{\sqrt K}{\lambda_{\min}\sqrt{\underline\mu_\tau}}.
$$

**Procrustes(Step5) [C15, C16, C17].**  
输入率包括上一阶段的
$$
\varepsilon_m \lesssim \sqrt{\frac{\log(N+n_m)}{\underline\mu_\tau}},
\qquad
\frac{1}{\lambda_{\min}\sqrt{\underline\mu_\tau}}
$$
型 LOO/Procrustes 接近项。  
这一阶段新插入三项：

第一项，Bernstein 分支：
$$
\mu\sqrt{\frac{K}{N}}\cdot \frac{\varepsilon_m}{\lambda_{\min}}
=
\mu\sqrt{\frac{K}{N}}\cdot
\frac{1}{\lambda_{\min}}
\sqrt{\frac{\log(N+n_m)}{\underline\mu_\tau}}.
$$

第二项，二次余项：
$$
\frac{\varepsilon_m^2}{\lambda_{\min}^2}
=
\frac{1}{\lambda_{\min}^2}
\cdot
\frac{\log(N+n_m)}{\underline\mu_\tau}.
$$

第三项，LOO-Procrustes 接近项：
$$
\frac{1}{\lambda_{\min}\sqrt{\underline\mu_\tau}}.
$$

把这些显式加起来，进入 Sample-Degree(Step6) 的量可以写成
$$
\mu\sqrt{\frac{K}{N}}
\frac{\sqrt{\log(N+n_m)/\underline\mu_\tau}}{\lambda_{\min}}
\;+\;
\frac{\log(N+n_m)}{\lambda_{\min}^2\underline\mu_\tau}
$$
以及一个单独继续携带的 LOO 尺度
$$
\frac{1}{\lambda_{\min}\sqrt{\underline\mu_\tau}}.
$$

**Sample-Degree(Step6) [C18, C19, C20, C21, C22, C23].**  
输入率是上一步的 Step5 行级项
$$
\mu\sqrt{\frac{K}{N}}
\frac{\sqrt{\log(N+n_m)/\underline\mu_\tau}}{\lambda_{\min}}
+
\frac{\log(N+n_m)}{\lambda_{\min}^2\underline\mu_\tau},
$$
外加保留下来的
$$
\frac{1}{\lambda_{\min}\sqrt{\underline\mu_\tau}}
$$
型 sample-LOO 尺度。  
这一阶段新插入两项：

第一项，额外 transfer 分支：
$$
\frac{\sqrt{\log(N+n_m)}}{\lambda_{\min}\underline\mu_\tau}.
$$

第二项，新的二次项：
$$
\frac{(\varepsilon_m+\widetilde\varepsilon_m)^2}{\lambda_{\min}^2}.
$$
由表末摘要，$\varepsilon_m,\widetilde\varepsilon_m$ 都是
$$
\lesssim \sqrt{\frac{\log(N+n_m)}{\underline\mu_\tau}},
$$
所以
$$
\frac{(\varepsilon_m+\widetilde\varepsilon_m)^2}{\lambda_{\min}^2}
\lesssim
\frac{\log(N+n_m)}{\lambda_{\min}^2\underline\mu_\tau}.
$$

把旧项与新项相加，进入 Weighted-Procrustes 之前的行级误差就是
$$
\mu\sqrt{\frac{K}{N}}
\frac{\sqrt{\log(N+n_m)/\underline\mu_\tau}}{\lambda_{\min}}
\;+\;
\frac{\sqrt{\log(N+n_m)}}{\lambda_{\min}\underline\mu_\tau}
\;+\;
\frac{\log(N+n_m)}{\lambda_{\min}^2\underline\mu_\tau},
$$
同时 sample-LOO 尺度仍是
$$
\frac{1}{\lambda_{\min}\sqrt{\underline\mu_\tau}}.
$$

**Weighted-Procrustes(Step7-8) [C24, C25].**  
按 DAG，C25 的上游是 C11、C09、C24，而不是 Step5/Step6 的行级链，所以这里输入的是 C11 的子空间误差
$$
\frac{\sqrt K}{\lambda_{\min}}\varepsilon_m
\lesssim
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\sqrt{\underline\mu_\tau}},
$$
再加上 C24 的权重扰动 $\delta_{W,m}$。  
这一阶段新插入的 covariance 扰动是
$$
\|\widehat C_m-\bar C_m^*\|_F
\lesssim
\omega_{\max}\sqrt K\,\frac{\varepsilon_m}{\lambda_{\min}}
+
\omega_{\max}\sqrt K\,\frac{\varepsilon_a}{\lambda_{\min}}
+
\sqrt K\,\delta_{W,m}.
$$
把
$$
\varepsilon_m,\varepsilon_a \lesssim \sqrt{\frac{\log(N+n_m)}{\underline\mu_\tau}}
$$
代入，得到
$$
\|\widehat C_m-\bar C_m^*\|_F
\lesssim
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\sqrt{\underline\mu_\tau}}
+
\sqrt K\,\delta_{W,m}.
$$
再除以 $\gamma_{\mathrm{pil}}l$，旋转误差变成
$$
\|O_m-\bar Q_m^*\|_F
\lesssim
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\gamma_{\mathrm{pil}}l\sqrt{\underline\mu_\tau}}
+
\frac{\sqrt K\,\delta_{W,m}}{\gamma_{\mathrm{pil}}l}.
$$
所以进入 Global-Embedding 的对齐项是上式。

**Global-Embedding [C26, C27].**  
输入有两部分：  
第一部分是 C26 的 slice 子空间项
$$
\frac{\sqrt K}{\lambda_{\min}}\varepsilon_m
\lesssim
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\sqrt{\underline\mu_\tau}}.
$$
第二部分是上一阶段得到的对齐项
$$
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\gamma_{\mathrm{pil}}l\sqrt{\underline\mu_\tau}}
+
\frac{\sqrt K\,\delta_{W,m}}{\gamma_{\mathrm{pil}}l}.
$$
所以每个 worker 的 slice 误差先相加为
$$
\|\Psi_m-\Psi_m^*\|_F
\lesssim
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\sqrt{\underline\mu_\tau}}
+
\frac{\sqrt{K\log(N+n_m)}}{\lambda_{\min}\gamma_{\mathrm{pil}}l\sqrt{\underline\mu_\tau}}
+
\frac{\sqrt K\,\delta_{W,m}}{\gamma_{\mathrm{pil}}l}.
$$
然后按 C27 对各 slice 平方并求和。逐项平方后，进入 Misclustering 的全局 Frobenius 量级是
$$
\sum_{m=1}^M
\left[
\frac{K\log(N+n_m)}{\lambda_{\min}^2\underline\mu_\tau}
+
\frac{K\log(N+n_m)}{\lambda_{\min}^2\gamma_{\mathrm{pil}}^2l^2\underline\mu_\tau}
+
\frac{K\delta_{W,m}^2}{\gamma_{\mathrm{pil}}^2l^2}
\right]
$$
忽略交叉项与常数后，可写成
$$
M\left[
\frac{K\log(N+n_{\max})}{\lambda_{\min}^2\underline\mu_\tau}
+
\frac{K\log(N+n_{\max})}{\lambda_{\min}^2\gamma_{\mathrm{pil}}^2l^2\underline\mu_\tau}
+
\frac{K\delta_W^2}{\gamma_{\mathrm{pil}}^2l^2}
\right].
$$

**Misclustering [C28, C29, C30, C31].**  
输入是上一阶段的全局 Frobenius 误差。  
这一阶段新插入两个纯乘法因子：row-normalization 给
$$
\frac{16}{c_{\mathrm{row}}^2},
$$
nearest-centroid 给
$$
\frac{4}{N\Delta^2}.
$$
把它们乘到上一阶段结果上：
$$
\frac{|\Mis|}{N}
\lesssim
\frac{1}{N\Delta^2c_{\mathrm{row}}^2}
\cdot
M\left[
\frac{K\log(N+n_{\max})}{\lambda_{\min}^2\underline\mu_\tau}
+
\frac{K\log(N+n_{\max})}{\lambda_{\min}^2\gamma_{\mathrm{pil}}^2l^2\underline\mu_\tau}
+
\frac{K\delta_W^2}{\gamma_{\mathrm{pil}}^2l^2}
\right].
$$
这就是沿着
$$
\text{C10}\to\text{C11}\to\text{C12,C13}\to\text{C15,C16,C17}\to\text{C18--C23}\to\text{C24,C25}\to\text{C26,C27}\to\text{C28--C31}
$$
逐步代数合成后得到的 walked composition。

## Section B — Comparison with thm:misclustering (C30) + cor:explicit-rate (C31)

C30 只给通用 misclustering 机制：先用 C27 的全局 Frobenius 误差，再乘上 C29 的 row-normalization 因子与最近中心分类因子，所以它本身不额外改动任何 $\log,\underline\mu_\tau,K,C_P,N,M,\lambda_{\min},\gamma_{\mathrm{pil}},l,\Delta,c_{\mathrm{row}},\delta_W$ 指数。就这一层而言，walked composition 与 C30 一致。

C31 在 `CLAIM_DAG.md` 中给出的 stated rate 是：
$$
\frac{|\Mis|}{N}
\lesssim
\frac{MK\log(N+n_{\max})}{N\Delta^2 c_{\mathrm{row}}^2\lambda_{\min}^2\underline\mu_\tau}
+
\frac{M\bigl(K\log(N+n_{\max})/\underline\mu_\tau+\delta_W^2\bigr)}{N\Delta^2 c_{\mathrm{row}}^2\gamma_{\mathrm{pil}}^2l^2}.
$$

把它与上面的 walked composition 逐项对比：

第一项
$$
\frac{MK\log(N+n_{\max})}{N\Delta^2 c_{\mathrm{row}}^2\lambda_{\min}^2\underline\mu_\tau}
$$
完全一致。这里的 $\log$ 幂、$\underline\mu_\tau$ 幂、$K$、$M$、$N$、$\lambda_{\min}$、$\Delta$、$c_{\mathrm{row}}$ 都匹配。

第二项的对数分支，walked composition 给出的是
$$
\frac{MK\log(N+n_{\max})}{N\Delta^2 c_{\mathrm{row}}^2\lambda_{\min}^2\gamma_{\mathrm{pil}}^2l^2\underline\mu_\tau},
$$
而 C31 写的是
$$
\frac{MK\log(N+n_{\max})}{N\Delta^2 c_{\mathrm{row}}^2\gamma_{\mathrm{pil}}^2l^2\underline\mu_\tau}.
$$
差别在于 walked composition 里保留了 $\lambda_{\min}^{-2}$，C31 则没有。按 DAG，C25 只依赖 C11、C09、C24；而 C11 的输入就是 $\varepsilon_m/\lambda_{\min}$ 型子空间误差。若只按表末 rate-chain 与 DAG 机械合成，没有任何中间一步会把这个 $\lambda_{\min}^{-2}$ 消掉，所以这是一个超出常数因子的差异。

第二项的权重扰动分支，walked composition 给出的是
$$
\frac{MK\delta_W^2}{N\Delta^2 c_{\mathrm{row}}^2\gamma_{\mathrm{pil}}^2l^2},
$$
而 C31 写的是
$$
\frac{M\delta_W^2}{N\Delta^2 c_{\mathrm{row}}^2\gamma_{\mathrm{pil}}^2l^2}.
$$
差别在于 walked composition 保留了一个 $K$。原因同样来自表末的 Weighted-Procrustes 行：C25 的 covariance 扰动写的是 $\sqrt K\,\delta_{W,m}$，平方进 C27 后自然变成 $K\delta_W^2$。只按这张表做代数，不存在去掉这个 $K$ 的步骤，所以这也是一个超出常数因子的差异。

其余变量方面：$C_P$ 列在 rate-chain summary 中全程是 $0$，而 `SYMBOL_LEDGER.md` 已明确说明 theorem chain 之外才出现 `rem:theory-vs-experiment` 的 $C_P^2$，因此这里不能也不应对 C31 提出任何 $C_P$ 的 chain break。$\gamma_{\mathrm{pil}},l,\Delta,c_{\mathrm{row}},M,N$ 的指数在 walked composition 与 C31 中一致。

```json
[
  {
    "claim_id": "C31",
    "type": "chain_break",
    "discrepancy_variable": "\\lambda_{\\min}",
    "walked_exponent": "-2 on the alignment-log branch",
    "stated_exponent": "0 on the alignment-log branch",
    "severity": 5,
    "confidence": 0.92,
    "explanation": "Using only the rate-chain table and the DAG, the alignment branch comes from C25 <- C11, C09, C24. The C11 input already carries a factor $\\lambda_{\\min}^{-1}$ through $\\sqrt K\\,\\varepsilon_m/\\lambda_{\\min}$, and the C25 row writes the covariance perturbation as another $\\sqrt K\\,\\varepsilon/\\lambda_{\\min}$-type term before dividing by $\\gamma_{\\mathrm{pil}}l$. Squaring in C27 therefore leaves a $\\lambda_{\\min}^{-2}$ factor in the alignment-log contribution. No row in the supplied chain summary removes that factor, so the stated C31 rate is strictly smaller than the mechanically composed chain by a non-constant power of $\\lambda_{\\min}$.",
    "fix": "Either tighten the C25 weighted-Procrustes input so that its log branch is shown to avoid the $\\lambda_{\\min}^{-1}$ loss, or relax the C31 explicit-rate statement to include a factor $\\lambda_{\\min}^{-2}$ in the $(K\\log/\\underline\\mu_\\tau)/(\\gamma_{\\mathrm{pil}}^2 l^2)$ branch."
  },
  {
    "claim_id": "C31",
    "type": "chain_break",
    "discrepancy_variable": "K on the \\delta_W branch",
    "walked_exponent": "+1",
    "stated_exponent": "0",
    "severity": 5,
    "confidence": 0.88,
    "explanation": "The Weighted-Procrustes row in the rate-chain summary inserts a covariance perturbation term $\\sqrt K\\,\\delta_{W,m}$. After division by $\\gamma_{\\mathrm{pil}}l$ and squaring in C27, the walked composition produces $K\\delta_W^2/(\\gamma_{\\mathrm{pil}}^2 l^2)$. The stated C31 bound keeps only $\\delta_W^2/(\\gamma_{\\mathrm{pil}}^2 l^2)$, with no compensating cancellation step anywhere in the DAG row sequence. Therefore the explicit-rate statement is better than the walked chain by one full power of $K$ on the weight-perturbation branch.",
    "fix": "Either tighten C25/C24 so that the weight perturbation enters covariance control without the displayed $\\sqrt K$ factor, or relax C31 so that the weight branch reads $K\\delta_W^2/(\\gamma_{\\mathrm{pil}}^2 l^2)$."
  }
]
```
