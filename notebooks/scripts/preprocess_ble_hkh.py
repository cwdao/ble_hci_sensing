"""Preprocess BLE CS + HKH breathing belt recording pair.

Run:
    python notebooks/scripts/preprocess_ble_hkh.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found (missing src/ directory)")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.ble_hkh_preprocess import (
    BleHkhCropSpec,
    BleHkhFilterSpec,
    preprocess_ble_hkh_pair,
)
from ble_analysis.bootstrap import init_notebook
from ble_analysis.segments import FilterParams

_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]

DATASET_NAME = "room_A-sbj_A-07101613"
CS_SRC = project_root / "sampleData/ble-hkh/CS_frames_all_20260710_161311.jsonl"
HKH_SRC = project_root / "sampleData/ble-hkh/HKH_frames_all_20260710_161315.jsonl"
OUT_ROOT = project_root / "sampleData/processed"

CROP = BleHkhCropSpec(
    ble_start_seq=1147,
    ble_end_seq=2017,
    hkh_start_seq=21125,
    hkh_end_seq=None,
)
FILTERS = BleHkhFilterSpec(
    ble=FilterParams(median_window=3),
    hkh=FilterParams(median_window=5),
)


def plot_alignment_diagnostic(out_dir: Path, meta: dict) -> Path:
    bundle = np.load(out_dir / "aligned_bundle.npz")
    hkh_bp = bundle["hkh_bandpass"]
    hkh_t = bundle["hkh_t_host_utc_ns"]
    fs_hkh = float(meta["sampling_rate_hz"]["hkh_used"])

    t_sec = (hkh_t - hkh_t[0]) / 1e9
    fig, axes = plt.subplots(2, 1, figsize=(14, 6), sharex=True)

    axes[0].plot(t_sec, bundle["hkh_amp_raw"], color="0.6", lw=0.8, label="HKH raw")
    axes[0].set_ylabel("HKH raw amp")
    axes[0].legend(loc="upper right")
    axes[0].set_title(f"HKH alignment diagnostic — {DATASET_NAME}")

    axes[1].plot(t_sec, hkh_bp, color="crimson", lw=1.0, label="HKH bandpass (GT)")
    axes[1].set_ylabel("HKH bandpass")
    axes[1].set_xlabel("Time (s)")
    axes[1].legend(loc="upper right")

    info = (
        f"BLE fs≈{meta['sampling_rate_hz']['ble_used']:.2f} Hz | "
        f"HKH fs≈{fs_hkh:.2f} Hz | "
        f"duration={meta['crop']['duration_s']:.1f}s"
    )
    fig.text(0.01, 0.01, info, fontsize=9, color="0.35")
    fig.tight_layout()

    fig_path = FIGURES_DIR / f"ble_hkh_preprocess_{DATASET_NAME}.png"
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig_path


def write_scenario_json(out_dir: Path, meta: dict, n_ble: int) -> Path:
    scenario = {
        "id": DATASET_NAME,
        "name": "Room A Subject A — BLE+HKH live breathing (2026-07-10)",
        "modality": "CS",
        "data_file": str(out_dir.relative_to(project_root) / "CS_frames_cropped.jsonl").replace("\\", "/"),
        "hkh_file": str(out_dir.relative_to(project_root) / "HKH_frames_cropped.jsonl").replace("\\", "/"),
        "preprocess_meta": str(out_dir.relative_to(project_root) / "preprocess_meta.json").replace("\\", "/"),
        "default_channel": 2,
        "description": (
            "Live human breathing with HKH ground truth. "
            "Single clean segment; BPM GT derived from HKH bandpass waveform."
        ),
        "segments": {
            "main": {
                "start": 0,
                "end": n_ble - 1,
                "type": "breath",
            }
        },
    }
    cfg_dir = project_root / "config/scenarios"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / f"{DATASET_NAME}.json"
    with cfg_path.open("w", encoding="utf-8") as handle:
        json.dump(scenario, handle, ensure_ascii=False, indent=2)
    return cfg_path


if __name__ == "__main__":
    meta = preprocess_ble_hkh_pair(
        CS_SRC,
        HKH_SRC,
        OUT_ROOT,
        dataset_name=DATASET_NAME,
        crop=CROP,
        filters=FILTERS,
        verbose=True,
    )
    out_dir = OUT_ROOT / DATASET_NAME
    fig_path = plot_alignment_diagnostic(out_dir, meta)
    scenario_path = write_scenario_json(out_dir, meta, meta["crop"]["ble_frames"])
    print(f"Saved figure: {fig_path}")
    print(f"Saved scenario: {scenario_path}")
