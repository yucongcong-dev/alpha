"""
策略与规则模块。

集中管理所有策略相关逻辑：
- expression: 数据集表达式策略构建与反馈阶段解析
- blacklist: 模板黑名单管理
"""

from __future__ import annotations

from .blacklist import (
    auto_update_blacklist,
    auto_update_blacklist_incremental,
    build_blacklist_runtime_stats,
    ensure_template_blacklist_file,
    invalidate_blacklist_path_cache,
    load_blacklisted_template_names,
)
from .expression import (
    get_dataset_expression_policy,
    resolve_feedback_stage,
    use_curated_heuristics_for_dataset,
    use_fundamental6_heuristics,
)

__all__ = [
    "auto_update_blacklist",
    "auto_update_blacklist_incremental",
    "build_blacklist_runtime_stats",
    "ensure_template_blacklist_file",
    "get_dataset_expression_policy",
    "invalidate_blacklist_path_cache",
    "load_blacklisted_template_names",
    "resolve_feedback_stage",
    "use_curated_heuristics_for_dataset",
    "use_fundamental6_heuristics",
]