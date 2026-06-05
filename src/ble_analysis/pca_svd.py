"""PCA / SVD 多信道呼吸波形提取。

从多个信道（72 道 BLE CS tone）的滤波信号中，利用 PCA 或 SVD
提取所有信道的共同变化模式（第一主成分 / 第一左奇异向量），作为呼吸波形。

参考
----
WiFi CSI 呼吸感知文献中 PCA/SVD 是标准的降噪+信号提取手段。
详见 ``docs/chFusion_pca_svd_plan.md``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# 类型定义
# ---------------------------------------------------------------------------

PcaSvdMethod = Literal["pca", "svd_real", "svd_complex"]
"""PCA: 实矩阵特征分解; SVD_real: 实矩阵 SVD; SVD_complex: 复矩阵 SVD"""

NormalizeMethod = Literal["none", "zscore", "minmax"]
"""标准化策略:
- none:   不标准化（注意：幅值大的信道会主导结果）
- zscore: 按列 (x - μ) / σ（推荐，消除信道间幅值差异）
- minmax: 按列 (x - min) / (max - min)
"""

PcaSvdVariable = Literal[
    "amplitudes",
    "remote_amplitudes",
    "local_amplitudes",
    "phases",
    "complex",
    "stacked",
]
"""变量标识:
- amplitudes / remote_amplitudes / local_amplitudes: 对应 CS_SIGNAL_VARIABLES
- phases: 总相位
- complex: 总幅值 + j·总相位 复矩阵 SVD
- stacked: 三种幅值堆叠
"""


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


@dataclass
class PcaSvdConfig:
    """PCA / SVD 波形提取配置。

    Parameters
    ----------
    method : PcaSvdMethod
        ``pca``: 实矩阵 PCA（协方差特征分解）。
        ``svd_real``: 实矩阵 SVD。
        ``svd_complex``: 复矩阵 SVD（仅对 complex 变量有效）。
    normalize : NormalizeMethod
        每列（信道）标准化策略，默认 ``zscore``。
    min_channels : int
        最小有效信道数，低于此数跳过。
    min_variance_ratio : float
        PC1 方差占比阈值，低于此值发出警告（呼吸可能不主导）。
    eps : float
        数值稳定小量。
    """

    method: PcaSvdMethod = "pca"
    normalize: NormalizeMethod = "zscore"
    min_channels: int = 4
    min_variance_ratio: float = 0.10
    eps: float = 1e-12


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _normalize_matrix(
    X: np.ndarray,
    method: NormalizeMethod,
    eps: float = 1e-12,
) -> np.ndarray:
    """按列标准化 M×N 矩阵。

    Parameters
    ----------
    X : ndarray, shape (M, N)
    method : NormalizeMethod
    eps : float

    Returns
    -------
    ndarray, shape (M, N)
    """
    if method == "none":
        return X.astype(float)
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


def _check_and_warn(
    X: np.ndarray,
    cfg: PcaSvdConfig,
    seg_name: str,
) -> bool:
    """检查数据矩阵的有效性，无效或信道不足返回 False 并打印警告。"""
    if X is None or X.size == 0 or X.shape[1] < cfg.min_channels:
        print(
            f"  ⚠ [{seg_name}] 信道数={X.shape[1] if X is not None else 0} < "
            f"{cfg.min_channels}，跳过 PCA/SVD"
        )
        return False
    if not np.all(np.isfinite(X)):
        print(f"  ⚠ [{seg_name}] 数据含 NaN/inf，跳过")
        return False
    return True


# ---------------------------------------------------------------------------
# 实矩阵 PCA
# ---------------------------------------------------------------------------


def extract_breath_waveform_pca(
    X: np.ndarray,
    cfg: Optional[PcaSvdConfig] = None,
    seg_name: str = "",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """从 M×N 实矩阵提取呼吸波形（PC1）。

    Parameters
    ----------
    X : ndarray, shape (M, N)
        每列是一个信道的带通滤波信号（M 帧, N 信道）。
    cfg : PcaSvdConfig, optional
    seg_name : str
        段名（用于警告信息）。

    Returns
    -------
    waveform : ndarray, shape (M,)
        PC1 时间序列（呼吸波形）。
    info : dict
        ``explained_variance_ratio``: 各主成分方差占比。
        ``pc1_variance_ratio``: PC1 方差占比。
        ``warn``: 警告信息列表。
    """
    cfg = cfg or PcaSvdConfig()
    info: Dict[str, Any] = {
        "explained_variance_ratio": [],
        "pc1_variance_ratio": np.nan,
        "warn": [],
    }
    if not _check_and_warn(X, cfg, seg_name):
        return np.full(X.shape[0], np.nan), info

    M, N = X.shape
    Z = _normalize_matrix(X, cfg.normalize, cfg.eps)

    # 协方差矩阵 N×N（N=72 << M，特征分解高效）
    C = (Z.T @ Z) / max(M - 1, 1)
    eigenvalues, eigenvectors = np.linalg.eigh(C)  # 自动升序返回
    eigenvalues = eigenvalues[::-1]
    eigenvectors = eigenvectors[:, ::-1]  # 降序排列

    # 方差占比
    total_var = float(np.sum(eigenvalues))
    if total_var > cfg.eps:
        ratios = eigenvalues / total_var
    else:
        ratios = np.zeros_like(eigenvalues)
        ratios[0] = 1.0 if N > 0 else 0.0
    info["explained_variance_ratio"] = ratios.tolist()
    info["pc1_variance_ratio"] = float(ratios[0]) if len(ratios) > 0 else np.nan

    if info["pc1_variance_ratio"] < cfg.min_variance_ratio:
        w = (
            f"[{seg_name}] PC1 方差占比={info['pc1_variance_ratio']:.3f} < "
            f"{cfg.min_variance_ratio}，呼吸信号可能不占主导"
        )
        print(f"  ⚠ {w}")
        info["warn"].append(w)

    pc1 = Z @ eigenvectors[:, 0]  # shape (M,)
    return pc1, info


def pca_explained_variance(X: np.ndarray) -> np.ndarray:
    """返回 PCA 各主成分方差占比（不提取波形）。

    Parameters
    ----------
    X : ndarray, shape (M, N)

    Returns
    -------
    ratios : ndarray, shape (N,)
    """
    M, N = X.shape
    if N < 2:
        return np.array([1.0] if N == 1 else [])
    Z = _normalize_matrix(X, "zscore")
    C = (Z.T @ Z) / max(M - 1, 1)
    eigenvalues = np.linalg.eigvalsh(C)  # 升序
    total = float(np.sum(eigenvalues))
    if total <= 1e-12:
        return np.ones(N) / N
    return (eigenvalues[::-1] / total)  # 降序


# ---------------------------------------------------------------------------
# 实矩阵 SVD
# ---------------------------------------------------------------------------


def extract_breath_waveform_svd(
    X: np.ndarray,
    cfg: Optional[PcaSvdConfig] = None,
    seg_name: str = "",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """从 M×N 实矩阵提取呼吸波形（第一左奇异向量）。

    Parameters
    ----------
    X : ndarray, shape (M, N)
    cfg : PcaSvdConfig, optional
    seg_name : str

    Returns
    -------
    waveform : ndarray, shape (M,)
    info : dict
    """
    cfg = cfg or PcaSvdConfig(method="svd_real")
    info: Dict[str, Any] = {
        "explained_variance_ratio": [],
        "pc1_variance_ratio": np.nan,
        "warn": [],
    }
    if not _check_and_warn(X, cfg, seg_name):
        return np.full(X.shape[0], np.nan), info

    Z = _normalize_matrix(X, cfg.normalize, cfg.eps)
    # 紧凑 SVD: Z = U @ diag(s) @ V^T
    U, s, Vt = np.linalg.svd(Z, full_matrices=False)
    s = np.asarray(s, dtype=float)

    # 奇异值平方 → 方差占比
    s2 = s**2
    total_s2 = float(np.sum(s2))
    if total_s2 > cfg.eps:
        ratios = s2 / total_s2
    else:
        ratios = np.ones(len(s)) / max(len(s), 1)
    info["explained_variance_ratio"] = ratios.tolist()
    info["pc1_variance_ratio"] = float(ratios[0]) if len(ratios) > 0 else np.nan

    if info["pc1_variance_ratio"] < cfg.min_variance_ratio:
        w = (
            f"[{seg_name}] SVD u_1 方差占比={info['pc1_variance_ratio']:.3f} < "
            f"{cfg.min_variance_ratio}"
        )
        print(f"  ⚠ {w}")
        info["warn"].append(w)

    u1 = U[:, 0]  # shape (M,)
    return u1, info


# ---------------------------------------------------------------------------
# 复矩阵 SVD
# ---------------------------------------------------------------------------


def extract_breath_waveform_complex_svd(
    X_complex: np.ndarray,
    cfg: Optional[PcaSvdConfig] = None,
    seg_name: str = "",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """从 M×N 复矩阵提取呼吸波形（第一左奇异向量的幅值）。

    ``X_complex[i, j] = A_ij · exp(j · φ_ij)``，典型构造方式为
    每信道 j: ``amplitudes_j · exp(j · phases_j)``。

    Parameters
    ----------
    X_complex : ndarray, shape (M, N), dtype complex
    cfg : PcaSvdConfig, optional
        method 会被隐式覆写为 ``svd_complex``。
    seg_name : str

    Returns
    -------
    waveform : ndarray, shape (M,)
        |u1|，实数呼吸波形。
    info : dict
    """
    cfg = cfg or PcaSvdConfig(method="svd_complex")
    cfg.method = "svd_complex"
    info: Dict[str, Any] = {
        "explained_variance_ratio": [],
        "pc1_variance_ratio": np.nan,
        "warn": [],
    }
    if not _check_and_warn(np.abs(X_complex), cfg, seg_name):
        return np.full(X_complex.shape[0], np.nan), info

    # 复矩阵：每列中心化（去复均值），不做 zscore（幅值相位联合不宜过度缩放）
    Z = X_complex.astype(complex)
    Z = Z - np.mean(Z, axis=0, keepdims=True)

    # numpy 原生支持复 SVD: Z = U @ diag(s) @ V^H
    U, s, Vh = np.linalg.svd(Z, full_matrices=False)
    s = np.asarray(s, dtype=float)

    s2 = s**2
    total_s2 = float(np.sum(s2))
    if total_s2 > cfg.eps:
        ratios = s2 / total_s2
    else:
        ratios = np.ones(len(s)) / max(len(s), 1)
    info["explained_variance_ratio"] = ratios.tolist()
    info["pc1_variance_ratio"] = float(ratios[0]) if len(ratios) > 0 else np.nan

    if info["pc1_variance_ratio"] < cfg.min_variance_ratio:
        w = (
            f"[{seg_name}] 复SVD u_1 方差占比={info['pc1_variance_ratio']:.3f} < "
            f"{cfg.min_variance_ratio}"
        )
        print(f"  ⚠ {w}")
        info["warn"].append(w)

    u1 = U[:, 0]  # shape (M,), complex
    waveform = np.abs(u1)  # 取幅值，得到实值呼吸波形
    return waveform, info


# ---------------------------------------------------------------------------
# 符号一致性
# ---------------------------------------------------------------------------


def align_waveform_sign(
    waveform: np.ndarray,
    prev_waveform: Optional[np.ndarray] = None,
    reference_channel: Optional[np.ndarray] = None,
) -> np.ndarray:
    """对齐呼吸波形符号，避免相邻窗口间因 SVD/PCA 符号任意性导致的翻转。

    优先级:
    1. 与上一窗口波形做相关，若负则翻转
    2. 首个窗口：若提供 reference_channel，与其做相关决定初始符号

    Parameters
    ----------
    waveform : ndarray, shape (M,)
        当前窗口的呼吸波形。
    prev_waveform : ndarray, optional
        上一窗口的波形（长度可能不同，取共同部分做相关）。
    reference_channel : ndarray, optional
        首个窗口的参考信号（如中位信道带通波形）。

    Returns
    -------
    ndarray
        符号对齐后的波形。
    """
    wf = waveform.copy()
    if prev_waveform is not None and len(prev_waveform) > 0 and len(wf) > 0:
        # 取较短长度做相关
        L = min(len(prev_waveform), len(wf))
        corr = np.dot(prev_waveform[:L], wf[:L])
        if corr < 0:
            wf = -wf
    elif reference_channel is not None and len(reference_channel) > 0 and len(wf) > 0:
        L = min(len(reference_channel), len(wf))
        corr = np.dot(reference_channel[:L], wf[:L])
        if corr < 0:
            wf = -wf
    return wf


# ---------------------------------------------------------------------------
# 多变量数据矩阵构造
# ---------------------------------------------------------------------------


def build_multivariable_data_matrix(
    ch_maps: Dict[str, Dict[Any, Dict[str, Any]]],
    var_names: List[str],
    channels: List[Any],
    st: int,
    end: int,
) -> np.ndarray:
    """将多种变量的多信道数据构造成一个 M×N 矩阵。

    每列是某个信道某个变量的 ``bandpass_filtered[st:end]`` 切片。
    列顺序: var_1 的所有信道, var_2 的所有信道, ...。

    Parameters
    ----------
    ch_maps : dict
        key=变量名, value = ``{ch: proc}``，其中 ``proc[varname]["bandpass_filtered"]``
        是 np.ndarray。
    var_names : list[str]
        要包含的变量名列表。
    channels : list
        信道标识列表。
    st : int
        窗口起始索引。
    end : int
        窗口结束索引。

    Returns
    -------
    ndarray, shape (M, N_total)
    """
    cols: List[np.ndarray] = []
    M = end - st
    for var in var_names:
        ch_map = ch_maps.get(var, {})
        for ch in channels:
            proc = ch_map.get(ch)
            if proc is None:
                continue
            bp = proc[var].get("bandpass_filtered")
            if bp is None or len(bp) < end:
                continue
            col = bp[st:end].copy()
            if len(col) == M:
                cols.append(col)
    if not cols:
        return np.empty((M, 0))
    return np.column_stack(cols).astype(float)
