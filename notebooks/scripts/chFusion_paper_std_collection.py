"""Collect Table 6.3-B per-room std and Table 6.4 RMSE std (ddof=0).

Plan: docs/plans/paper_std_collection_plan.md

Reads existing summaries only. Does not rewrite source JSON.

    python notebooks/scripts/chFusion_paper_std_collection.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

REPORTS_DIR = project_root / "outputs" / "reports"
OUT_PATH = REPORTS_DIR / "paper_table63b_per_room_std.json"

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

ROOMS = (
    ("living", "room_A", "Living sitting", 0, 4),
    ("bedroom_flat", "room_B", "Bedroom flat", 4, 8),
    ("bedroom_side", "room_C", "Bedroom side", 8, 12),
)

# Table 6.3-B row order.
TABLE_63B = (
    ("breathecs", "BreatheCS", "draft_s_rl", "ablation"),
    ("pos_free_pca", "Pos-Free (PCA)", "z1_no_vmd", "baselines"),
    ("wifi_sleep_mrc_pca", "WiFi-Sleep (MRC-PCA)", "mrc_pca_eta_equal_pca", "baselines"),
    ("breathecs_wave", "BreatheCS-Wave", "draft_w_rl", "ablation"),
    ("wifi_sleep_sqrt_eta", "WiFi-Sleep (√η)", "mrc_pca_eta_sqrt", "baselines"),
    ("pca_sign_only", "PCA sign only", "b2_a0_pca_sign", "baselines"),
    ("clessbreath_eta_linear", "ClessBreath (η-linear)", "fan_eta_linear", "baselines"),
    ("clessbreath_eta_equal", "ClessBreath (η-equal)", "fan_eta_equal_wf", "baselines"),
)

# Plan author hand values (ddof=0), cross-check only.
HAND_CHECK = {
    "breathecs": {
        "living": (0.356, 0.092),
        "bedroom_flat": (0.412, 0.169),
        "bedroom_side": (0.344, 0.096),
    },
    "breathecs_wave": {
        "living": (0.358, 0.070),
        "bedroom_flat": (0.424, 0.139),
        "bedroom_side": (0.374, 0.107),
    },
}

# Published Table 6.4 RMSE std (3 decimals). Source is ddof=1 in
# chFusion_paper_figure_redraw.py load_unified_catalog().
TABLE_64_PUBLISHED_DDOF1 = {
    "breathecs": 0.209,
    "pos_free_pca": 0.250,
    "wifi_sleep_mrc_pca": 0.245,
    "wifi_sleep_sqrt_eta": None,  # paper cell is em dash
    "pca_sign_only": 0.182,
    "clessbreath_eta_linear": 0.241,
    "clessbreath_eta_equal": 0.211,
}

TABLE_64 = (
    ("breathecs", "BreatheCS", "draft_w_rl", "ablation"),
    ("pos_free_pca", "Pos-Free (PCA)", "z1_no_vmd", "baselines_bpm_row"),
    ("wifi_sleep_mrc_pca", "WiFi-Sleep (MRC-PCA)", "mrc_pca_eta_equal_pca", "baselines_bpm_row"),
    ("wifi_sleep_sqrt_eta", "WiFi-Sleep (√η)", "mrc_pca_eta_sqrt", "baselines_bpm_row"),
    ("pca_sign_only", "PCA sign only", "b2_a0_pca_sign", "baselines_bpm_row"),
    ("clessbreath_eta_linear", "ClessBreath (η-linear)", "fan_eta_linear", "baselines_bpm_row"),
    ("clessbreath_eta_equal", "ClessBreath (η-equal)", "fan_eta_equal_wf", "baselines_bpm_row"),
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _room_stats(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    if arr.size != 12 or not np.all(np.isfinite(arr)):
        raise ValueError(f"expected 12 finite values, got {arr.size}")
    out = {}
    for key, room_id, label, a, b in ROOMS:
        chunk = arr[a:b]
        out[key] = {
            "room_id": room_id,
            "label": label,
            "n": int(chunk.size),
            "values": [float(x) for x in chunk],
            "mean": float(np.mean(chunk)),
            "std": float(np.std(chunk, ddof=0)),
        }
    return out


def _baseline_by_room(summary: dict) -> dict[str, dict[str, dict]]:
    """method_key -> room_id -> row."""
    found: dict[str, dict[str, dict]] = {}
    for room_id, rows in summary["by_room"].items():
        for row in rows:
            found.setdefault(row["method_key"], {})[room_id] = row
    return found


def _rmse_from_baseline_files(method_key: str) -> list[float]:
    """Per-scenario RMSE from leaderboard_bpm, same source as figure redraw."""
    vals = []
    for sid in SCENARIO_IDS:
        path = REPORTS_DIR / f"ble_hkh_paper_baselines_{sid}.json"
        payload = _load(path)
        match = [r for r in payload["leaderboard_bpm"] if r["method_key"] == method_key]
        if len(match) != 1:
            raise KeyError(f"{sid}: {method_key} not unique in leaderboard_bpm ({len(match)})")
        rmse = match[0].get("rmse_mean")
        if rmse is None or not math.isfinite(float(rmse)):
            raise ValueError(f"{sid}: {method_key} rmse_mean is not finite")
        vals.append(float(rmse))
    return vals


def _rmse_from_ablation_files(method_key: str) -> list[float]:
    vals = []
    for sid in SCENARIO_IDS:
        path = REPORTS_DIR / f"ble_hkh_draft_ablation_{sid}.json"
        payload = _load(path)
        row = payload["methods"][method_key]
        rmse = row.get("rmse_mean")
        if rmse is None or not math.isfinite(float(rmse)):
            raise ValueError(f"{sid}: {method_key} rmse_mean is not finite")
        vals.append(float(rmse))
    return vals


def _std_pair(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    ddof1 = float(np.std(arr, ddof=1)) if n > 1 else float("nan")
    ddof0 = float(np.std(arr, ddof=0))
    scale = math.sqrt((n - 1) / n) if n > 1 else float("nan")
    converted = ddof1 * scale
    if not math.isclose(converted, ddof0, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError(f"ddof conversion mismatch: {converted} vs {ddof0}")
    return {
        "n": n,
        "values": [float(x) for x in arr],
        "mean": float(np.mean(arr)),
        "std_ddof1": ddof1,
        "std_ddof0": ddof0,
        "std_ddof0_from_ddof1_scale": float(converted),
        "scale_sqrt_nm1_over_n": float(scale),
    }


def _r3(x: float) -> float:
    return float(f"{x:.3f}")


def main() -> None:
    ablation = _load(REPORTS_DIR / "ble_hkh_draft_ablation_summary.json")
    baselines = _load(REPORTS_DIR / "ble_hkh_paper_baselines_summary.json")
    if baselines["scenario_ids"] != SCENARIO_IDS:
        raise AssertionError("scenario_ids differ from plan order")

    by_room = _baseline_by_room(baselines)
    methods_out = {}
    hand_mismatches = []

    for slug, label, key, source in TABLE_63B:
        if source == "ablation":
            per = [float(x) for x in ablation["methods"][key]["bpm_per_scenario"]]
            stats = _room_stats(per)
            src = f"{key}.bpm_per_scenario"
        else:
            stats = {}
            for room_key, room_id, room_label, _a, _b in ROOMS:
                row = by_room[key][room_id]
                stats[room_key] = {
                    "room_id": room_id,
                    "label": room_label,
                    "n": int(row["n_scenarios"]),
                    "mean": float(row["bpm_mean_abs_err"]),
                    "std": float(row["bpm_std_across_scenarios"]),
                }
            src = f"ble_hkh_paper_baselines_summary.json by_room[*].{key}"

        if slug in HAND_CHECK:
            for room_key, (exp_mean, exp_std) in HAND_CHECK[slug].items():
                got_mean = stats[room_key]["mean"]
                got_std = stats[room_key]["std"]
                if abs(got_mean - exp_mean) > 0.0015 or abs(got_std - exp_std) > 0.0015:
                    hand_mismatches.append(
                        {
                            "method": slug,
                            "room": room_key,
                            "expected_mean": exp_mean,
                            "got_mean": got_mean,
                            "expected_std": exp_std,
                            "got_std": got_std,
                        }
                    )

        methods_out[slug] = {
            "label": label,
            "source_key": key,
            "source": src,
            "per_room": stats,
        }

    table_64 = {}
    published_mismatches = []
    for slug, label, key, source in TABLE_64:
        if source == "ablation":
            vals = _rmse_from_ablation_files(key)
            src = f"ble_hkh_draft_ablation_{{scenario}}.json methods.{key}.rmse_mean"
        else:
            vals = _rmse_from_baseline_files(key)
            src = (
                "ble_hkh_paper_baselines_{scenario}.json "
                f"leaderboard_bpm[{key}].rmse_mean"
            )
        pair = _std_pair(vals)
        published = TABLE_64_PUBLISHED_DDOF1[slug]
        rounded_ddof1 = _r3(pair["std_ddof1"])
        if published is not None and rounded_ddof1 != published:
            published_mismatches.append(
                {
                    "method": slug,
                    "published_ddof1": published,
                    "recomputed_ddof1_rounded": rounded_ddof1,
                    "recomputed_ddof1": pair["std_ddof1"],
                }
            )
        table_64[slug] = {
            "label": label,
            "source_key": key,
            "source": src,
            "ddof_in_redraw_script": 1,
            "redraw_script": "notebooks/scripts/chFusion_paper_figure_redraw.py",
            "published_std_ddof1": published,
            "std_ddof0_rounded": _r3(pair["std_ddof0"]),
            "std_ddof1_rounded": rounded_ddof1,
            **pair,
        }

    if hand_mismatches:
        raise AssertionError(f"hand-check failed: {hand_mismatches}")
    if published_mismatches:
        raise AssertionError(f"Table 6.4 published std mismatch: {published_mismatches}")

    payload = {
        "metric": "bpm_abs_err",
        "grouping": "room (Living sitting / Bedroom flat / Bedroom side), 4 subjects each",
        "ddof": 0,
        "scenario_ids": SCENARIO_IDS,
        "scenario_order_source": "ble_hkh_paper_baselines_summary.json scenario_ids; matches chFusion_paper_ablation_draft.py SCENARIO_IDS",
        "methods": methods_out,
        "table_64_waveform_rmse": {
            "metric": "waveform_rmse",
            "n_scenarios": 12,
            "ddof": 0,
            "note": (
                "Published Table 6.4 std values match np.std(per-scenario rmse, ddof=1) "
                "from chFusion_paper_figure_redraw.py. ddof=0 = ddof=1 * sqrt(11/12)."
            ),
            "methods": table_64,
        },
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_PATH}")
    print("\nTable 6.3-B per-room (mean, std ddof=0), rounded to 3 decimals:")
    for slug, _label, _key, _source in TABLE_63B:
        rooms = methods_out[slug]["per_room"]
        cells = []
        for room_key, *_rest in ROOMS:
            cell = rooms[room_key]
            cells.append(f"{cell['mean']:.3f} ({cell['std']:.3f})")
        print(f"  {methods_out[slug]['label']}: " + " | ".join(cells))

    print("\nTable 6.4 RMSE std ddof=0 (from ddof=1 * sqrt(11/12)):")
    for slug, _label, _key, _source in TABLE_64:
        row = table_64[slug]
        print(
            f"  {row['label']}: mean {row['mean']:.3f} | "
            f"std ddof1 {row['std_ddof1']:.6f} -> {row['std_ddof1_rounded']:.3f} | "
            f"std ddof0 {row['std_ddof0']:.6f} -> {row['std_ddof0_rounded']:.3f}"
        )


if __name__ == "__main__":
    main()
