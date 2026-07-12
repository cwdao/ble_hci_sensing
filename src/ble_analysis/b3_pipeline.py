"""B3 unified pipeline: channel-level Voting BPM + two-level Hilbert-MRC waveform.

Implements ``docs/plans/b3_unified_pipeline_voting_bpm_plan.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ble_analysis.ble_hkh_validation import (
    _ble_window_time_range,
    _hkh_window_bandpass,
    _resolve_hkh_fs,
    compute_hkh_gt_per_window,
    summarize_bpm_vs_hkh,
)
from ble_analysis.chfusion import (
    ChFusionConfig,
    _energy_ratio,
    _next_pow2,
    _parabolic_peak_freq,
)
from ble_analysis.coherent_mrc import (
    coherent_mrc_fuse_modals,
    coherent_mrc_fuse_tones,
    estimate_bpm_from_waveform_multi,
)
from ble_analysis.segments import BreathMetricParams, _sliding_window_indices
from ble_analysis.systematic_fusion import (
    _collect_channel_window_data,
    _weighted_spectrum_average,
    modal_fusion_from_spectra,
    per_modal_uniform_spectrum,
    per_modal_voting_spectrum,
)
from ble_analysis.voting_fusion import (
    MODAL_VOTING_VARIABLES,
    VotingConfig,
    _vote_weights,
    vote_bpm_weighted_histogram,
)
from ble_analysis.waveform_metrics import window_rmse_against_reference
from ble_analysis.wifi_mrc import _collect_modal_window_matrix

MODAL_SHORT: Dict[str, str] = {
    "remote_amplitudes": "remote",
    "local_amplitudes": "local",
    "phases": "phase",
}


@dataclass(frozen=True)
class B3VariantConfig:
    """B3 Simplified pipeline configuration with optional ablation toggles."""

    use_voting: bool = True
    use_eta_rho_weights: bool = True
    use_multi_modal: bool = True
    use_two_level_hilbert: bool = True


B3_SIMPLIFIED_CONFIG = B3VariantConfig()

B3_VARIANT_SPECS: Tuple[Tuple[str, str, B3VariantConfig], ...] = (
    (
        "B3 Simplified",
        "b3_b1_equal",
        B3_SIMPLIFIED_CONFIG,
    ),
    (
        "A1 Single best-η",
        "a1_single_best_eta",
        B3VariantConfig(use_voting=False),
    ),
    (
        "A3 Remote only",
        "a3_remote_only",
        B3VariantConfig(use_multi_modal=False),
    ),
    (
        "A4 Equal spectral fusion",
        "a4_equal_spectral",
        B3VariantConfig(use_two_level_hilbert=False),
    ),
    (
        "A5 Equal-weight voting",
        "a5_equal_voting",
        B3VariantConfig(use_eta_rho_weights=False),
    ),
)

EXTERNAL_BASELINE_SPECS: Tuple[Tuple[str, str], ...] = (
    ("B1 Vote→Equal", "b1_vote_modal_equal"),
    ("B2-D Two-level Hilbert-MRC", "b2_d_two_level"),
    ("Zhuo Z1-no-VMD", "z1_no_vmd"),
)

__all__ = [
    "B3VariantConfig",
    "B3_SIMPLIFIED_CONFIG",
    "B3_VARIANT_SPECS",
    "EXTERNAL_BASELINE_SPECS",
    "MODAL_SHORT",
    "estimate_b3_window",
    "validate_b3_variant_against_hkh",
    "validate_b1_vote_equal_against_hkh",
    "compute_b3_cross_domain_summary",
]


def _active_modal_variables(use_multi_modal: bool) -> Tuple[str, ...]:
    if use_multi_modal:
        return MODAL_VOTING_VARIABLES
    return ("remote_amplitudes",)


def _voting_strategy(use_eta_rho_weights: bool) -> str:
    return "eta_rho_weighted" if use_eta_rho_weights else "simple"


def _bpm_per_tone_from_spectra(
    spectra: Sequence[np.ndarray],
    band_freqs: np.ndarray,
    cfg: ChFusionConfig,
) -> np.ndarray:
    bpms: List[float] = []
    for spec in spectra:
        spec_arr = np.asarray(spec, dtype=float)
        if spec_arr.size == 0 or float(np.sum(spec_arr)) <= cfg.eps:
            bpms.append(float("nan"))
            continue
        k = int(np.argmax(spec_arr))
        f_peak = _parabolic_peak_freq(band_freqs, spec_arr, k, cfg.eps)
        bpms.append(float(60.0 * f_peak))
    return np.asarray(bpms, dtype=float)


def _compute_per_tone_spectra(
    ch_list: Sequence[Any],
    ch_map: dict,
    variable: str,
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    nfft: int,
    band_mask: np.ndarray,
    band_freqs: np.ndarray,
    hann: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return η, ρ, per-tone spectra [N, F], BPM-from-spectrum [N]."""
    eta, rho, _bpm_wave, spectra_list = _collect_channel_window_data(
        ch_list,
        ch_map,
        variable,
        st,
        end,
        fs,
        cfg,
        nfft,
        band_mask,
        band_freqs,
        hann,
    )
    spectra = np.vstack(spectra_list) if spectra_list else np.zeros((0, len(band_freqs)))
    bpm_per_tone = _bpm_per_tone_from_spectra(spectra_list, band_freqs, cfg)
    return eta, rho, spectra, bpm_per_tone


def _vote_bpm_per_modal(
    eta: np.ndarray,
    rho: np.ndarray,
    bpm_per_tone: np.ndarray,
    spectra: np.ndarray,
    *,
    cfg: ChFusionConfig,
    vcfg: VotingConfig,
    strategy: str,
) -> dict:
    weights = _vote_weights(eta, rho, strategy, cfg.eps)
    mask = np.isfinite(bpm_per_tone) & np.isfinite(weights) & (weights > 0)
    if not np.any(mask):
        zero = np.zeros(spectra.shape[1] if spectra.ndim == 2 and spectra.size else 1)
        return {
            "voted_bpm": float("nan"),
            "confidence": 0.0,
            "weighted_spectrum": zero,
            "weights": weights,
            "bpm_per_tone": bpm_per_tone,
        }

    voted_bpm, _conf_flag, win_mass = vote_bpm_weighted_histogram(
        bpm_per_tone[mask],
        weights[mask],
        vcfg,
    )
    total_w = float(np.sum(weights[mask]))
    confidence = win_mass / total_w if total_w > 0 else 0.0
    spec_weights = weights * mask.astype(float)
    band_len = spectra.shape[1] if spectra.ndim == 2 and spectra.size else 1
    band_stub = np.zeros(band_len, dtype=float)
    weighted_spectrum = _weighted_spectrum_average(
        spectra, spec_weights, band_stub, cfg.eps
    )

    return {
        "voted_bpm": float(voted_bpm),
        "confidence": float(confidence),
        "weighted_spectrum": weighted_spectrum,
        "weights": weights,
        "bpm_per_tone": bpm_per_tone,
        "winning_mass": float(win_mass),
    }


def _single_best_eta_bpm(
    eta: np.ndarray,
    rho: np.ndarray,
    bpm_per_tone: np.ndarray,
    *,
    use_eta_rho_weights: bool,
) -> Tuple[float, float]:
    quality = eta * np.clip(rho, 0.0, None) if use_eta_rho_weights else eta
    mask = np.isfinite(quality) & np.isfinite(bpm_per_tone)
    if not np.any(mask):
        return float("nan"), 0.0
    idx = int(np.argmax(np.where(mask, quality, -np.inf)))
    conf = float(quality[idx] / (np.sum(quality[mask]) + 1e-12))
    return float(bpm_per_tone[idx]), conf


def estimate_b3_window(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    ch_list: Sequence[Any],
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    *,
    variant: Optional[B3VariantConfig] = None,
    vcfg: Optional[VotingConfig] = None,
    nfft: Optional[int] = None,
    band_freqs: Optional[np.ndarray] = None,
    band_mask: Optional[np.ndarray] = None,
    hann: Optional[np.ndarray] = None,
) -> dict:
    """Run one sliding-window B3 pipeline (or ablation variant)."""
    variant = variant or B3VariantConfig()
    vcfg = vcfg or VotingConfig(voting_strategy="eta_rho_weighted")
    win_len = end - st
    nfft = nfft or (cfg.nfft or _next_pow2(4 * win_len))
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)
    band_mask = band_mask if band_mask is not None else (
        (freqs >= cfg.breath_freq_low) & (freqs <= cfg.breath_freq_high)
    )
    band_freqs = band_freqs if band_freqs is not None else freqs[band_mask]
    hann = hann if hann is not None else np.hanning(win_len)

    strategy = _voting_strategy(variant.use_eta_rho_weights)
    active_vars = _active_modal_variables(variant.use_multi_modal)
    modal_results: Dict[str, dict] = {}
    modal_spectra: Dict[str, np.ndarray] = {}
    modal_scores: Dict[str, float] = {}
    modal_waveforms: Dict[str, np.ndarray] = {}
    modal_etas: Dict[str, float] = {}

    for variable in active_vars:
        ref_seg = multichannel_by_var.get(variable, {}).get(seg_name)
        if ref_seg is None:
            continue
        ch_map = ref_seg["channels"]
        short = MODAL_SHORT[variable]

        eta, rho, spectra, bpm_per_tone = _compute_per_tone_spectra(
            ch_list,
            ch_map,
            variable,
            st,
            end,
            fs,
            cfg,
            nfft,
            band_mask,
            band_freqs,
            hann,
        )

        if variant.use_voting:
            modal_results[short] = _vote_bpm_per_modal(
                eta,
                rho,
                bpm_per_tone,
                spectra,
                cfg=cfg,
                vcfg=vcfg,
                strategy=strategy,
            )
        else:
            bpm_single, conf = _single_best_eta_bpm(
                eta, rho, bpm_per_tone, use_eta_rho_weights=variant.use_eta_rho_weights
            )
            modal_results[short] = {
                "voted_bpm": bpm_single,
                "confidence": conf,
                "weights": _vote_weights(eta, rho, strategy, cfg.eps),
                "bpm_per_tone": bpm_per_tone,
            }

        if variant.use_two_level_hilbert:
            X, eta_mrc, rho_mrc = _collect_modal_window_matrix(
                ch_list, ch_map, variable, st, end, fs, cfg
            )
            y_modal, tone_info = coherent_mrc_fuse_tones(
                X,
                eta_mrc,
                rho_mrc,
                phase_method="hilbert",
                weight_mode="coherence_gated",
                fs=fs,
                min_coherence=0.0,
            )
            modal_waveforms[short] = y_modal
            modal_etas[short] = _energy_ratio(y_modal, fs, cfg)
            modal_results[short]["tone_info"] = tone_info
        else:
            if variant.use_voting:
                spec, _bpm, info = per_modal_voting_spectrum(
                    ch_list,
                    ch_map,
                    variable,
                    st,
                    end,
                    fs,
                    cfg,
                    vcfg,
                    nfft,
                    band_mask,
                    band_freqs,
                    hann,
                )
            else:
                spec, _bpm, info = per_modal_uniform_spectrum(
                    ch_list,
                    ch_map,
                    variable,
                    st,
                    end,
                    fs,
                    cfg,
                    nfft,
                    band_mask,
                    band_freqs,
                    hann,
                )
            modal_spectra[short] = spec
            modal_scores[short] = float(info.get("score", info.get("conf", 0.0)))

    if not modal_results:
        return {
            "bpm": float("nan"),
            "bpm_wf": float("nan"),
            "waveform": None,
            "diagnostics": {},
        }

    spectra_for_modal: Dict[str, np.ndarray] = {}
    scores_for_modal: Dict[str, float] = {}
    for short, res in modal_results.items():
        ws = res.get("weighted_spectrum")
        if ws is None:
            continue
        ws_arr = np.asarray(ws, dtype=float)
        if ws_arr.size != len(band_freqs):
            continue
        spectra_for_modal[short] = ws_arr
        scores_for_modal[short] = float(res.get("confidence", 0.0))

    if variant.use_two_level_hilbert:
        if spectra_for_modal:
            bpm_vote, _sel = modal_fusion_from_spectra(
                spectra_for_modal,
                scores_for_modal,
                "equal",
                band_freqs,
                cfg,
            )
        else:
            bpm_vote = float("nan")
    else:
        bpm_vote, _sel = modal_fusion_from_spectra(
            modal_spectra,
            modal_scores,
            "equal",
            band_freqs,
            cfg,
        )

    y_final: Optional[np.ndarray] = None
    bpm_wf = float("nan")

    if variant.use_two_level_hilbert and modal_waveforms:
        if len(modal_waveforms) == 1:
            y_final = next(iter(modal_waveforms.values()))
            modal_info = {"phase_aligned": False, "modal_keys": list(modal_waveforms.keys())}
        else:
            y_final, modal_info = coherent_mrc_fuse_modals(
                modal_waveforms,
                modal_etas,
                modal_weight_mode="eta_coherence",
                use_phase_align=True,
            )
        bpm_out = estimate_bpm_from_waveform_multi(y_final, fs, cfg=cfg)
        bpm_wf = float(bpm_out.get("bpm_psd", float("nan")))

    primary_bpm = float(bpm_vote)

    return {
        "bpm": primary_bpm,
        "bpm_vote": float(bpm_vote),
        "bpm_wf": bpm_wf,
        "waveform": y_final,
        "diagnostics": {
            "modal_results": modal_results,
            "modal_etas": modal_etas,
            "variant": variant,
        },
    }


def validate_b3_variant_against_hkh(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    cs_t_host: np.ndarray,
    *,
    variant_key: str = "b3_full",
    variant: Optional[B3VariantConfig] = None,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    fs_hkh_override: Optional[float] = None,
    verbose: bool = False,
) -> Optional[dict]:
    """Window-level BPM + RMSE for one B3 variant vs HKH GT."""
    if variant is None:
        matched = next((v for _l, k, v in B3_VARIANT_SPECS if k == variant_key), None)
        if matched is None:
            raise ValueError(f"Unknown B3 variant: {variant_key}")
        variant = matched

    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")

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

    nfft = cfg.nfft or _next_pow2(4 * win_len)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)
    band_mask = (freqs >= cfg.breath_freq_low) & (freqs <= cfg.breath_freq_high)
    band_freqs = freqs[band_mask]
    hann = np.hanning(win_len)

    bpm_est: List[float] = []
    bpm_vote: List[float] = []
    bpm_wf: List[float] = []
    bpm_hkh: List[float] = []
    rmse_list: List[float] = []

    for st in starts:
        end = st + win_len
        out = estimate_b3_window(
            multichannel_by_var,
            seg_name,
            ch_list,
            st,
            end,
            fs,
            cfg,
            variant=variant,
            vcfg=vcfg,
            nfft=nfft,
            band_freqs=band_freqs,
            band_mask=band_mask,
            hann=hann,
        )
        bpm_est.append(float(out["bpm"]))
        bpm_vote.append(float(out.get("bpm_vote", float("nan"))))
        bpm_wf.append(float(out.get("bpm_wf", float("nan"))))

        t0, t1 = _ble_window_time_range(cs_t_host, st, end, fs, win_len)
        hkh_win = _hkh_window_bandpass(hkh_bandpass, hkh_t_host, t0, t1 + 1)
        if len(hkh_win) < 4:
            bpm_hkh.append(float("nan"))
            rmse_list.append(float("nan"))
            continue

        from ble_analysis.wifi_mrc import estimate_bpm_from_waveform

        bpm_gt, _, _, _ = estimate_bpm_from_waveform(hkh_win, fs_hkh, cfg=cfg)
        bpm_hkh.append(float(bpm_gt))

        y_final = out.get("waveform")
        if y_final is None or len(y_final) < 4:
            rmse_list.append(float("nan"))
        else:
            rmse_val, _sign = window_rmse_against_reference(y_final, hkh_win)
            rmse_list.append(float(rmse_val))

    bpm_est_arr = np.asarray(bpm_est, dtype=float)
    bpm_hkh_arr = np.asarray(bpm_hkh, dtype=float)
    rmse_arr = np.asarray(rmse_list, dtype=float)

    valid_bpm = np.isfinite(bpm_est_arr) & np.isfinite(bpm_hkh_arr) & (bpm_hkh_arr > 0)
    abs_err = np.where(valid_bpm, np.abs(bpm_est_arr - bpm_hkh_arr), np.nan)
    rel_err = np.where(valid_bpm, abs_err / bpm_hkh_arr * 100.0, np.nan)

    label = next((lbl for lbl, key, _ in B3_VARIANT_SPECS if key == variant_key), variant_key)

    result = {
        "segment": seg_name,
        "method": variant_key,
        "label": label,
        "n_windows": len(starts),
        "fs_ble": fs,
        "fs_hkh": fs_hkh,
        "bpm_est": bpm_est_arr,
        "bpm_vote": np.asarray(bpm_vote, dtype=float),
        "bpm_wf": np.asarray(bpm_wf, dtype=float),
        "bpm_hkh_gt": bpm_hkh_arr,
        "bpm_abs_err": abs_err,
        "bpm_rel_err_pct": rel_err,
        "rmse": rmse_arr,
        "has_waveform": variant.use_two_level_hilbert,
        "summary": {
            "bpm_mean_abs_err": float(np.nanmean(abs_err)),
            "bpm_std_abs_err": float(np.nanstd(abs_err)),
            "bpm_mean_rel_err_pct": float(np.nanmean(rel_err)),
            "bpm_std_rel_err_pct": float(np.nanstd(rel_err)),
            "rmse_mean": float(np.nanmean(rmse_arr)) if variant.use_two_level_hilbert else float("nan"),
            "rmse_std": float(np.nanstd(rmse_arr)) if variant.use_two_level_hilbert else float("nan"),
            "n_valid_bpm": int(np.sum(valid_bpm)),
            "n_valid_rmse": int(np.sum(np.isfinite(rmse_arr))),
        },
    }

    if verbose:
        s = result["summary"]
        rmse_txt = (
            f" | RMSE {s['rmse_mean']:.3f}±{s['rmse_std']:.3f}"
            if variant.use_two_level_hilbert
            else " | RMSE N/A"
        )
        print(
            f"  {label}: BPM {s['bpm_mean_abs_err']:.2f}±{s['bpm_std_abs_err']:.2f}{rmse_txt}"
        )
    return result


def validate_b1_vote_equal_against_hkh(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    cs_t_host: np.ndarray,
    *,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    fs_hkh_override: Optional[float] = None,
    verbose: bool = False,
) -> Optional[dict]:
    """B1 Vote→Equal baseline vs HKH (BPM only, no waveform RMSE)."""
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")

    bpm_hkh, _, fs_ble, fs_hkh = compute_hkh_gt_per_window(
        hkh_bandpass,
        hkh_t_host,
        cs_t_host,
        multichannel_by_var,
        seg_name,
        config=cfg,
        metric_params=mp,
        fs_hkh_override=fs_hkh_override,
    )

    ref_seg = multichannel_by_var["phases"].get(seg_name)
    if ref_seg is None:
        return None

    fs = ref_seg["metadata"]["sampling_rate"]
    ch_lists: Dict[str, List[Any]] = {}
    seg_maps: Dict[str, dict] = {}
    for var in MODAL_VOTING_VARIABLES:
        seg = multichannel_by_var.get(var, {}).get(seg_name)
        if seg is None:
            return None
        seg_maps[var] = seg["channels"]
        ch_lists[var] = sorted(seg["channels"].keys(), key=lambda c: (isinstance(c, str), str(c)))

    ref_len = 0
    for var in MODAL_VOTING_VARIABLES:
        ref_len = max(
            ref_len,
            max(len(c[var]["bandpass_filtered"]) for c in seg_maps[var].values()),
        )
    win_len = int(round(mp.window_length_sec * fs))
    step_len = int(round(mp.step_length_sec * fs))
    starts = _sliding_window_indices(ref_len, win_len, step_len)

    nfft = cfg.nfft or _next_pow2(4 * win_len)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)
    band_mask = (freqs >= cfg.breath_freq_low) & (freqs <= cfg.breath_freq_high)
    band_freqs = freqs[band_mask]
    hann = np.hanning(win_len)

    bpm_est: List[float] = []
    for st in starts:
        end = st + win_len
        spectra_by_var: Dict[str, np.ndarray] = {}
        scores_by_var: Dict[str, float] = {}
        for var in MODAL_VOTING_VARIABLES:
            spec, _bpm, info = per_modal_voting_spectrum(
                ch_lists[var],
                seg_maps[var],
                var,
                st,
                end,
                fs,
                cfg,
                vcfg,
                nfft,
                band_mask,
                band_freqs,
                hann,
            )
            short = MODAL_SHORT[var]
            spectra_by_var[short] = spec
            scores_by_var[short] = float(info.get("conf", 0.0))
        bpm, _sel = modal_fusion_from_spectra(
            spectra_by_var, scores_by_var, "equal", band_freqs, cfg
        )
        bpm_est.append(float(bpm))

    bpm_est_arr = np.asarray(bpm_est, dtype=float)
    summary = summarize_bpm_vs_hkh(bpm_est_arr, bpm_hkh)
    summary["rmse_mean"] = float("nan")
    summary["rmse_std"] = float("nan")
    summary["n_valid_rmse"] = 0

    if verbose:
        print(
            f"  B1 Vote→Equal: BPM {summary['bpm_mean_abs_err']:.2f}±{summary['bpm_std_abs_err']:.2f} | RMSE N/A"
        )

    return {
        "segment": seg_name,
        "method": "b1_vote_modal_equal",
        "label": "B1 Vote→Equal",
        "bpm_est": bpm_est_arr,
        "bpm_hkh_gt": bpm_hkh,
        "rmse": np.full(len(starts), np.nan),
        "has_waveform": False,
        "summary": summary,
        "fs_ble": fs_ble,
        "fs_hkh": fs_hkh,
    }


def compute_b3_cross_domain_summary(
    per_scenario_results: Dict[str, Dict[str, dict]],
) -> dict:
    """Aggregate per-scenario method summaries across all HKH scenarios."""
    method_keys = set()
    for scenario_payload in per_scenario_results.values():
        method_keys.update(scenario_payload.get("methods", {}).keys())

    cross: Dict[str, dict] = {}
    for method_key in sorted(method_keys):
        bpm_means: List[float] = []
        bpm_stds: List[float] = []
        rmse_means: List[float] = []
        labels: List[str] = []
        for _sid, payload in per_scenario_results.items():
            row = payload.get("methods", {}).get(method_key)
            if row is None:
                continue
            s = row.get("summary", {})
            if np.isfinite(s.get("bpm_mean_abs_err", float("nan"))):
                bpm_means.append(float(s["bpm_mean_abs_err"]))
                bpm_stds.append(float(s.get("bpm_std_abs_err", 0.0)))
            rmse_m = s.get("rmse_mean", float("nan"))
            if np.isfinite(rmse_m):
                rmse_means.append(float(rmse_m))
            labels.append(row.get("label", method_key))

        if not bpm_means:
            continue
        cross[method_key] = {
            "label": labels[0] if labels else method_key,
            "bpm_mean_abs_err": float(np.mean(bpm_means)),
            "bpm_std_abs_err": float(np.mean(bpm_stds)),
            "bpm_per_scenario": bpm_means,
            "rmse_mean": float(np.mean(rmse_means)) if rmse_means else float("nan"),
            "rmse_per_scenario": rmse_means,
            "n_scenarios": len(bpm_means),
        }

    leaderboard = sorted(
        cross.values(),
        key=lambda r: r["bpm_mean_abs_err"],
    )
    return {"methods": cross, "leaderboard": leaderboard}
