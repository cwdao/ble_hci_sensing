"""Simplified E2/E3 Phase adaptive fusion (D1=C: ≤3 variants, LOSO thresholds).

Plan: docs/plans/phase_unique_role_adaptive_fusion_plan.md
Gate: only after P0+E1; no large search.

Run:
    python notebooks/scripts/chFusion_phase_adaptive_fusion.py
    python notebooks/scripts/chFusion_phase_adaptive_fusion.py --domain hkh
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
from ble_analysis.iq_geometry import compute_amplitude_joint_weakness, recording_level_paired_bootstrap
from ble_analysis.phase_adaptive_gating import classify_window_condition, weights_for_policy
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.systematic_fusion import modal_fusion_from_spectra
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

# D1=C: only 3 variants
POLICIES = ("p0_rl_default", "e2_tiebreak", "e3_conditional")
POLICY_LABELS = {
    "p0_rl_default": "R+L equal (no Phase)",
    "e2_tiebreak": "R+L + Phase tie-break",
    "e3_conditional": "R+L + Phase conditional",
    "draft_ms_remote": "Remote only",
    "draft_s_full": "Equal 3-modal",
}
T_AGREE_GRID = (0.5, 1.0)
ORACLE_VARIANT = B3VariantConfig(
    use_voting=True,
    use_two_level_hilbert=False,
    modal_combine="fuse",
    bpm_source="spectral",
    modal_weight_mode="equal",
)


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


def _subject_of(sid: str) -> str:
    # room_A-sbj_B-...
    parts = sid.split("-")
    for p in parts:
        if p.startswith("sbj_"):
            return p
    return "unknown"


def _cache_scenario_windows(scenario_id: str, domain: str, *, verbose: bool = True) -> List[dict]:
    scenario = load_scenario(scenario_id, project_root=project_root)
    mp = BreathMetricParams()
    cfg = ChFusionConfig(
        breath_freq_low=mp.breath_freq_low,
        breath_freq_high=mp.breath_freq_high,
        window_length_sec=mp.window_length_sec,
        step_length_sec=mp.step_length_sec,
    )
    multichannel_by_var, _fs, _ = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=FilterParams(),
        cache_dir=CACHE_DIR,
        verbose=False,
    )
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")

    hkh_bp = hkh_t = cs_t = None
    fs_hkh = None
    if domain == "hkh":
        processed_dir = (project_root / Path(scenario.data_file)).parent
        hkh_bp, hkh_t, cs_t, preprocess_meta = load_hkh_gt_signals(processed_dir)
        fs_hkh = _resolve_hkh_fs(
            hkh_bp, hkh_t, preprocess_meta.get("sampling_rate_hz", {}).get("hkh_used")
        )

    records: List[dict] = []
    phase_segs = multichannel_by_var.get("phases", {})
    for seg_name, ref_seg in phase_segs.items():
        if ref_seg is None:
            continue
        meta = ref_seg.get("metadata", {})
        if meta.get("type") == "apnea":
            continue

        fs = float(meta["sampling_rate"])
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
            if not all(m in modal for m in ("remote", "local", "phase")):
                continue

            if domain == "hkh":
                t0, t1 = _ble_window_time_range(cs_t, st, end, fs, win_len)
                hkh_win = _hkh_window_bandpass(hkh_bp, hkh_t, t0, t1 + 1)
                if len(hkh_win) < 4:
                    continue
                bpm_gt, _, _, _ = estimate_bpm_from_waveform(hkh_win, fs_hkh, cfg=cfg)
                if not np.isfinite(bpm_gt) or bpm_gt <= 0:
                    continue
            else:
                bpm_gt = meta.get("bpm_gt")
                if bpm_gt is None or not np.isfinite(float(bpm_gt)) or float(bpm_gt) <= 0:
                    continue
                bpm_gt = float(bpm_gt)

            packs = {}
            spectra = {}
            for m in ("remote", "local", "phase"):
                res = modal[m]
                packs[m] = {
                    "bpm": float(res.get("voted_bpm", float("nan"))),
                    "eta": float(res.get("mean_eta", 0.0)),
                    "rho": float(res.get("mean_rho", 0.0)),
                    "conf": float(res.get("confidence", 0.0)),
                }
                ws = res.get("weighted_spectrum")
                if ws is None:
                    continue
                spectra[m] = np.asarray(ws, dtype=float)

            if len(spectra) < 3:
                continue

            records.append(
                {
                    "scenario_id": scenario_id,
                    "subject": _subject_of(scenario_id),
                    "segment": seg_name,
                    "window_idx": wi,
                    "bpm_gt": float(bpm_gt),
                    "packs": packs,
                    "spectra": spectra,
                    "band_freqs": band_freqs,
                    "cfg": cfg,
                }
            )
    if verbose:
        print(f"  cached {scenario_id}: {len(records)} windows")
    return records


def _recording_medians(recs: Sequence[dict]) -> dict:
    eta_r = [r["packs"]["remote"]["eta"] for r in recs]
    eta_l = [r["packs"]["local"]["eta"] for r in recs]
    conf_r = [r["packs"]["remote"]["conf"] for r in recs]
    conf_l = [r["packs"]["local"]["conf"] for r in recs]
    return {
        "eta_med_r": float(np.nanmedian(eta_r)),
        "eta_med_l": float(np.nanmedian(eta_l)),
        "conf_med_r": float(np.nanmedian(conf_r)),
        "conf_med_l": float(np.nanmedian(conf_l)),
        "conf_med_rl": float(np.nanmedian(conf_r + conf_l)),
    }


def _q_amp_for_recording(recs: Sequence[dict]) -> np.ndarray:
    er = np.asarray([r["packs"]["remote"]["eta"] for r in recs], dtype=float)
    el = np.asarray([r["packs"]["local"]["eta"] for r in recs], dtype=float)
    return compute_amplitude_joint_weakness(er, el)["q_amp"]


def _eval_policy_on_recs(
    recs: Sequence[dict],
    policy: str,
    *,
    t_agree: float,
    theta_c1: float = 0.5,
    domain: str = "hkh",
) -> Dict[str, Any]:
    if not recs:
        return {"mean_err": float("nan"), "n": 0}
    med = _recording_medians(recs)
    q_amp = _q_amp_for_recording(recs)
    errs = []
    cond_counts = defaultdict(int)
    phase_on = 0
    for i, rec in enumerate(recs):
        p = rec["packs"]
        cond = classify_window_condition(
            p["remote"]["bpm"],
            p["local"]["bpm"],
            p["phase"]["bpm"],
            p["remote"]["eta"],
            p["local"]["eta"],
            p["phase"]["eta"],
            p["remote"]["conf"],
            p["local"]["conf"],
            p["phase"]["conf"],
            eta_med_r=med["eta_med_r"],
            eta_med_l=med["eta_med_l"],
            conf_med_r=med["conf_med_r"],
            conf_med_l=med["conf_med_l"],
            t_agree=t_agree,
        )
        cond_counts[cond] += 1
        w, tag = weights_for_policy(
            policy,
            cond,
            p["remote"]["bpm"],
            p["local"]["bpm"],
            p["phase"]["bpm"],
            q_amp=float(q_amp[i]),
            theta_c1=theta_c1,
            theta_disagree=t_agree,
            theta_agree=t_agree,
            conf_p=p["phase"]["conf"],
            conf_med_rl=med["conf_med_rl"],
        )
        if w.get("phase", 0) > 0:
            phase_on += 1
        scores = {m: p[m]["conf"] for m in rec["spectra"]}
        bpm, _ = modal_fusion_from_spectra(
            rec["spectra"], scores, "custom", rec["band_freqs"], rec["cfg"], custom_weights=w
        )
        gt = rec["bpm_gt"]
        if domain == "hkh":
            err = abs(float(bpm) - float(gt))
        else:
            err = abs(float(bpm) - float(gt)) / float(gt) * 100.0
        if np.isfinite(err):
            errs.append(err)
    return {
        "mean_err": float(np.mean(errs)) if errs else float("nan"),
        "std_err": float(np.std(errs)) if errs else float("nan"),
        "n": len(errs),
        "phase_activation_rate": float(phase_on / max(len(recs), 1)),
        "condition_frac": {k: v / max(len(recs), 1) for k, v in cond_counts.items()},
    }


def _baseline_remote_equal(recs: Sequence[dict], domain: str) -> Dict[str, Dict[str, float]]:
    """Remote-only and Equal-3 from cached modal spectra."""
    out = {}
    for key, mode in (("draft_ms_remote", "remote"), ("draft_s_full", "equal")):
        errs = []
        for rec in recs:
            if mode == "remote":
                bpm = rec["packs"]["remote"]["bpm"]
            else:
                scores = {m: rec["packs"][m]["conf"] for m in rec["spectra"]}
                bpm, _ = modal_fusion_from_spectra(
                    rec["spectra"], scores, "equal", rec["band_freqs"], rec["cfg"]
                )
            gt = rec["bpm_gt"]
            if domain == "hkh":
                err = abs(float(bpm) - float(gt))
            else:
                err = abs(float(bpm) - float(gt)) / float(gt) * 100.0
            if np.isfinite(err):
                errs.append(err)
        out[key] = {
            "mean_err": float(np.mean(errs)) if errs else float("nan"),
            "std_err": float(np.std(errs)) if errs else float("nan"),
            "n": len(errs),
        }
    return out


def run_hkh_loso(all_recs: Dict[str, List[dict]]) -> Dict[str, Any]:
    subjects = sorted({_subject_of(s) for s in all_recs})
    # per-recording means under LOSO-chosen t_agree
    per_rec_means: Dict[str, Dict[str, float]] = {p: {} for p in POLICIES}
    per_rec_means["draft_ms_remote"] = {}
    per_rec_means["draft_s_full"] = {}
    fold_details = []
    chosen_t = {}

    for held in subjects:
        train_sids = [s for s in all_recs if _subject_of(s) != held]
        test_sids = [s for s in all_recs if _subject_of(s) == held]
        # pick t_agree on train for e2_tiebreak / e3_conditional (shared)
        best_t = 1.0
        best_score = float("inf")
        for t in T_AGREE_GRID:
            scores = []
            for sid in train_sids:
                ev = _eval_policy_on_recs(all_recs[sid], "e2_tiebreak", t_agree=t, domain="hkh")
                scores.append(ev["mean_err"])
            m = float(np.nanmean(scores))
            if m < best_score:
                best_score = m
                best_t = t
        chosen_t[held] = best_t

        for sid in test_sids:
            base = _baseline_remote_equal(all_recs[sid], "hkh")
            for k, v in base.items():
                per_rec_means[k][sid] = v["mean_err"]
            for policy in POLICIES:
                ev = _eval_policy_on_recs(all_recs[sid], policy, t_agree=best_t, domain="hkh")
                per_rec_means[policy][sid] = ev["mean_err"]
        fold_details.append({"held_subject": held, "t_agree": best_t, "train_score": best_score})

    # overall = mean of recording means
    methods = {}
    for k, recmap in per_rec_means.items():
        vals = [v for v in recmap.values() if np.isfinite(v)]
        methods[k] = {
            "label": POLICY_LABELS.get(k, k),
            "bpm_mean_abs_err": float(np.mean(vals)) if vals else float("nan"),
            "bpm_std_across_recordings": float(np.std(vals)) if vals else float("nan"),
            "per_recording": recmap,
            "n_scenarios": len(vals),
        }

    boot = recording_level_paired_bootstrap(
        {k: methods[k]["per_recording"] for k in ("p0_rl_default", "e2_tiebreak", "e3_conditional", "draft_ms_remote", "draft_s_full")},
        n_bootstrap=10000,
        seed=7,
    )
    return {
        "domain": "hkh",
        "metric": "bpm_mean_abs_err",
        "loso_chosen_t_agree": chosen_t,
        "folds": fold_details,
        "methods": methods,
        "bootstrap": boot,
    }


def run_cs(all_recs: Dict[str, List[dict]], t_agree: float = 1.0) -> Dict[str, Any]:
    """CS: only 3 recordings — use fixed t_agree=1.0 (no subject LOSO)."""
    methods = {}
    for policy in list(POLICIES) + ["draft_ms_remote", "draft_s_full"]:
        per = {}
        act = []
        for sid, recs in all_recs.items():
            if policy in ("draft_ms_remote", "draft_s_full"):
                base = _baseline_remote_equal(recs, "cs")
                per[sid] = base[policy]["mean_err"]
            else:
                ev = _eval_policy_on_recs(recs, policy, t_agree=t_agree, domain="cs")
                per[sid] = ev["mean_err"]
                act.append(ev.get("phase_activation_rate", float("nan")))
        vals = [v for v in per.values() if np.isfinite(v)]
        methods[policy] = {
            "label": POLICY_LABELS.get(policy, policy),
            "bpm_mean_rel_err_pct": float(np.mean(vals)) if vals else float("nan"),
            "bpm_std_across_recordings": float(np.std(vals)) if vals else float("nan"),
            "per_recording": per,
            "phase_activation_rate_mean": float(np.nanmean(act)) if act else None,
            "n_scenarios": len(vals),
        }
    return {"domain": "cs", "metric": "bpm_mean_rel_err_pct", "t_agree_fixed": t_agree, "methods": methods}


def _leaderboard_fig(summary: dict, domain: str, stem: str) -> Path:
    methods = summary["methods"]
    key = "bpm_mean_abs_err" if domain == "hkh" else "bpm_mean_rel_err_pct"
    rows = [(POLICY_LABELS.get(k, k), methods[k][key], k) for k in methods]
    rows = [r for r in rows if np.isfinite(r[1])]
    rows.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ys = np.arange(len(rows))
    ax.barh(ys, [r[1] for r in rows], color="#1f77b4")
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis()
    ylab = "BPM abs err" if domain == "hkh" else "BPM rel err %"
    ax.set_xlabel(ylab)
    ax.set_title(f"Phase adaptive fusion | {domain.upper()} (simplified E2/E3)")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, stem)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=("hkh", "cs", "both"), default="both")
    args = ap.parse_args()

    results = {}
    if args.domain in ("hkh", "both"):
        print("=== Cache HKH windows ===")
        hkh_recs = {}
        for sid in HKH_SCENARIO_IDS:
            hkh_recs[sid] = _cache_scenario_windows(sid, "hkh")
        print("=== HKH LOSO eval ===")
        hkh_sum = run_hkh_loso(hkh_recs)
        fig = _leaderboard_fig(hkh_sum, "hkh", "phase_adaptive_fusion_hkh_leaderboard")
        hkh_sum["figure"] = str(fig.relative_to(project_root)).replace("\\", "/")
        _save_json(REPORTS_DIR / "phase_adaptive_fusion_hkh_summary.json", hkh_sum)
        results["hkh"] = hkh_sum
        print("HKH means:")
        for k, m in sorted(hkh_sum["methods"].items(), key=lambda kv: kv[1]["bpm_mean_abs_err"]):
            print(f"  {m['label']}: {m['bpm_mean_abs_err']:.4f}")

    if args.domain in ("cs", "both"):
        print("=== Cache CS windows ===")
        cs_recs = {}
        for sid in CS_SCENARIO_IDS:
            cs_recs[sid] = _cache_scenario_windows(sid, "cs")
        print("=== CS eval (fixed t_agree=1.0) ===")
        cs_sum = run_cs(cs_recs, t_agree=1.0)
        fig = _leaderboard_fig(cs_sum, "cs", "phase_adaptive_fusion_cs_leaderboard")
        cs_sum["figure"] = str(fig.relative_to(project_root)).replace("\\", "/")
        _save_json(REPORTS_DIR / "phase_adaptive_fusion_cs_summary.json", cs_sum)
        results["cs"] = cs_sum
        print("CS means:")
        for k, m in sorted(cs_sum["methods"].items(), key=lambda kv: kv[1]["bpm_mean_rel_err_pct"]):
            print(f"  {m['label']}: {m['bpm_mean_rel_err_pct']:.3f}%")

    # gate distribution figure from one HKH pass with t=1.0
    if "hkh" in results:
        # reuse last cached if available — recompute lightweight condition hist from summary note
        pass

    _save_json(REPORTS_DIR / "phase_adaptive_fusion_gate_summary.json", {
        "date": "2026-07-26",
        "policies": list(POLICIES),
        "d1_condition": "C",
        "hkh": {
            k: results["hkh"]["methods"][k]["bpm_mean_abs_err"]
            for k in results.get("hkh", {}).get("methods", {})
        } if "hkh" in results else None,
        "cs": {
            k: results["cs"]["methods"][k]["bpm_mean_rel_err_pct"]
            for k in results.get("cs", {}).get("methods", {})
        } if "cs" in results else None,
    })
    print("Done.")


if __name__ == "__main__":
    main()
