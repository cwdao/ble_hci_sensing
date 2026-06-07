# Consensus Gating — 窗级共识门控融合计划

> **来源**：
> - Voting Fusion Review（Deng et al. voting 验证结论：T0-V3 跨域 9.20% 略优但 091339 退化）
> - PCA plan Q3（PCA-Modal 与 Plan2 谱峰一致性门控）
> - [待文献调研后补充] TR-BREATH [7] / Wi-Breath [6] / Bimodal CSI [10]
>
> **目标报告**：`docs/reports/voting_gating_report.md`  
> **日期**：2026-06-07（初稿，文献调研完成后补充 §1.4 / §3.4 / §4.3）  
> **验证状态**：待实现

---

## 1. 动机与背景

### 1.1 问题

两个独立的实验线程揭露了同一个模式：

| 线程 | 最优方法 | 跨域 mean | 091339 | 095806 | 102621 |
|------|----------|-----------|--------|--------|--------|
| Plan2 Modal | Modal top2 equal | **9.45%** | 13.04% | 10.61% | **4.69%** |
| Voting Fusion | T0-V3 η·ρ per-tone voting | **9.20%** | 13.77% | **6.84%** | 6.99% |
| PCA-Modal | PCA-Modal3 η/ch-η | 10.92% | 19.54% | 7.51% | 5.72% |

**关键观察**：没有单一方法在所有场景中都是最优的。

- Modal top2 在 091339 和 102621 上最强，但在 095806 上被 T0-V3 大幅超越（10.61% vs 6.84%）
- T0-V3 在 095806 上极强，但在 091339 上比 Modal 差
- PCA-Modal3 在 095806 上优于 Modal（7.51% vs 10.61%），在 091339 上严重退化（19.54%）

这说明不同方法的优劣是**窗级条件性**的——某些窗适合 voting（per-tone 多数派明确），某些窗适合谱融合（per-tone 分散但谱峰收敛）。

### 1.2 核心假设

> **H1**：在 095806 上 T0-V3 优于 Modal top2 的那些窗口，与 Modal top2 在 091339 上优于 T0-V3 的那些窗口，存在**可检测的信号特征差异**（如 voting confidence、谱峰一致性、η 分布偏度）。如果能检测这些特征，就可以在窗口级别动态选择方法。

> **H2**：窗级门控（gating）可以通过跨方法共识实现——当两个结构不同的方法（如 voting 和谱融合）给出相近 BPM 时，结果可信；当结果分歧时，选择历史可靠性更高的方法作为 fallback。

### 1.3 与现有工作的关系

- **PCA plan Q3** 提出了完全一致的思路：*"窗级 phase/remote/local 峰频差 > 阈值时退回 Single remote"*。本 plan 将这一概念从 PCA/Modal 之间的门控，扩展到 **Voting / Modal / PCA-Modal 三者之间的通用门控框架**。
- **Deng et al. 论文** 的 voting threshold τ 本质上是一种"单方法内部门控"——当票数不足时标记 low-conf。本 plan 将其扩展为**跨方法门控**——不仅看 voting 内部置信度，还看 voting 与 Modal 的外部一致性。
- **[待文献调研后补充]**

### 1.4 文献调研衔接（预留）

> `[待文献调研后补充]`：
> - TR-BREATH [7] 的 TRRS 指标是否可作为门控特征？
> - Wi-Breath [6] 的 SVM 置信度是否优于 η/ρ threshold？
> - Bimodal CSI [10] 的体动检测器是否可作为"切换到 robust 方法"的门控信号？

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | T0-V3 的主输入；Modal top2 的参与模态之一 |
| `local_amplitudes` | ✅ | Modal top2 的参与模态 |
| `phases` | ✅ | Modal top2 的参与模态 |
| `amplitudes`（总幅值） | ❌ | 保持与现有 leaderboard 一致；门控概念验证阶段不引入新变量 |

### 2.2 门控信号来源

门控在**窗口级别**运行，每窗可用的信号包括：

| 信号 | 来源方法 | 含义 |
|------|----------|------|
| `BPM_vote` | T0-V3 | per-tone η·ρ 直方图投票结果 |
| `BPM_modal` | Modal top2 | top2 模态谱融合寻峰结果 |
| `BPM_single` | Single Remote | max-η tone 独立 BPM（robust fallback） |
| `conf_vote` | T0-V3 | voting 最高 bin 加权票数占比 |
| `win_mass_vote` | T0-V3 | 最高 bin 的绝对权重和 |
| `peak_dist` | 跨方法 | `|BPM_vote - BPM_modal|` |
| `η_vote_max` | T0-V3 | 参与 voting 的 tone 中最高 η |
| `ρ_vote_mean` | T0-v3 | 参与 voting 的 tone 的平均 ρ |
| `modal_eta_gap` | Modal top2 | top2 模态的 η 差距（top1 η − top2 η） |
| [待补充] | TRRS | TR-BREATH 谐振强度指标 |

---

## 3. 算法步骤

### 3.1 公共前置

```
数据源：BLE CS 72 tone
分段：config/scenarios/cs_*.json
滤波：median → highpass → bandpass（与 Plan2 相同）
滑窗：20 s / 1 s 步
呼吸带：0.1–0.35 Hz
```

### 3.2 门控框架

```
对每窗:
  1. 并行计算三个方法的 BPM:
     BPM_vote  ← T0-V3(remote_amplitudes, 72 tone)   # η·ρ 加权直方图投票
     BPM_modal ← Modal top2(remote, local, phase)     # top2 模态谱融合
     BPM_single ← Single Remote(max-η tone)           # robust fallback

  2. 计算门控信号:
     peak_dist = |BPM_vote - BPM_modal|
     conf_vote = winning_bin_mass / total_weight      # 0~1
     consensus = (peak_dist ≤ δ)                       # δ = 门控容忍度, BPM

  3. 门控决策:
     if consensus and conf_vote ≥ τ_hi:
       BPM_final = weighted_average(BPM_vote, BPM_modal)  # 二者一致且高质量
     elif consensus and conf_vote < τ_hi:
       BPM_final = BPM_modal                              # 一致但 voting 低质量 → 信 Modal
     elif not consensus and conf_vote ≥ τ_hi:
       BPM_final = BPM_vote                               # voting 高置信但分歧 → 信 voting（095806 模式）
     else:
       BPM_final = BPM_single                             # 都不好 → fallback
```

### 3.3 门控策略变体

| 策略 | δ (BPM) | τ_hi | 说明 |
|------|---------|------|------|
| **G1 — 简单共识** | 3.0 | 0.30 | voting 和 modal 在 3 BPM 内一致 → 取平均 |
| **G2 — 置信度优先** | 2.0 | 0.35 | 更严格的门控；分歧时用 conf 更高的方法 |
| **G3 — 自适应** | 2.0 ~ 5.0 | η-dependent | δ 随 max(η_vote, η_modal) 缩放：η 高时容忍度小 |
| **G4 — Single fallback** | — | — | 只在 voting 与 modal 分歧时退回 Single；一致时取 voting+modal 平均 |

### 3.4 待文献调研后追加的方法变体

> `[待文献调研后补充]`：
>
> - **G5 — TRRS 门控**：用 TRRS 替代/补充 conf_vote 作为门控信号
> - **G6 — SVM 窗级质量分类器**：用 Wi-Breath 的 SVM 特征工程思路训练窗级 quality classifier
> - **G7 — Bimodal CSI 体动检测器**：借鉴 [10] 的 motion detection 作为 "切换到 robust fallback" 的触发器

### 3.5 共识门控 vs 无门控的预期差异

```
无门控 T0-V3:
  091339: 段 3 某个窗 → per-tone BPM 多峰 → voting 选 8 BPM (错) → 误差大
  095806: 某个窗 → per-tone BPM 集中在 GT 附近 → voting 选正确 → 误差小

有门控:
  091339: 同窗 → voting 选 8, modal 选 14 → peak_dist = 6 > δ → conf_vote 可能低
         → 门控退回 Single 或 Modal → 避免 8 BPM 错误
  095806: 同窗 → voting 选 14, modal 选 14 → consensus → 取平均 → 保持优势
```

### 3.6 BPM 加权平均策略

当 voting 和 modal 共识（peak_dist ≤ δ）时：

```
BPM_final = (w_vote * BPM_vote + w_modal * BPM_modal) / (w_vote + w_modal)

其中:
  w_vote = conf_vote · max(η_vote_max, 0.05)
  w_modal = 1.0  # modal 不产出 conf，暂固定
```

---

## 4. Baseline 对比

### 4.1 必跑方法

| ID | 说明 | 来源 |
|----|------|------|
| B0 | Single Remote | chfusion baseline |
| B1 | Uniform Remote | chfusion baseline |
| B2 | Modal top2 equal | 当前跨域最优 baseline |
| B3 | Modal η-weight | Plan2 baseline |
| T0-V3 | Per-Tone η·ρ voting | Voting plan 最优 |
| **G1** | 简单共识门控（δ=3, τ_hi=0.30） | 本 plan §3.3 |
| **G2** | 置信度优先门控（δ=2, τ_hi=0.35） | 本 plan §3.3 |
| **G3** | 自适应门控 | 本 plan §3.3 |
| **G4** | Simple consensus + Single fallback | 本 plan §3.3 |

### 4.2 预期相对关系

| 对比 | 预期 | 理由 |
|------|------|------|
| G1 vs T0-V3 | 091339 改善、095806 略降 | 门控应阻止 091339 上的 voting 错误，但 095806 上可能因保守而损失一些窗 |
| G1 vs B2 (Modal) | 跨域优于或接近 Modal | 门控组合了两种方法的优势 |
| G4 vs G1 | 091339 更好、095806 略差 | Single fallback 在 voting-modal 分歧时更保守 |
| G1–G4 跨域 mean | 预期在 8.5–9.5% 区间 | 理想情况下接近 T0-V3 在 095806 的表现 + Modal 在 091339 的表现 |

### 4.3 文献调研后追加的 baseline

> `[待文献调研后补充]`：
>
> | G5 | TRRS 门控 | TR-BREATH [7] |
> | G6 | η/ρ/TRRS 联合特征 + threshold | — |
> | PCA 共识门控 | PCA-Modal3 + Plan2 Modal 共识（PCA plan Q3） | 与 G1 同框架、不同方法对 |

---

## 5. 评估设计

### 5.1 场景

| 场景 JSON | 用途 |
|-----------|------|
| `config/scenarios/cs_091339.json` | 主场景 — 验证门控能否阻止 voting 退化 |
| `config/scenarios/cs_095806.json` | 跨域 — 验证门控是否保留了 voting 的优势 |
| `config/scenarios/cs_102621.json` | 跨域 — 验证门控不引入新退化 |

### 5.2 指标

| 指标 | 说明 |
|------|------|
| 分段 BPM err% mean/std | 主指标 |
| 跨域 mean | 三场景平均 |
| 窗级门控动作分布 | `consensus & high-conf` / `consensus & low-conf` / `vote-high-conf` / `fallback` 四类占比 |
| 门控 vs 无门控窗级 BPM 偏差 | 分析门控改变了哪些窗的 BPM，方向是否正确 |
| 方法选择准确率 | 每窗比较门控选择的 BPM vs voting/modal/single 三者中最接近 GT 的 —— 门控是否选对了 |

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **理想** | 跨域 mean < 8.5%，且 091339 ≤ Modal top2（13.04%）+ 095806 ≤ T0-V3（6.84%）+ 1.5% |
| **最低** | 跨域 mean < 9.45%（不差于 Modal top2），且 091339 无灾难性退化（≤ 18%） |
| **失败** | 门控跨域 mean > Modal top2 + 2%（> 11.45%），或门控在 091339 上比 T0-V3 还差 |
| **部分成功** | 门控在某个场景上显著优于两种无门控方法，但跨域均值未改善 |

### 5.4 诊断产出

关键诊断：**窗级方法选择准确率热力图**。对每窗，找出 voting / modal / single 三者中 BPM 最接近 GT 的那个（oracle），然后统计门控选对/选错的比例。宽表如下：

| 场景 | 段 | oracle = voting | oracle = modal | oracle = single | 门控选对率 |
|------|-----|-----------------|----------------|-----------------|------------|
| 091339 | 3 | 30% | 45% | 25% | ? |
| 095806 | 1a | 55% | 30% | 15% | ? |
| ... | ... | ... | ... | ... | ? |

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 |
|------|------|
| 实验脚本 | `notebooks/scripts/chFusion_voting_gating.py` |
| 可复用模块 | `src/ble_analysis/consensus_gating.py`（新建，~200 行） |
| 场景配置 | 沿用现有 JSON |

### 6.2 复用 API

```python
from ble_analysis.chfusion import (
    ChFusionConfig, Plan2Config,
    run_multichannel_segment_filtering,
    run_modal_fusion_benchmark,
    estimate_segment_bpm_methods,        # Single/Uniform
    _energy_ratio, _peak_prominence,
    _find_best_channel, _weighted_median,
    _overall_rel_error, _seg_bpm_stats,
)
from ble_analysis.voting_fusion import (
    VotingConfig,
    estimate_bpm_per_tone,
    vote_bpm_weighted_histogram,
    vote_bpm_histogram,
    _vote_one_window,
    MODAL_VOTING_VARIABLES,
)
from ble_analysis.segments import (
    BreathMetricParams, FilterParams,
    _sliding_window_indices,
)
```

### 6.3 新增模块接口草案

`src/ble_analysis/consensus_gating.py`：

```python
__all__ = [
    "GatingConfig",
    "GatingStrategy",
    "GatingDecision",
    "compute_gating_signals",
    "apply_gating",
    "run_gating_benchmark",
]

@dataclass
class GatingConfig:
    """窗级共识门控配置"""
    delta_bpm: float = 3.0             # 共识容忍度 (BPM)
    tau_hi: float = 0.30               # voting 高置信度阈值
    fallback_method: str = "single"    # "single" | "modal"
    consensus_weighting: str = "conf"  # "equal" | "conf"
    min_eta_for_gating: float = 0.02   # η 过低时直接 fallback

class GatingDecision(Enum):
    CONSENSUS_HIGH = "consensus_high"      # 一致 + 高置信 → 平均
    CONSENSUS_LOW = "consensus_low"        # 一致 + 低置信 → 信 modal
    VOTE_HIGH_CONF = "vote_high_conf"      # 分歧 + vote 高置信 → 信 vote
    FALLBACK = "fallback"                  # 都不好 → fallback

def compute_gating_signals(
    bpm_vote: float, bpm_modal: float, bpm_single: float,
    conf_vote: float, conf_vote_mass: float,
    eta_vote_max: float, eta_modal_max: float,
    config: GatingConfig,
) -> Tuple[GatingDecision, float]:
    """返回 (决策类型, 最终 BPM)"""
    ...

def apply_gating(
    voting_results: dict,     # T0-V3 的完整结果
    modal_results: dict,      # Modal top2 的完整结果
    single_results: dict,     # Single Remote 的完整结果
    config: GatingConfig,
) -> dict:
    """完整门控 pipeline：逐窗计算信号 → 决策 → 汇总"""
    ...

def run_gating_benchmark(
    frames, segment_config, ...,
    gating_strategies: List[GatingConfig],
) -> dict:
    """跑所有门控策略 + 返回对比"""
    ...
```

### 6.4 伪代码：窗级门控循环

```python
# 对每段 breath 数据
for seg in breath_segments:
    gated_bpms = []
    decisions = []
    for w_idx, window in enumerate(sliding_windows(seg)):
        # 1. 获取三个方法在该窗的 BPM
        bpm_vote   = voting_results[seg][window].bpm       # T0-V3
        bpm_modal  = modal_results[seg][window].bpm        # Modal top2
        bpm_single = single_results[seg][window].bpm       # Single Remote

        # 2. 计算门控信号
        peak_dist   = abs(bpm_vote - bpm_modal)
        conf_vote   = voting_results[seg][window].confidence
        eta_vote    = voting_results[seg][window].max_eta
        eta_modal   = modal_results[seg][window].top2_eta_mean

        # 3. 门控决策
        decision, bpm_final = compute_gating_signals(
            bpm_vote, bpm_modal, bpm_single,
            conf_vote, peak_dist, eta_vote,
            config
        )

        gated_bpms.append(bpm_final)
        decisions.append(decision)

    # 段级统计
    seg_err = np.mean(np.abs(np.array(gated_bpms) - gt) / gt) * 100
```

### 6.5 不做的事

- 不引入新变量（总幅值等）
- 不在本 plan 阶段做 τ/δ 的 exhaustive grid search（留待实验脚本内快速扫描）
- 不修改 `voting_fusion.py` 或 `chfusion.py`
- 不新增场景 JSON

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| 验证报告 | `docs/reports/voting_gating_report.md` |
| 数值结果 | `outputs/reports/voting_gating_results.npy` |
| 跨域汇总 | `outputs/reports/voting_gating_cross_domain.npy` |
| 门控决策分布图 | `outputs/figures/voting_gating_decision_pie.pdf`（四类决策占比） |
| 对比柱状图 | `outputs/figures/voting_gating_comparison_bars.pdf`（G1–G4 vs T0-V3 vs Modal） |
| 方法选择准确率热力图 | `outputs/figures/voting_gating_oracle_heatmap.pdf` |

---

## 8. 风险与保留问题

### 8.1 算法风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 门控本身引入新错误——在 consensus 时取平均可能拉偏正确结果 | 中 | 诊断 oracle 选对率；如果平均比二选一更差，改用 "选更可信的" 而非平均 |
| δ = 2–3 BPM 是否合理？呼吸 BPM 变化缓慢（窗间差通常 < 2 BPM），但 GT 分辨率有限 | 低 | δ 在 1–5 BPM 范围内扫描 |
| Fallback 到 Single 在 091339 上本身就是 10.91%（比 Modal 13.04% 更好）——门控可能只是在学"多用 Single" | 中 | 报告门控决策分布；如果 >70% 窗 fallback 到 Single，说明门控没有真正融合两种方法 |
| 门控策略可能过拟合三场景的特定窗 | 高 | 明确标注"仅金属板三场景"；如需推广需要更多场景验证 |

### 8.2 保留问题

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | 门控最优 δ/τ_hi 是否跨场景一致？ | `[待确认]` — 需三场景分别扫描 |
| Q2 | η 是否足够作为"窗级可靠性"的代理？ | `[待确认]` |
| Q3 | Fallback 用 Single Remote 还是 Modal top2？091339 上 Single 更优（10.91% vs 13.04%），095806 上 Modal 更优（10.61% vs 12.16%） | `[待确认]` — 可能也需要场景自适应 |
| Q4 | [待文献调研后补充] TRRS / SVM 特征是否能提供更好的门控信号？ | |
| Q5 | [待文献调研后补充] 门控能否扩展到 PCA-Modal3 + Modal top2 的方法对？ | |

---

## 9. 文献调研衔接清单

以下章节预留了文献调研后的补充空间：

| 章节 | 当前状态 | 待补充内容 |
|------|----------|-----------|
| §1.3 | 写了 PCA Q3 和 Deng et al. τ | 追加 TR-BREATH TRRS、Wi-Breath SVM、Bimodal CSI motion detection 与本 plan 的关联 |
| §1.4 | 空 | 每个关键论文可借鉴的具体技术点 + 如何集成到门控框架 |
| §2.2 | 列出了 η/ρ/conf 等现有信号 | 追加 TRRS、SVM confidence score 等文献中的门控信号候选 |
| §3.4 | 空 | G5/G6/G7 方法定义 |
| §4.3 | 空 | 文献驱动的 baseline 方法 |
| §8.2 Q4/Q5 | 空 | 文献驱动的保留问题 |

---

## 10. 验证状态

| 字段 | 内容 |
|------|------|
| **验证状态** | 待实现（等待文献调研完成后更新 plan，再交给 Cursor Composer） |
| **实际脚本** | — |
| **报告链接** | — |
| **一句话结论** | — |

---

## 给执行 Agent 的首条指令

> ⚠️ **本 plan 尚未就绪**：请等待用户完成文献调研（`docs/plans/literature_review_plan.md`），由 Claude/DeepSeek 更新本 plan 的 `[待文献调研后补充]` 章节后，再在 Cursor Composer 中执行。
>
> 当前可执行的内容（如果用户选择不等待文献调研）：
> 1. 实现 §3.2–3.3 的 G1–G4 四种门控策略
> 2. 新增 `src/ble_analysis/consensus_gating.py`（接口见 §6.3）
> 3. 写 `notebooks/scripts/chFusion_voting_gating.py`
> 4. 跑 §4.1 的 10 个方法 × 三场景
> 5. 输出 §7 的图表和报告
> 6. 生成 §5.4 的 oracle 方法选择准确率分析
