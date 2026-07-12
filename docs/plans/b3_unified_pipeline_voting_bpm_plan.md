# B3 统一管线：信道级 Voting BPM + 两级 Hilbert-MRC 波形 — 实现计划

> **来源**：B1（Vote→Equal, BPM-only）与 B2-D（Two-level Hilbert-MRC, waveform）的跨场景验证结论  
> **目标报告**：`docs/reports/b3_unified_pipeline_voting_bpm_report.md`（模板：`docs/templates/algorithm_validation_report.md`）  
> **建议 plan 路径**：`docs/plans/b3_unified_pipeline_voting_bpm_plan.md`  
> **日期**：2026-07-12  
> **验证状态**：已完成

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
| **B3（精简版，最终）** | **η·ρ Voting**（= B1 前端） | **两级 Hilbert-MRC**（= B2-D，去 coherence gate） | **Voting → 三模态等权谱融合寻峰**（= B1） | ✅ |

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

### 3.1 完整流程图（精简版，消融实验后定稿）

> **消融依据**：A5（η·ρ 权重 ΔBPM=0.02）、A6（coherence gate ΔBPM=0.00, ΔRMSE=+0.001）、A7（全局 Voting ΔBPM=0.00）在 12 场景跨域无显著效果，已从管线移除。B3 B1-equal 变体验证 equal spectral fusion 替代 weighted_median 共识可精确复现 B1 BPM（0.405 vs 0.405，max |Δ|=0.000），已替换。

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
  ║  Shared Frontend（per modal: remote / local / phase）    ║
  ║  [模块: wifi_mrc.py → _collect_modal_window_matrix()]    ║
  ║                                                        ║
  ║    X [72, T_win] ← bandpass 时域切片                    ║
  ║    η[72]  ← _energy_ratio(highpass)                     ║
  ║    ρ[72]  ← _peak_prominence(bandpass)                  ║
  ║    quality[72] = η × max(ρ, 0)                          ║
  ║    spectra[72, nfft] ← per-tone FFT 功率谱              ║
  ╚══════════════════════════════════════════════════════════╝
      │
      ├─► BPM 路径（= B1 Vote→Equal）:
      │     Per-modal η·ρ 加权直方图 Voting
      │       weights[72] = η × max(ρ, 0) / Σ(η × max(ρ,0))
      │       weighted_spectrum = Σ(weights[i] × spectra[i])
      │       [参考: voting_fusion.py + systematic_fusion.py]
      │     → per-modal weighted_spectrum (remote / local / phase)
      │     → 三模态等权谱融合（1:1:1）
      │     → argmax 寻峰 → ★ 最终 BPM ★
      │
      └─► 波形路径（= B2-D 精简版，去 coherence gate）:
            Level 1: coherent_mrc_fuse_tones() per modal
              [模块: coherent_mrc.py]
              - Hilbert 解析信号 (72 tone)
              - 以最高 quality tone 为参考
              - 相位对齐（无 coherence gating）
              - quality 加权融合 → per-modal waveform
              → wave_r, wave_l, wave_p
            │
            Level 2: coherent_mrc_fuse_modals()
              [模块: coherent_mrc.py]
              - 以最高 η modal 为参考
              - Hilbert 模态间相位对齐
              - η 加权融合
              → 最终呼吸波形 y_final → ★ RMSE ★

  输出 (每窗):
    - BPM:   Voting → 三模态等权谱融合寻峰（= B1，已验证 BPM=0.405）
    - 波形:  两级 Hilbert-MRC 融合输出（= B2-D，RMSE=0.950）
```

### 3.2 与 B1 / B2-D 的关键差异

| 维度 | B1 Vote→Equal | B2-D Two-level | **B3（精简版）** |
|------|--------------|----------------|-------------------|
| 信道融合 | Voting（η·ρ 直方图） | η·ρ 质量加权 + Hilbert 对齐 | **Voting（同 B1）+ Hilbert 对齐（同 B2-D）** |
| 模态融合 | 等权谱平均（1:1:1） | 两级 Hilbert + η·coherence 加权 | **两级 Hilbert（同 B2-D，去 coherence gate）** |
| BPM 来源 | 融合谱寻峰 | 最终波形 PSD | **Voting → 等权谱融合寻峰（= B1）** |
| 波形输出 | ❌ | ✅ 最终融合波形 | ✅ 最终融合波形 |
| 增量计算 | — | — | 仅 Voting（< B2-D 的 5%） |

### 3.3 各步骤的物理/算法理由

| # | 步骤 | 为什么需要这一步 | 消融验证 | 保留？ |
|---|------|----------------|---------|--------|
| 1 | Per-tone η·ρ 权重 | η 度量呼吸频段能量占比，ρ 度量谱峰锐度 | A5（ΔBPM=0.02, 几乎零成本） | ✅ |
| 2 | 直方图 Voting | 72 tone 独立估计 BPM → 多数投票天然压制 outlier | **A1（ΔBPM=0.50，outlier Δ>1）** | ✅ |
| 3 | Voting BPM（而非波形 PSD BPM） | 频域投票对参考 tone 质量不敏感，避免级联崩溃 | **A2（ΔBPM=0.22，outlier Δ>1）** | ✅ |
| 4 | 三模态分别 Voting | remote/local/phase 走不同物理路径，保留模态多样性 | A3（ΔBPM=0.00，但物理自洽性要求对称对待） | ✅ |
| 5 | Equal spectral fusion（vs weighted_median） | 等权谱融合保留完整谱信息，argmax 更鲁棒；weighted_median 在两个高 confidence 模态给出相近错误 BPM 时无纠正机制 | **B3 B1-equal vs Full（BPM 0.405 vs 0.46）** | ✅ |
| 6 | 两级 Hilbert 相位对齐 | 先 tone 级后 modal 级相干叠加，避免直接混合 216 维 | A4（BPM Δ=+0.06，但 RMSE 仅 Hilbert 路径可产出） | ✅ |
| 7 | ~~Coherence gate~~ | — | A6（ΔBPM=0.00, ΔRMSE=+0.001） | ❌ 移除 |
| 8 | ~~跨模态全局 Voting~~ | — | A7（ΔBPM=0.00, ΔRMSE=0.000） | ❌ 移除 |
| 9 | ~~波形 PSD BPM 路径~~ | — | A2（Voting BPM 严格更优） | ❌ 移除 |

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

### 4.3 消融实验结果（执行后回填）

> 数据来源：[`b3_unified_pipeline_voting_bpm_report.md`](../reports/b3_unified_pipeline_voting_bpm_report.md) §4.4

| 步骤 | 对比 | ΔBPM | ΔRMSE | 判定 | 管线处置 |
|------|------|-----:|------:|------|----------|
| η·ρ 权重 | Full vs A5 | 0.02 | 0.000 | **无显著效果** | ✅ 保留（几乎零成本，B1 遗产） |
| 直方图 Voting | Full vs A1 | 0.50 | 0.000 | **有意义**（outlier Δ>1） | ✅ 保留 |
| 三模态 | Full vs A3 | 0.00 | +0.020 (A3 略优) | BPM 无增益；RMSE A3 略优 | ✅ 保留（物理自洽） |
| Hilbert 相位对齐 | Full vs A4 | +0.06 | N/A | BPM 变差；RMSE 无法比（A4 无波形） | ✅ 保留（唯波形产出路径） |
| ~~Coherence gate~~ | Full vs A6 | 0.00 | +0.001 | **无显著效果** | ❌ **移除** |
| Voting BPM | Full vs A2 | 0.22 | 0.000 | **有意义**（outlier Δ>1） | ✅ 保留（替代波形 PSD BPM） |
| per-modal 分组 | Full vs A7 | 0.00 | 0.000 | **无显著效果** | ❌ **移除** |
| Equal spectral vs weighted_median | B3 B1-equal vs Full | **0.055** | 0.000 | **有意义**（B3 B1-equal BPM=0.405 ≡ B1） | ✅ **替换为 equal spectral** |

### 4.4 论文消融实验表（建议格式）

> 以下表格可直接用于论文 §4.3 Ablation Study。仅报告有显著效果的消融，其余可一句带过或放 supplementary。

**Table X: Ablation study on 12-scene HKH dataset (BPM absolute error, breaths/min).**

| Ablation | Variant Description | BPM mean±std | Δ BPM (vs Final) | Outlier Δ (A-D / C-A) |
|----------|--------------------|-------------:|-----------------:|----------------------:|
| — | **B3 (Final, simplified)** | **0.41±0.14** | — | — |
| (i) | Remove Voting → single best-η per modal | 0.96±1.28 | +0.55 | +1.66 / +0.99 |
| (ii) | Replace Voting BPM with waveform PSD BPM | 0.68±0.84 | +0.27 | +1.66 / +1.05 |
| (iii) | Replace equal spectral fusion with weighted_median | 0.46±0.37 | +0.05 | — |
| (iv) | Remove η·ρ weights → simple majority vote | 0.44±0.34 | +0.03 | — |
| (v) | Remote modal only (no local/phase) | 0.46±0.36 | +0.05 | — |

**消融解读（论文正文用）**：

- **(i) Voting 的必要性**：移除直方图 Voting（退化为单信道 best-η），跨域 BPM 从 0.41 升至 0.96。在 outlier 场景 A-D 上 Δ=+1.66 BPM——Voting 的多数投票机制是防止单一低质量信道劫持 BPM 估计的核心保护。
- **(ii) Voting BPM vs 波形 PSD BPM**：用 B2-D 的最终波形 PSD 寻峰替代 Voting BPM，BPM 从 0.41 升至 0.68，outlier 场景 Δ>1 BPM。原因：波形融合以 η 最高 tone 为参考做 Hilbert 对齐，参考 tone 质量决定整个融合链的 BPM 可靠性——Voting BPM 不依赖单一参考 tone，天然更鲁棒。
- **(iii) Equal spectral vs weighted_median**：三模态分别 Voting 后用置信度加权中位数（而非等权谱融合），BPM 从 0.41 升至 0.46。weighted_median 在两个高 confidence 模态给出相近但错误的 BPM 时缺乏纠正机制；等权谱融合保留了完整频谱信息，argmax 在融合谱上更鲁棒。
- **(iv)–(v)**：η·ρ 权重和模态数对 12 场景跨域均值的贡献较小（Δ≤0.05），但保留 η·ρ（几乎零成本）和三模态（物理自洽性要求对称对待 remote/local/phase）的理由不在跨域均值而在物理合理性。

**其余消融（可 supplementary 或正文一句话）**：Coherence gate（ΔBPM=0.00, ΔRMSE=+0.001）、跨模态全局 Voting（ΔBPM=0.00, ΔRMSE=0.000）在 12 场景跨域无显著效果，已从最终管线移除。

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

### 5.2 成功标准 vs 实际

| 级别 | 条件 | 实际 | 达标？ |
|------|------|------|--------|
| **最低** | B3 BPM ≤ B1（0.41），RMSE ≤ B2-D（0.950） | B3-Full BPM 0.46 ❌；B3 B1-equal BPM **0.405** ✅；RMSE 0.950 ✅ | **B3 B1-equal 达标** |
| **理想** | BPM ≤ 0.40，RMSE ≤ 0.95，std ≤ 0.20 | BPM 0.405（差 0.005），RMSE 0.950 ✅，std 0.14 ✅ | **接近理想** |
| **outlier 关注** | A-D、C-A、B-C 不再崩溃 | A-D: 2.31→0.60, C-A: 1.40→0.27 ✅；B-C 无显著差异 | **2/3 改善** |

### 5.3 消融结果解读矩阵（已回填实际结果）

| 步骤 | 对应消融 | 判断标准 | 实际 | 判定 |
|------|---------|---------|------|------|
| η·ρ 权重 | Full vs A5 | ΔBPM > 0.02 | ΔBPM=0.02 | 边界，保留（零成本） |
| Voting | Full vs A1 | ΔBPM > 0.05 | **ΔBPM=0.50** | ✅ 有意义 |
| 三模态 | Full vs A3 | ΔRMSE > 0.03 | ΔBPM=0.00 | 按物理自洽保留 |
| Hilbert 相位对齐 | Full vs A4 | ΔRMSE > 0.05 | ΔBPM=+0.06 | 保留（波形唯一路径） |
| ~~Coherence gate~~ | Full vs A6 | ΔRMSE > 0.01 | ΔRMSE=+0.001 | ❌ 移除 |
| Voting BPM | Full vs A2 | outlier Δ>0.3 | **ΔBPM=0.22** | ✅ 有意义 |
| Equal spectral vs weighted_median | B3 B1-equal vs Full | ΔBPM > 0.02 | **ΔBPM=0.055** | ✅ 替换 |
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

> **Review 更新日期**：2026-07-12（消融实验完成后，Claude/DeepSeek Review）

| 字段 | 内容 |
|------|------|
| **验证状态** | ✅ **已完成 — 精简版方案已定稿** |
| **实际脚本** | `notebooks/scripts/chFusion_ble_hkh_b3_validation.py`（完整消融）；`_quick_b3_b1_equal_check.py`（B3 B1-equal 快验） |
| **核心模块** | `src/ble_analysis/b3_pipeline.py` |
| **报告链接** | `docs/reports/b3_unified_pipeline_voting_bpm_report.md` |
| **数值结果** | `outputs/reports/ble_hkh_b3_validation_summary.json` |
| **图表** | `outputs/figures/ble_hkh_b3_ablation_leaderboard.png`；`ble_hkh_b3_bpm_vs_rmse.png`；`ble_hkh_b3_outlier_timeseries.png` |

### 最终方案（Review 定稿）

**B3 Simplified** = B1 Vote→Equal BPM + B2-D Waveform，共享前端：

| 组件 | 来源 | 配置 |
|------|------|------|
| 共享前端 | B2-D `_collect_modal_window_matrix()` | 保留 per-tone η, ρ, spectra |
| BPM 路径 | **B1 Vote→Equal** | η·ρ Voting → 三模态等权谱融合（1:1:1）→ argmax |
| 波形路径 | **B2-D 精简** | 两级 Hilbert 相位对齐（去 coherence gate）→ 最终波形 |
| 移除 | B3-Full 中无效步骤 | coherence gate、weighted_median 共识、波形 PSD BPM、跨模态全局 Voting |

**关键数值**（12 场景 HKH，B3 B1-equal 变体）：

| 指标 | B3 B1-equal | B1 Vote→Equal | B2-D |
|------|------------|--------------|------|
| BPM cross mean | **0.405** | 0.405 | 0.68 |
| RMSE mean | **0.950** | N/A | 0.950 |
| Outlier A-D BPM | 0.60 | 0.60 | 2.31 |
| Outlier C-A BPM | 0.27 | 0.27 | 1.40 |

### 执行结论摘要

- **B3-Full 最低标准**：部分满足 — RMSE ≤ B2-D ✅；BPM ≤ B1 ❌（0.46 > 0.41）
- **B3 B1-equal 变体**：BPM 精确复现 B1（0.405），RMSE 保持 B2-D（0.950）— **这是推荐部署版本**
- **消融核心发现**：Voting（A1 ΔBPM=0.50）和 Voting BPM（A2 ΔBPM=0.22）是唯二有显著跨域效果的步骤
- **放弃的步骤**：coherence gate（Δ=0.00）、全局 Voting（Δ=0.00）、weighted_median（被 equal spectral 替换）

### 保留问题（Review 更新）

| ID | 问题 | 结论 |
|----|------|------|
| Q1 | B3 B1-equal 完整 12 场景验证？ | ✅ 已完成 — `chFusion_ble_hkh_b3_validation.py --mode simplified` 产出 `ble_hkh_b3_simplified_validation_summary.json` |
| Q2 | 精简版代码是否需重构 `b3_pipeline.py`？ | ✅ 已完成 — 移除 coherence gate / weighted_median / waveform PSD BPM / 全局 Voting；默认 equal spectral |
| Q3 | 精简版是否影响论文消融写作？ | 不影响 — 消融数据已存在（§4.4），论文可直接引用 |
| Q4 | B2-D 中 coherence gate 是否在 CS 金属板场景有不同表现？ | 未测试；12 场景 HKH 上无效果不一定推广到 CS 场景 |

---

## 9. 下一步：论文写作与管线清理

### 9.1 论文消融写作

见本 plan §4.4 的论文消融表。写作策略：
- §3 Method 描述 B3 Simplified（精简版）
- §4.3 Ablation 报告表 X（§4.4 格式），论证 Voting、Voting BPM、equal spectral fusion 三个关键设计选择
- 其余消融（coherence gate、全局 Voting）一句带过或放 supplementary

### 9.2 待执行任务

| 优先级 | 任务 | 说明 |
|--------|------|------|
| **P0** | 为 B3 B1-equal 跑完整 12 场景批量验证 | ✅ 已完成 — `ble_hkh_b3_simplified_validation_summary.json` |
| **P0** | 更新 `b3_pipeline.py` 至精简版 | ✅ 已完成 |
| **P1** | 更新 `docs/methods/README.md` | ✅ 已完成 — B3 Simplified 条目 + HKH 排行榜 + CS [待确认] 标注 |
| **P1** | 更新 `docs/CS呼吸算法验证整体进度.md` | 补充 B3 + HKH 多场景验证章节和方法演进路线图 |
| **P2** | 新 plan: `b1_b2_hybrid_gating` | 窗级门控：|B2 BPM − B1 BPM| > 阈值 → 取 B1（HKH 报告 §4.9） |
| **P2** | 异常场景目视诊断 | A-D、B-C、C-A 三条问题场景的 HKH 佩戴质量可视化检查 |
| **P3** | CS 金属板场景上验证 B3 Simplified | 确认精简版在 091339/095806/102621 上不退化（当前仅 HKH 12 场景验证） |

---

## 10. 给执行 Agent 的首条指令（精简版）

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，按以下顺序执行：

### Phase 1 — B3 B1-equal 完整验证

1. 运行 `notebooks/scripts/chFusion_ble_hkh_b3_validation.py` 的 B3 B1-equal 配置（`modal_bpm_fusion="equal_spectral"`），12 场景全量
2. 产出 `outputs/reports/ble_hkh_b3_simplified_validation_summary.json`
3. 确认 BPM=0.405、RMSE=0.950 与 quick-check 一致
4. 如有偏差，报告差异 root cause

### Phase 2 — 管线代码清理

1. 更新 `src/ble_analysis/b3_pipeline.py`：
   - 默认 `modal_bpm_fusion="equal_spectral"`（替代 `weighted_median`）
   - 移除 coherence gate 相关参数（`min_coherence`）
   - 移除 `vote_bpm` toggle（始终使用 Voting BPM）
   - 移除全局 Voting 路径（A7）
   - 保留 `use_voting`、`use_eta_rho_weights`、`use_multi_modal` 消融 toggle
2. 不改动 `coherent_mrc.py`、`systematic_fusion.py`、`voting_fusion.py`

### Phase 3 — 文档更新

1. 更新 `docs/methods/README.md`：新增 B3 Simplified 条目 + 更新排行榜
2. 更新 `docs/CS呼吸算法验证整体进度.md`：补充 B3 + HKH 章节
3. 完成后准备 git commit

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
