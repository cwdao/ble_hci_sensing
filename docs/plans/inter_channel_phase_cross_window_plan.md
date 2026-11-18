# 信道间相位跨窗观测图（fig3 信道版）— 实现计划

> **来源**：论文 §4.3 的"信道间残余相位偏移场景依赖"结论（`docs/paper_draft/paper_draft_skeleton.md` §4.3）与 fig3_cd 的模态间跨窗图对照讨论
> **目标报告**：`docs/reports/inter_channel_phase_cross_window_report.md`（模板：`docs/templates/algorithm_validation_report.md`，按图任务适配）
> **建议 plan 路径**：`docs/plans/inter_channel_phase_cross_window_plan.md`
> **日期**：2026-11-17
> **验证状态**：已完成

---

## 1. 动机与背景

论文 §4.3（Inter-Channel）已断言"信道间残余相位偏移**随 tone pair 和场景变化**"（见 draft §4.3 "频率选择性多径"段），但目前 §4.3 只配了 Fig 2（单窗、4 条 tone 的时域波形，含一条中间相位 tone），**没有"Δφ 随窗口变化"的时间序列图**。相反，§4.4（Inter-Modal）的 fig3_cd 已经有了模态间 Δφ 的跨窗时间序列。

本计划在 **fig3_cd 的同一份工作室（多径）数据**上，补一张**信道间 Δφ 的跨窗时间序列图**，从而：

1. 填补 §4.3 缺失的"跨窗时间序列"证据；
2. 与 fig3_cd（模态间）形成**同数据、只换"信道 vs 模态"一个变量的可控对比**；
3. 直接验证 draft §4.3 已写下但尚未配图的"场景依赖"结论。

> 注意：本计划**只补图、不改算法、不改指标、不改数据、不改 GT**，属于观察性证据图。

| 项目 | 说明 |
|------|------|
| 问题 | 复杂多径（工作室）下，信道间相位偏移是否也像模态间那样出现大量非整数 π？ |
| 相关文档 | `docs/paper_draft/paper_draft_skeleton.md` §4.3/§4.4；`notebooks/scripts/chFusion_paper_figures_mechanism.py` |
| 本 plan 定位 | 补一张观察图（非新算法、非 benchmark） |

---

## 2. 物理与变量

### 2.1 使用变量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 与 Fig 2 / §4.3 一致，"信道间"= 同一模态（remote 幅值）内不同 tone 的相位关系 |
| `local_amplitudes` | ❌ | 本图只谈信道间，不需要跨模态；避免与 fig3_cd（模态间）语义混叠 |
| `phases`（合成相位） | ❌ | 同上 |
| `amplitudes`（总幅值） | ❌ | 无独立物理意义，项目约定不使用 |

### 2.2 语义边界（避免再次混淆）

- **信道间** = 同一模态内，不同 CS tone 之间的相位关系 → 属于 §4.3，配 Fig 2（单窗）与本计划新图（跨窗）。
- **模态间** = remote/local/phase 三个模态之间的相位关系 → 属于 §4.4，配 Fig 3（ab + cd，其中 cd 为跨窗）。
- 本图是**信道间**，挂 §4.3，只是用工作室（多径）数据来画，用于与 fig3_cd（模态间、同数据）做可控对比。

### 2.3 符号约定

| 符号 | 含义 |
|------|------|
| Δφ(ch, ref) | tone ch 相对参考 tone 的相位差（rad），= `angle(Σ_t z_ch·conj(z_ref))` |
| η | 呼吸频段能量比（选参考 tone 的质量依据之一） |
| ρ | 谱峰突出度 |

---

## 3. 算法步骤（图生成流程）

本图**无新算法**，复用现有机制图管线的滤波、滑窗、相位估计，只新增"按窗收集信道间 Δφ 并绘图"的循环。

```text
Raw BLE CS Frames（cs_095806 / cs_102621，金属板工作室）
  │
  ├─ load_scenario + load_multichannel_for_scenario（remote_amplitudes）
  │   [模块: chfusion.load_multichannel_for_scenario]
  │   [维度: 72 tone × T，已滤波为带通呼吸波形]
  │
  ▼
  _longest_breath_segment → 选最长呼吸段（避开 apnea）
  │
  ▼
  _segment_window_setup → 20 s / 1 s 滑窗
  [模块: segments._sliding_window_indices]
  [维度: 每窗 72 tone × win_len]
  │
  ▼
  选固定参考 tone ref_fixed（一次选定，跨窗不变）   [待确认 Q1]
  │
  ▼
  for each window:
      X, eta, rho = _collect_modal_window_matrix(remote_amplitudes)
      [维度: 72 tone × win_len]
      │
      ▼
      phases = estimate_phase_hilbert(X, q=eta·ρ, ref_idx=ref_fixed)
      [模块: coherent_mrc.estimate_phase_hilbert；ref_idx 固定]
      [结果: 72 个标量，phases[i]=Δφ(tone_i, ref)]
      │
      ▼
      记录 phases[K 个选中 tone] → (n_windows × K) 矩阵
  │
  ▼
  Plot：x = window index，y = Δφ(rad)，2 面板 = Studio position 1/2
  [产出: paper_fig3_channel_dphi_cross_window.{png,pdf}]
```

### 3.1 关键实现细节

- **固定参考 tone**（Q1）：建议 `ref_fixed` 选"跨所有窗中位 η·ρ 最高的 tone"，跨窗不变，避免逐窗换 ref 导致序列跳变。`estimate_phase_hilbert(..., ref_idx=ref_fixed)` 已支持显式传 `ref_idx`（[coherent_mrc.py:119-123](../src/ble_analysis/coherent_mrc.py#L119-L123)），可直接复用。
- **选中 tone**（Q2）：固定 K=3 个 tone（非 ref），默认取 spaced 索引 `[20, 40, 60]` 以对齐 D2 的"两三个信道"；若其中某个是 ref 或 η 过低（相位噪声大），则顺延替换并在日志说明，**不得为凑结果调换 tone**。
- **两面板**：`cs_095806`（Studio position 1）、`cs_102621`（Studio position 2），与 fig3_cd 完全同构（x 轴 `Window index`，y 轴 `Δφ (rad)`，加 `axhline(0)` 与 ±π 参考虚线）。
- **配色**：沿用信道专用定性色集 `["#ff7f0e","#17becf","#2ca02c"]`（避开单模态红/蓝/紫与模态对橙/青/棕，见 round2 plan §3.1）。

---

## 4. 对照（Baseline）设计

本计划**不是算法 benchmark**，无 B0/B1/B2 算法基线。这里的"对照"是**图对图**：

| 对照图 | 关系 | 说明 |
|--------|------|------|
| `paper_fig3_cd` | 同数据、模态间 | 本图与它在同一工作室数据上，形成"信道 vs 模态"可控对比 |
| `paper_fig2_inter_tone_phase` | 同主题、单窗 | 信道间相位的既有证据（单窗波形），本图补其跨窗时间序列 |
| `position_sweep_figD2_dphi_vs_position_ch20_40_60` | 单一分量对照 | 理想走廊下模态间的跨位置 Δφ（大多 0/π），用于正文叙事"理想→多径" |

执行 Agent **不得**改动上述任一对照图的既有结构、数据或配色语义。

---

## 5. 评估设计

### 5.1 场景

| 场景 JSON | 用途 |
|-----------|------|
| `config/scenarios/cs_095806.json` | Studio position 1（多径工作室） |
| `config/scenarios/cs_102621.json` | Studio position 2（多径工作室） |

### 5.2 判定内容（诚实观测，不设"必须非整数"的硬指标）

本图成功与否**不取决于**它是否显示非整数 π。执行 Agent 必须如实报告观测结果：

- **现象**：两场景下，信道间 Δφ 随窗口是否漂移？是否存在非整数 π（离最近 π 整数倍的距离 > 阈值，如 0.3 rad）？
- **量化摘要（仅写进报告作诊断，非新论文指标）**：统计每个 (tone, window) 对的 Δφ 到最近 π 整数倍的角距离 δ，报告"非整数占比"（δ > 0.3 rad 的比例），按场景分开。
- **两种结果的解读都要给出**：
  - 若信道间 Δφ 大量非整数 → 印证 §4.3"场景依赖"，且与 fig3_cd（模态间）同构；
  - 若信道间 Δφ 仍基本 0/π、只有模态侧非整数 → 说明连续偏移是 composite phase 特有结构所致，收紧 §4.4 模态专属叙事。
- **单场景标记**：任一结论都按场景分别陈述，不得把单场景写成全局。

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | 两场景图生成，x/y 轴、图例、配色正确，日志记录 ref_fixed 与选中 tone 及其 η |
| **理想** | 报告给出两种结果中实际那一种的解读，并与 fig3_cd 同数据对比 |
| **失败** | 图未生成 / 用硬编码帧 index / 为凑"非整数"而调换 tone 或窗口 |

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 |
|------|------|
| 改脚本 | `notebooks/scripts/chFusion_paper_figures_mechanism.py`（新增 `generate_fig3_channel`，复用现有 helper） |
| 不改模块 | `src/ble_analysis/coherent_mrc.py`（只调用 `estimate_phase_hilbert`） |
| 报告 | `docs/reports/inter_channel_phase_cross_window_report.md` |

### 6.2 复用 API

```python
from ble_analysis.chfusion import ChFusionConfig
from ble_analysis.coherent_mrc import estimate_phase_hilbert
from ble_analysis.wifi_mrc import _collect_modal_window_matrix
from ble_analysis.segments import _sliding_window_indices
# 脚本内已有: _segment_window_setup / _longest_breath_segment / _save_figure
```

### 6.3 接口草案

```python
def generate_fig3_channel(data_by_scenario, cfg, metric_params, max_windows=0) -> dict:
    """在 cs_095806 / cs_102621 上，按窗收集 remote_amplitudes 的信道间 Δφ 并绘图。
    输入: data_by_scenario = {sid: (multichannel, fs)}（同 generate_fig3）
    输出: 保存 paper_fig3_channel_dphi_cross_window.{png,pdf}；
          返回 {ref_tone, selected_tones, dphi_scenario1, dphi_scenario2}
    实现要点:
      ref_fixed 一次选定；每窗 estimate_phase_hilbert(X, q, ref_idx=ref_fixed)
      记录 phases[selected_tones]；最后画 1x2 面板（x=Window index, y=Δφ rad）。
    """
```

在 `main()` 里新增图组 token（建议 `--only 3channel`），单独可跑：

```bash
python notebooks/scripts/chFusion_paper_figures_mechanism.py --only 3channel
```

### 6.4 不做的事

- 不改算法、指标定义、baseline、原始数据/GT。
- 不重画/覆盖 fig3_cd、fig2、D2。
- 不为了"显示非整数"而 cherry-pick tone 或窗口；结果是什么就如实报什么。
- 不在本阶段写最终论文题注（题注措辞由作者定，执行 Agent 最多给建议）。

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| 新图 | `outputs/figures/paper_fig3_channel_dphi_cross_window.{png,pdf}` |
| 诊断数据（可选） | `outputs/figures/paper_fig3_channel_diagnostics.npy` |
| 验证报告 | `docs/reports/inter_channel_phase_cross_window_report.md` |
| 本 plan 状态回填 | 本文件 §8 |

### 7.1 建议运行命令

```bash
python notebooks/scripts/chFusion_paper_figures_mechanism.py --only 3channel
```

---

## 8. 验证状态与保留问题

> 由 **执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | 已完成 |
| **实际脚本** | `notebooks/scripts/chFusion_paper_figures_mechanism.py`（`generate_fig3_channel`，`--only 3channel`） |
| **报告链接** | `docs/reports/inter_channel_phase_cross_window_report.md` |
| **一句话结论** | 固定 tone 20/40/60 的信道间 Δφ 随场景不同：`cs_095806` 非整数占比 0.230，`cs_102621` 为 0.642；不能写成与 fig3_cd 同构的全局结论。 |

执行采用的定义（作者 2026-11-17 确认）：

- 信道号固定为 20、40、60，全程不按 η 替换。
- Δφ 只在这三条 tone 的三对之间计算（ch40−ch20、ch60−ch20、ch60−ch40），不再另选质量最高的参考 tone。
- 图名用 `paper_fig3_channel_dphi_cross_window`。未做 2×2 合图。

实际产出路径：

- 脚本：`notebooks/scripts/chFusion_paper_figures_mechanism.py`
- 数值结果：`outputs/reports/inter_channel_phase_cross_window_results.json`、`outputs/figures/paper_fig3_channel_diagnostics.npy`
- 图表：`outputs/figures/paper_fig3_channel_dphi_cross_window.{png,pdf}`
- 报告：`docs/reports/inter_channel_phase_cross_window_report.md`

结论摘要：两场景都用最长非 apnea 段 `1b`。Studio position 1 多数窗口仍靠近 0 或 ±π；Studio position 2 约六成窗口落在非整数相位。同段模态间 fig3_cd 的非整数占比分别约 0.659 与 0.699。

遗留问题：Q4 的 2×2 合图未做；正稿题注与编号仍由作者定。`cs_102621` 的 tone 40 中位 η 只有 0.392，已按确认保留。

### 保留问题（交付前由作者拍板）

| ID | 问题 | 选项 | 建议默认 |
|----|------|------|----------|
| Q1 | 参考 tone 选法 | (a) 固定 ref=跨窗中位 η·ρ 最高 tone；(b) 逐窗 argmax η·ρ（复用 estimate_phase_hilbert 默认） | (a) 固定 ref，序列更干净 |
| Q2 | 选中 tone 数量与索引 | spaced `[20,40,60]` 或高 η 代表 tone | K=3，默认 `[20,40,60]`（对齐 D2） |
| Q3 | 输出图命名 / 论文正稿编号 | `paper_fig3_channel_dphi_cross_window` 或其它 | 先按此命名，正稿编号由作者定 |
| Q4 | 是否另出一张 2×2 合图（上：模态间 fig3_cd；下：信道间本图） | 要 / 不要 | 先出独立图，2×2 合图可选 |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/inter_channel_phase_cross_window_plan.md`

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/inter_channel_phase_cross_window_plan.md`
- `docs/reports/inter_channel_phase_cross_window_report.md`
- `outputs/figures/paper_fig3_channel_dphi_cross_window.{png,pdf}`
- 关键脚本路径与 git diff 摘要
