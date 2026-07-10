# BLE CS + HKH 呼吸带数据预处理与验证

本文档说明如何将 **BLE CS 帧数据** 与 **HKH 压力传感器呼吸带** 对齐、裁剪、滤波，并作为算法验证（含 B2 波形 RMSE 与 BPM 误差）的输入。

---

## 1. 背景

| 项目 | 说明 |
|------|------|
| 用途 | 真人呼吸场景下，用 HKH 呼吸带作为波形/BPM 真值，验证 BLE CS 算法 |
| 首条数据集 | `room_A-sbj_A-07101613`（2026-07-10 16:13 采集） |
| 原始文件 | `sampleData/ble-hkh/CS_frames_all_20260710_161311.jsonl` |
| | `sampleData/ble-hkh/HKH_frames_all_20260710_161315.jsonl` |

与金属板脚本场景（`cs_091339` 等）不同：

- **GT 来源**：HKH 带通滤波后的滑窗 BPM（真人呼吸，每窗可有细微差别），而非脚本标注 BPM。
- **新增指标**：算法合成带通波形 vs HKH 带通波形的 **窗级 RMSE**（z-score + 符号对齐后取 min）。

---

## 2. 时间对齐

### 2.1 锚点

| 传感器 | 裁剪 seq 起点 | 对应关系 |
|--------|--------------|----------|
| BLE CS | `1147` | 干净段起点 |
| HKH | `21125` | 与 BLE seq=1147 **同一 `t_host_utc_ns`**（实测差 0 ms） |

HKH 文件开头（seq≈0–21124）为采集启动后批量刷盘的历史缓冲，**不是**与 BLE 同步的有效段，预处理中丢弃。

### 2.2 裁剪终点

- BLE：`seq = 2017`（含）
- HKH：取 `t_host_utc_ns ≤ BLE seq=2017` 的最后一帧 → **seq = 32144**

裁剪后：

| | 帧数 | 时长 | 实测 fs |
|--|------|------|---------|
| BLE | 523 | 217.5 s | **2.4 Hz**（由 `t_dev_ms` 差分） |
| HKH | 11020 | 217.5 s | **≈50.7 Hz**（`len / duration`，由 `t_host_utc_ns` 头尾） |

> **说明**：HKH 设备标称 50 Hz（`t_dev_ms` 步进 20 ms）。因存在批量写入（多帧共享同一 `t_host_utc_ns`），`t_host` 正差分统计仅得 **≈19.6 Hz**（见 `preprocess_meta.json` 的 `hkh_from_t_host_diff`），**不能**用于带通滤波或 BPM 估计。预处理与 GT 验证统一使用 **`hkh_from_len_duration` / `hkh_used`**（帧数 ÷ 主机时间头尾时长）。

### 2.3 `DataSaver` 更新

`src/data_saver.py` 的 JSONL 加载现已保留：

- `t_host_utc_ns`
- `seq`
- HKH 帧顶层的 `amp` / `ch`（`frame_type == hkh11c_resp` 时不伪造 DF `channels` 结构）

---

## 3. 滤波参数

与项目标准一致（物理频率 Hz，与 fs 无关）：

```
median → highpass (0.05 Hz, order=1) → bandpass (0.1–0.35 Hz, order=2)
```

| 传感器 | 中值窗口 | 其余 |
|--------|----------|------|
| BLE | 3 | 与 `FilterParams` 默认相同 |
| HKH | 5 | 高通/带通与 BLE 相同 |

BLE 的 per-tone 滤波在算法 pipeline（`run_multichannel_segment_filtering`）中执行；预处理阶段对 **HKH 幅值序列** 直接跑完整滤波链。

---

## 4. 产出物

运行：

```bash
python notebooks/scripts/preprocess_ble_hkh.py
```

输出目录：`sampleData/processed/room_A-sbj_A-07101613/`

| 文件 | 说明 |
|------|------|
| `CS_frames_cropped.jsonl` | 裁剪后 BLE，seq 重编号 0…522 |
| `HKH_frames_cropped.jsonl` | 裁剪后 HKH，seq 重编号 0…11019 |
| `preprocess_meta.json` | 裁剪参数、对齐信息、实测 fs、滤波参数 |
| `aligned_bundle.npz` | NumPy 压缩包，便于 Python 一次加载数组 |

### 4.1 `npz` 是什么？

**`.npz`** 是 NumPy 的压缩数组归档格式。一次 `np.load("aligned_bundle.npz")` 即可得到：

- `hkh_bandpass` — HKH 带通波形（GT 波形）
- `hkh_t_host_utc_ns` / `cs_t_host_utc_ns` — 绝对时间轴
- `fs_ble` / `fs_hkh` — 实测采样率

比反复解析 JSONL 更适合验证脚本和 notebook 快速调用。**原始 jsonl 仍保留**，供需要完整帧结构的算法 pipeline 使用。

场景配置：`config/scenarios/room_A-sbj_A-07101613.json`

---

## 5. B2 验证（HKH 作 GT）

运行：

```bash
python notebooks/scripts/chFusion_ble_hkh_b2_validation.py
```

### 5.1 指标

| 指标 | 定义 |
|------|------|
| **BPM 绝对误差** | 每窗 \|B2 BPM − HKH BPM\|（单位：次/分）；报告 mean ± std |
| **BPM 相对误差** | 同上，除以 HKH BPM × 100%（JSON 中保留，便于跨场景对比） |
| **窗级 RMSE** | 每窗 B2 合成带通波形 vs HKH 带通；z-score 标准化 + 符号翻转取 min；报告 mean ± std |

滑窗：**20 s 窗长 / 1 s 步长**（与项目标准一致）。

### 5.2 首条数据 B2 结果（2026-07-10，fs 修复后）

| 方法 | BPM err (mean±std) | RMSE (mean±std) |
|------|-------------------:|----------------:|
| B2-D Two-level Hilbert-MRC | **0.42±0.31 BPM** | 0.762±0.369 |
| B2-B Hilbert η·ρ | **0.62±0.52 BPM** | 0.852±0.338 |
| B2-A0 PCA sign | **0.69±0.71 BPM** | 1.080±0.253 |
| B2-A1 Corr sign | **0.72±0.87 BPM** | 1.066±0.227 |

（HKH GT 窗均值约 **10.7 BPM**；B2-D 窗均值约 **8.4 BPM**。）

### 5.3 采样率与误差（重要）

2026-07-10 曾出现两轮 fs 相关 bug，均已修复（见 `docs/plans/hkh_sampling_rate_fix_plan.md`）：

| 阶段 | HKH fs 用法 | B2-D BPM err | HKH GT 均值 | 问题 |
|------|-------------|-------------:|------------:|------|
| 初版 | `len/duration` ≈ 50.7 Hz 估 BPM | ~5.7 | ~16.3 | GT BPM 被放大（commit 前） |
| 误修（6d59d09） | `t_host` 正差分 ≈ 19.6 Hz 滤波+估 BPM | **2.85±0.74** | 8.2 | 带通实际通带偏移至 0.26–0.91 Hz，GT 不可信 |
| **当前（修复后）** ✅ | `len/duration` ≈ 50.7 Hz 滤波+估 BPM + Welch `nfft` | **0.42±0.31** | **10.7** | 频域标度正确 |

**根因**：HKH 批量写入使 `estimate_fs_from_host_timestamps` 低估 fs；用 19.6 Hz 设计 0.1–0.35 Hz 带通会实际作用于 ~0.26–0.91 Hz，呼吸信号被严重衰减。同时 `estimate_bpm_from_waveform` 缺少 Welch `nfft` 零填充，加剧 bin 量化误差。

**正确做法**：

1. 预处理：`fs_hkh = len(hkh_crop) / duration_from_t_host` → `preprocess_meta.json` → `hkh_used`
2. 验证：从 meta 读取 `hkh_used` 传入 `fs_hkh_override`
3. Welch BPM：`nfft = max(nperseg, _next_pow2(4 * len(sig)))`

结果文件：

- `outputs/reports/ble_hkh_b2_validation_room_A-sbj_A-07101613.json`
- `outputs/figures/ble_hkh_b2_validation_room_A-sbj_A-07101613.png`

---

## 5.1 多算法对比（HKH GT）

脚本：`notebooks/scripts/chFusion_ble_hkh_multi_algorithm.py`  
模块：`src/ble_analysis/ble_hkh_multi_validation.py`

共 **26** 种方法（B0/B1、Systematic A/B/C、Modal 5 种、Voting T0–T3、B2 三主变体），238 个 20 s 滑窗，GT 来自 HKH 带通波形 Welch 寻峰（BLE 2.4 Hz，HKH **50.7 Hz**）。

**HKH GT 窗均值 ≈ 10.7 BPM**；多数 BLE 方法估计均值 ≈ 11.0 BPM。

### BPM 绝对误差排行榜（Top / Bottom）

| Rank | 方法 | BPM err (mean±std) | RMSE |
|------|------|-------------------:|-----:|
| 1 | C2 Uniform→η modal | **0.40±0.29** | — |
| 2 | B1 Vote→Equal modal | 0.41±0.29 | — |
| 3 | B1 Uniform Remote | 0.41±0.30 | — |
| 8 | B2-D Two-level Hilbert-MRC | 0.42±0.31 | **0.762±0.369** |
| 26 | A2 Phase persistence voting | 1.37±1.46 | — |

### 简要结论（单场景，不可外推）

1. **BPM 误差显著改善**：修复 fs 后，26 法误差 **0.40–1.37 BPM**（此前 ~2.75–3.0 BPM 系 GT 错误所致）。
2. **B2-D** BPM 排第 8（0.42 BPM），**RMSE 仍最低**（0.762），波形贴合最优。
3. **Uniform / Voting / Modal 系列** 与 B2-D 同量级（~0.4 BPM），差距 <0.05 BPM。
4. **Phase 投票**（A1/A2）std 仍较大（1.46），波动大。

产出：

- `outputs/reports/ble_hkh_multi_algorithm_room_A-sbj_A-07101613.json`
- `outputs/figures/ble_hkh_multi_algorithm_room_A-sbj_A-07101613.png`

---

## 5.2 三篇 WiFi 论文波形方法（Fan / Yu / Zhuo）

脚本：`notebooks/scripts/chFusion_ble_hkh_paper_baselines.py`  
模块：`src/ble_analysis/ble_hkh_paper_validation.py`

这些方法均 **输出融合呼吸波形**，再估计 BPM；同时报告窗级 **RMSE**（z-score + 符号对齐 vs HKH 带通）。

| 论文 | 方法 | BPM err (mean±std) | RMSE (mean±std) |
|------|------|-------------------:|----------------:|
| **Fan 2024** | η-linear (best modal) | **0.37±0.28** | 0.993±0.153 |
| **Fan 2024** | η-equal waveform avg | 0.53±0.37 | 1.013±0.160 |
| **Fan 2024** | Hilbert equal wf | 0.53±0.36 | 1.012±0.160 |
| **Yu 2021** | MRC-PCA √η (best modal) | 0.46±0.41 | 1.083±0.232 |
| **Yu 2021** | MRC-PCA η-equal PCA3→1 | 0.47±0.53 | 1.121±0.217 |
| **Zhuo 2023** | Z1 VMD→Peak | 0.66±0.45 | 1.117±0.220 |
| **Zhuo 2023** | Z1 VMD→FFT | 0.65±0.44 | 1.117±0.220 |
| **Zhuo 2023** | Z1-no-VMD→Peak | 0.51±0.39 | 1.139±0.113 |
| B2 参照 | B2-D Two-level | 0.42±0.31 | **0.762±0.369** |
| B2 参照 | B2-A0 PCA sign | 0.69±0.71 | 1.080±0.253 |

### 与金属板三场景结论的对比

| 维度 | 金属板（cs_091339 等） | 本段真人 HKH |
|------|------------------------|--------------|
| Fan/Yu vs B1/B2 BPM | 论文方法 **系统性劣于** B1/B2 | Fan η-linear **略优**（0.37 BPM），B2-D 0.42 |
| 最优波形 RMSE | B2-D 领先 | **B2-D 仍最低**（0.762） |
| Fan 波形融合 | equal-wf 跨域更差 | equal-wf BPM 0.53，略逊于 linear |

### 简要结论（单场景）

1. **Fan 2024 η-linear** BPM 最优（0.37），与 B2-D（0.42）同量级。
2. **Yu 2021 MRC-PCA** BPM ~0.46–0.47，波形 RMSE ~1.08–1.12。
3. **Zhuo 2023 VMD** 在本数据上 **无增益**（VMD 0.66 vs no-VMD 0.51 BPM）。
4. **B2-D** 波形形态仍最佳（RMSE 0.762）。

产出：

- `outputs/reports/ble_hkh_paper_baselines_room_A-sbj_A-07101613.json`
- `outputs/figures/ble_hkh_paper_baselines_room_A-sbj_A-07101613.png`

---

## 6. 代码模块

| 模块 | 路径 |
|------|------|
| HKH 加载 / fs 估计 | `src/ble_analysis/hkh_data.py` |
| 对齐裁剪滤波 | `src/ble_analysis/ble_hkh_preprocess.py` |
| 窗级 RMSE | `src/ble_analysis/waveform_metrics.py` |
| B2 vs HKH 验证 | `src/ble_analysis/ble_hkh_validation.py` |
| 多算法 vs HKH | `src/ble_analysis/ble_hkh_multi_validation.py` |
| 论文波形 vs HKH | `src/ble_analysis/ble_hkh_paper_validation.py` |
| Fan/Yu 实现 | `src/ble_analysis/wifi_mrc.py` |
| Zhuo 实现 | `src/ble_analysis/pca_vmd.py` |
| 预处理脚本 | `notebooks/scripts/preprocess_ble_hkh.py` |
| B2 验证脚本 | `notebooks/scripts/chFusion_ble_hkh_b2_validation.py` |
| 多算法脚本 | `notebooks/scripts/chFusion_ble_hkh_multi_algorithm.py` |
| 论文波形脚本 | `notebooks/scripts/chFusion_ble_hkh_paper_baselines.py` |

---

## 7. 后续新数据集

1. 将原始 `CS_*.jsonl` / `HKH_*.jsonl` 放入 `sampleData/ble-hkh/`（或子目录）。
2. 目视确定 BLE 干净段 seq 范围，以及 HKH 对应锚点 seq（`t_host_utc_ns` 一致处）。
3. 修改 `preprocess_ble_hkh.py` 中 `DATASET_NAME`、`CROP`、源路径，或扩展为 CLI 参数。
4. 运行预处理 → 检查 `outputs/figures/ble_hkh_preprocess_*.png` 对齐诊断图。
5. 运行 B2 验证 → 检查 RMSE / BPM 报告。

---

## 8. 保留问题

- [ ] BLE 实测 2.4 Hz vs 用户预期 4 Hz：需确认 CS 采集配置或 seq 间隔含义。
- [ ] HKH `t_host` 正差分（≈19.6 Hz）与 `len/duration`（≈50.7 Hz）差异：批量写入机制待文档化；**滤波/BPM 必须用后者**。
- [x] ~~BPM 误差 ~3 BPM~~：已确认系 HKH fs 误用 19.6 Hz 导致 GT 带通偏移；修复后 B2-D **0.42±0.31 BPM**。
- [ ] 是否将 RMSE 归一化方式（z-score vs 幅值归一化）写入正式指标定义。
