# -*- coding: utf-8 -*-
"""
公共工具模块单元测试

测试 alpha.utils.helpers 中的工具函数。
"""

import unittest

from alpha.utils import first_non_empty, choose_field_name, choose_field_type


class TestFirstNonEmpty(unittest.TestCase):
    """first_non_empty 函数测试用例"""

    def test_returns_first_non_empty_string(self):
        """测试返回第一个非空字符串"""
        self.assertEqual(first_non_empty(None, "", "value"), "value")

    def test_returns_none_when_all_empty(self):
        """测试所有值为空时返回 None"""
        self.assertIsNone(first_non_empty(None, "", [], {}))

    def test_returns_first_non_empty_list(self):
        """测试返回第一个非空列表"""
        self.assertEqual(first_non_empty(None, [], [1, 2]), [1, 2])

    def test_returns_first_non_empty_dict(self):
        """测试返回第一个非空字典"""
        self.assertEqual(first_non_empty(None, {}, {"key": "val"}), {"key": "val"})

    def test_single_valid_value(self):
        """测试单个有效值"""
        self.assertEqual(first_non_empty("hello"), "hello")


class TestChooseFieldName(unittest.TestCase):
    """choose_field_name 函数测试用例"""

    def test_prefers_id_over_name(self):
        """测试优先使用 id 而非 name"""
        field = {"id": "sales_id", "name": "Sales"}
        self.assertEqual(choose_field_name(field), "sales_id")

    def test_falls_back_to_name(self):
        """测试回退到 name"""
        field = {"name": "Sales"}
        self.assertEqual(choose_field_name(field), "Sales")

    def test_falls_back_to_mnemonic(self):
        """测试回退到 mnemonic"""
        field = {"mnemonic": "ebitda"}
        self.assertEqual(choose_field_name(field), "ebitda")

    def test_falls_back_to_field(self):
        """测试回退到 field"""
        field = {"field": "close"}
        self.assertEqual(choose_field_name(field), "close")


class TestChooseFieldType(unittest.TestCase):
    """choose_field_type 函数测试用例"""

    def test_prefers_type(self):
        """测试优先使用 type"""
        field = {"type": "MATRIX", "fieldType": "vector"}
        self.assertEqual(choose_field_type(field), "MATRIX")

    def test_falls_back_to_fieldType(self):
        """测试回退到 fieldType"""
        field = {"fieldType": "vector"}
        self.assertEqual(choose_field_type(field), "VECTOR")

    def test_falls_back_to_category(self):
        """测试回退到 category"""
        field = {"category": "fundamental"}
        self.assertEqual(choose_field_type(field), "FUNDAMENTAL")

    def test_returns_unknown_when_empty(self):
        """测试空字典返回 UNKNOWN"""
        self.assertEqual(choose_field_type({}), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
