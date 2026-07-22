"""Paper baseline waveform methods vs HKH GT on live breathing data (multi-subject).

Compares Fan 2024, Yu 2021 WiFi-Sleep, Zhuo 2023 (+ B2 refs) with BPM
error and waveform RMSE across 12 BLE+HKH scenarios.

Run:
    python notebooks/scripts/chFusion_ble_hkh_paper_baselines.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

ROOM_LABELS = {
    "room_A": "Living room (sitting)",
    "room_B": "Bedroom (flat)",
    "room_C": "Bedroom (side)",
}

POSTURE_GROUPS = {
    "Living room": ["room_A"],
    "Bedroom": ["room_B", "room_C"],
}


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _save_figure(fig: plt.Figure, stem_or_filename: str) -> Path:
    """Save PNG (preview) and PDF (paper-ready). Accepts stem or ``*.png`` name."""
    stem = Path(stem_or_filename).stem
    png_path = FIGURES_DIR / f"{stem}.png"
    pdf_path = FIGURES_DIR / f"{stem}.pdf"
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    return png_path


def _parse_scenario_id(scenario_id: str) -> Tuple[str, str]:
    m = re.match(r"(room_[A-C])-(sbj_[A-D])-", scenario_id)
    if not m:
        return "unknown", "unknown"
    return m.group(1), m.group(2)


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
    path = _save_figure(fig, f"ble_hkh_paper_baselines_{dataset_name}")
    plt.close(fig)
    return path


def run_single_scenario(
    scenario_id: str,
    filter_params: FilterParams,
    metric_params: BreathMetricParams,
    chfusion_config: ChFusionConfig,
    *,
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

    if verbose:
        print(f"\n=== Paper baselines vs HKH GT ({scenario_id}) ===")
    bench = run_hkh_paper_baselines_benchmark(
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

    report_json = REPORTS_DIR / f"ble_hkh_paper_baselines_{scenario_id}.json"
    slim = {
        "scenario_id": scenario_id,
        "room": _parse_scenario_id(scenario_id)[0],
        "subject": _parse_scenario_id(scenario_id)[1],
        "preprocess_meta": preprocess_meta,
        "segment": bench["segment"],
        "leaderboard_bpm": bench["leaderboard_bpm"],
        "leaderboard_rmse": bench["leaderboard_rmse"],
    }
    with report_json.open("w", encoding="utf-8") as handle:
        json.dump(slim, handle, ensure_ascii=False, indent=2, default=_json_default)

    fig_path = plot_paper_leaderboard(bench, scenario_id)
    if verbose:
        print(f"Saved JSON: {report_json}")
        print(f"Saved figure: {fig_path}")
    return slim


def aggregate_method_stats(per_scenario: List[dict]) -> List[dict]:
    """Mean BPM/RMSE across scenarios per method key."""
    bpm_acc: Dict[str, List[float]] = defaultdict(list)
    bpm_std_acc: Dict[str, List[float]] = defaultdict(list)
    rmse_acc: Dict[str, List[float]] = defaultdict(list)
    meta: Dict[str, dict] = {}

    for sc in per_scenario:
        for row in sc["leaderboard_bpm"]:
            key = row["method_key"]
            bpm_acc[key].append(row["bpm_mean_abs_err"])
            bpm_std_acc[key].append(row["bpm_std_abs_err"])
            meta[key] = row
        for row in sc["leaderboard_rmse"]:
            key = row["method_key"]
            rmse_acc[key].append(row["rmse_mean"])

    rows = []
    for key, bpm_vals in bpm_acc.items():
        m = meta[key]
        rows.append(
            {
                "method_key": key,
                "label": m["label"],
                "paper": m["paper"],
                "n_scenarios": len(bpm_vals),
                "bpm_mean_abs_err": float(np.mean(bpm_vals)),
                "bpm_std_across_scenarios": float(np.std(bpm_vals, ddof=0)),
                "bpm_mean_of_window_std": float(np.mean(bpm_std_acc[key])),
                "rmse_mean": float(np.mean(rmse_acc.get(key, [np.nan]))),
            }
        )
    rows.sort(key=lambda r: r["bpm_mean_abs_err"])
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    return rows


def aggregate_by_group(
    per_scenario: List[dict],
    group_key_fn,
) -> Dict[str, List[dict]]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for sc in per_scenario:
        groups[group_key_fn(sc)].append(sc)
    return {k: aggregate_method_stats(v) for k, v in sorted(groups.items())}


def plot_cross_scenario_leaderboard(
    agg_rows: List[dict],
    title: str,
    filename: str,
) -> Path:
    labels = [r["label"] for r in agg_rows][::-1]
    means = [r["bpm_mean_abs_err"] for r in agg_rows][::-1]
    stds = [r["bpm_std_across_scenarios"] for r in agg_rows][::-1]
    colors = [PAPER_COLORS.get(r["paper"], "gray") for r in agg_rows][::-1]

    fig_h = max(6, 0.38 * len(labels))
    fig, ax = plt.subplots(figsize=(10, fig_h))
    y = np.arange(len(labels))
    ax.barh(y, means, xerr=stds, capsize=3, color=colors, alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Mean BPM abs err across scenarios (breaths/min)")
    ax.set_title(title)
    fig.tight_layout()
    path = _save_figure(fig, filename)
    plt.close(fig)
    return path


def plot_group_comparison(
    group_stats: Dict[str, List[dict]],
    title: str,
    filename: str,
    top_n: int = 5,
) -> Path:
    """Grouped bar chart for top-N methods across groups."""
    pooled: Dict[str, List[float]] = defaultdict(list)
    labels_map: Dict[str, str] = {}
    for _g, rows in group_stats.items():
        for r in rows:
            pooled[r["method_key"]].append(r["bpm_mean_abs_err"])
            labels_map[r["method_key"]] = r["label"]
    top_keys = sorted(pooled.keys(), key=lambda k: np.mean(pooled[k]))[:top_n]
    groups = list(group_stats.keys())

    x = np.arange(len(top_keys))
    width = 0.8 / max(len(groups), 1)
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, gname in enumerate(groups):
        vals = []
        row_map = {r["method_key"]: r["bpm_mean_abs_err"] for r in group_stats[gname]}
        for k in top_keys:
            vals.append(row_map.get(k, np.nan))
        offset = (i - (len(groups) - 1) / 2) * width
        ax.bar(x + offset, vals, width, label=gname, alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels([labels_map[k] for k in top_keys], rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Mean BPM abs err (breaths/min)")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    path = _save_figure(fig, filename)
    plt.close(fig)
    return path


def build_posture_group_stats(per_scenario: List[dict]) -> Dict[str, List[dict]]:
    posture_scenarios: Dict[str, List[dict]] = defaultdict(list)
    for sc in per_scenario:
        room = sc["room"]
        for posture, room_keys in POSTURE_GROUPS.items():
            if room in room_keys:
                posture_scenarios[posture].append(sc)
                break
    return {k: aggregate_method_stats(v) for k, v in posture_scenarios.items()}


if __name__ == "__main__":
    filter_params = FilterParams()
    metric_params = BreathMetricParams()
    chfusion_config = ChFusionConfig(
        breath_freq_low=metric_params.breath_freq_low,
        breath_freq_high=metric_params.breath_freq_high,
        window_length_sec=metric_params.window_length_sec,
        step_length_sec=metric_params.step_length_sec,
    )

    per_scenario_results: List[dict] = []
    for sid in SCENARIO_IDS:
        print(f"\n{'#' * 70}")
        print(f"# Scenario: {sid}")
        print(f"{'#' * 70}")
        result = run_single_scenario(
            sid,
            filter_params,
            metric_params,
            chfusion_config,
            verbose=True,
        )
        per_scenario_results.append(result)

    overall = aggregate_method_stats(per_scenario_results)
    by_room = aggregate_by_group(per_scenario_results, lambda sc: sc["room"])
    by_subject = aggregate_by_group(per_scenario_results, lambda sc: sc["subject"])
    by_posture = build_posture_group_stats(per_scenario_results)

    summary = {
        "n_scenarios": len(SCENARIO_IDS),
        "scenario_ids": SCENARIO_IDS,
        "overall_leaderboard": overall,
        "by_room": by_room,
        "by_subject": by_subject,
        "by_posture": by_posture,
    }
    summary_path = REPORTS_DIR / "ble_hkh_paper_baselines_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=_json_default)

    fig_all = plot_cross_scenario_leaderboard(
        overall,
        f"HKH multi-subject — paper baselines BPM error (N={len(SCENARIO_IDS)} scenarios)",
        "ble_hkh_paper_baselines_leaderboard_all.png",
    )
    room_labels = {k: ROOM_LABELS.get(k, k) for k in by_room}
    by_room_labeled = {room_labels.get(k, k): v for k, v in by_room.items()}
    fig_room = plot_group_comparison(
        by_room_labeled,
        "BPM error by room (top 5 methods)",
        "ble_hkh_paper_baselines_by_room.png",
    )
    by_subject_labeled = {k.replace("sbj_", "Subject "): v for k, v in by_subject.items()}
    fig_subj = plot_group_comparison(
        by_subject_labeled,
        "BPM error by subject (top 5 methods)",
        "ble_hkh_paper_baselines_by_subject.png",
    )
    fig_posture = plot_group_comparison(
        by_posture,
        "Living room (sitting) vs Bedroom (lying) — top 5 methods",
        "ble_hkh_paper_baselines_bedroom_vs_living.png",
    )

    print(f"\n{'=' * 70}")
    print("=== Cross-scenario BPM leaderboard (mean across 12 scenarios) ===")
    print(f"{'Rank':<5} {'Paper':<10} {'Method':<42} {'BPM err':>12} {'RMSE':>10}")
    print("-" * 85)
    for row in overall:
        print(
            f"{row['rank']:<5} {row['paper']:<10} {row['label']:<42} "
            f"{row['bpm_mean_abs_err']:.2f}±{row['bpm_std_across_scenarios']:.2f} BPM"
            f"  {row['rmse_mean']:.3f}"
        )

    print(f"\nSaved summary: {summary_path}")
    print(f"Saved figures: {fig_all.name}, {fig_room.name}, {fig_subj.name}, {fig_posture.name}")
