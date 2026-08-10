"""Resolved research-run fingerprint tests."""

from __future__ import annotations

from copy import deepcopy

from alpha.app.run_identity import build_research_run_fingerprint
from alpha.config.models import DatasetExpressionPolicy
from alpha.models.domain import TemplateField
from alpha.models.io_types import RunFilters


def _fingerprint(
    *,
    run_config=None,
    filters=None,
    policy=None,
    blacklist=None,
    fields=None,
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
        fields=fields
        or [
            TemplateField("f1", "Field 1", "MATRIX"),
            TemplateField("f2", "Field 2", "MATRIX"),
        ],
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


def test_run_fingerprint_changes_with_resolved_field_order() -> None:
    fields = [
        TemplateField("f1", "Field 1", "MATRIX"),
        TemplateField("f2", "Field 2", "MATRIX"),
    ]

    assert _fingerprint(fields=fields) != _fingerprint(fields=list(reversed(fields)))
