"""Feedback-driven mutation orchestration."""

from __future__ import annotations

from ...config import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    EXPR_MUTATION_EXTEND_THRESHOLD,
    EXPR_NEARPASS_BOOST_THRESHOLD,
    FEEDBACK_STAGE_GENERATE,
    FEEDBACK_STAGE_RESIMULATE,
    MUTATION_ACCOUNT_EXTEND_THRESHOLD,
    MUTATION_DOMINANT_CHECK_LIMIT,
    STATS_DEFAULT_SCORE,
    DatasetExpressionPolicy,
    get_backfill_window,
)
from ...models.domain import FieldFeedbackSummary, TemplateCandidate
from .feedback_best_expression import build_best_expression_mutations
from .feedback_mutation_sets import (
    build_account_resimulation_mutations,
    build_base_feedback_mutations,
    build_group_quality_repair_mutations,
    build_low_turnover_repair_mutations,
    build_nearpass_extension_mutations,
    build_nearpass_vol_scaled_mutations,
)
from .historical_reuse import build_historical_reuse_templates
from .priority import dominant_failed_check_names


def build_feedback_mutations(
    field_name: str,
    field_feedback: FieldFeedbackSummary | None,
    *,
    expression_policy: DatasetExpressionPolicy | None = None,
    feedback_stage: str = FEEDBACK_STAGE_GENERATE,
) -> list[TemplateCandidate]:
    """Build mutations from field feedback and best-known expressions."""
    bw = get_backfill_window()
    base_mutations = build_base_feedback_mutations(
        field_name,
        bw,
        expression_policy=expression_policy,
    )
    if not field_feedback:
        return base_mutations if feedback_stage == FEEDBACK_STAGE_GENERATE else []

    mutations = list(base_mutations)
    failed_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = dominant_failed_check_names(failed_counts, limit=MUTATION_DOMINANT_CHECK_LIMIT)
    best_expression = str(field_feedback.get("best_expression", "")).strip()
    best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))
    best_template_name = str(field_feedback.get("best_template_name", "")).strip()

    if feedback_stage == FEEDBACK_STAGE_RESIMULATE and best_score >= EXPR_MUTATION_EXTEND_THRESHOLD:
        mutations.extend(build_nearpass_extension_mutations(field_name, bw))

    if feedback_stage == FEEDBACK_STAGE_RESIMULATE and (
        best_template_name in {"account_rank_backfill_504", "account_ir_60"} or best_score >= MUTATION_ACCOUNT_EXTEND_THRESHOLD
    ):
        mutations.extend(build_account_resimulation_mutations(field_name, bw))

    if feedback_stage == FEEDBACK_STAGE_RESIMULATE and best_score >= EXPR_NEARPASS_BOOST_THRESHOLD:
        mutations.extend(
            build_nearpass_vol_scaled_mutations(
                field_name,
                bw,
                expression_policy=expression_policy,
            )
        )

    if feedback_stage != FEEDBACK_STAGE_GENERATE and CHECK_LOW_TURNOVER in dominant_names:
        mutations.extend(build_low_turnover_repair_mutations(field_name, bw))

    if feedback_stage != FEEDBACK_STAGE_GENERATE and (
        CHECK_LOW_SUB_UNIVERSE_SHARPE in dominant_names
        or CHECK_CONCENTRATED_WEIGHT in dominant_names
    ):
        mutations.extend(build_group_quality_repair_mutations(field_name, bw))

    if feedback_stage == FEEDBACK_STAGE_RESIMULATE and best_expression:
        mutations.extend(build_best_expression_mutations(best_expression, best_score, bw))

    mutations.extend(
        build_historical_reuse_templates(
            field_name,
            field_feedback,
            feedback_stage=feedback_stage,
            expression_policy=expression_policy,
        )
    )
    return mutations
