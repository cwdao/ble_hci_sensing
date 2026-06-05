"""chFusion PCA/SVD — cross-domain pipeline runner (§8 only).

Run: ``python notebooks/scripts/chFusion_pca_svd_cross_domain.py``
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next(
    (p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()),
    None,
)
if project_root is None:
    raise FileNotFoundError("Project root not found (missing src/ directory)")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import (
    CS_SIGNAL_VARIABLES,
    ChFusionConfig,
    Plan2Config,
    _overall_rel_error,
    build_plan2_leaderboard_rows,
    estimate_segment_bpm_methods,
    run_multichannel_segment_filtering,
    run_plan2_validation,
)
from ble_analysis.data import load_ble_frames
from ble_analysis.pca_svd import (
    MODAL_PCA_VARIABLES,
    PcaSvdConfig,
    run_pca_complex_dual_amp,
    run_pca_complex_eta_blend,
    run_pca_complex_fusion,
    run_pca_complex_modal_fusion,
    run_pca_modal_fusion,
    run_pca_topk_bpm,
)
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams, FilterParams

# Import helpers from main script via exec of function-only block is fragile;
# duplicate minimal runner below (keeps this script import-safe).

_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]

COMPARE_SCENARIO_IDS = ("cs_091339", "cs_095806", "cs_102621")
FORCE_REBUILD = True

REQUIRED_PCA_V2_CACHE_KEYS = (
    "PCA-Modal3 top2/ch-η",
    "PCA-Cmplx-Modal rem+loc top2",
    "PCA-Cmplx η-blend ch-η",
    "PCA-Modal3 top8/ch-η",
    "PCA-HP Remote top8/ch-η",
)

CROSS_DOMAIN_COMPARE_LABELS = (
    "Modal η-weight",
    "Modal top2 equal",
    "PCA-Modal3 top2/ch-η",
    "PCA-Modal3 top8/ch-η",
    "PCA-Modal3 top16/ch-η",
    "PCA-Cmplx-Modal rem+loc top2",
    "PCA-Cmplx Total ch-η",
    "PCA-Cmplx Total top8/ch-η",
    "PCA-Cmplx η-blend ch-η",
    "PCA-Cmplx-Modal rem+loc η",
    "PCA-Modal3 η/ch-η",
    "PCA-HP Remote top8/ch-η",
    "PCA-HP Remote ch-η",
    "PCA Total Amp",
    "Uniform Remote amplitude",
    "Single Remote amplitude",
)

PCA_SVD_EXPERIMENTS = {
    "PCA Remote Amp": {"method": "pca", "variable": "remote_amplitudes"},
    "PCA Local Amp": {"method": "pca", "variable": "local_amplitudes"},
    "PCA Total Amp": {"method": "pca", "variable": "amplitudes"},
    "SVD Remote Amp": {"method": "svd_real", "variable": "remote_amplitudes"},
    "SVD Local Amp": {"method": "svd_real", "variable": "local_amplitudes"},
    "SVD Total Amp": {"method": "svd_real", "variable": "amplitudes"},
    "PCA Phase": {"method": "pca", "variable": "phases"},
    "SVD Phase": {"method": "svd_real", "variable": "phases"},
    "SVD Complex Total": {
        "method": "svd_complex", "variable": "phases", "complex_amp_var": "amplitudes",
    },
    "SVD Complex Remote": {
        "method": "svd_complex", "variable": "phases", "complex_amp_var": "remote_amplitudes",
    },
    "SVD Complex Local": {
        "method": "svd_complex", "variable": "phases", "complex_amp_var": "local_amplitudes",
    },
    "PCA Stacked": {
        "method": "pca",
        "variable": ["remote_amplitudes", "local_amplitudes", "amplitudes"],
    },
}

PCA_V2_EXPERIMENTS = {
    "PCA-HP Remote ch-uniform": {
        "method": "pca", "variable": "remote_amplitudes",
        "channel_weight": "uniform", "signal_key": "highpass_filtered",
    },
    "PCA-HP Remote ch-η": {
        "method": "pca", "variable": "remote_amplitudes",
        "channel_weight": "energy_ratio", "signal_key": "highpass_filtered",
    },
    "PCA-HP Phase ch-uniform": {
        "method": "pca", "variable": "phases",
        "channel_weight": "uniform", "signal_key": "highpass_filtered",
    },
    "PCA-HP Phase ch-η": {
        "method": "pca", "variable": "phases",
        "channel_weight": "energy_ratio", "signal_key": "highpass_filtered",
    },
    "PCA-HP Total ch-uniform": {
        "method": "pca", "variable": "amplitudes",
        "channel_weight": "uniform", "signal_key": "highpass_filtered",
    },
    "PCA-HP Total ch-η": {
        "method": "pca", "variable": "amplitudes",
        "channel_weight": "energy_ratio", "signal_key": "highpass_filtered",
    },
}

PCA_MODAL_EXPERIMENTS = {
    "PCA-Modal3 eq/ch-uni": {
        "modal_variables": MODAL_PCA_VARIABLES,
        "channel_weight": "uniform", "modal_weight": "equal",
    },
    "PCA-Modal3 η/ch-η": {
        "modal_variables": MODAL_PCA_VARIABLES,
        "channel_weight": "energy_ratio", "modal_weight": "energy_ratio",
    },
    "PCA-Modal amp+pha eq": {
        "modal_variables": ("remote_amplitudes", "phases"),
        "channel_weight": "uniform", "modal_weight": "equal",
    },
    "PCA-Modal amp+pha η": {
        "modal_variables": ("remote_amplitudes", "phases"),
        "channel_weight": "energy_ratio", "modal_weight": "energy_ratio",
    },
    "PCA-Modal3 top2/ch-η": {
        "modal_variables": MODAL_PCA_VARIABLES,
        "channel_weight": "energy_ratio", "modal_weight": "top2_equal",
    },
    "PCA-Modal amp+pha top2": {
        "modal_variables": ("remote_amplitudes", "phases"),
        "channel_weight": "energy_ratio", "modal_weight": "top2_equal",
    },
}

PCA_COMPLEX_EXPERIMENTS = {
    "PCA-Cmplx Total ch-uni": {"amp_var": "amplitudes", "channel_weight": "uniform"},
    "PCA-Cmplx Total ch-η": {"amp_var": "amplitudes", "channel_weight": "energy_ratio"},
}

PCA_COMPLEX_INTEGRATION_EXPERIMENTS = {
    "PCA-Cmplx Dual-Amp ch-uni": {"runner": "dual_amp", "channel_weight": "uniform"},
    "PCA-Cmplx Dual-Amp ch-η": {"runner": "dual_amp", "channel_weight": "energy_ratio"},
    "PCA-Cmplx η-blend ch-uni": {"runner": "eta_blend", "channel_weight": "uniform"},
    "PCA-Cmplx η-blend ch-η": {"runner": "eta_blend", "channel_weight": "energy_ratio"},
    "PCA-Cmplx-Modal rem+loc eq": {
        "runner": "complex_modal",
        "amp_variables": ("remote_amplitudes", "local_amplitudes"),
        "channel_weight": "uniform", "modal_weight": "equal",
    },
    "PCA-Cmplx-Modal rem+loc η": {
        "runner": "complex_modal",
        "amp_variables": ("remote_amplitudes", "local_amplitudes"),
        "channel_weight": "energy_ratio", "modal_weight": "energy_ratio",
    },
    "PCA-Cmplx-Modal rem+loc top2": {
        "runner": "complex_modal",
        "amp_variables": ("remote_amplitudes", "local_amplitudes"),
        "channel_weight": "energy_ratio", "modal_weight": "top2_equal",
    },
}

PCA_TOPK_EXPERIMENTS = {
    "PCA-HP Remote top8/ch-η": {
        "runner": "variable", "variable": "remote_amplitudes",
        "top_k": 8, "channel_weight": "energy_ratio",
    },
    "PCA-HP Remote top16/ch-η": {
        "runner": "variable", "variable": "remote_amplitudes",
        "top_k": 16, "channel_weight": "energy_ratio",
    },
    "PCA-Modal3 top8/ch-η": {
        "runner": "modal", "modal_variables": MODAL_PCA_VARIABLES,
        "channel_weight": "energy_ratio", "modal_weight": "energy_ratio", "top_k_channels": 8,
    },
    "PCA-Modal3 top16/ch-η": {
        "runner": "modal", "modal_variables": MODAL_PCA_VARIABLES,
        "channel_weight": "energy_ratio", "modal_weight": "energy_ratio", "top_k_channels": 16,
    },
    "PCA-Cmplx Total top8/ch-η": {
        "runner": "complex", "amp_var": "amplitudes",
        "channel_weight": "energy_ratio", "top_k_channels": 8,
    },
}


def _modal_to_per_seg(modal_raw, method_key):
    out = {}
    for seg_name, row in modal_raw.items():
        if row is None:
            out[seg_name] = None
            continue
        block = row.get(method_key)
        if block is None:
            out[seg_name] = None
            continue
        out[seg_name] = {**block, "bpm_gt": row.get("bpm_gt")}
    return out


def _segment_rel_err_pct(errs):
    if not errs:
        return np.nan, np.nan, 0
    a = np.asarray(errs, dtype=float)
    std = float(np.std(a, ddof=1) * 100.0) if len(a) > 1 else 0.0
    return float(np.mean(a) * 100.0), std, len(a)


def _pca_svd_category(exp_name: str) -> str:
    if exp_name.startswith("SVD Complex"):
        return "SVD Complex"
    if (
        exp_name.startswith("PCA-Modal")
        or exp_name.startswith("PCA-Cmplx")
        or exp_name.startswith("PCA-Cmplx-Modal")
    ):
        return "PCA Modal"
    if exp_name.startswith("PCA-HP"):
        return "PCA HP"
    return exp_name.split()[0]


METHOD_CATEGORY_COLORS = {
    "PCA": "#5A9BD5", "PCA HP": "#4A8BC2", "PCA Modal": "#9B7FBF",
    "SVD": "#70AD47", "SVD Complex": "#BF8FBF", "Baseline": "#F0C8A0",
    "Single": "#E8A0A0", "Uniform": "#F0C8A0", "Modal": "#C9A0DC", "Plan2": "#C9A0DC",
}


def _category_color(label, category=None):
    if category:
        return METHOD_CATEGORY_COLORS.get(category, "#CCCCCC")
    if label.startswith("SVD Complex"):
        return METHOD_CATEGORY_COLORS["SVD Complex"]
    return METHOD_CATEGORY_COLORS.get(label.split()[0], "#CCCCCC")


def build_leaderboard(pca_svd_results, baseline_results, plan2_rows=None):
    rows = []
    baseline_names_map = {
        "fft_single_max_energy": ("Single (remote amp)", "Single"),
        "fft_uniform_fusion": ("Uniform (remote amp)", "Uniform"),
        "fft_q_energy_peak_fusion": ("q_energy_peak (remote amp)", "Baseline"),
    }
    for key, (label, cat) in baseline_names_map.items():
        stats = _overall_rel_error(baseline_results, key)
        if not np.isfinite(stats["mean_rel_err_pct"]):
            continue
        rows.append({
            "label": label,
            "mean_rel_err_pct": stats["mean_rel_err_pct"],
            "std_rel_err_pct": stats["std_rel_err_pct"],
            "n_valid": stats["n_segments"],
            "category": cat,
            "color": _category_color(label, cat),
            "source": "baseline",
        })
    for exp_name, per_seg in pca_svd_results.items():
        errs = []
        for _seg_name, seg_stats in per_seg.items():
            if seg_stats is None:
                continue
            err = seg_stats.get("bpm_rel_err", np.nan)
            if np.isfinite(err):
                errs.append(float(err))
        mean_err, std_err, n_valid = _segment_rel_err_pct(errs)
        if not np.isfinite(mean_err):
            continue
        cat = _pca_svd_category(exp_name)
        rows.append({
            "label": exp_name,
            "mean_rel_err_pct": mean_err,
            "std_rel_err_pct": std_err,
            "n_valid": n_valid,
            "category": cat,
            "color": _category_color(exp_name, cat),
            "source": "pca_svd",
        })
    for prow in plan2_rows or []:
        rows.append({
            "label": prow["label"],
            "mean_rel_err_pct": prow["mean_rel_err_pct"],
            "std_rel_err_pct": prow["std_rel_err_pct"],
            "n_valid": prow.get("n_segments", 0),
            "category": prow.get("category", "Plan2"),
            "color": prow.get("color", _category_color(prow["label"], "Plan2")),
            "source": "plan2",
        })
    rows.sort(key=lambda r: r["mean_rel_err_pct"] if np.isfinite(r["mean_rel_err_pct"]) else 999)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def run_pca_v2_suite(multichannel_by_var, segment_config, fs, metric_params, pca_hp_cfg, *, verbose=True):
    pca_v2 = {}
    # HP single-variable experiments need run_pca_svd_bpm — import from segments helper module
    from ble_analysis.segments import _estimate_breathing_freq_hz, _sliding_window_indices
    from ble_analysis.pca_svd import (
        align_waveform_sign,
        build_channel_data_matrix,
        compute_channel_energy_weights,
        extract_breath_waveform_pca,
    )

    for exp_name, exp_cfg in PCA_V2_EXPERIMENTS.items():
        cfg = replace(pca_hp_cfg, channel_weight=exp_cfg["channel_weight"])
        var = exp_cfg["variable"]
        mp = metric_params
        win_len = int(round(mp.window_length_sec * fs))
        step_len = int(round(mp.step_length_sec * fs))
        per_seg = {}
        if verbose:
            print(f"\n--- PCA v2: {exp_name} ---")
        mc = multichannel_by_var.get(var, {})
        for seg_name in sorted(segment_config.keys()):
            seg_cfg = segment_config[seg_name]
            seg = mc.get(seg_name)
            if seg is None or seg_cfg.get("type") == "apnea":
                per_seg[seg_name] = None
                continue
            metadata = seg.get("metadata", {})
            bpm_gt = metadata.get("bpm_gt") or seg_cfg.get("bpm_gt")
            ch_map = seg["channels"]
            ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
            ref_len = max(
                len(ch_map[c][var].get(cfg.signal_key, []))
                for c in ch_list
                if ch_map[c][var].get(cfg.signal_key) is not None
            )
            if ref_len < win_len:
                per_seg[seg_name] = None
                continue
            starts = _sliding_window_indices(ref_len, win_len, step_len)
            bpms, prev_wf = [], None
            for st in starts:
                end = st + win_len
                x_mat, used = build_channel_data_matrix(ch_map, var, ch_list, st, end, cfg.signal_key)
                if x_mat.shape[1] < cfg.min_channels:
                    bpms.append(np.nan)
                    continue
                ch_w = (
                    compute_channel_energy_weights(ch_map, var, used, st, end, fs, cfg)
                    if cfg.channel_weight == "energy_ratio"
                    else None
                )
                wf, _ = extract_breath_waveform_pca(x_mat, cfg, seg_name, channel_weights=ch_w)
                wf = align_waveform_sign(wf, prev_wf)
                prev_wf = wf.copy()
                seg_wf = wf - np.mean(wf)
                f_hz = _estimate_breathing_freq_hz(
                    seg_wf, fs, cfg.breath_freq_low, cfg.breath_freq_high
                )
                bpms.append(60.0 * f_hz if np.isfinite(f_hz) else np.nan)
            from ble_analysis.chfusion import _seg_bpm_stats
            per_seg[seg_name] = {**_seg_bpm_stats(np.asarray(bpms, float), bpm_gt, len(starts)), "bpm_gt": bpm_gt}
        pca_v2[exp_name] = per_seg

    for exp_name, exp_cfg in PCA_MODAL_EXPERIMENTS.items():
        cfg = replace(pca_hp_cfg, channel_weight=exp_cfg["channel_weight"])
        raw = run_pca_modal_fusion(
            multichannel_by_var,
            modal_variables=exp_cfg["modal_variables"],
            channel_weight=exp_cfg["channel_weight"],
            modal_weight=exp_cfg["modal_weight"],
            top_k_channels=exp_cfg.get("top_k_channels"),
            metric_params=metric_params,
            pca_svd_config=cfg,
            verbose=verbose,
        )
        top_suffix = f"_top{exp_cfg['top_k_channels']}" if exp_cfg.get("top_k_channels") else ""
        mkey = f"pca_modal_{exp_cfg['modal_weight']}_ch_{exp_cfg['channel_weight']}{top_suffix}"
        pca_v2[exp_name] = _modal_to_per_seg(raw, mkey)

    for exp_name, exp_cfg in PCA_COMPLEX_EXPERIMENTS.items():
        cfg = replace(pca_hp_cfg, channel_weight=exp_cfg["channel_weight"])
        raw = run_pca_complex_fusion(
            multichannel_by_var,
            amp_var=exp_cfg["amp_var"],
            channel_weight=exp_cfg["channel_weight"],
            top_k_channels=exp_cfg.get("top_k_channels"),
            metric_params=metric_params,
            pca_svd_config=cfg,
            verbose=verbose,
        )
        top_suffix = f"_top{exp_cfg['top_k_channels']}" if exp_cfg.get("top_k_channels") else ""
        ckey = f"pca_complex_{exp_cfg['amp_var']}_ch_{exp_cfg['channel_weight']}{top_suffix}"
        pca_v2[exp_name] = _modal_to_per_seg(raw, ckey)

    for exp_name, exp_cfg in PCA_COMPLEX_INTEGRATION_EXPERIMENTS.items():
        cfg = replace(pca_hp_cfg, channel_weight=exp_cfg.get("channel_weight", "uniform"))
        runner = exp_cfg["runner"]
        if verbose:
            print(f"\n--- PCA integration: {exp_name} ---")
        if runner == "dual_amp":
            raw = run_pca_complex_dual_amp(
                multichannel_by_var, channel_weight=exp_cfg["channel_weight"],
                metric_params=metric_params, pca_svd_config=cfg, verbose=verbose,
            )
            ikey = f"pca_complex_dual_amp_ch_{exp_cfg['channel_weight']}"
        elif runner == "eta_blend":
            raw = run_pca_complex_eta_blend(
                multichannel_by_var, channel_weight=exp_cfg["channel_weight"],
                metric_params=metric_params, pca_svd_config=cfg, verbose=verbose,
            )
            ikey = f"pca_complex_eta_blend_ch_{exp_cfg['channel_weight']}"
        else:
            raw = run_pca_complex_modal_fusion(
                multichannel_by_var,
                amp_variables=exp_cfg["amp_variables"],
                channel_weight=exp_cfg["channel_weight"],
                modal_weight=exp_cfg["modal_weight"],
                metric_params=metric_params,
                pca_svd_config=cfg,
                verbose=verbose,
            )
            ikey = f"pca_complex_modal_{exp_cfg['modal_weight']}_ch_{exp_cfg['channel_weight']}"
        pca_v2[exp_name] = _modal_to_per_seg(raw, ikey)

    for exp_name, exp_cfg in PCA_TOPK_EXPERIMENTS.items():
        cfg = replace(pca_hp_cfg, channel_weight=exp_cfg.get("channel_weight", "energy_ratio"))
        runner = exp_cfg["runner"]
        if verbose:
            print(f"\n--- PCA top-K: {exp_name} ---")
        if runner == "variable":
            raw = run_pca_topk_bpm(
                multichannel_by_var, variable=exp_cfg["variable"], top_k=exp_cfg["top_k"],
                channel_weight=exp_cfg["channel_weight"],
                metric_params=metric_params, pca_svd_config=cfg, verbose=verbose,
            )
            tkey = f"pca_topk_{exp_cfg['variable']}_k{exp_cfg['top_k']}_ch_{exp_cfg['channel_weight']}"
        elif runner == "modal":
            raw = run_pca_modal_fusion(
                multichannel_by_var,
                modal_variables=exp_cfg["modal_variables"],
                channel_weight=exp_cfg["channel_weight"],
                modal_weight=exp_cfg["modal_weight"],
                top_k_channels=exp_cfg["top_k_channels"],
                metric_params=metric_params, pca_svd_config=cfg, verbose=verbose,
            )
            tkey = (
                f"pca_modal_{exp_cfg['modal_weight']}_ch_{exp_cfg['channel_weight']}"
                f"_top{exp_cfg['top_k_channels']}"
            )
        else:
            raw = run_pca_complex_fusion(
                multichannel_by_var, amp_var=exp_cfg["amp_var"],
                channel_weight=exp_cfg["channel_weight"],
                top_k_channels=exp_cfg["top_k_channels"],
                metric_params=metric_params, pca_svd_config=cfg, verbose=verbose,
            )
            tkey = (
                f"pca_complex_{exp_cfg['amp_var']}_ch_{exp_cfg['channel_weight']}"
                f"_top{exp_cfg['top_k_channels']}"
            )
        pca_v2[exp_name] = _modal_to_per_seg(raw, tkey)
    return pca_v2


def run_pca_svd_bpm_v1(multichannel_by_var, segment_config, fs, metric_params, pca_svd_config, verbose=True):
    """Minimal v1 PCA/SVD runner (bandpass) for cross-domain pipeline."""
    from ble_analysis.pca_svd import (
        align_waveform_sign,
        build_channel_data_matrix,
        build_multivariable_data_matrix,
        compute_channel_energy_weights,
        extract_breath_waveform_complex_pca,
        extract_breath_waveform_complex_svd,
        extract_breath_waveform_pca,
        extract_breath_waveform_svd,
    )
    from ble_analysis.chfusion import _seg_bpm_stats
    from ble_analysis.segments import _estimate_breathing_freq_hz, _sliding_window_indices

    mp = metric_params
    cfg = pca_svd_config
    win_len = int(round(mp.window_length_sec * fs))
    step_len = int(round(mp.step_length_sec * fs))
    results = {}

    for exp_name, exp_cfg in PCA_SVD_EXPERIMENTS.items():
        method = exp_cfg["method"]
        variable_or_vars = exp_cfg["variable"]
        complex_amp_var = exp_cfg.get("complex_amp_var")
        is_stack = not isinstance(variable_or_vars, str)
        var_list = [variable_or_vars] if not is_stack else list(variable_or_vars)
        if verbose:
            print(f"\n--- {exp_name} ---")
        per_seg = {}
        for seg_name in sorted(segment_config.keys()):
            seg_cfg = segment_config[seg_name]
            if seg_cfg.get("type") == "apnea":
                per_seg[seg_name] = None
                continue
            if is_stack:
                ch_lengths = {}
                for var in var_list:
                    seg = multichannel_by_var.get(var, {}).get(seg_name)
                    if seg is None:
                        continue
                    for ch, proc in seg["channels"].items():
                        sig = proc[var].get(cfg.signal_key)
                        if sig is not None:
                            ch_lengths[ch] = min(ch_lengths.get(ch, len(sig)), len(sig))
                ch_list = sorted(k for k in ch_lengths if ch_lengths[k] >= win_len)
                ref_len = max(ch_lengths.values()) if ch_lengths else 0
                ref_mc = multichannel_by_var.get("remote_amplitudes", {}).get(seg_name)
            else:
                var = var_list[0]
                seg = multichannel_by_var.get(var, {}).get(seg_name)
                if seg is None:
                    per_seg[seg_name] = None
                    continue
                ref_mc = seg
                ch_map = seg["channels"]
                ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
                ref_len = max(len(ch_map[c][var].get(cfg.signal_key, [])) for c in ch_list)
            metadata = (ref_mc or {}).get("metadata", {})
            bpm_gt = metadata.get("bpm_gt") or seg_cfg.get("bpm_gt")
            if ref_len < win_len:
                per_seg[seg_name] = None
                continue
            starts = _sliding_window_indices(ref_len, win_len, step_len)
            bpms, prev_wf = [], None
            sk = cfg.signal_key
            for st in starts:
                end = st + win_len
                if method in ("svd_complex", "pca_complex") and not is_stack:
                    amp_var = complex_amp_var or "amplitudes"
                    seg_amp = multichannel_by_var.get(amp_var, {}).get(seg_name)
                    seg_pha = multichannel_by_var.get("phases", {}).get(seg_name)
                    if seg_amp is None or seg_pha is None:
                        bpms.append(np.nan)
                        continue
                    cols_c = []
                    for ch in ch_list:
                        pa, pp = seg_amp["channels"].get(ch), seg_pha["channels"].get(ch)
                        if pa is None or pp is None:
                            continue
                        ba = pa[amp_var].get(sk)
                        bp = pp["phases"].get(sk)
                        if ba is None or bp is None or len(ba) < end or len(bp) < end:
                            continue
                        cols_c.append(ba[st:end] * np.exp(1j * bp[st:end]))
                    if len(cols_c) < cfg.min_channels:
                        bpms.append(np.nan)
                        continue
                    x_c = np.column_stack(cols_c)
                    wf, _ = (
                        extract_breath_waveform_complex_pca(x_c, cfg, seg_name)
                        if method == "pca_complex"
                        else extract_breath_waveform_complex_svd(x_c, cfg, seg_name)
                    )
                elif not is_stack:
                    var = var_list[0]
                    ch_map = multichannel_by_var.get(var, {}).get(seg_name)["channels"]
                    x_mat, _ = build_channel_data_matrix(ch_map, var, ch_list, st, end, sk)
                    if x_mat.shape[1] < cfg.min_channels:
                        bpms.append(np.nan)
                        continue
                    wf, _ = (
                        extract_breath_waveform_pca(x_mat, cfg, seg_name)
                        if method == "pca"
                        else extract_breath_waveform_svd(x_mat, cfg, seg_name)
                    )
                else:
                    ch_maps = {
                        v: multichannel_by_var.get(v, {}).get(seg_name, {}).get("channels", {})
                        for v in var_list
                    }
                    x_mat = build_multivariable_data_matrix(ch_maps, var_list, ch_list, st, end, sk)
                    if x_mat.shape[1] < cfg.min_channels:
                        bpms.append(np.nan)
                        continue
                    wf, _ = (
                        extract_breath_waveform_pca(x_mat, cfg, seg_name)
                        if method == "pca"
                        else extract_breath_waveform_svd(x_mat, cfg, seg_name)
                    )
                wf = align_waveform_sign(wf, prev_wf)
                prev_wf = wf.copy()
                seg_wf = wf - np.mean(wf)
                f_hz = _estimate_breathing_freq_hz(
                    seg_wf, fs, cfg.breath_freq_low, cfg.breath_freq_high
                )
                bpms.append(60.0 * f_hz if np.isfinite(f_hz) else np.nan)
            per_seg[seg_name] = {**_seg_bpm_stats(np.asarray(bpms, float), bpm_gt, len(starts)), "bpm_gt": bpm_gt}
        results[exp_name] = per_seg
    return results


def run_scenario_pipeline(
    scenario_id, *, project_root, filter_params, metric_params,
    chfusion_config, plan2_config, pca_svd_config, pca_hp_cfg, verbose=True,
):
    sc = load_scenario(scenario_id, project_root=project_root)
    _data, run_frames = load_ble_frames(sc.resolve_data_path(project_root), verbose=False)
    seg_cfg = sc.segment_config
    vars_list = [v[0] for v in CS_SIGNAL_VARIABLES]
    mc_by_var, run_fs = {}, None
    for variable in vars_list:
        mc, run_fs = run_multichannel_segment_filtering(
            run_frames, seg_cfg, variable=variable,
            filter_params=filter_params, verbose=verbose,
        )
        mc_by_var[variable] = mc
    baseline = estimate_segment_bpm_methods(
        mc_by_var["remote_amplitudes"], variable="remote_amplitudes",
        config=chfusion_config, metric_params=metric_params,
        methods=("single", "uniform", "q_energy_peak"),
        single_channel_metric="energy_ratio", verbose=verbose,
    )
    pca_results = run_pca_svd_bpm_v1(
        mc_by_var, seg_cfg, run_fs, metric_params, pca_svd_config, verbose=verbose,
    )
    pca_results.update(
        run_pca_v2_suite(mc_by_var, seg_cfg, run_fs, metric_params, pca_hp_cfg, verbose=verbose)
    )
    plan2_out = run_plan2_validation(
        run_frames, seg_cfg, filter_params=filter_params, metric_params=metric_params,
        config=chfusion_config, plan2_config=plan2_config,
        reference_variable="phases", verbose=verbose,
    )
    p2_lb = build_plan2_leaderboard_rows(plan2_out)
    lb = build_leaderboard(pca_results, baseline, p2_lb)
    return {
        "scenario_id": scenario_id,
        "scenario_tag": sc.tag,
        "segment_config": seg_cfg,
        "fs": run_fs,
        "multichannel_by_var": mc_by_var,
        "baseline_results": baseline,
        "pca_svd_results": pca_results,
        "plan2_results": plan2_out,
        "plan2_leaderboard": p2_lb,
        "leaderboard": lb,
    }


def _leaderboard_lookup(rows):
    return {r["label"]: r for r in rows}


def ensure_scenario_report(scenario_id, *, configs, verbose=False, force=False):
    sc = load_scenario(scenario_id, project_root=project_root)
    path = REPORTS_DIR / f"chfusion_pca_svd_{sc.tag}.npy"
    if not force and path.is_file():
        cached = np.load(path, allow_pickle=True).item()
        if all(k in cached.get("pca_svd_results", {}) for k in REQUIRED_PCA_V2_CACHE_KEYS):
            print(f"Loaded cached report: {path.name}")
            return cached
        print(f"Stale cache: {path.name}")
    print(f"Running PCA/SVD pipeline for {scenario_id} …")
    result = run_scenario_pipeline(scenario_id, project_root=project_root, verbose=verbose, **configs)
    np.save(path, result, allow_pickle=True)
    print(f"Saved: {path.name}")
    return result


def main():
    filter_params = FilterParams()
    metric_params = BreathMetricParams()
    configs = dict(
        filter_params=filter_params,
        metric_params=metric_params,
        chfusion_config=ChFusionConfig(
            breath_freq_low=metric_params.breath_freq_low,
            breath_freq_high=metric_params.breath_freq_high,
            window_length_sec=metric_params.window_length_sec,
            step_length_sec=metric_params.step_length_sec,
            enable_consensus=False,
        ),
        plan2_config=Plan2Config(channel_metric="energy_ratio"),
        pca_svd_config=PcaSvdConfig(
            method="pca", normalize="zscore", min_channels=4, min_variance_ratio=0.10,
            signal_key="bandpass_filtered",
            breath_freq_low=metric_params.breath_freq_low,
            breath_freq_high=metric_params.breath_freq_high,
        ),
        pca_hp_cfg=PcaSvdConfig(
            method="pca", normalize="zscore", min_channels=4, min_variance_ratio=0.10,
            signal_key="highpass_filtered",
            breath_freq_low=metric_params.breath_freq_low,
            breath_freq_high=metric_params.breath_freq_high,
        ),
    )

    results_by_tag = {}
    for sid in COMPARE_SCENARIO_IDS:
        sc = load_scenario(sid, project_root=project_root)
        results_by_tag[sc.tag] = ensure_scenario_report(
            sid, configs=configs, verbose=True, force=FORCE_REBUILD,
        )

    compare_tags = [load_scenario(sid, project_root=project_root).tag for sid in COMPARE_SCENARIO_IDS]
    print(f"\n{'=' * 72}\n  Cross-scenario leaderboard\n  {' / '.join(compare_tags)}\n{'=' * 72}")
    col_w = 10
    print(f"{'方法':<32}" + "".join(f"{t:>{col_w}}" for t in compare_tags) + f"{'mean':>8}{'±std':>8}")
    print("-" * 72)

    cross_rows = []
    for lbl in CROSS_DOMAIN_COMPARE_LABELS:
        domain_errs = []
        for tag in compare_tags:
            row = _leaderboard_lookup(results_by_tag[tag]["leaderboard"]).get(lbl)
            domain_errs.append(float(row["mean_rel_err_pct"]) if row else np.nan)
        finite = [e for e in domain_errs if np.isfinite(e)]
        if not finite:
            continue
        mean_across = float(np.mean(finite))
        std_across = float(np.std(finite, ddof=1)) if len(finite) > 1 else 0.0
        cross_rows.append({
            "label": lbl, "domain_errs": domain_errs,
            "mean_across_domains": mean_across, "std_across_domains": std_across,
        })
        line = f"{lbl:<32}"
        for e in domain_errs:
            line += f"{e:>{col_w}.2f}" if np.isfinite(e) else f"{'—':>{col_w}}"
        print(line + f"{mean_across:>{col_w}.2f}{std_across:>8.2f}")

    cross_rows.sort(key=lambda r: r["mean_across_domains"])
    best = cross_rows[0]
    print(f"\n  ★ 跨场景综合最优: {best['label']}  →  {best['mean_across_domains']:.2f}% ± {best['std_across_domains']:.2f}%")

    fig, ax = plt.subplots(figsize=(10, max(5.0, 0.38 * len(cross_rows) + 1.5)))
    y = np.arange(len(cross_rows))
    means = [r["mean_across_domains"] for r in cross_rows]
    stds = [r["std_across_domains"] for r in cross_rows]
    ax.barh(y, means, xerr=stds, color="#7B9FD4", edgecolor="black", alpha=0.85, height=0.72, capsize=3)
    ax.set_yticks(y)
    ax.set_yticklabels([r["label"] for r in cross_rows], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Mean relative BPM error (%) across scenarios")
    ax.set_title("PCA/SVD + Plan2 — cross-domain aggregate")
    ax.grid(True, axis="x", alpha=0.25)
    plt.tight_layout()
    cross_path = FIGURES_DIR / "pca_svd_cross_domain_aggregate_bars.pdf"
    fig.savefig(cross_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Fig -> {cross_path.name}")

    np.save(
        REPORTS_DIR / "chfusion_pca_svd_cross_domain.npy",
        {
            "scenario_ids": COMPARE_SCENARIO_IDS,
            "scenario_tags": compare_tags,
            "compare_labels": CROSS_DOMAIN_COMPARE_LABELS,
            "cross_rows": cross_rows,
            "results_by_tag": {k: v["leaderboard"] for k, v in results_by_tag.items()},
        },
        allow_pickle=True,
    )
    print("  Saved: chfusion_pca_svd_cross_domain.npy")


if __name__ == "__main__":
    main()
