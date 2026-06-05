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
- **SVD Complex**            : 总幅值+j总相位 72 道复 SVD
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

# %% [markdown]
# ## 0. Environment bootstrap

# %%
import sys
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
    PcaSvdConfig,
    align_waveform_sign,
    build_multivariable_data_matrix,
    extract_breath_waveform_complex_svd,
    extract_breath_waveform_pca,
    extract_breath_waveform_svd,
)
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams

SCENARIO_ID = "cs_102621"
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
                    bp = proc[var].get("bandpass_filtered")
                    if bp is not None:
                        ch_lengths[ch] = min(ch_lengths.get(ch, len(bp)), len(bp))
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
            ref_len = max(len(ch_map[c][var].get("bandpass_filtered", [])) for c in ch_list)

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

            if method == "svd_complex" and not is_stack:
                mc_amp = multichannel_by_var.get("amplitudes", {})
                mc_pha = multichannel_by_var.get("phases", {})
                seg_amp = mc_amp.get(seg_name)
                seg_pha = mc_pha.get(seg_name)
                if seg_amp is None or seg_pha is None:
                    bpms.append(np.nan)
                    continue
                ch_map_amp = seg_amp["channels"]
                ch_map_pha = seg_pha["channels"]
                cols_a, cols_p = [], []
                for ch in ch_list:
                    pa = ch_map_amp.get(ch)
                    pp = ch_map_pha.get(ch)
                    if pa is None or pp is None:
                        continue
                    bp_a = pa["amplitudes"].get("bandpass_filtered")
                    bp_p = pp["phases"].get("bandpass_filtered")
                    if bp_a is None or bp_p is None or len(bp_a) < end_val or len(bp_p) < end_val:
                        continue
                    cols_a.append(bp_a[st:end_val])
                    cols_p.append(bp_p[st:end_val])
                if len(cols_a) < pca_cfg.min_channels:
                    bpms.append(np.nan)
                    continue
                X_r = np.column_stack(cols_a).astype(float)
                X_p = np.column_stack(cols_p).astype(float)
                X_c = X_r * np.exp(1j * X_p)
                waveform, info = extract_breath_waveform_complex_svd(X_c, pca_cfg, seg_name)
            elif not is_stack:
                cols = []
                for ch in ch_list:
                    proc = ch_map.get(ch)
                    if proc is None:
                        continue
                    bp = proc[var].get("bandpass_filtered")
                    if bp is None or len(bp) < end_val:
                        continue
                    cols.append(bp[st:end_val])
                if len(cols) < pca_cfg.min_channels:
                    bpms.append(np.nan)
                    continue
                X = np.column_stack(cols).astype(float)
                if method == "pca":
                    waveform, info = extract_breath_waveform_pca(X, pca_cfg, seg_name)
                else:
                    waveform, info = extract_breath_waveform_svd(X, pca_cfg, seg_name)
            else:
                ch_maps = {
                    v: multichannel_by_var.get(v, {}).get(seg_name, {}).get("channels", {})
                    for v in var_list
                }
                X = build_multivariable_data_matrix(ch_maps, var_list, ch_list, st, end_val)
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
# ## 3b. Run PCA/SVD BPM estimation (10 methods)

# %%

PCA_SVD_EXPERIMENTS = {
    "PCA Remote Amp": {"method": "pca", "variable": "remote_amplitudes"},
    "PCA Local Amp": {"method": "pca", "variable": "local_amplitudes"},
    "PCA Total Amp": {"method": "pca", "variable": "amplitudes"},
    "SVD Remote Amp": {"method": "svd_real", "variable": "remote_amplitudes"},
    "SVD Local Amp": {"method": "svd_real", "variable": "local_amplitudes"},
    "SVD Total Amp": {"method": "svd_real", "variable": "amplitudes"},
    "PCA Phase": {"method": "pca", "variable": "phases"},
    "SVD Phase": {"method": "svd_real", "variable": "phases"},
    "SVD Complex": {"method": "svd_complex", "variable": "amplitudes"},
    "PCA Stacked": {
        "method": "pca",
        "variable": ["remote_amplitudes", "local_amplitudes", "amplitudes"],
    },
}

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
        fs=fs,
        metric_params=metric_params,
        pca_svd_config=pca_svd_config,
        verbose=True,
    )
    pca_svd_results[exp_name] = result

print(f"\nOK {len(pca_svd_results)} PCA/SVD methods completed")

# %% [markdown]
# ## 3c. Plan 2 validation (same scenario, same metrics)

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
    cat = category or label.split()[0]
    return METHOD_CATEGORY_COLORS.get(cat, "#CCCCCC")


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
        cat = exp_name.split()[0]
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
colors_pc1 = [pc1_colors.get(r["label"].split()[0], "#CCCCCC") for r in pc1_records]
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
