# 论文第六章「表格 → 图示」重绘计划（v2）

> **任务类型**：Research Mode → 绘图规格 plan（**不重跑实验**，仅重绘 + 补图）
> **对象**：`docs/paper_draft/paper_draft_skeleton.md` 第六章（§6.3 主结果、§6.4 波形精度、§6.4 消融）
> **目标报告**：`docs/reports/paper_ch6_tables_to_figures_report.md`
> **日期**：2026-10-22
> **验证状态**：待实现

---

## 1. 动机与背景

第六章当前是「表格为主、图为辅」，且已有图存在三处与 skeleton 最新数值不一致的问题：

| # | 问题 | 说明 |
|---|------|------|
| 1 | **BreatheCS / BreatheCS-Wave 数值过期** | 现有 `paper_fig6a/6b/8` 仍用旧值（BreatheCS BPM=0.405、BreatheCS-Wave BPM=0.682/0.744）。skeleton 已定稿为 **BreatheCS=0.371、BreatheCS-Wave=0.385**（端侧幅值 R+L，非三模态） |
| 2 | **表格未成图** | 表 6.4（RMSE）、表 8-A（融合层级）、表 8-B（单模态）当前无独立带误差线条形图 |
| 3 | **图内冗余标注** | Fig 6a 的 BreatheCS 行带「★ BreatheCS」红色文字 + 黑边星标，不符合论文图表规范（正文/题注负责说明，图上不画提示） |
| 4 | **缺误差线** | Fig 6b、Fig 8 均无 std 误差线 |
| 5 | **图上画了标题/题注** | Fig 8 各 panel 的 `set_title("(a) Fusion levels · ...")` 属于题注，应移到正文 caption |

本 plan 只做：**① 建立方法含义对照表；② 逐图给出数据来源 + 布局 + 误差线口径 + 题注文字；③ 统一图表风格**。不修改算法、不改数据、不改指标定义。

---

## 2. 方法命名与含义对照表（本 plan 的核心交付物）

> 用户诉求：把所有方法（含括号变体）的含义写清楚。以下为「论文名 → 内部 key → 算法含义」的权威对照。

### 2.1 本文方法（BreatheCS 家族，红色 #E63946）

| 论文名 | 内部 key | 算法含义 |
|---|---|---|
| **BreatheCS** | Spec=`draft_s_rl`，Wave=`draft_w_rl` | 本文方法。BPM 分支 = 端侧幅值（Remote+Local）**等权谱融合**后寻峰；波形分支 = R+L **两级 Hilbert-MRC**。合成相位按窗级 η 自适应选择，但真人数据下相位几乎不被选中（open_ratio≈0），故最终 ≈ 端侧幅值 R+L |
| **BreatheCS-Wave**（时域分支，对照） | `draft_w_rl` | 仅波形分支的 BPM 输出（R+L Hilbert-MRC 谱峰）。**双分支对照行，非主方法**——正文用于说明「BPM 分支与波形分支的 BPM 精度接近」 |

### 2.2 外部 baseline（迁移自 WiFi 文献）

| 论文名 | 内部 key | 出处 | 算法含义 |
|---|---|---|---|
| **Pos-Free (PCA)** | `z1_no_vmd` | Zhuo et al. 2023（position-free） | PCA(72 tone)→PCA(3 modal)→峰值检测（**无 VMD**） |
| Pos-Free (PCA-VMD) | `z1` | Zhuo 2023 | PCA→PCA→VMD→峰值检测（正文表未列，仅 Fig 7 散点可选展示） |
| **WiFi-Sleep (MRC-PCA)** | `mrc_pca_eta_equal_pca` | Yu et al. 2021 WiFi-Sleep | √η-MRC 信道融合 + PCA 符号校正 → 三模态波形 PCA(3→1) 融合 |
| **WiFi-Sleep (√η)** | `mrc_pca_eta_sqrt` | Yu 2021 | √η-MRC 信道融合 → 按 η 选最优单模态 |
| **PCA sign only** | `b2_a0_pca_sign` | —（信道级消融） | 仅 PCA ±1 符号校正（信道级对齐），**不做模态融合** |
| **ClessBreath (η-linear)** | `fan_eta_linear` | Fan et al. 2024（Contactless Breathing，用户选定简称） | η 加权 MRC 信道融合 → 按 η 选最优单模态（Fan 原文做法） |
| **ClessBreath (η-equal)** | `fan_eta_equal_wf` | Fan 2024 | η-MRC 信道融合 → 三模态时域等权平均 |

### 2.3 消融——融合层级（表 8-A）

| 论文名 | Spec key | Wave key | 算法含义 |
|---|---|---|---|
| **No fusion** | `draft_s_none` | `draft_w_none` | 单信道 max-η（信道、模态均不融合） |
| **Channel only** | `draft_s_channel` | `draft_w_channel` | 仅信道级融合；模态级选单最优 |
| **Modal only** | `draft_s_modal` | `draft_w_modal` | 仅模态级融合；信道级选单最优 |
| **BreatheCS** | `draft_s_rl` | `draft_w_rl` | 两级融合（信道 + 端侧幅值模态） |

### 2.4 消融——单模态（表 8-B）

| 论文名 | Spec key | Wave key | 算法含义 |
|---|---|---|---|
| **Remote** | `draft_ms_remote` | `draft_mw_remote` | 仅 Remote 幅值 |
| **Local** | `draft_ms_local` | `draft_mw_local` | 仅 Local 幅值 |
| **Phase** | `draft_ms_phase` | `draft_mw_phase` | 仅合成相位 |
| **BreatheCS** | `draft_s_rl` | `draft_w_rl` | 端侧幅值 R+L 融合 |

### 2.5 关键口径说明（务必与 skeleton 一致）

- **BreatheCS 不再是三模态等权**。旧值 0.405（`draft_s_full`）/ 0.744（`draft_w_full`）是三模态版本，因 Phase 退化已降为消融对照。**图内 BreatheCS 一律用 `draft_s_rl`（0.371）/ `draft_w_rl`（0.385，RMSE 0.937）**。
- **std 口径 = 总体标准差 `np.std(per_scenario, ddof=0)`**（N=12 场景，或 N=4 subject/房间）。skeleton 表 6.3-B / 6.4 / 8-A / 8-B 均按此口径标注。

---

## 3. 数据来源汇总

| 图 | 数据文件 | 读取方式 |
|---|---|---|
| Fig 6a（表 6.3-A） | `ble_hkh_draft_ablation_summary.json`（BreatheCS=`draft_s_rl`、BreatheCS-Wave=`draft_w_rl`）+ `ble_hkh_paper_baselines_summary.json`（6 个 baseline） | BPM mean + per-scenario std(ddof=0) |
| Fig 6b（表 6.3-B） | `outputs/reports/paper_table63b_per_room_std.json` → `methods.*.per_room` | 每房间 mean ± std（已按 ddof=0，N=4） |
| 表 6.4 条形图 | `paper_table63b_per_room_std.json` → `table_64_waveform_rmse.methods.*.values` | 12 场景 RMSE → mean ± std(ddof=0) |
| Fig 8-A（表 8-A） | `ble_hkh_draft_ablation_summary.json` | Spec/Wave BPM + Wave RMSE，per-scenario std(ddof=0) |
| Fig 8-B（表 8-B） | `ble_hkh_draft_ablation_summary.json`（`draft_ms_*`/`draft_mw_*` + `draft_s_rl`/`draft_w_rl`） | 同上 |

> **std(ddof=0) 计算方式**：优先读 per-scenario 值直接 `np.std(vals, ddof=0)`；若只有汇总 std（ddof=1），按 `×√(11/12)` 折算。两法结果一致（skeleton 备注已说明）。

---

## 4. 逐图规格与题注

### 4.1 Fig 6a —— 表 6.3-A（BPM 排行榜，在现有图上改）

**做法**：修改 `paper_fig6a_bpm_leaderboard.png/.pdf`。

- **方法集（8 个，BPM 升序）**：
  1. BreatheCS 0.371 (±0.128)
  2. BreatheCS-Wave 0.385 (±0.113)
  3. Pos-Free (PCA) 0.435 (±0.123)
  4. WiFi-Sleep (MRC-PCA) 0.505 (±0.149)
  5. WiFi-Sleep (√η) 1.023 (±1.257)
  6. PCA sign only 1.317 (±0.646)
  7. ClessBreath (η-linear) 1.386 (±1.685)
  8. ClessBreath (η-equal) 1.486 (±1.527)
- **改动点**：
  1. 更新 BreatheCS → 0.371、BreatheCS-Wave → 0.385；std 用 ddof=0。
  2. **删除 BreatheCS 行的黑边星标 + 红色「★ BreatheCS」文字**（`bars[i].set_edgecolor("black")`、`ax.text(... "★ BreatheCS" ...)` 均移除）。
  3. 保留颜色分组图例（BreatheCS 家族红 / Pos-Free 绿 / WiFi-Sleep 深蓝 / ClessBreath 橙 / 简单消融灰）——图例允许上墙。
- **布局**：横向条形图（`barh`），x 轴 `Mean BPM absolute error (breaths/min) across 12 scenarios`，误差线 `capsize=3`。
- **风格**：不设 `set_title`；方法名即 ytick。

**题注（写入正文/报告，不画在图上）**：

> **Fig. 6a — BPM accuracy across all 12 HKH recordings.** Mean absolute BPM error (breaths/min) and cross-scenario std for BreatheCS and migrated WiFi baselines. BreatheCS (0.371) is lowest; Pos-Free (PCA) and WiFi-Sleep (MRC-PCA) follow around 0.44–0.51; the ClessBreath variants are ≈1.39–1.49.

---

### 4.2 Fig 6b —— 表 6.3-B（按房间 BPM，加误差线）

**做法**：修改 `paper_fig6b_bpm_by_room.png/.pdf`，**形式不变，仅加 std 误差线**。

- **数据**：每房间（Living sitting / Bedroom flat / Bedroom side）4 subject 的 mean ± std，直接读 `paper_table63b_per_room_std.json`（已按 ddof=0）。
- **布局**：维持现有 grouped bar（x = 方法，分组 = 3 房间），每组柱加 `yerr` 误差线（`capsize=2`）。8 方法 × 3 房间 = 24 柱。
- **方法集**：与 Fig 6a 一致（8 个，含 ClessBreath 系列）。
- **风格**：x 轴方法名旋转 25°；不设标题。

**题注**：

> **Fig. 6b — BPM accuracy by room.** Same method set as Fig. 6a, split by recording scenario (Living sitting / Bedroom flat / Bedroom side). BreatheCS is the lowest in all three rooms; the ClessBreath variants show large per-subject variance (error bars).

---

### 4.3 表 6.4 —— 波形 RMSE 条形图（**新增**）

**做法**：新增 `paper_fig6_4_rmse_leaderboard.png/.pdf`（横向条形图，RMSE 升序）。

- **方法集（7 个）**：
  1. BreatheCS 0.937 (±0.201)
  2. ClessBreath (η-linear) 1.025 (±0.231)
  3. ClessBreath (η-equal) 1.046 (±0.202)
  4. WiFi-Sleep (√η) 1.054 (±0.228)
  5. WiFi-Sleep (MRC-PCA) 1.063 (±0.234)
  6. Pos-Free (PCA) 1.070 (±0.239)
  7. PCA sign only 1.085 (±0.174)
- **数据**：`paper_table63b_per_room_std.json` → `table_64_waveform_rmse.methods.*.values`（12 场景 RMSE），`mean` 与 `std_ddof0`。
- **布局**：横向条形图，x 轴 `Waveform RMSE (normalized, z-score aligned vs belt)`，误差线 `capsize=3`。
- **注意**：BreatheCS RMSE 取波形分支 `draft_w_rl`（0.937），**不另列 BreatheCS-Wave 行**（二者 RMSE 相同，正文已说明）。
- **与 Fig 7 的关系**：本图为「表 6.4 的主图」；现有 Fig 7（BPM×RMSE 散点）是否保留/替换 → **[待确认]**（默认保留作为 trade-off 补充图）。

**题注**：

> **Fig. 6.4 — Waveform recovery RMSE across 12 HKH recordings.** Mean normalized RMSE (vs belt ground truth) with cross-scenario std. BreatheCS (0.937) is lowest; the WiFi-Sleep and Pos-Free baselines cluster around 1.05–1.07.

---

### 4.4 Fig 8-A —— 表 8-A（融合层级消融，加误差线）

**做法**：修改 `paper_fig8_abc_fusion.png/.pdf`。

- **三 panel（1×3 横向条形）**：
  - (a) Spectral BPM：No fusion 1.640(±0.464) / Channel only 0.381(±0.116) / Modal only 0.655(±0.245) / **BreatheCS 0.371(±0.128)**
  - (b) Waveform BPM：1.192(±1.137) / 1.003(±1.193) / 1.025(±0.988) / **0.385(±0.113)**
  - (c) Waveform RMSE：1.007(±0.180) / 0.962(±0.195) / 0.986(±0.178) / **0.937(±0.201)**
- **改动点**：
  1. BreatheCS 列用 `draft_s_rl`/`draft_w_rl`（不是 `draft_s_full`/`draft_w_full`）。
  2. **加误差线**（当前 `_barh_panel` 无 `xerr`）。
  3. **删除各 panel 的 `set_title("(a) Fusion levels · ...")`**；改为图外 caption 说明。panel 内如需区分，仅用面板字母 (a)(b)(c) 作左上角小标（可选，非题注）。
- **颜色**：BreatheCS 红 #E63946，其余灰 #999999（消融统一灰，突出主方法）。

**题注**：

> **Fig. 8a–c — Fusion-level ablation.** (a) Spectral BPM, (b) waveform BPM, (c) waveform RMSE. Bars: no fusion / channel only / modal only / BreatheCS. Channel-level fusion contributes the dominant gain (1.640→0.381 BPM); modal-level fusion adds a smaller, secondary improvement.

---

### 4.5 Fig 8-B —— 表 8-B（单模态消融，加误差线）

**做法**：修改 `paper_fig8_def_single_modal.png/.pdf`。

- **三 panel（1×3 横向条形）**，每 panel 4 柱（Remote / Local / Phase / BreatheCS）：
  - (d) Spectral BPM：0.376(±0.115) / 0.378(±0.119) / 2.191(±1.302) / **0.371(±0.128)**
  - (e) Waveform BPM：0.399(±0.121) / 0.439(±0.217) / 2.395(±1.169) / **0.385(±0.113)**
  - (f) Waveform RMSE：0.931(±0.207) / 0.947(±0.214) / 1.109(±0.111) / **0.937(±0.201)**
- **改动点**：同 4.4——BreatheCS 用 `draft_s_rl`/`draft_w_rl`；加误差线；删 panel 标题（改用 (d)(e)(f) 小标或 caption）。
- **颜色**：Remote/Local/Phase 灰，BreatheCS 红。

**题注**：

> **Fig. 8d–f — Single-modal ablation.** (d) Spectral BPM, (e) waveform BPM, (f) waveform RMSE. Remote and Local are nearly equivalent to BreatheCS, while composite Phase degrades sharply (≈2.2–2.4 BPM), confirming phase is unreliable for human-subject respiration sensing and is largely deselected by BreatheCS.

---

## 5. 图表风格规范（统一约束）

1. **图内不画标题、不画题注**。所有「图 X 解读 / Fig. caption」文字写入 plan → report → skeleton 对应位置。
2. **允许上墙**：横纵坐标轴标签、图例、刻度标签、面板字母 (a)(b)(c)/(d)(e)(f)。
3. **误差线统一**：`capsize=3`（单系列横向条形）/ `capsize=2`（分组柱），颜色与柱体同色、`alpha=0.7`。
4. **配色统一**：BreatheCS 家族 `#E63946`；Pos-Free `#81B29A`；WiFi-Sleep `#3D405B`；ClessBreath `#E07A5F`；简单/消融 `#999999`。全文一致。
5. **方向统一**：单系列排行榜用**横向条形**（`barh`，方法名在 y 轴，升序），多 panel 消融也用横向条形；仅 Fig 6b（房间分组）用竖向 grouped bar。
6. **字体/尺寸**：方法名 `fontsize=8–10`；无 `suptitle`；`dpi=150`，同时出 `.png` + `.pdf`。
7. **不硬编码数值**：所有数值从 §3 数据文件读取，不写死。

---

## 6. 实现要点（给 Cursor Composer）

### 6.1 复用与修改

| 脚本 | 改动 |
|---|---|
| `notebooks/scripts/chFusion_paper_figure_redraw.py` | ① `plot_fig6a` 删星标/红字、BreatheCS 键改为 `draft_s_rl`、`draft_w_rl`、std 用 ddof=0；② `plot_fig6b` 加 `yerr`；③ 新增 `plot_rmse_leaderboard()` 读 `paper_table63b_per_room_std.json` 的 `table_64_waveform_rmse` |
| `notebooks/scripts/chFusion_paper_ablation_draft.py` | ① `PANEL_SPEC/PANEL_WAVE/PANEL_MS/PANEL_MW` 末位键改为 `draft_s_rl`/`draft_w_rl`；② `_barh_panel` 增加 `xerr` 参数；③ 删除 `set_title`，改面板字母小标 |

> 也可合并为一个新脚本 `chFusion_paper_ch6_figures.py`，统一生成五张图。推荐**复用 + 小改**，避免重写。

### 6.2 建议新增/更新模块

`src/ble_analysis/paper_naming.py`：更新 `FIG6A_METHOD_KEYS` 中 BreatheCS 键映射（`b3_b1_equal`→`draft_s_rl` 语义），并新增 RMSE 排行榜键表 `RMSE_FIG6_4_KEYS`。若嫌改动侵入，可在脚本内局部覆盖，不动公共模块。

### 6.3 伪代码（RMSE 条形图）

```python
def plot_rmse_leaderboard():
    data = load("paper_table63b_per_room_std.json")["table_64_waveform_rmse"]["methods"]
    rows = [(label(m), m["mean"], m["std_ddof0"]) for m in data.values()]  # 升序
    ax.barh(labels, means, xerr=stds, capsize=3, color=paper_color(method_key))
    ax.set_xlabel("Waveform RMSE (normalized, z-score aligned vs belt)")
    # 无 set_title；BreatheCS 红，其余按分组色
```

### 6.4 输入输出

- 输入：§3 所列 JSON（只读）。
- 输出：§4 所列 5 组 `.png` + `.pdf`（路径见 §7）。

---

## 7. 预期产出

| 产出 | 路径 |
|---|---|
| Fig 6a（改） | `outputs/figures/paper_fig6a_bpm_leaderboard.png` + `.pdf` |
| Fig 6b（改） | `outputs/figures/paper_fig6b_bpm_by_room.png` + `.pdf` |
| 表 6.4 条形图（新） | `outputs/figures/paper_fig6_4_rmse_leaderboard.png` + `.pdf` |
| Fig 8-A（改） | `outputs/figures/paper_fig8_abc_fusion.png` + `.pdf` |
| Fig 8-B（改） | `outputs/figures/paper_fig8_def_single_modal.png` + `.pdf` |
| 验证报告 | `docs/reports/paper_ch6_tables_to_figures_report.md` |
| Skeleton 更新 | `docs/paper_draft/paper_draft_skeleton.md` §6.3–§6.4 图引用 + 题注 |

---

## 8. 风险与保留问题

- **[已确认 A]** Fig 7（BPM×RMSE 散点图）→ **搁置，不处理**。本次只重绘/新增 §4 所列五组图，Fig 7 保持现状。
- **[已确认 B]** Fig 6a 去掉星标后，**不额外强调 BreatheCS**；仅保留「BreatheCS 家族红色」作为统一分组配色（非强调手段），不额外加星/加粗/文字。
- **[已确认 C]** BreatheCS-Wave 的 std 统一按 ddof=0 → **0.113**（skeleton 中 0.118 同步改为 0.113）。
- **风险**：Fig 8 的 RMSE 误差线需从 12 个 `ble_hkh_draft_ablation_{sid}.json` 的 per-scenario `rmse_mean` 重新聚合（summary 只存 ddof=1 汇总），执行时注意按 ddof=0 重算，勿直接引用 summary 的 ddof=1 值。
- **风险**：不要误用三模态键（`draft_s_full`/`draft_w_full` = 0.405/0.744/0.951）当作 BreatheCS——它们已降为消融对照。

---

## 9. 验证状态

| 字段 | 内容 |
|---|---|
| **验证状态** | 待实现 |
| **待用户确认项** | 无（§8 三处 [待确认] 已由用户确认：Fig 7 搁置 / Fig 6a 不强调 / std 统一 0.113） |

---

## 10. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/paper_ch6_tables_to_figures_plan.md`

> **核心任务**：
> 1. 按 §2 建立方法含义 → key 映射（不改算法）。
> 2. 按 §4 逐图重绘/新增，输出到 §7 路径；std 一律 `np.std(ddof=0)`。
> 3. 删除图内标题/题注，改由正文 caption 说明；统一配色与误差线风格（§5）。
> 4. 把每张图的题注文字写入验证报告 `docs/reports/paper_ch6_tables_to_figures_report.md`。
> 5. **不重跑实验**——所有数据已有，只改绘图端。

执行完成后，请返回给 Claude/DeepSeek Review：

- `outputs/figures/paper_fig6a/6b/6_4/8_abc/8_def*.png`
- `docs/reports/paper_ch6_tables_to_figures_report.md`
- 修改后的脚本路径 + git diff 摘要
