# Zhuo 2023 PCA-VMD 外部基线 — 验证报告

> **Plan**：[`docs/plans/zhuo2023_pca_vmd_baseline_plan.md`](../plans/zhuo2023_pca_vmd_baseline_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_zhuo2023_pca_vmd.py`、`chFusion_zhuo2023_pca_vmd_cross_domain.py`  
> **模块**：`src/ble_analysis/pca_vmd.py`  
> **场景**：`config/scenarios/cs_091339.json`、`cs_095806.json`、`cs_102621.json`  
> **日期**：2026-06-26  
> **状态**：已完成

---

## 1. 目标与假设

将 Zhuo 2023 WiFi CSI 的 PCA-VMD 思路迁移到 BLE CS，作为与 WiFi MRC 正交的外部 baseline，对比 B1（8.45% 跨域 mean）。

| ID | 假设 | 结论 |
|----|------|------|
| H1 | VMD 分离呼吸模态 → Z1 优于 Z1_no_vmd | **未证实**（Δ≈0.10 pp） |
| H2 | 峰值检测（论文）优于 FFT | **未证实**（跨域 Z1 11.31% vs Z1_fft 12.19%；单场景 095806 上 FFT 更优） |
| H3 | 复平面投影（Z1_proj）有增益 | **未证实**（11.47% vs Z1 11.31%） |
| H4 | Hilbert 对齐优于相关符号翻转 | **未证实**（与 Z1 完全相同 11.31%） |
| H5 | 跨域可接近 B1 或 WiFi MRC 最优 | **未证实**（Z1 11.31% vs B1 8.45%） |

**VMD 参数**（cs_095806 消融）：K=2, α=2000（Z1 mean 8.20%）。

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 第一级 PCA | 每变量 72 tone bandpass → PC1 |
| 符号对齐 | 最大方差 PC1 为参考，相关符号翻转 |
| 第二级 PCA | 3×PC1 → PC1 融合波形（`min_channels=2` 适配三模态） |
| VMD | vmdpy，K=2，α=2000，max-Var 选模态 |
| Z1 BPM | 峰值检测 + 伪峰剔除 |
| Z1_fft | Welch FFT 寻峰（项目标准） |

实现修复：第二级 PCA 仅 3 列，需 `PcaSvdConfig(min_channels=2)`，否则全部被跳过。

---

## 3. 主结果表

数据来源：`outputs/reports/zhuo2023_pca_vmd_results.npy`

| 排名 | 方法 | cs_091339 | cs_095806 | cs_102621 | **跨域 mean** |
|------|------|-----------|-----------|-----------|---------------|
| 1 | **B1 Vote→Equal modal** | 13.22 | **6.50** | **5.63** | **8.45%** |
| 2 | Modal top2 equal | 13.04 | 10.61 | 4.69 | 9.45% |
| 3 | B0 Single Remote | 10.91 | 12.16 | 8.29 | 10.45% |
| 4 | Z1-no-VMD PCA→PCA→Peak | 18.70 | 7.71 | 7.23 | **11.21%** |
| 5 | **Z1 PCA→PCA→VMD→Peak** | 17.49 | 8.20 | 8.22 | **11.31%** |
| 6 | Z1-proj | 18.02 | 8.17 | 8.22 | 11.47% |
| 7 | PCA modal equal | 20.65 | 7.02 | 6.45 | 11.37% |
| 8 | Z1-FFT | 22.60 | 5.99 | 7.98 | 12.19% |
| 9 | Z1-no-VMD-FFT | 24.33 | 5.91 | 6.84 | 12.36% |

---

## 4. 与 plan 成功标准对比

| 级别 | 条件 | 判定 |
|------|------|------|
| 最低（<20%，VMD 收敛>80%） | Z1 跨域 11.31% | **达成** |
| 理想（<10% 或优于 WiFi MRC 10.78%） | 11.31% | **未达成** |
| 突出（≤8.45%） | — | **未达成** |
| VMD 无效（Z1 vs no_vmd <0.5 pp） | 11.31% vs 11.21%，Δ=0.10 pp | **成立——VMD 无额外增益** |

---

## 5. 关键发现

1. **VMD 在 BLE ~2 Hz 下几乎无增益**：跨域 Z1 与 Z1_no_vmd 差 0.10 pp，低于 plan 阈值 0.5 pp。
2. **091339 拖高跨域**：Z1 在 091339 为 17.49%，095806/102621 约 8%。
3. **单场景 095806**：Z1_no_vmd_fft（5.91%）略优于 B1（6.50%），**仅单场景**，不可推广。
4. **投影 / Hilbert 无跨域增益**：Z1_proj +0.16 pp；Z1_hilbert 与 Z1 数值相同。
5. **峰值检测 vs FFT**：跨域峰值路线（Z1）优于 FFT 变体；但 095806 上 FFT 更优——BPM 估计方式影响大于融合策略。

---

## 6. 与 B 系列方案对比

本节将 Zhuo2023 PCA-VMD 与项目 **B 系列自研方案**（谱域 Voting / Modal 及 B2 时域相干 MRC）对比。B 系列跨域数值来自 `docs/methods/README.md` §2 与 `docs/reports/b2_coherent_mrc_waveform_fusion_report.md`；Z1 数值来自 `outputs/reports/zhuo2023_pca_vmd_results.npy`（2026-06-26）。

### 6.1 跨域排行榜（Z1 + B 系列 + 外部 baseline）

| 排名 | 类别 | 方法 | cs_091339 | cs_095806 | cs_102621 | **跨域 mean** | vs B1 |
|------|------|------|-----------|-----------|-----------|---------------|-------|
| 1 | **B 系列·推荐** | **B1 Vote→Equal modal** | 13.22 | **6.50** | **5.63** | **8.45%** | — |
| 2 | B 系列·波形 | **B2-D** 两级 Hilbert-MRC | 15.01 | **5.82** | 7.45 | **9.43%** | +0.98 pp |
| 3 | B 系列·baseline | Modal top2 equal | 13.04 | 10.61 | **4.69** | 9.45% | +1.00 pp |
| 4 | B 系列·波形 | B2-C FFT 互谱相位 MRC | 15.98 | 5.69 | 6.83 | 9.50% | +1.05 pp |
| 5 | B 系列·baseline | B0 Single Remote | **10.91** | 12.16 | 8.29 | 10.45% | +2.00 pp |
| 6 | 外部·WiFi MRC | MRC-PCA-η-equal (legacy) | 17.63 | 7.29 | 7.41 | 10.78% | +2.33 pp |
| 7 | B 系列·波形 | B2-Bγ | 17.85 | 5.67 | 9.17 | 10.89% | +2.44 pp |
| 8 | **Z1 系列·最优** | **Z1-no-VMD** PCA→PCA→Peak | 18.70 | 7.71 | 7.23 | **11.21%** | +2.76 pp |
| 9 | **Z1 系列·主方案** | **Z1** PCA→PCA→VMD→Peak | 17.49 | 8.20 | 8.22 | **11.31%** | +2.86 pp |
| 10 | Z1 系列 | Z1-proj / Z1-Hilbert | 17.49–18.02 | 8.17–8.20 | 8.22 | 11.31–11.47% | +2.86–3.02 pp |
| 11 | B 系列·波形 | B2-A0 PCA 符号 MRC | 20.57 | 6.74 | 9.69 | 12.33% | +3.88 pp |
| 12 | Z1 系列 | Z1-FFT / Z1-no-VMD-FFT | 22.60–24.33 | 5.91–5.99 | 6.84–7.98 | 12.19–12.36% | +3.74–3.91 pp |

### 6.2 相对 B2-D（自研波形路线最优，9.43%）

| 方法 | 跨域 mean | vs B2-D | 路线 |
|------|-----------|---------|------|
| **B2-D** | **9.43%** | — | tone+modal Hilbert 相干 MRC → FFT BPM |
| MRC-PCA-η-equal (WiFi) | 10.78% | +1.35 pp | √η-MRC + PCA 符号 → BPM avg |
| **Z1-no-VMD** | 11.21% | **+1.78 pp** | PCA(72)→PCA(3) → 峰值 BPM |
| **Z1** | 11.31% | **+1.88 pp** | 上 + VMD（无实质增益） |
| B2-A0 | 12.33% | +2.90 pp | B2 系列较差变体 |
| Z1-FFT | 12.19% | +1.76 pp | Z1 + FFT BPM（091339 拖高） |

**结论**：Z1 跨域性能与 **B2-A1 / B2-A0-D**（约 11.06–11.15%）同档，**明显弱于 B2-D / B2-C**，也弱于 WiFi MRC legacy（10.78%）。自研波形融合中，**Hilbert 相干 MRC（B2）仍显著优于 WiFi 文献的 PCA-VMD（Z1）**。

### 6.3 分场景：Z1 vs B1 vs B2-D

| 场景 | B1 | B2-D | Z1 | Z1-no-VMD | 最优 |
|------|-----|------|-----|-----------|------|
| cs_091339 | **13.22** | 15.01 | 17.49 | 18.70 | **B1** |
| cs_095806 | 6.50 | **5.82** | 8.20 | 7.71 | **B2-D** |
| cs_102621 | **5.63** | 7.45 | 8.22 | 7.23 | **B1** |

- **095806**：B2-D 领先 Z1 约 **2.4 pp**；Z1_no_vmd_fft（5.91%）可略优于 B1（6.50%），但 Z1 主方案仍劣于 B 系列。
- **091339**：B1（13.22%）优于 B2-D（15.01%），但二者均远优于 Z1（17.49%）——外部 PCA-VMD 在困难场景退化最重。

### 6.4 三类路线定位（B 系列 vs 外部 vs 本次新结果）

| 路线 | 代表方法 | 跨域 mean | 相对 B1 | 部署状态 |
|------|----------|-----------|---------|----------|
| 谱域自研 | **B1 Vote→Equal** | **8.45%** | — | ✅ 推荐 |
| 谱域 baseline | Modal top2 | 9.45% | +1.00 pp | baseline |
| 波形自研 | **B2-D** | **9.43%** | +0.98 pp | ⏸️ 挂起（保留波形输出） |
| 外部 WiFi MRC | MRC-PCA-η-equal | 10.78% | +2.33 pp | ❌ 已结案 |
| 外部 WiFi CSI | **Z1-no-VMD / Z1** | **11.21–11.31%** | +2.76–2.86 pp | ❌ 已结案 |
| WiFi MRC 修正 | equal-wf / Hilbert | 16.31–16.60% | +7.9–8.2 pp | ❌ 劣于 legacy |

**论文叙事建议**：B1 为 proposed default；B2-D 为自研波形上界（9.43%，仍差 B1 0.98 pp）；WiFi MRC（10.78%）与 Zhuo Z1（11.31%）作为 **two external WiFi-literature baselines**，均系统性劣于 B 系列。

---

## 7. 结论

### 已验证

- PCA-VMD 管线可在 BLE CS 上运行（VMD 收敛正常）。
- 两级 PCA 第二级 PC2 方差占比典型 >0.85（单窗调试）。
- 跨域 Z1（11.31%）劣于 B2-D（9.43%）**1.88 pp**、劣于 B1（8.45%）**2.86 pp**（见 §6）。
- VMD 在 BLE 低采样率下**无实质增益**（Δ≈0.10 pp）。

### 仅单场景

- cs_095806：Z1_no_vmd_fft（5.91%）略优于 B1（6.50%）。

### 未证实

- VMD、投影、Hilbert 对齐可带来跨域 BPM 提升。

### 已废弃

- 不推荐将 Zhuo2023 PCA-VMD 作为默认 BPM pipeline。

**部署建议**：维持 B1 Vote→Equal；PCA-VMD 可作为论文「proposed vs WiFi CSI baseline」引用，与 WiFi MRC 同属已结案外部 baseline。

---

## 8. 产出清单

| 类型 | 路径 |
|------|------|
| 模块 | `src/ble_analysis/pca_vmd.py` |
| 脚本 | `notebooks/scripts/chFusion_zhuo2023_pca_vmd.py` |
| VMD 消融 | `outputs/reports/zhuo2023_pca_vmd_vmd_ablation.npy` |
| 数值 | `outputs/reports/zhuo2023_pca_vmd_results.npy` |
| 图表 | `outputs/figures/zhuo2023_pca_vmd_*.png` |

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
- Ready to commit: yes
