# BLE CS 呼吸感知：Phase 模态的角色困惑与自适应融合方向

> **写给导师的阶段性汇报**  
> **作者**：Cheng WANG（实验执行）+ Claude/DeepSeek（研究分析与方案设计）  
> **日期**：2026-07-26  
> **定位**：介绍当前实验进展、核心困惑、物理分析与下一步方向，征求导师意见

---

## 1. 项目背景（简短）

### 1.1 BLE CS 如何做呼吸感知？

BLE 6.0 引入了信道探测（Channel Sounding, CS），其核心测量机制是：

1. 两个 BLE 设备对 72 个信道（跨 72 MHz 带宽）依次做双向测量
2. 每个信道测量中，双方互相发送一个 CS tone，各自记录对方的 IQ 值为 PCT（Phase Correction Term）
3. 两端 PCT 在复平面做向量乘法后，**LO 漂移抵消**，获得有物理意义的相位

最终的可用观测量为三种（不是四种）：

| 变量 | 物理含义 | 噪声来源 |
|------|----------|----------|
| **Remote 幅值** | 远端设备测到的 PCT 幅值（单端） | 单设备噪声 |
| **Local 幅值** | 本地设备测到的 PCT 幅值（单端） | 单设备噪声 |
| **Phase**（总相位） | 两端 PCT 向量相乘后的相位 | **两端噪声之和** |
| ~~Total 幅值~~ | Remote × Local 的幅值乘积 | 双方噪声乘积，**无独立物理意义，不使用** |

### 1.2 关键物理特性

**幅值（Remote/Local）**：
- 单端测量，噪声低
- 反映多径干涉图样的变化 → 对位移的响应是**非线性**的
- 存在"零陷"工作点：特定多径配置下，小幅值位移几乎不改变幅值（dA/dd ≈ 0）

**相位（Phase）**：
- 双端测量，噪声 ≈ 两端之和（理论上方差为幅值的 2 倍）
- 与反射体位移呈**线性**关系：ΔΦ = 4πΔd/λ（λ ≈ 12.5 cm @ 2.4 GHz）
- **无零陷**：不存在 dΦ/dd = 0 的工作点（不考虑 2π 缠绕）

**Remote 与 Local 的物理对等性**：
- 二者来自同一次 CS 交换的两个方向，物理上完全对等
- 谁更优完全取决于具体多径环境和设备位置，不可预设

### 1.3 实验数据

| 数据集 | 类型 | 规模 | Ground Truth |
|--------|------|------|-------------|
| **HKH** | 真人呼吸 | 3 房间 × 4 受试者 = 12 条 | 呼吸带（胸部位移） |
| **CS 金属板** | 机械振动 | 3 个场景 (091339/095806/102621) | 已知机械频率 |

- 标准滑窗：20 s 窗长 / 1 s 步长
- 呼吸频段：0.1–0.35 Hz (6–21 BPM)
- 主指标：HKH → BPM 绝对误差 (breaths/min)；CS → BPM 相对误差 %

---

## 2. 当前实验进展

### 2.1 方法论演化（已完成的 11 轮实验）

```text
PCA/SVD (~10.9%) → Single Remote (10.5%) → Modal Top2 (9.5%)
  → Per-Tone Voting (9.2%) → G4 Gating (8.7%)
  → B1 Vote→Equal Modal (8.45%, CS 跨域最优)
  → G4-B1-v2 三候选门控 (8.05%, 物理不自洽，不推荐)
  → B2 Coherent-MRC 时域融合 (9.4%, BPM 未超越 B1)
  → B1+B2 混合门控 (全线劣于 B1, 已废弃)
  → HKH 12 场景验证 (B1 系列 BPM 全面最优)
  → B3 统一管线 (B1 BPM + B2 波形, 当前推荐)
  → HKH 消融矩阵 (Phase 系统性崩坏的发现)
  → 模态质量感知融合与门控 (质量加权路线触及上限)
```

**当前推荐方案**：B3 Simplified（逐模态 Voting → 三模态等权谱融合 BPM + 两级 Hilbert 波形）

### 2.2 最近两轮关键实验

#### 实验 A：HKH 消融矩阵（2026-07-25）

将 BreatheCS 管线拆解为信道融合和模态融合两个独立维度，HKH 12 场景结果：

| 方法 | BPM abs err | 含义 |
|------|------------:|------|
| Remote 单模态 Voting | **0.376** | 当前 HKH 天花板 |
| Local 单模态 Voting | 0.378 | 与 Remote 几乎等价（物理对等成立） |
| Channel-only（Voting → 三选一） | 0.381 | 硬选最优模态 |
| **BreatheCS**（Voting → 三模态等权融合） | **0.405** | ⬅ 等权融合反而不如单模态 |
| Phase 单模态 Voting | **2.191** | ⬅ Phase 系统性崩坏 |
| 完全不融合（单 tone 单模态） | 1.640 | 信道融合是最关键的增益源 |

**核心发现**：信道融合贡献了 1.26 BPM 的增益（1.640 → 0.381），但模态融合在此基础上反而**增加了 0.024 BPM 的误差**（0.381 → 0.405）。根因是 Phase 质量太差（2.191），等权融合时污染了好模态。

#### 实验 B：模态质量感知融合与门控（2026-07-26）

尝试用 η（呼吸频段能量比）/ ρ（谱峰峰度）做模态级质量加权，替代 1:1:1 等权，避免 Phase 污染。同时测试 Phase 专用门控。

**HKH 结果**：

| 方法 | BPM | vs Equal | vs Remote |
|------|----:|---------:|----------:|
| Remote-only | 0.376 | −0.029 | — |
| E3d (η·ρ·conf 加权) | 0.384 | −0.021 | +0.008 |
| E3b (η·ρ 加权) | 0.388 | −0.017 | +0.012 |
| E3a (η 加权) | 0.396 | −0.009 | +0.020 |
| Equal (BreatheCS) | 0.405 | — | +0.029 |
| Phase-only | 2.191 | +1.786 | +1.815 |

**CS 金属板结果**：

| 方法 | BPM rel% | vs Equal |
|------|---------:|---------:|
| Equal (BreatheCS) | **10.14%** | — |
| E3a (η 加权) | 10.17% | +0.03 |
| Phase-only | 10.92% | +0.78 |
| Remote-only | 11.23% | +1.09 |
| Channel-only | 12.51% | +2.37 |

**关键发现**：

1. **质量加权路线在 HKH 上有微弱增益**：回收了 Equal → Remote 差距的 72%（0.021/0.029），但无法完全消除 Phase 的污染——即使 Phase 权重降至 0.1，其（错误的）谱峰仍影响加权平均
2. **CS 上质量加权无增益甚至略差**：Equal 仍是最优方案
3. **η·ρ 在模态级选择上不如 η-only**：η-only top-1 命中率 63.6% vs η·ρ 54.3%——与信道级结论（η·ρ > η-only）相反
4. **Phase 专用门控（E4）几乎无增益**：无论 hard/soft gate，ΔBPM < 0.005
5. **质量指标与"谁给出正确 BPM"的相关性仅 ~64%**：即使在最好的情况下，>36% 的窗口选错最优模态

---

## 3. 核心困惑：Phase 的矛盾行为

### 3.1 两域 Phase 表现的巨大差异

| 指标 | HKH（真人） | CS（金属板） |
|------|-----------|------------|
| Phase-only BPM | **2.191** abs | **10.92%** rel |
| Phase vs Remote/Local 差距 | ~5.8× | ~1.0×（Phase ≈ Remote） |
| Phase 为 oracle 最优的窗口占比 | **6.1%** | **14.4%** |
| 等权融合 vs Channel-only | 0.405 vs 0.381（等权更差） | 10.14% vs 12.51%（等权更优） |

**在 HKH 上 Phase 是系统性崩坏的（2.191 vs 0.376），但在 CS 上 Phase 几乎与 Remote 持平（10.92% vs 11.23%）。**

这不是"Phase 总是差"或"Phase 总是不差"——它取决于实验条件。问题是：**取决于什么？**

### 3.2 一个更深层的问题

即使 Phase 在全局 mean 上差于幅值模态，它仍在 **HKH 6.1% / CS 14.4%** 的窗口中是个体最优的。在这些窗口中，Remote 和 Local 的 BPM 可能更差。

**Phase 有没有幅值模态无法替代的独特作用？**

---

## 4. 物理分析：Phase 的独特价值假说

### 4.1 "零陷填充"（Null-Filling）假说

回顾幅值与相位的物理特性：

```text
幅值 A = |Σ α_i·exp(jφ_i)|
  → 多径干涉的非线性函数
  → 在干涉零陷处：dA/dd ≈ 0
  → 存在对位移"失明"的工作点

相位 Φ ≈ 4πd/λ（主导路径）
  → 位移的线性函数
  → dΦ/dd = 4π/λ ≈ const（不考虑缠绕）
  → 不存在"失明"工作点
```

**假说**：在少数窗口中，Remote 和 Local 幅值**同时落入多径零陷**——两个方向的干涉图样都恰好对呼吸位移不敏感。此时 Phase ——虽然噪声更高——是**唯一仍对位移保持敏感的信号**。

这解释了为什么 Phase 只在 ~6–14% 窗口中是最优的（零陷窗口是小概率事件），以及为什么在这些窗口中 Phase 确实优于幅值。

**可检验预测**：在 Phase 为 oracle 最优的窗口中，Remote η 和 Local η 应**双双偏低**（低于各自全域中位数）。

### 4.2 为什么 HKH 和 CS 上 Phase 表现不同？

可能的原因（待实验验证）：

| 假说 | 机制 | 可检验 |
|------|------|--------|
| **人体微动** | 被试身体的微小移动（非呼吸）引入宽带相位噪声，金属板无此问题 | HKH Phase η 方差 > CS |
| **呼吸非正弦性** | 真人呼吸有吸/呼不对称，Phase 线性保形 → 频域能量分散到谐波 | HKH Phase ρ < CS Phase ρ |
| **多径复杂度** | HKH 房间多径更丰富 → Phase 的 tone 间一致性更差 | HKH Phase Voting confidence < CS |
| **零陷频率** | 两个域的多径几何不同 → 零陷发生的概率不同 | Phase-best 占比 HKH 6% vs CS 14% |

### 4.3 对话：Phase 到底该不该用？

如果"零陷填充"假说成立，答案不是简单的"用"或"不用"：

- **多数窗口**：Remote/Local 幅值 SNR 足够高 → Phase 不需要，甚至因其高噪声而有害
- **零陷窗口**（~6–14%）：幅值双双失明 → Phase 是唯一可用信号
- **共识窗口**：Phase 的 BPM 与 R+L 一致 → Phase 即使参与也不造成破坏，且能提供 diversity

因此，**正确的策略不是"加权融合"，而是"条件激活"**：
- 默认使用 Remote+Local 双模态等权（安全基线）
- 检测到特定条件（零陷 / BPM 共识 / Phase 自身高质量）时激活 Phase

### 4.4 与 WiFi 感知文献的关联

WiFi CSI 呼吸感知文献中也有类似讨论：在菲涅尔区边界附近，幅度对位移的灵敏度极低，但相位仍保持灵敏度（Wang et al. 2017, "Understanding and Modeling of WiFi Signal Based Human Activity Recognition"）。BLE CS 的情况与此类似，但有一个额外的复杂因素：Phase 噪声是双端叠加的（PCT 乘积），比 WiFi 单端 CSI 相位噪声更高。

---

## 5. 下一轮实验计划（已撰写详细 plan）

围绕上述假说，已撰写执行计划：[`docs/plans/phase_unique_role_adaptive_fusion_plan.md`](../plans/phase_unique_role_adaptive_fusion_plan.md)

五个实验模块：

| 实验 | 内容 | 目的 |
|------|------|------|
| **E1** 诊断 | 零陷填充检验 + 波形保真度 + 跨模态分集 | 验证 Phase 的独特价值假说 |
| **E2** 算法 | 谱峰一致性门控（用 BPM 一致性替代 η/ρ 间接代理） | 直接门控是否优于质量代理？ |
| **E3** 算法 | R+L 默认 + Phase 条件激活（零陷/共识/质量三条件） | 真正的自适应策略 |
| **E4** 诊断 | η·ρ 在信道级有效但在模态级失效的根因 | 指标的非平凡传播 |
| **E5** 诊断 | HKH vs CS Phase 跨域差异根因 | 物理理解 |

**期望的突破**：如果 E1 的零陷假设被验证，就能为 Phase 提供一个清晰的、物理上有意义的独特角色——"零陷救援"——使自适应策略既自圆其说又在实验中可量化。

---

## 6. 希望导师给予指导的问题

1. **物理层面**：BLE CS 中 Phase 含两端 LO 噪声之和，这个噪声的具体统计特性（白噪声？flicker？与信道频率的关系？）我们目前缺乏对 nRF54L15 射频前端的详细噪声模型。导师是否有相关经验或参考文献？

2. **方法论层面**：目前质量指标（η/ρ）与"哪个模态给出正确 BPM"的相关性仅 ~64%。是否存在更好的窗级质量指标？例如基于多 tone 间相位一致性的指标、或基于呼吸波形"可预测性"的指标？

3. **实验设计层面**：目前 HKH 和 CS 是两个完全不同的物理场景（人体 vs 金属板），Phase 在两者上的行为截然不同。是否应该增加一个**中间场景**（如模拟肺/假人，既有类呼吸运动又无人体微动）来隔离"人体微动"变量的影响？

4. **叙事层面**：如果 Phase 的独特价值确实在于"零陷填充"，这个叙事在呼吸感知社区是否有先例？导师是否知道 WiFi/FMCW 文献中类似的"相位救援幅度"的论证方式，可以供我们参考？

5. **优先级层面**：当前 HKH 上 BPM 绝对误差的最优值（0.376 breaths/min）似乎已接近硬件能力的上限——因为呼吸带 GT 本身也存在 ~0.2–0.3 BPM 的标注误差。是否应该将精力更多地转向波形质量（RMSE）、呼吸模式分类、或 apnea 检测等更"高维"的感知任务？

---

## 7. 附录：关键数据快速参考

### 当前最优方法排行榜（CS 金属板）

| 方法 | 跨域 mean | 物理自洽 |
|------|----------:|:--------:|
| B1 Vote→Equal (当前推荐) | 8.45% | ✅ |
| Modal top2 equal | 9.45% | ✅ |
| B0 Single Remote | 10.45% | ✅ |
| WiFi MRC 最优变体 | 10.78% | ✅ |
| Zhuo2023 PCA-VMD | 11.31% | ✅ |

### 当前最优方法排行榜（HKH 真人）

| 方法 | BPM abs err | RMSE | 波形 |
|------|------------:|------|:----:|
| B1 Uniform Remote | 0.37 | — | ❌ |
| B1 Vote→Equal | 0.41 | — | ❌ |
| **B3 Simplified（推荐）** | **0.41** | **0.950** | ✅ |
| Zhuo Z1-no-VMD | 0.44 | 1.070 | ✅ |
| B2-D Hilbert-MRC | 0.68 | 0.950 | ✅ |

### 各方法的文件索引

| 内容 | 路径 |
|------|------|
| 整体进度 | [`docs/CS呼吸算法验证整体进度.md`](../CS呼吸算法验证整体进度.md) |
| 方法注册表 | [`docs/methods/README.md`](../methods/README.md) |
| 论文骨架稿 | [`docs/plans/paper_draft_skeleton.md`](../plans/paper_draft_skeleton.md) |
| Plan（消融对齐） | [`docs/plans/paper_ablation_draft_align_plan.md`](../plans/paper_ablation_draft_align_plan.md) |
| Report（消融对齐） | [`docs/reports/paper_ablation_draft_align_report.md`](../reports/paper_ablation_draft_align_report.md) |
| Plan（质量门控） | [`docs/plans/modal_quality_gating_plan.md`](../plans/modal_quality_gating_plan.md) |
| Report（质量门控） | [`docs/reports/modal_quality_gating_report.md`](../reports/modal_quality_gating_report.md) |
| **Plan（Phase 独特角色）** | **[`docs/plans/phase_unique_role_adaptive_fusion_plan.md`](../plans/phase_unique_role_adaptive_fusion_plan.md)** |
| 本汇报 | [`docs/achievements/phase_role_advisor_briefing.md`](../achievements/phase_role_advisor_briefing.md) |

---

> 🤖 本报告由 Claude/DeepSeek（Research & Review 角色）撰写。实验由 Cursor Composer（执行 Agent）在 Cheng WANG 的监督下运行。所有数字均来自实际实验结果（`outputs/reports/`），无编造。
