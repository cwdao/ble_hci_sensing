"""Multi-algorithm validation on BLE+HKH live breathing data."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ble_analysis.ble_hkh_validation import (
    compute_hkh_gt_per_window,
    extract_bpm_per_window,
    summarize_bpm_vs_hkh,
    validate_b2_against_hkh,
)
from ble_analysis.chfusion import (
    ChFusionConfig,
    MODAL_FUSION_METHOD_LABELS,
    Plan2Config,
    _MODAL_FUSION_WEIGHT_MODES,
    estimate_modal_best_channel_fusion,
    estimate_segment_bpm_methods,
)
from ble_analysis.coherent_mrc import B2_ALL_SPECS
from ble_analysis.segments import BreathMetricParams
from ble_analysis.systematic_fusion import (
    SYSTEMATIC_NEW_METHOD_SPECS,
    estimate_systematic_fusion_segment,
)
from ble_analysis.voting_fusion import VOTING_METHOD_SPECS, VotingConfig, estimate_voting_segment_methods

B2_PRIMARY_KEYS = ("b2_d_two_level", "b2_b_hilbert", "b2_a0_pca_sign")


def _run_systematic(
    multichannel_by_var,
    seg_name: str,
    channel_strategy: str,
    modal_strategy: str,
    *,
    config: ChFusionConfig,
    metric_params: BreathMetricParams,
) -> Optional[np.ndarray]:
    vcfg = VotingConfig(voting_strategy="eta_rho_weighted")
    row = estimate_systematic_fusion_segment(
        multichannel_by_var,
        seg_name,
        channel_strategy=channel_strategy,
        modal_strategy=modal_strategy,
        config=config,
        metric_params=metric_params,
        vcfg=vcfg,
        verbose=False,
    )
    if row is None:
        return None
    for _l, key, _c, ch, mod in SYSTEMATIC_NEW_METHOD_SPECS:
        if ch == channel_strategy and mod == modal_strategy:
            return extract_bpm_per_window(row, key)
    return None


def run_hkh_multi_algorithm_benchmark(
    multichannel_by_var: Dict,
    seg_name: str,
    hkh_bandpass: np.ndarray,
    hkh_t_host: np.ndarray,
    cs_t_host: np.ndarray,
    *,
    config: Optional[ChFusionConfig] = None,
    metric_params: Optional[BreathMetricParams] = None,
    plan2_config: Optional[Plan2Config] = None,
    include_b2_variants: bool = True,
    fs_hkh_override: Optional[float] = None,
    verbose: bool = True,
) -> dict:
    """Compare project methods on one HKH-aligned segment."""
    cfg = config or ChFusionConfig()
    mp = metric_params or BreathMetricParams()
    p2 = plan2_config or Plan2Config(channel_metric="energy_ratio")

    bpm_hkh, _, fs_ble, fs_hkh = compute_hkh_gt_per_window(
        hkh_bandpass,
        hkh_t_host,
        cs_t_host,
        multichannel_by_var,
        seg_name,
        config=cfg,
        metric_params=mp,
        fs_hkh_override=fs_hkh_override,
    )

    results: Dict[str, dict] = {}
    runners: List[Tuple[str, str, Callable[[], Optional[np.ndarray]]]] = []

    remote_mc = {seg_name: multichannel_by_var["remote_amplitudes"][seg_name]}
    seg_remote = estimate_segment_bpm_methods(
        remote_mc,
        variable="remote_amplitudes",
        config=cfg,
        metric_params=mp,
        methods=("single", "uniform"),
        single_channel_metric=p2.channel_metric,
        verbose=False,
    )
    row_r = seg_remote.get(seg_name)
    runners.append(("B0 Single Remote", "b0_single_remote", lambda: extract_bpm_per_window(row_r, "fft_single_max_energy")))
    runners.append(("B1 Uniform Remote", "b1_uniform_remote", lambda: extract_bpm_per_window(row_r, "fft_uniform_fusion")))

    for label, key, _c, ch, mod in SYSTEMATIC_NEW_METHOD_SPECS:
        runners.append(
            (label, key, lambda ch=ch, mod=mod: _run_systematic(
                multichannel_by_var, seg_name, ch, mod, config=cfg, metric_params=mp
            ))
        )

    for label, key, _color in MODAL_FUSION_METHOD_LABELS:
        mode = _MODAL_FUSION_WEIGHT_MODES[key]

        def _modal_run(mode=mode, key=key):
            partial = estimate_modal_best_channel_fusion(
                multichannel_by_var,
                weight_mode=mode,
                config=cfg,
                metric_params=mp,
                plan2_config=p2,
                verbose=False,
            )
            return extract_bpm_per_window(partial.get(seg_name), key)

        runners.append((label, key, _modal_run))

    for label, key, _color in VOTING_METHOD_SPECS:
        if not key.startswith(("t0_", "t1_", "t2_", "t3_")):
            continue

        def _vote_run(key=key):
            if key == "t0_v1_simple":
                vcfg = VotingConfig(variable="remote_amplitudes", voting_strategy="simple")
            elif key in ("t0_v2_eta_weighted", "t1_k4_v2", "t1_k8_v2", "t1_k16_v2"):
                top_k = {"t1_k4_v2": 4, "t1_k8_v2": 8, "t1_k16_v2": 16}.get(key)
                vcfg = VotingConfig(
                    variable="remote_amplitudes",
                    voting_strategy="eta_weighted",
                    top_k=top_k,
                )
            elif key == "t0_v3_eta_rho_weighted":
                vcfg = VotingConfig(variable="remote_amplitudes", voting_strategy="eta_rho_weighted")
            elif key == "t2_cross_modal_median":
                vcfg = VotingConfig(variable="remote_amplitudes", voting_strategy="eta_rho_weighted")
            else:
                vcfg = VotingConfig(variable="remote_amplitudes", voting_strategy="eta_rho_weighted")
            partial = estimate_voting_segment_methods(
                remote_mc,
                variable="remote_amplitudes",
                config=cfg,
                metric_params=mp,
                voting_config=vcfg,
                method_key=key,
                verbose=False,
            )
            return extract_bpm_per_window(partial.get(seg_name), key)

        runners.append((label, key, _vote_run))

    if include_b2_variants:
        for label, key, _color in B2_ALL_SPECS:
            if key not in B2_PRIMARY_KEYS:
                continue

            def _b2_run(key=key):
                row = validate_b2_against_hkh(
                    multichannel_by_var,
                    seg_name,
                    hkh_bandpass,
                    hkh_t_host,
                    cs_t_host,
                    method_key=key,
                    config=cfg,
                    metric_params=mp,
                    fs_hkh_override=fs_hkh_override,
                    verbose=False,
                )
                if row is None:
                    return None, None
                return np.asarray(row["bpm_ble"], dtype=float), row["summary"]

            runners.append((label, key, _b2_run, True))

    for item in runners:
        is_b2 = len(item) == 4
        if is_b2:
            label, key, runner, _ = item
        else:
            label, key, runner = item
        try:
            out = runner()
        except Exception as exc:
            if verbose:
                print(f"  skip {key}: {exc}")
            continue
        b2_summary = None
        if is_b2:
            if out is None or out[0] is None:
                if verbose:
                    print(f"  skip {key}: no BPM series")
                continue
            bpm_est, b2_summary = out
        else:
            bpm_est = out
        if bpm_est is None or len(bpm_est) != len(bpm_hkh):
            if verbose:
                print(f"  skip {key}: no/wrong-length BPM series")
            continue
        summary = summarize_bpm_vs_hkh(bpm_est, bpm_hkh)
        entry = {
            "label": label,
            "method_key": key,
            "summary": summary,
            "bpm_est": bpm_est,
            "bpm_hkh_gt": bpm_hkh,
        }
        if b2_summary is not None:
            entry["rmse_mean"] = b2_summary["rmse_mean"]
            entry["rmse_std"] = b2_summary["rmse_std"]
        results[key] = entry
        if verbose:
            s = summary
            extra = ""
            if "rmse_mean" in entry:
                extra = f" | RMSE {entry['rmse_mean']:.3f}±{entry['rmse_std']:.3f}"
            print(
                f"  {label:<36} {s['bpm_mean_abs_err']:.2f}±{s['bpm_std_abs_err']:.2f} BPM"
                f"{extra}"
            )

    leaderboard = sorted(
        results.values(),
        key=lambda r: r["summary"]["bpm_mean_abs_err"],
    )

    return {
        "segment": seg_name,
        "fs_ble": fs_ble,
        "fs_hkh": fs_hkh,
        "bpm_hkh_gt": bpm_hkh,
        "methods": results,
        "leaderboard": [
            {
                "rank": i + 1,
                "label": r["label"],
                "method_key": r["method_key"],
                **r["summary"],
                **({"rmse_mean": r.get("rmse_mean"), "rmse_std": r.get("rmse_std")} if "rmse_mean" in r else {}),
            }
            for i, r in enumerate(leaderboard)
        ],
    }
