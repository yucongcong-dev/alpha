"""Declarative settings table consistency tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from alpha.cli.parser_schema import build_parser, collect_parser_defaults
from alpha.config.defaults import apply_yaml_global_defaults
from alpha.config.settings_spec import SETTINGS, dataset_profile_keys, yaml_default_settings

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_DATASET_PROFILE_KEYS = {
    "page_size",
    "min_request_interval",
    "sleep_between_fields",
    "max_concurrent_simulations",
    "max_concurrent_creates",
    "max_templates_per_field",
    "field_template_batch_size",
    "simulation_max_wait_seconds",
    "simulation_max_queue_seconds",
    "queue_busy_cooldown_seconds",
}


def test_setting_specs_are_unique() -> None:
    """dest / CLI 名称 / YAML 路径都必须唯一，避免合并覆盖歧义。"""
    dests = [spec.dest for spec in SETTINGS]
    clis = [spec.cli for spec in SETTINGS if spec.cli]
    yamls = [spec.yaml for spec in SETTINGS if spec.yaml]
    assert len(dests) == len(set(dests))
    assert len(clis) == len(set(clis))
    assert len(yamls) == len(set(yamls))


def test_every_setting_dest_has_parser_default() -> None:
    """设置表里的每个 dest 都必须存在于 argparse 默认值中。"""
    parser_defaults = collect_parser_defaults(build_parser())
    missing = [spec.dest for spec in SETTINGS if spec.dest not in parser_defaults]
    assert missing == []


def test_parser_exposes_all_cli_settings() -> None:
    """每个带 CLI 名称的设置都必须以正确 dest 暴露在 parser 上。"""
    parser = build_parser()
    option_to_dest = {
        option: action.dest for action in parser._actions for option in action.option_strings
    }
    mismatches = [
        (spec.dest, spec.cli, option_to_dest.get(spec.cli))
        for spec in SETTINGS
        if spec.cli and option_to_dest.get(spec.cli) != spec.dest
    ]
    assert mismatches == []


def test_bool_pair_settings_expose_no_variants() -> None:
    """bool_pair 设置必须同时暴露 --x 与 --no-x。"""
    parser = build_parser()
    options = {option for action in parser._actions for option in action.option_strings}
    for spec in SETTINGS:
        if spec.kind == "bool_pair":
            assert spec.cli in options
            assert f"--no-{spec.cli[2:]}" in options


def test_dataset_profile_keys_match_profile_config() -> None:
    """dataset profile 可覆盖的 dest 集合必须与 dataset_profiles.yaml 的键一致。"""
    assert set(dataset_profile_keys()) == EXPECTED_DATASET_PROFILE_KEYS


def test_yaml_global_defaults_merge_every_section() -> None:
    """global 各 section 的每个设置都应被 YAML 合并应用到目标对象。"""
    sentinel = {spec.dest: f"<{spec.dest}>" for spec in yaml_default_settings()}
    global_cfg: dict[str, object] = {"global": {}}
    assert isinstance(global_cfg["global"], dict)
    for spec in yaml_default_settings():
        assert spec.yaml is not None
        section = global_cfg["global"]
        for part in spec.yaml[:-1]:
            assert isinstance(section, dict)
            section = section.setdefault(part, {})
        assert isinstance(section, dict)
        section[spec.yaml[-1]] = sentinel[spec.dest]

    target = SimpleNamespace(**{spec.dest: None for spec in SETTINGS})
    apply_yaml_global_defaults(target, global_cfg, set())

    applied = {dest: getattr(target, dest) for dest in sentinel}
    assert applied == sentinel


def test_yaml_global_defaults_respect_explicit_cli() -> None:
    """CLI 显式传参时，YAML 默认值不得覆盖。"""
    global_cfg = {"global": {"limits": {"limit": 300}}}
    target = SimpleNamespace(limit=50)
    apply_yaml_global_defaults(target, global_cfg, {"limit"})
    assert target.limit == 50


OPTIONAL_YAML_KEYS = {"start_date", "end_date"}


def test_repo_settings_yaml_declares_every_mirrored_setting() -> None:
    """config/settings.yaml 必须声明每个 YAML 镜像设置，防止误删后静默回退到兜底值。"""
    import yaml

    settings_path = ROOT / "config" / "settings.yaml"
    data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    global_cfg = data.get("global", {}) if isinstance(data, dict) else {}
    missing = []
    for spec in yaml_default_settings():
        if spec.dest in OPTIONAL_YAML_KEYS:
            continue
        assert spec.yaml is not None
        section = global_cfg
        for part in spec.yaml[:-1]:
            section = section.get(part, {}) if isinstance(section, dict) else {}
        if not isinstance(section, dict) or spec.yaml[-1] not in section:
            missing.append((spec.dest, ".".join(spec.yaml)))
    assert missing == []


def test_section_field_sets_match_runtime_dataclasses() -> None:
    """每个 section 的设置 dest 集合必须与对应运行时 dataclass 字段一致。"""
    from dataclasses import fields

    from alpha.config.application_sections import (
        DatasetConfig,
        ExecutionConfig,
        PlanningConfig,
        QualityConfig,
        RuntimeFlagsConfig,
        SimulationConfig,
    )
    from alpha.config.settings_spec import section_settings

    section_fields = {
        "dataset": {field.name for field in fields(DatasetConfig)} - {"dataset_id"},
        "simulation": {field.name for field in fields(SimulationConfig)},
        "planning": {field.name for field in fields(PlanningConfig)},
        "execution": {field.name for field in fields(ExecutionConfig)},
        "quality": {field.name for field in fields(QualityConfig)},
        "runtime_flags": {field.name for field in fields(RuntimeFlagsConfig)},
    }
    for section, expected in section_fields.items():
        assert {spec.dest for spec in section_settings(section)} == expected


def test_section_args_empty_namespace_uses_fallbacks() -> None:
    """空 namespace 时 from_args 必须落到 section 级防御性默认值。"""
    from alpha.config.application_sections import (
        ExecutionConfig,
        PlanningConfig,
        QualityConfig,
        SimulationConfig,
    )

    empty = SimpleNamespace()
    assert SimulationConfig.from_args(empty).decay == 4
    assert SimulationConfig.from_args(empty).neutralization == "SUBINDUSTRY"
    assert PlanningConfig.from_args(empty).page_size == 1
    assert ExecutionConfig.from_args(empty).max_concurrent_simulations == 1
    assert QualityConfig.from_args(empty).max_turnover == 1.0


def test_section_args_falsy_values_normalize_like_legacy() -> None:
    """falsy 值必须按旧版 `or 默认` 语义归一化。"""
    from alpha.config.application_sections import SimulationConfig

    assert SimulationConfig.from_args(SimpleNamespace(max_trade="")).max_trade == "OFF"
    assert SimulationConfig.from_args(SimpleNamespace(decay=0)).decay == 0
