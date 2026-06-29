"""CLI parser precedence tests."""

from __future__ import annotations

import sys

from alpha.cli.parser import parse_args
from alpha.config import get_yaml_config


def clear_yaml_cache() -> None:
    """Clear parser config cache between tests."""
    if hasattr(get_yaml_config, "_yaml_config_cache"):
        delattr(get_yaml_config, "_yaml_config_cache")


def write_config(path) -> None:
    """Write a minimal config that would override CLI values if precedence regressed."""
    path.write_text(
        """
global:
  limits:
    limit: 300
    max_templates_per_field: 0
  runtime:
    smoke_test: false
    auto_update_blacklist: true
dataset_profiles:
  fundamental6:
    max_concurrent_simulations: 3
    max_templates_per_field: 8
""".strip(),
        encoding="utf-8",
    )


def test_cli_limit_overrides_yaml(monkeypatch, tmp_path) -> None:
    """Explicit CLI values must win over YAML global/profile defaults."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    write_config(config_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--config",
            str(config_path),
            "--limit",
            "50",
            "--max-templates-per-field",
            "5",
            "--max-concurrent-simulations",
            "1",
        ],
    )

    args = parse_args()

    assert args.limit == 50
    assert args.max_templates_per_field == 5
    assert args.max_concurrent_simulations == 1


def test_cli_smoke_test_overrides_yaml_false(monkeypatch, tmp_path) -> None:
    """--smoke-test must not be reset by runtime.smoke_test=false in YAML."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    write_config(config_path)
    monkeypatch.setattr(sys, "argv", ["alpha", "--config", str(config_path), "--smoke-test"])

    args = parse_args()

    assert args.smoke_test is True
    assert args.limit == 1
    assert args.max_templates_per_field == 1
    assert args.max_concurrent_simulations == 1


def test_yaml_can_enable_auto_update_blacklist(monkeypatch, tmp_path) -> None:
    """YAML runtime.auto_update_blacklist should be applied when CLI is silent."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    write_config(config_path)
    monkeypatch.setattr(sys, "argv", ["alpha", "--config", str(config_path)])

    args = parse_args()

    assert args.auto_update_blacklist is True


def test_cli_auto_update_blacklist_flag(monkeypatch, tmp_path) -> None:
    """--auto-update-blacklist should enable runtime blacklist updates explicitly."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  runtime:
    auto_update_blacklist: false
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--config", str(config_path), "--auto-update-blacklist"],
    )

    args = parse_args()

    assert args.auto_update_blacklist is True
