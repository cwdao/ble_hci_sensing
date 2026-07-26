"""IQ radial / tangential breath-energy diagnostics for Phase Plan P0.

Implements complementary-projection geometry on per-tone complex PCT:
radial ∝ amplitude response, tangential ∝ phase response.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np


def extract_pct_complex_series(
    frames: Sequence[dict],
    *,
    channel_keys: Optional[Sequence] = None,
) -> Tuple[np.ndarray, np.ndarray, List]:
    """Extract local/remote complex PCT time series from BLE frames.

    Uses ``il/ql`` and ``ir/qr`` fields when present.

    Returns
    -------
    z_local, z_remote : complex ndarray, shape (n_tones, n_frames)
    channel_keys : list of tone keys used (sorted)
    """
    if not frames:
        raise ValueError("frames is empty")

    if channel_keys is None:
        keys = set()
        for fr in frames:
            keys.update(fr.get("channels", {}).keys())

        def _sk(k):
            if isinstance(k, (int, float)):
                return (0, int(k))
            if isinstance(k, str) and k.isdigit():
                return (0, int(k))
            return (1, str(k))

        channel_keys = sorted(keys, key=_sk)
    else:
        channel_keys = list(channel_keys)

    n_t = len(channel_keys)
    n_f = len(frames)
    z_l = np.full((n_t, n_f), np.nan + 1j * np.nan, dtype=np.complex128)
    z_r = np.full((n_t, n_f), np.nan + 1j * np.nan, dtype=np.complex128)

    for ti, fr in enumerate(frames):
        chs = fr.get("channels", {})
        for ci, ck in enumerate(channel_keys):
            # int/str key compatibility
            ch = None
            for cand in (ck, str(ck), int(ck) if str(ck).lstrip("-").isdigit() else None):
                if cand is None:
                    continue
                if cand in chs:
                    ch = chs[cand]
                    break
            if ch is None:
                continue
            if "il" in ch and "ql" in ch:
                z_l[ci, ti] = complex(float(ch["il"]), float(ch["ql"]))
            elif "local_amplitude" in ch and "local_phase" in ch:
                a = float(ch["local_amplitude"])
                p = float(ch["local_phase"])
                z_l[ci, ti] = a * np.exp(1j * p)
            if "ir" in ch and "qr" in ch:
                z_r[ci, ti] = complex(float(ch["ir"]), float(ch["qr"]))
            elif "remote_amplitude" in ch and "remote_phase" in ch:
                a = float(ch["remote_amplitude"])
                p = float(ch["remote_phase"])
                z_r[ci, ti] = a * np.exp(1j * p)

    return z_l, z_r, channel_keys


def compute_radial_tangential_energy(
    z_complex: np.ndarray,
    fs: float,
    f_band: Tuple[float, float] = (0.1, 0.35),
    *,
    nfft: Optional[int] = None,
) -> Dict[str, np.ndarray]:
    """Per-tone radial / tangential breath-band energy for one window.

    Parameters
    ----------
    z_complex : (n_tones, n_timesteps) complex
    fs : sampling rate
    f_band : breath band (Hz)

    Returns
    -------
    dict with E_rad, E_tan, static_ref (each length n_tones)
    """
    z = np.asarray(z_complex, dtype=np.complex128)
    if z.ndim != 2:
        raise ValueError(f"z_complex must be 2D, got shape {z.shape}")
    n_tones, n_t = z.shape
    if n_t < 4:
        nan = np.full(n_tones, np.nan)
        return {"E_rad": nan.copy(), "E_tan": nan.copy(), "static_ref": nan.astype(np.complex128)}

    # window-mean static reference (ignore NaN tones/samples)
    static_ref = np.nanmean(z, axis=1)
    ang = np.angle(static_ref)
    rot = np.exp(-1j * ang)[:, None]
    delta = z - static_ref[:, None]
    proj = delta * rot
    r = np.real(proj)
    q = np.imag(proj)

    # replace nan with 0 for FFT energy (missing tones stay nan in output)
    r = np.nan_to_num(r, nan=0.0)
    q = np.nan_to_num(q, nan=0.0)

    nfft = int(nfft or max(256, 1 << int(np.ceil(np.log2(max(n_t, 4))))))
    freqs = np.fft.rfftfreq(nfft, d=1.0 / float(fs))
    band = (freqs >= f_band[0]) & (freqs <= f_band[1])
    if not np.any(band):
        nan = np.full(n_tones, np.nan)
        return {"E_rad": nan.copy(), "E_tan": nan.copy(), "static_ref": static_ref}

    win = np.hanning(n_t)
    r_w = r * win[None, :]
    q_w = q * win[None, :]
    R = np.fft.rfft(r_w, n=nfft, axis=1)
    Q = np.fft.rfft(q_w, n=nfft, axis=1)
    e_rad = np.sum(np.abs(R[:, band]) ** 2, axis=1)
    e_tan = np.sum(np.abs(Q[:, band]) ** 2, axis=1)

    # tones that were entirely NaN
    all_nan = ~np.any(np.isfinite(z), axis=1)
    e_rad = e_rad.astype(float)
    e_tan = e_tan.astype(float)
    e_rad[all_nan] = np.nan
    e_tan[all_nan] = np.nan
    return {"E_rad": e_rad, "E_tan": e_tan, "static_ref": static_ref}


def aggregate_modal_energies(
    e_rad_local: np.ndarray,
    e_rad_remote: np.ndarray,
    e_tan_local: np.ndarray,
    e_tan_remote: np.ndarray,
) -> Dict[str, float]:
    """Aggregate per-tone energies to modal scalars (nanmean over tones)."""
    return {
        "E_rad_R": float(np.nanmean(e_rad_remote)),
        "E_rad_L": float(np.nanmean(e_rad_local)),
        "E_tan_P": float(np.nanmean(e_tan_local + e_tan_remote)),
        "E_tan_R": float(np.nanmean(e_tan_remote)),
        "E_tan_L": float(np.nanmean(e_tan_local)),
    }


def compute_phase_oracle_delta(
    bpm_errors: Mapping[str, Mapping[str, np.ndarray]],
    *,
    tau: float = 1.0,
) -> "Any":
    """Recording-level Δ_oracle = E[min(e_R,e_L)] − E[min(e_R,e_L,e_P)].

    Parameters
    ----------
    bpm_errors : {recording: {"remote"|"local"|"phase": errors}}
    tau : unused (kept for plan signature compatibility); reserved for rescue metrics

    Returns
    -------
    pandas.DataFrame or list[dict] if pandas unavailable
    """
    _ = tau
    rows: List[Dict[str, Any]] = []
    for rec, mods in bpm_errors.items():
        e_r = np.asarray(mods["remote"], dtype=float)
        e_l = np.asarray(mods["local"], dtype=float)
        e_p = np.asarray(mods["phase"], dtype=float)
        n = min(len(e_r), len(e_l), len(e_p))
        e_r, e_l, e_p = e_r[:n], e_l[:n], e_p[:n]
        e_rl = np.minimum(e_r, e_l)
        e_rlp = np.minimum(e_rl, e_p)
        rows.append(
            {
                "recording": rec,
                "n_windows": int(n),
                "e_rl_oracle": float(np.nanmean(e_rl)),
                "e_rlp_oracle": float(np.nanmean(e_rlp)),
                "delta_oracle": float(np.nanmean(e_rl) - np.nanmean(e_rlp)),
                "phase_improves_frac": float(np.nanmean(e_p < e_rl)),
            }
        )
    try:
        import pandas as pd

        return pd.DataFrame(rows)
    except ImportError:
        return rows


def recording_level_paired_bootstrap(
    results: Mapping[str, Mapping[str, float]],
    n_bootstrap: int = 10000,
    *,
    seed: int = 0,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Recording-level paired bootstrap 95% CI for all method pairs.

    Parameters
    ----------
    results : {method: {recording: mean_error}}
    """
    methods = list(results.keys())
    # intersect recording ids
    rec_sets = [set(results[m].keys()) for m in methods]
    recordings = sorted(set.intersection(*rec_sets)) if rec_sets else []
    if len(recordings) < 2:
        return {"n_recordings": len(recordings), "pairs": {}}

    rng = np.random.default_rng(seed)
    n = len(recordings)
    mats = {m: np.asarray([results[m][r] for r in recordings], dtype=float) for m in methods}

    pairs: Dict[str, Any] = {}
    for i, a in enumerate(methods):
        for b in methods[i + 1 :]:
            diff = mats[a] - mats[b]
            observed = float(np.mean(diff))
            boots = np.empty(n_bootstrap, dtype=float)
            for k in range(n_bootstrap):
                idx = rng.integers(0, n, size=n)
                boots[k] = float(np.mean(diff[idx]))
            lo = float(np.quantile(boots, alpha / 2))
            hi = float(np.quantile(boots, 1 - alpha / 2))
            pairs[f"{a}__vs__{b}"] = {
                "method_a": a,
                "method_b": b,
                "mean_diff_a_minus_b": observed,
                "ci_low": lo,
                "ci_high": hi,
                "ci_includes_0": bool(lo <= 0.0 <= hi),
                "n_recordings": n,
            }
    return {"n_recordings": n, "recordings": recordings, "pairs": pairs}


def compute_amplitude_joint_weakness(
    eta_r: np.ndarray,
    eta_l: np.ndarray,
    eta_p: np.ndarray | None = None,
    *,
    norm_method: str = "recording_median",
    eps: float = 1e-12,
) -> Dict[str, np.ndarray]:
    """Compute q_amp = max(η̃_R, η̃_L) with recording-median normalization.

    Old Null Score = min/max is also returned for contrast (deprecated).
    """
    _ = eta_p  # reserved for future joint tests
    er = np.asarray(eta_r, dtype=float)
    el = np.asarray(eta_l, dtype=float)
    if norm_method == "recording_median":
        er_n = er / (float(np.nanmedian(er)) + eps)
        el_n = el / (float(np.nanmedian(el)) + eps)
    else:
        er_n, el_n = er, el
    q_amp = np.maximum(er_n, el_n)
    q_amp_geo = np.sqrt(np.clip(er_n, 0, None) * np.clip(el_n, 0, None))
    mn = np.minimum(er_n, el_n)
    mx = np.maximum(er_n, el_n)
    null_score_deprecated = mn / (mx + eps)
    return {
        "eta_r_norm": er_n,
        "eta_l_norm": el_n,
        "q_amp": q_amp,
        "q_amp_geo": q_amp_geo,
        "null_score_deprecated": null_score_deprecated,
    }


def compute_rescue_metrics(
    bpm_errors: Mapping[str, np.ndarray],
    tau: float = 1.0,
) -> Dict[str, float]:
    """Rescue / unique-correct / destruction rates at absolute-error threshold τ."""
    e_r = np.asarray(bpm_errors["remote"], dtype=float)
    e_l = np.asarray(bpm_errors["local"], dtype=float)
    e_p = np.asarray(bpm_errors["phase"], dtype=float)
    n = min(len(e_r), len(e_l), len(e_p))
    e_r, e_l, e_p = e_r[:n], e_l[:n], e_p[:n]
    e_rl = np.minimum(e_r, e_l)

    both_fail = (e_r > tau) & (e_l > tau)
    rescue = both_fail & (e_p <= tau)
    unique = (e_p <= tau) & (e_r > tau) & (e_l > tau)
    rl_ok = e_rl <= tau
    destroy = rl_ok & (e_p > tau)

    return {
        "tau": float(tau),
        "n": float(n),
        "rescue_rate": float(np.sum(rescue) / max(np.sum(both_fail), 1)),
        "n_both_fail": float(np.sum(both_fail)),
        "n_rescue": float(np.sum(rescue)),
        "unique_correct": float(np.sum(unique) / max(n, 1)),
        "n_unique": float(np.sum(unique)),
        "destruction_rate": float(np.sum(destroy) / max(np.sum(rl_ok), 1)),
        "n_rl_ok": float(np.sum(rl_ok)),
        "n_destroy": float(np.sum(destroy)),
        "oracle_rl": float(np.nanmean(e_rl)),
        "oracle_rlp": float(np.nanmean(np.minimum(e_rl, e_p))),
        "corr_err_rl": float(np.corrcoef(e_r, e_l)[0, 1]) if n > 2 else float("nan"),
        "corr_err_rp": float(np.corrcoef(e_r, e_p)[0, 1]) if n > 2 else float("nan"),
        "corr_err_lp": float(np.corrcoef(e_l, e_p)[0, 1]) if n > 2 else float("nan"),
    }


def detect_temporal_clustering(
    window_indices: np.ndarray,
    step_sec: float = 1.0,
    *,
    max_gap_steps: int = 1,
) -> Dict[str, Any]:
    """Detect temporal clustering of selected windows.

    Consecutive indices within ``max_gap_steps`` form one segment.
    """
    idx = np.asarray(window_indices, dtype=int)
    idx = np.unique(idx[~np.isnan(idx.astype(float))])
    idx = np.sort(idx)
    n_total = int(len(idx))
    if n_total == 0:
        return {
            "n_segments": 0,
            "max_segment_len": 0.0,
            "max_segment_windows": 0,
            "n_total_windows": 0,
            "segment_lengths": [],
            "independence_ratio": float("nan"),
        }

    segments: List[List[int]] = [[int(idx[0])]]
    for w in idx[1:]:
        if int(w) - segments[-1][-1] <= max_gap_steps:
            segments[-1].append(int(w))
        else:
            segments.append([int(w)])

    lengths = [len(s) for s in segments]
    max_len = max(lengths)
    return {
        "n_segments": int(len(segments)),
        "max_segment_len": float(max_len * step_sec),
        "max_segment_windows": int(max_len),
        "n_total_windows": n_total,
        "segment_lengths": lengths,
        "independence_ratio": float(len(segments) / n_total),
    }
