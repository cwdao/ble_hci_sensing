# Paper Outline: BLE CS Breathing Sensing — Unified BPM + Waveform Pipeline

> **定位**：论文大纲 + 算法流程公式化描述 + 图表设计  
> **日期**：2026-07-18（2026-07-18 更新：加入 §2–§3 验证图 + 调整 novelty 定位 + 金属板/真人数据角色分工）  
> **状态**：供用户审阅

---

## 1. 论文标题（草稿）

**Breathing Sensing via BLE Channel Sounding: System Modeling, Phase Analysis, and a Unified Physically-Principled Pipeline**

备选：

**Understanding and Exploiting BLE Channel Sounding for Contactless Breathing Sensing**

---

## 2. Novelty Claim（根据用户反馈重新整理）

本文的三个核心贡献：

### C1: 首次全面分析 BLE CS 在呼吸感知中的理论机制

- 对 BLE CS 的双向测量、PCT 相位抵消、逐 tone 顺序采样等机制进行系统建模
- **证明** BLE CS 的呼吸波形在频率和相位上具有独特性质：
  - (a) 信道间：符合菲涅尔区 ±1 理论，但因顺序采样存在额外连续相位结构
  - (b) 模态间：remote/local/phase 三者的相对相位完全取决于多径环境，非固定
  - (c) 低有效采样率（~2 Hz）使时域对齐不可靠，频谱域更稳健
- **区别于**：WiFi CSI 方法直接搬过来不做适配 —— BLE CS 的物理机制与 WiFi 有本质差异

### C2: 针对 BLE CS 特性提出统一管线（B3 / 正式名待定）

- 共享前端：逐模态 η·ρ Voting（质量驱动信道融合，对称对待三种模态）
- BPM 分支：三模态等权谱融合（频谱域，对时间对齐不敏感）
- 波形分支：两级 Hilbert-MRC（复平面旋转对齐，连续相位补偿，无边缘效应）
- 关键机制发现：第一级 Hilbert 连续相位是第二级模态对齐的"解锁器"

### C3: 可控场景机制验证 + 真人场景普适性验证

- **金属板场景**（CS × 3）：可控 BPM ground truth，用于 §2–§3 中验证理论机制（信道间相位关系、模态间相位对齐、消融实验）。金属板无波形 GT，BPM 实验放在机制讨论章节而非独立实验章节
- **真人场景**（HKH：3 room × 4 subject = 12）：呼吸带 ground truth，用于 §4 证明实用有效性（BPM 误差 + RMSE）

---

## 3. 论文结构大纲（修订版）

```
§1  Introduction
    1.1  Motivation
    1.2  Why BLE CS (vs WiFi CSI / FMCW radar / dedicated sensors)
    1.3  Core challenges rooted in BLE CS physics:
         (a) Bidirectional measurement → 3-variable symmetry
         (b) Low effective sampling rate (~2 Hz) → time-domain fragile
         (c) Sequential tone sampling → phase structure beyond Fresnel ±1
    1.4  Limitations of prior work (WiFi MRC / PCA-VMD directly applied to BLE CS)
    1.5  Our contributions (C1–C3 above)
    1.6  Paper organization

§2  BLE CS System Model & Mechanism Analysis                ← 核心理论贡献 C1
    2.1  BLE CS physical primer
         — CS exchange protocol, PCT multiplication, LO drift cancellation
         — 3 available observables: remote_amplitudes / local_amplitudes / phases
         — Total amplitude = remote × local (noise product → not used)
    2.2  Effective sampling rate analysis
         — BLE CS event interval ~100–200 ms → effective f_s ≈ 5–10 Hz
         — After 20 s window + 0.1–0.35 Hz bandpass → ~4 breathing cycles per window
         — Consequence: time-domain waveform alignment is unreliable
            → spectral domain preferred for BPM estimation
    2.3  Inter-tone phase relationship: Fresnel zone theory + sequential sampling
         — Review: WiFi Fresnel zone → ±1 phase relationship
         — BLE CS: theory predicts same ±1, but sequential sampling adds
           inter-tone timing offset (each tone sampled ~hundreds μs apart)
         — Experimental evidence: PCA sign correction works → confirms ±1 baseline
         — BUT: Hilbert continuous phase systematically improves → confirms
           additional phase structure beyond ±1
         [验证图 Figure 2: 同模态多 tone 对齐前后对比]
    2.4  Inter-modal phase relationship: environment-dependent
         — Remote vs local vs phase: relative phase determined by multipath geometry
         — Different rooms / different positions → relationships can flip
         — Must be estimated per-window, not hardcoded
         [验证图 Figure 3: 三模态波形对齐前后对比]
    2.5  Signal quality proxies: η and ρ
         — Definition, physical meaning, why the product η·ρ works

§3  Proposed Method: [正式名待定] Unified Pipeline             ← 核心贡献 C2
    3.1  Design rationale: why two branches sharing one front-end
    3.2  Preprocessing (shared)
    3.3  Stage 1: Per-Modal η·ρ Voting (channel fusion) [公式]
    3.4  Stage 2a: BPM Branch — 3-Modal Equal Spectrum Fusion [公式]
    3.5  Stage 2b: Waveform Branch — Two-Level Hilbert-MRC [公式]
         — Level 1: Tone-level Hilbert phase alignment + coherence gating
         — Level 2: Modal-level Hilbert phase alignment + η·γ weighting
         — Key: complex-plane rotation (≠ time shift) → no edge effects
    3.6  The "unlocking" interaction effect
         — Experimental finding: Level-2 gain depends on Level-1 being Hilbert
         — A1-D ≈ A1 (no gain from Level 2 when Level 1 is sign-only)
         — Physical interpretation: sign correction leaves residual phase errors
           that pollute the modal waveforms → Level 2 cannot recover
         [验证图 Figure 4: 解锁器效应的消融矩阵 + 示意图]

§4  Human-Subject Validation                                  ← 核心贡献 C3
    4.1  Experimental setup
         — HKH: 3 rooms × 4 subjects = 12 scenarios
         — BLE CS devices + respiratory belt ground truth
         — Metrics: BPM absolute error (breaths/min), RMSE (waveform vs belt)
    4.2  Overall BPM accuracy
    4.3  Waveform recovery accuracy (RMSE)
    4.4  Ablation experiments
         — Voting vs Single-best vs Uniform
         — Equal vs Top2 vs η-weight
         — PCA sign vs Corr sign vs Hilbert (Level 1)
         — Two-level vs single-level
    4.5  Comparison with baselines
         — WiFi MRC (Fan 2024), PCA-VMD (Zhuo 2023) migrated to BLE CS
         — BLE CS naive baselines (Single, Uniform, Modal top2)
    4.6  Per-scenario breakdown and failure analysis

§5  Discussion
    5.1  Why spectral domain beats time domain at low sampling rates
    5.2  Physical interpretation of the unlocking interaction
    5.3  Generalizability: from controlled (CS metal-plate) to real-world (HKH)
    5.4  Limitations and future work

§6  Conclusion

附录（可选）: CS 金属板三场景的完整数据作为 mechanism validation 的补充材料
```

---

## 4. 金属板 vs 真人数据的分工

| 数据 | 角色 | 所在章节 | 验证什么 |
|------|------|----------|----------|
| CS 金属板 (3 rooms) | **机制验证** | §2.3, §2.4, §3.6 | 信道间相位关系、模态间相位对齐、解锁器效应、消融实验。BPM ground truth 由脚本机械振动频率提供，精确可控。无波形 GT |
| HKH 真人 (12 scenarios) | **效果验证** | §4 | BPM 精度、波形 RMSE（vs 呼吸带）、方法普适性。有完整呼吸带 GT |

**原则**：金属板数据不出现在 §4（实验章节），而是以"mechanism validation"或"micro-benchmark"的身份出现在 §2–§3 中支撑理论论述。这样金属板缺乏波形 GT 的缺陷不会影响 §4 实验章节的完整性，而金属板高可控性的优势在 §2–§3 中最大化。

---

## 5. 图表设计方案

### 5.1 全文图表总览

| 图编号 | 内容 | 章节 | 数据来源 |
|--------|------|------|----------|
| Figure 1 | System overview（四面板：测量 + 采样率 + 管线 + 创新） | §1/§2 | 架构图（手绘/PPT） |
| Figure 2 | **Inter-tone phase: 对齐前后对比 + coherence 热力图** | §2.3 | CS 金属板单窗数据 |
| Figure 3 | **Inter-modal phase: 对齐前后对比 + 跨窗相位漂移** | §2.4 | CS 金属板单窗数据 |
| Figure 4 | **解锁器效应：消融矩阵 + 机制示意图** | §3.6 | CS 金属板三场景 |
| Figure 5 | η·ρ 分布 + Voting vs Uniform 机制对比 | §3.3 | CS 金属板单窗数据 |
| Figure 6 | BPM 主结果（HKH 12-scenario） | §4.2 | HKH validation |
| Figure 7 | 波形 RMSE + 示例 overlay（B3 vs belt） | §4.3 | HKH validation |
| Figure 8 | 消融瀑布图（cumulative contribution） | §4.4 | HKH validation |
| Figure S1 (suppl.) | Coherence (γ) 跨窗口稳定性（good vs poor tone pair） | §2.3 补充 | CS 金属板 |

**论文定稿阶段注意事项**：
- 当前已有的 `.png` 文件（见 §10 盘点清单）来自多轮独立实验，风格不统一（配色、字体、尺寸各异）
- 论文提交前，需要**统一重绘所有图**，建议用 matplotlib rcParams 全局配置或 TikZ/PGFPlots
- Figure 2–5 目前**尚未生成**——它们是新增的理论验证图，需要从 CS 金属板数据中提取窗口级数据后绘制
- Figure 6–8 的**数据已有**（HKH validation + 消融结果），但当前图风格需统一重绘

---

### 5.2 Figure 1: System + Pipeline Overview（四面板，含低采样率论证）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Figure 1: BLE CS breathing sensing — physical setup, constraints,            │
│  algorithm pipeline, and design principles                                     │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐│
│  │ (a) BLE CS measurement setup                                              ││
│  │                                                                            ││
│  │   [Device A] ◄──────── 72 tones, 72 MHz BW ────────► [Device B]          ││
│  │   (initiator)   f₁=2402, f₂=2403, ..., f₇₂=2474 MHz    (reflector)       ││
│  │       │                                                    │               ││
│  │       ▼                                                    ▼               ││
│  │   PCT multiplication → LO drift cancellation                              ││
│  │   Output: remote_amplitudes (72) / local_amplitudes (72) / phases (72)    ││
│  │                                                                           ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐│
│  │ (b) Effective sampling rate & why spectral domain for BPM                  ││
│  │                                                                            ││
│  │   BLE CS event timeline:                                                   ││
│  │   ├──ΔT──┤├──ΔT──┤├──ΔT──┤  (ΔT ≈ 100–200 ms → f_s ≈ 5–10 Hz)            ││
│  │                                                                            ││
│  │   One 20 s window ≈ only ~4 breathing cycles (f_breath ≈ 0.2 Hz):         ││
│  │     ╱╲      ╱╲      ╱╲      ╱╲                                           ││
│  │    ╱  ╲    ╱  ╲    ╱  ╲    ╱  ╲  ← time-domain alignment fragile          ││
│  │                                                                            ││
│  │   |FFT| discards timing → spectral fusion robust to misalignment           ││
│  │   → Design: BPM estimation in spectral domain (§3.4)                       ││
│  │                                                                            ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐│
│  │ (c) B3 Unified Pipeline (data flow)                                        ││
│  │                                                                            ││
│  │   216-dim CS frames → Preprocessing (median→highpass→bandpass + 20s/1s)  ││
│  │        │                                                                   ││
│  │        ▼                                                                   ││
│  │   Stage 1: Per-Modal η·ρ Voting (§3.3)  ← shared front-end                ││
│  │        72 tones → quality weights → weighted spectrum per modal            ││
│  │        → S_remote(f), S_local(f), S_phase(f) + confidence scores           ││
│  │        │                                                                   ││
│  │        ├──────────────┬──────────────────────┐                             ││
│  │        ▼              ▼                      ▼                             ││
│  │   ┌─────────────┐ ┌──────────────────────────────────┐                    ││
│  │   │ Stage 2a    │ │ Stage 2b: Waveform Branch (§3.5)  │                    ││
│  │   │ BPM (§3.4)  │ │ Two-level Hilbert-MRC             │                    ││
│  │   │ 3-modal     │ │ L1: tone align (72→1 per modal)   │                    ││
│  │   │ equal fusion│ │ L2: modal align (3→1)             │                    ││
│  │   │ → BPM       │ │ → y_final(t) breathing waveform   │                    ││
│  │   └─────────────┘ └──────────────────────────────────┘                    ││
│  │                                                                            ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐│
│  │ (d) Design principles                                                      ││
│  │                                                                            ││
│  │   ◆ Quality-driven: η·ρ per-tone per-window → no hardcoded preference     ││
│  │   ◆ Physically symmetric: remote/local/phase 1:1:1 equal treatment        ││
│  │   ◆ Continuous phase: Hilbert rotation (≠ time shift) → no edge artifacts ││
│  │   ◆ Per-window estimation: modal align adapts to multipath changes        ││
│  │                                                                            ││
│  └──────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

**变化说明**：将原来的三面板扩展为四面板，新增 panel (b) 展示低采样率约束，作为 §2.2 的可视化支撑。Panel (c) 和 (d) 分别是管线数据流和设计原则。

---

### 5.3 Figure 2: Inter-Tone Phase Relationship（§2.3 验证图）★ 新增

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Figure 2: Inter-tone phase relationship — validation of Fresnel zone theory  │
│  with BLE CS sequential sampling                                              │
│                                                                               │
│  (a) Raw bandpass-filtered waveforms from 4 representative tones             │
│      (same modal, same window)                                                │
│                                                                               │
│       Tone 12 ────╲    ╱────╲                                                │
│       Tone 38 ──────╲──╱──────╲──  (anti-phase ≈ π vs Tone 12)              │
│       Tone 55 ────╱    ╲────╱                                                │
│       Tone 71 ──────╱──╲──────╱──  (in-phase ≈ 0 vs Tone 12)                │
│       └── 20 s window ──┘                                                     │
│                                                                               │
│  (b) After PCA sign correction (±1 only)                                      │
│       ─── all 4 tones approximately aligned                                   │
│       ─── but residual misalignment visible (≠ perfect overlap)               │
│                                                                               │
│  (c) After Hilbert continuous phase alignment                                 │
│       ─── near-perfect overlap                                                │
│       ─── confirms that tone-to-tone phase relationship                        │
│           contains non-binary components (e.g., ±π/4, ±π/3)                  │
│                                                                               │
│  (d) Coherence matrix: γ_ij for all 72×72 tone pairs                          │
│       [heatmap, 72×72]                                                        │
│       ─── median γ ≈ 0.6–0.8 in cs_095806 (good scenario)                    │
│       ─── median γ ≈ 0.2–0.4 in cs_091339 (hard scenario)                     │
│                                                                               │
│  Takeaway: Fresnel ±1 is a good first approximation (PCA sign works),         │
│  but sequential sampling introduces additional continuous phase offsets        │
│  that Hilbert alignment can further compensate.                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

**数据来源**：CS 金属板数据，选择 cs_095806 的一个代表性窗口（γ 中位数高的场景）和 cs_091339 的一个窗口（γ 低的场景），同一模态（如 remote_amplitudes）。

**制作方式**：
- (a)–(c): 选 4 条 tone 的 bandpass_filtered 波形，overlay plot，三列（raw / PCA sign / Hilbert）
- (d): 72×72 coherence 热力图，2 列（good scenario / hard scenario）

**可选 inset（~10% 版面）**：Hilbert 复平面旋转 vs 时移对齐对比

```
    ┌─ Time shift ─────────┐    ┌─ Hilbert rotation ────┐
    │ x[n] → shift by Δn   │    │ z = x + jH{x}          │
    │ y[n] = x[n-Δn]       │    │ z' = z · e^{-jΔφ}      │
    │                       │    │ y = Re{z'}              │
    │ ✗ edge sample loss   │    │ ✓ all samples preserved │
    │ ✗ integer-sample err │    │ ✓ continuous phase      │
    └───────────────────────┘    └────────────────────────┘
```

此 inset 放在 Figure 2 的底部角落，用来直观解释 §3.5 中"复平面旋转 ≠ 时移"这一关键区别。

---

### 5.4 Figure 3: Inter-Modal Phase Alignment（§2.4 验证图）★ 新增

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Figure 3: Inter-modal phase relationship — environment-dependent and         │
│  resolved by per-window Hilbert alignment                                     │
│                                                                               │
│  (a) Three modal waveforms after Level-1 tone fusion, BEFORE Level-2 alignment│
│      (same window)                                                            │
│                                                                               │
│       y_remote(t) ───╲    ╱────╲                                              │
│       y_local(t)  ──────╲──╱──────╲──  (phase-shifted vs remote)             │
│       y_phase(t)  ──╱    ╲────╱        (different shift again)               │
│       └── 20 s window ──┘                                                     │
│                                                                               │
│  (b) AFTER Level-2 Hilbert alignment + η·γ weighted fusion                   │
│       ─── all 3 modal waveforms aligned                                       │
│       ─── fused waveform (bold) closely tracks the consensus                  │
│                                                                               │
│  (c) Phase difference Δφ across windows (time series)                         │
│       remote vs local:  ⌁⌁⌁ (varies slowly, range ~±π/2)                     │
│       remote vs phase:  ⌁⌁ (varies, range ~±π)                                │
│       └── confirms: phase relationships are NOT fixed → must be               │
│           per-window estimated                                                │
│                                                                               │
│  (d) Same plot for a DIFFERENT room (cs_102621)                                │
│       → different baseline Δφ, confirming environment-dependence              │
│                                                                               │
│  Takeaway: Modal-to-modal phase is non-fixed, scene-dependent,                │
│  and per-window Hilbert alignment effectively resolves it.                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

**数据来源**：CS 金属板数据，取两场景（cs_095806 和 cs_102621）的代表性 segment。

**制作方式**：
- (a)–(b): 三模态波形 overlay + 融合后波形 overlay（同一窗口两列对比）
- (c): 跨窗口相位差时间序列（x 轴 = 窗口 index，y 轴 = Δφ）
- (d): 另一场景的同款图

---

### 5.5 Figure 4: The "Unlocking" Interaction（§3.6 验证图）★ 新增

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Figure 4: The "unlocking" interaction — Level-2 modal alignment gain         │
│  depends on Level-1 providing continuous phase information                     │
│                                                                               │
│  (a) Ablation matrix (cross-domain mean BPM err %)                             │
│                                                                               │
│       Level 1 \ Level 2  │  None       │  Hilbert + η·γ       │             │
│       ───────────────────┼─────────────┼──────────────────────┤             │
│       PCA sign (±1)      │  12.33% (A0)│  11.09% (A0-D)       │             │
│                          │             │  Δ = −1.24 pp         │             │
│       ───────────────────┼─────────────┼──────────────────────┤             │
│       Corr sign (±1)     │  11.06% (A1)│  11.15% (A1-D)       │ ← 无效!     │
│                          │             │  Δ = +0.09 pp         │             │
│       ───────────────────┼─────────────┼──────────────────────┤             │
│       Hilbert continuous │  10.89% (Bγ)│   9.43% (B2-D)       │ ← 有效!     │
│                          │             │  Δ = −1.46 pp         │             │
│                                                                               │
│  (b) Schematic: Why sign correction fails to unlock Level 2                   │
│                                                                               │
│       Level-1 PCA sign (±1):                                                  │
│         Tone 1 ──► sign = +1 ──► aligned to ref                               │
│         Tone 2 ──► sign = −1 ──► flipped (correct for π)                     │
│         Tone 3 ──► sign = +1 ──► but actual Δφ = π/3 → residual error!       │
│              │                                                                 │
│              ▼                                                                 │
│         Fused modal waveform has phase distortion                              │
│              │                                                                 │
│              ▼                                                                 │
│         Level-2 Hilbert: CANNOT recover clean inter-modal phase                │
│         → A1-D ≈ A1 (no gain)                                                  │
│                                                                               │
│       Level-1 Hilbert (continuous):                                            │
│         Tone 1 ──► Δφ=0.00 rad ──► exact alignment                            │
│         Tone 2 ──► Δφ=3.14 rad ──► exact alignment (≈π)                       │
│         Tone 3 ──► Δφ=1.05 rad ──► exact alignment (π/3, not ±1!)            │
│              │                                                                 │
│              ▼                                                                 │
│         Fused modal waveform preserves phase fidelity                          │
│              │                                                                 │
│              ▼                                                                 │
│         Level-2 Hilbert: CAN recover clean inter-modal phase                   │
│         → Bγ→D: −1.46 pp gain                                                  │
│                                                                               │
│  Takeaway: Continuous phase alignment at Level 1 is a prerequisite             │
│  ("unlocker") for Level 2 to work — not because Level 1 alone helps           │
│  BPM much, but because it preserves the waveform fidelity needed              │
│  for Level 2 to operate correctly.                                             │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### 5.6 Figure 5: η·ρ Quality Voting Mechanism（§3.3 辅助图）★ 新增

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Figure 5: Why η·ρ voting outperforms uniform averaging — quality             │
│  discrimination across tones                                                  │
│                                                                               │
│  (a) Per-tone η and ρ distribution (scatter, 72 points, one window)           │
│       x = η, y = ρ                                                            │
│       ─── top-right quadrant: high-quality tones (high η, high ρ)            │
│       ─── bottom-left: noisy tones (low η or low ρ)                           │
│       ─── color = BPM error (vs consensus)                                    │
│                                                                               │
│  (b) Tonal BPM histogram                                                        │
│       ─── Uniform: all 72 tones equally weighted → broad, low-confidence peak │
│       ─── η·ρ Voting: weighted by quality → sharp, high-confidence peak       │
│                                                                               │
│  (c) Resulting per-modal spectrum comparison                                   │
│       ─── Uniform averaged spectrum: noise floor elevated                      │
│       ─── η·ρ weighted spectrum: cleaner peak, higher peak prominence         │
│                                                                               │
│  Takeaway: η identifies tones with energy concentrated in breath band;         │
│  ρ suppresses tones with sharp but spurious peaks. Product η·ρ ensures         │
│  both conditions hold simultaneously.                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### 5.7 Figure 6–8: 实验结果图（§4）

与上一版设计相同，数据来源全部改为 HKH 12 场景：

| 图 | 内容 |
|----|------|
| Figure 6 | BPM leaderboard（HKH 12-scenario aggregate）+ per-room breakdown |
| Figure 7 | RMSE leaderboard + best/worst 示例波形 overlay（B3 vs 呼吸带） |
| Figure 8 | 消融瀑布图（cumulative: Single → Uniform → Voting → +Modal equal → +Two-level Hilbert） |

---

## 6. 核心算法公式化描述 (§3.3–§3.5)

（本节内容与上一版相同，此处仅保留引用，详细信息见前一版本或代码）

### 符号约定

| 符号 | 含义 | 维度 |
|------|------|------|
| $N_t = 72$ | BLE CS tone 数量 | — |
| $m \in \{\text{rem}, \text{loc}, \text{pha}\}$ | 模态 | — |
| $\mathbf{x}_m^{(i)}[n]$ | 第 $i$ tone、模态 $m$ 的带通滤波信号 | $\mathbb{R}^{W}$ |
| $W$ | 滑窗长度 = 20 s × $f_s$ | — |
| $\eta_m^{(i)}, \rho_m^{(i)}$ | 第 $i$ tone 的能量比 / 峰度 | $\mathbb{R}^+$ |

### Stage 1: Per-Modal η·ρ Voting

$$\eta_i = \frac{\int_{f_{\text{low}}}^{f_{\text{high}}} |\hat{x}_i(f)|^2 df}{\int_0^{f_s/2} |\hat{x}_i(f)|^2 df}, \quad \rho_i = \frac{\max_{f \in B} |\hat{x}_i(f)|}{\frac{1}{|B|}\sum_{f \in B} |\hat{x}_i(f)|}$$

$$w_i = \eta_i \cdot \max(\rho_i, 0), \quad \tilde{w}_i = w_i / \sum_j w_j$$

$$H(b) = \sum_{i: \text{BPM}_i \in [b, b+\Delta)} \tilde{w}_i, \quad \text{BPM}_m^{\text{vote}} = \arg\max_b H(b)$$

$$\bar{S}_m(f_k) = \sum_{i=1}^{72} \tilde{w}_i \cdot S_i(f_k)$$

**输出**：$\bar{S}_{\text{rem}}(f), \bar{S}_{\text{loc}}(f), \bar{S}_{\text{pha}}(f)$ + 置信度 $c_m$

### Stage 2a: BPM — 3-Modal Equal Spectrum Fusion

$$S_{\text{final}}(f_k) = \frac{1}{3}\left(\bar{S}_{\text{rem}}(f_k) + \bar{S}_{\text{loc}}(f_k) + \bar{S}_{\text{pha}}(f_k)\right)$$

$$\text{BPM} = 60 \cdot \text{ParabolicInterp}(S_{\text{final}}, \arg\max_k S_{\text{final}}(f_k))$$

### Stage 2b: Waveform — Two-Level Hilbert-MRC

**Level 1**（tone 级，72→1 per modal）:

$$z_i[n] = x_i[n] + j \cdot \mathcal{H}\{x_i\}[n]$$

$$\Delta\phi_i = \arg\left(\sum_n z_i[n] \cdot z_{\text{ref}}^*[n]\right), \quad \gamma_i = \frac{|\sum z_i z_{\text{ref}}^*|}{\|z_i\| \cdot \|z_{\text{ref}}\|}$$

$$z_i'[n] = z_i[n] \cdot e^{-j\Delta\phi_i} \quad \text{(复平面旋转, 非时移)}$$

$$z_m[n] = \sum_i w_i \cdot z_i'[n], \quad w_i \propto \eta_i \cdot \max(\rho_i, 0) \cdot \gamma_i$$

$$y_m[n] = \operatorname{Re}\{z_m[n]\}, \quad \text{then standardize}$$

**Level 2**（模态级，3→1）:

$$\Delta\phi_m = \arg\left(\sum_n z_m[n] \cdot z_{\text{ref}}^*[n]\right)$$

$$\tilde{w}_m \propto \eta(y_m) \cdot \gamma_m$$

$$z_{\text{final}}[n] = \sum_m \tilde{w}_m \cdot z_m[n] \cdot e^{-j\Delta\phi_m}$$

$$y_{\text{final}}[n] = \operatorname{Re}\{z_{\text{final}}[n]\}, \quad \text{then standardize}$$

---

## 7. 论文叙事逻辑链

```
§2.1  BLE CS 物理机制
  │    PCT 向量乘法 → LO 漂移抵消 → phases 物理可用
  │    双向测量 → remote/local 物理对等
  │
  ├─► §2.2  有效采样率 ~2 Hz
  │    → 时域仅含 ~4 周期 → 频谱域更稳健
  │    → 设计决策: BPM 走谱域 [Figure 1 中体现]
  │
  ├─► §2.3  信道间相位关系 [Figure 2 验证]
  │    菲涅尔区 ±1 成立（PCA sign 有效）
  │    BUT 顺序采样引入额外连续相位（Hilbert 更进一步）
  │    → 设计决策: 信道融合用 Hilbert 而非 PCA sign
  │
  └─► §2.4  模态间相位关系 [Figure 3 验证]
        remote/local/phase 相位差场景依赖、窗口间浮动
        → 设计决策: 模态对齐 per-window、不可硬编码
        → 设计决策: 模态融合 equal 等权（不预设偏好）

§3.3-3.5  公式化管线（基于 §2 的物理约束设计）

§3.6  解锁器效应 [Figure 4 验证]
  │    Level-2 增益依赖 Level-1 连续相位
  │    Sign → Hilbert 非简单加法，而是解锁了第二级的效能
  │
  ▼
§4  HKH 真人验证 [Figures 6–8]
  │    B3 在 12 场景上 BPM 0.41 + RMSE 0.950
  │    系统性地优于 WiFi MRC、Zhuo2023 等直接迁移方法
  │
  ▼
§5  讨论：为什么谱域更好（§2.2）、为什么等权正确（§2.4 的推论）、
    为什么两级 Hilbert（§3.6 的解锁机制）
```

---

## 8. 开放式问题（更新状态）

| # | 问题 | 状态 |
|---|------|------|
| 1 | Novelty claim 的焦点 | ✅ 已确认（C1 理论建模 + C2 统一管线 + C3 双场景验证） |
| 2 | CS + HKH 是否合一篇 | ✅ 已确认（合一篇，分工：CS 在 §2–§3 做机制验证，HKH 在 §4 做效果验证） |
| 3 | Related work 是否需要深入比较 WiFi | 留待撰写 Related Work 时处理（会做细致对比） |
| 4 | 解锁器效应是否需要更深入的理论分析 | 🔓 用户将咨询他人（暂保留消融实验 + 物理直觉解释） |
| 5 | 是否需要比 RMSE 更多的波形指标 | ✅ RMSE 足够 |

---

## 9. 论文所需图表 vs 已有产出盘点

### 9.1 盘点总览

> 以下盘点基于 2026-07-18 对 `outputs/figures/`（~158 文件）、`outputs/reports/`（~108 文件）、`docs/reports/`（15 份报告）的全面审计。

| 论文图 | 用途 | 数据来源 | 现有相关文件 | 状态 |
|--------|------|----------|-------------|------|
| **Figure 1** | System overview（四面板：测量+采样率+管线+创新） | 无（架构图） | 无 | ❌ 需从零画（PPT/手绘） |
| **Figure 2a–c** | 信道间相位：4 tone 波形 overlay（raw/PCA/Hilbert） | CS 金属板单窗数据 | 无（现有图是 aggregate 结果，无单窗波形 overlay） | ❌ 需新建脚本提取数据+绘图 |
| **Figure 2d** | 72×72 coherence 热力图（good vs hard scenario） | CS 金属板 | `cross_spectrum_diag_cos_matrix.png`（互谱 cos φ 矩阵，非直接 γ 热力图） | ⚠️ 数据可算（`coherent_mrc.py` 已计算 γ），需新建绘图脚本 |
| **Figure 3a–b** | 模态间波形 overlay（对齐前/后） | CS 金属板单窗数据 | 无 | ❌ 需新建脚本 |
| **Figure 3c–d** | 跨窗口模态相位差时间序列 | CS 金属板 | 无 | ❌ 需新建脚本 |
| **Figure 4a** | 解锁器消融矩阵（3×2 表格） | CS 三场景跨域 | `b2_coherent_mrc_all_cross_domain.npy` 中有所有数值 | ⚠️ 数值已有（B2 report §6.2.5），需画成论文风格的矩阵图 |
| **Figure 4b** | 解锁器机制示意图 | 无（示意图） | 无 | ❌ 需手绘 |
| **Figure 5a** | η vs ρ 散点图（72 tone，单窗） | CS 金属板单窗数据 | 无（现有诊断图是跨窗 aggregate） | ❌ 需新建脚本 |
| **Figure 5b–c** | BPM 直方图（Voting vs Uniform）+ 融合频谱对比 | CS 金属板单窗数据 | 无 | ❌ 需新建脚本 |
| **Figure 6a** | HKH BPM leaderboard（12-scenario） | HKH 12 场景 | ✅ `ble_hkh_paper_baselines_leaderboard_all.png` | ✅ 数值完整，需统一风格重绘 |
| **Figure 6b** | HKH per-room breakdown | HKH 12 场景 | ✅ `ble_hkh_paper_baselines_by_room.png` | ✅ 数值完整，需统一风格重绘 |
| **Figure 7a** | HKH 波形 RMSE leaderboard | HKH 12 场景 | ✅ `ble_hkh_multi_subject_validation_report.md` §4.7 有全表 | ✅ 数值完整，需统一风格重绘 |
| **Figure 7b** | 示例波形 overlay（B3 vs 呼吸带, best + worst） | HKH 单场景 | ⚠️ `ble_hkh_b2_validation_room_A-sbj_A-07101613.png` 可能是波形图 | ⚠️ 需确认现有图是否包含 B3 波形 vs belt overlay |
| **Figure 8** | 消融瀑布图（cumulative contribution） | CS + HKH | ✅ `b2_coherent_mrc_waterfall_decomposition.png`（CS）、B3 report 消融数据（HKH） | ⚠️ 数值已有，需统一风格 + 合并 CS/HKH 数据 |
| **Figure S1** | Coherence γ 跨窗口稳定性（good vs poor tone pair） | CS 金属板 | 无 | ❌ 需新建脚本 |

**状态统计**：

| 状态 | 数量 | 说明 |
|------|------|------|
| ❌ 需从零生成 | **8 项** | Figure 1, 2a–c, 3a–d, 4b, 5a–c, S1 |
| ⚠️ 数据已有，需重绘 | **3 项** | Figure 2d, 4a, 7b |
| ✅ 数据+图已有，需统一风格 | **3 项** | Figure 6a–b, 8 |

### 9.2 关键已有数据文件（论文直接可用）

| 数据 | 文件 | 核心数值 |
|------|------|----------|
| B1 跨域 BPM（CS 三场景） | `systematic_fusion_cross_domain.npy` | B1 = **8.45%**（BPM err%） |
| B2-D 跨域 BPM（CS 三场景） | `b2_coherent_mrc_all_cross_domain.npy` | B2-D = 9.43%, A0-D = 11.09%, A1-D = 11.15% |
| B3 Simplified HKH 汇总 | `ble_hkh_b3_simplified_validation_summary.json` | BPM 0.405, RMSE 0.950 |
| HKH 全方法 BPM 排行榜 | `ble_hkh_paper_baselines_summary.json` | 10 方法 × 12 场景 |
| HKH 全场景逐窗 BPM + RMSE | `ble_hkh_b3_validation_summary.json` | B3 变体 × 12 场景 |
| WiFi MRC 跨域 | `wifi_mrc_baselines_cross_domain.npy` | MRC-PCA-η-equal = 10.78% |
| Zhuo2023 跨域 | `zhuo2023_pca_vmd_cross_domain.npy` | Z1 = 11.31%, Z1-no-VMD = 11.21% |
| 互谱失效诊断 | `cross_spectrum_failure_diagnosis_summary.npy` | D1–D4 诊断数据 |

### 9.3 需要新建的脚本（供 Cursor Composer 执行）

为生成 Figure 2–5 和 S1，需要一个专门的论文图生成脚本：

```
notebooks/scripts/chFusion_paper_figures_mechanism.py
```

**输入**：CS 金属板三场景的已滤波数据（可从 `multichannel_by_var` cache 加载）  
**输出**：`outputs/figures/paper_fig{2,3,4,5,s1}_*.png`

各图需要的具体数据：
- **Figure 2**: 选 cs_095806 + cs_091339 各 1 个代表性窗口 → 提取 remote_amplitudes 的 4 个 tone 的 `bandpass_filtered` 波形 → 画 raw/PCA/Hilbert 三列 overlay → 计算 72×72 γ 矩阵画热力图
- **Figure 3**: 选 cs_095806 + cs_102621 各 1 个 segment → 先跑 Level-1 Hilbert 得到三模态波形 → 画对齐前/后 overlay → 画跨窗口 Δφ 时间序列
- **Figure 4**: 从已有 `.npy` 中提取 A0/A1/Bγ/A0-D/A1-D/D 的跨域数值 → 画论文风格矩阵图 + 手绘示意图（后者用 PPT）
- **Figure 5**: 选 1 个代表性窗口 → 画 η vs ρ 散点（颜色= BPM error vs consensus）→ 画 BPM 直方图（Uniform vs Voting 叠加）→ 画融合频谱对比
- **Figure S1**: 选 2 对 tone（高 γ 和低 γ）→ 跨窗口画 γ 时间序列

---

## 10. 开源问题（更新状态）

| # | 问题 | 状态 |
|---|------|------|
| 1 | Novelty claim 的焦点 | ✅ C1 理论建模 + C2 统一管线 + C3 双场景验证 |
| 2 | CS + HKH 是否合一篇 | ✅ 合一篇：CS 在 §2–§3 做机制验证，HKH 在 §4 做效果验证 |
| 3 | Related work 是否需要深入比较 WiFi | 留待撰写 Related Work 时处理 |
| 4 | 解锁器效应是否需要更深入的理论分析 | 🔓 用户将咨询他人 |
| 5 | 是否需要比 RMSE 更多的波形指标 | ✅ RMSE 足够 |

---

## 11. 后续行动

1. **用户确认** Figure 2–5 的设计是否符合预期（是否需要调整）
2. **生成 Figure 2–5 的实际数据图**（由 Cursor Composer 执行脚本，从 CS 金属板数据中提取代表性子窗口，画对齐前后对比、coherence 热力图、相位差时间序列）
3. **撰写论文初稿 §1–§3**（Claude/DeepSeek，进入 Achievement Report Mode 或直接撰写）
4. **确定方法正式名称**（替代 "B3" 代号，建议格式：{描述性前缀}-{技术关键词}，如 "UniBreath" 或 "BLE-CS-Fusion"）
