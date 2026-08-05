"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

from argparse import Namespace

from alpha.core.executor import build_pending_templates_for_field, inflight_template_keys
from alpha.core.template_planning import (
    TemplatePlanningServices,
    resolve_field_template_candidates,
)
from alpha.generators.payload import build_settings_fingerprint_from_payload
from alpha.models.domain import TemplateCandidate, TemplateLibraryItem
from alpha.models.runtime import (
    PendingFutureContext,
    TemplateBuildContext,
    TemplateBuildOptions,
)
from alpha.policy.expression import get_dataset_expression_policy


def test_exploration_candidate_pool_is_not_limited_before_seed_selection() -> None:
    captured_limits: list[tuple[int, int]] = []

    def build_candidates(
        _field,
        _build_ctx,
        *,
        max_templates_per_field,
        max_templates_per_family,
        **_kwargs,
    ):
        captured_limits.append((max_templates_per_field, max_templates_per_family))
        return []

    args = Namespace(
        dataset_id="fundamental6",
        max_templates_per_field=1,
        max_templates_per_family=1,
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
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )
    services = TemplatePlanningServices(
        build_expression_candidates=build_candidates,
        build_setting_variants=lambda *_args, **_kwargs: [],
        build_settings_fingerprint=lambda _payload: "fingerprint",
    )

    resolve_field_template_candidates(
        build_ctx,
        {"id": "new_signal", "type": "MATRIX", "name": "new_signal"},
        services=services,
    )

    assert captured_limits == [(0, 0)]


def test_build_pending_templates_skips_inflight_duplicate(monkeypatch) -> None:
    settings_payload = {"neutralization": "SUBINDUSTRY", "truncation": 0.08}
    monkeypatch.setattr(
        "alpha.core.template_planning.build_setting_variants",
        lambda *args, **kwargs: [settings_payload],
    )
    monkeypatch.setattr(
        "alpha.core.template_planning.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "model51_market_zscore_decay_63",
                "ts_decay_linear(group_neutralize(ts_zscore(winsorize(ts_backfill(unsystematic_risk_last_360_days, 504), std=4), 63), market), 20)",
                1000,
                {"family": "neutralize_decay", "stage": "group_second_order"},
            )
        ],
    )
    args = Namespace(
        dataset_id="model51",
        max_templates_per_field=3,
        max_templates_per_family=1,
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
        all_fields=[
            {
                "id": "unsystematic_risk_last_360_days",
                "type": "MATRIX",
                "name": "unsystematic_risk_last_360_days",
            }
        ],
        template_library={},
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("model51"),
    )

    pending_futures = {
        object(): PendingFutureContext(
            field_id="unsystematic_risk_last_360_days",
            field_name="unsystematic_risk_last_360_days",
            field_type="MATRIX",
            template_name="model51_market_zscore_decay_63",
            template_family="neutralize_decay",
            template_stage="group_second_order",
            expression="ts_decay_linear(group_neutralize(ts_zscore(winsorize(ts_backfill(unsystematic_risk_last_360_days, 504), std=4), 63), market), 20)",
            settings_fingerprint=build_settings_fingerprint_from_payload(settings_payload),
        )
    }

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {
            "id": "unsystematic_risk_last_360_days",
            "type": "MATRIX",
            "name": "unsystematic_risk_last_360_days",
        },
        attempted_keys=set(),
        prior_results=[],
        reserved_keys=inflight_template_keys(pending_futures),
    )

    assert total >= 1
    assert disabled == 0
    assert pending == []


def test_build_pending_templates_uses_explicit_template_role(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "alpha.core.template_planning.build_setting_variants",
        lambda *args, **kwargs: [
            {"neutralization": "SUBINDUSTRY", "truncation": 0.08, "decay": 4},
            {"neutralization": "SUBINDUSTRY", "truncation": 0.08, "decay": 8},
        ],
    )
    monkeypatch.setattr(
        "alpha.core.template_planning.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "strong_template",
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
    args = Namespace(
        dataset_id="fundamental6",
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
        all_fields=[{"id": "cash_st", "type": "VECTOR", "name": "cash_st"}],
        field_feedback={"cash_st": {"attempted_templates": 1, "best_score": 0.0}},
        template_library={},
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "cash_st", "type": "VECTOR", "name": "cash_st"},
        attempted_keys=set(),
        prior_results=[],
    )

    assert total == 1
    assert disabled == 0
    assert len(pending) == 2
    assert all(item.template_role == "default_seed" for item in pending)


def test_build_pending_templates_ignores_persisted_registry_recommendation(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.template_planning.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )
    monkeypatch.setattr(
        "alpha.core.template_planning.build_expression_candidates",
        lambda *args, **kwargs: [
            TemplateCandidate(
                "persisted_core_template",
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
    args = Namespace(
        dataset_id="fundamental6",
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
        all_fields=[{"id": "cash_st", "type": "VECTOR", "name": "cash_st"}],
        field_feedback={"cash_st": {"attempted_templates": 1, "best_score": 0.0}},
        template_library={},
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "cash_st", "type": "VECTOR", "name": "cash_st"},
        attempted_keys=set(),
        prior_results=[],
    )

    assert total == 1
    assert disabled == 0
    assert len(pending) == 1
    assert pending[0].template_role == "default_seed"


def test_build_pending_templates_dedupes_same_expression_variant_across_template_names(
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
                "template_a",
                "rank(cash_st)",
                1000,
                {
                    "family": "ts_rank",
                    "stage": "first_order",
                    "role": "default_seed",
                    "activation_scope": "broad",
                },
            ),
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
            ),
        ],
    )
    args = Namespace(
        dataset_id="fundamental6",
        max_templates_per_field=6,
        max_templates_per_family=6,
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
        all_fields=[{"id": "cash_st", "type": "VECTOR", "name": "cash_st"}],
        template_library={},
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "cash_st", "type": "VECTOR", "name": "cash_st"},
        attempted_keys=set(),
        prior_results=[],
    )

    assert total == 2
    assert disabled == 0
    assert len(pending) == 1
    assert pending[0].template_name == "template_a"
    assert pending[0].expression == "rank(cash_st)"


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
    args = Namespace(
        dataset_id="fundamental6",
        max_templates_per_field=6,
        max_templates_per_family=6,
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
        all_fields=[{"id": "cash_st", "type": "VECTOR", "name": "cash_st"}],
        template_library={},
        use_dataset_heuristics=False,
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
        {"id": "cash_st", "type": "VECTOR", "name": "cash_st"},
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
    args = Namespace(
        dataset_id="fundamental6",
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
        all_fields=[
            {
                "id": "cash_st",
                "type": "VECTOR",
                "name": "cash_st",
                "runtime_field_tags": ["high_coverage"],
            }
        ],
        template_library={},
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {
            "id": "cash_st",
            "type": "VECTOR",
            "name": "cash_st",
            "runtime_field_tags": ["high_coverage"],
        },
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
    args = Namespace(
        dataset_id="fundamental6",
        max_templates_per_field=10,
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
        all_fields=[
            {
                "id": "fnd6_cptnewqeventv110_apq",
                "type": "VECTOR",
                "name": "fnd6_cptnewqeventv110_apq",
            }
        ],
        template_library={},
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, _disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "fnd6_cptnewqeventv110_apq", "type": "VECTOR", "name": "fnd6_cptnewqeventv110_apq"},
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
    args = Namespace(
        dataset_id="fundamental6",
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
        all_fields=[{"id": "cash_st", "type": "VECTOR", "name": "cash_st"}],
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
        use_dataset_heuristics=False,
        expression_policy=get_dataset_expression_policy("fundamental6"),
    )

    pending, disabled, total = build_pending_templates_for_field(
        build_ctx,
        {"id": "cash_st", "type": "VECTOR", "name": "cash_st"},
        attempted_keys=set(),
        prior_results=[],
    )

    assert total >= 1
    assert disabled == 0
    assert len(pending) == 1
