# -*- coding: utf-8 -*-
"""
表达式构建模块单元测试

测试 alpha.generators.expressions 中的表达式分类和构建函数。
"""

import unittest

from alpha.generators.expressions import classify_expression_family, is_legacy_family


class TestClassifyExpressionFamily(unittest.TestCase):
    """classify_expression_family 函数测试用例"""

    def test_group_rank_delta(self):
        """测试 group_rank_delta 家族"""
        family = classify_expression_family(
            "test",
            "group_rank(ts_delta(rank(sales), 5), subindustry)"
        )
        self.assertEqual(family, "group_rank_delta")

    def test_rank_delta(self):
        """测试 rank_delta 家族"""
        family = classify_expression_family(
            "test",
            "rank(ts_delta(rank(sales), 5))"
        )
        self.assertEqual(family, "rank_delta")

    def test_legacy_level_raw_field(self):
        """测试 legacy_level 家族 - raw_field"""
        family = classify_expression_family("raw_field", "sales")
        self.assertEqual(family, "legacy_level")

    def test_legacy_ratio(self):
        """测试 legacy_ratio 家族"""
        family = classify_expression_family("ratio_debt_assets", "debt/assets")
        self.assertEqual(family, "legacy_ratio")

    def test_zscore_time(self):
        """测试 zscore_time 家族"""
        family = classify_expression_family(
            "test",
            "ts_zscore(sales, 60)"
        )
        self.assertEqual(family, "zscore_time")

    def test_vol_scaled_delta(self):
        """测试 vol_scaled_delta 家族"""
        family = classify_expression_family(
            "test",
            "ts_delta(sales, 5) / ts_std_dev(sales, 20)"
        )
        self.assertEqual(family, "vol_scaled_delta")

    def test_mean_spread(self):
        """测试 mean_spread 家族"""
        family = classify_expression_family(
            "test",
            "ts_mean(sales, 5) - ts_mean(sales, 20)"
        )
        self.assertEqual(family, "mean_spread")


class TestIsLegacyFamily(unittest.TestCase):
    """is_legacy_family 函数测试用例"""

    def test_raw_field_is_legacy(self):
        """测试 raw_field 属于 legacy"""
        self.assertTrue(is_legacy_family("raw_field", "sales"))

    def test_rank_raw_field_is_legacy(self):
        """测试 rank_raw_field 属于 legacy"""
        self.assertTrue(is_legacy_family("rank_raw_field", "rank(sales)"))

    def test_ratio_is_legacy(self):
        """测试 ratio_ 前缀属于 legacy"""
        self.assertTrue(is_legacy_family("ratio_debt_assets", "debt/assets"))

    def test_group_rank_delta_not_legacy(self):
        """测试 group_rank_delta 不属于 legacy"""
        self.assertFalse(is_legacy_family(
            "test",
            "group_rank(ts_delta(rank(sales), 5), subindustry)"
        ))

    def test_zscore_not_legacy(self):
        """测试 zscore 不属于 legacy"""
        self.assertFalse(is_legacy_family("test", "ts_zscore(sales, 60)"))


if __name__ == "__main__":
    unittest.main()
