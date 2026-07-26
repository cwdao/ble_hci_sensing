# BreatheCS 统一管线：最终方法收敛与配置选择 — 实现计划

> **来源**：Phase 互补投影实验 (`phase_unique_role_adaptive_fusion`) + 消融矩阵 (`paper_ablation_draft_align`) + 模态质量门控 (`modal_quality_gating`) + 波形 MRC (`b2_coherent_mrc`)  
> **目标报告**：`docs/reports/unified_pipeline_final_report.md`  
> **日期**：2026-07-26  
> **验证状态**：已完成（2026-07-26）

---

## 1. 动机与背景

| 项目 | 说明 |
|------|------|
| **问题** | 经过 6 轮实验，tone-level fusion 的最优策略已确认（Voting η·ρ），但 modal-level 的最终配置尚未冻结。当前存在两个竞争方案：（A）Amplitude-only（R+L 双模态融合，简单可靠）；（B）Phase-gated（Phase 置信度闸门自适应加入，跨域灵活）。本实验在二者之间做最终选择。 |
| **定位** | **收敛选择实验，非探索性实验**。不引入新组件，不搜索新超参数。核心问题是：Phase gate 是否在 out-of-sample 条件下提供足够价值以证明其复杂度？ |
| **理论框架** | Multi-Scale Quality-Weighted Diversity Combining（§2.3）作为经验支持的设计框架，不代表形式化定理。 |

### 1.1 已有实验支撑（每个设计选择的证据来源）

| 管线组件 | 选择 | 证据实验 | 关键数字 |
|----------|------|----------|----------|
| 信道融合策略 | Voting (η·ρ) | `systematic_fusion` + `paper_ablation_draft_align` | Voting (0.381) ≫ Uniform (1.640) |
| 模态级质量度量 | η-only（非 η·ρ） | `modal_quality_gating` E2 | η hit 63.6% > η·ρ hit 54.3% |
| Phase 闸门指标 | Voting confidence（非 η） | `phase_unique_role_adaptive_fusion` E5 | H5a 否（η 不区分域），H5c 是（conf 区分） |
| Phase 闸门阈值 | θ_conf ~0.35 | `phase_unique_role_adaptive_fusion` E5 | HKH 0.324 vs CS 0.402 |
| 模态融合算子 | η-weighted spectral avg | `modal_quality_gating` E3a | CS E3a 10.17% ≈ Equal 10.14% |
| R+L 谱域基线 | R+L equal = 0.372 | `phase_unique_role_adaptive_fusion` p0_rl_default | HKH 当前最优 |
| Phase oracle 上限 | Δ_oracle = 0.028 BPM | `phase_unique_role_adaptive_fusion` P0a | Phase 即使 GT 选最优窗，增益也极小 |
| Phase rescue/destruction | rescue 18%, destruction 49% | `phase_unique_role_adaptive_fusion` E1c | Phase 破坏 > 救援 |
| Phase gate vs R+L | paired CI 含 0 — 无显著增益 | `phase_unique_role_adaptive_fusion` E2/E3 | gate 尚未证明其价值 |
| 波形 MRC | coherent MRC (Hilbert) | `b2_coherent_mrc` | B2-D 9.43% CS |
| 波形单模态基线 | Remote RMSE 0.931 | `paper_ablation_draft_align` | HKH 波形 baseline |

### 1.2 两个候选主方法（预注册）

#### Candidate A：Amplitude-only BreatheCS（推荐默认）

```text
Tone-level η·ρ aggregation
        ↓
Remote + Local modal fusion (equal or η-weighted)
        ↓
Spectral BPM / coherent waveform
```

- Phase 不参与融合。最简配置。
- HKH 已有证据：R+L = 0.372，优于 Remote 0.376、三模态 0.405。

#### Candidate B：Phase-gated BreatheCS（待验证扩展）

```text
Tone-level η·ρ aggregation
        ↓
Phase confidence gate (θ_conf LOSO-determined)
        ↓
R+L or R+L+P (η-weighted)
        ↓
Spectral BPM / coherent waveform
```

- Phase 通过跨 tone 投票一致性闸门后参与融合。
- 期望：HKH 上闸门关闭 ≈ R+L（不劣），CS 上闸门开启 → Phase 参与 → 接近三模态最优。

### 1.3 本次实验需新增的测量

| 测量项 | 原因 | 域 |
|--------|------|-----|
| R+L 波形 RMSE | 已有 Remote/Local 单模态波形 RMSE,但没有 R+L 组合 | HKH |
| Candidate A (R+L η-weighted) full pipeline | 统一脚本重跑确认 | HKH + CS |
| Candidate B (Phase-gated) full pipeline | 各组件分别验证过，组合后未跑过完整实验 | HKH + CS |
| Gate threshold LOSO (含 θ=+∞) | θ_conf 需要 out-of-sample 验证，且必须包含"永不用 Phase"选项 | HKH |
| CS spectral BPM for both candidates | 跨域验证——CS 无波形 GT，仅测谱域 BPM | CS |

> ⚠️ CS 金属板**无呼吸带 GT 波形**。CS 仅评估 spectral BPM relative error。CS 不测 waveform RMSE。

### 1.4 预期性能

| 管线 | 域 | 指标 | 预期值 | 推断来源 |
|------|-----|------|:------:|------|
| Candidate A (R+L) | HKH | BPM abs err | **~0.372** | `p0_rl_default` — 复现已有结果 |
| Candidate A (R+L) | CS | BPM rel % | **~14%** | `p0_rl_default` — R+L 在 CS 上不如三模态 |
| Candidate B (gated) | HKH | BPM abs err | **~0.372** | gate 关闭 Phase → ≈ R+L |
| Candidate B (gated) | CS | BPM rel % | **~10.1–10.2%** | Phase 通过闸门 → ≈ E3a 三模态 η-weighted |
| R+L waveform | HKH | RMSE | **~0.91–0.95** | Remote alone=0.931；R+L MRC 预期略优或持平 |

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 单端 PCT 幅值——复信道微扰的径向投影（Re 分量），噪声低 |
| `local_amplitudes` | ✅ | 同 Remote，物理对等但接收链/噪声独立，提供观测分集 |
| `phases`（总相位） | ✅（条件） | 两端复观测组合后的切向投影（Im 分量）；通过 Voting confidence 闸门决定是否参与融合 |
| `amplitudes`（总幅值） | ❌ | 双方幅值乘积，无独立物理信息（已有定论） |

### 2.2 理论框架：多尺度质量加权分集合并 (MS-QWDC)

BLE CS 在两个尺度上提供了分集：

```
Micro-diversity (channel-level, N=72):
  72 tones × 80 MHz bandwidth → frequency-selective fading
  → different tones have different breathing sensitivities
  → Strategy: η·ρ-weighted Voting (non-coherent MRC)
  → Large N protects against ρ false positives

Macro-diversity (modal-level, N=3):
  3 modal variables = 3 geometric projections of the same complex perturbation
    Remote: radial projection at device A
    Local:  radial projection at device B
    Phase:  tangential projection (sum of both devices)
  → Strategy: η-weighted spectral fusion + Phase coherence gate
  → Small N mandatates conservative weighting (η-only, drop ρ)
```

**Phase 闸门的物理原理**：

Phase 的 Voting confidence 测量的是"72 个 Phase tone 是否在**同一频率**看到了呼吸信号"——这是**相干性检测**（coherence detection），不同于 η 的**能量检测**（energy detection）。

- 当切向投影的呼吸分量足够强时 → 72 tone 一致投票 → confidence 高
- 当切向投影弱（如 HKH 丰富多径下径向主导） → 噪声 tone 频率随机 → confidence 低

闸门阈值 θ_conf 将 Phase 参与融合的条件表述为：**"存在足够的跨 tone 统计证据表明切向投影中含有呼吸信号"**。

**为什么 N=72 用 η·ρ 而 N=3 用 η-only**：

这是一个经验支持的尺度依赖加权原则。在 72-tone 层级，孤立的尖锐假峰能够被跨 tone 共识稀释——即使个别 tone 的 ρ 误选假峰，其影响在大量 tone 的加权平均中被抑制。在仅有 2–3 个模态时，一个错误的高突出度候选即可直接主导融合，因此模态级权重需要比 tone 级更保守。E4 数据验证了这一关系：模态级 η-only hit (63.6%) > η·ρ hit (54.3%)。

### 2.3 符号约定

| 符号 | 含义 |
|------|------|
| η_m | 模态 m 融合波形的呼吸频段能量比 |
| ρ_m | 模态 m 融合波形的峰值突出度 / peak prominence（⚠️ 奖励尖峰，包括尖锐假峰） |
| conf_m | 模态 m 的 Voting confidence（跨 tone 峰频一致性） |
| S_m(f) | 模态 m 的 Voting 融合谱 |
| w_m | 模态 m 在融合中的权重，∝ η_m |
| θ_conf | Phase 闸门阈值（LOSO 确定） |
| y_m(t) | 模态 m 的 coherent MRC 融合波形（仅波形分支） |

---

## 3. 算法步骤

### 3.1 流程图

```text
                    ┌──────────────────────────────────────────┐
                    │     BreatheCS Unified Pipeline           │
                    │  Multi-Scale Quality-Weighted Diversity  │
                    │           Combining (MS-QWDC)             │
                    └──────────────────────────────────────────┘

  Raw BLE CS Frames:  72 tone × 3 variables (remote_amplitudes / local_amplitudes / phases)
    │
    │  滤波链 (per tone, per variable):
    │    median(w=3) → highpass(0.05 Hz) → bandpass(0.1–0.35 Hz)
    │    [模块: segments.py]
    │    [维度: 72 tone × 3 var × T timesteps]
    │
    ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ Stage 1 — 信道级融合 (Micro-Diversity Combining)                         │
  │                                                                          │
  │ Per modal (R / L / P), per window (20s/1s):                             │
  │   • Per-tone: 计算 η (呼吸频段能量比), ρ (谱峰峰度)                      │
  │   • Voting: 72 tone 以 η·ρ 加权直方图投票                                │
  │   • 输出: 3 条 per-modal 融合谱 S_R(f), S_L(f), S_P(f)                  │
  │   • 同时输出: η_m, conf_m, ρ_m (per-modal 质量向量)                      │
  │                                                                          │
  │   [模块: systematic_fusion.py → _channel_spectrum_and_q() + vote]       │
  │   [证据: Voting 0.381 ≫ Uniform 1.640]                                  │
  └─────────────────────────────────────────────────────────────────────────┘
    │
    │  输出 per window: (S_R, S_L, S_P), (η_R, η_L, η_P), (conf_R, conf_L, conf_P)
    │
    ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ Candidate Decision: Modal Inclusion Policy                                │
  │                                                                          │
  │ Candidate A (Amplitude-only):                                            │
  │   M_active = {R, L}   (Phase never included)                             │
  │                                                                          │
  │ Candidate B (Phase-gated):                                               │
  │   IF conf_P < θ_conf:                                                    │
  │       M_active = {R, L}  (切向投影无足够跨 tone 相干证据)                 │
  │   ELSE:                                                                  │
  │       M_active = {R, L, P}                                               │
  │                                                                          │
  │ θ_conf 由 LOSO 在训练集上确定（候选集含 +∞ = Phase 永不启用）            │
  │                                                                          │
  │ [模块: phase_adaptive_gating.py → gate_by_confidence()]                  │
  │ [证据: E5 HKH conf 0.324 < CS 0.402; H5c validated]                     │
  └─────────────────────────────────────────────────────────────────────────┘
    │
    │  M_active ⊆ {R, L, P}
    │
    ├─────────────────────────────────────────────────────┐
    ▼                                                     ▼
  ┌──────────────────────────────┐         ┌──────────────────────────────┐
  │ Stage 3a — 谱域模态融合       │         │ Stage 3b — 波形模态融合       │
  │ (Spectral BPM Pipeline)      │         │ (Waveform RMSE Pipeline)     │
  │                              │         │                              │
  │ w_m ∝ η_m, 归一化到 sum=1   │         │ w_m ∝ η_m, 归一化到 sum=1   │
  │                              │         │                              │
  │ S_fused(f) = Σ w_m·S_m(f)   │         │ y_fused(t) = coherent MRC:   │
  │                              │         │   1. Hilbert 变换 per modal  │
  │   (实数谱平均, 无需对齐)     │         │   2. 互相关相位对齐          │
  │                              │         │   3. w_m 加权叠加            │
  │         │                    │         │                              │
  │         ▼                    │         │         │                    │
  │  寻峰 → BPM                  │         │         ▼                    │
  │                              │         │  Welch PSD 寻峰 → BPM        │
  │  [模块: systematic_fusion.py │         │  + waveform → RMSE vs GT     │
  │   → modal_fusion_from_       │         │                              │
  │   spectra(weight_mode=       │         │  [模块: coherent_mrc.py →    │
  │   "eta_only")]               │         │   coherent_mrc_fuse_modals() │
  └──────────────────────────────┘         └──────────────────────────────┘
```

### 3.2 Stage 1 详细：信道级 Voting

```
对窗口 w、模态 m (m ∈ {R, L, P}):

  输入: 72 tone 带通滤波后的实值序列 (每 tone 长度 = 20s × fs)
  
  1. Per-tone 谱估计与质量:
     for i in 1..72:
       P_i(f) = Welch PSD(tone_i)
       η_i = Σ_{f∈[0.1,0.35]} P_i(f) / Σ_{f} P_i(f)
       f_peak,i = argmax_{f∈[0.1,0.35]} P_i(f)
       ρ_i = P_i(f_peak,i) / mean(P_i(f))  for f∈[0.1,0.35]
  
  2. η·ρ 加权直方图投票:
     valid = {i | η_i > 0.05}  # 过滤极低 SNR tone
     for i in valid:
       histogram_bin[round(f_peak,i / Δf)] += η_i · ρ_i
     
  3. 融合谱 S_m(f):
     for i in valid:
       P_i_norm(f) = P_i(f) / max(P_i)
       S_m(f) += η_i · ρ_i · P_i_norm(f)
     S_m(f) /= Σ valid(η_i · ρ_i)
  
  4. 模态质量指标:
     η_m = Σ_{f∈[0.1,0.35]} S_m(f) / Σ_{f} S_m(f)
     conf_m = max_b(Σ_{i:f_i∈b} w_i) / (Σ_i w_i + ε)  # 固定定义：最高 bin 加权票数占比
     ρ_m = S_m(f_peak) / mean_{f∈[0.1,0.35]} S_m(f)
```

### 3.3 Candidate Decision 详细：Modal Inclusion Policy

**Candidate A (Amplitude-only)**：

```
active_modals = {"R", "L"}  # Phase never included
```

**Candidate B (Phase-gated)**：

```
对每个窗口 w:

  conf_P = Voting confidence from Stage 1 (Phase modal)
           # 固定定义: max_bin_weighted_votes / total_weighted_votes
  
  if conf_P < θ_conf:
      active_modals = {"R", "L"}
      gate_log[w] = "phase_excluded"
  else:
      active_modals = {"R", "L", "P"}
      gate_log[w] = "phase_included"

  # θ_conf 确定方式（4-fold LOSO, leave-one-subject-out）:
  #   HKH 共 4 subjects, 每 subject 3 recordings
  #   for each held-out subject s:
  #     在其余 3 subjects 的 9 条 recording 上扫描候选 θ
  #     候选集: θ ∈ {0.30, 0.35, 0.38, 0.40, +∞}
  #       +∞ = Phase 永不启用 = Candidate A
  #     选使 train BPM 最优的 θ
  #     在 held-out subject 的 3 条 recording 上评估
  #   Tie-breaking: 多 θ 训练误差接近时，选更保守的（Phase 激活率更低的）
  #   CS 上使用 4 个 LOSO fold 所选 θ 的中位数，不再重新调参
```

### 3.4 Stage 3a 详细：谱域 η-weighted 融合

```
  w_m = η_m / Σ_{k∈active_modals} η_k   # η 归一化为权重

  S_fused(f) = Σ_{m∈active_modals} w_m · S_m(f)
  
  f_peak = argmax_{f∈[0.1,0.35]} S_fused(f)
  BPM = 60 · parabolic_peak(S_fused, f_peak)

  # 与现有 E3a 的区别: E3a 无条件三模态; 本管线先过闸门
```

### 3.5 Stage 3b 详细：波形 η-weighted coherent MRC

```
  # 第一级: Per-modal tone-level coherent MRC
  for m in active_modals:
    y_m(t) = coherent_mrc_fuse_tones(
      tones = filtered_tones[m],  # 72 tone
      weights = η_i · ρ_i,        # per-tone quality
      method = "hilbert",         # Hilbert 连续相位补偿
    )

  # 第二级: 跨模态 coherent MRC
  y_fused(t) = coherent_mrc_fuse_modals(
    waveforms = {m: y_m for m in active_modals},
    quality_weights = {m: η_m for m in active_modals},
    weight_mode = "eta_only",     # η-only, 非 η·ρ 或 η·coherence
  )

  # BPM: Welch PSD on y_fused, 寻峰
  # RMSE: sqrt(mean((y_fused_norm - gt_norm)²))
  #   y_fused_norm: z-score normalized
  #   gt_norm: z-score normalized GT waveform
```

---

## 4. Baseline 对比

### 4.1 谱域 Baseline（大部分已有，直接复用）

| Key | 描述性名称 | HKH BPM | CS rel% | 来源 | 需重跑? |
|-----|-----------|:------:|:------:|------|:------:|
| `draft_ms_remote` | **逐模态 Voting → Remote 单模态** | 0.376 | 11.23% | draft ablation + modal_quality_gating | **否** |
| `draft_ms_local` | **逐模态 Voting → Local 单模态** | 0.378 | 16.21% | 同上 | **否** |
| `draft_ms_phase` | **逐模态 Voting → Phase 单模态** | 2.191 | 10.92% | 同上 | **否** |
| `p0_rl_default` | **逐模态 Voting → R+L 等权谱融合** | 0.372 | 14.05% | Phase report | **否** |
| `draft_s_channel` | **逐模态 Voting → 三选一最优模态** | 0.381 | 12.51% | draft ablation | **否** |
| `e3a` | **逐模态 Voting → η-weighted 三模态谱融合（无闸门）** | 0.396 | 10.17% | modal_quality_gating | **否** |
| `draft_s_full` | **逐模态 Voting → 三模态等权谱融合** | 0.405 | 10.14% | draft ablation | **否** |

### 4.2 波形域 Baseline（仅 HKH）

| Key | 描述性名称 | HKH RMSE | 来源 | 需重跑? |
|-----|-----------|:------:|------|:------:|
| `draft_mw_remote` | **逐模态 MRC → Remote 单模态波形** | 0.931 | draft ablation | **否** |
| `draft_mw_local` | **逐模态 MRC → Local 单模态波形** | 0.947 | draft ablation | **否** |
| `draft_mw_phase` | **逐模态 MRC → Phase 单模态波形** | 1.109 | draft ablation | **否** |
| `rl_waveform` | **逐模态 MRC → R+L coherent MRC** | **?** | **新增** | **是** |
| `draft_w_full` | **逐模态 MRC → 三模态 coherent MRC** | 0.951 | draft ablation | **否** |

> ⚠️ CS 金属板无呼吸带 GT 波形，波形 RMSE 仅限 HKH。CS 仅评估 spectral BPM relative error。

### 4.3 待测方法（本 plan 新增）

| Key | 描述性名称 | 说明 |
|-----|-----------|------|
| `candidate_a` | **Amplitude-only BreatheCS：Voting (η·ρ) → R+L η-weighted 谱/波形融合** | Candidate A — 最简配置 |
| `candidate_b` | **Phase-gated BreatheCS：Voting (η·ρ) → Phase 闸门 → η-weighted 谱/波形融合** | Candidate B — Phase 条件性参与 |
| `rl_waveform` | **逐模态 MRC → R+L coherent MRC（无 Phase，无闸门）** | 波形对照 |

### 4.4 核心对比矩阵

| 对比 | 域 | 问题 |
|------|-----|------|
| `candidate_a` vs `draft_ms_remote` | HKH | R+L (0.372) 是否稳定复现且优于 Remote (0.376)？ |
| `candidate_a` vs `draft_s_full` | HKH | R+L 是否明显优于等权三模态 (0.405)？ |
| `candidate_b` vs `candidate_a` | HKH | Gate 是否在 held-out 上不劣于 R+L？ |
| `candidate_b` vs `candidate_a` | CS | Gate 是否在 CS 上自动启用 Phase → 恢复三模态优势？ |
| `rl_waveform` vs `draft_mw_remote` | HKH | R+L waveform RMSE 是否优于 Remote-only 0.931？ |

---

## 5. 评估设计

### 5.1 场景

| 数据 | 场景 | 用途 | 指标 |
|------|------|------|------|
| **HKH 真人** | 3 Room × 4 Subject = 12 条 | 主评估 | BPM abs err + waveform RMSE |
| **CS 金属板** | `cs_091339` / `cs_095806` / `cs_102621` | 跨域对照（谱域 BPM only） | BPM rel err % |

> ⚠️ CS 无波形 GT，仅评估 spectral BPM relative error。HKH 和 CS 分表/分图。HKH 用 abs err, CS 用 rel %。

### 5.2 指标

| 指标 | 域 | 说明 |
|------|-----|------|
| BPM abs err mean ± std | HKH | recording-level mean (breaths/min) |
| BPM rel err % mean ± std | CS | recording-level mean (%) |
| Waveform RMSE mean ± std | HKH only | z-score normalized, recording-level |
| R+L waveform RMSE vs Remote RMSE | HKH | paired difference per recording |
| Phase 激活率 | HKH + CS | Phase 通过闸门的窗占比（Candidate B only） |
| LOSO gate threshold stability | HKH | 各 fold 所选 θ 的一致性 |
| Subject-cluster bootstrap CI | HKH | B=10000, cluster=subject, CI 95% for paired differences |

### 5.3 决策标准（选择 Candidate A 还是 B）


**选择 Candidate A (Amplitude-only, R+L) 为主方法，如果：**

- R+L 在 HKH 上优于或不劣于 Remote-only (0.376)
- R+L 明显优于等权三模态 (0.405)
- Candidate B (gated) 相对 Candidate A 无 out-of-sample 实质收益（差值 < 0.02 BPM）
- LOSO 阈值不稳定或跨 fold 波动大
- 某条 recording 因 gate 出现明显退化

**选择 Candidate B (Phase-gated) 为主方法，如果：**

- HKH out-of-sample 结果不劣于 Candidate A（差值 < 0.02 BPM）
- CS 上 Candidate B 明显优于 Candidate A（Phase 通过闸门恢复三模态优势）
- 各 LOSO fold 所选 θ 稳定（max − min ≤ 0.05）
- Gate 行为与 conf 分布一致（HKH 低 conf → gate 关闭；CS 高 conf → gate 开启）
- 无 recording 级灾难性退化

**波形分支决策：**

| 条件 | 选择 |
|------|------|
| R+L waveform RMSE < Remote 0.931（多数 recording 改善） | R+L coherent MRC |
| R+L waveform RMSE ≈ Remote 0.931 或更差 | Remote-only waveform |

"不劣"容忍范围：BPM 差值 < 0.02–0.03 breaths/min，不应仅依赖 p-value。

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 | 操作 |
|------|------|------|
| 实验脚本 | `notebooks/scripts/chFusion_unified_pipeline.py` | **新建** |
| 模态融合（谱域） | `src/ble_analysis/systematic_fusion.py` | **扩展**：新增 `modal_fusion_from_spectra(weight_mode="eta_only")` |
| 闸门逻辑 | `src/ble_analysis/phase_adaptive_gating.py` | **扩展**：新增 `gate_by_confidence(conf, theta)` |
| B3 Pipeline | `src/ble_analysis/b3_pipeline.py` | **扩展**：`UNIFIED_PIPELINE_SPECS` 追加新变体 |
| 波形 MRC | `src/ble_analysis/coherent_mrc.py` | **复用**：`coherent_mrc_fuse_modals(weight_mode="eta_only")` |

### 6.2 新增/修改函数签名

```python
# === Stage 2: Phase confidence gate ===

def gate_by_confidence(
    conf_per_modal: dict[str, float],
    theta_conf: float = 0.35,
) -> set[str]:
    """
    返回通过闸门的模态集合。
    
    Args:
        conf_per_modal: {"R": float, "L": float, "P": float}
        theta_conf: Phase confidence threshold
    
    Returns:
        {"R", "L"} or {"R", "L", "P"}
    """
    active = {"R", "L"}
    if conf_per_modal.get("P", 0.0) >= theta_conf:
        active.add("P")
    return active

# === Stage 3a: η-weighted spectral fusion ===

def modal_fusion_eta_only(
    spectra_map: dict[str, np.ndarray],  # {modal: spectrum}
    eta_map: dict[str, float],           # {modal: η}
    band_freqs: np.ndarray,
) -> tuple[float, np.ndarray]:
    """
    η-weighted spectral fusion.
    
    w_m = η_m / Σ η_k
    S_fused = Σ w_m · S_m
    
    Returns (bpm, fused_spectrum).
    """
    ...

# === LOSO gate threshold search ===

def loso_gate_threshold(
    recordings: list[str],
    theta_candidates: list[float] = [0.30, 0.35, 0.38, 0.40],
) -> dict[str, float]:
    """
    Leave-one-subject-out gate threshold selection.
    
    Returns:
        {subject_id: best_theta}
    """
    ...
```

### 6.3 不做的事

- 不引入新的信道融合策略（Voting 已确认最优）
- 不引入新的质量指标
- 不调整滤波参数
- 不在本 plan 中修改 B2 MRC 内部逻辑
- 不做 exhaustive 超参数搜索（仅 4 个 θ 候选值）
- 不新建场景 JSON

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| **谱域结果（HKH + CS）** | `outputs/reports/unified_pipeline_spectral_summary.json` |
| **波形结果（HKH only）** | `outputs/reports/unified_pipeline_waveform_hkh_summary.json` |
| **LOSO gate thresholds** | `outputs/reports/unified_pipeline_gate_loso.json` |
| **Per-recording 明细** | `outputs/reports/unified_pipeline_per_recording.csv` |
| **Phase 诊断数据** | `outputs/reports/unified_pipeline_phase_diagnostics.json` |
| **HKH 主性能图** | `outputs/figures/unified_pipeline_hkh_main.png`（Candidate A vs B + baselines, 谱域 + 波形分面） |
| **模态参与消融图** | `outputs/figures/unified_pipeline_modal_ablation.png`（Remote/Local/Phase/R+L/R+L+P/gated） |
| **Phase 可靠性诊断图** | `outputs/figures/unified_pipeline_phase_reliability.png`（conf 分布, rescue/destruction, oracle, gate activation） |
| **Per-recording 配对差异图** | `outputs/figures/unified_pipeline_paired_diff.png`（Candidate B − Candidate A, R+L waveform − Remote waveform） |
| **CS 谱域 BPM 图** | `outputs/figures/unified_pipeline_cs_spectral.png`（仅 BPM rel error，无 waveform RMSE） |
| **验证报告** | `docs/reports/unified_pipeline_final_report.md` |

### 7.1 建议运行命令

```bash
python notebooks/scripts/chFusion_unified_pipeline.py
```

---

## 8. 验证状态与保留问题

> 由 **执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | **已完成**（2026-07-26） |
| **实际脚本** | `notebooks/scripts/chFusion_unified_pipeline.py` |
| **报告链接** | [`docs/reports/unified_pipeline_final_report.md`](../reports/unified_pipeline_final_report.md) |
| **一句话结论** | 4/4 LOSO fold 选 θ=+∞ → Candidate B≡A；推荐 Amplitude-only（Voting→R+L η-weighted）为主方法；CS 上三模态优势无法由当前 conf 闸门自动恢复。 |

### 实际产出路径

- 谱域：`outputs/reports/unified_pipeline_spectral_summary.json`
- LOSO：`outputs/reports/unified_pipeline_gate_loso.json`
- 波形：`outputs/reports/unified_pipeline_waveform_hkh_summary.json`
- 诊断：`outputs/reports/unified_pipeline_phase_diagnostics.json`
- CSV：`outputs/reports/unified_pipeline_per_recording.csv`
- 图：`outputs/figures/unified_pipeline_*.png`

### 关键数字（执行回填）

| 域 | 方法 | 指标 | 值 |
|----|------|------|-----:|
| HKH | Candidate A / B | BPM abs err | **0.3717** |
| HKH | Remote | BPM abs err | 0.3760 |
| HKH | Equal-3 | BPM abs err | 0.4050 |
| HKH | LOSO θ | — | **4/4 = +∞** |
| CS | Candidate A / B (θ=+∞) | BPM rel % | 12.80 |
| CS | Equal-3 | BPM rel % | **10.14** |
| HKH | R+L waveform | window-mean RMSE | 0.937 |
| HKH | Remote waveform | window-mean RMSE | 0.931 |
| HKH | R+L waveform | recording-level RMSE | **0.666** |

### 保留问题（执行后）

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | R+L waveform RMSE 是否优于 Remote-only 0.931？ | window-mean：否（0.937≈0.931）；recording-level：是（0.666\<0.684） |
| Q2 | Candidate B 在 held-out HKH 上是否不劣于 A？ | 是，但因 θ=+∞ 而完全相同，无增益 |
| Q3 | Candidate B 在 CS 上是否自动启用 Phase？ | **否**（θ=+∞，激活率 0） |
| Q4 | LOSO θ 是否稳定？最常被选是否为 +∞？ | **是：4/4 +∞** → Phase 不应进入主方法 |
| Q5 | Candidate A 的 R+L 0.372 是否复现？ | **是（0.3717）** |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，按以下顺序执行：

1. **先读** `docs/plans/unified_pipeline_final_plan.md`（本文件）全文
2. **组装 Candidate A (Amplitude-only)**：
   - 复用 Voting (η·ρ)，见 `systematic_fusion.py` 和 `b3_pipeline.py`
   - `modal_fusion_from_spectra(weight_mode="eta_only", active_modals={"R","L"})`
   - 注册为 `candidate_a`
3. **组装 Candidate B (Phase-gated)**：
   - 新增 `gate_by_confidence(conf, theta)` → `phase_adaptive_gating.py`
   - `modal_fusion_from_spectra(weight_mode="eta_only", active_modals=gate_result)`
   - 注册为 `candidate_b`
4. **LOSO 闸门阈值**：
   - 4-fold leave-one-subject-out on HKH（每 fold 留 1 subject = 3 recordings）
   - θ ∈ {0.30, 0.35, 0.38, 0.40, **+∞**}（+∞ = Candidate A）
   - Tie-breaking：多 θ 接近时选 Phase 激活率更低的
5. **全量评估**：
   - HKH 12: `candidate_a`, `candidate_b`, `rl_waveform`
   - CS 3: `candidate_a`, `candidate_b`（**仅谱域 BPM**，CS 无波形 GT）
   - CS 用固定 θ_conf = HKH 4 个 LOSO fold 所选 θ 的中位数
6. **波形 RMSE 协议（必须冻结）**：
   - z-score per-recording（非 per-window）
   - 仅允许 recording-level 固定时间偏移和全局 polarity
   - 不允许逐窗用 GT 调整 lag、sign 或融合相位
   - 所有方法使用同一对齐协议
   - overlapping window 拼接方式固定
7. **统计报告**：
   - 性能汇总：12-recording mean ± std
   - CI：subject-cluster bootstrap (B=10000, cluster=subject)
   - 报告逐 recording 差值、最坏退化、Phase 激活率
8. **撰报告**：按 `docs/templates/algorithm_validation_report.md` 写 `docs/reports/unified_pipeline_final_report.md`
9. **回填本 plan §8**

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/unified_pipeline_final_plan.md`
- `docs/reports/unified_pipeline_final_report.md`
- `outputs/reports/unified_pipeline_*`
- `outputs/figures/unified_pipeline_*`
- 关键脚本路径
- git commit message

> ⚠️ **关键提醒**：
> - HKH 和 CS **必须分表/分图**
> - HKH 4 subjects × 3 recordings = 12 recordings（非 12 个独立样本）
> - BPM abs err for HKH, rel% for CS
> - **CS 不测 waveform RMSE**（无呼吸带 GT 波形）
> - η 在高通信号上计算，ρ 和 BPM 在带通信号上计算
> - Gate confidence 固定定义：`max_bin_weighted_votes / total_weighted_votes`
> - LOSO θ 候选**必须包含 +∞**（Phase 永不启用 = Candidate A）
> - 本实验的最终目的是在 Candidate A 和 Candidate B 之间做选择，不是证明 Candidate B 最优
