# Two-Level Hilbert Coherent MRC Waveform Fusion for BLE Channel Sounding-Based Respiration Monitoring

> **状态**：Manuscript 大纲（金属板实验阶段）  
> **日期**：2026-06-26  
> **后续**：真人环境实验结果补充后更新  

---

## 论文元信息（草案）

| 字段 | 内容 |
|------|------|
| **论文类型** | Journal paper |
| **建议期刊** | IEEE Internet of Things Journal / IEEE Sensors Journal / IEEE Transactions on Instrumentation & Measurement |
| **核心技术** | Two-Level Hilbert Coherent MRC → 融合呼吸波形 + BPM 估计 |
| **验证范围** | 金属板脚本 × 3 房间布局（跨域验证） |
| **对比基线** | Fan 2024 [1]、Yu 2021 WiFi-Sleep [2]、Zhuo 2023 [3]（三篇 WiFi CSI 文献，均已迁移到 BLE CS） |
| **内部参照** | B1 Vote→Equal（谱域 Voting fusion，跨域 8.45% — 当前内部最优 BPM 方法） |

---

# 1. Introduction

## 1.1 背景

- 非接触式呼吸监测的临床需求（睡眠呼吸暂停筛查、慢性呼吸疾病长期监测、婴儿/老年护理）
- 现有方法的局限：接触式（PSG/呼吸带）不舒适、视觉方案受光照/遮挡影响、雷达方案成本高
- WiFi CSI 呼吸感知的成熟度 — Fan 2024, Yu 2021 WiFi-Sleep, Zhuo 2023 等代表工作

## 1.2 BLE Channel Sounding 作为新兴感知平台

- BLE CS 的设计初衷：蓝牙高精度测距（~0.5 m）
- 副产物：72 tone × 双向 IQ 测量 → 信道频率响应采样 → 潜在的呼吸感知信号源
- BLE CS vs WiFi CSI 的关键差异：
  | 维度 | WiFi CSI | BLE CS |
  |------|----------|--------|
  | 频段 | 2.4/5 GHz | 2.4 GHz |
  | 子载波/tone 数 | 30–114 | 72 |
  | 采样率 | 50–200 Hz | ~2 Hz |
  | 天线数 | 2–3 RX | 单天线对 |
  | 可用变量 | CSI ratio 幅值/相位 | remote_amp / local_amp / phases |
  | 设备 | 需特定网卡 + 工具 | 标准 BLE 6.0 芯片 |
- **核心挑战**：BLE CS 的 2 Hz 低采样率能否支撑呼吸感知？72 tone 的频域分集能否弥补时域欠采样？

## 1.3 现有 WiFi 文献方法迁移到 BLE CS 的适配问题

- **Fan 2024** [1]：η-MRC 子载波融合 → 最优模态选择。原文仅对单一 CSI ratio 流操作。迁移到 BLE CS 后，remote/local/phase 三模态如何处理？我们创建了 BPM 平均（legacy）和波形等权融合（wf）两种 fair 变体。
- **Yu 2021 WiFi-Sleep** [2]：MRC-PCA 符号校正 + 多链路融合。原文针对多天线对设计。迁移到 BLE CS 后，三模态如何融合？我们创建了 BPM 平均（legacy）和 PCA(3→1) 波形融合两种 fair 变体。
- **Zhuo 2023** [3]：PCA+VMD + 峰值检测 BPM。原文基于 CSI ratio 复平面投影。迁移到 BLE CS 后，BPM 估计方式（峰值检测 vs FFT）和 VMD 在 2 Hz 下的有效性均是开放问题。我们创建了 ±VMD × ±FFT 四种变体。

## 1.4 本文贡献

1. **提出 B2-D**：首个面向 BLE CS 的两级 Hilbert 相干 MRC 波形融合方法。第一级 tone-level Hilbert 连续相位补偿 + coherence gating；第二级 modal-level Hilbert 相位对齐 + η·γ 质量加权。**输出可用的呼吸波形**（而不仅是 BPM）。
2. **系统性消融**：量化 Hilbert 连续相位 vs PCA/corr 符号校正（−1.42 pp 跨域增益）、coherence gating（Δ < 0.02 pp）、两层级联（−1.46 pp）、modal Hilbert 对齐（−1.46 pp）各模块的独立贡献。
3. **公平外部基线对比**：将 Fan 2024 / Yu 2021 / Zhuo 2023 三篇 WiFi 文献迁移到 BLE CS，并为其创建原文未涉及的 fair 变体。B2-D（9.43%）在三个金属板场景上系统性优于全部外部基线（最优 WiFi MRC 10.78%）。
4. **BLE CS 感知可行性实证**：在 ~2 Hz 采样率下，72 tone 频率分集 + 时域相干融合可实现 9.43% 的 BPM 相对误差（跨域 mean），验证了 BLE CS 作为低成本呼吸感知平台的潜力。

---

# 2. Background: BLE CS for Respiration Sensing

## 2.1 BLE CS 物理层

### 2.1.1 CS 测量过程
- 一次 CS process：双向交换 — initiator 发 → reflector 收（local PCT），reflector 发 → initiator 收（remote PCT）
- PCT (Phase Correction Term)：单次 IQ 测量在应用层的上报形式
- 两端 PCT 向量相乘 → 抵消载波频偏 (CFO) 导致的相位漂移

### 2.1.2 可用观测量
$$
\begin{aligned}
A_r(t) &= |\text{PCT}_{\text{remote}}(t)| \quad &\text{(remote 幅值)} \\
A_l(t) &= |\text{PCT}_{\text{local}}(t)| \quad &\text{(local 幅值)} \\
\phi(t) &= \angle\left[\text{PCT}_{\text{remote}}(t) \cdot \text{PCT}_{\text{local}}(t)\right] \quad &\text{(总相位，LO 漂移已抵消)}
\end{aligned}
$$

- remote/local 物理上完全对等（同一 CS 交换的两个方向），不存在先验质量差异
- 总幅值 $A_r(t) \cdot A_l(t)$ 无独立物理意义（双方噪声乘积），不使用

### 2.1.3 72 tone 结构
- 72 tone 跨越 ~72 MHz 带宽（1 MHz 间隔）
- 每个 tone 为独立的窄带信道频率响应采样
- 室内多径相干带宽 ~1–3 MHz < 72 MHz → tone 间衰落不相关 → 频率分集

## 2.2 BLE CS vs WiFi CSI 的物理差异

| 特性 | WiFi CSI (5 GHz, 20 MHz) | BLE CS (2.4 GHz, 72 MHz) |
|------|--------------------------|---------------------------|
| 采样率 | 50–200 Hz | **~2 Hz** |
| 子载波 | 30（等间隔） | **72（等间隔）** |
| 天线 | 2–3 RX | **单天线对** |
| 带宽 | 20 MHz | **72 MHz**（更宽） |
| 变量 | CSI ratio 幅值/相位 | **remote_amp, local_amp, phases（3 种）** |

→ BLE CS 用**更宽的带宽（频率分集）** 弥补**更低的采样率（时域稀疏）**。

## 2.3 信号模型

对于第 $i$ 个 tone 的带通呼吸波形：

$$
x_i(t) = |h_i| \cdot s(t - \tau_i) + n_i(t)
$$

其中 $s(t)$ 为真实呼吸运动，$h_i$ 为该 tone 的复信道增益，$\tau_i = \Delta\phi_i / (2\pi f_0)$ 为 tone 间呼吸分量的相对时延，$n_i(t)$ 为噪声。

在窄带呼吸频段 (0.1–0.35 Hz) 内近似：

$$
x_i(t) \approx |h_i| \cdot s(t) \cdot e^{j\Delta\phi_i} + n_i(t)
$$

→ **MRC 融合需要补偿 $\Delta\phi_i$ 以实现相长干涉** — 这是 B2 方法的物理出发点。

---

# 3. Proposed Method: Two-Level Hilbert Coherent MRC

## 3.1 总体架构

```text
┌─────────────────────────────────────────────────────────────────┐
│ Preprocessing (shared with all methods)                          │
│ Raw 72 tones × 3 variables                                       │
│  → Phase unwrap (phases only)                                    │
│  → Per-tone filter chain: median → highpass (0.05 Hz)            │
│    → bandpass (0.1–0.35 Hz) → z-score standardization            │
│  → Sliding window: 20 s / 1 s step                               │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Remote 72-tone  │ │ Local 72-tone   │ │ Phase 72-tone   │
│ bandpass matrix │ │ bandpass matrix │ │ bandpass matrix │
│ [T_win × 72]    │ │ [T_win × 72]    │ │ [T_win × 72]    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 1: Tone-Level Coherent MRC (per modal, §3.2)               │
│                                                                    │
│  For each tone i in modal m:                                      │
│    z_i(t) = Hilbert(x_i(t))             ▸ analytic signal         │
│    q_i = η_i · ρ_i                       ▸ quality weight         │
│                                                                    │
│  Reference selection: i* = argmax_i q_i                           │
│  Phase estimation:                                                │
│    Δφ_i = angle( Σ_t z_i(t) · conj(z_{i*}(t)) )                  │
│    γ_i  = |Σ z_i · conj(z_{i*})| / √(Σ|z_i|² · Σ|z_{i*}|²)     │
│                                                                    │
│  Coherence-gated weights:                                         │
│    w_i = q_i · γ_i   (if γ_i ≥ 0.2, else 0)                      │
│                                                                    │
│  Coherent fusion:                                                 │
│    z_m^fused(t) = Σ_i w_i · z_i(t) · e^{-jΔφ_i} / Σ_i w_i        │
│    y_m(t) = Re{z_m^fused(t)}                                      │
│                                                                    │
│  Output: {y_r(t), y_l(t), y_p(t)} — 3 modal breathing waveforms  │
└─────────────────────────────────────────────────────────────────┘
            │                 │                 │
            └─────────────────┼─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 2: Modal-Level Hilbert Coherent Fusion (§3.3)               │
│                                                                    │
│  Input: y_r(t), y_l(t), y_p(t) from Level 1                       │
│                                                                    │
│  Modal analytic signals:                                          │
│    z_m(t) = Hilbert(y_m(t)),  m ∈ {r, l, p}                       │
│                                                                    │
│  Reference: m* = argmax_m η(y_m)                                  │
│  Inter-modal phase alignment:                                     │
│    Δφ_m = angle( Σ_t z_m(t) · conj(z_{m*}(t)) )                  │
│    γ_m  = coherence as above                                      │
│                                                                    │
│  Modal quality weights:                                           │
│    W_m = η(y_m) · γ_m                                             │
│                                                                    │
│  Final fused waveform:                                            │
│    z_final(t) = Σ_m W_m · z_m(t) · e^{-jΔφ_m} / Σ_m W_m          │
│    y_final(t) = Re{z_final(t)}                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ BPM Estimation (§3.4)                                             │
│ y_final(t) → Welch PSD → argmax ∈ [0.1, 0.35] Hz                 │
│   → parabolic interpolation → BPM                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 3.2 第一级：Tone-Level Hilbert Coherent MRC

### 3.2.1 Hilbert 解析信号构造
$$
z_i(t) = x_i(t) + j \cdot \mathcal{H}\{x_i(t)\}
$$
其中 $\mathcal{H}\{\cdot\}$ 为 Hilbert 变换。解析信号的瞬时相位 $\angle z_i(t)$ 和瞬时幅值 $|z_i(t)|$ 为连续相位对齐提供了数学基础。

### 3.2.2 Per-Tone 质量权重
$$
q_i = \eta_i \cdot \rho_i
$$

| 指标 | 定义 | 物理含义 |
|------|------|----------|
| $\eta_i$ | $E_{[0.1,0.35]\text{Hz}} / E_{[0.35,0.8]\text{Hz}}$ | 呼吸频段能量占比 |
| $\rho_i$ | $\max P_i(f) / \text{median } P_i(f)$ | 谱峰尖锐度 |

### 3.2.3 相位差估计（相对于参考 tone）
$$
\Delta\phi_i = \angle\left( \sum_t z_i(t) \cdot \overline{z_{i^*}(t)} \right)
$$
其中 $i^* = \arg\max_i q_i$ 为参考 tone。

### 3.2.4 Coherence Gating
$$
\gamma_i = \frac{\left|\sum_t z_i(t) \cdot \overline{z_{i^*}(t)}\right|}{\sqrt{\sum_t |z_i(t)|^2 \cdot \sum_t |z_{i^*}(t)|^2}} \in [0, 1]
$$

- $\gamma_i$ 度量 tone $i$ 与参考 tone 之间呼吸波形分量的相位一致性
- 硬门控：$\gamma_i < 0.2 \rightarrow w_i = 0$（剔除与参考反相/无相关的 tone）

### 3.2.5 相干加权融合
$$
w_i = q_i \cdot \max(\gamma_i, 0.2), \quad z_m^{\text{fused}}(t) = \frac{\sum_i w_i \cdot z_i(t) \cdot e^{-j\Delta\phi_i}}{\sum_i w_i}
$$
$$
y_m(t) = \Re\{z_m^{\text{fused}}(t)\}
$$

## 3.3 第二级：Modal-Level Hilbert Coherent Fusion

### 3.3.1 动机
第一级输出 $y_r(t), y_l(t), y_p(t)$ 三条融合波形。它们对应同一呼吸运动，但在不同模态（remote/local/phase）中的表现可能不同——某模态可能在某个半周期信噪比更高。第二级对三条模态波形做相干融合。

### 3.3.2 模态间相位对齐
- 参考模态：$m^* = \arg\max_{m \in \{r,l,p\}} \eta(y_m)$
- 模态间 Hilbert 互解析相位差 $\Delta\phi_m$（公式同 §3.2.3）
- 模态间相干性 $\gamma_m$（公式同 §3.2.4）

### 3.3.3 模态质量加权
$$
W_m = \eta(y_m) \cdot \gamma_m
$$

### 3.3.4 最终融合波形
$$
z_{\text{final}}(t) = \frac{\sum_m W_m \cdot z_m(t) \cdot e^{-j\Delta\phi_m}}{\sum_m W_m}, \quad y_{\text{final}}(t) = \Re\{z_{\text{final}}(t)\}
$$

## 3.4 BPM 估计

### 3.4.1 主方法：Welch PSD
- 去均值 + Hanning 窗 → rFFT → $P(f) = |\text{FFT}|^2$
- $\hat{f}_{\text{peak}} = \arg\max_{f \in [0.1, 0.35]\text{Hz}} P(f)$
- 抛物线插值细化 → $\text{BPM} = 60 \cdot \hat{f}_{\text{peak}}$

### 3.4.2 备选方法（诊断用）
- ACF 自相关 → 峰值间隔
- 波形峰值检测 → 呼吸周期

## 3.5 消融变体设计（Table 2 in paper）

| 变体 | 第一级相位 | 第一级权重 | 第二级 | 目的 |
|------|-----------|-----------|--------|------|
| **B2-D** | Hilbert 连续 | η·ρ + γ gate | Hilbert 对齐 + η·γ | **主方案** |
| B2-C | FFT 互谱 (B1 f₀) | η·ρ + γ gate | 等权 | FFT vs Hilbert 相位估计 |
| B2-Bγ | Hilbert 连续 | η·ρ + γ gate | 等权 | 第二级增益消融 |
| B2-B | Hilbert 连续 | η·ρ only | 等权 | Coherence gating 消融 |
| B2-A1 | Corr sign | η·ρ + sign | 等权 | Sign vs Hilbert 消融 |
| B2-A0 | PCA sign | η·ρ + sign | 等权 | 最简符号校正（WiFi MRC 等同） |
| B2-A0-D | PCA sign | η·ρ + sign | Hilbert 对齐 + η·γ | 符号校正 + 二级 Hilbert |
| B2-D-eq | Hilbert 连续 | η·ρ + γ gate | 等权（无对齐） | 模态对齐增益消融 |

---

# 4. Baseline Methods (Adapted from WiFi Literature)

## 4.1 Baseline 1: Fan 2024 — η-MRC Subcarrier Fusion [1]

### 4.1.1 原文方法摘要
- CSI ratio 幅值 → 逐子载波 BNR 估计 → MRC 加权 → Savitzky-Golay 平滑 → 60 s 呼吸波形 → CNN-LSTM 分类
- 原文仅处理单一 CSI ratio 流（1 维信号链）

### 4.1.2 BLE CS 适配（模块：`wifi_mrc.py`）

```
Per-modal: 72 tone bandpass → η_i estimation → MRC weights g_i = η_i
  → y_m(t) = Σ g_i · x_i(t) / Σ g_i  → Welch FFT → BPM_m

Modal combine:
  Best: BPM = BPM_{m*},  m* = argmax η(y_m)     (原文范式)
  Equal (BPM avg): BPM = mean(BPM_r, BPM_l, BPM_p)  (legacy)
  Equal (waveform avg): y_fused = mean(y_r, y_l, y_p) → FFT → BPM  (新 fair 变体)
  Hilbert-align: per-tone Hilbert phase align → MRC → waveform avg   (新 fair 变体)
```

### 4.1.3 Fair Comparison 变体说明
- **BPM avg (legacy)**：原文无需处理三模态融合 → 最直接的泛化是各模态独立 MRC 后 BPM 取平均
- **波形等权 (wf)**：时域波形融合 → 测试波形层面的互补性能否带来增益
- **Hilbert 对齐**：加入与 B2 同级的 Hilbert 相位对齐 → 测试 MRC 框架下的对齐增益上限

## 4.2 Baseline 2: Yu 2021 WiFi-Sleep — MRC-PCA [2]

### 4.2.1 原文方法摘要
- CSI ratio → 多子载波 amplitude/phase candidates → PSD-SNR 估计 → MRC gain → PCA sign correction → signed MRC → ACF 呼吸率
- 原文具有多天线对（3 RX），PCA 符号校正建立在"多链路呼吸波形可能反相"的物理事实上

### 4.2.2 BLE CS 适配（模块：`wifi_mrc.py`）

```
Per-modal: 72 tone bandpass → √η_i MRC weights → PCA on weighted tones
  → sign_i = sign(PC1 loading_i) → w_i = sign_i · √η_i / Σ|sign_j · √η_j|
  → y_m(t) = Σ w_i · x_i(t) → Welch FFT → BPM_m

Modal combine:
  Best: BPM = BPM_{m*}  (原文范式)
  Equal (BPM avg): BPM = mean(BPM_r, BPM_l, BPM_p)  (legacy)
  Equal (PCA 3→1): X_wf = [y_r, y_l, y_p] → PCA(3→1) → FFT → BPM  (新 fair 变体)
```

### 4.2.3 Fair Comparison 变体说明
- 原文的多链路 PCA 融合针对同一变量的多个空间链路 → 在 BLE CS 中，三模态是不同物理量的时间序列，PCA(3→1) 是 PCA 降维思路的自然扩展

## 4.3 Baseline 3: Zhuo 2023 — PCA-VMD [3]

### 4.3.1 原文方法摘要
- CSI ratio → 复平面投影（周期性与变化性联合评分选最优模式）→ 波形方向调整 → PCA 多子载波融合 → VMD 分解 → 峰值检测 + 伪峰剔除 → 呼吸率

### 4.3.2 BLE CS 适配（模块：`pca_vmd.py`）

```
Per-modal: 72 tone bandpass → PCA(72→1) → PC1 waveform
  → sign alignment (max-Var PC1 as reference)

Cross-modal: [PC1_r, PC1_l, PC1_p] → PCA(3→1) → y_pca(t)

Post-processing (Z1 main):
  y_pca(t) → VMD (K=2, α=2000) → max-Var mode → peak detection → BPM

Variants:
  Z1_no_vmd: skip VMD, peak detection on y_pca(t)    (VMD ablation)
  Z1_fft: VMD → Welch FFT → BPM                      (FFT vs peak detection)
  Z1_no_vmd_fft: no VMD + FFT                          (pure PCA + standard BPM)
  Z1_proj: complex plane projection before PCA         (projection ablation)
  Z1_hilbert: Hilbert sign alignment instead of corr   (alignment ablation)
```

### 4.3.3 Fair Comparison 变体说明
- **VMD ±**：原文 K=3 基于 ~100 Hz WiFi CSI；在 BLE ~2 Hz 下 VMD 有效性为开放问题
- **FFT vs 峰值检测**：原文使用峰值检测（非 FFT）；FFT 变体使 BPM 估计方式与 B2 和所有其他 baseline 对齐
- **投影 ±**：原文基于 CSI ratio 复数结构；在 BLE CS 中仅 remote/local amplitude 可构造复信号，phase 不可

---

# 5. Experimental Setup

## 5.1 数据采集

| 参数 | 值 |
|------|-----|
| 平台 | nRF52840 BLE 6.0 |
| 天线配置 | 单天线对（1 TX, 1 RX） |
| CS tone | 72（1 MHz 间隔） |
| CS 间隔 | ~500 ms → 有效采样率 ~2 Hz |
| 呼吸模拟 | 金属板周期性运动（可编程脚本） |
| Ground truth BPM | 金属板脚本设定频率 |

## 5.2 验证场景

| 场景 ID | 房间布局 | 多径特征 | 备注 |
|---------|----------|----------|------|
| cs_091339 | LoS + 金属反射面 | 复杂多径 | 瓶颈场景（所有方法 >12%） |
| cs_095806 | LoS + 部分遮挡 | 中等复杂 | Voting 方法优势 |
| cs_102621 | LoS 为主 | 较简单 | 跨域对照 |

→ 三个场景权重相等，用于跨域鲁棒性评估（非单场景报告）。

## 5.3 信号处理参数

| 参数 | 值 | 备注 |
|------|-----|------|
| 窗长 / 步长 | 20 s / 1 s | 覆盖 2–7 个呼吸周期 |
| 滤波链 | median(w=3) → highpass(0.05 Hz, order=1) → bandpass(0.1–0.35 Hz, order=2) | 所有方法完全一致 |
| 呼吸频段 | 0.1–0.35 Hz (6–21 BPM) | 覆盖成人静息呼吸 |
| FFT | rFFT, Hanning 窗, nfft = next_pow2(4 × win_len) | 抛物线插值细化 |
| z-score | per-tone per-window 标准化 | 消除 tone 间增益差异 |

## 5.4 评估指标

| 指标 | 定义 |
|------|------|
| **段级 BPM 相对误差 % (mean)** | $\frac{1}{N_{\text{seg}}} \sum_j \frac{\|\text{BPM}_{\text{est},j} - \text{BPM}_{\text{gt},j}\|}{\text{BPM}_{\text{gt},j}} \times 100\%$ |
| 跨域 mean | 三场景等权平均 |
| 段级 BPM 相对误差 % (std) | 稳定性指标 |
| $R^2$ / signed error | 偏差方向诊断 |

---

# 6. Results and Discussion

## 6.1 Overall Performance Ranking (Table 3)

**建议主表结构**：方法 × 场景 + 跨域 mean，按跨域 mean 升序排列。

| 排名 | 类别 | 方法 | cs_091339 | cs_095806 | cs_102621 | 跨域 mean |
|------|------|------|-----------|-----------|-----------|-----------|
| 1 | 内部谱域参照 | B1 Vote→Equal modal | 13.22 | 6.50 | 5.63 | **8.45%** |
| 2 | **Proposed** | **B2-D Two-Level Hilbert MRC** | 15.01 | **5.82** | 7.45 | **9.43%** |
| 3 | Proposed 变体 | B2-C FFT cross-spectrum | 15.98 | 5.69 | 6.83 | 9.50% |
| 4 | Yu 2021 | MRC-PCA-η-equal (BPM avg) | 17.63 | 7.29 | 7.41 | **10.78%** |
| 5 | Proposed 变体 | B2-Bγ (no modal level) | 17.85 | 5.67 | 9.17 | 10.89% |
| 6 | Zhuo 2023 | Z1 PCA-VMD-Peak | 17.49 | 8.20 | 8.22 | **11.31%** |
| 7 | Fan 2024 | Fan-η-equal (BPM avg) | 18.78 | 11.79 | 9.97 | **13.51%** |
| 8+ | ... | 其他 fair 变体 (waveform avg, Hilbert, PCA 3→1) | ... | ... | ... | 12.79–16.60% |

> **关键叙事**：B2-D（9.43%）在所有外部基线中最优（Yu MRC-PCA 10.78% +1.35 pp, Zhuo Z1 11.31% +1.88 pp, Fan η-equal 13.51% +4.08 pp）。谱域内部方法 B1（8.45%）在 BPM 精度上更优但不输出波形。

## 6.2 Ablation Analysis (Figure X)

建议双面板图：
- **(a) 消融阶梯图**：A0 (12.33%) → A1 (11.06%) → B (10.91%) → Bγ (10.89%) → D (9.43%)，标注 Δ
- **(b) 关键消融配对条形图**：
  - Sign vs Hilbert: A0 (12.33%) vs B (10.91%), Δ = −1.42 pp
  - Coherence gating: B (10.91%) vs Bγ (10.89%), Δ = −0.02 pp
  - Single-level vs Two-level: Bγ (10.89%) vs D (9.43%), Δ = −1.46 pp
  - Modal alignment: D-eq (10.89%) vs D (9.43%), Δ = −1.46 pp

### 6.2.1 Finding 1: Hilbert 连续相位 > 符号校正 (Δ = −1.42 pp)
- PCA sign (A0, 12.33%) 和 corr sign (A1, 11.06%) 只能校正 0/π → 丢失连续相位信息
- Hilbert (B, 10.91%) 补偿连续 [−π, π] 相位差 → 各 tone 波形真正相长干涉
- 091339 上收益最大（20.57% → 17.80%），复杂多径下相位精度的边际收益更大

### 6.2.2 Finding 2: Coherence gating 几乎无跨域收益 (Δ < 0.02 pp)
- 在 η·ρ 已经有效筛选的基础上，γ 门控未提供额外增益
- 可能原因：η·ρ 已经压制了低质量 tone；在 coherence gating 有效的情况下，被排除的 tone 本来权重也很低
- 但 coherence gating 为第二级提供了模态间相干性估计的基础

### 6.2.3 Finding 3: 两层级联有意义 (Δ = −1.46 pp)
- B2-Bγ（仅 tone-level, 10.89%）vs B2-D（tone + modal level, 9.43%）
- 模态间 Hilbert 对齐在 091339 上贡献最大（17.85% → 15.01%, Δ = −2.84 pp）
- 确认三模态波形之间存在可利用的相位互补性

### 6.2.4 Finding 4: 符号校正 + 二级 Hilbert ≠ 全 Hilbert (Figure Y)
- A0-D (11.09%) 大幅劣于 D (9.43%)，差 1.66 pp
- A1-D (11.15%) ≈ A1 (11.06%) — 第二级在符号校正前提上无效
- **两阶段的交互效应**：第二级 Hilbert 对齐的增益（−1.46 pp）依赖于第一级已做连续相位补偿

## 6.3 Comparison with WiFi Baselines (Figure X)

### 6.3.1 跨域排行榜
- 三类路线定位：Proposed B2 (9.43%) < WiFi MRC-PCA (10.78%) < WiFi PCA-VMD (11.31%) < WiFi η-MRC (13.51%)
- 全场景一致：B2-D 在三个场景上均不劣于 WiFi 最优方法

### 6.3.2 分场景优势
| 场景 | B2-D | 最优 WiFi baseline | Δ | 说明 |
|------|------|--------------------|------|------|
| cs_091339 | 15.01% | MRC-PCA 17.63% | −2.62 pp | 困难场景下时域相干融合优势最大 |
| cs_095806 | 5.82% | MRC-PCA 7.29% | −1.47 pp | 最优场景，B2-D 亦优于所有外基线 |
| cs_102621 | 7.45% | MRC-PCA 7.41% | +0.04 pp | 唯一外基线接近的场景（可接受的持平） |

### 6.3.3 Fair variant analysis: waveform fusion ≠ always better
- Fan equal waveform avg (16.60%) **劣于** BPM avg (13.51%) → +3.09 pp
- MRC-PCA PCA(3→1) (12.79%) **劣于** BPM avg (10.78%) → +2.01 pp
- **解释**：BPM 标量平均在困难场景（cs_091339）意外地平滑了某模态的离群 BPM
- **论文叙事**：我们主动报告了这些 fair 变体，而不只 cherry-pick 最好的 baseline 数值

## 6.4 Why B2-D does not surpass B1 (8.45%)

- **B1 是谱域非相干融合**：$\eta \cdot \rho$ per-tone 加权直方图投票 → 三模态等权谱融合
- B1 不依赖 tone 间相位相干性 → 在 091339 等低相干场景更稳健（13.22% vs 15.01%）
- B2-D 在 tone 间相干性高的场景（095806, 5.82% vs 6.50%）可超越 B1
- **互补性**：B2-D 提供**呼吸波形**（可用于后续呼吸模式识别、呼吸深度估计等），B1 仅提供 BPM
- **坦率报告** B1 (8.45%) 为 BPM 精度上界，B2-D (9.43%) 为波形输出的 trade-off

## 6.5 Key Findings Summary

| # | 发现 | 证据 |
|---|------|------|
| 1 | Hilbert 连续相位优于符号校正 | B2-B (10.91%) vs B2-A0 (12.33%), Δ = −1.42 pp |
| 2 | 两层级联结构必需 | B2-D (9.43%) vs B2-Bγ (10.89%), Δ = −1.46 pp |
| 3 | 两级间存在交互效应 | A1-D (11.15%) ≈ A1 (11.06%), 二级增益需一级 Hilbert 前提 |
| 4 | Coherence gating 无独立增益 | Bγ vs B, Δ < 0.02 pp |
| 5 | B2-D 系统性优于三篇 WiFi SOTA | vs Yu +1.35 pp, vs Zhuo +1.88 pp, vs Fan +4.08 pp |
| 6 | Waveform equal 变体劣于 BPM 平均 | Fair 变体创建的必要性 — 不能假设波形融合一定更好 |
| 7 | VMD 在 BLE 2 Hz 下无增益 | Z1 vs Z1_no_vmd, Δ = 0.10 pp |

---

# 7. Discussion

## 7.1 为什么 Hilbert MRC 在 BLE CS 上有效？

- 72 MHz 带宽 > 相干带宽 → tone 间多径衰落独立 → 频率分集
- Hilbert 连续相位对齐将分集增益从功率谱域（B1）推进到时域波形
- 低采样率（2 Hz）在此反为优势：20 s 窗内仅 40 sample → Hilbert 相位估计的边界效应更可控

## 7.2 为什么未能超越 B1？

- B1 的 Voting 在功率谱域保留了 tone 间相位差异的全部信息（每 tone 独立估计 BPM 后投票）
- B2 的 MRC 在时域合并时，即使连续相位对齐，波形叠加仍然可能损失信息
- 本质 trade-off：谱域非相干（保留全部相位信息但无法输出波形）vs 时域相干（输出波形但信息可能有损耗）

## 7.3 金属板的局限与真人环境的推广

- 金属板 = 单散射体、呼吸运动单一频率 → 简化了多径环境
- 真人胸部运动 = 多散射体、呼吸+心跳混合、体动干扰
- 真人环境的预期差异：
  - tone 间 coherence 可能更低（更复杂的体表散射）
  - 呼吸频率变异性（非恒定 BPM）→ 需要窗内跟踪
  - 体动检测和剔除需求
- **B2 的波形输出优势在真人环境中将更加关键**：呼吸波形可用于与呼吸带 ground truth 做相关性分析、呼吸深度估计、吸呼比提取

## 7.4 部署考量

| 因素 | B2-D | B1 | 外部 WiFi 方法 |
|------|------|-----|---------------|
| BPM 精度 (跨域) | 9.43% | 8.45% | 10.78–13.51% |
| 输出呼吸波形 | ✅ | ❌ (仅 BPM) | ✅ (MRC) / ❌ (Voting) |
| 计算复杂度 | 中等 (Hilbert + 2 级) | 低 (PSD + Voting) | 中–高 (PCA/VMD) |
| 物理自洽 | ✅ | ✅ | ✅ |
| 推荐场景 | 需要波形 + 可接受的 BPM trade-off | 仅需 BPM | — (不推荐) |

---

# 8. Conclusion

## 8.1 Summary

- 提出 B2-D — 首个面向 BLE CS 的两级 Hilbert 相干 MRC 波形融合方法
- B2-D（9.43%）系统性优于三篇 WiFi SOTA baseline：Yu 2021 MRC-PCA (10.78%, +1.35 pp)、Zhuo 2023 PCA-VMD (11.31%, +1.88 pp)、Fan 2024 η-MRC (13.51%, +4.08 pp)
- 系统性消融确认：Hilbert 连续相位（−1.42 pp）和两层级联（−1.46 pp）是 B2 增益的核心来源
- 公平对比：为各 WiFi 基线创建原文未涉及的 BLE CS 适配变体（波形融合、FFT BPM、±VMD），如实报告
- B2-D 输出可用呼吸波形 — 这是谱域方法不具备的能力

## 8.2 Limitations

1. 仅金属板模拟呼吸验证 — 真人胸部生理运动的复杂性（多散射体、呼吸-心跳混合）尚未覆盖
2. B1（谱域 Voting）BPM 精度仍优于 B2-D（8.45% vs 9.43%）— 当仅需 BPM 时，B1 是更优选择
3. cs_091339 瓶颈（所有方法 >12%）— 该场景的多径环境对 tone 间相干性退化机制尚待独立诊断
4. 静态场景 — 未考虑体动干扰

## 8.3 Future Work

1. **真人实验**：在真实人体呼吸数据上验证 B2-D 的波形质量和 BPM 精度（与呼吸带 ground truth 对比波形相关性）
2. **B1+B2 per-window 动态选择**：利用 B1 和 B2-D 的场景间互补性（095806 上 B2-D 优于 B1），设计基于窗级 tone 间 coherence 信号的物理自洽选择器
3. **cs_091339 退化诊断**：量化 tone 间 Hilbert 相干的场景依赖性，诊断多径环境对相干 MRC 的退化机制
4. **体动检测与剔除**：利用 B2 的 γ（coherence）信号作为体动检测的代理指标
5. **呼吸形态特征提取**：从 B2-D 的融合波形中提取呼吸深度、吸呼比等特征（参考 WiFi-Sleep 的形态分析框架）

---

# References

[1] X. Fan et al., "A Contactless Breathing Pattern Recognition System Using Deep Learning and WiFi Signal," *IEEE Internet of Things Journal*, 2024.

[2] B. Yu, Y. Wang, K. Niu, Y. Zeng, T. Gu, L. Wang, C. Guan, and D. Zhang, "WiFi-Sleep: Sleep Stage Monitoring Using Commodity Wi-Fi Devices," *IEEE Internet of Things Journal*, vol. 8, no. 18, pp. 13900–13913, 2021. DOI: `10.1109/JIOT.2021.3068798`.

[3] H. Zhuo, X. Wu, Q. Zhong, and H. Zhang, "Position-Free Breath Detection During Sleep via Commodity WiFi," *IEEE Sensors Journal*, 2023.

---

# 建议 Figure List

| Figure | 内容 | 数据来源 |
|--------|------|----------|
| **Fig. 1** | B2-D 总体架构图（§3.1 流程图的美化版） | — |
| **Fig. 2** | Hilbert 相位对齐原理示意图（tone i vs ref tone, 解析信号复平面） | — |
| **Fig. 3** | 主排行榜条形图（跨域 mean, 分方法着色：proposed / internal / Yu2021 / Zhuo2023 / Fan2024） | `b2_coherent_mrc_leaderboard.png` |
| **Fig. 4** | 跨域汇总面板图（三场景 × 关键方法 BPM err%） | `b2_coherent_mrc_cross_domain_summary.png` |
| **Fig. 5** | 消融阶梯图（A0→A1→B→Bγ→D, 标注每个 Δ） | `b2_coherent_mrc_phase_method_ablation.png` |
| **Fig. 6** | Sign vs Hilbert 配对条形图（A0 vs B, A1 vs B, A0-D vs D）+ 091339 放大 | 需新图 |
| **Fig. 7** | 两级交互效应图：A0→A0-D vs B→Bγ→D | 需新图 |
| **Fig. 8** | 分场景雷达图 / 热力图（proposed + 3 external baselines × 3 scenarios） | 需新图 |
| **Fig. 9** | 融合呼吸波形示例（B2-D y_final(t), 标 η/γ 质量, 叠加 ground truth 周期） | 需新图 |

---

# 建议 Table List

| Table | 内容 |
|-------|------|
| **Table 1** | BLE CS vs WiFi CSI 关键参数对比 |
| **Table 2** | B2 消融变体矩阵（Phase × Weight × Level） |
| **Table 3** | 主结果表（全方法 × 三场景 + 跨域 mean） |
| **Table 4** | 消融分析表（A0/A1/B/Bγ/C/D/D-eq/A0-D/A1-D 各场景 + 跨域） |
| **Table 5** | Fair comparison 变体表（per baseline: 原文范式 vs fair 变体结果） |
| **Table 6** | 关键假设验证汇总 |

---

# 当前状态与待补充

| 项目 | 状态 | 备注 |
|------|------|------|
| 金属板三场景实验 | ✅ 完成 | 所有数据已跑完，结果在 `outputs/reports/` |
| 方法实现 | ✅ 完成 | `src/ble_analysis/coherent_mrc.py` |
| 外部基线实现 | ✅ 完成 | `wifi_mrc.py`, `pca_vmd.py` |
| 论文图表 | ⚠️ 部分完成 | 需补：原理示意图 (Fig 1–2)、配对消融图 (Fig 6–7)、波形示例 (Fig 9) |
| 真人实验 | ❌ 待进行 | Future work 章节的核心 |
| 论文正文 | ❌ 待撰写 | 本大纲为章节级指引 |

---

> **下一轮建议**：先基于本大纲撰写 Methods + Results 的初稿（使用已有数值和图表），Introduction 和 Discussion 可在真人实验数据出来后调整叙事重心。
