"""
配置模块单元测试（pytest 风格）

测试 alpha.config 中的配置常量和辅助函数。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from alpha.config import (
    API_BASE,
    AUTH_URL,
    DEFAULT_DATASET_ID,
    SIM_ACCEPT_HEADER,
    VERSION_HEADER,
    FieldTransformStage,
    get_yaml_config,
)
from alpha.config.runtime_values import (
    clear_runtime_config_cache,
    get_runtime_config,
    load_submit_quality_runtime_config,
)
from alpha.config.yaml import (
    clear_yaml_caches,
    get_active_config_path,
    set_active_config_path,
)
from alpha.policy.expression import (
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
        assert DEFAULT_DATASET_ID == "model51"

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
        "alpha.config.policy_overrides.get_yaml_config",
        lambda config_path="": {
            "expression_policies": {
                "__default__": {
                    "partner_limit": 5,
                    "preferred_partner_score_bonuses": {"assets": 11},
                },
                "__curated__": {
                    "protected_templates": ["base_protected"],
                },
                "fundamental6": {
                    "partner_limit": 9,
                    "protected_templates": ["dataset_protected"],
                    "matrix_field_transform": {
                        "stages": [{"kind": "backfill", "window": 720}],
                        "backfill_window": 720,
                    },
                    "feedback_loop_policy": {
                        "resimulate": {
                            "min_attempted_templates": 5,
                            "min_best_score": 0.4,
                            "settings_variant_budget": 4,
                            "enable_template_pruning": True,
                            "preferred_template_stages": ["event_conditioned"],
                        }
                    },
                    "template_prefix_penalties": [
                        {"prefixes": ["delta_", "group_delta_"], "penalty": -500}
                    ],
                },
            }
        },
    )

    policy = get_dataset_expression_policy("fundamental6")

    assert policy.partner_limit == 9
    assert "base_protected" in policy.protected_templates
    assert "dataset_protected" in policy.protected_templates
    assert policy.preferred_partner_score_bonuses["assets"] == 11
    assert policy.matrix_field_transform.backfill_window == 720
    assert policy.matrix_field_transform.stages == (
        FieldTransformStage(kind="backfill", window=720, std=None),
    )
    assert policy.feedback_loop_policy.resimulate.min_attempted_templates == 5
    assert policy.feedback_loop_policy.resimulate.preferred_template_stages == (
        "event_conditioned",
    )
    assert policy.template_prefix_penalties == {("delta_", "group_delta_"): -500}


def test_unknown_expression_policy_key_is_reported(caplog, monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.policy_overrides.get_yaml_config",
        lambda config_path="": {
            "expression_policies": {
                "new_dataset": {"unknown_selector": 1},
            }
        },
    )

    with caplog.at_level("WARNING", logger="alpha.config.policy_overrides"):
        policy = get_dataset_expression_policy("new_dataset")

    assert not hasattr(policy, "unknown_selector")
    assert "unknown expression policy key 'unknown_selector'" in caplog.text


def test_fundamental6_default_policy_is_loaded_from_settings_yaml() -> None:
    policy = get_dataset_expression_policy("fundamental6")

    assert policy.policy_version == "2026-07-30.1"
    assert policy.feedback_scope == "field_type"
    assert policy.partner_limit == 6
    assert "account_rank_backfill_504" in policy.protected_templates
    assert ("cashflow_op", "fnd6_mkvalt") in policy.high_conviction_ratio_pairs
    assert ("cashflow_op", "assets") in policy.high_conviction_ratio_pairs
    assert ("ebitda", "enterprise_value") in policy.high_conviction_ratio_pairs
    assert ("liabilities", "assets") in policy.high_conviction_ratio_pairs
    assert ("income", "assets") in policy.high_conviction_ratio_pairs
    assert ("sales", "assets") in policy.high_conviction_ratio_pairs
    assert policy.field_min_coverage == 0.20
    assert policy.field_min_date_coverage == 0.98
    assert policy.field_min_alpha_count == 40
    assert policy.field_min_user_count == 8
    assert policy.event_field_prefixes == ("fnd6_cptnewqeventv110_",)
    assert policy.event_field_min_coverage == 0.30
    assert policy.event_field_min_date_coverage == 0.99
    assert policy.event_max_templates_per_field == 3
    assert policy.event_max_templates_per_family == 1
    assert policy.event_allowed_template_stages == ("event_conditioned",)
    assert "event_trade_when" in policy.event_allowed_template_families
    assert policy.matrix_field_transform.backfill_window == 120
    assert policy.matrix_field_transform.stages == (
        FieldTransformStage(kind="backfill", window=120, std=None),
        FieldTransformStage(kind="winsorize", window=0, std=4.0),
    )
    assert policy.vector_field_transform.backfill_window == 120
    assert policy.vector_field_transform.stages == (
        FieldTransformStage(kind="backfill", window=120, std=None),
        FieldTransformStage(kind="winsorize", window=0, std=4.0),
    )
    assert policy.template_priority_penalties == {}
    assert policy.template_prefix_penalties == {}
    assert policy.feedback_loop_policy.resimulate.preferred_template_stages == (
        "group_second_order",
        "event_conditioned",
    )


def test_unknown_dataset_uses_nonzero_default_field_selection_policy() -> None:
    policy = get_dataset_expression_policy("new_dataset")

    assert policy.field_min_coverage == 0.20
    assert policy.field_min_date_coverage == 0.90
    assert policy.field_min_alpha_count == 10
    assert policy.field_min_user_count == 3
    assert policy.field_max_alpha_count == 10000
    assert policy.field_max_user_count == 5000
    assert policy.field_coverage_weight > 0
    assert policy.field_alpha_crowding_penalty_weight > 0
    assert policy.field_max_per_family == 2
    assert policy.field_exploration_ratio == 0.40
    assert policy.field_feedback_half_life_days == 365
    assert policy.field_feedback_min_attempts_for_promising == 2
    assert policy.field_unknown_metadata_penalty_weight == 0.08
    assert policy.preferred_field_type_order == {
        "MATRIX": 0,
        "VECTOR": 1,
        "GROUP": 2,
        "SET": 3,
    }


def test_model16_policy_uses_long_backfill_with_winsorize() -> None:
    policy = get_dataset_expression_policy("model16")

    assert policy.matrix_field_transform.backfill_window == 252
    assert policy.matrix_field_transform.stages == (
        FieldTransformStage(kind="backfill", window=252, std=None),
        FieldTransformStage(kind="winsorize", window=0, std=4.0),
    )
    assert "model16_bucket_cap_ratio_zscore_120" in policy.protected_templates
    assert "model16_ratio_cap_zscore_120" in policy.protected_templates
    assert (
        "analyst_revision_rank_derivative",
        "earnings_certainty_rank_derivative",
    ) not in policy.high_conviction_ratio_pairs
    assert not policy.ratio_delta_over_std_windows


def test_model51_policy_uses_risk_metric_winsorize_and_bucket_templates() -> None:
    policy = get_dataset_expression_policy("model51")

    assert policy.matrix_field_transform.backfill_window == 504
    assert policy.matrix_field_transform.stages == (
        FieldTransformStage(kind="backfill", window=504, std=None),
        FieldTransformStage(kind="winsorize", window=0, std=4.0),
    )
    assert "model51_bucket_cap_ratio_zscore_60" in policy.protected_templates
    assert "model51_ratio_cap_zscore_60" in policy.protected_templates
    assert "model51_group_zscore_subindustry_120" in policy.protected_templates


def test_get_yaml_config_reloads_when_file_changes(tmp_path) -> None:
    if hasattr(get_yaml_config, "_yaml_config_cache"):
        delattr(get_yaml_config, "_yaml_config_cache")
    config_path = tmp_path / "settings.yaml"
    config_path.write_text("global:\n  limits:\n    limit: 10\n", encoding="utf-8")

    first = get_yaml_config(str(config_path))
    time.sleep(0.01)
    config_path.write_text("global:\n  limits:\n    limit: 25\n", encoding="utf-8")
    os.utime(config_path, None)
    second = get_yaml_config(str(config_path))

    assert first["global"]["limits"]["limit"] == 10
    assert second["global"]["limits"]["limit"] == 25


def test_runtime_config_reloads_when_active_yaml_changes(tmp_path) -> None:
    original_path = get_active_config_path()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        "global:\n  http:\n    request_timeout: 11.0\n",
        encoding="utf-8",
    )
    try:
        set_active_config_path(str(config_path))
        clear_yaml_caches()
        clear_runtime_config_cache()
        assert get_runtime_config().http.request_timeout == 11.0

        time.sleep(0.01)
        config_path.write_text(
            "global:\n  http:\n    request_timeout: 22.0\n",
            encoding="utf-8",
        )
        os.utime(config_path, None)

        assert get_runtime_config().http.request_timeout == 22.0
    finally:
        set_active_config_path(original_path or "")
        clear_yaml_caches()
        clear_runtime_config_cache()


def test_cli_config_is_bound_before_yaml_backed_constants_import(tmp_path) -> None:
    """The CLI settings file must govern both constants and runtime snapshots."""
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        "global:\n  http:\n    request_timeout: 12.5\n",
        encoding="utf-8",
    )
    script = """
import sys
sys.argv = ["alpha", "--config", sys.argv[1]]
import alpha.main
from alpha.config.constants import HTTP_REQUEST_TIMEOUT
from alpha.config.runtime_values import get_runtime_config
assert HTTP_REQUEST_TIMEOUT == 12.5
assert get_runtime_config().http.request_timeout == 12.5
"""

    completed = subprocess.run(
        [sys.executable, "-c", script, str(config_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_expression_policy_default_section_applies_to_non_curated_dataset(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.policy_overrides.get_yaml_config",
        lambda config_path="": {
            "expression_policies": {
                "__default__": {
                    "partner_limit": 7,
                    "preferred_partner_score_bonuses": {"assets": 33},
                },
                "__curated__": {
                    "protected_templates": ["curated_only"],
                },
            }
        },
    )

    policy = get_dataset_expression_policy("custom_ds", use_curated_heuristics=False)

    assert policy.partner_limit == 7
    assert policy.preferred_partner_score_bonuses["assets"] == 33
    assert "curated_only" not in policy.protected_templates

def test_model51_policy_disables_undersized_holdout_experiment() -> None:
    """The small closed library cannot produce a statistically useful A/B holdout."""
    policy = get_dataset_expression_policy("model51")

    assert policy.closed_default_template_library is True

def test_load_submit_quality_runtime_config_reads_yaml_globals(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.runtime_values.get_yaml_config",
        lambda config_path="": {
            "global": {
                "quality": {
                    "min_sharpe": 1.7,
                    "min_fitness": 1.2,
                    "min_turnover": 0.03,
                    "max_turnover": 0.55,
                    "max_weight": 0.08,
                }
            }
        },
    )

    quality = load_submit_quality_runtime_config()

    assert quality.min_sharpe == 1.7
    assert quality.min_fitness == 1.2
    assert quality.min_turnover == 0.03
    assert quality.max_turnover == 0.55
    assert quality.max_weight == 0.08
