"""
分析与优化包

负责结果统计分析和历史反馈迭代优化。

子模块：
    - results_loader: 历史结果加载与 journal 恢复
    - result_identity: 结果身份、续跑去重与有效反馈判断
    - template_stats: 模板统计与历史优先级
    - field_stats: 字段统计与字段优先级
    - failed_checks: 失败检查评分、near-pass 与优化建议
    - feedback_stats: 字段反馈画像与全局失败检查计数
    - feedback_history: 历史反馈状态与 near-pass 选择
    - feedback_filters: 模板剪枝策略
    - report_builder: 结果分析报告构建
    - analysis_sync: 分析边车文件同步
"""

from __future__ import annotations

from .analysis_sync import ensure_analysis_synced
from .failed_checks import (
    compile_failed_check_leaderboard,
    compile_near_pass_summary,
    compile_optimization_hints,
    failed_check_closeness,
    failed_check_gap,
    score_failed_checks,
    summarize_failed_check,
)
from .feedback_filters import (
    is_legacy_family_disabled,
    is_template_disabled,
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)
from .feedback_history import (
    build_historical_run_state,
    choose_settings_variant_budget,
    select_nearpass_candidates,
    should_stop_after_submittable,
)
from .feedback_stats import (
    compile_field_feedback,
    compile_global_failed_check_counts,
    dominant_failed_check_names,
    merge_failed_check_counts,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from .field_stats import compile_field_performance_summary, current_submittable_count, field_priority
from .result_identity import attempted_template_keys, is_informative_result, result_identity
from .results_loader import load_existing_results
from .template_stats import (
    compile_template_performance_summary,
    compile_template_stats,
    historical_template_priority_bonus,
    update_template_stats_with_result,
)

__all__ = [
    "attempted_template_keys",
    "choose_settings_variant_budget",
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
    "ensure_analysis_synced",
    "failed_check_closeness",
    "failed_check_gap",
    "field_priority",
    "historical_template_priority_bonus",
    "is_informative_result",
    "is_legacy_family_disabled",
    "is_template_disabled",
    "load_existing_results",
    "merge_failed_check_counts",
    "result_identity",
    "score_failed_checks",
    "select_nearpass_candidates",
    "should_keep_template_for_feedback",
    "should_skip_field_template_family",
    "should_stop_after_submittable",
    "summarize_failed_check",
    "update_field_feedback_with_result",
    "update_global_failed_check_counts_with_result",
    "update_template_stats_with_result",
]
