"""
测试执行流程模块

本模块是 Alpha 测试执行的高层协调模块，
负责任务队列构建、字段过滤和干运行计划等功能。

实际的模拟生命周期管理由 simulation.py 负责，
并发调度与拥塞控制由 scheduler_draining.py 与 scheduler_concurrency.py 负责。

模块内容：
    - 模板队列构建函数
    - 历史跳过判断函数
    - 字段跳过判断函数
    - 干运行计划打印函数
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from concurrent.futures import Future
from dataclasses import replace
import logging
import zlib

from ..config.models import DatasetExpressionPolicy
from ..config.static_config import get_static_config
from ..generators.fields import choose_field_name, choose_field_type
from ..generators.templates.metadata import normalize_template_role
from ..models.domain import FieldTestResult, TemplateCandidate, TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_options import TemplateBuildOptions
from ..runtime.contexts import (
    HistoricalRunState,
    PendingFutureContext,
    PendingTemplateEntry,
    TemplateBuildContext,
    TemplateFeedbackContext,
    TemplateSourceContext,
)
from ..runtime.preset_mode import resolve_preset_mode
from ..runtime.state import ExecutionState
from ..utils.helpers import first_non_empty
from . import executor_dry_run as _dry_run
from .execution_filters import (
    resolve_field_skip_reason,
    resolve_template_skip_reason,
    should_skip_field,
)
from .execution_filters import (
    should_skip_expression_by_history as should_skip_expression_by_history,
)
from .template_planning import (
    TemplatePlanningServices,
    build_pending_template_variants,
    build_template_planning_services,
    resolve_field_template_candidates,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 模板队列构建函数
# ============================================================================


def _ordered_exploration_templates(
    templates: Sequence[TemplateCandidate],
    *,
    field_id: str,
) -> list[TemplateCandidate]:
    """Put deterministic, field-distributed seeds before distributed fallbacks."""

    def rotate(candidates: list[TemplateCandidate]) -> list[TemplateCandidate]:
        if len(candidates) < 2:
            return candidates
        offset = zlib.crc32(field_id.encode("utf-8")) % len(candidates)
        return [*candidates[offset:], *candidates[:offset]]

    seeds = [
        template
        for template in templates
        if normalize_template_role(template.metadata.get("role")) == "default_seed"
    ]
    fallback = [template for template in templates if template not in seeds]
    return [*rotate(seeds), *rotate(fallback)]


def build_template_build_context(
    *,
    options: TemplateBuildOptions,
    fields: Sequence[TemplateField],
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    filters: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    existing_results_count: int,
) -> TemplateBuildContext:
    """Construct the shared template build context for dry-run and live execution."""
    options = replace(
        options,
        preset_mode=options.preset_mode
        or resolve_preset_mode(
            template_library_file=options.template_library_file,
            include_fields=filters.include_fields,
        ),
    )
    template_build_ctx = TemplateBuildContext(
        source=TemplateSourceContext(
            options=options,
            template_library_file=options.template_library_file,
            all_fields=fields,
            template_library=template_library,
            include_templates=filters.include_templates,
            exclude_templates=filters.exclude_templates,
            expression_policy=expression_policy,
        ),
        feedback=TemplateFeedbackContext(
            field_feedback=historical_state.field_feedback,
            global_failed_check_counts=historical_state.global_failed_check_counts,
            feedback_template_min_priority=options.feedback_template_min_priority,
        ),
    )
    template_build_ctx.feedback.feedback_result_count = existing_results_count
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
        field_id = str(first_non_empty(context.field_id, get_static_config().sentinel_unknown))
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
    template_skip_reasons: MutableMapping[str, int] | None = None,
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
    active_services = planning_services or build_template_planning_services()
    field_id = str(first_non_empty(field.field_id, get_static_config().sentinel_unknown))
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    templates, field_feedback, expression_policy = resolve_field_template_candidates(
        build_ctx,
        field,
        services=active_services,
    )
    # Exploration stays cheap at one candidate, but explicit seeds must be
    # selected before priority-based refine candidates. Rotate both seed and
    # fallback pools so blacklisted seeds cannot collapse broad coverage back
    # onto one high-priority structure.
    planning_ctx = build_ctx
    is_exploration = not field_feedback and not planning_ctx.source.options.preset_mode
    planning_templates = (
        _ordered_exploration_templates(templates, field_id=field_id)
        if is_exploration
        else templates
    )
    enabled_templates: list[TemplateCandidate] = []
    filtered_templates = 0
    for template in planning_templates:
        skip_reason = resolve_template_skip_reason(
            template=template,
            build_ctx=planning_ctx,
            field_id=field_id,
            field_name=field_name,
            field_type=field_type,
            field_feedback=field_feedback,
            expression_policy=expression_policy,
            prior_results=prior_results,
        )
        if skip_reason == "name_filter":
            if template_skip_reasons is not None:
                template_skip_reasons["template_filtered_name_filter"] = (
                    template_skip_reasons.get("template_filtered_name_filter", 0) + 1
                )
            continue
        if skip_reason is None:
            enabled_templates.append(template)
            if is_exploration:
                break
        else:
            filtered_templates += 1
            if template_skip_reasons is not None:
                key = f"template_filtered_{skip_reason}"
                template_skip_reasons[key] = template_skip_reasons.get(key, 0) + 1
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
    options: TemplateBuildOptions,
    fields: Sequence[TemplateField],
    filters: RunFilters,
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    execution_state: ExecutionState,
    expression_policy: DatasetExpressionPolicy,
    full_run: bool,
    max_new_simulations: int,
    sample_limit: int | None = None,
) -> None:
    """
    打印本轮计划执行的字段/模板，不创建任何 simulation。

    在干运行模式下打印计划执行的字段和模板信息，
    不实际创建模拟任务。

    Args:
        options: 模板构建配置。
        fields: 字段列表。
        filters: 运行过滤器。
        template_library: 模板库。
        historical_state: 历史运行状态。
        execution_state: 执行状态。
        expression_policy: bootstrap 阶段冻结的数据集表达式策略。
        sample_limit: 打印样本数量限制。默认为 20。
        full_run: 是否优先安排未完成的 seed 字段。
        max_new_simulations: 本轮 simulation 预算；0 表示不限制。

    Example:
        >>> print_dry_run_plan(
        ...     options=options,
        ...     fields=fields,
        ...     filters=filters,
        ...     template_library=library,
        ...     historical_state=history,
        ...     execution_state=state,
        ...     expression_policy=expression_policy,
        ...     full_run=False,
        ...     max_new_simulations=0,
        ... )

    Note:
        - 不创建任何模拟任务
        - 打印计划字段数、模板数、禁用模板数等信息
        - 打印最多 sample_limit 个样本详情
    """
    if sample_limit is None:
        sample_limit = get_static_config().dry_run_sample_limit
    _dry_run.print_dry_run_plan(
        options=options,
        fields=fields,
        filters=filters,
        template_library=template_library,
        historical_state=historical_state,
        execution_state=execution_state,
        expression_policy=expression_policy,
        build_context=build_template_build_context,
        should_skip=should_skip_field,
        resolve_skip_reason=resolve_field_skip_reason,
        build_pending=build_pending_templates_for_field,
        sample_limit=sample_limit,
        log=logger,
        full_run=full_run,
        max_new_simulations=max_new_simulations,
    )
