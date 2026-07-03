"""Settings variant generation for near-pass alpha refinement."""

from __future__ import annotations

from typing import Any

from ..config.constants import (
    GROUP_NAME_SUBINDUSTRY,
    NEUTRALIZATION_INDUSTRY,
    NEUTRALIZATION_MARKET,
    NEUTRALIZATION_NONE,
    SETTINGS_VARIANT_DECAY_FAST,
    SETTINGS_VARIANT_DECAY_SLOW,
    TRUNCATION_TIGHTER_MAX,
    TRUNCATION_WEB_DEFAULT,
)
from ..models.domain import NearPassCandidate, SettingsVariant
from ..models.runtime import SimulationSettingsArgs
from .payload import build_simulation_payload


def build_setting_variants(
    args: SimulationSettingsArgs,
    template_name: str,
    expression: str,
    *,
    field_feedback: dict[str, Any] | None = None,
    refine_candidate: NearPassCandidate | None = None,
) -> list[SettingsVariant]:
    """
    基于统一基准配置生成少量高信号 settings 变体。

    Generate a small set of high-signal settings variants around the baseline
    payload, especially for near-pass candidates.
    """
    _ = template_name, field_feedback
    base_settings = build_simulation_payload(args, expression)["settings"]
    variants: list[SettingsVariant] = [dict(base_settings)]
    lower_expr = expression.lower()

    def add_variant(**updates: Any) -> None:
        candidate = dict(base_settings)
        candidate.update(updates)
        if candidate not in variants:
            variants.append(candidate)

    nearpass_failed_names = {
        str(check.get("name", "")).strip()
        for check in (refine_candidate.failed_checks if refine_candidate else [])
    }
    tighter_truncation = min(float(base_settings.get("truncation", TRUNCATION_WEB_DEFAULT)), TRUNCATION_TIGHTER_MAX)

    add_variant(truncation=tighter_truncation)

    if "group_neutralize(" in lower_expr:
        add_variant(neutralization=NEUTRALIZATION_NONE, truncation=tighter_truncation)
    elif GROUP_NAME_SUBINDUSTRY in lower_expr or "group_rank(" in lower_expr:
        add_variant(neutralization=NEUTRALIZATION_INDUSTRY, truncation=tighter_truncation)
    else:
        add_variant(neutralization=NEUTRALIZATION_MARKET)

    if refine_candidate is not None:
        if {"CONCENTRATED_WEIGHT", "LOW_SUB_UNIVERSE_SHARPE"} & nearpass_failed_names:
            add_variant(neutralization=NEUTRALIZATION_INDUSTRY, truncation=tighter_truncation)
            add_variant(neutralization=NEUTRALIZATION_MARKET, truncation=tighter_truncation)
        if "LOW_TURNOVER" in nearpass_failed_names:
            add_variant(decay=SETTINGS_VARIANT_DECAY_FAST, truncation=tighter_truncation)
        elif "HIGH_TURNOVER" in nearpass_failed_names:
            add_variant(decay=SETTINGS_VARIANT_DECAY_SLOW, truncation=tighter_truncation)
        else:
            add_variant(decay=SETTINGS_VARIANT_DECAY_FAST)
            add_variant(decay=SETTINGS_VARIANT_DECAY_SLOW, truncation=tighter_truncation)

    return variants
