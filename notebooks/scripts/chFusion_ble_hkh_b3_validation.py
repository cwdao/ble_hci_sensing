"""B3 unified pipeline validation vs HKH GT across 12 live-breathing scenarios.

Run (default — B3 Simplified + baselines):
    python notebooks/scripts/chFusion_ble_hkh_b3_validation.py

Full ablation (legacy A1–A5 variants):
    python notebooks/scripts/chFusion_ble_hkh_b3_validation.py --mode full
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found (missing src/ directory)")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.b3_pipeline import (
    B3_VARIANT_SPECS,
    EXTERNAL_BASELINE_SPECS,
    compute_b3_cross_domain_summary,
    validate_b1_vote_equal_against_hkh,
    validate_b3_variant_against_hkh,
)
from ble_analysis.ble_hkh_paper_validation import validate_paper_method_against_hkh
from ble_analysis.ble_hkh_validation import load_hkh_gt_signals
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import ChFusionConfig, load_multichannel_for_scenario
from ble_analysis.pca_svd import PcaSvdConfig
from ble_analysis.pca_vmd import VmdParams
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams

_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]
CACHE_DIR = str(project_root / "outputs" / "cache")

SCENARIO_IDS = [
    "room_A-sbj_A-07101613",
    "room_A-sbj_B-07111610",
    "room_A-sbj_C-07111623",
    "room_A-sbj_D-07111635",
    "room_B-sbj_A-07111726",
    "room_B-sbj_B-07111820",
    "room_B-sbj_C-07111843",
    "room_B-sbj_D-07111653",
    "room_C-sbj_A-07111734",
    "room_C-sbj_B-07111835",
    "room_C-sbj_C-07111850",
    "room_C-sbj_D-07111659",
]

OUTLIER_SCENARIOS = [
    "room_A-sbj_D-07111635",
    "room_B-sbj_C-07111843",
    "room_C-sbj_A-07111734",
]

OUTLIER_COMPARE_KEYS = [
    "b3_b1_equal",
    "a1_single_best_eta",
    "b2_d_two_level",
]


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _parse_scenario_id(scenario_id: str) -> Tuple[str, str]:
    m = re.match(r"(room_[A-C])-(sbj_[A-D])-", scenario_id)
    if not m:
        return "unknown", "unknown"
    return m.group(1), m.group(2)


def _method_summary_row(row: dict) -> dict:
    s = row.get("summary", {})
    return {
        "label": row.get("label", row.get("method", "")),
        "method_key": row.get("method", ""),
        "bpm_mean_abs_err": s.get("bpm_mean_abs_err"),
        "bpm_std_abs_err": s.get("bpm_std_abs_err"),
        "rmse_mean": s.get("rmse_mean"),
        "rmse_std": s.get("rmse_std"),
        "has_waveform": row.get("has_waveform", True),
    }


def run_single_scenario(
    scenario_id: str,
    filter_params: FilterParams,
    metric_params: BreathMetricParams,
    chfusion_config: ChFusionConfig,
    *,
    mode: str = "simplified",
    verbose: bool = True,
) -> dict:
    scenario = load_scenario(scenario_id, project_root=project_root)
    if verbose:
        print_scenario_summary(scenario)

    processed_dir = (project_root / Path(scenario.data_file)).parent
    hkh_bp, hkh_t, cs_t, preprocess_meta = load_hkh_gt_signals(processed_dir)
    fs_hkh = preprocess_meta.get("sampling_rate_hz", {}).get("hkh_used")

    multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=filter_params,
        cache_dir=CACHE_DIR,
        verbose=verbose,
    )

    pca_cfg = PcaSvdConfig(signal_key="bandpass_filtered")
    vmd_params = VmdParams(K=3, alpha=3000.0)

    methods: Dict[str, dict] = {}

    if mode == "full":
        if verbose:
            print("\n--- B3 variants ---")
        for label, variant_key, _cfg in B3_VARIANT_SPECS:
            row = validate_b3_variant_against_hkh(
                multichannel_by_var,
                "main",
                hkh_bp,
                hkh_t,
                cs_t,
                variant_key=variant_key,
                config=chfusion_config,
                metric_params=metric_params,
                fs_hkh_override=fs_hkh,
                verbose=verbose,
            )
            if row is not None:
                methods[variant_key] = row
    else:
        if verbose:
            print("\n--- B3 Simplified ---")
        row = validate_b3_variant_against_hkh(
            multichannel_by_var,
            "main",
            hkh_bp,
            hkh_t,
            cs_t,
            variant_key="b3_b1_equal",
            config=chfusion_config,
            metric_params=metric_params,
            fs_hkh_override=fs_hkh,
            verbose=verbose,
        )
        if row is not None:
            methods["b3_b1_equal"] = row

    if verbose:
        print("\n--- External baselines ---")
    b1_row = validate_b1_vote_equal_against_hkh(
        multichannel_by_var,
        "main",
        hkh_bp,
        hkh_t,
        cs_t,
        config=chfusion_config,
        metric_params=metric_params,
        fs_hkh_override=fs_hkh,
        verbose=verbose,
    )
    if b1_row is not None:
        methods["b1_vote_modal_equal"] = b1_row

    for _label, baseline_key in EXTERNAL_BASELINE_SPECS:
        if baseline_key == "b1_vote_modal_equal":
            continue
        if mode == "simplified" and baseline_key not in {"b2_d_two_level"}:
            continue
        row = validate_paper_method_against_hkh(
            multichannel_by_var,
            "main",
            hkh_bp,
            hkh_t,
            cs_t,
            method_key=baseline_key,
            config=chfusion_config,
            metric_params=metric_params,
            pca_cfg=pca_cfg,
            vmd_params=vmd_params,
            fs_hkh_override=fs_hkh,
            verbose=verbose,
        )
        if row is not None:
            methods[baseline_key] = row

    room, subject = _parse_scenario_id(scenario_id)
    payload = {
        "scenario_id": scenario_id,
        "room": room,
        "subject": subject,
        "preprocess_meta": preprocess_meta,
        "methods": {k: _method_summary_row(v) | {"raw": v} for k, v in methods.items()},
    }

    out_path = REPORTS_DIR / f"ble_hkh_b3_validation_{scenario_id}.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)

    if verbose:
        print(f"\nSaved: {out_path}")

    return {
        "scenario_id": scenario_id,
        "room": room,
        "subject": subject,
        "methods": methods,
        "bpm_series": {
            k: {
                "bpm_est": v["bpm_est"],
                "bpm_hkh_gt": v["bpm_hkh_gt"],
                "label": v.get("label", k),
            }
            for k, v in methods.items()
        },
    }


def plot_ablation_leaderboard(summary: dict) -> Path:
    rows = summary["leaderboard"]
    labels = [r["label"] for r in rows][::-1]
    bpm_m = [r["bpm_mean_abs_err"] for r in rows][::-1]
    bpm_s = [r["bpm_std_abs_err"] for r in rows][::-1]
    rmse_m = [r.get("rmse_mean", float("nan")) for r in rows][::-1]
    has_wf = [np.isfinite(r.get("rmse_mean", float("nan"))) for r in rows][::-1]

    fig_h = max(6.0, 0.42 * len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(14, fig_h))
    y = np.arange(len(labels))

    axes[0].barh(y, bpm_m, xerr=bpm_s, capsize=3, color="steelblue", alpha=0.88)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels, fontsize=8)
    axes[0].set_xlabel("BPM abs err vs HKH (12-scenario mean ± scenario std)")
    axes[0].set_title("B3 ablation + baselines — BPM")

    colors = ["crimson" if hw else "lightgray" for hw in has_wf]
    rmse_plot = [v if np.isfinite(v) else 0.0 for v in rmse_m]
    axes[1].barh(y, rmse_plot, color=colors, alpha=0.88)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(labels, fontsize=8)
    axes[1].set_xlabel("RMSE mean (waveform variants only)")
    axes[1].set_title("Waveform RMSE")

    fig.suptitle("B3 unified pipeline — 12 HKH scenarios", y=1.01)
    fig.tight_layout()
    path = FIGURES_DIR / "ble_hkh_b3_ablation_leaderboard.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_bpm_vs_rmse(summary: dict) -> Path:
    fig, ax = plt.subplots(figsize=(8, 6))
    for key, row in summary["methods"].items():
        bpm = row.get("bpm_mean_abs_err", float("nan"))
        rmse = row.get("rmse_mean", float("nan"))
        if not np.isfinite(bpm):
            continue
        if np.isfinite(rmse):
            ax.scatter(bpm, rmse, s=60, alpha=0.85)
            ax.annotate(row["label"], (bpm, rmse), fontsize=7, xytext=(4, 4), textcoords="offset points")
        else:
            ax.scatter(bpm, 0.0, s=40, marker="x", color="gray", alpha=0.6)
            ax.annotate(row["label"] + " (no wf)", (bpm, 0.0), fontsize=6, xytext=(4, 2), textcoords="offset points")

    ax.set_xlabel("BPM abs err (12-scenario mean)")
    ax.set_ylabel("RMSE mean (waveform methods)")
    ax.set_title("BPM error vs waveform RMSE")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = FIGURES_DIR / "ble_hkh_b3_bpm_vs_rmse.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_outlier_timeseries(all_results: Dict[str, dict]) -> Path:
    compare_keys = OUTLIER_COMPARE_KEYS
    labels = {
        "b3_b1_equal": "B3 Simplified BPM",
        "a1_single_best_eta": "A1 best-η",
        "b2_d_two_level": "B2-D",
    }
    colors = {
        "b3_b1_equal": "crimson",
        "a1_single_best_eta": "steelblue",
        "b2_d_two_level": "seagreen",
    }

    fig, axes = plt.subplots(len(OUTLIER_SCENARIOS), 1, figsize=(12, 3.2 * len(OUTLIER_SCENARIOS)), sharex=False)
    if len(OUTLIER_SCENARIOS) == 1:
        axes = [axes]

    for ax, sid in zip(axes, OUTLIER_SCENARIOS):
        payload = all_results.get(sid)
        if payload is None:
            continue
        methods = payload.get("methods", {})
        gt = None
        for key in compare_keys:
            row = methods.get(key)
            if row is None:
                continue
            if gt is None:
                gt = row["bpm_hkh_gt"]
                t = np.arange(len(gt))
                ax.plot(t, gt, "k--", linewidth=1.2, label="HKH GT", alpha=0.8)
            ax.plot(t, row["bpm_est"], color=colors.get(key, "gray"), linewidth=1.0, label=labels.get(key, key))
        ax.set_title(sid)
        ax.set_ylabel("BPM")
        ax.legend(fontsize=7, loc="upper right")
        ax.grid(True, alpha=0.25)

    axes[-1].set_xlabel("Window index")
    fig.suptitle("Outlier scenarios — BPM time series", y=1.01)
    fig.tight_layout()
    path = FIGURES_DIR / "ble_hkh_b3_outlier_timeseries.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate B3 pipeline on HKH 12 scenarios")
    parser.add_argument(
        "--mode",
        choices=("simplified", "full"),
        default="simplified",
        help="simplified: B3 Simplified + B1/B2-D baselines; full: legacy ablation A1-A5",
    )
    args = parser.parse_args()

    filter_params = FilterParams()
    metric_params = BreathMetricParams()
    chfusion_config = ChFusionConfig(
        breath_freq_low=metric_params.breath_freq_low,
        breath_freq_high=metric_params.breath_freq_high,
        window_length_sec=metric_params.window_length_sec,
        step_length_sec=metric_params.step_length_sec,
    )

    all_results: Dict[str, dict] = {}
    for scenario_id in SCENARIO_IDS:
        print(f"\n{'=' * 72}\nScenario: {scenario_id}\n{'=' * 72}")
        all_results[scenario_id] = run_single_scenario(
            scenario_id,
            filter_params,
            metric_params,
            chfusion_config,
            mode=args.mode,
            verbose=True,
        )

    cross_input = {
        sid: {"methods": payload["methods"]}
        for sid, payload in all_results.items()
    }
    summary = compute_b3_cross_domain_summary(cross_input)

    if args.mode == "full":
        summary_path = REPORTS_DIR / "ble_hkh_b3_validation_summary.json"
    else:
        summary_path = REPORTS_DIR / "ble_hkh_b3_simplified_validation_summary.json"

    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=_json_default)

    fig_leader = plot_ablation_leaderboard(summary)
    fig_scatter = plot_bpm_vs_rmse(summary)
    if args.mode == "full":
        fig_outlier = plot_outlier_timeseries(all_results)
    else:
        fig_outlier = None

    print("\n=== Cross-domain leaderboard (BPM mean abs err) ===")
    print(f"{'Rank':<5} {'Method':<40} {'BPM mean±std':>16} {'RMSE mean':>12}")
    print("-" * 78)
    for i, row in enumerate(summary["leaderboard"], start=1):
        rmse_txt = f"{row['rmse_mean']:.3f}" if np.isfinite(row.get("rmse_mean", float("nan"))) else "N/A"
        print(
            f"{i:<5} {row['label']:<40} "
            f"{row['bpm_mean_abs_err']:.3f}±{row['bpm_std_abs_err']:.3f} "
            f"{rmse_txt:>12}"
        )

    print(f"\nSaved summary: {summary_path}")
    print(f"Saved figure: {fig_leader}")
    print(f"Saved figure: {fig_scatter}")
    if fig_outlier is not None:
        print(f"Saved figure: {fig_outlier}")

    if args.mode == "simplified":
        b3 = summary["methods"].get("b3_b1_equal", {})
        b1 = summary["methods"].get("b1_vote_modal_equal", {})
        b2 = summary["methods"].get("b2_d_two_level", {})
        print("\n=== B3 Simplified vs baselines ===")
        if b3:
            print(
                f"B3 Simplified: BPM {b3['bpm_mean_abs_err']:.3f}±{b3['bpm_std_abs_err']:.3f} "
                f"RMSE {b3.get('rmse_mean', float('nan')):.3f}"
            )
        if b1:
            print(
                f"B1 Vote→Equal: BPM {b1['bpm_mean_abs_err']:.3f}±{b1['bpm_std_abs_err']:.3f}"
            )
        if b3 and b1:
            print(f"BPM delta (B3 - B1): {b3['bpm_mean_abs_err'] - b1['bpm_mean_abs_err']:+.6f}")
        if b2:
            print(f"B2-D RMSE: {b2.get('rmse_mean', float('nan')):.3f}")
