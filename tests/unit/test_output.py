"""Output persistence tests."""

from __future__ import annotations

from alpha.io.output import dump_results


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
