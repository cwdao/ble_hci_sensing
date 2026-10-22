"""Redraw Chapter 6 paper figures with paper-facing method names.

Does NOT re-run experiments — reads existing JSON summaries.

Default entry point (plan: docs/plans/paper_ch6_tables_to_figures_plan.md):
    python notebooks/scripts/chFusion_paper_figure_redraw.py

Writes Fig 6a, Fig 6b, and the Table 6.4 RMSE leaderboard only.
Does not touch Fig 7 or the Fig 8 ablation panels.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.bootstrap import init_notebook
from ble_analysis.paper_naming import (
    ABLATION_GROUPS,
    FIG7_METHOD_KEYS,
    GROUP_COLORS,
    RMSE_FIG6_4_KEYS,
    RMSE_TABLE_KEYS,
    WATERFALL_B1_REF_KEY,
    WATERFALL_STEPS,
    paper_color,
    paper_group,
    paper_label,
)

_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]

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

ROOM_LABELS = {
    "room_A": "Room A\n(Living, sitting)",
    "room_B": "Room B\n(Bedroom, flat)",
    "room_C": "Room C\n(Bedroom, side)",
}

ROOM_OF_SCENARIO = {sid: sid.split("-")[0] for sid in SCENARIO_IDS}

# Fig 6a / 6b method set. BPM numbers are read from per-scenario series
# (ablation summary or baseline scenario files), never hardcoded.
# slug matches paper_table63b_per_room_std.json → methods.
CH6_BPM_METHODS = (
    ("breathecs", "BreatheCS", "draft_s_rl", "BreatheCS", "ablation"),
    ("breathecs_wave", "BreatheCS-Wave", "draft_w_rl", "BreatheCS", "ablation"),
    ("pos_free_pca", "Pos-Free (PCA)", "z1_no_vmd", "Pos-Free", "baseline"),
    ("wifi_sleep_mrc_pca", "WiFi-Sleep (MRC-PCA)", "mrc_pca_eta_equal_pca", "WiFi-Sleep", "baseline"),
    ("wifi_sleep_sqrt_eta", "WiFi-Sleep (√η)", "mrc_pca_eta_sqrt", "WiFi-Sleep", "baseline"),
    ("pca_sign_only", "PCA sign only", "b2_a0_pca_sign", "Ablation", "baseline"),
    ("clessbreath_eta_linear", "ClessBreath (η-linear)", "fan_eta_linear", "ClessBreath", "baseline"),
    ("clessbreath_eta_equal", "ClessBreath (η-equal)", "fan_eta_equal_wf", "ClessBreath", "baseline"),
)

CH6_ROOM_ORDER = ("living", "bedroom_flat", "bedroom_side")
# Same order as SCENARIO_IDS: room_A, room_B, room_C, four subjects each.
CH6_ROOM_SLICES = {
    "living": (0, 4),
    "bedroom_flat": (4, 8),
    "bedroom_side": (8, 12),
}

# Fig 6.4 bar color. draft_w_rl is labeled BreatheCS on this figure.
CH6_RMSE_GROUP = {
    "draft_w_rl": "BreatheCS",
    "fan_eta_linear": "ClessBreath",
    "fan_eta_equal_wf": "ClessBreath",
    "mrc_pca_eta_sqrt": "WiFi-Sleep",
    "mrc_pca_eta_equal_pca": "WiFi-Sleep",
    "z1_no_vmd": "Pos-Free",
    "b2_a0_pca_sign": "Ablation",
}


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _save_figure(fig: plt.Figure, stem: str) -> Path:
    png_path = FIGURES_DIR / f"{stem}.png"
    pdf_path = FIGURES_DIR / f"{stem}.pdf"
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    return png_path


def _finite(x) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def load_unified_catalog() -> Dict[str, dict]:
    """Merge paper-baselines + B3 simplified (+ full ablation) into one catalog."""
    paper = json.loads(
        (REPORTS_DIR / "ble_hkh_paper_baselines_summary.json").read_text(encoding="utf-8")
    )
    b3s = json.loads(
        (REPORTS_DIR / "ble_hkh_b3_simplified_validation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    b3full = json.loads(
        (REPORTS_DIR / "ble_hkh_b3_validation_summary.json").read_text(encoding="utf-8")
    )

    catalog: Dict[str, dict] = {}

    for row in paper["overall_leaderboard"]:
        key = row["method_key"]
        catalog[key] = {
            "method_key": key,
            "bpm_mean": float(row["bpm_mean_abs_err"]),
            "bpm_std": float(row["bpm_std_across_scenarios"]),
            "rmse_mean": float(row["rmse_mean"]) if _finite(row.get("rmse_mean")) else None,
            "rmse_std": None,
            "bpm_per_scenario": None,
            "rmse_per_scenario": None,
            "source": "paper_baselines",
        }

    for key, row in b3s["methods"].items():
        bpm = float(row["bpm_mean_abs_err"])
        bpm_std = float(row["bpm_std_abs_err"])
        rmse = float(row["rmse_mean"]) if _finite(row.get("rmse_mean")) else None
        bpm_ps = [float(x) for x in row.get("bpm_per_scenario") or []]
        rmse_ps = [float(x) for x in row.get("rmse_per_scenario") or []]
        catalog[key] = {
            "method_key": key,
            "bpm_mean": bpm,
            "bpm_std": float(np.std(bpm_ps, ddof=1)) if len(bpm_ps) > 1 else bpm_std,
            "rmse_mean": rmse,
            "rmse_std": float(np.std(rmse_ps, ddof=1)) if len(rmse_ps) > 1 else None,
            "bpm_per_scenario": bpm_ps or None,
            "rmse_per_scenario": rmse_ps or None,
            "source": "b3_simplified",
        }

    # Ablation-only keys from full validation (do not overwrite BreatheCS family)
    for key, row in b3full["methods"].items():
        if key in catalog and key in ("b3_b1_equal", "b1_vote_modal_equal", "b2_d_two_level"):
            continue
        bpm = float(row["bpm_mean_abs_err"])
        bpm_std = float(row.get("bpm_std_abs_err") or 0.0)
        rmse = float(row["rmse_mean"]) if _finite(row.get("rmse_mean")) else None
        bpm_ps = [float(x) for x in row.get("bpm_per_scenario") or []]
        rmse_ps = [float(x) for x in row.get("rmse_per_scenario") or []]
        entry = {
            "method_key": key,
            "bpm_mean": bpm,
            "bpm_std": float(np.std(bpm_ps, ddof=1)) if len(bpm_ps) > 1 else bpm_std,
            "rmse_mean": rmse,
            "rmse_std": float(np.std(rmse_ps, ddof=1)) if len(rmse_ps) > 1 else None,
            "bpm_per_scenario": bpm_ps or None,
            "rmse_per_scenario": rmse_ps or None,
            "source": "b3_full_ablation",
        }
        # Prefer simplified numbers when both exist for shared keys (z1 etc.)
        if key not in catalog:
            catalog[key] = entry
        elif key.startswith("a"):
            catalog[key] = entry

    # Fill RMSE std for paper baselines from per-scenario files
    rmse_by_key: Dict[str, List[float]] = {k: [] for k in catalog}
    bpm_by_key_room: Dict[str, Dict[str, List[float]]] = {
        k: {"room_A": [], "room_B": [], "room_C": []} for k in catalog
    }

    for sid in SCENARIO_IDS:
        path = REPORTS_DIR / f"ble_hkh_paper_baselines_{sid}.json"
        if not path.exists():
            continue
        sc = json.loads(path.read_text(encoding="utf-8"))
        room = sc.get("room") or ROOM_OF_SCENARIO[sid]
        for row in sc["leaderboard_bpm"]:
            key = row["method_key"]
            if key not in catalog:
                continue
            if _finite(row.get("rmse_mean")):
                rmse_by_key[key].append(float(row["rmse_mean"]))
            if _finite(row.get("bpm_mean_abs_err")):
                bpm_by_key_room[key][room].append(float(row["bpm_mean_abs_err"]))

    for key, vals in rmse_by_key.items():
        if vals and catalog[key]["rmse_std"] is None:
            catalog[key]["rmse_std"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            if catalog[key]["rmse_mean"] is None:
                catalog[key]["rmse_mean"] = float(np.mean(vals))

    # Room aggregates for BreatheCS from per-scenario BPM
    for key, entry in catalog.items():
        bpm_ps = entry.get("bpm_per_scenario")
        if not bpm_ps or len(bpm_ps) != len(SCENARIO_IDS):
            continue
        for sid, bpm in zip(SCENARIO_IDS, bpm_ps):
            room = ROOM_OF_SCENARIO[sid]
            bpm_by_key_room[key][room].append(bpm)

    for key, rooms in bpm_by_key_room.items():
        catalog[key]["by_room"] = {
            room: {
                "bpm_mean": float(np.mean(vals)) if vals else None,
                "bpm_std": float(np.std(vals, ddof=1)) if len(vals) > 1 else (0.0 if vals else None),
                "n": len(vals),
            }
            for room, vals in rooms.items()
        }

    return catalog


def _load_report(name: str) -> dict:
    return json.loads((REPORTS_DIR / name).read_text(encoding="utf-8"))


def _nonneg_err(means, stds) -> np.ndarray:
    """Asymmetric whiskers. Lower side stops at 0; upper side is +std.

    The plotted values are absolute errors (or RMSE), so they cannot be
    negative. mean - std can still be negative when the cross-scenario
    spread is larger than the mean. The stored std is unchanged.
    """
    means = np.asarray(means, dtype=float)
    stds = np.asarray(stds, dtype=float)
    lower = np.minimum(stds, np.maximum(means, 0.0))
    return np.vstack([lower, stds])


def _mean_std0(values: Sequence[float]) -> Tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0 or not np.all(np.isfinite(arr)):
        raise ValueError("BPM/RMSE series is empty or non-finite")
    return float(np.mean(arr)), float(np.std(arr, ddof=0))


def _baseline_bpm_per_scenario(method_key: str) -> List[float]:
    vals: List[float] = []
    for sid in SCENARIO_IDS:
        payload = _load_report(f"ble_hkh_paper_baselines_{sid}.json")
        match = [r for r in payload["leaderboard_bpm"] if r["method_key"] == method_key]
        if len(match) != 1:
            raise KeyError(f"{sid}: {method_key} not unique in leaderboard_bpm ({len(match)})")
        vals.append(float(match[0]["bpm_mean_abs_err"]))
    return vals


def load_ch6_bpm_rows() -> List[dict]:
    """Eight Fig 6a methods. mean/std from the 12-scenario series, ddof=0."""
    ablation = _load_report("ble_hkh_draft_ablation_summary.json")
    rows = []
    for slug, label, key, group, source in CH6_BPM_METHODS:
        if source == "ablation":
            series = [float(x) for x in ablation["methods"][key]["bpm_per_scenario"]]
            src = f"ble_hkh_draft_ablation_summary.json methods.{key}.bpm_per_scenario"
        else:
            series = _baseline_bpm_per_scenario(key)
            src = f"ble_hkh_paper_baselines_{{scenario}}.json leaderboard_bpm[{key}]"
        mean, std = _mean_std0(series)
        rows.append(
            {
                "slug": slug,
                "method_key": key,
                "label": label,
                "group": group,
                "color": GROUP_COLORS[group],
                "bpm_mean": mean,
                "bpm_std": std,
                "series": series,
                "n": len(series),
                "source": src,
            }
        )
    rows.sort(key=lambda r: r["bpm_mean"])
    return rows


def _legend_handles() -> List[Patch]:
    return [
        Patch(facecolor=GROUP_COLORS["BreatheCS"], label="BreatheCS"),
        Patch(facecolor=GROUP_COLORS["Pos-Free"], label="Pos-Free"),
        Patch(facecolor=GROUP_COLORS["WiFi-Sleep"], label="WiFi-Sleep"),
        Patch(facecolor=GROUP_COLORS["ClessBreath"], label="ClessBreath"),
        Patch(facecolor=GROUP_COLORS["Ablation"], label="Ablation / simple"),
    ]


def plot_fig6a(rows: Optional[List[dict]] = None) -> Tuple[Path, List[dict]]:
    """Horizontal BPM leaderboard. No star, no in-figure title."""
    if rows is None:
        rows = load_ch6_bpm_rows()

    labels = [r["label"] for r in rows][::-1]
    means = [r["bpm_mean"] for r in rows][::-1]
    stds = [r["bpm_std"] for r in rows][::-1]
    colors = [r["color"] for r in rows][::-1]

    fig_h = max(4.5, 0.45 * len(labels))
    fig, ax = plt.subplots(figsize=(9.5, fig_h))
    y = np.arange(len(labels))
    for i, (mean, std, color) in enumerate(zip(means, stds, colors)):
        ax.barh(
            y[i],
            mean,
            xerr=_nonneg_err([mean], [std]),
            color=color,
            ecolor="black",
            capsize=3,
            alpha=0.92,
            height=0.7,
            error_kw={"elinewidth": 1.0, "capthick": 1.0},
        )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlim(left=0)
    ax.set_xlabel("Mean BPM absolute error (breaths/min) across 12 scenarios")
    ax.legend(handles=_legend_handles(), loc="upper right", fontsize=8, framealpha=0.9)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig6a_bpm_leaderboard")
    plt.close(fig)
    return path, rows


def plot_fig6b(rows: Optional[List[dict]] = None) -> Tuple[Path, List[dict]]:
    """Grouped bars by room. Same methods as Fig 6a, plus per-room std."""
    if rows is None:
        rows = load_ch6_bpm_rows()
    table = _load_report("paper_table63b_per_room_std.json")
    methods = table["methods"]

    room_labels = [methods[rows[0]["slug"]]["per_room"][k]["label"] for k in CH6_ROOM_ORDER]
    cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    x = np.arange(len(rows))
    width = 0.8 / len(CH6_ROOM_ORDER)
    fig, ax = plt.subplots(figsize=(12.5, 5.4))
    room_payload = []
    for i, room_key in enumerate(CH6_ROOM_ORDER):
        means = []
        stds = []
        for row in rows:
            cell = methods[row["slug"]]["per_room"][room_key]
            means.append(float(cell["mean"]))
            stds.append(float(cell["std"]))
        offset = (i - (len(CH6_ROOM_ORDER) - 1) / 2) * width
        color = cycle[i % len(cycle)]
        ax.bar(
            x + offset,
            means,
            width,
            yerr=_nonneg_err(means, stds),
            label=room_labels[i],
            color=color,
            ecolor="black",
            capsize=2,
            alpha=0.9,
            error_kw={"elinewidth": 0.8, "capthick": 0.8},
        )
        room_payload.append(
            {
                "room_key": room_key,
                "label": room_labels[i],
                "methods": [
                    {"slug": row["slug"], "label": row["label"], "mean": m, "std": s}
                    for row, m, s in zip(rows, means, stds)
                ],
            }
        )

    ax.set_xticks(x)
    ax.set_xticklabels([r["label"] for r in rows], rotation=25, ha="right", fontsize=8)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Mean BPM abs err (breaths/min)")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig6b_bpm_by_room")
    plt.close(fig)
    return path, room_payload


def plot_rmse_leaderboard() -> Tuple[Path, List[dict]]:
    """Table 6.4 as a horizontal bar chart. One BreatheCS row (waveform RMSE)."""
    block = _load_report("paper_table63b_per_room_std.json")["table_64_waveform_rmse"]["methods"]
    by_key = {row["source_key"]: (slug, row) for slug, row in block.items()}
    missing = [k for k in RMSE_FIG6_4_KEYS if k not in by_key]
    if missing:
        raise KeyError(f"table_64_waveform_rmse missing source keys: {missing}")

    rows = []
    for key in RMSE_FIG6_4_KEYS:
        slug, row = by_key[key]
        group = CH6_RMSE_GROUP[key]
        rows.append(
            {
                "slug": slug,
                "method_key": key,
                "label": row["label"],
                "group": group,
                "color": GROUP_COLORS[group],
                "rmse_mean": float(row["mean"]),
                "rmse_std": float(row["std_ddof0"]),
                "n": int(row["n"]),
                "source": row["source"],
            }
        )
    rows.sort(key=lambda r: r["rmse_mean"])

    labels = [r["label"] for r in rows][::-1]
    means = [r["rmse_mean"] for r in rows][::-1]
    stds = [r["rmse_std"] for r in rows][::-1]
    colors = [r["color"] for r in rows][::-1]

    fig_h = max(4.2, 0.48 * len(labels))
    fig, ax = plt.subplots(figsize=(9.5, fig_h))
    y = np.arange(len(labels))
    for i, (mean, std, color) in enumerate(zip(means, stds, colors)):
        ax.barh(
            y[i],
            mean,
            xerr=_nonneg_err([mean], [std]),
            color=color,
            ecolor="black",
            capsize=3,
            alpha=0.92,
            height=0.7,
            error_kw={"elinewidth": 1.0, "capthick": 1.0},
        )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlim(left=0)
    ax.set_xlabel("Waveform RMSE")
    ax.legend(handles=_legend_handles(), loc="lower right", fontsize=8, framealpha=0.9)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig6_4_rmse_leaderboard")
    plt.close(fig)
    return path, rows


def _paint_boxes(bp, colors: Sequence[str]) -> None:
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_edgecolor("black")
        patch.set_alpha(0.9)
    for line in bp["medians"]:
        line.set_color("black")
        line.set_linewidth(1.2)
    for key in ("whiskers", "caps"):
        for line in bp[key]:
            line.set_color("black")
            line.set_linewidth(1.0)
    for flier in bp["fliers"]:
        flier.set(
            marker="o",
            markerfacecolor="black",
            markeredgecolor="black",
            markersize=3.5,
            alpha=0.85,
        )


def _rmse_per_scenario(method_key: str) -> List[float]:
    """12 scenario RMSEs. Ablation key is read from ablation files; others from baselines."""
    vals: List[float] = []
    for sid in SCENARIO_IDS:
        if method_key == "draft_w_rl":
            payload = _load_report(f"ble_hkh_draft_ablation_{sid}.json")
            rmse = payload["methods"][method_key].get("rmse_mean")
        else:
            payload = _load_report(f"ble_hkh_paper_baselines_{sid}.json")
            match = [r for r in payload["leaderboard_bpm"] if r["method_key"] == method_key]
            if len(match) != 1:
                raise KeyError(f"{sid}: {method_key} not unique in leaderboard_bpm ({len(match)})")
            rmse = match[0].get("rmse_mean")
        if rmse is None or not math.isfinite(float(rmse)):
            raise ValueError(f"{sid}: {method_key} rmse_mean is not finite")
        vals.append(float(rmse))
    return vals


def load_ch6_rmse_rows() -> List[dict]:
    block = _load_report("paper_table63b_per_room_std.json")["table_64_waveform_rmse"]["methods"]
    by_key = {row["source_key"]: (slug, row) for slug, row in block.items()}
    rows = []
    for key in RMSE_FIG6_4_KEYS:
        slug, row = by_key[key]
        series = _rmse_per_scenario(key)
        group = CH6_RMSE_GROUP[key]
        rows.append(
            {
                "slug": slug,
                "method_key": key,
                "label": row["label"],
                "group": group,
                "color": GROUP_COLORS[group],
                "rmse_mean": float(row["mean"]),
                "rmse_std": float(row["std_ddof0"]),
                "series": series,
            }
        )
    rows.sort(key=lambda r: r["rmse_mean"])
    return rows


def plot_fig6a_box(rows: Optional[List[dict]] = None) -> Path:
    """Box plot of the 12 per-scenario BPM absolute errors. Does not replace Fig 6a."""
    if rows is None:
        rows = load_ch6_bpm_rows()
    shown = list(reversed(rows))
    data = [r["series"] for r in shown]
    labels = [r["label"] for r in shown]
    colors = [r["color"] for r in shown]
    y = np.arange(len(shown))
    fig_h = max(4.5, 0.45 * len(labels))
    fig, ax = plt.subplots(figsize=(9.5, fig_h))
    bp = ax.boxplot(
        data,
        vert=False,
        positions=y,
        widths=0.6,
        patch_artist=True,
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "black", "markeredgecolor": "black", "markersize": 4},
        manage_ticks=False,
    )
    _paint_boxes(bp, colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_ylim(-0.6, len(shown) - 0.4)
    ax.set_xlim(left=0)
    ax.set_xlabel("BPM absolute error (breaths/min) across 12 scenarios")
    handles = _legend_handles() + [plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="black", markersize=4, label="mean")]
    ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig6a_bpm_leaderboard_box")
    plt.close(fig)
    return path


def plot_fig6b_box(rows: Optional[List[dict]] = None) -> Path:
    """Per-room box plots (4 subjects each). Does not replace Fig 6b."""
    if rows is None:
        rows = load_ch6_bpm_rows()
    table = _load_report("paper_table63b_per_room_std.json")
    methods = table["methods"]
    room_labels = [methods[rows[0]["slug"]]["per_room"][k]["label"] for k in CH6_ROOM_ORDER]
    cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    x = np.arange(len(rows))
    width = 0.24
    fig, ax = plt.subplots(figsize=(12.5, 5.4))
    legend_handles = []
    for i, room_key in enumerate(CH6_ROOM_ORDER):
        lo, hi = CH6_ROOM_SLICES[room_key]
        data = [r["series"][lo:hi] for r in rows]
        if any(len(chunk) != hi - lo for chunk in data):
            raise ValueError(f"{room_key} slice is not length {hi - lo}")
        positions = x + (i - 1) * width
        color = cycle[i % len(cycle)]
        bp = ax.boxplot(
            data,
            positions=positions,
            widths=width * 0.9,
            patch_artist=True,
            showmeans=True,
            meanprops={"marker": "o", "markerfacecolor": "black", "markeredgecolor": "black", "markersize": 3.5},
            manage_ticks=False,
        )
        _paint_boxes(bp, [color] * len(data))
        legend_handles.append(Patch(facecolor=color, edgecolor="black", label=room_labels[i]))
    ax.set_xticks(x)
    ax.set_xticklabels([r["label"] for r in rows], rotation=25, ha="right", fontsize=8)
    ax.set_xlim(-0.5, len(rows) - 0.5)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("BPM absolute error (breaths/min)")
    legend_handles.append(plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="black", markersize=4, label="mean"))
    ax.legend(handles=legend_handles, fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig6b_bpm_by_room_box")
    plt.close(fig)
    return path


def plot_rmse_box(rows: Optional[List[dict]] = None) -> Path:
    """Box plot of the 12 per-scenario RMSEs. Does not replace Fig 6.4."""
    if rows is None:
        rows = load_ch6_rmse_rows()
    shown = list(reversed(rows))
    data = [r["series"] for r in shown]
    labels = [r["label"] for r in shown]
    colors = [r["color"] for r in shown]
    y = np.arange(len(shown))
    fig_h = max(4.2, 0.48 * len(labels))
    fig, ax = plt.subplots(figsize=(9.5, fig_h))
    bp = ax.boxplot(
        data,
        vert=False,
        positions=y,
        widths=0.6,
        patch_artist=True,
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "black", "markeredgecolor": "black", "markersize": 4},
        manage_ticks=False,
    )
    _paint_boxes(bp, colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_ylim(-0.6, len(shown) - 0.4)
    ax.set_xlim(left=0)
    ax.set_xlabel("Waveform RMSE")
    handles = _legend_handles() + [plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="black", markersize=4, label="mean")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3, fontsize=8, frameon=False)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig6_4_rmse_leaderboard_box")
    plt.close(fig)
    return path


def plot_chapter6_box() -> Dict[str, str]:
    """Write box-plot copies only. Existing Fig 6 bar charts are left in place."""
    rows = load_ch6_bpm_rows()
    paths = {
        "fig6a_box": str(plot_fig6a_box(rows)),
        "fig6b_box": str(plot_fig6b_box(rows)),
        "fig6_4_box": str(plot_rmse_box()),
    }
    out = REPORTS_DIR / "paper_ch6_tables_to_figures_results.json"
    payload = {}
    if out.exists():
        payload = json.loads(out.read_text(encoding="utf-8"))
    payload["box_figures"] = {
        "note": "Per-scenario distribution. Median line, black dot = mean. Does not replace the bar charts.",
        "whis": 1.5,
        "figures": paths,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return paths


def build_rmse_table(catalog: Dict[str, dict]) -> List[dict]:
    rows = []
    for key in RMSE_TABLE_KEYS:
        if key not in catalog:
            continue
        e = catalog[key]
        if e["rmse_mean"] is None:
            continue
        rows.append(
            {
                "method_key": key,
                "label": paper_label(key),
                "rmse_mean": e["rmse_mean"],
                "rmse_std": e["rmse_std"] if e["rmse_std"] is not None else float("nan"),
                "bpm_mean": e["bpm_mean"],
            }
        )
    rows.sort(key=lambda r: r["rmse_mean"])
    return rows


def plot_fig7(catalog: Dict[str, dict]) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    plotted = []
    for key in FIG7_METHOD_KEYS:
        if key not in catalog:
            continue
        e = catalog[key]
        if e["rmse_mean"] is None:
            continue  # skip BreatheCS-Spec etc.
        bpm, rmse = e["bpm_mean"], e["rmse_mean"]
        color = paper_color(key)
        if key == "b3_b1_equal":
            ax.scatter([bpm], [rmse], s=160, c=color, marker="*", zorder=5, edgecolors="k", linewidths=0.6)
        elif key == "b2_d_two_level":
            ax.scatter([bpm], [rmse], s=90, c=color, marker="D", zorder=4, edgecolors="k", linewidths=0.5)
        else:
            ax.scatter([bpm], [rmse], s=70, c=color, marker="o", zorder=3, alpha=0.9)
        ax.annotate(
            paper_label(key),
            (bpm, rmse),
            fontsize=8,
            xytext=(5, 5),
            textcoords="offset points",
        )
        plotted.append(key)

    ax.set_xlabel("BPM abs err (12-scenario mean)")
    ax.set_ylabel("Waveform RMSE mean (z-score aligned vs belt)")
    ax.grid(True, alpha=0.3)
    legend_handles = [
        plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="#E63946", markersize=14, label="BreatheCS"),
        plt.Line2D([0], [0], marker="D", color="w", markerfacecolor="#E63946", markersize=9, label="BreatheCS-Wave"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#777777", markersize=8, label="Baselines"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig7_bpm_vs_rmse")
    plt.close(fig)
    return path


def plot_fig8a(catalog: Dict[str, dict]) -> Tuple[Path, Path]:
    group_names = list(ABLATION_GROUPS.keys())
    # --- Layout A: single grouped bar ---
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(group_names))
    # Within each group, up to 3 methods — use positions within group
    # Better: for each group, plot bars for its methods with group labels on x
    # Use clustered bars where cluster = group, bars = ordered methods in group
    max_m = max(len(v) for v in ABLATION_GROUPS.values())
    width = 0.8 / max_m
    for j in range(max_m):
        vals = []
        colors = []
        labels_j = []
        for gname in group_names:
            keys = ABLATION_GROUPS[gname]
            if j < len(keys):
                key = keys[j]
                vals.append(catalog[key]["bpm_mean"] if key in catalog else np.nan)
                colors.append(paper_color(key) if key in catalog else "#cccccc")
                labels_j.append(paper_label(key) if key in catalog else "")
            else:
                vals.append(np.nan)
                colors.append("#cccccc")
                labels_j.append("")
        offset = (j - (max_m - 1) / 2) * width
        bars = ax.bar(x + offset, vals, width, color=colors, alpha=0.9, edgecolor="black", linewidth=0.4)
        for xi, (v, lab, key_ok) in enumerate(zip(vals, labels_j, [ABLATION_GROUPS[g][j] if j < len(ABLATION_GROUPS[g]) else None for g in group_names])):
            if not math.isfinite(v):
                continue
            ax.text(x[xi] + offset, v + 0.015, f"{v:.2f}", ha="center", va="bottom", fontsize=7, rotation=0)
            if key_ok == "b3_b1_equal":
                ax.text(x[xi] + offset, v / 2, "★", ha="center", va="center", fontsize=11, color="white", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(group_names, fontsize=10)
    ax.set_ylabel("BPM abs err (12-scenario mean)")
    # In-figure note only (not a figure title); caption carries the full description
    ax.text(
        0.01,
        0.98,
        "Within each group (left→right): simpler → fuller\n"
        "Channel: Single(best-η) → Equal voting → BreatheCS\n"
        "Modal: Remote-only → Equal spectral → BreatheCS\n"
        "Phase: PCA sign → Equal spectral → BreatheCS-Wave",
        transform=ax.transAxes,
        fontsize=7.5,
        va="top",
        ha="left",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.35),
    )
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path_a = _save_figure(fig, "paper_fig8a_ablation_hkh")
    plt.close(fig)

    # --- Layout B: 1×3 faceted (no sharey — each panel has distinct method labels) ---
    fig2, axes = plt.subplots(1, 3, figsize=(12.5, 4.2), sharey=False)
    for ax2, gname in zip(axes, group_names):
        keys = ABLATION_GROUPS[gname]
        labels = [paper_label(k) for k in keys]
        vals = [catalog[k]["bpm_mean"] for k in keys]
        colors = [paper_color(k) for k in keys]
        y = np.arange(len(keys))
        bars = ax2.barh(y, vals, color=colors, alpha=0.92, height=0.65)
        ax2.set_yticks(y)
        ax2.set_yticklabels(labels, fontsize=8)
        ax2.set_xlabel("BPM abs err")
        # Panel label only — descriptive title goes in caption
        ax2.set_title(f"({chr(ord('a') + list(group_names).index(gname))}) {gname}", fontsize=10)
        ax2.grid(True, axis="x", alpha=0.3)
        ax2.set_xlim(0, max(vals) * 1.25)
        for i, key in enumerate(keys):
            if key in ("b3_b1_equal", "b2_d_two_level"):
                bars[i].set_edgecolor("black")
                bars[i].set_linewidth(1.2)
                ax2.text(vals[i] + 0.01, i, "★", va="center", color="#E63946", fontsize=11)
            ax2.text(vals[i] + 0.02, i, f"{vals[i]:.2f}", va="center", fontsize=7, color="#333333")
    fig2.tight_layout()
    path_b = _save_figure(fig2, "paper_fig8a_ablation_hkh_faceted")
    plt.close(fig2)
    return path_a, path_b


def plot_fig8b() -> Path:
    cross_path = REPORTS_DIR / "b2_coherent_mrc_all_cross_domain.npy"
    cross_domain = list(np.load(cross_path, allow_pickle=True))

    def _lookup(key: str) -> dict:
        for row in cross_domain:
            if row["method_key"] == key:
                return row
        raise KeyError(key)

    steps = WATERFALL_STEPS
    values = [_lookup(key)["cross_domain_mean"] for key, _ in steps]
    deltas = [None] + [values[i] - values[i - 1] for i in range(1, len(values))]
    labels = [lab for _, lab in steps]

    fig, ax = plt.subplots(figsize=(10, 5.8))
    b1_ref = _lookup(WATERFALL_B1_REF_KEY)["cross_domain_mean"]
    ax.axhline(
        b1_ref,
        color="#E63946",
        linestyle="--",
        linewidth=1.3,
        label=f"{paper_label(WATERFALL_B1_REF_KEY)} (spectral BPM) {b1_ref:.2f}%",
    )

    running = values[0]
    for i, (lab, val, delta) in enumerate(zip(labels, values, deltas)):
        if i == 0:
            color = "#999999"
            ax.bar(i, val, color=color, alpha=0.85, width=0.55)
            ax.text(i, val + 0.15, f"{val:.2f}%", ha="center", fontsize=9)
        else:
            color = "#2ca02c" if delta < -0.05 else ("#d62728" if delta > 0.05 else "#aaaaaa")
            if delta >= 0:
                bottom = running
                height = delta
            else:
                bottom = val
                height = -delta
            ax.bar(i, height, bottom=bottom, color=color, alpha=0.85, width=0.55)
            ax.text(i, val + 0.2, f"{val:.2f}%\nΔ{delta:+.2f}", ha="center", va="bottom", fontsize=8)
            running = val
        if steps[i][0] == "b2_d_two_level":
            ax.text(i, values[i] / 2, "★", ha="center", va="center", color="white", fontsize=12, fontweight="bold")

    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Cross-domain mean BPM err %")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig8b_waterfall_cs")
    plt.close(fig)
    return path


def rmse_table_markdown(rows: List[dict]) -> str:
    lines = [
        "| Method | RMSE mean | RMSE std |",
        "|---|---:|---:|",
    ]
    for r in rows:
        std = r["rmse_std"]
        std_s = f"{std:.3f}" if _finite(std) else "—"
        star = " ★" if r["method_key"] == "b3_b1_equal" else ""
        lines.append(f"| {r['label']}{star} | {r['rmse_mean']:.3f} | {std_s} |")
    lines.append("")
    lines.append(
        "> Data: `ble_hkh_paper_baselines_summary.json` + "
        "`ble_hkh_b3_simplified_validation_summary.json` (12 HKH scenarios, z-score aligned vs belt)."
    )
    return "\n".join(lines)


def main() -> None:
    """Redraw Fig 6a / 6b / Table 6.4. Does not rewrite experiment summaries or Fig 7.

    `--box-only` writes `*_box` figures and does not touch the bar-chart files.
    """
    if "--box-only" in sys.argv:
        paths = plot_chapter6_box()
        print("=== Chapter 6 box plots (bar charts not rewritten) ===")
        for key, path in paths.items():
            print(f"{key}: {Path(path).name}")
        return

    rows6a = load_ch6_bpm_rows()
    fig6a, rows6a = plot_fig6a(rows6a)
    fig6b, rooms6b = plot_fig6b(rows6a)
    fig64, rows64 = plot_rmse_leaderboard()

    summary = {
        "plan": "docs/plans/paper_ch6_tables_to_figures_plan.md",
        "ddof": 0,
        "n_scenarios": 12,
        "figures": {
            "fig6a": str(fig6a),
            "fig6b": str(fig6b),
            "fig6_4": str(fig64),
        },
        "fig6a_methods": rows6a,
        "fig6b_rooms": rooms6b,
        "fig6_4_methods": rows64,
        "not_redrawn": [
            "paper_fig7_bpm_vs_rmse (shelved)",
            "paper_fig8_abc_fusion and paper_fig8_def_single_modal are written by chFusion_paper_ablation_draft.py --figures-only",
        ],
    }
    out = REPORTS_DIR / "paper_ch6_tables_to_figures_results.json"
    payload = {}
    if out.exists():
        payload = json.loads(out.read_text(encoding="utf-8"))
    payload.update(summary)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

    md_lines = [
        "## Waveform RMSE comparison (HKH, 12 scenarios)",
        "",
        "| Method | RMSE mean | RMSE std (ddof=0) |",
        "|---|---:|---:|",
    ]
    for r in rows64:
        md_lines.append(f"| {r['label']} | {r['rmse_mean']:.3f} | {r['rmse_std']:.3f} |")
    md_lines.append("")
    md_lines.append(
        "> Data: `outputs/reports/paper_table63b_per_room_std.json` "
        "`table_64_waveform_rmse` (12 HKH scenarios, `np.std(ddof=0)`). "
        "BreatheCS row is waveform-branch RMSE (`draft_w_rl`), not a separate BreatheCS-Wave row."
    )
    md_frag = REPORTS_DIR / "paper_fig6_4_rmse_table.md"
    md_frag.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("=== Chapter 6 figure redraw (6a / 6b / 6.4) ===")
    print(f"Fig 6a: {fig6a.name}")
    for r in rows6a:
        print(f"  {r['label']:<28} {r['bpm_mean']:.3f} ± {r['bpm_std']:.3f}")
    print(f"Fig 6b: {fig6b.name}")
    print(f"Fig 6.4: {fig64.name}")
    for r in rows64:
        print(f"  {r['label']:<28} {r['rmse_mean']:.3f} ± {r['rmse_std']:.3f}")
    print(f"Saved: {out}")
    print(f"Saved: {md_frag}")


if __name__ == "__main__":
    main()
