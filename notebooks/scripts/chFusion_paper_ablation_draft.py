"""Run draft §6.5 ablation matrix on HKH 12 scenarios and redraw Fig 8.

Plan: docs/plans/paper_ablation_draft_align_plan.md

Run (full):
    python notebooks/scripts/chFusion_paper_ablation_draft.py

Replot only (reuse summary JSON; still rewrites the summary file):
    python notebooks/scripts/chFusion_paper_ablation_draft.py --plot-only

Redraw Fig 8 from existing JSON without rewriting the summary:
    python notebooks/scripts/chFusion_paper_ablation_draft.py --figures-only

Box-plot copies only (does not overwrite Fig 8 bar charts):
    python notebooks/scripts/chFusion_paper_ablation_draft.py --box-only

Only run selected keys then merge + replot:
    python notebooks/scripts/chFusion_paper_ablation_draft.py --only-keys draft_ms_remote,draft_ms_local,...
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

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

PANEL_SPEC = ("draft_s_none", "draft_s_channel", "draft_s_modal", "draft_s_rl")
PANEL_WAVE = ("draft_w_none", "draft_w_channel", "draft_w_modal", "draft_w_rl")
PANEL_MS = ("draft_ms_remote", "draft_ms_local", "draft_ms_phase", "draft_s_rl")
PANEL_MW = ("draft_mw_remote", "draft_mw_local", "draft_mw_phase", "draft_w_rl")

SHORT_LABEL = {
    "draft_s_none": "No fusion",
    "draft_s_channel": "Channel only",
    "draft_s_modal": "Modal only",
    "draft_s_full": "BreatheCS",
    "draft_s_rl": "BreatheCS",
    "draft_w_none": "No fusion",
    "draft_w_channel": "Channel only",
    "draft_w_modal": "Modal only",
    "draft_w_full": "BreatheCS",
    "draft_w_rl": "BreatheCS",
    "draft_ms_remote": "Remote",
    "draft_ms_local": "Local",
    "draft_ms_phase": "Phase",
    "draft_mw_remote": "Remote",
    "draft_mw_local": "Local",
    "draft_mw_phase": "Phase",
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


def _fmt3(v: float) -> str:
    return f"{v:.3f}"


def _std0(values: Sequence[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0 or not np.all(np.isfinite(arr)):
        raise ValueError("cannot compute std: empty or non-finite series")
    return float(np.std(arr, ddof=0))


def _bpm_series(summary: dict, key: str) -> List[float]:
    return [float(x) for x in summary["methods"][key]["bpm_per_scenario"]]


def _rmse_series(key: str) -> List[float]:
    """Per-scenario waveform RMSE. Summary stores only ddof=1 rmse_std."""
    vals: List[float] = []
    for sid in SCENARIO_IDS:
        path = REPORTS_DIR / f"ble_hkh_draft_ablation_{sid}.json"
        row = json.loads(path.read_text(encoding="utf-8"))["methods"][key]
        rmse = row.get("rmse_mean")
        if rmse is None or not math.isfinite(float(rmse)):
            raise ValueError(f"{sid}: {key} rmse_mean is not finite")
        vals.append(float(rmse))
    return vals


def _nonneg_err(means, stds) -> np.ndarray:
    """Lower whisker stops at 0. Upper whisker is +std. Stored std is unchanged."""
    means = np.asarray(means, dtype=float)
    stds = np.asarray(stds, dtype=float)
    lower = np.minimum(stds, np.maximum(means, 0.0))
    return np.vstack([lower, stds])


def _grouped_metric_bars(
    method_labels: Sequence[str],
    bpm_series: Sequence[Tuple[str, Sequence[float], Sequence[float]]],
    rmse_series: Tuple[str, Sequence[float], Sequence[float]],
) -> plt.Figure:
    """Grouped bars. Left axis: RR absolute error (BPM). Right axis: waveform RMSE."""
    n_methods = len(method_labels)
    n_slots = len(bpm_series) + 1
    x = np.arange(n_methods)
    width = 0.8 / n_slots
    cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    bpm_top = 0.0
    for i, (label, means, stds) in enumerate(bpm_series):
        offset = (i - (n_slots - 1) / 2) * width
        ax.bar(
            x + offset,
            list(means),
            width,
            yerr=_nonneg_err(means, stds),
            label=label,
            color=cycle[i % len(cycle)],
            ecolor="black",
            capsize=2,
            alpha=0.9,
            error_kw={"elinewidth": 0.8, "capthick": 0.8},
        )
        bpm_top = max(bpm_top, float(np.max(np.asarray(means) + np.asarray(stds))))
    rmse_label, rmse_means, rmse_stds = rmse_series
    rmse_color = cycle[len(bpm_series) % len(cycle)]
    offset = (len(bpm_series) - (n_slots - 1) / 2) * width
    ax2 = ax.twinx()
    ax2.bar(
        x + offset,
        list(rmse_means),
        width,
        yerr=_nonneg_err(rmse_means, rmse_stds),
        label=rmse_label,
        color=rmse_color,
        ecolor="black",
        capsize=2,
        alpha=0.9,
        error_kw={"elinewidth": 0.8, "capthick": 0.8},
    )
    rmse_top = float(np.max(np.asarray(rmse_means, dtype=float) + np.asarray(rmse_stds, dtype=float)))
    ax.set_xticks(x)
    ax.set_xticklabels(list(method_labels), fontsize=10)
    ax.set_ylim(0, bpm_top * 1.18 if bpm_top > 0 else 1.0)
    ax2.set_ylim(0, rmse_top * 1.18 if rmse_top > 0 else 1.0)
    ax.set_ylabel("RR absolute error (BPM)")
    ax2.set_ylabel("Waveform RMSE")
    handles, labels = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles + handles2, labels + labels2, fontsize=8, loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def _paint_boxes(bp, colors: Sequence[str]) -> None:
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_edgecolor("black")
        patch.set_alpha(0.9)
    for line in bp["medians"]:
        line.set_color("black")
        line.set_linewidth(1.2)
    for key in ("whiskers", "caps"):
        for line in bp[key]:
            line.set_color("black")
            line.set_linewidth(1.0)
    for flier in bp["fliers"]:
        flier.set(
            marker="o",
            markerfacecolor="black",
            markeredgecolor="black",
            markersize=3.5,
            alpha=0.85,
        )


def _grouped_metric_boxes(
    method_labels: Sequence[str],
    bpm_series: Sequence[Tuple[str, Sequence[Sequence[float]]]],
    rmse_series: Tuple[str, Sequence[Sequence[float]]],
) -> plt.Figure:
    """Box plots on the same dual-axis layout as the Fig 8 bars. One box = 12 scenarios."""
    n_methods = len(method_labels)
    n_slots = len(bpm_series) + 1
    x = np.arange(n_methods)
    width = 0.8 / n_slots
    cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    meanprops = {"marker": "o", "markerfacecolor": "black", "markeredgecolor": "black", "markersize": 3.5}
    bpm_top = 0.0
    handles = []
    for i, (label, groups) in enumerate(bpm_series):
        offset = (i - (n_slots - 1) / 2) * width
        color = cycle[i % len(cycle)]
        bp = ax.boxplot(
            list(groups),
            positions=x + offset,
            widths=width * 0.9,
            patch_artist=True,
            showmeans=True,
            meanprops=meanprops,
            manage_ticks=False,
        )
        _paint_boxes(bp, [color] * n_methods)
        handles.append(Patch(facecolor=color, edgecolor="black", label=label))
        bpm_top = max(bpm_top, float(np.max(np.asarray(groups, dtype=float))))
    rmse_label, rmse_groups = rmse_series
    rmse_color = cycle[len(bpm_series) % len(cycle)]
    offset = (len(bpm_series) - (n_slots - 1) / 2) * width
    ax2 = ax.twinx()
    bp = ax2.boxplot(
        list(rmse_groups),
        positions=x + offset,
        widths=width * 0.9,
        patch_artist=True,
        showmeans=True,
        meanprops=meanprops,
        manage_ticks=False,
    )
    _paint_boxes(bp, [rmse_color] * n_methods)
    handles.append(Patch(facecolor=rmse_color, edgecolor="black", label=rmse_label))
    handles.append(plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="black", markersize=4, label="mean"))
    rmse_top = float(np.max(np.asarray(rmse_groups, dtype=float)))
    ax.set_xticks(x)
    ax.set_xticklabels(list(method_labels), fontsize=10)
    ax.set_xlim(-0.5, n_methods - 0.5)
    ax.set_ylim(0, bpm_top * 1.12 if bpm_top > 0 else 1.0)
    ax2.set_ylim(0, rmse_top * 1.12 if rmse_top > 0 else 1.0)
    ax.set_ylabel("RR absolute error (BPM)")
    ax2.set_ylabel("Waveform RMSE")
    ax.legend(handles=handles, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_draft_fig8_box(summary: dict) -> List[Path]:
    """Box-plot copies. Does not overwrite the Fig 8 bar charts or the summary JSON."""
    paths: List[Path] = []
    fusion_labels = [SHORT_LABEL[k] for k in PANEL_SPEC]
    fig = _grouped_metric_boxes(
        fusion_labels,
        (
            ("Spectral BPM", [_bpm_series(summary, k) for k in PANEL_SPEC]),
            ("Waveform BPM", [_bpm_series(summary, k) for k in PANEL_WAVE]),
        ),
        ("Waveform RMSE", [_rmse_series(k) for k in PANEL_WAVE]),
    )
    paths.append(_save_figure(fig, "paper_fig8_abc_fusion_box"))
    plt.close(fig)

    modal_labels = [SHORT_LABEL[k] for k in PANEL_MS]
    fig = _grouped_metric_boxes(
        modal_labels,
        (
            ("Spectral BPM", [_bpm_series(summary, k) for k in PANEL_MS]),
            ("Waveform BPM", [_bpm_series(summary, k) for k in PANEL_MW]),
        ),
        ("Waveform RMSE", [_rmse_series(k) for k in PANEL_MW]),
    )
    paths.append(_save_figure(fig, "paper_fig8_def_single_modal_box"))
    plt.close(fig)
    return paths


def run_scenario(
    scenario_id: str,
    *,
    only_keys: Optional[Sequence[str]] = None,
    verbose: bool = True,
) -> dict:
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

    key_set = set(only_keys) if only_keys else None
    methods: Dict[str, dict] = {}
    for label, key, cfg in DRAFT_ABLATION_SPECS:
        if key_set is not None and key not in key_set:
            continue
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

    # Merge into existing per-scenario JSON if partial run
    out = REPORTS_DIR / f"ble_hkh_draft_ablation_{scenario_id}.json"
    existing_methods: Dict[str, dict] = {}
    if out.exists() and key_set is not None:
        old = json.loads(out.read_text(encoding="utf-8"))
        existing_methods = old.get("methods", {})

    compact = {
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
    }
    existing_methods.update(compact)

    payload = {
        "scenario_id": scenario_id,
        "preprocess_meta": preprocess_meta,
        "methods": existing_methods,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    if verbose:
        print(f"Saved {out.name}")
    return {"scenario_id": scenario_id, "methods": methods}


def aggregate_from_scenario_files(keys: Optional[Iterable[str]] = None) -> dict:
    wanted = set(keys) if keys is not None else None
    agg: Dict[str, List[dict]] = defaultdict(list)
    for sid in SCENARIO_IDS:
        path = REPORTS_DIR / f"ble_hkh_draft_ablation_{sid}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for k, row in payload.get("methods", {}).items():
            if wanted is not None and k not in wanted:
                continue
            agg[k].append(row)

    methods_out = {}
    for k, rows in agg.items():
        bpms = [float(r["bpm_mean_abs_err"]) for r in rows]
        rmses = [
            float(r["rmse_mean"])
            for r in rows
            if r.get("has_waveform") and r.get("rmse_mean") is not None and math.isfinite(float(r["rmse_mean"]))
        ]
        methods_out[k] = {
            "label": rows[0].get("label", k),
            "method_key": k,
            "bpm_mean_abs_err": float(np.mean(bpms)),
            "bpm_std_abs_err": float(np.std(bpms, ddof=1)) if len(bpms) > 1 else 0.0,
            "rmse_mean": float(np.mean(rmses)) if rmses else float("nan"),
            "rmse_std": float(np.std(rmses, ddof=1)) if len(rmses) > 1 else float("nan"),
            "has_waveform": bool(rows[0].get("has_waveform")),
            "n_scenarios": len(rows),
            "bpm_per_scenario": bpms,
        }
    return {"methods": methods_out, "n_scenarios": len(SCENARIO_IDS)}


def build_single_modal_table(summary: dict) -> str:
    m = summary["methods"]

    def g(key: str, field: str) -> str:
        if key not in m:
            return "—"
        v = m[key].get(field)
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return "—"
        return _fmt3(float(v))

    lines = [
        "| Domain | Remote | Local | Phase | BreatheCS |",
        "|---|---:|---:|---:|---:|",
        f"| Spectral BPM | {g('draft_ms_remote','bpm_mean_abs_err')} | {g('draft_ms_local','bpm_mean_abs_err')} | {g('draft_ms_phase','bpm_mean_abs_err')} | {g('draft_s_rl','bpm_mean_abs_err')} |",
        f"| Waveform BPM | {g('draft_mw_remote','bpm_mean_abs_err')} | {g('draft_mw_local','bpm_mean_abs_err')} | {g('draft_mw_phase','bpm_mean_abs_err')} | {g('draft_w_rl','bpm_mean_abs_err')} |",
        f"| Waveform RMSE | {g('draft_mw_remote','rmse_mean')} | {g('draft_mw_local','rmse_mean')} | {g('draft_mw_phase','rmse_mean')} | {g('draft_w_rl','rmse_mean')} |",
        "",
        "> HKH 12-scenario mean. Spectral rows have no RMSE. BreatheCS columns use endpoint-amplitude R+L (`draft_s_rl` / `draft_w_rl`).",
    ]
    return "\n".join(lines)


def _panel_stats(summary: dict, keys: Sequence[str], kind: str) -> dict:
    """kind is 'bpm' or 'rmse'. Means follow the stored series; std is ddof=0."""
    labels = []
    means = []
    stds = []
    for key in keys:
        if kind == "bpm":
            series = _bpm_series(summary, key)
        else:
            series = _rmse_series(key)
        labels.append(SHORT_LABEL.get(key, key))
        means.append(float(np.mean(series)))
        stds.append(_std0(series))
    return {"keys": list(keys), "labels": labels, "mean": means, "std_ddof0": stds}


def plot_draft_fig8(summary: dict) -> Tuple[List[Path], dict]:
    paths: List[Path] = []

    spec_bpm = _panel_stats(summary, PANEL_SPEC, "bpm")
    wave_bpm = _panel_stats(summary, PANEL_WAVE, "bpm")
    wave_rmse = _panel_stats(summary, PANEL_WAVE, "rmse")
    ms_bpm = _panel_stats(summary, PANEL_MS, "bpm")
    mw_bpm = _panel_stats(summary, PANEL_MW, "bpm")
    mw_rmse = _panel_stats(summary, PANEL_MW, "rmse")

    fusion_labels = [SHORT_LABEL[k] for k in PANEL_SPEC]
    fig = _grouped_metric_bars(
        fusion_labels,
        (
            ("Spectral BPM", spec_bpm["mean"], spec_bpm["std_ddof0"]),
            ("Waveform BPM", wave_bpm["mean"], wave_bpm["std_ddof0"]),
        ),
        ("Waveform RMSE", wave_rmse["mean"], wave_rmse["std_ddof0"]),
    )
    paths.append(_save_figure(fig, "paper_fig8_abc_fusion"))
    plt.close(fig)

    modal_labels = [SHORT_LABEL[k] for k in PANEL_MS]
    fig = _grouped_metric_bars(
        modal_labels,
        (
            ("Spectral BPM", ms_bpm["mean"], ms_bpm["std_ddof0"]),
            ("Waveform BPM", mw_bpm["mean"], mw_bpm["std_ddof0"]),
        ),
        ("Waveform RMSE", mw_rmse["mean"], mw_rmse["std_ddof0"]),
    )
    paths.append(_save_figure(fig, "paper_fig8_def_single_modal"))
    plt.close(fig)

    table_md = "## Single-modal ablation (HKH)\n\n" + build_single_modal_table(summary) + "\n"
    table_path = REPORTS_DIR / "paper_fig8_single_modal_table.md"
    table_path.write_text(table_md, encoding="utf-8")
    print(f"Saved table: {table_path.name}")

    stats = {
        "fusion": {"spectral_bpm": spec_bpm, "waveform_bpm": wave_bpm, "waveform_rmse": wave_rmse},
        "single_modal": {"spectral_bpm": ms_bpm, "waveform_bpm": mw_bpm, "waveform_rmse": mw_rmse},
    }
    return paths, stats


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plot-only", action="store_true", help="Only replot from existing per-scenario JSON")
    p.add_argument(
        "--figures-only",
        action="store_true",
        help="Redraw Fig 8 from existing JSON. Do not rerun experiments or rewrite the summary.",
    )
    p.add_argument(
        "--box-only",
        action="store_true",
        help="Write Fig 8 box-plot copies. Do not overwrite the bar charts or the summary.",
    )
    p.add_argument(
        "--only-keys",
        type=str,
        default="",
        help="Comma-separated method keys to (re)run; merge into existing files",
    )
    return p.parse_args()


def _write_fig8_numbers(stats: dict, paths: List[Path]) -> Path:
    out = REPORTS_DIR / "paper_ch6_tables_to_figures_results.json"
    payload = {}
    if out.exists():
        payload = json.loads(out.read_text(encoding="utf-8"))
    payload["fig8"] = {
        "figures": [str(p) for p in paths],
        "ddof": 0,
        "breathecs_keys": {"spectral": "draft_s_rl", "waveform": "draft_w_rl"},
        "panels": stats,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return out


def main() -> None:
    args = parse_args()
    if args.box_only:
        summary_path = REPORTS_DIR / "ble_hkh_draft_ablation_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        paths = plot_draft_fig8_box(summary)
        out = REPORTS_DIR / "paper_ch6_tables_to_figures_results.json"
        payload = {}
        if out.exists():
            payload = json.loads(out.read_text(encoding="utf-8"))
        box = payload.get("box_figures", {})
        box["fig8"] = [str(p) for p in paths]
        box["fig8_note"] = "12-scenario box plots. Median line, black dot = mean. Bar charts were not rewritten."
        payload["box_figures"] = box
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        for p in paths:
            print(f"Saved box figure: {p.name}")
        print("Fig 8 box plots only; bar charts and summary JSON were not rewritten.")
        return

    if args.figures_only:
        summary_path = REPORTS_DIR / "ble_hkh_draft_ablation_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        paths, stats = plot_draft_fig8(summary)
        out = _write_fig8_numbers(stats, paths)
        for p in paths:
            print(f"Saved figure: {p.name}")
        print(f"Saved numbers: {out.name}")
        print("Fig 8 redraw only; summary JSON was not rewritten.")
        return

    only_keys = [k.strip() for k in args.only_keys.split(",") if k.strip()] or None

    if not args.plot_only:
        for sid in SCENARIO_IDS:
            print(f"\n{'#' * 70}\n# {sid}\n{'#' * 70}")
            run_scenario(sid, only_keys=only_keys, verbose=True)

    # Aggregate all keys present on disk (full matrix after merge)
    all_keys = [k for _l, k, _c in DRAFT_ABLATION_SPECS]
    summary = aggregate_from_scenario_files(all_keys)

    # Drop obsolete hybrid single-modal keys from summary display if present
    for obsolete in ("draft_m_remote", "draft_m_local", "draft_m_phase"):
        summary["methods"].pop(obsolete, None)

    out = REPORTS_DIR / "ble_hkh_draft_ablation_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    print(f"\nSaved summary: {out}")

    paths, stats = plot_draft_fig8(summary)
    _write_fig8_numbers(stats, paths)
    for p in paths:
        print(f"Saved figure: {p.name}")

    print("\n=== Draft ablation BPM leaderboard ===")
    for k, m in sorted(summary["methods"].items(), key=lambda kv: kv[1]["bpm_mean_abs_err"]):
        rmse = m.get("rmse_mean")
        rmse_s = _fmt3(rmse) if rmse is not None and math.isfinite(rmse) else "N/A"
        print(f"{m['label']:<28} BPM={_fmt3(m['bpm_mean_abs_err'])}  RMSE={rmse_s}")

    print("\n=== Single-modal table ===")
    print(build_single_modal_table(summary))


if __name__ == "__main__":
    main()
