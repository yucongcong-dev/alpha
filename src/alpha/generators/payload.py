"""Simulation payload serialization from resolved runtime settings."""

from __future__ import annotations

from typing import Any

from ..models.runtime_config import SimulationSettingsConfig
from .fingerprint import stable_fingerprint


def build_simulation_payload(
    args: SimulationSettingsConfig,
    expression: str,
) -> dict[str, Any]:
    """Build a Brain simulation payload from the canonical resolved settings."""
    return {
        "type": "REGULAR",
        "settings": {
            "language": args.language,
            "instrumentType": args.instrument_type,
            "region": args.region,
            "universe": args.universe,
            "delay": args.delay,
            "neutralization": args.neutralization,
            "decay": args.decay,
            "truncation": args.truncation,
            "pasteurization": args.pasteurization,
            "unitHandling": args.unit_handling,
            "nanHandling": args.nan_handling,
            "maxTrade": args.max_trade,
            "visualization": False,
            "startDate": args.start_date,
            "endDate": args.end_date,
        },
        "regular": expression,
    }


def build_settings_fingerprint(args: SimulationSettingsConfig) -> str:
    """为当前模拟配置生成指纹，便于安全续跑与去重。"""
    payload = build_simulation_payload(args, "placeholder")
    return stable_fingerprint(payload["settings"])


def build_settings_fingerprint_from_payload(payload: object) -> str:
    """为单个具体 settings 变体生成配置指纹。"""
    return stable_fingerprint(payload)
