"""
配置模块单元测试（pytest 风格）

测试 alpha.config 中的配置常量和辅助函数。
"""

from __future__ import annotations

from alpha.config import (
    API_BASE,
    AUTH_URL,
    DEFAULT_DATASET_ID,
    SIM_ACCEPT_HEADER,
    VERSION_HEADER,
    get_dataset_expression_policy,
    use_fundamental6_heuristics,
)


class TestConfigConstants:
    """配置常量测试用例"""

    def test_api_base_is_string(self) -> None:
        assert isinstance(API_BASE, str)
        assert API_BASE.startswith("https://")

    def test_auth_url_contains_api_base(self) -> None:
        assert AUTH_URL.startswith(API_BASE)

    def test_default_dataset_id(self) -> None:
        assert DEFAULT_DATASET_ID == "fundamental6"

    def test_version_header_format(self) -> None:
        assert isinstance(VERSION_HEADER, dict)
        assert "Accept" in VERSION_HEADER
        assert "version=2.0" in VERSION_HEADER["Accept"]

    def test_sim_accept_header_format(self) -> None:
        assert isinstance(SIM_ACCEPT_HEADER, dict)
        assert "Accept" in SIM_ACCEPT_HEADER
        assert "version=3.0" in SIM_ACCEPT_HEADER["Accept"]

    def test_auth_url_is_https(self) -> None:
        """AUTH_URL 也应该是 HTTPS 的。"""
        assert AUTH_URL.startswith("https://")


class TestUseFundamental6Heuristics:
    """use_fundamental6_heuristics 函数测试用例"""

    def test_exact_match(self) -> None:
        assert use_fundamental6_heuristics("fundamental6") is True

    def test_case_insensitive_match(self) -> None:
        assert use_fundamental6_heuristics("FUNDAMENTAL6") is True

    def test_contains_keyword(self) -> None:
        assert use_fundamental6_heuristics("fundamental6_v2") is True

    def test_other_dataset(self) -> None:
        assert use_fundamental6_heuristics("model51") is False

    def test_empty_string(self) -> None:
        assert use_fundamental6_heuristics("") is False

    def test_default_parameter(self) -> None:
        assert use_fundamental6_heuristics() is True

    # ---- 补充边界测试 ----
    def test_partial_match(self) -> None:
        """包含 "fundamental6" 子串即为匹配。"""
        assert use_fundamental6_heuristics("my_fundamental6_custom") is True

    def test_whitespace_only(self) -> None:
        """纯空白不包含 fundamental6，返回 False。"""
        assert use_fundamental6_heuristics("   ") is False

    def test_near_match_not_confused(self) -> None:
        """fundamental5 不应匹配 fundamental6。"""
        assert use_fundamental6_heuristics("fundamental5") is False

    def test_similar_but_different_dataset(self) -> None:
        """类似但不包含 fundamental6 的数据集名称不匹配。"""
        assert use_fundamental6_heuristics("price6") is False


def test_expression_policy_can_be_overridden_from_yaml(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.get_yaml_config",
        lambda config_path="": {
            "expression_policies": {
                "fundamental6": {
                    "partner_limit": 9,
                    "blacklisted_template_name_substrings": ["custom_block"],
                    "disabled_templates": ["weak_template"],
                    "template_prefix_penalties": [
                        {"prefixes": ["delta_", "group_delta_"], "penalty": -500}
                    ],
                }
            }
        },
    )

    policy = get_dataset_expression_policy("fundamental6")

    assert policy.partner_limit == 9
    assert policy.blacklisted_template_name_substrings == ("custom_block",)
    assert "weak_template" in policy.disabled_templates
    assert policy.template_prefix_penalties == {("delta_", "group_delta_"): -500}


def test_fundamental6_default_policy_is_loaded_from_settings_yaml() -> None:
    policy = get_dataset_expression_policy("fundamental6")

    assert policy.partner_limit == 6
    assert "account_rank_backfill_504" in policy.protected_templates
    assert ("cashflow_op", "fnd6_mkvalt") in policy.high_conviction_ratio_pairs
    assert policy.field_min_coverage == 0.10
    assert policy.field_min_alpha_count == 25
