"""Paper baseline waveform methods vs HKH GT on live breathing data.

Compares Fan 2024, Yu 2021 WiFi-Sleep, Zhuo 2023 (+ B2 refs) with BPM
error and waveform RMSE.

Run:
    python notebooks/scripts/chFusion_ble_hkh_paper_baselines.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.ble_hkh_paper_validation import run_hkh_paper_baselines_benchmark
from ble_analysis.ble_hkh_validation import load_hkh_gt_signals
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import ChFusionConfig, load_multichannel_for_scenario
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams

PAPER_COLORS = {
    "Fan2024": "#E07A5F",
    "Yu2021": "#3D405B",
    "Zhuo2023": "#81B29A",
    "B2": "#457B9D",
}


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]
CACHE_DIR = str(project_root / "outputs" / "cache")

SCENARIO_ID = "room_A-sbj_A-07101613"


def plot_paper_leaderboard(bench: dict, dataset_name: str) -> Path:
    rows = bench["leaderboard_bpm"]
    labels = [r["label"] for r in rows][::-1]
    means = [r["bpm_mean_abs_err"] for r in rows][::-1]
    stds = [r["bpm_std_abs_err"] for r in rows][::-1]
    colors = [PAPER_COLORS.get(r["paper"], "gray") for r in rows][::-1]

    fig_h = max(5.5, 0.38 * len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(14, fig_h))
    y = np.arange(len(labels))

    ax = axes[0]
    ax.barh(y, means, xerr=stds, capsize=3, color=colors, alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("BPM abs err vs HKH (breaths/min)")
    ax.set_title("Paper baselines — BPM error")

    rows_rmse = bench["leaderboard_rmse"]
    labels_r = [r["label"] for r in rows_rmse][::-1]
    rmse_m = [r["rmse_mean"] for r in rows_rmse][::-1]
    rmse_s = [r["rmse_std"] for r in rows_rmse][::-1]
    colors_r = [PAPER_COLORS.get(r["paper"], "gray") for r in rows_rmse][::-1]
    y2 = np.arange(len(labels_r))

    ax2 = axes[1]
    ax2.barh(y2, rmse_m, xerr=rmse_s, capsize=3, color=colors_r, alpha=0.9)
    ax2.set_yticks(y2)
    ax2.set_yticklabels(labels_r, fontsize=9)
    ax2.set_xlabel("Waveform RMSE vs HKH (z-score aligned)")
    ax2.set_title("Paper baselines — waveform RMSE")

    from matplotlib.patches import Patch
    legend = [
        Patch(facecolor=PAPER_COLORS[k], label=k) for k in ("Fan2024", "Yu2021", "Zhuo2023", "B2")
    ]
    fig.legend(handles=legend, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(f"HKH live breathing — WiFi paper baselines ({dataset_name})", y=1.01)
    fig.tight_layout()
    path = FIGURES_DIR / f"ble_hkh_paper_baselines_{dataset_name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


if __name__ == "__main__":
    filter_params = FilterParams()
    metric_params = BreathMetricParams()
    chfusion_config = ChFusionConfig(
        breath_freq_low=metric_params.breath_freq_low,
        breath_freq_high=metric_params.breath_freq_high,
        window_length_sec=metric_params.window_length_sec,
        step_length_sec=metric_params.step_length_sec,
    )

    scenario = load_scenario(SCENARIO_ID, project_root=project_root)
    print_scenario_summary(scenario)

    processed_dir = (project_root / Path(scenario.data_file)).parent
    hkh_bp, hkh_t, cs_t, preprocess_meta = load_hkh_gt_signals(processed_dir)
    fs_hkh = preprocess_meta.get("sampling_rate_hz", {}).get("hkh_used")

    multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=filter_params,
        cache_dir=CACHE_DIR,
        verbose=True,
    )

    print(f"\n=== Paper baselines vs HKH GT ({SCENARIO_ID}) ===")
    bench = run_hkh_paper_baselines_benchmark(
        multichannel_by_var,
        "main",
        hkh_bp,
        hkh_t,
        cs_t,
        config=chfusion_config,
        metric_params=metric_params,
        fs_hkh_override=fs_hkh,
        verbose=True,
    )

    report_json = REPORTS_DIR / f"ble_hkh_paper_baselines_{SCENARIO_ID}.json"
    slim = {
        "scenario_id": SCENARIO_ID,
        "preprocess_meta": preprocess_meta,
        "segment": bench["segment"],
        "leaderboard_bpm": bench["leaderboard_bpm"],
        "leaderboard_rmse": bench["leaderboard_rmse"],
    }
    with report_json.open("w", encoding="utf-8") as handle:
        json.dump(slim, handle, ensure_ascii=False, indent=2, default=_json_default)

    fig_path = plot_paper_leaderboard(bench, SCENARIO_ID)

    print("\n=== BPM leaderboard ===")
    print(f"{'Rank':<5} {'Paper':<10} {'Method':<42} {'BPM err':>16} {'RMSE':>12}")
    print("-" * 90)
    for row in bench["leaderboard_bpm"]:
        print(
            f"{row['rank']:<5} {row['paper']:<10} {row['label']:<42} "
            f"{row['bpm_mean_abs_err']:.2f}±{row['bpm_std_abs_err']:.2f} BPM"
            f"  {row['rmse_mean']:.3f}±{row['rmse_std']:.3f}"
        )

    print(f"\nSaved JSON: {report_json}")
    print(f"Saved figure: {fig_path}")
