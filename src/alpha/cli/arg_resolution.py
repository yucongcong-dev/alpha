"""CLI argument precedence and runtime-mode normalization."""

from __future__ import annotations

import argparse

from ..config.constants import SMOKE_TEST_MAX_PENDING_CYCLES, SMOKE_TEST_MAX_QUEUE_SECONDS
from ..config.defaults import apply_yaml_global_defaults
from ..config.profiles import get_dataset_profile
from ..config.yaml import get_yaml_config

DATASET_PROFILE_KEYS = (
    "min_request_interval",
    "sleep_between_fields",
    "max_concurrent_simulations",
    "max_concurrent_creates",
    "max_templates_per_field",
    "field_template_batch_size",
    "simulation_max_wait_seconds",
    "simulation_max_queue_seconds",
    "queue_busy_cooldown_seconds",
    "template_disable_after",
)


def resolve_cli_args(
    args: argparse.Namespace,
    *,
    parser_defaults: dict[str, object],
    explicit_cli_keys: set[str],
) -> argparse.Namespace:
    """Apply YAML defaults, dataset profile overrides, and run-mode rewrites."""
    yaml_config = get_yaml_config(args.config if args.config else "")
    apply_yaml_global_defaults(args, yaml_config, explicit_cli_keys)
    apply_dataset_profile_defaults(
        args,
        yaml_config=yaml_config,
        parser_defaults=parser_defaults,
        explicit_cli_keys=explicit_cli_keys,
    )
    apply_run_mode_overrides(args)
    return args


def apply_dataset_profile_defaults(
    args: argparse.Namespace,
    *,
    yaml_config: dict[str, object] | None,
    parser_defaults: dict[str, object],
    explicit_cli_keys: set[str],
) -> None:
    """Apply dataset profile defaults without overriding explicit CLI input."""
    profile = get_dataset_profile(args.dataset_id, yaml_config)
    yaml_profiles = (yaml_config or {}).get("dataset_profiles", {})
    yaml_dataset_cfg = yaml_profiles.get(args.dataset_id, {}) if isinstance(yaml_profiles, dict) else {}

    for key in DATASET_PROFILE_KEYS:
        if key in explicit_cli_keys or key not in profile:
            continue
        if key in yaml_dataset_cfg:
            setattr(args, key, profile[key])
            continue
        if getattr(args, key, None) == parser_defaults.get(key):
            setattr(args, key, profile[key])


def apply_run_mode_overrides(args: argparse.Namespace) -> None:
    """Normalize run-mode flags into concrete concurrency and search limits."""
    if args.smoke_test:
        args.limit = 1
        args.max_templates_per_field = 1
        args.max_concurrent_simulations = 1
        args.max_concurrent_creates = 1
        args.simulation_max_pending_cycles = min(args.simulation_max_pending_cycles, SMOKE_TEST_MAX_PENDING_CYCLES)
        args.simulation_max_queue_seconds = min(args.simulation_max_queue_seconds, SMOKE_TEST_MAX_QUEUE_SECONDS)
        return
    if args.full_run:
        args.limit = 0
        args.max_templates_per_field = 0
