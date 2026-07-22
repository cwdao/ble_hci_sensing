"""Replot paper-related HKH/B2 figures as PNG+PDF from existing summaries.

Does not re-run sensing experiments. Uses:
  - outputs/reports/ble_hkh_paper_baselines_summary.json
  - outputs/reports/ble_hkh_b3_validation_summary.json
  - outputs/reports/b2_coherent_mrc_all_cross_domain.npy
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_cwd = Path.cwd().resolve()
project_root = next((p for p in [_cwd, *_cwd.parents] if (p / "src").is_dir()), None)
if project_root is None:
    raise FileNotFoundError("Project root not found")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

# Import plot helpers from the validation scripts by path.
sys.path.insert(0, str(project_root / "notebooks" / "scripts"))

from ble_analysis.bootstrap import init_notebook  # noqa: E402
from ble_analysis.coherent_mrc import plot_b2_achievement_figures  # noqa: E402

import chFusion_ble_hkh_b3_validation as b3_mod  # noqa: E402
import chFusion_ble_hkh_paper_baselines as paper_mod  # noqa: E402

_env = init_notebook(project_root)
FIGURES_DIR = _env["FIGURES_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]


def _load_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").replace("NaN", "null")
    return json.loads(text)


def main() -> None:
    paper = _load_json(REPORTS_DIR / "ble_hkh_paper_baselines_summary.json")
    overall = paper["overall_leaderboard"]
    by_room = paper["by_room"]
    room_labels = {k: paper_mod.ROOM_LABELS.get(k, k) for k in by_room}
    by_room_labeled = {room_labels.get(k, k): v for k, v in by_room.items()}

    p_all = paper_mod.plot_cross_scenario_leaderboard(
        overall,
        f"HKH multi-subject — paper baselines BPM error (N={paper['n_scenarios']} scenarios)",
        "ble_hkh_paper_baselines_leaderboard_all.png",
    )
    p_room = paper_mod.plot_group_comparison(
        by_room_labeled,
        "BPM error by room (top 5 methods)",
        "ble_hkh_paper_baselines_by_room.png",
    )
    print(f"paper: {p_all.name} (+pdf), {p_room.name} (+pdf)")

    b3 = _load_json(REPORTS_DIR / "ble_hkh_b3_validation_summary.json")
    # Restore NaN for plotting helpers that check np.isfinite
    for row in b3.get("leaderboard", []):
        if row.get("rmse_mean") is None:
            row["rmse_mean"] = float("nan")
    for _k, row in b3.get("methods", {}).items():
        if row.get("rmse_mean") is None:
            row["rmse_mean"] = float("nan")

    p_abl = b3_mod.plot_ablation_leaderboard(b3)
    p_sc = b3_mod.plot_bpm_vs_rmse(b3)
    print(f"b3: {p_abl.name} (+pdf), {p_sc.name} (+pdf)")

    cross = np.load(REPORTS_DIR / "b2_coherent_mrc_all_cross_domain.npy", allow_pickle=True)
    cross_domain = list(cross)
    paths = plot_b2_achievement_figures(
        cross_domain,
        figures_dir=FIGURES_DIR,
        prefix="b2_coherent_mrc",
        show=False,
        save=True,
    )
    print(f"b2: {paths['waterfall_decomposition'].name} (+pdf)")

    latex_figs = Path(r"d:\Work\atomic\paper_sj_ble_sensing\figs")
    stems = [
        "ble_hkh_paper_baselines_leaderboard_all",
        "ble_hkh_paper_baselines_by_room",
        "ble_hkh_b3_ablation_leaderboard",
        "ble_hkh_b3_bpm_vs_rmse",
        "b2_coherent_mrc_waterfall_decomposition",
        "b2_coherent_mrc_two_level_contribution",
    ]
    for stem in stems:
        src = FIGURES_DIR / f"{stem}.pdf"
        if src.exists():
            dst = latex_figs / f"{stem}.pdf"
            dst.write_bytes(src.read_bytes())
            print(f"copied -> {dst}")
        else:
            print(f"MISSING {src}")


if __name__ == "__main__":
    main()
