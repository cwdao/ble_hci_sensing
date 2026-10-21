# Plan: 论文表 6.3-B 缺失 per-room std 采集

## 1. 动机与背景

论文 `docs/paper_draft/paper_draft_skeleton.md` 的三张表（6.3-B、8-A、8-B）已补充标准差。其中 8-A / 8-B 全部单元格、以及 6.3-B 的 6 个 baseline 行，std 均已从现有结果文件直接补上。

唯一缺口：**Table 6.3-B 中 BreatheCS 与 BreatheCS-Wave 两行的 per-room std 没有现成字段**，需要从已存在的 `bpm_per_scenario` 数组计算后落盘为 JSON，供论文引用。

## 2. 数据源与字段

- 主文件：`outputs/reports/ble_hkh_draft_ablation_summary.json`
  - `methods["draft_s_rl"]["bpm_per_scenario"]` → BreatheCS（Spec · R+L equal, G0）12 场景均值
  - `methods["draft_w_rl"]["bpm_per_scenario"]` → BreatheCS-Wave（Wave · R+L Hilbert-MRC）12 场景均值
- baseline 对照文件：`outputs/reports/ble_hkh_paper_baselines_summary.json` 的 `by_room.{room_A,room_B,room_C}[*].bpm_std_across_scenarios`（已有，仅用于确认口径）

12 场景顺序与房间分组（与 `ble_hkh_paper_baselines_summary.json` 的 `scenario_ids` 一致）：

```text
room_A（Living sitting, idx 0–3）:
  room_A-sbj_A, room_A-sbj_B, room_A-sbj_C, room_A-sbj_D
room_B（Bedroom flat, idx 4–7）:
  room_B-sbj_A, room_B-sbj_B, room_B-sbj_C, room_B-sbj_D
room_C（Bedroom side, idx 8–11）:
  room_C-sbj_A, room_C-sbj_B, room_C-sbj_C, room_C-sbj_D
```

## 3. 算法步骤（纯统计，无信号处理）

1. 读 `draft_s_rl.bpm_per_scenario`（12 值）与 `draft_w_rl.bpm_per_scenario`（12 值）。
2. 按上述分组切为 3 组 × 4 值。
3. 对每组 4 值计算 `mean` 与 `std`（跨 4 subject）。**统一用总体 std：`np.std(ddof=0)`，N=4**。
4. 已确认 baseline 的 `bpm_std_across_scenarios` 用 `np.std(ddof=0)`（见 `chFusion_ble_hkh_paper_baselines.py` 第 232 行）。BreatheCS / BreatheCS-Wave 同样用 `ddof=0`，保证与 baseline、8-A/8-B 三表口径一致。
5. 输出统一 JSON，覆盖 6.3-B 全部 8 个方法的 per-room `mean` + `std`。

### 参考（本 plan 作者手算的临时值，仅用于 Cursor 交叉校验，不得直接当最终结果）

BreatheCS（`draft_s_rl`）per-room（ddof=0）：
- Living sitting：mean 0.356，std ≈ 0.092
- Bedroom flat：mean 0.412，std ≈ 0.169
- Bedroom side：mean 0.344，std ≈ 0.096

BreatheCS-Wave（`draft_w_rl`）per-room（ddof=0）：
- Living sitting：mean 0.358，std ≈ 0.070
- Bedroom flat：mean 0.424，std ≈ 0.139
- Bedroom side：mean 0.374，std ≈ 0.107

## 4. 实现要点

- 建议新增脚本：`notebooks/scripts/chFusion_paper_std_collection.py`（或复用现有 redraw 脚本）。
- 只读不写 `outputs/reports/ble_hkh_draft_ablation_summary.json` 与 `ble_hkh_paper_baselines_summary.json`。
- 输出：`outputs/reports/paper_table63b_per_room_std.json`，结构建议：

```json
{
  "metric": "bpm_abs_err",
  "grouping": "room (Living sitting / Bedroom flat / Bedroom side), 4 subjects each",
  "ddof": 0,
  "methods": {
    "breathecs": {
      "label": "BreatheCS",
      "source": "draft_s_rl.bpm_per_scenario",
      "per_room": { "living": {"mean": 0.356, "std": "..."}, "bedroom_flat": {...}, "bedroom_side": {...} }
    },
    "breathecs_wave": { "source": "draft_w_rl.bpm_per_scenario", "...": "..." }
  }
}
```

## 5. 顺带核对（非必做，但建议）

- **Remote 波形 RMSE 不一致（已解决）**：以 `draft_mw_remote.rmse_mean = 0.9306` 为准，论文 Table 8-B 已更正为 **0.931**。
- **ddof 口径（已统一 ddof=0）**：`ble_hkh_draft_ablation_summary.json` 的 `bpm_std_abs_err`/`rmse_std` 为样本 std（ddof=1）；`ble_hkh_paper_baselines_summary.json` 的 `bpm_std_across_scenarios` 与 `gate_decomposition_hkh.json` 的 `cross_std` 均为总体 std（ddof=0）。论文已统一为 ddof=0：8-A/8-B 的 std 已按 √(11/12) 由 ddof=1 折算为 ddof=0。
- **Table 6.4 Waveform RMSE std 待核对（交 Cursor）**：论文 Table 6.4（及正文 6.4 处「0.937±0.209」）BreatheCS RMSE std 仍为 0.209（`draft_w_rl.rmse_std` 的 ddof=1 值），与 Table 8-B 的 0.201（ddof=0）不一致。请 Cursor：① 确认 Table 6.4 各 baseline RMSE std（0.250/0.245/0.182/0.241/0.211）来自哪个文件、用哪个 ddof；② 若为 ddof=1，则整表按 √(11/12) 折算为 ddof=0，并将 BreatheCS 0.209 改为 0.201，正文「0.937±0.209」同步改为「0.937±0.201」。

## 6. 预期产出

- `outputs/reports/paper_table63b_per_room_std.json`
- 回填论文 Table 6.3-B 的 BreatheCS / BreatheCS-Wave 两行 std，并更新表下注记。
- 如需，同步修正 Remote RMSE 与 ddof 口径问题。

## 7. 验证状态

状态：已完成

实际产出路径：
- 脚本：`notebooks/scripts/chFusion_paper_std_collection.py`
- 数值结果：`outputs/reports/paper_table63b_per_room_std.json`
- 图表：无（纯统计汇总，plan 未要求图）
- 报告：`docs/reports/paper_std_collection_report.md`
- 论文回填：`docs/paper_draft/paper_draft_skeleton.md`、`docs/paper_draft/latex.md`

结论摘要：
- BreatheCS / BreatheCS-Wave 的 per-room std（ddof=0，N=4）与 plan 手算值一致（差 < 0.0015），已写入 Table 6.3-B。
- Table 6.4 原 RMSE std 确认为 `chFusion_paper_figure_redraw.py` 的 `np.std(ddof=1)`。已按 √(11/12) 折为 ddof=0。BreatheCS 由 0.209 改为 0.201，与 Table 8-B 一致。WiFi-Sleep (√η) 原为「—」，已用同一 per-scenario RMSE 补为 0.228。
- Remote 波形 RMSE 按 plan 视为已解决，未再改 Table 8-B。

遗留问题：
- `docs/paper_draft/paper_draft_old.md` 未同步。
- `latex.md` 中 Table 8-A / 8-B 仍是旧数字（无 std），本 plan 未要求改这两张表。
- Fig 6 / Fig 7 未按新 std 重绘。
