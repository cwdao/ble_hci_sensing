# BLE CS 呼吸检测 — 工作周报

> **周期**：2026-06-05 → 2026-06-08 | **提交**：`c3c1728` → `2fb16d5` | **日期**：2026-06-09

## 摘要

从 BLE CS 72 tone × 3 变量中提取呼吸信号。方法路线：**PCA 全局融合（~10.92%，失败）→ Per-Tone 投票（9.20%，范式转变）→ 逐模态 Voting + 三模态等权谱融合（8.45%，当前最优）**。核心机制发现：**Voting 系统性地降低模态间频谱差异性，使等权融合优于选择性融合**——这一非直观效应解释了本阶段最重要的正负结果（B1 Equal > B3 Top2）。

![演进时间线](../../outputs/figures/method_evolution_timeline.png)

**图 1**：方法演进。从 P0 到 P2 跨域 mean 降低 2.47pp。

---

## 主线一：PCA/SVD — 失败的尝试

**思路**：受 Wi-Fi CSI 文献启发，用 PCA 从 72 信道提取"共同呼吸波形"，期望第一主成分分离呼吸信号与多径噪声。

**数据矩阵** $\mathbf{X} \in \mathbb{R}^{M \times N}$（$M$ 帧，$N$ 信道），z-score 标准化后构造协方差矩阵 $\mathbf{C} = \frac{1}{M-1}\mathbf{Z}^T\mathbf{Z}$，取第一特征向量对应的 PC1 作为呼吸波形。三模态各自 PCA 后 η 加权谱融合 → BPM。

**结果**：PCA-Modal3 跨域 **~10.92%**，未超越 Modal top2（9.45%），甚至不如 Single Remote（10.45%）。

![PCA PC1 方差占比](../../outputs/figures/pca_svd_pc1_variance_ratio.png)

**图 2**：PC1 方差占比集中在 0.3–0.6，说明呼吸并非数据方差的压倒性主导成分——多径噪声同样贡献了高方差。

**失败原因**：信道间噪声（ICI）是相关的 → PCA 将相关噪声也纳入主成分。这直接催生了下一阶段。

---

## 主线二：Per-Tone 投票 — 范式转变

**灵感**：Deng et al. (2024) — 传统加权求和假设噪声独立，但 OFDM 中 ICI 强相关。替代方案：每 tone **独立估计 BPM，再统计投票**。

**算法**：每窗内，对 72 tone 各自做 FFT 寻峰得到 $\{\text{BPM}_i\}$，以 $\eta_i \cdot \rho_i$ 为权重做直方图投票：

$$\text{BPM}_{\text{voted}} = c_{k^*}, \quad k^* = \arg\max_k \sum_{i: \text{BPM}_i \in \text{bin}_k} \eta_i \cdot \rho_i$$

### 阶段一：纯 Voting 验证

T0-V3（η·ρ 加权投票，仅 remote）跨域 **9.20%**，首次超越 Modal top2（9.45%），验证了"先估计再投票 > 先融合再估计"。

### 阶段二：信道×模态 系统性融合

将 Voting 从单模态扩展为 per-modal + 模态融合，填充 4×4 策略网格。**逐模态 Voting → 三模态等权谱融合（B1）跨域 8.45%**，首次突破 8.5%。

![全阶段排行榜](../../outputs/figures/method_evolution_full_leaderboard.png)

**图 3**：主线 8 方法排行榜。B1（绿色 P2）以 8.45% 登顶。关键负结果：B3 Voting→Top2（9.92%）系统性差于 B1。

---

## ⭐ 核心机制发现：Voting 改变模态间关系

**问题**：为什么 Voting 下 Equal（8.45%）优于 Top2（9.92%），而 Single-best 下 Top2（9.45%）反而优于 Equal（10.50%）？

**诊断方法**：每窗计算三模态归一化呼吸带功率谱的两两余弦相似度。

> **"谱"是什么 & 两重澄清**：
> 1. 被比较的谱 = 某时间波形的 FFT 功率谱（呼吸带内归一化）。Vote 谱 = 72 tone 各自 FFT → η·ρ 加权平均；Single-best 谱 = 被选 max-η tone 的 FFT。后者**有谱**——任何波形 FFT 即谱。
> 2. Voting 在本项目中有**两种用法**：① BPM 投票（T0-V3：72 tone 各投一个 BPM → 直方图 → 一个数字，无谱）；② 谱加权融合（B1/B3：72 tone 各自 FFT → 加权平均谱 → 再寻峰，有谱）。D1 诊断比较的是第②种——因 B1/B3 需要 per-modal 谱做模态融合。
> 3. **Voting 谱 vs PCA**：都做多信道加权，但 PCA 在时域操作、权重 = 方差最大方向（噪声也能高方差）；Voting 在频域操作、权重 = η·ρ（直接衡量呼吸信号质量）。这解释了 Voting 有效而 PCA 失败。

| 场景 | Voting 路径 | Single-best 路径 |
|------|:----------:|:---------------:|
| 091339 | **0.864** | 0.772 |
| 095806 | **0.991** | 0.930 |
| 102621 | **0.959** | 0.885 |

![D1 模态频谱相似度](../../outputs/figures/b1_diag_spectral_similarity.png)

**图 4**：三场景合并直方图。🟢 Voting 路径（olive）整体偏右——模态间频谱高度一致；🔵 Single-best 路径（steelblue）偏左——模态间更分化。

**物理机制**：三种模态的 Vote 谱都聚合同一组 tone index（0–71）。同一 tone index 在三种模态下经历相同多径 → 好 tone 在三种模态间高度一致 → 三个 Vote 谱被同一组好 tone 主导 → 天然趋同。Single-best 相反：remote 选 tone 37，local 可能选 tone 52——不同物理信道 → 谱天然分化。

**更精确的结论**：

> D1 只与**谱加权融合**（B1/B3）有关，与 BPM 投票（T0-V3）无关——后者坍缩为单个 BPM 数字，没有谱可供比较。模态间高相似度不是被"发现"的神秘效应，而是**谱加权融合的结构性必然**：三种模态都在平均同一组 72 tone 的 FFT 谱 → 天然趋同 → Equal 模态融合最合理。真正的 insight：**保留完整谱信息（B1: 8.45%）优于坍缩为 BPM 再投票（T0-V3: 9.20%）**。

**证明边界**：图 4 解释 Equal > Top2，不证明 Voting > Single-best。后者证据是独立的 BPM 数字（T0-V3 9.20% < Single 10.45%）。

---

## 下一步

| 方向 | 内容 |
|------|------|
| 多径诊断 | 091339 退化根因（>12%），已排除双峰性和 η 质量假设 |
| 泛化验证 | B1 仅在金属板三场景下验证，需新场景 |
| 论文复现 | 谐波抑制、投票阈值 τ 调优、有监督信道筛选 |

---

## 产出清单

| 类型 | 路径 |
|------|------|
| 综合报告 | `docs/achievements/pca_voting_comprehensive_achievement_report.md` |
| 图表脚本 | `notebooks/scripts/chFusion_achievement_figures.py`、`src/ble_analysis/achievement_figures.py` |
| 新增图表 | `method_evolution_timeline.png`、`method_evolution_full_leaderboard.png`、`pca_svd_*.png` 等 |
