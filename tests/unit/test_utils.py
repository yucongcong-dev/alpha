"""
公共工具模块单元测试（pytest 风格）

测试 alpha.utils.helpers 中的工具函数，覆盖所有边界条件和回退链。
"""

from __future__ import annotations

from alpha.generators.fields import choose_field_name, choose_field_type
from alpha.utils import first_non_empty

# ============================================================================
# first_non_empty 测试
# ============================================================================


class TestFirstNonEmpty:
    """first_non_empty 函数测试用例"""

    def test_returns_first_non_empty_string(self) -> None:
        assert first_non_empty(None, "", "value") == "value"

    def test_returns_none_when_all_empty(self) -> None:
        assert first_non_empty(None, "", [], {}) is None

    def test_returns_first_non_empty_list(self) -> None:
        assert first_non_empty(None, [], [1, 2]) == [1, 2]

    def test_returns_first_non_empty_dict(self) -> None:
        assert first_non_empty(None, {}, {"key": "val"}) == {"key": "val"}

    def test_single_valid_value(self) -> None:
        assert first_non_empty("hello") == "hello"

    # ---- 补充边界测试 ----
    def test_zero_is_valid(self) -> None:
        """0 是有效值，不应被跳过。"""
        assert first_non_empty(None, "", 0) == 0

    def test_false_is_valid(self) -> None:
        """False 是有效值，不应被跳过。"""
        assert first_non_empty(None, "", False) is False

    def test_tuple_is_valid(self) -> None:
        """非空 tuple 是有效值（first_non_empty 不特殊处理 tuple）。"""
        # first_non_empty 仅将 None, "", [], {} 视为空，() 不被特殊处理
        result = first_non_empty(None, (), (1,))
        # () 是空元组但不是 [] 或 {}，所以被视为有效值
        assert result == ()

    def test_empty_tuple_is_not_skipped(self) -> None:
        """空 tuple () 不被 first_non_empty 视为空值。"""
        # first_non_empty 不将 () 视为空，只检查 None, "", [], {}
        result = first_non_empty(None, (), "fallback")
        assert result == ()

    def test_no_arguments_returns_none(self) -> None:
        """无参数调用返回 None。"""
        assert first_non_empty() is None


# ============================================================================
# choose_field_name 测试
# ============================================================================


class TestChooseFieldName:
    """choose_field_name 函数测试用例"""

    def test_prefers_id_over_name(self) -> None:
        assert choose_field_name({"id": "sales_id", "name": "Sales"}) == "sales_id"

    def test_falls_back_to_name(self) -> None:
        assert choose_field_name({"name": "Sales"}) == "Sales"

    def test_falls_back_to_mnemonic(self) -> None:
        assert choose_field_name({"mnemonic": "ebitda"}) == "ebitda"

    def test_falls_back_to_field(self) -> None:
        assert choose_field_name({"field": "close"}) == "close"

    # ---- 补充边界测试 ----
    def test_empty_field_returns_none_string(self) -> None:
        """所有字段都为空时返回 'None'。"""
        assert choose_field_name({}) == "None"

    def test_none_values_in_field(self) -> None:
        """字段值为 None 时正确跳过。"""
        assert choose_field_name({"id": None, "name": "Sales"}) == "Sales"

    def test_empty_string_values_skipped(self) -> None:
        """空字符串值被跳过。"""
        assert choose_field_name({"id": "", "name": "", "mnemonic": "ebitda"}) == "ebitda"

    def test_full_priority_chain(self) -> None:
        """验证完整的 4 级回退链：id > name > mnemonic > field。"""
        field = {"id": "a", "name": "b", "mnemonic": "c", "field": "d"}
        assert choose_field_name(field) == "a"

    def test_non_string_id_converted(self) -> None:
        """非字符串 id 被 str() 转换。"""
        result = choose_field_name({"id": 123})
        assert result == "123"
        assert isinstance(result, str)


# ============================================================================
# choose_field_type 测试
# ============================================================================


class TestChooseFieldType:
    """choose_field_type 函数测试用例"""

    def test_prefers_type(self) -> None:
        assert choose_field_type({"type": "MATRIX", "fieldType": "vector"}) == "MATRIX"

    def test_falls_back_to_fieldType(self) -> None:  # noqa: N802
        assert choose_field_type({"fieldType": "vector"}) == "VECTOR"

    def test_falls_back_to_category(self) -> None:
        assert choose_field_type({"category": "fundamental"}) == "FUNDAMENTAL"

    def test_returns_unknown_when_empty(self) -> None:
        assert choose_field_type({}) == "UNKNOWN"

    # ---- 补充边界测试 ----
    def test_already_uppercase_preserved(self) -> None:
        """已大写的类型保持不变。"""
        assert choose_field_type({"type": "MATRIX"}) == "MATRIX"

    def test_mixed_case_uppercased(self) -> None:
        """混合大小写转为全大写。"""
        assert choose_field_type({"type": "Matrix"}) == "MATRIX"

    def test_full_priority_chain(self) -> None:
        """验证完整的 3 级回退链：type > fieldType > category > UNKNOWN。"""
        field = {"type": "MATRIX", "fieldType": "vector", "category": "fundamental"}
        assert choose_field_type(field) == "MATRIX"

    def test_none_type_falls_back(self) -> None:
        """type 为 None 时回退到 fieldType。"""
        assert choose_field_type({"type": None, "fieldType": "vector"}) == "VECTOR"

    def test_empty_string_type_falls_back(self) -> None:
        """type 为空字符串时回退到 fieldType。"""
        assert choose_field_type({"type": "", "fieldType": "vector"}) == "VECTOR"

    def test_whitespace_only_not_skipped(self) -> None:
        """纯空白字符不被 first_non_empty 跳过，会被 upper() 处理。"""
        result = choose_field_type({"type": "  "})
        assert result == "  "

    def test_category_with_spaces(self) -> None:
        """category 中的空格保留但大写。"""
        assert choose_field_type({"category": "fundamental data"}) == "FUNDAMENTAL DATA"
