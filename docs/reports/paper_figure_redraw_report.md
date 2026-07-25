# 论文第六章配图重绘 — 验证报告

> **Plan**：[`docs/plans/paper_figure_redraw_plan.md`](../plans/paper_figure_redraw_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_paper_figure_redraw.py`（命名模块：`src/ble_analysis/paper_naming.py`）  
> **场景**：HKH 12 场景（Fig 6–8a）；CS 金属板 `cs_091339/095806/102621`（Fig 8b）  
> **日期**：2026-07-25  
> **状态**：已完成

---

## 1. 目标与假设

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 用论文名称替换内部代号后，第六章图可读 | §1–§2 |
| H2 | BreatheCS 的 BPM 应取自谱分支（0.405），非波形分支（0.682） | §3.1 |
| H3 | §6.4 可用 RMSE 表补齐；Fig 7 维持位置并用论文名 | §3.3–§3.4 |
| H4 | 消融图可按维度分组（grouped + faceted 两版） | §3.5 / Q3 |

本轮**不重跑实验**，仅重绘。

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 数据源 | `ble_hkh_paper_baselines_summary.json`、`ble_hkh_b3_simplified_validation_summary.json`、`ble_hkh_b3_validation_summary.json`、`b2_coherent_mrc_all_cross_domain.npy` |
| 命名 | `paper_naming.PAPER_LABEL_MAP`（BreatheCS / Pos-Free / WiFi-Sleep / ClessBreath） |
| 指标 | 未改：BPM abs err、RMSE（z-score vs belt）；金属板 waterfall 仍为相对 BPM err % |

---

## 3. 实验设置

- **Baseline / 对比方法**：按 plan §3.1 精简至 8 个（缺 Single Remote，见下）
- **待测主方法**：BreatheCS（`b3_b1_equal`）
- **未改**：原始数据、GT、指标定义

---

## 4. 结果

### 4.1 产出路径

| 产出 | 路径 |
|------|------|
| Fig 6a | `outputs/figures/paper_fig6a_bpm_leaderboard.png` (+`.pdf`) |
| Fig 6b | `outputs/figures/paper_fig6b_bpm_by_room.png` (+`.pdf`) |
| Fig 7 | `outputs/figures/paper_fig7_bpm_vs_rmse.png` (+`.pdf`) |
| Fig 8a grouped | `outputs/figures/paper_fig8a_ablation_hkh.png` (+`.pdf`) |
| Fig 8a faceted | `outputs/figures/paper_fig8a_ablation_hkh_faceted.png` (+`.pdf`) |
| Fig 8b | `outputs/figures/paper_fig8b_waterfall_cs.png` (+`.pdf`) |
| RMSE 表片段 | `outputs/reports/paper_fig6_4_rmse_table.md` |
| 汇总 JSON | `outputs/reports/paper_figure_redraw_results.json` |
| Draft 更新 | `docs/plans/paper_draft_skeleton.md` §6.3–§6.5 |

### 4.2 主数字（跨 12 HKH 场景）

| Method | BPM mean abs | RMSE mean ± std |
|--------|-------------:|----------------:|
| BreatheCS ★ | **0.405** | **0.951 ± 0.192** |
| Pos-Free (PCA) | 0.435 | 1.070 ± 0.250 |
| WiFi-Sleep (MRC-PCA) | 0.505 | 1.063 ± 0.245 |
| BreatheCS-Wave | 0.682 | 0.950 ± 0.195 |
| WiFi-Sleep (√η) | 1.023 | — |
| PCA sign only | 1.317 | 1.085 ± 0.182 |
| ClessBreath (η-linear) | 1.386 | 1.025 ± 0.241 |
| ClessBreath (η-equal) | 1.486 | 1.046 ± 0.211 |

### 4.3 一致性检查

| 检查 | 结果 |
|------|------|
| B2-D RMSE：paper_baselines vs b3_simplified | Δ = **0.000000** ✅ |
| BreatheCS BPM 是否等于谱分支（非 Wave） | 0.405 = B1 Vote→Equal ✅ |
| Fig 6a 是否出现内部代号 B3/B1/B2 | 否 ✅ |

### 4.4 与 plan 预期对比

| 预期（Plan） | 实际 | 是否一致 |
|--------------|------|----------|
| 论文命名映射 | 已实现 | ✅ |
| Fig 6a 约 9 方法 | 8 方法（缺 Single Remote） | 部分 |
| Fig 6b 按房间 Top-5 | 已生成 | ✅ |
| §6.4 RMSE 表 | 已写入 draft | ✅ |
| Fig 7 论文名 + ★/◆ | 已生成 | ✅ |
| Fig 8a grouped + faceted | 两版均有 | ✅ |
| Fig 8b 论文名 + 标注 CS 金属板 | 已生成 | ✅ |

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| 第六章结果图可用论文名称重绘，且 BreatheCS BPM 取自谱分支 | **已验证** |
| 两 JSON 的 B2-D RMSE 可直接合并用于表格 | **已验证** |
| HKH 上 Single (Remote) abs-BPM≈1.952 可放入 Fig 6a | **未证实**（paper_baselines 无该 key） |

### 已验证

- 命名映射与 Fig 6a/6b/7/8a/8b 重绘完成
- BreatheCS = 0.405 BPM（谱）+ 0.951 RMSE（波）
- Draft §6 图路径已切换到 `paper_fig*` 新文件

### 仅单场景

- （无；本轮为跨场景重绘）

### 未证实

- Single (Remote) / `r12_d_single_remote` 的 HKH abs-BPM 未在现有 paper baselines JSON 中找到，Fig 6a 暂略

### 已废弃

- 无算法废弃；旧代号图仍保留在 `ble_hkh_*` / `b2_coherent_mrc_waterfall_*`，draft 不再引用

---

## 6. 保留问题

1. Fig 8a Phase 组中 Equal-weight (spectral) BPM 低于 BreatheCS-Wave——谱方法无波形，并列比较时需在正文说明指标口径。
2. Fig 8a 最终选用 grouped 还是 faceted，由用户决定。
3. 若论文需要 Single (Remote) 柱，需补跑或定位含该 key 的 HKH abs-BPM 结果后再并入 Fig 6a。

---

## Self Check

- Plan read: yes
- Baseline confirmed: yes（未改指标/baseline 定义）
- Scenario JSON used: yes（读既有 12 场景汇总；未硬编码帧）
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes
- Hardcoded frame index risk: no
- Baseline changed: no
- Metric definition changed: no
- Ready to commit: yes（待用户确认）
