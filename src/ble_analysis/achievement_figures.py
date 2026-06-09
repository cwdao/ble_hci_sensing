"""Achievement-report summary figures for PCA→Voting method evolution.

Generates PNG figures listed in
``docs/achievements/pca_voting_comprehensive_achievement_report.md`` §9.3.
Uses descriptive method names (§5.2 / §9.1), not internal codes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

from ble_analysis.chfusion import _overall_rel_error

# --- Descriptive name mapping (§9.1 / §5.2) ---

VOTING_DESCRIPTIVE_NAMES: Dict[str, str] = {
    "t0_v3_eta_rho_weighted": "远程单模态 Per-Tone η·ρ 投票",
    "b2_modal_top2_equal": "逐模态最优信道 → Top2 等权谱融合",
    "b3_modal_eta_weight": "逐模态最优信道 → η 加权谱融合",
    "t3_voting_modal_hybrid": "逐模态 Voting → 跨模态 η 加权中位数",
    "b0_single_remote": "单信道 Remote 幅值（max-η 选道）",
    "t2_cross_modal_median": "逐模态最优信道 → 跨模态中位数",
    "t0_v1_simple": "远程单模态 Per-Tone 等权投票",
    "t0_v2_eta_weighted": "远程单模态 Per-Tone η 加权投票",
    "t1_k4_v2": "远程 Top-4 Per-Tone η 加权投票",
    "t1_k8_v2": "远程 Top-8 Per-Tone η 加权投票",
    "t1_k16_v2": "远程 Top-16 Per-Tone η 加权投票",
    "b1_uniform_remote": "远程 72 信道均匀谱融合",
}

PHASE_COLORS: Dict[str, str] = {
    "P0": "#4C72B0",
    "P1": "#DD8452",
    "P2": "#55A868",
    "P3": "#8172B3",
}

# Mainline 8 methods: (method_key, descriptive_name, phase, data_source)
MAINLINE_METHODS: Tuple[Tuple[str, str, str, str], ...] = (
    ("b1_vote_modal_equal", "逐模态 Voting → 三模态等权谱融合", "P2", "systematic"),
    ("c2_uniform_modal_eta", "逐模态均匀 → η 加权融合", "P2", "systematic"),
    ("b2_vote_modal_eta", "逐模态 Voting → η 加权融合", "P2", "systematic"),
    ("t0_v3_eta_rho_weighted", "远程单模态 Per-Tone η·ρ 投票", "P1", "voting"),
    ("b2_modal_top2_equal", "逐模态最优信道 → Top2 等权谱融合", "P1", "voting"),
    ("b3_vote_modal_top2", "逐模态 Voting → Top2 融合", "P2", "systematic"),
    ("b0_single_remote", "单信道 Remote 幅值（max-η 选道）", "P0", "voting"),
    ("pca_modal3_eta", "PCA-Modal3（PCA per modal → η 加权融合）", "P0", "pca"),
)

PCA_MODAL3_LABEL = "PCA-Modal3 η/ch-η"
PCA_MODAL3_KEY = "pca_modal3_eta"

EVOLUTION_TIMELINE: Tuple[Tuple[str, str, str, float], ...] = (
    ("P0", "PCA/SVD", "PCA-Modal3（PCA per modal → η 加权融合）", 10.922),
    ("P1", "Per-Tone 投票", "远程单模态 Per-Tone η·ρ 投票", 9.20),
    ("P2", "系统性融合", "逐模态 Voting → 三模态等权谱融合", 8.45),
    ("P3", "机制诊断", "物理机制确认（无新方法）", 8.45),
)

SCENARIO_IDS: Tuple[str, ...] = ("cs_091339", "cs_095806", "cs_102621")
SCENARIO_COLORS: Tuple[str, ...] = ("#4C72B0", "#55A868", "#C44E52")

__all__ = [
    "VOTING_DESCRIPTIVE_NAMES",
    "PHASE_COLORS",
    "MAINLINE_METHODS",
    "setup_cjk_font",
    "load_voting_cross_domain",
    "load_systematic_cross_domain",
    "load_pca_cross_domain",
    "lookup_cross_domain_mean",
    "plot_voting_fusion_leaderboard",
    "plot_voting_fusion_cross_domain_bars",
    "plot_method_evolution_timeline",
    "plot_method_evolution_full_leaderboard",
    "plot_all_achievement_figures",
]


def setup_cjk_font() -> None:
    """Configure matplotlib for Chinese labels on Windows/Linux."""
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def _load_npy(path: Path):
    data = np.load(path, allow_pickle=True)
    if isinstance(data, np.ndarray) and data.shape == ():
        return data.item()
    return data


def load_voting_cross_domain(reports_dir: Path) -> np.ndarray:
    return _load_npy(reports_dir / "voting_fusion_cross_domain.npy")


def load_systematic_cross_domain(reports_dir: Path) -> np.ndarray:
    return _load_npy(reports_dir / "systematic_fusion_cross_domain.npy")


def load_pca_cross_domain(reports_dir: Path) -> dict:
    return _load_npy(reports_dir / "chfusion_pca_svd_cross_domain.npy")


def _voting_descriptive(row: dict) -> str:
    key = row.get("method_key", "")
    return VOTING_DESCRIPTIVE_NAMES.get(key, row.get("label", key))


def lookup_cross_domain_mean(
    method_key: str,
    *,
    voting_cd: np.ndarray,
    systematic_cd: np.ndarray,
    pca_cd: dict,
) -> float:
    """Resolve cross-domain mean for a mainline method key."""
    if method_key == PCA_MODAL3_KEY:
        for row in pca_cd["cross_rows"]:
            if row["label"] == PCA_MODAL3_LABEL:
                return float(row["mean_across_domains"])
        raise KeyError(f"PCA label not found: {PCA_MODAL3_LABEL}")

    for row in systematic_cd:
        if row["method_key"] == method_key:
            return float(row["cross_domain_mean"])
    for row in voting_cd:
        if row["method_key"] == method_key:
            return float(row["cross_domain_mean"])
    raise KeyError(f"Method key not found: {method_key}")


def _save_fig(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", format="png")
    plt.close(fig)
    return path


def plot_voting_fusion_leaderboard(
    cross_domain: Sequence[dict],
    figures_dir: Path,
    *,
    top_n: Optional[int] = None,
) -> Path:
    """Phase 1 cross-domain leaderboard (horizontal bars, descriptive names)."""
    rows = list(cross_domain)
    if top_n is not None:
        rows = rows[:top_n]

    labels = [_voting_descriptive(r) for r in rows]
    means = [r["cross_domain_mean"] for r in rows]
    stds = [r.get("cross_domain_std", 0.0) for r in rows]
    colors = [r.get("color", "#888888") for r in rows]

    fig, ax = plt.subplots(figsize=(13, 7))
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, means, xerr=stds, color=colors, alpha=0.85, capsize=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("跨域 mean BPM 相对误差 (%)")
    ax.set_title("Phase 1 Per-Tone 投票 — 跨域排行榜（三金属板场景）")
    ax.axvline(9.45, color="gray", linestyle="--", linewidth=1, label="Modal top2 参考 (9.45%)")
    ax.legend(loc="lower right")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return _save_fig(fig, figures_dir / "voting_fusion_leaderboard.png")


def plot_voting_fusion_cross_domain_bars(
    cross_domain: Sequence[dict],
    results_by_scenario: dict,
    figures_dir: Path,
    *,
    top_n: int = 8,
) -> Path:
    """Phase 1 top methods — per-scenario grouped bars with descriptive names."""
    rows = list(cross_domain)[:top_n]
    labels = [_voting_descriptive(r) for r in rows]
    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(15, 6))
    for i, sid in enumerate(SCENARIO_IDS):
        vals = []
        for row in rows:
            stats = _overall_rel_error(results_by_scenario[sid]["results"], row["method_key"])
            vals.append(stats["mean_rel_err_pct"])
        ax.bar(
            x + (i - 1) * width,
            vals,
            width,
            label=sid,
            color=SCENARIO_COLORS[i],
            alpha=0.85,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=28, ha="right", fontsize=8)
    ax.set_ylabel("mean BPM 相对误差 (%)")
    ax.set_title("Phase 1 Per-Tone 投票 — 各场景 Top-8 方法对比")
    ax.legend(title="场景")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return _save_fig(fig, figures_dir / "voting_fusion_cross_domain_aggregate_bars.png")


def plot_method_evolution_timeline(figures_dir: Path) -> Path:
    """Best mainline method per phase: P0→P1→P2→P3 vs cross-domain mean err%."""
    phases = [t[0] for t in EVOLUTION_TIMELINE]
    means = [t[3] for t in EVOLUTION_TIMELINE]
    names = [t[2] for t in EVOLUTION_TIMELINE]
    colors = [PHASE_COLORS[p] for p in phases]

    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(phases))
    ax.plot(x, means, "o-", color="#333333", linewidth=2, markersize=10, zorder=2)
    for i, (phase, mean, name, color) in enumerate(
        zip(phases, means, names, colors)
    ):
        ax.scatter(i, mean, s=180, color=color, zorder=3, edgecolors="white", linewidths=1.5)
        ax.annotate(
            f"{mean:.2f}%",
            (i, mean),
            textcoords="offset points",
            xytext=(0, 12),
            ha="center",
            fontsize=10,
            fontweight="bold",
        )
        ax.annotate(
            name,
            (i, mean),
            textcoords="offset points",
            xytext=(0, -28 if i % 2 == 0 else -42),
            ha="center",
            fontsize=7.5,
            color="#444444",
            wrap=True,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(phases)
    ax.set_xlabel("阶段")
    ax.set_ylabel("跨域 mean BPM 相对误差 (%)")
    ax.set_title("方法演进时间线 — 各阶段最优主线方法")
    ax.set_ylim(7.5, 12.0)
    ax.grid(True, alpha=0.3)

    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor=PHASE_COLORS[p], label=f"{p} {EVOLUTION_TIMELINE[i][1]}")
        for i, p in enumerate(phases)
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8)
    fig.tight_layout()
    return _save_fig(fig, figures_dir / "method_evolution_timeline.png")


def plot_method_evolution_full_leaderboard(
    voting_cd: Sequence[dict],
    systematic_cd: Sequence[dict],
    pca_cd: dict,
    figures_dir: Path,
) -> Path:
    """All 8 mainline methods sorted by cross-domain mean, colored by phase."""
    entries: List[dict] = []
    for method_key, name, phase, _source in MAINLINE_METHODS:
        mean = lookup_cross_domain_mean(
            method_key,
            voting_cd=voting_cd,
            systematic_cd=systematic_cd,
            pca_cd=pca_cd,
        )
        entries.append(
            {
                "name": name,
                "phase": phase,
                "mean": mean,
                "color": PHASE_COLORS[phase],
            }
        )
    entries.sort(key=lambda e: e["mean"])

    labels = [e["name"] for e in entries]
    means = [e["mean"] for e in entries]
    colors = [e["color"] for e in entries]

    fig, ax = plt.subplots(figsize=(13, 7))
    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, means, color=colors, alpha=0.88)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("跨域 mean BPM 相对误差 (%)")
    ax.set_title("全阶段排行榜 — 主线 8 方法（按跨域 mean 升序）")

    for bar, val in zip(bars, means):
        ax.text(val + 0.08, bar.get_y() + bar.get_height() / 2, f"{val:.2f}%", va="center", fontsize=8)

    from matplotlib.patches import Patch

    phase_legend = [
        Patch(facecolor=PHASE_COLORS[p], label=label)
        for p, label in [("P0", "Phase 0: PCA/SVD"), ("P1", "Phase 1: Per-Tone 投票"),
                         ("P2", "Phase 2: 系统性融合"), ("P3", "Phase 3: 机制诊断")]
    ]
    ax.legend(handles=phase_legend, loc="lower right", fontsize=8)
    ax.axvline(8.45, color="gray", linestyle="--", linewidth=1, alpha=0.6)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return _save_fig(fig, figures_dir / "method_evolution_full_leaderboard.png")


def plot_all_achievement_figures(
    *,
    reports_dir: Path,
    figures_dir: Path,
) -> Dict[str, Path]:
    """Generate all §9.3 high-priority achievement figures."""
    setup_cjk_font()

    voting_cd = load_voting_cross_domain(reports_dir)
    systematic_cd = load_systematic_cross_domain(reports_dir)
    pca_cd = load_pca_cross_domain(reports_dir)
    voting_results = _load_npy(reports_dir / "voting_fusion_results.npy")

    paths = {
        "voting_leaderboard": plot_voting_fusion_leaderboard(voting_cd, figures_dir),
        "voting_cross_domain_bars": plot_voting_fusion_cross_domain_bars(
            voting_cd, voting_results, figures_dir
        ),
        "evolution_timeline": plot_method_evolution_timeline(figures_dir),
        "evolution_full_leaderboard": plot_method_evolution_full_leaderboard(
            voting_cd, systematic_cd, pca_cd, figures_dir
        ),
    }
    return paths
