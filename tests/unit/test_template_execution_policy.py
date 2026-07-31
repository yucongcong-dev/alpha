from __future__ import annotations

from alpha.analysis.template_execution_policy import build_template_execution_decision


def test_build_template_execution_decision_uses_explicit_metadata_and_budget() -> None:
    decision = build_template_execution_decision(
        template_name="ratio_cap_zscore_60",
        expression="rank(ts_zscore(x/cap, 60))",
        priority=100,
        template_family="ratio_cap",
        template_stage="account",
        template_metadata={"role": "default_seed", "activation_scope": "broad"},
        field_id="cashflow_op",
        field_name="cashflow_op",
        base_variant_budget=2,
    )

    assert decision.template_role == "default_seed"
    assert decision.template_activation_scope == "broad"
    assert decision.effective_priority == 100
    assert decision.effective_variant_budget == 2


def test_build_template_execution_decision_rebuilds_refine_candidate() -> None:
    decision = build_template_execution_decision(
        template_name="refine_template",
        expression="rank(x)",
        priority=50,
        template_family="ts_rank",
        template_stage="first_order",
        template_metadata={
            "refine_score": 0.7,
            "refine_failed_checks": [{"name": "LOW_SHARPE", "value": 1.1}],
        },
        field_id="f1",
        field_name="f1",
        base_variant_budget=1,
    )

    assert decision.refine_candidate is not None
    assert decision.refine_candidate.score == 0.7
    assert decision.refine_candidate.failed_checks[0].name == "LOW_SHARPE"
