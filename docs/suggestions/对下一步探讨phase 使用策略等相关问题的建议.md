*Thinking...*

> **Assessing Bluetooth specifications**
>
> I need to respond as an advisor and carefully assess the documents, focusing on specific claims and citations. I should only search for primary sources like the official Bluetooth core specifications and technical papers from proceedings, such as those from ACM. I want to identify inaccuracies in the physical data and experimental designs. Also, I’ll check if the draft correctly mentions that Bluetooth Core 6.0 introduced CS, not 5.2, and clarify some technical terms. I'll search through all relevant official specs.
>
> **Considering critiques and details**
>
> I need to formulate major critiques on this topic. It seems important to inspect the official technical overview and details on the PCT, along with timings. This inspection could help me identify any significant flaws or areas that need improvement. I’m curious about how the specifics will guide my critiques and if they'll uncover any insights I hadn't considered yet. Alright, let's dive into those details!
>
> **Analyzing sequential tones**
>
> I’m considering how sequential tones reveal contradictory and abstract claims through continuous phase offsets. It's clear that their Hilbert offsets likely don't result from a sequential scan, so I need to remove any causal attribution. The continuous residual phase across the tone might stem from multipath frequency response and processing instead of sequential sampling. This feels significant! Lastly, sampling intervals of 250-500ms indicate a range of 2-4 Hz, which isn't the same as "2 Hz."
>
> **Planning experiments for evaluation**
>
> I'm thinking about how to approach this evaluation using domain robust minimax principles. I want to avoid tailoring to HKH and use leave-domain-out methods. My priority list includes auditing the model for correctness, establishing a diagnostic tone-level, and ensuring robust evaluation before moving on to gating. I’m considering controlled experiments that vary plate positions across Fresnel zones and incorporate nonrespiratory motion to test radial and tangential complementarity directly. I’ll explore different motorized plate positions and link geometries to achieve this effectively.
>
> **Considering experimental setups**
>
> I'm planning to sweep the baseline position slowly, breathing oscillation at each point. I want to add rigid whole-body drift or some random low-frequency motion, rotate or relocate endpoints, and ensure I record timestamps along with AGC and quality indicators. I'm considering testing phase noise in a static scene and separating local and remote phase noise, while also looking into Allan deviation and PSD. I should seek recent paper recommendations for further insights, while being cautious about previous literature.

我认真看了三份文档。整体判断是：

> **你们已经找到一个真实且有研究价值的问题，但当前“Phase 无零陷、用于填补幅值零陷”的物理叙事写得过强。下一步不应急着继续搜索门控权重，而应先修正观测模型，再用受控实验验证“幅值—相位互补”究竟以什么形式存在。**

下面分物理模型、实验计划、算法设计和论文写作四部分给建议。

------

# 一、最关键的物理问题：Phase 并非天然“无零陷”

当前 plan 和 briefing 中最核心的假设是：

$\Delta\Phi=\frac{4\pi}{\lambda}\Delta d,\qquad \frac{d\Phi}{dd}\neq 0$

因此 Phase 对位移线性、没有零陷，而幅值有零陷。

这个结论只在非常受限的情况下成立，例如：

- 存在一个可分离、占主导的动态反射路径；
- 测量的是该路径自身的传播相位；
- 位移方向和双基地传播几何已知；
- 静态多径不会显著改变合成信道的相位。

但你现在使用的是**合成多径信道的 PCT 相位**，并不是已被分离的胸部反射路径相位。一般应写成：

$H(d)=H_s+H_d(d),$

其中 $H_s$ 是静态多径合成项，$H_d(d)$ 是受呼吸调制的动态项。此时：

$\frac{d|H|}{dd} = \frac{\operatorname{Re}\{H^*H'\}}{|H|},$

$\frac{d\angle H}{dd} = \frac{\operatorname{Im}\{H^*H'\}}{|H|^2}.$

这说明：

- 幅值是复信道扰动在**径向方向**上的投影；
- 相位是复信道扰动在**切向方向**上的投影；
- 两者谁强，取决于 IQ 轨迹相对于原点的方向；
- **幅值可以出现盲区，相位同样可以出现盲区**；
- 更准确的说法是：二者通常具有互补的敏感区，而不是 Phase 永远无零陷。

近期无线呼吸感知研究也明确指出，幅值和相位都可能因 Fresnel 几何而退化；在某些位置幅值强、相位弱，在另一些位置则相反。更稳健的方法通常利用完整 IQ 几何，而不是预设相位始终线性。([nature.com](https://www.nature.com/articles/s44459-026-00036-z)) FullBreathe 等工作也确实讨论了幅值和相位在呼吸盲区中的互补性，因此你们的研究方向有文献基础，但应表述为“互补投影”而不是“Phase 无零陷”。([www-public.imtbs-tsp.eu](https://www-public.imtbs-tsp.eu/~zhang_da/pub/FullBreathe.pdf))

## 建议修改核心假设

不要写：

> Phase 的唯一作用是在幅值双零陷时提供无零陷的线性位移测量。

建议改为：

> **Phase 提供与 Remote/Local 幅值不同的复平面投影。当幅值观测的径向呼吸分量较弱，而合成相位的切向呼吸分量仍显著时，Phase 可能提供互补的救援信息。**

对应地，可以把“Null-Filling”改成更稳妥的名称：

- **Complementary Projection Rescue**
- **Radial-Blind-Spot Compensation**
- **Phase-Assisted Blind-Spot Mitigation**
- 中文：“互补投影救援”或“幅值盲区补偿”

如果最终实验真的证明 Phase-best 窗口主要对应幅值径向分量弱、相位切向分量强，再进一步使用“零陷填充”也不迟。

------

# 二、$\Delta\Phi=4\pi\Delta d/\lambda$ 也需要几何修正

$4\pi\Delta d/\lambda$ 是典型单基地往返路径模型。你们的 BLE 链路更接近双基地反射几何。一般应写为：

$\Delta\phi = \frac{2\pi}{\lambda}\Delta L,$

其中：

$\Delta L \approx \left(\mathbf{u}_{\mathrm{Tx}}+\mathbf{u}_{\mathrm{Rx}}\right)^{T} \Delta\mathbf{x}.$

只有在位移方向与入射、反射方向都近似共线，并且总路径变化约为 $2\Delta d$ 时，才退化为：

$\Delta\phi\approx\frac{4\pi}{\lambda}\Delta d.$

所以建议在论文中：

1. 把 $4\pi/\lambda$ 写成特殊几何下的近似；
2. 主模型使用 $(2\pi/\lambda)\Delta L$；
3. 再强调实际观测的是合成信道相位，因此还受到静态、多动态路径矢量叠加影响。

------

# 三、Remote、Local、Phase 不是“三条独立传播路径”

briefing 中说：

> 三个模态构成对同一物理位移的三条独立观测路径。

这个表述也偏强。

Remote 和 Local 的传播信道在理想时分双向测量中具有互易性，它们并不等于两个空间独立的 AP。其差异更多来自：

- 两端 RF 前端增益和相位响应；
- 接收机噪声；
- AGC、校准和量化差异；
- 双向测量不完全同时；
- 天线及硬件链路不完全互易；
- PCT 后处理差异。

因此更准确的说法是：

> Remote 和 Local 是同一双向交换的两个端侧观测，传播几何高度相关，但接收链、噪声及测量时刻不同，因此具有一定观测分集，而非完全独立的空间分集。

Phase 则是两端复观测组合后的切向信息，并不是第三条独立传播路径。

这并不削弱你们的工作。相反，可以把论文问题定义得更准确：

> **如何融合高度相关但噪声结构不同的双向幅值观测，以及由二者共同构成的相位观测？**

------

# 四、关于 Phase 噪声的表述也要收紧

“Phase 噪声是幅值的两倍”不能直接成立，因为幅值噪声和相位噪声量纲不同。

可以说：

> 若 Local 和 Remote 的单向相位估计噪声相互独立且方差近似相等，则组合相位的误差方差近似等于两端相位误差方差之和，即约为单端相位误差方差的两倍。

即：

$\Phi=\phi_l+\phi_r,$

$\operatorname{Var}(\Phi) = \operatorname{Var}(\phi_l) + \operatorname{Var}(\phi_r) + 2\operatorname{Cov}(\phi_l,\phi_r).$

只有协方差可忽略、两端同方差时，才有：

$\operatorname{Var}(\Phi)\approx 2\sigma_\phi^2.$

此外，不宜笼统写“PCT 相乘消除了 LO 漂移”。建议写成：

> 双向 PCT 组合旨在抵消互易的本振相位偏置，但实际系统仍可能存在残余频偏、短期相位噪声、硬件校准误差和非同时采样误差。

Bluetooth Channel Sounding 是 Bluetooth Core 6.0 引入的特性，采用连接态下的双向交换并支持 PBR 和 RTT；官方材料也强调实际实现中仍需处理频率生成误差等硬件非理想性。([bluetooth.com](https://www.bluetooth.com/core-specification-6-feature-overview/))

------

# 五、当前 E1 的 Null Score 不能正确检测“双幅值零陷”

目前定义：

$\text{Null Score} = \frac{\min(\eta_R,\eta_L)} {\max(\eta_R,\eta_L,\eta_P)}.$

它有一个明显问题：

- 如果 Remote 很弱、Local 很强，分子依然很小；
- 因此低 Null Score 只能说明“至少一个幅值模态弱”，不能说明“Remote 和 Local 同时弱”。

## 更合适的统计定义

先对不同模态的 $\eta$ 做域内或记录内归一化，例如：

$\tilde{\eta}_m = \frac{\eta_m} {\operatorname{median}_{w\in \text{training record}}(\eta_m(w))+\epsilon}.$

然后定义幅值联合弱响应：

$q_{\mathrm{amp}} = \max(\tilde{\eta}_R,\tilde{\eta}_L).$

只有 $q_{\mathrm{amp}}$ 很低，才说明两个幅值都低。

或者定义：

$q_{\mathrm{amp,geo}} = \sqrt{\tilde{\eta}_R\tilde{\eta}_L}.$

但更重要的是：**低 $\eta$ 不等于物理零陷**。它也可能由身体微动、滤波泄漏、弱 SNR 或错误谱峰造成。

## 最推荐的诊断：使用原始 PCT IQ

你们已经有 $Z_l(t)$、$Z_r(t)$，应该直接分析每个 tone 的局部 IQ 几何。对于：

$Z(t)=\bar Z+\delta Z(t),$

定义相对静态向量的径向和切向呼吸分量：

$r(t) = \operatorname{Re} \left\{ \delta Z(t)e^{-j\angle\bar Z} \right\},$

$q(t) = \operatorname{Im} \left\{ \delta Z(t)e^{-j\angle\bar Z} \right\}.$

然后计算呼吸频带能量：

$E_{\mathrm{rad}} = \sum_{f\in \mathcal F_b}|R(f)|^2, \qquad E_{\mathrm{tan}} = \sum_{f\in \mathcal F_b}|Q(f)|^2.$

真正支持 Phase 互补作用的证据应是：

> 在 Phase-best 窗口中，Remote/Local 的径向呼吸能量系统性下降，而切向能量或组合相位的跨 tone 一致性仍然较高。

这比比较三个 $\eta$ 有更强的物理解释力。

------

# 六、E1b 目前存在选择偏差

原计划是：

> 比较 Phase-best 窗的 Phase–GT 相关系数，和 Remote-best 窗的 Remote–GT 相关系数。

这基本会产生预期结果，因为窗口已经根据 GT 定义为“某模态最优”。这是条件选择偏差。

## 正确的比较方式

在**同一批 Phase oracle-best 窗口**内，比较：

$r(P,GT),\quad r(R,GT),\quad r(L,GT),\quad r(RL,GT).$

然后报告配对差值：

$\Delta r_P = r(P,GT)-\max\{r(R,GT),r(L,GT)\}.$

同理，在 Remote-best 窗口内也比较所有模态，而不是跨不同窗口组比较。

还建议增加：

- 允许符号翻转后的最大相关；
- 固定、小范围时延内的相关，但不能逐窗无限搜索 lag；
- DTW 或形态距离；
- 吸气/呼气时间比误差；
- 峰谷位置误差；
- 波形谐波结构误差。

如果 RMSE 是 z-score 后的 RMSE，需要明确说明。两个标准化信号之间：

$\mathrm{RMSE}^2\approx 2-2r$

在无额外时延处理时，RMSE 约 0.95 对应的相关系数大约只有 0.55。因此，论文不能只说“0.950 RMSE 很好”，必须给出相对基线和至少一个更直观的波形指标。

------

# 七、E1c 应从“误差相关性”升级为“救援概率”

误差相关性可以做，但它不是最直接的证据。推荐增加以下指标。

设正确阈值为 $\tau$，例如 1 BPM：

## 1. 幅值双失败时的 Phase 救援率

$P(e_P\le \tau \mid e_R>\tau,\ e_L>\tau).$

这回答：

> Remote 和 Local 都失败时，Phase 有多少概率能救回来？

## 2. Phase 独特正确率

$P( e_P\le\tau,\  e_R>\tau,\  e_L>\tau ).$

## 3. Phase 破坏率

$P( e_P>\tau \mid e_{RL}\le\tau ).$

## 4. Oracle 上限

比较：

- R-only；
- R+L；
- R/L oracle；
- R/L/P oracle。

如果增加 Phase 后的 oracle 提升本身很小，那么任何复杂 Phase 门控的理论上限都很有限。这一步应该在实现 E2/E3 前先算出来。

例如：

$\Delta_{\mathrm{oracle}} = E[\min(e_R,e_L)] - E[\min(e_R,e_L,e_P)].$

如果这个差值只有 0.005 BPM，就不值得设计复杂门控；如果是 0.1 BPM，则值得继续。

------

# 八、当前 E2 的“共识门控”逻辑可能恰好反了

当前方案是：

> Phase 与 R+L 一致时，让 Phase 加入；不一致时排除。

问题是：如果 Phase 已经与 R+L 一致，它通常不会改变最终峰值，因此自然很难带来增益。这也解释了你们此前 Phase gate 几乎无收益。

Phase 真正有价值的窗口应该是：

- R 和 L 不一致；
- 或 R、L 都低置信度；
- Phase 与其中一个形成更可信的二对一共识；
- 或 Phase 提供了 R/L 谱中缺失但物理一致的峰。

## 我更建议的规则

### 情况 A：R、L 高置信且一致

$|BPM_R-BPM_L|\le T,$

并且两者谱熵低、峰值明显：

> 直接用 R+L，不引入 Phase。

因为此时 Phase 没有边际价值。

### 情况 B：R、L 不一致

如果：

$|BPM_P-BPM_R|<|BPM_P-BPM_L|,$

且 Phase 和 Remote 都有足够跨 tone 一致性，则选 $R+P$。

反之选 $L+P$。

### 情况 C：R、L 都低质量

只有此时才考虑 Phase 独立接管，但应要求：

- Phase 跨 tone 峰频一致；
- 相位谱峰不是边界峰；
- 邻窗 BPM 连续；
- Phase 的峰不是二次谐波；
- Phase 的静态场景噪声指标在可接受范围内。

换句话说，Phase 更适合作为：

> **低频率触发的 tie-breaker / rescue expert**

而不是“与主判断一致时加入的第三票”。

------

# 九、比 $\eta/\rho$ 更值得尝试的质量指标

你们发现模态级 $\eta/\rho$ 命中率只有约 64%，并不意外。尤其是：

$\rho = \frac{\text{峰值}} {\text{带内平均值}}$

只衡量“峰是否尖”，并不知道峰是否正确。一个尖锐的运动伪峰也会得到很高的 $\rho$。

论文中目前说：

> $\rho$ 抑制带内能量被尖锐假峰主导的信道。

这与定义不一致。按照当前公式，$\rho$ 实际会**奖励尖峰**，包括尖锐假峰。需要修改文字。

## 推荐的模态质量指标

### 1. 跨 tone 峰频一致性

$c_m = \left| \frac{ \sum_i w_{m,i}e^{j2\pi \hat f_{m,i}/B} }{ \sum_i w_{m,i} } \right|.$

或者简单使用：

- tone BPM 的加权 MAD；
- 落在模态主峰 $\pm 0.5$ BPM 内的权重比例；
- 主峰支持 tone 数量。

这比模态级单一 $\rho$ 更可靠，因为它利用了 72-tone 冗余。

### 2. 谱熵

$H_m = -\sum_{f\in\mathcal F_b}p_m(f)\log p_m(f).$

低谱熵代表候选集中，但仍需结合跨 tone 支持度。

### 3. 邻窗稳定性

呼吸 BPM 通常不会在相邻 1 秒窗口剧烈变化。可使用：

$q_{\mathrm{temp},m}(w) = \exp \left( -\frac{ |\hat f_m(w)-\hat f_{\mathrm{final}}(w-1)|^2 }{\sigma_f^2} \right).$

但必须使用因果历史，不能偷看未来窗口。

### 4. 相位专用指标

对 Phase 尤其值得检查：

- tone 间相位呼吸分量相干性；
- 相位 unwrap 跳变数量；
- 各 tone 主峰一致率；
- 静态段相位噪声 PSD；
- 相邻 event 的相位增量离群率；
- phase-tone coherence graph 的最大连通子图比例。

你们已经在 Fig. 2 用 tone-pair coherence，这个指标很可能比 $\eta/\rho$ 更适合做 Phase gate。

------

# 十、统计评估需要比现在更严格

你们的滑窗为 20 s、步长 1 s，相邻窗口共享 95% 数据。因此数千个窗口绝不是独立样本。

这会影响：

- 显著性检验；
- oracle 分组；
- 门控阈值搜索；
- Phase-best 窗口计数；
- 置信区间。

## 建议的评估单位

主统计单位应是：

- subject；
- recording；
- room × subject 场景；

而不是 overlapping window。

建议至少报告：

1. 12 条 HKH recording 的逐记录误差；
2. 每个方法的 recording-level mean；
3. 配对 bootstrap，按 subject 或 recording 重采样；
4. 方法间 paired difference 的 95% CI；
5. Phase-best 窗口在时间轴上的连续段数，而不只是窗口数。

因为 105 个 Phase-best 窗可能实际上来自一个连续 2 分钟片段，不能解释为 105 次独立救援。

## 门控阈值不能在测试集上扫描后报告最优值

例如 $T\in\{0.5,1,1.5,2\}$ BPM，如果在 HKH 12 条上选择最优 $T$，再在同一批数据报告 0.37 BPM，会有明显乐观偏差。

推荐：

- leave-one-subject-out；
- leave-one-room-out；
- 或在 CS 上定阈值、HKH 上测试，反向再做一次；
- 所有 median、normalization 和阈值必须由训练记录计算。

------

# 十一、0.376、0.381 和 0.405 之间可能没有统计显著性

目前你们将：

- 0.376 Remote-only；
- 0.381 Channel-only；
- 0.405 Equal；

解释成明确排名。

但差距只有：

$0.405-0.376=0.029\text{ BPM}.$

在 12 条记录规模下，这很可能小于跨 subject 变异，也可能小于 GT 和频率估计误差。建议先做 paired bootstrap 或 permutation test。

如果差异不显著，论文叙事应改成：

> Remote-only 在 HKH 上取得最低点估计，但与三模态融合差异有限；三模态等权在金属板跨场景实验中更稳定，呈现更好的跨域鲁棒性。

这比直接宣称“Phase 污染导致等权失败”更科学。

------

# 十二、建议增加的受控实验比继续搜索门控更重要

导师 briefing 中提出“中间场景”非常正确，我认为这是下一阶段最值得做的实验。

## 推荐三类受控实验

### 实验 1：工作点扫描

使用金属板或机械胸腔模型：

1. 保持呼吸振幅和频率固定；
2. 缓慢改变金属板基准位置；
3. 至少扫过约半个波长对应的路径差范围；
4. 每个工作点重复固定 5–10 mm 周期运动；
5. 记录 Remote IQ、Local IQ 和组合 Phase。

目标是观察：

- Remote/Local 径向响应随工作点周期变化；
- 切向响应是否与径向响应互补；
- Phase-only 的盲点是否存在；
- Phase-best 是否确实集中在幅值径向弱区。

这是验证核心物理故事最直接的实验。

### 实验 2：机械呼吸 + 非呼吸扰动

在机械周期运动上叠加：

- 缓慢位置漂移；
- 随机小幅抖动；
- 偶发整体移动。

比较 Phase 和幅值的退化速度。这可直接验证“HKH Phase 崩坏是否由人体微动导致”。

### 实验 3：完全静态噪声标定

无人、金属板静止时连续采集：

- Remote amplitude PSD；
- Local amplitude PSD；
- 单端 PCT phase PSD；
- 组合 phase PSD；
- event 间隔 jitter；
- unwrap 跳变；
- 不同 tone 的 phase noise。

最好画 Allan deviation 或不同积分时间下的相位方差，而不是直接假设白噪声。

------

# 十三、draft 中有几处需要立即修正的矛盾

## 1. Bluetooth 版本错误

英文摘要/References 中写 Bluetooth 5.2，中文写 Bluetooth 6.0。

应统一为：

> **Bluetooth Core Specification 6.0 introduced Channel Sounding.**

官方 Core 6.0 feature overview 将 Channel Sounding 列为新功能，并说明其包含 PBR 和 RTT。([bluetooth.com](https://www.bluetooth.com/core-specification-6-feature-overview/))

## 2. 顺序扫描因果叙事自相矛盾

摘要说：

> sequential tone sampling introduces continuous phase offsets beyond ±1。

但 §4.2 又计算最大扫描相位差只有约 $3.6^\circ$，并得出“几乎不构成主要影响”。

这两句话不能同时作为论文主结论。

你们的 Hilbert 连续相位对齐有效，并不证明该偏差来自顺序扫描。更可能的来源包括：

- 不同频率下复信道导数方向不同；
- 多径频率选择性；
- tone-specific RF phase/gain；
- 滤波和窗口边界效应；
- event 时间抖动；
- 低 SNR 下的相位估计偏差。

建议把第三个 constraint 改成：

> Frequency-dependent multipath and implementation nonidealities produce continuous inter-tone phase offsets beyond a binary sign model.

顺序扫描只能作为次要可能因素，除非后续实验能够隔离证明。

## 3. 有效采样率及周期数

250–500 ms 对应：

$f_s=2\text{--}4\text{ Hz},$

不是统一的“约 2 Hz”。

20 秒窗口在 0.1–0.35 Hz 内包含：

$2\text{--}7$

个周期，而不是固定约 4 个周期。可以说“典型 0.2 Hz 呼吸约 4 周期”。

## 4. “低采样率使时域对齐本质不可靠”过强

低采样率和短窗确实增加估计方差，但窄带正弦的分数相位仍可在高 SNR 下精确估计。建议改为：

> 在当前采样率、窗口长度和实测 SNR 下，时域相位估计对 event jitter、边界效应和非平稳扰动更敏感；谱幅融合在实验中表现出更高的 BPM 稳健性。

即把它写成“模型支持 + 实验观察”，不要写成本质不可能。

## 5. 公式错误

式 (4) 应为：

$\frac{\delta A_{d,i}(t)}{\bar A_{d,i}} \approx \operatorname{Re} \left\{ \frac{\delta Z_{d,i}(t)} {\bar Z_{d,i}} \right\}.$

若：

$\delta Z_{d,i}(t)=V_{d,i}\xi(t),$

则：

$\frac{\delta A_{d,i}(t)}{\bar A_{d,i}} \approx \operatorname{Re} \left\{ \frac{V_{d,i}}{\bar Z_{d,i}} \right\}\xi(t).$

当前式 (4) 把 $V/\bar Z$ 和 $\delta Z$ 又乘了一次，量纲和含义都不对。

式 (6) 左侧也应是 $\delta A/\bar A$，而不是 $\delta Z/Z$。

## 6. 模态融合公式矛盾

当前写：

$S_{\mathrm{final}} = \frac13(w_r\bar S_r+w_l\bar S_l+w_\phi\bar S_\phi).$

如果是等权，就应直接：

$S_{\mathrm{final}} = \frac{\bar S_r+\bar S_l+\bar S_\phi}{3}.$

如果是质量加权，则应：

$S_{\mathrm{final}} = \frac{ w_r\bar S_r+w_l\bar S_l+w_\phi\bar S_\phi }{ w_r+w_l+w_\phi+\epsilon }.$

不能同时叫“等权”又保留不明定义的 $w_m$。

## 7. “Total amplitude 无物理意义”建议收敛

总幅值：

$|Z_lZ_r|=|Z_l||Z_r|$

确实不提供新的独立自由度，但不能由此推出它一定没有感知价值。非线性组合有时仍可能改变噪声或增强共同变化。

建议写：

> Total amplitude is a deterministic product of the two single-ended amplitudes and therefore introduces no independent observable. We omit it to avoid redundant nonlinear features.

最好再补一个简单消融，而不是只凭物理判断排除。

------

# 十四、论文主线建议重新定位

目前 draft 的强叙事是：

1. Remote/local 物理对等；
2. 低采样率使时域对齐脆弱；
3. 顺序采样产生连续 tone 相位；
4. 等权三模态融合是正确先验；
5. 两级 Hilbert 解锁模态融合。

但现有消融结果实际上显示：

- HKH 上 Remote/Local 单模态略优于三模态等权；
- Phase-only 很差；
- Channel-only 谱 BPM 略优于完整三模态；
- 波形分支中的 Level-2 融合收益需要进一步确认；
- 顺序扫描又被你们自己的计算判断为影响很小。

因此建议把主线改成更经得住审稿的版本：

## 更稳妥的三条发现

### C1：双向 PCT 提供三类互补投影

Remote/Local 是双向端侧幅值观测，组合 Phase 是切向观测；三者具有相关但不同的噪声和灵敏度。

### C2：tone diversity 是最稳定、最大的增益来源

你们的消融已经非常清楚：

$1.640 \rightarrow 0.381\text{ BPM}.$

这是当前最强结果，应成为论文核心，而不是把主要篇幅放在效果微弱的模态加权上。

### C3：频率和波形需要不同融合原则

- BPM：谱域 tone voting 最稳健；
- 波形：需要连续相位对齐；
- 模态融合不是无条件有益，收益具有场景依赖性。

这比“等权模态融合永远正确”更有价值，也更符合数据。

------

# 十五、我建议的下一步执行优先级

不要立刻把 E1–E5 全部铺开。建议按下面顺序。

## P0：先做模型和统计审计

1. 修正 Phase 无零陷假设；
2. 修正双基地位移公式；
3. 修正 Null Score；
4. 计算 Phase 的 oracle 增量上限；
5. 对 0.376/0.381/0.405 做 recording-level 配对置信区间；
6. 检查 Phase-best 窗口是否集中在少数 subject 或连续时间段。

## P1：做 IQ 几何诊断

用 $Z_l,Z_r$ 计算：

- 径向呼吸能量；
- 切向呼吸能量；
- IQ 轨迹主轴；
- Phase-best 窗口的径向/切向比例；
- tone 间一致性。

这是决定论文物理叙事能否成立的关键。

## P2：做受控工作点扫描

如果只能新增一个实验，我建议选择这个，而不是先增加复杂 gating。

## P3：再测试简单、可解释的 rescue gate

最多先保留三个方法：

1. R+L baseline；
2. R/L conflict + Phase tie-break；
3. R/L low-confidence + Phase rescue。

暂时不要一次搜索几十个 C1/C2/C3 权重组合，否则很容易在 12 条数据上过拟合。

## P4：最后再决定论文方案

可能的结果有三种：

### 结果 A：Phase 救援证据明确且可门控

把自适应 Phase rescue 纳入主方法。

### 结果 B：Phase 有物理互补，但无法无监督检测

把 Phase 角色作为诊断发现，主 BPM 使用幅值，Phase 只用于波形或 future work。

### 结果 C：Phase oracle 增益也很小

不要强行保留 Phase BPM 融合。可以把论文贡献转向：

- BLE CS 双向观测建模；
- tone-level quality voting；
- 谱/波形双分支；
- Phase failure analysis。

负面发现同样有价值。

------

# 十六、对导师五个问题的直接回答

## 1. Phase 噪声是什么？

目前不宜直接假定为白噪声或固定方差。至少可能包括：

- 热噪声导致的相位估计误差；
- 残余频偏和短期本振相位噪声；
- event timing jitter；
- AGC/前端状态变化；
- PCT 校准残差；
- 低幅值时的异方差相位误差；
- unwrap 离群。

最好的方式不是先寻找复杂 nRF 射频噪声模型，而是做静态实测 PSD 和方差标定。

## 2. 是否有比 $\eta/\rho$ 更好的质量指标？

有，最推荐：

1. 跨 tone 峰频一致性；
2. tone-pair coherence；
3. 模态谱熵；
4. 邻窗因果稳定性；
5. Phase unwrap 离群率；
6. IQ 径向/切向能量比。

## 3. 是否应该增加中间场景？

**应该，而且优先级很高。**

理想中间场景是：

- 机械胸腔/软材料表面；
- 呼吸式非正弦运动；
- 可控基准位置；
- 可叠加随机整体微动。

它能把“人体材质、多径复杂度、非正弦呼吸、身体微动”逐步解耦。

## 4. “相位救援幅值”是否有文献先例？

有。FullBreathe 和 FarSense 都利用幅值与相位/IQ 投影的互补性缓解呼吸盲区；更新的研究也强调幅值和相位各自都可能退化，完整 IQ 几何或自适应投影通常更稳健。([researchers.mq.edu.au](https://researchers.mq.edu.au/en/publications/fullbreathe-full-human-respiration-detection-exploiting-complemen/?utm_source=openai))

但你们的 BLE CS 特点在于：

- 双向 PCT；
- 两个端侧幅值；
- 组合相位；
- 低事件率；
- 多 tone 双向顺序测量。

所以真正新颖的地方不是“Phase 无零陷”，而是：

> **幅值—相位互补关系如何在双向 BLE CS PCT 结构中表现，以及为什么这种互补在机械目标和人体目标之间显著变化。**

## 5. 是否转向波形、呼吸模式或 apnea？

可以，但不要因为猜测“0.376 已达到硬件上限”就立即转向。呼吸带 GT 的 0.2–0.3 BPM 误差目前需要独立标定，不能直接作为事实写入论文。

建议先：

1. 做频率注入仿真，确定 20 s 窗、当前采样率下的 BPM 算法下限；
2. 做机械 GT 测试；
3. 做呼吸带自身重复性测试。

如果 BPM 确实已经饱和，波形恢复会更有研究空间。但波形需要增加比 RMSE 更有生理意义的指标，例如：

- inspiration/expiration ratio；
- respiratory cycle duration variability；
- peak/trough timing；
- apnea episode detection；
- irregular breathing classification。

------

# 最终建议

我建议你们下一轮不要以“把 BPM 从 0.384 优化到 0.376 以下”为主要目标，而应回答一个更重要的问题：

> **BLE CS 的组合 Phase 在什么可观测条件下提供幅值之外的增量信息？这种增量能否在没有 GT 的情况下可靠识别？**

对应的最短研究路径是：

1. **修正物理模型：径向/切向互补，而非幅值有零陷、Phase 无零陷；**
2. **计算 Phase 的 oracle 增量上限；**
3. **用原始 PCT IQ 验证 Phase-best 窗口的复平面几何；**
4. **增加机械工作点扫描实验；**
5. **只在 R/L 冲突或双低置信时让 Phase 充当 rescue expert；**
6. **采用 subject/recording-level 独立评估，避免重叠窗口和阈值搜索造成虚假增益。**

即使最后 Phase 无法形成有效门控，这项研究仍然可以得到一个很强的结论：

> **BLE CS 呼吸感知的主要可靠增益来自 tone diversity；模态 diversity 具有条件性，特别是组合 Phase 在真人场景中受到明显的噪声和运动敏感性限制。**

这个结论比强行证明“三模态等权一定最好”更可信，也更容易形成扎实的论文贡献。