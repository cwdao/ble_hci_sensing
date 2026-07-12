# B3 统一管线：信道级 Voting BPM + 两级 Hilbert-MRC 波形 — 实现计划

> **来源**：B1（Vote→Equal, BPM-only）与 B2-D（Two-level Hilbert-MRC, waveform）的跨场景验证结论  
> **目标报告**：`docs/reports/b3_unified_pipeline_voting_bpm_report.md`（模板：`docs/templates/algorithm_validation_report.md`）  
> **建议 plan 路径**：`docs/plans/b3_unified_pipeline_voting_bpm_plan.md`  
> **日期**：2026-07-12  
> **验证状态**：待实现

---

## 1. 动机与背景

### 1.1 问题

12 场景 HKH 真人验证揭示了一个深层 trade-off：

| 方法 | 域 | BPM 跨场景 mean | BPM std | RMSE | 失效模式 |
|------|-----|----------------:|--------:|------|---------|
| B1 Vote→Equal | 频域（谱投票） | **0.41** | **0.14** | — | 无波形输出 |
| B2-D Two-level | 时域（Hilbert 相位对齐） | 0.68 | **0.57** | **0.950** | 3/12 场景 BPM 崩溃（A-D: 2.31, C-A: 1.40, B-C: 0.73） |

**B2-D BPM 崩溃的根本机制**（Review 已确认）：B2-D 以 η 最高 tone 为参考，所有 tone 向其做 Hilbert 相位对齐。若参考 tone 本身因多径/遮挡质量差，整个融合链级联崩溃。频域直方图投票天然压制 outlier，因此在同样场景上 B1 仍稳（A-D: 0.60, C-A: 0.27）。

### 1.2 关键发现：两者共享数据采集前端

B2-D 在 `_collect_modal_window_matrix()` 中已经计算了 Voting 所需的全部中间量——per-tone η、ρ、功率谱——只是当前代码仅保留标量 η，丢弃了完整谱。**在 Hilbert 相位对齐之前插入一次 Voting，几乎零额外成本。**

### 1.3 本 plan 定位

**B3**：统一管线，在 B2-D 的信道数据采集阶段抽取 Voting BPM 作为主 BPM 输出，同时保持两级 Hilbert-MRC 管线产出高质量波形。**不是一个新方法，而是对 B1 和 B2-D 的架构级统一**——B1 的 Voting 逻辑和 B2-D 的波形管线共享同一前端，不再分为两条独立路径。

与既有工作的关系：

| 方法 | 信道融合 | 模态融合 | BPM 来源 | 波形 |
|------|---------|---------|---------|------|
| B1 Vote→Equal | η·ρ Voting | 等权谱平均 | 融合谱寻峰 | ❌ |
| B2-D Two-level | η·ρ 质量加权 + coherence gate | 两级 Hilbert 相位对齐 | 最终波形 PSD | ✅ |
| **B3（本 plan）** | **η·ρ Voting**（从 B1 继承） | **两级 Hilbert-MRC**（从 B2-D 继承） | **信道级 Voting 共识**（中间结果） | ✅（最终管线输出） |

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 远端幅值，含呼吸调制信息 |
| `local_amplitudes` | ✅ | 本地幅值，物理上与 remote 对等 |
| `phases`（总相位） | ✅ | 两端 PCT 向量相乘后的总相位，LO 漂移已抵消 |
| `amplitudes`（总幅值） | ❌ | remote × local 的合成幅值，无独立物理意义 |

### 2.2 符号约定

沿用项目一致的：

| 符号 | 含义 |
|------|------|
| `η` | 呼吸频段能量比（`_energy_ratio()` from highpass signal） |
| `ρ` | 谱峰峰度 / prominence（`_peak_prominence()` from bandpass signal） |
| `quality = η × max(ρ, 0)` | 单 tone 信号质量 |
| `coherence` | Hilbert 解析信号互相关归一化幅值 `|cross| / sqrt(|z_i|² × |z_ref|²)` |
| `B_r = [0.1, 0.35] Hz` | 呼吸频段 |

---

## 3. 算法步骤

### 3.1 完整流程图

```text
Raw BLE CS Frames (72 tone × 3 variables)
  │
  └─► Filter Chain (per tone, per variable):
        median(w=3) → highpass(0.05 Hz, order=1) → bandpass(0.1–0.35 Hz, order=2)
        [模块: segments.py → FilterParams + process_segments()]
        [维度: 72 tone × 3 var, 每 tone 长度 T]
      │
      ▼
  Sliding Window: 20 s / 1 s step
  [模块: segments.py → _sliding_window_indices()]
      │
      ▼
  ╔══════════════════════════════════════════════════════════╗
  ║  _collect_modal_window_matrix()   ← 共享前端（已有）    ║
  ║  [模块: wifi_mrc.py]                                    ║
  ║                                                        ║
  ║  对每个 modal 变量 (remote / local / phase):            ║
  ║    X [72, T_win] ← bandpass 时域切片                    ║
  ║    η[72]  ← _energy_ratio(highpass)                     ║
  ║    ρ[72]  ← _peak_prominence(bandpass)                  ║
  ║    quality[72] = η × max(ρ, 0)                          ║
  ║    spectra[72, nfft] ← per-tone FFT 功率谱  【NEW】     ║
  ╚══════════════════════════════════════════════════════════╝
      │
      ├─► 【NEW】信道级 Voting BPM ─────────────────────────┐
      │                                                      │
      │   _vote_bpm_per_modal(spectra, η, ρ, freq_axis):     │
      │     weights[72] = η × max(ρ, 0) / sum(η × max(ρ,0)) │
      │     bpm_per_tone[72] ← argmax(spectra) 在 B_r 内     │
      │     hist ← weighted_histogram(bpm_per_tone, weights) │
      │     voted_bpm = argmax(hist)                         │
      │     confidence = hist[voted_bpm] / sum(hist)         │
      │     weighted_spectrum = sum(weights[i] × spectra[i]) │
      │     → (voted_bpm, confidence, weighted_spectrum)     │
      │     [参考: voting_fusion.py → _vote_weights,         │
      │             vote_bpm_weighted_histogram]              │
      │                                                      │
      │   三模态 Voting 结果:                                 │
      │     remote:  (bpm_r, conf_r, spec_r)                 │
      │     local:   (bpm_l, conf_l, spec_l)                 │
      │     phase:   (bpm_p, conf_p, spec_p)                 │
      │                                                      │
      │   【NEW】模态间 Voting 共识:                           │
      │     Option A (默认): confidence-weighted median      │
      │       final_bpm = weighted_median(                   │
      │         [bpm_r, bpm_l, bpm_p],                       │
      │         [conf_r, conf_l, conf_p]                     │
      │       )                                              │
      │     Option B: 取最高 confidence 模态的 voted_bpm     │
      │     → ★ 最终 BPM 输出 ★                              │
      │                                                      │
      └─► 两级 Hilbert-MRC 波形管线 ─────────────────────────┘
            │
            │  与 B2-D 完全相同（已有逻辑，不变）:
            │
            ├─► Level 1: coherent_mrc_fuse_tones()
            │     [模块: coherent_mrc.py]
            │     - Hilbert 解析信号 (72 tone)
            │     - 以最高 quality tone 为参考
            │     - 相位对齐 + coherence gating (min_coherence=0.2)
            │     - 加权融合 → per-modal waveform
            │     → wave_r, wave_l, wave_p
            │
            ├─► Level 2: coherent_mrc_fuse_modals()
            │     [模块: coherent_mrc.py]
            │     - 以最高 η modal 为参考
            │     - Hilbert 模态间相位对齐
            │     - η·coherence 加权融合
            │     → 最终呼吸波形 y_final
            │
            └─► 波形质量评估:
                  RMSE = window_rmse_against_reference(y_final, hkh_bandpass_window)
                  → ★ RMSE 输出 ★

  输出 (每窗):
    - BPM:   信道级 Voting 三模态共识          (primary)
    - 波形:  两级 Hilbert-MRC 融合输出          (primary)
    - RMSE:  融合波形 vs HKH 带通波形           (primary)
    - BPM_wf: 最终波形 PSD 寻峰结果             (secondary, 仅作 sanity check)
```

### 3.2 与 B1 / B2-D 的关键差异

| 维度 | B1 Vote→Equal | B2-D Two-level | **B3（本 plan）** |
|------|--------------|----------------|-------------------|
| 信道融合 | Voting（η·ρ 直方图） | η·ρ 质量加权 + Hilbert 对齐 | **Voting（同 B1）+ Hilbert 对齐（同 B2-D）** |
| 模态融合 | 等权谱平均 | 两级 Hilbert + η·coherence | **两级 Hilbert + η·coherence（同 B2-D）** |
| BPM 来源 | 融合谱寻峰 | 最终波形 PSD | **信道级 Voting 共识** |
| 波形输出 | ❌ | ✅ 最终融合波形 | ✅ 最终融合波形（同 B2-D） |
| 增量计算 | — | — | 仅 Voting（< B2-D 的 5%） |

### 3.3 各步骤的物理/算法理由

| # | 步骤 | 为什么需要这一步 | 消融验证 |
|---|------|----------------|---------|
| 1 | Per-tone η·ρ 权重 | η 度量呼吸频段能量占比，ρ 度量谱峰锐度；两者相乘同时惩罚低能量和宽峰 | A5（等权投票） |
| 2 | 直方图 Voting | 72 tone 独立估计 BPM → 多数投票天然压制 outlier 频率估计 | A1（单信道 best-η） |
| 3 | 三模态分别 Voting 后共识 | remote / local / phase 走不同物理路径，先独立投票再共识保留了模态多样性 | A3（Remote only） |
| 4 | Hilbert 相位对齐 | 多径使不同 tone 的呼吸调制相位不同；对齐后叠加实现相干增益 | A4（等权谱平均） |
| 5 | Coherence gating | 与参考 tone 相关性低的 tone（coherence < 0.2）大概率是噪声，排除后提升波形 SNR | A6（无 gating） |
| 6 | 两级（tone→modal→waveform） | 先在同模态内对齐（相同物理量），后跨模态对齐（不同物理量），避免直接混合 216 维 | A4（跨模态直接谱融合） |
| 7 | Voting BPM（而非波形 BPM） | 频域多数投票对 outlier tone 鲁棒；波形 BPM 依赖融合波形的质量（级联风险） | A2（波形 PSD BPM） |

---

## 4. Baseline 对比

### 4.1 外部 Baseline（与既有方法对比）

| 方法 | 说明 | 来源 |
|------|------|------|
| B1 Vote→Equal | 上一代 BPM 最优方法（12 场景 0.41 BPM） | `systematic_fusion.py` |
| B1 Uniform Remote | 12 场景 BPM 第 1（0.37 BPM） | `chfusion.py` |
| B2-D Two-level | 上一代波形最优方法（RMSE 0.950） | `coherent_mrc.py` |
| Zhuo Z1-no-VMD | 论文方法 BPM 最优（0.44 BPM） | `pca_vmd.py` |
| Fan η-linear | 单场景曾最优（跨场景 1.39） | `wifi_mrc.py` |

### 4.2 消融变体（内部 Baseline）

每个消融变体只改变 B3-Full 的一个设计选择，其余保持不变。

#### Tier 1（必须运行 — 核心设计选择辩护）

| ID | 变体 | 改动 | 验证的设计选择 |
|----|------|------|---------------|
| **B3-Full** | 全管线 | — | — |
| **A1** | 单信道 best-η | Voting → 每模态选单个最高 η tone；其余不变 | 步骤 2：直方图 Voting 的价值 |
| **A2** | 波形 PSD BPM | BPM 来源：信道 Voting → 最终波形 PSD 寻峰（= B2-D 的 BPM 方式）；其余不变 | 步骤 7：Voting BPM vs 波形 BPM |
| **A3** | Remote only | 去掉 local + phase 模态；仅 Remote → 单级 Hilbert-MRC；其余不变 | 步骤 3：三模态 vs 单模态 |
| **A4** | 等权谱融合 | 两级 Hilbert → 三模态等权谱平均 + Welch 寻峰（≈ B1 的模态融合方式）；无波形输出 | 步骤 4+6：时域相位对齐的价值 |

#### Tier 2（建议运行 — 深度理解）

| ID | 变体 | 改动 | 验证的设计选择 |
|----|------|------|---------------|
| **A5** | 等权投票 | η·ρ 权重 → 每 tone 等权（simple majority histogram）；其余不变 | 步骤 1：η·ρ 质量加权 vs 简单计票 |
| **A6** | 无 coherence gate | min_coherence = 0；其余不变 | 步骤 5：coherence gating 的价值 |
| **A7** | 跨模态直接 Voting | 三模态分别 Voting → 216 tone 全局 Voting（不分 modal）；其余不变 | 步骤 3（变体）：per-modal 分组的意义 |

### 4.3 预期相对关系（假设，可被实验推翻）

| 对比 | 预期 | 理由 |
|------|------|------|
| B3-Full vs B1 Vote→Equal | BPM 相当或略优；B3 多了波形 | B3 的 Voting 与 B1 同源，模态融合更先进（Hilbert vs equal spectral） |
| B3-Full vs B2-D | BPM 明显更优（std 更小）；RMSE 相当 | Voting BPM 避免了 B2-D 在 3/12 场景上的 BPM 崩溃 |
| B3-Full vs A1 | BPM 更优（尤其 outlier 场景） | Voting 压制 outlier tone；单信道无此保护 |
| B3-Full vs A2 | BPM std 更小；outlier 场景差距显著 | Voting BPM 对参考 tone 质量不敏感 |
| B3-Full vs A3 | RMSE 更优；BPM 相当或略优 | 多模态提供分集增益 |
| B3-Full vs A4 | RMSE 明显更优 | Hilbert 相位对齐保证波形形态；谱平均无相位信息 |
| B3-Full vs A5 | BPM 略优 | η·ρ 权重给高质量 tone 更高投票权 |
| B3-Full vs A6 | RMSE 略优 | coherence gate 排除噪声 tone |
| B3 vs Fan / Yu / Zhuo | 至少同量级 | 预期 BPM ≤ 0.5，RMSE ≤ 1.0 |

---

## 5. 评估设计

### 5.1 场景与指标

| 维度 | 内容 |
|------|------|
| 场景 | 全部 12 个 HKH 真人场景（`config/scenarios/room_{A,B,C}-sbj_{A,B,C,D}-*.json`） |
| 主指标 | **BPM 绝对误差 mean ± std**（12 场景跨域） |
| 次指标 | **窗级 RMSE**（z-score + 符号对齐，仅波形输出变体） |
| 补充指标 | BPM 相对误差 %、跨域 mean、按 Room 分组、按姿势分组（Living vs Bedroom） |
| 滑窗 | 20 s 窗长 / 1 s 步长 |
| 呼吸频段 | 0.1–0.35 Hz |
| GT | HKH 带通波形 Welch 寻峰 BPM（fs = len/duration） |

### 5.2 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | B3-Full BPM ≤ B1 Vote→Equal（0.41 BPM 跨域 mean），且 RMSE ≤ B2-D（0.950） |
| **理想** | B3-Full BPM ≤ 0.40 且 RMSE ≤ 0.95，且 std ≤ 0.20；A1/A2 显著劣于 Full |
| **失败** | B3-Full BPM > 0.50 或 RMSE > 1.05，或 A1/A2 反超 Full |
| **额外关注** | A-D（`room_A-sbj_D`）、C-A（`room_C-sbj_A`）、B-C（`room_B-sbj_C`）三个问题场景上的 BPM 是否仍崩溃 |

### 5.3 消融结果解读矩阵

实验完成后，用以下矩阵判断每个步骤是否有意义：

| 步骤 | 对应消融 | 判断标准 | 若失效说明 |
|------|---------|---------|-----------|
| η·ρ 权重 | Full vs A5 | ΔBPM > 0.02 或 ΔRMSE > 0.02 | ρ 在此数据上无额外信息 |
| Voting | Full vs A1 | ΔBPM > 0.05 或 outlier 场景 Δ > 0.5 | 单信道 best-η 已足够 |
| 三模态 | Full vs A3 | ΔRMSE > 0.03 | Remote 单模态已够 |
| Hilbert 相位对齐 | Full vs A4 | ΔRMSE > 0.05 | 谱融合已是波形质量上限 |
| Coherence gate | Full vs A6 | ΔRMSE > 0.01 | coherence 在此数据上无区分力 |
| Voting BPM | Full vs A2 | 3 outlier 场景 ΔBPM > 0.3 | Voting 和波形 BPM 等价 |

> **关键原则**：如果某步骤被消融实验判定为「无显著效果」，应诚实报告并在论文中去掉该步骤，而不是保留以增加复杂性。

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 | 说明 |
|------|------|------|
| **新增模块** | `src/ble_analysis/b3_pipeline.py` | B3 统一管线主逻辑，包含 `_vote_bpm_per_modal()` 和 `estimate_b3_window()` |
| **修改模块** | `src/ble_analysis/wifi_mrc.py` | `_collect_modal_window_matrix()` 新增可选返回 per-tone 谱 |
| **修改模块** | `src/ble_analysis/coherent_mrc.py` | 新增 `estimate_b3_segment()` 入口，或在 `_window_b2_bpms` 中插入 Voting 步骤 |
| **新增脚本** | `notebooks/scripts/chFusion_ble_hkh_b3_validation.py` | B3 + 全部消融变体 × 12 场景批量验证 |
| 不改动 | `systematic_fusion.py`、`voting_fusion.py`、`chfusion.py` | B1/Voting 逻辑作为参考保留 |
| 不改动 | `ble_hkh_validation.py` | `validate_b2_against_hkh()` 继续用于 B2-D baseline |

### 6.2 推荐实现策略：最小侵入

为降低对现有代码的破坏风险，推荐**新建 `b3_pipeline.py` 作为 wrapper**，而非修改 `coherent_mrc.py` 内部逻辑：

```python
# src/ble_analysis/b3_pipeline.py  (伪代码 / 接口草案)

def _compute_per_tone_spectra(
    X: np.ndarray,     # [N_tones, T_win] bandpass slices
    fs: float,
    nfft: int,
    breath_band: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Compute per-tone power spectra and frequency axis.
    
    Returns:
        spectra: [N_tones, nfft//2] normalized power spectra
        freq_axis: [nfft//2] frequency bins in Hz
    """
    ...

def _vote_bpm_per_modal(
    spectra: np.ndarray,  # [N_tones, nfft//2]
    eta: np.ndarray,       # [N_tones]
    rho: np.ndarray,       # [N_tones]
    freq_axis: np.ndarray, # [nfft//2]
    breath_band: tuple[float, float],
    bpm_bin_width_hz: float = 0.02,
) -> dict:
    """η·ρ weighted histogram voting over tones → voted BPM + confidence.
    
    Returns:
        voted_bpm: float
        confidence: float in [0, 1]
        weighted_spectrum: [nfft//2] voting-weight-averaged spectrum
    """
    ...

def _modal_voting_consensus(
    modal_results: dict[str, dict],  # {"remote": {...}, "local": {...}, "phase": {...}}
    method: str = "weighted_median",
) -> float:
    """Consensus across three modals' voted BPMs.
    
    method="weighted_median": confidence-weighted median
    method="max_confidence": take the modal with highest confidence
    """
    ...

def estimate_b3_window(
    multichannel_by_var: dict,
    seg_name: str,
    ch_list: list,
    st: int,
    end: int,
    fs: float,
    config: ChFusionConfig,
    *,
    vote_bpm: bool = True,              # True = B3-Full, False → falls back to A2 (waveform BPM)
    min_coherence: float = 0.2,
    modal_consensus: str = "weighted_median",
    # Ablation toggles:
    use_voting: bool = True,            # False → A1 (single best-η)
    use_eta_rho_weights: bool = True,   # False → A5 (equal weights)
    use_multi_modal: bool = True,       # False → A3 (remote only)
    use_two_level_hilbert: bool = True, # False → A4 (equal spectral fusion)
    return_waveform: bool = True,
) -> dict:
    """Single-window B3 pipeline.
    
    Returns:
        bpm: float — primary BPM from channel-level voting (or waveform PSD if vote_bpm=False)
        waveform: np.ndarray | None — fused breathing waveform
        rmse: float | None — vs HKH GT (computed externally)
        diagnostics: dict — per-modal voting results, tone weights, coherences
    """
    ...
```

### 6.3 关键实现注意事项

1. **per-tone 谱的保留**：`_collect_modal_window_matrix()` 当前在 `wifi_mrc.py` 中只返回 `etas, rhos, X, valid_mask`。需要在计算 η 的过程中保留 FFT 结果。`_energy_ratio()` 内部调用了 Welch/FFT——修改它的返回签名是最干净的方案，但会影响所有调用方。替代方案：在 B3 wrapper 中单独调用一次 per-tone FFT（增加 ~5% 计算但避免改动核心模块）。

2. **Voting 权重与 MRC 权重的复用**：B3 的 Voting 权重 `η × max(ρ, 0)` 与 B2-D 的 MRC quality weights 完全相同。可以直接传入 `coherent_mrc_fuse_tones()` 的 `eta` 和 `rho` 参数，避免重复计算。

3. **三模态 Voting 共识策略**：当前建议的 `confidence-weighted median` 是自然的默认选择，但如果两种策略（weighted_median vs max_confidence）在 12 场景上结果差异显著，应选择更优者作为默认并报告 ablation。

4. **HKH GT 口径统一**：B3 的 BPM 验证口径与 B1、B2-D 完全一致——HKH 带通波形 Welch 寻峰，`fs = len / duration`，`nfft` 零填充。

5. **A4（等权谱融合）的特殊处理**：A4 不产生波形，使用 `_bpm_from_fused_spectrum()` 估计 BPM。其 RMSE 无法计算——在汇总表中标记为 N/A。

### 6.4 不做的事

- 不修改 `systematic_fusion.py`（B1 保留为独立参考）
- 不修改 `coherent_mrc.py` 的核心融合逻辑（B2-D 保留为独立参考）
- 不新增滤波参数、滑窗参数、指标定义
- 不引入窗级门控或其他外部融合逻辑
- 不修改已有 12 场景的预处理结果

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| B3 核心模块 | `src/ble_analysis/b3_pipeline.py` |
| B3 + 消融批量脚本 | `notebooks/scripts/chFusion_ble_hkh_b3_validation.py` |
| 每场景完整结果 | `outputs/reports/ble_hkh_b3_validation_{scenario_id}.json` ×12 |
| 跨场景汇总结果 | `outputs/reports/ble_hkh_b3_validation_summary.json` |
| 消融排行榜图 | `outputs/figures/ble_hkh_b3_ablation_leaderboard.png` |
| BPM vs RMSE 散点图 | `outputs/figures/ble_hkh_b3_bpm_vs_rmse.png` |
| 问题场景 BPM 时间序列图 | `outputs/figures/ble_hkh_b3_outlier_timeseries.png` |
| 验证报告 | `docs/reports/b3_unified_pipeline_voting_bpm_report.md` |

### 建议运行命令

```bash
python notebooks/scripts/chFusion_ble_hkh_b3_validation.py
```

---

## 8. 验证状态与保留问题

> 由**执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | 待实现 |
| **实际脚本** | — |
| **报告链接** | — |
| **一句话结论** | — |

### 保留问题

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | Voting 的三模态共识策略（weighted_median vs max_confidence）哪个更优？ | 实验确定 |
| Q2 | `_energy_ratio()` 内部 FFT 结果是否值得复用（vs 独立计算 per-tone 谱）？ | 工程权衡，见 §6.3(1) |
| Q3 | A4（等权谱融合）无波形 → 无法算 RMSE，如何公平对比？ | 只在 BPM 维度对比 |
| Q4 | 3 条问题场景（A-D, B-C, C-A）是否会因 B3 Voting BPM 而改善？ | 本 plan 核心假设之一 |
| Q5 | 若某消融步骤判定为「无显著效果」，是否需要从 B3 最终方案中移除？ | 论文策略，待 Review 决策 |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并按以下顺序执行：

### Phase 1 — 模块实现

1. 读取本 plan：`docs/plans/b3_unified_pipeline_voting_bpm_plan.md`
2. **新建** `src/ble_analysis/b3_pipeline.py`：
   - 实现 `_compute_per_tone_spectra()`——per-tone FFT 功率谱
   - 实现 `_vote_bpm_per_modal()`——η·ρ 加权直方图投票
   - 实现 `_modal_voting_consensus()`——三模态 voted BPM 共识
   - 实现 `estimate_b3_window()`——单窗 B3 完整管线，含 ablation toggle 参数（`use_voting`, `use_eta_rho_weights`, `use_multi_modal`, `use_two_level_hilbert`, `vote_bpm`）
3. 在 `estimate_b3_window()` 内部：
   - 调用 `_collect_modal_window_matrix()` 获取 X, η, ρ
   - 调 `_compute_per_tone_spectra()` 获取 per-tone 谱
   - 调 `_vote_bpm_per_modal()` × 3 modal
   - 调 `_modal_voting_consensus()` → final BPM
   - 调 `coherent_mrc_fuse_tones()` × 3 modal → per-modal waveforms
   - 调 `coherent_mrc_fuse_modals()` → final waveform
   - 根据 `vote_bpm` flag 决定 BPM 来源（Voting vs waveform PSD）
4. **不要修改** `coherent_mrc.py`、`wifi_mrc.py`、`systematic_fusion.py`、`voting_fusion.py`

### Phase 2 — 批量验证

1. **新建** `notebooks/scripts/chFusion_ble_hkh_b3_validation.py`
2. 遍历全部 12 个 HKH 场景配置
3. 对每个场景运行以下变体（至少 Tier 1）：
   - **Tier 1（必须）**：B3-Full, A1（单信道 best-η）, A2（波形 PSD BPM）, A3（Remote only）, A4（等权谱融合）
   - **Tier 2（建议）**：A5（等权投票）, A6（无 coherence gate）, A7（跨模态直接 Voting）
   - **外部 baseline**：B1 Vote→Equal, B2-D, Zhuo Z1-no-VMD
4. 每场景保存独立结果 JSON；生成跨场景汇总 JSON
5. 生成以下图表：
   - 消融排行榜（全部变体 + baseline 的 BPM mean±std 及 RMSE）
   - BPM vs RMSE 散点图（x=BPM err, y=RMSE，每个变体一个点）
   - 3 条问题场景的 BPM 时间序列图（B3-Full vs A1 vs A2 vs B2-D vs HKH GT）
6. 使用 `docs/templates/algorithm_validation_report.md` 撰写 `docs/reports/b3_unified_pipeline_voting_bpm_report.md`
7. 在报告中填写 §6.3 消融结果解读矩阵，明确标记每个步骤的「有意义 / 无显著效果」
8. 回填本 plan §8 验证状态

---

## 补充确认：12 场景对齐质量

原始 plan 规定 `anchor_diff_ms > 100 ms` 应停止处理；执行阶段因 BLE 采样率仅 ~2.4 Hz（采样间隔 ~417 ms），锚点偏差 100–206 ms 均在单次采样间隔内，属于正常现象而非时钟错配。**批量预处理汇总**（`ble_hkh_preprocess_batch_summary.json`）确认：

| 项目 | 值 |
|------|-----|
| 最小 \|anchor_diff\| | 29 ms（room_B-sbj_C） |
| 最大 \|anchor_diff\| | 206 ms（room_C-sbj_A） |
| \|anchor_diff\| > 100 ms 的场景 | 8/11 |
| 根因 | BLE ~2.4 Hz 稀疏采样 + HKH ~50.7 Hz 密集采样 → 最近帧查找存在 ±208 ms 量化误差 |
| 结论 | **全部 12 条数据对齐可接受**，不需重新预处理 |

> **建议**：将 plan 模板中的 100 ms 停止规则更新为「< 100 ms 通过，100–500 ms 警告（记录原因），> 500 ms 停止（疑似时钟错配/文件错配）」。
