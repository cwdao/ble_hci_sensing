"""P1: cs_091339 harmonic + PC1 spectrum diagnostics.

Run after cross-domain reports exist:
``python notebooks/scripts/chFusion_pca_svd_p1_diag.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.bootstrap import init_notebook
from ble_analysis.pca_svd import (
    PcaSvdConfig,
    diagnose_complex_integration_harmonics,
    extract_integration_pc1_spectrum,
)
from ble_analysis.scenarios import load_scenario
from ble_analysis.segments import BreathMetricParams

_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]

DIAG_SCENARIO_ID = "cs_091339"


def main():
    sc = load_scenario(DIAG_SCENARIO_ID, project_root=project_root)
    path = REPORTS_DIR / f"chfusion_pca_svd_{sc.tag}.npy"
    if not path.is_file():
        raise FileNotFoundError(f"Missing report: {path}. Run cross_domain first.")
    cached = np.load(path, allow_pickle=True).item()
    diag_mc = cached["multichannel_by_var"]
    metric_params = BreathMetricParams()
    pca_hp_config = PcaSvdConfig(signal_key="highpass_filtered")

    print(f"\n{'=' * 72}\n  PC1 harmonic diagnosis — {sc.tag}\n{'=' * 72}")
    diag_summary = []
    for method_label, integration in (("η-blend ch-η", "eta_blend"), ("Dual-Amp ch-η", "dual_amp")):
        harm = diagnose_complex_integration_harmonics(
            diag_mc, integration=integration, channel_weight="energy_ratio",
            metric_params=metric_params, pca_svd_config=pca_hp_config,
        )
        for seg_name, row in sorted(harm.items()):
            if row is None:
                continue
            fr = row["harmonic_fracs"]
            print(
                f"  {method_label:<28} {seg_name:<12} GT={row['bpm_gt']:.0f} "
                f"err={row['mean_rel_err_pct']:.1f}%  "
                f"fund={fr['fundamental']:.0%} dbl={fr['double']:.0%} "
                f"half={fr['half']:.0%} oth={fr['other']:.0%}"
            )
            diag_summary.append({"method": method_label, "segment": seg_name, **row})

    np.save(
        REPORTS_DIR / f"chfusion_pca_svd_{sc.tag}_harmonic_diag.npy",
        {"scenario_id": DIAG_SCENARIO_ID, "summary": diag_summary},
        allow_pickle=True,
    )

    worst_seg, worst_err = None, -1.0
    harm_eta = diagnose_complex_integration_harmonics(
        diag_mc, integration="eta_blend", channel_weight="energy_ratio",
        metric_params=metric_params, pca_svd_config=pca_hp_config,
    )
    for seg_name, row in harm_eta.items():
        if row is None:
            continue
        err = row.get("mean_rel_err_pct", np.nan)
        if np.isfinite(err) and err > worst_err:
            worst_err, worst_seg = float(err), seg_name

    if not worst_seg:
        print("No worst segment for spectrum plot.")
        return

    plot_specs = (
        ("η-blend ch-η", "eta_blend"),
        ("Dual-Amp ch-η", "dual_amp"),
        ("Total ch-η", "total_complex"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8))
    for ax, (label, integration) in zip(axes, plot_specs):
        snap = extract_integration_pc1_spectrum(
            diag_mc, worst_seg, integration=integration, window_index=0,
            channel_weight="energy_ratio",
            metric_params=metric_params, pca_svd_config=pca_hp_config,
        )
        if snap is None:
            ax.set_title(f"{label}\n(no data)")
            continue
        ax.plot(snap["band_freqs"] * 60.0, snap["spectrum"], color="#2E6F9E", lw=1.5)
        if np.isfinite(snap["gt_hz"]):
            ax.axvline(snap["gt_hz"] * 60.0, color="#C44E52", ls="--", lw=1.2, label="GT")
        if np.isfinite(snap["peak_hz"]):
            ax.axvline(snap["peak_hz"] * 60.0, color="#55A868", ls=":", lw=1.2, label="PC1 peak")
        ax.set_xlabel("BPM")
        ax.set_ylabel("Norm. power")
        ax.set_title(label)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.25)
    fig.suptitle(f"091339 worst seg {worst_seg} (η-blend err≈{worst_err:.1f}%)", fontsize=10)
    plt.tight_layout()
    spec_path = FIGURES_DIR / f"pca_svd_{sc.tag}_worst_seg_pc1_spectrum.pdf"
    fig.savefig(spec_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Saved spectrum fig -> {spec_path.name}")


if __name__ == "__main__":
    main()
