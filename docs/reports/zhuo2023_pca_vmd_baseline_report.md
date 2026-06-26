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

## 6. 结论

### 已验证

- PCA-VMD 管线可在 BLE CS 上运行（VMD 收敛正常）。
- 两级 PCA 第二级 PC2 方差占比典型 >0.85（单窗调试）。
- 跨域 Z1（11.31%）劣于 B1（8.45%）约 **2.86 pp**。
- VMD 在 BLE 低采样率下**无实质增益**（Δ≈0.10 pp）。

### 仅单场景

- cs_095806：Z1_no_vmd_fft（5.91%）略优于 B1（6.50%）。

### 未证实

- VMD、投影、Hilbert 对齐可带来跨域 BPM 提升。

### 已废弃

- 不推荐将 Zhuo2023 PCA-VMD 作为默认 BPM pipeline。

**部署建议**：维持 B1 Vote→Equal；PCA-VMD 可作为论文「proposed vs WiFi CSI baseline」引用，与 WiFi MRC 同属已结案外部 baseline。

---

## 7. 产出清单

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
