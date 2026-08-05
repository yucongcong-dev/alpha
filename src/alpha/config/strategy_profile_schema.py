"""Static schema for named strategy profiles."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from .models import DatasetExpressionPolicy

STRATEGY_PROFILE_CHOICES = ("explore", "refine", "submit-focused")
STRATEGY_PROFILE_SCHEMA_KEYS = {
    "purpose",
    "primary_goal",
    "tuning_keys",
    "runtime_defaults",
    "notes",
}

_INT = "integer"
_NUMBER = "number"
_BOOL = "boolean"
_STRING = "string"

STRATEGY_PROFILE_RUNTIME_DEFAULT_TYPES: dict[str, dict[str, str]] = {
    "limits": {
        "limit": _INT,
        "offset": _INT,
        "page_size": _INT,
        "sleep_between_fields": _NUMBER,
        "max_templates_per_field": _INT,
        "max_templates_per_family": _INT,
        "max_total_simulations": _INT,
        "field_template_batch_size": _INT,
        "legacy_similarity_penalty": _INT,
    },
    "concurrency": {
        "max_concurrent_simulations": _INT,
        "max_concurrent_creates": _INT,
    },
    "filters": {
        "top_fields_by_feedback": _INT,
        "stop_after_submittable": _INT,
    },
    "quality": {
        "min_sharpe": _NUMBER,
        "min_fitness": _NUMBER,
        "min_turnover": _NUMBER,
        "max_turnover": _NUMBER,
        "max_weight": _NUMBER,
    },
    "retries": {
        "simulation_create_retries": _INT,
        "simulation_poll_retries": _INT,
        "simulation_max_polls": _INT,
        "simulation_max_wait_seconds": _NUMBER,
        "simulation_max_pending_cycles": _INT,
        "simulation_max_queue_seconds": _NUMBER,
        "queue_busy_cooldown_seconds": _NUMBER,
        "queue_busy_retry_limit": _INT,
        "check_submission_retries": _INT,
        "rate_limit_max_retries": _INT,
        "login_retries": _INT,
        "min_request_interval": _NUMBER,
    },
    "runtime": {
        "auto_update_blacklist": _BOOL,
        "smoke_test": _BOOL,
        "dry_run_plan": _BOOL,
        "full_run": _BOOL,
        "verbose": _BOOL,
        "quiet": _BOOL,
    },
}

STRATEGY_PROFILE_RUNTIME_DEFAULT_CHOICES: dict[tuple[str, str], frozenset[str]] = {}

_FEEDBACK_TUNING_KEYS = {
    "feedback_mutation_highscore_threshold",
    "feedback_template_min_priority",
    "expr_nearpass_boost_threshold",
    "expr_iter_boost_threshold",
    "expr_fail_penalty_threshold",
    "expr_mutation_extend_threshold",
}
_EXPRESSION_POLICY_TUNING_KEYS = {
    item.name
    for item in fields(DatasetExpressionPolicy)
    if item.name not in {"dataset_id", "policy_version"}
}
_DATASET_PROFILE_TUNING_KEYS = {
    "min_request_interval",
    "sleep_between_fields",
    "max_concurrent_simulations",
    "max_concurrent_creates",
    "max_templates_per_field",
    "field_template_batch_size",
    "simulation_max_wait_seconds",
    "simulation_max_queue_seconds",
    "queue_busy_cooldown_seconds",
    "default_preset",
    "paused",
}

STRATEGY_PROFILE_TUNING_KEYS: dict[str, set[str]] = {
    **{
        section: set(key_types)
        for section, key_types in STRATEGY_PROFILE_RUNTIME_DEFAULT_TYPES.items()
    },
    "feedback": _FEEDBACK_TUNING_KEYS,
    "expression_policies": _EXPRESSION_POLICY_TUNING_KEYS,
    "dataset_profiles": _DATASET_PROFILE_TUNING_KEYS,
}
STRATEGY_PROFILE_TUNING_SECTIONS = set(STRATEGY_PROFILE_TUNING_KEYS)


def validate_runtime_defaults(profile_name: str, value: object) -> list[str]:
    """Return schema errors for executable profile defaults."""
    prefix = f"strategy_profiles.{profile_name}.runtime_defaults"
    if not isinstance(value, dict):
        return [f"{prefix} 必须是 mapping。"]

    errors: list[str] = []
    for section_name, defaults in value.items():
        section_schema = STRATEGY_PROFILE_RUNTIME_DEFAULT_TYPES.get(section_name)
        if section_schema is None:
            errors.append(
                f"{prefix} 存在未知 section '{section_name}'，已知 section: "
                f"{sorted(STRATEGY_PROFILE_RUNTIME_DEFAULT_TYPES)}"
            )
            continue
        if not isinstance(defaults, dict):
            errors.append(f"{prefix}.{section_name} 必须是 mapping。")
            continue
        for key, item in defaults.items():
            expected = section_schema.get(key)
            item_path = f"{prefix}.{section_name}.{key}"
            if expected is None:
                errors.append(f"{item_path} 是未知 key，已知 key: {sorted(section_schema)}")
                continue
            if not _matches_type(item, expected):
                errors.append(f"{item_path} 必须是 {expected}，当前为 {type(item).__name__}。")
                continue
            choices = STRATEGY_PROFILE_RUNTIME_DEFAULT_CHOICES.get((section_name, key))
            if choices is not None and item not in choices:
                errors.append(f"{item_path} 必须是 {sorted(choices)} 之一。")
    return errors


def _matches_type(value: Any, expected: str) -> bool:
    if expected == _INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == _NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == _BOOL:
        return isinstance(value, bool)
    if expected == _STRING:
        return isinstance(value, str)
    return False
