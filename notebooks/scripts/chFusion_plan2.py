"""chFusion Plan 2 — amplitude–phase complementarity & modal fusion validation.

Implements **改进方案2** from ``docs/CS呼吸算法验证整体进度.md``:

Part A — 幅值相位互补性（波形对比）
------------------------------------
On **total phase** Single (max-η channel) windows, pick best / worst / median
accuracy windows across all breath segments. At each window's phase-best channel,
plot normalized **bandpass** waveforms for all four CS variables with η annotations.

Part B — 只联合最好的信道 × 最好的变量
---------------------------------------
Per sliding window, each variable picks its own max-η channel; fuse spectra of
phase + remote amplitude + local amplitude (total amplitude excluded):

- **Modal equal**           — equal weights (1/3 each)
- **Modal η-weight**        — weights ∝ breath-band energy ratio η
- **Modal 0.5/0.25/0.25**   — phase 0.5, remote/local 0.25

Run: ``python notebooks/scripts/chFusion_plan2.py``
"""

# %% [markdown]
# # chFusion Plan 2 — 互补性波形 + 模态融合
#
# | Step | Content |
# |------|---------|
# | 0 | Bootstrap + parameters |
# | 1 | Run Plan 2 validation (filter 4 vars, collect windows, modal fusion) |
# | 2 | Complementarity waveform figures (best / worst / median phase windows) |
# | 3 | Modal fusion BPM tables |
# | 4 | Save results + optional violin plots |

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
# ## 0b. Parameters

# %%
from ble_analysis.chfusion import (
    CS_SIGNAL_VARIABLES,
    ChFusionConfig,
    build_plan2_comparison_method_labels,
    build_plan2_violin_results,
    plot_bpm_error_violins,
    plot_complementarity_waveforms,
    print_plan2_comparison_table,
    run_plan2_validation,
)
from ble_analysis.data import load_ble_frames
from ble_analysis.segments import BreathMetricParams, FilterParams

filepath = project_root / "sampleData" / "CS_frames_all_20260113_091339.jsonl"

segment_config = {
    "1a": {"start": 131, "end": 244, "type": "breath", "ie_gt": 0.985, "bpm_gt": 8.675},
    "1b": {"start": 244, "end": 361, "type": "breath", "ie_gt": 1.451, "bpm_gt": 8.675},
    "2a": {"start": 361, "end": 419, "type": "breath", "ie_gt": 1.419, "bpm_gt": 11.49},
    "p1": {"start": 419, "end": 437, "type": "apnea", "apnea_gt_sec": 10.0},
    "2b": {"start": 437, "end": 473, "type": "breath", "ie_gt": 1.419, "bpm_gt": 11.49},
    "3": {"start": 473, "end": 586, "type": "breath", "ie_gt": 1.229, "bpm_gt": 14.04},
    "4a": {"start": 586, "end": 648, "type": "breath", "ie_gt": 1.081, "bpm_gt": 16.17},
    "p2": {"start": 648, "end": 666, "type": "apnea", "apnea_gt_sec": 10.0},
    "4b": {"start": 666, "end": 702, "type": "breath", "ie_gt": 1.081, "bpm_gt": 16.17},
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
print("Plan 2 reference variable:", REFERENCE_VARIABLE)
print("CS variables:", ", ".join(f"{k} ({lbl})" for k, lbl in CS_SIGNAL_VARIABLES))
print("Comparison methods:", len(build_plan2_comparison_method_labels()), "total (4×Single + 4×Uniform + 3×modal)")

# %% [markdown]
# ## 1. Run Plan 2 validation
#
# Filters all four variables on all channels, collects per-window phase Single
# records, and runs three modal-fusion weight strategies.

# %%
data, frames = load_ble_frames(filepath, verbose=False)

plan2 = run_plan2_validation(
    frames,
    segment_config,
    filter_params=filter_params,
    metric_params=metric_params,
    config=chfusion_config,
    reference_variable=REFERENCE_VARIABLE,
    verbose=True,
)

n_windows = len(plan2["window_records"])
print(f"\nCollected {n_windows} phase Single windows across breath segments")

for tag, rec in plan2["complementarity_windows"].items():
    if rec is None:
        print(f"  [{tag}] — no window")
        continue
    print(
        f"  [{tag}] seg={rec['segment']} win={rec['window_idx']} ch={rec['best_channel']} "
        f"| est={rec['bpm_est']:.2f} GT={rec['bpm_gt']:.2f} | rel err={rec['rel_err']*100:.1f}%"
    )

# %% [markdown]
# ## 2. Complementarity waveform figures
#
# Three PDFs: phase BPM best / worst / median window; four normalized bandpass
# waveforms on the phase-best channel, each annotated with η (from highpass).

# %%
complementarity_paths = plot_complementarity_waveforms(
    plan2["complementarity_windows"],
    figures_dir=FIGURES_DIR,
    reference_variable=REFERENCE_VARIABLE,
    show=True,
    save=True,
)
print(f"Saved {len(complementarity_paths)} complementarity figure(s)")

# %% [markdown]
# ## 3. Baseline + modal fusion comparison table

# %%
print_plan2_comparison_table(plan2)

# %% [markdown]
# ## 4. Save results + violin plots (baselines + modal fusion)

# %%
report_path = REPORTS_DIR / "chfusion_plan2_validation.npy"
np.save(report_path, plan2, allow_pickle=True)
print(f"Saved: {report_path}")

comparison_labels = build_plan2_comparison_method_labels()
violin_results = build_plan2_violin_results(plan2)
plot_bpm_error_violins(
    violin_results,
    method_labels=comparison_labels,
    figures_dir=FIGURES_DIR,
    filename="chfusion_plan2_comparison_violins.pdf",
    title="Plan 2: 4×Single + 4×Uniform baselines + modal fusion",
    show=True,
    save=True,
)
print(f"Violin plot: {FIGURES_DIR / 'chfusion_plan2_comparison_violins.pdf'}")
