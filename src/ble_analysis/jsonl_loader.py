"""JSONL BLE CS frame loader for metal_verify / position-sweep recordings.

Supports the 2026-08 metal_verify schema where channels are keyed by tone
index and fields use ``local_amp`` / ``remote_amp`` / ``phase`` / ``I`` / ``Q``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

PathLike = Union[str, Path]

VARIABLES = ("remote_amplitudes", "local_amplitudes", "phases")

# JSONL channel field → project variable name
_FIELD_BY_VARIABLE = {
    "remote_amplitudes": "remote_amp",
    "local_amplitudes": "local_amp",
    "phases": "phase",  # composite phase = ∠(I+jQ) = wrap(local_phase+remote_phase)
}


def load_jsonl_frames(filepath: PathLike) -> List[dict]:
    """Load channel_sounding frame records from a JSONL file (skip meta)."""
    path = Path(filepath)
    frames: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("record_type") == "frame" and d.get("frame_type") == "channel_sounding":
                frames.append(d)
    return frames


def estimate_fs_from_frames(
    frames: Sequence[dict],
    *,
    time_key: str = "t_dev_ms",
) -> float:
    """Estimate sampling rate from median inter-frame interval (Hz)."""
    if len(frames) < 2:
        return 2.0
    if time_key == "t_dev_ms":
        t = np.asarray([float(fr.get("t_dev_ms", np.nan)) for fr in frames], dtype=float)
        t = t[np.isfinite(t)]
        if len(t) < 2:
            return 2.0
        dt_sec = np.diff(t) / 1000.0
    else:
        t = np.asarray([float(fr.get("t_host_utc_ns", np.nan)) for fr in frames], dtype=float)
        t = t[np.isfinite(t)]
        if len(t) < 2:
            return 2.0
        dt_sec = np.diff(t) / 1e9
    dt_sec = dt_sec[dt_sec > 0]
    if len(dt_sec) == 0:
        return 2.0
    med = float(np.median(dt_sec))
    return 1.0 / med if med > 0 else 2.0


def frame_time_sec(frames: Sequence[dict], *, time_key: str = "t_dev_ms") -> np.ndarray:
    """Return absolute time in seconds for each frame (relative origin preserved)."""
    if time_key == "t_dev_ms":
        t = np.asarray([float(fr.get("t_dev_ms", np.nan)) for fr in frames], dtype=float)
        return t / 1000.0
    t = np.asarray([float(fr.get("t_host_utc_ns", np.nan)) for fr in frames], dtype=float)
    return t / 1e9


def filter_frames_by_seq(
    frames: Sequence[dict],
    seq_start: int,
    seq_end: int,
    *,
    inclusive: bool = True,
) -> List[dict]:
    """Keep frames whose ``seq`` lies in ``[seq_start, seq_end]`` (inclusive)."""
    out: List[dict] = []
    for fr in frames:
        seq = int(fr.get("seq", -1))
        if inclusive:
            if seq_start <= seq <= seq_end:
                out.append(fr)
        else:
            if seq_start <= seq < seq_end:
                out.append(fr)
    return out


def list_channel_keys(frames: Sequence[dict]) -> List[int]:
    """Return sorted numeric channel keys from the first non-empty frame."""
    for fr in frames:
        ch = fr.get("channels") or {}
        if ch:
            keys = []
            for k in ch.keys():
                try:
                    keys.append(int(k))
                except (TypeError, ValueError):
                    continue
            return sorted(keys)
    return list(range(72))


def extract_variable_matrix(
    frames: Sequence[dict],
    variable: str,
    *,
    channel_keys: Optional[Sequence[int]] = None,
    unwrap_phases: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract ``(n_channels, n_frames)`` matrix for one variable.

    Returns
    -------
    values : ndarray, shape (n_ch, n_frames)
    time_sec : ndarray, shape (n_frames,)
    seqs : ndarray, shape (n_frames,)
    """
    if variable not in _FIELD_BY_VARIABLE:
        raise ValueError(f"Unsupported variable: {variable}")
    field = _FIELD_BY_VARIABLE[variable]
    if not frames:
        return (
            np.zeros((0, 0), dtype=float),
            np.zeros(0, dtype=float),
            np.zeros(0, dtype=int),
        )

    keys = list(channel_keys) if channel_keys is not None else list_channel_keys(frames)
    n_ch = len(keys)
    n_fr = len(frames)
    values = np.full((n_ch, n_fr), np.nan, dtype=float)
    time_sec = frame_time_sec(frames)
    seqs = np.asarray([int(fr.get("seq", -1)) for fr in frames], dtype=int)

    for j, fr in enumerate(frames):
        ch_map = fr.get("channels") or {}
        for i, ck in enumerate(keys):
            # JSONL keys may be str or int
            ch = ch_map.get(ck)
            if ch is None:
                ch = ch_map.get(str(ck))
            if ch is None:
                continue
            if variable == "phases":
                # Prefer composite phase; fall back to ∠(I+jQ)
                if "phase" in ch and ch["phase"] is not None:
                    values[i, j] = float(ch["phase"])
                elif "I" in ch and "Q" in ch:
                    values[i, j] = float(np.angle(complex(float(ch["I"]), float(ch["Q"]))))
            else:
                if field in ch and ch[field] is not None:
                    values[i, j] = float(ch[field])

    if variable == "phases" and unwrap_phases and n_fr >= 2:
        for i in range(n_ch):
            row = values[i]
            mask = np.isfinite(row)
            if np.sum(mask) >= 2:
                unwrapped = row.copy()
                unwrapped[mask] = np.unwrap(row[mask])
                values[i] = unwrapped

    return values, time_sec, seqs


def extract_multivar_cube(
    frames: Sequence[dict],
    variables: Sequence[str] = VARIABLES,
    *,
    channel_keys: Optional[Sequence[int]] = None,
) -> Dict[str, np.ndarray]:
    """Extract all requested variables; also returns ``time_sec`` and ``seqs``."""
    keys = list(channel_keys) if channel_keys is not None else list_channel_keys(frames)
    out: Dict[str, np.ndarray] = {}
    time_sec = None
    seqs = None
    for var in variables:
        mat, t, s = extract_variable_matrix(
            frames, var, channel_keys=keys, unwrap_phases=(var == "phases")
        )
        out[var] = mat
        time_sec = t
        seqs = s
    out["time_sec"] = time_sec if time_sec is not None else np.zeros(0)
    out["seqs"] = seqs if seqs is not None else np.zeros(0, dtype=int)
    out["channel_keys"] = np.asarray(keys, dtype=int)
    return out


def segment_frames_by_ranges(
    frames: Sequence[dict],
    ranges: Dict[str, Tuple[int, int]],
) -> Dict[str, List[dict]]:
    """Split frames by named inclusive seq ranges."""
    return {
        name: filter_frames_by_seq(frames, int(a), int(b))
        for name, (a, b) in ranges.items()
    }
