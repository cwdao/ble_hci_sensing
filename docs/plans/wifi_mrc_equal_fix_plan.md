# WiFi MRC "equal" 变体修正 — 从 BPM 标量平均改为时域波形融合

> **来源**：Review 发现 `wifi_mrc.py` 中 Fan-η-equal 和 MRC-PCA-η-equal 对三模态做 BPM 标量平均，未在时域波形层面融合  
> **目标**：将 "equal" 变体改为时域波形融合（Fan: 波形等权平均; MRC+PCA: PCA(3→1)），并新增 Fan-Hilbert 对照变体  
> **日期**：2026-06-26  
> **验证状态**：待实现

---

## 1. 动机与背景

### 1.1 当前问题

`wifi_mrc.py` 中的 `_fan_window_bpms()` 和 `_mrc_pca_window_bpms()` 存在一致的缺陷：

```text
当前逻辑（有问题）:
  remote:  72-tone MRC → waveform → FFT → BPM_remote
  local:   72-tone MRC → waveform → FFT → BPM_local
  phase:   72-tone MRC → waveform → FFT → BPM_phase
  equal:   nanmean([BPM_remote, BPM_local, BPM_phase])   ← BPM 标量平均
```

每个模态独立经历了完整的 MRC → FFT → BPM 管道，最后只对 3 个 BPM 标量取平均。这丢弃了波形层面的全部信息——三模态波形之间可能存在互补性（如 remote 在某个半周期信噪比高、local 在另一个半周期好），BPM 标量平均无法利用这些互补性。

### 1.2 修正目标

| 路线 | 旧 key（保留不动） | 旧行为 | 新 key（追加） | 新行为 |
|------|-------------------|--------|----------------|--------|
| **Fan (equal)** | `fan_eta_equal` | BPM 标量平均 | `fan_eta_equal_wf` | 三 MRC 波形时域等权平均 → FFT → BPM |
| **Fan-Hilbert** | — | — | `fan_hilbert_equal` | Hilbert 对齐 tone → MRC → 三波形时域平均 → FFT → BPM |
| **MRC+PCA (equal)** | `mrc_pca_eta_equal` | BPM 标量平均 | `mrc_pca_eta_equal_pca` | 三 MRC+PCA 波形 → PCA(3→1) → FFT → BPM |

> **旧 key 历史数值全部保留**，README 排行榜中标记为 `(legacy, BPM avg)` 即可追溯。新 key 的跨域数值独立计算、独立排名。

### 1.3 为何 PCA(3→1) 而非等权平均用于 MRC+PCA

- **Fan**：MRC 本身就是时域加权平均，没有降维步骤。三级模态之间使用等权平均（各模态 MRC 结果已经是各自的"最优"加权），符合 Fan 2024 的时域路线。
- **MRC+PCA**：Yu 2021 WiFi-Sleep 的核心是 PCA 符号校正 + PCA 融合。在 per-modal PCA 符号校正完成之后，第二级 PCA(3→1) 自然延续这一路线——PCA 自动学习三模态波形的最优线性组合权重，而非预设等权。

---

## 2. 算法步骤

### 2.1 完整流程（修正后）

```text
┌──────────────────────────────────────────────────────────────────┐
│ 预处理（不变）                                                       │
│ Raw BLE CS Frames                                                 │
│   → Phase Unwrap (phases only)                                    │
│   → Filter Chain: median (w=3) → highpass (0.05 Hz) → bandpass   │
│     (0.1–0.35 Hz) [per tone, per variable]                        │
│   → Sliding Window: 20 s / 1 s step                               │
│ [模块: chfusion.py → run_multichannel_segment_filtering()]        │
└──────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Fan (equal)     │ │ Fan-Hilbert     │ │ MRC+PCA (equal) │
│ 路线：时域加权   │ │ 路线：Hilbert   │ │ 路线：PCA 降维  │
│                 │ │ + 时域加权      │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Per modal:      │ │ Per modal:      │ │ Per modal:      │
│ 72-tone bandpass│ │ 72-tone bandpass│ │ 72-tone bandpass│
│   → η-MRC 时域  │ │   → Hilbert 相  │ │   → √η-MRC +    │
│     加权融合    │ │     位对齐      │ │     PCA 符号校正 │
│   → 3 waveforms │ │   → η-MRC 时域  │ │   → 3 waveforms │
│                 │ │     加权融合    │ │                 │
│                 │ │   → 3 waveforms │ │                 │
│ [复用:          │ │ [新增:          │ │ [复用:          │
│  fan_mrc_fusion]│ │  _fan_hilbert_  │ │  mrc_pca_fusion]│
│                 │ │  window_bpms]   │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ 模态融合:        │ │ 模态融合:        │ │ 模态融合:        │
│ 三波形时域       │ │ 三波形时域       │ │ 三波形          │
│ 等权平均         │ │ 等权平均         │ │ → PCA (3→1)    │
│ y = mean(wf_i)  │ │ y = mean(wf_i)  │ │ → 1 waveform   │
│ [新增]           │ │ [新增]           │ │ [新增]           │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────┐
│ Welch PSD → argmax → parabolic → BPM                              │
│ [复用: estimate_bpm_from_waveform()]                               │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 "best" 变体保持不变

`fan_eta_linear`、`fan_eta_sqrt`、`mrc_pca_eta_sqrt` 的 "best" 逻辑不变——按 η 选最优模态的波形，不做三模态融合。这些变体是单模态对照，用于量化三模态融合带来的增益。

---

## 3. 代码修改要点

### 3.1 `_fan_window_bpms()` — 修改

当前 `equal` 返回值（line 311）：

```python
_nanmean_bpm(list(modal_bpms.values()))
```

改为：

```python
# equal: 三模态 MRC 波形时域等权平均 → FFT → BPM
if len(modal_waveforms) >= 2:
    wf_list = [wf - np.mean(wf) for wf in modal_waveforms.values()]
    min_len = min(len(w) for w in wf_list)
    wf_avg = np.mean([w[:min_len] for w in wf_list], axis=0)
    bpm_equal, _, _, _ = estimate_bpm_from_waveform(wf_avg, fs, cfg=cfg)
else:
    bpm_equal = float("nan")
```

同时新增 `modal_waveforms: Dict[str, np.ndarray] = {}`，在每模态 MRC 后将 `y` 保存进去。

### 3.2 `_mrc_pca_window_bpms()` — 修改

当前 `equal` 同样使用 `_nanmean_bpm`。改为 PCA(3→1)：

```python
if len(modal_waveforms) >= 2:
    wf_list = [wf - np.mean(wf) for wf in modal_waveforms.values()]
    min_len = min(len(w) for w in wf_list)
    X_wf = np.column_stack([w[:min_len] for w in wf_list])  # M × 3
    from sklearn.decomposition import PCA
    pca_modal = PCA(n_components=1)
    wf_fused = pca_modal.fit_transform(X_wf).ravel()
    bpm_equal, _, _, _ = estimate_bpm_from_waveform(wf_fused, fs, cfg=cfg)
else:
    bpm_equal = float("nan")
```

同理新增 `modal_waveforms` 保存。

### 3.3 新增 `_fan_hilbert_window_bpms()`

```python
def _fan_hilbert_window_bpms(
    multichannel_by_var, seg_name, ch_list,
    st, end, fs, cfg,
    weight_mode: MrcWeightMode = "linear",
) -> Tuple[float, dict]:
    """
    Per-modal: Hilbert phase-align tones → η-MRC → waveform.
    Modal combine: time-domain equal-weight average → FFT → BPM.
    """
    from scipy.signal import hilbert

    modal_waveforms: Dict[str, np.ndarray] = {}
    modal_etas: Dict[str, float] = {}
    for variable in MODAL_VOTING_VARIABLES:
        ref_seg = multichannel_by_var[variable].get(seg_name)
        if ref_seg is None:
            continue
        ch_map = ref_seg["channels"]
        X, eta, rho = _collect_modal_window_matrix(
            ch_list, ch_map, variable, st, end, fs, cfg
        )
        # Hilbert 瞬时相位对齐（以最高 η 的 tone 为参考）
        analytic = hilbert(X, axis=1)
        phases = np.angle(analytic)
        ref_idx = int(np.argmax(eta))
        ref_phase = phases[ref_idx]
        X_aligned = np.zeros_like(X)
        for i in range(X.shape[0]):
            delta_phi = np.mean(ref_phase - phases[i])
            X_aligned[i] = X[i] * np.cos(delta_phi)
        g = compute_mrc_weights(eta, mode=weight_mode, rho=rho, eps=cfg.eps)
        y = np.sum(g[:, None] * X_aligned, axis=0)
        modal_waveforms[variable] = y
        modal_etas[variable] = _energy_ratio(y, fs, cfg)

    if len(modal_waveforms) < 2:
        return float("nan"), {}
    wf_list = [wf - np.mean(wf) for wf in modal_waveforms.values()]
    min_len = min(len(w) for w in wf_list)
    wf_avg = np.mean([w[:min_len] for w in wf_list], axis=0)
    bpm, _fp, _f, _p = estimate_bpm_from_waveform(wf_avg, fs, cfg=cfg)
    return bpm, {"modal_etas": modal_etas}
```

### 3.4 `estimate_wifi_mrc_segment()` — 新增变体列表，旧代码一条不动

在窗循环中**追加**（不修改现有 `fan_linear` / `fan_equal` / `fan_sqrt` / `mrc_sqrt` / `mrc_equal` / `mrc_no_sign` 的赋值逻辑）：

```python
# 新增列表
fan_equal_wf: List[float] = []
fan_hilbert: List[float] = []
mrc_equal_pca: List[float] = []

for st in starts:
    end = st + win_len
    # ... 现有 Fan / MRC-PCA 逻辑（一条都不动）...

    # 新增：Fan equal 波形平均版
    b_fan_wf, _, _ = _fan_window_bpms(
        multichannel_by_var, seg_name, ch_list, st, end, fs, cfg, "linear",
        equal_mode="waveform_avg"  # 新参数控制 equal 的计算方式
    )
    fan_equal_wf.append(b_fan_wf)

    # 新增：Fan-Hilbert
    b_hb, _ = _fan_hilbert_window_bpms(
        multichannel_by_var, seg_name, ch_list, st, end, fs, cfg
    )
    fan_hilbert.append(b_hb)

    # 新增：MRC-PCA equal PCA(3→1) 版
    _, b_mrc_pca, _, _ = _mrc_pca_window_bpms(
        multichannel_by_var, seg_name, ch_list, st, end, fs, cfg,
        equal_mode="pca3"  # 新参数控制 equal 的计算方式
    )
    mrc_equal_pca.append(b_mrc_pca)
```

返回字典追加（旧字段不动）：

```python
"fan_eta_equal_wf":   _seg_bpm_stats(np.asarray(fan_equal_wf), bpm_gt, len(starts)),
"fan_hilbert_equal":  _seg_bpm_stats(np.asarray(fan_hilbert),  bpm_gt, len(starts)),
"mrc_pca_eta_equal_pca": _seg_bpm_stats(np.asarray(mrc_equal_pca), bpm_gt, len(starts)),
```

### 3.4.1 `_fan_window_bpms()` 和 `_mrc_pca_window_bpms()` 签名扩展

新增 `equal_mode` 参数控制 equal 返回值的行为，向后兼容：

```python
def _fan_window_bpms(
    ...,
    equal_mode: Literal["bpm_avg", "waveform_avg"] = "bpm_avg",
) -> Tuple[float, float, dict]:
```

- `"bpm_avg"`（默认，旧行为）：`nanmean([BPM_r, BPM_l, BPM_p])` — 保留不动
- `"waveform_avg"`（新行为）：三波形时域等权平均 → FFT → BPM

`_mrc_pca_window_bpms()` 同理：
- `"bpm_avg"`（默认，旧行为）：`nanmean([BPM_r, BPM_l, BPM_p])` — 保留不动
- `"pca3"`（新行为）：三波形 PCA(3→1) → FFT → BPM

### 3.5 方法注册表更新

**旧 key 全部保留不动**（保持排行榜/README 中已有数值可追溯）。新变体使用新 key。

```python
# WIFI_MRC_METHOD_SPECS — 追加新变体（旧条目全部保留）
WIFI_MRC_METHOD_SPECS: Tuple[Tuple[str, str, str], ...] = (
    # === 旧版（保留不动）===
    ("B0 Single Remote",              "b0_single_remote",      "steelblue"),
    ("B1 Uniform Remote",             "b1_uniform_remote",     "seagreen"),
    ("Modal top2 equal",              "b2_modal_top2_equal",   "mediumpurple"),
    ("B1 Vote→Equal modal",           "b1_vote_modal_equal",   "olive"),
    ("Fan-η-linear (best)",           "fan_eta_linear",        "coral"),
    ("Fan-η-sqrt (best)",             "fan_eta_sqrt",          "tomato"),
    ("Fan-η-equal (BPM avg, legacy)", "fan_eta_equal",         "darkorange"),
    ("MRC-PCA-η-sqrt (best)",         "mrc_pca_eta_sqrt",      "indianred"),
    ("MRC-PCA-η-equal (BPM avg, legacy)","mrc_pca_eta_equal",  "crimson"),
    ("MRC-PCA-no-sign (best)",        "mrc_pca_no_sign",       "gray"),
    # === 新增：时域波形融合版 ===
    ("Fan-η-equal-wf (waveform avg)", "fan_eta_equal_wf",      "darkgoldenrod"),
    ("Fan-Hilbert-equal (Hilbert+wf)","fan_hilbert_equal",     "goldenrod"),
    ("MRC-PCA-η-equal-pca (PCA3→1)",  "mrc_pca_eta_equal_pca", "firebrick"),
)
```

`MRC_METHOD_KEYS` 追加新 key，不删除旧 key。

### 3.6 消融注册表更新

旧条目保留，追加新变体：

```python
WIFI_MRC_ABLATION_SPECS: Tuple[Tuple[str, str, str], ...] = (
    # 旧版（保留不动）
    ("Fan-ηρ-linear (best)",           "fan_eta_rho_linear",      "chocolate"),
    ("Fan-ηρ-equal (BPM avg, legacy)", "fan_eta_rho_equal",       "saddlebrown"),
    ("MRC-PCA-η-linear (BPM avg, legacy)","mrc_pca_eta_linear",   "firebrick"),
    # 新增：波形融合版
    ("Fan-ηρ-equal-wf (waveform avg)", "fan_eta_rho_equal_wf",    "sienna"),
    ("MRC-PCA-η-linear-pca (PCA3→1)",  "mrc_pca_eta_linear_pca",  "maroon"),
)
```

### 3.7 诊断函数适配

`run_wifi_mrc_diagnosis_pass()` 中的 `_fan_window_bpms` 和 `_mrc_pca_window_bpms` 调用签名不变（仍返回 best/equal 两个 BPM），但 equal 的计算逻辑已变。无需改动诊断函数签名。

### 3.8 绘制函数适配

`plot_wifi_mrc_figures()` 中硬编码的 `ablation_keys` 列表需同步更新方法 key。

---

## 4. 影响范围

| 文件 | 变更类型 |
|------|----------|
| `src/ble_analysis/wifi_mrc.py` | **修改** `_fan_window_bpms`、`_mrc_pca_window_bpms`（新增 `equal_mode` 参数，默认旧行为）；**修改** `estimate_wifi_mrc_segment`、`estimate_wifi_mrc_ablation_segment`（追加新变体列表，旧代码不动）；**新增** `_fan_hilbert_window_bpms`；**更新** `WIFI_MRC_METHOD_SPECS`、`WIFI_MRC_ABLATION_SPECS`（追加新条目，旧条目保留）；**更新** `MRC_METHOD_KEYS`（追加新 key）；**更新** `plot_wifi_mrc_figures` 中的 `ablation_keys` 列表 |
| `docs/methods/README.md` | **更新** §4.9 表：旧条目标记 `(legacy, BPM avg)`，追加新条目 Fan-η-equal-wf / Fan-Hilbert-equal / MRC-PCA-η-equal-pca |

### 不受影响

- `chfusion.py`、`segments.py`、`pca_svd.py` 等 — 零改动
- 诊断函数 (`run_wifi_mrc_diagnosis_pass`) — 签名不变
- 跨域聚合 (`compute_wifi_mrc_cross_domain`) — 自动跟随 spec
- `coherent_mrc.py` — 零改动

---

## 5. 预期产出

| 产出 | 路径 |
|------|------|
| 修改后的模块 | `src/ble_analysis/wifi_mrc.py`（diff ~100 行） |
| 更新后的方法注册表 | `docs/methods/README.md` |

### 5.1 建议运行命令

```bash
# 重新运行 WiFi MRC 实验以获取修正后的 "equal" 数值
python notebooks/scripts/chFusion_wifi_mrc_baselines.py
python notebooks/scripts/chFusion_wifi_mrc_cross_domain.py
```

---

## 6. 风险与保留问题

| ID | 风险 | 缓解措施 |
|----|------|----------|
| R1 | 修正后的 equal 可能劣于修正前（BPM 平均意外地平滑了离群值） | 如实报告；若修正后更差则说明 BPM 平均碰巧掩盖了某模态的坏估计 |
| R2 | Fan-Hilbert 的 `cos(Δφ)` 投影在低采样率下可能不稳定 | Hilbert 变换需要至少几个周期的采样点——20s 窗 × 0.1–0.35 Hz = 2–7 周期，边界条件 |
| R3 | MRC-PCA equal 的 PCA(3→1) 只有 M×3 矩阵，PC1 方差占比可能很低 | 记录 PC1 variance ratio，若 < 0.5 则三波形共性弱，PCA(3→1) 意义有限 |

---

## 7. 验证状态

| 字段 | 内容 |
|------|------|
| **验证状态** | 待实现 |
| **实际脚本** | — |
| **报告链接** | — |

---

## 8. 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/wifi_mrc_equal_fix_plan.md`

执行完成后：
1. 运行 `chFusion_wifi_mrc_baselines.py` + `chFusion_wifi_mrc_cross_domain.py` 获取修正后数值
2. 更新 `docs/methods/README.md` §4.9 中 Fan-η-equal 和 MRC-PCA-η-equal 的描述和数值
3. 新增 Fan-Hilbert 条目到 README
