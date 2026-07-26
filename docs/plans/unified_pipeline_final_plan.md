# BreatheCS 统一管线：多尺度质量加权分集合并 — 实现计划

> **来源**：Phase 互补投影实验 (`phase_unique_role_adaptive_fusion`) + 消融矩阵 (`paper_ablation_draft_align`) + 模态质量门控 (`modal_quality_gating`) + 波形 MRC (`b2_coherent_mrc`)  
> **目标报告**：`docs/reports/unified_pipeline_final_report.md`  
> **日期**：2026-07-26  
> **验证状态**：待实现

---

## 1. 动机与背景

| 项目 | 说明 |
|------|------|
| **问题** | 经过 6 轮实验（Voting → 模态融合 → 质量门控 → Phase 互补投影 → 消融矩阵 → 波形 MRC），各项组件的最优策略已各自验证，但尚未整合为一条统一的、有理论支撑的 BreatheCS 管线。本次实验是**管线设计的收尾**：将已验证的最优组件组合为完整的谱域+波形双管线，用最终实验确认性能。 |
| **定位** | **验证性实验，非探索性实验**。所有组件的最优性已在既往实验中分别验证，本实验仅需组装+确认。大部分预期性能可直接从已有数据推断（见 §1.3）。需要新增的测量仅限波形域的 R+L 组合（HKH + CS），以及 Phase 闸门阈值的 LOSO 验证。 |
| **理论框架** | Multi-Scale Quality-Weighted Diversity Combining（§2.3）——管线不是经验的堆砌，有统一的物理/统计基础，可直接用于论文写作。 |

### 1.1 已有实验支撑（每个设计选择的证据来源）

| 管线组件 | 选择 | 证据实验 | 关键数字 |
|----------|------|----------|----------|
| 信道融合策略 | Voting (η·ρ) | `systematic_fusion` + `paper_ablation_draft_align` | Voting (0.381) ≫ Uniform (1.640) |
| 模态级质量度量 | η-only（非 η·ρ） | `modal_quality_gating` E2 | η hit 63.6% > η·ρ hit 54.3% |
| Phase 闸门指标 | Voting confidence（非 η） | `phase_unique_role_adaptive_fusion` E5 | H5a 否（η 不区分域），H5c 是（conf 区分） |
| Phase 闸门阈值 | θ_conf ~0.35 | `phase_unique_role_adaptive_fusion` E5 | HKH 0.324 vs CS 0.402 |
| 模态融合算子 | η-weighted spectral avg | `modal_quality_gating` E3a | CS E3a 10.17% ≈ Equal 10.14% |
| R+L 谱域基线 | R+L equal = 0.372 | `phase_unique_role_adaptive_fusion` p0_rl_default | HKH 最优 |
| 波形 MRC | coherent MRC (Hilbert) | `b2_coherent_mrc` | B2-D 9.43% CS |
| 波形单模态基线 | Remote RMSE 0.931 | `paper_ablation_draft_align` | HKH 波形天花板 |

### 1.2 本次实验需新增的测量

| 测量项 | 原因 | 域 |
|--------|------|-----|
| R+L 波形 RMSE | 已有 Remote/Local 单模态波形 RMSE,但没有 R+L 组合 | HKH |
| CS 波形单模态 RMSE (Remote/Local/Phase) | B2 MRC 报告了融合后的 CS 波形，但没有单模态基线 | CS |
| CS R+L 波形 RMSE | 同上 | CS |
| Phase gate + η-weighted full pipeline | 各组件分别验证过，但组合后未跑过一次完整实验 | HKH + CS |
| Gate threshold LOSO | θ_conf 在全部数据上观察到 0.35 可分，未做 leave-one-subject-out | HKH |

### 1.3 预期性能（可推断部分）

| 管线 | 域 | 指标 | 预期值 | 推断来源 |
|------|-----|------|:------:|------|
| 谱域 gate+η | HKH | BPM abs err | **~0.372** | `p0_rl_default` — Phase gated out, η-weighted R+L ≈ equal R+L（R/L η 接近） |
| 谱域 gate+η | CS | BPM rel % | **~10.14–10.17%** | `E3a`（η-weighted 3-modal）— Phase passes gate on CS |
| 波形 gate+η | HKH | RMSE | **~0.91–0.93** | Remote alone=0.931；R+L coherent MRC 预期略优或持平 |
| 波形 gate+η | CS | RMSE | **N/A** | CS 金属板**无呼吸带 GT 波形**，波形 RMSE 仅限 HKH |

> ⚠️ 谱域预期值实质上**已经被测量过**（`p0_rl_default` = 0.372, `E3a` = 10.17%）。本次实验的谱域部分是**组装确认**，不是新发现。波形域仅 HKH（CS 无 GT 波形）。

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

这是样本量驱动的正则化需求，不是工程巧合。设 ρ 以概率 p 误选假峰，误选对融合的污染期望为 p/N。N=72 → 可忽略；N=3 → 不可忽略。E4 数据直接验证：模态级 η-only hit (63.6%) > η·ρ hit (54.3%)。

### 2.3 符号约定

| 符号 | 含义 |
|------|------|
| η_m | 模态 m 融合波形的呼吸频段能量比 |
| ρ_m | 模态 m 融合波形的谱峰峰度（⚠️ 奖励尖峰，包括尖锐假峰） |
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
  │ Stage 2 — Phase 投影闸门 (Projection Gate)                                │
  │                                                                          │
  │   IF conf_P < θ_conf:                                                    │
  │       w_P = 0  (Phase excluded — 切向投影无足够跨 tone 相干证据)         │
  │       模态集合 M_active = {R, L}                                         │
  │   ELSE:                                                                  │
  │       模态集合 M_active = {R, L, P}                                      │
  │                                                                          │
  │   θ_conf 由 LOSO 在训练集上确定（扫描 {0.30, 0.35, 0.38, 0.40}）        │
  │                                                                          │
  │   [模块: phase_adaptive_gating.py → 新增 gate_by_confidence()]          │
  │   [证据: E5 HKH conf 0.324 < CS 0.402; H5c validated]                   │
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
     conf_m = (最高 bin 票数) / (总票数)  # 或用原 Voting 输出的 confidence
     ρ_m = S_m(f_peak) / mean_{f∈[0.1,0.35]} S_m(f)
```

### 3.3 Stage 2 详细：Phase 闸门

```
对每个窗口 w:

  conf_P = Voting confidence from Stage 1 (Phase modal)
  
  # 判定
  if conf_P < θ_conf:
      active_modals = {"R", "L"}
      gate_log[w] = "phase_excluded"
  else:
      active_modals = {"R", "L", "P"}
      gate_log[w] = "phase_included"

  # θ_conf 确定方式（LOSO）:
  #   for each held-out subject s:
  #     在其余 9 条 recording 上扫描 θ ∈ {0.30, 0.35, 0.38, 0.40}
  #     选使 train BPM 最优的 θ
  #     在 held-out subject 的 3 条 recording 上评估
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

### 4.2 波形域 Baseline

| Key | 描述性名称 | HKH RMSE | CS RMSE | 来源 | 需重跑? |
|-----|-----------|:------:|:------:|------|:------:|
| `draft_mw_remote` | **逐模态 MRC → Remote 单模态波形** | 0.931 | N/A | draft ablation | **否** |
| `draft_mw_local` | **逐模态 MRC → Local 单模态波形** | 0.947 | N/A | draft ablation | **否** |
| `draft_mw_phase` | **逐模态 MRC → Phase 单模态波形** | 1.109 | N/A | draft ablation | **否** |
| `rl_waveform` | **逐模态 MRC → R+L coherent MRC** | **?** | N/A | **新增** | **是** |
| `draft_w_full` | **逐模态 MRC → 三模态 coherent MRC** | 0.951 | N/A | draft ablation | **否** |

> ⚠️ CS 金属板无呼吸带 GT 波形，所有波形 RMSE 指标仅限 HKH。

### 4.3 待测方法（本 plan 新增）

| Key | 描述性名称 | 说明 |
|-----|-----------|------|
| `unified_spectral` | **MS-QWDC 谱域管线：Voting (η·ρ) → Phase 闸门 → η-weighted 谱融合** | §3.2–3.4 |
| `unified_waveform` | **MS-QWDC 波形管线：Voting (η·ρ) → Phase 闸门 → η-weighted coherent MRC** | §3.2, 3.3, 3.5 |
| `rl_waveform` | **逐模态 MRC → R+L coherent MRC（无 Phase，无闸门）** | 波形对照：确认闸门的价值 |

### 4.4 预期相对关系

| 对比 | 域 | 预期 | 理由 |
|------|-----|------|------|
| `unified_spectral` vs `draft_ms_remote` | HKH | **≤** (≈0.372 vs 0.376) | 闸门关闭→R+L; R+L≥Remote |
| `unified_spectral` vs `draft_s_full` | HKH | **<** (≈0.372 vs 0.405) | Phase 被闸门剔除, 免于被 2.191 污染 |
| `unified_spectral` vs `e3a` | HKH | **<** (≈0.372 vs 0.396) | 闸门关闭 vs 无条件三模态 η-加权 |
| `unified_spectral` vs `draft_s_full` | CS | **≈** (≈10.15% vs 10.14%) | Phase 通过闸门 → η-weighted ≈ equal 在 CS 上 |
| `unified_spectral` vs `p0_rl_default` | CS | **≪** (≈10.15% vs 14.05%) | Phase 参与融合在 CS 上至关关键 |
| `unified_waveform` vs `draft_mw_remote` | HKH | **≤** (≈0.92 vs 0.931) | R+L coherent MRC 预期略优或持平 Remote alone |
| `unified_waveform` vs `draft_w_full` | HKH | **<** (≈0.92 vs 0.951) | Phase 波形 1.109 被闸门剔除 |
| `rl_waveform` vs `draft_mw_remote` | HKH | **≤** | R+L vs Remote alone |

---

## 5. 评估设计

### 5.1 场景

| 数据 | 场景 | 用途 | 指标 |
|------|------|------|------|
| **HKH 真人** | 3 Room × 4 Subject = 12 条 | 主评估（谱域 + 波形） | BPM abs err (breaths/min) + waveform RMSE |
| **CS 金属板** | `cs_091339` / `cs_095806` / `cs_102621` | 跨域对照 | BPM rel err % + waveform RMSE |

> ⚠️ HKH 和 CS 必须分表/分图。HKH 用 abs err, CS 用 rel %。

### 5.2 指标

| 指标 | 域 | 管线 | 说明 |
|------|-----|------|------|
| BPM abs err mean ± std | HKH | 谱域 + 波形 | breaths/min, recording-level mean |
| BPM rel err % mean ± std | CS | 谱域 + 波形 | %, recording-level mean |
| Waveform RMSE mean ± std | 两者 | 波形 | z-score normalized, recording-level mean |
| Phase 激活率 | 两者 | 两者 | Phase 通过闸门的窗占比 |
| Phase 破坏率 | 两者 | 两者 | Phase 激活窗中 BPM 劣于 R+L 的占比 |
| Recording-level paired bootstrap | 两者 | 两者 | B=10000, CI 95% |
| LOSO gate threshold | HKH | 两者 | 每 fold 最优 θ_conf |

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | 谱域 HKH + CS 输出与预期一致（`unified_spectral` ≈ `p0_rl_default` on HKH, ≈ `e3a` on CS）；波形 HKH R+L RMSE 已测量 |
| **理想** | 谱域在 HKH 上不劣于 R+L, 在 CS 上不劣于 Equal；波形 RMSE ≤ Remote alone (0.931) on HKH |
| **突破** | 波形 R+L RMSE < 0.91 on HKH（说明 coherent MRC 有 real diversity gain） |

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
| **波形结果（HKH only）** | `outputs/reports/unified_pipeline_waveform_summary.json` |
| **LOSO gate thresholds** | `outputs/reports/unified_pipeline_loso_gates.json` |
| **HKH 排行榜图** | `outputs/figures/unified_pipeline_hkh_leaderboard.png`（谱域 + 波形分面） |
| **CS 排行榜图** | `outputs/figures/unified_pipeline_cs_leaderboard.png`（谱域 + 波形分面） |
| **Gate 行为图** | `outputs/figures/unified_pipeline_gate_behavior.png`（Phase 激活率 per recording, conf 分布） |
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
| **验证状态** | 待实现 |
| **实际脚本** | — |
| **报告链接** | — |
| **一句话结论** | — |

### 保留问题

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | R+L coherent MRC RMSE (HKH) 是多少？是否优于 Remote alone？ | 需首次测量 |
| Q2 | LOSO 闸门阈值是否稳健？CS 上 gate 行为是否符合预期（Phase 通过）？ | LOSO 仅在 HKH；CS 用固定 θ |
| Q3 | 谱域 `unified_spectral` 是否确实 ≈ `p0_rl_default` (HKH) 和 ≈ `e3a` (CS)？ | 组装确认 |
| Q4 | 波形 unified_waveform vs rl_waveform vs draft_mw_remote 的 HKH 对比 | Phased gated → 预期≈R+L |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，按以下顺序执行：

1. **先读** `docs/plans/unified_pipeline_final_plan.md`（本文件）全文
2. **组装谱域管线**：
   - 复用现有 Voting (η·ρ)，见 `systematic_fusion.py` 和 `b3_pipeline.py`
   - 新增 `gate_by_confidence()` → `phase_adaptive_gating.py`
   - 实现/扩展 `modal_fusion_from_spectra(weight_mode="eta_only")` → `systematic_fusion.py`
   - 在 `DRAFT_ABLATION_SPECS` 或新 `UNIFIED_PIPELINE_SPECS` 中注册 `unified_spectral`
3. **组装波形管线**：
   - 复用 `coherent_mrc.py` 的 tone-level + modal-level MRC
   - 将 modal-level weight_mode 扩展为 `"eta_only"`
   - 新增 `rl_waveform` 对照（无 Phase, 无闸门）
   - 注册 `unified_waveform` 变体
4. **LOSO 闸门阈值**：
   - 在 HKH 12 上做 leave-one-subject-out
   - 扫描 θ_conf ∈ {0.30, 0.35, 0.38, 0.40}
5. **全量评估**：
   - HKH 12: `unified_spectral`, `unified_waveform`, `rl_waveform`
   - CS 3: 同上 + CS 波形单模态基线 (Remote/Local/Phase) — **这是首次测量**
   - CS 用固定 θ_conf（从 HKH LOSO 中位数值确定，或直接用 0.35）
6. **撰报告**：按 `docs/templates/algorithm_validation_report.md` 写 `docs/reports/unified_pipeline_final_report.md`
7. **回填本 plan §8**

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/unified_pipeline_final_plan.md`
- `docs/reports/unified_pipeline_final_report.md`
- `outputs/reports/unified_pipeline_*`
- `outputs/figures/unified_pipeline_*`
- 关键脚本路径
- git commit message

> ⚠️ **关键提醒**：
> - HKH 和 CS 必须分表/分图
> - main statistical unit = recording (12 HKH / 3 CS), NOT sliding window
> - BPM abs err for HKH, rel% for CS
> - 波形 RMSE 用 z-score normalized
> - **CS 波形单模态基线 (Remote/Local/Phase RMSE) 需要首次测量**——此前只有 B2 MRC 融合结果，没有单模态 CS 波形
> - 谱域预期值已基本已知，这是确认实验而非探索实验
