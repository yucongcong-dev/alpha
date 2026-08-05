"""Tests for repository documentation consistency checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_check_docs_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_docs.py"
    spec = importlib.util.spec_from_file_location("check_docs", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_docs = _load_check_docs_module()


def test_documentation_files_include_dataset_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")
    dataset_dir = tmp_path / "datasets" / "demo"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "README.md").write_text("# Demo\n", encoding="utf-8")
    (dataset_dir / "research_history.md").write_text("# History\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)

    paths = {path.relative_to(tmp_path).as_posix() for path in check_docs.documentation_files()}

    assert paths == {
        "README.md",
        "datasets/demo/README.md",
        "datasets/demo/research_history.md",
        "docs/guide.md",
    }


def _check(tmp_path: Path, text: str, *, flags: set[str] | None = None) -> list[str]:
    path = tmp_path / "README.md"
    path.write_text(text, encoding="utf-8")
    return check_docs.check_document(path, root=tmp_path, valid_cli_flags=flags)


def test_rejects_absolute_local_paths(tmp_path: Path) -> None:
    errors = _check(tmp_path, "`cd /Users/example/project`\n")
    assert any("absolute local path" in error for error in errors)


def test_rejects_missing_inline_repository_paths(tmp_path: Path) -> None:
    errors = _check(tmp_path, "Use `datasets/example/template.json`.\n")
    assert any("missing repository path" in error for error in errors)


def test_accepts_existing_inline_repository_paths(tmp_path: Path) -> None:
    target = tmp_path / "datasets" / "example" / "template.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    assert _check(tmp_path, "Use `datasets/example/template.json`.\n") == []


def test_rejects_unknown_cli_options(tmp_path: Path) -> None:
    errors = _check(tmp_path, "Run with `--removed-option`.\n", flags={"--help"})
    assert any("undocumented CLI option" in error for error in errors)


def test_accepts_known_cli_options_and_placeholders(tmp_path: Path) -> None:
    errors = _check(
        tmp_path,
        "Run `--help` or a `--no-*` override with `datasets/<dataset_id>/template.json`.\n",
        flags={"--help"},
    )
    assert errors == []
