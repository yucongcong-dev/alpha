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

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
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
    from .template_registry_rules import (
        compile_template_registry_summary,
        normalize_activation_scope,
        normalize_template_role,
        recommend_template_role_transition,
    )
    from .template_stats import (
        compile_template_performance_summary,
        compile_template_stats,
        historical_template_priority_bonus,
        update_template_stats_with_result,
    )

_EXPORT_MAP: ExportMap = {
    "ensure_analysis_synced": (".analysis_sync", "ensure_analysis_synced"),
    "compile_failed_check_leaderboard": (".failed_checks", "compile_failed_check_leaderboard"),
    "compile_near_pass_summary": (".failed_checks", "compile_near_pass_summary"),
    "compile_optimization_hints": (".failed_checks", "compile_optimization_hints"),
    "failed_check_closeness": (".failed_checks", "failed_check_closeness"),
    "failed_check_gap": (".failed_checks", "failed_check_gap"),
    "score_failed_checks": (".failed_checks", "score_failed_checks"),
    "summarize_failed_check": (".failed_checks", "summarize_failed_check"),
    "is_legacy_family_disabled": (".feedback_filters", "is_legacy_family_disabled"),
    "is_template_disabled": (".feedback_filters", "is_template_disabled"),
    "should_keep_template_for_feedback": (".feedback_filters", "should_keep_template_for_feedback"),
    "should_skip_field_template_family": (".feedback_filters", "should_skip_field_template_family"),
    "build_historical_run_state": (".feedback_history", "build_historical_run_state"),
    "choose_settings_variant_budget": (".feedback_history", "choose_settings_variant_budget"),
    "select_nearpass_candidates": (".feedback_history", "select_nearpass_candidates"),
    "should_stop_after_submittable": (".feedback_history", "should_stop_after_submittable"),
    "compile_field_feedback": (".feedback_stats", "compile_field_feedback"),
    "compile_global_failed_check_counts": (".feedback_stats", "compile_global_failed_check_counts"),
    "dominant_failed_check_names": (".feedback_stats", "dominant_failed_check_names"),
    "merge_failed_check_counts": (".feedback_stats", "merge_failed_check_counts"),
    "update_field_feedback_with_result": (".feedback_stats", "update_field_feedback_with_result"),
    "update_global_failed_check_counts_with_result": (".feedback_stats", "update_global_failed_check_counts_with_result"),
    "compile_field_performance_summary": (".field_stats", "compile_field_performance_summary"),
    "current_submittable_count": (".field_stats", "current_submittable_count"),
    "field_priority": (".field_stats", "field_priority"),
    "attempted_template_keys": (".result_identity", "attempted_template_keys"),
    "is_informative_result": (".result_identity", "is_informative_result"),
    "result_identity": (".result_identity", "result_identity"),
    "load_existing_results": (".results_loader", "load_existing_results"),
    "compile_template_registry_summary": (".template_registry_rules", "compile_template_registry_summary"),
    "normalize_activation_scope": (".template_registry_rules", "normalize_activation_scope"),
    "normalize_template_role": (".template_registry_rules", "normalize_template_role"),
    "recommend_template_role_transition": (".template_registry_rules", "recommend_template_role_transition"),
    "compile_template_performance_summary": (".template_stats", "compile_template_performance_summary"),
    "compile_template_stats": (".template_stats", "compile_template_stats"),
    "historical_template_priority_bonus": (".template_stats", "historical_template_priority_bonus"),
    "update_template_stats_with_result": (".template_stats", "update_template_stats_with_result"),
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
