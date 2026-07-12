"""Batch preprocess BLE CS + HKH breathing belt recording pairs.

Run:
    python notebooks/scripts/preprocess_ble_hkh_batch.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Optional

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
    _crop_records_by_seq,
    _iter_raw_frames,
    preprocess_ble_hkh_pair,
)
from ble_analysis.bootstrap import init_notebook
from ble_analysis.segments import FilterParams

_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]

OUT_ROOT = project_root / "sampleData/processed"
BLE_HKH_DIR = project_root / "sampleData/ble-hkh"

ANCHOR_DIFF_STOP_MS = 500.0  # clock/file mismatch; sparse BLE may be ~200 ms
ANCHOR_DIFF_WARN_MS = 100.0

FILTERS = BleHkhFilterSpec(
    ble=FilterParams(median_window=3),
    hkh=FilterParams(median_window=5),
)

ROOM_LABELS = {
    "room_A": "Living room sitting",
    "room_B": "Bedroom lying flat",
    "room_C": "Bedroom side lying",
}

DATASETS = [
    {
        "id": "room_A-sbj_B-07111610",
        "cs_src": "CS_frames_all_20260711_161050.jsonl",
        "hkh_src": "HKH_frames_all_20260711_160953.jsonl",
        "hkh_start_seq": 8957,
        "hkh_end_seq": 16868,
    },
    {
        "id": "room_A-sbj_C-07111623",
        "cs_src": "CS_frames_all_20260711_162335.jsonl",
        "hkh_src": "HKH_frames_all_20260711_162311.jsonl",
        "hkh_start_seq": 3629,
        "hkh_end_seq": 11445,
    },
    {
        "id": "room_A-sbj_D-07111635",
        "cs_src": "CS_frames_all_20260711_163501.jsonl",
        "hkh_src": "HKH_frames_all_20260711_163426.jsonl",
        "hkh_start_seq": 11474,
        "hkh_end_seq": 17958,
    },
    {
        "id": "room_B-sbj_A-07111726",
        "cs_src": "CS_frames_all_20260711_172655.jsonl",
        "hkh_src": "HKH_frames_all_20260711_172916.jsonl",
        "hkh_start_seq": 4978,
        "hkh_end_seq": 9027,
    },
    {
        "id": "room_B-sbj_B-07111820",
        "cs_src": "CS_frames_all_20260711_182051.jsonl",
        "hkh_src": "HKH_frames_all_20260711_182032.jsonl",
        "hkh_start_seq": 3824,
        "hkh_end_seq": 9259,
    },
    {
        "id": "room_B-sbj_C-07111843",
        "cs_src": "CS_frames_all_20260711_184311.jsonl",
        "hkh_src": "HKH_frames_all_20260711_184313.jsonl",
        "hkh_start_seq": 3513,
        "hkh_end_seq": 10405,
    },
    {
        "id": "room_B-sbj_D-07111653",
        "cs_src": "CS_frames_all_20260711_165337.jsonl",
        "hkh_src": "HKH_frames_all_20260711_165254.jsonl",
        "hkh_start_seq": 8049,
        "hkh_end_seq": 13542,
    },
    {
        "id": "room_C-sbj_A-07111734",
        "cs_src": "CS_frames_all_20260711_173459.jsonl",
        "hkh_src": "HKH_frames_all_20260711_173502.jsonl",
        "hkh_start_seq": 2088,
        "hkh_end_seq": 8033,
    },
    {
        "id": "room_C-sbj_B-07111835",
        "cs_src": "CS_frames_all_20260711_183527.jsonl",
        "hkh_src": "HKH_frames_all_20260711_183528.jsonl",
        "hkh_start_seq": 1843,
        "hkh_end_seq": 9646,
    },
    {
        "id": "room_C-sbj_C-07111850",
        "cs_src": "CS_frames_all_20260711_185002.jsonl",
        "hkh_src": "HKH_frames_all_20260711_185017.jsonl",
        "hkh_start_seq": 4341,
        "hkh_end_seq": 13489,
    },
    {
        "id": "room_C-sbj_D-07111659",
        "cs_src": "CS_frames_all_20260711_165953.jsonl",
        "hkh_src": "HKH_frames_all_20260711_170037.jsonl",
        "hkh_start_seq": 2248,
        "hkh_end_seq": 8766,
    },
]


def infer_ble_crop_from_hkh_window(
    cs_path: Path,
    hkh_path: Path,
    hkh_start_seq: int,
    hkh_end_seq: int,
) -> BleHkhCropSpec:
    """Crop HKH by seq, derive time window, locate matching BLE seq range."""
    hkh_raw = list(_iter_raw_frames(hkh_path))
    hkh_crop = _crop_records_by_seq(hkh_raw, hkh_start_seq, hkh_end_seq)
    if not hkh_crop:
        raise ValueError(
            f"HKH crop empty: seq {hkh_start_seq}-{hkh_end_seq} in {hkh_path.name}"
        )

    t_start = int(hkh_crop[0]["t_host_utc_ns"])
    t_end = int(hkh_crop[-1]["t_host_utc_ns"])

    cs_raw = list(_iter_raw_frames(cs_path))
    cs_in_window = [
        r for r in cs_raw if t_start <= int(r.get("t_host_utc_ns", 0)) <= t_end
    ]
    if not cs_in_window:
        raise ValueError(
            f"No BLE frames in HKH time window [{t_start}, {t_end}] for {cs_path.name}"
        )

    # Anchor BLE start to HKH start timestamp (nearest frame), not merely first in-window
    # frame — BLE ~2.4 Hz may lag HKH t_start by <1 sample period.
    search_ns = int(500e6)  # 500 ms search radius
    cs_near_start = [
        r
        for r in cs_raw
        if abs(int(r.get("t_host_utc_ns", 0)) - t_start) <= search_ns
    ]
    if cs_near_start:
        ble_start_rec = min(
            cs_near_start,
            key=lambda r: abs(int(r["t_host_utc_ns"]) - t_start),
        )
    else:
        ble_start_rec = cs_in_window[0]

    cs_near_end = [
        r for r in cs_raw if abs(int(r.get("t_host_utc_ns", 0)) - t_end) <= search_ns
    ]
    if cs_near_end:
        ble_end_rec = min(
            cs_near_end,
            key=lambda r: abs(int(r["t_host_utc_ns"]) - t_end),
        )
    else:
        ble_end_rec = cs_in_window[-1]

    ble_start_seq = int(ble_start_rec["seq"])
    ble_end_seq = int(ble_end_rec["seq"])
    if ble_start_seq > ble_end_seq:
        ble_start_seq, ble_end_seq = ble_end_seq, ble_start_seq

    return BleHkhCropSpec(
        ble_start_seq=ble_start_seq,
        ble_end_seq=ble_end_seq,
        hkh_start_seq=hkh_start_seq,
        hkh_end_seq=hkh_end_seq,
    )


def plot_alignment_diagnostic(dataset_id: str, out_dir: Path, meta: dict) -> Path:
    bundle = np.load(out_dir / "aligned_bundle.npz")
    hkh_bp = bundle["hkh_bandpass"]
    hkh_t = bundle["hkh_t_host_utc_ns"]
    fs_hkh = float(meta["sampling_rate_hz"]["hkh_used"])

    t_sec = (hkh_t - hkh_t[0]) / 1e9
    fig, axes = plt.subplots(2, 1, figsize=(14, 6), sharex=True)

    axes[0].plot(t_sec, bundle["hkh_amp_raw"], color="0.6", lw=0.8, label="HKH raw")
    axes[0].set_ylabel("HKH raw amp")
    axes[0].legend(loc="upper right")
    axes[0].set_title(f"HKH alignment diagnostic — {dataset_id}")

    axes[1].plot(t_sec, hkh_bp, color="crimson", lw=1.0, label="HKH bandpass (GT)")
    axes[1].set_ylabel("HKH bandpass")
    axes[1].set_xlabel("Time (s)")
    axes[1].legend(loc="upper right")

    anchor_ms = meta["alignment"]["anchor_diff_ms"]
    info = (
        f"BLE fs≈{meta['sampling_rate_hz']['ble_used']:.2f} Hz | "
        f"HKH fs≈{fs_hkh:.2f} Hz | "
        f"duration={meta['crop']['duration_s']:.1f}s | "
        f"anchor_diff={anchor_ms:.2f} ms"
    )
    fig.text(0.01, 0.01, info, fontsize=9, color="0.35")
    fig.tight_layout()

    fig_path = FIGURES_DIR / f"ble_hkh_preprocess_{dataset_id}.png"
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fig_path


def _parse_dataset_id(dataset_id: str):
    m = re.match(r"(room_[A-C])-(sbj_[A-D])-(\d+)", dataset_id)
    if not m:
        return "unknown", "unknown", ""
    return m.group(1), m.group(2), m.group(3)


def write_scenario_json(dataset_id: str, out_dir: Path, meta: dict, n_ble: int) -> Path:
    room_key, subject_key, ts = _parse_dataset_id(dataset_id)
    subject_letter = subject_key.replace("sbj_", "")
    room_desc = ROOM_LABELS.get(room_key, room_key)

    scenario = {
        "id": dataset_id,
        "name": f"{room_desc} — Subject {subject_letter} BLE+HKH ({ts})",
        "modality": "CS",
        "data_file": str(out_dir.relative_to(project_root) / "CS_frames_cropped.jsonl").replace(
            "\\", "/"
        ),
        "hkh_file": str(out_dir.relative_to(project_root) / "HKH_frames_cropped.jsonl").replace(
            "\\", "/"
        ),
        "preprocess_meta": str(
            out_dir.relative_to(project_root) / "preprocess_meta.json"
        ).replace("\\", "/"),
        "default_channel": 2,
        "description": (
            f"Live human breathing with HKH ground truth. "
            f"{room_desc}; BPM GT from HKH bandpass waveform."
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
    cfg_path = cfg_dir / f"{dataset_id}.json"
    with cfg_path.open("w", encoding="utf-8") as handle:
        json.dump(scenario, handle, ensure_ascii=False, indent=2)
    return cfg_path


def process_one_dataset(ds: dict) -> dict:
    dataset_id = ds["id"]
    cs_path = BLE_HKH_DIR / ds["cs_src"]
    hkh_path = BLE_HKH_DIR / ds["hkh_src"]

    if not cs_path.is_file():
        raise FileNotFoundError(f"CS source missing: {cs_path}")
    if not hkh_path.is_file():
        raise FileNotFoundError(f"HKH source missing: {hkh_path}")

    crop = infer_ble_crop_from_hkh_window(
        cs_path,
        hkh_path,
        ds["hkh_start_seq"],
        ds["hkh_end_seq"],
    )

    print(f"\n{'=' * 60}")
    print(f"Processing {dataset_id}")
    print(
        f"  BLE seq: {crop.ble_start_seq}-{crop.ble_end_seq} | "
        f"HKH seq: {crop.hkh_start_seq}-{crop.hkh_end_seq}"
    )

    meta = preprocess_ble_hkh_pair(
        cs_path,
        hkh_path,
        OUT_ROOT,
        dataset_name=dataset_id,
        crop=crop,
        filters=FILTERS,
        verbose=True,
    )

    anchor_diff_ms = float(meta["alignment"]["anchor_diff_ms"])
    if abs(anchor_diff_ms) > ANCHOR_DIFF_STOP_MS:
        raise RuntimeError(
            f"STOP: {dataset_id} anchor_diff_ms={anchor_diff_ms:.2f} ms "
            f"exceeds {ANCHOR_DIFF_STOP_MS} ms threshold. Manual check required."
        )
    if abs(anchor_diff_ms) > ANCHOR_DIFF_WARN_MS:
        print(
            f"  ⚠ anchor_diff_ms={anchor_diff_ms:.2f} ms > {ANCHOR_DIFF_WARN_MS} ms "
            f"(expected with BLE ~2.4 Hz sparse sampling)"
        )

    out_dir = OUT_ROOT / dataset_id
    fig_path = plot_alignment_diagnostic(dataset_id, out_dir, meta)
    scenario_path = write_scenario_json(dataset_id, out_dir, meta, meta["crop"]["ble_frames"])

    print(f"  Saved figure: {fig_path}")
    print(f"  Saved scenario: {scenario_path}")
    return meta


if __name__ == "__main__":
    results: List[dict] = []
    try:
        for ds in DATASETS:
            meta = process_one_dataset(ds)
            results.append(
                {
                    "id": ds["id"],
                    "anchor_diff_ms": meta["alignment"]["anchor_diff_ms"],
                    "ble_frames": meta["crop"]["ble_frames"],
                    "hkh_frames": meta["crop"]["hkh_frames"],
                    "duration_s": meta["crop"]["duration_s"],
                    "fs_ble": meta["sampling_rate_hz"]["ble_used"],
                    "fs_hkh": meta["sampling_rate_hz"]["hkh_used"],
                }
            )
    except RuntimeError as exc:
        print(f"\n❌ Batch aborted: {exc}")
        sys.exit(1)

    summary_path = project_root / "outputs/reports/ble_hkh_preprocess_batch_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump({"processed": len(results), "datasets": results}, handle, indent=2)

    print(f"\n{'=' * 60}")
    print(f"✓ Batch complete: {len(results)}/{len(DATASETS)} datasets")
    print(f"  Summary: {summary_path}")
    print("\nAnchor diff (ms):")
    for row in results:
        print(f"  {row['id']}: {row['anchor_diff_ms']:.3f} ms")
