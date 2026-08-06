# 门控拆解 + 波形 ρ 保留 + 呼吸频带诊断 — 实现计划

> **来源**：`eta_only_ablation_report`（G3 中性、η gate 跨域失败）+ `phase_unique_role_adaptive_fusion_report`（P0a oracle Δ 灰色地带）  
> **目标报告**：`docs/reports/gate_decomposition_band_diagnostic_report.md`  
> **日期**：2026-08-06  
> **验证状态**：待实现

---

## 1. 动机与背景

### 1.1 问题

`eta_only_ablation` 的两项实验结果明确了当前瓶颈：

1. **G3 门控（η 优越 + BPM 互验证）在 HKH 上是 no-op**：Phase 仅在 1.3% 窗口被纳入，G3 BPM（0.371）≡ G0 R+L（0.371）。但 G3 的失败可能来自 η 条件过严、BPM 条件过严、或两者叠加——需要拆解归因。
2. **CS 上 G3 反而关了有用的 Phase**：CS 三模态常开（G4-upper）BPM err 10.72% 远优于 G3（14.61%），η 门控在金属板场景误杀了 Phase 的有效窗口——但放宽 η 条件能否修复？
3. **η 作为单模态选择器命中率仅 63.6%（HKH）**：不清楚 η 主要混淆了谁（Remote↔Local 低成本互换？还是误选 Phase 导致高代价错误？）。
4. **波形分支 η-only 退化**：RMSE 从 0.951 升到 0.994（Δ=+0.043），ρ 在波形路径可能仍有价值。

### 1.2 本 plan 定位

**收尾诊断**——不做新算法，只做三个独立机制的归因实验 + 一项频带参数诊断。目标：确认当前路线的理论天花板，判断是否需要继续投入门控/选模态优化，还是就此结题。

| 项目 | 说明 |
|------|------|
| 问题 | 门控的两个条件各自贡献多少？η 选错的代价有多大？呼吸频带是否限制了 η 的分辨力？ |
| 相关报告 | `eta_only_ablation_report`、`phase_unique_role_adaptive_fusion_report`、`modal_quality_gating_report` |
| 本 plan 定位 | 诊断性收尾——拆解门控条件、量化 η 混淆矩阵、测试频带参数敏感性 |

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 主模态，HKH 上 89.5% 窗口最优 |
| `local_amplitudes` | ✅ | 辅助模态，与 Remote 物理对等 |
| `phases` | ✅（条件性） | 6.1% 窗口最优（HKH），但单独 BPM err 2.09；需门控 |
| `amplitudes`（总幅值） | ❌ | 无独立物理意义 |

### 2.2 符号约定

| 符号 | 含义 |
|------|------|
| η_r, η_l, η_p | 各模态逐信道 η 中位数（per-window） |
| BPM_r, BPM_l, BPM_p | 各模态 Voting 谱 argmax BPM |
| δ_bpm | BPM 共识阈值 |

---

## 3. 算法步骤

### 3.0 流程图

```
Raw BLE CS Frames (72 tone × 3 variables)
  │
  ├─► Filter Chain (不变):
  │     median (w=3) → highpass (0.05 Hz) → bandpass (0.1–0.35 Hz)
  │     [Part 4 诊断: bandpass highcut 扫描 0.35/0.40/0.50/0.60 Hz]
  │
  ├─► Sliding Window: 20 s / 1 s step (不变)
  │
  ▼
Per-tone FFT → η, ρ 计算
  │
  ├─► Part 3 诊断: Per-window η-selected vs oracle-best modal 混淆矩阵
  │
  ▼
逐模态 Voting (η-only 权重，同 eta_only_ablation 结论)
  │
  ├─► S_r(f), S_l(f), S_p(f)  ← 各模态融合谱
  ├─► BPM_r, BPM_l, BPM_p    ← argmax 寻峰
  ├─► η_r, η_l, η_p          ← 逐信道 η 中位数
  │
  ▼
═══════════════════════════════════════════════════════════
  Part 1: 门控拆解
═══════════════════════════════════════════════════════════
  │
  ├─► Gate-A (η-only relaxed):
  │     if η_p > min(η_r, η_l):  → R+L+P 3-modal equal
  │     else:                     → R+L only
  │
  ├─► Gate-B (BPM consensus only, δ ∈ {1.5, 3.0}):
  │     if max(|BPM_i - BPM_j|) < δ:  → R+L+P 3-modal equal
  │     else:                          → R+L only
  │     (不检查 η，仅 BPM 分支生效)
  │
  ▼
═══════════════════════════════════════════════════════════
  Part 2: 波形分支 ρ 保留
═══════════════════════════════════════════════════════════
  │
  ├─► BPM 分支: η-only 权重 (Part 1 + 既成结论)
  ├─► 波形分支: η·ρ 权重 (保留 ρ)
  │     前端共享 Voting 谱，仅额外计算 per-tone ρ
  │
  ▼
═══════════════════════════════════════════════════════════
  Part 4: 呼吸频带扫描 (0.1–0.35/0.40/0.50/0.60 Hz)
═══════════════════════════════════════════════════════════
  │
  ├─► 仅跑 BreatheCS 主方案 (η-only, 3-modal equal)
  ├─► 扫描 bandpass 高截止: 0.35 / 0.40 / 0.50 / 0.60 Hz
  ├─► BPM 搜索范围保持 6–21 BPM
  ├─► 若有效 → 后续全量 benchmark；若无效 → 结题
  │
  ▼
评估: BPM abs err (HKH) / BPM err% (CS) + η top-1 hit rate
```

### 3.1 Part 1: 门控拆解 — Gate-A（η-only relaxed）

**动机**：G3 的 η 条件（η_p > η_r AND η_p > η_l）过严——即使在 CS 上 Phase 质量不错（14.4% 窗口 Phase 最优），Phase η 也未必同时高于两端幅值。将条件放松到"Phase 不是最差的"。

**逻辑**：

```
Gate-A 决策:
  if η_p > min(η_r, η_l):
      融合模态 = [Remote, Local, Phase]   ← 3-modal equal (η-only 信道权重)
  else:
      融合模态 = [Remote, Local]          ← R+L only
```

**与 G1/G2 的关系**：

| Gate | 条件 | 严格度 |
|------|------|--------|
| G1 (旧) | η_p > median(η_r, η_l) | 中等 |
| G2 (旧) | η_p > η_r AND η_p > η_l | 最严 |
| **Gate-A (新)** | **η_p > min(η_r, η_l)** | **最松** |

> 例：η_r=0.3, η_l=0.8, η_p=0.5  
> G1: 0.5 < median(0.3,0.8)=0.55 → ❌  
> Gate-A: 0.5 > min(0.3,0.8)=0.3 → ✅  
> Gate-A 允许 Phase 在仅优于一端幅值时参与。

**方法 key**：`b1_eta_gate_ga`

### 3.2 Part 1: 门控拆解 — Gate-B（BPM consensus only）

**动机**：完全去掉 η 条件，仅靠 BPM 一致性判断 Phase 是否可以融合。如果三个模态独立估计的 BPM 高度一致，说明它们看到了同一个呼吸成分——此时 Phase 大概率可靠，不管其 η 高低。

**逻辑**：

```
Gate-B 决策 (δ ∈ {1.5, 3.0}):
  bpm_range = max(BPM_r, BPM_l, BPM_p) - min(BPM_r, BPM_l, BPM_p)
  
  if bpm_range < δ:
      融合模态 = [Remote, Local, Phase]   ← 3-modal equal
  else:
      融合模态 = [Remote, Local]          ← R+L only
```

**δ 参数选择理由**：

| δ | 含义 | 预期行为 |
|---|------|----------|
| **1.5 BPM** | 半 bin（20s 窗 FFT bin = 3 BPM） | 严格——Phase 必须与幅值高度一致 |
| **3.0 BPM** | 一 bin | 宽松——允许 Phase 与幅值差一个 FFT bin |

**方法 key**：`b1_eta_gate_gb_d15`、`b1_eta_gate_gb_d30`

**仅 BPM 分支生效**：Gate-B 不改变波形分支。波形分支始终使用 R+L（当前最优），或按 Part 2 保留 η·ρ。

### 3.3 Part 2: 波形分支 ρ 保留

**动机**：`eta_only_ablation` 已显示波形 RMSE 在 η-only 下退化（η·ρ: 0.951 → η-only: 0.994）。ρ 可能对波形质量更重要——波形重建需要尖锐的相位对齐参考 tone，ρ 的峰尖锐度信息在此有独立价值。

**方案**：

```
BPM 分支: quality = η        (既成结论)
波形分支: quality = η·ρ      (保留 ρ)
```

前端 Voting 谱计算共享——波形分支仅在 bandpass 后额外计算 per-tone ρ，增量计算可忽略。

**方法 key**：
- `b2_d_two_level`（η·ρ，现有 baseline）
- `b2_d_two_level_eta`（η-only，eta_only_ablation 已跑）
- 对比两者 RMSE Δ

> **不需要新跑**——`eta_only_ablation` 已有 B2-D η·ρ vs η-only 配对数据。本轮仅需在报告中确认此结论并写入最终推荐。

### 3.4 Part 3: η 混淆矩阵诊断

**动机**：η top-1 hit rate 63.6%（HKH），但不知道 η 选错时的代价分布。如果 η 主要混淆 Remote ↔ Local（两者 BPM err 接近：0.465 vs 0.462），则选错代价很小，无需优化。如果 η 系统性误选 Phase（BPM err 2.09），则需要针对性修复。

**诊断输出**（per-window，跨 12 场景汇总）：

| oracle best | η selected | 窗口数 | 占比 | 选错代价 (Δ BPM err) |
|-------------|------------|--------|------|---------------------|
| Remote | Remote | ... | ... | 0 (正确) |
| Remote | Local | ... | ... | ≈0 (低成本) |
| Remote | Phase | ... | ... | ≈1.6 (高成本) |
| Local | Remote | ... | ... | ≈0 |
| Local | Local | ... | ... | 0 |
| Local | Phase | ... | ... | ≈1.6 |
| Phase | Remote | ... | ... | ≈1.6 |
| Phase | Local | ... | ... | ≈1.6 |
| Phase | Phase | ... | ... | 0 |

**关键判断**：
- 若高成本混淆（η→Phase 但 oracle=Remote/Local）占比 <2% → η 实际可用，63.6% 命中率够用
- 若高成本混淆 >5% → η 作为单模态选择器有系统性缺陷

> **不需要新跑**——此诊断可从既有 `modal_oracle_summary.json` 的 per-window 原始数据生成。若原始数据不含 per-window η-selected 标签，则需补跑一次轻量 oracle 遍历（不涉及新方法，仅查询已有频谱和 GT）。

### 3.5 Part 4: 呼吸频带扫描诊断

**动机**：当前呼吸频段 0.1–0.35 Hz（6–21 BPM）可能偏窄。若呼吸能量部分溢出到更高频段（如呼吸谐波、瞬时速率波动），η 会低估该信道/模态的真实呼吸信息量，导致选道/选模态错误。做一次粗粒度频带扫描，看 η 的分辨力是否对频带上界敏感。

**方案**：

```
仅改一个参数: bandpass highcut
扫描: 0.35 (baseline) / 0.40 / 0.50 / 0.60 Hz
其余不变: 滑窗 20s/1s, FFT, Voting, 寻峰逻辑
BPM 搜索范围保持 6–21 BPM（仅 η 计算频带扩展）
```

**测试范围**（极轻量——仅跑 BreatheCS 主方案）：

| 频带 | 方法 | 域 | 指标 |
|------|------|-----|------|
| 0.1–0.35 Hz (baseline) | BreatheCS（η-only, 三模态 equal） | HKH + CS | BPM err, η per-modal |
| **0.1–0.40 Hz** | 同上 | HKH + CS | 同上 |
| **0.1–0.50 Hz** | 同上 | HKH + CS | 同上 |
| **0.1–0.60 Hz** | 同上 | HKH + CS | 同上 |

> 每个频带额外输出：η top-1 hit rate（vs oracle）、per-modal η 均值、Phase η 分布。

**判断标准**：

| 结果 | 判定 | 后续动作 |
|------|------|----------|
| 某频带 BreatheCS BPM 明显优于 baseline（HKH Δ > 0.02） | 频带扩展有效 | 对该频带跑全量 benchmark |
| 所有频带 BPM 持平 baseline（Δ < 0.02） | 频带不是瓶颈 | 结题——η 分辨力受限于 20s FFT 分辨率或其他因素 |
| 某频带 BPM 明显退化 | 该频带引入噪声 | 排除该频带，关注其他 |

---

## 4. Oracle 理论极限参考

> 以下数据来自已完成实验，本 plan 不重跑。列入供执行 Agent 和 Reviewer 对照。

### 4.1 HKH 12 场景（BPM 绝对误差 breaths/min）

| 指标 | 值 | 来源 |
|------|----|------|
| **单模态 Oracle**（每窗选最优单模态） | **0.408** | `modal_oracle_summary.json` |
| Remote-only（全窗） | 0.465 | 同上 |
| Local-only（全窗） | 0.462 | 同上 |
| Phase-only（全窗） | 2.088 | 同上 |
| **R+L 实际最优** | **0.372** | `eta_only_ablation` / `phase_unique_role_adaptive_fusion` |
| R+L Oracle（每窗选 R/L 中更优者） | [待确认] | 未单独计算；近似 ≤0.372 |
| **R+L+P Oracle Δ over R+L** | **+0.028** (mean Δ) | `phase_p0_oracle_delta.json` |
| R+L+P Oracle（估算） | ≈0.344 | R+L(0.372) − Δ(0.028) |
| **BreatheCS 三模态等权（实际）** | **0.405** | `eta_only_ablation` (η-only) |
| **BreatheCS R+L（实际，推荐）** | **0.371** | `eta_only_ablation` G0 |

**每窗最优模态分布**（1730 窗）：

| 模态 | 窗口数 | 占比 |
|------|--------|------|
| Remote | 1549 | **89.5%** |
| Local | 76 | 4.4% |
| Phase | 105 | 6.1% |

**η 选择器命中率**：

| 指标 | top-1 hit rate | selected mean err | oracle mean err |
|------|---------------:|------------------:|----------------:|
| η | **63.6%** | 0.750 | 0.408 |
| η·ρ | 54.3% | 0.528 | 0.408 |
| ρ | 50.7% | 0.500 | 0.408 |
| conf | 53.1% | 0.466 | 0.408 |

> 注：selected mean err 是被该指标选中的模态的实际 BPM err；η·ρ 的 selected err（0.528）低于 η（0.750）——这是因为 η·ρ 的 ρ 因子惩罚了 Phase 的高-ρ-但低-BPM-质量窗口，恰好避免了部分高成本错误。但这也导致 η·ρ 的 top-1 hit rate 更低——它更保守，宁可错过也不选错。

### 4.2 HKH 波形 RMSE

| 方法 | RMSE η·ρ | RMSE η-only | Δ |
|------|---------:|------------:|--:|
| Wave Remote | 0.931 | 0.989 | +0.058 |
| Wave Local | 0.947 | 0.981 | +0.034 |
| Wave Phase | 1.109 | 1.124 | +0.015 |
| **Wave BreatheCS** | **0.951** | **0.994** | **+0.043** |

> 来源：`eta_only_ablation_report` §4.2。波形分支 η-only 一致退化，建议保留 η·ρ。

### 4.3 CS 金属板三场景（BPM 绝对误差，breaths/min）

| 指标 | 值 | 来源 |
|------|----|------|
| **单模态 Oracle**（每窗选最优单模态） | **0.651** | `modal_oracle_summary.json` |
| Remote-only（全窗） | 1.062 | 同上 |
| Local-only（全窗） | 1.730 | 同上 |
| Phase-only（全窗） | 1.259 | 同上 |

> CS GT BPM 范围 8.7–16.2 BPM，Oracle 0.651 BPM ≈ 4–7% err%。

**每窗最优模态分布**（437 窗）：

| 模态 | 窗口数 | 占比 |
|------|--------|------|
| Remote | 310 | **70.9%** |
| Local | 64 | 14.6% |
| Phase | 63 | 14.4% |

### 4.4 CS 跨域 BPM err%（实际方法）

| 方法 | η·ρ | η-only | 来源 |
|------|-----:|-------:|------|
| BreatheCS 三模态等权 | 10.14% | **10.72%** | `eta_only_ablation` |
| R+L only | 14.05% | 14.64% | 同上 |
| G4-upper（三模态常开） | — | 10.72% | 同上 |

> CS 上三模态显著优于 R+L（与 HKH 相反），Phase 的 14.4% 最优窗口贡献明确。

---

## 5. Baseline 对比

### 5.1 必须跑齐的方法

| 方法 key | 描述 | 域 | 说明 |
|----------|------|-----|------|
| `b1_eta_only_rl` | G0 R+L only（η-only 信道权重） | HKH + CS | 下界 baseline |
| `b1_eta_3modal` | G4-upper 三模态常开（η-only） | HKH + CS | 上界 baseline |
| `b1_eta_gate_g3` | G3 η 优越 + BPM 互验证（旧） | HKH + CS | 旧门控对照 |
| **`b1_eta_gate_ga`** | **Gate-A η-only relaxed（新）** | HKH + CS | Part 1 待测 |
| **`b1_eta_gate_gb_d15`** | **Gate-B BPM consensus δ=1.5（新）** | HKH | Part 1 待测 |
| **`b1_eta_gate_gb_d30`** | **Gate-B BPM consensus δ=3.0（新）** | HKH | Part 1 待测 |

### 5.2 波形分支对照（不新跑，引用既有数据）

| 方法 key | 描述 | BPM 权重 | 波形权重 |
|----------|------|----------|----------|
| `b2_d_two_level` | B2-D 两级 Hilbert-MRC | η·ρ | η·ρ |
| `b2_d_two_level_eta` | B2-D η-only | η | η |

### 5.3 预期相对关系

| 对比 | 域 | 预期 | 理由 |
|------|-----|------|------|
| Gate-A vs G0 (R+L) | HKH | Gate-A ≥ G0（略优或持平） | 放松 η 条件可能纳入少数有效 Phase 窗，但不会大量纳入噪声窗（Phase η 最低的窗已被排除） |
| Gate-A vs G3 (旧) | HKH | Gate-A open ratio > G3 | min 条件比 AND 条件显著更松 |
| Gate-A vs G4 (三模态) | HKH | 介于 G0 和 G4 之间 | 排除了 Phase η 最低的窗 |
| Gate-A vs G0 (R+L) | CS | Gate-A 应优于 G0 | CS 上 Phase 最优窗占 14.4%，放宽 η 条件有望纳入更多 |
| Gate-B δ=1.5 vs G0 | HKH | ≈G0 | 1.5 BPM 过于严格，Phase 很少与幅值如此一致 |
| Gate-B δ=3.0 vs G0 | HKH | 不确定 | 3.0 BPM 可能纳入部分 Phase 有效窗，但也可能纳入假峰窗 |
| 0.1–0.6 Hz vs 0.1–0.35 Hz | HKH | η hit rate 略升或不变 | 若呼吸谐波含信息量，η 分辨力提升；若纯噪声，不变 |
| 波形 η·ρ vs η-only | HKH | η·ρ 更优 | 已确认 |

---

## 6. 评估设计

### 6.1 场景

| 域 | 场景 | 用途 |
|-----|------|------|
| HKH | 12 recordings（3 Room × 4 Subject） | **主评估** |
| CS | cs_091339 / cs_095806 / cs_102621 | 跨域对照（参考） |

### 6.2 指标

| 指标 | 域 | 用途 |
|------|-----|------|
| BPM abs err（mean ± std，breaths/min） | HKH | 主指标 |
| BPM rel err %（mean ± std） | CS | 对照 |
| Gate open ratio（mean + per-recording） | HKH + CS | Gate-A / Gate-B 行为特征 |
| Gate-open 窗 Phase BPM err | HKH + CS | 验证 gate 是否挑对窗 |
| η top-1 hit rate | HKH + CS | Part 4 频带对比 |
| 混淆矩阵（η-selected vs oracle-best） | HKH | Part 3 诊断 |
| Wave RMSE（mean ± std） | HKH | Part 2 波形对照（引用既有） |

### 6.3 成功标准

| 级别 | 条件 |
|------|------|
| **突破** | Gate-A 或 Gate-B 在 HKH 上 BPM 优于 G0 且不劣于 G4；CS 上接近 G4 |
| **有效** | Gate-A 或 Gate-B 在某一域优于 G0，另一域不退化 |
| **中性** | 所有新 gate ≈ G0（与 G3 相同结局）→ 门控路线收尾 |
| **频带有效** | 某频带 BreatheCS BPM 优于 baseline（HKH Δ > 0.02）→ 对该频带补全量 benchmark |
| **频带中性** | 所有频带 BPM 持平 baseline（Δ < 0.02）→ η 分辨力瓶颈不在频带范围，结题 |

---

## 7. 实现要点

### 7.1 建议文件

| 类型 | 路径 |
|------|------|
| 实验脚本 | `notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py` |
| 复用模块 | `src/ble_analysis/voting_fusion.py`（扩展 gate 逻辑或脚本内实现） |
| 复用模块 | `src/ble_analysis/b3_pipeline.py`（`tone_weight_mode="eta"`，既成） |
| 复用模块 | `src/ble_analysis/coherent_mrc.py`（波形对照，不需改动） |
| 场景配置 | 沿用现有 `config/scenarios/cs_*.json` + `room_*.json` |

### 7.2 接口草案

```python
# Part 1: Gate-A — η-only relaxed
def gate_a_decision(
    eta_r: float, eta_l: float, eta_p: float,
) -> list[str]:
    """Phase participates if its η is not the lowest among 3 modals."""
    if eta_p > min(eta_r, eta_l):
        return ["remote_amplitudes", "local_amplitudes", "phases"]
    return ["remote_amplitudes", "local_amplitudes"]


# Part 1: Gate-B — BPM consensus only
def gate_b_decision(
    bpm_r: float, bpm_l: float, bpm_p: float,
    delta: float = 1.5,
) -> list[str]:
    """Fuse all 3 modals if BPMs agree within δ; else R+L only."""
    bpm_range = max(bpm_r, bpm_l, bpm_p) - min(bpm_r, bpm_l, bpm_p)
    if bpm_range < delta:
        return ["remote_amplitudes", "local_amplitudes", "phases"]
    return ["remote_amplitudes", "local_amplitudes"]
```

### 7.3 Part 3 诊断实现

```python
# 混淆矩阵: 对每窗记录 oracle_best 与 eta_selected
# oracle_best = argmin_{m in {R,L,P}} |BPM_m - BPM_gt|
# eta_selected = argmax_{m in {R,L,P}} eta_m
# 输出 3×3 矩阵 + per-cell 的 mean/median BPM err
```

### 7.4 Part 4 频带变更

```python
# 仅改一处: FilterParams 的 bandpass highcut
# 现有:
filter_params = FilterParams(
    bandpass_low=0.1, bandpass_high=0.35, ...
)
# 诊断变体:
filter_params_wide = FilterParams(
    bandpass_low=0.1, bandpass_high=0.6, ...
)
# BPM 搜索范围不变: f_min=0.1, f_max=0.35 (6–21 BPM)
```

### 7.5 不做的事

- 不引入新的信道融合策略（继续 η-only Voting）
- 不引入新的模态融合权重（继续 equal）
- 不修改滑窗参数、寻峰逻辑
- 不跑论文方法集之外的方法
- 不跑双参数网格搜索（δη × δbpm）
- 波形分支不新跑（引用既有 η·ρ vs η-only 配对数据即可）

---

## 8. 预期产出

### 8.1 数值结果

| 产出 | 路径 |
|------|------|
| Gate 拆解 HKH 汇总 | `outputs/reports/gate_decomposition_hkh.json` |
| Gate 拆解 CS 汇总 | `outputs/reports/gate_decomposition_cs.json` |
| η 混淆矩阵 | `outputs/reports/eta_confusion_matrix.json` |
| 频带扫描对比（0.35/0.40/0.50/0.60 Hz） | `outputs/reports/breathing_band_sweep.json` |

### 8.2 图表

| 图 ID | 内容 | 路径 |
|-------|------|------|
| F1 | Gate-A/B vs G0/G3/G4 BPM leaderboard（HKH） | `outputs/figures/gate_decomposition_figF1_hkh_bpm.png` |
| F2 | Gate-A open ratio per recording（HKH + CS） | `outputs/figures/gate_decomposition_figF2_open_ratio.png` |
| F3 | Gate-A gate-open window Phase BPM err distribution | `outputs/figures/gate_decomposition_figF3_gate_quality.png` |
| F4 | η 混淆矩阵 heatmap（HKH） | `outputs/figures/gate_decomposition_figF4_eta_confusion.png` |
| F5 | 频带扫描：BreatheCS BPM vs bandpass highcut（0.35/0.40/0.50/0.60 Hz） | `outputs/figures/gate_decomposition_figF5_band_sweep.png` |

### 8.3 报告

| 产出 | 路径 |
|------|------|
| 诊断验证报告 | `docs/reports/gate_decomposition_band_diagnostic_report.md` |

---

## 9. 风险与保留问题

### 9.1 Part 1 风险

- **Gate-A open ratio 在 HKH 上仍极低**：若 η_p > min(η_r, η_l) 仍然很少成立，说明 Phase η 系统性低于至少一端幅值——此时问题不在门控，而在 Phase 本身
- **Gate-A 在 CS 上 open ratio 可能接近 100%**：若 Phase η 很少是最低的，gate 退化为三模态常开（≈G4），但这在 CS 上反而是好的
- **Gate-B δ=3.0 纳入噪声 Phase 窗**：δ=1 bin 时，Phase BPM 可能与幅值"碰巧"一致（假峰恰好落在同一 bin），需检查 gate-open 窗 Phase 的实际 BPM err

### 9.2 Part 3 风险

- **混淆矩阵需 per-window GT BPM**：HKH 的 GT 是呼吸带（belt）连续波形，per-window GT BPM 需从 belt 波形计算。若现有数据无此粒度的 GT，需先从 belt 波形提取

### 9.3 Part 4 风险

- **频带扩展到 0.4–0.6 Hz 可能引入高频假峰**：若 BPM 搜索范围不变（仍是 6–21 BPM），高频成分仅影响 η 计算，不直接影响寻峰。但 η 计算时高频噪声可能稀释呼吸频段能量比——效果可能适得其反
- **CS 金属板机械运动频率稳定**：频带扩展对 CS 影响应更小（金属板运动频率集中，η 本已接近 1.0）
- **扫描粒度粗**：本次仅测 0.40/0.50/0.60 三个点。若发现趋势但最优值在中间（如 0.45 Hz），后续可细化

### 9.4 保留问题

| ID | 问题 |
|----|------|
| Q1 | 若 Gate-A 和 Gate-B 均中性，是否正式结题门控路线？ |
| Q2 | 若频带扩展无效，η 的分辨力瓶颈是否来自 FFT 频率分辨率（20s 窗 = 0.05 Hz bin）而非频带范围？ |
| Q3 | CS 上 Phase 参与的必要性是否可通过更简单的 rule（如 CS 场景默认三模态、HKH 场景默认 R+L）绕过门控？ |

---

## 10. 验证状态

状态：**待实现**

---

## 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/gate_decomposition_band_diagnostic_plan.md`

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/gate_decomposition_band_diagnostic_plan.md`（回填 §10 验证状态）
- `docs/reports/gate_decomposition_band_diagnostic_report.md`
- `outputs/reports/gate_decomposition_*.json`
- `outputs/reports/eta_confusion_matrix.json`
- `outputs/reports/breathing_band_diagnostic.json`
- `outputs/figures/gate_decomposition_figF*.png`
- 关键脚本路径
- git commit message 或 git diff 摘要

Review 完成后，若结论改变方法推荐/废弃状态，Claude/DeepSeek 负责更新 `docs/methods/README.md`。
