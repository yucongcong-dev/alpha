"""
结果分析报告构建模块。

本模块只负责把运行结果编译成 `SummaryPayload` / `AnalysisPayload`，
不负责具体文件写入。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..config.static_config import get_static_config
from ..models.domain import (
    AnalysisInputs,
    AnalysisPayload,
    FieldTestResult,
    ResultRow,
    SummaryPayload,
)
from ..models.domain_serializers import serialize_failed_check, serialize_field_test_result
from ..models.result_predicates import has_pending_checks, is_queue_timeout_result
from .failed_checks import (
    compile_failed_check_leaderboard,
    compile_near_pass_summary,
    compile_optimization_hints,
)
from .field_stats import compile_field_performance_summary
from .template_registry_rules import compile_template_registry_summary
from .template_stats import compile_template_performance_summary, compile_template_stats


def build_results_summary_payload(
    dataset_id: str,
    results: list[FieldTestResult],
    *,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_fingerprint: str,
    run_config: dict[str, Any] | None,
    results_journal_path: str,
    include_embedded_results: bool = True,
) -> tuple[SummaryPayload, AnalysisInputs]:
    """单次遍历构建主结果 summary 及 analysis 所需的中间聚合数据。"""
    results_dicts: list[ResultRow] = []
    submittable_results: list[ResultRow] = []
    failed_checks_summary: list[ResultRow] = []
    field_ids: set[str] = set()
    submittable_count = 0
    error_count = 0
    queue_timeout_count = 0
    pending_check_count = 0

    for result in results:
        field_ids.add(result.field_id)

        if result.submittable:
            item = serialize_field_test_result(result)
            submittable_count += 1
            submittable_results.append(item)
        elif include_embedded_results:
            item = serialize_field_test_result(result)
        else:
            item = None
        if include_embedded_results and item is not None:
            results_dicts.append(item)
        if result.status == get_static_config().status_error:
            error_count += 1
        if is_queue_timeout_result(result):
            queue_timeout_count += 1
        if has_pending_checks(result):
            pending_check_count += 1
        if result.failed_checks:
            failed_checks_summary.append(
                {
                    "field_id": result.field_id,
                    "template_name": result.template_name,
                    "expression": result.expression,
                    "failed_checks": [
                        serialize_failed_check(check) for check in result.failed_checks
                    ],
                }
            )

    summary = {
        "dataset_id": dataset_id,
        "run_config": run_config or {},
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "run_fingerprint": run_fingerprint,
        "tested": len(results),
        "unique_fields_tested": len(field_ids),
        "submittable": submittable_count,
        "errors": error_count,
        "queue_timeouts": queue_timeout_count,
        "pending_checks": pending_check_count,
        "template_registry_embedded": False,
        "results_journal": results_journal_path,
    }
    if include_embedded_results:
        summary["results"] = results_dicts
    analysis_inputs = {
        "submittable_results": submittable_results,
        "failed_checks_summary": failed_checks_summary,
    }
    return summary, analysis_inputs


def build_analysis_payload(
    results: list[FieldTestResult],
    summary: SummaryPayload,
    analysis_inputs: AnalysisInputs,
    *,
    template_stats: Mapping[str, Mapping[str, Any]] | None = None,
    template_registry_summary: list[dict[str, Any]] | None = None,
) -> AnalysisPayload:
    """基于完整结果和 summary 构建 analysis sidecar 内容。"""
    template_performance_summary = compile_template_performance_summary(results)
    resolved_template_stats = (
        template_stats if template_stats is not None else compile_template_stats(results)
    )
    resolved_template_registry_summary = (
        template_registry_summary
        if template_registry_summary is not None
        else compile_template_registry_summary(resolved_template_stats)
    )
    field_performance_summary = compile_field_performance_summary(results)
    failed_check_leaderboard = compile_failed_check_leaderboard(results)
    near_pass_summary = compile_near_pass_summary(results)
    optimization_hints = compile_optimization_hints(
        failed_check_leaderboard,
        near_pass_summary,
    )
    return {
        "dataset_id": summary["dataset_id"],
        "settings_fingerprint": summary["settings_fingerprint"],
        "template_library_fingerprint": summary["template_library_fingerprint"],
        "run_fingerprint": summary.get("run_fingerprint", ""),
        "tested": summary["tested"],
        "unique_fields_tested": summary["unique_fields_tested"],
        "submittable_count": summary["submittable"],
        "error_count": summary["errors"],
        "queue_timeout_count": summary["queue_timeouts"],
        "pending_check_count": summary.get("pending_checks", 0),
        "submittable": analysis_inputs["submittable_results"],
        "failed_checks_summary": analysis_inputs["failed_checks_summary"],
        "failed_check_leaderboard": failed_check_leaderboard,
        "near_pass_summary": near_pass_summary,
        "optimization_hints": optimization_hints,
        "template_performance_summary": template_performance_summary,
        "template_registry_summary": resolved_template_registry_summary,
        "field_performance_summary": field_performance_summary,
    }
