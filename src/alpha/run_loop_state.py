"""Run-loop state helper functions."""

from __future__ import annotations

from .analysis.stats import (
    compile_field_feedback,
    compile_global_failed_check_counts,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from .config.constants import SENTINEL_UNKNOWN
from .models.domain import FieldTestResult
from .models.io_types import RunPaths
from .models.runtime import (
    ResultWriteArgs,
    ResultWriteOptions,
    TemplateBuildContext,
    TemplateField,
)
from .utils.helpers import first_non_empty


def refresh_runtime_feedback(
    template_build_ctx: TemplateBuildContext,
    results: list[FieldTestResult],
    *,
    force: bool = False,
) -> None:
    """把当前进程内新产生的结果增量回灌到模板构建上下文。"""
    result_count = len(results)
    cached_count = template_build_ctx.feedback_result_count
    if force:
        template_build_ctx.field_feedback = compile_field_feedback(results)
        template_build_ctx.global_failed_check_counts = compile_global_failed_check_counts(results)
        template_build_ctx.feedback_result_count = result_count
        return
    if cached_count == result_count:
        return
    if cached_count < 0 or cached_count > result_count:
        template_build_ctx.field_feedback = compile_field_feedback(results)
        template_build_ctx.global_failed_check_counts = compile_global_failed_check_counts(results)
        template_build_ctx.feedback_result_count = result_count
        return
    for result in results[cached_count:]:
        update_field_feedback_with_result(template_build_ctx.field_feedback, result)
        update_global_failed_check_counts_with_result(
            template_build_ctx.global_failed_check_counts,
            result,
        )
    template_build_ctx.feedback_result_count = result_count


def build_field_resume_positions(fields: list[TemplateField]) -> dict[str, int]:
    """为字段列表建立稳定的原始顺序恢复位置索引。"""
    return {
        str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)): (index + 1)
        for index, field in enumerate(fields)
    }


def clamp_resume_index(resume_index: int, total_fields: int) -> int:
    """把续跑索引限制在当前字段列表范围内，并保留“已全部完成”终态。"""
    if total_fields <= 0:
        return 0
    return max(0, min(resume_index, total_fields))


def normalize_resume_index(resume_index: int, total_fields: int) -> int:
    """兼容旧调用方的续跑索引归一化入口。"""
    if total_fields <= 0:
        return 0
    return resume_index % total_fields


def run_path_value(run_paths: object | None, attr: str) -> str:
    """兼容 RunPaths 与历史 attr-style 对象的路径读取。"""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def resolve_result_write_options(
    args: ResultWriteArgs,
    run_paths: RunPaths | object | None,
) -> ResultWriteOptions:
    """优先使用 run_paths 中的输出路径，避免旧调用链依赖 args 已被改写。"""
    options = ResultWriteOptions.from_args(args)
    output_path = run_path_value(run_paths, "output") or options.output_path
    return ResultWriteOptions(
        dataset_id=options.dataset_id,
        output_path=output_path,
        auto_update_blacklist=options.auto_update_blacklist,
    )
