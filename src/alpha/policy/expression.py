"""Dataset expression policy construction and feedback-stage resolution."""

from __future__ import annotations

from typing import Any

from ..config.models import (
    DatasetExpressionPolicy,
    FeedbackLoopPolicy,
    FeedbackPhasePolicy,
    FieldTransformSpec,
    FieldTransformStage,
)
from ..config.policy_overrides import apply_yaml_expression_policy_overrides
from ..config.static_config import get_static_config
from ..models.domain_types import FieldFeedbackSummary


def _default_feedback_loop_policy() -> FeedbackLoopPolicy:
    """Build the default generate/resimulate feedback policy."""
    return FeedbackLoopPolicy(
        generate=FeedbackPhasePolicy(
            min_attempted_templates=0,
            min_best_score=get_static_config().stats_default_score,
            settings_variant_budget=1,
        ),
        resimulate=FeedbackPhasePolicy(
            min_attempted_templates=3,
            min_best_score=get_static_config().feedback_mutation_highscore_threshold,
            settings_variant_budget=3,
            enable_template_pruning=True,
            preferred_template_stages=(
                get_static_config().template_stage_group_second_order,
                get_static_config().template_stage_event_conditioned,
            ),
        ),
    )


def _base_expression_policy(
    dataset_id: str,
    *,
    default_backfill_window: int,
    use_curated_heuristics: bool,
) -> DatasetExpressionPolicy:
    """Build a base policy before YAML overrides are applied."""
    backfill_transform = FieldTransformSpec(
        stages=(FieldTransformStage(kind="backfill", window=default_backfill_window),),
        backfill_window=default_backfill_window,
    )
    policy_kwargs: dict[str, Any] = {
        "dataset_id": dataset_id,
        "use_curated_heuristics": use_curated_heuristics,
        "partner_limit": 4,
        "matrix_delta_over_std_windows": get_static_config().default_matrix_delta_over_std_windows,
        "matrix_diversified_template_specs": get_static_config().default_matrix_diversified_template_specs,
        "ratio_delta_rank_windows": get_static_config().default_ratio_delta_rank_windows,
        "ratio_delta_over_std_windows": get_static_config().default_ratio_delta_over_std_windows,
        "ratio_diversified_template_specs": get_static_config().default_ratio_diversified_template_specs,
        "ratio_legacy_template_specs": get_static_config().ratio_legacy_template_specs,
        "ratio_partner_candidates": dict(get_static_config().ratio_partner_candidates),
        "ratio_keywords": dict(get_static_config().ratio_keywords),
        "preferred_partner_score_bonuses": dict(
            get_static_config().default_preferred_partner_score_bonuses
        ),
        "default_field_transform": FieldTransformSpec(),
        "matrix_field_transform": backfill_transform,
        "vector_field_transform": backfill_transform,
        "ratio_numerator_transform": backfill_transform,
        "ratio_denominator_transform": backfill_transform,
        "feedback_loop_policy": _default_feedback_loop_policy(),
    }
    if use_curated_heuristics:
        policy_kwargs.update(
            positive_raw_fields=set(get_static_config().positive_raw_fields),
            negative_raw_fields=set(get_static_config().negative_raw_fields),
        )
    return DatasetExpressionPolicy(**policy_kwargs)


def get_dataset_expression_policy(
    dataset_id: str,
    *,
    default_backfill_window: int | None = None,
    use_curated_heuristics: bool | None = None,
) -> DatasetExpressionPolicy:
    """Return the dataset expression policy after YAML overrides.

    精选启发式（use_curated_heuristics）现在由 YAML expression_policies.<dataset>.use_curated_heuristics
    控制，不再硬编码特定数据集名称。
    """
    if use_curated_heuristics is None:
        use_curated_heuristics = use_curated_heuristics_for_dataset(dataset_id)
    if default_backfill_window is None:
        default_backfill_window = get_static_config().backfill_window

    base_policy = _base_expression_policy(
        dataset_id,
        default_backfill_window=default_backfill_window,
        use_curated_heuristics=use_curated_heuristics,
    )
    return apply_yaml_expression_policy_overrides(
        base_policy,
        dataset_id=dataset_id,
        use_curated_heuristics=use_curated_heuristics,
    )


def resolve_feedback_stage(
    field_feedback: FieldFeedbackSummary | None,
    loop_policy: FeedbackLoopPolicy,
) -> str:
    """Resolve whether a field should generate or resimulate templates."""
    if not field_feedback:
        return get_static_config().feedback_stage_generate
    feedback: dict[str, Any] = dict(field_feedback)
    attempted = int(feedback.get(get_static_config().stat_field_attempted_templates, 0) or 0)
    raw_best_score = feedback.get("best_score", get_static_config().stats_default_score)
    best_score = float(
        get_static_config().stats_default_score if raw_best_score is None else raw_best_score
    )
    if (
        attempted >= loop_policy.resimulate.min_attempted_templates
        and best_score >= loop_policy.resimulate.min_best_score
    ):
        return get_static_config().feedback_stage_resimulate
    return get_static_config().feedback_stage_generate


def use_curated_heuristics_for_dataset(
    dataset_id: str = "",
    *,
    yaml_config: dict | None = None,
) -> bool:
    """检查数据集是否应使用精选启发式（POSITIVE/NEGATIVE_RAW_FIELDS、高置信度比率等）。

    默认返回 False；YAML expression_policies.<dataset>.use_curated_heuristics 控制开启。
    """
    if not dataset_id:
        return False
    if yaml_config is None:
        from ..config.yaml import get_yaml_config

        yaml_config = get_yaml_config() or {}
    policies = yaml_config.get("expression_policies", {})
    if not isinstance(policies, dict):
        return False
    dataset_policy = policies.get(dataset_id, {})
    if isinstance(dataset_policy, dict):
        return bool(dataset_policy.get("use_curated_heuristics", False))
    return False
