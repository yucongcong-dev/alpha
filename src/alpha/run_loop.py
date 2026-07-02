"""
运行循环编排模块。

本模块承接主流程中的执行阶段逻辑，包括：
- 运行中反馈回灌
- 断点续跑索引处理
- 字段/模板调度循环
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging

from .analysis.feedback import should_stop_after_submittable
from .analysis.stats import (
    compile_field_feedback,
    compile_global_failed_check_counts,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from .config.constants import SENTINEL_UNKNOWN
from .core import (
    build_pending_templates_for_field,
    inflight_template_keys,
    maybe_restore_runtime_concurrency,
    print_dry_run_plan,
    should_skip_field,
    throttle_before_submission,
)
from .loop_support import (
    create_template_build_context,
    drain_remaining_futures,
    drain_until_capacity,
    persist_field_progress,
    restore_fields_from_state,
    save_runtime_checkpoint,
    submit_template_future,
)
from .models.domain import FieldTestResult
from .models.io_types import RunPaths
from .models.runtime import (
    InitializedRunContext,
    ResultWriteArgs,
    ResultWriteOptions,
    RunLoopArgs,
    TemplateBuildContext,
    TemplateField,
)
from .utils.helpers import choose_field_name, choose_field_type, first_non_empty

logger = logging.getLogger(__name__)


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


def _run_path_value(run_paths: object | None, attr: str) -> str:
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
    output_path = _run_path_value(run_paths, "output") or options.output_path
    return ResultWriteOptions(
        dataset_id=options.dataset_id,
        output_path=output_path,
        auto_update_blacklist=options.auto_update_blacklist,
    )


def run_field_test_loop(
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    run_paths: RunPaths | object | None = None,
) -> None:
    """线程池中遍历字段并提交模拟任务，实时消费结果。"""
    state_file = _run_path_value(run_paths, "state_file")
    checkpoint_file = _run_path_value(run_paths, "checkpoint_file")
    runtime_state = run_ctx.runtime_state
    execution_state = run_ctx.execution_state
    fields = list(run_ctx.fields)
    original_fields = list(run_ctx.fields)
    max_workers = runtime_state.max_workers
    field_template_batch_size = max(0, int(getattr(args, "field_template_batch_size", 0) or 0))
    field_resume_positions = build_field_resume_positions(original_fields)
    result_write_options = resolve_result_write_options(args, run_paths)

    fields, _resumed_index = restore_fields_from_state(
        fields=fields,
        state_file=state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
        clamp_resume_index_fn=clamp_resume_index,
    )

    if args.dry_run_plan:
        print_dry_run_plan(
            args=args,
            fields=fields,
            filters=run_ctx.filters,
            template_library=run_ctx.template_library,
            historical_state=run_ctx.historical_state,
            execution_state=execution_state,
            use_dataset_heuristics=run_ctx.use_dataset_heuristics,
        )
        return

    template_build_ctx = create_template_build_context(
        args=args,
        run_ctx=run_ctx,
        fields=fields,
        existing_results_count=len(execution_state.results),
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        last_field_id = ""
        try:
            round_index = 0
            while True:
                round_index += 1
                progressed_this_round = False
                if field_template_batch_size > 0:
                    logger.info(
                        "[schedule] round=%d breadth-first batch_size=%d fields=%d",
                        round_index,
                        field_template_batch_size,
                        len(fields),
                    )
                for field_index, field in enumerate(fields, start=1):
                    if should_stop_after_submittable(args, execution_state.results):
                        logger.info(
                            "[stop] 达到 stop-after-submittable=%d",
                            args.stop_after_submittable,
                        )
                        break

                    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
                    last_field_id = field_id
                    field_name = choose_field_name(field)
                    field_type = choose_field_type(field)
                    refresh_runtime_feedback(template_build_ctx, execution_state.results)

                    if should_skip_field(
                        field_id,
                        field_name,
                        run_ctx.filters,
                        execution_state.skipped_fields_due_to_queue,
                    ):
                        persist_field_progress(
                            state_file=state_file,
                            field_id=field_id,
                            field_index=field_index,
                            original_fields=original_fields,
                            field_resume_positions=field_resume_positions,
                            execution_state=execution_state,
                            runtime_state=runtime_state,
                        )
                        continue

                    pending_templates, disabled_templates, template_count = (
                        build_pending_templates_for_field(
                            template_build_ctx,
                            field,
                            template_stats=execution_state.template_stats,
                            attempted_keys=execution_state.attempted_keys,
                            prior_results=execution_state.results,
                            reserved_keys=inflight_template_keys(
                                execution_state.pending_futures
                            ),
                        )
                    )

                    logger.debug(
                        "[progress] 字段 %d/%d field_id=%s templates=%d pending=%d disabled=%d",
                        field_index,
                        len(fields),
                        field_id,
                        template_count,
                        len(pending_templates),
                        disabled_templates,
                    )

                    if field_template_batch_size > 0:
                        scheduled_templates = pending_templates[:field_template_batch_size]
                        deferred_templates = max(0, len(pending_templates) - len(scheduled_templates))
                    else:
                        scheduled_templates = pending_templates
                        deferred_templates = 0
                    if scheduled_templates:
                        progressed_this_round = True
                    if deferred_templates > 0:
                        logger.debug(
                            "[schedule] field=%s round=%d dispatch=%d deferred=%d",
                            field_id,
                            round_index,
                            len(scheduled_templates),
                            deferred_templates,
                        )

                    for template_index, (
                        template_name,
                        template_family,
                        template_stage,
                        expression,
                        priority,
                        settings_variant,
                        variant_fingerprint,
                    ) in enumerate(scheduled_templates, start=1):
                        if should_stop_after_submittable(args, execution_state.results):
                            logger.info(
                                "[stop] 达到 stop-after-submittable=%d",
                                args.stop_after_submittable,
                            )
                            break

                        if field_id in execution_state.skipped_fields_due_to_queue:
                            logger.warning("[skip] field=%s 队列拥塞后停止剩余模板", field_id)
                            break

                        maybe_restore_runtime_concurrency(runtime_state)

                        if not drain_until_capacity(
                            executor_state=execution_state,
                            runtime_state=runtime_state,
                            args=args,
                            run_ctx=run_ctx,
                            field_id=field_id,
                            result_write_options=result_write_options,
                        ):
                            break

                        logger.debug(
                            "[progress] field=%s template %d/%d name=%s priority=%d queued=%d/%d settings=%s",
                            field_id,
                            template_index,
                            len(scheduled_templates),
                            template_name,
                            priority,
                            len(execution_state.pending_futures) + 1,
                            runtime_state.runtime_max_workers,
                            variant_fingerprint,
                        )

                        throttle_before_submission(args, execution_state)

                        submit_template_future(
                            executor=executor,
                            run_ctx=run_ctx,
                            execution_state=execution_state,
                            args=args,
                            field=field,
                            field_id=field_id,
                            field_name=field_name,
                            field_type=field_type,
                            template_name=template_name,
                            template_family=template_family,
                            template_stage=template_stage,
                            expression=expression,
                            settings_variant=settings_variant,
                            variant_fingerprint=variant_fingerprint,
                        )
                    persist_field_progress(
                        state_file=state_file,
                        field_id=field_id,
                        field_index=field_index,
                        original_fields=original_fields,
                        field_resume_positions=field_resume_positions,
                        execution_state=execution_state,
                        runtime_state=runtime_state,
                    )

                if field_template_batch_size <= 0 or should_stop_after_submittable(
                    args, execution_state.results
                ):
                    break
                if not progressed_this_round:
                    logger.info("[schedule] no pending templates remain after round=%d", round_index)
                    break

            drain_remaining_futures(
                state_file=state_file,
                total_fields=len(original_fields),
                last_field_id=last_field_id,
                execution_state=execution_state,
                runtime_state=runtime_state,
                args=args,
                run_ctx=run_ctx,
                result_write_options=result_write_options,
            )
        except KeyboardInterrupt:
            save_runtime_checkpoint(
                checkpoint_file=checkpoint_file,
                execution_state=execution_state,
                runtime_state=runtime_state,
                last_field_id=last_field_id,
                fields=fields,
                reason="KeyboardInterrupt",
            )
            raise
        except Exception:
            save_runtime_checkpoint(
                checkpoint_file=checkpoint_file,
                execution_state=execution_state,
                runtime_state=runtime_state,
                last_field_id=last_field_id,
                fields=fields,
                reason="Exception",
            )
            raise
