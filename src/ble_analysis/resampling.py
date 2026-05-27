"""Resampling helpers for irregular BLE time series."""

import numpy as np


def resample_to_uniform_grid(time_sec, values, target_fs=None, method="linear"):
    """
    Resample an irregular time series to a uniform time grid.
    """
    time_sec = np.asarray(time_sec, dtype=float)
    values = np.asarray(values, dtype=float)

    if len(time_sec) < 2 or len(values) < 2:
        return {
            "time_sec": np.array([]),
            "values": np.array([]),
            "target_fs": target_fs,
        }

    if method != "linear":
        raise ValueError(f"Unsupported resampling method: {method}")

    if target_fs is None:
        mean_dt = float(np.mean(np.diff(time_sec)))
        target_fs = 1.0 / mean_dt if mean_dt > 0 else 1.0

    dt = 1.0 / target_fs
    uniform_time = np.arange(time_sec[0], time_sec[-1] + dt / 2, dt)
    resampled_values = np.interp(uniform_time, time_sec, values)

    return {
        "time_sec": uniform_time,
        "values": resampled_values,
        "target_fs": float(target_fs),
    }
