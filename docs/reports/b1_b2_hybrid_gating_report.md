# B1+B2 窗级混合门控 — 验证报告

> **Plan**：[`docs/plans/b1_b2_hybrid_gating_plan.md`](../plans/b1_b2_hybrid_gating_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_b1_b2_hybrid_gating.py`（核心模块：`src/ble_analysis/hybrid_gating.py`）  
> **场景**：12 个 HKH 真人场景 `config/scenarios/room_{A,B,C}-sbj_{A,B,C,D}-*.json`  
> **日期**：2026-07-12  
> **状态**：已完成

---

## 1. 目标与假设

验证在 B3 管线输出上施加窗级 BPM 分歧门控（G-Hybrid），能否在共识窗利用 B2 BPM 优势、在分歧窗回退 B1，使跨域 BPM 优于 B1（0.41）。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 共识窗（Δ≤T）上 B2 BPM 优于 B1 | §3.4 D1 |
| H2 | 分歧窗门控可捕获 B2 崩溃窗，outlier 场景 BPM 改善 | §3.4 D3 |
| H3 | 存在 (G-H*, T) 使 12 场景 BPM ≤ B1（0.41） | §5.2 最低成功标准 |
| H4 | 最优 T 在 1.0–1.5 BPM 附近 | §4.3 |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | remote_amplitudes / local_amplitudes / phases |
| 前端 | B3 Shared Frontend（`b3_b1_equal` 变体，不改动融合逻辑） |
| 门控信号 | Δ(w) = \|bpm_b1(w) − bpm_b2(w)\| |
| G-H1 | Δ > T → B1；否则 → B2 |
| G-H2 | Δ > T → B1；否则 → mean(B1, B2) |
| G-H3 / G-H4 | 退化对照：始终 B1 / 始终 B2 |
| 阈值扫描 | T ∈ {0.5, 1.0, 1.5, 2.0} |
| 滑窗与寻峰 | 20 s / 1 s；呼吸频段 0.1–0.35 Hz；HKH GT Welch 寻峰 |

---

## 3. 实验设置

| 场景 ID | Room | 备注 |
|---------|------|------|
| room_A-sbj_{A,B,C,D}-* | A | A-D 为 outlier |
| room_B-sbj_{A,B,C,D}-* | B | — |
| room_C-sbj_{A,B,C,D}-* | C | C-A 为 outlier |

- **Baseline**：B1 Vote→Equal（0.405）、B2-D（0.682）、B3 Simplified ≡ B1（0.405）
- **待测方法**：G-H1/G-H2 × 4 阈值 + G-H3/G-H4
- **指标**：BPM 绝对误差 mean ± std（12 场景跨域）

---

## 4. 结果

### 4.1 主结果表（跨域 BPM mean abs err）

| 方法 | 12 场景 mean | 12 场景 std | 触发率 |
|------|-------------:|------------:|-------:|
| **B1 Vote→Equal / B3 Simplified** | **0.405** | 0.310 | — |
| G-H2 T=0.5 | 0.408 | 0.309 | 6.1% |
| G-H2 T=1.0 | 0.411 | 0.314 | 4.2% |
| G-H1 T=0.5（最优 G-H1） | 0.416 | 0.312 | 6.1% |
| G-H1 T=1.0 | 0.425 | 0.326 | 4.2% |
| G-H1 T=1.5 | 0.432 | 0.337 | 3.5% |
| G-H1 T=2.0 | 0.434 | 0.337 | 3.4% |
| B2-D / G-H4 | 0.682 | 0.837 | — |

数据来源：`outputs/reports/ble_hkh_hybrid_gating_summary.json`

### 4.2 Outlier 场景（G-H1 T=0.5）

| 场景 | B1 | B2 | G-H1 T=0.5 |
|------|---:|---:|-----------:|
| room_A-sbj_D（A-D） | 0.595 | 2.309 | 0.630 |
| room_C-sbj_A（C-A） | 0.267 | 1.396 | 0.292 |

门控在 A-D/C-A 上**未能**优于 B1：分歧窗虽回退 B1，但共识窗采用 B2 拉高了整体误差。

### 4.3 与 plan 预期对比

| 预期（Plan §x） | 实际 | 是否一致 |
|-----------------|------|----------|
| G-H1 vs B1：相当或略优 | G-H1 全部 ≥ B1（最优 0.416 > 0.405） | ❌ |
| G-H1 vs B2-D：明显更优 | 是（0.416 vs 0.682） | ✅ |
| 共识窗 B2 略优于 B1（D1） | 共识窗 B2 **更差**（Δ advantage = −0.013 @ T=0.5） | ❌ |
| 最优 T ≈ 1.0–1.5 | 最优 G-H1 在 T=0.5（仍劣于 B1） | ❌ |
| 失败路径：全 (G-H*,T) ≥ B1 → B3 确认最优 | **成立** | ✅ |

### 4.4 诊断

**D1 — 共识窗 B1 vs B2（跨场景 pooled，T=0.5）**

| 窗类型 | B1 mean abs err | B2 mean abs err |
|--------|----------------:|----------------:|
| 共识窗（Δ≤0.5） | 0.410 | 0.423 |
| B2 优势 | — | **−0.013**（B2 更差） |

**D2 — 门控触发率 vs T**

| T | Outlier 触发率 | Normal 触发率 |
|---|---------------:|--------------:|
| 0.5 | 24.6% | 2.4% |
| 1.0 | 19.2% | 1.2% |
| 1.5 | 17.6% | 0.7% |
| 2.0 | 16.8% | 0.7% |

Outlier 场景触发率显著高于正常场景，说明 Δ 信号**能区分** B2 不稳定窗口，但触发比例偏低（T=0.5 时 outlier 仅 ~25%），大量 B2 崩溃窗未被捕获。

**D3/D4 图**

- 阈值扫描：`outputs/figures/ble_hkh_hybrid_gating_threshold_scan.png`
- Outlier Δ 与 BPM 误差时序：`outputs/figures/ble_hkh_hybrid_gating_trigger_timeseries.png`
- Per-window 误差小提琴：`outputs/figures/ble_hkh_hybrid_gating_error_distribution.png`
- D2 触发率曲线：`outputs/figures/ble_hkh_hybrid_gating_d2_trigger_rate.png`

---

## 5. 结论

### 已验证

- 全部 12 场景实验完成；G-H3 ≡ B1、G-H4 ≡ B2 退化对照正确。
- G-Hybrid 相对 B2-D 显著改善 BPM（0.416 vs 0.682，最优 G-H1）。
- D2：outlier 场景门控触发率高于正常场景（机制部分有效）。
- **B3 Simplified（始终 B1 BPM + B2 波形）确认为 BPM 最优方案**——门控无增益。

### 仅单场景

- G-H1 在 A-D 上相对 B2 大幅改善（2.31→0.63），但仍劣于 B1（0.60）。

### 未证实

- H1：共识窗 B2 优于 B1（实际相反，B2 在共识窗也更差）。
- H3：无任何 (G-H*, T) 组合 BPM ≤ B1。

### 已废弃

- **G-Hybrid 窗级 BPM 门控**作为部署方案——所有阈值下均劣于 B1/B3 Simplified。

**相对 baseline**：G-Hybrid vs B1 — **更差**（+0.011 BPM，最优 G-H1 T=0.5）。

**部署建议**：维持 B3 Simplified（B1 BPM + B2-D 波形）；不引入 G-Hybrid 门控。

---

## 6. 开放问题与下一步

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | 为何共识窗 B2 也不优于 B1？ | 可能 B2 波形 PSD 寻峰在正常窗也有系统偏差；需 D1 窗级细查 |
| Q2 | Outlier 触发率仅 ~25%，是否 T 过小或 Δ 非充分统计量？ | 可探索更低 T 或组合门控，但当前负结果已足够支撑 B3 结论 |
| Q3 | CS 金属板场景是否不同？ | Plan Q4；本实验仅 HKH |
| Q4 | 是否更新 `docs/methods/README.md`？ | 交 Claude Review Mode 确认 G-Hybrid 废弃状态 |

---

## 7. 复现

```bash
python notebooks/scripts/chFusion_b1_b2_hybrid_gating.py
```

| 产出 | 路径 |
|------|------|
| 每场景 JSON | `outputs/reports/ble_hkh_hybrid_gating_{scenario_id}.json` ×12 |
| 跨场景汇总 | `outputs/reports/ble_hkh_hybrid_gating_summary.json` |
| 阈值扫描图 | `outputs/figures/ble_hkh_hybrid_gating_threshold_scan.png` |
| 触发时序图 | `outputs/figures/ble_hkh_hybrid_gating_trigger_timeseries.png` |
| 小提琴图 | `outputs/figures/ble_hkh_hybrid_gating_error_distribution.png` |
| D2 触发率图 | `outputs/figures/ble_hkh_hybrid_gating_d2_trigger_rate.png` |
| 本报告 | `docs/reports/b1_b2_hybrid_gating_report.md` |

---

## 8. Plan 回填

- **验证状态**：已完成
- **实际脚本**：`notebooks/scripts/chFusion_b1_b2_hybrid_gating.py`
- **结论一句话**：所有 G-Hybrid 变体 BPM ≥ B1（0.405）；门控无增益，B3 Simplified 确认最优。
