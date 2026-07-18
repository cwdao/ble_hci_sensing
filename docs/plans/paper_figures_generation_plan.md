# Plan: Paper Figures Generation — Mechanism Validation (CS Metal-Plate)

> **目标**：从 CS 金属板已滤波数据中提取单窗/跨窗诊断数据，绘制论文 Figure 2/3/5/S1  
> **模式**：Research Mode → 交付 Cursor Composer 执行  
> **日期**：2026-07-18  
> **状态**：待执行

---

## 1. 背景

论文 §2–§3 需要 4 类机制验证图，用于支撑理论论述。这些图需要从 CS 金属板已滤波的窗口级数据中提取，而非从 aggregate 结果中生成。现有实验产出中**没有**这个粒度的图——当前所有图都是跨 segment/scenario 的 aggregate 结果。

**不需要从零跑滤波**——可以使用已有的 `multichannel_by_var` 缓存数据，或调用 `run_multichannel_segment_filtering(cache_dir=...)` 加载已缓存的滤波结果。

---

## 2. 待生成的图

### Figure 2: Inter-Tone Phase Relationship（§2.3 支撑图）

**目标**：展示 (a) 同模态多个 tone 的原始波形、(b) PCA sign 对齐后、(c) Hilbert 对齐后的对比，证明信道间不仅存在 ±1 相位关系，还有需要连续相位才能处理的额外结构。(d) 72×72 相干性热力图。

**建议的 4 个 panel**：

```
Figure 2: Inter-tone phase relationship

(a) 4 representative tones, raw bandpass waveforms, overlaid
    (20 s window, same modal, e.g. remote_amplitudes)
    Pick tones that clearly show both in-phase and anti-phase pairs

(b) Same 4 tones after PCA sign correction (±1 only)
    → approximately aligned but residual misalignment visible

(c) Same 4 tones after Hilbert continuous phase alignment
    → near-perfect overlap

(d) 72×72 tone-pair coherence matrix γ_ij
    Side-by-side: cs_095806 (good) | cs_091339 (hard)
```

**数据来源**：
- 场景：`cs_095806`（good）和 `cs_091339`（hard）
- 模态：`remote_amplitudes`（任选，local/phases 亦可）
- 窗口选择：选 1 个 η 中位数附近、γ 多样性好的窗口（即包含明显同相和反相 tone pair 的窗口）

**实现要点**：

```
输入：
  - 加载已缓存的 multichannel_by_var（或调用 run_multichannel_segment_filtering 加载）
  - cs_095806 和 cs_091339

步骤：
1. 选定一个 segment（如最长的非 apnea segment）
2. 选定一个代表性窗口（如第 10 个 window）
3. 对 remote_amplitudes，提取所有 72 个 tone 在该窗口的 bandpass_filtered 信号
   数据路径: ch_map[ch]["remote_amplitudes"]["bandpass_filtered"][st:end]

4. 计算 per-tone η 和 ρ（调 _energy_ratio 和 _peak_prominence）
5. 选 4 个代表 tone：
   - 1 个最高 η·ρ 的作为 reference
   - 1 个与 ref 近似同相的（γ > 0.7, Δφ ≈ 0）
   - 1 个与 ref 近似反相的（γ > 0.7, Δφ ≈ π）
   - 1 个与 ref 有非二值相位差的（如 Δφ ≈ π/3 或 π/4）

6. 画三个子图 (a)-(c)：
   - (a) raw: overlay 4 条 bandpass_filtered 波形
   - (b) PCA sign: 对每个非 ref tone，计算 corrcoef sign → flip if negative → overlay
   - (c) Hilbert: 调 estimate_phase_hilbert() 得到 phases[i] → z_i * exp(-j*phases[i]) → overlay

7. 画 (d) 热力图：
   - 对每个场景，计算 72×72 的 pairwise coherence γ_ij
     公式: γ_ij = |Σ z_i * conj(z_j)| / (||z_i|| · ||z_j||)
   - Heatmap (imshow, cmap="viridis" 或 "RdYlBu")
   - 两个场景并排

8. 可选 inset（~10% 版面）：Hilbert 复平面旋转 vs 时移对齐对比示意

输出：
  outputs/figures/paper_fig2_inter_tone_phase.png
  outputs/figures/paper_fig2_diagnostics.npy  （γ 矩阵、相位值、选中的 tone index）
```

**注意事项**：
- 所有 tone 波形需要标准化（zero-mean, unit-std）后再 overlay，否则幅值差异会掩盖相位信息
- 先用 `estimate_phase_hilbert()` 得到每个 tone 的 Δφ_i 和 γ_i，再用这些值选择代表 tone 和排序
- 热力图的 tone 顺序按 η·ρ 降序排列（好 tone 在左上角）

---

### Figure 3: Inter-Modal Phase Alignment（§2.4 支撑图）

**目标**：展示 (a) 三模态波形在 Level-2 对齐前的相位差异、(b) 对齐后的对齐效果、(c) 跨窗口模态间相位差的浮动、(d) 不同房间的相位差基线不同。

**建议的 4 个 panel + 1 个可选**：

```
Figure 3: Inter-modal phase relationship

(a) Three modal waveforms after Level-1 fusion, BEFORE Level-2 alignment
    (remote / local / phase), same window, overlaid
    → visibly different phases

(b) Same three modal waveforms AFTER Level-2 Hilbert alignment + η·γ fusion
    → aligned, and fused waveform (bold black) tracks consensus

(c) Cross-window Δφ time series (one segment, all windows)
    Δφ(remote, local)[w], Δφ(remote, phase)[w], Δφ(local, phase)[w]
    → phases are NOT fixed across windows → must be per-window estimated

(d) Same Δφ plot for a DIFFERENT room (cs_102621)
    → different baseline Δφ, confirming environment-dependence
```

**数据来源**：
- 场景：`cs_095806` 和 `cs_102621`
- 选 1 个完整 segment（所有窗口）

**实现要点**：

```
输入：
  - 已缓存的 multichannel_by_var（三模态都加载）
  - cs_095806 和 cs_102621

步骤：
1. 选定 segment
2. 取一个代表性窗口（如中间窗口），执行 Level-1 Hilbert MRC：
   对每个模态 m ∈ {remote_amplitudes, local_amplitudes, phases}：
     - _collect_modal_window_matrix(ch_list, ch_map, variable, st, end, fs, cfg)
     - coherent_mrc_fuse_tones(X, eta, rho, phase_method="hilbert", weight_mode="coherence_gated")
       → y_m[n] (modal waveform)
     - _energy_ratio(y_m, fs, cfg) → η_m

3. 画 (a)：overlay 三条 y_m[n]（对齐前），标注每条对应哪个模态

4. 调用 coherent_mrc_fuse_modals() 做 Level-2 对齐：
     - 传入 {y_remote, y_local, y_phase} 和 {η_remote, η_local, η_phase}
     - weight_mode="eta_coherence", use_phase_align=True
     - 返回 y_final[n] 和诊断信息（phases dict, coherences dict）

5. 画 (b)：overlay 三条对齐后的波形 + 粗黑线表示 y_final

6. 对该 segment 的所有窗口，重复步骤 2-4，记录每窗的模态间相位：
     Δφ_rem_loc[w] = phases["remote"] - phases["local"] (或直接取 cross-correlation 角度)
     存储 phases dict (keyed by modal)

7. 画 (c)：x 轴 = window index, y 轴 = Δφ (rad), 三条线（remote-local, remote-phase, local-phase）

8. 对 cs_102621 的某个 segment，重复步骤 6-7，画 (d)

输出：
  outputs/figures/paper_fig3_inter_modal_phase.png
  outputs/figures/paper_fig3_diagnostics.npy  （跨窗相位序列）
```

**注意事项**：
- Level-1 tone fusion 的计算量较大（每窗 3 模态 × 72 tone Hilbert），一个完整 segment 可能有 ~50-100 个窗口，总耗时可能需要几十秒到几分钟。可以先限制 max_segments 和 max_windows 加速排查
- 存储跨窗相位数据时同时保存 γ 值，用于后续筛选 quality windows
- 对齐前后的 y 轴范围需要保持一致（方便视觉对比）

---

### Figure 5: η·ρ Quality Voting Mechanism（§3.3 支撑图）

**目标**：展示为什么 η·ρ 加权比等权好——(a) η vs ρ 散点图、(b) Voting vs Uniform BPM 直方图、(c) 融合频谱对比。

**建议的 3 个 panel**：

```
Figure 5: η·ρ quality voting vs uniform averaging

(a) Per-tone η vs ρ scatter (72 points, one window)
    x = η (energy ratio), y = ρ (kurtosis)
    Color = |BPM_i - BPM_voted| (error vs voting consensus)
    Marker size = w_i (η·ρ weight)
    → high-quality tones cluster in top-right; low-quality tones have large BPM error

(b) BPM histogram comparison
    Light bars: Uniform (all 72 tones equally weighted)
    Dark bars: η·ρ Voting (weighted by quality)
    Vertical lines: BPM_voted (dark) and BPM_uniform (light)
    → Voting produces sharper, higher-confidence peak

(c) Fused spectrum comparison
    S_uniform(f) vs S_voting(f), overlaid
    → Voting spectrum has cleaner peak, lower noise floor
```

**数据来源**：
- 场景：`cs_095806`
- 模态：`remote_amplitudes`
- 选 1 个代表性窗口

**实现要点**：

```
输入：
  - 已缓存的 multichannel_by_var["remote_amplitudes"]
  - cs_095806

步骤：
1. 选定 segment 和窗口 index
2. 调用 _collect_channel_window_data() 获取：
     eta (72,), rho (72,), bpm_per_tone (72,), spectra (72 × F)
3. 计算 η·ρ 权重: w_i = η_i * max(rho_i, 0)
4. 计算 Voting BPM: vote_bpm_weighted_histogram(bpm_per_tone, w_i, vcfg)
5. 计算 Uniform BPM: argmax(mean(spectra, axis=0))

6. 画 (a): scatter plot
     x = η, y = ρ
     color = |bpm_per_tone - bpm_voted| (or NaN if bpm = NaN)
     size = w_i / sum(w_i) * 100
     标注 top 5 tones (highest η·ρ)

7. 画 (b): 双直方图 overlay
     Uniform 直方图: np.histogram(bpm_per_tone[mask], bins=range(6,22))
     Voting 直方图: np.histogram(bpm_per_tone[mask], bins=..., weights=w_i[mask])
     vertical lines at BPM_voted and BPM_uniform

8. 画 (c): 频谱 overlay
     S_uniform = np.mean(spectra[mask], axis=0)
     S_voting = _weighted_spectrum_average(spectra, w_i, ...)
     plot vs frequency (Hz), different colors

输出：
  outputs/figures/paper_fig5_eta_rho_voting.png
  outputs/figures/paper_fig5_diagnostics.npy  （per-tone 数据）
```

---

### Figure S1 (Supplementary): Coherence Stability Across Windows（§2.3 补充）

**目标**：展示同一对 tone 的 γ 在不同场景的稳定程度——good scenario（cs_095806）下 γ 稳定高，hard scenario（cs_091339）下 γ 波动大。

**建议的 1 个 panel**：

```
Figure S1: Tone-pair coherence stability

Two tone pairs tracked across all windows of one segment:
  cs_095806 (blue): high-γ pair → γ ≈ 0.7–0.9, stable
  cs_091339 (red): same pair indices → γ fluctuates 0.2–0.6, unstable
```

**实现要点**：

```
步骤：
1. 对 cs_095806 和 cs_091339，各选 1 个完整 segment
2. 选 2 个 tone index（如 tone 12 和 tone 38，在 cs_095806 上 γ 高的一对）
3. 对每个窗口，计算这两 tone 之间的 γ：
     z_i = hilbert(bp_i[st:end]), z_j = hilbert(bp_j[st:end])
     γ = |Σ z_i * conj(z_j)| / (||z_i|| · ||z_j||)
4. 画两个场景的 γ 时间序列（双线，不同颜色）
5. 标注均值 ± std

输出：
  outputs/figures/paper_figS1_coherence_stability.png
```

---

## 3. 脚本与输出路径

| 类型 | 路径 |
|------|------|
| 实验脚本 | `notebooks/scripts/chFusion_paper_figures_mechanism.py` |
| Figure 2 | `outputs/figures/paper_fig2_inter_tone_phase.png` |
| Figure 3 | `outputs/figures/paper_fig3_inter_modal_phase.png` |
| Figure 5 | `outputs/figures/paper_fig5_eta_rho_voting.png` |
| Figure S1 | `outputs/figures/paper_figS1_coherence_stability.png` |
| 诊断数据 | `outputs/reports/paper_figures_diagnostics.npy`（包含所有中间数据） |

**诊断数据应包含**（保存为 dict）：

```python
diagnostics = {
    "fig2": {
        "scenario_good": "cs_095806",
        "scenario_hard": "cs_091339",
        "seg_name": "...",
        "window_idx": 10,
        "variable": "remote_amplitudes",
        "selected_tones": [12, 38, 55, 71],  # tone indices
        "tone_waveforms": np.ndarray,  # (4, W) raw waveforms
        "tone_waveforms_pca_sign": np.ndarray,  # (4, W) after PCA sign
        "tone_waveforms_hilbert": np.ndarray,  # (4, W) after Hilbert
        "phases": np.ndarray,  # (72,) estimated Δφ per tone
        "coherences": np.ndarray,  # (72,) γ per tone
        "gamma_matrix_good": np.ndarray,  # (72, 72)
        "gamma_matrix_hard": np.ndarray,  # (72, 72)
    },
    "fig3": {
        "scenario_1": "cs_095806",
        "scenario_2": "cs_102621",
        "seg_name": "...",
        "modal_waveforms_before": dict,  # {"remote": (W,), "local": (W,), "phase": (W,)}
        "modal_waveforms_after": dict,  # same keys, aligned
        "y_fused": np.ndarray,  # (W,)
        "modal_phases": dict,  # {"remote": float, "local": float, "phase": float}
        "cross_window_phases_scenario1": np.ndarray,  # (n_windows, 3)
        "cross_window_phases_scenario2": np.ndarray,  # (n_windows, 3)
    },
    "fig5": {
        "eta": np.ndarray,  # (72,)
        "rho": np.ndarray,  # (72,)
        "bpm_per_tone": np.ndarray,  # (72,)
        "weights": np.ndarray,  # (72,)
        "bpm_voted": float,
        "bpm_uniform": float,
        "spectrum_voting": np.ndarray,  # (F,)
        "spectrum_uniform": np.ndarray,  # (F,)
        "band_freqs": np.ndarray,  # (F,)
    },
    "figS1": {
        "tone_pair": (12, 38),
        "gamma_cs095806": np.ndarray,  # (n_windows,)
        "gamma_cs091339": np.ndarray,  # (n_windows,)
    },
}
```

---

## 4. 绘图风格（建议）

为了实现跨图一致，建议在脚本开头统一设定：

```python
import matplotlib.pyplot as plt

plt.rcParams.update({
    "figure.dpi": 150,
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "legend.fontsize": 8,
    "lines.linewidth": 1.5,
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})
```

**注意**：论文最终定稿时仍会统一重绘——本脚本的目标是**生成正确的数据视图**（正确的数值、正确的相对关系），而非最终的美术风格。

---

## 5. 预期执行时间

- 加载缓存数据：~5 秒
- Figure 2：~10 秒（2 场景 × 72 tone Hilbert + 1 个 72×72 矩阵）
- Figure 3：~2–5 分钟（2 场景 × ~50 窗口 × 3 模态 × 72 tone Hilbert）
- Figure 5：~5 秒（1 窗口 × 72 tone 统计）
- Figure S1：~30 秒（2 场景 × ~50 窗口 × 1 tone pair 计算）

总计：约 3–6 分钟。如果跨窗口循环太慢，可以先 `max_windows=30` 调试，确认正确后再跑全量。

---

## 6. 模块依赖

脚本需要 `import` 以下项目模块：

| 模块 | 用途 |
|------|------|
| `ble_analysis.chfusion` | `ChFusionConfig`, `_energy_ratio`, `_peak_prominence`, `_next_pow2` |
| `ble_analysis.segments` | `FilterParams`, `BreathMetricParams`, `_sliding_window_indices` |
| `ble_analysis.systematic_fusion` | `_collect_channel_window_data`, `_weighted_spectrum_average` |
| `ble_analysis.coherent_mrc` | `estimate_phase_hilbert`, `coherent_mrc_fuse_tones`, `coherent_mrc_fuse_modals` |
| `ble_analysis.wifi_mrc` | `_collect_modal_window_matrix` |
| `ble_analysis.voting_fusion` | `VotingConfig`, `_vote_weights`, `vote_bpm_weighted_histogram` |

---

## 7. 风险与保留问题

| 风险 | 影响 | 缓解 |
|------|------|------|
| 跨窗口循环慢（Figure 3） | 执行时间过长 | 限制 max_segments=1, max_windows=50；并行化三个模态的 Level-1 计算 |
| 选不到好的代表窗口 | Figure 2 效果不清晰 | 先批量计算所有窗口的 per-tone γ 分布，选 γ 方差最大的窗口（说明同时存在同相和反相 tone） |
| 缓存数据已过时 | 加载失败 | 提供 fallback：用 `run_multichannel_segment_filtering` 重新滤波，接受额外耗时 |
| cs_091339 中好的 tone pair 少 | Figure S1 对比不明显 | 放宽标准——选 cs_095806 中 γ > 0.7 的某对 tone，同 index 在 cs_091339 中看退化 |

---

## 给 Cursor Composer 的交接说明

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并执行本 plan：

`docs/plans/paper_figures_generation_plan.md`

### 执行步骤

1. 加载 cs_091339、cs_095806、cs_102621 的已缓存滤波数据（`multichannel_by_var`）
2. 按 §2 的「实现要点」逐图生成诊断数据并保存 `.npy`
3. 按 §2 的 panel 描述绘制各图并保存 `.png`
4. 如果某个场景的缓存缺失，可用 `run_multichannel_segment_filtering(cache_dir=...)` 重新生成

### 产出清单

- `notebooks/scripts/chFusion_paper_figures_mechanism.py`
- `outputs/figures/paper_fig2_inter_tone_phase.png`
- `outputs/figures/paper_fig3_inter_modal_phase.png`
- `outputs/figures/paper_fig5_eta_rho_voting.png`
- `outputs/figures/paper_figS1_coherence_stability.png`
- `outputs/reports/paper_figures_diagnostics.npy`
