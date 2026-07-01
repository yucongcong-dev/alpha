from __future__ import annotations

from alpha.config import FieldTransformSpec, FieldTransformStage, get_dataset_expression_policy
from alpha.generators.expressions import build_expression_candidates
from alpha.generators.field_transforms import apply_transform_pipeline, build_field_view, iter_transform_stages
from alpha.generators.templates import load_template_library


def test_apply_transform_pipeline_backfill_then_winsorize() -> None:
    spec = FieldTransformSpec(backfill_window=120, winsorize_std=4.0)
    assert (
        apply_transform_pipeline("cash_st", spec)
        == "winsorize(ts_backfill(cash_st, 120), std=4)"
    )


def test_iter_transform_stages_prefers_explicit_stage_list() -> None:
    spec = FieldTransformSpec(
        stages=(
            FieldTransformStage(kind="backfill", window=63),
            FieldTransformStage(kind="winsorize", std=4.0),
        ),
        backfill_window=120,
    )

    stages = iter_transform_stages(spec)

    assert [stage.kind for stage in stages] == ["backfill", "winsorize"]
    assert stages[0].window == 63


def test_build_field_view_uses_vec_avg_for_vector_fields() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field_view = build_field_view({"id": "sentiment_vec", "type": "VECTOR"}, policy)

    assert field_view.raw_expression == "vec_avg(sentiment_vec)"
    assert (
        field_view.preprocessed_expression
        == "winsorize(ts_backfill(vec_avg(sentiment_vec), 120), std=4)"
    )


def test_build_expression_candidates_uses_preprocessed_raw_field_view() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    template_library = {"default": []}
    candidates = build_expression_candidates(
        field={"id": "cash_st", "type": "MATRIX"},
        template_library=template_library,
        max_templates_per_field=200,
        max_templates_per_family=200,
        legacy_similarity_penalty=0,
        all_fields=[{"id": "assets_curr", "type": "MATRIX"}],
        dataset_id="fundamental6",
        expression_policy=policy,
    )

    expressions = {expression for _, expression, _ in candidates}
    assert "winsorize(ts_backfill(cash_st, 120), std=4)" in expressions
    assert (
        "group_rank(winsorize(ts_backfill(cash_st, 120), std=4), densify(bucket(rank(cap), range='0.1, 1, 0.1')))"
        in expressions
    )


def test_fundamental6_account_templates_use_preprocessed_field_view() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    template_library = load_template_library("data/templates/fundamental6/library.json")
    candidates = build_expression_candidates(
        field={"id": "cash_st", "type": "MATRIX"},
        template_library=template_library,
        max_templates_per_field=50,
        max_templates_per_family=50,
        legacy_similarity_penalty=0,
        all_fields=[{"id": "assets_curr", "type": "MATRIX"}],
        dataset_id="fundamental6",
        expression_policy=policy,
    )

    by_name = {name: expression for name, expression, _ in candidates}
    assert by_name["account_rank_backfill_504"] == "rank(winsorize(ts_backfill(cash_st, 120), std=4))"
    assert by_name["account_group_backfill_504_subindustry"] == (
        "group_rank(winsorize(ts_backfill(cash_st, 120), std=4), subindustry)"
    )
    assert by_name["account_bucket_cap_zscore_63"] == (
        "group_rank(ts_zscore(winsorize(ts_backfill(cash_st, 120), std=4), 63), bucket(rank(cap), range='0.1, 1, 0.1'))"
    )


def test_model16_templates_include_bucket_groups() -> None:
    policy = get_dataset_expression_policy("model16")
    template_library = load_template_library("data/templates/model16/library.json")
    candidates = build_expression_candidates(
        field={"id": "value_score", "type": "MATRIX"},
        template_library=template_library,
        max_templates_per_field=50,
        max_templates_per_family=50,
        legacy_similarity_penalty=0,
        all_fields=[{"id": "quality_score", "type": "MATRIX"}],
        dataset_id="model16",
        expression_policy=policy,
    )

    by_name = {name: expression for name, expression, _ in candidates}
    assert by_name["model16_bucket_cap_zscore_126"] == (
        "group_rank(ts_zscore(winsorize(ts_backfill(value_score, 252), std=4), 126), bucket(rank(cap), range='0.1, 1, 0.1'))"
    )


def test_model51_templates_include_bucket_groups() -> None:
    policy = get_dataset_expression_policy("model51")
    template_library = load_template_library("data/templates/model51/library.json")
    candidates = build_expression_candidates(
        field={"id": "risk_metric", "type": "MATRIX"},
        template_library=template_library,
        max_templates_per_field=50,
        max_templates_per_family=50,
        legacy_similarity_penalty=0,
        all_fields=[{"id": "market_beta", "type": "MATRIX"}],
        dataset_id="model51",
        expression_policy=policy,
    )

    by_name = {name: expression for name, expression, _ in candidates}
    assert by_name["model51_bucket_cap_zscore_126"] == (
        "group_rank(ts_zscore(winsorize(ts_backfill(risk_metric, 504), std=4), 126), bucket(rank(cap), range='0.1, 1, 0.1'))"
    )
