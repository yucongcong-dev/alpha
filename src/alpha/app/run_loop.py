"""
运行循环编排模块。

本模块承接主流程中的执行阶段逻辑，包括：
- 线程池调度循环
- 字段/模板调度轮次
- 运行中反馈回灌
- 断点续跑索引处理
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import dataclasses
from dataclasses import dataclass
import logging
import time
from typing import TYPE_CHECKING, Any, cast

from ..analysis.feedback_history import should_stop_after_submittable
from ..analysis.stats import (
    compile_field_feedback,
    compile_global_failed_check_counts,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from ..config.constants import SENTINEL_UNKNOWN
from ..core import (
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
from ..generators.fields import choose_field_name, choose_field_type
from ..models.domain import FieldTestResult, SettingsVariant
from ..models.io_types import RunPaths
from ..models.runtime import (
    ExecutionState,
    InitializedRunContext,
    PendingFutureContext,
    ResultWriteArgs,
    ResultWriteOptions,
    RunLoopArgs,
    RuntimeConcurrencyState,
    SchedulerRuntimeArgs,
    SimulationStageArgs,
    TemplateBuildArgs,
    TemplateBuildContext,
    TemplateBuildOptions,
    TemplateField,
)
from ..utils.helpers import first_non_empty

if TYPE_CHECKING:
    from ..api.client import WorkerClientFactory

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleRoundResult:
    """Summary of a single breadth-first scheduling round."""

    progressed: bool
    stop_requested: bool
    last_field_id: str


def run_path_value(run_paths: object | None, attr: str) -> str:
    """Read a path from RunPaths or a legacy attr-style object."""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def resolve_result_write_options(
    args: ResultWriteArgs,
    run_paths: RunPaths | object | None,
) -> ResultWriteOptions:
    """Prefer run_paths output over raw args output to avoid legacy mutation coupling."""
    options = ResultWriteOptions.from_args(args)
    output_path = run_path_value(run_paths, "output") or options.output_path
    return ResultWriteOptions(
        dataset_id=options.dataset_id,
        output_path=output_path,
        auto_update_blacklist=options.auto_update_blacklist,
    )


def build_field_resume_positions(fields: list[TemplateField]) -> dict[str, int]:
    """Build stable original-order resume positions for each field id."""
    return {
        str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)): (index + 1)
        for index, field in enumerate(fields)
    }


def clamp_resume_index(resume_index: int, total_fields: int) -> int:
    """Clamp resume index into the current field range while preserving terminal completion."""
    if total_fields <= 0:
        return 0
    return max(0, min(resume_index, total_fields))


def normalize_resume_index(resume_index: int, total_fields: int) -> int:
    """Normalize resume index modulo current field count for legacy callers."""
    if total_fields <= 0:
        return 0
    return resume_index % total_fields


def refresh_runtime_feedback(
    template_build_ctx: TemplateBuildContext,
    results: list[FieldTestResult],
    *,
    force: bool = False,
) -> None:
    """Incrementally feed newly produced results back into the template context."""
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


def restore_fields_from_state(
    *,
    fields: list[TemplateField],
    state_file: str,
    runtime_state: RuntimeConcurrencyState,
    execution_state: ExecutionState,
    clamp_resume_index_fn,
) -> tuple[list[TemplateField], int]:
    """Restore field start position from pipeline state and rotate field order accordingly."""
    resumed_index = 0
    if not state_file:
        return fields, resumed_index
    resumed_index = load_pipeline_state(
        state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
    )
    if resumed_index <= 0:
        return fields, resumed_index
    resumed_index = clamp_resume_index_fn(resumed_index, len(fields))
    if resumed_index >= len(fields):
        logger.info(
            "[resume] state_file 记录的字段进度已覆盖全部 %d 个字段，直接进入收尾阶段",
            len(fields),
        )
        return [], resumed_index
    logger.info(
        "[resume] 从字段索引 %d/%d 附近继续 (优先从该位置恢复，但不会丢掉更早字段)",
        resumed_index + 1,
        len(fields),
    )
    return fields[resumed_index:] + fields[:resumed_index], resumed_index


def create_template_build_context(
    *,
    args: TemplateBuildArgs,
    run_ctx: InitializedRunContext,
    fields: list[TemplateField],
    existing_results_count: int,
) -> TemplateBuildContext:
    """Construct the template build context and seed its feedback cache count."""
    template_build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=fields,
        template_library=run_ctx.template_library,
        field_feedback=run_ctx.historical_state.field_feedback,
        global_failed_check_counts=run_ctx.historical_state.global_failed_check_counts,
        include_templates=run_ctx.filters.include_templates,
        exclude_templates=run_ctx.filters.exclude_templates,
        use_dataset_heuristics=run_ctx.use_dataset_heuristics,
        expression_policy=run_ctx.expression_policy,
    )
    template_build_ctx.feedback_result_count = existing_results_count
    return template_build_ctx


def persist_field_progress(
    *,
    state_file: str,
    field_id: str,
    field_index: int,
    original_fields: list[TemplateField],
    field_resume_positions: dict[str, int],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """Persist pipeline state after completing one field."""
    if not state_file:
        return
    completed_index = field_resume_positions.get(field_id, field_index)
    completed_index = max(0, min(completed_index, len(original_fields)))
    save_pipeline_state(
        state_file,
        completed_field_index=completed_index,
        execution_state=execution_state,
        runtime_state=runtime_state,
        field_id=field_id,
    )


def save_runtime_checkpoint(
    *,
    checkpoint_file: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    last_field_id: str,
    fields: list[TemplateField],
    reason: str,
) -> None:
    """Persist a checkpoint on interrupt or exception."""
    if not checkpoint_file:
        return
    save_checkpoint(
        checkpoint_file,
        execution_state=execution_state,
        runtime_state=runtime_state,
        field_id=last_field_id or "",
        remaining_fields=max(0, len(fields)),
        reason=reason,
    )


def drain_until_capacity(
    *,
    executor_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    args: SchedulerRuntimeArgs,
    run_ctx: InitializedRunContext,
    field_id: str,
    result_write_options: ResultWriteOptions,
) -> bool:
    """Drain completed futures until runtime concurrency has available capacity."""
    while len(executor_state.pending_futures) >= runtime_state.runtime_max_workers:
        done, _ = wait(
            set(
                cast(
                    "dict[Future[Any], PendingFutureContext]",
                    executor_state.pending_futures,
                )
            ),
            return_when=FIRST_COMPLETED,
        )
        drain_completed_futures(
            completed_futures=list(done),
            execution_state=executor_state,
            args=args,
            result_write_options=result_write_options,
            settings_fingerprint=run_ctx.settings_fingerprint,
            template_library_fingerprint=run_ctx.template_library_fingerprint,
            run_config=run_ctx.run_config,
            runtime_state=runtime_state,
        )
        if field_id in executor_state.skipped_fields_due_to_queue:
            return False
    return True


def submit_template_future(
    *,
    executor: ThreadPoolExecutor,
    run_ctx: InitializedRunContext,
    execution_state: ExecutionState,
    args: SimulationStageArgs,
    field: TemplateField,
    field_id: str,
    field_name: str,
    field_type: str,
    template_name: str,
    template_family: str,
    template_stage: str,
    expression: str,
    settings_variant: SettingsVariant,
    variant_fingerprint: str,
) -> None:
    """Submit one simulation future and register its pending metadata."""
    field_with_template = dataclasses.replace(
        field,
        metadata={**field.metadata, "template_family": template_family, "template_stage": template_stage},
    )
    future = executor.submit(
        run_field_test_in_worker,
        cast("WorkerClientFactory", run_ctx.client_factory),
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
    execution_state.pending_futures[future] = PendingFutureContext(
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        template_name=template_name,
        template_family=template_family,
        template_stage=template_stage,
        expression=expression,
        settings_fingerprint=variant_fingerprint,
    )


def drain_remaining_futures(
    *,
    state_file: str,
    total_fields: int,
    last_field_id: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    args: SchedulerRuntimeArgs,
    run_ctx: InitializedRunContext,
    result_write_options: ResultWriteOptions,
) -> None:
    """Drain all remaining futures and persist terminal pipeline state when needed."""
    while execution_state.pending_futures:
        done, _ = wait(
            set(
                cast(
                    "dict[Future[Any], PendingFutureContext]",
                    execution_state.pending_futures,
                )
            ),
            return_when=FIRST_COMPLETED,
        )
        drain_completed_futures(
            completed_futures=list(done),
            execution_state=execution_state,
            args=args,
            result_write_options=result_write_options,
            settings_fingerprint=run_ctx.settings_fingerprint,
            template_library_fingerprint=run_ctx.template_library_fingerprint,
            run_config=run_ctx.run_config,
            runtime_state=runtime_state,
        )
        if state_file:
            save_pipeline_state(
                state_file,
                completed_field_index=max(0, total_fields),
                execution_state=execution_state,
                runtime_state=runtime_state,
                field_id=last_field_id,
            )


def execute_schedule_round(
    *,
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    executor: ThreadPoolExecutor,
    template_build_ctx: TemplateBuildContext,
    fields: list[TemplateField],
    original_fields: list[TemplateField],
    field_resume_positions: dict[str, int],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    result_write_options: ResultWriteOptions,
    state_file: str,
    round_index: int,
    field_template_batch_size: int,
) -> ScheduleRoundResult:
    """Execute one scheduling round across every remaining field."""
    progressed_this_round = False
    last_field_id = ""
    if field_template_batch_size > 0:
        logger.info(
            "[schedule] round=%d breadth-first batch_size=%d fields=%d",
            round_index,
            field_template_batch_size,
            len(fields),
        )

    for field_index, field in enumerate(fields, start=1):
        if should_stop_after_submittable(args, execution_state.results):
            logger.info("[stop] 达到 stop-after-submittable=%d", args.stop_after_submittable)
            return ScheduleRoundResult(
                progressed=progressed_this_round,
                stop_requested=True,
                last_field_id=last_field_id,
            )

        field_result = schedule_field_round(
            args=args,
            run_ctx=run_ctx,
            executor=executor,
            template_build_ctx=template_build_ctx,
            field=field,
            field_index=field_index,
            total_fields=len(fields),
            original_fields=original_fields,
            field_resume_positions=field_resume_positions,
            execution_state=execution_state,
            runtime_state=runtime_state,
            result_write_options=result_write_options,
            state_file=state_file,
            round_index=round_index,
            field_template_batch_size=field_template_batch_size,
        )
        last_field_id = field_result.last_field_id or last_field_id
        progressed_this_round = progressed_this_round or field_result.progressed
        if field_result.stop_requested:
            return ScheduleRoundResult(
                progressed=progressed_this_round,
                stop_requested=True,
                last_field_id=last_field_id,
            )

    return ScheduleRoundResult(
        progressed=progressed_this_round,
        stop_requested=False,
        last_field_id=last_field_id,
    )


def schedule_field_round(
    *,
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    executor: ThreadPoolExecutor,
    template_build_ctx: TemplateBuildContext,
    field: TemplateField,
    field_index: int,
    total_fields: int,
    original_fields: list[TemplateField],
    field_resume_positions: dict[str, int],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    result_write_options: ResultWriteOptions,
    state_file: str,
    round_index: int,
    field_template_batch_size: int,
) -> ScheduleRoundResult:
    """Schedule one field for the current round and persist its progress."""
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
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
        return ScheduleRoundResult(progressed=False, stop_requested=False, last_field_id=field_id)

    pending_templates, disabled_templates, template_count = build_pending_templates_for_field(
        template_build_ctx,
        field,
        template_stats=execution_state.template_stats,
        attempted_keys=execution_state.attempted_keys,
        prior_results=execution_state.results,
        reserved_keys=inflight_template_keys(execution_state.pending_futures),
    )
    logger.debug(
        "[progress] 字段 %d/%d field_id=%s templates=%d pending=%d disabled=%d",
        field_index,
        total_fields,
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
    progressed = bool(scheduled_templates)
    if deferred_templates > 0:
        logger.debug(
            "[schedule] field=%s round=%d dispatch=%d deferred=%d",
            field_id,
            round_index,
            len(scheduled_templates),
            deferred_templates,
        )

    stop_requested = _dispatch_templates_for_field(
        args=args,
        run_ctx=run_ctx,
        executor=executor,
        execution_state=execution_state,
        runtime_state=runtime_state,
        result_write_options=result_write_options,
        field=field,
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        scheduled_templates=scheduled_templates,
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
    return ScheduleRoundResult(
        progressed=progressed,
        stop_requested=stop_requested,
        last_field_id=field_id,
    )


def _dispatch_templates_for_field(
    *,
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    executor: ThreadPoolExecutor,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    result_write_options: ResultWriteOptions,
    field: TemplateField,
    field_id: str,
    field_name: str,
    field_type: str,
    scheduled_templates: list[tuple[str, str, str, str, int, SettingsVariant, str]],
) -> bool:
    """Dispatch scheduled templates for a single field; return whether a stop was requested."""
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
            logger.info("[stop] 达到 stop-after-submittable=%d", args.stop_after_submittable)
            return True

        if field_id in execution_state.skipped_fields_due_to_queue:
            logger.warning("[skip] field=%s 队列拥塞后停止剩余模板", field_id)
            return False

        maybe_restore_runtime_concurrency(runtime_state)
        if not drain_until_capacity(
            executor_state=execution_state,
            runtime_state=runtime_state,
            args=args,
            run_ctx=run_ctx,
            field_id=field_id,
            result_write_options=result_write_options,
        ):
            return False

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
            settings_variant=cast("SettingsVariant", settings_variant),
            variant_fingerprint=variant_fingerprint,
        )
    return False


def run_field_test_loop(
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    run_paths: RunPaths | object | None = None,
) -> None:
    """线程池中遍历字段并提交模拟任务，实时消费结果。"""
    state_file = run_path_value(run_paths, "state_file")
    checkpoint_file = run_path_value(run_paths, "checkpoint_file")
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
            args=cast("TemplateBuildArgs", args),
            fields=fields,
            filters=run_ctx.filters,
            template_library=run_ctx.template_library,
            historical_state=run_ctx.historical_state,
            execution_state=execution_state,
            use_dataset_heuristics=run_ctx.use_dataset_heuristics,
        )
        return

    template_build_ctx = create_template_build_context(
        args=cast("TemplateBuildArgs", args),
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
                round_result = execute_schedule_round(
                    args=args,
                    run_ctx=run_ctx,
                    executor=executor,
                    template_build_ctx=template_build_ctx,
                    fields=fields,
                    original_fields=original_fields,
                    field_resume_positions=field_resume_positions,
                    execution_state=execution_state,
                    runtime_state=runtime_state,
                    result_write_options=result_write_options,
                    state_file=state_file,
                    round_index=round_index,
                    field_template_batch_size=field_template_batch_size,
                )
                last_field_id = round_result.last_field_id or last_field_id
                if field_template_batch_size <= 0 or round_result.stop_requested:
                    break
                if not round_result.progressed:
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