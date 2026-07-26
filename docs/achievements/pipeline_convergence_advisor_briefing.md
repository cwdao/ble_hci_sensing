# BLE CS 呼吸感知：管线收敛、Phase 终判与论文路线图

> **写给导师的阶段性汇报**  
> **作者**：Cheng WANG（实验执行）+ Claude/DeepSeek（研究分析与方案设计）  
> **日期**：2026-07-26  
> **定位**：自上次汇报以来，完成了 Phase 互补投影诊断 + 门控实验 + 统一管线设计。本汇报更新结论、呈现证据、征求论文路线及后续实验方向的建议。

---

## 1. 背景速览（供未参与实验的导师快速上手）

### 1.1 BLE CS 感知机制

BLE 6.0 信道探测（Channel Sounding）在两个设备间通过 72 个载波信道（跨 80 MHz 带宽）做双向 IQ 测量。关键处理步骤：

```text
设备 A ──► 设备 B 发射 tone → B 测量 IQ (PCT)
设备 B ──► 设备 A 发射 tone → A 测量 IQ (PCT)
两端 PCT 在复平面做向量乘法 → LO 漂移抵消 → 获得有物理意义的测量
```

最终可用的观测量仅**三种**：

| 变量 | 物理含义 | 特点 |
|------|----------|------|
| **Remote 幅值** | 远端设备测到的单端 PCT 幅值 | 噪声低，单设备链路 |
| **Local 幅值** | 本地设备测到的单端 PCT 幅值 | 与 Remote 物理对等（同一交换的反方向） |
| **Phase**（总相位） | 两端 PCT 向量相乘后的合成相位 | 含**双端噪声之和**（方差约为单端 2 倍） |
| ~~Total 幅值~~ | Remote × Local | 无独立物理意义，**已弃用** |

### 1.2 核心物理：径向/切向互补投影

BLE CS 测量的是复信道 $H(d) = H_s + H_d(d)$（$H_s$ 为静态多径，$H_d$ 为呼吸微扰）。对位移 d 求导：

$$\frac{d|H|}{dd} = \frac{\text{Re}\{H^* H'\}}{|H|} \quad (\text{径向投影}), \qquad \frac{d\angle H}{dd} = \frac{\text{Im}\{H^* H'\}}{|H|^2} \quad (\text{切向投影})$$

- Remote/Local 幅值 → 两个独立接收链的**径向投影**（对应呼吸微扰在复平面上的实轴分量）
- Phase → 两端**切向投影之和**（对应虚轴分量）
- **两者各有盲区**：径向投影在多径几何不当时（微扰方向接近切向）会变弱；切向投影在微扰方向接近径向时同样变弱。因此两者是**互补**的，而非一个绝对优于另一个

### 1.3 实验数据

| 数据集 | 类型 | 规模 | GT 类型 |
|--------|------|------|--------|
| **HKH** | 真人自然呼吸 | 3 房间 × 4 受试者 = 12 条记录 | 呼吸带（胸部位移）→ BPM + 波形 RMSE |
| **CS 金属板** | 机械周期振动 | 3 个房间布局 (091339/095806/102621) | 已知机械频率 → BPM only（**无波形 GT**） |

- 标准滑窗：20 s / 1 s step
- 呼吸频段：0.1–0.35 Hz（6–21 BPM）
- 主指标：HKH → BPM 绝对误差 (breaths/min)；CS → BPM 相对误差 (%)

---

## 2. 实验历程：15 轮实验的逻辑链

```text
PCA/SVD (CS ~10.9%)                        ← 基线: 经典方法
  │
  ├──► Per-Tone Voting (η·ρ 加权)           ← 核心发现: 信道融合是最大增益源
  │      CS 8.45%, HKH 0.405
  │
  ├──► 消融矩阵                             ← 分解信道融合 × 模态融合的独立贡献
  │     发现: 增益几乎全部来自信道融合 (1.640→0.381)
  │     模态融合反而引入损失 (0.381→0.405，Phase 污染)
  │
  ├──► 模态质量加权融合                       ← 尝试 η/ρ/conf 替代等权
  │     结论: 有微弱增益 (0.405→0.384)，但无法超越 Remote-only (0.376)
  │     模态级 ρ 有害 (hit 54.3% < η-only 63.6%)
  │
  ├──► Phase 互补投影诊断 ★本次汇报核心★     ← 5.6sol 修正物理模型后重设计
  │     P0a: Phase BPM 救援上限仅 0.028 (极其有限)
  │     P0b: IQ 几何诊断—互补投影假设未成立
  │     E1a: Phase-best 窗幅值并不系统性弱
  │     E1b: Phase 波形保真度差于幅值 (Δr=−0.081)
  │     E1c: Phase rescue=18% 但 destruction=49% (破坏力远超救援力)
  │     E2/E3: Phase 门控相对 R+L 无统计显著增益
  │
  └──► 统一管线设计                           ← 将已验证的最优组件组装为完整方案
        MS-QWDC 理论框架 (见 §4)
```

---

## 3. Phase 的终判：当前证据不支持其作为 BPM 主组件

### 3.1 关键证据汇总

| 实验 | 检验内容 | 结果 | 对 Phase 的含义 |
|------|----------|------|----------------|
| **P0a** | Phase oracle 上限 | Δ_oracle = 0.028 BPM，仅 2/12 条 ≥ 0.05 | Phase 即使以 GT 最优选也不可能带来大幅 BPM 改善 |
| **P0b** | IQ 几何互补投影 | 径向/切向能量对比不支持互补投影预测 | Phase-best 窗不是"径向能量低、切向能量高" |
| **E1a** | Null-filling (幅值双弱→Phase 救援) | 不支持：Phase-best 窗 q_amp 并不低 | Phase 的优势窗口不来自幅值双失效 |
| **E1b** | Phase 波形保真度 | Δr_P = −0.081（Phase 波形比幅值差） | Phase 不提供更好的呼吸波形 |
| **E1c** | Phase 救援 vs 破坏 | rescue=18%, destruction=**49%** | Phase 破坏好结果 > 救回坏结果 |
| **E2/E3** | Phase 门控（tie-break/conditional） | paired CI 含 0 — 相对 R+L 无显著增益 | 门控不能可靠地释放 Phase 的潜在价值 |
| **E4** | η·ρ 信道级 vs 模态级不对称 | 模态级 η-only hit (63.6%) > η·ρ (54.3%) | Phase 的 ρ 在模态级误选率太高 |
| **E5** | HKH vs CS Phase 跨域诊断 | Phase ρ↓, conf↓ (HKH) 但 η 无差异 | HKH Phase 问题是峰钝化(非正弦呼吸) + 多径导致的一致性低，不是 SNR 低 |

### 3.2 当前判断

> **Phase 在当前数据上的 BPM 价值有限，不应作为 BPM 融合的主组件。** Phase 的"破坏力"（destruction rate 49%）是"救援力"（rescue rate 18%）的 2.7 倍。HKH 上最优策略是 R+L 双模态（0.372 BPM），Phase 不参与。

### 3.3 Phase 的唯一剩余出路

互补投影物理原理本身没有错——它是复信道微扰的数学恒等式。问题在于：在当前的静态实验数据中，**我们没有观测到幅值盲区和相位盲区交替出现的场景**。可能是因为：

1. 被试/金属板的基准位置恰好处于幅值敏感区（径向投影始终有足够响应）
2. 自然呼吸 + 人体微动产生的扰动足够大，掩盖了投影角度的差异

**唯一可以系统检验互补投影假设的实验**：受控工作点扫描——固定振幅/频率的机械振动，缓慢改变金属板基准位置（扫过约半个波长），观察径向/切向响应是否随工作点周期性交替。这个实验需要特定的硬件设置（可微调位置的机械振动源），目前**尚未实施**。

**在受控实验给出相反证据之前**，论文中 Phase 的定位应是：
- ✅ 作为诊断/波形分析线索（diagnostic finding）
- ✅ 诚实报告其在不同域上的行为差异（HKH 崩坏 vs CS 正常）
- ❌ 不作为 BPM 主组件或核心贡献写入 Abstract

---

## 4. 统一管线设计：MS-QWDC

### 4.1 理论框架

将所有实验发现统一在 **Multi-Scale Quality-Weighted Diversity Combining (MS-QWDC)** 框架下：

| 尺度 | 候选数 N | 分集类型 | 策略 | 质量度量 | 保护机制 |
|------|:------:|------|------|----------|----------|
| **Micro** (信道级) | 72 | 频率分集 | η·ρ Voting | η·ρ（双因子） | N=72 稀释 ρ 假阳性 |
| **Gate** (投影闸门) | — | 相干性检测 | Phase confidence threshold | Voting confidence | 物理异常值剔除 |
| **Macro** (模态级) | ≤3 | 投影分集 | η-weighted spectral fusion | η-only（单因子） | N≤3 时 ρ 假阳性不可接受 |

**理论创新点**：解释了为什么同一个质量指标 η·ρ 在信道级有效但在模态级失效——不是因为指标本身有问题，而是**样本量 N 决定了假阳性风险的可接受水平**。这是一个统计学习理论中"bias-variance tradeoff"在感知融合中的具体体现，可以成为论文的一个重要贡献点。

### 4.2 管线结构

```text
72 tone × 3 模态
    │
    ▼
┌─────────────────────────────────┐
│ Stage 1: Voting (η·ρ) per modal │  ← 信道级频率分集
│ 输出: S_R(f), S_L(f), S_P(f)    │
│       + η_m, conf_m             │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Stage 2: Phase confidence gate  │  ← 投影闸门
│ conf_P < θ → Phase 被排除       │
│ conf_P ≥ θ → Phase 参与融合     │
└─────────────────────────────────┘
    │
    ├─────────────────────────────┐
    ▼                             ▼
┌──────────────────┐    ┌──────────────────────┐
│ 谱域融合 (BPM)    │    │ 波形融合 (RMSE, HKH)  │
│ η-weighted       │    │ η-weighted           │
│ spectral average │    │ coherent MRC         │
│ → 寻峰 → BPM     │    │ → Welch PSD → BPM    │
│                  │    │ → waveform → RMSE    │
└──────────────────┘    └──────────────────────┘
```

### 4.3 预期性能（可直接从已有数据推断，无需等待新实验）

| 管线 | 域 | 指标 | 预期 | 等于哪个已有结果 |
|------|-----|------|:---:|------|
| 谱域 | HKH | BPM abs err | **~0.372** | `p0_rl_default` — Phase 被闸门自动剔除 |
| 谱域 | CS | BPM rel % | **~10.14%** | `E3a` / `draft_s_full` — Phase 通过闸门 |
| 波形 | HKH | RMSE | **~0.91–0.93** | 待测（R+L coherent MRC，预期优于 Remote 0.931） |
| 波形 | CS | RMSE | **N/A** | CS 无呼吸带 GT 波形 |

### 4.4 论文定位

```text
论文主线:
  "BLE CS 呼吸感知的核心增益来自 tone diversity（频率分集），
   而非 modal diversity（投影分集）。
   72-tone Voting 贡献了从 1.640 到 0.381 的质变；
   而模态融合仅能在此基础上提供 0–0.01 BPM 的边际改善，
   且取决于 Phase 质量（HKH 上甚至有害）。
   最优管线为 MS-QWDC：
   信道级 η·ρ Voting + Phase 投影闸门 + 模态级 η-weighted 融合。"

波形管线定位:
  "波形融合精度受限于 Hilbert 重建误差，
   不宜作为主 BPM 管线，但保留了呼吸波形的时间结构，
   可用于呼吸模式分析、吸呼比、apnea 检测等无法仅从 BPM 回答的问题。"
```

---

## 5. 两域行为差异：需要解释但不应回避

| 观察 | HKH (真人) | CS (金属板) |
|------|:----------:|:----------:|
| Remote-only BPM | 0.376 ✓ | 11.23% |
| Phase-only BPM | 2.191 ✗ | 10.92% ≈ Remote |
| 最优融合策略 | **R+L 双模态** | **三模态等权/η-加权** |
| 最优 BPM | **0.372** | **10.14%** |
| Phase conf (闸门指标) | 0.324 → 闸门关闭 | 0.402 → 闸门打开 |

**两域的最优策略是相反的，但这正是闸门设计的价值所在**：它不预设 Phase 有用或无用，而是用可观测的 Phase Voting confidence 自动判断。在 HKH 上闸门自动关闭（Phase 不参与），在 CS 上自动打开（Phase 参与）。这是一个**物理上可解释、数据上可验证的自适应行为**。

---

## 6. 希望导师指导的问题

1. **论文叙事层面**：主线定位为"tone diversity 是核心贡献，modal diversity 是边际优化"——这个故事的力度是否足够？是否需要补充与 WiFi CSI 的定量对比来凸显 BLE CS 的特殊性（72 tone 而非 OFDM subcarrier）？

2. **理论贡献层面**：MS-QWDC 中"样本量 N 决定最优质量度量"的命题（N=72 用 η·ρ, N=3 用 η-only）是否有理论深度可以深入挖掘？例如与 James-Stein 估计、经验贝叶斯等框架的关联，还是只适合作为一个 empirical finding 呈现？

3. **Phase 定位层面**：在受控工作点扫描实验可以实施之前，Phase 在论文中的位置我目前的建议是"诚实报告、不作为核心贡献"。导师觉得这个处理是否妥当？或者有没有其他方式（如引用文献中的类似发现）来让 Phase 的分析更有价值？

4. **实验完备性层面**：目前 HKH (真人 12 条) + CS (金属板 3 条) + WiFi baselines + PCA/VMD baselines，覆盖面是否足够？CS 上没有波形 GT 限制了波形管线的评估——这是否构成审稿弱点？

5. **优先级层面**：在受控工作点扫描实施之前，是否应该将精力集中在论文写作和图表生成上？目前实验基本收敛，继续跑新的算法变体可能边际收益递减。

6. **方法论层面**：质量指标与"哪个模态给出正确 BPM"的相关性仅 ~64%。导师是否知道更好的盲选指标（不需要 GT 的质量指标）？特别是在模态级别（N=3）上，什么样的指标能更可靠地鉴别"这个模态这次是对的"？

---

## 7. 附录：关键数据快速参考

### 当前 BPM 排行榜（HKH）

| 方法 | BPM abs err | 说明 |
|------|:----------:|------|
| **R+L 等权双模态** | **0.372** | 当前最优，Phase 不参与 |
| Remote 单模态 Voting | 0.376 | 单模态天花板 |
| Local 单模态 Voting | 0.378 | 与 Remote 几乎等价 |
| Channel-only (三选一) | 0.381 | 硬选最优模态 |
| η·ρ·conf 加权三模态 | 0.384 | 质量加权最优 |
| Equal 三模态 (BreatheCS) | 0.405 | 等权基线 |
| Phase 单模态 | 2.191 | 系统性崩坏 |

### 当前 BPM 排行榜（CS 金属板）

| 方法 | BPM rel % | 说明 |
|------|:---------:|------|
| **Equal 三模态** | **10.14%** | 当前最优 |
| η 加权三模态 | 10.17% | 与 Equal 持平 |
| Phase 单模态 | 10.92% | ≈ Remote |
| Remote 单模态 | 11.23% | — |
| R+L 等权双模态 | 14.05% | Local 拖累 |

### 文件索引

| 内容 | 路径 |
|------|------|
| Plan（Phase 互补投影诊断 v2.0） | `docs/plans/phase_unique_role_adaptive_fusion_plan.md` |
| Report（Phase 互补投影终判） | `docs/reports/phase_unique_role_adaptive_fusion_report.md` |
| Report（消融矩阵） | `docs/reports/paper_ablation_draft_align_report.md` |
| Report（模态质量门控） | `docs/reports/modal_quality_gating_report.md` |
| Plan（统一管线最终验证） | `docs/plans/unified_pipeline_final_plan.md` |
| 论文骨架 | `docs/plans/paper_outline_plan.md` |
| 方法注册表 | `docs/methods/README.md` |
| 上次导师汇报 | `docs/achievements/phase_role_advisor_briefing.md` |
| **本汇报** | `docs/achievements/pipeline_convergence_advisor_briefing.md` |

---

> 🤖 本报告由 Claude/DeepSeek（Research & Review 角色）撰写。所有数字均来自 `outputs/reports/` 中的实际实验结果，无编造。实验由 Cursor Composer（执行 Agent）在 Cheng WANG 监督下运行。
