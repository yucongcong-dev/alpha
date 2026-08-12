"""
YAML global 默认值合并。

本模块负责把合并 YAML 配置中的 global 配置应用到 argparse namespace。
声明式设置表见 ``config.settings_spec``，本模块只做通用遍历合并。
"""

from __future__ import annotations

from typing import Any, Protocol

from .settings_spec import yaml_default_settings

_MISSING = object()


class DefaultsTarget(Protocol):
    """支持按属性读写的配置承载对象。"""

    def __getattr__(self, name: str) -> object: ...

    def __setattr__(self, name: str, value: object) -> None: ...


def _assign_if_supported(
    target: DefaultsTarget,
    key: str,
    value: object,
    explicit_cli_keys: set[str],
) -> None:
    """仅在目标对象支持该属性且 CLI 未显式传参时写入值。"""
    if key in explicit_cli_keys or not hasattr(target, key):
        return
    setattr(target, key, value)


def _lookup_yaml_default(global_cfg: dict[str, Any], path: tuple[str, ...]) -> object:
    """沿 YAML 路径取 global 默认值；路径缺失或非 dict 时返回 _MISSING。"""
    section: Any = global_cfg
    for part in path[:-1]:
        if not isinstance(section, dict):
            return _MISSING
        section = section.get(part, {})
    if not isinstance(section, dict) or path[-1] not in section:
        return _MISSING
    return section[path[-1]]


def apply_yaml_global_defaults(
    args: DefaultsTarget,
    yaml_config: dict[str, Any] | None = None,
    explicit_cli_keys: set[str] | None = None,
) -> None:
    """将 YAML global 默认值应用到 argparse namespace 上（CLI 未显式传参时）。"""
    if not yaml_config:
        return
    explicit_cli_keys = explicit_cli_keys or set()

    global_cfg = yaml_config.get("global", {})
    if not isinstance(global_cfg, dict):
        return

    for spec in yaml_default_settings():
        assert spec.yaml is not None
        value = _lookup_yaml_default(global_cfg, spec.yaml)
        if value is not _MISSING:
            _assign_if_supported(args, spec.dest, value, explicit_cli_keys)
