# BLE CS 人体呼吸监测 — 实验结果汇报

---

## 1. 波形合成类方案：BPM 表现不佳

首先测试了三类基于**波形生成/恢复**的方案

### 方法说明

| 方法 | 路线描述 |
|------|----------|
| **Zhuo 2023 PCA-VMD**（外部参考） | 两级 PCA 降维（72 tone → PC1 → 3 模态 → PC1 融合波形）→ 可选 VMD → 峰值检测 BPM。源自 WiFi CSI 文献 |
| **B2-D 两级 Hilbert 相干融合**（自研） | 第一级：每模态 72 tone Hilbert 相位对齐 MRC → 模态波形。第二级：三模态 Hilbert 相位对齐 + η·γ 加权 → 最终波形 → Welch PSD 寻峰 |
| **Fan 2024 η 线性 MRC**（外部参考） | CSI 幅值 MRC + PCA 符号对齐 → 等权波形平均 |

### 12 场景主结果

| 方法 | BPM 误差 ↓ (mean±std) | RMSE ↓ | 波形 | BPM 排名 |
|------|---------------------:|-------:|:----:|:--------:|
| **逐模态 Voting → 三模态等权谱融合**（B1, 谱域） | **0.41±0.14** | — | ❌ | 🥇 |
| Zhuo 2023 PCA-VMD（无 VMD） | 0.44±0.12 | 1.070 | ✅ | 🥈 |
| **B2-D 两级 Hilbert 相干融合** | 0.68±0.84 | **0.950** | ✅ | 🥉 |
| Fan 2024 η 线性 MRC | 1.39±1.68 | 1.025 | ✅ | 7 |

- 

| 问题场景 | B1 Voting BPM | B2-D BPM | B2-D 退化幅度 |
|----------|-------------:|--------:|-------------:|
| `room_A-sbj_D`（坐姿） | **0.60** | 2.31 | −1.71 |
| `room_C-sbj_A`（侧躺） | **0.27** | 1.40 | −1.13 |
| `room_B-sbj_C`（平躺） | 0.71 | 0.73 | ≈0 |

波形类方案在 A-D 和 C-A 两条场景上出现了**级联性 BPM 崩溃**（波形 PSD 谱峰误选），而谱域 Voting 方法在同场景保持稳定。

![Outlier Timeseries](../../outputs/figures/ble_hkh_b3_outlier_timeseries.png)

**图 2**：问题场景 BPM 时序对比。Voting BPM（蓝）紧贴 GT（黑虚线），B2-D 波形 PSD BPM（红）在部分窗口大幅偏离，展示了 Voting 的 outlier 鲁棒性。

---

## 2. 频谱投票方案：BPM 保持稳定

### 12 场景 HKH BPM 排行榜

| 排名 | 方法 | BPM 误差 (mean±std) | 波形 |
|------|------|-------------------:|:----:|
| 1 | **逐模态 Voting → Top2 等权谱融合**（B3） | 0.38±0.12 | ❌ |
| 2 | **逐模态 Voting → 三模态等权谱融合**（B1, 推荐） | **0.41±0.14** | ❌ |
| 3 | Zhuo Z1-no-VMD（波形类最优） | 0.44±0.12 | ✅ |
| 4 | B2-D 两级 Hilbert（波形类最优） | 0.68±0.57 | ✅ |
| 5 | Fan η-linear | 1.39±1.68 | ✅ |

![B1 Leaderboard](../../outputs/figures/ble_hkh_b1_validation_leaderboard_12scenarios.png)

**图 3**：12 场景 BPM 排行榜。谱域 Voting 系列（蓝/绿柱）在 BPM 精度和稳定性上全面优于波形类方法（红柱）。

### 关键发现

- **Voting 的 BPM 稳定性跨场景保持**：B1 std 仅 0.14 BPM vs B2-D 0.84 BPM（6× 差异）。
- **Outlier 场景不崩溃**：Voting 在 A-D（0.60）、C-A（0.27）上远优于 B2-D（2.31、1.40）。
- **谱域 Voting 的唯一缺陷**：不能输出可用的呼吸波形（仅输出谱和 BPM）。

---

## 3. B3 统一管线：综合两者优势

B1（最优 BPM，无波形）和 B2-D（最优 RMSE，BPM 不稳定）共享相同的预处理前端（滤波 + 逐模态 Voting），因此可以合并为一条管线：

```text
                  72 tone × 3 变量 (remote/local/phases)
                        │
              共享前端：滤波 + 逐模态 η·ρ Voting
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   BPM 分支：                      波形分支：
   Voting 加权谱                   Voting 加权波形
   → 三模态等权谱融合              → 两级 Hilbert MRC 对齐
   → Welch 寻峰 → BPM             → 最终呼吸波形 → RMSE
   (B1 逻辑, 0.41 BPM)            (B2-D 逻辑, 0.950 RMSE)
```

这就是 **B3 Simplified**（B3 B1-equal 变体）——单条管线，共享预处理，BPM 和波形各自走最优路径，无需窗级门控。

### 核心结果

| 方案 | BPM 误差 (mean±std) | RMSE | 波形 | 说明 |
|------|-------------------:|------|:----:|------|
| **B3 Simplified** ✅ | **0.41±0.14** | **0.950** | ✅ |               |
| B1 Vote→Equal（对照） | 0.41±0.14 | — | ❌ | BPM-only 基线 |
| B2-D（对照） | 0.68±0.84 | 0.950 | ✅ | 波形基线 |

- **B3 BPM 精确复现 B1**：12 场景逐场景 BPM 差异 = **0.000 BPM**（数值完全一致）。
- **B3 RMSE 精确复现 B2-D**：同一条两级 Hilbert-MRC 波形管线，RMSE 同为 0.950。

![B3 Ablation Leaderboard](../../outputs/figures/ble_hkh_b3_ablation_leaderboard.png)

**图 4**：B3 消融排行榜。B3 Simplified（绿）与 B1（蓝）并列 BPM 榜首，同时 B3 拥有 B2-D（红）的波形能力。

# EN version

# Weekly Report: BLE CS Human Respiration Monitoring — Experimental Results

------

## 1. Waveform-Reconstruction Methods Show Limited BPM Robustness

We first evaluated several methods that attempt to generate or reconstruct a respiration waveform from BLE CS measurements.

### Tested Methods

| Method                                     | Description                                                  |
| ------------------------------------------ | ------------------------------------------------------------ |
| **Zhuo 2023 PCA-VMD**                      | A WiFi CSI-inspired method using two-stage PCA dimensionality reduction, optional VMD, and peak detection for BPM estimation. |
| **B2-D Two-stage Hilbert Coherent Fusion** | Our waveform-based method. It applies Hilbert phase alignment and weighted coherent fusion across tones and modalities, followed by Welch PSD peak detection. |
| **Fan 2024 η-linear MRC**                  | A reference waveform fusion method using CSI amplitude MRC, PCA sign alignment, and equal-weight waveform averaging. |

### Main Results Across 12 Scenarios

| Method                                                       | BPM Error ↓ (mean±std) | RMSE ↓    | Waveform Output | BPM Rank |
| ------------------------------------------------------------ | ---------------------- | --------- | --------------- | -------- |
| **Per-modality Voting → Three-modality Equal Spectrum Fusion** | **0.41±0.14**          | —         | ❌               | 🥇        |
| Zhuo 2023 PCA-VMD, without VMD                               | 0.44±0.12              | 1.070     | ✅               | 🥈        |
| **B2-D Two-stage Hilbert Fusion**                            | 0.68±0.84              | **0.950** | ✅               | 🥉        |
| Fan 2024 η-linear MRC                                        | 1.39±1.68              | 1.025     | ✅               | 7        |

Although waveform-based methods can output a respiration waveform, their BPM estimation is less stable in some difficult scenarios. In particular, B2-D suffers from PSD peak mis-selection in several windows, leading to large BPM deviations.

| Difficult Scenario          | B1 Voting BPM Error | B2-D BPM Error | Degradation |
| --------------------------- | ------------------- | -------------- | ----------- |
| `room_A-sbj_D` — sitting    | **0.60**            | 2.31           | −1.71       |
| `room_C-sbj_A` — side lying | **0.27**            | 1.40           | −1.13       |
| `room_B-sbj_C` — supine     | 0.71                | 0.73           | ≈0          |

**Key observation:** waveform-based BPM estimation may collapse in outlier scenarios, while spectrum-domain voting remains robust.

![Outlier Timeseries Placeholder](https://poe.com/outputs/figures/ble_hkh_b3_outlier_timeseries.png)

**Figure 1.** BPM time-series comparison in difficult scenarios. Voting BPM closely follows the ground truth, while B2-D waveform PSD BPM occasionally deviates significantly.

------

## 2. Spectrum-Domain Voting Provides Stable BPM Estimation

### BPM Leaderboard Across 12 HKH Scenarios

| Rank | Method                                                       | BPM Error (mean±std) | Waveform Output |
| ---- | ------------------------------------------------------------ | -------------------- | --------------- |
| 1    | **Per-modality Voting → Top-2 Equal Spectrum Fusion**        | 0.38±0.12            | ❌               |
| 2    | **Per-modality Voting → Three-modality Equal Spectrum Fusion** | **0.41±0.14**        | ❌               |
| 3    | Zhuo Z1-no-VMD                                               | 0.44±0.12            | ✅               |
| 4    | B2-D Two-stage Hilbert Fusion                                | 0.68±0.57            | ✅               |
| 5    | Fan η-linear                                                 | 1.39±1.68            | ✅               |

![B1 Leaderboard Placeholder](https://poe.com/outputs/figures/ble_hkh_b1_validation_leaderboard_12scenarios.png)

**Figure 2.** BPM leaderboard across 12 scenarios. Spectrum-domain voting methods achieve the best BPM accuracy and stability.

### Main Findings

- **Voting is consistently stable across scenarios.**
   The standard deviation of B1 is only **0.14 BPM**, much lower than B2-D.
- **Voting is robust to outliers.**
   In challenging scenarios such as `room_A-sbj_D` and `room_C-sbj_A`, Voting significantly outperforms B2-D.
- **Main limitation of spectrum-domain voting:**
   It estimates BPM reliably but does **not** generate a usable respiration waveform.

------

## 3. B3 Unified Pipeline Combines BPM Accuracy and Waveform Output

Since B1 and B2-D share the same preprocessing frontend, they can be integrated into a unified pipeline.

```text
                  72 tones × 3 modalities
                        │
        Shared frontend: filtering + per-modality η·ρ Voting
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   BPM branch:                    Waveform branch:
   Voting-weighted spectra        Voting-weighted waveforms
   → three-modality equal fusion   → two-stage Hilbert MRC alignment
   → Welch peak search → BPM       → final respiration waveform → RMSE
```

This unified method is referred to as **B3 Simplified**. It keeps the best BPM branch from B1 and the best waveform branch from B2-D, without requiring window-level gating.

### Final Results

| Method              | BPM Error (mean±std) | RMSE      | Waveform Output | Notes                           |
| ------------------- | -------------------- | --------- | --------------- | ------------------------------- |
| **B3 Simplified** ✅ | **0.41±0.14**        | **0.950** | ✅               | Unified BPM + waveform pipeline |
| B1 Vote→Equal       | 0.41±0.14            | —         | ❌               | BPM-only baseline               |
| B2-D                | 0.68±0.84            | 0.950     | ✅               | Waveform baseline               |

B3 Simplified exactly reproduces the BPM performance of B1 and the waveform RMSE of B2-D:

- **BPM:** identical to B1 across all 12 scenarios, with a per-scenario BPM difference of **0.000 BPM**.
- **RMSE:** identical to B2-D, with an RMSE of **0.950**.

![B3 Ablation Leaderboard Placeholder](https://poe.com/outputs/figures/ble_hkh_b3_ablation_leaderboard.png)

**Figure 3.** B3 ablation leaderboard. B3 Simplified matches the BPM accuracy of B1 while preserving the waveform output capability of B2-D.



------

## 5. Plan for Next Week

1. **Finalize the algorithm pipeline** and draw a clear algorithm flowchart for inclusion in the paper.
2. **Complete the first draft of the paper manuscript.**
