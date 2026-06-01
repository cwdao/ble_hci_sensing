# q_energy + q_peak 融合方法

> 实现位置：`src/ble_analysis/chfusion.py`  
> 实验脚本：`notebooks/scripts/chFusion_fft-q.py`  
> 设计背景：在 compact FFT+q（`docs/chfusion_fft-q.md` §1.3）之外，尝试把 **Single 选信道指标（能量比）** 与 **谱峰质量 q_peak** 组合成软权重，做多信道频谱融合。

---

## 1. 动机

| 方法 | 行为 |
|------|------|
| **Single** | 每窗硬选能量比最高的 **1** 个信道 |
| **FFT+q_peak** | 所有信道参与，权重仅看带通谱峰突出度 |
| **FFT+q_energy_peak** | 所有信道参与，权重 = √(q_energy · q_peak) |
| **FFT+q_ep_topK** | 先按 q_energy 保留 Top-K 信道，再在其上做 energy+peak 融合 |

Single 在 remote 幅值上表现最好，说明 **能量比** 是有判别力的；但硬选 1 路会丢失多信道冗余。本方案用 q_energy 把「选信道逻辑」软化为权重，并与 q_peak 几何融合。

---

## 2. 子分数定义

### 2.1 q_energy（能量比质量分）

- **信号**：高通滤波序列 `highpass_filtered`（与 Single 选信道一致，**不是**带通）
- **原始量**：

  $$\eta_c = \frac{E_{\text{breath},c}}{E_{\text{total},c}}$$

  - 分子：FFT 功率在呼吸带 `[breath_freq_low, breath_freq_high]`（默认 0.1–0.35 Hz）之和  
  - 分母：FFT 功率在总带 `[total_freq_low, total_freq_high]`（默认 0.05–0.8 Hz）之和  

- **映射到 [0, 1]**（线性裁剪）：

  $$q_{\text{energy},c} = \operatorname{clip}\left(\frac{\eta_c - \eta_{\min}}{\eta_{\mathrm{good}} - \eta_{\min}},\, 0,\, 1\right)$$

  默认：`energy_ratio_min = 0.02`，`energy_ratio_good = 0.20`。

- **代码**：`_energy_ratio()` → `_quality_from_energy_ratio()`

### 2.2 q_peak（谱峰突出度）

- **信号**：带通滤波序列 `bandpass_filtered`
- **原始量**：$\rho_c = \max(P) / \median(P)$（呼吸带内 FFT 功率）
- **映射**：对数域线性裁剪到 [0, 1]（默认 ρ ∈ [1.5, 6.0]）
- **代码**：`_channel_spectrum_and_q()` 内计算，与 compact FFT+q 相同

---

## 3. 组合权重 q_energy_peak

两子分 **几何平均**（平方根），**不使用** q_valid、q_phi：

$$q_c^{\ep} = \sqrt{q_{\text{energy},c} \cdot q_{\text{peak},c}}$$

- **代码**：`_compose_q_weight(..., mode="energy_peak", q_energy=...)`
- **方法键**：`fft_q_energy_peak_fusion`（benchmark 标签 `FFT+q_energy_peak`）

---

## 4. 多信道频谱融合

对每个滑动窗、每个变量：

1. 各信道计算归一化呼吸频谱 $\bar P_c(f)$（带通 FFT，呼吸带内归一化）
2. 各信道计算 $q_c^{\ep}$
3. Softmax 权重：$w_c = q_c^{\ep} / \sum_j q_j^{\ep}$
4. 融合谱：$S(f) = \sum_c w_c \bar P_c(f)$
5. BPM：$\hat R = 60 \cdot \arg\max_{f \in \mathcal B} S(f)$（含抛物线峰插值）

- **代码**：`_fuse_weighted_spectrum()` → `_bpm_from_fused_spectrum()`

---

## 5. Top-K 预筛选变体（FFT+q_ep_topK）

**动机**：全信道（例如 ~72 路）软融合时，低 q_energy 信道仍分走少量权重，可能引入噪声。Top-K 在融合前只保留能量质量最好的 K 路。

**流程**（每个滑窗独立）：

1. 对所有信道计算 $q_{\text{energy},c}$（及对应的 $\bar P_c$、$q_{\text{peak},c}$）
2. 按 $q_{\text{energy},c}$ **降序**取 Top-K（默认 K=20）
3. 不在 Top-K 内的信道：融合权重置 **0**
4. 在 Top-K 内信道：仍用 $q_c^{\ep} = \sqrt{q_{\text{energy},c} \cdot q_{\text{peak},c}}$ 做加权融合（步骤同 §4）

**配置**：

| 参数 | 默认 | 说明 |
|------|------|------|
| `ChFusionConfig.energy_peak_top_k` | `20` | Top-K 信道数；`None` 或 `≤0` 表示不截断（等同全信道） |

**方法键**：`fft_q_energy_peak_topk_fusion`（benchmark 标签 `FFT+q_ep_topK`）

**代码**：`_mask_top_k_by_score(q_energy_peak_weights, q_energy_scores, top_k)`

---

## 6. 配置参数汇总

| 参数 | 默认 | 用于 |
|------|------|------|
| `breath_freq_low` / `breath_freq_high` | 0.1 / 0.35 Hz | q_energy 分子带、q_peak、BPM 搜索 |
| `total_freq_low` / `total_freq_high` | 0.05 / 0.8 Hz | q_energy 分母带 |
| `energy_ratio_min` / `energy_ratio_good` | 0.02 / 0.20 | q_energy 线性映射 |
| `peak_snr_min` / `peak_snr_good` | 1.5 / 6.0 | q_peak 对数映射 |
| `energy_peak_top_k` | 20 | Top-K 变体专用 |

在脚本中调试示例：

```python
chfusion_config = ChFusionConfig(
    energy_peak_top_k=20,  # 改为 10、30 或 None 对比
    ...
)
```

---

## 7. Benchmark 中的对比方法

Part 2 默认对比（4 变量 × 5 方法）：

1. Single  
2. Uniform  
3. FFT+q_peak  
4. FFT+q_energy_peak（全信道）  
5. FFT+q_ep_topK（q_energy Top-K + energy+peak）

---

## 8. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-01 | 初版：q_energy + q_peak 几何平均；全信道软融合 |
| 2026-06-01 | 新增 Top-K 变体 `FFT+q_ep_topK`；`energy_peak_top_k` 可配置（默认 20） |

*后续若调整公式、默认阈值或 Top-K 策略，请在本表追加一行并更新对应章节。*
