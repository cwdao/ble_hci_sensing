#!/usr/bin/env python3
"""
BLE CS PCA 呼吸波形提取 — 独立教学演示
===========================================

演示两种 PCA 方案从 BLE Channel Sounding 多信道数据中提取呼吸信号。

**方案 1: 实矩阵 PCA**
    将 72 个 tone 的高通滤波幅值构造成 M×N 矩阵（M=时间帧, N=信道），
    通过特征分解提取所有信道共享的"共同变化模式"（PC1）作为呼吸波形。

**方案 2: 复矩阵 PCA**
    构造 M×N 复矩阵 Z[i,j] = Aᵢⱼ · e^(j·φᵢⱼ)，在 Hermitian 协方差上
    做复 PCA，取 Re(PC1) 为呼吸波形。同时利用幅值和相位信息。

物理背景
--------
BLE CS 有 72 个 tone（子载波）。呼吸引起的胸腔位移通过多径信道传播，
会同时影响所有 tone 的幅值和相位。每个 tone 的信道响应变化由呼吸主导，
而电路噪声和多径干扰在不同 tone 上是不相关的——这便是 PCA 可以分离
信号与噪声的物理基础。

核心假设：呼吸信号在所有 72 个 tone 上表现为一个共同的变化模式，
PCA 的第一主成分 (PC1) 捕获的正是"方差最大的共同方向"。

输入数据格式
------------
BLE CS JSONL 文件，每行一个 JSON 帧对象，含 ``channels`` 字典。
每个信道条目包含: ``amplitude``, ``phase``, ``local_amplitude``, ``remote_amplitude``。

参考
----
- 项目模块: ``src/ble_analysis/pca_svd.py``
- 设计方案: ``docs/chFusion_pca_svd_plan.md``
- WiFi CSI 呼吸感知文献中 PCA/SVD 是标准降噪手段

依赖
----
仅需 numpy, scipy, matplotlib — 不依赖项目任何内部模块。

用法
----
::

    python pca_demo.py                                    # 使用默认数据
    python pca_demo.py sampleData/CS_frames_all_*.jsonl   # 指定文件

作者: Claude Code (提炼自项目 src/ble_analysis/pca_svd.py)
日期: 2026-06-15
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


# ============================================================================
# Part 1: 数据加载 — 从 BLE CS JSONL 解析多信道矩阵
# ============================================================================

def _channel_sort_key(ch: object) -> tuple:
    """排序键：数字信道在前，非数字 key 在后。"""
    s = str(ch)
    if s.lstrip("-").isdigit():
        return (0, int(s))
    return (1, s)


def load_jsonl_frames(filepath: str) -> List[dict]:
    """逐行读取 JSONL 文件，返回帧列表。"""
    frames: List[dict] = []
    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                frames.append(json.loads(stripped))
    print(f"✓ 加载 {len(frames)} 帧  ←  {Path(filepath).name}")
    return frames


def _find_ch_in_frame(channels: dict, target: object) -> object | None:
    """在帧的 channels 字典中查找 target（尝试 int/str 两种 key 类型）。"""
    for key in (target, str(target)):
        if key in channels:
            return key
    if isinstance(target, str) and target.lstrip("-").isdigit():
        key_i = int(target)
        if key_i in channels:
            return key_i
    return None


def extract_multichannel_matrix(
    frames: List[dict],
    variable: str = "amplitude",
) -> Tuple[np.ndarray, np.ndarray, float]:
    """从全部帧中提取 (T 帧 × N 信道) 数据矩阵并估算采样率。

    Parameters
    ----------
    frames : 帧列表
    variable : 要提取的字段名
        ``"amplitude"`` — 总幅值 (remote × local)
        ``"local_amplitude"`` — 本地幅值
        ``"remote_amplitude"`` — 远程幅值
        ``"phase"`` — 总相位（两端 PCT 向量相乘后 LO 漂移已抵消）

    Returns
    -------
    data : ndarray (T, N) — 缺失填充 NaN
    timestamps_ms : ndarray (T,)
    fs : float — 估算采样率 (Hz)
    """
    # 收集所有出现的信道号
    all_channels: set[object] = set()
    for f in frames:
        all_channels.update(f.get("channels", {}).keys())
    channels = sorted(all_channels, key=_channel_sort_key)
    print(f"  信道数: {len(channels)}")

    T = len(frames)
    N = len(channels)
    data = np.full((T, N), np.nan, dtype=float)
    timestamps = np.full(T, np.nan, dtype=float)

    for i, frame in enumerate(frames):
        timestamps[i] = frame.get("timestamp_ms", np.nan)
        ch_dict = frame.get("channels", {})
        for j, ch in enumerate(channels):
            matched = _find_ch_in_frame(ch_dict, ch)
            if matched is not None:
                data[i, j] = ch_dict[matched].get(variable, np.nan)

    # 估算采样率
    valid_ts = timestamps[~np.isnan(timestamps)]
    fs = 1000.0 / float(np.mean(np.diff(valid_ts))) if len(valid_ts) >= 2 else 2.0
    print(f"  数据矩阵: {T} 帧 × {N} 信道,  fs ≈ {fs:.1f} Hz  ({variable})")
    return data, timestamps, fs


# ============================================================================
# Part 2: 信号预处理 — 中值去脉冲 + 高通去趋势
# ============================================================================

def _fill_nan_linear(col: np.ndarray) -> np.ndarray:
    """线性插值填补单列中的 NaN。"""
    valid = ~np.isnan(col)
    if np.all(valid):
        return col.copy()
    if np.sum(valid) < 2:
        return col.copy()
    x_all = np.arange(len(col))
    return np.interp(x_all, x_all[valid], col[valid])


def median_filter_1d(x: np.ndarray, window: int = 3) -> np.ndarray:
    """一维中值滤波（去脉冲噪声），边缘用最近邻填充。"""
    from scipy.ndimage import median_filter as mf
    return mf(x, size=window)


def butter_highpass_coeffs(
    cutoff: float, fs: float, order: int = 1
) -> Tuple[np.ndarray, np.ndarray]:
    """Butterworth 高通滤波器系数 (b, a)。"""
    from scipy.signal import butter
    return butter(order, cutoff / (0.5 * fs), btype="high", analog=False)


def apply_highpass(data: np.ndarray, fs: float, cutoff: float = 0.05) -> np.ndarray:
    """按列高通滤波（零相位 filtfilt）。

    Parameters
    ----------
    data : (T, N) — 可能含 NaN
    fs : 采样率 (Hz)
    cutoff : 截止频率 (Hz)
    """
    from scipy.signal import filtfilt

    T, N = data.shape
    out = np.full_like(data, np.nan)
    b, a = butter_highpass_coeffs(cutoff, fs, order=1)
    for j in range(N):
        col = _fill_nan_linear(data[:, j])
        if len(col) < 4 or not np.all(np.isfinite(col)):
            continue
        col_dm = col - np.mean(col)
        out[:, j] = filtfilt(b, a, col_dm)
    return out


# ============================================================================
# Part 3: PCA 核心算法（从 pca_svd.py 内联，含完整教学注释）
# ============================================================================

def normalize_matrix(
    X: np.ndarray, method: str = "zscore", eps: float = 1e-12
) -> np.ndarray:
    """按列标准化 M×N 矩阵，消除信道间幅值差异。

    - ``"zscore"``  (推荐):  (x − μ) / σ   →  每列均值为 0、标准差为 1
    - ``"minmax"``:            (x − min)/(max−min)  →  每列缩放到 [0, 1]
    - ``"none"``:              不标准化（幅值大的信道会主导 PCA 结果）
    """
    Xf = X.astype(float)
    if Xf.shape[1] == 0:
        return Xf
    if method == "zscore":
        mu = np.mean(Xf, axis=0, keepdims=True)
        sigma = np.std(Xf, axis=0, ddof=1, keepdims=True)
        sigma[sigma < eps] = 1.0
        return (Xf - mu) / sigma
    if method == "minmax":
        xmin = np.min(Xf, axis=0, keepdims=True)
        xmax = np.max(Xf, axis=0, keepdims=True)
        denom = xmax - xmin
        denom[denom < eps] = 1.0
        return (Xf - xmin) / denom
    return Xf


def channel_energy_ratio(
    signal_seg: np.ndarray,
    fs: float,
    breath_low: float = 0.1,
    breath_high: float = 0.35,
    total_low: float = 0.05,
    total_high: float = 0.8,
    eps: float = 1e-12,
) -> float:
    """计算单信道呼吸频段能量占比 η。

    .. math::

        η = E_{breath} / E_{total}

    其中分子是呼吸频段 (0.1–0.35 Hz, 对应 6–21 BPM) 的 FFT 能量，
    分母是全频段 (0.05–0.8 Hz) 能量。

    η 越高 → 该信道中呼吸信号越强 → 可用于信道质量评估与加权。
    """
    if len(signal_seg) < 4 or not np.all(np.isfinite(signal_seg)):
        return 0.0
    windowed = (signal_seg - np.mean(signal_seg)) * np.hanning(len(signal_seg))
    fft_power = np.abs(np.fft.rfft(windowed)) ** 2
    fft_freq = np.fft.rfftfreq(len(windowed), 1.0 / fs)
    breath_mask = (fft_freq >= breath_low) & (fft_freq <= breath_high)
    total_mask = (fft_freq >= total_low) & (fft_freq <= total_high)
    breath_energy = float(np.sum(fft_power[breath_mask]))
    total_energy = float(np.sum(fft_power[total_mask]))
    return breath_energy / total_energy if total_energy > eps else 0.0


def extract_pc1_real(
    X: np.ndarray,
    normalize: str = "zscore",
    min_channels: int = 4,
    min_variance_ratio: float = 0.10,
    channel_weights: Optional[np.ndarray] = None,
    verbose: bool = True,
) -> Tuple[np.ndarray, dict]:
    """
    **实矩阵 PCA — 从多信道幅值提取 PC1 呼吸波形**

    输入: X ∈ R^(M×N)，M 帧，N 个 BLE tone（已高通滤波）

    ┌─────────────────────────────────────────────────────────┐
    │ Step 1. 有效信道数检查（≥ min_channels, 无 NaN/inf）    │
    │ Step 2. 按列 z-score 标准化: Zⱼ = (Xⱼ − μⱼ) / σⱼ       │
    │          目的: 消除不同 tone 的幅值量级差异              │
    │ Step 3. (可选) 按 √η 缩放列，给高 η 信道更高权重        │
    │ Step 4. 协方差矩阵: C = ZᵀZ / (M−1)   ∈ R^(N×N)        │
    │          为什么是 N×N? N=72 << M≈2000，特征分解极快      │
    │ Step 5. 特征分解: C = V diag(λ) Vᵀ, λ 降序              │
    │ Step 6. 主成分投影: PC1 = Z · v₁  ∈ R^M                │
    │          v₁ 是第一特征向量，Z 在所有列上的最优共同方向   │
    │ Step 7. 诊断: λ₁/Σλ ≥ min_variance_ratio?              │
    │          若 < 阈值 → 呼吸信号可能在被噪声污染的窗        │
    └─────────────────────────────────────────────────────────┘

    Parameters
    ----------
    X : (M, N) — 高通滤波后的多信道数据
    normalize : 列标准化方法
    min_channels : 最少有效信道数
    min_variance_ratio : PC1 方差占比下限（< 此值发出警告）
    channel_weights : (N,) — 可选 η 权重数组
    verbose : 打印诊断信息

    Returns
    -------
    waveform : (M,) — PC1 时间序列（即呼吸波形）
    info : dict — ``explained_variance_ratio``, ``pc1_variance_ratio``, ``warn``
    """
    eps = 1e-12
    info: dict = {
        "explained_variance_ratio": [],
        "pc1_variance_ratio": np.nan,
        "warn": [],
    }

    # Step 1: 有效性检查
    if X is None or X.size == 0 or X.shape[1] < min_channels:
        nch = X.shape[1] if X is not None else 0
        if verbose:
            print(f"  ⚠ 信道数不足: {nch} < {min_channels}")
        return np.full(X.shape[0], np.nan), info
    if not np.all(np.isfinite(X)):
        if verbose:
            print("  ⚠ 数据含 NaN/inf")
        return np.full(X.shape[0], np.nan), info

    M, N = X.shape
    if verbose:
        print(f"  输入: {M} 帧 × {N} 信道")

    # Step 2: 列标准化
    Z = normalize_matrix(X, normalize, eps)

    # Step 3: 可选 √η 信道加权
    if channel_weights is not None:
        w = np.maximum(np.asarray(channel_weights, dtype=float), 0.0)
        if w.shape[0] == N:
            s = float(np.sum(w))
            if s > eps:
                w = w / s * N   # 保持与均匀 PCA 的总尺度可比
                Z = Z * np.sqrt(w)[np.newaxis, :]

    # Step 4: N×N 协方差矩阵
    C = (Z.T @ Z) / max(M - 1, 1)

    # Step 5: 特征分解（eigh 升序 → 反转得降序）
    eigenvalues, eigenvectors = np.linalg.eigh(C)
    eigenvalues = eigenvalues[::-1]
    eigenvectors = eigenvectors[:, ::-1]

    # Step 6: 方差占比
    total_var = float(np.sum(eigenvalues))
    if total_var > eps:
        ratios = eigenvalues / total_var
    else:
        ratios = np.zeros(N)
        if N > 0:
            ratios[0] = 1.0
    info["explained_variance_ratio"] = ratios.tolist()
    info["pc1_variance_ratio"] = float(ratios[0]) if N > 0 else np.nan

    # Step 7: PC1 主导程度检查
    if info["pc1_variance_ratio"] < min_variance_ratio:
        msg = (
            f"PC1 方差占比={info['pc1_variance_ratio']:.3f} < "
            f"{min_variance_ratio}，呼吸信号可能不占主导"
        )
        if verbose:
            print(f"  ⚠ {msg}")
        info["warn"].append(msg)

    if verbose:
        print(f"  PC1 方差占比: {info['pc1_variance_ratio']:.3f}")
        print(f"  前 5 成分:    {[f'{r:.3f}' for r in ratios[:5]]}")

    # Step 8: 投影得到 PC1 时间序列
    pc1 = Z @ eigenvectors[:, 0]  # (M,)
    return pc1, info


def extract_pc1_complex(
    X_complex: np.ndarray,
    min_channels: int = 4,
    min_variance_ratio: float = 0.10,
    channel_weights: Optional[np.ndarray] = None,
    verbose: bool = True,
) -> Tuple[np.ndarray, dict]:
    """
    **复矩阵 PCA — 同时利用幅值与相位信息**

    输入: Z ∈ C^(M×N),  Z[i,j] = A_ij · exp(j · φ_ij)

    ┌─────────────────────────────────────────────────────────┐
    │ Step 1. 有效信道数检查                                   │
    │ Step 2. 每列中心化（减去复均值）                         │
    │          注: 不做 z-score（幅相联合结构不宜过度缩放）    │
    │ Step 3. (可选) √η 列加权                                 │
    │ Step 4. Hermitian 协方差: C = ZᴴZ / (M−1)  ∈ C^(N×N)   │
    │          C 是共轭对称的 → 特征值恒为实数                 │
    │ Step 5. 特征分解 (eigh)，取降序                          │
    │ Step 6. PC1 = Z · v₁, 取 Re(PC1) 为呼吸波形             │
    │          ⚠ 关键: 取实部，而非 |PC1|                       │
    │          |u₁| 会引入频率加倍 → 倍频 → BPM ~2× 真实值     │
    └─────────────────────────────────────────────────────────┘

    与实 PCA 的核心差异
    -------------------
    实 PCA 只看幅值（或只看相位），两者的呼吸信息可能互补。
    复 PCA 用一个复数同时编码 A（衰减）和 φ（相移），希望捕捉到
    更完整的信道变化模式。

    已知局限
    --------
    复 PCA Re(PC1) 在部分场景（如 cs_091339）上不如实 PCA + 模态融合
    稳定，存在半频/倍频风险。本脚本仅作教学对比，不构成部署推荐。

    Parameters
    ----------
    X_complex : (M, N) dtype complex
    min_channels : 最少有效信道数
    min_variance_ratio : PC1 方差占比下限
    channel_weights : (N,) — 可选 η 权重
    verbose : 打印诊断信息

    Returns
    -------
    waveform : (M,) — Re(PC1)，实数呼吸波形
    info : dict
    """
    eps = 1e-12
    info: dict = {
        "explained_variance_ratio": [],
        "pc1_variance_ratio": np.nan,
        "warn": [],
    }

    # Step 1: 有效性检查
    if (
        X_complex is None
        or X_complex.size == 0
        or X_complex.shape[1] < min_channels
    ):
        nch = X_complex.shape[1] if X_complex is not None else 0
        if verbose:
            print(f"  ⚠ 信道数不足: {nch} < {min_channels}")
        return np.full(X_complex.shape[0], np.nan), info

    M, N = X_complex.shape
    if verbose:
        print(f"  输入: {M} 帧 × {N} 信道 (复)")

    # Step 2: 每列中心化（复均值）
    Z = X_complex.astype(complex)
    Z = Z - np.mean(Z, axis=0, keepdims=True)

    # Step 3: 可选 √η 列加权
    if channel_weights is not None:
        w = np.maximum(np.asarray(channel_weights, dtype=float), 0.0)
        if w.shape[0] == N:
            s = float(np.sum(w))
            if s > eps:
                w = w / s * N
                Z = Z * np.sqrt(w)[np.newaxis, :]

    # Step 4: Hermitian 协方差 C = ZᴴZ / (M−1)
    C = (Z.conj().T @ Z) / max(M - 1, 1)

    # Step 5: 特征分解（Hermitian + eigh → 实特征值）
    eigenvalues, eigenvectors = np.linalg.eigh(C)
    eigenvalues = eigenvalues[::-1].real
    eigenvectors = eigenvectors[:, ::-1]

    # Step 6: 方差占比
    total_var = float(np.sum(eigenvalues))
    if total_var > eps:
        ratios = eigenvalues / total_var
    else:
        ratios = np.zeros(N)
        if N > 0:
            ratios[0] = 1.0
    info["explained_variance_ratio"] = ratios.tolist()
    info["pc1_variance_ratio"] = float(ratios[0]) if N > 0 else np.nan

    if info["pc1_variance_ratio"] < min_variance_ratio:
        msg = (
            f"复 PC1 方差占比={info['pc1_variance_ratio']:.3f} < "
            f"{min_variance_ratio}"
        )
        if verbose:
            print(f"  ⚠ {msg}")
        info["warn"].append(msg)

    if verbose:
        print(f"  复 PC1 方差占比: {info['pc1_variance_ratio']:.3f}")
        print(f"  前 5 成分:       {[f'{r:.3f}' for r in ratios[:5]]}")

    # Step 7: 复 PC1 取实部
    pc1 = Z @ eigenvectors[:, 0]
    return np.real(pc1), info


# ============================================================================
# Part 4: FFT 频谱分析与 BPM 估计
# ============================================================================

def estimate_bpm(
    waveform: np.ndarray,
    fs: float,
    breath_low: float = 0.1,
    breath_high: float = 0.35,
    nfft: Optional[int] = None,
    parabolic: bool = True,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """1D 呼吸波形 → FFT 功率谱 → 呼吸频带峰频 → BPM。

    使用 Hanning 窗抑制频谱泄漏，parabolic 插值精化峰频估计。

    Returns
    -------
    bpm : float — 估计值 (NaN 表示失败)
    freqs : (K,) — FFT 频率轴 (Hz)
    power : (K,) — 功率谱
    """
    if len(waveform) < 4 or not np.all(np.isfinite(waveform)):
        return np.nan, np.array([]), np.array([])

    if nfft is None:
        nfft = 2 ** int(np.ceil(np.log2(4 * len(waveform))))

    seg = waveform - np.mean(waveform)
    if np.std(seg) < 1e-12:
        return np.nan, np.array([]), np.array([])

    windowed = seg * np.hanning(len(seg))
    power = np.abs(np.fft.rfft(windowed, n=nfft)) ** 2
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)

    # 呼吸频带内找峰值
    mask = (freqs >= breath_low) & (freqs <= breath_high)
    if not np.any(mask):
        return np.nan, freqs, power

    band_p = power[mask]
    band_f = freqs[mask]
    k = int(np.argmax(band_p))
    f_hat = float(band_f[k])

    # Parabolic 插值: 修正峰频到亚 bin 精度
    if parabolic and 0 < k < len(band_p) - 1:
        y0, y1, y2 = band_p[k - 1], band_p[k], band_p[k + 1]
        denom = y0 - 2.0 * y1 + y2
        if abs(denom) > 1e-12:
            delta = 0.5 * (y0 - y2) / denom
            df = band_f[1] - band_f[0]
            f_hat = float(band_f[k] + delta * df)

    return 60.0 * f_hat, freqs, power


# ============================================================================
# Part 5: 主演示流程
# ============================================================================

def run_demo(data_path: str):
    """运行完整的 PCA 呼吸波形提取教学演示。"""
    print("=" * 72)
    print("  BLE CS PCA 呼吸波形提取 — 教学演示")
    print("=" * 72)

    # ── Step 1: 加载 ──────────────────────────────────────────
    print("\n[Step 1] 加载 BLE CS 帧数据 …")
    frames = load_jsonl_frames(data_path)

    amp_matrix, timestamps_ms, fs = extract_multichannel_matrix(frames, "amplitude")
    phase_matrix, _, _ = extract_multichannel_matrix(frames, "phase")

    T, N = amp_matrix.shape
    print(f"\n  → 总帧数={T}, 信道={N}, fs≈{fs:.1f} Hz, 时长≈{T/fs:.0f} s")

    # ── Step 2: 预处理 ────────────────────────────────────────
    print("\n[Step 2] 预处理: 中值滤波 + 高通 0.05 Hz …")

    # 幅值：逐列填 NaN → 中值 → 高通
    amp_filled = np.column_stack([
        _fill_nan_linear(amp_matrix[:, j]) for j in range(N)
    ])
    amp_median = np.column_stack([
        median_filter_1d(amp_filled[:, j], 3) for j in range(N)
    ])
    amp_hp = apply_highpass(amp_median, fs, cutoff=0.05)

    # 相位：逐列填 NaN → unwrap → 中值 → 高通
    phase_filled = np.column_stack([
        _fill_nan_linear(phase_matrix[:, j]) for j in range(N)
    ])
    phase_unwrapped = np.column_stack([
        np.unwrap(phase_filled[:, j]) for j in range(N)
    ])
    phase_median = np.column_stack([
        median_filter_1d(phase_unwrapped[:, j], 3) for j in range(N)
    ])
    phase_hp = apply_highpass(phase_median, fs, cutoff=0.05)

    print("  ✓ 滤波完成")

    # ── Step 3: 选取 20 秒分析窗 ──────────────────────────────
    print("\n[Step 3] 选取 20 秒分析窗口 …")
    win_sec = 20.0
    win_samples = int(round(win_sec * fs))
    if T < win_samples:
        win_samples = T
        win_sec = T / fs
        print(f"  ⚠ 数据仅 {win_sec:.1f} 秒，使用全部数据")

    st = max(0, (T - win_samples) // 2)   # 居中取窗
    end = st + win_samples
    time_axis = np.arange(win_samples) / fs
    print(f"  窗口: 帧 [{st}, {end}),  {win_samples} 帧 ≈ {win_sec:.1f} s")

    # ── 实 PCA 数据矩阵 ──────────────────────────────────────
    # 使用所有 72 个 tone 的高通幅值
    X_real = amp_hp[st:end, :]   # (M, N=72)
    # 只保留全部值有限的有效列
    valid_real = [j for j in range(N) if np.all(np.isfinite(X_real[:, j]))]
    X_real_valid = X_real[:, valid_real]
    print(f"  实 PCA 有效信道: {len(valid_real)} 列")

    # ── 复 PCA 数据矩阵 ──────────────────────────────────────
    # 取幅值和相位都有效的信道交集
    valid_complex: List[int] = []
    for j in range(N):
        ca = amp_hp[st:end, j]
        cp = phase_hp[st:end, j]
        if np.all(np.isfinite(ca)) and np.all(np.isfinite(cp)):
            valid_complex.append(j)
    X_complex = np.column_stack([
        amp_hp[st:end, j] * np.exp(1j * phase_hp[st:end, j])
        for j in valid_complex
    ])
    print(f"  复 PCA 有效信道: {len(valid_complex)} 列")
    print(f"  复矩阵示例值: Z[0,0] = {X_complex[0,0]:.2f}")

    # ── Step 4: 计算信道质量 η ───────────────────────────────
    print("\n[Step 4] 计算各信道呼吸能量比 η …")
    eta_all = np.array([
        channel_energy_ratio(amp_hp[st:end, j], fs) for j in range(N)
    ])
    print(f"  η ∈ [{np.min(eta_all):.4f}, {np.max(eta_all):.4f}], "
          f"均值={np.mean(eta_all):.4f}")

    # ── Step 5: 实矩阵 PCA ───────────────────────────────────
    print("\n[Step 5] ═══ 实矩阵 PCA ═══")
    print("  变量: total amplitudes (高通滤波)")
    print("  原理: 72 信道共享呼吸引起的共同变化 → PC1 = 呼吸波形")

    wf_real, info_real = extract_pc1_real(
        X_real_valid, normalize="zscore", verbose=True
    )
    bpm_real, freqs_r, power_r = estimate_bpm(wf_real, fs)
    if np.isfinite(bpm_real):
        print(f"  → 实 PCA 估计 BPM = {bpm_real:.1f}")
    else:
        print("  → 实 PCA BPM 估计失败 (NaN)")

    # ── Step 6: 复矩阵 PCA ───────────────────────────────────
    print("\n[Step 6] ═══ 复矩阵 PCA ═══")
    print("  变量: A · e^(j·φ)  (幅值 + 相位联合)")
    print("  原理: Hermitian PCA → Re(PC1) 避免 |u₁| 倍频陷阱")

    wf_complex, info_complex = extract_pc1_complex(
        X_complex, verbose=True
    )
    bpm_complex, freqs_c, power_c = estimate_bpm(wf_complex, fs)
    if np.isfinite(bpm_complex):
        print(f"  → 复 PCA 估计 BPM = {bpm_complex:.1f}")
    else:
        print("  → 复 PCA BPM 估计失败 (NaN)")

    # 波形相关性
    corr_wf = np.corrcoef(wf_real, wf_complex)[0, 1] if len(wf_real) > 1 else np.nan

    # ── Step 7: 可视化 ───────────────────────────────────────
    print("\n[Step 7] 生成 3×2 教学图表 …")

    fig, axes = plt.subplots(3, 2, figsize=(18, 13))
    fig.suptitle(
        f"BLE CS 多信道 PCA 呼吸波形提取 — 教学演示\n"
        f"数据: {Path(data_path).name}  |  "
        f"窗长: {win_sec:.0f} s  |  "
        f"fs={fs:.1f} Hz  |  "
        f"{len(valid_real)} 信道",
        fontsize=13,
        fontweight="bold",
    )

    # ── [0,0] 高通幅值矩阵热力图 ──
    ax = axes[0, 0]
    vlim = np.std(X_real_valid) * 3
    im = ax.imshow(
        X_real_valid.T, aspect="auto", cmap="RdBu_r",
        interpolation="none", vmin=-vlim, vmax=vlim,
    )
    ax.set_xlabel("时间帧")
    ax.set_ylabel("Tone 序号")
    ax.set_title(f"高通滤波幅值矩阵 ({X_real_valid.shape[0]} 帧 × {X_real_valid.shape[1]} 信道)")
    plt.colorbar(im, ax=ax, shrink=0.85, label="幅值 (去均值)")

    # ── [0,1] η 分布 ──
    ax = axes[0, 1]
    eta_plot = eta_all[valid_real]
    colors_eta = ["#2E86C1" if e > 0.1 else "#AAB7B8" for e in eta_plot]
    ax.bar(range(len(eta_plot)), eta_plot, color=colors_eta, alpha=0.8, width=0.8)
    ax.axhline(0.10, color="#E74C3C", ls="--", lw=1.2, alpha=0.5, label="η = 0.10 阈值")
    ax.set_xlabel("Tone 序号")
    ax.set_ylabel("η")
    ax.set_title(f"各信道呼吸能量比 η  (均值={np.mean(eta_plot):.3f}, "
                 f"≥0.10: {(eta_plot>=0.1).sum()}/{(~np.isnan(eta_plot)).sum()})")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25, axis="y")

    # ── [1,0] PC1/PC2/… 方差占比 ──
    ax = axes[1, 0]
    n_show = min(20, len(info_real["explained_variance_ratio"]))
    x_pc = np.arange(1, n_show + 1)
    w = 0.35
    ax.bar(x_pc - w/2, info_real["explained_variance_ratio"][:n_show],
           w, color="#5A9BD5", alpha=0.85, label="实 PCA (幅值)")
    if info_complex["explained_variance_ratio"]:
        ax.bar(x_pc + w/2, info_complex["explained_variance_ratio"][:n_show],
               w, color="#ED7D31", alpha=0.85, label="复 PCA (幅值+相位)")
    ax.set_xlabel("主成分序号")
    ax.set_ylabel("方差占比")
    ax.set_title("PCA 各主成分方差占比 (前 20)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25, axis="y")
    ax.set_xticks(x_pc[::2])

    # ── [1,1] 高 η 信道 vs PC1 ──
    ax = axes[1, 1]
    top_idx = np.argsort(-eta_plot)[:3]
    for i, tidx in enumerate(top_idx):
        col = X_real_valid[:, tidx]
        ax.plot(time_axis, col / np.std(col),
                color=["#BDC3C7", "#95A5A6", "#7F8C8D"][i],
                alpha=0.5, lw=0.8,
                label=f"Tone {valid_real[tidx]} (η={eta_plot[tidx]:.3f})")
    ax.plot(time_axis, wf_real / np.std(wf_real),
            color="#D62728", lw=2.0,
            label=f"PC1 实 PCA (BPM≈{bpm_real:.1f})")
    ax.set_xlabel("时间 (s)")
    ax.set_ylabel("标准化信号")
    ax.set_title("高 η 单信道 vs PCA 提取的 PC1 呼吸波形")
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, alpha=0.25)

    # ── [2,0] PC1 频谱对比 ──
    ax = axes[2, 0]
    lo, hi = int(np.searchsorted(freqs_r, 0.04)), int(np.searchsorted(freqs_r, 0.55))
    nr = power_r[lo:hi] / (np.max(power_r[lo:hi]) + 1e-12)
    nc = power_c[lo:hi] / (np.max(power_c[lo:hi]) + 1e-12)
    ax.plot(freqs_r[lo:hi] * 60, nr, color="#5A9BD5", lw=1.5,
            label="实 PCA (幅值)")
    ax.plot(freqs_c[lo:hi] * 60, nc, color="#ED7D31", lw=1.5,
            label="复 PCA (幅值+相位)")
    for bpm_v, clr, lbl in [
        (bpm_real, "#2E6F9E", f"实 PCA 峰值 {bpm_real:.1f} BPM"),
        (bpm_complex, "#C44E52", f"复 PCA 峰值 {bpm_complex:.1f} BPM"),
    ]:
        if np.isfinite(bpm_v):
            ax.axvline(bpm_v, color=clr, ls="--", lw=1.3, alpha=0.7, label=lbl)
    ax.axvspan(6, 21, color="green", alpha=0.05)
    ax.text(7, 0.96, "呼吸频带 6–21 BPM", fontsize=8, va="top", color="green", alpha=0.6)
    ax.set_xlabel("BPM")
    ax.set_ylabel("归一化功率")
    ax.set_title("PC1 频谱对比 (Hanning FFT)")
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, alpha=0.25)
    ax.set_xlim(0, 45)

    # ── [2,1] 实 vs 复 PCA 波形 ──
    ax = axes[2, 1]
    ax.plot(time_axis, wf_real / np.std(wf_real),
            color="#5A9BD5", lw=1.5, alpha=0.85, label="实 PCA PC1")
    ax.plot(time_axis, wf_complex / np.std(wf_complex),
            color="#ED7D31", lw=1.5, alpha=0.85, label="复 PCA PC1 (Re)")
    ax.set_xlabel("时间 (s)")
    ax.set_ylabel("标准化波形")
    ax.set_title(f"实 PCA vs 复 PCA 波形  (Pearson r={corr_wf:.3f})")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)

    plt.tight_layout()

    # 保存到项目 outputs/figures/
    _script = Path(__file__).resolve()
    _proj = _script
    for _p in [_script, *_script.parents]:
        if (_p / "outputs").is_dir():
            _proj = _p
            break
    output_dir = _proj / "outputs" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_png = output_dir / "pca_demo.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"\n  ✓ 图表已保存: {out_png}")

    # ── 终端总结 ─────────────────────────────────────────────
    print(f"\n{'═' * 72}")
    print(f"  演示总结")
    print(f"{'═' * 72}")
    print(f"  实 PCA  (amplitudes):")
    print(f"    PC1 方差占比  {info_real['pc1_variance_ratio']:.4f}")
    print(f"    估计 BPM       {bpm_real:.1f}" if np.isfinite(bpm_real) else "    估计 BPM       —")
    print(f"  复 PCA  (A·e^(jφ)):")
    print(f"    PC1 方差占比  {info_complex['pc1_variance_ratio']:.4f}")
    print(f"    估计 BPM       {bpm_complex:.1f}" if np.isfinite(bpm_complex) else "    估计 BPM       —")
    print(f"  两波形相关       {corr_wf:.4f}")
    print(f"{'═' * 72}")

    plt.show()

    return {
        "wf_real": wf_real,
        "wf_complex": wf_complex,
        "info_real": info_real,
        "info_complex": info_complex,
        "bpm_real": bpm_real,
        "bpm_complex": bpm_complex,
    }


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    # 自动定位项目根目录下的 sampleData/
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir
    for p in [script_dir, *script_dir.parents]:
        if (p / "sampleData").is_dir():
            project_root = p
            break

    default_file = project_root / "sampleData" / "CS_frames_all_20260113_091339.jsonl"

    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    elif default_file.exists():
        data_path = str(default_file)
        print(f"▸ 使用默认数据: {Path(data_path).name}\n")
    else:
        print("用法:  python pca_demo.py [CS_frames_*.jsonl]")
        print(f"\n默认路径不存在: {default_file}")
        sd = project_root / "sampleData"
        if sd.is_dir():
            print("\n可用的 CS 数据文件:")
            for f in sorted(sd.glob("CS_frames_*.jsonl")):
                print(f"  {f.name}")
        sys.exit(1)

    run_demo(data_path)
