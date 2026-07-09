"""
策略与规则模块。

集中管理所有策略相关逻辑：
- expression: 数据集表达式策略构建与反馈阶段解析
- blacklist_runtime: 黑名单运行态聚合与自动更新规则
- blacklist_store: 黑名单文件存取与缓存失效
- template_blacklist: 模板黑名单匹配策略
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .blacklist_runtime import (
        auto_update_blacklist,
        auto_update_blacklist_incremental,
        build_blacklist_runtime_stats,
    )
    from .blacklist_store import (
        ensure_template_blacklist_file,
        invalidate_blacklist_path_cache,
        load_blacklisted_template_keys,
        load_blacklisted_template_names,
    )
    from .expression import (
        get_dataset_expression_policy,
        resolve_feedback_stage,
        use_curated_heuristics_for_dataset,
        use_fundamental6_heuristics,
    )

_EXPORT_MAP: ExportMap = {
    "auto_update_blacklist": (".blacklist_runtime", "auto_update_blacklist"),
    "auto_update_blacklist_incremental": (".blacklist_runtime", "auto_update_blacklist_incremental"),
    "build_blacklist_runtime_stats": (".blacklist_runtime", "build_blacklist_runtime_stats"),
    "ensure_template_blacklist_file": (".blacklist_store", "ensure_template_blacklist_file"),
    "get_dataset_expression_policy": (".expression", "get_dataset_expression_policy"),
    "load_blacklisted_template_keys": (".blacklist_store", "load_blacklisted_template_keys"),
    "invalidate_blacklist_path_cache": (".blacklist_store", "invalidate_blacklist_path_cache"),
    "load_blacklisted_template_names": (".blacklist_store", "load_blacklisted_template_names"),
    "resolve_feedback_stage": (".expression", "resolve_feedback_stage"),
    "use_curated_heuristics_for_dataset": (".expression", "use_curated_heuristics_for_dataset"),
    "use_fundamental6_heuristics": (".expression", "use_fundamental6_heuristics"),
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
