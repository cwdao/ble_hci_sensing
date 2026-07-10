"""Three WiFi paper baselines (Fan 2024 / Yu 2021 / Zhuo 2023) vs HKH GT.

Each method produces a fused respiratory waveform per window; we report BPM
error and waveform RMSE against the HKH bandpass reference.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy.signal import hilbert

from ble_analysis.ble_hkh_validation import (
    _ble_window_time_range,
    _hkh_window_bandpass,
    compute_hkh_gt_per_window,
    summarize_bpm_vs_hkh,
)
from ble_analysis.chfusion import ChFusionConfig, _energy_ratio
from ble_analysis.coherent_mrc import _window_b2_bpms
from ble_analysis.pca_svd import PcaSvdConfig
from ble_analysis.pca_vmd import (
    VmdParams,
    ZHUO2023_VARIANT_SPECS,
    estimate_pca_vmd_window_bpm,
)
from ble_analysis.segments import BreathMetricParams, _sliding_window_indices
from ble_analysis.voting_fusion import MODAL_VOTING_VARIABLES
from ble_analysis.waveform_metrics import window_rmse_against_reference
from ble_analysis.wifi_mrc import (
    _collect_modal_window_matrix,
    _fuse_modal_waveforms_equal,
    _fuse_modal_waveforms_pca3,
    compute_mrc_weights,
    estimate_bpm_from_waveform,
    mrc_pca_fusion,
)

PAPER_METHOD_SPECS: Tuple[Tuple[str, str, str], ...] = (
    ("Fan 2024 η-linear (best modal)", "fan_eta_linear", "Fan2024"),
    ("Fan 2024 η-equal waveform avg", "fan_eta_equal_wf", "Fan2024"),
    ("Fan 2024 Hilbert equal wf", "fan_hilbert_equal", "Fan2024"),
    ("Yu 2021 MRC-PCA √η (best modal)", "mrc_pca_eta_sqrt", "Yu2021"),
    ("Yu 2021 MRC-PCA η-equal PCA3→1", "mrc_pca_eta_equal_pca", "Yu2021"),
    ("Zhuo 2023 Z1 PCA→PCA→VMD→Peak", "z1", "Zhuo2023"),
    ("Zhuo 2023 Z1-FFT PCA→PCA→VMD→FFT", "z1_fft", "Zhuo2023"),
    ("Zhuo 2023 Z1-no-VMD PCA→PCA→Peak", "z1_no_vmd", "Zhuo2023"),
    ("B2-D Two-level Hilbert-MRC (ref)", "b2_d_two_level", "B2"),
    ("B2-A0 PCA sign (ref)", "b2_a0_pca_sign", "B2"),
)

B2_METHOD_CONFIGS: Dict[str, dict] = {
    "b2_a0_pca_sign": {
        "phase_method": "pca_sign",
        "weight_mode": "eta_rho",
        "use_two_level": False,
        "use_modal_phase_align": False,
        "min_coherence": 0.0,
    },
    "b2_d_two_level": {
        "phase_method": "hilbert",
        "weight_mode": "coherence_gated",
        "use_two_level": True,
        "use_modal_phase_align": True,
        "modal_weight_mode": "eta_coherence",
        "min_coherence": 0.2,
    },
}


def _fan_modal_waveforms(
    multichannel_by_var: Dict,
    seg_name: str,
    ch_list,
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    weight_mode: str,
) -> Tuple[Dict[str, np.ndarray], Dict[str, float]]:
    modal_waveforms: Dict[str, np.ndarray] = {}
    modal_etas: Dict[str, float] = {}
    for variable in MODAL_VOTING_VARIABLES:
        ref_seg = multichannel_by_var[variable].get(seg_name)
        if ref_seg is None:
            continue
        ch_map = ref_seg["channels"]
        x_mat, eta, rho = _collect_modal_window_matrix(
            ch_list, ch_map, variable, st, end, fs, cfg
        )
        g = compute_mrc_weights(eta, mode=weight_mode, rho=rho, eps=cfg.eps)
        y = np.sum(g[:, None] * x_mat, axis=0)
        modal_waveforms[variable] = y
        modal_etas[variable] = _energy_ratio(y, fs, cfg)
    return modal_waveforms, modal_etas


def _mrc_pca_modal_waveforms(
    multichannel_by_var: Dict,
    seg_name: str,
    ch_list,
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    *,
    weight_mode: str = "sqrt",
    use_pca_sign: bool = True,
    pca_top_k: int = 36,
) -> Tuple[Dict[str, np.ndarray], Dict[str, float]]:
    modal_waveforms: Dict[str, np.ndarray] = {}
    modal_etas: Dict[str, float] = {}
    for variable in MODAL_VOTING_VARIABLES:
        ref_seg = multichannel_by_var[variable].get(seg_name)
        if ref_seg is None:
            continue
        ch_map = ref_seg["channels"]
        x_mat, eta, rho = _collect_modal_window_matrix(
            ch_list, ch_map, variable, st, end, fs, cfg
        )
        y, _info = mrc_pca_fusion(
            x_mat,
            eta,
            weight_mode=weight_mode,
            use_pca_sign=use_pca_sign,
            top_k=pca_top_k,
            rho=rho,
            eps=cfg.eps,
        )
        modal_waveforms[variable] = y
        modal_etas[variable] = _energy_ratio(y, fs, cfg)
    return modal_waveforms, modal_etas


def _fan_hilbert_modal_waveforms(
    multichannel_by_var: Dict,
    seg_name: str,
    ch_list,
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    weight_mode: str = "linear",
) -> Dict[str, np.ndarray]:
    modal_waveforms: Dict[str, np.ndarray] = {}
    for variable in MODAL_VOTING_VARIABLES:
        ref_seg = multichannel_by_var[variable].get(seg_name)
        if ref_seg is None:
            continue
        ch_map = ref_seg["channels"]
        x_mat, eta, rho = _collect_modal_window_matrix(
            ch_list, ch_map, variable, st, end, fs, cfg
        )
        analytic = hilbert(x_mat, axis=1)
        phases = np.angle(analytic)
        ref_idx = int(np.argmax(eta))
        ref_phase = phases[ref_idx]
        x_aligned = np.zeros_like(x_mat)
        for i in range(x_mat.shape[0]):
            delta_phi = np.mean(ref_phase - phases[i])
            x_aligned[i] = x_mat[i] * np.cos(delta_phi)
        g = compute_mrc_weights(eta, mode=weight_mode, rho=rho, eps=cfg.eps)
        modal_waveforms[variable] = np.sum(g[:, None] * x_aligned, axis=0)
    return modal_waveforms


def _window_waveform_fan_linear_best(
    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg
) -> Optional[np.ndarray]:
    wfs, etas = _fan_modal_waveforms(
        multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, "linear"
    )
    if not wfs:
        return None
    return wfs[max(etas, key=etas.get)]


def _window_waveform_fan_equal_wf(
    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg
) -> Optional[np.ndarray]:
    wfs, _etas = _fan_modal_waveforms(
        multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, "linear"
    )
    return _fuse_modal_waveforms_equal(wfs)


def _window_waveform_fan_hilbert(
    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg
) -> Optional[np.ndarray]:
    wfs = _fan_hilbert_modal_waveforms(
        multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, "linear"
    )
    return _fuse_modal_waveforms_equal(wfs)


def _window_waveform_mrc_pca_sqrt_best(
    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, pca_top_k
) -> Optional[np.ndarray]:
    wfs, etas = _mrc_pca_modal_waveforms(
        multichannel_by_var, seg_name, ch_list, st, end, fs, cfg,
        weight_mode="sqrt", use_pca_sign=True, pca_top_k=pca_top_k,
    )
    if not wfs:
        return None
    return wfs[max(etas, key=etas.get)]


def _window_waveform_mrc_pca_pca3(
    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, pca_top_k
) -> Optional[np.ndarray]:
    wfs, _etas = _mrc_pca_modal_waveforms(
        multichannel_by_var, seg_name, ch_list, st, end, fs, cfg,
        weight_mode="sqrt", use_pca_sign=True, pca_top_k=pca_top_k,
    )
    return _fuse_modal_waveforms_pca3(wfs)


def _window_waveform_zhuo(
    multichannel_by_var,
    seg_name,
    ch_list,
    st,
    end,
    fs,
    cfg,
    pca_cfg,
    variant_key: str,
    vmd_params: VmdParams,
) -> Tuple[Optional[float], Optional[np.ndarray]]:
    spec = ZHUO2023_VARIANT_SPECS[variant_key]
    bpm, info = estimate_pca_vmd_window_bpm(
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
    wf = info.get("waveform")
    if wf is None:
        return None, None
    return float(bpm), np.asarray(wf, dtype=float)


def _window_result_from_waveform(
    y_final: Optional[np.ndarray], fs: float, cfg: ChFusionConfig,
) -> Tuple[Optional[float], Optional[np.ndarray]]:
    if y_final is None or len(y_final) < 4:
        return None, None
    bpm, _, _, _ = estimate_bpm_from_waveform(y_final, fs, cfg=cfg)
    return float(bpm), y_final


def _window_result_b2(
    multichannel_by_var,
    seg_name,
    ch_list,
    st,
    end,
    fs,
    cfg,
    method_key: str,
    pca_top_k: int,
) -> Tuple[Optional[float], Optional[np.ndarray]]:
    mc = B2_METHOD_CONFIGS[method_key]
    bpm, _diag, y_final = _window_b2_bpms(
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
    if y_final is None or len(y_final) < 4:
        return None, None
    return float(bpm), y_final


def _build_waveform_runner(
    method_key: str,
    *,
    pca_cfg: PcaSvdConfig,
    vmd_params: VmdParams,
    pca_top_k: int = 36,
) -> Callable:
    def _run(multichannel_by_var, seg_name, ch_list, st, end, fs, cfg):
        if method_key == "fan_eta_linear":
            return _window_result_from_waveform(
                _window_waveform_fan_linear_best(
                    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg
                ),
                fs, cfg,
            )
        if method_key == "fan_eta_equal_wf":
            return _window_result_from_waveform(
                _window_waveform_fan_equal_wf(
                    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg
                ),
                fs, cfg,
            )
        if method_key == "fan_hilbert_equal":
            return _window_result_from_waveform(
                _window_waveform_fan_hilbert(
                    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg
                ),
                fs, cfg,
            )
        if method_key == "mrc_pca_eta_sqrt":
            return _window_result_from_waveform(
                _window_waveform_mrc_pca_sqrt_best(
                    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, pca_top_k
                ),
                fs, cfg,
            )
        if method_key == "mrc_pca_eta_equal_pca":
            return _window_result_from_waveform(
                _window_waveform_mrc_pca_pca3(
                    multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, pca_top_k
                ),
                fs, cfg,
            )
        if method_key.startswith("z1"):
            variant_map = {
                "z1": "Z1",
                "z1_fft": "Z1_fft",
                "z1_no_vmd": "Z1_no_vmd",
            }
            return _window_waveform_zhuo(
                multichannel_by_var, seg_name, ch_list, st, end, fs, cfg,
                pca_cfg, variant_map[method_key], vmd_params,
            )
        if method_key.startswith("b2_"):
            return _window_result_b2(
                multichannel_by_var, seg_name, ch_list, st, end, fs, cfg,
                method_key, pca_top_k,
            )
        raise ValueError(f"Unknown paper method: {method_key}")

    return _run


def validate_paper_method_against_hkh(
    multichannel_by_var: Dict,
    seg_name: str,
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    cs_t_host: np.ndarray,
    *,
    method_key: str,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    pca_cfg: Optional[PcaSvdConfig] = None,
    vmd_params: Optional[VmdParams] = None,
    pca_top_k: int = 36,
    verbose: bool = False,
) -> Optional[dict]:
    """Window-level BPM + RMSE for one paper/B2 waveform method."""
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    pca_cfg = pca_cfg or PcaSvdConfig(signal_key="bandpass_filtered")
    vmd_params = vmd_params or VmdParams(K=3, alpha=3000.0)

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

    bpm_hkh, _, _fs_ble, fs_hkh = compute_hkh_gt_per_window(
        hkh_bandpass, hkh_t_host, cs_t_host, multichannel_by_var, seg_name,
        config=cfg, metric_params=mp,
    )

    runner = _build_waveform_runner(
        method_key, pca_cfg=pca_cfg, vmd_params=vmd_params, pca_top_k=pca_top_k,
    )
    starts = _sliding_window_indices(ref_len, win_len, step_len)

    bpm_est_list: List[float] = []
    rmse_list: List[float] = []

    for st in starts:
        end = st + win_len
        bpm, y_final = runner(multichannel_by_var, seg_name, ch_list, st, end, fs, cfg)
        if y_final is None or bpm is None or not np.isfinite(bpm):
            bpm_est_list.append(float("nan"))
            rmse_list.append(float("nan"))
            continue

        bpm_est_list.append(float(bpm))

        t0, t1 = _ble_window_time_range(cs_t_host, st, end, fs, win_len)
        hkh_win = _hkh_window_bandpass(hkh_bandpass, hkh_t_host, t0, t1 + 1)
        if len(hkh_win) < 4:
            rmse_list.append(float("nan"))
        else:
            rmse_val, _sign = window_rmse_against_reference(y_final, hkh_win)
            rmse_list.append(float(rmse_val))

    bpm_est = np.asarray(bpm_est_list, dtype=float)
    rmse_arr = np.asarray(rmse_list, dtype=float)
    summary = summarize_bpm_vs_hkh(bpm_est, bpm_hkh)
    summary["rmse_mean"] = float(np.nanmean(rmse_arr))
    summary["rmse_std"] = float(np.nanstd(rmse_arr))
    summary["n_valid_rmse"] = int(np.sum(np.isfinite(rmse_arr)))

    label = next((lbl for lbl, key, _ in PAPER_METHOD_SPECS if key == method_key), method_key)
    paper = next((p for lbl, key, p in PAPER_METHOD_SPECS if key == method_key), "")

    if verbose:
        print(
            f"  {label:<42} BPM {summary['bpm_mean_abs_err']:.2f}±{summary['bpm_std_abs_err']:.2f}"
            f" | RMSE {summary['rmse_mean']:.3f}±{summary['rmse_std']:.3f}"
        )

    return {
        "label": label,
        "paper": paper,
        "method_key": method_key,
        "bpm_est": bpm_est,
        "bpm_hkh_gt": bpm_hkh,
        "rmse": rmse_arr,
        "summary": summary,
    }


def run_hkh_paper_baselines_benchmark(
    multichannel_by_var: Dict,
    seg_name: str,
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    cs_t_host: np.ndarray,
    *,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    method_keys: Optional[Tuple[str, ...]] = None,
    verbose: bool = True,
) -> dict:
    """Benchmark all paper waveform methods (+ B2 refs) on one HKH segment."""
    keys = method_keys or tuple(k for _l, k, _p in PAPER_METHOD_SPECS)
    results: Dict[str, dict] = {}

    for key in keys:
        try:
            row = validate_paper_method_against_hkh(
                multichannel_by_var,
                seg_name,
                hkh_bandpass,
                hkh_t_host,
                cs_t_host,
                method_key=key,
                config=config,
                metric_params=metric_params,
                verbose=verbose,
            )
        except Exception as exc:
            if verbose:
                print(f"  skip {key}: {exc}")
            continue
        if row is None:
            if verbose:
                print(f"  skip {key}: no result")
            continue
        results[key] = row

    by_bpm = sorted(results.values(), key=lambda r: r["summary"]["bpm_mean_abs_err"])
    by_rmse = sorted(results.values(), key=lambda r: r["summary"]["rmse_mean"])

    def _leaderboard_row(r: dict, rank: int) -> dict:
        s = r["summary"]
        return {
            "rank": rank,
            "label": r["label"],
            "paper": r["paper"],
            "method_key": r["method_key"],
            **s,
        }

    return {
        "segment": seg_name,
        "methods": results,
        "leaderboard_bpm": [_leaderboard_row(r, i + 1) for i, r in enumerate(by_bpm)],
        "leaderboard_rmse": [_leaderboard_row(r, i + 1) for i, r in enumerate(by_rmse)],
    }
