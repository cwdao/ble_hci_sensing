# η-only 质量指标消融：移除峰度 ρ，统一使用能量比 η — 实现计划

> **来源**：`position_sweep_observation_report` §4.3.5–4.3.6（人体 ρ 剧降、η 相对稳健）；`modal_quality_gating_report`（η-only 模态选择命中率反超 η·ρ）  
> **目标报告**：`docs/reports/eta_only_ablation_report.md`  
> **日期**：2026-08-05  
> **验证状态**：待实现

---

## 1. 动机与背景

### 1.1 问题

当前 BreatheCS 论文的核心方法使用 η·ρ（能量比 × 峰度）作为 per-tone 质量权重（`eq:eta_rho_weight`）。但两条独立证据链同时指向 ρ 可能存在问题：

**证据 A（跨域尺度崩溃）**：position_sweep 图 E3 显示，金属板 ρ 范围 4–315，人体 ρ 范围仅 2–21——差异 1–2 个数量级。η 相对稳健（金属板 → 人体：100 cm remote η 0.807→0.802，仅 −0.7%）。

**证据 B（模态选择反超）**：`modal_quality_gating_report` 的 H5 已被推翻——η-only 模态选择命中率（HKH 63.6%、CS 33.4%）高于 η·ρ（HKH 58.8%、CS 31.1%）。在模态级，ρ 不仅未增加信息，反而引入了噪声。

### 1.2 论文上下文

论文 `paper_draft_skeleton.md` 的 §6.3（BPM Accuracy）、§6.4（Waveform Recovery）和 §6.5（Ablation Experiments）目前全部基于 η·ρ。本实验直接回答：**如果切换到 η-only，论文的核心结果和消融结论是否会改变？**

### 1.3 本 plan 定位

**论文消融实验**。测试单一变量：BreatheCS 及其消融变体的质量指标从 η·ρ 切换到 η-only。不涉及论文方法集之外的方案。

---

## 2. 物理与变量

### 2.1 η 与 ρ 的物理角色

| 指标 | 物理含义 | 金属板行为 | 人体行为 |
|------|----------|------------|----------|
| **η**（能量比） | 呼吸频段能量占总频段（>0.05 Hz）的比例 | 0.5–0.95 | 0.5–0.86（范围接近） |
| **ρ**（峰突出度） | 呼吸峰相对于带内本底的突出程度 | 4–315（极宽） | 2–21（压缩 ~10×） |
| **η·ρ**（乘积） | 综合质量：既要呼吸带能量，又要尖锐单峰 | 由 ρ 主导动态范围 | η 和 ρ 的贡献量级失衡 |

**物理直觉**：金属板近正弦机械运动 → 极尖锐谱峰（ρ 大）。人体自然呼吸含速率漂移、谐波 → 能量仍集中在呼吸频段（η 不崩），但峰不再尖锐（ρ 小）。η·ρ 乘积在人体上可能过度惩罚"宽带呼吸能量"信道——这些信道的 BPM 估计仍然正确，只是峰不够尖。

---

## 3. 算法步骤

### 3.1 变更范围

```
现有: quality = η × clip(ρ, 0, +∞)    (论文 eq:eta_rho_weight)
改为: quality = η
```

本实验**不引入新算法**。仅切换配置参数：

| 模块 | 受影响方法 | 变更方式 |
|------|-----------|----------|
| `systematic_fusion.py` | BreatheCS 谱分支（B1 Vote→Equal） | `VotingConfig(voting_strategy="eta_weighted")` |
| `b3_pipeline.py` | BreatheCS 统一管线（B3 Simplified） | `B3VariantConfig(use_eta_rho_weights=False)` |
| `coherent_mrc.py` | BreatheCS-Wave（B2-D，分支对照） | `WeightMode` 新增 `"eta_only"` 或传 `rho=None` |

### 3.2 论文方法清单（仅论文涉及的方案）

本实验**严格限定**为论文中已出现的方法。以下方案**不在论文中，本轮不跑**：

| 不跑的方法 | 原因 |
|------------|------|
| B0 Single Remote, B1 Uniform Remote, Modal top2 | 不在论文 leaderboard 或消融表中 |
| T0-V2, T0-V3 作为独立方法 | 论文中仅作为 B1 的内部 Voting 步骤，不作为独立方法展示 |
| G4, G4-B1-v2（门控系列） | 不在论文中 |
| B3 Vote→Top2 | 不在论文中 |
| Fan-ηρ-linear, Fan-ηρ-equal | 论文使用的 ClessBreath 是 η-only（Fan-η-linear, Fan-η-equal） |
| Z1（含 VMD） | 论文使用 Z1-no-VMD（Pos-Free PCA） |

### 3.3 方法变体清单

#### 需要 η-only 变体的方法（论文核心，当前使用 η·ρ）

| 论文名称 | 内部 key | 当前权重 | η-only key | 域 |
|----------|----------|----------|-------------|-----|
| **BreatheCS**（谱 BPM） | `b1_vote_modal_equal` | η·ρ | `b1_vote_modal_equal_eta` | CS + HKH |
| **BreatheCS**（统一管线 BPM+波形） | `b3_simplified` | η·ρ | `b3_simplified_eta` | HKH |
| **BreatheCS-Wave**（分支对照） | `b2_d` | η·ρ | `b2_d_eta` | CS + HKH |
| Channel-only 消融 | `b1_channel_only`（Voting η·ρ, modal=best） | η·ρ | `b1_channel_only_eta` | HKH |
| Remote-only 消融 | `b1_remote_only`（B1 限于 Remote） | η·ρ | `b1_remote_only_eta` | HKH |
| Local-only 消融 | `b1_local_only` | η·ρ | `b1_local_only_eta` | HKH |
| Phase-only 消融 | `b1_phase_only` | η·ρ | `b1_phase_only_eta` | HKH |

> **CS 域消融变体**：Channel-only、Remote-only、Local-only、Phase-only 在 CS 域也跑，以观察 ρ 的跨域行为差异。

#### 不受影响的方法（已是 η-only 或无质量权重，作为稳定参照）

| 论文名称 | 内部 key | 权重 | 域 | 说明 |
|----------|----------|------|-----|------|
| **Pos-Free (PCA)** | `z1_no_vmd` | 无（PCA 降维） | CS + HKH | 外部 baseline |
| **WiFi-Sleep (MRC-PCA)** | `mrc_pca_eta_equal` | √η | CS + HKH | 外部 baseline |
| **WiFi-Sleep (√η)** | `mrc_pca_eta_sqrt` | √η | HKH | 外部 baseline |
| **PCA sign only** | `pca_sign_only` | 无 | HKH | 外部 baseline |
| **ClessBreath (η-linear)** | `fan_linear` | η | CS + HKH | 外部 baseline |
| **ClessBreath (η-equal)** | `fan_equal` | η | CS + HKH | 外部 baseline |
| No-fusion 消融 | `no_fusion`（max-η per modal → best modal） | η（max-η 选择） | HKH | 消融基线 |
| Modal-only 消融 | `modal_only`（max-η channel → 3-modal equal） | η（max-η 信道） | HKH | 消融基线 |

> **注意**：不受影响的方法虽然质量指标不变，但应在**同一次 benchmark 中重跑**，确保 η-only vs η·ρ 的 Δ 不因跨脚本/跨时期的微小实现差异而被污染。

### 3.4 实验流程图

```
CS 三场景 (cs_091339/095806/102621)    HKH 12 场景 (3 Room × 4 Subject)
        │                                        │
        ▼                                        ▼
  预处理（不变）                             预处理（不变）
  median → HP → BP                          median → HP → BP
  20s / 1s sliding window                   20s / 1s sliding window
        │                                        │
        ▼                                        ▼
  ╔═══════════════════════════════════════════════════════╗
  ║  论文方法集 × 2 变体：                                ║
  ║  (a) quality = η·ρ  (现有，论文 baseline)             ║
  ║  (b) quality = η    (本次消融)                       ║
  ║                                                      ║
  ║  受影响（7 对）：BreatheCS, BreatheCS-Wave,           ║
  ║    Channel-only, Remote/Local/Phase-only,             ║
  ║    BreatheCS 统一管线 (HKH only)                      ║
  ║  不受影响（~8 个）：Pos-Free, WiFi-Sleep ×2,          ║
  ║    PCA sign only, ClessBreath ×2, No-fusion,          ║
  ║    Modal-only                                         ║
  ╚═══════════════════════════════════════════════════════╝
        │                                        │
        ▼                                        ▼
  跨域汇总                                   跨域汇总
  (a) vs (b) mean BPM err%                   (a) vs (b) mean BPM err
  (a) vs (b) waveform RMSE (HKH only)        (a) vs (b) waveform RMSE
        │                                        │
        └──────────────┬─────────────────────────┘
                       ▼
              论文核心问题：
              · BreatheCS 谱 BPM 在 η-only 下是否退化？退化多少？
              · 消融结论（Table 8-A/8-B）是否改变？
              · 外部 baseline 的相对排序是否稳定？
              · 论文是否应切换到 η-only 作为默认配置？
```

---

## 4. Baseline 对比

### 4.1 论文现有结果（全部基于 η·ρ，作为本次 baseline）

#### HKH 域（12 场景，论文 Table 6.3-A / 6.4）

| 论文名称 | BPM abs err ↓ | RMSE | 来源 |
|----------|--------------:|------|------|
| **BreatheCS** ★ | **0.405** | **0.951** | `paper_draft_skeleton.md` §6.3 |
| Pos-Free (PCA) | 0.435 | 1.070 | 同上 |
| WiFi-Sleep (MRC-PCA) | 0.505 | 1.063 | 同上 |
| BreatheCS-Wave（对照） | 0.682 | 0.950 | 同上 |
| WiFi-Sleep (√η) | 1.023 | 1.054 | 同上 |
| PCA sign only | 1.317 | 1.085 | 同上 |
| ClessBreath (η-linear) | 1.386 | 1.025 | 同上 |
| ClessBreath (η-equal) | 1.486 | 1.046 | 同上 |

#### HKH 域（消融 Table 8-A / 8-B）

| 消融 | Spec BPM | Wave BPM | Wave RMSE | 来源 |
|------|---------:|---------:|----------:|------|
| No fusion | 1.640 | 1.192 | 1.007 | §6.5 |
| Channel only | **0.381** | 1.003 | 0.962 | §6.5 |
| Modal only | 0.655 | 1.025 | 0.986 | §6.5 |
| BreatheCS ★ | 0.405 | 0.744 | 0.951 | §6.5 |
| Remote only | 0.376 | 0.399 | 0.931 | §6.5 |
| Local only | 0.378 | 0.439 | 0.947 | §6.5 |
| Phase only | 2.191 | 2.395 | 1.109 | §6.5 |

#### CS 域（3 场景，跨域 mean BPM err%）

CS 域在论文中主要用于 §4 观测模型验证；BreatheCS 的 CS 域结果用于补充论证。现有跨域 B1 = **8.45%**（`methods/README.md`）。

### 4.2 预期相对关系

| 对比 | 域 | 预期 | 理由 |
|------|-----|------|------|
| BreatheCS-η vs BreatheCS (η·ρ) | HKH | 持平或略优 | ρ 动态范围压缩 → η·ρ ≈ c·η，乘积不增加信息 |
| BreatheCS-η vs BreatheCS (η·ρ) | CS | 略差（+0.5–1.5 pp） | ρ 在金属板尖锐谱峰场景有 discrimination 价值 |
| Channel-only-η vs η·ρ | HKH | 接近 | Voting 的信息保留优势不依赖 ρ |
| Remote-only-η vs η·ρ | HKH | 接近 | Remote 幅值本身峰已较尖，ρ 贡献有限 |
| Phase-only-η vs η·ρ | HKH | Phase-only-η 可能更差 | Phase 本身 η 低 + 无 ρ 惩罚宽峰 → 噪声 tone 权重提高 |
| B2-D-η vs B2-D (η·ρ) | HKH | 接近 | B2-D 主增益来自 Hilbert 相位对齐，ref tone 选择对 ρ 不敏感 |
| 外部 baseline 排序 | 两域 | 不变 | 外部 baseline 质量指标未变，仅因 benchmark 自洽性可能有微小波动 |

> **核心预期**：η-only 在人体数据（HKH）上不应显著退化；如果退化 >0.03 breaths/min，说明 ρ 在人体上的贡献被低估。在金属板（CS）上预期有轻度退化，但三模态融合应比单模态 Voting（T0-V2 vs T0-V3 的 +1.76 pp 差距）更能缓冲。

---

---

## 5. Phase η-BPM Gate：能量比优越性 + 幅相假峰互验证

### 5.1 动机

论文 §5.4 和 §7.2 已提出「Phase 通过置信度门控有条件参与」的设计意图，但 §5.6（具体门控机制）尚未撰写，对应实验也未执行。本实验填补这个空白。

旧门控方案（G4 系列）的问题：需运行多个独立方法做 consensus，分歧时硬编码 fallback 到 Single Remote，机制复杂且违反物理对称性。

新方案利用两个来自 position sweep 实验的物理洞察：

**洞察 1（η 优越性）**：如果 Phase 的呼吸能量比确实高于两端幅值，说明 Phase 是当前窗口质量最高的模态——有资格参与融合。但仅靠「Phase η > 阈值」不够——如果 Remote 恰好处在菲涅尔盲点（η_remote 极低），Phase 可能被「衬托」出虚假优势。

**洞察 2（幅相假峰互验证）**：位置扫描 Fig A3 表明，幅值和相位**不会同时出现明显的假峰/双峰**。但假峰能量落入呼吸频段会抬高 η → 单靠 η 无法区分「真高质量」和「假峰伪装」。不过假峰会导致 Phase BPM 偏离真值 → 若 Phase BPM 与幅值共识一致，则 Phase 大概率是真实呼吸成分而非假峰。

因此 gate 需**两层联合判断**：η 优越性 + BPM 互验证。

### 5.2 门控逻辑

```
每窗预处理（已由 Part 1 计算）：
  η_r, η_l, η_p           ← 各模态逐信道 η 中位数
  S_r(f), S_l(f), S_p(f)  ← 各模态 η-only 加权融合谱
  BPM_amp = argmax( (S_r + S_l) / 2 )   ← 幅值共识 BPM
  BPM_phase = argmax( S_p )             ← Phase BPM

Gate 决策:
  η_ok  = (η_p > η_r) AND (η_p > η_l)
  bpm_ok = |BPM_phase - BPM_amp| < 1.5

  if η_ok AND bpm_ok:
      融合模态 = [Remote, Local, Phase]   ← 3-modal equal
  else:
      融合模态 = [Remote, Local]          ← R+L dual-modal
```

**δ = 1.5 BPM** 的理由：呼吸频段 6–21 BPM，20s 窗 FFT bin 宽 = 3 BPM。1.5 BPM ≈ 半 bin——若 Phase BPM 与幅值共识差超过半个 bin，大概率是不同峰（即 Phase 的峰是假峰）。


### 5.3 门控变体消融

为分别量化两层条件各自的贡献：

| 变体 | 条件 (a): η 优越性 | 条件 (b): BPM 一致性 | 要回答的问题 |
|------|--------------------|-----------------------|-------------|
| **G0** (下界) | — | — | R+L 双模态 baseline |
| **G1** (η-relaxed) | η_p > **median**(η_r, η_l) | — | 宽松阈值是否因幅值盲点误纳入 Phase？ |
| **G2** (η-strict) | η_p > η_r **AND** η_p > η_l | — | 严格 η 优越性单独够吗？ |
| **G3** (η+BPM) | η_p > η_r AND η_p > η_l | ✅ | BPM 互验证是否额外排除了假峰窗？ |
| **G4** (上界) | — | — | 三模态 equal（Phase 始终参与） |

### 5.4 方法变体

| 方法 key | 描述 | Gate | 域 |
|----------|------|------|-----|
| `b1_eta_only_rl` | R+L only（无 Phase） | G0 | CS + HKH |
| `b1_eta_gate_g1` | η_p > median(η_r, η_l) → Phase | G1 | CS + HKH |
| `b1_eta_gate_g2` | η_p > η_r AND η_p > η_l → Phase | G2 | CS + HKH |
| `b1_eta_gate_g3` | η 优越 + BPM 一致 → Phase | G3 | CS + HKH |
| `b1_eta_3modal` | 三模态 equal（无 gate） | G4 | CS + HKH |

所有变体均使用 η-only 权重（Part 1 的结果应用于信道级 Voting）。

### 5.5 预期

| 对比 | 域 | 预期 | 理由 |
|------|-----|------|------|
| G1 vs G0 (R+L) | HKH | G1 可能更差 | 宽松阈值在幅值盲点窗口易误触发 |
| G2 vs G0 (R+L) | HKH | G2 ≈ R+L（略优或持平） | 严格条件排除盲点误触发，但假峰 η 抬高仍可漏过 |
| G3 vs G0 (R+L) | HKH | G3 ≥ R+L（最优） | BPM 一致性补上假峰防护 |
| G3 vs G4 (3-modal) | HKH | G3 优于 G4 | 排除 Phase 噪声窗和假峰窗 |
| G3 gate open ratio | CS vs HKH | CS >> HKH | 金属板 Phase 天然好 → 常开 ≈ G4；人体 → 选择性开放 |
| G3 gate-open 窗 BPM error | HKH | Gate-open 窗 error 应低 | 验证 gate 正确识别了 Phase 可靠的窗口 |

### 5.6 实现要点

```python
def phase_gate_decision(
    eta_r: float, eta_l: float, eta_p: float,
    bpm_amp: float, bpm_phase: float,
    gate_level: str = "G3",
) -> list:
    """Return modals to include in fusion."""
    if gate_level == "G0":
        return ["remote_amplitudes", "local_amplitudes"]
    if gate_level == "G4":
        return ["remote_amplitudes", "local_amplitudes", "phases"]

    if gate_level == "G1":
        if eta_p > np.median([eta_r, eta_l]):
            return ["remote_amplitudes", "local_amplitudes", "phases"]
        return ["remote_amplitudes", "local_amplitudes"]

    # G2 & G3: strict η superiority
    eta_ok = (eta_p > eta_r) and (eta_p > eta_l)
    if gate_level == "G2":
        return (["remote_amplitudes", "local_amplitudes", "phases"]
                if eta_ok else ["remote_amplitudes", "local_amplitudes"])

    # G3: + BPM mutual verification (δ = 1.5 BPM)
    bpm_ok = abs(bpm_phase - bpm_amp) < 1.5
    if eta_ok and bpm_ok:
        return ["remote_amplitudes", "local_amplitudes", "phases"]
    return ["remote_amplitudes", "local_amplitudes"]
```

**诊断输出**（gate 变体额外记录，用于论文 §5.6 分析）：
- Per-window gate open/close flag + 拒绝原因（η 不够 / BPM 不一致）
- Per-window η_r, η_l, η_p 值
- Gate-open 窗口的 Phase BPM error（vs GT）——验证 gate 是否有效识别 Phase 可靠窗口

---
## 6. 评估设计

### 6.1 场景

| 域 | 场景 | 用途 |
|-----|------|------|
| CS | cs_091339 / cs_095806 / cs_102621 | 金属板跨域：η-only 是否在机械运动下退化 |
| HKH | 3 Room × 4 Subject = 12 场景 | 真人主评估：论文 §6.3/§6.4/§6.5 的核心域 |

### 6.2 指标

| 指标 | 域 | 对应论文 |
|------|-----|----------|
| BPM abs err（mean ± std） | HKH | §6.3 Table 6.3-A, §6.5 Table 8-A/8-B |
| RMSE（mean ± std） | HKH | §6.4 Table 6.4, §6.5 Table 8-A/8-B |
| BPM err%（mean ± std） | CS | 补充论证 |
| η-only − η·ρ 配对 Δ | 两域 | 核心消融数字 |

### 6.3 成功标准

#### Part 1: η-only 消融

| 判定 | 条件 |
|------|------|
| **论文切换到 η-only** | HKH: BreatheCS-η BPM ≤ BreatheCS (η·ρ) + 0.02 **且** 消融排序不变 |
| **论文保留 η·ρ** | HKH: BreatheCS-η BPM > BreatheCS (η·ρ) + 0.03 **或** 消融结论发生翻转 |
| **分域策略** | CS 保留 η·ρ（若 CS 退化 >1.0 pp）、HKH 切换 η-only（若 HKH 改善） |
| **不确定** | Δ 在 ±0.02 以内 → 论文按简洁性原则推荐 η-only，Discussion 中讨论两可性 |

#### Part 2: Phase η-BPM Gate

| 判定 | 条件 |
|------|------|
| **Gate 有效（G3 推荐）** | G3 BPM < G4 (3-modal) **且** G3 BPM ≤ G0 (R+L) + 0.01 → G3 是唯一优于两端点的方法 |
| **η-strict 已足够（G2 推荐）** | G2 ≈ G3（Δ < 0.01）→ BPM 一致性条件无额外增益 |
| **Gate 中性** | G3 BPM ≈ G0 BPM ± 0.01（gate 退化为 R+L，Phase 从未被纳入或纳入后无差异） |
| **Gate 有害** | G3 BPM > G0 BPM + 0.02 → gate 条件不当，纳入了有害 Phase 窗 |
| **论文动作** | Gate 有效（尤其 G3）→ 写入 §5.6；BreatheCS 默认升级为 η-only + G3 gate |

#### 综合判定（两实验合并后的论文建议）

| 场景 | η-only | Phase gate | 论文最终建议 |
|------|--------|------------|-------------|
| 最佳 | ✅ 持平或略优 | ✅ Gate 有效 | BreatheCS = η-only weights + η-gated Phase |
| 次佳 | ✅ 持平或略优 | ⚠️ Gate 中性 | BreatheCS = η-only weights + R+L（Phase 保留但不默认参与） |
| 保守 | ⚠️ 不确定 | ✅ Gate 有效 | BreatheCS = η·ρ weights（不改）+ η-gated Phase |
| 保留 | ❌ 退化 | ⚠️/❌ | 保持现状（η·ρ + 三模态 equal） |

---

## 7. 实现要点

### 7.1 建议文件

| 类型 | 路径 |
|------|------|
| 实验脚本 | `notebooks/scripts/chFusion_eta_only_ablation.py` |
| 复用模块 | `src/ble_analysis/systematic_fusion.py`（`VotingConfig(voting_strategy="eta_weighted")`） |
| 复用模块 | `src/ble_analysis/b3_pipeline.py`（`B3VariantConfig(use_eta_rho_weights=False)`） |
| 复用模块 | `src/ble_analysis/coherent_mrc.py`（需支持 η-only 权重） |
| 复用模块 | `src/ble_analysis/wifi_mrc.py`（不变，但重跑以保持 benchmark 自洽） |
| 复用模块 | `src/ble_analysis/pca_vmd.py`（不变，重跑 Z1-no-VMD） |
| 场景配置 | 沿用现有 `config/scenarios/cs_*.json` |

### 7.2 实现策略

不复制代码，仅切换配置参数：

```python
# Part 1 — BreatheCS 谱分支 η-only:
vcfg_eta = VotingConfig(voting_strategy="eta_weighted")
# BreatheCS 统一管线 η-only:
variant_eta = B3VariantConfig(use_eta_rho_weights=False)
# B2-D η-only: 将传入 coherent_mrc 的 rho 替换为 None 或 ones

# Part 2 — Phase η-Gate（在模态融合前插入门控判断）:
def phase_eta_gate_decision(eta_r, eta_l, eta_p, threshold_mode="relative"):
    theta = np.median([eta_r, eta_l]) if threshold_mode == "relative" else 0.70
    if eta_p > theta:
        return ["remote_amplitudes", "local_amplitudes", "phases"]
    return ["remote_amplitudes", "local_amplitudes"]
```

### 7.3 脚本结构建议

```text
notebooks/scripts/chFusion_eta_only_ablation.py

├── Part 1: η-only 消融
│   ├── Section 1: CS 三场景 benchmark
│   │   ├── 1a. 外部 baseline 重跑: Pos-Free, WiFi-Sleep, ClessBreath ×2
│   │   ├── 1b. BreatheCS 谱分支: B1 η·ρ vs η-only
│   │   └── 1c. BreatheCS-Wave: B2-D η·ρ vs η-only
│   │
│   ├── Section 2: HKH 12 场景 benchmark
│   │   ├── 2a. 外部 baseline 重跑: 同 CS + WiFi-Sleep(√η) + PCA sign only
│   │   ├── 2b. BreatheCS 谱分支 + 统一管线: B1/B3 η·ρ vs η-only
│   │   ├── 2c. BreatheCS-Wave: B2-D η·ρ vs η-only
│   │   └── 2d. 消融变体: Channel-only, Remote/Local/Phase-only η·ρ vs η-only
│   │       （No-fusion 和 Modal-only 已是 η-only，仅重跑验证）
│   │
│   └── Section 3: Part 1 汇总
│       ├── 3a. HKH leaderboard（η·ρ vs η-only 双列）
│       ├── 3b. HKH 消融表（η·ρ vs η-only 双列）
│       ├── 3c. CS 跨域对比
│       └── 3d. 配对 Δ 汇总
│
├── Part 2: Phase η-Gate（在 η-only 基础上）
│   ├── Section 4: Gate 变体运行
│   │   ├── 4a. R+L only（下界）
│   │   ├── 4b. η-gate relative（Phase η > Remote median η）
│   │   └── 4c. η-gate absolute（Phase η > 0.70）
│   │
│   └── Section 5: Part 2 汇总
│       ├── 5a. Gate vs R+L vs 3-modal（HKH + CS）
│       ├── 5b. Per-window gate open/close ratio（CS vs HKH）
│       └── 5c. Threshold sensitivity（如需要）
│
└── Section 6: 综合诊断图
    ├── 6a. HKH BPM leaderboard（η·ρ / η-only / η-gate 三色，论文 Fig 6a 格式）
    ├── 6b. HKH 消融对比（论文 Fig 8 格式，三色）
    └── 6c. ρ 分布对比（CS vs HKH）
```

### 7.4 不做的事

- 不跑论文方法集之外的任何方案（G4, Modal top2, B0, Uniform, T0 standalone, Fan-ηρ, Z1-with-VMD 等）
- 不引入 η·soft(ρ) / η·rank(ρ) 等中间变体
- 不引入需要多候选 consensus 的复杂门控
- 不修改滤波链、滑窗参数、寻峰逻辑

---

## 8. 预期产出

### 8.1 数值结果

| 产出 | 路径 | 对应论文 |
|------|------|----------|
| HKH leaderboard（η·ρ + η-only + gate） | `outputs/reports/eta_only_ablation_hkh_leaderboard.json` | §6.3 Table 6.3-A |
| HKH 消融表（η·ρ + η-only） | `outputs/reports/eta_only_ablation_hkh_ablation.json` | §6.5 Table 8-A/8-B |
| Phase gate 结果（gate vs R+L vs 3-modal） | `outputs/reports/eta_only_ablation_phase_gate.json` | §5.6（待写） |
| CS 跨域对比 | `outputs/reports/eta_only_ablation_cs_leaderboard.json` | 补充 |
| 配对 Δ 表 | `outputs/reports/eta_only_ablation_delta.csv` | 核心消融数字 |

### 8.2 图表

| 图 ID | 内容 | 路径 |
|-------|------|------|
| G1 | HKH BPM leaderboard（η·ρ / η-only / η-gate 三色） | `outputs/figures/eta_only_ablation_figG1_hkh_leaderboard.png` |
| G2 | HKH 消融对比（论文 Fig 8 格式，三色并列） | `outputs/figures/eta_only_ablation_figG2_hkh_ablation.png` |
| G3 | CS 跨域 BPM（η·ρ vs η-only） | `outputs/figures/eta_only_ablation_figG3_cs_leaderboard.png` |
| G4 | ρ 分布对比（CS vs HKH） | `outputs/figures/eta_only_ablation_figG4_rho_distribution.png` |
| G5 | Phase gate open/close ratio（CS vs HKH per-window） | `outputs/figures/eta_only_ablation_figG5_gate_behavior.png` |

### 8.3 报告

| 产出 | 路径 |
|------|------|
| 消融验证报告 | `docs/reports/eta_only_ablation_report.md` |

---

## 9. 风险与保留问题

### 9.1 Part 1 风险（η-only 消融）

- **Phase-only 在 η-only 下可能进一步恶化**：Phase 本身 ρ 已很低，去掉 ρ 后低-η 噪声 tone 权重提高，可能导致 Phase-only BPM 从 2.191 进一步退化
- **Channel-only 可能在 η-only 下反超 BreatheCS**：当前 Channel-only（0.381）已略优于 BreatheCS（0.405）。若 η-only 扩大差距，需在论文中解释

### 9.2 Part 2 风险（Phase η-Gate）

- **Gate 阈值敏感**：若 R+L（0.372）和三模态（0.405）之间的差距仅有 0.033 BPM，gate 的改善空间有限。门控价值可能更多体现在 CS 域（Phase 质量高时自动纳入）而非 HKH 域
- **Gate open ratio 在 CS 上可能接近 100%**：若 CS 金属板上 Phase η 始终高于阈值，gate 退化为 3-modal equal，无实际选择行为——但这也正是期望的跨域自适应行为
- **相对阈值可能不稳定**：若 Remote η 在某个窗口中异常低（如盲点），相对阈值过低，可能错误纳入 Phase。需检查 gate open 窗口的 Phase 实际质量

### 9.3 保留问题

| ID | 问题 |
|----|------|
| Q1 | 若 η-only 在 HKH 上持平或略优，论文 `eq:eta_rho_weight` 是否改为 `w = η`？ |
| Q2 | 若 CS 退化 >1.0 pp 但 HKH 改善，论文是否接受分域结论？ |
| Q3 | Phase gate 若有效，论文 §5.6 是否直接将 η-gate 作为默认配置写入？ |
| Q4 | 是否需要 η·log(1+ρ) 等中间方案？本 plan 暂不纳入，视 Part 1 结果决定 |

---

## 10. 验证状态

状态：**待实现**

---

## 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/eta_only_ablation_plan.md`

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/eta_only_ablation_plan.md`（回填 §10 验证状态）
- `docs/reports/eta_only_ablation_report.md`
- `outputs/reports/eta_only_ablation_*.json` / `*.csv`
- `outputs/figures/eta_only_ablation_figG*.png`
- 关键脚本路径
- git commit message 或 git diff 摘要
