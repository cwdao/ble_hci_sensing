"""波形对比指标：z-score、符号对齐、窗级 RMSE。"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def zscore(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    std = float(np.std(x))
    if std < eps:
        return x - float(np.mean(x))
    return (x - float(np.mean(x))) / std


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(len(a), len(b))
    if n < 2:
        return float("nan")
    d = a[:n] - b[:n]
    return float(np.sqrt(np.mean(d * d)))


def rmse_with_sign_alignment(a: np.ndarray, b: np.ndarray) -> Tuple[float, int]:
    """z-score 后比较，自动选择是否翻转 b 的符号。返回 (rmse, sign)。"""
    za = zscore(a)
    zb = zscore(b)
    r_pos = rmse(za, zb)
    r_neg = rmse(za, -zb)
    if r_neg < r_pos:
        return r_neg, -1
    return r_pos, 1


def resample_to_length(y: np.ndarray, target_len: int) -> np.ndarray:
    """线性插值到目标长度（用于不同采样率窗内对齐）。"""
    y = np.asarray(y, dtype=float)
    if target_len <= 0:
        return np.array([], dtype=float)
    if len(y) == target_len:
        return y.copy()
    if len(y) < 2:
        return np.full(target_len, y[0] if len(y) else np.nan)
    x_old = np.linspace(0.0, 1.0, len(y))
    x_new = np.linspace(0.0, 1.0, target_len)
    return np.interp(x_new, x_old, y)


def window_rmse_against_reference(
    est_waveform: np.ndarray,
    ref_waveform: np.ndarray,
    *,
    resample_to: str = "ref",
) -> Tuple[float, int]:
    """单窗 RMSE（带符号对齐）。

    Parameters
    ----------
    resample_to : ``"ref"`` | ``"est"`` | ``"longer"``
        插值对齐长度策略。
    """
    est = np.asarray(est_waveform, dtype=float)
    ref = np.asarray(ref_waveform, dtype=float)
    if len(est) < 2 or len(ref) < 2:
        return float("nan"), 1

    if resample_to == "ref":
        est = resample_to_length(est, len(ref))
    elif resample_to == "est":
        ref = resample_to_length(ref, len(est))
    else:
        n = max(len(est), len(ref))
        est = resample_to_length(est, n)
        ref = resample_to_length(ref, n)

    return rmse_with_sign_alignment(est, ref)
