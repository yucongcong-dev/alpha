"""Build expression candidates from configured template-library items."""

from __future__ import annotations

from collections.abc import Sequence

from ...config.models import DatasetExpressionPolicy
from ...models.domain import FieldView, TemplateCandidate, TemplateLibraryItem
from ...policy.template_blacklist import runtime_blacklist_match_reason
from ...runtime.contexts import TemplateBuildContext
from .candidates import _make_template_candidate
from .classification import classify_expression_family, classify_template_stage
from .metadata import _runtime_template_metadata


def _record_candidate_blacklist_filter(
    build_ctx: TemplateBuildContext,
    reason: str,
) -> None:
    counts = build_ctx.candidate_filter_counts
    if counts is None:
        return
    normalized = reason.strip().lower().replace("+", "_").replace(":", "_").replace("-", "_")
    key = f"template_filtered_blacklist_{normalized or 'unknown'}"
    counts[key] = counts.get(key, 0) + 1


def _policy_template_priority_adjustment(
    template_name: str,
    policy: DatasetExpressionPolicy,
) -> int:
    """Adjust configured template priority using the active dataset policy."""
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


def build_library_candidates(
    raw_templates: Sequence[TemplateLibraryItem],
    *,
    build_ctx: TemplateBuildContext,
    field_view: FieldView,
    field_type: str,
    policy: DatasetExpressionPolicy,
    backfill_window: int,
) -> list[TemplateCandidate]:
    """Expand configured library items and explain runtime blacklist filtering."""
    candidates: list[TemplateCandidate] = []
    for item in raw_templates:
        metadata = _runtime_template_metadata(item)
        reason = runtime_blacklist_match_reason(
            item.name,
            item.expression,
            template_metadata=metadata,
            policy=policy,
            current_field_type=field_type,
            current_family=classify_expression_family(item.name, item.expression, metadata),
            current_stage=classify_template_stage(item.name, item.expression, metadata),
        )
        if reason is not None:
            _record_candidate_blacklist_filter(build_ctx, reason)
            continue
        candidates.append(
            _make_template_candidate(
                item.name,
                item.expression.format(
                    field=field_view.raw_expression,
                    field_preprocessed=field_view.preprocessed_expression,
                    field_groupfill=field_view.groupfill_expression,
                    ratio_numerator=field_view.ratio_numerator_expression,
                    ratio_denominator=field_view.ratio_denominator_expression,
                    backfill_window=backfill_window,
                ),
                item.priority + _policy_template_priority_adjustment(item.name, policy),
                metadata=metadata,
            )
        )
    return candidates
