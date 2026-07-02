"""
结果分析报告构建模块。

本模块只负责把运行结果编译成 `SummaryPayload` / `AnalysisPayload`，
不负责具体文件写入。
"""

from __future__ import annotations

from typing import Any

from ..config.constants import STATUS_ERROR
from ..models.domain import (
    AnalysisInputs,
    AnalysisPayload,
    FieldTestResult,
    ResultRow,
    SummaryPayload,
)
from .stats import (
    compile_failed_check_leaderboard,
    compile_field_performance_summary,
    compile_near_pass_summary,
    compile_optimization_hints,
    compile_template_performance_summary,
    is_queue_timeout_result,
)


def build_results_summary_payload(
    dataset_id: str,
    results: list[FieldTestResult],
    *,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict[str, Any] | None,
    results_journal_path: str,
) -> tuple[SummaryPayload, AnalysisInputs]:
    """单次遍历构建主结果 summary 及 analysis 所需的中间聚合数据。"""
    results_dicts: list[ResultRow] = []
    submittable_results: list[ResultRow] = []
    submitted_results: list[ResultRow] = []
    failed_checks_summary: list[ResultRow] = []
    field_ids: set[str] = set()
    submittable_count = 0
    submitted_count = 0
    error_count = 0
    queue_timeout_count = 0

    for result in results:
        item = result.to_dict()
        results_dicts.append(item)
        field_ids.add(result.field_id)

        if result.submittable:
            submittable_count += 1
            submittable_results.append(item)
        if result.submitted:
            submitted_count += 1
            submitted_results.append(item)
        if result.status == STATUS_ERROR:
            error_count += 1
        if is_queue_timeout_result(result):
            queue_timeout_count += 1
        if result.failed_checks:
            failed_checks_summary.append(
                {
                    "field_id": result.field_id,
                    "template_name": result.template_name,
                    "expression": result.expression,
                    "failed_checks": result.failed_checks,
                }
            )

    summary = {
        "dataset_id": dataset_id,
        "run_config": run_config or {},
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "tested": len(results),
        "unique_fields_tested": len(field_ids),
        "submittable": submittable_count,
        "submitted": submitted_count,
        "errors": error_count,
        "queue_timeouts": queue_timeout_count,
        "results_journal": results_journal_path,
        "results": results_dicts,
    }
    analysis_inputs = {
        "submittable_results": submittable_results,
        "submitted_results": submitted_results,
        "failed_checks_summary": failed_checks_summary,
    }
    return summary, analysis_inputs


def build_analysis_payload(
    results: list[FieldTestResult],
    summary: SummaryPayload,
    analysis_inputs: AnalysisInputs,
) -> AnalysisPayload:
    """基于完整结果和 summary 构建 analysis sidecar 内容。"""
    template_performance_summary = compile_template_performance_summary(results)
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
        "tested": summary["tested"],
        "unique_fields_tested": summary["unique_fields_tested"],
        "submittable_count": summary["submittable"],
        "submitted_count": summary["submitted"],
        "error_count": summary["errors"],
        "queue_timeout_count": summary["queue_timeouts"],
        "submittable": analysis_inputs["submittable_results"],
        "submitted": analysis_inputs["submitted_results"],
        "failed_checks_summary": analysis_inputs["failed_checks_summary"],
        "failed_check_leaderboard": failed_check_leaderboard,
        "near_pass_summary": near_pass_summary,
        "optimization_hints": optimization_hints,
        "template_performance_summary": template_performance_summary,
        "field_performance_summary": field_performance_summary,
    }
