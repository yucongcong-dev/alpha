"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

import json

from alpha.generators.templates.variation_common import (
    is_blacklisted_template as _is_blacklisted_template,
)
from alpha.models.domain import FailedCheck, FieldTestResult
from alpha.policy.blacklist_runtime_stats import build_blacklist_runtime_stats
from alpha.policy.blacklist_runtime_updates import auto_update_blacklist
from alpha.policy.blacklist_store import ensure_template_blacklist_file
from alpha.policy.template_blacklist import invalidate_blacklist_cache


def test_blacklist_runtime_stats_separate_same_template_by_field_type() -> None:
    results = [
        FieldTestResult(
            field_id="matrix_field",
            field_type="MATRIX",
            field_name="matrix_field",
            template_name="shared_template",
            template_family="ts_rank",
            template_stage="first_order",
            status="simulated",
            failed_checks=[FailedCheck(name="LOW_SHARPE", value=0.1)],
        ),
        FieldTestResult(
            field_id="vector_field",
            field_type="VECTOR",
            field_name="vector_field",
            template_name="shared_template",
            template_family="ts_rank",
            template_stage="first_order",
            status="simulated",
            failed_checks=[FailedCheck(name="LOW_SHARPE", value=0.2)],
        ),
    ]

    stats = build_blacklist_runtime_stats(results)

    assert len(stats) == 2
    assert {summary.field_type for summary in stats.values()} == {"MATRIX", "VECTOR"}


def test_ensure_template_blacklist_file_creates_empty_dataset_file(tmp_path) -> None:
    """Missing dataset blacklist files should be created with the expected schema."""
    path = ensure_template_blacklist_file("custom_ds", datasets_root=str(tmp_path / "datasets"))

    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    payload = json.loads(blacklist_file.read_text(encoding="utf-8"))
    assert path == str(blacklist_file)
    assert payload["dataset_id"] == "custom_ds"
    assert payload["learned_templates"] == []
    assert payload["expression_rules"] == []


def test_auto_update_blacklist_appends_low_quality_template_once(tmp_path) -> None:
    """Low-quality templates should be appended to the dataset blacklist without duplicates."""
    results = [
        FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            expression="rank(sales)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.1),
                FailedCheck(name="LOW_FITNESS", value=0.2),
            ],
        ),
        FieldTestResult(
            field_id="assets",
            field_type="MATRIX",
            field_name="assets",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            expression="rank(assets)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.2),
                FailedCheck(name="LOW_FITNESS", value=0.3),
            ],
        ),
        FieldTestResult(
            field_id="income",
            field_type="MATRIX",
            field_name="income",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            expression="rank(income)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.15),
                FailedCheck(name="LOW_FITNESS", value=0.25),
            ],
        ),
    ]

    auto_update_blacklist(results, "custom_ds", datasets_root=str(tmp_path / "datasets"))
    auto_update_blacklist(results, "custom_ds", datasets_root=str(tmp_path / "datasets"))

    payload = json.loads(
        (tmp_path / "datasets" / "custom_ds" / "blacklist.json").read_text(encoding="utf-8")
    )
    entries = payload["learned_templates"]
    assert [entry["name"] for entry in entries] == ["weak_template"]
    assert entries[0]["template_family"] == "group_vol_scaled_delta"
    assert entries[0]["fields_tested"] == ["sales", "assets", "income"]


def test_auto_update_blacklist_is_visible_to_same_process(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert not _is_blacklisted_template("weak_template", "rank(close)", dataset_id="custom_ds")

    results = [
        FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
            expression="rank(sales)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.1),
                FailedCheck(name="LOW_FITNESS", value=0.2),
            ],
        ),
        FieldTestResult(
            field_id="assets",
            field_type="MATRIX",
            field_name="assets",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
            expression="rank(assets)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.2),
                FailedCheck(name="LOW_FITNESS", value=0.3),
            ],
        ),
        FieldTestResult(
            field_id="income",
            field_type="MATRIX",
            field_name="income",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
            expression="rank(income)",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.15),
                FailedCheck(name="LOW_FITNESS", value=0.25),
            ],
        ),
    ]

    auto_update_blacklist(results, "custom_ds", datasets_root=str(tmp_path / "datasets"))

    assert _is_blacklisted_template(
        "weak_template",
        "group_rank(ts_zscore(close, 60), subindustry)",
        template_metadata={
            "stage": "group_second_order",
            "family": "group_vol_scaled_delta",
        },
        dataset_id="custom_ds",
        field_type="MATRIX",
    )
    assert not _is_blacklisted_template(
        "weak_template",
        "group_rank(ts_zscore(close, 60), subindustry)",
        template_metadata={
            "stage": "group_second_order",
            "family": "group_vol_scaled_delta",
        },
        dataset_id="custom_ds",
        field_type="VECTOR",
    )


def test_auto_update_blacklist_defers_promoted_templates_to_registry(tmp_path) -> None:
    """Promoted/refine templates with weak but non-terminal failures should stay in registry flow."""
    results = [
        FieldTestResult(
            field_id=f"field_{idx}",
            field_type="MATRIX",
            field_name=f"field_{idx}",
            template_name="borderline_template",
            template_family="mean_spread",
            template_stage="first_order",
            template_role="promoted_core",
            template_activation_scope="broad",
            expression=f"rank(field_{idx})",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.05),
                FailedCheck(name="LOW_FITNESS", value=0.08),
            ],
        )
        for idx in range(3)
    ]

    auto_update_blacklist(results, "custom_ds", datasets_root=str(tmp_path / "datasets"))

    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    assert not blacklist_file.exists()


def test_blacklist_prefers_name_and_stage_over_name_only(monkeypatch, tmp_path) -> None:
    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "learned_templates": [
                    {
                        "name": "weak_template",
                        "template_stage": "group_second_order",
                        "template_family": "group_zscore",
                    }
                ],
                "expression_rules": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert _is_blacklisted_template(
        "weak_template",
        "group_rank(ts_zscore(close, 60), subindustry)",
        template_metadata={"stage": "group_second_order", "family": "group_zscore"},
        dataset_id="custom_ds",
    )
    assert not _is_blacklisted_template(
        "weak_template",
        "rank(ts_zscore(close, 60))",
        template_metadata={"stage": "first_order", "family": "zscore_time"},
        dataset_id="custom_ds",
    )


def test_legacy_blacklist_name_only_only_applies_without_runtime_metadata(
    monkeypatch, tmp_path
) -> None:
    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "learned_templates": [{"name": "legacy_template"}],
                "expression_rules": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert _is_blacklisted_template("legacy_template", dataset_id="custom_ds")
    assert not _is_blacklisted_template(
        "legacy_template",
        "rank(close)",
        template_metadata={"stage": "first_order", "family": "legacy_level"},
        dataset_id="custom_ds",
    )


def test_blacklist_pattern_rules_support_exact_and_regex(monkeypatch, tmp_path) -> None:
    blacklist_file = tmp_path / "datasets" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "learned_templates": [],
                "expression_rules": [
                    {"type": "exact", "pattern": "rank(close)"},
                    {"type": "regex", "pattern": r"ts_delta\(.*?, 5\)"},
                    {
                        "target": "template_name",
                        "type": "contains",
                        "pattern": "blocked_name",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    invalidate_blacklist_cache()

    assert _is_blacklisted_template("t1", "rank(close)", dataset_id="custom_ds")
    assert _is_blacklisted_template("t2", "rank(ts_delta(close, 5))", dataset_id="custom_ds")
    assert _is_blacklisted_template("blocked_name_template", "rank(open)", dataset_id="custom_ds")
    assert not _is_blacklisted_template("t3", "rank(close) + 1", dataset_id="custom_ds")
