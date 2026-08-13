"""Template candidate feedback and metadata planning tests."""

from __future__ import annotations

from alpha.core.executor import build_pending_templates_for_field
from alpha.generators.payload import build_settings_fingerprint_from_payload
from alpha.models.domain import TemplateCandidate, TemplateField, TemplateLibraryItem
from alpha.policy.expression import get_dataset_expression_policy
from alpha.runtime.contexts import TemplateBuildContext

from .template_build_options_support import template_build_options


def _field(
    field_id: str,
    field_type: str = "VECTOR",
    *,
    metadata: dict[str, object] | None = None,
) -> TemplateField:
    return TemplateField(
        field_id=field_id,
        field_name=field_id,
        field_type=field_type,
        metadata=dict(metadata or {}),
    )


def test_build_pending_templates_skips_attempted_expression_variant_across_template_names(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "alpha.core.template_planning.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )
    monkeypatch.setattr(
        "alpha.core.template_planning.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "template_b",
                "rank(cash_st)",
                900,
                {
                    "family": "ts_rank",
                    "stage": "first_order",
                    "role": "refine_neighbor",
                    "activation_scope": "refine",
                },
            )
        ],
    )
    options = template_build_options(
        dataset_id="fundamental6",
        max_templates_per_field=6,
        max_templates_per_family=6,
        similarity_penalty=0,
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
        options=options,
        all_fields=[_field("cash_st")],
        template_library={},
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )
    attempted_keys = {
        (
            "cash_st",
            "template_a",
            "rank(cash_st)",
            build_settings_fingerprint_from_payload(
                {"neutralization": "SUBINDUSTRY", "truncation": 0.08}
            ),
        )
    }

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        _field("cash_st"),
        attempted_keys=attempted_keys,
        prior_results=[],
    )

    assert total == 1
    assert disabled == 0
    assert pending == []


def test_build_pending_templates_uses_template_metadata_without_registry_override(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "alpha.core.template_planning.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )
    monkeypatch.setattr(
        "alpha.core.template_planning.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "manual_override_template",
                "rank(cash_st)",
                1000,
                {
                    "family": "ts_rank",
                    "stage": "first_order",
                    "role": "default_seed",
                    "activation_scope": "broad",
                },
            )
        ],
    )
    options = template_build_options(
        dataset_id="fundamental6",
        max_templates_per_field=6,
        max_templates_per_family=3,
        similarity_penalty=0,
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
        options=options,
        all_fields=[_field("cash_st", metadata={"runtime_field_tags": ["high_coverage"]})],
        template_library={},
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        _field("cash_st", metadata={"runtime_field_tags": ["high_coverage"]}),
        attempted_keys=set(),
        prior_results=[],
    )

    assert total == 1
    assert disabled == 0
    assert len(pending) == 1
    assert pending[0].template_role == "default_seed"


def test_event_field_exploration_uses_one_seed_template(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.template_planning.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )
    monkeypatch.setattr(
        "alpha.core.template_planning.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "vec_avg_ts_rank_63",
                "rank(ts_rank(vec_avg(x), 63))",
                100,
                {"family": "ts_rank", "stage": "first_order"},
            ),
            TemplateCandidate(
                "vec_avg_ts_zscore_63",
                "rank(ts_zscore(vec_avg(x), 63))",
                99,
                {"family": "zscore_time", "stage": "first_order"},
            ),
            TemplateCandidate(
                "vec_avg_decay_20",
                "rank(ts_decay_linear(vec_avg(x), 20))",
                98,
                {"family": "decay_level", "stage": "first_order"},
            ),
            TemplateCandidate(
                "iter_reuse_best_trade_when_volume_expansion",
                "trade_when(ts_mean(volume, 10) > ts_mean(volume, 60), rank(x), -1)",
                97,
                {"family": "event_trade_when", "stage": "event_conditioned"},
            ),
        ],
    )
    options = template_build_options(
        dataset_id="fundamental6",
        max_templates_per_field=10,
        max_templates_per_family=3,
        similarity_penalty=0,
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
        options=options,
        all_fields=[_field("fnd6_cptnewqeventv110_apq")],
        template_library={},
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, _disabled, total = build_pending_templates_for_field(
        build_ctx,
        _field("fnd6_cptnewqeventv110_apq"),
        attempted_keys=set(),
        prior_results=[],
    )

    assert total == 4
    assert len(pending) == 1


def test_build_pending_templates_does_not_hard_demote_from_global_stats(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.template_planning.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )
    monkeypatch.setattr(
        "alpha.core.template_planning.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "weak_template",
                "rank(cash_st)",
                1000,
                {
                    "family": "mean_spread",
                    "stage": "first_order",
                    "role": "default_seed",
                    "activation_scope": "broad",
                },
            )
        ],
    )
    options = template_build_options(
        dataset_id="fundamental6",
        max_templates_per_field=6,
        max_templates_per_family=3,
        similarity_penalty=0,
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
        options=options,
        all_fields=[_field("cash_st")],
        field_feedback={"cash_st": {"attempted_templates": 1, "best_score": -999.0}},
        template_library={
            "default": [
                TemplateLibraryItem(
                    name="weak_template",
                    expression="rank({field})",
                    priority=1000,
                    family="mean_spread",
                    stage="first_order",
                    metadata={"role": "default_seed", "activation_scope": "broad"},
                )
            ]
        },
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        _field("cash_st"),
        attempted_keys=set(),
        prior_results=[],
    )

    assert total >= 1
    assert disabled == 0
    assert len(pending) == 1
