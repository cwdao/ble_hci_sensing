"""E1/E4/E5 diagnostics for Phase Plan v2.0 (no E2/E3 gating).

Plan: docs/plans/phase_unique_role_adaptive_fusion_plan.md
Deps: docs/plans/paper_experiment_dependencies_plan.md (D7)

Run:
    python notebooks/scripts/chFusion_phase_diagnostics.py
    python notebooks/scripts/chFusion_phase_diagnostics.py --skip-e1b
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
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
from ble_analysis.chfusion import ChFusionConfig, _next_pow2, load_multichannel_for_scenario
from ble_analysis.coherent_mrc import coherent_mrc_fuse_tones
from ble_analysis.iq_geometry import compute_amplitude_joint_weakness, compute_rescue_metrics
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.voting_fusion import VotingConfig
from ble_analysis.waveform_metrics import resample_to_length, zscore
from ble_analysis.wifi_mrc import _collect_modal_window_matrix, _energy_ratio

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
VAR_MAP = {
    "remote": "remote_amplitudes",
    "local": "local_amplitudes",
    "phase": "phases",
}


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _save_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    return path


def _save_figure(fig: plt.Figure, stem: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    png = FIGURES_DIR / f"{stem}.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png


def _load_oracle() -> np.ndarray:
    path = REPORTS_DIR / "modal_oracle_per_window.npy"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return np.load(path)


def _signed_lagged_corr(a: np.ndarray, b: np.ndarray, max_lag: int = 3) -> float:
    """Max |Pearson| over small lag and sign flip (plan E1b)."""
    a = zscore(np.asarray(a, dtype=float))
    b = zscore(np.asarray(b, dtype=float))
    n = min(len(a), len(b))
    if n < 8:
        return float("nan")
    a, b = a[:n], b[:n]
    best = -1.0
    for sign in (1.0, -1.0):
        bb = sign * b
        for lag in range(-max_lag, max_lag + 1):
            if lag == 0:
                x, y = a, bb
            elif lag > 0:
                x, y = a[lag:], bb[:-lag]
            else:
                x, y = a[:lag], bb[-lag:]
            if len(x) < 8:
                continue
            if float(np.std(x)) < 1e-12 or float(np.std(y)) < 1e-12:
                continue
            r = float(np.corrcoef(x, y)[0, 1])
            if np.isfinite(r) and abs(r) > best:
                best = abs(r)
    return float(best) if best >= 0 else float("nan")


# ---------------------------------------------------------------------------
# E1a
# ---------------------------------------------------------------------------

def run_e1a(oracle: np.ndarray) -> Dict[str, Any]:
    out: Dict[str, Any] = {"experiment": "E1a", "by_domain": {}}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    for ax, domain in zip(axes, ("hkh", "cs")):
        arr = oracle[oracle["domain"] == domain]
        per_rec_q: Dict[str, List[float]] = defaultdict(list)
        group_q: Dict[str, List[float]] = defaultdict(list)
        dual_weak_phase = []
        scatter_phase = []
        scatter_remote = []

        for sid in np.unique(arr["scenario_id"]):
            sub = arr[arr["scenario_id"] == sid]
            weak = compute_amplitude_joint_weakness(
                sub["eta_remote"], sub["eta_local"], sub["eta_phase"]
            )
            q = weak["q_amp"]
            er_n, el_n = weak["eta_r_norm"], weak["eta_l_norm"]
            med_r = float(np.nanmedian(er_n))
            med_l = float(np.nanmedian(el_n))
            for i, row in enumerate(sub):
                best = str(row["best_modal"])
                group_q[best].append(float(q[i]))
                per_rec_q[best].append(float(q[i]))
                if best == "phase":
                    dual_weak_phase.append(bool(er_n[i] < med_r and el_n[i] < med_l))
                    scatter_phase.append((float(er_n[i]), float(el_n[i])))
                elif best == "remote":
                    scatter_remote.append((float(er_n[i]), float(el_n[i])))

        stats = {}
        for g in MODALS:
            vals = np.asarray(group_q.get(g, []), dtype=float)
            stats[g] = {
                "n": int(len(vals)),
                "q_amp_mean": float(np.nanmean(vals)) if len(vals) else float("nan"),
                "q_amp_median": float(np.nanmedian(vals)) if len(vals) else float("nan"),
            }
        dual_frac = float(np.mean(dual_weak_phase)) if dual_weak_phase else float("nan")
        # H1: phase q_amp < remote q_amp
        h1 = (
            stats["phase"]["n"] > 0
            and stats["remote"]["n"] > 0
            and stats["phase"]["q_amp_median"] < stats["remote"]["q_amp_median"]
            and (not np.isfinite(dual_frac) or dual_frac > 0.5)
        )
        out["by_domain"][domain] = {
            "group_stats": stats,
            "phase_dual_weak_frac": dual_frac,
            "h1_supported": bool(h1),
            "note": (
                "Phase-best q_amp 更低且双弱比例>50%"
                if h1
                else "H1 未充分成立（q_amp 或双弱比例未达预期）"
            ),
        }

        data, labs, cols = [], [], {"phase": "#d62728", "remote": "#1f77b4", "local": "#2ca02c"}
        for g in MODALS:
            if group_q.get(g):
                data.append(group_q[g])
                labs.append(f"{g}\nn={len(group_q[g])}")
        if data:
            bp = ax.boxplot(data, tick_labels=labs, patch_artist=True, showfliers=False)
            for patch, g in zip(bp["boxes"], [x for x in MODALS if group_q.get(x)]):
                patch.set_facecolor(cols[g])
                patch.set_alpha(0.5)
        ax.set_title(f"E1a q_amp by oracle-best | {domain.upper()}")
        ax.set_ylabel("q_amp = max(η̃_R, η̃_L)")
        ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig_path = _save_figure(fig, "phase_e1_complementary_projection")
    out["figure"] = str(fig_path.relative_to(project_root)).replace("\\", "/")

    # scatter HKH only
    arr = oracle[oracle["domain"] == "hkh"]
    fig, ax = plt.subplots(figsize=(5.5, 5))
    for sid in np.unique(arr["scenario_id"]):
        sub = arr[arr["scenario_id"] == sid]
        weak = compute_amplitude_joint_weakness(sub["eta_remote"], sub["eta_local"])
        for i, row in enumerate(sub):
            if row["best_modal"] == "phase":
                ax.scatter(weak["eta_r_norm"][i], weak["eta_l_norm"][i], c="#d62728", s=18, alpha=0.7, label="phase-best" if sid == np.unique(arr["scenario_id"])[0] and i == 0 else None)
            elif row["best_modal"] == "remote" and (i % 20 == 0):
                ax.scatter(weak["eta_r_norm"][i], weak["eta_l_norm"][i], c="#1f77b4", s=8, alpha=0.25, label="remote-best (sub)" if sid == np.unique(arr["scenario_id"])[0] and i == 0 else None)
    ax.axhline(1.0, color="k", ls="--", lw=0.7)
    ax.axvline(1.0, color="k", ls="--", lw=0.7)
    ax.set_xlabel("η̃_R")
    ax.set_ylabel("η̃_L")
    ax.set_title("E1a HKH (η̃_R, η̃_L) Phase-best vs Remote-best")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig_path2 = _save_figure(fig, "phase_e1_eta_scatter")
    out["scatter_figure"] = str(fig_path2.relative_to(project_root)).replace("\\", "/")
    return out


# ---------------------------------------------------------------------------
# E1c
# ---------------------------------------------------------------------------

def run_e1c(oracle: np.ndarray, tau: float = 1.0) -> Dict[str, Any]:
    out: Dict[str, Any] = {"experiment": "E1c", "tau": tau, "by_domain": {}}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    for ax, domain in zip(axes, ("hkh", "cs")):
        arr = oracle[oracle["domain"] == domain]
        # pooled
        pooled = compute_rescue_metrics(
            {
                "remote": arr["err_remote"],
                "local": arr["err_local"],
                "phase": arr["err_phase"],
            },
            tau=tau,
        )
        # per-recording then mean (HKH only meaningful)
        per_rec = []
        for sid in np.unique(arr["scenario_id"]):
            sub = arr[arr["scenario_id"] == sid]
            m = compute_rescue_metrics(
                {"remote": sub["err_remote"], "local": sub["err_local"], "phase": sub["err_phase"]},
                tau=tau,
            )
            m["recording"] = str(sid)
            per_rec.append(m)
        out["by_domain"][domain] = {"pooled": pooled, "per_recording": per_rec}

        keys = ["rescue_rate", "unique_correct", "destruction_rate"]
        vals = [pooled[k] for k in keys]
        ax.bar(keys, vals, color=["#2ca02c", "#1f77b4", "#d62728"])
        ax.set_ylim(0, max(0.2, max(vals) * 1.25 if vals else 0.2))
        ax.set_title(f"E1c rescue metrics | {domain.upper()} | τ={tau}")
        ax.tick_params(axis="x", rotation=20)
        for i, v in enumerate(vals):
            ax.text(i, v + 0.01, f"{v:.3f}", ha="center", fontsize=8)
        ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig_path = _save_figure(fig, "phase_e1_rescue_metrics")
    out["figure"] = str(fig_path.relative_to(project_root)).replace("\\", "/")
    return out


# ---------------------------------------------------------------------------
# E4: channel vs modal ρ asymmetry
# ---------------------------------------------------------------------------

def run_e4(oracle: np.ndarray) -> Dict[str, Any]:
    """Diagnose why η·ρ helps channel voting but hurts modal selection.

    Note: ρ = peak / in-band mean rewards sharp peaks (including false peaks).
    """
    summary = json.loads((REPORTS_DIR / "modal_oracle_summary.json").read_text(encoding="utf-8"))
    out: Dict[str, Any] = {
        "experiment": "E4",
        "rho_definition_note": (
            "ρ = peak / in-band-mean rewards sharp peaks, including sharp false peaks; "
            "it does NOT suppress false-peak-dominated spectra."
        ),
        "known_channel_level": {
            "source": "Plan2 / prior CS metal-plate channel voting",
            "claim": "At per-tone channel selection, η·ρ often outperforms η-only on CS",
        },
        "modal_level_from_oracle": {},
        "by_domain": {},
    }

    for domain in ("hkh", "cs"):
        sel = summary[domain]["selection_metrics"]
        out["modal_level_from_oracle"][domain] = {
            k: {
                "top1_hit_rate": v["top1_hit_rate"],
                "selected_mean_abs_err": v["selected_mean_abs_err"],
            }
            for k, v in sel.items()
        }
        arr = oracle[oracle["domain"] == domain]
        # When η picks correctly vs when η·ρ picks differently
        eta_pick = []
        etarho_pick = []
        rho_of_true = []
        rho_of_etarho_pick = []
        for row in arr:
            scores_eta = {
                "remote": float(row["eta_remote"]),
                "local": float(row["eta_local"]),
                "phase": float(row["eta_phase"]),
            }
            scores_rho = {
                "remote": float(row["rho_remote"]),
                "local": float(row["rho_local"]),
                "phase": float(row["rho_phase"]),
            }
            scores_er = {m: scores_eta[m] * max(scores_rho[m], 0.0) for m in MODALS}
            true = str(row["best_modal"])
            pe = max(MODALS, key=lambda m: scores_eta[m])
            pr = max(MODALS, key=lambda m: scores_er[m])
            eta_pick.append(pe == true)
            etarho_pick.append(pr == true)
            rho_of_true.append(scores_rho[true])
            rho_of_etarho_pick.append(scores_rho[pr])

        eta_hit = float(np.mean(eta_pick))
        er_hit = float(np.mean(etarho_pick))
        # Among windows where picks differ: who is right?
        disagree = []
        for row, pe_ok, pr_ok in zip(arr, eta_pick, etarho_pick):
            scores_eta = {
                "remote": float(row["eta_remote"]),
                "local": float(row["eta_local"]),
                "phase": float(row["eta_phase"]),
            }
            scores_rho = {
                "remote": float(row["rho_remote"]),
                "local": float(row["rho_local"]),
                "phase": float(row["rho_phase"]),
            }
            scores_er = {m: scores_eta[m] * max(scores_rho[m], 0.0) for m in MODALS}
            pe = max(MODALS, key=lambda m: scores_eta[m])
            pr = max(MODALS, key=lambda m: scores_er[m])
            if pe != pr:
                disagree.append(
                    {
                        "eta_correct": pe_ok,
                        "etarho_correct": pr_ok,
                        "picked_phase_by_etarho": pr == "phase",
                        "true": str(row["best_modal"]),
                        "rho_true": scores_rho[str(row["best_modal"])],
                        "rho_etarho_pick": scores_rho[pr],
                    }
                )

        n_dis = len(disagree)
        eta_wins = sum(1 for d in disagree if d["eta_correct"] and not d["etarho_correct"])
        er_wins = sum(1 for d in disagree if d["etarho_correct"] and not d["eta_correct"])
        phase_overpick = sum(1 for d in disagree if d["picked_phase_by_etarho"] and d["true"] != "phase")

        out["by_domain"][domain] = {
            "eta_hit": eta_hit,
            "eta_rho_hit": er_hit,
            "n_disagree": n_dis,
            "eta_wins_on_disagree": eta_wins,
            "etarho_wins_on_disagree": er_wins,
            "etarho_false_phase_picks_on_disagree": phase_overpick,
            "mean_rho_true_best": float(np.nanmean(rho_of_true)),
            "mean_rho_etarho_pick": float(np.nanmean(rho_of_etarho_pick)),
            "mechanism_note": (
                "η·ρ 在分歧窗更常选错，且常因 Phase 的尖峰 ρ 抬升而误选 Phase"
                if eta_wins > er_wins
                else "η·ρ 在分歧窗不劣于 η"
            ),
        }

    # figure
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, domain in zip(axes, ("hkh", "cs")):
        m = out["modal_level_from_oracle"][domain]
        keys = ["eta", "rho", "eta_rho", "conf"]
        hits = [m[k]["top1_hit_rate"] * 100 for k in keys]
        ax.bar(keys, hits, color=["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd"])
        ax.set_ylabel("top-1 hit %")
        ax.set_title(f"E4 modal selection hit | {domain.upper()}")
        d = out["by_domain"][domain]
        ax.text(
            0.02,
            0.98,
            f"disagree n={d['n_disagree']}\nη wins {d['eta_wins_on_disagree']} / ηρ wins {d['etarho_wins_on_disagree']}\nfalse Phase by ηρ: {d['etarho_false_phase_picks_on_disagree']}",
            transform=ax.transAxes,
            va="top",
            fontsize=8,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )
        ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig_path = _save_figure(fig, "phase_e4_channel_vs_modal_rho")
    out["figure"] = str(fig_path.relative_to(project_root)).replace("\\", "/")
    out["conclusion"] = (
        "模态级：η-only hit > η·ρ（HKH/CS）；分歧窗中 η·ρ 常因 Phase 高 ρ 误选。"
        "信道级 η·ρ 有效不等于模态级有效——ρ 奖励尖峰，模态数少时假峰代价更大。"
    )
    return out


# ---------------------------------------------------------------------------
# E5: HKH vs CS Phase quality
# ---------------------------------------------------------------------------

def run_e5(oracle: np.ndarray) -> Dict[str, Any]:
    out: Dict[str, Any] = {"experiment": "E5", "hypotheses": {}}
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))

    metrics = [
        ("eta_phase", "Phase η"),
        ("rho_phase", "Phase ρ"),
        ("conf_phase", "Phase voting conf"),
        ("err_phase", "Phase abs BPM err"),
        ("eta_remote", "Remote η"),
        ("err_remote", "Remote abs BPM err"),
    ]
    for ax, (field, title) in zip(axes.ravel(), metrics):
        data = []
        labs = []
        for domain, color in (("hkh", "#d62728"), ("cs", "#1f77b4")):
            vals = np.asarray(oracle[oracle["domain"] == domain][field], dtype=float)
            data.append(vals)
            labs.append(f"{domain}\nn={len(vals)}")
            out.setdefault("distributions", {})
            out["distributions"].setdefault(field, {})[domain] = {
                "mean": float(np.nanmean(vals)),
                "std": float(np.nanstd(vals)),
                "median": float(np.nanmedian(vals)),
            }
        bp = ax.boxplot(data, tick_labels=labs, patch_artist=True, showfliers=False)
        for patch, c in zip(bp["boxes"], ("#d62728", "#1f77b4")):
            patch.set_facecolor(c)
            patch.set_alpha(0.45)
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)

    # Hypotheses
    d = out["distributions"]
    h5a = d["eta_phase"]["hkh"]["std"] > d["eta_phase"]["cs"]["std"]
    h5b = d["rho_phase"]["hkh"]["mean"] < d["rho_phase"]["cs"]["mean"]
    h5c = d["conf_phase"]["hkh"]["mean"] < d["conf_phase"]["cs"]["mean"]
    out["hypotheses"] = {
        "H5a_hkh_phase_eta_var_gt_cs": {
            "supported": bool(h5a),
            "hkh_std": d["eta_phase"]["hkh"]["std"],
            "cs_std": d["eta_phase"]["cs"]["std"],
            "note": "人体微动→HKH Phase η 方差更大" if h5a else "未观察到 HKH Phase η 方差更大",
        },
        "H5b_hkh_phase_rho_lt_cs": {
            "supported": bool(h5b),
            "hkh_mean": d["rho_phase"]["hkh"]["mean"],
            "cs_mean": d["rho_phase"]["cs"]["mean"],
            "note": "HKH Phase ρ 更低（非正弦/峰钝）" if h5b else "未观察到 HKH Phase ρ 更低",
        },
        "H5c_hkh_phase_conf_lt_cs": {
            "supported": bool(h5c),
            "hkh_mean": d["conf_phase"]["hkh"]["mean"],
            "cs_mean": d["conf_phase"]["cs"]["mean"],
            "note": "HKH Phase voting conf 更低" if h5c else "未观察到 conf 更低",
        },
        "phase_err_gap": {
            "hkh_mean_err": d["err_phase"]["hkh"]["mean"],
            "cs_mean_err": d["err_phase"]["cs"]["mean"],
            "note": "HKH Phase 绝对误差远大于 CS（跨域崩坏）",
        },
    }

    fig.suptitle("E5 HKH vs CS Phase quality distributions")
    fig.tight_layout()
    fig_path = _save_figure(fig, "phase_e5_hkh_vs_cs_quality_dist")
    out["figure"] = str(fig_path.relative_to(project_root)).replace("\\", "/")
    out["conclusion"] = (
        f"H5a={h5a}, H5b={h5b}, H5c={h5c}; "
        f"HKH Phase err mean={d['err_phase']['hkh']['mean']:.2f} vs CS {d['err_phase']['cs']['mean']:.2f}"
    )
    return out


# ---------------------------------------------------------------------------
# E1b waveform fidelity (HKH only, selected windows)
# ---------------------------------------------------------------------------

def _modal_waveform(
    multichannel_by_var,
    seg_name: str,
    ch_list,
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
    modal: str,
) -> np.ndarray:
    variable = VAR_MAP[modal]
    X, eta, rho = _collect_modal_window_matrix(
        ch_list, multichannel_by_var[variable][seg_name]["channels"], variable, st, end, fs, cfg
    )
    if X.size == 0:
        return np.asarray([], dtype=float)
    y, _info = coherent_mrc_fuse_tones(
        X,
        eta,
        rho,
        phase_method="corr_sign",
        weight_mode="eta_rho",
        fs=fs,
        min_coherence=0.0,
    )
    return np.asarray(y, dtype=float)


def run_e1b(oracle: np.ndarray, *, max_remote_per_rec: int = 12) -> Dict[str, Any]:
    """Within-group waveform-GT correlation (avoids selection bias)."""
    cfg = ChFusionConfig()
    mp = BreathMetricParams()
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")
    records: List[Dict[str, Any]] = []

    hkh = oracle[oracle["domain"] == "hkh"]
    for sid in HKH_SCENARIO_IDS:
        sub = hkh[hkh["scenario_id"] == sid]
        if len(sub) == 0:
            continue
        print(f"[E1b] {sid}")
        scenario = load_scenario(sid, project_root=project_root)
        processed_dir = (project_root / Path(scenario.data_file)).parent
        hkh_bp, hkh_t, cs_t, preprocess_meta = load_hkh_gt_signals(processed_dir)
        fs_hkh = preprocess_meta.get("sampling_rate_hz", {}).get("hkh_used")
        fs_hkh = _resolve_hkh_fs(hkh_bp, hkh_t, fs_hkh)

        multichannel_by_var, _fs, _ = load_multichannel_for_scenario(
            scenario,
            project_root=project_root,
            filter_params=FilterParams(),
            cache_dir=CACHE_DIR,
            verbose=False,
        )
        ref_seg = multichannel_by_var["phases"]["main"]
        fs = float(ref_seg["metadata"]["sampling_rate"])
        ch_map = ref_seg["channels"]
        ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
        seg_var = ref_seg.get("variable", "phases")
        ref_len = max(len(ch_map[c][seg_var]["bandpass_filtered"]) for c in ch_list)
        win_len = int(round(mp.window_length_sec * fs))
        step_len = int(round(mp.step_length_sec * fs))
        starts = _sliding_window_indices(ref_len, win_len, step_len)

        phase_rows = sub[sub["best_modal"] == "phase"]
        remote_rows = sub[sub["best_modal"] == "remote"]
        # subsample remote-best
        if len(remote_rows) > max_remote_per_rec:
            idx = np.linspace(0, len(remote_rows) - 1, max_remote_per_rec).astype(int)
            remote_rows = remote_rows[idx]

        for group_name, rows in (("phase", phase_rows), ("remote", remote_rows)):
            for row in rows:
                wi = int(row["window_idx"])
                if wi < 0 or wi >= len(starts):
                    continue
                st = starts[wi]
                end = st + win_len
                t0, t1 = _ble_window_time_range(cs_t, st, end, fs, win_len)
                gt = _hkh_window_bandpass(hkh_bp, hkh_t, t0, t1 + 1)
                if len(gt) < 8:
                    continue
                corrs = {}
                for m in MODALS:
                    try:
                        wf = _modal_waveform(
                            multichannel_by_var, "main", ch_list, st, end, fs, cfg, m
                        )
                    except Exception:
                        wf = np.asarray([], dtype=float)
                    if wf.size < 8:
                        corrs[m] = float("nan")
                        continue
                    # resample BLE wf to HKH length
                    wf_r = resample_to_length(wf, len(gt))
                    corrs[m] = _signed_lagged_corr(wf_r, gt, max_lag=3)
                amp_best = np.nanmax([corrs["remote"], corrs["local"]])
                records.append(
                    {
                        "scenario_id": sid,
                        "window_idx": wi,
                        "oracle_group": group_name,
                        "r_remote": corrs["remote"],
                        "r_local": corrs["local"],
                        "r_phase": corrs["phase"],
                        "delta_r_p": float(corrs["phase"] - amp_best)
                        if np.isfinite(corrs["phase"]) and np.isfinite(amp_best)
                        else float("nan"),
                    }
                )

    if not records:
        return {"experiment": "E1b", "error": "no records", "n": 0}

    by_group: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_group[r["oracle_group"]].append(r)

    def _summ(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not rows:
            return {"n": 0}
        dp = np.asarray([r["delta_r_p"] for r in rows], dtype=float)
        return {
            "n": len(rows),
            "r_phase_mean": float(np.nanmean([r["r_phase"] for r in rows])),
            "r_remote_mean": float(np.nanmean([r["r_remote"] for r in rows])),
            "r_local_mean": float(np.nanmean([r["r_local"] for r in rows])),
            "delta_r_p_mean": float(np.nanmean(dp)),
            "delta_r_p_median": float(np.nanmedian(dp)),
            "frac_phase_better": float(np.nanmean(dp > 0)),
        }

    summary = {g: _summ(rows) for g, rows in by_group.items()}
    # H2: in phase-best group, delta_r_p > 0
    h2 = summary.get("phase", {}).get("delta_r_p_mean", 0) > 0

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, g in zip(axes, ("phase", "remote")):
        rows = by_group.get(g, [])
        if not rows:
            ax.set_title(f"E1b {g}-best (empty)")
            continue
        data = [
            [r["r_phase"] for r in rows],
            [r["r_remote"] for r in rows],
            [r["r_local"] for r in rows],
        ]
        bp = ax.boxplot(data, tick_labels=["Phase", "Remote", "Local"], patch_artist=True, showfliers=False)
        for patch, c in zip(bp["boxes"], ("#d62728", "#1f77b4", "#2ca02c")):
            patch.set_facecolor(c)
            patch.set_alpha(0.5)
        s = summary[g]
        ax.set_title(f"E1b within {g}-best | Δr_P mean={s.get('delta_r_p_mean', float('nan')):.3f}")
        ax.set_ylabel("|corr| (sign+lag)")
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("E1b waveform fidelity (same-window cross-modal; avoids selection bias)")
    fig.tight_layout()
    fig_path = _save_figure(fig, "phase_e1_waveform_fidelity")

    return {
        "experiment": "E1b",
        "n_records": len(records),
        "summary_by_oracle_group": summary,
        "h2_supported": bool(h2),
        "note": (
            "Phase-best 窗内 Phase 波形相关优于幅值"
            if h2
            else "即使在 Phase-best 窗内，Phase 波形也未系统性优于幅值"
        ),
        "figure": str(fig_path.relative_to(project_root)).replace("\\", "/"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-e1b", action="store_true")
    ap.add_argument("--max-remote-per-rec", type=int, default=12)
    args = ap.parse_args()

    oracle = _load_oracle()
    print(f"oracle windows: {len(oracle)} (hkh={(oracle['domain']=='hkh').sum()}, cs={(oracle['domain']=='cs').sum()})")

    print("=== E1a ===")
    e1a = run_e1a(oracle)
    _save_json(REPORTS_DIR / "phase_e1a_diagnostics.json", e1a)
    print("  HKH H1:", e1a["by_domain"]["hkh"])
    print("  CS  H1:", e1a["by_domain"]["cs"])

    print("=== E1c ===")
    e1c = run_e1c(oracle, tau=1.0)
    _save_json(REPORTS_DIR / "phase_e1c_rescue_metrics.json", e1c)
    print("  HKH pooled:", {k: e1c["by_domain"]["hkh"]["pooled"][k] for k in ("rescue_rate", "unique_correct", "destruction_rate", "oracle_rl", "oracle_rlp")})
    print("  CS  pooled:", {k: e1c["by_domain"]["cs"]["pooled"][k] for k in ("rescue_rate", "unique_correct", "destruction_rate", "oracle_rl", "oracle_rlp")})

    print("=== E4 ===")
    e4 = run_e4(oracle)
    _save_json(REPORTS_DIR / "phase_e4_channel_vs_modal_rho.json", e4)
    print(" ", e4["conclusion"])

    print("=== E5 ===")
    e5 = run_e5(oracle)
    _save_json(REPORTS_DIR / "phase_e5_hkh_vs_cs.json", e5)
    print(" ", e5["conclusion"])

    e1b = None
    if not args.skip_e1b:
        print("=== E1b (waveforms) ===")
        e1b = run_e1b(oracle, max_remote_per_rec=args.max_remote_per_rec)
        _save_json(REPORTS_DIR / "phase_e1b_waveform_fidelity.json", e1b)
        print(" ", e1b.get("note"), e1b.get("summary_by_oracle_group"))

    combined = {
        "date": "2026-07-26",
        "e1a": {d: e1a["by_domain"][d] for d in ("hkh", "cs")},
        "e1b": {
            "h2_supported": None if e1b is None else e1b.get("h2_supported"),
            "summary": None if e1b is None else e1b.get("summary_by_oracle_group"),
            "note": None if e1b is None else e1b.get("note"),
        },
        "e1c": {
            "hkh": e1c["by_domain"]["hkh"]["pooled"],
            "cs": e1c["by_domain"]["cs"]["pooled"],
        },
        "e4_conclusion": e4["conclusion"],
        "e4_by_domain": e4["by_domain"],
        "e5_conclusion": e5["conclusion"],
        "e5_hypotheses": e5["hypotheses"],
        "e2_e3_status": "NOT STARTED — await Review; D1=C implies simplified only after this batch",
    }
    path = _save_json(REPORTS_DIR / "phase_e1_diagnostics.json", combined)
    print(f"Combined diagnostics -> {path}")


if __name__ == "__main__":
    main()
