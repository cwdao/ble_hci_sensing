# 金属板位置扫描 + 人体对照观测 — 验证报告

> **Plan**：[`docs/plans/position_sweep_observation_plan.md`](../plans/position_sweep_observation_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_position_sweep_observation.py`（模块：`src/ble_analysis/jsonl_loader.py`）  
> **场景**：新数据 `sampleData/metal_verify/`（非 `config/scenarios/cs_*.json`；本 plan 为定性观测实验）  
> **日期**：2026-08-05  
> **状态**：已完成

> **本轮增补（审阅入口）**  
> 1. [§4.3.4b](#434b-与-draft-fig-3cd-的差异如何解释) — Draft Fig 3c/d「随机」vs 本次 D2「规整」  
> 2. [§4.3.5](#435-图-e--人体-vs-金属板h5) — E3：ρ 剧降 / η 相对稳健（含数字表与限定）  
> 3. [§4.3.6](#436-对算法质量门控的含义ηρ乘起来是否仍合适) — 人体部署下 η·ρ 乘积是否合适  
> 4. [§5 结论](#5-结论) / [§6 Q6–Q7](#6-开放问题与下一步)

---

## 1. 目标与假设

本实验为**定性观测**（非 BPM 算法验证），从金属板 100→85 cm 连续位置扫描与同距离人体对照中提取论文 Chapter 4 可视化素材。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | 同一典型信道在连续位置变化下，幅值与合成相位波形差异化演变（互补性 / position dependence） | §4 图 A |
| H2 | 同一模态内不同信道因频率差异，在连续 3 cm 位置过渡中响应互换 | §5 图 B |
| H3 | 信道间相位偏移 / 相干性随位置变化（Good vs Hard） | §6 图 C |
| H4 | 三模态间 Δφ 随位置系统性变化（非随机噪声） | §7 图 D |
| H5 | 合成相位在金属板上与幅值 η 相近，在人体呼吸中 η 系统性下降 | §8 图 E |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | `remote_amplitudes` / `local_amplitudes` / `phases`（合成相位 = ∠(I+jQ)） |
| 预处理 | 每段独立；median(w=3) → HP 0.05 Hz（图 A/B）；再 + BP 0.1–0.35 Hz（图 C/D/E） |
| 重采样 | 段内中位间隔估计 fs（≈2.5 Hz），均匀网格线性插值；tone 内孤立 NaN 先填补 |
| 信道融合 | 无（单信道或叠加展示） |
| 模态融合 | 无 |
| 质量指标 | η = `_energy_ratio`(HP)；ρ = `_peak_prominence`(BP) |

**固定典型信道（图 A/D1）**：`ch66`（16 段 × 三模态均值 η 的中位数信道，median-η≈0.878）  
**图 B1/B2 信道**：均匀间隔 `ch20, ch40, ch60`（避免相邻 tone 波形几乎重合）  
**图 D2 信道**：多样对 `ch35, ch71` + 均匀间隔 `ch20, ch40, ch60`

---

## 3. 实验设置

| 数据集 | 文件 | 备注 |
|--------|------|------|
| 金属板扫描 | `sampleData/metal_verify/CS_frames_all_20260804_090719.jsonl` | 1394 frames；16 段 seq 标记；100→85 cm |
| 人体呼吸 | `sampleData/metal_verify/CS_frames_all_20260804_094043.jsonl` | 296 frames；H1/H2/H3 = 80/90/100 cm |

| 人体段 | seq | 实际帧数 | 距离 |
|--------|-----|----------|------|
| H1 | 30–210 | 109 | 80 cm |
| H2 | 320–380 | 36 | 90 cm（较短） |
| H3 | 397–470 | 44 | 100 cm |

- **Baseline**：无算法 baseline；对照旧 Fig 2/3 的展示格式（波形对齐 + γ 热力图）
- **指标**：η、ρ、Δφ、γ（定性）；无 BPM err%
- **距离对齐（图 E）**：100 cm 精确；90 cm 精确；80 cm 人体 vs 金属板 **85 cm（seg16）** 并标注

---

## 4. 结果

### 4.1 主结果表（人 vs 金属板，逐信道 η 均值）

| 距离 | 变量 | Metal η | Human η | Metal ρ | Human ρ | 备注 |
|------|------|--------:|--------:|--------:|--------:|------|
| 100 cm | remote | 0.807 | 0.802 | — | — | 精确对齐；seg1 去除走动 seq≤450 |
| 100 cm | local | ≈remote | ≈remote | — | — | 见 E2/E3 图 |
| 100 cm | phase | 0.680 | 0.546 | — | — | 人体相位 η 略低 |
| 90 cm | remote | 0.656 | 0.856 | — | — | 人体幅值更高 |
| 90 cm | phase | 0.939 | 0.471 | — | — | **相位人体明显劣化** |
| 80≈85 cm | remote | 0.933 | 0.803 | — | — | 距离非精确匹配 |
| 80≈85 cm | phase | 0.730 | 0.729 | — | — | 相位 η 接近 |

精确数字见 `outputs/reports/position_sweep_observation_meta.json` 与 `position_sweep_human_vs_metal_quality.npy`。

### 4.2 与 plan 预期对比

| 预期（Plan） | 实际 | 是否一致 |
|--------------|------|----------|
| 产出图 A–E 全套 | 68 张 PNG（含 A1×16、D1×16、C1/C2×12 等） | ✅ |
| 典型信道非最优/非最差 | ch66，median-η≈0.878 | ✅ |
| 幅度-相位位置依赖可见 | A3：seg7 vs seg14 波形形态差异明显 | ✅（定性） |
| Good/Hard γ 热力图有对比 | Good 几乎全局高 γ；单 tone 失效带可见；Hard 需对照图 | 部分（Q3 风险兑现） |
| 人体相位 η 系统性下降 | 90 cm 清晰；100 cm 轻度；80 cm 不明显 | **部分支持** |

### 4.3 现象与图

> 图片路径相对本报告：`../../outputs/figures/`。全量约 68 张；下文内嵌**主图**，其余 A1/D1 分立图见 §7。

#### 4.3.1 图 A — 固定信道三变量位置扫描（H1）

固定 ch66，HP-only。remote/local 高度重合；合成相位与幅值峰形/相位关系随距离变化。

**A3 选址对比（seg7 @94 cm vs seg14 @87 cm）**

![Fig A3 selected positions ch66](../../outputs/figures/position_sweep_figA3_selected_positions.png)

解读：两位置下幅值振荡形态与相位峰值形状明显不同，支持幅度–相位互补 / position dependence。

**A2 拼合长图（100→85 cm）**

![Fig A2 stitched 100 to 85 cm](../../outputs/figures/position_sweep_figA2_stitched.png)

解读：自上而下距离由近到远；可沿位置连续追踪三变量波形演变。完整 16 张分立图：`position_sweep_figA1_seg{N}_{dist}cm.png`。

#### 4.3.2 图 B — 同模态多信道 × 连续位置（H2）

seg13–15（88→86 cm），信道改为均匀间隔 **ch20 / ch40 / ch60**（原 η 敏感选道含相邻 70/71，对比度不足）。

**B1 Remote**

![Fig B1 remote](../../outputs/figures/position_sweep_figB1_remote.png)

**B1 Local**

![Fig B1 local](../../outputs/figures/position_sweep_figB1_local.png)

**B1 Phase**

![Fig B1 phase](../../outputs/figures/position_sweep_figB1_phase.png)

**B2 信道×位置矩阵（Remote，spaced tones）**

![Fig B2 channel-position matrix](../../outputs/figures/position_sweep_figB2_channel_position_matrix.png)

解读：ch20/40/60 在同一 3 cm 过渡内波形形态可区分，优于相邻 tone 叠加。

#### 4.3.3 图 C — Good vs Hard 信道相位关系（H3）

Good = seg5（96 cm）；Hard = seg14（87 cm）。C1：(a) BP 叠加 → (b) corr-sign → (c) Hilbert 对齐。

**C1 Good / Remote**

![Fig C1 good remote](../../outputs/figures/position_sweep_figC1_good_remote.png)

**C1 Hard / Remote**

![Fig C1 hard remote](../../outputs/figures/position_sweep_figC1_hard_remote.png)

**C1 Good / Phase**

![Fig C1 good phase](../../outputs/figures/position_sweep_figC1_good_phase.png)

**C1 Hard / Phase**

![Fig C1 hard phase](../../outputs/figures/position_sweep_figC1_hard_phase.png)

**C2 γ 热力图（Remote）**

![Fig C2 heatmap good remote](../../outputs/figures/position_sweep_figC2_heatmap_good_remote.png)

![Fig C2 heatmap hard remote](../../outputs/figures/position_sweep_figC2_heatmap_hard_remote.png)

解读：单房间内 γ 常接近饱和（Q3）；失效 tone 呈十字暗带。论文主图建议优先 C1，热力图可作附录。其余模态：`figC1_*_{local,phase}.png`、`figC2_heatmap_*_{local,phase}.png`。

#### 4.3.4 图 D — 模态间 Δφ 随位置（H4）

**D1 示例（seg7 / seg14，典型信道 ch66）**

![Fig D1 seg7 94cm](../../outputs/figures/position_sweep_figD1_seg7_94cm.png)

![Fig D1 seg14 87cm](../../outputs/figures/position_sweep_figD1_seg14_87cm.png)

**D2 Δφ vs 距离 — 多样对 ch35 / ch71**

![Fig D2 dphi ch35](../../outputs/figures/position_sweep_figD2_dphi_vs_position_ch35.png)

![Fig D2 dphi ch71](../../outputs/figures/position_sweep_figD2_dphi_vs_position_ch71.png)

**D2 Δφ vs 距离 — 均匀间隔 ch20 / ch40 / ch60**

![Fig D2 dphi ch20](../../outputs/figures/position_sweep_figD2_dphi_vs_position_ch20.png)

![Fig D2 dphi ch40](../../outputs/figures/position_sweep_figD2_dphi_vs_position_ch40.png)

![Fig D2 dphi ch60](../../outputs/figures/position_sweep_figD2_dphi_vs_position_ch60.png)

解读：Δφ(R,L) 接近 0（remote/local 同相）；相对 phase 的 Δφ 随距离跳变，支持位置依赖。论文可主用 ch35+ch71，或改用 20/40/60 中对比最清晰的一条。

#### 4.3.4b 与 Draft Fig 3c/d 的差异如何解释

| | Draft Fig 3c/d | 本次 D2 |
|--|----------------|---------|
| 对象 | 各模态 **Level-1 多 tone 融合后** 的波形 | **单个 tone** 上的三模态 |
| X 轴 | 固定几何下的 **滑窗时间** | **受控距离** 100→85 cm |
| 物理含义 | 「同一位置、估计是否稳定」 | 「几何一变，相位关系怎么走」 |

二者**不矛盾**，测的不是同一件事：

1. **Tone 融合混入异质信道**：72 tone 处于不同菲涅尔状态；每窗 η 权重变化会改变融合波形的有效组成，使模态间 Δφ 跳变——即便单 tone 上 remote–local 其实很稳。
2. **X 轴语义不同**：Fig 3 在位置几乎不变时主要看到估计噪声、短时非平稳与相位 wrap（±π），显得「随机」；D2 是几何参数扫描，多径干涉缓慢变化，Δφ 可呈准周期/分段跃变。
3. **Δφ(R,L)≈0 在单 tone 上合理**：两端幅值同为径向投影、互易路径；融合后两边可能偏重不同 tone 子集，Fig 3 中 R–L 也会乱跳。

**论文表述建议**：Fig 3c/d →「融合模态波形的窗间 Δφ 不稳定、场景依赖 → 需 per-window 对齐」；本次 D2 →「单 tone 上 Δφ 随距离系统性演变（R–L 近 0；相对 phase 准周期）→ 支持多相量 / 径向–切向模型」。前者暴露融合后估计波动，后者暴露单信道几何规律。

#### 4.3.5 图 E — 人体 vs 金属板（H5）

**E2 η 对比**

![Fig E2 eta comparison](../../outputs/figures/position_sweep_figE2_eta_comparison.png)

**E3 η + ρ 联合对比**

![Fig E3 eta rho comparison](../../outputs/figures/position_sweep_figE3_eta_rho_comparison.png)

**逐信道均值（金属板 → 人体；相对变化）**

| 距离 | 变量 | η metal→human | ρ metal→human |
|------|------|---------------|---------------|
| 100 cm | remote | 0.807→0.802（−0.7%） | 4.4→3.1（−28%） |
| 100 cm | phase | 0.680→0.546（−20%） | 6.0→2.8（−53%） |
| 90 cm | remote | 0.656→0.856（**+30%**） | 54→2.5（**−95%**） |
| 90 cm | phase | 0.939→0.471（−50%） | 62→2.3（**−96%**） |
| 80≈85 cm | remote | 0.933→0.803（−14%） | 315→21（**−93%**） |
| 80≈85 cm | phase | 0.730→0.729（≈0%） | 112→7.1（**−94%**） |

解读（是否「ρ 剧降、η 降得不多」）：

- **对幅值模态（remote/local）、尤其 90/80 cm：基本准确。** η 变化温和甚至人体更高（90 cm），ρ 下降约一个数量级。
- **需限定**：100 cm 时 ρ 只降约 28%，并非「剧烈」；相位模态在 90 cm 上 **η 与 ρ 都明显下降**。
- **物理原因（定性）**：金属板近正弦机械运动 → 呼吸带谱峰极尖，ρ=max(P)/median(P) 可达数十～数百；人体自然呼吸含速率漂移、谐波与体动 → 能量仍可落在 0.1–0.35 Hz（η 不崩），但峰不再尖锐（ρ 崩）。注意：项目中 ρ 是 **谱峰突出度**，不是统计峰度。

**E1 波形对照（相位，三距离）**

![Fig E1 100cm phase](../../outputs/figures/position_sweep_figE1_100cm_phase.png)

![Fig E1 90cm phase](../../outputs/figures/position_sweep_figE1_90cm_phase.png)

![Fig E1 80cm phase](../../outputs/figures/position_sweep_figE1_80cm_phase.png)

**E1 幅值对照（remote，三距离）**

![Fig E1 100cm remote](../../outputs/figures/position_sweep_figE1_100cm_remote.png)

![Fig E1 90cm remote](../../outputs/figures/position_sweep_figE1_90cm_remote.png)

![Fig E1 80cm remote](../../outputs/figures/position_sweep_figE1_80cm_remote.png)

解读：90 cm 相位 η 人体明显低于金属板；100 cm 轻度；80≈85 cm 接近——**H5 仅部分距离成立**。其余 local 波形：`figE1_{80,90,100}cm_local.png`。

#### 4.3.6 对算法质量门控的含义：η·ρ「乘起来」是否仍合适？

现有投票 / 加权常用 `q = η · clip(ρ, 0)`（如 B3 `eta_rho_weighted`）。E3 提示：

| 风险 | 说明 |
|------|------|
| **跨域尺度不可比** | 金属板 ρ 可达 50–300，人体常落在 2–20；同一套绝对阈值 / 乘积在跨域迁移时会过度打压人体 tone |
| **人体上 ρ 动态范围压缩** | 若多数 tone 的 ρ≈2–3，则 `η·ρ ≈ c·η`，ρ 几乎不再提供排序信息；或相反，ρ 的微小噪声主导排序 |
| **η 与 ρ 回答不同问题** | η：「能量是否在呼吸带？」；ρ：「是否有尖锐单峰？」人体常「有带能量、无尖峰」——乘积要求两者同时高，可能误杀仍可用于 BPM 的宽带呼吸能量 tone |

**因此：描述准确（在 90/80 cm 幅值上尤甚）；乘积门控对人体并非自动作废，但不宜默认沿用金属板标定的绝对尺度。**

更稳妥的方向（供 Research / 下一轮 plan，本报告不改算法）：

1. **域内相对化**：每窗对 ρ 做 rank / 分位数归一，再与 η 结合；
2. **主 η、辅 ρ**：`q = η · softgate(ρ)`（ρ 过低才降权），避免线性乘积把人体 ρ 压成近零；
3. **任务拆分**：BPM 谱峰搜索更吃 ρ；波形/能量融合更吃 η——不必同一 `η·ρ` 通吃；
4. **HKH 上消融**：直接对比 `η` vs `η·ρ` vs `η·log(1+ρ)` 的跨域 BPM，以实证决定是否保留乘积。

本观测实验**不能**单独判定乘积该废弃；它只表明：**跨域时 ρ 的边际信息与尺度与金属板差异极大，乘积假设需要在人体数据上重新验证。**

---

## 5. 结论

| 结论 | 证据强度 |
|------|----------|
| 位置扫描可提供连续位置下三变量波形素材（图 A/B/D） | **已验证**（本数据集定性） |
| 信道间 γ / 相位对齐图可按旧 Fig 2 格式复现 | **已验证**（产出完成）；跨位置视觉差异强度 **部分** |
| 合成相位在人体上 η 系统性低于金属板 | **仅部分距离成立**（90 cm 强；100/80 cm 弱或无） |
| 人体相对金属板：ρ 剧降、η 相对稳健（幅值 90/80 cm） | **已验证**（本对照）；100 cm / 相位 η 需单独看 |
| Fig 3c/d「随机」与 D2「规整」可并存解释 | **已验证**（方法学差异：融合滑窗 vs 单 tone 位置扫描） |
| 可直接替代旧 Fig 2/3 | **未证实**（本 plan 定位为补充扩展） |
| 人体部署应废弃 η·ρ 乘积 | **未证实**（需 HKH 消融）；本实验仅提示尺度与角色需重估 |

**相对 baseline**：不适用（非算法对比）。

**部署建议**：图 A/B/D/E 可作为论文 §4.2–4.4 素材候选；图 C 热力图若视觉冲击不足，建议论文中优先用 C1 波形列，热力图作附录或仅保留 Good/Hard 差分更明显的模态。人体算法侧：勿直接沿用金属板绝对 ρ 尺度的 η·ρ 乘积；优先在 HKH 上消融后再定门控形式（见 §4.3.6、Q7）。

---

## 6. 开放问题与下一步

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | 金属板 BPM=16 无独立传感器 | 报告中仅作标注；不据此做 BPM 误差声明 |
| Q2 | H2 仅 36 帧，η/ρ 方差大 | 论文中弱化 90 cm 统计结论，或补采更长人体段 |
| Q3 | 单房间内 γ 热力图接近饱和 | Review 决定是否改用 Δγ=Good−Hard、或 tone 子集排序展示 |
| Q4 | 80 cm 人体只能对 85 cm 金属板 | 正文必须标注距离近似 |
| Q5 | 相位人体劣化非三距离一致 | Research 复核假说措辞：由「系统性」改为「条件性 / 距离依赖」 |
| Q6 | Fig 3c/d vs D2 表述如何统一 | 按 §4.3.4b：融合窗间不稳定性 vs 单 tone 几何规律，分句写入 draft |
| Q7 | 人体上 η·ρ 乘积是否仍合适 | 在 HKH 做 η / η·ρ / η·soft(ρ) 消融；勿仅凭本 E3 废弃乘积 |

---

## 7. 复现

```bash
python notebooks/scripts/chFusion_position_sweep_observation.py
```

| 产出 | 路径 |
|------|------|
| 段质量 η/ρ | `outputs/reports/position_sweep_segment_quality.npy` |
| 段间 Δφ | `outputs/reports/position_sweep_dphi_per_segment.npy` |
| 人vs金属板 | `outputs/reports/position_sweep_human_vs_metal_quality.npy` |
| 元信息 JSON | `outputs/reports/position_sweep_observation_meta.json` |
| 图表 | `outputs/figures/position_sweep_*.png`（约 68 张） |
| 本报告 | `docs/reports/position_sweep_observation_report.md` |

---

## 8. Plan 回填（执行 Agent 更新 plan 末尾）

- **验证状态**：已完成
- **实际脚本**：`notebooks/scripts/chFusion_position_sweep_observation.py`
- **结论一句话**：位置扫描观测图全套已产出；幅度-相位位置依赖可展示；人体相位 η 劣化仅在部分距离成立；E3 显示人体 ρ 相对金属板剧降而 η 较稳，η·ρ 乘积需在人体域重估（见报告 §4.3.4b–4.3.6）。

---

## Self Check

- Plan read: yes
- Baseline confirmed: yes（定性观测，无算法 baseline）
- Scenario JSON used: no（新 metal_verify JSONL + plan 内 seq 段表；非 cs_*.json）
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes（见 plan §12）
- Hardcoded frame index risk: yes（seq 段范围来自 plan 标注，属本观测实验数据定义，非算法过拟合）
- Baseline changed: no
- Metric definition changed: no（复用 `_energy_ratio` / `_peak_prominence`）
- Ready to commit: yes（待用户确认后提交）
