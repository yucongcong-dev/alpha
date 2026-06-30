"""Output persistence tests."""

from __future__ import annotations

from pathlib import Path

from alpha.io.output import build_dataset_scoped_paths, dump_results, resolve_cli_path


def test_dump_results_does_not_update_blacklist_by_default(monkeypatch, tmp_path) -> None:
    """Runtime result writes must not mutate tracked blacklist files unless requested."""
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("alpha.io.output.auto_update_blacklist", lambda *args, **kwargs: calls.append(args))

    dump_results(
        str(tmp_path / "results.json"),
        "fundamental6",
        [],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )

    assert calls == []


def test_dump_results_updates_blacklist_when_enabled(monkeypatch, tmp_path) -> None:
    """The explicit opt-in flag should preserve the previous auto-update capability."""
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("alpha.io.output.auto_update_blacklist", lambda *args, **kwargs: calls.append(args))

    dump_results(
        str(tmp_path / "results.json"),
        "fundamental6",
        [],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        auto_update_template_blacklist=True,
    )

    assert len(calls) == 1


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
    assert template_path.parts[-4:] == ("data", "templates", "fundamental6", "library.json")
    cache_path = Path(paths["fields_cache_file"])
    assert cache_path.parent.parts[-7:] == (
        "cache",
        "fields",
        "fundamental6",
        "USA",
        "TOP3000",
        "EQUITY",
        "delay1",
    )
    assert cache_path.name == "fields.json"
    assert Path(paths["output"]).name == "test_results.json"
