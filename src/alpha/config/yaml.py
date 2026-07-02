"""
YAML 配置文件加载与缓存。

本模块负责查找 settings.yaml、expression_policies.yaml、dataset_profiles.yaml、
constant_defaults.yaml，解析 YAML 内容并合并为统一配置。

合并优先级 (高 → 低)：
  1. settings.yaml           — 用户主配置 (模拟、运维、运行时)
  2. expression_policies.yaml — 表达式策略
  3. dataset_profiles.yaml   — 数据集 profiles
  4. constants_defaults.yaml — 代码常量默认值

同级 key 合并策略：settings.yaml 覆盖 expression_policies.yaml 覆盖 ...
深合并仅用于 expression_policies、dataset_profiles 顶层的 dataset key。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .types import YamlConfig

# ---------------------------------------------------------------------------
# YAML 文件定义
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_YAML_FILES: list[tuple[str, list[str]]] = [
    ("constants_defaults", ["constants_defaults.yaml", "config/constants_defaults.yaml"]),
    ("dataset_profiles", ["dataset_profiles.yaml", "config/dataset_profiles.yaml"]),
    ("expression_policies", ["expression_policies.yaml", "config/expression_policies.yaml"]),
    ("settings", ["settings.yaml", "config/settings.yaml"]),
]
"""YAML 文件定义：(逻辑名称, [相对搜索路径])，按优先级升序排列。"""

_ENV_CONFIG_PATH: str = "ALPHA_CONFIG_FILE"
"""可通过该环境变量指定主配置文件路径。"""


def _resolve_file(search_paths: list[str]) -> str | None:
    """按搜索路径列表查找文件，返回第一个存在的文件的绝对路径。"""
    for rel in search_paths:
        if os.path.isfile(rel):
            return os.path.abspath(rel)
    return None


def _resolve_yaml_path() -> str | None:
    """按优先级查找主 settings.yaml 配置文件路径。"""
    env_path = os.environ.get(_ENV_CONFIG_PATH)
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    for name, search_paths in _YAML_FILES:
        if name == "settings":
            resolved = _resolve_file(search_paths)
            if resolved:
                return resolved

    candidate = _PROJECT_ROOT / "settings.yaml"
    if candidate.is_file():
        return str(candidate)

    return None


def _load_yaml_file(path: str) -> YamlConfig:
    """从单个 YAML 文件加载配置。解析失败返回空字典。"""
    try:
        import yaml
    except ImportError:
        return {}

    if not os.path.isfile(path):
        return {}

    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            return data
    except (yaml.YAMLError, UnicodeDecodeError, OSError):
        pass

    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """深合并两个字典：override 中的值覆盖 base。

    对于 expression_policies 和 dataset_profiles 的顶层 key，
    当两边都是 dict 时进行深合并（而非简单覆盖），以支持 dataset 级别的增量覆盖。
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # 对已知的顶层合并段进行深合并
            if key in ("expression_policies", "dataset_profiles"):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
        else:
            result[key] = value
    return result


def _load_all_yamls(settings_path: str | None = None) -> YamlConfig:
    """加载所有 YAML 文件并按优先级合并。

    返回合并后的完整配置字典。
    """
    merged: YamlConfig = {}
    project_dir = str(_PROJECT_ROOT)

    for name, search_paths in _YAML_FILES:
        if name == "settings" and settings_path:
            resolved = os.path.abspath(settings_path)
        else:
            # 先在项目根目录找，再在 config/ 子目录找
            resolved = None
            for rel in search_paths:
                full = os.path.join(project_dir, rel) if not os.path.isabs(rel) else rel
                if os.path.isfile(full):
                    resolved = full
                    break

        if resolved and os.path.isfile(resolved):
            data = _load_yaml_file(resolved)
            if data:
                merged = _deep_merge(merged, data)

    return merged


def _config_file_signature(path: str | None) -> tuple[int, int] | None:
    """返回配置文件签名：(mtime_ns, size)。"""
    if not path or not os.path.isfile(path):
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _all_files_signature(settings_path: str | None = None) -> tuple[tuple[str, int, int], ...] | None:
    """计算所有 YAML 文件的聚合签名（用于缓存失效检测）。"""
    sigs: list[tuple[str, int, int]] = []
    project_dir = str(_PROJECT_ROOT)

    for name, search_paths in _YAML_FILES:
        if name == "settings" and settings_path:
            resolved = os.path.abspath(settings_path)
        else:
            resolved = None
            for rel in search_paths:
                full = os.path.join(project_dir, rel) if not os.path.isabs(rel) else rel
                if os.path.isfile(full):
                    resolved = full
                    break
        if resolved:
            sig = _config_file_signature(resolved)
            if sig:
                sigs.append((resolved, sig[0], sig[1]))

    return tuple(sigs) if sigs else None


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def load_yaml_config(config_path: str = "") -> YamlConfig:
    """从 YAML 文件加载运行配置。文件不存在或解析失败返回空字典。

    向后兼容：原 API 仅加载 settings.yaml。现在加载所有文件并合并。
    """
    return _load_all_yamls(config_path or None)


def get_yaml_config(config_path: str = "") -> YamlConfig:
    """获取 YAML 配置（带多文件缓存）。

    缓存基于所有 YAML 文件的聚合签名，任一文件变化即触发重载。
    """
    cache_attr = "_yaml_config_cache"
    settings_path = (
        os.path.abspath(config_path) if config_path else _resolve_yaml_path()
    )
    cache_key = settings_path or "__missing__"
    signature = _all_files_signature(settings_path)
    cache = getattr(get_yaml_config, cache_attr, {})  # type: ignore[attr-defined]
    cached_entry = cache.get(cache_key)
    if isinstance(cached_entry, dict):
        if cached_entry.get("signature") == signature and isinstance(
            cached_entry.get("data"), dict
        ):
            return cached_entry["data"]
    data = _load_all_yamls(settings_path)
    cache[cache_key] = {
        "path": settings_path,
        "signature": signature,
        "data": data,
    }
    setattr(get_yaml_config, cache_attr, cache)
    return data


def load_constants_yaml() -> YamlConfig:
    """仅加载 constants_defaults.yaml，返回其内容。

    用于 constants.py 初始化时的代码常量读取。
    """
    project_dir = str(_PROJECT_ROOT)
    for name, search_paths in _YAML_FILES:
        if name == "constants_defaults":
            for rel in search_paths:
                full = os.path.join(project_dir, rel) if not os.path.isabs(rel) else rel
                if os.path.isfile(full):
                    return _load_yaml_file(full)
            break
    return {}
