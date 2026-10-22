# 论文第六章表格转图示 — 验证报告

> **Plan**：[`docs/plans/paper_ch6_tables_to_figures_plan.md`](../plans/paper_ch6_tables_to_figures_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_paper_figure_redraw.py`、`notebooks/scripts/chFusion_paper_ablation_draft.py`（命名常量：`src/ble_analysis/paper_naming.py`）  
> **场景**：HKH 12 条记录（`room_{A,B,C}-sbj_{A–D}-*`）。本轮不重跑场景，不读取 `config/scenarios/cs_*.json`。  
> **日期**：2026-10-22  
> **状态**：已完成

---

## 1. 目标与假设

把第六章主结果和消融从「表格为主」改成与 skeleton 定稿一致的图：BreatheCS 使用端侧幅值 R+L（`draft_s_rl` / `draft_w_rl`），误差线为 12 场景总体标准差 `np.std(ddof=0)`，图内不放标题、星标或「★ BreatheCS」文字。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 五张图的 mean / std 与 skeleton 表 6.3-A、6.3-B、6.4、8-A、8-B 的三位小数一致 | §4 |
| H2 | 图内没有标题、题注、星标；BreatheCS 仅以红色分组区分 | §5、§8-B |
| H3 | 不重跑实验，不改写 `ble_hkh_draft_ablation_summary.json` | §10 |

---

## 2. 方法摘要

只改绘图。数值从已有 JSON 读取。

| 项目 | 内容 |
|------|------|
| 观测量 | 不新处理。图中的 BreatheCS 对应已有 R+L 结果：谱分支 `draft_s_rl`，波形分支 `draft_w_rl` |
| 信道 / 模态融合 | 不改算法。Fig 8 的 BreatheCS 柱从三模态 `draft_*_full` 改为 `draft_s_rl` / `draft_w_rl` |
| 滑窗与寻峰 | 不涉及 |
| std | 优先对 per-scenario 序列做 `np.std(ddof=0)`。Fig 8 的 RMSE 从 12 个 `ble_hkh_draft_ablation_{sid}.json` 的 `rmse_mean` 重算，不用 summary 里的 ddof=1 |

Fig 6a / 6b 的八个方法：BreatheCS、BreatheCS-Wave、Pos-Free (PCA)、WiFi-Sleep (MRC-PCA)、WiFi-Sleep (√η)、PCA sign only、ClessBreath (η-linear)、ClessBreath (η-equal)。

Fig 6.4 七个方法，只保留一行 BreatheCS（波形 RMSE = `draft_w_rl`），不另列 BreatheCS-Wave。

---

## 3. 实验设置

- **Baseline**：图中的外部方法沿用已有 HKH 汇总，不改定义。Pos-Free (PCA)、WiFi-Sleep (MRC-PCA / √η)、ClessBreath (η-linear / η-equal)、PCA sign only。
- **待测方法**：BreatheCS = `draft_s_rl`（BPM）与 `draft_w_rl`（波形 BPM / RMSE）。
- **指标**：12 场景 mean BPM absolute error、波形 RMSE，以及跨场景 `std(ddof=0)`。Fig 6b 为每房间 4 名受试者的 mean ± std(ddof=0)。
- **未做**：不重跑 HKH，不改 Fig 7。

---

## 4. 结果

数字来自 `outputs/reports/paper_ch6_tables_to_figures_results.json`。下表为脚本打印的三位小数，与 plan §4 一致。

### 4.1 主结果表

Fig 6a · 12 场景 BPM abs err，升序，`std(ddof=0)`：

| 方法 | mean | std |
|------|-----:|----:|
| BreatheCS (`draft_s_rl`) | 0.371 | 0.128 |
| BreatheCS-Wave (`draft_w_rl`) | 0.385 | 0.113 |
| Pos-Free (PCA) | 0.435 | 0.123 |
| WiFi-Sleep (MRC-PCA) | 0.505 | 0.149 |
| WiFi-Sleep (√η) | 1.023 | 1.257 |
| PCA sign only | 1.317 | 0.646 |
| ClessBreath (η-linear) | 1.386 | 1.685 |
| ClessBreath (η-equal) | 1.486 | 1.527 |

Fig 6.4 · 波形 RMSE：

| 方法 | mean | std |
|------|-----:|----:|
| BreatheCS (`draft_w_rl`) | 0.937 | 0.201 |
| ClessBreath (η-linear) | 1.025 | 0.231 |
| ClessBreath (η-equal) | 1.046 | 0.202 |
| WiFi-Sleep (√η) | 1.054 | 0.228 |
| WiFi-Sleep (MRC-PCA) | 1.063 | 0.234 |
| Pos-Free (PCA) | 1.070 | 0.239 |
| PCA sign only | 1.085 | 0.174 |

Fig 8a–c · 融合层级（mean (std)）：

| Fusion level | Spec BPM | Wave BPM | Wave RMSE |
|---|---:|---:|---:|
| No fusion | 1.640 (0.464) | 1.192 (1.137) | 1.007 (0.180) |
| Channel only | 0.381 (0.116) | 1.003 (1.193) | 0.962 (0.195) |
| Modal only | 0.655 (0.245) | 1.025 (0.988) | 0.986 (0.178) |
| BreatheCS | 0.371 (0.128) | 0.385 (0.113) | 0.937 (0.201) |

Fig 8d–f · 单模态：

| Domain | Remote | Local | Phase | BreatheCS |
|---|---:|---:|---:|---:|
| Spectral BPM | 0.376 (0.115) | 0.378 (0.119) | 2.191 (1.302) | 0.371 (0.128) |
| Waveform BPM | 0.399 (0.121) | 0.439 (0.217) | 2.395 (1.169) | 0.385 (0.113) |
| Waveform RMSE | 0.931 (0.207) | 0.947 (0.214) | 1.109 (0.111) | 0.937 (0.201) |

Fig 6b 的房间 mean / std 直接来自 `paper_table63b_per_room_std.json` 的 `methods.*.per_room`，与 skeleton 表 6.3-B 同一文件，未另算一套数。

### 4.2 与 plan 预期对比

| 预期（Plan §4） | 实际 | 是否一致 |
|-----------------|------|----------|
| BreatheCS BPM 0.371 ± 0.128，Wave 0.385 ± 0.113 | 同左 | ✅ |
| Fig 6.4 BreatheCS RMSE 0.937 ± 0.201，且不另列 Wave 行 | 同左 | ✅ |
| Fig 8 BreatheCS 用 `draft_s_rl` / `draft_w_rl`，不用 `draft_*_full` | 图与结果 JSON 的 key 均为 rl | ✅ |
| 去掉 Fig 6a 星标和红色「★ BreatheCS」 | 已去掉 | ✅ |
| Fig 6b、Fig 8 加 std 误差线 | 已加；后续改为黑色误差线。Fig 8 改为与 Fig 6b 相同的分组整图，不再分子图 | ✅ |
| 图内不画长标题 | 只保留轴标签和图例。Fig 8 不再标 (a)–(f) | ✅ |
| Fig 7 搁置 | 未重绘 | ✅ |

### 4.3 现象与图

- BreatheCS 的图上数值已从旧三模态（BPM 0.405 / Wave BPM 0.744）换成 R+L。
- 误差线在 ClessBreath 与 Phase 上很长，横轴因此拉宽；这是 std，不是把均值画错。
- 图：
  - `outputs/figures/paper_fig6a_bpm_leaderboard.png`
  - `outputs/figures/paper_fig6b_bpm_by_room.png`
  - `outputs/figures/paper_fig6_4_rmse_leaderboard.png`
  - `outputs/figures/paper_fig8_abc_fusion.png`
  - `outputs/figures/paper_fig8_def_single_modal.png`
  - 以上均有同名 `.pdf`
- 正文以箱线图为准，文件名带 `_box`。每箱是 12 个场景的绝对误差或 RMSE（Fig 6b 为每个房间 4 名受试者）。箱内黑线是中位数，黑点是均值，须为 1.5 IQR。同名不带 `_box` 的条形图仍保留，不再作为正文图。

### 4.4 题注（写入正文，不画在图上）

**Fig. 6a — BPM accuracy across all 12 HKH recordings.** Box plots of BPM absolute error (breaths/min). Each box is the 12 recordings of one method. The line inside the box is the median, and the black dot is the mean. BreatheCS has the lowest mean (0.371). Pos-Free (PCA) and WiFi-Sleep (MRC-PCA) follow around 0.44–0.51. The ClessBreath variants are about 1.39–1.49 and spread more widely.

**Fig. 6b — BPM accuracy by room.** Same methods as Fig. 6a, split into Living sitting, Bedroom flat, and Bedroom side. Each box is the four subjects in that room. The line is the median and the black dot is the mean. BreatheCS has the lowest mean in all three rooms. The ClessBreath variants spread widely across subjects.

**Fig. 6.4 — Waveform recovery RMSE across 12 HKH recordings.** Box plots of waveform RMSE against the belt. Each box is the 12 recordings of one method. Before RMSE, each trace is z-scored and sign-aligned, so the value compares shape. The line inside the box is the median, and the black dot is the mean. BreatheCS has the lowest mean (0.937). WiFi-Sleep and Pos-Free cluster around 1.05–1.07.

**Fig. 8 — Fusion-level ablation.** Grouped box plots. Each box is the 12 recordings. Left axis: spectral and waveform RR absolute error (BPM). Right axis: waveform RMSE. The line inside a box is the median, and the black dot is the mean. Methods: no fusion / channel only / modal only / BreatheCS. Channel-level fusion accounts for most of the mean BPM drop (1.640→0.381).

**Fig. 8 — Single-modal ablation.** Grouped box plots with the same axes as the fusion figure. Each box is the 12 recordings. Methods: Remote / Local / Phase / BreatheCS. Remote and Local means stay close to BreatheCS. Composite Phase is much higher (about 2.2–2.4 BPM).

表内数字仍是 12 场景均值和总体 std。箱线图展示的是各场景的分布，黑点对应表中的均值。

同一段题注已写入 `docs/paper_draft/paper_draft_skeleton.md` §6.3–§6.4，并同步到 `docs/paper_draft/latex.md`。

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| 五张图与 skeleton 定稿数值一致，std 为 ddof=0 | **已验证** |
| 图内星标和长标题已去掉 | **已验证** |
| Fig 7 是否改成别的 trade-off 图 | **未证实**（按确认搁置） |

**相对 baseline**：本轮没有新的算法比较。图上仍是 BreatheCS 的 12 场景 BPM / RMSE 低于所绘外部方法。这是既有结果的重绘，不是新实验。

### 已验证

- Fig 6a、6b、6.4、8a–c、8d–f 的 mean 与 `std(ddof=0)` 与 plan §4 的三位小数一致。
- BreatheCS 图柱使用 `draft_s_rl` / `draft_w_rl`，没有使用三模态 `draft_s_full` / `draft_w_full`。

### 仅单场景

- 无。图都是 12 场景或按房间（每房间 4 人）汇总。

### 未证实

- Fig 7 散点未重绘，也不在本轮结论里。

### 已废弃

- 无新的方法废弃。绘图不再把三模态等权结果标成 BreatheCS；该决定来自既有 skeleton，不是本轮新结论。

---

## 6. 开放问题与下一步

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | `docs/paper_draft/latex.md` 里 BreatheCS-Wave 仍是 0.385 ± 0.118 | skeleton 已是 0.113。若 LaTeX 正文要同步，交给 Research / 写作侧，本轮按 plan 只改了 skeleton 图注 |
| Q2 | Fig 7 仍是旧散点 | 保持搁置，直到有新的 plan |

---

## 7. 复现

```bash
python notebooks/scripts/chFusion_paper_figure_redraw.py
python notebooks/scripts/chFusion_paper_ablation_draft.py --figures-only
```

第二条只读已有 JSON 并重绘 Fig 8，不重跑 12 个场景，不改写 `ble_hkh_draft_ablation_summary.json`。不要去掉 `--figures-only`，否则会重跑消融并覆写 summary。

| 产出 | 路径 |
|------|------|
| 数值 | `outputs/reports/paper_ch6_tables_to_figures_results.json` |
| RMSE 表片段 | `outputs/reports/paper_fig6_4_rmse_table.md` |
| 单模态表片段 | `outputs/reports/paper_fig8_single_modal_table.md` |
| 图表 | `outputs/figures/paper_fig6a_bpm_leaderboard.png/.pdf`、`paper_fig6b_bpm_by_room.png/.pdf`、`paper_fig6_4_rmse_leaderboard.png/.pdf`、`paper_fig8_abc_fusion.png/.pdf`、`paper_fig8_def_single_modal.png/.pdf` |
| 本报告 | `docs/reports/paper_ch6_tables_to_figures_report.md` |

---

## 8. Plan 回填（执行 Agent 更新 plan 末尾）

- **验证状态**：已完成
- **实际脚本**：`notebooks/scripts/chFusion_paper_figure_redraw.py`、`notebooks/scripts/chFusion_paper_ablation_draft.py --figures-only`
- **结论一句话**：五张图已按 R+L 与 ddof=0 重绘，三位小数与 skeleton 一致；Fig 7 未改。

## Self Check

- Plan read: yes
- Baseline confirmed: yes（沿用已有外部方法，未改定义）
- Scenario JSON used: no（本 plan 明确不重跑实验；数据来自已有 HKH JSON）
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes
- Hardcoded frame index risk: no
- Baseline changed: no
- Metric definition changed: no（std 口径按已定稿的 ddof=0 绘图，未改指标定义）
- Ready to commit: yes（未执行 commit）
