from __future__ import annotations

from alpha.config import FieldTransformSpec, get_dataset_expression_policy
from alpha.generators.expressions import build_expression_candidates
from alpha.generators.field_transforms import apply_transform_pipeline, build_field_view


def test_apply_transform_pipeline_backfill_then_winsorize() -> None:
    spec = FieldTransformSpec(backfill_window=120, winsorize_std=4.0)
    assert (
        apply_transform_pipeline("cash_st", spec)
        == "winsorize(ts_backfill(cash_st, 120), std=4)"
    )


def test_build_field_view_uses_vec_avg_for_vector_fields() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field_view = build_field_view({"id": "sentiment_vec", "type": "VECTOR"}, policy)

    assert field_view.raw_expression == "vec_avg(sentiment_vec)"
    assert field_view.preprocessed_expression == "ts_backfill(vec_avg(sentiment_vec), 240)"


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
    assert "ts_backfill(cash_st, 240)" in expressions
    assert "group_rank(ts_backfill(cash_st, 240), subindustry)" in expressions
