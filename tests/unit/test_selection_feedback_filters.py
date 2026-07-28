"""Selection feedback pruning policy branch tests."""

from __future__ import annotations

from alpha.config.models import DatasetExpressionPolicy, FeedbackLoopPolicy, FeedbackPhasePolicy
from alpha.policy.expression import resolve_feedback_stage
from alpha.selection.feedback_filters import (
    is_legacy_family_disabled,
    is_template_disabled,
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)


def _policy(**overrides: object) -> DatasetExpressionPolicy:
    values: dict[str, object] = {
        "use_curated_heuristics": True,
        "feedback_loop_policy": FeedbackLoopPolicy(
            generate=FeedbackPhasePolicy(),
            prune=FeedbackPhasePolicy(
                min_attempted_templates=1,
                min_best_score=0.0,
                enable_template_pruning=True,
            ),
            resimulate=FeedbackPhasePolicy(
                min_attempted_templates=999,
                min_best_score=999.0,
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


def test_feedback_stage_preserves_valid_zero_best_score() -> None:
    assert resolve_feedback_stage(_feedback(), _policy().feedback_loop_policy) == "prune"


def test_template_disable_guards_and_quality_shortcuts() -> None:
    assert not is_template_disabled("missing", {}, disable_after=3)
    assert not is_template_disabled("template", {"template": {"attempted": 99}}, disable_after=0)
    assert is_template_disabled(
        "mean_spread_template",
        {
            "mean_spread_template": {
                "simulated": 3,
                "submittable": 0,
                "low_sharpe": 3,
                "low_fitness": 3,
            }
        },
        disable_after=99,
    )
    assert is_template_disabled(
        "concentrated",
        {
            "concentrated": {
                "simulated": 3,
                "submittable": 0,
                "concentrated_weight": 2,
            }
        },
        disable_after=99,
    )


def test_legacy_disable_ignores_nonlegacy_candidates_and_prior_families() -> None:
    assert not is_legacy_family_disabled(
        "custom",
        "rank(field)",
        {},
        disable_after=2,
        template_metadata={"family": "custom"},
    )
    assert is_legacy_family_disabled(
        "candidate",
        "rank(field)",
        {
            "nonlegacy": {"attempted": 100, "template_family": "ts_rank"},
            "legacy": {"attempted": 2, "submittable": 0, "template_family": "legacy_ratio"},
        },
        disable_after=2,
        template_metadata={"family": "legacy_ratio"},
    )


def test_feedback_pruning_early_keep_rules() -> None:
    assert should_keep_template_for_feedback("template", "rank(field)", 0, None)
    assert should_keep_template_for_feedback(
        "template",
        "rank(field)",
        0,
        _feedback(),
        expression_policy=DatasetExpressionPolicy(),
    )
    policy = _policy(
        always_keep_families={"always"},
        protected_templates={"protected"},
    )
    assert should_keep_template_for_feedback(
        "template",
        "rank(field)",
        0,
        _feedback(),
        expression_policy=policy,
        template_metadata={"family": "always"},
    )
    assert should_keep_template_for_feedback(
        "iter_template", "rank(field)", 0, _feedback(), expression_policy=policy
    )
    assert should_keep_template_for_feedback(
        "protected", "rank(field)", 0, _feedback(), expression_policy=policy
    )


def test_low_turnover_prunes_slow_level_templates() -> None:
    policy = _policy(slow_template_prefixes=("slow_",), slow_template_names={"exact_slow"})
    cases = [
        ("slow_template", "rank(field)"),
        ("exact_slow", "rank(field)"),
        ("mean_level", "rank(ts_mean(field, 20))"),
        ("backfill_level", "rank(ts_backfill(field, 20))"),
    ]

    for name, expression in cases:
        assert not should_keep_template_for_feedback(
            name,
            expression,
            200,
            _feedback(LOW_TURNOVER=5),
            expression_policy=policy,
            template_metadata={"family": "custom"},
        )


def test_concentration_and_low_sharpe_prune_weak_ratio_templates() -> None:
    policy = _policy(
        concentrated_weak_families={"weak_family"},
        concentrated_weak_prefixes=("prefix_",),
        concentrated_weak_names={"exact_weak"},
        low_sharpe_weak_ratio_families={"weak_ratio"},
        low_sharpe_weak_ratio_prefixes=("ratio_",),
        low_sharpe_ratio_fail_threshold=2,
    )
    cases = [
        ("family", "weak_family", {"CONCENTRATED_WEIGHT": 3}),
        ("prefix_template", "custom", {"CONCENTRATED_WEIGHT": 3}),
        ("exact_weak", "custom", {"LOW_SUB_UNIVERSE_SHARPE": 3}),
        ("ratio_family", "weak_ratio", {"LOW_SHARPE": 2}),
        ("ratio_template", "custom", {"LOW_SHARPE": 2}),
    ]

    for name, family, failed_counts in cases:
        assert not should_keep_template_for_feedback(
            name,
            "rank(numerator/denominator)",
            200,
            _feedback(**failed_counts),
            expression_policy=policy,
            template_metadata={"family": family},
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


def test_field_family_skip_policy_covers_all_curated_rules() -> None:
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
    assert should_skip_field_template_family(
        "spread_field",
        "template",
        "rank(field)",
        expression_policy=_policy(weak_mean_spread_fields={"spread_field"}),
        template_metadata={"family": "mean_spread"},
    )
    assert should_skip_field_template_family(
        "zscore_field",
        "custom_zscore_spread",
        "rank(field)",
        expression_policy=_policy(broken_zscore_spread_fields={"zscore_field"}),
    )
    assert should_skip_field_template_family(
        "ratio_field",
        "ratio_template",
        "rank(field)",
        expression_policy=_policy(weak_ratio_standalone_fields={"ratio_field"}),
        template_metadata={"family": "legacy_ratio"},
    )
