# η-only 质量指标消融 + Phase η-BPM Gate — 验证报告

> **Plan**：[`docs/plans/eta_only_ablation_plan.md`](../plans/eta_only_ablation_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_eta_only_ablation.py`（模块：`b3_pipeline.py` / `coherent_mrc.py` / `voting_fusion.py`）  
> **场景**：HKH 12（`config/scenarios/room_*.json`）+ CS 3（`cs_091339` / `cs_095806` / `cs_102621`，参考附录）  
> **日期**：2026-08-05  
> **状态**：已完成

---

## 1. 目标与假设

测试单一变量：论文方法集质量权重从 η·ρ 切换到 η-only；并在 η-only 信道权重上验证 Phase η-BPM Gate（G0–G4）。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | HKH 上 BreatheCS η-only 相对 η·ρ 不显著退化（Δ ≤ 0.02） | §6.3 Part 1 |
| H2 | 消融主序（Remote/Local/Channel/BreatheCS/Modal/No-fusion/Phase）不因 η-only 翻转 | §6.3 Part 1 |
| H3 | CS 上 η-only 轻度退化（预期 +0.5–1.5 pp） | §4.2 |
| H4 | G3（η 优越 + BPM 互验证）优于 G4 且不劣于 G0 | §6.3 Part 2 |
| H5 | Gate open ratio：CS ≫ HKH | §5.5 |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | `remote_amplitudes` / `local_amplitudes` / `phases` |
| 信道融合 | Voting：`eta_rho_weighted` vs `eta_weighted`；单 tone 选取同步配对 |
| 模态融合 | 等权谱融合（BreatheCS）；Gate 在 R+L vs 3-modal 间切换 |
| 滑窗与寻峰 | 20 s / 1 s；0.1–0.35 Hz；抛物线插值寻峰 |
| 实现修正 | `B3VariantConfig.tone_weight_mode="eta"` → **η-weighted**（非 A5 simple）；`coherent_mrc.quality_mode="eta"` |

---

## 3. 实验设置

| 域 | 场景 | 指标 | 角色 |
|----|------|------|------|
| HKH | 12 recordings | BPM abs err（mean±std）；Wave RMSE（mean±std） | **主评估** |
| CS | 3 metal-plate | BPM rel err %（mean±std） | **参考附录** |

- **Baseline**：论文现状 η·ρ（BreatheCS / draft 消融 / B2-D / B3）
- **待测**：对应 η-only 配对；Part 2 G0–G4（η-only tones）
- **外部 baseline**：质量指标未改；HKH 侧复用同管线既有 `ble_hkh_paper_baselines_summary.json`（provenance 写入 leaderboard JSON）

---

## 4. 结果

### 4.1 Part 1 — HKH 谱域配对（主表）

> 数字为跨 12 场景 mean ± std（BPM abs err）。  
> 单模态 / 幅值双模态 / 三模态均列出，便于对照 Phase 贡献。

| 方法 | η·ρ | η-only | Δ (η−η·ρ) |
|------|----:|-------:|----------:|
| Remote only | 0.376±0.115 | **0.366±0.120** | −0.010 |
| Local only | 0.378±0.119 | **0.376±0.128** | −0.002 |
| **Amplitude-only（R+L equal）** | **0.372±0.118** | **0.371±0.128** | −0.001 |
| Phase only | 2.191±1.302 | 2.250±1.413 | +0.059 |
| Channel only | 0.381±0.116 | 0.391±0.114 | +0.011 |
| **BreatheCS（Vote→3-modal equal）** | **0.405±0.144** | **0.403±0.152** | **−0.002** |
| B3 unified | 0.405±0.144 | 0.403±0.152 | −0.002 |
| Modal only | 0.655±0.245 | 1.116±1.857 | +0.461 |
| No fusion | 1.640±0.464 | 2.403±1.804 | +0.764 |
| BreatheCS-Wave (B2-D) | 0.682±0.574 | 0.756±0.738 | +0.074 |

来源：`outputs/reports/eta_only_ablation_delta.csv`、`eta_only_ablation_hkh_leaderboard.json`  
要点：HKH 上 **R+L（0.372）优于三模态 BreatheCS（0.405）**；Remote/Local 单模态也略优于三模态。

图：`outputs/figures/eta_only_ablation_figG1_hkh_leaderboard.png`、`eta_only_ablation_figG2_hkh_ablation.png`

### 4.2 Part 1 — HKH 波形消融（RMSE）

> Wave BPM / RMSE 均为跨场景 mean ± std。

| 方法 | Wave BPM η·ρ | Wave BPM η | RMSE η·ρ | RMSE η |
|------|-------------:|-----------:|---------:|-------:|
| Wave · Remote only | 0.399±0.121 | 0.501±0.326 | 0.931±0.207 | 0.989±0.207 |
| Wave · Local only | 0.439±0.217 | 0.464±0.240 | 0.947±0.214 | 0.981±0.196 |
| Wave · Phase only | 2.395±1.169 | 2.236±1.492 | 1.109±0.111 | 1.124±0.121 |
| Wave · Channel only | 1.003±1.193 | 1.145±1.506 | 0.962±0.195 | 1.008±0.205 |
| Wave · BreatheCS | 0.744±0.706 | 0.817±0.871 | **0.951±0.184** | 0.994±0.192 |

η-only 在波形支路普遍轻度退化（BPM 与 RMSE）。

### 4.3 Part 1 — CS 参考附录

> 跨 3 场景 mean ± std（BPM rel err %）。

| 方法 | η·ρ (%) | η-only (%) | Δ (pp) |
|------|--------:|-----------:|-------:|
| Remote only | 11.23±4.16 | 12.03±3.87 | +0.79 |
| Local only | 16.21±11.65 | 16.23±10.10 | +0.02 |
| Amplitude-only（R+L） | 14.05±8.62 | 14.64±7.97 | +0.59 |
| Phase only | 10.92±4.12 | 11.39±3.17 | +0.47 |
| Channel only | 12.51±7.68 | 13.68±7.25 | +1.17 |
| **BreatheCS** | **10.14±3.90** | 10.72±3.29 | **+0.58** |
| Modal only | 13.40±6.01 | **12.39±4.51** | −1.01 |
| B2-D | 9.45±3.70 | 10.87±5.06 | +1.42 |

CS 上 Phase / 三模态明显优于 R+L（Local 拖累）；与 HKH「幅值双模态更优」形成对照。

图：`outputs/figures/eta_only_ablation_figG3_cs_leaderboard.png`

### 4.4 Part 2 — Phase η-BPM Gate

> HKH/CS BPM 为跨场景 mean ± std；open ratio 为跨场景均值。

| Gate | HKH BPM | HKH open | CS BPM % | CS open |
|------|--------:|---------:|---------:|--------:|
| G0 R+L only | **0.371±0.128** | 0% | 14.64±7.97 | 0% |
| G1 η-relaxed | 0.382±0.140 | 6.8% | 12.72±5.32 | 22.9% |
| G2 η-strict | 0.381±0.139 | 6.1% | 14.38±7.67 | 7.6% |
| G3 η+BPM | **0.371±0.128** | 1.3% | 14.61±7.94 | 3.7% |
| G4-upper 3-modal | 0.403±0.152 | 100% | **10.72±3.29** | 100% |

- HKH：G3 ≈ G0（几乎不打开 Phase）；G1/G2 打开的窗 Phase 误差高（open-phase err ≈ 5–6），相对 G0 有害。
- CS：open ratio **未**出现 CS ≫ HKH 的期望自适应；G3 几乎退化为 R+L，而 CS 最优仍是 G4 常开三模态。

图：`outputs/figures/eta_only_ablation_figG5_gate_behavior.png`、`figG4_rho_distribution.png`

### 4.5 与 plan 预期对比

| 预期 | 实际 | 是否一致 |
|------|------|----------|
| HKH BreatheCS η-only 持平或略优 | 0.403 vs 0.405（Δ=−0.002） | ✅ |
| CS 轻度退化 +0.5–1.5 pp | +0.58 pp | ✅ |
| No-fusion/Modal-only 需配对（非已是 η-only） | η-only 下大幅退化 | ✅（ρ 对单 tone 选取仍关键） |
| G3 优于 G4 且 ≤ G0+0.01 | G3≈G0≪G4（HKH）；CS 上 G3≪G4 | 部分（HKH 中性；跨域失败） |
| CS open ≫ HKH open | G3：CS 3.7% vs HKH 1.3% | ❌ 未达自适应 |

---

## 5. 结论

### 已验证

- **HKH 上 BreatheCS 谱 BPM：η-only ≈ η·ρ**（Δ=−0.002 ≤ 0.02），满足 Part 1「可按简洁性切换 η-only」数值门槛。
- **主消融序不翻转**：Remote/Local/Channel 仍优于或接近 BreatheCS；Phase / No-fusion 仍最差。
- **CS 参考**：BreatheCS η-only 退化 **+0.58 pp < 1.0 pp**，未触发「CS 必须保留 η·ρ」的分域硬阈值。
- **ρ 对单 tone 选取仍有价值**：No-fusion / Modal-only 在 η-only 下明显变差（不能把「Voting 路径可去 ρ」外推到 max-quality 选道）。

### 仅单场景 / 参考域

- CS 全部结论标记为**参考附录**（论文主表仍以 HKH 为准）。
- Gate open 行为高度场景依赖（HKH 上几乎仅个别 recording 打开）。

### 未证实

- **G3 Gate 有效并优于两端点**：HKH 上 G3≡G0（中性）；CS 上远差于 G4 → **不支持**写入默认 BreatheCS。
- **跨域自适应 Phase 纳入**（CS 常开 / HKH 慎开）：未实现。

### 已废弃（本轮）

- 将 G1/G2（仅 η 门控、无 BPM 互验证或过松）作为部署候选：HKH 上相对 G0 有害。
- 「η 优越性门控即可替代三模态/双模态域适配」——当前证据不支持。

**相对 baseline**：  
- 谱域 BreatheCS：**η-only 可替换 η·ρ（HKH 主域）**，代价是单 tone 消融变体与波形支路轻度变差。  
- Phase：**默认不参与**（R+L）在 HKH 仍优于三模态；本轮 Gate 未能在保留 R+L 优势的同时恢复 CS 三模态收益。

**部署建议（供 Review，非自动 recommended）**：  
综合判定落在 plan §6.3「次佳」：`BreatheCS = η-only weights + R+L`（Phase 保留为条件观测，但不默认进融合）。G3 不必写入 §5.6 默认机制，除非后续改条件。

---

## 6. 风险与缺失

- 外部 baseline 未在本脚本内全量重跑，而是复用同管线既有 summary（质量指标未变）；若需绝对同次 seed 对齐可补跑。
- Channel-only 首次实现曾误用 mean-η 作 pick_best 分数，已改为 voting confidence 并重跑；报告数字以重跑为准。
- B2-D HKH 为窗级 belt GT 路径；与论文 waveform 协议细节可能略有尺度差，但 η·ρ 基线 0.682 与论文对照一致。

---

## 7. 产出路径

| 类型 | 路径 |
|------|------|
| 脚本 | `notebooks/scripts/chFusion_eta_only_ablation.py` |
| HKH leaderboard | `outputs/reports/eta_only_ablation_hkh_leaderboard.json` |
| HKH ablation | `outputs/reports/eta_only_ablation_hkh_ablation.json` |
| Phase gate | `outputs/reports/eta_only_ablation_phase_gate.json` |
| CS 参考 | `outputs/reports/eta_only_ablation_cs_leaderboard.json` |
| Δ 表 | `outputs/reports/eta_only_ablation_delta.csv` |
| 图 G1–G5 | `outputs/figures/eta_only_ablation_figG*.png` |

---

## Self Check

- Plan read: yes
- Baseline confirmed: yes（BreatheCS 0.405 / Channel 0.381 对齐）
- Scenario JSON used: yes
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes（见 plan §10）
- Hardcoded frame index risk: no
- Baseline changed: no
- Metric definition changed: no
- Ready to commit: yes（待用户确认后提交）
