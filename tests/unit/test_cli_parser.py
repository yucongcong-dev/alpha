"""CLI parser precedence tests."""

from __future__ import annotations

import sys

from alpha.cli.parser import normalize_args_paths, parse_args
from alpha.cli.path_resolution import apply_run_paths
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
    assert args.simulation_max_pending_cycles == 60
    assert args.simulation_max_queue_seconds == 300


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


def test_cli_no_flag_overrides_yaml_true(monkeypatch, tmp_path) -> None:
    """--no-* flags must be able to disable YAML-enabled booleans."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  runtime:
    submit: true
    auto_update_blacklist: true
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
            "--no-submit",
            "--no-auto-update-blacklist",
            "--no-dry-run-plan",
            "--no-verbose",
            "--no-quiet",
        ],
    )

    args = parse_args()

    assert args.submit is False
    assert args.auto_update_blacklist is False
    assert args.dry_run_plan is False
    assert args.verbose is False
    assert args.quiet is False


def test_cli_no_run_mode_overrides_yaml_true(monkeypatch, tmp_path) -> None:
    """Run-mode booleans should also support explicit disabling."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  runtime:
    smoke_test: true
    full_run: true
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--config", str(config_path), "--no-smoke-test", "--no-full-run"],
    )

    args = parse_args()

    assert args.smoke_test is False
    assert args.full_run is False


def test_clean_command_parses(monkeypatch) -> None:
    """The clean subcommand should parse without requiring run credentials."""
    clear_yaml_cache()
    monkeypatch.setattr(sys, "argv", ["alpha", "clean", "--dry-run-clean"])

    args = parse_args()

    assert args.command == "clean"
    assert args.dry_run_clean is True


def test_normalize_args_paths_uses_dataset_scoped_defaults(monkeypatch, tmp_path) -> None:
    """Blank CLI path defaults should expand using the active dataset context."""
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "pv1",
            "--region",
            "USA",
            "--universe",
            "TOP1000",
            "--instrument-type",
            "EQUITY",
            "--delay",
            "2",
        ],
    )

    args = parse_args()
    paths = normalize_args_paths(args)

    assert paths.fields_cache_file.endswith("/cache/fields/pv1/USA/TOP1000/EQUITY/delay2/fields.json")
    assert paths.output.endswith("/results/pv1/test_results.json")


def test_normalize_args_paths_does_not_mutate_original_args(monkeypatch, tmp_path) -> None:
    """Path normalization should return RunPaths without rewriting raw CLI attrs in-place."""
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["alpha", "--dataset-id", "pv1"])

    args = parse_args()
    original_output = args.output
    original_template_library = args.template_library_file
    original_fields_cache = args.fields_cache_file

    paths = normalize_args_paths(args)

    assert original_output == ""
    assert original_template_library == ""
    assert original_fields_cache == ""
    assert args.output == ""
    assert args.template_library_file == ""
    assert args.fields_cache_file == ""
    assert paths.output.endswith("/results/pv1/test_results.json")


def test_normalize_args_paths_resolves_relative_files_from_cwd(monkeypatch, tmp_path) -> None:
    """User-supplied relative file paths should resolve from the shell cwd."""
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--include-fields-file",
            "tmp_priority_fields_round1.txt",
        ],
    )

    args = parse_args()
    paths = normalize_args_paths(args)

    assert paths.include_fields_file == str((tmp_path / "tmp_priority_fields_round1.txt").resolve())


def test_apply_run_paths_syncs_legacy_runtime_path_attrs(monkeypatch, tmp_path) -> None:
    """Normalized CLI paths should be mirrored back to args for legacy call sites."""
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--output",
            "results/custom.json",
            "--feedback-output",
            "results/feedback.json",
            "--fields-cache-file",
            "cache/fields.json",
            "--template-library-file",
            "data/templates/custom.json",
            "--creds-file",
            "~/.alpha/credentials.json",
            "--creds-key-file",
            "~/.alpha/credentials.key",
            "--include-fields-file",
            "filters/include_fields.txt",
            "--exclude-fields-file",
            "filters/exclude_fields.txt",
            "--include-templates-file",
            "filters/include_templates.txt",
            "--exclude-templates-file",
            "filters/exclude_templates.txt",
            "--log-file",
            "logs/runtime.log",
        ],
    )

    args = parse_args()
    paths = normalize_args_paths(args)
    apply_run_paths(args, paths)

    assert args.output == paths.output
    assert args.feedback_output == paths.feedback_output
    assert args.fields_cache_file == paths.fields_cache_file
    assert args.template_library_file == paths.template_library_file
    assert args.creds_file == paths.creds_file
    assert args.creds_key_file == paths.creds_key_file
    assert args.include_fields_file == paths.include_fields_file
    assert args.exclude_fields_file == paths.exclude_fields_file
    assert args.include_templates_file == paths.include_templates_file
    assert args.exclude_templates_file == paths.exclude_templates_file
    assert args.log_file == paths.log_file
    assert args.state_file == paths.state_file
    assert args.checkpoint_file == paths.checkpoint_file


def test_default_profile_applies_when_dataset_profile_is_missing(monkeypatch, tmp_path) -> None:
    """Missing dataset_profiles entries should still fall back to DEFAULT_PROFILE."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text("global:\n  runtime:\n    verbose: false\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--config", str(config_path), "--dataset-id", "custom_ds"],
    )

    args = parse_args()

    assert args.max_templates_per_field == 12


def test_yaml_global_still_beats_default_profile_when_dataset_profile_is_missing(
    monkeypatch, tmp_path
) -> None:
    """DEFAULT_PROFILE must not override YAML global defaults for unknown datasets."""
    clear_yaml_cache()
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  limits:
    max_templates_per_field: 9
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--config", str(config_path), "--dataset-id", "custom_ds"],
    )

    args = parse_args()

    assert args.max_templates_per_field == 9
