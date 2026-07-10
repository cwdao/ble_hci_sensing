"""BLE CS + HKH 呼吸带联合验证：B2 波形 RMSE 与 BPM 误差。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ble_analysis.chfusion import ChFusionConfig
from ble_analysis.coherent_mrc import _window_b2_bpms
from ble_analysis.hkh_data import load_hkh_frames
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.waveform_metrics import window_rmse_against_reference
from ble_analysis.wifi_mrc import estimate_bpm_from_waveform


def _load_preprocess_meta(meta_path: Path) -> dict:
    with meta_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _hkh_window_bandpass(
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    t_start_ns: int,
    t_end_ns: int,
) -> np.ndarray:
    mask = (hkh_t_host >= t_start_ns) & (hkh_t_host < t_end_ns)
    return hkh_bandpass[mask]


def _resolve_hkh_fs(
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    fs_hkh_override: Optional[float] = None,
) -> float:
    """Resolve HKH sampling rate from preprocess meta or len/duration."""
    if fs_hkh_override is not None:
        return float(fs_hkh_override)
    duration_s = float((hkh_t_host[-1] - hkh_t_host[0]) / 1e9)
    return float(len(hkh_bandpass) / max(duration_s, 1e-6))


def _ble_window_time_range(
    cs_t_host: np.ndarray,
    st: int,
    end: int,
    fs: float,
    win_len: int,
) -> Tuple[int, int]:
    """由 BLE 样本窗索引映射到绝对 UTC 时间范围。"""
    if len(cs_t_host) == 0:
        return 0, 0
    st = int(max(0, min(st, len(cs_t_host) - 1)))
    end = int(max(st + 1, min(end, len(cs_t_host))))
    return int(cs_t_host[st]), int(cs_t_host[end - 1])


def compute_hkh_gt_per_window(
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    cs_t_host: np.ndarray,
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    *,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    fs_hkh_override: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """Return HKH GT BPM per BLE sliding window (aligned by ``cs_t_host``).

    Returns
    -------
    bpm_hkh, bpm_ble_placeholder (nan array), fs_ble, fs_hkh
    """
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()

    ref_seg = multichannel_by_var["phases"].get(seg_name)
    if ref_seg is None:
        raise ValueError(f"Segment {seg_name} not found")

    fs_ble = ref_seg["metadata"]["sampling_rate"]
    ch_map = ref_seg["channels"]
    ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
    seg_var = ref_seg.get("variable", "phases")
    ref_len = max(len(ch_map[c][seg_var]["bandpass_filtered"]) for c in ch_list)

    win_len = int(round(mp.window_length_sec * fs_ble))
    step_len = int(round(mp.step_length_sec * fs_ble))
    starts = _sliding_window_indices(ref_len, win_len, step_len)

    fs_hkh = _resolve_hkh_fs(hkh_bandpass, hkh_t_host, fs_hkh_override)

    bpm_hkh: List[float] = []
    for st in starts:
        end = st + win_len
        t0, t1 = _ble_window_time_range(cs_t_host, st, end, fs_ble, win_len)
        hkh_win = _hkh_window_bandpass(hkh_bandpass, hkh_t_host, t0, t1 + 1)
        if len(hkh_win) < 4:
            bpm_hkh.append(float("nan"))
            continue
        bpm_gt, _, _, _ = estimate_bpm_from_waveform(hkh_win, fs_hkh, cfg=cfg)
        bpm_hkh.append(float(bpm_gt))

    return (
        np.asarray(bpm_hkh, dtype=float),
        np.full(len(starts), np.nan),
        float(fs_ble),
        float(fs_hkh),
    )


def summarize_bpm_vs_hkh(
    bpm_est: np.ndarray,
    bpm_hkh_gt: np.ndarray,
) -> dict:
    """Window-level absolute BPM error vs HKH GT."""
    valid = np.isfinite(bpm_est) & np.isfinite(bpm_hkh_gt) & (bpm_hkh_gt > 0)
    abs_err = np.where(valid, np.abs(bpm_est - bpm_hkh_gt), np.nan)
    rel_err = np.where(valid, abs_err / bpm_hkh_gt * 100.0, np.nan)
    return {
        "bpm_mean_abs_err": float(np.nanmean(abs_err)),
        "bpm_std_abs_err": float(np.nanstd(abs_err)),
        "bpm_mean_rel_err_pct": float(np.nanmean(rel_err)),
        "bpm_std_rel_err_pct": float(np.nanstd(rel_err)),
        "est_mean_bpm": float(np.nanmean(bpm_est)),
        "gt_mean_bpm": float(np.nanmean(bpm_hkh_gt)),
        "n_valid": int(np.sum(valid)),
        "n_windows": int(len(bpm_est)),
    }


def extract_bpm_per_window(row: Optional[dict], method_key: str) -> Optional[np.ndarray]:
    if row is None or method_key not in row:
        return None
    block = row[method_key]
    if isinstance(block, dict) and "bpm_per_window" in block:
        return np.asarray(block["bpm_per_window"], dtype=float)
    return None


def validate_b2_against_hkh(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    cs_t_host: np.ndarray,
    *,
    method_key: str = "b2_d_two_level",
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    pca_top_k: int = 36,
    min_coherence: float = 0.2,
    verbose: bool = False,
    fs_hkh_override: Optional[float] = None,
) -> Optional[dict]:
    """单段 B2 vs HKH：窗级 BPM 误差 + 窗级 RMSE。"""
    from ble_analysis.coherent_mrc import estimate_b2_segment  # noqa: F401 — method configs

    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()

    method_configs: Dict[str, dict] = {
        "b2_a0_pca_sign": {
            "phase_method": "pca_sign",
            "weight_mode": "eta_rho",
            "use_two_level": False,
            "use_modal_phase_align": False,
            "f0_from_b1": False,
            "min_coherence": 0.0,
        },
        "b2_a1_corr_sign": {
            "phase_method": "corr_sign",
            "weight_mode": "eta_rho",
            "use_two_level": False,
            "use_modal_phase_align": False,
            "f0_from_b1": False,
            "min_coherence": 0.0,
        },
        "b2_b_hilbert": {
            "phase_method": "hilbert",
            "weight_mode": "eta_rho",
            "use_two_level": False,
            "use_modal_phase_align": False,
            "f0_from_b1": False,
            "min_coherence": 0.0,
        },
        "b2_d_two_level": {
            "phase_method": "hilbert",
            "weight_mode": "coherence_gated",
            "use_two_level": True,
            "use_modal_phase_align": True,
            "modal_weight_mode": "eta_coherence",
            "f0_from_b1": False,
            "min_coherence": min_coherence,
        },
    }
    if method_key not in method_configs:
        raise ValueError(f"Unsupported method for HKH validation: {method_key}")
    mc = method_configs[method_key]

    ref_seg = multichannel_by_var["phases"].get(seg_name)
    if ref_seg is None:
        return None

    fs = ref_seg["metadata"]["sampling_rate"]
    ch_map = ref_seg["channels"]
    ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
    seg_var = ref_seg.get("variable", "phases")
    ref_len = max(len(ch_map[c][seg_var]["bandpass_filtered"]) for c in ch_list)

    win_len = int(round(mp.window_length_sec * fs))
    step_len = int(round(mp.step_length_sec * fs))
    if ref_len < win_len:
        return None

    starts = _sliding_window_indices(ref_len, win_len, step_len)
    fs_hkh = _resolve_hkh_fs(hkh_bandpass, hkh_t_host, fs_hkh_override)

    bpm_ble: List[float] = []
    bpm_hkh: List[float] = []
    rmse_list: List[float] = []

    for st in starts:
        end = st + win_len
        bpm_est, _diag, y_final = _window_b2_bpms(
            multichannel_by_var,
            seg_name,
            ch_list,
            st,
            end,
            fs,
            cfg,
            phase_method=mc["phase_method"],
            weight_mode=mc["weight_mode"],
            modal_weight_mode=mc.get("modal_weight_mode", "equal"),
            use_two_level=mc["use_two_level"],
            use_modal_phase_align=mc["use_modal_phase_align"],
            f0=None,
            min_coherence=mc.get("min_coherence", 0.0),
            pca_top_k=pca_top_k,
            return_waveform=True,
        )
        bpm_ble.append(float(bpm_est))

        t0, t1 = _ble_window_time_range(cs_t_host, st, end, fs, win_len)
        hkh_win = _hkh_window_bandpass(hkh_bandpass, hkh_t_host, t0, t1 + 1)
        if len(hkh_win) < 4:
            bpm_hkh.append(float("nan"))
            rmse_list.append(float("nan"))
            continue

        bpm_gt, _, _, _ = estimate_bpm_from_waveform(hkh_win, fs_hkh, cfg=cfg)
        bpm_hkh.append(float(bpm_gt))

        rmse_val, _sign = window_rmse_against_reference(y_final, hkh_win)
        rmse_list.append(float(rmse_val))

    bpm_ble_arr = np.asarray(bpm_ble, dtype=float)
    bpm_hkh_arr = np.asarray(bpm_hkh, dtype=float)
    rmse_arr = np.asarray(rmse_list, dtype=float)

    valid_bpm = np.isfinite(bpm_ble_arr) & np.isfinite(bpm_hkh_arr) & (bpm_hkh_arr > 0)
    abs_err = np.where(
        valid_bpm,
        np.abs(bpm_ble_arr - bpm_hkh_arr),
        np.nan,
    )
    rel_err = np.where(
        valid_bpm,
        abs_err / bpm_hkh_arr * 100.0,
        np.nan,
    )

    valid_rmse = np.isfinite(rmse_arr)
    result = {
        "segment": seg_name,
        "method": method_key,
        "n_windows": len(starts),
        "fs_ble": fs,
        "fs_hkh": fs_hkh,
        "bpm_ble": bpm_ble_arr,
        "bpm_hkh_gt": bpm_hkh_arr,
        "bpm_abs_err": abs_err,
        "bpm_rel_err_pct": rel_err,
        "rmse": rmse_arr,
        "summary": {
            "bpm_mean_abs_err": float(np.nanmean(abs_err)),
            "bpm_std_abs_err": float(np.nanstd(abs_err)),
            "bpm_mean_rel_err_pct": float(np.nanmean(rel_err)),
            "bpm_std_rel_err_pct": float(np.nanstd(rel_err)),
            "rmse_mean": float(np.nanmean(rmse_arr)),
            "rmse_std": float(np.nanstd(rmse_arr)),
            "n_valid_bpm": int(np.sum(valid_bpm)),
            "n_valid_rmse": int(np.sum(valid_rmse)),
        },
    }

    if verbose:
        s = result["summary"]
        print(
            f"  {seg_name} [{method_key}]: "
            f"BPM err {s['bpm_mean_abs_err']:.2f}±{s['bpm_std_abs_err']:.2f} BPM | "
            f"RMSE {s['rmse_mean']:.4f}±{s['rmse_std']:.4f}"
        )
    return result


def load_hkh_gt_signals(processed_dir: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """从预处理产物加载 HKH 带通波形与时间轴。"""
    meta_path = processed_dir / "preprocess_meta.json"
    meta = _load_preprocess_meta(meta_path)

    bundle_path = processed_dir / "aligned_bundle.npz"
    if bundle_path.is_file():
        bundle = np.load(bundle_path)
        return (
            bundle["hkh_bandpass"],
            bundle["hkh_t_host_utc_ns"],
            bundle["cs_t_host_utc_ns"],
            meta,
        )

    _, hkh_frames = load_hkh_frames(processed_dir / "HKH_frames_cropped.jsonl", verbose=False)
    hkh_t = np.array([f["t_host_utc_ns"] for f in hkh_frames], dtype=np.int64)
    raise FileNotFoundError(f"缺少 aligned_bundle.npz: {bundle_path}")
