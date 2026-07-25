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

## 2. 主结果（12-scenario mean，3 位小数）

### 融合层级

| 槽位 | BPM | RMSE |
|------|----:|-----:|
| Spec · no fusion | 1.640 | — |
| Spec · channel only | 0.381 | — |
| Spec · modal only | 0.655 | — |
| Spec · BreatheCS | 0.405 | — |
| Wave · no fusion | 1.192 | 1.007 |
| Wave · channel only | 1.003 | 0.962 |
| Wave · modal only | 1.025 | 0.986 |
| Wave · BreatheCS | 0.744 | 0.951 |

### 单模态（谱 / 时域分开）

| Domain | Remote | Local | Phase | BreatheCS |
|---|---:|---:|---:|---:|
| Spectral BPM | 0.376 | 0.378 | 2.191 | 0.405 |
| Waveform BPM | 0.399 | 0.439 | 2.395 | 0.744 |
| Waveform RMSE | 0.931 | 0.947 | 1.109 | 0.951 |

说明：先前 `draft_m_*` 是「谱 BPM 为主 + 顺带算波形 RMSE」的混合口径；现已拆成 `draft_ms_*`（纯谱）与 `draft_mw_*`（纯时域）。

---

## 3. 图表

- `outputs/figures/paper_fig8a_ablation_draft_bpm.png`
- `outputs/figures/paper_fig8a_ablation_draft_rmse.png`
- `outputs/figures/paper_fig8c_ablation_draft_modal.png`
- 汇总：`outputs/reports/ble_hkh_draft_ablation_summary.json`

---

## 5. 模态消融解读与后续优化建议

### BreatheCS 三模态怎么融？

谱分支：**逐模态 η·ρ 加权谱 → 三模态等权 (1:1:1) 谱平均 → 寻峰**。  
时域分支：**逐模态 Hilbert tone 融合 → 三模态 Hilbert 对齐 + η·coherence 加权**（不是简单等权平均幅值）。  
因此「等权」主要体现在**谱 BPM 的模态级**；时域模态级仍有质量加权，但 Phase 波形差时仍会污染融合结果。

### 单模态结果说明了什么？

| 观察 | 数字 | 含义 |
|------|------|------|
| Phase 单独极差 | 谱 BPM 2.191 / 波 BPM 2.395 / RMSE 1.109 | phases 在本 HKH 集合上噪声大，不宜与幅值等权硬融 |
| Remote/Local 略优于三模态等权 | 谱 0.376–0.378 vs BreatheCS 0.405 | 等权把 Phase 拖累进来，均值上不占优 |
| 时域 Remote RMSE 仍略优 | 0.931 vs BreatheCS 0.951 | 波形融合同样受弱模态拖累 |
| Channel-only（选最优模态）也略优 | 谱 0.381 | 「挑好模态」>「等权硬融」在本数据上成立 |

**结论（与你的判断一致）**：当前等权三模态的「平均优势」在 HKH 上**未证实**；主要机制很可能是 **Phase 质量系统性偏弱**，等权/半等权融合把差模态噪声注入好模态。物理对称仍是合理先验，但需要**质量门控或自适应权重**，而不是无条件 1:1:1。

### 后续算法优化建议（按优先级）

1. **模态级质量门控（优先）**  
   - 窗级估计每模态 η、ρ、以及与其它模态的谱峰一致性；  
   - Phase 若 η/ρ 低或峰不一致 → 降权或剔除，而不是等权。  
   - 对应实验：复用 `draft_s_channel`（pick-best）思想，但改为 soft gate，避免硬选过拟合。

2. **自适应模态权重（替代死等权）**  
   - \(w_m \propto \eta_m \rho_m\) 或 \(w_m \propto \eta_m \cdot \mathrm{coherence}(m,\mathrm{ref})\)；  
   - 归一化后谱融合 / 波形 MRC；  
   - 约束：不得默认偏爱 Remote（物理对称），权重必须由窗级质量决定。

3. **Phase 专用预处理**  
   - 检查 unwrap / 高通是否引入额外抖动；  
   - 对 phases 提高中值滤波或降低其在低 γ 窗的贡献；  
   - 可选：Phase 只作「一致性校验」，不直接进主 BPM。

4. **双候选共识（部署层）**  
   - 候选 A：质量加权三模态；候选 B：幅值-only（Remote+Local）；  
   - 窗级 BPM 接近则平均，分歧则取质量更高者——避免 Phase 拖垮。

5. **论文表述建议**  
   - 把「等权」写成物理先验 + 消融对照，而不是「已证明最优」；  
   - 用 Fig 8(d–f) 诚实报告 Phase 失效与 Remote/Local 优势；  
   - 将自适应门控列为 future work / 下一轮 plan。

---

## Self Check

- Plan read: yes
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Hardcoded frame index: no
- Metric definition changed: no
- Ready to commit: yes
