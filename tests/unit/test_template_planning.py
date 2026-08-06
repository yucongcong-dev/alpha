"""Template planning service assembly tests."""

from __future__ import annotations

from alpha.config.models import DatasetExpressionPolicy, FeedbackLoopPolicy, FeedbackPhasePolicy
import alpha.core.template_planning as template_planning
from alpha.core.template_planning import build_pending_template_variants
from alpha.models import TemplateBuildContext, TemplateBuildOptions
from alpha.models.domain import TemplateCandidate

_DEFAULT_SIM_SETTINGS = {
    "region": "USA",
    "universe": "TOP3000",
    "instrument_type": "EQUITY",
    "delay": 1,
    "decay": 4,
    "neutralization": "SUBINDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unit_handling": "VERIFY",
    "nan_handling": "OFF",
    "language": "FASTEXPR",
}


def test_low_level_planning_services_read_current_module_dependencies(monkeypatch) -> None:
    """Direct low-level callers should receive the same late-binding behavior."""

    def candidates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(template_planning, "build_expression_candidates", candidates)

    services = template_planning.build_template_planning_services()

    assert services.build_expression_candidates is candidates
    assert (
        services.build_settings_fingerprint
        is template_planning.build_settings_fingerprint_from_payload
    )


def test_preset_mode_limits_settings_variants_to_baseline() -> None:
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS, preset_mode=True)
    )
    pending = build_pending_template_variants(
        build_ctx,
        {"id": "cash_st", "type": "MATRIX"},
        templates=[
            TemplateCandidate(
                name="manual_group_rank",
                expression="group_rank(cash_st, subindustry)",
                priority=100,
                metadata={},
            )
        ],
        attempted_keys=set(),
        reserved_keys=set(),
        field_feedback={"best_score": 1.0, "attempted_templates": 3},
    )

    assert len(pending) == 1


def test_resimulate_budget_prioritizes_decay_variants() -> None:
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS),
        expression_policy=DatasetExpressionPolicy(
            feedback_loop_policy=FeedbackLoopPolicy(
                generate=FeedbackPhasePolicy(settings_variant_budget=1),
                resimulate=FeedbackPhasePolicy(
                    min_attempted_templates=3,
                    min_best_score=0.5,
                    settings_variant_budget=3,
                ),
            ),
        ),
    )
    pending = build_pending_template_variants(
        build_ctx,
        {"id": "cash_st", "type": "MATRIX"},
        templates=[
            TemplateCandidate(
                name="manual_group_rank",
                expression="group_rank(cash_st, subindustry)",
                priority=100,
                metadata={},
            )
        ],
        attempted_keys=set(),
        reserved_keys=set(),
        field_feedback={"best_score": 1.0, "attempted_templates": 3},
    )

    assert len(pending) == 3
    assert {entry.settings_variant.get("decay") for entry in pending} == {2, 4, 6}


def test_resimulate_budget_can_include_full_settings_variant_set() -> None:
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS),
        expression_policy=DatasetExpressionPolicy(
            feedback_loop_policy=FeedbackLoopPolicy(
                generate=FeedbackPhasePolicy(settings_variant_budget=1),
                resimulate=FeedbackPhasePolicy(
                    min_attempted_templates=3,
                    min_best_score=0.5,
                    settings_variant_budget=5,
                ),
            ),
        ),
    )
    pending = build_pending_template_variants(
        build_ctx,
        {"id": "cash_st", "type": "MATRIX"},
        templates=[
            TemplateCandidate(
                name="manual_group_rank",
                expression="group_rank(cash_st, subindustry)",
                priority=100,
                metadata={},
            )
        ],
        attempted_keys=set(),
        reserved_keys=set(),
        field_feedback={"best_score": 1.0, "attempted_templates": 3},
    )

    assert len(pending) == 5
    assert {entry.settings_variant.get("decay") for entry in pending} == {2, 4, 6}
    assert any(entry.settings_variant.get("truncation") == 0.05 for entry in pending)
    assert any(entry.settings_variant.get("neutralization") == "INDUSTRY" for entry in pending)
