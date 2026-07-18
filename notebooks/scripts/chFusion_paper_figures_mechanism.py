"""Paper mechanism figures (Fig 2 / 3 / 5 / S1) from CS metal-plate caches.

Implements ``docs/plans/paper_figures_generation_plan.md``.

Run:
    python notebooks/scripts/chFusion_paper_figures_mechanism.py
    python notebooks/scripts/chFusion_paper_figures_mechanism.py --max-windows 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import hilbert

_cwd = Path.cwd().resolve()
project_root = next(
    (p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()),
    None,
)
if project_root is None:
    raise FileNotFoundError("Project root not found (missing src/ directory)")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.bootstrap import init_notebook

_env = init_notebook(project_root)
project_root = _env["project_root"]
FIGURES_DIR = Path(_env["FIGURES_DIR"])
REPORTS_DIR = Path(_env["REPORTS_DIR"])
CACHE_DIR = str(project_root / "outputs" / "cache")

from ble_analysis.chfusion import (
    ChFusionConfig,
    _bpm_from_fused_spectrum,
    _energy_ratio,
    _next_pow2,
    _peak_prominence,
    load_multichannel_for_scenario,
)
from ble_analysis.coherent_mrc import (
    MODAL_SHORT,
    coherent_mrc_fuse_modals,
    coherent_mrc_fuse_tones,
    estimate_phase_hilbert,
)
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams, _sliding_window_indices
from ble_analysis.systematic_fusion import (
    _collect_channel_window_data,
    _weighted_spectrum_average,
)
from ble_analysis.voting_fusion import VotingConfig, vote_bpm_weighted_histogram
from ble_analysis.wifi_mrc import _collect_modal_window_matrix

VARIABLE = "remote_amplitudes"
MODAL_VARS = ("remote_amplitudes", "local_amplitudes", "phases")

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "legend.fontsize": 8,
        "lines.linewidth": 1.5,
        "savefig.bbox": "tight",
        "savefig.dpi": 300,
    }
)


def _save_figure(fig: plt.Figure, stem: str) -> Tuple[Path, Path]:
    """Save both PNG (preview) and PDF (paper-ready) under FIGURES_DIR."""
    png_path = FIGURES_DIR / f"{stem}.png"
    pdf_path = FIGURES_DIR / f"{stem}.pdf"
    fig.savefig(png_path)
    fig.savefig(pdf_path)
    print(f"  saved {png_path.name} + {pdf_path.name}")
    return png_path, pdf_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate paper mechanism figures")
    p.add_argument(
        "--max-windows",
        type=int,
        default=0,
        help="Cap windows for Fig3/S1 (0 = all)",
    )
    return p.parse_args()


def _zscore(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    mu = float(np.mean(x))
    sd = float(np.std(x))
    return (x - mu) / sd if sd > eps else (x - mu)


def _pairwise_coherence(X: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """γ_ij = |Σ z_i conj(z_j)| / (||z_i|| ||z_j||) for rows of X."""
    n = X.shape[0]
    Z = hilbert(X, axis=1)
    norms = np.sqrt(np.sum(np.abs(Z) ** 2, axis=1))
    gamma = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i, n):
            denom = norms[i] * norms[j]
            if denom <= eps:
                g = 0.0
            else:
                g = float(np.abs(np.sum(Z[i] * np.conj(Z[j]))) / denom)
            gamma[i, j] = g
            gamma[j, i] = g
    return gamma


def _tone_pair_coherence(a: np.ndarray, b: np.ndarray, eps: float = 1e-12) -> float:
    z_i = hilbert(np.asarray(a, dtype=float))
    z_j = hilbert(np.asarray(b, dtype=float))
    denom = np.sqrt(np.sum(np.abs(z_i) ** 2) * np.sum(np.abs(z_j) ** 2))
    if denom <= eps:
        return 0.0
    return float(np.abs(np.sum(z_i * np.conj(z_j))) / denom)


def _longest_breath_segment(mc_var: dict) -> str:
    best_name = None
    best_len = -1
    for seg_name, seg in mc_var.items():
        if seg is None:
            continue
        meta = seg.get("metadata") or {}
        if meta.get("type") == "apnea":
            continue
        ch_map = seg["channels"]
        if not ch_map:
            continue
        ref_ch = next(iter(ch_map.values()))
        n = len(ref_ch[VARIABLE]["bandpass_filtered"])
        if n > best_len:
            best_len = n
            best_name = seg_name
    if best_name is None:
        raise RuntimeError("No non-apnea segment found")
    return best_name


def _segment_window_setup(
    mc_var: dict,
    seg_name: str,
    fs: float,
    metric_params: BreathMetricParams,
) -> Tuple[List[Any], dict, List[int], int]:
    seg = mc_var[seg_name]
    ch_map = seg["channels"]
    ch_list = sorted(ch_map.keys(), key=lambda c: (isinstance(c, str), str(c)))
    ref_len = max(len(ch_map[c][VARIABLE]["bandpass_filtered"]) for c in ch_list)
    win_len = int(round(metric_params.window_length_sec * fs))
    step_len = int(round(metric_params.step_length_sec * fs))
    starts = _sliding_window_indices(ref_len, win_len, step_len)
    return ch_list, ch_map, starts, win_len


def _select_diverse_window(
    X_windows: Sequence[np.ndarray],
    eta_list: Sequence[np.ndarray],
    rho_list: Sequence[np.ndarray],
) -> int:
    """Pick window near median η·ρ with high phase diversity (γ / Δφ)."""
    scores = []
    for X, eta, rho in zip(X_windows, eta_list, rho_list):
        q = eta * np.clip(rho, 0.0, None)
        mean_q = float(np.nanmean(q))
        y, phases, coherences, info = estimate_phase_hilbert(X, q)
        ref = info["ref_idx"]
        mask = np.arange(len(phases)) != ref
        dphi = np.abs(phases[mask])
        # diversity: mix of near-0, near-π, and intermediate phases among coherent tones
        high_g = coherences[mask] > 0.5
        if np.sum(high_g) < 3:
            diversity = 0.0
        else:
            d = dphi[high_g]
            has_in = np.any(d < 0.4)
            has_anti = np.any(np.abs(d - np.pi) < 0.4)
            has_mid = np.any((d > 0.6) & (d < 2.4))
            diversity = float(has_in) + float(has_anti) + float(has_mid) + float(np.std(d))
        scores.append((diversity, mean_q))
    mean_qs = np.array([s[1] for s in scores], dtype=float)
    med = float(np.nanmedian(mean_qs))
    # prefer diversity, then closeness of mean_q to median
    best = int(
        np.argmax(
            [
                s[0] * 10.0 - abs(s[1] - med)
                for s in scores
            ]
        )
    )
    return best


def _select_representative_tones(
    phases: np.ndarray,
    coherences: np.ndarray,
    eta: np.ndarray,
    rho: np.ndarray,
    ref_idx: int,
) -> List[int]:
    q = eta * np.clip(rho, 0.0, None)
    selected = [int(ref_idx)]
    others = [i for i in range(len(phases)) if i != ref_idx]

    def _pick(cond, prefer_high_q: bool = True) -> Optional[int]:
        cands = [i for i in others if i not in selected and cond(i)]
        if not cands:
            return None
        if prefer_high_q:
            return int(max(cands, key=lambda i: q[i] * coherences[i]))
        return int(cands[0])

    # in-phase
    t = _pick(lambda i: coherences[i] > 0.7 and abs(phases[i]) < 0.35)
    if t is None:
        t = _pick(lambda i: abs(phases[i]) < 0.5)
    if t is not None:
        selected.append(t)

    # anti-phase
    t = _pick(lambda i: coherences[i] > 0.7 and abs(abs(phases[i]) - np.pi) < 0.35)
    if t is None:
        t = _pick(lambda i: abs(abs(phases[i]) - np.pi) < 0.6)
    if t is not None:
        selected.append(t)

    # intermediate non-binary
    t = _pick(
        lambda i: coherences[i] > 0.5
        and abs(phases[i]) > 0.5
        and abs(abs(phases[i]) - np.pi) > 0.5
    )
    if t is None:
        t = _pick(lambda i: abs(phases[i]) > 0.4 and abs(abs(phases[i]) - np.pi) > 0.4)
    if t is not None:
        selected.append(t)

    # fill to 4 with highest remaining q
    while len(selected) < 4:
        rest = [i for i in others if i not in selected]
        if not rest:
            break
        selected.append(int(max(rest, key=lambda i: q[i])))
    return selected[:4]


def _apply_corr_sign(X: np.ndarray, ref_idx: int) -> np.ndarray:
    out = np.zeros_like(X)
    x_ref = X[ref_idx]
    for i in range(X.shape[0]):
        xi = X[i]
        r = np.corrcoef(xi, x_ref)[0, 1]
        s = 1.0 if (not np.isfinite(r) or r >= 0) else -1.0
        out[i] = s * xi
    return out


def _apply_hilbert_align(X: np.ndarray, phases: np.ndarray) -> np.ndarray:
    out = np.zeros_like(X)
    for i in range(X.shape[0]):
        z = hilbert(X[i]) * np.exp(-1j * phases[i])
        out[i] = _zscore(np.real(z))
    return out


def generate_fig2(
    data_by_scenario: Dict[str, Tuple[dict, float]],
    cfg: ChFusionConfig,
    metric_params: BreathMetricParams,
) -> dict:
    print("\n=== Figure 2: Inter-tone phase relationship ===")
    good_id, hard_id = "cs_095806", "cs_091339"
    mc_good, fs_good = data_by_scenario[good_id]
    mc_hard, fs_hard = data_by_scenario[hard_id]

    mc_var_g = mc_good[VARIABLE]
    seg_name = _longest_breath_segment(mc_var_g)
    ch_list, ch_map, starts, win_len = _segment_window_setup(
        mc_var_g, seg_name, fs_good, metric_params
    )
    print(f"  good={good_id} seg={seg_name} n_windows={len(starts)} fs={fs_good:.2f}")

    # probe a subset of windows for diversity
    probe_idx = list(range(len(starts)))
    if len(probe_idx) > 40:
        step = max(1, len(probe_idx) // 40)
        probe_idx = probe_idx[::step]

    X_list, eta_list, rho_list = [], [], []
    for wi in probe_idx:
        st = starts[wi]
        end = st + win_len
        X, eta, rho = _collect_modal_window_matrix(
            ch_list, ch_map, VARIABLE, st, end, fs_good, cfg
        )
        X_list.append(X)
        eta_list.append(eta)
        rho_list.append(rho)

    local_best = _select_diverse_window(X_list, eta_list, rho_list)
    window_idx = probe_idx[local_best]
    st = starts[window_idx]
    end = st + win_len
    X = X_list[local_best]
    eta = eta_list[local_best]
    rho = rho_list[local_best]
    print(f"  selected window_idx={window_idx} (st={st})")

    q = eta * np.clip(rho, 0.0, None)
    _y, phases, coherences, info = estimate_phase_hilbert(X, q)
    ref_idx = int(info["ref_idx"])
    selected = _select_representative_tones(phases, coherences, eta, rho, ref_idx)
    print(
        f"  tones={selected} phases={[f'{phases[i]:.2f}' for i in selected]} "
        f"γ={[f'{coherences[i]:.2f}' for i in selected]}"
    )

    X_sel = X[selected]
    labels = [
        f"tone {t}"
        + (" (ref)" if t == ref_idx else f" Δφ={phases[t]:.2f}")
        for t in selected
    ]
    raw = np.vstack([_zscore(row) for row in X_sel])
    pca_sign = _apply_corr_sign(X_sel, 0)  # first selected is ref
    # re-align relative to selected[0] which is ref
    # but if selected[0] != ref_idx order — _select puts ref first
    pca_sign = np.vstack([_zscore(row) for row in pca_sign])
    hilbert_aligned = _apply_hilbert_align(X, phases)[selected]

    # coherence matrices (η·ρ sorted)
    order_g = np.argsort(-(eta * np.clip(rho, 0.0, None)))
    gamma_good = _pairwise_coherence(X[order_g])

    mc_var_h = mc_hard[VARIABLE]
    seg_h = _longest_breath_segment(mc_var_h)
    ch_list_h, ch_map_h, starts_h, win_len_h = _segment_window_setup(
        mc_var_h, seg_h, fs_hard, metric_params
    )
    # use middle window for hard scenario heatmap
    wi_h = min(window_idx, len(starts_h) - 1)
    st_h = starts_h[wi_h]
    end_h = st_h + win_len_h
    X_h, eta_h, rho_h = _collect_modal_window_matrix(
        ch_list_h, ch_map_h, VARIABLE, st_h, end_h, fs_hard, cfg
    )
    order_h = np.argsort(-(eta_h * np.clip(rho_h, 0.0, None)))
    gamma_hard = _pairwise_coherence(X_h[order_h])

    t = np.arange(raw.shape[1]) / fs_good
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    fig = plt.figure(figsize=(12, 9))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.1], hspace=0.35, wspace=0.25)

    for col, (title, data) in enumerate(
        [
            ("(a) Raw bandpass (z-scored)", raw),
            ("(b) After ±1 sign correction", pca_sign),
        ]
    ):
        ax = fig.add_subplot(gs[0, col])
        for i, lab in enumerate(labels):
            ax.plot(t, data[i], color=colors[i], label=lab, alpha=0.85)
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Amplitude")
        if col == 0:
            ax.legend(loc="upper right", fontsize=7)

    ax = fig.add_subplot(gs[1, :])
    for i, lab in enumerate(labels):
        ax.plot(t, hilbert_aligned[i], color=colors[i], label=lab, alpha=0.85)
    ax.set_title("(c) After Hilbert continuous phase alignment")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.legend(loc="upper right", fontsize=7)

    ax_g = fig.add_subplot(gs[2, 0])
    im0 = ax_g.imshow(gamma_good, cmap="viridis", vmin=0, vmax=1, aspect="auto")
    ax_g.set_title(f"(d) Tone-pair γ — {good_id} (good)")
    ax_g.set_xlabel("Tone rank (η·ρ ↓)")
    ax_g.set_ylabel("Tone rank (η·ρ ↓)")
    fig.colorbar(im0, ax=ax_g, fraction=0.046, pad=0.04)

    ax_h = fig.add_subplot(gs[2, 1])
    im1 = ax_h.imshow(gamma_hard, cmap="viridis", vmin=0, vmax=1, aspect="auto")
    ax_h.set_title(f"(d) Tone-pair γ — {hard_id} (hard)")
    ax_h.set_xlabel("Tone rank (η·ρ ↓)")
    ax_h.set_ylabel("Tone rank (η·ρ ↓)")
    fig.colorbar(im1, ax=ax_h, fraction=0.046, pad=0.04)

    fig.suptitle(
        f"Figure 2: Inter-tone phase relationship  [{good_id}/{seg_name}/win{window_idx}]",
        y=1.01,
    )
    _save_figure(fig, "paper_fig2_inter_tone_phase")
    plt.close(fig)

    return {
        "scenario_good": good_id,
        "scenario_hard": hard_id,
        "seg_name": seg_name,
        "seg_name_hard": seg_h,
        "window_idx": window_idx,
        "variable": VARIABLE,
        "selected_tones": np.asarray(selected, dtype=int),
        "tone_waveforms": raw,
        "tone_waveforms_pca_sign": pca_sign,
        "tone_waveforms_hilbert": hilbert_aligned,
        "phases": phases,
        "coherences": coherences,
        "ref_idx": ref_idx,
        "gamma_matrix_good": gamma_good,
        "gamma_matrix_hard": gamma_hard,
        "eta": eta,
        "rho": rho,
    }


def _level1_modal_waveforms(
    multichannel_by_var: dict,
    seg_name: str,
    ch_list: Sequence[Any],
    st: int,
    end: int,
    fs: float,
    cfg: ChFusionConfig,
) -> Tuple[Dict[str, np.ndarray], Dict[str, float], dict]:
    waveforms: Dict[str, np.ndarray] = {}
    etas: Dict[str, float] = {}
    infos: dict = {}
    for variable in MODAL_VARS:
        seg = multichannel_by_var[variable].get(seg_name)
        if seg is None:
            continue
        ch_map = seg["channels"]
        X, eta, rho = _collect_modal_window_matrix(
            ch_list, ch_map, variable, st, end, fs, cfg
        )
        y, info = coherent_mrc_fuse_tones(
            X,
            eta,
            rho,
            phase_method="hilbert",
            weight_mode="coherence_gated",
            fs=fs,
        )
        short = MODAL_SHORT[variable]
        waveforms[short] = y
        etas[short] = _energy_ratio(y, fs, cfg)
        infos[short] = info
    return waveforms, etas, infos


def _aligned_modal_waveforms(
    waveforms: Dict[str, np.ndarray],
    phases: Dict[str, float],
) -> Dict[str, np.ndarray]:
    out = {}
    for k, y in waveforms.items():
        z = hilbert(y) * np.exp(-1j * phases.get(k, 0.0))
        out[k] = _zscore(np.real(z))
    return out


def _cross_modal_dphi(phases: Dict[str, float]) -> Tuple[float, float, float]:
    """Return (remote-local, remote-phase, local-phase) wrapped to [-π, π]."""
    keys = ("remote", "local", "phase")
    if not all(k in phases for k in keys):
        return (np.nan, np.nan, np.nan)

    def wrap(a: float) -> float:
        return float(np.angle(np.exp(1j * a)))

    return (
        wrap(phases["remote"] - phases["local"]),
        wrap(phases["remote"] - phases["phase"]),
        wrap(phases["local"] - phases["phase"]),
    )


def _collect_cross_window_phases(
    multichannel_by_var: dict,
    seg_name: str,
    fs: float,
    cfg: ChFusionConfig,
    metric_params: BreathMetricParams,
    max_windows: int = 0,
):
    """Returns dphi, coherences, mid before/after, y_fused, mid_phases, mid_i, fs, win_len."""
    mc_var = multichannel_by_var[VARIABLE]
    ch_list, _ch_map, starts, win_len = _segment_window_setup(
        mc_var, seg_name, fs, metric_params
    )
    if max_windows > 0:
        starts = starts[:max_windows]

    dphi_rows = []
    coh_rows = []
    mid_i = len(starts) // 2
    mid_before: Dict[str, np.ndarray] = {}
    mid_after: Dict[str, np.ndarray] = {}
    mid_fused = np.array([])
    mid_phases: Dict[str, float] = {}

    for wi, st in enumerate(starts):
        end = st + win_len
        wfs, etas, _infos = _level1_modal_waveforms(
            multichannel_by_var, seg_name, ch_list, st, end, fs, cfg
        )
        if len(wfs) < 2:
            dphi_rows.append([np.nan, np.nan, np.nan])
            coh_rows.append([np.nan, np.nan, np.nan])
            continue
        y_fused, minfo = coherent_mrc_fuse_modals(
            wfs,
            etas,
            modal_weight_mode="eta_coherence",
            use_phase_align=True,
        )
        phases = minfo.get("phases", {})
        coherences = minfo.get("coherences", {})
        dphi_rows.append(list(_cross_modal_dphi(phases)))
        coh_rows.append(
            [
                float(coherences.get("remote", np.nan)),
                float(coherences.get("local", np.nan)),
                float(coherences.get("phase", np.nan)),
            ]
        )
        if wi == mid_i:
            mid_before = {k: _zscore(v) for k, v in wfs.items()}
            mid_after = _aligned_modal_waveforms(wfs, phases)
            mid_fused = _zscore(y_fused)
            mid_phases = dict(phases)

    return (
        np.asarray(dphi_rows, dtype=float),
        np.asarray(coh_rows, dtype=float),
        mid_before,
        mid_after,
        mid_fused,
        mid_phases,
        mid_i,
        fs,
        win_len,
    )


def generate_fig3(
    data_by_scenario: Dict[str, Tuple[dict, float]],
    cfg: ChFusionConfig,
    metric_params: BreathMetricParams,
    max_windows: int = 0,
) -> dict:
    print("\n=== Figure 3: Inter-modal phase alignment ===")
    s1, s2 = "cs_095806", "cs_102621"
    mc1, fs1 = data_by_scenario[s1]
    mc2, fs2 = data_by_scenario[s2]
    seg1 = _longest_breath_segment(mc1[VARIABLE])
    seg2 = _longest_breath_segment(mc2[VARIABLE])
    print(f"  {s1} seg={seg1}; {s2} seg={seg2}; max_windows={max_windows or 'all'}")

    (
        dphi1,
        coh1,
        before,
        after,
        y_fused,
        mid_phases,
        mid_i,
        fs_plot,
        win_len,
    ) = _collect_cross_window_phases(mc1, seg1, fs1, cfg, metric_params, max_windows)
    print(f"  scenario1 windows={len(dphi1)} mid_window={mid_i}")

    dphi2, coh2, *_rest = _collect_cross_window_phases(
        mc2, seg2, fs2, cfg, metric_params, max_windows
    )
    print(f"  scenario2 windows={len(dphi2)}")

    t = np.arange(win_len) / fs_plot
    colors = {"remote": "#1f77b4", "local": "#ff7f0e", "phase": "#2ca02c"}
    pair_labels = ["remote−local", "remote−phase", "local−phase"]
    pair_colors = ["#1f77b4", "#d62728", "#9467bd"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    ax = axes[0, 0]
    for k in ("remote", "local", "phase"):
        if k in before:
            ax.plot(t, before[k], color=colors[k], label=k, alpha=0.9)
    ax.set_title("(a) Level-1 modal waveforms (before Level-2 align)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.legend()
    ylim = ax.get_ylim()

    ax = axes[0, 1]
    for k in ("remote", "local", "phase"):
        if k in after:
            ax.plot(t, after[k], color=colors[k], label=k, alpha=0.85)
    if y_fused.size:
        ax.plot(t, y_fused, color="k", linewidth=2.2, label="fused", zorder=5)
    ax.set_title("(b) After Level-2 Hilbert + η·γ fusion")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_ylim(ylim)
    ax.legend()

    ax = axes[1, 0]
    x = np.arange(len(dphi1))
    for i, lab in enumerate(pair_labels):
        ax.plot(x, dphi1[:, i], color=pair_colors[i], label=lab, alpha=0.9)
    ax.axhline(0, color="gray", lw=0.8, ls="--")
    ax.set_title(f"(c) Cross-window Δφ — {s1}")
    ax.set_xlabel("Window index")
    ax.set_ylabel("Δφ (rad)")
    ax.legend(fontsize=7)

    ax = axes[1, 1]
    x2 = np.arange(len(dphi2))
    for i, lab in enumerate(pair_labels):
        ax.plot(x2, dphi2[:, i], color=pair_colors[i], label=lab, alpha=0.9)
    ax.axhline(0, color="gray", lw=0.8, ls="--")
    ax.set_title(f"(d) Cross-window Δφ — {s2}")
    ax.set_xlabel("Window index")
    ax.set_ylabel("Δφ (rad)")
    ax.legend(fontsize=7)

    fig.suptitle("Figure 3: Inter-modal phase relationship", y=1.01)
    fig.tight_layout()
    _save_figure(fig, "paper_fig3_inter_modal_phase")
    plt.close(fig)

    return {
        "scenario_1": s1,
        "scenario_2": s2,
        "seg_name": seg1,
        "seg_name_2": seg2,
        "mid_window_idx": mid_i,
        "modal_waveforms_before": before,
        "modal_waveforms_after": after,
        "y_fused": y_fused,
        "modal_phases": mid_phases,
        "cross_window_phases_scenario1": dphi1,
        "cross_window_phases_scenario2": dphi2,
        "cross_window_coherences_scenario1": coh1,
        "cross_window_coherences_scenario2": coh2,
    }


def generate_fig5(
    data_by_scenario: Dict[str, Tuple[dict, float]],
    cfg: ChFusionConfig,
    metric_params: BreathMetricParams,
    fig2_meta: Optional[dict] = None,
) -> dict:
    print("\n=== Figure 5: η·ρ quality voting ===")
    sid = "cs_095806"
    mc, fs = data_by_scenario[sid]
    mc_var = mc[VARIABLE]
    seg_name = (
        fig2_meta["seg_name"]
        if fig2_meta and fig2_meta.get("scenario_good") == sid
        else _longest_breath_segment(mc_var)
    )
    ch_list, ch_map, starts, win_len = _segment_window_setup(
        mc_var, seg_name, fs, metric_params
    )
    window_idx = (
        int(fig2_meta["window_idx"])
        if fig2_meta and fig2_meta.get("scenario_good") == sid
        else len(starts) // 2
    )
    window_idx = min(window_idx, len(starts) - 1)
    st = starts[window_idx]
    end = st + win_len
    print(f"  {sid}/{seg_name}/win{window_idx}")

    nfft = cfg.nfft or _next_pow2(4 * win_len)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)
    band_mask = (freqs >= cfg.breath_freq_low) & (freqs <= cfg.breath_freq_high)
    band_freqs = freqs[band_mask]
    hann = np.hanning(win_len)

    eta, rho, bpm_per_tone, spectra = _collect_channel_window_data(
        ch_list, ch_map, VARIABLE, st, end, fs, cfg, nfft, band_mask, band_freqs, hann
    )
    w = eta * np.maximum(rho, 0.0)
    vcfg = VotingConfig(
        variable=VARIABLE,
        voting_strategy="eta_rho_weighted",
        breath_freq_low=cfg.breath_freq_low,
        breath_freq_high=cfg.breath_freq_high,
    )
    bpm_voted, _conf, _mass = vote_bpm_weighted_histogram(bpm_per_tone, w, vcfg)

    mask = np.array([np.sum(s) > cfg.eps for s in spectra], dtype=bool) & np.isfinite(
        bpm_per_tone
    )
    if np.any(mask):
        s_uniform = np.mean(np.vstack([spectra[i] for i in range(len(spectra)) if mask[i]]), axis=0)
    else:
        s_uniform = np.zeros_like(band_freqs)
    bpm_uniform = _bpm_from_fused_spectrum(s_uniform, band_freqs, cfg)
    s_voting = _weighted_spectrum_average(spectra, w, band_freqs, cfg.eps)

    err = np.abs(bpm_per_tone - bpm_voted)
    err[~np.isfinite(err)] = np.nan
    sizes = w / (np.sum(w) + cfg.eps) * 400 + 15
    top5 = np.argsort(-(eta * np.clip(rho, 0.0, None)))[:5]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))

    ax = axes[0]
    sc = ax.scatter(
        eta,
        rho,
        c=np.nan_to_num(err, nan=0.0),
        s=sizes,
        cmap="coolwarm",
        alpha=0.85,
        edgecolors="k",
        linewidths=0.3,
    )
    for i in top5:
        ax.annotate(
            str(i),
            (eta[i], rho[i]),
            textcoords="offset points",
            xytext=(3, 3),
            fontsize=7,
        )
    ax.set_xlabel("η (energy ratio)")
    ax.set_ylabel("ρ (peak prominence)")
    ax.set_title("(a) Per-tone η vs ρ")
    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("|BPM_i − BPM_voted|")

    ax = axes[1]
    bins = np.arange(6, 22)
    bpm_valid = bpm_per_tone[mask]
    w_valid = w[mask]
    ax.hist(
        bpm_valid,
        bins=bins,
        color="lightgray",
        edgecolor="gray",
        label="Uniform (count)",
        alpha=0.9,
    )
    ax.hist(
        bpm_valid,
        bins=bins,
        weights=w_valid / (np.sum(w_valid) + cfg.eps) * len(bpm_valid),
        color="#1f77b4",
        alpha=0.55,
        edgecolor="#1f77b4",
        label="η·ρ Voting (weighted)",
    )
    if np.isfinite(bpm_uniform):
        ax.axvline(bpm_uniform, color="gray", ls="--", lw=1.5, label=f"Uniform BPM={bpm_uniform:.1f}")
    if np.isfinite(bpm_voted):
        ax.axvline(bpm_voted, color="#1f77b4", ls="-", lw=1.8, label=f"Voting BPM={bpm_voted:.1f}")
    ax.set_xlabel("BPM")
    ax.set_ylabel("Count / scaled weight")
    ax.set_title("(b) BPM histogram")
    ax.legend(fontsize=7)

    ax = axes[2]
    ax.plot(band_freqs, s_uniform, color="gray", label="S_uniform", alpha=0.9)
    ax.plot(band_freqs, s_voting, color="#1f77b4", label="S_voting (η·ρ)", alpha=0.9)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Normalized power")
    ax.set_title("(c) Fused spectrum")
    ax.legend(fontsize=7)

    fig.suptitle(
        f"Figure 5: η·ρ quality voting  [{sid}/{seg_name}/win{window_idx}]",
        y=1.02,
    )
    fig.tight_layout()
    _save_figure(fig, "paper_fig5_eta_rho_voting")
    plt.close(fig)
    print(f"  BPM voted={bpm_voted:.2f} uniform={bpm_uniform:.2f}")

    return {
        "scenario": sid,
        "seg_name": seg_name,
        "window_idx": window_idx,
        "eta": eta,
        "rho": rho,
        "bpm_per_tone": bpm_per_tone,
        "weights": w,
        "bpm_voted": float(bpm_voted) if np.isfinite(bpm_voted) else np.nan,
        "bpm_uniform": float(bpm_uniform) if np.isfinite(bpm_uniform) else np.nan,
        "spectrum_voting": s_voting,
        "spectrum_uniform": s_uniform,
        "band_freqs": band_freqs,
    }


def _pick_high_gamma_pair(
    X: np.ndarray,
    eta: np.ndarray,
    rho: np.ndarray,
    min_gamma: float = 0.7,
) -> Tuple[int, int]:
    q = eta * np.clip(rho, 0.0, None)
    order = np.argsort(-q)
    top = order[:20]
    best = (int(top[0]), int(top[1]))
    best_g = -1.0
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            a, b = int(top[i]), int(top[j])
            g = _tone_pair_coherence(X[a], X[b])
            if g > best_g:
                best_g = g
                best = (a, b)
            if g >= min_gamma and q[a] > 0 and q[b] > 0:
                return a, b
    return best


def generate_figS1(
    data_by_scenario: Dict[str, Tuple[dict, float]],
    cfg: ChFusionConfig,
    metric_params: BreathMetricParams,
    max_windows: int = 0,
    fig2_meta: Optional[dict] = None,
) -> dict:
    print("\n=== Figure S1: Coherence stability ===")
    good_id, hard_id = "cs_095806", "cs_091339"
    mc_g, fs_g = data_by_scenario[good_id]
    mc_h, fs_h = data_by_scenario[hard_id]

    seg_g = (
        fig2_meta["seg_name"]
        if fig2_meta
        else _longest_breath_segment(mc_g[VARIABLE])
    )
    ch_list_g, ch_map_g, starts_g, win_len_g = _segment_window_setup(
        mc_g[VARIABLE], seg_g, fs_g, metric_params
    )
    wi0 = (
        int(fig2_meta["window_idx"])
        if fig2_meta
        else len(starts_g) // 2
    )
    wi0 = min(wi0, len(starts_g) - 1)
    st0 = starts_g[wi0]
    X0, eta0, rho0 = _collect_modal_window_matrix(
        ch_list_g, ch_map_g, VARIABLE, st0, st0 + win_len_g, fs_g, cfg
    )
    t_i, t_j = _pick_high_gamma_pair(X0, eta0, rho0)
    print(f"  tone pair=({t_i}, {t_j}) from {good_id}/{seg_g}/win{wi0}")

    def track(mc, fs, seg_name, max_w):
        ch_list, ch_map, starts, win_len = _segment_window_setup(
            mc[VARIABLE], seg_name, fs, metric_params
        )
        if max_w > 0:
            starts = starts[:max_w]
        # tone indices come from good scenario ch_list order; clamp if hard has fewer tones
        n_ch = len(ch_list)
        if t_i >= n_ch or t_j >= n_ch:
            return np.full(len(starts), np.nan, dtype=float)
        gammas = []
        for st in starts:
            end = st + win_len
            rows = []
            ok = True
            for ch_idx in (t_i, t_j):
                ch = ch_list[ch_idx]
                bp_full = ch_map[ch][VARIABLE]["bandpass_filtered"]
                if len(bp_full) < end:
                    ok = False
                    break
                rows.append(_zscore(bp_full[st:end]))
            if not ok:
                gammas.append(np.nan)
                continue
            n = min(len(rows[0]), len(rows[1]))
            gammas.append(_tone_pair_coherence(rows[0][:n], rows[1][:n]))
        return np.asarray(gammas, dtype=float)

    # Prefer same segment name as good scenario when available
    if mc_h[VARIABLE].get(seg_g) is not None:
        seg_h = seg_g
    else:
        seg_h = _longest_breath_segment(mc_h[VARIABLE])
    g_good = track(mc_g, fs_g, seg_g, max_windows)
    g_hard = track(mc_h, fs_h, seg_h, max_windows)
    print(
        f"  good γ={np.nanmean(g_good):.3f}±{np.nanstd(g_good):.3f} "
        f"hard γ={np.nanmean(g_hard):.3f}±{np.nanstd(g_hard):.3f}"
    )

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(
        np.arange(len(g_good)),
        g_good,
        color="#1f77b4",
        label=(
            f"{good_id} (good): "
            f"μ={np.nanmean(g_good):.2f}±{np.nanstd(g_good):.2f}"
        ),
    )
    ax.plot(
        np.arange(len(g_hard)),
        g_hard,
        color="#d62728",
        label=(
            f"{hard_id} (hard): "
            f"μ={np.nanmean(g_hard):.2f}±{np.nanstd(g_hard):.2f}"
        ),
    )
    ax.axhline(np.nanmean(g_good), color="#1f77b4", ls="--", lw=1, alpha=0.6)
    ax.axhline(np.nanmean(g_hard), color="#d62728", ls="--", lw=1, alpha=0.6)
    ax.set_xlabel("Window index")
    ax.set_ylabel(f"γ (tone {t_i}, {t_j})")
    ax.set_ylim(0, 1.05)
    ax.set_title(
        f"Figure S1: Tone-pair coherence stability  (pair={t_i},{t_j}; "
        f"segs {seg_g}/{seg_h})"
    )
    ax.legend()
    fig.tight_layout()
    _save_figure(fig, "paper_figS1_coherence_stability")
    plt.close(fig)

    return {
        "tone_pair": (int(t_i), int(t_j)),
        "seg_good": seg_g,
        "seg_hard": seg_h,
        "gamma_cs095806": g_good,
        "gamma_cs091339": g_hard,
    }


def main() -> None:
    args = parse_args()
    filter_params = FilterParams()
    metric_params = BreathMetricParams()
    cfg = ChFusionConfig(
        breath_freq_low=metric_params.breath_freq_low,
        breath_freq_high=metric_params.breath_freq_high,
        window_length_sec=metric_params.window_length_sec,
        step_length_sec=metric_params.step_length_sec,
        enable_consensus=False,
    )

    scenario_ids = ("cs_091339", "cs_095806", "cs_102621")
    data_by_scenario: Dict[str, Tuple[dict, float]] = {}
    for sid in scenario_ids:
        scenario = load_scenario(sid, project_root=project_root)
        print(f"\n{'=' * 60}")
        print_scenario_summary(scenario)
        mc, fs, skipped = load_multichannel_for_scenario(
            scenario,
            project_root=project_root,
            filter_params=filter_params,
            cache_dir=CACHE_DIR,
            verbose=True,
        )
        print(f"  fs={fs:.3f} Hz  cache_skip_raw={skipped}")
        data_by_scenario[sid] = (mc, float(fs))

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    fig2 = generate_fig2(data_by_scenario, cfg, metric_params)
    fig3 = generate_fig3(
        data_by_scenario, cfg, metric_params, max_windows=args.max_windows
    )
    fig5 = generate_fig5(data_by_scenario, cfg, metric_params, fig2_meta=fig2)
    figS1 = generate_figS1(
        data_by_scenario,
        cfg,
        metric_params,
        max_windows=args.max_windows,
        fig2_meta=fig2,
    )

    diagnostics = {
        "fig2": fig2,
        "fig3": fig3,
        "fig5": fig5,
        "figS1": figS1,
    }
    # also save per-figure npy as plan mentions optional per-fig dumps
    np.save(FIGURES_DIR / "paper_fig2_diagnostics.npy", fig2, allow_pickle=True)
    np.save(FIGURES_DIR / "paper_fig3_diagnostics.npy", fig3, allow_pickle=True)
    np.save(FIGURES_DIR / "paper_fig5_diagnostics.npy", fig5, allow_pickle=True)
    out_npy = REPORTS_DIR / "paper_figures_diagnostics.npy"
    np.save(out_npy, diagnostics, allow_pickle=True)
    print(f"\nSaved diagnostics: {out_npy}")
    print("Done.")


if __name__ == "__main__":
    main()
