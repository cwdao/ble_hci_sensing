"""Gate decomposition + η confusion + breathing-band diagnostic.

Plan: docs/plans/gate_decomposition_band_diagnostic_plan.md

Confirmed decisions (user):
  - Part 4: sync FilterParams.bandpass_highcut + η breath_freq_high; BPM search stays 0.1–0.35 Hz
  - Gate-B also on CS
  - δ sweep: {0.5, 1.0, 1.5, 2.0, 3.0} BPM (zero-pad ~4× + parabolic → sub-bin)
  - Gate-A k sweep: η_p > k * min(η_r, η_l), k ∈ {1.0, 1.05, 1.1}
  - If band sweep looks effective (HKH Δ > 0.02), STOP before full benchmark

Run:
    python notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py
    python notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py --part gate
    python notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py --part confusion
    python notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py --part band
    python notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py --part wave_band
    python notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py --part quality_band
    python notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py --plot-only
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import replace
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

from ble_analysis.b3_pipeline import B3VariantConfig, estimate_b3_window  # noqa: E402
from ble_analysis.ble_hkh_validation import (  # noqa: E402
    _ble_window_time_range,
    _hkh_window_bandpass,
    _resolve_hkh_fs,
    load_hkh_gt_signals,
)
from ble_analysis.bootstrap import init_notebook  # noqa: E402
from ble_analysis.chfusion import (  # noqa: E402
    ChFusionConfig,
    _next_pow2,
    _parabolic_peak_freq,
    load_multichannel_for_scenario,
)
from ble_analysis.coherent_mrc import (  # noqa: E402
    _window_b2_bpms,
    estimate_bpm_from_waveform_multi,
)
from ble_analysis.scenarios import load_scenario  # noqa: E402
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices  # noqa: E402
from ble_analysis.systematic_fusion import modal_fusion_from_spectra  # noqa: E402
from ble_analysis.voting_fusion import VotingConfig  # noqa: E402
from ble_analysis.waveform_metrics import window_rmse_against_reference  # noqa: E402
from ble_analysis.wifi_mrc import estimate_bpm_from_waveform  # noqa: E402

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

# Gate-A: η_p > k * min(η_r, η_l)
GATE_A_KS = (1.0, 1.05, 1.1)
# Gate-B: max(BPM)-min(BPM) < δ
GATE_B_DELTAS = (0.5, 1.0, 1.5, 2.0, 3.0)
BAND_HIGHCUTS = (0.35, 0.40, 0.50, 0.60)
BPM_SEARCH_LOW = 0.1
BPM_SEARCH_HIGH = 0.35
BAND_EFFECTIVE_DELTA = 0.02  # HKH abs-err improvement threshold

ORACLE_SPEC_ETA = B3VariantConfig(
    use_voting=True,
    use_two_level_hilbert=False,
    modal_combine="fuse",
    bpm_source="spectral",
    modal_weight_mode="equal",
    tone_weight_mode="eta",
)
ORACLE_SPEC_ETA_RHO = replace(ORACLE_SPEC_ETA, tone_weight_mode="eta_rho")

DESC_LABELS = {
    "b1_eta_only_rl": "G0 R+L only (η-only)",
    "b1_eta_3modal": "G4 3-modal always (η-only)",
    "b1_eta_gate_g3": "G3 η-strict + BPM±1.5",
    "b1_eta_gate_ga_k100": "Gate-A η > 1.00·min",
    "b1_eta_gate_ga_k105": "Gate-A η > 1.05·min",
    "b1_eta_gate_ga_k110": "Gate-A η > 1.10·min",
    "b1_eta_gate_gb_d05": "Gate-B BPM range < 0.5",
    "b1_eta_gate_gb_d10": "Gate-B BPM range < 1.0",
    "b1_eta_gate_gb_d15": "Gate-B BPM range < 1.5",
    "b1_eta_gate_gb_d20": "Gate-B BPM range < 2.0",
    "b1_eta_gate_gb_d30": "Gate-B BPM range < 3.0",
    "breathecs_eta": "BreatheCS η-only 3-modal equal",
}


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        v = obj.item()
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v
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


def _nanmean(xs: Sequence[float]) -> float:
    arr = np.asarray(list(xs), dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.mean(arr)) if arr.size else float("nan")


def _nanstd(xs: Sequence[float]) -> float:
    arr = np.asarray(list(xs), dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.std(arr)) if arr.size else float("nan")


def _abs_err(est: float, gt: float) -> float:
    if not (np.isfinite(est) and np.isfinite(gt) and gt > 0):
        return float("nan")
    return abs(float(est) - float(gt))


def _rel_err_pct(est: float, gt: float) -> float:
    if not (np.isfinite(est) and np.isfinite(gt) and gt > 0):
        return float("nan")
    return 100.0 * abs(float(est) - float(gt)) / float(gt)


def _bpm_from_spectrum(spec: np.ndarray, band_freqs: np.ndarray, eps: float = 1e-12) -> float:
    s = np.asarray(spec, dtype=float)
    if s.size == 0 or float(np.sum(s)) <= eps:
        return float("nan")
    k = int(np.argmax(s))
    f_peak = _parabolic_peak_freq(band_freqs, s, k, eps)
    return float(60.0 * f_peak)


def _fuse_equal(
    spectra: Dict[str, np.ndarray], keys: Sequence[str], band_freqs: np.ndarray, cfg: ChFusionConfig
) -> float:
    use = {k: spectra[k] for k in keys if k in spectra and spectra[k] is not None}
    if not use:
        return float("nan")
    bpm, _ = modal_fusion_from_spectra(use, {k: 1.0 for k in use}, "equal", band_freqs, cfg)
    return float(bpm)


def _gate_a_key(k: float) -> str:
    return f"b1_eta_gate_ga_k{int(round(k * 100)):03d}"


def _gate_b_key(delta: float) -> str:
    return f"b1_eta_gate_gb_d{int(round(delta * 10)):02d}"


def gate_a_decision(eta_r: float, eta_l: float, eta_p: float, k: float = 1.0) -> List[str]:
    if eta_p > k * min(eta_r, eta_l):
        return ["remote", "local", "phase"]
    return ["remote", "local"]


def gate_b_decision(bpm_r: float, bpm_l: float, bpm_p: float, delta: float) -> List[str]:
    vals = [bpm_r, bpm_l, bpm_p]
    if not all(np.isfinite(v) for v in vals):
        return ["remote", "local"]
    bpm_range = max(vals) - min(vals)
    if bpm_range < delta:
        return ["remote", "local", "phase"]
    return ["remote", "local"]


def gate_g3_decision(
    eta_r: float, eta_l: float, eta_p: float, bpm_amp: float, bpm_phase: float
) -> List[str]:
    eta_ok = (eta_p > eta_r) and (eta_p > eta_l)
    bpm_ok = abs(float(bpm_phase) - float(bpm_amp)) < 1.5
    if eta_ok and bpm_ok:
        return ["remote", "local", "phase"]
    return ["remote", "local"]


def _load_scenario_bundle(
    scenario_id: str,
    domain: str,
    *,
    bandpass_highcut: float = 0.35,
    eta_breath_high: Optional[float] = None,
):
    """Load filtered MC; cfg.breath_freq_high drives η; BPM search band set separately."""
    scenario = load_scenario(scenario_id, project_root=project_root)
    mp = BreathMetricParams()
    eta_hi = float(eta_breath_high if eta_breath_high is not None else bandpass_highcut)
    cfg = ChFusionConfig(
        breath_freq_low=mp.breath_freq_low,
        breath_freq_high=eta_hi,
        window_length_sec=mp.window_length_sec,
        step_length_sec=mp.step_length_sec,
    )
    fp = FilterParams(bandpass_highcut=bandpass_highcut)
    multichannel_by_var, _fs, _ = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=fp,
        cache_dir=CACHE_DIR,
        verbose=False,
    )
    hkh_bp = hkh_t = cs_t = None
    fs_hkh = None
    if domain == "hkh":
        processed_dir = (project_root / Path(scenario.data_file)).parent
        hkh_bp, hkh_t, cs_t, preprocess_meta = load_hkh_gt_signals(processed_dir)
        fs_hkh = _resolve_hkh_fs(
            hkh_bp, hkh_t, preprocess_meta.get("sampling_rate_hz", {}).get("hkh_used")
        )
    return {
        "scenario_id": scenario_id,
        "domain": domain,
        "mp": mp,
        "cfg": cfg,
        "mc": multichannel_by_var,
        "hkh_bp": hkh_bp,
        "hkh_t": hkh_t,
        "cs_t": cs_t,
        "fs_hkh": fs_hkh,
        "bandpass_highcut": bandpass_highcut,
        "eta_breath_high": eta_hi,
    }


def _iter_windows(bundle: dict):
    mc = bundle["mc"]
    mp = bundle["mp"]
    cfg = bundle["cfg"]
    domain = bundle["domain"]
    phase_segs = mc.get("phases", {})
    for seg_name, ref_seg in phase_segs.items():
        if ref_seg is None:
            continue
        meta = ref_seg.get("metadata", {})
        if meta.get("type") == "apnea" or meta.get("segment_type") == "apnea":
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
        # BPM / spectrum search stays in canonical breath band
        band_mask = (freqs >= BPM_SEARCH_LOW) & (freqs <= BPM_SEARCH_HIGH)
        band_freqs = freqs[band_mask]
        hann = np.hanning(win_len)

        for wi, st in enumerate(starts):
            end = st + win_len
            if domain == "hkh":
                t0, t1 = _ble_window_time_range(bundle["cs_t"], st, end, fs, win_len)
                hkh_win = _hkh_window_bandpass(bundle["hkh_bp"], bundle["hkh_t"], t0, t1 + 1)
                if len(hkh_win) < 4:
                    continue
                # GT BPM search uses baseline cfg band (0.1–0.35)
                gt_cfg = replace(cfg, breath_freq_low=BPM_SEARCH_LOW, breath_freq_high=BPM_SEARCH_HIGH)
                bpm_gt, _, _, _ = estimate_bpm_from_waveform(hkh_win, bundle["fs_hkh"], cfg=gt_cfg)
                if not np.isfinite(bpm_gt) or bpm_gt <= 0:
                    continue
            else:
                bpm_gt = meta.get("bpm_gt")
                if bpm_gt is None or not np.isfinite(float(bpm_gt)) or float(bpm_gt) <= 0:
                    continue
                bpm_gt = float(bpm_gt)

            yield {
                "seg_name": seg_name,
                "ch_list": ch_list,
                "st": st,
                "end": end,
                "fs": fs,
                "nfft": nfft,
                "band_mask": band_mask,
                "band_freqs": band_freqs,
                "hann": hann,
                "bpm_gt": float(bpm_gt),
                "wi": wi,
            }


def _modal_pack_from_out(out: dict) -> Optional[dict]:
    modal = out.get("diagnostics", {}).get("modal_results", {})
    if not all(m in modal for m in ("remote", "local", "phase")):
        return None
    packs = {}
    spectra = {}
    for m in ("remote", "local", "phase"):
        res = modal[m]
        packs[m] = {
            "bpm": float(res.get("voted_bpm", float("nan"))),
            "eta": float(res.get("mean_eta", 0.0)),
            "rho": float(res.get("mean_rho", 0.0)),
        }
        ws = res.get("weighted_spectrum")
        if ws is None:
            return None
        spectra[m] = np.asarray(ws, dtype=float)
    return {"packs": packs, "spectra": spectra}


def _all_method_keys() -> List[str]:
    keys = ["b1_eta_only_rl", "b1_eta_3modal", "b1_eta_gate_g3"]
    keys += [_gate_a_key(k) for k in GATE_A_KS]
    keys += [_gate_b_key(d) for d in GATE_B_DELTAS]
    return keys


def run_gates_for_scenario(bundle: dict) -> dict:
    cfg = bundle["cfg"]
    mc = bundle["mc"]
    domain = bundle["domain"]
    err_fn = _abs_err if domain == "hkh" else _rel_err_pct
    method_keys = _all_method_keys()
    errs: Dict[str, List[float]] = {k: [] for k in method_keys}
    gate_diag: Dict[str, Dict[str, Any]] = {
        k: {"open": 0, "total": 0, "open_phase_err": [], "per_scenario_open": None}
        for k in method_keys
    }
    vcfg = VotingConfig(voting_strategy="eta_weighted")
    n_win = 0

    for win in _iter_windows(bundle):
        out = estimate_b3_window(
            multichannel_by_var=mc,
            seg_name=win["seg_name"],
            ch_list=win["ch_list"],
            st=win["st"],
            end=win["end"],
            fs=win["fs"],
            cfg=cfg,
            nfft=win["nfft"],
            band_freqs=win["band_freqs"],
            band_mask=win["band_mask"],
            hann=win["hann"],
            variant=ORACLE_SPEC_ETA,
            vcfg=vcfg,
        )
        pack = _modal_pack_from_out(out)
        if pack is None:
            continue
        n_win += 1
        gt = win["bpm_gt"]
        bf = win["band_freqs"]
        sp = pack["spectra"]
        eta_r = pack["packs"]["remote"]["eta"]
        eta_l = pack["packs"]["local"]["eta"]
        eta_p = pack["packs"]["phase"]["eta"]
        bpm_r = _bpm_from_spectrum(sp["remote"], bf, cfg.eps)
        bpm_l = _bpm_from_spectrum(sp["local"], bf, cfg.eps)
        bpm_p = _bpm_from_spectrum(sp["phase"], bf, cfg.eps)
        bpm_amp = _fuse_equal(sp, ["remote", "local"], bf, cfg)

        decisions: Dict[str, List[str]] = {
            "b1_eta_only_rl": ["remote", "local"],
            "b1_eta_3modal": ["remote", "local", "phase"],
            "b1_eta_gate_g3": gate_g3_decision(eta_r, eta_l, eta_p, bpm_amp, bpm_p),
        }
        for k in GATE_A_KS:
            decisions[_gate_a_key(k)] = gate_a_decision(eta_r, eta_l, eta_p, k)
        for d in GATE_B_DELTAS:
            decisions[_gate_b_key(d)] = gate_b_decision(bpm_r, bpm_l, bpm_p, d)

        for key, mods in decisions.items():
            bpm = _fuse_equal(sp, mods, bf, cfg)
            e = err_fn(bpm, gt)
            if np.isfinite(e):
                errs[key].append(e)
            gate_diag[key]["total"] += 1
            if "phase" in mods:
                gate_diag[key]["open"] += 1
                pe = err_fn(bpm_p, gt)
                if np.isfinite(pe):
                    gate_diag[key]["open_phase_err"].append(pe)

    methods = {
        k: {
            "label": DESC_LABELS.get(k, k),
            "mean": _nanmean(v),
            "std": _nanstd(v),
            "n": int(np.sum(np.isfinite(v))),
        }
        for k, v in errs.items()
    }
    gate = {}
    for k, g in gate_diag.items():
        tot = max(g["total"], 1)
        gate[k] = {
            "open_ratio": g["open"] / tot,
            "n_total": g["total"],
            "n_open": g["open"],
            "open_phase_err_mean": _nanmean(g["open_phase_err"]),
        }
    return {
        "scenario_id": bundle["scenario_id"],
        "domain": domain,
        "n_windows": n_win,
        "methods": methods,
        "gate": gate,
        "metric": "bpm_abs_err" if domain == "hkh" else "bpm_rel_err_pct",
    }


def aggregate_domain(scenario_results: List[dict]) -> dict:
    keys = _all_method_keys()
    methods = {}
    for k in keys:
        means = [r["methods"][k]["mean"] for r in scenario_results if k in r["methods"]]
        methods[k] = {
            "label": DESC_LABELS.get(k, k),
            "per_scenario_mean": means,
            "cross_mean": _nanmean(means),
            "cross_std": _nanstd(means),
        }
    gate = {}
    for k in keys:
        ratios = [r["gate"][k]["open_ratio"] for r in scenario_results if k in r.get("gate", {})]
        open_err = [
            r["gate"][k]["open_phase_err_mean"]
            for r in scenario_results
            if k in r.get("gate", {})
        ]
        gate[k] = {
            "open_ratio_mean": _nanmean(ratios),
            "open_phase_err_mean": _nanmean(open_err),
            "per_scenario_open_ratio": ratios,
        }
    return {
        "n_scenarios": len(scenario_results),
        "metric": scenario_results[0]["metric"] if scenario_results else None,
        "methods": methods,
        "gate": gate,
        "per_scenario": scenario_results,
    }


def run_gate_part(domains: Sequence[str]) -> Dict[str, Path]:
    paths: Dict[str, Path] = {}
    for domain in domains:
        ids = HKH_SCENARIO_IDS if domain == "hkh" else CS_SCENARIO_IDS
        results = []
        for sid in ids:
            print(f"  [gate/{domain}] {sid}")
            bundle = _load_scenario_bundle(sid, domain)
            results.append(run_gates_for_scenario(bundle))
        agg = aggregate_domain(results)
        out = REPORTS_DIR / f"gate_decomposition_{domain}.json"
        paths[domain] = _save_json(
            out,
            {
                "domain": domain,
                "gate_a_ks": list(GATE_A_KS),
                "gate_b_deltas": list(GATE_B_DELTAS),
                "aggregate": agg,
            },
        )
        print(f"  saved {out}")
    return paths


def run_confusion_part() -> Path:
    npy = REPORTS_DIR / "modal_oracle_per_window.npy"
    if not npy.is_file():
        raise FileNotFoundError(f"Missing {npy}; run chFusion_modal_oracle_diag.py first")
    rows = np.load(npy)
    hkh = rows[rows["domain"] == "hkh"]
    modals = ("remote", "local", "phase")
    eta_mat = np.column_stack([hkh["eta_remote"], hkh["eta_local"], hkh["eta_phase"]])
    eta_sel_idx = np.argmax(eta_mat, axis=1)
    eta_selected = np.array(modals)[eta_sel_idx]
    err_mat = np.column_stack([hkh["err_remote"], hkh["err_local"], hkh["err_phase"]])

    matrix = {}
    cost_buckets = {"low_rl_swap": 0, "high_to_phase": 0, "miss_phase": 0, "correct": 0}
    for ob in modals:
        matrix[ob] = {}
        for sel in modals:
            m = (hkh["best_modal"] == ob) & (eta_selected == sel)
            n = int(np.sum(m))
            # cost = selected err - oracle err
            if n:
                sel_err = err_mat[m, modals.index(sel)]
                ora_err = hkh["oracle_err"][m]
                delta = sel_err - ora_err
                matrix[ob][sel] = {
                    "n": n,
                    "pct": 100.0 * n / len(hkh),
                    "mean_selected_err": float(np.mean(sel_err)),
                    "mean_oracle_err": float(np.mean(ora_err)),
                    "mean_cost_delta": float(np.mean(delta)),
                }
            else:
                matrix[ob][sel] = {
                    "n": 0,
                    "pct": 0.0,
                    "mean_selected_err": None,
                    "mean_oracle_err": None,
                    "mean_cost_delta": None,
                }
            if ob == sel:
                cost_buckets["correct"] += n
            elif {ob, sel} <= {"remote", "local"}:
                cost_buckets["low_rl_swap"] += n
            elif sel == "phase" and ob != "phase":
                cost_buckets["high_to_phase"] += n
            elif ob == "phase" and sel != "phase":
                cost_buckets["miss_phase"] += n

    hit = cost_buckets["correct"] / max(len(hkh), 1)
    high_cost_pct = 100.0 * cost_buckets["high_to_phase"] / max(len(hkh), 1)
    payload = {
        "domain": "hkh",
        "n_windows": int(len(hkh)),
        "eta_top1_hit_rate": float(hit),
        "high_cost_to_phase_pct": float(high_cost_pct),
        "cost_buckets": cost_buckets,
        "matrix": matrix,
        "judgment": (
            "eta_usable_low_cost"
            if high_cost_pct < 2.0
            else ("eta_systematic_defect" if high_cost_pct > 5.0 else "eta_borderline")
        ),
    }
    out = REPORTS_DIR / "eta_confusion_matrix.json"
    path = _save_json(out, payload)
    print(f"  saved {path} (hit={hit:.3f}, high_cost_phase={high_cost_pct:.2f}%)")
    return path


def run_breathecs_band_for_scenario(bundle: dict) -> dict:
    """BreatheCS η-only 3-modal equal; also η top-1 hit vs single-modal oracle."""
    cfg = bundle["cfg"]
    mc = bundle["mc"]
    domain = bundle["domain"]
    err_fn = _abs_err if domain == "hkh" else _rel_err_pct
    errs: List[float] = []
    hit = 0
    total = 0
    modal_eta = {"remote": [], "local": [], "phase": []}
    vcfg = VotingConfig(voting_strategy="eta_weighted")

    for win in _iter_windows(bundle):
        out = estimate_b3_window(
            multichannel_by_var=mc,
            seg_name=win["seg_name"],
            ch_list=win["ch_list"],
            st=win["st"],
            end=win["end"],
            fs=win["fs"],
            cfg=cfg,
            nfft=win["nfft"],
            band_freqs=win["band_freqs"],
            band_mask=win["band_mask"],
            hann=win["hann"],
            variant=ORACLE_SPEC_ETA,
            vcfg=vcfg,
        )
        pack = _modal_pack_from_out(out)
        if pack is None:
            continue
        gt = win["bpm_gt"]
        bf = win["band_freqs"]
        sp = pack["spectra"]
        bpm = _fuse_equal(sp, ["remote", "local", "phase"], bf, cfg)
        e = err_fn(bpm, gt)
        if np.isfinite(e):
            errs.append(e)

        modal_bpms = {
            m: _bpm_from_spectrum(sp[m], bf, cfg.eps) for m in ("remote", "local", "phase")
        }
        modal_errs = {m: err_fn(modal_bpms[m], gt) for m in modal_bpms}
        if all(np.isfinite(v) for v in modal_errs.values()):
            oracle = min(modal_errs, key=modal_errs.get)
            eta_sel = max(
                ("remote", "local", "phase"), key=lambda m: pack["packs"][m]["eta"]
            )
            total += 1
            if eta_sel == oracle:
                hit += 1
        for m in ("remote", "local", "phase"):
            modal_eta[m].append(pack["packs"][m]["eta"])

    return {
        "scenario_id": bundle["scenario_id"],
        "domain": domain,
        "mean": _nanmean(errs),
        "std": _nanstd(errs),
        "n": len(errs),
        "eta_top1_hit_rate": (hit / total) if total else float("nan"),
        "modal_eta_mean": {m: _nanmean(v) for m, v in modal_eta.items()},
        "metric": "bpm_abs_err" if domain == "hkh" else "bpm_rel_err_pct",
    }


def run_band_part(domains: Sequence[str]) -> Tuple[Path, dict]:
    payload: Dict[str, Any] = {
        "highcuts": list(BAND_HIGHCUTS),
        "note": (
            "Option A: FilterParams.bandpass_highcut and ChFusionConfig.breath_freq_high "
            "move together; BPM search band fixed at 0.1–0.35 Hz. "
            "Full benchmark deferred until user review if HKH Δ > 0.02."
        ),
        "domains": {},
    }
    for domain in domains:
        ids = HKH_SCENARIO_IDS if domain == "hkh" else CS_SCENARIO_IDS
        by_hc = {}
        for hc in BAND_HIGHCUTS:
            print(f"  [band/{domain}] highcut={hc}")
            scen = []
            for sid in ids:
                print(f"    {sid}")
                bundle = _load_scenario_bundle(
                    sid, domain, bandpass_highcut=hc, eta_breath_high=hc
                )
                scen.append(run_breathecs_band_for_scenario(bundle))
            means = [s["mean"] for s in scen]
            hits = [s["eta_top1_hit_rate"] for s in scen]
            by_hc[str(hc)] = {
                "cross_mean": _nanmean(means),
                "cross_std": _nanstd(means),
                "eta_top1_hit_rate_mean": _nanmean(hits),
                "modal_eta_mean": {
                    m: _nanmean([s["modal_eta_mean"][m] for s in scen])
                    for m in ("remote", "local", "phase")
                },
                "per_scenario": scen,
            }
        # deltas vs 0.35 baseline
        base = by_hc["0.35"]["cross_mean"]
        for hc, row in by_hc.items():
            row["delta_vs_035"] = (
                (row["cross_mean"] - base)
                if np.isfinite(row["cross_mean"]) and np.isfinite(base)
                else float("nan")
            )
        payload["domains"][domain] = by_hc

    hkh = payload["domains"].get("hkh", {})
    effective = []
    for hc, row in hkh.items():
        d = row.get("delta_vs_035")
        # improvement = lower err → negative delta
        if d is not None and np.isfinite(d) and (-d) > BAND_EFFECTIVE_DELTA:
            effective.append({"highcut": float(hc), "delta": d})
    payload["hkh_effective_highcuts"] = effective
    payload["stop_before_full_benchmark"] = True
    payload["band_verdict"] = (
        "effective_pending_user_review" if effective else "neutral_or_worse"
    )

    out = REPORTS_DIR / "breathing_band_sweep.json"
    path = _save_json(out, payload)
    print(f"  saved {path}; verdict={payload['band_verdict']}")
    return path, payload


def run_wave_band_for_scenario(bundle: dict) -> dict:
    """HKH Wave BreatheCS (B2-D): RMSE + Wave BPM under band-expanded η/filter.

    Option A: filter + η breath highcut expanded; Wave/GT BPM search stays 0.1–0.35 Hz.
    Primary quality = η·ρ (waveform recommendation); η-only paired for reference.
    """
    cfg_eta = bundle["cfg"]  # breath_freq_high = highcut (drives η)
    cfg_bpm = replace(cfg_eta, breath_freq_low=BPM_SEARCH_LOW, breath_freq_high=BPM_SEARCH_HIGH)
    mc = bundle["mc"]
    mp = bundle["mp"]
    configs = {
        "wave_breathecs_eta_rho": "eta_rho",
        "wave_breathecs_eta": "eta",
    }
    rmse: Dict[str, List[float]] = {k: [] for k in configs}
    bpm_err: Dict[str, List[float]] = {k: [] for k in configs}

    for win in _iter_windows(bundle):
        gt = win["bpm_gt"]
        win_len = int(round(mp.window_length_sec * win["fs"]))
        t0, t1 = _ble_window_time_range(bundle["cs_t"], win["st"], win["end"], win["fs"], win_len)
        hkh_win = _hkh_window_bandpass(bundle["hkh_bp"], bundle["hkh_t"], t0, t1 + 1)
        if len(hkh_win) < 4:
            continue

        for key, qmode in configs.items():
            bpm_psd, _diag, y = _window_b2_bpms(
                mc,
                win["seg_name"],
                win["ch_list"],
                win["st"],
                win["end"],
                win["fs"],
                cfg_eta,
                phase_method="hilbert",
                weight_mode="coherence_gated",
                modal_weight_mode="eta_coherence",
                use_two_level=True,
                use_modal_phase_align=True,
                f0=None,
                min_coherence=0.2,
                pca_top_k=36,
                return_waveform=True,
                quality_mode=qmode,
            )
            if y is None or len(y) < 4:
                continue
            rmse_val, _sign = window_rmse_against_reference(y, hkh_win)
            if np.isfinite(rmse_val):
                rmse[key].append(float(rmse_val))

            bpm_out = estimate_bpm_from_waveform_multi(y, win["fs"], cfg=cfg_bpm)
            bpm_est = float(bpm_out.get("bpm_psd", bpm_psd))
            ae = _abs_err(bpm_est, gt)
            if np.isfinite(ae):
                bpm_err[key].append(ae)

    out = {}
    for key in configs:
        out[key] = {
            "rmse_mean": _nanmean(rmse[key]),
            "rmse_std": _nanstd(rmse[key]),
            "rmse_n": len(rmse[key]),
            "bpm_mean": _nanmean(bpm_err[key]),
            "bpm_std": _nanstd(bpm_err[key]),
            "bpm_n": len(bpm_err[key]),
        }
    return {
        "scenario_id": bundle["scenario_id"],
        "domain": "hkh",
        "methods": out,
    }


def run_wave_band_part() -> Tuple[Path, dict]:
    """HKH-only waveform band sweep (follow-up after spectral band looked effective)."""
    by_hc: Dict[str, Any] = {}
    for hc in BAND_HIGHCUTS:
        print(f"  [wave_band/hkh] highcut={hc}")
        scen = []
        for sid in HKH_SCENARIO_IDS:
            print(f"    {sid}")
            bundle = _load_scenario_bundle(sid, "hkh", bandpass_highcut=hc, eta_breath_high=hc)
            scen.append(run_wave_band_for_scenario(bundle))
        methods = {}
        for key in ("wave_breathecs_eta_rho", "wave_breathecs_eta"):
            rmse_means = [s["methods"][key]["rmse_mean"] for s in scen]
            bpm_means = [s["methods"][key]["bpm_mean"] for s in scen]
            methods[key] = {
                "rmse_cross_mean": _nanmean(rmse_means),
                "rmse_cross_std": _nanstd(rmse_means),
                "bpm_cross_mean": _nanmean(bpm_means),
                "bpm_cross_std": _nanstd(bpm_means),
                "per_scenario": [s["methods"][key] for s in scen],
            }
        by_hc[str(hc)] = {"methods": methods, "per_scenario_ids": [s["scenario_id"] for s in scen]}

    base_rho = by_hc["0.35"]["methods"]["wave_breathecs_eta_rho"]["rmse_cross_mean"]
    base_eta = by_hc["0.35"]["methods"]["wave_breathecs_eta"]["rmse_cross_mean"]
    for _hc, row in by_hc.items():
        r = row["methods"]["wave_breathecs_eta_rho"]["rmse_cross_mean"]
        e = row["methods"]["wave_breathecs_eta"]["rmse_cross_mean"]
        row["methods"]["wave_breathecs_eta_rho"]["rmse_delta_vs_035"] = (
            (r - base_rho) if np.isfinite(r) and np.isfinite(base_rho) else float("nan")
        )
        row["methods"]["wave_breathecs_eta"]["rmse_delta_vs_035"] = (
            (e - base_eta) if np.isfinite(e) and np.isfinite(base_eta) else float("nan")
        )

    effective = []
    for hc, row in by_hc.items():
        d = row["methods"]["wave_breathecs_eta_rho"]["rmse_delta_vs_035"]
        if d is not None and np.isfinite(d) and (-d) > 0.02:
            effective.append({"highcut": float(hc), "rmse_delta": d})

    payload = {
        "domain": "hkh",
        "highcuts": list(BAND_HIGHCUTS),
        "note": (
            "Option A on waveform branch: FilterParams.bandpass_highcut + η breath_freq_high "
            "synced; Wave/GT BPM search fixed at 0.1–0.35. Primary = B2-D η·ρ."
        ),
        "by_highcut": by_hc,
        "hkh_rmse_effective_highcuts": effective,
        "wave_band_verdict": ("effective_rmse" if effective else "neutral_or_worse_rmse"),
    }
    out = REPORTS_DIR / "breathing_band_wave_rmse_sweep.json"
    path = _save_json(out, payload)
    print(f"  saved {path}; verdict={payload['wave_band_verdict']}")
    return path, payload


def plot_f6_wave_band(wave: dict) -> Path:
    xs = [float(k) for k in BAND_HIGHCUTS if str(k) in wave["by_highcut"]]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, key, title, color in (
        (axes[0], "wave_breathecs_eta_rho", "Wave BreatheCS η·ρ RMSE", "#4C78A8"),
        (axes[1], "wave_breathecs_eta", "Wave BreatheCS η-only RMSE", "#F58518"),
    ):
        ys = [wave["by_highcut"][str(x)]["methods"][key]["rmse_cross_mean"] for x in xs]
        yerr = [
            wave["by_highcut"][str(x)]["methods"][key].get("rmse_cross_std", 0) or 0 for x in xs
        ]
        bpms = [wave["by_highcut"][str(x)]["methods"][key]["bpm_cross_mean"] for x in xs]
        ax.errorbar(xs, ys, yerr=yerr, marker="o", color=color, label="RMSE")
        ax.set_xlabel("bandpass / η highcut (Hz)")
        ax.set_ylabel("HKH Wave RMSE (mean±std across scenarios)")
        ax.set_title(title)
        ax2 = ax.twinx()
        ax2.plot(xs, bpms, "s--", color="#54A24B", label="Wave BPM abs err")
        ax2.set_ylabel("Wave BPM abs err")
    fig.suptitle(f"HKH waveform band sweep — {wave.get('wave_band_verdict', '')}", fontsize=11)
    fig.tight_layout()
    return _save_figure(fig, "gate_decomposition_figF6_wave_band_rmse")


def run_quality_band_controlled_scenario(bundle: dict) -> dict:
    """Controlled 2×2 on one HKH scenario: spectral/wave × η·ρ/η-only.

    Fixed within a highcut load:
      - same windows / GT
      - Option A filter+η highcut
      - BPM search always 0.1–0.35 Hz
    """
    cfg_eta = bundle["cfg"]
    cfg_bpm = replace(cfg_eta, breath_freq_low=BPM_SEARCH_LOW, breath_freq_high=BPM_SEARCH_HIGH)
    mc = bundle["mc"]
    mp = bundle["mp"]
    vcfg_rho = VotingConfig(voting_strategy="eta_rho_weighted")
    vcfg_eta = VotingConfig(voting_strategy="eta_weighted")

    keys = (
        "spectral_eta_rho",
        "spectral_eta",
        "spectral_rl_eta_rho",
        "spectral_rl_eta",
        "wave_eta_rho",
        "wave_eta",
    )
    bpm_errs: Dict[str, List[float]] = {k: [] for k in keys}
    rmse_errs: Dict[str, List[float]] = {"wave_eta_rho": [], "wave_eta": []}

    for win in _iter_windows(bundle):
        gt = win["bpm_gt"]
        bf = win["band_freqs"]
        common = dict(
            multichannel_by_var=mc,
            seg_name=win["seg_name"],
            ch_list=win["ch_list"],
            st=win["st"],
            end=win["end"],
            fs=win["fs"],
            cfg=cfg_eta,
            nfft=win["nfft"],
            band_freqs=bf,
            band_mask=win["band_mask"],
            hann=win["hann"],
        )
        out_rho = estimate_b3_window(
            **common, variant=ORACLE_SPEC_ETA_RHO, vcfg=vcfg_rho
        )
        out_eta = estimate_b3_window(**common, variant=ORACLE_SPEC_ETA, vcfg=vcfg_eta)
        pack_rho = _modal_pack_from_out(out_rho)
        pack_eta = _modal_pack_from_out(out_eta)
        if pack_rho is None or pack_eta is None:
            continue

        for label, pack in (
            ("spectral_eta_rho", pack_rho),
            ("spectral_eta", pack_eta),
        ):
            bpm3 = _fuse_equal(pack["spectra"], ["remote", "local", "phase"], bf, cfg_bpm)
            e3 = _abs_err(bpm3, gt)
            if np.isfinite(e3):
                bpm_errs[label].append(e3)
        for label, pack in (
            ("spectral_rl_eta_rho", pack_rho),
            ("spectral_rl_eta", pack_eta),
        ):
            bpm2 = _fuse_equal(pack["spectra"], ["remote", "local"], bf, cfg_bpm)
            e2 = _abs_err(bpm2, gt)
            if np.isfinite(e2):
                bpm_errs[label].append(e2)

        win_len = int(round(mp.window_length_sec * win["fs"]))
        t0, t1 = _ble_window_time_range(bundle["cs_t"], win["st"], win["end"], win["fs"], win_len)
        hkh_win = _hkh_window_bandpass(bundle["hkh_bp"], bundle["hkh_t"], t0, t1 + 1)
        if len(hkh_win) < 4:
            continue

        for wkey, qmode in (("wave_eta_rho", "eta_rho"), ("wave_eta", "eta")):
            bpm_psd, _diag, y = _window_b2_bpms(
                mc,
                win["seg_name"],
                win["ch_list"],
                win["st"],
                win["end"],
                win["fs"],
                cfg_eta,
                phase_method="hilbert",
                weight_mode="coherence_gated",
                modal_weight_mode="eta_coherence",
                use_two_level=True,
                use_modal_phase_align=True,
                f0=None,
                min_coherence=0.2,
                pca_top_k=36,
                return_waveform=True,
                quality_mode=qmode,
            )
            if y is None or len(y) < 4:
                continue
            rmse_val, _sign = window_rmse_against_reference(y, hkh_win)
            if np.isfinite(rmse_val):
                rmse_errs[wkey].append(float(rmse_val))
            bpm_out = estimate_bpm_from_waveform_multi(y, win["fs"], cfg=cfg_bpm)
            bpm_est = float(bpm_out.get("bpm_psd", bpm_psd))
            ae = _abs_err(bpm_est, gt)
            if np.isfinite(ae):
                bpm_errs[wkey].append(ae)

    methods = {}
    for k in keys:
        methods[k] = {
            "bpm_mean": _nanmean(bpm_errs[k]),
            "bpm_std": _nanstd(bpm_errs[k]),
            "bpm_n": len(bpm_errs[k]),
        }
        if k in rmse_errs:
            methods[k]["rmse_mean"] = _nanmean(rmse_errs[k])
            methods[k]["rmse_std"] = _nanstd(rmse_errs[k])
            methods[k]["rmse_n"] = len(rmse_errs[k])
    return {"scenario_id": bundle["scenario_id"], "methods": methods}


def run_quality_band_controlled() -> Tuple[Path, dict]:
    """HKH controlled matrix: highcut × (spectral/wave) × (η·ρ / η-only)."""
    by_hc: Dict[str, Any] = {}
    method_keys = (
        "spectral_eta_rho",
        "spectral_eta",
        "spectral_rl_eta_rho",
        "spectral_rl_eta",
        "wave_eta_rho",
        "wave_eta",
    )
    for hc in BAND_HIGHCUTS:
        print(f"  [quality_band/hkh] highcut={hc}")
        scen = []
        for sid in HKH_SCENARIO_IDS:
            print(f"    {sid}")
            bundle = _load_scenario_bundle(sid, "hkh", bandpass_highcut=hc, eta_breath_high=hc)
            scen.append(run_quality_band_controlled_scenario(bundle))
        methods = {}
        for key in method_keys:
            bpm_means = [s["methods"][key]["bpm_mean"] for s in scen]
            entry = {
                "bpm_cross_mean": _nanmean(bpm_means),
                "bpm_cross_std": _nanstd(bpm_means),
                "per_scenario_bpm": bpm_means,
            }
            if "rmse_mean" in scen[0]["methods"][key]:
                rmse_means = [s["methods"][key]["rmse_mean"] for s in scen]
                entry["rmse_cross_mean"] = _nanmean(rmse_means)
                entry["rmse_cross_std"] = _nanstd(rmse_means)
                entry["per_scenario_rmse"] = rmse_means
            methods[key] = entry
        by_hc[str(hc)] = {"methods": methods, "scenario_ids": [s["scenario_id"] for s in scen]}

    # deltas vs 0.35 within each method; gap wave vs spectral under same quality
    for hc, row in by_hc.items():
        m = row["methods"]
        for key in method_keys:
            base = by_hc["0.35"]["methods"][key]["bpm_cross_mean"]
            cur = m[key]["bpm_cross_mean"]
            m[key]["bpm_delta_vs_035"] = (
                (cur - base) if np.isfinite(cur) and np.isfinite(base) else float("nan")
            )
            if "rmse_cross_mean" in m[key]:
                rb = by_hc["0.35"]["methods"][key].get("rmse_cross_mean")
                rc = m[key]["rmse_cross_mean"]
                m[key]["rmse_delta_vs_035"] = (
                    (rc - rb) if np.isfinite(rc) and np.isfinite(rb) else float("nan")
                )
        for q in ("eta_rho", "eta"):
            w = m[f"wave_{q}"]["bpm_cross_mean"]
            s = m[f"spectral_{q}"]["bpm_cross_mean"]
            m[f"gap_wave_minus_spectral_{q}"] = (
                (w - s) if np.isfinite(w) and np.isfinite(s) else float("nan")
            )

    payload = {
        "domain": "hkh",
        "highcuts": list(BAND_HIGHCUTS),
        "factors": {
            "branch": ["spectral_3modal", "spectral_rl", "wave_b2d"],
            "quality": ["eta_rho", "eta"],
            "fixed": {
                "filter_and_eta_highcut": "synced (option A)",
                "bpm_search_hz": [BPM_SEARCH_LOW, BPM_SEARCH_HIGH],
                "window": "20s / 1s",
                "modal_fusion_spectral": "equal",
                "wave_pipeline": "B2-D two-level Hilbert-MRC",
            },
        },
        "by_highcut": by_hc,
        "note": (
            "Controlled follow-up: same windows/GT per highcut; cross branch × quality. "
            "Addresses whether η-only (vs η·ρ) changes the band-expanded wave≈spectral story."
        ),
    }
    out = REPORTS_DIR / "quality_band_controlled_hkh.json"
    path = _save_json(out, payload)
    print(f"  saved {path}")
    return path, payload


def plot_f7_quality_band(ctrl: dict) -> Path:
    xs = [float(k) for k in BAND_HIGHCUTS if str(k) in ctrl["by_highcut"]]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    # Left: BPM abs err curves
    ax = axes[0]
    series = [
        ("spectral_eta_rho", "Spectral 3-modal η·ρ", "#4C78A8", "-"),
        ("spectral_eta", "Spectral 3-modal η-only", "#4C78A8", "--"),
        ("wave_eta_rho", "Wave B2-D η·ρ", "#F58518", "-"),
        ("wave_eta", "Wave B2-D η-only", "#F58518", "--"),
        ("spectral_rl_eta", "Spectral R+L η-only", "#54A24B", ":"),
    ]
    for key, lab, color, ls in series:
        ys = [ctrl["by_highcut"][str(x)]["methods"][key]["bpm_cross_mean"] for x in xs]
        ax.plot(xs, ys, linestyle=ls, marker="o", color=color, label=lab)
    ax.set_xlabel("bandpass / η highcut (Hz)")
    ax.set_ylabel("HKH BPM abs err")
    ax.set_title("Controlled: branch × quality × highcut (BPM)")
    ax.legend(fontsize=7)

    # Right: Wave RMSE + gap wave−spectral
    ax = axes[1]
    for key, lab, color in (
        ("wave_eta_rho", "Wave RMSE η·ρ", "#4C78A8"),
        ("wave_eta", "Wave RMSE η-only", "#F58518"),
    ):
        ys = [ctrl["by_highcut"][str(x)]["methods"][key]["rmse_cross_mean"] for x in xs]
        ax.plot(xs, ys, marker="o", color=color, label=lab)
    ax.set_xlabel("bandpass / η highcut (Hz)")
    ax.set_ylabel("HKH Wave RMSE")
    ax2 = ax.twinx()
    for q, color, lab in (
        ("eta_rho", "#72B7B2", "gap Wave−Spectral (η·ρ)"),
        ("eta", "#E45756", "gap Wave−Spectral (η)"),
    ):
        gaps = [
            ctrl["by_highcut"][str(x)]["methods"][f"gap_wave_minus_spectral_{q}"] for x in xs
        ]
        ax2.plot(xs, gaps, "s--", color=color, label=lab)
    ax2.axhline(0.0, color="#888", lw=0.8)
    ax2.set_ylabel("Wave BPM − Spectral BPM (abs err)")
    ax.set_title("RMSE + Wave−Spectral BPM gap")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="best")
    fig.tight_layout()
    return _save_figure(fig, "gate_decomposition_figF7_quality_band_controlled")


def plot_f1_leaderboard(hkh: dict, cs: dict) -> Path:
    keys = _all_method_keys()
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=False)
    for ax, agg, title, xlab in (
        (axes[0], hkh, "HKH Gate decomposition", "BPM abs err"),
        (axes[1], cs, "CS Gate decomposition", "BPM rel err %"),
    ):
        rows = []
        for k in keys:
            m = agg["methods"].get(k)
            if not m or not np.isfinite(m["cross_mean"]):
                continue
            g = agg["gate"].get(k, {})
            rows.append(
                (
                    DESC_LABELS.get(k, k),
                    m["cross_mean"],
                    m.get("cross_std", 0.0) or 0.0,
                    g.get("open_ratio_mean", float("nan")),
                )
            )
        rows = sorted(rows, key=lambda r: r[1], reverse=True)
        y = np.arange(len(rows))
        colors = []
        for lab, *_ in rows:
            if lab.startswith("Gate-A"):
                colors.append("#F58518")
            elif lab.startswith("Gate-B"):
                colors.append("#54A24B")
            else:
                colors.append("#4C78A8")
        ax.barh(
            y,
            [r[1] for r in rows],
            xerr=[r[2] for r in rows],
            color=colors,
            alpha=0.9,
            capsize=2,
            ecolor="#444",
        )
        ax.set_yticks(y)
        ax.set_yticklabels(
            [f"{r[0]}  (open={r[3]*100:.1f}%)" if np.isfinite(r[3]) else r[0] for r in rows],
            fontsize=7,
        )
        ax.set_xlabel(xlab)
        ax.set_title(title)
        ax.invert_yaxis()
    fig.tight_layout()
    return _save_figure(fig, "gate_decomposition_figF1_hkh_bpm")


def plot_f2_open_ratio(hkh: dict, cs: dict) -> Path:
    # Focus on Gate-A k=1.0 and Gate-B δ sweep + baselines
    focus = [
        "b1_eta_only_rl",
        "b1_eta_gate_g3",
        _gate_a_key(1.0),
        _gate_a_key(1.05),
        _gate_a_key(1.1),
        *[_gate_b_key(d) for d in GATE_B_DELTAS],
        "b1_eta_3modal",
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, agg, title in ((axes[0], hkh, "HKH open ratio"), (axes[1], cs, "CS open ratio")):
        labs, vals = [], []
        for k in focus:
            labs.append(DESC_LABELS.get(k, k))
            vals.append(agg["gate"].get(k, {}).get("open_ratio_mean", float("nan")))
        x = np.arange(len(labs))
        ax.bar(x, [100.0 * v if np.isfinite(v) else 0 for v in vals], color="#72B7B2")
        ax.set_xticks(x)
        ax.set_xticklabels(labs, rotation=30, ha="right", fontsize=7)
        ax.set_ylabel("Phase-open %")
        ax.set_title(title)
        ax.set_ylim(0, 105)
    fig.tight_layout()
    return _save_figure(fig, "gate_decomposition_figF2_open_ratio")


def plot_f3_gate_quality(hkh: dict, cs: dict) -> Path:
    focus = [_gate_a_key(k) for k in GATE_A_KS] + [_gate_b_key(d) for d in GATE_B_DELTAS]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, agg, title, ylab in (
        (axes[0], hkh, "HKH open-window Phase err", "Phase BPM abs err"),
        (axes[1], cs, "CS open-window Phase err", "Phase BPM rel err %"),
    ):
        labs, vals = [], []
        for k in focus:
            labs.append(DESC_LABELS.get(k, k))
            vals.append(agg["gate"].get(k, {}).get("open_phase_err_mean", float("nan")))
        x = np.arange(len(labs))
        ax.bar(x, vals, color="#E45756")
        ax.set_xticks(x)
        ax.set_xticklabels(labs, rotation=30, ha="right", fontsize=7)
        ax.set_ylabel(ylab)
        ax.set_title(title)
    fig.tight_layout()
    return _save_figure(fig, "gate_decomposition_figF3_gate_quality")


def plot_f4_confusion(conf: dict) -> Path:
    modals = ("remote", "local", "phase")
    mat = np.zeros((3, 3))
    for i, ob in enumerate(modals):
        for j, sel in enumerate(modals):
            mat[i, j] = conf["matrix"][ob][sel]["n"]
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks(range(3))
    ax.set_yticks(range(3))
    ax.set_xticklabels([f"η→{m}" for m in modals])
    ax.set_yticklabels([f"oracle={m}" for m in modals])
    for i in range(3):
        for j in range(3):
            cell = conf["matrix"][modals[i]][modals[j]]
            ax.text(
                j,
                i,
                f"{int(mat[i,j])}\nΔ={cell['mean_cost_delta']:.2f}"
                if cell["mean_cost_delta"] is not None
                else f"{int(mat[i,j])}",
                ha="center",
                va="center",
                fontsize=8,
            )
    ax.set_title(
        f"η confusion (HKH) hit={conf['eta_top1_hit_rate']*100:.1f}% "
        f"high→Phase={conf['high_cost_to_phase_pct']:.1f}%"
    )
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    return _save_figure(fig, "gate_decomposition_figF4_eta_confusion")


def plot_f5_band(band: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, domain, ylab in (
        (axes[0], "hkh", "BreatheCS BPM abs err"),
        (axes[1], "cs", "BreatheCS BPM rel err %"),
    ):
        by_hc = band["domains"].get(domain, {})
        xs = [float(k) for k in BAND_HIGHCUTS if str(k) in by_hc]
        ys = [by_hc[str(x)]["cross_mean"] for x in xs]
        yerr = [by_hc[str(x)].get("cross_std", 0) or 0 for x in xs]
        hits = [by_hc[str(x)].get("eta_top1_hit_rate_mean", float("nan")) for x in xs]
        ax.errorbar(xs, ys, yerr=yerr, marker="o", color="#4C78A8", label="BPM err")
        ax.set_xlabel("bandpass / η highcut (Hz)")
        ax.set_ylabel(ylab)
        ax.set_title(f"{domain.upper()} band sweep")
        ax2 = ax.twinx()
        ax2.plot(xs, hits, "s--", color="#F58518", label="η hit rate")
        ax2.set_ylabel("η top-1 hit rate")
        ax2.set_ylim(0, 1)
    fig.tight_layout()
    return _save_figure(fig, "gate_decomposition_figF5_band_sweep")


def plot_all() -> List[Path]:
    hkh = json.loads((REPORTS_DIR / "gate_decomposition_hkh.json").read_text(encoding="utf-8"))[
        "aggregate"
    ]
    cs = json.loads((REPORTS_DIR / "gate_decomposition_cs.json").read_text(encoding="utf-8"))[
        "aggregate"
    ]
    conf = json.loads((REPORTS_DIR / "eta_confusion_matrix.json").read_text(encoding="utf-8"))
    band = json.loads((REPORTS_DIR / "breathing_band_sweep.json").read_text(encoding="utf-8"))
    paths = [
        plot_f1_leaderboard(hkh, cs),
        plot_f2_open_ratio(hkh, cs),
        plot_f3_gate_quality(hkh, cs),
        plot_f4_confusion(conf),
        plot_f5_band(band),
    ]
    wave_path = REPORTS_DIR / "breathing_band_wave_rmse_sweep.json"
    if wave_path.is_file():
        wave = json.loads(wave_path.read_text(encoding="utf-8"))
        paths.append(plot_f6_wave_band(wave))
    ctrl_path = REPORTS_DIR / "quality_band_controlled_hkh.json"
    if ctrl_path.is_file():
        ctrl = json.loads(ctrl_path.read_text(encoding="utf-8"))
        paths.append(plot_f7_quality_band(ctrl))
    return paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--part",
        choices=["all", "gate", "confusion", "band", "wave_band", "quality_band", "plot"],
        default="all",
    )
    parser.add_argument("--domain", choices=["all", "hkh", "cs"], default="all")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args()
    domains = ["hkh", "cs"] if args.domain == "all" else [args.domain]

    if args.plot_only or args.part == "plot":
        paths = plot_all()
        print("figures:", paths)
        return

    if args.part in ("all", "gate"):
        print("=== Part 1: Gate-A / Gate-B decomposition ===")
        run_gate_part(domains)

    if args.part in ("all", "confusion"):
        print("=== Part 3: η confusion matrix ===")
        run_confusion_part()

    if args.part in ("all", "band"):
        print("=== Part 4: breathing band sweep (stop if effective) ===")
        _, band = run_band_part(domains)
        if band.get("hkh_effective_highcuts"):
            print(
                "\n*** BAND LOOKS EFFECTIVE — STOPPING before full benchmark. "
                "Please review breathing_band_sweep.json / fig F5. ***\n"
            )

    if args.part == "wave_band":
        print("=== Follow-up: HKH waveform RMSE band sweep ===")
        _, wave = run_wave_band_part()
        fig = plot_f6_wave_band(wave)
        print("figure:", fig)

    if args.part == "quality_band":
        print("=== Follow-up: controlled quality × band × branch (HKH) ===")
        _, ctrl = run_quality_band_controlled()
        fig = plot_f7_quality_band(ctrl)
        print("figure:", fig)

    if args.part == "all":
        print("=== plots ===")
        paths = plot_all()
        print("figures:", paths)


if __name__ == "__main__":
    main()
