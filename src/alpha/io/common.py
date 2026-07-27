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
from ..workspace import DEFAULT_WORKSPACE

PROJECT_ROOT = DEFAULT_WORKSPACE.root
# Disk-backed, reproducible runtime cache root. In-memory YAML / blacklist /
# runtime caches use separate module-level state and do not live here.
CACHE_DIR = DEFAULT_WORKSPACE.cache_dir
RESULTS_DIR = DEFAULT_WORKSPACE.results_dir
DATA_DIR = DEFAULT_WORKSPACE.data_dir
DATASETS_DIR = DEFAULT_WORKSPACE.datasets_dir
SHARED_DIR = DEFAULT_WORKSPACE.shared_dir
SHARED_BLACKLISTS_DIR = DEFAULT_WORKSPACE.shared_blacklists_dir
TEMPLATES_DIR = DEFAULT_WORKSPACE.templates_dir
BLACKLISTS_DIR = DEFAULT_WORKSPACE.blacklists_dir


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

    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", dataset_id.strip()).strip(".")
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


def resolve_templates_dir(templates_dir: str = "") -> Path:
    """
    解析模板库根目录。

    优先级：
    1. 显式传入的 templates_dir
    2. 当前工作目录下存在的 datasets/
    3. 工作区 datasets/
    """
    if templates_dir:
        return Path(templates_dir)
    cwd_datasets_dir = Path.cwd() / "datasets"
    if cwd_datasets_dir.exists():
        return cwd_datasets_dir
    return TEMPLATES_DIR


def resolve_blacklists_dir(blacklists_dir: str = "") -> Path:
    """
    解析黑名单根目录。

    优先级：
    1. 显式传入的 blacklists_dir
    2. 当前工作目录下存在的 datasets/
    3. 工作区 datasets/
    """
    if blacklists_dir:
        return Path(blacklists_dir)
    cwd_datasets_dir = Path.cwd() / "datasets"
    if cwd_datasets_dir.exists():
        return cwd_datasets_dir
    return BLACKLISTS_DIR


def resolve_shared_blacklists_dir(shared_blacklists_dir: str = "") -> Path:
    """Resolve cross-dataset blacklist rules independently from dataset assets."""
    if shared_blacklists_dir:
        return Path(shared_blacklists_dir)
    cwd_shared_dir = Path.cwd() / "shared" / "blacklists"
    if cwd_shared_dir.exists():
        return cwd_shared_dir
    return SHARED_BLACKLISTS_DIR
