"""Zhuo 2023 PCA-VMD external baseline validation.

Implements ``docs/plans/zhuo2023_pca_vmd_baseline_plan.md``.

Run:
    python notebooks/scripts/chFusion_zhuo2023_pca_vmd.py --scenario cs_095806 --ablation
    python notebooks/scripts/chFusion_zhuo2023_pca_vmd.py --all
"""

from __future__ import annotations

import argparse
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
CACHE_DIR = str(project_root / "outputs" / "cache")

from ble_analysis.chfusion import ChFusionConfig, Plan2Config, _overall_rel_error, load_multichannel_for_scenario
from ble_analysis.pca_svd import PcaSvdConfig
from ble_analysis.pca_vmd import (
    VmdParams,
    ZHUO2023_METHOD_SPECS,
    ZHUO2023_VARIANT_SPECS,
    compute_zhuo2023_cross_domain,
    plot_zhuo2023_pca_vmd_figures,
    run_vmd_param_ablation,
    run_zhuo2023_pca_vmd_benchmark,
)
from ble_analysis.scenarios import load_scenario, print_scenario_summary
from ble_analysis.segments import BreathMetricParams, FilterParams

DEFAULT_SCENARIOS = ("cs_091339", "cs_095806", "cs_102621")
DEFAULT_VMD_PARAMS = VmdParams(K=3, alpha=3000.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zhuo2023 PCA-VMD baseline benchmark")
    parser.add_argument("--scenario", type=str, default=None, help="Single scenario id")
    parser.add_argument("--all", action="store_true", help="Run all three validation scenarios")
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run VMD (K, alpha) grid search on one scenario only",
    )
    parser.add_argument("--vmd-k", type=int, default=None, help="Override VMD K")
    parser.add_argument("--vmd-alpha", type=float, default=None, help="Override VMD alpha")
    return parser.parse_args()


def run_one_scenario(
    scenario_id: str,
    *,
    vmd_params: VmdParams,
    variants: tuple[str, ...],
) -> dict:
    scenario = load_scenario(scenario_id, project_root=project_root)
    print(f"\n{'=' * 60}")
    print_scenario_summary(scenario)
    multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
        scenario,
        project_root=project_root,
        filter_params=filter_params,
        cache_dir=CACHE_DIR,
        verbose=True,
    )
    bench = run_zhuo2023_pca_vmd_benchmark(
        None,
        scenario.segment_config,
        filter_params=filter_params,
        metric_params=metric_params,
        config=chfusion_config,
        plan2_config=plan2_config,
        pca_cfg=pca_cfg,
        variants=variants,
        vmd_params=vmd_params,
        verbose=True,
        cache_dir=CACHE_DIR,
        multichannel_by_var=multichannel_by_var,
    )
    tag = scenario.tag
    report_path = REPORTS_DIR / f"zhuo2023_pca_vmd_{tag}_results.npy"
    np.save(report_path, bench, allow_pickle=True)
    print(f"Saved: {report_path}")
    return bench


if __name__ == "__main__":
    args = parse_args()
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
    pca_cfg = PcaSvdConfig(signal_key="bandpass_filtered")

    if args.ablation:
        scenario_id = args.scenario or "cs_095806"
        scenario = load_scenario(scenario_id, project_root=project_root)
        print_scenario_summary(scenario)
        multichannel_by_var, _fs, _skipped = load_multichannel_for_scenario(
            scenario,
            project_root=project_root,
            filter_params=filter_params,
            cache_dir=CACHE_DIR,
            verbose=True,
        )
        ablation_rows = run_vmd_param_ablation(
            multichannel_by_var,
            config=chfusion_config,
            metric_params=metric_params,
            pca_cfg=pca_cfg,
        )
        ablation_path = REPORTS_DIR / "zhuo2023_pca_vmd_vmd_ablation.npy"
        np.save(ablation_path, ablation_rows, allow_pickle=True)
        print(f"\nSaved VMD ablation: {ablation_path}")
        print("\n=== Top 5 VMD (K, alpha) by Z1 mean err% ===")
        for row in ablation_rows[:5]:
            print(
                f"K={row['K']} alpha={row['alpha']:.0f} "
                f"mean={row['mean_rel_err_pct']:.2f}% std={row['std_rel_err_pct']:.2f}%"
            )
        best = ablation_rows[0]
        print(
            f"\nRecommended VMD params: K={best['K']}, alpha={best['alpha']:.0f}"
        )
        raise SystemExit(0)

    vmd_params = DEFAULT_VMD_PARAMS
    if args.vmd_k is not None:
        vmd_params = VmdParams(K=args.vmd_k, alpha=vmd_params.alpha)
    if args.vmd_alpha is not None:
        vmd_params = VmdParams(K=vmd_params.K, alpha=args.vmd_alpha)

    variants = tuple(ZHUO2023_VARIANT_SPECS.keys())

    if args.all or args.scenario is None:
        scenario_ids = list(DEFAULT_SCENARIOS)
    else:
        scenario_ids = [args.scenario]

    results_by_scenario: dict = {}
    for sid in scenario_ids:
        results_by_scenario[sid] = run_one_scenario(
            sid, vmd_params=vmd_params, variants=variants
        )

    combined_path = REPORTS_DIR / "zhuo2023_pca_vmd_results.npy"
    np.save(combined_path, results_by_scenario, allow_pickle=True)
    print(f"\nSaved combined: {combined_path}")

    cross_domain = compute_zhuo2023_cross_domain(results_by_scenario)
    np.save(REPORTS_DIR / "zhuo2023_pca_vmd_cross_domain.npy", cross_domain, allow_pickle=True)

    print("\n=== Cross-domain leaderboard (mean err%) ===")
    print(f"{'Rank':<5} {'Method':<36} {'Mean':>8} {'±std':>8}")
    print("-" * 60)
    for row in cross_domain:
        print(
            f"{row['rank']:<5} {row['label']:<36} "
            f"{row['cross_domain_mean']:8.2f} {row['cross_domain_std']:8.2f}"
        )

    print("\n=== Per-scenario mean err% ===")
    header = f"{'Method':<36}" + "".join(f"{sid[-6:]:>10}" for sid in scenario_ids) + f"{'X-dom':>10}"
    print(header)
    print("-" * len(header))
    for label, key, _ in ZHUO2023_METHOD_SPECS:
        row = f"{label:<36}"
        per_vals = []
        for sid in scenario_ids:
            stats = _overall_rel_error(results_by_scenario[sid]["results"], key)
            val = stats["mean_rel_err_pct"]
            per_vals.append(val)
            row += f"{val:10.2f}" if np.isfinite(val) else f"{'—':>10}"
        xdom = float(np.mean([v for v in per_vals if np.isfinite(v)])) if per_vals else np.nan
        row += f"{xdom:10.2f}" if np.isfinite(xdom) else f"{'—':>10}"
        print(row)

    if len(scenario_ids) == len(DEFAULT_SCENARIOS):
        fig_paths = plot_zhuo2023_pca_vmd_figures(
            results_by_scenario,
            cross_domain,
            figures_dir=FIGURES_DIR,
            scenario_ids=DEFAULT_SCENARIOS,
            show=False,
            save=True,
        )
        for name, path in fig_paths.items():
            print(f"Saved figure: {path}")

    print("\nDone. Report: docs/reports/zhuo2023_pca_vmd_baseline_report.md")
