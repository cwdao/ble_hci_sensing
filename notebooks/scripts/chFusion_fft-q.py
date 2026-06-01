"""chFusion FFT+q — CS metal-plate segment BPM benchmark script.

Overview
========
End-to-end experiment for BLE CS respiration-rate (BPM) on scripted metal-plate
segments. Compares **three fusion methods** across four CS observables.

Methods (see ``docs/chfusion_q_energy_peak.md``)
------------------------------------------------
- **FFT+q_energy**      — weight by log-mapped breath/total energy ratio η
- **FFT+q_peak**        — weight by log-mapped spectral peak SNR ρ
- **FFT+q_energy_peak** — weight by √(q_energy · q_peak), all channels

Variables: ``amplitudes``, ``remote_amplitudes``, ``local_amplitudes``, ``phases``
(phase unwrapped before filtering).

Pipeline
--------
1. Load CS frames → segment extract → median / HP / BP filter (all channels)
2. Sliding-window FFT → q scores → weighted spectral fusion → BPM
3. Tables + PDF figures under ``outputs/``

Run: ``python notebooks/scripts/chFusion_fft-q.py``
"""

# %% [markdown]
# # chFusion — 4 variables × 3 fusion methods
#
# | Step | Content |
# |------|---------|
# | 0 | Bootstrap + parameters |
# | 1 | Run benchmark |
# | 2 | Method tables per variable |
# | 3 | Leaderboard + save `.npy` |
# | 4 | Violin / overview PDF figures |

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
    plot_benchmark_violins,
    print_benchmark_leaderboard,
    print_part2_method_tables,
    print_q_score_documentation,
    run_chfusion_benchmark,
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

variables = [v[0] for v in CS_SIGNAL_VARIABLES]
print("Variables:", ", ".join(f"{k} ({lbl})" for k, lbl in CS_SIGNAL_VARIABLES))
print_q_score_documentation(chfusion_config)

# %% [markdown]
# ## 1. Run benchmark (4 variables × 3 methods)

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
# ## 2. Method comparison per variable

# %%
print_part2_method_tables(benchmark["part2"])

# %% [markdown]
# ## 3. Leaderboard and save results

# %%
print_benchmark_leaderboard(benchmark["leaderboard"])

report_path = REPORTS_DIR / "chfusion_benchmark_matrix.npy"
np.save(report_path, benchmark, allow_pickle=True)
print(f"Saved: {report_path}")

# %% [markdown]
# ## 4. PDF figures (violins + 4×3 overview)
#
# Methods: FFT+q_energy / FFT+q_peak / FFT+q_energy_peak

# %%
plot_benchmark_violins(
    benchmark,
    figures_dir=FIGURES_DIR,
    show=True,
    save=True,
)
