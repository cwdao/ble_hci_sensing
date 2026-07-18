# Breathing Sensing via BLE Channel Sounding: System Modeling and a Unified Physically-Principled Pipeline

# 基于 BLE 信道探测的呼吸感知：系统建模与物理驱动统一管线

> **DRAFT v0.2** — 骨架稿，每节仅写核心句子。先英后中。细节由用户补充。  
> **日期**：2026-07-18

---

## Abstract / 摘要

**EN**: We present the first systematic analysis of BLE Channel Sounding (CS) for contactless breathing sensing. Through modeling the bidirectional measurement mechanism, we identify three key physical constraints: (1) symmetric remote/local observables from mutual PCT exchange, (2) an effective sampling rate of ~2 Hz that makes time-domain alignment fragile, and (3) sequential tone sampling that introduces continuous phase offsets beyond the Fresnel-zone ±1 relationship known from WiFi CSI. We propose [Name TBD], a unified pipeline that addresses all three constraints: a shared per-modal η·ρ voting front-end for quality-driven channel fusion, a spectral-domain branch for robust BPM estimation via equal-weight modal fusion, and a two-level Hilbert-MRC branch for breathing waveform recovery via continuous phase alignment in the complex plane. We discover a critical "unlocking" interaction: continuous phase alignment at the tone level is a prerequisite for effective modal-level alignment—±1 sign correction alone eliminates this gain entirely. Validation on three controlled metal-plate scenarios and twelve human-subject scenarios (3 rooms × 4 subjects) with respiratory belt ground truth shows that [Name TBD] achieves 0.41 breaths/min BPM error and 0.950 RMSE against belt reference, outperforming WiFi MRC and PCA-VMD baselines migrated to BLE CS.

**CN**: 本文首次系统性地分析了 BLE 信道探测（Channel Sounding, CS）在非接触式呼吸感知中的理论机制。通过对双向测量机制的建模，我们识别出三个关键物理约束：(1) PCT 互相交换导致 remote/local 观测量物理对等；(2) ~2 Hz 的有效采样率使时域对齐不可靠；(3) 逐 tone 顺序采样引入了超越 WiFi CSI 菲涅尔区 ±1 关系的连续相位偏移。我们提出了 [名称待定]，一个统一管线来应对这三个约束：共享前端用逐模态 η·ρ 投票实现质量驱动的信道融合；频谱域分支通过等权模态融合稳健估计 BPM；时域分支通过复平面连续相位对齐（两级 Hilbert-MRC）重建呼吸波形。我们发现了一个关键的"解锁器"交互效应：tone 级的连续相位对齐是模态级对齐发挥作用的必要前提——仅使用 ±1 符号校正会完全消除这一增益。在三个可控金属板场景和十二个真人场景（3 房间 × 4 受试者，呼吸带 ground truth）上的验证表明，[名称待定] 的 BPM 误差为 0.41 breaths/min，波形 RMSE 为 0.950（vs 呼吸带），优于迁移到 BLE CS 的 WiFi MRC 和 PCA-VMD baseline。

---

## 1. Introduction / 引言

**EN—Motivation**: Contactless breathing sensing enables health monitoring without wearable devices. BLE CS, standardized in Bluetooth 5.2, offers a unique opportunity: it is ubiquitous (every smartphone), privacy-preserving (on-device), and provides 72-tone channel measurements across 72 MHz bandwidth.

**CN—动机**: 非接触式呼吸感知使无需穿戴设备的健康监测成为可能。BLE CS（Bluetooth 5.2 标准）提供了一个独特的机会：它无处不在（每部智能手机）、保护隐私（端侧处理）、并提供跨 72 MHz 带宽的 72 tone 信道测量。

**EN—Gap**: Prior work on wireless breathing sensing has focused on WiFi CSI or FMCW radar. BLE CS differs in three fundamental ways that demand a dedicated approach: [list three constraints briefly].

**CN—研究空白**: 现有的无线呼吸感知工作主要集中在 WiFi CSI 或 FMCW 雷达上。BLE CS 在三个根本方面有所不同，需要一个专门的方法：[简述三个物理约束]。

**EN—Contributions**: (C1) First comprehensive modeling of BLE CS for breathing sensing, identifying and experimentally validating three physical constraints. (C2) [Name TBD] unified pipeline addressing all three constraints. (C3) Validation on both controlled and real-world scenarios.

**CN—贡献**: (C1) 首次全面建模 BLE CS 用于呼吸感知的理论机制，识别并实验验证了三个物理约束。(C2) [名称待定] 统一管线，应对全部三个约束。(C3) 在可控场景和真实场景上的双重验证。

---

## 2. Background and System Model / 背景与系统模型

### 2.1 BLE CS Physical Primer / BLE CS 物理基础

**EN**: [Brief description of CS exchange, PCT multiplication, LO drift cancellation. Why remote_amplitudes, local_amplitudes, and phases are the three usable observables. Why total amplitude is not used.]

**CN**: [简述 CS 交换过程、PCT 乘法、LO 漂移抵消。为什么 remote_amplitudes、local_amplitudes、phases 是三个可用观测量。为什么 total amplitude 不可用（双方噪声乘积，无独立物理意义）。]

### 2.2 Effective Sampling Rate and Its Consequences / 有效采样率及其影响

**EN**: BLE CS events occur at ~100–200 ms intervals. After bandpass filtering (0.1–0.35 Hz) and 20-second windowing, each window contains only ~4 breathing cycles. This makes time-domain waveform alignment intrinsically unreliable—a small timing offset between two channels translates to a large relative phase error across only 4 cycles. The spectral domain (|FFT|) discards timing information and is therefore the natural choice for frequency estimation.

**CN**: BLE CS 事件的间隔约为 100–200 ms。经带通滤波（0.1–0.35 Hz）和 20 秒滑窗后，每个窗口仅包含约 4 个呼吸周期。这使得时域波形对齐在本质上不可靠——两个信道之间的微小时间偏移会在仅 4 个周期上转化为较大的相对相位误差。频谱域（|FFT|）丢弃了时间信息，因此是频率估计的自然选择。

### 2.3 Inter-Tone Phase Relationship / 信道间（Tone 间）相位关系

**EN**: [Fresnel zone theory review. Applicability to BLE CS. PCA sign correction works → confirms ±1 baseline. But Hilbert continuous phase further improves → confirms additional structure from sequential sampling. Cite Figure 2.]

**CN**: [回顾菲涅尔区理论。在 BLE CS 中的适用性论证。PCA 符号校正有效 → 确认 ±1 基线成立。但 Hilbert 连续相位补偿进一步改善 → 确认顺序采样引入了超越 ±1 的额外相位结构。引用 Figure 2。]

### 2.4 Inter-Modal Phase Relationship / 模态间（变量间）相位关系

**EN**: [Remote vs local vs phase: relative phase depends on multipath geometry. Different rooms → different relationships. Per-window variation observed. Cannot hardcode. Cite Figure 3.]

**CN**: [Remote 与 local 与 phase 之间：相对相位取决于多径几何。不同房间 → 不同的相位关系。观察到逐窗变化。不可硬编码。引用 Figure 3。]

### 2.5 Signal Quality Proxies: η and ρ / 信号质量指标：η 与 ρ

**EN**: [Definition. Why product. How they complement each other.]

**CN**: [η（呼吸频段能量比）和 ρ（谱峰峰度）的定义。为什么使用乘积 η·ρ 而非单一指标。两者如何互补：η 要求能量集中在呼吸频段，ρ 抑制假峰 tone。缺一不可。]

---

## 3. Proposed Method: [Name TBD] / 提出方法：[名称待定]

### 3.1 Design Rationale / 设计动机

**EN**: [Why two branches sharing one front-end. BPM → spectral domain (insensitive to misalignment). Waveform → time domain (preserves morphology). Both benefit from η·ρ quality weights.]

**CN**: [为什么两支共享一个前端。BPM → 频谱域（对时间对齐不敏感）。波形 → 时域（保留呼吸形态学特征）。η·ρ 质量权重对两支都有益。]

### 3.2 Preprocessing / 预处理

**EN**: [Filter chain. Sliding window parameters.]

**CN**: [滤波链：median → highpass (0.05 Hz) → bandpass (0.1–0.35 Hz)。滑窗：20 s 窗长 / 1 s 步长。]

### 3.3 Stage 1: Per-Modal η·ρ Voting / 第一阶段：逐模态 η·ρ 投票

**EN**: [Formulas from paper_outline_plan §3.3. η_i, ρ_i, w_i, weighted histogram, confidence-weighted spectrum average S̄_m(f).]

**CN**: [公式见 paper_outline_plan.md §3.3。逐 tone 计算 η_i, ρ_i → 质量权重 w_i = η_i·max(ρ_i, 0) → 加权直方图投票 BPM → 置信度加权频谱平均 S̄_m(f)。]

### 3.4 Stage 2a: BPM Branch — Equal Spectrum Fusion / BPM 分支：等权谱融合

**EN**: [Formula: S_final = (S_remote + S_local + S_phase) / 3. Argmax + parabolic interpolation. Why equal weight: physical symmetry argument.]

**CN**: [公式：S_final(f) = (S_remote(f) + S_local(f) + S_phase(f)) / 3。寻峰 + 抛物线插值。为什么等权：remote/local/phases 物理对等，不应预设哪一模态更优。实验证据：Equal (B1, 8.45%) 优于 Top2 (B3, 9.92%) 和 η-weight (B2, 9.45%)。]

### 3.5 Stage 2b: Waveform Branch — Two-Level Hilbert-MRC / 波形分支：两级 Hilbert-MRC

**EN**: [Level 1 formulas: Hilbert transform → analytic signal → cross-correlation phase → complex-plane rotation → weighted sum → real part. Level 2 formulas: same structure but across modals. Why complex-plane rotation ≠ time shift: no edge effects, continuous phase resolution.]

**CN**: [Level 1（tone 级，72→1/模态）：Hilbert 变换 → 解析信号 → 互相关求相位差 → 复平面旋转（z' = z·e^{−jΔφ}）→ η·ρ·γ 加权叠加 → 取实部。Level 2（模态级，3→1）：同上结构，跨 remote/local/phase 执行。为什么复平面旋转 ≠ 时域平移：无边缘效应、保留所有样本、连续相位分辨率。]

### 3.6 The "Unlocking" Interaction / "解锁器"交互效应

**EN**: [Experimental finding: A1-D ≈ A1 (no gain), Bγ→D = −1.46 pp (significant gain). Physical interpretation: sign correction leaves residual phase errors that pollute modal waveforms; Level-2 cannot recover from degraded input. Continuous phase at Level 1 preserves waveform fidelity → unlocks Level-2 gain. Cite Figure 4.]

**CN**: [实验发现：A1-D ≈ A1（Level-2 在符号校正第一级上无增益），Bγ→D = −1.46 pp（Level-2 在 Hilbert 第一级上有效）。物理解释：符号校正（±1）残留的非二值相位误差污染了模态融合波形；Level-2 无法从已被污染的输入中恢复。Level-1 连续相位保留了波形保真度 → "解锁" Level-2 的 −1.46 pp 增益。引用 Figure 4。]

---

## 4. Experimental Validation / 实验验证

### 4.1 Setup / 实验设置

**EN**: [CS metal-plate: 3 rooms, mechanical BPM ground truth. HKH: 3 rooms × 4 subjects, respiratory belt ground truth. Metrics: BPM absolute error, RMSE. Baseline methods listed.]

**CN**: [CS 金属板：3 个房间，机械振动 BPM ground truth（可控、精确，但无波形 GT）。用于 §2–§3 的机制验证。HKH 真人：3 房间 × 4 受试者 = 12 条数据，呼吸带 ground truth。用于 §4 的效果验证。指标：BPM 绝对误差（breaths/min）、RMSE（波形 vs 呼吸带）。Baseline：B0 Single Remote, B1 Uniform Remote, Modal top2, T0-V3 Per-Tone Voting, WiFi MRC (Fan 2024), Zhuo2023 PCA-VMD。]

### 4.2 BPM Accuracy (HKH) / BPM 精度（HKH）

**EN**: [Table: B1=0.41, Z1=0.44, etc. Cite Figure 6.]

**CN**: [主结果表：B1 Uniform Remote (0.37) ≈ B3 Vote→Top2 (0.38) > B3 Simplified = B1 Vote→Equal (0.41) > Z1 (0.44) > B2-D (0.68) > Fan (1.39)。引用 Figure 6。]

### 4.3 Waveform Recovery Accuracy (HKH) / 波形恢复精度（HKH）

**EN**: [B3 RMSE=0.950 vs belt. Cite Figure 7.]

**CN**: [B3 Simplified RMSE = 0.950（vs 呼吸带），B2-D 同值。Z1 RMSE = 1.070。B3 是唯一同时输出最优 BPM (0.41) 和最优波形 (0.950) 的统一管线。引用 Figure 7。]

### 4.4 Ablation Experiments / 消融实验

**EN**: [Channel fusion: Voting > Single-best > Uniform. Modal fusion: Equal > Top2 > η-weight. Phase method: Hilbert two-level > single-level > sign-only. Cite Figure 8.]

**CN**: [信道融合消融：Voting (η·ρ 加权) > Single-best (max-η) > Uniform (等权)。模态融合消融：Equal (1:1:1) > Top2 > η-weight → 对称对待被验证。相位方法消融：Hilbert 两级 > Hilbert 单级 > Corr sign > PCA sign。解锁器交互效应（§3.6）进一步证实第一级 Hilbert 的逻辑必要性。引用 Figure 8。]

### 4.5 Mechanism Validation (CS Metal-Plate) / 机制验证（CS 金属板）

**EN**: [Inter-tone phase (Figure 2). Inter-modal phase (Figure 3). Unlocking interaction (Figure 4). Quality voting (Figure 5).]

**CN**: [信道间相位：PCA sign 有效但不完美，Hilbert 连续相位进一步改善（Figure 2）。模态间相位：三模态相位差场景依赖、逐窗浮动，per-window Hilbert 对齐有效解决（Figure 3）。解锁器效应：Level-2 增益依赖 Level-1 连续相位——符号校正 + Level-2 = 无增益，Hilbert + Level-2 = −1.46 pp（Figure 4）。η·ρ Voting 机制：质量加权直方图的峰值比等权直方图更尖锐、融合频谱噪声更低（Figure 5）。]

### 4.6 Comparison with Prior Work / 与现有工作的比较

**EN**: [WiFi MRC: 10.78%. Zhuo2023: 11.31%. B1: 8.45%. B3 on HKH: 0.41 BPM + 0.950 RMSE.]

**CN**: [CS 金属板跨域：B1 (8.45%) < WiFi MRC (10.78%) < Zhuo2023 (11.31%)。B1 在 BPM 精度上系统性优于迁移到 BLE CS 的 WiFi 时域 MRC 方法。HKH 真人：B3 Simplified (0.41 BPM + 0.950 RMSE) 是唯一同时最优的统一管线。]

---

## 5. Discussion / 讨论

**EN**: [Why spectral domain beats time domain at low sampling rates. Why equal weight is correct. Physical interpretation of unlocking effect. Limitations: complex multipath (091339), sequential sampling timing analysis [待确认]. Future: multi-person, apnea detection, dynamic branch selection.]

**CN**: [为什么频谱域在低采样率下优于时域：20 s 窗口仅含 ~4 周期，时域对齐的相位估计方差大；|FFT| 丢弃时间信息后对对齐不敏感。为什么等权是正确的：remote/local/phases 物理对等，预设偏好反而引入场景过拟合。解锁器效应的物理含义：连续相位保真度从前端传递到后端的信息论解释 [待确认]。不足：复杂多径（cs_091339）是全局瓶颈，tone 间相干性系统性偏低；顺序采样的精确时序分析仍需进一步工作。未来方向：多人呼吸、呼吸暂停检测、per-window 动态分支选择（根据当前窗口的信号质量在 BPM 和波形分支间自适应切换）。]

---

## 6. Conclusion / 结论

**EN**: [One paragraph summary. Reiterate three contributions.]

**CN**: [一段话总结全文。重述三个贡献：(C1) 首次系统建模 BLE CS 在呼吸感知中的物理机制，识别并验证了三个关键物理约束；(C2) 提出了 [名称待定] 统一管线，用 η·ρ Voting + 等权谱融合 + 两级 Hilbert-MRC 分别应对这些约束；(C3) 在可控金属板场景和真人数据上完成了双重验证，B3 实现了 0.41 BPM + 0.950 RMSE，优于直接迁移的 WiFi 方法。]

---

## References / 参考文献

**EN**: [TBD — WiFi Fresnel zone papers (Wang et al. MobiCom, Zhang et al. MobiSys), Fan 2024, Yu 2021 WiFi-Sleep, Zhuo 2023 PCA-VMD, BLE CS spec (Bluetooth 5.2), etc.]

**CN**: [待补充 — 菲涅尔区 WiFi 感知论文、Fan 2024、Yu 2021 WiFi-Sleep、Zhuo 2023、BLE 5.2 信道探测规范等。]
