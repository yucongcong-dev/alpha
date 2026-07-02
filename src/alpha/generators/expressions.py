"""
表达式构建模块

本模块负责构建、排序和管理 Alpha 表达式候选，包括字段配对发现、
模板优先级调整、表达式家族分类等功能。通过智能的表达式生成策略，
提高 Alpha 发现的效率和质量。

模块内容：
    - tokenize_field_name(): 将字段名拆分为 token
    - score_partner_candidate(): 评估字段配对得分
    - discover_partner_fields(): 发现配对字段
    - sort_templates_by_priority(): 按优先级排序模板
    - limit_templates(): 限制模板数量
    - classify_expression_family(): 分类表达式家族
    - is_legacy_family(): 判断是否为 legacy 家族
    - apply_similarity_penalty(): 应用相似度惩罚
    - adaptive_template_priority_adjustment(): 自适应优先级调整
    - apply_adaptive_priority(): 应用自适应优先级
    - cap_templates_per_family(): 限制家族模板数量
    - build_expression_candidates(): 构建表达式候选
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config import (
    ALLOWED_EXTERNAL_RATIO_PARTNERS,
    DELTA_STD_PRIORITY_BOOST,
    DatasetExpressionPolicy,
    TEMPLATE_STAGE_EVENT_CONDITIONED,
    TEMPLATE_STAGE_FIRST_ORDER,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
    get_dataset_expression_policy,
    get_backfill_window,
    resolve_feedback_stage,
)
from ..generators.field_transforms import build_field_view, build_ratio_expression
from ..generators.partner_fields import (
    discover_partner_fields,
    score_partner_candidate as score_partner_candidate,
    tokenize_field_name as tokenize_field_name,
)
from ..generators.template_candidates import (
    _candidate_metadata,
    _coerce_template_candidate,
    _make_template_candidate,
    _render_template_specs,
)
from ..generators.template_classification import (
    classify_expression_family,
    classify_template_stage,
    is_legacy_family,
)
from ..generators.template_metadata import (
    TemplateMetadataMap,
    _runtime_template_metadata,
    _select_template_items,
    build_template_metadata_index,
    get_template_metadata,
)
from ..generators.template_priority import (
    adaptive_template_priority_adjustment as adaptive_template_priority_adjustment,
    apply_adaptive_priority,
    apply_similarity_penalty,
    cap_templates_per_family,
    dominant_failed_check_names as dominant_failed_check_names,
    merge_failed_check_counts as merge_failed_check_counts,
)
from ..generators.template_refine import build_refine_templates
from ..generators.template_variations import (
    build_bucket_group_templates,
    build_feedback_mutations,
    build_historical_reuse_templates,
    build_trade_when_templates,
    invert_expression,
)
from ..models.base import TemplateCandidate, TemplateLibrary
from ..policy import template_blacklist as _template_blacklist_policy
from ..policy.template_blacklist import (
    _BLACKLIST_CACHE,
    _DEFAULT_AVOID_RULES_CACHE,
    _load_default_avoid_rules as _policy_load_default_avoid_rules,
    blacklist_match_reason as _policy_blacklist_match_reason,
    invalidate_blacklist_cache,
)
from ..utils.helpers import choose_field_name, choose_field_type, is_event_field_name

_BUCKET_GROUP_SPECS: tuple[tuple[str, str, int], ...] = (
    ("cap_bucket", "bucket(rank(cap), range='0.1, 1, 0.1')", 174),
    ("asset_bucket", "bucket(rank(assets), range='0.1, 1, 0.1')", 172),
    ("volatility_bucket", "bucket(rank(ts_std_dev(returns, 20)), range='0.1, 1, 0.1')", 170),
    ("liquidity_bucket", "bucket(rank(close * volume), range='0.1, 1, 0.1')", 168),
)
"""从旧回测脚本吸收的通用 bucket 分组维度，控制数量避免候选爆炸。"""

_TRADE_WHEN_EVENT_SPECS: tuple[tuple[str, str, int], ...] = (
    ("volume_expansion", "ts_mean(volume, 10) > ts_mean(volume, 60)", 166),
    ("price_breakout_20", "ts_arg_max(close, 20) == 0", 164),
    ("return_zscore_high", "ts_zscore(returns, 60) > 2", 162),
    ("high_volatility_sector", "group_rank(ts_std_dev(returns, 60), sector) > 0.7", 160),
)
"""从旧回测脚本吸收的事件开关，用于降低噪声和改善 turnover。"""


def _load_default_avoid_rules() -> list[dict[str, str]]:
    """兼容导出：加载跨数据集默认规避规则。"""
    if _DEFAULT_AVOID_RULES_CACHE is None:
        _template_blacklist_policy._DEFAULT_AVOID_RULES_CACHE = None
    return _policy_load_default_avoid_rules()


def _policy_template_priority_adjustment(
    template_name: str,
    policy: DatasetExpressionPolicy,
) -> int:
    """按数据集策略调整模板优先级。"""
    lower_name = template_name.lower()
    adjustment = policy.account_template_boost if lower_name.startswith("account_") else 0
    if lower_name in policy.template_priority_penalties:
        adjustment += policy.template_priority_penalties[lower_name]
        return adjustment
    for prefixes, penalty in policy.template_prefix_penalties.items():
        if lower_name.startswith(prefixes):
            adjustment += penalty
            return adjustment
    return adjustment


def _is_event_field(field_name: str, policy: DatasetExpressionPolicy) -> bool:
    """按策略前缀判断字段是否属于事件类字段。"""
    return is_event_field_name(field_name, policy.event_field_prefixes)


def _event_template_allowed(
    candidate: TemplateCandidate,
    policy: DatasetExpressionPolicy,
) -> bool:
    """事件字段只保留更窄的模板池，避免高噪音模板占预算。"""
    if not (
        policy.event_allowed_template_stages
        or policy.event_allowed_template_prefixes
        or policy.event_allowed_template_families
    ):
        return True
    name = candidate.name
    family = classify_expression_family(name, candidate.expression, candidate.metadata)
    stage = classify_template_stage(name, candidate.expression, candidate.metadata)
    if policy.event_allowed_template_stages and stage in policy.event_allowed_template_stages:
        return True
    if policy.event_allowed_template_families and family in policy.event_allowed_template_families:
        return True
    if policy.event_allowed_template_prefixes and any(
        name.startswith(prefix) for prefix in policy.event_allowed_template_prefixes
    ):
        return True
    return False


def _is_blacklisted_template(
    template_name: str,
    expression: str = "",
    *,
    template_metadata: dict[str, Any] | None = None,
    dataset_id: str = "",
    policy: DatasetExpressionPolicy | None = None,
) -> bool:
    return (
        _blacklist_match_reason(
            template_name,
            expression,
            template_metadata=template_metadata,
            dataset_id=dataset_id,
            policy=policy,
        )
        is not None
    )


def _blacklist_match_reason(
    template_name: str,
    expression: str = "",
    *,
    template_metadata: dict[str, Any] | None = None,
    dataset_id: str = "",
    policy: DatasetExpressionPolicy | None = None,
) -> str | None:
    """检查模板名称或表达式是否在指定数据集的黑名单中。

    Args:
        template_name: 模板名称。
        expression: 表达式文本（用于模式匹配）。
        dataset_id: 数据集 ID。为空时仅检查跨数据集默认规则。

    Returns:
        bool: 在黑名单中返回 True。
    """
    effective_dataset_id = policy.dataset_id if policy is not None else dataset_id
    protected_templates = policy.protected_templates if policy is not None else set()
    blocked_name_substrings = (
        policy.blacklisted_template_name_substrings if policy is not None else ()
    )
    current_family = classify_expression_family(template_name, expression, template_metadata)
    current_stage = classify_template_stage(template_name, expression, template_metadata)
    return _policy_blacklist_match_reason(
        template_name,
        expression,
        dataset_id=effective_dataset_id,
        current_family=current_family,
        current_stage=current_stage,
        has_runtime_context=bool(template_metadata or expression),
        protected_templates=set(protected_templates),
        blocked_name_substrings=tuple(blocked_name_substrings),
    )


def sort_templates_by_priority(
    templates: Sequence[TemplateCandidate | tuple[str, str, int]],
) -> list[TemplateCandidate]:
    """
    按有效优先级从高到低排序候选模板。

    优先级越高（数值越大）的模板排序越靠前，优先被测试。
    这样可以让最可能成功的模板先运行，提高整体效率。

    Args:
        templates (Sequence[tuple[str, str, int]]): 模板列表，
            每个元素为 (name, expression, priority) 元组。

    Returns:
        list[tuple[str, str, int]]: 排序后的模板列表。

    Example:
        >>> templates = [("low", "expr1", 10), ("high", "expr2", 100), ("mid", "expr3", 50)]
        >>> sorted_templates = sort_templates_by_priority(templates)
        >>> print(sorted_templates[0][0])
        'high'
    """
    # Higher-priority templates run first so likely winners are tested earlier.
    normalized = [_coerce_template_candidate(template) for template in templates]
    return sorted(normalized, key=lambda item: (-item.priority, item.name, item.expression))


def limit_templates(
    templates: list[TemplateCandidate | tuple[str, str, int]],
    max_templates_per_field: int,
) -> list[TemplateCandidate]:
    """
    在排序与多样化之后应用字段级模板数量上限。

    通过硬性限制每个字段最多测试的模板数量，控制测试规模
    和资源消耗。

    Args:
        templates (list[tuple[str, str, int]]): 已排序的模板列表。
        max_templates_per_field (int): 每个字段的模板数量上限。
            如果为 0 或负数，不限制数量。

    Returns:
        list[tuple[str, str, int]]: 限制后的模板列表。

    Example:
        >>> templates = [("t1", "e1", 10), ("t2", "e2", 20), ("t3", "e3", 30)]
        >>> limited = limit_templates(templates, max_templates_per_field=2)
        >>> print(len(limited))
        2
    """
    normalized = [_coerce_template_candidate(template) for template in templates]
    if max_templates_per_field <= 0:
        return normalized
    return normalized[:max_templates_per_field]


def build_high_conviction_ratio_templates(
    ratio_expr: str,
    ratio_label: str,
    *,
    priority_boost: int = 0,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> list[TemplateCandidate]:
    """为财务含义强的 ratio pair 生成专属长窗质量模板。"""
    bw = get_backfill_window()
    specs: tuple[tuple[str, str, int, str, str], ...] = (
        (
            "hc_ratio_group_level_{ratio_label}",
            "group_rank({ratio_expr}, subindustry)",
            228,
            "high_conviction_ratio",
            TEMPLATE_STAGE_GROUP_SECOND_ORDER,
        ),
        (
            "hc_ratio_group_zscore_252_{ratio_label}",
            "group_rank(ts_zscore({ratio_expr}, 252), subindustry)",
            226,
            "high_conviction_ratio",
            TEMPLATE_STAGE_GROUP_SECOND_ORDER,
        ),
        (
            "hc_ratio_decay_zscore_252_{ratio_label}",
            "ts_decay_linear(group_rank(ts_zscore({ratio_expr}, 252), subindustry), 20)",
            224,
            "high_conviction_ratio",
            TEMPLATE_STAGE_GROUP_SECOND_ORDER,
        ),
        (
            "hc_ratio_industry_zscore_252_{ratio_label}",
            "group_rank(ts_zscore({ratio_expr}, 252), industry)",
            222,
            "high_conviction_ratio",
            TEMPLATE_STAGE_GROUP_SECOND_ORDER,
        ),
    )
    templates: list[TemplateCandidate] = []
    for name_template, expr_template, priority, family, stage in specs:
        name = name_template.format(ratio_label=ratio_label)
        expr = expr_template.format(ratio_expr=ratio_expr, backfill_window=bw)
        template = _make_template_candidate(
            name,
            expr,
            priority + priority_boost,
            metadata=_candidate_metadata(
                family=family,
                layer="group",
                stage=stage,
                requires_partner_field=True,
            ),
        )
        if not _is_blacklisted_template(
            template.name,
            template.expression,
            template_metadata=template.metadata,
            policy=expression_policy,
        ):
            templates.append(template)
    return templates


def _build_matrix_templates(
    field_view: Any,
    all_fields: Sequence[dict[str, Any]],
    expression_policy: DatasetExpressionPolicy,
) -> tuple[list[TemplateCandidate], list[TemplateCandidate]]:
    """为 MATRIX 类型字段构建多样化和 legacy 模板候选。

    Returns:
        (diversified_templates, legacy_templates) 两个列表。
    """
    field_name = field_view.field_name
    preprocessed_expression = field_view.preprocessed_expression
    backfill_window = expression_policy.matrix_field_transform.backfill_window or get_backfill_window()
    delta_over_std_windows = expression_policy.matrix_delta_over_std_windows

    diversified: list[TemplateCandidate] = []
    for delta, std, pri in delta_over_std_windows:
        diversified.append(
            _make_template_candidate(
                f"group_delta_over_std_subindustry_{delta}_{std}",
                f"group_rank(ts_delta({preprocessed_expression}, {delta}) / ts_std_dev({preprocessed_expression}, {std}), subindustry)",
                pri + DELTA_STD_PRIORITY_BOOST,
                metadata=_candidate_metadata(
                    family="group_vol_scaled_delta",
                    layer="group",
                    stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                ),
            )
        )

    diversified_specs = expression_policy.matrix_diversified_template_specs
    diversified.extend(
        [
            _make_template_candidate(
                candidate.name,
                candidate.expression,
                candidate.priority + DELTA_STD_PRIORITY_BOOST
                if "delta_over_std" in candidate.name
                else candidate.priority,
                metadata=candidate.metadata,
            )
            for candidate in _render_template_specs(
                diversified_specs,
                field=field_name,
                field_preprocessed=preprocessed_expression,
                backfill_window=backfill_window,
            )
        ]
    )
    diversified.extend(
        build_bucket_group_templates(
            preprocessed_expression,
            name_prefix="bucket",
        )
    )
    diversified.extend(
        build_trade_when_templates(
            f"rank({preprocessed_expression})",
            name_prefix="event",
        )
    )

    legacy: list[TemplateCandidate] = [
        _make_template_candidate(
            "raw_field",
            preprocessed_expression,
            145,
            metadata=_candidate_metadata(
                family="legacy_level",
                layer="first_order",
                stage=TEMPLATE_STAGE_FIRST_ORDER,
            ),
        ),
        _make_template_candidate(
            "group_rank_subindustry",
            f"group_rank({preprocessed_expression}, subindustry)",
            143,
            metadata=_candidate_metadata(
                family="legacy_group_level",
                layer="group",
                stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
            ),
        ),
        _make_template_candidate(
            "group_rank_industry",
            f"group_rank({preprocessed_expression}, industry)",
            141,
            metadata=_candidate_metadata(
                family="legacy_group_level",
                layer="group",
                stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
            ),
        ),
        _make_template_candidate(
            "rank_raw_field",
            f"rank({preprocessed_expression})",
            118,
            metadata=_candidate_metadata(
                family="legacy_level",
                layer="first_order",
                stage=TEMPLATE_STAGE_FIRST_ORDER,
            ),
        ),
    ]
    if expression_policy.use_curated_heuristics and field_name in expression_policy.positive_raw_fields:
        legacy.append(
            _make_template_candidate(
                "neg_raw_field",
                f"-{preprocessed_expression}",
                132,
                metadata=_candidate_metadata(
                    family="legacy_level",
                    layer="first_order",
                    stage=TEMPLATE_STAGE_FIRST_ORDER,
                ),
            )
        )
    elif expression_policy.use_curated_heuristics and field_name in expression_policy.negative_raw_fields:
        legacy.append(
            _make_template_candidate(
                "neg_raw_field",
                f"-{preprocessed_expression}",
                144,
                metadata=_candidate_metadata(
                    family="legacy_level",
                    layer="first_order",
                    stage=TEMPLATE_STAGE_FIRST_ORDER,
                ),
            )
        )
    elif expression_policy.use_curated_heuristics:
        legacy.append(
            _make_template_candidate(
                "neg_raw_field",
                f"-{preprocessed_expression}",
                128,
                metadata=_candidate_metadata(
                    family="legacy_level",
                    layer="first_order",
                    stage=TEMPLATE_STAGE_FIRST_ORDER,
                ),
            )
        )

    # 比率配对模板
    fields_by_name = {choose_field_name(item): item for item in all_fields}
    partner_names = discover_partner_fields(
        field_name,
        all_fields,
        expression_policy,
        limit=expression_policy.partner_limit,
    )

    ratio_delta_rank_windows = expression_policy.ratio_delta_rank_windows
    ratio_delta_over_std_windows = expression_policy.ratio_delta_over_std_windows

    for partner in partner_names:
        if partner not in fields_by_name and partner not in ALLOWED_EXTERNAL_RATIO_PARTNERS:
            continue
        denominator_view = (
            build_field_view(fields_by_name[partner], expression_policy)
            if partner in fields_by_name
            else None
        )
        ratio_expr = (
            build_ratio_expression(field_view, denominator_view)
            if denominator_view is not None
            else f"{field_view.ratio_numerator_expression}/{partner}"
        )
        ratio_label = f"{field_name}_over_{partner}"
        ratio_priority_boost = 0
        if (field_name, partner) in expression_policy.high_conviction_ratio_pairs:
            ratio_priority_boost = expression_policy.high_conviction_ratio_priority_boost
            diversified.extend(
                build_high_conviction_ratio_templates(
                    ratio_expr,
                    ratio_label,
                    priority_boost=ratio_priority_boost,
                    expression_policy=expression_policy,
                )
            )

        # Delta rank 变体
        for delta, pri in ratio_delta_rank_windows:
            name = f"group_ratio_delta_rank_{delta}_{ratio_label}"
            expr = f"group_rank(ts_delta(rank({ratio_expr}), {delta}), subindustry)"
            if not _is_blacklisted_template(name, expr, policy=expression_policy):
                diversified.append(
                    _make_template_candidate(
                        name,
                        expr,
                        pri + DELTA_STD_PRIORITY_BOOST + ratio_priority_boost,
                        metadata=_candidate_metadata(
                            family="group_ratio_level",
                            layer="group",
                            stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                            requires_partner_field=True,
                        ),
                    )
                )

        # Delta over std 变体
        for delta, std, pri in ratio_delta_over_std_windows:
            diversified.append(
                _make_template_candidate(
                    f"group_ratio_delta_over_std_{delta}_{std}_{ratio_label}",
                    f"group_rank(ts_delta({ratio_expr}, {delta}) / ts_std_dev({ratio_expr}, {std}), subindustry)",
                    pri + DELTA_STD_PRIORITY_BOOST + ratio_priority_boost,
                    metadata=_candidate_metadata(
                        family="group_vol_scaled_delta",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                        requires_partner_field=True,
                    ),
                )
            )

        ratio_diversified_specs = expression_policy.ratio_diversified_template_specs
        diversified.extend(
            [
                _make_template_candidate(
                    candidate.name,
                    candidate.expression,
                    candidate.priority + ratio_priority_boost,
                    metadata={
                        **candidate.metadata,
                        "requires_partner_field": True,
                    },
                )
                for candidate in _render_template_specs(
                    ratio_diversified_specs,
                    ratio_expr=ratio_expr,
                    ratio_label=ratio_label,
                    field_preprocessed=preprocessed_expression,
                    backfill_window=backfill_window,
                )
            ]
        )

        legacy.extend(
            [
                _make_template_candidate(
                    candidate.name,
                    candidate.expression,
                    candidate.priority + ratio_priority_boost,
                    metadata={
                        **candidate.metadata,
                        "requires_partner_field": True,
                    },
                )
                for candidate in _render_template_specs(
                    expression_policy.ratio_legacy_template_specs,
                    ratio_expr=ratio_expr,
                    ratio_label=ratio_label,
                    field_preprocessed=preprocessed_expression,
                    backfill_window=backfill_window,
                )
            ]
        )

    return diversified, legacy


def build_expression_candidates(
    field: dict[str, Any],
    template_library: TemplateLibrary,
    max_templates_per_field: int,
    max_templates_per_family: int,
    legacy_similarity_penalty: int,
    all_fields: Sequence[dict[str, Any]] | None = None,
    field_feedback: dict[str, Any] | None = None,
    global_failed_check_counts: dict[str, int] | None = None,
    use_dataset_heuristics: bool = True,
    *,
    dataset_id: str = "",
    expression_policy: DatasetExpressionPolicy | None = None,
) -> list[TemplateCandidate]:
    """
    为单个字段构建、变异、多样化并排序表达式候选。

    这是表达式构建的核心函数，整合了模板选择、变异生成、
    优先级调整和数量限制等多个步骤。

    Args:
        field (dict[str, Any]): 字段元数据。
        template_library (TemplateLibrary): 模板库字典。
        max_templates_per_field (int): 每个字段的模板数量上限。
        max_templates_per_family (int): 每个家族的模板数量上限。
        legacy_similarity_penalty (int): legacy 家族的相似度惩罚。
        all_fields (Sequence[dict[str, Any]] | None): 所有可用字段列表。
        field_feedback (dict[str, Any] | None): 字段反馈数据。
        global_failed_check_counts (dict[str, int] | None): 全局失败检查计数。
        use_dataset_heuristics (bool): 是否使用数据集启发式规则。
        dataset_id (str): 兼容保留；未显式传 expression_policy 时用于生成策略。
        expression_policy: 数据集表达式策略；推荐由调用方显式传入。

    Returns:
        list[tuple[str, str, int]]: 最终的表达式候选列表，
            每个元素为 (name, expression, priority) 元组。

    处理步骤：
        1. 从模板库选择基础模板
        2. 添加反馈驱动的变异
        3. 对于 MATRIX 类型字段，添加多样化的模板
        4. 添加 legacy 模板（原始字段、分组排名等）
        5. 为比率型模板发现配对字段
        6. 应用相似度惩罚
        7. 应用自适应优先级调整
        8. 按优先级排序
        9. 限制每个家族的模板数量
        10. 限制总数

    Example:
        >>> candidates = build_expression_candidates(
        ...     field={"id": "sales", "type": "MATRIX"},
        ...     template_library=load_template_library(""),
        ...     max_templates_per_field=50,
        ...     max_templates_per_family=10,
        ...     legacy_similarity_penalty=30,
        ...     all_fields=[{"id": "cap", "type": "MATRIX"}],
        ...     use_dataset_heuristics=True,
        ... )
        >>> print(len(candidates))
        50  # 限制后最多 50 个候选
    """
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    all_fields = all_fields or []
    global_failed_check_counts = global_failed_check_counts or {}
    policy = expression_policy or get_dataset_expression_policy(
        dataset_id,
        use_curated_heuristics=use_dataset_heuristics,
    )
    feedback_stage = resolve_feedback_stage(field_feedback, policy.feedback_loop_policy)
    field_view = build_field_view(field, policy)
    is_event_field = _is_event_field(field_name, policy)

    # Template selection is now driven by an externalizable library so we can
    # expand or shrink search coverage between runs without changing code.
    raw_templates = _select_template_items(template_library, field_type, policy.dataset_id)
    templates = [
        _make_template_candidate(
            str(item["name"]),
            str(item["expression"]).format(
                field=field_view.raw_expression,
                field_preprocessed=field_view.preprocessed_expression,
                ratio_numerator=field_view.ratio_numerator_expression,
                ratio_denominator=field_view.ratio_denominator_expression,
                backfill_window=get_backfill_window(),
            ),
            int(item.get("priority", 0))
            + _policy_template_priority_adjustment(str(item["name"]), policy),
            metadata=_runtime_template_metadata(item),
        )
        for item in raw_templates
        if isinstance(item, dict)
        and "name" in item
        and "expression" in item
        and str(item["name"]) not in policy.disabled_templates
        and not _is_blacklisted_template(
            str(item["name"]),
            str(item["expression"]),
            template_metadata=_runtime_template_metadata(item),
            policy=policy,
        )
    ]
    templates.extend(
        build_feedback_mutations(
            field_name,
            field_feedback,
            expression_policy=policy,
            feedback_stage=feedback_stage,
        )
    )

    if field_type == "MATRIX":
        diversified, legacy = _build_matrix_templates(
            field_view,
            all_fields,
            policy,
        )
        templates.extend(diversified)
        templates.extend(legacy)

    if is_event_field:
        templates = [item for item in templates if _event_template_allowed(item, policy)]

    templates = apply_similarity_penalty(
        templates,
        legacy_similarity_penalty,
    )
    templates = apply_adaptive_priority(
        templates,
        field_feedback=field_feedback,
        global_failed_check_counts=global_failed_check_counts,
    )
    templates = sort_templates_by_priority(templates)
    return limit_templates(
        cap_templates_per_family(
            templates,
            max_templates_per_family,
        ),
        max_templates_per_field,
    )
