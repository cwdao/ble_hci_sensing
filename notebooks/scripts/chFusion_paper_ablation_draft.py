"""Run draft §6.5 ablation matrix on HKH 12 scenarios and redraw Fig 8.

Plan: docs/plans/paper_ablation_draft_align_plan.md

Run (full):
    python notebooks/scripts/chFusion_paper_ablation_draft.py

Replot only (reuse summary JSON):
    python notebooks/scripts/chFusion_paper_ablation_draft.py --plot-only

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
from typing import Dict, Iterable, List, Optional, Sequence

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

PANEL_SPEC = ("draft_s_none", "draft_s_channel", "draft_s_modal", "draft_s_full")
PANEL_WAVE = ("draft_w_none", "draft_w_channel", "draft_w_modal", "draft_w_full")
PANEL_MS = ("draft_ms_remote", "draft_ms_local", "draft_ms_phase", "draft_s_full")
PANEL_MW = ("draft_mw_remote", "draft_mw_local", "draft_mw_phase", "draft_w_full")

SHORT_LABEL = {
    "draft_s_none": "No fusion",
    "draft_s_channel": "Channel only",
    "draft_s_modal": "Modal only",
    "draft_s_full": "BreatheCS",
    "draft_w_none": "No fusion",
    "draft_w_channel": "Channel only",
    "draft_w_modal": "Modal only",
    "draft_w_full": "BreatheCS",
    "draft_ms_remote": "Remote",
    "draft_ms_local": "Local",
    "draft_ms_phase": "Phase",
    "draft_mw_remote": "Remote",
    "draft_mw_local": "Local",
    "draft_mw_phase": "Phase",
}

BREATHECS_COLOR = "#E63946"
OTHER_COLOR = "#999999"


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


def _is_breathecs(key: str) -> bool:
    return key in ("draft_s_full", "draft_w_full") or key.endswith("_full")


def _barh_panel(
    ax,
    keys: Sequence[str],
    values: Sequence[float],
    *,
    xlabel: str,
    title: str,
    value_fmt: str = "{:.3f}",
) -> None:
    labels = [SHORT_LABEL.get(k, k) for k in keys]
    y = np.arange(len(keys))
    for i, (key, val) in enumerate(zip(keys, values)):
        is_bc = _is_breathecs(key)
        ax.barh(
            i,
            val,
            color=BREATHECS_COLOR if is_bc else OTHER_COLOR,
            alpha=0.92,
            height=0.65,
            edgecolor="black" if is_bc else "none",
            linewidth=1.5 if is_bc else 0.0,
            zorder=3,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=10)
    ax.grid(True, axis="x", alpha=0.3)
    finite = [v for v in values if math.isfinite(v)]
    xmax = max(finite) if finite else 1.0
    ax.set_xlim(0, xmax * 1.18)
    for i, v in enumerate(values):
        if not math.isfinite(v):
            continue
        ax.text(v + xmax * 0.02, i, value_fmt.format(v), va="center", fontsize=8)


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
        "| Domain | Remote | Local | Phase | BreatheCS (3-modal) |",
        "|---|---:|---:|---:|---:|",
        f"| Spectral BPM | {g('draft_ms_remote','bpm_mean_abs_err')} | {g('draft_ms_local','bpm_mean_abs_err')} | {g('draft_ms_phase','bpm_mean_abs_err')} | {g('draft_s_full','bpm_mean_abs_err')} |",
        f"| Waveform BPM | {g('draft_mw_remote','bpm_mean_abs_err')} | {g('draft_mw_local','bpm_mean_abs_err')} | {g('draft_mw_phase','bpm_mean_abs_err')} | {g('draft_w_full','bpm_mean_abs_err')} |",
        f"| Waveform RMSE | {g('draft_mw_remote','rmse_mean')} | {g('draft_mw_local','rmse_mean')} | {g('draft_mw_phase','rmse_mean')} | {g('draft_w_full','rmse_mean')} |",
        "",
        "> HKH 12-scenario mean. Spectral rows have no RMSE. BreatheCS columns use full three-modal fusion.",
    ]
    return "\n".join(lines)


def plot_draft_fig8(summary: dict) -> List[Path]:
    methods = summary["methods"]
    paths: List[Path] = []

    def bpm_of(keys):
        return [float(methods[k]["bpm_mean_abs_err"]) for k in keys]

    def rmse_of(keys):
        out = []
        for k in keys:
            v = methods[k].get("rmse_mean")
            out.append(float(v) if v is not None and math.isfinite(float(v)) else float("nan"))
        return out

    # (a)(b)(c): fusion-level — spectral BPM | waveform BPM | waveform RMSE
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.0), sharey=False)
    _barh_panel(
        axes[0],
        PANEL_SPEC,
        bpm_of(PANEL_SPEC),
        xlabel="BPM abs err",
        title="(a) Fusion levels · spectral BPM",
    )
    _barh_panel(
        axes[1],
        PANEL_WAVE,
        bpm_of(PANEL_WAVE),
        xlabel="BPM abs err",
        title="(b) Fusion levels · waveform BPM",
    )
    _barh_panel(
        axes[2],
        PANEL_WAVE,
        rmse_of(PANEL_WAVE),
        xlabel="RMSE mean",
        title="(c) Fusion levels · waveform RMSE",
    )
    fig.tight_layout()
    paths.append(_save_figure(fig, "paper_fig8_abc_fusion"))
    plt.close(fig)

    # (d)(e)(f): single-modal — spectral BPM | wave BPM | wave RMSE
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.0), sharey=False)
    _barh_panel(
        axes[0],
        PANEL_MS,
        bpm_of(PANEL_MS),
        xlabel="BPM abs err",
        title="(d) Single-modal · spectral BPM",
    )
    _barh_panel(
        axes[1],
        PANEL_MW,
        bpm_of(PANEL_MW),
        xlabel="BPM abs err",
        title="(e) Single-modal · waveform BPM",
    )
    _barh_panel(
        axes[2],
        PANEL_MW,
        rmse_of(PANEL_MW),
        xlabel="RMSE mean",
        title="(f) Single-modal · waveform RMSE",
    )
    fig.tight_layout()
    paths.append(_save_figure(fig, "paper_fig8_def_single_modal"))
    plt.close(fig)

    table_md = "## Single-modal ablation (HKH)\n\n" + build_single_modal_table(summary) + "\n"
    table_path = REPORTS_DIR / "paper_fig8_single_modal_table.md"
    table_path.write_text(table_md, encoding="utf-8")
    print(f"Saved table: {table_path.name}")

    return paths


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plot-only", action="store_true", help="Only replot from existing per-scenario JSON")
    p.add_argument(
        "--only-keys",
        type=str,
        default="",
        help="Comma-separated method keys to (re)run; merge into existing files",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
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

    paths = plot_draft_fig8(summary)
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
