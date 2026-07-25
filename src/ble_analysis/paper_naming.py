"""Paper-facing method names and colors for Chapter 6 figures.

Internal experiment keys map to short paper labels (see
``docs/plans/paper_figure_redraw_plan.md`` §2).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# internal_key → (paper_label, paper_group, color)
PAPER_LABEL_MAP: Dict[str, Tuple[str, str, str]] = {
    # BreatheCS family — red
    "b3_b1_equal": ("BreatheCS", "BreatheCS", "#E63946"),
    "b1_vote_modal_equal": ("BreatheCS-Spec", "BreatheCS", "#E63946"),
    "b2_d_two_level": ("BreatheCS-Wave", "BreatheCS", "#E63946"),
    # Pos-Free — green
    "z1_no_vmd": ("Pos-Free (PCA)", "Pos-Free", "#81B29A"),
    "z1": ("Pos-Free (PCA-VMD)", "Pos-Free", "#81B29A"),
    "z1_fft": ("Pos-Free (PCA-VMD+FFT)", "Pos-Free", "#81B29A"),
    # WiFi-Sleep — dark blue
    "mrc_pca_eta_equal_pca": ("WiFi-Sleep (MRC-PCA)", "WiFi-Sleep", "#3D405B"),
    "mrc_pca_eta_sqrt": ("WiFi-Sleep (√η)", "WiFi-Sleep", "#3D405B"),
    "mrc_pca_eta_equal": ("WiFi-Sleep (MRC-PCA)", "WiFi-Sleep", "#3D405B"),
    # ClessBreath — orange
    "fan_eta_linear": ("ClessBreath (η-linear)", "ClessBreath", "#E07A5F"),
    "fan_eta_equal_wf": ("ClessBreath (η-equal)", "ClessBreath", "#E07A5F"),
    "fan_hilbert_equal": ("ClessBreath (Hilbert)", "ClessBreath", "#E07A5F"),
    # Ablation / simple baselines — gray
    "a1_single_best_eta": ("Single (best-η)", "Ablation", "#999999"),
    "a3_remote_only": ("Remote-only", "Ablation", "#999999"),
    "a4_equal_spectral": ("Equal-weight (spectral)", "Ablation", "#999999"),
    "a5_equal_voting": ("Equal-weight (voting)", "Ablation", "#999999"),
    "b2_a0_pca_sign": ("PCA sign only", "Ablation", "#999999"),
    "b0_single_remote": ("Single (Remote)", "Ablation", "#999999"),
    "r12_d_single_remote": ("Single (Remote)", "Ablation", "#999999"),
    # CS metal-plate waterfall steps (Fig 8b)
    "b2_a1_corr_sign": ("Corr sign only", "Ablation", "#999999"),
    "b2_b_hilbert": ("Hilbert η·ρ (L1)", "Ablation", "#999999"),
    "b2_b_gamma": ("Hilbert + γ-gate (L1)", "Ablation", "#999999"),
}

# Fig 6a: methods to show (order = ascending BPM intent; actual sort uses data)
FIG6A_METHOD_KEYS = [
    "b3_b1_equal",
    "z1_no_vmd",
    "mrc_pca_eta_equal_pca",
    "b2_d_two_level",
    "mrc_pca_eta_sqrt",
    "b2_a0_pca_sign",
    "fan_eta_linear",
    "fan_eta_equal_wf",
    # "r12_d_single_remote" / Single (Remote): HKH abs-BPM not in paper_baselines JSON
]

# Fig 6b / optional: prefer these when selecting top-N
FIG6B_PREFERRED_KEYS = [
    "b3_b1_equal",
    "z1_no_vmd",
    "mrc_pca_eta_equal_pca",
    "b2_d_two_level",
    "fan_eta_linear",
]

# Fig 7 scatter (exclude pure spectral methods without RMSE)
FIG7_METHOD_KEYS = [
    "b3_b1_equal",
    "b2_d_two_level",
    "z1_no_vmd",
    "mrc_pca_eta_equal_pca",
    "mrc_pca_eta_sqrt",
    "b2_a0_pca_sign",
    "fan_eta_linear",
    "fan_eta_equal_wf",
    "fan_hilbert_equal",
    "z1",
    "z1_fft",
]

# RMSE table rows (BreatheCS as unified pipeline — no separate Wave row)
RMSE_TABLE_KEYS = [
    "b3_b1_equal",
    "fan_eta_linear",
    "fan_eta_equal_wf",
    "mrc_pca_eta_equal_pca",
    "z1_no_vmd",
    "b2_a0_pca_sign",
]

# Ablation groupings for Fig 8a
ABLATION_GROUPS = {
    "Channel fusion": ["a1_single_best_eta", "a5_equal_voting", "b3_b1_equal"],
    "Modal fusion": ["a3_remote_only", "a4_equal_spectral", "b3_b1_equal"],
    "Phase method": ["b2_a0_pca_sign", "a4_equal_spectral", "b2_d_two_level"],
}

# Waterfall steps on CS metal-plate (Fig 8b)
WATERFALL_STEPS = [
    ("b2_a0_pca_sign", "PCA sign only"),
    ("b2_a1_corr_sign", "Corr sign only"),
    ("b2_b_hilbert", "Hilbert η·ρ (L1)"),
    ("b2_b_gamma", "Hilbert + γ-gate (L1)"),
    ("b2_d_two_level", "BreatheCS-Wave"),
]

WATERFALL_B1_REF_KEY = "b1_vote_modal_equal"

GROUP_COLORS = {
    "BreatheCS": "#E63946",
    "Pos-Free": "#81B29A",
    "WiFi-Sleep": "#3D405B",
    "ClessBreath": "#E07A5F",
    "Ablation": "#999999",
}


def paper_label(method_key: str, fallback: Optional[str] = None) -> str:
    if method_key in PAPER_LABEL_MAP:
        return PAPER_LABEL_MAP[method_key][0]
    return fallback or method_key


def paper_group(method_key: str) -> str:
    if method_key in PAPER_LABEL_MAP:
        return PAPER_LABEL_MAP[method_key][1]
    return "Ablation"


def paper_color(method_key: str) -> str:
    if method_key in PAPER_LABEL_MAP:
        return PAPER_LABEL_MAP[method_key][2]
    return "#777777"
