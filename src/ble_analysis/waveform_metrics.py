"""波形对比指标：z-score、符号对齐、窗级/录制级 RMSE。"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

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


def stitch_overlapping_windows(
    windows: Sequence[np.ndarray],
    starts: Sequence[int],
    total_len: int,
) -> np.ndarray:
    """Overlap-average stitch of window waveforms onto a common timeline."""
    if total_len <= 0 or not windows:
        return np.asarray([], dtype=float)
    acc = np.zeros(total_len, dtype=float)
    wgt = np.zeros(total_len, dtype=float)
    for y, st in zip(windows, starts):
        yy = np.asarray(y, dtype=float)
        if yy.size < 2 or not np.any(np.isfinite(yy)):
            continue
        st_i = int(st)
        end_i = min(st_i + len(yy), total_len)
        if end_i <= st_i:
            continue
        sl = slice(st_i, end_i)
        n = end_i - st_i
        chunk = yy[:n]
        finite = np.isfinite(chunk)
        acc[sl] = np.where(finite, acc[sl] + np.where(finite, chunk, 0.0), acc[sl])
        wgt[sl] = np.where(finite, wgt[sl] + 1.0, wgt[sl])
    out = np.full(total_len, np.nan, dtype=float)
    mask = wgt > 0
    out[mask] = acc[mask] / wgt[mask]
    return out


def recording_level_rmse(
    est: np.ndarray,
    ref: np.ndarray,
    *,
    max_lag: int = 0,
) -> Dict[str, float]:
    """Recording-level RMSE with one global polarity and optional lag search.

    Protocol (unified_pipeline_final_plan):
      - z-score on the full recording (not per-window)
      - single global polarity flip
      - optional fixed lag (samples) searched once over ±max_lag
      - no per-window GT-driven re-alignment
    """
    a = np.asarray(est, dtype=float)
    b = np.asarray(ref, dtype=float)
    n = min(len(a), len(b))
    if n < 8:
        return {"rmse": float("nan"), "sign": 1.0, "lag": 0.0, "n": float(n)}
    a = a[:n].copy()
    b = b[:n].copy()
    valid = np.isfinite(a) & np.isfinite(b)
    if int(np.sum(valid)) < 8:
        return {
            "rmse": float("nan"),
            "sign": 1.0,
            "lag": 0.0,
            "n": float(np.sum(valid)),
        }

    # Dense fill for lag search: replace invalid with local mean of valid
    fill_a = float(np.nanmean(a[valid]))
    fill_b = float(np.nanmean(b[valid]))
    a_f = np.where(valid, a, fill_a)
    b_f = np.where(valid, b, fill_b)
    za_full = zscore(a_f)
    zb_full = zscore(b_f)

    best = {"rmse": float("inf"), "sign": 1.0, "lag": 0.0}
    lags = range(-int(max_lag), int(max_lag) + 1) if max_lag > 0 else [0]
    for lag in lags:
        for sign in (1.0, -1.0):
            if lag == 0:
                ea = za_full
                rb = sign * zb_full
            elif lag > 0:
                ea = za_full[lag:]
                rb = sign * zb_full[:-lag]
            else:
                ea = za_full[:lag]
                rb = sign * zb_full[-lag:]
            m = min(len(ea), len(rb))
            if m < 8:
                continue
            r = rmse(ea[:m], rb[:m])
            if np.isfinite(r) and r < best["rmse"]:
                best = {"rmse": float(r), "sign": float(sign), "lag": float(lag)}
    if not np.isfinite(best["rmse"]) or best["rmse"] == float("inf"):
        best["rmse"] = float("nan")
    best["n"] = float(n)
    return best
