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

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| Legacy key 向后兼容，数值未变 | **已验证** |
| 波形 equal 融合未优于 BPM 标量平均（跨域） | **已验证** |
| Fan-Hilbert 未带来增益 | **已验证** |
| MRC-PCA PCA(3→1) 在两易场景略优、091339 大劣 | **仅单场景**（095806/102621） |
| 修正后 MRC 仍全局劣于 B1 | **已验证** |

**相对 baseline**：所有新变体均劣于 B1（8.45%）；最优 MRC 仍为 legacy `mrc_pca_eta_equal`（10.78%）。

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
