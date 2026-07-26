# Phase 互补投影角色与自适应融合 — 验证报告

> **Plan**：[`docs/plans/phase_unique_role_adaptive_fusion_plan.md`](../plans/phase_unique_role_adaptive_fusion_plan.md)  
> **Dependencies**：[`docs/plans/paper_experiment_dependencies_plan.md`](../plans/paper_experiment_dependencies_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_phase_p0_audit.py`、`chFusion_phase_diagnostics.py`、`chFusion_phase_adaptive_fusion.py`  
> **模块**：`src/ble_analysis/iq_geometry.py`、`phase_adaptive_gating.py`  
> **日期**：2026-07-26  
> **状态**：已完成（P0→E1/E4/E5→简化 E2/E3；严格按 v2.0 §9）

---

## 1. 目标与假设

在修正物理模型（径向/切向互补投影）下，检验 Phase 是否提供可门控的 BPM 增量，以及 η·ρ 模态级失效与跨域 Phase 差异的机制。

| ID | 假设 | 结果 |
|----|------|------|
| H1 | Phase-best 对应幅值联合弱响应（q_amp 低） | ❌ 不支持 |
| H2 | Phase-best 窗内 Phase 波形优于幅值 | ❌ 不支持 |
| H3 | Phase 在 R/L 双失败时有实质救援 | 部分（rescue≈18%，但 destruction≈49%） |
| E2/E3 | 简化门控 LOSO 优于 R+L | ❌ 不支持（HKH） |

成功标准（plan §5.4）：最低=P0+E1 完成；理想=E2/E3 不劣于 R+L；突破=显著优于 R+L 与 Remote。

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | `remote_amplitudes` / `local_amplitudes` / `phases`（不用 total amplitudes） |
| 信道融合 | Voting（η·ρ 权重），与既有 B3 一致 |
| 模态融合 | R+L 等权默认；E2 tie-break；E3 conditional（D1=C → 仅 3 变体） |
| 阈值 | HKH leave-one-subject-out 选 `T_agree∈{0.5,1.0}`（全部折选 1.0） |
| 统计 | recording-level mean + paired bootstrap |

---

## 3. 实验设置

| 域 | 场景 | 指标 |
|----|------|------|
| HKH | 12 条（3 room × 4 subject） | BPM abs err（breaths/min） |
| CS | `cs_091339` / `cs_095806` / `cs_102621` | BPM rel err % |

Baseline：`p0_rl_default`（R+L）、Equal 三模态、（缓存内）Remote；外部对照 draft Remote=0.376 / Equal=0.405。

---

## 4. 结果

### 4.1 P0 审计

| 项 | 判定 | 关键数字 |
|----|------|----------|
| D1 oracle Δ | **条件 C** | mean Δ=**0.028** BPM；≥0.05:2；≤0.01:2；中间:8 |
| D2 IQ 几何 | **条件 B** | 径向无清晰下降；切向仅弱升高 |
| D4 显著性 | **条件 B** | Remote−Equal CI **[−0.058,−0.004]** 不含 0 |
| D5 聚集性 | **条件 B** | 105 窗 / 58 段；top2 subject 37% |

图：`outputs/figures/phase_p0_oracle_delta.png`、`phase_p0_radial_tangential_energy.png`、`phase_p0_statistical_audit.png`

### 4.2 E1 诊断

| 实验 | HKH | CS |
|------|-----|-----|
| E1a H1 q_amp | 不支持（Phase q_amp median≈Remote；双弱 43.8%） | 不支持 |
| E1b H2 波形 | Δr_P mean=**−0.081**（Phase 更差）；frac Phase better=35% | —（仅 HKH） |
| E1c rescue | rescue=**0.180**；unique=**0.012**；destruction=**0.487** | 0.229 / 0.082 / 0.289 |
| E1c 误差相关 | R-L **0.84** vs R-P **0.10** | — |

图：`phase_e1_complementary_projection.png`、`phase_e1_rescue_metrics.png`、`phase_e1_waveform_fidelity.png`

### 4.3 E4 / E5

- **E4**：模态级 η hit > η·ρ（HKH 63.6% vs 54.3%）；分歧窗 η 胜更多；ρ 奖励尖峰（含假峰）
- **E5**：H5a 否；H5b/H5c 是（HKH Phase ρ/conf 更低）；HKH Phase err 2.09 vs CS 1.26

图：`phase_e4_channel_vs_modal_rho.png`、`phase_e5_hkh_vs_cs_quality_dist.png`

### 4.4 简化 E2/E3（主结果）

**HKH**（recording-level mean abs BPM，LOSO）：

| 方法 | mean abs err |
|------|-------------:|
| **R+L 等权（无 Phase）** | **0.372** |
| R+L + Phase conditional | 0.376 |
| R+L + Phase tie-break | 0.376 |
| Equal 三模态 | 0.405 |
| Remote（本缓存） | 0.463 |

- R+L vs e2/e3：paired CI **含 0**（门控无显著增益）
- R+L vs Equal：显著更优（CI 不含 0）

**CS**（recording-level mean rel %，t_agree=1.0 固定）：

| 方法 | mean rel % |
|------|-----------:|
| Equal 三模态 | **10.14** |
| Remote（本缓存） | 10.53 |
| R+L + Phase tie-break | 10.77 |
| R+L + Phase conditional | 11.29 |
| R+L 等权（无 Phase） | 14.05 |

图：`phase_adaptive_fusion_hkh_leaderboard.png`、`phase_adaptive_fusion_cs_leaderboard.png`

### 4.5 与 plan 预期对比

| 预期 | 实际 | 一致？ |
|------|------|--------|
| P0a Δ 可能很小 | mean 0.028（条件 C） | ✅ |
| P0b 互补投影成立 | 不成立 | ❌ |
| E2/E3 优于 R+L | HKH 不优；CS 优于 R+L 但不优于 Equal | ❌ / 部分 |
| 跨域分表 | 已分表 | ✅ |

---

## 5. 结论

### 已验证

- P0a：Phase BPM oracle 增量有限（条件 C）
- P0c/D4：HKH 上 Remote 显著优于 Equal 三模态
- E4：模态级应优先 η-only，不宜照搬信道级 η·ρ
- E5：HKH Phase 峰钝/低 conf（非 η 方差故事）
- E2/E3：HKH 上门控相对 R+L **无显著 BPM 增益**（D3 条件 B）
- HKH 上 **R+L 双模态** 明显优于三模态等权（本实验内）

### 仅单场景 / 分域

- CS 上 Equal 仍最优；R+L 单独很差（Local 拖累），Phase 参与有帮助但达不到 Equal

### 未证实

- 互补投影救援作为可部署 BPM 组件（H1/H2/E2/E3 均未支持）
- Phase 波形保真优势（E1b 否定）

### 已废弃（本轮语境）

- 以「Phase 与 R+L 一致时加票」或大规模权重搜索换 BPM 的路线
- 将 Phase BPM rescue 写入 Abstract / 核心贡献（除非未来受控实验改写）

**部署建议**：HKH 类真人数据默认考虑 **R+L 或 Remote/Channel**，不要默认三模态等权；Phase 保留为 diagnostic / 波形或未来 apnea 线索，不作为当前 BPM 门控主组件。

---

## 6. 开放问题

| ID | 问题 |
|----|------|
| Q1 | 本缓存 Remote(0.463) 与 draft Remote(0.376) 的管线差异需核对（不影响 R+L vs 门控相对结论） |
| Q2 | CS 上为何 R+L 单独崩、Equal 最优——Local 噪声结构？ |
| Q3 | P2 受控工作点扫描是否可做（D6） |

---

## 7. Self Check

- Plan read: **yes**
- Baseline confirmed: **yes**（R+L / Equal；draft Remote 作外部对照）
- Scenario JSON used: **yes**
- Script executed: **yes**
- Results generated: **yes**
- Figures generated: **yes**
- Report generated: **yes**
- Plan updated: **yes**
- Dependencies D1–D5/D7/D3 回填: **yes**
- Hardcoded frame index risk: **no**
- Baseline changed: **no**
- Metric definition changed: **no**
- E2/E3 在 P0 前开始: **no**（遵守）
- Ready to commit: **yes**（待用户确认）
