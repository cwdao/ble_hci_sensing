# 模态间相位跨窗观测图（D2 风格、按单信道、散点）— 实现计划

> **来源**：与 `position_sweep_figD2_dphi_vs_position_ch20_40_60`（D2）的"理想走廊 vs 工作室多径"对比讨论
> **目标报告**：`docs/reports/inter_modal_phase_per_channel_report.md`（模板：`docs/templates/algorithm_validation_report.md`，按图任务适配）
> **建议 plan 路径**：`docs/plans/inter_modal_phase_per_channel_plan.md`
> **日期**：2026-11-17
> **验证状态**：已完成

---

## 1. 动机与背景

D2（`position_sweep_figD2_dphi_vs_position_ch20_40_60`）在**理想空旷走廊**上，按**单信道**计算三个模态之间的相位差 Δφ(R,L) / Δφ(R,P) / Δφ(L,P)，随位置变化，观察到**大多为 0/π、仅少数非整数**。

本计划把**同一套分析**（按单信道、三模态对、D2 的 `_instantaneous_dphi` 估计器）搬到**工作室多径数据**（`cs_095806` / `cs_102621`，即 fig3_cd 的同一份数据）上，以**散点图**画出跨窗口的 Δφ。这样：

1. 与 D2 形成**同分析、只换环境**的可控对比（理想走廊 → 工作室多径）；
2. 直接回答"复杂多径下，按单信道算的模态间相位差是否也从 0/π 变成大量非整数"；
3. 与 fig3_cd（同数据、但为 **72 信道融合后**的模态间 Δφ、折线图）互为补充——本图是"按单信道"版本。

> 注意：本计划**只补图、不改算法、不改指标、不改数据、不改 GT**，属于观察性证据图。

| 项目 | 说明 |
|------|------|
| 问题 | 工作室多径下，按单信道算的模态间相位差是否出现大量非整数 π？ |
| 相关文档 | `docs/paper_draft/paper_draft_skeleton.md` §4.2/§4.4；`notebooks/scripts/chFusion_paper_figures_mechanism.py`；`chFusion_position_sweep_observation.py` |
| 本 plan 定位 | 补一张观察图（非新算法、非 benchmark） |

---

## 2. 物理与变量

### 2.1 使用变量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 三模态之一，参与 Δφ(R,L)、Δφ(R,P) |
| `local_amplitudes` | ✅ | 三模态之一，参与 Δφ(R,L)、Δφ(L,P) |
| `phases`（合成相位） | ✅ | 三模态之一，参与 Δφ(R,P)、Δφ(L,P) |
| `amplitudes`（总幅值） | ❌ | 无独立物理意义，项目约定不使用 |

### 2.2 语义边界

- 本图是 **模态间（inter-modal）、按单信道（per-channel）**，与 D2 完全同构（D2 的三对就是 R-L / R-P / L-P）。
- 它与 fig3_cd 的区别只在**聚合层级**：fig3_cd 先把 72 信道融合成一条再比模态；本图直接比单信道。
- 它与 D2 的区别只在**数据与横轴**：D2 用理想走廊、横轴=位置；本图用工作室、横轴=窗口。

### 2.3 符号约定

| 符号 | 含义 |
|------|------|
| Δφ(R,L) | remote 与 local 幅值波形间的相位差（rad） |
| Δφ(R,P) | remote 幅值与合成相位间的相位差（rad） |
| Δφ(L,P) | local 幅值与合成相位间的相位差（rad） |
| `_instantaneous_dphi(a,b)` | D2 的估计器：`angle(mean(exp(1j·angle(hilbert(a)·conj(hilbert(b))))))` |

---

## 3. 算法步骤（图生成流程）

本图**无新算法**，复用 D2 的 `_instantaneous_dphi` 与机制图管线的滤波/滑窗，只新增"按窗、按信道收集三模态对 Δφ 并散点绘图"的循环。

```text
Raw BLE CS Frames（cs_095806 / cs_102621，金属板工作室）
  │
  ├─ load_scenario + load_multichannel_for_scenario（默认三模态 remote/local/phases）
  │   [模块: chfusion.load_multichannel_for_scenario，variables=MODAL_FILTER_VARIABLES]
  │   [结果: 每模态 72 tone × T 的带通呼吸波形]
  │
  ▼
  _longest_breath_segment → 选最长呼吸段（避开 apnea）
  │
  ▼
  _segment_window_setup → 20 s / 1 s 滑窗
  [模块: segments._sliding_window_indices]
  │
  ▼
  选 K 个信道（20/40/60，已确认）
  │
  ▼
  for each window:
      for each channel ch:
          remote = ch_map[ch]["remote_amplitudes"]["bandpass_filtered"][st:end]
          local  = ch_map[ch]["local_amplitudes"]["bandpass_filtered"][st:end]
          phase  = ch_map[ch]["phases"]["bandpass_filtered"][st:end]
          Δφ(R,L) = _instantaneous_dphi(remote, local)
          Δφ(R,P) = _instantaneous_dphi(remote, phase)
          Δφ(L,P) = _instantaneous_dphi(local,  phase)
          [模块: _instantaneous_dphi（从 position_sweep 脚本 port 到 mechanism 脚本）]
      [结果: 每窗 K 信道 × 3 模态对]
  │
  ▼
  Plot（散点）: x = window index，y = Δφ(rad)
        color = 模态对（R-L / R-P / L-P），marker = 信道（20/40/60）
        2 面板 = Studio position 1 / 2；加 axhline(0) 与 ±π 虚线
  [产出: paper_fig3_modal_dphi_per_channel.{png,pdf}]
```

### 3.1 关键实现细节

- **`_instantaneous_dphi` 移植**：直接复制 [chFusion_position_sweep_observation.py:359-365](../notebooks/scripts/chFusion_position_sweep_observation.py#L359-L365) 到机制脚本（含其 `_zscore` 依赖，机制脚本已有同名 `_zscore`，注意别重复定义）。对每个 20 s 窗口直接整窗计算（**不做** D2 里 `_mid_window_slice` 的 10 s 再切片——窗口本身就是单位）。
- **信道**（已确认）：固定 `[20, 40, 60]`，与 D2 对齐，全程不按 η 替换；若某信道 η 过低导致相位纯噪声，在日志说明即可，**不得为凑结果调换信道**。
- **散点样式**：仿 D2 拼合面板——`ax.scatter`，模态对=颜色（沿用 round2 plan §3.1 的模态对三色橙/青/棕 `["#ff7f0e","#17becf","#8c564b"]`），信道=marker（`o`/`s`/`*`），双图例（颜色=模态对、marker=信道）。
- **两面板**：`cs_095806`（Studio position 1）、`cs_102621`（Studio position 2），x 轴 `Window index`、y 轴 `Δφ (rad)`。

---

## 4. 对照（Baseline）设计

本计划**不是算法 benchmark**，无 B0/B1/B2 算法基线。"对照"是图对图：

| 对照图 | 关系 | 说明 |
|--------|------|------|
| `position_sweep_figD2_dphi_vs_position_ch20_40_60` | **同分析、异环境** | 理想走廊 vs 工作室；横轴位置 vs 窗口。这是本图的核心对照 |
| `paper_fig3_cd` | 同数据、异聚合 | 72 信道融合后 vs 单信道；折线 vs 散点 |
| `paper_fig3_channel_dphi_cross_window`（上一版，信道间） | 已被本图取代 | 上一版误做成了"信道间"，本 plan 修正为"模态间按单信道" |

执行 Agent **不得**改动上述任一对照图的既有结构、数据或配色语义。

---

## 5. 评估设计

### 5.1 场景

| 场景 JSON | 用途 |
|-----------|------|
| `config/scenarios/cs_095806.json` | Studio position 1（多径工作室） |
| `config/scenarios/cs_102621.json` | Studio position 2（多径工作室） |

### 5.2 判定内容（诚实观测，不设"必须非整数"的硬指标）

本图成功与否**不取决于**它是否显示非整数 π。执行 Agent 必须如实报告：

- **现象**：两场景下，按单信道的模态间 Δφ 随窗口是否漂移？非整数 π 占比如何？
- **量化摘要（仅写进报告作诊断，非新论文指标）**：统计每个 (信道, 模态对, 窗口) 的 Δφ 到最近 π 整数倍的角距离 δ，报告"非整数占比"（δ > 0.3 rad 的比例），按场景、按信道分开。
- **两种结果的解读都要给出**：
  - 若工作室里按单信道的模态间 Δφ **大量非整数** → 与 D2（理想走廊大多 0/π）对比，直接支持"多径导致连续相偏"；
  - 若仍基本 0/π → 说明单信道层面连续偏移不显著，需结合 fig3_cd（融合后）进一步说明，结论相应收紧。
- **单场景标记**：任一结论按场景分别陈述，不得把单场景写成全局。

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | 两场景散点图生成，x/y 轴、图例、配色正确，日志记录选中信道及其 η |
| **理想** | 报告给出实际观测结果的解读，并与 D2（同分析异环境）对比 |
| **失败** | 图未生成 / 用硬编码帧 index / 为凑"非整数"而调换信道或窗口 |

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 |
|------|------|
| 改脚本 | `notebooks/scripts/chFusion_paper_figures_mechanism.py`（新增 `generate_fig3_modal_per_channel`，port `_instantaneous_dphi`） |
| 不改模块 | `src/ble_analysis/coherent_mrc.py`、`src/ble_analysis/chfusion.py` |
| 报告 | `docs/reports/inter_modal_phase_per_channel_report.md` |

### 6.2 复用 API

```python
from ble_analysis.chfusion import ChFusionConfig
# 脚本内已有: _segment_window_setup / _longest_breath_segment / _save_figure / _zscore
# 需 port: _instantaneous_dphi（来自 chFusion_position_sweep_observation.py）
```

### 6.3 接口草案

```python
def generate_fig3_modal_per_channel(data_by_scenario, cfg, metric_params, max_windows=0) -> dict:
    """在 cs_095806 / cs_102621 上，按窗、按单信道计算三模态对 Δφ 并散点绘图。
    输入: data_by_scenario = {sid: (multichannel_by_var, fs)}（multichannel_by_var 含三模态）
    输出: 保存 paper_fig3_modal_dphi_per_channel.{png,pdf}；
          返回 {channels, dphi_scenario1: (n_win,K,3), dphi_scenario2: (n_win,K,3)}
    实现要点:
      for st in starts:
          for ch in channels:
              remote/local/phase 取 ch_map[ch][var]["bandpass_filtered"][st:end]
              Δφ = _instantaneous_dphi(...) 三对
      最后 scatter：color=模态对, marker=信道, 1x2 面板。
    """
```

在 `main()` 里新增图组 token（建议 `--only 3modal`），单独可跑：

```bash
python notebooks/scripts/chFusion_paper_figures_mechanism.py --only 3modal
```

### 6.4 不做的事

- 不改算法、指标定义、baseline、原始数据/GT。
- 不重画/覆盖 D2、fig3_cd、fig2。
- 不为了"显示非整数"而 cherry-pick 信道或窗口；结果是什么就如实报什么。
- 不在本阶段写最终论文题注（题注措辞由作者定，执行 Agent 最多给建议）。
- 上一版"信道间"函数 `generate_fig3_channel` 保留还是删除，由执行 Agent 在报告里说明即可，不强制。

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| 新图 | `outputs/figures/paper_fig3_modal_dphi_per_channel.{png,pdf}` |
| 诊断数据（可选） | `outputs/figures/paper_fig3_modal_dphi_per_channel_diagnostics.npy` |
| 验证报告 | `docs/reports/inter_modal_phase_per_channel_report.md` |
| 本 plan 状态回填 | 本文件 §8 |

### 7.1 建议运行命令

```bash
python notebooks/scripts/chFusion_paper_figures_mechanism.py --only 3modal
```

---

## 8. 验证状态与保留问题

> 由 **执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | 已完成 |
| **实际脚本** | `notebooks/scripts/chFusion_paper_figures_mechanism.py`（`generate_fig3_modal_per_channel`，`--only 3modal`） |
| **报告链接** | `docs/reports/inter_modal_phase_per_channel_report.md` |
| **一句话结论** | 同一 D2 估计器下，走廊 tone 20/40/60 的非整数占比为 0.069；工作室 `cs_095806` 为 0.156（集中在 ch40 的幅值–相位对），`cs_102621` 为 0.519。不能写成两个工作室都大量非整数。 |

实际产出路径：

- 脚本：`notebooks/scripts/chFusion_paper_figures_mechanism.py`
- 数值结果：`outputs/reports/inter_modal_phase_per_channel_results.json`、`outputs/figures/paper_fig3_modal_dphi_per_channel_diagnostics.npy`
- 图表：`outputs/figures/paper_fig3_modal_dphi_per_channel.{png,pdf}`
- 报告：`docs/reports/inter_modal_phase_per_channel_report.md`

执行约定（相对 plan 正文的落实）：

- 估计器是 D2 的 `_instantaneous_dphi`，整段 20 s 窗，不再切中间 10 s。
- 滑窗长度取三条选定信道里最短的一条（两场景都是 95 点，30 窗），不用全部 72 信道里的最长信道。末尾超出该长度的窗没有这三条 tone 的样本。
- 与 fig3_cd 的差别包括聚合层级和估计器，报告不把两者的占比差只归因于融合。
- 上一版 `generate_fig3_channel` 保留，未覆盖 D2 / fig3_cd。

遗留问题：正稿题注与编号仍由作者定。D2 对照用的是已保存的 10 s 中窗结果，没有为这次对照重跑走廊数据。

### 保留问题（作者 2026-11-18 已确认，全部按默认）

- Q1：K=3，信道固定 `[20, 40, 60]`，全程不按 η 替换。
- Q2：图命名 `paper_fig3_modal_dphi_per_channel`；论文正稿编号由作者后定。

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/inter_modal_phase_per_channel_plan.md`

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/inter_modal_phase_per_channel_plan.md`
- `docs/reports/inter_modal_phase_per_channel_report.md`
- `outputs/figures/paper_fig3_modal_dphi_per_channel.{png,pdf}`
- 关键脚本路径与 git diff 摘要
