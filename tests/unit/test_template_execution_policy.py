from __future__ import annotations

from alpha.analysis.template_execution_policy import build_template_execution_decision


def test_build_template_execution_decision_applies_override_and_priority_bonus() -> None:
    template_metadata = {
        "role": "default_seed",
        "activation_scope": "broad",
    }
    decision = build_template_execution_decision(
        template_name="ratio_cap_zscore_60",
        expression="rank(ts_zscore(x/cap, 60))",
        priority=100,
        template_family="ratio_cap",
        template_stage="account",
        template_metadata=template_metadata,
        template_stats={
            "ratio_cap_zscore_60": {
                "attempted": 5,
                "simulated": 3,
                "submittable": 0,
                "errors": 0,
                "low_sharpe": 0,
                "low_fitness": 0,
                "concentrated_weight": 0,
            }
        },
        template_registry={},
        template_family_registry={},
        template_registry_overrides={
            "template_overrides": {
                "ratio_cap_zscore_60": {
                    "recommended_scope": "refine",
                    "recommended_role": "refine_neighbor",
                    "priority_adjustment": 7,
                    "reason": "manual_refine_focus",
                }
            },
            "family_overrides": {},
            "field_cluster_overrides": {},
        },
        field_id="cashflow_op",
        field_name="cashflow_op",
        field_tags=[],
        base_variant_budget=2,
        feedback_stage="generate",
    )

    assert decision is not None
    assert decision.template_role == "refine_neighbor"
    assert decision.template_activation_scope == "refine"
    assert decision.effective_priority > 100
    assert decision.effective_variant_budget == 1
    assert template_metadata["registry_reason"] == "manual_refine_focus"


def test_build_template_execution_decision_suppresses_generate_for_persistent_failures() -> None:
    decision = build_template_execution_decision(
        template_name="weak_template",
        expression="rank(x)",
        priority=50,
        template_family="legacy_level",
        template_stage="time_series",
        template_metadata={},
        template_stats={
            "weak_template": {
                "attempted": 8,
                "submittable": 0,
                "simulated": 0,
                "errors": 0,
                "low_sharpe": 4,
                "low_fitness": 4,
                "concentrated_weight": 0,
            }
        },
        template_registry={},
        template_family_registry={},
        template_registry_overrides={
            "template_overrides": {},
            "family_overrides": {},
            "field_cluster_overrides": {},
        },
        field_id="f1",
        field_name="f1",
        field_tags=[],
        base_variant_budget=2,
        feedback_stage="generate",
    )

    assert decision is None
