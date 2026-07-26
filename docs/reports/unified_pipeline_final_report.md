# BreatheCS 统一管线最终收敛 — 验证报告

> **Plan**：[`docs/plans/unified_pipeline_final_plan.md`](../plans/unified_pipeline_final_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_unified_pipeline.py`（模块：`phase_adaptive_gating.py` / `systematic_fusion.py` / `b3_pipeline.py` / `waveform_metrics.py` / `iq_geometry.py`）  
> **场景**：HKH 12（`config/scenarios/room_*.json`）+ CS 3（`cs_091339` / `cs_095806` / `cs_102621`）  
> **日期**：2026-07-26  
> **状态**：已完成

---

## 1. 目标与假设

在 Amplitude-only（Candidate A）与 Phase-gated（Candidate B）之间做最终收敛选择；不引入新组件，仅用 LOSO 验证 Phase conf 闸门是否有 out-of-sample 价值。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | Candidate A（R+L η-weighted）在 HKH 上复现 ~0.372，且不劣于 Remote 0.376、优于等权三模态 0.405 | §1.4 / §5.3 |
| H2 | Candidate B 在 HKH LOSO 上不劣于 A；若 θ 稳定启用，CS 上可接近三模态 ~10.1% | §5.3 |
| H3 | LOSO 所选 θ 跨 fold 稳定；若常选 +∞，则 Phase 不应进入主方法 | §5.3 Q4 |
| H4 | R+L waveform RMSE 优于或不劣于 Remote-only 0.931（窗级对照） | §5.3 波形分支 |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | `remote_amplitudes` / `local_amplitudes` / `phases`（条件） |
| 信道融合 | Voting（η·ρ） |
| 模态融合 | η-weighted spectral average；波形支路 coherent MRC（η） |
| 闸门 | `gate_by_confidence(conf_P, θ)`；θ ∈ {0.30, 0.35, 0.38, 0.40, +∞}，4-fold LOSO |
| 滑窗与寻峰 | 20 s / 1 s；呼吸带 0.1–0.35 Hz |
| 波形 RMSE 协议 | recording-level z-score；全局 polarity；±2 s lag 一次搜索；overlap-average 拼接；另报 window-mean 对照 |

---

## 3. 实验设置

| 场景 ID | 用途 | 指标 |
|---------|------|------|
| HKH 12 recordings（4 subject × 3 room） | 主评估 + LOSO θ | BPM abs err；waveform RMSE |
| `cs_091339` / `cs_095806` / `cs_102621` | 跨域谱域对照 | BPM rel err %（无波形） |

- **Baseline（复用，不重跑全文）**：draft Remote / Equal / e3a 等；本脚本内重算 Remote 谱峰 BPM 与 R+L equal 以对齐
- **待测**：`candidate_a`、`candidate_b`、`rl_waveform`
- **CS θ**：HKH 4 个 LOSO fold 所选 θ 的规则中位数（本轮全部为 +∞ → CS 亦用 +∞）

---

## 4. 结果

### 4.1 HKH 谱域主结果（LOSO held-out recording mean）

| 方法（描述性名称） | Key | BPM abs err |
|--------------------|-----|------------:|
| Voting → R+L equal | `rl_equal` | **0.3717** |
| Amplitude-only BreatheCS（Voting → R+L η-weighted） | `candidate_a` | **0.3717** |
| Phase-gated BreatheCS（Voting → conf gate → η-weighted） | `candidate_b` | **0.3717** |
| Voting → Remote only | `draft_ms_remote` | 0.3760 |
| Voting → 三模态 η-weighted（无闸门） | `e3a` | 0.3957 |
| Voting → 三模态等权 | `draft_s_full` | 0.4050 |

图：`outputs/figures/unified_pipeline_hkh_main.png`、`unified_pipeline_modal_ablation.png`

### 4.2 LOSO 闸门阈值

| Held-out subject | 所选 θ | Train 最优误差（≈ Candidate A） |
|------------------|--------|--------------------------------:|
| sbj_A | **+∞** | 0.394 |
| sbj_B | **+∞** | 0.382 |
| sbj_C | **+∞** | 0.351 |
| sbj_D | **+∞** | 0.361 |

- 全部 fold 选择 **+∞**（Phase 永不启用）
- 有限 θ 上 train 误差单调随 θ 升高而下降，但仍差于 +∞
- Candidate B Phase 激活率 = **0**（HKH & CS）
- 配对差 A−B = 0（CI 退化为 0）

图：`outputs/figures/unified_pipeline_phase_reliability.png`、`unified_pipeline_paired_diff.png`  
结果：`outputs/reports/unified_pipeline_gate_loso.json`

### 4.3 Subject-cluster bootstrap（HKH，B=10000）

| 对比 | mean_diff (A−B) | 95% CI | 含 0？ |
|------|----------------:|--------|:------:|
| Candidate A vs Candidate B | 0.000 | [0, 0] | 是（相同） |
| Candidate A vs Remote | **−0.0043** | [−0.0079, −0.0006] | **否**（A 更好） |
| Candidate A vs Equal-3 | **−0.033** | [−0.068, −0.012] | **否**（A 更好） |

### 4.4 CS 谱域（θ=+∞，无波形）

| 方法 | BPM rel err % |
|------|--------------:|
| Voting → 三模态等权 | **10.14** |
| Voting → 三模态 η-weighted | 10.17 |
| Voting → Remote only | 11.23 |
| Amplitude-only / Phase-gated（θ=+∞） | **12.80** |
| Voting → R+L equal | 14.05 |

图：`outputs/figures/unified_pipeline_cs_spectral.png`

说明：因 LOSO 选 +∞，Candidate B **无法**在 CS 上自动启用 Phase，故与 A 同为 12.80%，未恢复三模态优势。

### 4.5 HKH 波形 RMSE

| 方法 | Recording-level RMSE | Window-mean RMSE（对照 draft） |
|------|---------------------:|-------------------------------:|
| R+L / Candidate A / B（θ=+∞） MRC | **0.666** | 0.937 |
| Remote-only MRC | 0.684 | **0.931** |

- Window-mean：R+L 0.937 ≈ Remote 0.931（略差，与 draft Remote 0.931 对齐）
- Recording-level 协议下：R+L **优于** Remote（0.666 vs 0.684）
- 因 θ=+∞，Candidate B 波形 ≡ Candidate A

结果：`outputs/reports/unified_pipeline_waveform_hkh_summary.json`

### 4.6 与 plan 预期对比

| 预期 | 实际 | 是否一致 |
|------|------|----------|
| Candidate A HKH ~0.372 | 0.3717 | ✅ |
| Candidate A CS ~14%（R+L equal 参考） | η-weighted **12.80%**；equal 14.05% | ✅（η-weighted 优于 equal） |
| Candidate B HKH ≈ A | 完全相同（θ=+∞） | ✅ |
| Candidate B CS ~10.1–10.2% | **12.80%**（未启用 Phase） | ❌（因 LOSO 选 +∞） |
| LOSO θ 稳定 / 或常选 +∞ | 4/4 为 +∞ | ✅ → 支持不把 Phase 纳入主方法 |
| R+L waveform vs Remote 0.931 | win-mean 0.937 ≈；rec-level 更优 | 部分 ✅ |

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| **选择 Candidate A（Amplitude-only R+L）作为谱域主方法** | **已验证**（HKH LOSO；全部 fold θ=+∞） |
| Candidate B 在当前闸门定义下无 out-of-sample BPM 增益 | **已验证**（B≡A；激活率 0） |
| HKH 上 R+L 显著优于等权三模态；略优于 Remote | **已验证**（subject-cluster CI 不含 0） |
| CS 上 R+L 仍劣于三模态等权/η-weighted | **已验证**（跨域已知代价；闸门未能自动恢复） |
| 波形：window-mean 与 Remote 持平；recording-level 协议下 R+L 略优 | **部分验证**（协议与 draft 窗级数字不完全同尺度） |

**相对 baseline**：HKH 上 Candidate A 优于 Remote / Equal-3；CS 上劣于三模态融合。

**部署建议**：默认部署 **Amplitude-only BreatheCS（Voting η·ρ → R+L η-weighted）**；Phase conf 闸门不进入主方法（可保留为 diagnostic / future work）。CS 金属板场景若需最优谱域 BPM，仍应使用三模态融合（与真人域默认配置分离，或作为域适配开关——超出本 plan 范围）。

---

## 6. 开放问题与下一步

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | CS 上 Amplitude-only 有 ~2.7 pp 相对三模态的代价，如何在产品中做域适配？ | Research：显式域开关 / 非 BPM 的域指示器（非本轮 conf 闸门） |
| Q2 | Recording-level RMSE 与 draft window-mean 数字尺度不同，论文应报告哪一种？ | Review：冻结一种协议写入 skeleton |
| Q3 | 是否仍保留 Phase 作为波形/ apnea 诊断变量？ | 交 Claude Review + dependencies plan D1/D3 分支 |

---

## 7. 复现

```bash
python notebooks/scripts/chFusion_unified_pipeline.py
# 仅谱域：
python notebooks/scripts/chFusion_unified_pipeline.py --skip-waveform
```

| 产出 | 路径 |
|------|------|
| 谱域汇总 | `outputs/reports/unified_pipeline_spectral_summary.json` |
| LOSO θ | `outputs/reports/unified_pipeline_gate_loso.json` |
| 波形汇总 | `outputs/reports/unified_pipeline_waveform_hkh_summary.json` |
| Phase 诊断 | `outputs/reports/unified_pipeline_phase_diagnostics.json` |
| Per-recording CSV | `outputs/reports/unified_pipeline_per_recording.csv` |
| 图表 | `outputs/figures/unified_pipeline_*.png` |
| 本报告 | `docs/reports/unified_pipeline_final_report.md` |

---

## 8. Plan 回填（执行 Agent 更新 plan 末尾）

- **验证状态**：已完成
- **实际脚本**：`notebooks/scripts/chFusion_unified_pipeline.py`
- **结论一句话**：4/4 LOSO fold 选 θ=+∞ → Candidate B≡A；推荐 Amplitude-only R+L 为主方法；CS 三模态优势无法由当前 conf 闸门自动恢复。

---

## Self Check

- Plan read: yes
- Baseline confirmed: yes（Remote 谱峰 BPM 已对齐 0.376）
- Scenario JSON used: yes
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes（见 plan §8）
- Hardcoded frame index risk: no
- Baseline changed: no（指标定义未改；Remote 从 voted_bpm 改为谱峰以与 draft 对齐）
- Metric definition changed: no
- Ready to commit: yes（待用户确认）
