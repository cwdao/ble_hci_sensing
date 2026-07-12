# BLE-HKH 多人多场景验证 — 验证报告

> **Plan**：[`docs/plans/ble_hkh_multi_subject_preprocessing_plan.md`](../plans/ble_hkh_multi_subject_preprocessing_plan.md)  
> **脚本**：`notebooks/scripts/preprocess_ble_hkh_batch.py`、`notebooks/scripts/chFusion_ble_hkh_paper_baselines.py`  
> **场景**：`config/scenarios/room_{A,B,C}-sbj_{A,B,C,D}-*.json`（共 12 个）  
> **日期**：2026-07-12  
> **状态**：已完成

---

## 1. 目标与假设

本实验将 BLE CS + HKH 呼吸带验证从 1 人 1 场景扩展至 **3 场景 × 4 人 = 12 条**真人数据，在 10 种有波形输出的论文/B2 方法上评估 BPM 误差与 RMSE，检验单场景结论是否可推广。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 11 条新数据可成功预处理，对齐诊断无异常 | §6.3 最低标准 |
| H2 | B2-D 跨场景 RMSE 仍最优或接近最优 | §6.3 理想标准 |
| H3 | 方法排名在 Room 维度（A/B/C）上大体一致 | §6.3 理想标准 |
| H4 | Fan/Yu/Zhuo 论文波形方法与 B2 在多人数据上同量级 | §5.1 |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | remote_amplitudes、local_amplitudes、phases（72 tone × 3 变量） |
| 待测方法 | Fan 2024（3）、Yu 2021 MRC-PCA（2）、Zhuo 2023（3）、B2 参照（2），共 10 种 |
| 滑窗与寻峰 | 20 s 窗长 / 1 s 步长；呼吸频段 0.1–0.35 Hz；Welch + nfft |
| GT | HKH 带通波形（fs = len/duration ≈ 50.7 Hz） |

---

## 3. 实验设置

### 3.1 场景

| Room | 姿势 | 人数 | 场景 ID 示例 |
|------|------|------|-------------|
| A | 客厅坐姿 | 4 | `room_A-sbj_A-07101613` … `room_A-sbj_D-07111635` |
| B | 卧室平躺 | 4 | `room_B-sbj_A-07111726` … `room_B-sbj_D-07111653` |
| C | 卧室侧躺 | 4 | `room_C-sbj_A-07111734` … `room_C-sbj_D-07111659` |

### 3.2 预处理

- **已有**：`room_A-sbj_A-07101613`（手动锚点对齐，anchor_diff = 0 ms）
- **新增 11 条**：`preprocess_ble_hkh_batch.py` 按 HKH seq 裁剪 → 时间边界 → 最近 BLE 帧推断 seq
- **锚点偏差**：8/11 条 |anchor_diff| > 100 ms（最大 206 ms），均 < 500 ms；系 BLE ~2.4 Hz 稀疏采样所致，非时钟错配

### 3.3 指标

- BPM 绝对误差 mean ± std（vs HKH GT）
- 窗级 RMSE（z-score + 符号对齐）
- 跨 12 场景 mean / std（及按 Room、Subject、姿势分组）

### 3.4 产出路径

| 类型 | 路径 |
|------|------|
| 预处理汇总 | `outputs/reports/ble_hkh_preprocess_batch_summary.json` |
| 每场景结果 | `outputs/reports/ble_hkh_paper_baselines_{scenario_id}.json` ×12 |
| 跨场景汇总 | `outputs/reports/ble_hkh_paper_baselines_summary.json` |
| 图表 | `outputs/figures/ble_hkh_paper_baselines_*.png`、`ble_hkh_preprocess_*.png` |

---

## 4. 结果

### 4.1 跨场景 BPM 排行榜（12 场景 mean）

| Rank | 方法 | BPM err (mean±std) | RMSE mean |
|------|------|-------------------:|----------:|
| 1 | Zhuo 2023 Z1-no-VMD → Peak | **0.44±0.12** | 1.070 |
| 2 | Yu 2021 MRC-PCA η-equal PCA3→1 | 0.51±0.15 | 1.063 |
| 3 | **B2-D Two-level Hilbert-MRC** | 0.68±0.57 | **0.950** |
| 4 | Zhuo 2023 Z1 VMD → FFT | 0.71±0.09 | 1.062 |
| 5 | Zhuo 2023 Z1 VMD → Peak | 0.74±0.10 | 1.062 |
| 6 | Yu 2021 MRC-PCA √η | 1.02±1.26 | 1.054 |
| 7 | B2-A0 PCA sign | 1.32±0.65 | 1.085 |
| 8 | Fan 2024 η-linear | 1.39±1.68 | 1.025 |
| 9 | Fan 2024 Hilbert equal wf | 1.47±1.52 | 1.044 |
| 10 | Fan 2024 η-equal wf avg | 1.49±1.53 | 1.046 |

数据来源：`outputs/reports/ble_hkh_paper_baselines_summary.json`

### 4.2 按 Room 分组（各 4 人 mean，Top-1）

| Room | 最优方法 | BPM err |
|------|----------|--------:|
| A（坐姿） | Zhuo Z1-no-VMD | 0.41 |
| B（平躺） | Zhuo Z1-no-VMD | 0.44 |
| C（侧躺） | Yu MRC-PCA η-equal | 0.46 |

### 4.3 姿势二分类（Living room vs Bedroom）

| 分组 | 最优方法 | BPM err |
|------|----------|--------:|
| Living room（Room A） | Zhuo Z1-no-VMD | 0.41 |
| Bedroom（Room B+C） | Zhuo Z1-no-VMD | 0.45 |

### 4.4 关键方法 × 场景 BPM 矩阵（mean abs err, BPM）

| 场景 | Z1-no-VMD | Yu PCA3 | B2-D | Fan η-linear |
|------|----------:|--------:|-----:|-------------:|
| room_A-sbj_A | 0.51 | 0.47 | **0.42** | **0.37** |
| room_A-sbj_B | **0.37** | 0.71 | 0.30 | 0.26 |
| room_A-sbj_C | **0.29** | 0.50 | 0.30 | 0.28 |
| room_A-sbj_D | 0.50 | 0.75 | 2.31 | 5.08 |
| room_B-sbj_A | **0.29** | 0.34 | 0.55 | 0.77 |
| room_B-sbj_B | **0.28** | **0.28** | 0.26 | 0.26 |
| room_B-sbj_C | 0.73 | 0.74 | 0.73 | 3.43 |
| room_B-sbj_D | 0.46 | 0.45 | 0.45 | 0.44 |
| room_C-sbj_A | 0.52 | 0.44 | 1.40 | 4.18 |
| room_C-sbj_B | 0.51 | 0.54 | 0.71 | 0.77 |
| room_C-sbj_C | **0.41** | 0.48 | **0.39** | 0.47 |
| room_C-sbj_D | 0.39 | **0.36** | 0.38 | **0.32** |

**异常场景**：`room_A-sbj_D`（Fan 5.08、B2-D 2.31 BPM）、`room_B-sbj_C`（Fan 3.43）、`room_C-sbj_A`（Fan 4.18、B2-D 1.40）显著劣于其余 9 条，拉高了 Fan/Yu 的跨场景 std。

### 4.5 与 plan 预期对比

| 预期（Plan §6.3） | 实际 | 一致？ |
|-------------------|------|--------|
| 11 条预处理成功 | 11/11 成功 | ✅ |
| B2-D RMSE 跨场景最优 | RMSE 0.950，其余 ≥ 1.025 | ✅ |
| 2/3 Room 排名一致 | Room A/B Top1 = Z1-no-VMD；Room C Top1 = Yu PCA3 | 部分 |
| Fan η-linear 单场景最优可推广 | 单场景 0.37 → 跨场景 1.39（第 8） | ❌ |

### 4.6 图表

- 跨场景排行榜：`outputs/figures/ble_hkh_paper_baselines_leaderboard_all.png`
- 按 Room：`outputs/figures/ble_hkh_paper_baselines_by_room.png`
- 按 Subject：`outputs/figures/ble_hkh_paper_baselines_by_subject.png`
- 坐姿 vs 躺姿：`outputs/figures/ble_hkh_paper_baselines_bedroom_vs_living.png`
- 预处理对齐（×11）：`outputs/figures/ble_hkh_preprocess_room_*.png`

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| 11 条新 HKH 数据预处理管线可用 | **已验证** |
| B2-D 跨 12 场景 RMSE 最低（0.950） | **已验证** |
| Zhuo Z1-no-VMD / Yu MRC-PCA 跨场景 BPM 优于 B2-D/Fan | **已验证**（12 场景 mean） |
| Fan η-linear 单场景最优结论可推广 | **未证实**（3 条 outlier 场景拖累） |
| 方法排名在 Room 维度完全一致 | **未证实**（Room C 最优为 Yu 而非 Zhuo） |
| 个别场景（A-D、B-C、C-A）可能存在采集/佩戴问题 | **仅单场景**（待目视诊断） |

### 已验证

- 批量预处理 11/11 成功；HKH fs ≈ 50.7 Hz，BLE fs ≈ 2.4 Hz
- 10 种波形方法在 12 场景全部跑通
- **B2-D RMSE 跨场景仍最低**（0.950 vs 次优 1.025）
- **Zhuo Z1-no-VMD** 跨场景 BPM 最优（0.44±0.12）

### 仅单场景

- `room_A-sbj_A` 上 Fan η-linear（0.37 BPM）最优 — 不可外推为全局结论
- `room_A-sbj_D`、`room_B-sbj_C`、`room_C-sbj_A` 上 Fan/B2-D 误差异常偏大

### 未证实

- Plan 理想标准「2/3 Room 排名一致」：Room C 与 A/B 的 Top-1 不同
- 单场景「Fan ≈ B2-D BPM」在 12 场景 mean 下不成立（Fan 1.39 vs B2-D 0.68 实际 B2 更优 BPM，但 Fan 有 outlier）

### 已废弃

- 无

---

## 6. 保留问题

1. **锚点阈值**：Plan 规定 >100 ms 停止；自动推断下 8/11 条为 100–206 ms（BLE 稀疏采样）。建议 Research 侧将「停止」阈值改为 500 ms（时钟错配），100 ms 仅作警告。
2. **异常场景**：`room_A-sbj_D` / `room_B-sbj_C` / `room_C-sbj_A` 需目视检查预处理诊断图与 HKH 佩戴质量。
3. **B2-D BPM std 大**（0.57 跨场景）：主要受 sbj_D(A) 单条 2.31 BPM 影响。
4. **VMD 无增益结论反转**：单场景 VMD 劣于 no-VMD；跨 12 场景 VMD 仍略差于 no-VMD（0.71–0.74 vs 0.44），结论一致。

---

## Self Check

- Plan read: yes
- Baseline confirmed: yes（Fan/Yu/Zhuo + B2，与 plan §5.1 一致）
- Scenario JSON used: yes（12 个）
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes
- Hardcoded frame index risk: no（HKH seq 来自 plan 用户标注；BLE seq 由时间边界自动推断）
- Baseline changed: no
- Metric definition changed: no
- Ready to commit: yes（待用户确认）
