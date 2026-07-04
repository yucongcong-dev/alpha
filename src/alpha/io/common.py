"""
IO 基础公共工具。

本模块承载更底层、无策略语义的公共能力，供 output_paths、
results_store、policy、generator 等上层模块复用，
避免它们彼此形成反向依赖。
"""

from __future__ import annotations

from contextlib import suppress
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from ..config.constants import DEFAULT_DATASET_ID

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data"


def atomic_write_json(path: str, payload: Any) -> None:
    """以原子方式写入 JSON，避免中断运行破坏状态文件。"""
    if not path:
        return
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            with suppress(OSError):
                os.remove(temp_path)


def sanitize_dataset_id_for_filename(dataset_id: str) -> str:
    """将 dataset_id 转成适合文件名的安全片段。"""
    import re

    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", dataset_id.strip())
    return sanitized or DEFAULT_DATASET_ID


def resolve_runtime_data_dir(data_dir: str = "") -> Path:
    """
    解析运行时 data 目录。

    优先级：
    1. 显式传入的 data_dir
    2. 当前工作目录下存在的 data/
    3. 项目内置 data/
    """
    if data_dir:
        return Path(data_dir)
    cwd_data_dir = Path.cwd() / "data"
    if cwd_data_dir.exists():
        return cwd_data_dir
    return DATA_DIR
