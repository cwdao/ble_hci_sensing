"""Cross-domain aggregation for Zhuo2023 PCA-VMD baselines.

Loads ``outputs/reports/zhuo2023_pca_vmd_results.npy`` and regenerates figures.

Run: ``python notebooks/scripts/chFusion_zhuo2023_pca_vmd_cross_domain.py``
"""

from __future__ import annotations

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

from ble_analysis.pca_vmd import (
    ZHUO2023_METHOD_SPECS,
    compute_zhuo2023_cross_domain,
    plot_zhuo2023_pca_vmd_figures,
)

SCENARIO_IDS = ("cs_091339", "cs_095806", "cs_102621")
RESULTS_PATH = REPORTS_DIR / "zhuo2023_pca_vmd_results.npy"

if not RESULTS_PATH.exists():
    raise FileNotFoundError(
        f"Missing {RESULTS_PATH}. Run chFusion_zhuo2023_pca_vmd.py --all first."
    )

results_by_scenario = np.load(RESULTS_PATH, allow_pickle=True).item()
cross_domain = compute_zhuo2023_cross_domain(results_by_scenario)
np.save(REPORTS_DIR / "zhuo2023_pca_vmd_cross_domain.npy", cross_domain, allow_pickle=True)

print("=== Cross-domain leaderboard ===")
for row in cross_domain:
    print(f"{row['rank']:>2}. {row['label']:<36} {row['cross_domain_mean']:.2f}%")

fig_paths = plot_zhuo2023_pca_vmd_figures(
    results_by_scenario,
    cross_domain,
    figures_dir=FIGURES_DIR,
    scenario_ids=SCENARIO_IDS,
    show=False,
    save=True,
)
for name, path in fig_paths.items():
    print(f"Saved figure: {path}")

print("\nDone.")
