\section{Introduction}
\label{sec:introduction}

\subsection{Motivation and Application Context}
\label{subsec:intro_motivation}

Respiration is a fundamental physiological signal for sleep monitoring, chronic disease management, and the early detection of respiratory abnormalities. Conventional monitoring methods typically rely on respiratory belts, electrodes, or dedicated radar hardware \cite{yang2022artificial}. Although these approaches have been widely adopted, their requirements for dedicated hardware and appropriate sensor placement or attachment can make long-term and pervasive deployment challenging.

Wireless sensing using commodity communication devices offers an alternative. Reusing communication hardware can reduce the need for additional sensing equipment, while contactless measurements remove the requirement to wear a sensor. In recent years, sensing with commodity wireless technologies, including Wi-Fi \cite{zhang2024wi} and LoRa \cite{zhang2020exploring}, has been extensively investigated. However, many existing approaches require hardware or software modifications to extract fine-grained sensing information, and such modifications are supported by only a limited range of devices. Another practical issue is that devices in residential monitoring environments cannot always be positioned as favorably as those in laboratory experiments. Expanding the range of available sensing technologies can therefore broaden the conditions under which wireless sensing is feasible. Among potential alternatives, Bluetooth Low Energy (BLE) is widely deployed in smartphones, wearables, embedded devices, and Internet of Things (IoT) systems, making it a promising platform for pervasive sensing.

\subsection{Opportunities and Challenges of BLE Channel Sounding}
\label{subsec:intro_cs}

Conventional BLE sensing has primarily relied on coarse measurements such as the received signal strength indicator (RSSI), and previous studies have reported limitations in its sensing capability \cite{ble_rssi_sensing_placeholder}. The introduction of Channel Sounding (CS) in Bluetooth Core 6.0 changes this situation \cite{bluetooth6}. CS is a ranging technology designed to estimate the distance between two devices using phase-based ranging (PBR) and round-trip timing (RTT) \cite{bluetooth_channel_sounding}. Although CS was not designed for sensing, it provides two capabilities that are important for fine-grained BLE sensing. First, CS-capable devices can measure the amplitude and phase of received signals. Second, CS supports configurable measurements over up to 72 frequency channels, allowing observations to be associated with individual channels rather than mixing measurements from uncontrolled frequency hopping. These capabilities enable the tracking of sensing-related channel variations, including those induced by respiration.

Despite the opportunities that CS creates for BLE sensing \cite{wang2025exploration,paulikas2026exploring}, its measurement structure does not directly match sensing requirements. Because CS was developed for ranging, its design emphasizes security and ranging accuracy. First, obtaining a usable phase observation requires bidirectional phase correction term (PCT) measurements, whereas sensing does not necessarily require phase information. Second, in the implementation considered here, the remote measurements must be transferred through a BLE application-layer ranging service before the two endpoints' observations can be combined. Both requirements reduce the measurement update rate. Nevertheless, CS offers an important advantage: it exposes measurements through a standardized interface. Access to CS measurements does not require proprietary physical-layer interfaces or modifications outside the BLE specification.

\subsection{Overview and Contributions}
\label{subsec:intro_contributions}

To investigate the sensing potential of CS, we use respiration monitoring as a representative task and propose BreatheCS, a respiration sensing framework tailored to BLE CS. BreatheCS extracts respiration-sensitive time series from bidirectional channel measurements and jointly uses amplitude and phase observations. It also accounts for differences in reliability across channels and observation modalities through adaptive fusion.

A key design choice is to process respiratory-rate estimation and waveform reconstruction separately, as illustrated in Fig.~\ref{fig:overview}. For respiratory-rate estimation, BreatheCS performs quality-weighted aggregation across channels in the spectral domain, followed by adaptive fusion and selection based on respiratory-band energy concentration. For waveform reconstruction, it aligns channel waveforms and combines them coherently to recover the respiratory waveform from the available observations.

We evaluate BreatheCS using 24 human recordings collected from eight participants under three indoor sensing scenarios and compare it with representative methods from recent studies. BreatheCS achieves a mean absolute respiratory-rate error of 0.371 breaths/min and a normalized waveform root-mean-square error (RMSE) of 0.937, obtaining the best results among the evaluated methods. The results also show that multi-channel CS measurements improve the robustness of respiration sensing. Although phase information is advantageous in some wireless sensing systems, the composite-phase observation in our CS measurements is less robust than the endpoint-amplitude observations.

% TODO: Reconcile the eight participants and 24 recordings reported here
% with the four participants and 12 recordings reported in the evaluation
% and conclusion.

The contributions of this work are summarized as follows:
\begin{enumerate}
    \item \textbf{BLE CS respiration observation modeling and empirical characterization.}
    We formulate bidirectional PCT measurements as two endpoint-amplitude observations and one composite-phase observation, and characterize their sensitivity to respiration and their relationships across channels.

    \item \textbf{Task-specific, reliability-aware fusion.}
    We develop BreatheCS with separate fusion strategies for respiratory-rate estimation and waveform reconstruction to address sparse sampling, multipath-dependent offsets, and heterogeneous channel reliability.
    
    \item \textbf{Experimental assessment of BLE CS sensing.}
    We show that frequency-channel diversity provides the largest and most consistent improvement in respiration monitoring, whereas composite phase is generally less robust than endpoint amplitudes.
\end{enumerate}

The remainder of this paper is organized as follows. Section~\ref{sec:related_work} reviews related work. Section~\ref{sec:preliminaries} introduces BLE Channel Sounding. Section~\ref{sec:observation_model} develops the respiration observation model. Section~\ref{sec:method} presents BreatheCS. Section~\ref{sec:evaluation} reports the experimental evaluation. Section~\ref{sec:discussion} discusses the findings and future directions, and Section~\ref{sec:conclusion} concludes the paper.

% Insert the system overview here.
% \begin{figure*}[t]
%     \centering
%     \includegraphics[width=\textwidth]{figures/system_overview.pdf}
%     \caption{Overview of BLE CS respiration sensing and the BreatheCS
%     pipeline.}
%     \label{fig:overview}
% \end{figure*}


\section{Related Work}
\label{sec:related_work}

\subsection{Device-Free RF Sensing}
\label{subsec:related_rf}

A wide range of sensors has been used to monitor human activity, with respiration monitoring playing an important role in disease prevention and sleep assessment \cite{yang2022artificial}. Radio-frequency (RF) sensing offers distinctive advantages because it can provide contactless measurements without acquiring visual imagery \cite{liu2020human}.

RF sensing systems can be broadly categorized into systems that transmit dedicated sensing waveforms and systems that reuse communication signals \cite{iannizzotto2022perspective}. The former include ultra-wideband (UWB) radar \cite{shyu2018detection} and frequency-modulated continuous-wave (FMCW) radar \cite{yao2024non}. Their relatively large bandwidths provide high range resolution and support fine-grained activity sensing. For example, radar-based systems can distinguish motion associated with different body parts \cite{shyu2018detection}. The latter reuse technologies such as Wi-Fi \cite{zeng2018fullbreathe}, LoRa \cite{zhang2020exploring}, BLE \cite{wang2025exploration}, and IEEE 802.15.4 \cite{patwari2013monitoring}. Reusing commodity communication infrastructure can reduce deployment costs and facilitate broader adoption.

\subsection{Sensing with Commodity Communication Devices}
\label{subsec:related_commodity}

Sensing with commodity communication devices extracts information about human activity from changes in RF propagation during communication \cite{youssef2007challenges,pahlavan2013principles}. Wi-Fi was among the first technologies to receive extensive attention because selected network interface cards and drivers can report detailed channel state information (CSI) \cite{liu2015contactless}. CSI describes the channel response over multiple orthogonal frequency-division multiplexing (OFDM) subcarriers, enabling human activity to be inferred from changes in those responses.

Compared with RSSI, CSI provides finer-grained channel information and has enabled more effective activity monitoring \cite{ma2019wifi,liu2015contactless,iannizzotto2022perspective,wang2016wifall,wang2016human}. Subsequent studies extracted more stable phase features through CSI differences or ratios across antennas, further improving respiration monitoring and activity sensing \cite{wang2017phasebeat,wu2022wifi,zeng2019farsense,ma2018signfi,ma2019wifi,zeng2018fullbreathe}. Phase-difference and CSI-ratio features have consequently become important tools for fine-grained wireless sensing \cite{wu2020fingerdraw,zeng2019farsense,gao2021towards,chen2024wiphase}.

Other communication technologies have also attracted interest. LoRa was designed for long-range IoT communication, and its modulation supports sensing over comparatively long distances. LoRa-based sensing studies have reported sensing ranges exceeding 10~m \cite{zhang2020exploring}. IEEE 802.15.4 was investigated in early wireless sensing work, but the limited measurement information available from commodity devices, typically RSSI, constrains its sensing capability \cite{patwari2013monitoring}. Despite its widespread deployment, conventional BLE has faced a similar limitation because fine-grained channel measurements were not readily accessible \cite{iannizzotto2022perspective}.

\subsection{Device-Free Sensing with BLE Channel Sounding}
\label{subsec:related_ble}

BLE was primarily designed for short-range wireless connectivity and is widely used in IoT systems \cite{iotbusinessnews_state_of_iot_2025_21_1b}. Its frequency-hopping operation introduces channel-dependent variation into RSSI measurements \cite{falsafi1996transmission}. Obtaining stable observations for sensing can therefore require device-specific modifications or additional processing \cite{huang2019robust,iannizzotto2022perspective}.

Bluetooth 5.1 introduced Direction Finding (DF), which added support for physical-layer measurements through in-phase and quadrature (IQ) sampling \cite{bluetooth5.1overview,zand2019high}. This capability enabled finer-grained BLE sensing \cite{zhang2023bleselect,taniguchi2024device}. However, DF measurements remain associated with communication channels governed by the frequency-hopping procedure, limiting direct control over repeated measurements on individual channels.

Bluetooth 6.0 introduced CS, including PBR. CS-PBR requires two devices to perform bidirectional channel measurements at multiple frequencies to estimate their separation \cite{zand2019high,Kastnes_NDT_2023}. Several studies have investigated improvements to phase-based ranging and CS ranging performance \cite{schroder2019investigation,santra2024enhancing,tsemko2025data,de2024multipath,wieme2025performance}. Nevertheless, the use of these richer observations and the bidirectional measurement procedure for device-free respiration sensing remains insufficiently explored \cite{tian2023bluebreathe,paulikas2026exploring}.

Beyond the deployment potential of BLE, CS can report measurement results through the standard Host Controller Interface (HCI) \cite{BluetoothCore6.0Overview}. This provides a standardized measurement interface on CS-capable platforms, without requiring proprietary CSI extraction mechanisms. It also differs from beamforming-feedback-based sensing approaches that use an additional sniffer to collect measurements \cite{yi2024bfmsense}. Table~\ref{tab:rf_comparison} summarizes representative wireless sensing technologies and their advantages and limitations.

% TODO: Insert the platform-comparison table with
% \label{tab:rf_comparison}. The Chinese draft refers to this table
% but does not provide its contents.

This work uses respiration monitoring as a representative application to investigate BLE CS sensing. We develop an observation model, characterize the resulting sensing properties, and design BreatheCS to account for the CS measurement structure. These analyses and experiments provide an initial assessment of the potential of BLE CS for device-free sensing.


\section{Preliminaries}
\label{sec:preliminaries}

\subsection{Channel Sounding Measurements}
\label{subsec:cs_measurements}

Bluetooth 6.0 introduces CS with support for two ranging mechanisms: RTT, which uses signal timing, and PBR, which uses signal phase. This work focuses on PBR because its amplitude- and phase-related measurements are relevant to respiration sensing. We refer to CS-PBR as CS in the remainder of this paper.

Before conducting CS measurements, two devices establish a connection and assume the initiator and reflector roles. Measurements are then performed across the BLE frequency band with a channel spacing of 1~MHz. After excluding reserved channels, up to 72 CS channels are available.

For each channel measurement, both devices transmit a CS tone to the other endpoint. The receiving endpoint measures the tone in IQ form, producing a complex PCT observation. After the measurement event, the two endpoints' PCT observations are collected through the ranging service.

The two PCT observations are multiplied to compensate for the local-oscillator (LO) phase offset between the devices. Let the LO phase offset be
\begin{equation}
    \Delta \theta_{\mathrm{LO}}
    =
    2\pi F(\varphi_i-\varphi_r),
    \label{eq:lo_offset}
\end{equation}
where $F$ is the channel frequency, and $\varphi_i$ and $\varphi_r$ are the timing offsets of the initiator and reflector relative to a common time reference.

Consider a CS tone transmitted by the initiator and received by the reflector after a propagation delay $\tau$. When the initiator is the endpoint that aggregates the measurements, the reflector is referred to as the remote endpoint. Its recorded phase is
\begin{equation}
    \theta_{\mathrm{INI}\rightarrow\mathrm{REF}}
    =
    2\pi F\tau+\Delta\theta_{\mathrm{LO}}.
    \label{eq:remote_pct_phase}
\end{equation}

The transmission direction is then reversed: the reflector transmits a CS tone, and the initiator records the local PCT phase,
\begin{equation}
    \theta_{\mathrm{REF}\rightarrow\mathrm{INI}}
    =
    2\pi F\tau-\Delta\theta_{\mathrm{LO}}.
    \label{eq:local_pct_phase}
\end{equation}

Adding the two phases cancels the unknown LO phase offset. Because the PCT observations are complex-valued, their multiplication directly produces this phase sum. The resulting sensing observables are the local PCT amplitude, the remote PCT amplitude, and the composite phase, denoted by
\begin{equation}
    A_{\mathrm{Local}},\qquad
    A_{\mathrm{Remote}},\qquad
    \Phi.
    \label{eq:three_observables}
\end{equation}

The magnitude of the complex product is simply the product of the two endpoint amplitudes. It does not introduce an additional physical observable and is therefore not considered separately in this work.

\subsection{Effective Sampling Rate}
\label{subsec:sampling_rate}

Although CS is designed for ranging, its operation must coexist with the BLE communication procedure. CS measurements are organized into procedures, events, subevents, and steps. A CS procedure may contain multiple events, and a step performs the relevant measurement operations on a selected channel.

In our configuration, one bidirectional channel measurement takes approximately $300~\mu\mathrm{s}$. Measuring all 72 channels therefore requires approximately 21~ms, excluding additional scheduling and data-transfer overhead. The remote PCT observations must also be returned to the measurement-aggregation endpoint through the ranging service, which introduces further overhead.

Repeated tests on Nordic nRF54L15 devices showed that the shortest practical measurement interval in our implementation was approximately 250~ms. For sustained operation, we relaxed the upper interval bound to avoid interruptions during long recordings. The resulting measurement intervals were typically between 250 and 500~ms, corresponding to an effective sampling rate of approximately 2--4~Hz.

This sampling rate is sufficient to cover the respiratory frequency band considered in this work under the Nyquist criterion, making respiratory-rate estimation feasible. However, the limited number of observations per window must be considered when reconstructing and aligning respiratory waveforms.


\section{Respiratory Observation Model}
\label{sec:observation_model}

This section develops an observation model for respiration sensing with BLE CS. We first identify the available physical observables. We then examine the relationships among respiratory waveforms across channels and modalities to guide their fusion. In particular, we investigate within-modality channel relationships and assess whether sequential channel scanning introduces appreciable respiratory phase offsets. Finally, we extend the model to multiple effective respiratory components to explain continuous phase differences across modalities and motivate the proposed coherent fusion strategy.

\subsection{Usable Observables}
\label{subsec:usable_observables}

Section~\ref{subsec:cs_measurements} describes the measurements available from one CS exchange. For respiration sensing, repeated exchanges produce time series of these measurements.

For each CS channel $i$, the two complex PCT observations are
\begin{equation}
    Z_{l,i}(t),\qquad Z_{r,i}(t),
    \label{eq:pct_sequences}
\end{equation}
where $l$ and $r$ denote the local and remote endpoints, respectively, and $t$ denotes slow time.

Three respiratory sensing variables are derived:
\begin{subequations}
\label{eq:observable_sequences}
\begin{align}
    A_{l,i}(t)
    &=
    |Z_{l,i}(t)|,
    \label{eq:local_amplitude}
    \\
    A_{r,i}(t)
    &=
    |Z_{r,i}(t)|,
    \label{eq:remote_amplitude}
    \\
    \Phi_i(t)
    &=
    \operatorname{unwrap}
    \left[
        \angle\left(Z_{l,i}(t)Z_{r,i}(t)\right)
    \right].
    \label{eq:composite_phase}
\end{align}
\end{subequations}

The two amplitude variables describe observations at the individual endpoints, whereas $\Phi_i(t)$ is a composite-phase observation. To examine their physical meanings, consider a respiration-induced perturbation around a quasi-static operating point:
\begin{equation}
    Z_{d,i}(t)
    =
    \overline{Z}_{d,i}
    +
    \delta Z_{d,i}(t),
    \qquad d\in\{l,r\},
    \label{eq:pct_perturbation}
\end{equation}
where $d$ indexes the endpoint, $\overline{Z}_{d,i}$ is the quasi-static component, and $\delta Z_{d,i}(t)$ is the respiration-induced perturbation.

When
$|\delta Z_{d,i}(t)|\ll|\overline{Z}_{d,i}|$,
the normalized amplitude perturbation is approximately
\begin{equation}
    \frac{\delta A_{d,i}(t)}{\overline{A}_{d,i}}
    \approx
    \operatorname{Re}
    \left\{
        \frac{\delta Z_{d,i}(t)}
        {\overline{Z}_{d,i}}
    \right\},
    \label{eq:amplitude_projection}
\end{equation}
where $\overline{A}_{d,i}=|\overline{Z}_{d,i}|$.

The composite-phase perturbation is approximately
\begin{equation}
    \delta\Phi_i(t)
    \approx
    \operatorname{Im}
    \left\{
        \frac{\delta Z_{l,i}(t)}{\overline{Z}_{l,i}}
        +
        \frac{\delta Z_{r,i}(t)}{\overline{Z}_{r,i}}
    \right\}.
    \label{eq:phase_projection}
\end{equation}

Thus, the amplitude variables reflect radial projections of the complex perturbations, whereas composite phase reflects the sum of their tangential projections. We therefore treat local amplitude, remote amplitude, and composite phase as three related observation modalities that provide different projections of respiratory motion.

\subsection{CS Waveforms under a Single Motion Component}
\label{subsec:single_component}

We use a moving metal plate to emulate chest displacement and examine whether local amplitude, remote amplitude, and composite phase capture respiratory-like motion. The experiments also assess the relationships predicted by Section~\ref{subsec:usable_observables}.

\subsubsection{Single-component model}

Consider a limiting case in which the respiration-induced perturbation is dominated by a single effective displacement component:
\begin{equation}
    \xi(t)
    =
    X\cos(\omega_b t+\psi),
    \label{eq:single_displacement}
\end{equation}
where $X$ is the displacement amplitude, $\psi$ is the initial phase, and $\omega_b$ is the respiratory angular frequency. The subscript $b$ denotes breathing.

Near the operating point, the PCT perturbation is assumed to depend linearly on displacement:
\begin{equation}
    \delta Z_{d,i}(t)
    =
    V_{d,i}\xi(t),
    \qquad d\in\{l,r\},
    \label{eq:displacement_sensitivity}
\end{equation}
where $V_{d,i}$ is the complex displacement sensitivity of the PCT observation.

Define the normalized complex sensitivity as
\begin{equation}
    \frac{V_{d,i}}{\overline{Z}_{d,i}}
    =
    u_{d,i}+jv_{d,i},
    \label{eq:normalized_sensitivity}
\end{equation}
where $u_{d,i}$ and $v_{d,i}$ are real-valued radial and tangential sensitivity coefficients.

The three respiratory observations are then
\begin{equation}
\begin{aligned}
    y_{l,i}(t)
    &=
    u_{l,i}\xi(t),
    \\
    y_{r,i}(t)
    &=
    u_{r,i}\xi(t),
    \\
    y_{\phi,i}(t)
    &=
    \left(v_{l,i}+v_{r,i}\right)\xi(t).
\end{aligned}
\label{eq:single_component_modalities}
\end{equation}

Let
\begin{equation}
\begin{aligned}
    k_{l,i}&=u_{l,i},\\
    k_{r,i}&=u_{r,i},\\
    k_{\phi,i}&=v_{l,i}+v_{r,i}.
\end{aligned}
\label{eq:real_modal_sensitivity}
\end{equation}
For modality $m\in\{l,r,\phi\}$, the observation can therefore be written as
\begin{equation}
    y_{m,i}(t)
    =
    k_{m,i}X\cos(\omega_b t+\psi).
    \label{eq:single_component_waveform}
\end{equation}

Its amplitude is $|k_{m,i}|X$, and its phase depends on the sign of $k_{m,i}$:
\begin{equation}
    \varphi_{m,i}
    =
    \begin{cases}
        \psi, & k_{m,i}>0,\\
        \psi+\pi, & k_{m,i}<0.
    \end{cases}
    \label{eq:binary_phase}
\end{equation}

If $|k_{m,i}|\approx 0$, the observation contains little respiratory energy, and its estimated phase becomes unreliable. Under this single-component linear model, waveforms across channels or modalities can therefore be in phase, in antiphase, or weakly responsive. Binary sign correction is theoretically sufficient in this limiting case.

\subsubsection{Experimental setup}

We constructed a BLE CS sensing platform in an open corridor approximately 5~m wide, as illustrated in Fig.~\ref{fig:metal_setup}. Both endpoints used Nordic nRF54L15 development kits connected to external antennas with a gain of 6~dBi. The endpoints were placed 1~m apart and aligned in height with a $30\times30~\mathrm{cm}^2$ metal plate.

One device served as the initiator and the other as the reflector. The initiator aggregated the measurements from both endpoints and transferred them to a laptop through a serial connection. All 72 CS channels were enabled, and the measurement interval was configured within a range of 250--500~ms. An interval of 250~ms was the shortest practical setting obtained in our implementation. However, sustained operation at this interval could lead to synchronization failures and interrupted measurements. We therefore allowed an upper bound of 500~ms to accommodate occasional delays.

The plate moved periodically over a 1~cm range to emulate respiratory displacement. Its initial distance from the line-of-sight (LoS) link between the endpoints was 100~cm. After six motion cycles, the plate was advanced by 1~cm along the rail, and the six-cycle sequence was repeated. This procedure allowed us to observe how the endpoint-amplitude and composite-phase waveforms changed with sensing geometry.

% Insert the metal-plate setup photograph here.
% \begin{figure}[t]
%     \centering
%     \includegraphics[width=\linewidth]{figures/metal_plate_setup.pdf}
%     \caption{Controlled metal-plate setup for characterizing BLE CS
%     respiratory observations.}
%     \label{fig:metal_setup}
% \end{figure}

\subsubsection{Differences across modalities}

Figure~\ref{fig:amp_phase_complement} compares the three modalities on a representative channel across plate positions. As the plate position changes, the observed responses vary periodically and exhibit complementary sensitivity. Positions with weak amplitude responses can exhibit stronger composite-phase responses, and vice versa. This behavior is consistent with the radial and tangential projections in
\eqref{eq:amplitude_projection} and \eqref{eq:phase_projection}.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {./assets/image-20260811170120543.png}
    \caption{Local-amplitude, remote-amplitude, and composite-phase
    waveforms on a representative CS channel at successive metal-plate
    positions.}
    \label{fig:amp_phase_complement}
\end{figure}

\subsubsection{Channel-dependent responses}

Figure~\ref{fig:channel_position_matrix} compares amplitude waveforms on channels 20, 40, and 60 at plate distances of 86, 87, and 88~cm. At 88~cm, all three channels show regular periodic responses. After the plate moves to 87~cm, the respiratory response on channel 40 becomes less distinct. At 86~cm, channel 60 exhibits waveform distortion and additional peaks, whereas the other channels retain more regular responses.

These observations indicate that PCT amplitude responses depend on both frequency channel and target position. Changes in geometry can affect the sensing quality of different channels differently, motivating the use of channel diversity rather than a fixed channel.

We further compare channels within one modality at a fixed plate position. As shown in Fig.~\ref{fig:channel_waveforms}, some waveforms are approximately in phase, whereas others are in antiphase.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/position_sweep_figB2_channel_position_matrix.png}
    \caption{Channel-dependent respiratory waveforms on channels 20,
    40, and 60 at successive metal-plate positions.}
    \label{fig:channel_position_matrix}
\end{figure}

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/position_sweep_figC1_hard_remote.png}
    \caption{Remote-amplitude waveforms from selected CS channels at
    a fixed metal-plate position.}
    \label{fig:channel_waveforms}
\end{figure}

\subsubsection{Non-binary phase differences across modalities}

The relationships among modalities are not limited to phase differences of zero or $\pi$. Figure~\ref{fig:modal_phase_position} tracks inter-modal phase differences across plate positions for channels 20, 40, and 60. The endpoint-amplitude waveforms are approximately aligned at most positions, while the amplitude and composite-phase waveforms are often approximately in phase or in antiphase.

At some positions, however, the endpoint-amplitude phase difference deviates from zero, and the amplitude--phase differences are not integer multiples of $\pi$. These observations indicate that continuous residual phase offsets can occur among BLE CS respiratory observations.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/position_sweep_figD2_dphi_vs_position_ch20_40_60.png}
    \caption{Inter-modal phase differences as a function of metal-plate
    position for channels 20, 40, and 60.}
    \label{fig:modal_phase_position}
\end{figure}

\subsubsection{Metal-plate motion versus human respiration}

We also collected data from four seated participants at fixed distances from the LoS link, with distance measured relative to the chest. Participants followed a metronome at the same respiratory rate used for the metal plate. Metal-plate measurements were then repeated at the corresponding distances to compare the resulting waveforms.

We use two spectral measures to characterize waveform quality: respiratory-band energy concentration $\eta$ and spectral peak prominence $\rho$. The former measures the proportion of signal energy within the respiratory band, while the latter measures the concentration of respiratory-band energy around the dominant spectral peak.

Let $P_{m,i}^{\mathrm{hp}}(f)$ be the power spectrum after high-pass filtering and $P_{m,i}(f)$ the power spectrum after respiratory bandpass filtering. Let $\mathcal{F}_b$ denote the respiratory frequency band and $\mathcal{F}$ the frequency range used for the energy calculation. The two measures are
\begin{equation}
    \eta_{m,i}
    =
    \frac{
        \sum_{f\in\mathcal{F}_b}P_{m,i}^{\mathrm{hp}}(f)
    }{
        \sum_{f\in\mathcal{F}}P_{m,i}^{\mathrm{hp}}(f)
        +\epsilon
    },
    \label{eq:eta}
\end{equation}
and
\begin{equation}
\begin{aligned}
    \rho_{m,i}
    &=
    \frac{
        P_{m,i}(\widehat{f}_{m,i})
    }{
        \dfrac{1}{|\mathcal{F}_b|}
        \sum_{f\in\mathcal{F}_b}P_{m,i}(f)
        +\epsilon
    },
    \\
    \widehat{f}_{m,i}
    &=
    \arg\max_{f\in\mathcal{F}_b}P_{m,i}(f),
\end{aligned}
\label{eq:rho}
\end{equation}
where $\epsilon$ is a small positive constant that prevents division by zero, and $|\mathcal{F}_b|$ denotes the number of spectral bins in the respiratory band.

Figure~\ref{fig:metal_human_quality} compares the two measures for metal-plate motion and human respiration. Respiratory-band energy concentration is broadly comparable between the two targets, with no pronounced reduction across the modalities. Spectral peak prominence, however, decreases more noticeably for human respiration. A possible explanation is that natural respiration contains rate variation, harmonics, and incidental body motion. Its energy can remain within the respiratory band even when the dominant spectral peak becomes less concentrated.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/position_sweep_figE3_eta_rho_comparison.png}
    \caption{Comparison of respiratory-band energy concentration
    $\eta$ and spectral peak prominence $\rho$ between metal-plate
    motion and human respiration.}
    \label{fig:metal_human_quality}
\end{figure}

The following subsections use these observations to examine waveform phase relationships within and across modalities.

\subsection{Inter-Channel Waveform Phase Relationships}
\label{subsec:inter_channel}

Different CS channels operate at different frequencies and therefore exhibit different responses to the same respiratory motion. Within one modality, the channels share the same type of physical observation. Under a Fresnel-zone interpretation, the zone boundaries vary with frequency, leading to approximately in-phase or antiphase responses to a common small displacement \cite{wifi_fresnel_model_placeholder}. Accordingly, some wireless sensing methods assign a binary sign to each channel before coherent combination \cite{wifi_channel_sign_fusion_placeholder}.

Combining \eqref{eq:pct_perturbation} and
\eqref{eq:displacement_sensitivity} gives the local linear model
\begin{equation}
    Z_{d,i}(t)
    \approx
    \underbrace{\overline{Z}_{d,i}}_{\text{static}}
    +
    \underbrace{V_{d,i}\xi(t)}_{\text{dynamic}}.
    \label{eq:channel_linear_model}
\end{equation}

After removal of the static component and projection onto a real-valued observation, the response is governed by the real coefficient $k_{m,i}$ defined in
\eqref{eq:real_modal_sensitivity}. For two channels $i$ and $j$ within modality $m$, $k_{m,i}k_{m,j}>0$ gives in-phase responses, whereas $k_{m,i}k_{m,j}<0$ gives antiphase responses. If either coefficient is close to zero, the corresponding channel is weakly responsive.

% Mathematical correction: sign comparisons apply to the real-valued
% observation coefficients k_{m,i}, not to the complex PCT
% sensitivity coefficients V_{d,i}.

The measurements also reveal phase relationships beyond this binary model. Figure~\ref{fig:inter_channel_phase}(a) shows four representative channel waveforms from one modality. Binary sign correction based on principal component analysis (PCA) successfully reverses antiphase waveforms, but residual phase offsets remain, as shown in Fig.~\ref{fig:inter_channel_phase}(b). Hilbert-transform-based phase estimation and complex-plane rotation further improve waveform alignment, as shown in Fig.~\ref{fig:inter_channel_phase}(c).

These observations indicate that the single-component model does not fully describe practical measurements. Several factors may contribute to residual phase differences:
\begin{itemize}
    \item \textbf{Sparse and potentially irregular sampling.}
    At low CS event rates, finite-window filtering and interpolation can be sensitive to timing uncertainty, noise, and boundary effects, producing or amplifying apparent waveform misalignment.

    \item \textbf{PCT measurement non-idealities.}
    Receiver gain or delay variation, phase estimation errors at finite signal-to-noise ratios, calibration residuals, and subsequent processing can affect the observed waveforms.
    
    \item \textbf{Frequency-selective multipath.}
    Different channels experience different combinations of propagation paths and therefore different complex operating points. Residual phase relationships can consequently vary across channel pairs and sensing environments.
\end{itemize}

The contribution of sequential channel scanning is comparatively small under our configuration. A channel measurement takes approximately 300--$400~\mu\mathrm{s}$. Even using the conservative value of $400~\mu\mathrm{s}$, scanning all 72 channels takes less than 30~ms. At the upper respiratory-band frequency of $f_b=0.35~\mathrm{Hz}$, the corresponding phase difference is bounded by
\begin{equation}
\begin{aligned}
    \Delta\varphi_{\mathrm{scan}}
    &\leq
    2\pi f_b
    \left(72\times400~\mu\mathrm{s}\right)
    \\
    &\approx
    0.063~\mathrm{rad}
    \approx
    3.6^\circ.
\end{aligned}
\label{eq:scan_phase_bound}
\end{equation}

This bound is too small to account for the larger continuous residual offsets observed in the measurements. We therefore treat the channel observations as approximately simultaneous for respiration sensing.

We model inter-channel relationships as a dominant binary sign relationship with an additional window-dependent continuous phase residual. Complex-plane rotation compensates for this residual before coherent combination. Although binary sign correction removes the principal antiphase relationship, continuous alignment can further improve waveform reconstruction \cite{respiration_waveform_alignment_placeholder}.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {./assets/paper_fig2_inter_tone_phase.png}
    \caption{Inter-channel waveform phase relationships within one
    modality. (a) Bandpass-filtered waveforms from four representative
    channels. (b) Waveforms after PCA-based binary sign correction.
    (c) Waveforms after Hilbert-transform-based continuous phase
    alignment. Channel 58 is used as the reference; channel 45 is
    approximately in antiphase, whereas channel 69 exhibits an
    intermediate phase offset of approximately $-0.83$~rad.}
    \label{fig:inter_channel_phase}
\end{figure}

\subsection{Inter-Modal Waveform Phase Relationships}
\label{subsec:inter_modal}

Section~\ref{subsec:usable_observables} establishes that the three modalities represent different physical projections, and Section~\ref{subsec:single_component} demonstrates complementary amplitude and composite-phase responses. To use these observations jointly, their relative waveform phases must also be considered.

For clarity, we omit the channel index in this subsection. Substituting
\eqref{eq:displacement_sensitivity} into
\eqref{eq:amplitude_projection} and
\eqref{eq:phase_projection} gives
\begin{equation}
\begin{aligned}
    \frac{\delta A_l(t)}{\overline{A}_l}
    &\approx
    \operatorname{Re}
    \left\{
        \frac{V_l}{\overline{Z}_l}
    \right\}\xi(t),
    \\
    \frac{\delta A_r(t)}{\overline{A}_r}
    &\approx
    \operatorname{Re}
    \left\{
        \frac{V_r}{\overline{Z}_r}
    \right\}\xi(t),
    \\
    \delta\Phi(t)
    &\approx
    \left[
        \operatorname{Im}
        \left\{
            \frac{V_l}{\overline{Z}_l}
        \right\}
        +
        \operatorname{Im}
        \left\{
            \frac{V_r}{\overline{Z}_r}
        \right\}
    \right]\xi(t).
\end{aligned}
\label{eq:modal_linear_response}
\end{equation}

% Mathematical correction: the first two left-hand sides are
% normalized amplitude perturbations, not complex PCT perturbations.

Define
\begin{equation}
\begin{aligned}
    \frac{V_l}{\overline{Z}_l}
    &=u_l+jv_l,\\
    \frac{V_r}{\overline{Z}_r}
    &=u_r+jv_r.
\end{aligned}
\label{eq:modal_sensitivities}
\end{equation}

Multiple effective respiratory components may contribute to the observations. Let the $q$th component be
\begin{equation}
\begin{aligned}
    \xi_q(t)
    &=
    X_q\cos(\omega_b t+\psi_q)
    \\
    &=
    \operatorname{Re}
    \left\{
        X_qe^{j\psi_q}e^{j\omega_b t}
    \right\},
\end{aligned}
\label{eq:multiple_components}
\end{equation}
where $X_q$ and $\psi_q$ are its amplitude and temporal phase, respectively.

The equivalent respiratory phasors of the three modalities are
\begin{equation}
\begin{aligned}
    C_l
    &=
    \sum_q u_{l,q}X_qe^{j\psi_q},
    \\
    C_r
    &=
    \sum_q u_{r,q}X_qe^{j\psi_q},
    \\
    C_\phi
    &=
    \sum_q
    \left(v_{l,q}+v_{r,q}\right)
    X_qe^{j\psi_q}.
\end{aligned}
\label{eq:modal_phasors}
\end{equation}

For modality $m$, the equivalent respiratory amplitude and phase are
\begin{equation}
    A_m=|C_m|,
    \qquad
    \varphi_m=\arg(C_m).
    \label{eq:modal_amplitude_phase}
\end{equation}

The waveform phase difference between modalities $m$ and $n$ is
\begin{equation}
    \Delta\varphi_{m,n}
    =
    \arg\left(C_m\overline{C_n}\right),
    \label{eq:modal_phase_difference}
\end{equation}
where the overbar denotes complex conjugation.

Unlike the single-component model, this multi-component representation permits continuous phase differences. The effective phasors can point in different directions in the complex plane because the modalities weight the component contributions differently.

Figure~\ref{fig:inter_modal_phase} shows an example with non-binary phase offsets. The modality waveforms retain relative phase differences after channel-level fusion, and complex-plane rotation reduces these differences. Such offsets occur relatively infrequently in the open-corridor measurements.

To examine a more complex propagation environment, we also collected metal-plate measurements in a furnished studio containing several tables and chairs. Measurements were taken at two positions, and the inter-modal phase differences were tracked across windows. Non-binary phase differences occur more frequently in this environment, and the two positions exhibit different phase-difference baselines.

These results indicate that inter-modal phase relationships depend on sensing geometry and should be estimated for each window. Successful alignment, however, does not imply that all modalities should contribute equally to the final waveform. Their inclusion should also depend on measured signal quality.

\begin{figure*}[t]
    \centering
    \includegraphics[width=\textwidth]
    {../../outputs/figures/paper_fig3_inter_modal_phase.png}
    \caption{Inter-modal waveform phase relationships.
    (a) Modality waveforms after channel-level fusion and before
    inter-modal alignment.
    (b) Waveforms after Hilbert-transform-based phase alignment,
    with an illustrative quality-weighted fused waveform.
    (c)--(d) Window-wise inter-modal phase differences under two
    sensing configurations. The relative phases vary across windows
    and configurations, motivating window-wise phase estimation.}
    \label{fig:inter_modal_phase}
\end{figure*}

% TODO: Verify whether panels (c) and (d) correspond to two positions
% in the same studio or to different rooms. The draft descriptions differ.

\subsection{Design Insights}
\label{subsec:design_insights}

The observations provide two main implications for algorithm design:
\begin{itemize}
    \item \textbf{Adaptive use of observation modalities.}
    Amplitude and composite phase exhibit complementary responses across positions. The two endpoint amplitudes, however, are often similar. The sensing system should therefore adaptively weight and select observations rather than assume that all modalities are equally informative.

    \item \textbf{Explicit compensation for residual phase differences.}
    Although many inter-channel and inter-modal relationships are approximately binary, continuous phase offsets also occur. These offsets motivate explicit phase alignment before coherent waveform fusion.
\end{itemize}


\section{Proposed Method: BreatheCS}
\label{sec:method}

BreatheCS estimates respiratory rate and reconstructs respiratory waveforms from the same low-rate, multi-channel observations. The inputs comprise three modalities: local amplitude, remote amplitude, and composite phase. The method uses a shared preprocessing and quality-estimation stage, followed by separate spectral and waveform-processing branches.

\subsection{Design Rationale}
\label{subsec:method_rationale}

The observations in Section~\ref{sec:observation_model} show that the two endpoint amplitudes have similar physical meanings but can exhibit small measurement-dependent differences. Composite phase provides a complementary projection, but its waveform phase relationship with amplitude is less predictable. Moreover, composite phase is derived from both endpoints' PCT observations and is therefore affected by errors in both measurements.

BreatheCS accounts for these properties through task-specific processing. Respiratory-rate estimation requires a stable estimate of the dominant respiratory frequency. Once magnitude spectra are formed, residual inter-channel waveform phase offsets no longer need to be explicitly aligned. Waveform reconstruction, in contrast, requires coherent combination to avoid cancellation and preserve the respiratory component.

The method comprises the following stages:
\begin{enumerate}
    \item \textbf{Shared quality estimation.}
    Respiratory-band energy concentration $\eta$ is computed for each channel and used to determine its contribution to spectral aggregation and waveform fusion.

    \item \textbf{Spectral respiratory-rate estimation.}
    Channel spectra are combined within each modality using quality weights. The local- and remote-amplitude spectra are then fused into an endpoint-amplitude candidate. The final candidate is selected between this amplitude spectrum and the composite-phase spectrum according to window-level energy concentration.
    
    \item \textbf{Coherent waveform reconstruction.}
    Spectral peak prominence $\rho$ is additionally used to guide waveform fusion. Channel waveforms are first aligned within each modality using the Hilbert transform. The endpoint-amplitude waveforms are then aligned and fused. Finally, the method selects between the endpoint-amplitude and composite-phase candidates according to window-level quality, rather than unconditionally combining all three modalities.
\end{enumerate}

\subsection{Preprocessing}
\label{subsec:preprocessing}

Each channel sequence is first interpolated onto a uniform 2~Hz sampling grid. It is then processed using a short-window median filter, a 0.05~Hz high-pass filter to suppress slow drift, and a 0.1--0.35~Hz respiratory bandpass filter. Composite phase is unwrapped before filtering.

Processing uses sliding windows of 20~s with a 1~s step. The bandpass-filtered waveform of modality $m$ and channel $i$ is denoted by $x_{m,i}(t)$.

% TODO: The previous English draft uses a 4 Hz interpolation grid.
% Confirm the sampling grid used to obtain the reported results.

\subsection{Channel Quality and Weighted Spectral Aggregation}
\label{subsec:channel_quality}

Before either processing branch, each channel receives a quality score based on the dominance of respiratory-band energy. For spectral aggregation, we use the energy concentration in \eqref{eq:eta}:
\begin{equation}
\begin{aligned}
    w_{m,i}
    &=
    \eta_{m,i},
    \\
    \widetilde{w}_{m,i}
    &=
    \frac{
        w_{m,i}
    }{
        \sum_j w_{m,j}+\epsilon
    }.
\end{aligned}
\label{eq:eta_weight}
\end{equation}

Let $S_{m,i}(f)$ denote the magnitude spectrum of the bandpass-filtered waveform for channel $i$ in modality $m$. With $N=72$ channels, the fused spectrum for modality $m$ is
\begin{equation}
    \overline{S}_m(f)
    =
    \sum_{i=1}^{N}
    \widetilde{w}_{m,i}S_{m,i}(f).
    \label{eq:weighted_spectrum}
\end{equation}

\subsection{Spectral Branch: Modality Fusion and Respiratory-Rate Estimation}
\label{subsec:spectral_branch}

After channel-level aggregation, each modality is represented by one spectrum $\overline{S}_m(f)$. We first combine the two endpoint-amplitude spectra:
\begin{equation}
    S_{\mathrm{A}}(f)
    =
    \frac{
        w_r\overline{S}_r(f)
        +
        w_l\overline{S}_l(f)
    }{
        w_r+w_l+\epsilon
    }.
    \label{eq:amplitude_spectrum}
\end{equation}

The composite-phase candidate is
\begin{equation}
    S_{\Phi}(f)
    =
    \overline{S}_\phi(f).
    \label{eq:phase_spectrum}
\end{equation}

Here, $w_m$ is determined by modality-level respiratory-band energy concentration or the corresponding window-level quality-selection rule. The fusion and selection variants are examined in Section~\ref{subsec:ablation}.

The two candidate spectra are compared using their respiratory-band energy concentrations. Let
\begin{equation}
\begin{aligned}
    b^\star
    &=
    \arg\max_{b\in\{\mathrm{A},\Phi\}}\eta_b,
    \\
    S_{\mathrm{opt}}(f)
    &=
    S_{b^\star}(f),
\end{aligned}
\label{eq:spectral_candidate_selection}
\end{equation}
where $\eta_b$ is the window-level energy concentration of candidate $b$.

The respiratory frequency and rate are estimated from the dominant spectral peak:
\begin{equation}
\begin{aligned}
    \widehat{f}_b
    &=
    \arg\max_{f\in\mathcal{F}_b}S_{\mathrm{opt}}(f),
    \\
    \widehat{\mathrm{BPM}}
    &=
    60\,\widehat{f}_b.
\end{aligned}
\label{eq:bpm_peak}
\end{equation}

This spectral branch provides the primary BPM output of BreatheCS. It retains the benefits of quality-weighted channel aggregation without requiring explicit waveform alignment before channel combination.

The weighting strategy is inspired by maximal-ratio combining (MRC) \cite{mrc_reference_placeholder}. Classical MRC uses complex channel coefficients and noise variance, whereas BreatheCS uses respiratory-band quality measures as practical reliability weights. We therefore describe the method as MRC-inspired quality-weighted combining rather than classical MRC.

\subsection{Waveform Branch: Coherent Endpoint Fusion and Candidate Selection}
\label{subsec:waveform_branch}

Waveform reconstruction uses Hilbert-transform-based phase alignment and quality-weighted coherent combination. The processing consists of channel-level alignment, endpoint-amplitude fusion, and final selection between the endpoint-amplitude and composite-phase candidates.

Following Section~\ref{sec:observation_model}, the band-limited respiratory component of channel $i$ in modality $m$ is approximated by
\begin{equation}
    x_{m,i}(t)
    \approx
    \operatorname{Re}
    \left\{
        C_{m,i}e^{j\omega_b t}
    \right\}
    +
    n_{m,i}(t),
    \label{eq:channel_phasor}
\end{equation}
where $n_{m,i}(t)$ represents measurement noise and other residual components.

Its analytic signal is
\begin{equation}
\begin{aligned}
    z_{m,i}(t)
    &=
    x_{m,i}(t)
    +
    j\mathcal{H}\{x_{m,i}(t)\}
    \\
    &\approx
    C_{m,i}e^{j\omega_b t}
    +
    \widetilde{n}_{m,i}(t),
\end{aligned}
\label{eq:analytic_channel}
\end{equation}
where $\mathcal{H}\{\cdot\}$ denotes the Hilbert transform.

\subsubsection{Channel-level coherent fusion}

Waveforms must be aligned before coherent combination to avoid cancellation. In addition to $\eta$, we use spectral peak prominence $\rho$ to emphasize channels with a well-defined respiratory component. The waveform-fusion weights are
\begin{equation}
\begin{aligned}
    w_{m,i}
    &=
    \eta_{m,i}\max(\rho_{m,i},0),
    \\
    \widetilde{w}_{m,i}
    &=
    \frac{
        w_{m,i}
    }{
        \sum_j w_{m,j}+\epsilon
    }.
\end{aligned}
\label{eq:eta_rho_weight}
\end{equation}

For each modality, the channel with the highest quality score is selected as the reference:
\begin{equation}
    i_m^\star
    =
    \arg\max_i w_{m,i}.
    \label{eq:reference_channel}
\end{equation}

The continuous phase offset relative to the reference is estimated through complex correlation:
\begin{equation}
    \Delta\phi_{m,i}
    =
    \arg
    \left(
        \sum_t
        z_{m,i}(t)
        \overline{z_{m,i_m^\star}(t)}
    \right).
    \label{eq:channel_phase_offset}
\end{equation}

The analytic signals are then rotated and combined:
\begin{equation}
\begin{aligned}
    z_m(t)
    &=
    \frac{
        \sum_i
        w_{m,i}z_{m,i}(t)e^{-j\Delta\phi_{m,i}}
    }{
        \sum_i w_{m,i}+\epsilon
    },
    \\
    y_m(t)
    &=
    \operatorname{Re}\{z_m(t)\}.
\end{aligned}
\label{eq:channel_coherent_fusion}
\end{equation}

Complex-plane rotation compensates for continuous phase differences that cannot be removed by binary sign correction alone. The quality weights determine the contribution of each aligned channel.

\subsubsection{Endpoint-amplitude fusion and final selection}

The channel-level outputs $y_r(t)$, $y_l(t)$, and $y_\phi(t)$ may still exhibit relative phase offsets. We convert them to analytic signals:
\begin{equation}
    u_m(t)
    =
    y_m(t)+j\mathcal{H}\{y_m(t)\}.
    \label{eq:modal_analytic_signal}
\end{equation}

The endpoint-amplitude waveforms are aligned and fused before comparison with the composite-phase candidate. We recompute the modality quality as
\begin{equation}
    Q_m=\eta_m\rho_m
    \label{eq:modal_quality}
\end{equation}
and select the amplitude reference modality:
\begin{equation}
    m_{\mathrm{A}}^\star
    =
    \arg\max_{m\in\{r,l\}}Q_m.
    \label{eq:amplitude_reference}
\end{equation}

For $m\in\{r,l\}$, the phase offset is
\begin{equation}
\begin{aligned}
    \Delta\theta_m
    &=
    \arg
    \left(
        \sum_t
        u_m(t)
        \overline{u_{m_{\mathrm{A}}^\star}(t)}
    \right),
    \\
    \Delta\theta_{m_{\mathrm{A}}^\star}
    &=0.
\end{aligned}
\label{eq:modal_phase_alignment}
\end{equation}

The endpoint-amplitude candidate is
\begin{equation}
\begin{aligned}
    z_{\mathrm{A}}(t)
    &=
    \frac{
        \sum_{m\in\{r,l\}}
        Q_m u_m(t)e^{-j\Delta\theta_m}
    }{
        \sum_{m\in\{r,l\}}Q_m+\epsilon
    },
    \\
    y_{\mathrm{A}}(t)
    &=
    \operatorname{Re}\{z_{\mathrm{A}}(t)\}.
\end{aligned}
\label{eq:endpoint_amplitude_fusion}
\end{equation}

Window-level quality is then recomputed for the two candidates:
\begin{equation}
    Q_{\mathrm{A}}
    =
    \eta(y_{\mathrm{A}}),
    \qquad
    Q_{\Phi}
    =
    \eta(y_\phi).
    \label{eq:waveform_candidate_quality}
\end{equation}

The final candidate is selected as
\begin{equation}
    b^\star
    =
    \arg\max_{b\in\{\mathrm{A},\Phi\}}Q_b,
    \label{eq:waveform_candidate_selection}
\end{equation}
with
\begin{equation}
    z_{\mathrm{final}}(t)
    =
    \begin{cases}
        z_{\mathrm{A}}(t), & b^\star=\mathrm{A},\\
        u_\phi(t), & b^\star=\Phi,
    \end{cases}
    \label{eq:final_analytic_waveform}
\end{equation}
and
\begin{equation}
    y_{\mathrm{final}}(t)
    =
    \operatorname{Re}\{z_{\mathrm{final}}(t)\}.
    \label{eq:final_waveform}
\end{equation}

The waveform in \eqref{eq:final_waveform} is the primary waveform output of BreatheCS.


\section{Evaluation}
\label{sec:evaluation}

\subsection{Experimental Setup}
\label{subsec:evaluation_setup}

We collected human respiration measurements from four participants under three indoor sensing scenarios: sitting in a living room, lying supine in a bedroom, and lying on the side in a bedroom. Figure~\ref{fig:human_setup} illustrates the measurement configurations.

Each participant wore an HKH-11C respiratory belt to provide a reference waveform. Two Nordic nRF54L15 devices equipped with 6~dBi antennas were positioned near the participant.

Measurements were aggregated at the initiator. The local PCT was measured by the initiator from the tone transmitted by the reflector, whereas the remote PCT was measured by the reflector. After each CS event, the reflector returned its measurements to the initiator. Both endpoints' PCT observations were then transferred through a serial connection to a custom PC acquisition program. The measured serial-transfer time for one event was less than 20~ms.

All 72 CS channels were enabled. The minimum measurement interval was set to 250~ms, but this interval could not always be maintained during sustained operation. Allowing measurement intervals within 250--500~ms provided stable continuous acquisition.

% TODO: Reconcile the four participants described here with the eight
% participants reported in the introduction. The numerical tables below
% are identified in the source draft as results from 12 recordings.

% Insert the human-subject measurement configurations here.
% \begin{figure*}[t]
%     \centering
%     \includegraphics[width=\textwidth]{figures/human_subject_setup.pdf}
%     \caption{Human-subject measurement configurations: sitting in a
%     living room, lying supine in a bedroom, and lying on the side
%     in a bedroom.}
%     \label{fig:human_setup}
% \end{figure*}

\subsection{Baselines and Adaptation Protocol}
\label{subsec:baselines}

BLE CS sensing is at an early stage, and comprehensive respiration-processing methods tailored to its measurement structure remain limited. In contrast, respiration sensing with Wi-Fi and other wireless platforms has produced a range of signal-processing and signal-enhancement methods \cite{wireless_respiration_baselines_placeholder}. These methods provide useful channel- and modality-fusion strategies, but they cannot always be transferred directly to BLE CS.

Two properties require particular consideration: the low effective sampling rate and the bidirectional PCT structure. We therefore adapt representative methods to the available CS observations and compare them under a common preprocessing protocol.

Fan et al.\ \cite{Fan2024} first compute a breathing-band energy ratio for each channel and then perform MRC-style channel combination. They select the final amplitude or phase candidate according to the energy ratio. Our adaptation retains this final selection rule and chooses the highest-quality candidate among the available modalities.

Some methods use CSI ratios from two antennas and search for a projection direction that enhances the respiratory component, as in FarSense \cite{zeng2019farsense}. These operations cannot be transferred directly because BLE CS endpoint amplitudes and composite phase do not form the same single-endpoint CSI-ratio representation. Other components, including PCA-based channel fusion \cite{zhuo2023_placeholder} and MRC--PCA fusion \cite{yu2021_placeholder}, can be adapted and included in the comparison.

For methods with distinctive post-processing stages, such as variational mode decomposition (VMD), we consider both a full adaptation and a fusion-only variant to distinguish the contributions of fusion and subsequent processing.

% TODO: Ensure that every claimed full adaptation and fusion-only
% variant is explicitly identified in the reported results.

All baselines use the preprocessing described in
Section~\ref{subsec:preprocessing}. The comparison therefore focuses on differences in channel-level and modality-level processing. Performance is assessed using absolute BPM error and waveform RMSE relative to the respiratory-belt reference.

\subsection{Main Results}
\label{subsec:main_results}

\subsubsection{Respiratory-rate estimation}

Table~\ref{tab:bpm_overall} reports the overall absolute BPM error. BreatheCS achieves the lowest mean error, at $0.371\pm0.128$~breaths/min. The strongest adapted baselines also achieve relatively low errors: Pos-Free with PCA obtains 0.435~breaths/min, and WiFi-Sleep with MRC--PCA obtains 0.505~breaths/min.

For comparison, we also estimate BPM from the reconstructed waveform. This variant, denoted BreatheCS-Wave, obtains an error of $0.385\pm0.118$~breaths/min. It is included only to compare the two processing branches and is not the primary BPM output of BreatheCS.

Table~\ref{tab:bpm_scenario} reports the results by sensing scenario. BreatheCS achieves the lowest mean absolute BPM error in all three configurations.

These results show that several established fusion strategies remain effective when adapted to BLE CS. Basic signal-processing principles therefore transfer across sensing platforms, while the CS-specific processing in BreatheCS provides the best respiratory-rate estimates among the evaluated methods.

\begin{table}[t]
    \centering
    \caption{Overall absolute BPM error. BreatheCS-Wave is included
    as a branch comparison rather than as the primary BPM estimator.}
    \label{tab:bpm_overall}
    \small
    \begin{tabular}{lrr}
        \toprule
        Method & Mean $\downarrow$ & Std. \\
        \midrule
        \textbf{BreatheCS} & \textbf{0.371} & 0.128 \\
        Pos-Free (PCA) & 0.435 & 0.123 \\
        WiFi-Sleep (MRC--PCA) & 0.505 & 0.149 \\
        BreatheCS-Wave & 0.385 & 0.118 \\
        WiFi-Sleep ($\sqrt{\eta}$) & 1.023 & 1.257 \\
        PCA sign only & 1.317 & 0.646 \\
        ClessBreath ($\eta$-linear) & 1.386 & 1.685 \\
        ClessBreath ($\eta$-equal) & 1.486 & 1.527 \\
        \bottomrule
    \end{tabular}
\end{table}

% Source note: the draft identifies these as means over 12
% subject--scenario recordings, with standard deviations across those
% cases. Data source: gate_decomposition_hkh.json.
% TODO: Confirm the exact aggregation unit used for the reported std.

\begin{table*}[t]
    \centering
    \caption{Mean absolute BPM error by sensing scenario, in
    breaths/min. Each scenario includes four participants.}
    \label{tab:bpm_scenario}
    \small
    \begin{tabular}{lrrr}
        \toprule
        Method
        & Living room: sitting
        & Bedroom: supine
        & Bedroom: side lying \\
        \midrule
        \textbf{BreatheCS}
        & \textbf{0.356} & \textbf{0.412} & \textbf{0.344} \\
        Pos-Free (PCA)
        & 0.415 & 0.436 & 0.455 \\
        WiFi-Sleep (MRC--PCA)
        & 0.609 & 0.451 & 0.455 \\
        BreatheCS-Wave
        & 0.358 & 0.424 & 0.374 \\
        WiFi-Sleep ($\sqrt{\eta}$)
        & 1.521 & 0.532 & 1.016 \\
        PCA sign only
        & 1.365 & 1.212 & 1.373 \\
        ClessBreath ($\eta$-linear)
        & 1.498 & 1.225 & 1.434 \\
        ClessBreath ($\eta$-equal)
        & 1.400 & 2.038 & 1.022 \\
        \bottomrule
    \end{tabular}
\end{table*}

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/paper_fig6a_bpm_leaderboard.png}
    \caption{Overall mean absolute BPM error across the 12
    subject--scenario recordings. BreatheCS uses the spectral branch
    for its primary BPM estimate.}
    \label{fig:bpm_overall}
\end{figure}

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/paper_fig6b_bpm_by_room.png}
    \caption{Mean absolute BPM error under the three sensing scenarios:
    living-room sitting, bedroom supine lying, and bedroom side lying.}
    \label{fig:bpm_scenario}
\end{figure}

% TODO: Regenerate the figures using the numerical values in
% Tables~\ref{tab:bpm_overall} and \ref{tab:bpm_scenario}.
% The source draft states that some figure files contain older results.

\subsubsection{Waveform reconstruction}

Table~\ref{tab:waveform_rmse} reports waveform reconstruction error relative to the respiratory belt. BreatheCS obtains the lowest RMSE among the adapted external baselines, at $0.937\pm0.209$. Relative to the next-best external baseline, ClessBreath with $\eta$-linear weighting, this corresponds to an RMSE reduction of approximately 8.6\%.

The remote-amplitude-only ablation achieves a similar RMSE of 0.941, as shown in Table~\ref{tab:single_modal_ablation}. Thus, endpoint-amplitude fusion provides only a small average improvement over the strongest individual modality. The results do not indicate a large waveform-reconstruction margin over remote amplitude alone.

Figure~\ref{fig:bpm_rmse_tradeoff} presents the joint BPM and waveform performance. BreatheCS combines the lowest reported spectral BPM error with the lowest waveform RMSE among the evaluated external methods.

\begin{table}[t]
    \centering
    \caption{Normalized waveform RMSE relative to the respiratory-belt
    reference.}
    \label{tab:waveform_rmse}
    \small
    \begin{tabular}{lrr}
        \toprule
        Method & Mean $\downarrow$ & Std. \\
        \midrule
        \textbf{BreatheCS} & \textbf{0.937} & 0.209 \\
        Pos-Free (PCA) & 1.070 & 0.250 \\
        WiFi-Sleep (MRC--PCA) & 1.063 & 0.245 \\
        WiFi-Sleep ($\sqrt{\eta}$) & 1.054 & --- \\
        PCA sign only & 1.085 & 0.182 \\
        ClessBreath ($\eta$-linear) & 1.025 & 0.241 \\
        ClessBreath ($\eta$-equal) & 1.046 & 0.211 \\
        \bottomrule
    \end{tabular}
\end{table}

% Source note: the reported BreatheCS result combines the spectral BPM
% branch (G0/draft_s_rl) with the endpoint-amplitude waveform result
% (draft_w_rl). The draft identifies these results as being based on
% 12 subject--scenario recordings.
% TODO: Confirm that the reported waveform result includes the final
% amplitude-versus-phase selection described in the method.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/paper_fig7_bpm_vs_rmse.png}
    \caption{Joint respiratory-rate and waveform-reconstruction
    performance. Each point represents a method's mean absolute BPM
    error and normalized waveform RMSE over the 12 recordings.
    BreatheCS-Wave is shown only to compare the spectral and waveform
    branches.}
    \label{fig:bpm_rmse_tradeoff}
\end{figure}

% TODO: Update the figure to match the final numerical results.

\subsection{Ablation Experiments}
\label{subsec:ablation}

We evaluate the contributions of channel fusion, endpoint-amplitude fusion, and individual observation modalities. BreatheCS performs processing at both the channel and modality levels. At the modality level, coherent fusion applies only to the local and remote amplitudes; composite phase remains a separate candidate for selection.

When fusion at a given level is disabled, the candidate with the highest respiratory-band energy concentration is retained at that level. This provides a selection-only comparison without averaging the available observations.

\subsubsection{Contributions of the two fusion levels}

Table~\ref{tab:fusion_ablation} summarizes the fusion-level ablation. BreatheCS achieves the lowest errors among the evaluated configurations. Channel fusion accounts for most of the spectral BPM improvement: the error decreases from 1.640~breaths/min without fusion to 0.381~breaths/min with channel-only fusion. Adding modality-level processing yields a smaller further reduction to 0.371~breaths/min.

The waveform branch behaves differently. Channel-only fusion gives a waveform-derived BPM error of 1.003~breaths/min, whereas the complete method reduces this error to 0.385~breaths/min. Thus, the two-level processing improves the rate estimate obtained from the reconstructed waveform and brings it closer to the primary spectral estimate.

\begin{table*}[t]
    \centering
    \caption{Fusion-level ablation. BPM errors are measured in
    breaths/min, and waveform RMSE is normalized.}
    \label{tab:fusion_ablation}
    \small
    \begin{tabular}{lrrr}
        \toprule
        Configuration
        & Spectral BPM error $\downarrow$
        & Waveform BPM error $\downarrow$
        & Waveform RMSE $\downarrow$ \\
        \midrule
        No fusion
        & 1.640 & 1.192 & 1.007 \\
        Channel only
        & 0.381 & 1.003 & 0.962 \\
        Modality only
        & 0.655 & 1.025 & 0.986 \\
        \textbf{BreatheCS}
        & \textbf{0.371} & \textbf{0.385} & \textbf{0.937} \\
        \bottomrule
    \end{tabular}
\end{table*}

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/paper_fig8_abc_fusion.png}
    \caption{Fusion-level ablation for (a) spectral BPM estimation,
    (b) waveform-derived BPM estimation, and (c) waveform
    reconstruction.}
    \label{fig:fusion_ablation}
\end{figure}

\subsubsection{Contributions of individual modalities}

Table~\ref{tab:single_modal_ablation} compares the full method with individual modalities. BreatheCS performs similarly to the endpoint-amplitude variants, whereas composite phase alone produces substantially larger errors.

For spectral BPM estimation, the remote- and local-amplitude errors are 0.376 and 0.378~breaths/min, respectively, compared with 2.191~breaths/min for composite phase. The corresponding waveform RMSE values are 0.941, 0.947, and 1.109. These results indicate that composite phase is less reliable for the human respiration recordings considered here.

Because composite phase generally has a lower respiratory-band energy concentration, it is rarely selected by the final quality-based decision. Consequently, the full method performs close to the endpoint-amplitude configurations.

\begin{table*}[t]
    \centering
    \caption{Single-modality ablation compared with BreatheCS.
    BPM errors are measured in breaths/min.}
    \label{tab:single_modal_ablation}
    \small
    \begin{tabular}{lrrrr}
        \toprule
        Metric
        & Remote amplitude
        & Local amplitude
        & Composite phase
        & BreatheCS \\
        \midrule
        Spectral BPM error
        & 0.376 & 0.378 & 2.191 & \textbf{0.371} \\
        Waveform BPM error
        & 0.399 & 0.439 & 2.395 & \textbf{0.385} \\
        Waveform RMSE
        & 0.941 & 0.947 & 1.109 & \textbf{0.937} \\
        \bottomrule
    \end{tabular}
\end{table*}

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/paper_fig8_def_single_modal.png}
    \caption{Single-modality ablation for spectral BPM estimation,
    waveform-derived BPM estimation, and waveform reconstruction.
    The remote-amplitude, local-amplitude, and composite-phase
    configurations are compared with BreatheCS.}
    \label{fig:single_modal_ablation}
\end{figure}

% Source note: the draft also lists an equal-weight three-modality
% variant with spectral BPM error 0.405, waveform BPM error 0.744,
% and waveform RMSE 0.951.
% TODO: Update the ablation figures to match the final configurations
% and results.

\subsubsection{Conditional value of composite phase}

A window-level oracle analysis further examines the potential contribution of composite phase. Among the 1,730 windows in the human dataset, composite phase is the oracle-best candidate in only 105 windows, or approximately 6.1\%.

Figure~\ref{fig:phase_oracle} compares the distribution of
$\eta_{\mathrm{phase}}$ over all windows with its distribution over the phase-best windows. The latter largely overlaps the middle-to-high portion of the full distribution rather than forming a clearly separated high-quality group. A high phase energy concentration therefore does not, by itself, consistently identify windows in which composite phase is the best candidate.

These results distinguish physical complementarity from statistical reliability. Although composite phase can provide complementary observations, it is not consistently beneficial for natural respiration in the evaluated dataset. Selective use is therefore more appropriate than unconditional three-modality fusion.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]
    {../../outputs/figures/paper_fig_modal_oracle_phase_eta_hkh.png}
    \caption{Distribution of composite-phase respiratory-band energy
    concentration $\eta_{\mathrm{phase}}$. The full distribution
    includes all 1,730 windows, while the highlighted distribution
    includes the 105 windows in which composite phase is oracle-best.
    The substantial overlap indicates that phase-best windows are
    not readily separated using $\eta_{\mathrm{phase}}$ alone.}
    \label{fig:phase_oracle}
\end{figure}


\section{Discussion}
\label{sec:discussion}

BreatheCS uses a dedicated spectral branch for respiratory-rate estimation to reduce its dependence on waveform alignment under low-rate and potentially irregular sampling. A 20~s window contains only two to seven respiratory cycles over the 0.1--0.35~Hz band. At a representative frequency of 0.2~Hz, it contains approximately four cycles.

With so few cycles, finite-window processing and waveform alignment can be sensitive to noise and timing errors. Magnitude-spectrum aggregation does not require the relative waveform phases to be aligned before combination. This distinction motivates the separate spectral branch for BPM estimation and is consistent with the observed results.

Future work will further investigate the measurement properties of BLE CS, including the conditions under which composite phase provides useful complementary information. The framework may also be extended to multi-person respiration sensing to explore whether the available frequency-channel diversity can support more complex sensing tasks.


\section{Conclusion}
\label{sec:conclusion}

This work presented BreatheCS, a respiration sensing framework tailored to Bluetooth Channel Sounding. By modeling bidirectional PCT measurements, we identified two endpoint-amplitude observations and one composite-phase observation with different complex-plane sensitivities. The measurements revealed heterogeneous sensing quality across channels, continuous and scene-dependent waveform phase relationships, and different processing requirements for respiratory-rate estimation and waveform reconstruction.

Based on these findings, BreatheCS combines shared channel-quality estimation with two task-specific branches. The spectral branch performs quality-weighted aggregation for BPM estimation. The waveform branch coherently combines channel observations, fuses the endpoint amplitudes, and then selects between the endpoint-amplitude and composite-phase candidates.

Evaluation using controlled mechanical motion and 12 human recordings achieved a mean absolute BPM error of 0.371 breaths/min and a normalized waveform RMSE of 0.937. Ablation results show that channel diversity is the largest and most consistent source of improvement, reducing spectral BPM error from 1.640 to 0.381 breaths/min before modality-level processing. Modality diversity, particularly composite phase, provides conditional rather than universal benefits.

These findings indicate that BLE CS sensing methods should account for the bidirectional measurement structure and the requirements of the sensing task. Future work will investigate when composite phase provides complementary information, improve robustness to body motion and complex multipath, and extend the framework to irregular breathing and apnea detection.

% TODO: Reconcile the 12 recordings reported here with the 24 recordings
% reported in the introduction.