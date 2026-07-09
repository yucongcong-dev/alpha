"""
Alpha 生成器包

负责 Alpha 表达式的生成、模板管理、字段管理和参数配置。

设计说明：
    generators 对 policy 存在合理的编译期依赖——表达式候选的构建、
    黑名单过滤和优先级调整均需要数据集策略输入。此依赖方向
    (generators → policy) 符合分层原则，无需注入解耦。

子模块：
    - templates: 模板库管理
    - expression_builder: 表达式候选构建
    - matrix_templates: MATRIX 字段模板生成
    - ratio_templates: Ratio 字段模板生成
    - fields: 字段缓存与配对发现
    - field_transforms: 字段预处理与变换
    - fingerprint: 稳定指纹生成
    - payload: 模拟请求体构建
    - variants: settings 变体构建
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .expression_builder import build_expression_candidates, limit_templates, sort_templates_by_priority
    from .fields import choose_field_name, choose_field_type
    from .fingerprint import stable_fingerprint
    from .payload import build_settings_fingerprint, build_simulation_payload
    from .templates import ensure_dataset_template_library, load_template_library
    from .variants import build_setting_variants

_EXPORT_MAP: ExportMap = {
    "build_expression_candidates": (".expression_builder", "build_expression_candidates"),
    "limit_templates": (".expression_builder", "limit_templates"),
    "sort_templates_by_priority": (".expression_builder", "sort_templates_by_priority"),
    "choose_field_name": (".fields", "choose_field_name"),
    "choose_field_type": (".fields", "choose_field_type"),
    "stable_fingerprint": (".fingerprint", "stable_fingerprint"),
    "build_settings_fingerprint": (".payload", "build_settings_fingerprint"),
    "build_simulation_payload": (".payload", "build_simulation_payload"),
    "ensure_dataset_template_library": (".templates", "ensure_dataset_template_library"),
    "load_template_library": (".templates", "load_template_library"),
    "build_setting_variants": (".variants", "build_setting_variants"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str) -> object:
    return resolve_export(
        name=name,
        export_map=_EXPORT_MAP,
        package=__package__ or "",
        namespace=__name__,
        target_globals=globals(),
    )


def __dir__() -> list[str]:
    return facade_dir(globals(), _EXPORT_MAP)
