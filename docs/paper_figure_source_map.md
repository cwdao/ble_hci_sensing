# 论文正稿插图来源与字体微调指南

> **用途**：对照 `paper_sj_ble_sensing/wang26csdf.tex` 正稿插图，定位 `ble_hci_sensing` 中的生成代码，以及**图内**标题 / 图例 / 轴标签字号改哪里。  
> **范围**：仅整理映射与改点，不自动重跑实验、不改字号。  
> **日期**：2026-08-12  
> **正稿**：`d:\Work\atomic\paper_sj_ble_sensing\`（`\graphicspath{{figs/}}`）

---

## 0. 先分清两种「字体」

| 类型 | 改哪里 | 说明 |
|------|--------|------|
| **图内文字**（legend、axes title、xlabel/ylabel、tick） | 下方 Python / drawio 源 | 改完需重导出 PDF，再复制到 `paper_sj_ble_sensing/figs/` |
| **LaTeX 题注**（`\caption{...}`） | `wang26csdf.tex` 第 37 行 `\captionsetup{font=small}`，以及各 `sections/*.tex` 的 caption 正文 | 与 matplotlib 无关；正稿已全局 `small` |

你感觉「插图字体偏小」，多数是 **图内文字**；题注另算。

**推荐微调流程**：改脚本字号 → 只重跑对应图 → 把新 `.pdf` 覆盖到 `paper_sj_ble_sensing/figs/` → 编译看效果 → 再改。

---

## 1. 正稿插图总表（按出现顺序）

| # | 正稿文件名（`figs/`） | LaTeX 位置 | `\label` | 生成方式 | 当前项目源 |
|---|----------------------|------------|----------|----------|------------|
| 1 | `BLE_HCI_Channel_sounding_Direction_finding.pdf` | `wang26csdf.tex` 摘要 wrapfigure | （无） | 外部示意图（非本仓库脚本） | **无代码**；旧素材 |
| 2 | `paper_fig1_system_overview.drawio.pdf` | `sections/intro.tex` | `fig:overview` | draw.io 导出 | `docs/figures/paper_fig1_system_overview.drawio` |
| 3 | `phase_amp_exp_settings.pdf` | `sections/model.tex` | `fig:ph_amp_exp` | 实验照片拼版 | **无脚本**；照片/排版 PDF |
| 4 | `amp_pha_complement.pdf` | `sections/model.tex` | `fig:ph_amp_complement` | 手工拼版 PDF（内嵌多图） | **无同名脚本**；内容对应 position-sweep **Fig A**（见 §3.2） |
| 5 | `position_sweep_figB2_channel_position_matrix.pdf` | `sections/model.tex` | `fig:diff_apearence_on_diff_channel` | Python | `chFusion_position_sweep_observation.py` → `plot_fig_b` |
| 6 | `position_sweep_figC1_hard_remote.pdf` | `sections/model.tex` | `fig:phase_on_diff_channel` | Python | 同上 → `plot_fig_c`（hard + remote 分支） |
| 7 | `position_sweep_figD2_dphi_vs_position_ch20_40_60.pdf` | `sections/model.tex` | `fig:phase_diff_in_diff_position` | Python | 同上 → `plot_fig_d` 拼合面板 |
| 8 | `position_sweep_figE3_eta_rho_comparison.pdf` | `sections/model.tex` | `fig:eta_rho_compare` | Python | 同上 → `plot_fig_e` |
| 9 | `paper_fig2_inter_tone_phase.pdf` | `sections/model.tex` | `fig:inter_tone` | Python | `chFusion_paper_figures_mechanism.py` → `generate_fig2` |
| 10 | `paper_fig3_ab.pdf` | `sections/model.tex` | `fig:modal_with_hilbert_fusion` | Python | 同上 → `generate_fig3` |
| 11 | `paper_fig3_cd.pdf` | `sections/model.tex` | `fig:modal_phase_diff_in_two_room` | Python | 同上 → `generate_fig3` |
| 12 | `experiment_settings.pdf` | `sections/evaluation.tex` | `fig:experiment_settings` | 人体实验照片拼版 | **无脚本** |
| 13 | `paper_fig_modal_oracle_phase_eta_hkh.pdf` | `sections/evaluation.tex` | `fig:phase_oracle_eta` | 一次性 Python 导出 | 数据来自 `modal_oracle`；**未落成独立脚本**（见 §3.4） |

说明：

- Evaluation 章大量是 **表格**，不是图。
- `paper_fig5_*` / `paper_fig6*` / `paper_fig8*` 等在本仓库曾生成，**当前正稿未引用**。
- MD5 核对（2026-08-12）：B2/C1/D2/E3、fig3_ab/cd、oracle 与 `outputs/figures/` **一致**；`paper_fig2_inter_tone_phase.pdf` 在 `outputs/figures/` 侧目前可能只有 PNG（PDF 已在正稿 `figs/`）。

---

## 2. 脚本 ↔ 产出目录速查

| 脚本 | 产出目录 | 重跑命令（示例） |
|------|----------|------------------|
| `notebooks/scripts/chFusion_position_sweep_observation.py` | `outputs/figures/position_sweep_fig*` | `python notebooks/scripts/chFusion_position_sweep_observation.py --only B,C,D,E` |
| `notebooks/scripts/chFusion_paper_figures_mechanism.py` | `outputs/figures/paper_fig2_*` / `paper_fig3_*` | `python notebooks/scripts/chFusion_paper_figures_mechanism.py --only 2,3` |
| `notebooks/scripts/chFusion_modal_oracle_diag.py` | `outputs/figures/modal_oracle_*`（双域双子图） | `python notebooks/scripts/chFusion_modal_oracle_diag.py --plot-only` |
| draw.io | 手动 Export → PDF | 打开 `docs/figures/paper_fig1_system_overview.drawio` |

复制到正稿（PowerShell 示例）：

```powershell
Copy-Item outputs\figures\<stem>.pdf d:\Work\atomic\paper_sj_ble_sensing\figs\ -Force
```

---

## 3. 可改字体：具体代码位置

### 3.1 Position sweep（正稿 #5–#8）

**文件**：`notebooks/scripts/chFusion_position_sweep_observation.py`

#### 全局默认字号

```112:115:notebooks/scripts/chFusion_position_sweep_observation.py
STYLE = {
    "linewidth": 1.6,
    "fontsize": 11,
}
```

多数 `set_xlabel` / `set_ylabel` / `set_title` 用 `fontsize=STYLE["fontsize"]`。  
**想整体加大**：先把这里的 `11` 改成 `12`/`13`，再按需改下面硬编码的 legend/tick。

#### 正稿用到的函数与硬编码字号

| 正稿图 | 函数 | 约略行号 | 图例 / 标题相关 |
|--------|------|----------|-----------------|
| B2 | `plot_fig_b` | ~672–694 | 列标题 `ax.set_title(..., fontsize=10)`；行标签 `set_ylabel(..., fontsize=10)`；`tick_params(labelsize=7)`；**无 legend** |
| C1 hard remote | `plot_fig_c` | ~727–751 | `xlabel/ylabel` → `STYLE["fontsize"]`；**legend `fontsize=7`** |
| D2 拼合 | `plot_fig_d` | ~917–956 | 子图 `set_title(..., STYLE["fontsize"])`；**各子图 legend `fontsize=8`**；单信道版 ~908 为 `fontsize=9` |
| E3 | `plot_fig_e` | ~1159–1183 | xtick `fontsize=8`；ylabel `STYLE["fontsize"]`；**合并 legend `fontsize=8`** |

C1 关键片段（改图例优先看这里）：

```742:744:notebooks/scripts/chFusion_position_sweep_observation.py
                ax.set_xlabel("Time (s)", fontsize=STYLE["fontsize"])
                ax.set_ylabel("Offset z-score", fontsize=STYLE["fontsize"])
                ax.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
```

E3 关键片段：

```1171:1176:notebooks/scripts/chFusion_position_sweep_observation.py
    ax.set_xticklabels(x_labels, fontsize=8)
    ax.set_ylabel("η (energy ratio)", fontsize=STYLE["fontsize"])
    ax2.set_ylabel("ρ (peak prominence)", fontsize=STYLE["fontsize"])
    ...
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper right")
```

PNG+PDF 双导出：`_save_png_pdf`（约 363 行）。

#### 与正稿相关、但未直接引用的 Fig A（互补波形）

正稿 `amp_pha_complement.pdf` **不是**脚本直接写出的文件名。最接近的生成逻辑是 **Fig A**：

| 产出 | 函数 | 约略行号 | 字号 |
|------|------|----------|------|
| `position_sweep_figA1_seg*_*.png` | `plot_fig_a` | ~531–554 | title/axis=`STYLE`；legend=`9` |
| `position_sweep_figA2_stitched.png` | 同上 | ~564–597 | ylabel=`9`；tick=`8`；legend=`7`；**suptitle=`12`** |
| `position_sweep_figA3_selected_positions.png` | 同上 | ~599+ | 类似 |

`amp_pha_complement.pdf` 实测为宽条拼版（约 960×198 pt，内嵌多图），更像从 A1/A2 素材**手工裁剪拼成**；draft 里还有临时截图 `docs/paper_draft/assets/image-20260811170120543.png`。  
若要加大该图字体：优先改 `plot_fig_a` 后重出 A 系列，再按你原来的版式重新导出/拼进 `figs/amp_pha_complement.pdf`。

---

### 3.2 Mechanism Fig 2 / Fig 3（正稿 #9–#11）

**文件**：`notebooks/scripts/chFusion_paper_figures_mechanism.py`

#### 全局 rcParams（先改这里最省事）

```67:78:notebooks/scripts/chFusion_paper_figures_mechanism.py
plt.rcParams.update(
    {
        "figure.dpi": 150,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "legend.fontsize": 8,
        "lines.linewidth": 1.5,
        "savefig.bbox": "tight",
        "savefig.dpi": 300,
    }
)
```

| rc 键 | 控制什么 |
|-------|----------|
| `font.size` | 默认正文/未指定处 |
| `axes.titlesize` | `set_title` 默认 |
| `axes.labelsize` | `xlabel`/`ylabel` 默认 |
| `legend.fontsize` | `ax.legend()` **未写 fontsize 时**的默认 |

#### 局部覆盖（rc 改完仍偏小就改这些）

| 图 | 函数 | 约略行号 | 注意 |
|----|------|----------|------|
| `paper_fig2_inter_tone_phase` | `generate_fig2` | ~385–396 | 组合图 legend **硬编码 `fontsize=7`**（仅 panel a） |
| `paper_fig2_a/b/c` | 同上 | ~399–408 | 各面板 legend **`fontsize=7`** |
| `paper_fig3_ab` | `generate_fig3` | ~603–627 | `ax.legend()` → 走 rc 的 `legend.fontsize` |
| `paper_fig3_cd` | 同上 | ~657–670 | legend **`fontsize=7`**；子标题为 `"Studio position 1/2"` |

Fig2 legend 硬编码示例：

```389:392:notebooks/scripts/chFusion_paper_figures_mechanism.py
        ax.set_title(title)
        ax.set_ylabel("Amplitude")
        if title == "(a)":
            ax.legend(loc="upper right", fontsize=7)
```

导出：`_save_figure`（约 81–88 行）→ `outputs/figures/{stem}.png` + `.pdf`。

---

### 3.3 Oracle η 直方图（正稿 #13）

正稿文件：`paper_fig_modal_oracle_phase_eta_hkh.pdf`

| 项 | 说明 |
|----|------|
| 数据 | `outputs/reports/modal_oracle_per_window.npy` |
| 可复用绘图逻辑 | `notebooks/scripts/chFusion_modal_oracle_diag.py` → `plot_oracle_figures` 内「Phase-best eta distribution」（约 **508–525** 行），产出是 **HKH\|CS 双子图** `modal_oracle_phase_eta_dist.png` |
| 正稿单面板 | **未写入仓库脚本**；2026-08-11 用一次性 `python -c` 从同一 npy 只画 HKH，并去掉大标题 |

双子图里与字号相关：

- `ax.legend(fontsize=8)`（约 522 行）
- `ax.set_title(...)` / `set_xlabel` / `set_ylabel` 未单独设 fontsize → 跟 matplotlib 默认 / 环境

若要反复微调正稿这张图，建议把当时的单面板导出逻辑固化成小函数或加 CLI 开关；需要时可让执行 Agent 补一刀。临时自改可参考：

```python
# 数据: outputs/reports/modal_oracle_per_window.npy
# 输出: outputs/figures/paper_fig_modal_oracle_phase_eta_hkh.{png,pdf}
# 关键字号: set_xlabel / set_ylabel / legend(fontsize=...) / 角标 text(fontsize=...)
```

---

### 3.4 非 Python / 无脚本图（正稿 #1–#3、#4、#12）

| 文件 | 性质 | 怎么改「字」 |
|------|------|--------------|
| `BLE_HCI_Channel_sounding_Direction_finding.pdf` | 旧示意图（矢量+位图混合） | 找原始 PPT/Illustrator/drawio；本仓库无生成脚本 |
| `paper_fig1_system_overview.drawio.pdf` | 系统框图 | 编辑 `docs/figures/paper_fig1_system_overview.drawio` → 选中文字改字号 → Export PDF → 覆盖 `figs/` |
| `phase_amp_exp_settings.pdf` | 金属板实验照片拼版 | 在排版软件里改标注字；无 matplotlib |
| `amp_pha_complement.pdf` | 手工拼版（见 §3.1 Fig A） | 重出 A 系列或直接在拼版源文件改字 |
| `experiment_settings.pdf` | 人体场景照片拼版 | 同照片排版；无 matplotlib |

---

## 4. 按「想改的元素」快速索引

| 想改什么 | 优先打开 |
|----------|----------|
| Fig2/Fig3 整体字号 | `chFusion_paper_figures_mechanism.py` **L67–78** `rcParams` |
| Fig2 图例仍偏小 | 同文件 **L392 / L406** 的 `fontsize=7` |
| Fig3_cd 图例 | 同文件 **~668** `fontsize=7` |
| B2 轴标题/刻度 | `chFusion_position_sweep_observation.py` **L684–688**（`10` / `7`） |
| C1 图例 | 同文件 **L744** `fontsize=7` |
| D2 图例 | 同文件 **L908**（单图 `9`）/ **L948**（拼合 `8`） |
| E3 图例与 xtick | 同文件 **L1171–1176** |
| Position 图整体轴文字 | 同文件 **L112–115** `STYLE["fontsize"]` |
| 系统框图文字 | `docs/figures/paper_fig1_system_overview.drawio` |
| LaTeX 题注字号 | `wang26csdf.tex` **L37** `\captionsetup{font=small}` |

---

## 5. 相关报告 / Plan（背景，非必须）

| 文档 | 内容 |
|------|------|
| `docs/plans/position_sweep_observation_plan.md` | B2/C1/D2/E3/A 系列规格 |
| `docs/reports/paper_figure_revision_ch4_fig23_report.md` | 2026-08-10 排版修订（去大标题、分面板、PDF） |
| `docs/plans/paper_figures_generation_plan.md` | Fig2/3/5/S1 原始计划 |
| `docs/reports/paper_figures_generation_report.md` | Fig2/3 首次生成记录 |
| `docs/paper_draft/paper_draft_skeleton.md` | draft 侧图引用与 oracle 题注 |

---

## 6. 自查备忘

- [ ] 改的是 **图内** 还是 **LaTeX caption**
- [ ] 硬编码 `fontsize=7/8` 会盖过 `rcParams` / `STYLE`
- [ ] 重跑后复制的是 **PDF**（正稿用），PNG 仅预览
- [ ] `amp_pha_complement` / 照片类图：改 Python 不会自动更新正稿文件名
- [ ] oracle 单面板：改 `modal_oracle_diag` 默认不会覆盖 `paper_fig_modal_oracle_phase_eta_hkh.*`

---

*本文档仅索引；字号最终以你编译后的 PDF 观感为准，可多次小步调整。*
