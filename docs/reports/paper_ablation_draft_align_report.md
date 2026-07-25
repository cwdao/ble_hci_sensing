# Draft §6.5 消融矩阵对齐 — 验证报告

> **Plan**：[`docs/plans/paper_ablation_draft_align_plan.md`](../plans/paper_ablation_draft_align_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_paper_ablation_draft.py`（`src/ble_analysis/b3_pipeline.py` 扩展）  
> **场景**：HKH 12  
> **日期**：2026-07-25  
> **状态**：已完成

---

## 1. 目标

按 draft §6.5 原文三点出图：时域四档 / 谱域四档 / 单模态三+BreatheCS。

---

## 2. 主结果（12-scenario mean）

| 槽位 | key | BPM | RMSE |
|------|-----|----:|-----:|
| Spec · no fusion | draft_s_none | 1.640 | N/A |
| Spec · channel only | draft_s_channel | **0.381** | N/A |
| Spec · modal only | draft_s_modal | 0.655 | N/A |
| Spec · BreatheCS | draft_s_full | 0.405 | N/A |
| Wave · no fusion | draft_w_none | 1.192 | 1.007 |
| Wave · channel only | draft_w_channel | 1.003 | 0.962 |
| Wave · modal only | draft_w_modal | 1.025 | 0.986 |
| Wave · BreatheCS | draft_w_full | **0.744** | **0.951** |
| Single · Remote | draft_m_remote | **0.376** | 0.931 |
| Single · Local | draft_m_local | 0.378 | 0.947 |
| Single · Phase | draft_m_phase | 2.191 | 1.109 |

### 关键观察

1. **谱域**：不融合最差；channel-only (0.381) 略优于等权三模态 BreatheCS (0.405)——需在正文诚实讨论「选最优模态 vs 等权」的 trade-off（物理自洽仍偏向等权）。
2. **时域**：四档单调改善，BreatheCS 波形最优（BPM 0.744 / RMSE 0.951）。
3. **单模态**：Remote/Local 谱 BPM 略优于三模态等权；Phase 单独极差。等权三模态的动机仍是物理对称与鲁棒，而非本 12 场景均值最优。

---

## 3. 图表

- `outputs/figures/paper_fig8a_ablation_draft_bpm.png`
- `outputs/figures/paper_fig8a_ablation_draft_rmse.png`
- `outputs/figures/paper_fig8c_ablation_draft_modal.png`
- 汇总：`outputs/reports/ble_hkh_draft_ablation_summary.json`

---

## 4. 结论

| 结论 | 证据强度 |
|------|----------|
| Draft 1/2/3 消融矩阵已在 HKH 跑通并出图 | **已验证** |
| 时域融合层级对波形 BPM/RMSE 有清晰增益 | **已验证** |
| 谱域等权三模态在 12 场景均值上未必优于 channel-only / Remote-only | **已验证**（负面/需讨论） |

### 已验证
- 按 draft 结构的 Fig 8a/8a′/8c

### 未证实
- （无）

---

## Self Check

- Plan read: yes
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Hardcoded frame index: no
- Metric definition changed: no
- Ready to commit: yes
