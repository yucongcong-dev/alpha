"""Template feedback pruning and skip policies."""

from __future__ import annotations

from typing import Any

from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    FEEDBACK_STAGE_PRUNE,
    FEEDBACK_STAGE_RESIMULATE,
    FEEDBACK_TEMPLATE_MIN_PRIORITY,
    TEMPLATE_DISABLE_MIN_CONCENTRATED_WEIGHT,
    TEMPLATE_DISABLE_MIN_LOW_FITNESS,
    TEMPLATE_DISABLE_MIN_LOW_SHARPE,
    TEMPLATE_DISABLE_MIN_SIMULATED,
)
from ..config.models import DatasetExpressionPolicy
from ..config.policy import get_dataset_expression_policy, resolve_feedback_stage
from ..generators.expression_builder import _is_blacklisted_template
from ..generators.templates.classification import (
    classify_expression_family,
    classify_template_stage,
    is_legacy_family,
)
from ..generators.templates.priority import (
    dominant_failed_check_names,
)


def is_template_disabled(
    template_name: str,
    template_stats: dict[str, dict[str, int]],
    disable_after: int,
) -> bool:
    """禁用历史尝试足够多但从未产生可提交结果的模板。"""
    if disable_after <= 0:
        return False
    stat = template_stats.get(template_name)
    if not stat:
        return False
    if (
        stat.get("simulated", 0) >= TEMPLATE_DISABLE_MIN_SIMULATED
        and stat.get("submittable", 0) == 0
        and (
            (
                "mean_spread" in template_name
                and stat.get("low_sharpe", 0) >= TEMPLATE_DISABLE_MIN_LOW_SHARPE
                and stat.get("low_fitness", 0) >= TEMPLATE_DISABLE_MIN_LOW_FITNESS
            )
            or stat.get("concentrated_weight", 0) >= TEMPLATE_DISABLE_MIN_CONCENTRATED_WEIGHT
        )
    ):
        return True
    return stat["attempted"] >= disable_after and stat["submittable"] == 0


def is_legacy_family_disabled(
    template_name: str,
    expression: str,
    template_stats: dict[str, dict[str, int]],
    disable_after: int,
    *,
    template_metadata: dict[str, Any] | None = None,
) -> bool:
    """当整个 legacy 家族消耗过多预算却没有收益时进行禁用。"""
    if disable_after <= 0 or not is_legacy_family(template_name, expression, template_metadata):
        return False
    attempted = 0
    submittable = 0
    for prior_template_name, stat in template_stats.items():
        prior_metadata: dict[str, Any] = {}
        if not is_legacy_family(prior_template_name, "", prior_metadata):
            continue
        attempted += int(stat.get("attempted", 0))
        submittable += int(stat.get("submittable", 0))
    return attempted >= disable_after and submittable == 0


def _is_high_conviction_ratio(expression: str, policy: DatasetExpressionPolicy) -> bool:
    """识别策略中值得继续探索的高经济含义比值方向。"""
    lower_expr = expression.lower()
    return any(f"{left}/{right}" in lower_expr for left, right in policy.high_conviction_ratio_pairs)


def should_keep_template_for_feedback(
    template_name: str,
    expression: str,
    priority: int,
    field_feedback: dict[str, Any] | None,
    *,
    dataset_id: str = "",
    expression_policy: DatasetExpressionPolicy | None = None,
    template_metadata: dict[str, Any] | None = None,
) -> bool:
    """在字段反馈足够后剪掉低信号、低价值的模板。"""
    if not field_feedback:
        return True
    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    feedback_stage = resolve_feedback_stage(field_feedback, policy.feedback_loop_policy)
    stage_policy = (
        policy.feedback_loop_policy.resimulate
        if feedback_stage == FEEDBACK_STAGE_RESIMULATE
        else policy.feedback_loop_policy.prune
        if feedback_stage == FEEDBACK_STAGE_PRUNE
        else policy.feedback_loop_policy.generate
    )
    if not stage_policy.enable_template_pruning:
        return True

    dominant_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = dominant_failed_check_names(dominant_counts)
    family = classify_expression_family(template_name, expression, template_metadata)
    template_stage = classify_template_stage(template_name, expression, template_metadata)
    lower_name = template_name.lower()
    lower_expr = expression.lower()

    if (
        feedback_stage == FEEDBACK_STAGE_RESIMULATE
        and stage_policy.preferred_template_stages
        and template_stage not in stage_policy.preferred_template_stages
        and template_name not in policy.protected_templates
    ):
        return False
    if family in policy.always_keep_families:
        return True
    if lower_name.startswith("iter_"):
        return True
    if template_name in policy.protected_templates:
        return True
    protected_ratio = _is_high_conviction_ratio(expression, policy)

    if CHECK_LOW_TURNOVER in dominant_names:
        if lower_name.startswith(policy.slow_template_prefixes):
            return False
        if lower_name in policy.slow_template_names:
            return False
        if "ts_mean(" in lower_expr and "-" not in lower_expr and "/" not in lower_expr:
            return False
        if (
            "ts_backfill(" in lower_expr
            and "ts_delta" not in lower_expr
            and "ts_zscore" not in lower_expr
        ):
            return False

    if (
        CHECK_LOW_SUB_UNIVERSE_SHARPE in dominant_names
        or CHECK_CONCENTRATED_WEIGHT in dominant_names
    ):
        if family in policy.concentrated_weak_families and not protected_ratio:
            return False
        if lower_name.startswith(policy.concentrated_weak_prefixes) and not protected_ratio:
            return False
        if lower_name in policy.concentrated_weak_names:
            return False

    field_low_sharpe = int(dominant_counts.get(CHECK_LOW_SHARPE, 0))
    if (
        field_low_sharpe >= policy.low_sharpe_ratio_fail_threshold
        and family in policy.low_sharpe_weak_ratio_families
        and not protected_ratio
    ):
        return False
    if (
        lower_name.startswith(policy.low_sharpe_weak_ratio_prefixes)
        and field_low_sharpe >= policy.low_sharpe_ratio_fail_threshold
        and not protected_ratio
    ):
        return False

    if (
        CHECK_HIGH_TURNOVER in dominant_names
        and CHECK_CONCENTRATED_WEIGHT in dominant_names
        and family in {"rank_spread", "mean_spread"}
        and "zscore" in lower_name
        and "spread" in lower_name
    ):
        return False

    return priority >= FEEDBACK_TEMPLATE_MIN_PRIORITY


def should_skip_field_template_family(
    field_name: str,
    template_name: str,
    expression: str,
    *,
    use_dataset_heuristics: bool | None = None,
    dataset_id: str = "",
    expression_policy: DatasetExpressionPolicy | None = None,
    template_metadata: dict[str, Any] | None = None,
) -> bool:
    """对已经证明偏弱的字段-模板家族组合做先验剪枝。"""
    policy = expression_policy or get_dataset_expression_policy(
        dataset_id,
        use_curated_heuristics=use_dataset_heuristics,
    )
    if not policy.use_curated_heuristics:
        return False

    if _is_blacklisted_template(
        template_name,
        expression,
        template_metadata=template_metadata,
        policy=policy,
    ):
        return True

    family = classify_expression_family(template_name, expression, template_metadata)

    if field_name in policy.weak_mean_spread_fields and family in {
        "group_mean_spread",
        "mean_spread",
        "rank_spread",
    }:
        return True
    return (
        field_name in policy.broken_zscore_spread_fields
        and "zscore" in template_name.lower()
        and "spread" in template_name.lower()
    ) or (
        field_name in policy.weak_ratio_standalone_fields
        and family in {"legacy_ratio", "legacy_neg_ratio", "group_ratio_level"}
    )
