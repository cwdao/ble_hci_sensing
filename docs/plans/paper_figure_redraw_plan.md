# 论文第六章实验配图重绘 — 实现计划

> **来源**：`docs/plans/paper_draft_skeleton.md` §6 审查结论  
> **目标报告**：`docs/reports/paper_figure_redraw_report.md`  
> **日期**：2026-07-25  
> **验证状态**：待实现

---

## 1. 动机与背景

### 问题

当前论文第六章（实验验证）的配图存在以下问题：

| # | 问题 | 影响 |
|---|------|------|
| 1 | 方法名使用内部代号（B3 Simplified, B1 Vote→Equal, B2-D 等），读者无法理解 | 论文不可读 |
| 2 | BreatheCS 的 BPM 标注可能混淆 BPM 分支与波形分支 | 自贬排名 |
| 3 | Fig 7（BPM×RMSE 散点图）放在 §6.4（波形恢复精度），与章节主题不匹配 | 叙事逻辑断裂 |
| 4 | §6.4 缺少独立的 RMSE 比较（表格或排行榜图） | 章节空洞 |
| 5 | Fig 8 消融图代号过多、分组不清 | 消融叙事不清晰 |
| 6 | 部分 baseline 变体数量过多（10+），论文中不需要全部展示 | 图杂乱 |

### 本 plan 定位

**不涉及新实验**——所有数据已有（`outputs/reports/ble_hkh_paper_baselines_summary.json`、`ble_hkh_b3_simplified_validation_summary.json` 等）。本 plan 仅要求：

1. 在绘图脚本中建立 **旧代号 → 论文名称映射表**
2. 按新的图-章节对应关系重新生成配图
3. 对 §6.4 补一张 RMSE 表格
4. 对消融图做分组和精简

---

## 2. 方法命名映射表（单一事实来源）

> **规则**：论文图中 ytick / legend 使用「论文简称」；正文首次出现时用 "WiFi-Sleep (Yu et al., 2021)" 形式。

### 2.1 本文方法（BreatheCS 家族）

| 内部 key | 当前 label | **→ 论文名称（图中）** | 用途 |
|---|---|---|---|
| `b3_b1_equal` | B3 Simplified | **BreatheCS** | 主方法（BPM 来自谱分支，RMSE 来自波分支） |
| `b1_vote_modal_equal` | B1 Vote→Equal | **BreatheCS-Spec** | 仅谱域变体（消融用，无波形输出） |
| `b2_d_two_level` | B2-D Two-level Hilbert-MRC (ref) | **BreatheCS-Wave** | 仅波形分支变体（消融用） |

### 2.2 外部 baseline（迁移的 WiFi 方法）

| 内部 key | 当前 label | **→ 论文名称（图中）** |
|---|---|---|
| `z1_no_vmd` | Zhuo 2023 Z1-no-VMD PCA→PCA→Peak | **Pos-Free (PCA)** |
| `z1` | Zhuo 2023 Z1 PCA→PCA→VMD→Peak | **Pos-Free (PCA-VMD)** |
| `z1_fft` | Zhuo 2023 Z1-FFT PCA→PCA→VMD→FFT | **Pos-Free (PCA-VMD+FFT)** |
| `mrc_pca_eta_equal_pca` | Yu 2021 MRC-PCA η-equal PCA3→1 | **WiFi-Sleep (MRC-PCA)** |
| `mrc_pca_eta_sqrt` | Yu 2021 MRC-PCA √η (best modal) | **WiFi-Sleep (√η)** |
| `fan_eta_linear` | Fan 2024 η-linear (best modal) | **ClessBreath (η-linear)** |
| `fan_eta_equal_wf` | Fan 2024 η-equal waveform avg | **ClessBreath (η-equal)** |
| `fan_hilbert_equal` | Fan 2024 Hilbert equal wf | **ClessBreath (Hilbert)** |

> **注**：Fan 2024 论文无标准简称，用户选定 **ClessBreath**（Contactless Breathing 缩写）。

### 2.3 消融 / 简单 baseline

| 内部 key | 当前 label | **→ 论文名称（图中）** |
|---|---|---|
| `a1_single_best_eta` | A1 Single best-η | **Single (best-η)** |
| `a3_remote_only` | A3 Remote only | **Remote-only** |
| `a4_equal_spectral` | A4 Equal spectral fusion | **Equal-weight (spectral)** |
| `a5_equal_voting` | A5 Equal-weight voting | **Equal-weight (voting)** |
| `b2_a0_pca_sign` | B2-A0 PCA sign (ref) | **PCA sign only** |
| `r12_d_single_remote` | R12-D Single Remote | **Single (Remote)** |

### 2.4 颜色方案

| 论文系列 | 颜色 | 说明 |
|---|---|---|
| BreatheCS 家族 | `#E63946`（红） | 本文方法突出 |
| Pos-Free | `#81B29A`（绿） | Zhuo 2023 |
| WiFi-Sleep | `#3D405B`（深蓝） | Yu 2021 |
| ClessBreath | `#E07A5F`（橙） | Fan 2024 |

---

## 3. 需重绘/新增的图与表

### 3.1 Fig 6a：HKH 全场景 BPM 排行榜（§6.3）

**当前状态**：`ble_hkh_paper_baselines_leaderboard_all.png` — 有，但名称是代号

**重绘要求**：

- **方法精简**：最多展示 8–10 个方法。建议保留：
  1. BreatheCS (0.405)
  2. Pos-Free (PCA) (0.435)
  3. WiFi-Sleep (MRC-PCA) (0.505)
  4. BreatheCS-Wave (0.682)
  5. WiFi-Sleep (√η) (1.023)
  6. PCA sign only (1.317)
  7. ClessBreath (η-linear) (1.386)
  8. ClessBreath (η-equal) (1.483)
  9. Single (Remote) (1.952)

  移除的变体：
  - BreatheCS-Spec（与 BreatheCS BPM 同值 0.405，消融时再出现）
  - Pos-Free (PCA-VMD) / Pos-Free (PCA-VMD+FFT)（不如 PCA-only，正文提一句即可）
  - Fan2024 (Hilbert)（与 η-equal 相近，留一个代表）

- **BreatheCS 的 BPM 值**：必须来自 BPM 分支（= B3 Simplified = 0.405），**不是**波形分支（B2-D = 0.682）
- **标注**：BreatheCS 柱用红色 + ★ 标记
- **yticks**：使用 §2 映射后的论文名称
- **横轴**：Mean BPM absolute error (breaths/min) across 12 scenarios
- **误差线**：跨 12 场景的 std

### 3.2 Fig 6b：按房间拆分 BPM（§6.3）

**当前状态**：`ble_hkh_paper_baselines_by_room.png` — 有，名称是代号

**重绘要求**：

- 三组：Room A (Living room, sitting) / Room B (Bedroom, flat) / Room C (Bedroom, side)
- Top-5 方法即可（精简）
- 论文名称标注
- 可考虑 grouped bar 或三列小图（faceted）

### 3.3 Table X：波形 RMSE 比较表（§6.4）

**当前状态**：无

**新增要求**：

- 表格内容：各方法在 12 场景上的 mean RMSE ± std（vs 呼吸带，z-score 对齐后）
- 建议保留的方法行（与 Fig 6a 一致）：

| Method | RMSE mean | RMSE std |
|---|---|---|
| BreatheCS | 0.951 | ... |
| BreatheCS-Wave | 0.950 | ... |
| ClessBreath (η-linear) | 1.025 | ... |
| ClessBreath (η-equal) | 1.046 | ... |
| WiFi-Sleep (MRC-PCA) | 1.063 | ... |
| Pos-Free (PCA) | 1.070 | ... |
| PCA sign only | 1.085 | ... |
| Single (Remote) | ... | ... |

- 表格放在 §6.4 正文中，作为 RMSE 主要展示方式
- 数据来源：`ble_hkh_paper_baselines_summary.json` 和 `ble_hkh_b3_simplified_validation_summary.json`

### 3.4 Fig 7：BPM×RMSE 双指标散点图（维持当前位置）

**当前状态**：`ble_hkh_b3_bpm_vs_rmse.png` — 有，在 §6.4

**重绘要求**：

- **位置**：维持在 §6.4（先观察效果，后期可能调整）
- **命名**：使用论文名称
- **标注**：BreatheCS 用 ★，BreatheCS-Wave 用不同标记
- **注意**：BreatheCS-Spec 无 RMSE（纯谱域方法），不出现在此图中

### 3.5 Fig 8a：消融排行榜 — HKH（§6.5 重绘）

**当前状态**：`ble_hkh_b3_ablation_leaderboard.png` — 有，代号混乱

**重绘要求**：

- **分组展示**（按消融维度）：
  - **信道融合消融**：Single (best-η) → Equal-weight (voting) → BreatheCS（η·ρ 加权）
  - **模态融合消融**：Remote-only → Equal-weight (spectral) → BreatheCS（三模态等权）
  - **相位方法消融**：PCA sign only → Equal-weight (spectral) → BreatheCS-Wave（Hilbert 两级）
- **两种布局都出图**：同时生成 (A) 单张 grouped bar chart 和 (B) 1×3 faceted 子图（每维度一张），用户后期选择
- 论文名称标注，BreatheCS 红色高亮

### 3.6 Fig 8b：Waterfall 分解 — CS 金属板（§6.5 保留/重绘）

**当前状态**：`b2_coherent_mrc_waterfall_decomposition.png` — 有

**重绘要求**：

- 使用论文命名体系
- 明确标注数据来源为 CS 金属板（非 HKH），与 Fig 8a 区分
- 保留 waterfall 累积误差递减的叙事

### 3.7 可选：按姿势分组的补充图

**当前状态**：`ble_hkh_paper_baselines_bedroom_vs_living.png` — 有

如果论文空间允许，可选保留一张 "Living room vs Bedroom" 对比图（currently sitting vs lying 两个姿势组），展示方法在不同姿态下的鲁棒性。

---

## 4. 不需要改动的图

以下机制图（§3–§5）不受本次 plan 影响，**不需要重绘**：

- Fig 2 (inter-tone phase) ✅
- Fig 3 (inter-modal phase) ✅
- Fig 5 (η·ρ voting mechanism) ✅
- Fig S1 (coherence stability) ✅
- Fig 4 (unlocking ablation matrix) ❌ — 数据已有但图未生成，另案处理

---

## 5. 实现要点

### 5.1 建议方案：扩展现有脚本，而非重写

已有两个关键绘图脚本：

| 脚本 | 当前产出 | 本次修改 |
|---|---|---|
| `notebooks/scripts/chFusion_ble_hkh_paper_baselines.py` | Fig 6 系列（代号版） | 加入命名映射、精简方法列表、调整颜色 |
| `notebooks/scripts/chFusion_ble_hkh_b3_validation.py` | Fig 7, Fig 8a（代号版） | 同上；Fig 7 移到新位置 |

### 5.2 建议新增模块

在 `src/ble_analysis/` 下新增一个轻量模块（或直接在脚本中定义）：

```python
# src/ble_analysis/paper_naming.py  （或内联于脚本）

# 单一映射表：internal_key → (paper_label, paper_group, color)
PAPER_LABEL_MAP: dict[str, tuple[str, str, str]] = {
    # BreatheCS family — red
    "b3_b1_equal":        ("BreatheCS",              "BreatheCS", "#E63946"),
    "b1_vote_modal_equal":("BreatheCS-Spec",         "BreatheCS", "#E63946"),
    "b2_d_two_level":     ("BreatheCS-Wave",         "BreatheCS", "#E63946"),
    # Pos-Free — green
    "z1_no_vmd":          ("Pos-Free (PCA)",         "Pos-Free",  "#81B29A"),
    "z1":                 ("Pos-Free (PCA-VMD)",     "Pos-Free",  "#81B29A"),
    "z1_fft":             ("Pos-Free (PCA-VMD+FFT)", "Pos-Free",  "#81B29A"),
    # WiFi-Sleep — dark blue
    "mrc_pca_eta_equal_pca": ("WiFi-Sleep (MRC-PCA)", "WiFi-Sleep", "#3D405B"),
    "mrc_pca_eta_sqrt":      ("WiFi-Sleep (√η)",      "WiFi-Sleep", "#3D405B"),
    # ClessBreath — orange
    "fan_eta_linear":     ("ClessBreath (η-linear)",     "ClessBreath",   "#E07A5F"),
    "fan_eta_equal_wf":   ("ClessBreath (η-equal)",      "ClessBreath",   "#E07A5F"),
    "fan_hilbert_equal":  ("ClessBreath (Hilbert)",      "ClessBreath",   "#E07A5F"),
    # Ablation variants — gray
    "a1_single_best_eta": ("Single (best-η)",        "Ablation",  "#999999"),
    "a3_remote_only":     ("Remote-only",            "Ablation",  "#999999"),
    "b2_a0_pca_sign":     ("PCA sign only",          "Ablation",  "#999999"),
}
```

### 5.3 绘图接口草案

```python
def plot_paper_leaderboard(
    rows: list[dict],           # 每个 dict 含 method_key, bpm_mean_abs_err, bpm_std...
    label_map: dict,            # method_key → paper_label
    color_map: dict,            # method_key → color
    highlight_keys: list[str],  # 高亮的方法（如 "b3_b1_equal"）
    filename: str,
) -> Path:
    """生成论文风格 BPM 排行榜。"""
    ...

def plot_paper_ablation_grouped(
    ablation_results: dict,     # {dimension: [{method_key, bpm_err, rmse}]}
    label_map: dict,
    ...
) -> Path:
    """分组消融图。"""
    ...
```

### 5.4 数据读取

所有数据来自已有的 JSON 文件，**不需要重新运行实验**：

- `outputs/reports/ble_hkh_paper_baselines_summary.json` — 外部 baseline
- `outputs/reports/ble_hkh_b3_simplified_validation_summary.json` — BreatheCS 家族
- 12 个单场景 JSON（`ble_hkh_paper_baselines_room_*.json`）— 如需 per-scenario 细节

### 5.5 不做的事

- 不重新跑实验（数据已有）
- 不修改 `src/ble_analysis/` 中的算法逻辑
- 不修改原始数据或 ground truth
- 不改变指标定义
- 不修改 Fig 2/3/4/5/S1（机制图不属于本次范围）

---

## 6. 预期产出

| 产出 | 路径 |
|------|------|
| 重绘 Fig 6a | `outputs/figures/paper_fig6a_bpm_leaderboard.png` + `.pdf` |
| 重绘 Fig 6b | `outputs/figures/paper_fig6b_bpm_by_room.png` + `.pdf` |
| 新增 RMSE 表 | 嵌入 `docs/plans/paper_draft_skeleton.md` §6.4（或独立 `.md` 片段） |
| 重绘 Fig 7 | `outputs/figures/paper_fig7_bpm_vs_rmse.png` + `.pdf` |
| 重绘 Fig 8a | `outputs/figures/paper_fig8a_ablation_hkh.png` + `.pdf` |
| 重绘 Fig 8b | `outputs/figures/paper_fig8b_waterfall_cs.png` + `.pdf` |
| 验证报告 | `docs/reports/paper_figure_redraw_report.md` |
| 更新 draft | `docs/plans/paper_draft_skeleton.md` §6 中图引用路径更新 |

---

## 7. 用户已确认事项

> 以下事项已由用户确认（2026-07-25），执行 Agent 直接按结论执行。

| ID | 问题 | 结论 |
|----|------|------|
| Q1 | Fan 2024 论文短名称 | **ClessBreath**（Contactless Breathing 缩写） |
| Q2 | Fig 6a 排行榜保留哪些方法 | 按 §3.1 建议保留 9 个 |
| Q3 | 消融图布局 | **两种都画**：单张 grouped bar + 1×3 faceted 子图，用户后期选择 |
| Q4 | RMSE 数据合并验证 | **先不管**，直接用两个 JSON 文件的已有 RMSE 值 |
| Q5 | Fig 7 散点图位置 | **维持现状**（§6.4），先不改动位置 |

---

## 8. 风险与保留问题

- **风险**：如果两个 JSON 文件的 RMSE 计算方法不完全一致（z-score 对齐参数差异），合并后可能出现不可比的情况。执行前应验证 B2-D 在两个文件中的 RMSE 值一致（当前 BPM 一致已确认，RMSE 需验证）。
- **风险**：精简方法列表可能遗漏 Reviewer 关心的 baseline 变体。建议在正文中提及 "完整变体结果见 Appendix"。
- **[待确认]**：CS 金属板 waterfall 消融图（Fig 8b）与 HKH 消融（Fig 8a）的数据来源不同，两图并列时需在标题明确标注。

---

## 9. 验证状态

| 字段 | 内容 |
|------|------|
| **验证状态** | 待实现 |
| **实际脚本** | — |
| **报告链接** | — |
| **一句话结论** | — |

---

## 10. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/paper_figure_redraw_plan.md`

> **核心任务**：
> 1. 在绘图脚本中建立 §2 的命名映射表
> 2. 按 §3 逐图重绘，输出到 `outputs/figures/paper_fig6a_*.png` 等新路径
> 3. 生成 RMSE 比较表
> 4. 写一份简短验证报告到 `docs/reports/paper_figure_redraw_report.md`
> 5. **不需要重新跑实验**——所有数据已有，只改绘图端

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `outputs/figures/paper_fig6a_*.png` 等新图
- `docs/reports/paper_figure_redraw_report.md`
- 修改后的脚本路径
- git diff 摘要
