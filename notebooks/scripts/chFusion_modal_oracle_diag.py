"""E1/E2: Per-window modal oracle + quality-metric selection accuracy.

Plan: docs/plans/modal_quality_gating_plan.md

Run:
    python notebooks/scripts/chFusion_modal_oracle_diag.py
    python notebooks/scripts/chFusion_modal_oracle_diag.py --domain hkh
    python notebooks/scripts/chFusion_modal_oracle_diag.py --domain cs
    python notebooks/scripts/chFusion_modal_oracle_diag.py --plot-only
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.b3_pipeline import B3VariantConfig, estimate_b3_window
from ble_analysis.ble_hkh_validation import (
    _ble_window_time_range,
    _hkh_window_bandpass,
    _resolve_hkh_fs,
    load_hkh_gt_signals,
)
from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import ChFusionConfig, _next_pow2, _seg_bpm_stats, load_multichannel_for_scenario
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.voting_fusion import VotingConfig
from ble_analysis.wifi_mrc import estimate_bpm_from_waveform

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
MODALS = ("remote", "local", "phase")

ORACLE_VARIANT = B3VariantConfig(
    use_voting=True,
    use_two_level_hilbert=False,
    modal_combine="fuse",
    bpm_source="spectral",
    modal_weight_mode="equal",
)

METRIC_FUNCS = {
    "eta": lambda r, l, p: {"remote": r["eta"], "local": l["eta"], "phase": p["eta"]},
    "rho": lambda r, l, p: {"remote": r["rho"], "local": l["rho"], "phase": p["rho"]},
    "eta_rho": lambda r, l, p: {
        "remote": r["eta"] * max(r["rho"], 0.0),
        "local": l["eta"] * max(l["rho"], 0.0),
        "phase": p["eta"] * max(p["rho"], 0.0),
    },
    "conf": lambda r, l, p: {"remote": r["conf"], "local": l["conf"], "phase": p["conf"]},
    "eta_1plus_rho": lambda r, l, p: {
        "remote": r["eta"] * (1.0 + r["rho"]),
        "local": l["eta"] * (1.0 + l["rho"]),
        "phase": p["eta"] * (1.0 + p["rho"]),
    },
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


def _modal_pack(res: dict) -> dict:
    return {
        "bpm": float(res.get("voted_bpm", float("nan"))),
        "eta": float(res.get("mean_eta", 0.0)),
        "rho": float(res.get("mean_rho", 0.0)),
        "conf": float(res.get("confidence", 0.0)),
    }


def _collect_windows_hkh(scenario_id: str, *, verbose: bool = True) -> List[dict]:
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

    ref_seg = multichannel_by_var["phases"]["main"]
    fs = ref_seg["metadata"]["sampling_rate"]
    ch_map = ref_seg["channels"]
    ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
    seg_var = ref_seg.get("variable", "phases")
    ref_len = max(len(ch_map[c][seg_var]["bandpass_filtered"]) for c in ch_list)
    win_len = int(round(mp.window_length_sec * fs))
    step_len = int(round(mp.step_length_sec * fs))
    starts = _sliding_window_indices(ref_len, win_len, step_len)
    fs_hkh = _resolve_hkh_fs(hkh_bp, hkh_t, fs_hkh)

    nfft = cfg.nfft or _next_pow2(4 * win_len)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)
    band_mask = (freqs >= cfg.breath_freq_low) & (freqs <= cfg.breath_freq_high)
    band_freqs = freqs[band_mask]
    hann = np.hanning(win_len)
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")

    records: List[dict] = []
    for wi, st in enumerate(starts):
        end = st + win_len
        out = estimate_b3_window(
            multichannel_by_var,
            "main",
            ch_list,
            st,
            end,
            fs,
            cfg,
            variant=ORACLE_VARIANT,
            vcfg=vcfg,
            nfft=nfft,
            band_freqs=band_freqs,
            band_mask=band_mask,
            hann=hann,
        )
        modal = out.get("diagnostics", {}).get("modal_results", {})
        packs = {m: _modal_pack(modal.get(m, {})) for m in MODALS}

        t0, t1 = _ble_window_time_range(cs_t, st, end, fs, win_len)
        hkh_win = _hkh_window_bandpass(hkh_bp, hkh_t, t0, t1 + 1)
        if len(hkh_win) < 4:
            continue
        bpm_gt, _, _, _ = estimate_bpm_from_waveform(hkh_win, fs_hkh, cfg=cfg)
        if not np.isfinite(bpm_gt) or bpm_gt <= 0:
            continue

        errs = {m: abs(packs[m]["bpm"] - bpm_gt) if np.isfinite(packs[m]["bpm"]) else float("inf") for m in MODALS}
        if not any(np.isfinite(list(errs.values()))):
            continue
        best = min(MODALS, key=lambda m: errs[m])
        sorted_modals = sorted(MODALS, key=lambda m: errs[m])
        margin = errs[sorted_modals[1]] - errs[sorted_modals[0]] if len(sorted_modals) > 1 else float("nan")

        records.append(
            {
                "domain": "hkh",
                "scenario_id": scenario_id,
                "segment": "main",
                "window_idx": wi,
                "bpm_gt": float(bpm_gt),
                "bpm_remote": packs["remote"]["bpm"],
                "bpm_local": packs["local"]["bpm"],
                "bpm_phase": packs["phase"]["bpm"],
                "eta_remote": packs["remote"]["eta"],
                "eta_local": packs["local"]["eta"],
                "eta_phase": packs["phase"]["eta"],
                "rho_remote": packs["remote"]["rho"],
                "rho_local": packs["local"]["rho"],
                "rho_phase": packs["phase"]["rho"],
                "conf_remote": packs["remote"]["conf"],
                "conf_local": packs["local"]["conf"],
                "conf_phase": packs["phase"]["conf"],
                "err_remote": float(errs["remote"]) if np.isfinite(errs["remote"]) else float("nan"),
                "err_local": float(errs["local"]) if np.isfinite(errs["local"]) else float("nan"),
                "err_phase": float(errs["phase"]) if np.isfinite(errs["phase"]) else float("nan"),
                "best_modal": best,
                "oracle_err": float(errs[best]),
                "margin": float(margin) if np.isfinite(margin) else float("nan"),
            }
        )
    return records


def _collect_windows_cs(scenario_id: str, *, verbose: bool = True) -> List[dict]:
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

    records: List[dict] = []
    phase_segs = multichannel_by_var.get("phases", {})
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
        win_len = int(round(mp.window_length_sec * fs))
        step_len = int(round(mp.step_length_sec * fs))
        if ref_len < win_len:
            continue
        starts = _sliding_window_indices(ref_len, win_len, step_len)

        nfft = cfg.nfft or _next_pow2(4 * win_len)
        freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)
        band_mask = (freqs >= cfg.breath_freq_low) & (freqs <= cfg.breath_freq_high)
        band_freqs = freqs[band_mask]
        hann = np.hanning(win_len)
        vcfg = VotingConfig(voting_strategy="eta_rho_weighted")

        for wi, st in enumerate(starts):
            end = st + win_len
            out = estimate_b3_window(
                multichannel_by_var,
                seg_name,
                ch_list,
                st,
                end,
                fs,
                cfg,
                variant=ORACLE_VARIANT,
                vcfg=vcfg,
                nfft=nfft,
                band_freqs=band_freqs,
                band_mask=band_mask,
                hann=hann,
            )
            modal = out.get("diagnostics", {}).get("modal_results", {})
            packs = {m: _modal_pack(modal.get(m, {})) for m in MODALS}
            errs = {
                m: abs(packs[m]["bpm"] - bpm_gt) if np.isfinite(packs[m]["bpm"]) else float("inf")
                for m in MODALS
            }
            if not any(np.isfinite(list(errs.values()))):
                continue
            best = min(MODALS, key=lambda m: errs[m])
            sorted_modals = sorted(MODALS, key=lambda m: errs[m])
            margin = errs[sorted_modals[1]] - errs[sorted_modals[0]]

            records.append(
                {
                    "domain": "cs",
                    "scenario_id": scenario_id,
                    "segment": seg_name,
                    "window_idx": wi,
                    "bpm_gt": bpm_gt,
                    "bpm_remote": packs["remote"]["bpm"],
                    "bpm_local": packs["local"]["bpm"],
                    "bpm_phase": packs["phase"]["bpm"],
                    "eta_remote": packs["remote"]["eta"],
                    "eta_local": packs["local"]["eta"],
                    "eta_phase": packs["phase"]["eta"],
                    "rho_remote": packs["remote"]["rho"],
                    "rho_local": packs["local"]["rho"],
                    "rho_phase": packs["phase"]["rho"],
                    "conf_remote": packs["remote"]["conf"],
                    "conf_local": packs["local"]["conf"],
                    "conf_phase": packs["phase"]["conf"],
                    "err_remote": float(errs["remote"]) if np.isfinite(errs["remote"]) else float("nan"),
                    "err_local": float(errs["local"]) if np.isfinite(errs["local"]) else float("nan"),
                    "err_phase": float(errs["phase"]) if np.isfinite(errs["phase"]) else float("nan"),
                    "best_modal": best,
                    "oracle_err": float(errs[best]),
                    "margin": float(margin) if np.isfinite(margin) else float("nan"),
                }
            )
    return records


def _records_to_structured(records: Sequence[dict]) -> np.ndarray:
    dtype = [
        ("domain", "U8"),
        ("scenario_id", "U64"),
        ("segment", "U32"),
        ("window_idx", "i4"),
        ("bpm_gt", "f8"),
        ("bpm_remote", "f8"),
        ("bpm_local", "f8"),
        ("bpm_phase", "f8"),
        ("eta_remote", "f8"),
        ("eta_local", "f8"),
        ("eta_phase", "f8"),
        ("rho_remote", "f8"),
        ("rho_local", "f8"),
        ("rho_phase", "f8"),
        ("conf_remote", "f8"),
        ("conf_local", "f8"),
        ("conf_phase", "f8"),
        ("err_remote", "f8"),
        ("err_local", "f8"),
        ("err_phase", "f8"),
        ("best_modal", "U16"),
        ("oracle_err", "f8"),
        ("margin", "f8"),
    ]
    arr = np.zeros(len(records), dtype=dtype)
    for i, r in enumerate(records):
        for name, _ in dtype:
            arr[i][name] = r[name]
    return arr


def _pack_from_row(row) -> Tuple[dict, dict, dict]:
    def one(prefix: str) -> dict:
        return {
            "eta": float(row[f"eta_{prefix}"]),
            "rho": float(row[f"rho_{prefix}"]),
            "conf": float(row[f"conf_{prefix}"]),
            "bpm": float(row[f"bpm_{prefix}"]),
            "err": float(row[f"err_{prefix}"]),
        }

    return one("remote"), one("local"), one("phase")


def evaluate_selection_metrics(arr: np.ndarray, domain: str) -> dict:
    sub = arr[arr["domain"] == domain] if len(arr) else arr
    out: Dict[str, dict] = {}
    if len(sub) == 0:
        return out
    for metric_name, fn in METRIC_FUNCS.items():
        hits = 0
        selected_errs: List[float] = []
        oracle_errs: List[float] = []
        for row in sub:
            r, l, p = _pack_from_row(row)
            scores = fn(r, l, p)
            best_pred = max(scores.keys(), key=lambda k: scores[k])
            if best_pred == str(row["best_modal"]):
                hits += 1
            selected_errs.append(float(row[f"err_{best_pred}"]))
            oracle_errs.append(float(row["oracle_err"]))
        n = len(sub)
        out[metric_name] = {
            "n": int(n),
            "top1_hit_rate": float(hits / n) if n else float("nan"),
            "selected_mean_abs_err": float(np.nanmean(selected_errs)),
            "oracle_mean_abs_err": float(np.nanmean(oracle_errs)),
        }
    return out


def summarize_oracle(arr: np.ndarray) -> dict:
    summary: Dict[str, Any] = {}
    for domain in ("hkh", "cs"):
        sub = arr[arr["domain"] == domain]
        if len(sub) == 0:
            continue
        counts = Counter(str(x) for x in sub["best_modal"])
        total = len(sub)
        by_scenario: Dict[str, dict] = {}
        for sid in sorted(set(str(x) for x in sub["scenario_id"])):
            ssub = sub[sub["scenario_id"] == sid]
            sc = Counter(str(x) for x in ssub["best_modal"])
            by_scenario[sid] = {
                "n": int(len(ssub)),
                "counts": {m: int(sc.get(m, 0)) for m in MODALS},
                "pct": {m: float(sc.get(m, 0) / len(ssub) * 100) for m in MODALS},
                "oracle_mean_abs_err": float(np.nanmean(ssub["oracle_err"])),
                "remote_mean_abs_err": float(np.nanmean(ssub["err_remote"])),
                "local_mean_abs_err": float(np.nanmean(ssub["err_local"])),
                "phase_mean_abs_err": float(np.nanmean(ssub["err_phase"])),
            }

        phase_best = sub[sub["best_modal"] == "phase"]
        q_phase = np.maximum(sub["eta_phase"], 0.0) * np.maximum(sub["rho_phase"], 0.0)
        summary[domain] = {
            "n_windows": int(total),
            "best_counts": {m: int(counts.get(m, 0)) for m in MODALS},
            "best_pct": {m: float(counts.get(m, 0) / total * 100) for m in MODALS},
            "oracle_mean_abs_err": float(np.nanmean(sub["oracle_err"])),
            "remote_mean_abs_err": float(np.nanmean(sub["err_remote"])),
            "local_mean_abs_err": float(np.nanmean(sub["err_local"])),
            "phase_mean_abs_err": float(np.nanmean(sub["err_phase"])),
            "phase_best_n": int(len(phase_best)),
            "phase_best_eta_mean": float(np.nanmean(phase_best["eta_phase"])) if len(phase_best) else float("nan"),
            "phase_best_rho_mean": float(np.nanmean(phase_best["rho_phase"])) if len(phase_best) else float("nan"),
            "q_phase_percentiles": {
                "p10": float(np.nanpercentile(q_phase, 10)),
                "p25": float(np.nanpercentile(q_phase, 25)),
                "p50": float(np.nanpercentile(q_phase, 50)),
                "p75": float(np.nanpercentile(q_phase, 75)),
            },
            "by_scenario": by_scenario,
            "selection_metrics": evaluate_selection_metrics(sub, domain),
        }
    return summary


def plot_oracle_figures(arr: np.ndarray, summary: dict) -> List[Path]:
    paths: List[Path] = []

    # Optimal modal pie / bar by domain
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, domain, title in zip(axes, ("hkh", "cs"), ("HKH 12", "CS metal plate 3")):
        if domain not in summary:
            ax.set_visible(False)
            continue
        pct = summary[domain]["best_pct"]
        vals = [pct[m] for m in MODALS]
        colors = ["#4C78A8", "#F58518", "#54A24B"]
        ax.bar(MODALS, vals, color=colors, edgecolor="black", linewidth=0.6)
        for i, v in enumerate(vals):
            ax.text(i, v + 1.0, f"{v:.1f}%", ha="center", fontsize=9)
        ax.set_ylim(0, max(vals) * 1.2 if vals else 1)
        ax.set_ylabel("Windows where modal is best (%)")
        ax.set_title(f"{title}: oracle best-modal share")
        ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    paths.append(_save_figure(fig, "modal_oracle_optimal_pie"))

    # Leaderboard oracle vs single modal
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, domain, ylabel in zip(
        axes,
        ("hkh", "cs"),
        ("Mean abs BPM err (breaths/min)", "Mean abs BPM err (breaths/min)"),
    ):
        if domain not in summary:
            ax.set_visible(False)
            continue
        s = summary[domain]
        keys = ["oracle", "remote", "local", "phase"]
        vals = [
            s["oracle_mean_abs_err"],
            s["remote_mean_abs_err"],
            s["local_mean_abs_err"],
            s["phase_mean_abs_err"],
        ]
        ax.barh(keys, vals, color=["#E63946", "#4C78A8", "#F58518", "#54A24B"])
        ax.set_xlabel(ylabel)
        ax.set_title(f"{domain.upper()}: oracle vs single-modal")
        ax.grid(True, axis="x", alpha=0.3)
        for i, v in enumerate(vals):
            ax.text(v, i, f" {v:.3f}", va="center", fontsize=8)
    fig.tight_layout()
    paths.append(_save_figure(fig, "modal_oracle_leaderboard"))

    # Phase-best eta distribution
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, domain in zip(axes, ("hkh", "cs")):
        sub = arr[(arr["domain"] == domain) & (arr["best_modal"] == "phase")]
        all_phase = arr[arr["domain"] == domain]
        if len(all_phase) == 0:
            ax.set_visible(False)
            continue
        ax.hist(all_phase["eta_phase"], bins=30, alpha=0.45, label="all windows", color="#999999")
        if len(sub):
            ax.hist(sub["eta_phase"], bins=30, alpha=0.75, label="phase-best", color="#54A24B")
        ax.set_xlabel(r"$\eta_{phase}$")
        ax.set_ylabel("Count")
        ax.set_title(f"{domain.upper()}: Phase η when Phase is oracle-best")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    paths.append(_save_figure(fig, "modal_oracle_phase_eta_dist"))

    # E2 metric accuracy
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    metric_order = list(METRIC_FUNCS.keys())
    for ax, domain in zip(axes, ("hkh", "cs")):
        if domain not in summary:
            ax.set_visible(False)
            continue
        mets = summary[domain]["selection_metrics"]
        hit = [mets[m]["top1_hit_rate"] * 100 for m in metric_order]
        ax.bar(metric_order, hit, color="#4C78A8", edgecolor="black", linewidth=0.5)
        ax.set_ylabel("Top-1 hit rate (%)")
        ax.set_title(f"{domain.upper()}: modal selection metric accuracy")
        ax.set_ylim(0, 100)
        ax.tick_params(axis="x", rotation=30)
        ax.grid(True, axis="y", alpha=0.3)
        for i, v in enumerate(hit):
            ax.text(i, v + 1.5, f"{v:.1f}", ha="center", fontsize=8)
    fig.tight_layout()
    paths.append(_save_figure(fig, "modal_selection_metric_accuracy"))

    # Per-window quality scatter (η vs ρ, colored by best modal)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    color_map = {"remote": "#4C78A8", "local": "#F58518", "phase": "#54A24B"}
    for ax, domain in zip(axes, ("hkh", "cs")):
        sub = arr[arr["domain"] == domain]
        if len(sub) == 0:
            ax.set_visible(False)
            continue
        # Use the best modal's (η, ρ) point
        for m in MODALS:
            mask = sub["best_modal"] == m
            if not np.any(mask):
                continue
            ax.scatter(
                sub[f"eta_{m}"][mask],
                sub[f"rho_{m}"][mask],
                s=8,
                alpha=0.45,
                c=color_map[m],
                label=m,
            )
        ax.set_xlabel(r"$\eta$ of oracle-best modal")
        ax.set_ylabel(r"$\rho$ of oracle-best modal")
        ax.set_title(f"{domain.upper()}: quality of oracle-best modal")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    paths.append(_save_figure(fig, "modal_quality_per_window_scatter"))

    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Modal oracle diagnosis E1/E2")
    parser.add_argument("--domain", choices=["all", "hkh", "cs"], default="all")
    parser.add_argument("--plot-only", action="store_true")
    parser.add_argument("--verbose", action="store_true", default=True)
    args = parser.parse_args()

    npy_path = REPORTS_DIR / "modal_oracle_per_window.npy"
    summary_path = REPORTS_DIR / "modal_oracle_summary.json"

    if args.plot_only:
        if not npy_path.exists():
            raise FileNotFoundError(npy_path)
        arr = np.load(npy_path, allow_pickle=False)
        summary = summarize_oracle(arr)
        paths = plot_oracle_figures(arr, summary)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        print(f"Saved {summary_path}")
        for p in paths:
            print(f"Figure: {p}")
        return

    records: List[dict] = []
    if args.domain in ("all", "hkh"):
        for sid in HKH_SCENARIO_IDS:
            print(f"\n=== HKH {sid} ===")
            records.extend(_collect_windows_hkh(sid, verbose=args.verbose))
    if args.domain in ("all", "cs"):
        for sid in CS_SCENARIO_IDS:
            print(f"\n=== CS {sid} ===")
            records.extend(_collect_windows_cs(sid, verbose=args.verbose))

    if npy_path.exists() and args.domain != "all":
        old = np.load(npy_path, allow_pickle=False)
        keep_domain = "cs" if args.domain == "hkh" else "hkh"
        old_recs = []
        for row in old:
            if str(row["domain"]) != keep_domain:
                continue
            old_recs.append({name: row[name].item() if hasattr(row[name], "item") else row[name] for name, _ in old.dtype.descr})
        # Fix string fields
        fixed = []
        for r in old_recs:
            fixed.append({k: (v.decode() if isinstance(v, bytes) else v) for k, v in r.items()})
        # Simpler: concatenate structured arrays by filtering domain
        new_arr = _records_to_structured(records)
        old_keep = old[old["domain"] == keep_domain]
        arr = np.concatenate([old_keep, new_arr]) if len(old_keep) else new_arr
    else:
        arr = _records_to_structured(records)

    np.save(npy_path, arr)
    print(f"Saved {npy_path} ({len(arr)} windows)")

    summary = summarize_oracle(arr)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    print(f"Saved {summary_path}")
    for domain, s in summary.items():
        print(
            f"[{domain}] n={s['n_windows']} best%="
            f"R{s['best_pct']['remote']:.1f}/L{s['best_pct']['local']:.1f}/P{s['best_pct']['phase']:.1f} "
            f"oracle={s['oracle_mean_abs_err']:.3f}"
        )
        for mname, m in s["selection_metrics"].items():
            print(f"  {mname}: hit={m['top1_hit_rate']*100:.1f}% sel_err={m['selected_mean_abs_err']:.3f}")

    paths = plot_oracle_figures(arr, summary)
    for p in paths:
        print(f"Figure: {p}")


if __name__ == "__main__":
    main()
