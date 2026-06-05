"""chFusion PCA/SVD — multi-channel breath waveform extraction via PCA / SVD.

Overview
========

代替"按能量比选最优单信道"的策略，利用 PCA 和 SVD
从 72 道 BLE CS tone 中提取所有信道的共同呼吸模式。

Methods
-------

- **PCA Remote/Local/Total Amp** : 远程/本地/总幅值 72 道实 PCA
- **SVD Remote/Local/Total Amp** : 远程/本地/总幅值 72 道实 SVD
- **PCA Phase**              : 总相位 72 道实 PCA
- **SVD Phase**              : 总相位 72 道实 SVD
- **SVD Complex Total/Remote/Local** : 总/远程/本地幅值 + j·总相位 72 道复 SVD
- **PCA Stacked**            : 三种幅值堆叠 216 道实 PCA

Run: ``python notebooks/scripts/chFusion_pca_svd.py``
"""

# %% [markdown]
# # chFusion PCA/SVD — 多信道呼吸波形提取
#
# | Step | Content |
# |------|---------|
# | 0 | Bootstrap + parameters |
# | 1 | Multi-channel filtering (4 variables x 72 channels) |
# | 2 | Baseline BPM (Single / Uniform / q_energy_peak) |
# | 3 | PCA / SVD BPM estimation |
# | 4 | Text + bar-chart leaderboard |
# | 5 | Segment x method heatmap |
# | 6 | PC1 variance ratio analysis |
# | 7 | Save results |
# | 8 | Cross-scenario aggregate leaderboard |

# %% [markdown]
# ## 0. Environment bootstrap

# %%
import sys
from dataclasses import replace
from pathlib import Path

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

_env = init_notebook(project_root)
project_root = _env["project_root"]
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]

# %% [markdown]
# ## 0b. Parameters

# %%
from ble_analysis.chfusion import (
    CS_SIGNAL_VARIABLES,
    ChFusionConfig,
    Plan2Config,
    _overall_rel_error,
    _seg_bpm_stats,
    build_plan2_leaderboard_rows,
    estimate_segment_bpm_methods,
    run_multichannel_segment_filtering,
    run_plan2_validation,
)
from ble_analysis.segments import _estimate_breathing_freq_hz, _sliding_window_indices
from ble_analysis.data import load_ble_frames
from ble_analysis.pca_svd import (
    MODAL_PCA_VARIABLES,
    PcaSvdConfig,
    align_waveform_sign,
    build_channel_data_matrix,
    build_multivariable_data_matrix,
    compute_channel_energy_weights,
    extract_breath_waveform_complex_pca,
    extract_breath_waveform_complex_svd,
    extract_breath_waveform_pca,
    extract_breath_waveform_svd,
    run_pca_complex_dual_amp,
    run_pca_complex_eta_blend,
    run_pca_complex_fusion,
    run_pca_complex_modal_fusion,
    run_pca_modal_fusion,
    run_pca_topk_bpm,
)
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams

SCENARIO_ID = "cs_102621"
COMPARE_SCENARIO_IDS = ("cs_091339", "cs_095806", "cs_102621")

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
        "method": "svd_complex",
        "variable": "phases",
        "complex_amp_var": "amplitudes",
    },
    "SVD Complex Remote": {
        "method": "svd_complex",
        "variable": "phases",
        "complex_amp_var": "remote_amplitudes",
    },
    "SVD Complex Local": {
        "method": "svd_complex",
        "variable": "phases",
        "complex_amp_var": "local_amplitudes",
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
    # 方案2：remote∥local 双复堆叠 144 列
    "PCA-Cmplx Dual-Amp ch-uni": {
        "runner": "dual_amp", "channel_weight": "uniform",
    },
    "PCA-Cmplx Dual-Amp ch-η": {
        "runner": "dual_amp", "channel_weight": "energy_ratio",
    },
    # 方案3：每信道 η 混合幅值后 Ã·e^(jφ)
    "PCA-Cmplx η-blend ch-uni": {
        "runner": "eta_blend", "channel_weight": "uniform",
    },
    "PCA-Cmplx η-blend ch-η": {
        "runner": "eta_blend", "channel_weight": "energy_ratio",
    },
    # 方案4：remote/local 各自复 PCA → 模态谱融合
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
        "runner": "variable",
        "variable": "remote_amplitudes",
        "top_k": 8,
        "channel_weight": "energy_ratio",
    },
    "PCA-HP Remote top16/ch-η": {
        "runner": "variable",
        "variable": "remote_amplitudes",
        "top_k": 16,
        "channel_weight": "energy_ratio",
    },
    "PCA-Modal3 top8/ch-η": {
        "runner": "modal",
        "modal_variables": MODAL_PCA_VARIABLES,
        "channel_weight": "energy_ratio",
        "modal_weight": "energy_ratio",
        "top_k_channels": 8,
    },
    "PCA-Modal3 top16/ch-η": {
        "runner": "modal",
        "modal_variables": MODAL_PCA_VARIABLES,
        "channel_weight": "energy_ratio",
        "modal_weight": "energy_ratio",
        "top_k_channels": 16,
    },
    "PCA-Cmplx Total top8/ch-η": {
        "runner": "complex",
        "amp_var": "amplitudes",
        "channel_weight": "energy_ratio",
        "top_k_channels": 8,
    },
}

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

REQUIRED_PCA_V2_CACHE_KEYS = (
    "PCA-Modal3 top2/ch-η",
    "PCA-Cmplx-Modal rem+loc top2",
    "PCA-Cmplx η-blend ch-η",
    "PCA-Modal3 top8/ch-η",
    "PCA-HP Remote top8/ch-η",
)
scenario = load_scenario(SCENARIO_ID, project_root=project_root)
filepath = scenario.resolve_data_path(project_root)
segment_config = scenario.segment_config
print_scenario_summary(scenario)

filter_params = FilterParams()
metric_params = BreathMetricParams()
chfusion_config = ChFusionConfig(
    breath_freq_low=metric_params.breath_freq_low,
    breath_freq_high=metric_params.breath_freq_high,
    window_length_sec=metric_params.window_length_sec,
    step_length_sec=metric_params.step_length_sec,
    enable_consensus=False,
)

plan2_config = Plan2Config(channel_metric="energy_ratio")

pca_svd_config = PcaSvdConfig(
    method="pca",
    normalize="zscore",
    min_channels=4,
    min_variance_ratio=0.10,
    signal_key="bandpass_filtered",
    breath_freq_low=metric_params.breath_freq_low,
    breath_freq_high=metric_params.breath_freq_high,
)

pca_hp_config = PcaSvdConfig(
    method="pca",
    normalize="zscore",
    min_channels=4,
    min_variance_ratio=0.10,
    signal_key="highpass_filtered",
    breath_freq_low=metric_params.breath_freq_low,
    breath_freq_high=metric_params.breath_freq_high,
)

variables = [v[0] for v in CS_SIGNAL_VARIABLES]
print("Variables:", ", ".join(f"{k} ({lbl})" for k, lbl in CS_SIGNAL_VARIABLES))
print("PCA/SVD normalize:", pca_svd_config.normalize)
print("PCA/SVD min_channels:", pca_svd_config.min_channels)

# %% [markdown]
# ## 1. Multi-channel filtering (4 variables x 72 channels)

# %%
# data 为原始 DataFrame，仅 frames 参与后续处理
data, frames = load_ble_frames(filepath, verbose=False)

multichannel_by_var = {}
fs = None
for variable in variables:
    mc, fs = run_multichannel_segment_filtering(
        frames,
        segment_config,
        variable=variable,
        filter_params=filter_params,
        verbose=True,
    )
    multichannel_by_var[variable] = mc

print(f"\n采样率: {fs:.2f} Hz")

# %% [markdown]
# ## 2. Baseline BPM (Single / Uniform / q_energy_peak)

# %%
baseline_methods = ("single", "uniform", "q_energy_peak")
baseline_results = estimate_segment_bpm_methods(
    multichannel_by_var["remote_amplitudes"],
    variable="remote_amplitudes",
    config=chfusion_config,
    metric_params=metric_params,
    methods=baseline_methods,
    single_channel_metric="energy_ratio",
    verbose=True,
)

print(f"Baseline ({len(baseline_results)} segments) completed")

# %% [markdown]
# ## 3a. Helpers — BPM estimation via PCA/SVD (reuse chfusion metrics)

# %%


def window_bpm_from_waveform(waveform, fs, breath_freq_low, breath_freq_high):
    """对提取的呼吸波形做 FFT 估计 BPM（与 Single 基线相同的峰频法）。"""
    if len(waveform) < 4 or not np.all(np.isfinite(waveform)):
        return np.nan
    wf = waveform - np.mean(waveform)
    f_hz = _estimate_breathing_freq_hz(wf, fs, breath_freq_low, breath_freq_high)
    return f_hz * 60.0 if np.isfinite(f_hz) else np.nan


def _segment_rel_err_pct(errs: list[float]) -> tuple[float, float, int]:
    """段级相对误差比例 → 百分比（与 ``_overall_rel_error`` 一致）。"""
    if not errs:
        return np.nan, np.nan, 0
    a = np.asarray(errs, dtype=float)
    std = float(np.std(a, ddof=1) * 100.0) if len(a) > 1 else 0.0
    return float(np.mean(a) * 100.0), std, len(a)


def run_pca_svd_bpm(
    multichannel_by_var,
    segment_config,
    *,
    method,
    variable_or_vars,
    fs,
    metric_params,
    pca_svd_config=None,
    complex_amp_var=None,
    verbose=True,
):
    """对每个呼吸段做滑窗 PCA/SVD -> BPM 估计。"""
    pca_cfg = pca_svd_config or PcaSvdConfig()
    mp = metric_params
    win_len = int(round(mp.window_length_sec * fs))
    step_len = int(round(mp.step_length_sec * fs))
    results = {}

    if isinstance(variable_or_vars, str):
        var_list = [variable_or_vars]
        is_stack = False
        label = variable_or_vars
    else:
        var_list = list(variable_or_vars)
        is_stack = True
        label = "+".join(var_list)

    if verbose:
        print(f"\n--- {method.upper()} on {label} ---")

    for seg_name in sorted(segment_config.keys()):
        seg_cfg = segment_config[seg_name]
        ref_mc = multichannel_by_var.get(
            var_list[0] if not is_stack else "remote_amplitudes", {}
        )
        ref_seg = ref_mc.get(seg_name)
        metadata = ref_seg.get("metadata", {}) if ref_seg else {}
        if metadata.get("segment_type") == "apnea" or seg_cfg.get("type") == "apnea":
            results[seg_name] = None
            continue

        bpm_gt = metadata.get("bpm_gt") or seg_cfg.get("bpm_gt")
        if is_stack:
            ch_lengths = {}
            for var in var_list:
                mc = multichannel_by_var.get(var, {})
                seg = mc.get(seg_name)
                if seg is None or seg.get("channels") is None:
                    continue
                for ch, proc in seg["channels"].items():
                    sig = proc[var].get(pca_cfg.signal_key)
                    if sig is not None:
                        ch_lengths[ch] = min(ch_lengths.get(ch, len(sig)), len(sig))
            ch_list = sorted(k for k in ch_lengths if ch_lengths[k] >= win_len)
            ref_len = max(ch_lengths[c] for c in ch_list) if ch_list else 0
        else:
            var = var_list[0]
            mc = multichannel_by_var.get(var, {})
            seg = mc.get(seg_name)
            if seg is None or seg.get("channels") is None:
                results[seg_name] = None
                continue
            ch_map = seg["channels"]
            ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
            ref_len = max(len(ch_map[c][var].get(pca_cfg.signal_key, [])) for c in ch_list)

        if ref_len < win_len:
            if verbose:
                print(f"  WARN {seg_name}: len={ref_len} < win={win_len}")
            results[seg_name] = None
            continue

        starts = _sliding_window_indices(ref_len, win_len, step_len)
        bpms = []
        prev_wf = None
        pc1_ratios = []

        for st in starts:
            end_val = st + win_len

            sk = pca_cfg.signal_key
            if method in ("svd_complex", "pca_complex") and not is_stack:
                amp_var = complex_amp_var or "amplitudes"
                mc_amp = multichannel_by_var.get(amp_var, {})
                mc_pha = multichannel_by_var.get("phases", {})
                seg_amp = mc_amp.get(seg_name)
                seg_pha = mc_pha.get(seg_name)
                if seg_amp is None or seg_pha is None:
                    bpms.append(np.nan)
                    continue
                ch_map_amp = seg_amp["channels"]
                ch_map_pha = seg_pha["channels"]
                cols_c, used = [], []
                for ch in ch_list:
                    pa = ch_map_amp.get(ch)
                    pp = ch_map_pha.get(ch)
                    if pa is None or pp is None:
                        continue
                    ba = pa[amp_var].get(sk)
                    bp = pp["phases"].get(sk)
                    if ba is None or bp is None or len(ba) < end_val or len(bp) < end_val:
                        continue
                    cols_c.append(ba[st:end_val] * np.exp(1j * bp[st:end_val]))
                    used.append(ch)
                if len(cols_c) < pca_cfg.min_channels:
                    bpms.append(np.nan)
                    continue
                X_c = np.column_stack(cols_c)
                ch_w = None
                if pca_cfg.channel_weight == "energy_ratio":
                    ch_w = compute_channel_energy_weights(
                        ch_map_amp, amp_var, used, st, end_val, fs, pca_cfg
                    )
                if method == "pca_complex":
                    waveform, info = extract_breath_waveform_complex_pca(
                        X_c, pca_cfg, seg_name, channel_weights=ch_w
                    )
                else:
                    waveform, info = extract_breath_waveform_complex_svd(X_c, pca_cfg, seg_name)
            elif not is_stack:
                X, used_ch = build_channel_data_matrix(
                    ch_map, var, ch_list, st, end_val, sk
                )
                if X.shape[1] < pca_cfg.min_channels:
                    bpms.append(np.nan)
                    continue
                ch_w = None
                if pca_cfg.channel_weight == "energy_ratio":
                    ch_w = compute_channel_energy_weights(
                        ch_map, var, used_ch, st, end_val, fs, pca_cfg
                    )
                if method == "pca":
                    waveform, info = extract_breath_waveform_pca(
                        X, pca_cfg, seg_name, channel_weights=ch_w
                    )
                else:
                    waveform, info = extract_breath_waveform_svd(X, pca_cfg, seg_name)
            else:
                ch_maps = {
                    v: multichannel_by_var.get(v, {}).get(seg_name, {}).get("channels", {})
                    for v in var_list
                }
                X = build_multivariable_data_matrix(
                    ch_maps, var_list, ch_list, st, end_val, sk
                )
                if X.shape[1] < pca_cfg.min_channels:
                    bpms.append(np.nan)
                    continue
                if method == "pca":
                    waveform, info = extract_breath_waveform_pca(X, pca_cfg, seg_name)
                else:
                    waveform, info = extract_breath_waveform_svd(X, pca_cfg, seg_name)

            pc1_ratios.append(info.get("pc1_variance_ratio", np.nan))
            waveform = align_waveform_sign(waveform, prev_wf)
            prev_wf = waveform.copy()
            bpm = window_bpm_from_waveform(waveform, fs, mp.breath_freq_low, mp.breath_freq_high)
            bpms.append(bpm)

        bpm_arr = np.asarray(bpms, dtype=float)
        n_wins = len(starts)
        stats = _seg_bpm_stats(bpm_arr, bpm_gt, n_wins)
        stats["bpm_gt"] = bpm_gt
        stats["pc1_variance_ratios"] = pc1_ratios
        stats["mean_pc1_ratio"] = float(np.nanmean(pc1_ratios)) if pc1_ratios else np.nan
        results[seg_name] = stats

        if verbose:
            e = stats["bpm_rel_err"]
            err_str = f"{e * 100:.2f}%" if np.isfinite(e) else "---"
            print(f"  {seg_name}: mean_rel_err={err_str}  pc1_ratio={stats['mean_pc1_ratio']:.3f}")

    return results


# %% [markdown]
# ## 3b. Run PCA/SVD BPM estimation (12 methods)

# %%

pca_svd_results = {}
for exp_name, exp_cfg in PCA_SVD_EXPERIMENTS.items():
    print(f"\n{'=' * 60}")
    print(f"Running: {exp_name}")
    print(f"{'=' * 60}")
    result = run_pca_svd_bpm(
        multichannel_by_var,
        segment_config,
        method=exp_cfg["method"],
        variable_or_vars=exp_cfg["variable"],
        complex_amp_var=exp_cfg.get("complex_amp_var"),
        fs=fs,
        metric_params=metric_params,
        pca_svd_config=pca_svd_config,
        verbose=True,
    )
    pca_svd_results[exp_name] = result

print(f"\nOK {len(pca_svd_results)} PCA/SVD methods completed")

# %% [markdown]
# ## 3c. PCA v2 — highpass + channel η-weight + PCA modal / complex PCA
#
# 默认用 ``highpass_filtered``；PCA 作多信道提取，再按 Plan2 框架做模态谱融合。

# %%


def _modal_to_per_seg(modal_raw, method_key):
    """将 ``run_pca_modal_fusion`` 输出转为与其它实验一致的 per-seg dict。"""
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


def run_pca_v2_suite(
    multichannel_by_var,
    segment_config,
    fs,
    metric_params,
    pca_hp_cfg,
    *,
    verbose=True,
):
    """高通 PCA 单变量 + PCA 模态融合 + 复 PCA。"""
    pca_v2 = {}
    for exp_name, exp_cfg in PCA_V2_EXPERIMENTS.items():
        cfg = replace(pca_hp_cfg, channel_weight=exp_cfg["channel_weight"])
        if verbose:
            print(f"\n--- PCA v2: {exp_name} ---")
        pca_v2[exp_name] = run_pca_svd_bpm(
            multichannel_by_var,
            segment_config,
            method=exp_cfg["method"],
            variable_or_vars=exp_cfg["variable"],
            fs=fs,
            metric_params=metric_params,
            pca_svd_config=cfg,
            verbose=verbose,
        )
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
        top_suffix = (
            f"_top{exp_cfg['top_k_channels']}" if exp_cfg.get("top_k_channels") else ""
        )
        mkey = (
            f"pca_modal_{exp_cfg['modal_weight']}_ch_{exp_cfg['channel_weight']}{top_suffix}"
        )
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
        top_suffix = (
            f"_top{exp_cfg['top_k_channels']}" if exp_cfg.get("top_k_channels") else ""
        )
        ckey = (
            f"pca_complex_{exp_cfg['amp_var']}_ch_{exp_cfg['channel_weight']}{top_suffix}"
        )
        pca_v2[exp_name] = _modal_to_per_seg(raw, ckey)
    for exp_name, exp_cfg in PCA_COMPLEX_INTEGRATION_EXPERIMENTS.items():
        cfg = replace(pca_hp_cfg, channel_weight=exp_cfg.get("channel_weight", "uniform"))
        runner = exp_cfg["runner"]
        if verbose:
            print(f"\n--- PCA integration: {exp_name} ---")
        if runner == "dual_amp":
            raw = run_pca_complex_dual_amp(
                multichannel_by_var,
                channel_weight=exp_cfg["channel_weight"],
                metric_params=metric_params,
                pca_svd_config=cfg,
                verbose=verbose,
            )
            ikey = f"pca_complex_dual_amp_ch_{exp_cfg['channel_weight']}"
        elif runner == "eta_blend":
            raw = run_pca_complex_eta_blend(
                multichannel_by_var,
                channel_weight=exp_cfg["channel_weight"],
                metric_params=metric_params,
                pca_svd_config=cfg,
                verbose=verbose,
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
            ikey = (
                f"pca_complex_modal_{exp_cfg['modal_weight']}_ch_{exp_cfg['channel_weight']}"
            )
        pca_v2[exp_name] = _modal_to_per_seg(raw, ikey)
    for exp_name, exp_cfg in PCA_TOPK_EXPERIMENTS.items():
        cfg = replace(pca_hp_cfg, channel_weight=exp_cfg.get("channel_weight", "energy_ratio"))
        runner = exp_cfg["runner"]
        if verbose:
            print(f"\n--- PCA top-K: {exp_name} ---")
        if runner == "variable":
            raw = run_pca_topk_bpm(
                multichannel_by_var,
                variable=exp_cfg["variable"],
                top_k=exp_cfg["top_k"],
                channel_weight=exp_cfg["channel_weight"],
                metric_params=metric_params,
                pca_svd_config=cfg,
                verbose=verbose,
            )
            tkey = (
                f"pca_topk_{exp_cfg['variable']}_k{exp_cfg['top_k']}"
                f"_ch_{exp_cfg['channel_weight']}"
            )
        elif runner == "modal":
            raw = run_pca_modal_fusion(
                multichannel_by_var,
                modal_variables=exp_cfg["modal_variables"],
                channel_weight=exp_cfg["channel_weight"],
                modal_weight=exp_cfg["modal_weight"],
                top_k_channels=exp_cfg["top_k_channels"],
                metric_params=metric_params,
                pca_svd_config=cfg,
                verbose=verbose,
            )
            tkey = (
                f"pca_modal_{exp_cfg['modal_weight']}_ch_{exp_cfg['channel_weight']}"
                f"_top{exp_cfg['top_k_channels']}"
            )
        else:
            raw = run_pca_complex_fusion(
                multichannel_by_var,
                amp_var=exp_cfg["amp_var"],
                channel_weight=exp_cfg["channel_weight"],
                top_k_channels=exp_cfg["top_k_channels"],
                metric_params=metric_params,
                pca_svd_config=cfg,
                verbose=verbose,
            )
            tkey = (
                f"pca_complex_{exp_cfg['amp_var']}_ch_{exp_cfg['channel_weight']}"
                f"_top{exp_cfg['top_k_channels']}"
            )
        pca_v2[exp_name] = _modal_to_per_seg(raw, tkey)
    return pca_v2


pca_v2_results = run_pca_v2_suite(
    multichannel_by_var, segment_config, fs, metric_params, pca_hp_config, verbose=True
)
pca_svd_results.update(pca_v2_results)
print(f"\nOK PCA v2: {len(pca_v2_results)} additional methods")

# %% [markdown]
# ## 3d. Plan 2 validation (same scenario, same metrics)

# %%

plan2 = run_plan2_validation(
    frames,
    segment_config,
    filter_params=filter_params,
    metric_params=metric_params,
    config=chfusion_config,
    plan2_config=plan2_config,
    reference_variable="phases",
    verbose=True,
)

plan2_leaderboard = build_plan2_leaderboard_rows(plan2)
print(f"Plan 2 methods: {len(plan2_leaderboard)} entries")

# %% [markdown]
# ## 4. Unified leaderboard  —  PCA/SVD + baseline + Plan 2
#
# 误差指标与 Plan 2 一致：各 breath 段窗级相对误差均值，再对段取平均，单位为 %。

# %%

METHOD_CATEGORY_COLORS = {
    "PCA": "#5A9BD5",
    "PCA HP": "#4A8BC2",
    "PCA Modal": "#9B7FBF",
    "SVD": "#70AD47",
    "SVD Complex": "#BF8FBF",
    "Stacked": "#EDB144",
    "Baseline": "#F0C8A0",
    "Single": "#E8A0A0",
    "Uniform": "#F0C8A0",
    "Modal": "#C9A0DC",
    "Plan2": "#C9A0DC",
}


def _category_color(label: str, category=None) -> str:
    if category:
        return METHOD_CATEGORY_COLORS.get(category, "#CCCCCC")
    if label.startswith("SVD Complex"):
        return METHOD_CATEGORY_COLORS["SVD Complex"]
    return METHOD_CATEGORY_COLORS.get(label.split()[0], "#CCCCCC")


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


def run_scenario_pipeline(
    scenario_id: str,
    *,
    project_root,
    filter_params,
    metric_params,
    chfusion_config,
    plan2_config,
    pca_svd_config,
    pca_hp_cfg=None,
    verbose: bool = True,
) -> dict:
    """单场景完整流程：滤波 → PCA/SVD → Plan2 → 排行榜。"""
    sc = load_scenario(scenario_id, project_root=project_root)
    _data, run_frames = load_ble_frames(sc.resolve_data_path(project_root), verbose=False)
    seg_cfg = sc.segment_config
    vars_list = [v[0] for v in CS_SIGNAL_VARIABLES]

    mc_by_var = {}
    run_fs = None
    for variable in vars_list:
        mc, run_fs = run_multichannel_segment_filtering(
            run_frames,
            seg_cfg,
            variable=variable,
            filter_params=filter_params,
            verbose=verbose,
        )
        mc_by_var[variable] = mc

    baseline = estimate_segment_bpm_methods(
        mc_by_var["remote_amplitudes"],
        variable="remote_amplitudes",
        config=chfusion_config,
        metric_params=metric_params,
        methods=("single", "uniform", "q_energy_peak"),
        single_channel_metric="energy_ratio",
        verbose=verbose,
    )

    pca_results = {}
    for exp_name, exp_cfg in PCA_SVD_EXPERIMENTS.items():
        if verbose:
            print(f"\n--- [{sc.tag}] {exp_name} ---")
        pca_results[exp_name] = run_pca_svd_bpm(
            mc_by_var,
            seg_cfg,
            method=exp_cfg["method"],
            variable_or_vars=exp_cfg["variable"],
            complex_amp_var=exp_cfg.get("complex_amp_var"),
            fs=run_fs,
            metric_params=metric_params,
            pca_svd_config=pca_svd_config,
            verbose=verbose,
        )

    hp_cfg = pca_hp_cfg or pca_hp_config
    pca_results.update(
        run_pca_v2_suite(
            mc_by_var, seg_cfg, run_fs, metric_params, hp_cfg, verbose=verbose
        )
    )

    plan2_out = run_plan2_validation(
        run_frames,
        seg_cfg,
        filter_params=filter_params,
        metric_params=metric_params,
        config=chfusion_config,
        plan2_config=plan2_config,
        reference_variable="phases",
        verbose=verbose,
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


def build_leaderboard(pca_svd_results, baseline_results, plan2_rows=None):
    """构建统一排行榜（``mean_rel_err_pct`` 已为百分比）。"""
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

    rows.sort(key=lambda r: (
        r["mean_rel_err_pct"] if np.isfinite(r["mean_rel_err_pct"]) else 999
    ))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


leaderboard = build_leaderboard(pca_svd_results, baseline_results, plan2_leaderboard)

# ---- 文本排名 ----
print("\n" + "=" * 72)
print(f"  chFusion PCA/SVD  —  Leaderboard")
print(f"  Scenario: {scenario.tag} ({SCENARIO_ID})")
print("=" * 72)
print(f"  {'Rank':>4}  {'方法':<32} {'err%':>7} {'±std%':>7}  {'类别':<10} {'来源'}")
print("  " + "-" * 72)
for r in leaderboard:
    e = f"{r['mean_rel_err_pct']:.2f}" if np.isfinite(r["mean_rel_err_pct"]) else "  ---"
    s = f"{r['std_rel_err_pct']:.2f}"
    mark = " ★" if r["rank"] == 1 else ""
    print(
        f"  {r['rank']:>4}{mark} {r['label']:<32} {e:>7} {s:>7}  "
        f"{r['category']:<10} {r.get('source', '')}"
    )

best = leaderboard[0]
print(f"\n  ★ 全局最优: {best['label']}  →  {best['mean_rel_err_pct']:.2f}%")
pca_only = [r for r in leaderboard if r.get("source") == "pca_svd"]
if pca_only:
    print(f"  PCA/SVD 最优: {pca_only[0]['label']} ({pca_only[0]['mean_rel_err_pct']:.2f}%)")
    print(f"  PCA/SVD 最差: {pca_only[-1]['label']} ({pca_only[-1]['mean_rel_err_pct']:.2f}%)")
plan2_only = [r for r in leaderboard if r.get("source") == "plan2"]
if plan2_only:
    print(f"  Plan2 最优: {plan2_only[0]['label']} ({plan2_only[0]['mean_rel_err_pct']:.2f}%)")
print()

# ---- 横向柱状图 ----
fig_h = max(5.5, 0.36 * len(leaderboard) + 2.0)
fig, ax = plt.subplots(figsize=(10.5, fig_h))
labels = [r["label"] for r in leaderboard]
means = np.asarray([r["mean_rel_err_pct"] for r in leaderboard], dtype=float)
colors = [r["color"] for r in leaderboard]
y = np.arange(len(leaderboard))

ax.barh(y, means, color=colors, edgecolor="black", alpha=0.85, height=0.72)
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=9)
ax.invert_yaxis()
ax.set_xlabel("Mean relative BPM error (%)")
ax.set_title("chFusion unified leaderboard — PCA/SVD vs baseline vs Plan 2")
ax.grid(True, axis="x", alpha=0.25)

for i, (m, r) in enumerate(zip(means, leaderboard)):
    txt = f"{m:.2f}%" if np.isfinite(m) else "---"
    ax.text(m + 0.25, i, txt, va="center", fontsize=8)

# 分类图例
seen_cats = set()
handles = []
for r in leaderboard:
    cat = r["category"]
    if cat not in seen_cats:
        seen_cats.add(cat)
        handles.append(plt.Rectangle(
            (0, 0), 1, 1, color=r["color"], ec="black",
            alpha=0.85, label=cat
        ))
ax.legend(handles=handles, loc="lower right", fontsize=8, title="Category")

plt.tight_layout()
bar_path = FIGURES_DIR / f"pca_svd_{scenario.tag}_leaderboard_bars.pdf"
fig.savefig(bar_path, dpi=150, bbox_inches="tight")
print(f"  Fig 1: Leaderboard bars  ->  {bar_path.name}")
plt.show()

# %% [markdown]
# ## 5. Segment × method heatmap
#
# 每行=呼吸段, 每列=方法, 格子=该段该方法 mean rel err%。

# %%

seg_names = sorted(
    k for k, v in pca_svd_results.get("PCA Total Amp", {}).items() if v is not None
)
all_meth_labels = [r["label"] for r in leaderboard]
matrix = np.full((len(seg_names), len(all_meth_labels)), np.nan)

for j, row_data in enumerate(leaderboard):
    label = row_data["label"]
    source = row_data.get("source")
    if source == "pca_svd" and label in pca_svd_results:
        per_seg = pca_svd_results[label]
        for i, seg_name in enumerate(seg_names):
            stats = per_seg.get(seg_name)
            if stats is not None:
                err = stats.get("bpm_rel_err", np.nan)
                matrix[i, j] = float(err) * 100.0 if np.isfinite(err) else np.nan
    elif source == "baseline":
        bmap = {
            "Single (remote amp)": "fft_single_max_energy",
            "Uniform (remote amp)": "fft_uniform_fusion",
            "q_energy_peak (remote amp)": "fft_q_energy_peak_fusion",
        }
        bkey = bmap.get(label)
        if bkey:
            for i, seg_name in enumerate(seg_names):
                seg_out = baseline_results.get(seg_name)
                if seg_out is not None and bkey in seg_out:
                    err = seg_out[bkey].get("bpm_rel_err", np.nan)
                    matrix[i, j] = float(err) * 100.0 if np.isfinite(err) else np.nan
    elif source == "plan2":
        plan2_lookup = {r["label"]: r for r in plan2_leaderboard}
        spec = plan2_lookup.get(label)
        if spec is None:
            continue
        results = (
            plan2["variable_baselines"][spec["baseline_var"]]
            if spec.get("baseline_var") is not None
            else plan2["modal_benchmark"]["results"]
        )
        result_key = spec["result_key"]
        for i, seg_name in enumerate(seg_names):
            row = results.get(seg_name)
            if row is None:
                continue
            block = row.get(result_key)
            if block is None:
                continue
            err = block.get("bpm_rel_err", np.nan)
            matrix[i, j] = float(err) * 100.0 if np.isfinite(err) else np.nan

row_labels = []
for seg in seg_names:
    gt = segment_config[seg].get("bpm_gt", np.nan)
    row_labels.append(f"{seg}\nGT={gt:.1f}" if np.isfinite(gt) else seg)

fig_w = max(12.0, 0.55 * len(all_meth_labels) + 4.0)
fig, ax = plt.subplots(figsize=(fig_w, max(4.5, 0.55 * len(seg_names) + 2.0)))
vmax = float(np.nanpercentile(matrix, 95)) if np.any(np.isfinite(matrix)) else 30.0
vmax = max(vmax, 2.0)
im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=0.0, vmax=vmax)
ax.set_xticks(np.arange(len(all_meth_labels)))
ax.set_yticks(np.arange(len(seg_names)))
ax.set_xticklabels(all_meth_labels, rotation=45, ha="right", fontsize=8)
ax.set_yticklabels(row_labels, fontsize=9)
ax.set_title("chFusion PCA/SVD — segment × method (cell = mean rel err%)")

for i in range(matrix.shape[0]):
    for j in range(matrix.shape[1]):
        val = matrix[i, j]
        if np.isfinite(val):
            tc = "white" if val > vmax * 0.6 else "black"
            ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                    fontsize=7, color=tc)

cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cbar.set_label("Rel. error (%)")
plt.tight_layout()
heatmap_path = FIGURES_DIR / f"pca_svd_{scenario.tag}_segment_method_heatmap.pdf"
fig.savefig(heatmap_path, dpi=150, bbox_inches="tight")
print(f"  Fig 2: Heatmap  ->  {heatmap_path.name}")
plt.show()

# %% [markdown]
# ## 6. PC1 variance ratio  —  table + bar chart
#
# PC1 方差占比越高说明呼吸信号在所有信道中的"共同模式"越明显。

# %%

pc1_records = []
for exp_name, per_seg in pca_svd_results.items():
    ratios = []
    for seg_name, seg_stats in per_seg.items():
        if seg_stats is None:
            continue
        r = seg_stats.get("mean_pc1_ratio", np.nan)
        if np.isfinite(r):
            ratios.append(r)
    if not ratios:
        continue
    arr = np.array(ratios)
    pc1_records.append({
        "label": exp_name,
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    })
pc1_records.sort(key=lambda x: -x["mean"])

print("\n  === PC1 方差占比统计 ===\n")
print(f"  {'方法':<25} {'Mean':>7} {'Std':>7} {'Min':>7} {'Max':>7}")
print("  " + "-" * 55)
for rec in pc1_records:
    print(f"  {rec['label']:<25} {rec['mean']:7.3f} {rec['std']:7.3f} "
          f"{rec['min']:7.3f} {rec['max']:7.3f}")
print()

# 柱状图
pc1_colors = {
    "PCA": "#5A9BD5", "SVD": "#70AD47",
    "SVD Complex": "#BF8FBF", "Stacked": "#EDB144",
}

fig, ax = plt.subplots(figsize=(10, max(5.5, 0.36 * len(pc1_records) + 1.5)))
labels_pc1 = [r["label"] for r in pc1_records]
means_pc1 = np.asarray([r["mean"] for r in pc1_records], dtype=float)
colors_pc1 = [
    pc1_colors.get(_pca_svd_category(r["label"]), "#CCCCCC") for r in pc1_records
]
y_pc1 = np.arange(len(pc1_records))

ax.barh(y_pc1, means_pc1, color=colors_pc1, edgecolor="black",
        alpha=0.85, height=0.72)
ax.set_yticks(y_pc1)
ax.set_yticklabels(labels_pc1, fontsize=9)
ax.invert_yaxis()
ax.set_xlabel("PC1 explained variance ratio")
ax.set_title("chFusion PCA/SVD — PC1 Variance Ratio (higher = stronger common mode)")
ax.grid(True, axis="x", alpha=0.25)
ax.axvline(0.30, color="red", ls="--", alpha=0.6, label="30% threshold")
ax.legend(fontsize=8)

for i, m in enumerate(means_pc1):
    ax.text(m + 0.02, i, f"{m:.2f}", va="center", fontsize=8)

plt.tight_layout()
pc1_path = FIGURES_DIR / f"pca_svd_{scenario.tag}_pc1_variance_ratio.pdf"
fig.savefig(pc1_path, dpi=150, bbox_inches="tight")
print(f"  Fig 3: PC1 variance  ->  {pc1_path.name}")
plt.show()

# %% [markdown]
# ## 7. Save results

# %%
output = {
    "scenario_id": SCENARIO_ID,
    "scenario_tag": scenario.tag,
    "segment_config": segment_config,
    "baseline_results": baseline_results,
    "pca_svd_results": pca_svd_results,
    "plan2_results": plan2,
    "plan2_leaderboard": plan2_leaderboard,
    "leaderboard": leaderboard,
    "pc1_analysis": pc1_records,
    "pca_svd_config": {
        "normalize": pca_svd_config.normalize,
        "min_channels": pca_svd_config.min_channels,
        "min_variance_ratio": pca_svd_config.min_variance_ratio,
    },
    "plan2_config": {"channel_metric": plan2_config.channel_metric},
}

report_path = REPORTS_DIR / f"chfusion_pca_svd_{scenario.tag}.npy"
np.save(report_path, output, allow_pickle=True)

print(f"\n{'=' * 60}")
print("  DONE — chFusion PCA/SVD")
print(f"{'=' * 60}")
print(f"  场景: {scenario.tag} ({SCENARIO_ID})")
print(f"  最优: {best['label']}  ({best['mean_rel_err_pct']:.2f}%)")
print(f"  图表: {bar_path.name}, {heatmap_path.name}, {pc1_path.name}")
print(f"  报告: {report_path.name}")
print(f"{'=' * 60}")

# %% [markdown]
# ## 8. Cross-scenario aggregate (cs_091339 / cs_095806 / cs_102621)
#
# 对三场景各方法 mean err% 取跨域均值；误差线为跨场景标准差。

# %%


def _leaderboard_lookup(leaderboard_rows: list) -> dict:
    return {r["label"]: r for r in leaderboard_rows}


def ensure_scenario_report(scenario_id: str, *, verbose: bool = False) -> dict:
    """加载缓存报告，缺失则运行完整 pipeline。"""
    sc = load_scenario(scenario_id, project_root=project_root)
    path = REPORTS_DIR / f"chfusion_pca_svd_{sc.tag}.npy"
    if scenario_id == SCENARIO_ID:
        return output
    if path.is_file():
        cached = np.load(path, allow_pickle=True).item()
        pca_res = cached.get("pca_svd_results", {})
        if all(k in pca_res for k in REQUIRED_PCA_V2_CACHE_KEYS):
            print(f"Loaded cached report: {path.name}")
            return cached
        print(f"Stale cache (missing PCA integration): {path.name}")
    print(f"Running PCA/SVD pipeline for {scenario_id} …")
    result = run_scenario_pipeline(
        scenario_id,
        project_root=project_root,
        filter_params=filter_params,
        metric_params=metric_params,
        chfusion_config=chfusion_config,
        plan2_config=plan2_config,
        pca_svd_config=pca_svd_config,
        pca_hp_cfg=pca_hp_config,
        verbose=verbose,
    )
    np.save(path, result, allow_pickle=True)
    print(f"Saved: {path.name}")
    return result


results_by_tag: dict[str, dict] = {}
for sid in COMPARE_SCENARIO_IDS:
    sc = load_scenario(sid, project_root=project_root)
    if sid == SCENARIO_ID:
        results_by_tag[sc.tag] = output
    else:
        results_by_tag[sc.tag] = ensure_scenario_report(sid, verbose=False)

compare_tags = [load_scenario(sid, project_root=project_root).tag for sid in COMPARE_SCENARIO_IDS]

print(f"\n{'=' * 72}")
print("  Cross-scenario leaderboard (mean err% per domain)")
print(f"  Scenarios: {' / '.join(compare_tags)}")
print("=" * 72)
col_w = 10
header = f"{'方法':<32}" + "".join(f"{t:>{col_w}}" for t in compare_tags) + f"{'mean':>8}{'±std':>8}"
print(header)
print("-" * (32 + col_w * len(compare_tags) + 16))

cross_rows = []
for lbl in CROSS_DOMAIN_COMPARE_LABELS:
    domain_errs = []
    for tag in compare_tags:
        row = _leaderboard_lookup(results_by_tag[tag]["leaderboard"]).get(lbl)
        val = row["mean_rel_err_pct"] if row else np.nan
        domain_errs.append(float(val) if np.isfinite(val) else np.nan)
    finite = [e for e in domain_errs if np.isfinite(e)]
    if not finite:
        continue
    mean_across = float(np.mean(finite))
    std_across = float(np.std(finite, ddof=1)) if len(finite) > 1 else 0.0
    cross_rows.append({
        "label": lbl,
        "domain_errs": domain_errs,
        "mean_across_domains": mean_across,
        "std_across_domains": std_across,
    })
    line = f"{lbl:<32}"
    for e in domain_errs:
        line += f"{e:>{col_w}.2f}" if np.isfinite(e) else f"{'—':>{col_w}}"
    line += f"{mean_across:>{col_w}.2f}{std_across:>8.2f}"
    print(line)

cross_rows.sort(key=lambda r: r["mean_across_domains"])
print(f"\n  ★ 跨场景综合最优: {cross_rows[0]['label']}  →  {cross_rows[0]['mean_across_domains']:.2f}% "
      f"± {cross_rows[0]['std_across_domains']:.2f}%")

# 跨场景柱状图
fig, ax = plt.subplots(figsize=(10, max(5.0, 0.38 * len(cross_rows) + 1.5)))
labels_cd = [r["label"] for r in cross_rows]
means_cd = np.asarray([r["mean_across_domains"] for r in cross_rows], dtype=float)
stds_cd = np.asarray([r["std_across_domains"] for r in cross_rows], dtype=float)
y_cd = np.arange(len(cross_rows))
ax.barh(y_cd, means_cd, xerr=stds_cd, color="#7B9FD4", edgecolor="black",
        alpha=0.85, height=0.72, capsize=3)
ax.set_yticks(y_cd)
ax.set_yticklabels(labels_cd, fontsize=9)
ax.invert_yaxis()
ax.set_xlabel("Mean relative BPM error (%) across scenarios")
ax.set_title("PCA/SVD + Plan2 — cross-domain aggregate (lower = better)")
ax.grid(True, axis="x", alpha=0.25)
for i, (m, s) in enumerate(zip(means_cd, stds_cd)):
    ax.text(m + s + 0.3, i, f"{m:.1f}±{s:.1f}%", va="center", fontsize=8)
plt.tight_layout()
cross_path = FIGURES_DIR / "pca_svd_cross_domain_aggregate_bars.pdf"
fig.savefig(cross_path, dpi=150, bbox_inches="tight")
print(f"\n  Fig 4: Cross-domain aggregate  ->  {cross_path.name}")
plt.show()

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

# %% [markdown]
# ## 9. cs_091339 复 PCA 整合失败诊断（η-blend / Dual-Amp）
#
# 统计窗级 BPM 与 GT 比值：fundamental / double / half / other，解释 091339 高误差来源。

# %%

from ble_analysis.pca_svd import diagnose_complex_integration_harmonics

DIAG_SCENARIO_ID = "cs_091339"
diag_sc = load_scenario(DIAG_SCENARIO_ID, project_root=project_root)
diag_tag = diag_sc.tag
if diag_tag not in results_by_tag:
    results_by_tag[diag_tag] = ensure_scenario_report(DIAG_SCENARIO_ID, verbose=False)
diag_mc = results_by_tag[diag_tag]["multichannel_by_var"]

print(f"\n{'=' * 72}")
print(f"  PC1 harmonic diagnosis — {diag_tag} ({DIAG_SCENARIO_ID})")
print("=" * 72)
print(f"  {'方法':<28} {'段':<12} {'GT':>5} {'err%':>7}  {'基频':>5} {'倍频':>5} {'半频':>5} {'其它':>5}")
print("  " + "-" * 72)

diag_summary = []
for method_label, integration in (
    ("η-blend ch-η", "eta_blend"),
    ("Dual-Amp ch-η", "dual_amp"),
):
    harm = diagnose_complex_integration_harmonics(
        diag_mc,
        integration=integration,
        channel_weight="energy_ratio",
        metric_params=metric_params,
        pca_svd_config=pca_hp_config,
    )
    for seg_name, row in sorted(harm.items()):
        if row is None:
            continue
        fr = row["harmonic_fracs"]
        err = row["mean_rel_err_pct"]
        gt = row["bpm_gt"]
        print(
            f"  {method_label:<28} {seg_name:<12} {gt:>5.0f} {err:>7.1f}  "
            f"{fr['fundamental']:>5.0%} {fr['double']:>5.0%} {fr['half']:>5.0%} {fr['other']:>5.0%}"
        )
        diag_summary.append({
            "method": method_label,
            "segment": seg_name,
            "bpm_gt": gt,
            "mean_rel_err_pct": err,
            **{f"frac_{k}": v for k, v in fr.items()},
        })

np.save(
    REPORTS_DIR / f"chfusion_pca_svd_{diag_tag}_harmonic_diag.npy",
    {"scenario_id": DIAG_SCENARIO_ID, "summary": diag_summary},
    allow_pickle=True,
)
print(f"\n  Saved: chfusion_pca_svd_{diag_tag}_harmonic_diag.npy")

# %% [markdown]
# ## 10. cs_091339 最差段 PC1 呼吸带谱 vs GT（P1 波形级对照）

# %%

from ble_analysis.pca_svd import extract_integration_pc1_spectrum

PLOT_INTEGRATIONS = (
    ("η-blend ch-η", "eta_blend"),
    ("Dual-Amp ch-η", "dual_amp"),
    ("Total ch-η", "total_complex"),
)

worst_seg = None
worst_err = -1.0
for seg_name, row in sorted(
    diagnose_complex_integration_harmonics(
        diag_mc,
        integration="eta_blend",
        channel_weight="energy_ratio",
        metric_params=metric_params,
        pca_svd_config=pca_hp_config,
    ).items()
):
    if row is None:
        continue
    err = row.get("mean_rel_err_pct", np.nan)
    if np.isfinite(err) and err > worst_err:
        worst_err = float(err)
        worst_seg = seg_name

if worst_seg:
    fig, axes = plt.subplots(1, len(PLOT_INTEGRATIONS), figsize=(4.2 * len(PLOT_INTEGRATIONS), 3.8))
    if len(PLOT_INTEGRATIONS) == 1:
        axes = [axes]
    mid_win = 0
    for ax, (label, integration) in zip(axes, PLOT_INTEGRATIONS):
        snap = extract_integration_pc1_spectrum(
            diag_mc,
            worst_seg,
            integration=integration,
            window_index=mid_win,
            channel_weight="energy_ratio",
            metric_params=metric_params,
            pca_svd_config=pca_hp_config,
        )
        if snap is None:
            ax.set_title(f"{label}\n(no data)")
            continue
        freqs_hz = snap["band_freqs"]
        spec = snap["spectrum"]
        ax.plot(freqs_hz * 60.0, spec, color="#2E6F9E", lw=1.5, label="PC1 norm. spec")
        if np.isfinite(snap["gt_hz"]):
            ax.axvline(snap["gt_hz"] * 60.0, color="#C44E52", ls="--", lw=1.2, label="GT BPM")
        if np.isfinite(snap["peak_hz"]):
            ax.axvline(
                snap["peak_hz"] * 60.0, color="#55A868", ls=":", lw=1.2, label="PC1 peak BPM"
            )
        ax.set_xlabel("BPM")
        ax.set_ylabel("Norm. power")
        ax.set_title(f"{label}\n{worst_seg} win={mid_win}")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.25)
    fig.suptitle(
        f"091339 worst segment PC1 breath-band spectrum ({worst_seg}, err≈{worst_err:.1f}%)",
        fontsize=10,
    )
    plt.tight_layout()
    spec_path = FIGURES_DIR / f"pca_svd_{diag_tag}_worst_seg_pc1_spectrum.pdf"
    fig.savefig(spec_path, dpi=150, bbox_inches="tight")
    print(f"\n  Fig 5: Worst-seg PC1 spectrum  ->  {spec_path.name}")
    plt.close(fig)
else:
    print("\n  Skip PC1 spectrum plot: no valid worst segment")
