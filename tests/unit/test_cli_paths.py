"""CLI path resolution and immutable application-config tests."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from alpha.cli.parser import parse_application_config, parse_args
from alpha.cli.path_resolution import normalize_args_paths
from alpha.cli.run_config import build_run_config_snapshot
from alpha.config import get_yaml_config
from alpha.models.runtime_options import ResultWriteOptions


def clear_yaml_cache() -> None:
    """Clear parser config cache between tests."""
    if hasattr(get_yaml_config, "_yaml_config_cache"):
        delattr(get_yaml_config, "_yaml_config_cache")


def test_clean_command_parses(monkeypatch) -> None:
    """The clean subcommand should parse without requiring run credentials."""
    clear_yaml_cache()
    monkeypatch.setattr(sys, "argv", ["alpha", "clean", "--dry-run-clean"])

    args = parse_args()

    assert args.command == "clean"
    assert args.dry_run_clean is True


@pytest.mark.parametrize("command", ["run", "clean"])
def test_normalize_args_paths_requires_dataset_id(monkeypatch, tmp_path, command) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    argv = ["alpha"] if command == "run" else ["alpha", "clean"]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(ValueError, match="--dataset-id is required"):
        normalize_args_paths(parse_args())


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

    assert paths.fields_cache_file.replace("\\", "/").endswith(
        "/datasets/pv1/cache/usa_top1000_equity_d2.json"
    )
    assert paths.template_library_file.replace("\\", "/").endswith("/datasets/pv1/template.json")
    assert paths.output.replace("\\", "/").endswith("/datasets/pv1/runs/default/summary.json")
    assert paths.feedback_output.replace("\\", "/").endswith(
        "/datasets/pv1/feedback/usa_top1000_equity_d2/summary.json"
    )
    assert paths.log_file.replace("\\", "/").endswith("/datasets/pv1/runs/default/run.log")


def test_normalize_args_paths_rejects_paused_fundamental6_without_explicit_entry(
    monkeypatch, tmp_path
) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["alpha", "--dataset-id", "fundamental6"])

    with pytest.raises(ValueError, match="dataset fundamental6 is paused"):
        normalize_args_paths(parse_args())


def test_normalize_args_paths_allows_clean_for_paused_fundamental6(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["alpha", "clean", "--dataset-id", "fundamental6"])

    paths = normalize_args_paths(parse_args())

    assert paths.template_library_file.replace("\\", "/").endswith(
        "/datasets/fundamental6/template.json"
    )


@pytest.mark.parametrize(
    "dataset_id",
    ["model16", "model51", "option8", "option9", "socialmedia12", "news18"],
)
def test_documented_paused_dataset_rejects_plain_run(monkeypatch, tmp_path, dataset_id) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["alpha", "--dataset-id", dataset_id])

    with pytest.raises(ValueError, match=f"dataset {dataset_id} is paused"):
        normalize_args_paths(parse_args())


def test_option8_explicit_active_preset_is_allowed(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    root = Path(__file__).resolve().parents[2]
    preset_dir = root / "datasets" / "option8" / "presets" / "subindustry_refine"
    template_path = preset_dir / "template.json"
    fields_path = preset_dir / "fields.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "option8",
            "--template-library-file",
            str(template_path),
            "--include-fields-file",
            str(fields_path),
        ],
    )

    paths = normalize_args_paths(parse_args())

    assert paths.template_library_file == str(template_path)
    assert paths.include_fields_file == str(fields_path)


def test_fundamental2_uses_default_tax_quality_preset(monkeypatch) -> None:
    clear_yaml_cache()
    monkeypatch.setattr(sys, "argv", ["alpha", "--dataset-id", "fundamental2"])

    paths = normalize_args_paths(parse_args())

    assert paths.template_library_file.replace("\\", "/").endswith(
        "/datasets/fundamental2/presets/tax_quality_seed/template.json"
    )
    assert paths.include_fields_file.replace("\\", "/").endswith(
        "/datasets/fundamental2/presets/tax_quality_seed/fields.txt"
    )
    assert paths.include_templates_file.replace("\\", "/").endswith(
        "/datasets/fundamental2/presets/tax_quality_seed/templates.txt"
    )


def test_explicit_template_path_allows_paused_fundamental6(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    custom_template = tmp_path / "custom-template.json"
    custom_template.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "fundamental6",
            "--template-library-file",
            str(custom_template),
        ],
    )

    paths = normalize_args_paths(parse_args())

    assert paths.template_library_file == str(custom_template)
    assert paths.include_fields_file == ""
    assert paths.include_templates_file == ""


@pytest.mark.parametrize(
    "option",
    [
        "--template-library-file",
        "--include-fields-file",
        "--include-templates-file",
    ],
)
def test_paused_dataset_rejects_empty_explicit_research_path(
    monkeypatch,
    tmp_path,
    option,
) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--dataset-id", "fundamental6", option, ""],
    )

    with pytest.raises(ValueError, match="must reference an existing file"):
        normalize_args_paths(parse_args())


def test_paused_dataset_rejects_missing_explicit_template_path(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "fundamental6",
            "--template-library-file",
            str(tmp_path / "missing-template.json"),
        ],
    )

    with pytest.raises(ValueError, match="must reference an existing file"):
        normalize_args_paths(parse_args())


def test_explicit_budgeted_full_run_allows_paused_fundamental6(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "fundamental6",
            "--strategy-profile",
            "explore",
            "--full-run",
            "--max-total-simulations",
            "100",
        ],
    )

    args = parse_args()
    paths = normalize_args_paths(args)

    assert args.full_run is True
    assert args.max_total_simulations == 100
    assert paths.template_library_file.replace("\\", "/").endswith(
        "/datasets/fundamental6/template.json"
    )


def test_budgeted_full_run_dry_plan_allows_paused_fundamental6(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "fundamental6",
            "--full-run",
            "--max-total-simulations",
            "25",
            "--dry-run-plan",
        ],
    )

    args = parse_args()
    normalize_args_paths(args)

    assert args.dry_run_plan is True
    assert args.max_total_simulations == 25


@pytest.mark.parametrize(
    "extra_args",
    [
        ["--full-run"],
        ["--full-run", "--max-total-simulations", "0"],
    ],
)
def test_paused_full_run_requires_explicit_positive_budget(
    monkeypatch,
    tmp_path,
    extra_args,
) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--dataset-id", "fundamental6", *extra_args],
    )

    with pytest.raises(ValueError, match="requires an explicit positive"):
        normalize_args_paths(parse_args())


def test_yaml_full_run_does_not_unlock_paused_dataset(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
global:
  limits:
    max_total_simulations: 100
  runtime:
    full_run: true
dataset_profiles:
  fundamental6:
    paused: true
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
        ],
    )

    args = parse_args()
    assert args.full_run is True
    assert args.max_total_simulations == 100
    with pytest.raises(ValueError, match="dataset fundamental6 is paused"):
        normalize_args_paths(args)


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
    assert paths.output.replace("\\", "/").endswith("/datasets/pv1/runs/default/summary.json")


def test_normalize_args_paths_uses_named_run_directory(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--dataset-id", "pv1", "--run-name", "20260727-entry-validation"],
    )

    paths = normalize_args_paths(parse_args())

    assert paths.output.replace("\\", "/").endswith(
        "/datasets/pv1/runs/20260727-entry-validation/summary.json"
    )
    assert paths.state_file.replace("\\", "/").endswith(
        "/datasets/pv1/runs/20260727-entry-validation/state.json"
    )
    assert paths.checkpoint_file.replace("\\", "/").endswith(
        "/datasets/pv1/runs/20260727-entry-validation/interrupt_report.json"
    )


def test_parse_application_config_is_immutable_and_uses_normalized_paths(
    monkeypatch, tmp_path
) -> None:
    """The active runtime config should be immutable and own normalized paths."""
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--dataset-id", "pv1", "--output", "results/custom.json"],
    )

    config = parse_application_config()

    assert config.output == config.paths.output
    assert config.output == str((tmp_path / "results/custom.json").resolve())
    assert config.dataset.dataset_id == "pv1"
    assert config.dataset_id == config.dataset.dataset_id
    assert config.strategy_profile == "explore"
    assert config.planning.limit == config.limit
    assert config.execution.max_concurrent_simulations == config.max_concurrent_simulations
    assert config.quality.min_sharpe == config.min_sharpe
    assert ResultWriteOptions.from_config(config) == ResultWriteOptions(
        dataset_id="pv1",
        output_path=config.paths.output,
        auto_update_blacklist=False,
    )
    assert not hasattr(config, "__dict__")
    with pytest.raises((AttributeError, TypeError)):
        config.limit = 999
    with pytest.raises((AttributeError, TypeError)):
        config.dataset.delay = 0


def test_parse_application_config_preserves_named_run_in_snapshot(monkeypatch, tmp_path) -> None:
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alpha", "--dataset-id", "pv1", "--run-name", "named-run"],
    )

    config = parse_application_config()
    snapshot = build_run_config_snapshot(config, config.paths)

    assert config.run_name == "named-run"
    assert snapshot["run"]["name"] == "named-run"
    assert config.paths.output.replace("\\", "/").endswith(
        "/datasets/pv1/runs/named-run/summary.json"
    )


def test_normalize_args_paths_resolves_relative_files_from_cwd(monkeypatch, tmp_path) -> None:
    """User-supplied relative file paths should resolve from the shell cwd."""
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tmp_priority_fields_round1.txt").write_text("cashflow_op\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "pv1",
            "--include-fields-file",
            "tmp_priority_fields_round1.txt",
        ],
    )

    args = parse_args()
    paths = normalize_args_paths(args)

    assert paths.include_fields_file == str((tmp_path / "tmp_priority_fields_round1.txt").resolve())


def test_normalize_args_paths_rejects_missing_explicit_filter_file(monkeypatch, tmp_path) -> None:
    """Explicit filter files should not silently degrade into empty filters."""
    clear_yaml_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha",
            "--dataset-id",
            "pv1",
            "--include-fields-file",
            "missing_fields.txt",
        ],
    )

    args = parse_args()

    with pytest.raises(ValueError, match="--include-fields-file"):
        normalize_args_paths(args)


def test_cli_rejects_abbreviated_long_options(monkeypatch) -> None:
    """Mistyped long options should fail instead of matching a longer option by prefix."""
    clear_yaml_cache()
    monkeypatch.setattr(sys, "argv", ["alpha", "--include-fields", "cashflow_op"])

    with pytest.raises(SystemExit):
        parse_args()


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
