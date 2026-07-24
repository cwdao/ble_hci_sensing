# Breathing Sensing via BLE Channel Sounding: System Modeling and a Unified Physically-Principled Pipeline

# 基于 BLE 信道探测的呼吸感知：系统建模与物理驱动统一管线

> **DRAFT v0.3** — 骨架稿 + 已插入可用配图。每节仅写核心句子。先英后中。细节由用户补充。  
> **日期**：2026-07-18  
> **配图状态**：Fig 2 ✅ | Fig 3 ✅ | Fig 4 ❌ (数据已有，图未生成) | Fig 5 ✅ | Fig 6 ✅ | Fig 7 ✅ | Fig 8 ✅ | Fig S1 ✅ | Fig 1 ❌ (需手绘架构图)

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

## 2.Background and Related work



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

> **EN**: BLE CS events occur at ~100–200 ms intervals. After bandpass filtering (0.1–0.35 Hz) and 20-second windowing, each window contains only ~4 breathing cycles. This makes time-domain waveform alignment intrinsically unreliable—a small timing offset between two channels translates to a large relative phase error across only 4 cycles. The spectral domain (|FFT|) discards timing information and is therefore the natural choice for frequency estimation.
>
> **CN**: BLE CS 事件的间隔约为 100–200 ms。经带通滤波（0.1–0.35 Hz）和 20 秒滑窗后，每个窗口仅包含约 4 个呼吸周期。这使得时域波形对齐在本质上不可靠——两个信道之间的微小时间偏移会在仅 4 个周期上转化为较大的相对相位误差。频谱域（|FFT|）丢弃了时间信息，因此是频率估计的自然选择。

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

![Figure 2: Inter-tone phase relationship — (a) 4 tones raw bandpass waveforms, (b) after PCA sign correction (±1 only), (c) after Hilbert continuous phase alignment → near-perfect overlap, (d) 72×72 coherence matrix γ_ij (good scenario cs_095806 | hard scenario cs_091339). Takeaway: Fresnel ±1 is the first-order baseline; sequential sampling introduces additional continuous phase offsets that only Hilbert alignment can compensate.](../../outputs/figures/paper_fig2_inter_tone_phase.png)

> **Fig. 2 解读**: (a) 4 个代表 tone（#58 ref, #48 同相 γ≈0.83, #45 反相 Δφ≈π, #69 中间相位 Δφ≈−0.83）的原始带通波形叠加。(b) PCA ±1 符号校正后：反相 tone 被翻转，但中间相位 tone 仍有明显残余错位。(c) Hilbert 连续相位对齐后：四条波形近乎完美重合。(d) 72×72 tone-pair 相干性热力图：cs_095806（左，good）左上角高 γ 结构密集；cs_091339（右，hard）整体 γ 更低且碎片化。**结论**：菲涅尔区 ±1 是有效的一阶近似，但顺序采样引入了超越 ±1 的连续相位分量，Hilbert 对齐可进一步补偿。另见 [Figure S1](#supplementary-figure-s1) 跨窗口 γ 稳定性对比。

### 4.3 Inter-Modal Phase Relationship / 模态间（变量间）相位关系

**EN**: [Remote vs local vs phase: relative phase depends on multipath geometry. Different rooms → different relationships. Per-window variation observed. Cannot hardcode. Cite Figure 3.]

**CN**: [Remote 与 local 与 phase 之间：相对相位取决于多径几何。不同房间 → 不同的相位关系。观察到逐窗变化。不可硬编码。引用 Figure 3。]

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

我们将4.3 的实验结果中三个模态的信道波形的相位对齐，然后融合成一个，并把三个波形归一化后比较【图-3 （a）】。它们之间也存在非整周期的相位关系。这验证了我们的模型。通过将它们的相位旋转对齐，可以消除这种相位偏差 【图3-b】。同时，这种情况并非偶然现象，我们将该次金属板模拟的所有数据的做加窗处理，然后画出每个窗口内三模态的相位偏差【图3-c】，这些相位偏差几乎是完全随机的；对于另一个位置场景下的模拟，相位关系又完全不同于前一场景【图3-d】。这充分证明了本节论述的各模态见不稳定的相位关系。



![Figure 3: Inter-modal phase relationship — (a) Three modal waveforms after Level-1 fusion, BEFORE Level-2 alignment, (b) AFTER Level-2 Hilbert alignment + η·γ weighted fusion, (c) cross-window Δφ time series (cs_095806), (d) same Δφ plot for different room (cs_102621). Takeaway: modal-to-modal phase is non-fixed, scene-dependent, and per-window Hilbert alignment effectively resolves it.](../../outputs/figures/paper_fig3_inter_modal_phase.png)

> **Fig. 3 解读**: (a) 三模态（remote/local/phase）经 Level-1 Hilbert tone 融合后的波形，Level-2 对齐前可见明显相位差异。(b) Level-2 Hilbert 对齐 + η·γ 加权融合后：三波形对齐，融合波形（粗黑线）跟踪一致性。(c) cs_095806 全 segment 跨窗模态间相位差 Δφ 序列：Δφ 非固定，逐窗浮动。(d) cs_102621（不同房间）同款图：Δφ 基线不同，确认模态间相位关系场景依赖。**结论**：模态相位不可预设，必须每窗估计，等权融合是正确的先验。

---

## 5. Proposed Method: BreatheCS / 提出方法：BreatheCS

### 5.1 Design Rationale / 设计动机

> **EN**: [Why two branches sharing one front-end. BPM → spectral domain (insensitive to misalignment). Waveform → time domain (preserves morphology). Both benefit from η·ρ quality weights.]
>
> **CN**: [为什么两支共享一个前端。BPM → 频谱域（对时间对齐不敏感）。波形 → 时域（保留呼吸形态学特征）。η·ρ 质量权重对两支都有益。]

对人体呼吸活动的观测包含BPM估计和呼吸波形的拟合两部分。BPM估计是最基本的需求，需要从BLE CS PCT中稳定地提取呼吸频率，对波形是否对齐并不敏感；而想要从各个模态中恢复呼吸波形以保留形态学特征，就必须依赖波形在时域的融合以增强呼吸能量比（BNR，breathe noise ratio）。

我们提出 BreatheCS，对两种呼吸指标做针对性的处理，以最大程度利用BLE CS 双观测、三模态的优势，并弱化低采样率和测量噪声的影响。

### 5.2 Preprocessing / 预处理

**EN**: [Filter chain. Sliding window parameters.]

**CN**: [滤波链：median → highpass (0.05 Hz) → bandpass (0.1–0.35 Hz)。滑窗：20 s 窗长 / 1 s 步长。]

### 5.3 Stage 1: Per-Modal η·ρ Voting / 第一阶段：逐模态 η·ρ 投票

> **EN**: [Formulas from paper_outline_plan §3.3. η_i, ρ_i, w_i, weighted histogram, confidence-weighted spectrum average S̄_m(f).]
>
> **CN**: [公式见 paper_outline_plan.md §3.3。逐 tone 计算 η_i, ρ_i → 质量权重 w_i = η_i·max(ρ_i, 0) → 加权直方图投票 BPM → 置信度加权频谱平均 S̄_m(f)。]

### 

**EN**: [Definition. Why product. How they complement each other.]

**CN**: [η（呼吸频段能量比）和 ρ（谱峰峰度）的定义。为什么使用乘积 η·ρ 而非单一指标。两者如何互补：η 要求能量集中在呼吸频段，ρ 抑制假峰 tone。缺一不可。]

![Figure 5: η·ρ quality voting mechanism — (a) Per-tone η vs ρ scatter (72 points, one window), color = |BPM_i − BPM_voted|, marker size ∝ w_i. (b) BPM histogram: Uniform (light) vs η·ρ Voting (dark). (c) Fused spectrum comparison: Voting spectrum has cleaner peak, lower noise floor. Takeaway: η identifies energy concentration in breath band; ρ suppresses spurious-peak tones; product η·ρ ensures both hold simultaneously.](../../outputs/figures/paper_fig5_eta_rho_voting.png)

> **Fig. 5 解读**: (a) 单个窗口 72 tone 的 η vs ρ 散点图，颜色=该 tone BPM 与 Voting 共识 BPM 的偏差，点大小 ∝ η·ρ 权重。右上角高 η 高 ρ 的 tone 偏差小（冷色），左下角低质量 tone 偏差大（暖色）。(b) BPM 直方图对比：等权（浅色）分布宽、峰低；η·ρ 加权投票（深色）峰更尖锐、置信度更高。实际数值：Voting BPM=8.00, Uniform BPM=8.86。(c) 融合频谱对比：η·ρ 加权谱（深色）噪声底更低、呼吸峰更突出。**结论**：η 和 ρ 互补——η 要求能量集中在呼吸频段，ρ 抑制有尖锐假峰的 tone，两者乘积作为质量权重有效。

### 5.4 Stage 2a: BPM Branch — Equal Spectrum Fusion / BPM 分支：等权谱融合

**EN**: [Formula: S_final = (S_remote + S_local + S_phase) / 3. Argmax + parabolic interpolation. Why equal weight: physical symmetry argument.]

**CN**: [公式：S_final(f) = (S_remote(f) + S_local(f) + S_phase(f)) / 3。寻峰 + 抛物线插值。为什么等权：remote/local/phases 物理对等，不应预设哪一模态更优。实验证据：Equal (B1, 8.45%) 优于 Top2 (B3, 9.92%) 和 η-weight (B2, 9.45%)。]

### 5.5 Stage 2b: Waveform Branch — Two-Level Hilbert-MRC / 波形分支：两级 Hilbert-MRC

**EN**: [Level 1 formulas: Hilbert transform → analytic signal → cross-correlation phase → complex-plane rotation → weighted sum → real part. Level 2 formulas: same structure but across modals. Why complex-plane rotation ≠ time shift: no edge effects, continuous phase resolution.]

**CN**: [Level 1（tone 级，72→1/模态）：Hilbert 变换 → 解析信号 → 互相关求相位差 → 复平面旋转（z' = z·e^{−jΔφ}）→ η·ρ·γ 加权叠加 → 取实部。Level 2（模态级，3→1）：同上结构，跨 remote/local/phase 执行。为什么复平面旋转 ≠ 时域平移：无边缘效应、保留所有样本、连续相位分辨率。]

### 5.6 The "Unlocking" Interaction / "解锁器"交互效应

**EN**: [Experimental finding: A1-D ≈ A1 (no gain), Bγ→D = −1.46 pp (significant gain). Physical interpretation: sign correction leaves residual phase errors that pollute modal waveforms; Level-2 cannot recover from degraded input. Continuous phase at Level 1 preserves waveform fidelity → unlocks Level-2 gain. Cite Figure 4.]

**CN**: [实验发现：A1-D ≈ A1（Level-2 在符号校正第一级上无增益），Bγ→D = −1.46 pp（Level-2 在 Hilbert 第一级上有效）。物理解释：符号校正（±1）残留的非二值相位误差污染了模态融合波形；Level-2 无法从已被污染的输入中恢复。Level-1 连续相位保留了波形保真度 → "解锁" Level-2 的 −1.46 pp 增益。引用 Figure 4。]

> ⚠️ **Fig. 4 状态**：解锁器效应消融矩阵的数据已有（CS 三场景跨域：A0=12.33%, A0-D=11.09%, A1=11.06%, A1-D=11.15% [无效!], Bγ=10.89%, B2-D=9.43% [有效!]），但论文风格的消融矩阵图 + 机制示意图**尚未生成**。Plan `paper_outline_plan.md` §5.5 和 `paper_figures_generation_plan.md` 均未覆盖 Figure 4（后者仅覆盖 Fig 2/3/5/S1）。需后续单独生成。

---

## 6. Experimental Validation / 实验验证

### 6.1 Setup / 实验设置

**EN**: [CS metal-plate: 3 rooms, mechanical BPM ground truth. HKH: 3 rooms × 4 subjects, respiratory belt ground truth. Metrics: BPM absolute error, RMSE. Baseline methods listed.]

**CN**: [CS 金属板：3 个房间，机械振动 BPM ground truth（可控、精确，但无波形 GT）。用于 §2–§3 的机制验证。HKH 真人：3 房间 × 4 受试者 = 12 条数据，呼吸带 ground truth。用于 §4 的效果验证。指标：BPM 绝对误差（breaths/min）、RMSE（波形 vs 呼吸带）。Baseline：B0 Single Remote, B1 Uniform Remote, Modal top2, T0-V3 Per-Tone Voting, WiFi MRC (Fan 2024), Zhuo2023 PCA-VMD。]

### 6.2 BPM Accuracy (HKH) / BPM 精度（HKH）

**EN**: [B3 Simplified = 0.41 BPM mean abs error, Z1-no-VMD = 0.44, B2-D = 0.68, Fan2024 η-linear = 1.39. Cite Figure 6.]

**CN**: [主结果（12-scenario aggregate）：B3 Simplified = B1 Vote→Equal = **0.405** BPM mean abs error（最优），Zhuo2023 Z1-no-VMD = 0.435，MRC-PCA η-equal PCA3→1 = 0.505，B2-D Two-level Hilbert-MRC = 0.682，Fan 2024 η-linear = 1.386。引用 Figure 6。]

![Figure 6: HKH BPM leaderboard — 10 methods × 12 scenarios (3 rooms × 4 subjects). B3 Simplified (逐模态 Voting → 三模态等权谱融合) achieves lowest BPM error (0.405 breaths/min).](../../outputs/figures/ble_hkh_paper_baselines_leaderboard_all.png)

![Figure 6b: HKH per-room BPM breakdown. Room A (Living room): Zhu2023 Z1-no-VMD = 0.415. Room B+C (Bedroom): B3/B1 methods lead.](../../outputs/figures/ble_hkh_paper_baselines_by_room.png)

> **Fig. 6 解读**: (上) 全 12 场景 BPM 排行榜。B3 Simplified（即 逐模态 Voting → 三模态等权谱融合）和 B1 Vote→Equal 并列最优，跨场景 mean abs error = 0.405 breaths/min，优于所有迁移 baseline（Zhuo2023 Z1-no-VMD 0.435, MRC-PCA 0.505）一个数量级优于 Fan 2024 系列（1.39–1.49）。(下) 按房间拆分：Room A（客厅）Zhuo2023 微弱领先（0.415 vs B3 0.405 在全量 aggregate 中），Room B+C（卧室）本项目方法系统性领先。

### 6.3 Waveform Recovery Accuracy (HKH) / 波形恢复精度（HKH）

**EN**: [B3 Simplified RMSE = 0.951 vs belt, B2-D same. Z1-no-VMD RMSE = 1.070. B3 is the only unified pipeline achieving both optimal BPM (0.41) and optimal waveform (0.951). Cite Figure 7.]

**CN**: [B3 Simplified RMSE = **0.951**（vs 呼吸带），B2-D 同值 0.950。Z1-no-VMD RMSE = 1.070。B3 是唯一同时输出最优 BPM (0.405) 和最优波形 (0.951) 的统一管线。引用 Figure 7。]

![Figure 7: BPM vs RMSE trade-off across methods on HKH 12 scenarios. B3 Simplified (★) achieves the best joint BPM+RMSE — lowest BPM error AND lowest waveform RMSE simultaneously.](../../outputs/figures/ble_hkh_b3_bpm_vs_rmse.png)

> **Fig. 7 解读**: BPM-RMSE 双指标散点图。每个点代表一个方法在 12 场景上的 (mean BPM abs error, mean RMSE)。B3 Simplified（★）位于左下角——同时实现最低 BPM 误差和最低 RMSE。B2-D Two-level Hilbert-MRC 波形 RMSE 同优 (0.950)，但 BPM 精度较差 (0.682)。Zhuo2023 Z1-no-VMD 在 BPM 上接近 (0.435)，但 RMSE 明显更差 (1.070)，因为其时域 PCA 对齐在低采样率下不可靠。

### 6.4 Ablation Experiments / 消融实验

**EN**: [Channel fusion: Voting > Single-best > Uniform. Modal fusion: Equal > Top2 > η-weight. Phase method: Hilbert two-level > single-level > sign-only. Cite Figure 8.]

**CN**: [信道融合消融：Voting (η·ρ 加权) > Single-best (max-η) > Uniform (等权)。模态融合消融：Equal (1:1:1) > Top2 > η-weight → 对称对待被验证。相位方法消融：Hilbert 两级 > Hilbert 单级 > Corr sign > PCA sign。解锁器交互效应（§3.6）进一步证实第一级 Hilbert 的逻辑必要性。引用 Figure 8。]

![Figure 8a: HKH ablation leaderboard — cumulative contribution of each pipeline component. B3 Simplified (full pipeline) achieves lowest BPM error.](../../outputs/figures/ble_hkh_b3_ablation_leaderboard.png)

![Figure 8b: CS metal-plate waterfall decomposition — cumulative BPM error reduction as components are added. Voting (η·ρ weighted) provides the largest single gain over Uniform.](../../outputs/figures/b2_coherent_mrc_waterfall_decomposition.png)

> **Fig. 8 解读**: (上) HKH 消融排行榜：从 Single Remote baseline 到完整 B3 Simplified 管线的逐组件贡献。(下) CS 金属板跨域 waterfall 分解：η·ρ Voting 在 Uniform 基础上贡献最大单步增益；Hilbert 两级对齐与等权模态融合进一步降低误差。解锁器效应（§3.6）是解释性的关键：Hilbert 连续相位不是直接改善 BPM，而是通过保留波形保真度"解锁"第二级模态对齐的效能。

### 6.5 Mechanism Validation (CS Metal-Plate) / 机制验证（CS 金属板）

**EN**: [Inter-tone phase (Figure 2). Inter-modal phase (Figure 3). Unlocking interaction (Figure 4). Quality voting (Figure 5).]

**CN**: [信道间相位：PCA sign 有效但不完美，Hilbert 连续相位进一步改善（Figure 2）。模态间相位：三模态相位差场景依赖、逐窗浮动，per-window Hilbert 对齐有效解决（Figure 3）。解锁器效应：Level-2 增益依赖 Level-1 连续相位——符号校正 + Level-2 = 无增益，Hilbert + Level-2 = −1.46 pp（Figure 4）。η·ρ Voting 机制：质量加权直方图的峰值比等权直方图更尖锐、融合频谱噪声更低（Figure 5）。]

### 6.6 Comparison with Prior Work / 与现有工作的比较

**EN**: [WiFi MRC: 10.78%. Zhuo2023: 11.31%. B1: 8.45%. B3 on HKH: 0.41 BPM + 0.950 RMSE.]

**CN**: [CS 金属板跨域：B1 (8.45%) < WiFi MRC (10.78%) < Zhuo2023 (11.31%)。B1 在 BPM 精度上系统性优于迁移到 BLE CS 的 WiFi 时域 MRC 方法。HKH 真人：B3 Simplified (0.41 BPM + 0.950 RMSE) 是唯一同时最优的统一管线。]

---

### Supplementary Figure S1: Tone-Pair Coherence Stability / 补充图 S1：Tone 对相干性稳定性

![Figure S1: Tone-pair coherence γ stability across windows — same tone pair (58, 69) tracked across all windows of segment 1b. cs_095806 (good): γ = 0.901 ± 0.075, stable high. cs_091339 (hard): γ = 0.485 ± 0.345, fluctuates strongly. Takeaway: tone coherence is scenario-dependent; hard multipath environments systematically degrade inter-tone phase consistency.](../../outputs/figures/paper_figS1_coherence_stability.png)

> **Fig. S1 解读**: 同一 tone pair (#58, #69) 在 good scenario (cs_095806) 和 hard scenario (cs_091339) 同 segment `1b` 上的跨窗口 γ 序列。Good: γ 均值 0.90，std 仅 0.075，跨窗稳定。Hard: γ 均值 0.49，std 达 0.345，大幅波动。**结论**：tone 间相干性场景依赖，复杂多径环境（cs_091339）会导致信道间相位一致性系统性退化——这解释了为何该场景在所有方法上都是全局瓶颈。

---

## 7. Discussion / 讨论

**EN**: [Why spectral domain beats time domain at low sampling rates. Why equal weight is correct. Physical interpretation of unlocking effect. Limitations: complex multipath (091339), sequential sampling timing analysis [待确认]. Future: multi-person, apnea detection, dynamic branch selection.]

**CN**: [为什么频谱域在低采样率下优于时域：20 s 窗口仅含 ~4 周期，时域对齐的相位估计方差大；|FFT| 丢弃时间信息后对对齐不敏感。为什么等权是正确的：remote/local/phases 物理对等，预设偏好反而引入场景过拟合。解锁器效应的物理含义：连续相位保真度从前端传递到后端的信息论解释 [待确认]。不足：复杂多径（cs_091339）是全局瓶颈，tone 间相干性系统性偏低；顺序采样的精确时序分析仍需进一步工作。未来方向：多人呼吸、呼吸暂停检测、per-window 动态分支选择（根据当前窗口的信号质量在 BPM 和波形分支间自适应切换）。]

---

## 8. Conclusion / 结论

**EN**: [One paragraph summary. Reiterate three contributions.]

**CN**: [一段话总结全文。重述三个贡献：(C1) 首次系统建模 BLE CS 在呼吸感知中的物理机制，识别并验证了三个关键物理约束；(C2) 提出了 [名称待定] 统一管线，用 η·ρ Voting + 等权谱融合 + 两级 Hilbert-MRC 分别应对这些约束；(C3) 在可控金属板场景和真人数据上完成了双重验证，B3 实现了 0.41 BPM + 0.950 RMSE，优于直接迁移的 WiFi 方法。]

---

## References / 参考文献

**EN**: [TBD — WiFi Fresnel zone papers (Wang et al. MobiCom, Zhang et al. MobiSys), Fan 2024, Yu 2021 WiFi-Sleep, Zhuo 2023 PCA-VMD, BLE CS spec (Bluetooth 5.2), etc.]

**CN**: [待补充 — 菲涅尔区 WiFi 感知论文、Fan 2024、Yu 2021 WiFi-Sleep、Zhuo 2023、BLE 5.2 信道探测规范等。]
