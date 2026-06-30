"""Feedback and result-family propagation tests."""

from __future__ import annotations

import json

from alpha.analysis.feedback import (
    choose_settings_variant_budget,
    is_legacy_family_disabled,
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)
from alpha.analysis.stats import load_existing_results
from alpha.config import get_dataset_expression_policy, resolve_feedback_stage


def test_should_skip_field_template_family_prefers_metadata_family() -> None:
    """Field-family pruning should honor explicit template metadata."""
    policy = get_dataset_expression_policy("fundamental6")

    should_skip = should_skip_field_template_family(
        "assets",
        "custom_template",
        "rank(custom_field)",
        expression_policy=policy,
        template_metadata={"family": "mean_spread"},
    )

    assert should_skip is True


def test_is_legacy_family_disabled_uses_historical_template_family() -> None:
    """Legacy-family disable should reuse explicit family stored in template stats."""
    template_stats = {
        "custom_template": {
            "attempted": 3,
            "submittable": 0,
            "template_family": "legacy_ratio",
        }
    }

    disabled = is_legacy_family_disabled(
        "next_template",
        "rank(custom_field)",
        template_stats,
        disable_after=3,
        template_metadata={"family": "legacy_ratio"},
    )

    assert disabled is True


def test_load_existing_results_reads_template_family(tmp_path) -> None:
    """Persisted results should round-trip template_family for later feedback passes."""
    result_file = tmp_path / "results.json"
    result_file.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "field_id": "cash_st",
                        "field_type": "MATRIX",
                        "field_name": "cash_st",
                        "template_name": "ts_rank_60",
                        "template_family": "ts_rank",
                        "template_stage": "first_order",
                        "status": "simulated",
                        "submittable": False,
                        "submitted": False,
                        "message": "LOW_SHARPE",
                        "expression": "rank(ts_rank(cash_st, 60))",
                        "settings_fingerprint": "settings",
                        "template_library_fingerprint": "library",
                        "failed_checks": [{"name": "LOW_SHARPE", "value": 0.9}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    results = load_existing_results(str(result_file))

    assert len(results) == 1
    assert results[0].template_family == "ts_rank"
    assert results[0].template_stage == "first_order"


def test_feedback_stage_advances_to_resimulate_for_nearpass_fields() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field_feedback = {
        "best_score": 0.30,
        "attempted_templates": 4,
    }

    stage = resolve_feedback_stage(field_feedback, policy.feedback_loop_policy)

    assert stage == "resimulate"


def test_choose_settings_variant_budget_uses_feedback_stage_policy() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    generate_budget = choose_settings_variant_budget(None, expression_policy=policy)
    resimulate_budget = choose_settings_variant_budget(
        {
            "best_score": 0.30,
            "attempted_templates": 4,
        },
        expression_policy=policy,
    )

    assert generate_budget == 1
    assert resimulate_budget == 3


def test_resimulate_stage_blocks_iter_templates_outside_preferred_stages() -> None:
    policy = get_dataset_expression_policy("fundamental6")

    keep = should_keep_template_for_feedback(
        "iter_rank_delta_5",
        "rank(ts_delta(ts_backfill(cash_st, 240), 5))",
        200,
        {
            "best_score": 0.30,
            "attempted_templates": 4,
            "failed_check_counts": {},
        },
        expression_policy=policy,
        template_metadata={"family": "rank_delta", "stage": "first_order"},
    )

    assert keep is False
