# 论文条件性内容追踪 Plan — 实验依赖性 & 决策分支

> **定位**：本文件不是算法 plan，而是追踪 **论文 skeleton 中哪些内容取决于尚未完成的实验**，以及在每种实验结果下应如何调整论文。  
> **关联**：[Phase Plan v2.0](phase_unique_role_adaptive_fusion_plan.md) · [Paper Skeleton v0.4](paper_draft_skeleton.md)  
> **日期**：2026-07-26  
> **状态**：活跃追踪中

---

## 决策树总览

```text
P0a: Phase oracle Δ?
  ├─ Δ ≥ 0.05 BPM → Phase BPM rescue 值得做 ──→ E2/E3
  │   ├─ E2/E3 leave-one-out 有增益 → Phase rescue → C2 升级
  │   └─ E2/E3 leave-one-out 无增益 → Phase 信号有限 → C2 不升级，但在 Discussion 中讨论
  └─ Δ ≤ 0.01 BPM → Phase BPM 救援空间极小
      └─ Phase 角色 → 纯 diagnostic finding / 波形用途（不承诺 BPM 增益）

P0c: 0.376/0.381/0.405 显著性？
  ├─ 差异不显著 → BreatheCS = "comparable BPM + best joint BPM-waveform"
  └─ Remote 显著更优 → 需诚实报告，可能修改 BreatheCS 默认策略

P0b: IQ 径向/切向诊断？
  ├─ 互补投影成立 → 强物理叙事支持
  └─ 无清晰模式 → 物理叙事更保守："实验观察但不完全理解"

P2: 受控实验可行？
  ├─ 是 → 最强物理验证
  └─ 否 → 依赖 IQ 诊断 + CS 金属板数据作为替代
```

---

## 依赖项逐一追踪

### D1 · Phase BPM Oracle 增量上限

| 字段 | 内容 |
|------|------|
| **实验** | P0a：每条 HKH recording 的 Δ_oracle = E[min(e_R,e_L)] − E[min(e_R,e_L,e_P)] |
| **当前状态** | ✅ 已执行（2026-07-26）→ **条件 C** |
| **优先级** | 🔴 P0（最高——决定 Phase BPM 路线是否值得投入） |
| **结果文件** | `outputs/reports/phase_p0_oracle_delta.json` |

### D1 · 状态更新 2026-07-26

**实验结果**：12 条 HKH recording；mean Δ_oracle = **0.0283** BPM，median = 0.0291；≥0.05：2 条；≤0.01：2 条；中间带 0.01–0.05：**8 条**。max=0.059（room_B-sbj_C），min=0.0（room_C-sbj_A）。
**判定**：条件 C（灰色地带）
**建议的论文调整**：定位为 "modest conditional improvement"；不承诺强 Phase BPM 收益；若做门控，变体 ≤2–3 且必须 leave-one-out。
**对执行的门控含义**：允许在 **E1/E4/E5 完成后** 进入简化版 E2/E3；**现在不要写门控代码**。

**条件 A**：Δ_oracle ≥ 0.05 BPM 在多数 recording 上

```text
→ Phase BPM rescue 有实质空间
→ 继续 E2/E3 的门控实验
→ 论文中可承诺 Phase 的 BPM 增量价值
→ 受影响段落：
   - [skeleton §1.5] 可加入："A quality/consensus mechanism determines whether composite phase contributes useful modal diversity."
   - [skeleton §7.4] 可写得更积极，Phase 作为 conditional rescue
   - [skeleton §8 Conclusion] 可提 Phase rescue 为方法贡献的一部分
```

**条件 B**：Δ_oracle ≤ 0.01 BPM 在多数 recording 上

```text
→ Phase BPM 救援空间极有限
→ E2/E3 不再以 BPM 增益为主要目标；可简化为诊断确认
→ 论文不应承诺 Phase BPM 融合收益
→ 受影响段落：
   - [skeleton Abstract] ✅ 已不依赖 Phase BPM 贡献（v0.4 已移除）
   - [skeleton §1.5] 不加入 Phase gating 描述
   - [skeleton §7.4] 改写成："Phase oracle gain is small; the value of Phase may lie in waveform fidelity or future apnea detection rather than BPM improvement."
   - [skeleton §8 Conclusion] 强调 negative finding 也是贡献
   - [skeleton Contributions C3] 加入："We further find that the composite phase provides at most marginal BPM gain over endpoint amplitudes alone..."
```

**条件 C**：Δ_oracle 在 0.01–0.05 BPM 之间

```text
→ 灰色地带——有空间但有限
→ 简化 E2/E3 变体（最多 2–3 个），关注 leave-one-out 下的稳健性
→ 论文定位为 "modest conditional improvement"
```

---

### D2 · IQ 几何诊断（径向/切向呼吸能量）

| 字段 | 内容 |
|------|------|
| **实验** | P0b：用原始 PCT IQ 计算径向/切向呼吸能量，检验 Phase-best 窗是否对应径向能量系统性下降 |
| **当前状态** | ✅ 已执行（2026-07-26）→ **条件 B（偏 partial）** |
| **优先级** | 🔴 P0 |
| **结果文件** | `outputs/reports/phase_p0_iq_geometry.json`、`outputs/figures/phase_p0_radial_tangential_energy.png` |

### D2 · 状态更新 2026-07-26

**实验结果**：Phase-best (n=105) vs Remote-best (n=1549)：
- 联合径向 E_rad,joint：Phase-best **略高**（18.11M vs 18.10M，相对差 ~0.05%）——**不符合**「径向系统性偏低」预测
- 切向 E_tan,P：Phase-best **略高**（39.46M vs 37.86M，相对差 ~4.2%）——方向符合但幅度弱
**判定**：条件 B（无清晰互补投影模式）；切向仅有弱方向性信号，不足支撑强物理叙事
**建议的论文调整**：保持 §4.1 抽象级径向/切向表述，**不强调实验已验证机制**；§7.4 承认 IQ 几何未给出简单 radial-vs-tangential 解释。

**条件 A**：互补投影成立

```text
即：Phase-best 窗中 E_rad(R) 和 E_rad(L) 系统性偏低，E_tan(P) 系统性偏高
→ 物理故事得到强有力支持
→ 受影响段落：
   - [skeleton §4.1] 可在观测模型中加入对 P0b 发现的引用
   - [skeleton §1.4 insight 3] 可更具体地描述互补投影机制
   - [skeleton §7.4] 可用 P0b 结果支撑 Phase 条件性价值的物理解释
```

**条件 B**：无清晰模式

```text
即：Phase-best 窗与幅值径向能量无系统性关联
→ 物理叙事需保守处理
→ 受影响段落：
   - [skeleton §4.1] 保持现有抽象级别（径向/切向互补），但不强调实验验证
   - [skeleton §1.4 insight 3] 改为更弱的表述："...but the physical mechanism underlying this conditionality requires further investigation"
   - [skeleton §7.4] 承认："IQ geometric analysis did not reveal a simple radial-vs-tangential explanation..."
```

---

### D3 · Phase 救援门控（E2/E3）

| 字段 | 内容 |
|------|------|
| **实验** | E2 tie-breaker + E3 conditional activation，leave-one-subject-out 评估 |
| **当前状态** | ✅ 已执行（2026-07-26）→ **条件 B** |
| **优先级** | 🟡 P1（取决于 D1 结果） |
| **前置** | D1 条件 C → 已按灰色地带简化为 3 变体 |
| **结果文件** | `outputs/reports/phase_adaptive_fusion_hkh_summary.json`、`phase_adaptive_fusion_cs_summary.json` |

### D3 · 状态更新 2026-07-26

**实验结果**：
- HKH（LOSO，全部折 `T_agree=1.0`）：R+L=**0.372**；e3_conditional=0.376；e2_tiebreak=0.376；Equal=0.405。R+L vs 门控 paired CI **含 0**（无显著增益）
- CS（t=1.0）：Equal=**10.14%** 最优；tie-break=10.77%；conditional=11.29%；R+L=14.05%（无 Phase 很差）
**判定**：条件 B（leave-one-out 下无显著优于 R+L+Remote 的 Phase rescue 算法贡献）
**建议的论文调整**：Abstract 保持不承诺 Phase BPM；§5.4 等权/自适应门控不升级为推荐；§7.4 诚实报告 gate 失败；可强调 HKH 上 **R+L 优于三模态等权** 这一旁路发现。

**条件 A**：在 leave-one-out 下显著优于 R+L default 和 Remote-only

```text
→ Phase adaptive rescue 是有效的算法贡献
→ 受影响段落：
   - [skeleton Contributions C2] 可升级加入 Phase rescue gate
   - [skeleton Abstract] 可加入一句描述 Phase 条件性贡献
   - [skeleton §5.4] 将 E2/E3 最佳变体描述为 BreatheCS 的推荐模态融合策略
   - [skeleton §7.4] 描述 Phase rescue 的工作机制和触发条件
```

**条件 B**：无显著增益

```text
→ Phase rescue 不可靠——论文将其作为 diagnostic finding
→ 受影响段落：
   - [skeleton Abstract] 保持 v0.4——不承诺 Phase BPM 贡献
   - [skeleton §5.4] 等权作为基线，自适应门控列为 future work
   - [skeleton §7.4] 诚实报告 Phase gate 失败 + 可能原因分析
   - [skeleton §8 Conclusion] 加入："Our attempts to gate Phase activation based on observable quality indicators did not yield statistically significant BPM improvement..."
```

---

### D4 · 0.376/0.381/0.405 统计显著性

| 字段 | 内容 |
|------|------|
| **实验** | P0c：Recording-level paired bootstrap 95% CI |
| **当前状态** | ✅ 已执行（2026-07-26）→ **条件 B** |
| **优先级** | 🔴 P0 |
| **结果文件** | `outputs/reports/phase_p0_statistical_audit.json`、`outputs/figures/phase_p0_statistical_audit.png` |

### D4 · 状态更新 2026-07-26

**实验结果**（recording-level paired bootstrap，B=10000）：
- Remote (0.376) − Equal (0.405)：mean_diff = **−0.029**，95% CI **[−0.058, −0.004]**，**不含 0** → Remote 显著优于 Equal
- Remote − Channel (0.381)：CI 含 0（不可区分）
- Channel − Equal：CI 含 0（边界）
**判定**：条件 B（Remote 显著优于 BreatheCS Equal）
**建议的论文调整**：Abstract/§6.3/§8 不得声称 BreatheCS BPM 最优；须诚实报告 Remote-only 消融在 HKH BPM 上更优；§5.4 考虑是否修正默认模态融合策略。

**条件 A**：差异不显著（CI 包含 0）

```text
→ 不能声称 BreatheCS BPM 最优
→ 受影响段落：
   - [skeleton Abstract] 改 "achieves 0.405 BPM error" → "maintains comparable BPM accuracy (0.405) while providing the best joint rate-and-waveform performance"
   - [skeleton §6.3] "BreatheCS = 0.405 (not significantly different from Remote-only 0.376 at p<0.05)"
   - [skeleton §7.2] 强调统计等价性而非排名
   - [skeleton §8 Conclusion] 不声称 BPM 最优
```

**条件 B**：Remote 显著优于 BreatheCS

```text
→ 必须诚实面对自己的消融优于完整方法
→ 受影响段落：
   - [skeleton §5.4] 可能需要修改 BreatheCS 默认模态融合策略
   - [skeleton §7.2] 深入讨论为什么等权三模态劣于双模态
   - [skeleton §8 Conclusion] 将模态融合改进列为明确的 future work
```

---

### D5 · Phase-best 窗口时间聚集性

| 字段 | 内容 |
|------|------|
| **实验** | P0c：Phase-best 窗口的连续段数 vs 窗口总数；subject 分布 |
| **当前状态** | ✅ 已执行（2026-07-26）→ **条件 B** |
| **优先级** | 🟡 P1 |
| **结果文件** | `outputs/reports/phase_p0_statistical_audit.json`（`phase_best_clustering`） |

### D5 · 状态更新 2026-07-26

**实验结果**：Phase-best 共 **105** 窗，跨 recording 连续段合计 **58** 段；top-2 subject 占比 **37.1%**（room_A-sbj_A:23 + room_A-sbj_C:16）；分布覆盖 11/12 recording（仅 room_C-sbj_A = 0）。
**判定**：条件 B（较分散，非少数连续段垄断）
**建议的论文调整**：可描述为低频但较广的条件性救援；仍应报告段数/subject 分布，避免「105 次独立救援」措辞。

**条件 A**：高度聚集

```text
即：105 个 Phase-best 窗来自 2–3 个连续时间段 / 1–2 个 subject
→ 不能声称"105 次独立救援"——论文必须报告聚集性
→ 受影响段落：
   - [skeleton §7.4] 必须报告连续段数和 subject 集中度
   - 任何"Phase rescue"叙述必须加上"concentrated in specific temporal segments/subjects"
```

**条件 B**：分散

```text
即：Phase-best 窗均匀分布在各 recording 和各时间段
→ 可声称 Phase 在特定条件下有广泛（但低频）的救援能力
```

---

### D6 · 受控实验（P2）

| 字段 | 内容 |
|------|------|
| **实验** | 工作点扫描 / 机械呼吸+非呼吸扰动 / 静态噪声标定 |
| **当前状态** | ❓ 可行性待确认 |
| **优先级** | 🟢 P2（取决于硬件和时间） |

**条件 A**：可行

```text
→ 论文增加一个实验验证 section（可能作为 §4 或 §6 的延伸）
→ 受影响段落：
   - [skeleton §4] 可用受控实验数据替代/补充当前的金属板数据
   - [skeleton Contributions C3] 可升级为包含受控验证
```

**条件 B**：不可行

```text
→ 依赖 IQ 几何诊断（D2）+ CS 金属板数据作为物理验证
→ 论文中说明受控实验作为 future work
```

---

### D7 · E4 信道 vs 模态 ρ 不对称 & E5 跨域 Phase 差异

| 字段 | 内容 |
|------|------|
| **实验** | E4 + E5 诊断 |
| **当前状态** | ✅ 已执行（2026-07-26） |
| **优先级** | 🟡 P1 |
| **结果文件** | `outputs/reports/phase_e4_channel_vs_modal_rho.json`、`phase_e5_hkh_vs_cs.json`、`phase_e1_diagnostics.json` |

### D7 · 状态更新 2026-07-26

**E4 实验结果**：
- 模态级 hit：HKH η-only **63.6%** > η·ρ **54.3%**；CS η **33.4%** > η·ρ **32.3%**
- 分歧窗：HKH η 胜 424 vs ηρ 胜 262（n_disagree=762）；CS 上 ηρ 误选 Phase 更明显（22/91）
- ρ 定义提醒：ρ=峰值/带内均值**奖励尖峰（含假峰）**，不是“抑制假峰”

**E5 实验结果**：
- H5a（HKH Phase η 方差更大）：**不成立**（HKH std 0.083 ≈ CS 0.086）
- H5b（HKH Phase ρ 更低）：**成立**（3.41 vs 9.98）
- H5c（HKH Phase conf 更低）：**成立**（0.324 vs 0.402）
- Phase abs err：HKH **2.09** vs CS **1.26**

**建议的论文调整**：
- [skeleton §5.3] 明确：**信道级可用 η·ρ，模态级优先 η-only**；修正 ρ 文字描述
- [skeleton §7.4] 跨域：HKH Phase 峰钝/置信低（ρ、conf），而非单纯 η 方差更大

**附：同批 E1 诊断摘要（供 D3 前置判断）**：
- E1a H1（q_amp）：HKH/CS **均不支持**（Phase-best q_amp 不系统性偏低；双弱比例 ~44%）
- E1b H2（波形）：Phase-best 窗内 Δr_P mean=**−0.081**，Phase 波形**未**优于幅值（H2 不支持）
- E1c：HKH rescue_rate=**0.180**，unique_correct=**0.012**，destruction_rate=**0.487**；R-L 误差相关 0.84 vs R-P 0.10
→ Phase 偶有救援，但破坏风险高；与 D1=C 一致，E2/E3 仅做简化确认
---

## 检查表 & 时间线

### 执行前

- [x] 确认 Phase Plan v2.0 P0–E5 的执行可行性
- [ ] 确认受控实验（P2）的硬件和时间可行性
- [x] 将本文件交给 Cursor Composer：实验完成后回填 §D1–D7 的实验结果（P0 项已回填）

### P0 完成后

- [x] **D1**：Δ_oracle 值填入 → **条件 C**（mean 0.028；简化 E2/E3，且须先做完 E1/E4/E5）
- [x] **D2**：IQ 几何诊断结果 → **条件 B / partial**（无清晰互补投影；叙事保守）
- [x] **D4**：显著性检验 → **条件 B**（Remote 显著优于 Equal）
- [x] **D5**：窗口聚集性 → **条件 B**（105 窗 / 58 段，较分散）
- [ ] 根据以上 4 项结果，**更新 skeleton 中受影响段落**（交给 Claude/DeepSeek Review）

### E1–E5 完成后

- [x] **D3**：Phase gate 结果 → **条件 B**（无显著 BPM 增益；Phase 不升级为算法贡献）
- [x] **D7**：E4/E5 诊断 → 已回填
- [ ] 最终定稿 Abstract、§7 Discussion、§8 Conclusion（交给 Claude/DeepSeek Review）

### 受控实验可行性确认后

- [ ] **D6**：如可行 → 设计实验 detail plan；如不可行 → 标记 paper limitation

---

## 附：Skeleton 中已标记 [待实验验证] 的段落索引

以下 skeleton 段落的内容取决于上述实验——Cline/DeepSeek Review 时需逐条核对：

| Skeleton 位置 | 内容 | 依赖实验 | 备注 |
|--------------|------|---------|------|
| Abstract: "modal diversity...is conditional" | 措辞强弱 | D1, D3 | D3 成功 → 措辞可更强 |
| §1.4 insight 3: "composite phase behaves differently" | 是否有物理解释 | D2 | D2 成功 → 可附加机制 |
| §1.5: 是否加入 Phase gating 描述 | 是否加入 | D1, D3 | 仅 D3 成功时加入 |
| §5.4: 推荐模态融合策略 | 等权 vs 自适应 | D3, D4 | D3 成功 → 自适应为推荐 |
| §6.3: 0.405 vs 0.376 的叙述 | 排名 vs 等价 | D4 | D4 不显著 → "comparable" |
| §6.5 Table 8-B: Phase 2.191 的讨论 | 正面/负面 | D1 | D1 Δ 小 → 诚实负面 |
| §7.2: "等权是合理先验" | 保留/修正 | D4 | D4 Remote 显著优 → 需修正 |
| §7.4: Phase 条件性角色 | 积极/保守 | D1, D2, D3 | 综合判定 |
| §8 Conclusion: takeaway 三条 | 是否包含 Phase | D1, D3 | D3 失败 → Phase 只放 future work |

---

## 给执行 Agent 的指令

本文件是论文层的条件追踪，不是算法执行 plan。请在完成 Phase Plan v2.0 的每个实验阶段后，回填本文档中对应的 D1–D7 项结果。特别需要回填：

1. P0 完成后：D1 (Δ_oracle 值), D2 (IQ 几何结论), D4 (CI), D5 (聚集性)
2. E2/E3 完成后：D3 (leave-one-out 门控结果)
3. E4/E5 完成后：D7 (诊断结论)
4. 如执行 P2：D6 (受控实验结论)

回填格式：

```text
### D1 · 状态更新 YYYY-MM-DD

**实验结果**：[具体数值]
**判定**：条件 A / B / C
**建议的论文调整**：[具体一句话]
```

---

## 给 Claude/DeepSeek Review 的提醒

每次 Review Mode 时，对照本文件逐条检查：

1. 自上次 Review 以来，哪些实验已完成？
2. 实验结果触发了哪个条件分支（A/B/C）？
3. Skeleton 中受影响段落是否已按本文件指示更新？
4. 是否有新的实验发现产生了本文件未覆盖的依赖项？
