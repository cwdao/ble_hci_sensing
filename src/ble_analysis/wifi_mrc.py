"""WiFi MRC baseline migration for BLE CS breathing BPM estimation.

Implements Fan-BLE (η-MRC → best modal) and MRC-PCA-BLE (√η-MRC + PCA sign)
from ``docs/plans/wifi_mrc_baselines_plan.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import welch

from ble_analysis.chfusion import (
    ChFusionConfig,
    Plan2Config,
    _energy_ratio,
    _overall_rel_error,
    _parabolic_peak_freq,
    _seg_bpm_stats,
    run_multichannel_segment_filtering,
)
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.systematic_fusion import (
    estimate_systematic_fusion_segment,
)
from ble_analysis.voting_fusion import (
    MODAL_VOTING_VARIABLES,
    VotingConfig,
    run_voting_fusion_benchmark,
)

MrcWeightMode = Literal["linear", "sqrt", "eta_rho"]

WIFI_MRC_METHOD_SPECS: Tuple[Tuple[str, str, str], ...] = (
    ("B0 Single Remote", "b0_single_remote", "steelblue"),
    ("B1 Uniform Remote", "b1_uniform_remote", "seagreen"),
    ("Modal top2 equal", "b2_modal_top2_equal", "mediumpurple"),
    ("B1 Vote→Equal modal", "b1_vote_modal_equal", "olive"),
    ("Fan-η-linear", "fan_eta_linear", "coral"),
    ("Fan-η-sqrt", "fan_eta_sqrt", "tomato"),
    ("Fan-η-equal", "fan_eta_equal", "darkorange"),
    ("MRC-PCA-η-sqrt", "mrc_pca_eta_sqrt", "indianred"),
    ("MRC-PCA-η-equal", "mrc_pca_eta_equal", "crimson"),
    ("MRC-PCA-no-sign", "mrc_pca_no_sign", "gray"),
)

MRC_METHOD_KEYS: Tuple[str, ...] = tuple(
    key for _label, key, _color in WIFI_MRC_METHOD_SPECS if key.startswith(("fan_", "mrc_"))
)

__all__ = [
    "WIFI_MRC_METHOD_SPECS",
    "MRC_METHOD_KEYS",
    "compute_mrc_weights",
    "fan_mrc_fusion",
    "mrc_pca_fusion",
    "estimate_bpm_from_waveform",
    "estimate_wifi_mrc_segment",
    "run_wifi_mrc_benchmark",
    "compute_wifi_mrc_cross_domain",
    "compute_window_level_metrics",
    "plot_wifi_mrc_figures",
]


def compute_mrc_weights(
    eta: np.ndarray,
    mode: MrcWeightMode = "sqrt",
    rho: Optional[np.ndarray] = None,
    eps: float = 1e-12,
) -> np.ndarray:
    """Derive normalized MRC positive weights from per-tone η."""
    eta_arr = np.asarray(eta, dtype=float)
    eta_arr = np.clip(eta_arr, 0.0, None)
    if mode == "linear":
        raw = eta_arr
    elif mode == "sqrt":
        raw = np.sqrt(eta_arr)
    elif mode == "eta_rho":
        if rho is None:
            raise ValueError("rho required for mode='eta_rho'")
        raw = eta_arr * np.clip(np.asarray(rho, dtype=float), 0.0, None)
    else:
        raise ValueError(f"Unknown MRC weight mode: {mode}")
    total = float(np.sum(raw))
    if total <= eps:
        n = len(raw)
        return np.full(n, 1.0 / n) if n else raw
    return raw / total


def _standardize_rows(X: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    out = np.zeros_like(X, dtype=float)
    for i in range(X.shape[0]):
        row = X[i]
        if not np.all(np.isfinite(row)):
            continue
        mu = float(np.mean(row))
        sd = float(np.std(row))
        out[i] = (row - mu) / sd if sd > eps else (row - mu)
    return out


def fan_mrc_fusion(
    X: np.ndarray,
    eta: np.ndarray,
    weight_mode: MrcWeightMode = "linear",
    fs: float = 2.0,
    cfg: Optional[ChFusionConfig] = None,
    eps: float = 1e-12,
) -> Tuple[np.ndarray, float, dict]:
    """Fan-style η-MRC time-domain fusion for one modal variable."""
    cfg = cfg or ChFusionConfig(eps=eps)
    X_arr = np.asarray(X, dtype=float)
    g = compute_mrc_weights(eta, mode=weight_mode, eps=eps)
    if X_arr.ndim != 2:
        raise ValueError("X must have shape [n_tones, T_win]")
    y = np.sum(g[:, None] * X_arr, axis=0)
    eta_fused = _energy_ratio(y, fs, cfg)
    return y, eta_fused, {"weights": g}


def mrc_pca_fusion(
    X: np.ndarray,
    eta: np.ndarray,
    weight_mode: MrcWeightMode = "sqrt",
    use_pca_sign: bool = True,
    top_k: Optional[int] = 36,
    eps: float = 1e-12,
) -> Tuple[np.ndarray, dict]:
    """WiFi-Sleep style √η-MRC + PCA sign correction."""
    X_arr = np.asarray(X, dtype=float)
    g = compute_mrc_weights(eta, mode=weight_mode, eps=eps)
    n_tones = X_arr.shape[0]
    signs = np.ones(n_tones, dtype=float)

    if use_pca_sign and n_tones > 1:
        idx = np.arange(n_tones)
        if top_k is not None and top_k < n_tones:
            order = np.argsort(-np.asarray(eta, dtype=float))
            idx = order[:top_k]
        X_weighted = X_arr[idx] * g[idx, None]
        X_weighted = _standardize_rows(X_weighted, eps=eps)
        n_samples, n_features = X_weighted.shape
        if n_samples >= 2 and n_features >= 2:
            Z = X_weighted.T
            cov = (Z.T @ Z) / max(n_samples - 1, 1)
            _evals, evecs = np.linalg.eigh(cov)
            loadings = np.asarray(evecs[:, -1], dtype=float)
            for local_i, global_i in enumerate(idx):
                s = np.sign(loadings[local_i])
                signs[global_i] = 1.0 if s == 0 else s

    w = signs * g
    w_sum = float(np.sum(np.abs(w)))
    if w_sum > eps:
        w = w / w_sum
    y = np.sum(w[:, None] * X_arr, axis=0)
    mu = float(np.mean(y))
    sd = float(np.std(y))
    if sd > eps:
        y = (y - mu) / sd
    else:
        y = y - mu
    return y, {"weights": w, "signs": signs, "positive_weights": g}


def estimate_bpm_from_waveform(
    y: np.ndarray,
    fs: float,
    breath_band: Tuple[float, float] = (0.1, 0.35),
    cfg: Optional[ChFusionConfig] = None,
) -> Tuple[float, float, np.ndarray, np.ndarray]:
    """Welch PSD peak BPM with parabolic refinement."""
    cfg = cfg or ChFusionConfig()
    sig = np.asarray(y, dtype=float)
    if len(sig) < 4 or not np.all(np.isfinite(sig)):
        nan = np.array([], dtype=float)
        return float("nan"), float("nan"), nan, nan

    nperseg = min(len(sig), 512)
    noverlap = nperseg // 2
    freqs, pxx = welch(
        sig - np.mean(sig),
        fs=fs,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
    )
    band_mask = (freqs >= breath_band[0]) & (freqs <= breath_band[1])
    if not np.any(band_mask):
        return float("nan"), float("nan"), freqs, pxx

    band_freqs = freqs[band_mask]
    power_band = pxx[band_mask]
    k = int(np.argmax(power_band))
    f_peak = _parabolic_peak_freq(band_freqs, power_band, k, cfg.eps)
    bpm = float(60.0 * f_peak)
    return bpm, float(f_peak), freqs, pxx


def _collect_modal_window_matrix(
    ch_list: Sequence[Any],
    ch_map: dict,
    variable: str,
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
) -> Tuple[np.ndarray, np.ndarray]:
    """Collect standardized bandpass matrix [n_tones, T] and η vector."""
    eta_list: List[float] = []
    rows: List[np.ndarray] = []
    for ch in ch_list:
        ch_data = ch_map[ch][variable]
        bp = ch_data["bandpass_filtered"]
        hp = ch_data["highpass_filtered"]
        if len(bp) < end or len(hp) < end:
            eta_list.append(0.0)
            rows.append(np.full(end - st, np.nan, dtype=float))
            continue
        bp_slice = bp[st:end]
        hp_slice = hp[st:end]
        eta_list.append(_energy_ratio(hp_slice, fs, cfg))
        rows.append(bp_slice)

    X = np.vstack(rows)
    X = _standardize_rows(X, eps=cfg.eps)
    return X, np.asarray(eta_list, dtype=float)


def _nanmean_bpm(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0 or not np.any(np.isfinite(arr)):
        return float("nan")
    return float(np.nanmean(arr))


def _fan_window_bpms(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    ch_list: Sequence[Any],
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    weight_mode: MrcWeightMode,
) -> Tuple[float, float, dict]:
    """Fan MRC per modal; return best-modal BPM, equal-modal BPM, diagnostics."""
    modal_bpms: Dict[str, float] = {}
    modal_etas: Dict[str, float] = {}
    for variable in MODAL_VOTING_VARIABLES:
        ref_seg = multichannel_by_var[variable].get(seg_name)
        if ref_seg is None:
            continue
        ch_map = ref_seg["channels"]
        X, eta = _collect_modal_window_matrix(ch_list, ch_map, variable, st, end, fs, cfg)
        g = compute_mrc_weights(eta, mode=weight_mode, eps=cfg.eps)
        y = np.sum(g[:, None] * X, axis=0)
        eta_fused = _energy_ratio(y, fs, cfg)
        bpm, _fp, _f, _p = estimate_bpm_from_waveform(y, fs, cfg=cfg)
        modal_bpms[variable] = bpm
        modal_etas[variable] = eta_fused

    if not modal_bpms:
        return float("nan"), float("nan"), {"modal_etas": {}, "best_modal": None}

    best_modal = max(modal_etas, key=lambda k: modal_etas[k])
    return (
        modal_bpms[best_modal],
        _nanmean_bpm(list(modal_bpms.values())),
        {"modal_etas": modal_etas, "best_modal": best_modal, "modal_bpms": modal_bpms},
    )


def _mrc_pca_window_bpms(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    ch_list: Sequence[Any],
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    *,
    use_pca_sign: bool = True,
    pca_top_k: int = 36,
) -> Tuple[float, float, dict]:
    modal_bpms: Dict[str, float] = {}
    modal_etas: Dict[str, float] = {}
    for variable in MODAL_VOTING_VARIABLES:
        ref_seg = multichannel_by_var[variable].get(seg_name)
        if ref_seg is None:
            continue
        ch_map = ref_seg["channels"]
        X, eta = _collect_modal_window_matrix(ch_list, ch_map, variable, st, end, fs, cfg)
        y, info = mrc_pca_fusion(
            X,
            eta,
            weight_mode="sqrt",
            use_pca_sign=use_pca_sign,
            top_k=pca_top_k,
            eps=cfg.eps,
        )
        eta_fused = _energy_ratio(y, fs, cfg)
        bpm, _fp, _f, _p = estimate_bpm_from_waveform(y, fs, cfg=cfg)
        modal_bpms[variable] = bpm
        modal_etas[variable] = eta_fused
        info["eta_fused"] = eta_fused

    if not modal_bpms:
        return float("nan"), float("nan"), {"modal_etas": {}, "best_modal": None}

    best_modal = max(modal_etas, key=lambda k: modal_etas[k])
    return (
        modal_bpms[best_modal],
        _nanmean_bpm(list(modal_bpms.values())),
        {"modal_etas": modal_etas, "best_modal": best_modal, "modal_bpms": modal_bpms},
    )


def estimate_wifi_mrc_segment(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    seg_name: str,
    *,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    pca_top_k: int = 36,
    verbose: bool = False,
) -> Optional[dict]:
    """Per-segment WiFi MRC methods (Fan + MRC-PCA variants)."""
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()

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
    fan_linear: List[float] = []
    fan_sqrt: List[float] = []
    fan_equal: List[float] = []
    mrc_sqrt: List[float] = []
    mrc_equal: List[float] = []
    mrc_no_sign: List[float] = []
    best_modals_fan: List[Optional[str]] = []
    best_modals_mrc: List[Optional[str]] = []

    for st in starts:
        end = st + win_len
        b_best, b_equal, info = _fan_window_bpms(
            multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, "linear"
        )
        fan_linear.append(b_best)
        fan_equal.append(b_equal)
        best_modals_fan.append(info.get("best_modal"))

        b_best_s, _b_equal_s, _ = _fan_window_bpms(
            multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, "sqrt"
        )
        fan_sqrt.append(b_best_s)

        b_mrc, b_mrc_eq, info_m = _mrc_pca_window_bpms(
            multichannel_by_var,
            seg_name,
            ch_list,
            st,
            end,
            fs,
            cfg,
            use_pca_sign=True,
            pca_top_k=pca_top_k,
        )
        mrc_sqrt.append(b_mrc)
        mrc_equal.append(b_mrc_eq)
        best_modals_mrc.append(info_m.get("best_modal"))

        b_no, _, _ = _mrc_pca_window_bpms(
            multichannel_by_var,
            seg_name,
            ch_list,
            st,
            end,
            fs,
            cfg,
            use_pca_sign=False,
            pca_top_k=pca_top_k,
        )
        mrc_no_sign.append(b_no)

    return {
        "segment": seg_name,
        "bpm_gt": bpm_gt,
        "metadata": metadata,
        "fan_eta_linear": _seg_bpm_stats(np.asarray(fan_linear), bpm_gt, len(starts)),
        "fan_eta_sqrt": _seg_bpm_stats(np.asarray(fan_sqrt), bpm_gt, len(starts)),
        "fan_eta_equal": _seg_bpm_stats(np.asarray(fan_equal), bpm_gt, len(starts)),
        "mrc_pca_eta_sqrt": _seg_bpm_stats(np.asarray(mrc_sqrt), bpm_gt, len(starts)),
        "mrc_pca_eta_equal": _seg_bpm_stats(np.asarray(mrc_equal), bpm_gt, len(starts)),
        "mrc_pca_no_sign": _seg_bpm_stats(np.asarray(mrc_no_sign), bpm_gt, len(starts)),
        "fan_best_modal_per_window": best_modals_fan,
        "mrc_best_modal_per_window": best_modals_mrc,
    }


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


def run_wifi_mrc_benchmark(
    frames,
    segment_config: Dict[str, dict],
    *,
    filter_params: Optional[FilterParams] = None,
    metric_params: Optional[BreathMetricParams] = None,
    config: Optional[ChFusionConfig] = None,
    plan2_config: Optional[Plan2Config] = None,
    verbose: bool = True,
    cache_dir: Optional[str] = None,
    multichannel_by_var: Optional[Dict[str, Dict[str, Optional[dict]]]] = None,
    pca_top_k: int = 36,
) -> dict:
    """Run WiFi MRC methods plus required baselines for one scenario."""
    cfg = config or ChFusionConfig()
    fp = filter_params or FilterParams()
    mp = metric_params or BreathMetricParams()
    p2 = plan2_config or Plan2Config(channel_metric="energy_ratio")
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")

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
        print("\n--- WiFi MRC methods (Fan + MRC-PCA) ---")
    for seg_name in seg_names:
        row = estimate_wifi_mrc_segment(
            multichannel_by_var,
            seg_name,
            config=cfg,
            metric_params=mp,
            pca_top_k=pca_top_k,
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
        for key in MRC_METHOD_KEYS:
            merged[seg_name][key] = row[key]
        if verbose:
            stats = _overall_rel_error({seg_name: row}, "fan_eta_linear")
            print(
                f"  {seg_name} fan_linear {stats['mean_rel_err_pct']:.2f}% | "
                f"mrc_pca { _overall_rel_error({seg_name: row}, 'mrc_pca_eta_sqrt')['mean_rel_err_pct']:.2f}%"
            )

    if verbose:
        print("\n--- Baselines (B0 / Uniform / Modal top2 / B1 Vote→Equal) ---")
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

    if verbose:
        for label, key, _ in WIFI_MRC_METHOD_SPECS:
            stats = _overall_rel_error(merged, key)
            if np.isfinite(stats["mean_rel_err_pct"]):
                print(f"✓ [{key}] {label} | mean err {stats['mean_rel_err_pct']:.2f}%")

    return {
        "results": merged,
        "multichannel_by_var": multichannel_by_var,
        "method_specs": WIFI_MRC_METHOD_SPECS,
    }


def compute_wifi_mrc_cross_domain(
    results_by_scenario: Dict[str, dict],
) -> List[dict]:
    """Aggregate cross-domain leaderboard rows."""
    agg: List[dict] = []
    for label, key, color in WIFI_MRC_METHOD_SPECS:
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


def compute_window_level_metrics(
    results: Dict[str, Optional[dict]],
    method_key: str,
) -> dict:
    """Window-level BPM error metrics for one method."""
    rel_errs: List[float] = []
    abs_bpms: List[float] = []
    for row in results.values():
        if row is None or row.get("bpm_gt") is None:
            continue
        block = row.get(method_key)
        if block is None:
            continue
        bpm_gt = float(row["bpm_gt"])
        per_win = block.get("bpm_per_window")
        signed = block.get("bpm_signed_err_per_window")
        if per_win is None:
            continue
        per_win = np.asarray(per_win, dtype=float)
        if signed is not None:
            signed_arr = np.asarray(signed, dtype=float)
        else:
            signed_arr = per_win - bpm_gt
        for i, bpm in enumerate(per_win):
            if not np.isfinite(bpm) or bpm_gt <= 0:
                continue
            rel_errs.append(abs(bpm - bpm_gt) / bpm_gt * 100.0)
            if signed is not None and i < len(signed_arr) and np.isfinite(signed_arr[i]):
                abs_bpms.append(abs(signed_arr[i]))
            else:
                abs_bpms.append(abs(bpm - bpm_gt))

    if not rel_errs:
        return {
            "p90_rel_err_pct": np.nan,
            "within_1_bpm_ratio": np.nan,
            "within_2_bpm_ratio": np.nan,
            "n_windows": 0,
        }
    rel_arr = np.asarray(rel_errs, dtype=float)
    abs_arr = np.asarray(abs_bpms, dtype=float)
    return {
        "p90_rel_err_pct": float(np.percentile(rel_arr, 90)),
        "within_1_bpm_ratio": float(np.mean(abs_arr <= 1.0)),
        "within_2_bpm_ratio": float(np.mean(abs_arr <= 2.0)),
        "n_windows": int(len(rel_arr)),
    }


def plot_wifi_mrc_figures(
    results_by_scenario: Dict[str, dict],
    cross_domain: List[dict],
    *,
    figures_dir,
    scenario_ids: Sequence[str],
    show: bool = False,
    save: bool = True,
) -> dict:
    """Generate leaderboard, cross-domain summary, per-scenario, and ablation figures."""
    import matplotlib.pyplot as plt

    figures_dir = Path(figures_dir)
    paths: dict = {}

    fig, ax = plt.subplots(figsize=(12, 7))
    labels = [r["label"] for r in cross_domain]
    means = [r["cross_domain_mean"] for r in cross_domain]
    colors = [r["color"] for r in cross_domain]
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, means, color=colors, alpha=0.85)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Cross-domain mean BPM err %")
    ax.set_title("WiFi MRC baselines — cross-domain leaderboard")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    lb_path = figures_dir / "wifi_mrc_baselines_leaderboard.png"
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
        ax_i.set_yticklabels(lbls, fontsize=7)
        ax_i.invert_yaxis()
        ax_i.set_title(sid)
        ax_i.set_xlabel("Mean BPM err %")
        ax_i.grid(True, axis="x", alpha=0.3)
    fig.suptitle("WiFi MRC baselines — per-scenario comparison", y=1.02)
    fig.tight_layout()
    summary_path = figures_dir / "wifi_mrc_baselines_cross_domain_summary.png"
    if save:
        fig.savefig(summary_path, dpi=150, bbox_inches="tight")
    paths["cross_domain_summary"] = summary_path
    if not show:
        plt.close(fig)

    for sid in scenario_ids:
        bench = results_by_scenario[sid]
        fig_s, ax_s = plt.subplots(figsize=(10, 6))
        vals = []
        lbls = []
        cols = []
        for label, key, color in WIFI_MRC_METHOD_SPECS:
            stats = _overall_rel_error(bench["results"], key)
            if np.isfinite(stats["mean_rel_err_pct"]):
                vals.append(stats["mean_rel_err_pct"])
                lbls.append(label)
                cols.append(color)
        order = np.argsort(vals)
        vals = [vals[i] for i in order]
        lbls = [lbls[i] for i in order]
        cols = [cols[i] for i in order]
        ax_s.barh(np.arange(len(vals)), vals, color=cols, alpha=0.85)
        ax_s.set_yticks(np.arange(len(lbls)))
        ax_s.set_yticklabels(lbls, fontsize=8)
        ax_s.invert_yaxis()
        ax_s.set_xlabel("Mean BPM err %")
        ax_s.set_title(f"WiFi MRC baselines — {sid}")
        ax_s.grid(True, axis="x", alpha=0.3)
        fig_s.tight_layout()
        tag = sid.replace("cs_", "")
        scen_path = figures_dir / f"wifi_mrc_baselines_{tag}.png"
        if save:
            fig_s.savefig(scen_path, dpi=150, bbox_inches="tight")
        paths[f"scenario_{sid}"] = scen_path
        if not show:
            plt.close(fig_s)

    ablation_keys = [
        ("MRC-PCA-η-sqrt", "mrc_pca_eta_sqrt", "indianred"),
        ("MRC-PCA-no-sign", "mrc_pca_no_sign", "gray"),
        ("Fan-η-linear", "fan_eta_linear", "coral"),
        ("Fan-η-equal", "fan_eta_equal", "darkorange"),
        ("B1 Vote→Equal", "b1_vote_modal_equal", "olive"),
    ]
    fig_a, ax_a = plt.subplots(figsize=(8, 5))
    x = np.arange(len(scenario_ids))
    width = 0.15
    for i, (label, key, color) in enumerate(ablation_keys):
        ys = []
        for sid in scenario_ids:
            stats = _overall_rel_error(results_by_scenario[sid]["results"], key)
            ys.append(stats["mean_rel_err_pct"])
        ax_a.bar(x + i * width, ys, width, label=label, color=color, alpha=0.85)
    ax_a.set_xticks(x + width * (len(ablation_keys) - 1) / 2)
    ax_a.set_xticklabels([s.replace("cs_", "") for s in scenario_ids])
    ax_a.set_ylabel("Mean BPM err %")
    ax_a.set_title("WiFi MRC ablation — key methods by scenario")
    ax_a.legend(fontsize=8, loc="upper right")
    ax_a.grid(True, axis="y", alpha=0.3)
    fig_a.tight_layout()
    ablation_path = figures_dir / "wifi_mrc_baselines_ablation.png"
    if save:
        fig_a.savefig(ablation_path, dpi=150, bbox_inches="tight")
    paths["ablation"] = ablation_path
    if not show:
        plt.close(fig_a)

    return paths
