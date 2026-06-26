# WiFi MRC "equal" 变体修正 — 验证报告

> **Plan**：[`docs/plans/wifi_mrc_equal_fix_plan.md`](../plans/wifi_mrc_equal_fix_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_wifi_mrc_baselines.py`、`chFusion_wifi_mrc_cross_domain.py`（核心模块：`src/ble_analysis/wifi_mrc.py`）  
> **场景**：`config/scenarios/cs_091339.json`、`cs_095806.json`、`cs_102621.json`  
> **日期**：2026-06-26  
> **状态**：已完成

---

## 1. 目标与假设

Review 发现 `fan_eta_equal` / `mrc_pca_eta_equal` 对三模态做 **BPM 标量平均**，而非 plan 原意的时域波形融合。本实验修正实现并对比 legacy 与新波形融合变体。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 波形等权融合（Fan equal-wf）应优于或接近 BPM 标量平均（legacy） | §1.2 |
| H2 | MRC+PCA 路线下 PCA(3→1) 模态融合应优于 BPM 标量平均 | §1.3 |
| H3 | Fan-Hilbert 相位对齐 + 波形平均可提供额外增益 | §2.1 |
| H4 | 修正后仍全局劣于 B1（8.45%）——外部 baseline 结论不变 | §6 R1 |

**成功标准**：legacy key 数值不变；新 key 独立计算；如实报告波形融合 vs BPM 平均的优劣。

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| Legacy（保留） | `fan_eta_equal` / `mrc_pca_eta_equal`：`nanmean(BPM_r, BPM_l, BPM_p)` |
| Fan-η-equal-wf | 三模态 η-MRC 波形 → 时域等权平均 → Welch 寻峰 |
| Fan-Hilbert-equal | Hilbert 相位对齐 tone → η-MRC → 三波形等权平均 → 寻峰 |
| MRC-PCA-η-equal-pca | 三模态 √η-MRC+PCA 符号校正波形 → PCA(3→1) → 寻峰 |
| 实现 | `_fan_window_bpms(equal_mode=...)`、`_mrc_pca_window_bpms(equal_mode=...)`、新增 `_fan_hilbert_window_bpms`；PCA(3→1) 用 `np.linalg.eigh`，无 sklearn |

---

## 3. 实验设置

- **Baseline**：B1 Vote→Equal modal（8.45%）、legacy equal 变体  
- **待测**：`fan_eta_equal_wf`、`fan_hilbert_equal`、`mrc_pca_eta_equal_pca`  
- **指标**：分段 BPM 相对误差 % mean、跨域 mean  
- **命令**：`python notebooks/scripts/chFusion_wifi_mrc_baselines.py --all`

---

## 4. 结果

### 4.1 主结果表

| 方法 | cs_091339 | cs_095806 | cs_102621 | **跨域 mean** | 备注 |
|------|-----------|-----------|-----------|---------------|------|
| B1 Vote→Equal modal | 13.22 | 6.50 | 5.63 | **8.45%** | 当前推荐 |
| MRC-PCA-η-equal (legacy, BPM avg) | 17.63 | 7.29 | 7.41 | **10.78%** | 与修正前一致 |
| Fan-η-equal (legacy, BPM avg) | 18.78 | 11.79 | 9.97 | **13.51%** | 与修正前一致 |
| **MRC-PCA-η-equal-pca (PCA3→1)** | 24.43 | **6.84** | **7.10** | **12.79%** | 新 |
| Fan-Hilbert-equal (Hilbert+wf) | 22.49 | 10.86 | 15.57 | **16.31%** | 新 |
| **Fan-η-equal-wf (waveform avg)** | 23.09 | 11.00 | 15.72 | **16.60%** | 新 |

数据来源：`outputs/reports/wifi_mrc_baselines_results.npy`（2026-06-26 重跑）

### 4.2 Legacy 数值一致性

| Legacy key | 修正前（README §4.9） | 修正后重跑 | 一致 |
|------------|----------------------|------------|------|
| `fan_eta_equal` | 13.51% | 13.51% | ✅ |
| `mrc_pca_eta_equal` | 10.78% | 10.78% | ✅ |

### 4.3 波形融合 vs BPM 标量平均

| 对比 | legacy 跨域 | 波形版跨域 | Δ (wf − legacy) | 结论 |
|------|-------------|------------|-----------------|------|
| Fan equal | 13.51% | 16.60% | **+3.09 pp** | 波形融合更差 |
| MRC+PCA equal | 10.78% | 12.79% | **+2.01 pp** | 波形融合更差（跨域） |
| Fan + Hilbert | — | 16.31% | vs legacy +2.80 pp | Hilbert 未改善 |

**场景分解（MRC-PCA equal-pca）**：095806/102621 略优于 legacy（6.84/7.10 vs 7.29/7.41），但 cs_091339 严重退化（24.43% vs 17.63%），拉高跨域 mean。Plan R1 成立：BPM 标量平均在困难场景上意外起到了平滑离群模态 BPM 的作用。

### 4.4 图表

- `outputs/figures/wifi_mrc_baselines_leaderboard.png`
- `outputs/figures/wifi_mrc_baselines_ablation.png`（含新变体）

### 4.5 与 B 系列方案对比

本节将 WiFi MRC（含本次修正变体）与项目 **B 系列自研方案** 及 B2 时域波形路线放在同一跨域尺度下比较。B 系列数值来自 `docs/methods/README.md` §2 与 B2 验证报告（2026-06-23）；MRC 数值来自 `outputs/reports/wifi_mrc_baselines_results.npy`（2026-06-26 重跑）。

#### 4.5.1 跨域排行榜（MRC + B 系列）

| 排名 | 类别 | 方法 | cs_091339 | cs_095806 | cs_102621 | **跨域 mean** | vs B1 |
|------|------|------|-----------|-----------|-----------|---------------|-------|
| 1 | **B 系列·推荐** | **B1 Vote→Equal modal** | 13.22 | **6.50** | **5.63** | **8.45%** | — |
| 2 | B 系列·波形 | **B2-D** 两级 Hilbert-MRC | 15.01 | **5.82** | 7.45 | **9.43%** | +0.98 pp |
| 3 | B 系列·baseline | Modal top2 equal | 13.04 | 10.61 | **4.69** | 9.45% | +1.00 pp |
| 4 | B 系列·波形 | B2-C FFT 互谱相位 MRC | 15.98 | 5.69 | 6.83 | 9.50% | +1.05 pp |
| 5 | B 系列·baseline | B0 Single Remote | **10.91** | 12.16 | 8.29 | 10.45% | +2.00 pp |
| 6 | **WiFi MRC·legacy** | MRC-PCA-η-equal (BPM avg) | 17.63 | 7.29 | 7.41 | **10.78%** | +2.33 pp |
| 7 | B 系列·波形 | B2-Bγ Hilbert + γ 门控 | 17.85 | 5.67 | 9.17 | 10.89% | +2.44 pp |
| 8 | B 系列·baseline | B1 Uniform Remote | 17.09 | 9.15 | 6.82 | 11.02% | +2.57 pp |
| 9 | **WiFi MRC·新** | MRC-PCA-η-equal-pca (PCA3→1) | 24.43 | 6.84 | 7.10 | **12.79%** | +4.34 pp |
| 10 | B 系列·波形 | B2-A0 PCA 符号 MRC | 20.57 | 6.74 | 9.69 | 12.33% | +3.88 pp |
| 11 | **WiFi MRC·legacy** | Fan-η-equal (BPM avg) | 18.78 | 11.79 | 9.97 | **13.51%** | +5.06 pp |
| 12 | **WiFi MRC·新** | Fan-Hilbert-equal | 22.49 | 10.86 | 15.57 | **16.31%** | +7.86 pp |
| 13 | **WiFi MRC·新** | Fan-η-equal-wf | 23.09 | 11.00 | 15.72 | **16.60%** | +8.15 pp |

#### 4.5.2 相对 B2-D（波形路线最优，9.43%）

| WiFi MRC 变体 | 跨域 mean | vs B2-D | 说明 |
|---------------|-----------|---------|------|
| MRC-PCA-η-equal (legacy) | 10.78% | +1.35 pp | 外部 baseline 最优，仍劣于 B2-D |
| MRC-PCA-η-equal-pca | 12.79% | +3.36 pp | 波形 PCA(3→1) 劣于 legacy BPM avg |
| Fan-η-equal (legacy) | 13.51% | +4.08 pp | Fan 路线整体弱于 Yu 2021 MRC |
| Fan-η-equal-wf / Hilbert | 16.31–16.60% | +6.9–7.2 pp | 修正变体全面劣于 B2 全系列 |

#### 4.5.3 分场景：MRC 最优 vs B 系列代表

| 场景 | B1 | B2-D | MRC-PCA legacy | MRC-PCA-pca | Fan equal-wf | 谁最优 |
|------|-----|------|----------------|-------------|--------------|--------|
| cs_091339 | 13.22 | 15.01 | 17.63 | 24.43 | 23.09 | **B1** |
| cs_095806 | 6.50 | **5.82** | 7.29 | **6.84** | 11.00 | **B2-D**（MRC-pca 接近 B1） |
| cs_102621 | **5.63** | 7.45 | 7.41 | 7.10 | 15.72 | **B1** |

**解读**：

1. **谱域 B 系列仍全局最优**：B1（8.45%）为跨域 default；Modal top2（9.45%）为无 Voting 的最强 baseline。
2. **自研波形路线 B2-D（9.43%）全面优于 WiFi MRC 全族**（最优 MRC 10.78%，差 1.35 pp）；本次 MRC 波形修正变体（12.79–16.60%）更远劣于 B2-D。
3. **091339 上 B 系列也优于 MRC**：B1 13.22% vs MRC legacy 17.63%；说明困难场景下谱域 Voting 比外部时域 MRC 更稳。
4. **095806 单场景**：MRC-PCA-pca（6.84%）可接近 B1（6.50%），但仍劣于 B2-D（5.82%）；不可抵消 091339 上的大幅退化。

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| Legacy key 向后兼容，数值未变 | **已验证** |
| 波形 equal 融合未优于 BPM 标量平均（跨域） | **已验证** |
| Fan-Hilbert 未带来增益 | **已验证** |
| MRC-PCA PCA(3→1) 在两易场景略优、091339 大劣 | **仅单场景**（095806/102621） |
| 修正后 MRC 仍全局劣于 B1 | **已验证** |

**相对 baseline**：所有新变体均劣于 B1（8.45%）；最优 MRC 仍为 legacy `mrc_pca_eta_equal`（10.78%），仍劣于 B2-D（9.43%）1.35 pp（见 §4.5）。

**部署建议**：不推荐 waveform equal / Hilbert / PCA(3→1) 替换 legacy equal；WiFi MRC BPM 路线维持「已结案、不推荐部署」。

---

## 6. 产出清单

| 类型 | 路径 |
|------|------|
| 模块 | `src/ble_analysis/wifi_mrc.py` |
| 数值 | `outputs/reports/wifi_mrc_baselines_results.npy` |
| 跨域 | `outputs/reports/wifi_mrc_baselines_cross_domain.npy` |
| 图表 | `outputs/figures/wifi_mrc_baselines_*.png` |
| 方法注册表 | `docs/methods/README.md` §4.9 |

---

## 7. 保留问题

1. cs_091339 上 waveform/PCA(3→1) 大幅退化机制待诊断（是否与模态波形反相/低 η 窗有关）。
2. 是否将 legacy equal 在 README 中明确标注为「BPM avg，非 waveform equal」——已在 §4.9 更新。

---

## Self Check

- Plan read: yes
- Baseline confirmed: yes
- Scenario JSON used: yes
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes
- Hardcoded frame index risk: no
- Baseline changed: no
- Metric definition changed: no
- Ready to commit: yes（待用户确认）
