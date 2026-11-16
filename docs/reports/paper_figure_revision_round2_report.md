# 论文插图修订 Round 2 — 验证报告

> **Plan**：[`docs/plans/paper_figure_revision_round2_plan.md`](../plans/paper_figure_revision_round2_plan.md)
> **脚本**：`notebooks/scripts/chFusion_position_sweep_observation.py`、`notebooks/scripts/chFusion_paper_figures_mechanism.py`、`notebooks/scripts/chFusion_modal_oracle_diag.py`
> **场景**：本轮不估计 BPM，不读 `config/scenarios/cs_*.json` 做新实验。图 4/6/8 来自既有金属板/人体 position-sweep 段；图 2/9/10 来自 `cs_095806` 与 `cs_102621` 的既有机制图流程；图 17 只读 `outputs/reports/modal_oracle_per_window.npy` 的 HKH 行。
> **日期**：2026-11-15
> **状态**：已完成（图 17 正稿文件待作者择优；图 5 题注与模态对配色观感待作者确认）

---

## 1. 目标与假设

本轮只改示意/观察图的配色和版式，不改算法、指标或原始数据。成功标准是 plan §5 的 6 条验收。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 蓝/红/紫只留给 remote/local/phase | §3.1、§5.1 |
| H2 | 图 6 固定为信道 13/64/71，且 Hilbert 相位检查能确认同相+反相 | §3.2、R1 |
| H3 | 图 8 改为单子图散点，颜色=模态对，marker=信道 | §3.3 |
| H4 | 图 17 可复现地给出三种候选，图内不再写 oracle-best | §3.6 |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | 图中仍使用既有 `remote_amplitudes` / `local_amplitudes` / `phases`。未引入总幅值。 |
| 信道融合 | 未改。 |
| 模态融合 | 未改。 |
| 滑窗与寻峰 | 未改。图 17 直接读已有窗级 η 与 `best_modal`。 |

配色（全篇这一轮采用的色表）：

| 语义 | 系列 | 色值 |
|------|------|------|
| 单模态 | remote / local / phase | `#1f77b4` / `#d62728` / `#9467bd` |
| 模态对 | R-L / R-P / L-P | `#ff7f0e` / `#17becf` / `#8c564b` |
| 信道 | tone 序列 | `#ff7f0e`, `#17becf`, `#2ca02c`, `#8c564b`, `#bcbd22`, `#7f7f7f` |
| 域 | metal / human | `#9e9e9e` / `#e07a3d` |

同相/反相判据与 `_select_representative_tones` 相同，来自 `estimate_phase_hilbert`：相干 > 0.7 且 `|φ| < 0.35` 为同相；相干 > 0.7 且 `||φ| − π| < 0.35` 为反相。不满足「同时有同相和反相」时不写图 6、不换信道。

---

## 3. 实验设置

- **Baseline**：无新 BPM baseline。对照物是改图前的正稿 PDF。
- **待测方法**：不适用。
- **指标**：图 6 的相位/相干；图 17 的 η 排名占比与 GT-optimal 占比。η/ρ 定义未改。

图 5（E3）口径，供题注使用，数据未改：每个模态在整段（非滑窗）上按 72 信道分别算 η、ρ，再对信道取平均。η 用高通波形，ρ 用带通波形（`per_channel_eta_rho`）。

---

## 4. 结果

### 4.1 图 6 相位检查（hard remote，seg14）

`ref_idx = 71`。

| 信道 | phase (rad) | coherence | 类别 |
|------|------------:|----------:|------|
| 13 | −3.1305 | 0.9735 | anti-phase |
| 64 | −0.0004 | 0.9986 | in-phase |
| 71 | 0.0000 | 1.0000 | in-phase（参考信道） |

集合里同时有同相和反相，图已写出。ch13 与 ch64/ch71 在图上反相，和这张表一致。

### 4.2 图 17（HKH，n = 1730 个有限 η 窗）

| 统计 | 值 |
|------|---:|
| remote η 排名第 1 | 70.23% |
| local η 排名第 1 | 24.28% |
| phase η 排名第 1 | 5.49% |
| `r = η_phase / max(η_remote, η_local) > 1` | 5.49%（`r ≤ 0` 丢弃 0 窗） |
| phase 为 GT-optimal modal | 6.07% |
| amplitude η 排名第 1 | 94.51% |
| amplitude 为 GT-optimal | 93.93% |

v4 把 remote 与 local 合成 amplitude：每个窗取 `η_amplitude = max(η_remote, η_local)`，再和 composite phase 比较。无并列窗。GT-optimal amplitude 指 `best_modal` 为 remote 或 local。

GT-optimal modal：相对 ground truth，BPM 误差最低的那个模态。它和「η 排名第 1」不是同一个量。

图 17 的四张候选图内没有大标题，也没有底部题注。下面的句子供直接放进论文题注：

- v1：HKH 上 remote、local、composite phase 的 η 分布。phase 的 η 高于 max(remote, local) 的窗占 5.5%；phase 为 GT-optimal modal 的窗占 6.1%。GT-optimal modal 指相对 ground truth 的 BPM 误差最低的模态。
- v2：HKH 上 `r = η_phase / max(η_remote, η_local)` 的分布。`r > 1` 的窗占 5.5%。竖线为 `r = 1`。
- v3：左为各模态 η 排名第 1 的窗占比（remote 70.2%，local 24.3%，phase 5.5%）；右为三模态 η 分布。
- v4：amplitude 与 composite phase 的比较。每个窗的 amplitude η 取 max(η_remote, η_local)。η 更高的窗中 amplitude 占 94.5%，composite phase 占 5.5%。GT-optimal 为 amplitude 的窗占 93.9%，为 composite phase 的窗占 6.1%。

未覆盖正稿 `phase_oracle_eta.pdf` / `paper_fig_modal_oracle_phase_eta_hkh.*`。

### 4.3 与 plan 预期对比

| 预期 | 实际 | 是否一致 |
|------|------|----------|
| 图 4 保持 3×3 波形，信道色去掉蓝/红/紫 | B2 仍是 3×3；ch20/40/60 为橙/青/绿 | ✅ |
| 图 6 仅 13/64/71 | 已打印相位并落图 | ✅ |
| 图 8 单子图、纯散点、双图例 | 图例放在图内左上角，画布宽 8 in | ✅ |
| 图 9 模态对橙/青/棕 | `paper_fig3_cd` | ✅ |
| 图 10 单模态蓝/红/紫 | `paper_fig3_ab` | ✅ |
| fig2 信道色去掉蓝/红 | 橙/青/绿/棕 | ✅ |
| 图 17 三候选，无 oracle-best | 三套 PNG+PDF | ✅ |
| 不改 `modal_oracle_per_window.npy` | 未写该文件 | ✅ |

### 4.4 图

正稿对应（作者编号）：

- 图 4：`outputs/figures/position_sweep_figB2_channel_position_matrix.png`
- 图 6：`outputs/figures/position_sweep_figC1_hard_remote.png`
- 图 8：`outputs/figures/position_sweep_figD2_dphi_vs_position_ch20_40_60.png`
- 图 9：`outputs/figures/paper_fig3_cd.png`
- 图 10：`outputs/figures/paper_fig3_ab.png`
- fig2：`outputs/figures/paper_fig2_inter_tone_phase.png`
- 图 17 v1/v2/v3：`outputs/figures/paper_fig_modal_oracle_phase_eta_hkh_v1_modal_dist.png`、`..._v2_ratio_hist.png`、`..._v3_share_bar.png`
- 图 17 v4（amplitude vs composite phase）：`outputs/figures/paper_fig_modal_oracle_phase_eta_hkh_v4_amp_vs_phase.png`

图 8 上，R-L 大多贴在 0 附近，R-P / L-P 在 0 与 ±π 上叠在一起。这是数据本身靠在一起，不是画错坐标。双图例已分开。

---

## 5. 结论

### 已验证

- 指定的正稿图已按色表重绘，蓝/红/紫只出现在单模态序列上。
- 图 6 的 13/64/71 通过 Hilbert 相位检查：13 反相，64 与参考信道 71 同相。
- 图 17 三种候选可由 `plot_oracle_phase_eta_single` 复现。

### 仅单场景

- 图 6 的相位检查只针对 hard remote 这一段（seg14），不能外推到其他位置或其他模态。
- 图 17 的占比只来自 HKH 的 1730 个窗。

### 未证实

- 模态对三色（橙/青/棕）作者是否接受（plan Q2）。
- 图 17 三种形式哪一张进入正稿。

### 已废弃

- 无。

**相对 baseline**：本轮没有 BPM 方法对比。

---

## 6. 开放问题与下一步

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | 图 5 题注是否写成 channel-averaged | 见下方建议措辞。未改 tex。`[待确认]` |
| Q2 | 模态对橙/青/棕是否可接受 | 看 `paper_fig3_cd` 与图 8。`[待确认]` |
| Q3 | 图 17 选哪一版覆盖正稿 | 选定后再覆盖 `figs/phase_oracle_eta.pdf`。本轮未覆盖。 |

### 图 5 题注建议（不改 tex）

当前 `sections/model.tex` 中 `fig:eta_rho_compare` 的题注是：

> Comparison of η and spectral peak prominence ρ between metal-plate and human respiration.

建议改为：

> Channel-averaged η and spectral peak prominence ρ for metal-plate motion and human respiration. For each modality, both statistics are computed on each of the 72 tones over the full segment, not a sliding window, and then averaged across tones. η uses the high-pass waveform; ρ uses the band-pass waveform.

### 图 5 字号位置（作者自查）

`chFusion_position_sweep_observation.py`：

- `STYLE["fontsize"] = 16`（约 L117），E3 两个 y 轴用这个字号（约 L1249–L1250）
- x 刻度 `fontsize=14`（约 L1248）
- 图例 `fontsize=14`（约 L1253）
- E3 没有 `set_title`
- 当前正稿主文件是 `wang26breathecs.tex`，里面没有 `\captionsetup{font=small}`。plan 里写的 `wang26csdf.tex` 已不在该目录。

### 已改 / 未改

已改并复制进正稿 `paper_sj_ble_sensing/figs/`（tex 用的是短文件名，不是脚本 stem）：

| 正稿 PDF | 来源 |
|----------|------|
| `diff_apearence_on_diff_channel.pdf` | 图 4 B2 |
| `phase_on_diff_channel.pdf` | 图 6 |
| `phase_diff_in_diff_position.pdf` | 图 8 |
| `inter_tone.pdf` | fig2 |
| `modal_with_hilbert_fusion.pdf` | 图 10 |
| `modal_phase_diff_in_two_room.pdf` | 图 9 |

未覆盖正稿：

- `eta_rho_compare.pdf`（图 5，数据和柱色未改）
- `phase_oracle_eta.pdf`（图 17，等作者择优）

顺带重导出、但不是本轮正稿目标的文件：B1、其余 C1 三面板（选道逻辑未改，只跟着信道色表变色）、D1、单信道 D2 折线（折线结构还在，模态对颜色换成了新三色）、E1 金属曲线灰值改为 `#9e9e9e`。`chFusion_paper_figures_mechanism.py` 按原逻辑重写了 `outputs/reports/paper_figures_diagnostics.npy`，没有改算法。诊断图 `plot_oracle_figures` 的模态色和 “oracle-best” 用词已在代码里改成 GT-optimal，本轮没有用 `--plot-only` 重导出那些诊断图。

`latexmk -pdf wang26breathecs.tex` 通过，输出 13 页 PDF，无缺图错误。

---

## 7. 复现

```bash
python notebooks/scripts/chFusion_position_sweep_observation.py --only C,D,B,E
python notebooks/scripts/chFusion_paper_figures_mechanism.py --only 2,3
python notebooks/scripts/chFusion_modal_oracle_diag.py --oracle-single
```

图 8 与图 17 的最终版在上述命令之后又单独重跑了 `--only D` 和 `--oracle-single`，只调整图例/说明文字位置。

| 产出 | 路径 |
|------|------|
| 图表 | `outputs/figures/` 下 §4.4 所列 PNG+PDF |
| 本报告 | `docs/reports/paper_figure_revision_round2_report.md` |
| 未改数据 | `outputs/reports/modal_oracle_per_window.npy` |

---

## 8. Plan 回填（执行 Agent 更新 plan 末尾）

- **验证状态**：已完成
- **实际脚本**：上述三个脚本
- **结论一句话**：配色和图 6/8/17 的版式已按 plan 落地；图 17 正稿文件和图 5 题注留给作者选定。
