"""Small, deterministic settings variant generation."""

from __future__ import annotations

from typing import Any

from ..config.static_config import get_static_config
from ..models.domain import SettingsVariant
from ..models.domain_parsers import parse_settings_variant
from ..models.runtime_options import TemplateBuildOptions
from .payload import build_simulation_payload


def build_setting_variants(
    args: TemplateBuildOptions,
    template_name: str,
    expression: str,
    *,
    field_feedback: dict[str, Any] | None = None,
) -> list[SettingsVariant]:
    """
    基于统一基准配置生成少量高信号 settings 变体。

    Generate a small set of high-signal settings variants around the baseline
    payload.
    """
    _ = template_name, field_feedback
    base_settings = build_simulation_payload(args, expression)["settings"]
    variants: list[SettingsVariant] = [parse_settings_variant(dict(base_settings))]
    lower_expr = expression.lower()

    def add_variant(**updates: Any) -> None:
        candidate = dict(base_settings)
        candidate.update(updates)
        casted = parse_settings_variant(candidate)
        if casted not in variants:
            variants.append(casted)

    tighter_truncation = min(
        float(base_settings.get("truncation", get_static_config().truncation_web_default)),
        get_static_config().truncation_tighter_max,
    )

    add_variant(decay=get_static_config().settings_variant_decay_slow)
    add_variant(decay=get_static_config().settings_variant_decay_fast)
    add_variant(truncation=tighter_truncation)

    if "group_neutralize(" in lower_expr:
        add_variant(
            neutralization=get_static_config().neutralization_none, truncation=tighter_truncation
        )
    elif get_static_config().group_name_subindustry in lower_expr or "group_rank(" in lower_expr:
        add_variant(
            neutralization=get_static_config().neutralization_industry,
            truncation=tighter_truncation,
        )
    else:
        add_variant(neutralization=get_static_config().neutralization_market)

    return variants
