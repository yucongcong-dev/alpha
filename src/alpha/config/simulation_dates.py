"""Resolve simulation date ranges at the configuration boundary."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from .static_config import get_static_config

MONTHS_PER_YEAR = 12
DEFAULT_TEST_PERIOD_YEARS = 1
DEFAULT_TEST_PERIOD_MONTHS = 0


def resolve_simulation_dates(
    *,
    start_date: str | None,
    end_date: str | None,
    simulation_config: dict[str, Any] | None,
    today: date | None = None,
) -> tuple[str, str]:
    """Resolve explicit dates, test-period dates, fixed YAML dates, then fallbacks."""
    resolved_start = start_date
    resolved_end = end_date
    config = simulation_config or {}

    if resolved_start is None or resolved_end is None:
        years = int(config.get("testPeriodYears", DEFAULT_TEST_PERIOD_YEARS) or 0)
        months = int(config.get("testPeriodMonths", DEFAULT_TEST_PERIOD_MONTHS) or 0)
        total_months = years * MONTHS_PER_YEAR + months
        if total_months > 0:
            current = today or date.today()
            comparison_month = current.year * MONTHS_PER_YEAR + current.month - 1 - total_months
            year, month_index = divmod(comparison_month, MONTHS_PER_YEAR)
            month = month_index + 1
            day = min(current.day, calendar.monthrange(year, month)[1])
            if resolved_start is None:
                resolved_start = date(year, month, day).isoformat()
            if resolved_end is None:
                resolved_end = current.isoformat()

    return (
        resolved_start or str(config.get("startDate") or get_static_config().default_start_date),
        resolved_end or str(config.get("endDate") or get_static_config().default_end_date),
    )
