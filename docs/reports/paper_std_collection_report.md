# 论文表 6.3-B per-room std 采集 — 验证报告

> **Plan**：[`docs/plans/paper_std_collection_plan.md`](../plans/paper_std_collection_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_paper_std_collection.py`  
> **场景**：HKH 12 scenario，顺序与 `outputs/reports/ble_hkh_paper_baselines_summary.json` 的 `scenario_ids` 一致（未重跑场景 JSON）  
> **日期**：2026-10-22  
> **状态**：已完成

---

## 1. 目标与假设

从已有 `bpm_per_scenario` 计算 Table 6.3-B 中 BreatheCS 与 BreatheCS-Wave 的 per-room 总体标准差，并核对 Table 6.4 的 RMSE std 是否仍为样本标准差。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | BreatheCS / BreatheCS-Wave 的 per-room mean、std（ddof=0，N=4）与 plan 手算值一致 | §3 |
| H2 | Table 6.4 baseline RMSE std 来自 `np.std(ddof=1)`，可按 √(11/12) 折为 ddof=0 | §5 |

---

## 2. 方法摘要

只读现有结果，不改源 JSON，不重跑感知算法。

| 项目 | 内容 |
|------|------|
| 观测量 | 无新观测量；使用已落盘的 BPM abs err 与 waveform RMSE |
| 分组 | room_A / room_B / room_C 各 4 subject，idx 0–3 / 4–7 / 8–11 |
| 标准差 | 总体 std，`np.std(ddof=0)` |
| 6.3-B BreatheCS | `ble_hkh_draft_ablation_summary.json` → `draft_s_rl.bpm_per_scenario` |
| 6.3-B BreatheCS-Wave | 同文件 → `draft_w_rl.bpm_per_scenario` |
| 6.3-B baseline | `ble_hkh_paper_baselines_summary.json` → `by_room.*.bpm_std_across_scenarios` |
| 6.4 RMSE | 逐场景 `rmse_mean` 重算；baseline 取 `leaderboard_bpm`（与 `chFusion_paper_figure_redraw.py` 相同） |

---

## 3. 实验设置

- **Baseline**：Table 6.3-B 的 6 个外部方法，数字直接引用已有 `bpm_std_across_scenarios`（ddof=0），未重算定义。
- **待补方法**：BreatheCS（`draft_s_rl`）、BreatheCS-Wave（`draft_w_rl`）。
- **指标**：per-room BPM abs err 的 mean / std；12 场景 waveform RMSE 的 std。
- **场景配置**：未读取 `config/scenarios/cs_*.json`。本任务是 HKH 论文表统计，场景列表来自上述 summary 的 `scenario_ids`，并与 `chFusion_paper_ablation_draft.py` 的 `SCENARIO_IDS` 一致。

---

## 4. 结果

### 4.1 Table 6.3-B（BPM abs err，括号内为 ddof=0 std）

三位小数。来源：`outputs/reports/paper_table63b_per_room_std.json`。

| 方法 | Living sitting | Bedroom flat | Bedroom side |
|------|----------------|--------------|--------------|
| **BreatheCS** | **0.356 (0.092)** | **0.412 (0.169)** | **0.344 (0.096)** |
| Pos-Free (PCA) | 0.415 (0.091) | 0.436 (0.182) | 0.455 (0.057) |
| WiFi-Sleep (MRC-PCA) | 0.609 (0.123) | 0.451 (0.176) | 0.455 (0.065) |
| BreatheCS-Wave | 0.358 (0.070) | 0.424 (0.139) | 0.374 (0.107) |
| WiFi-Sleep (√η) | 1.521 (1.895) | 0.532 (0.205) | 1.016 (0.787) |
| PCA sign only | 1.365 (0.806) | 1.212 (0.449) | 1.373 (0.618) |
| ClessBreath (η-linear) | 1.498 (2.070) | 1.225 (1.286) | 1.434 (1.593) |
| ClessBreath (η-equal) | 1.400 (1.709) | 2.038 (1.723) | 1.022 (0.758) |

BreatheCS 全精度 std：living 0.092311，bedroom flat 0.168999，bedroom side 0.095855。BreatheCS-Wave：0.069604，0.138732，0.106760。与 plan 手算值之差均小于 0.0015。

### 4.2 Table 6.4 waveform RMSE std

原发表 std 与重算 `np.std(ddof=1)` 四舍五入到三位小数后逐项一致。ddof=0 = ddof=1 × √(11/12)，脚本内用原始 12 点重算并核对换算误差 < 1e-12。

| 方法 | RMSE mean | 原 std（ddof=1） | 新 std（ddof=0） |
|------|----------:|-----------------:|-----------------:|
| **BreatheCS** | **0.937** | 0.209 | **0.201** |
| Pos-Free (PCA) | 1.070 | 0.250 | 0.239 |
| WiFi-Sleep (MRC-PCA) | 1.063 | 0.245 | 0.234 |
| WiFi-Sleep (√η) | 1.054 | 0.238（原表为「—」） | 0.228 |
| PCA sign only | 1.085 | 0.182 | 0.174 |
| ClessBreath (η-linear) | 1.025 | 0.241 | 0.231 |
| ClessBreath (η-equal) | 1.046 | 0.211 | 0.202 |

WiFi-Sleep (√η) 的 RMSE 序列在逐场景 baseline JSON 中完整（N=12）。原表为空，是因为 `RMSE_TABLE_KEYS` 未包含 `mrc_pca_eta_sqrt`，不是因为缺数。已按 plan「整表折算」补上 ddof=0。

### 4.3 与 plan 预期对比

| 预期（Plan） | 实际 | 是否一致 |
|-----------------|------|----------|
| BreatheCS living / flat / side std ≈ 0.092 / 0.169 / 0.096 | 0.092 / 0.169 / 0.096 | ✅ |
| BreatheCS-Wave std ≈ 0.070 / 0.139 / 0.107 | 0.070 / 0.139 / 0.107 | ✅ |
| baseline `bpm_std_across_scenarios` 为 ddof=0 | `chFusion_ble_hkh_paper_baselines.py` 第 232 行 `np.std(..., ddof=0)`，且与表中已有括号值一致 | ✅ |
| Table 6.4 若为 ddof=1 则整表折算，BreatheCS 0.209 → 0.201 | 已确认并改表；正文「0.937±0.209」改为「0.937±0.201」 | ✅ |

未改 `ble_hkh_draft_ablation_summary.json` 与 `ble_hkh_paper_baselines_summary.json`。Remote RMSE（`draft_mw_remote.rmse_mean = 0.9306`，Table 8-B 已是 0.931）按 plan 视为已解决，未再修改。

---

## 5. 结论

### 已验证

- BreatheCS 与 BreatheCS-Wave 的三房间 BPM abs err 总体标准差已从 `bpm_per_scenario` 算出，并回填 `paper_draft_skeleton.md` 与 `latex.md` 的 Table 6.3-B。
- Table 6.4 的 RMSE std 原为 12 场景样本标准差。折成总体标准差后，BreatheCS 为 0.201，与 Table 8-B 一致。

### 仅单场景

- 无。统计覆盖 HKH 全部 12 条记录，按 3 个房间各 4 人分组。

### 未证实

- 无新算法结论。本轮只统一已有数字的标准差口径。

### 已废弃

- Table 6.4 中基于 ddof=1 的 RMSE std（含正文 0.937±0.209）不再作为论文口径。

---

## 6. 开放问题与下一步

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | `paper_draft_old.md` 仍是旧 std | 若该文件仍被引用，再单独同步 |
| Q2 | `latex.md` 的 Table 8-A / 8-B 未带 std，与 skeleton 不一致 | 不在本 plan 范围；需要时另开同步 |
| Q3 | Fig 6 / Fig 7 未按新 std 重绘 | 误差棒若使用这些 std，需另一次绘图 |

---

## 7. 复现

```bash
python notebooks/scripts/chFusion_paper_std_collection.py
```

| 产出 | 路径 |
|------|------|
| 数值报告 | `outputs/reports/paper_table63b_per_room_std.json` |
| 图表 | 无 |
| 本报告 | `docs/reports/paper_std_collection_report.md` |

---

## 8. Plan 回填（执行 Agent 更新 plan 末尾）

- **验证状态**：已完成
- **实际脚本**：`notebooks/scripts/chFusion_paper_std_collection.py`
- **结论一句话**：BreatheCS / BreatheCS-Wave 的 per-room std 已按 ddof=0 落盘并回填；Table 6.4 RMSE std 已从 ddof=1 折为 ddof=0，BreatheCS 为 0.201。
