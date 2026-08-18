"""
配置模块单元测试（pytest 风格）

测试 alpha.config 中的配置常量和辅助函数。
"""

from __future__ import annotations

from dataclasses import fields
import os
import subprocess
import sys
import time

import pytest

from alpha.config._constants_api import (
    API_BASE,
    AUTH_URL,
    SIM_ACCEPT_HEADER,
    VERSION_HEADER,
)
from alpha.config._constants_core import _yaml_val
from alpha.config._constants_thresholds import DEFAULT_DATASET_ID
from alpha.config.expression_policy_coercion import coerce_expression_policy_override
from alpha.config.expression_policy_merging import (
    expression_policy_overrides_for_dataset,
)
from alpha.config.expression_policy_schema import EXPRESSION_POLICY_TYPED_OVERRIDE_FIELDS
from alpha.config.models import DatasetExpressionPolicy, FieldTransformStage
from alpha.config.runtime_values import (
    clear_runtime_config_cache,
    get_runtime_config,
    load_feedback_template_min_priority,
    load_http_runtime_config,
    resolve_http_runtime_config,
)
from alpha.config.strategy_profiles import load_strategy_profile_schemas
import alpha.config.yaml as yaml_module
from alpha.config.yaml import (
    clear_yaml_caches,
    get_active_config_path,
    get_yaml_config,
    set_active_config_path,
    validate_yaml_config,
)
from alpha.config.yaml_sources import deep_merge, load_yaml_file
from alpha.config.yaml_validator import _get_schema_keys, clear_schema_cache
from alpha.policy.expression import (
    get_dataset_expression_policy,
    use_curated_heuristics_for_dataset,
)


class TestConfigConstants:
    """配置常量测试用例"""

    def test_api_base_is_string(self) -> None:
        assert isinstance(API_BASE, str)
        assert API_BASE.startswith("https://")

    def test_auth_url_contains_api_base(self) -> None:
        assert AUTH_URL.startswith(API_BASE)

    def test_default_dataset_id(self) -> None:
        assert DEFAULT_DATASET_ID == ""

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


def test_curated_heuristics_are_loaded_only_from_yaml() -> None:
    assert use_curated_heuristics_for_dataset("fundamental6") is False
    assert use_curated_heuristics_for_dataset("model16") is True
    assert use_curated_heuristics_for_dataset("fundamental6_v2") is False
    assert use_curated_heuristics_for_dataset("") is False


def test_expression_policy_can_be_overridden_from_yaml(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.expression_policy_merging.get_yaml_config",
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
    assert "base_protected" not in policy.protected_templates
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
        "alpha.config.expression_policy_merging.get_yaml_config",
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
    assert policy.closed_default_template_library is True
    assert policy.partner_limit == 0
    assert policy.account_template_boost == 0
    assert policy.high_conviction_ratio_priority_boost == 0
    assert policy.protected_templates == {
        "cashflow_assets_industry_zscore_252",
        "cashflow_enterprise_value_industry_zscore_252",
        "cashflow_cap_bucket_delta_over_std_63_126",
        "cashflow_change_trade_when_assets_zscore_252",
        "hc_ratio_group_zscore_252_over_cap",
        "group_ratio_delta_over_std_63_126_over_cap",
    }
    assert policy.high_conviction_ratio_pairs == {("cashflow_op", "cap")}
    assert policy.matrix_delta_over_std_windows == ()
    assert policy.ratio_delta_rank_windows == ()
    assert policy.ratio_delta_over_std_windows == ()
    assert policy.ratio_partner_candidates == {}
    assert policy.feedback_loop_policy.generate.settings_variant_budget == 1
    assert policy.feedback_loop_policy.resimulate.settings_variant_budget == 5
    assert policy.ratio_keywords == {}
    assert policy.preferred_partner_score_bonuses == {}
    assert policy.preferred_field_order == {"cashflow_op": 0}
    assert policy.field_min_coverage == 0.20
    assert policy.field_min_date_coverage == 0.98
    assert policy.field_min_alpha_count == 40
    assert policy.field_min_user_count == 8
    assert policy.event_field_prefixes == ()
    assert policy.event_max_templates_per_field == 0
    assert policy.event_max_templates_per_family == 0
    assert policy.event_allowed_template_stages == ()
    assert policy.event_allowed_template_families == set()
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
    assert policy.feedback_loop_policy.resimulate.enable_template_pruning is False
    assert policy.feedback_loop_policy.resimulate.preferred_template_stages == ()


def test_unknown_dataset_uses_nonzero_default_field_selection_policy() -> None:
    policy = get_dataset_expression_policy("new_dataset")

    assert policy.field_min_coverage == 0.20
    assert policy.field_min_date_coverage == 0.90
    assert policy.field_min_alpha_count == 10
    assert policy.field_min_user_count == 3
    assert policy.field_max_alpha_count == 10000
    assert policy.field_max_user_count == 5000
    assert policy.field_max_per_family == 2
    assert policy.field_exploration_ratio == 0.40
    assert policy.field_feedback_half_life_days == 365
    assert policy.field_feedback_min_attempts_for_promising == 2
    assert policy.preferred_field_type_order == {
        "MATRIX": 0,
        "VECTOR": 1,
        "GROUP": 2,
        "SET": 3,
    }


def test_unknown_dataset_uses_runtime_backfill_window_as_policy_default() -> None:
    policy = get_dataset_expression_policy("new_dataset", default_backfill_window=5)

    assert policy.matrix_field_transform.backfill_window == 5
    assert policy.matrix_field_transform.stages == (
        FieldTransformStage(kind="backfill", window=5, std=None),
    )
    assert policy.vector_field_transform.backfill_window == 5
    assert policy.ratio_numerator_transform.backfill_window == 5
    assert policy.ratio_denominator_transform.backfill_window == 5


def test_dataset_policy_backfill_override_beats_runtime_default() -> None:
    policy = get_dataset_expression_policy("model16", default_backfill_window=5)

    assert policy.matrix_field_transform.backfill_window == 252
    assert policy.matrix_field_transform.stages[0] == FieldTransformStage(
        kind="backfill", window=252, std=None
    )


def test_strategy_profile_schemas_are_loaded_from_yaml() -> None:
    schemas = load_strategy_profile_schemas()

    assert set(schemas) == {"explore", "refine", "candidate-focused"}
    assert schemas["explore"].tuning_keys["limits"] == (
        "limit",
        "max_templates_per_field",
        "max_templates_per_family",
        "max_new_simulations",
        "field_template_batch_size",
    )
    assert "feedback_loop_policy" in schemas["refine"].tuning_keys["expression_policies"]
    assert "runtime" not in schemas["explore"].tuning_keys
    assert "runtime" not in schemas["candidate-focused"].tuning_keys
    assert "filters" not in schemas["refine"].runtime_defaults
    assert schemas["explore"].runtime_defaults == {}


def test_strategy_profile_schema_validation_reports_unknown_sections(tmp_path) -> None:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
strategy_profiles:
  aggressive:
    purpose: "bad profile"
    primary_goal: "bad"
    tuning_keys: {}
  explore:
    purpose: "bad section"
    primary_goal: "bad"
    tuning_keys:
      magic:
        - hidden_knob
    runtime_defaults:
      magic:
        hidden_knob: true
""".strip(),
        encoding="utf-8",
    )

    warnings = validate_yaml_config(str(config_path))

    assert any("未知 profile 'aggressive'" in warning for warning in warnings)
    assert any("未知 section ['magic']" in warning for warning in warnings)
    assert any("runtime_defaults 存在未知 section 'magic'" in warning for warning in warnings)


def test_global_leaf_schema_reports_unknown_operational_key(tmp_path) -> None:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  concurrency:
    max_concurrent_simluations: 5
""".strip(),
        encoding="utf-8",
    )

    warnings = validate_yaml_config(str(config_path))

    assert any(
        "global.concurrency" in warning and "max_concurrent_simluations" in warning
        for warning in warnings
    )


def test_global_leaf_schema_reports_unknown_nested_key(tmp_path) -> None:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  quality:
    submit:
      min_fitnes: 1.35
""".strip(),
        encoding="utf-8",
    )

    warnings = validate_yaml_config(str(config_path))

    assert "global.quality.submit.min_fitnes 是未知配置路径。" in warnings


def test_strategy_profile_schema_validates_keys_and_runtime_default_types(tmp_path) -> None:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
strategy_profiles:
  explore:
    purpose: 123
    primary_goal: "bad defaults"
    notes: "not-a-list"
    tuning_keys:
      limits:
        - max_total_simluations
    runtime_defaults:
      limits:
        max_total_simluations: 10
        limit: "all"
""".strip(),
        encoding="utf-8",
    )

    warnings = validate_yaml_config(str(config_path))

    assert any("purpose 必须是字符串" in warning for warning in warnings)
    assert any("notes 必须是字符串列表" in warning for warning in warnings)
    assert any("max_total_simluations" in warning and "未知 key" in warning for warning in warnings)
    assert any("limits.limit 必须是 integer" in warning for warning in warnings)


def test_strategy_profile_loader_rejects_invalid_runtime_defaults() -> None:
    with pytest.raises(ValueError, match=r"limits\.limit 必须是 integer"):
        load_strategy_profile_schemas(
            {
                "strategy_profiles": {
                    "explore": {
                        "runtime_defaults": {"limits": {"limit": "all"}},
                    }
                }
            }
        )


def test_expression_policy_schema_keys_match_policy_fields() -> None:
    """Typed override schema should only name real DatasetExpressionPolicy fields."""
    policy_fields = {field.name for field in fields(DatasetExpressionPolicy)}

    assert policy_fields >= EXPRESSION_POLICY_TYPED_OVERRIDE_FIELDS


def test_expression_policy_coercion_resolves_tiers_and_skip_failures() -> None:
    should_update, value = coerce_expression_policy_override(
        "partner_limit",
        "@wide",
        tiers={"wide": 7},
    )
    assert should_update is True
    assert value == 7

    should_update, value = coerce_expression_policy_override(
        "partner_limit",
        "@missing",
        tiers={"wide": 7},
    )
    assert should_update is False
    assert value is None


def test_expression_policy_overrides_merge_default_curated_and_dataset_layers() -> None:
    yaml_config = {
        "expression_policies": {
            "__default__": {
                "protected_templates": ["base"],
                "matrix_field_transform": {"stages": [{"kind": "backfill", "window": 120}]},
                "feedback_loop_policy": {
                    "resimulate": {"preferred_template_stages": ["default_stage"]}
                },
            },
            "__curated__": {
                "protected_templates": ["curated"],
                "feedback_loop_policy": {
                    "resimulate": {"preferred_template_stages": ["curated_stage"]}
                },
            },
            "model51": {
                "protected_templates": ["dataset"],
                "matrix_field_transform": {"stages": [{"kind": "winsorize", "std": 4}]},
            },
        }
    }

    overrides = expression_policy_overrides_for_dataset(
        "model51",
        use_curated_heuristics=True,
        yaml_config=yaml_config,
    )

    assert overrides["protected_templates"] == ["base", "curated", "dataset"]
    assert overrides["matrix_field_transform"]["stages"] == [{"kind": "winsorize", "std": 4}]
    assert overrides["feedback_loop_policy"]["resimulate"]["preferred_template_stages"] == [
        "curated_stage"
    ]

    should_update, value = coerce_expression_policy_override(
        "matrix_field_transform",
        None,
        tiers={},
    )
    assert should_update is False
    assert value is None


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


def test_fundamental2_policy_keeps_seed_search_bounded() -> None:
    policy = get_dataset_expression_policy("fundamental2")

    assert policy.closed_default_template_library is True
    assert policy.partner_limit == 0
    assert policy.field_min_coverage == 0.70
    assert policy.field_min_date_coverage == 0.99
    assert policy.field_max_alpha_count == 50
    assert policy.field_exploration_ratio == 0.0
    assert policy.protected_templates == {
        "fundamental2_current_tax_assets_zscore_252",
        "fundamental2_current_minus_deferred_tax_assets_zscore_252",
    }


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


def test_load_yaml_file_returns_empty_mapping_for_missing_file(tmp_path) -> None:
    missing_path = tmp_path / "missing.yaml"

    assert load_yaml_file(str(missing_path)) == {}


def test_load_yaml_file_rejects_malformed_yaml(tmp_path) -> None:
    config_path = tmp_path / "broken.yaml"
    config_path.write_text("global: [broken", encoding="utf-8")

    with pytest.raises(ValueError, match="无法读取 YAML 配置"):
        load_yaml_file(str(config_path))


def test_load_yaml_file_rejects_non_mapping_top_level(tmp_path) -> None:
    config_path = tmp_path / "list.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="顶层必须是 mapping"):
        load_yaml_file(str(config_path))


def test_deep_merge_rejects_excessive_nesting() -> None:
    base = {"a": {"b": {"c": {"d": {"e": {"f": {"g": 0}}}}}}}
    override = {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}

    with pytest.raises(ValueError, match="嵌套层级超过合并上限"):
        deep_merge(base, override)


def test_yaml_val_rejects_uncoercible_value(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.yaml.get_yaml_config",
        lambda config_path="": {"global": {"quality": {"submit": {"min_fitness": "wrong"}}}},
    )

    with pytest.raises(ValueError, match="min_fitness"):
        _yaml_val("quality", "submit", "min_fitness", cast=float)


def test_schema_keys_cache_refreshes_when_sources_change(tmp_path) -> None:
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    first.write_text("section_a:\n  a: 1\n", encoding="utf-8")
    second.write_text("section_b:\n  b: 2\n", encoding="utf-8")

    clear_schema_cache()

    assert _get_schema_keys({"template_defaults": str(first)})["template_defaults"] == {"section_a"}
    assert _get_schema_keys({"template_defaults": str(second)})["template_defaults"] == {
        "section_b"
    }


def test_get_yaml_config_reloads_when_content_changes_with_same_stat_metadata(tmp_path) -> None:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text("global:\n  limits:\n    limit: 10\n", encoding="utf-8")
    first = get_yaml_config(str(config_path))
    original_stat = config_path.stat()

    config_path.write_text("global:\n  limits:\n    limit: 20\n", encoding="utf-8")
    os.utime(config_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    second = get_yaml_config(str(config_path))

    assert first["global"]["limits"]["limit"] == 10
    assert second["global"]["limits"]["limit"] == 20


def test_yaml_validation_is_scoped_to_each_cached_path(monkeypatch, tmp_path) -> None:
    first_path = tmp_path / "first.yaml"
    second_path = tmp_path / "second.yaml"
    first_path.write_text("global:\n  limits:\n    limit: 10\n", encoding="utf-8")
    second_path.write_text("global:\n  limits:\n    limit: 20\n", encoding="utf-8")
    validated_limits: list[int] = []

    def record_validation(data, _resolved_files) -> list[str]:
        validated_limits.append(data["global"]["limits"]["limit"])
        return []

    clear_yaml_caches()
    monkeypatch.setattr(yaml_module, "validate_merged_config", record_validation)

    get_yaml_config(str(first_path))
    get_yaml_config(str(second_path))
    get_yaml_config(str(first_path))

    assert validated_limits == [10, 20, 10]


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


def test_resolve_http_runtime_config_prefers_client_snapshot(monkeypatch) -> None:
    frozen = load_http_runtime_config()
    client = type("Client", (), {"http_config": frozen})()
    monkeypatch.setattr(
        "alpha.config.runtime_values.get_runtime_config",
        lambda: (_ for _ in ()).throw(AssertionError("must not read runtime YAML")),
    )

    assert resolve_http_runtime_config(client) is frozen


def test_resolve_http_runtime_config_keeps_standalone_fallback(monkeypatch) -> None:
    fallback = load_http_runtime_config()

    class Runtime:
        http = fallback

    def runtime_config() -> Runtime:
        return Runtime()

    monkeypatch.setattr(
        "alpha.config.runtime_values.get_runtime_config",
        runtime_config,
    )

    assert resolve_http_runtime_config(object()) is fallback


def test_cli_config_is_bound_before_yaml_backed_constants_import(tmp_path) -> None:
    """The CLI settings file must govern both constants and runtime snapshots."""
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        "global:\n"
        "  quality:\n"
        "    submit:\n"
        "      min_fitness: 1.35\n"
        "  http:\n"
        "    simulation_retry_wait: 12.5\n",
        encoding="utf-8",
    )
    script = """
import sys
sys.argv = ["alpha", "--config", sys.argv[1]]
import alpha.main

def inspect_bound_config():
    from alpha.config._constants_thresholds import SUBMIT_MIN_FITNESS
    from alpha.config.runtime_values import get_runtime_config

    assert SUBMIT_MIN_FITNESS == 1.35
    assert get_runtime_config().http.simulation_retry_wait == 12.5
    return 0

alpha.main.main = inspect_bound_config
assert alpha.main.run_cli_entry() == 0
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
        "alpha.config.expression_policy_merging.get_yaml_config",
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


def test_load_feedback_template_min_priority_reads_yaml_globals(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.runtime_values.get_yaml_config",
        lambda config_path="": {"global": {"feedback": {"feedback_template_min_priority": 175}}},
    )

    assert load_feedback_template_min_priority() == 175


def test_load_feedback_template_min_priority_rejects_negative_value(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.runtime_values.get_yaml_config",
        lambda config_path="": {"global": {"feedback": {"feedback_template_min_priority": -1}}},
    )

    with pytest.raises(ValueError, match="feedback_template_min_priority must be >= 0"):
        load_feedback_template_min_priority()


def test_load_http_runtime_config_rejects_invalid_waits(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.config.runtime_values.get_yaml_config",
        lambda config_path="": {"global": {"http": {"request_timeout": 0}}},
    )

    with pytest.raises(ValueError, match=r"http\.request_timeout"):
        load_http_runtime_config()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("request_timeout", float("nan")),
        ("rate_limit_default_wait", float("inf")),
    ],
)
def test_load_http_runtime_config_rejects_non_finite_values(
    monkeypatch,
    key,
    value,
) -> None:
    monkeypatch.setattr(
        "alpha.config.runtime_values.get_yaml_config",
        lambda config_path="": {"global": {"http": {key: value}}},
    )

    with pytest.raises(ValueError, match=rf"http\.{key} must be finite"):
        load_http_runtime_config()


def test_no_yaml_key_read_by_both_runtime_and_import_time_paths() -> None:
    """Every YAML key must have exactly one reader.

    runtime_values.get_runtime_config() is the only runtime reader of http.*
    and feedback.feedback_template_min_priority; the import-time constants in
    config/_constants_*.py must not read the same flat keys, otherwise the two
    paths can disagree about one setting. The key set mirrors
    runtime_values.py's HttpRuntimeConfig and load_feedback_template_min_priority.
    """
    import ast
    from pathlib import Path

    runtime_keys = {
        ("http", "request_timeout"),
        ("http", "rate_limit_default_wait"),
        ("http", "polling_default_wait"),
        ("http", "polling_no_retry_after_wait"),
        ("http", "server_error_backoff_max"),
        ("http", "server_error_backoff_step"),
        ("http", "retry_operation_default_wait"),
        ("http", "login_retry_wait"),
        ("http", "simulation_retry_wait"),
        ("http", "polling_retry_buffer"),
        ("feedback", "feedback_template_min_priority"),
    }

    root = Path(__file__).resolve().parents[2]
    constant_keys: set[tuple[str, ...]] = set()
    for module_path in (root / "src" / "alpha" / "config").glob("_constants*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id.startswith("_yaml")
            ):
                key_args = tuple(
                    arg.value
                    for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                )
                if key_args:
                    constant_keys.add(key_args)

    overlap = sorted(runtime_keys & constant_keys)
    assert overlap == [], (
        "YAML keys read by both runtime_values and import-time constants: "
        f"{overlap}; each key must have a single reader"
    )
