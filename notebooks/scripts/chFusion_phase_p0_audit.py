"""P0 audit for Phase Plan v2.0: oracle Δ, IQ geometry, statistical audit.

Plan: docs/plans/phase_unique_role_adaptive_fusion_plan.md
Deps: docs/plans/paper_experiment_dependencies_plan.md (D1/D2/D4/D5)

Run:
    python notebooks/scripts/chFusion_phase_p0_audit.py
    python notebooks/scripts/chFusion_phase_p0_audit.py --skip-iq
    python notebooks/scripts/chFusion_phase_p0_audit.py --only-iq
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.bootstrap import init_notebook
from ble_analysis.chfusion import load_multichannel_for_scenario
from ble_analysis.data import load_ble_frames
from ble_analysis.iq_geometry import (
    aggregate_modal_energies,
    compute_phase_oracle_delta,
    compute_radial_tangential_energy,
    detect_temporal_clustering,
    extract_pct_complex_series,
    recording_level_paired_bootstrap,
)
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices

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

P0C_METHODS = ("draft_ms_remote", "draft_s_channel", "draft_s_full")
P0C_LABELS = {
    "draft_ms_remote": "Remote-only",
    "draft_s_channel": "Channel-only",
    "draft_s_full": "Equal (BreatheCS)",
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


def _load_oracle_hkh() -> np.ndarray:
    path = REPORTS_DIR / "modal_oracle_per_window.npy"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run notebooks/scripts/chFusion_modal_oracle_diag.py first."
        )
    arr = np.load(path)
    return arr[arr["domain"] == "hkh"]


# ---------------------------------------------------------------------------
# P0a: Phase oracle Δ
# ---------------------------------------------------------------------------

def run_p0a(oracle: np.ndarray) -> Dict[str, Any]:
    bpm_errors: Dict[str, Dict[str, np.ndarray]] = {}
    for sid in HKH_SCENARIO_IDS:
        sub = oracle[oracle["scenario_id"] == sid]
        if len(sub) == 0:
            continue
        bpm_errors[sid] = {
            "remote": np.asarray(sub["err_remote"], dtype=float),
            "local": np.asarray(sub["err_local"], dtype=float),
            "phase": np.asarray(sub["err_phase"], dtype=float),
        }

    df = compute_phase_oracle_delta(bpm_errors)
    if hasattr(df, "to_dict"):
        rows = df.to_dict(orient="records")
        deltas = np.asarray(df["delta_oracle"], dtype=float)
    else:
        rows = list(df)
        deltas = np.asarray([r["delta_oracle"] for r in rows], dtype=float)

    n = len(deltas)
    n_ge_005 = int(np.sum(deltas >= 0.05))
    n_le_001 = int(np.sum(deltas <= 0.01))
    n_mid = int(np.sum((deltas > 0.01) & (deltas < 0.05)))

    if n_ge_005 > n / 2:
        verdict = "A"  # worth E2/E3
        verdict_note = "多数 recording Δ≥0.05 → Phase BPM rescue 值得做"
    elif n_le_001 > n / 2:
        verdict = "B"  # tiny headroom
        verdict_note = "多数 recording Δ≤0.01 → Phase BPM 救援空间极小，勿重投入门控"
    else:
        verdict = "C"
        verdict_note = "Δ 在 0.01–0.05 灰色地带 → 可简化 E2/E3，关注 leave-one-out"

    payload = {
        "experiment": "P0a",
        "metric": "delta_oracle_bpm_abs_err",
        "per_recording": rows,
        "summary": {
            "n_recordings": n,
            "mean_delta": float(np.nanmean(deltas)),
            "median_delta": float(np.nanmedian(deltas)),
            "std_delta": float(np.nanstd(deltas)),
            "min_delta": float(np.nanmin(deltas)),
            "max_delta": float(np.nanmax(deltas)),
            "n_ge_0.05": n_ge_005,
            "n_le_0.01": n_le_001,
            "n_mid_0.01_0.05": n_mid,
            "verdict_condition": verdict,
            "verdict_note": verdict_note,
        },
    }

    # figure
    fig, ax = plt.subplots(figsize=(10, 4.5))
    order = [r["recording"] for r in rows]
    vals = [r["delta_oracle"] for r in rows]
    colors = ["#2ca02c" if v >= 0.05 else ("#d62728" if v <= 0.01 else "#ff7f0e") for v in vals]
    ax.bar(range(len(vals)), vals, color=colors)
    ax.axhline(0.05, color="#2ca02c", ls="--", lw=1, label="0.05 (worth gating)")
    ax.axhline(0.01, color="#d62728", ls="--", lw=1, label="0.01 (tiny headroom)")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([o.replace("room_", "R").replace("-sbj_", "/").replace("-07", "") for o in order], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Δ_oracle (BPM abs err)")
    ax.set_title(f"P0a Phase oracle headroom | mean={payload['summary']['mean_delta']:.4f} | condition {verdict}")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig_path = _save_figure(fig, "phase_p0_oracle_delta")
    payload["figure"] = str(fig_path.relative_to(project_root)).replace("\\", "/")
    return payload


# ---------------------------------------------------------------------------
# P0c: statistical audit (bootstrap + clustering)
# ---------------------------------------------------------------------------

def run_p0c(oracle: np.ndarray) -> Dict[str, Any]:
    summary_path = REPORTS_DIR / "ble_hkh_draft_ablation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    results: Dict[str, Dict[str, float]] = {}
    for key in P0C_METHODS:
        per = summary["methods"][key]["bpm_per_scenario"]
        if len(per) != len(HKH_SCENARIO_IDS):
            raise ValueError(f"{key}: bpm_per_scenario length {len(per)} != 12")
        results[key] = {sid: float(v) for sid, v in zip(HKH_SCENARIO_IDS, per)}

    boot = recording_level_paired_bootstrap(results, n_bootstrap=10000, seed=42)

    # human-readable pair focus
    focus_pairs = {
        "remote_vs_equal": "draft_ms_remote__vs__draft_s_full",
        "remote_vs_channel": "draft_ms_remote__vs__draft_s_channel",
        "channel_vs_equal": "draft_s_channel__vs__draft_s_full",
    }
    focus = {}
    for name, pk in focus_pairs.items():
        if pk in boot["pairs"]:
            focus[name] = boot["pairs"][pk]
        else:
            # order may be reversed
            a, _, b = pk.partition("__vs__")
            alt = f"{b}__vs__{a}"
            if alt in boot["pairs"]:
                p = dict(boot["pairs"][alt])
                p["mean_diff_a_minus_b"] = -p["mean_diff_a_minus_b"]
                p["ci_low"], p["ci_high"] = -p["ci_high"], -p["ci_low"]
                p["method_a"], p["method_b"] = a, b
                focus[name] = p

    # clustering of Phase-best windows
    clustering_by_rec: Dict[str, Any] = {}
    all_phase_idx: List[int] = []
    subject_counts: Dict[str, int] = defaultdict(int)
    room_counts: Dict[str, int] = defaultdict(int)

    phase_best = oracle[oracle["best_modal"] == "phase"]
    for sid in HKH_SCENARIO_IDS:
        sub = phase_best[phase_best["scenario_id"] == sid]
        idxs = np.asarray(sub["window_idx"], dtype=int)
        cl = detect_temporal_clustering(idxs, step_sec=1.0, max_gap_steps=1)
        clustering_by_rec[sid] = cl
        all_phase_idx.extend(idxs.tolist())
        # subject / room
        # id like room_A-sbj_B-07111610
        parts = sid.split("-")
        room = parts[0]  # room_A
        sbj = parts[1] if len(parts) > 1 else "?"
        subject_counts[f"{room}-{sbj}"] += int(cl["n_total_windows"])
        room_counts[room] += int(cl["n_total_windows"])

    # global clustering is not meaningful across recordings; report totals
    total_phase = int(len(phase_best))
    total_segments = int(sum(c["n_segments"] for c in clustering_by_rec.values()))
    max_seg = max((c["max_segment_windows"] for c in clustering_by_rec.values()), default=0)

    # CI verdict for remote vs equal
    rv = focus.get("remote_vs_equal", {})
    if rv:
        # mean_diff = remote - equal; remote better if negative (lower error)
        if rv.get("ci_includes_0"):
            d4_condition = "A"
            d4_note = "Remote vs Equal 差异 CI 含 0 → 不能声称 BPM 排名显著"
        elif rv.get("mean_diff_a_minus_b", 0) < 0 and rv.get("ci_high", 1) < 0:
            d4_condition = "B"
            d4_note = "Remote 显著优于 Equal → 需诚实报告消融优于完整方法"
        else:
            d4_condition = "A"
            d4_note = "差异方向不支持 Remote 显著更优或 CI 含 0"
    else:
        d4_condition = "unknown"
        d4_note = "missing pair"

    # clustering condition: highly concentrated if few subjects dominate or few segments
    top_subj = sorted(subject_counts.items(), key=lambda kv: -kv[1])
    top2_share = (top_subj[0][1] + top_subj[1][1]) / total_phase if total_phase and len(top_subj) >= 2 else float("nan")
    if total_phase > 0 and (total_segments <= 5 or top2_share >= 0.5):
        d5_condition = "A"
        d5_note = "Phase-best 高度聚集（少段或少数 subject）→ 不能声称多次独立救援"
    else:
        d5_condition = "B"
        d5_note = "Phase-best 较分散 → 可声称条件性、低频但较广的救援"

    payload = {
        "experiment": "P0c",
        "bootstrap": boot,
        "focus_pairs": focus,
        "method_recording_means": {
            k: {
                "overall_mean": float(np.mean(list(results[k].values()))),
                "per_recording": results[k],
                "label": P0C_LABELS[k],
            }
            for k in P0C_METHODS
        },
        "phase_best_clustering": {
            "n_total_windows": total_phase,
            "n_segments_sum_over_recordings": total_segments,
            "max_segment_windows_any_recording": int(max_seg),
            "by_recording": clustering_by_rec,
            "by_subject": dict(subject_counts),
            "by_room": dict(room_counts),
            "top2_subject_share": float(top2_share),
        },
        "d4_verdict": {"condition": d4_condition, "note": d4_note},
        "d5_verdict": {"condition": d5_condition, "note": d5_note},
    }

    # figure: paired diffs
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    labels = []
    means = []
    los = []
    his = []
    for name, p in focus.items():
        labels.append(name.replace("_", "\n"))
        means.append(p["mean_diff_a_minus_b"])
        los.append(p["ci_low"])
        his.append(p["ci_high"])
    x = np.arange(len(labels))
    yerr = np.vstack([np.asarray(means) - np.asarray(los), np.asarray(his) - np.asarray(means)])
    ax.bar(x, means, color="#1f77b4", alpha=0.8)
    ax.errorbar(x, means, yerr=yerr, fmt="none", ecolor="k", capsize=4)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("mean paired diff (BPM)")
    ax.set_title("P0c recording-level paired bootstrap 95% CI")
    ax.grid(True, axis="y", alpha=0.3)

    ax = axes[1]
    # segments vs windows per recording
    recs = [s for s in HKH_SCENARIO_IDS if clustering_by_rec.get(s, {}).get("n_total_windows", 0) > 0]
    n_win = [clustering_by_rec[s]["n_total_windows"] for s in recs]
    n_seg = [clustering_by_rec[s]["n_segments"] for s in recs]
    xpos = np.arange(len(recs))
    w = 0.35
    ax.bar(xpos - w / 2, n_win, w, label="# Phase-best windows", color="#ff7f0e")
    ax.bar(xpos + w / 2, n_seg, w, label="# contiguous segments", color="#2ca02c")
    ax.set_xticks(xpos)
    ax.set_xticklabels([r.replace("room_", "").replace("-sbj_", "/")[:10] for r in recs], rotation=45, ha="right", fontsize=7)
    ax.set_title(f"P0c Phase-best clustering | total win={total_phase}, segments={total_segments}")
    ax.legend(fontsize=7)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig_path = _save_figure(fig, "phase_p0_statistical_audit")
    payload["figure"] = str(fig_path.relative_to(project_root)).replace("\\", "/")
    return payload


# ---------------------------------------------------------------------------
# P0b: IQ radial / tangential geometry
# ---------------------------------------------------------------------------

def _window_starts_for_scenario(scenario_id: str) -> Tuple[List[int], float, int]:
    """Match oracle sliding-window indexing via filtered phases length."""
    scenario = load_scenario(scenario_id, project_root=project_root)
    mp = BreathMetricParams()
    multichannel_by_var, _fs, _ = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        variables=("phases",),
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
    return starts, fs, win_len


def run_p0b(oracle: np.ndarray, *, max_scenarios: Optional[int] = None) -> Dict[str, Any]:
    mp = BreathMetricParams()
    f_band = (mp.breath_freq_low, mp.breath_freq_high)

    records: List[Dict[str, Any]] = []
    scenario_ids = HKH_SCENARIO_IDS[: max_scenarios or len(HKH_SCENARIO_IDS)]

    for sid in scenario_ids:
        print(f"[P0b] {sid}")
        scenario = load_scenario(sid, project_root=project_root)
        starts, fs, win_len = _window_starts_for_scenario(sid)

        data_path = scenario.resolve_data_path(project_root)
        _data, frames = load_ble_frames(data_path, verbose=False)
        seg = scenario.segment_config["main"]
        i0, i1 = int(seg["start"]), int(seg["end"]) + 1
        seg_frames = frames[i0:i1]
        z_l, z_r, _keys = extract_pct_complex_series(seg_frames)

        # Align complex length to filtered length if needed (usually equal)
        n_t = min(z_l.shape[1], max(starts) + win_len if starts else z_l.shape[1])
        z_l = z_l[:, :n_t]
        z_r = z_r[:, :n_t]

        sub = oracle[oracle["scenario_id"] == sid]
        for row in sub:
            wi = int(row["window_idx"])
            if wi < 0 or wi >= len(starts):
                continue
            st = starts[wi]
            en = st + win_len
            if en > z_l.shape[1]:
                continue
            el = compute_radial_tangential_energy(z_l[:, st:en], fs, f_band)
            er = compute_radial_tangential_energy(z_r[:, st:en], fs, f_band)
            agg = aggregate_modal_energies(el["E_rad"], er["E_rad"], el["E_tan"], er["E_tan"])
            records.append(
                {
                    "scenario_id": sid,
                    "window_idx": wi,
                    "best_modal": str(row["best_modal"]),
                    "err_remote": float(row["err_remote"]),
                    "err_local": float(row["err_local"]),
                    "err_phase": float(row["err_phase"]),
                    **agg,
                }
            )

    if not records:
        return {"experiment": "P0b", "error": "no windows computed", "n_windows": 0}

    # group stats
    by_best: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_best[r["best_modal"]].append(r)

    def _group_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not rows:
            return {"n": 0}
        out: Dict[str, Any] = {"n": len(rows)}
        for k in ("E_rad_R", "E_rad_L", "E_tan_P"):
            vals = np.asarray([r[k] for r in rows], dtype=float)
            out[f"{k}_mean"] = float(np.nanmean(vals))
            out[f"{k}_median"] = float(np.nanmedian(vals))
        # joint radial weakness: geometric mean of R/L rad
        rad_joint = np.asarray([np.sqrt(max(r["E_rad_R"], 0) * max(r["E_rad_L"], 0)) for r in rows], dtype=float)
        out["E_rad_joint_geo_mean"] = float(np.nanmean(rad_joint))
        out["E_rad_joint_geo_median"] = float(np.nanmedian(rad_joint))
        return out

    group_stats = {m: _group_summary(rows) for m, rows in by_best.items()}

    # Hypothesis test: Phase-best has lower joint radial / higher tan than Remote-best
    phase_rows = by_best.get("phase", [])
    remote_rows = by_best.get("remote", [])
    local_rows = by_best.get("local", [])

    def _mean(rows, key):
        if not rows:
            return float("nan")
        return float(np.nanmean([r[key] for r in rows]))

    comparison = {
        "phase_best_E_rad_R_mean": _mean(phase_rows, "E_rad_R"),
        "remote_best_E_rad_R_mean": _mean(remote_rows, "E_rad_R"),
        "phase_best_E_rad_L_mean": _mean(phase_rows, "E_rad_L"),
        "remote_best_E_rad_L_mean": _mean(remote_rows, "E_rad_L"),
        "phase_best_E_tan_P_mean": _mean(phase_rows, "E_tan_P"),
        "remote_best_E_tan_P_mean": _mean(remote_rows, "E_tan_P"),
        "phase_best_joint_rad_mean": float(
            np.nanmean([np.sqrt(max(r["E_rad_R"], 0) * max(r["E_rad_L"], 0)) for r in phase_rows])
        )
        if phase_rows
        else float("nan"),
        "remote_best_joint_rad_mean": float(
            np.nanmean([np.sqrt(max(r["E_rad_R"], 0) * max(r["E_rad_L"], 0)) for r in remote_rows])
        )
        if remote_rows
        else float("nan"),
    }

    # Condition A if phase-best joint rad lower AND tan higher (relative)
    jr_p = comparison["phase_best_joint_rad_mean"]
    jr_r = comparison["remote_best_joint_rad_mean"]
    tp = comparison["phase_best_E_tan_P_mean"]
    tr = comparison["remote_best_E_tan_P_mean"]
    rad_ok = np.isfinite(jr_p) and np.isfinite(jr_r) and jr_p < jr_r
    tan_ok = np.isfinite(tp) and np.isfinite(tr) and tp > tr
    if rad_ok and tan_ok:
        d2_condition = "A"
        d2_note = "Phase-best 窗：联合径向能量偏低且切向能量偏高 → 互补投影叙事成立"
    elif rad_ok or tan_ok:
        d2_condition = "partial"
        d2_note = "仅部分符合互补投影预测（径向或切向一侧成立）→ 叙事需谨慎"
    else:
        d2_condition = "B"
        d2_note = "无清晰径向/切向模式 → 物理叙事应保守"

    # figure
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    groups = ["phase", "remote", "local"]
    colors = {"phase": "#d62728", "remote": "#1f77b4", "local": "#2ca02c"}
    for ax, key, title in zip(
        axes,
        ("E_rad_R", "E_rad_L", "E_tan_P"),
        ("E_rad (Remote)", "E_rad (Local)", "E_tan (Phase≈L+R)"),
    ):
        data = []
        labs = []
        cols = []
        for g in groups:
            rows = by_best.get(g, [])
            if not rows:
                continue
            data.append([r[key] for r in rows])
            labs.append(f"{g}\n(n={len(rows)})")
            cols.append(colors[g])
        if data:
            bp = ax.boxplot(data, labels=labs, patch_artist=True, showfliers=False)
            for patch, c in zip(bp["boxes"], cols):
                patch.set_facecolor(c)
                patch.set_alpha(0.5)
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle(f"P0b IQ geometry by oracle-best modal | condition {d2_condition}")
    fig.tight_layout()
    fig_path = _save_figure(fig, "phase_p0_radial_tangential_energy")

    # compact per-window table for downstream (optional npy)
    dtype = np.dtype(
        [
            ("scenario_id", "U64"),
            ("window_idx", "i4"),
            ("best_modal", "U16"),
            ("E_rad_R", "f8"),
            ("E_rad_L", "f8"),
            ("E_tan_P", "f8"),
        ]
    )
    arr = np.zeros(len(records), dtype=dtype)
    for i, r in enumerate(records):
        arr[i] = (r["scenario_id"], r["window_idx"], r["best_modal"], r["E_rad_R"], r["E_rad_L"], r["E_tan_P"])
    npy_path = REPORTS_DIR / "phase_p0_iq_geometry_per_window.npy"
    np.save(npy_path, arr)

    return {
        "experiment": "P0b",
        "n_windows": len(records),
        "n_scenarios": len(scenario_ids),
        "group_stats": group_stats,
        "comparison": comparison,
        "d2_verdict": {"condition": d2_condition, "note": d2_note},
        "figure": str(fig_path.relative_to(project_root)).replace("\\", "/"),
        "per_window_npy": str(npy_path.relative_to(project_root)).replace("\\", "/"),
        "n_local_best": len(local_rows),
    }


def main():
    ap = argparse.ArgumentParser(description="Phase Plan v2.0 P0 audit")
    ap.add_argument("--skip-iq", action="store_true", help="Skip P0b IQ geometry (slow)")
    ap.add_argument("--only-iq", action="store_true", help="Only run P0b")
    ap.add_argument("--max-scenarios", type=int, default=None, help="Limit scenarios for P0b debug")
    args = ap.parse_args()

    oracle = _load_oracle_hkh()
    print(f"Loaded HKH oracle windows: {len(oracle)}")

    out_a = out_b = out_c = None

    if not args.only_iq:
        print("=== P0a oracle Δ ===")
        out_a = run_p0a(oracle)
        path_a = _save_json(REPORTS_DIR / "phase_p0_oracle_delta.json", out_a)
        print(f"Saved {path_a}")
        print(f"  mean Δ={out_a['summary']['mean_delta']:.4f} | condition {out_a['summary']['verdict_condition']}")
        print(f"  {out_a['summary']['verdict_note']}")

        print("=== P0c statistical audit ===")
        out_c = run_p0c(oracle)
        path_c = _save_json(REPORTS_DIR / "phase_p0_statistical_audit.json", out_c)
        print(f"Saved {path_c}")
        print(f"  D4: {out_c['d4_verdict']}")
        print(f"  D5: {out_c['d5_verdict']}")

    if not args.skip_iq:
        print("=== P0b IQ geometry ===")
        out_b = run_p0b(oracle, max_scenarios=args.max_scenarios)
        path_b = _save_json(REPORTS_DIR / "phase_p0_iq_geometry.json", out_b)
        print(f"Saved {path_b}")
        if "d2_verdict" in out_b:
            print(f"  D2: {out_b['d2_verdict']}")

    # combined gate summary for Dependencies Plan backfill
    gate = {
        "date": "2026-07-26",
        "p0a": out_a["summary"] if out_a else None,
        "p0b": out_b.get("d2_verdict") if out_b else None,
        "p0c_d4": out_c["d4_verdict"] if out_c else None,
        "p0c_d5": out_c["d5_verdict"] if out_c else None,
        "proceed_to_e2_e3": None,
    }
    if out_a:
        cond = out_a["summary"]["verdict_condition"]
        gate["proceed_to_e2_e3"] = cond in ("A", "C")
        gate["e2_e3_recommendation"] = {
            "A": "继续 E2/E3（可完整变体，仍需 leave-one-out）",
            "B": "不要以 BPM 增益为目标做 E2/E3；最多诊断确认",
            "C": "简化 E2/E3（≤2–3 变体），关注 leave-one-out 稳健性",
        }[cond]
    _save_json(REPORTS_DIR / "phase_p0_gate_summary.json", gate)
    print("=== P0 gate summary ===")
    print(json.dumps(gate, indent=2, ensure_ascii=False, default=_json_default))


if __name__ == "__main__":
    main()
