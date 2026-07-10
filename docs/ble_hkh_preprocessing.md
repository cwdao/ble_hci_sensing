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
| HKH | 11020 | 217.5 s | **≈19.6 Hz**（由 `t_host_utc_ns` 正差分） |

> **说明**：HKH 设备标称 50 Hz（`t_dev_ms` 步进 20 ms），但有效 UTC 时间戳显示存在丢帧/合并写入，预处理 **以实测 fs 为准**，不强制重采样到 50 Hz。

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

### 5.2 首条数据 B2 结果（2026-07-10）

| 方法 | BPM err (mean±std) | RMSE (mean±std) |
|------|-------------------:|----------------:|
| B2-D Two-level Hilbert-MRC | **2.85±0.74 BPM** | 1.217±0.133 |
| B2-B Hilbert η·ρ | **2.88±0.96 BPM** | 1.230±0.114 |
| B2-A0 PCA sign | **2.75±1.14 BPM** | 1.297±0.088 |
| B2-A1 Corr sign | **2.90±1.04 BPM** | 1.269±0.112 |

（HKH GT 窗均值约 **8.2 BPM**；BLE B2 窗均值约 **11.1 BPM**。）

### 5.3 采样率与误差（重要）

早期验证曾误用 `fs_hkh = 帧数 / 总时长 ≈ 50.7 Hz` 估计 HKH BPM。因 HKH 存在批量写入（多帧共享 `t_host_utc_ns`），该公式等价于把标称 50 Hz 当作有效采样率，**GT BPM 被放大约 2×（~16.5 BPM）**，从而出现 ~5.8 BPM 的虚假大误差。

**正确做法**：HKH BPM 估计使用 `t_host_utc_ns` **正差分** 得到的有效 fs（本数据 **≈19.6 Hz**），与 `preprocess_meta.json` 中 `hkh_used` 一致。

| 配置 | B2-D BPM err | HKH GT 均值 | 说明 |
|------|-------------:|------------:|------|
| 实测 fs（BLE 2.4 + HKH 19.6）✅ | **2.85±0.74** | 8.2 | 当前默认 |
| 理论 fs（BLE 4 + HKH 50，滤波/估计均名义值） | 4.37±2.07 | 11.7 | 窗长 80 样本，物理时长≠20 s |
| 仅 HKH 用 50 Hz 估 BPM（旧 bug） | ~5.7 | ~16.3 | 不推荐 |

结论：**不是 B2 算法本身差，而是 HKH GT 的 fs 设置错误**；按实测有效 fs 后，误差回到 ~3 BPM 量级。

结果文件：

- `outputs/reports/ble_hkh_b2_validation_room_A-sbj_A-07101613.json`
- `outputs/figures/ble_hkh_b2_validation_room_A-sbj_A-07101613.png`

---

## 6. 代码模块

| 模块 | 路径 |
|------|------|
| HKH 加载 / fs 估计 | `src/ble_analysis/hkh_data.py` |
| 对齐裁剪滤波 | `src/ble_analysis/ble_hkh_preprocess.py` |
| 窗级 RMSE | `src/ble_analysis/waveform_metrics.py` |
| B2 vs HKH 验证 | `src/ble_analysis/ble_hkh_validation.py` |
| 预处理脚本 | `notebooks/scripts/preprocess_ble_hkh.py` |
| B2 验证脚本 | `notebooks/scripts/chFusion_ble_hkh_b2_validation.py` |

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
- [ ] HKH 有效 ~20 Hz：是否可通过固件/串口配置减少丢帧；GT BPM 必须用有效 fs，不可用 len/duration。
- [x] ~~BPM 误差 ~6 BPM~~：已确认系 HKH fs 误设为 ~50 Hz 导致 GT 放大；修正后 ~2.9 BPM。
- [ ] 是否将 RMSE 归一化方式（z-score vs 幅值归一化）写入正式指标定义。
