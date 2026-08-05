"""Dataset-scoped output path tests."""

from __future__ import annotations

from pathlib import Path

from alpha.io.output_paths import (
    build_dataset_scoped_paths,
    build_fields_cache_scope_key,
    resolve_cli_path,
)


def test_resolve_cli_path_uses_cwd_for_relative_paths(monkeypatch, tmp_path) -> None:
    """Relative CLI paths should resolve from the current working directory."""
    monkeypatch.chdir(tmp_path)

    resolved = resolve_cli_path("nested/config.json")

    assert resolved == str((tmp_path / "nested" / "config.json").resolve())


def test_build_dataset_scoped_paths_includes_runtime_context_in_cache_path() -> None:
    """Cache paths should distinguish region/universe/instrument/delay contexts."""
    paths = build_dataset_scoped_paths(
        "fundamental6",
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
    )

    template_path = Path(paths["template_library_file"])
    assert template_path.parts[-3:] == ("datasets", "fundamental6", "template.json")
    cache_path = Path(paths["fields_cache_file"])
    assert cache_path.parent.parts[-3:] == ("datasets", "fundamental6", "cache")
    assert cache_path.name == "usa_top3000_equity_d1.json"
    assert Path(paths["output"]).parts[-4:] == (
        "fundamental6",
        "runs",
        "default",
        "summary.json",
    )


def test_build_dataset_scoped_paths_sanitizes_run_directory_segments() -> None:
    paths = build_dataset_scoped_paths("fundamental6", run_name="../nightly run")

    assert Path(paths["output"]).parts[-4:] == (
        "fundamental6",
        "runs",
        "_nightly_run",
        "summary.json",
    )


def test_build_fields_cache_scope_key_uses_short_readable_context_key() -> None:
    assert (
        build_fields_cache_scope_key(
            region="USA",
            universe="TOP3000",
            instrument_type="EQUITY",
            delay=1,
        )
        == "usa_top3000_equity_d1"
    )
    assert build_fields_cache_scope_key() == "default"
