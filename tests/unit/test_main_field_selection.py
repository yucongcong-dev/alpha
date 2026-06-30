"""Field selection and ranking tests."""

from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace

from alpha.config import get_dataset_expression_policy
from alpha.main import prepare_fields_for_execution


def test_prepare_fields_for_execution_filters_before_limit() -> None:
    """include/exclude filters must run before limit truncation."""
    fields = [
        {
            "id": "assets",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 10,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
        {
            "id": "cash_st",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 10,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
    ]
    args = Namespace(limit=1, offset=0, top_fields_by_feedback=0)
    filters = SimpleNamespace(include_fields={"cash_st"}, exclude_fields=set())
    historical_state = SimpleNamespace(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        fields,
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=historical_state,
        args=args,
    )

    assert [row["id"] for row in selected] == ["cash_st"]
    assert stats["prefiltered_count"] == 1
    assert stats["filtered_field_count"] == 1
    assert stats["ranked_field_count"] == 1


def test_prepare_fields_for_execution_applies_metadata_filters() -> None:
    """Fields below metadata thresholds should be dropped before ranking."""
    fields = [
        {
            "id": "cash_st",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 10,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
        {
            "id": "weak_field",
            "coverage": 0.01,
            "dateCoverage": 0.50,
            "alphaCount": 1,
            "userCount": 0,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
    ]
    args = Namespace(limit=0, offset=0, top_fields_by_feedback=0)
    filters = SimpleNamespace(include_fields=set(), exclude_fields=set())
    historical_state = SimpleNamespace(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        fields,
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=historical_state,
        args=args,
    )

    assert [row["id"] for row in selected] == ["cash_st"]
    assert stats["low_coverage_count"] == 1
    assert stats["filtered_field_count"] == 1
