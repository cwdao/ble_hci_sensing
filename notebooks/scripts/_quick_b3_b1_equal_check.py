"""Quick check: b3_b1_equal BPM vs B1 Vote→Equal across 12 HKH scenarios."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

project_root = next((p for p in [Path.cwd().resolve(), *Path.cwd().resolve().parents] if (p / "src").is_dir()), None)
sys.path.insert(0, str(project_root / "src"))

from ble_analysis.b3_pipeline import validate_b1_vote_equal_against_hkh, validate_b3_variant_against_hkh
from ble_analysis.ble_hkh_validation import load_hkh_gt_signals
from ble_analysis.chfusion import ChFusionConfig, load_multichannel_for_scenario
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams, FilterParams

SCENARIO_IDS = [
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

if __name__ == "__main__":
    fp, mp = FilterParams(), BreathMetricParams()
    cfg = ChFusionConfig(
        breath_freq_low=mp.breath_freq_low,
        breath_freq_high=mp.breath_freq_high,
        window_length_sec=mp.window_length_sec,
        step_length_sec=mp.step_length_sec,
    )
    b1s, b3s, rmses = [], [], []
    for sid in SCENARIO_IDS:
        sc = load_scenario(sid, project_root=project_root)
        pd = (project_root / Path(sc.data_file)).parent
        hkh, ht, ct, meta = load_hkh_gt_signals(pd)
        fs_hkh = meta.get("sampling_rate_hz", {}).get("hkh_used")
        mc, _, _ = load_multichannel_for_scenario(
            sc,
            project_root=project_root,
            filter_params=fp,
            cache_dir=str(project_root / "outputs" / "cache"),
            verbose=False,
        )
        r1 = validate_b1_vote_equal_against_hkh(
            mc, "main", hkh, ht, ct,
            config=cfg, metric_params=mp, fs_hkh_override=fs_hkh, verbose=False,
        )
        r3 = validate_b3_variant_against_hkh(
            mc, "main", hkh, ht, ct,
            variant_key="b3_b1_equal",
            config=cfg, metric_params=mp, fs_hkh_override=fs_hkh, verbose=False,
        )
        b1m = r1["summary"]["bpm_mean_abs_err"]
        b3m = r3["summary"]["bpm_mean_abs_err"]
        b1s.append(b1m)
        b3s.append(b3m)
        rmses.append(r3["summary"]["rmse_mean"])
        print(
            f"{sid}: B1={b1m:.4f} B3={b3m:.4f} diff={b3m - b1m:+.4f} "
            f"RMSE={r3['summary']['rmse_mean']:.3f}"
        )
    diff = np.array(b3s) - np.array(b1s)
    print(
        f"\nCross mean: B1={np.mean(b1s):.4f} B3={np.mean(b3s):.4f} "
        f"max|diff|={np.max(np.abs(diff)):.6f} RMSE={np.mean(rmses):.3f}"
    )
