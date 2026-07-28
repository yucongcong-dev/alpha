"""Executor context construction and dry-run orchestration tests."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

from alpha.core.executor import build_template_build_context, print_dry_run_plan
from alpha.models.domain import SettingsVariant, TemplateField
from alpha.models.io_types import RunFilters
from alpha.models.runtime import ExecutionState, HistoricalRunState, PendingTemplateEntry


def _args() -> SimpleNamespace:
    return SimpleNamespace(
        dataset_id="model16",
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
        max_trade="OFF",
        max_templates_per_field=6,
        max_templates_per_family=2,
        legacy_similarity_penalty=42,
        template_disable_after=0,
        disable_legacy_after=8,
        start_date=None,
        end_date=None,
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
    return ExecutionState(
        results=[],
        attempted_keys=set(),
        template_stats={},
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )


def test_build_template_context_copies_narrow_options_and_feedback() -> None:
    history = HistoricalRunState(
        template_registry={"rank": {"recommended_role": "core"}},
        template_family_registry={"rank": {"recommended_scope": "broad"}},
        template_registry_overrides={"template_overrides": {}},
        field_feedback={"f1": {"best_score": 0.5}},
        global_failed_check_counts={"LOW_SHARPE": 3},
    )

    context = build_template_build_context(
        args=_args(),
        fields=[_field("f1")],
        template_library={},
        historical_state=history,
        filters=RunFilters(include_templates={"rank"}, exclude_templates={"raw"}),
        use_dataset_heuristics=True,
        existing_results_count=7,
    )

    assert context.options.dataset_id == "model16"
    assert context.template_library_file.endswith("model16/template.json")
    assert context.template_registry == history.template_registry
    assert context.field_feedback == history.field_feedback
    assert context.include_templates == {"rank"}
    assert context.exclude_templates == {"raw"}
    assert context.feedback_result_count == 7


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
    with (
        patch("alpha.core.executor.build_template_build_context", return_value=object()),
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
            args=_args(),
            fields=fields,
            filters=RunFilters(),
            template_library={},
            historical_state=HistoricalRunState(),
            execution_state=_execution_state(),
            use_dataset_heuristics=False,
            sample_limit=1,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert "[dry-run] planned_fields=1" in messages
    assert "[dry-run] planned_simulations=2" in messages
    assert "[dry-run] disabled_templates=1" in messages
    assert any("sample 1/1 field=active template=rank" in message for message in messages)
