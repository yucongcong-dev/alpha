"""Executor context construction and dry-run orchestration tests."""

from __future__ import annotations

import logging
from unittest.mock import patch

from alpha.core.execution_filters import resolve_template_skip_reason
from alpha.core.executor import (
    build_pending_templates_for_field,
    build_template_build_context,
    print_dry_run_plan,
)
from alpha.models.domain import SettingsVariant, TemplateCandidate, TemplateField
from alpha.models.io_types import RunFilters
from alpha.models.runtime_options import TemplateBuildOptions
from alpha.policy.expression import get_dataset_expression_policy
from alpha.runtime.contexts import HistoricalRunState, PendingTemplateEntry, TemplateBuildContext
from alpha.runtime.state import ExecutionState

from .template_build_options_support import template_build_options


def _options() -> TemplateBuildOptions:
    return template_build_options(
        dataset_id="model16",
        max_templates_per_field=6,
        max_templates_per_family=2,
        similarity_penalty=42,
        template_library_file="datasets/model16/template.json",
    )


def _field(field_id: str) -> TemplateField:
    return TemplateField(
        field_id=field_id,
        field_name=field_id,
        field_type="MATRIX",
        metadata={"id": field_id, "name": field_id, "type": "MATRIX"},
    )


def _execution_state() -> ExecutionState:
    return ExecutionState.create()


def test_build_template_context_copies_narrow_options_and_feedback() -> None:
    history = HistoricalRunState(
        field_feedback={"f1": {"best_score": 0.5}},
        global_failed_check_counts={"LOW_SHARPE": 3},
    )

    context = build_template_build_context(
        options=_options(),
        fields=[_field("f1")],
        template_library={},
        historical_state=history,
        filters=RunFilters(include_templates={"rank"}, exclude_templates={"raw"}),
        expression_policy=get_dataset_expression_policy("model16"),
        existing_results_count=7,
    )

    assert context.options.dataset_id == "model16"
    assert context.template_library_file.endswith("model16/template.json")
    assert context.field_feedback == history.field_feedback
    assert context.include_templates == {"rank"}
    assert context.exclude_templates == {"raw"}
    assert context.feedback_result_count == 7
    assert context.expression_policy is not None
    assert context.feedback_template_min_priority == _options().feedback_template_min_priority


def test_unexplored_field_gets_one_seed(monkeypatch) -> None:
    field = _field("new_signal")
    candidate = TemplateCandidate(
        name="seed",
        expression="rank(new_signal)",
        priority=1000,
        metadata={"family": "rank", "activation_scope": "broad"},
    )
    context = TemplateBuildContext(
        options=_options(),
        all_fields=[field],
        expression_policy=get_dataset_expression_policy("model16"),
    )
    monkeypatch.setattr(
        "alpha.core.executor.resolve_field_template_candidates",
        lambda *_args, **_kwargs: ([candidate], {}, get_dataset_expression_policy("model16")),
    )

    pending, _, _ = build_pending_templates_for_field(
        context,
        field,
        attempted_keys=set(),
        prior_results=[],
    )

    assert len(pending) == 1
    assert pending[0].template_name == "seed"


def test_unexplored_field_prefers_explicit_seed_over_high_priority_refine(monkeypatch) -> None:
    field = _field("new_signal")
    refine = TemplateCandidate(
        name="high_priority_refine",
        expression="group_rank(new_signal, industry)",
        priority=1200,
        metadata={"role": "refine_neighbor", "activation_scope": "broad"},
    )
    seed = TemplateCandidate(
        name="simple_seed",
        expression="rank(ts_rank(new_signal, 120))",
        priority=900,
        metadata={"role": "default_seed", "activation_scope": "broad"},
    )
    context = TemplateBuildContext(
        options=_options(),
        all_fields=[field],
        expression_policy=get_dataset_expression_policy("model16"),
    )
    monkeypatch.setattr(
        "alpha.core.executor.resolve_field_template_candidates",
        lambda *_args, **_kwargs: (
            [refine, seed],
            {},
            get_dataset_expression_policy("model16"),
        ),
    )

    pending, _, _ = build_pending_templates_for_field(
        context,
        field,
        attempted_keys=set(),
        prior_results=[],
    )

    assert [item.template_name for item in pending] == ["simple_seed"]


def test_unexplored_fields_rotate_across_explicit_seed_templates(monkeypatch) -> None:
    seeds = [
        TemplateCandidate(
            name=f"seed_{index}",
            expression=f"rank(signal) + {index}",
            priority=1000 - index,
            metadata={"role": "default_seed", "activation_scope": "broad"},
        )
        for index in range(3)
    ]
    context = TemplateBuildContext(
        options=_options(),
        expression_policy=get_dataset_expression_policy("model16"),
    )
    monkeypatch.setattr(
        "alpha.core.executor.resolve_field_template_candidates",
        lambda *_args, **_kwargs: (
            seeds,
            {},
            get_dataset_expression_policy("model16"),
        ),
    )

    selected = set()
    for index in range(12):
        pending, _, _ = build_pending_templates_for_field(
            context,
            _field(f"field_{index}"),
            attempted_keys=set(),
            prior_results=[],
        )
        selected.add(pending[0].template_name)

    assert selected == {"seed_0", "seed_1", "seed_2"}


def test_unexplored_fields_rotate_across_fallback_templates(monkeypatch) -> None:
    fallbacks = [
        TemplateCandidate(
            name=f"fallback_{index}",
            expression=f"rank(signal) + {index}",
            priority=1200 - index,
            metadata={"role": "refine_neighbor", "activation_scope": "broad"},
        )
        for index in range(4)
    ]
    context = TemplateBuildContext(
        options=_options(),
        expression_policy=get_dataset_expression_policy("model16"),
    )
    monkeypatch.setattr(
        "alpha.core.executor.resolve_field_template_candidates",
        lambda *_args, **_kwargs: (
            fallbacks,
            {},
            get_dataset_expression_policy("model16"),
        ),
    )

    selected = set()
    for index in range(16):
        pending, _, _ = build_pending_templates_for_field(
            context,
            _field(f"field_{index}"),
            attempted_keys=set(),
            prior_results=[],
        )
        selected.add(pending[0].template_name)

    assert selected == {"fallback_0", "fallback_1", "fallback_2", "fallback_3"}


def test_template_skip_reason_explains_name_filter() -> None:
    field = _field("signal")
    candidate = TemplateCandidate(
        name="seed",
        expression="rank(signal)",
        priority=1000,
        metadata={"family": "rank", "activation_scope": "broad"},
    )
    context = TemplateBuildContext(
        options=_options(),
        all_fields=[field],
        include_templates={"other"},
        expression_policy=get_dataset_expression_policy("model16"),
    )

    assert (
        resolve_template_skip_reason(
            template=candidate,
            build_ctx=context,
            field_id="signal",
            field_name="signal",
            field_feedback={},
            expression_policy=get_dataset_expression_policy("model16"),
            prior_results=[],
        )
        == "name_filter"
    )


def test_template_skip_reason_explains_blacklist_match(monkeypatch) -> None:
    field = _field("signal")
    candidate = TemplateCandidate(
        name="blocked",
        expression="rank(signal)",
        priority=1000,
        metadata={"family": "rank", "stage": "first_order"},
    )
    context = TemplateBuildContext(
        options=_options(),
        all_fields=[field],
        expression_policy=get_dataset_expression_policy("model16"),
    )
    monkeypatch.setattr(
        "alpha.selection.feedback_filters._is_blacklisted_template",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "alpha.selection.feedback_filters.runtime_blacklist_match_reason",
        lambda *_args, **_kwargs: "name+stage",
    )

    assert (
        resolve_template_skip_reason(
            template=candidate,
            build_ctx=context,
            field_id="signal",
            field_name="signal",
            field_feedback={},
            expression_policy=get_dataset_expression_policy("model16"),
            prior_results=[],
        )
        == "blacklist_name_stage"
    )


def test_build_pending_templates_records_name_filter_reason(monkeypatch) -> None:
    field = _field("signal")
    candidate = TemplateCandidate(
        name="seed",
        expression="rank(signal)",
        priority=1000,
        metadata={"family": "rank", "activation_scope": "broad"},
    )
    context = TemplateBuildContext(
        options=_options(),
        all_fields=[field],
        include_templates={"other"},
        expression_policy=get_dataset_expression_policy("model16"),
    )
    monkeypatch.setattr(
        "alpha.core.executor.resolve_field_template_candidates",
        lambda *_args, **_kwargs: (
            [candidate],
            {"attempted": 1},
            get_dataset_expression_policy("model16"),
        ),
    )
    reasons: dict[str, int] = {}

    pending, disabled, total = build_pending_templates_for_field(
        context,
        field,
        attempted_keys=set(),
        prior_results=[],
        template_skip_reasons=reasons,
    )

    assert pending == []
    assert disabled == 0
    assert total == 1
    assert reasons == {"template_filtered_name_filter": 1}


def test_build_pending_templates_records_blacklist_reason(monkeypatch) -> None:
    field = _field("signal")
    candidate = TemplateCandidate(
        name="blocked",
        expression="rank(signal)",
        priority=1000,
        metadata={"family": "rank", "stage": "first_order"},
    )
    context = TemplateBuildContext(
        options=_options(),
        all_fields=[field],
        expression_policy=get_dataset_expression_policy("model16"),
    )
    monkeypatch.setattr(
        "alpha.core.executor.resolve_field_template_candidates",
        lambda *_args, **_kwargs: (
            [candidate],
            {"attempted": 1},
            get_dataset_expression_policy("model16"),
        ),
    )
    monkeypatch.setattr(
        "alpha.selection.feedback_filters._is_blacklisted_template",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "alpha.selection.feedback_filters.runtime_blacklist_match_reason",
        lambda *_args, **_kwargs: "name+stage",
    )
    reasons: dict[str, int] = {}

    pending, disabled, total = build_pending_templates_for_field(
        context,
        field,
        attempted_keys=set(),
        prior_results=[],
        template_skip_reasons=reasons,
    )

    assert pending == []
    assert disabled == 1
    assert total == 1
    assert reasons == {"template_filtered_blacklist_name_stage": 1}


def test_print_dry_run_plan_counts_only_actionable_fields(caplog) -> None:
    fields = [_field("skip"), _field("empty"), _field("active")]
    entry = PendingTemplateEntry(
        template_name="rank",
        template_family="rank",
        template_stage="first_order",
        template_role="core",
        template_activation_scope="broad",
        expression="rank(active)",
        priority=200,
        settings_variant=SettingsVariant(decay=4),
        variant_fingerprint="settings-1",
    )

    def pending_for_field(_ctx, field, **_kwargs):
        if field.field_id == "empty":
            return [], 0, 0
        return [entry, entry], 1, 2

    caplog.set_level(logging.INFO)
    options = _options()
    with (
        patch(
            "alpha.core.executor.build_template_build_context",
            return_value=TemplateBuildContext(options=options),
        ),
        patch(
            "alpha.core.executor.should_skip_field",
            side_effect=lambda field_id, *_args: field_id == "skip",
        ),
        patch(
            "alpha.core.executor.build_pending_templates_for_field",
            side_effect=pending_for_field,
        ),
    ):
        print_dry_run_plan(
            options=options,
            fields=fields,
            filters=RunFilters(),
            template_library={},
            historical_state=HistoricalRunState(),
            execution_state=_execution_state(),
            expression_policy=get_dataset_expression_policy("model16"),
            full_run=False,
            max_total_simulations=1,
            sample_limit=1,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert "[dry-run] planned_fields=1" in messages
    assert "[dry-run] eligible_simulations=2" in messages
    assert "[dry-run] scheduled_simulations=1" in messages
    assert "[dry-run] budget_truncated=true" in messages
    assert "[dry-run] filtered_templates=1" in messages
    assert (
        "[dry-run] explain_summary fields_total=3 planned=1 skipped=1 "
        "unactionable=1 templates_eligible=2 templates_scheduled=1 templates_filtered=1"
    ) in messages
    assert (
        "[dry-run] explain_fields skipped_queue=0 skipped_include=0 "
        "skipped_exclude=0 skipped_unknown=1 unactionable=1"
    ) in messages
    assert "[dry-run] explain_templates name_filter=0 feedback=0 family=0 history=0" in messages
    assert (
        "[dry-run] explain_blacklist name_stage=0 name_stage_family=0 "
        "name_family=0 pattern_expression=0 "
        "pattern_template_name=0 other=0"
    ) in messages
    assert (
        "[dry-run] explain_feedback generate_no_feedback=2 generate_attempts=0 "
        "generate_score=0 generate_other=0 resimulate=0 settings_budget=2"
    ) in messages
    assert any("sample 1/1 field=active template=rank" in message for message in messages)


def test_print_dry_run_plan_explains_feedback_stage_reasons(caplog) -> None:
    fields = [
        _field("new"),
        _field("few_attempts"),
        _field("low_score"),
        _field("strong"),
    ]
    entry = PendingTemplateEntry(
        template_name="rank",
        template_family="rank",
        template_stage="first_order",
        template_role="core",
        template_activation_scope="broad",
        expression="rank(field)",
        priority=200,
        settings_variant=SettingsVariant(decay=4),
        variant_fingerprint="settings-1",
    )
    historical_state = HistoricalRunState(
        field_feedback={
            "few_attempts": {"attempted_templates": 1, "best_score": 0.9},
            "low_score": {"attempted_templates": 3, "best_score": 0.1},
            "strong": {"attempted_templates": 3, "best_score": 0.9},
        }
    )

    caplog.set_level(logging.INFO)
    with patch(
        "alpha.core.executor.build_pending_templates_for_field",
        return_value=([entry], 0, 1),
    ):
        print_dry_run_plan(
            options=_options(),
            fields=fields,
            filters=RunFilters(),
            template_library={},
            historical_state=historical_state,
            execution_state=_execution_state(),
            expression_policy=get_dataset_expression_policy("model16"),
            full_run=False,
            max_total_simulations=0,
            sample_limit=1,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert (
        "[dry-run] explain_feedback generate_no_feedback=1 generate_attempts=1 "
        "generate_score=1 generate_other=0 resimulate=1 settings_budget=6"
    ) in messages


def test_print_dry_run_plan_reports_partial_full_run_seed_budget(caplog) -> None:
    fields = [_field("f1"), _field("f2")]
    entry = PendingTemplateEntry(
        template_name="seed",
        template_family="rank",
        template_stage="first_order",
        template_role="core",
        template_activation_scope="broad",
        expression="rank(field)",
        priority=100,
        settings_variant=SettingsVariant(),
        variant_fingerprint="settings",
    )
    caplog.set_level(logging.INFO)

    with patch(
        "alpha.core.executor.build_pending_templates_for_field",
        return_value=([entry], 0, 1),
    ):
        print_dry_run_plan(
            options=_options(),
            fields=fields,
            filters=RunFilters(),
            template_library={},
            historical_state=HistoricalRunState(),
            execution_state=_execution_state(),
            expression_policy=get_dataset_expression_policy("model16"),
            full_run=True,
            max_total_simulations=1,
            sample_limit=1,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert "[dry-run] full_run_seed resolved=0 remaining=2 budget_sufficient=false" in messages
    assert (
        "[dry-run] full_run_budget seed_eligible=2 refine_eligible=0 "
        "seed_scheduled=1 refine_scheduled=0"
    ) in messages
    assert "[dry-run] full_run_schedule seed=1 refine=0" in messages


def test_print_dry_run_plan_allocates_remaining_budget_to_refine(caplog) -> None:
    fields = [_field("f1"), _field("f2")]
    entries = [
        PendingTemplateEntry(
            template_name="seed",
            template_family="rank",
            template_stage="first_order",
            template_role="default_seed",
            template_activation_scope="broad",
            expression="rank(field)",
            priority=100,
            settings_variant=SettingsVariant(),
            variant_fingerprint="seed-settings",
        ),
        PendingTemplateEntry(
            template_name="refine",
            template_family="rank",
            template_stage="first_order",
            template_role="refine_neighbor",
            template_activation_scope="broad",
            expression="ts_rank(field, 20)",
            priority=200,
            settings_variant=SettingsVariant(),
            variant_fingerprint="refine-settings",
        ),
    ]
    caplog.set_level(logging.INFO)

    with patch(
        "alpha.core.executor.build_pending_templates_for_field",
        return_value=(entries, 0, len(entries)),
    ):
        print_dry_run_plan(
            options=_options(),
            fields=fields,
            filters=RunFilters(),
            template_library={},
            historical_state=HistoricalRunState(),
            execution_state=_execution_state(),
            expression_policy=get_dataset_expression_policy("model16"),
            full_run=True,
            max_total_simulations=3,
            sample_limit=1,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert (
        "[dry-run] full_run_budget seed_eligible=2 refine_eligible=2 "
        "seed_scheduled=2 refine_scheduled=1"
    ) in messages


def test_print_dry_run_plan_samples_explicit_default_seed(caplog) -> None:
    field = _field("f1")
    refine_entry = PendingTemplateEntry(
        template_name="high-priority-refine",
        template_family="ratio",
        template_stage="group_second_order",
        template_role="refine_neighbor",
        template_activation_scope="broad",
        expression="group_rank(f1, industry)",
        priority=1200,
        settings_variant=SettingsVariant(),
        variant_fingerprint="refine-settings",
    )
    seed_entry = PendingTemplateEntry(
        template_name="generic-seed",
        template_family="rank",
        template_stage="first_order",
        template_role="default_seed",
        template_activation_scope="broad",
        expression="rank(f1)",
        priority=900,
        settings_variant=SettingsVariant(),
        variant_fingerprint="seed-settings",
    )
    caplog.set_level(logging.INFO)

    with patch(
        "alpha.core.executor.build_pending_templates_for_field",
        return_value=([refine_entry, seed_entry], 0, 2),
    ):
        print_dry_run_plan(
            options=_options(),
            fields=[field],
            filters=RunFilters(),
            template_library={},
            historical_state=HistoricalRunState(),
            execution_state=_execution_state(),
            expression_policy=get_dataset_expression_policy("model16"),
            full_run=True,
            max_total_simulations=0,
            sample_limit=1,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any("template=generic-seed" in message for message in messages)
    assert not any("template=high-priority-refine" in message for message in messages)
