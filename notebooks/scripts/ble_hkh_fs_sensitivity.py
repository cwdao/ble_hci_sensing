"""Compare B2 vs HKH validation under measured vs nominal sampling rates.

Run:
    python notebooks/scripts/ble_hkh_fs_sensitivity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.ble_hkh_preprocess import _filter_1d
from ble_analysis.ble_hkh_validation import load_hkh_gt_signals, validate_b2_against_hkh
from ble_analysis.chfusion import (
    ChFusionConfig,
    MODAL_FILTER_VARIABLES,
    run_multichannel_segment_filtering,
)
from ble_analysis.data import load_ble_frames
from ble_analysis.hkh_data import estimate_fs_from_dev_timestamps, estimate_fs_from_host_timestamps
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams, FilterParams

SCENARIO_ID = "room_A-sbj_A-07101613"
B2_METHOD = "b2_d_two_level"
NOMINAL_FS_BLE = 4.0
NOMINAL_FS_HKH = 50.0


def load_multichannel_no_cache(scenario, fs_override: float | None):
    _, frames = load_ble_frames(scenario.resolve_data_path(project_root), verbose=False)
    t_dev = np.array([f.get("timestamp_ms", 0) for f in frames], dtype=float)
    t_host = np.array([f.get("t_host_utc_ns", 0) for f in frames], dtype=np.int64)
    fs_dev = estimate_fs_from_dev_timestamps(t_dev)
    fs_host = estimate_fs_from_host_timestamps(t_host)

    multichannel_by_var = {}
    fs_used = fs_override if fs_override is not None else fs_dev
    for variable in MODAL_FILTER_VARIABLES:
        mc, fs_used = run_multichannel_segment_filtering(
            frames,
            scenario.segment_config,
            variable=variable,
            filter_params=FilterParams(),
            cache_dir=None,
            fs_override=fs_override,
            verbose=False,
        )
        multichannel_by_var[variable] = mc

    return multichannel_by_var, fs_used, fs_dev, fs_host


def run_case(
    label: str,
    multichannel_by_var,
    hkh_bandpass,
    hkh_t,
    cs_t,
    fs_hkh: float,
):
    cfg = ChFusionConfig()
    mp = BreathMetricParams()
    row = validate_b2_against_hkh(
        multichannel_by_var,
        "main",
        hkh_bandpass,
        hkh_t,
        cs_t,
        method_key=B2_METHOD,
        config=cfg,
        metric_params=mp,
        fs_hkh_override=fs_hkh,
        verbose=False,
    )
    if row is None:
        return None
    s = row["summary"]
    fs_ble = row["fs_ble"]
    gt_mean = float(np.nanmean(row["bpm_hkh_gt"]))
    ble_mean = float(np.nanmean(row["bpm_ble"]))
    return {
        "label": label,
        "fs_ble": fs_ble,
        "fs_hkh": fs_hkh,
        "bpm_err": s["bpm_mean_abs_err"],
        "bpm_std": s["bpm_std_abs_err"],
        "bpm_rel_pct": s["bpm_mean_rel_err_pct"],
        "rmse": s["rmse_mean"],
        "gt_mean_bpm": gt_mean,
        "ble_mean_bpm": ble_mean,
        "n_windows": row["n_windows"],
        "win_len_samples": int(round(mp.window_length_sec * fs_ble)),
    }


if __name__ == "__main__":
    scenario = load_scenario(SCENARIO_ID, project_root=project_root)
    processed_dir = (project_root / Path(scenario.data_file)).parent
    bundle = np.load(processed_dir / "aligned_bundle.npz")
    hkh_amp = bundle["hkh_amp_raw"]
    hkh_t = bundle["hkh_t_host_utc_ns"]
    cs_t = bundle["cs_t_host_utc_ns"]
    fs_hkh_meas = float(bundle["fs_hkh"][0])
    fs_ble_meas = float(bundle["fs_ble"][0])

    fp_hkh = FilterParams(median_window=5)
    hkh_bp_meas = bundle["hkh_bandpass"]
    hkh_bp_nom = _filter_1d(hkh_amp, NOMINAL_FS_HKH, fp_hkh)["bandpass_filtered"]

    mc_meas, _, fs_dev, fs_host = load_multichannel_no_cache(scenario, fs_override=None)
    mc_nom, fs_ble_nom, _, _ = load_multichannel_no_cache(scenario, fs_override=NOMINAL_FS_BLE)

    cases = [
        run_case(
            "A measured fs (current)",
            mc_meas,
            hkh_bp_meas,
            hkh_t,
            cs_t,
            fs_hkh_meas,
        ),
        run_case(
            "B nominal fs (BLE 4 + HKH 50)",
            mc_nom,
            hkh_bp_nom,
            hkh_t,
            cs_t,
            NOMINAL_FS_HKH,
        ),
        run_case(
            "C mixed: BLE measured + HKH 50 BPM",
            mc_meas,
            hkh_bp_meas,
            hkh_t,
            cs_t,
            NOMINAL_FS_HKH,
        ),
        run_case(
            "D mixed: BLE 4 filter + HKH measured BPM",
            mc_nom,
            hkh_bp_nom,
            hkh_t,
            cs_t,
            fs_hkh_meas,
        ),
    ]

    print(f"\n=== FS sensitivity ({SCENARIO_ID}, {B2_METHOD}) ===\n")
    print(f"BLE measured: t_dev={fs_ble_meas:.3f} Hz, t_host={fs_host:.3f} Hz")
    print(f"HKH measured: t_host={fs_hkh_meas:.3f} Hz (nominal 50 Hz)")
    print(f"Nominal: BLE={NOMINAL_FS_BLE} Hz, HKH={NOMINAL_FS_HKH} Hz\n")

    print(f"{'Case':<42} {'fs_BLE':>7} {'fs_HKH':>7} {'win_len':>7}  {'BPM err':>14}  {'GT mean':>8} {'BLE mean':>9}")
    print("-" * 105)
    for c in cases:
        if c is None:
            continue
        print(
            f"{c['label']:<42} {c['fs_ble']:7.2f} {c['fs_hkh']:7.1f} {c['win_len_samples']:7d}  "
            f"{c['bpm_err']:.2f}+/-{c['bpm_std']:.2f} BPM  "
            f"{c['gt_mean_bpm']:8.2f} {c['ble_mean_bpm']:9.2f}"
        )

    print("\nwin_len = round(20s * fs_BLE) samples per sliding window")
