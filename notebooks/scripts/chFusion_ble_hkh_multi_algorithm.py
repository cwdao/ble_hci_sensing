"""Multi-algorithm benchmark vs HKH ground truth on live breathing data.

Run:
    python notebooks/scripts/chFusion_ble_hkh_multi_algorithm.py
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

from ble_analysis.ble_hkh_multi_validation import run_hkh_multi_algorithm_benchmark
from ble_analysis.ble_hkh_validation import load_hkh_gt_signals
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import ChFusionConfig, load_multichannel_for_scenario
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams


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


def plot_leaderboard(bench: dict, dataset_name: str) -> Path:
    rows = bench["leaderboard"][:15]
    labels = [r["label"] for r in rows][::-1]
    means = [r["bpm_mean_abs_err"] for r in rows][::-1]
    stds = [r["bpm_std_abs_err"] for r in rows][::-1]

    fig_h = max(6, 0.35 * len(labels))
    fig, ax = plt.subplots(figsize=(10, fig_h))
    y = np.arange(len(labels))
    ax.barh(y, means, xerr=stds, capsize=3, color="steelblue", alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("BPM abs err vs HKH (breaths/min)")
    ax.set_title(f"HKH live breathing — method leaderboard ({dataset_name})")
    fig.tight_layout()
    path = FIGURES_DIR / f"ble_hkh_multi_algorithm_{dataset_name}.png"
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

    multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=filter_params,
        cache_dir=CACHE_DIR,
        verbose=True,
    )

    print(f"\n=== Multi-algorithm vs HKH GT ({SCENARIO_ID}) ===")
    bench = run_hkh_multi_algorithm_benchmark(
        multichannel_by_var,
        "main",
        hkh_bp,
        hkh_t,
        cs_t,
        config=chfusion_config,
        metric_params=metric_params,
        verbose=True,
    )

    report_json = REPORTS_DIR / f"ble_hkh_multi_algorithm_{SCENARIO_ID}.json"
    with report_json.open("w", encoding="utf-8") as handle:
        json.dump(
            {"scenario_id": SCENARIO_ID, "preprocess_meta": preprocess_meta, **bench},
            handle,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )

    fig_path = plot_leaderboard(bench, SCENARIO_ID)

    print("\n=== Top 10 (BPM abs err, lower is better) ===")
    print(f"{'Rank':<5} {'Method':<40} {'BPM err (mean±std)':>18} {'RMSE':>12}")
    print("-" * 80)
    for row in bench["leaderboard"][:10]:
        rmse = ""
        if row.get("rmse_mean") is not None:
            rmse = f"{row['rmse_mean']:.3f}±{row.get('rmse_std', 0):.3f}"
        print(
            f"{row['rank']:<5} {row['label']:<40} "
            f"{row['bpm_mean_abs_err']:.2f}±{row['bpm_std_abs_err']:.2f} BPM".rjust(18)
            + f"  {rmse:>12}"
        )

    print(f"\nSaved JSON: {report_json}")
    print(f"Saved figure: {fig_path}")
