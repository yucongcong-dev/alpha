"""Feedback-stage, history, and settings-budget tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

from alpha.analysis.feedback_history import (
    build_historical_run_state,
    choose_settings_variant_budget,
    rebuild_historical_run_state,
)
from alpha.analysis.results_loader import load_existing_results
from alpha.analysis.results_persistence import dump_results
from alpha.generators.variants import build_setting_variants
from alpha.models.domain import FieldTestResult
from alpha.policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from alpha.runtime.contexts import HistoricalRunState
from alpha.selection import feedback_filters as feedback_filters_module
from alpha.selection.feedback_filters import should_keep_template_for_feedback


def test_high_conviction_ratio_recognizes_optional_whitespace() -> None:
    keep = should_keep_template_for_feedback(
        "custom_ratio",
        "rank(cashflow_op / assets)",
        200,
        {
            "best_score": 0.5,
            "attempted_templates": 2,
            "failed_check_counts": {"LOW_SHARPE": 4},
        },
        expression_policy=get_dataset_expression_policy("fundamental6"),
        template_metadata={"family": "legacy_ratio"},
    )

    assert keep is True


def test_fundamental6_maintenance_policy_disables_feedback_priority_pruning(monkeypatch) -> None:
    monkeypatch.setattr(
        feedback_filters_module,
        "get_runtime_config",
        lambda: SimpleNamespace(feedback=SimpleNamespace(feedback_template_min_priority=175)),
    )

    keep = should_keep_template_for_feedback(
        "custom_template",
        "rank(custom_field)",
        174,
        {"best_score": 0.5, "attempted_templates": 3, "failed_check_counts": {}},
        expression_policy=get_dataset_expression_policy("fundamental6"),
        template_metadata={"family": "custom"},
    )

    assert keep is True


def test_load_existing_results_reads_template_family(tmp_path) -> None:
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

    assert results[0].template_family == "ts_rank"
    assert results[0].template_stage == "first_order"


def test_feedback_stage_and_settings_budget_advance_for_strong_history() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    feedback = {"best_score": 0.55, "attempted_templates": 4}

    assert resolve_feedback_stage(feedback, policy.feedback_loop_policy) == "resimulate"
    assert choose_settings_variant_budget(None, expression_policy=policy) == 1
    assert choose_settings_variant_budget(feedback, expression_policy=policy) == 5


def test_build_historical_run_state_uses_dataset_feedback_across_runs(tmp_path) -> None:
    run_output = tmp_path / "runs" / "new-run" / "summary.json"
    feedback_output = tmp_path / "feedback" / "summary.json"
    historical = FieldTestResult(
        field_id="cash_st",
        field_type="MATRIX",
        field_name="cash_st",
        template_name="weak_template",
        status="simulated",
        submittable=False,
        expression="rank(cash_st)",
        settings_fingerprint="settings-v1",
        failed_checks=[{"name": "LOW_SHARPE", "value": 0.2}],
    )
    dump_results(
        str(feedback_output),
        "fundamental6",
        [historical],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        include_analysis=False,
    )

    state = build_historical_run_state(str(run_output), str(feedback_output))

    assert state.feedback_results == [historical]
    assert ("cash_st", "weak_template", "rank(cash_st)", "settings-v1") in state.attempted_keys


def test_rebuild_historical_run_state_refreshes_all_derived_feedback() -> None:
    pending = FieldTestResult(
        field_id="cash_st",
        field_type="MATRIX",
        field_name="cash_st",
        template_name="candidate",
        status="simulated",
        submittable=None,
        message="checks pending",
        expression="rank(cash_st)",
        settings_fingerprint="settings-v1",
    )
    resolved = FieldTestResult(
        field_id="cash_st",
        field_type="MATRIX",
        field_name="cash_st",
        template_name="candidate",
        status="simulated",
        submittable=True,
        message="checks passed",
        expression="rank(cash_st)",
        settings_fingerprint="settings-v1",
    )
    state = HistoricalRunState(
        existing_results=[pending],
        feedback_results=[pending],
        field_feedback={},
        global_failed_check_counts={"SELF_CORRELATION": 1},
    )

    rebuilt = rebuild_historical_run_state(state, [resolved])

    assert rebuilt.feedback_results == [resolved]
    assert rebuilt.field_feedback["cash_st"]["submittable_templates"] == 1
    assert rebuilt.global_failed_check_counts == {}


def test_build_setting_variants_keeps_explicit_refine_small_and_deterministic() -> None:
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
        max_trade = "OFF"
        language = "FASTEXPR"
        start_date = None
        end_date = None

    variants = build_setting_variants(
        _Args(),
        "explicit_refine",
        "group_rank(ts_zscore(ts_backfill(cash_st, 504), 60), subindustry)",
    )

    assert len(variants) == 5
    assert [variant.get("decay") for variant in variants[:3]] == [4, 6, 2]
    assert any(variant.get("truncation") == 0.05 for variant in variants)
    assert any(variant.get("neutralization") == "INDUSTRY" for variant in variants)
    assert all(variant.to_dict().get("maxTrade") == "OFF" for variant in variants)
