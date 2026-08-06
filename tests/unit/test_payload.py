"""Simulation payload precedence and test-period tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from alpha.config.simulation_dates import resolve_simulation_dates
from alpha.generators import payload as payload_module
from alpha.models.runtime_config import SimulationSettingsConfig

_SETTINGS = SimulationSettingsConfig(
    instrument_type="EQUITY",
    region="USA",
    universe="TOP3000",
    delay=1,
    decay=4,
    neutralization="SUBINDUSTRY",
    truncation=0.08,
    pasteurization="ON",
    unit_handling="VERIFY",
    nan_handling="OFF",
    language="FASTEXPR",
)


def test_zero_year_period_preserves_months_and_clamps_month_end() -> None:
    dates = resolve_simulation_dates(
        start_date=None,
        end_date=None,
        simulation_config={"testPeriodYears": 0, "testPeriodMonths": 1},
        today=date(2026, 3, 31),
    )

    assert dates == ("2026-02-28", "2026-03-31")


def test_explicit_dates_override_period_and_yaml_fixed_dates() -> None:
    dates = resolve_simulation_dates(
        start_date="2020-01-01",
        end_date="2020-12-31",
        simulation_config={
            "testPeriodYears": 1,
            "testPeriodMonths": 0,
            "startDate": "2019-01-01",
            "endDate": "2019-12-31",
        },
        today=date(2026, 3, 31),
    )

    assert dates == ("2020-01-01", "2020-12-31")


def test_zero_period_uses_yaml_fixed_dates() -> None:
    dates = resolve_simulation_dates(
        start_date=None,
        end_date=None,
        simulation_config={
            "testPeriodYears": 0,
            "testPeriodMonths": 0,
            "startDate": "2021-01-01",
            "endDate": "2021-06-30",
        },
    )

    assert dates == ("2021-01-01", "2021-06-30")


def test_missing_period_values_use_one_year_default() -> None:
    assert resolve_simulation_dates(
        start_date=None,
        end_date=None,
        simulation_config={"decay": 4},
        today=date(2026, 3, 31),
    ) == (
        "2025-03-31",
        "2026-03-31",
    )


def test_fixed_fallback_dates_are_used_without_period() -> None:
    assert resolve_simulation_dates(
        start_date=None,
        end_date=None,
        simulation_config={"testPeriodYears": 0, "testPeriodMonths": 0},
    ) == (
        "2020-01-01",
        "2025-12-31",
    )


def test_build_payload_and_settings_fingerprint_use_resolved_values() -> None:
    settings = replace(_SETTINGS, decay=8, start_date="2021-01-01", end_date="2021-12-31")
    payload = payload_module.build_simulation_payload(settings, "rank(field)")
    other = payload_module.build_simulation_payload(settings, "-rank(field)")

    assert payload["type"] == "REGULAR"
    assert payload["regular"] == "rank(field)"
    assert payload["settings"]["decay"] == 8
    assert payload["settings"]["startDate"] == "2021-01-01"
    assert payload_module.build_settings_fingerprint(settings) == payload_module.stable_fingerprint(
        payload["settings"]
    )
    assert payload_module.stable_fingerprint(
        payload["settings"]
    ) == payload_module.stable_fingerprint(other["settings"])
    assert payload_module.build_settings_fingerprint_from_payload({"decay": 8}) == (
        payload_module.stable_fingerprint({"decay": 8})
    )
