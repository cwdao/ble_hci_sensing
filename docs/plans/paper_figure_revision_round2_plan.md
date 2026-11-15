# 论文插图修订 Round 2 — 实现计划

> **来源**：审稿/导师修改意见 + 作者逐图改图清单（2026-11-15）
> **目标报告**：`docs/reports/paper_figure_revision_round2_report.md`
> **建议 plan 路径**：`docs/plans/paper_figure_revision_round2_plan.md`
> **日期**：2026-11-15
> **验证状态**：已完成

---

## 1. 动机与背景

论文正稿插图收到修改意见，本轮目标是把若干**示意/观察类图**改到更清晰、语义更准确，并**统一全篇配色**。本轮**只改图、不改算法、不改数据、不改指标定义**。

涉及改动范围（按源文件名索引，作者用「图 N」指代正稿编号，映射关系见 §2）：

| 正稿编号 | 源文件 | 改动性质 |
|----------|--------|----------|
| 图4 | `position_sweep_figB2_channel_position_matrix` | 保持波形矩阵，**不改结构**（仅配色对齐） |
| 图5 | `position_sweep_figE3_eta_rho_comparison` | 确认指标口径 + 记录字号位置（作者自查） |
| 图6 | `position_sweep_figC1_hard_remote` | 8 信道 → 3 信道（13/64/71） |
| 图8 | `position_sweep_figD2_dphi_vs_position_ch20_40_60` | 折线→散点，3 子图→1 子图，信道=marker |
| 图9 | `paper_fig3_cd` | 不改结构，配色改为「模态对」专用色 |
| 图10 | `paper_fig3_ab` | 不改结构，配色改为「单模态」红蓝紫 |
| 图17 | `paper_fig_modal_oracle_phase_eta_hkh` | 重绘 3 种候选形式 + 术语规范化 |
| — | `paper_fig2_inter_tone_phase` | 配色对齐（信道专用色） |

作者已拍板的 4 项决策：

1. **图4**：保留 3×3 时域波形矩阵，不做 heatmap。
2. **图17**：三模态 η 分布叠加 / 比值直方图 / 占比条形+分布 三种形式**都生成**，由作者择优。
3. **横轴**：图8（距离）/ 图9（窗序号）/ 图10（时间）**不统一**，只强化轴标签与图注区分。
4. **配色**：单模态固定红/蓝/紫；模态对（R-L/R-P/L-P）另用一组三色，避免语义冲突。

---

## 2. 物理与变量（本轮不涉算法，仅说明语义轴）

这些图都是**观察性证据图**，不改动任何信号处理管线。图中涉及的「语义轴」决定配色，必须区分：

| 语义轴 | 含义 | 本轮配色归属 |
|--------|------|--------------|
| 单模态 | remote_amplitudes / local_amplitudes / phases 各自一条序列 | **模态专用色**（§3.2） |
| 模态对 | Δφ(R,L) / Δφ(R,P) / Δφ(L,P) 两模态之间的相位差 | **模态对专用色**（§3.2） |
| 信道（tone） | 72 tone 中的某一条 | **信道专用色**（§3.2） |
| 域（金属 vs 人） | Metal plate / Human 两类对照 | **域专用色**（§3.2） |

物理背景（不重述，仅作约束）：remote/local 物理对等；`phases` 是两端 PCT 向量相乘后的总相位；`amplitudes`（总幅值）无独立物理意义，本轮不涉及。**本轮图 6/8 中「同相/反相信道」的判据来自 `estimate_phase_hilbert` 的相位估计，执行时需打印确认，不得凭经验硬写。**

---

## 3. 修改步骤

### 3.0 总流程图

```text
现有生成脚本（3 个）＋ modal_oracle_per_window.npy
  │
  ├─► [脚本1] chFusion_position_sweep_observation.py
  │      ├─ plot_fig_b  (图4 B2)      → 不改结构，仅信道配色对齐
  │      ├─ plot_fig_c  (图6 C1 hard) → 8→3 信道 [13,64,71]
  │      ├─ plot_fig_d  (图8 D2)      → 散点+单子图+marker=信道+对色
  │      └─ plot_fig_e  (图5 E3)      → 只确认指标/记录字号，不改数据
  │
  ├─► [脚本2] chFusion_paper_figures_mechanism.py
  │      ├─ generate_fig2 (fig2)      → 信道专用色（去蓝/红/紫）
  │      ├─ generate_fig3 (fig3_ab)   → 单模态红蓝紫
  │      └─ generate_fig3 (fig3_cd)   → 模态对专用三色
  │
  └─► [脚本3] chFusion_modal_oracle_diag.py（新增可复现单面板函数）
         └─ 读 outputs/reports/modal_oracle_per_window.npy(HKH)
              → 生成 图17 三候选 + 术语改「GT-optimal modal」
  │
  ▼
重跑对应脚本 → 输出 PNG+PDF → 复制到 paper_sj_ble_sensing/figs/ → 编译核对
```

### 3.1 统一配色规范（全篇唯一事实来源，§3 其余任务都遵守）

**不变量**：`#1f77b4`（蓝）、`#d62728`（红）、`#9467bd`（紫）**只**用于三种模态；任何信道/模态对/域的序列**不得**再使用这三个色。

| 语义轴 | 具体系列 | 目标色 |
|--------|----------|--------|
| 模态 | remote | `#1f77b4`（蓝） |
| 模态 | local | `#d62728`（红） |
| 模态 | phase | `#9467bd`（紫） |
| 模态对 | R-L | `#ff7f0e`（橙） |
| 模态对 | R-P | `#17becf`（青） |
| 模态对 | L-P | `#8c564b`（棕） |
| 信道 | tone 系列 | 定性集 `["#ff7f0e","#17becf","#2ca02c","#8c564b","#bcbd22","#7f7f7f"]`（不含蓝/红/紫） |
| 域 | metal / human | metal=`#9e9e9e`（灰），human=`#e07a3d`（橙） |

> 注：具体 hex 可微调以兼顾色盲友好，但**必须全篇一致**，最终色表在报告 §6 回填。信道色与模态对色允许在不同图之间复用（不会同图出现），只要不与模态三色冲突。

**受影响的现有配色定义（必须改）**：

| 文件 | 位置 | 现状 | 改为 |
|------|------|------|------|
| `chFusion_position_sweep_observation.py` | `MODAL_COLORS`（约 L94-98） | local=绿 `#2ca02c`、phase=红 `#d62728` | local=红 `#d62728`、phase=紫 `#9467bd` |
| 同上 | `plot_fig_d` `pair_colors`（约 L870） | `["#1f77b4","#ff7f0e","#2ca02c"]` | `["#ff7f0e","#17becf","#8c564b"]` |
| 同上 | `plot_fig_c`/`plot_fig_b` `CHANNEL_COLORS`（约 L110） | 含蓝/红/紫 | 替换为信道专用定性集 |
| `chFusion_paper_figures_mechanism.py` | `generate_fig3` `colors`（约 L595） | local=橙、phase=绿 | local=红、phase=紫 |
| 同上 | `generate_fig3` `pair_colors`（约 L597） | `["#1f77b4","#d62728","#9467bd"]` | `["#ff7f0e","#17becf","#8c564b"]` |
| 同上 | `generate_fig2` `colors`（约 L376） | 含 `#1f77b4`/`#d62728` | 信道专用定性集前 4 色 |
| `chFusion_modal_oracle_diag.py` | 模态色（约 L470/499/549） | 蓝/橙/绿 | 统一为蓝/红/紫 |

### 3.2 图6 — `position_sweep_figC1_hard_remote`：8→3 信道

**文件/函数**：`notebooks/scripts/chFusion_position_sweep_observation.py` → `plot_fig_c`，`hard + remote_amplitudes` 分支（约 L727-751）。

改动：

1. 把 `selected = _select_representative_tones(phases, coherences, eta, rho, ref, k=8)`（L729）替换为固定 `selected = [13, 64, 71]`（建议定义模块级常量 `C1_HARD_CHANNELS = [13, 64, 71]`）。
2. **先打印** `phases[ch]` 与 `coherences[ch]`（ch∈13,64,71），确认「13/64/71 确为同相 + 反相代表」再落图；若与预期不符，**停止并回报**，不要擅自换信道。
3. 垂直堆叠逻辑（`y = _zscore(X[ch]) + i*3.0`）不变，图例改为 `ch13/ch64/ch71`，配色用信道专用色。
4. 其余 C1 分支（good/remote、hard/local/phase 的三面板 PNG）**不动**。

产出：`outputs/figures/position_sweep_figC1_hard_remote.{png,pdf}`。

### 3.3 图8 — `position_sweep_figD2_dphi_vs_position_ch20_40_60`：散点 + 单子图

**文件/函数**：同上 → `plot_fig_d`，拼合面板段（约 L917-957）。

改动：

1. **合成单子图**：删除 `plt.subplots(3,1)`，改为单 `plt.subplots(figsize=(8,4.5))`。
2. **折线→散点**：`ax.plot(..., "o-")` 改为 `ax.scatter(xs, series[lab], marker=..., s=..., color=...)`（或 `ax.plot` 仅 `linestyle="none"`）。
3. **信道 = marker**：ch20=圆 `o`、ch40=方 `s`、ch60=星 `*`（具体形状可微调，但要可区分、与图例一致）。
4. **模态对 = 颜色**：沿用 §3.1 的模态对三色（橙/青/棕），对应 R-L / R-P / L-P。
5. **图例双维度**：颜色图例（模态对）+ marker 图例（信道）分开画（用 `Line2D` 手工构造），避免 9 条合并图例拥挤。
6. 横轴仍为 `Distance (cm)`，`set_xlim(101, 84)` 保留；纵轴 `Δφ (rad)`。**不**把 x 轴改成时间（作者已定不统一）。

产出：`outputs/figures/position_sweep_figD2_dphi_vs_position_ch20_40_60.{png,pdf}`。

> 单信道 D2 图（ch20/40/60 单图）本轮可不动；若顺带改，保持与拼合图一致即可。

### 3.4 图4 / 图5 — 结构不动

- **图4**（`plot_fig_b` B2 矩阵，约 L672-695）：**保持 3×3 时域波形矩阵**，不做 heatmap。仅把 `CHANNEL_COLORS` 对齐到 §3.1 信道专用色。
- **图5**（`plot_fig_e` E3，约 L1137-1184）：
  - **指标口径已确认**：η/ρ 是「**按模态分开、对 72 信道取平均**、整段（非滑窗）计算」的统计量；η 用高通信号、ρ 用带通信号。**不改数据**。
  - 若 LaTeX 题注未体现「channel-averaged」这一口径，执行 Agent 提出题注措辞建议（**只写建议，不改 tex**，由作者定）。
  - **字号位置（作者自查用，非执行任务）**：y 轴 `fontsize=STYLE["fontsize"]`（`STYLE` 定义 L114，当前 16；用在 L1173-1174）；x 刻度 L1172 `fontsize=14`；图例 L1177 `fontsize=14`。E3 无 `set_title`；LaTeX 题注在 `wang26csdf.tex` 的 `\captionsetup{font=small}`。

### 3.5 图9 / 图10 / fig2 — 仅配色

- **图10**（`paper_fig3_ab`，`generate_fig3` 约 L595/603-627）：`colors` 改为单模态红蓝紫（local→红、phase→紫），结构不动。
- **图9**（`paper_fig3_cd`，约 L597/658-670）：`pair_colors` 改为模态对三色（橙/青/棕），结构不动（横轴仍是 `Window index`）。
- **fig2**（`generate_fig2`，约 L376）：4 条 tone 波形改用信道专用色前 4 色，避免用蓝/红（与模态冲突）。

### 3.6 图17 — `paper_fig_modal_oracle_phase_eta_hkh`：三种候选 + 术语规范化

**现状**：单面板 HKH 图由一次性 `python -c` 生成，**未落脚本**（`docs/paper_figure_source_map.md` §3.3）。本轮要把它固化成可复现函数。

**文件**：`notebooks/scripts/chFusion_modal_oracle_diag.py`，新增函数（建议名 `plot_oracle_phase_eta_single(domain="hkh", form=...)`），并加 `--oracle-single` CLI 开关。

**数据**：`outputs/reports/modal_oracle_per_window.npy`，取 `domain=="hkh"`；用到的字段：`eta_remote / eta_local / eta_phase / best_modal`。

**三种候选形式（都生成）**：

1. **v1 三模态 η 分布叠加**：remote/local/phase 三条 η 直方图或密度曲线叠加（模态三色），标注「phase η > max(remote,local) 的窗占比 ≈ X%」。
2. **v2 比值直方图**：横轴 `r = η_phase / max(η_remote, η_local)`，对数轴，竖线标 `r=1`，标注 `r>1` 占比。
3. **v3 占比条形 + 分布并排**：左子图 = 「phase η 排名第 1 的窗占比」条形；右子图 = 三模态 η 分布。

**术语规范化**：所有标题/轴标签/图例里的 "oracle-best" 统一改为 **"GT-optimal modal"**（对 ground truth 最优模态）；首次出现处加一句定义。正文与图注（`paper_draft_skeleton.md`/`latex.md`）里的 "oracle-best" 由作者另行改，执行 Agent **只改图内文字**。

**产出**：
- `outputs/figures/paper_fig_modal_oracle_phase_eta_hkh_v1_modal_dist.{png,pdf}`
- `outputs/figures/paper_fig_modal_oracle_phase_eta_hkh_v2_ratio_hist.{png,pdf}`
- `outputs/figures/paper_fig_modal_oracle_phase_eta_hkh_v3_share_bar.{png,pdf}`

作者择优后，把胜出的一张另存为 `paper_fig_modal_oracle_phase_eta_hkh.{png,pdf}`（覆盖正稿文件）。**本轮先出三候选，不擅自覆盖正稿文件。**

---

## 4. 现状 vs 目标（对照）

| 图 | 现状 | 目标 |
|----|------|------|
| 图4 | 3×3 波形，信道色含蓝红紫 | 3×3 波形不变，信道色去蓝红紫 |
| 图5 | η/ρ 柱状（口径需说明） | 不动；补题注口径建议 |
| 图6 | 8 信道垂直堆叠 | 3 信道（13/64/71）垂直堆叠 |
| 图8 | 3 子图、折线+圆点、3 色 | 单子图、纯散点、3 色×3 marker |
| 图9 | 模态对蓝/红/紫 | 模态对橙/青/棕 |
| 图10 | 单模态蓝/橙/绿 | 单模态蓝/红/紫 |
| 图17 | 灰+绿堆叠、横轴=η_phase、术语 oracle-best | 三候选 + 术语 GT-optimal |
| fig2 | 信道色含蓝红 | 信道色去蓝红 |

---

## 5. 评估 / 验收标准

| # | 检查项 | 通过条件 |
|---|--------|----------|
| 1 | 不变量 | 全篇任何图内，蓝/红/紫只出现在「单模态」系列，信道/模态对/域系列不再出现这三色 |
| 2 | 图6 | 仅 3 条信道且为 13/64/71，日志打印过其相位/相干值 |
| 3 | 图8 | 单子图、纯散点、信道=marker、模态对=颜色，图例可读 |
| 4 | 图17 | 三候选 PNG+PDF 齐全，图内无 "oracle-best" |
| 5 | 数据不变 | 未修改 `modal_oracle_per_window.npy`、原始 JSONL、任何 GT |
| 6 | 复现性 | 图17 由脚本函数可复现，不再依赖一次性 `python -c` |

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 |
|------|------|
| 改脚本 1 | `notebooks/scripts/chFusion_position_sweep_observation.py` |
| 改脚本 2 | `notebooks/scripts/chFusion_paper_figures_mechanism.py` |
| 改脚本 3 | `notebooks/scripts/chFusion_modal_oracle_diag.py`（新增单面板函数） |
| 报告 | `docs/reports/paper_figure_revision_round2_report.md` |

### 6.2 重跑命令（示例）

```bash
python notebooks/scripts/chFusion_position_sweep_observation.py --only C,D,B
python notebooks/scripts/chFusion_paper_figures_mechanism.py --only 2,3
python notebooks/scripts/chFusion_modal_oracle_diag.py --plot-only --oracle-single  # 新增开关
```

### 6.3 接口草案（图17 新增函数）

```python
def plot_oracle_phase_eta_single(arr, domain="hkh", form="v1|v2|v3") -> Path:
    """从 modal_oracle_per_window.npy 的 structured array 画单面板图17候选。
    输入 arr: domain=='hkh' 的子集；form: 候选形式；返回保存的 PNG 路径。
    内部用 GT-optimal 替代 oracle-best，并打印 phase η 排名占比。
    """
```

### 6.4 不做的事

- 不改算法、指标定义、baseline、原始数据/GT。
- 不擅自覆盖正稿 `paper_fig_modal_oracle_phase_eta_hkh.{png,pdf}`（等作者择优）。
- 不替作者改 LaTeX 题注正文（只出建议）。
- 不把图8 横轴改成时间（已定不统一）。

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| 图6 | `outputs/figures/position_sweep_figC1_hard_remote.{png,pdf}` |
| 图8 | `outputs/figures/position_sweep_figD2_dphi_vs_position_ch20_40_60.{png,pdf}` |
| 图10 | `outputs/figures/paper_fig3_ab.{png,pdf}` |
| 图9 | `outputs/figures/paper_fig3_cd.{png,pdf}` |
| fig2 | `outputs/figures/paper_fig2_inter_tone_phase.{png,pdf}` |
| 图17 候选 | `outputs/figures/paper_fig_modal_oracle_phase_eta_hkh_v1/v2/v3.{png,pdf}` |
| 报告 | `docs/reports/paper_figure_revision_round2_report.md` |
| 色表回填 | 报告 §6 附最终全篇色表 |

---

## 8. 风险与保留问题

| ID | 风险/问题 | 处置 |
|----|-----------|------|
| R1 | 信道 13/64/71 是否确为「同相/反相」代表 | 执行时打印相位/相干值；不符则停止回报，不擅自换 |
| R2 | 图8 单子图 9 组散点可能重叠拥挤 | 用双图例 + 可微调 marker/透明度；执行后附预览供作者定 |
| R3 | 图17 三候选可能无一是作者要的 | 先出候选不覆盖正稿；作者可再提第 4 种形式 |
| R4 | 配色改动范围可能遗漏某些图 | 报告列出「已改/未改」清单，作者复核 |
| R5 | 现有 E 系列灰值不统一（`#7f7f7f` vs `#9e9e9e`） | 统一为 `#9e9e9e`，随配色一并处理 |
| Q1 | 图5 题注是否需改为「channel-averaged η/ρ」措辞 | 执行 Agent 出建议，作者定 `[待确认]` |
| Q2 | 模态对三色（橙/青/棕）观感是否可接受 | 出图后作者看 `paper_fig3_cd` 定 `[待确认]` |

---

## 9. 验证状态

状态：已完成

实际产出路径：
- 脚本：`notebooks/scripts/chFusion_position_sweep_observation.py`、`notebooks/scripts/chFusion_paper_figures_mechanism.py`、`notebooks/scripts/chFusion_modal_oracle_diag.py`
- 数值结果：未新写指标文件。`modal_oracle_per_window.npy` 未修改。机制图脚本按原路径重写了 `outputs/reports/paper_figures_diagnostics.npy`。
- 图表：`outputs/figures/position_sweep_figB2_channel_position_matrix.{png,pdf}`、`position_sweep_figC1_hard_remote.{png,pdf}`、`position_sweep_figD2_dphi_vs_position_ch20_40_60.{png,pdf}`、`paper_fig2_inter_tone_phase.{png,pdf}`、`paper_fig3_ab.{png,pdf}`、`paper_fig3_cd.{png,pdf}`、`paper_fig_modal_oracle_phase_eta_hkh_v1_modal_dist.{png,pdf}`、`..._v2_ratio_hist.{png,pdf}`、`..._v3_share_bar.{png,pdf}`
- 报告：`docs/reports/paper_figure_revision_round2_report.md`

结论摘要：

图 6 相位检查通过（ref=71；ch13 反相 φ=−3.1305、γ=0.9735；ch64 同相 φ=−0.0004、γ=0.9986；ch71 同相 φ=0、γ=1）。图 17 HKH n=1730：phase η 排名第 1 占 5.49%，phase 为 GT-optimal modal 占 6.07%。正稿 `phase_oracle_eta.pdf` 未覆盖。`wang26breathecs.tex` 已编译通过（13 页）。

遗留问题：

- Q1 图 5 题注措辞仍待作者定，报告里给了建议，未改 tex。
- Q2 模态对橙/青/棕观感待作者看 `paper_fig3_cd` 与图 8。
- 图 17 三候选待作者择优后再覆盖正稿。
- 图 8 上 R-P 与 L-P 在 0 和 ±π 处仍然叠在一起，图例已移到轴外。

---

## 10. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/paper_figure_revision_round2_plan.md`

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/paper_figure_revision_round2_plan.md`
- `docs/reports/paper_figure_revision_round2_report.md`
- `outputs/figures/` 下本轮新增/覆盖的 PNG+PDF
- 关键脚本路径与 git diff 摘要
