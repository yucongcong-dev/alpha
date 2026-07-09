"""Historical best-expression reuse strategies."""

from __future__ import annotations

from ...config import (
    EXPR_MUTATION_EXTEND_THRESHOLD,
    FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
    FEEDBACK_STAGE_GENERATE,
    STATS_DEFAULT_SCORE,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
    DatasetExpressionPolicy,
)
from ...models.domain import TemplateCandidate
from ...models.domain_types import FieldFeedbackSummary
from .candidates import _candidate_metadata, _make_template_candidate
from .variation_common import is_blacklisted_template
from .wrappers import build_bucket_group_templates, build_trade_when_templates


def build_historical_reuse_templates(
    field_name: str,
    field_feedback: FieldFeedbackSummary | None,
    *,
    feedback_stage: str,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> list[TemplateCandidate]:
    """Reuse historically strong expressions through wrapper-style mutations."""
    del field_name
    if not field_feedback or feedback_stage == FEEDBACK_STAGE_GENERATE:
        return []
    best_expression = str(field_feedback.get("best_expression", "")).strip()
    if not best_expression:
        return []
    try:
        best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))
    except (TypeError, ValueError):
        best_score = STATS_DEFAULT_SCORE
    if best_score < EXPR_MUTATION_EXTEND_THRESHOLD:
        return []

    priority_offset = 18 if best_score >= FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD else 0
    templates: list[TemplateCandidate] = []
    templates.extend(
        build_bucket_group_templates(
            best_expression,
            name_prefix="iter_reuse_best",
            priority_offset=priority_offset,
        )
    )
    templates.extend(
        build_trade_when_templates(
            best_expression,
            name_prefix="iter_reuse_best",
            priority_offset=priority_offset,
        )
    )
    templates.extend(
        [
            _make_template_candidate(
                "iter_reuse_best_group_neutralize_subindustry",
                f"group_neutralize({best_expression}, subindustry)",
                178 + priority_offset,
                metadata=_candidate_metadata(
                    family="neutralize_decay",
                    layer="group",
                    stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                ),
            ),
            _make_template_candidate(
                "iter_reuse_best_group_rank_subindustry",
                f"group_rank({best_expression}, subindustry)",
                176 + priority_offset,
                metadata=_candidate_metadata(
                    family="legacy_group_level",
                    layer="group",
                    stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                ),
            ),
        ]
    )
    return [
        template
        for template in templates
        if not is_blacklisted_template(
            template.name,
            template.expression,
            template_metadata=template.metadata,
            policy=expression_policy,
        )
    ]
