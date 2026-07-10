"""HKH 呼吸带 JSONL 数据加载与采样率估计。"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from data_saver import DataSaver


def load_hkh_frames(filepath, verbose: bool = True):
    """加载 HKH 呼吸带 JSONL 帧数据。

    Returns
    -------
    data : dict or None
    frames : list
        每帧含 ``index``, ``seq``, ``timestamp_ms``, ``t_host_utc_ns``, ``amp``。
    """
    filepath = str(filepath)
    path = Path(filepath)
    if not path.is_file():
        if verbose:
            print(f"⚠️  文件不存在: {filepath}")
        return None, []

    if verbose:
        print(f"✓ 加载 HKH: {filepath} ({path.stat().st_size / 1024 / 1024:.2f} MB)")

    saver = DataSaver()
    data = saver.load_frames(filepath)
    if data is None:
        if verbose:
            print("✗ HKH 加载失败")
        return None, []

    frames = data.get("frames", [])
    if verbose:
        print(f"✓ HKH 共 {len(frames)} 帧")
    return data, frames


def extract_hkh_amplitudes(frames) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """从 HKH 帧列表提取 seq、绝对时间（ns）、幅值。"""
    seq = np.array([f.get("index", f.get("seq", i)) for i, f in enumerate(frames)], dtype=int)
    t_host = np.array(
        [f.get("t_host_utc_ns", 0) for f in frames],
        dtype=np.int64,
    )
    amp = np.array([f.get("amp", np.nan) for f in frames], dtype=float)
    return seq, t_host, amp


def estimate_fs_from_host_timestamps(
    t_host_utc_ns: np.ndarray,
    *,
    min_positive_ms: float = 1.0,
) -> float:
    """用 ``t_host_utc_ns`` 正差分估计平均采样率（Hz）。

    适用于 HKH seq≥21125 之后 UTC 时间正常的区段。
    """
    t = np.asarray(t_host_utc_ns, dtype=np.int64)
    if len(t) < 2:
        return float("nan")
    diffs_ms = np.diff(t) / 1e6
    pos = diffs_ms[diffs_ms >= min_positive_ms]
    if len(pos) == 0:
        return float("nan")
    return float(1000.0 / np.mean(pos))


def estimate_fs_from_dev_timestamps(
    timestamp_ms: np.ndarray,
    *,
    min_positive_ms: float = 1.0,
) -> float:
    """用 ``t_dev_ms`` 差分估计采样率（Hz）。"""
    t = np.asarray(timestamp_ms, dtype=float)
    if len(t) < 2:
        return float("nan")
    diffs = np.diff(t)
    pos = diffs[diffs >= min_positive_ms]
    if len(pos) == 0:
        return float("nan")
    return float(1000.0 / np.mean(pos))
