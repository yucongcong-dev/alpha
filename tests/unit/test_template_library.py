"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha.exceptions import BrainAPIError
from alpha.generators.expression_builder import build_expression_candidates
from alpha.generators.templates.library_loader import load_template_library
from alpha.generators.templates.library_store import ensure_dataset_template_library
from alpha.models.domain_parsers import parse_template_field
from alpha.models.runtime_options import TemplateBuildOptions
from alpha.runtime.contexts import (
    TemplateBuildContext,
    TemplateFeedbackContext,
    TemplateSourceContext,
)


def test_ensure_dataset_template_library_raises_when_missing(tmp_path) -> None:
    """Missing dataset-specific template files should raise an error, not auto-generate."""
    target = tmp_path / "nonexistent_library.json"

    with pytest.raises(BrainAPIError, match="模板库文件不存在"):
        ensure_dataset_template_library(str(target), "custom_ds")


def test_ensure_dataset_template_library_raises_when_path_empty() -> None:
    """Empty path should raise an error requiring explicit template library."""
    with pytest.raises(BrainAPIError, match="缺少模板库文件路径"):
        ensure_dataset_template_library("", "custom_ds")


def test_ensure_dataset_template_library_preserves_existing(tmp_path) -> None:
    """Existing dataset template files should not be overwritten."""
    target = tmp_path / "library.json"
    target.write_text(
        json.dumps({"default": [{"name": "custom", "expression": "zscore({field})"}]}),
        encoding="utf-8",
    )

    ensure_dataset_template_library(str(target), "custom_ds")

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["default"][0]["name"] == "custom"


def test_load_template_library_preserves_optional_metadata(tmp_path) -> None:
    template_file = tmp_path / "library.json"
    template_file.write_text(
        json.dumps(
            {
                "default": [
                    {
                        "name": "custom",
                        "expression": "rank({field})",
                        "priority": 100,
                        "family": "custom_family",
                        "layer": "ratio",
                        "stage": "first_order",
                        "role": "default_seed",
                        "activation_scope": "refine",
                        "requires_partner_field": False,
                        "field_tags": ["dense_lane"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    library = load_template_library(str(template_file), default_backfill_window=504)

    item = library["default"][0]
    assert item.family == "custom_family"
    assert item.metadata.get("layer") == "ratio"
    assert item.stage == "first_order"
    assert item.metadata.get("role") == "default_seed"
    assert item.metadata.get("activation_scope") == "refine"
    assert item.metadata.get("requires_partner_field") is False
    assert item.metadata.get("field_tags") == ["dense_lane"]


def test_build_expression_candidates_respects_template_field_tags(tmp_path) -> None:
    template_file = tmp_path / "library.json"
    template_file.write_text(
        json.dumps(
            {
                "_dataset_id": "model16",
                "default": [
                    {
                        "name": "dense_only",
                        "expression": "rank(ts_rank({field_preprocessed}, 120))",
                        "priority": 100,
                        "field_tags": ["model16_dense_derivative"],
                    },
                    {
                        "name": "sparse_only",
                        "expression": "rank(ts_rank({field_groupfill}, 120))",
                        "priority": 90,
                        "field_tags": ["model16_sparse_fscore"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    build_ctx = TemplateBuildContext(
        source=TemplateSourceContext(
            options=TemplateBuildOptions(
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
                dataset_id="model16",
            ),
            template_library=load_template_library(str(template_file), default_backfill_window=504),
        ),
        feedback=TemplateFeedbackContext(),
    )
    field = parse_template_field(
        {
            "id": "analyst_revision_rank_derivative",
            "type": "MATRIX",
            "runtime_field_tags": ["model16_dense_derivative", "high_coverage"],
        }
    )

    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=200,
        max_templates_per_family=200,
    )

    names = [item.name for item in candidates]
    assert "dense_only" in names
    assert "sparse_only" not in names


def test_build_expression_candidates_skip_refine_only_templates_in_default_library(
    tmp_path,
) -> None:
    template_file = tmp_path / "library.json"
    template_file.write_text(
        json.dumps(
            {
                "default": [
                    {
                        "name": "broad_template",
                        "expression": "rank({field})",
                        "priority": 100,
                        "activation_scope": "broad",
                    },
                    {
                        "name": "refine_template",
                        "expression": "ts_rank({field}, 20)",
                        "priority": 90,
                        "activation_scope": "refine",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    build_ctx = TemplateBuildContext(
        source=TemplateSourceContext(
            options=TemplateBuildOptions(
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
                dataset_id="fundamental6",
            ),
            template_library_file=str(template_file),
            template_library=load_template_library(str(template_file), default_backfill_window=504),
        ),
        feedback=TemplateFeedbackContext(),
    )
    field = parse_template_field({"id": "cash_st", "type": "VECTOR"})

    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=20,
        max_templates_per_family=20,
    )

    names = {item.name for item in candidates}
    assert "broad_template" in names
    assert "refine_template" not in names


def test_build_expression_candidates_include_refine_only_templates_in_explicit_preset(
    tmp_path,
) -> None:
    preset_dir = tmp_path / "datasets" / "fundamental6" / "presets" / "default_neighbors"
    preset_dir.mkdir(parents=True)
    template_file = preset_dir / "template.json"
    template_file.write_text(
        json.dumps(
            {
                "default": [
                    {
                        "name": "broad_template",
                        "expression": "rank({field})",
                        "priority": 100,
                        "activation_scope": "broad",
                    },
                    {
                        "name": "refine_template",
                        "expression": "ts_rank({field}, 20)",
                        "priority": 90,
                        "activation_scope": "refine",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    build_ctx = TemplateBuildContext(
        source=TemplateSourceContext(
            options=TemplateBuildOptions(
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
                dataset_id="fundamental6",
            ),
            template_library_file=str(template_file),
            template_library=load_template_library(str(template_file), default_backfill_window=504),
        ),
        feedback=TemplateFeedbackContext(),
    )
    field = parse_template_field({"id": "cash_st", "type": "VECTOR"})

    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=20,
        max_templates_per_family=20,
    )

    names = {item.name for item in candidates}
    assert "broad_template" in names
    assert "refine_template" in names


def test_load_template_library_infers_stage_from_layer(tmp_path) -> None:
    template_file = tmp_path / "library.json"
    template_file.write_text(
        json.dumps(
            {
                "default": [
                    {
                        "name": "group_custom",
                        "expression": "group_rank({field}, subindustry)",
                        "priority": 100,
                        "layer": "group",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    library = load_template_library(str(template_file), default_backfill_window=504)

    assert library["default"][0].stage == "group_second_order"


def test_missing_template_priorities_are_resolved_without_mutating_source(tmp_path) -> None:
    """Missing priorities should resolve in memory while source JSON stays unchanged."""
    target = tmp_path / "library.json"
    target.write_text(
        json.dumps(
            {
                "default": [
                    {"name": "first", "expression": "rank({field})"},
                    {"name": "manual", "expression": "zscore({field})", "priority": 999},
                    {"name": "third", "expression": "scale({field})"},
                ]
            }
        ),
        encoding="utf-8",
    )

    original = target.read_text(encoding="utf-8")
    ensure_dataset_template_library(str(target), "custom_ds")
    library = load_template_library(str(target), default_backfill_window=504)

    assert target.read_text(encoding="utf-8") == original
    assert [item.priority for item in library["default"]] == [1000, 999, 998]


def test_load_template_library_raises_on_missing_file(tmp_path) -> None:
    """Loading a non-existent template file should raise an error."""
    missing = tmp_path / "nonexistent.json"

    with pytest.raises(BrainAPIError, match="模板库文件不存在"):
        load_template_library(str(missing), default_backfill_window=504)


def test_load_template_library_raises_on_empty_path() -> None:
    """Loading with an empty path should raise an error."""
    with pytest.raises(BrainAPIError, match="模板库文件路径为空"):
        load_template_library("", default_backfill_window=504)


def test_fundamental6_template_library_has_family_and_layer_metadata() -> None:
    """Common dataset template library entries should carry explicit family/layer metadata."""
    template_file = (
        Path(__file__).resolve().parents[2] / "datasets" / "fundamental6" / "template.json"
    )
    payload = json.loads(template_file.read_text(encoding="utf-8"))

    missing = []
    for section, items in payload.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or "name" not in item or "expression" not in item:
                continue
            if "family" not in item or "layer" not in item:
                missing.append((section, item["name"]))

    assert missing == []


def test_fundamental6_default_seeds_span_distinct_families() -> None:
    template_file = (
        Path(__file__).resolve().parents[2] / "datasets" / "fundamental6" / "template.json"
    )
    payload = json.loads(template_file.read_text(encoding="utf-8"))
    default_seeds = [
        item
        for item in payload["default"]
        if isinstance(item, dict) and item.get("role") == "default_seed"
    ]

    assert {item["name"] for item in default_seeds} == {
        "seed_delta_over_std_63_126",
        "seed_industry_zscore_120",
        "seed_cap_bucket_ts_rank_120",
        "seed_change_event_delta_over_std_20_120",
    }
    assert len({item["family"] for item in default_seeds}) == len(default_seeds)
    assert all(item.get("activation_scope") == "broad" for item in default_seeds)


def test_fundamental6_template_library_removes_known_weak_short_window_templates() -> None:
    template_file = (
        Path(__file__).resolve().parents[2] / "datasets" / "fundamental6" / "template.json"
    )
    payload = json.loads(template_file.read_text(encoding="utf-8"))

    names = {
        item["name"]
        for section, items in payload.items()
        if isinstance(items, list)
        for item in items
        if isinstance(item, dict) and "name" in item
    }

    removed = {
        "vol_scaled_delta_5_20",
        "vol_scaled_delta_5_20_MARKET",
        "delta_5",
        "rank_delta_5",
        "group_delta_5",
        "group_delta_5_MARKET",
        "vec_avg_vol_scaled_delta_20_60",
        "vec_avg_delta_5",
        "vec_avg_delta_20",
        "vec_avg_delta_21",
        "vec_avg_delta_22",
        "vec_avg_delta_66",
        "vec_avg_rank_delta_5",
        "mean_diff_5_20",
        "vec_avg_ts_corr_self_60",
        "vec_avg_zscore",
        "vec_avg_backfill",
        "vec_avg_rank",
        "vec_avg_ts_mean_20",
        "vec_avg_ts_mean_22",
        "vec_avg_ts_mean_60",
        "vec_avg_ts_mean_63",
        "vec_avg_ts_mean_66",
        "vec_avg_ts_mean_252",
        "vec_avg_scale",
    }

    assert names.isdisjoint(removed)
