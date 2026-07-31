"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

from argparse import Namespace

from alpha.core.executor import build_pending_templates_for_field
from alpha.core.scheduler import handle_completed_future
from alpha.generators.expression_builder import _is_blacklisted_template
from alpha.models.domain import (
    FailedCheck,
    FieldTestResult,
    TemplateLibraryItem,
)
from alpha.models.runtime import (
    ExecutionState,
    FutureCompletionContext,
    PendingFutureContext,
    ResultWriteOptions,
    TemplateBuildContext,
    TemplateBuildOptions,
)
from alpha.policy.blacklist_store import invalidate_blacklist_path_cache
from alpha.policy.template_blacklist import invalidate_blacklist_cache


def test_scheduler_dump_results_shrinks_next_template_queue(monkeypatch, tmp_path) -> None:
    results_path = tmp_path / "results.json"
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()
    invalidate_blacklist_path_cache()
    monkeypatch.setattr("alpha.io.common.DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(
        "alpha.core.executor.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )

    args = Namespace(
        output=str(results_path),
        dataset_id="custom_ds",
        auto_update_blacklist=True,
        max_templates_per_field=1000,
        max_templates_per_family=1000,
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
    completion_ctx = FutureCompletionContext(
        result_write_options=ResultWriteOptions(
            dataset_id=args.dataset_id,
            output_path=args.output,
            auto_update_blacklist=args.auto_update_blacklist,
        ),
        settings_fingerprint="settings_fp",
        template_library_fingerprint="tpl_fp",
        run_config={"mode": "test"},
    )
    template_library = {
        "default": [
            TemplateLibraryItem(
                name="weak_template",
                expression="rank(ts_backfill({field}, {backfill_window}))",
                priority=9999,
                family="legacy_level",
                stage="first_order",
            )
        ]
    }
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=[{"id": "sales", "type": "MATRIX"}],
        template_library=template_library,
        include_templates={"weak_template"},
        use_dataset_heuristics=False,
        expression_policy=None,
    )

    before_pending, before_disabled, before_count = build_pending_templates_for_field(
        build_ctx,
        {"id": "sales", "type": "MATRIX"},
        attempted_keys=set(),
        prior_results=[],
    )
    assert before_count >= 1
    assert len(before_pending) == 1
    assert before_disabled == 0

    existing_results = [
        FieldTestResult(
            field_id="field_a",
            field_type="MATRIX",
            field_name="field_a",
            template_name="weak_template",
            template_family="legacy_level",
            template_stage="first_order",
            expression="rank(ts_backfill(field_a, 240))",
            status="simulated",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.1),
                FailedCheck(name="LOW_FITNESS", value=0.2),
            ],
        ),
        FieldTestResult(
            field_id="field_c",
            field_type="MATRIX",
            field_name="field_c",
            template_name="weak_template",
            template_family="legacy_level",
            template_stage="first_order",
            expression="rank(ts_backfill(field_c, 240))",
            status="simulated",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.12),
                FailedCheck(name="LOW_FITNESS", value=0.22),
            ],
        ),
    ]

    class _DoneFuture:
        def result(self) -> FieldTestResult:
            return FieldTestResult(
                field_id="field_b",
                field_type="MATRIX",
                field_name="field_b",
                template_name="weak_template",
                template_family="legacy_level",
                template_stage="first_order",
                expression="rank(ts_backfill(field_b, 240))",
                status="simulated",
                submittable=False,
                failed_checks=[
                    FailedCheck(name="LOW_SHARPE", value=0.1),
                    FailedCheck(name="LOW_FITNESS", value=0.2),
                ],
            )

    future = _DoneFuture()
    execution_state = ExecutionState(
        results=existing_results,
        attempted_keys=set(),
        template_stats={},
        pending_futures={
            future: PendingFutureContext(
                field_id="field_b",
                field_name="field_b",
                field_type="MATRIX",
                template_name="weak_template",
                template_family="legacy_level",
                template_stage="first_order",
                expression="rank(ts_backfill(field_b, 240))",
                settings_fingerprint="variant_fp",
            )
        },
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )
    handle_completed_future(
        future,
        completion_ctx=completion_ctx,
        execution_state=execution_state,
    )

    after_pending, after_disabled, after_count = build_pending_templates_for_field(
        build_ctx,
        {"id": "sales", "type": "MATRIX"},
        attempted_keys=set(),
        prior_results=[],
    )
    assert after_count >= 1
    assert after_pending == []
    assert after_disabled == 0
    assert _is_blacklisted_template(
        "weak_template",
        "rank(ts_backfill(sales, 240))",
        template_metadata={"family": "legacy_level", "stage": "first_order"},
        dataset_id="custom_ds",
    )
