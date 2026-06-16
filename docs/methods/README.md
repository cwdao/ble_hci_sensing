# BLE CS 呼吸感知 — 方法注册表

> **用途**：记录当前已验证的全部方法，标注物理自洽性、实现位置、实验结论和维护状态。  
> **更新规则**：新实验产生可部署的方法或推翻既有结论时，更新本文档对应条目。  
> **最后更新**：2026-06-16

---

## 1. 当前推荐方法

### 1.1 物理自洽最优：B1 Vote→Equal (8.45%)

| 字段 | 内容 |
|------|------|
| **代号** | B1（Systematic B1 = `b1_vote_modal_equal`） |
| **描述性全称** | 逐模态 η·ρ Voting → 三模态等权谱融合 |
| **跨域 mean** | **8.45%**（cs_091339: 13.22%, cs_095806: 6.50%, cs_102621: 5.63%） |
| **物理自洽性** | ✅ 自洽 — 两层均为质量驱动 + 对称对待 |
| **信道融合** | 逐模态 η·ρ Voting（per-tone 质量加权直方图投票 → conf 加权谱平均） |
| **模态融合** | Equal（remote_amp : local_amp : phase = 1:1:1） |
| **门控** | 无 |
| **实现** | `src/ble_analysis/systematic_fusion.py` → `per_modal_voting_spectrum()` + `modal_fusion_from_spectra(weight_mode="equal")` |
| **Plan** | [`docs/plans/systematic_modal_channel_fusion_plan.md`](../plans/systematic_modal_channel_fusion_plan.md) |
| **Report** | [`docs/reports/systematic_modal_channel_fusion_report.md`](../reports/systematic_modal_channel_fusion_report.md) |
| **成果汇报** | [`docs/achievements/systematic_modal_channel_fusion_achievement_report.md`](../achievements/systematic_modal_channel_fusion_achievement_report.md) |
| **实现指南** | [`docs/methods/b1_implementation_guide.md`](b1_implementation_guide.md) — 从原始信号到 BPM 的完整教程 |
| **状态** | ✅ **推荐部署（跨域默认）** |

**为何是"物理自洽最优"**：

- 信道融合：η·ρ 是 per-tone per-window 的信号质量代理——权重由每窗实际数据动态决定
- 模态融合：1:1:1 等权——不预设 remote 优于 local 或 phase，遵循"三种变量对称对待"原则
- 无硬编码 fallback、无预设模态偏好

**已知限制**：
- 102621 上 5.63% vs G4 4.51%（差 1.12 pp）— 该场景下门控 fallback→Remote 恰好有效
- 091339 上 13.22% — 所有方法在此场景 >12%，非 B1 特有问题

---

## 2. 方法排行榜（跨域 mean 升序）

| 排名 | 代号 | 描述性名称 | 跨域 mean | 091339 | 095806 | 102621 | 物理自洽 | 状态 |
|------|------|-----------|-----------|--------|--------|--------|----------|------|
| 1 | G4-B1-v2 | 窗级门控：三候选最近对共识 | 8.05% | 12.36 | 6.31 | 5.50 | ❌ fallback 硬编码 Remote | 实验（不推荐） |
| 2 | **B1** | **逐模态 Voting → 三模态等权谱融合** | **8.45%** | 13.22 | 6.50 | 5.63 | ✅ | **推荐** |
| 3 | G4 | 窗级门控：双候选共识→分歧回退 Single Remote | 8.65% | 12.39 | 9.05 | 4.51 | ❌ fallback 硬编码 Remote | 实验（不推荐） |
| 4 | T0-V3 | Per-Tone η·ρ 加权直方图投票（仅 Remote） | 9.20% | 13.77 | 6.84 | 6.99 | ⚠️ 仅 Remote 单模态 | Baseline |
| 5 | Modal top2 | 逐模态 max-η 最优信道 → Top2 等权谱融合 | 9.45% | 13.04 | 10.61 | 4.69 | ✅ | Baseline |
| 6 | B0 Single Remote | max-η 单信道（Remote 幅值） | 10.45% | 10.91 | 12.16 | 8.29 | ✅ | Baseline |
| 7 | B1 Uniform Remote | 72 tone 等权谱平均（Remote 幅值） | 11.02% | 17.09 | 9.15 | 6.82 | ✅ | Baseline |

> **物理自洽判定标准**（来自 CLAUDE.md）：  
> ✅ remote/local 物理对等，不得硬编码偏好；三种变量对称对待；决策由 per-window 信号质量动态驱动。  
> ⚠️ 部分违反（如仅使用单一模态，但不硬编码哪一 modal 更优）。  
> ❌ 硬编码特定模态/信道偏好，或将特定场景下的经验有效性强加为通用规则。

---

## 3. Baseline 方法（定义与实现）

以下方法构成项目的最简方法集。所有新实验必须至少包含这些 baseline 作为参照。

### 3.1 B0 — Single Remote

| 字段 | 内容 |
|------|------|
| **描述** | 每窗选 η 最大的 tone，对其 Remote 幅值 bandpass 波形做 FFT 寻峰 |
| **跨域 mean** | 10.45% |
| **实现** | `src/ble_analysis/chfusion.py` → `estimate_segment_bpm_methods(methods=("single",), variable="remote_amplitudes")` |
| **单信道选择** | `_find_best_channel(channel_metric="energy_ratio")` |
| **模态** | 仅 Remote 幅值 |
| **物理自洽** | ✅ — 不硬编码特定 tone，max-η 每窗动态选择 |
| **备注** | 最简基线；在 091339 上 10.91% 意外地强（该场景 Remote 恰好优） |

### 3.2 B1 (old) — Uniform Remote

| 字段 | 内容 |
|------|------|
| **描述** | 72 tone 的 Remote 幅值归一化频谱等权平均后寻峰 |
| **跨域 mean** | 11.02% |
| **实现** | `src/ble_analysis/chfusion.py` → `estimate_segment_bpm_methods(methods=("uniform",), variable="remote_amplitudes")` |
| **模态** | 仅 Remote 幅值 |
| **物理自洽** | ✅ |
| **备注** | 等权不加质量区分——劣质 tone 同等贡献。被 B1（η·ρ 加权）系统性超越 |

### 3.3 B2 — Modal top2 equal

| 字段 | 内容 |
|------|------|
| **描述** | 逐模态选 max-η 最优信道 → 三模态各得一条谱 → 按 η 取 top2 模态等权谱融合 → 寻峰 |
| **跨域 mean** | 9.45% |
| **实现** | `src/ble_analysis/chfusion.py` → `estimate_modal_best_channel_fusion(weight_mode="top2_equal")` |
| **信道融合** | Single best per modal（逐模态 max-η 单信道） |
| **模态融合** | Top2 equal（每窗按 η 取前二模态，等权） |
| **物理自洽** | ✅ — Top2 每窗动态选择，不预设哪两个模态更优 |
| **备注** | Plan2 阶段最优；被 Voting 系列超越后降为 baseline |

### 3.4 B3 — Modal η-weight

| 字段 | 内容 |
|------|------|
| **描述** | 同 Modal top2，但模态融合改为三模态 η 加权（不踢出第三模态） |
| **跨域 mean** | 9.45%（与 B2 相同） |
| **实现** | `src/ble_analysis/chfusion.py` → `estimate_modal_best_channel_fusion(weight_mode="energy_ratio")` |
| **备注** | 与 B2 性能持平——在 Single-best 信道策略下 η-weight 和 top2 equal 无显著差异 |

### 3.5 T0-V3 — Per-Tone η·ρ Voting

| 字段 | 内容 |
|------|------|
| **描述** | 72 tone 各自独立估计 BPM → η·ρ 加权直方图投票（仅 Remote 模态） |
| **跨域 mean** | 9.20% |
| **实现** | `src/ble_analysis/voting_fusion.py` → `VotingConfig(voting_strategy="eta_rho_weighted")` |
| **模态** | 仅 Remote 幅值 |
| **物理自洽** | ⚠️ — 信道融合质量驱动，但仅用 Remote 单模态 |
| **备注** | Deng 2024 范式的 BLE CS 实现；095806 上 6.84% 极强，但 091339 上退化 |

---

## 4. 实验性方法（记录但不推荐部署）

### 4.1 G4 — Single fallback gating (8.65%)

| 字段 | 内容 |
|------|------|
| **描述** | 窗级：T0-V3 与 Modal top2 一致 → 加权平均；不一致 → 回退 Single Remote |
| **跨域 mean** | 8.65% |
| **实现** | `src/ble_analysis/consensus_gating.py` → `GatingConfig(strategy="single_fallback")` |
| **不推荐原因** | ❌ 分歧时硬编码回退 Single Remote — 违反 remote/local 物理对称性原则。102621 上 4.51% 可能是该场景 Remote 恰好最优的巧合 |
| **Plan** | [`docs/plans/voting_gating_plan.md`](../plans/voting_gating_plan.md) |
| **Report** | [`docs/reports/voting_gating_report.md`](../reports/voting_gating_report.md) |

### 4.2 G4-B1-v2 — 三候选最近对共识 (8.05%)

| 字段 | 内容 |
|------|------|
| **描述** | G4 的扩展：第三候选加入 B1 → 三候选（T0-V3 / Modal top2 / B1）最近一对共识 |
| **跨域 mean** | 8.05% |
| **实现** | `src/ble_analysis/b1_gating_diagnosis.py` → `_g4_b1_decision()` |
| **不推荐原因** | ❌ 共识失败时同 G4 — fallback 到 Single Remote |
| **Plan** | [`docs/plans/b1_gating_and_diagnosis_plan.md`](../plans/b1_gating_and_diagnosis_plan.md) |
| **Report** | [`docs/reports/b1_gating_and_diagnosis_report.md`](../reports/b1_gating_and_diagnosis_report.md) |

### 4.3 G5 — 双峰性门控 (8.72%)

| 字段 | 内容 |
|------|------|
| **描述** | Voting BPM 分布双峰时回退 Modal（不含硬编码 Remote） |
| **跨域 mean** | 8.72% |
| **备注** | 091339 最优（12.27%）— 双峰检测命中了 voting 多簇竞争模式。但 102621 退化。物理上无硬编码问题，但跨域未超越 B1 |

### 4.4 X1–X7 — 互谱合并 (12.25–14.95%)

| 字段 | 内容 |
|------|------|
| **描述** | 将 B1 的功率谱加权平均替换为 tone 间互功率谱合并（magnitude/real/coherent × 全对/Δk=1/Δk=5） |
| **跨域最优** | 12.25%（X3 coherent） |
| **不推荐原因** | 全局劣于 B1 — tone 间 cos(φᵢ−φⱼ) 在多径下不满足同相假设 |
| **Plan** | [`docs/plans/cross_spectrum_combining_plan.md`](../plans/cross_spectrum_combining_plan.md) |
| **Report** | [`docs/reports/cross_spectrum_combining_report.md`](../reports/cross_spectrum_combining_report.md) |
| **状态** | ❌ 已废弃方向。待 [`cross_spectrum_failure_diagnosis_plan.md`](../plans/cross_spectrum_failure_diagnosis_plan.md) 确认失效机制 |

### 4.5 SA 系列 — 信号自适应门控 (10.66%)

| 字段 | 内容 |
|------|------|
| **描述** | 基于 per-window 信号特征（三候选一致性 / η 质量）自动选择门控策略 |
| **跨域 mean** | 10.66%（SA-v2 最优） |
| **不推荐原因** | 未超越 B1 (8.45%) |
| **Plan** | [`docs/plans/signal_adaptive_gating_plan.md`](../plans/signal_adaptive_gating_plan.md) |
| **Report** | [`docs/reports/signal_adaptive_gating_report.md`](../reports/signal_adaptive_gating_report.md) |

### 4.6 Vote→Top2 系列 (B3, 9.92%)

| 字段 | 内容 |
|------|------|
| **描述** | 逐模态 Voting → Top2 模态融合 |
| **不推荐原因** | Voting 降低模态间频谱相似度 → Top2 选择退化为随机剔除 → Equal (B1) 严格优于 Top2 (B3) |
| **诊断发现** | B1 的模态间频谱余弦相似度 0.864 vs Single-best 0.772（091339）— 机制级解释见 [`b1_gating_and_diagnosis_achievement_report.md`](../achievements/b1_gating_and_diagnosis_achievement_report.md) §D1 |

---

## 5. 物理自洽性判定细则

判断一个方法是否"物理自洽"，逐项检查下表。来自 CLAUDE.md 第 2 节。

| # | 检查项 | B1 | G4 | G4-B1-v2 | Modal top2 | T0-V3 |
|---|--------|----|----|----------|------------|-------|
| 1 | remote/local 对称对待 | ✅ | ❌ | ❌ | ✅ | ⚠️ |
| 2 | 三种变量对称对待 | ✅ | ❌ | ❌ | ✅ | ❌ |
| 3 | 信道/模态选择由 per-window 信号质量动态决定 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 | 无硬编码 fallback 到特定模态/信道 | ✅ | ❌ | ❌ | ✅ | ✅ |
| 5 | 不使用总幅值（无独立物理意义） | ✅ | ✅ | ✅ | ✅ | ✅ |

**判定**：
- 全部 ✅ → 物理自洽，可推荐部署
- 任一项 ❌ → 标记为"实验性"，不推荐部署（无论跨域 mean 多低）

---

## 6. 场景与参数

所有方法共用：

| 参数 | 值 |
|------|-----|
| 滑窗 | 20 s 窗长 / 1 s 步长 |
| 滤波链 | median → highpass (0.05 Hz) → bandpass (0.1–0.35 Hz) |
| 呼吸频段 | 0.1–0.35 Hz (6–21 BPM) |
| FFT | rFFT, Hanning 窗, nfft = next_pow2(4 × win_len) |
| 寻峰 | argmax + parabolic 插值 |

| 场景 | 数据文件 | 特点 |
|------|----------|------|
| cs_091339 | `CS_frames_all_20260113_091339.jsonl` | 复杂多径，所有方法 >12% |
| cs_095806 | `CS_frames_all_20260116_095806.jsonl` | Voting 优势场景 |
| cs_102621 | `CS_frames_all_20260116_102621.jsonl` | 跨域对照 |

---

## 7. 模块与脚本索引

| 模块 | 实现的方法 |
|------|-----------|
| `chfusion.py` | B0 Single, B1 Uniform, B2 Modal top2, B3 Modal η-weight, 公共滤波/寻峰/评估 |
| `voting_fusion.py` | T0-V1/V2/V3, T1-K4/K8/K16, T2, T3（per-tone voting 系列） |
| `systematic_fusion.py` | B1 Vote→Equal, B2 Vote→η, B3 Vote→Top2, C1, C2, A1, A2, B4 |
| `consensus_gating.py` | G1–G6（窗级门控系列） |
| `b1_gating_diagnosis.py` | G4-B1-v1/v2/v3/v4, G5-B1, D1–D3 诊断 |
| `signal_adaptive_gating.py` | SA-v1, SA-v2 |
| `cross_spectrum.py` | X0–X7（互谱合并系列） |
| `pca_svd.py` | PCA/SVD 降维系列 |
| `segments.py` | 滑窗、分段、滤波参数 |
| `metrics.py` | 评估指标（`_overall_rel_error`, `_seg_bpm_stats`） |

---

## 8. 更新日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-06-16 | 初版 | 汇总 Voting → Gating → Systematic → Cross-Spectrum 全部实验结论 |
| 2026-06-16 | B1 标记为推荐；G4/G4-B1-v2 标记为实验（不推荐） | 物理自洽性审查——硬编码 Remote fallback |
| 2026-06-16 | 互谱 X1–X7 标记为已废弃 | 跨域 12.25–14.95%，全局劣于 B1 |
