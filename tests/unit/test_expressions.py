"""
表达式构建模块单元测试（pytest 风格）

测试 alpha.generators.expressions 中的表达式分类和构建函数。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha.config import get_dataset_expression_policy
from alpha.generators.expressions import (
    _load_default_avoid_rules,
    build_bucket_group_templates,
    build_expression_candidates,
    build_feedback_mutations,
    build_high_conviction_ratio_templates,
    build_historical_reuse_templates,
    build_trade_when_templates,
    classify_expression_family,
    is_legacy_family,
)
from alpha.generators.templates import load_template_library


class TestClassifyExpressionFamily:
    """classify_expression_family 函数测试用例"""

    def test_group_rank_delta(self) -> None:
        family = classify_expression_family(
            "test", "group_rank(ts_delta(rank(sales), 5), subindustry)"
        )
        assert family == "group_rank_delta"

    def test_rank_delta(self) -> None:
        family = classify_expression_family("test", "rank(ts_delta(rank(sales), 5))")
        assert family == "rank_delta"

    def test_legacy_level_raw_field(self) -> None:
        family = classify_expression_family("raw_field", "sales")
        assert family == "legacy_level"

    def test_legacy_ratio(self) -> None:
        family = classify_expression_family("ratio_debt_assets", "debt/assets")
        assert family == "legacy_ratio"

    def test_zscore_time(self) -> None:
        family = classify_expression_family("test", "ts_zscore(sales, 60)")
        assert family == "zscore_time"

    def test_vol_scaled_delta(self) -> None:
        family = classify_expression_family("test", "ts_delta(sales, 5) / ts_std_dev(sales, 20)")
        assert family == "vol_scaled_delta"

    def test_mean_spread(self) -> None:
        family = classify_expression_family("test", "ts_mean(sales, 5) - ts_mean(sales, 20)")
        assert family == "mean_spread"

    # ---- 补充边界测试 ----
    def test_unknown_template_falls_back(self) -> None:
        """未知模板名回退到表达式分类。"""
        family = classify_expression_family("completely_unknown_template", "ts_zscore(sales, 60)")
        assert family == "zscore_time"

    def test_empty_expression(self) -> None:
        """空表达式应返回某个默认值（不应崩溃）。"""
        # 空表达式应能处理而不抛异常
        family = classify_expression_family("test", "")
        assert isinstance(family, str)

    def test_non_string_expression(self) -> None:
        """非字符串表达式会抛出 AttributeError（设计如此）。"""
        with pytest.raises(AttributeError):
            classify_expression_family("test", None)  # type: ignore[arg-type]


class TestIsLegacyFamily:
    """is_legacy_family 函数测试用例"""

    def test_raw_field_is_legacy(self) -> None:
        assert is_legacy_family("raw_field", "sales") is True

    def test_rank_raw_field_is_legacy(self) -> None:
        assert is_legacy_family("rank_raw_field", "rank(sales)") is True

    def test_ratio_is_legacy(self) -> None:
        assert is_legacy_family("ratio_debt_assets", "debt/assets") is True

    def test_group_rank_delta_not_legacy(self) -> None:
        assert (
            is_legacy_family("test", "group_rank(ts_delta(rank(sales), 5), subindustry)") is False
        )

    def test_zscore_not_legacy(self) -> None:
        assert is_legacy_family("test", "ts_zscore(sales, 60)") is False

    # ---- 补充边界测试 ----
    def test_unknown_template_not_legacy(self) -> None:
        """未知模板不应被视为 legacy。"""
        assert is_legacy_family("unknown_template", "ts_mean(sales, 20)") is False

    def test_empty_template_not_legacy(self) -> None:
        """空模板名不应被视为 legacy。"""
        assert is_legacy_family("", "sales") is False

    def test_ratio_with_suffix_is_legacy(self) -> None:
        """ratio_ 前缀的变体也应视为 legacy。"""
        assert is_legacy_family("ratio_profit_margin", "profit/cost") is True


def test_build_feedback_mutations_attach_runtime_metadata() -> None:
    mutations = build_feedback_mutations("cash_st", None)

    candidate = next(item for item in mutations if item.name == "iter_group_rank_delta_of_rank_63")
    assert candidate.metadata["family"] == "group_rank_delta"
    assert candidate.metadata["stage"] == "group_second_order"


def test_build_expression_candidates_preserve_generated_metadata() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "cash_st", "type": "MATRIX"}
    template_library = {"default": []}

    candidates = build_expression_candidates(
        field,
        template_library,
        max_templates_per_field=0,
        max_templates_per_family=0,
        legacy_similarity_penalty=0,
        all_fields=[field],
        expression_policy=policy,
    )

    candidate = next(item for item in candidates if item.name == "raw_field")
    assert candidate.metadata["family"] == "legacy_level"
    assert candidate.metadata["stage"] == "first_order"


def test_bucket_group_templates_add_four_controlled_groups() -> None:
    templates = build_bucket_group_templates("rank(cash_st)", name_prefix="bucket")

    assert len(templates) == 4
    assert {item.metadata["family"] for item in templates} == {"bucket_group_rank"}
    assert all("bucket(" in item.expression for item in templates)
    assert all(item.metadata["stage"] == "group_second_order" for item in templates)


def test_trade_when_templates_wrap_expression_with_event_switches() -> None:
    templates = build_trade_when_templates("rank(cash_st)", name_prefix="event")

    assert len(templates) == 4
    assert {item.metadata["family"] for item in templates} == {"event_trade_when"}
    assert all(item.expression.startswith("trade_when(") for item in templates)
    assert all(item.expression.endswith(", -1)") for item in templates)
    assert all(item.metadata["stage"] == "event_conditioned" for item in templates)


def test_historical_reuse_templates_require_good_feedback() -> None:
    weak = build_historical_reuse_templates(
        "cash_st",
        {"best_score": 0.1, "best_expression": "rank(cash_st)"},
        feedback_stage="resimulate",
    )
    strong = build_historical_reuse_templates(
        "cash_st",
        {"best_score": 0.7, "best_expression": "rank(cash_st)"},
        feedback_stage="resimulate",
    )

    assert weak == []
    assert any(item.name.startswith("iter_reuse_best_bucket_group_rank_") for item in strong)
    assert any(item.name.startswith("iter_reuse_best_trade_when_") for item in strong)


def test_high_conviction_ratio_templates_are_group_second_order() -> None:
    templates = build_high_conviction_ratio_templates(
        "cashflow_op/assets",
        "cashflow_op_over_assets",
    )

    assert len(templates) == 4
    assert {item.metadata["family"] for item in templates} == {"high_conviction_ratio"}
    assert all(item.metadata["requires_partner_field"] is True for item in templates)
    assert all(item.metadata["stage"] == "group_second_order" for item in templates)


def test_build_expression_candidates_adds_financial_ratio_templates() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "cashflow_op", "type": "MATRIX"}
    all_fields = [
        field,
        {"id": "assets", "type": "MATRIX"},
        {"id": "enterprise_value", "type": "MATRIX"},
    ]

    candidates = build_expression_candidates(
        field,
        {"default": []},
        max_templates_per_field=0,
        max_templates_per_family=0,
        legacy_similarity_penalty=0,
        all_fields=all_fields,
        expression_policy=policy,
    )

    names = {item.name for item in candidates}
    assert "hc_ratio_group_level_cashflow_op_over_assets" in names
    assert "hc_ratio_group_zscore_252_cashflow_op_over_assets" in names


def test_load_default_avoid_rules_ignores_invalid_json_shape(monkeypatch, tmp_path) -> None:
    """A valid JSON file with the wrong top-level type should not crash rule loading."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "template_blacklist.json").write_text(json.dumps([]), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("alpha.generators.expressions._DEFAULT_AVOID_RULES_CACHE", None)

    assert _load_default_avoid_rules() == []


def test_build_expression_candidates_narrows_event_field_template_pool() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "fnd6_cptnewqeventv110_apq", "type": "VECTOR"}
    template_file = Path(__file__).resolve().parents[2] / "data" / "templates" / "fundamental6" / "library.json"
    template_library = load_template_library(str(template_file))

    candidates = build_expression_candidates(
        field,
        template_library,
        max_templates_per_field=0,
        max_templates_per_family=0,
        legacy_similarity_penalty=0,
        all_fields=[field],
        expression_policy=policy,
    )

    assert candidates
    names = {item.name for item in candidates}
    families = {item.metadata["family"] for item in candidates}

    assert "vec_avg_ts_mean_63" not in names
    assert "vec_avg_zscore" not in names
    assert families <= {"ts_rank", "zscore_time", "decay_level", "event_trade_when"}
    assert all("vec_avg(vec_avg(" not in item.expression for item in candidates)
