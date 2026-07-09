"""Feedback and result-family propagation tests."""

from __future__ import annotations

import json

from alpha.analysis.feedback_filters import (
    is_legacy_family_disabled,
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)
from alpha.analysis.feedback_history import (
    build_historical_run_state,
    choose_settings_variant_budget,
    select_nearpass_candidates,
)
from alpha.analysis.template_registry import choose_registry_settings_budget
from alpha.analysis.template_registry import choose_family_settings_budget
from alpha.analysis.template_registry import choose_field_cluster_settings_budget
from alpha.analysis.results_loader import load_existing_results
from alpha.generators.templates.refine import build_refine_templates
from alpha.generators.variants import build_setting_variants
from alpha.models.domain import FieldTestResult, NearPassCandidate
from alpha.policy.expression import get_dataset_expression_policy, resolve_feedback_stage


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
        "best_score": 0.55,
        "attempted_templates": 4,
    }

    stage = resolve_feedback_stage(field_feedback, policy.feedback_loop_policy)

    assert stage == "resimulate"


def test_choose_settings_variant_budget_uses_feedback_stage_policy() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    generate_budget = choose_settings_variant_budget(None, expression_policy=policy)
    resimulate_budget = choose_settings_variant_budget(
        {
            "best_score": 0.55,
            "attempted_templates": 4,
        },
        expression_policy=policy,
    )

    assert generate_budget == 1
    assert resimulate_budget == 3


def test_registry_settings_budget_respects_recommended_scope() -> None:
    assert (
        choose_registry_settings_budget(
            1,
            {"recommended_scope": "broad", "recommended_role": "promoted_core"},
        )
        == 2
    )
    assert (
        choose_registry_settings_budget(
            3,
            {"recommended_scope": "refine", "recommended_role": "refine_neighbor"},
        )
        == 1
    )
    assert (
        choose_registry_settings_budget(
            3,
            {"recommended_scope": "diagnostic", "recommended_role": "diagnostic_probe"},
        )
        == 0
    )


def test_family_settings_budget_respects_family_registry() -> None:
    assert (
        choose_family_settings_budget(
            1,
            "ts_rank",
            {"ts_rank": {"recommended_scope": "broad", "budget_adjustment": 1}},
        )
        == 2
    )
    assert (
        choose_family_settings_budget(
            2,
            "mean_spread",
            {"mean_spread": {"recommended_scope": "diagnostic", "budget_adjustment": -1}},
        )
        == 0
    )


def test_field_cluster_settings_budget_respects_runtime_tags_and_overrides() -> None:
    assert choose_field_cluster_settings_budget(1, ["high_coverage"], {}) == 2
    assert (
        choose_field_cluster_settings_budget(
            2,
            ["sparse_coverage"],
            {
                "field_cluster_overrides": {
                    "sparse_coverage": {
                        "recommended_scope": "diagnostic",
                        "budget_adjustment": -1,
                    }
                }
            },
        )
        == 0
    )


def test_build_historical_run_state_loads_persisted_template_registry(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    output_path.write_text(
        json.dumps(
            {
                "dataset_id": "fundamental6",
                "results": [
                    {
                        "field_id": "cash_st",
                        "field_type": "MATRIX",
                        "field_name": "cash_st",
                        "template_name": "core_template",
                        "template_family": "ts_rank",
                        "template_stage": "first_order",
                        "status": "simulated",
                        "submittable": True,
                        "submitted": False,
                        "message": "",
                        "expression": "rank(ts_rank(cash_st, 60))",
                        "settings_fingerprint": "settings",
                        "template_library_fingerprint": "library",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "results_template_registry.json").write_text(
        json.dumps(
            [
                {
                    "template_name": "core_template",
                    "template_family": "ts_rank",
                    "recommended_role": "promoted_core",
                    "recommended_scope": "broad",
                    "priority_adjustment": 120,
                    "reason": "submittable_history",
                }
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "results_template_registry_overrides.json").write_text(
        json.dumps(
            {
                "template_overrides": {
                    "core_template": {
                        "recommended_role": "promoted_core",
                        "recommended_scope": "broad",
                    }
                },
                "family_overrides": {},
                "field_cluster_overrides": {},
            }
        ),
        encoding="utf-8",
    )

    state = build_historical_run_state(str(output_path), str(output_path))

    assert state.template_registry["core_template"]["recommended_role"] == "promoted_core"
    assert state.template_stats["core_template"]["registry_recommended_role"] == "promoted_core"
    assert state.template_family_registry["ts_rank"]["recommended_scope"] == "broad"
    assert state.template_registry_overrides["template_overrides"]["core_template"]["recommended_role"] == "promoted_core"


def test_resimulate_stage_blocks_iter_templates_outside_preferred_stages() -> None:
    policy = get_dataset_expression_policy("fundamental6")

    keep = should_keep_template_for_feedback(
        "iter_rank_delta_5",
        "rank(ts_delta(ts_backfill(cash_st, 240), 5))",
        200,
        {
            "best_score": 0.55,
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

    assert len(candidates) >= 1
    assert candidates[0].template_name == "account_group_zscore_60_subindustry"


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

    assert all(isinstance(variant, type(variants[0])) for variant in variants)
    assert any(variant.get("truncation") == 0.05 for variant in variants)
    assert any(variant.get("neutralization") == "INDUSTRY" for variant in variants)
    assert any(variant.get("neutralization") == "MARKET" for variant in variants)
    assert all("instrumentType" in variant.to_dict() for variant in variants)
    assert all("unitHandling" in variant.to_dict() for variant in variants)
    assert all("nanHandling" in variant.to_dict() for variant in variants)


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


def test_build_refine_templates_deduplicates_identical_expressions() -> None:
    templates = build_refine_templates(
        "cash_st",
        [
            NearPassCandidate(
                field_id="cash_st",
                field_name="cash_st",
                template_name="model51_ts_zscore_120",
                expression="rank(ts_zscore(ts_backfill(cash_st, 504), 120))",
                template_family="zscore_time",
                template_stage="first_order",
                score=0.85,
                failed_checks=[
                    {"name": "LOW_FITNESS", "value": 0.85, "limit": 1.0},
                ],
            ),
            NearPassCandidate(
                field_id="cash_st",
                field_name="cash_st",
                template_name="duplicate_model51_ts_zscore_120",
                expression="rank(ts_zscore(ts_backfill(cash_st, 504), 120))",
                template_family="zscore_time",
                template_stage="first_order",
                score=0.84,
                failed_checks=[
                    {"name": "LOW_FITNESS", "value": 0.84, "limit": 1.0},
                ],
            ),
        ],
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    exact_templates = [template for template in templates if template.expression == "rank(ts_zscore(ts_backfill(cash_st, 504), 120))"]

    assert len(exact_templates) == 1
    assert exact_templates[0].name == "refine_exact_1_model51_ts_zscore_120"
