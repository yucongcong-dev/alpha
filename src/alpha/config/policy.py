"""Dataset expression policy construction and feedback-stage resolution."""

from __future__ import annotations

from typing import Any

from .constants import (
    BACKFILL_WINDOW,
    DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS,
    DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS,
    DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES,
    DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS,
    DEFAULT_RATIO_DELTA_RANK_WINDOWS,
    DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS,
    FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
    FEEDBACK_STAGE_GENERATE,
    FEEDBACK_STAGE_PRUNE,
    FEEDBACK_STAGE_RESIMULATE,
    NEGATIVE_RAW_FIELDS,
    POSITIVE_RAW_FIELDS,
    RATIO_KEYWORDS,
    RATIO_LEGACY_TEMPLATE_SPECS,
    RATIO_PARTNER_CANDIDATES,
    STAT_FIELD_ATTEMPTED_TEMPLATES,
    STATS_DEFAULT_SCORE,
    TEMPLATE_STAGE_EVENT_CONDITIONED,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
)
from .models import (
    DatasetExpressionPolicy,
    FeedbackLoopPolicy,
    FeedbackPhasePolicy,
    FieldTransformSpec,
    FieldTransformStage,
)
from .policy_overrides import apply_yaml_expression_policy_overrides


def _default_transform_specs() -> tuple[
    FieldTransformSpec,
    FieldTransformSpec,
    FieldTransformSpec,
    FieldTransformSpec,
]:
    """Build default field transform specs used by all dataset policies."""
    default_transform = FieldTransformSpec()
    matrix_transform = FieldTransformSpec(
        stages=(FieldTransformStage(kind="backfill", window=BACKFILL_WINDOW),),
        backfill_window=BACKFILL_WINDOW,
    )
    vector_transform = FieldTransformSpec(
        stages=(FieldTransformStage(kind="backfill", window=BACKFILL_WINDOW),),
        backfill_window=BACKFILL_WINDOW,
    )
    ratio_transform = FieldTransformSpec(
        stages=(FieldTransformStage(kind="backfill", window=BACKFILL_WINDOW),),
        backfill_window=BACKFILL_WINDOW,
    )
    return default_transform, matrix_transform, vector_transform, ratio_transform


def _default_feedback_loop_policy() -> FeedbackLoopPolicy:
    """Build the default generate/prune/resimulate feedback policy."""
    return FeedbackLoopPolicy(
        generate=FeedbackPhasePolicy(
            min_attempted_templates=0,
            min_best_score=STATS_DEFAULT_SCORE,
            settings_variant_budget=1,
        ),
        prune=FeedbackPhasePolicy(
            min_attempted_templates=2,
            min_best_score=STATS_DEFAULT_SCORE,
            settings_variant_budget=2,
            enable_template_pruning=True,
        ),
        resimulate=FeedbackPhasePolicy(
            min_attempted_templates=3,
            min_best_score=FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
            settings_variant_budget=3,
            enable_template_pruning=True,
            enable_resimulation_mutations=True,
            preferred_template_stages=(
                TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                TEMPLATE_STAGE_EVENT_CONDITIONED,
            ),
        ),
    )


def _base_expression_policy(
    dataset_id: str,
    *,
    use_curated_heuristics: bool,
    default_transform: FieldTransformSpec,
    matrix_transform: FieldTransformSpec,
    vector_transform: FieldTransformSpec,
    ratio_transform: FieldTransformSpec,
    feedback_loop_policy: FeedbackLoopPolicy,
) -> DatasetExpressionPolicy:
    """Build a base policy before YAML overrides are applied."""
    policy_kwargs: dict[str, Any] = {
        "dataset_id": dataset_id,
        "use_curated_heuristics": use_curated_heuristics,
        "partner_limit": 4,
        "matrix_delta_over_std_windows": DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS,
        "matrix_diversified_template_specs": DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS,
        "ratio_delta_rank_windows": DEFAULT_RATIO_DELTA_RANK_WINDOWS,
        "ratio_delta_over_std_windows": DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS,
        "ratio_diversified_template_specs": DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS,
        "ratio_legacy_template_specs": RATIO_LEGACY_TEMPLATE_SPECS,
        "ratio_partner_candidates": dict(RATIO_PARTNER_CANDIDATES),
        "ratio_keywords": dict(RATIO_KEYWORDS),
        "preferred_partner_score_bonuses": dict(DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES),
        "default_field_transform": default_transform,
        "matrix_field_transform": matrix_transform,
        "vector_field_transform": vector_transform,
        "ratio_numerator_transform": ratio_transform,
        "ratio_denominator_transform": ratio_transform,
        "feedback_loop_policy": feedback_loop_policy,
    }
    if use_curated_heuristics:
        policy_kwargs.update(
            positive_raw_fields=set(POSITIVE_RAW_FIELDS),
            negative_raw_fields=set(NEGATIVE_RAW_FIELDS),
        )
    return DatasetExpressionPolicy(**policy_kwargs)


def get_dataset_expression_policy(
    dataset_id: str,
    *,
    use_curated_heuristics: bool | None = None,
) -> DatasetExpressionPolicy:
    """Return the dataset expression policy after YAML overrides."""
    if use_curated_heuristics is None:
        use_curated_heuristics = dataset_id == "fundamental6"

    default_transform, matrix_transform, vector_transform, ratio_transform = _default_transform_specs()
    base_policy = _base_expression_policy(
        dataset_id,
        use_curated_heuristics=use_curated_heuristics,
        default_transform=default_transform,
        matrix_transform=matrix_transform,
        vector_transform=vector_transform,
        ratio_transform=ratio_transform,
        feedback_loop_policy=_default_feedback_loop_policy(),
    )
    return apply_yaml_expression_policy_overrides(
        base_policy,
        dataset_id=dataset_id,
        use_curated_heuristics=use_curated_heuristics,
    )


def resolve_feedback_stage(
    field_feedback: dict[str, Any] | None,
    loop_policy: FeedbackLoopPolicy,
) -> str:
    """Resolve whether a field should generate, prune, or resimulate templates."""
    if not field_feedback:
        return FEEDBACK_STAGE_GENERATE
    attempted = int(field_feedback.get(STAT_FIELD_ATTEMPTED_TEMPLATES, 0))
    best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))
    if (
        attempted >= loop_policy.resimulate.min_attempted_templates
        and best_score >= loop_policy.resimulate.min_best_score
    ):
        return FEEDBACK_STAGE_RESIMULATE
    if (
        attempted >= loop_policy.prune.min_attempted_templates
        and best_score >= loop_policy.prune.min_best_score
    ):
        return FEEDBACK_STAGE_PRUNE
    return FEEDBACK_STAGE_GENERATE


def use_fundamental6_heuristics(dataset_id: str = "fundamental6") -> bool:
    """Return whether a dataset id should use fundamental6 curated heuristics."""
    return dataset_id == "fundamental6" or "fundamental6" in dataset_id.lower()
