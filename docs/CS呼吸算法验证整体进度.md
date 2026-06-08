# CS呼吸算法验证整体进度

本文档是总体思路的大纲。大体上包含：模态融合+信道融合。

模态融合：幅值和相位用谁，或者直接融合使用；

信道融合：多个信道融合成一个。

## BLE CS做无线感知的原理？

这部分是 Y = HX+N那几个公式，不算算法，不列举。

## BLE CS提供什么变量？

一次CS process 提供72信道的IQ测量。每个信道下，两个设备会先后发送一次CS tone，并由对方测得接收的IQ，在BLE CS中这被称作PCT（相位校正项， phase correlation term, 意思是最终相位获取的中间项）。这个部分结束后，设备会将自己的IQ测量结果经由HCI report 报告给应用层。假设我们指定initiator 作为最后的测距方，那么reflector就会把它的测量结果传回initiator,反之亦然。

最终，initiator 获得了本地的IQ结果和远端设备的PCT，它将两端PCT在I-Q平面施以向量乘法，这样就抵消了载波频偏。最后，我们能获得的是：

- 本地幅值、相位：由本地设备测得的PCT。幅值是相对稳定的，但相位是额外包含随机噪声和本振漂移的。
- 远端幅值、相位：远端设备的PCT，发回到了本地。幅值和相位所含噪声与本地PCT类似。
- 合成的总幅值、相位：PCT向量乘法后得来。相位已经抵消了一部分本振漂移，所以可用了。幅值则受两端共同的影响。

### 这些变量哪些质量好，哪些质量一般？

在某个场景记录金属板脚本活动（091339，----），

- 使用呼吸频段能量占比$\tau$选择一个最大的信道，然后比较。这个方法相当于只给最高信道赋权重，其他的都置0 。

$\tau = \frac{E_i(B_r)} {E_i(B_0)+\epsilon}.$ 不做信道融合，只看变量差异。

<img src="./assets/image-20260601223543433.png" alt="image-20260601223543433" style="zoom:50%;" />

现象：

2b,4b不够单窗长度，画的时候只有一个点。其他的可以做滑动窗口估计。

直观的看，remote 幅值最好，total 幅值被local 幅值影响了，相位没有想象中的差，仅弱于remote 幅值。

原因：

我们认为可能的原因是，相位整体上效果仅次于Remote 幅值，没有预想的差。但不会比总幅值，remote/local 幅值都强。从理论上，幅值所夹带的噪声就小于相位。至于三个幅值变量谁更好，应该是 某个幅值>总幅值>另一个幅值。因为向量乘法会把两个幅值合成，相当于为好的引入了差的一方的噪声。而实际上，remote / local 所对应的多径环境也是相反的，谁更好谁更差都不好说。需要换个环境重复。

> 余：其他环境验证结论：remote/local 谁更好不一定。

此外，在当前场景下，一个隐蔽的现象是，幅值效果好的地方，相位效果就偏差，相位效果好的时候，幅值效果就偏差。相对而言比较符合幅值-相位互补理论。但这里具体相位和remote/local 哪个互补，我的想法是和总幅值互补。

<img src="./assets/image-20260601230833968.png" alt="image-20260601230833968" style="zoom: 50%;" />

## 融合信道信息是否有效果



比较三种baseline方法：

- 取单信道能量最大者

- 多信道平均融合

- 多信道按峰度融合。所谓峰度：

  峰值尖锐度

  有些信道 $\tau$ 不低，但频谱是宽的，不一定是稳定呼吸。可以加：

  $S_i = \frac{\max_{f\in B_r} P_i(f)} {\operatorname{median}_{f\in B_r} P_i(f)+\epsilon}.$

  这个分数越高，说明呼吸峰越突出。

我们在场景091339四个变量上比较这三种方案：

<img src="./assets/image-20260601225703448.png" alt="image-20260601225703448" style="zoom:50%;" />

结论是符合预期的。注意的是，所有场景下，峰度融合要优于平均融合，但多数情况不如 单信道最大能量。

画一个热力图对比模态融合X信道融合更明显：

<img src="./assets/image-20260601225916854.png" alt="image-20260601225916854" style="zoom:50%;" />

## 总结

上述实验表明以下事实，相位要比预想的稳定，虽然不如夹带噪声最小的某个单侧幅值，但也要优于噪声更大的某侧幅值，以及总幅值。

多信道算法中，无论施行什么样的加权方式，效果都不如只保留最大的，其他舍弃的这种加权方式。在多信道呼吸监测中，也许对于提升BPM准确率这个指标而言，只要引进了非最大能量的信道做平均，就会把BPM向偏离真实值的方向去拉。结果就是，BPM估计的标准差变小了，但也更偏离真实值了。所以，在考虑信息时要综合所有的信息，防止倍频等等，但在最终计算BPM的时候，不应该利用所有信息的去计算BPM。

## 改进方案2：

提出的后续问题：

### 幅值相位的互补性对谁成立，

1. 首先，我们希望在目前的基础上，先看看幅相互补在原始波形上是否存在，对谁存在？
1. 具体做法：首先，我们对总幅值、remote /local 幅值，相位这四种变量使用每个窗口的最大能量信道进行估计BPM。前面已经实现过了。现在在此基础上画一个波形比较图：例如，对于总相位，找出所有时间窗中BPM 估计最准的那个窗，然后把该窗口内能量最大的信道记下来，画一张该信道所有四种变量经过高通滤波之后的波形图比较。四个变量的能量比数值也需要标注在图上。这个图就是在总相位最准的那个窗口、信道下，其他变量和该变量的归一化后的波形对比。
1. 然后，第二张图是总相位BPM估计最差的窗口，记下来该窗口总相位能量比最高的信道，然后画出这个信道的四种变量高通滤波之后的波形比较。
1. 第三张图是总相位BPM估计值居中的窗口下，该窗口总相位能量最大的信道，四种变量经过高通滤波后的波形比较。
1. 所有三张图都需要标注每个变量的能量比。

### 窗口内变量的互补性：

在某个窗口内，四种变量谁单信道能量比的BPM 最准

### 只联合最好的信道最好的变量可以吗

我们在前面的方法中初步验证了所有信道都给加权是没意义的，同时相位似乎比较稳定。那么，我们提出一种最高能量变量融合的方案：对每个窗口，计算四种变量下最大能量信道是哪个，可能每个变量都会对应一个最大能量的信道。然后融合的时候，权重分别使用以下策略：

- 总相位，remote,local 三个等权重，估计BPM。总幅值不使用（因为这就是remote/local的结合体）
- 总相位, remote,local 按各自的能量比数值，归一化后给权重。
- 总相位0.5，remote/local 各自0.25.



尝试2：幅相互补性那里，能量比改为峰度指标，权重策略增加下面的 ：

- 三个变量只用指标靠前的前两个变量，然后等权重各自0.5；
- 三个变量只用指标靠前的前两个变量，然后按峰度数值归一化后给权重。

实现脚本：`notebooks/scripts/chFusion_plan2.py`（`Plan2Config.channel_metric` 可切换 η / ρ；默认 **η**）。

### 改进方案2 阶段小结（091339 金属板脚本）

#### 信道选择：能量比 η 优于峰度 ρ

| 指标 | Single remote | Single phase | 说明 |
|------|---------------|--------------|------|
| **η 选路** | **10.91%** | 15.13% | 与早期「最大能量信道」结论一致 |
| ρ 选路 | 20.26% | 19.77% | ρ 易选到「峰尖但频率错」的信道 |

Uniform 多信道融合**不是**对各信道 BPM 求平均，而是对**归一化呼吸频谱**等权平均后再寻峰（见 `chfusion.estimate_segment_bpm_methods`）。Uniform 与 selector 无关，091339 上 remote Uniform 恒为 17.09%。

#### 模态融合（phase + remote + local，各变量各自 max-η 信道）

| 方法 | mean err% | 备注 |
|------|-----------|------|
| Single remote | **10.91%** | 本场景 oracle 上界（事后知 remote 更优） |
| Modal top2 equal | 13.04% | 每窗按 η 取前二变量等权 0.5 |
| Modal η-weight | 13.25% | 三变量按 η 加权 |
| Modal equal | 13.61% | 三变量等权 |
| Single phase | 15.13% | |
| Single local | 30.49% | 误选 local 代价大 |

**结论：**

1. η 选路下，模态融合误差落在 **Single remote（10.9%）与 Single phase（15.1%）之间**，符合「综合较好单侧幅值与相位」的预期。
2. 部署时无法预知 remote/local 孰优；η + 模态融合（尤其 **top-2**）可在不绑定单侧的前提下，接近 remote+phase 折中（~13%），避免误用 local（~30%）。
3. **top-2** 按窗对 phase/remote/local 的 max-η 排序，取前二融合；多数窗口 local η 最低，等价于动态剔除较差一侧幅值（非固定去掉 local）。
4. 互补性波形：phase / remote / local 三种参考变量各出 best/worst/median 三图（带通波形 + η/ρ + 各变量 BPM）；方法对比见排行榜柱状图、段×方法热力图、三面板小提琴图（`plot_plan2_comparison_figures`）。

<img src="./assets/image-20260602180859484.png" alt="image-20260602180859484" style="zoom:50%;" />

![image-20260602182324462](./assets/image-20260602182324462.png)

#### 跨域重复性验证（095806 金属板脚本）

脚本：`notebooks/scripts/chFusion_plan2_diff_domain_verify.py`（分段来自 `show_analysis_cs_frames_095806.ipynb`，其余配置与 091339 一致，η 选路）。

| 方法 | 091339 | 095806 |
|------|--------|--------|
| Single remote | **10.91%** | 12.16% |
| Single phase | 15.13% | 11.12% |
| Single local | 30.49% | 13.17% |
| Uniform remote | 17.09% | **9.15%** |
| Modal top2 equal | 13.04% | 10.61% |
| Modal equal | 13.61% | 10.50% |

**可重复：** Single remote 仍优于 Single local；模态融合在两域均明显优于误用 local 的代价；095806 各方法整体误差更低。

**域相关差异：** 095806 上 Uniform phase（6.75%）优于所有 Single；Single remote 不再是最优，Uniform remote 反而优于 Single remote。模态融合略优于 Single remote/phase，而非严格落在两者之间；top-2 未优于三变量 equal。

**备注：** 095806 段 `4b` 长度略短于窗长，modal 统计仅含 6 个 breath 段。

![image-20260602221021579](./assets/image-20260602221021579.png)

---

## 改进方案3：Per-Tone Voting 融合（voting_fusion）

**Plan**：[`docs/plans/voting_fusion_plan.md`](plans/voting_fusion_plan.md)  
**Report**：[`docs/reports/voting_fusion_report.md`](reports/voting_fusion_report.md)  
**脚本**：`notebooks/scripts/chFusion_voting_fusion.py`  
**模块**：`src/ble_analysis/voting_fusion.py`

### 核心思路

将 72 tone 视为 72 个独立"选民"，每窗每个 tone 独立估计 BPM → η·ρ 加权直方图投票 → 选出 winning BPM。

| 方法 | 091339 | 095806 | 102621 | 跨域 mean |
|------|--------|--------|--------|-----------|
| T0-V3 Per-Tone η·ρ voting | 13.77% | **6.84%** | 6.99% | **9.20%** |
| T3 Voting+Modal hybrid | 14.92% | 7.94% | 6.24% | 9.70% |
| B0 Single Remote | **10.91%** | 12.16% | **8.29%** | 10.45% |
| Modal top2 equal | 13.04% | 10.61% | 4.69% | 9.45% |

**结论**：T0-V3 跨域 9.20% 优于 Modal top2 9.45%，但场景互补性强——voting 在 095806 极强（6.84% vs Modal 10.61%），在 091339 弱于 Modal（13.77% vs 13.04%）。

---

## 改进方案4：窗级共识门控（voting_gating）

**Plan**：[`docs/plans/voting_gating_plan.md`](plans/voting_gating_plan.md)  
**Report**：[`docs/reports/voting_gating_report.md`](reports/voting_gating_report.md)  
**成果汇报**：[`docs/achievements/voting_gating_achievement_report.md`](achievements/voting_gating_achievement_report.md)  
**脚本**：`notebooks/scripts/chFusion_voting_gating.py`  
**模块**：`src/ble_analysis/consensus_gating.py`

### 核心思路

利用 T0-V3 voting 和 Modal top2 的场景互补性，在窗级通过共识/双峰性/persistence 等门控信号动态选择方法。

| 排名 | 方法 | 跨域 mean |
|------|------|-----------|
| **1** | **G4 Single fallback** | **8.65%** |
| 2 | G5 Bimodality gating | 8.72% |
| 3 | G1 Simple consensus | 8.95% |
| 4 | G2 Conf priority | 8.99% |
| 5 | G6 Persistence voting | 9.00% |

**结论**：
- G4（共识→平均，分歧→Single Remote）跨域 8.65% 为当时全局最优
- 无单一门控策略在所有场景均最优——G5 在 091339 最优（12.27%），G6 在 095806 最优（6.55%），G2 在 102621 最优（4.36%）
- 理想标准（< 8.5%）未达成

---

## 改进方案5：模态×信道 系统性融合（systematic_modal_channel_fusion）

**Plan**：[`docs/plans/systematic_modal_channel_fusion_plan.md`](plans/systematic_modal_channel_fusion_plan.md)  
**Report**：[`docs/reports/systematic_modal_channel_fusion_report.md`](reports/systematic_modal_channel_fusion_report.md)  
**成果汇报**：[`docs/achievements/systematic_modal_channel_fusion_achievement_report.md`](achievements/systematic_modal_channel_fusion_achievement_report.md)  
**脚本**：`notebooks/scripts/chFusion_systematic_fusion.py`  
**模块**：`src/ble_analysis/systematic_fusion.py`

### 核心思路

首次系统分离**信道策略**（C-Single/C-Uniform/C-Vote/C-VoteP）和**模态策略**（M-Remote/M-Phase/M-Equal/M-η/M-Top2）的独立贡献，填充二维网格中 12 个关键盲区单元格。

### 主结果

| 排名 | 方法 | cs_091339 | cs_095806 | cs_102621 | **跨域 mean** |
|------|------|-----------|-----------|-----------|---------------|
| **1** | **B1 Vote→Equal modal** | 13.22 | **6.50** | 5.63 | **8.45%** |
| 2 | G4 Single fallback | 12.39 | 9.05 | **4.51** | 8.65% |
| 3 | C2 Uniform→η modal | 13.43 | 7.93 | 6.10 | 9.15% |
| 4 | B2 Vote→η modal | 15.65 | 6.47 | 5.35 | 9.16% |
| 5 | T0-V3 Per-Tone η·ρ | 13.77 | 6.84 | 6.99 | 9.20% |
| 6 | Modal top2 equal | **13.04** | 10.61 | 4.69 | 9.45% |

### 假设验证汇总

| 假设 | 判定 |
|------|------|
| H1 Phase voting 跨域优于 Remote voting | **未证实**（11.07% vs 9.20%） |
| H2 信道×模态存在交互效应 | **已验证** — Equal 有效但 Top2 无效 |
| H3 Vote per modal + Top2 < T0-V3 且 < Modal | **未证实** — B3=9.92%，但 B1 Equal=8.45% |
| H4 Phase voting 在 095806 特别有效 | **仅单场景**（5.81% vs 6.84%） |
| H5 Persistence 可迁移到 phases/模态融合 | **已废弃**（A2 17.49%, B4 16.59%） |

### 结论

- **B1（Vote per modal → 三模态等权谱融合）以 8.45% 突破理想标准（< 8.5%），为当前全局最优 pipeline 候选**
- 信道策略与模态策略存在显著交互——最优模态融合权重取决于信道策略
- Vote→Top2（H3）的系统性失败是本实验最重要的负结果，提示 Voting 降低了模态间差异性
- 091339 仍是瓶颈（所有方法 > 12%）

---

## 下一轮：B1 联合门控与诊断（b1_gating_and_diagnosis）

**Plan**：[`docs/plans/b1_gating_and_diagnosis_plan.md`](plans/b1_gating_and_diagnosis_plan.md)  
**状态**：待实现

### 目标

1. 将 B1 加入 G4 门控框架，推动跨域 < 8.0%
2. 诊断 Vote→Equal 有效但 Vote→Top2 无效的机制
3. 091339 专项攻坚（B1 + 双峰性门控）
4. Voting→谱构造方式 ablation

---

## 方法演进路线图

```text
Single Remote (10.45%)
    ↓
Modal top2 (9.45%)          ← Plan2: 模态融合
    ↓
T0-V3 Voting (9.20%)        ← voting_fusion: 信道融合
    ↓
G4 Gating (8.65%)           ← voting_gating: 窗级门控
    ↓
B1 Vote→Equal (8.45%)       ← systematic_fusion: 二维联合优化
    ↓
G4-B1 联合门控 (待验证)      ← b1_gating_and_diagnosis: 门控+诊断
```
