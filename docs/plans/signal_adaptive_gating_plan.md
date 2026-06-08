# 信号级自适应门控与退化根因追查 — 实现计划

> **来源**：
> - [B1 gating & diagnosis plan](../plans/b1_gating_and_diagnosis_plan.md) — G4-B1-v2 跨域 8.05%，但 102621 仍由 G4 主导
> - [B1 gating & diagnosis report](../reports/b1_gating_and_diagnosis_report.md) — H2 已验证、H3 未证实
> - [B1 gating review](#) — Claude Review 判定 partially supported；Q1/Q2/Q3 需追查
>
> **目标报告**：`docs/reports/signal_adaptive_gating_report.md`  
> **日期**：2026-06-08（初稿）

---

## 1. 动机与背景

### 1.1 核心问题：最优门控策略因窗而异，但不能按场景编号选择

B1 gating 实验确认了两件事：

1. **G4-B1-v2（三候选最近对共识）跨域 8.05%，为当前全局最优**，且 H2 已从机制上解释 Voting→Equal 优于 Voting→Top2。
2. **102621 上 G4（双候选共识/分歧→回退单信道，4.51%）仍显著优于所有 B1 三候选变体**（G4-B1-v2 = 5.50%，差 0.99pp）。

这意味着 102621 的某些窗上，将 B1（逐模态 Voting→等权谱融合）作为第三候选反而增加了门控混乱——B1 的 BPM 在那些窗上既不接近 Voting（远程单模态投票），也不接近 Modal Top2（逐模态最优信道→Top2），导致三候选门控的"最近对共识"选到了错误的一对。

**但这不是场景标签问题**——不能简单地"102621 用 G4，其余用 v2"。需要回答：**G4 优于 v2 的那些窗，在信号层面有什么共同特征？**

### 1.2 附加问题：091339 退化根因

H3（双峰性根因）已在 D2 诊断中被推翻——双峰窗 B1 error（15.17%）并未高于单峰窗（17.20%）。091339 所有方法 > 12% 的根因仍然不明。

### 1.3 本 plan 定位

本 plan **不引入新的信道或模态融合策略**，聚焦三个目标：

1. **102621 G4 优势根因追查**（P1）：分析 G4 vs G4-B1-v2 的窗级决策差异，定位哪些窗上 B1 的加入是负贡献。
2. **信号级自适应门控**（P2）：基于 P1 发现的可迁移信号特征，设计不依赖场景标签的自适应门控。
3. **091339 替代根因诊断**（P3）：追查 091339 退化原因（信号质量？多径？段结构？）。

### 1.4 核心假设

> **H1（102621 G4 优势的机制）**：102621 上 G4 优于 G4-B1-v2 的窗，特征是 Voting（远程单模态投票）与 Modal Top2 的 BPM 差异 ≤ 3 BPM（即 G4 双候选已共识），但 B1（逐模态 Voting→等权谱融合）的 BPM 偏离这两者——即 B1 在 G4 已共识的窗上引入了噪声偏离。

> **H2（信号级自适应门控）**：可以在窗级计算一个「三候选一致性」评分：如果三候选 BPM 两两差异均小（三者高度一致），加权平均优于任意单一候选；如果仅 Voting 与 Modal 接近但 B1 偏离，应退化为 G4 模式（或直接忽略 B1）。这样可以在不依赖场景标签的前提下，在 102621 类窗上取得接近 G4（4.51%）的表现，在其他窗上保持 v2 的优势。

> **H3（091339 替代根因）**：091339 的退化与信号本身的 η 质量相关——该场景的 per-tone η（呼吸频段能量比）系统性偏低，导致 Voting 阶段的 tone 级 BPM 估计噪声大，进而污染了逐模态 Voting→谱的质量。如果此假说成立，η 分布可作为自适应 fallback（低 η 窗→回退到 Single Remote 而非 Voting）。

---

## 2. 物理与变量

### 2.1 沿用变量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | Voting 和 Single 的基础 |
| `local_amplitudes` | ✅ | B1 三模态等权融合的模态之一 |
| `phases` | ✅ | B1 三模态等权融合的模态之一 |
| `η` per tone | ✅ | 新增诊断：tone 级呼吸频段能量比分布 |
| `η` per modal | ✅ | 新增诊断：每模态 Voting 置信度 |

### 2.2 新增诊断信号

| 诊断量 | 含义 | 用途 |
|--------|------|------|
| `triplet_consensus_score` | 三候选 BPM 的两两差异的最小值与最大值之比 | H2：判断 B1 是否是"搅局者" |
| `b1_deviation` | B1 BPM 与 (Voting, Modal) 均值的距离 | H1：量化 B1 在 G4 共识窗上的偏离 |
| `mean_per_tone_eta` | 72 tone η 的均值 | H3：判断 Voting 输入信号质量 |
| `eta_std_per_tone` | 72 tone η 的标准差 | 判断 tone 间质量差异 |
| `g4_win_window_mask` | 每窗是否 G4 error < v2 error | P1 追查：标识 G4 优势窗 |

---

## 3. 算法设计

### 3.1 P1：102621 G4 优势窗级追查

**不需要新方法**，仅对现有 G4 和 G4-B1-v2 在 102621 上的窗级结果做差异分析。

```
对 102621 每窗：
  1. 计算 error_g4 = |BPM_g4 - BPM_gt|
     error_v2 = |BPM_v2 - BPM_gt|
  2. 若 error_g4 < error_v2 - 0.5 BPM：标记为 "G4 优势窗"
     若 error_v2 < error_g4 - 0.5 BPM：标记为 "v2 优势窗"
     否则：标记为 "相当"
  3. 在 G4 优势窗上：
     a. 计算 B1 BPM 与 (Voting, Modal) 均值的距离（b1_deviation）
     b. 计算 Voting BPM 与 Modal BPM 的差异（g4_pair_distance）
     c. 计算三候选两两差异的完整矩阵
  4. 汇总统计：
     - G4 优势窗 vs v2 优势窗 vs 相当窗 各占比
     - G4 优势窗的 b1_deviation 分布 vs v2 优势窗的 b1_deviation 分布
```

**预期（如果 H1 成立）**：G4 优势窗上，Voting 与 Modal BPM 接近（≤ 3 BPM）但 B1 BPM 偏离二者（> 3 BPM）。这意味着 G4 双候选已正确共识，B1 的加入制造了伪分歧。

### 3.2 P2：信号级自适应门控

基于 P1 发现的信号特征，设计两个候选自适应方案：

#### P2-a：三候选一致性门控（基于 triplet_consensus_score）

```
每窗：
  bpm_vote, bpm_modal, bpm_b1 = 三候选 BPM
  pair_diffs = [|vote-modal|, |vote-b1|, |modal-b1|]
  sorted_diffs = sort(pair_diffs)
  consensus_score = sorted_diffs[0] / (sorted_diffs[2] + eps)  # 最接近对 / 最远对

  if consensus_score < 0.4（三者离散，B1 可能是搅局者）:
      检查 |vote-modal| 是否 ≤ δ：
          是 → G4 模式（vote + modal 共识/分歧→fallback），忽略 B1
          否 → Single Remote fallback
  else（三者接近一致 或 B1 与某方接近）:
      G4-B1-v2 模式（三候选最近对共识）
```

δ = 3 BPM（沿用）。

**关键**：此门控不依赖场景标签——`consensus_score` 是纯窗级信号特征。

#### P2-b：η 质量加权门控（基于 per-tone η 分布）

```
每窗：
  计算 mean_eta = 72 tone η 的均值
  计算 eta_cv = std(η) / mean(η)  # 变异系数，衡量 tone 间质量差异

  if mean_eta > τ_high 且 eta_cv < cv_thresh（信号质量好）:
      使用 B1（逐模态 Voting→等权融合）直接输出
  elif mean_eta > τ_low（信号质量可接受）:
      使用 G4-B1-v2 三候选门控
  else（信号质量差）:
      使用 G4 双候选门控（直接忽略 B1）
```

τ_high, τ_low, cv_thresh 在 102621 和 091339 上通过 hold-one-scene-out 初步标定（不固定死，标注 `[待优化]`）。

### 3.3 P3：091339 η 质量诊断

```
对 091339 每窗：
  1. 计算 per-tone η 统计量（mean, std, cv, 10th/90th 分位数）
  2. 将窗按 mean_η 分为三组（低中高），对比 B1 error 分布
  3. 将窗按 eta_cv 分为两组（高变异 vs 低变异），对比 B1 error 分布
  4. 交叉检查：G4 是否在低 η 窗上优于 B1？
```

**预期（如果 H3 成立）**：091339 低 mean_η 窗占比较高，且 B1 error 集中在低 η 窗。低 η 意味着 Voting tone 级 BPM 估计噪声大，逐模态 Voting→谱被污染。

---

## 4. Baseline 对比

### 4.1 必须复现/引用的 baseline

| 方法 | 跨域 mean | 来源 |
|------|-----------|------|
| G4（双候选共识/分歧→回退单信道） | 8.65% | voting_gating |
| B1（逐模态 Voting→等权谱融合） | 8.45% | systematic_fusion |
| G4-B1-v2（三候选最近对共识） | 8.05% | b1_gating_diagnosis |
| T0-V3（远程单模态 Per-Tone η·ρ 投票） | 9.20% | voting_fusion |
| Modal top2（逐模态最优信道→Top2 等权谱融合） | 9.45% | Plan2 |

### 4.2 待测方法

| ID | 方法 | 说明 |
|----|------|------|
| **SA-v1** | 三候选一致性门控（P2-a） | 主方案 |
| **SA-v2** | η 质量加权门控（P2-b） | 备选 |
| **SA-v1+G4** | SA-v1 但 fallback 改为 G4 而非 Single | 验证 G4 fallback 是否优于 Single fallback |

### 4.3 预期相对关系

| 对比 | 预期 | 理由 |
|------|------|------|
| SA-v1 vs G4-B1-v2（全局） | 更好 | 在 102621 上自动退化为 G4-like 行为 |
| SA-v1 vs G4（102621） | 接近（≤ 0.3pp） | 通过 consensus_score 检测 B1 搅局窗 |
| SA-v2 vs B1（091339） | 更好 | 低 η 窗自动 fallback |
| P3 诊断 | 091339 全局 η 低于其他两场景 | 解释 091339 系统性退化 |

---

## 5. 评估设计

### 5.1 场景

| 场景 | 用途 |
|------|------|
| `cs_091339` | P3 诊断主场景 + SA 验证 |
| `cs_095806` | SA 验证（B1 优势保持） |
| `cs_102621` | P1 追查 + SA 验证（G4 优势保持） |

### 5.2 指标

| 指标 | 说明 |
|------|------|
| 分段 BPM err% mean / std | 主指标 |
| 跨域 mean | 三场景平均 |
| **G4 优势窗占比**（102621） | P1 新增：|error_g4| < |error_v2| - 0.5 BPM 的窗比例 |
| **b1_deviation 分布**（G4 优势窗 vs v2 优势窗） | P1 新增：B1 BPM 偏离 Voting/Modal 均值的幅度 |
| **triplet_consensus_score 分布** | P2 新增：三候选两两差异的模式 |
| **per-tone η 分布（mean/std/CV）** | P3 新增：三场景对比 |
| SA-v1 门控决策分布 | 各 fallback 路径被选中的窗比例 |

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **理想** | SA-v1 跨域 mean < **7.8%**，且 102621 ≤ G4 + 0.3pp，091339 < 12% |
| **良好** | SA-v1 跨域 mean < **8.0%**，且三场景均不差于各自单一最优 + 0.5pp |
| **最低** | 至少一个 SA 变体跨域 mean < G4-B1-v2（8.05%），且 P1 产出 G4 优势窗的明确信号特征解释 |
| **P3 诊断成功** | 091339 退化与 η 质量相关获得统计证据（低 η 窗 B1 error 显著高于高 η 窗） |
| **失败** | 无 SA 变体跨域 < 8.05%，且 P1 无法找到可迁移信号特征 |

---

## 6. 实现要点

### 6.1 文件规划

| 类型 | 路径 | 说明 |
|------|------|------|
| 实验脚本 | `notebooks/scripts/chFusion_signal_adaptive_gating.py` | 主脚本 |
| 可复用模块（新增） | `src/ble_analysis/signal_adaptive_gating.py` | P2 门控逻辑 |
| 可复用模块（扩展） | `src/ble_analysis/consensus_gating.py` | 新增 `compute_triplet_consensus()` 诊断函数 |

### 6.2 复用 API

```python
from ble_analysis.systematic_fusion import (
    per_modal_voting_spectrum,
    modal_fusion_from_spectra,
    run_systematic_fusion_benchmark,
)
from ble_analysis.consensus_gating import (
    _gate_one_window_g4,
    gate_three_candidates,  # 已有（b1_gating_diagnosis）
)
from ble_analysis.chfusion import (
    _energy_ratio,  # per-tone η
    ChFusionConfig,
)
```

### 6.3 关键新增函数签名

```python
def compute_triplet_consensus_score(
    bpm_vote: float, bpm_modal: float, bpm_b1: float,
) -> float:
    """返回三候选一致性评分 ∈ [0,1]；接近 1 = 三者一致，接近 0 = 一对接近但第三偏离."""
    ...

def compute_per_tone_eta_stats(
    ch_list: List, ch_map: Dict, variable: str,
    st: int, end: int, fs: float, cfg: ChFusionConfig,
) -> Dict[str, float]:
    """返回该窗该变量 72 tone η 的 {mean, std, cv, p10, p50, p90}."""
    ...

def gate_signal_adaptive(
    bpm_vote: float, bpm_modal: float, bpm_b1: float,
    bpm_single: float,
    eta_stats: Dict[str, float],
    delta: float = 3.0,
    variant: str = "v1",
) -> Tuple[float, str]:
    """信号级自适应门控；返回 (bpm, decision_tag)."""
    ...

def run_p1_g4_advantage_analysis(
    results_g4: Dict, results_v2: Dict,
    scenario: str,
) -> Dict:
    """P1：对比 G4 vs v2 窗级差异，返回 G4 优势窗的特征汇总."""
    ...
```

### 6.4 不做的事

- 不新增场景 JSON
- 不改变滑窗参数或滤波链
- 不探索新信道/模态融合策略
- 不对 τ_high/τ_low/cv_thresh 做 exhaustive grid search（仅手动标定）
- 不用场景标签做任何 if-else 分支
- 不做 G7–G9 文献驱动方法

### 6.5 P1 追查的特殊实现注意

P1 不需要运行新实验——直接加载 `outputs/reports/b1_gating_diagnosis_102621_results.npy` 中已有的 G4 和 G4-B1-v2 窗级结果，与 GT 比较即可。这大大降低了 P1 的执行成本。

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| 验证报告 | `docs/reports/signal_adaptive_gating_report.md` |
| 数值结果 | `outputs/reports/signal_adaptive_gating_*.npy` |
| 跨域汇总 | `outputs/reports/signal_adaptive_gating_cross_domain.npy` |
| P1 G4 优势窗特征图 | `outputs/figures/sa_p1_g4_advantage_scatter.png` |
| P1 B1 deviation 分布图（G4 vs v2 优势窗对比） | `outputs/figures/sa_p1_b1_deviation_hist.png` |
| SA 跨域排行榜 | `outputs/figures/sa_leaderboard.png` |
| SA 门控决策分布图 | `outputs/figures/sa_decision_sankey.png` |
| P3 三场景 per-tone η 分布对比 | `outputs/figures/sa_p3_eta_distribution.png` |
| P3 091339 η 分组 B1 error 对比 | `outputs/figures/sa_p3_eta_vs_error.png` |

---

## 8. 风险与保留问题

### 8.1 算法风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| triad_consensus_score 在 102621 上无法区分 G4 优势窗 | 高 | P1 先追查再设计，避免闭门造车；如果 P1 找不到信号特征，SA-v1 取消 |
| η 质量在不跨场景时有分布偏移 | 中 | τ 阈值在 hold-one-scene-out 下初步标定，避免固定值 |
| P2-a 和 P2-b 组合引入过多阈值 | 中 | 优先 P2-a（仅一个参数 consensus_score 阈值），P2-b 仅在 P3 确认 η 质量是关键因素后启用 |
| SA-v1 改善幅度微小（< 0.2pp） | 中 | 如果改善 < 0.2pp 但产出明确机制解释，仍算部分成功 |

### 8.2 保留问题

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | P1 追查是否需要扩展到 095806（B1 优势场景）作为对照？ | `[待确认]` — 如果 102621 P1 发现可迁移特征，在 095806 上做对照验证会加强结论 |
| Q2 | 如果 P3 确认 η 是 091339 退化根因，是否需要回到信道选择层改进？ | `[待确认]` — 可能是下一轮 plan 的内容 |
| Q3 | SA-v1 中的 consensus_score 阈值是否需要跨场景自适应？ | `[待确认]` — 先固定 0.4，观察跨场景分布 |

---

## 9. 验证状态

状态：**待实现**

---

## 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/signal_adaptive_gating_plan.md`

### 执行范围

**P1 必做（轻量）**：加载已有 `b1_gating_diagnosis_102621_results.npy` 中 G4 和 G4-B1-v2 的窗级结果，与 ground truth 比较，输出 G4 优势窗特征分析。

**P2 必做**：实现 SA-v1（三候选一致性门控）和 SA-v2（η 质量加权门控），三场景运行。

**P3 必做**：三场景 per-tone η 分布对比 + 091339 η 分组 B1 error 分析。

### 关键实现注意

- P1 不需要新 benchmark，直接读已有 .npy 的窗级 BPM 列表与 GT
- SA-v1 的 `consensus_score` = 最近对距离 / 最远对距离（三对 pairwise），阈值暂设 0.4
- SA-v2 的 τ_high/τ_low 在 102621 上标定（取 G4 优势窗的 mean_η 中位数作为 τ_low）
- **严禁**：任何基于场景标签的 if-else 分支。门控仅能使用窗级信号特征
- P3 的 per-tone η 统计仅需在每窗首帧计算一次（不滑动）

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/reports/signal_adaptive_gating_report.md`
- `outputs/reports/signal_adaptive_gating_*.npy`
- `outputs/figures/sa_*.png`
- 关键脚本路径
- git diff 摘要
