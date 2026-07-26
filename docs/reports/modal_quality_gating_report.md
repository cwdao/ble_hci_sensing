# 模态质量感知融合与门控 — 验证报告

> **Plan**：[`docs/plans/modal_quality_gating_plan.md`](../plans/modal_quality_gating_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_modal_oracle_diag.py`、`notebooks/scripts/chFusion_modal_quality_gating.py`  
> **核心模块**：`src/ble_analysis/b3_pipeline.py`、`src/ble_analysis/systematic_fusion.py`  
> **场景**：HKH 12（`room_*-sbj_*`）+ CS 金属板 3（`cs_091339` / `cs_095806` / `cs_102621`）  
> **日期**：2026-07-26  
> **状态**：已完成

---

## 1. 目标与假设

验证质量感知模态融合能否超越等权三模态融合，并检验 Phase 专用门控是否有增益。HKH 与 CS **分表**，不可合并跨域 mean。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 质量加权融合 ≤ 等权融合（HKH BPM ≤ 0.405） | §5.3 最低 |
| H2 | 质量加权融合 ≤ channel-only（HKH BPM ≤ 0.381） | §5.3 理想 |
| H3 | Phase 在 ≥5% 窗口中为 oracle 最优 | §5.3 理想 |
| H4 | Phase 门控相对 E3 有额外增益 | §4.3 |
| H5 | η·ρ 在模态级选择上优于 η-only | Q2 |
| H6 | Phase 在 CS 金属板上与 HKH 一样差 | Q1 |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | `remote_amplitudes` / `local_amplitudes` / `phases` |
| 信道融合 | 逐模态 Voting（η·ρ 加权直方图） |
| 模态融合 | Equal / η / η·ρ / η·γ / η·ρ·conf；可选 Phase hard/soft gate |
| 滑窗与寻峰 | 20 s / 1 s；呼吸频段 0.1–0.35 Hz；谱峰 BPM |

E3/E4 变体通过 `B3VariantConfig.modal_weight_mode` + `phase_gate_*` 接入 `estimate_b3_window()`；`modal_fusion_from_spectra(..., weight_mode="custom")` 支持显式权重。

---

## 3. 实验设置

| 域 | 场景 | 指标 |
|----|------|------|
| HKH | 12 条真人呼吸带 | mean abs BPM err（breaths/min） |
| CS | 3 条金属板 | mean rel BPM err % |

- **Baseline**：Equal（`draft_s_full`）、Channel-only（`draft_s_channel`）、Remote/Local/Phase 单模态  
- **待测**：E3a–E3d、E4a/b（p10/p25/p50）、E4c（η·ρ + soft p25）  
- Phase 门控阈值来自 E1 HKH 的 `q_phase = η·max(ρ,0)` 百分位：p10=1.376 / p25=1.593 / p50=1.817

---

## 4. 结果

### 4.1 E1 Oracle（窗级最优模态）

| 域 | n 窗 | Remote 最优% | Local 最优% | Phase 最优% | Oracle abs err |
|----|-----:|-------------:|------------:|------------:|---------------:|
| HKH | 1730 | 89.5 | 4.4 | **6.1** | 0.408 |
| CS | 437 | 70.9 | 14.6 | **14.4** | 0.651 |

要点：

- HKH 上 Remote 主导，但 Phase 仍在 **6.1%** 窗口最优（满足 H3 ≥5%）。
- CS 上 Phase 最优占比升至 **14.4%**；单模态 Phase abs err（1.259）接近 Remote（1.062），**远好于 HKH 上的系统性崩坏**。

图：`outputs/figures/modal_oracle_optimal_pie.png`、`modal_oracle_leaderboard.png`、`modal_oracle_phase_eta_dist.png`

### 4.2 E2 模态选择指标

| 指标 | HKH top-1 hit% | HKH 选中后 abs err | CS top-1 hit% | CS 选中后 abs err |
|------|---------------:|-------------------:|--------------:|------------------:|
| η-only | **63.6** | 0.750 | **33.4** | 1.206 |
| ρ-only | 50.7 | 0.500 | 30.0 | 1.324 |
| η·ρ | 54.3 | 0.528 | 32.3 | 1.175 |
| Voting conf | 53.1 | **0.466** | 30.4 | 1.308 |
| η·(1+ρ) | 54.5 | 0.541 | 31.8 | 1.190 |

要点：

- **命中率**：HKH/CS 上 η-only 均最高 → H5（η·ρ 更准）**不成立**。
- **选中后误差**：HKH 上 conf 最低（0.466），但仍劣于 channel-only（0.381）与单模态 Remote（0.376）。
- 硬选最优模态的质量指标，不能替代谱融合 / pick-by-conf。

图：`outputs/figures/modal_selection_metric_accuracy.png`、`modal_quality_per_window_scatter.png`

### 4.3 E3/E4 主结果 — HKH（12-scenario mean abs BPM）

| 方法 | BPM abs err | vs Equal | vs Channel-only |
|------|------------:|---------:|----------------:|
| Remote only | **0.376** | −0.029 | −0.005 |
| Local only | 0.378 | −0.027 | −0.003 |
| Channel-only | 0.381 | −0.024 | — |
| η·ρ·conf 加权（E3d） | 0.384 | −0.021 | +0.003 |
| Hard gate p50（E4a） | 0.385 | −0.020 | +0.004 |
| Soft×0.3 p25 / E4c | 0.386 | −0.019 | +0.005 |
| η·ρ 加权（E3b） | 0.388 | −0.017 | +0.007 |
| η·γ 加权（E3c） | 0.392 | −0.013 | +0.011 |
| η 加权（E3a） | 0.396 | −0.009 | +0.015 |
| Equal（BreatheCS） | 0.405 | — | +0.024 |
| Phase only | 2.191 | +1.786 | +1.810 |

### 4.4 E3/E4 主结果 — CS（3-scenario mean rel BPM %）

| 方法 | BPM rel err % | vs Equal |
|------|--------------:|---------:|
| Equal（BreatheCS） | **10.138** | — |
| η 加权（E3a） | 10.168 | +0.030 |
| η·γ 加权（E3c） | 10.193 | +0.055 |
| η·ρ 加权（E3b） | 10.457 | +0.319 |
| Soft×0.3 p25 / E4c | 10.503 | +0.365 |
| Phase only | 10.919 | +0.781 |
| Remote only | 11.232 | +1.094 |
| η·ρ·conf（E3d） | 11.286 | +1.148 |
| Channel-only | 12.509 | +2.371 |
| Local only | 16.210 | +6.072 |

图：`outputs/figures/modal_quality_gating_hkh_leaderboard.png`、`modal_quality_gating_cs_leaderboard.png`

### 4.5 与 plan 预期对比

| 预期 | 实际 | 一致？ |
|------|------|--------|
| E3 ≤ Equal（0.405）on HKH | 全部 E3 ∈ [0.384, 0.396] | ✅ |
| E3 ≤ Channel-only（0.381） | 最佳 E3d=0.384，略差 | ❌（接近） |
| E4 优于 E3 | E4≈E3（差 <0.005） | ❌ |
| η·ρ 模态选择更准 | η-only hit 更高 | ❌ |
| Phase 在 CS 一样差 | CS Phase 10.9%，接近 Equal | ❌（推翻） |
| Phase ≥5% 正贡献窗 | HKH 6.1%，CS 14.4% | ✅ |

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| HKH 上质量加权融合稳定优于等权（最低成功标准达成） | **已验证** |
| HKH 上质量加权仍略劣于 Remote-only / Channel-only | **已验证** |
| Phase 门控相对 E3 无实质额外增益 | **已验证** |
| Phase 在 HKH 系统性差、但在少数窗（6.1%）仍为 oracle 最优 | **已验证** |
| Phase 在 CS 金属板并不系统性崩坏；等权融合在 CS 最优 | **已验证** |
| 模态级选择应用 η·ρ 优于 η | **未证实**（相反：η hit 更高） |
| 质量加权可同时在 HKH+CS 成为推荐默认 | **未证实**（CS 偏好 Equal） |

**相对 baseline**：

- **HKH**：E3d（η·ρ·conf）相对 Equal 有明确增益，但仍不如 Remote-only / Channel-only。
- **CS**：Equal 仍是最优；质量加权与 Phase 门控无增益甚至略伤。

**部署建议**：不要把「质量加权三模态」直接替换 BreatheCS 默认等权；若面向 HKH 类真人数据，可考虑 Remote-only 或 Channel-only；Phase 是否参与必须分域判断，不能从 HKH 外推到 CS。

---

## 6. 开放问题与下一步

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | Phase HKH 差 / CS 不差的机制？ | 设备噪声、机械 vs 人体、采样条件对比 |
| Q2 | 为何硬选指标命中高但误差仍差？ | 最优模态 margin 小；融合比硬选更稳 |
| Q3 | 是否应对 Remote/Local 也做对称门控，而非仅 Phase？ | 新 plan：对称质量门控 / 双幅值优先 |
| Q4 | CS 上等权为何优于 channel-only？ | 金属板上 Phase 有正贡献，硬选丢 diversity |

---

## 7. 复现

```bash
# E1/E2
python notebooks/scripts/chFusion_modal_oracle_diag.py

# E3/E4（依赖 E1 的 q_phase 百分位）
python notebooks/scripts/chFusion_modal_quality_gating.py
```

| 产出 | 路径 |
|------|------|
| E1 窗级数据 | `outputs/reports/modal_oracle_per_window.npy` |
| E1/E2 摘要 | `outputs/reports/modal_oracle_summary.json` |
| E3/E4 HKH | `outputs/reports/modal_quality_gating_hkh_summary.json` |
| E3/E4 CS | `outputs/reports/modal_quality_gating_cs_summary.json` |
| 图表 | `outputs/figures/modal_oracle_*.png`、`modal_selection_*.png`、`modal_quality_*.png` |
| 本报告 | `docs/reports/modal_quality_gating_report.md` |

---

## 8. Plan 回填（执行 Agent）

- **验证状态**：已完成
- **实际脚本**：`chFusion_modal_oracle_diag.py`、`chFusion_modal_quality_gating.py`
- **结论一句话**：HKH 上质量加权击败等权但未击败单模态/channel-only；CS 上等权仍最优且 Phase 并不差；Phase 门控增益可忽略。
