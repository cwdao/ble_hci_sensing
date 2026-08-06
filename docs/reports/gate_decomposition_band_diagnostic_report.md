# 门控拆解 + 波形 ρ 保留 + 呼吸频带诊断 — 验证报告

> **Plan**：[`docs/plans/gate_decomposition_band_diagnostic_plan.md`](../plans/gate_decomposition_band_diagnostic_plan.md)  
> **脚本**：`notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py`  
> **场景**：HKH 12（`config/scenarios/room_*.json`）+ CS 3（`cs_091339` / `cs_095806` / `cs_102621`）  
> **日期**：2026-08-06  
> **状态**：部分完成（频带有效 → 按用户要求停在全量 benchmark 前，待确认）

---

## 1. 目标与假设

拆解 Phase 门控的 η / BPM 条件；量化 η 选模态混淆代价；粗扫呼吸频带上界。本轮目标是判断参数是否有优化空间，而非部署新方法。

| ID | 假设 | Plan 引用 |
|----|------|-----------|
| H1 | Gate-A（η_p > k·min）放宽后优于 G3，且 HKH 不劣于 G0 | §3.1 / §6.3 |
| H2 | Gate-B（仅 BPM 共识，δ∈0.5–3）可替代 η 条件 | §3.2 |
| H3 | η 选错主要是 Remote↔Local 低成本互换 | §3.4 |
| H4 | 放宽 bandpass/η highcut 可提升 η 分辨力与 BreatheCS BPM | §3.5 |

**用户确认的执行偏差**（相对原 plan）：

| 项 | 决定 |
|----|------|
| Part 4 | 方案 A：滤波 highcut 与 η breath band 同步扩展；BPM 寻峰仍 0.1–0.35 Hz |
| Gate-B | HKH + CS |
| δ | `{0.5, 1.0, 1.5, 2.0, 3.0}`（零填充 ~4× + 抛物线，bin≈0.4–0.6 BPM） |
| Gate-A k | `{1.00, 1.05, 1.10}` |
| 频带有效后 | **先停，不自动全量 benchmark** |

---

## 2. 方法摘要

| 项目 | 内容 |
|------|------|
| 观测量 | `remote_amplitudes` / `local_amplitudes` / `phases` |
| 信道融合 | Voting η-only（`tone_weight_mode="eta"`） |
| 模态融合 | 等权谱融合；门控在 R+L vs R+L+P 间切换 |
| 滑窗与寻峰 | 20 s / 1 s；BPM 搜索 0.1–0.35 Hz；`nfft≈4×win` 零填充 + 抛物线插值 |
| Part 2 波形 | 不新跑；引用 `eta_only_ablation`（η·ρ RMSE 0.951 vs η-only 0.994） |

---

## 3. 实验设置

| 域 | 场景 | 指标 |
|----|------|------|
| HKH | 12 recordings | BPM abs err（mean±std） |
| CS | 3 metal-plate | BPM rel err %（mean±std） |

- **Baseline**：G0 R+L、G3（η-strict + BPM±1.5）、G4 三模态常开（均为 η-only）
- **待测**：Gate-A ×3、Gate-B ×5；η 混淆矩阵；频带 highcut ∈ {0.35, 0.40, 0.50, 0.60}

---

## 4. 结果

### 4.1 Part 1 — 门控拆解（HKH 主表）

| 方法 | mean±std | Phase open % | open 窗 Phase err |
|------|---------:|-------------:|------------------:|
| **G0 R+L only** | **0.371±0.128** | 0.0 | — |
| G3 η-strict+BPM±1.5 | 0.371±0.128 | 1.3 | 1.26 |
| Gate-B δ&lt;0.5 | 0.372±0.129 | 29.8 | 0.40 |
| Gate-B δ&lt;1.0 | 0.376±0.130 | 48.8 | 0.58 |
| Gate-A k=1.10 | 0.380±0.137 | 5.3 | 6.50 |
| Gate-A k=1.05 | 0.380±0.137 | 5.9 | 6.39 |
| Gate-B δ&lt;1.5 | 0.380±0.131 | 57.8 | 0.71 |
| Gate-A k=1.00 | 0.382±0.140 | 7.2 | 5.11 |
| Gate-B δ&lt;2.0 | 0.383±0.133 | 64.2 | 0.83 |
| Gate-B δ&lt;3.0 | 0.393±0.139 | 72.9 | 1.05 |
| G4 3-modal always | 0.403±0.152 | 100.0 | 2.25 |

来源：`outputs/reports/gate_decomposition_hkh.json`  
图：`outputs/figures/gate_decomposition_figF1_hkh_bpm.png`、`figF2_open_ratio.png`、`figF3_gate_quality.png`

要点：

- **k 扫描几乎无增益**：Gate-A 三档均劣于 G0；open 仅 5–7%，且 open 窗 Phase err 极差（~5–6.5）。
- **δ 扫描呈单调**：δ 越小越接近 G0；放宽 δ 只增加 open、同时抬高误差。δ=0.5 时 open~30% 但 mean≈G0——说明多数共识窗 Phase 无害也无益。
- G3 仍 ≈ G0（open 1.3% no-op）。

### 4.2 Part 1 — CS 对照

| 方法 | mean±std (%) | Phase open % |
|------|-------------:|-------------:|
| **G4 3-modal always** | **10.72±3.29** | 100.0 |
| Gate-A k=1.00 | 11.45±3.51 | 33.5 |
| Gate-A k=1.05 | 11.54±3.68 | 28.9 |
| Gate-A k=1.10 | 12.29±4.73 | 23.7 |
| Gate-B（各 δ） | 14.23–14.49 | 49.5–79.0 |
| G3 | 14.61±7.94 | 3.7 |
| G0 R+L | 14.64±7.97 | 0.0 |

要点：

- CS 上 **G4 仍最优**；Gate-A 介于 G4 与 G0，k 越大越差。
- **Gate-B 在 CS 上几乎退化为 G0**：即使 open 到 50–79%，BPM 也停在 ~14.3–14.5%，吃不到 Phase 红利。说明「三模态 BPM 一致」的窗 ≠ Phase 真正有用的窗。

### 4.3 Part 2 — 波形 ρ（引用，不新跑）

| 方法 | RMSE η·ρ | RMSE η-only | Δ |
|------|---------:|------------:|--:|
| Wave BreatheCS | **0.951** | 0.994 | +0.043 |

来源：`eta_only_ablation_report` §4.2。波形分支仍建议保留 η·ρ。

### 4.4 Part 3 — η 混淆矩阵（HKH，1730 窗）

| | η→Remote | η→Local | η→Phase |
|--|----------:|--------:|--------:|
| oracle=Remote | 1082 (Δ0) | 384 (Δ0.04) | 83 (**Δ5.72**) |
| oracle=Local | 53 (Δ0.56) | 15 (Δ0) | 8 (Δ2.96) |
| oracle=Phase | 80 (Δ0.46) | 21 (Δ0.60) | 4 (Δ0) |

- top-1 hit：**63.6%**
- Remote↔Local 互换：**437**（低成本）
- 高成本误选 Phase：**91 = 5.26%** → 按 plan 阈值判为 **`eta_systematic_defect`**（>5%）
- Phase 为 oracle 时几乎选不中（4/105）

来源：`outputs/reports/eta_confusion_matrix.json`  
图：`outputs/figures/gate_decomposition_figF4_eta_confusion.png`

### 4.5 Part 4 — 呼吸频带扫描（**有效，已暂停全量**）

| highcut | HKH BreatheCS abs err | Δ vs 0.35 | HKH η hit | CS rel err % | CS Δ |
|--------:|----------------------:|----------:|----------:|-------------:|-----:|
| **0.35** | 0.403 | 0 | 0.396 | **10.72** | 0 |
| **0.40** | **0.379** | **−0.024** | 0.440 | 12.56 | +1.84 |
| **0.50** | 0.381 | **−0.022** | 0.434 | 13.62 | +2.90 |
| 0.60 | 0.383 | −0.020 | 0.423 | 13.95 | +3.23 |

来源：`outputs/reports/breathing_band_sweep.json`  
图：`outputs/figures/gate_decomposition_figF5_band_sweep.png`

判定：

- HKH：0.40 / 0.50 满足 |Δ|>0.02 → `effective_pending_user_review`
- CS：**同步退化**（+1.8–3.2 pp）
- **未跑全量 benchmark**（按用户要求）

### 4.7 Follow-up — HKH 波形 RMSE 频带扫描（用户追加）

设置与谱域 Part 4 相同（方案 A：滤波 + η highcut 同步；Wave/GT BPM 搜索仍 0.1–0.35）。方法：B2-D 两级 Hilbert-MRC（Wave BreatheCS），主看 η·ρ，η-only 对照。

| highcut | η·ρ RMSE | Δ vs 0.35 | η·ρ Wave BPM | η-only RMSE | Δ | η-only Wave BPM |
|--------:|---------:|----------:|-------------:|------------:|--:|----------------:|
| **0.35** | **0.950** | 0 | 0.682 | 0.997 | 0 | 0.756 |
| 0.40 | 0.979 | **+0.029** | **0.400** | 0.982 | −0.015 | 0.407 |
| 0.50 | 0.990 | +0.041 | 0.414 | 0.995 | −0.002 | 0.407 |
| 0.60 | 0.984 | +0.034 | 0.404 | 0.987 | −0.010 | 0.400 |

来源：`outputs/reports/breathing_band_wave_rmse_sweep.json`  
图：`outputs/figures/gate_decomposition_figF6_wave_band_rmse.png`

判定：`neutral_or_worse_rmse`

要点：

- **波形重建 RMSE：频带扩展对 η·ρ 主路径不利**（0.40 起 Δ≈+0.03）；η-only 略降但未过 0.02 阈值。
- **Wave BPM abs err 却明显下降**（η·ρ：0.682→0.400），与谱域 BreatheCS 改善方向一致——说明扩频带更像改善了「频率估计/选 tone」，而不是波形形状对齐。
- 因此：**不能把谱域 BPM 的频带收益直接推广到波形 RMSE**。

### 4.8 Follow-up — 受控交叉：分支 × 质量指标 × highcut（HKH）

用户观察：highcut=0.40 时 Wave BPM 已接近谱 BPM。本节省去「分次实验」的混杂，在**同一批窗 / 同一 GT / 同一 Option A 滤波**下交叉：

| 因子 | 水平 | 固定不变 |
|------|------|----------|
| highcut | 0.35 / 0.40 / 0.50 / 0.60 | 滤波 highcut 与 η breath band **同步** |
| 分支 | Spectral 三模态 equal / Spectral R+L / Wave B2-D | BPM 搜索 **始终 0.1–0.35 Hz** |
| 质量 | η·ρ vs η-only | 窗长 20 s / 步长 1 s；滑窗集合相同 |

来源：`outputs/reports/quality_band_controlled_hkh.json`  
图：`outputs/figures/gate_decomposition_figF7_quality_band_controlled.png`

#### 4.8.1 主表 — BPM abs err（跨 12 场景 mean）

| highcut | Spec 3-modal η·ρ | Spec 3-modal η | Spec R+L η·ρ | Spec R+L η | Wave η·ρ | Wave η |
|--------:|-----------------:|---------------:|-------------:|-----------:|---------:|-------:|
| **0.35** | 0.405 | **0.403** | **0.372** | **0.371** | 0.682 | 0.756 |
| **0.40** | **0.377** | 0.379 | **0.352** | 0.360 | **0.400** | 0.407 |
| **0.50** | **0.377** | 0.381 | **0.353** | 0.363 | 0.414 | **0.407** |
| **0.60** | **0.377** | 0.383 | **0.355** | 0.364 | 0.404 | **0.400** |

相对 0.35 的 Δ（BPM）：

| highcut | Spec3 η·ρ | Spec3 η | R+L η·ρ | R+L η | Wave η·ρ | Wave η |
|--------:|----------:|--------:|--------:|------:|---------:|-------:|
| 0.40 | **−0.028** | −0.024 | −0.020 | −0.011 | **−0.282** | **−0.349** |
| 0.50 | −0.028 | −0.022 | −0.019 | −0.008 | −0.268 | −0.349 |
| 0.60 | −0.028 | −0.020 | −0.017 | −0.007 | −0.278 | −0.356 |

#### 4.8.2 Wave−Spectral 间隙（同质量指标下）

| highcut | gap = Wave−Spec3（η·ρ） | gap（η-only） |
|--------:|------------------------:|--------------:|
| 0.35 | **+0.277** | **+0.353** |
| 0.40 | **+0.023** | **+0.028** |
| 0.50 | +0.038 | +0.026 |
| 0.60 | +0.027 | +0.017 |

#### 4.8.3 波形 RMSE（同一次受控跑）

| highcut | Wave η·ρ RMSE | Δ | Wave η RMSE | Δ |
|--------:|--------------:|--:|------------:|--:|
| 0.35 | **0.950** | 0 | 0.997 | 0 |
| 0.40 | 0.979 | +0.029 | 0.982 | −0.015 |
| 0.50 | 0.990 | +0.041 | 0.995 | −0.002 |
| 0.60 | 0.984 | +0.034 | 0.987 | −0.010 |

#### 4.8.4 变量控制下的解读

1. **η vs η·ρ（扩频带后）几乎不再是主差异**  
   - Spec 3-modal：0.40 起两者差 ≤0.006（η·ρ 略优或持平）。  
   - Wave BPM：0.40 起两者差 ≤0.014，可视为同级。  
   - 基线 0.35 上 Wave 仍是 η·ρ（0.682）明显优于 η-only（0.756）；**扩到 ≥0.40 后该差距塌缩**。

2. **「Wave≈Spectral」故事在 η 与 η·ρ 下都成立**  
   - 0.35：Wave 落后 Spec3 约 0.28–0.35。  
   - ≥0.40：差距收至约 **0.02–0.04**（无论 η 还是 η·ρ）。  
   - 即：接近谱分支的主因是 **频带/滤波扩展**，不是换成 η-only。

3. **η-only 没有额外挖出「新台阶」**  
   - 在 0.40/0.50/0.60，换 η-only 不会显著再压 Wave 或 Spec3；R+L 上 η·ρ 仍略优于 η（0.352 vs 0.360 @0.40）。  
   - Wave RMSE：η-only 相对 0.35 略降，但绝对值仍 ≈0.98，且不如 0.35 的 η·ρ（0.950）。

4. **R+L 对照**  
   - 扩频带后 R+L 也改善（η·ρ @0.40 → 0.352），仍是 HKH BPM 最优档；Wave 逼近的是 **Spec3**，尚未追上 R+L。

### 4.6 与 plan 预期对比

| 预期 | 实际 | 是否一致 |
|------|------|----------|
| Gate-A ≥ G0（HKH） | Gate-A 全劣于 G0 | ❌ |
| Gate-A 在 CS 优于 G0 | 是（但仍劣于 G4） | 部分 |
| Gate-B δ=1.5 ≈ G0 | 略差；δ=0.5 才≈G0 | 部分 |
| η 误选多为 R↔L | 是（437），但高成本 Phase 误选 5.3% | 部分 |
| 频带扩展提升 η / BPM | HKH 有效；CS 变差 | 跨域冲突 |
| 扩频带后 η-only 相对 η·ρ 另有突破 | **无**；两者 BPM 间隙塌缩，方向由 highcut 主导 | ❌（相对「再挖一刀」的期望） |

---

## 5. 结论

### 已验证

- HKH 上 **G0 R+L 仍是门控族最优**；放宽 η（Gate-A）或仅靠 BPM 共识（Gate-B）都无法稳定超过 G0。
- Gate-A 的 **k 扫描无实质优化空间**（open 与 BPM 几乎不动）。
- Gate-B：**δ 越小越好（越接近关 Phase）**；放宽只会抬错。CS 上 Gate-B 无法复现 G4 的 Phase 收益。
- η 作为单模态选择器：低成本 R↔L 互换为主，但 **高成本误选 Phase 占 5.3%**，且几乎选不中真正的 Phase-oracle 窗。
- **受控交叉（§4.8）**：highcut≥0.40 时 Wave BPM ≈ Spec3 BPM（gap≈0.02–0.04）；**η vs η·ρ 在扩频带后几乎等价**；Wave≈Spectral 由频带驱动，非质量指标切换驱动。
- 基线 0.35 上波形路径 η·ρ 仍优于 η-only（BPM 与 RMSE）；扩频带后 RMSE 仍不支持用 η-only 替换为默认。

### 仅单场景 / 跨域冲突（待你确认）

- **频带 0.40–0.50 Hz 在 HKH 谱域 BreatheCS 改善 ~0.022–0.028**，但 **CS 同步变差 +1.8–3.2 pp**。
- **同一扩频带到波形分支：η·ρ RMSE 变差（+0.03）**；Wave BPM 变好并贴近 Spec3，但 RMSE 无优势 → 波形**形状**路径不支持默认放宽。
- 扩频带后改用 η-only：**无额外 BPM 收益**（相对 η·ρ）。

### 未证实

- 存在「跨域都更好」的门控参数（η 阈值或 δ）。
- 频带扩展作为**全局默认**（谱+波、HKH+CS）的有效性。
- 在 highcut≥0.40 下用 η-only 作为统一质量指标优于 η·ρ。

### 已废弃（本轮证据倾向）

- 继续细调 Gate-A k 或单独 Gate-B δ 作为主路线（HKH 无增益、CS Gate-B 无效）。
- 把 η top-1 单模态选择当作可靠 Phase 纳入器（命中 Phase-oracle≈4/105）。
- 「扩频带后再切 η-only 能再挖一截」——受控实验不支持。

---

## 6. 产出路径

| 类型 | 路径 |
|------|------|
| 脚本 | `notebooks/scripts/chFusion_gate_decomposition_band_diagnostic.py` |
| HKH 门控 | `outputs/reports/gate_decomposition_hkh.json` |
| CS 门控 | `outputs/reports/gate_decomposition_cs.json` |
| 混淆矩阵 | `outputs/reports/eta_confusion_matrix.json` |
| 频带扫描 | `outputs/reports/breathing_band_sweep.json` |
| 波形频带 RMSE | `outputs/reports/breathing_band_wave_rmse_sweep.json` |
| 受控 quality×band | `outputs/reports/quality_band_controlled_hkh.json` |
| 图 F1–F7 | `outputs/figures/gate_decomposition_figF*.png` |

---

## 7. 保留问题（请确认）

1. **频带**：HKH 有效、CS 变差 —— 是否（a）放弃频带扩展、（b）仅 HKH 用 0.40、（c）仍对 0.40 跑一次受控全量对照？
2. **门控路线**：是否正式结题（HKH 默认 R+L，CS 默认三模态 / 不靠窗级门控）？
3. 是否需要把「域相关默认模态集」写成显式 rule（plan Q3），而不是继续找统一 gate？

---

## Self Check

- Plan read: yes
- Baseline confirmed: yes（G0/G3/G4）
- Scenario JSON used: yes
- Script executed: yes
- Results generated: yes
- Figures generated: yes
- Report generated: yes
- Plan updated: yes（见 plan §10）
- Hardcoded frame index risk: no
- Baseline changed: no
- Metric definition changed: no
- Ready to commit: yes（待用户确认是否提交）

---

## 8. 论文预备汇总：Oracle 上限 · BreatheCS 实绩 · 可简化管线

> 本节汇总本轮及前序相关实验中、可直接进入论文 Results / Method 的数字与管线定义。  
> 默认呼吸带 **0.1–0.35 Hz**（除非单独标注频带诊断）。未经验证的扩频带（0.40+）**不**写入默认管线。

### 8.1 本轮及相关实验——数据速查

| 主题 | 关键结论 | 主数字 | 来源 |
|------|----------|--------|------|
| η-only 消融（谱） | HKH 上谱 BPM 用 η ≈ η·ρ | Spec3：0.405→0.403 | `eta_only_ablation` |
| η-only 消融（波） | 波形 RMSE 需要保留 ρ | 0.951→0.994（+0.043） | 同上 |
| Phase 门控 | 统一窗级门控跨域失败 | HKH G3≡G0（open 1.3%）；CS G3≈G0，远差于 G4 | 本报告 §4.1–4.2 |
| Gate-A/B 参数扫 | k、δ 无跨域可用最优点 | HKH 最优仍 G0=0.371；CS 最优仍 G4=10.72% | 本报告 §4.1–4.2 |
| η 混淆矩阵 | 命中率中等，高成本误选 Phase | hit 63.6%；high→Phase 5.3% | 本报告 §4.4 |
| 频带扩展 | HKH 谱/波 BPM 受益，CS 与 RMSE 受损 | HKH Spec3 @0.40：0.379；CS +1.8 pp；RMSE +0.03 | §4.5–4.8 |
| 受控 quality×band | Wave≈Spec3 由频带驱动，非 η vs η·ρ | @0.40 gap≈0.02–0.03 | §4.8 |

### 8.2 理论最优（Oracle）vs 当前 BreatheCS 实绩

#### 8.2.1 HKH 12 场景（指标：BPM 绝对误差，breaths/min）

| 层级 | 方法 / 定义 | 数值 | 相对 Oracle | 备注 |
|------|-------------|-----:|------------:|------|
| **理论①** | 单模态 Oracle（每窗 argmin \|BPM_m−GT\|，m∈{R,L,P}） | **0.408** | — | `modal_oracle_summary.json`；Remote 最优窗 89.5% |
| 参考 | Remote / Local / Phase 全窗固定 | 0.465 / 0.462 / 2.088 | +0.057 / +0.054 / +1.68 | 同上 |
| **理论②** | R+L+P 可融合 Oracle（相对 R+L 的窗级增益） | ≈**0.344**（估） | −0.064 vs ① | R+L(0.372) − Δ0.028；`phase_p0_oracle_delta.json` |
| **实绩·域最优 BPM** | Amplitude-only R+L equal（η-only Voting） | **0.371** | −0.037 vs ① | 已优于单模态 Oracle——融合增益 |
| **实绩·BreatheCS 谱（论文主方法形态）** | Vote→三模态 equal（η-only） | **0.403** | −0.005 vs ① | ≡ 旧 η·ρ 的 0.405；含 Phase 在 HKH 略伤 |
| **实绩·波形** | B2-D / BreatheCS-Wave（η·ρ） | RMSE **0.951**；Wave BPM≈0.68 | — | η-only RMSE 0.994（更差） |

**HKH 读法（写论文可用）**：

- 单模态天花板约 **0.41**；实际 **R+L≈0.37** 已打穿该天花板（双幅值融合有效）。
- 再纳入 Phase 的理论增量约 **0.03**（oracle Δ），但**现有门控与 η 选择都吃不到**；硬开三模态反而回到 ~0.40。
- 因此 HKH 上「BreatheCS 谱主结果」若强调最优 BPM，应报 **R+L**；若强调与 CS 统一的三模态方法，报 **0.403**，并说明相对 R+L 的代价。

#### 8.2.2 CS 金属板三场景（指标：BPM 相对误差 %）

| 层级 | 方法 / 定义 | 数值 | 备注 |
|------|-------------|-----:|------|
| **理论①** | 单模态 Oracle（abs err） | **0.651** BPM | `modal_oracle_summary.json`；≈4–7% rel（视 GT BPM） |
| 参考 | Remote / Local / Phase 全窗（abs） | 1.062 / 1.730 / 1.259 | Phase 最优窗占 **14.4%**（远高于 HKH 的 6.1%） |
| **实绩·BreatheCS 谱（三模态）** | Vote→equal，η·ρ / η-only | **10.14%** / **10.72%** | `eta_only_ablation`；η-only 轻度退化 |
| **实绩·R+L** | 双幅值 equal | 14.05% / 14.64% | 明显差于三模态 |
| **实绩·门控** | G3 等 | ≈14.6%（≈G0） | 关死 Phase → 失去 CS 红利 |

**CS 读法**：

- Phase **必须参与**（与 HKH 相反）；统一「关 Phase 门控」不可行。
- BreatheCS 三模态是 CS 实绩最优档之一（本系列验证内）；η·ρ 略优于 η-only（~0.6 pp）。

#### 8.2.3 跨域对照一览（默认 0.1–0.35 Hz）

| | HKH 最优实绩 | HKH BreatheCS 三模态 | CS BreatheCS 三模态 | CS R+L |
|--|-------------:|---------------------:|--------------------:|-------:|
| 指标 | BPM abs | BPM abs | BPM rel % | BPM rel % |
| **数值** | **0.371**（R+L） | 0.403 | **10.14%**（η·ρ）/ 10.72%（η） | 14.0–14.6% |
| vs Oracle | 优于单模态 Oracle | ≈单模态 Oracle | 远优于 R+L | 差 |

> **论文叙事张力**：同一套「三模态 BreatheCS」在 CS 必要、在 HKH 次优；窗级自适应门控本轮**未打通**。写作上可并列：（i）统一方法三模态数字；（ii）域最优（HKH=R+L，CS=三模态）作为上限参照。

### 8.3 推荐写入论文的 BreatheCS 简化管线（已删可证伪步骤）

目标：只保留实验支持的计算；**去掉已证明无增益的步骤**。

#### 8.3.1 删除 / 不采用的步骤（已有负证或空操作）

| 原候选步骤 | 处理 | 证据 |
|------------|------|------|
| 谱分支 tone 权重用 η·ρ | **改为仅 η** | HKH Spec Δ≈0；CS 仅 ~0.6 pp，可作消融而非默认 |
| Phase η-BPM 窗级门控（G1–G3 / Gate-A/B） | **删除** | HKH no-op 或变差；CS 关 Phase 致命 |
| 以 η top-1 做单模态选择器纳入 Phase | **删除** | hit 63.6%，high→Phase 5.3%；Phase-oracle 几乎选不中 |
| 波形路径去掉 ρ（全局 η-only） | **不采用** | RMSE +0.043 |
| 默认把 bandpass/η 扩到 0.40–0.60 | **不写入默认** | HKH 谱/波 BPM 好，但 CS 与 RMSE 差；待定 |
| B2 coherence gate 等（B3 精简已做） | **保持删除** | B3 Simplified 既有结论 |

#### 8.3.2 简化后的默认管线（论文 Method 草案）

```text
Raw BLE CS (72 tone × {remote_amp, local_amp, phases})
  │
  ├─ Filter (per tone): median(w=3) → HP 0.05 Hz → BP 0.1–0.35 Hz
  ├─ Sliding window: 20 s / 1 s
  │
  ├─ Per-tone FFT (nfft ≈ 4×win 零填充) + 抛物线插值寻峰
  │     BPM 搜索带固定 0.1–0.35 Hz
  │
  ├─══ 谱 BPM 分支（BreatheCS-Spectral）══════════════════
  │     tone 质量 = η          ← 只用能量比（不算 ρ）
  │     逐模态 η-weighted Voting → 融合谱
  │     模态融合 = equal
  │       · 论文主方法（跨域统一形态）：{R, L, P}
  │       · HKH 域最优参照：{R, L} only
  │       · CS 域最优：{R, L, P}（与主方法一致）
  │     输出：BPM
  │
  └─══ 波形分支（BreatheCS-Wave / B2-D）════════════════
        tone 质量 = η·ρ        ← 仅此分支需要峰度 ρ
        两级 Hilbert-MRC（tone → modal），无 coherence gate
        模态：与谱分支部署策略对齐（见上）
        输出：波形 + RMSE；可选 Wave-BPM
```

#### 8.3.3 参数表（可直接进论文）

| 模块 | 参数 | 值 | 说明 |
|------|------|-----|------|
| 中值滤波 | window | 3 | 不变 |
| 高通 | cutoff | 0.05 Hz | 不变 |
| 带通 | band | **0.1–0.35 Hz** | 默认；0.40 仅为诊断 |
| η 定义带 | breath / total | 0.1–0.35 / 0.05–0.8 Hz | 与带通对齐 |
| 滑窗 | length / step | 20 s / 1 s | 不变 |
| FFT | nfft | `next_pow2(4·win)` | 零填充 + 抛物线 |
| 谱 tone 权重 | quality | **η** | 已简化 |
| 波 tone 权重 | quality | **η·ρ** | **仅波形分支算 ρ** |
| 谱模态融合 | weights | equal | 无学习权重 |
| 波模态融合 | | 两级 Hilbert-MRC | 无 coherence gate |
| Phase 门控 | | **待定（见 §8.5）** | 叙事上需要；候选 Gate-A / Gate-B |
| 实现锚点 | | `b3_pipeline.py` + `coherent_mrc.py` | tone_weight_mode 谱=`eta`，波=`eta_rho` |

#### 8.3.4 论文中建议报告的「主结果」三元组

| 角色 | HKH | CS | 管线 |
|------|-----|-----|------|
| **主方法（统一 BreatheCS）** | Spec3 η-only **0.403**；Wave RMSE **0.951**（η·ρ） | Spec3 **10.14%**（η·ρ）或并列 10.72%（η-only 消融） | 三模态 equal（或 +门控，见 §8.5） |
| **域最优上限（实绩）** | R+L **0.371** | 同主方法三模态 | 说明 HKH 关 Phase 更优 |
| **理论参照** | 单模态 Oracle 0.408；R+L+P Oracle≈0.344 | 单模态 Oracle abs 0.651 | 讨论剩余 gap |

### 8.4 仍开放的 Method 选择点

1. **是否把窗级 Phase 门控写入最终管线**：叙事需要（§8.5）；性能上无「双赢」，需在 Gate-A / Gate-B / 常开三模态间取舍。  
2. **频带 0.40 Hz**：HKH 上 Spec/Wave BPM 有趣（Wave≈Spec），CS 与 RMSE 反对；需单独实验章节或附录，不进默认。  
3. **CS 上 η·ρ vs η-only**：主方法若强调跨域简单性，谱分支可统一 η；CS 上保留 η·ρ 作为「完整版」消融对照。

### 8.5 门控是否放进最终管线——性能对照（供拍板）

#### 8.5.1 叙事判断（同意你的主线）

你的推理**成立**，且比「HKH 方法里直接删 Phase」更适合论文推导链：

1. **CS（金属板）**：Remote / Local / Phase 都可用 → 方法上应保留「条件性纳入 Phase」的接口，而不是一开始就删掉。  
2. **门控**：用 η 比较或 BPM 共识，在窗级决定 Phase 是否进融合——这是从 CS 可用性推导到部署规则的桥梁。  
3. **HKH（人体）**：门控几乎不打开 / 打开也无益 → **实验结论**是「人体场景下 Phase 质量不够，很少通过门控」，因此 BreatheCS 人体性能 ≈ 幅值（R+L），而不是 Method 里先验删 Phase。

需要诚实写的一点：门控是**叙事与接口上的必要组件**；本轮数据里它**不是**跨域精度最优器（CS 上仍差于「三模态常开」）。

#### 8.5.2 性能总表（η-only Voting；谱分支）

| 方法 | 规则（Phase 何时加入） | HKH BPM abs | vs G0 | Phase open | CS BPM rel % | vs G0 | vs G4 |
|------|------------------------|------------:|------:|-----------:|-------------:|------:|------:|
| G0 R+L | 永不 | **0.371** | — | 0% | 14.64 | — | +3.92 |
| G4 三模态常开 | 永远 | 0.403 | +0.032 | 100% | **10.72** | **−3.92** | — |
| G3（旧） | η_p>η_r∧η_p>η_l 且 \|BPM_p−BPM_{R+L}\|<1.5 | 0.371 | +0.000 | 1.3% | 14.61 | −0.03 | +3.89 |
| **Gate-A k=1.00** | **η_p > min(η_r,η_l)** | **0.382** | **+0.011** | **7.2%** | **11.45** | **−3.19** | +0.73 |
| Gate-A k=1.05 | η_p > 1.05·min | 0.380 | +0.009 | 5.9% | 11.54 | −3.10 | +0.82 |
| Gate-A k=1.10 | η_p > 1.10·min | 0.380 | +0.009 | 5.3% | 12.29 | −2.35 | +1.57 |
| **Gate-B δ=0.5** | **max−min BPM < 0.5** | **0.372** | **+0.001** | **29.8%** | **14.49** | **−0.15** | +3.77 |
| Gate-B δ=1.0 | range < 1.0 | 0.376 | +0.005 | 48.8% | 14.41 | −0.23 | +3.69 |
| Gate-B δ=1.5 | range < 1.5 | 0.380 | +0.009 | 57.8% | 14.35 | −0.29 | +3.63 |
| Gate-B δ=2.0 | range < 2.0 | 0.383 | +0.012 | 64.2% | 14.23 | −0.41 | +3.51 |
| Gate-B δ=3.0 | range < 3.0 | 0.393 | +0.022 | 72.9% | 14.30 | −0.34 | +3.58 |

来源：`gate_decomposition_hkh.json` / `gate_decomposition_cs.json`（本报告 §4.1–4.2）。

#### 8.5.3 按你的「可放」标准怎么读

| 候选 | HKH 负面？ | CS 正面？ | 是否服务「CS 可用→门控→HKH 少用 Phase」叙事 | 建议 |
|------|-----------|----------|---------------------------------------------|------|
| **Gate-A k=1.00** | 轻负：0.371→**0.382**（+0.011） | **有**：14.64→**11.45**（接近 G4 的 10.72） | **强**：CS open 33.5% 真正吃到 Phase；HKH open 仅 7.2%≈少参与 | **若必须选一个门控进主方法：优先 A** |
| Gate-A k=1.05/1.10 | 同级轻负 | CS 收益变小 | 同方向，略更保守 | 消融档 |
| **Gate-B δ=0.5** | **几乎无负**：0.372≈0.371 | **几乎无正**：仍≈14.5%（≈G0） | **弱**：HKH 看似「安全」，但 CS 说不通（open 高却无收益） | 可作 HKH 中性对照，不宜单独当跨域主门控 |
| Gate-B δ≥1.5 | HKH 明显变差 | CS 仍无 Phase 红利 | 叙事与精度双弱 | 不推荐 |
| G3 | HKH 中性 | CS 无收益 | open 过低，像空操作 | 不推荐 |
| 无门控 + 域写死 R+L/3modal | HKH 最优 / CS 最优 | — | **推导链断**：人体章无法从 CS 模态可用性推过来 | 仅适合 Discussion「oracle 式域规则」 |

#### 8.5.4 拍板用的三选一（性能事实，不做最终替你决定）

1. **主方法 = Vote→Equal 三模态常开（无门控）**  
   - CS 最好（10.72% η-only）；HKH 付出 +0.032 vs R+L。  
   - 叙事弱：说不清「为何人体几乎等于幅值」。

2. **主方法 = Gate-A（η_p > min(η_r,η_l)）→ 通过则 R+L+P，否则 R+L**  ← 最贴你的叙事  
   - HKH：**轻微负**（0.382，Δ=+0.011），Phase 很少进。  
   - CS：**明显正** vs R+L（11.45%，Δ=−3.2 pp），仍略差于常开三模态（+0.73 pp）。  
   - 人体结论可写成：门控在 HKH 上很少放行 Phase ⇒ 性能≈幅值。

3. **主方法 = Gate-B（δ=0.5）**  
   - HKH 几乎无伤；**CS 讲不通**（无 Phase 红利）。  
   - 若论文要强调「从 CS 模态可用性出发」，B 单独不够。

**可选组合（若你想更稳）**：主文用 **Gate-A**；消融表保留 G0 / G4 / Gate-B δ=0.5，用来证明「共识门控 ≠ 质量门控」。

---

**一句话**：你的叙事方向对——门控是连接 CS 与 HKH 的方法组件，不是可有可无的调参。性能上 **Gate-A（k=1）是唯一同时满足「CS 有正面收益 + HKH 无大伤 + 叙事闭环」的候选**；Gate-B 对 HKH 更「无害」，但撑不起 CS。最终放不放、放 A 还是常开三模态，等你拍板后再改 §8.3 默认管线。
