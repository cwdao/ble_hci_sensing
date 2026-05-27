"""BLE frame data loading."""

import os
from pathlib import Path

from data_saver import DataSaver


def load_ble_frames(filepath, verbose=True):
    """
    Load BLE frame data using existing DataSaver.

    Parameters
    ----------
    filepath : str or Path
        Path to JSON or JSONL frame data.
    verbose : bool
        Whether to print loading information.

    Returns
    -------
    data : dict or None
        Loaded data object.
    frames : list
        data["frames"] if available, otherwise [].
    """
    filepath = str(filepath)

    if not os.path.exists(filepath):
        if verbose:
            print(f"⚠️  文件不存在: {filepath}")
            print(f"当前目录: {os.getcwd()}")
            print("\n请修改 filepath 变量，指向正确的文件路径")
        return None, []

    if verbose:
        print(f"✓ 找到文件: {filepath}")
        print(f"文件大小: {os.path.getsize(filepath) / 1024 / 1024:.2f} MB")
        print(f"正在加载: {filepath}")

    saver = DataSaver()
    data = saver.load_frames(filepath)

    if data is None:
        if verbose:
            print("✗ 加载失败")
        return None, []

    frames = data.get("frames", [])
    if verbose:
        print("✓ 加载成功")
        print(f"✓ 共加载 {len(frames)} 帧数据")
    return data, frames
