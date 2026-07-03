"""结果分析统计兼容出口。

真实实现已按职责拆分到 analysis 子模块：
- results_loader: 历史结果加载与 journal 恢复
- result_identity: 结果身份、续跑去重与有效反馈判断
- template_stats: 模板统计与历史优先级
- field_stats: 字段统计与字段优先级
- failed_checks: 失败检查评分、near-pass 与优化建议
- feedback_stats: 字段反馈画像与全局失败检查计数

.. deprecated:: 1.0.0
    This module is a compatibility facade. Import from the specific module
    instead: ``alpha.analysis.results_loader``, ``alpha.analysis.result_identity``,
    ``alpha.analysis.template_stats``, ``alpha.analysis.field_stats``,
    ``alpha.analysis.failed_checks``, ``alpha.analysis.feedback_stats``.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "alpha.analysis.stats is deprecated. Import from specific modules instead: "
    "alpha.analysis.results_loader, alpha.analysis.result_identity, "
    "alpha.analysis.template_stats, alpha.analysis.field_stats, "
    "alpha.analysis.failed_checks, alpha.analysis.feedback_stats.",
    DeprecationWarning,
    stacklevel=2,
)

from .failed_checks import (
    compile_failed_check_leaderboard,
    compile_near_pass_summary,
    compile_optimization_hints,
    failed_check_closeness,
    failed_check_gap,
    score_failed_checks,
    summarize_failed_check,
)
from .feedback_stats import (
    compile_field_feedback,
    compile_global_failed_check_counts,
    dominant_failed_check_names,
    merge_failed_check_counts,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from .field_stats import (
    compile_field_performance_summary,
    current_submittable_count,
    field_priority,
)
from .result_identity import (
    attempted_template_keys,
    is_informative_result,
    is_queue_timeout_result,
    result_identity,
)
from .results_loader import (
    _default_results_journal_path,
    _load_results_rows_from_journal,
    _recover_results_from_journal,
    _rows_to_results,
    load_existing_results,
)
from .template_stats import (
    compile_template_performance_summary,
    compile_template_stats,
    historical_template_priority_bonus,
    update_template_stats_with_result,
)

__all__ = [
    "_default_results_journal_path",
    "_load_results_rows_from_journal",
    "_recover_results_from_journal",
    "_rows_to_results",
    "attempted_template_keys",
    "compile_failed_check_leaderboard",
    "compile_field_feedback",
    "compile_field_performance_summary",
    "compile_global_failed_check_counts",
    "compile_near_pass_summary",
    "compile_optimization_hints",
    "compile_template_performance_summary",
    "compile_template_stats",
    "current_submittable_count",
    "dominant_failed_check_names",
    "failed_check_closeness",
    "failed_check_gap",
    "field_priority",
    "historical_template_priority_bonus",
    "is_informative_result",
    "is_queue_timeout_result",
    "load_existing_results",
    "merge_failed_check_counts",
    "result_identity",
    "score_failed_checks",
    "summarize_failed_check",
    "update_field_feedback_with_result",
    "update_global_failed_check_counts_with_result",
    "update_template_stats_with_result",
]
