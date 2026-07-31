"""Selection feedback pruning policy branch tests."""

from __future__ import annotations

from alpha.config.models import DatasetExpressionPolicy, FeedbackLoopPolicy, FeedbackPhasePolicy
from alpha.policy.expression import resolve_feedback_stage
from alpha.selection.feedback_filters import (
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)


def _policy(**overrides: object) -> DatasetExpressionPolicy:
    values: dict[str, object] = {
        "use_curated_heuristics": True,
        "feedback_loop_policy": FeedbackLoopPolicy(
            generate=FeedbackPhasePolicy(),
            resimulate=FeedbackPhasePolicy(
                min_attempted_templates=1,
                min_best_score=0.0,
                enable_template_pruning=True,
            ),
        ),
    }
    values.update(overrides)
    return DatasetExpressionPolicy(**values)


def _feedback(**failed_counts: int) -> dict[str, object]:
    return {
        "attempted_templates": 1,
        "best_score": 0.0,
        "failed_check_counts": failed_counts,
    }


def test_feedback_stage_preserves_valid_zero_best_score_for_refine() -> None:
    assert resolve_feedback_stage(_feedback(), _policy().feedback_loop_policy) == "resimulate"


def test_feedback_stage_stays_generate_before_refine_threshold() -> None:
    policy = _policy(
        feedback_loop_policy=FeedbackLoopPolicy(
            generate=FeedbackPhasePolicy(),
            resimulate=FeedbackPhasePolicy(
                min_attempted_templates=2,
                min_best_score=0.5,
            ),
        )
    )
    assert resolve_feedback_stage(_feedback(), policy.feedback_loop_policy) == "generate"


def test_feedback_pruning_early_keep_rules() -> None:
    assert should_keep_template_for_feedback("template", "rank(field)", 0, None)
    assert should_keep_template_for_feedback(
        "template",
        "rank(field)",
        0,
        _feedback(),
        expression_policy=DatasetExpressionPolicy(),
    )
    policy = _policy(protected_templates={"protected"})
    assert should_keep_template_for_feedback(
        "iter_template", "rank(field)", 0, _feedback(), expression_policy=policy
    )
    assert should_keep_template_for_feedback(
        "protected", "rank(field)", 0, _feedback(), expression_policy=policy
    )


def test_low_turnover_prunes_slow_level_templates() -> None:
    cases = [
        ("mean_level", "rank(ts_mean(field, 20))"),
        ("backfill_level", "rank(ts_backfill(field, 20))"),
    ]

    for name, expression in cases:
        assert not should_keep_template_for_feedback(
            name,
            expression,
            200,
            _feedback(LOW_TURNOVER=5),
            expression_policy=_policy(),
            template_metadata={"family": "custom"},
        )


def test_combined_turnover_concentration_prunes_zscore_spread() -> None:
    assert not should_keep_template_for_feedback(
        "custom_zscore_spread",
        "rank(field)",
        200,
        _feedback(HIGH_TURNOVER=3, CONCENTRATED_WEIGHT=3),
        expression_policy=_policy(),
        template_metadata={"family": "rank_spread"},
    )


def test_field_family_skip_policy_only_applies_explicit_blacklist() -> None:
    assert not should_skip_field_template_family(
        "field", "template", "rank(field)", expression_policy=DatasetExpressionPolicy()
    )
    assert should_skip_field_template_family(
        "field",
        "blocked_template",
        "rank(field)",
        expression_policy=_policy(
            dataset_id="test",
            blacklisted_template_name_substrings=("blocked",),
        ),
    )
