"""
统一配置管理器
提供一致的配置访问接口，支持多来源配置合并、优先级控制、类型安全的配置访问、
配置验证和schema检查、热重载支持、性能优化缓存和配置变更通知。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Set, Union, cast

import yaml

from .schema import ConfigSchema
from .types import ConfigSource, YamlConfig
from .yaml_sources import (
    DEFAULT_CONFIG_NAMES,
    YAML_FILES,
    all_files_signature,
    deep_merge,
    load_all_yamls,
    resolve_all_yaml_files,
)


@dataclass(frozen=True)
class ConfigValue:
    """配置值封装，包含来源和元数据"""
    value: Any
    source: ConfigSource
    timestamp: float
    path: Optional[str] = None
    validated: bool = False

    def __str__(self) -> str:
        source_name = self.source.value.replace("_", " ").title()
        if self.path:
            return f"{self.value} (from {source_name}: {self.path})"
        return f"{self.value} (from {source_name})"


@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    key: str
    old_value: Optional[ConfigValue]
    new_value: ConfigValue
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        old_val = str(old_value.value) if (old_value := self.old_value) else "None"
        new_val = str(self.new_value.value)
        return f"Config changed: {self.key} = {old_val} -> {new_val}"


class UnifiedConfigManager:
    """
    统一配置管理器
    提供一致的配置访问接口
    """

    _instance: Optional[UnifiedConfigManager] = None
    _lock = threading.RLock()

    def __new__(cls, project_root: Optional[Union[str, Path]] = None) -> UnifiedConfigManager:
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例实例（用于测试）"""
        with cls._lock:
            cls._instance = None

    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        """初始化配置管理器"""
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent.parent.parent
        self.config_dir = self.project_root / "config"

        self._config_by_source: Dict[ConfigSource, Dict[str, Any]] = {}
        self._merged_config: Dict[str, Any] = {}
        self._cached_values: Dict[str, ConfigValue] = {}

        self._change_listeners: List[Callable[[ConfigChangeEvent], None]] = []

        self._schema: Optional[ConfigSchema] = None

        self._last_signature: Optional[tuple] = None
        self._last_merge_time: float = 0

        self._initialize_sources()

        self.reload()

        self._initialized = True

    def _initialize_sources(self) -> None:
        """初始化所有配置源"""
        for source in ConfigSource:
            if source not in self._config_by_source:
                self._config_by_source[source] = {}

    def reload(self, force: bool = False) -> None:
        """重新加载所有配置"""
        with self._lock:
            current_signature = self._get_config_files_signature()
            if not force and current_signature == self._last_signature:
                return

            self._config_by_source.clear()
            self._cached_values.clear()
            self._initialize_sources()

            self._load_yaml_configs()

            self._load_code_constants()

            self._merge_all_configs()

            self._validate_configs()

            self._last_signature = current_signature
            self._last_merge_time = time.time()

    def _load_yaml_configs(self) -> None:
        """加载所有YAML配置文件"""
        for name, search_paths in YAML_FILES:
            for rel_path in search_paths:
                file_path = self.config_dir / rel_path.split('/')[-1]
                if file_path.exists():
                    try:
                        with open(file_path, encoding='utf-8') as f:
                            config_data = yaml.safe_load(f) or {}

                        source = ConfigSource.from_yaml_name(name)
                        if source:
                            self._config_by_source[source] = config_data
                            print(f"Loaded config from {file_path}")
                    except Exception as e:
                        print(f"Error loading {file_path}: {e}")
                    break
            else:
                print(f"Warning: Config file not found for {name}")

    def _load_code_constants(self) -> None:
        """加载代码常量"""
        try:
            from . import constants as config_constants

            code_constants = {}
            for attr_name in dir(config_constants):
                if not attr_name.startswith("_"):
                    attr_value = getattr(config_constants, attr_name)
                    if not callable(attr_value):
                        if isinstance(attr_value, (int, float, str, bool, list, dict)):
                            code_constants[attr_name] = attr_value

            self._config_by_source[ConfigSource.CODE_CONSTANTS] = code_constants

        except ImportError as e:
            print(f"Warning: Failed to load code constants: {e}")

    def _merge_all_configs(self) -> None:
        """合并所有配置源，按优先级从低到高"""
        self._merged_config = {}

        sorted_sources = sorted(ConfigSource, key=lambda s: s.priority)

        for source in sorted_sources:
            source_config = self._config_by_source.get(source, {})
            if source_config:
                self._merged_config = deep_merge(self._merged_config, source_config)

    def _validate_configs(self) -> None:
        """验证配置数据"""
        if not self._schema:
            return

        for source, config in self._config_by_source.items():
            if config:
                errors = self._schema.validate(config, source)
                if errors:
                    print(f"Config validation errors from {source.value}:")
                    for error in errors:
                        print(f"  - {error}")

    def set_schema(self, schema_def: Union[Dict[str, Any], ConfigSchema]) -> None:
        """设置配置schema"""
        with self._lock:
            if isinstance(schema_def, ConfigSchema):
                self._schema = schema_def
            else:
                self._schema = ConfigSchema(schema_def)
            self._validate_configs()

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self._lock:
            if key in self._cached_values:
                return self._cached_values[key].value

            value = self._get_nested_value(self._merged_config, key)
            if value is None:
                return default

            source = self._find_source(key, value)

            config_value = ConfigValue(
                value=value,
                source=source,
                timestamp=time.time()
            )
            self._cached_values[key] = config_value

            return value

    def get_with_metadata(self, key: str) -> Optional[ConfigValue]:
        """获取配置值及其元数据"""
        with self._lock:
            if key in self._cached_values:
                return self._cached_values[key]

            value = self._get_nested_value(self._merged_config, key)
            if value is None:
                return None

            source = self._find_source(key, value)

            config_value = ConfigValue(
                value=value,
                source=source,
                timestamp=time.time()
            )
            self._cached_values[key] = config_value

            return config_value

    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.RUNTIME_OVERRIDE) -> None:
        """设置配置值"""
        with self._lock:
            old_value = self.get_with_metadata(key)

            self._set_nested_value(self._config_by_source[source], key, value)

            self._merge_all_configs()

            new_value = ConfigValue(
                value=value,
                source=source,
                timestamp=time.time()
            )
            self._cached_values[key] = new_value

            event = ConfigChangeEvent(
                key=key,
                old_value=old_value,
                new_value=new_value
            )
            self._notify_listeners(event)

    def set_command_line_args(self, args: Dict[str, Any]) -> None:
        """设置命令行参数"""
        self._config_by_source[ConfigSource.COMMAND_LINE] = args
        self._merge_all_configs()
        self._cached_values.clear()

    def get_source_for_key(self, key: str) -> Optional[ConfigSource]:
        """获取配置键的来源"""
        with self._lock:
            config_value = self.get_with_metadata(key)
            return config_value.source if config_value else None

    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """获取嵌套配置值"""
        keys = key.split('.')
        value = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value

    def _set_nested_value(self, config: Dict[str, Any], key: str, value: Any) -> None:
        """设置嵌套配置值"""
        keys = key.split('.')
        for _i, k in enumerate(keys[:-1]):
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def _find_source(self, key: str, value: Any) -> ConfigSource:
        """查找配置值的来源"""
        sorted_sources = sorted(ConfigSource, key=lambda s: s.priority, reverse=True)

        for source in sorted_sources:
            source_config = self._config_by_source.get(source, {})
            source_value = self._get_nested_value(source_config, key)
            if source_value is not None:
                return source

        return ConfigSource.CODE_CONSTANTS

    def add_change_listener(self, listener: Callable[[ConfigChangeEvent], None]) -> None:
        """添加配置变更监听器"""
        with self._lock:
            if listener not in self._change_listeners:
                self._change_listeners.append(listener)

    def remove_change_listener(self, listener: Callable[[ConfigChangeEvent], None]) -> None:
        """移除配置变更监听器"""
        with self._lock:
            if listener in self._change_listeners:
                self._change_listeners.remove(listener)

    def _notify_listeners(self, event: ConfigChangeEvent) -> None:
        """通知所有配置变更监听器"""
        for listener in self._change_listeners:
            try:
                listener(event)
            except Exception as e:
                print(f"Error in config change listener: {e}")

    def get_all_sources(self) -> Dict[ConfigSource, Dict[str, Any]]:
        """获取所有配置源"""
        with self._lock:
            return {k: v.copy() for k, v in self._config_by_source.items()}

    def get_merged_config(self) -> Dict[str, Any]:
        """获取合并后的完整配置"""
        with self._lock:
            return self._merged_config.copy()

    def export_to_yaml(self, path: Union[str, Path]) -> None:
        """导出合并后的配置到YAML文件"""
        with self._lock:
            def convert_to_yaml_safe(obj):
                if isinstance(obj, dict):
                    return {k: convert_to_yaml_safe(v) for k, v in obj.items()}
                elif isinstance(obj, (tuple, frozenset, set, list)):
                    return [convert_to_yaml_safe(item) for item in obj]
                else:
                    return obj

            config_for_export = convert_to_yaml_safe(self._merged_config)
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(config_for_export, f, default_flow_style=False, allow_unicode=True)

    def _get_config_files_signature(self) -> Optional[tuple]:
        """获取配置文件签名，用于检测文件变化"""
        try:
            files = list(self.config_dir.glob('*.yaml')) + list(self.config_dir.glob('*.yml'))
            sigs = [(f.name, f.stat().st_mtime) for f in files if f.is_file()]
            return tuple(sorted(sigs)) if sigs else None
        except Exception as e:
            print(f"Error getting config files signature: {e}")
            return None

    def __contains__(self, key: str) -> bool:
        """检查配置键是否存在"""
        return self.get(key) is not None

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问"""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        """支持字典式设置"""
        self.set(key, value)

    def __len__(self) -> int:
        """返回配置项数量"""
        return len(self._merged_config)

    def __iter__(self):
        """支持迭代"""
        return iter(self._merged_config)


def get_config_manager(project_root: Optional[Union[str, Path]] = None) -> UnifiedConfigManager:
    """获取配置管理器单例"""
    return UnifiedConfigManager(project_root)


def get_config(key: str, default: Any = None) -> Any:
    """快捷函数：获取配置值"""
    return get_config_manager().get(key, default)


def set_config(key: str, value: Any) -> None:
    """快捷函数：设置配置值"""
    get_config_manager().set(key, value)


def reload_config() -> None:
    """快捷函数：重新加载配置"""
    get_config_manager().reload()


_config_manager: Optional[UnifiedConfigManager] = None


def init_config_manager(project_root: Optional[Union[str, Path]] = None) -> UnifiedConfigManager:
    """初始化配置管理器（用于测试）"""
    global _config_manager
    _config_manager = UnifiedConfigManager(project_root)
    return _config_manager
