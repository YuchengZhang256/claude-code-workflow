# Common Proof Gaps — 概率/统计证明中的典型漏洞清单

本清单是 `proof-audit` 技能三个 persona 在审计时的参考 checklist。每条格式：**描述** + **如何补丁**。LaTeX 片段为可直接复用的模板。

---

## 1. 可测性与 σ-代数

1. **Supremum over uncountable index 未论证可测** — 在不可数指标集上取 $\sup_{t\in[0,1]} X_t$ 直接当作随机变量，未说明 separability 或 path continuity。**Patch**: 加 "by separability of $(X_t)$, $\sup_t X_t$ is measurable"。

2. **Conditional expectation 未指定 σ-代数** — 写 $\mathbb{E}[Y \mid X]$ 但未声明 conditioning σ-algebra $\sigma(X)$。**Patch**: 明确 $\mathbb{E}[Y \mid \mathcal{F}]$，$\mathcal{F} := \sigma(X)$。

3. **Filtration 不递增** — 定义 $\mathcal{F}_t$ 但没说明 $\mathcal{F}_s \subseteq \mathcal{F}_t$ for $s \le t$。**Patch**: 加 "$(\mathcal{F}_t)_{t\ge 0}$ is a filtration" 一句。

4. **Stopping time 未验证** — 把某个随机时刻 $\tau$ 当 stopping time 用，但没验 $\{\tau \le t\} \in \mathcal{F}_t$。**Patch**: 单独一句论证；若是 hitting time，引用 début theorem。

5. **Borel 可测性被默认** — 对 Polish space 上的函数默认 Borel 可测。**Patch**: 注明连续函数 $\Rightarrow$ Borel 可测。

6. **Image of measurable set 被当作可测** — forgetting that measurable images require analytic-set machinery。**Patch**: 限制在可数 / injective 情形或引用 Lusin。

7. **Almost sure 等号被当作处处等号** — 把 "$X = Y$ a.s." 当成 "$X(\omega) = Y(\omega)$" 用在逐点极限里。**Patch**: 显式处理零测集。

---

## 2. 极限交换（Fubini/Tonelli/DCT/MCT）

8. **DCT 无 dominating function** — 交换 $\lim$ 与 $\mathbb{E}$ 未给 $|f_n| \le g$, $\mathbb{E}[g]<\infty$。**Patch**:
```latex
By Assumption ..., $|f_n(X)| \le g(X)$ with $\mathbb{E}[g(X)] < \infty$;
hence DCT yields $\lim_n \mathbb{E}[f_n] = \mathbb{E}[\lim_n f_n]$.
```

9. **MCT 单调性未验证** — 用单调收敛定理但没说序列单调。**Patch**: 明确 $f_n \uparrow f$ 或 $f_n \ge 0$ 且 $\uparrow$。

10. **Fubini 未验证可积** — 交换积分次序前没验 $\iint |f| \, d\mu \, d\nu < \infty$。**Patch**: Tonelli 先给 $|f|$ 有限，再引用 Fubini。

11. **Uniform integrability 缺失** — 从 $X_n \xrightarrow{P} X$ 直接跳到 $\mathbb{E}[X_n] \to \mathbb{E}[X]$，未验 UI。**Patch**: 加 $\sup_n \mathbb{E}[|X_n|^{1+\delta}] < \infty$。

12. **Sum/integral 交换** — $\sum_n \int f_n = \int \sum_n f_n$ 未论证 (Fubini for counting measure)。**Patch**: 引用 Tonelli for $|f_n| \ge 0$。

13. **Limit 与 derivative 交换** — $\frac{d}{d\theta}\mathbb{E}[f(X,\theta)] = \mathbb{E}[\partial_\theta f]$ 无 regularity。**Patch**: 显式 Leibniz rule 条件（local dominating function）。

14. **Limit 与 $\sup$ 交换** — $\lim_n \sup_\theta = \sup_\theta \lim_n$ 通常**错误**。**Patch**: 改用 uniform convergence 或 Glivenko–Cantelli 型论证。

---

## 3. iid / 平稳性未声明

15. **"Sample $X_1, \dots, X_n$" 未指 iid** — 不写 iid 就用 SLLN。**Patch**: 声明 $X_i \overset{\text{iid}}{\sim} P$。

16. **隐式独立** — 用 $\mathbb{E}[XY] = \mathbb{E}[X]\mathbb{E}[Y]$ 但未声明 $X \perp Y$。**Patch**: 声明独立或替换为 covariance 形式。

17. **平稳性未声明** — 时间序列证明里把 $\mathbb{E}[X_t]$ 当常数。**Patch**: 加 "strictly/weakly stationary"。

18. **Mixing condition 缺失** — 对非 iid 序列用 CLT 但未验 $\alpha$-mixing / $\beta$-mixing。**Patch**: 加 mixing rate 条件并引用 Rosenblatt/Ibragimov。

19. **Exchangeability 被当作 iid** — 两者不同，de Finetti 只在无限序列上给 conditional iid。**Patch**: 显式说明是 finite exchangeability 还是 infinite。

---

## 4. Concentration inequality 常数

20. **Hoeffding 常数写错** — $\exp(-2t^2/\sum(b_i-a_i)^2)$ 漏 2 或漏平方。**Patch**: 抄 Boucheron–Lugosi–Massart 原文。

21. **常数随维度爆炸未提醒** — Bernstein / Talagrand 的 $\sigma^2$ 其实依赖 $d$。**Patch**: 把常数显式写成 $C(d)$ 并给 scaling。

22. **Sub-Gaussian / sub-exponential 参数未定义** — 直接用 $\|\cdot\|_{\psi_2}$ 而不给定义。**Patch**: 在 notation 块定义 Orlicz norm。

23. **Union bound 过松** — 对 $p$ 个事件 union bound 失去 log 因子。**Patch**: 明示 $p$ 与 $n$ 的 scaling 条件 $\log p = o(n)$。

24. **McDiarmid bounded-difference 未验证** — 用 McDiarmid 但没验 $c_i$ 常数。**Patch**: 显式计算 $c_i$。

---

## 5. Regularity 条件缺失

25. **连续性未声明** — 用 Portmanteau / continuous mapping 但未说 $g$ 连续。**Patch**: 加 "$g$ continuous a.s. w.r.t. $P$"。

26. **可微性未声明** — Taylor 展开用到 $\nabla^2 f$ 但未假设 $C^2$。**Patch**: 加 "$f \in C^2$ in a neighborhood of $\theta_0$"。

27. **有界性未声明** — 用 bounded convergence 但未给 $\|f\|_\infty < \infty$。**Patch**: 加有界假设或改 dominating。

28. **Lipschitz 常数 implicit** — 写 "$|f(x)-f(y)| \lesssim |x-y|$" 但未声明 Lipschitz。**Patch**: 显式 $\|f\|_{\text{Lip}} \le L$。

29. **Identifiability 未声明** — $M$-estimator 的 argmin 唯一性未证。**Patch**: 加 identifiability assumption 或唯一性 lemma。

30. **Compactness 缺失** — 用 Heine–Borel 式论证 argmax 存在但未声明紧集。**Patch**: 声明 $\Theta$ compact。

---

## 6. Asymptotic regime 次序

31. **$n\to\infty$ 与 $d\to\infty$ 次序未指定** — high-dim 统计的 iterated limit vs joint limit。**Patch**: 明示 $n,d\to\infty$ with $d/n \to \gamma$ 或明确 iterated 次序。

32. **$n\to\infty$, $h\to 0$ 次序** — nonparametric regression 的 bandwidth 与样本量联动。**Patch**: 给 $nh^d \to \infty$ 或具体联动条件。

33. **Double limit 与 single limit 混用** — $\lim_n \lim_k$ 与 $\lim_k \lim_n$ 交换需 uniform。**Patch**: Moore–Osgood 或直接改 joint $n=k$。

---

## 7. 隐式独立性

34. **Cross-fitting 折次之间独立被默认** — double ML 里两折的 nuisance 估计被当 independent of test fold，但 random split 需声明。**Patch**: 声明 "independent of $(X_i, Y_i)_{i \in \mathcal{I}_k}$ by sample splitting"。

35. **Bootstrap 重抽样独立性** — bootstrap sample 对原样本的 conditional independence 未写。**Patch**: 明说 "conditional on $\mathcal{D}_n$"。

36. **$X$ 与 noise 独立被默认** — regression 里 $\varepsilon \perp X$ 未写。**Patch**: 加到 Assumption block。

---

## 8. 符号重用 / scope collision

37. **$C$ 随行变化** — "$\le C \cdot x$" 中 $C$ 每行不同但不声明。**Patch**: 文首加 "$C$ denotes a constant that may change from line to line"。

38. **$n$ 既是样本量又是维度** — 同一符号双重含义。**Patch**: 换 $d$ 或 $p$。

39. **$\theta$ 与 $\theta_0$ 混用** — true parameter 与 generic parameter 符号冲突。**Patch**: 统一 $\theta_0$ for truth, $\theta$ for argument。

40. **$\mathbb{P}$ 与 $\mathbb{P}_n$ 混用** — population vs empirical measure。**Patch**: notation block 明确区分。

---

## 9. Tail bound 松紧度

41. **Polynomial tail 被当 exponential tail 用** — $P(|X|>t) \le t^{-k}$ 给不出 sub-Gaussian 结论。**Patch**: 改用 Markov / Chebyshev 的 matching bound。

42. **Gaussian tail 的常数错误** — $P(Z>t) \le e^{-t^2/2}$ 正确，$e^{-t^2}$ 错。**Patch**: 对照 Mills ratio。

43. **Median vs mean 混用** — 集中不等式里 median 和 mean 差一个常数。**Patch**: 引用 Ledoux 的 median-mean bound。

---

## 10. 边界情形

44. **$n=1$ trivial case** — sample variance 定义在 $n=1$ 时分母为 0。**Patch**: 假设 $n \ge 2$。

45. **退化分布** — 证明里默认 $\text{Var}(X)>0$，未处理 constant $X$。**Patch**: 明说 non-degenerate 或分情况。

46. **零概率事件** — 条件概率 $P(A\mid B)$ 在 $P(B)=0$ 时未定义。**Patch**: 声明 $P(B)>0$ 或改用 regular conditional probability。

47. **空集 / 边界参数** — argmin 在 $\partial\Theta$ 时 Taylor 展开失败。**Patch**: 假设 interior point 或处理 boundary case。

48. **离散与连续混用** — 同一证明里 $\int f \, dP$ 同时覆盖离散和连续，但 density 只在连续时存在。**Patch**: 统一用 Radon–Nikodym 导数 $dP/d\mu$，$\mu$ 为 dominating measure。

---

## 11. 依赖结构

49. **Martingale difference 未验证** — $\mathbb{E}[\xi_t \mid \mathcal{F}_{t-1}] = 0$ 未显式验证。**Patch**: 单独一句验证。

50. **Mixing rate 未给定** — "weakly dependent" 含糊说法。**Patch**: 显式 $\alpha$-mixing with rate $\alpha(k) = O(k^{-\beta})$。

51. **Markov chain 遍历性未验证** — 用 ergodic theorem 但未验 irreducible + aperiodic。**Patch**: 引用具体 ergodicity theorem (Meyn–Tweedie)。

52. **Clustered data 被当 iid** — 分组/面板数据的组内相关性被忽略。**Patch**: 声明 cluster-level independence 并调整方差估计。

---

## 使用建议

- **Pedantic persona** 重点看 1–2、8、25–30、37–40、42。
- **Adversarial persona** 重点看 14、21、31–33、44–48。
- **Generous persona** 重点看 15–19、26–29、34–36、49–52，给出最小充分条件。
