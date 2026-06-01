"""chFusion FFT+q — CS metal-plate segment BPM benchmark script.

Overview
========
End-to-end experiment script for BLE Channel Sounding (CS) respiration-rate (BPM)
estimation on scripted metal-plate segments. Implements the method design in
``docs/chfusion_fft-q.md`` and reuses the segment filter pipeline from
``glb_cs_segment_breath_analysis`` (median -> highpass -> bandpass).

Background: valid CS observables
--------------------------------
After local/remote vector composition, only four scalar series per channel are
physically meaningful for fusion (single-ended phases are not used alone):

  - ``amplitudes``          total amplitude
  - ``remote_amplitudes``   remote-reported amplitude
  - ``local_amplitudes``    local-measured amplitude
  - ``phases``              total phase (**np.unwrap** before filtering)

Pipeline per variable x channel x segment
-----------------------------------------
1. Load CS frames (``load_ble_frames``).
2. Extract each script segment by frame index (``segment_config``).
3. For all available channels: preprocess (unwrap if phase) -> filter ->
   sliding-window FFT BPM estimation.

Comparison design (two parts)
-----------------------------
**Part 1 — Which variable is best?**
  Four variables, one method only:
  **Single** = per window, pick the channel with largest breath-band energy ratio,
  then take the FFT peak BPM on that channel's bandpass signal.

**Part 2 — Which fusion method is best (per variable)?**
  Four variables x three methods:
  - **Single**      max-energy-ratio single channel (same as Part 1)
  - **Uniform**     equal-weight average of per-channel normalized FFT spectra
  - **FFT+q_peak**  q_peak-weighted fusion (spectral peak SNR only; no q_phi)

**Overview 4×3 — Full matrix across variables and methods**
  Part 1 only compares variables under Single; Part 2 splits by variable.
  The overview figures put all 12 (variable × method) combinations on one page:

  - Bar chart / heatmap: segment-level mean relative error (leaderboard metrics)
  - Violins by method (1×3): extends Part 1 to all three methods — which variable
    wins under Single vs Uniform vs FFT+q_peak?
  - Violins by variable (2×2): merges Part 2 into one figure — fusion vs single
    per CS observable

  Use bars/heatmap for a quick ranking; use matrix violins for dispersion
  (window-level signed error distribution) across segments.

Outputs
-------
- Console tables: Part 1 variable ranking, Part 2 method tables per variable,
  overall leaderboard (12 combos sorted by mean relative BPM error).
- ``outputs/reports/chfusion_benchmark_matrix.npy`` — full numeric results.
- Figures (PDF vector format, English labels; y=0 dashed line = ground truth):
  - ``chfusion_part1_variable_violins.pdf`` — 4 variables x segments (Single only)
  - ``chfusion_part2_<variable>_violins.pdf`` — 3 methods x segments per variable
  - **4×3 overview** (all variables × all methods):
    - ``chfusion_overview_4x3_mean_error_bars.pdf`` — grouped bar chart (mean ± std)
    - ``chfusion_overview_4x3_heatmap.pdf`` — mean error heatmap
    - ``chfusion_overview_4x3_violins_by_method.pdf`` — 1×3 panels: per method, 4 variables
    - ``chfusion_overview_4x3_violins_by_variable.pdf`` — 2×2 panels: per variable, 3 methods
  Violin markers: **black bar = mean**, **white bar = median** of window-level
  signed BPM errors (estimated - GT).

Key modules
-----------
- ``src/ble_analysis/chfusion.py`` — algorithms, tables, plotting
- ``src/ble_analysis/segments.py``  — segment extract + filter chain

Run
---
  python notebooks/scripts/chFusion_fft-q.py

Or execute ``# %%`` cells in VS Code Python Interactive.
"""

# %% [markdown]
# # chFusion — multi-variable x multi-method BPM benchmark
#
# | Step | Content |
# |------|---------|
# | 0 | Bootstrap + parameters |
# | 1 | Run full benchmark (Part 1 + Part 2) |
# | 2 | Part 1 table — variable comparison (Single only) |
# | 3 | Part 2 tables — method comparison per variable |
# | 4 | Leaderboard + save `.npy` |
# | 5 | Violin plots (Part 1/2 + 4×3 overview: bars, heatmap, matrix violins) |
#
# See module docstring above for full workflow description.

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
#
# Edit ``filepath`` and ``segment_config`` for other recordings.
# Filter: median=3, HP 0.05 Hz, BP 0.1-0.35 Hz; sliding window 20 s / step 1 s.

# %%
from ble_analysis.chfusion import (
    CS_SIGNAL_VARIABLES,
    ChFusionConfig,
    plot_benchmark_violins,
    print_benchmark_leaderboard,
    print_part1_variable_table,
    print_part2_method_tables,
    print_q_score_documentation,
    run_chfusion_benchmark,
)
from ble_analysis.data import load_ble_frames
from ble_analysis.segments import BreathMetricParams, FilterParams

filepath = project_root / "sampleData" / "CS_frames_all_20260113_091339.jsonl"

# Metal-plate script segments with BPM ground truth (breath) or apnea labels
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

variables = [v[0] for v in CS_SIGNAL_VARIABLES]
print("Variables:", ", ".join(f"{k} ({lbl})" for k, lbl in CS_SIGNAL_VARIABLES))
print_q_score_documentation(chfusion_config)

# %% [markdown]
# ## 1. Run benchmark (all variables; Part 1 + Part 2)

# %%
data, frames = load_ble_frames(filepath, verbose=False)

benchmark = run_chfusion_benchmark(
    frames,
    segment_config,
    variables=variables,
    filter_params=filter_params,
    metric_params=metric_params,
    config=chfusion_config,
    verbose=True,
)

# %% [markdown]
# ## 2. Part 1 — variable comparison (Single / max-energy channel)

# %%
print_part1_variable_table(benchmark["part1"])

# %% [markdown]
# ## 3. Part 2 — method comparison per variable

# %%
print_part2_method_tables(benchmark["part2"])

# %% [markdown]
# ## 4. Leaderboard and save results

# %%
print_benchmark_leaderboard(benchmark["leaderboard"])

report_path = REPORTS_DIR / "chfusion_benchmark_matrix.npy"
np.save(report_path, benchmark, allow_pickle=True)
print(f"Saved: {report_path}")

# %% [markdown]
# ## 5. Violin plots (signed BPM error; GT at y=0)
#
# All figures are written as **PDF** by ``plot_benchmark_violins`` (see ``chfusion.py``).
#
# | Figure (``.pdf``) | What it compares |
# |--------|------------------|
# | ``part1_variable_violins`` | 4 variables, Single only (Part 1) |
# | ``part2_<var>_violins`` | 3 methods for one variable (Part 2, ×4 files) |
# | ``overview_4x3_mean_error_bars`` | 12 combos: mean segment rel err ± std |
# | ``overview_4x3_heatmap`` | Same 12 combos as colour matrix |
# | ``overview_4x3_violins_by_method`` | 1×3 panels: 4 variables per method |
# | ``overview_4x3_violins_by_variable`` | 2×2 panels: 3 methods per variable |
#
# Violin conventions: y = estimated BPM − GT; dashed y=0 = ground truth;
# black bar = mean, white bar = median of window errors; 1-window segments → scatter.

# %%
# Part 1 + Part 2 per-variable figures, then 4×3 overview (bars, heatmap, matrix violins).
plot_benchmark_violins(
    benchmark,
    figures_dir=FIGURES_DIR,
    show=True,
    save=True,
)
