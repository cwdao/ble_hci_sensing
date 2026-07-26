# Phase 独特角色发掘与自适应融合 — 实现计划

> **来源**：`modal_quality_gating` 实验结论 + `paper_ablation_draft_align` 消融矩阵  
> **目标报告**：`docs/reports/phase_unique_role_adaptive_fusion_report.md`  
> **日期**：2026-07-26  
> **验证状态**：待实现

---

## 1. 动机与背景

| 项目 | 说明 |
|------|------|
| **问题** | 质量加权融合（E3d=0.384）优于等权（0.405）但未超越 Remote-only（0.376），CS 上等权仍最优（10.14%）。质量指标（η/ρ）与"谁给出正确 BPM"的相关性仅 ~64%，模态级质量加权路线已触及上限。核心问题转变为：**Phase 有没有幅值模态无法替代的独特作用？如果有，自适应策略如何利用它？** |
| **相关实验** | `modal_quality_gating` 两轮（E1 oracle + E2 指标评估 + E3 质量加权 + E4 Phase 门控）、`paper_ablation_draft_align` HKH 消融矩阵 |
| **本 plan 定位** | 不继续在 η/ρ 加权路线上做增量优化；转向**发现 Phase 的独特物理价值**并围绕它设计**自适应融合策略**——利用"幅值更稳定、相位噪声更多但位移线性"的先验，让每窗数据自己决定 Phase 是否参与 |

### Phase 可能有什么独特作用？（研究假设）

回顾 BLE CS 的物理机制，Phase 至少在四个维度上可能具有幅值不可替代的价值：

| # | 假设 | 物理直觉 | 可检验 |
|---|------|----------|--------|
| **H1** | **零陷填充（Null-Filling）** | Phase ∝ 位移（线性响应），幅值 ∝ 干涉图样（非线性）。在 Remote 和 Local 同时落入多径零陷的窗口，幅值对微小胸部位移不敏感（dA/dd ≈ 0），Phase 仍保持灵敏度（dφ/dd = 4π/λ）。Phase 的唯一作用：**在幅值双双失明时提供唯一可用信号** | E1 |
| **H2** | **波形保真度** | 呼吸非正弦（吸/呼不对称），Phase 线性保形，幅值非线性畸变。即使 Phase BPM 不准，其波形形状可能更接近真实呼吸——这对波形输出管线有独立价值 | E1 |
| **H3** | **跨模态分集** | Remote / Local 测量在不同设备端、经不同信道——三个模态构成对同一物理位移的三条独立观测路径。Phase 不是"劣化版幅值"，而是不同投影——在某些多径配置下可能是唯一正确投影 | E1 |
| **H4** | **谱峰一致性作为直接质量信号** | η/ρ 是间接质量代理（BPM 正确性关联 ~64%）。直接用三模态 BPM 的一致性判断 Phase 可信度——Phase 峰与 R+L 共识一致 → 高质量窗口；偏离 → 低质量窗口 | E2 |

如果 H1 成立，整个故事就自圆其说了：**Phase 的独特角色是"零陷救援"——幅值模态在多数窗口更稳定（默认使用），Phase 在幅值失效的少数窗口提供唯一可用信号（条件激活）。** 这个叙事既有物理深度（多径零陷 + 位移线性），又有工程价值（自适应融合超越纯幅值上限）。

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 单端 PCT 幅值，噪声低，多径干涉非线性响应 |
| `local_amplitudes` | ✅ | 同上，物理对等 |
| `phases`（总相位） | ✅（条件使用） | 位移线性响应（φ ∝ d），但含两端噪声之和；在幅值零陷窗口有不可替代价值 |
| `amplitudes`（总幅值） | ❌ | 双方噪声乘积，无独立物理意义（已有定论） |

### 2.2 Phase 的物理特性：为什么线性响应重要

BLE CS 的 Phase 来自两端 PCT 向量相乘后取相位：

$$\Phi_i(t) = \angle\left(Z_{l,i}(t) \cdot Z_{r,i}(t)\right)$$

在单一路径主导（或存在稳定直达径）的条件下，Φ 与反射体位移 Δd 的关系为：

$$\Delta\Phi = \frac{4\pi}{\lambda}\Delta d \quad (\lambda \approx 12.5\text{ cm at }2.4\text{ GHz})$$

胸部位移 ~1 cm → ΔΦ ≈ 1 rad，远高于相位噪声。**关键特性**：

- **线性响应**：ΔΦ ∝ Δd，不依赖多径干涉的具体形态
- **无零陷**：不存在 "dΦ/dd = 0" 的工作点（不考虑 2π 缠绕时）
- **双端噪声**：Var[Φ] ≈ Var[∠Z_l] + Var[∠Z_r]，是幅值模态的两倍

相比之下，幅值 A = |Σ α_i exp(jφ_i)| 是非线性的：

- 在干涉峰值处 dA/dd ≈ 0（对位移最不敏感）
- 在干涉零点附近 dA/dd 最大（但对噪声也最敏感）
- **存在零陷**：特定多径配置下，呼吸频段的幅值响应可能几乎为零

**Phase 与幅值的互补关系并非"一个好一个差"，而是"线性 vs 非线性"+"高噪声 vs 低噪声"的 trade-off。在幅值的非线性导致失效时（零陷），Phase 的线性是唯一选择——代价是承受更高的噪声。**

### 2.3 符号约定

| 符号 | 含义 |
|------|------|
| η_m | 模态 m 融合波形的呼吸频段能量比 |
| ρ_m | 模态 m 融合波形的谱峰峰度 |
| BPM_m | 模态 m 的 Voting BPM 估计 |
| Δ(BPM_m, BPM_n) | 两模态 BPM 的绝对差（breaths/min） |
| q_null | 幅值零陷指标：Remote 和 Local 同时低 η 或低 ρ |
| consensus(BPM_R, BPM_L, BPM_P) | 三模态 BPM 一致性度量 |
| N_best(w) | 窗 w 的 oracle 最优模态（来自 GT） |

---

## 3. 算法与实验步骤

本 plan 包含 **五个实验模块（E1–E5）**。E1 是核心诊断（检验 H1–H3），E2–E3 是算法方案，E4 是信道侧诊断，E5 是跨域对比。

### 整体流程图

```text
E1: Phase Unique Role Discovery（核心诊断）
  │
  ├─► E1a: 零陷填充检验
  │     在 Phase oracle-best 窗口中，Remote 和 Local 是否双双低 η？
  │     定义 Null Score = min(η_R, η_L) / max(η_R, η_L, η_P)
  │     Null Score 低 → R+L 双低 → Phase 填零陷
  │
  ├─► E1b: 波形保真度检验
  │     Phase oracle-best 窗 vs Remote oracle-best 窗
  │     波形与 GT（呼吸带）的相关系数是否 Phase > Remote？
  │
  ├─► E1c: 跨模态分集检验
  │     三模态 pairwise BPM error correlation
  │     若 corr(err_R, err_P) 低 → Phase 提供独立信息
  │
  ▼
E2: Spectral Peak Consensus Gating（方向 1：BPM 一致性门控）
  │
  ├─► 替代 η/ρ 质量代理，直接用三模态 Voting BPM 的一致性判断 Phase 可信度
  │     若 |BPM_P - BPM_RL| ≤ 1 BPM → Phase 参与等权融合
  │     若 |BPM_P - BPM_RL| > 1 BPM → Phase 排除（退化为 R+L 等权）
  │     其中 BPM_RL = Remote+Local 等权融合的 BPM
  │
  ├─► 变体：严格共识 / 多数投票 / 加权共识
  │
  ▼
E3: R+L Default + Phase Conditional Activation（方向 2：双模态默认 + Phase 条件激活）
  │
  ├─► 默认策略：Remote + Local 等权双模态融合
  │     Phase 激活条件（满足任一即激活）：
  │       C1 (零陷): q_null < threshold → 幅值可能双双失明
  │       C2 (共识): |BPM_P - BPM_RL| ≤ 1 BPM → Phase 与幅值一致
  │       C3 (质量): η_P > median(η_R, η_L) → Phase 质量不低于幅值中位数
  │
  ├─► Phase 激活后权重：
  │       等权 R:L:P = 1:1:1（共识强时）
  │       或 R:L:P = 1:1:α（α 由共识度/零陷度决定）
  │
  ├─► 变体矩阵：C1/C2/C3 的 and/or 组合 × 激活后权重策略
  │
  ▼
E4: Channel-vs-Modal Metric Asymmetry（方向 3：信道侧 vs 模态侧指标不对称诊断）
  │
  ├─► 已知：η·ρ 在信道级（per-tone 选择）优于 η-only；但 η-only 在模态级 hit rate 更高
  │     诊断：信道级 η·ρ > η-only 是因为 ρ 在 72 tone 中有效压制了"峰尖但频率错"的 tone？
  │           模态级 η-only > η·ρ 是因为 3 模态尺度下 ρ 过拟合窗口噪声？
  │
  ├─► 检查 per-tone ρ 的分布特性 vs per-modal ρ 的分布特性
  │     在信道 Voting 中 ρ 的作用机制是什么？
  │
  ▼
E5: Cross-Domain Phase Degradation Diagnosis（方向 4：Phase 跨域差异根因）
  │
  ├─► HKH vs CS：Phase 为什么在真人数据和金属板数据上表现截然不同？
  │     对比：η/ρ/BPM error 分布 / Phase-best 窗特征 / 人体微动 vs 机械振动
  │
  ├─► 可能原因：人体微动引入相位抖动 / 呼吸带波形非正弦性 / 多径环境差异
  │
  ▼
综合：输出推荐的自适应策略 + Phase 独特价值证据
```

---

### 3.1 E1: Phase 独特价值发现（核心诊断）

**目的**：检验 H1（零陷填充）、H2（波形保真度）、H3（跨模态分集）。

**输入**：复用 `outputs/reports/modal_oracle_per_window.npy`（已有，含每窗三模态 BPM、η、ρ、oracle 标签），需补充 CS 域数据（如尚未包含）。

#### E1a: 零陷填充检验（H1）

```text
对每个窗口 w：
  1. 计算 Null Score(w) = min(η_R(w), η_L(w)) / max(η_R(w), η_L(w), η_P(w))
     含义：Remote 和 Local 中较差者 vs 三模态最优者的比值
     Null Score → 0 表示 R 和 L 都弱（可能的零陷状态）
     Null Score → 1 表示三模态 η 相近

  2. 按 oracle 最优模态分组：
     Group A: N_best = Phase (105 窗 HKH, 63 窗 CS)
     Group B: N_best = Remote (1549 窗 HKH, 310 窗 CS)
     Group C: N_best = Local (76 窗 HKH, 64 窗 CS)

  3. 比较 Null Score 在各组的分布：
     H1 预测：Group A 的 Null Score 显著低于 Group B/C
     → 若成立：Phase 确实在 R+L 双双低 η 时承担零陷填充角色

  4. 额外检验：在 Group A 中，检查 η_R 和 η_L 是否都低于各自全域中位数
     → "双低"比例应显著 > 50%
```

**产出图表**：
- Null Score 按 oracle 最优模态分组的小提琴图/箱线图（HKH / CS 分面）
- Phase-best 窗的 (η_R, η_L) 二维散点图 vs Remote-best 窗
- 零陷检测率：不同 Null Score 阈值下 Phase-best 窗的召回率

#### E1b: 波形保真度检验（H2）

```text
仅适用于 HKH（有呼吸带 GT 波形）：
  在 Phase oracle-best 窗口和 Remote oracle-best 窗口中：
    1. 提取各模态的 Hilbert 融合波形（复用 B3 pipeline）
    2. 计算波形与呼吸带 GT 的 Pearson 相关系数
    3. 比较 Phase-best 窗 vs Remote-best 窗的相关系数分布
  
  H2 预测：Phase-best 窗的波形-GT 相关系数不劣于（甚至优于）Remote-best 窗
  → 若成立：即使 Phase BPM 全局差，其在它擅长的窗口上波形质量也不差
```

**产出图表**：
- Phase-best vs Remote-best 窗的波形-GT 相关系数直方图
- 典型窗口的波形叠加对比图（Phase / Remote / Local / GT 四线）

#### E1c: 跨模态分集检验（H3）

```text
计算三模态 pairwise BPM error 的 Spearman 秩相关：
  corr(|BPM_R - GT|, |BPM_P - GT|)
  corr(|BPM_L - GT|, |BPM_P - GT|)
  corr(|BPM_R - GT|, |BPM_L - GT|)

H3 预测：
  - R-L 误差正相关（两者都是幅值模态，共享多径失效模式）
  - R-P 误差相关性弱（Phase 失效模式与幅值不同）
  → 若成立：Phase 提供与幅值正交的失效模式，融合有 diversity 增益潜力

额外检验：
  在 R 和 L 同时大误差（> median error）的窗口中：
    Phase 误差是否显著低于 R/L？
  → 若成立：Phase 在幅值双双失效时确实更优（与 H1 互补）
```

**产出图表**：
- 三模态 pairwise BPM error 散点图矩阵 + 相关系数标注
- R+L 双高误差窗中 Phase 误差的分布

---

### 3.2 E2: 谱峰一致性门控（方向 1）

**目的**：用直接 BPM 一致性替代 η/ρ 间接质量代理。检验 H4。

**核心逻辑**：

```text
对每个窗口 w：
  1. 计算三模态各自的 Voting BPM（复用现有 estimate_b3_window）
     得到 BPM_R(w), BPM_L(w), BPM_P(w)
  
  2. 计算 R+L 等权融合 BPM：
     S_RL(f) = 0.5 × S_R(f) + 0.5 × S_L(f)
     BPM_RL = argmax S_RL(f)
  
  3. 谱峰一致性判定：
     Δ_P = |BPM_P(w) - BPM_RL(w)|
     
     若 Δ_P ≤ θ_consensus（建议扫描 θ ∈ {0.5, 1.0, 1.5, 2.0} BPM）：
       → Phase 参与：S_final = (S_R + S_L + S_P) / 3  （等权三模态）
     否则：
       → Phase 排除：S_final = (S_R + S_L) / 2          （等权双模态）
  
  4. BPM_final = argmax S_final(f) over 呼吸频段
```

**变体矩阵**：

| Key | 描述 | 门控逻辑 |
|-----|------|----------|
| `e2_consensus_hard_T` | Hard consensus gate | Δ_P ≤ T → Equal 三模态; else → R+L 等权 |
| `e2_consensus_soft_T` | Soft consensus gate | w_P ∝ exp(−Δ_P² / T²)，R+L 始终等权 |
| `e2_majority` | 三模态多数投票 | 两两 Δ ≤ T 的对数 ≥ 2 → 全部等权; else → R+L |
| `e2_nearest_pair` | 最近对共识 | 找 BPM 最接近的一对：若含 Phase → Phase 参与；否则 → R+L |

**Baseline**：
- `draft_s_full` (Equal 三模态 = BreatheCS): HKH 0.405, CS 10.14%
- `draft_s_channel` (Channel-only): HKH 0.381, CS 12.51%
- `draft_ms_remote` (Remote-only): HKH 0.376, CS 11.23%
- R+L 等权双模态 (新增 baseline，E3 也需要): [待实验]

**与 E4 (Phase 门控) 的关键区别**：
- E4 用 η·ρ 数值判断 Phase 质量（间接代理，hit rate ~64%）
- E2 用 BPM 输出一致性判断 Phase 可信度（直接测量输出空间）
- **预测**：E2 应优于 E4，因为 η·ρ 与"BPM 正确性"的相关性仅有 ~64%

---

### 3.3 E3: R+L 默认 + Phase 条件激活（方向 2）

**目的**：利用"幅值更稳定"的先验设计默认双模态策略，Phase 在检测到有利条件时激活。

**核心逻辑**：

```text
默认策略（所有窗口）：
  S_default(f) = 0.5 × S_R(f) + 0.5 × S_L(f)   （Remote + Local 等权）
  BPM_default = argmax S_default(f)

Phase 激活条件（满足任一即触发）：
  
  C1 (零陷检测):
    η_R(w) < median(η_R) AND η_L(w) < median(η_L)
    → 幅值可能双双在零陷 → Phase 激活
  
  C2 (BPM 共识):
    |BPM_P(w) - BPM_default(w)| ≤ θ_c2  (建议 θ_c2 = 1.0 BPM)
    → Phase 与 R+L 共识一致 → Phase 激活
  
  C3 (Phase 自身质量):
    η_P(w) > median(η_R(w), η_L(w))
    → Phase 在当前窗不比幅值差 → Phase 激活

激活后融合：
  若仅 C2 满足（共识强，但零陷不显著）：
    S_final = (S_R + S_L + S_P) / 3        → 等权三模态
  若 C1 满足（零陷）：
    S_final = (S_R + S_L) / 3 + S_P / 1.5  → Phase 升权（因其是唯一可用信号）
    即 w_R:w_L:w_P = 1:1:1.5
  若 C3 满足但不满足 C1/C2：
    S_final = (S_R + S_L) / 2.5 + S_P / 5  → Phase 小权重试探
    即 w_R:w_L:w_P = 1:1:0.5
```

**变体矩阵**：

| Key | 描述 | 激活条件 | Phase 权重 |
|-----|------|----------|-----------|
| `e3_default` | R+L 等权（无 Phase） | 从不 | w_P = 0 |
| `e3_c2_only` | 共识激活 | C2 (Δ ≤ 1.0 BPM) | 1:1:1 |
| `e3_c1_or_c2` | 零陷或共识激活 | C1 OR C2 | C1→1:1:1.5, C2→1:1:1 |
| `e3_c1_c2_and` | 零陷且共识激活 | C1 AND C2 | 1:1:1.5 |
| `e3_full_adaptive` | 全条件自适应 | C1/C2/C3 组合 | 动态权重 |

**预测**：
- `e3_default`（无 Phase）应在 HKH 上接近 Remote-only（0.376），CS 上需验证
- `e3_c2_only` 应在 CS 上有增益（CS Phase 与 R+L 共识好）、HKH 上不退化（共识差时不引入 Phase）
- `e3_c1_or_c2` 可能是最优平衡

---

### 3.4 E4: 信道侧 vs 模态侧指标不对称诊断（方向 3）

**目的**：理解为什么 η·ρ 在信道级有效但在模态级不如 η-only，为信道融合改进提供依据。

**已知事实**：
- CS 金属板信道级（per-tone 选择）：η·ρ > η-only（Plan2 阶段结论）
- HKH 模态级（per-modal 选择）：η-only hit 63.6% > η·ρ hit 54.3%（E2 结论）

**诊断步骤**：

```text
D4a: Per-tone ρ 的噪声特性
  在单窗内，72 tone 各自的 ρ 分布：
    - 高 ρ tone 是否集中在正确的呼吸频率附近？
    - 还是 ρ 高只是因为 tone 的噪声谱恰好有一个窄峰（但不一定在呼吸频率）？
  方法：对每个 tone，比较其 argmax 频率 vs GT BPM
  
D4b: ρ 在信道 Voting 中的作用机制
  当前 Voting = η·ρ 加权直方图：
    - 分别用 η-only 和 η·ρ 做 Voting，比较 winning BPM 的准确性
    - 检查：η·ρ 是否通过压低"噪声 tone 但峰值尖锐"的假峰来提升 Voting？
    - 这在本项目的信道 Voting 中是否确实发生？
  
D4c: 模态级 ρ 为何失效
  模态级只有 3 个候选 vs 信道级 72 个候选：
    - ρ 在 3 模态中的方差小（三模态谱都已经过 Voting → 噪声 tone 已被抑制）
    - 模态级 ρ 的差异主要反映窗口间的随机波动，而非真实的模态质量差异
    - 对比：per-tone ρ 反映了 72 个信道的真实质量差异（尚未融合）
```

**产出图表**：
- Per-tone ρ vs per-modal ρ 的分布对比
- η-only Voting vs η·ρ Voting 的 winning BPM 准确性散点图
- 信道级 hit rate 对比：η vs η·ρ（复用已有单窗 per-tone 数据）

**预期发现**：
- 信道级：ρ 压低假峰 tone 的贡献是真实的（72 tone 中存在噪声 tone）
- 模态级：Voting 已消除大部分噪声 tone，3 模态的 ρ 差异不反映真实质量差异
- **启示**：不需要改信道融合，但模态融合不应再用 ρ

---

### 3.5 E5: Phase 跨域差异根因诊断（方向 4）

**目的**：理解 Phase 为什么在 HKH（真人）崩溃但在 CS（金属板）表现正常。

**假设池**：

| 假设 | 物理机制 | 可检验预测 |
|------|----------|-----------|
| H5a: 人体微动 | HKH 被试身体微小移动引入宽带相位噪声，金属板无此问题 | HKH Phase η 方差 > CS Phase η 方差 |
| H5b: 呼吸非正弦性 | 真人呼吸波形与正弦差异大，Phase 线性保形 → 频域能量分散到谐波 | HKH Phase ρ < CS Phase ρ（峰不够尖） |
| H5c: 多径复杂度 | HKH 房间多径更复杂 → Phase 的 tone 间一致性更差 | HKH Phase Voting confidence < CS Phase Voting confidence |
| H5d: 采样/滤波差异 | HKH 数据采样率或滤波参数有差异 | 检查原始数据时间戳间隔 |

**诊断步骤**：

```text
D5a: Per-window Phase 质量分布对比
  对比 HKH vs CS 的：
    - η_P 分布（直方图 + 统计量）
    - ρ_P 分布
    - Voting confidence 分布
    - Phase argmax 频率 vs GT 的误差分布
  找出 HKH Phase 差的主要表现维度

D5b: Phase-best 窗的共同特征
  分别在 HKH 和 CS 中，Phase oracle-best 的窗口：
    - η_R, η_L 的分布 → H1 零陷假设的跨域一致性
    - 窗口所在的 subject/scenario → 是否有特定的 subject 或 room 驱动？
    - 窗口在时间轴上的聚集性 → 是否集中在特定时间段？
  
D5c: 人体微动指标
  若有加速度计或陀螺仪数据：[待确认]
  若无：用 Remote/Local 幅值的总功率波动作为微动代理
    → 检查微动代理与 Phase BPM error 的相关性
```

**产出图表**：
- HKH vs CS Phase η/ρ/BPM error 分布对比（三面板）
- Phase-best 窗的 subject/scenario 分布热力图
- Phase 误差 vs 幅值功率波动散点图

---

## 4. Baseline 对比

执行 Agent 必须跑齐以下方法。**新 baseline：R+L 等权双模态（`e3_default`）**，是 E2/E3 的默认策略对照。

### 4.1 已有方法（复用既有结果）

| 方法 Key | 描述性名称 | HKH BPM | CS rel% | 来源 |
|----------|-----------|--------:|--------:|------|
| `draft_s_full` | 逐模态 Voting → 三模态等权融合（BreatheCS） | 0.405 | 10.14% | 已有 |
| `draft_s_channel` | Voting → 三选一最优模态 | 0.381 | 12.51% | 已有 |
| `draft_ms_remote` | Remote 单模态 Voting | 0.376 | 11.23% | 已有 |
| `draft_ms_local` | Local 单模态 Voting | 0.378 | 16.21% | 已有 |
| `draft_ms_phase` | Phase 单模态 Voting | 2.191 | 10.92% | 已有 |
| `e3d` | η·ρ·conf 加权融合（当前最优质量加权） | 0.384 | 11.29% | 已有 |
| `e3a` | η 加权融合 | 0.396 | 10.17% | 已有 |

### 4.2 新增方法（本 plan 待实现）

| 方法 Key | 描述性名称 | 所属实验 | 说明 |
|----------|-----------|----------|------|
| `e3_default` | **R+L 等权双模态融合** | E3 baseline | Remote + Local 等权谱平均，Phase 不参与 |
| `e2_consensus_hard_1.0` | **谱峰一致性硬门控（Δ≤1 BPM）** | E2 | BPM 共识→三模态等权；分歧→R+L 等权 |
| `e2_consensus_soft_1.0` | **谱峰一致性软门控（σ=1 BPM）** | E2 | w_P ∝ exp(−Δ²) |
| `e2_nearest_pair` | **最近对共识门控** | E2 | 找最近 BPM 对，含 Phase 则 Phase 参与 |
| `e3_c2_only` | **Phase 共识激活** | E3 | 仅 C2（Δ≤1 BPM）控制 Phase 是否参与 |
| `e3_c1_or_c2` | **零陷或共识激活** | E3 | C1 (双低 η) OR C2 (共识) → Phase 激活 |
| `e3_full_adaptive` | **全条件自适应** | E3 | C1/C2/C3 联合决定 Phase 权重 |

### 4.3 预期相对关系（研究假设）

| 对比 | 预期 | 理由 |
|------|------|------|
| `e3_default` vs `draft_ms_remote` | HKH: 接近（~0.377）；CS: 待验证 | R+L 均值应接近二者中的优者 |
| `e2_consensus_hard` vs `draft_s_full` | HKH: 优于 Equal (0.405)；CS: 接近 Equal (10.14%) | HKH: Phase 多数被排除 → ∼R+L; CS: Phase 多数参与 → ∼Equal |
| `e2_consensus_hard` vs `e3d` (0.384) | 可能持平或略优 | BPM 一致性比 η·ρ 更直接 |
| `e3_c1_or_c2` vs `e3_default` | HKH: 相当；CS: 优于 | C2 在 CS 上高触发率，C1 安全网 |
| `e3_full_adaptive` vs 所有 | 未知 | 取决于各条件的触发率和准确性 |
| E1 H1 (零陷) | 应成立 | 物理上 Phase 在零陷中唯一可用 |
| E4 诊断 | η·ρ 在信道级>η-only 真实, 模态级 ρ 失效因样本太少 | 已有数据强烈暗示 |

---

## 5. 评估设计

### 5.1 场景

| 数据 | 场景 | 用途 | 备注 |
|------|------|------|------|
| **HKH 真人** | 3 Room × 4 Subject = 12 条 | 主评估 + E1b 波形诊断 + E5 对比 | 呼吸带 GT；BPM abs err (breaths/min) |
| **CS 金属板** | `cs_091339` / `cs_095806` / `cs_102621` | 跨域对照 + E5 对比 | 机械振动 GT；BPM rel err % |

> ⚠️ **HKH 和 CS 结果必须分表/分图**，不可合并跨域 mean。

### 5.2 指标

| 指标 | 适用域 | 说明 |
|------|--------|------|
| BPM 绝对误差 mean ± std | HKH | breaths/min，主指标 |
| BPM 相对误差 % mean ± std | CS | %，主指标 |
| Phase 排除率 | 两者 | E2/E3 中 Phase 被排除的窗占比 |
| 共识窗占比 | 两者 | Δ(BPM_P, BPM_RL) ≤ 1 BPM 的窗占比 |
| E1 Null Score | 两者 | 诊断指标 |
| 波形-GT 相关系数 | HKH | E1b 波形保真度 |

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | E2/E3 至少一个变体在 HKH 上 BPM ≤ 0.384（不劣于 E3d）；E1 至少一项 Phase 独特价值假设被验证 |
| **理想** | E2/E3 至少一个变体在 HKH 上 BPM ≤ 0.381（不劣于 channel-only）**且** CS 上不显著退化（≤ 11%）；E1 零陷填充（H1）被验证，为 Phase 的独特角色提供物理依据 |
| **突破** | E2/E3 在 HKH 上 BPM ≤ 0.376（持平或超越 Remote-only）——自适应策略超越了纯单模态天花板 |
| **失败** | 所有 E2/E3 变体在 HKH 上劣于 E3d (0.384)，或 E1 全部假设被推翻 |

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 | 操作 |
|------|------|------|
| E1 诊断脚本 | `notebooks/scripts/chFusion_phase_unique_role_diag.py` | **新建** |
| E2/E3 实验脚本 | `notebooks/scripts/chFusion_phase_adaptive_fusion.py` | **新建** |
| E4/E5 诊断 | 合入 E1 脚本或在 E2/E3 脚本中追加 | **新建/扩展** |
| 模态融合 | `src/ble_analysis/systematic_fusion.py` | **扩展**：新增 `weight_mode="consensus_gate"` + `"adaptive_dual_default"` |
| B3 Pipeline | `src/ble_analysis/b3_pipeline.py` | **扩展**：`DRAFT_ABLATION_SPECS` 追加 E2/E3 变体 |
| Gating 逻辑 | `src/ble_analysis/phase_adaptive_gating.py` | **新建**：E2 共识门控 + E3 自适应激活逻辑 |

### 6.2 复用 API

```python
# 已有，直接复用
from ble_analysis.b3_pipeline import (
    DRAFT_ABLATION_SPECS,         # 扩展追加 E2/E3 变体
    estimate_b3_window,            # 单窗 BPM + 波形估计
    validate_b3_variant_against_hkh,  # HKH 评估
)
from ble_analysis.systematic_fusion import (
    modal_fusion_from_spectra,    # 扩展 weight_mode
    per_modal_voting_spectrum,    # 逐模态 Voting 谱
)
from ble_analysis.chfusion import (
    ChFusionConfig,
    load_multichannel_for_scenario,
)

# E1 诊断复用已有的 per-window oracle 数据
import numpy as np
oracle_data = np.load("outputs/reports/modal_oracle_per_window.npy", allow_pickle=True)
```

### 6.3 新增函数签名建议

```python
# === E2: 谱峰一致性门控 ===

def compute_modal_bpm_consensus(
    bpm_remote: float, bpm_local: float, bpm_phase: float,
    consensus_threshold: float = 1.0
) -> dict:
    """
    计算三模态 BPM 一致性指标。
    
    Returns:
        {
            "delta_p_rl": |BPM_P - BPM_RL|,
            "delta_r_l": |BPM_R - BPM_L|,
            "consensus": True if delta_p_rl <= threshold,
            "nearest_pair": ("remote", "local") or ("remote", "phase") or ("local", "phase"),
            "phase_included": bool,
        }
    """
    ...

def consensus_gated_fusion(
    spectra_by_var: dict,
    consensus_info: dict,
    gate_mode: str = "hard",  # "hard" | "soft"
) -> np.ndarray:
    """根据共识信息融合三模态谱。"""
    ...

# === E3: R+L 默认 + Phase 条件激活 ===

def detect_amplitude_null(
    eta_remote: float, eta_local: float,
    eta_remote_global_median: float, eta_local_global_median: float,
) -> bool:
    """检测 Remote 和 Local 是否同时处于疑似零陷状态。"""
    return eta_remote < eta_remote_global_median and eta_local < eta_local_global_median

def adaptive_phase_activation(
    spectra_by_var: dict,
    bpm_by_var: dict,
    eta_by_var: dict,
    activation_conditions: list[str],  # ["null", "consensus", "quality"]
    consensus_threshold: float = 1.0,
) -> tuple[np.ndarray, dict]:
    """
    R+L 默认融合 + Phase 条件激活。
    
    Returns:
        fused_spectrum, activation_log
    """
    ...
```

### 6.4 窗口级 BPM 一致性门控的实现路径

E2 的核心修改点在 `estimate_b3_window()`。当前流程：

```text
当前（等权）:
  Voting per modal → S_R, S_L, S_P → modal_fusion_from_spectra(weight_mode="equal")
  
E2 修改后:
  Voting per modal → S_R, S_L, S_P, BPM_R, BPM_L, BPM_P
  → compute_modal_bpm_consensus()
  → if consensus:
      modal_fusion_from_spectra(weight_mode="equal")  # 三模态
    else:
      modal_fusion_from_spectra(
        weight_mode="custom",
        custom_weights={"remote": 0.5, "local": 0.5, "phase": 0.0}
      )  # R+L 等权
```

**注意**：E2 门控需要 BPM_RL（R+L 等权融合的 BPM），而 BPM_RL 本身需要先做一次 R+L 等权融合。这引入了一个鸡生蛋问题——不过可以在门控内部先算 BPM_RL，再根据门控结果算最终融合。实际操作中，BPM_RL 可以直接从 S_R 和 S_L 等权平均谱的 argmax 得到，不依赖 Phase。

### 6.5 不做的事

- 不修改原始数据、GT、滤波参数
- 不引入新的外部方法（如 VMD, PCA）
- 不修改 Voting 信道融合逻辑（E4 仅做诊断，不产出新方法变体）
- 不在本 plan 中修改波形分支（B2-D MRC）
- 不新建场景 JSON

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| **E1 诊断图** | `outputs/figures/phase_role_null_score_by_oracle.png`、`phase_role_waveform_fidelity.png`、`phase_role_cross_modal_correlation.png` |
| **E1 诊断数据** | `outputs/reports/phase_unique_role_diag.json` |
| **E2/E3 HKH 结果** | `outputs/reports/phase_adaptive_fusion_hkh_summary.json` |
| **E2/E3 CS 结果** | `outputs/reports/phase_adaptive_fusion_cs_summary.json` |
| **E2/E3 排行榜图** | `outputs/figures/phase_adaptive_fusion_hkh_leaderboard.png`、`phase_adaptive_fusion_cs_leaderboard.png` |
| **E2/E3 门控行为图** | `outputs/figures/phase_consensus_gate_behavior.png`（Δ 分布 + 排除率 vs 阈值） |
| **E4 诊断图** | `outputs/figures/phase_role_channel_vs_modal_rho.png` |
| **E5 跨域对比图** | `outputs/figures/phase_role_hkh_vs_cs_quality_dist.png` |
| **验证报告** | `docs/reports/phase_unique_role_adaptive_fusion_report.md` |
| **实验脚本** | `notebooks/scripts/chFusion_phase_unique_role_diag.py`、`notebooks/scripts/chFusion_phase_adaptive_fusion.py` |
| **新增模块** | `src/ble_analysis/phase_adaptive_gating.py` |
| **扩展模块** | `src/ble_analysis/systematic_fusion.py`、`src/ble_analysis/b3_pipeline.py` |

---

## 8. 验证状态与保留问题

> 由 **执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | 待实现 |
| **实际脚本** | — |
| **报告链接** | — |
| **一句话结论** | — |

### 保留问题

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | Phase 的零陷填充角色是否在 HKH 和 CS 上都成立？ | E1a 检验 |
| Q2 | Phase 在它最优的窗口中，波形是否比幅值更接近 GT？ | E1b 检验（仅 HKH） |
| Q3 | BPM 一致性门控是否优于 η·ρ 加权门控？ | E2 vs E3d |
| Q4 | R+L 默认 + Phase 条件激活能否同时适应 HKH（Phase 多数排除）和 CS（Phase 多数保留）？ | E3 跨域对比 |
| Q5 | 为什么 ρ 在信道级有效但在模态级失效？ | E4 诊断 |
| Q6 | HKH 和 CS 上 Phase 行为差异的物理根因是什么？ | E5 诊断 |
| Q7 | 是否存在某些场景/subject 中 Phase 系统性优于幅值？ | E5b 检查 |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，按以下顺序执行：

1. **先读** `docs/plans/phase_unique_role_adaptive_fusion_plan.md` 全文
2. **E1 诊断**：实现 `notebooks/scripts/chFusion_phase_unique_role_diag.py`
   - E1a: 基于已有 `modal_oracle_per_window.npy` 做零陷填充检验（Null Score 分析）
   - E1b: HKH 上 Phase-best vs Remote-best 窗的波形-GT 相关系数对比
   - E1c: 三模态 pairwise BPM error 相关性分析
   - E4: 信道级 vs 模态级 ρ 作用机制诊断
   - E5: HKH vs CS Phase 质量分布对比
3. **E2/E3 算法实验**：实现 `notebooks/scripts/chFusion_phase_adaptive_fusion.py`
   - 新增 `src/ble_analysis/phase_adaptive_gating.py`
   - 扩展 `systematic_fusion.py` 支持 consensus gate 和 adaptive activation
   - 在 `DRAFT_ABLATION_SPECS` 中追加 E2/E3 变体
   - 在 HKH 12 + CS 3 上跑全量评估
4. **撰报告**：按 `docs/templates/algorithm_validation_report.md` 模板写 `docs/reports/phase_unique_role_adaptive_fusion_report.md`
5. **回填本 plan §8** 的验证状态

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/phase_unique_role_adaptive_fusion_plan.md`
- `docs/reports/phase_unique_role_adaptive_fusion_report.md`
- `outputs/reports/phase_adaptive_fusion_*_summary.json`
- `outputs/reports/phase_unique_role_diag.json`
- `outputs/figures/phase_role_*`、`phase_adaptive_fusion_*`、`phase_consensus_*`
- 关键脚本路径
- git commit message

> ⚠️ **HKH 和 CS 结果必须分表/分图展示**。HKH 用 BPM abs err (breaths/min)，CS 用 BPM rel err %。
