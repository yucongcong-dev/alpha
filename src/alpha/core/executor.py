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

import argparse
import logging
from typing import Any, Sequence

from ..analysis.feedback import (
    choose_settings_variant_budget,
    is_legacy_family_disabled,
    is_template_disabled,
    should_skip_field_template_family,
)
from ..analysis.stats import historical_template_priority_bonus
from ..config import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    SENTINEL_UNKNOWN,
)
from ..generators.expressions import build_expression_candidates
from ..generators.settings import (
    build_setting_variants,
    build_settings_fingerprint_from_payload,
)
from ..models.base import (
    ExecutionState,
    FieldTestResult,
    HistoricalRunState,
    RunFilters,
    SettingsVariant,
    TemplateBuildContext,
    TemplateLibrary,
)
from ..utils.helpers import choose_field_name, first_non_empty

logger = logging.getLogger(__name__)

# ============================================================================
# 模板队列构建函数
# ============================================================================

def build_pending_templates_for_field(
    build_ctx: TemplateBuildContext,
    field: dict[str, Any],
    *,
    template_stats: dict[str, dict[str, int]],
    attempted_keys: set[tuple[str, str, str, str]],
    prior_results: Sequence[FieldTestResult],
) -> tuple[list[tuple[str, str, int, SettingsVariant, str]], int, int]:
    """
    为单个字段构建真正可执行的模板与 settings 队列。

    根据字段信息、历史反馈和各种过滤条件，构建一个可执行的模板队列，
    包含模板名称、表达式、优先级、设置变体和指纹。
    使用 TemplateBuildContext 将 11 个参数收敛到 4 个。

    Args:
        build_ctx: 包含 args、all_fields、template_library、field_feedback 等只读配置的上下文对象。
        field: 字段元数据字典。
        template_stats: 模板统计数据。
        attempted_keys: 已尝试的模板键集合。
        prior_results: 历史测试结果列表。

    Returns:
        Tuple[List[Tuple[str, str, int, SettingsVariant, str]], int, int]: 返回一个元组，包含：
            - pending_templates: 待执行模板列表
            - disabled_templates: 禁用模板数量
            - template_count: 原始模板总数

    Note:
        - 模板按优先级降序排列
        - 已尝试的键会被跳过
    """
    args = build_ctx.args
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    field_feedback = build_ctx.field_feedback.get(field_id)
    templates = build_expression_candidates(
        field,
        build_ctx.template_library,
        args.max_templates_per_field,
        args.max_templates_per_family,
        args.legacy_similarity_penalty,
        all_fields=build_ctx.all_fields,
        field_feedback=field_feedback,
        global_failed_check_counts=build_ctx.global_failed_check_counts,
        use_dataset_heuristics=build_ctx.use_dataset_heuristics,
    )
    pending_templates: list[tuple[str, str, int, SettingsVariant, str]] = []
    disabled_templates = 0
    max_setting_variants = choose_settings_variant_budget(field_feedback)
    for template_name, expression, priority in templates:
        if build_ctx.include_templates and template_name not in build_ctx.include_templates:
            continue
        if template_name in build_ctx.exclude_templates:
            continue
        if should_skip_field_template_family(
            field_name,
            template_name,
            expression,
            use_dataset_heuristics=build_ctx.use_dataset_heuristics,
        ):
            disabled_templates += 1
            continue
        if is_template_disabled(template_name, template_stats, args.template_disable_after):
            disabled_templates += 1
            continue
        if is_legacy_family_disabled(
            template_name,
            expression,
            template_stats,
            args.disable_legacy_after,
        ):
            disabled_templates += 1
            continue
        if should_skip_expression_by_history(field_id, template_name, expression, prior_results):
            disabled_templates += 1
            continue
        effective_priority = priority + historical_template_priority_bonus(template_name, template_stats)
        for settings_variant in build_setting_variants(
            args, template_name, expression, field_feedback=field_feedback
        )[:max_setting_variants]:
            variant_fingerprint = build_settings_fingerprint_from_payload(settings_variant)
            if (field_id, template_name, expression, variant_fingerprint) in attempted_keys:
                continue
            pending_templates.append((template_name, expression, effective_priority, settings_variant, variant_fingerprint))
    pending_templates.sort(key=lambda item: (-item[2], item[0], item[1], item[4]))
    return pending_templates, disabled_templates, len(templates)


def should_skip_expression_by_history(
    field_id: str,
    template_name: str,
    expression: str,
    prior_results: Sequence[FieldTestResult],
) -> bool:
    """
    对历史上已明显偏弱的同字段同表达式，续跑时直接跳过剩余变体。

    根据历史结果判断某个表达式是否应该被跳过，
    避免浪费资源在明显偏弱的候选上。

    Args:
        field_id: 字段 ID。
        template_name: 模板名称。
        expression: Alpha 表达式。
        prior_results: 历史测试结果列表。

    Returns:
        bool: 如果应该跳过返回 True，否则返回 False。

    Example:
        >>> results = [
        ...     FieldTestResult(
        ...         field_id="sales", template_name="ts_mean_20",
        ...         expression="rank(ts_mean(sales, 20))",
        ...         submittable=False, failed_checks=[
        ...             {"name": "LOW_SHARPE", "value": -0.1},
        ...             {"name": "LOW_FITNESS", "value": -0.2}
        ...         ]
        ...     )
        ... ]
        >>> should_skip_expression_by_history("sales", "ts_mean_20", "rank(ts_mean(sales, 20))", results)
        True

    Note:
        - 如果历史结果中已有可提交的相同表达式，不跳过
        - 如果 LOW_SHARPE 和 LOW_FITNESS 都为负数，跳过
        - 如果同时有 CONCENTRATED_WEIGHT 和 LOW_SUB_UNIVERSE_SHARPE，跳过
    """
    for result in prior_results:
        if result.field_id != field_id or result.template_name != template_name or result.expression != expression:
            continue
        if result.submittable:
            return False
        failed_checks = result.failed_checks or []
        if not failed_checks:
            continue
        values = {str(check.get("name")): check.get("value") for check in failed_checks}
        low_sharpe = values.get(CHECK_LOW_SHARPE)
        low_fitness = values.get(CHECK_LOW_FITNESS)
        if isinstance(low_sharpe, (int, float)) and isinstance(low_fitness, (int, float)) and low_sharpe < 0.0 and low_fitness < 0.0:
            return True
        if CHECK_CONCENTRATED_WEIGHT in values and CHECK_LOW_SUB_UNIVERSE_SHARPE in values:
            return True
    return False


def should_skip_field(
    field_id: str,
    field_name: str,
    filters: RunFilters,
    skipped_fields_due_to_queue: set[str],
) -> bool:
    """
    判断某个字段是否应在生成模板前被直接跳过。

    根据队列拥塞状态和过滤条件判断字段是否应该被跳过。

    Args:
        field_id: 字段 ID。
        field_name: 字段名称。
        filters: 运行过滤器集合。
        skipped_fields_due_to_queue: 因队列拥塞而跳过的字段集合。

    Returns:
        bool: 如果应该跳过返回 True，否则返回 False。

    Example:
        >>> filters = RunFilters(
        ...     include_fields=set(), exclude_fields=set(),
        ...     include_templates=set(), exclude_templates=set()
        ... )
        >>> should_skip_field("sales", "sales", filters, set())
        False

        >>> skipped = {"field_123"}
        >>> should_skip_field("field_123", "test", filters, skipped)
        True

    Note:
        - 如果字段在 skipped_fields_due_to_queue 中，跳过
        - 如果 filters 指定了包含字段且字段不在其中，跳过
        - 如果字段在排除列表中，跳过
    """
    if field_id in skipped_fields_due_to_queue:
        logger.info("[skip] field=%s skipped after repeated queue-busy simulations", field_id)
        return True
    if filters.include_fields and field_id not in filters.include_fields and field_name not in filters.include_fields:
        logger.info("[skip] field=%s excluded by include-fields filter", field_id)
        return True
    if field_id in filters.exclude_fields or field_name in filters.exclude_fields:
        logger.info("[skip] field=%s excluded by exclude-fields filter", field_id)
        return True
    return False


# ============================================================================
# 干运行计划打印函数
# ============================================================================

def print_dry_run_plan(
    *,
    args: argparse.Namespace,
    fields: Sequence[dict[str, Any]],
    filters: RunFilters,
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    execution_state: ExecutionState,
    use_dataset_heuristics: bool,
    sample_limit: int = 20,
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
        ...     args=args, fields=fields, filters=filters,
        ...     template_library=library, historical_state=history,
        ...     execution_state=state, use_dataset_heuristics=True
        ... )

    Note:
        - 不创建任何模拟任务
        - 打印计划字段数、模板数、禁用模板数等信息
        - 打印最多 sample_limit 个样本详情
    """
    planned_fields = 0
    planned_templates = 0
    disabled_templates = 0
    samples: list[dict[str, Any]] = []

    build_ctx = TemplateBuildContext(
        args=args,
        all_fields=fields,
        template_library=template_library,
        field_feedback=historical_state.field_feedback,
        global_failed_check_counts=historical_state.global_failed_check_counts,
        include_templates=filters.include_templates,
        exclude_templates=filters.exclude_templates,
        use_dataset_heuristics=use_dataset_heuristics,
    )

    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        field_name = choose_field_name(field)
        if should_skip_field(field_id, field_name, filters, execution_state.skipped_fields_due_to_queue):
            continue
        pending_templates, disabled_count, template_count = build_pending_templates_for_field(
            build_ctx,
            field,
            template_stats=execution_state.template_stats,
            attempted_keys=execution_state.attempted_keys,
            prior_results=execution_state.results,
        )
        if not pending_templates and template_count == 0:
            continue
        planned_fields += 1
        planned_templates += len(pending_templates)
        disabled_templates += disabled_count
        for template_name, expression, priority, _settings_variant, variant_fingerprint in pending_templates:
            if len(samples) >= sample_limit:
                break
            samples.append(
                {
                    "field_id": field_id,
                    "field_name": field_name,
                    "template_name": template_name,
                    "priority": priority,
                    "settings": variant_fingerprint,
                    "expression": expression,
                }
            )

    logger.info("[dry-run] simulation creation is disabled; this is a plan only")
    logger.info("[dry-run] planned_fields=%d", planned_fields)
    logger.info("[dry-run] planned_simulations=%d", planned_templates)
    logger.info("[dry-run] disabled_templates=%d", disabled_templates)
    logger.info("[dry-run] existing_results=%d", len(execution_state.results))
    logger.info("[dry-run] attempted_keys=%d", len(execution_state.attempted_keys))
    for index, sample in enumerate(samples, start=1):
        logger.info(
            "[dry-run] sample %d/%d field=%s template=%s priority=%d settings=%s expression=%s",
            index, len(samples), sample['field_id'], sample['template_name'],
            sample['priority'], sample['settings'], sample['expression'],
        )
