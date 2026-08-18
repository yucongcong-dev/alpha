"""Tests for cross-platform repository policy checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_check_repo_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_repo.py"
    spec = importlib.util.spec_from_file_location("check_repo", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_repo = _load_check_repo_module()


def test_repo_boundary_rejects_root_tmp_files(tmp_path: Path) -> None:
    (tmp_path / "tmp_notes.txt").write_text("scratch\n", encoding="utf-8")

    errors = check_repo.repo_boundary_check(tmp_path)

    assert any("root tmp_* files" in error for error in errors)
    assert any("tmp_notes.txt" in error for error in errors)


def test_removed_compat_file_check_rejects_root_app_facade(tmp_path: Path) -> None:
    alpha_dir = tmp_path / "src" / "alpha"
    app_dir = alpha_dir / "app"
    app_dir.mkdir(parents=True)
    (alpha_dir / "run_loop.py").write_text("", encoding="utf-8")

    errors = check_repo.removed_compat_file_check(tmp_path)

    assert any("compatibility aggregate files" in error for error in errors)
    assert any("src/alpha/run_loop.py" in error for error in errors)


def test_removed_compat_file_check_rejects_simulation_stage_aggregate(tmp_path: Path) -> None:
    app_dir = tmp_path / "src" / "alpha" / "app"
    core_dir = tmp_path / "src" / "alpha" / "core"
    app_dir.mkdir(parents=True)
    core_dir.mkdir(parents=True)
    (core_dir / "simulation_stages.py").write_text("", encoding="utf-8")

    errors = check_repo.removed_compat_file_check(tmp_path)

    assert any("compatibility aggregate files" in error for error in errors)
    assert any("src/alpha/core/simulation_stages.py" in error for error in errors)


def test_removed_compat_file_check_rejects_domain_conversion_facade(tmp_path: Path) -> None:
    app_dir = tmp_path / "src" / "alpha" / "app"
    models_dir = tmp_path / "src" / "alpha" / "models"
    app_dir.mkdir(parents=True)
    models_dir.mkdir(parents=True)
    (models_dir / "domain_conversion.py").write_text("", encoding="utf-8")

    errors = check_repo.removed_compat_file_check(tmp_path)

    assert any("compatibility aggregate files" in error for error in errors)
    assert any("src/alpha/models/domain_conversion.py" in error for error in errors)


def test_removed_compat_file_check_rejects_domain_codecs_layer(tmp_path: Path) -> None:
    app_dir = tmp_path / "src" / "alpha" / "app"
    models_dir = tmp_path / "src" / "alpha" / "models"
    app_dir.mkdir(parents=True)
    models_dir.mkdir(parents=True)
    (models_dir / "domain_codecs.py").write_text("", encoding="utf-8")

    errors = check_repo.removed_compat_file_check(tmp_path)

    assert any("compatibility aggregate files" in error for error in errors)
    assert any("src/alpha/models/domain_codecs.py" in error for error in errors)


def test_removed_compat_file_check_rejects_models_runtime_facade(tmp_path: Path) -> None:
    app_dir = tmp_path / "src" / "alpha" / "app"
    models_dir = tmp_path / "src" / "alpha" / "models"
    app_dir.mkdir(parents=True)
    models_dir.mkdir(parents=True)
    (models_dir / "runtime.py").write_text("", encoding="utf-8")

    errors = check_repo.removed_compat_file_check(tmp_path)

    assert any("compatibility aggregate files" in error for error in errors)
    assert any("src/alpha/models/runtime.py" in error for error in errors)


def test_removed_compat_file_check_rejects_dynamic_facade_helper(tmp_path: Path) -> None:
    alpha_dir = tmp_path / "src" / "alpha"
    app_dir = alpha_dir / "app"
    app_dir.mkdir(parents=True)
    (alpha_dir / "_facade.py").write_text("", encoding="utf-8")

    errors = check_repo.removed_compat_file_check(tmp_path)

    assert any("compatibility aggregate files" in error for error in errors)
    assert any("src/alpha/_facade.py" in error for error in errors)


def test_removed_compat_file_check_rejects_removed_constants_modules(tmp_path: Path) -> None:
    alpha_dir = tmp_path / "src" / "alpha"
    app_dir = alpha_dir / "app"
    config_dir = alpha_dir / "config"
    app_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (config_dir / "_constants_thresholds.py").write_text("", encoding="utf-8")

    errors = check_repo.removed_compat_file_check(tmp_path)

    assert any("compatibility aggregate files" in error for error in errors)
    assert any("src/alpha/config/_constants_thresholds.py" in error for error in errors)


def test_compat_import_check_rejects_package_facade_import(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_legacy.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        "from alpha." + "run_loop import run_field_test_loop\n",
        encoding="utf-8",
    )

    errors = check_repo.compat_import_check(tmp_path)

    assert any("canonical modules" in error for error in errors)
    assert any("tests/test_legacy.py:1" in error for error in errors)


def test_compat_import_check_rejects_symbol_package_export(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_legacy.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        "from alpha." + "models import ExecutionState\n",
        encoding="utf-8",
    )

    errors = check_repo.compat_import_check(tmp_path)

    assert any("canonical modules" in error for error in errors)
    assert any("tests/test_legacy.py:1" in error for error in errors)


def test_compat_import_check_rejects_models_runtime_import(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_legacy.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        "from alpha.models." + "runtime import ExecutionState\n",
        encoding="utf-8",
    )

    errors = check_repo.compat_import_check(tmp_path)

    assert any("canonical modules" in error for error in errors)
    assert any("tests/test_legacy.py:1" in error for error in errors)


def test_compat_import_check_rejects_removed_constants_import(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_legacy.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        "from alpha.config." + "_constants_thresholds import SUBMIT_MIN_FITNESS\n",
        encoding="utf-8",
    )

    errors = check_repo.compat_import_check(tmp_path)

    assert any("alpha.config.static_config" in error for error in errors)
    assert any("tests/test_legacy.py:1" in error for error in errors)


def test_arch_boundary_check_rejects_lower_level_app_import(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "core" / "worker.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("from alpha.app.run_loop import run_field_test_loop\n", encoding="utf-8")

    errors = check_repo.arch_boundary_check(tmp_path)

    assert any("lower-level modules" in error for error in errors)
    assert any("src/alpha/core/worker.py:1" in error for error in errors)


def test_scan_secrets_skips_ignored_runtime_dirs(tmp_path: Path) -> None:
    feedback_file = tmp_path / "datasets" / "fundamental6" / "runs" / "default" / "run.log"
    feedback_file.parent.mkdir(parents=True)
    feedback_file.write_text(
        "Authorization: " + "Basic local-run-output\n",
        encoding="utf-8",
    )

    assert check_repo.scan_secrets(tmp_path) == []


def test_dead_symbols_check_flags_unreferenced_module_constant(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "config" / "_constants_example.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        "ORPHANED_DEFAULT: int = 3\nLIVE_DEFAULT: int = 4\n",
        encoding="utf-8",
    )
    consumer = tmp_path / "src" / "alpha" / "app" / "consumer.py"
    consumer.parent.mkdir(parents=True)
    consumer.write_text(
        "from alpha.config._constants_example import LIVE_DEFAULT\n",
        encoding="utf-8",
    )

    errors = check_repo.dead_symbols_check(tmp_path)

    assert any("dead module-level symbols" in error for error in errors)
    assert any("ORPHANED_DEFAULT" in error for error in errors)
    assert not any("LIVE_DEFAULT" in error for error in errors)


def test_dead_symbols_check_allows_all_exported_names(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "config" / "_constants_exported.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        '__all__ = ["PUBLIC_TOKEN"]\nPUBLIC_TOKEN: str = "x"\n',
        encoding="utf-8",
    )

    errors = check_repo.dead_symbols_check(tmp_path)

    assert errors == []


def test_dead_symbols_check_counts_attribute_references(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "app" / "helpers.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("def used_via_attribute() -> None: ...\n", encoding="utf-8")
    consumer = tmp_path / "src" / "alpha" / "app" / "consumer.py"
    consumer.write_text(
        "import alpha.app.helpers as helpers\nhelpers.used_via_attribute()\n",
        encoding="utf-8",
    )

    errors = check_repo.dead_symbols_check(tmp_path)

    assert errors == []


def test_config_consistency_check_rejects_divergent_overlap(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.yaml").write_text(
        "global:\n  http:\n    polling_retry_buffer: 1.0\n",
        encoding="utf-8",
    )
    (config_dir / "constants_defaults.yaml").write_text(
        "http:\n  polling_retry_buffer: 0.5\n",
        encoding="utf-8",
    )

    errors = check_repo.config_consistency_check(tmp_path)

    assert any("polling_retry_buffer" in error for error in errors)
    assert any("settings.yaml global.*" in error for error in errors)


def test_config_consistency_check_accepts_matching_overlap(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.yaml").write_text(
        "global:\n  http:\n    polling_retry_buffer: 1.0\n",
        encoding="utf-8",
    )
    (config_dir / "constants_defaults.yaml").write_text(
        "http:\n  polling_retry_buffer: 1.0\n",
        encoding="utf-8",
    )

    assert check_repo.config_consistency_check(tmp_path) == []


def test_config_consistency_check_rejects_duplicate_default_section_owner(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.yaml").write_text("global: {}\n", encoding="utf-8")
    (config_dir / "constants_defaults.yaml").write_text(
        "api:\n  base_url: https://example.test\n",
        encoding="utf-8",
    )
    (config_dir / "quality_feedback.yaml").write_text(
        "api:\n  request_timeout: 10\n",
        encoding="utf-8",
    )

    errors = check_repo.config_consistency_check(tmp_path)

    assert any("default YAML section 'api'" in error for error in errors)


def test_config_binding_check_rejects_module_level_binding(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "config" / "yaml.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        "def _activate() -> None:\n    activate_config_from_argv()\n",
        encoding="utf-8",
    )

    errors = check_repo.config_binding_check(tmp_path)

    assert any("main.py" in error for error in errors)
    assert any("src/alpha/config/yaml.py:2" in error for error in errors)


def test_config_binding_check_rejects_non_entry_import_of_main(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "app" / "tool.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("from alpha.main import run_cli_entry\n", encoding="utf-8")

    errors = check_repo.config_binding_check(tmp_path)

    assert any("alpha.main may only be imported" in error for error in errors)


def test_config_binding_check_accepts_main_dispatch_binding(tmp_path: Path) -> None:
    entry_file = tmp_path / "src" / "alpha" / "__main__.py"
    entry_file.parent.mkdir(parents=True)
    entry_file.write_text(
        "from .main import run_cli_entry\n",
        encoding="utf-8",
    )
    main_file = tmp_path / "src" / "alpha" / "main.py"
    main_file.write_text(
        "def run_cli_entry() -> int:\n    activate_config_from_argv()\n    return 0\n",
        encoding="utf-8",
    )

    assert check_repo.config_binding_check(tmp_path) == []


def test_acl_boundary_check_rejects_domain_construction_outside_acl(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "app" / "run_loop.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        "def _convert(raw):\n    return FailedCheck(name=raw.get('name'))\n",
        encoding="utf-8",
    )

    errors = check_repo.acl_boundary_check(tmp_path)

    assert any("constructed outside the ACL" in error for error in errors)
    assert any("src/alpha/app/run_loop.py:2" in error for error in errors)


def test_acl_boundary_check_accepts_acl_module_construction(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "models" / "domain_parsers.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        "def parse_failed_check(data):\n    return FailedCheck(name=str(data.get('name')))\n",
        encoding="utf-8",
    )

    assert check_repo.acl_boundary_check(tmp_path) == []


def test_acl_boundary_check_ignores_annotations_and_type_checks(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "analysis" / "field_stats.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        "def count(results):\n"
        "    total = 0\n"
        "    for result in results:\n"
        "        if isinstance(result, FieldTestResult):\n"
        "            total += 1\n"
        "    return total\n",
        encoding="utf-8",
    )

    assert check_repo.acl_boundary_check(tmp_path) == []
