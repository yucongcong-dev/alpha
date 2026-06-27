"""
表达式构建模块单元测试（pytest 风格）

测试 alpha.generators.expressions 中的表达式分类和构建函数。
"""

from __future__ import annotations

import pytest

from alpha.generators.expressions import classify_expression_family, is_legacy_family


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
