"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

from argparse import Namespace

from alpha.core.executor import build_pending_templates_for_field
from alpha.models.domain import (
    FailedCheck,
    FieldTestResult,
    TemplateCandidate,
    TemplateLibraryItem,
)
from alpha.models.runtime import TemplateBuildContext, TemplateBuildOptions
from alpha.policy.expression import get_dataset_expression_policy


def test_resimulate_stage_prefers_refine_templates_over_broad_generation(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.executor.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )
    args = Namespace(
        dataset_id="fundamental6",
        template_disable_after=0,
        disable_legacy_after=0,
        max_templates_per_field=6,
        max_templates_per_family=3,
        legacy_similarity_penalty=0,
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
        decay=4,
        neutralization="SUBINDUSTRY",
        truncation=0.08,
        pasteurization="ON",
        unit_handling="VERIFY",
        nan_handling="OFF",
        language="FASTEXPR",
    )
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=[{"id": "cash_st", "type": "MATRIX", "name": "cash_st"}],
        template_library={
            "default": [
                TemplateLibraryItem(
                    name="broad_template",
                    expression="rank(ts_backfill({field}, {backfill_window}))",
                    priority=9999,
                    family="legacy_level",
                    stage="first_order",
                )
            ]
        },
        field_feedback={
            "cash_st": {
                "field_name": "cash_st",
                "best_score": 0.55,
                "best_template_name": "account_group_zscore_63_subindustry",
                "best_template_family": "group_zscore",
                "best_template_stage": "group_second_order",
                "attempted_templates": 4,
                "failed_check_counts": {"LOW_SHARPE": 1, "LOW_FITNESS": 1},
            }
        },
        use_dataset_heuristics=False,
    )
    prior_results = [
        FieldTestResult(
            field_id="cash_st",
            field_type="MATRIX",
            field_name="cash_st",
            template_name="account_group_zscore_63_subindustry",
            template_family="group_zscore",
            template_stage="group_second_order",
            status="simulated",
            submittable=False,
            expression="group_rank(ts_zscore(ts_backfill(cash_st, 504), 60), subindustry)",
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=1.21, limit=1.25),
                FailedCheck(name="LOW_FITNESS", value=0.64, limit=1.0),
            ],
        )
    ]

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "cash_st", "type": "MATRIX", "name": "cash_st"},
        template_stats={},
        attempted_keys=set(),
        prior_results=prior_results,
    )

    assert total > 0
    assert disabled == 0
    assert pending
    assert pending[0].template_name.startswith("refine_")
    assert all(entry.template_name != "broad_template" for entry in pending)


def test_resimulate_stage_limits_duplicate_expression_to_one_settings_variant(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.executor.build_refine_templates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "refine_primary",
                "rank(ts_backfill(cash_st, 504))",
                1000,
                {
                    "family": "group_zscore",
                    "stage": "group_second_order",
                    "role": "refine_neighbor",
                    "activation_scope": "refine",
                },
            ),
            TemplateCandidate(
                "refine_duplicate",
                "rank(ts_backfill(cash_st, 504))",
                900,
                {
                    "family": "group_zscore",
                    "stage": "group_second_order",
                    "role": "refine_neighbor",
                    "activation_scope": "refine",
                },
            ),
        ],
    )
    monkeypatch.setattr(
        "alpha.core.executor.build_setting_variants",
        lambda *args, **kwargs: [
            {"neutralization": "SUBINDUSTRY", "truncation": 0.08},
            {"neutralization": "INDUSTRY", "truncation": 0.05},
            {"neutralization": "MARKET", "truncation": 0.05},
        ],
    )
    args = Namespace(
        dataset_id="fundamental6",
        template_disable_after=0,
        disable_legacy_after=0,
        max_templates_per_field=6,
        max_templates_per_family=3,
        legacy_similarity_penalty=0,
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
        decay=4,
        neutralization="SUBINDUSTRY",
        truncation=0.08,
        pasteurization="ON",
        unit_handling="VERIFY",
        nan_handling="OFF",
        language="FASTEXPR",
    )
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=[{"id": "cash_st", "type": "MATRIX", "name": "cash_st"}],
        template_library={},
        field_feedback={
            "cash_st": {
                "field_name": "cash_st",
                "best_score": 0.80,
                "best_template_name": "seed_template",
                "best_template_family": "group_zscore",
                "best_template_stage": "group_second_order",
                "attempted_templates": 4,
                "failed_check_counts": {"LOW_SHARPE": 1, "LOW_FITNESS": 1},
            }
        },
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )
    prior_results = [
        FieldTestResult(
            field_id="cash_st",
            field_type="MATRIX",
            field_name="cash_st",
            template_name="seed_template",
            template_family="group_zscore",
            template_stage="group_second_order",
            status="simulated",
            submittable=False,
            expression="rank(ts_backfill(cash_st, 504))",
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=1.20, limit=1.25),
                FailedCheck(name="LOW_FITNESS", value=0.79, limit=1.0),
            ],
        )
    ]

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "cash_st", "type": "MATRIX", "name": "cash_st"},
        template_stats={},
        attempted_keys=set(),
        prior_results=prior_results,
    )

    assert total == 2
    assert disabled == 0
    assert len(pending) == 1
    assert pending[0].template_name == "refine_primary"
    assert pending[0].expression == "rank(ts_backfill(cash_st, 504))"
