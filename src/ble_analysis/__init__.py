"""BLE CS data analysis utilities."""

from ble_analysis.channels import (
    extract_channel_series,
    find_channel_key,
    get_available_channels,
    resolve_channel,
)
from ble_analysis.data import load_ble_frames
from ble_analysis.diagnostics import (
    analyze_time_intervals,
    diagnose_channel_presence,
    print_file_info,
    print_time_interval_summary,
)
from ble_analysis.filters import apply_filter_pipeline
from ble_analysis.paths import ensure_output_dirs, find_project_root
from ble_analysis.plotting import (
    plot_channel_amplitude_phase,
    plot_time_intervals,
    setup_plot_style,
)
from ble_analysis.resampling import resample_to_uniform_grid

__all__ = [
    "load_ble_frames",
    "get_available_channels",
    "find_channel_key",
    "resolve_channel",
    "extract_channel_series",
    "print_file_info",
    "diagnose_channel_presence",
    "analyze_time_intervals",
    "print_time_interval_summary",
    "resample_to_uniform_grid",
    "apply_filter_pipeline",
    "setup_plot_style",
    "plot_channel_amplitude_phase",
    "plot_time_intervals",
    "find_project_root",
    "ensure_output_dirs",
]
