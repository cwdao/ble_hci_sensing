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
- **fft_q_energy_peak_fusion**: ``q_energy_peak`` = geometric mean of ``q_energy`` and ``q_peak`` (see ``docs/chfusion_q_energy_peak.md``).
- **fft_q_energy_peak_topk_fusion**: Top-K channels by ``q_energy`` (linear map), then fusion.
- **fft_q_energy_peak_topk_log_fusion**: Same as top-K, but ``q_energy`` uses log map like ``q_peak``.

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

``q_energy``
    Breath-band energy concentration (Single-channel selector metric):
    ``η = E_breath / E_total`` on highpass signal, linear-mapped to [0, 1]
    between ``energy_ratio_min`` and ``energy_ratio_good``.

``q_phi``
    Phase smoothness after unwrap. Jump rate =
    ``mean(|Δφ| > phase_jump_rad)``; then ``q_phi = exp(-jump_rate / jump_rate_good)``.

Compact fusion weight (default)::

    q_c = (q_valid · q_peak · q_phi)^(1/3)    # geometric mean

Peak-only ablation::

    q_c = q_peak

Energy + peak fusion (``q_energy_peak``)::

    q_c = (q_energy · q_peak)^(1/2)

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

# CS 可融合的四种有效观测量（本地/远程单端相位无独立物理意义，不纳入）
CS_SIGNAL_VARIABLES: Tuple[Tuple[str, str], ...] = (
    ("amplitudes", "总幅值 amp"),
    ("remote_amplitudes", "远程幅值 remote"),
    ("local_amplitudes", "本地幅值 local"),
    ("phases", "总相位 phase"),
)

# English labels for matplotlib titles/legends (avoid CJK font issues)
VARIABLE_PLOT_LABELS: Dict[str, str] = {
    "amplitudes": "Total amplitude",
    "remote_amplitudes": "Remote amplitude",
    "local_amplitudes": "Local amplitude",
    "phases": "Total phase (unwrapped)",
}

# Part-2 默认对比的融合方法（详见 docs/chfusion_q_energy_peak.md）
FUSION_METHOD_KEYS: Tuple[str, ...] = (
    "fft_single_max_energy",
    "fft_uniform_fusion",
    "fft_q_peak_fusion",
    "fft_q_energy_peak_fusion",
    "fft_q_energy_peak_topk_fusion",
    "fft_q_energy_peak_topk_log_fusion",
)

FUSION_METHOD_LABELS: Tuple[Tuple[str, str, str], ...] = (
    ("Single", "fft_single_max_energy", "steelblue"),
    ("Uniform", "fft_uniform_fusion", "seagreen"),
    ("FFT+q_peak", "fft_q_peak_fusion", "mediumpurple"),
    ("FFT+q_energy_peak", "fft_q_energy_peak_fusion", "darkorange"),
    ("FFT+q_ep_topK", "fft_q_energy_peak_topk_fusion", "crimson"),
    ("FFT+q_ep_topK_log", "fft_q_energy_peak_topk_log_fusion", "chocolate"),
)

# Supported q_c composition modes for weighted fusion.
QWeightMode = Literal["compact", "peak_only", "energy_peak"]

Q_WEIGHT_MODE_LABELS: Dict[str, str] = {
    "compact": "q_c = (q_valid × q_peak × q_phi)^(1/3)",
    "peak_only": "q_c = q_peak",
    "energy_peak": "q_c = (q_energy × q_peak)^(1/2)",
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

    # --- q_energy: breath/total band energy ratio (Single selector metric) ---
    energy_ratio_min: float = 0.02
    energy_ratio_good: float = 0.20

    # --- q_energy + q_peak Top-K prefilter (see docs/chfusion_q_energy_peak.md §5) ---
    energy_peak_top_k: Optional[int] = 5

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
        f"q_energy      | 呼吸/全频段能量比 (≈SNR)     | "
        f"η linear [{cfg.energy_ratio_min}, {cfg.energy_ratio_good}] "
        f"or log (topK_log)"
    )
    print(
        f"q_phi         | 相位 unwrap 后平滑度         | "
        f"exp(-jump_rate/{cfg.jump_rate_good}), jump>{cfg.phase_jump_rad} rad"
    )
    print("-" * 72)
    print(f"compact q_c   | 默认融合权重                 | {Q_WEIGHT_MODE_LABELS['compact']}")
    print(f"peak-only q_c | 消融：仅谱峰质量             | {Q_WEIGHT_MODE_LABELS['peak_only']}")
    print(
        f"energy_peak   | 能量比 + 谱峰                | {Q_WEIGHT_MODE_LABELS['energy_peak']}"
    )
    topk = cfg.energy_peak_top_k
    topk_str = str(topk) if topk is not None and topk > 0 else "all channels"
    print(
        f"q_ep_topK     | 先 q_energy Top-{topk_str} 再 energy+peak (linear η) | "
        f"ChFusionConfig.energy_peak_top_k"
    )
    print(
        f"q_ep_topK_log | 同上，q_energy 用 log 映射 (同 q_peak) | "
        f"fft_q_energy_peak_topk_log_fusion"
    )
    print(f"详细说明见 docs/chfusion_q_energy_peak.md")
    print(f"当前配置 q_weight_mode = '{cfg.q_weight_mode}'\n")


def _is_phase_variable(variable: str) -> bool:
    """True for composite or per-end phase series that require unwrap before filtering."""
    return variable == "phases" or variable.endswith("_phases")


def _preprocess_raw_series(raw: np.ndarray, variable: str) -> np.ndarray:
    """Apply variable-specific preprocessing before the filter chain.

    Phase (total ``phases`` from local⊗remote product) must be unwrapped so that
    highpass/bandpass see continuous incremental change, not 2π wraps.
    Amplitude variables are passed through unchanged.
    """
    x = np.asarray(raw, dtype=float)
    if not _is_phase_variable(variable):
        return x
    mask = np.isfinite(x)
    if np.sum(mask) < 2:
        return x
    out = x.copy()
    out[mask] = np.unwrap(x[mask])
    return out


def _variable_display_name(variable: str) -> str:
    for key, label in CS_SIGNAL_VARIABLES:
        if key == variable:
            return label
    return variable


def _variable_plot_label(variable: str) -> str:
    """English-only label for figure titles and legends."""
    return VARIABLE_PLOT_LABELS.get(variable, variable.replace("_", " "))


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


def _quality_from_energy_ratio(
    energy_ratio: float,
    er_min: float,
    er_good: float,
    eps: float,
    *,
    log_map: bool = False,
) -> float:
    """Map breath/total band energy ratio η to q_energy ∈ [0, 1].

    ``log_map=False`` (default): linear clip — used by ``FFT+q_energy_peak`` and
    ``FFT+q_ep_topK``.  ``log_map=True``: same log-linear formula as ``q_peak``
    — used by ``FFT+q_ep_topK_log``. See ``docs/chfusion_q_energy_peak.md`` §5–§6.
    """
    er = max(float(np.clip(energy_ratio, 0.0, 1.0)), eps)
    if log_map:
        return _quality_from_snr(er, er_min, er_good, eps)
    return float(np.clip((er - er_min) / (er_good - er_min + eps), 0.0, 1.0))


def _compose_q_weight(
    q_valid: float,
    q_peak: float,
    q_phi: float,
    mode: QWeightMode,
    eps: float,
    *,
    q_energy: float = 0.0,
) -> float:
    """Combine sub-scores into scalar fusion weight q_c."""
    if mode == "peak_only":
        return float(q_peak)
    if mode == "energy_peak":
        return float((q_energy * q_peak + eps) ** 0.5)
    # compact: geometric mean of three sub-scores (doc §1.3)
    return float((q_valid * q_peak * q_phi + eps) ** (1.0 / 3.0))


def _mask_top_k_by_score(
    weights: np.ndarray, scores: np.ndarray, top_k: Optional[int]
) -> np.ndarray:
    """Zero fusion weights for channels outside Top-K (ranked by ``scores`` descending).

    Used by ``fft_q_energy_peak_topk_fusion``: prefilter on ``q_energy``, then fuse
    with ``q_energy_peak`` weights on survivors. See ``docs/chfusion_q_energy_peak.md`` §5.
    """
    w = np.asarray(weights, dtype=float)
    s = np.asarray(scores, dtype=float)
    n = len(w)
    if top_k is None or top_k <= 0 or n <= top_k:
        return w
    k = min(int(top_k), n)
    top_idx = np.argsort(s)[-k:]
    mask = np.zeros(n, dtype=bool)
    mask[top_idx] = True
    return np.where(mask, w, 0.0)


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
    compute_q_phi: bool = True,
) -> Tuple[np.ndarray, float, float, Dict[str, float]]:
    """FFT spectrum + q sub-scores for one channel/window.

    For **amplitude** variables set ``compute_q_phi=False`` (q_phi=1).
    For **phase** variables pass unwrapped phase as ``raw_phase_seg`` and
    ``compute_q_phi=True``.

    Returns
    -------
    p_norm, q_c, f_peak, detail
        ``detail`` includes ``q_valid``, ``q_peak``, ``q_phi``, ``q_c``, ``peak_snr``.
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

    # q_phi: phase smoothness (only meaningful for phase signals)
    if compute_q_phi:
        dphi = np.diff(np.unwrap(raw_phase_seg[np.isfinite(raw_phase_seg)]))
        if len(dphi) == 0:
            q_phi, jump_rate = 0.0, 1.0
        else:
            jump_rate = float(np.mean(np.abs(dphi) > cfg.phase_jump_rad))
            q_phi = float(np.exp(-jump_rate / (cfg.jump_rate_good + cfg.eps)))
    else:
        q_phi, jump_rate = 1.0, 0.0

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
    variable: str = "amplitudes",
    *,
    filter_params: Optional[FilterParams] = None,
    verbose: bool = True,
) -> Tuple[Dict[str, Optional[dict]], float]:
    """Extract and filter **all channels** for one signal variable per segment.

    For ``phases``, raw series are **unwrapped** before median/highpass/bandpass.
    Only the requested ``variable`` is extracted (no separate remote/local phase).
    """
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
                [variable],
                estimated_fs=fs,
                verbose=False,
            )
            seg_raw = seg_data.get(seg_name)
            if seg_raw is None or seg_raw.get("n_points", 0) < min_points:
                continue
            # Unwrap phase (if needed) then filter
            seg_raw = dict(seg_raw)
            seg_raw[variable] = _preprocess_raw_series(seg_raw[variable], variable)
            try:
                seg_proc = process_segments(
                    {seg_name: seg_raw},
                    fs,
                    [variable],
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
        out[seg_name] = {
            "metadata": metadata,
            "channels": ch_map,
            "variable": variable,
            "is_phase": _is_phase_variable(variable),
        }

    if verbose:
        n_ok = sum(1 for v in out.values() if v is not None)
        tag = _variable_display_name(variable)
        print(
            f"✓ [{tag}] 多信道滤波 {n_ok}/{len(segment_config)} 段 | "
            f"{len(channels)} 信道 | fs≈{fs:.2f} Hz"
        )
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
    keys = (
        "q_valid", "q_peak", "q_energy", "q_energy_log", "q_phi", "q_c",
        "peak_snr", "energy_ratio", "jump_rate", "valid_frac",
    )
    out = {}
    for k in keys:
        vals = [d[k] for d in q_details if k in d and np.isfinite(d[k])]
        out[f"mean_{k}"] = float(np.mean(vals)) if vals else np.nan
    return out


def estimate_segment_bpm_methods(
    multichannel_segments: Dict[str, Optional[dict]],
    *,
    variable: str = "amplitudes",
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    methods: Sequence[str] = (
        "single", "uniform", "q_peak", "q_energy_peak", "q_energy_peak_topk",
        "q_energy_peak_topk_log", "q_compact",
    ),
    verbose: bool = False,
) -> Dict[str, Optional[dict]]:
    """Per-segment BPM for selected fusion methods.

    Parameters
    ----------
    methods
        Subset of ``single``, ``uniform``, ``q_peak``, ``q_energy_peak``,
        ``q_energy_peak_topk``, ``q_energy_peak_topk_log``, ``q_compact``.
        Part-2 benchmark uses all five fusion baselines; see ``docs/chfusion_q_energy_peak.md``.
    """
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    want_single = "single" in methods
    want_uniform = "uniform" in methods
    want_q_peak = "q_peak" in methods
    want_q_energy_peak = "q_energy_peak" in methods
    want_q_energy_peak_topk = "q_energy_peak_topk" in methods
    want_q_energy_peak_topk_log = "q_energy_peak_topk_log" in methods
    want_q_compact = "q_compact" in methods
    need_log_q_energy = want_q_energy_peak_topk_log
    compute_q_phi = _is_phase_variable(variable)
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
        q_energy_peak_bpms: List[float] = []
        q_energy_peak_topk_bpms: List[float] = []
        q_energy_peak_topk_log_bpms: List[float] = []
        selected_channels: List[Any] = []
        all_q_details: List[Dict[str, float]] = []

        for st in starts:
            end = st + win_len

            # --- Single: max energy-ratio channel + FFT peak ---
            if want_single:
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

            need_fusion = (
                want_uniform
                or want_q_peak
                or want_q_energy_peak
                or want_q_energy_peak_topk
                or want_q_energy_peak_topk_log
                or want_q_compact
            )
            if need_fusion:
                (
                    spectra,
                    q_compact,
                    q_peak_only,
                    q_energy_peak_only,
                    q_energy_peak_log_only,
                    q_energies,
                    q_energies_log,
                    peak_freqs,
                ) = ([], [], [], [], [], [], [], [])
                for ch in ch_list:
                    bp = ch_map[ch][variable]["bandpass_filtered"]
                    hp = ch_map[ch][variable]["highpass_filtered"]
                    raw = ch_map[ch][variable]["original"]
                    if len(bp) < end:
                        spectra.append(np.zeros_like(band_freqs))
                        q_compact.append(0.0)
                        q_peak_only.append(0.0)
                        q_energy_peak_only.append(0.0)
                        q_energy_peak_log_only.append(0.0)
                        q_energies.append(0.0)
                        q_energies_log.append(0.0)
                        peak_freqs.append(np.nan)
                        continue

                    ref_slice = raw[st:end] if len(raw) >= end else bp[st:end]
                    p_norm, _qc, f_peak, detail_c = _channel_spectrum_and_q(
                        bp[st:end],
                        ref_slice,
                        fs,
                        cfg,
                        nfft,
                        band_mask,
                        band_freqs,
                        hann,
                        q_weight_mode="compact",
                        compute_q_phi=compute_q_phi,
                    )
                    energy_ratio = (
                        _energy_ratio(hp[st:end], fs, cfg) if len(hp) >= end else 0.0
                    )
                    q_energy = _quality_from_energy_ratio(
                        energy_ratio,
                        cfg.energy_ratio_min,
                        cfg.energy_ratio_good,
                        cfg.eps,
                        log_map=False,
                    )
                    q_ep = _compose_q_weight(
                        detail_c["q_valid"],
                        detail_c["q_peak"],
                        detail_c["q_phi"],
                        "energy_peak",
                        cfg.eps,
                        q_energy=q_energy,
                    )
                    if need_log_q_energy:
                        q_energy_log = _quality_from_energy_ratio(
                            energy_ratio,
                            cfg.energy_ratio_min,
                            cfg.energy_ratio_good,
                            cfg.eps,
                            log_map=True,
                        )
                        q_ep_log = _compose_q_weight(
                            detail_c["q_valid"],
                            detail_c["q_peak"],
                            detail_c["q_phi"],
                            "energy_peak",
                            cfg.eps,
                            q_energy=q_energy_log,
                        )
                    else:
                        q_energy_log, q_ep_log = 0.0, 0.0
                    detail_c = {
                        **detail_c,
                        "energy_ratio": energy_ratio,
                        "q_energy": q_energy,
                        "q_energy_peak": q_ep,
                        "q_energy_log": q_energy_log,
                        "q_energy_peak_log": q_ep_log,
                    }
                    q_compact.append(detail_c["q_c"])
                    q_peak_only.append(detail_c["q_peak"])
                    q_energy_peak_only.append(q_ep)
                    q_energy_peak_log_only.append(q_ep_log)
                    q_energies.append(q_energy)
                    q_energies_log.append(q_energy_log)
                    peak_freqs.append(f_peak)
                    all_q_details.append(detail_c)
                    spectra.append(p_norm)

                spectra_arr = np.vstack(spectra)

                if want_uniform:
                    valid_rows = np.sum(spectra_arr, axis=1) > cfg.eps
                    if np.any(valid_rows):
                        uniform_fused = np.mean(spectra_arr[valid_rows], axis=0)
                    else:
                        uniform_fused = np.zeros_like(band_freqs)
                    uniform_bpms.append(_bpm_from_fused_spectrum(uniform_fused, band_freqs, cfg))

                if want_q_compact:
                    q_compact_bpms.append(
                        _fuse_weighted_spectrum(
                            spectra_arr, np.asarray(q_compact), band_freqs, cfg, peak_freqs
                        )
                    )

                if want_q_peak:
                    q_peak_bpms.append(
                        _fuse_weighted_spectrum(
                            spectra_arr, np.asarray(q_peak_only), band_freqs, cfg, peak_freqs
                        )
                    )

                if want_q_energy_peak:
                    q_energy_peak_bpms.append(
                        _fuse_weighted_spectrum(
                            spectra_arr,
                            np.asarray(q_energy_peak_only),
                            band_freqs,
                            cfg,
                            peak_freqs,
                        )
                    )

                if want_q_energy_peak_topk:
                    topk_weights = _mask_top_k_by_score(
                        np.asarray(q_energy_peak_only),
                        np.asarray(q_energies),
                        cfg.energy_peak_top_k,
                    )
                    q_energy_peak_topk_bpms.append(
                        _fuse_weighted_spectrum(
                            spectra_arr,
                            topk_weights,
                            band_freqs,
                            cfg,
                            peak_freqs,
                        )
                    )

                if want_q_energy_peak_topk_log:
                    topk_log_weights = _mask_top_k_by_score(
                        np.asarray(q_energy_peak_log_only),
                        np.asarray(q_energies_log),
                        cfg.energy_peak_top_k,
                    )
                    q_energy_peak_topk_log_bpms.append(
                        _fuse_weighted_spectrum(
                            spectra_arr,
                            topk_log_weights,
                            band_freqs,
                            cfg,
                            peak_freqs,
                        )
                    )

        seg_out: dict = {
            "segment": seg_name,
            "bpm_gt": bpm_gt,
            "variable": variable,
            "metadata": metadata,
            "q_summary": _aggregate_q_details(all_q_details),
        }
        if want_single:
            seg_out["fft_single_max_energy"] = {
                **_seg_bpm_stats(np.asarray(single_bpms), bpm_gt, len(starts)),
                "selected_channels": selected_channels,
            }
        if want_uniform:
            seg_out["fft_uniform_fusion"] = _seg_bpm_stats(
                np.asarray(uniform_bpms), bpm_gt, len(starts)
            )
        if want_q_compact:
            seg_out["fft_q_fusion"] = _seg_bpm_stats(
                np.asarray(q_compact_bpms), bpm_gt, len(starts)
            )
        if want_q_peak:
            seg_out["fft_q_peak_fusion"] = _seg_bpm_stats(
                np.asarray(q_peak_bpms), bpm_gt, len(starts)
            )
        if want_q_energy_peak:
            seg_out["fft_q_energy_peak_fusion"] = _seg_bpm_stats(
                np.asarray(q_energy_peak_bpms), bpm_gt, len(starts)
            )
        if want_q_energy_peak_topk:
            seg_out["fft_q_energy_peak_topk_fusion"] = _seg_bpm_stats(
                np.asarray(q_energy_peak_topk_bpms), bpm_gt, len(starts)
            )
        if want_q_energy_peak_topk_log:
            seg_out["fft_q_energy_peak_topk_log_fusion"] = _seg_bpm_stats(
                np.asarray(q_energy_peak_topk_log_bpms), bpm_gt, len(starts)
            )
        results[seg_name] = seg_out

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


def _overall_rel_error(method_results: Dict[str, Optional[dict]], method_key: str) -> dict:
    """Mean segment-level relative BPM error (%) for one method key."""
    errs = []
    for row in method_results.values():
        if row is None or row.get("bpm_gt") is None:
            continue
        block = row.get(method_key)
        if block is None:
            continue
        e = block.get("bpm_rel_err")
        if e is not None and np.isfinite(e):
            errs.append(float(e))
    if not errs:
        return {"mean_rel_err_pct": np.nan, "std_rel_err_pct": np.nan, "n_segments": 0}
    a = np.asarray(errs, dtype=float)
    return {
        "mean_rel_err_pct": float(np.mean(a) * 100),
        "std_rel_err_pct": float(np.std(a, ddof=1) * 100) if len(a) > 1 else 0.0,
        "n_segments": len(a),
    }


def run_chfusion_benchmark(
    frames,
    segment_config: Dict[str, dict],
    *,
    variables: Optional[Sequence[str]] = None,
    filter_params: Optional[FilterParams] = None,
    metric_params: Optional[BreathMetricParams] = None,
    config: Optional[ChFusionConfig] = None,
    verbose: bool = True,
) -> dict:
    """Two-part benchmark over all CS signal variables.

    Part 1 — variable comparison (Single / max-energy channel only).
    Part 2 — method comparison (Single, Uniform, FFT+q_peak, FFT+q_energy_peak,
    FFT+q_ep_topK) per variable. See ``docs/chfusion_q_energy_peak.md``.

    Returns dict with ``part1``, ``part2``, ``leaderboard`` keys.
    """
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    fp = filter_params or FilterParams()
    var_list = list(variables or [v[0] for v in CS_SIGNAL_VARIABLES])

    part1: Dict[str, dict] = {}
    part2: Dict[str, dict] = {}

    for variable in var_list:
        mc, fs = run_multichannel_segment_filtering(
            frames, segment_config, variable=variable, filter_params=fp, verbose=verbose
        )
        r1 = estimate_segment_bpm_methods(
            mc, variable=variable, config=cfg, metric_params=mp, methods=("single",)
        )
        r2 = estimate_segment_bpm_methods(
            mc,
            variable=variable,
            config=cfg,
            metric_params=mp,
            methods=(
                "single", "uniform", "q_peak", "q_energy_peak",
                "q_energy_peak_topk", "q_energy_peak_topk_log",
            ),
        )
        part1[variable] = {"results": r1, "sampling_rate": fs}
        part2[variable] = {"results": r2, "sampling_rate": fs}

    leaderboard = build_benchmark_leaderboard(part1, part2)
    return {
        "variables": var_list,
        "part1": part1,
        "part2": part2,
        "leaderboard": leaderboard,
        "segment_config": segment_config,
    }


def build_benchmark_leaderboard(part1: dict, part2: dict) -> List[dict]:
    """Rank all (variable × method) combos from Part 2 by mean relative BPM error."""
    rows: List[dict] = []

    for variable, block in part2.items():
        for label, key, _ in FUSION_METHOD_LABELS:
            stats = _overall_rel_error(block["results"], key)
            rows.append(
                {
                    "part": 2,
                    "variable": variable,
                    "variable_label": _variable_display_name(variable),
                    "method": label,
                    "method_key": key,
                    **stats,
                }
            )

    rows = [r for r in rows if np.isfinite(r["mean_rel_err_pct"])]
    rows.sort(key=lambda r: r["mean_rel_err_pct"])
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def print_part1_variable_table(part1: dict) -> None:
    """Part 1: compare four variables using Single (max-energy) FFT only."""
    print("\n=== Part 1：变量对比（Single / 最大能量比单信道 FFT）===")
    print(f"{'变量':<22} {'mean err%':>10} {'±std%':>8} {'n_seg':>6}")
    print("-" * 50)
    rows = []
    for variable, block in part1.items():
        stats = _overall_rel_error(block["results"], "fft_single_max_energy")
        rows.append((variable, stats))
    rows.sort(key=lambda x: x[1]["mean_rel_err_pct"])
    for variable, stats in rows:
        print(
            f"{_variable_display_name(variable):<22} "
            f"{stats['mean_rel_err_pct']:10.2f} "
            f"{stats['std_rel_err_pct']:8.2f} "
            f"{stats['n_segments']:6d}"
        )
    print("（误差为各 breath 段相对 BPM 误差的均值；phase 变量滤波前已 unwrap）\n")


def print_part2_method_tables(part2: dict) -> None:
    """Part 2: compare Single / Uniform / FFT+q_peak / FFT+q_energy_peak / topK / topK_log."""
    print(
        "\n=== Part 2：方法对比（Single / Uniform / FFT+q_peak / "
        "FFT+q_energy_peak / FFT+q_ep_topK / FFT+q_ep_topK_log）==="
    )
    for variable, block in part2.items():
        print(f"\n--- {_variable_display_name(variable)} ({variable}) ---")
        print(f"{'方法':<12} {'mean err%':>10} {'±std%':>8} {'n_seg':>6}")
        print("-" * 40)
        for label, key, _ in FUSION_METHOD_LABELS:
            stats = _overall_rel_error(block["results"], key)
            print(
                f"{label:<12} {stats['mean_rel_err_pct']:10.2f} "
                f"{stats['std_rel_err_pct']:8.2f} {stats['n_segments']:6d}"
            )
    print()


def print_benchmark_leaderboard(leaderboard: List[dict], top_n: Optional[int] = None) -> None:
    """Print ranked table of all variable×method combinations (Part 2 matrix)."""
    ranked = sorted(leaderboard, key=lambda r: r.get("rank", 9999))
    if top_n is not None:
        ranked = ranked[:top_n]
    print("\n=== 总排行榜：变量 × 方法 BPM 估计性能（按 mean err% 升序）===")
    print(f"{'#':>3} {'变量':<18} {'方法':<12} {'err%':>8} {'±std%':>8}")
    print("-" * 54)
    for r in ranked:
        print(
            f"{r['rank']:3d} {r['variable_label']:<18} "
            f"{r['method']:<12} {r['mean_rel_err_pct']:8.2f} {r['std_rel_err_pct']:8.2f}"
        )
    if ranked:
        best = ranked[0]
        print(
            f"\n★ 当前最优：{best['variable_label']} + {best['method']} "
            f"→ mean err {best['mean_rel_err_pct']:.2f}%\n"
        )


def collect_window_signed_errors(
    method_results: Dict[str, Optional[dict]],
    method_labels: Sequence[Tuple[str, str, str]] = FUSION_METHOD_LABELS,
) -> List[dict]:
    """Collect per-window signed BPM errors (estimated − GT) for violin plots."""
    records: List[dict] = []
    for seg_name in sorted(method_results.keys()):
        row = method_results[seg_name]
        if row is None or row.get("bpm_gt") is None:
            continue
        bpm_gt = float(row["bpm_gt"])
        for label, key, _color in method_labels:
            if key not in row:
                continue
            block = row[key]
            signed = block.get("bpm_signed_err_per_window")
            if signed is None:
                bpm_wins = block["bpm_per_window"]
                signed = np.array(
                    [b - bpm_gt if np.isfinite(b) else np.nan for b in bpm_wins], dtype=float
                )
            signed = np.asarray(signed, dtype=float)
            signed = signed[np.isfinite(signed)]
            records.append(
                {"segment": seg_name, "method": label, "bpm_gt": bpm_gt, "signed_errors": signed}
            )
    return records


# ---------------------------------------------------------------------------
# Overview plotting: full 4 variables × N methods matrix (see docs/chfusion_q_energy_peak.md)
# ---------------------------------------------------------------------------
# Part 1 violins compare variables (Single only); Part 2 violins compare methods
# per variable (4 separate figures). The functions below add aggregate views:
#
#   collect_part2_variable_method_errors  → flat records for all 16 combos
#   _part2_matrix_stats                   → mean/std matrices for bars & heatmap
#   plot_overview_matrix_bars             → grouped bar chart (leaderboard view)
#   plot_overview_matrix_heatmap          → colour matrix of mean rel error
#   plot_overview_violins_by_method       → Part 1 extended to 4 methods (N×1 stack)
#   plot_overview_violins_by_variable     → Part 2 merged into one N×1 figure
#
# Called from plot_benchmark_violins() after Part 1/2 individual figures.
# All benchmark figures are saved as vector PDF (CHFUSION_FIGURE_FORMAT).

# Benchmark figure output format (vector PDF for publication / LaTeX)
CHFUSION_FIGURE_FORMAT = "pdf"
CHFUSION_FIGURE_EXT = ".pdf"


def _chfusion_figure_name(stem: str) -> str:
    """Return benchmark figure filename with the configured extension."""
    return f"{stem}{CHFUSION_FIGURE_EXT}"


def _save_chfusion_figure(fig, path: Path, *, bbox_inches: Optional[str] = None) -> Path:
    """Save a matplotlib figure as PDF (``CHFUSION_FIGURE_FORMAT``)."""
    kwargs: Dict[str, Any] = {"format": CHFUSION_FIGURE_FORMAT}
    if bbox_inches is not None:
        kwargs["bbox_inches"] = bbox_inches
    fig.savefig(path, **kwargs)
    return path


def _signed_errors_from_method_block(block: dict, bpm_gt: float) -> np.ndarray:
    """Window-level signed BPM errors (estimated − GT) from one method result block."""
    signed = block.get("bpm_signed_err_per_window")
    if signed is None:
        signed = np.array(
            [b - bpm_gt if np.isfinite(b) else np.nan for b in block["bpm_per_window"]],
            dtype=float,
        )
    signed = np.asarray(signed, dtype=float)
    return signed[np.isfinite(signed)]


def collect_part1_variable_errors(part1: dict) -> List[dict]:
    """Part-1: signed errors per segment × variable (Single method only)."""
    records: List[dict] = []
    for variable, block in part1.items():
        results = block["results"]
        var_label = _variable_display_name(variable)
        for seg_name in sorted(results.keys()):
            row = results[seg_name]
            if row is None or row.get("bpm_gt") is None:
                continue
            bpm_gt = float(row["bpm_gt"])
            single = row.get("fft_single_max_energy")
            if single is None:
                continue
            signed = _signed_errors_from_method_block(single, bpm_gt)
            records.append(
                {
                    "segment": seg_name,
                    "variable": variable,
                    "variable_label": var_label,
                    "bpm_gt": bpm_gt,
                    "signed_errors": signed,
                }
            )
    return records


def collect_part2_variable_method_errors(part2: dict) -> List[dict]:
    """Collect window-level signed errors for every segment × variable × method.

    Each record has keys: segment, variable, variable_label, method, method_key,
    bpm_gt, signed_errors. Used by overview violin plots (4×4 matrix).
    """
    records: List[dict] = []
    for variable, block in part2.items():
        results = block["results"]
        var_label = _variable_plot_label(variable)
        for seg_name in sorted(results.keys()):
            row = results[seg_name]
            if row is None or row.get("bpm_gt") is None:
                continue
            bpm_gt = float(row["bpm_gt"])
            for label, key, _color in FUSION_METHOD_LABELS:
                method_block = row.get(key)
                if method_block is None:
                    continue
                signed = _signed_errors_from_method_block(method_block, bpm_gt)
                records.append(
                    {
                        "segment": seg_name,
                        "variable": variable,
                        "variable_label": var_label,
                        "method": label,
                        "method_key": key,
                        "bpm_gt": bpm_gt,
                        "signed_errors": signed,
                    }
                )
    return records


def plot_bpm_error_violins(
    method_results: Dict[str, Optional[dict]],
    *,
    method_labels: Sequence[Tuple[str, str, str]] = FUSION_METHOD_LABELS,
    figures_dir=None,
    filename: str = "",
    title: Optional[str] = None,
    show: bool = True,
    save: bool = True,
):
    """Violin plot of signed window-level BPM error; y=0 is ground truth."""
    import matplotlib.pyplot as plt

    if not filename:
        filename = _chfusion_figure_name("chfusion_fft_q_bpm_error_violins")

    records = collect_window_signed_errors(method_results, method_labels)
    if not records:
        print("⚠️  无可用误差数据，跳过小提琴图")
        return None

    segments = sorted({r["segment"] for r in records})
    gt_by_seg = {r["segment"]: r["bpm_gt"] for r in records}
    methods = [m[0] for m in method_labels]
    colors = {m[0]: m[2] for m in method_labels}

    n_seg = len(segments)
    n_methods = len(methods)
    group_gap = 1.0
    group_width = 0.8
    violin_width = group_width / n_methods

    fig, ax = plt.subplots(figsize=(max(12, n_seg * 2.0), 5.5))

    for i, seg in enumerate(segments):
        group_center = i * group_gap
        for j, method in enumerate(methods):
            rec = next(
                (r for r in records if r["segment"] == seg and r["method"] == method),
                None,
            )
            if rec is None:
                continue
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
    ax.set_ylabel("BPM error (estimated - GT)")
    ax.set_title(title or "Window-level BPM error by segment")
    ax.grid(True, axis="y", alpha=0.25)

    legend_handles = _violin_legend_with_stats([
        plt.Line2D([0], [0], color=colors[m], lw=6, alpha=0.65, label=m) for m in methods
    ])
    ax.legend(handles=legend_handles, loc="upper right", fontsize=7)
    plt.tight_layout()

    fig_path = None
    if save and figures_dir is not None:
        fig_path = Path(figures_dir) / filename
        _save_chfusion_figure(fig, fig_path)
        print(f"✓ 小提琴图已保存: {fig_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


# Variable colors for Part-1 violin (same order as CS_SIGNAL_VARIABLES)
PART1_VARIABLE_COLORS = {
    "amplitudes": "coral",
    "remote_amplitudes": "steelblue",
    "local_amplitudes": "seagreen",
    "phases": "mediumpurple",
}


def _violin_legend_with_stats(method_handles: List) -> List:
    """Append mean / median / GT reference entries to a violin plot legend."""
    import matplotlib.pyplot as plt

    stat_handles = [
        plt.Line2D([0], [0], color="black", lw=1.5, label="Mean (window BPM error)"),
        plt.Line2D(
            [0], [0], color="white", lw=2, markeredgecolor="black",
            markeredgewidth=0.8, label="Median (window BPM error)",
        ),
        plt.Line2D([0], [0], color="black", lw=1.2, ls="--", label="Ground truth (y=0)"),
    ]
    return list(method_handles) + stat_handles


def _draw_grouped_violins_on_ax(
    ax,
    records: List[dict],
    *,
    segments: Sequence[str],
    group_ids: Sequence[str],
    group_field: str,
    colors: Dict[str, str],
    gt_by_seg: Dict[str, float],
    title: Optional[str] = None,
    show_ylabel: bool = True,
) -> None:
    """Draw segment-grouped violins on an existing axes.

    Layout: one x-axis group per script segment; within each group, one violin
    per entry in ``group_ids`` (either 4 variables or 4 methods). Shared by
    Part 1/2 and overview multi-panel figures.
    """
    n_groups = len(group_ids)
    group_gap = 1.0
    group_width = 0.85
    violin_width = group_width / max(n_groups, 1)

    for i, seg in enumerate(segments):
        group_center = i * group_gap
        for j, gid in enumerate(group_ids):
            rec = next(
                (r for r in records if r["segment"] == seg and r[group_field] == gid),
                None,
            )
            if rec is None:
                continue
            errors = rec["signed_errors"]
            pos = group_center + (j - (n_groups - 1) / 2) * violin_width
            color = colors.get(gid, "gray")

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
    ax.set_xticks([i * group_gap for i in range(len(segments))])
    ax.set_xticklabels([f"{seg}\nGT={gt_by_seg[seg]:.2f}" for seg in segments], fontsize=8)
    if show_ylabel:
        ax.set_ylabel("BPM error (estimated - GT)")
    if title:
        ax.set_title(title, fontsize=10)
    ax.grid(True, axis="y", alpha=0.25)


def _part2_matrix_stats(part2: dict) -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Aggregate Part-2 results into 4×4 mean/std matrices (%).

    Rows follow ``CS_SIGNAL_VARIABLES`` order; columns follow ``FUSION_METHOD_LABELS``.
    Mean = average segment-level relative BPM error; std = std of those segment errors.
    """
    variables = [v[0] for v in CS_SIGNAL_VARIABLES if v[0] in part2]
    n_var, n_meth = len(variables), len(FUSION_METHOD_LABELS)
    means = np.full((n_var, n_meth), np.nan)
    stds = np.full((n_var, n_meth), np.nan)
    for i, variable in enumerate(variables):
        for j, (_label, key, _color) in enumerate(FUSION_METHOD_LABELS):
            stats = _overall_rel_error(part2[variable]["results"], key)
            means[i, j] = stats["mean_rel_err_pct"]
            stds[i, j] = stats["std_rel_err_pct"]
    return variables, means, stds


def plot_overview_matrix_bars(
    benchmark: dict,
    *,
    figures_dir=None,
    filename: str = "",
    show: bool = True,
    save: bool = True,
):
    """Grouped bar chart summarising all 16 variable×method combos.

    X-axis: four CS observables. Four bars per group = Single / Uniform / FFT+q_peak / FFT+q_energy_peak.
    Height = mean segment relative BPM error (%); error bars = ±std across segments.
    """
    import matplotlib.pyplot as plt

    if not filename:
        filename = _chfusion_figure_name("chfusion_overview_4x3_mean_error_bars")

    part2 = benchmark["part2"]
    variables, means, stds = _part2_matrix_stats(part2)
    if not variables:
        print("⚠️  无 Part-2 数据，跳过 4×3 柱状图")
        return None

    var_labels = [_variable_plot_label(v) for v in variables]
    n_var = len(variables)
    n_meth = len(FUSION_METHOD_LABELS)
    x = np.arange(n_var)
    bar_width = 0.13
    offsets = (np.arange(n_meth) - (n_meth - 1) / 2) * bar_width

    fig, ax = plt.subplots(figsize=(max(10, n_var * 2.5), 5.5))
    for j, (label, _key, color) in enumerate(FUSION_METHOD_LABELS):
        ax.bar(
            x + offsets[j],
            means[:, j],
            bar_width,
            yerr=stds[:, j],
            capsize=3,
            label=label,
            color=color,
            edgecolor="black",
            alpha=0.85,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(var_labels, rotation=15, ha="right")
    ax.set_ylabel("Mean relative BPM error (%)")
    ax.set_title("Overview: 4 variables × 6 methods (segment mean ± window std)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, axis="y", alpha=0.25)
    plt.tight_layout()

    if save and figures_dir is not None:
        fig_path = Path(figures_dir) / filename
        _save_chfusion_figure(fig, fig_path)
        print(f"✓ 4×3 柱状图已保存: {fig_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def plot_overview_matrix_heatmap(
    benchmark: dict,
    *,
    figures_dir=None,
    filename: str = "",
    show: bool = True,
    save: bool = True,
):
    """Heatmap of mean relative BPM error (%) for the 4×4 benchmark matrix.

    Darker/warmer cells = higher error. Cell text shows numeric mean err%.
    Same underlying stats as ``plot_overview_matrix_bars``.
    """
    import matplotlib.pyplot as plt

    if not filename:
        filename = _chfusion_figure_name("chfusion_overview_4x3_heatmap")

    part2 = benchmark["part2"]
    variables, means, _stds = _part2_matrix_stats(part2)
    if not variables:
        print("⚠️  无 Part-2 数据，跳过 4×3 热力图")
        return None

    var_labels = [_variable_plot_label(v) for v in variables]
    meth_labels = [m[0] for m in FUSION_METHOD_LABELS]

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    im = ax.imshow(means, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(np.arange(len(meth_labels)))
    ax.set_yticks(np.arange(len(var_labels)))
    ax.set_xticklabels(meth_labels)
    ax.set_yticklabels(var_labels)
    ax.set_title("Mean relative BPM error (%) — 4 variables × 6 methods")

    for i in range(means.shape[0]):
        for j in range(means.shape[1]):
            val = means[i, j]
            if np.isfinite(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=9, color="black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Mean rel. error (%)")
    plt.tight_layout()

    if save and figures_dir is not None:
        fig_path = Path(figures_dir) / filename
        _save_chfusion_figure(fig, fig_path)
        print(f"✓ 4×3 热力图已保存: {fig_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def plot_overview_violins_by_method(
    benchmark: dict,
    *,
    figures_dir=None,
    filename: str = "",
    show: bool = True,
    save: bool = True,
):
    """N×1 violin panels: variable comparison under each fusion method (vertical stack).

    Extends Part 1 (which only shows Single) to Uniform, FFT+q_peak, FFT+q_energy_peak.
    Each panel layout matches ``plot_part1_variable_violins`` (4 colours per segment).
    """
    import matplotlib.pyplot as plt

    if not filename:
        filename = _chfusion_figure_name("chfusion_overview_4x3_violins_by_method")

    records = collect_part2_variable_method_errors(benchmark["part2"])
    if not records:
        print("⚠️  无 Part-2 误差数据，跳过按方法分组小提琴图")
        return None

    segments = sorted({r["segment"] for r in records})
    gt_by_seg = {r["segment"]: r["bpm_gt"] for r in records}
    variables = [v[0] for v in CS_SIGNAL_VARIABLES if any(r["variable"] == v[0] for r in records)]
    var_colors = {v: PART1_VARIABLE_COLORS.get(v, "gray") for v in variables}
    var_legend_labels = {v: _variable_plot_label(v) for v in variables}

    n_methods = len(FUSION_METHOD_LABELS)
    panel_h = 5.5
    fig, axes = plt.subplots(
        n_methods,
        1,
        figsize=(max(12, len(segments) * 2.2), panel_h * n_methods),
        sharey=True,
    )
    axes_flat = np.atleast_1d(axes).flatten()

    for ax, (method_label, _key, _color) in zip(axes_flat, FUSION_METHOD_LABELS):
        subset = [r for r in records if r["method"] == method_label]
        _draw_grouped_violins_on_ax(
            ax,
            subset,
            segments=segments,
            group_ids=variables,
            group_field="variable",
            colors=var_colors,
            gt_by_seg=gt_by_seg,
            title=f"Method: {method_label}",
            show_ylabel=(ax is axes_flat[0]),
        )

    legend_handles = _violin_legend_with_stats([
        plt.Line2D(
            [0], [0],
            color=var_colors[v],
            lw=6, alpha=0.65,
            label=var_legend_labels[v],
        )
        for v in variables
    ])
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=min(4, len(variables) + 3),
        fontsize=7,
    )
    fig.suptitle(
        "Overview: variable comparison per method (window-level signed BPM error)",
        y=0.995,
        fontsize=11,
    )
    plt.tight_layout(rect=[0, 0.04, 1, 0.98])

    if save and figures_dir is not None:
        fig_path = Path(figures_dir) / filename
        _save_chfusion_figure(fig, fig_path, bbox_inches="tight")
        print(f"✓ 按方法分组小提琴图已保存: {fig_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def plot_overview_violins_by_variable(
    benchmark: dict,
    *,
    figures_dir=None,
    filename: str = "",
    show: bool = True,
    save: bool = True,
):
    """N×1 violin panels: method comparison for each CS observable (vertical stack).

    Merges the four Part-2 per-variable figures into one overview page.
    Each panel layout matches ``plot_bpm_error_violins`` (3 colours per segment).
    """
    import matplotlib.pyplot as plt

    if not filename:
        filename = _chfusion_figure_name("chfusion_overview_4x3_violins_by_variable")

    records = collect_part2_variable_method_errors(benchmark["part2"])
    if not records:
        print("⚠️  无 Part-2 误差数据，跳过按变量分组小提琴图")
        return None

    segments = sorted({r["segment"] for r in records})
    gt_by_seg = {r["segment"]: r["bpm_gt"] for r in records}
    variables = [v[0] for v in CS_SIGNAL_VARIABLES if any(r["variable"] == v[0] for r in records)]
    method_labels = [m[0] for m in FUSION_METHOD_LABELS]
    method_colors = {m[0]: m[2] for m in FUSION_METHOD_LABELS}

    n_var = len(variables)
    panel_h = 5.5
    fig, axes = plt.subplots(
        n_var,
        1,
        figsize=(max(12, len(segments) * 2.2), panel_h * n_var),
        sharey=True,
    )
    axes_flat = np.atleast_1d(axes).flatten()

    for ax, variable in zip(axes_flat, variables):
        subset = [r for r in records if r["variable"] == variable]
        _draw_grouped_violins_on_ax(
            ax,
            subset,
            segments=segments,
            group_ids=method_labels,
            group_field="method",
            colors=method_colors,
            gt_by_seg=gt_by_seg,
            title=_variable_plot_label(variable),
            show_ylabel=(ax is axes_flat[0]),
        )

    legend_handles = _violin_legend_with_stats([
        plt.Line2D([0], [0], color=method_colors[m], lw=6, alpha=0.65, label=m)
        for m in method_labels
    ])
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=len(method_labels) + 3,
        fontsize=7,
    )
    fig.suptitle(
        "Overview: method comparison per variable (window-level signed BPM error)",
        y=0.995,
        fontsize=11,
    )
    plt.tight_layout(rect=[0, 0.04, 1, 0.98])

    if save and figures_dir is not None:
        fig_path = Path(figures_dir) / filename
        _save_chfusion_figure(fig, fig_path, bbox_inches="tight")
        print(f"✓ 按变量分组小提琴图已保存: {fig_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def plot_part1_variable_violins(
    part1: dict,
    *,
    figures_dir=None,
    filename: str = "",
    show: bool = True,
    save: bool = True,
):
    """Part-1 violin: per segment, compare four variables (Single method). y=0 is GT."""
    import matplotlib.pyplot as plt

    if not filename:
        filename = _chfusion_figure_name("chfusion_part1_variable_violins")

    records = collect_part1_variable_errors(part1)
    if not records:
        print("⚠️  Part-1 无可用误差数据，跳过小提琴图")
        return None

    segments = sorted({r["segment"] for r in records})
    gt_by_seg = {r["segment"]: r["bpm_gt"] for r in records}
    variables = [v[0] for v in CS_SIGNAL_VARIABLES if any(r["variable"] == v[0] for r in records)]

    n_seg = len(segments)
    n_var = len(variables)
    group_gap = 1.0
    group_width = 0.85
    violin_width = group_width / max(n_var, 1)

    fig, ax = plt.subplots(figsize=(max(12, n_seg * 2.0), 5.5))

    for i, seg in enumerate(segments):
        group_center = i * group_gap
        for j, variable in enumerate(variables):
            rec = next(
                (r for r in records if r["segment"] == seg and r["variable"] == variable),
                None,
            )
            if rec is None:
                continue
            errors = rec["signed_errors"]
            pos = group_center + (j - (n_var - 1) / 2) * violin_width
            color = PART1_VARIABLE_COLORS.get(variable, "gray")

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
                parts["cmedians"].set_color("white")
            elif len(errors) == 1:
                ax.scatter([pos], errors, color=color, edgecolors="black", s=40, zorder=4)

    ax.axhline(0.0, color="black", linestyle="--", linewidth=1.2, alpha=0.75)
    ax.set_xticks([i * group_gap for i in range(n_seg)])
    ax.set_xticklabels([f"{seg}\nGT={gt_by_seg[seg]:.2f}" for seg in segments])
    ax.set_ylabel("BPM error (estimated - GT)")
    ax.set_title("Part 1: variable comparison (Single / max-energy channel)")
    ax.grid(True, axis="y", alpha=0.25)

    legend_handles = _violin_legend_with_stats([
        plt.Line2D(
            [0], [0],
            color=PART1_VARIABLE_COLORS.get(v, "gray"),
            lw=6, alpha=0.65,
            label=_variable_plot_label(v),
        )
        for v in variables
    ])
    ax.legend(handles=legend_handles, loc="upper right", fontsize=7)
    plt.tight_layout()

    fig_path = None
    if save and figures_dir is not None:
        fig_path = Path(figures_dir) / filename
        _save_chfusion_figure(fig, fig_path)
        print(f"✓ Part-1 小提琴图已保存: {fig_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def plot_benchmark_violins(
    benchmark: dict,
    *,
    figures_dir=None,
    show: bool = True,
    save: bool = True,
) -> List[Path]:
    """Generate all benchmark violin/overview figures from a ``run_chfusion_benchmark`` result.

    Order: Part-1 variable violins → Part-2 per-variable method violins (×4) →
    4×4 overview (bars, heatmap, violins-by-method, violins-by-variable).

    Returns list of saved PDF paths when ``save=True``.
    """
    saved: List[Path] = []

    part1_name = _chfusion_figure_name("chfusion_part1_variable_violins")
    plot_part1_variable_violins(
        benchmark["part1"],
        figures_dir=figures_dir,
        filename=part1_name,
        show=show,
        save=save,
    )
    if save and figures_dir is not None:
        saved.append(Path(figures_dir) / part1_name)

    for variable, block in benchmark["part2"].items():
        slug = variable.replace("_", "-")
        part2_name = _chfusion_figure_name(f"chfusion_part2_{slug}_violins")
        plot_bpm_error_violins(
            block["results"],
            method_labels=FUSION_METHOD_LABELS,
            figures_dir=figures_dir,
            filename=part2_name,
            title=f"Part 2: {_variable_plot_label(variable)} - methods comparison",
            show=show,
            save=save,
        )
        if save and figures_dir is not None:
            saved.append(Path(figures_dir) / part2_name)

    overview_specs = [
        ("chfusion_overview_4x3_mean_error_bars", plot_overview_matrix_bars),
        ("chfusion_overview_4x3_heatmap", plot_overview_matrix_heatmap),
        ("chfusion_overview_4x3_violins_by_method", plot_overview_violins_by_method),
        ("chfusion_overview_4x3_violins_by_variable", plot_overview_violins_by_variable),
    ]
    for stem, plot_fn in overview_specs:
        fname = _chfusion_figure_name(stem)
        plot_fn(benchmark, figures_dir=figures_dir, filename=fname, show=show, save=save)
        if save and figures_dir is not None:
            saved.append(Path(figures_dir) / fname)

    return saved
