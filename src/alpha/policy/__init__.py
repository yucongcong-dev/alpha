"""
策略与规则模块。

集中管理所有策略相关逻辑：
- expression: 数据集表达式策略构建与反馈阶段解析
- blacklist_store: 黑名单文件存取与缓存失效
- template_blacklist: 模板黑名单匹配策略
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .blacklist_store import (
        ensure_template_blacklist_file,
        invalidate_blacklist_path_cache,
    )
    from .expression import (
        get_dataset_expression_policy,
        resolve_feedback_stage,
        use_curated_heuristics_for_dataset,
    )

_EXPORT_MAP: ExportMap = {
    "ensure_template_blacklist_file": (".blacklist_store", "ensure_template_blacklist_file"),
    "get_dataset_expression_policy": (".expression", "get_dataset_expression_policy"),
    "invalidate_blacklist_path_cache": (".blacklist_store", "invalidate_blacklist_path_cache"),
    "resolve_feedback_stage": (".expression", "resolve_feedback_stage"),
    "use_curated_heuristics_for_dataset": (".expression", "use_curated_heuristics_for_dataset"),
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
