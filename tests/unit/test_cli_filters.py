"""CLI filter file and logging boundary tests."""

from __future__ import annotations

import logging
from unittest.mock import Mock, patch

from alpha.cli.filters import (
    load_line_set,
    load_run_filters,
    load_run_filters_extended,
    setup_runtime_logging,
)
from alpha.models.io_types import RunPaths


def _paths(tmp_path) -> RunPaths:
    return RunPaths(
        results_dir=str(tmp_path),
        log_file=str(tmp_path / "run.log"),
        state_file=str(tmp_path / "state.json"),
        checkpoint_file=str(tmp_path / "interrupt_report.json"),
        include_fields_file=str(tmp_path / "include_fields.txt"),
        exclude_fields_file=str(tmp_path / "exclude_fields.txt"),
        include_templates_file=str(tmp_path / "include_templates.txt"),
        exclude_templates_file=str(tmp_path / "exclude_templates.txt"),
    )


def test_load_line_set_ignores_blank_comments_and_duplicates(tmp_path) -> None:
    path = tmp_path / "fields.txt"
    path.write_text("\n# research note\nf1\nf1\n f2 \n", encoding="utf-8")

    assert load_line_set(str(path)) == {"f1", "f2"}
    assert load_line_set("") == set()
    assert load_line_set(str(tmp_path / "missing.txt")) == set()


def test_load_line_set_logs_unreadable_file(tmp_path, caplog) -> None:
    caplog.set_level(logging.WARNING)

    assert load_line_set(str(tmp_path)) == set()
    assert any("failed to read" in record.getMessage() for record in caplog.records)


def test_load_run_filters_reads_all_include_and_exclude_files(tmp_path) -> None:
    paths = _paths(tmp_path)
    (tmp_path / "include_fields.txt").write_text("f1\n", encoding="utf-8")
    (tmp_path / "exclude_fields.txt").write_text("f2\n", encoding="utf-8")
    (tmp_path / "include_templates.txt").write_text("rank\n", encoding="utf-8")
    (tmp_path / "exclude_templates.txt").write_text("raw\n", encoding="utf-8")

    basic = load_run_filters(paths)
    extended = load_run_filters_extended(paths)

    assert basic.exclude_fields == {"f2"}
    assert extended.include_fields == {"f1"}
    assert extended.exclude_fields == {"f2"}
    assert extended.include_templates == {"rank"}
    assert extended.exclude_templates == {"raw"}


def test_setup_runtime_logging_closes_old_handlers_and_adds_rotating_file(tmp_path) -> None:
    old_handler = Mock()
    root = Mock()
    root.handlers = [old_handler]
    new_handler = Mock()
    log_path = tmp_path / "nested" / "run.log"

    with (
        patch("alpha.cli.filters.logging.getLogger", return_value=root),
        patch("coloredlogs.install") as install,
        patch(
            "alpha.cli.filters.logging.handlers.TimedRotatingFileHandler",
            return_value=new_handler,
        ) as handler_factory,
    ):
        setup_runtime_logging(str(log_path))

    root.removeHandler.assert_called_once_with(old_handler)
    old_handler.close.assert_called_once_with()
    install.assert_called_once()
    handler_factory.assert_called_once_with(
        str(log_path), when="midnight", backupCount=7, encoding="utf-8"
    )
    new_handler.setFormatter.assert_called_once()
    root.addHandler.assert_called_once_with(new_handler)
    assert log_path.parent.is_dir()


def test_setup_runtime_logging_console_only_skips_file_handler() -> None:
    root = Mock()
    root.handlers = []

    with (
        patch("alpha.cli.filters.logging.getLogger", return_value=root),
        patch("coloredlogs.install"),
        patch("alpha.cli.filters.logging.handlers.TimedRotatingFileHandler") as handler_factory,
    ):
        setup_runtime_logging("")

    handler_factory.assert_not_called()
    root.addHandler.assert_not_called()
    root.info.assert_called_once_with("logging to console only")
