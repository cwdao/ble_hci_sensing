"""B1+B2 window-level hybrid gating validation across 12 HKH scenarios.

Run:
    python notebooks/scripts/chFusion_b1_b2_hybrid_gating.py
"""

from __future__ import annotations

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

from ble_analysis.b3_pipeline import validate_b3_variant_against_hkh
from ble_analysis.ble_hkh_validation import load_hkh_gt_signals
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import ChFusionConfig, load_multichannel_for_scenario
from ble_analysis.hybrid_gating import (
    DEFAULT_THRESHOLDS,
    apply_hybrid_gating,
    diagnose_consensus_windows,
    diagnose_trigger_rate_by_group,
    evaluate_hybrid_gating_scan,
)
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
    "room_C-sbj_A-07111734",
]

THRESHOLDS = list(DEFAULT_THRESHOLDS)


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.bool_):
        return bool(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _parse_scenario_id(scenario_id: str) -> Tuple[str, str]:
    m = re.match(r"(room_[A-C])-(sbj_[A-D])-", scenario_id)
    if not m:
        return "unknown", "unknown"
    return m.group(1), m.group(2)


def _serialize_scan_results(scan: dict) -> dict:
    out: Dict[str, dict] = {}
    for key, row in scan.items():
        out[key] = {
            "method_key": row["method_key"],
            "label": row["label"],
            "strategy": row.get("strategy"),
            "threshold": row.get("threshold"),
            "summary": {
                k: v
                for k, v in row["summary"].items()
                if k not in ("bpm_abs_err", "bpm_rel_err_pct")
            },
            "trigger_rate": row.get("trigger_rate"),
        }
    return out


def run_single_scenario(
    scenario_id: str,
    filter_params: FilterParams,
    metric_params: BreathMetricParams,
    chfusion_config: ChFusionConfig,
    *,
    verbose: bool = True,
) -> dict:
    """Run B3 b1_equal variant and apply hybrid gating post-hoc."""
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

    b3_row = validate_b3_variant_against_hkh(
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
    if b3_row is None:
        raise RuntimeError(f"B3 validation failed for {scenario_id}")

    bpm_b1 = np.asarray(b3_row["bpm_vote"], dtype=float)
    bpm_b2 = np.asarray(b3_row["bpm_wf"], dtype=float)
    bpm_gt = np.asarray(b3_row["bpm_hkh_gt"], dtype=float)
    rmse = np.asarray(b3_row["rmse"], dtype=float)

    scan = evaluate_hybrid_gating_scan(
        bpm_b1,
        bpm_b2,
        bpm_gt,
        thresholds=THRESHOLDS,
        strategies=("b2", "mean"),
    )

    d1_by_threshold = {
        str(t): diagnose_consensus_windows(bpm_b1, bpm_b2, bpm_gt, t)
        for t in THRESHOLDS
    }

    divergence = np.abs(bpm_b1 - bpm_b2)
    d2_rows = diagnose_trigger_rate_by_group(
        divergence,
        THRESHOLDS,
        is_outlier=scenario_id in OUTLIER_SCENARIOS,
    )

    room, subject = _parse_scenario_id(scenario_id)
    payload = {
        "scenario_id": scenario_id,
        "room": room,
        "subject": subject,
        "is_outlier": scenario_id in OUTLIER_SCENARIOS,
        "preprocess_meta": preprocess_meta,
        "bpm_b1_summary": scan["b1_ref"]["summary"],
        "bpm_b2_summary": scan["b2_ref"]["summary"],
        "b3_rmse_summary": {
            "rmse_mean": b3_row["summary"]["rmse_mean"],
            "rmse_std": b3_row["summary"]["rmse_std"],
        },
        "methods": _serialize_scan_results(scan),
        "diagnostics": {
            "d1_consensus_vs_divergence": d1_by_threshold,
            "d2_trigger_rate": d2_rows,
        },
        "per_window": {
            "bpm_b1": bpm_b1,
            "bpm_b2": bpm_b2,
            "bpm_gt": bpm_gt,
            "divergence": divergence,
            "rmse": rmse,
        },
        "_scan_raw": scan,
    }

    out_path = REPORTS_DIR / f"ble_hkh_hybrid_gating_{scenario_id}.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)

    if verbose:
        b1 = scan["b1_ref"]["summary"]["bpm_mean_abs_err"]
        b2 = scan["b2_ref"]["summary"]["bpm_mean_abs_err"]
        print(f"  B1={b1:.3f}  B2={b2:.3f}  saved {out_path.name}")

    return payload


def compute_cross_domain_summary(all_results: Dict[str, dict]) -> dict:
    """Aggregate per-scenario method summaries across 12 HKH scenarios."""
    method_keys: set = set()
    for payload in all_results.values():
        method_keys.update(payload.get("methods", {}).keys())

    cross: Dict[str, dict] = {}
    for method_key in sorted(method_keys):
        bpm_means: List[float] = []
        bpm_stds: List[float] = []
        trigger_rates: List[float] = []
        labels: List[str] = []
        per_scenario: Dict[str, float] = {}

        for sid, payload in all_results.items():
            row = payload.get("methods", {}).get(method_key)
            if row is None:
                continue
            s = row.get("summary", {})
            mean_err = s.get("bpm_mean_abs_err", float("nan"))
            if np.isfinite(mean_err):
                bpm_means.append(float(mean_err))
                bpm_stds.append(float(s.get("bpm_std_abs_err", 0.0)))
                per_scenario[sid] = float(mean_err)
            tr = row.get("trigger_rate")
            if tr is not None and np.isfinite(tr):
                trigger_rates.append(float(tr))
            labels.append(row.get("label", method_key))

        if not bpm_means:
            continue
        cross[method_key] = {
            "label": labels[0] if labels else method_key,
            "strategy": next(
                (
                    payload["methods"][method_key].get("strategy")
                    for payload in all_results.values()
                    if method_key in payload.get("methods", {})
                ),
                None,
            ),
            "threshold": next(
                (
                    payload["methods"][method_key].get("threshold")
                    for payload in all_results.values()
                    if method_key in payload.get("methods", {})
                ),
                None,
            ),
            "bpm_mean_abs_err": float(np.mean(bpm_means)),
            "bpm_std_abs_err": float(np.mean(bpm_stds)),
            "bpm_per_scenario": per_scenario,
            "trigger_rate_mean": float(np.mean(trigger_rates)) if trigger_rates else float("nan"),
            "n_scenarios": len(bpm_means),
        }

    leaderboard = sorted(cross.values(), key=lambda r: r["bpm_mean_abs_err"])
    return {"methods": cross, "leaderboard": leaderboard}


def aggregate_d1_d2(all_results: Dict[str, dict]) -> dict:
    """Cross-scenario D1 and D2 diagnostics."""
    d1_agg: Dict[str, dict] = {}
    for t in THRESHOLDS:
        key = str(t)
        b1_consensus: List[float] = []
        b2_consensus: List[float] = []
        for payload in all_results.values():
            d1 = payload["diagnostics"]["d1_consensus_vs_divergence"].get(key, {})
            v1 = d1.get("consensus_b1_mean_abs_err", float("nan"))
            v2 = d1.get("consensus_b2_mean_abs_err", float("nan"))
            if np.isfinite(v1):
                b1_consensus.append(v1)
            if np.isfinite(v2):
                b2_consensus.append(v2)
        d1_agg[key] = {
            "consensus_b1_mean_abs_err": float(np.mean(b1_consensus)) if b1_consensus else float("nan"),
            "consensus_b2_mean_abs_err": float(np.mean(b2_consensus)) if b2_consensus else float("nan"),
            "b2_advantage_on_consensus": (
                float(np.mean(b1_consensus) - np.mean(b2_consensus))
                if b1_consensus and b2_consensus
                else float("nan")
            ),
        }

    d2_outlier: Dict[str, List[float]] = {str(t): [] for t in THRESHOLDS}
    d2_normal: Dict[str, List[float]] = {str(t): [] for t in THRESHOLDS}
    for sid, payload in all_results.items():
        for row in payload["diagnostics"]["d2_trigger_rate"]:
            key = str(row["threshold"])
            if sid in OUTLIER_SCENARIOS:
                d2_outlier[key].append(row["trigger_rate"])
            else:
                d2_normal[key].append(row["trigger_rate"])

    d2_summary = {}
    for t in THRESHOLDS:
        key = str(t)
        d2_summary[key] = {
            "outlier_trigger_rate_mean": float(np.mean(d2_outlier[key])) if d2_outlier[key] else float("nan"),
            "normal_trigger_rate_mean": float(np.mean(d2_normal[key])) if d2_normal[key] else float("nan"),
        }

    return {"d1_cross_scenario": d1_agg, "d2_trigger_rate": d2_summary}


def find_best_g_h1(summary: dict) -> Optional[str]:
    """Return method_key of best G-H1 variant."""
    candidates = [(k, v) for k, v in summary["methods"].items() if k.startswith("g_h1_")]
    if not candidates:
        return None
    return min(candidates, key=lambda kv: kv[1]["bpm_mean_abs_err"])[0]


def plot_threshold_scan(summary: dict) -> Path:
    """Threshold scan: BPM cross-scene mean vs T."""
    fig, ax = plt.subplots(figsize=(8, 5))

    b1_mean = summary["methods"].get("g_h3", {}).get("bpm_mean_abs_err", float("nan"))
    b2_mean = summary["methods"].get("g_h4", {}).get("bpm_mean_abs_err", float("nan"))

    for prefix, label, color, marker in (
        ("g_h1_", "G-H1 (consensus→B2)", "crimson", "o"),
        ("g_h2_", "G-H2 (consensus→mean)", "steelblue", "s"),
    ):
        xs, ys = [], []
        for key, row in sorted(summary["methods"].items()):
            if not key.startswith(prefix):
                continue
            t = row.get("threshold")
            if t is None:
                continue
            xs.append(t)
            ys.append(row["bpm_mean_abs_err"])
        if xs:
            ax.plot(xs, ys, marker=marker, color=color, linewidth=2, label=label)

    if np.isfinite(b1_mean):
        ax.axhline(b1_mean, color="gray", linestyle="--", linewidth=1.2, label=f"B1 / B3 ({b1_mean:.3f})")
    if np.isfinite(b2_mean):
        ax.axhline(b2_mean, color="darkorange", linestyle=":", linewidth=1.2, label=f"B2-D ({b2_mean:.3f})")

    ax.set_xlabel("Threshold T (breaths/min)")
    ax.set_ylabel("BPM abs err (12-scenario mean)")
    ax.set_title("G-Hybrid threshold scan")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = FIGURES_DIR / "ble_hkh_hybrid_gating_threshold_scan.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_trigger_timeseries(all_results: Dict[str, dict], best_t: float) -> Path:
    """D3: outlier scenarios — divergence and BPM error time series."""
    fig, axes = plt.subplots(len(OUTLIER_SCENARIOS), 2, figsize=(14, 3.5 * len(OUTLIER_SCENARIOS)))
    if len(OUTLIER_SCENARIOS) == 1:
        axes = np.array([axes])

    for row_idx, sid in enumerate(OUTLIER_SCENARIOS):
        payload = all_results.get(sid)
        if payload is None:
            continue
        pw = payload["per_window"]
        bpm_b1 = pw["bpm_b1"]
        bpm_b2 = pw["bpm_b2"]
        bpm_gt = pw["bpm_gt"]
        divergence = pw["divergence"]
        t = np.arange(len(bpm_gt))

        gated = apply_hybrid_gating(bpm_b1, bpm_b2, threshold=best_t, consensus_strategy="b2")
        bpm_h1 = gated["bpm_final"]
        triggered = gated["gate_triggered"]

        ax_div, ax_bpm = axes[row_idx, 0], axes[row_idx, 1]
        ymax = float(np.nanmax(divergence)) * 1.05 if len(divergence) else 1.0
        ax_div.plot(t, divergence, color="purple", linewidth=1.0, label="|B1−B2|")
        ax_div.axhline(best_t, color="red", linestyle="--", linewidth=1.0, label=f"T={best_t}")
        ax_div.fill_between(t, 0, ymax, where=triggered, alpha=0.15, color="red", label="gate triggered")
        ax_div.set_ylabel("Δ BPM")
        ax_div.set_title(f"{sid} — divergence")
        ax_div.legend(fontsize=7)
        ax_div.grid(True, alpha=0.25)

        err_b1 = np.abs(bpm_b1 - bpm_gt)
        err_b2 = np.abs(bpm_b2 - bpm_gt)
        err_h1 = np.abs(bpm_h1 - bpm_gt)
        ax_bpm.plot(t, err_b1, color="gray", linewidth=1.0, alpha=0.8, label="|B1−GT|")
        ax_bpm.plot(t, err_b2, color="darkorange", linewidth=1.0, alpha=0.8, label="|B2−GT|")
        ax_bpm.plot(t, err_h1, color="crimson", linewidth=1.2, label=f"|G-H1−GT| T={best_t}")
        ax_bpm.set_ylabel("|BPM err|")
        ax_bpm.set_title(f"{sid} — per-window BPM error")
        ax_bpm.legend(fontsize=7)
        ax_bpm.grid(True, alpha=0.25)

    axes[-1, 0].set_xlabel("Window index")
    axes[-1, 1].set_xlabel("Window index")
    fig.suptitle("Outlier scenarios — D3 divergence & BPM error", y=1.01)
    fig.tight_layout()
    path = FIGURES_DIR / "ble_hkh_hybrid_gating_trigger_timeseries.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_error_violin(all_results: Dict[str, dict], best_t: float) -> Path:
    """D4: per-window BPM error violin — B1 / B2 / G-H1."""
    errors_b1: List[float] = []
    errors_b2: List[float] = []
    errors_h1: List[float] = []

    for payload in all_results.values():
        pw = payload["per_window"]
        bpm_b1 = np.asarray(pw["bpm_b1"], dtype=float)
        bpm_b2 = np.asarray(pw["bpm_b2"], dtype=float)
        bpm_gt = np.asarray(pw["bpm_gt"], dtype=float)
        valid = np.isfinite(bpm_gt) & (bpm_gt > 0)
        gated = apply_hybrid_gating(bpm_b1, bpm_b2, threshold=best_t, consensus_strategy="b2")
        bpm_h1 = gated["bpm_final"]
        for bpm, bucket in ((bpm_b1, errors_b1), (bpm_b2, errors_b2), (bpm_h1, errors_h1)):
            m = valid & np.isfinite(bpm)
            bucket.extend(np.abs(bpm[m] - bpm_gt[m]).tolist())

    fig, ax = plt.subplots(figsize=(7, 5))
    data = [errors_b1, errors_b2, errors_h1]
    labels = ["B1 Vote→Equal", "B2-D waveform", f"G-H1 T={best_t}"]
    parts = ax.violinplot(data, showmeans=True, showmedians=True)
    for pc in parts["bodies"]:
        pc.set_alpha(0.7)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Per-window |BPM − GT|")
    ax.set_title("D4 — pooled per-window BPM error (12 scenarios)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = FIGURES_DIR / "ble_hkh_hybrid_gating_error_distribution.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_d2_trigger_rate(diag: dict) -> Path:
    """D2: trigger rate vs T — outlier vs normal."""
    fig, ax = plt.subplots(figsize=(7, 4))
    xs = THRESHOLDS
    outlier = [diag["d2_trigger_rate"][str(t)]["outlier_trigger_rate_mean"] for t in THRESHOLDS]
    normal = [diag["d2_trigger_rate"][str(t)]["normal_trigger_rate_mean"] for t in THRESHOLDS]
    ax.plot(xs, outlier, "o-", color="crimson", label="Outlier scenarios (A-D, C-A)")
    ax.plot(xs, normal, "s-", color="steelblue", label="Normal scenarios")
    ax.set_xlabel("Threshold T (breaths/min)")
    ax.set_ylabel("Gate trigger rate")
    ax.set_title("D2 — divergence trigger rate vs threshold")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = FIGURES_DIR / "ble_hkh_hybrid_gating_d2_trigger_rate.png"
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

    all_results: Dict[str, dict] = {}
    for scenario_id in SCENARIO_IDS:
        print(f"\n{'=' * 72}\nScenario: {scenario_id}\n{'=' * 72}")
        all_results[scenario_id] = run_single_scenario(
            scenario_id,
            filter_params,
            metric_params,
            chfusion_config,
            verbose=True,
        )

    summary = compute_cross_domain_summary(all_results)
    diag = aggregate_d1_d2(all_results)
    best_key = find_best_g_h1(summary)
    best_t = summary["methods"][best_key]["threshold"] if best_key else 1.0

    full_summary = {
        "methods": summary["methods"],
        "leaderboard": summary["leaderboard"],
        "diagnostics": diag,
        "best_g_h1_key": best_key,
        "best_g_h1_threshold": best_t,
        "outlier_scenarios": OUTLIER_SCENARIOS,
        "thresholds": THRESHOLDS,
    }

    summary_path = REPORTS_DIR / "ble_hkh_hybrid_gating_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(full_summary, handle, ensure_ascii=False, indent=2, default=_json_default)

    fig_scan = plot_threshold_scan(summary)
    fig_trigger = plot_trigger_timeseries(all_results, best_t)
    fig_violin = plot_error_violin(all_results, best_t)
    fig_d2 = plot_d2_trigger_rate(diag)

    print("\n=== Cross-domain leaderboard (BPM mean abs err) ===")
    print(f"{'Rank':<5} {'Method':<36} {'BPM mean±std':>16} {'Trigger%':>10}")
    print("-" * 72)
    for i, row in enumerate(summary["leaderboard"], start=1):
        tr = row.get("trigger_rate_mean", float("nan"))
        tr_txt = f"{tr * 100:.1f}%" if np.isfinite(tr) else "N/A"
        print(
            f"{i:<5} {row['label']:<36} "
            f"{row['bpm_mean_abs_err']:.3f}±{row['bpm_std_abs_err']:.3f}".rjust(16)
            + f"  {tr_txt:>10}"
        )

    b1 = summary["methods"].get("g_h3", {}).get("bpm_mean_abs_err", float("nan"))
    best_gh1 = summary["methods"].get(best_key, {}).get("bpm_mean_abs_err", float("nan")) if best_key else float("nan")
    print(f"\nBest G-H1: {best_key} T={best_t} → BPM {best_gh1:.3f} (B1 baseline {b1:.3f})")
    print(f"Summary JSON: {summary_path}")
    print(f"Threshold scan: {fig_scan}")
    print(f"Trigger TS:     {fig_trigger}")
    print(f"Violin:         {fig_violin}")
    print(f"D2 trigger:     {fig_d2}")
