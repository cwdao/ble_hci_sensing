"""B2 vs HKH ground-truth validation on live breathing data.

Run:
    python notebooks/scripts/chFusion_ble_hkh_b2_validation.py
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
    raise FileNotFoundError("Project root not found (missing src/ directory)")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.ble_hkh_validation import load_hkh_gt_signals, validate_b2_against_hkh
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import ChFusionConfig, load_multichannel_for_scenario
from ble_analysis.coherent_mrc import B2_ALL_SPECS
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
B2_METHODS = [
    "b2_d_two_level",
    "b2_b_hilbert",
    "b2_a0_pca_sign",
    "b2_a1_corr_sign",
]


def _method_label(key: str) -> str:
    for label, k, _c in B2_ALL_SPECS:
        if k == key:
            return label
    return key


def plot_validation_results(results: dict, dataset_name: str) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))

    methods = list(results["methods"].keys())
    bpm_means = [results["methods"][m]["summary"]["bpm_mean_abs_err"] for m in methods]
    bpm_stds = [results["methods"][m]["summary"]["bpm_std_abs_err"] for m in methods]
    rmse_means = [results["methods"][m]["summary"]["rmse_mean"] for m in methods]
    rmse_stds = [results["methods"][m]["summary"]["rmse_std"] for m in methods]
    labels = [_method_label(m) for m in methods]

    x = np.arange(len(methods))
    axes[0].bar(x, bpm_means, yerr=bpm_stds, capsize=4, color="steelblue", alpha=0.85)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=20, ha="right")
    axes[0].set_ylabel("BPM abs err vs HKH (breaths/min)")
    axes[0].set_title(f"B2 vs HKH GT — {dataset_name}")

    axes[1].bar(x, rmse_means, yerr=rmse_stds, capsize=4, color="crimson", alpha=0.85)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=20, ha="right")
    axes[1].set_ylabel("Window RMSE (z-scored)")

    fig.tight_layout()
    fig_path = FIGURES_DIR / f"ble_hkh_b2_validation_{dataset_name}.png"
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig_path


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

    method_results = {}
    for method_key in B2_METHODS:
        print(f"\n--- {_method_label(method_key)} ---")
        row = validate_b2_against_hkh(
            multichannel_by_var,
            "main",
            hkh_bp,
            hkh_t,
            cs_t,
            method_key=method_key,
            config=chfusion_config,
            metric_params=metric_params,
            verbose=True,
        )
        if row is not None:
            method_results[method_key] = row

    payload = {
        "scenario_id": SCENARIO_ID,
        "preprocess_meta": preprocess_meta,
        "methods": method_results,
    }

    report_json = REPORTS_DIR / f"ble_hkh_b2_validation_{SCENARIO_ID}.json"
    with report_json.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)

    report_npy = REPORTS_DIR / f"ble_hkh_b2_validation_{SCENARIO_ID}.npy"
    np.save(report_npy, payload, allow_pickle=True)

    fig_path = plot_validation_results(payload, SCENARIO_ID)

    print("\n=== BPM error summary (absolute, breaths/min) ===")
    print(f"{'Method':<42} {'BPM err (mean±std)':>20} {'RMSE (mean±std)':>18}")
    print("-" * 82)
    for method_key in B2_METHODS:
        if method_key not in method_results:
            continue
        s = method_results[method_key]["summary"]
        label = _method_label(method_key)
        print(
            f"{label:<42} "
            f"{s['bpm_mean_abs_err']:.2f}±{s['bpm_std_abs_err']:.2f} BPM".rjust(20)
            + f"  {s['rmse_mean']:.3f}±{s['rmse_std']:.3f}".rjust(18)
        )

    print(f"\nSaved JSON: {report_json}")
    print(f"Saved NPY:  {report_npy}")
    print(f"Saved figure: {fig_path}")
