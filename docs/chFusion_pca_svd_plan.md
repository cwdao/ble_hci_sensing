# chFusion PCA/SVD 多信道呼吸波形提取方案

## 1. 动机与背景

当前 chFusion 系列的多信道融合策略为：

- **Single**: 按能量比 η 或峰度 ρ 选**最优单信道**，其余信道丢弃
- **Uniform/q-weighted**: 所有信道加权融合，但权重基于单个信道的标量质量分数

这种方法的问题是：**每个信道的选择/加权是独立的**，没有利用信道之间的相关性结构。呼吸引起的胸腔位移会**同时影响所有信道**（幅值衰减 + 相位偏移），而电路噪声、多径干扰在不同信道上是非相关的。因此，呼吸信号在所有信道上表现为一个**共同的变化模式**。

**PCA/SVD 恰好能提取这种共同模式**：第一主成分（PC1）对应"所有信道中方差最大的共同方向"，理论上就是呼吸信号。

在 WiFi CSI 呼吸感知文献中，PCA 和 SVD 是标准的信号提取手段，用于从 30+ 子载波中去除静态环境噪声、分离呼吸主导成分。

## 2. 物理模型与变量选择

### 2.1 BLE CS 数据可用变量

| 变量名 | 含义 | 物理意义 |
|--------|------|----------|
| `amplitudes` | 总幅值 | 双向测量综合幅值响应 |
| `remote_amplitudes` | 远程幅值 | 远端设备单端幅值测量 |
| `local_amplitudes` | 本地幅值 | 本地设备单端幅值测量 |
| `phases` | 总相位（已 unwrap） | 双向测量差分相位（LO 漂移已抵消） |

### 2.2 为什么不使用本地/远程单端相位

单端相位包含本振 (LO) 相位漂移：

```
φ_local  = φ_prop + φ_LO_remote - φ_LO_local + φ_noise
φ_remote = φ_prop + φ_LO_local  - φ_LO_remote + φ_noise
```

只有功率相乘后的**总相位**（差分相位）能抵消 LO 漂移：

```
φ_total = φ_local + φ_remote = 2·φ_prop + φ_noise
```

因此只能用 `phases`（总相位）。不能直接用 local/remote 单端相位。

### 2.3 复矩阵构造：总幅值 + 总相位

**推荐方案**：`z = A_total · e^(j · φ_total)`

理由：
1. 总幅值和总相位都来自双向综合测量，处于同一参考系
2. 复数值完整保留了 CSI 的幅相信息，与 WiFi CSI 的复信道响应 `H(f)` 同构
3. 单独对幅值或相位做 PCA 只捕捉单一模态的呼吸信息

**不推荐**：`remote_amplitude · e^(j · φ_total)` 或 `local_amplitude · e^(j · φ_total)`

理由：remote/local 幅值是单端测量（包含各自的 LO 幅值响应），而 total phase 是差分测量（LO 已抵消）。将单端量（含 LO 漂移贡献）和差分量强行组合成复数在物理上不一致——它们不在同一个参考系中。

但 `remote_amplitudes` 和 `local_amplitudes` **单独作为实矩阵**做 PCA/SVD 是完全合理的（它们各自的多信道间仍然共享呼吸引起的相关变化）。

### 2.4 优化策略：堆叠所有有用信号

为提高 PCA/SVD 效果，可将多种信号的信道数据**横向堆叠**成更大的矩阵。

例如将 `amplitudes` 的 72 通道 + `remote_amplitudes` 的 72 通道 + `local_amplitudes` 的 72 通道 = 216 列的大矩阵。呼吸信号在所有 216 维上都有相关投影，PC1 的信噪比更高。

## 3. 架构设计

### 3.1 文件结构

```
src/ble_analysis/pca_svd.py          ← 新建：核心 PCA/SVD 提取算法（可复用模块）
notebooks/scripts/chFusion_pca_svd.py ← 新建：分段式实验脚本
docs/chFusion_pca_svd_plan.md        ← 本文档
```

### 3.2 模块职责划分

**`src/ble_analysis/pca_svd.py`（可复用模块）**

| 内容 | 说明 |
|------|------|
| `PcaSvdConfig` | dataclass 配置（方法、标准化策略、最小信道数、方差阈值等） |
| `PcaSvdMethod` | Literal 类型：`pca` / `svd_real` / `svd_complex` |
| `NormalizeMethod` | Literal 类型：`none` / `zscore` / `minmax` |
| `extract_breath_waveform_pca()` | 实矩阵 PCA，返回 PC1 时间序列 |
| `extract_breath_waveform_svd()` | 实矩阵 SVD，返回第一左奇异向量 |
| `extract_breath_waveform_complex_svd()` | 复矩阵 SVD，返回第一左奇异向量的幅值 |
| `_normalize_matrix()` | 标准化函数（zscore / minmax） |
| `align_waveform_sign()` | 跨窗口符号一致性对齐 |
| `pca_explained_variance()` | 返回各主成分的方差占比 |
| `build_multivariable_data_matrix()` | 将多种变量的多信道数据构造成 M×N 矩阵 |

**`notebooks/scripts/chFusion_pca_svd.py`（实验脚本）**

复用现有 pipeline 的分段式 py 脚本风格：

| 步骤 | 内容 |
|------|------|
| 0 | Bootstrap + 参数配置 |
| 1 | 运行多信道滤波（复用 `run_multichannel_segment_filtering`） |
| 2 | PCA/SVD 呼吸波形提取 + BPM 估计（调用 `pca_svd` 模块） |
| 3 | 与现有方法（Single/Uniform/q-weighted）的误差对比表 |
| 4 | PCA 解释方差分析（PC1 占比分布） |
| 5 | 波形对比图（best/worst window 的 PCA/FFT 并排图） |
| 6 | 跨场景一致性验证 |
| 7 | 保存结果 + 汇总图表 |

## 4. 核心算法

### 4.1 实矩阵 PCA 提取

```
输入: X ∈ R^{M×N}，M 帧，N 信道（已带通滤波）
步骤:
  1. 检查有效信道数 >= min_channels
  2. 按列 Z-score 标准化: Z_j = (X_j - μ_j) / σ_j
  3. 协方差矩阵: C = Z^T Z / (M-1)  ∈ R^{N×N}
  4. 特征分解: C = V diag(λ) V^T, λ 降序排列
  5. PC1 = Z · v_1  ∈ R^M
  6. 检查 λ_1 / Σλ >= min_variance_ratio（否则警告）
  7. 符号一致性（与前一窗口的 PC1 做相关，若负则翻转）
输出: PC1 时间序列 (M,)
```

### 4.2 实矩阵 SVD 提取

```
输入: X ∈ R^{M×N}
步骤:
  1. 按列 Z-score 标准化
  2. 紧凑 SVD: Z = U diag(s) V^T
  3. u_1 = U[:, 0] ∈ R^M（第一左奇异向量）
  4. 检查 s_1² / Σs_i² >= min_variance_ratio
  5. 符号一致性
输出: u_1 时间序列 (M,)
```

注：PCA 和 SVD 在数学上等价。PCA 走特征分解（N×N 协方差矩阵），SVD 直接对 M×N 数据矩阵分解。当 N << M 时（72 信道 << 数百帧），PCA 的特征分解更高效。

### 4.3 复矩阵 SVD 提取

```
输入: Z ∈ C^{M×N}, Z_{i,j} = A_{i,j} · e^{j·φ_{i,j}}
步骤:
  1. 每列中心化: Z̃ = Z - mean(Z, axis=0)
  2. 构造实矩阵: R = [Re(Z̃), -Im(Z̃); Im(Z̃), Re(Z̃)]
     或使用 np.linalg.svd 直接分解复矩阵
  3. SVD: Z̃ = U diag(s) V^H
  4. u_1 = U[:, 0] ∈ C^M
  5. waveform = |u_1| 或 Re(u_1)（取幅值更稳定）
  6. 符号一致性（对实值波形）
输出: 呼吸波形 (M,)
```

Python ≥ 3.9 的 `numpy.linalg.svd` 已原生支持复数矩阵，无需手动展开为实矩阵。

### 4.4 符号一致性算法

```
对齐窗口 t 的符号:
  if t == 0: cur 不变（或与参考信道做相关决定初始符号）
  else:
    corr = dot(prev_waveform, cur_waveform)
    if corr < 0: cur_waveform *= -1

参考信道选择: 取中间信道（如 ch=37）的带通波形作为初始符号参考
```

### 4.5 滑窗 BPM 估计整合

复用 `segments.py` 中的 `_sliding_window_indices` 逻辑：

```
对每段呼吸数据:
  all_windows_bpm = []
  for each sliding window:
    1. 取出 M×N 数据矩阵（M 帧，N 个有效信道）
    2. 调用 pca_svd.extract_breath_waveform_xxx(data_matrix)
    3. 对提取的 1D 波形做 FFT
    4. 在呼吸频带 [breath_freq_low, breath_freq_high] 找峰值频率
    5. BPM = freq × 60
    all_windows_bpm.append(bpm)
  return all_windows_bpm
```

## 5. 实验策略

### 5.1 受试方法

共比较以下方法（在 leaderboard 中排列）：

| 编号 | 方法 | 输入矩阵 |
|------|------|----------|
| 1 | PCA Remote Amp | `remote_amplitudes` 72 道实 PCA |
| 2 | PCA Local Amp | `local_amplitudes` 72 道实 PCA |
| 3 | PCA Total Amp | `amplitudes` 72 道实 PCA |
| 4 | SVD Remote Amp | `remote_amplitudes` 72 道实 SVD |
| 5 | SVD Local Amp | `local_amplitudes` 72 道实 SVD |
| 6 | SVD Total Amp | `amplitudes` 72 道实 SVD |
| 7 | PCA Phase | `phases` 72 道实 PCA |
| 8 | SVD Phase | `phases` 72 道实 SVD |
| 9 | SVD Complex | `amplitudes`·e^(j·`phases`) 72 道复 SVD |
| 10 | PCA Stacked | 三种幅值堆叠 (remote+local+total) 216 道实 PCA |
| 11 | Single (baseline) | 现有能量比最优单信道 (remote amp) |
| 12 | Uniform (baseline) | 现有等权融合 (remote amp) |
| 13 | q_energy_peak (baseline) | 现有质量加权融合 (remote amp) |

注：baseline 统一使用 `remote_amplitudes`（当前实验中最优的单变量），benchmark 脚本中额外包含全部 4 种变量的 baseline。

### 5.2 关键诊断指标

- **PC1 方差占比**: λ₁ / Σλ — 衡量呼吸信号的主导程度。理想值 > 0.5
- **跨窗口 PC1 相关性**: 相邻窗口 PC1 的相关系数 — 衡量提取的一致性
- **跨场景稳定性**: 不同金属板录制下的 mean_rel_err_pct 标准差

### 5.3 预期效果

- PCA/SVD 应优于 Single（因为它利用了所有信道的信息）
- PCA/SVD 应至少与 Uniform 持平或更好（PC1 是数据驱动的最优组合）
- 复 SVD 可能优于单独的幅值或相位 PCA（同时利用幅相信息）
- Stacked PCA 可能最优（融合了多种信号的互补信息）

## 6. 文件生成计划

### `src/ble_analysis/pca_svd.py`

~200 行，包含：
- `PcaSvdConfig` dataclass
- `__all__` 导出列表
- `extract_breath_waveform_pca()`, `extract_breath_waveform_svd()`, `extract_breath_waveform_complex_svd()`
- `align_waveform_sign()`, `_normalize_matrix()`
- `pca_explained_variance()`, `build_multivariable_data_matrix()`
- 完整的 numpy-style docstring

### `notebooks/scripts/chFusion_pca_svd.py`

~300 行，分段式结构（`# %% [markdown]` + `# %%`），包含：
- 模块 docstring
- Step 0: 环境引导
- Step 0b: 参数配置（含 PcaSvdConfig）
- Step 1: 多信道滤波
- Step 2: PCA/SVD BPM 提取 + 滑窗循环
- Step 3: 误差对比表
- Step 4: 解释方差分析
- Step 5: 波形对比图
- Step 6: 跨场景验证
- Step 7: 保存结果

## 7. 风险与注意事项

| 风险 | 状态 | 缓解措施 |
|------|------|----------|
| 信道数少导致 PCA 不稳定 | ✅ 已排除 — BLE CS 有 72 信道 | — |
| PC1 不对应呼吸 | ⚠️ 待验证 | 检查 PC1 频谱是否在呼吸频带有峰值；若方差比 < 30% 则警告 |
| 符号翻转 | ⚠️ 待处理 | 跨窗口符号对齐 + 初始符号由中位信道确定 |
| 复 SVD 实现复杂度 | ✅ 清晰 | numpy.svd 原生支持复数 |
| 标准化策略影响结果 | ⚠️ 需实验 | 三种策略均实现，实验后选择最优 |
| 与现有 pipeline 的集成 | ✅ 清晰 | 复用 `run_multichannel_segment_filtering` 的输出 |
