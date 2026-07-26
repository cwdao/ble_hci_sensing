# Phase 互补投影角色发掘与自适应融合 — 实现计划（v2.0，吸收 5.6sol 建议）

> **v2.0 变更**：根据 5.6sol 建议全面修正物理模型（幅值/相位互补投影替代 Phase 无零陷）、重设计 E1a/E1b/E2、新增 P0 oracle 上限/IQ 几何诊断、升级统计评估标准  
> **v1.0 来源**：`modal_quality_gating` 实验结论 + `paper_ablation_draft_align` 消融矩阵  
> **目标报告**：`docs/reports/phase_unique_role_adaptive_fusion_report.md`  
> **日期**：2026-07-26  
> **验证状态**：待实现

---

## 1. 动机与背景

| 项目 | 说明 |
|------|------|
| **问题** | 质量加权融合（E3d=0.384）优于等权（0.405）但未超越 Remote-only（0.376），CS 上等权仍最优（10.14%）。质量指标（η/ρ）与"谁给出正确 BPM"的相关性仅 ~64%。核心问题转变为：**组合相位（composite Phase）在什么条件下提供幅值模态无法替代的增量信息？这种增量能否在没有 GT 的情况下可靠识别？** |
| **相关实验** | `modal_quality_gating` 两轮（E1 oracle + E2 指标评估 + E3 质量加权 + E4 Phase 门控）、`paper_ablation_draft_align` HKH 消融矩阵 |
| **本 plan 定位** | 不继续在 η/ρ 加权路线上做增量优化；转向**理解 Phase 在合成多径信道中的互补投影角色**，围绕它设计**条件性救援策略**——Phase 不预设总是有用或总是无用，由每窗可观测的信号特征决定 Phase 是否参与、以多大权重参与 |
| **关键修正（vs v1.0）** | 5.6sol 指出：合成多径下 Phase 并非天然"无零陷"——幅值和相位是复信道扰动在径向和切向的互补投影，两者都可能出现盲区。Phase 的价值在于当幅值的径向呼吸分量弱时，相位切向分量可能仍显著。这不是"零陷填充"而是"互补投影救援"。详见 §2 |

### Phase 可能有什么互补价值？（修正后的研究假设）

回顾合成多径信道的复平面几何，Phase 至少在以下维度可能具有幅值不可替代的价值：

| # | 假设 | 物理直觉 | 可检验 |
|---|------|----------|--------|
| **H1** | **互补投影救援（Complementary Projection Rescue）** | 幅值扰动 ∝ 复信道扰动的**径向**投影（敏感区在扰动向量的径向方向），相位扰动 ∝ 复信道扰动的**切向**投影（敏感区在切向方向）。当 Remote 和 Local 的径向呼吸分量同时较弱时，切向分量（即组合 Phase）可能仍保持显著呼吸响应。Phase 的角色是：**当幅值径向投影双双失效时，提供切向投影的救援信息** | E1 + P0b IQ 几何诊断 |
| **H2** | **波形保真度** | 呼吸非正弦（吸/呼不对称），Phase 在切向保留了呼吸位移的线性保形特性（在单路径主导时近似线性），而幅值径向投影可能引入非线性畸变。即使 Phase BPM 不准，其波形形状在特定窗口可能更接近真实呼吸 | E1b（修正版） |
| **H3** | **跨模态分集** | Remote/Local 是同一双向交换的两个端侧观测——传播几何高度相关，但接收链、噪声及测量时刻不同，具有一定观测分集而非完全独立的空间分集。Phase 是两端复观测组合后的切向信息，也不是第三条独立路径。三者的失效模式因投影方向不同而可能互补——这构成了融合 diversity 增益的物理基础 | E1c（修正版） |
| **H4** | **Phase 在 R/L 不一致时最有价值** | 当 R 和 L 的 BPM 估计不一致（暗示至少一个幅值模态不可靠），或两者都低质量时，Phase 可作为 tie-breaker 或 rescue expert；当 R 和 L 高置信且一致时，Phase 几乎没有边际价值 | E2（修正版） |

**关键叙事修正（vs v1.0）**：
- ❌ 旧：Phase 无零陷（dφ/dd = 4π/λ ≠ 0），幅值有零陷（dA/dd ≈ 0）→ Phase 的唯一作用是填幅值零陷
- ✅ 新：幅值和相位是复信道扰动在径向和切向的互补投影 → 两者各自有敏感区和盲区 → Phase 在幅值径向分量弱时提供条件性互补信息

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 单端 PCT 幅值——复信道扰动的径向投影（Re 分量），噪声较低 |
| `local_amplitudes` | ✅ | 同上，物理对等但接收链/噪声独立 |
| `phases`（总相位） | ✅（条件使用） | 两端复观测组合后的切向投影（Im 分量）；在幅值径向分量弱时可能提供互补信息，但含两端噪声之和 |
| `amplitudes`（总幅值） | ❌ | 双方幅值乘积，无独立物理信息（已有定论） |

### 2.2 修正的物理模型：径向/切向互补投影

**这是 v2.0 最关键的修正。** 5.6sol 指出：在合成多径信道中，Phase 并非天然"无零陷"。

BLE CS 的复信道观测为 $H(d) = H_s + H_d(d)$，其中 $H_s$ 是静态多径合成项，$H_d(d)$ 是受呼吸调制的动态项。对复信道扰动求导：

$$\frac{d|H|}{dd} = \frac{\operatorname{Re}\{H^*H'\}}{|H|}, \qquad \frac{d\angle H}{dd} = \frac{\operatorname{Im}\{H^*H'\}}{|H|^2}$$

这说明：
- **幅值响应** ∝ 复信道扰动在**径向方向**的投影（d|H|/dd ∝ Re{H\*H'}）
- **相位响应** ∝ 复信道扰动在**切向方向**的投影（d∠H/dd ∝ Im{H\*H'}）
- **两者谁强，取决于 IQ 轨迹相对于原点的方向**
- **幅值可以出现盲区，相位同样可以出现盲区**（当扰动方向恰好径向或恰好切向时）
- **更准确的说法：二者通常具有互补的敏感区**

对于 BLE CS 的具体情况，BreatheCS 的两级 PCT 处理后：

$$\Phi_i(t) = \angle\left(Z_{l,i}(t) \cdot Z_{r,i}(t)\right)$$

组合相位的呼吸分量对应于 Local 和 Remote 复观测的切向分量之和：

$$\delta\Phi_i \approx \operatorname{Im}\left\{\frac{\delta Z_{l,i}}{\overline{Z}_{l,i}} + \frac{\delta Z_{r,i}}{\overline{Z}_{r,i}}\right\}$$

而幅值的呼吸分量对应于各自复观测的径向分量：

$$\frac{\delta A_{d,i}}{\overline{A}_{d,i}} \approx \operatorname{Re}\left\{\frac{\delta Z_{d,i}}{\overline{Z}_{d,i}}\right\}$$

**核心结论**：Remote/Local 幅值和组合 Phase 不是"一个好一个差"，而是同一复信道扰动的三个不同投影方向——径向（Remote）、径向（Local）、切向之和（Phase）。当径向投影因多径几何而弱化时，切向投影可能仍保持显著。

### 2.3 双基地几何修正

5.6sol 指出 $4\pi\Delta d/\lambda$ 是单基地往返模型。BLE 链路更接近双基地反射几何：

$$\Delta\phi = \frac{2\pi}{\lambda}\Delta L, \quad \Delta L \approx (\mathbf{u}_{\mathrm{Tx}}+\mathbf{u}_{\mathrm{Rx}})^T \Delta\mathbf{x}$$

$4\pi/\lambda$ 仅是位移方向与入射/反射方向共线时的特例。论文中应使用 $(2\pi/\lambda)\Delta L$ 作为主模型。

### 2.4 Remote/Local/Phase 不是"三条独立传播路径"

修正表述：
- Remote 和 Local 是**同一双向交换的两个端侧观测**——传播几何高度相关（理想互易），但接收链、噪声、AGC、校准及测量时刻不同，具有**一定观测分集而非完全独立的空间分集**
- Phase 是两端复观测组合后的切向信息，**不是第三条独立传播路径**
- 正确的定位：**如何融合高度相关但噪声结构不同的双向幅值观测，以及由二者共同构成的相位观测？**

### 2.5 Phase 噪声表述修正

不写"Phase 噪声是幅值的两倍"。应写：

$$\Phi = \phi_l + \phi_r, \quad \operatorname{Var}(\Phi) = \operatorname{Var}(\phi_l) + \operatorname{Var}(\phi_r) + 2\operatorname{Cov}(\phi_l,\phi_r)$$

仅当协方差可忽略且两端同方差时，$\operatorname{Var}(\Phi) \approx 2\sigma_\phi^2$。

### 2.6 符号约定

| 符号 | 含义 |
|------|------|
| η_m | 模态 m 融合波形的呼吸频段能量比 |
| ρ_m | 模态 m 融合波形的谱峰峰度（⚠️ ρ 奖励尖峰，包括尖锐假峰——这已在 §2.2 中注明） |
| BPM_m | 模态 m 的 Voting BPM 估计 |
| q_amp | 幅值联合弱响应指标：max(η̃_R, η̃_L) 或 √(η̃_R·η̃_L) |
| N_best(w) | 窗 w 的 oracle 最优模态（来自 GT） |
| E_rad | 径向呼吸能量（Re{δZ·e^{-j∠Z̄}}） |
| E_tan | 切向呼吸能量（Im{δZ·e^{-j∠Z̄}}） |

---

## 3. 算法与实验步骤

本 plan 按 5.6sol 建议的优先级重新组织：

```text
P0: 模型与统计审计（必须在 E1-E5 之前完成）
  │
  ├─► P0a: Phase oracle 增量上限
  │     计算 Δ_oracle = E[min(e_R,e_L)] - E[min(e_R,e_L,e_P)]
  │     若增量 < 0.01 BPM → Phase 的整体救援空间非常有限
  │
  ├─► P0b: IQ 几何诊断（径向/切向呼吸能量）
  │     用原始 PCT IQ（Z_l, Z_r）计算每窗每 tone 的径向和切向呼吸能量
  │     检验：Phase-best 窗是否确实对应幅值径向能量系统性下降？
  │
  ├─► P0c: 统计审计
  │     - 0.376/0.381/0.405 的 recording-level paired CI
  │     - Phase-best 窗口在时间轴上的聚集性检查
  │     - Phase-best 窗是否集中在少数 subject 或连续时段
  │
  ▼
E1: Phase 互补投影价值诊断（修正版）
  │
  ├─► E1a: 互补投影检验（替代旧 Null Score 方案）
  │     定义 q_amp(w) = max(η̃_R(w), η̃_L(w)) 为幅值联合弱响应
  │     其中 η̃_m = η_m / median_{w}(η_m) 是记录内归一化
  │     在 Phase oracle-best 窗中：q_amp 是否系统性偏低？
  │     → 若成立：Phase 在幅值径向分量双双退化时提供救援
  │
  ├─► E1b: 波形保真度（修正选择偏差）
  │     在同一批 Phase oracle-best 窗口内，比较：
  │       r(P,GT), r(R,GT), r(L,GT)
  │     报告配对差值：Δr_P = r(P,GT) - max{r(R,GT), r(L,GT)}
  │     同理在 Remote-best 窗内也比较所有模态
  │     → 若 Δr_P 在 Phase-best 窗内显著 > 0：Phase 波形优于幅值
  │
  ├─► E1c: 救援概率指标（替代旧误差相关分析）
  │     设正确阈值 τ = 1 BPM：
  │       (1) 救援率：P(e_P ≤ τ | e_R > τ, e_L > τ)
  │       (2) 独特正确率：P(e_P ≤ τ, e_R > τ, e_L > τ)
  │       (3) 破坏率：P(e_P > τ | e_RL ≤ τ)
  │       (4) Oracle 上限对比：R-only / R+L / R/L oracle / R/L/P oracle
  │
  ▼
E2: Phase 救援门控（逻辑修正版）
  │
  ├─► 核心修正：Phase 不应在"与 R+L 一致时"参与
  │    应在"R 和 L 不一致或双低质量时"做 tie-breaker / rescue expert
  │
  ├─► 情况 A: R,L 高置信且一致 → 直接用 R+L，不引入 Phase
  │     条件：|BPM_R - BPM_L| ≤ T_agree 且两者谱熵低、η高
  │
  ├─► 情况 B: R,L 不一致 → Phase 做 tie-breaker
  │     若 |BPM_P - BPM_R| < |BPM_P - BPM_L| → 选 R+P
  │     反之 → 选 L+P
  │     要求：Phase 有足够跨 tone 一致性
  │
  ├─► 情况 C: R,L 都低质量 → Phase 独立接管
  │     要求严格：Phase 跨 tone 峰频一致、非边界峰、邻窗连续、非二次谐波
  │
  ├─► 变体：严格共识(tie-breaker) / 多数投票 / 质量门控
  │
  ▼
E3: R+L Default + Phase Conditional Activation（修正版）
  │
  ├─► 默认 R+L 等权双模态 + Phase 条件激活
  │    激活条件（OR 逻辑）：
  │      C1 (幅值双弱): q_amp < threshold
  │      C2 (Phase 独特): Phase 与 R 或 L 之一一致但 R 和 L 不一致
  │      C3 (Phase 高质量): η_P > median(η_R, η_L) AND Phase 跨 tone 一致性高
  │
  ├─► 大幅简化变体矩阵（最多 3 个变体，避免在 12 条数据上过拟合）
  │
  ▼
E4: Channel-vs-Modal Metric Asymmetry（保持）
  │
  ├─► 诊断为什么 η·ρ 在信道级有效但在模态级失效
  │
  ▼
E5: Cross-Domain Phase Degradation Diagnosis（保持）
  │
  ├─► HKH vs CS：Phase 跨域差异根因
  │
  ▼
P2: 受控实验（条件性，依赖硬件可用性）
  │
  ├─► 工作点扫描 / 机械呼吸+非呼吸扰动 / 静态噪声标定
  │     实验可行性：[待确认]
```

---

### 3.0 P0: 模型与统计审计（优先于 E1-E5）

**目的**：在投入实现 E1-E5 之前，先完成关键的模型修正和上限计算，避免在物理上不成立的假设上浪费实验资源。

#### P0a: Phase Oracle 增量上限

```text
对每条 recording（HKH 12 条）：
  1. 计算每窗的三模态 BPM 误差（需 GT）：e_R, e_L, e_P, e_RL
  2. Oracle-幅值：每窗取 min(e_R, e_L)
  3. Oracle-全模态：每窗取 min(e_R, e_L, e_P)
  4. 计算 recording-level 均值：
     Δ_oracle = E_w[min(e_R, e_L)] - E_w[min(e_R, e_L, e_P)]
  
  若 Δ_oracle 在多数 recording 上 ≤ 0.01 BPM：
    → Phase 的整体 BPM 救援空间非常有限
    → 论文不应重点承诺 Phase BPM 融合收益
    → 转向将 Phase 价值定位于波形或 diagnostic finding
  
  若 Δ_oracle 在多数 recording 上 ≥ 0.05 BPM：
    → Phase 有实质救援潜力，值得继续 E2/E3
```

**产出**：每条 recording 的 Δ_oracle 表 + 跨 recording 分布

#### P0b: IQ 几何诊断（径向/切向呼吸能量）

这是 5.6sol 最推荐的诊断——用原始 PCT IQ 直接验证物理假设：

```text
对每个窗口 w、每个 tone i：
  1. 取原始复序列 Z_{l,i}(t), Z_{r,i}(t)（滤波后、滑窗内）
  2. 计算静态参考向量（窗内均值）：
     Z̄_{d,i} = mean_t(Z_{d,i}(t))
  3. 定义相对静态向量的扰动：
     δZ_{d,i}(t) = Z_{d,i}(t) - Z̄_{d,i}
  4. 计算径向和切向呼吸分量：
     r_{d,i}(t) = Re{δZ_{d,i}(t) · e^{-j∠Z̄_{d,i}}}
     q_{d,i}(t) = Im{δZ_{d,i}(t) · e^{-j∠Z̄_{d,i}}}
  5. 计算呼吸频段能量：
     E_rad(d,i) = Σ_{f∈F_b} |FFT(r_{d,i})|²
     E_tan(d,i) = Σ_{f∈F_b} |FFT(q_{d,i})|²
  6. 聚合到模态级：
     Remote: E_rad(R) = aggregate over i (E_rad(r,i))
     Local:  E_rad(L) = aggregate over i (E_rad(l,i))
     Phase:  E_tan(P) = aggregate over i (E_tan(l,i) + E_tan(r,i))
```

**关键检验**：
- 在 Phase oracle-best 窗口中，E_rad(R) 和 E_rad(L) 是否系统性偏低？
- 在 Phase oracle-best 窗口中，E_tan(P) 是否系统性偏高？
- 如果成立 → **物理学叙事被验证**：Phase 在幅值径向弱时通过切向提供互补信息
- 如果不成立 → Phase-best 可能来自其他机制（噪声、偶然正确），需修正论文叙事

**产出图表**：
- Phase-best vs Remote-best 窗的 E_rad/E_tan 分布对比
- 三模态 oracle 分组的径向/切向能量箱线图
- 单窗示例：IQ 轨迹 + 径向/切向分解

#### P0c: 统计审计

```text
1. Recording-level paired CI:
   - 对 0.376 (Remote), 0.381 (Channel), 0.405 (Equal)
   - 计算 12 条 recording 的 paired differences
   - Bootstrap 95% CI (按 recording 重采样，B=10000)
   - 若 CI 包含 0 → 差异无统计显著性 → 论文叙事需修正

2. Phase-best 窗口聚集性：
   - 105 个 HKH Phase-best 窗：是否来自连续的 1-2 个时间段？
   - 是否集中在 1-2 个 subject？
   - 若窗口高度聚集 → 不能声称 105 次独立救援

3. 重叠窗口影响：
   - 当前 20s/1s step → 相邻 95% 数据共享
   - 后续所有 BPM 统计改用 recording-level mean（先对每条 recording 内平均，再跨 recording 平均）
```

---

### 3.1 E1: Phase 互补投影价值诊断（修正版）

**目的**：在修正的物理模型下，检验 H1（互补投影救援）、H2（波形保真度）、H3（跨模态分集）。

**输入**：复用 `outputs/reports/modal_oracle_per_window.npy`（已有），需补充 CS 域数据。

#### E1a: 互补投影检验（H1，修正版）

```text
对每个窗口 w：
  1. 记录内归一化（关键修正—v2.0）：
     对每条 recording，计算 η_R, η_L, η_P 的中位数
     η̃_m(w) = η_m(w) / (median_{w'∈recording}(η_m(w')) + ε)
     （记录内归一化消除了跨 recording 的绝对水平差异）

  2. 定义幅值联合弱响应（修正版—v2.0）：
     q_amp(w) = max(η̃_R(w), η̃_L(w))
     或 q_amp,geo(w) = √(η̃_R(w) · η̃_L(w))
     （用 max 替代 min/max 比值：只有两个幅值都弱时 q_amp 才低）
     （旧版 Null Score = min/max → 已废弃，只检测"至少一个弱"）

  3. 按 oracle 最优模态分组：
     Group A: N_best = Phase
     Group B: N_best = Remote
     Group C: N_best = Local

  4. 比较 q_amp 在各组的分布：
     H1 预测：Group A 的 q_amp 显著低于 Group B/C
     → 若成立：Phase 在幅值径向投影双双退化时提供救援

  5. 额外检验：在 Group A 中
     "双弱"比例 = P(η̃_R < median(η̃_R) AND η̃_L < median(η̃_L))
     应显著 > 50%
```

**产出图表**：
- q_amp 按 oracle 最优模态分组的小提琴图/箱线图（HKH / CS 分面）
- Phase-best 窗的 (η̃_R, η̃_L) 二维散点图 vs Remote-best 窗
- 旧 Null Score 与新 q_amp 的对比（证明修正必要性）

#### E1b: 波形保真度检验（H2，修正版）

**修正选择偏差（v2.0 关键修正）**：

```text
正确做法（在同一批窗口内跨模态比较）：

  在 Phase oracle-best 窗口中（即那些 Phase BPM 最接近 GT 的窗口）：
    比较 r(P,GT), r(R,GT), r(L,GT)
    计算配对差值：
      Δr_P = r(P,GT) - max{r(R,GT), r(L,GT)}
    → 若 Δr_P > 0，则 Phase 波形在它擅长的窗口优于幅值

  在 Remote oracle-best 窗口中：
    同样比较 r(P,GT), r(R,GT), r(L,GT)
    → 幅值在它擅长的窗口中是否确实优于 Phase？

  错误做法（v1.0）：
    比较 Phase-best 窗的 Phase-GT 相关 vs Remote-best 窗的 Remote-GT 相关
    → 这几乎一定产生预期结果，因为是按 GT 分组的条件选择偏差
```

**补充波形指标**（5.6sol 建议）：
- 允许符号翻转后的最大相关
- 固定小范围时延内相关（不逐窗无限搜索 lag）
- 峰谷位置误差
- 吸气/呼气时间比误差

**产出图表**：
- Phase-best 窗内 r(P,GT) vs r(R,GT) vs r(L,GT) 的配对对比
- 典型窗口的波形叠加对比图（四线：P / R / L / GT）

#### E1c: 救援概率指标（H3，修正版）

```text
设正确阈值 τ = 1 BPM（约 0.05 Hz）：

  1. 幅值双失败时的 Phase 救援率：
     P(e_P ≤ τ | e_R > τ, e_L > τ)
     → "Remote 和 Local 都失败时，Phase 有多少概率救回来？"

  2. Phase 独特正确率：
     P(e_P ≤ τ, e_R > τ, e_L > τ)
     → "Phase 独自正确的窗口占比"

  3. Phase 破坏率：
     P(e_P > τ | e_RL ≤ τ)
     → "R+L 本就是对的，Phase 加入反而会错的情况占比"

  4. Oracle 上限（与 P0a 呼应）：
     E[min(e_R, e_L)] vs E[min(e_R, e_L, e_P)]
     Δ_oracle 跨 recording 分布

  5. 还需报告（修正版新增）：
     R-L 误差相关性 vs R-P 误差相关性（佐证分集假设）
     在 R 和 L 同时大误差（> median）的窗中，Phase 误差分布
```

**产出图表**：
- 救援率/独特正确率/破坏率的条形图
- Oracle 上限的 recording-level 分布
- Phase 误差 vs R+L 误差的条件散点图

---

### 3.2 E2: Phase 救援门控（逻辑修正版）

**目的**：用修正后的共识逻辑——Phase 在 R/L 不一致或双低时充当 tie-breaker。

**v2.0 核心修正**：5.6sol 指出，旧 E2 的逻辑"Phase 与 R+L 一致时参与"可能有误——如果 Phase 已经与 R+L 一致，它通常不会改变最终峰值，因此自然很难带来增益。Phase 真正有价值的窗口是：
- R 和 L 不一致（需要一个 tie-breaker）
- R 和 L 都低质量（Phase 独立接管）

#### 情况分类与门控规则

```text
对每个窗口 w：
  1. 计算三模态 Voting BPM：BPM_R, BPM_L, BPM_P
  
  2. 计算质量指标（用于情况判定）：
     η_R, η_L, η_P
     tone 一致性 c_R, c_L, c_P（跨 tone 峰频一致性）
     谱熵 H_R, H_L, H_P
  
  3. 情况判定：

  情况 A: R、L 高置信且一致
    条件：
      |BPM_R - BPM_L| ≤ T_agree（建议扫描 {0.5, 1.0} BPM）
      AND η_R > median(η_R across recording)
      AND η_L > median(η_L across recording)
      AND H_R < median(H_R) AND H_L < median(H_L)（低谱熵=峰集中）
    动作：
      → 直接用 R+L 等权融合，不引入 Phase
      → 因为 Phase 没有边际价值
  
  情况 B: R、L 不一致
    条件：
      |BPM_R - BPM_L| > T_agree（暗示至少一个不可靠）
      AND Phase 的跨 tone 一致性 c_P > threshold
    动作：
      若 |BPM_P - BPM_R| < |BPM_P - BPM_L|：
        → Phase 与 Remote 一致，R+P 等权（排除 Local）
      否则：
        → Phase 与 Local 一致，L+P 等权（排除 Remote）
      → Phase 充当 tie-breaker
  
  情况 C: R、L 都低质量
    条件：
      η_R < median(η_R) AND η_L < median(η_L)
      AND c_R < threshold AND c_L < threshold
    动作（严格条件）：
      若 Phase 满足全部：c_P > threshold
                      AND Phase 峰非边界峰（距 F_b 边界 > 0.02 Hz）
                      AND |BPM_P - BPM_prev| ≤ 2.0 BPM（因果邻窗连续）
                      AND Phase 峰非二次谐波（|2·f_P - f_consensus| > 0.02 Hz）
        → Phase 独立接管
      否则：
        → 退化为情况 B 或 R+L（最佳 effort）
```

**简化变体（最多 3 个，避免过拟合）**：

| Key | 描述 | 门控逻辑 |
|-----|------|----------|
| `e2_tiebreak` | Phase tie-breaker | 情况 A → R+L; 情况 B → Phase 做 tie-breaker; 情况 C → R+L fallback |
| `e2_rescue` | Phase rescue expert | 情况 A → R+L; 情况 B → Phase tie-breaker; 情况 C → Phase 独立接管（严格条件） |
| `e2_rl_default` | R+L 默认 + Phase 仅情况 C | 始终 R+L，仅情况 C（双低）时 Phase 介入 |

**Baseline**：
- `draft_s_full` (Equal 三模态): HKH 0.405, CS 10.14%
- `draft_s_channel` (Channel-only): HKH 0.381, CS 12.51%
- `draft_ms_remote` (Remote-only): HKH 0.376, CS 11.23%
- R+L 等权双模态 (新增 baseline): [待实验]

**与旧 E2 的关键区别**：
- 旧 E2：Phase 与 R+L 共识一致 → Phase 参与（Phase = 额外一票）
- 新 E2：Phase 在 R/L 不一致时做 tie-breaker（Phase = 打破僵局）
- **预测**：新 E2 应在 HKH 上有更可解释的收益（Phase 只在真正有用时激活，而非在已有共识时添加冗余信息）

---

### 3.3 E3: R+L 默认 + Phase 条件激活（修正版）

**目的**：利用"幅值通常更稳定"的先验，Phase 在检测到特定有利条件时激活。

**vs v1.0 的关键修正**：
- C2 条件从"Phase 与 R+L 共识一致"改为"Phase 与 R 或 L 之一一致但 R 和 L 不一致"
- 大幅简化变体（v1.0 有 5 个变体 → v2.0 最多 3 个）
- 权重策略简化

```text
默认策略（所有窗口）：
  S_default(f) = 0.5 × S_R(f) + 0.5 × S_L(f)   （Remote + Local 等权）

Phase 激活条件（满足任一即触发）：

  C1 (幅值径向双弱):
    q_amp(w) = max(η̃_R(w), η̃_L(w)) < θ_C1（建议 θ_C1 = 0.5）
    → 幅值径向投影可能双双退化 → Phase 激活

  C2 (R/L 冲突 + Phase tie-break):
    |BPM_R - BPM_L| > θ_disagree（建议 θ_disagree = 1.0 BPM）
    AND (|BPM_P - BPM_R| ≤ θ_agree OR |BPM_P - BPM_L| ≤ θ_agree)
    → R 和 L 不一致，Phase 与其中之一共识 → Phase 激活为 tie-breaker

  C3 (Phase 自身高质量):
    c_P > median(c_R, c_L)（跨 tone 一致性更高）
    AND η_P > median(η_R, η_L)

激活后融合（简化为 2 类）：
  若 C1 AND C2 同时满足（双弱且 R/L 冲突）；
    w_R:w_L:w_P = 1:1:2（Phase 升权——既是唯一可用的强信号，又承担 tie-breaker）
  否则（仅满足 C2 或 C3 之一）：
    w_R:w_L:w_P = 1:1:1（等权三模态——Phase 提供额外信息但不主导）
```

**简化变体**：

| Key | 描述 | 激活条件 | Phase 权重 |
|-----|------|----------|-----------|
| `e3_default` | R+L 等权（无 Phase） | 从不 | w_P = 0 |
| `e3_conditional` | 条件激活 | C1 OR C2 | 等权 1:1:1 |
| `e3_adaptive` | 自适应激活 | C1 OR C2 OR C3 | C1+C2 → 1:1:2, else → 1:1:1 |

**预测**：
- `e3_default`（无 Phase）应在 HKH 上接近 Remote-only（0.376）
- `e3_conditional` 应在 CS 上有增益（CS Phase 质量好）、HKH 上不退化（多数窗口不满足激活条件）
- `e3_adaptive` 可能因 12 条数据过小而不可靠——需 leave-one-subject-out 验证

---

### 3.4 E4: 信道侧 vs 模态侧指标不对称诊断（保持 v1.0）

**目的**：理解为什么 η·ρ 在信道级有效但在模态级不如 η-only。

**已知事实**：
- CS 金属板信道级（per-tone 选择）：η·ρ > η-only（Plan2 阶段结论）
- HKH 模态级（per-modal 选择）：η-only hit 63.6% > η·ρ hit 54.3%（E2 结论）

**诊断步骤**（同 v1.0，不再重复）：
- D4a: Per-tone ρ 的噪声特性
- D4b: ρ 在信道 Voting 中的作用机制
- D4c: 模态级 ρ 为何失效

**v2.0 补充注意**：5.6sol 指出当前论文 ρ 的文字描述（"ρ 抑制带内能量被尖锐假峰主导"）与数学定义（ρ = 峰值/带内均值 → 奖励尖峰，包括尖锐假峰）矛盾，需在代码注释和后续报告中使用准确表述。

---

### 3.5 E5: Phase 跨域差异根因诊断（保持 v1.0）

**目的**：理解 Phase 为什么在 HKH 崩溃但在 CS 表现正常。

**假设池和诊断步骤**（同 v1.0，不再重复）：
- H5a: 人体微动 → HKH Phase η 方差 > CS
- H5b: 呼吸非正弦性 → HKH Phase ρ < CS
- H5c: 多径复杂度 → HKH Phase Voting confidence < CS
- H5d: 采样/滤波差异 → 检查原始数据时间戳间隔

---

### 3.6 P2: 受控实验（条件性新增）

**优先级**：如果只能新增一个实验，5.6sol 建议选择这个而非进一步搜索复杂门控。

**实验可行性**：[待确认——取决于硬件条件和时间]

#### 实验 2-1：工作点扫描

- 使用金属板，保持呼吸振幅/频率固定
- 缓慢改变金属板基准位置（扫过约半个波长对应路径差范围）
- 每个工作点重复固定 5–10 mm 周期运动
- 记录 Remote IQ、Local IQ 和组合 Phase
- **目标**：观察径向/切向响应随工作点周期性变化，验证互补投影模型

#### 实验 2-2：机械呼吸 + 非呼吸扰动

- 在机械周期运动上叠加缓慢位置漂移、随机小幅抖动、偶发整体移动
- 比较 Phase 和幅值的退化速度
- **目标**：验证"HKH Phase 崩坏是否由人体微动导致"

#### 实验 2-3：完全静态噪声标定

- 无人、金属板静止时连续采集
- Remote/Local amplitude PSD、单端 PCT phase PSD、组合 phase PSD
- Event 间隔 jitter、unwrap 跳变
- 不同 tone 的 phase noise（Allan deviation 或不同积分时间下的相位方差）

---

## 4. Baseline 对比

### 4.1 已有方法（复用既有结果）

| 方法 Key | 描述性名称 | HKH BPM | CS rel% | 来源 |
|----------|-----------|--------:|--------:|------|
| `draft_s_full` | 逐模态 Voting → 三模态等权谱融合 | 0.405 | 10.14% | 已有 |
| `draft_s_channel` | Voting → 三选一最优模态 | 0.381 | 12.51% | 已有 |
| `draft_ms_remote` | Remote 单模态 Voting | 0.376 | 11.23% | 已有 |
| `draft_ms_local` | Local 单模态 Voting | 0.378 | 16.21% | 已有 |
| `draft_ms_phase` | Phase 单模态 Voting | 2.191 | 10.92% | 已有 |
| `e3d` | 逐模态 Voting → η·ρ·conf 加权谱融合 | 0.384 | 11.29% | 已有 |
| `e3a` | 逐模态 Voting → η 加权谱融合 | 0.396 | 10.17% | 已有 |

### 4.2 新增方法（本 plan 待实现）

| 方法 Key | 描述性名称 | 所属实验 | 说明 |
|----------|-----------|----------|------|
| `p0_rl_default` | **R+L 等权双模态融合** | P0/E3 baseline | Remote + Local 等权谱平均，Phase 不参与 |
| `e2_rl_default` | **R+L 默认 + Phase 仅救援** | E2 | 始终 R+L，仅情况 C 双低时 Phase 介入 |
| `e2_tiebreak` | **R+L 默认 + Phase tie-breaker** | E2 | 情况 A→R+L; 情况 B→Phase tie-break; 情况 C→R+L fallback |
| `e2_rescue` | **R+L 默认 + Phase rescue expert** | E2 | 情况 A→R+L; 情况 B→Phase tie-break; 情况 C→Phase 独立接管 |
| `e3_conditional` | **R+L 默认 + Phase 条件激活（双弱或冲突）** | E3 | C1（幅值双弱）OR C2（R/L 冲突+Phase tie-break） |
| `e3_adaptive` | **R+L 默认 + Phase 自适应权重** | E3 | C1/C2/C3 联合决定，C1+C2→升权, else→等权 |

**注意**：v2.0 变体从 v1.0 的 ~10 个简化为 5 个，避免在 12 条数据上过拟合。

### 4.3 预期相对关系（修正版）

| 对比 | 预期 | 理由 |
|------|------|------|
| `p0_rl_default` vs `draft_ms_remote` | HKH: 接近（~0.377）；CS: 待验证 | R+L 均值应接近二者中优者 |
| `e2_tiebreak` vs `p0_rl_default` | HKH: 略优（仅 Phase 有用时激活）；CS: 优于 | CS Phase 质量好，tie-break 有机会触发 |
| `e2_tiebreak` vs `draft_s_full` (0.405) | HKH: 应优于；CS: 接近或优于 | HKH: Phase 多数不激活→∼R+L; CS: Phase 质量好→有增益 |
| `e3_adaptive` vs `e2_tiebreak` | 差异可能很小 | 条件更细但 12 条数据上不可靠 |
| E1 H1 (互补投影) | 应在 P0b IQ 诊断中成立 | 这是最根本的物理检验；若失败→Phase 叙事需大幅修正 |
| P0a oracle 上限 | Δ_oracle 可能 ≤ 0.02 BPM | 基于 HKH Phase-only=2.191 的悲观预测 |

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
| Recording-level paired statistics | 两者 | **v2.0 新增**：先 per-recording 平均，再跨 recording 统计 |
| Paired bootstrap 95% CI | 两者 | **v2.0 新增**：按 recording 重采样，B=10000 |
| Phase 激活率 | 两者 | E2/E3 中 Phase 被激活的窗占比（分情况 A/B/C 报告） |
| Phase 破坏率 | 两者 | Phase 激活但 BPM 误差比 R+L default 更差的窗占比 |
| q_amp（幅值联合弱响应） | 两者 | E1a 诊断指标 |
| E_rad / E_tan | 两者 | P0b IQ 几何诊断指标 |
| 波形-GT 相关系数 + 配对差值 | HKH | E1b 波形保真度 |
| Δ_oracle (recording-level) | HKH | P0a oracle 上限 |

### 5.3 统计评估标准（v2.0 升级）

**关键修正**：5.6sol 指出滑窗 20s/1s step 导致相邻窗口共享 95% 数据，数千个窗口不是独立样本。

- **主统计单位**：recording（12 条 HKH；3 条 CS），而非 overlapping window
- **跨方法比较**：recording-level paired differences + bootstrap 95% CI
- **门控阈值选择**：必须在训练数据上确定（leave-one-subject-out 或 leave-one-room-out），不能在全部 12 条上扫描后报告最优值
- **Phase-best 窗口计数**：必须报告连续段数（而非仅窗口总数）——105 个 Phase-best 窗可能来自 1 个连续 2 分钟段
- **0.376/0.381/0.405 差异**：必须做 paired bootstrap。若 95% CI 包含 0，论文不能声称"BreatheCS BPM 最优"

### 5.4 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | P0 诊断完成（oracle 上限 + IQ 几何 + 统计审计）；E1 至少一项 Phase 互补投影假设被验证或明确证伪 |
| **理想** | E2/E3 至少一个变体在 leave-one-out 下不劣于 R+L default；Phase 救援的物理机制（径向/切向互补）被 P0b 验证 |
| **突破** | E2/E3 在 leave-one-out 下显著优于 R+L default 和 Remote-only——自适应策略超越了纯单模态天花板 |
| **失败** | P0a oracle 上限显示 Δ_oracle ≤ 0.01 BPM → Phase BPM 救援空间极有限 → 论文将 Phase 定位为 diagnostic finding 而非主算法组件 |

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 | 操作 |
|------|------|------|
| P0 诊断脚本 | `notebooks/scripts/chFusion_phase_p0_audit.py` | **新建**（oracle 上限 + IQ 几何 + 统计审计） |
| E1/E4/E5 诊断脚本 | `notebooks/scripts/chFusion_phase_diagnostics.py` | **新建**（合并 E1 + E4 + E5） |
| E2/E3 实验脚本 | `notebooks/scripts/chFusion_phase_adaptive_fusion.py` | **新建** |
| 模态融合 | `src/ble_analysis/systematic_fusion.py` | **扩展**：新增 `weight_mode="tiebreak"` + `"rescue"` + `"conditional"` |
| B3 Pipeline | `src/ble_analysis/b3_pipeline.py` | **扩展**：`DRAFT_ABLATION_SPECS` 追加 E2/E3 变体 |
| Gating 逻辑 | `src/ble_analysis/phase_adaptive_gating.py` | **新建**：E2 tie-breaker + E3 条件激活逻辑 |
| IQ 几何分析 | `src/ble_analysis/iq_geometry.py` | **新建**：径向/切向呼吸能量计算 |

### 6.2 新增函数签名建议

```python
# === P0a: Oracle 上限 ===

def compute_phase_oracle_delta(
    bpm_errors: dict[str, np.ndarray],  # {recording: {modality: errors}}
    tau: float = 1.0,
) -> pd.DataFrame:
    """
    每条 recording 的 Δ_oracle = E[min(e_R,e_L)] - E[min(e_R,e_L,e_P)].
    
    Returns:
        DataFrame with columns: recording, delta_oracle, e_rl_oracle, e_rlp_oracle
    """
    ...

# === P0b: IQ 几何诊断 ===

def compute_radial_tangential_energy(
    z_complex: np.ndarray,   # (n_tones, n_timesteps) complex PCT
    fs: float,
    f_band: tuple[float, float],
) -> dict:
    """
    计算每 tone 的径向和切向呼吸频段能量。
    
    Returns:
        {
            "E_rad": np.ndarray (n_tones,),   # 径向呼吸能量
            "E_tan": np.ndarray (n_tones,),   # 切向呼吸能量
            "static_ref": np.ndarray (n_tones,),  # 静态参考向量
        }
    """
    ...

# === P0c: 统计审计 ===

def recording_level_paired_bootstrap(
    results: dict,  # {method: {recording: mean_error}}
    n_bootstrap: int = 10000,
) -> dict:
    """Recording-level paired bootstrap 95% CI for all method pairs."""
    ...

def detect_temporal_clustering(
    window_indices: np.ndarray,
    step_sec: float = 1.0,
) -> dict:
    """
    检测窗口在时间轴上的聚集性。
    
    Returns:
        {
            "n_segments": int,        # 连续段数
            "max_segment_len": float,  # 最长连续段时间（秒）
            "n_total_windows": int,    # 窗口总数
        }
    """
    ...

# === E1a: 互补投影检验 ===

def compute_amplitude_joint_weakness(
    eta_r: np.ndarray,
    eta_l: np.ndarray,
    eta_p: np.ndarray,
    norm_method: str = "recording_median",
) -> np.ndarray:
    """
    计算 q_amp = max(η̃_R, η̃_L)——幅值联合弱响应指标。
    旧版 Null Score = min/max → 已废弃。
    """
    ...

# === E1c: 救援概率 ===

def compute_rescue_metrics(
    bpm_errors: dict,  # {modality: errors per window}
    tau: float = 1.0,
) -> dict:
    """
    Returns:
        {
            "rescue_rate": P(e_P≤τ | e_R>τ, e_L>τ),
            "unique_correct": P(e_P≤τ, e_R>τ, e_L>τ),
            "destruction_rate": P(e_P>τ | e_RL≤τ),
            "oracle_rl": E[min(e_R, e_L)],
            "oracle_rlp": E[min(e_R, e_L, e_P)],
        }
    """
    ...

# === E2: 修正版共识门控 ===

def classify_window_condition(
    bpm_r: float, bpm_l: float, bpm_p: float,
    eta_r: float, eta_l: float, eta_p: float,
    coherence_r: float, coherence_l: float, coherence_p: float,
    eta_medians: dict, coherence_thresholds: dict,
    t_agree: float = 1.0,
) -> str:
    """
    返回 "A" (R,L 高置信一致), "B" (不一致), "C" (双低质量).
    """
    ...

def tiebreak_gated_fusion(
    spectra_by_var: dict,
    condition: str,
    bpm_by_var: dict,
) -> np.ndarray:
    """
    修正版门控融合：
    - 情况 A → R+L 等权
    - 情况 B → Phase tie-break (R+P 或 L+P)
    - 情况 C → Phase 独立接管或 R+L fallback
    """
    ...
```

### 6.3 不做的事

- 不修改原始数据、GT、滤波参数
- 不引入新的外部方法（如 VMD, PCA）
- 不修改 Voting 信道融合逻辑（E4 仅做诊断）
- 不在本 plan 中修改波形分支（B2-D MRC）
- 不新建场景 JSON
- **v2.0 新增**：不一次搜索几十个权重组合（避免在 12 条数据上过拟合）

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| **P0 oracle 上限** | `outputs/reports/phase_p0_oracle_delta.json` |
| **P0 IQ 几何诊断** | `outputs/figures/phase_p0_radial_tangential_energy.png` |
| **P0 统计审计** | `outputs/reports/phase_p0_statistical_audit.json` |
| **E1 互补投影图** | `outputs/figures/phase_e1_complementary_projection.png` |
| **E1 救援概率图** | `outputs/figures/phase_e1_rescue_metrics.png` |
| **E1 诊断数据** | `outputs/reports/phase_e1_diagnostics.json` |
| **E2/E3 HKH 结果** | `outputs/reports/phase_adaptive_fusion_hkh_summary.json` |
| **E2/E3 CS 结果** | `outputs/reports/phase_adaptive_fusion_cs_summary.json` |
| **E2/E3 排行榜图** | `outputs/figures/phase_adaptive_fusion_hkh_leaderboard.png`、`phase_adaptive_fusion_cs_leaderboard.png` |
| **E2/E3 门控行为图** | `outputs/figures/phase_gate_condition_distribution.png`（情况 A/B/C 占比 + 各条件激活率） |
| **E4 诊断图** | `outputs/figures/phase_e4_channel_vs_modal_rho.png` |
| **E5 跨域对比图** | `outputs/figures/phase_e5_hkh_vs_cs_quality_dist.png` |
| **验证报告** | `docs/reports/phase_unique_role_adaptive_fusion_report.md` |
| **新增/修改模块** | `src/ble_analysis/phase_adaptive_gating.py`、`src/ble_analysis/iq_geometry.py`、`systematic_fusion.py`、`b3_pipeline.py` |

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
| Q1 | Phase 的 oracle 增量上限有多大？值得继续做门控吗？ | P0a |
| Q2 | Phase-best 窗是否确实对应幅值径向能量系统性下降、切向能量仍显著？ | P0b（最关键的物理检验） |
| Q3 | 0.376/0.381/0.405 的 recording-level paired CI 是否包含 0？ | P0c |
| Q4 | Phase-best 窗口是分散的还是聚集的（连续段数 vs 窗口总数）？ | P0c |
| Q5 | 修正版 E2（Phase tie-breaker）是否优于旧版 E2（Phase 一致时参与）？ | E2 vs 旧 E2 |
| Q6 | R+L 默认 + Phase 条件激活能否同时适应 HKH（Phase 多数不激活）和 CS（Phase 多数激活）？ | E3 跨域对比 |
| Q7 | 为什么 ρ 在信道级有效但在模态级失效？ | E4 |
| Q8 | HKH 和 CS 上 Phase 行为差异的物理根因是什么？ | E5 |
| Q9 | 受控工作点扫描实验是否可行？能否验证互补投影模型？ | P2 [待确认] |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，按以下顺序执行：

1. **先读** `docs/plans/phase_unique_role_adaptive_fusion_plan.md`（本文件 v2.0）全文
2. **P0 审计**（优先于 E1-E5）：
   - P0a: 实现 `compute_phase_oracle_delta()` → 计算每条 HKH recording 的 Δ_oracle
   - P0b: 实现 `compute_radial_tangential_energy()` → IQ 几何诊断，验证幅值/相位互补投影假设
   - P0c: 实现 `recording_level_paired_bootstrap()` + 窗口聚集性检测
3. **E1 诊断**：实现 `notebooks/scripts/chFusion_phase_diagnostics.py`
   - E1a: 用修正版 q_amp = max(η̃_R, η̃_L) 做互补投影检验
   - E1b: 修正选择偏差——同窗口内跨模态比较
   - E1c: 救援率/独特正确率/破坏率/oracle 上限
   - E4: 信道级 vs 模态级 ρ 作用机制
   - E5: HKH vs CS Phase 质量分布对比
4. **E2/E3 算法实验**：实现 `notebooks/scripts/chFusion_phase_adaptive_fusion.py`
   - 新增 `src/ble_analysis/phase_adaptive_gating.py`（tie-breaker + rescue + conditional）
   - 新增 `src/ble_analysis/iq_geometry.py`（径向/切向能量计算）
   - 扩展 `systematic_fusion.py` 支持 tie-break/rescue/conditional 门控
   - 在 `DRAFT_ABLATION_SPECS` 中追加 E2/E3 变体（最多 5 个）
   - 在 HKH 12 + CS 3 上跑全量评估
   - **门控阈值必须用 leave-one-subject-out 确定**，不能在全量数据上扫描
5. **撰报告**：按 `docs/templates/algorithm_validation_report.md` 模板写 `docs/reports/phase_unique_role_adaptive_fusion_report.md`
6. **回填本 plan §8** 的验证状态

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/phase_unique_role_adaptive_fusion_plan.md`
- `docs/reports/phase_unique_role_adaptive_fusion_report.md`
- `outputs/reports/phase_p0_*`、`phase_e1_*`、`phase_adaptive_fusion_*`
- `outputs/figures/phase_*`
- 关键脚本路径
- git commit message

> ⚠️ **关键提醒**：
> - HKH 和 CS 结果必须分表/分图展示。HKH 用 BPM abs err (breaths/min)，CS 用 BPM rel err %
> - **主统计单位为 recording，而非滑窗**。先 per-recording 平均，再跨 recording 统计
> - **门控阈值不可在全部数据上扫描最优值**——必须 leave-one-subject-out 或 leave-one-room-out
> - 旧版 Null Score（min/max）已废弃 → 改用 q_amp = max(η̃_R, η̃_L)
> - E1b 不要跨窗口组比较（选择偏差）→ 在同一批窗口内比较所有模态
