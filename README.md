# BLE HCI Sensing

BLE 信道探测（CS）与方向估计（DF）数据的离线分析与算法验证项目。从原 BLE Host 上位机项目中拆分而来，仅保留 notebook 实验与数据处理核心模块。

## 项目结构

```
├── *.ipynb              # Jupyter 分析 notebook
├── sampleData/          # 示例 JSONL/JSON 帧数据
├── src/
│   ├── data_saver.py    # JSONL 帧数据加载
│   ├── config.py        # 配置（data_saver 依赖）
│   └── utils/
│       └── signal_algrithom.py  # 滤波与信号处理
└── docs/
    └── jsonl_format.md  # JSONL 数据格式说明
```

## 环境要求

- Python 3.9+
- Jupyter Lab / Notebook

## 安装

```bash
pip install -r requirements.txt
```

## 使用

1. 在项目根目录启动 Jupyter
2. 打开对应的 notebook（如 `glb_load_df_saved_frames_show_analysis.ipynb`）
3. 修改 `filepath` 指向 `sampleData/` 下的 JSONL 文件
4. 按顺序执行 cell

Notebook 会自动将 `src/` 加入 Python 路径，无需额外配置。

## 数据格式

采集数据为 JSONL 格式，详见 [docs/jsonl_format.md](docs/jsonl_format.md)。

## 与原 BLE Host 的关系

本项目由原 [ble_host](https://github.com/cwdao/ble_host) 仓库的 `examples/` 目录及 notebook 依赖的 `src/` 模块拆分而来，不包含 GUI 上位机、串口通信与打包相关代码。
