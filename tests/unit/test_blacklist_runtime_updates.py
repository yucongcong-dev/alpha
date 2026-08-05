"""Incremental runtime blacklist update tests."""

from __future__ import annotations

import json

from alpha.models.domain import FailedCheck, FieldTestResult
from alpha.policy import blacklist_store
from alpha.policy.blacklist_runtime_stats import build_blacklist_runtime_stats
from alpha.policy.blacklist_runtime_updates import auto_update_blacklist_incremental


def test_auto_update_blacklist_incremental_blacklists_only_changed_template(tmp_path) -> None:
    """Incremental blacklist updates should blacklist qualifying templates without full rescans."""
    runtime_stats = build_blacklist_runtime_stats([])
    blacklisted_keys = blacklist_store.load_blacklisted_template_keys(
        "custom_ds", datasets_root=str(tmp_path / "datasets")
    )
    results = [
        FieldTestResult(
            field_id=field_id,
            field_type="MATRIX",
            field_name=field_name,
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
            expression=f"rank({field_name})",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=sharpe),
                FailedCheck(name="LOW_FITNESS", value=fitness),
            ],
        )
        for field_id, field_name, sharpe, fitness in (
            ("f1", "sales", 0.1, 0.2),
            ("f2", "assets", 0.2, 0.3),
            ("f3", "income", 0.15, 0.25),
        )
    ]

    added = [
        auto_update_blacklist_incremental(
            runtime_stats,
            blacklisted_keys,
            result,
            "custom_ds",
            datasets_root=str(tmp_path / "datasets"),
        )
        for result in results
    ]

    payload = json.loads(
        (tmp_path / "datasets" / "custom_ds" / "blacklist.json").read_text(encoding="utf-8")
    )
    assert added == [False, False, True]
    assert [entry["name"] for entry in payload["learned_templates"]] == ["weak_template"]


def test_auto_update_blacklist_incremental_can_write_staging_file(tmp_path) -> None:
    """Incremental staging mode avoids writing the repository blacklist."""
    runtime_stats = build_blacklist_runtime_stats([])
    blacklisted_keys = blacklist_store.load_blacklisted_template_keys(
        "custom_ds", datasets_root=str(tmp_path / "datasets")
    )
    results = [
        FieldTestResult(
            field_id=field_id,
            field_type="MATRIX",
            field_name=field_id,
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
            expression=f"rank({field_id})",
            submittable=False,
            failed_checks=[
                FailedCheck(name="LOW_SHARPE", value=0.1),
                FailedCheck(name="LOW_FITNESS", value=0.2),
            ],
        )
        for field_id in ("sales", "assets", "income")
    ]

    added = [
        auto_update_blacklist_incremental(
            runtime_stats,
            blacklisted_keys,
            result,
            "custom_ds",
            datasets_root=str(tmp_path / "datasets"),
            update_mode="staging",
        )
        for result in results
    ]

    dataset_dir = tmp_path / "datasets" / "custom_ds"
    assert added == [False, False, True]
    assert not (dataset_dir / "blacklist.json").exists()
    payload = json.loads((dataset_dir / "blacklist.staging.json").read_text(encoding="utf-8"))
    assert [entry["name"] for entry in payload["learned_templates"]] == ["weak_template"]
