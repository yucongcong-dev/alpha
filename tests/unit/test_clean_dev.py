"""Tests for cross-platform development cache cleanup."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_clean_dev_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "clean_dev.py"
    spec = importlib.util.spec_from_file_location("clean_dev", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


clean_dev = _load_clean_dev_module()


def test_clean_dev_removes_cache_artifacts_without_touching_sources(tmp_path: Path) -> None:
    source_file = tmp_path / "src" / "alpha" / "module.py"
    cache_dir = tmp_path / "src" / "alpha" / "__pycache__"
    egg_info = tmp_path / "src" / "alpha.egg-info"
    coverage = tmp_path / ".coverage"
    cache_dir.mkdir(parents=True)
    egg_info.mkdir(parents=True)
    source_file.write_text("print('kept')\n", encoding="utf-8")
    (cache_dir / "module.pyc").write_bytes(b"cache")
    (egg_info / "PKG-INFO").write_text("cache\n", encoding="utf-8")
    coverage.write_text("cache\n", encoding="utf-8")

    removed = clean_dev.clean_dev(tmp_path)

    assert "src/alpha/__pycache__" in removed
    assert "src/alpha.egg-info" in removed
    assert ".coverage" in removed
    assert source_file.exists()
    assert not cache_dir.exists()
    assert not egg_info.exists()
    assert not coverage.exists()
