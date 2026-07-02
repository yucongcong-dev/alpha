"""
YAML 配置文件加载与缓存。

本模块负责查找 settings.yaml、解析 YAML 内容，并基于文件签名缓存配置。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

_YAML_SEARCH_PATHS: list[str] = [
    "settings.yaml",
    "config/settings.yaml",
]
"""默认 YAML 配置文件查找路径（按优先级）。"""

_ENV_CONFIG_PATH: str = "ALPHA_CONFIG_FILE"
"""可通过该环境变量指定配置文件路径。"""


def _resolve_yaml_path() -> Optional[str]:
    """按优先级查找 YAML 配置文件路径。"""
    env_path = os.environ.get(_ENV_CONFIG_PATH)
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    for rel in _YAML_SEARCH_PATHS:
        if os.path.isfile(rel):
            return os.path.abspath(rel)

    project_root = Path(__file__).resolve().parent.parent.parent
    candidate = project_root / "settings.yaml"
    if candidate.is_file():
        return str(candidate)

    return None


def load_yaml_config(config_path: str = "") -> dict[str, Any]:
    """从 YAML 文件加载运行配置。文件不存在或解析失败返回空字典。"""
    try:
        import yaml
    except ImportError:
        return {}

    path = config_path if config_path else _resolve_yaml_path()
    if not path or not os.path.isfile(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            return data
    except (yaml.YAMLError, UnicodeDecodeError, OSError):
        pass

    return {}


def _config_file_signature(path: str | None) -> tuple[int, int] | None:
    """返回配置文件签名：(mtime_ns, size)。"""
    if not path or not os.path.isfile(path):
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def get_yaml_config(config_path: str = "") -> dict[str, Any]:
    """获取 YAML 配置（带缓存）。"""
    cache_attr = "_yaml_config_cache"
    resolved_path = os.path.abspath(config_path) if config_path else _resolve_yaml_path()
    cache_key = resolved_path or "__missing__"
    signature = _config_file_signature(resolved_path)
    cache = getattr(get_yaml_config, cache_attr, {})  # type: ignore[attr-defined]
    cached_entry = cache.get(cache_key)
    if isinstance(cached_entry, dict):
        cached_signature = cached_entry.get("signature")
        cached_path = cached_entry.get("path")
        cached_data = cached_entry.get("data")
        if (
            cached_signature == signature
            and cached_path == resolved_path
            and isinstance(cached_data, dict)
        ):
            return cached_data
    data = load_yaml_config(resolved_path or "")
    cache[cache_key] = {
        "path": resolved_path,
        "signature": signature,
        "data": data,
    }
    setattr(get_yaml_config, cache_attr, cache)
    return data
