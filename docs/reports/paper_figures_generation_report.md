# Paper Figures Generation — Mechanism Validation 验证报告

> **Plan**：[`docs/plans/paper_figures_generation_plan.md`](../plans/paper_figures_generation_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_paper_figures_mechanism.py`（核心模块：`coherent_mrc` / `systematic_fusion` / `voting_fusion` / `wifi_mrc`）  
> **场景**：`config/scenarios/cs_091339.json`、`cs_095806.json`、`cs_102621.json`  
> **日期**：2026-07-18  
> **状态**：已完成

---

## 1. 目标与假设

从 CS 金属板已缓存滤波数据中提取窗级诊断量，绘制论文 Figure 2/3/5/S1，支撑 §2–§3 机制论述。本任务为**配图/机制可视化**，不做 BPM 误差排行榜。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 同模态 tone 间不仅有 ±1 相位关系，还存在需连续相位对齐的结构；Hilbert 对齐后波形近乎重合 | Fig 2 |
| H2 | 三模态 Level-1 波形相位不同；Level-2 Hilbert 可对齐；跨窗 Δφ 非固定且房间依赖 | Fig 3 |
| H3 | η·ρ 加权投票相对等权能突出高质量 tone，融合谱更干净 | Fig 5 |
| H4 | 好场景 tone-pair γ 稳定高，难场景同 index 对 γ 更低且波动更大 | Fig S1 |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | `remote_amplitudes` / `local_amplitudes` / `phases`（Fig 2/5/S1 主用 remote） |
| 数据加载 | `load_multichannel_for_scenario` + `outputs/cache`（三场景全缓存命中） |
| 信道融合 | Level-1 Hilbert MRC（`coherence_gated`）；Voting η·ρ（Fig 5） |
| 模态融合 | Level-2 Hilbert + `eta_coherence`（Fig 3） |
| 滑窗 | 20 s / 1 s；呼吸频段 0.1–0.35 Hz |

---

## 3. 实验设置

| 场景 ID | 数据文件 | 备注 |
|---------|----------|------|
| cs_091339 | `sampleData/CS_frames_all_20260113_091339.jsonl` | hard（Fig 2d / S1） |
| cs_095806 | `sampleData/CS_frames_all_20260116_095806.jsonl` | good（主图） |
| cs_102621 | `sampleData/CS_frames_all_20260116_102621.jsonl` | Fig 3(d) 跨房间 |

- **代表窗口**：`cs_095806` / segment `1b` / window `16`（按 η·ρ 中位附近 + 相位多样性自动选）
- **代表 tones**：58 (ref)、48 (同相)、45 (反相 Δφ≈π)、69 (中间相位 Δφ≈−0.83)
- **Baseline**（机制对比，非 BPM 排行）：Uniform 谱平均 vs η·ρ Voting；±1 sign vs Hilbert

---

## 4. 结果

### 4.1 产出清单

| 产出 | PNG | PDF |
|------|-----|-----|
| Figure 2 | `outputs/figures/paper_fig2_inter_tone_phase.png` | `outputs/figures/paper_fig2_inter_tone_phase.pdf` |
| Figure 3 | `outputs/figures/paper_fig3_inter_modal_phase.png` | `outputs/figures/paper_fig3_inter_modal_phase.pdf` |
| Figure 5 | `outputs/figures/paper_fig5_eta_rho_voting.png` | `outputs/figures/paper_fig5_eta_rho_voting.pdf` |
| Figure S1 | `outputs/figures/paper_figS1_coherence_stability.png` | `outputs/figures/paper_figS1_coherence_stability.pdf` |
| 诊断数据 | `outputs/reports/paper_figures_diagnostics.npy` | — |

### 4.2 关键数值（来自实际运行）

| 图 | 指标 | 数值 |
|----|------|------|
| Fig 2 | 选中 tones / Δφ | 58(0), 48(−0.09), 45(3.10), 69(−0.83)；γ≈1.00/0.83/0.93/0.95 |
| Fig 3 | 跨窗数 | cs_095806: 42；cs_102621: 41（segment 1b） |
| Fig 5 | BPM Voting / Uniform | 8.00 / 8.86 |
| Fig S1 | tone pair (58,69) γ | good 0.901±0.075；hard 0.485±0.345（同 segment `1b`） |

### 4.3 与 plan 预期对比

| 预期（Plan §2） | 实际 | 是否一致 |
|-----------------|------|----------|
| (a) raw 可见同相/反相；(b) ±1 部分对齐；(c) Hilbert 近重合 | 目视成立：tone 45 经 sign flip 后改善，Hilbert 后四线重合 | ✅ |
| (d) good/hard 热力图对比 | good 左上高 γ 结构更密；hard 更碎 | ✅ |
| Fig 3 对齐前后 + 跨窗 Δφ 浮动 + 跨房间不同 | (a)(b) 对齐清晰；(c)(d) Δφ 跨窗非固定且基线不同 | ✅ |
| Fig 5 Voting 谱更尖 / 高质量 tone 右上 | Voting 峰更高更尖；Uniform/Voting BPM 有差异 | ✅ |
| Fig S1 good 稳定高、hard 波动 | μ 0.90 vs 0.49，hard std 更大 | ✅ |

### 4.4 现象与图

#### Figure 2 — Inter-tone phase relationship

中间相位 tone（Δφ≈−0.83）在 ±1 校正后仍有残余错位，Hilbert 后消除——支撑连续相位必要性。

![Figure 2: Inter-tone phase relationship](../../outputs/figures/paper_fig2_inter_tone_phase.png)

- PNG: `outputs/figures/paper_fig2_inter_tone_phase.png`
- PDF: `outputs/figures/paper_fig2_inter_tone_phase.pdf`

#### Figure 3 — Inter-modal phase alignment

模态间 Δφ 跨窗跳跃，且两房间轨迹不同——支撑 per-window 估计，而非固定相位先验。

![Figure 3: Inter-modal phase relationship](../../outputs/figures/paper_fig3_inter_modal_phase.png)

- PNG: `outputs/figures/paper_fig3_inter_modal_phase.png`
- PDF: `outputs/figures/paper_fig3_inter_modal_phase.pdf`

#### Figure 5 — η·ρ quality voting

低 ρ tone 的 |BPM−voted| 偏大（暖色）；Voting 谱噪声底更低。

![Figure 5: η·ρ quality voting](../../outputs/figures/paper_fig5_eta_rho_voting.png)

- PNG: `outputs/figures/paper_fig5_eta_rho_voting.png`
- PDF: `outputs/figures/paper_fig5_eta_rho_voting.pdf`

#### Figure S1 — Coherence stability

同 tone index 对在 hard 场景 γ 均值更低、波动更大。

![Figure S1: Tone-pair coherence stability](../../outputs/figures/paper_figS1_coherence_stability.png)

- PNG: `outputs/figures/paper_figS1_coherence_stability.png`
- PDF: `outputs/figures/paper_figS1_coherence_stability.pdf`

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| Tone 间需连续相位对齐（Hilbert > ±1 sign） | **已验证**（机制图，代表窗） |
| 模态间相位跨窗非固定、房间依赖 | **已验证**（两场景 segment 全窗） |
| η·ρ Voting 相对 Uniform 谱更干净 | **仅单场景**（cs_095806 代表窗） |
| Tone-pair γ 在 hard 场景更不稳定 | **已验证**（两场景同 pair / 同 seg） |

**相对 baseline**：本任务不产生部署推荐；机制对比支持论文叙述中的 Hilbert 两级对齐与 η·ρ 投票动机。

**部署建议**：无（配图任务）。

---

## 6. 开放问题与下一步

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | 代表窗/tone 为自动启发式选择，论文定稿是否改手选更“教科书”的窗 | Review 后可固定 window/tone 列表重绘 |
| Q2 | Fig 2 hard 热力图有效 tone 数似少于 72（边缘暗带） | 检查 hard 场景部分 tone 窗内有效长度 / NaN |
| Q3 | 论文最终美术风格未统一 | 按期刊模板重绘；本轮保证数值关系正确 |

---

## 7. 复现

```bash
python notebooks/scripts/chFusion_paper_figures_mechanism.py
# 调试加速：
python notebooks/scripts/chFusion_paper_figures_mechanism.py --max-windows 40
```

| 产出 | 路径 |
|------|------|
| 数值报告 | `outputs/reports/paper_figures_diagnostics.npy` |
| 图表 PNG | `outputs/figures/paper_fig{2,3,5,S1}_*.png` |
| 图表 PDF | `outputs/figures/paper_fig{2,3,5,S1}_*.pdf` |
| 本报告 | `docs/reports/paper_figures_generation_report.md` |

---

## 8. Plan 回填（执行 Agent 更新 plan 末尾）

- **验证状态**：已完成
- **实际脚本**：`notebooks/scripts/chFusion_paper_figures_mechanism.py`
- **结论一句话**：四张机制图均已从缓存数据生成；Hilbert 对齐、跨窗模态相位浮动、η·ρ 投票与 hard 场景 γ 退化均在图中可见。
