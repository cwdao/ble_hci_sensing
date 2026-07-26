"""Unified pipeline final: Candidate A (Amplitude-only) vs Candidate B (Phase-gated).

Plan: docs/plans/unified_pipeline_final_plan.md

Run:
    python notebooks/scripts/chFusion_unified_pipeline.py
    python notebooks/scripts/chFusion_unified_pipeline.py --skip-waveform
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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
from ble_analysis.coherent_mrc import coherent_mrc_fuse_modals
from ble_analysis.iq_geometry import subject_cluster_paired_bootstrap
from ble_analysis.phase_adaptive_gating import (
    active_modals_to_spectrum_keys,
    gate_by_confidence,
)
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.systematic_fusion import modal_fusion_eta_only
from ble_analysis.voting_fusion import VotingConfig
from ble_analysis.waveform_metrics import (
    recording_level_rmse,
    resample_to_length,
    stitch_overlapping_windows,
    window_rmse_against_reference,
)
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

# LOSO θ candidates; +inf = Phase never on = Candidate A
THETA_CANDIDATES = [0.30, 0.35, 0.38, 0.40, float("inf")]
TIE_EPS = 0.01  # BPM; prefer lower Phase activation when within this

ORACLE_VARIANT = B3VariantConfig(
    use_voting=True,
    use_two_level_hilbert=False,
    modal_combine="fuse",
    bpm_source="spectral",
    modal_weight_mode="equal",
)
WAVEFORM_VARIANT = B3VariantConfig(
    use_voting=True,
    use_two_level_hilbert=True,
    modal_combine="fuse",
    bpm_source="waveform",
    modal_weight_mode="eta",
)

METHOD_LABELS = {
    "candidate_a": "Amplitude-only BreatheCS (Voting→R+L η-weighted)",
    "candidate_b": "Phase-gated BreatheCS (Voting→conf gate→η-weighted)",
    "rl_equal": "Voting→R+L equal (p0_rl_default)",
    "draft_ms_remote": "Voting→Remote only",
    "draft_s_full": "Voting -> equal 3-modal",
    "e3a": "Voting -> eta-weighted 3-modal (no gate)",
    "rl_waveform": "R+L coherent MRC waveform",
    "candidate_a_wf": "Candidate A waveform (R+L MRC)",
    "candidate_b_wf": "Candidate B waveform (gated MRC)",
    "remote_waveform": "Remote-only MRC waveform",
}


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, set):
        return sorted(obj)
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
    for p in sid.split("-"):
        if p.startswith("sbj_"):
            return p
    return "unknown"


def _theta_label(theta: float) -> str:
    return "+inf" if not np.isfinite(theta) else f"{theta:.2f}"


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


def _fuse_bpm(
    rec: dict,
    active_keys: Set[str],
) -> float:
    eta_map = {m: float(rec["packs"][m]["eta"]) for m in active_keys if m in rec["spectra"]}
    specs = {m: rec["spectra"][m] for m in active_keys if m in rec["spectra"]}
    bpm, _ = modal_fusion_eta_only(specs, eta_map, rec["band_freqs"], rec["cfg"])
    return float(bpm)


def _bpm_from_spectrum(rec: dict, modal: str) -> float:
    """Peak BPM from a modal weighted spectrum (matches draft ablation primary BPM)."""
    from ble_analysis.chfusion import _parabolic_peak_freq

    spec = np.asarray(rec["spectra"][modal], dtype=float)
    band = np.asarray(rec["band_freqs"], dtype=float)
    cfg = rec["cfg"]
    if spec.size == 0 or float(np.sum(spec)) <= cfg.eps:
        return float("nan")
    k = int(np.argmax(spec))
    f_peak = _parabolic_peak_freq(band, spec, k, cfg.eps)
    return float(60.0 * f_peak)


def _err(bpm: float, gt: float, domain: str) -> float:
    if domain == "hkh":
        return abs(float(bpm) - float(gt))
    return abs(float(bpm) - float(gt)) / float(gt) * 100.0


def _eval_method_on_recs(
    recs: Sequence[dict],
    method: str,
    *,
    theta_conf: float,
    domain: str,
) -> Dict[str, Any]:
    if not recs:
        return {"mean_err": float("nan"), "n": 0, "phase_activation_rate": 0.0}

    errs: List[float] = []
    phase_on = 0
    for rec in recs:
        packs = rec["packs"]
        if method == "candidate_a":
            active = {"remote", "local"}
        elif method == "candidate_b":
            gate = gate_by_confidence(
                {"R": packs["remote"]["conf"], "L": packs["local"]["conf"], "P": packs["phase"]["conf"]},
                theta_conf=theta_conf,
            )
            active = active_modals_to_spectrum_keys(gate)
            if "phase" in active:
                phase_on += 1
        elif method == "rl_equal":
            # equal R+L for sanity vs prior 0.372
            from ble_analysis.systematic_fusion import modal_fusion_from_spectra

            scores = {m: packs[m]["conf"] for m in ("remote", "local")}
            specs = {m: rec["spectra"][m] for m in ("remote", "local")}
            bpm, _ = modal_fusion_from_spectra(
                specs, scores, "equal", rec["band_freqs"], rec["cfg"]
            )
            err = _err(bpm, rec["bpm_gt"], domain)
            if np.isfinite(err):
                errs.append(err)
            continue
        elif method == "draft_ms_remote":
            bpm = _bpm_from_spectrum(rec, "remote")
            err = _err(bpm, rec["bpm_gt"], domain)
            if np.isfinite(err):
                errs.append(err)
            continue
        elif method == "draft_s_full":
            from ble_analysis.systematic_fusion import modal_fusion_from_spectra

            scores = {m: packs[m]["conf"] for m in rec["spectra"]}
            bpm, _ = modal_fusion_from_spectra(
                rec["spectra"], scores, "equal", rec["band_freqs"], rec["cfg"]
            )
            err = _err(bpm, rec["bpm_gt"], domain)
            if np.isfinite(err):
                errs.append(err)
            continue
        elif method == "e3a":
            active = {"remote", "local", "phase"}
        else:
            raise ValueError(method)

        bpm = _fuse_bpm(rec, active)
        err = _err(bpm, rec["bpm_gt"], domain)
        if np.isfinite(err):
            errs.append(err)

    return {
        "mean_err": float(np.mean(errs)) if errs else float("nan"),
        "std_err": float(np.std(errs)) if errs else float("nan"),
        "n": len(errs),
        "phase_activation_rate": float(phase_on / max(len(recs), 1)),
    }


def _select_theta_on_train(train_recs_by_sid: Dict[str, List[dict]]) -> Tuple[float, Dict[str, Any]]:
    """Pick θ on train recordings: min BPM; tie-break → lower Phase activation."""
    details = []
    best_theta = float("inf")
    best_err = float("inf")
    best_act = float("inf")
    for theta in THETA_CANDIDATES:
        errs = []
        acts = []
        for sid, recs in train_recs_by_sid.items():
            ev = _eval_method_on_recs(recs, "candidate_b", theta_conf=theta, domain="hkh")
            errs.append(ev["mean_err"])
            acts.append(ev["phase_activation_rate"])
        mean_err = float(np.nanmean(errs))
        mean_act = float(np.nanmean(acts))
        details.append(
            {
                "theta": None if not np.isfinite(theta) else float(theta),
                "theta_label": _theta_label(theta),
                "train_mean_err": mean_err,
                "train_phase_activation": mean_act,
            }
        )
        better = False
        if mean_err < best_err - TIE_EPS:
            better = True
        elif abs(mean_err - best_err) <= TIE_EPS and mean_act < best_act:
            better = True
        if better:
            best_err = mean_err
            best_act = mean_act
            best_theta = theta
    return best_theta, {"candidates": details, "chosen_theta": best_theta, "chosen_err": best_err}


def run_hkh_loso(all_recs: Dict[str, List[dict]]) -> Dict[str, Any]:
    subjects = sorted({_subject_of(s) for s in all_recs})
    methods_need = [
        "candidate_a",
        "candidate_b",
        "rl_equal",
        "draft_ms_remote",
        "draft_s_full",
        "e3a",
    ]
    per_rec: Dict[str, Dict[str, float]] = {m: {} for m in methods_need}
    phase_act_per_rec: Dict[str, float] = {}
    fold_details = []
    chosen_thetas: Dict[str, float] = {}

    for held in subjects:
        train = {s: all_recs[s] for s in all_recs if _subject_of(s) != held}
        test_sids = [s for s in all_recs if _subject_of(s) == held]
        theta, sel = _select_theta_on_train(train)
        chosen_thetas[held] = theta
        fold_details.append(
            {
                "held_subject": held,
                "theta": None if not np.isfinite(theta) else float(theta),
                "theta_label": _theta_label(theta),
                "selection": sel,
            }
        )
        for sid in test_sids:
            for method in methods_need:
                th = theta if method == "candidate_b" else float("inf")
                ev = _eval_method_on_recs(all_recs[sid], method, theta_conf=th, domain="hkh")
                per_rec[method][sid] = ev["mean_err"]
                if method == "candidate_b":
                    phase_act_per_rec[sid] = ev["phase_activation_rate"]

    methods_out = {}
    for m, recmap in per_rec.items():
        vals = [v for v in recmap.values() if np.isfinite(v)]
        methods_out[m] = {
            "label": METHOD_LABELS.get(m, m),
            "bpm_mean_abs_err": float(np.mean(vals)) if vals else float("nan"),
            "bpm_std_across_recordings": float(np.std(vals)) if vals else float("nan"),
            "per_recording": recmap,
            "n_scenarios": len(vals),
        }
        if m == "candidate_b":
            acts = [phase_act_per_rec[s] for s in recmap if s in phase_act_per_rec]
            methods_out[m]["phase_activation_rate_mean"] = (
                float(np.mean(acts)) if acts else float("nan")
            )
            methods_out[m]["phase_activation_per_recording"] = phase_act_per_rec

    rec_to_subj = {sid: _subject_of(sid) for sid in all_recs}
    boot = subject_cluster_paired_bootstrap(
        {
            "candidate_a": per_rec["candidate_a"],
            "candidate_b": per_rec["candidate_b"],
            "draft_ms_remote": per_rec["draft_ms_remote"],
            "draft_s_full": per_rec["draft_s_full"],
        },
        rec_to_subj,
        n_bootstrap=10000,
        seed=11,
    )

    theta_vals = list(chosen_thetas.values())
    finite_thetas = [t for t in theta_vals if np.isfinite(t)]
    # CS uses median of LOSO-chosen θ; if all +inf → +inf
    if len(finite_thetas) == 0:
        cs_theta = float("inf")
    else:
        # Include +inf as a very large number only if majority; else median of finite
        n_inf = sum(1 for t in theta_vals if not np.isfinite(t))
        if n_inf >= len(theta_vals) / 2:
            cs_theta = float("inf")
        else:
            cs_theta = float(np.median(finite_thetas))

    return {
        "domain": "hkh",
        "metric": "bpm_mean_abs_err",
        "loso_chosen_theta": {k: (None if not np.isfinite(v) else float(v)) for k, v in chosen_thetas.items()},
        "loso_chosen_theta_labels": {k: _theta_label(v) for k, v in chosen_thetas.items()},
        "cs_theta_from_loso_median": None if not np.isfinite(cs_theta) else float(cs_theta),
        "cs_theta_label": _theta_label(cs_theta),
        "folds": fold_details,
        "methods": methods_out,
        "bootstrap_subject_cluster": boot,
        "_cs_theta": cs_theta,
    }


def run_cs(all_recs: Dict[str, List[dict]], theta_conf: float) -> Dict[str, Any]:
    methods_need = [
        "candidate_a",
        "candidate_b",
        "rl_equal",
        "draft_ms_remote",
        "draft_s_full",
        "e3a",
    ]
    methods_out = {}
    for method in methods_need:
        per = {}
        acts = []
        for sid, recs in all_recs.items():
            th = theta_conf if method == "candidate_b" else float("inf")
            ev = _eval_method_on_recs(recs, method, theta_conf=th, domain="cs")
            per[sid] = ev["mean_err"]
            if method == "candidate_b":
                acts.append(ev["phase_activation_rate"])
        vals = [v for v in per.values() if np.isfinite(v)]
        methods_out[method] = {
            "label": METHOD_LABELS.get(method, method),
            "bpm_mean_rel_err_pct": float(np.mean(vals)) if vals else float("nan"),
            "bpm_std_across_recordings": float(np.std(vals)) if vals else float("nan"),
            "per_recording": per,
            "n_scenarios": len(vals),
        }
        if method == "candidate_b":
            methods_out[method]["phase_activation_rate_mean"] = (
                float(np.mean(acts)) if acts else float("nan")
            )
    return {
        "domain": "cs",
        "metric": "bpm_mean_rel_err_pct",
        "theta_conf": None if not np.isfinite(theta_conf) else float(theta_conf),
        "theta_label": _theta_label(theta_conf),
        "methods": methods_out,
    }


def _run_waveform_hkh(
    scenario_ids: Sequence[str],
    *,
    theta_conf: float,
    spectral_cache: Optional[Dict[str, List[dict]]] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Waveform RMSE under frozen recording-level protocol (+ window-mean for baseline cmp)."""
    per_rec_reclevel: Dict[str, Dict[str, float]] = defaultdict(dict)
    per_rec_winmean: Dict[str, Dict[str, float]] = defaultdict(dict)
    phase_act: Dict[str, float] = {}
    align_meta: Dict[str, dict] = {}

    from ble_analysis.chfusion import _energy_ratio
    from ble_analysis.coherent_mrc import coherent_mrc_fuse_tones
    from ble_analysis.wifi_mrc import _collect_modal_window_matrix as collect_mat

    for sid in scenario_ids:
        if verbose:
            print(f"  waveform {sid} ...")
        conf_by_wi: Dict[int, float] = {}
        if spectral_cache and sid in spectral_cache:
            for rec in spectral_cache[sid]:
                conf_by_wi[int(rec["window_idx"])] = float(rec["packs"]["phase"]["conf"])
        scenario = load_scenario(sid, project_root=project_root)
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
        processed_dir = (project_root / Path(scenario.data_file)).parent
        hkh_bp, hkh_t, cs_t, preprocess_meta = load_hkh_gt_signals(processed_dir)
        _ = (
            hkh_bp,
            preprocess_meta,
        )  # hkh_bp used via window helper; keep load side-effects
        fs_hkh = _resolve_hkh_fs(
            hkh_bp, hkh_t, preprocess_meta.get("sampling_rate_hz", {}).get("hkh_used")
        )
        _ = fs_hkh

        ref_seg = multichannel_by_var["phases"].get("main")
        if ref_seg is None:
            seg_name = None
            for sn, sg in multichannel_by_var["phases"].items():
                if sg is not None and sg.get("metadata", {}).get("type") != "apnea":
                    ref_seg = sg
                    seg_name = sn
                    break
            if ref_seg is None or seg_name is None:
                continue
        else:
            seg_name = "main"

        fs = float(ref_seg["metadata"]["sampling_rate"])
        ch_map = ref_seg["channels"]
        ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
        seg_var = ref_seg.get("variable", "phases")
        ref_len = max(len(ch_map[c][seg_var]["bandpass_filtered"]) for c in ch_list)
        win_len = int(round(mp.window_length_sec * fs))
        step_len = int(round(mp.step_length_sec * fs))
        if ref_len < win_len:
            continue
        starts = _sliding_window_indices(ref_len, win_len, step_len)

        method_windows: Dict[str, List[np.ndarray]] = {
            "rl_waveform": [],
            "candidate_a_wf": [],
            "candidate_b_wf": [],
            "remote_waveform": [],
        }
        method_starts: Dict[str, List[int]] = {k: [] for k in method_windows}
        win_rmses: Dict[str, List[float]] = {k: [] for k in method_windows}
        gt_win_list: List[np.ndarray] = []
        gt_starts: List[int] = []
        phase_on = 0
        n_ok = 0

        for wi, st in enumerate(starts):
            end = st + win_len
            conf_p = float(conf_by_wi.get(wi, 0.0))

            modal_waveforms: Dict[str, np.ndarray] = {}
            modal_etas: Dict[str, float] = {}
            need_phase = np.isfinite(theta_conf)  # +inf → never need Phase waveform
            vars_to_fuse = [
                ("remote_amplitudes", "remote"),
                ("local_amplitudes", "local"),
            ]
            if need_phase:
                vars_to_fuse.append(("phases", "phase"))
            for variable, short in vars_to_fuse:
                ref = multichannel_by_var.get(variable, {}).get(seg_name)
                if ref is None:
                    continue
                X, eta_mrc, rho_mrc = collect_mat(
                    ch_list, ref["channels"], variable, st, end, fs, cfg
                )
                y_modal, _info = coherent_mrc_fuse_tones(
                    X,
                    eta_mrc,
                    rho_mrc,
                    phase_method="hilbert",
                    weight_mode="coherence_gated",
                    fs=fs,
                    min_coherence=0.0,
                )
                modal_waveforms[short] = y_modal
                modal_etas[short] = _energy_ratio(y_modal, fs, cfg)

            if "remote" not in modal_waveforms or "local" not in modal_waveforms:
                continue

            t0, t1 = _ble_window_time_range(cs_t, st, end, fs, win_len)
            hkh_win = _hkh_window_bandpass(hkh_bp, hkh_t, t0, t1 + 1)
            if len(hkh_win) < 4:
                continue
            hkh_rs = resample_to_length(hkh_win, win_len)
            gt_win_list.append(hkh_rs)
            gt_starts.append(st)

            y_rl, _ = coherent_mrc_fuse_modals(
                {"remote": modal_waveforms["remote"], "local": modal_waveforms["local"]},
                {"remote": modal_etas["remote"], "local": modal_etas["local"]},
                modal_weight_mode="eta",
                use_phase_align=True,
            )
            gate = gate_by_confidence({"P": conf_p}, theta_conf=theta_conf)
            if "P" in gate and "phase" in modal_waveforms:
                phase_on += 1
                y_b, _ = coherent_mrc_fuse_modals(
                    {
                        "remote": modal_waveforms["remote"],
                        "local": modal_waveforms["local"],
                        "phase": modal_waveforms["phase"],
                    },
                    {
                        "remote": modal_etas["remote"],
                        "local": modal_etas["local"],
                        "phase": modal_etas.get("phase", 0.0),
                    },
                    modal_weight_mode="eta",
                    use_phase_align=True,
                )
            else:
                y_b = y_rl

            y_remote = modal_waveforms["remote"]

            for key, y in (
                ("rl_waveform", y_rl),
                ("candidate_a_wf", y_rl),
                ("candidate_b_wf", y_b),
                ("remote_waveform", y_remote),
            ):
                if y is None or len(y) < 4:
                    continue
                method_windows[key].append(np.asarray(y, dtype=float))
                method_starts[key].append(st)
                wr, _ = window_rmse_against_reference(y, hkh_win)
                if np.isfinite(wr):
                    win_rmses[key].append(float(wr))
            n_ok += 1

        if n_ok == 0:
            continue

        gt_stitched = stitch_overlapping_windows(gt_win_list, gt_starts, ref_len)
        # max lag ≈ 2 s
        max_lag = int(round(2.0 * fs))
        for key in method_windows:
            if not method_windows[key]:
                continue
            est = stitch_overlapping_windows(method_windows[key], method_starts[key], ref_len)
            # Align GT to BLE length already
            meta = recording_level_rmse(est, gt_stitched, max_lag=max_lag)
            per_rec_reclevel[key][sid] = float(meta["rmse"])
            per_rec_winmean[key][sid] = (
                float(np.mean(win_rmses[key])) if win_rmses[key] else float("nan")
            )
            align_meta[f"{sid}:{key}"] = meta
        phase_act[sid] = float(phase_on / max(n_ok, 1))

    methods_out = {}
    for key in ("rl_waveform", "candidate_a_wf", "candidate_b_wf", "remote_waveform"):
        vals_r = [v for v in per_rec_reclevel[key].values() if np.isfinite(v)]
        vals_w = [v for v in per_rec_winmean[key].values() if np.isfinite(v)]
        methods_out[key] = {
            "label": METHOD_LABELS.get(key, key),
            "rmse_recording_level_mean": float(np.mean(vals_r)) if vals_r else float("nan"),
            "rmse_recording_level_std": float(np.std(vals_r)) if vals_r else float("nan"),
            "rmse_window_mean_mean": float(np.mean(vals_w)) if vals_w else float("nan"),
            "rmse_window_mean_std": float(np.std(vals_w)) if vals_w else float("nan"),
            "per_recording_recording_level": dict(per_rec_reclevel[key]),
            "per_recording_window_mean": dict(per_rec_winmean[key]),
            "n_scenarios": len(vals_r),
        }
        if key == "candidate_b_wf":
            methods_out[key]["phase_activation_rate_mean"] = (
                float(np.mean(list(phase_act.values()))) if phase_act else float("nan")
            )
            methods_out[key]["phase_activation_per_recording"] = phase_act

    return {
        "domain": "hkh",
        "metric": "waveform_rmse",
        "theta_conf": None if not np.isfinite(theta_conf) else float(theta_conf),
        "theta_label": _theta_label(theta_conf),
        "protocol": {
            "zscore": "per-recording",
            "polarity": "global_one_flip",
            "lag": "recording-level ±2s search",
            "stitch": "overlap-average",
            "no_per_window_gt_align": True,
        },
        "methods": methods_out,
        "align_meta_sample": {k: align_meta[k] for k in list(align_meta)[:6]},
    }


def _barh_fig(rows: List[Tuple[str, float]], title: str, xlabel: str, stem: str) -> Path:
    rows = [r for r in rows if np.isfinite(r[1])]
    rows.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(9, max(3.5, 0.45 * len(rows) + 1)))
    ys = np.arange(len(rows))
    ax.barh(ys, [r[1] for r in rows], color="#2a6f97")
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, stem)


def _paired_diff_fig(
    per_a: Dict[str, float],
    per_b: Dict[str, float],
    title: str,
    stem: str,
) -> Path:
    keys = sorted(set(per_a) & set(per_b))
    diffs = [per_b[k] - per_a[k] for k in keys]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    xs = np.arange(len(keys))
    colors = ["#2a9d8f" if d <= 0 else "#e76f51" for d in diffs]
    ax.bar(xs, diffs, color=colors)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels(keys, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("B − A (negative = B better)")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return _save_figure(fig, stem)


def _conf_hist_fig(all_recs: Dict[str, List[dict]], domain: str, stem: str) -> Path:
    confs = []
    for recs in all_recs.values():
        for r in recs:
            confs.append(r["packs"]["phase"]["conf"])
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(confs, bins=30, color="#264653", alpha=0.85)
    for t in (0.30, 0.35, 0.38, 0.40):
        ax.axvline(t, color="#e9c46a", ls="--", lw=1)
    ax.set_xlabel("Phase voting confidence")
    ax.set_ylabel("Windows")
    ax.set_title(f"Phase conf distribution | {domain.upper()}")
    fig.tight_layout()
    return _save_figure(fig, stem)


def _write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-waveform", action="store_true")
    ap.add_argument("--domain", choices=("hkh", "cs", "both"), default="both")
    args = ap.parse_args()

    hkh_sum = None
    cs_sum = None
    wf_sum = None
    hkh_recs: Dict[str, List[dict]] = {}
    cs_recs: Dict[str, List[dict]] = {}

    if args.domain in ("hkh", "both"):
        print("=== Cache HKH spectral windows ===")
        for sid in HKH_SCENARIO_IDS:
            hkh_recs[sid] = _cache_scenario_windows(sid, "hkh")
        print("=== HKH LOSO (Candidate A/B) ===")
        hkh_sum = run_hkh_loso(hkh_recs)
        fig = _barh_fig(
            [
                (hkh_sum["methods"][k]["label"], hkh_sum["methods"][k]["bpm_mean_abs_err"])
                for k in hkh_sum["methods"]
            ],
            "Unified pipeline | HKH spectral BPM abs err (LOSO)",
            "BPM abs err",
            "unified_pipeline_hkh_main",
        )
        hkh_sum["figure_main"] = str(fig.relative_to(project_root)).replace("\\", "/")
        fig2 = _paired_diff_fig(
            hkh_sum["methods"]["candidate_a"]["per_recording"],
            hkh_sum["methods"]["candidate_b"]["per_recording"],
            "HKH paired: Candidate B − Candidate A (BPM abs err)",
            "unified_pipeline_paired_diff",
        )
        hkh_sum["figure_paired"] = str(fig2.relative_to(project_root)).replace("\\", "/")
        fig3 = _conf_hist_fig(hkh_recs, "hkh", "unified_pipeline_phase_reliability")
        hkh_sum["figure_phase"] = str(fig3.relative_to(project_root)).replace("\\", "/")

        # modal ablation panel
        abl_rows = [
            (hkh_sum["methods"][k]["label"], hkh_sum["methods"][k]["bpm_mean_abs_err"])
            for k in (
                "draft_ms_remote",
                "rl_equal",
                "candidate_a",
                "candidate_b",
                "e3a",
                "draft_s_full",
            )
        ]
        fig4 = _barh_fig(
            abl_rows,
            "HKH modal participation ablation",
            "BPM abs err",
            "unified_pipeline_modal_ablation",
        )
        hkh_sum["figure_ablation"] = str(fig4.relative_to(project_root)).replace("\\", "/")

        _save_json(REPORTS_DIR / "unified_pipeline_gate_loso.json", {
            "loso_chosen_theta": hkh_sum["loso_chosen_theta"],
            "loso_chosen_theta_labels": hkh_sum["loso_chosen_theta_labels"],
            "cs_theta_label": hkh_sum["cs_theta_label"],
            "cs_theta": hkh_sum["cs_theta_from_loso_median"],
            "folds": hkh_sum["folds"],
        })
        print("HKH means:")
        for k, m in sorted(
            hkh_sum["methods"].items(), key=lambda kv: kv[1]["bpm_mean_abs_err"]
        ):
            print(f"  {m['label']}: {m['bpm_mean_abs_err']:.4f}")
        print("LOSO θ:", hkh_sum["loso_chosen_theta_labels"])

    cs_theta = hkh_sum["_cs_theta"] if hkh_sum else float("inf")

    if args.domain in ("cs", "both"):
        print("=== Cache CS spectral windows ===")
        for sid in CS_SCENARIO_IDS:
            cs_recs[sid] = _cache_scenario_windows(sid, "cs")
        print(f"=== CS eval (θ={_theta_label(cs_theta)}) ===")
        cs_sum = run_cs(cs_recs, cs_theta)
        fig = _barh_fig(
            [
                (cs_sum["methods"][k]["label"], cs_sum["methods"][k]["bpm_mean_rel_err_pct"])
                for k in cs_sum["methods"]
            ],
            f"Unified pipeline | CS spectral BPM rel% (θ={_theta_label(cs_theta)})",
            "BPM rel err %",
            "unified_pipeline_cs_spectral",
        )
        cs_sum["figure"] = str(fig.relative_to(project_root)).replace("\\", "/")
        _save_json(REPORTS_DIR / "unified_pipeline_cs_tmp.json", cs_sum)  # intermediate
        print("CS means:")
        for k, m in sorted(
            cs_sum["methods"].items(), key=lambda kv: kv[1]["bpm_mean_rel_err_pct"]
        ):
            print(f"  {m['label']}: {m['bpm_mean_rel_err_pct']:.3f}%")

    if not args.skip_waveform and args.domain in ("hkh", "both"):
        print("=== HKH waveform RMSE ===")
        # Use median of finite LOSO θ for waveform Candidate B; if all +inf use +inf
        wf_theta = cs_theta
        # Per-recording LOSO θ would be ideal; use global CS θ (LOSO median) for simplicity
        # and also report per-fold θ stability separately.
        wf_sum = _run_waveform_hkh(
            HKH_SCENARIO_IDS,
            theta_conf=wf_theta,
            spectral_cache=hkh_recs if hkh_recs else None,
        )
        _save_json(REPORTS_DIR / "unified_pipeline_waveform_hkh_summary.json", wf_sum)
        print("Waveform recording-level RMSE:")
        for k, m in wf_sum["methods"].items():
            print(
                f"  {m['label']}: rec={m['rmse_recording_level_mean']:.4f} "
                f"winmean={m['rmse_window_mean_mean']:.4f}"
            )

    # Combined spectral summary
    spectral = {
        "date": "2026-07-26",
        "hkh": {k: v for k, v in (hkh_sum or {}).items() if not k.startswith("_")},
        "cs": cs_sum,
    }
    _save_json(REPORTS_DIR / "unified_pipeline_spectral_summary.json", spectral)

    # Phase diagnostics summary
    phase_diag = {
        "hkh_phase_activation": (
            hkh_sum["methods"]["candidate_b"].get("phase_activation_rate_mean")
            if hkh_sum
            else None
        ),
        "cs_phase_activation": (
            cs_sum["methods"]["candidate_b"].get("phase_activation_rate_mean")
            if cs_sum
            else None
        ),
        "loso_theta_labels": hkh_sum.get("loso_chosen_theta_labels") if hkh_sum else None,
        "cs_theta_label": hkh_sum.get("cs_theta_label") if hkh_sum else None,
    }
    _save_json(REPORTS_DIR / "unified_pipeline_phase_diagnostics.json", phase_diag)

    # Per-recording CSV
    rows = []
    if hkh_sum:
        for sid in HKH_SCENARIO_IDS:
            row = {"scenario_id": sid, "domain": "hkh", "subject": _subject_of(sid)}
            for m, blk in hkh_sum["methods"].items():
                row[f"{m}_bpm_abs"] = blk["per_recording"].get(sid)
            if "candidate_b" in hkh_sum["methods"]:
                row["candidate_b_phase_act"] = (
                    hkh_sum["methods"]["candidate_b"]
                    .get("phase_activation_per_recording", {})
                    .get(sid)
                )
            if wf_sum:
                for m, blk in wf_sum["methods"].items():
                    row[f"{m}_rmse_rec"] = blk["per_recording_recording_level"].get(sid)
                    row[f"{m}_rmse_win"] = blk["per_recording_window_mean"].get(sid)
            rows.append(row)
    if cs_sum:
        for sid in CS_SCENARIO_IDS:
            row = {"scenario_id": sid, "domain": "cs", "subject": ""}
            for m, blk in cs_sum["methods"].items():
                row[f"{m}_bpm_rel"] = blk["per_recording"].get(sid)
            rows.append(row)
    if rows:
        # union fieldnames
        fields = sorted({k for r in rows for k in r.keys()})
        # keep scenario_id first
        fields = ["scenario_id", "domain", "subject"] + [
            f for f in fields if f not in ("scenario_id", "domain", "subject")
        ]
        _write_csv(REPORTS_DIR / "unified_pipeline_per_recording.csv", rows, fields)

    # clean tmp
    tmp = REPORTS_DIR / "unified_pipeline_cs_tmp.json"
    if tmp.exists():
        tmp.unlink()

    print("Done.")


if __name__ == "__main__":
    main()
