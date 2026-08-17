"""Derived result analysis tests."""

from __future__ import annotations

from alpha.analysis.analysis_sync import ensure_analysis_synced
from alpha.analysis.report_builder import build_results_summary_payload
from alpha.analysis.results_persistence import ResultPersistenceContext, persist_results
from alpha.analysis.template_registry_rules import compile_template_registry_summary
from alpha.analysis.template_stats import compile_template_stats
from alpha.models.domain import FailedCheck, FieldTestResult


def test_compile_template_stats_excludes_self_correlation_pending_results() -> None:
    stats = compile_template_stats(
        [
            FieldTestResult(
                field_id="field_pending",
                field_type="MATRIX",
                field_name="field_pending",
                template_name="tpl",
                status="simulated",
                submittable=True,
                expression="rank(field_pending)",
                failed_checks=[FailedCheck(name="SELF_CORRELATION", result="PENDING")],
            )
        ]
    )

    assert stats == {}


def test_summary_builder_can_skip_embedded_rows_without_serializing_non_submittable_results(
    monkeypatch,
) -> None:
    result = FieldTestResult(
        field_id="field_non_submittable",
        field_type="MATRIX",
        field_name="field_non_submittable",
        template_name="tpl",
        status="simulated",
        submittable=False,
        expression="rank(field_non_submittable)",
    )
    monkeypatch.setattr(
        "alpha.analysis.report_builder.serialize_field_test_result",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("non-submittable rows should not be serialized")
        ),
    )

    summary, analysis_inputs = build_results_summary_payload(
        "fundamental6",
        [result],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        run_fingerprint="run",
        run_config={},
        results_journal_path="results.jsonl",
        include_embedded_results=False,
    )

    assert "results" not in summary
    assert analysis_inputs["submittable_results"] == []


def test_compile_template_registry_summary_reports_weak_template_stats() -> None:
    stats = compile_template_stats(
        [
            FieldTestResult(
                field_id=f"field_{idx}",
                field_type="MATRIX",
                field_name=f"field_{idx}",
                template_name="weak_template",
                template_family="mean_spread",
                template_stage="first_order",
                template_role="default_seed",
                template_activation_scope="broad",
                status="simulated",
                submittable=False,
                expression=f"rank(ts_mean(field_{idx}, 20))",
                failed_checks=[
                    FailedCheck(name="LOW_SHARPE", value=0.1),
                    FailedCheck(name="LOW_FITNESS", value=0.2),
                ],
            )
            for idx in range(6)
        ]
    )

    summary = compile_template_registry_summary(stats)
    row = next(item for item in summary if item["template_name"] == "weak_template")

    assert row["activation_scope"] == "broad"
    assert row["template_role"] == "default_seed"
    assert row["attempted"] == 6
    assert row["simulated"] == 6
    assert row["submittable"] == 0
    assert row["low_sharpe"] == 6
    assert row["low_fitness"] == 6


def test_compile_template_stats_keeps_metadata_and_outcome_rules_separate() -> None:
    stats = compile_template_stats(
        [
            FieldTestResult(
                field_id="queue_field",
                field_type="MATRIX",
                field_name="queue_field",
                template_name="tpl",
                template_family="rank",
                template_stage="first_order",
                template_role="default_seed",
                template_activation_scope="broad",
                status="error",
                failed_stage="simulation",
                message="queued too long",
            ),
            FieldTestResult(
                field_id="skipped_field",
                field_type="MATRIX",
                field_name="skipped_field",
                template_name="tpl",
                template_role="default_seed",
                template_activation_scope="broad",
                status="skipped",
            ),
            FieldTestResult(
                field_id="simulated_field",
                field_type="MATRIX",
                field_name="simulated_field",
                template_name="tpl",
                template_role="promoted_core",
                template_activation_scope="feedback_only",
                status="simulated",
                submittable=True,
                failed_checks=[
                    FailedCheck(name="LOW_SHARPE"),
                    FailedCheck(name="LOW_FITNESS"),
                    FailedCheck(name="CONCENTRATED_WEIGHT"),
                    FailedCheck(name="LOW_SUB_UNIVERSE_SHARPE"),
                ],
            ),
        ]
    )["tpl"]

    assert stats["template_family"] == "rank"
    assert stats["role_counts"] == {"default_seed": 2, "promoted_core": 1}
    assert stats["scope_counts"] == {"broad": 2, "feedback_only": 1}
    assert stats["attempted"] == 1
    assert stats["simulated"] == 1
    assert stats["submittable"] == 1
    assert stats["errors"] == 0
    assert stats["queue_timeouts"] == 1
    assert stats["low_sharpe"] == 1
    assert stats["low_fitness"] == 1
    assert stats["concentrated_weight"] == 1
    assert stats["low_sub_universe_sharpe"] == 1


def test_ensure_analysis_synced_skips_invalid_main_summary_shape(tmp_path) -> None:
    """Analysis sync should gracefully skip a valid JSON file with the wrong top-level type."""
    output_path = tmp_path / "results.json"
    output_path.write_text("[]", encoding="utf-8")

    ensure_analysis_synced(str(output_path))

    assert output_path.read_text(encoding="utf-8") == "[]"
    assert not (tmp_path / "results_analysis.json").exists()


def test_ensure_analysis_synced_only_rebuilds_derived_sidecars(tmp_path) -> None:
    """Startup repair must not rewrite the authoritative journal or main summary."""
    output_path = tmp_path / "results.json"
    persist_results(
        ResultPersistenceContext(
            output_path=str(output_path),
            dataset_id="fundamental6",
            settings_fingerprint="settings",
            template_library_fingerprint="templates",
        ),
        [
            FieldTestResult(
                field_id="field_derived",
                field_type="MATRIX",
                field_name="field_derived",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(field_derived)",
            )
        ],
        include_analysis=False,
    )
    journal_path = tmp_path / "results_results.jsonl"
    summary_before = output_path.read_bytes()
    journal_before = journal_path.read_bytes()

    ensure_analysis_synced(str(output_path))

    assert output_path.read_bytes() == summary_before
    assert journal_path.read_bytes() == journal_before
    assert (tmp_path / "results_analysis.json").exists()
    assert (tmp_path / "results_template_registry.json").exists()
