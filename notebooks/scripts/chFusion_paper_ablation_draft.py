"""Run draft §6.5 ablation matrix on HKH 12 scenarios and redraw Fig 8.

Plan: docs/plans/paper_ablation_draft_align_plan.md

Run:
    python notebooks/scripts/chFusion_paper_ablation_draft.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.b3_pipeline import (
    DRAFT_ABLATION_SPECS,
    validate_b3_variant_against_hkh,
)
from ble_analysis.ble_hkh_validation import load_hkh_gt_signals
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import ChFusionConfig, load_multichannel_for_scenario
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

PANEL_SPEC = [
    ("draft_s_none", "draft_s_channel", "draft_s_modal", "draft_s_full"),
]
PANEL_WAVE = [
    ("draft_w_none", "draft_w_channel", "draft_w_modal", "draft_w_full"),
]
PANEL_MODAL = [
    ("draft_m_remote", "draft_m_local", "draft_m_phase", "draft_s_full"),
]

SHORT_LABEL = {
    "draft_s_none": "No fusion",
    "draft_s_channel": "Channel only",
    "draft_s_modal": "Modal only",
    "draft_s_full": "BreatheCS",
    "draft_w_none": "No fusion",
    "draft_w_channel": "Channel only",
    "draft_w_modal": "Modal only",
    "draft_w_full": "BreatheCS",
    "draft_m_remote": "Remote",
    "draft_m_local": "Local",
    "draft_m_phase": "Phase",
}


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _save_figure(fig: plt.Figure, stem: str) -> Path:
    png = FIGURES_DIR / f"{stem}.png"
    pdf = FIGURES_DIR / f"{stem}.pdf"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    return png


def run_scenario(scenario_id: str, verbose: bool = True) -> dict:
    scenario = load_scenario(scenario_id, project_root=project_root)
    if verbose:
        print_scenario_summary(scenario)

    processed_dir = (project_root / Path(scenario.data_file)).parent
    hkh_bp, hkh_t, cs_t, preprocess_meta = load_hkh_gt_signals(processed_dir)
    fs_hkh = preprocess_meta.get("sampling_rate_hz", {}).get("hkh_used")

    filter_params = FilterParams()
    metric_params = BreathMetricParams()
    chfusion_config = ChFusionConfig(
        breath_freq_low=metric_params.breath_freq_low,
        breath_freq_high=metric_params.breath_freq_high,
        window_length_sec=metric_params.window_length_sec,
        step_length_sec=metric_params.step_length_sec,
    )

    multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=filter_params,
        cache_dir=CACHE_DIR,
        verbose=verbose,
    )

    methods: Dict[str, dict] = {}
    for label, key, cfg in DRAFT_ABLATION_SPECS:
        if verbose:
            print(f"  running {key} ({label})")
        row = validate_b3_variant_against_hkh(
            multichannel_by_var,
            "main",
            hkh_bp,
            hkh_t,
            cs_t,
            variant_key=key,
            variant=cfg,
            config=chfusion_config,
            metric_params=metric_params,
            fs_hkh_override=fs_hkh,
            verbose=False,
        )
        if row is not None:
            methods[key] = row

    payload = {
        "scenario_id": scenario_id,
        "preprocess_meta": preprocess_meta,
        "methods": {
            k: {
                "label": v.get("label", k),
                "method_key": k,
                "bpm_mean_abs_err": v["summary"]["bpm_mean_abs_err"],
                "bpm_std_abs_err": v["summary"]["bpm_std_abs_err"],
                "rmse_mean": v["summary"]["rmse_mean"],
                "rmse_std": v["summary"]["rmse_std"],
                "has_waveform": v.get("has_waveform", False),
            }
            for k, v in methods.items()
        },
    }
    out = REPORTS_DIR / f"ble_hkh_draft_ablation_{scenario_id}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    if verbose:
        print(f"Saved {out.name}")
    return {"scenario_id": scenario_id, "methods": methods}


def plot_draft_fig8(summary: dict) -> List[Path]:
    methods = summary["methods"]
    paths: List[Path] = []

    def _vals(keys):
        bpm, rmse, labels = [], [], []
        for k in keys:
            m = methods[k]
            labels.append(SHORT_LABEL.get(k, k))
            bpm.append(m["bpm_mean_abs_err"])
            rmse.append(m["rmse_mean"] if m.get("has_waveform") and math.isfinite(m.get("rmse_mean") or float("nan")) else None)
        return labels, bpm, rmse

    # Fig 8a: spectral + waveform side by side (BPM)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=False)
    for ax, keys, title in (
        (axes[0], PANEL_SPEC[0], "(a) Spectral fusion"),
        (axes[1], PANEL_WAVE[0], "(b) Waveform fusion"),
    ):
        labels, bpm, _rmse = _vals(keys)
        colors = ["#999999"] * (len(keys) - 1) + ["#E63946"]
        y = np.arange(len(keys))
        bars = ax.barh(y, bpm, color=colors, alpha=0.92, height=0.65)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel("BPM abs err (12-scenario mean)")
        ax.set_title(title.split(" ", 1)[0], fontsize=10)  # panel id only, e.g. (a)
        ax.grid(True, axis="x", alpha=0.3)
        for i, v in enumerate(bpm):
            ax.text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=8)
            if keys[i].endswith("_full"):
                bars[i].set_edgecolor("k")
                bars[i].set_linewidth(1.2)
    fig.tight_layout()
    paths.append(_save_figure(fig, "paper_fig8a_ablation_draft_bpm"))
    plt.close(fig)

    # Fig 8a RMSE for waveform panel only
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    labels, _bpm, rmse = _vals(PANEL_WAVE[0])
    vals = [r if r is not None else np.nan for r in rmse]
    colors = ["#999999"] * (len(labels) - 1) + ["#E63946"]
    y = np.arange(len(labels))
    ax.barh(y, vals, color=colors, alpha=0.92, height=0.65)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("RMSE mean (z-score vs belt)")
    ax.set_title("(b′)", fontsize=10)
    ax.grid(True, axis="x", alpha=0.3)
    for i, v in enumerate(vals):
        if math.isfinite(v):
            ax.text(v + 0.005, i, f"{v:.3f}", va="center", fontsize=8)
    fig.tight_layout()
    paths.append(_save_figure(fig, "paper_fig8a_ablation_draft_rmse"))
    plt.close(fig)

    # Fig 8c: single modal
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    labels, bpm, _ = _vals(PANEL_MODAL[0])
    colors = ["#999999", "#999999", "#999999", "#E63946"]
    y = np.arange(len(labels))
    bars = ax.barh(y, bpm, color=colors, alpha=0.92, height=0.65)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("BPM abs err (12-scenario mean)")
    ax.set_title("(c)", fontsize=10)
    ax.grid(True, axis="x", alpha=0.3)
    bars[-1].set_edgecolor("k")
    bars[-1].set_linewidth(1.2)
    for i, v in enumerate(bpm):
        ax.text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=8)
    fig.tight_layout()
    paths.append(_save_figure(fig, "paper_fig8c_ablation_draft_modal"))
    plt.close(fig)

    return paths


def main() -> None:
    all_results: Dict[str, dict] = {}
    for sid in SCENARIO_IDS:
        print(f"\n{'#' * 70}\n# {sid}\n{'#' * 70}")
        all_results[sid] = run_scenario(sid, verbose=True)

    from collections import defaultdict

    agg: Dict[str, List[dict]] = defaultdict(list)
    for _sid, payload in all_results.items():
        for k, row in payload["methods"].items():
            agg[k].append(row)
    methods_out = {}
    for k, rows in agg.items():
        bpms = [r["summary"]["bpm_mean_abs_err"] for r in rows]
        rmses = [r["summary"]["rmse_mean"] for r in rows if r.get("has_waveform")]
        label = rows[0].get("label", k)
        methods_out[k] = {
            "label": label,
            "method_key": k,
            "bpm_mean_abs_err": float(np.mean(bpms)),
            "bpm_std_abs_err": float(np.std(bpms, ddof=1)) if len(bpms) > 1 else 0.0,
            "rmse_mean": float(np.nanmean(rmses)) if rmses else float("nan"),
            "rmse_std": float(np.nanstd(rmses, ddof=1)) if len(rmses) > 1 else float("nan"),
            "has_waveform": bool(rows[0].get("has_waveform")),
            "n_scenarios": len(rows),
            "bpm_per_scenario": bpms,
        }
    summary = {"methods": methods_out, "n_scenarios": len(SCENARIO_IDS)}

    out = REPORTS_DIR / "ble_hkh_draft_ablation_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    print(f"\nSaved summary: {out}")

    paths = plot_draft_fig8(summary)
    for p in paths:
        print(f"Saved figure: {p.name}")

    print("\n=== Draft ablation BPM leaderboard ===")
    for k, m in sorted(summary["methods"].items(), key=lambda kv: kv[1]["bpm_mean_abs_err"]):
        rmse = m.get("rmse_mean")
        rmse_s = f"{rmse:.3f}" if rmse is not None and math.isfinite(rmse) else "N/A"
        print(f"{m['label']:<28} BPM={m['bpm_mean_abs_err']:.3f}  RMSE={rmse_s}")


if __name__ == "__main__":
    main()
