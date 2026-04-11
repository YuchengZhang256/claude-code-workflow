# Collision Taxonomy — 四轴碰撞判据与防御手册

本文件为 `lit-collision` 技能的判据手册。主 agent 和 subagent 在执行 Phase 3 打分时应**逐轴**参照本文件的操作性判据，避免主观打分漂移。

所有评分取值区间 $[0, 1]$，四轴加权：

$$
\text{collision\_score} \;=\; 0.4\cdot\text{method\_overlap} \;+\; 0.3\cdot\text{theorem\_overlap} \;+\; 0.2\cdot\text{problem\_overlap} \;+\; 0.1\cdot\text{dataset\_overlap}
$$

---

## 1. Problem Overlap（问题重叠轴）

### 形式化定义

设草稿要回答的科学问题为 $Q_{\text{draft}}$，候选论文的问题为 $Q_{\text{cand}}$。问题重叠度 $\text{problem\_overlap} \in [0,1]$ 衡量两者在**科学目标**层面的同一性，而不是技术层面。

### 操作性判据

判断"是否同一个问题"的证据来源（按证据强度递减）：

1. **输入输出形式**：候选论文的输入数据结构和输出目标量是否与草稿一致？（例：输入都是单个 SBM 图、输出都是社区划分 → 高度重叠）
2. **评价指标**：两篇论文是否用同一类指标衡量成功？（例：都用 misclassification rate、都报 minimax rate）
3. **应用场景表述**：introduction 中的 motivating example 是否覆盖同一个实际领域？
4. **研究问题句式**：摘要或引言中 "we study the problem of ..." 的句子是否可互换？

### 评分锚点

| 分值 | 含义 | 示例 |
|---|---|---|
| 0.9–1.0 | 同一个问题，几乎是 head-to-head | 两篇都做 "SBM 下的 community recovery 的 minimax rate" |
| 0.6–0.8 | 同一个问题族，但有次要维度差 | 草稿做 directed SBM recovery，候选做 undirected SBM recovery |
| 0.3–0.5 | 相关但目标量不同 | 草稿做社区数 $K$ 估计，候选做社区成员划分 |
| 0.0–0.2 | 只是共享关键词，研究目标不同 | 都提到 "community detection"，但一篇是算法、一篇是理论下界 |

### 常见假阳性

- **同词不同问**：两篇都用 "spectral method"，但一篇做 PCA、一篇做 Laplacian clustering —— 关键词重合不代表问题重叠。
- **同域不同问**：同一个数据集（例如 ogbn-products）被用于完全不同的任务（分类 vs. 链接预测）。

---

## 2. Method Overlap（方法重叠轴，权重最高）

### 形式化定义

设草稿方法为算法过程 $\mathcal{A}_{\text{draft}}$，候选方法为 $\mathcal{A}_{\text{cand}}$。方法重叠度衡量两者在**核心算法步骤**上的相似度，而非输入输出相似度。

### 操作性判据

将两篇论文的方法抽象为 pipeline 步骤列表 $(s_1, s_2, \ldots, s_k)$，然后看：

1. **核心算子是否相同**：是否都依赖同一种核心运算？（例：都基于 $\ell_2$ 正则化的最小二乘 + 随机投影）
2. **正则化/损失函数是否同族**：是否都使用同一种 penalty（nuclear norm, group lasso, trace-norm 等）？
3. **更新规则是否相同**：迭代算法的 update step 是否等价或只差 $O(1)$ 常数项改写？
4. **模型假设是否嵌套**：草稿模型是不是候选模型的特例或推广？
5. **关键技巧是否相同**：leave-one-out、data splitting、debiasing、cross-fitting 等核心 trick 是否共用？

### 评分锚点

| 分值 | 含义 | 示例 |
|---|---|---|
| 0.9–1.0 | 方法本质相同，只是换了符号或小的 $O(1)$ 常数 | 都是 spectral clustering + $K$-means on leading eigenvectors |
| 0.6–0.8 | 核心步骤相同，一两个辅助步骤不同 | 都用谱分解，但 post-processing 用不同 rounding |
| 0.3–0.5 | 同一类方法家族，细节差异显著 | 都属于半正定规划松弛，但约束集不同 |
| 0.0–0.2 | 方法家族完全不同 | 草稿用 MCMC、候选用变分近似 |

### 常见假阳性

- **方法名相同但 regime 不同**：都叫 "distributed gradient descent"，但一篇做同步、另一篇做异步且有拜占庭节点——应调低到 0.4 以下。
- **工具通用**：SVD、bootstrap、kernel trick 是通用工具而不是具体方法；只因为共用 SVD 就打高分是错的。

---

## 3. Theorem Overlap（定理重叠轴，权重第二高）

### 形式化定义

令草稿定理集为 $\{T_i^{\text{draft}}\}$，候选定理集为 $\{T_j^{\text{cand}}\}$。定理重叠度衡量**理论结果**层面的贴近度：是否证了同一件事、是否给了同阶的率、是否命中相同的 minimax bound。

### 操作性判据

1. **结论类型匹配**：consistency / rate / minimax lower bound / asymptotic normality —— 两篇的定理是否属于同一种类型？
2. **率的阶数**：若两篇都给出收敛率，$O(n^{-\alpha})$ 中 $\alpha$ 是否相同或同阶？
3. **假设对齐**：两个定理的前提条件是否大致重合？（这里要特别留意：**假设严格更弱也是一种贡献**）
4. **证明技术**：用的是 concentration（Bernstein、matrix Bernstein）、PAC-Bayes、empirical process、Stein 方法中哪一类？相同技术 + 相同结论 = 高度重叠。
5. **minimax 配对**：是否一篇给上界、一篇给下界，并且 bound 匹配？

### 评分锚点

| 分值 | 含义 | 示例 |
|---|---|---|
| 0.9–1.0 | 几乎证了同一个定理：同假设、同率、同技巧 | 两篇都证 $\|\hat\theta-\theta\|_2 = O_p(\sqrt{s\log p/n})$ 且均用 restricted eigenvalue |
| 0.6–0.8 | 同类结论，但率的常数或假设松紧不同 | 都证一致性，草稿允许异方差 |
| 0.3–0.5 | 相似结论类型但不同 regime | 都做 minimax，但一篇 sparse、一篇 dense |
| 0.0–0.2 | 定理类型不同（一篇证下界，一篇给算法保证） | —— |

### 常见假阳性

- **都是 "consistency"**：consistency 是个很弱的标签，两篇论文可能 consistency 的含义（estimation vs. model selection vs. test）完全不同。
- **同一工具，不同应用**：都用 matrix Bernstein inequality，但对象（样本协方差 vs. 图拉普拉斯）完全不同 → 方法工具重叠 ≠ 定理重叠。

---

## 4. Dataset Overlap（数据/实验重叠轴，权重最低）

### 形式化定义

候选论文在实验上与草稿是否使用了相同或高度相似的合成实验/真实数据集。

### 操作性判据

1. **合成实验生成模型**：SBM 参数、Gaussian mixture 参数、scaling 规律是否同类？
2. **真实数据集**：是否共用标准 benchmark（Cora、Citeseer、ogbn-* 系列、IMDb、Yelp 等）？
3. **实验协议**：train/val/test split、评价指标、超参选取方式是否相同？
4. **baseline 集合**：对比的 baseline 列表是否重合？

### 评分锚点

| 分值 | 含义 |
|---|---|
| 0.8–1.0 | 同一个真实数据集 + 同样的 split + 同样的指标 |
| 0.5–0.7 | 同类合成实验或同 benchmark 但评价方式不同 |
| 0.2–0.4 | 只共享一个标准 benchmark，其他完全不同 |
| 0.0–0.1 | 数据完全没有交集 |

### 常见假阳性

- **"都用了 MNIST"**：MNIST、CIFAR-10 这样的通用 benchmark 几乎所有论文都会顺手跑，不应视为实质性重叠；除非两篇论文的核心贡献就是 MNIST/CIFAR 上的实验。

---

## 5. 全局常见假阳性清单

跨轴的经验陷阱，subagent 打分时应逐条自检：

1. **关键词同名陷阱**：NLP 里的 "attention" 和统计里的 "attention weight" 完全是两个概念。
2. **方法族同名陷阱**：rand matrix 里的 "spectral method" 和 graph ML 里的 "spectral method" 差异极大。
3. **定理标签陷阱**：两篇都说 "minimax optimal"，但一篇是 local minimax、一篇是 global minimax。
4. **相同 benchmark 陷阱**：共用 benchmark 不等于相同研究。
5. **同作者稀释偏差**：同一作者连发多篇类似工作时，往往每篇只在一两个维度上有差异——打分应严格，不要被"名气"影响。
6. **综述假阳性**：survey / review 论文在关键词上与技术论文高度重叠，但它们**不能 scoop 你**，应降权或直接剔除。

---

## 6. 防御 Playbook — 被哪种轴碰到就用哪种反击

本节按"被碰到的主轴"组织，每种情形提供 3–5 个标准差异化动作。subagent 在 `defense_suggestions` 字段里引用本节条目。

### 6.1 当 `method_overlap` 高时

1. **更严假设的松动**：证明你的方法在候选要求的假设更弱的情形下仍然 work（例如去掉 sub-Gaussian、允许 heavy-tail）。
2. **新 regime**：把方法迁移到候选未覆盖的参数区间（high-dimensional vs. classical；稀疏 vs. 稠密；大 $K$ vs. 小 $K$）。
3. **复杂度差异**：证明你的算法在 time 或 communication 复杂度上严格更优（需要定理支持）。
4. **在线/分布式改造**：把候选的 offline/集中式方法改造成 online 或 distributed 版本，并证明同样的率。
5. **去掉 tuning parameter**：提供 parameter-free 版本并证明 adaptive rate。

### 6.2 当 `theorem_overlap` 高时

1. **更紧的率**：把 $O(n^{-1/2})$ 改进到 $O(n^{-1/2}(\log n)^{-1/2})$ 或匹配 minimax 下界。
2. **匹配的下界**：如果候选只给了上界，补一个 minimax 下界，说明率无法改进。
3. **去 log 因子**：消除原结果中的 polylog 因子。
4. **放宽条件**：去掉 RIP/incoherence 等苛刻条件，改用更现实的条件（restricted eigenvalue、compatibility）。
5. **新结论类型**：在同一方法上给出 asymptotic normality（而候选只证 consistency），为 CI 构造打开大门。

### 6.3 当 `problem_overlap` 高时

1. **新 identification strategy**：同一问题，用全新识别假设（IV → negative control → proximal 方法）。
2. **目标量升级**：从 ATE 升级到 HTE / CATE；从 community recovery 升级到 changepoint-in-community。
3. **新失败模式**：指出候选方法在某 regime 下会 fail，并证明你的方法在该 regime 下仍 consistent。
4. **多任务联合**：把原问题嵌入到多任务/迁移学习框架中。
5. **可计算性**：证明候选方法不可多项式时间求解、而你的方法可以。

### 6.4 当 `dataset_overlap` 高时

1. **超越 benchmark**：引入候选未使用的更难数据集（更大规模、更高噪声、真实世界 corruption）。
2. **stress test**：在候选使用的数据集上做 ablation / robustness / adversarial 分析。
3. **新协议**：在相同数据上提出更严格的评价协议（leave-one-domain-out、temporal split）。
4. **理论驱动的合成实验**：设计能区分"方法本质差异"的合成实验，而不是重复 benchmark。

### 6.5 通用（score 高但你确信自己有本质贡献）

- 在 introduction 开头就**显式点出**与 top-1 碰撞论文的差异（"Unlike [X], we ..."），不要藏到 related work 后半段。
- 在 main theorem 旁加一个 "Comparison to [X]" 小段或表格。
- 在 related work 章节为每篇 high-risk 论文给**一句话 differentiator**。
- 把 harsh critic 阶段发现的"最难反驳的攻击线"提前放进 discussion/limitation 章节，主动讨论而非被审稿人揪出。
