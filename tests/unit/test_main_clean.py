"""Runtime cleanup command tests."""

from __future__ import annotations

import pytest

from alpha.app.bootstrap import clean_runtime_artifacts
from alpha.config.application import CleanConfig
from alpha.io.file_lock import exclusive_file_lock


def _clean_config(
    *,
    dataset_id: str | None = None,
    all_datasets: bool = False,
    include_credentials: bool = False,
    confirm_clean: bool = False,
    dry_run_clean: bool = False,
) -> CleanConfig:
    return CleanConfig(
        command="clean",
        dataset_id=dataset_id,
        all_datasets=all_datasets,
        include_credentials=include_credentials,
        confirm_clean=confirm_clean,
        dry_run_clean=dry_run_clean,
    )


def _create_dataset_runtime(tmp_path, dataset_id: str) -> None:
    dataset_dir = tmp_path / "datasets" / dataset_id
    for dirname in ("cache", "runs", "feedback", "presets"):
        path = dataset_dir / dirname
        path.mkdir(parents=True)
        (path / "marker.txt").write_text("x", encoding="utf-8")
    (dataset_dir / "blacklist.json").write_text("{}", encoding="utf-8")
    (dataset_dir / "template.json").write_text("{}", encoding="utf-8")
    (dataset_dir / ".blacklist.transaction.lock").write_text("", encoding="utf-8")


def test_clean_defaults_to_global_preview(tmp_path) -> None:
    _create_dataset_runtime(tmp_path, "fundamental6")
    root_cache = tmp_path / "cache"
    root_cache.mkdir()

    assert clean_runtime_artifacts(_clean_config(), project_root=tmp_path) == 0

    assert (tmp_path / "datasets" / "fundamental6" / "runs").exists()
    assert root_cache.exists()


def test_confirmed_dataset_clean_only_removes_selected_runtime(tmp_path) -> None:
    _create_dataset_runtime(tmp_path, "fundamental6")
    _create_dataset_runtime(tmp_path, "option9")
    root_cache = tmp_path / "cache"
    root_cache.mkdir()

    config = _clean_config(dataset_id="fundamental6", confirm_clean=True)

    assert clean_runtime_artifacts(config, project_root=tmp_path) == 0
    selected = tmp_path / "datasets" / "fundamental6"
    untouched = tmp_path / "datasets" / "option9"
    assert not (selected / "cache").exists()
    assert not (selected / "runs").exists()
    assert not (selected / "feedback").exists()
    assert not (selected / ".blacklist.transaction.lock").exists()
    assert (selected / "presets").exists()
    assert (selected / "blacklist.json").exists()
    assert (selected / "template.json").exists()
    assert (untouched / "runs").exists()
    assert (untouched / ".blacklist.transaction.lock").exists()
    assert root_cache.exists()


def test_confirmed_global_clean_preserves_credentials_by_default(tmp_path) -> None:
    _create_dataset_runtime(tmp_path, "fundamental6")
    for dirname in ("cache", "results", ".credentials"):
        path = tmp_path / dirname
        path.mkdir()
        (path / "marker.txt").write_text("x", encoding="utf-8")

    config = _clean_config(all_datasets=True, confirm_clean=True)

    assert clean_runtime_artifacts(config, project_root=tmp_path) == 0
    assert not (tmp_path / "datasets" / "fundamental6" / "runs").exists()
    assert not (tmp_path / "cache").exists()
    assert not (tmp_path / "results").exists()
    assert (tmp_path / ".credentials").exists()


def test_confirmed_global_clean_can_include_credentials(tmp_path) -> None:
    creds = tmp_path / ".credentials"
    creds.mkdir()
    (creds / "credentials.json").write_text("{}", encoding="utf-8")
    config = _clean_config(
        all_datasets=True,
        include_credentials=True,
        confirm_clean=True,
    )

    assert clean_runtime_artifacts(config, project_root=tmp_path) == 0
    assert not creds.exists()


def test_explicit_dry_run_keeps_files(tmp_path) -> None:
    _create_dataset_runtime(tmp_path, "option9")
    config = _clean_config(dataset_id="option9", dry_run_clean=True)

    assert clean_runtime_artifacts(config, project_root=tmp_path) == 0
    assert (tmp_path / "datasets" / "option9" / "runs").exists()


def test_confirmed_clean_refuses_active_run(tmp_path) -> None:
    _create_dataset_runtime(tmp_path, "fundamental6")
    output_path = tmp_path / "datasets" / "fundamental6" / "runs" / "live" / "summary.json"
    output_path.parent.mkdir(parents=True)
    run_lock_path = f"{output_path}.run.lock"

    with exclusive_file_lock(run_lock_path), pytest.raises(RuntimeError, match="active runtime"):
        clean_runtime_artifacts(
            _clean_config(dataset_id="fundamental6", confirm_clean=True),
            project_root=tmp_path,
        )

    assert (tmp_path / "datasets" / "fundamental6" / "runs").exists()
