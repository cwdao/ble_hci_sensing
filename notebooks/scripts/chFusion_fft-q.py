"""CS 金属板脚本段：多信道 FFT 融合 BPM 对比实验。

基于 ``glb_cs_segment_breath_analysis`` 的分段滤波 pipeline，在 bandpass 之后
按 ``docs/chfusion_fft-q.md`` 实现 FFT+q 及多种 baseline / 消融。

对比方法（4 种）：
  1. Single      — 每窗选呼吸能量比最大的单信道，FFT 峰值
  2. Uniform     — 多信道归一化频谱等权平均
  3. FFT+q       — q_c = (q_valid·q_peak·q_phi)^(1/3) 加权融合
  4. FFT+q_peak  — 消融：仅 q_peak 作为融合权重

运行：VS Code 逐 cell 执行，或 ``python notebooks/scripts/chFusion_fft-q.py``
"""

# %% [markdown]
# # chFusion FFT+q — 金属板 CS 分段 BPM 对比
#
# | 步骤 | 内容 |
# |------|------|
# | 0 | 打印 q 分数公式说明 |
# | 1 | 加载 CS 帧 → 多信道分段滤波 |
# | 2 | 四种方法 BPM 估计 + q 子项统计 |
# | 3 | 数值对比表 + 保存 `.npy` |
# | 4 | 窗级有符号误差小提琴图（GT = y0） |
#
# 方法细节见 ``docs/chfusion_fft-q.md``。

# %% [markdown]
# ## 0. 环境初始化
#
# 向上查找含 ``src/`` 的项目根，加入 ``sys.path``，创建 ``outputs/`` 子目录。

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
    raise FileNotFoundError("未找到项目根目录（缺少 src/ 目录）")

_src = project_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from ble_analysis.bootstrap import init_notebook

_env = init_notebook(project_root)
project_root = _env["project_root"]
FIGURES_DIR = _env["FIGURES_DIR"]
PROCESSED_DIR = _env["PROCESSED_DIR"]
REPORTS_DIR = _env["REPORTS_DIR"]

# %% [markdown]
# ## 0b. 参数与 q 分数说明
#
# **q 三子项**（doc §1.3）：
# - ``q_valid``：窗内有效相位采样比例（阈值 ``min_valid_frac=0.7``）
# - ``q_peak``：呼吸频带谱峰 SNR ρ=max/median，log 映射到 [0,1]
# - ``q_phi``：unwrap 相位大跳比例惩罚
#
# **compact q_c**（默认 FFT+q）：三者几何平均，三者权重相等。
# **peak-only 消融**（FFT+q_peak）：仅 ``q_peak`` 参与加权，用于验证谱峰质量是否主导。

# %%
from ble_analysis.chfusion import (
    ChFusionConfig,
    collect_window_signed_errors,
    estimate_segment_bpm_methods,
    plot_bpm_error_violins,
    print_bpm_comparison_table,
    print_q_component_summary,
    print_q_score_documentation,
    run_multichannel_segment_filtering,
    summarize_bpm_comparison,
)
from ble_analysis.data import load_ble_frames
from ble_analysis.segments import BreathMetricParams, FilterParams

# === 数据路径（可改）===
filepath = project_root / "sampleData" / "CS_frames_all_20260113_091339.jsonl"
signal_variable = "remote_amplitudes"   # 融合 FFT 使用的 bandpass 信号
phase_variable = "remote_phases"      # 仅用于 q_valid / q_phi 计算

# === 金属板脚本段 GT（与 glb_cs_segment_breath_analysis 一致）===
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

filter_params = FilterParams()       # median=3, HP 0.05 Hz, BP 0.1–0.35 Hz
metric_params = BreathMetricParams() # 20 s 窗, 1 s 步
chfusion_config = ChFusionConfig(
    breath_freq_low=metric_params.breath_freq_low,
    breath_freq_high=metric_params.breath_freq_high,
    window_length_sec=metric_params.window_length_sec,
    step_length_sec=metric_params.step_length_sec,
    enable_consensus=False,
)

print_q_score_documentation(chfusion_config)

# %% [markdown]
# ## 1. 加载数据 & 多信道分段滤波
#
# 对每个脚本段、每个可用信道独立执行：
# ``extract_segment_data`` → ``process_segments``（median / highpass / bandpass）。

# %%
data, frames = load_ble_frames(filepath, verbose=False)

multichannel_segments, sampling_rate = run_multichannel_segment_filtering(
    frames,
    segment_config,
    variable=signal_variable,
    phase_variable=phase_variable,
    filter_params=filter_params,
    verbose=True,
)

# %% [markdown]
# ## 2. 四种方法 BPM 估计
#
# | 键名 | 方法 |
# |------|------|
# | ``fft_single_max_energy`` | 最大能量比单信道 FFT |
# | ``fft_uniform_fusion`` | 频谱等权平均 |
# | ``fft_q_fusion`` | compact q 加权（几何平均三子项） |
# | ``fft_q_peak_fusion`` | **消融**：权重 = q_peak only |

# %%
method_results = estimate_segment_bpm_methods(
    multichannel_segments,
    variable=signal_variable,
    phase_variable=phase_variable,
    config=chfusion_config,
    metric_params=metric_params,
)

# 各段 q 子项均值（帮助判断 q_peak 是否主导 compact q_c）
print_q_component_summary(method_results)

# %% [markdown]
# ## 3. BPM 误差对比表 & 保存结果
#
# 输出相对误差（%）及窗级 ±std；apnea 段自动跳过。

# %%
comparison_rows, comparison_overall = summarize_bpm_comparison(method_results)
print_bpm_comparison_table(comparison_rows, comparison_overall)
signed_error_records = collect_window_signed_errors(method_results)

report_path = REPORTS_DIR / "chfusion_fft_q_bpm_comparison.npy"
np.save(
    report_path,
    {
        "method_results": method_results,
        "comparison_rows": comparison_rows,
        "comparison_overall": comparison_overall,
        "signed_error_records": signed_error_records,
        "q_formula": {
            "compact": "q_c = (q_valid * q_peak * q_phi)^(1/3)",
            "peak_only": "q_c = q_peak",
        },
        "config": {
            "filepath": str(filepath),
            "signal_variable": signal_variable,
            "phase_variable": phase_variable,
            "sampling_rate": sampling_rate,
            "chfusion_config": chfusion_config,
        },
    },
    allow_pickle=True,
)
print(f"✓ 结果已保存: {report_path}")

# %% [markdown]
# ## 4. 窗级 BPM 有符号误差小提琴图
#
# - 纵轴：``估计 BPM − GT``（可正可负）
# - **y = 0** 虚线 = Ground Truth
# - 每段 4 根小提琴：Single / Uniform / FFT+q / FFT+q_peak
# - 仅 1 个滑窗的短段（如 2b、4b）用散点代替

# %%
plot_bpm_error_violins(
    method_results,
    figures_dir=FIGURES_DIR,
    show=True,
    save=True,
)
