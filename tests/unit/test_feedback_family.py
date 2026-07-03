"""Feedback and result-family propagation tests."""

from __future__ import annotations

import json

from alpha.analysis.feedback import (
    choose_settings_variant_budget,
    is_legacy_family_disabled,
    select_nearpass_candidates,
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)
from alpha.analysis.stats import load_existing_results
from alpha.config import get_dataset_expression_policy, resolve_feedback_stage
from alpha.generators.expressions import build_refine_templates
from alpha.generators.variants import build_setting_variants
from alpha.models.domain import FieldTestResult, NearPassCandidate


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


def test_select_nearpass_candidates_penalizes_concentration_failures() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    results = [
        FieldTestResult(
            field_id="cash_st",
            field_type="MATRIX",
            field_name="cash_st",
            template_name="account_group_zscore_60_subindustry",
            template_family="group_zscore",
            template_stage="group_second_order",
            status="simulated",
            submittable=False,
            expression="group_rank(ts_zscore(ts_backfill(cash_st, 504), 60), subindustry)",
            failed_checks=[
                {"name": "LOW_SHARPE", "value": 1.21, "limit": 1.25},
                {"name": "LOW_FITNESS", "value": 0.64, "limit": 1.0},
            ],
        ),
        FieldTestResult(
            field_id="cash_st",
            field_type="MATRIX",
            field_name="cash_st",
            template_name="account_ts_rank_60",
            template_family="ts_rank",
            template_stage="first_order",
            status="simulated",
            submittable=False,
            expression="rank(ts_rank(ts_backfill(cash_st, 504), 60))",
            failed_checks=[
                {"name": "LOW_SHARPE", "value": 1.20, "limit": 1.25},
                {"name": "CONCENTRATED_WEIGHT", "value": 0.500001, "limit": 0.10},
            ],
        ),
    ]

    candidates = select_nearpass_candidates(
        "cash_st",
        results,
        expression_policy=policy,
        limit=2,
    )

    assert [candidate.template_name for candidate in candidates] == [
        "account_group_zscore_60_subindustry",
        "account_ts_rank_60",
    ]


def test_build_setting_variants_expands_candidate_centric_refine_settings() -> None:
    class _Args:
        instrument_type = "EQUITY"
        region = "USA"
        universe = "TOP3000"
        delay = 1
        decay = 4
        neutralization = "SUBINDUSTRY"
        truncation = 0.08
        pasteurization = "ON"
        unit_handling = "VERIFY"
        nan_handling = "OFF"
        language = "FASTEXPR"
        start_date = None
        end_date = None

    variants = build_setting_variants(
        _Args(),
        "refine_exact",
        "group_rank(ts_zscore(ts_backfill(cash_st, 504), 60), subindustry)",
        refine_candidate=NearPassCandidate(
            field_id="cash_st",
            field_name="cash_st",
            template_name="account_group_zscore_60_subindustry",
            expression="group_rank(ts_zscore(ts_backfill(cash_st, 504), 60), subindustry)",
            template_family="group_zscore",
            template_stage="group_second_order",
            score=0.80,
            failed_checks=[
                {"name": "CONCENTRATED_WEIGHT", "value": 0.14, "limit": 0.10},
                {"name": "LOW_SUB_UNIVERSE_SHARPE", "value": 0.50, "limit": 0.52},
            ],
        ),
    )

    assert any(variant.get("truncation") == 0.05 for variant in variants)
    assert any(variant.get("neutralization") == "INDUSTRY" for variant in variants)
    assert any(variant.get("neutralization") == "MARKET" for variant in variants)


def test_build_refine_templates_generates_localized_mutations_from_nearpass_candidate() -> None:
    templates = build_refine_templates(
        "cash_st",
        [
            NearPassCandidate(
                field_id="cash_st",
                field_name="cash_st",
                template_name="account_group_zscore_60_subindustry",
                expression="group_rank(ts_zscore(ts_backfill(cash_st, 504), 60), subindustry)",
                template_family="group_zscore",
                template_stage="group_second_order",
                score=0.80,
                failed_checks=[
                    {"name": "LOW_SHARPE", "value": 1.21, "limit": 1.25},
                    {"name": "LOW_FITNESS", "value": 0.64, "limit": 1.0},
                ],
            )
        ],
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    names = {template.name for template in templates}
    expressions = {template.expression for template in templates}

    assert "refine_exact_1_account_group_zscore_60_subindustry" in names
    assert "refine_industry_1_account_group_zscore_60_subindustry" in names
    assert any("trade_when(" in expression for expression in expressions)
    assert any("ts_decay_linear(" in expression for expression in expressions)


def test_build_refine_templates_skips_recursive_refine_candidates() -> None:
    templates = build_refine_templates(
        "cash_st",
        [
            NearPassCandidate(
                field_id="cash_st",
                field_name="cash_st",
                template_name="refine_exact_1_account_group_zscore_60_subindustry",
                expression="group_rank(ts_zscore(cash_st, 60), subindustry)",
                template_family="group_zscore",
                template_stage="group_second_order",
                score=0.80,
                failed_checks=[
                    {"name": "LOW_SHARPE", "value": 1.21, "limit": 1.25},
                    {"name": "LOW_FITNESS", "value": 0.64, "limit": 1.0},
                ],
            )
        ],
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    assert templates == []
