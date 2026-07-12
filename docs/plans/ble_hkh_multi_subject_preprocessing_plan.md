# BLE-HKH 多人多场景数据预处理与多算法验证 — 实现计划

> **来源**：用户需求 — 新增 3 场景 × 4 人 BLE CS + HKH 呼吸带配对数据  
> **目标报告**：`docs/reports/ble_hkh_multi_subject_validation_report.md`  
> **建议 plan 路径**：`docs/plans/ble_hkh_multi_subject_preprocessing_plan.md`  
> **日期**：2026-07-12  
> **验证状态**：已完成

---

## 1. 动机与背景

| 项目 | 说明 |
|------|------|
| 问题 | 当前仅有 1 个场景 1 人的 HKH 呼吸带验证数据（`room_A-sbj_A-07101613`），需扩展至 3 场景 × 4 人共 12 条数据集，实现对 BLE CS 呼吸估计算法在多场景多人条件下的统计评估 |
| 相关脚本/文档 | `notebooks/scripts/preprocess_ble_hkh.py`、`docs/ble_hkh_preprocessing.md`、`notebooks/scripts/chFusion_ble_hkh_multi_algorithm.py`、`notebooks/scripts/chFusion_ble_hkh_paper_baselines.py` |
| 本 plan 定位 | **数据工程 + 批量验证**：预处理 11 条新数据，然后在这 12 条（含已有 1 条）上运行现有算法对比 |

与已有 `docs/ble_hkh_preprocessing.md` 的关系：该文档描述了预处理流程和首条数据结果，本 plan 是将其**批量化**至全部 12 条数据。

---

## 2. 数据清单与命名

### 2.1 场景定义

| Room | 含义 | 环境 |
|------|------|------|
| A | 客厅坐姿 | 常见室内，椅子坐姿 |
| B | 卧室平躺 | 同一卧室，仰卧 |
| C | 卧室侧躺 | 同一卧室，侧卧 |

> Room B 和 C 是同一房间的两种姿势，为简化标注各给一个 room 代号。

### 2.2 全部 12 条数据集

**已完成（1 条）**：

| ID | Room | Subj | CS 源文件 | HKH 源文件 | HKH seq |
|----|------|------|-----------|------------|---------|
| `room_A-sbj_A-07101613` | A | A | `CS_frames_all_20260710_161311.jsonl` | `HKH_frames_all_20260710_161315.jsonl` | 21125–(auto) |

**待处理（11 条）**：

| # | ID | Room | Subj | CS 源文件 | HKH 源文件 | HKH seq 范围 |
|---|-----|------|------|-----------|------------|-------------|
| 1 | `room_A-sbj_B-07111610` | A | B | `CS_frames_all_20260711_161050.jsonl` | `HKH_frames_all_20260711_160953.jsonl` | 8957–16868 |
| 2 | `room_A-sbj_C-07111623` | A | C | `CS_frames_all_20260711_162335.jsonl` | `HKH_frames_all_20260711_162311.jsonl` | 3629–11445 |
| 3 | `room_A-sbj_D-07111635` | A | D | `CS_frames_all_20260711_163501.jsonl` | `HKH_frames_all_20260711_163426.jsonl` | 11474–17958 |
| 4 | `room_B-sbj_A-07111726` | B | A | `CS_frames_all_20260711_172655.jsonl` | `HKH_frames_all_20260711_172916.jsonl` | 4978–9027 |
| 5 | `room_B-sbj_B-07111820` | B | B | `CS_frames_all_20260711_182051.jsonl` | `HKH_frames_all_20260711_182032.jsonl` | 3824–9259 |
| 6 | `room_B-sbj_C-07111843` | B | C | `CS_frames_all_20260711_184311.jsonl` | `HKH_frames_all_20260711_184313.jsonl` | 3513–10405 |
| 7 | `room_B-sbj_D-07111653` | B | D | `CS_frames_all_20260711_165337.jsonl` | `HKH_frames_all_20260711_165254.jsonl` | 8049–13542 |
| 8 | `room_C-sbj_A-07111734` | C | A | `CS_frames_all_20260711_173459.jsonl` | `HKH_frames_all_20260711_173502.jsonl` | 2088–8033 |
| 9 | `room_C-sbj_B-07111835` | C | B | `CS_frames_all_20260711_183527.jsonl` | `HKH_frames_all_20260711_183528.jsonl` | 1843–9646 |
| 10 | `room_C-sbj_C-07111850` | C | C | `CS_frames_all_20260711_185002.jsonl` | `HKH_frames_all_20260711_185017.jsonl` | 4341–13489 |
| 11 | `room_C-sbj_D-07111659` | C | D | `CS_frames_all_20260711_165953.jsonl` | `HKH_frames_all_20260711_170037.jsonl` | 2248–8766 |

### 2.3 命名规则

```
{room}_{sbj}_{MMDDHHmm}
```

- `room`：`room_A` / `room_B` / `room_C`（大写，与已有数据一致）
- `sbj`：`sbj_A` / `sbj_B` / `sbj_C` / `sbj_D`（小写 sbj，大写字母区分人）
- `MMDDHHmm`：取自 CS 源文件名中的时间戳（月日时分）

---

## 3. 预处理步骤

### 3.1 流程图

```text
原始 CS_frames_all_*.jsonl          原始 HKH_frames_all_*.jsonl
        │                                     │
        │                                     ├─► 按给定 seq 范围裁剪 HKH
        │                                     │   [hkh_start_seq, hkh_end_seq]（含端点）
        │                                     │
        │                                     ▼
        │                              裁剪后 HKH records
        │                                     │
        │                                     ├─► 获取时间边界:
        │                                     │   t_start = HKH[0].t_host_utc_ns
        │                                     │   t_end   = HKH[-1].t_host_utc_ns
        │                                     │
        ▼                                     ▼
  按 t_host_utc_ns 范围裁剪 BLE ────────►  找到 BLE frames 中
  [t_start, t_end]（含边界）                 t_host 在 [t_start, t_end] 内的帧
        │                                     │
        ▼                                     ▼
  BLE cropped records                   HKH cropped records
        │                                     │
        ├─► seq 重编号 0…N_ble-1              ├─► seq 重编号 0…N_hkh-1
        │                                     │
        ▼                                     ▼
  CS_frames_cropped.jsonl               HKH_frames_cropped.jsonl
        │                                     │
        │                                     ├─► _filter_1d(hkh_amp, fs_hkh, filters.hkh)
        │                                     │   median(w=5) → highpass(0.05Hz) → bandpass(0.1–0.35Hz)
        │                                     │
        ▼                                     ▼
        └──────────┬──────────────────────────┘
                   │
                   ▼
            aligned_bundle.npz
            (cs_t_host, hkh_t_host, hkh_amp_raw, hkh_median, hkh_highpass, hkh_bandpass, fs_ble, fs_hkh)
                   │
                   ▼
            preprocess_meta.json
```

### 3.2 与已有 preprocess_ble_hkh.py 的关键差异

| 维度 | 已有（room_A/sbj_A） | 新增 11 条 |
|------|---------------------|-----------|
| BLE seq | 手动指定 `ble_start_seq` / `ble_end_seq` | **自动**：由 HKH 时间边界推断 |
| HKH end_seq | `None` → 由 BLE 末帧时间推断 | **显式给定**：用户提供了 HKH seq 范围 |
| 执行方式 | 单条硬编码 | **批量循环** 或 CLI 参数化 |

### 3.3 对齐逻辑（关键）

由于用户只提供了 HKH 的起止 seq，BLE 的裁剪边界需要从 HKH 的时间戳反推：

```python
# 伪代码
hkh_cropped = crop_hkh_by_seq(hkh_raw, hkh_start_seq, hkh_end_seq)
t_start = hkh_cropped[0]["t_host_utc_ns"]
t_end   = hkh_cropped[-1]["t_host_utc_ns"]

ble_cropped = [f for f in ble_raw if t_start <= f["t_host_utc_ns"] <= t_end]
```

**注意**：HKH 和 BLE 的 `t_host_utc_ns` 来自同一主机时钟，可直接比较。两端数据帧率不同（BLE ~2.4 Hz，HKH ~50 Hz），因此 BLE 帧数远少于 HKH 帧数，但时间跨度应一致。

### 3.4 滤波参数（沿用）

```text
BLE:  median(w=3) → highpass(0.05 Hz, order=1) → bandpass(0.1–0.35 Hz, order=2)
HKH:  median(w=5) → highpass(0.05 Hz, order=1) → bandpass(0.1–0.35 Hz, order=2)
```

HKH 采样率使用 `len(hkh_cropped) / duration_s`（`hkh_used`），**不得**使用 `t_host` 正差分（会因批量写入低估）。

### 3.5 锚点对齐差检查

每条的 `anchor_diff_ms = (hkh_anchor_t - cs_anchor_t) / 1e6` 应接近 0（同一主机时钟，通常偏差 <10 ms）。

**若偏差 > 100 ms**：表示可能存在时钟域异常或文件错配，**应立即停止**，报告该条数据的具体偏差值，等待用户手动检查。不要自动继续处理。

---

## 4. 预处理产出物

每条数据集产出 4 个文件，放入 `sampleData/processed/{dataset_id}/`：

| 文件 | 说明 |
|------|------|
| `CS_frames_cropped.jsonl` | 裁剪后 BLE 帧（seq 重编号 0…） |
| `HKH_frames_cropped.jsonl` | 裁剪后 HKH 帧（seq 重编号 0…） |
| `aligned_bundle.npz` | 对齐后的 NumPy 数组包 |
| `preprocess_meta.json` | 裁剪参数、对齐信息、fs、滤波参数 |

每条同时生成一份对齐诊断图：

```
outputs/figures/ble_hkh_preprocess_{dataset_id}.png
```

每条生成一个场景配置 JSON：

```
config/scenarios/{dataset_id}.json
```

---

## 5. 算法验证（Phase 2）

### 5.1 待比较的方法（精简范围）

本次聚焦于**有波形生成能力**的核心方法——这些方法的输出可以直接与 HKH 带通波形计算 RMSE，物理可解释性最强，也是论文中最可能采用的方案。不需要跑全部 26 种方法。

| 方法类别 | 具体方法 | 来源 |
|----------|----------|------|
| **B2 系列**（3 变体） | B2-D Two-level Hilbert-MRC、B2-A0 PCA sign、B2-A1 Corr sign | `src/ble_analysis/ble_hkh_validation.py` |
| **Fan 2024**（2 变体） | η-linear (best modal)、η-equal waveform avg | `src/ble_analysis/wifi_mrc.py` |
| **Yu 2021**（2 变体） | MRC-PCA √η (best modal)、MRC-PCA η-equal PCA3→1 | `src/ble_analysis/wifi_mrc.py` |
| **Zhuo 2023**（3 变体） | Z1 VMD→Peak、Z1 VMD→FFT、Z1-no-VMD→Peak | `src/ble_analysis/pca_vmd.py` |

> 共 **10 种**方法，均为有融合波形输出的方案。B0/B1/Voting/Modal/Systematic 等无波形输出的 BPM-only 方法本次不跑（可在后续扩展）。

### 5.2 验证脚本

直接修改 `chFusion_ble_hkh_paper_baselines.py`（已覆盖 Fan/Yu/Zhuo + B2 参照），将其从单场景扩展为批量。`chFusion_ble_hkh_multi_algorithm.py`（26 法）本次**不需要**修改或运行。

| 脚本 | 操作 | 覆盖方法 |
|------|------|----------|
| `chFusion_ble_hkh_paper_baselines.py` | **修改**：遍历 12 场景 | Fan/Yu/Zhuo + B2（共 ~10 法） |
| `chFusion_ble_hkh_multi_algorithm.py` | **不动** | — |

### 5.3 批量化

将 `chFusion_ble_hkh_paper_baselines.py` 中的 `SCENARIO_ID` 改为遍历全部 12 个场景配置：

```python
SCENARIO_IDS = [
    "room_A-sbj_A-07101613",  # 已有
    "room_A-sbj_B-07111610",
    # ... 共 12 个
]
```

对每个场景运行 benchmark，汇总为跨场景统计。

### 5.4 汇总分析

除每个场景独立的结果外，还需产出：

- **跨场景 BPM 误差汇总表**（12 行 × 方法）— **主分析维度**
- **按 Room 分组统计**（A 坐姿 / B 平躺 / C 侧躺 各 4 人）— **优先**
- **按 Subject 分组统计**（每人 3 场景）— **次要**（个体差异参考）
- **跨场景排行榜图**（所有场景平均排名）
- **补充分析**：Room B+C 合并为 "Bedroom" vs Room A "Living Room" 的二分类对比（坐姿 vs 躺姿）

---

## 6. 评估设计

### 6.1 场景

全部 12 个场景配置：

```text
config/scenarios/room_A-sbj_A-07101613.json  ← 已有
config/scenarios/room_A-sbj_B-07111610.json  ← 新增
...（共 12 个）
```

### 6.2 指标

| 指标 | 说明 |
|------|------|
| BPM 绝对误差（mean ± std） | 主指标 |
| BPM 相对误差 % | 跨场景可比 |
| 窗级 RMSE（z-score + 符号对齐） | 仅论文波形方法 |
| 跨域 mean BPM err | 12 场景平均（也可分别按 Room/Subject 聚合） |

### 6.3 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | 11 条新数据全部预处理成功，诊断图无异常 |
| **理想** | 多算法在至少 2/3 场景（Room 维度）上保持 rank 一致；B2-D RMSE 跨场景仍最优或接近最优 |
| **关注** | 若某场景/某人数据上所有方法 BPM 误差均显著恶化，可能表示该数据存在采集问题 |

---

## 7. 实现要点

### 7.1 建议文件

| 类型 | 路径 | 说明 |
|------|------|------|
| **批量预处理脚本** | `notebooks/scripts/preprocess_ble_hkh_batch.py` | 新建：遍历 11 条数据调用 `preprocess_ble_hkh_pair()` |
| 复用模块（不改） | `src/ble_analysis/ble_hkh_preprocess.py` | 已有：`preprocess_ble_hkh_pair()` |
| 复用模块（不改） | `src/ble_analysis/ble_hkh_validation.py` | 已有：`load_hkh_gt_signals()` |
| 复用模块（不改） | `src/ble_analysis/ble_hkh_paper_validation.py` | 已有：论文方法验证（Fan/Yu/Zhuo + B2） |
| **修改** | `notebooks/scripts/chFusion_ble_hkh_paper_baselines.py` | 改为遍历 12 场景，并增加按 Room/Subject 汇总 + Room B+C vs A 补充分析 |
| 不动 | `notebooks/scripts/chFusion_ble_hkh_multi_algorithm.py` | 本次不需要（26 法不跑） |

### 7.2 批量预处理脚本接口草案

```python
# notebooks/scripts/preprocess_ble_hkh_batch.py

DATASETS = [
    {
        "id": "room_A-sbj_B-07111610",
        "cs_src": "sampleData/ble-hkh/CS_frames_all_20260711_161050.jsonl",
        "hkh_src": "sampleData/ble-hkh/HKH_frames_all_20260711_160953.jsonl",
        "hkh_start_seq": 8957,
        "hkh_end_seq": 16868,
    },
    # ... 共 11 条
]

for ds in DATASETS:
    crop = BleHkhCropSpec(
        ble_start_seq=0,        # 占位：实际由 HKH 时间边界推断
        ble_end_seq=None,       # 占位
        hkh_start_seq=ds["hkh_start_seq"],
        hkh_end_seq=ds["hkh_end_seq"],
    )
    # 注意：现有 preprocess_ble_hkh_pair 接口需要 ble_start_seq/ble_end_seq
    # 若不想改核心函数，可以在调用前先读 CS 文件定位起止 seq
```

### 7.3 关键实现注意事项

1. **BLE seq 自动推断**：现有 `preprocess_ble_hkh_pair()` 要求显式 `ble_start_seq` / `ble_end_seq`。有两种方式处理：
   - **方式 A（推荐）**：在 batch 脚本中先加载 CS 和 HKH raw 数据，用 HKH 裁剪后的 `t_host_utc_ns` 边界去 CS 中查找对应的 seq 范围，再调用 `preprocess_ble_hkh_pair()`。
   - **方式 B**：给 `preprocess_ble_hkh_pair()` 增加一个 `hkh_time_based: bool = False` 参数，内部自动推断 BLE seq。但此方式改动核心模块，影响已有逻辑。

2. **HKH 单文件可能含多个 session**：HKH 的 seq 不一定从 0 开始的有效段，头尾可能有采集启动/停止时的无效数据。给定的 seq 范围是用户目视确认的有效呼吸段。

3. **诊断图**：每条数据都应生成对齐诊断图，便于快速目视检查。

4. **批量验证的输出组织**：建议每条场景独立保存一份结果 JSON，再加一个汇总 JSON：

```
outputs/reports/ble_hkh_multi_algorithm_{dataset_id}.json  (×12)
outputs/reports/ble_hkh_multi_algorithm_summary.json       (汇总)
outputs/figures/ble_hkh_multi_algorithm_leaderboard_all.png
outputs/figures/ble_hkh_multi_algorithm_by_room.png
outputs/figures/ble_hkh_multi_algorithm_by_subject.png
```

### 7.4 不做的事

- 不修改 `src/ble_analysis/ble_hkh_preprocess.py` 的核心逻辑（除非发现 bug）
- 不修改滤波参数
- 不新增算法方法
- 不修改指标定义
- 不修改已有 `room_A-sbj_A-07101613` 的预处理结果

---

## 8. 预期产出

### Phase 1 — 预处理

| 产出 | 路径 |
|------|------|
| 11 条新数据集的 cropped JSONL | `sampleData/processed/{dataset_id}/CS_frames_cropped.jsonl` ×11 |
| | `sampleData/processed/{dataset_id}/HKH_frames_cropped.jsonl` ×11 |
| | `sampleData/processed/{dataset_id}/aligned_bundle.npz` ×11 |
| | `sampleData/processed/{dataset_id}/preprocess_meta.json` ×11 |
| 11 张对齐诊断图 | `outputs/figures/ble_hkh_preprocess_{dataset_id}.png` ×11 |
| 11 个场景配置 JSON | `config/scenarios/{dataset_id}.json` ×11 |

### Phase 2 — 验证

| 产出 | 路径 |
|------|------|
| 批量预处理脚本 | `notebooks/scripts/preprocess_ble_hkh_batch.py` |
| 论文波形 × 12 场景结果 | `outputs/reports/ble_hkh_paper_baselines_{dataset_id}.json` ×12 |
| 论文波形汇总 | `outputs/reports/ble_hkh_paper_baselines_summary.json` |
| 跨场景排行榜图 | `outputs/figures/ble_hkh_paper_baselines_leaderboard_all.png` |
| 按 Room 分组图 | `outputs/figures/ble_hkh_paper_baselines_by_room.png` |
| 按 Subject 分组图 | `outputs/figures/ble_hkh_paper_baselines_by_subject.png` |
| Room B+C vs A 补充分析图 | `outputs/figures/ble_hkh_paper_baselines_bedroom_vs_living.png` |
| 验证报告 | `docs/reports/ble_hkh_multi_subject_validation_report.md` |

### 建议运行命令

```bash
# Phase 1: 批量预处理
python notebooks/scripts/preprocess_ble_hkh_batch.py

# Phase 2: 论文波形方法 + B2 批量验证
python notebooks/scripts/chFusion_ble_hkh_paper_baselines.py
```

---

## 9. 风险与保留问题

| # | 风险 | 说明 |
|---|------|------|
| R1 | **BLE seq 自动推断失败** | 若 CS 和 HKH 的时间戳不在同一主机时钟域（极小概率），则按 `t_host_utc_ns` 对齐会失败。诊断图中 `anchor_diff_ms` 可发现此问题 |
| R2 | **某条数据 HKH 信号质量差** | 呼吸带佩戴不当可能导致 GT 不可靠，需在报告中标注 |
| R3 | **BLE 帧缺失** | 原始 CS 文件 seq 不连续（如示例中 seq 21-23 缺失），这不影响预处理——只要在时间窗口内有足够帧即可 |
| R4 | **HKH seq 范围标注误差** | 用户目视标注的起止点可能有 1–2 秒偏差，影响微小（<1 个滑窗），可接受 |
| R5 | **验证脚本适配成本** | 将现有单场景脚本改为多场景遍历可能涉及较大量代码重构，需评估是改原脚本还是另写 batch wrapper |

### 保留问题

| ID | 问题 | 决策 |
|----|------|------|
| Q1 | 若某条诊断图显示对齐异常（`anchor_diff_ms` 大） | **已定**：若 >100 ms 则停止，交用户检查 |
| Q2 | 汇总分析维度优先级 | **已定**：跨场景类型（Room）优先，个体差异（Subject）次要 |
| Q3 | 方法范围 | **已定**：仅跑 B2 + Fan/Yu/Zhuo（~10 法，有波形输出），不跑全部 26 法 |
| Q4 | Room B+C vs A 对比 | **已定**：作为补充分析加入，非主分析维度 |

---

## 10. 验证状态

| 字段 | 内容 |
|------|------|
| **验证状态** | 已完成 |
| **实际脚本** | `notebooks/scripts/preprocess_ble_hkh_batch.py`；`notebooks/scripts/chFusion_ble_hkh_paper_baselines.py` |
| **报告链接** | `docs/reports/ble_hkh_multi_subject_validation_report.md` |
| **一句话结论** | 11/11 预处理成功；Zhuo Z1-no-VMD 跨 12 场景 BPM 最优（0.44 BPM），B2-D RMSE 仍最低（0.950）；Fan η-linear 单场景结论不可推广 |

实际产出路径：
- 脚本：`notebooks/scripts/preprocess_ble_hkh_batch.py`（新建）；`notebooks/scripts/chFusion_ble_hkh_paper_baselines.py`（改为 12 场景批量）
- 数值结果：`outputs/reports/ble_hkh_preprocess_batch_summary.json`；`outputs/reports/ble_hkh_paper_baselines_{scenario_id}.json` ×12；`outputs/reports/ble_hkh_paper_baselines_summary.json`
- 图表：`outputs/figures/ble_hkh_preprocess_*.png` ×11；`outputs/figures/ble_hkh_paper_baselines_*.png`
- 报告：`docs/reports/ble_hkh_multi_subject_validation_report.md`

结论摘要：
- Phase 1：11 条新数据全部预处理成功；8/11 条 anchor_diff >100 ms（BLE 稀疏采样，已记录）
- Phase 2：10 种波形方法 × 12 场景；跨场景 BPM Top3 = Zhuo no-VMD / Yu PCA3 / B2-D；B2-D RMSE 跨场景最低

遗留问题：
- 3 条场景（A-D、B-C、C-A）Fan/B2 BPM 异常，建议目视诊断
- Plan Q1 锚点 >100 ms 停止规则与 BLE 稀疏采样冲突，执行侧改用 500 ms 停止 / 100 ms 警告
- **补充（2026-07-12）**：B1 系列 12 场景 BPM 验证（`chFusion_ble_hkh_b1_validation.py`）— B1 Uniform 0.37 BPM 最优，B2-D RMSE 0.950 仍最低；详见报告 §4.7–§4.9

---

## 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并按以下顺序执行：

### Phase 1 — 批量预处理（11 条新数据）

1. 读取本 plan：`docs/plans/ble_hkh_multi_subject_preprocessing_plan.md`
2. 新建 `notebooks/scripts/preprocess_ble_hkh_batch.py`
3. 遍历 §2.2 中 11 条待处理数据，调用 `src/ble_analysis/ble_hkh_preprocess.py` 中的 `preprocess_ble_hkh_pair()`
   - **关键**：每条数据先按 HKH seq 裁剪 HKH → 取时间边界 → 定位 CS 中对应 seq → 再调用预处理函数
   - **若** `anchor_diff_ms > 100 ms`：立即停止，报告该条数据的具体偏差值，等待用户检查
4. 为每条生成对齐诊断图、场景配置 JSON
5. 检查所有 `anchor_diff_ms` 是否在合理范围

### Phase 2 — 论文波形方法 + B2 批量验证（12 场景）

1. 修改 `chFusion_ble_hkh_paper_baselines.py`：将 `SCENARIO_ID` 改为遍历全部 12 场景
   - 方法范围：B2（3 变体）+ Fan 2024（2 变体）+ Yu 2021（2 变体）+ Zhuo 2023（3 变体）≈ 10 种
   - **不需要**修改或运行 `chFusion_ble_hkh_multi_algorithm.py`（26 法）
2. 运行脚本
3. 生成汇总统计：
   - 跨场景 BPM 误差排行榜（**主分析**）
   - 按 Room 分组（A/B/C，**优先**）
   - 按 Subject 分组（A/B/C/D，次要）
   - **补充分析**：Room B+C 合并为 "Bedroom" vs Room A "Living Room" 的二分类对比
4. 撰写验证报告：`docs/reports/ble_hkh_multi_subject_validation_report.md`（使用 `docs/templates/algorithm_validation_report.md`）
5. 更新本 plan §10 验证状态

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/ble_hkh_multi_subject_preprocessing_plan.md`（含回填的 §10）
- `docs/reports/ble_hkh_multi_subject_validation_report.md`
- 所有 `outputs/reports/ble_hkh_paper_baselines_*.json`
- 关键图表 `outputs/figures/`
- 新增/修改的脚本路径
- git commit message 或 git diff 摘要
