# B3 Simplified CS 金属板三场景验证 — 实现计划

> **来源**：[Review B3 Simplified Full Validation](#) — P1 任务  
> **目标报告**：`docs/reports/b3_cs_metal_plate_validation_report.md`（模板：`docs/templates/algorithm_validation_report.md`）  
> **日期**：2026-07-12  
> **验证状态**：待实现

---

## 1. 动机与背景

### 1.1 问题

B3 Simplified（逐模态 Voting → 三模态等权谱融合 BPM + 两级 Hilbert-MRC 波形）在 HKH 12 场景真人数据上确认：

| 指标 | B3 Simplified | B1 Vote→Equal | B2-D |
|------|-------------|--------------|------|
| BPM (HKH 12场景) | **0.405** | 0.405 | 0.68 |
| RMSE (HKH 12场景) | **0.950** | N/A | 0.950 |

但 **CS 金属板三场景**（091339/095806/102621）尚未验证。当前 methods README 中该条目标注为 `[待确认]`。

### 1.2 为什么需要单独验证

- **场景差异**：HKH 为真人自由呼吸（多房间多姿势），CS 为金属板脚本呼吸（固定 BPM 序列）。多径环境、体动、呼吸模式均不同。
- **指标差异**：HKH 用 BPM 绝对误差（breaths/min），CS 用 BPM 相对误差 %——不可直接比较。
- **历史教训**：B2-D 在 HKH outlier 场景（A-D/C-A）上 BPM 崩溃，但 CS 场景上 B2-D 跨域 9.43% 相对尚可。B3 Simplified 在 CS 上的 RMSE 是否仍保持 0.950 量级，需实测确认。
- **Coherence gate 问题**：B3 Simplified 移除了 coherence gate（HKH 上 ΔRMSE=+0.001），但 CS 场景上 coherence gate 效果可能不同（B3 plan Q4 保留问题）。

### 1.3 本 plan 定位

**轻量级验证**：不做新方法设计。将 B3 Simplified（`b3_pipeline.py` 的 `B3_SIMPLIFIED_CONFIG`）在 CS 三场景上跑 `chFusion_ble_hkh_b3_validation.py --mode simplified` 的 CS 适配版，产出 BPM（±%）和 RMSE 与 B1/B2-D baseline 的对比。

- **若 B3 Simplified BPM ≡ B1（跨域 8.45%）且 RMSE ≤ B2-D（~0.95）**：CS `[待确认]` 解除，B3 Simplified 推荐状态扩展至 CS 域。
- **若 B3 Simplified BPM 或 RMSE 退化**：记录退化量和可能原因（coherence gate？场景差异？），标注为 HKH-only 推荐。

---

## 2. 物理与变量

与 B3 plan §2 完全一致：

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 远端幅值 |
| `local_amplitudes` | ✅ | 物理上与 remote 对等 |
| `phases` | ✅ | 两端 PCT 向量相乘后总相位 |
| `amplitudes`（总幅值） | ❌ | 无独立物理意义 |

---

## 3. 算法步骤

### 3.1 管线（无改动）

B3 Simplified ≡ B1 Voting BPM + B2-D 精简波形，与 HKH 验证完全相同的管线：

```text
Raw BLE CS Frames (72 tone × 3 variables)
  │
  └─► Filter Chain (per tone, per variable):
        median(w=3) → highpass(0.05 Hz) → bandpass(0.1–0.35 Hz)
      │
      ▼
  Sliding Window: 20 s / 1 s step
      │
      ▼
  Shared Frontend: _collect_modal_window_matrix()
    η[72], ρ[72], spectra[72, nfft]
      │
      ├─► BPM 路径 (= B1 Vote→Equal):
      │     η·ρ Voting → per-modal weighted_spectrum
      │     → 三模态等权谱融合 (1:1:1) → argmax → BPM
      │
      └─► 波形路径 (= B2-D 精简, min_coherence=0.0):
            两级 Hilbert 相位对齐 → 最终波形 → RMSE
```

**与 HKH 验证的唯一差异**：GT 来源不同——CS 场景使用金属板脚本 BPM GT（`bpm_gt` 字段），无 HKH 呼吸带波形 GT。因此 **RMSE 在 CS 场景上不可计算**（无 ground truth 波形）。CS 验证仅比较 BPM。

> 若需要波形质量评估，可用 B2-D CS 场景的 RMSE（vs 自身或其他参照）作为代理，但非本 plan 范围。

### 3.2 不做的事

- 不修改 `b3_pipeline.py` 任何逻辑
- 不新增滤波参数、滑窗参数、指标定义
- 不新增消融变体
- 不重跑 B1/B2-D baseline（直接引用已有 CS 结果）

---

## 4. Baseline 对比

### 4.1 外部 Baseline（引用已有 CS 结果，无需重跑）

| 方法 | CS 跨域 mean | 091339 | 095806 | 102621 | 来源 |
|------|-------------|--------|--------|--------|------|
| **B1 Vote→Equal** | **8.45%** | 13.22% | 6.50% | 5.63% | `systematic_fusion.py` — `docs/methods/README.md` §2 |
| B2-D Two-level | 9.43% | 15.01% | 5.82% | 7.45% | `coherent_mrc.py` — `docs/methods/README.md` §2 |
| G4-B1-v2 | 8.05% | 12.36% | 6.31% | 5.50% | 实验性（不推荐，fallback 硬编码 Remote） |
| B0 Single Remote | 10.45% | 10.91% | 12.16% | 8.29% | Baseline |

### 4.2 待测方法

| ID | 配置 | 来源 |
|----|------|------|
| **B3 Simplified** | `B3_SIMPLIFIED_CONFIG`（equal spectral fusion BPM + Hilbert 波形，min_coherence=0.0） | `b3_pipeline.py` |

### 4.3 预期

| 指标 | 预期 | 理由 |
|------|------|------|
| B3 Simplified BPM vs B1 | **≡ B1**（≤ 0.01 pp 差异） | B3 B1-equal 的 BPM 管线 = B1 Vote→Equal |
| B3 Simplified vs B2-D BPM | **优于 B2-D** | Voting BPM 替代波形 PSD BPM，CS 场景上 B1(8.45%) 已优于 B2-D(9.43%) |
| B3 Simplified RMSE vs B2-D | **CS 场景无波形 GT，RMSE 不可算** | `[待确认]` — 若有替代评估方案需另议 |

---

## 5. 评估设计

### 5.1 场景与指标

| 维度 | 内容 |
|------|------|
| 场景 | CS 金属板三场景：`cs_091339` / `cs_095806` / `cs_102621` |
| 配置 | `config/scenarios/cs_091339.json` 等 |
| 主指标 | **BPM 相对误差 %**（mean ± std，跨域 mean），口径与既有 CS 排行榜一致 |
| 次指标 | per-segment BPM 误差、breath-only segment BPM 误差 |
| 滑窗 | 20 s 窗长 / 1 s 步长 |
| 呼吸频段 | 0.1–0.35 Hz |
| GT | 金属板脚本 `bpm_gt`（per segment） |

### 5.2 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | B3 Simplified BPM 跨域 ≤ 8.50%（与 B1 8.45% 差距 < 0.05 pp） |
| **理想** | B3 Simplified BPM 跨域 < 8.45%（超越 B1）或 ≡ B1（差距 < 0.01 pp） |
| **失败** | B3 Simplified BPM 跨域 > 8.50%（差距 > 0.05 pp vs B1）→ 差异 root cause 分析 |

### 5.3 额外输出

- 若 B3 Simplified BPM ≠ B1 BPM（差距 > 0.01 pp），逐窗/逐段追查差异来源
- 与 HKH 结论对比：同一管线在不同场景类型上的表现差异

---

## 6. 实现要点

### 6.1 建议策略：CS 适配脚本

**新建轻量脚本**（而非修改 HKH 脚本），复用 `b3_pipeline.py`：

| 类型 | 路径 | 说明 |
|------|------|------|
| **新增脚本** | `notebooks/scripts/chFusion_b3_cs_validation.py` | CS 三场景 B3 Simplified 验证 |
| 复用模块 | `src/ble_analysis/b3_pipeline.py` | `B3_SIMPLIFIED_CONFIG` + `estimate_b3_window()` |
| 复用模块 | `src/ble_analysis/chfusion.py` | 滤波、评估（BPM 相对误差 %）、`ChFusionConfig` |
| 引用结果 | `outputs/reports/` 中已有 CS baseline JSON | B1 / B2-D / B0 数值，无需重跑 |

### 6.2 接口草案

```python
# notebooks/scripts/chFusion_b3_cs_validation.py  (伪代码)

from ble_analysis.b3_pipeline import B3_SIMPLIFIED_CONFIG, estimate_b3_window

SCENARIOS = ["cs_091339", "cs_095806", "cs_102621"]

for scenario_id in SCENARIOS:
    # 1. 加载场景 + 数据（复用既有 CS 加载管线）
    scenario = load_scenario(scenario_id)
    frames = load_frames(scenario.data_file)
    multichannel_by_var = build_multichannel(frames, filter_params)

    # 2. 逐窗 B3 Simplified
    for seg_name, seg_info in scenario.segments.items():
        if seg_info.type != "breath":
            continue  # skip apnea segments for BPM
        for st, end in sliding_windows(seg_info, win_len=20, step=1):
            result = estimate_b3_window(
                multichannel_by_var, seg_name, ch_list, st, end, fs,
                variant=B3_SIMPLIFIED_CONFIG,
                cfg=chfusion_config,
            )
            # result["bpm"] → vs seg_info.bpm_gt → relative error %

    # 3. 汇总：跨域 mean %（与 CS 排行榜口径一致）

# 4. 与 B1 / B2-D 已有 CS 结果对比（读 methods README 或既有 JSON）
```

### 6.3 注意事项

1. **CS 场景的 BPM 指标是相对误差 %**，非 HKH 的绝对误差 breaths/min——评估函数用 `_overall_rel_error()` 或等效逻辑。
2. **CS 场景含 apnea 段**（`"type": "apnea"`），BPM 评估仅对 `"type": "breath"` 段进行。
3. **CS 场景的滑窗参数**应与既有 CS 排行榜一致（20 s / 1 s），确保可比性。
4. **B1/B2-D CS 基线数值直接引用** `docs/methods/README.md` §2 排行榜，无需重跑——前提是滑窗/滤波/指标口径一致（已确认一致）。
5. **若 B3 Simplified BPM ≠ B1**（差距 > 0.01 pp），必须追查差异来源：是否 B3 wrapper 的 `_collect_modal_window_matrix()` 调用与 B1 独立运行时有所不同（fft 复用、eta/rho 计算微差等）。

### 6.4 不做的事

- 不重跑 B1/B2-D CS baseline
- 不修改 `b3_pipeline.py`
- 不新增消融变体
- 不产出波形 RMSE（CS 场景无 waveform GT）

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| CS 验证脚本 | `notebooks/scripts/chFusion_b3_cs_validation.py` |
| 每场景结果 | `outputs/reports/b3_cs_{scenario_id}_validation.json` ×3 |
| 跨场景汇总 | `outputs/reports/b3_cs_validation_summary.json` |
| CS 排行榜图（含 B3 Simplified） | `outputs/figures/b3_cs_validation_leaderboard.png` |
| 验证报告 | `docs/reports/b3_cs_metal_plate_validation_report.md` |
| Plan 回填 | 本 plan §8 |

### 建议运行命令

```bash
python notebooks/scripts/chFusion_b3_cs_validation.py
```

---

## 8. 风险与保留问题

| # | 风险 | 缓解 |
|---|------|------|
| 1 | B3 Simplified BPM ≠ B1（wrapper 微差） | 逐窗追查差异来源；若差异 < 0.01 pp 可视为等同 |
| 2 | CS 场景无波形 GT，RMSE 不可验证 | B3 Simplified 的波形 = B2-D 精简版，B2-D CS RMSE 已知（但无 GT）；如需波形质量评估需新方法 |
| 3 | CS 场景 segment 较短（如 2b 仅 36 frames） | B3 的 Voting BPM 在短窗上可能退化（投票样本少）；记录短 segment 的单独统计 |
| 4 | Coherence gate 在 CS 上可能有不同表现 | B3 Simplified 已移除 coherence gate；若 B3 Simplified BPM 退化且 B2-D BPM 更优，可能是 coherence gate 在 CS 场景有正面作用 |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，按以下顺序执行：

### Phase 1 — CS 适配脚本

1. 读取本 plan：`docs/plans/b3_cs_metal_plate_validation_plan.md`
2. 读取 `src/ble_analysis/b3_pipeline.py`（确认 `B3_SIMPLIFIED_CONFIG` 和 `estimate_b3_window()` 接口）
3. **新建** `notebooks/scripts/chFusion_b3_cs_validation.py`：
   - 加载 CS 三场景 `config/scenarios/cs_091339.json` 等
   - 对每个 breath segment 逐窗调用 `estimate_b3_window(variant=B3_SIMPLIFIED_CONFIG)`
   - 计算 BPM 相对误差 %（与 `bpm_gt` 对比），口径与既有 CS 排行榜一致
   - 产出 `outputs/reports/b3_cs_{scenario_id}_validation.json` ×3 + `b3_cs_validation_summary.json`

### Phase 2 — 对比与报告

4. 引用既有 B1（8.45%）/ B2-D（9.43%）CS 跨域数值，与 B3 Simplified 对比
5. 若 B3 Simplified BPM ≠ B1（> 0.01 pp），追查差异来源并记录
6. 生成排行榜图 `outputs/figures/b3_cs_validation_leaderboard.png`
7. 使用 `docs/templates/algorithm_validation_report.md` 撰写 `docs/reports/b3_cs_metal_plate_validation_report.md`
8. 回填本 plan §8 验证状态
9. **更新** `docs/methods/README.md`：解除或更新 B3 Simplified 条目的 CS `[待确认]` 标注

执行完成后返回 Review：
- `docs/reports/b3_cs_metal_plate_validation_report.md`
- `outputs/reports/b3_cs_validation_summary.json`
- `outputs/figures/b3_cs_validation_leaderboard.png`
- 更新后的 `docs/methods/README.md`
