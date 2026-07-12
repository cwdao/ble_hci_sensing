# B1+B2 窗级混合门控 — 实现计划

> **来源**：[`ble_hkh_multi_subject_validation_report.md`](../reports/ble_hkh_multi_subject_validation_report.md) §4.9  
> **目标报告**：`docs/reports/b1_b2_hybrid_gating_report.md`（模板：`docs/templates/algorithm_validation_report.md`）  
> **日期**：2026-07-12  
> **验证状态**：已完成

---

## 1. 动机与背景

### 1.1 问题

B1 Vote→Equal 和 B2-D 在 12 场景 HKH 上展示了清晰的互补模式：

| 场景类型 | B1 Vote→Equal BPM | B2-D BPM | 模式 |
|----------|------------------:|---------:|------|
| 正常（10/12 场景） | 0.26–0.71 | 0.26–0.73 | 两者同量级 |
| Outlier（A-D） | **0.60** | **2.31** | B2 崩溃，B1 仍稳 |
| Outlier（C-A） | **0.27** | **1.40** | B2 崩溃，B1 仍稳 |

**核心观察**：B2-D 的 BPM 并非在所有窗口都差——它在正常场景上与 B1 相当。问题出在少数 outlier 窗口上 B2-D 的参考 tone 质量差导致级联崩溃。如果能**在窗级识别 B2 何时可靠、何时不可靠**，就可以在可靠窗口使用 B2 BPM（可能更优），不可靠窗口回退 B1 BPM。

### 1.2 与既有工作的关系

| 方法 | BPM 来源 | 波形 | 门控 |
|------|---------|------|------|
| B1 Vote→Equal | Voting → 等权谱融合 | ❌ | 无 |
| B2-D | 最终波形 PSD 寻峰 | ✅ | 无 |
| B3 Simplified | **B1 BPM（始终）** | ✅ B2-D 波形 | 无（B1 为唯一 BPM 源） |
| **G-Hybrid（本 plan）** | **窗级动态选择 B1 或 B2** | ✅ B2-D 波形 | |B1−B2| > T → B1 |

**与 G4 系列的关键区别**：G4 的 fallback 硬编码为 Single Remote（物理不自洽）。本 plan 的 fallback 是 B1 Vote→Equal——已验证物理自洽且 BPM 鲁棒。门控信号直接比较两个候选的 BPM 估计值，而非间接的信号质量代理（η、ρ 等），避免 SA 系列"信号特征与 BPM 准确性脱钩"的问题。

### 1.3 本 plan 定位

**轻量级后处理门控**：在 B3 管线（已同时计算 B1 BPM 和 B2-D 波形 PSD BPM）的输出上，加一层窗级 BPM 选择器。不改动任何融合逻辑，完全后处理。

**若成功**：Hybrid BPM < B1（0.41），证明 B2 BPM 在可靠窗口确实更优。
**若失败**：所有阈值下 Hybrid ≥ B1，则 B3 Simplified（始终取 B1 BPM）确认为最优——同样是有效的论文结论。

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | B1/B2 均使用 |
| `local_amplitudes` | ✅ | B1/B2 均使用 |
| `phases`（总相位） | ✅ | B1/B2 均使用 |
| `amplitudes`（总幅值） | ❌ | 无独立物理意义 |

### 2.2 门控信号的物理直觉

|B1 BPM − B2 BPM| 作为门控信号的合理性：

- B1 BPM 来自频域 Voting（72 tone 独立估计 BPM → 多数投票），对 outlier tone 鲁棒
- B2 BPM 来自时域波形 PSD（以最高 η tone 为参考做 Hilbert 对齐后融合），对参考 tone 质量敏感
- **当两者一致**：B2 的参考 tone 大概率质量正常，B2 BPM 可信
- **当两者分歧**：B2 的参考 tone 可能已退化，B1 BPM 更可靠

这与 B2-D 崩溃的已知机制（参考 tone 质量差 → 级联崩溃）一致。

### 2.3 符号约定

| 符号 | 含义 |
|------|------|
| `bpm_b1(w)` | 窗 `w` 上 B1 Vote→Equal 的 BPM 估计 |
| `bpm_b2(w)` | 窗 `w` 上 B2-D 最终波形 PSD 的 BPM 估计 |
| `Δ(w) = \|bpm_b1(w) − bpm_b2(w)\|` | 窗级 BPM 分歧度 |
| `T` | 门控阈值（breaths/min） |
| `bpm_gt(w)` | HKH 呼吸带 ground truth BPM |

---

## 3. 算法步骤

### 3.1 完整流程图

```text
B3 Shared Frontend（已有，不改动）
  │
  ├─► B1 BPM 路径:
  │     η·ρ Voting → per-modal weighted_spectrum
  │       → 三模态等权谱融合 → argmax
  │       → bpm_b1(w)
  │
  └─► B2-D 波形路径:
        两级 Hilbert 相位对齐 → 最终波形
          → 波形 PSD 寻峰 → bpm_b2(w)
          → waveform(w) → RMSE(w)
        │
        ▼
  ╔═══════════════════════════════════════════════════╗
  ║  【NEW】窗级混合门控 G-Hybrid                     ║
  ║                                                  ║
  ║  Δ(w) = |bpm_b1(w) − bpm_b2(w)|                  ║
  ║                                                  ║
  ║  if Δ(w) > T:                                    ║
  ║      bpm_final(w) = bpm_b1(w)    ← B2 不可靠     ║
  ║  else:                                           ║
  ║      bpm_final(w) = bpm_b2(w)    ← 两者一致      ║
  ║        (或 mean(bpm_b1, bpm_b2)，见变体)          ║
  ║                                                  ║
  ║  waveform(w) = B2-D waveform(w)  ← 波形始终不变  ║
  ╚═══════════════════════════════════════════════════╝

输出 (每窗):
  - BPM:   G-Hybrid 选择结果
  - 波形:  B2-D 融合波形（不变）
  - RMSE:  B2-D vs HKH GT（不变）
  - Δ(w):  窗级分歧度（诊断用）
  - gate_triggered(w): bool（诊断用）
```

### 3.2 门控变体

| ID | 共识时 BPM | 分歧时 BPM | 说明 |
|----|-----------|-----------|------|
| **G-H1** | `bpm_b2` | `bpm_b1` | 主方案：信任 B2 直到它与 B1 分歧 |
| G-H2 | `mean(bpm_b1, bpm_b2)` | `bpm_b1` | 共识时取均值，分歧时回退 |
| G-H3 | `bpm_b1` | `bpm_b1` | 退化：始终 B1（= B3 Simplified，baseline） |
| G-H4 | `bpm_b2` | `bpm_b2` | 退化：始终 B2（= B2-D，baseline） |

### 3.3 阈值扫描

对 G-H1 和 G-H2 扫描 `T ∈ {0.5, 1.0, 1.5, 2.0}` breaths/min，观察 BPM 跨域 mean 随 T 的变化。

> 若最优 T 与场景高度相关（如 Room A 最优 T=0.5 而 Room C 最优 T=2.0），则说明单一全局阈值不足以覆盖场景多样性——这是值得报告的重要负结果。

### 3.4 诊断分析

实验必须产出以下诊断，帮助理清门控是否有效以及为何有效/无效：

| ID | 诊断 | 方法 |
|----|------|------|
| **D1** | 共识窗上 B2 vs B1 BPM 谁更准？ | 取所有 Δ(w) ≤ T 的窗，分别计算 bpm_b1(w) 和 bpm_b2(w) 的绝对误差 vs GT |
| **D2** | 分歧窗占比 vs T | 随 T ↑，gate_triggered 比例如何变化？outlier 场景 vs 正常场景差异？ |
| **D3** | 门控是否命中了真正的 B2 崩溃窗？ | 在 outlier 场景（A-D/C-A）上，绘制 Δ(w) 时间序列 + BPM 误差时间序列 |
| **D4** | G-H1 最优 T 的窗级 BPM 误差分布 | 小提琴图：B1 / B2 / G-H1 三者的 per-window BPM 误差分布 |

---

## 4. Baseline 对比

### 4.1 外部 Baseline

| 方法 | 说明 | BPM (12 场景) | 来源 |
|------|------|-------------:|------|
| B1 Vote→Equal | 当前 BPM 推荐（0.41） | 0.41±0.14 | `systematic_fusion.py` |
| B2-D Two-level | 当前波形最优（RMSE 0.950） | 0.68±0.57 | `coherent_mrc.py` |
| **B3 Simplified** | B1 BPM + B2 波形（0.405 + 0.950） | **0.41±0.14** | `b3_pipeline.py` |

### 4.2 待测变体

| ID | 共识 BPM | 分歧 BPM | T 扫描 |
|----|---------|---------|--------|
| G-H1-T{0.5,1.0,1.5,2.0} | B2 | B1 | 4 个阈值 |
| G-H2-T{0.5,1.0,1.5,2.0} | mean(B1,B2) | B1 | 4 个阈值 |
| G-H3 | B1 | B1 | N/A（= B3 Simplified 对照） |
| G-H4 | B2 | B2 | N/A（= B2-D 对照） |

### 4.3 预期相对关系

| 对比 | 预期 | 理由 |
|------|------|------|
| G-H1 vs B1 | 相当或略优 | 共识窗上 B2 可能略优于 B1；分歧窗上 B1 = B1 |
| G-H1 vs B2-D | 明显更优（尤其 outlier） | 分歧窗回退 B1 避免了 B2 崩溃 |
| G-H1 vs B3 Simplified | **关键对比**：若 G-H1 ≤ B3 Simplified → 门控有价值；否则 B3 Simplified 更简且等价 | — |
| G-H1 vs G-H2 | 相当 | mean(B1,B2) 在共识窗上可能微调但未必改善 |
| 最优 T | 预期 T≈1.0–1.5 BPM | 太小→过度触发（正常波动被误判分歧）；太大→outlier 漏检 |

---

## 5. 评估设计

### 5.1 场景与指标

| 维度 | 内容 |
|------|------|
| 场景 | 全部 12 个 HKH 真人场景（`config/scenarios/room_{A,B,C}-sbj_{A,B,C,D}-*.json`） |
| 主指标 | **BPM 绝对误差 mean ± std**（12 场景跨域） |
| 次指标 | 窗级 RMSE（不变，始终 = B2-D）、共识窗 BPM error、分歧窗占比 |
| 滑窗 | 20 s 窗长 / 1 s 步长 |
| 呼吸频段 | 0.1–0.35 Hz |
| GT | HKH 带通波形 Welch 寻峰 BPM（fs = len/duration） |

### 5.2 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | 存在至少一个 (G-H*, T) 组合，其 12 场景 BPM ≤ B1（0.41）且 outlier 场景不退化 |
| **理想** | 最优 G-H* BPM < 0.40，且 D1 显示共识窗上 B2 显著优于 B1（Δ > 0.05 BPM） |
| **失败** | 所有 (G-H*, T) 的 BPM ≥ B1（0.41）→ 门控无增益，B3 Simplified 确认最优 |

### 5.3 额外关注

- **outlier 场景（A-D / C-A / B-C）**：Δ(w) 是否在 B2 真正崩溃的窗口上显著升高？
- **正常场景**：Δ(w) 是否主要保持在低水平（共识窗占多数），避免不必要的回退？
- **阈值泛化性**：最优 T 是否跨 Room（A/B/C）一致？

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 | 说明 |
|------|------|------|
| **新增模块** | `src/ble_analysis/hybrid_gating.py` | 窗级 BPM 门控逻辑，纯后处理 |
| **新增脚本** | `notebooks/scripts/chFusion_b1_b2_hybrid_gating.py` | 12 场景 × (G-H1/2 × 4T + G-H3/4) 批量验证 |
| 不改动 | `b3_pipeline.py`、`systematic_fusion.py`、`coherent_mrc.py` | 门控在 B3 输出上做后处理 |

### 6.2 接口草案

```python
# src/ble_analysis/hybrid_gating.py

def apply_hybrid_gating(
    bpm_b1_per_window: np.ndarray,      # [N_windows] B1 Vote→Equal BPM
    bpm_b2_per_window: np.ndarray,      # [N_windows] B2-D waveform PSD BPM
    threshold: float = 1.0,             # BPM divergence threshold
    consensus_strategy: str = "b2",     # "b2" | "mean"
) -> dict:
    """Post-hoc window-level hybrid gating.

    Returns:
        bpm_final: [N_windows] gated BPM
        gate_triggered: [N_windows] bool — True = divergence, used B1
        divergence: [N_windows] |bpm_b1 − bpm_b2|
    """
    divergence = np.abs(bpm_b1_per_window - bpm_b2_per_window)
    gate_triggered = divergence > threshold

    if consensus_strategy == "b2":
        bpm_final = np.where(gate_triggered, bpm_b1_per_window, bpm_b2_per_window)
    elif consensus_strategy == "mean":
        bpm_final = np.where(
            gate_triggered,
            bpm_b1_per_window,
            (bpm_b1_per_window + bpm_b2_per_window) / 2
        )

    return {
        "bpm_final": bpm_final,
        "gate_triggered": gate_triggered,
        "divergence": divergence,
    }


def evaluate_hybrid_gating_scan(
    bpm_b1: np.ndarray,
    bpm_b2: np.ndarray,
    bpm_gt: np.ndarray,
    thresholds: list[float] = [0.5, 1.0, 1.5, 2.0],
    strategies: list[str] = ["b2", "mean"],
) -> dict:
    """Scan thresholds and strategies, return cross-scene BPM error for each."""
    ...
```

### 6.3 实现策略

**最小侵入**：在 B3 管线的每窗输出中，`bpm_b1` 已经是 Voting → equal spectral fusion 的结果，`bpm_b2` 可以从最终波形 PSD 计算（A2 路径已验证）。在 B3 segment-level 循环外包裹一层后处理即可。

```text
for each scene:
    for each window:
        result = estimate_b3_window(...)
        # result already contains:
        #   result["bpm"]          ← B1 BPM (equal spectral fusion)
        #   result["waveform"]     ← B2-D waveform
        #   result["bpm_waveform"] ← B2-D waveform PSD BPM (A2 path)

    # Post-hoc gating:
    gated = apply_hybrid_gating(
        bpm_b1=all_windows["bpm"],
        bpm_b2=all_windows["bpm_waveform"],
        threshold=T,
        consensus_strategy="b2",
    )
    # Evaluate gated["bpm_final"] vs GT
```

### 6.4 不做的事

- 不修改 B1 / B2-D / B3 的任何融合逻辑
- 不引入新的信号质量特征（η、ρ 等）作为门控信号——只使用 BPM 分歧度
- 不引入窗间时序平滑（persistence）——先验证单窗门控是否有效
- 不新增滤波参数、滑窗参数、指标定义

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| 门控模块 | `src/ble_analysis/hybrid_gating.py` |
| 批量脚本 | `notebooks/scripts/chFusion_b1_b2_hybrid_gating.py` |
| 每场景结果 | `outputs/reports/ble_hkh_hybrid_gating_{scenario_id}.json` ×12 |
| 跨场景汇总 | `outputs/reports/ble_hkh_hybrid_gating_summary.json` |
| 阈值扫描图 | `outputs/figures/ble_hkh_hybrid_gating_threshold_scan.png`（BPM vs T） |
| 门控触发图 | `outputs/figures/ble_hkh_hybrid_gating_trigger_timeseries.png`（outlier 场景 Δ(w) 时间序列） |
| 小提琴图 | `outputs/figures/ble_hkh_hybrid_gating_error_distribution.png`（D4） |
| 验证报告 | `docs/reports/b1_b2_hybrid_gating_report.md` |

### 建议运行命令

```bash
python notebooks/scripts/chFusion_b1_b2_hybrid_gating.py
```

---

## 8. 验证状态与保留问题

> 由**执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | 已完成 |
| **实际脚本** | `notebooks/scripts/chFusion_b1_b2_hybrid_gating.py` |
| **核心模块** | `src/ble_analysis/hybrid_gating.py` |
| **报告链接** | `docs/reports/b1_b2_hybrid_gating_report.md` |
| **一句话结论** | 所有 G-Hybrid 变体 BPM ≥ B1（0.405）；门控无增益，B3 Simplified 确认最优 |

**实际产出路径：**
- 脚本：`notebooks/scripts/chFusion_b1_b2_hybrid_gating.py`
- 模块：`src/ble_analysis/hybrid_gating.py`
- 数值结果：`outputs/reports/ble_hkh_hybrid_gating_{scenario_id}.json` ×12；`outputs/reports/ble_hkh_hybrid_gating_summary.json`
- 图表：`outputs/figures/ble_hkh_hybrid_gating_threshold_scan.png`；`ble_hkh_hybrid_gating_trigger_timeseries.png`；`ble_hkh_hybrid_gating_error_distribution.png`；`ble_hkh_hybrid_gating_d2_trigger_rate.png`
- 报告：`docs/reports/b1_b2_hybrid_gating_report.md`

**结论摘要：**
- 最优 G-H1（T=0.5）BPM = 0.416 > B1 = 0.405；G-H2 最优 T=0.5 BPM = 0.408，仍劣于 B1。
- D1：共识窗 B2 误差高于 B1（b2_advantage = −0.013），H1 不成立。
- D2：outlier 触发率（24.6% @ T=0.5）高于 normal（2.4%），机制部分有效但不足以改善跨域 BPM。
- Plan §5.2「失败路径」成立：B3 Simplified 确认为 BPM 最优。

**遗留问题：**
- Q2（共识窗 B2 是否更优）：实验推翻，B2 在共识窗也更差。
- Q1（最优 T 跨 Room 一致性）：最优 T=0.5 全局一致，但所有 T 均劣于 B1。
- G-Hybrid 标记为已废弃；待 Review Mode 更新 `docs/methods/README.md`。

### 保留问题

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | 最优 T 是否跨 Room 一致？ | 若不一致→单一全局阈值策略受限 |
| Q2 | 共识窗上 B2 BPM 是否确实优于 B1？ | D1 诊断；若否→门控无理论基础 |
| Q3 | 是否应该用 B3 Simplified 的 BPM（= B1）替代 B1 作为 fallback？ | 两者等价（B3 Simplified BPM ≡ B1 BPM）；为代码复用建议走 B3 |
| Q4 | CS 金属板场景上是否适用？ | 本 plan 仅 HKH；CS 场景 B1 vs B2-D 互补模式不同 |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并按以下顺序执行：

### Phase 1 — 模块实现

1. 读取本 plan：`docs/plans/b1_b2_hybrid_gating_plan.md`
2. **新建** `src/ble_analysis/hybrid_gating.py`：
   - 实现 `apply_hybrid_gating()` — 窗级后处理门控
   - 实现 `evaluate_hybrid_gating_scan()` — 阈值 × 策略扫描
3. 门控逻辑在 B3 管线输出上做后处理——不修改 B3 / B1 / B2 源码

### Phase 2 — 批量验证与诊断

1. **新建** `notebooks/scripts/chFusion_b1_b2_hybrid_gating.py`
2. 遍历 12 个 HKH 场景，每窗收集：
   - `bpm_b1`：B1 Vote→Equal BPM（B3 管线的 equal spectral fusion 路径）
   - `bpm_b2`：B2-D 最终波形 PSD BPM
   - `bpm_gt`：HKH GT BPM
   - `waveform`：B2-D 融合波形
3. 对每个场景运行：
   - **G-H1** × T ∈ {0.5, 1.0, 1.5, 2.0}（共识→B2, 分歧→B1）
   - **G-H2** × T ∈ {0.5, 1.0, 1.5, 2.0}（共识→mean, 分歧→B1）
   - **G-H3**：始终 B1（baseline）
   - **G-H4**：始终 B2（baseline）
4. 产出诊断：
   - **D1**：共识窗（Δ ≤ 最优 T）上 B1 vs B2 per-window BPM error 对比
   - **D2**：分歧窗占比 vs T 曲线（正常场景 vs outlier 场景分组）
   - **D3**：outlier 场景（A-D/C-A）上 Δ(w) 时间序列 + BPM error 时间序列
   - **D4**：最优 G-H1 配置的 per-window BPM error 小提琴图（B1 / B2 / G-H1 三组）
5. 生成图表：
   - 阈值扫描图：x=T, y=BPM cross-scene mean（G-H1 和 G-H2 两条线 + B1/B2 水平参考线）
   - Outlier 场景门控触发时间序列图
   - Per-window BPM error 小提琴图
6. 使用 `docs/templates/algorithm_validation_report.md` 撰写 `docs/reports/b1_b2_hybrid_gating_report.md`
7. 回填本 plan §8 验证状态
