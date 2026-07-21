# B3 统一管线（信道级 Voting BPM + 两级 Hilbert-MRC 波形）— 验证报告

> **Plan**：[`docs/plans/b3_unified_pipeline_voting_bpm_plan.md`](../plans/b3_unified_pipeline_voting_bpm_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_ble_hkh_b3_validation.py`（核心模块：`src/ble_analysis/b3_pipeline.py`）  
> **场景**：12 个 HKH 真人场景 `config/scenarios/room_{A,B,C}-sbj_{A,B,C,D}-*.json`  
> **日期**：2026-07-12  
> **状态**：已完成

---

## 1. 目标与假设

验证 B3 统一管线能否在保持 B2-D 波形质量（RMSE）的同时，用信道级 Voting BPM 避免 B2-D 在 outlier 场景上的 BPM 崩溃。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | B3-Full BPM ≤ B1 Vote→Equal（0.41），且 RMSE ≤ B2-D（0.950） | §5.2 最低成功标准 |
| H2 | B3-Full 在 A-D / C-A / B-C 三个问题场景上 BPM 显著优于 B2-D | §5.2 额外关注 |
| H3 | Full vs A1：Voting 压制 outlier tone，A1 显著更差 | §5.3 消融 |
| H4 | Full vs A2：Voting BPM 比波形 PSD BPM 更稳（std 更小） | §5.3 消融 |
| H5 | Full vs A4：Hilbert 相位对齐提升波形 RMSE | §5.3 消融 |

---

## 2. 方法摘要

> **2026-07-21 校订**：以下描述反映 B3 Simplified（最终推荐方案）。B3-Full 的 weighted_median 共识已被 equal spectral fusion 替代（见 §7.1）。

| 项目 | 内容 |
|------|------|
| 观测量 | `remote_amplitudes`、`local_amplitudes`、`phases`（不用 total amplitudes） |
| **BPM 路径** | Per-modal η·ρ 加权谱平均 → 三模态等权谱融合 (1:1:1) → argmax 寻峰 |
| **波形路径** | 两级 Hilbert-MRC（tone 级 + modal 级 Hilbert 相位对齐，去 coherence gate） |
| BPM 主输出 | 三模态 weighted_spectrum 等权融合寻峰（= B1 Vote→Equal，非 weighted_median） |
| 滑窗与寻峰 | 20 s / 1 s；呼吸频段 0.1–0.35 Hz；HKH GT 同口径 Welch 寻峰 |
| 诊断输出（不参与 BPM） | per-tone BPM 估计、直方图 Voting 标量结果、confidence、波形 PSD BPM |

实现采用 **wrapper 策略**（`b3_pipeline.py`），未修改 `coherent_mrc.py` / `wifi_mrc.py` / `systematic_fusion.py`。
- **η/ρ 双重计算**：BPM 路径和波形路径各自独立计算 η 和 ρ（~2% 额外开销，有意为之的工程取舍，见 plan §6.3）。

---

## 3. 实验设置

| 场景 ID | 布局 | 备注 |
|---------|------|------|
| `room_A-sbj_*` ×4 | 客厅坐姿 | 含问题场景 A-D |
| `room_B-sbj_*` ×4 | 卧室平躺 | 含问题场景 B-C |
| `room_C-sbj_*` ×4 | 卧室侧卧 | 含问题场景 C-A |

- **Baseline**：B1 Vote→Equal、B2-D Two-level、Zhuo Z1-no-VMD
- **待测**：B3-Full + Tier1/2 消融 A1–A7
- **指标**：窗级 BPM 绝对误差 mean±std（12 场景跨域）；窗级 RMSE（有波形变体）
- **GT**：HKH 带通波形，`fs = len/duration`

---

## 4. 结果

### 4.1 跨域主结果表（12 场景 mean）

数据来源：`outputs/reports/ble_hkh_b3_validation_summary.json`

| 方法 | BPM mean±std | RMSE mean | 波形 |
|------|-------------:|----------:|:----:|
| A4 等权谱融合 | **0.41±0.31** | N/A | ❌ |
| B1 Vote→Equal | **0.41±0.31** | N/A | ❌ |
| Zhuo Z1-no-VMD | 0.44±0.39 | 1.070 | ✅ |
| A5 等权投票 | 0.44±0.34 | 0.950 | ✅ |
| A7 跨模态全局 Voting | 0.46±0.36 | 0.950 | ✅ |
| A3 Remote only | 0.46±0.36 | 0.930 | ✅ |
| A6 无 coherence gate | 0.46±0.37 | 0.951 | ✅ |
| **B3-Full** | **0.46±0.37** | **0.950** | ✅ |
| A2 波形 PSD BPM | 0.68±0.84 | 0.950 | ✅ |
| B2-D Two-level | 0.68±0.84 | 0.950 | ✅ |
| A1 单信道 best-η | 0.96±1.28 | 0.950 | ✅ |

### 4.2 问题场景 BPM mean（breaths/min）

| 场景 | B3-Full | A2/B2-D | B1 | Δ(B3−B2) |
|------|--------:|--------:|---:|---------:|
| room_A-sbj_D | 0.65 | **2.31** | 0.60 | **−1.66** |
| room_C-sbj_A | 0.35 | **1.40** | 0.27 | **−1.05** |
| room_B-sbj_C | 0.74 | 0.73 | 0.71 | ≈0 |

B3 Voting BPM 在 A-D、C-A 上避免了 B2-D 的级联崩溃；B-C 两方法均 ~0.73，无显著差异。

### 4.3 与 plan 预期对比

| 预期（Plan §5.2） | 实际 | 是否一致 |
|-------------------|------|----------|
| B3 BPM ≤ 0.41（B1） | 0.46 | ❌ 略差 |
| B3 RMSE ≤ 0.950（B2-D） | 0.950 | ✅ 持平 |
| B3 std ≤ 0.20 | 0.37（跨场景 mean of std） | ❌ |
| A1/A2 劣于 Full | A1 0.96、A2 0.68 vs Full 0.46 | ✅ |

### 4.4 消融解读矩阵（Plan §5.3）

| 步骤 | 对比 | ΔBPM | ΔRMSE | 判定 |
|------|------|-----:|------:|------|
| η·ρ 权重 | Full vs A5 | 0.02 | 0.000 | **无显著效果** |
| 直方图 Voting | Full vs A1 | 0.50 | 0.000 | **有意义** |
| 三模态 | Full vs A3 | 0.00 | +0.020（A3 更优） | BPM 无增益；RMSE A3 略优 |
| Hilbert 相位对齐 | Full vs A4 | +0.06 | N/A | BPM 变差；RMSE 无法比 |
| Coherence gate | Full vs A6 | 0.00 | +0.001 | **无显著效果** |
| Voting BPM | Full vs A2 | 0.22（跨域） | 0.000 | **有意义**（outlier 场景 Δ>0.3） |
| per-modal 分组 | Full vs A7 | 0.00 | 0.000 | **无显著效果** |

### 4.5 图表

- 消融排行榜：`outputs/figures/ble_hkh_b3_ablation_leaderboard.png`
- BPM vs RMSE 散点：`outputs/figures/ble_hkh_b3_bpm_vs_rmse.png`
- 问题场景 BPM 时序：`outputs/figures/ble_hkh_b3_outlier_timeseries.png`

**关键现象**：

1. B3-Full 与 B2-D **RMSE 完全相同**（同一 Hilbert 波形管线），但 BPM mean 从 0.68 降至 0.46。
2. B3-Full BPM **未超越 B1/A4**（0.41）；模态共识（weighted median）略逊于 B1 的等权谱融合寻峰。
3. A2 与 B2-D BPM 数值完全一致（验证：波形 PSD BPM 路径复现 B2-D）。
4. A4 与 B1 数值完全一致（验证：谱融合路径与 systematic_fusion 一致）。

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| Voting BPM 可避免 B2-D 在 A-D/C-A 的 BPM 崩溃，同时保持 B2-D 波形 RMSE | **已验证** |
| B3-Full 跨域 BPM 未优于 B1 Vote→Equal（0.46 vs 0.41） | **已验证**（负面结论） |
| 直方图 Voting（vs 单信道 best-η）与 Voting BPM（vs 波形 PSD）两步均有显著价值 | **已验证** |
| η·ρ 权重、coherence gate、per-modal 分组对 12 场景跨域指标无显著增益 | **已验证** |
| B3-Full 成为全局 BPM 最优方法 | **未证实** |

**相对 baseline**：

- vs **B2-D**：BPM 明显更优（0.46 vs 0.68），RMSE 持平 → **B3 在需要波形+稳定 BPM 时优于纯 B2-D**。
- vs **B1**：BPM 略差（0.46 vs 0.41），但 B1 无波形 → **trade-off 成立，未实现「BPM 不输 B1 且多出波形」**。

### 已验证

- B3 架构可行：共享前端 + Voting BPM + Hilbert 波形，增量计算可接受（~17 min / 12 场景 × 11 方法）。
- 问题场景 A-D（2.31→0.65）、C-A（1.40→0.35）Voting BPM 修复机制成立。
- A1 单信道 best-η 跨域 0.96 BPM，Voting 价值明确。

### 仅单场景

- B-C 场景 B3 未显著优于 B2-D（均 ~0.73 BPM mean）。

### 未证实

- B3-Full 作为全局 BPM 推荐方法（劣于 B1/A4）。
- Hilbert 相位对齐相对谱融合（A4）的 RMSE 增益（A4 无波形，未能直接对比 RMSE）。
- coherence gating 的 RMSE 收益。

### 已废弃

- （无）— 但 η·ρ 投票权重、coherence gate、跨模态全局 Voting 对当前 12 场景可视为**可移除候选**（待 Review 决策）。

---

## 6. 实现与可复现性

| 项目 | 路径 |
|------|------|
| 模块 | `src/ble_analysis/b3_pipeline.py` |
| 脚本 | `notebooks/scripts/chFusion_ble_hkh_b3_validation.py` |
| 每场景 JSON | `outputs/reports/ble_hkh_b3_validation_{scenario_id}.json` ×12 |
| 跨域汇总 | `outputs/reports/ble_hkh_b3_validation_summary.json` |

```bash
python notebooks/scripts/chFusion_ble_hkh_b3_validation.py
```

- Hardcoded frame index：**无**
- Baseline 定义变更：**无**
- 指标定义变更：**无**

---

## 7. 保留问题

| ID | 问题 | 执行后状态 |
|----|------|-----------|
| Q1 | weighted_median vs max_confidence | 未单独消融；默认 weighted_median |
| Q2 | FFT 复用 vs 独立计算 | 采用独立 `_collect_channel_window_data`，可接受 |
| Q3 | A4 无 RMSE 的公平对比 | 仅在 BPM 维对比；报告中已标注 |
| Q4 | 三问题场景改善？ | A-D/C-A **是**；B-C **否** |
| Q5 | 无显著效果步骤是否移除？ | 建议 Review 决定：η·ρ 权重、coherence gate、A7 可精简 |

---

## 7.1 补充：B3 B1-equal 变体（推荐部署）

**变体** `b3_b1_equal`（`B3VariantConfig(modal_bpm_fusion="equal_spectral")`）：

- **波形**：与 B2-D 完全相同（两级 Hilbert-MRC，未改动）
- **BPM**：复用同一窗 Voting 前端的 per-modal `weighted_spectrum` → 三模态等权谱融合寻峰（与 B1 Vote→Equal 同一流程）

12 场景快验（`notebooks/scripts/_quick_b3_b1_equal_check.py`）：

| 指标 | B1 Vote→Equal | B3 B1-equal |
|------|-------------:|------------:|
| BPM cross mean | 0.405 | 0.405 |
| 逐场景 max \|Δ\| | — | **0.000** |
| RMSE mean | N/A | **0.950** |

**结论**：B3 可在不改 B2 波形的前提下，通过输出中间 Voting 谱精确复现 B1 BPM。

---

## 8. Self Check

| 项 | 状态 |
|----|------|
| Plan read | yes |
| Baseline confirmed | yes |
| Scenario JSON used | yes（12/12） |
| Script executed | yes |
| Results generated | yes |
| Figures generated | yes |
| Report generated | yes |
| Plan updated | yes |
| Hardcoded frame index risk | no |
| Baseline changed | no |
| Metric definition changed | no |
| Ready to commit | yes（待用户确认） |
