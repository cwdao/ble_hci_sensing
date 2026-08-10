"""BLE CS position-sweep observation figures (paper Ch.4 qualitative evidence).

Implements ``docs/plans/position_sweep_observation_plan.md``.

Run:
    python notebooks/scripts/chFusion_position_sweep_observation.py
"""

from __future__ import annotations

import argparse
import json
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
from ble_analysis.chfusion import ChFusionConfig, _energy_ratio, _peak_prominence
from ble_analysis.coherent_mrc import estimate_phase_hilbert
from ble_analysis.filters import apply_filter_pipeline
from ble_analysis.jsonl_loader import (
    VARIABLES,
    estimate_fs_from_frames,
    extract_multivar_cube,
    filter_frames_by_seq,
    load_jsonl_frames,
    segment_frames_by_ranges,
)
from ble_analysis.resampling import resample_to_uniform_grid
from ble_analysis.segments import FilterParams

_env = init_notebook(project_root)
project_root = Path(_env["project_root"])
FIGURES_DIR = Path(_env["FIGURES_DIR"])
REPORTS_DIR = Path(_env["REPORTS_DIR"])

METAL_PATH = project_root / "sampleData" / "metal_verify" / "CS_frames_all_20260804_090719.jsonl"
HUMAN_PATH = project_root / "sampleData" / "metal_verify" / "CS_frames_all_20260804_094043.jsonl"

# Plan §3.2 — metal plate segments (seq inclusive), 100 cm → 85 cm by 1 cm
METAL_SEGMENTS: Dict[str, Tuple[int, int]] = {
    f"seg{i}": rng
    for i, rng in enumerate(
        [
            (434, 540),
            (550, 657),
            (663, 772),
            (790, 898),
            (907, 1015),
            (1022, 1130),
            (1138, 1236),
            (1246, 1352),
            (1362, 1469),
            (1479, 1584),
            (1595, 1710),
            (1718, 1827),
            (1837, 1942),
            (1947, 2055),
            (2059, 2169),
            (2174, 2279),
        ],
        start=1,
    )
}

# Plan §3.3 — human breathing segments
HUMAN_SEGMENTS: Dict[str, Tuple[int, int]] = {
    "H1": (30, 210),   # 80 cm
    "H2": (320, 380),  # 90 cm
    "H3": (397, 470),  # 100 cm
}

HUMAN_DIST_CM = {"H1": 80, "H2": 90, "H3": 100}

# Walking frames to drop from metal seg1 for human-vs-metal comparison
METAL_SEG1_WALK_END_SEQ = 450

MODAL_COLORS = {
    "remote_amplitudes": "#1f77b4",
    "local_amplitudes": "#2ca02c",
    "phases": "#d62728",
}
MODAL_LABELS = {
    "remote_amplitudes": "Remote amp",
    "local_amplitudes": "Local amp",
    "phases": "Composite phase",
}
MODAL_SHORT = {
    "remote_amplitudes": "remote",
    "local_amplitudes": "local",
    "phases": "phase",
}

CHANNEL_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

STYLE = {
    "linewidth": 1.6,
    "fontsize": 11,
}


def metal_distance_cm(seg_idx: int) -> int:
    """Segment 1 = 100 cm, each step −1 cm."""
    return 100 - (seg_idx - 1)


def _apply_style(ax) -> None:
    ax.grid(False)
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_visible(True)


def _zscore(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    finite = x[np.isfinite(x)]
    if finite.size == 0:
        return np.zeros_like(x, dtype=float)
    mu = float(np.mean(finite))
    sd = float(np.std(finite))
    if not np.isfinite(sd) or sd < eps:
        out = x - mu
        out[~np.isfinite(out)] = 0.0
        return out
    out = (x - mu) / sd
    out[~np.isfinite(out)] = 0.0
    return out


def _normalize01(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    finite = x[np.isfinite(x)]
    if finite.size == 0:
        return np.zeros_like(x, dtype=float)
    lo = float(np.min(finite))
    hi = float(np.max(finite))
    if (hi - lo) < eps:
        return np.zeros_like(x, dtype=float)
    out = (x - lo) / (hi - lo)
    out[~np.isfinite(out)] = 0.0
    return out


def _fill_nan_1d(y: np.ndarray) -> np.ndarray:
    """Linear-interpolate isolated NaNs; edge NaNs use nearest finite value."""
    y = np.asarray(y, dtype=float).copy()
    n = len(y)
    if n == 0:
        return y
    good = np.isfinite(y)
    if not np.any(good):
        return np.zeros(n, dtype=float)
    if np.all(good):
        return y
    idx = np.arange(n)
    y[~good] = np.interp(idx[~good], idx[good], y[good])
    return y


def _resample_matrix(
    values: np.ndarray,
    time_sec: np.ndarray,
    target_fs: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Resample each channel row onto a uniform time grid."""
    t0 = float(time_sec[0])
    t_rel = np.asarray(time_sec, dtype=float) - t0
    # drop non-finite time
    ok = np.isfinite(t_rel)
    t_rel = t_rel[ok]
    values = values[:, ok]
    if len(t_rel) < 2:
        fs = float(target_fs) if target_fs else 2.0
        return values, t_rel, fs

    if target_fs is None:
        dt = np.diff(t_rel)
        dt = dt[dt > 0]
        med = float(np.median(dt)) if len(dt) else 0.5
        target_fs = 1.0 / med if med > 0 else 2.0

    rows = []
    t_out = None
    for i in range(values.shape[0]):
        yi = _fill_nan_1d(values[i])
        res = resample_to_uniform_grid(t_rel, yi, target_fs=target_fs)
        rows.append(res["values"])
        t_out = res["time_sec"]
        target_fs = float(res["target_fs"])
    return np.vstack(rows), np.asarray(t_out, dtype=float), float(target_fs)


def _filter_series(
    x: np.ndarray,
    fs: float,
    *,
    depth: str,
    fp: FilterParams,
) -> Dict[str, np.ndarray]:
    """depth: 'hp' | 'bp' — always returns median/hp/(optional bp)."""
    median = apply_filter_pipeline(
        x, pipeline=[{"type": "median", "window_size": fp.median_window}]
    )
    hp = apply_filter_pipeline(
        median,
        fs=fs,
        pipeline=[{"type": "highpass", "cutoff": fp.highpass_cutoff, "order": fp.highpass_order}],
    )
    out = {"median": median, "highpass": hp, "bandpass": hp}
    if depth == "bp":
        bp = apply_filter_pipeline(
            hp,
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
        out["bandpass"] = bp
    return out


def _filter_cube(
    cube: np.ndarray,
    fs: float,
    *,
    depth: str,
    fp: FilterParams,
) -> Dict[str, np.ndarray]:
    n_ch, n_t = cube.shape
    med = np.zeros_like(cube)
    hp = np.zeros_like(cube)
    bp = np.zeros_like(cube)
    for i in range(n_ch):
        f = _filter_series(cube[i], fs, depth=depth, fp=fp)
        med[i] = f["median"]
        hp[i] = f["highpass"]
        bp[i] = f["bandpass"]
    return {"median": med, "highpass": hp, "bandpass": bp}


def compute_eta(signal: np.ndarray, fs: float, cfg: Optional[ChFusionConfig] = None) -> float:
    cfg = cfg or ChFusionConfig()
    return float(_energy_ratio(np.asarray(signal, dtype=float), fs, cfg))


def compute_rho(signal: np.ndarray, fs: float, cfg: Optional[ChFusionConfig] = None) -> float:
    cfg = cfg or ChFusionConfig()
    return float(_peak_prominence(np.asarray(signal, dtype=float), fs, cfg))


def _pairwise_coherence(X: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = X.shape[0]
    Z = hilbert(X, axis=1)
    norms = np.sqrt(np.sum(np.abs(Z) ** 2, axis=1))
    gamma = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i, n):
            denom = norms[i] * norms[j]
            g = 0.0 if denom <= eps else float(np.abs(np.sum(Z[i] * np.conj(Z[j]))) / denom)
            gamma[i, j] = g
            gamma[j, i] = g
    return gamma


def _apply_corr_sign(X: np.ndarray, ref_idx: int) -> np.ndarray:
    out = np.zeros_like(X)
    x_ref = X[ref_idx]
    for i in range(X.shape[0]):
        xi = X[i]
        if np.std(xi) < 1e-12 or np.std(x_ref) < 1e-12:
            out[i] = xi
            continue
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


def _select_representative_tones(
    phases: np.ndarray,
    coherences: np.ndarray,
    eta: np.ndarray,
    rho: np.ndarray,
    ref_idx: int,
    k: int = 4,
) -> List[int]:
    q = eta * np.clip(rho, 0.0, None)
    selected = [int(ref_idx)]
    others = [i for i in range(len(phases)) if i != ref_idx]

    def _pick(cond) -> Optional[int]:
        cands = [i for i in others if i not in selected and cond(i)]
        if not cands:
            return None
        return int(max(cands, key=lambda i: q[i] * coherences[i]))

    for cond in (
        lambda i: coherences[i] > 0.7 and abs(phases[i]) < 0.35,
        lambda i: coherences[i] > 0.7 and abs(abs(phases[i]) - np.pi) < 0.35,
        lambda i: coherences[i] > 0.5
        and abs(phases[i]) > 0.5
        and abs(abs(phases[i]) - np.pi) > 0.5,
    ):
        t = _pick(cond)
        if t is not None:
            selected.append(t)

    while len(selected) < k:
        rest = [i for i in others if i not in selected]
        if not rest:
            break
        selected.append(int(max(rest, key=lambda i: q[i])))
    return selected[:k]


def _instantaneous_dphi(a: np.ndarray, b: np.ndarray) -> float:
    """Mean instantaneous phase difference (rad) over the segment via Hilbert."""
    za = hilbert(_zscore(a))
    zb = hilbert(_zscore(b))
    dphi = np.angle(za * np.conj(zb))
    # circular mean
    return float(np.angle(np.mean(np.exp(1j * dphi))))


def _mid_window_slice(n: int, fs: float, duration_sec: float = 10.0) -> slice:
    """Take a centered stable window of ``duration_sec`` (or full if shorter)."""
    win = int(round(duration_sec * fs))
    if n <= win or win < 4:
        return slice(0, n)
    start = (n - win) // 2
    return slice(start, start + win)


def _save_png_pdf(fig: plt.Figure, stem: Path | str) -> Tuple[Path, Path]:
    """Save PNG preview + PDF paper copy next to each other."""
    stem_path = Path(stem)
    if stem_path.suffix.lower() in {".png", ".pdf"}:
        stem_path = stem_path.with_suffix("")
    png = stem_path.with_suffix(".png")
    pdf = stem_path.with_suffix(".pdf")
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    return png, pdf


# ---------------------------------------------------------------------------
# Segment preprocessing cache
# ---------------------------------------------------------------------------

def prepare_segment(
    frames: List[dict],
    *,
    fp: FilterParams,
    channel_keys: Sequence[int],
    trim_seq_after: Optional[int] = None,
) -> Dict[str, Any]:
    """Load one seq-range segment → resampled cubes + HP/BP filters."""
    use = frames
    if trim_seq_after is not None:
        use = [fr for fr in frames if int(fr.get("seq", -1)) > int(trim_seq_after)]
    if len(use) < 4:
        return {"ok": False, "n_frames": len(use)}

    raw_fs = estimate_fs_from_frames(use)
    cube = extract_multivar_cube(use, VARIABLES, channel_keys=channel_keys)
    t = cube["time_sec"]
    # Use median-interval fs as target
    target_fs = raw_fs

    filtered: Dict[str, Any] = {"ok": True, "n_frames_raw": len(use), "fs_raw": raw_fs}
    filtered["seqs"] = cube["seqs"]
    filtered["channel_keys"] = np.asarray(channel_keys, dtype=int)

    for var in VARIABLES:
        mat_rs, t_rs, fs = _resample_matrix(cube[var], t, target_fs=target_fs)
        hp = _filter_cube(mat_rs, fs, depth="hp", fp=fp)
        bp = _filter_cube(mat_rs, fs, depth="bp", fp=fp)
        filtered[var] = {
            "raw_rs": mat_rs,
            "time_sec": t_rs,
            "fs": fs,
            "hp": hp,
            "bp": bp,
        }
    # shared time/fs from first var
    filtered["time_sec"] = filtered["remote_amplitudes"]["time_sec"]
    filtered["fs"] = filtered["remote_amplitudes"]["fs"]
    return filtered


def prepare_all_metal(
    all_frames: List[dict],
    fp: FilterParams,
    channel_keys: Sequence[int],
) -> Dict[str, Dict[str, Any]]:
    segs = segment_frames_by_ranges(all_frames, METAL_SEGMENTS)
    out = {}
    for name, frs in segs.items():
        print(f"  prepare {name}: {len(frs)} frames")
        out[name] = prepare_segment(frs, fp=fp, channel_keys=channel_keys)
    return out


def prepare_all_human(
    all_frames: List[dict],
    fp: FilterParams,
    channel_keys: Sequence[int],
) -> Dict[str, Dict[str, Any]]:
    segs = segment_frames_by_ranges(all_frames, HUMAN_SEGMENTS)
    out = {}
    for name, frs in segs.items():
        print(f"  prepare {name}: {len(frs)} frames")
        out[name] = prepare_segment(frs, fp=fp, channel_keys=channel_keys)
    return out


def per_channel_eta_rho(
    seg: Dict[str, Any],
    variable: str,
    cfg: ChFusionConfig,
) -> Tuple[np.ndarray, np.ndarray]:
    """η from HP, ρ from BP, per channel."""
    block = seg[variable]
    fs = float(block["fs"])
    hp = block["hp"]["highpass"]
    bp = block["bp"]["bandpass"]
    n_ch = hp.shape[0]
    eta = np.zeros(n_ch, dtype=float)
    rho = np.zeros(n_ch, dtype=float)
    for i in range(n_ch):
        eta[i] = compute_eta(hp[i], fs, cfg)
        rho[i] = compute_rho(bp[i], fs, cfg)
    return eta, rho


def select_median_eta_channel(
    metal_segs: Dict[str, Dict[str, Any]],
    cfg: ChFusionConfig,
) -> Tuple[int, np.ndarray]:
    """Pick channel with median-of-median η across segments & modals (typical)."""
    # Use mean η across 3 modals per segment, then median across segments
    n_ch = None
    eta_stack = []
    for name, seg in metal_segs.items():
        if not seg.get("ok"):
            continue
        etas = []
        for var in VARIABLES:
            eta, _ = per_channel_eta_rho(seg, var, cfg)
            etas.append(eta)
        mean_eta = np.mean(np.vstack(etas), axis=0)
        eta_stack.append(mean_eta)
        n_ch = len(mean_eta)
    assert n_ch is not None
    stacked = np.vstack(eta_stack)
    med = np.median(stacked, axis=0)
    # Require finite, positive median η (exclude NaN-poisoned / silent tones)
    valid = np.isfinite(med) & (med > 1e-4)
    if not np.any(valid):
        ch = int(np.nanargmax(med))
        return ch, med
    med_valid = med[valid]
    target = float(np.median(med_valid))
    candidates = np.where(valid)[0]
    ch = int(candidates[np.argmin(np.abs(med_valid - target))])
    return ch, med


def select_sensitive_channels(
    metal_segs: Dict[str, Dict[str, Any]],
    seg_names: Sequence[str],
    cfg: ChFusionConfig,
    n_pick: int = 4,
) -> List[int]:
    """Channels with largest η range across the given segments (mean over modals)."""
    per_seg = []
    for name in seg_names:
        seg = metal_segs[name]
        etas = []
        for var in VARIABLES:
            eta, _ = per_channel_eta_rho(seg, var, cfg)
            etas.append(eta)
        per_seg.append(np.mean(np.vstack(etas), axis=0))
    arr = np.vstack(per_seg)  # (n_seg, n_ch)
    spread = np.max(arr, axis=0) - np.min(arr, axis=0)
    order = np.argsort(-spread)
    return [int(i) for i in order[:n_pick]]


# ---------------------------------------------------------------------------
# Figure A
# ---------------------------------------------------------------------------

def plot_fig_a(
    metal_segs: Dict[str, Dict[str, Any]],
    ch: int,
    figures_dir: Path,
) -> List[Path]:
    paths: List[Path] = []
    panel_paths: List[Path] = []

    for seg_i in range(1, 17):
        name = f"seg{seg_i}"
        seg = metal_segs[name]
        if not seg.get("ok"):
            continue
        dist = metal_distance_cm(seg_i)
        fig, ax = plt.subplots(figsize=(8, 2.8), dpi=150)
        t = seg["time_sec"]
        for var in VARIABLES:
            y = _normalize01(seg[var]["hp"]["highpass"][ch])
            ax.plot(
                t,
                y,
                color=MODAL_COLORS[var],
                lw=STYLE["linewidth"],
                label=MODAL_LABELS[var],
            )
        ax.set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
        ax.set_ylabel("Normalized", fontsize=STYLE["fontsize"])
        ax.set_title(
            f"Fig A1 — ch{ch}, {dist} cm (seg{seg_i})",
            fontsize=STYLE["fontsize"],
        )
        ax.legend(loc="upper right", fontsize=9, frameon=False)
        _apply_style(ax)
        fig.tight_layout()
        out = figures_dir / f"position_sweep_figA1_seg{seg_i}_{dist}cm.png"
        fig.savefig(out, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        paths.append(out)
        panel_paths.append(out)
        print(f"  wrote {out.name}")

    # A2 stitched
    if panel_paths:
        n = len(panel_paths)
        fig, axes = plt.subplots(n, 1, figsize=(8, 1.6 * n), dpi=150, sharex=False)
        if n == 1:
            axes = [axes]
        for ax, seg_i in zip(axes, range(1, 17)):
            name = f"seg{seg_i}"
            seg = metal_segs[name]
            dist = metal_distance_cm(seg_i)
            if not seg.get("ok"):
                ax.set_visible(False)
                continue
            t = seg["time_sec"]
            for var in VARIABLES:
                y = _normalize01(seg[var]["hp"]["highpass"][ch])
                ax.plot(t, y, color=MODAL_COLORS[var], lw=1.4, label=MODAL_LABELS[var])
            ax.set_ylabel(f"{dist} cm", fontsize=9)
            ax.set_xlim(0, max(float(t[-1]), 1e-3))
            ax.tick_params(labelsize=8)
            _apply_style(ax)
            if seg_i == 1:
                ax.legend(loc="upper right", fontsize=7, frameon=False, ncol=3)
            if seg_i < 16:
                ax.set_xlabel("")
            else:
                ax.set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
        fig.suptitle(f"Fig A2 — Fixed ch{ch}, 100→85 cm (HP only)", fontsize=12, y=1.0)
        fig.tight_layout()
        out = figures_dir / "position_sweep_figA2_stitched.png"
        fig.savefig(out, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        paths.append(out)
        print(f"  wrote {out.name}")

    # A3 selected contrast: seg7 (double peak note) vs seg14 (pseudo double peak)
    selected = [7, 14]
    fig, axes = plt.subplots(len(selected), 1, figsize=(8, 5.5), dpi=150)
    for ax, seg_i in zip(axes, selected):
        name = f"seg{seg_i}"
        seg = metal_segs[name]
        dist = metal_distance_cm(seg_i)
        t = seg["time_sec"]
        for var in VARIABLES:
            y = _normalize01(seg[var]["hp"]["highpass"][ch])
            ax.plot(t, y, color=MODAL_COLORS[var], lw=STYLE["linewidth"], label=MODAL_LABELS[var])
        ax.set_title(f"seg{seg_i} — {dist} cm", fontsize=STYLE["fontsize"])
        ax.set_ylabel("Normalized", fontsize=STYLE["fontsize"])
        _apply_style(ax)
        ax.legend(loc="upper right", fontsize=8, frameon=False)
    axes[-1].set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
    fig.suptitle(f"Fig A3 — Selected positions (ch{ch})", fontsize=12)
    fig.tight_layout()
    out = figures_dir / "position_sweep_figA3_selected_positions.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths.append(out)
    print(f"  wrote {out.name}")
    return paths


# ---------------------------------------------------------------------------
# Figure B
# ---------------------------------------------------------------------------

def plot_fig_b(
    metal_segs: Dict[str, Dict[str, Any]],
    b1_channels: Sequence[int],
    b2_channels: Sequence[int],
    figures_dir: Path,
) -> List[Path]:
    """B1 overlays ``b1_channels``; B2 matrix uses evenly spaced ``b2_channels``."""
    paths: List[Path] = []
    seg_names = ["seg13", "seg14", "seg15"]
    seg_dists = [metal_distance_cm(13), metal_distance_cm(14), metal_distance_cm(15)]

    for var in VARIABLES:
        fig, axes = plt.subplots(3, 1, figsize=(8, 7), dpi=150, sharex=False)
        for ax, sname, dist in zip(axes, seg_names, seg_dists):
            seg = metal_segs[sname]
            t = seg["time_sec"]
            for ci, ch in enumerate(b1_channels):
                y = _zscore(seg[var]["hp"]["highpass"][ch])
                ax.plot(
                    t,
                    y,
                    color=CHANNEL_COLORS[ci % len(CHANNEL_COLORS)],
                    lw=1.5,
                    label=f"ch{ch}",
                )
            ax.set_ylabel(f"{dist} cm\n(z-score)", fontsize=9)
            ax.set_title(f"{sname}", fontsize=10)
            _apply_style(ax)
            if sname == "seg13":
                ax.legend(loc="upper right", fontsize=8, frameon=False, ncol=2)
        axes[-1].set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
        short = MODAL_SHORT[var]
        fig.suptitle(
            f"Fig B1 — {MODAL_LABELS[var]} channel contrast (seg13–15)",
            fontsize=12,
        )
        fig.tight_layout()
        out = figures_dir / f"position_sweep_figB1_{short}.png"
        fig.savefig(out, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        paths.append(out)
        print(f"  wrote {out.name}")

    # B2 matrix: evenly spaced channels × 3 segments, remote only
    ch_show = list(b2_channels)[:3]
    fig, axes = plt.subplots(3, 3, figsize=(10, 7), dpi=150, sharex=False, sharey=False)
    var = "remote_amplitudes"
    for r, ch in enumerate(ch_show):
        for c, (sname, dist) in enumerate(zip(seg_names, seg_dists)):
            ax = axes[r, c]
            seg = metal_segs[sname]
            t = seg["time_sec"]
            y = _zscore(seg[var]["hp"]["highpass"][ch])
            ax.plot(t, y, color=CHANNEL_COLORS[r], lw=1.4)
            if r == 0:
                ax.set_title(f"{dist} cm", fontsize=10)
            if c == 0:
                ax.set_ylabel(f"ch{ch}", fontsize=10)
            _apply_style(ax)
            ax.tick_params(labelsize=7)
    fig.tight_layout()
    out_stem = figures_dir / "position_sweep_figB2_channel_position_matrix"
    png, pdf = _save_png_pdf(fig, out_stem)
    plt.close(fig)
    paths.extend([png, pdf])
    print(f"  wrote {png.name} + {pdf.name}")
    return paths


# ---------------------------------------------------------------------------
# Figure C
# ---------------------------------------------------------------------------

def plot_fig_c(
    metal_segs: Dict[str, Dict[str, Any]],
    cfg: ChFusionConfig,
    figures_dir: Path,
) -> List[Path]:
    paths: List[Path] = []
    positions = {
        "good": ("seg5", metal_distance_cm(5)),
        "hard": ("seg14", metal_distance_cm(14)),
    }

    for pos_key, (sname, dist) in positions.items():
        seg = metal_segs[sname]
        for var in VARIABLES:
            block = seg[var]
            fs = float(block["fs"])
            X = block["bp"]["bandpass"]  # (n_ch, T)
            eta, rho = per_channel_eta_rho(seg, var, cfg)
            q = eta * np.clip(rho, 0.0, None)
            # Use full segment as one "window"
            _, phases, coherences, info = estimate_phase_hilbert(X, q)
            ref = int(info["ref_idx"])
            short = MODAL_SHORT[var]
            t = block["time_sec"]

            # Paper C1 hard_remote: panel (a) only, 6–8 tones, vertical stack
            if pos_key == "hard" and var == "remote_amplitudes":
                selected = _select_representative_tones(
                    phases, coherences, eta, rho, ref, k=8
                )
                fig, ax = plt.subplots(figsize=(8, 6.5), dpi=150)
                for i, ch in enumerate(selected):
                    y = _zscore(X[ch]) + i * 3.0
                    ax.plot(
                        t,
                        y,
                        color=CHANNEL_COLORS[i % len(CHANNEL_COLORS)],
                        lw=1.5,
                        label=f"ch{ch}",
                    )
                ax.set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
                ax.set_ylabel("Offset z-score", fontsize=STYLE["fontsize"])
                ax.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
                _apply_style(ax)
                fig.tight_layout()
                out_stem = figures_dir / f"position_sweep_figC1_{pos_key}_{short}"
                png, pdf = _save_png_pdf(fig, out_stem)
                plt.close(fig)
                paths.extend([png, pdf])
                print(f"  wrote {png.name} + {pdf.name}")
            else:
                selected = _select_representative_tones(
                    phases, coherences, eta, rho, ref, k=4
                )

                X_sel = X[selected]
                raw_z = np.vstack([_zscore(row) for row in X_sel])
                if ref in selected:
                    local_ref = selected.index(ref)
                else:
                    local_ref = 0
                pca_sign = _apply_corr_sign(X_sel, local_ref)
                pca_sign = np.vstack([_zscore(row) for row in pca_sign])
                hilbert_aligned = _apply_hilbert_align(X, phases)[selected]

                fig, axes = plt.subplots(3, 1, figsize=(8, 7.5), dpi=150, sharex=True)
                panels = [
                    ("(a) Bandpass waveforms", raw_z),
                    ("(b) Corr-sign corrected", pca_sign),
                    ("(c) Hilbert phase-aligned", hilbert_aligned),
                ]
                for ax, (title, mat) in zip(axes, panels):
                    for i, ch in enumerate(selected):
                        ax.plot(
                            t,
                            mat[i],
                            color=CHANNEL_COLORS[i % len(CHANNEL_COLORS)],
                            lw=1.5,
                            label=f"ch{ch}",
                        )
                    ax.set_title(title, fontsize=10)
                    ax.set_ylabel("z-score", fontsize=9)
                    _apply_style(ax)
                    ax.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
                axes[-1].set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
                fig.suptitle(
                    f"Fig C1 — {pos_key} ({sname}, {dist} cm) / {MODAL_LABELS[var]}",
                    fontsize=12,
                )
                fig.tight_layout()
                out = figures_dir / f"position_sweep_figC1_{pos_key}_{short}.png"
                fig.savefig(out, bbox_inches="tight", facecolor="white")
                plt.close(fig)
                paths.append(out)
                print(f"  wrote {out.name}")

            # C2 heatmap
            gamma = _pairwise_coherence(X)
            fig, ax = plt.subplots(figsize=(5.5, 4.8), dpi=150)
            im = ax.imshow(gamma, cmap="viridis", vmin=0, vmax=1, aspect="auto")
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label("γ", fontsize=STYLE["fontsize"])
            ax.set_xlabel("Tone index", fontsize=STYLE["fontsize"])
            ax.set_ylabel("Tone index", fontsize=STYLE["fontsize"])
            ax.set_title(
                f"Fig C2 — γ heatmap / {pos_key} / {MODAL_LABELS[var]}",
                fontsize=11,
            )
            _apply_style(ax)
            fig.tight_layout()
            out = figures_dir / f"position_sweep_figC2_heatmap_{pos_key}_{short}.png"
            fig.savefig(out, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            paths.append(out)
            print(f"  wrote {out.name}")
    return paths


# ---------------------------------------------------------------------------
# Figure D
# ---------------------------------------------------------------------------

def plot_fig_d(
    metal_segs: Dict[str, Dict[str, Any]],
    d1_channel: int,
    d2_channels: Sequence[int],
    figures_dir: Path,
) -> Tuple[List[Path], Dict[str, Any]]:
    """D1 uses the typical channel; D2 tracks Δφ on spaced / diverse tones."""
    paths: List[Path] = []
    dphi_store: Dict[str, Any] = {
        "d1_channel": int(d1_channel),
        "d2_channels": [int(c) for c in d2_channels],
        "segments": {},
    }

    # D1: one overlay per segment for typical channel (aligned with Fig A)
    ch0 = int(d1_channel)
    for seg_i in range(1, 17):
        name = f"seg{seg_i}"
        seg = metal_segs[name]
        if not seg.get("ok"):
            continue
        dist = metal_distance_cm(seg_i)
        fig, ax = plt.subplots(figsize=(8, 2.8), dpi=150)
        t = seg["time_sec"]
        for var in VARIABLES:
            y = _zscore(seg[var]["bp"]["bandpass"][ch0])
            ax.plot(t, y, color=MODAL_COLORS[var], lw=STYLE["linewidth"], label=MODAL_LABELS[var])
        ax.set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
        ax.set_ylabel("z-score", fontsize=STYLE["fontsize"])
        ax.set_title(f"Fig D1 — ch{ch0}, {dist} cm (seg{seg_i})", fontsize=STYLE["fontsize"])
        ax.legend(loc="upper right", fontsize=8, frameon=False)
        _apply_style(ax)
        fig.tight_layout()
        out = figures_dir / f"position_sweep_figD1_seg{seg_i}_{dist}cm.png"
        fig.savefig(out, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        paths.append(out)

    print(f"  wrote {16} D1 panels for ch{ch0}")

    # D2: Δφ vs position for each selected channel
    pairs = [
        ("remote_amplitudes", "local_amplitudes", "Δφ(R,L)"),
        ("remote_amplitudes", "phases", "Δφ(R,P)"),
        ("local_amplitudes", "phases", "Δφ(L,P)"),
    ]
    pair_colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]

    for ch in d2_channels:
        xs, series = [], {lab: [] for _, _, lab in pairs}
        for seg_i in range(1, 17):
            name = f"seg{seg_i}"
            seg = metal_segs[name]
            if not seg.get("ok"):
                continue
            fs = float(seg["fs"])
            sl = _mid_window_slice(len(seg["time_sec"]), fs, 10.0)
            dist = metal_distance_cm(seg_i)
            xs.append(dist)
            rec = {}
            for va, vb, lab in pairs:
                a = seg[va]["bp"]["bandpass"][ch][sl]
                b = seg[vb]["bp"]["bandpass"][ch][sl]
                dphi = _instantaneous_dphi(a, b)
                series[lab].append(dphi)
                rec[lab] = dphi
            dphi_store["segments"].setdefault(name, {})[f"ch{ch}"] = rec

        fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
        for (va, vb, lab), color in zip(pairs, pair_colors):
            ax.plot(
                xs,
                series[lab],
                "o-",
                color=color,
                lw=STYLE["linewidth"],
                ms=5,
                label=lab,
            )
        ax.set_xlabel("Distance (cm)", fontsize=STYLE["fontsize"])
        ax.set_ylabel("Δφ (rad)", fontsize=STYLE["fontsize"])
        ax.set_title(f"ch {ch}", fontsize=STYLE["fontsize"])
        # xs already ordered 100→85; keep 100 on left (near→far)
        ax.set_xlim(101, 84)
        ax.legend(loc="best", fontsize=9, frameon=False)
        _apply_style(ax)
        fig.tight_layout()
        out_stem = figures_dir / f"position_sweep_figD2_dphi_vs_position_ch{ch}"
        png, pdf = _save_png_pdf(fig, out_stem)
        plt.close(fig)
        paths.extend([png, pdf])
        print(f"  wrote {png.name} + {pdf.name}")

    # Stitched vertical panel for spaced tones (paper Ch.4)
    stitch_chs = [c for c in (20, 40, 60) if c in set(d2_channels)]
    if len(stitch_chs) == 3:
        fig, axes = plt.subplots(3, 1, figsize=(8, 8.5), dpi=150, sharex=True)
        for ax, ch in zip(axes, stitch_chs):
            xs, series = [], {lab: [] for _, _, lab in pairs}
            for seg_i in range(1, 17):
                name = f"seg{seg_i}"
                seg = metal_segs[name]
                if not seg.get("ok"):
                    continue
                fs = float(seg["fs"])
                sl = _mid_window_slice(len(seg["time_sec"]), fs, 10.0)
                xs.append(metal_distance_cm(seg_i))
                for va, vb, lab in pairs:
                    a = seg[va]["bp"]["bandpass"][ch][sl]
                    b = seg[vb]["bp"]["bandpass"][ch][sl]
                    series[lab].append(_instantaneous_dphi(a, b))
            for (va, vb, lab), color in zip(pairs, pair_colors):
                ax.plot(
                    xs,
                    series[lab],
                    "o-",
                    color=color,
                    lw=STYLE["linewidth"],
                    ms=5,
                    label=lab,
                )
            ax.set_ylabel("Δφ (rad)", fontsize=STYLE["fontsize"])
            ax.set_title(f"ch {ch}", fontsize=STYLE["fontsize"])
            ax.set_xlim(101, 84)
            ax.legend(loc="best", fontsize=8, frameon=False)
            _apply_style(ax)
        axes[-1].set_xlabel("Distance (cm)", fontsize=STYLE["fontsize"])
        fig.tight_layout()
        out_stem = figures_dir / "position_sweep_figD2_dphi_vs_position_ch20_40_60"
        png, pdf = _save_png_pdf(fig, out_stem)
        plt.close(fig)
        paths.extend([png, pdf])
        print(f"  wrote {png.name} + {pdf.name}")

    return paths, dphi_store


# ---------------------------------------------------------------------------
# Figure E
# ---------------------------------------------------------------------------

def _nearest_metal_for_human_dist(dist_cm: int) -> Tuple[str, int, bool]:
    """Return (seg_name, metal_dist_cm, exact_match)."""
    # Available metal distances: 100..85
    metal_dist = int(np.clip(dist_cm, 85, 100))
    # Prefer exact; for 80→85
    if dist_cm < 85:
        metal_dist = 85
        exact = False
    else:
        exact = metal_dist == dist_cm
    seg_i = 100 - metal_dist + 1
    return f"seg{seg_i}", metal_dist, exact


def plot_fig_e(
    metal_segs: Dict[str, Dict[str, Any]],
    human_segs: Dict[str, Dict[str, Any]],
    metal_frames: List[dict],
    fp: FilterParams,
    channel_keys: Sequence[int],
    cfg: ChFusionConfig,
    figures_dir: Path,
) -> Tuple[List[Path], Dict[str, Any]]:
    paths: List[Path] = []

    # Rebuild metal seg1 without walking for 100 cm comparison
    seg1_clean = prepare_segment(
        filter_frames_by_seq(metal_frames, *METAL_SEGMENTS["seg1"]),
        fp=fp,
        channel_keys=channel_keys,
        trim_seq_after=METAL_SEG1_WALK_END_SEQ,
    )

    quality: Dict[str, Any] = {"pairs": {}}

    # E1 waveforms — pick one typical channel (median η on metal side of pair)
    for hname, hdist in HUMAN_DIST_CM.items():
        mname, mdist, exact = _nearest_metal_for_human_dist(hdist)
        hseg = human_segs[hname]
        if mname == "seg1" and seg1_clean.get("ok"):
            mseg = seg1_clean
        else:
            mseg = metal_segs[mname]
        if not hseg.get("ok") or not mseg.get("ok"):
            print(f"  skip E1 {hname}: missing data")
            continue

        # pick channel by metal median-η proximity using remote
        eta_m, _ = per_channel_eta_rho(mseg, "remote_amplitudes", cfg)
        ch = int(np.argmin(np.abs(eta_m - np.median(eta_m))))

        for var in VARIABLES:
            fig, ax = plt.subplots(figsize=(8, 2.8), dpi=150)
            tm = mseg[var]["time_sec"]
            th = hseg[var]["time_sec"]
            ym = _zscore(mseg[var]["bp"]["bandpass"][ch])
            yh = _zscore(hseg[var]["bp"]["bandpass"][ch])
            label_m = f"Metal {mdist} cm" + ("" if exact else f" (≈{hdist} cm req.)")
            ax.plot(tm, ym, color="#7f7f7f", lw=STYLE["linewidth"], label=label_m)
            ax.plot(th, yh, color="#e07a3d", lw=STYLE["linewidth"], label=f"Human {hdist} cm")
            ax.set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
            ax.set_ylabel("z-score", fontsize=STYLE["fontsize"])
            short = MODAL_SHORT[var]
            ax.set_title(
                f"Fig E1 — {MODAL_LABELS[var]} @ ~{hdist} cm (ch{ch})",
                fontsize=STYLE["fontsize"],
            )
            ax.legend(loc="upper right", fontsize=8, frameon=False)
            _apply_style(ax)
            fig.tight_layout()
            out = figures_dir / f"position_sweep_figE1_{hdist}cm_{short}.png"
            fig.savefig(out, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            paths.append(out)
            print(f"  wrote {out.name}")

    # E2 / E3: per-channel mean η (±std) and ρ
    # Structure: for each (dist_label, variable): metal vs human arrays
    dist_keys = [100, 90, 80]
    eta_means = {  # key -> (metal_mean, metal_std, human_mean, human_std)
        "metal": {v: [] for v in VARIABLES},
        "human": {v: [] for v in VARIABLES},
    }
    rho_means = {
        "metal": {v: [] for v in VARIABLES},
        "human": {v: [] for v in VARIABLES},
    }
    meta_rows = []

    for hname, hdist in [("H3", 100), ("H2", 90), ("H1", 80)]:
        mname, mdist, exact = _nearest_metal_for_human_dist(hdist)
        hseg = human_segs[hname]
        mseg = seg1_clean if (mname == "seg1" and seg1_clean.get("ok")) else metal_segs[mname]
        row = {
            "human_seg": hname,
            "human_dist_cm": hdist,
            "metal_seg": mname,
            "metal_dist_cm": mdist,
            "exact_distance_match": exact,
        }
        for var in VARIABLES:
            if mseg.get("ok"):
                eta_m, rho_m = per_channel_eta_rho(mseg, var, cfg)
            else:
                eta_m = rho_m = np.array([np.nan])
            if hseg.get("ok"):
                eta_h, rho_h = per_channel_eta_rho(hseg, var, cfg)
            else:
                eta_h = rho_h = np.array([np.nan])
            eta_means["metal"][var].append((float(np.nanmean(eta_m)), float(np.nanstd(eta_m))))
            eta_means["human"][var].append((float(np.nanmean(eta_h)), float(np.nanstd(eta_h))))
            rho_means["metal"][var].append((float(np.nanmean(rho_m)), float(np.nanstd(rho_m))))
            rho_means["human"][var].append((float(np.nanmean(rho_h)), float(np.nanstd(rho_h))))
            row[f"{var}_eta_metal_mean"] = float(np.nanmean(eta_m))
            row[f"{var}_eta_human_mean"] = float(np.nanmean(eta_h))
            row[f"{var}_rho_metal_mean"] = float(np.nanmean(rho_m))
            row[f"{var}_rho_human_mean"] = float(np.nanmean(rho_h))
        meta_rows.append(row)
        quality["pairs"][f"{hdist}cm"] = row

    # E2 bar chart
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
    x_labels = []
    metal_y, metal_e, human_y, human_e = [], [], [], []
    for di, dist in enumerate(dist_keys):
        for var in VARIABLES:
            x_labels.append(f"{MODAL_SHORT[var]}\n{dist}cm")
            mi = dist_keys.index(dist)
            mm, ms = eta_means["metal"][var][mi]
            hm, hs = eta_means["human"][var][mi]
            metal_y.append(mm)
            metal_e.append(ms)
            human_y.append(hm)
            human_e.append(hs)
    idx = np.arange(len(x_labels))
    w = 0.36
    ax.bar(
        idx - w / 2,
        metal_y,
        w,
        yerr=metal_e,
        color="#9e9e9e",
        edgecolor="black",
        linewidth=0.6,
        label="Metal plate",
        capsize=3,
    )
    ax.bar(
        idx + w / 2,
        human_y,
        w,
        yerr=human_e,
        color="#e07a3d",
        edgecolor="black",
        linewidth=0.6,
        label="Human",
        capsize=3,
    )
    ax.set_xticks(idx)
    ax.set_xticklabels(x_labels, fontsize=8)
    ax.set_ylabel("η (mean ± std across tones)", fontsize=STYLE["fontsize"])
    ax.set_title("Fig E2 — η comparison: metal vs human", fontsize=STYLE["fontsize"])
    ax.legend(frameon=False, fontsize=9)
    _apply_style(ax)
    fig.tight_layout()
    out = figures_dir / "position_sweep_figE2_eta_comparison.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths.append(out)
    print(f"  wrote {out.name}")

    # E3: η + ρ grouped (4 bars)
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=150)
    x_labels = []
    vals = {k: [] for k in ("m_eta", "h_eta", "m_rho", "h_rho")}
    errs = {k: [] for k in ("m_eta", "h_eta", "m_rho", "h_rho")}
    for dist in dist_keys:
        for var in VARIABLES:
            x_labels.append(f"{MODAL_SHORT[var]}\n{dist}cm")
            mi = dist_keys.index(dist)
            mm, ms = eta_means["metal"][var][mi]
            hm, hs = eta_means["human"][var][mi]
            rm, rs = rho_means["metal"][var][mi]
            rh, rhs = rho_means["human"][var][mi]
            # normalize ρ for shared axis readability: show raw ρ on secondary later
            vals["m_eta"].append(mm)
            vals["h_eta"].append(hm)
            vals["m_rho"].append(rm)
            vals["h_rho"].append(rh)
            errs["m_eta"].append(ms)
            errs["h_eta"].append(hs)
            errs["m_rho"].append(rs)
            errs["h_rho"].append(rhs)

    idx = np.arange(len(x_labels))
    w = 0.2
    ax.bar(idx - 1.5 * w, vals["m_eta"], w, yerr=errs["m_eta"], color="#9e9e9e",
           label="Metal η", capsize=2, edgecolor="black", linewidth=0.5)
    ax.bar(idx - 0.5 * w, vals["h_eta"], w, yerr=errs["h_eta"], color="#e07a3d",
           label="Human η", capsize=2, edgecolor="black", linewidth=0.5)
    ax2 = ax.twinx()
    ax2.bar(idx + 0.5 * w, vals["m_rho"], w, yerr=errs["m_rho"], color="#5c5c5c",
            label="Metal ρ", capsize=2, edgecolor="black", linewidth=0.5, alpha=0.85)
    ax2.bar(idx + 1.5 * w, vals["h_rho"], w, yerr=errs["h_rho"], color="#c44e1a",
            label="Human ρ", capsize=2, edgecolor="black", linewidth=0.5, alpha=0.85)
    ax.set_xticks(idx)
    ax.set_xticklabels(x_labels, fontsize=8)
    ax.set_ylabel("η (energy ratio)", fontsize=STYLE["fontsize"])
    ax2.set_ylabel("ρ (peak prominence)", fontsize=STYLE["fontsize"])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper right")
    _apply_style(ax)
    fig.tight_layout()
    out_stem = figures_dir / "position_sweep_figE3_eta_rho_comparison"
    png, pdf = _save_png_pdf(fig, out_stem)
    plt.close(fig)
    paths.extend([png, pdf])
    print(f"  wrote {png.name} + {pdf.name}")

    quality["rows"] = meta_rows
    return paths, quality


# ---------------------------------------------------------------------------
# Quality dump helpers
# ---------------------------------------------------------------------------

def dump_segment_quality(
    metal_segs: Dict[str, Dict[str, Any]],
    cfg: ChFusionConfig,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, seg in metal_segs.items():
        if not seg.get("ok"):
            continue
        rec = {"fs": float(seg["fs"]), "n_samples": int(len(seg["time_sec"]))}
        for var in VARIABLES:
            eta, rho = per_channel_eta_rho(seg, var, cfg)
            rec[var] = {"eta": eta, "rho": rho}
        out[name] = rec
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated figure groups: A,B,C,D,E (default: all)",
    )
    args = parser.parse_args()
    only = {x.strip().upper() for x in args.only.split(",") if x.strip()} or None

    print("=== Position sweep observation (plan) ===")
    fp = FilterParams()
    cfg = ChFusionConfig()

    print("Loading metal JSONL…")
    metal_frames = load_jsonl_frames(METAL_PATH)
    print(f"  metal frames: {len(metal_frames)}")
    print("Loading human JSONL…")
    human_frames = load_jsonl_frames(HUMAN_PATH)
    print(f"  human frames: {len(human_frames)}")

    channel_keys = list(range(72))

    print("Preparing metal segments…")
    metal_segs = prepare_all_metal(metal_frames, fp, channel_keys)
    print("Preparing human segments…")
    human_segs = prepare_all_human(human_frames, fp, channel_keys)

    ch_typ, med_eta = select_median_eta_channel(metal_segs, cfg)
    print(f"Typical channel (median η): ch{ch_typ}  (median-η={med_eta[ch_typ]:.4f})")

    spaced_chs = [20, 40, 60]
    print(f"Spaced channels (B1/B2): {spaced_chs}")

    sens_chs = select_sensitive_channels(
        metal_segs, ["seg13", "seg14", "seg15"], cfg, n_pick=4
    )
    diverse_pair = [35, 71]
    d2_channels = list(dict.fromkeys(diverse_pair + spaced_chs))
    print(f"Sensitive channels (seg13-15, diagnostic only): {sens_chs}")
    print(f"D2 channels (35+71 + spaced): {d2_channels}")

    all_paths: List[Path] = []

    if only is None or "A" in only:
        print("\n--- Figure A ---")
        all_paths.extend(plot_fig_a(metal_segs, ch_typ, FIGURES_DIR))

    if only is None or "B" in only:
        print("\n--- Figure B ---")
        all_paths.extend(plot_fig_b(metal_segs, spaced_chs, spaced_chs, FIGURES_DIR))

    if only is None or "C" in only:
        print("\n--- Figure C ---")
        all_paths.extend(plot_fig_c(metal_segs, cfg, FIGURES_DIR))

    if only is None or "D" in only:
        print("\n--- Figure D ---")
        d_paths, dphi_store = plot_fig_d(metal_segs, ch_typ, d2_channels, FIGURES_DIR)
        all_paths.extend(d_paths)
    else:
        dphi_store = {"skipped": True}

    if only is None or "E" in only:
        print("\n--- Figure E ---")
        e_paths, human_vs_metal = plot_fig_e(
            metal_segs,
            human_segs,
            metal_frames,
            fp,
            channel_keys,
            cfg,
            FIGURES_DIR,
        )
        all_paths.extend(e_paths)
    else:
        human_vs_metal = {"skipped": True}

    if only is None:
        seg_quality = dump_segment_quality(metal_segs, cfg)
        seg_quality_path = REPORTS_DIR / "position_sweep_segment_quality.npy"
        np.save(seg_quality_path, seg_quality, allow_pickle=True)

        dphi_path = REPORTS_DIR / "position_sweep_dphi_per_segment.npy"
        np.save(dphi_path, dphi_store, allow_pickle=True)

        hv_path = REPORTS_DIR / "position_sweep_human_vs_metal_quality.npy"
        np.save(hv_path, human_vs_metal, allow_pickle=True)

        meta = {
            "typical_channel": int(ch_typ),
            "spaced_channels_b1_b2": [int(c) for c in spaced_chs],
            "sensitive_channels_seg13_15": [int(c) for c in sens_chs],
            "d2_channels": [int(c) for c in d2_channels],
            "d2_diverse_pair": [int(c) for c in diverse_pair],
            "metal_path": str(METAL_PATH),
            "human_path": str(HUMAN_PATH),
            "n_figures": len(all_paths),
            "figure_files": [p.name for p in all_paths],
            "human_vs_metal_summary": human_vs_metal.get("rows", []),
            "notes": {
                "human_frame_counts": {
                    k: int(human_segs[k]["n_frames_raw"]) if human_segs[k].get("ok") else 0
                    for k in HUMAN_SEGMENTS
                },
                "metal_80cm_fallback": "human 80 cm compared to metal 85 cm (seg16)",
                "seg1_walk_trim_seq": f"{METAL_SEG1_WALK_END_SEQ} dropped for E@100cm",
                "channel_selection": (
                    "B1/B2 use evenly spaced tones [20,40,60]; "
                    "D1 uses typical median-η channel; "
                    "D2 uses diverse η-spread pair + spaced set"
                ),
            },
        }
        meta_path = REPORTS_DIR / "position_sweep_observation_meta.json"
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        print("\n=== Done ===")
        print(f"Figures: {len(all_paths)}")
        print(f"Typical channel: ch{ch_typ}")
        print(f"Saved: {seg_quality_path.name}, {dphi_path.name}, {hv_path.name}, {meta_path.name}")
    else:
        print("\n=== Done (partial) ===")
        print(f"Figures: {len(all_paths)}")
        for p in all_paths:
            print(f"  {p.name}")



if __name__ == "__main__":
    main()
