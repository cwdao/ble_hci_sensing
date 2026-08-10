# 论文配图修订（Position Sweep + Fig 2/3）— 验证报告

> **性质**：执行侧配图修订记录（非新算法验证）  
> **触发**：用户对 draft Ch.4 / Fig 2–3 相关 PNG 的排版与导出要求  
> **脚本**：  
> - `notebooks/scripts/chFusion_position_sweep_observation.py`  
> - `notebooks/scripts/chFusion_paper_figures_mechanism.py`  
> **日期**：2026-08-10  
> **状态**：已完成

---

## 1. 目标

按用户确认的规格修订 draft 引用的若干 position-sweep / 机制图：

1. 去掉不必要的大标题；
2. 调整子图布局与坐标轴标注；
3. 同步导出 **PDF**（纸质/排版用）与 **PNG**（预览）；
4. 为 Fig 2/3 额外产出可单独插入正文的分面板文件。

本轮**不改变**底层数值计算定义（η/ρ、Δφ、滤波与选道逻辑保持原实现）；仅改绘图与导出。

---

## 2. 用户确认的规格（执行依据）

| # | 图 | 确认项 |
|---|----|--------|
| 1 | E3 | 纵轴在符号旁补充解释性英文：`η (energy ratio)`、`ρ (peak prominence)` |
| 2 | C1 | **只重画** `hard_remote`；其它 `figC1_*` 保留旧三面板样式 |
| 3 | D2 | 纵向拼合仅 **ch20 / ch40 / ch60**（不含 35/71） |
| 4 | Fig3 CD | 子标题用英文：**Studio position 1** / **Studio position 2**（对应 `cs_095806` / `cs_102621`） |
| 5 | C1 垂直偏移 | 步长固定 **3**（约一个 π 量级的视觉间隔） |

其余改动沿用用户此前口头规格（B2 列标题、Fig2 去 d/e、宽度约 70%、分面板导出等）。

---

## 3. 代码改动摘要

### 3.1 `chFusion_position_sweep_observation.py`

| 改动 | 说明 |
|------|------|
| 新增 `_save_png_pdf()` | 统一写出 `.png` + `.pdf` |
| 新增 CLI `--only A,B,C,D,E` | 支持部分重跑（本轮：`--only B,C,D,E`） |
| `plot_fig_b` / B2 | 去掉 `suptitle`；列标题由 `segXX (N cm)` 改为 **`N cm`**；B2 存 PDF |
| `plot_fig_c` / C1 hard_remote | 仅画 panel (a)；选 8 个代表性 tone；`y = zscore + i*3` 垂直散开；无大标题；PNG+PDF |
| `plot_fig_d` / D2 | 单图标题改为 **`ch {n}`**；新增纵向拼合 `…_ch20_40_60`；各图 PNG+PDF |
| `plot_fig_e` / E3 | 去掉大标题；`set_ylabel("η (energy ratio)")` / `"ρ (peak prominence)"`；PNG+PDF |

### 3.2 `chFusion_paper_figures_mechanism.py`

| 改动 | 说明 |
|------|------|
| CLI `--only 2,3,5,S1` | 本轮：`--only 2,3` |
| `generate_fig2` | 删除 (d)(e) 相干热图；**(a)(b)(c) 各占一行、等宽**；`figsize≈(8.4, 8.5)`（宽约原 12 的 70%）；另存 `paper_fig2_a/b/c` |
| `generate_fig3` | 拆出 `paper_fig3_ab`、`paper_fig3_a/b`、`paper_fig3_cd`、`paper_fig3_studio_pos1/pos2`；CD 标题为 Studio position 1/2；保留旧名 `paper_fig3_inter_modal_phase` 2×2 总图以兼容 draft 链接 |

---

## 4. 执行命令

```bash
python notebooks/scripts/chFusion_position_sweep_observation.py --only B,C,D,E
python notebooks/scripts/chFusion_paper_figures_mechanism.py --only 2,3
```

两脚本均 exit 0。

---

## 5. 逐图修订明细

### 5.1 `position_sweep_figB2_channel_position_matrix`

| 项 | 旧 | 新 |
|----|----|----|
| 大标题 | `Fig B2 — Channel × position matrix …` | **删除** |
| 列标题 | `seg13 (88 cm)` 等 | **`88 cm` / `87 cm` / `86 cm`** |
| 行标签 | `ch20` / `ch40` / `ch60` | 不变 |
| 导出 | PNG only | **PNG + PDF** |

路径：

- `outputs/figures/position_sweep_figB2_channel_position_matrix.png`
- `outputs/figures/position_sweep_figB2_channel_position_matrix.pdf`

---

### 5.2 `position_sweep_figC1_hard_remote`

| 项 | 旧 | 新 |
|----|----|----|
| 面板 | (a)(b)(c) 三行 | **仅 (a)** 多信道波形 |
| 信道数 | 4 | **8**（`_select_representative_tones(..., k=8)`） |
| 纵轴排布 | 全部 z-score 叠到 y≈0 | **`z + i*3`** 垂直散开 |
| 大标题 | `Fig C1 — hard …` | **删除** |
| 其它 C1 | — | **未改算法样式**（仍三面板 PNG） |
| 导出 | PNG only | **PNG + PDF**（仅 hard_remote） |

路径：

- `outputs/figures/position_sweep_figC1_hard_remote.png`
- `outputs/figures/position_sweep_figC1_hard_remote.pdf`

本轮 hard_remote 选用信道（日志/图例）：`ch71, ch70, ch13, ch67, ch61, ch65, ch66, ch64`。

---

### 5.3 `position_sweep_figD2_dphi_vs_position_ch*`

| 项 | 旧 | 新 |
|----|----|----|
| 单图标题 | `Fig D2 — Modal Δφ vs position (chN)` | **`ch N`** |
| 拼合图 | 无 | **`…_ch20_40_60`** 三行纵向；无总大标题；子标题 `ch 20/40/60` |
| 覆盖信道 | 35, 71, 20, 40, 60（单图均更新标题） | 拼合**仅** 20/40/60 |
| 导出 | PNG only | 单图 + 拼合均 **PNG + PDF** |

路径（关键）：

- `outputs/figures/position_sweep_figD2_dphi_vs_position_ch20.png/.pdf`
- `outputs/figures/position_sweep_figD2_dphi_vs_position_ch40.png/.pdf`
- `outputs/figures/position_sweep_figD2_dphi_vs_position_ch60.png/.pdf`
- `outputs/figures/position_sweep_figD2_dphi_vs_position_ch20_40_60.png/.pdf`
- （同轮也更新了 ch35/ch71 单图标题与 PDF）

---

### 5.4 `position_sweep_figE3_eta_rho_comparison`

| 项 | 旧 | 新 |
|----|----|----|
| 大标题 | `Fig E3 — η + ρ comparison: metal vs human` | **删除** |
| 左纵轴 | `η` | **`η (energy ratio)`** |
| 右纵轴 | `ρ` | **`ρ (peak prominence)`** |
| 导出 | PNG only | **PNG + PDF** |

路径：

- `outputs/figures/position_sweep_figE3_eta_rho_comparison.png`
- `outputs/figures/position_sweep_figE3_eta_rho_comparison.pdf`

> 说明：正文中文常称 ρ 为「峰度」，工程指标名为 peak prominence；英文轴标签按项目术语写作 `peak prominence`。若需改为 `kurtosis` 可再改一版。

---

### 5.5 `paper_fig2_inter_tone_phase`

| 项 | 旧 | 新 |
|----|----|----|
| 布局 | 第 1 行 a\|b；第 2 行 c 通栏；第 3 行 d\|e 热图 | **删除 d/e**；**a/b/c 各占一行、等宽** |
| 宽度 | `figsize=(12, 9)` | **`≈(8.4, 8.5)`（约 70%）** |
| 分面板 | 无 | `paper_fig2_a` / `_b` / `_c` |
| 大标题 | 无总标题（仅子图 `(a)(b)(c)`） | 保持；分面板同样无总标题 |
| 导出 | 总图已有 PNG+PDF | 总图 + 三分面板均 PNG+PDF |

路径：

- `outputs/figures/paper_fig2_inter_tone_phase.png/.pdf`
- `outputs/figures/paper_fig2_a.png/.pdf`
- `outputs/figures/paper_fig2_b.png/.pdf`
- `outputs/figures/paper_fig2_c.png/.pdf`

本轮 Fig2 选窗：`cs_095806` seg=`1b`，`window_idx=16`，tones=`[58, 48, 45, 69]`。

---

### 5.6 `paper_fig3_inter_modal_phase` 及拆分

| 产出 | 内容 | 子标题 |
|------|------|--------|
| `paper_fig3_ab` | 原 (a)(b) 合图 | `(a)` / `(b)` |
| `paper_fig3_a` | 单独 (a) | `(a)` |
| `paper_fig3_b` | 单独 (b) | `(b)` |
| `paper_fig3_cd` | 原 (c)(d) 合图 | **Studio position 1** / **Studio position 2** |
| `paper_fig3_studio_pos1` | `cs_095806` Δφ | Studio position 1 |
| `paper_fig3_studio_pos2` | `cs_102621` Δφ | Studio position 2 |
| `paper_fig3_inter_modal_phase` | 兼容旧链接的 2×2 总图 | a/b + Studio position 1/2 |

全部 PNG+PDF。场景：`cs_095806` seg=`1b`（42 窗）；`cs_102621` seg=`1b`（41 窗）。

---

## 6. 产出清单（本轮新增/覆盖）

### Position sweep（PDF 新增或 PNG 覆盖）

```text
outputs/figures/position_sweep_figB2_channel_position_matrix.{png,pdf}
outputs/figures/position_sweep_figC1_hard_remote.{png,pdf}
outputs/figures/position_sweep_figD2_dphi_vs_position_ch20.{png,pdf}
outputs/figures/position_sweep_figD2_dphi_vs_position_ch40.{png,pdf}
outputs/figures/position_sweep_figD2_dphi_vs_position_ch60.{png,pdf}
outputs/figures/position_sweep_figD2_dphi_vs_position_ch35.{png,pdf}
outputs/figures/position_sweep_figD2_dphi_vs_position_ch71.{png,pdf}
outputs/figures/position_sweep_figD2_dphi_vs_position_ch20_40_60.{png,pdf}
outputs/figures/position_sweep_figE3_eta_rho_comparison.{png,pdf}
```

### Paper mechanism

```text
outputs/figures/paper_fig2_inter_tone_phase.{png,pdf}
outputs/figures/paper_fig2_a.{png,pdf}
outputs/figures/paper_fig2_b.{png,pdf}
outputs/figures/paper_fig2_c.{png,pdf}
outputs/figures/paper_fig3_inter_modal_phase.{png,pdf}
outputs/figures/paper_fig3_ab.{png,pdf}
outputs/figures/paper_fig3_a.{png,pdf}
outputs/figures/paper_fig3_b.{png,pdf}
outputs/figures/paper_fig3_cd.{png,pdf}
outputs/figures/paper_fig3_studio_pos1.{png,pdf}
outputs/figures/paper_fig3_studio_pos2.{png,pdf}
```

---

## 7. 与 draft 的对应关系

| Draft 引用 | 建议使用文件 |
|------------|--------------|
| Ch.4 B2 信道×位置矩阵 | `position_sweep_figB2_channel_position_matrix` |
| Ch.4 C1 hard remote 波形 | `position_sweep_figC1_hard_remote` |
| Ch.4 D2 Δφ vs 位置 | 单信道用 `…_ch{20,40,60}`；正文拼版优先 `…_ch20_40_60` |
| Ch.4 E3 η/ρ | `position_sweep_figE3_eta_rho_comparison` |
| Figure 2 | 总图 `paper_fig2_inter_tone_phase` 或分面板 `paper_fig2_a/b/c` |
| Figure 3 | 对齐前/后：`paper_fig3_ab`（或 a/b）；工作室两位置：`paper_fig3_cd`（或 studio_pos1/2） |

> 本轮**未自动改写** `docs/paper_draft/paper_draft_skeleton.md` 中的图注路径；若正文要改用拼合 D2 / 分面板 Fig2–3，需另开一轮 draft 链接更新。

---

## 8. 结论

| 项 | 状态 |
|----|------|
| B2 / C1 hard_remote / D2 / E3 按确认规格重绘 | **已完成** |
| Fig2 去 d/e、abc 竖排、宽度约 70%、分面板 | **已完成** |
| Fig3 ab/cd 总图 + 拆分；Studio position 英文标题 | **已完成** |
| 关键图 PNG+PDF 双导出 | **已完成** |
| 算法数值定义变更 | **无** |

---

## Self Check

- Spec confirmed with user: yes
- Scripts updated: yes
- Scripts executed: yes (`--only B,C,D,E` / `--only 2,3`)
- PNG+PDF generated for requested figures: yes
- Hardcoded frame index risk: no（沿用既有选窗/选道逻辑）
- Metric definition changed: no
- Draft markdown paths updated: **no**（仅出图；链接更新待另轮）
- Ready to commit: yes（若用户要求提交）
