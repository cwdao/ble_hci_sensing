"""Redraw Chapter 6 paper figures with paper-facing method names.

Does NOT re-run experiments — reads existing JSON / NPY summaries.

Run:
    python notebooks/scripts/chFusion_paper_figure_redraw.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    FIG6A_METHOD_KEYS,
    FIG7_METHOD_KEYS,
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


def plot_fig6a(catalog: Dict[str, dict]) -> Tuple[Path, List[dict], List[str]]:
    rows = []
    missing = []
    for key in FIG6A_METHOD_KEYS:
        if key not in catalog:
            missing.append(key)
            continue
        e = catalog[key]
        rows.append(
            {
                "method_key": key,
                "label": paper_label(key),
                "color": paper_color(key),
                "group": paper_group(key),
                "bpm_mean": e["bpm_mean"],
                "bpm_std": e["bpm_std"],
            }
        )
    rows.sort(key=lambda r: r["bpm_mean"])

    labels = [r["label"] for r in rows][::-1]
    means = [r["bpm_mean"] for r in rows][::-1]
    stds = [r["bpm_std"] for r in rows][::-1]
    colors = [r["color"] for r in rows][::-1]
    keys = [r["method_key"] for r in rows][::-1]

    fig_h = max(4.5, 0.45 * len(labels))
    fig, ax = plt.subplots(figsize=(9.5, fig_h))
    y = np.arange(len(labels))
    bars = ax.barh(y, means, xerr=stds, capsize=3, color=colors, alpha=0.92, height=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Mean BPM absolute error (breaths/min) across 12 scenarios")

    for i, key in enumerate(keys):
        if key == "b3_b1_equal":
            bars[i].set_edgecolor("black")
            bars[i].set_linewidth(1.4)
            ax.text(means[i] + stds[i] + 0.02, i, "★ BreatheCS", va="center", fontsize=9, fontweight="bold", color="#E63946")

    legend_handles = [
        Patch(facecolor="#E63946", label="BreatheCS"),
        Patch(facecolor="#81B29A", label="Pos-Free"),
        Patch(facecolor="#3D405B", label="WiFi-Sleep"),
        Patch(facecolor="#E07A5F", label="ClessBreath"),
        Patch(facecolor="#999999", label="Ablation / simple"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8, framealpha=0.9)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig6a_bpm_leaderboard")
    plt.close(fig)
    return path, rows, missing


def plot_fig6b(catalog: Dict[str, dict]) -> Path:
    """Per-room BPM for the same method set as Fig 6a (incl. ClessBreath)."""
    top_keys = [k for k in FIG6A_METHOD_KEYS if k in catalog]
    # Sort by overall BPM so axis order matches Fig 6a narrative
    top_keys.sort(key=lambda k: catalog[k]["bpm_mean"])

    rooms = ["room_A", "room_B", "room_C"]
    x = np.arange(len(top_keys))
    width = 0.8 / len(rooms)
    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    for i, room in enumerate(rooms):
        vals = []
        for key in top_keys:
            br = catalog[key].get("by_room", {}).get(room, {})
            vals.append(br.get("bpm_mean") if br.get("bpm_mean") is not None else np.nan)
        offset = (i - (len(rooms) - 1) / 2) * width
        ax.bar(x + offset, vals, width, label=ROOM_LABELS[room].replace("\n", " "), alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels([paper_label(k) for k in top_keys], rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Mean BPM abs err (breaths/min)")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = _save_figure(fig, "paper_fig6b_bpm_by_room")
    plt.close(fig)
    return path


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
    catalog = load_unified_catalog()
    fig6a, rows6a, missing6a = plot_fig6a(catalog)
    fig6b = plot_fig6b(catalog)
    rmse_rows = build_rmse_table(catalog)
    fig7 = plot_fig7(catalog)
    fig8a, fig8a_faceted = plot_fig8a(catalog)
    fig8b = plot_fig8b()

    # Consistency check: B2-D RMSE in both sources
    paper = json.loads(
        (REPORTS_DIR / "ble_hkh_paper_baselines_summary.json").read_text(encoding="utf-8")
    )
    b3s = json.loads(
        (REPORTS_DIR / "ble_hkh_b3_simplified_validation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    paper_b2 = next(r for r in paper["overall_leaderboard"] if r["method_key"] == "b2_d_two_level")
    b3_b2 = b3s["methods"]["b2_d_two_level"]
    rmse_delta = abs(float(paper_b2["rmse_mean"]) - float(b3_b2["rmse_mean"]))

    summary = {
        "figures": {
            "fig6a": str(fig6a),
            "fig6b": str(fig6b),
            "fig7": str(fig7),
            "fig8a": str(fig8a),
            "fig8a_faceted": str(fig8a_faceted),
            "fig8b": str(fig8b),
        },
        "fig6a_methods": rows6a,
        "fig6a_missing_keys": missing6a,
        "rmse_table": rmse_rows,
        "rmse_table_markdown": rmse_table_markdown(rmse_rows),
        "consistency": {
            "b2_d_rmse_paper": float(paper_b2["rmse_mean"]),
            "b2_d_rmse_b3": float(b3_b2["rmse_mean"]),
            "b2_d_rmse_abs_delta": rmse_delta,
            "breathecs_bpm": catalog["b3_b1_equal"]["bpm_mean"],
            "breathecs_rmse": catalog["b3_b1_equal"]["rmse_mean"],
            "breathecs_wave_bpm": catalog["b2_d_two_level"]["bpm_mean"],
        },
        "notes": [
            "Single (Remote) / r12_d_single_remote omitted from Fig 6a: no HKH abs-BPM in paper_baselines JSON.",
            "BreatheCS BPM from spectral branch (b3_b1_equal = 0.405), not waveform branch.",
            "Fig 8b uses CS metal-plate relative BPM err %; Fig 8a uses HKH abs BPM.",
        ],
    }
    out = REPORTS_DIR / "paper_figure_redraw_results.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

    md_frag = REPORTS_DIR / "paper_fig6_4_rmse_table.md"
    md_frag.write_text(
        "## Waveform RMSE comparison (HKH, 12 scenarios)\n\n" + rmse_table_markdown(rmse_rows) + "\n",
        encoding="utf-8",
    )

    print("=== Paper figure redraw ===")
    print(f"Fig 6a: {fig6a.name}  methods={len(rows6a)} missing={missing6a}")
    print(f"Fig 6b: {fig6b.name}")
    print(f"Fig 7:  {fig7.name}")
    print(f"Fig 8a: {fig8a.name} / {fig8a_faceted.name}")
    print(f"Fig 8b: {fig8b.name}")
    print(f"B2-D RMSE delta (paper vs b3): {rmse_delta:.6f}")
    print(f"Saved: {out}")
    print(f"Saved: {md_frag}")
    print("\nRMSE table:")
    print(rmse_table_markdown(rmse_rows))


if __name__ == "__main__":
    main()
