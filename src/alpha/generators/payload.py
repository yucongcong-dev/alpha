"""Simulation payload construction from CLI args and merged YAML config."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from ..config.constants import (
    MONTHS_PER_YEAR,
    NEUTRALIZATION_SUBINDUSTRY,
)
from ..config.runtime_values import get_runtime_config
from ..config.yaml import get_yaml_config
from ..models.runtime_protocols import SimulationSettingsArgs
from .fingerprint import stable_fingerprint

WEBSITE_DEFAULTS: dict[str, Any] = {
    "language": "FASTEXPR",
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "neutralization": NEUTRALIZATION_SUBINDUSTRY,
    "decay": 4,
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "OFF",
    "visualization": False,
}
"""Brain website defaults used when YAML config is unavailable."""

API_TO_ARGS: dict[str, str] = {
    "instrumentType": "instrument_type",
    "unitHandling": "unit_handling",
    "nanHandling": "nan_handling",
    "startDate": "start_date",
    "endDate": "end_date",
}
"""Brain API camelCase setting key to CLI argparse attribute mapping."""

CLI_DEFAULTS: dict[str, Any] = {
    "instrument_type": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 4,
    "neutralization": NEUTRALIZATION_SUBINDUSTRY,
    "truncation": 0.08,
    "pasteurization": "ON",
    "unit_handling": "VERIFY",
    "nan_handling": "OFF",
    "language": "FASTEXPR",
}
"""argparse defaults used to distinguish explicit CLI overrides from defaults."""

TEST_PERIOD_DEFAULTS = {"testPeriodYears": 1, "testPeriodMonths": 0}
"""Default Brain test period: one year."""


def read_simulation_from_yaml() -> dict[str, Any] | None:
    """从合并 YAML 配置读取 global.simulation 节点，不可用时返回 None。"""
    yaml_cfg = get_yaml_config()
    if not yaml_cfg:
        return None
    global_cfg = yaml_cfg.get("global")
    if not isinstance(global_cfg, dict):
        return None
    sim = global_cfg.get("simulation")
    return sim if isinstance(sim, dict) else None


def resolve_setting(
    yaml_sim: dict[str, Any] | None,
    args: SimulationSettingsArgs,
    api_key: str,
) -> Any:
    """按 CLI > YAML > 官网默认 优先级解析单个设置参数。"""
    arg_key = API_TO_ARGS.get(api_key, api_key)
    cli_val = getattr(args, arg_key, None)
    if cli_val is not None and cli_val != CLI_DEFAULTS.get(arg_key):
        return cli_val
    if yaml_sim and api_key in yaml_sim:
        return yaml_sim[api_key]
    return WEBSITE_DEFAULTS.get(api_key, cli_val)


def resolve_test_period_dates(
    args: SimulationSettingsArgs,
    yaml_sim: dict[str, Any] | None,
) -> tuple[str, str]:
    """Resolve start/end dates from CLI, YAML test period, YAML fixed dates, or defaults."""
    start_date = None
    end_date = None

    cli_start = getattr(args, "start_date", None)
    cli_end = getattr(args, "end_date", None)
    if cli_start is not None and cli_start != CLI_DEFAULTS.get("start_date"):
        start_date = cli_start
    if cli_end is not None and cli_end != CLI_DEFAULTS.get("end_date"):
        end_date = cli_end

    if (start_date is None or end_date is None) and yaml_sim:
        years = yaml_sim.get("testPeriodYears") or TEST_PERIOD_DEFAULTS["testPeriodYears"]
        months = yaml_sim.get("testPeriodMonths") or TEST_PERIOD_DEFAULTS["testPeriodMonths"]
        total_months = (years or 0) * MONTHS_PER_YEAR + (months or 0)
        if total_months > 0:
            today = date.today()
            comp_months = today.year * MONTHS_PER_YEAR + today.month - 1
            comp_months -= total_months
            cy, cm = divmod(comp_months, MONTHS_PER_YEAR)
            cm += 1
            max_day = calendar.monthrange(cy, cm)[1]
            computed = date(cy, cm, min(today.day, max_day))
            if start_date is None:
                start_date = computed.isoformat()
            if end_date is None:
                end_date = today.isoformat()

    if yaml_sim:
        if start_date is None:
            start_date = yaml_sim.get("startDate")
        if end_date is None:
            end_date = yaml_sim.get("endDate")

    defaults = get_runtime_config().simulation
    return (
        start_date or defaults.start_date,
        end_date or defaults.end_date,
    )


def build_simulation_payload(args: SimulationSettingsArgs, expression: str) -> dict[str, Any]:
    """
    从合并 YAML 配置读取设置，构建模拟请求体。

    Build a Brain simulation payload from CLI args and merged YAML settings.
    """
    yaml_sim = read_simulation_from_yaml()

    settings: dict[str, Any] = {}
    for api_key in WEBSITE_DEFAULTS:
        settings[api_key] = resolve_setting(yaml_sim, args, api_key)

    start_date, end_date = resolve_test_period_dates(args, yaml_sim)
    settings["startDate"] = start_date
    settings["endDate"] = end_date

    return {
        "type": "REGULAR",
        "settings": settings,
        "regular": expression,
    }


def build_settings_fingerprint(args: SimulationSettingsArgs) -> str:
    """为当前模拟配置生成指纹，便于安全续跑与去重。"""
    payload = build_simulation_payload(args, "placeholder")
    return stable_fingerprint(payload["settings"])


def build_settings_fingerprint_from_payload(payload: dict[str, Any]) -> str:
    """为单个具体 settings 变体生成配置指纹。"""
    return stable_fingerprint(payload)
