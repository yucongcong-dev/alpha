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

import logging
import os
from pathlib import Path
from typing import Optional

from .types import YamlConfig

_log = logging.getLogger("alpha.config.yaml")

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
# Schema 验证 — 配置加载时检测未知 key，帮助发现 YAML 拼写错误
# ---------------------------------------------------------------------------

# 各 YAML 文件中已知的顶层 key（每个文件各自的顶层 key 清单）
_KNOWN_TOP_KEYS: dict[str, set[str]] = {
    "constants_defaults": {
        "api", "checkpoint", "dataset_profiles", "default_profile", "expression",
        "failed_check", "feedback", "field", "http", "misc", "mutation",
        "nearpass", "partner", "paths", "quality", "ratio", "sentinel",
        "settings_variant", "simulation", "smoke_test", "stats", "strings", "templates",
    },
    "dataset_profiles": {"dataset_profiles"},
    "expression_policies": {"expression_policies"},
    "settings": {
        "global", "dataset_profiles", "expression_policies",
        # 注释行不产生实际 key，以下为 settings.yaml 顶层允许的 key
    },
}


def _validate_merged_config(config: YamlConfig, resolved_files: dict[str, str]) -> list[str]:
    """验证合并后的配置，返回警告信息列表。

    检查项：
      1. 顶层 key 是否为已知类型（防止 typo）
      2. 各文件专属 key 是否出现在正确文件中
    """
    warnings: list[str] = []
    if not isinstance(config, dict):
        return warnings

    # 收集所有已知顶层 key（从各文件合并而来）
    all_top_keys: set[str] = set()
    for keys in _KNOWN_TOP_KEYS.values():
        all_top_keys.update(keys)

    actual_keys = set(config.keys())

    # 1. 检查是否为有效顶层 key 的超集
    unknown = actual_keys - all_top_keys
    if unknown:
        # 某些 key 可能是运行时动态插入的（如 expression_policies 下层合并结果）
        # 仅对完全不在任何文件已知 key 中的 key 发出警告
        warnings.append(
            f"未知顶层 key: {sorted(unknown)}。"
            f"可能是 YAML 中的拼写错误，请在对应 YAML 文件中检查。"
        )

    # 2. 按文件验证：检查 settings.yaml 中是否存在拼写错误的 section
    settings_files = [
        name for name, _ in _YAML_FILES
        if name == "settings" and name in resolved_files
    ]
    if settings_files:
        # 对 settings.yaml 的顶层 key 进行深度结构检查
        global_section = config.get("global", {})
        if isinstance(global_section, dict):
            _global_known = {
                "simulation", "limits", "concurrency", "retries", "filters",
                "quality", "http", "expression", "feedback", "runtime",
            }
            for gkey in global_section:
                if gkey not in _global_known:
                    warnings.append(
                        f"settings.yaml: global 段存在未知 key '{gkey}'，"
                        f"已知 key: {sorted(_global_known)}"
                    )

    return warnings


def validate_yaml_config(config_path: str = "") -> list[str]:
    """验证 YAML 配置，返回警告信息列表。

    如有警告，建议检查对应 YAML 文件中的 key 拼写。
    返回空列表表示所有配置 key 均通过验证。
    """
    merged = get_yaml_config(config_path)
    # 收集实际加载的文件
    resolved_files: dict[str, str] = {}
    project_dir = str(_PROJECT_ROOT)
    for name, search_paths in _YAML_FILES:
        for rel in search_paths:
            full = os.path.join(project_dir, rel) if not os.path.isabs(rel) else rel
            if os.path.isfile(full):
                resolved_files[name] = full
                break
    return _validate_merged_config(merged, resolved_files)


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def load_yaml_config(config_path: str = "") -> YamlConfig:
    """从 YAML 文件加载运行配置。文件不存在或解析失败返回空字典。

    向后兼容：原 API 仅加载 settings.yaml。现在加载所有文件并合并。
    """
    return _load_all_yamls(config_path or None)


def get_yaml_config(config_path: str = "") -> YamlConfig:
    """获取 YAML 配置（带多文件缓存与 schema 验证）。

    缓存基于所有 YAML 文件的聚合签名，任一文件变化即触发重载。
    首次加载时自动运行 schema 验证，检测 YAML 键名拼写错误。
    """
    cache_attr = "_yaml_config_cache"
    validated_attr = "_yaml_config_validated"
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

    # 仅首次加载时运行验证（避免重复警告）
    if not getattr(get_yaml_config, validated_attr, False):
        resolved_files: dict[str, str] = {}
        project_dir = str(_PROJECT_ROOT)
        for name, search_paths in _YAML_FILES:
            for rel in search_paths:
                full = os.path.join(project_dir, rel) if not os.path.isabs(rel) else rel
                if os.path.isfile(full):
                    resolved_files[name] = full
                    break
        validation_warnings = _validate_merged_config(data, resolved_files)
        if validation_warnings:
            for warning in validation_warnings:
                _log.warning("[schema] %s", warning)
        setattr(get_yaml_config, validated_attr, True)

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
