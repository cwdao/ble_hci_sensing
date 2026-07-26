"""Phase adaptive gating (E2/E3) — simplified variants for Phase Plan v2.0.

D1=C → at most 2–3 variants; thresholds via leave-one-subject-out.
Also: confidence gate for unified Amplitude-only vs Phase-gated pipeline.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Set, Tuple

import numpy as np


def gate_by_confidence(
    conf_per_modal: Mapping[str, float],
    theta_conf: float = 0.35,
) -> Set[str]:
    """Return active modal short-names under Phase confidence gate.

    Always keeps Remote/Local. Adds Phase only when ``conf_P >= theta_conf``.
    ``theta_conf=+inf`` never includes Phase (Candidate A).
    """
    active: Set[str] = {"R", "L"}
    # Accept both short keys used in packs ("phase") and plan keys ("P")
    conf_p = float(
        conf_per_modal.get(
            "P",
            conf_per_modal.get("phase", 0.0),
        )
    )
    if np.isfinite(theta_conf) and conf_p >= float(theta_conf):
        active.add("P")
    return active


def active_modals_to_spectrum_keys(active: Set[str]) -> Set[str]:
    """Map {R,L,P} → {remote,local,phase} for spectrum dict keys."""
    mapping = {"R": "remote", "L": "local", "P": "phase"}
    return {mapping[k] for k in active if k in mapping}


def classify_window_condition(
    bpm_r: float,
    bpm_l: float,
    bpm_p: float,
    eta_r: float,
    eta_l: float,
    eta_p: float,
    conf_r: float,
    conf_l: float,
    conf_p: float,
    *,
    eta_med_r: float,
    eta_med_l: float,
    conf_med_r: float,
    conf_med_l: float,
    t_agree: float = 1.0,
    conf_p_min: float = 0.0,
) -> str:
    """Return ``A`` (agree high-quality), ``B`` (disagree), or ``C`` (both weak)."""
    _ = (bpm_p, eta_p)  # reserved for stricter C checks
    agree = abs(float(bpm_r) - float(bpm_l)) <= float(t_agree)
    high_r = float(eta_r) >= float(eta_med_r) and float(conf_r) >= float(conf_med_r)
    high_l = float(eta_l) >= float(eta_med_l) and float(conf_l) >= float(conf_med_l)
    weak_r = float(eta_r) < float(eta_med_r)
    weak_l = float(eta_l) < float(eta_med_l)

    if agree and high_r and high_l:
        return "A"
    if (not agree) and float(conf_p) >= float(conf_p_min):
        return "B"
    if weak_r and weak_l:
        return "C"
    # fallback: treat residual as B if disagree else A
    return "B" if not agree else "A"


def weights_for_policy(
    policy: str,
    condition: str,
    bpm_r: float,
    bpm_l: float,
    bpm_p: float,
    *,
    q_amp: float,
    theta_c1: float = 0.5,
    theta_disagree: float = 1.0,
    theta_agree: float = 1.0,
    eta_r: float = 0.0,
    eta_l: float = 0.0,
    eta_p: float = 0.0,
    conf_p: float = 0.0,
    conf_med_rl: float = 0.0,
) -> Tuple[Dict[str, float], str]:
    """Return modal weights and a short action tag.

    Policies (simplified D1=C set):
      - ``e3_default`` / ``p0_rl_default``: always R+L
      - ``e2_tiebreak``: A→R+L; B→tie-break; C→R+L
      - ``e3_conditional``: activate Phase on C1 (q_amp low) or C2 (disagree+near one)
    """
    if policy in ("e3_default", "p0_rl_default", "rl_default"):
        return {"remote": 0.5, "local": 0.5, "phase": 0.0}, "rl_default"

    if policy == "e2_tiebreak":
        if condition == "A":
            return {"remote": 0.5, "local": 0.5, "phase": 0.0}, "A_rl"
        if condition == "B":
            if abs(bpm_p - bpm_r) <= abs(bpm_p - bpm_l):
                return {"remote": 0.5, "local": 0.0, "phase": 0.5}, "B_rp"
            return {"remote": 0.0, "local": 0.5, "phase": 0.5}, "B_lp"
        # C → R+L fallback (strict rescue deferred)
        return {"remote": 0.5, "local": 0.5, "phase": 0.0}, "C_rl_fallback"

    if policy == "e2_rescue":
        if condition == "A":
            return {"remote": 0.5, "local": 0.5, "phase": 0.0}, "A_rl"
        if condition == "B":
            if abs(bpm_p - bpm_r) <= abs(bpm_p - bpm_l):
                return {"remote": 0.5, "local": 0.0, "phase": 0.5}, "B_rp"
            return {"remote": 0.0, "local": 0.5, "phase": 0.5}, "B_lp"
        # C: Phase takeover only if conf_p is not below median of R/L confs
        if conf_p >= conf_med_rl:
            return {"remote": 0.0, "local": 0.0, "phase": 1.0}, "C_phase"
        return {"remote": 0.5, "local": 0.5, "phase": 0.0}, "C_rl_fallback"

    if policy == "e3_conditional":
        c1 = float(q_amp) < float(theta_c1)
        disagree = abs(bpm_r - bpm_l) > float(theta_disagree)
        near = abs(bpm_p - bpm_r) <= float(theta_agree) or abs(bpm_p - bpm_l) <= float(theta_agree)
        c2 = disagree and near
        if c1 or c2:
            return {"remote": 1.0, "local": 1.0, "phase": 1.0}, "phase_on"
        return {"remote": 0.5, "local": 0.5, "phase": 0.0}, "phase_off"

    raise ValueError(f"Unknown policy: {policy}")
