"""E3/E4: Quality-weighted modal fusion + Phase gating on HKH + CS.

Plan: docs/plans/modal_quality_gating_plan.md

Depends on E1 summary for Phase gate thresholds:
    outputs/reports/modal_oracle_summary.json

Run:
    python notebooks/scripts/chFusion_modal_quality_gating.py
    python notebooks/scripts/chFusion_modal_quality_gating.py --domain hkh
    python notebooks/scripts/chFusion_modal_quality_gating.py --domain cs
    python notebooks/scripts/chFusion_modal_quality_gating.py --plot-only
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
    B3VariantConfig,
    DRAFT_ABLATION_SPECS,
    estimate_b3_window,
    validate_b3_variant_against_hkh,
)
from ble_analysis.ble_hkh_validation import load_hkh_gt_signals
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import (
    ChFusionConfig,
    _next_pow2,
    _seg_bpm_stats,
    load_multichannel_for_scenario,
)
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.voting_fusion import VotingConfig

_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]
CACHE_DIR = str(project_root / "outputs" / "cache")

HKH_SCENARIO_IDS = [
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
CS_SCENARIO_IDS = ["cs_091339", "cs_095806", "cs_102621"]

BASELINE_KEYS = (
    "draft_s_full",
    "draft_s_channel",
    "draft_ms_remote",
    "draft_ms_local",
    "draft_ms_phase",
)
E3_KEYS = (
    "e3a_eta_weighted",
    "e3b_eta_rho_weighted",
    "e3c_eta_coherence_weighted",
    "e3d_eta_rho_conf_weighted",
)

SHORT_LABEL = {
    "draft_s_full": "Equal (BreatheCS)",
    "draft_s_channel": "Channel-only",
    "draft_ms_remote": "Remote only",
    "draft_ms_local": "Local only",
    "draft_ms_phase": "Phase only",
    "e3a_eta_weighted": "η-weighted",
    "e3b_eta_rho_weighted": "η·ρ-weighted",
    "e3c_eta_coherence_weighted": "η·γ-weighted",
    "e3d_eta_rho_conf_weighted": "η·ρ·conf",
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
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png


def _lookup_variant(key: str) -> Tuple[str, B3VariantConfig]:
    for label, k, cfg in DRAFT_ABLATION_SPECS:
        if k == key:
            return label, cfg
    raise KeyError(key)


def build_e4_specs(q_phase_p: Dict[str, float]) -> List[Tuple[str, str, B3VariantConfig]]:
    """Build E4 variants from HKH q_phase percentiles + soft alphas."""
    base_label, base_cfg = _lookup_variant("e3b_eta_rho_weighted")
    specs: List[Tuple[str, str, B3VariantConfig]] = []

    for p_name in ("p10", "p25", "p50"):
        thr = float(q_phase_p[p_name])
        # Hard gate
        key_h = f"e4a_hard_{p_name}"
        SHORT_LABEL[key_h] = f"Hard gate {p_name}"
        specs.append(
            (
                f"Spec · η·ρ + Phase hard ({p_name})",
                key_h,
                replace(base_cfg, phase_gate_threshold=thr, phase_gate_alpha=0.0),
            )
        )
        # Soft gate alpha=0.3
        key_s = f"e4b_soft_{p_name}"
        SHORT_LABEL[key_s] = f"Soft×0.3 {p_name}"
        specs.append(
            (
                f"Spec · η·ρ + Phase soft0.3 ({p_name})",
                key_s,
                replace(base_cfg, phase_gate_threshold=thr, phase_gate_alpha=0.3),
            )
        )

    # E4c: primary soft p25 (plan default)
    thr25 = float(q_phase_p["p25"])
    key_c = "e4c_quality_soft"
    SHORT_LABEL[key_c] = "η·ρ + soft p25"
    specs.append(
        (
            "Spec · η·ρ + Phase soft0.3 (p25)",
            key_c,
            replace(base_cfg, phase_gate_threshold=thr25, phase_gate_alpha=0.3),
        )
    )
    return specs


def load_phase_thresholds() -> Dict[str, float]:
    path = REPORTS_DIR / "modal_oracle_summary.json"
    if not path.exists():
        # Fallback defaults; E1 should run first
        return {"p10": 0.0, "p25": 0.0, "p50": 0.0}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("hkh", {}).get("q_phase_percentiles", {"p10": 0.0, "p25": 0.0, "p50": 0.0})


def all_method_specs(e4_specs: Sequence[Tuple[str, str, B3VariantConfig]]) -> List[Tuple[str, str, B3VariantConfig]]:
    specs: List[Tuple[str, str, B3VariantConfig]] = []
    wanted = set(BASELINE_KEYS) | set(E3_KEYS)
    for label, key, cfg in DRAFT_ABLATION_SPECS:
        if key in wanted:
            specs.append((label, key, cfg))
    specs.extend(list(e4_specs))
    return specs


def run_hkh_scenario(
    scenario_id: str,
    method_specs: Sequence[Tuple[str, str, B3VariantConfig]],
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

    mp = BreathMetricParams()
    cfg = ChFusionConfig(
        breath_freq_low=mp.breath_freq_low,
        breath_freq_high=mp.breath_freq_high,
        window_length_sec=mp.window_length_sec,
        step_length_sec=mp.step_length_sec,
    )
    multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=FilterParams(),
        cache_dir=CACHE_DIR,
        verbose=verbose,
    )

    key_set = set(only_keys) if only_keys else None
    methods: Dict[str, dict] = {}
    for label, key, vcfg in method_specs:
        if key_set is not None and key not in key_set:
            continue
        if verbose:
            print(f"  running {key}")
        row = validate_b3_variant_against_hkh(
            multichannel_by_var,
            "main",
            hkh_bp,
            hkh_t,
            cs_t,
            variant_key=key,
            variant=vcfg,
            config=cfg,
            metric_params=mp,
            fs_hkh_override=fs_hkh,
            verbose=False,
        )
        if row is None:
            continue
        methods[key] = {
            "label": label,
            "method_key": key,
            "bpm_mean_abs_err": row["summary"]["bpm_mean_abs_err"],
            "bpm_std_abs_err": row["summary"]["bpm_std_abs_err"],
            "n_valid_bpm": row["summary"]["n_valid_bpm"],
        }

    out = REPORTS_DIR / f"modal_quality_gating_hkh_{scenario_id}.json"
    existing: Dict[str, dict] = {}
    if out.exists() and key_set is not None:
        existing = json.loads(out.read_text(encoding="utf-8")).get("methods", {})
    existing.update(methods)
    payload = {"scenario_id": scenario_id, "methods": existing}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return payload


def validate_b3_variant_against_cs(
    multichannel_by_var: Dict[str, Dict[str, Optional[dict]]],
    *,
    variant_key: str,
    variant: B3VariantConfig,
    config: ChFusionConfig,
    metric_params: BreathMetricParams,
) -> dict:
    """CS metal-plate: relative BPM err% over breath segments."""
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")
    phase_segs = multichannel_by_var.get("phases", {})
    per_seg: Dict[str, dict] = {}
    all_bpms: List[float] = []
    all_gts: List[float] = []

    for seg_name, ref_seg in phase_segs.items():
        if ref_seg is None:
            continue
        meta = ref_seg.get("metadata", {})
        if meta.get("type") == "apnea":
            continue
        bpm_gt = meta.get("bpm_gt")
        if bpm_gt is None or not np.isfinite(float(bpm_gt)) or float(bpm_gt) <= 0:
            continue
        bpm_gt = float(bpm_gt)

        fs = meta["sampling_rate"]
        ch_map = ref_seg["channels"]
        ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
        seg_var = ref_seg.get("variable", "phases")
        ref_len = max(len(ch_map[c][seg_var]["bandpass_filtered"]) for c in ch_list)
        win_len = int(round(metric_params.window_length_sec * fs))
        step_len = int(round(metric_params.step_length_sec * fs))
        if ref_len < win_len:
            continue
        starts = _sliding_window_indices(ref_len, win_len, step_len)

        nfft = config.nfft or _next_pow2(4 * win_len)
        freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)
        band_mask = (freqs >= config.breath_freq_low) & (freqs <= config.breath_freq_high)
        band_freqs = freqs[band_mask]
        hann = np.hanning(win_len)

        bpms: List[float] = []
        for st in starts:
            end = st + win_len
            out = estimate_b3_window(
                multichannel_by_var,
                seg_name,
                ch_list,
                st,
                end,
                fs,
                config,
                variant=variant,
                vcfg=vcfg,
                nfft=nfft,
                band_freqs=band_freqs,
                band_mask=band_mask,
                hann=hann,
            )
            bpms.append(float(out["bpm"]))

        bpm_arr = np.asarray(bpms, dtype=float)
        stats = _seg_bpm_stats(bpm_arr, bpm_gt, len(starts))
        per_seg[seg_name] = stats
        for b in bpm_arr:
            if np.isfinite(b):
                all_bpms.append(float(b))
                all_gts.append(bpm_gt)

    if all_bpms:
        bp = np.asarray(all_bpms, dtype=float)
        gt = np.asarray(all_gts, dtype=float)
        rel = np.abs(bp - gt) / gt * 100.0
        overall = {
            "mean_rel_err_pct": float(np.mean(rel)),
            "std_rel_err_pct": float(np.std(rel)),
            "n_valid": int(len(rel)),
        }
    else:
        overall = {
            "mean_rel_err_pct": float("nan"),
            "std_rel_err_pct": float("nan"),
            "n_valid": 0,
        }
    return {
        "method_key": variant_key,
        "segments": per_seg,
        "summary": {
            "bpm_mean_rel_err_pct": float(overall["mean_rel_err_pct"]),
            "bpm_std_rel_err_pct": float(overall["std_rel_err_pct"]),
            "n_valid_bpm": int(overall["n_valid"]),
        },
    }


def run_cs_scenario(
    scenario_id: str,
    method_specs: Sequence[Tuple[str, str, B3VariantConfig]],
    *,
    only_keys: Optional[Sequence[str]] = None,
    verbose: bool = True,
) -> dict:
    scenario = load_scenario(scenario_id, project_root=project_root)
    if verbose:
        print_scenario_summary(scenario)

    mp = BreathMetricParams()
    cfg = ChFusionConfig(
        breath_freq_low=mp.breath_freq_low,
        breath_freq_high=mp.breath_freq_high,
        window_length_sec=mp.window_length_sec,
        step_length_sec=mp.step_length_sec,
    )
    multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=FilterParams(),
        cache_dir=CACHE_DIR,
        verbose=verbose,
    )

    key_set = set(only_keys) if only_keys else None
    methods: Dict[str, dict] = {}
    for label, key, vcfg in method_specs:
        if key_set is not None and key not in key_set:
            continue
        if verbose:
            print(f"  running {key}")
        row = validate_b3_variant_against_cs(
            multichannel_by_var,
            variant_key=key,
            variant=vcfg,
            config=cfg,
            metric_params=mp,
        )
        methods[key] = {
            "label": label,
            "method_key": key,
            "bpm_mean_rel_err_pct": row["summary"]["bpm_mean_rel_err_pct"],
            "bpm_std_rel_err_pct": row["summary"]["bpm_std_rel_err_pct"],
            "n_valid_bpm": row["summary"]["n_valid_bpm"],
        }

    out = REPORTS_DIR / f"modal_quality_gating_cs_{scenario_id}.json"
    existing: Dict[str, dict] = {}
    if out.exists() and key_set is not None:
        existing = json.loads(out.read_text(encoding="utf-8")).get("methods", {})
    existing.update(methods)
    payload = {"scenario_id": scenario_id, "methods": existing}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return payload


def aggregate_hkh(scenario_ids: Sequence[str], keys: Optional[Iterable[str]] = None) -> dict:
    wanted = set(keys) if keys is not None else None
    agg: Dict[str, List[float]] = defaultdict(list)
    labels: Dict[str, str] = {}
    for sid in scenario_ids:
        path = REPORTS_DIR / f"modal_quality_gating_hkh_{sid}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for k, row in payload.get("methods", {}).items():
            if wanted is not None and k not in wanted:
                continue
            v = row.get("bpm_mean_abs_err")
            if v is None or not math.isfinite(float(v)):
                continue
            agg[k].append(float(v))
            labels[k] = row.get("label", SHORT_LABEL.get(k, k))
    methods = {}
    for k, vals in agg.items():
        methods[k] = {
            "label": labels.get(k, SHORT_LABEL.get(k, k)),
            "n_scenarios": len(vals),
            "bpm_mean_abs_err": float(np.mean(vals)),
            "bpm_std_across_scenarios": float(np.std(vals)),
            "per_scenario": vals,
        }
    ranked = sorted(methods.items(), key=lambda kv: kv[1]["bpm_mean_abs_err"])
    return {"domain": "hkh", "metric": "bpm_mean_abs_err", "methods": methods, "ranking": [k for k, _ in ranked]}


def aggregate_cs(scenario_ids: Sequence[str], keys: Optional[Iterable[str]] = None) -> dict:
    wanted = set(keys) if keys is not None else None
    agg: Dict[str, List[float]] = defaultdict(list)
    labels: Dict[str, str] = {}
    for sid in scenario_ids:
        path = REPORTS_DIR / f"modal_quality_gating_cs_{sid}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for k, row in payload.get("methods", {}).items():
            if wanted is not None and k not in wanted:
                continue
            v = row.get("bpm_mean_rel_err_pct")
            if v is None or not math.isfinite(float(v)):
                continue
            agg[k].append(float(v))
            labels[k] = row.get("label", SHORT_LABEL.get(k, k))
    methods = {}
    for k, vals in agg.items():
        methods[k] = {
            "label": labels.get(k, SHORT_LABEL.get(k, k)),
            "n_scenarios": len(vals),
            "bpm_mean_rel_err_pct": float(np.mean(vals)),
            "bpm_std_across_scenarios": float(np.std(vals)),
            "per_scenario": vals,
        }
    ranked = sorted(methods.items(), key=lambda kv: kv[1]["bpm_mean_rel_err_pct"])
    return {
        "domain": "cs",
        "metric": "bpm_mean_rel_err_pct",
        "methods": methods,
        "ranking": [k for k, _ in ranked],
    }


def plot_leaderboards(hkh_summary: dict, cs_summary: dict) -> List[Path]:
    paths: List[Path] = []

    def _plot_one(summary: dict, stem: str, xlabel: str, highlight_keys: Sequence[str]) -> Path:
        methods = summary.get("methods", {})
        ranking = summary.get("ranking", list(methods.keys()))
        keys = list(reversed(ranking))
        vals = []
        for k in keys:
            m = methods[k]
            vals.append(m.get("bpm_mean_abs_err", m.get("bpm_mean_rel_err_pct", float("nan"))))
        labels = [SHORT_LABEL.get(k, methods[k].get("label", k)) for k in keys]
        fig, ax = plt.subplots(figsize=(9, max(4.5, 0.35 * len(keys) + 1.5)))
        y = np.arange(len(keys))
        for i, (k, v) in enumerate(zip(keys, vals)):
            color = "#E63946" if k in highlight_keys else "#4C78A8"
            ax.barh(i, v, color=color, alpha=0.9, height=0.7)
            if math.isfinite(v):
                ax.text(v, i, f" {v:.3f}", va="center", fontsize=8)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel(xlabel)
        ax.set_title(stem.replace("_", " "))
        ax.grid(True, axis="x", alpha=0.3)
        fig.tight_layout()
        return _save_figure(fig, stem)

    if hkh_summary.get("methods"):
        paths.append(
            _plot_one(
                hkh_summary,
                "modal_quality_gating_hkh_leaderboard",
                "12-scenario mean abs BPM err (breaths/min)",
                highlight_keys=("draft_s_full", "draft_s_channel", "e3b_eta_rho_weighted", "e4c_quality_soft"),
            )
        )
    if cs_summary.get("methods"):
        paths.append(
            _plot_one(
                cs_summary,
                "modal_quality_gating_cs_leaderboard",
                "3-scenario mean rel BPM err (%)",
                highlight_keys=("draft_s_full", "draft_s_channel", "e3b_eta_rho_weighted", "e4c_quality_soft"),
            )
        )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Modal quality gating E3/E4")
    parser.add_argument("--domain", choices=["all", "hkh", "cs"], default="all")
    parser.add_argument("--only-keys", type=str, default="")
    parser.add_argument("--plot-only", action="store_true")
    parser.add_argument("--skip-e4", action="store_true")
    args = parser.parse_args()

    only_keys = [k.strip() for k in args.only_keys.split(",") if k.strip()] or None

    hkh_summary_path = REPORTS_DIR / "modal_quality_gating_hkh_summary.json"
    cs_summary_path = REPORTS_DIR / "modal_quality_gating_cs_summary.json"

    if args.plot_only:
        hkh_summary = json.loads(hkh_summary_path.read_text(encoding="utf-8")) if hkh_summary_path.exists() else {}
        cs_summary = json.loads(cs_summary_path.read_text(encoding="utf-8")) if cs_summary_path.exists() else {}
        for p in plot_leaderboards(hkh_summary, cs_summary):
            print(f"Figure: {p}")
        return

    q_phase_p = load_phase_thresholds()
    print(f"Phase q percentiles (HKH): {q_phase_p}")
    e4_specs = [] if args.skip_e4 else build_e4_specs(q_phase_p)
    method_specs = all_method_specs(e4_specs)
    print(f"Methods to run: {[k for _, k, _ in method_specs]}")

    if args.domain in ("all", "hkh"):
        for sid in HKH_SCENARIO_IDS:
            print(f"\n=== HKH {sid} ===")
            run_hkh_scenario(sid, method_specs, only_keys=only_keys, verbose=True)
        hkh_summary = aggregate_hkh(HKH_SCENARIO_IDS)
        hkh_summary["phase_gate_thresholds"] = q_phase_p
        hkh_summary_path.write_text(
            json.dumps(hkh_summary, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        print(f"Saved {hkh_summary_path}")
        for k in hkh_summary.get("ranking", []):
            m = hkh_summary["methods"][k]
            print(f"  {k}: {m['bpm_mean_abs_err']:.3f}")

    if args.domain in ("all", "cs"):
        for sid in CS_SCENARIO_IDS:
            print(f"\n=== CS {sid} ===")
            run_cs_scenario(sid, method_specs, only_keys=only_keys, verbose=True)
        cs_summary = aggregate_cs(CS_SCENARIO_IDS)
        cs_summary["phase_gate_thresholds"] = q_phase_p
        cs_summary_path.write_text(
            json.dumps(cs_summary, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        print(f"Saved {cs_summary_path}")
        for k in cs_summary.get("ranking", []):
            m = cs_summary["methods"][k]
            print(f"  {k}: {m['bpm_mean_rel_err_pct']:.3f}")

    hkh_summary = json.loads(hkh_summary_path.read_text(encoding="utf-8")) if hkh_summary_path.exists() else {}
    cs_summary = json.loads(cs_summary_path.read_text(encoding="utf-8")) if cs_summary_path.exists() else {}
    for p in plot_leaderboards(hkh_summary, cs_summary):
        print(f"Figure: {p}")


if __name__ == "__main__":
    main()
