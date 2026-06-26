# Zhuo 2023 PCA-VMD 外部基线 — 复现计划

> **来源**：`docs/papers/zhuo2023position.md` — Zhuo et al., "Position-Free Breath Detection During Sleep via Commodity WiFi", IEEE Sensors Journal, 2023  
> **目标报告**：`docs/reports/zhuo2023_pca_vmd_baseline_report.md`  
> **日期**：2026-06-26  
> **验证状态**：已完成

---

## 1. 动机与背景

### 1.1 问题

Zhuo 2023 提出 PCA-VMD 融合方案用于 WiFi CSI 呼吸检测。核心思路：先对多子载波做 PCA 提取主导呼吸成分，再用 VMD（K=3）分解为窄带模态，选方差最大者作为最终呼吸信号，最后通过峰值检测估计呼吸率。

本 plan 将 **PCA-VMD 核心融合思路** 迁移到 BLE CS 平台，作为外部基线参与排行榜比较。复现聚焦于 PCA 两级融合 + VMD 分解 + 峰值检测 BPM，跳过 WiFi 特有的 CSI ratio 和复平面投影步骤。

### 1.2 与现有工作的关系

| 项目 | 说明 |
|------|------|
| 当前最优 | B1 Vote→Equal（跨域 8.45%）— 逐模态 Voting → 三模态等权谱融合 |
| 现有 PCA | `pca_svd.py` 已有 PCA/SVD 降维 + 谱融合 BPM，但**不含两级 PCA、不含 VMD、不含峰值检测 BPM** |
| 现有 WiFi 基线 | `wifi_mrc.py` — Fan 2024 / Yu 2021 的时域 MRC 路线，全局劣于 B1 |
| 本 plan 定位 | **新增外部基线**：PCA-VMD 是 WiFi CSI 文献中与 MRC 正交的路线（PCA 降维 + VMD 模态分解），考察其在 BLE CS 低采样率下的可行性 |

---

## 2. 物理与变量

### 2.1 使用哪些变量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 三种可用变量之一，对称对待 |
| `local_amplitudes` | ✅ | 三种可用变量之一，对称对待 |
| `phases`（总相位，unwrap） | ✅ | 三种可用变量之一，对称对待 |
| `amplitudes`（总幅值） | ❌ | 无独立物理意义（remote × local 噪声乘积） |

### 2.2 变量与论文的对应

论文使用 WiFi CSI ratio（复数，60 stream = 2 RX × 30 subcarrier）。BLE CS 等效为：

| 论文 | BLE CS 等效 | 说明 |
|------|------------|------|
| 1 个 CSI ratio stream（复数 I+jQ） | 1 个 tone 的 `A(t)·e^(jφ(t))`（复数） | 用于投影步骤 |
| 多子载波 PCA 融合 | 72 tone per variable PCA（第一级） | 论文用 30 或 60 stream，我们 72 tone |
| 单链路 | 单一 BLE CS 测量（无多天线对） | BLE CS 无双天线对概念，三个场景各为独立数据集 |

### 2.3 符号约定

| 符号 | 含义 | 对应论文 |
|------|------|----------|
| η | 呼吸频段能量比 | BNR（论文 §9.6） |
| ρ | 谱峰峰度 | —（论文用 variance 选模态） |
| K | VMD 模态数 | 论文 K=3 |
| α | VMD 带宽约束 | 论文未明确 |

---

## 3. 算法步骤（含完整流程图）

### 3.1 主方案 Z1：PCA(72) → PCA(3) → VMD → 峰值检测 BPM

```text
┌──────────────────────────────────────────────────────────────────┐
│ Step 0: 原始数据                                                    │
│ Raw BLE CS Frames                                                 │
│ 72 tones × 3 variables (remote_amplitudes, local_amplitudes,      │
│ phases) × T 帧                                                     │
│ [模块: data.py → load_ble_frames()]                                │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 1: Phase Unwrap（仅 phases 变量）                              │
│ phases[tone] = np.unwrap(raw_phases[tone])                        │
│ [模块: chfusion.py → _preprocess_raw_series()]                     │
│ remote/local amplitudes: 不做处理，直接进入滤波                      │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 2: 逐 tone 滤波链（per tone, per variable）                     │
│                                                                   │
│   raw[tone]                                                        │
│     → median filter (window=3)                                     │
│     → highpass filter (0.05 Hz, order=1)                           │
│     → bandpass filter (0.1–0.35 Hz, order=2)                       │
│                                                                   │
│ 输出: 每个 tone 得到 3 个滤波后信号:                                  │
│   • bandpass_filtered (0.1–0.35 Hz) — 用于 PCA                    │
│   • highpass_filtered (≥0.05 Hz) — 用于 η 计算                     │
│   • median_filtered — 保留                                         │
│                                                                   │
│ [模块: segments.py → FilterParams + process_segments()]            │
│ [模块: chfusion.py → run_multichannel_segment_filtering()]         │
│                                                                   │
│ 维度: 72 tones × 3 vars × T 样本                                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 3: 滑窗                                                        │
│ 窗长: 20 s, 步长: 1 s                                              │
│ 每窗样本数: win_len = 20 × fs ≈ 40 samples (fs≈2 Hz)               │
│ [模块: segments.py → _sliding_window_indices()]                    │
│                                                                   │
│ 以下 Step 4–9 对每个滑窗独立执行                                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 4 [可选变体 Z1_proj]: 复平面投影 + BNR/Variance 联合选择         │
│                                                                   │
│ 仅对 remote/local amplitudes 执行（phase 跳过此步）:                  │
│                                                                   │
│ Per tone t:                                                        │
│   构造复信号: z_t(t) = A_t(t) · e^(j·φ_t(t))                       │
│   I_t(t) = A_t(t)·cos(φ_t(t)),  Q_t(t) = A_t(t)·sin(φ_t(t))       │
│                                                                   │
│   对 100 个投影角 θ_j ∈ [0, π), j=0..99:                            │
│     x_{t,j}(t) = I_t(t)·cos(θ_j) + Q_t(t)·sin(θ_j)                │
│                = A_t(t) · cos(φ_t(t) - θ_j)                        │
│                                                                   │
│   对每个候选 x_{t,j}:                                               │
│     BNR_j  = η(x_{t,j})  [复用 _energy_ratio()]                    │
│     Var_j  = variance(x_{t,j})                                     │
│     Score_j = 0.5·BNR_norm_j + 0.5·Var_norm_j                     │
│                                                                   │
│   选择: j* = argmax Score_j,  输出信号: x_t(t) = x_{t,j*}(t)       │
│                                                                   │
│ 产出: 72 个 best-projected real signals (per amplitude variable)    │
│                                                                   │
│ 主方案 Z1: 跳过此步，直接使用 bandpass_filtered 进入 PCA              │
│ 变体 Z1_proj: 执行此步，用投影后信号替代 bandpass_filtered 进入 PCA    │
│                                                                   │
│ [新增: pca_vmd.py → project_complex_candidates()]                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 5: PCA 第一级 — 逐变量 72-tone → PC1                           │
│                                                                   │
│ 对每个变量 var ∈ {remote_amplitudes, local_amplitudes, phases}:     │
│                                                                   │
│   构造 M×72 数据矩阵 X_var（M=win_len, 每列一个 tone 的 bandpass）    │
│   [复用: pca_svd.py → build_channel_data_matrix()]                 │
│                                                                   │
│   z-score 标准化（每列去均值除标准差）                                 │
│   [复用: pca_svd.py → _normalize_matrix(method="zscore")]          │
│                                                                   │
│   协方差矩阵特征分解 → PC1                                          │
│   [复用: pca_svd.py → extract_breath_waveform_pca()]               │
│                                                                   │
│ 产出: 3 个 PC1 波形（每变量一个，长度 M）                             │
│   PC1_remote(t), PC1_local(t), PC1_phase(t)                        │
│                                                                   │
│ 维度变化: 72 tones × M → 3 waveforms × M                            │
│ 论文对应: §9.14 PCA 融合（论文对全部子载波一起做，我们分变量做）        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 6: 波形方向对齐（符号一致性）                                    │
│                                                                   │
│ 以方差最大的 PC1 为参考，对其余 PC1 做 correlation-based sign flip:    │
│   ref = PC1 with max(Var)                                          │
│   for each PC1_i:                                                  │
│     if corr(PC1_i, ref) < 0: PC1_i = -PC1_i                        │
│                                                                   │
│ [复用: pca_svd.py → align_waveform_sign() — 需改为三波形批量对齐]    │
│ 论文对应: §9.12 波形方向调整                                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 7: PCA 第二级 — 3 模态 PC1 → 1 融合波形                         │
│                                                                   │
│   构造 M×3 数据矩阵: [PC1_remote, PC1_local, PC1_phase]             │
│                                                                   │
│   z-score 标准化 → PCA → PC1                                       │
│   [复用: pca_svd.py → extract_breath_waveform_pca()]               │
│                                                                   │
│ 产出: y_pca(t) — 两级 PCA 融合呼吸波形（长度 M）                     │
│                                                                   │
│ 维度变化: 3 waveforms × M → 1 waveform × M                          │
│ 论文对应: §9.14（论文仅一级 PCA，我们两级——这是 BLE CS 三变量结构的适配）│
│                                                                   │
│ [可选变体 Z1_hilbert: Step 6 替换为 Hilbert 连续相位对齐后再 PCA]     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 8: VMD 分解 + 模态选择                                         │
│                                                                   │
│ 对 y_pca(t) 做 VMD (K=2–4, α≈3000, τ=0, DC=0, init=1, tol=1e-7):  │
│                                                                   │
│   modes, modes_hat, omega = VMD(y_pca, α, τ, K, DC, init, tol)    │
│   [新增依赖: vmdpy → from vmdpy import VMD]                        │
│                                                                   │
│ 模态选择准则:                                                       │
│   k* = argmax_k Var(modes[k])                                      │
│   y_final(t) = modes[k*]                                           │
│                                                                   │
│ [新增: pca_vmd.py → vmd_decompose_and_select()]                    │
│ 论文对应: §9.15 VMD 分解（K=3, max-Var 选模态）                      │
│                                                                   │
│ VMD 参数消融（在单场景上执行）:                                       │
│   K ∈ {2, 3, 4}                                                    │
│   α ∈ {500, 1000, 2000, 3000, 5000}                                │
│ 选择跨窗平均 η 最高或 BPM err 最低的组合作为最终参数                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 9a [主方案 Z1]: 峰值检测 → BPM（论文方式）                       │
│                                                                   │
│ 对 y_final(t) 做峰值检测:                                           │
│                                                                   │
│   min_distance = int(fs × 1.2)  # 最小峰间距 ≈ 1.2 s               │
│   peaks, props = find_peaks(y_final, distance=min_distance,        │
│                              prominence=prominence_threshold)       │
│   [scipy.signal.find_peaks]                                        │
│                                                                   │
│ 伪峰剔除 (§9.17):                                                   │
│   intervals = diff(peaks) / fs                                     │
│   若 interval < min_breath_period (≈ 1.5 s 对应 40 BPM):           │
│     保留 prominence 更大的峰，剔除另一个                              │
│   若 interval > max_breath_period (≈ 10 s 对应 6 BPM):             │
│     标记为可疑（可能漏检），不剔除                                    │
│                                                                   │
│ 呼吸率估计 (§9.18):                                                 │
│   mean_period = mean(valid_intervals)                              │
│   BPM = 60 / mean_period                                           │
│                                                                   │
│ [新增: pca_vmd.py → estimate_bpm_from_peaks()]                     │
│ 论文对应: §9.16–9.18                                                │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 9b [消融变体 Z1_fft]: FFT 寻峰 → BPM（本项目标准方式）           │
│                                                                   │
│ 对 y_final(t) 做 FFT:                                              │
│   windowed = (y_final - mean) × hanning                            │
│   power = |rFFT(windowed, n=nfft)|²                                │
│   f_peak = argmax_{f∈[0.1,0.35]Hz} power(f)                       │
│   BPM = 60 × parabolic_refined_peak(f_peak)                        │
│                                                                   │
│ [复用: segments.py → _estimate_breathing_freq_hz()]                │
│ 或 [复用: chfusion.py → estimate_bpm_from_waveform()]              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 10: 段级 BPM 误差聚合                                           │
│ 每窗 BPM → 段级 mean / signed err / rel err                         │
│ [复用: chfusion.py → _seg_bpm_stats()]                              │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 方法变体总览

| 变体 ID | 描述 | Step 4 投影 | Step 6 对齐 | Step 8 VMD | Step 9 BPM | 目的 |
|---------|------|------------|------------|------------|------------|------|
| **Z1** | **PCA(72)→PCA(3)→VMD→Peak** | 无 | Corr sign | K=2–4 | 峰值检测 | **主方案（论文路线）** |
| Z1_fft | PCA(72)→PCA(3)→VMD→FFT | 无 | Corr sign | K=2–4 | FFT argmax | FFT vs 峰值检测消融 |
| Z1_no_vmd | PCA(72)→PCA(3)→Peak | 无 | Corr sign | 无 | 峰值检测 | **VMD 增益消融** |
| Z1_no_vmd_fft | PCA(72)→PCA(3)→FFT | 无 | Corr sign | 无 | FFT argmax | PCA-only FFT 对照 |
| Z1_proj | Proj→PCA(72)→PCA(3)→VMD→Peak | 有 | Corr sign | K=2–4 | 峰值检测 | 投影步骤增益 |
| Z1_hilbert | PCA(72)→Hilbert→PCA(3)→VMD→Peak | 无 | Hilbert 连续相位 | K=2–4 | 峰值检测 | Hilbert vs Corr 对齐 |

> **执行优先级**：Z1 + Z1_no_vmd（必须）> Z1_fft > Z1_proj > Z1_hilbert。VMD 参数 K/α 消融在 Z1 的单场景调试阶段完成。

### 3.3 VMD 参数消融设计

在**单场景**（建议 cs_095806，Voting 优势场景，信号质量较好）上对 Z1 执行：

| 参数 | 候选值 | 选择准则 |
|------|--------|----------|
| K | 2, 3, 4 | 跨窗 mean η 最高 + BPM err 最低 |
| α | 500, 1000, 2000, 3000, 5000 | VMD 收敛率 + BPM err |

选定最优 (K, α) 后，固定用于三场景全量实验。

---

## 4. Baseline 对比

### 4.1 必跑方法

| 方法 ID | 描述性名称 | 实现参考 |
|---------|-----------|----------|
| B0 | Single Remote（max-η 单信道 → FFT BPM） | `chfusion.py` |
| B1 (Uniform) | Uniform Remote（72 tone 等权谱平均 → FFT BPM） | `chfusion.py` |
| Modal top2 | 逐模态 max-η 最优信道 → Top2 等权谱融合 → FFT BPM | `chfusion.py` |
| B1 Vote→Equal | 逐模态 Voting → 三模态等权谱融合 → FFT BPM（当前最优） | `systematic_fusion.py` |
| PCA modal equal | PCA per-modal → equal 谱融合 → FFT BPM（现有 PCA 方法） | `pca_svd.py` |
| **Z1** | **PCA(72)→PCA(3)→VMD→峰值检测 BPM**（本 plan 主方案） | 新增 `pca_vmd.py` |
| **Z1_no_vmd** | **PCA(72)→PCA(3)→峰值检测 BPM**（VMD 消融） | 新增 `pca_vmd.py` |

### 4.2 预期相对关系（假设，可被实验推翻）

| 对比 | 预期 | 理由 |
|------|------|------|
| Z1 vs Z1_no_vmd | 若 VMD 有效则 Z1 更优 | VMD 应能分离呼吸模态与噪声模态 |
| Z1 vs B1 Vote→Equal | [待确认] | 不同技术路线：时域 PCA+VMD+峰值 vs 频域 Voting+FFT |
| Z1 vs B0 Single Remote | 预期 Z1 更优 | PCA 利用多 tone 信息 |
| Z1_fft vs Z1 | [待确认] | FFT vs 峰值检测在低采样率下的精度差异 |

---

## 5. 评估设计

### 5.1 场景

三个标准验证场景，权重相等：

| 场景 JSON | 用途 |
|-----------|------|
| `config/scenarios/cs_091339.json` | 跨域验证（复杂多径） |
| `config/scenarios/cs_095806.json` | 跨域验证（Voting 优势） |
| `config/scenarios/cs_102621.json` | 跨域验证 |

### 5.2 指标

| 指标 | 说明 |
|------|------|
| 分段 BPM 相对误差 %（mean） | 主指标 |
| 分段 BPM 相对误差 %（std） | 稳定性 |
| 跨域 mean | 三场景等权平均 |
| 窗级 signed error | 小提琴图 |
| VMD 收敛率 | `n_iter < max_iter` 的比例 |
| VMD 选中模态的中心频率 | 是否落在呼吸频带内 |

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | Z1/no_vmd 跨域 mean < 20%，且 VMD 收敛率 > 80% |
| **理想** | Z1 跨域 mean < 10% 或优于 WiFi MRC 最优（10.78%） |
| **突出** | Z1 接近或超越 B1 Vote→Equal（8.45%） |
| **失败** | 任意场景 mean > 25%，或 VMD 持续不收敛 |
| **VMD 无效** | Z1 与 Z1_no_vmd 跨域 mean 差异 < 0.5 pp — 则结论为"VMD 在 BLE CS 低采样率下无额外增益" |

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 | 说明 |
|------|------|------|
| **可复用模块（新建）** | `src/ble_analysis/pca_vmd.py` | PCA-VMD 两级融合 + 峰值检测 BPM + 投影 |
| 实验脚本（新建） | `notebooks/scripts/chFusion_zhuo2023_pca_vmd.py` | 单场景 benchmark + VMD 参数消融 |
| 跨域脚本（新建） | `notebooks/scripts/chFusion_zhuo2023_pca_vmd_cross_domain.py` | 三场景汇总 + 图表 |
| 场景配置 | 沿用现有 JSON | 无需修改 |

### 6.2 复用 API 清单

```python
# --- 数据加载 & 滤波（完全复用）---
from ble_analysis.chfusion import (
    ChFusionConfig,
    run_multichannel_segment_filtering,
    load_multichannel_for_scenario,
    _energy_ratio,           # = 论文 BNR
    _seg_bpm_stats,
    _overall_rel_error,
    _parabolic_peak_freq,
    estimate_bpm_from_waveform,  # 用于 Z1_fft
)

from ble_analysis.segments import (
    BreathMetricParams,
    FilterParams,
    _sliding_window_indices,
    _estimate_breathing_freq_hz,
)

# --- PCA（完全复用）---
from ble_analysis.pca_svd import (
    PcaSvdConfig,
    build_channel_data_matrix,
    extract_breath_waveform_pca,
    align_waveform_sign,
    _normalize_matrix,
    compute_channel_energy_weights,
    MODAL_PCA_VARIABLES,
)

# --- 场景（完全复用）---
from ble_analysis.scenarios import load_scenario

# --- 新增依赖 ---
from vmdpy import VMD           # pip install vmdpy
from scipy.signal import find_peaks  # 峰值检测（已有）
```

### 6.3 新增模块接口草案（`pca_vmd.py`）

```python
# -------- 复平面投影（变体 Z1_proj）--------

def project_complex_candidates(
    amplitude: np.ndarray,       # [T] real
    phase: np.ndarray,           # [T] real (unwrapped)
    fs: float,
    num_angles: int = 100,
    select_duration_sec: float = 12.0,
    n_fft: int = 8192,
    breath_band: Tuple[float, float] = (0.1, 0.35),
    w_bnr: float = 0.5,
    w_var: float = 0.5,
) -> Tuple[np.ndarray, float, dict]:
    """
    对单 tone 的 A(t)·e^(jφ(t)) 做复平面投影 + BNR/Var 联合选择。

    Returns
    -------
    best_signal : [T] 最优投影实信号
    best_theta : 最优投影角 (rad)
    info : BNR/Var/Scores 详情
    """


def project_all_tones(
    ch_map_amp: Dict,            # amplitude variable channel map
    ch_map_phase: Dict,          # phase channel map
    ch_list: List,
    st: int,
    end: int,
    fs: float,
    **proj_kw,
) -> np.ndarray:
    """
    对全部 tone 执行投影选择 → M×72 矩阵（每列一个 tone 的最优投影信号）。
    """


# -------- VMD 分解 + 模态选择 --------

def vmd_decompose_and_select(
    waveform: np.ndarray,        # [T] 时域波形
    fs: float,
    K: int = 3,
    alpha: float = 3000,
    selection: str = "max_variance",
    breath_band: Tuple[float, float] = (0.1, 0.35),
    tau: float = 0.0,
    DC: int = 0,
    init: int = 1,
    tol: float = 1e-7,
) -> Tuple[np.ndarray, np.ndarray, int, dict]:
    """
    VMD 分解 + 模态选择。

    Returns
    -------
    y_final : [T] 选出的模态
    all_modes : [K, T] 全部 K 个模态
    selected_idx : 选中模态索引
    info : {variances, bnrs, center_freqs, n_iter, converged}
    """


# -------- 峰值检测 BPM（论文方式）--------

def estimate_bpm_from_peaks(
    waveform: np.ndarray,
    fs: float,
    min_breath_interval_sec: float = 1.2,
    max_breath_interval_sec: float = 10.0,
    prominence: Optional[float] = None,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    峰值检测 + 伪峰剔除 → BPM。

    Returns
    -------
    bpm : float
    peaks : 峰位置索引
    valid_intervals : 有效峰间隔 (s)
    """


# -------- 单窗 PCA-VMD --------

def estimate_pca_vmd_window_bpm(
    multichannel_by_var: Dict,
    seg_name: str,
    ch_list: List,
    st: int, end: int,
    fs: float,
    cfg: ChFusionConfig,
    pca_cfg: PcaSvdConfig,
    *,
    vmd_K: int = 3,
    vmd_alpha: float = 3000,
    vmd_selection: str = "max_variance",
    use_projection: bool = False,
    use_hilbert_align: bool = False,
    bpm_method: str = "peak",  # "peak" | "fft"
) -> Tuple[float, dict]:
    """
    单窗 PCA(72)→[Proj?]→PCA(3)→VMD→BPM。

    Returns
    -------
    bpm : float
    info : {pc1_variance_ratios, pc2_variance_ratio, vmd_info, ...}
    """


# -------- 单段多窗 --------

def estimate_zhuo2023_pca_vmd_segment(
    multichannel_by_var: Dict,
    seg_name: str,
    *,
    config: ChFusionConfig = None,
    metric_params: BreathMetricParams = None,
    pca_cfg: PcaSvdConfig = None,
    variants: Sequence[str] = ("Z1", "Z1_no_vmd"),
    vmd_K: int = 3,
    vmd_alpha: float = 3000,
) -> Optional[dict]:
    """
    单段 PCA-VMD 多变体 BPM 估计。
    variants: "Z1", "Z1_no_vmd", "Z1_fft", "Z1_no_vmd_fft",
              "Z1_proj", "Z1_hilbert"
    """


# -------- 单场景 benchmark --------

def run_zhuo2023_pca_vmd_benchmark(
    frames,
    segment_config: Dict,
    *,
    filter_params: FilterParams = None,
    metric_params: BreathMetricParams = None,
    config: ChFusionConfig = None,
    verbose: bool = True,
    cache_dir: str = None,
    multichannel_by_var: Dict = None,
) -> dict:
    """
    单场景 PCA-VMD benchmark（含 baseline 方法）。
    返回结构对齐 wifi_mrc.run_wifi_mrc_benchmark()。
    """


# -------- 跨域聚合 --------

def compute_zhuo2023_cross_domain(
    results_by_scenario: Dict[str, dict],
) -> List[dict]:
    """跨域排行榜，复用 wifi_mrc.compute_wifi_mrc_cross_domain() 模式。"""
```

### 6.4 不做的事

- 不实现 CSI ratio 提取（WiFi 特有，BLE CS 不适用）
- 不实现 Savitzky-Golay 滤波（本项目已有 median 替代）
- 不实现 Hampel filter（已有实现，median 已覆盖其去异常点功能）
- 不修改 `pca_svd.py` 或 `chfusion.py`
- 不新增场景 JSON

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| 可复用模块 | `src/ble_analysis/pca_vmd.py` |
| 实验脚本 | `notebooks/scripts/chFusion_zhuo2023_pca_vmd.py` |
| 跨域脚本 | `notebooks/scripts/chFusion_zhuo2023_pca_vmd_cross_domain.py` |
| 数值结果 | `outputs/reports/zhuo2023_pca_vmd_results.npy` |
| VMD 消融结果 | `outputs/reports/zhuo2023_pca_vmd_vmd_ablation.npy` |
| 排行榜图 | `outputs/figures/zhuo2023_pca_vmd_leaderboard.png` |
| 跨域汇总图 | `outputs/figures/zhuo2023_pca_vmd_cross_domain_summary.png` |
| 消融对比图 | `outputs/figures/zhuo2023_pca_vmd_ablation.png` |
| 验证报告 | `docs/reports/zhuo2023_pca_vmd_baseline_report.md` |

### 7.1 建议运行命令

```bash
# 第一步：单场景 VMD 参数消融（在 cs_095806 上）
python notebooks/scripts/chFusion_zhuo2023_pca_vmd.py --scenario cs_095806 --ablation

# 第二步：三场景全量运行（使用消融选定的 K, α）
python notebooks/scripts/chFusion_zhuo2023_pca_vmd.py --all

# 第三步：跨域汇总 + 图表
python notebooks/scripts/chFusion_zhuo2023_pca_vmd_cross_domain.py
```

---

## 8. 风险与保留问题

### 8.1 算法风险

| ID | 风险 | 影响 | 缓解措施 |
|----|------|------|----------|
| R1 | VMD 在 ~2 Hz / 40 sample 窗长下不收敛 | VMD 模态无意义 | α 消融；不收敛窗 fallback 到 Z1_no_vmd |
| R2 | max-Var 模态选择误选噪声 | BPM 误差增大 | 检查选中模态中心频率是否在呼吸频带内 |
| R3 | 峰值检测在低采样率下精度不足 | BPM 偏倚大 | Z1_fft 作为对照，量化 BPM 估计方式差异 |
| R4 | 两级 PCA 中 PC1_phase 可能与 PC1_remote/local 相位差异大 | 第二级 PCA 的 PC1 方差占比低 | 检查 `pc2_variance_ratio`；若 < 0.4 则三波形共性弱 |

### 8.2 数据风险

| ID | 风险 | 影响 | 缓解措施 |
|----|------|------|----------|
| R5 | BLE CS 采样率（~2 Hz）远低于 WiFi CSI（~100 Hz） | VMD 时频分辨率受限 | 这是物理限制，如实报告即可 |
| R6 | 091339 复杂多径场景下 PCA-VMD 可能灾难性退化 | 跨域 mean 被拉高 | 逐场景报告，不掩盖退化 |

### 8.3 可比性风险

| ID | 风险 | 影响 | 缓解措施 |
|----|------|------|----------|
| R7 | Z1 使用峰值检测 BPM，baseline 全部使用 FFT BPM | BPM 估计方法不同，非纯融合策略比较 | Z1_fft 提供 FFT 对照，隔离 BPM 估计方式影响 |
| R8 | 两级 PCA 结构与论文一级 PCA 不同 | 不是论文的精确复现 | 明确标注为"论文思路的 BLE CS 适配"，非精确复现 |

### 8.4 需要执行后确认的问题

| ID | 问题 | 确认方式 |
|----|------|----------|
| Q1 | VMD (K, α) 最优参数组合？ | 消融实验 |
| Q2 | 两级 PCA 的 PC1 方差占比？第一级每变量、第二级三模态各是多少？ | 收集 `explained_variance_ratio` |
| Q3 | 峰值检测 vs FFT 的 BPM 差异多大？ | Z1 vs Z1_fft 逐窗对比 |
| Q4 | 投影步骤（Z1_proj）是否有增益？ | Z1_proj vs Z1 对比 |
| Q5 | 091339 是否退化？ | 若 mean > 25% 标记为场景不适用 |

---

## 9. 验证状态

> 由 **执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | 已完成 |
| **实际脚本** | `notebooks/scripts/chFusion_zhuo2023_pca_vmd.py`、`chFusion_zhuo2023_pca_vmd_cross_domain.py` |
| **报告链接** | [`docs/reports/zhuo2023_pca_vmd_baseline_report.md`](../reports/zhuo2023_pca_vmd_baseline_report.md) |
| **一句话结论** | PCA-VMD 跨域 11.31% 劣于 B1（8.45%）；VMD 无实质增益（Δ≈0.10 pp） |
| **VMD 最优参数** | K=2, α=2000（cs_095806 消融） |

**遗留问题**：091339 退化机制待诊断；095806 单场景 FFT 变体略优 B1 不可推广。

---

## 10. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/zhuo2023_pca_vmd_baseline_plan.md`

执行顺序：
1. 在 cs_095806 上跑 VMD 参数消融（K=2,3,4; α=500,1000,2000,3000,5000），选定最优 (K, α)
2. 用选定参数在三场景上跑全部变体（Z1, Z1_no_vmd, Z1_fft, Z1_no_vmd_fft, Z1_proj, Z1_hilbert）+ baseline
3. 跨域汇总 + 图表
4. 撰写报告

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/reports/zhuo2023_pca_vmd_baseline_report.md`
- `outputs/reports/zhuo2023_pca_vmd_*.npy`
- `outputs/figures/zhuo2023_pca_vmd_*.png`
- `src/ble_analysis/pca_vmd.py`
- `notebooks/scripts/chFusion_zhuo2023_pca_vmd.py`
- `notebooks/scripts/chFusion_zhuo2023_pca_vmd_cross_domain.py`
- git commit message 或 git diff 摘要
