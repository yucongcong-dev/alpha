"""Typed coercion helpers for YAML expression-policy overrides."""

from __future__ import annotations

from typing import Any

from .constants import DEFAULT_SETTINGS_VARIANT_BUDGET, STATS_DEFAULT_SCORE
from .models import FeedbackLoopPolicy, FeedbackPhasePolicy, FieldTransformSpec, FieldTransformStage


def tuple_tuple_int(value: Any, width: int) -> tuple[tuple[int, ...], ...]:
    """Coerce [[int, ...], ...] values to tuples with a fixed row width."""
    if not isinstance(value, (list, tuple)):
        return ()
    rows: list[tuple[int, ...]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != width:
            continue
        try:
            rows.append(tuple(int(part) for part in item))
        except (TypeError, ValueError):
            continue
    return tuple(rows)


def tuple_tuple_str_int(value: Any) -> tuple[tuple[str, str, int], ...]:
    """Coerce template specs to (name, expression, priority) tuples."""
    if not isinstance(value, (list, tuple)):
        return ()
    rows: list[tuple[str, str, int]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            continue
        name, expression, priority = item
        if not isinstance(name, str) or not isinstance(expression, str):
            continue
        try:
            rows.append((name, expression, int(priority)))
        except (TypeError, ValueError):
            continue
    return tuple(rows)


def coerce_field_transform_stage(value: Any) -> FieldTransformStage | None:
    """Coerce one field-transform stage from YAML."""
    if not isinstance(value, dict):
        return None
    kind = str(value.get("kind", "")).strip()
    if not kind:
        return None
    try:
        window = int(value.get("window", 0) or 0)
    except (TypeError, ValueError):
        window = 0
    std_value = value.get("std")
    try:
        std = float(std_value) if std_value is not None else None
    except (TypeError, ValueError):
        std = None
    return FieldTransformStage(kind=kind, window=window, std=std)


def coerce_field_transform_spec(value: Any) -> FieldTransformSpec | None:
    """Coerce a full field-transform spec from YAML."""
    if not isinstance(value, dict):
        return None
    stages_raw = value.get("stages", ())
    stages: list[FieldTransformStage] = []
    if isinstance(stages_raw, (list, tuple)):
        for item in stages_raw:
            stage = coerce_field_transform_stage(item)
            if stage is not None:
                stages.append(stage)
    try:
        backfill_window = int(value.get("backfill_window", 0) or 0)
    except (TypeError, ValueError):
        backfill_window = 0
    winsorize_value = value.get("winsorize_std")
    try:
        winsorize_std = float(winsorize_value) if winsorize_value is not None else None
    except (TypeError, ValueError):
        winsorize_std = None
    return FieldTransformSpec(
        stages=tuple(stages),
        backfill_window=backfill_window,
        winsorize_std=winsorize_std,
    )


def coerce_feedback_phase_policy(value: Any) -> FeedbackPhasePolicy | None:
    """Coerce one feedback phase policy from YAML."""
    if not isinstance(value, dict):
        return None
    preferred_raw = value.get("preferred_template_stages", ())
    preferred_template_stages = ()
    if isinstance(preferred_raw, (list, tuple)):
        preferred_template_stages = tuple(str(item) for item in preferred_raw if str(item).strip())
    try:
        min_attempted_templates = int(value.get("min_attempted_templates", 0) or 0)
    except (TypeError, ValueError):
        min_attempted_templates = 0
    try:
        min_best_score = float(value.get("min_best_score", STATS_DEFAULT_SCORE))
    except (TypeError, ValueError):
        min_best_score = STATS_DEFAULT_SCORE
    try:
        settings_variant_budget = int(
            value.get("settings_variant_budget", DEFAULT_SETTINGS_VARIANT_BUDGET)
            or DEFAULT_SETTINGS_VARIANT_BUDGET
        )
    except (TypeError, ValueError):
        settings_variant_budget = DEFAULT_SETTINGS_VARIANT_BUDGET
    return FeedbackPhasePolicy(
        min_attempted_templates=min_attempted_templates,
        min_best_score=min_best_score,
        settings_variant_budget=settings_variant_budget,
        enable_template_pruning=bool(value.get("enable_template_pruning", False)),
        enable_resimulation_mutations=bool(value.get("enable_resimulation_mutations", False)),
        preferred_template_stages=preferred_template_stages,
    )


def coerce_feedback_loop_policy(value: Any) -> FeedbackLoopPolicy | None:
    """Coerce the feedback loop policy from YAML."""
    if not isinstance(value, dict):
        return None
    generate = coerce_feedback_phase_policy(value.get("generate"))
    prune = coerce_feedback_phase_policy(value.get("prune"))
    resimulate = coerce_feedback_phase_policy(value.get("resimulate"))
    if generate is None and prune is None and resimulate is None:
        return None
    return FeedbackLoopPolicy(
        generate=generate or FeedbackPhasePolicy(),
        prune=prune or FeedbackPhasePolicy(),
        resimulate=resimulate or FeedbackPhasePolicy(),
    )


def resolve_priority_tiers(merged: dict[str, Any]) -> dict[str, int]:
    """Resolve __default__.priority_tiers for @tier_name references."""
    tiers_raw = merged.get("priority_tiers", {})
    if not isinstance(tiers_raw, dict):
        return {}
    resolved: dict[str, int] = {}
    for name, value in tiers_raw.items():
        try:
            resolved[str(name)] = int(value)
        except (TypeError, ValueError):
            continue
    return resolved


def resolve_tier_value(raw_value: Any, tiers: dict[str, int]) -> int | None:
    """Resolve @tier_name references or plain numeric values to int."""
    if isinstance(raw_value, str) and raw_value.startswith("@"):
        tier_name = raw_value[1:]
        return tiers.get(tier_name)
    if isinstance(raw_value, (int, float)):
        return int(raw_value)
    return None


def coerce_template_prefix_penalties(
    value: Any,
    tiers: dict[str, int] | None = None,
) -> dict[tuple[str, ...], int]:
    """Coerce template prefix penalties from dict or legacy list[dict] YAML."""
    tiers = tiers or {}
    coerced_prefix_penalties: dict[tuple[str, ...], int] = {}
    if isinstance(value, dict):
        iterable = value.items()
    elif isinstance(value, (list, tuple)):
        iterable = (
            (item.get("prefixes", ()), item.get("penalty"))
            for item in value
            if isinstance(item, dict)
        )
    else:
        return coerced_prefix_penalties

    for prefixes, score in iterable:
        if isinstance(prefixes, str):
            parsed_prefixes = tuple(part.strip() for part in prefixes.split("|") if part.strip())
        elif isinstance(prefixes, (list, tuple)):
            parsed_prefixes = tuple(str(part).strip() for part in prefixes if str(part).strip())
        else:
            continue
        if not parsed_prefixes:
            continue
        resolved = resolve_tier_value(score, tiers)
        if resolved is not None:
            coerced_prefix_penalties[parsed_prefixes] = resolved
    return coerced_prefix_penalties
