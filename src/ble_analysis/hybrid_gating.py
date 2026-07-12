"""Window-level B1+B2 hybrid BPM gating (post-hoc on B3 pipeline output).

Implements ``docs/plans/b1_b2_hybrid_gating_plan.md``.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np

ConsensusStrategy = Literal["b2", "mean", "b1", "b2_only"]

DEFAULT_THRESHOLDS: Tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)

__all__ = [
    "DEFAULT_THRESHOLDS",
    "apply_hybrid_gating",
    "evaluate_hybrid_gating_scan",
    "compute_gated_bpm_summary",
    "diagnose_consensus_windows",
    "diagnose_trigger_rate_by_group",
]


def apply_hybrid_gating(
    bpm_b1_per_window: np.ndarray,
    bpm_b2_per_window: np.ndarray,
    threshold: float = 1.0,
    consensus_strategy: ConsensusStrategy = "b2",
) -> dict:
    """Post-hoc window-level hybrid gating.

    When divergence > threshold, fallback to B1; otherwise use consensus strategy.

    Returns:
        bpm_final: gated BPM per window
        gate_triggered: bool — True when divergence exceeded threshold (B1 used)
        divergence: |bpm_b1 − bpm_b2| per window
    """
    bpm_b1 = np.asarray(bpm_b1_per_window, dtype=float)
    bpm_b2 = np.asarray(bpm_b2_per_window, dtype=float)
    divergence = np.abs(bpm_b1 - bpm_b2)
    gate_triggered = divergence > threshold

    if consensus_strategy == "b1":
        bpm_final = bpm_b1.copy()
    elif consensus_strategy == "b2_only":
        bpm_final = bpm_b2.copy()
    elif consensus_strategy == "b2":
        bpm_final = np.where(gate_triggered, bpm_b1, bpm_b2)
    elif consensus_strategy == "mean":
        consensus = (bpm_b1 + bpm_b2) / 2.0
        bpm_final = np.where(gate_triggered, bpm_b1, consensus)
    else:
        raise ValueError(f"Unknown consensus_strategy: {consensus_strategy}")

    return {
        "bpm_final": bpm_final,
        "gate_triggered": gate_triggered,
        "divergence": divergence,
        "threshold": float(threshold),
        "consensus_strategy": consensus_strategy,
    }


def compute_gated_bpm_summary(
    bpm_final: np.ndarray,
    bpm_gt: np.ndarray,
) -> dict:
    """Per-scenario BPM error summary for gated output."""
    bpm_final = np.asarray(bpm_final, dtype=float)
    bpm_gt = np.asarray(bpm_gt, dtype=float)
    valid = np.isfinite(bpm_final) & np.isfinite(bpm_gt) & (bpm_gt > 0)
    abs_err = np.where(valid, np.abs(bpm_final - bpm_gt), np.nan)
    rel_err = np.where(valid, abs_err / bpm_gt * 100.0, np.nan)
    return {
        "bpm_mean_abs_err": float(np.nanmean(abs_err)),
        "bpm_std_abs_err": float(np.nanstd(abs_err)),
        "bpm_mean_rel_err_pct": float(np.nanmean(rel_err)),
        "bpm_std_rel_err_pct": float(np.nanstd(rel_err)),
        "n_valid_bpm": int(np.sum(valid)),
        "bpm_abs_err": abs_err,
        "bpm_rel_err_pct": rel_err,
    }


def evaluate_hybrid_gating_scan(
    bpm_b1: np.ndarray,
    bpm_b2: np.ndarray,
    bpm_gt: np.ndarray,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    strategies: Sequence[ConsensusStrategy] = ("b2", "mean"),
) -> dict:
    """Scan thresholds and strategies; return per-config BPM error summaries."""
    bpm_b1 = np.asarray(bpm_b1, dtype=float)
    bpm_b2 = np.asarray(bpm_b2, dtype=float)
    bpm_gt = np.asarray(bpm_gt, dtype=float)

    results: Dict[str, dict] = {}

    for strategy in strategies:
        for threshold in thresholds:
            key = f"g_h{1 if strategy == 'b2' else 2}_t{threshold:.1f}".replace(".", "p")
            gated = apply_hybrid_gating(
                bpm_b1, bpm_b2, threshold=threshold, consensus_strategy=strategy
            )
            summary = compute_gated_bpm_summary(gated["bpm_final"], bpm_gt)
            trigger_rate = float(np.mean(gated["gate_triggered"]))
            results[key] = {
                "method_key": key,
                "label": (
                    f"G-H1 T={threshold:.1f}"
                    if strategy == "b2"
                    else f"G-H2 T={threshold:.1f}"
                ),
                "strategy": strategy,
                "threshold": float(threshold),
                "summary": summary,
                "trigger_rate": trigger_rate,
                "bpm_final": gated["bpm_final"],
                "gate_triggered": gated["gate_triggered"],
                "divergence": gated["divergence"],
            }

    for strategy, label, key in (
        ("b1", "G-H3 (always B1)", "g_h3"),
        ("b2_only", "G-H4 (always B2)", "g_h4"),
    ):
        gated = apply_hybrid_gating(
            bpm_b1, bpm_b2, threshold=0.0, consensus_strategy=strategy
        )
        summary = compute_gated_bpm_summary(gated["bpm_final"], bpm_gt)
        results[key] = {
            "method_key": key,
            "label": label,
            "strategy": strategy,
            "threshold": None,
            "summary": summary,
            "trigger_rate": float(np.mean(gated["gate_triggered"])),
            "bpm_final": gated["bpm_final"],
            "gate_triggered": gated["gate_triggered"],
            "divergence": gated["divergence"],
        }

    b1_summary = compute_gated_bpm_summary(bpm_b1, bpm_gt)
    b2_summary = compute_gated_bpm_summary(bpm_b2, bpm_gt)
    results["b1_ref"] = {
        "method_key": "b1_ref",
        "label": "B1 Vote→Equal",
        "summary": b1_summary,
        "bpm_final": bpm_b1,
    }
    results["b2_ref"] = {
        "method_key": "b2_ref",
        "label": "B2-D waveform PSD",
        "summary": b2_summary,
        "bpm_final": bpm_b2,
    }

    return results


def diagnose_consensus_windows(
    bpm_b1: np.ndarray,
    bpm_b2: np.ndarray,
    bpm_gt: np.ndarray,
    threshold: float,
) -> dict:
    """D1: consensus vs divergence window BPM error comparison."""
    bpm_b1 = np.asarray(bpm_b1, dtype=float)
    bpm_b2 = np.asarray(bpm_b2, dtype=float)
    bpm_gt = np.asarray(bpm_gt, dtype=float)
    divergence = np.abs(bpm_b1 - bpm_b2)
    consensus_mask = divergence <= threshold
    divergence_mask = divergence > threshold
    valid = np.isfinite(bpm_gt) & (bpm_gt > 0)

    def _mean_abs_err(bpm: np.ndarray, mask: np.ndarray) -> float:
        m = mask & valid & np.isfinite(bpm)
        if not np.any(m):
            return float("nan")
        return float(np.mean(np.abs(bpm[m] - bpm_gt[m])))

    return {
        "threshold": float(threshold),
        "n_consensus": int(np.sum(consensus_mask)),
        "n_divergence": int(np.sum(divergence_mask)),
        "consensus_b1_mean_abs_err": _mean_abs_err(bpm_b1, consensus_mask),
        "consensus_b2_mean_abs_err": _mean_abs_err(bpm_b2, consensus_mask),
        "divergence_b1_mean_abs_err": _mean_abs_err(bpm_b1, divergence_mask),
        "divergence_b2_mean_abs_err": _mean_abs_err(bpm_b2, divergence_mask),
    }


def diagnose_trigger_rate_by_group(
    divergence: np.ndarray,
    thresholds: Sequence[float],
    *,
    is_outlier: bool,
) -> List[dict]:
    """D2: gate trigger rate vs threshold for a scenario group."""
    divergence = np.asarray(divergence, dtype=float)
    rows: List[dict] = []
    for threshold in thresholds:
        triggered = divergence > threshold
        rows.append(
            {
                "threshold": float(threshold),
                "trigger_rate": float(np.mean(triggered)),
                "is_outlier_group": bool(is_outlier),
            }
        )
    return rows
