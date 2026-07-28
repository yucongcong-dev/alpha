"""Simulation payload precedence and test-period tests."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from alpha.generators import payload as payload_module


def _args(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "instrument_type": "EQUITY",
        "region": "USA",
        "universe": "TOP3000",
        "delay": 1,
        "decay": 4,
        "neutralization": "SUBINDUSTRY",
        "truncation": 0.08,
        "pasteurization": "ON",
        "unit_handling": "VERIFY",
        "nan_handling": "OFF",
        "max_trade": "OFF",
        "language": "FASTEXPR",
        "start_date": None,
        "end_date": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FixedDate(date):
    @classmethod
    def today(cls) -> _FixedDate:
        return cls(2026, 3, 31)


def test_read_simulation_from_yaml_rejects_invalid_nodes(monkeypatch) -> None:
    monkeypatch.setattr(payload_module, "get_yaml_config", lambda: None)
    assert payload_module.read_simulation_from_yaml() is None

    monkeypatch.setattr(payload_module, "get_yaml_config", lambda: {"global": []})
    assert payload_module.read_simulation_from_yaml() is None

    monkeypatch.setattr(
        payload_module,
        "get_yaml_config",
        lambda: {"global": {"simulation": {"decay": 8}}},
    )
    assert payload_module.read_simulation_from_yaml() == {"decay": 8}


def test_resolve_setting_uses_cli_then_yaml_then_website_default() -> None:
    yaml_sim = {"decay": 8, "region": "EUR"}

    assert payload_module.resolve_setting(yaml_sim, _args(decay=12), "decay") == 12
    assert payload_module.resolve_setting(yaml_sim, _args(), "decay") == 8
    assert payload_module.resolve_setting(None, _args(), "region") == "USA"


def test_zero_year_period_preserves_months_and_clamps_month_end(monkeypatch) -> None:
    monkeypatch.setattr(payload_module, "date", _FixedDate)

    dates = payload_module.resolve_test_period_dates(
        _args(),
        {"testPeriodYears": 0, "testPeriodMonths": 1},
    )

    assert dates == ("2026-02-28", "2026-03-31")


def test_cli_dates_override_period_and_yaml_fixed_dates(monkeypatch) -> None:
    monkeypatch.setattr(payload_module, "date", _FixedDate)

    dates = payload_module.resolve_test_period_dates(
        _args(start_date="2020-01-01", end_date="2020-12-31"),
        {
            "testPeriodYears": 1,
            "testPeriodMonths": 0,
            "startDate": "2019-01-01",
            "endDate": "2019-12-31",
        },
    )

    assert dates == ("2020-01-01", "2020-12-31")


def test_zero_period_uses_yaml_fixed_dates(monkeypatch) -> None:
    monkeypatch.setattr(payload_module, "date", _FixedDate)

    dates = payload_module.resolve_test_period_dates(
        _args(),
        {
            "testPeriodYears": 0,
            "testPeriodMonths": 0,
            "startDate": "2021-01-01",
            "endDate": "2021-06-30",
        },
    )

    assert dates == ("2021-01-01", "2021-06-30")


def test_missing_period_values_use_one_year_default(monkeypatch) -> None:
    monkeypatch.setattr(payload_module, "date", _FixedDate)

    assert payload_module.resolve_test_period_dates(_args(), {"decay": 4}) == (
        "2025-03-31",
        "2026-03-31",
    )


def test_runtime_dates_are_final_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        payload_module,
        "get_runtime_config",
        lambda: SimpleNamespace(
            simulation=SimpleNamespace(start_date="2022-01-01", end_date="2022-12-31")
        ),
    )

    assert payload_module.resolve_test_period_dates(_args(), None) == (
        "2022-01-01",
        "2022-12-31",
    )


def test_build_payload_and_settings_fingerprint(monkeypatch) -> None:
    monkeypatch.setattr(
        payload_module,
        "read_simulation_from_yaml",
        lambda: {
            "decay": 8,
            "testPeriodYears": 0,
            "testPeriodMonths": 0,
            "startDate": "2021-01-01",
            "endDate": "2021-12-31",
        },
    )

    payload = payload_module.build_simulation_payload(_args(), "rank(field)")
    other = payload_module.build_simulation_payload(_args(), "-rank(field)")

    assert payload["type"] == "REGULAR"
    assert payload["regular"] == "rank(field)"
    assert payload["settings"]["decay"] == 8
    assert payload["settings"]["startDate"] == "2021-01-01"
    assert payload_module.build_settings_fingerprint(_args()) == payload_module.stable_fingerprint(
        payload["settings"]
    )
    assert payload_module.stable_fingerprint(
        payload["settings"]
    ) == payload_module.stable_fingerprint(other["settings"])
    assert payload_module.build_settings_fingerprint_from_payload({"decay": 8}) == (
        payload_module.stable_fingerprint({"decay": 8})
    )
