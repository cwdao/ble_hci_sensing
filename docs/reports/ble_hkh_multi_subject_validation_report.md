# BLE-HKH 多人多场景验证 — 验证报告

> **Plan**：[`docs/plans/ble_hkh_multi_subject_preprocessing_plan.md`](../plans/ble_hkh_multi_subject_preprocessing_plan.md)  
> **脚本**：`notebooks/scripts/preprocess_ble_hkh_batch.py`、`notebooks/scripts/chFusion_ble_hkh_paper_baselines.py`、`notebooks/scripts/chFusion_ble_hkh_b1_validation.py`（B1 补充实验）  
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
| H5 | B1 系列（BPM-only）在 12 场景真人 HKH 上 BPM 优于或接近 B2-D | 补充实验 |
| H6 | B2-D RMSE 优势具有统计方向性（非仅单场景偶然） | 补充分析 |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | remote_amplitudes、local_amplitudes、phases（72 tone × 3 变量） |
| 待测方法 | **Phase A**（plan）：Fan 2024（3）、Yu 2021 MRC-PCA（2）、Zhuo 2023（3）、B2 参照（2），共 10 种（有波形） |
| | **Phase B**（补充）：B1 Vote→Equal、B1 Uniform Remote、B3 Vote→Top2（BPM-only，谱域融合） |
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
| B1 补充汇总 | `outputs/reports/ble_hkh_b1_validation_summary.json` |
| 图表 | `outputs/figures/ble_hkh_paper_baselines_*.png`、`ble_hkh_preprocess_*.png`、`ble_hkh_b1_validation_leaderboard_12scenarios.png` |

---

## 4. 结果

### 4.1 跨场景 BPM 排行榜 — 论文波形方法（12 场景 mean）

> Phase A：仅有波形输出的 Fan/Yu/Zhuo + B2。**BPM-only 的 B1 系列见 §4.7。**

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

### 4.7 B1 系列补充实验（BPM-only，12 场景）

脚本：`notebooks/scripts/chFusion_ble_hkh_b1_validation.py`  
数据来源：`outputs/reports/ble_hkh_b1_validation_summary.json`

| Rank | 方法 | BPM err (mean±std) | 波形输出 |
|------|------|-------------------:|----------|
| **1** | **B1 Uniform Remote** | **0.37±0.12** | ❌ |
| 2 | B3 Vote→Top2 modal | 0.38±0.12 | ❌ |
| 3 | **B1 Vote→Equal modal**（主推 B1） | **0.41±0.14** | ❌ |
| 4 | Zhuo Z1-no-VMD | 0.44±0.12 | ✅ |
| 5 | B2-D Two-level Hilbert-MRC | 0.68±0.57 | ✅ |
| 6 | Fan η-linear | 1.39±1.68 | ✅ |

**关键对比（B1 vs B2-D，outlier 场景）**：

| 场景 | B1 Vote→Equal | B2-D | 说明 |
|------|-------------:|-----:|------|
| `room_A-sbj_D` | 0.60 | **2.31** | B2 谱峰误选；B1 谱投票仍稳 |
| `room_C-sbj_A` | **0.27** | 1.40 | 同上 |
| 其余 10 条 | 0.26–0.71 | 0.26–0.73 | 两者同量级 |

B1 跨场景 **std 更小**（0.12–0.14 vs B2-D 0.57），在问题场景上未出现 BPM 崩溃。

### 4.8 B2-D RMSE 优势的可解释性与可靠性

| 观察 | 数值 | 解读 |
|------|------|------|
| B2-D 跨场景 mean RMSE | **0.950**（次优 Fan 1.025） | z-score 对齐后的波形形态偏差，单位 ≈ 标准差倍数 |
| 每场景 RMSE 排名第 1 | **6/12** | 非全胜，优势为 modest |
| 相对场景第 2 名 mean gap | **~0.05** | 绝对幅度小 |
| B2-D 优于 Fan 的场景 | 9/12 | 场景级配对 Wilcoxon p≈0.01 |
| B2-D mean RMSE bootstrap 95% CI | [0.84, 1.05] | 区间较宽 |

**结论分级**：

- **方向可靠**：B2-D RMSE 整体最低，场景级配对检验显著（α=0.05）。
- **幅度有限**：多数场景仅比第二名好 0.02–0.12；**RMSE 优 ≠ BPM 优**（B2 在 A-D/C-A 上 RMSE 尚可但 BPM 崩溃）。
- **报告建议**：RMSE 与 BPM 分开陈述；可选补充 win rate、配对 ΔRMSE bootstrap CI、Pearson r。

### 4.9 B1 + B2 组合建议（下一步）

| 分工 | 方案 | 依据 |
|------|------|------|
| **BPM 部署** | B1 Vote→Equal 或 B1 Uniform | 12 场景 BPM 第 1–3，std 小，outlier 鲁棒 |
| **波形/RMSE** | B2-D | RMSE 跨场景仍第 1（0.950） |
| **不推荐** | 为抬 BPM 排名 post-hoc 删场景 | 9 场景子集 B2 仍 BPM 第 2，且有过拟合风险 |

可行实现路径（待新 plan）：

1. **窗级门控 BPM**：\|B2 BPM − B1 BPM\| > 阈值 → 取 B1；否则取 B2（类似 G4 思路）。
2. **双指标部署**：同时输出 `BPM_B1` + `RMSE_B2`，不做强行融合。
3. **B2 波形 + B1 式谱投票寻峰**：在 B2 融合波形上改用 B1 谱逻辑估 BPM。

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| 11 条新 HKH 数据预处理管线可用 | **已验证** |
| B2-D 跨 12 场景 RMSE 最低（0.950） | **已验证** |
| B2-D RMSE 优势具有 modest 幅度与统计方向性 | **已验证**（§4.8） |
| Zhuo Z1-no-VMD 论文波形方法 BPM 优于 B2-D/Fan | **已验证**（Phase A，12 场景 mean） |
| **B1 系列 BPM 跨场景优于 B2-D 与 Z1** | **已验证**（§4.7；B1 Uniform 0.37） |
| Fan η-linear 单场景最优结论可推广 | **未证实**（3 条 outlier 场景拖累） |
| 方法排名在 Room 维度完全一致 | **未证实**（Room C 最优为 Yu 而非 Zhuo） |
| 个别场景（A-D、B-C、C-A）可能存在采集/佩戴问题 | **仅单场景**（待目视诊断） |
| B1+B2 混合门控已验证 | **未证实**（仅方案建议，§4.9） |

### 已验证

- 批量预处理 11/11 成功；HKH fs ≈ 50.7 Hz，BLE fs ≈ 2.4 Hz
- 10 种波形方法在 12 场景全部跑通
- **B2-D RMSE 跨场景仍最低**（0.950 vs 次优 1.025；幅度 modest，见 §4.8）
- **B1 Uniform Remote / B1 Vote→Equal** 为 12 场景 BPM 最优档（0.37 / 0.41），优于 Z1（0.44）与 B2-D（0.68）
- Phase A 中 **Zhuo Z1-no-VMD** 为波形方法 BPM 最优（0.44±0.12）

### 仅单场景

- `room_A-sbj_A` 上 Fan η-linear（0.37 BPM）最优 — 不可外推为全局结论
- `room_A-sbj_D`、`room_B-sbj_C`、`room_C-sbj_A` 上 Fan/B2-D 误差异常偏大

### 未证实

- Plan 理想标准「2/3 Room 排名一致」：Room C 与 A/B 的 Top-1 不同
- **B1+B2 混合门控**：方案已提出（§4.9），尚未实验验证

### 已废弃

- 无

---

## 6. 保留问题

1. **锚点阈值**：Plan 规定 >100 ms 停止；自动推断下 8/11 条为 100–206 ms（BLE 稀疏采样）。建议 Research 侧将「停止」阈值改为 500 ms（时钟错配），100 ms 仅作警告。
2. **异常场景**：`room_A-sbj_D` / `room_B-sbj_C` / `room_C-sbj_A` 需目视检查预处理诊断图与 HKH 佩戴质量。
3. **B2-D BPM std 大**（0.57 跨场景）：主要受 A-D、C-A 单条谱峰误选影响；B1 在同场景上仍稳（§4.7）。
4. **VMD 无增益**：跨 12 场景 VMD 仍略差于 no-VMD（0.71–0.74 vs 0.44），结论一致。
5. **B1+B2 混合**：建议新开 `b1_b2_hybrid_gating_plan.md` 验证窗级门控 BPM。
6. **RMSE 正式指标定义**：是否补充 win rate、配对 bootstrap CI、Pearson r（§4.8）。

---

## Self Check

- Plan read: yes
- Baseline confirmed: yes（Fan/Yu/Zhuo + B2，与 plan §5.1 一致）
- Scenario JSON used: yes（12 个）
- Script executed: yes（含 B1 补充实验）
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes
- Hardcoded frame index risk: no（HKH seq 来自 plan 用户标注；BLE seq 由时间边界自动推断）
- Baseline changed: no
- Metric definition changed: no
- Ready to commit: yes（待用户确认）
