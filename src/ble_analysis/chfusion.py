"""Multi-channel FFT + quality-weighted fusion (FFT+q).

Pipeline (see ``docs/chfusion_fft-q.md``):

1. Reuse segment filter chain from ``segments.process_segments``:
   median → highpass → bandpass (per channel, per script segment).
2. Sliding-window FFT on bandpass signals → normalized spectra ``P̄_c(f)``.
3. Compute per-channel quality sub-scores and fuse spectra with weights ``w_c``.

Comparison methods
------------------
- **fft_single_max_energy**: pick channel with max breath-band energy ratio, FFT peak.
- **fft_uniform_fusion**: equal-weight average of ``P̄_c(f)`` (FFT-uniform).
- **fft_q_fusion**: compact q-weighted fusion (default ``q_weight_mode='compact'``).
- **fft_q_peak_fusion**: use **only** ``q_peak`` as weight (ablation vs compact q).

Quality score (q_c)
-----------------
Three sub-scores (doc §1.3):

``q_valid``
    Fraction of finite phase samples in the window, mapped linearly to [0, 1]
    with threshold ``min_valid_frac`` (default 0.70).

``q_peak``
    Peak prominence in the breath band. Compute
    ``ρ = max(P) / median(P)``, then log-map ρ to [0, 1] between
    ``peak_snr_min`` and ``peak_snr_good``.

``q_phi``
    Phase smoothness after unwrap. Jump rate =
    ``mean(|Δφ| > phase_jump_rad)``; then ``q_phi = exp(-jump_rate / jump_rate_good)``.

Compact fusion weight (default)::

    q_c = (q_valid · q_peak · q_phi)^(1/3)    # geometric mean

Peak-only ablation::

    q_c = q_peak

Fusion (doc §1.4)::

    S(f) = Σ_c w_c · P̄_c(f),   w_c = q_c / Σ_j q_j
    BPM  = 60 · argmax_{f∈B} S(f)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np

from ble_analysis.channels import get_available_channels
from ble_analysis.segments import (
    BreathMetricParams,
    FilterParams,
    _estimate_breathing_freq_hz,
    _sliding_window_indices,
    estimate_sampling_rate_from_frames,
    extract_segment_data,
    process_segments,
)

# Supported q_c composition modes for weighted fusion.
QWeightMode = Literal["compact", "peak_only"]

Q_WEIGHT_MODE_LABELS: Dict[str, str] = {
    "compact": "q_c = (q_valid × q_peak × q_phi)^(1/3)",
    "peak_only": "q_c = q_peak",
}


@dataclass
class ChFusionConfig:
    """FFT+q sliding-window parameters (aligned with ``BreathMetricParams``)."""

    # Breath band for FFT peak search [Hz]
    breath_freq_low: float = 0.1
    breath_freq_high: float = 0.35
    # Denominator band for single-channel energy-ratio baseline [Hz]
    total_freq_low: float = 0.05
    total_freq_high: float = 0.8
    # Sliding window
    window_length_sec: float = 20.0
    step_length_sec: float = 1.0
    nfft: Optional[int] = None

    # --- q_valid: valid sample fraction threshold ---
    min_valid_frac: float = 0.70

    # --- q_peak: ρ = peak/median mapped in log domain ---
    peak_snr_min: float = 1.5
    peak_snr_good: float = 6.0

    # --- q_phi: unwrap phase jump penalty ---
    phase_jump_rad: float = 1.2
    jump_rate_good: float = 0.05

    # How to combine sub-scores into fusion weight q_c
    q_weight_mode: QWeightMode = "compact"

    # Optional consensus gate (doc §1.5); off by default
    enable_consensus: bool = False
    consensus_sigma_bpm: float = 2.0
    eps: float = 1e-12


def print_q_score_documentation(cfg: Optional[ChFusionConfig] = None) -> None:
    """Print q sub-score definitions and the active q_c formula to stdout."""
    cfg = cfg or ChFusionConfig()
    print("\n=== q 分数组成（docs/chfusion_fft-q.md §1.3）===")
    print("子项          | 含义                         | 计算方式")
    print("-" * 72)
    print(
        f"q_valid       | 窗内有效采样比例             | "
        f"linear map, min_valid_frac={cfg.min_valid_frac}"
    )
    print(
        f"q_peak        | 呼吸频带谱峰突出程度         | "
        f"ρ=max(P)/median(P), log map [{cfg.peak_snr_min}, {cfg.peak_snr_good}]"
    )
    print(
        f"q_phi         | 相位 unwrap 后平滑度         | "
        f"exp(-jump_rate/{cfg.jump_rate_good}), jump>{cfg.phase_jump_rad} rad"
    )
    print("-" * 72)
    print(f"compact q_c   | 默认融合权重                 | {Q_WEIGHT_MODE_LABELS['compact']}")
    print(f"peak-only q_c | 消融：仅谱峰质量             | {Q_WEIGHT_MODE_LABELS['peak_only']}")
    print(f"当前配置 q_weight_mode = '{cfg.q_weight_mode}'\n")


def _next_pow2(n: int) -> int:
    return 1 << int(np.ceil(np.log2(max(1, n))))


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if np.sum(mask) == 0:
        return float(np.nanmedian(values))
    values = values[mask]
    weights = weights[mask]
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cdf = np.cumsum(weights) / np.sum(weights)
    return float(values[np.searchsorted(cdf, 0.5)])


def _quality_from_snr(snr: float, snr_min: float, snr_good: float, eps: float) -> float:
    """Map peak/median ratio ρ to q_peak ∈ [0, 1] via log-linear clipping."""
    snr = max(float(snr), eps)
    numerator = np.log(snr) - np.log(snr_min)
    denominator = np.log(snr_good) - np.log(snr_min) + eps
    return float(np.clip(numerator / denominator, 0.0, 1.0))


def _compose_q_weight(
    q_valid: float,
    q_peak: float,
    q_phi: float,
    mode: QWeightMode,
    eps: float,
) -> float:
    """Combine sub-scores into scalar fusion weight q_c."""
    if mode == "peak_only":
        return float(q_peak)
    # compact: geometric mean of three sub-scores (doc §1.3)
    return float((q_valid * q_peak * q_phi + eps) ** (1.0 / 3.0))


def _parabolic_peak_freq(f_band: np.ndarray, power_band: np.ndarray, k: int, eps: float) -> float:
    f_hat = float(f_band[k])
    if 0 < k < len(power_band) - 1:
        y0, y1, y2 = power_band[k - 1], power_band[k], power_band[k + 1]
        denom = y0 - 2.0 * y1 + y2
        if abs(denom) > eps:
            delta = 0.5 * (y0 - y2) / denom
            df = f_band[1] - f_band[0]
            f_hat = float(f_band[k] + delta * df)
    return f_hat


def _bpm_from_fused_spectrum(
    fused: np.ndarray, band_freqs: np.ndarray, cfg: ChFusionConfig
) -> float:
    k = int(np.argmax(fused))
    f_hat = _parabolic_peak_freq(band_freqs, fused, k, cfg.eps)
    return 60.0 * f_hat


def _channel_spectrum_and_q(
    bandpass_seg: np.ndarray,
    raw_phase_seg: np.ndarray,
    fs: float,
    cfg: ChFusionConfig,
    nfft: int,
    band_mask: np.ndarray,
    band_freqs: np.ndarray,
    hann: np.ndarray,
    *,
    q_weight_mode: QWeightMode = "compact",
) -> Tuple[np.ndarray, float, float, Dict[str, float]]:
    """FFT spectrum + q sub-scores for one channel/window.

    Returns
    -------
    p_norm, q_c, f_peak, detail
        ``detail`` always includes ``q_valid``, ``q_peak``, ``q_phi``, ``q_c``,
        ``q_weight_mode``, and ``peak_snr`` (ρ).
    """
    zero_spec = np.zeros_like(band_freqs)
    bad_detail: Dict[str, float] = {
        "q_valid": 0.0,
        "q_peak": 0.0,
        "q_phi": 0.0,
        "q_c": 0.0,
        "peak_snr": 0.0,
    }

    if len(bandpass_seg) != len(hann) or not np.all(np.isfinite(bandpass_seg)):
        return zero_spec, 0.0, np.nan, bad_detail

    # q_valid: linear ramp above min_valid_frac
    valid_frac = float(np.mean(np.isfinite(raw_phase_seg)))
    q_valid = float(
        np.clip(
            (valid_frac - cfg.min_valid_frac) / (1.0 - cfg.min_valid_frac + cfg.eps),
            0.0,
            1.0,
        )
    )

    seg = bandpass_seg - np.mean(bandpass_seg)
    if np.std(seg) < cfg.eps:
        d = {**bad_detail, "q_valid": q_valid, "valid_frac": valid_frac, "q_weight_mode": q_weight_mode}
        return zero_spec, 0.0, np.nan, d

    # FFT power in breath band → q_peak
    x = np.fft.rfft(seg * hann, n=nfft)
    p_band = (np.abs(x) ** 2)[band_mask]
    peak_power = float(np.max(p_band))
    noise_floor = float(np.median(p_band) + cfg.eps)
    peak_snr = peak_power / noise_floor  # ρ in doc
    q_peak = _quality_from_snr(peak_snr, cfg.peak_snr_min, cfg.peak_snr_good, cfg.eps)
    k = int(np.argmax(p_band))
    f_peak = _parabolic_peak_freq(band_freqs, p_band, k, cfg.eps)

    # q_phi: penalize large phase steps after unwrap
    dphi = np.diff(np.unwrap(raw_phase_seg[np.isfinite(raw_phase_seg)]))
    if len(dphi) == 0:
        q_phi, jump_rate = 0.0, 1.0
    else:
        jump_rate = float(np.mean(np.abs(dphi) > cfg.phase_jump_rad))
        q_phi = float(np.exp(-jump_rate / (cfg.jump_rate_good + cfg.eps)))

    q_c = _compose_q_weight(q_valid, q_peak, q_phi, q_weight_mode, cfg.eps)
    p_norm = p_band / (np.sum(p_band) + cfg.eps)
    detail = {
        "q_valid": q_valid,
        "q_peak": q_peak,
        "q_phi": q_phi,
        "q_c": q_c,
        "q_weight_mode": q_weight_mode,
        "peak_snr": peak_snr,
        "jump_rate": jump_rate,
        "valid_frac": valid_frac,
    }
    return p_norm, q_c, f_peak, detail


def _energy_ratio(signal_seg: np.ndarray, fs: float, cfg: ChFusionConfig) -> float:
    """Breath-band energy / total-band energy (single-channel baseline selector)."""
    if len(signal_seg) < 4 or not np.all(np.isfinite(signal_seg)):
        return 0.0
    windowed = (signal_seg - np.mean(signal_seg)) * np.hanning(len(signal_seg))
    fft_power = np.abs(np.fft.rfft(windowed)) ** 2
    fft_freq = np.fft.rfftfreq(len(windowed), 1.0 / fs)
    breath_mask = (fft_freq >= cfg.breath_freq_low) & (fft_freq <= cfg.breath_freq_high)
    total_mask = (fft_freq >= cfg.total_freq_low) & (fft_freq <= cfg.total_freq_high)
    breath_energy = float(np.sum(fft_power[breath_mask]))
    total_energy = float(np.sum(fft_power[total_mask]))
    if total_energy <= cfg.eps:
        return 0.0
    return breath_energy / total_energy


def _fuse_weighted_spectrum(
    spectra_arr: np.ndarray,
    q_weights: np.ndarray,
    band_freqs: np.ndarray,
    cfg: ChFusionConfig,
    peak_freqs: Optional[np.ndarray] = None,
) -> float:
    """Fuse normalized spectra with q_c weights; optional consensus gate."""
    q_arr = np.asarray(q_weights, dtype=float)
    n_ch = spectra_arr.shape[0]

    if np.sum(q_arr) <= cfg.eps:
        weights = np.ones(n_ch) / n_ch
    else:
        q_eff = q_arr.copy()
        if cfg.enable_consensus and peak_freqs is not None:
            peak_freqs_arr = np.asarray(peak_freqs, dtype=float)
            consensus_hz = _weighted_median(peak_freqs_arr, q_arr)
            sigma_hz = cfg.consensus_sigma_bpm / 60.0
            gate = np.exp(-0.5 * ((peak_freqs_arr - consensus_hz) / (sigma_hz + cfg.eps)) ** 2)
            gate[~np.isfinite(gate)] = 0.0
            q_eff = q_arr * gate
            if np.sum(q_eff) <= cfg.eps:
                q_eff = q_arr.copy()
        weights = q_eff / (np.sum(q_eff) + cfg.eps)

    fused = np.sum(weights[:, None] * spectra_arr, axis=0)
    return _bpm_from_fused_spectrum(fused, band_freqs, cfg)


def run_multichannel_segment_filtering(
    frames,
    segment_config: Dict[str, dict],
    variable: str = "remote_amplitudes",
    phase_variable: str = "remote_phases",
    *,
    filter_params: Optional[FilterParams] = None,
    verbose: bool = True,
) -> Tuple[Dict[str, Optional[dict]], float]:
    """Extract and filter **all channels** for each script segment."""
    fs = estimate_sampling_rate_from_frames(frames)
    fp = filter_params or FilterParams()
    min_points = max(fp.median_window, 20)
    channels = get_available_channels(frames)
    out: Dict[str, Optional[dict]] = {}

    for seg_name in sorted(segment_config.keys()):
        ch_map: Dict[Any, dict] = {}
        metadata = None
        for ch in channels:
            seg_data = extract_segment_data(
                frames,
                {seg_name: segment_config[seg_name]},
                ch,
                [variable, phase_variable],
                estimated_fs=fs,
                verbose=False,
            )
            seg_raw = seg_data.get(seg_name)
            if seg_raw is None or seg_raw.get("n_points", 0) < min_points:
                continue
            try:
                seg_proc = process_segments(
                    {seg_name: seg_raw},
                    fs,
                    [variable, phase_variable],
                    fp,
                    verbose=False,
                )
            except (ValueError, RuntimeError):
                continue
            proc = seg_proc.get(seg_name)
            if proc is None:
                continue
            ch_map[ch] = proc
            if metadata is None:
                metadata = proc["metadata"]

        if not ch_map:
            out[seg_name] = None
            continue
        out[seg_name] = {"metadata": metadata, "channels": ch_map, "variable": variable}

    if verbose:
        n_ok = sum(1 for v in out.values() if v is not None)
        print(f"✓ 多信道分段滤波 {n_ok}/{len(segment_config)} 段 | {len(channels)} 信道 | fs≈{fs:.2f} Hz")
    return out, fs


def _seg_bpm_stats(bpm_arr: np.ndarray, bpm_gt: Optional[float], n_windows: int) -> dict:
    """Aggregate window BPM estimates into mean / signed / relative error stats."""
    bpm_mean = float(np.nanmean(bpm_arr))
    rel_per_win = np.array(
        [
            abs(b - bpm_gt) / bpm_gt
            if (bpm_gt and bpm_gt > 0 and np.isfinite(b))
            else np.nan
            for b in bpm_arr
        ],
        dtype=float,
    )
    valid = rel_per_win[~np.isnan(rel_per_win)]
    rel_mean = float(np.mean(valid)) if valid.size else np.nan
    rel_std = float(np.std(valid, ddof=1)) if valid.size > 1 else 0.0
    signed_per_win = np.array(
        [b - bpm_gt if (bpm_gt is not None and np.isfinite(b)) else np.nan for b in bpm_arr],
        dtype=float,
    )
    return {
        "bpm_mean": bpm_mean,
        "bpm_per_window": bpm_arr,
        "bpm_signed_err_per_window": signed_per_win,
        "bpm_rel_err": rel_mean,
        "bpm_rel_err_std": rel_std,
        "n_windows": n_windows,
    }


def _aggregate_q_details(q_details: List[Dict[str, float]]) -> dict:
    """Mean q sub-scores over all channel×window entries."""
    if not q_details:
        return {}
    keys = ("q_valid", "q_peak", "q_phi", "q_c", "peak_snr", "jump_rate", "valid_frac")
    out = {}
    for k in keys:
        vals = [d[k] for d in q_details if k in d and np.isfinite(d[k])]
        out[f"mean_{k}"] = float(np.mean(vals)) if vals else np.nan
    return out


def estimate_segment_bpm_methods(
    multichannel_segments: Dict[str, Optional[dict]],
    *,
    variable: str = "remote_amplitudes",
    phase_variable: str = "remote_phases",
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    verbose: bool = False,
) -> Dict[str, Optional[dict]]:
    """Per-segment BPM for Single / Uniform / FFT+q (compact) / FFT+q_peak."""
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    results: Dict[str, Optional[dict]] = {}

    for seg_name in sorted(multichannel_segments.keys()):
        seg = multichannel_segments[seg_name]
        if seg is None:
            results[seg_name] = None
            continue

        metadata = seg["metadata"]
        if metadata.get("segment_type") == "apnea":
            results[seg_name] = None
            continue

        bpm_gt = metadata.get("bpm_gt")
        fs = metadata["sampling_rate"]
        ch_map = seg["channels"]
        if not ch_map:
            results[seg_name] = None
            continue

        ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
        ref_len = max(len(ch_map[c][variable]["bandpass_filtered"]) for c in ch_list)
        win_len = int(round(mp.window_length_sec * fs))
        step_len = int(round(mp.step_length_sec * fs))
        if ref_len < win_len:
            if verbose:
                print(f"⚠️  {seg_name}: 长度 {ref_len} < 窗长 {win_len}，跳过")
            results[seg_name] = None
            continue

        starts = _sliding_window_indices(ref_len, win_len, step_len)
        nfft = cfg.nfft or _next_pow2(4 * win_len)
        freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)
        band_mask = (freqs >= cfg.breath_freq_low) & (freqs <= cfg.breath_freq_high)
        band_freqs = freqs[band_mask]
        hann = np.hanning(win_len)

        single_bpms: List[float] = []
        uniform_bpms: List[float] = []
        q_compact_bpms: List[float] = []
        q_peak_bpms: List[float] = []
        selected_channels: List[Any] = []
        all_q_details: List[Dict[str, float]] = []

        for st in starts:
            end = st + win_len

            # --- Baseline A: max energy-ratio single channel ---
            best_ch, best_er = None, -1.0
            for ch in ch_list:
                hp = ch_map[ch][variable]["highpass_filtered"]
                if len(hp) < end:
                    continue
                er = _energy_ratio(hp[st:end], fs, cfg)
                if er > best_er:
                    best_er, best_ch = er, ch

            if best_ch is not None:
                bp_slice = ch_map[best_ch][variable]["bandpass_filtered"][st:end]
                f_hz = _estimate_breathing_freq_hz(
                    bp_slice, fs, cfg.breath_freq_low, cfg.breath_freq_high
                )
                single_bpms.append(f_hz * 60.0 if np.isfinite(f_hz) else np.nan)
                selected_channels.append(best_ch)
            else:
                single_bpms.append(np.nan)
                selected_channels.append(None)

            # --- Per-channel spectra + q sub-scores (shared by fusion variants) ---
            spectra, q_compact, q_peak_only, peak_freqs = [], [], [], []
            for ch in ch_list:
                bp = ch_map[ch][variable]["bandpass_filtered"]
                ph = ch_map[ch].get(phase_variable, {}).get("original", bp)
                if len(bp) < end:
                    spectra.append(np.zeros_like(band_freqs))
                    q_compact.append(0.0)
                    q_peak_only.append(0.0)
                    peak_freqs.append(np.nan)
                    continue

                phase_slice = ph[st:end] if hasattr(ph, "__len__") and len(ph) >= end else bp[st:end]

                p_norm, _qc, f_peak, detail_c = _channel_spectrum_and_q(
                    bp[st:end], phase_slice, fs, cfg, nfft, band_mask, band_freqs, hann,
                    q_weight_mode="compact",
                )
                q_compact.append(detail_c["q_c"])
                q_peak_only.append(detail_c["q_peak"])
                peak_freqs.append(f_peak)
                all_q_details.append(detail_c)
                spectra.append(p_norm)

            spectra_arr = np.vstack(spectra)

            # --- Baseline B: uniform fusion ---
            valid_rows = np.sum(spectra_arr, axis=1) > cfg.eps
            if np.any(valid_rows):
                uniform_fused = np.mean(spectra_arr[valid_rows], axis=0)
            else:
                uniform_fused = np.zeros_like(band_freqs)
            uniform_bpms.append(_bpm_from_fused_spectrum(uniform_fused, band_freqs, cfg))

            # --- FFT+q compact: w_c ∝ (q_valid·q_peak·q_phi)^(1/3) ---
            q_compact_bpms.append(
                _fuse_weighted_spectrum(
                    spectra_arr, np.asarray(q_compact), band_freqs, cfg, peak_freqs
                )
            )

            # --- Ablation: FFT+q_peak only ---
            q_peak_bpms.append(
                _fuse_weighted_spectrum(
                    spectra_arr, np.asarray(q_peak_only), band_freqs, cfg, peak_freqs
                )
            )

        results[seg_name] = {
            "segment": seg_name,
            "bpm_gt": bpm_gt,
            "metadata": metadata,
            "q_summary": _aggregate_q_details(all_q_details),
            "fft_single_max_energy": {
                **_seg_bpm_stats(np.asarray(single_bpms), bpm_gt, len(starts)),
                "selected_channels": selected_channels,
            },
            "fft_uniform_fusion": _seg_bpm_stats(np.asarray(uniform_bpms), bpm_gt, len(starts)),
            "fft_q_fusion": _seg_bpm_stats(np.asarray(q_compact_bpms), bpm_gt, len(starts)),
            "fft_q_peak_fusion": _seg_bpm_stats(np.asarray(q_peak_bpms), bpm_gt, len(starts)),
        }

    return results


def print_q_component_summary(method_results: Dict[str, Optional[dict]]) -> None:
    """Print per-segment mean q_valid / q_peak / q_phi / q_c (compact)."""
    print("\n=== 各段 q 子项均值（全信道×全滑窗）===")
    print(f"{'段':<6} {'q_valid':>8} {'q_peak':>8} {'q_phi':>8} {'q_c':>8} {'ρ_peak':>8}")
    print("-" * 50)
    for seg_name in sorted(method_results.keys()):
        row = method_results[seg_name]
        if row is None:
            continue
        qs = row.get("q_summary") or {}
        print(
            f"{seg_name:<6} "
            f"{qs.get('mean_q_valid', float('nan')):8.3f} "
            f"{qs.get('mean_q_peak', float('nan')):8.3f} "
            f"{qs.get('mean_q_phi', float('nan')):8.3f} "
            f"{qs.get('mean_q_c', float('nan')):8.3f} "
            f"{qs.get('mean_peak_snr', float('nan')):8.3f}"
        )
    print("（q_c 为 compact 几何平均；FFT+q_peak 消融仅使用 q_peak 列作为权重）\n")


# Table / plot method registry: (display label, result key, color)
METHOD_LABELS = (
    ("Single", "fft_single_max_energy", "steelblue"),
    ("Uniform", "fft_uniform_fusion", "seagreen"),
    ("FFT+q", "fft_q_fusion", "coral"),
    ("FFT+q_peak", "fft_q_peak_fusion", "mediumpurple"),
)

_METHOD_KEYS = [m[1] for m in METHOD_LABELS]


def summarize_bpm_comparison(
    method_results: Dict[str, Optional[dict]],
) -> Tuple[List[dict], dict]:
    """Build per-segment rows and overall mean relative error ± std for all methods."""
    rows: List[dict] = []
    errs_by_method = {k: [] for k in _METHOD_KEYS}

    for seg_name in sorted(method_results.keys()):
        row = method_results[seg_name]
        if row is None or row.get("bpm_gt") is None:
            continue

        entry: dict = {"segment": seg_name, "bpm_gt": row["bpm_gt"]}
        for label, key, _ in METHOD_LABELS:
            prefix = key.replace("fft_", "").replace("_fusion", "")
            s = row[key]
            entry[f"{prefix}_bpm"] = s["bpm_mean"]
            entry[f"{prefix}_rel_err_pct"] = s["bpm_rel_err"] * 100 if s["bpm_rel_err"] is not None else np.nan
            entry[f"{prefix}_rel_err_std_pct"] = s["bpm_rel_err_std"] * 100
            entry[f"{prefix}_n_windows"] = s["n_windows"]
            if np.isfinite(s["bpm_rel_err"]):
                errs_by_method[key].append(s["bpm_rel_err"])

        rows.append(entry)

    def _overall(errs: List[float]) -> dict:
        if not errs:
            return {"mean_rel_err_pct": np.nan, "std_rel_err_pct": np.nan}
        a = np.asarray(errs, dtype=float)
        return {
            "mean_rel_err_pct": float(np.mean(a) * 100),
            "std_rel_err_pct": float(np.std(a, ddof=1) * 100) if len(a) > 1 else 0.0,
        }

    overall = {k: _overall(errs_by_method[k]) for k in _METHOD_KEYS}
    overall["n_segments"] = len(rows)
    return rows, overall


def _fmt_std_pct(value: float, n_windows: int) -> str:
    if n_windows < 2:
        return "  N/A"
    return f"{value:7.2f}"


def print_bpm_comparison_table(rows: List[dict], overall: dict) -> None:
    """Print BPM relative error table for all registered methods."""
    print("\n=== BPM 相对误差对比（各金属板脚本段）===")
    hdr = f"{'段':<5} {'GT':>6}"
    for label, key, _ in METHOD_LABELS:
        short = label[:8]
        hdr += f" | {short:>8} {'err%':>6} {'±std':>6}"
    print(hdr)
    print("-" * (12 + 22 * len(METHOD_LABELS)))

    for r in rows:
        line = f"{r['segment']:<5} {r['bpm_gt']:6.2f}"
        for label, key, _ in METHOD_LABELS:
            prefix = key.replace("fft_", "").replace("_fusion", "")
            line += (
                f" | {r[f'{prefix}_bpm']:8.2f} "
                f"{r[f'{prefix}_rel_err_pct']:6.2f} "
                f"{_fmt_std_pct(r[f'{prefix}_rel_err_std_pct'], r[f'{prefix}_n_windows'])}"
            )
        print(line)

    print("-" * (12 + 22 * len(METHOD_LABELS)))
    line = f"{'All':<5} {'—':>6}"
    for _label, key, _ in METHOD_LABELS:
        o = overall[key]
        line += f" | {'—':>8} {o['mean_rel_err_pct']:6.2f} {o['std_rel_err_pct']:6.2f}"
    print(line)
    print(
        f"（{overall['n_segments']} 个 breath 段；"
        f"FFT+q={Q_WEIGHT_MODE_LABELS['compact']}；"
        f"FFT+q_peak={Q_WEIGHT_MODE_LABELS['peak_only']}；"
        f"±std=窗级相对误差标准差，1 窗时为 N/A）\n"
    )


def collect_window_signed_errors(method_results: Dict[str, Optional[dict]]) -> List[dict]:
    """Collect per-window signed BPM errors (estimated − GT) for violin plots."""
    records: List[dict] = []
    for seg_name in sorted(method_results.keys()):
        row = method_results[seg_name]
        if row is None or row.get("bpm_gt") is None:
            continue
        bpm_gt = float(row["bpm_gt"])
        for label, key, _color in METHOD_LABELS:
            signed = row[key].get("bpm_signed_err_per_window")
            if signed is None:
                bpm_wins = row[key]["bpm_per_window"]
                signed = np.array(
                    [b - bpm_gt if np.isfinite(b) else np.nan for b in bpm_wins], dtype=float
                )
            signed = np.asarray(signed, dtype=float)
            signed = signed[np.isfinite(signed)]
            records.append(
                {"segment": seg_name, "method": label, "bpm_gt": bpm_gt, "signed_errors": signed}
            )
    return records


def plot_bpm_error_violins(
    method_results: Dict[str, Optional[dict]],
    *,
    figures_dir=None,
    filename: str = "chfusion_fft_q_bpm_error_violins.png",
    show: bool = True,
    save: bool = True,
):
    """Violin plot of signed window-level BPM error; y=0 is ground truth."""
    import matplotlib.pyplot as plt

    records = collect_window_signed_errors(method_results)
    if not records:
        print("⚠️  无可用误差数据，跳过小提琴图")
        return None

    segments = sorted({r["segment"] for r in records})
    gt_by_seg = {r["segment"]: r["bpm_gt"] for r in records}
    methods = [m[0] for m in METHOD_LABELS]
    colors = {m[0]: m[2] for m in METHOD_LABELS}

    n_seg = len(segments)
    n_methods = len(methods)
    group_gap = 1.0
    group_width = 0.8
    violin_width = group_width / n_methods

    fig, ax = plt.subplots(figsize=(max(12, n_seg * 2.0), 5.5))

    for i, seg in enumerate(segments):
        group_center = i * group_gap
        for j, method in enumerate(methods):
            rec = next(r for r in records if r["segment"] == seg and r["method"] == method)
            errors = rec["signed_errors"]
            pos = group_center + (j - (n_methods - 1) / 2) * violin_width
            color = colors[method]

            if len(errors) >= 2:
                parts = ax.violinplot(
                    [errors],
                    positions=[pos],
                    widths=violin_width * 0.85,
                    showmeans=True,
                    showmedians=True,
                    showextrema=False,
                )
                for body in parts["bodies"]:
                    body.set_facecolor(color)
                    body.set_edgecolor("black")
                    body.set_alpha(0.65)
                parts["cmeans"].set_color("black")
                parts["cmeans"].set_linewidth(1.2)
                parts["cmedians"].set_color("white")
                parts["cmedians"].set_linewidth(1.5)
            elif len(errors) == 1:
                ax.scatter([pos], errors, color=color, edgecolors="black", s=40, zorder=4)

    ax.axhline(0.0, color="black", linestyle="--", linewidth=1.2, alpha=0.75)
    ax.set_xticks([i * group_gap for i in range(n_seg)])
    ax.set_xticklabels([f"{seg}\nGT={gt_by_seg[seg]:.2f}" for seg in segments])
    ax.set_ylabel("BPM error (estimated − GT)")
    ax.set_title("Window-level BPM error by segment (violin)")
    ax.grid(True, axis="y", alpha=0.25)

    legend_handles = [
        plt.Line2D([0], [0], color=colors[m], lw=6, alpha=0.65, label=m) for m in methods
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8)
    plt.tight_layout()

    fig_path = None
    if save and figures_dir is not None:
        fig_path = Path(figures_dir) / filename
        fig.savefig(fig_path, dpi=150)
        print(f"✓ 小提琴图已保存: {fig_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig
