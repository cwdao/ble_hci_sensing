"""BLE CS 与 HKH 呼吸带数据对齐、裁剪、滤波与保存。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ble_analysis.filters import apply_filter_pipeline
from ble_analysis.hkh_data import (
    estimate_fs_from_dev_timestamps,
    estimate_fs_from_host_timestamps,
    extract_hkh_amplitudes,
)
from ble_analysis.segments import FilterParams
from data_saver import DataSaver


@dataclass
class BleHkhCropSpec:
    """裁剪规格：BLE / HKH 各自 seq 起止（含端点）。"""

    ble_start_seq: int
    ble_end_seq: int
    hkh_start_seq: int
    hkh_end_seq: Optional[int] = None  # None 时按 BLE 末帧 t_host 自动截断


@dataclass
class BleHkhFilterSpec:
    ble: FilterParams
    hkh: FilterParams


DEFAULT_CROP = BleHkhCropSpec(
    ble_start_seq=1147,
    ble_end_seq=2017,
    hkh_start_seq=21125,
    hkh_end_seq=None,
)

DEFAULT_FILTERS = BleHkhFilterSpec(
    ble=FilterParams(median_window=3),
    hkh=FilterParams(median_window=5),
)


def _iter_raw_frames(filepath: Path):
    saver = DataSaver()
    for record in saver.iter_frames(str(filepath)):
        yield record


def _crop_records_by_seq(
    records: List[dict],
    start_seq: int,
    end_seq: Optional[int],
) -> List[dict]:
    out = [r for r in records if start_seq <= r.get("seq", -1) <= (end_seq or 10**9)]
    if end_seq is not None:
        out = [r for r in out if r.get("seq", -1) <= end_seq]
    return out


def _resolve_hkh_end_seq(
    hkh_records: List[dict],
    hkh_start_seq: int,
    ble_end_t_host: int,
) -> int:
    eligible = [r for r in hkh_records if r.get("seq", -1) >= hkh_start_seq]
    in_window = [r for r in eligible if r.get("t_host_utc_ns", 0) <= ble_end_t_host]
    if not in_window:
        raise ValueError("HKH 裁剪窗口为空：请检查 seq 对齐参数")
    return int(in_window[-1]["seq"])


def _renumber_records(records: List[dict]) -> List[dict]:
    renumbered = []
    for new_seq, rec in enumerate(records):
        out = dict(rec)
        out["seq"] = new_seq
        renumbered.append(out)
    return renumbered


def write_jsonl_records(
    filepath: Path,
    meta: dict,
    records: List[dict],
) -> None:
    """写入 JSONL（meta + frame 行）。"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("w", encoding="utf-8") as handle:
        meta_out = dict(meta)
        meta_out["record_type"] = "meta"
        handle.write(json.dumps(meta_out, ensure_ascii=False, separators=(",", ":")) + "\n")
        for rec in records:
            row = dict(rec)
            row["record_type"] = "frame"
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _filter_1d(values: np.ndarray, fs: float, fp: FilterParams) -> Dict[str, np.ndarray]:
    raw = np.asarray(values, dtype=float)
    median = apply_filter_pipeline(raw, fs=fs, pipeline=[{"type": "median", "window_size": fp.median_window}])
    highpass = apply_filter_pipeline(
        median,
        fs=fs,
        pipeline=[{"type": "highpass", "cutoff": fp.highpass_cutoff, "order": fp.highpass_order}],
    )
    bandpass = apply_filter_pipeline(
        highpass,
        fs=fs,
        pipeline=[
            {
                "type": "bandpass",
                "lowcut": fp.bandpass_lowcut,
                "highcut": fp.bandpass_highcut,
                "order": fp.bandpass_order,
            }
        ],
    )
    return {
        "raw": raw,
        "median_filtered": median,
        "highpass_filtered": highpass,
        "bandpass_filtered": bandpass,
    }


def preprocess_ble_hkh_pair(
    cs_path: Path,
    hkh_path: Path,
    output_dir: Path,
    *,
    dataset_name: str,
    crop: BleHkhCropSpec = DEFAULT_CROP,
    filters: BleHkhFilterSpec = DEFAULT_FILTERS,
    verbose: bool = True,
) -> dict:
    """对齐裁剪 BLE/HKH，滤波并保存 jsonl + npz + meta。"""
    saver = DataSaver()
    cs_meta = saver.read_meta(str(cs_path))
    hkh_meta = saver.read_meta(str(hkh_path))
    if cs_meta is None or hkh_meta is None:
        raise ValueError("无法读取 CS 或 HKH meta 行")

    cs_raw = list(_iter_raw_frames(cs_path))
    hkh_raw = list(_iter_raw_frames(hkh_path))

    cs_crop = _crop_records_by_seq(cs_raw, crop.ble_start_seq, crop.ble_end_seq)
    if not cs_crop:
        raise ValueError(f"BLE 裁剪为空: seq {crop.ble_start_seq}-{crop.ble_end_seq}")

    ble_end_t_host = int(cs_crop[-1]["t_host_utc_ns"])
    hkh_end_seq = crop.hkh_end_seq
    if hkh_end_seq is None:
        hkh_end_seq = _resolve_hkh_end_seq(hkh_raw, crop.hkh_start_seq, ble_end_t_host)

    hkh_crop = _crop_records_by_seq(hkh_raw, crop.hkh_start_seq, hkh_end_seq)
    if not hkh_crop:
        raise ValueError(f"HKH 裁剪为空: seq {crop.hkh_start_seq}-{hkh_end_seq}")

    # 对齐检查
    cs_anchor_t = int(cs_crop[0]["t_host_utc_ns"])
    hkh_anchor_t = int(hkh_crop[0]["t_host_utc_ns"])
    anchor_diff_ms = (hkh_anchor_t - cs_anchor_t) / 1e6

    cs_out = _renumber_records(cs_crop)
    hkh_out = _renumber_records(hkh_crop)

    out_dir = output_dir / dataset_name
    out_dir.mkdir(parents=True, exist_ok=True)

    cs_out_path = out_dir / "CS_frames_cropped.jsonl"
    hkh_out_path = out_dir / "HKH_frames_cropped.jsonl"
    npz_path = out_dir / "aligned_bundle.npz"
    meta_path = out_dir / "preprocess_meta.json"

    cs_meta_out = dict(cs_meta)
    cs_meta_out["cropped_from"] = str(cs_path)
    cs_meta_out["crop_seq"] = [crop.ble_start_seq, crop.ble_end_seq]
    hkh_meta_out = dict(hkh_meta)
    hkh_meta_out["cropped_from"] = str(hkh_path)
    hkh_meta_out["crop_seq"] = [crop.hkh_start_seq, hkh_end_seq]

    write_jsonl_records(cs_out_path, cs_meta_out, cs_out)
    write_jsonl_records(hkh_out_path, hkh_meta_out, hkh_out)

    # 采样率
    cs_t_dev = np.array([r["t_dev_ms"] for r in cs_crop], dtype=float)
    hkh_t_host = np.array([r["t_host_utc_ns"] for r in hkh_crop], dtype=np.int64)
    hkh_amp = np.array([r["amp"] for r in hkh_crop], dtype=float)

    fs_ble_dev = estimate_fs_from_dev_timestamps(cs_t_dev)
    fs_ble_host = estimate_fs_from_host_timestamps(
        np.array([r["t_host_utc_ns"] for r in cs_crop], dtype=np.int64)
    )
    fs_hkh_host = estimate_fs_from_host_timestamps(hkh_t_host)
    fs_ble = fs_ble_dev if np.isfinite(fs_ble_dev) else fs_ble_host

    duration_s = float((hkh_t_host[-1] - hkh_t_host[0]) / 1e9)
    fs_hkh = float(len(hkh_crop) / max(duration_s, 1e-6))

    hkh_filtered = _filter_1d(hkh_amp, fs_hkh, filters.hkh)

    np.savez_compressed(
        npz_path,
        cs_t_host_utc_ns=np.array([r["t_host_utc_ns"] for r in cs_crop], dtype=np.int64),
        cs_t_dev_ms=cs_t_dev,
        hkh_t_host_utc_ns=hkh_t_host,
        hkh_amp_raw=hkh_amp,
        hkh_median=hkh_filtered["median_filtered"],
        hkh_highpass=hkh_filtered["highpass_filtered"],
        hkh_bandpass=hkh_filtered["bandpass_filtered"],
        fs_ble=np.array([fs_ble]),
        fs_hkh=np.array([fs_hkh]),
    )

    meta_doc: Dict[str, Any] = {
        "dataset_name": dataset_name,
        "source_files": {
            "cs": str(cs_path),
            "hkh": str(hkh_path),
        },
        "output_files": {
            "cs_cropped": str(cs_out_path),
            "hkh_cropped": str(hkh_out_path),
            "aligned_bundle": str(npz_path),
        },
        "crop": {
            "ble_seq": [crop.ble_start_seq, crop.ble_end_seq],
            "hkh_seq": [crop.hkh_start_seq, hkh_end_seq],
            "ble_frames": len(cs_crop),
            "hkh_frames": len(hkh_crop),
            "duration_s": duration_s,
        },
        "alignment": {
            "cs_anchor_seq": crop.ble_start_seq,
            "hkh_anchor_seq": crop.hkh_start_seq,
            "anchor_t_host_utc_ns": cs_anchor_t,
            "anchor_diff_ms": anchor_diff_ms,
        },
        "sampling_rate_hz": {
            "ble_from_t_dev": fs_ble_dev,
            "ble_from_t_host": fs_ble_host,
            "ble_used": fs_ble,
            "hkh_from_t_host_diff": fs_hkh_host,
            "hkh_from_len_duration": fs_hkh,
            "hkh_used": fs_hkh,
        },
        "filters": {
            "ble": asdict(filters.ble),
            "hkh": asdict(filters.hkh),
        },
    }

    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta_doc, handle, ensure_ascii=False, indent=2)

    if verbose:
        print(f"✓ 预处理完成: {out_dir}")
        print(f"  BLE: {len(cs_crop)} 帧, fs≈{fs_ble:.3f} Hz")
        print(f"  HKH: {len(hkh_crop)} 帧, fs≈{fs_hkh:.3f} Hz")
        print(f"  时长: {duration_s:.1f} s, 锚点对齐差: {anchor_diff_ms:.3f} ms")

    return meta_doc
