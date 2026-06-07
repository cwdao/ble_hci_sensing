"""chFusion Voting Fusion — per-tone BPM voting validation.

Implements ``docs/plans/voting_fusion_plan.md``: T0/T1/T2/T3 voting methods
vs Plan2 baselines across three metal-plate scenarios.

Run: ``python notebooks/scripts/chFusion_voting_fusion.py``
"""

# %%
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

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
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]

# %%
from ble_analysis.chfusion import ChFusionConfig, Plan2Config, _overall_rel_error
from ble_analysis.data import load_ble_frames
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams
from ble_analysis.voting_fusion import (
    VOTING_METHOD_SPECS,
    build_voting_leaderboard_rows,
    compute_cross_domain_aggregate,
    run_voting_fusion_benchmark,
)

SCENARIO_IDS = ("cs_091339", "cs_095806", "cs_102621")

filter_params = FilterParams()
metric_params = BreathMetricParams()
chfusion_config = ChFusionConfig(
    breath_freq_low=metric_params.breath_freq_low,
    breath_freq_high=metric_params.breath_freq_high,
    window_length_sec=metric_params.window_length_sec,
    step_length_sec=metric_params.step_length_sec,
    enable_consensus=False,
)
plan2_config = Plan2Config(channel_metric="energy_ratio")

# %%
results_by_scenario: dict = {}

for scenario_id in SCENARIO_IDS:
    scenario = load_scenario(scenario_id, project_root=project_root)
    print(f"\n{'=' * 60}")
    print_scenario_summary(scenario)
    _data, frames = load_ble_frames(scenario.resolve_data_path(project_root), verbose=False)
    bench = run_voting_fusion_benchmark(
        frames,
        scenario.segment_config,
        filter_params=filter_params,
        metric_params=metric_params,
        config=chfusion_config,
        plan2_config=plan2_config,
        verbose=True,
    )
    results_by_scenario[scenario_id] = bench
    report_path = REPORTS_DIR / f"voting_fusion_{scenario.tag}_results.npy"
    np.save(report_path, bench, allow_pickle=True)
    print(f"Saved: {report_path}")

np.save(REPORTS_DIR / "voting_fusion_results.npy", results_by_scenario, allow_pickle=True)
print(f"\nSaved combined: {REPORTS_DIR / 'voting_fusion_results.npy'}")

# %%
cross_domain = compute_cross_domain_aggregate(results_by_scenario)
np.save(REPORTS_DIR / "voting_fusion_cross_domain.npy", cross_domain, allow_pickle=True)

print("\n=== Cross-domain leaderboard (mean err%) ===")
print(f"{'Rank':<5} {'Method':<28} {'Mean':>8} {'±std':>8}")
print("-" * 52)
for row in cross_domain:
    print(
        f"{row['rank']:<5} {row['label']:<28} "
        f"{row['cross_domain_mean']:8.2f} {row['cross_domain_std']:8.2f}"
    )

# %%
# Per-scenario table
print("\n=== Per-scenario mean err% ===")
header = f"{'Method':<28}" + "".join(f"{sid[-6:]:>10}" for sid in SCENARIO_IDS) + f"{'X-dom':>10}"
print(header)
print("-" * len(header))
for label, key, _ in VOTING_METHOD_SPECS:
    row = f"{label:<28}"
    per_scenario = []
    for sid in SCENARIO_IDS:
        stats = _overall_rel_error(results_by_scenario[sid]["results"], key)
        val = stats["mean_rel_err_pct"]
        per_scenario.append(val)
        row += f"{val:10.2f}" if np.isfinite(val) else f"{'—':>10}"
    xdom = float(np.mean([v for v in per_scenario if np.isfinite(v)])) if per_scenario else np.nan
    row += f"{xdom:10.2f}" if np.isfinite(xdom) else f"{'—':>10}"
    print(row)

# %%
# Leaderboard bar chart (cross-domain)
fig, ax = plt.subplots(figsize=(12, 6))
labels = [r["label"] for r in cross_domain]
means = [r["cross_domain_mean"] for r in cross_domain]
stds = [r["cross_domain_std"] for r in cross_domain]
colors = [r["color"] for r in cross_domain]
y_pos = np.arange(len(labels))
ax.barh(y_pos, means, xerr=stds, color=colors, alpha=0.85, capsize=3)
ax.set_yticks(y_pos)
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel("Mean BPM relative error (%)")
ax.set_title("Voting Fusion — cross-domain aggregate (3 metal-plate scenarios)")
ax.axvline(9.45, color="gray", linestyle="--", linewidth=1, label="Modal top2 ref (9.45%)")
ax.legend(loc="lower right")
ax.grid(True, axis="x", alpha=0.3)
plt.tight_layout()
leaderboard_path = FIGURES_DIR / "voting_fusion_leaderboard.pdf"
fig.savefig(leaderboard_path, bbox_inches="tight")
print(f"Saved: {leaderboard_path}")
plt.close(fig)

# %%
# Cross-domain aggregate bars (scenario-colored)
fig, ax = plt.subplots(figsize=(14, 6))
method_labels = [r["label"] for r in cross_domain[:8]]
x = np.arange(len(method_labels))
width = 0.25
scenario_colors = ["#4C72B0", "#55A868", "#C44E52"]
for i, sid in enumerate(SCENARIO_IDS):
    tag = load_scenario(sid, project_root=project_root).tag
    vals = []
    for row in cross_domain[:8]:
        stats = _overall_rel_error(results_by_scenario[sid]["results"], row["method_key"])
        vals.append(stats["mean_rel_err_pct"])
    ax.bar(x + (i - 1) * width, vals, width, label=tag, color=scenario_colors[i], alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels(method_labels, rotation=30, ha="right", fontsize=8)
ax.set_ylabel("Mean BPM relative error (%)")
ax.set_title("Voting Fusion — top-8 methods by scenario")
ax.legend()
ax.grid(True, axis="y", alpha=0.3)
plt.tight_layout()
cross_path = FIGURES_DIR / "voting_fusion_cross_domain_aggregate_bars.pdf"
fig.savefig(cross_path, bbox_inches="tight")
print(f"Saved: {cross_path}")
plt.close(fig)

# %%
# Diagnostics: per-tone BPM scatter vs GT (091339, one segment)
diag_scenario = "cs_091339"
bench = results_by_scenario[diag_scenario]
results = bench["results"]
seg_name = "3"
row = results.get(seg_name)
if row and "t0_v2_eta_weighted" in row:
    block = row["t0_v2_eta_weighted"]
    gt = row["bpm_gt"]
    tone_bpms = block.get("bpm_per_tone_per_window", [])
    conf = block.get("confident_per_window", [])
    voted = block.get("bpm_per_window", [])

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    # Panel 1: per-tone BPM vs window for first 3 windows
    for wi in range(min(3, len(tone_bpms))):
        tb = tone_bpms[wi]
        axes[0].scatter(
            np.full(len(tb), wi) + np.random.uniform(-0.1, 0.1, len(tb)),
            tb,
            s=8,
            alpha=0.5,
            label=f"win {wi}",
        )
        if wi < len(voted) and np.isfinite(voted[wi]):
            axes[0].axhline(voted[wi], color="red", linestyle="--", alpha=0.4)
    axes[0].axhline(gt, color="black", linestyle="-", linewidth=2, label=f"GT={gt}")
    axes[0].set_xlabel("Window index (sample)")
    axes[0].set_ylabel("Per-tone BPM")
    axes[0].set_title(f"Per-tone BPM scatter (seg {seg_name})")
    axes[0].legend(fontsize=7)

    # Panel 2: confidence distribution
    conf_frac = 1.0 - block.get("low_confidence_frac", 0.0)
    axes[1].bar(["confident", "low-conf"], [conf_frac, 1 - conf_frac], color=["green", "orange"])
    axes[1].set_ylabel("Fraction of windows")
    axes[1].set_title("Voting confidence (T0-V2)")

    # Panel 3: histogram example (last window)
    if tone_bpms:
        tb = tone_bpms[-1]
        valid = tb[np.isfinite(tb)]
        axes[2].hist(valid, bins=np.arange(5.5, 31.5, 1.0), edgecolor="black", alpha=0.7)
        axes[2].axvline(gt, color="black", linestyle="-", label=f"GT={gt}")
        if len(voted) and np.isfinite(voted[-1]):
            axes[2].axvline(voted[-1], color="red", linestyle="--", label=f"voted={voted[-1]:.1f}")
        axes[2].set_xlabel("BPM")
        axes[2].set_ylabel("Tone count")
        axes[2].set_title("Last-window BPM histogram")
        axes[2].legend(fontsize=8)

    plt.tight_layout()
    diag_path = FIGURES_DIR / "voting_fusion_diagnostics.pdf"
    fig.savefig(diag_path, bbox_inches="tight")
    print(f"Saved: {diag_path}")
    plt.close(fig)

print("\n=== Done ===")
