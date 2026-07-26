# BreatheCS: Spectral Fusion and Coherent Waveform Reconstruction for Contactless Respiration Sensing with Bidirectional Bluetooth Channel Sounding

# BreatheCS：融合双向 BLE 信道探测测量的非接触式呼吸感知——频谱融合与相干波形重建

> **DRAFT v0.4** — 根据 5.6sol 建议重定位：论文主线从"Phase 零陷填充"转向"BLE CS 不是低采样率 WiFi CSI——双向 PCT 观测结构需要不同的融合原则"。Abstract/Introduction/Related Work/Conclusion 全面重写。  
> **日期**：2026-07-26  
> **上版**：v0.3 (2026-07-18)  
> **配图状态**：Fig 2 ✅ | Fig 3 ✅ | Fig 4 ❌ | Fig 5 ✅ | Fig 6 ✅ | Fig 7 ✅ | Fig 8 ✅ | Fig S1 ✅ | Fig 1 ❌  
> **⚠️ 条件性内容**：本文档多个段落的最终措辞取决于尚未完成的实验。详见 [`docs/plans/paper_experiment_dependencies_plan.md`](paper_experiment_dependencies_plan.md)。标有 `[⚠️ D1]`–`[⚠️ D7]` 的段落表示内容取决于对应实验的结果。

---

## Abstract / 摘要

**EN**: Bluetooth Channel Sounding (CS), introduced in Bluetooth Core 6.0, exposes multi-frequency bidirectional measurements that create a new opportunity for contactless respiration sensing on energy-efficient BLE devices. However, CS differs fundamentally from WiFi CSI: it provides two endpoint amplitude observations and a composite-phase observation from reciprocal PCT exchange, operates at a sparse practical event rate of 2–4 Hz, and exhibits frequency- and scene-dependent phase relationships that make direct migration of conventional CSI fusion unreliable. We present BreatheCS, a measurement-aware framework that models these properties and separates respiratory-rate estimation from waveform recovery into distinct processing branches. A shared front-end evaluates per-tone quality via complementary spectral metrics (energy concentration $\eta$ and peak prominence $\rho$). The BPM branch fuses quality-weighted magnitude spectra for timing-robust frequency estimation, while the waveform branch performs two-level complex-domain alignment to reconstruct a coherent respiratory waveform. We evaluate BreatheCS on three controlled mechanical-motion settings and 12 human-subject recordings across three indoor environments using a respiratory belt reference. BreatheCS achieves a mean absolute BPM error of 0.405 breaths/min and a normalized waveform RMSE of 0.951. Ablation experiments reveal that tone diversity is the dominant and most consistent source of improvement (1.640 → 0.381 BPM), while the benefit of modal diversity—particularly composite phase—is conditional rather than universal. These results establish measurement-aware fusion principles for physiological sensing with Bluetooth Channel Sounding.

**CN**: 蓝牙信道探测（Channel Sounding, CS）是 Bluetooth Core 6.0 引入的标准功能，其多频点双向测量为低功耗 BLE 设备上的非接触呼吸感知创造了新机遇。然而，BLE CS 与 WiFi CSI 存在根本性区别：CS 通过互易 PCT 交换提供两个端侧幅值观测和一个组合相位观测，实际事件率仅为 2–4 Hz，且 tone 间和模态间的相位关系随频率和场景连续变化，使传统 CSI 融合方法难以直接迁移。本文提出 BreatheCS，一个测量感知的呼吸感知框架：首先建模双向 PCT 观测的呼吸扰动，刻画 tone 间及模态间的连续相位关系；随后设计共享的质量驱动信道融合前端，将呼吸率估计与波形恢复分解为谱域分支和复平面相干分支。谱域分支融合质量加权幅度谱实现稳健 BPM 估计；波形分支通过两级复平面对齐重建连贯的呼吸波形。在三个可控金属板场景和十二个真人场景（3 房间 × 4 受试者，呼吸带 ground truth）上的实验表明，BreatheCS 的 BPM 平均绝对误差为 0.405 breaths/min，归一化波形 RMSE 为 0.951，在联合 BPM-波形性能上优于迁移自 WiFi 的 PCA、MRC 和 PCA-VMD baseline。消融实验揭示了一个关键的层级关系：tone diversity 是最稳定、最大的增益来源（1.640 → 0.381 BPM），而 modal diversity——特别是组合相位的增益——是条件性的，取决于场景和信号质量。这些发现为基于 BLE 信道探测的生理感知建立了测量感知的融合原则。

---

## 1. Introduction / 引言

### 1.1 问题与应用价值

Respiration is a fundamental physiological indicator for sleep monitoring, chronic disease management, and early detection of respiratory abnormalities. Conventional monitoring solutions typically require wearable belts, electrodes, or dedicated radar hardware, which can limit comfort and long-term deployment. Device-free sensing using commodity wireless signals offers an attractive alternative because it can capture respiration-induced channel variations without requiring the user to wear a sensor.

呼吸是睡眠监测、慢病管理和呼吸异常早期检测的基础生理指标。传统监测方案通常需要穿戴式绑带、电极或专用雷达硬件，在舒适性和长期部署上存在限制。使用商用无线信号的非接触式感知提供了一种有吸引力的替代方案——无需佩戴传感器即可捕获呼吸引起的信道变化。

### 1.2 为什么 BLE Channel Sounding 值得研究？

BLE is widely deployed, and Channel Sounding (CS) is becoming available in a new generation of Bluetooth Core 6.0-capable chipsets. CS was designed for secure fine ranging via Phase-Based Ranging (PBR) and Round-Trip Timing (RTT), but it simultaneously exposes bidirectional phase-related measurements over up to 72 RF channels—creating a new opportunity for device-free sensing on energy-efficient BLE platforms. However, CS was designed for ranging rather than physiological sensing, and its measurement structure differs substantially from the WiFi CSI commonly used in prior respiration systems.

BLE 已广泛部署，Channel Sounding（CS）正在新一代支持 Bluetooth Core 6.0 的芯片组中可用。CS 本为通过基于相位的测距（PBR）和往返时间（RTT）实现安全的精细测距而设计，但它同时暴露了跨多达 72 个 RF 信道的双向相位相关测量——这为低功耗 BLE 平台上的非接触式感知创造了新机遇。然而，CS 是为测距而非生理感知设计的，其测量结构与现有呼吸感知系统中常用的 WiFi CSI 存在根本差异。

### 1.3 为什么 WiFi 方法不能直接迁移？

Directly migrating WiFi respiration pipelines to BLE CS is problematic for three reasons:

**Difference 1: Observable structure.** WiFi typically provides single-ended complex CSI or antenna/subcarrier ratios. BLE CS produces two endpoint PCT measurements from a reciprocal bidirectional exchange. After combining them to suppress local-oscillator offsets, we obtain two endpoint amplitude observables (`remote_amplitudes`, `local_amplitudes`) and one composite-phase observable (`phases`). These three observables represent different complex-plane projections of the same channel perturbation rather than independent propagation paths.

**Difference 2: Sampling conditions.** A BLE CS event typically completes in 250–500 ms, yielding an effective rate of 2–4 Hz. In a 20-second sliding window at this rate, only 2–7 respiratory cycles (at 0.1–0.35 Hz) are available, with uncertain and potentially uneven inter-event intervals. Short-window temporal alignment is therefore sensitive to timing irregularity, noise, and non-stationary motion—more so than in typical WiFi CSI streams.

**Difference 3: Inter-tone and inter-modal phase relationships.** Frequency-selective multipath and implementation non-idealities produce continuous, scene-dependent phase offsets across tones and across observation modalities (remote/local/phase). These offsets go beyond the binary in-phase/anti-phase (±1) relationship commonly assumed in WiFi Fresnel-zone models. Many existing fusion methods (PCA sign correction, MRC with fixed reference) assume only a binary relationship and are therefore insufficient.

直接将 WiFi 呼吸感知管线迁移到 BLE CS 存在三个问题：

**区别 1：观测结构。** WiFi 通常提供单向复 CSI 或天线/子载波比值。BLE CS 通过互易双向交换产生两个端侧 PCT 测量。将它们组合以抵消本振偏置后，我们获得两个端侧幅值观测量（remote_amplitudes、local_amplitudes）和一个组合相位观测量（phases）。这三个观测量代表同一信道扰动在复平面上的不同投影方向，而非独立的传播路径。

**区别 2：采样条件。** BLE CS 事件通常在 250–500 ms 内完成，有效速率 2–4 Hz。在此速率下的 20 秒滑窗中，仅有 2–7 个呼吸周期（0.1–0.35 Hz），且事件间隔可能不均匀。短窗时域对齐因此对时序误差、噪声和非平稳运动更敏感——比典型 WiFi CSI 数据流更脆弱。

**区别 3：Tone 间与模态间的相位关系。** 频率选择性多径和实现非理想性导致 tone 间和观测模态间（remote/local/phase）产生连续、场景依赖的相位偏移。这些偏移超越了 WiFi 菲涅尔区模型中通常假设的二值同相/反相（±1）关系。许多现有融合方法（PCA 符号校正、固定参考 MRC）仅假设二值关系，因而不充分。

### 1.4 关键实验洞察

Our measurements lead to three design insights:

1. **Tone diversity is the dominant gain.** Reliable tone aggregation provides the largest and most consistent improvement because individual CS tones exhibit strongly varying respiration sensitivity (single-tone BPM error 1.640 → channel-fused 0.381 BPM). No single tone or small subset of tones is consistently reliable across scenes.

2. **Respiratory rate and waveform require different fusion domains.** Magnitude spectra discard timing information and are therefore robust to residual temporal offsets between tones—making them ideal for BPM estimation. Waveform recovery, in contrast, requires coherent phase alignment to preserve morphological features. Forcing a single fusion mechanism to serve both objectives degrades at least one of them.

3. **Modal diversity is conditional, not universal.** Remote and local amplitudes are physically symmetric but not always equally reliable in every window. Composite phase, in particular, behaves differently between controlled mechanical motion and human respiration—its benefit is scene- and quality-dependent. Equal-weight three-modal fusion is a bias-free baseline but not necessarily the optimal strategy for every window. [⚠️ D2, D3: 互补投影证据和 Phase gate 结果决定此 insight 的措辞强弱]

我们的测量产生了三条设计洞察：

1. **Tone diversity 是主要增益。** 可靠的 tone 聚合提供了最大且最稳定的改进，因为各 CS tone 的呼吸灵敏度差异显著（单 tone BPM 误差 1.640 → 信道融合 0.381 BPM）。没有任何单一 tone 或少量 tone 子集在所有场景中持续可靠。

2. **呼吸率和波形需要不同的融合域。** 幅度谱丢弃了时间信息，因此对 tone 间的残余时间偏移稳健——适合 BPM 估计。波形恢复则需要相干相位对齐以保留形态学特征。强迫同一融合机制同时服务两个目标会至少损害其中一个。

3. **模态 diversity 是条件性的。** Remote 和 Local 幅值物理对等，但并非在每个窗口中都同等可靠。特别是组合相位，在可控机械运动和人体呼吸之间表现显著不同——其增益是场景和信号质量依赖的。等权三模态融合是一个无偏基线，但不一定是每个窗口的最优策略。

### 1.5 方法概述

Guided by these insights, we design BreatheCS, a measurement-aware dual-branch pipeline. A shared front-end evaluates the respiratory relevance of each tone using complementary spectral metrics ($\eta$ for energy concentration, $\rho$ for peak prominence). The BPM branch fuses quality-weighted magnitude spectra across tones and observables for timing-robust respiratory-rate estimation. In parallel, the waveform branch represents each band-limited signal as an analytic signal and performs hierarchical complex-domain alignment—first across tones within each observable, then across observables—to reconstruct a coherent respiratory waveform.

基于这些洞察，我们设计了 BreatheCS，一个测量感知的双分支管线。共享前端使用互补的频谱指标（$\eta$ 衡量能量集中度，$\rho$ 衡量峰值主导度）评估每个 tone 的呼吸相关性。BPM 分支融合质量加权的幅度谱，实现时序稳健的呼吸率估计。波形分支将每个带限信号表示为解析信号，并执行分层复平面对齐——先在每个观测量内部跨 tone 对齐，再跨观测量对齐——从而重建连贯的呼吸波形。

### 1.6 贡献

This paper makes the following contributions:

1. **BLE CS respiration observation model and empirical characterization.** We formulate the bidirectional PCT measurements as two endpoint amplitude observables and one composite-phase observable, and characterize their complex-plane sensitivities, inter-tone relationships, and scene-dependent inter-modal phase offsets. Our analysis reveals why BLE CS respiration sensing cannot be treated as a direct low-rate migration of WiFi CSI sensing.

2. **A task-oriented dual-branch sensing pipeline.** We develop BreatheCS, which shares a quality-aware tone fusion front-end but separates respiratory-rate estimation from waveform recovery. The spectral branch aggregates reliable tone spectra for timing-robust BPM estimation, whereas the waveform branch performs hierarchical complex-domain alignment for coherent waveform reconstruction.

3. **Controlled and human-subject evaluation with actionable design findings.** We evaluate BreatheCS on controlled mechanical-motion experiments and 12 human-subject recordings with respiratory-belt references. The results quantify the dominant benefit of tone diversity, demonstrate the different fusion requirements of BPM and waveform recovery, and reveal that modal diversity—especially composite phase—is beneficial only under scene- and quality-dependent conditions.

本文做出以下贡献：

1. **BLE CS 呼吸观测建模与实证刻画。** 建立双向 PCT 呼吸观测模型，将可用测量表示为两个端侧幅值观测与一个组合相位观测，并分析其复平面灵敏度、tone 间关系以及场景相关的模态间相位关系，说明 BLE CS 呼吸感知不能被简单视为低采样率 WiFi CSI 感知。

2. **面向不同感知目标的双分支管线。** 提出 BreatheCS，共享质量驱动的 tone 融合前端，但分别针对呼吸率和呼吸波形设计谱域分支与复平面相干分支，从而避免用同一种融合机制同时承担两个不同目标。

3. **受控目标与真人呼吸的系统评估与设计结论。** 通过机械运动目标和带呼吸带参考的真人实验，量化 tone diversity、modal diversity、谱域融合与相干融合的贡献，并揭示 tone 融合是最稳定的增益来源，而模态融合、特别是组合相位的增益具有明显条件性。

### 中心论点

The central thesis connecting all sections of this paper is:

> **BLE CS is not simply WiFi CSI sampled at a lower rate; its bidirectional measurement structure, sparse event sampling, and frequency-dependent phase relationships require task-specific fusion for respiratory rate and waveform sensing.**

贯穿全文的中心论点：

> **BLE CS 并不是低采样率版本的 WiFi CSI：其双向 PCT 观测结构、稀疏事件采样及频率相关的连续相位关系，使呼吸率估计和波形恢复需要不同的融合原则。**

## 2. Related Work

Related work spans three areas: contactless respiration sensing, WiFi CSI modeling and multi-channel fusion, and Bluetooth sensing with Channel Sounding. We organize by theme rather than by paper, and highlight what is missing for BLE CS.

### 2.1 Contactless Respiration Sensing

| Technology | Strengths | Key difference from this work |
|---|---|---|
| FMCW/UWB Radar | High sampling rate, range resolution | Requires dedicated hardware |
| WiFi CSI | Many subcarriers, typically higher sampling rate | Different measurement primitive (single-ended CSI vs bidirectional PCT) |
| BLE RSSI | Low power, ubiquitous | Only coarse-grained signal strength |
| BLE CS | Bidirectional, multi-frequency, phase-capable | New measurement structure; respiration sensing uncharacterized |

Prior respiration sensing systems have been dominated by WiFi CSI and radar. Their signal models and fusion assumptions do not directly describe the bidirectional PCT observations exposed by BLE CS.

> **Gap**: Existing respiration systems are built on measurement primitives (CSI, RSSI, radar IF) that differ fundamentally from BLE CS's reciprocal PCT structure. Their fusion strategies do not account for the specific tone-modal relationships we characterize here.

### 2.2 WiFi CSI Modeling and Multi-Channel Fusion

**Fresnel-zone and multipath modeling.** Respiration-induced path-length variation causes periodic channel changes. Amplitude and phase sensitivity depend on the multipath operating point—different subcarriers or links exhibit different sensitivity to the same physical motion. This body of work establishes the theoretical basis for multi-channel respiration sensing, but the models assume single-ended CSI rather than bidirectional PCT.

**Amplitude–phase complementarity.** FullBreathe (Zhang et al.) exploits the orthogonal complementarity between CSI amplitude and phase to mitigate blind spots; FarSense uses dual-antenna CSI ratios to relieve phase bias and jointly exploit amplitude and phase information to extend sensing range. These works demonstrate that amplitude and phase can have complementary rather than redundant information. However, in these methods, amplitude and phase typically come from the same WiFi CSI or antenna ratio. In BLE CS, Remote/Local amplitudes and composite Phase arise from bidirectional PCT exchange and represent different complex-plane projections—not directly comparable to WiFi's amplitude/phase decomposition. Moreover, FullBreathe itself notes that standalone amplitude or phase can both have blind spots; their value lies in complementarity, not in phase being universally blind-spot-free.

**Subcarrier/link fusion and signal decomposition.** PCA/SVD-based methods extract the dominant respiratory component across subcarriers. MRC assigns weights proportional to channel quality. VMD/EMD decompose signals into modes for respiratory component selection. Position-Free Breath Detection (Zhuo et al.) combines CSI ratio with PCA–VMD fusion to mitigate position and noise issues, serving as a suitable migration baseline. However, prior approaches generally fuse channels to produce a single signal and then derive respiration rate from that signal. BreatheCS instead separates spectral rate estimation from coherent waveform reconstruction because the two outputs have different sensitivity to temporal phase errors.

> **Gap**: Prior fusion work assumes either binary phase relationships (±1 sign correction) or decomposes a single fused signal. BLE CS exhibits continuous, scene-dependent inter-tone and inter-modal phase offsets that require continuous complex-plane alignment and task-specific fusion domains.

### 2.3 Bluetooth Sensing and Channel Sounding

Traditional BLE sensing has primarily used RSSI, AoA/AoD, or proprietary channel measurements. Bluetooth Core Specification 6.0 formally introduced Channel Sounding, which includes Phase-Based Ranging (PBR) and Round-Trip Timing (RTT) for secure fine ranging. Early work has begun exploring BLE 6.0 CS for device-free sensing, but remains at the feasibility-demonstration stage. Our prior work demonstrated the feasibility of device-free sensing using BLE CS. This paper goes beyond feasibility by establishing a respiration-specific observation model, characterizing tone and modal relationships, designing separate rate and waveform processing branches, and evaluating the resulting system against physiological ground truth.

> **Gap**: No prior work has systematically modeled BLE CS PCT measurements for respiration, characterized the relationship between tone diversity and modal diversity, or addressed the task-specific fusion requirements of BPM estimation and waveform recovery.

### Summary

In summary, prior wireless respiration research has established Fresnel-based sensing models, amplitude–phase complementarity, and multi-channel fusion for WiFi CSI. Bluetooth CS introduces a different measurement primitive: bidirectional endpoint observations, a composite phase, sparse event sampling, and frequency-dependent tone relationships. Existing works have not systematically studied how these properties affect respiratory-rate estimation and waveform recovery, nor whether the two objectives should share the same fusion strategy. BreatheCS addresses this gap.

---

## 2. 相关工作（中文摘要）

现有无线呼吸感知研究主要围绕 WiFi CSI 和雷达展开，其信号模型和融合假设无法直接描述 BLE CS 的双向 PCT 观测。BLE CS 提供了不同的测量原语——双向端侧观测、组合相位、稀疏事件采样和频率相关的 tone 间关系——这些特征的呼吸感知建模尚属空白。BreatheCS 填补了这一空白。



---

## 3. BLE CS Primer / BLE CS 基础

### 3.1 BLE CS Physical Primer / BLE CS 物理基础

> **EN**: [Brief description of CS exchange, PCT multiplication, LO drift cancellation. Why remote_amplitudes, local_amplitudes, and phases are the three usable observables. Why total amplitude is not used.]
>
> **CN**: [简述 CS 交换过程、PCT 乘法、LO 漂移抵消。为什么 remote_amplitudes、local_amplitudes、phases 是三个可用观测量。为什么 total amplitude 不可用（双方噪声乘积，无独立物理意义）。]

BLE 6.0 推出了信道探测功能，其中最重要的更新就是引入了基于相位的测距（phase-based ranging, PBR）。CS -PBR （以下简称CS）要求两个设备必须首先连接，确定发起者、接收者的角色，随后在BLE的频段上以1MHz 的带宽为步进依次执行每个信道的测量。在预留一部分信道后，可用信道数为72个。

在每个信道测量中，双方各自向对方发送一个 CS tone，并由接收方测量该 CS tone 的幅值和相位，以 IQ 形式存储，记为 PCT （即 phase correlation term）。双方的PCT 在当前event 结束后会经由 ranging service 收集到一处。

为了抵消两个设备间的本振漂移，只需要将两者PCT叠加，就能获得最终的相位。我们设两个设备本振的固定相位差为  
$$
\Delta \theta_{LO} = 2\pi F_(\varphi_i- \varphi_r),
$$
其中，$F_1$ 是当前信道频率， $\varphi_i,\varphi_r$分别是发起方、反射方设备对真实时间的延迟。

从发起方出发的CStone ，经过时间 $\tau$后抵达反射方。当我们以发起方作为最终PCT整合方时，反射方就被视为 remote 端。因此，这一过程中的相位变化由反射方记录为 Remote PCT:
$$
\text{PCT}_{\text{Remote}}:\theta_{INI \rarr REF}  = 2\pi F \tau +\Delta \theta_{LO}.
$$

然后交换角色，反射方向发起方发送 CS tone，发起方记录 Local PCT:
$$
\text{PCT}_{\text{Local}}:\theta_{REF \rarr INI} = 2\pi F \tau -\Delta \theta_{LO} .
$$
显然，由上述两式可见，若将两端PCT叠加，就能消去未知的 $\Delta\theta_{LO}$。二者均为(a+bi)形式的复数，使用复数乘法就能得到两者的相位之和。最后，我们所获得的可用物理层感知信息就是本地、远端PCT的幅值，以及PCT叠加后的相位，我们分别将其记为：
$$
A_{\text{Local}},A_{\text{Remote}},\Phi
$$
由复数乘法获得的乘积的幅值就是幅值的乘积，并未引入新的物理量，因此不使用。

### 3.2 Effective Sampling Rate and Its Consequences / 有效采样率及其影响

> **EN**: BLE CS events occur at ~250–500 ms intervals (2–4 Hz). After bandpass filtering (0.1–0.35 Hz) and 20-second windowing, each window contains only ~2–7 breathing cycles (e.g., ~4 cycles for typical 0.2 Hz respiration). At this low effective rate, time-domain waveform alignment is more sensitive to event jitter, boundary effects, and non-stationary perturbations than in typical WiFi CSI streams. The spectral domain (|FFT|) discards timing information and is therefore more robust for frequency estimation—though narrowband sinusoidal phase can still be precisely estimated at high SNR. Our experiments confirm that magnitude-spectrum fusion achieves consistently higher BPM robustness.
>
> **CN**: BLE CS 事件的间隔约为 250–500 ms（2–4 Hz）。经带通滤波（0.1–0.35 Hz）和 20 秒滑窗后，每个窗口仅包含约 2–7 个呼吸周期（典型 0.2 Hz 呼吸约 4 个周期）。在此低有效采样率下，时域波形对齐对事件时序抖动、边界效应和非平稳扰动更敏感——比典型 WiFi CSI 数据流更脆弱。频谱域（|FFT|）丢弃了时间信息，因此对频率估计更稳健——但这不意味着时域对齐"本质不可能"，窄带正弦在高 SNR 下仍可精确估计相位。实验确认幅度谱融合在 BPM 稳健性上持续占优。

一个CS流程可能包含多个CS事件，CS事件是包含所有必须步骤的最小测量单位。单个事件内包含多个step，每个step就是某个信道的一次完整的双向测量。 本文启用全部的72信道以获得最大的频谱丰富度。

单个Step的耗时约300us，启用全部的信道后，单个事件的时长约为21ms。但根据BLE6.0规范【引用预留】，远端的PCT需要经由 ranging service 返回，这需要占用更多的时间。我们在nordic nrf54L15 上进行了多次测试，发现最短的事件间隔约为250ms。但如果需要长期执行测量，需要适当放宽最大间隔的上限。因此，实际的事件间隔在 250-500ms之间，频率为2-4Hz。根据奈奎斯特采样定理，这恰好高于呼吸频率的2倍范围，因此可以实现呼吸感知。

##   4.BLE CS Respiratory Observation Model

本节建立用于解释基于 BLE CS 呼吸感知的观测模型。我们首先分析BLE CS的有效物理观测量；接着，我们尝试构建信道、观测量模态之间的呼吸波形关系，以指导如何融合这些呼吸波形，达到提升信噪比、更好地拟合原始呼吸波形的目标。为此，我们讨论同一模态内 CS 信道之间的关系，并分析顺序 CS 信道扫描是否会引入不可忽略的呼吸相位偏移。最后，我们将模型扩展为多有效成分相量表示，从而解释不同观测模态间的连续性相位偏差，以为所提出的两级相干融合方法提供动机。

### 4.1 CS的有效观测变量

在 Section 3.1 中，我们论证了单次CS 测量可获得的变量。在呼吸感知中，我们需要连续进行CS测量，以获得各个变量的时序数据，随后用于进一步提取呼吸。

对于每个 CS 信道 $i$，BLE CS 提供两个 PCT 复数观测：
$$
Z_{l,i}(t), \quad Z_{r,i}(t), \tag{1}
$$
其中 $Z_{l,i}(t)$ 和 $Z_{r,i}(t)$ 分别表示$\text{PCT}_{\text{Local},}$, $\text{PCT}_{\text{Remote}}$ 在时间$t$ 上的采样序列。

随后，我们计算得到三个可用的呼吸感知变量序列：
$$
A_{l,i}(t)=|Z_{l,i}(t)|, \qquad A_{r,i}(t)=|Z_{r,i}(t)|, \\\Phi_i(t)=\operatorname{unwrap} \left( \angle\left(Z_{l,i}(t)Z_{r,i}(t)\right) \right). \tag{2}
$$
其中，$A_{l,i}(t)$ 和 $A_{r,i}(t)$ 是幅度型观测，分别是来自两端设备对环境的观测；而 $\Phi_i(t)$ 是相位型观测。三者具有不同的物理意义。为了论证这一点，考虑一种简单的单一呼吸路径下的情形：
$$
Z_{d,i}(t)=\overline{Z}_{d,i}+\delta Z_{d,i}(t), \quad d\in\{l,r\},\tag{3}
$$
其中 $\overline{Z}_{d,i}$ 是准静态分量，$\delta Z_{d,i}(t)$ 是由呼吸引起的扰动。

当 $|\delta Z_{d,i}(t)|\ll |\overline{Z}_{d,i}|$ 时，归一化幅度扰动可近似为该扰动的实部（复平面中，与$Z_{d,i}(t)$方向相同）：
$$
\frac{\delta A_{d,i}(t)}{\overline{A}_{d,i}} \approx \operatorname{Re} \left\{ \frac{V_d}{\overline{Z}_{d,i}} \right\}\delta Z_{d,i}(t),\tag{4}
$$
其中 $\overline{A}_{d,i}=|\overline{Z}_{d,i}|$。相反，积分相位扰动可近似为该扰动的虚部（复平面中，与$Z_{d,i}(t)$方向垂直）：
$$
\delta \Phi_i(t) \approx \operatorname{Im} \left\{ \frac{\delta Z_{l,i}(t)}{\overline{Z}_{l,i}} + \frac{\delta Z_{r,i}(t)}{\overline{Z}_{r,i}} \right\}.\tag{5}
$$
因此，幅度变量依赖于本地和远端复数扰动的径向分量，而积分相位依赖于两个 PCT 观测切向分量之和。这一区别促使我们将本地幅度、远端幅度和积分相位视为三种具有不同物理意义的呼吸观测模态。接下来，我们分别讨论模态内部各信道呼吸波形间的相位关系和模态之间的波形相位关系。

### 4.2 信道间的相位关系 Inter-Tone Phase Relationship / 信道间（Tone 间）相位关系

> **EN**: [Fresnel zone theory review. Applicability to BLE CS. PCA sign correction works → confirms ±1 baseline. But Hilbert continuous phase further improves → confirms additional structure from sequential sampling. Cite Figure 2.]
>
> **CN**: [回顾菲涅尔区理论。在 BLE CS 中的适用性论证。PCA 符号校正有效 → 确认 ±1 基线成立。但 Hilbert 连续相位补偿进一步改善 → 确认顺序采样引入了超越 ±1 的额外相位结构。引用 Figure 2。]

不同信道的频率不同，对于同样的呼吸活动，所引发的信道衰落也会有差异。为了更好的估计呼吸，拟合原始的波形，许多工作选择将各信道的波形融合到一起【相关WIFI的论文】。

同一模态内部各信道的物理意义是相同的，因此，如果按照菲涅尔区理论，它们之间的菲涅尔区边界会因为频率不同而略微有区别。对于同样的呼吸扰动，它们的影响要么是同相的，要么恰好是反相的。因此在过去的WIFI 感知工作中，为了合并所有信道的波形以获得最大的信噪比，通常仅考虑计算同相/反相的情况，为各信道赋予符号，以将所有信道的波形进行正确的相干合并。

仍考虑在静态工作点附近，由呼吸活动产生的一个微小扰动（等式 3），将其在工作点$\overline{Z}_{d,i}$附近做一阶泰勒展开
$$
Z_{d,i}(t)\approx \underbrace{Z_{d,i}^{(0)}} _{\text{Static}}+\underbrace{k_{d,i}\xi(t)} _{\text{Dynamic}},
$$
此时，静态分量可通过滤波等方式去除，剩余的动态项的系数和信道的频率相关。对于两个比较的信道 $Ch_i,Ch_j$，如果 $k_{d,i}k_{d,j}>0$那么两个 CS 信道观测同相；如果 $k_{d,i}k_{d,j}<0$，它们反相；如果任一系数接近零，则对应信道为弱响应。



我们在常见的会议室环境搭建了验证平台【图-金属板设置】，使用nrf54L15 启动BLE CS测量，并在其视距路径的垂直平分线上部署了金属板。金属板按模拟的呼吸频率周期性前后移动，范围为5-10mm。我们希望用金属板模拟较为理想的单一动态路径，以验证我们的猜想。

测试的结果如【图2-信道间关系(a)】，经预处理后，我们只保留动态呼吸成分，并展示72信道中的四个原始带通波形的叠加。不同信道间的幅值呼吸波形大致呈同相、反相分布。我们使用PCA为各信道赋予正负号，反相的波形被成功翻转，但可以观察到各信道之间仍然存在细微的相位偏差【图2-b】。通过希尔伯特变换并求出各信道的平均相位，然后旋转对齐，波形重合度得到了明显提升【图2-c】。

进一步的，我们在两个位置连续采集数分钟数据后，做出整个数据的信道间相干性热力图【图2-d】。在位置1（095806），各信道整体相干性更高，而位置2的相干性较低，且颜色分布更多样。这说明在真实的呼吸状态下，BLE CS的信道间相位存在同相、反相之外的细小偏差。尽管基于菲涅尔区的符号赋予已经非常有效，但通过hilbert变换对齐仍可进一步补偿。

我们认为，BLE CS 的具体实现过程可能会引入一些因素影响波形的相位关系，令实际情况不再符合理想的同相、反相情况：

-  BLE CS 的有效事件采样率较低，且 event 间隔可能存在不均匀性。有限长度窗口内的带通滤波、插值更容易受到时序误差、噪声和边界效应的影响，从而产生或放大表观的波形相位失配。
-  PCT 测量非理想性。包括接收机增益/延迟变化、有限信噪比下的相位估计误差、校准残差以及后处理畸变。
- 顺序扫描测量的影响是有限的。在BLE规范6.0中，每个 CS 信道约耗时 $300$--$400\,\mu\mathrm{s}$。即便使用保守值 $400\,\mu\mathrm{s}$，72 个信道的完整扫描时间也低于 $30\,\mathrm{ms}$。在呼吸频带上限 $f_b=0.35\,\mathrm{Hz}$ 处，由扫描导致的最大相位差近似为：

$$
\Delta\varphi_{\max} \le 2\pi f_b \cdot 72 \cdot 400\,\mu\mathrm{s} \approx 0.063\,\mathrm{rad} \approx 3.6^\circ.
$$

这一数值几乎对测量不造成主要影响。因此，对于呼吸感知而言，72 个 CS 信道观测可以视为准同时测量。

因此，本文将信道间关系建模为二值主符号关系与逐窗口连续残余相位的组合，并通过复平面旋转进行补偿。

![Figure 2: Inter-tone phase relationship. (a) Raw bandpass; (b) after ±1 sign; (c) after Hilbert; (d–e) 72×72 γ heatmaps (good/hard). Fresnel ±1 is first-order; sequential sampling needs continuous phase.](../../outputs/figures/paper_fig2_inter_tone_phase.png)

> **Fig. 2 解读**: (a) 4 个代表 tone（#58 ref, #48 同相 γ≈0.83, #45 反相 Δφ≈π, #69 中间相位 Δφ≈−0.83）的原始带通波形叠加。(b) PCA ±1 符号校正后：反相 tone 被翻转，但中间相位 tone 仍有明显残余错位。(c) Hilbert 连续相位对齐后：四条波形近乎完美重合。(d) 72×72 tone-pair 相干性热力图：cs_095806（左，good）左上角高 γ 结构密集；cs_091339（右，hard）整体 γ 更低且碎片化。**结论**：菲涅尔区 ±1 是有效的一阶近似，但顺序采样引入了超越 ±1 的连续相位分量，Hilbert 对齐可进一步补偿。另见 [Figure S1](#supplementary-figure-s1) 跨窗口 γ 稳定性对比。

<a id="supplementary-figure-s1"></a>

![Figure S1: Tone-pair coherence γ stability across windows (good vs hard CS metal-plate scenario).](../../outputs/figures/paper_figS1_coherence_stability.png)

> **Fig. S1 解读**: 同一 tone pair 跨窗口 γ；good 场景高且稳，hard 场景低且波动大。
### 4.3 Inter-Modal Phase Relationship / 模态间（变量间）相位关系

> **EN**: [Remote vs local vs phase: relative phase depends on multipath geometry. Different rooms → different relationships. Per-window variation observed. Cannot hardcode. Cite Figure 3.]
>
> **CN**: [Remote 与 local 与 phase 之间：相对相位取决于多径几何。不同房间 → 不同的相位关系。观察到逐窗变化。不可硬编码。引用 Figure 3。]

本章第一节已经证明三种模态之间是独立的物理量。为了增大感知性能、拟合原始呼吸波形，有必要研究三者波形间的相位关系，以讨论融合各观测模态的方案。

在【等式3】中，呼吸扰动$\delta Z_{d,i}(t)$ 可以进一步表示为：
$$
\delta Z_d(t)=V_d\xi(t)
$$
$V_d$是观测对于呼吸位移的敏感系数。比照 4.1，我们分别讨论各个模态的波形关系：
$$
\frac{\delta Z_l(t)}{Z_{l0}} = \operatorname{Re}\left\{\frac{V_l}{Z_{l0}}\right\}\xi(t)\tag
{6}\\ 
\frac{\delta Z_r(t)}{Z_{r0}} = \operatorname{Re}\left\{\frac{V_r}{Z_{r0}}\right\}\xi(t)\\
\delta\Phi(t) = \left[ \operatorname{Im}\left\{\frac{V_l}{Z_{l0}}\right\} + \operatorname{Im}\left\{\frac{V_r}{Z_{r0}}\right\} \right]\xi(t)
$$
我们将系数用复数形式表示，并予以简化的代号代替：
$$
\frac{V_L}{Z_{L0}}=u_L+jv_L \tag{7}\\
\frac{V_R}{Z_{R0}}=u_R+jv_R
$$
空间中由呼吸引起的路径可能有多个，第 $q$ 个有效呼吸成分写为：
$$
\xi_q(t)=X_q\cos(\omega t+\psi_q),
$$
其中 $X_q$ 和 $\psi_q$ 分别为其幅度和时间相位。为了简洁，我们转为使用向量表示：
$$
\xi_q(t) = \operatorname{Re} \left\{ X_qe^{j\psi_q}e^{j\omega_b t} \right\},\tag{8}
$$
于是，各模态的观测为：
$$
C_l=\sum_q u_{l,q}X_qe^{j\psi_q}\\
C_r=\sum_q u_{r,q}X_qe^{j\psi_q}\\
C_\Phi=\sum_q (v_{L,q}+v_{R,q})X_qe^{j\psi_q}
$$
因此，任意模态的等效呼吸幅度和相位可表示为：
$$
A=|C_{d}|, \qquad \varphi_{d}=\arg(C_{d}).
$$


于是，任意两个模态$m,n$的波形相位差可由复数的除法得到：
$$
\Delta\varphi_{(m),(n)} = \arg \left( C_{m}\overline{C}_{n} \right).\tag{9}
$$
含有多个有效成分的模型允许连续相位偏移。这是因为 $C_{d}$ 是复数，两个复数的夹角可以是任意的。因此，不同信道和不同模态可能产生指向复平面中不同方向的有效呼吸相量。

我们将4.3 的实验结果中三个模态的信道波形的相位对齐，然后融合成一个，并把三个波形归一化后比较【图-3 （a）】。它们之间也存在非整周期的相位关系。这验证了我们的模型。通过将它们的相位旋转对齐，可以消除这种相位偏差 【图3-b】。同时，这种情况并非偶然现象，我们将该次金属板模拟的所有数据的做加窗处理，然后画出每个窗口内三模态的相位偏差【图3-c】，这些相位偏差几乎是完全随机的；对于另一个位置场景下的模拟，相位关系又完全不同于前一场景【图3-d】。这充分证明了本节论述的各模态间不稳定的相位关系。



![Figure 3: Inter-modal phase relationship. (a) Before Level-2 align; (b) after Level-2 Hilbert + η fusion; (c–d) cross-window Δφ in two rooms. Modal phase is non-fixed and scene-dependent.](../../outputs/figures/paper_fig3_inter_modal_phase.png)

> **Fig. 3 解读**: (a) 三模态（remote/local/phase）经 Level-1 Hilbert tone 融合后的波形，Level-2 对齐前可见明显相位差异。(b) Level-2 Hilbert 对齐 + $\eta$ 加权融合后：三波形对齐，融合波形（粗黑线）跟踪一致性。(c) cs_095806 全 segment 跨窗模态间相位差 Δφ 序列：Δφ 非固定，逐窗浮动。(d) cs_102621（不同房间）同款图：Δφ 基线不同，确认模态间相位关系场景依赖。**结论**：模态相位不可预设，必须每窗估计，等权融合是正确的先验。

---

## 5. Proposed Method: BreatheCS / 提出方法：BreatheCS

本节提出 BreatheCS：面向 BLE CS 呼吸感知的统一双分支管线。目标是在同一套低采样率、多信道、三模态观测上，同时给出稳健的呼吸率估计与连续呼吸波形。

### 5.1 Design Rationale / 设计动机

对人体呼吸活动的观测包含两部分：BPM 估计与呼吸波形恢复。BPM 只需稳定的呼吸频率，一旦形成频谱，对时域残余错位不敏感；波形恢复则需保留形态学特征，因此依赖时域相干融合以提高呼吸能量比（BNR）。

BreatheCS 用共享前端 + 两条专用分支应对这两个目标：

1. **共享前端**：逐信道质量估计，采用互补的指标 $\eta$（呼吸频段能量比）与 $\rho$（谱峰峰度）构成权重，同时服务于谱加权与波形 MRC 权重。
2. **BPM 分支**：逐信道加权谱融合，再对三模态做加权谱融合。
3. **波形分支**：两级 Hilbert 相干 MRC：先在模态内做channel级对齐，再跨 remote/local/phase 做模态级对齐。

### 5.2 Preprocessing / 预处理

对每个 tone、三种变量：短窗中值滤波 → $0.05\,\mathrm{Hz}$ 高通去缓变漂移 → $0.1$--$0.35\,\mathrm{Hz}$ 呼吸带通。相位变量在滤波前先做 unwrap。随后以 $20\,\mathrm{s}$ 窗长、$1\,\mathrm{s}$ 步长滑窗处理。记模态 $m$、信道$i$ 的带通波形为 $x_{m,i}(t)$。

### 5.3 Stage 1: Per-Modal Channel Quality and Weighted Spectra / 逐模态信道质量与加权谱

在进入任一分支前，为每个 tone 赋予反映呼吸频段主导性与峰值可靠性的质量分数。设 $P_{m,i}(f)$ 为（$\eta$ 用高通、$\rho$ 与 BPM 谱用带通）信道 功率谱，$\mathcal{F}_b$ 为呼吸频段，$\mathcal{F}$ 为分析频段：

$$
\eta_{m,i}
=
\frac{\sum_{f\in\mathcal{F}_b}P_{m,i}(f)}{\sum_{f\in\mathcal{F}}P_{m,i}(f)+\epsilon}
$$

（LaTeX: `eq:eta`）

$$
\begin{aligned}
\rho_{m,i}
&=
\frac{P_{m,i}(\widehat{f}_{m,i})}{\frac{1}{|\mathcal{F}_b|}\sum_{f\in\mathcal{F}_b}P_{m,i}(f)+\epsilon},
\\
\widehat{f}_{m,i}
&=
\arg\max_{f\in\mathcal{F}_b}P_{m,i}(f)
\end{aligned}
$$

（LaTeX: `eq:rho`）

$$
\begin{aligned}
w_{m,i}
&=
\eta_{m,i}\cdot\max(\rho_{m,i},0),
\\
\tilde{w}_{m,i}
&=
\frac{w_{m,i}}{\sum_j w_{m,j}+\epsilon}
\end{aligned}
$$

（LaTeX: `eq:eta_rho_weight`）



呼吸能量比 $\eta$ 反映呼吸频段能量在总频带内的集中程度。$\rho$ 衡量呼吸频带内主峰相对于均值的突出程度（峰值/带内均值），与 $\eta$ 互补——$\eta$ 检测"呼吸频段是否有足够能量"，$\rho$ 检测"呼吸频段内是否有显著主峰"。注意 $\rho$ 本身奖励任何尖锐峰（包括非呼吸假峰），因此必须与 $\eta$ 联用（$\eta$ 确保能量集中在呼吸频段，$\rho$ 确保该频段内有主导峰）。最终权重为两者的乘积 $w = \eta \cdot \max(\rho, 0)$。



记 $S_{m,i}(f)$ 为模态 $m$、tone $i$ 的带通幅度谱。逐模态融合谱为质量加权平均：

$$
\bar{S}_m(f)
=
\sum_{i=1}^{N}\tilde{w}_{m,i}\,S_{m,i}(f)
$$

（LaTeX: `eq:weighted_spectrum`）

### 5.4 Stage 2a: BPM Branch — Weighted Spectrum Fusion / BPM 分支：加权谱融合

BLE CS 的PCT测量提供三种模态。在对三种模态的信道融合、模态之间的融合，然后估计 BPM 时，我们基于权重动态地决定每个窗口三模态的话语权，不预设任一模态更优。三个模态的谱按等权无偏先验融合，或按窗级质量自适应加权：

$$
S_{\mathrm{final}}(f)
=
\frac{\bar{S}_{r}(f)+\bar{S}_{l}(f)+\bar{S}_{\phi}(f)}{3}
\quad\text{（等权基线）}
$$

或

$$
S_{\mathrm{final}}(f)
=
\frac{w_r\bar{S}_{r}(f)+w_l\bar{S}_{l}(f)+w_{\phi}\bar{S}_{\phi}(f)}{w_r+w_l+w_{\phi}+\epsilon}
\quad\text{（质量加权）}
$$

其中 $w_m$ 由模态级 $\eta$ 或窗级质量门控决定（见消融实验 §6.5）。等权是物理无偏先验——Remote 和 Local 物理对等，Phase 是二者的切向组合——在无额外质量信息时不应预设偏好；但 HKH 消融表明等权可能因 Phase 噪声注入而劣于双模态（Remote+Local）融合，因此自适应门控是必要的后续方向。 [⚠️ D3, D4: Phase gate 结果和显著性检验决定此段最终推荐策略]

在 $\mathcal{F}_b$ 内寻峰，并对主峰邻域做抛物线插值：

$$
\begin{aligned}
\widehat{f}_b
&=
\operatorname{ParabolicInterp}\Bigl(
S_{\mathrm{final}},\,
\arg\max_{f\in\mathcal{F}_b}S_{\mathrm{final}}(f)
\Bigr),
\\
\widehat{\mathrm{BPM}}
&=
60\,\widehat{f}_b
\end{aligned}
$$

（LaTeX: `eq:bpm_peak`）

该谱域分支是 BreatheCS 的**主 BPM 输出**。它继承质量加权信道融合的稳健性，并避免低采样率下脆弱的时域对齐。

我们在金属板数据上对$w$ 的信道选择效果予以验证【图5】。【图5-b】显示，通过权重$w$对信道的抑制和增强，在估计BPM时，所得到的频谱投票结果要更集中于groundtruth 附近。

![Figure 5: η·ρ quality voting. (a) Per-tone η vs ρ; (b) BPM histogram uniform vs voting; (c) fused spectrum.](../../outputs/figures/paper_fig5_eta_rho_voting.png)

> **Fig. 5 解读**: (a) 单窗 72 tone 的 $\eta$ vs $\rho$：高 $\eta$/高 $\rho$ tone 与共识 BPM 一致。(b) 直方图：$\eta\cdot\rho$ 加权峰更尖。(c) 加权谱噪声底更低、呼吸峰更突出。**结论**：$\eta$ 与 $\rho$ 互补，乘积作质量权重有效。注：直方图投票标量在 B3 Simplified 中主要用于机制示意/诊断；**最终 BPM 由加权谱等权模态融合寻峰得到**。

### 5.5 Stage 2b: Waveform Branch — Two-Level Hilbert-MRC / 波形分支：两级 Hilbert-MRC

波形恢复使用 HiCo-MRC（两级复平面相干融合）。由 §4 相量模型，模态 $m$、tone $i$ 的带限呼吸分量可写为：

$$
x_{m,i}(t)
\approx
\operatorname{Re}\bigl\{C_{m,i}e^{j\omega_b t}\bigr\}
+
n_{m,i}(t)
$$

（LaTeX: `eq:tone_phasor`）

其解析信号为：

$$
\begin{aligned}
z_{m,i}(t)
&=
x_{m,i}(t)+j\mathcal{H}\{x_{m,i}(t)\}
\\
&\approx
C_{m,i}e^{j\omega_b t}+\tilde{n}_{m,i}(t)
\end{aligned}
$$

（LaTeX: `eq:analytic_tone`）

其中 $\mathcal{H}\{\cdot\}$ 为 Hilbert 变换。

#### Channel-level fusion / 信道级融合

对每个模态 $m$，按质量选参考 信道：

$$
i_m^\star=\arg\max_i w_{m,i}
$$

（LaTeX: `eq:ref_tone`）

相对参考 tone 的连续相位由复相关估计：

$$
\Delta\phi_{m,i}
=
\arg\left(\sum_t z_{m,i}(t)\overline{z}_{m,i_m^\star}(t)\right)
$$

（LaTeX: `eq:delta_phi_tone`）

再在复平面旋转，并用 Stage~1 的质量权重 $w_{m,i}$ 叠加：

$$
\begin{aligned}
z_m(t)
&=
\frac{\sum_i w_{m,i}\,z_{m,i}(t)\,e^{-j\Delta\phi_{m,i}}}{\sum_i w_{m,i}+\epsilon},
\\
y_m(t)
&=
\operatorname{Re}\{z_m(t)\}
\end{aligned}
$$

（LaTeX: `eq:level1_mrc`）

复平面旋转能补偿符号校正剩余的连续相位偏差。各个波形的融合则参考MRC（最大比合并）的思想【参考预留】，为各个波形按$w$ 赋予权重。MRC 为各个信道赋予等比于自身信噪比（SNR）的权重，以最大化提升整体的信噪比。在BreatheCS 中，我们用呼吸能量权重$w$ 模拟SNR在MRC的功能。

#### Modal-level fusion / 模态级融合

三模态波形 $y_r(t)$、$y_l(t)$、$y_\phi(t)$ 仍可能存在连续相位差。各自转为解析信号 $u_m(t)=y_m(t)+j\mathcal{H}\{y_m(t)\}$，由 $y_m$ 重算模态能量比 $\eta_m$，取参考模态 $m^\star=\arg\max_m\eta_m$。模态相位差 $\Delta\theta_m$ 的定义与信道级 $\Delta\phi_{m,i}$ 类似：

$$
\begin{aligned}
z_{\mathrm{final}}(t)
&=
\frac{\sum_m \eta_m\,u_m(t)\,e^{-j\Delta\theta_m}}{\sum_m\eta_m+\epsilon},
\\
y_{\mathrm{final}}(t)
&=
\operatorname{Re}\{z_{\mathrm{final}}(t)\}
\end{aligned}
$$

（LaTeX: `eq:level2_mrc`）

$y_{\mathrm{final}}(t)$ 是 BreatheCS 的主波形输出，用于呼吸波形的恢复。

> 

---

## 6. Experimental Validation / 实验验证

### 6.1 Setup / 实验设置

> **EN**: [CS metal-plate: 3 rooms, mechanical BPM ground truth. HKH: 3 rooms × 4 subjects, respiratory belt ground truth. Metrics: BPM absolute error, RMSE. Baseline methods listed.]
>
> **CN**: [CS 金属板：3 个房间，机械振动 BPM ground truth（可控、精确，但无波形 GT）。用于 §2–§3 的机制验证。HKH 真人：3 房间 × 4 受试者 = 12 条数据，呼吸带 ground truth。用于 §4 的效果验证。指标：BPM 绝对误差（breaths/min）、RMSE（波形 vs 呼吸带）。Baseline：B0 Single Remote, B1 Uniform Remote, Modal top2, T0-V3 Per-Tone Voting, WiFi MRC (Fan 2024), Zhuo2023 PCA-VMD。]

为验证 BreatheCS 的效果，我们采集了4位subjects 的真人呼吸数据。实验共分三个场景，均为常见的室内环境：客厅的静坐，卧室的平躺、卧室的侧躺【图-实验场景】。在每个场景中，我们要求受试者佩戴HKH-11C呼吸传感器采集真实的呼吸波形。两个BLE CS 设备被安置于受试者附近，且装载6dbi 的天线。BLE CS 的平台是支持 BLE 6.0 的 Nordic nrf54L15。

我们从BLE CS initiator 一侧收集数据，因此， local PCT 即为 initiator 所测得的reflector 所发射的CS tone ，remote PCT 即为reflector 的数据。在一次CS event  结束后，reflector 将remotePCT发回 initiator，随后两侧PCT通过串口上传到我们自行设计的PC上位机。单个event数据传输的时间经过测量小于20ms. 

在BLE CS的配置中，我们启用了全部72个信道，并将事件最短事件间隔设置为250ms 。但经过我们大量实验，这个参数无法在长期CS测量中稳定维持。通过将事件的最大执行时间限制设置为250-500ms，CS可以得到稳定执行。

### 6.2 Baseline /比较基线

基于BLE CS 的无线感知研究较为早期，据我们所知，目前尚未有比较全面的呼吸感知算法研究。基于WIFI等其他传感器的无线呼吸感知则比较完善，许多专门的信号处理和信噪比增强的方案都已得到讨论【参考预留】。在现有的基于商用设备的呼吸感知中，对于信道的融合和模态的融合已有考虑，但它们通常无法直接迁移到BLE CS上作为比较基线。

较低的采样率、独有的双向PCT合成是BLE的特殊之处。现有的无线呼吸感知技术中，缺乏专门针对此特征的处理方案。为此，我们专门针对近期的各类呼吸感知工作做出针对性调整，以和我们所提出的BreatheCS做公正合理的比较。

Fan 等人【Fan2024】 先计算各信道呼吸能量比（BNR），然后用MRC做多信道的加权合并。在最终决定用幅值还是相位候选时，依照BNR选择最大的一个作为最终波形。所以在我们的迁移复现中，第二阶段依最大能量比从三模态选择一个 ，与其保持一致。

一些工作使用两个天线的CSI ratio 作为原始数据，信号预处理阶段有时涉及寻找CSI ratio 的最大投影方向以增强波形的显著性【Farsense 等】。这类步骤在BLE CS上无法复现，因为 BLE CS 的幅值-相位信息并不属于同一个设备。除去这一步之外，多信道的融合策略也有使用PCA【Zhuo 2023】、MRC+PCA【wi-sleep（yu2021）】的方案，这些步骤及其后续部分可以作为baseline 参与比较。

为了进一步挖掘各方案的优势，对于在信号后处理部分具有独特做法的（例如zhuo 2023使用VMD获得频率成分），除了原样复现的对照外，还会有只包含融合部分的变体参与比较，以研究各部分的优势。

由于BLE CS 的低采样率特性，我们为所有baseline 部署于 BreathCS 一致的预处理步骤（即章节5.2），然后，比较主要在在信道级融合与模态级融合的差异，并最终体现在BPM估计误差和恢复的波形与groundtruth的RMSE上。

### 6.3 BPM Accuracy/ BPM 精度

> **EN**: [B3 Simplified = 0.41 BPM mean abs error, Z1-no-VMD = 0.44, B2-D = 0.68, Fan2024 η-linear = 1.39. Cite Figure 6.]
>
> **CN**: [主结果（12-scenario aggregate）：B3 Simplified = B1 Vote→Equal = **0.405** BPM mean abs error（最优），Zhuo2023 Z1-no-VMD = 0.435，MRC-PCA η-equal PCA3→1 = 0.505，B2-D Two-level Hilbert-MRC = 0.682，Fan 2024 η-linear = 1.386。引用 Figure 6。]

这一章节展示不同的baseline 及其变体在BLE CS 数据上的性能，并于 breatheCS 作比较。这里我希望，如果几乎是原样迁移的，比如zhuo 2023 单级PCA然后VMD就是主baseline ，双级PCA就是变体，那主baseline 里第二级就是选一个最大模态就可以。我们可以在实验中制作很多变体，但最后论文中没必要都放出来。可能需要优化一下展示方式，比如各个方法的具体名称如何简洁的表达。

尽管BreatheCS是两个分支的组合，但在最终绘图的时候，要只保留最终的名字，而不是分支的名（目前两个图里的ref 都是分支名字，而且不是论文里的名称，是跑算法时候的代号）。这块也应该考虑。

同时，目前的图里BPM没有 BreatheCS 的BPM，用的是波形分支的结果，这显然是不合适的，因为波形分支在BPM估计中不占优势。不要使用波形分支，直接用BPM分支并标注为BreatheCS 即可。对于fig 6，不论是按房间还是全场景的总排名都是这样。

（简化代号，让图更清晰。或者我们干脆在正文里对各个方案详细表述，然后表格中只放简化的代号，比如 zhuo 23 ,zhuo23-a 这种。或者干脆就考虑其他展示方式，表格会好一些还是更差一些呢）

> **配图更新（执行侧）**：已按论文名重绘；BreatheCS BPM=0.405（谱分支）；Fig 6b 与 Fig 6a 同方法集（含 ClessBreath）。图内无标题，说明见题注。  
> **表格对照**：下面同时给出与 Fig 6a/6b 同口径的数值表，便于比较「图 vs 表」哪种更适合正文。

#### Table 6.3-A · BPM overall（对应 Fig 6a）

| Method | BPM abs err mean ↓ | std（跨场景） |
|---|---:|---:|
| BreatheCS ★（谱分支） | **0.405** | 0.150 |
| Pos-Free (PCA) | 0.435 | 0.123 |
| WiFi-Sleep (MRC-PCA) | 0.505 | 0.149 |
| BreatheCS-Wave（时域分支，对照） | 0.682 | 0.599 |
| WiFi-Sleep (√η) | 1.023 | 1.257 |
| PCA sign only | 1.317 | 0.646 |
| ClessBreath (η-linear) | 1.386 | 1.685 |
| ClessBreath (η-equal) | 1.486 | 1.527 |

> HKH 12-scenario mean。BreatheCS = 谱分支 BPM；BreatheCS-Wave 仅作双分支对照，非主方法行。

#### Table 6.3-B · BPM by room（对应 Fig 6b）

| Method | Room A（客厅静坐） | Room B（卧室平躺） | Room C（卧室侧躺） |
|---|---:|---:|---:|
| BreatheCS ★ | **0.383** | 0.456 | **0.377** |
| Pos-Free (PCA) | 0.415 | **0.436** | 0.455 |
| WiFi-Sleep (MRC-PCA) | 0.609 | 0.451 | 0.455 |
| BreatheCS-Wave | 0.830 | 0.497 | 0.719 |
| WiFi-Sleep (√η) | 1.521 | 0.532 | 1.016 |
| PCA sign only | 1.365 | 1.212 | 1.373 |
| ClessBreath (η-linear) | 1.498 | 1.225 | 1.434 |
| ClessBreath (η-equal) | 1.400 | 2.038 | 1.022 |

> 每房间 4 subjects 均值。单位：BPM abs err。

![Figure 6a: HKH BPM leaderboard across 12 scenarios. BreatheCS (spectral BPM, ★) = 0.405 breaths/min mean abs error; paper method names.](../../outputs/figures/paper_fig6a_bpm_leaderboard.png)

![Figure 6b: HKH BPM by room for the same methods as Fig 6a (incl. ClessBreath). Rooms: Living sitting / Bedroom flat / Bedroom side.](../../outputs/figures/paper_fig6b_bpm_by_room.png)

> **Fig. 6 解读**: (上) 全 12 场景 BPM 排行榜。**BreatheCS**（谱分支）= 0.405，优于 Pos-Free (PCA) 0.435、WiFi-Sleep (MRC-PCA) 0.505；ClessBreath 系列约 1.39–1.49。(下) 按房间拆分，方法集与 Fig 6a 一致。

### 6.4 Waveform Recovery Accuracy / 波形恢复精度

> **EN**: [B3 Simplified RMSE = 0.951 vs belt, B2-D same. Z1-no-VMD RMSE = 1.070. B3 is the only unified pipeline achieving both optimal BPM (0.41) and optimal waveform (0.951). Cite Figure 7.]
>
> **CN**: [B3 Simplified RMSE = **0.951**（vs 呼吸带），B2-D 同值 0.950。Z1-no-VMD RMSE = 1.070。B3 是唯一同时输出最优 BPM (0.405) 和最优波形 (0.951) 的统一管线。引用 Figure 7。]

这一章节同样是和上面的baseline 比较波形恢复的性能，也就是RMSE误差比较。我认为至少也应该像6.3一样，把各类方法画图比较，图7感觉好像暂时在这章用不上。

> **配图更新（执行侧）**：§6.4 主展示用表；Fig 7 为 BPM×RMSE 散点。下面 Table 6.4 把 BPM 与 RMSE 合在一张表，便于和 Fig 7 对照。

#### Table 6.4 · BPM × RMSE（对应 Fig 7）

| Method | BPM abs err mean | RMSE mean | RMSE std |
|---|---:|---:|---:|
| BreatheCS ★ | **0.405** | **0.951** | 0.192 |
| Pos-Free (PCA) | 0.435 | 1.070 | 0.250 |
| WiFi-Sleep (MRC-PCA) | 0.505 | 1.063 | 0.245 |
| BreatheCS-Wave（时域分支对照） | 0.682 | 0.950 | 0.195 |
| WiFi-Sleep (√η) | 1.023 | 1.054 | — |
| PCA sign only | 1.317 | 1.085 | 0.182 |
| ClessBreath (η-linear) | 1.386 | 1.025 | 0.241 |
| ClessBreath (η-equal) | 1.486 | 1.046 | 0.211 |

> HKH 12 scenarios；RMSE = z-score 对齐 vs 呼吸带。BreatheCS 主方法取谱 BPM + 统一管线波形 RMSE；BreatheCS-Wave 行仅对照。√η 的 RMSE std 未单列于 redraw 表，故标 —。

![Figure 7: BPM vs RMSE trade-off on HKH 12 scenarios. BreatheCS (★) best joint; BreatheCS-Wave (◆) shown only for branch contrast, not as a separate table row.](../../outputs/figures/paper_fig7_bpm_vs_rmse.png)

> **Fig. 7 解读**: 每个点为方法在 12 场景上的 (BPM abs err, RMSE)。BreatheCS（★）左下角最优联合表现。

### 6.5 Ablation Experiments / 消融实验

> **EN**: [Channel fusion: Voting > Single-best > Uniform. Modal fusion: Equal > Top2 > η-weight. Phase method: Hilbert two-level > single-level > sign-only. Cite Figure 8.]
>
> **CN**: [信道融合消融：Voting (η·ρ 加权) > Single-best (max-η) > Uniform (等权)。模态融合消融：Equal (1:1:1) > Top2 > η-weight → 对称对待被验证。相位方法消融：Hilbert 两级 > Hilbert 单级 > Corr sign > PCA sign。解锁器交互效应（§3.6）进一步证实第一级 Hilbert 的逻辑必要性。引用 Figure 8。]

本章节通过比较不同融合权重分配方案（包括不使用融合，仅保留最大变量）验证 BreatheCS 的性能。BreatheCS 作为信道+模态的两级融合方案，每一级都会利用所有可用的信息做融合。当消融需要某一级不再融合时，我们就选择该层级上能量比最大的一个作为最终的BPM和呼吸波形的候选。

（这块做个表格好还是画图好呢）

每种方案都会计算BPM和RMSE 误差：

1.时域波形的融合（有波形的话，既能有BPM，也有RMSE）：

- 不融合：两级均只选择最大能量比的信号
- 仅信道融合，模态选最大；
- 仅模态融合，信道选最大；
- BreatheCS （本文方案）



2.频域的谱融合（此类方案没有波形输出，只有BPM估计）：

- 不融合：两级均只选择最大能量比的信号
- 仅信道融合，模态选最大；
- 仅模态融合，信道选最大；
- BreatheCS  （本文方案）

3.局限单一模态的方案
这个是指在1，2中，全程只考虑同一个模态的情况，最后比较的结果图就是三个模态+breatheCS的比较。



通过上述三点，应该能充分展示信道融合、模态融合的性能优势，同时展示BreatheCS 的优势。（是否存在解锁器效应，则需要在结果中尝试发掘）。

目前的图问题在于有许多代号，导致分类不够清晰，不好比较。由于前面两章已经比较了一些代表性相关工作的方案，它们或多或少有某一级的融合，因此这里不再根据融合策略拆分不同的子项。

> **配图更新（执行侧）**：Fig 8 两组三连图 —— (a)(b)(c) 融合层级；(d)(e)(f) 单模态。数值 3 位小数；BreatheCS 红柱+黑边。  
> **表格对照**：Table 8-A/8-B 与图同口径，便于比较图/表可读性。

#### Table 8-A · Fusion levels（对应 Fig 8a–c）

| Fusion level | Spec BPM ↓ | Wave BPM ↓ | Wave RMSE ↓ |
|---|---:|---:|---:|
| No fusion | 1.640 | 1.192 | 1.007 |
| Channel only | **0.381** | 1.003 | 0.962 |
| Modal only | 0.655 | 1.025 | 0.986 |
| BreatheCS ★ | 0.405 | **0.744** | **0.951** |

> 谱域无波形 RMSE（—）。Channel only 在谱 BPM 上略优于等权三模态 BreatheCS。

#### Table 8-B · Single-modal（对应 Fig 8d–f）

| Domain | Remote | Local | Phase | BreatheCS (3-modal) |
|---|---:|---:|---:|---:|
| Spectral BPM | **0.376** | 0.378 | 2.191 | 0.405 |
| Waveform BPM | **0.399** | 0.439 | 2.395 | 0.744 |
| Waveform RMSE | **0.931** | 0.947 | 1.109 | 0.951 |

> HKH 12-scenario mean。谱域无 RMSE。Phase 单独极差；Remote/Local 常略优于三模态等权。汇总：`outputs/reports/ble_hkh_draft_ablation_summary.json`。

![Figure 8a–c: Fusion-level ablation. (a) Spectral BPM; (b) Waveform BPM; (c) Waveform RMSE. Bars: no fusion / channel only / modal only / BreatheCS.](../../outputs/figures/paper_fig8_abc_fusion.png)

![Figure 8d–f: Single-modal ablation. (d) Spectral BPM; (e) Waveform BPM; (f) Waveform RMSE. Remote / Local / Phase vs BreatheCS.](../../outputs/figures/paper_fig8_def_single_modal.png)

> **Fig. 8 解读**: (a–c) 信道/模态融合层级；(d–f) 把完整管线限制在单一模态。BreatheCS 谱分支为逐模态 η·ρ 加权谱 → **三模态等权**融合；时域分支为两级 Hilbert-MRC。单模态表显示 Phase 单独很差，Remote/Local 幅值常略优于三模态等权——见报告讨论。

---

## 7. Discussion / 讨论

### 7.1 为什么谱域在低采样率下优于时域？

20 s 窗口在 0.1–0.35 Hz 内仅包含 2–7 个呼吸周期（典型的 0.2 Hz 呼吸约 4 个周期）。时域波形对齐对微小时间偏移敏感——两个信道间一个采样点的偏移可能在仅 4 个周期上造成显著相对相位误差。|FFT| 丢弃时间信息后对这类残差偏移不敏感，因此谱域融合更适合 BPM 估计。但这不意味着时域对齐”本质不可能”——只是在实际采样率、窗口长度和 SNR 下更敏感。波形分支通过复平面相干对齐补偿这些残差。

### 7.2 为什么等权是合理的无偏先验而非已证明最优？ [⚠️ D4: 显著性检验结果决定此节论述方向]

Remote 和 Local 是同一双向交换的两个端侧观测，物理上对等。组合 Phase 是二者的切向投影之和。在缺乏每窗额外质量信息时，等权避免了预设偏好引入的场景过拟合。但 HKH 消融（§6.5, Table 8-B）表明等权三模态（0.405）略劣于双模态 R+L（[待实验]）和 Remote-only（0.376）——因为 Phase 质量系统性偏弱时，等权等价于向好信号中注入噪声。因此等权应定位为”无偏基线”而非”已证明最优策略”；条件性 Phase 门控是自然延伸。

### 7.3 解锁器效应的物理含义

实验发现仅当第一级使用连续 Hilbert 相位校正时，第二级模态对齐才有效（CS 跨域：B2-D 有效、A1-D 无效）。这与 §4 模型一致：符号校正后残留的非二值相位误差污染模态波形，第二级无法从已退化输入中恢复。连续对齐保住保真度，从而”解锁”模态级相干融合收益。此效应也说明：将 BLE CS 的 tone 间/模态间相位关系建模为连续的（而非二值的）是必要的。

### 7.4 组合相位的条件性角色 [⚠️ D1, D2, D3: 此节内容取决于 Phase oracle 上限、IQ 几何诊断和 Phase gate 实验结果]

Phase 在机械金属板（CS）上有用但非支配性；在真人（HKH）上系统性偏差。5.6sol 建议从”径向/切向互补投影”角度理解。Phase 是切向投影之和——当幅值径向分量弱时可能有增量信息，但切向分量本身也可能因多径而退化。此外人体微动、非正弦呼吸、多径复杂度均可能劣化 Phase 的跨 tone 一致性。**Phase 的合理定位不是”等权第三模态”，而是”条件性 rescue expert”——仅在可观测指标指示幅值不可靠时启用。** 这是 Phase plan v2.0 (§3.2–3.3) 的核心假设和后续验证方向。

> ⚠️ 本段最终措辞取决于 D1/D2/D3 实验结论。若 D1 显示 oracle 增量极小，需加入”Phase oracle upper bound is limited to ~0.0X BPM”；若 D3 门控失败，需加入”observable quality indicators did not reliably identify windows where Phase improves BPM”。

不足与未来方向：复杂多径（cs_091339）仍是全局瓶颈；受控工作点扫描实验是验证物理模型的最直接方式 [待确认可行性]；多人呼吸、呼吸暂停检测、per-window 动态分支选择是后续扩展方向。

---

## 8. Conclusion / 结论

**EN**: This work presented BreatheCS, a measurement-aware framework for contactless respiration sensing with Bluetooth Channel Sounding. By modeling the bidirectional PCT measurements, we showed that BLE CS provides two endpoint amplitude observations and one composite-phase observation with distinct complex-plane sensitivities and noise characteristics. Our measurements further revealed heterogeneous sensing quality across tones, continuous and scene-dependent phase relationships, and different processing requirements for respiratory-rate estimation and waveform recovery. Based on these findings, BreatheCS combines a shared quality-aware tone-fusion front-end with a spectral branch for robust BPM estimation and a hierarchical complex-domain branch for waveform reconstruction. Evaluation on controlled mechanical motion and 12 human-subject recordings achieved a mean BPM error of 0.405 breaths/min and a normalized waveform RMSE of 0.951. More importantly, the ablation results showed that tone diversity is the most reliable source of improvement (1.640 → 0.381 BPM), whereas modal diversity—particularly composite phase—provides conditional rather than universal benefit. These findings suggest that future BLE CS sensing systems should avoid directly migrating fixed WiFi CSI fusion assumptions and instead account for the bidirectional measurement structure and task-specific sensing objective. Future work will investigate observable conditions under which composite phase provides complementary information, improve robustness to body motion and complex multipath, and extend the framework to irregular breathing and apnea detection. [⚠️ D1, D3: Phase 相关 future work 的措辞取决于 oracle 上限和 gate 结果——若 D3 成功则改为 "scale the adaptive Phase gating to larger cohorts"，若失败则保持当前措辞]

**CN**: 本文提出了 BreatheCS，一个面向 BLE 信道探测的测量感知非接触呼吸感知框架。通过建模双向 PCT 测量，我们表明 BLE CS 提供了两个端侧幅值观测和一个组合相位观测——三者具有不同的复平面灵敏度和噪声特性。实验测量进一步揭示了 tone 间显著的感知质量异质性、连续且场景依赖的相位关系，以及呼吸率估计和波形恢复需要不同的处理域。基于这些发现，BreatheCS 组合了共享的质量驱动 tone 融合前端、稳健的谱域 BPM 分支，以及分层复平面相干波形分支。在可控机械运动和 12 条真人记录上的评估实现了 0.405 breaths/min 的平均 BPM 误差和 0.951 的归一化波形 RMSE。消融实验揭示了一个核心发现：**tone diversity 是最稳定、最大的增益来源（1.640 → 0.381 BPM），而 modal diversity——特别是组合相位的增益——是条件性的，取决于场景和信号质量。** 这些发现为未来 BLE CS 感知系统指明了方向：不应直接迁移 WiFi CSI 的固定融合假设，而应考虑双向测量结构和感知目标对融合域的不同需求。

---

## References / 参考文献

**EN**: [TBD — WiFi Fresnel zone papers (Wang et al. MobiCom, Zhang et al. MobiSys), Fan 2024, Yu 2021 WiFi-Sleep, Zhuo 2023 PCA-VMD, FullBreathe (Zhang et al.), FarSense, BLE CS spec (Bluetooth Core Specification 6.0), etc.]

**CN**: [待补充 — 菲涅尔区 WiFi 感知论文、Fan 2024、Yu 2021 WiFi-Sleep、Zhuo 2023 PCA-VMD、FullBreathe、FarSense、BLE Core 6.0 信道探测规范、BLE CS device-free sensing 早期演示工作等。]

> ⚠️ **版本修正（v0.4）**：全文统一 Bluetooth 版本为 **Core Specification 6.0**（旧版 draft 中英文不一致——英文写 5.2、中文写 6.0）。Channel Sounding 是 Bluetooth Core 6.0 引入的新功能。
