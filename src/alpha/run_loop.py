"""
运行循环编排模块。

本模块承接主流程中的执行阶段逻辑，包括：
- 运行中反馈回灌
- 断点续跑索引处理
- 字段/模板调度循环
"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import logging
from typing import Any

from .analysis.feedback import should_stop_after_submittable
from .analysis.stats import (
    compile_field_feedback,
    compile_global_failed_check_counts,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from .config import SENTINEL_UNKNOWN
from .core import (
    build_pending_templates_for_field,
    drain_completed_futures,
    inflight_template_keys,
    load_pipeline_state,
    maybe_restore_runtime_concurrency,
    print_dry_run_plan,
    run_field_test_in_worker,
    save_checkpoint,
    save_pipeline_state,
    should_skip_field,
    throttle_before_submission,
)
from .models.base import InitializedRunContext, TemplateBuildContext
from .utils.helpers import choose_field_name, choose_field_type, first_non_empty

logger = logging.getLogger(__name__)


def refresh_runtime_feedback(
    template_build_ctx: TemplateBuildContext,
    results: list[Any],
    *,
    force: bool = False,
) -> None:
    """把当前进程内新产生的结果增量回灌到模板构建上下文。"""
    result_count = len(results)
    cached_count = getattr(template_build_ctx, "_feedback_result_count", -1)
    if force:
        template_build_ctx.field_feedback = compile_field_feedback(results)
        template_build_ctx.global_failed_check_counts = compile_global_failed_check_counts(results)
        setattr(template_build_ctx, "_feedback_result_count", result_count)
        return
    if cached_count == result_count:
        return
    if cached_count < 0 or cached_count > result_count:
        template_build_ctx.field_feedback = compile_field_feedback(results)
        template_build_ctx.global_failed_check_counts = compile_global_failed_check_counts(results)
        setattr(template_build_ctx, "_feedback_result_count", result_count)
        return
    for result in results[cached_count:]:
        update_field_feedback_with_result(template_build_ctx.field_feedback, result)
        update_global_failed_check_counts_with_result(
            template_build_ctx.global_failed_check_counts,
            result,
        )
    setattr(template_build_ctx, "_feedback_result_count", result_count)


def build_field_resume_positions(fields: list[dict[str, Any]]) -> dict[str, int]:
    """为字段列表建立稳定的原始顺序恢复位置索引。"""
    return {
        str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)): (index + 1)
        for index, field in enumerate(fields)
    }


def normalize_resume_index(resume_index: int, total_fields: int) -> int:
    """把续跑索引限制在当前字段列表范围内。"""
    if total_fields <= 0:
        return 0
    return resume_index % total_fields


def run_field_test_loop(
    args: argparse.Namespace,
    run_ctx: InitializedRunContext,
    run_paths: Any = None,
) -> None:
    """线程池中遍历字段并提交模拟任务，实时消费结果。"""
    state_file = getattr(run_paths, "state_file", "") if run_paths is not None else ""
    checkpoint_file = getattr(run_paths, "checkpoint_file", "") if run_paths is not None else ""
    runtime_state = run_ctx.runtime_state
    execution_state = run_ctx.execution_state
    fields = list(run_ctx.fields)
    original_fields = list(run_ctx.fields)
    max_workers = runtime_state.max_workers
    field_template_batch_size = max(0, int(getattr(args, "field_template_batch_size", 0) or 0))
    field_resume_positions = build_field_resume_positions(original_fields)

    resumed_index = 0
    if state_file:
        resumed_index = load_pipeline_state(
            state_file,
            runtime_state=runtime_state,
            execution_state=execution_state,
        )
        if resumed_index > 0:
            resumed_index = normalize_resume_index(resumed_index, len(fields))
            logger.info(
                "[resume] 从字段索引 %d/%d 附近继续 (优先从该位置恢复，但不会丢掉更早字段)",
                resumed_index + 1,
                len(fields),
            )
            fields = fields[resumed_index:] + fields[:resumed_index]

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

    template_build_ctx = TemplateBuildContext(
        args=args,
        all_fields=fields,
        template_library=run_ctx.template_library,
        field_feedback=run_ctx.historical_state.field_feedback,
        global_failed_check_counts=run_ctx.historical_state.global_failed_check_counts,
        include_templates=run_ctx.filters.include_templates,
        exclude_templates=run_ctx.filters.exclude_templates,
        use_dataset_heuristics=run_ctx.use_dataset_heuristics,
        expression_policy=run_ctx.expression_policy,
    )
    setattr(template_build_ctx, "_feedback_result_count", len(execution_state.results))

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

                        while len(execution_state.pending_futures) >= runtime_state.runtime_max_workers:
                            done, _ = wait(
                                set(execution_state.pending_futures), return_when=FIRST_COMPLETED
                            )
                            drain_completed_futures(
                                completed_futures=list(done),
                                execution_state=execution_state,
                                args=args,
                                settings_fingerprint=run_ctx.settings_fingerprint,
                                template_library_fingerprint=run_ctx.template_library_fingerprint,
                                run_config=run_ctx.run_config,
                                runtime_state=runtime_state,
                            )
                            if field_id in execution_state.skipped_fields_due_to_queue:
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

                        field_with_template = dict(field)
                        field_with_template["template_family"] = template_family
                        field_with_template["template_stage"] = template_stage
                        future = executor.submit(
                            run_field_test_in_worker,
                            run_ctx.client_factory,
                            args,
                            field_with_template,
                            template_name,
                            expression,
                            variant_fingerprint,
                            run_ctx.template_library_fingerprint,
                            settings_variant,
                            run_ctx.create_semaphore,
                        )

                        execution_state.last_submission_at = time.monotonic()
                        execution_state.pending_futures[future] = {
                            "field_id": field_id,
                            "field_name": field_name,
                            "field_type": field_type,
                            "template_name": template_name,
                            "template_family": template_family,
                            "template_stage": template_stage,
                            "expression": expression,
                            "settings_fingerprint": variant_fingerprint,
                        }

                    if state_file:
                        completed_index = field_resume_positions.get(field_id, field_index)
                        completed_index = normalize_resume_index(
                            completed_index,
                            len(original_fields),
                        )
                        save_pipeline_state(
                            state_file,
                            completed_field_index=completed_index,
                            execution_state=execution_state,
                            runtime_state=runtime_state,
                            field_id=field_id,
                        )

                if field_template_batch_size <= 0 or should_stop_after_submittable(
                    args, execution_state.results
                ):
                    break
                if not progressed_this_round:
                    logger.info("[schedule] no pending templates remain after round=%d", round_index)
                    break

            while execution_state.pending_futures:
                done, _ = wait(set(execution_state.pending_futures), return_when=FIRST_COMPLETED)
                drain_completed_futures(
                    completed_futures=list(done),
                    execution_state=execution_state,
                    args=args,
                    settings_fingerprint=run_ctx.settings_fingerprint,
                    template_library_fingerprint=run_ctx.template_library_fingerprint,
                    run_config=run_ctx.run_config,
                    runtime_state=runtime_state,
                )
                if state_file:
                    completed_index = resumed_index + len(fields)
                    save_pipeline_state(
                        state_file,
                        completed_field_index=completed_index,
                        execution_state=execution_state,
                        runtime_state=runtime_state,
                        field_id=last_field_id,
                    )
        except KeyboardInterrupt:
            if checkpoint_file:
                save_checkpoint(
                    checkpoint_file,
                    execution_state=execution_state,
                    runtime_state=runtime_state,
                    field_id=last_field_id or "",
                    remaining_fields=max(0, len(fields)),
                    reason="KeyboardInterrupt",
                )
            raise
        except Exception:
            if checkpoint_file:
                save_checkpoint(
                    checkpoint_file,
                    execution_state=execution_state,
                    runtime_state=runtime_state,
                    field_id=last_field_id or "",
                    remaining_fields=max(0, len(fields)),
                    reason="Exception",
                )
            raise
