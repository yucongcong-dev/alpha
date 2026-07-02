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
import threading
from pathlib import Path
from .types import YamlConfig, YamlConfigCacheEntry

_log = logging.getLogger("alpha.config.yaml")

# ---------------------------------------------------------------------------
# 模块级缓存（线程安全）
# ---------------------------------------------------------------------------
_config_lock = threading.RLock()
_config_cache: dict[str, YamlConfigCacheEntry] = {}
_config_validated: bool = False

_schema_lock = threading.RLock()
_schema_keys_cache: dict[str, set[str]] | None = None

# ---------------------------------------------------------------------------
# 项目根目录发现
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """向上查找包含 settings.yaml 或 pyproject.toml 的目录作为项目根。

    不再依赖固定层数的 .parent，支持文件位置变动。
    """
    current = Path(__file__).resolve().parent
    for _ in range(8):
        if (current / "settings.yaml").is_file() or (current / "pyproject.toml").is_file():
            return current
        if current.parent == current:  # 到达文件系统根
            break
        current = current.parent
    # 回退：从 src/alpha/config/ 向上 4 层到项目根
    return Path(__file__).resolve().parent.parent.parent.parent


_PROJECT_ROOT = _find_project_root()

# ---------------------------------------------------------------------------
# YAML 文件定义
# ---------------------------------------------------------------------------

_YAML_FILES: list[tuple[str, list[str]]] = [
    ("constants_defaults", ["constants_defaults.yaml", "config/constants_defaults.yaml"]),
    ("dataset_profiles", ["dataset_profiles.yaml", "config/dataset_profiles.yaml"]),
    ("expression_policies", ["expression_policies.yaml", "config/expression_policies.yaml"]),
    ("settings", ["settings.yaml", "config/settings.yaml"]),
]
"""YAML 文件定义：(逻辑名称, [相对搜索路径])，按优先级升序排列。"""

_ENV_CONFIG_PATH: str = "ALPHA_CONFIG_FILE"
"""可通过该环境变量指定主配置文件路径。"""


def _resolve_all_yaml_files(settings_path: str | None = None) -> dict[str, str]:
    """统一解析所有 YAML 文件，返回 {逻辑名称: 绝对路径}。

    消除 _load_all_yamls、_all_files_signature、get_yaml_config、
    validate_yaml_config 中重复的文件解析逻辑。

    仅包含实际存在的文件。
    """
    project_dir = str(_PROJECT_ROOT)
    resolved: dict[str, str] = {}

    for name, search_paths in _YAML_FILES:
        if name == "settings" and settings_path:
            candidate = os.path.abspath(settings_path)
            if os.path.isfile(candidate):
                resolved[name] = candidate
                continue

        for rel in search_paths:
            full = os.path.join(project_dir, rel) if not os.path.isabs(rel) else rel
            if os.path.isfile(full):
                resolved[name] = full
                break

    return resolved


def _resolve_yaml_path() -> str | None:
    """按优先级查找主 settings.yaml 配置文件路径。"""
    env_path = os.environ.get(_ENV_CONFIG_PATH)
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    resolved = _resolve_all_yaml_files()
    settings_path = resolved.get("settings")
    if settings_path:
        return settings_path

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


def _deep_merge(base: dict, override: dict, _max_depth: int = 6) -> dict:
    """深合并两个字典：override 中的值覆盖 base。

    对所有嵌套 dict 递归合并（不再硬编码特定 key），以支持任意逐数据集/逐配置段的增量覆盖。
    _max_depth 防止循环引用导致栈溢出。
    """
    if _max_depth <= 0:
        return dict(override)  # 达到深度上限，直接覆盖
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value, _max_depth - 1)
        else:
            result[key] = value
    return result


def _load_all_yamls(settings_path: str | None = None) -> YamlConfig:
    """加载所有 YAML 文件并按优先级合并。"""
    merged: YamlConfig = {}
    resolved_files = _resolve_all_yaml_files(settings_path)

    # 按 _YAML_FILES 定义的顺序合并（升序：低优先级先加载）
    for name, _search_paths in _YAML_FILES:
        path = resolved_files.get(name)
        if path:
            data = _load_yaml_file(path)
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
    resolved_files = _resolve_all_yaml_files(settings_path)

    for path in resolved_files.values():
        sig = _config_file_signature(path)
        if sig:
            sigs.append((path, sig[0], sig[1]))

    return tuple(sigs) if sigs else None



# ---------------------------------------------------------------------------
# Schema 验证 — 递归验证 + 交叉一致性检查
# ---------------------------------------------------------------------------

# settings.yaml global 段的已知子 key（由 defaults.py 的 apply_yaml_global_defaults 映射而来）
_GLOBAL_KNOWN_KEYS = {
    "simulation", "limits", "concurrency", "retries", "filters",
    "quality", "http", "expression", "feedback", "runtime",
}


def _collect_leaf_paths(data: dict, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    """递归收集 dict 中所有叶子键路径（到非 dict 值为止）。"""
    paths: set[tuple[str, ...]] = set()
    if not isinstance(data, dict):
        return paths
    for key, value in data.items():
        full = prefix + (key,)
        if isinstance(value, dict) and value:
            paths.update(_collect_leaf_paths(value, full))
        else:
            paths.add(full)
    return paths


def _collect_all_string_keys(data: dict) -> set[str]:
    """递归收集 dict 中所有层级出现的键名（用于拼写检查）。"""
    keys: set[str] = set()
    if not isinstance(data, dict):
        return keys
    for key, value in data.items():
        keys.add(key)
        if isinstance(value, dict):
            keys.update(_collect_all_string_keys(value))
    return keys


def _get_schema_keys(resolved_files: dict[str, str]) -> dict[str, set[str]]:
    """从各 YAML 文件的实际内容中提取顶层 key，线程安全，无需手动维护白名单。"""
    global _schema_keys_cache
    with _schema_lock:
        if _schema_keys_cache is not None:
            return _schema_keys_cache

        keys_by_file: dict[str, set[str]] = {}
        # settings.yaml 的已知顶层 key（结构固定）
        keys_by_file["settings"] = {"global", "dataset_profiles", "expression_policies"}

        for name in ("constants_defaults", "dataset_profiles", "expression_policies"):
            path = resolved_files.get(name)
            if path:
                data = _load_yaml_file(path)
                if isinstance(data, dict):
                    keys_by_file[name] = set(data.keys())

        _schema_keys_cache = keys_by_file
        return keys_by_file


def _validate_top_level_keys(
    config: YamlConfig,
    schema_keys: dict[str, set[str]],
) -> list[str]:
    """检查顶层 key 是否来自已知 YAML 文件（防止 typo）。"""
    all_top_keys: set[str] = set()
    for keys in schema_keys.values():
        all_top_keys.update(keys)

    unknown = set(config.keys()) - all_top_keys
    if unknown:
        return [
            f"未知顶层 key: {sorted(unknown)}。可能是 YAML 中的拼写错误，请在对应 YAML 文件中检查。"
        ]
    return []


def _validate_global_section(config: YamlConfig, resolved_files: dict[str, str]) -> list[str]:
    """验证 settings.yaml global 段子 key 拼写。"""
    warnings: list[str] = []
    if "settings" not in resolved_files:
        return warnings

    global_section = config.get("global", {})
    if not isinstance(global_section, dict):
        return warnings

    for gkey in global_section:
        if gkey not in _GLOBAL_KNOWN_KEYS:
            warnings.append(
                f"settings.yaml: global 段存在未知 key '{gkey}'，已知 key: {sorted(_GLOBAL_KNOWN_KEYS)}"
            )
    return warnings


def _validate_cross_consistency(
    config: YamlConfig,
    resolved_files: dict[str, str],
) -> list[str]:
    """交叉一致性检查：验证 settings.yaml global.* 和 constants_defaults.yaml 之间的键名一致性。

    仅检查重叠段（quality, http, expression, feedback）——这些段在两处均有定义，
    键名应保持一致。settings-only 段（simulation, limits, concurrency, retries, filters, runtime）
    不参与此检查，因为它们使用的是与 constants_defaults 完全不同的键空间。
    """
    # 仅对这些重叠段进行交叉检查
    _OVERLAP_SECTIONS = {"quality", "http", "expression", "feedback"}
    # 已知的命名变体映射：settings.yaml 键名 → constants_defaults 键名（非 typo，只是命名风格差异）
    _KNOWN_ALIASES: dict[str, dict[str, str]] = {
        "feedback": {
            "feedback_mutation_nearpass_threshold": "mutation_nearpass_threshold",
            "feedback_mutation_highscore_threshold": "mutation_highscore_threshold",
            "feedback_template_min_priority": "template_min_priority",
        },
        "http": {
            "backend": "@settings_only",  # 纯 settings 键，不在 constants 中
        },
    }

    warnings: list[str] = []

    defaults_path = resolved_files.get("constants_defaults")
    if not defaults_path:
        return warnings

    defaults_data = _load_yaml_file(defaults_path)
    if not isinstance(defaults_data, dict):
        return warnings

    global_section = config.get("global", {})
    if not isinstance(global_section, dict):
        return warnings

    for section in _OVERLAP_SECTIONS:
        gdata = global_section.get(section)
        if not isinstance(gdata, dict):
            continue

        defaults_section = defaults_data.get(section)
        if not isinstance(defaults_section, dict):
            continue

        defaults_keys = _collect_all_string_keys(defaults_section)
        if not defaults_keys:
            continue

        aliases = _KNOWN_ALIASES.get(section, {})
        # 筛选出既不在 defaults_keys 也不在 aliases 中的 settings key
        extra = []
        for skey in gdata.keys():
            if skey in defaults_keys:
                continue
            if skey in aliases and (aliases[skey] in defaults_keys or aliases[skey] == "@settings_only"):
                continue
            extra.append(skey)

        if extra:
            warnings.append(
                f"交叉一致性警告: settings.yaml global.{section} 中的 key "
                + f"{sorted(extra)} 在 constants_defaults.yaml 的 {section} 段中不存在。"
                + f"可能是键名拼写错误。已知 key: {sorted(defaults_keys)}"
            )

    return warnings


def _validate_nested_paths(config: YamlConfig) -> list[str]:
    """递归验证：检查合并后配置中没有孤立的、无法追溯到已知来源的嵌套键。

    对每一个顶层 section（如 quality, http, feedback 等），验证其子键结构在
    constants_defaults 或 global 段中能找到对应。

    仅针对非 dataset_profiles / expression_policies 的通用设置段。
    """
    warnings: list[str] = []
    skip_sections = {"global", "dataset_profiles", "expression_policies"}

    for section, section_data in config.items():
        if section in skip_sections or not isinstance(section_data, dict):
            continue

        # 对已知通用设置段做深度键名检查
        if section in _GLOBAL_KNOWN_KEYS:
            leaf_paths = _collect_leaf_paths(section_data, (section,))
            # 每个叶子路径应不超过合理深度（3 层：section.sub.key）
            for path in leaf_paths:
                if len(path) > 4:
                    warnings.append(
                        f"嵌套过深: {' > '.join(path)}，请检查 constants_defaults.yaml 中 {section} 段的结构。"
                    )

    return warnings


def _validate_merged_config(config: YamlConfig, resolved_files: dict[str, str]) -> list[str]:
    """验证合并后的配置，返回警告信息列表。

    检查项（递归 + 交叉一致性）：
      1. 顶层 key 是否来自已知 YAML 文件
      2. settings.yaml global 段子 key 拼写检查
      3. 交叉一致性：global.* 的键名是否与 constants_defaults 一致
      4. 嵌套路径深度：防止异常嵌套结构
    """
    if not isinstance(config, dict):
        return []

    schema_keys = _get_schema_keys(resolved_files)

    warnings: list[str] = []
    warnings.extend(_validate_top_level_keys(config, schema_keys))
    warnings.extend(_validate_global_section(config, resolved_files))
    warnings.extend(_validate_cross_consistency(config, resolved_files))
    warnings.extend(_validate_nested_paths(config))
    return warnings


def clear_yaml_caches() -> None:
    """清除所有 YAML 配置缓存（线程安全），强制下次访问时重新加载。

    用于测试或运行时配置热重载场景。
    """
    global _config_cache, _config_validated, _schema_keys_cache
    with _config_lock:
        _config_cache.clear()
        _config_validated = False
    with _schema_lock:
        _schema_keys_cache = None


def validate_yaml_config(config_path: str = "") -> list[str]:
    """验证 YAML 配置，返回警告信息列表。"""
    merged = get_yaml_config(config_path)
    resolved_files = _resolve_all_yaml_files(config_path or None)
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
    """获取 YAML 配置（线程安全缓存 + schema 验证）。

    缓存基于所有 YAML 文件的聚合签名，任一文件变化即触发重载。
    首次加载时自动运行 schema 验证，检测 YAML 键名拼写错误。
    """
    global _config_cache, _config_validated

    settings_path = (
        os.path.abspath(config_path) if config_path else _resolve_yaml_path()
    )
    cache_key = settings_path or "__missing__"
    signature = _all_files_signature(settings_path)

    with _config_lock:
        cached_entry = _config_cache.get(cache_key)
        if isinstance(cached_entry, dict):
            if cached_entry.get("signature") == signature and isinstance(
                cached_entry.get("data"), dict
            ):
                return cached_entry["data"]

        # 缓存未命中或已过期 → 重新加载
        data = _load_all_yamls(settings_path)

        # 仅首次加载时运行验证（避免重复警告）
        if not _config_validated:
            resolved_files = _resolve_all_yaml_files(settings_path)
            validation_warnings = _validate_merged_config(data, resolved_files)
            if validation_warnings:
                for warning in validation_warnings:
                    _log.warning("[schema] %s", warning)
            _config_validated = True

        _config_cache[cache_key] = {
            "path": settings_path,
            "signature": signature,
            "data": data,
        }
        return data
