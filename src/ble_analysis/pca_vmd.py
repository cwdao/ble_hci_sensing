"""Zhuo 2023 PCA-VMD external baseline for BLE CS breathing BPM estimation.

Implements two-level PCA + optional VMD + peak/FFT BPM from
``docs/plans/zhuo2023_pca_vmd_baseline_plan.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import find_peaks

from ble_analysis.chfusion import (
    ChFusionConfig,
    Plan2Config,
    _energy_ratio,
    _overall_rel_error,
    _seg_bpm_stats,
    run_multichannel_segment_filtering,
)
from ble_analysis.pca_svd import (
    MODAL_PCA_VARIABLES,
    PcaSvdConfig,
    build_channel_data_matrix,
    extract_breath_waveform_pca,
    run_pca_modal_fusion,
)
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.systematic_fusion import estimate_systematic_fusion_segment
from ble_analysis.voting_fusion import (
    MODAL_VOTING_VARIABLES,
    VotingConfig,
    run_voting_fusion_benchmark,
)
from ble_analysis.wifi_mrc import estimate_bpm_from_waveform

BpmMethod = Literal["peak", "fft"]
VmdSelection = Literal["max_variance"]

ZHUO2023_VARIANT_SPECS: Dict[str, dict] = {
    "Z1": {
        "use_projection": False,
        "use_hilbert_align": False,
        "use_vmd": True,
        "bpm_method": "peak",
    },
    "Z1_fft": {
        "use_projection": False,
        "use_hilbert_align": False,
        "use_vmd": True,
        "bpm_method": "fft",
    },
    "Z1_no_vmd": {
        "use_projection": False,
        "use_hilbert_align": False,
        "use_vmd": False,
        "bpm_method": "peak",
    },
    "Z1_no_vmd_fft": {
        "use_projection": False,
        "use_hilbert_align": False,
        "use_vmd": False,
        "bpm_method": "fft",
    },
    "Z1_proj": {
        "use_projection": True,
        "use_hilbert_align": False,
        "use_vmd": True,
        "bpm_method": "peak",
    },
    "Z1_hilbert": {
        "use_projection": False,
        "use_hilbert_align": True,
        "use_vmd": True,
        "bpm_method": "peak",
    },
}

ZHUO2023_METHOD_SPECS: Tuple[Tuple[str, str, str], ...] = (
    ("B0 Single Remote", "b0_single_remote", "steelblue"),
    ("B1 Uniform Remote", "b1_uniform_remote", "seagreen"),
    ("Modal top2 equal", "b2_modal_top2_equal", "mediumpurple"),
    ("B1 Vote→Equal modal", "b1_vote_modal_equal", "olive"),
    ("PCA modal equal", "pca_modal_equal_ch_uniform", "teal"),
    ("Z1 PCA→PCA→VMD→Peak", "z1", "darkred"),
    ("Z1-no-VMD PCA→PCA→Peak", "z1_no_vmd", "indianred"),
    ("Z1-FFT PCA→PCA→VMD→FFT", "z1_fft", "crimson"),
    ("Z1-no-VMD-FFT PCA→PCA→FFT", "z1_no_vmd_fft", "salmon"),
    ("Z1-proj Proj→PCA→VMD→Peak", "z1_proj", "maroon"),
    ("Z1-Hilbert PCA→Hilbert→VMD→Peak", "z1_hilbert", "firebrick"),
)

ZHUO2023_VARIANT_KEYS: Tuple[str, ...] = tuple(
    key for _label, key, _color in ZHUO2023_METHOD_SPECS if key.startswith("z1")
)

__all__ = [
    "ZHUO2023_METHOD_SPECS",
    "ZHUO2023_VARIANT_SPECS",
    "ZHUO2023_VARIANT_KEYS",
    "VmdParams",
    "project_complex_candidates",
    "project_all_tones",
    "vmd_decompose_and_select",
    "estimate_bpm_from_peaks",
    "estimate_pca_vmd_window_bpm",
    "estimate_zhuo2023_pca_vmd_segment",
    "run_vmd_param_ablation",
    "run_zhuo2023_pca_vmd_benchmark",
    "compute_zhuo2023_cross_domain",
    "plot_zhuo2023_pca_vmd_figures",
]


@dataclass(frozen=True)
class VmdParams:
    K: int = 3
    alpha: float = 3000.0
    tau: float = 0.0
    DC: int = 0
    init: int = 1
    tol: float = 1e-7


def project_complex_candidates(
    amplitude: np.ndarray,
    phase: np.ndarray,
    fs: float,
    *,
    num_angles: int = 100,
    breath_band: Tuple[float, float] = (0.1, 0.35),
    w_bnr: float = 0.5,
    w_var: float = 0.5,
    cfg: Optional[ChFusionConfig] = None,
) -> Tuple[np.ndarray, float, dict]:
    """Complex-plane projection + BNR/variance joint selection for one tone."""
    cfg = cfg or ChFusionConfig()
    amp = np.asarray(amplitude, dtype=float)
    ph = np.asarray(phase, dtype=float)
    n = min(len(amp), len(ph))
    if n < 4:
        return amp[:n], 0.0, {"bnrs": [], "vars": [], "scores": []}

    amp = amp[:n]
    ph = ph[:n]
    i_sig = amp * np.cos(ph)
    q_sig = amp * np.sin(ph)
    thetas = np.linspace(0.0, np.pi, num_angles, endpoint=False)
    bnrs: List[float] = []
    vars_: List[float] = []
    signals: List[np.ndarray] = []
    for theta in thetas:
        x = i_sig * np.cos(theta) + q_sig * np.sin(theta)
        bnrs.append(_energy_ratio(x, fs, cfg))
        vars_.append(float(np.var(x)))
        signals.append(x)

    bnr_arr = np.asarray(bnrs, dtype=float)
    var_arr = np.asarray(vars_, dtype=float)
    bnr_norm = (bnr_arr - np.min(bnr_arr)) / (np.max(bnr_arr) - np.min(bnr_arr) + cfg.eps)
    var_norm = (var_arr - np.min(var_arr)) / (np.max(var_arr) - np.min(var_arr) + cfg.eps)
    scores = w_bnr * bnr_norm + w_var * var_norm
    best_idx = int(np.argmax(scores))
    return (
        signals[best_idx],
        float(thetas[best_idx]),
        {
            "bnrs": bnrs,
            "vars": vars_,
            "scores": scores.tolist(),
            "best_theta": float(thetas[best_idx]),
        },
    )


def project_all_tones(
    ch_map_amp: Dict[Any, Dict[str, Any]],
    ch_map_phase: Dict[Any, Dict[str, Any]],
    ch_list: Sequence[Any],
    st: int,
    end: int,
    amp_variable: str,
    fs: float,
    *,
    cfg: Optional[ChFusionConfig] = None,
) -> np.ndarray:
    """Project all tones for one amplitude variable; returns M×N matrix."""
    cols: List[np.ndarray] = []
    m = end - st
    for ch in ch_list:
        amp_proc = ch_map_amp.get(ch)
        ph_proc = ch_map_phase.get(ch)
        if amp_proc is None or ph_proc is None:
            continue
        amp_sig = amp_proc[amp_variable].get("bandpass_filtered")
        ph_sig = ph_proc["phases"].get("bandpass_filtered")
        if amp_sig is None or ph_sig is None or len(amp_sig) < end or len(ph_sig) < end:
            continue
        projected, _, _ = project_complex_candidates(
            amp_sig[st:end], ph_sig[st:end], fs, cfg=cfg
        )
        if len(projected) == m:
            cols.append(projected)
    if not cols:
        return np.empty((m, 0))
    return np.column_stack(cols)


def vmd_decompose_and_select(
    waveform: np.ndarray,
    fs: float,
    *,
    params: Optional[VmdParams] = None,
    selection: VmdSelection = "max_variance",
    breath_band: Tuple[float, float] = (0.1, 0.35),
) -> Tuple[np.ndarray, np.ndarray, int, dict]:
    """VMD decomposition + modal selection."""
    from vmdpy import VMD

    p = params or VmdParams()
    sig = np.asarray(waveform, dtype=float)
    if len(sig) < 4 or not np.all(np.isfinite(sig)):
        empty = np.array([], dtype=float)
        return sig, empty.reshape(0, len(sig)), 0, {
            "variances": [],
            "center_freqs": [],
            "converged": False,
            "n_iter": 0,
        }

    sig = sig - np.mean(sig)
    try:
        modes, _modes_hat, omega = VMD(
            sig,
            p.alpha,
            p.tau,
            p.K,
            p.DC,
            p.init,
            p.tol,
        )
    except Exception as exc:
        return sig, np.empty((0, len(sig))), 0, {
            "variances": [],
            "center_freqs": [],
            "converged": False,
            "n_iter": 0,
            "error": str(exc),
        }

    modes = np.asarray(modes, dtype=float)
    if modes.ndim == 1:
        modes = modes.reshape(1, -1)
    variances = [float(np.var(modes[k])) for k in range(modes.shape[0])]
    center_freqs = []
    if omega is not None and len(omega) > 0:
        center_freqs = (np.asarray(omega[-1], dtype=float) * fs / (2 * np.pi)).tolist()

    if selection == "max_variance":
        selected_idx = int(np.argmax(variances))
    else:
        selected_idx = 0

    info = {
        "variances": variances,
        "center_freqs": center_freqs,
        "converged": True,
        "n_iter": len(omega) if omega is not None else 0,
        "selected_center_freq_hz": center_freqs[selected_idx] if center_freqs else float("nan"),
    }
    return modes[selected_idx], modes, selected_idx, info


def estimate_bpm_from_peaks(
    waveform: np.ndarray,
    fs: float,
    *,
    min_breath_interval_sec: float = 1.2,
    max_breath_interval_sec: float = 10.0,
    prominence: Optional[float] = None,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """Peak detection + pseudo-peak rejection → BPM."""
    sig = np.asarray(waveform, dtype=float)
    if len(sig) < 4 or not np.all(np.isfinite(sig)):
        return float("nan"), np.array([], dtype=int), np.array([], dtype=float)

    min_distance = max(1, int(round(fs * min_breath_interval_sec)))
    if prominence is None:
        prominence = 0.1 * float(np.std(sig))
    peaks, _props = find_peaks(sig, distance=min_distance, prominence=prominence)
    if len(peaks) < 2:
        return float("nan"), peaks, np.array([], dtype=float)

    intervals = np.diff(peaks) / fs
    valid_mask = (intervals >= min_breath_interval_sec) & (
        intervals <= max_breath_interval_sec
    )
    valid_intervals = intervals[valid_mask]
    if valid_intervals.size == 0:
        return float("nan"), peaks, valid_intervals
    return float(60.0 / np.mean(valid_intervals)), peaks, valid_intervals


def _align_pc1_signs(waveforms: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    if not waveforms:
        return waveforms
    ref_key = max(waveforms, key=lambda k: float(np.var(waveforms[k])))
    ref = waveforms[ref_key]
    out = {ref_key: ref.copy()}
    for key, wf in waveforms.items():
        if key == ref_key:
            continue
        n = min(len(ref), len(wf))
        corr = float(np.dot(ref[:n], wf[:n]))
        out[key] = -wf if corr < 0 else wf.copy()
    return out


def _hilbert_align_waveforms(waveforms: List[np.ndarray]) -> List[np.ndarray]:
    from scipy.signal import hilbert

    if len(waveforms) < 2:
        return waveforms
    vars_ = [float(np.var(w)) for w in waveforms]
    ref_idx = int(np.argmax(vars_))
    ref_phase = np.angle(hilbert(waveforms[ref_idx]))
    aligned: List[np.ndarray] = []
    for i, wf in enumerate(waveforms):
        if i == ref_idx:
            aligned.append(wf.copy())
            continue
        phase = np.angle(hilbert(wf))
        delta = np.mean(ref_phase - phase)
        aligned.append(wf * np.cos(delta))
    return aligned


def _estimate_bpm_from_waveform(
    waveform: np.ndarray,
    fs: float,
    bpm_method: BpmMethod,
    cfg: ChFusionConfig,
) -> float:
    if bpm_method == "fft":
        bpm, _, _, _ = estimate_bpm_from_waveform(waveform, fs, cfg=cfg)
        return bpm
    bpm, _, _ = estimate_bpm_from_peaks(waveform, fs)
    return bpm


def _first_level_pc1_waveforms(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    ch_list: Sequence[Any],
    st: int,
    end: int,
    *,
    use_projection: bool,
    pca_cfg: PcaSvdConfig,
) -> Tuple[Dict[str, np.ndarray], dict]:
    pc1_map: Dict[str, np.ndarray] = {}
    info: dict = {"pc1_variance_ratios": {}}
    phase_seg = multichannel_by_var["phases"].get(seg_name)
    phase_ch_map = phase_seg["channels"] if phase_seg is not None else {}

    for variable in MODAL_PCA_VARIABLES:
        ref_seg = multichannel_by_var[variable].get(seg_name)
        if ref_seg is None:
            continue
        ch_map = ref_seg["channels"]
        if use_projection and variable in ("remote_amplitudes", "local_amplitudes"):
            x_mat = project_all_tones(
                ch_map,
                phase_ch_map,
                ch_list,
                st,
                end,
                variable,
                ref_seg["metadata"]["sampling_rate"],
            )
        else:
            x_mat, _used = build_channel_data_matrix(
                ch_map,
                variable,
                list(ch_list),
                st,
                end,
                signal_key="bandpass_filtered",
            )
        if x_mat.shape[1] < pca_cfg.min_channels:
            continue
        wf, pca_info = extract_breath_waveform_pca(x_mat, pca_cfg, seg_name)
        pc1_map[variable] = wf
        info["pc1_variance_ratios"][variable] = pca_info.get("pc1_variance_ratio", np.nan)

    return pc1_map, info


def estimate_pca_vmd_window_bpm(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    ch_list: Sequence[Any],
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    pca_cfg: PcaSvdConfig,
    *,
    vmd_params: Optional[VmdParams] = None,
    use_projection: bool = False,
    use_hilbert_align: bool = False,
    use_vmd: bool = True,
    bpm_method: BpmMethod = "peak",
) -> Tuple[float, dict]:
    """Single-window two-level PCA (+ optional VMD) → BPM."""
    pc1_map, info = _first_level_pc1_waveforms(
        multichannel_by_var,
        seg_name,
        ch_list,
        st,
        end,
        use_projection=use_projection,
        pca_cfg=pca_cfg,
    )
    if len(pc1_map) < 2:
        return float("nan"), info

    aligned = _align_pc1_signs(pc1_map)
    wf_list = [aligned[v] for v in MODAL_PCA_VARIABLES if v in aligned]
    if use_hilbert_align:
        wf_list = _hilbert_align_waveforms(wf_list)

    min_len = min(len(w) for w in wf_list)
    x_modal = np.column_stack([w[:min_len] for w in wf_list])
    modal_pca_cfg = PcaSvdConfig(
        normalize=pca_cfg.normalize,
        min_channels=2,
        min_variance_ratio=pca_cfg.min_variance_ratio,
        eps=pca_cfg.eps,
        channel_weight=pca_cfg.channel_weight,
        signal_key=pca_cfg.signal_key,
        breath_freq_low=pca_cfg.breath_freq_low,
        breath_freq_high=pca_cfg.breath_freq_high,
        total_freq_low=pca_cfg.total_freq_low,
        total_freq_high=pca_cfg.total_freq_high,
    )
    y_pca, pca2_info = extract_breath_waveform_pca(x_modal, modal_pca_cfg, seg_name)
    info["pc2_variance_ratio"] = pca2_info.get("pc1_variance_ratio", np.nan)

    if use_vmd:
        y_final, _modes, _idx, vmd_info = vmd_decompose_and_select(
            y_pca, fs, params=vmd_params
        )
        info["vmd_info"] = vmd_info
        if not vmd_info.get("converged", False):
            y_final = y_pca
    else:
        y_final = y_pca
        info["vmd_info"] = {"converged": False, "skipped": True}

    bpm = _estimate_bpm_from_waveform(y_final, fs, bpm_method, cfg)
    return bpm, info


def estimate_zhuo2023_pca_vmd_segment(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    *,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    pca_cfg: Optional[PcaSvdConfig] = None,
    variants: Sequence[str] = ("Z1", "Z1_no_vmd"),
    vmd_params: Optional[VmdParams] = None,
    verbose: bool = False,
) -> Optional[dict]:
    """Per-segment multi-variant PCA-VMD BPM estimation."""
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    pca_cfg = pca_cfg or PcaSvdConfig(signal_key="bandpass_filtered")

    ref_seg = multichannel_by_var["phases"].get(seg_name)
    if ref_seg is None:
        return None
    metadata = ref_seg["metadata"]
    if metadata.get("segment_type") == "apnea":
        return None

    bpm_gt = metadata.get("bpm_gt")
    fs = metadata["sampling_rate"]
    ch_map = ref_seg["channels"]
    if not ch_map:
        return None

    ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
    seg_var = ref_seg.get("variable", "phases")
    ref_len = max(len(ch_map[c][seg_var]["bandpass_filtered"]) for c in ch_list)
    win_len = int(round(mp.window_length_sec * fs))
    step_len = int(round(mp.step_length_sec * fs))
    if ref_len < win_len:
        if verbose:
            print(f"⚠️  {seg_name}: length {ref_len} < window {win_len}, skip")
        return None

    starts = _sliding_window_indices(ref_len, win_len, step_len)
    variant_bpms: Dict[str, List[float]] = {v: [] for v in variants}

    for st in starts:
        end = st + win_len
        for variant in variants:
            spec = ZHUO2023_VARIANT_SPECS[variant]
            bpm, _info = estimate_pca_vmd_window_bpm(
                multichannel_by_var,
                seg_name,
                ch_list,
                st,
                end,
                fs,
                cfg,
                pca_cfg,
                vmd_params=vmd_params,
                use_projection=spec["use_projection"],
                use_hilbert_align=spec["use_hilbert_align"],
                use_vmd=spec["use_vmd"],
                bpm_method=spec["bpm_method"],
            )
            variant_bpms[variant].append(bpm)

    row = {
        "segment": seg_name,
        "bpm_gt": bpm_gt,
        "metadata": metadata,
    }
    for variant in variants:
        key = variant.lower()
        row[key] = _seg_bpm_stats(np.asarray(variant_bpms[variant]), bpm_gt, len(starts))
    return row


def run_vmd_param_ablation(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    *,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    pca_cfg: Optional[PcaSvdConfig] = None,
    k_values: Sequence[int] = (2, 3, 4),
    alpha_values: Sequence[float] = (500, 1000, 2000, 3000, 5000),
) -> List[dict]:
    """Grid search VMD (K, α) on one scenario; rank by Z1 cross-segment mean err."""
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    pca_cfg = pca_cfg or PcaSvdConfig(signal_key="bandpass_filtered")
    rows: List[dict] = []

    for k in k_values:
        for alpha in alpha_values:
            merged: Dict[str, Optional[dict]] = {}
            for seg_name in sorted(multichannel_by_var["phases"].keys()):
                row = estimate_zhuo2023_pca_vmd_segment(
                    multichannel_by_var,
                    seg_name,
                    config=cfg,
                    metric_params=mp,
                    pca_cfg=pca_cfg,
                    variants=("Z1",),
                    vmd_params=VmdParams(K=k, alpha=alpha),
                    verbose=False,
                )
                merged[seg_name] = row
            stats = _overall_rel_error(merged, "z1")
            rows.append(
                {
                    "K": k,
                    "alpha": alpha,
                    "mean_rel_err_pct": stats["mean_rel_err_pct"],
                    "std_rel_err_pct": stats["std_rel_err_pct"],
                    "n_segments": stats["n_segments"],
                }
            )

    rows.sort(key=lambda r: r["mean_rel_err_pct"])
    return rows


def _merge_baseline_results(
    merged: Dict[str, Optional[dict]],
    baseline_partial: Dict[str, Optional[dict]],
    method_key: str,
    baseline_key: str,
) -> None:
    for seg_name, row in baseline_partial.items():
        if row is None:
            merged.setdefault(seg_name, None)
            continue
        block = row.get(baseline_key)
        if block is None:
            continue
        if merged.get(seg_name) is None:
            merged[seg_name] = {
                "segment": seg_name,
                "bpm_gt": row.get("bpm_gt"),
                "metadata": row.get("metadata", {}),
            }
        merged[seg_name][method_key] = block


def run_zhuo2023_pca_vmd_benchmark(
    frames,
    segment_config: Dict[str, dict],
    *,
    filter_params: Optional[FilterParams] = None,
    metric_params: Optional[BreathMetricParams] = None,
    config: Optional[ChFusionConfig] = None,
    plan2_config: Optional[Plan2Config] = None,
    pca_cfg: Optional[PcaSvdConfig] = None,
    variants: Sequence[str] = tuple(ZHUO2023_VARIANT_SPECS.keys()),
    vmd_params: Optional[VmdParams] = None,
    verbose: bool = True,
    cache_dir: Optional[str] = None,
    multichannel_by_var: Optional[Dict[str, Dict[str, Optional[dict]]]] = None,
) -> dict:
    """Run Zhuo2023 PCA-VMD variants plus required baselines for one scenario."""
    cfg = config or ChFusionConfig()
    fp = filter_params or FilterParams()
    mp = metric_params or BreathMetricParams()
    p2 = plan2_config or Plan2Config(channel_metric="energy_ratio")
    pca_cfg = pca_cfg or PcaSvdConfig(signal_key="bandpass_filtered")
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")
    vmd_params = vmd_params or VmdParams()

    if multichannel_by_var is None:
        multichannel_by_var = {}
        for variable in MODAL_VOTING_VARIABLES:
            mc, _fs = run_multichannel_segment_filtering(
                frames,
                segment_config,
                variable=variable,
                filter_params=fp,
                verbose=verbose,
                cache_dir=cache_dir,
            )
            multichannel_by_var[variable] = mc
    else:
        multichannel_by_var = dict(multichannel_by_var)

    merged: Dict[str, Optional[dict]] = {}
    seg_names = sorted(multichannel_by_var["phases"].keys())

    if verbose:
        print("\n--- Zhuo2023 PCA-VMD variants ---")
    for seg_name in seg_names:
        row = estimate_zhuo2023_pca_vmd_segment(
            multichannel_by_var,
            seg_name,
            config=cfg,
            metric_params=mp,
            pca_cfg=pca_cfg,
            variants=variants,
            vmd_params=vmd_params,
            verbose=verbose,
        )
        if row is None:
            merged[seg_name] = None
            continue
        merged[seg_name] = {
            "segment": seg_name,
            "bpm_gt": row["bpm_gt"],
            "metadata": row["metadata"],
        }
        for variant in variants:
            merged[seg_name][variant.lower()] = row[variant.lower()]
        if verbose and "z1" in row:
            stats = row["z1"]
            rel = stats.get("bpm_rel_err", np.nan)
            if rel is not None and np.isfinite(rel):
                print(f"  {seg_name} Z1 {rel * 100:.2f}%")
            else:
                print(f"  {seg_name} Z1 —")

    if verbose:
        print("\n--- Baselines ---")
    voting_bench = run_voting_fusion_benchmark(
        frames,
        segment_config,
        filter_params=fp,
        metric_params=mp,
        config=cfg,
        plan2_config=p2,
        verbose=False,
        cache_dir=cache_dir,
        multichannel_by_var=multichannel_by_var,
    )
    _merge_baseline_results(merged, voting_bench["results"], "b0_single_remote", "b0_single_remote")
    _merge_baseline_results(merged, voting_bench["results"], "b1_uniform_remote", "b1_uniform_remote")
    _merge_baseline_results(
        merged, voting_bench["results"], "b2_modal_top2_equal", "b2_modal_top2_equal"
    )

    b1_partial: Dict[str, Optional[dict]] = {}
    for seg_name in seg_names:
        b1_partial[seg_name] = estimate_systematic_fusion_segment(
            multichannel_by_var,
            seg_name,
            channel_strategy="vote",
            modal_strategy="equal",
            config=cfg,
            metric_params=mp,
            vcfg=vcfg,
            persistence_masks=None,
            verbose=False,
        )
    _merge_baseline_results(
        merged, b1_partial, "b1_vote_modal_equal", "b1_vote_modal_equal"
    )

    pca_partial = run_pca_modal_fusion(
        multichannel_by_var,
        channel_weight="uniform",
        modal_weight="equal",
        metric_params=mp,
        pca_svd_config=pca_cfg,
        verbose=False,
    )
    _merge_baseline_results(
        merged, pca_partial, "pca_modal_equal_ch_uniform", "pca_modal_equal_ch_uniform"
    )

    if verbose:
        for label, key, _ in ZHUO2023_METHOD_SPECS:
            stats = _overall_rel_error(merged, key)
            if np.isfinite(stats["mean_rel_err_pct"]):
                print(f"✓ [{key}] {label} | mean err {stats['mean_rel_err_pct']:.2f}%")

    return {
        "results": merged,
        "multichannel_by_var": multichannel_by_var,
        "method_specs": ZHUO2023_METHOD_SPECS,
        "vmd_params": vmd_params,
    }


def compute_zhuo2023_cross_domain(
    results_by_scenario: Dict[str, dict],
) -> List[dict]:
    """Aggregate cross-domain leaderboard rows."""
    agg: List[dict] = []
    for label, key, color in ZHUO2023_METHOD_SPECS:
        per_scenario: Dict[str, float] = {}
        for sid, bench in results_by_scenario.items():
            stats = _overall_rel_error(bench["results"], key)
            if np.isfinite(stats["mean_rel_err_pct"]):
                per_scenario[sid] = stats["mean_rel_err_pct"]
        if not per_scenario:
            continue
        means = list(per_scenario.values())
        agg.append(
            {
                "label": label,
                "method_key": key,
                "color": color,
                "cross_domain_mean": float(np.mean(means)),
                "cross_domain_std": float(np.std(means, ddof=1)) if len(means) > 1 else 0.0,
                "n_scenarios": len(means),
                "per_scenario": per_scenario,
            }
        )
    agg.sort(key=lambda r: r["cross_domain_mean"])
    for rank, row in enumerate(agg, start=1):
        row["rank"] = rank
    return agg


def plot_zhuo2023_pca_vmd_figures(
    results_by_scenario: Dict[str, dict],
    cross_domain: List[dict],
    *,
    figures_dir,
    scenario_ids: Sequence[str],
    show: bool = False,
    save: bool = True,
) -> dict:
    """Generate leaderboard, cross-domain summary, and ablation figures."""
    import matplotlib.pyplot as plt

    figures_dir = Path(figures_dir)
    paths: dict = {}

    fig, ax = plt.subplots(figsize=(12, 8))
    labels = [r["label"] for r in cross_domain]
    means = [r["cross_domain_mean"] for r in cross_domain]
    colors = [r["color"] for r in cross_domain]
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, means, color=colors, alpha=0.85)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Cross-domain mean BPM err %")
    ax.set_title("Zhuo2023 PCA-VMD — cross-domain leaderboard")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    lb_path = figures_dir / "zhuo2023_pca_vmd_leaderboard.png"
    if save:
        fig.savefig(lb_path, dpi=150, bbox_inches="tight")
    paths["leaderboard"] = lb_path
    if not show:
        plt.close(fig)

    fig, axes = plt.subplots(1, len(scenario_ids), figsize=(5 * len(scenario_ids), 6), sharey=True)
    if len(scenario_ids) == 1:
        axes = [axes]
    for ax_i, sid in zip(axes, scenario_ids):
        bench = results_by_scenario[sid]
        vals = []
        lbls = []
        cols = []
        for row in cross_domain:
            stats = _overall_rel_error(bench["results"], row["method_key"])
            if np.isfinite(stats["mean_rel_err_pct"]):
                vals.append(stats["mean_rel_err_pct"])
                lbls.append(row["label"])
                cols.append(row["color"])
        order = np.argsort(vals)
        vals = [vals[i] for i in order]
        lbls = [lbls[i] for i in order]
        cols = [cols[i] for i in order]
        ax_i.barh(np.arange(len(vals)), vals, color=cols, alpha=0.85)
        ax_i.set_yticks(np.arange(len(lbls)))
        ax_i.set_yticklabels(lbls, fontsize=6)
        ax_i.invert_yaxis()
        ax_i.set_title(sid)
        ax_i.set_xlabel("Mean BPM err %")
        ax_i.grid(True, axis="x", alpha=0.3)
    fig.suptitle("Zhuo2023 PCA-VMD — per-scenario comparison", y=1.02)
    fig.tight_layout()
    summary_path = figures_dir / "zhuo2023_pca_vmd_cross_domain_summary.png"
    if save:
        fig.savefig(summary_path, dpi=150, bbox_inches="tight")
    paths["cross_domain_summary"] = summary_path
    if not show:
        plt.close(fig)

    ablation_keys = [
        ("B1 Vote→Equal", "b1_vote_modal_equal", "olive"),
        ("Z1-no-VMD", "z1_no_vmd", "indianred"),
        ("Z1", "z1", "darkred"),
        ("Z1-FFT", "z1_fft", "crimson"),
        ("Z1-proj", "z1_proj", "maroon"),
        ("Z1-Hilbert", "z1_hilbert", "firebrick"),
    ]
    fig_a, ax_a = plt.subplots(figsize=(9, 5))
    x = np.arange(len(scenario_ids))
    width = 0.13
    for i, (label, key, color) in enumerate(ablation_keys):
        ys = []
        for sid in scenario_ids:
            stats = _overall_rel_error(results_by_scenario[sid]["results"], key)
            ys.append(stats["mean_rel_err_pct"])
        ax_a.bar(x + i * width, ys, width, label=label, color=color, alpha=0.85)
    ax_a.set_xticks(x + width * (len(ablation_keys) - 1) / 2)
    ax_a.set_xticklabels([s.replace("cs_", "") for s in scenario_ids])
    ax_a.set_ylabel("Mean BPM err %")
    ax_a.set_title("Zhuo2023 PCA-VMD ablation by scenario")
    ax_a.legend(fontsize=7, loc="upper right")
    ax_a.grid(True, axis="y", alpha=0.3)
    fig_a.tight_layout()
    ablation_path = figures_dir / "zhuo2023_pca_vmd_ablation.png"
    if save:
        fig_a.savefig(ablation_path, dpi=150, bbox_inches="tight")
    paths["ablation"] = ablation_path
    if not show:
        plt.close(fig_a)

    return paths
