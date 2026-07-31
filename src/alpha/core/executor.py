"""
测试执行流程模块

本模块是 Alpha 测试执行的高层协调模块，
负责任务队列构建、字段过滤和干运行计划等功能。

实际的模拟生命周期管理由 simulation.py 负责，
并发调度与拥塞控制由 scheduler.py 负责。

模块内容：
    - 模板队列构建函数
    - 历史跳过判断函数
    - 字段跳过判断函数
    - 干运行计划打印函数
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import Future
from dataclasses import replace
import logging

from ..config.constants import DRY_RUN_SAMPLE_LIMIT, SENTINEL_UNKNOWN
from ..generators.expression_builder import build_expression_candidates
from ..generators.fields import choose_field_name
from ..generators.payload import build_settings_fingerprint_from_payload
from ..generators.variants import build_setting_variants
from ..models.domain import FieldTestResult, TemplateCandidate, TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_options import TemplateBuildOptions
from ..models.runtime_protocols import TemplateBuildArgs
from ..policy.expression import get_dataset_expression_policy
from ..runtime.contexts import (
    HistoricalRunState,
    PendingFutureContext,
    PendingTemplateEntry,
    TemplateBuildContext,
)
from ..runtime.preset_mode import resolve_preset_mode
from ..runtime.state import ExecutionState
from ..utils.helpers import first_non_empty
from .execution_filters import (
    is_template_actionable,
    is_template_selected_by_filters,
    should_skip_field,
)
from .execution_filters import (
    should_skip_expression_by_history as should_skip_expression_by_history,
)
from .template_planning import (
    TemplatePlanningServices,
    build_pending_template_variants,
    resolve_field_template_candidates,
)

logger = logging.getLogger(__name__)


def build_executor_template_planning_services() -> TemplatePlanningServices:
    """Build planning dependencies from current executor module overrides."""
    return TemplatePlanningServices(
        build_expression_candidates=build_expression_candidates,
        build_setting_variants=build_setting_variants,
        build_settings_fingerprint=build_settings_fingerprint_from_payload,
    )


# ============================================================================
# 模板队列构建函数
# ============================================================================


def build_template_build_context(
    *,
    args: TemplateBuildArgs,
    fields: Sequence[TemplateField],
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    filters: RunFilters,
    use_dataset_heuristics: bool,
    existing_results_count: int,
) -> TemplateBuildContext:
    """Construct the shared template build context for dry-run and live execution."""
    options = TemplateBuildOptions.from_args(args)
    options = replace(
        options,
        preset_mode=options.preset_mode
        or resolve_preset_mode(
            template_library_file=str(args.template_library_file or ""),
            include_fields=filters.include_fields,
        ),
    )
    template_build_ctx = TemplateBuildContext(
        options=options,
        template_library_file=str(args.template_library_file or ""),
        all_fields=fields,
        template_library=template_library,
        field_feedback=historical_state.field_feedback,
        global_failed_check_counts=historical_state.global_failed_check_counts,
        include_templates=filters.include_templates,
        exclude_templates=filters.exclude_templates,
        use_dataset_heuristics=use_dataset_heuristics,
        expression_policy=get_dataset_expression_policy(
            options.dataset_id,
            use_curated_heuristics=use_dataset_heuristics,
        ),
    )
    template_build_ctx.feedback_result_count = existing_results_count
    return template_build_ctx


def inflight_template_keys(
    pending_futures: Mapping[Future[FieldTestResult], PendingFutureContext],
) -> set[tuple[str, str, str, str]]:
    """
    从尚未完成的 future 上下文中提取去重键。

    breadth-first 调度会在上一轮 future 尚未完成时继续进入下一轮，
    因此不能只依赖已落盘结果与 attempted_keys；否则同一 field/template/settings
    会在 pending 期间被再次加入队列。
    """
    reserved: set[tuple[str, str, str, str]] = set()
    for context in pending_futures.values():
        field_id = str(first_non_empty(context.field_id, SENTINEL_UNKNOWN))
        template_name = str(first_non_empty(context.template_name, ""))
        expression = str(first_non_empty(context.expression, ""))
        settings_fingerprint = str(first_non_empty(context.settings_fingerprint, ""))
        reserved.add((field_id, template_name, expression, settings_fingerprint))
    return reserved


def build_pending_templates_for_field(
    build_ctx: TemplateBuildContext,
    field: TemplateField,
    *,
    attempted_keys: set[tuple[str, str, str, str]],
    prior_results: Sequence[FieldTestResult],
    reserved_keys: set[tuple[str, str, str, str]] | None = None,
    planning_services: TemplatePlanningServices | None = None,
) -> tuple[list[PendingTemplateEntry], int, int]:
    """
    为单个字段构建真正可执行的模板与 settings 队列。

    根据字段信息、历史反馈和各种过滤条件，构建一个可执行的模板队列，
    包含模板名称、表达式、优先级、设置变体和指纹。
    使用 TemplateBuildContext 将 11 个参数收敛到 4 个。

    Args:
        build_ctx: 包含模板构建配置、字段集合和历史反馈等只读上下文对象。
        field: 字段元数据字典。
        attempted_keys: 已尝试的模板键集合。
        prior_results: 历史测试结果列表。
        reserved_keys: 当前运行中已提交但尚未完成的组合键集合。

    Returns:
        tuple[list[tuple[str, str, int, SettingsVariant, str]], int, int]: 返回一个元组，包含：
            - pending_templates: 待执行模板列表
            - filtered_templates: 被显式规则或字段反馈过滤的模板数量
            - template_count: 原始模板总数

    Note:
        - 模板按优先级降序排列
        - 已尝试的键会被跳过
    """
    active_services = planning_services or build_executor_template_planning_services()
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    templates, field_feedback, expression_policy = resolve_field_template_candidates(
        build_ctx,
        field,
        prior_results=prior_results,
        services=active_services,
    )
    # Exploration is intentionally cheap and independent of global failures:
    # a new field gets one seed template, while exact historical combinations
    # remain deduplicated below.  This avoids a separate fallback path when
    # global template history has demoted every candidate.
    planning_ctx = build_ctx
    is_exploration = not field_feedback and not planning_ctx.options.preset_mode
    planning_templates = templates[:1] if is_exploration else templates
    enabled_templates: list[TemplateCandidate] = []
    filtered_templates = 0
    for template in planning_templates:
        if not is_template_selected_by_filters(planning_ctx, template.name):
            continue
        if is_template_actionable(
            template=template,
            build_ctx=planning_ctx,
            field_id=field_id,
            field_name=field_name,
            field_feedback=field_feedback,
            expression_policy=expression_policy,
            prior_results=prior_results,
        ):
            enabled_templates.append(template)
        else:
            filtered_templates += 1
    pending_templates = build_pending_template_variants(
        planning_ctx,
        field,
        templates=enabled_templates,
        attempted_keys=attempted_keys,
        reserved_keys=reserved_keys or set(),
        field_feedback=field_feedback,
        services=active_services,
    )
    return pending_templates, filtered_templates, len(templates)


# ============================================================================
# 干运行计划打印函数
# ============================================================================


def print_dry_run_plan(
    *,
    args: TemplateBuildArgs,
    fields: Sequence[TemplateField],
    filters: RunFilters,
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    execution_state: ExecutionState,
    use_dataset_heuristics: bool,
    sample_limit: int = DRY_RUN_SAMPLE_LIMIT,
) -> None:
    """
    打印本轮计划执行的字段/模板，不创建任何 simulation。

    在干运行模式下打印计划执行的字段和模板信息，
    不实际创建模拟任务。

    Args:
        args: 命令行参数。
        fields: 字段列表。
        filters: 运行过滤器。
        template_library: 模板库。
        historical_state: 历史运行状态。
        execution_state: 执行状态。
        use_dataset_heuristics: 是否使用数据集启发式。
        sample_limit: 打印样本数量限制。默认为 20。

    Example:
        >>> print_dry_run_plan(
        ...     args=args,
        ...     fields=fields,
        ...     filters=filters,
        ...     template_library=library,
        ...     historical_state=history,
        ...     execution_state=state,
        ...     use_dataset_heuristics=True,
        ... )

    Note:
        - 不创建任何模拟任务
        - 打印计划字段数、模板数、禁用模板数等信息
        - 打印最多 sample_limit 个样本详情
    """
    planned_fields = 0
    planned_templates = 0
    filtered_templates = 0
    unactionable_fields = 0
    samples: list[dict[str, object]] = []
    build_ctx = build_template_build_context(
        args=args,
        fields=fields,
        template_library=template_library,
        historical_state=historical_state,
        filters=filters,
        use_dataset_heuristics=use_dataset_heuristics,
        existing_results_count=len(execution_state.result_ledger.results),
    )

    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        field_name = choose_field_name(field)
        if should_skip_field(
            field_id,
            field_name,
            filters,
            execution_state.field_queue.skipped_fields,
        ):
            continue
        pending_templates, filtered_count, _template_count = build_pending_templates_for_field(
            build_ctx,
            field,
            attempted_keys=execution_state.attempted_keys,
            prior_results=[
                *historical_state.feedback_results,
                *execution_state.result_ledger.results,
            ],
        )
        if not pending_templates:
            unactionable_fields += 1
            continue
        planned_fields += 1
        planned_templates += len(pending_templates)
        filtered_templates += filtered_count
        for entry in pending_templates:
            if len(samples) >= sample_limit:
                break
            samples.append(
                {
                    "field_id": field_id,
                    "field_name": field_name,
                    "template_name": entry.template_name,
                    "priority": entry.priority,
                    "settings": entry.variant_fingerprint,
                    "expression": entry.expression,
                }
            )

    logger.info("[dry-run] simulation creation is disabled; this is a plan only")
    logger.info("[dry-run] planned_fields=%d", planned_fields)
    logger.info("[dry-run] planned_simulations=%d", planned_templates)
    logger.info("[dry-run] filtered_templates=%d", filtered_templates)
    logger.info("[dry-run] unactionable_fields=%d", unactionable_fields)
    logger.info("[dry-run] existing_results=%d", len(execution_state.result_ledger.results))
    logger.info("[dry-run] attempted_keys=%d", len(execution_state.attempted_keys))
    for index, field in enumerate(fields[:sample_limit], start=1):
        logger.info(
            "[dry-run] field %d/%d id=%s rank=%s score=%.4f family=%s reason=%s "
            "coverage=%.4f alpha_count=%d user_count=%d",
            index,
            min(len(fields), sample_limit),
            str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
            field.get("selection_rank", "?"),
            float(field.get("selection_score", 0.0) or 0.0),
            field.get("selection_family", "unknown"),
            field.get("selection_reason", "unknown"),
            float(field.get("coverage", 0.0) or 0.0),
            int(field.get("alphaCount", 0) or 0),
            int(field.get("userCount", 0) or 0),
        )
    for index, sample in enumerate(samples, start=1):
        logger.info(
            "[dry-run] sample %d/%d field=%s template=%s priority=%d settings=%s expression=%s",
            index,
            len(samples),
            sample["field_id"],
            sample["template_name"],
            sample["priority"],
            sample["settings"],
            sample["expression"],
        )
