"""
表达式构建模块单元测试（pytest 风格）

测试 alpha.generators.expression_builder 和 templates 子模块中的
表达式分类和构建函数。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from alpha.generators.expression_builder import build_expression_candidates
from alpha.generators.ratio_templates import build_high_conviction_ratio_templates
from alpha.generators.templates import load_template_library
from alpha.generators.templates.classification import (
    classify_expression_family,
    is_legacy_family,
)
from alpha.generators.templates.wrappers import (
    build_bucket_group_templates,
    build_trade_when_templates,
)
from alpha.models.domain import TemplateLibraryItem
from alpha.models.runtime import TemplateBuildContext, TemplateBuildOptions
from alpha.policy.expression import get_dataset_expression_policy

_DEFAULT_SIM_SETTINGS = {
    "region": "USA",
    "universe": "TOP3000",
    "instrument_type": "EQUITY",
    "delay": 1,
    "decay": 4,
    "neutralization": "SUBINDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unit_handling": "VERIFY",
    "nan_handling": "OFF",
    "language": "FASTEXPR",
}


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

    def test_rank_spread(self) -> None:
        family = classify_expression_family("test", "ts_rank(sales, 5) - ts_rank(sales, 20)")
        assert family == "rank_spread"

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


def test_build_expression_candidates_preserve_generated_metadata() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "cash_st", "type": "MATRIX"}
    template_library = {"default": []}

    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS, legacy_similarity_penalty=0),
        all_fields=[field],
        template_library=template_library,
    )
    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=0,
        max_templates_per_family=0,
        expression_policy=policy,
    )

    candidate = next(item for item in candidates if item.name == "raw_field")
    assert candidate.metadata["family"] == "legacy_level"
    assert candidate.metadata["stage"] == "first_order"


def test_preset_mode_uses_template_library_as_closed_candidate_set() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "cashflow_op", "type": "MATRIX"}
    all_fields = [field, {"id": "assets", "type": "MATRIX"}]
    template_library = {
        "default": [
            TemplateLibraryItem(
                name="manual_cashflow_rank",
                expression="rank({field_preprocessed} / cap)",
                priority=1000,
            )
        ]
    }

    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(
            **_DEFAULT_SIM_SETTINGS,
            dataset_id="fundamental6",
            legacy_similarity_penalty=0,
            preset_mode=True,
        ),
        all_fields=all_fields,
        template_library=template_library,
    )
    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=0,
        max_templates_per_family=0,
        expression_policy=policy,
    )

    assert [item.name for item in candidates] == ["manual_cashflow_rank"]
    assert "raw_field" not in {item.name for item in candidates}


def test_candidate_generation_records_blacklist_reason(monkeypatch) -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "cashflow_op", "type": "MATRIX"}
    filter_counts: dict[str, int] = {}
    template_library = {
        "default": [
            TemplateLibraryItem(
                name="blocked_seed",
                expression="rank({field_preprocessed})",
                priority=1000,
            ),
            TemplateLibraryItem(
                name="allowed_seed",
                expression="ts_rank({field_preprocessed}, 120)",
                priority=900,
            ),
        ]
    }
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(
            **_DEFAULT_SIM_SETTINGS,
            dataset_id="fundamental6",
            legacy_similarity_penalty=0,
            preset_mode=True,
        ),
        all_fields=[field],
        template_library=template_library,
        candidate_filter_counts=filter_counts,
    )
    monkeypatch.setattr(
        "alpha.generators.templates.library_candidates.runtime_blacklist_match_reason",
        lambda name, *_args, **_kwargs: "name+stage" if name == "blocked_seed" else None,
    )

    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=0,
        max_templates_per_family=0,
        expression_policy=policy,
    )

    assert [item.name for item in candidates] == ["allowed_seed"]
    assert filter_counts == {"template_filtered_blacklist_name_stage": 1}


def test_build_expression_candidates_skip_unsupported_grouping_fields() -> None:
    policy = replace(
        get_dataset_expression_policy("fundamental6"),
        closed_default_template_library=True,
        supported_grouping_fields={"industry"},
    )
    field = {"id": "cash_st", "type": "MATRIX"}
    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS, legacy_similarity_penalty=0),
        all_fields=[field],
        template_library={
            "default": [
                TemplateLibraryItem(
                    name="requires_subindustry",
                    expression="group_rank({field}, subindustry)",
                    priority=100,
                )
            ]
        },
        template_library_file="datasets/fundamental6/template.json",
    )

    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=0,
        max_templates_per_family=0,
        expression_policy=policy,
    )

    assert candidates == []


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


def test_high_conviction_ratio_templates_are_group_second_order() -> None:
    templates = build_high_conviction_ratio_templates(
        "cashflow_op/assets",
        "cashflow_op_over_assets",
    )

    assert len(templates) == 4
    assert {item.metadata["family"] for item in templates} == {"high_conviction_ratio"}
    assert all(item.metadata["requires_partner_field"] is True for item in templates)
    assert all(item.metadata["stage"] == "group_second_order" for item in templates)


def test_fundamental6_default_policy_does_not_auto_expand_financial_ratio_templates() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "cashflow_op", "type": "MATRIX"}
    all_fields = [
        field,
        {"id": "assets", "type": "MATRIX"},
        {"id": "enterprise_value", "type": "MATRIX"},
    ]

    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS, legacy_similarity_penalty=0),
        all_fields=all_fields,
        template_library_file="datasets/fundamental6/template.json",
        template_library={"default": []},
    )
    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=0,
        max_templates_per_family=0,
        expression_policy=policy,
    )

    assert candidates == []


def test_fundamental6_default_template_library_is_closed_for_vector_fields() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "fnd6_cptnewqeventv110_apq", "type": "VECTOR"}
    template_file = (
        Path(__file__).resolve().parents[2] / "datasets" / "fundamental6" / "template.json"
    )
    template_library = load_template_library(str(template_file), default_backfill_window=504)

    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS, legacy_similarity_penalty=0),
        all_fields=[field],
        template_library=template_library,
    )
    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=0,
        max_templates_per_family=0,
        expression_policy=policy,
    )

    assert candidates
    names = {item.name for item in candidates}
    families = {item.metadata["family"] for item in candidates}

    assert "event_trade_when_recent_change_zscore_60" in names
    assert "vec_avg_ts_rank_60" in names
    assert names <= {
        "seed_delta_over_std_63_126",
        "seed_industry_zscore_120",
        "seed_cap_bucket_ts_rank_120",
        "seed_change_event_delta_over_std_20_120",
        "event_trade_when_recent_change_zscore_60",
        "vec_avg_ts_rank_60",
    }
    assert families <= {
        "delta_over_std",
        "grouped_zscore",
        "bucket_ts_rank",
        "event_delta_over_std",
        "event_trade_when",
        "ts_rank",
    }
    assert all("vec_avg(vec_avg(" not in item.expression for item in candidates)


def test_fundamental6_refine_vector_templates_do_not_double_wrap_vec_avg(
    tmp_path: Path,
) -> None:
    policy = get_dataset_expression_policy("fundamental6")
    field = {"id": "fnd6_cptnewqeventv110_apq", "type": "VECTOR"}
    template_file = (
        tmp_path
        / "datasets"
        / "fundamental6"
        / "presets"
        / "vector_refine_fixture"
        / "template.json"
    )
    template_file.parent.mkdir(parents=True)
    template_file.write_text(
        """{
  "default": [],
  "VECTOR": [
    {
      "name": "vec_avg_decay_120",
      "expression": "rank(ts_decay_linear(ts_backfill({field}, {backfill_window}), 120))",
      "priority": 1000,
      "family": "decay_level",
      "layer": "vector",
      "role": "refine_neighbor",
      "activation_scope": "refine"
    }
  ],
  "GROUP": [],
  "SET": []
}
""",
        encoding="utf-8",
    )
    template_library = load_template_library(str(template_file), default_backfill_window=504)

    build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions(
            **_DEFAULT_SIM_SETTINGS, dataset_id="fundamental6", legacy_similarity_penalty=0
        ),
        all_fields=[field],
        template_library_file=str(template_file),
        template_library=template_library,
    )
    candidates = build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=0,
        max_templates_per_family=0,
        expression_policy=policy,
    )

    by_name = {item.name: item.expression for item in candidates}
    assert "vec_avg_decay_120" in by_name
    assert by_name["vec_avg_decay_120"] == (
        "rank(ts_decay_linear(ts_backfill(vec_avg(fnd6_cptnewqeventv110_apq), 504), 120))"
    )
    assert all("vec_avg(vec_avg(" not in item.expression for item in candidates)
