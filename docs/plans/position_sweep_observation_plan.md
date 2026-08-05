# BLE CS 观测变量特性验证：金属板位置扫描 + 人体-金属板对比 — 实现计划

> **来源**：论文 draft v0.4 Chapter 4「利用 BLE CS 观测呼吸」；Advisor 5.6sol 建议（受控工作点扫描实验验证物理模型）  
> **目标报告**：`docs/reports/position_sweep_observation_report.md`  
> **日期**：2026-08-05  
> **验证状态**：待实现

---

## 1. 动机与背景

### 1.1 问题

论文 Chapter 4 建立了 BLE CS 呼吸观测模型（径向幅值投影 vs 切向相位投影），并通过 Fig 2（信道间关系）和 Fig 3（模态间关系）提供了旧数据（cs_095806/cs_091339/cs_102621）上的证据。但旧数据缺乏**同一场景下连续位置变化的系统性观测**——这正是证明幅度-相位互补性、菲涅尔区边界随位置/频率变化的最直接方式。

同时，现有结论「Phase 在金属板上可用、在真人身上退化」目前仅基于跨数据集（CS 金属板 vs HKH 真人）的比较，缺乏**同距离下金属板 vs 人体的直接对照**。

### 1.2 本 plan 定位

**定性观测实验**（非算法验证）。目标是从新数据中提取可视化素材，嵌入论文 Chapter 4，形成完整的论证链：

```
§4.1 观测模型（公式 1-9）
  → §4.2 单信道三变量位置扫描（图 A1-A3：证明互补性 + position dependence）
  → §4.3 信道间关系（图 B/C：Fresnel + 连续相位偏差 + position dependence）
  → §4.4 模态间关系（图 D/E：多相量模型 + Δφ 随位置变化 + 人/金属板 η 对比）
  → 过渡到 Ch5：因此需要 per-window 估计 + 质量驱动融合
```

### 1.3 与已有 Fig 2/3 的关系

本 plan 的图是**补充/扩展**，非替换。旧 Fig 2/3 覆盖不同房间的对比，新图覆盖同一房间内不同位置的连续变化。两者互补：

| 维度 | 旧 Fig 2/3 | 新图 |
|------|-----------|------|
| 变量 | 不同房间 | 同一房间不同位置（连续 1cm 步进） |
| 证据类型 | 房间间对比 | 位置连续追踪 |
| 物理含义 | 场景依赖性 | 菲涅尔区边界随距离的渐变性 |

---

## 2. 物理与变量

### 2.1 可用观测量

| 变量 | 是否使用 | 理由 |
|------|----------|------|
| `remote_amplitudes` | ✅ | 远端幅值（径向投影） |
| `local_amplitudes` | ✅ | 本地幅值（径向投影） |
| `phases`（合成相位） | ✅ | 两端 PCT 复数乘法后相位（切向投影之和） |
| `amplitudes`（总幅值） | ❌ | 双方噪声乘积，无独立物理意义 |

**术语约定**：
- **合成相位**（composite phase）= 两端 PCT 复数乘法后的相位，即 `unwrap(∠(Z_l × Z_r))`
- **呼吸波形相位**（respiratory waveform phase）= 带通滤波后呼吸时序信号的瞬时相位，通过 Hilbert 变换得到
- 正文中首次出现时各加一句说明以消除歧义

### 2.2 符号约定

| 符号 | 含义 |
|------|------|
| η | 呼吸频段能量比 |
| ρ | 谱峰突出度（peak prominence） |
| Δφ | 两波形间的瞬时相位差（Hilbert 变换后计算） |
| γ | 波形对相干性（complex correlation magnitude） |

---

## 3. 数据与预处理

### 3.1 数据文件

| 文件 | 内容 | 帧数 |
|------|------|------|
| `sampleData/metal_verify/CS_frames_all_20260804_090719.jsonl` | 金属板 16 BPM 呼吸，100→85 cm 逐段前进 | 1396 lines (meta + frames) |
| `sampleData/metal_verify/CS_frames_all_20260804_094043.jsonl` | 人体呼吸，3 个距离 | ~600 lines |

### 3.2 金属板段标记

首行 meta；后续 frame 行，含 `seq` 字段（全局帧号），以下为各段的 `seq` 范围：

| 段 | seq 范围 | 特征描述 |
|----|----------|----------|
| 1 | 434–540 | 含走动（434–450），质量较差时可去除初段 |
| 2 | 550–657 | 部分信道微小双峰 |
| 3 | 663–772 | 部分信道微小双峰 |
| 4 | 790–898 | 部分信道微小双峰（与上段双峰信道几乎反转） |
| 5 | 907–1015 | — |
| 6 | 1022–1130 | 部分信道已不明显（幅值弱势位置） |
| 7 | 1138–1236 | 部分信道较大双峰 |
| 8 | 1246–1352 | 部分信道微小双峰 |
| 9 | 1362–1469 | — |
| 10 | 1479–1584 | 部分信道双峰明显，几乎看不出主信道 |
| 11 | 1595–1710 | 另一部分信道双峰明显 |
| 12 | 1718–1827 | — |
| 13 | 1837–1942 | 微小双峰 |
| 14 | 1947–2055 | 明显伪双峰幅值（≈跨过同相点） |
| 15 | 2059–2169 | 双峰保持不变，伪峰减小 |
| 16 | 2174–2279 | — |

**距离标定**：初始距离 100 cm（段 1），每段前进 1 cm，段 16 约 85 cm。图片从左到右对应距离由近到远（100→85 cm）。

### 3.3 人体呼吸段标记

`CS_frames_all_20260804_094043.jsonl`：

| 段 | seq 范围 | 距离 |
|----|----------|------|
| H1 | 30–210 | 80 cm |
| H2 | 320–380 | 90 cm |
| H3 | 397–470 | 100 cm |

### 3.4 预处理约定

复用现有 `src/ble_analysis/segments.py` 中的 `FilterParams` 和 `process_segments()`。

**两种预处理深度**（不同图按需选用）：

| 深度 | 步骤 | 保留特征 | 适用图 |
|------|------|----------|--------|
| **HP only** | median(w=3) → highpass(0.05 Hz) | 保留伪峰、双峰、谐波等非呼吸成分 | 图 A（展示原始观测差异，不丢失伪峰双峰） |
| **HP+BP** | median(w=3) → highpass(0.05 Hz) → bandpass(0.1–0.35 Hz) | 只保留呼吸频段，用于相位分析 | 图 C（需要干净的呼吸波形以比较相位偏移）、图 D、图 E |

注意：**金属板数据每段独立处理**（不跨段滤波），因为每段对应不同位置。

### 3.5 数据加载实现要点

```python
# 伪代码：从 JSONL 提取变量序列
def load_jsonl_frames(filepath):
    frames = []
    with open(filepath) as f:
        for line in f:
            d = json.loads(line)
            if d.get("record_type") == "frame" and d.get("frame_type") == "channel_sounding":
                frames.append(d)
    return frames

# 提取指定 seq 范围内的变量矩阵 (n_channels × n_frames)
# 变量：remote_amplitudes = channels[*]["remote_amp"]
#       local_amplitudes  = channels[*]["local_amp"]
#       phases            = unwrap(∠(channels[*]["I"] + j*channels[*]["Q"]))
# 注意：phases 需要 unwrap（沿时间轴）；合成相位 = local_phase + remote_phase 的相位和
```

### 3.6 采样率估计

每段内部的 frame 时间间隔需从 `t_dev_ms` 或 `t_host_utc_ns` 计算实际采样率（约为 2–4 Hz）。用中位数间隔的倒数作为该段的等效 `fs`。

---

## 4. 图 A：不同位置下三变量的时域波形对比

### 4.1 目的

论文 §4.2 验证实验。展示同一信道在连续位置变化下，幅度和相位的呼吸波形出现差异化演变——幅度可能出现伪峰/双峰（径向投影零点附近），而相位保持较好的正弦性（或反之）。证明幅度-相位互补性。

### 4.2 预处理深度

**HP only**（median + highpass 0.05 Hz），**不做 bandpass**，以保留伪峰和双峰特征。

### 4.3 信道选取

**全程固定一个信道**。选取策略：

1. 在所有 16 段上计算每个信道的 η 中位数。
2. 选 η 中位数的信道（非最优、非最差），代表「典型」信道。
3. 同时记录该信道号，写入报告。

### 4.4 产出

#### A1：分立图（16 张）

每段一张独立 PNG，内容：

- X 轴：时间（秒），以每段起始时刻为 t=0
- Y 轴：幅度（归一化到 [0,1] 或 z-score）、合成相位（rad，可能以 rad 或归一化显示）
- 3 条曲线：remote_amplitudes、local_amplitudes、phases，颜色区分
- 背景空白（无网格），保留边框
- 文件名：`outputs/figures/position_sweep_figA1_seg{N}_{distance}cm.png`（N=1–16）

#### A2：拼合长图（1 张）

将 16 张分立图垂直排列拼合，统一 X 轴长度，左侧标注距离（100→85 cm），自上而下。

- 文件名：`outputs/figures/position_sweep_figA2_stitched.png`

#### A3：选址对比图（可选，2-4 张）

若某些段的对比特别明显（如段 7 幅值双峰 vs 段 14 伪双峰），单独提取 2-4 段做突出对比的大图。

- 文件名：`outputs/figures/position_sweep_figA3_selected_positions.png`

### 4.5 风格要求

```text
- 无网格（no grid）
- 背景白色/透明
- 保留坐标轴边框
- 线宽 ≥ 1.5 pt（适合论文缩放）
- 字号 ≥ 10 pt
- 图例清晰，置于图外或图内空白处
```

---

## 5. 图 B：同一模态内不同信道的波形差异（跨位置对比）

### 5.1 目的

论文 §4.3 信道间关系。展示同一模态内不同信道因频率差异导致菲涅尔区边界不同，使得在同一位置下各信道响应各异；位置移动后优劣互换。

### 5.2 预处理深度

**HP only**（median + highpass 0.05 Hz），不做 bandpass，展示定性波形差异。

### 5.3 位置选取

**3 个连续段**：段 13（1837–1942）、段 14（1947–2055）、段 15（2059–2169）。

理由：
- 三段连续、距离跨度仅 3 cm，菲涅尔区渐变可追踪
- 段 13 微小双峰 → 段 14 明显伪双峰（≈同相点）→ 段 15 伪峰减小，构成完整过渡
- 连续位置确保其他因素（房间布局、多径几何）不变，仅距离在变

### 5.4 信道选取

**3-4 个信道，三段一致**。选取策略：

1. 在三段上分别计算各信道的 η（HP 滤波后，以 0.1–0.35 Hz 为呼吸频段）。
2. 选出在三段间 η 变化最大的 3-4 个信道（即对该 3 cm 距离变化最敏感的信道），以确保展示效果明显。
3. 若敏感信道不足 3 个，则补充 η 中位数附近的信道。

### 5.5 产出

#### B1：三模态独立图（3 张）

- 每张对应一个模态（remote_amplitudes / local_amplitudes / phases）
- 每张 3 行（段 13/14/15）× 1 列，行内叠加 3-4 条信道波形
- 颜色按信道区分，三段颜色一致
- 文件名：`outputs/figures/position_sweep_figB1_{modal}.png`（modal = remote/local/phase）

#### B2：信道-位置对照矩阵图（可选，1 张）

- 行 = 3 个信道，列 = 3 个段，格内 = 该信道在该段的波形（单条曲线）
- 仅选 1 个模态（remote_amplitudes），若效果好也可做
- 文件名：`outputs/figures/position_sweep_figB2_channel_position_matrix.png`

### 5.6 风格要求

同图 A（无网格、白底、保留边框）。

---

## 6. 图 C：不同位置下的信道间相位偏移

### 6.1 目的

论文 §4.3 信道间关系（类似旧 Fig 2 的扩展）。展示信道间连续相位偏差随位置变化——**不仅是不同房间不同、同一房间的不同位置也不同**。

### 6.2 预处理深度

**HP+BP**（median + highpass + bandpass），以获得干净的呼吸波形用于相位比较。

### 6.3 位置选取

两个有对比性的位置：
- **位置 Good**：段 5（907–1015，多数信道波形干净、无明显伪峰）
- **位置 Hard**：段 14（1947–2055，伪双峰明显、≈同相点）

两个位置距离差约 10 cm，确保有足够差异但仍在同一房间内。

### 6.4 产出

#### C1：波形对比图（每模态 1 张 × 3 模态 = 3 张，可按需拆为 Good/Hard 各 1 张 = 6 张）

仿旧 Fig 2a-c 格式，但按位置拆分：

对每个位置（Good/Hard）、每个模态（remote/local/phase），选 4 个代表信道，画出：

- (a) 原始带通波形叠加
- (b) PCA ±1 符号校正后
- (c) Hilbert 连续相位对齐后

为保证图不拥挤，建议将 (a)(b)(c) 做成一列（3 行），而非一行三列。

- 文件名：`outputs/figures/position_sweep_figC1_{position}_{modal}.png`
  - position = good (段5) / hard (段14)
  - modal = remote / local / phase

> **注意**：Good 和 Hard 是两张独立图（不是子图），以便论文按需独立引用。

#### C2：72×72 相干性热力图（每模态 1 张 × 3 模态 × 2 位置 = 6 张）

仿旧 Fig 2d 格式：

- 对每个位置（Good/Hard）、每个模态，计算 72×72 tone-pair 的复相干性 γ
- 热力图颜色映射需与旧 Fig 2d 一致（便于跨图比较）
- 文件名：`outputs/figures/position_sweep_figC2_heatmap_{position}_{modal}.png`

### 6.5 风格要求

同图 A，额外要求：热力图的 colorbar 清晰可读，标注 γ 值的范围 [0, 1]。

---

## 7. 图 D：模态间相位偏移随位置的变化

### 7.1 目的

论文 §4.4 模态间关系（类似旧 Fig 3 的扩展）。展示三模态波形间的相位差随位置系统性变化——验证多相量模型，排除「模态间相位关系是随机噪声」的怀疑。

### 7.2 预处理深度

**HP+BP**（median + highpass + bandpass）。

### 7.3 方法

**不做信道融合**（尚未到算法章节）。选取单个代表信道（同图 A 的信道），或选 3-4 个信道分别展示。

### 7.4 产出

#### D1：三模态波形叠加图（每段 1 张 = 16 张，或每个代表位置 1 张）

- 选定信道后，每段画三模态带通波形叠加
- 用于观察 Δφ 的视觉差异
- 文件名：`outputs/figures/position_sweep_figD1_seg{N}_{distance}cm.png`

#### D2：Δφ vs 位置追踪图（每信道 1 张 = 1–4 张）

- X 轴：段号 / 距离（1–16，100→85 cm）
- Y 轴：三对模态的相位差（rad）：
  - Δφ(Remote, Local)
  - Δφ(Remote, Phase)
  - Δφ(Local, Phase)
- 每个点代表该段的 Δφ（取该段中间 10 秒稳定区间计算）
- 三条折线，颜色区分
- 文件名：`outputs/figures/position_sweep_figD2_dphi_vs_position_ch{ch}.png`

> **注意**：D1 和 D2 是独立图文件，不合成为子图。论文写作时手动合并排版。

### 7.5 风格要求

同图 A。D2 的 marker 大小适中，折线清晰。

---

## 8. 图 E：人体 vs 金属板对比

### 8.1 目的

论文 §4.4 或 §7.2。在相同距离（80/90/100 cm）下直接对比金属板和人体呼吸的观测变量特性。核心待验证假说：**合成相位在金属板上与幅值性能相近，在人体呼吸中显著劣化**（η 系统性下降）。

### 8.2 预处理深度

**HP+BP**（median + highpass + bandpass）。

### 8.3 方法

- 金属板选段 1（100 cm，434–540，去除走动初段 434–450）、段约 85 cm（段 16，2174–2279）以及中间段
- **对齐策略**：人体 H3 为 100 cm，金属板段 1 为 100 cm——恰好可直接对比。其他距离需插值匹配。
- 计算每个信道、每种变量的 η 和 ρ，取均值（不融合）

### 8.4 产出

#### E1：波形对比图（3 距离 × 3 变量 = 9 格，可拆为独立图）

- 每格叠加金属板和人各一条带通波形（已去除直流）
- 若同距离无可比段，用最接近的金属板段替代并标注
- 文件名格式：`outputs/figures/position_sweep_figE1_{distance}_{modal}.png`（拆为独立图）或 `outputs/figures/position_sweep_figE1_all.png`（合成一张）

#### E2：η 能量比对比柱状图（1 张）

- 分组柱状图：3 变量 × 3 距离，每组两根柱（金属板 vs 人）
- X 轴标注：变量 + 距离
- Y 轴：逐信道 η 均值 ± 标准差（error bar）
- 文件名：`outputs/figures/position_sweep_figE2_eta_comparison.png`

#### E3：η + ρ 联合对比图（1 张）

- 类似 E2，但同时展示 η（左 Y 轴）和 ρ（右 Y 轴）
- 或使用分组柱状图，每组 4 根柱（金属板 η / 人 η / 金属板 ρ / 人 ρ）
- 文件名：`outputs/figures/position_sweep_figE3_eta_rho_comparison.png`

### 8.5 风格要求

同图 A。柱状图需 error bar，颜色区分金属板（灰色/银色）和人（暖色），保持学术风格。

---

## 9. 实现要点

### 9.1 建议文件

| 类型 | 路径 |
|------|------|
| 实验脚本 | `notebooks/scripts/chFusion_position_sweep_observation.py` |
| 可复用模块（如需新增） | `src/ble_analysis/jsonl_loader.py`（JSONL 帧加载工具） |
| 可复用模块（复用） | `src/ble_analysis/segments.py`（FilterParams, process_segments） |
| 可复用模块（复用） | `src/ble_analysis/chfusion.py`（η/ρ 计算） |
| 可复用模块（复用） | `src/ble_analysis/metrics.py`（BPM 估计，如需） |

### 9.2 复用 API

```python
from ble_analysis.segments import FilterParams, process_segments
from ble_analysis.chfusion import compute_eta, compute_rho
from ble_analysis.resampling import resample_to_uniform_grid
```

### 9.3 脚本结构建议

```text
notebooks/scripts/chFusion_position_sweep_observation.py

├── Section 1: 数据加载
│   ├── load_jsonl_frames() → List[dict]
│   ├── extract_channel_series(frames, channels, variables) → np.ndarray
│   └── segment_by_seq(frames, ranges) → Dict[str, np.ndarray]
│
├── Section 2: 预处理
│   ├── hp_only() → median + highpass
│   ├── hp_bp()   → median + highpass + bandpass
│   └── 复用 FilterParams
│
├── Section 3: 图 A 数据提取 + 绘图
├── Section 4: 图 B 数据提取 + 绘图
├── Section 5: 图 C 数据提取 + 绘图
├── Section 6: 图 D 数据提取 + 绘图
├── Section 7: 图 E 数据提取 + 绘图
│
└── Section 8: 辅助诊断图（可选）
```

### 9.4 不做的事

- 不在此脚本中运行算法验证（BPM/RMSE 比较）
- 不做信道融合或模态融合
- 不修改 `src/ble_analysis/` 中的现有模块行为
- 不生成综合性的成果汇报

---

## 10. 预期产出

### 10.1 图产出清单

| 图 ID | 内容 | 数量 | 路径模板 |
|-------|------|------|----------|
| A1 | 三变量单段分立图 | 16 张 | `outputs/figures/position_sweep_figA1_seg{N}_{distance}cm.png` |
| A2 | A1 拼合长图 | 1 张 | `outputs/figures/position_sweep_figA2_stitched.png` |
| A3 | 选址对比图 | 1–2 张 | `outputs/figures/position_sweep_figA3_selected_positions.png` |
| B1 | 三模态信道对比 | 3 张 | `outputs/figures/position_sweep_figB1_{modal}.png` |
| B2 | 信道-位置矩阵 | 0–1 张 | `outputs/figures/position_sweep_figB2_channel_position_matrix.png` |
| C1 | 信道相位偏移波形 | ≤6 张 | `outputs/figures/position_sweep_figC1_{position}_{modal}.png` |
| C2 | 72×72 γ 热力图 | ≤6 张 | `outputs/figures/position_sweep_figC2_heatmap_{position}_{modal}.png` |
| D1 | 三模态波形叠加 | ≤16 张 | `outputs/figures/position_sweep_figD1_seg{N}_{distance}cm.png` |
| D2 | Δφ vs 位置追踪 | 1–4 张 | `outputs/figures/position_sweep_figD2_dphi_vs_position_ch{ch}.png` |
| E1 | 人体 vs 金属板波形 | ≤9 张 | `outputs/figures/position_sweep_figE1_{distance}_{modal}.png` |
| E2 | η 对比柱状图 | 1 张 | `outputs/figures/position_sweep_figE2_eta_comparison.png` |
| E3 | η+ρ 联合对比 | 1 张 | `outputs/figures/position_sweep_figE3_eta_rho_comparison.png` |

### 10.2 数值产出

| 产出 | 路径 | 用途 |
|------|------|------|
| 选中的代表信道号 | 写入报告 | 记录固定信道选择 |
| 各段/信道 η ρ 值 | `outputs/reports/position_sweep_segment_quality.npy` | 诊断参考 |
| 各段三模态 Δφ | `outputs/reports/position_sweep_dphi_per_segment.npy` | 图 D2 数据源 |
| 人vs金属板 η ρ | `outputs/reports/position_sweep_human_vs_metal_quality.npy` | 图 E2/E3 数据源 |

### 10.3 报告

| 产出 | 路径 |
|------|------|
| 观测验证报告 | `docs/reports/position_sweep_observation_report.md` |

---

## 11. 风险与保留问题

### 11.1 数据风险

- 段 1 含走动帧（434–450），若波形异常需截去前半段
- 人体呼吸帧数较少（H1=180 帧，H2=60 帧，H3=73 帧），H2/H3 可能不足以做可靠的 η/ρ 估计
- 人体呼吸无 ground truth BPM——仅能定性对比波形形态和 η/ρ

### 11.2 展示风险

- 固定信道如果在某些段恰好非常差（η≈0），图 A 中该段的波形可能是纯噪声——可选该段备用信道（如 η 第二高信道）画影线对比
- 段的等效采样率可能不均匀（event 间隔 250–500 ms 浮动），需在每段内做时间轴插值后再滤波

### 11.3 保留问题

| ID | 问题 |
|----|------|
| Q1 | 金属板实际 BPM=16，但无独立传感器验证，若段的实际 BPM 有漂移需标注 |
| Q2 | 人体呼吸无 ground truth——η 对比以信道均值为准，无法做统计检验 |
| Q3 | 图 C 的 γ 热力图若在单场景内差异不够明显（相比旧数据跨房间对比），可能视觉冲击力不足 |

---

## 12. 验证状态

状态：**待实现**

---

## 给执行 Agent 的首条指令

请在 Cursor Composer 中启用 `BLE CS 执行 Agent`，并严格执行：

`docs/plans/position_sweep_observation_plan.md`

执行完成后，请返回以下材料给 Claude/DeepSeek Review：

- `docs/plans/position_sweep_observation_plan.md`（回填 §12 验证状态）
- `docs/reports/position_sweep_observation_report.md`
- `outputs/figures/position_sweep_*.png`
- `outputs/reports/position_sweep_*.npy`
- 关键脚本路径
- git commit message 或 git diff 摘要
