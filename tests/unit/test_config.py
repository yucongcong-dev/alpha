# -*- coding: utf-8 -*-
"""
配置模块单元测试

测试 alpha.config 中的配置常量和辅助函数。
"""

import unittest

from alpha.config import (
    API_BASE,
    AUTH_URL,
    DEFAULT_DATASET_ID,
    SIM_ACCEPT_HEADER,
    VERSION_HEADER,
    use_fundamental6_heuristics,
)


class TestConfigConstants(unittest.TestCase):
    """配置常量测试用例"""

    def test_api_base_is_string(self):
        """测试 API_BASE 是字符串"""
        self.assertIsInstance(API_BASE, str)
        self.assertTrue(API_BASE.startswith("https://"))

    def test_auth_url_contains_api_base(self):
        """测试 AUTH_URL 包含 API_BASE"""
        self.assertTrue(AUTH_URL.startswith(API_BASE))

    def test_default_dataset_id(self):
        """测试默认数据集 ID"""
        self.assertEqual(DEFAULT_DATASET_ID, "fundamental6")

    def test_version_header_format(self):
        """测试 VERSION_HEADER 格式"""
        self.assertIsInstance(VERSION_HEADER, dict)
        self.assertIn("Accept", VERSION_HEADER)
        self.assertIn("version=2.0", VERSION_HEADER["Accept"])

    def test_sim_accept_header_format(self):
        """测试 SIM_ACCEPT_HEADER 格式"""
        self.assertIsInstance(SIM_ACCEPT_HEADER, dict)
        self.assertIn("Accept", SIM_ACCEPT_HEADER)
        self.assertIn("version=3.0", SIM_ACCEPT_HEADER["Accept"])


class TestUseFundamental6Heuristics(unittest.TestCase):
    """use_fundamental6_heuristics 函数测试用例"""

    def test_exact_match(self):
        """测试精确匹配 fundamental6"""
        self.assertTrue(use_fundamental6_heuristics("fundamental6"))

    def test_case_insensitive_match(self):
        """测试不区分大小写匹配"""
        self.assertTrue(use_fundamental6_heuristics("FUNDAMENTAL6"))

    def test_contains_keyword(self):
        """测试包含关键词时匹配"""
        self.assertTrue(use_fundamental6_heuristics("fundamental6_v2"))

    def test_other_dataset(self):
        """测试其他数据集不匹配"""
        self.assertFalse(use_fundamental6_heuristics("model51"))

    def test_empty_string(self):
        """测试空字符串"""
        self.assertFalse(use_fundamental6_heuristics(""))

    def test_default_parameter(self):
        """测试默认参数值"""
        self.assertTrue(use_fundamental6_heuristics())


if __name__ == "__main__":
    unittest.main()
