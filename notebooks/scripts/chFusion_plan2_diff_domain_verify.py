"""chFusion Plan 2 — cross-domain repeatability verification (095806).

Re-runs the full Plan 2 pipeline from ``chFusion_plan2.py`` on a second metal-plate
recording (``CS_frames_all_20260116_095806.jsonl``) using segment boundaries from
``notebooks/show_analysis_cs_frames_095806.ipynb``.

Purpose: check whether 091339 conclusions hold on a different CS domain:

- η channel selector vs ρ (optional second run)
- Single remote / phase / local baselines
- Modal fusion between best amplitude and phase
- top-2 modal vs full three-variable fusion

Run: ``python notebooks/scripts/chFusion_plan2_diff_domain_verify.py``
"""

# %% [markdown]
# # Plan 2 cross-domain verify — 095806
#
# | Step | Content |
# |------|---------|
# | 0 | Bootstrap + 095806 segment config |
# | 1 | Run Plan 2 validation (η selector, same as 091339) |
# | 2 | Complementarity waveforms (phase / remote / local) |
# | 3 | Comparison table + overview figures |
# | 4 | Cross-domain checklist vs 091339 (if saved) |

# %% [markdown]
# ## 0. Environment bootstrap

# %%
import sys
from pathlib import Path

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

# %% [markdown]
# ## 0b. Parameters — 095806 domain

# %%
from ble_analysis.chfusion import (
    COMPLEMENTARITY_REFERENCE_VARIABLES,
    ChFusionConfig,
    Plan2Config,
    build_plan2_leaderboard_rows,
    plot_complementarity_waveforms_all,
    plot_plan2_leaderboard_bars,
    plot_plan2_segment_method_heatmap,
    plot_plan2_violins_by_category,
    print_complementarity_window_summary,
    print_plan2_comparison_table,
    run_plan2_validation,
)
from ble_analysis.data import load_ble_frames
from ble_analysis.segments import BreathMetricParams, FilterParams

DOMAIN_ID = "095806"
REF_DOMAIN_ID = "091339"

filepath = project_root / "sampleData" / "CS_frames_all_20260116_095806.jsonl"

# Segment config from notebooks/show_analysis_cs_frames_095806.ipynb
# (same script / BPM GT as 091339 metal-plate protocol, different frame indices)
segment_config = {
    "1a": {"start": 73, "end": 183, "type": "breath", "ie_gt": 0.985, "bpm_gt": 8.675},
    "1b": {"start": 183, "end": 300, "type": "breath", "ie_gt": 1.451, "bpm_gt": 8.675},
    "2a": {"start": 300, "end": 354, "type": "breath", "ie_gt": 1.419, "bpm_gt": 11.49},
    "p1": {"start": 354, "end": 372, "type": "apnea", "apnea_gt_sec": 10.0},
    "2b": {"start": 372, "end": 409, "type": "breath", "ie_gt": 1.419, "bpm_gt": 11.49},
    "3": {"start": 409, "end": 516, "type": "breath", "ie_gt": 1.229, "bpm_gt": 14.04},
    "4a": {"start": 516, "end": 577, "type": "breath", "ie_gt": 1.081, "bpm_gt": 16.17},
    "p2": {"start": 577, "end": 594, "type": "apnea", "apnea_gt_sec": 10.0},
    "4b": {"start": 594, "end": 628, "type": "breath", "ie_gt": 1.081, "bpm_gt": 16.17},
}

filter_params = FilterParams()
metric_params = BreathMetricParams()
chfusion_config = ChFusionConfig(
    breath_freq_low=metric_params.breath_freq_low,
    breath_freq_high=metric_params.breath_freq_high,
    window_length_sec=metric_params.window_length_sec,
    step_length_sec=metric_params.step_length_sec,
    enable_consensus=False,
)

REFERENCE_VARIABLE = "phases"
COMPLEMENTARITY_VARS = list(COMPLEMENTARITY_REFERENCE_VARIABLES)
plan2_config = Plan2Config(channel_metric="energy_ratio")

FIG_PREFIX = f"plan2_{DOMAIN_ID}"
REPORT_PATH = REPORTS_DIR / f"chfusion_plan2_{DOMAIN_ID}_validation.npy"
REF_REPORT_PATH = REPORTS_DIR / "chfusion_plan2_validation.npy"

print(f"Domain: {DOMAIN_ID} | file: {filepath.name}")
print("Plan 2 channel metric:", plan2_config.channel_metric)
print("Complementarity refs:", ", ".join(COMPLEMENTARITY_VARS))

# %% [markdown]
# ## 1. Run Plan 2 validation

# %%
data, frames = load_ble_frames(filepath, verbose=False)

plan2 = run_plan2_validation(
    frames,
    segment_config,
    filter_params=filter_params,
    metric_params=metric_params,
    config=chfusion_config,
    plan2_config=plan2_config,
    reference_variable=REFERENCE_VARIABLE,
    complementarity_variables=COMPLEMENTARITY_VARS,
    verbose=True,
)

print_complementarity_window_summary(plan2["complementarity_by_reference"])

# %% [markdown]
# ## 2. Complementarity waveform figures (095806)

# %%
complementarity_paths = plot_complementarity_waveforms_all(
    plan2["complementarity_by_reference"],
    reference_variables=COMPLEMENTARITY_VARS,
    figures_dir=FIGURES_DIR,
    filename_prefix=f"{FIG_PREFIX}_complementarity",
    show=True,
    save=True,
)
print(f"Saved {len(complementarity_paths)} complementarity figure(s)")

# %% [markdown]
# ## 3. Comparison table + overview figures

# %%
print_plan2_comparison_table(plan2)

np.save(REPORT_PATH, plan2, allow_pickle=True)
print(f"Saved: {REPORT_PATH}")

overview_paths = []
for fname, plot_fn in (
    (f"{FIG_PREFIX}_leaderboard_bars.pdf", plot_plan2_leaderboard_bars),
    (f"{FIG_PREFIX}_segment_method_heatmap.pdf", plot_plan2_segment_method_heatmap),
    (f"{FIG_PREFIX}_violins_by_category.pdf", plot_plan2_violins_by_category),
):
    plot_fn(plan2, figures_dir=FIGURES_DIR, filename=fname, show=True, save=True)
    overview_paths.append(FIGURES_DIR / fname)
print(f"Saved {len(overview_paths)} overview figure(s)")

# %% [markdown]
# ## 4. Cross-domain hypothesis checklist (vs 091339)

# %%
def _leaderboard_lookup(plan2_result: dict) -> dict:
    return {r["label"]: r for r in build_plan2_leaderboard_rows(plan2_result)}


def _err(plan2_result: dict, label: str) -> float:
    row = _leaderboard_lookup(plan2_result).get(label)
    return float(row["mean_rel_err_pct"]) if row else float("nan")


def print_cross_domain_checklist(
    current: dict,
    reference: dict | None,
    *,
    cur_id: str,
    ref_id: str,
) -> None:
    """Print whether key Plan 2 hypotheses hold on *cur_id* vs *ref_id*."""
    cur = _leaderboard_lookup(current)
    ref_lb = _leaderboard_lookup(reference) if reference else {}

    compare_labels = [
        "Single Remote amplitude",
        "Single Local amplitude",
        "Single Total phase (unwrapped)",
        "Uniform Remote amplitude",
        "Modal top2 equal",
        "Modal η-weight",
        "Modal equal",
    ]

    print(f"\n=== Cross-domain leaderboard: {cur_id} vs {ref_id} ===")
    print(f"{'方法':<32} {cur_id:>10} {ref_id:>10}")
    print("-" * 54)
    for lbl in compare_labels:
        c = cur.get(lbl, {}).get("mean_rel_err_pct", np.nan)
        r = ref_lb.get(lbl, {}).get("mean_rel_err_pct", np.nan) if reference else np.nan
        c_str = f"{c:10.2f}" if np.isfinite(c) else f"{'—':>10}"
        r_str = f"{r:10.2f}" if np.isfinite(r) else f"{'—':>10}"
        print(f"{lbl:<32} {c_str} {r_str}")

    s_rem = _err(current, "Single Remote amplitude")
    s_loc = _err(current, "Single Local amplitude")
    s_pha = _err(current, "Single Total phase (unwrapped)")
    u_rem = _err(current, "Uniform Remote amplitude")
    m_top2 = _err(current, "Modal top2 equal")
    m_eq = _err(current, "Modal equal")

    print(f"\n=== Hypothesis checklist ({cur_id}) ===")
    checks = [
        (
            "Single remote 优于 Single local",
            np.isfinite(s_rem) and np.isfinite(s_loc) and s_rem < s_loc,
            f"remote={s_rem:.2f}% local={s_loc:.2f}%",
        ),
        (
            "Single remote 优于 Uniform remote",
            np.isfinite(s_rem) and np.isfinite(u_rem) and s_rem < u_rem,
            f"single={s_rem:.2f}% uniform={u_rem:.2f}%",
        ),
        (
            "Modal 介于 Single remote 与 Single phase 之间",
            np.isfinite(s_rem) and np.isfinite(s_pha) and np.isfinite(m_eq)
            and min(s_rem, s_pha) <= m_eq <= max(s_rem, s_pha),
            f"remote={s_rem:.2f}% modal={m_eq:.2f}% phase={s_pha:.2f}%",
        ),
        (
            "Modal top2 ≤ Modal equal（动态去掉较差变量）",
            np.isfinite(m_top2) and np.isfinite(m_eq) and m_top2 <= m_eq + 0.01,
            f"top2={m_top2:.2f}% equal={m_eq:.2f}%",
        ),
    ]
    for name, ok, detail in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {name}  ({detail})")


ref_plan2 = None
if REF_REPORT_PATH.is_file():
    ref_plan2 = np.load(REF_REPORT_PATH, allow_pickle=True).item()
    print(f"Loaded reference domain report: {REF_REPORT_PATH}")
else:
    print(f"Reference report not found ({REF_REPORT_PATH}); run chFusion_plan2.py on 091339 first.")

print_cross_domain_checklist(plan2, ref_plan2, cur_id=DOMAIN_ID, ref_id=REF_DOMAIN_ID)
