"""B1 series (BPM-only) vs HKH GT on 12 live breathing scenarios.

Run:
    python notebooks/scripts/chFusion_ble_hkh_b1_validation.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.ble_hkh_validation import (
    compute_hkh_gt_per_window,
    extract_bpm_per_window,
    load_hkh_gt_signals,
    summarize_bpm_vs_hkh,
)
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import ChFusionConfig, Plan2Config, load_multichannel_for_scenario
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams, FilterParams
from ble_analysis.systematic_fusion import estimate_systematic_fusion_segment
from ble_analysis.voting_fusion import VotingConfig

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

# B1 系列：谱域 BPM-only（无融合波形）
B1_METHODS = [
    ("B1 Vote→Equal modal", "b1_vote_modal_equal", "vote", "equal"),
    ("B1 Uniform Remote", "b1_uniform_remote", None, None),
    ("B3 Vote→Top2 modal", "b3_vote_modal_top2", "vote", "top2"),
]

REF_KEYS = {
    "b2_d_two_level": "B2-D Two-level Hilbert-MRC",
    "z1_no_vmd": "Zhuo Z1-no-VMD",
    "fan_eta_linear": "Fan η-linear",
}


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def run_b1_for_scenario(
    scenario_id: str,
    filter_params: FilterParams,
    metric_params: BreathMetricParams,
    chfusion_config: ChFusionConfig,
    plan2_config: Plan2Config,
) -> dict:
    scenario = load_scenario(scenario_id, project_root=project_root)
    processed_dir = (project_root / Path(scenario.data_file)).parent
    hkh_bp, hkh_t, cs_t, preprocess_meta = load_hkh_gt_signals(processed_dir)
    fs_hkh = preprocess_meta.get("sampling_rate_hz", {}).get("hkh_used")

    multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=filter_params,
        cache_dir=CACHE_DIR,
        verbose=False,
    )

    bpm_hkh, _, _fs_ble, _fs_hkh = compute_hkh_gt_per_window(
        hkh_bp,
        hkh_t,
        cs_t,
        multichannel_by_var,
        "main",
        config=chfusion_config,
        metric_params=metric_params,
        fs_hkh_override=fs_hkh,
    )

    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")
    results: Dict[str, dict] = {}

    for label, key, ch_strat, mod_strat in B1_METHODS:
        if key == "b1_uniform_remote":
            remote_mc = { "main": multichannel_by_var["remote_amplitudes"]["main"] }
            from ble_analysis.chfusion import estimate_segment_bpm_methods

            seg_remote = estimate_segment_bpm_methods(
                remote_mc,
                variable="remote_amplitudes",
                config=chfusion_config,
                metric_params=metric_params,
                methods=("uniform",),
                single_channel_metric=plan2_config.channel_metric,
                verbose=False,
            )
            row = seg_remote.get("main")
            bpm_est = extract_bpm_per_window(row, "fft_uniform_fusion")
        else:
            row = estimate_systematic_fusion_segment(
                multichannel_by_var,
                "main",
                channel_strategy=ch_strat,
                modal_strategy=mod_strat,
                config=chfusion_config,
                metric_params=metric_params,
                vcfg=vcfg,
                verbose=False,
            )
            bpm_est = extract_bpm_per_window(row, key)

        if bpm_est is None or len(bpm_est) != len(bpm_hkh):
            continue
        summary = summarize_bpm_vs_hkh(bpm_est, bpm_hkh)
        results[key] = {"label": label, "method_key": key, "summary": summary}

    # 参照：已有 paper baselines 结果
    ref_path = REPORTS_DIR / f"ble_hkh_paper_baselines_{scenario_id}.json"
    refs = {}
    if ref_path.is_file():
        ref_doc = json.loads(ref_path.read_text(encoding="utf-8"))
        for rk, rlabel in REF_KEYS.items():
            hit = next((r for r in ref_doc["leaderboard_bpm"] if r["method_key"] == rk), None)
            if hit:
                refs[rk] = {
                    "label": rlabel,
                    "bpm_mean_abs_err": hit["bpm_mean_abs_err"],
                    "bpm_std_abs_err": hit["bpm_std_abs_err"],
                    "rmse_mean": hit.get("rmse_mean"),
                }

    return {
        "scenario_id": scenario_id,
        "b1_methods": results,
        "references": refs,
    }


def aggregate_leaderboard(per_scenario: List[dict]) -> List[dict]:
    acc: Dict[str, List[float]] = defaultdict(list)
    labels: Dict[str, str] = {}
    for sc in per_scenario:
        for key, entry in sc["b1_methods"].items():
            acc[key].append(entry["summary"]["bpm_mean_abs_err"])
            labels[key] = entry["label"]
        for rk, ref in sc.get("references", {}).items():
            acc[rk].append(ref["bpm_mean_abs_err"])
            labels[rk] = ref["label"]
    rows = []
    for key, vals in acc.items():
        rows.append(
            {
                "method_key": key,
                "label": labels[key],
                "bpm_mean_abs_err": float(np.mean(vals)),
                "bpm_std_across_scenarios": float(np.std(vals, ddof=0)),
                "n_scenarios": len(vals),
            }
        )
    rows.sort(key=lambda r: r["bpm_mean_abs_err"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def plot_leaderboard(rows: List[dict]) -> Path:
    labels = [r["label"] for r in rows][::-1]
    means = [r["bpm_mean_abs_err"] for r in rows][::-1]
    stds = [r["bpm_std_across_scenarios"] for r in rows][::-1]
    colors = ["olive" if "B1" in lb or "B3 Vote" in lb else "gray" for lb in labels]

    fig, ax = plt.subplots(figsize=(10, max(5, 0.4 * len(labels))))
    y = np.arange(len(labels))
    ax.barh(y, means, xerr=stds, capsize=3, color=colors, alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Mean BPM abs err across 12 scenarios (breaths/min)")
    ax.set_title("HKH multi-subject — B1 series vs B2-D / Z1 / Fan (BPM only)")
    fig.tight_layout()
    path = FIGURES_DIR / "ble_hkh_b1_validation_leaderboard_12scenarios.png"
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
    plan2_config = Plan2Config(channel_metric="energy_ratio")

    per_scenario: List[dict] = []
    for sid in SCENARIO_IDS:
        print(f"\n=== {sid} ===")
        result = run_b1_for_scenario(
            sid, filter_params, metric_params, chfusion_config, plan2_config
        )
        per_scenario.append(result)
        for key, entry in result["b1_methods"].items():
            s = entry["summary"]
            print(f"  {entry['label']:<28} {s['bpm_mean_abs_err']:.2f}±{s['bpm_std_abs_err']:.2f} BPM")
        for rk, ref in result.get("references", {}).items():
            print(f"  {ref['label']:<28} {ref['bpm_mean_abs_err']:.2f}±{ref['bpm_std_abs_err']:.2f} BPM (ref)")

    leaderboard = aggregate_leaderboard(per_scenario)
    summary = {
        "n_scenarios": len(SCENARIO_IDS),
        "scenario_ids": SCENARIO_IDS,
        "b1_methods_tested": [m[1] for m in B1_METHODS],
        "leaderboard_bpm": leaderboard,
        "per_scenario": [
            {
                "scenario_id": sc["scenario_id"],
                "b1": {
                    k: v["summary"] for k, v in sc["b1_methods"].items()
                },
                "references": sc.get("references", {}),
            }
            for sc in per_scenario
        ],
    }

    out_json = REPORTS_DIR / "ble_hkh_b1_validation_summary.json"
    with out_json.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=_json_default)

    fig_path = plot_leaderboard(leaderboard)

    print(f"\n{'=' * 70}")
    print("=== Cross-scenario BPM leaderboard (B1 + refs) ===")
    for row in leaderboard:
        print(
            f"{row['rank']:>2}. {row['label']:<32} "
            f"{row['bpm_mean_abs_err']:.2f}±{row['bpm_std_across_scenarios']:.2f} BPM"
        )
    print(f"\nSaved: {out_json}")
    print(f"Saved: {fig_path}")
