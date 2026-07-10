# HKH 采样率 + Welch nfft 修复 — 实现计划

> **来源**：Claude/DeepSeek Review of `hkh-data-test` branch (2026-07-10)
> **目标报告**：`docs/ble_hkh_preprocessing.md`（更新 §5 结果）
> **建议 plan 路径**：`docs/plans/hkh_sampling_rate_fix_plan.md`
> **日期**：2026-07-10
> **验证状态**：已完成

---

## 1. 动机与背景

| 项目 | 说明 |
|------|------|
| 问题 | HKH 预处理和 BPM 估计使用了错误的采样率（19.6 Hz，应为 50 Hz），导致 GT 带通滤波和 Welch PSD 频域标度整体偏离 2.55×；`estimate_bpm_from_waveform` 的 Welch 调用缺少 `nfft` 零填充，频率采样过粗 |
| 相关 commit | `6d59d09` — 将 HKH fs 从 `len/duration`（~50 Hz）错误地改为 `estimate_fs_from_host_timestamps`（~19.6 Hz） |
| 本 plan 定位 | **Bug fix** — 修复数据预处理管线中的采样率估计和 Welch PSD 参数，非新算法方案 |

### 根因分析

HKH 截取段（seq 21125–32144，11020 帧）从主机时间头尾计算：

```
fs_hkh = 11020 帧 / 217.5 s = 50.67 Hz ≈ 50 Hz
```

但当前代码使用 `estimate_fs_from_host_timestamps`（仅统计 `t_host_utc_ns` 正差分 >1 ms），因 HKH 存在批量写入（多个采样帧共享同一 `t_host_utc_ns`），大量差分被丢弃，得到 19.6 Hz。

用 fs=19.6 Hz 设计带通滤波器并应用于实际 50 Hz 采样的信号 → 实际通带 = [0.1, 0.35] × 50/19.6 ≈ [0.26, 0.91] Hz（设计目标 [0.1, 0.35] Hz）。呼吸信号（~0.14 Hz / ~8 BPM）被滤波器严重衰减，GT 不可信。

同时 Welch PSD 缺少 `nfft` 零填充，在 50 Hz 下呼吸频段仅 2 个 bin（bin=5.86 BPM），造成 ~3.5 BPM 的虚假误差。

增加 `nfft`（如 `max(nperseg, _next_pow2(4 * len(sig)))`）可将 bin 细化至 <1 BPM，误差降至 <1 BPM。

### 注意

当前 BLE CS 侧的 `estimate_segment_bpm_methods` / `estimate_modal_best_channel_fusion` 已通过 `cfg.nfft or _next_pow2(4 * win_len)` 做了 nfft 零填充。只需修复 `estimate_bpm_from_waveform` 中的 Welch 调用。

---

## 2. 物理与变量

本 plan 不改变使用的物理变量。仅修复信号处理管线的数值参数：

| 参数 | 当前值 | 修复后 | 影响范围 |
|------|--------|--------|----------|
| HKH fs（预处理） | 19.6 Hz | **50.0 Hz** | `ble_hkh_preprocess.py` |
| HKH fs（验证） | 19.6 Hz | **从 `preprocess_meta.json` 的 `hkh_used` 读取** | `ble_hkh_validation.py` |
| Welch `nfft` | `nperseg`（默认） | **`max(nperseg, nfft_spec)`** | `wifi_mrc.py:estimate_bpm_from_waveform` |

### HKH 采样率推导

截取段主机时间戳（`t_host_utc_ns`）头尾：

```
duration_s = (t_host[-1] - t_host[0]) / 1e9 = 217.50 s
n_frames = 11020
fs_hkh = n_frames / duration_s = 50.67 Hz → round to 50.0 Hz
```

### BLE 采样率

```
duration_s = (t_host[-1] - t_host[0]) / 1e9 = 217.50 s
n_frames = 523
fs_ble = n_frames / duration_s = 2.40 Hz  （与 t_dev_ms 差分一致）
```

BLE 侧无需修改。

---

## 3. 修改步骤

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: ble_hkh_preprocess.py                               │
│   HKH fs 估计改为 len(hkh_crop) / duration_from_t_host       │
│   → fs_hkh = 50.0 Hz                                        │
│   保存到 preprocess_meta.json → sampling_rate_hz.hkh_used   │
├─────────────────────────────────────────────────────────────┤
│ Step 2: wifi_mrc.py:estimate_bpm_from_waveform               │
│   增加 nfft 参数 → welch(..., nfft=nfft)                     │
│   nfft = max(nperseg, _next_pow2(4 * len(sig)))             │
│   [也可从 cfg.nfft 读取，默认 None 时自动计算]                │
├─────────────────────────────────────────────────────────────┤
│ Step 3: ble_hkh_validation.py                                │
│   compute_hkh_gt_per_window / validate_b2_against_hkh        │
│   → HKH fs 优先从 meta["sampling_rate_hz"]["hkh_used"] 读取  │
│   → 移除自行调用 estimate_fs_from_host_timestamps 的逻辑     │
├─────────────────────────────────────────────────────────────┤
│ Step 4: 重新运行                                             │
│   preprocess_ble_hkh.py → 三个验证脚本 → 对比修复前后结果     │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Step 1：预处理 HKH fs 修复

**文件**：`src/ble_analysis/ble_hkh_preprocess.py`，函数 `preprocess_ble_hkh_pair`

**当前代码**（约 L196-204）：
```python
hkh_t_host = np.array([r["t_host_utc_ns"] for r in hkh_crop], dtype=np.int64)
hkh_amp = np.array([r["amp"] for r in hkh_crop], dtype=float)

fs_hkh_host = estimate_fs_from_host_timestamps(hkh_t_host)
# ...
fs_hkh = fs_hkh_host
```

**修改为**：
```python
hkh_t_host = np.array([r["t_host_utc_ns"] for r in hkh_crop], dtype=np.int64)
hkh_amp = np.array([r["amp"] for r in hkh_crop], dtype=float)

# 从主机时间头尾计算精确采样率
hkh_duration_s = float((hkh_t_host[-1] - hkh_t_host[0]) / 1e9)
fs_hkh = float(len(hkh_crop) / max(hkh_duration_s, 1e-6))  # → 50.67 → ≈50 Hz
```

**理由**：主机时间是唯一真实的时钟源。截取段内 `t_host_utc_ns` 头尾差精确测量了总时长，帧数是确定的，`len/duration` 给出正确的平均采样率。不应使用 `estimate_fs_from_host_timestamps`（它丢弃了批量写入帧的差分信息）。

**输出变化**：`preprocess_meta.json` 中 `sampling_rate_hz.hkh_used` 从 ~19.6 → ~50.7 Hz。`aligned_bundle.npz` 中 `hkh_bandpass` 等滤波信号的频域标度变为正确。

### 3.2 Step 2：Welch nfft 零填充

**文件**：`src/ble_analysis/wifi_mrc.py`，函数 `estimate_bpm_from_waveform`

**当前代码**（约 L225-233）：
```python
nperseg = min(len(sig), 512)
noverlap = nperseg // 2
freqs, pxx = welch(
    sig - np.mean(sig),
    fs=fs,
    window="hann",
    nperseg=nperseg,
    noverlap=noverlap,
)
```

**修改为**：
```python
nperseg = min(len(sig), 512)
noverlap = nperseg // 2

# nfft: 从 cfg 读取，或自动计算（≥4×nperseg 以保证 <1 BPM bin）
if cfg is not None and cfg.nfft is not None:
    nfft = cfg.nfft
else:
    nfft = _next_pow2(max(nperseg, 4 * len(sig)))

freqs, pxx = welch(
    sig - np.mean(sig),
    fs=fs,
    window="hann",
    nperseg=nperseg,
    noverlap=noverlap,
    nfft=nfft,
)
```

需要从 `chfusion.py` 引入 `_next_pow2`，或在 `wifi_mrc.py` 中定义等价的辅助函数。

**参数对照**：

| 场景 | len(sig) | nperseg | 4*len(sig) | 建议 nfft | bin BPM |
|------|----------|---------|------------|-----------|---------|
| BLE 2.4 Hz | 48 | 48 | 192 | 256 | 0.56 |
| BLE 4.0 Hz | 80 | 80 | 320 | 512 | 0.47 |
| HKH 50 Hz | 1000+ | 512 | 4000+ | 4096 | 0.73 |

### 3.3 Step 3：验证模块 fs 来源统一

**文件**：`src/ble_analysis/ble_hkh_validation.py`

两个函数需要修改：`compute_hkh_gt_per_window` 和 `validate_b2_against_hkh`。

**当前逻辑**：
```python
fs_hkh = estimate_fs_from_host_timestamps(hkh_t_host)
if not np.isfinite(fs_hkh) or fs_hkh <= 0:
    fs_hkh = float(
        len(hkh_bandpass) / max((hkh_t_host[-1] - hkh_t_host[0]) / 1e9, 1e-6)
    )
```

**修改为**：如果调用方传入了 `fs_hkh_override`（已存在），使用之；否则从 `hkh_t_host` 头尾直接计算 `len(hkh_bandpass) / duration`：

```python
if fs_hkh_override is not None:
    fs_hkh = float(fs_hkh_override)
else:
    duration_s = float((hkh_t_host[-1] - hkh_t_host[0]) / 1e9)
    fs_hkh = float(len(hkh_bandpass) / max(duration_s, 1e-6))
```

同时在脚本侧（`chFusion_ble_hkh_*.py`）从 `preprocess_meta.json` 的 `sampling_rate_hz.hkh_used` 读取并传入 `fs_hkh_override`，确保一致。

### 3.4 Step 4：重新运行全套管线

```bash
# 1. 重新预处理（生成正确滤波的 HKH 带通信号）
python notebooks/scripts/preprocess_ble_hkh.py

# 2. 重新运行所有验证
python notebooks/scripts/chFusion_ble_hkh_b2_validation.py
python notebooks/scripts/chFusion_ble_hkh_multi_algorithm.py
python notebooks/scripts/chFusion_ble_hkh_paper_baselines.py
```

---

## 4. Baseline 对比

本 plan 是 bug fix，不引入新方法。验证方式为**修复前后 self-baseline**：

| 对比维度 | 修复前 | 修复后预期 |
|----------|--------|-----------|
| HKH fs | 19.6 Hz | **50.0 Hz** |
| HKH 带通滤波 | 实际通带 0.26–0.91 Hz（错误） | **实际通带 0.1–0.35 Hz（正确）** |
| HKH GT BPM | ~8.2 BPM（频域偏移，不可信） | **~8 BPM（基于正确滤波的波形）** |
| Welch bin（`estimate_bpm_from_waveform`） | nperseg 默认（≥3 BPM） | **nfft 细化（≤1 BPM）** |
| BLE vs HKH BPM 误差 | ~2.8 BPM（可能不反映真实误差） | **预期变化，方向不确定** |
| HKH GT 波形形态 | 高频分量为主（滤波错误） | **呼吸频段为主** |
| RMSE | ~1.2–1.3（比较了不同频段的信号） | **有意义的波形比较** |

> **重要**：修复后 BPM 误差可能变大或变小，均属正常——因为修复前 GT 本身不可信。修复后的数值才是真实性能。

---

## 5. 评估设计

### 5.1 场景

| 场景 | 用途 |
|------|------|
| `config/scenarios/room_A-sbj_A-07101613.json` | 唯一 HKH 真人数据集 |

（后续新增 HKH 数据集时，预处理自动应用修复后的 fs 估计逻辑。）

### 5.2 指标

与现有一致，不做修改：

- BPM 绝对误差（mean ± std）vs HKH GT
- 窗级 RMSE（z-score + 符号对齐）vs HKH 带通波形
- GT BPM 均值、范围

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | HKH 带通滤波频域标度正确（确认通带为 0.1–0.35 Hz 物理频率） |
| **理想** | BPM 误差 < 3 BPM（单场景初步结论），RMSE 比较物理有意义 |
| **失败** | 不适用——这是 bug fix，修复本身即为成功 |

---

## 6. 实现要点

### 6.1 修改文件清单

| 类型 | 路径 | 修改内容 |
|------|------|----------|
| 模块 | `src/ble_analysis/ble_hkh_preprocess.py` | HKH fs 估计改为 `len/duration` |
| 模块 | `src/ble_analysis/wifi_mrc.py` | `estimate_bpm_from_waveform` 增加 `nfft` |
| 模块 | `src/ble_analysis/ble_hkh_validation.py` | `compute_hkh_gt_per_window` + `validate_b2_against_hkh` fs 来源统一 |
| 脚本 | `notebooks/scripts/preprocess_ble_hkh.py` | 无需修改（自动继承模块修改） |
| 脚本 | `notebooks/scripts/chFusion_ble_hkh_b2_validation.py` | 传入 `fs_hkh_override` 从 meta |
| 脚本 | `notebooks/scripts/chFusion_ble_hkh_multi_algorithm.py` | 传入 `fs_hkh_override` 从 meta |
| 脚本 | `notebooks/scripts/chFusion_ble_hkh_paper_baselines.py` | 传入 `fs_hkh_override` 从 meta |
| 文档 | `docs/ble_hkh_preprocessing.md` | 更新 §5 结果与 §5.3 说明 |

### 6.2 不做的事

- 不修改 BLE CS 采样率估计（`estimate_sampling_rate_from_frames` — 对 BLE 正确）
- 不修改 `_energy_ratio` / `_peak_prominence`（η/ρ 用 `rfft`，已经够用）
- 不修改原始数据、ground truth 格式、指标定义
- 不修改基准方法（B0/B1/B2/Voting 等）的算法逻辑
- 不对 BLE 做降采样到 2 Hz（后续可单独评估）

### 6.3 辅助函数 `_next_pow2`

`chfusion.py` 中已定义。建议在 `wifi_mrc.py` 中直接复用：

```python
from ble_analysis.chfusion import _next_pow2
```

或复制该函数到 `wifi_mrc.py` 以减少模块耦合。

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| 更新预处理产物 | `sampleData/processed/room_A-sbj_A-07101613/aligned_bundle.npz`（覆盖） |
| 更新预处理 meta | `sampleData/processed/room_A-sbj_A-07101613/preprocess_meta.json`（覆盖） |
| B2 验证结果 | `outputs/reports/ble_hkh_b2_validation_room_A-sbj_A-07101613.json`（覆盖） |
| 多算法对比结果 | `outputs/reports/ble_hkh_multi_algorithm_room_A-sbj_A-07101613.json`（覆盖） |
| 论文基线结果 | `outputs/reports/ble_hkh_paper_baselines_room_A-sbj_A-07101613.json`（覆盖） |
| 更新图表 | `outputs/figures/ble_hkh_*.png`（覆盖） |
| 更新文档 | `docs/ble_hkh_preprocessing.md`（追加修复说明 + 更新结果表） |

---

## 8. 验证状态与保留问题

> 由 **执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | 已完成 |
| **实际脚本** | `preprocess_ble_hkh.py`；`chFusion_ble_hkh_b2_validation.py`；`chFusion_ble_hkh_multi_algorithm.py`；`chFusion_ble_hkh_paper_baselines.py` |
| **报告链接** | `docs/ble_hkh_preprocessing.md` §5 |
| **一句话结论** | HKH fs 修复为 len/duration（50.7 Hz）+ Welch nfft 后，B2-D BPM 误差从 2.85 降至 **0.42 BPM**，算法性能正常 |

### 保留问题

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | 修复后 BLE vs HKH BPM 误差是否 < 3 BPM？ | ✅ B2-D 0.42 BPM（单场景） |
| Q2 | HKH 带通波形是否呈现典型的呼吸形态（0.1–0.35 Hz）？ | 待目视检查 `ble_hkh_preprocess_*.png` |
| Q3 | BLE 非均匀采样（300/400/550 ms）是否对 BPM 估计有残余影响？ | 后续可尝试重采样到 2 Hz uniform |
| Q4 | `_energy_ratio` 和 `_peak_prominence` 的 `rfft` 是否需要类似 nfft 处理？ | 低优先级；当前用于信道排序 |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/hkh_sampling_rate_fix_plan.md`

执行顺序：
1. 修改 `ble_hkh_preprocess.py` → HKH fs = `len/duration`
2. 修改 `wifi_mrc.py` → `estimate_bpm_from_waveform` 增加 `nfft`
3. 修改 `ble_hkh_validation.py` → fs 来源统一
4. 修改三个验证脚本 → 传入 `fs_hkh_override`
5. 重新运行 `preprocess_ble_hkh.py`
6. 重新运行三个验证脚本
7. 更新 `docs/ble_hkh_preprocessing.md` 结果表
8. 回填本 plan §8 验证状态

执行完成后，请将以下材料返回给 Claude/DeepSeek Review：
- 本 plan（含回填的验证状态）
- 更新后的 `docs/ble_hkh_preprocessing.md`
- 所有 `outputs/reports/ble_hkh_*.json`
- 所有 `outputs/figures/ble_hkh_*.png`
- 修改的脚本和模块路径
- git diff 摘要
