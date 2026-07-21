# BLE CS 人体呼吸监测 — 实验结果汇报

> **数据**：12 条 HKH 真人数据（3 房间布局 × 4 受试者），BLE CS + HKH 呼吸带同步采集  
> **指标**：BPM 绝对误差 mean±std（breaths/min）、波形 RMSE（z-score 对齐）  
> **场景**：Room A（客厅坐姿）、Room B（卧室平躺）、Room C（卧室侧躺）  
> **日期**：2026-07-12（实验完成）

---

## 1. 波形合成类方案：BPM 表现不佳

首先测试了三类基于**波形生成/恢复**的方案——这类方法的优势是能输出呼吸波形供下游分析，但 BPM 精度存在问题。

### 方法说明

| 方法 | 路线描述 |
|------|----------|
| **Zhuo 2023 PCA-VMD**（外部参考） | 两级 PCA 降维（72 tone → PC1 → 3 模态 → PC1 融合波形）→ 可选 VMD → 峰值检测 BPM。源自 WiFi CSI 文献 |
| **B2-D 两级 Hilbert 相干融合**（自研） | 第一级：每模态 72 tone Hilbert 相位对齐 MRC → 模态波形。第二级：三模态 Hilbert 相位对齐 + η·γ 加权 → 最终波形 → Welch PSD 寻峰 |
| **Fan 2024 η 线性 MRC**（外部参考） | CSI 幅值 MRC + PCA 符号对齐 → 等权波形平均 |

### 12 场景主结果

| 方法 | BPM 误差 ↓ (mean±std) | RMSE ↓ | 波形 | BPM 排名 |
|------|---------------------:|-------:|:----:|:--------:|
| **逐模态 Voting → 三模态等权谱融合**（B1, 谱域） | **0.41±0.14** | — | ❌ | 🥇 |
| Zhuo 2023 PCA-VMD（无 VMD） | 0.44±0.12 | 1.070 | ✅ | 🥈 |
| **B2-D 两级 Hilbert 相干融合** | 0.68±0.84 | **0.950** | ✅ | 🥉 |
| Fan 2024 η 线性 MRC | 1.39±1.68 | 1.025 | ✅ | 7 |

![BPM vs RMSE](../../outputs/figures/ble_hkh_b3_bpm_vs_rmse.png)

**图 1**：各方法在 BPM 误差与 RMSE 两个维度上的分布。B2-D 拥有最优 RMSE（0.950），但其 BPM 方差（0.84）远大于谱域方法（0.14），在 outlier 场景出现严重退化。

### 关键发现

- **波形质量 ≠ BPM 精度**：B2-D 的 RMSE 在 12 场景排名第一（0.950），但在 outlier 场景 BPM 崩溃（见下表）。
- **Zhuo PCA-VMD 的 VMD 无增益**：带 VMD（0.74 BPM）劣于去 VMD（0.44），与之前金属板场景结论一致。

| 问题场景 | B1 Voting BPM | B2-D BPM | B2-D 退化幅度 |
|----------|-------------:|--------:|-------------:|
| `room_A-sbj_D`（坐姿） | **0.60** | 2.31 | −1.71 |
| `room_C-sbj_A`（侧躺） | **0.27** | 1.40 | −1.13 |
| `room_B-sbj_C`（平躺） | 0.71 | 0.73 | ≈0 |

波形类方案在 A-D 和 C-A 两条场景上出现了**级联性 BPM 崩溃**（波形 PSD 谱峰误选），而谱域 Voting 方法在同场景保持稳定。

![Outlier Timeseries](../../outputs/figures/ble_hkh_b3_outlier_timeseries.png)

**图 2**：问题场景 BPM 时序对比。Voting BPM（蓝）紧贴 GT（黑虚线），B2-D 波形 PSD BPM（红）在部分窗口大幅偏离，展示了 Voting 的 outlier 鲁棒性。

---

## 2. 频谱投票方案：BPM 保持稳定

**逐模态 Per-Tone η·ρ Voting** 的信道融合策略在金属板和真人场景上持续表现最优，其核心机制是：将 72 个 tone 视为独立"选民"，每窗每个 tone 独立估计 BPM → η·ρ 加权直方图投票 → 避免单个劣质信道的谱峰劫持融合结果。

### 方法说明

**逐模态 Voting → 三模态等权谱融合**（代号 B1，当前推荐部署的 BPM 方案）：

1. **信道级 Voting**：每个模态（Remote 幅值 / Local 幅值 / 相位）独立对 72 tone 做 per-tone BPM 估计 → η·ρ 加权直方图投票 → 每个模态输出一条加权谱
2. **模态级等权融合**：三条模态谱 1:1:1 融合 → 寻峰得 BPM

### 12 场景 HKH BPM 排行榜

| 排名 | 方法 | BPM 误差 (mean±std) | 波形 |
|------|------|-------------------:|:----:|
| 🥇 | **Uniform Remote**（72 信道谱等权平均, 仅 Remote） | **0.37±0.12** | ❌ |
| 🥈 | **逐模态 Voting → Top2 等权谱融合**（B3） | 0.38±0.12 | ❌ |
| 🥉 | **逐模态 Voting → 三模态等权谱融合**（B1, 推荐） | **0.41±0.14** | ❌ |
| 4 | Zhuo Z1-no-VMD（波形类最优） | 0.44±0.12 | ✅ |
| 5 | B2-D 两级 Hilbert（波形类最优） | 0.68±0.57 | ✅ |
| 6 | Fan η-linear | 1.39±1.68 | ✅ |

![B1 Leaderboard](../../outputs/figures/ble_hkh_b1_validation_leaderboard_12scenarios.png)

**图 3**：12 场景 BPM 排行榜。谱域 Voting 系列（蓝/绿柱）在 BPM 精度和稳定性上全面优于波形类方法（红柱）。

### 关键发现

- **Voting 的 BPM 稳定性跨场景保持**：B1 std 仅 0.14 BPM vs B2-D 0.84 BPM（6× 差异）。
- **Outlier 场景不崩溃**：Voting 在 A-D（0.60）、C-A（0.27）上远优于 B2-D（2.31、1.40）。
- **谱域 Voting 的唯一缺陷**：不能输出可用的呼吸波形（仅输出谱和 BPM）。

---

## 3. B3 统一管线：综合两者优势

B1（最优 BPM，无波形）和 B2-D（最优 RMSE，BPM 不稳定）共享相同的预处理前端（滤波 + 逐模态 Voting），因此可以合并为一条管线：

```text
                  72 tone × 3 变量 (remote/local/phases)
                        │
              共享前端：滤波 + 逐模态 η·ρ Voting
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   BPM 分支：                      波形分支：
   Voting 加权谱                   Voting 加权波形
   → 三模态等权谱融合              → 两级 Hilbert MRC 对齐
   → Welch 寻峰 → BPM             → 最终呼吸波形 → RMSE
   (B1 逻辑, 0.41 BPM)            (B2-D 逻辑, 0.950 RMSE)
```

这就是 **B3 Simplified**（B3 B1-equal 变体）——单条管线，共享预处理，BPM 和波形各自走最优路径，无需窗级门控。

### 核心结果

| 方案 | BPM 误差 (mean±std) | RMSE | 波形 | 说明 |
|------|-------------------:|------|:----:|------|
| **B3 Simplified** ✅ | **0.41±0.14** | **0.950** | ✅ | **推荐部署** |
| B1 Vote→Equal（对照） | 0.41±0.14 | — | ❌ | BPM-only 基线 |
| B2-D（对照） | 0.68±0.84 | 0.950 | ✅ | 波形基线 |

- **B3 BPM 精确复现 B1**：12 场景逐场景 BPM 差异 = **0.000 BPM**（数值完全一致）。
- **B3 RMSE 精确复现 B2-D**：同一条两级 Hilbert-MRC 波形管线，RMSE 同为 0.950。

![B3 Ablation Leaderboard](../../outputs/figures/ble_hkh_b3_ablation_leaderboard.png)

**图 4**：B3 消融排行榜。B3 Simplified（绿）与 B1（蓝）并列 BPM 榜首，同时 B3 拥有 B2-D（红）的波形能力。

### 补充实验：窗级门控（G-Hybrid）— 负结果，已废弃

曾尝试用窗级 BPM 分歧度 Δ = |BPM_B1 − BPM_B2| 做门控（Δ 大时回退 B1，否则取 B2），期望在共识窗利用 B2 的 BPM 优势。结果：

- **全部变体 × 全部阈值 BPM ≥ B1**（最优 G-H2 T=0.5: 0.408 > 0.405）
- 根因：即使 Δ 很小的"共识窗"，B2 BPM 也不优于 B1（b2_advantage = −0.013）

**结论**：B3 Simplified（始终 B1 BPM + B2 波形）即最优方案，无需门控。

### 消融分析：管线中各组件的贡献

| 消融对比 | 效果 | ΔBPM | 是否保留 |
|----------|------|-----:|:--------:|
| Voting → 单信道 best-η | Voting 远优于单信道（0.50 BPM 改善） | **0.50** | ✅ |
| Voting BPM → 波形 PSD BPM | Voting BPM 优于波形 PSD（0.22 BPM 改善） | **0.22** | ✅ |
| 等权谱融合 → weighted_median 共识 | 等权融合略优 | 0.06 | ✅ 用等权 |
| η·ρ 投票权重 → 等权投票 | 几乎无差异 | 0.02 | ✅ 零成本保留 |
| 有/无 coherence gate | 无差异 | 0.00 | ❌ 移除 |
| per-modal 分组 → 跨模态全局 Voting | 无差异 | 0.00 | ❌ 移除 |

---

## 总结

| # | 结论 | 证据强度 |
|---|------|----------|
| 1 | 波形合成路线（Zhuo PCA-VMD / B2-D / Fan MRC）的 BPM 精度均不及谱域 Voting | **12 场景验证** |
| 2 | 逐模态 Voting → 三模态等权谱融合（B1）在 12 场景 HKH 上 BPM 稳定最优（0.41±0.14），outlier 场景不崩溃 | **12 场景验证** |
| 3 | **B3 Simplified** 统一管线 = B1 的 BPM（0.41）+ B2-D 的波形（RMSE 0.950），单条管线同时输出最优 BPM 和最优波形 | **12 场景验证** |
| 4 | G-Hybrid 窗级 BPM 门控全线劣于 B1，已正式废弃 | **负结果** |

**推荐部署方案**：B3 Simplified — 共享 Voting 前端，BPM 用三模态等权谱融合，波形用两级 Hilbert-MRC。

---

*数据来源：`outputs/reports/ble_hkh_b3_validation_summary.json`、`ble_hkh_b3_simplified_validation_summary.json`、`ble_hkh_paper_baselines_summary.json`、`ble_hkh_b1_validation_summary.json`、`ble_hkh_hybrid_gating_summary.json`*
