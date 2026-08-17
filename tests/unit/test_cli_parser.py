"""CLI parser precedence and runtime-option tests."""

from __future__ import annotations

import sys

import pytest

from alpha.cli.parser import parse_args
from alpha.cli.parser_schema import build_parser, command_from_argv
from alpha.config.yaml import get_yaml_config


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
    strategy_profile: refine
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


def test_default_field_page_size_prefers_stability(monkeypatch) -> None:
    clear_yaml_cache()
    monkeypatch.setattr(sys, "argv", ["alpha"])

    assert parse_args().page_size == 20


def test_check_submissions_help_shows_only_refresh_controls() -> None:
    help_text = build_parser(command="check-submissions").format_help()

    assert "--pending-check-limit" in help_text
    assert "--check-submission-retries" in help_text
    assert "--decay" not in help_text
    assert "--max-templates-per-field" not in help_text
    assert "--dry-run-clean" not in help_text


def test_clean_help_hides_simulation_and_submission_controls() -> None:
    help_text = build_parser(command="clean").format_help()

    assert "--dry-run-clean" in help_text
    assert "--all-datasets" in help_text
    assert "--decay" not in help_text
    assert "--pending-check-limit" not in help_text


def test_run_help_prioritizes_common_research_controls() -> None:
    """Standard run help should not bury the common workflow in expert knobs."""
    help_text = build_parser(command="run").format_help()

    assert "--dataset-id" in help_text
    assert "--run-mode" in help_text
    assert "--dry-run-plan" in help_text
    assert "--max-new-simulations" in help_text
    assert "--max-concurrent-simulations" not in help_text
    assert "--simulation-create-retries" not in help_text
    assert "--pending-check-limit" not in help_text
    assert "--min-sharpe" not in help_text


def test_run_accepts_hidden_advanced_overrides(monkeypatch) -> None:
    """Existing scripts can retain advanced CLI overrides after help is simplified."""
    clear_yaml_cache()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--max-concurrent-simulations",
            "2",
            "--simulation-create-retries",
            "4",
            "--min-sharpe",
            "1.5",
        ],
    )

    args = parse_args()

    assert args.max_concurrent_simulations == 2
    assert args.simulation_create_retries == 4
    assert args.min_sharpe == 1.5


def test_command_parsers_reject_options_outside_their_surface() -> None:
    """The strict command parser is separate from the legacy compatibility path."""
    with pytest.raises(SystemExit):
        build_parser(command="clean").parse_args(["--decay", "4"])

    with pytest.raises(SystemExit):
        build_parser(command="check-submissions").parse_args(["--max-templates-per-field", "2"])


@pytest.mark.parametrize(
    ("command", "option_args"),
    [
        ("clean", ["--limit", "1"]),
        ("check-submissions", ["--max-templates-per-field", "2"]),
    ],
)
def test_parse_args_keeps_explicit_command_boundaries(monkeypatch, command, option_args) -> None:
    clear_yaml_cache()
    monkeypatch.setattr(sys, "argv", ["alpha", command, *option_args])

    with pytest.raises(SystemExit):
        parse_args()


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["clean", "--help"], "clean"),
        (["--run-name", "clean", "--help"], "run"),
        (["--output", "check-submissions", "--help"], "run"),
        (["--dataset-id", "fundamental6", "check-submissions", "--help"], "check-submissions"),
    ],
)
def test_command_from_argv_ignores_option_values(argv, expected) -> None:
    assert command_from_argv(argv) == expected


def test_dataset_profile_can_reduce_field_page_size(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
dataset_profiles:
  analyst4:
    page_size: 20
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--config", str(config_path), "--dataset-id", "analyst4"],
    )

    assert parse_args().page_size == 20


def test_cli_page_size_overrides_dataset_profile(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
dataset_profiles:
  analyst4:
    page_size: 20
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--config",
            str(config_path),
            "--dataset-id",
            "analyst4",
            "--page-size",
            "30",
        ],
    )

    assert parse_args().page_size == 30


def test_queue_busy_retry_limit_accepts_canonical_cli_name(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["alpha", "--queue-busy-retry-limit", "7"])

    args = parse_args()

    assert args.queue_busy_retry_limit == 7


def test_queue_busy_retry_limit_rejects_removed_cli_alias(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["alpha", "--field-queue-busy-skip-after", "7"])

    with pytest.raises(SystemExit):
        parse_args()


def test_max_trade_respects_cli_over_yaml_precedence(monkeypatch, tmp_path) -> None:
    """Max Trade should follow the same CLI > YAML precedence as other settings."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  simulation:
    maxTrade: "ON"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["alpha", "--config", str(config_path)])
    assert parse_args().max_trade == "ON"

    clear_yaml_cache()
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--config", str(config_path), "--max-trade", "OFF"],
    )
    assert parse_args().max_trade == "OFF"


def test_full_run_rejects_conflicting_explicit_search_limits(monkeypatch) -> None:
    clear_yaml_cache()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--strategy-profile",
            "candidate-focused",
            "--run-mode",
            "full",
            "--offset",
            "7",
            "--limit",
            "4",
            "--max-templates-per-field",
            "3",
            "--max-templates-per-family",
            "1",
            "--top-fields-by-feedback",
            "5",
        ],
    )

    with pytest.raises(ValueError, match="conflicts with explicit options"):
        parse_args()


def test_full_run_allows_explicit_unlimited_total_simulation_budget(monkeypatch) -> None:
    clear_yaml_cache()
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--run-mode", "full", "--max-new-simulations", "0"],
    )

    args = parse_args()

    assert args.max_new_simulations == 0


def test_cli_strategy_profile_applies_runtime_defaults(monkeypatch, tmp_path) -> None:
    """CLI can select a named strategy profile that rewrites non-explicit knobs."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    write_config(config_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--config", str(config_path), "--strategy-profile", "candidate-focused"],
    )

    args = parse_args()

    assert args.strategy_profile == "candidate-focused"
    assert args.limit == 30
    assert args.max_templates_per_field == 2
    assert args.field_template_batch_size == 1
    assert args.top_fields_by_feedback == 20


def test_config_source_chain_records_each_overriding_layer(monkeypatch, tmp_path) -> None:
    """The parser exposes the complete precedence path for a resolved value."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  limits:
    max_templates_per_field: 9
  runtime:
    strategy_profile: candidate-focused
dataset_profiles:
  fundamental6:
    max_templates_per_field: 8
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--config",
            str(config_path),
            "--dataset-id",
            "fundamental6",
            "--run-mode",
            "full",
        ],
    )

    args = parse_args()

    assert args.max_templates_per_field == 0
    assert args._config_sources["max_templates_per_field"] == "run_mode"
    assert args._config_source_chains["max_templates_per_field"] == (
        "parser_default",
        "global_yaml",
        "dataset_profile",
        "strategy_profile",
        "run_mode",
    )
    assert args._config_report["max_templates_per_field"] == {
        "value": 0,
        "source": "run_mode",
        "chain": [
            "parser_default",
            "global_yaml",
            "dataset_profile",
            "strategy_profile",
            "run_mode",
        ],
    }


def test_config_source_chain_keeps_explicit_cli_value(monkeypatch, tmp_path) -> None:
    """An explicit CLI value is final and lower-precedence layers do not appear."""
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
            "--max-concurrent-simulations",
            "1",
        ],
    )

    args = parse_args()

    assert args.max_concurrent_simulations == 1
    assert args._config_sources["max_concurrent_simulations"] == "cli"
    assert args._config_source_chains["max_concurrent_simulations"] == (
        "parser_default",
        "cli",
    )


def test_config_report_redacts_password(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--dataset-id", "option9", "--password", "plain-secret"],
    )

    args = parse_args()

    assert args._config_report["password"]["value"] == "<redacted>"


def test_cli_preserves_zero_field_template_batch_size_for_config_validation(
    monkeypatch, tmp_path
) -> None:
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    write_config(config_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--config", str(config_path), "--field-template-batch-size", "0"],
    )

    args = parse_args()

    assert args.field_template_batch_size == 0


def test_yaml_strategy_profile_rejects_unknown_value(monkeypatch, tmp_path) -> None:
    """YAML strategy profiles should use the same supported names as CLI choices."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  runtime:
    strategy_profile: aggressive
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["alpha", "--config", str(config_path)])

    with pytest.raises(ValueError, match="unsupported strategy_profile"):
        parse_args()


def test_cli_no_flag_overrides_yaml_true(monkeypatch, tmp_path) -> None:
    """--no-* flags must be able to disable YAML-enabled booleans."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  runtime:
    dry_run_plan: true
    verbose: true
    quiet: true
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--config",
            str(config_path),
            "--no-dry-run-plan",
            "--no-verbose",
            "--no-quiet",
        ],
    )

    args = parse_args()

    assert args.dry_run_plan is False
    assert args.verbose is False
    assert args.quiet is False


def test_run_mode_smoke_matches_smoke_test(monkeypatch, tmp_path) -> None:
    """--run-mode smoke applies smoke-test safety limits."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    write_config(config_path)
    monkeypatch.setattr(sys, "argv", ["alpha", "--config", str(config_path), "--run-mode", "smoke"])

    args = parse_args()

    assert args.run_mode == "smoke"
    assert args.limit == 1
    assert args.max_templates_per_field == 1
    assert args.max_concurrent_simulations == 1


def test_run_mode_full_rejects_conflicting_explicit_search_limits(monkeypatch) -> None:
    """--run-mode full rejects contradictory explicit search limits."""
    clear_yaml_cache()
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--run-mode", "full", "--offset", "7", "--limit", "4"],
    )

    with pytest.raises(ValueError, match="conflicts with explicit options"):
        parse_args()


def test_run_mode_normal_overrides_yaml_true(monkeypatch, tmp_path) -> None:
    """--run-mode normal selects the regular planning mode."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  runtime:
    dry_run_plan: false
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["alpha", "--config", str(config_path), "--run-mode", "normal"]
    )

    args = parse_args()

    assert args.run_mode == "normal"
