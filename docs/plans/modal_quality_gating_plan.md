# 模态质量感知融合与门控 — 实现计划

> **来源**：`paper_draft_skeleton.md` §6.5 消融实验结果分析 + HKH 12 场景消融数据  
> **目标报告**：`docs/reports/modal_quality_gating_report.md`  
> **日期**：2026-07-26  
> **验证状态**：待实现

---

## 1. 动机与背景

| 项目 | 说明 |
|------|------|
| **问题** | HKH 消融实验（`ble_hkh_draft_ablation_summary.json`）揭示了两个关键发现：(1) BreatheCS 三模态等权融合（BPM=0.405）**略劣于** channel-only / 单模态 Remote/Local（0.376–0.381）；(2) Phase 模态在 HKH 上系统性极差（BPM=2.191），等权融合时污染了融合谱。需回答：**等权融合能否被质量感知融合超越？用什么指标做模态级质量判断？Phase 在什么条件下可用？** |
| **相关脚本/文档** | `b3_pipeline.py`（`DRAFT_ABLATION_SPECS` + `estimate_b3_window`）、`paper_draft_skeleton.md` §6.5、`ble_hkh_draft_ablation_summary.json` |
| **本 plan 定位** | 延续 §6.5 消融，从「等权融合是否优于不融合」推进到「质量感知融合能否超越等权融合 + 三选一」，并在 CS 金属板数据上做对照验证 |
| **物理背景** | Phase 由两端 PCT 向量相乘后取相位得到，其噪声为两端测量噪声的叠加。在低成本嵌入式设备（nrf54L15）上，相位测量噪声天然高于幅值。Phase 系统性劣于 Remote/Local 是**物理上可预期的**，不是算法缺陷。挑战在于：如何在不硬编码排除 Phase 的前提下，让管线自动识别并抑制其低质量窗口 |

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 核心幅值模态，物理意义明确（单端 PCT 幅值） |
| `local_amplitudes` | ✅ | 同上，与 remote 物理对等 |
| `phases`（总相位） | ✅（条件使用） | 两端测量叠加，噪声高于幅值模态；在少数窗口可能有独特贡献，需质量门控 |
| `amplitudes`（总幅值） | ❌ | 双方噪声乘积，无独立物理意义（已有定论） |

### 2.2 Phase 的物理局限

Phase 变量 $\Phi_i(t) = \angle(Z_{l,i}(t) \cdot Z_{r,i}(t))$ 含有两端 PCT 的相位噪声之和：

$$\text{Var}[\Phi] \approx \text{Var}[\angle Z_l] + \text{Var}[\angle Z_r]$$

而 Remote/Local 幅值仅含单端噪声。在低成本射频前端上，相位噪声分量通常大于幅值噪声分量。因此 **Phase 的平均质量低于幅值模态是合乎物理预期的**，不应被视为方法缺陷。

### 2.3 符号约定

| 符号 | 含义 |
|------|------|
| $\eta_m$ | 模态 $m$ 融合波形的呼吸频段能量比 |
| $\rho_m$ | 模态 $m$ 融合波形的谱峰峰度 |
| $w_m$ | 模态 $m$ 的融合权重，$w_m \propto \eta_m \cdot \max(\rho_m, 0)$ |
| $q_m$ | 模态 $m$ 的逐窗质量分数，用于门控判定 |
| $\theta_m$ | Phase 专用门控阈值 |

---

## 3. 算法步骤

本 plan 包含**四个实验模块**（E1–E4），按依赖关系排序。E1 是诊断基础，E2–E4 是算法改进。

### 整体流程图

```text
E1: Per-Window Modal Oracle Analysis（诊断，不产出新方法）
  │
  ├─► 输入：HKH 12 + CS 金属板 3 场景
  │     │
  │     └─► 每窗同时跑 Remote-only / Local-only / Phase-only（single-modal Voting）
  │            │
  │            ▼
  │         记录：每窗 GT → 哪个模态 BPM 最近？每模态 η, ρ, η·ρ, Voting confidence
  │            │
  │            ▼
  │         输出：模态最优比例分布（Remote/Local/Phase 各占多少窗）
  │               模态质量指标分布（η/ρ/η·ρ 的 per-modal histogram）
  │               质量指标 vs "是否为最优模态" 的 ROC/分类准确率
  │
  ├─► 回答：Phase 在多少窗口中是最优？用什么指标能选对最优模态？
  │
  ▼
E2: Quality Metric Evaluation for Modal Selection（诊断 → 指导 E3/E4 参数）
  │
  ├─► 比较候选指标：η-only / ρ-only / η·ρ / Voting winning mass / η·(1+ρ)
  │     │
  │     └─► 每窗：按各指标排序模态 → 检查 top-1 模态是否 = 实际最优模态
  │            │
  │            ▼
  │         输出：各指标的 top-1 命中率（= 选对最优模态的窗占比）
  │               各指标的 top-1 BPM err（选了该模态后的实际 BPM 误差）
  │
  ├─► 回答：η-only 还是 η·ρ 在模态选择上更准确？
  │         （回顾：CS 金属板上 η·ρ > η-only 在信道级已证实，但模态级未验证）
  │
  ▼
E3: Quality-Weighted Modal Fusion（替代等权融合）
  │
  ├─► 变体：
  │     E3a: w_m ∝ η_m（纯能量比加权）
  │     E3b: w_m ∝ η_m · max(ρ_m, 0)（η·ρ 加权）
  │     E3c: w_m ∝ η_m · coherence(m, ref)（η·γ 加权）
  │     E3d: w_m ∝ η_m · ρ_m · Voting confidence（三项乘积）
  │     │
  │     └─► 所有权重 per-window 归一化：w̃_m = w_m / Σw_j
  │           模态融合：S_final(f) = Σ w̃_m · S̄_m(f)，寻峰得 BPM
  │
  ├─► Baseline：Equal (1:1:1) = 当前 BreatheCS、Channel-only (三选一)
  │
  ├─► 回答：质量加权融合能否同时超越等权融合 AND channel-only？
  │
  ▼
E4: Phase-Specific Soft Gating（Phase 专用门控）
  │
  ├─► 策略：
  │     - 不预设 Phase 总是差（违反物理对称性）
  │     - 窗级计算 Phase 的质量分数 q_phase = η_phase · max(ρ_phase, 0)
  │     - 若 q_phase < θ（阈值），Phase 降权：w_phase ← w_phase × α（α ∈ [0, 0.5]）
  │     - Remote/Local 不做门控（它们在 HKH 上质量稳定）
  │     - 阈值 θ 通过 HKH 数据自适应确定（如 q_phase 的第 25 百分位）
  │
  ├─► 变体：
  │     E4a: Hard gate（q_phase < θ → w_phase = 0，即退化为 Remote+Local 等权）
  │     E4b: Soft gate（q_phase < θ → w_phase *= 0.3）
  │     E4c: Soft gate + quality-weighted fusion（E3 + E4 叠加）
  │
  ├─► 回答：Phase 门控后，三模态融合能否 ≤ channel-only 的 BPM？
  │         如果 Phase 几乎永不被选中，hard gate 是否等价于 channel-only (Remote+Local 子集)？
```

---

### 3.1 E1: Per-Window Modal Oracle Analysis（诊断）

**目的**：摸清三种模态在各窗口中的相对表现，确定"三选一"策略的理论上限。

**步骤**：

```text
对每个场景（HKH 12 + CS 金属板 3）：
  对每个滑窗（20 s / 1 s）：
    1. 计算单模态 Voting BPM（Remote-only / Local-only / Phase-only）
       [复用: estimate_b3_window() with draft_ms_* variant configs]
    2. 获取窗口 GT BPM（HKH: 呼吸带; CS: 金属板机械频率）
    3. 记录 3 个模态的 BPM 绝对误差
    4. 记录 3 个模态的 η, ρ, η·ρ, Voting winning mass
    5. 标记该窗口的"最优模态" = argmin |BPM_modal - BPM_GT|

输出：
  - 最优模态分布：Remote/Local/Phase 各自在多少窗中最优（总数 + 百分比）
  - Oracle BPM：每窗取最优模态的 BPM → 场景级 mean abs err
  - 备选模态的 margin：最优 vs 次优的 BPM 误差差距分布
```

**产出图表**：
- 三模态最优比例饼图/柱状图（按场景分面）
- Oracle BPM vs 各单模态 BPM 的 leaderboard
- Phase 最优的窗口的 η_phase 分布（看是否有一个可辨识的高 η 子集）

### 3.2 E2: 模态级质量指标评估

**目的**：确定用哪个指标做模态选择/加权最可靠。

**步骤**：

```text
对每个窗口（复用 E1 的 per-window 数据）：
  1. 按各候选指标对各模态排序
  2. 检查指标排名 top-1 的模态是否 = 实际最优模态（来自 E1 GT）
  3. 计算 top-1 命中率 = 选对的窗口 / 总有效窗口
  4. 计算若按 top-1 指标选模态，实际 BPM 误差（vs oracle BPM）

候选指标：
  - η-only                    [用户关注的：是否 η 就够了]
  - ρ-only                    [对照]
  - η·ρ                       [当前信道级使用的指标]
  - Voting winning mass       [当前 spectral pick_best 实际使用的]
  - η · (1 + ρ)               [η 为主，ρ 做调制]
```

**产出图表**：
- 各指标 top-1 命中率 bar chart（HKH 和 CS 分开）
- 各指标的"实际选择 BPM err" vs "Oracle BPM err" 对比

### 3.3 E3: 质量加权模态融合

**目的**：用 E2 确定的最优指标做模态级加权融合，替代 1:1:1 等权。

**步骤**：

```text
修改 estimate_b3_window() 的模态融合逻辑：
  当前（等权）：
    modal_fusion_from_spectra(spectra, scores, weight_mode="equal", ...)
  
  新增（质量加权）：
    modal_fusion_from_spectra(spectra, quality_weights, weight_mode="custom", ...)
    其中 quality_weights = {m: w_m}，w_m 来自 E2 选定的最优指标

实现位置：
  - src/ble_analysis/systematic_fusion.py: modal_fusion_from_spectra()
    新增 weight_mode="custom" 分支，接受显式权重 dict
  - src/ble_analysis/b3_pipeline.py: DRAFT_ABLATION_SPECS
    新增 E3a–E3d 变体
```

**变体矩阵**：

| Key | 描述 | 模态权重 |
|-----|------|----------|
| `draft_s_full` | Equal（当前 BreatheCS） | 1:1:1 |
| `e3a_eta_weighted` | η 加权 | w_m = η_m |
| `e3b_eta_rho_weighted` | η·ρ 加权 | w_m = η_m · max(ρ_m, 0) |
| `e3c_eta_coherence_weighted` | η·γ 加权 | w_m = η_m · γ(m, ref) |
| `e3d_eta_rho_conf_weighted` | η·ρ·conf 三项乘积 | w_m = η_m · ρ_m · Voting winning mass |

**Baseline**：
- `draft_s_channel`（channel-only = Voting → pick best modal）
- `draft_s_full`（BreatheCS = Voting → equal fusion）
- Remote-only / Local-only（单模态上限参考）

### 3.4 E4: Phase 专用软门控

**目的**：Phase 在多数窗口差，但可能在少数窗口有独特贡献——软门控使其在高质量窗口时参与、低质量窗口时退避。

**步骤**：

```text
修改 estimate_b3_window() 的模态融合权重计算：
  1. 计算三模态基础权重 w_m（来自 E3 选定的最优方案）
  2. Phase 专用调整：
     if q_phase < θ:
       w_phase ← w_phase × α  (α 为衰减因子)
  3. 其他模态不做门控调整
  4. 所有权重重新归一化
  5. 加权谱融合 → BPM

阈值 θ 的确定：
  方案 A（数据驱动）：HKH 上 q_phase 的第 P 百分位（P 从 {10, 25, 50} 扫描）
  方案 B（物理驱动）：q_phase < q_remote · 0.5 → 降权（Phase 质量显著低于幅值模态时）

衰减因子 α 扫描：{0, 0.1, 0.3, 0.5}
  α=0 → hard gate（Phase 完全排除）
  α=0.3 → soft gate（Phase 贡献降低但不为零）
```

**变体矩阵**：

| Key | 描述 | 门控方式 |
|-----|------|----------|
| `e4a_hard_pXX` | Phase q < PXX 时 weight=0 | Hard gate |
| `e4b_soft_pXX` | Phase q < PXX 时 weight*=0.3 | Soft gate |
| `e4c_quality_soft` | E3b (η·ρ 加权) + E4b (Phase soft gate) | 叠加 |

---

## 4. Baseline 对比

执行 Agent 必须跑齐以下方法：

### 4.1 已有方法（复用既有结果）

| 方法 Key | 描述性名称 | 来源 |
|----------|-----------|------|
| `draft_s_remote` | Remote 单模态 Voting | 已有（0.376） |
| `draft_s_local` | Local 单模态 Voting | 已有（0.378） |
| `draft_s_phase` | Phase 单模态 Voting | 已有（2.191） |
| `draft_s_channel` | Voting → 三选一最优模态 | 已有（0.381） |
| `draft_s_full` | Voting → 三模态等权融合（BreatheCS） | 已有（0.405） |
| `draft_s_none` | 两级均选最优（单 tone 单模态） | 已有（1.640） |

### 4.2 新增方法（本 plan 待实现）

| 方法 Key | 描述性名称 | 所属实验 |
|----------|-----------|----------|
| `e3a_eta_weighted` | Voting → η 加权模态融合 | E3 |
| `e3b_eta_rho_weighted` | Voting → η·ρ 加权模态融合 | E3 |
| `e3c_eta_coherence_weighted` | Voting → η·γ 加权模态融合 | E3 |
| `e3d_eta_rho_conf_weighted` | Voting → η·ρ·conf 加权模态融合 | E3 |
| `e4a_hard_pXX` | Voting → η·ρ 加权 + Phase hard gate | E4 |
| `e4b_soft_pXX` | Voting → η·ρ 加权 + Phase soft gate | E4 |
| `e4c_quality_soft` | E3b + E4b 叠加 | E4 |

### 4.3 预期相对关系（研究假设，可被推翻）

| 对比 | 预期 | 理由 |
|------|------|------|
| E3a–E3d vs Equal (0.405) | **优于或持平** | 质量加权抑制弱模态贡献，应 ≤ 等权 |
| E3a–E3d vs Channel-only (0.381) | **接近或略优** | 质量加权优于硬选（保留 diversity），但若 Phase 完全无信息则可能持平 |
| E4 vs E3 | **略优或持平** | Phase 门控在 Phase 极差窗口降低其权重 |
| η-only vs η·ρ for modal selection (E2) | **待实验确定** | CS 金属板上 η·ρ 在信道级优于 η-only，但模态级可能不同（模态数少、差异大） |

---

## 5. 评估设计

### 5.1 场景

| 数据 | 场景 | 用途 | 备注 |
|------|------|------|------|
| **HKH 真人** | 3 Room × 4 Subject = 12 条 | 主评估（已有数据） | 呼吸带 GT；BPM 绝对误差 breaths/min |
| **CS 金属板** | `cs_091339` / `cs_095806` / `cs_102621` | 对照验证 | 机械振动 GT；BPM 相对误差 % |

> ⚠️ **HKH 和 CS 金属板必须分开展示结果**——实验对象不同（真人 vs 金属板），指标不同（绝对误差 vs 相对误差%），不可合并跨域 mean。

### 5.2 指标

| 指标 | HKH | CS 金属板 | 说明 |
|------|-----|-----------|------|
| BPM 绝对误差 mean ± std | ✅ 主指标 | — | breaths/min |
| BPM 相对误差 % mean ± std | — | ✅ 主指标 | % |
| E1 Oracle 最优模态比例 | ✅ | ✅ | Remote/Local/Phase 各自最优的窗占比 |
| E2 模态选择 top-1 命中率 | ✅ | ✅ | 指标选对最优模态的窗占比 |

### 5.3 成功标准

| 级别 | 条件 |
|------|------|
| **最低** | E3 质量加权融合在 HKH 上 BPM ≤ 0.405（不劣于等权）；CS 金属板对照完成 |
| **理想** | E3 质量加权融合在 HKH 上 BPM ≤ 0.381（不劣于 channel-only）；Phase 在 ≥5% 窗口中有正贡献；Phase 门控使融合 BPM 接近单模态最优 |
| **失败** | 所有质量加权变体均劣于等权（0.405）或 Channel-only（0.381）超过 0.02 BPM |

---

## 6. 实现要点

### 6.1 建议文件

| 类型 | 路径 | 操作 |
|------|------|------|
| E1 诊断脚本 | `notebooks/scripts/chFusion_modal_oracle_diag.py` | **新建** |
| E2–E4 实验脚本 | `notebooks/scripts/chFusion_modal_quality_gating.py` | **新建** |
| 模态融合 | `src/ble_analysis/systematic_fusion.py` | **扩展**：`modal_fusion_from_spectra()` 新增 `weight_mode="custom"` |
| B3 Pipeline | `src/ble_analysis/b3_pipeline.py` | **扩展**：`DRAFT_ABLATION_SPECS` 追加 E3/E4 变体；`estimate_b3_window()` 支持质量加权融合 |
| CS 金属板数据加载 | 复用 `chfusion.py` → `load_multichannel_for_scenario()` | 不需改动 |

### 6.2 复用 API

```python
# 已有，直接复用
from ble_analysis.b3_pipeline import (
    DRAFT_ABLATION_SPECS,        # 扩展追加 E3/E4 变体
    estimate_b3_window,           # 核心修改点：模态融合权重
    validate_b3_variant_against_hkh,  # HKH 评估
)
from ble_analysis.systematic_fusion import (
    modal_fusion_from_spectra,   # 扩展 weight_mode="custom"
    per_modal_voting_spectrum,   # 不变
)
from ble_analysis.chfusion import (
    ChFusionConfig,
    load_multichannel_for_scenario,  # CS 金属板数据加载
)

# E1 诊断需要的新函数签名建议
def compute_modal_oracle_per_window(
    multichannel_by_var, seg_name, ch_list, starts, fs, cfg, gt_bpm_per_window
) -> dict:
    """返回 per-window 最优模态标签 + 各模态质量指标"""
    ...

# E2 质量指标评估
def evaluate_modal_selection_metric(
    per_window_data, metric_name: str
) -> dict:
    """返回 top-1 命中率、实际 BPM err"""
    ...
```

### 6.3 `modal_fusion_from_spectra` 扩展草案

```python
def modal_fusion_from_spectra(
    spectra_by_var: Dict[str, np.ndarray],
    scores_by_var: Dict[str, float],
    weight_mode: str = "equal",       # "equal" | "top2_equal" | "energy_ratio" | "custom"
    band_freqs: Optional[np.ndarray] = None,
    cfg: Optional[ChFusionConfig] = None,
    custom_weights: Optional[Dict[str, float]] = None,  # 新增：显式权重
) -> Tuple[float, str]:
    """
    weight_mode="custom" 时使用 custom_weights 做加权平均。
    否则行为不变（向后兼容）。
    """
```

### 6.4 E1 诊断脚本的 per-window 数据收集

E1 需要收集每个窗口的以下字段（保存为 `.npy` 或 `.json`）：

```python
per_window_record = {
    "window_idx": int,
    "bpm_remote": float,    # Remote-only Voting BPM
    "bpm_local": float,     # Local-only Voting BPM
    "bpm_phase": float,     # Phase-only Voting BPM
    "bpm_gt": float,        # ground truth
    "eta_remote": float,    # Remote 融合谱的 η
    "eta_local": float,
    "eta_phase": float,
    "rho_remote": float,    # Remote 融合谱的 ρ
    "rho_local": float,
    "rho_phase": float,
    "conf_remote": float,   # Voting winning mass
    "conf_local": float,
    "conf_phase": float,
    "best_modal": str,      # "remote" | "local" | "phase" (from GT)
}
```

### 6.5 不做的事

- 不修改原始数据、GT、滤波参数
- 不改动 HKH 数据加载管线
- 不修改 `coherent_mrc.py`（波形分支不在本轮范围）
- 不在本 plan 中实现新的门控架构（G4/G5 系列）——E4 的 Phase 门控是模态融合权重层面的简单调整

---

## 7. 预期产出

| 产出 | 路径 |
|------|------|
| E1 诊断数据 | `outputs/reports/modal_oracle_per_window.npy`（或 `.json`） |
| E1 诊断图 | `outputs/figures/modal_oracle_optimal_pie.png`、`modal_oracle_phase_eta_dist.png` |
| E2 指标评估图 | `outputs/figures/modal_selection_metric_accuracy.png` |
| E3/E4 HKH 结果 | `outputs/reports/modal_quality_gating_hkh_summary.json` |
| E3/E4 CS 金属板结果 | `outputs/reports/modal_quality_gating_cs_summary.json` |
| E3/E4 汇总图 | `outputs/figures/modal_quality_gating_hkh_leaderboard.png`、`modal_quality_gating_cs_leaderboard.png` |
| Per-window 质量分布图 | `outputs/figures/modal_quality_per_window_scatter.png` |
| 验证报告 | `docs/reports/modal_quality_gating_report.md` |
| 实验脚本 | `notebooks/scripts/chFusion_modal_oracle_diag.py`、`notebooks/scripts/chFusion_modal_quality_gating.py` |

---

## 8. 验证状态与保留问题

> 由**执行 Agent** 在实验后更新本节。

| 字段 | 内容 |
|------|------|
| **验证状态** | 待实现 |
| **实际脚本** | — |
| **报告链接** | — |
| **一句话结论** | — |

### 保留问题

| ID | 问题 | 备注 |
|----|------|------|
| Q1 | Phase 在 CS 金属板上是否和 HKH 一样差？ | CS 金属板单模态消融未跑；若 Phase 在金属板上不差，说明问题在 HKH 数据特性 |
| Q2 | η-only vs η·ρ 在模态级选择上谁更准？ | 信道级 η·ρ 更好（T0-V3 > T0-V2），但模态级可能不同（仅 3 个模态，差异大） |
| Q3 | Phase 的最优窗口是否有可辨识的质量特征？ | E1 诊断回答——若 Phase 最优的窗口有系统性高 η/ρ，门控可精确启用 |
| Q4 | 质量加权融合在 CS 金属板场景是否也有增益？ | 需 E3 对照实验回答 |
| Q5 | Phase 是否在波形恢复（RMSE）上有独特贡献，即使 BPM 很差？ | 本轮聚焦 BPM；波形分支的 Phase 角色留待后续 plan |

---

## 9. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，按以下顺序执行：

1. **先读** `docs/plans/modal_quality_gating_plan.md` 全文
2. **E1 诊断**：实现 `notebooks/scripts/chFusion_modal_oracle_diag.py`，收集 HKH 12 + CS 金属板 3 场景的 per-window 最优模态数据
3. **E2 指标评估**：基于 E1 输出，评估 η-only / η·ρ / Voting conf 等指标的模态选择准确率
4. **E3 质量加权融合**：扩展 `modal_fusion_from_spectra()` 支持 `weight_mode="custom"`，在 `DRAFT_ABLATION_SPECS` 中追加 E3a–E3d 变体，在 HKH 12 + CS 金属板 3 上运行
5. **E4 Phase 门控**：追加 E4a–E4c 变体，运行评估
6. **撰报告**：按 `docs/templates/algorithm_validation_report.md` 模板写 `docs/reports/modal_quality_gating_report.md`
7. **回填本 plan §8** 的验证状态

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/modal_quality_gating_plan.md`
- `docs/reports/modal_quality_gating_report.md`
- `outputs/reports/modal_quality_gating_*_summary.json`
- `outputs/reports/modal_oracle_per_window.npy`
- `outputs/figures/modal_*`
- 关键脚本路径
- git commit message

> ⚠️ **HKH 和 CS 金属板结果必须分表/分图展示**，不可合并跨域 mean。HKH 用 BPM 绝对误差 (breaths/min)，CS 金属板用 BPM 相对误差 %。
