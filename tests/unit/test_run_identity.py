"""Resolved research-run fingerprint tests."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from alpha.app.run_identity import (
    build_research_input_fingerprints,
    build_research_run_fingerprint,
    validate_existing_run_identity,
)
from alpha.config.models import DatasetExpressionPolicy
from alpha.models.domain import TemplateField
from alpha.models.io_types import RunFilters


def _fingerprint(
    *,
    run_config=None,
    filters=None,
    policy=None,
    blacklist=None,
) -> str:
    return build_research_run_fingerprint(
        run_config=run_config
        or {
            "dataset": {"dataset_id": "fundamental6", "region": "USA"},
            "settings": {"decay": 4},
            "limits": {"limit": 10},
            "filters": {"top_fields_by_feedback": 5},
            "runtime": {"strategy_profile": "balanced"},
            "paths": {"output": "/machine-a/results.json"},
        },
        template_library={"MATRIX": []},
        filters=filters or RunFilters(include_fields={"f1", "f2"}),
        expression_policy=policy or DatasetExpressionPolicy(dataset_id="fundamental6"),
        blacklist_payload=blacklist
        or {
            "dataset_id": "fundamental6",
            "learned_templates": [],
            "expression_rules": [],
        },
    )


def test_run_fingerprint_ignores_paths_and_presentation_flags() -> None:
    first_config = {
        "dataset": {"dataset_id": "fundamental6", "region": "USA"},
        "settings": {"decay": 4},
        "limits": {"limit": 10},
        "filters": {"top_fields_by_feedback": 5},
        "runtime": {"strategy_profile": "balanced", "verbose": False},
        "paths": {"output": "/machine-a/results.json"},
    }
    second_config = deepcopy(first_config)
    second_config["paths"] = {"output": r"C:\\runs\\results.json"}
    second_config["runtime"]["verbose"] = True

    assert _fingerprint(run_config=first_config) == _fingerprint(run_config=second_config)


def test_run_fingerprint_changes_with_resolved_research_inputs() -> None:
    baseline = _fingerprint()

    assert baseline != _fingerprint(filters=RunFilters(include_fields={"f1"}))
    assert baseline != _fingerprint(
        policy=DatasetExpressionPolicy(dataset_id="fundamental6", partner_limit=9)
    )
    assert baseline != _fingerprint(
        blacklist={
            "dataset_id": "fundamental6",
            "learned_templates": ["weak_template"],
            "expression_rules": [],
        }
    )


def test_research_input_fingerprints_track_normalized_content() -> None:
    baseline = build_research_input_fingerprints(
        filters=RunFilters(include_fields={"f2", "f1"}),
        expression_policy=DatasetExpressionPolicy(dataset_id="fundamental6"),
        blacklist_payload={
            "dataset_id": "fundamental6",
            "_updated": "2026-08-01",
            "learned_templates": [],
            "expression_rules": [],
        },
    )
    reordered_metadata = build_research_input_fingerprints(
        filters=RunFilters(include_fields={"f1", "f2"}),
        expression_policy=DatasetExpressionPolicy(dataset_id="fundamental6"),
        blacklist_payload={
            "dataset_id": "fundamental6",
            "_updated": "2026-08-10",
            "learned_templates": [],
            "expression_rules": [],
        },
    )
    changed = build_research_input_fingerprints(
        filters=RunFilters(include_fields={"f1"}),
        expression_policy=DatasetExpressionPolicy(dataset_id="fundamental6", partner_limit=9),
        blacklist_payload={
            "dataset_id": "fundamental6",
            "learned_templates": ["weak_template"],
            "expression_rules": [],
        },
    )

    assert baseline == reordered_metadata
    assert changed["include_fields"] != baseline["include_fields"]
    assert changed["expression_policy"] != baseline["expression_policy"]
    assert changed["blacklist"] != baseline["blacklist"]


def test_research_input_fingerprints_track_field_metadata() -> None:
    first = [TemplateField("f1", "field_one", "MATRIX", {"coverage": 1.0})]
    second = [TemplateField("f1", "field_one", "MATRIX", {"coverage": 0.9})]

    first_fingerprint = build_research_input_fingerprints(
        filters=RunFilters(),
        expression_policy=DatasetExpressionPolicy(),
        blacklist_payload={},
        fields=first,
    )
    second_fingerprint = build_research_input_fingerprints(
        filters=RunFilters(),
        expression_policy=DatasetExpressionPolicy(),
        blacklist_payload={},
        fields=second,
    )

    assert first_fingerprint["fields"] != second_fingerprint["fields"]


def test_existing_run_identity_rejects_configuration_drift(tmp_path) -> None:
    output_path = tmp_path / "summary.json"
    output_path.write_text(
        json.dumps({"tested": 1, "run_fingerprint": "old-run"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="new --run-name"):
        validate_existing_run_identity(
            str(output_path),
            run_fingerprint="current-run",
            run_config={},
            settings_fingerprint="settings",
            template_library_fingerprint="templates",
        )


def test_existing_run_identity_migrates_matching_legacy_summary(tmp_path, caplog) -> None:
    output_path = tmp_path / "summary.json"
    run_config = {
        "dataset": {"dataset_id": "fundamental6"},
        "settings": {"decay": 4},
        "runtime": {"strategy_profile": "balanced"},
    }
    output_path.write_text(
        json.dumps(
            {
                "tested": 1,
                "run_config": run_config,
                "settings_fingerprint": "settings",
                "template_library_fingerprint": "templates",
            }
        ),
        encoding="utf-8",
    )

    validate_existing_run_identity(
        str(output_path),
        run_fingerprint="current-run",
        run_config=run_config,
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )

    assert "migrating legacy summary" in caplog.text
