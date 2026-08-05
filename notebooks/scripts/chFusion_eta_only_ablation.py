"""η-only quality ablation + Phase η-BPM gate (paper ablation).

Plan: docs/plans/eta_only_ablation_plan.md

Run:
    python notebooks/scripts/chFusion_eta_only_ablation.py
    python notebooks/scripts/chFusion_eta_only_ablation.py --domain hkh --part all
    python notebooks/scripts/chFusion_eta_only_ablation.py --domain cs --part 1
    python notebooks/scripts/chFusion_eta_only_ablation.py --plot-only
"""

from __future__ import annotations

import argparse
import csv
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

from ble_analysis.b3_pipeline import (  # noqa: E402
    B3VariantConfig,
    DRAFT_ABLATION_SPECS,
    estimate_b3_window,
    validate_b3_variant_against_hkh,
)
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
from ble_analysis.coherent_mrc import estimate_b2_segment  # noqa: E402
from ble_analysis.scenarios import load_scenario  # noqa: E402
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices  # noqa: E402
from ble_analysis.systematic_fusion import modal_fusion_from_spectra  # noqa: E402
from ble_analysis.voting_fusion import VotingConfig  # noqa: E402
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

# Spectral draft keys that need η·ρ vs η pairing (paper §6.5 + single-modal)
SPECTRAL_DRAFT_KEYS = (
    "draft_s_none",
    "draft_s_channel",
    "draft_s_modal",
    "draft_s_full",
    "draft_ms_remote",
    "draft_ms_local",
    "draft_ms_phase",
)
WAVE_DRAFT_KEYS = (
    "draft_w_none",
    "draft_w_channel",
    "draft_w_modal",
    "draft_w_full",
    "draft_mw_remote",
    "draft_mw_local",
    "draft_mw_phase",
)

GATE_LEVELS = ("G0", "G1", "G2", "G3", "G4")
GATE_KEYS = {
    "G0": "b1_eta_only_rl",
    "G1": "b1_eta_gate_g1",
    "G2": "b1_eta_gate_g2",
    "G3": "b1_eta_gate_g3",
    "G4": "b1_eta_3modal",
}

DESC_LABELS = {
    "draft_s_full": "BreatheCS (Vote→3-modal equal)",
    "draft_s_full_eta": "BreatheCS η-only (Vote→3-modal equal)",
    "draft_s_none": "No fusion",
    "draft_s_none_eta": "No fusion η-only",
    "draft_s_channel": "Channel only",
    "draft_s_channel_eta": "Channel only η-only",
    "draft_s_modal": "Modal only",
    "draft_s_modal_eta": "Modal only η-only",
    "draft_ms_remote": "Remote only",
    "draft_ms_remote_eta": "Remote only η-only",
    "draft_ms_local": "Local only",
    "draft_ms_local_eta": "Local only η-only",
    "draft_ms_phase": "Phase only",
    "draft_ms_phase_eta": "Phase only η-only",
    "b3_b1_equal": "BreatheCS unified (B3)",
    "b3_b1_equal_eta": "BreatheCS unified η-only (B3)",
    "b2_d_two_level": "BreatheCS-Wave (B2-D)",
    "b2_d_two_level_eta": "BreatheCS-Wave η-only (B2-D)",
    "b1_eta_only_rl": "G0 R+L only (η-only tones)",
    "b1_eta_gate_g1": "G1 η-relaxed Phase gate",
    "b1_eta_gate_g2": "G2 η-strict Phase gate",
    "b1_eta_gate_g3": "G3 η+BPM Phase gate",
    "b1_eta_3modal": "G4-upper 3-modal always (η-only)",
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


def _draft_map() -> Dict[str, B3VariantConfig]:
    return {k: v for _l, k, v in DRAFT_ABLATION_SPECS}


def phase_gate_decision(
    eta_r: float,
    eta_l: float,
    eta_p: float,
    bpm_amp: float,
    bpm_phase: float,
    gate_level: str = "G3",
) -> Tuple[List[str], str]:
    """Return (modal short names, reject_reason). reason='' if open/always."""
    if gate_level == "G0":
        return ["remote", "local"], "g0_force_rl"
    if gate_level == "G4":
        return ["remote", "local", "phase"], ""

    if gate_level == "G1":
        if eta_p > float(np.median([eta_r, eta_l])):
            return ["remote", "local", "phase"], ""
        return ["remote", "local"], "eta_not_above_median"

    eta_ok = (eta_p > eta_r) and (eta_p > eta_l)
    if gate_level == "G2":
        if eta_ok:
            return ["remote", "local", "phase"], ""
        return ["remote", "local"], "eta_not_strict"

    # G3
    bpm_ok = abs(float(bpm_phase) - float(bpm_amp)) < 1.5
    if eta_ok and bpm_ok:
        return ["remote", "local", "phase"], ""
    if not eta_ok:
        return ["remote", "local"], "eta_not_strict"
    return ["remote", "local"], "bpm_mismatch"


def _bpm_from_spectrum(spec: np.ndarray, band_freqs: np.ndarray, eps: float = 1e-12) -> float:
    s = np.asarray(spec, dtype=float)
    if s.size == 0 or float(np.sum(s)) <= eps:
        return float("nan")
    k = int(np.argmax(s))
    f_peak = _parabolic_peak_freq(band_freqs, s, k, eps)
    return float(60.0 * f_peak)


def _fuse_equal(spectra: Dict[str, np.ndarray], keys: Sequence[str], band_freqs: np.ndarray, cfg: ChFusionConfig) -> float:
    use = {k: spectra[k] for k in keys if k in spectra and spectra[k] is not None}
    if not use:
        return float("nan")
    bpm, _ = modal_fusion_from_spectra(use, {k: 1.0 for k in use}, "equal", band_freqs, cfg)
    return float(bpm)


def _pick_best_modal(spectra: Dict[str, np.ndarray], scores: Dict[str, float], band_freqs: np.ndarray, cfg: ChFusionConfig) -> float:
    if not spectra:
        return float("nan")
    best = max(spectra.keys(), key=lambda k: scores.get(k, -np.inf))
    return _bpm_from_spectrum(spectra[best], band_freqs, cfg.eps)


def _abs_err(est: float, gt: float) -> float:
    if not (np.isfinite(est) and np.isfinite(gt) and gt > 0):
        return float("nan")
    return abs(float(est) - float(gt))


def _rel_err_pct(est: float, gt: float) -> float:
    if not (np.isfinite(est) and np.isfinite(gt) and gt > 0):
        return float("nan")
    return 100.0 * abs(float(est) - float(gt)) / float(gt)


def _nanmean(xs: Sequence[float]) -> float:
    arr = np.asarray(list(xs), dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.mean(arr)) if arr.size else float("nan")


def _nanstd(xs: Sequence[float]) -> float:
    arr = np.asarray(list(xs), dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.std(arr)) if arr.size else float("nan")


def _load_scenario_bundle(scenario_id: str, domain: str):
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
        band_mask = (freqs >= cfg.breath_freq_low) & (freqs <= cfg.breath_freq_high)
        band_freqs = freqs[band_mask]
        hann = np.hanning(win_len)

        for wi, st in enumerate(starts):
            end = st + win_len
            if domain == "hkh":
                t0, t1 = _ble_window_time_range(bundle["cs_t"], st, end, fs, win_len)
                hkh_win = _hkh_window_bandpass(bundle["hkh_bp"], bundle["hkh_t"], t0, t1 + 1)
                if len(hkh_win) < 4:
                    continue
                bpm_gt, _, _, _ = estimate_bpm_from_waveform(hkh_win, bundle["fs_hkh"], cfg=cfg)
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
    scores = {}
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
            return None
        spectra[m] = np.asarray(ws, dtype=float)
        # Channel-only pick_best uses voting confidence (winning mass), not mean η
        scores[m] = float(res.get("confidence", 0.0))
    return {"packs": packs, "spectra": spectra, "scores": scores}


ORACLE_SPEC = B3VariantConfig(
    use_voting=True,
    use_two_level_hilbert=False,
    modal_combine="fuse",
    bpm_source="spectral",
    modal_weight_mode="equal",
    tone_weight_mode="eta_rho",
)
ORACLE_SPEC_ETA = replace(ORACLE_SPEC, tone_weight_mode="eta")
NOFUSE_SPEC = B3VariantConfig(
    use_voting=False,
    use_two_level_hilbert=False,
    modal_combine="pick_best",
    bpm_source="spectral",
    tone_weight_mode="eta_rho",
)
NOFUSE_SPEC_ETA = replace(NOFUSE_SPEC, tone_weight_mode="eta")
MODAL_ONLY_SPEC = B3VariantConfig(
    use_voting=False,
    use_two_level_hilbert=False,
    modal_combine="fuse",
    bpm_source="spectral",
    tone_weight_mode="eta_rho",
)
MODAL_ONLY_SPEC_ETA = replace(MODAL_ONLY_SPEC, tone_weight_mode="eta")


def run_spectral_and_gate_for_scenario(bundle: dict) -> dict:
    """Part 1 spectral pairs + Part 2 gates for one scenario (window-level)."""
    cfg = bundle["cfg"]
    mc = bundle["mc"]
    domain = bundle["domain"]
    errs: Dict[str, List[float]] = defaultdict(list)
    rho_samples: Dict[str, List[float]] = defaultdict(list)
    gate_diag: Dict[str, Dict[str, Any]] = {
        g: {"open": 0, "total": 0, "reject": defaultdict(int), "open_phase_abs_err": []}
        for g in GATE_LEVELS
    }

    vcfg_rho = VotingConfig(voting_strategy="eta_rho_weighted")
    vcfg_eta = VotingConfig(voting_strategy="eta_weighted")

    n_win = 0
    for win in _iter_windows(bundle):
        n_win += 1
        common = dict(
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
        )
        out_rho = estimate_b3_window(**common, variant=ORACLE_SPEC, vcfg=vcfg_rho)
        out_eta = estimate_b3_window(**common, variant=ORACLE_SPEC_ETA, vcfg=vcfg_eta)
        pack_rho = _modal_pack_from_out(out_rho)
        pack_eta = _modal_pack_from_out(out_eta)
        if pack_rho is None or pack_eta is None:
            continue

        # No-fusion / modal-only need single-tone pick paths
        out_nf_rho = estimate_b3_window(**common, variant=NOFUSE_SPEC, vcfg=vcfg_rho)
        out_nf_eta = estimate_b3_window(**common, variant=NOFUSE_SPEC_ETA, vcfg=vcfg_eta)
        out_mo_rho = estimate_b3_window(**common, variant=MODAL_ONLY_SPEC, vcfg=vcfg_rho)
        out_mo_eta = estimate_b3_window(**common, variant=MODAL_ONLY_SPEC_ETA, vcfg=vcfg_eta)

        gt = win["bpm_gt"]
        bf = win["band_freqs"]
        err_fn = _abs_err if domain == "hkh" else _rel_err_pct

        # ρ diagnostic (η-only oracle packs still have mean_rho)
        for m in ("remote", "local", "phase"):
            rho_samples[m].append(pack_rho["packs"][m]["rho"])

        def _record(key: str, bpm: float):
            e = err_fn(bpm, gt)
            if np.isfinite(e):
                errs[key].append(e)

        # η·ρ spectral methods from voting packs
        sp_r, sc_r = pack_rho["spectra"], pack_rho["scores"]
        _record("draft_s_full", _fuse_equal(sp_r, ["remote", "local", "phase"], bf, cfg))
        _record("draft_s_channel", _pick_best_modal(sp_r, sc_r, bf, cfg))
        _record("draft_ms_remote", _bpm_from_spectrum(sp_r["remote"], bf, cfg.eps))
        _record("draft_ms_local", _bpm_from_spectrum(sp_r["local"], bf, cfg.eps))
        _record("draft_ms_phase", _bpm_from_spectrum(sp_r["phase"], bf, cfg.eps))

        # η-only spectral methods from voting packs
        sp_e, sc_e = pack_eta["spectra"], pack_eta["scores"]
        _record("draft_s_full_eta", _fuse_equal(sp_e, ["remote", "local", "phase"], bf, cfg))
        _record("draft_s_channel_eta", _pick_best_modal(sp_e, sc_e, bf, cfg))
        _record("draft_ms_remote_eta", _bpm_from_spectrum(sp_e["remote"], bf, cfg.eps))
        _record("draft_ms_local_eta", _bpm_from_spectrum(sp_e["local"], bf, cfg.eps))
        _record("draft_ms_phase_eta", _bpm_from_spectrum(sp_e["phase"], bf, cfg.eps))

        # No-fusion / modal-only from dedicated outs
        _record("draft_s_none", float(out_nf_rho.get("bpm", float("nan"))))
        _record("draft_s_none_eta", float(out_nf_eta.get("bpm", float("nan"))))
        _record("draft_s_modal", float(out_mo_rho.get("bpm", float("nan"))))
        _record("draft_s_modal_eta", float(out_mo_eta.get("bpm", float("nan"))))

        # Part 2 gates on η-only packs
        eta_r = pack_eta["packs"]["remote"]["eta"]
        eta_l = pack_eta["packs"]["local"]["eta"]
        eta_p = pack_eta["packs"]["phase"]["eta"]
        bpm_amp = _fuse_equal(sp_e, ["remote", "local"], bf, cfg)
        bpm_phase = _bpm_from_spectrum(sp_e["phase"], bf, cfg.eps)
        for g in GATE_LEVELS:
            mods, reason = phase_gate_decision(eta_r, eta_l, eta_p, bpm_amp, bpm_phase, g)
            bpm_g = _fuse_equal(sp_e, mods, bf, cfg)
            key = GATE_KEYS[g]
            _record(key, bpm_g)
            gate_diag[g]["total"] += 1
            if "phase" in mods:
                gate_diag[g]["open"] += 1
                pe = _abs_err(bpm_phase, gt) if domain == "hkh" else _rel_err_pct(bpm_phase, gt)
                if np.isfinite(pe):
                    gate_diag[g]["open_phase_abs_err"].append(pe)
            elif reason:
                gate_diag[g]["reject"][reason] += 1

    method_summary = {}
    for k, vals in errs.items():
        method_summary[k] = {
            "label": DESC_LABELS.get(k, k),
            "mean": _nanmean(vals),
            "std": _nanstd(vals),
            "n": int(np.sum(np.isfinite(vals))),
        }

    gate_summary = {}
    for g in GATE_LEVELS:
        tot = max(gate_diag[g]["total"], 1)
        gate_summary[g] = {
            "key": GATE_KEYS[g],
            "open_ratio": gate_diag[g]["open"] / tot,
            "n_total": gate_diag[g]["total"],
            "n_open": gate_diag[g]["open"],
            "reject": dict(gate_diag[g]["reject"]),
            "open_phase_err_mean": _nanmean(gate_diag[g]["open_phase_abs_err"]),
        }

    rho_summary = {
        m: {"mean": _nanmean(v), "std": _nanstd(v), "n": len(v)} for m, v in rho_samples.items()
    }
    return {
        "scenario_id": bundle["scenario_id"],
        "domain": domain,
        "n_windows": n_win,
        "methods": method_summary,
        "gate": gate_summary,
        "rho": rho_summary,
        "metric": "bpm_abs_err" if domain == "hkh" else "bpm_rel_err_pct",
    }


def run_b2_for_scenario(bundle: dict) -> dict:
    """B2-D η·ρ vs η-only. CS uses segment GT; HKH uses belt GT per window."""
    from ble_analysis.coherent_mrc import _window_b2_bpms

    mc = bundle["mc"]
    cfg = bundle["cfg"]
    mp = bundle["mp"]
    domain = bundle["domain"]
    errs = {"b2_d_two_level": [], "b2_d_two_level_eta": []}

    if domain == "cs":
        for seg_name, ref_seg in mc.get("phases", {}).items():
            if ref_seg is None:
                continue
            meta = ref_seg.get("metadata", {})
            if meta.get("type") == "apnea" or meta.get("segment_type") == "apnea":
                continue
            row = estimate_b2_segment(
                mc,
                seg_name,
                methods=["b2_d_two_level", "b2_d_two_level_eta"],
                config=cfg,
                metric_params=mp,
                verbose=False,
            )
            if row is None:
                continue
            for k in errs:
                stats = row.get(k)
                if not stats:
                    continue
                # bpm_rel_err is fraction; convert to %
                v = stats.get("bpm_rel_err")
                if v is not None and np.isfinite(float(v)):
                    errs[k].append(100.0 * float(v))
        return {
            k: {"label": DESC_LABELS.get(k, k), "mean": _nanmean(v), "std": _nanstd(v), "n": len(v)}
            for k, v in errs.items()
        }

    # HKH: window-level vs belt
    configs = {
        "b2_d_two_level": {"quality_mode": "eta_rho"},
        "b2_d_two_level_eta": {"quality_mode": "eta"},
    }
    for win in _iter_windows(bundle):
        gt = win["bpm_gt"]
        for k, kw in configs.items():
            bpm, _diag = _window_b2_bpms(
                mc,
                win["seg_name"],
                win["ch_list"],
                win["st"],
                win["end"],
                win["fs"],
                cfg,
                phase_method="hilbert",
                weight_mode="coherence_gated",
                modal_weight_mode="eta_coherence",
                use_two_level=True,
                use_modal_phase_align=True,
                f0=None,
                min_coherence=0.2,
                pca_top_k=36,
                quality_mode=kw["quality_mode"],
            )
            ae = _abs_err(float(bpm), gt)
            if np.isfinite(ae):
                errs[k].append(ae)

    return {
        k: {"label": DESC_LABELS.get(k, k), "mean": _nanmean(v), "std": _nanstd(v), "n": len(v)}
        for k, v in errs.items()
    }


def run_hkh_wave_and_b3(scenario_ids: Sequence[str], *, skip_wave: bool = False) -> dict:
    """HKH waveform ablation + B3 unified via validate_b3_variant_against_hkh."""
    draft = _draft_map()
    jobs: List[Tuple[str, B3VariantConfig]] = []
    # B3 simplified (defaults = BreatheCS unified)
    jobs.append(("b3_b1_equal", B3VariantConfig(tone_weight_mode="eta_rho")))
    jobs.append(("b3_b1_equal_eta", B3VariantConfig(tone_weight_mode="eta")))

    if not skip_wave:
        for key in WAVE_DRAFT_KEYS:
            base = draft[key]
            jobs.append((key, replace(base, tone_weight_mode="eta_rho")))
            jobs.append((f"{key}_eta", replace(base, tone_weight_mode="eta")))

    per_method: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: {"bpm": [], "rmse": []})

    for sid in scenario_ids:
        print(f"  [HKH wave/B3] {sid}")
        bundle = _load_scenario_bundle(sid, "hkh")
        mc = bundle["mc"]
        cfg = bundle["cfg"]
        mp = bundle["mp"]
        for seg_name, ref_seg in mc.get("phases", {}).items():
            if ref_seg is None:
                continue
            meta = ref_seg.get("metadata", {})
            if meta.get("type") == "apnea" or meta.get("segment_type") == "apnea":
                continue
            for key, variant in jobs:
                res = validate_b3_variant_against_hkh(
                    mc,
                    seg_name,
                    bundle["hkh_bp"],
                    bundle["hkh_t"],
                    bundle["cs_t"],
                    variant_key=key,
                    variant=variant,
                    config=cfg,
                    metric_params=mp,
                    fs_hkh_override=bundle["fs_hkh"],
                    verbose=False,
                )
                if res is None:
                    continue
                bpm_mean = res.get("summary", {}).get("bpm_mean_abs_err")
                rmse_mean = res.get("summary", {}).get("rmse_mean")
                if bpm_mean is not None and np.isfinite(float(bpm_mean)):
                    per_method[key]["bpm"].append(float(bpm_mean))
                if rmse_mean is not None and np.isfinite(float(rmse_mean)):
                    per_method[key]["rmse"].append(float(rmse_mean))

    out = {}
    for key, vals in per_method.items():
        out[key] = {
            "label": DESC_LABELS.get(key, key),
            "bpm_mean": _nanmean(vals["bpm"]),
            "bpm_std": _nanstd(vals["bpm"]),
            "rmse_mean": _nanmean(vals["rmse"]),
            "rmse_std": _nanstd(vals["rmse"]),
            "n_segments": len(vals["bpm"]),
        }
    return out


def aggregate_domain(scenario_results: List[dict]) -> dict:
    keys = set()
    for r in scenario_results:
        keys.update(r["methods"].keys())
    methods = {}
    for k in sorted(keys):
        means = [r["methods"][k]["mean"] for r in scenario_results if k in r["methods"]]
        methods[k] = {
            "label": DESC_LABELS.get(k, k),
            "per_scenario_mean": means,
            "cross_mean": _nanmean(means),
            "cross_std": _nanstd(means),
        }
    gate = {}
    for g in GATE_LEVELS:
        ratios = [r["gate"][g]["open_ratio"] for r in scenario_results if g in r.get("gate", {})]
        open_err = [
            r["gate"][g]["open_phase_err_mean"]
            for r in scenario_results
            if g in r.get("gate", {})
        ]
        gate[g] = {
            "key": GATE_KEYS[g],
            "open_ratio_mean": _nanmean(ratios),
            "open_phase_err_mean": _nanmean(open_err),
            "per_scenario_open_ratio": ratios,
        }
    rho = {}
    for m in ("remote", "local", "phase"):
        means = [r["rho"][m]["mean"] for r in scenario_results if m in r.get("rho", {})]
        rho[m] = {"mean": _nanmean(means), "per_scenario": means}
    return {
        "n_scenarios": len(scenario_results),
        "metric": scenario_results[0]["metric"] if scenario_results else None,
        "methods": methods,
        "gate": gate,
        "rho": rho,
        "per_scenario": scenario_results,
    }


def build_delta_table(agg: dict, pairs: Sequence[Tuple[str, str]]) -> List[dict]:
    rows = []
    methods = agg["methods"]
    for base, eta_key in pairs:
        if base not in methods or eta_key not in methods:
            continue
        b = methods[base]["cross_mean"]
        e = methods[eta_key]["cross_mean"]
        rows.append(
            {
                "base": base,
                "eta": eta_key,
                "label": DESC_LABELS.get(base, base),
                "base_mean": b,
                "eta_mean": e,
                "delta_eta_minus_base": (e - b) if np.isfinite(e) and np.isfinite(b) else float("nan"),
            }
        )
    return rows


SPECTRAL_PAIRS = [
    ("draft_s_full", "draft_s_full_eta"),
    ("draft_s_none", "draft_s_none_eta"),
    ("draft_s_channel", "draft_s_channel_eta"),
    ("draft_s_modal", "draft_s_modal_eta"),
    ("draft_ms_remote", "draft_ms_remote_eta"),
    ("draft_ms_local", "draft_ms_local_eta"),
    ("draft_ms_phase", "draft_ms_phase_eta"),
    ("b2_d_two_level", "b2_d_two_level_eta"),
    ("b3_b1_equal", "b3_b1_equal_eta"),
]


def plot_hkh_leaderboard(hkh_agg: dict, gate_keys: Sequence[str], path_stem: str) -> Path:
    rows = []
    for base, eta_key in SPECTRAL_PAIRS[:7]:  # spectral + breathecs
        if base in hkh_agg["methods"]:
            rows.append((DESC_LABELS.get(base, base) + " [η·ρ]", hkh_agg["methods"][base]["cross_mean"], "#4C78A8"))
        if eta_key in hkh_agg["methods"]:
            rows.append((DESC_LABELS.get(eta_key, eta_key), hkh_agg["methods"][eta_key]["cross_mean"], "#F58518"))
    for g in ("G0", "G3", "G4"):
        k = GATE_KEYS[g]
        if k in hkh_agg["methods"]:
            rows.append((DESC_LABELS[k], hkh_agg["methods"][k]["cross_mean"], "#54A24B"))
    rows = [(l, v, c) for l, v, c in rows if np.isfinite(v)]
    rows = sorted(rows, key=lambda x: x[1], reverse=True)
    fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(rows))))
    y = np.arange(len(rows))
    ax.barh(y, [r[1] for r in rows], color=[r[2] for r in rows], alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlabel("HKH mean BPM abs err")
    ax.set_title("η-only ablation + Phase gate (HKH)")
    ax.invert_yaxis()
    fig.tight_layout()
    return _save_figure(fig, path_stem)


def plot_ablation_bars(hkh_agg: dict, path_stem: str) -> Path:
    names = ["No fusion", "Channel only", "Modal only", "BreatheCS", "Remote", "Local", "Phase"]
    bases = [
        "draft_s_none",
        "draft_s_channel",
        "draft_s_modal",
        "draft_s_full",
        "draft_ms_remote",
        "draft_ms_local",
        "draft_ms_phase",
    ]
    etas = [b + "_eta" for b in bases]
    x = np.arange(len(names))
    w = 0.35
    bvals = [hkh_agg["methods"].get(k, {}).get("cross_mean", np.nan) for k in bases]
    evals = [hkh_agg["methods"].get(k, {}).get("cross_mean", np.nan) for k in etas]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(x - w / 2, bvals, w, label="η·ρ", color="#4C78A8")
    ax.bar(x + w / 2, evals, w, label="η-only", color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.set_ylabel("HKH BPM abs err")
    ax.set_title("HKH spectral ablation: η·ρ vs η-only")
    ax.legend()
    fig.tight_layout()
    return _save_figure(fig, path_stem)


def plot_cs_leaderboard(cs_agg: dict, path_stem: str) -> Path:
    pairs = SPECTRAL_PAIRS[:7]
    labels, bvals, evals = [], [], []
    for b, e in pairs:
        if b not in cs_agg["methods"]:
            continue
        labels.append(DESC_LABELS.get(b, b))
        bvals.append(cs_agg["methods"][b]["cross_mean"])
        evals.append(cs_agg["methods"].get(e, {}).get("cross_mean", np.nan))
    x = np.arange(len(labels))
    w = 0.35
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(x - w / 2, bvals, w, label="η·ρ", color="#4C78A8")
    ax.bar(x + w / 2, evals, w, label="η-only", color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("CS mean BPM rel err %")
    ax.set_title("CS metal-plate reference: η·ρ vs η-only")
    ax.legend()
    fig.tight_layout()
    return _save_figure(fig, path_stem)


def plot_rho_dist(hkh_agg: dict, cs_agg: dict, path_stem: str) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    mods = ["remote", "local", "phase"]
    x = np.arange(len(mods))
    hkh_v = [hkh_agg["rho"].get(m, {}).get("mean", np.nan) for m in mods]
    cs_v = [cs_agg["rho"].get(m, {}).get("mean", np.nan) for m in mods]
    ax.bar(x - 0.2, cs_v, 0.4, label="CS (metal)", color="#4C78A8")
    ax.bar(x + 0.2, hkh_v, 0.4, label="HKH (human)", color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(mods)
    ax.set_ylabel("mean ρ (window-level)")
    ax.set_title("ρ scale: CS vs HKH")
    ax.legend()
    fig.tight_layout()
    return _save_figure(fig, path_stem)


def plot_gate_behavior(hkh_agg: dict, cs_agg: dict, path_stem: str) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    gs = list(GATE_LEVELS)
    for ax, agg, title in (
        (axes[0], hkh_agg, "HKH"),
        (axes[1], cs_agg, "CS"),
    ):
        ratios = [agg["gate"][g]["open_ratio_mean"] for g in gs]
        ax.bar(gs, ratios, color="#54A24B", alpha=0.85)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Phase gate open ratio")
        ax.set_title(f"Gate open ratio — {title}")
    fig.tight_layout()
    return _save_figure(fig, path_stem)


def load_external_baselines_hkh() -> dict:
    """Reuse prior same-pipeline paper baseline summary (quality metric unchanged)."""
    path = REPORTS_DIR / "ble_hkh_paper_baselines_summary.json"
    if not path.exists():
        return {"available": False, "path": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"available": True, "path": str(path), "data": data}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["hkh", "cs", "all"], default="all")
    parser.add_argument("--part", choices=["1", "2", "all"], default="all")
    parser.add_argument("--skip-wave", action="store_true", help="Skip HKH waveform/B3 validate pass")
    parser.add_argument("--skip-b2", action="store_true")
    parser.add_argument("--plot-only", action="store_true")
    parser.add_argument("--max-hkh", type=int, default=0, help="Debug: limit HKH scenarios (0=all)")
    parser.add_argument("--max-cs", type=int, default=0, help="Debug: limit CS scenarios (0=all)")
    args = parser.parse_args()

    hkh_ids = HKH_SCENARIO_IDS[: args.max_hkh] if args.max_hkh > 0 else HKH_SCENARIO_IDS
    cs_ids = CS_SCENARIO_IDS[: args.max_cs] if args.max_cs > 0 else CS_SCENARIO_IDS

    hkh_sum_path = REPORTS_DIR / "eta_only_ablation_hkh_leaderboard.json"
    cs_sum_path = REPORTS_DIR / "eta_only_ablation_cs_leaderboard.json"
    abl_path = REPORTS_DIR / "eta_only_ablation_hkh_ablation.json"
    gate_path = REPORTS_DIR / "eta_only_ablation_phase_gate.json"
    delta_path = REPORTS_DIR / "eta_only_ablation_delta.csv"

    if args.plot_only:
        hkh_agg = json.loads(hkh_sum_path.read_text(encoding="utf-8"))
        cs_agg = json.loads(cs_sum_path.read_text(encoding="utf-8"))
        plot_hkh_leaderboard(hkh_agg, GATE_KEYS, "eta_only_ablation_figG1_hkh_leaderboard")
        plot_ablation_bars(hkh_agg, "eta_only_ablation_figG2_hkh_ablation")
        plot_cs_leaderboard(cs_agg, "eta_only_ablation_figG3_cs_leaderboard")
        plot_rho_dist(hkh_agg, cs_agg, "eta_only_ablation_figG4_rho_distribution")
        plot_gate_behavior(hkh_agg, cs_agg, "eta_only_ablation_figG5_gate_behavior")
        print("Replotted figures.")
        return

    hkh_results: List[dict] = []
    cs_results: List[dict] = []
    hkh_wave = {}
    external = load_external_baselines_hkh()

    if args.domain in ("hkh", "all"):
        print("=== HKH spectral + gate ===")
        for sid in hkh_ids:
            print(f"  [HKH] {sid}")
            bundle = _load_scenario_bundle(sid, "hkh")
            res = run_spectral_and_gate_for_scenario(bundle)
            if not args.skip_b2:
                b2 = run_b2_for_scenario(bundle)
                res["methods"].update(b2)
            hkh_results.append(res)
        if not args.skip_wave:
            print("=== HKH waveform / B3 ===")
            hkh_wave = run_hkh_wave_and_b3(hkh_ids, skip_wave=False)

    if args.domain in ("cs", "all"):
        print("=== CS spectral + gate (reference) ===")
        for sid in cs_ids:
            print(f"  [CS] {sid}")
            bundle = _load_scenario_bundle(sid, "cs")
            res = run_spectral_and_gate_for_scenario(bundle)
            if not args.skip_b2:
                b2 = run_b2_for_scenario(bundle)
                res["methods"].update(b2)
            cs_results.append(res)

    hkh_agg = aggregate_domain(hkh_results) if hkh_results else {}
    cs_agg = aggregate_domain(cs_results) if cs_results else {}

    # Merge B3 / wave means into HKH agg methods
    if args.skip_wave and hkh_sum_path.exists():
        prev = json.loads(hkh_sum_path.read_text(encoding="utf-8"))
        for k, v in prev.get("methods", {}).items():
            if k.startswith("draft_w") or k.startswith("draft_mw") or k.startswith("b3_"):
                hkh_wave.setdefault(k, {
                    "label": v.get("label", k),
                    "bpm_mean": v.get("cross_mean"),
                    "bpm_std": v.get("cross_std"),
                    "rmse_mean": v.get("rmse_mean"),
                    "rmse_std": v.get("rmse_std"),
                    "n_segments": v.get("n_segments", 0),
                })

    for k, v in hkh_wave.items():
        hkh_agg.setdefault("methods", {})[k] = {
            "label": v.get("label", DESC_LABELS.get(k, k)),
            "per_scenario_mean": [],
            "cross_mean": v["bpm_mean"],
            "cross_std": v.get("bpm_std"),
            "rmse_mean": v.get("rmse_mean"),
            "rmse_std": v.get("rmse_std"),
            "n_segments": v.get("n_segments"),
            "source": "validate_b3_variant_against_hkh",
        }

    if hkh_agg:
        _save_json(hkh_sum_path, {**hkh_agg, "external_baselines": external})
        abl = {
            "spectral_pairs": build_delta_table(hkh_agg, SPECTRAL_PAIRS),
            "wave_methods": {k: v for k, v in hkh_wave.items() if k.startswith("draft_w") or k.startswith("draft_mw")},
            "note": "HKH primary; CS in separate file as reference appendix",
        }
        _save_json(abl_path, abl)
        gate_payload = {
            "hkh": hkh_agg.get("gate", {}),
            "methods_hkh": {GATE_KEYS[g]: hkh_agg["methods"].get(GATE_KEYS[g]) for g in GATE_LEVELS},
            "cs": cs_agg.get("gate", {}) if cs_agg else {},
            "methods_cs": (
                {GATE_KEYS[g]: cs_agg["methods"].get(GATE_KEYS[g]) for g in GATE_LEVELS} if cs_agg else {}
            ),
        }
        _save_json(gate_path, gate_payload)

        # delta csv
        with delta_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["domain", "base", "eta", "label", "base_mean", "eta_mean", "delta_eta_minus_base"],
            )
            w.writeheader()
            for row in build_delta_table(hkh_agg, SPECTRAL_PAIRS):
                w.writerow({"domain": "hkh", **row})
            if cs_agg:
                for row in build_delta_table(cs_agg, SPECTRAL_PAIRS):
                    w.writerow({"domain": "cs", **row})

        plot_hkh_leaderboard(hkh_agg, GATE_KEYS, "eta_only_ablation_figG1_hkh_leaderboard")
        plot_ablation_bars(hkh_agg, "eta_only_ablation_figG2_hkh_ablation")
        plot_rho_dist(hkh_agg, cs_agg if cs_agg else {"rho": {}}, "eta_only_ablation_figG4_rho_distribution")
        if cs_agg:
            plot_gate_behavior(hkh_agg, cs_agg, "eta_only_ablation_figG5_gate_behavior")

    if cs_agg:
        _save_json(cs_sum_path, cs_agg)
        plot_cs_leaderboard(cs_agg, "eta_only_ablation_figG3_cs_leaderboard")

    print("Done.")
    if hkh_agg and "draft_s_full" in hkh_agg["methods"]:
        b = hkh_agg["methods"]["draft_s_full"]["cross_mean"]
        e = hkh_agg["methods"].get("draft_s_full_eta", {}).get("cross_mean", float("nan"))
        print(f"HKH BreatheCS η·ρ={b:.4f}  η-only={e:.4f}  Δ={e - b:+.4f}")
    if hkh_agg:
        for g in GATE_LEVELS:
            k = GATE_KEYS[g]
            m = hkh_agg["methods"].get(k, {})
            print(f"  {g} {k}: {m.get('cross_mean', float('nan')):.4f}  open={hkh_agg['gate'][g]['open_ratio_mean']:.3f}")


if __name__ == "__main__":
    main()
