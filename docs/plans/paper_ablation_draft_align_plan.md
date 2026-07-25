# Plan: Align §6.5 ablation figures to draft prose (HKH)

> **目标**：按 `paper_draft_skeleton.md` §6.5 原文的 1/2/3 点消融矩阵出图，不再使用 plan 的「信道/模态/相位」临时分组。  
> **日期**：2026-07-25  
> **验证状态**：进行中

---

## 1. Draft 原文需求（单一事实来源）

1. **时域波形融合**（有 BPM + RMSE）  
   - 不融合：两级均选 max-η  
   - 仅信道融合，模态选最大  
   - 仅模态融合，信道选最大  
   - BreatheCS  

2. **频域谱融合**（仅 BPM）  
   - 同上四档  
   - BreatheCS  

3. **局限单一模态**  
   - remote / local / phase 各一条 + BreatheCS  

---

## 2. 与已有变体的对应（HKH 已跑）

| Draft 槽位 | 已有 key | BPM | RMSE | 对应质量 |
|---|---|---:|---:|---|
| 谱 · 完整 BreatheCS | `b1_vote_modal_equal` / `a4_equal_spectral` / `b3_b1_equal` | 0.405 | N/A | ✅ 精确 |
| 波 · 完整（波形分支） | `b2_d_two_level`（BPM 用波形 PSD；RMSE） | 0.682 | 0.950 | ✅ 精确（作「时域完整」） |
| 波 · 仅模态融合、信道选最大 | `a1_single_best_eta` | 0.958 | 0.950 | ✅ 近似（每模态 max-η tone + 模态 Hilbert） |
| 波 · Remote-only（兼单模态） | `a3_remote_only` | 0.463 | 0.930 | ✅ 单模态 remote；也近似「仅信道、单模态」 |
| 谱 · 等权投票权重消融 | `a5_equal_voting` | 0.442 | 0.950 | ⚠️ 非 draft 四档结构 |
| 单模态 local / phase | — | — | — | ❌ 未跑 |
| 谱 · 不融合 / 仅信道 / 仅模态 | — | — | — | ❌ 未按 draft 四档明确跑 |
| 波 · 不融合 / 仅信道融合 | — | — | — | ❌ 缺清晰变体 |

---

## 3. 本轮执行

1. 扩展 `B3VariantConfig`：`modal_variables` + `bpm_source` + 修复 `use_voting=False` 时仍输出 best-tone spectrum（谱 BPM 可算）  
2. 新增 draft 对齐变体并在 HKH 12 场景跑缺失项  
3. 重绘 Fig 8：`(a)` 时域四档 `(b)` 谱域四档 `(c)` 单模态三+BreatheCS  
4. 更新 draft §6.5 图路径与引用说明  

---

## 4. 验证状态

状态：已完成  

实际产出路径：
- 脚本：`notebooks/scripts/chFusion_paper_ablation_draft.py`
- 模块：`src/ble_analysis/b3_pipeline.py`（`DRAFT_ABLATION_SPECS`）
- 数值：`outputs/reports/ble_hkh_draft_ablation_summary.json`
- 图表：`paper_fig8a_ablation_draft_bpm/rmse.png`、`paper_fig8c_ablation_draft_modal.png`
- 报告：`docs/reports/paper_ablation_draft_align_report.md`

结论摘要：Draft 1/2/3 矩阵已在 HKH 跑通；时域四档增益清晰；谱域 channel-only / Remote-only 均值略优于等权 BreatheCS，正文需讨论物理自洽 vs 均值最优。

遗留问题：是否在正文强调「等权」的物理理由；Fig 8b CS waterfall 是否仍保留为补充。
