"""CLI argument precedence and runtime-mode normalization."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import cast

from ..config._constants_thresholds import (
    FULL_RUN_MAX_TOTAL_SIMULATIONS,
    SMOKE_TEST_MAX_PENDING_CYCLES,
    SMOKE_TEST_MAX_QUEUE_SECONDS,
)
from ..config.profiles import get_dataset_profile
from ..config.settings_spec import (
    dataset_profile_keys,
    yaml_default_settings,
)
from ..config.simulation_dates import resolve_simulation_dates
from ..config.strategy_profiles import (
    get_strategy_profile_runtime_defaults,
    normalize_strategy_profile,
)
from ..config.yaml import get_yaml_config, set_active_config_path
from ..config.yaml_sources import validate_explicit_yaml_file

DATASET_PROFILE_KEYS = dataset_profile_keys()


@dataclass(frozen=True, slots=True)
class ResolvedCliConfig:
    """One resolved CLI snapshot and the source chosen for each setting."""

    values: dict[str, object]
    sources: dict[str, str]

    def apply_to(self, args: argparse.Namespace) -> argparse.Namespace:
        """Apply the completed snapshot once at the CLI boundary."""
        for key, value in self.values.items():
            setattr(args, key, value)
        args._config_sources = dict(self.sources)
        return args


def resolve_cli_args(
    args: argparse.Namespace,
    *,
    parser_defaults: dict[str, object],
    explicit_cli_keys: set[str],
    explicit_cli_options: set[str] | None = None,
) -> argparse.Namespace:
    """Resolve all configuration layers once, then apply one final snapshot."""
    if "config" in explicit_cli_keys:
        validate_explicit_yaml_file(args.config)
    set_active_config_path(args.config if args.config else "")
    yaml_config = get_yaml_config()
    resolved = _resolve_settings(
        args,
        yaml_config=yaml_config,
        parser_defaults=parser_defaults,
        explicit_cli_keys=explicit_cli_keys,
        explicit_cli_options=explicit_cli_options,
    )
    args._explicit_cli_keys = frozenset(explicit_cli_keys)
    return resolved.apply_to(args)


def _resolve_settings(
    args: argparse.Namespace,
    *,
    yaml_config: dict[str, object] | None,
    parser_defaults: dict[str, object],
    explicit_cli_keys: set[str],
    explicit_cli_options: set[str] | None,
) -> ResolvedCliConfig:
    """Resolve YAML, dataset, strategy, and mode layers in one pass."""
    values = {key: value for key, value in vars(args).items() if not key.startswith("_")}
    sources = {key: ("cli" if key in explicit_cli_keys else "parser_default") for key in values}

    _resolve_global_yaml(values, sources, yaml_config, explicit_cli_keys)
    _resolve_simulation_dates(values, sources, yaml_config)
    _resolve_dataset_profile(
        values,
        sources,
        yaml_config=yaml_config,
        parser_defaults=parser_defaults,
        explicit_cli_keys=explicit_cli_keys,
    )
    _resolve_strategy_profile(values, sources, yaml_config, explicit_cli_keys)
    _resolve_run_mode(values, sources, explicit_cli_keys, explicit_cli_options)
    return ResolvedCliConfig(values=values, sources=sources)


def _resolve_global_yaml(
    values: dict[str, object],
    sources: dict[str, str],
    yaml_config: dict[str, object] | None,
    explicit_cli_keys: set[str],
) -> None:
    """Apply global YAML values below every explicit CLI value."""
    global_config = (yaml_config or {}).get("global", {})
    if not isinstance(global_config, dict):
        return

    missing = object()

    def lookup(path: tuple[str, ...]) -> object:
        section: object = global_config
        for part in path[:-1]:
            if not isinstance(section, dict):
                return missing
            section = section.get(part, {})
        if not isinstance(section, dict) or path[-1] not in section:
            return missing
        return section[path[-1]]

    for spec in yaml_default_settings():
        if spec.dest in explicit_cli_keys or spec.yaml is None:
            continue
        value = lookup(spec.yaml)
        if value is missing:
            for alias in spec.yaml_aliases:
                value = lookup(alias)
                if value is not missing:
                    break
        if value is not missing and spec.dest in values:
            values[spec.dest] = value
            sources[spec.dest] = "global_yaml"


def _resolve_simulation_dates(
    values: dict[str, object],
    sources: dict[str, str],
    yaml_config: dict[str, object] | None,
) -> None:
    """Resolve date defaults after global simulation values are selected."""
    global_config = (yaml_config or {}).get("global", {})
    simulation_config = (
        global_config.get("simulation", {}) if isinstance(global_config, dict) else {}
    )
    if not isinstance(simulation_config, dict):
        simulation_config = None
    start_date, end_date = resolve_simulation_dates(
        start_date=_optional_string(values.get("start_date")),
        end_date=_optional_string(values.get("end_date")),
        simulation_config=simulation_config,
    )
    for key, value in (("start_date", start_date), ("end_date", end_date)):
        if values.get(key) != value:
            values[key] = value
            sources[key] = "date_resolution"


def _resolve_dataset_profile(
    values: dict[str, object],
    sources: dict[str, str],
    *,
    yaml_config: dict[str, object] | None,
    parser_defaults: dict[str, object],
    explicit_cli_keys: set[str],
) -> None:
    """Apply dataset values that are more specific than global YAML."""
    dataset_id = str(values.get("dataset_id", "") or "")
    profile = get_dataset_profile(dataset_id, yaml_config)
    profile_dict = cast(dict[str, object], profile)
    yaml_profiles = (yaml_config or {}).get("dataset_profiles", {})
    yaml_dataset_cfg = yaml_profiles.get(dataset_id, {}) if isinstance(yaml_profiles, dict) else {}

    for key in DATASET_PROFILE_KEYS:
        if key in explicit_cli_keys or key not in profile_dict or key not in values:
            continue
        if key in yaml_dataset_cfg:
            values[key] = profile_dict[key]
            sources[key] = "dataset_profile"
            continue
        if values.get(key) == parser_defaults.get(key):
            values[key] = profile_dict[key]
            sources[key] = "dataset_profile"


def _resolve_strategy_profile(
    values: dict[str, object],
    sources: dict[str, str],
    yaml_config: dict[str, object] | None,
    explicit_cli_keys: set[str],
) -> None:
    """Apply strategy defaults below explicit CLI values."""
    raw_profile = values.get("strategy_profile", "explore")
    profile = normalize_strategy_profile(raw_profile)
    if values.get("strategy_profile") != profile:
        values["strategy_profile"] = profile
        sources["strategy_profile"] = "strategy_profile"
    defaults = get_strategy_profile_runtime_defaults(profile, yaml_config)
    for key, value in defaults.items():
        if key in explicit_cli_keys or key not in values:
            continue
        values[key] = value
        sources[key] = "strategy_profile"


def _resolve_run_mode(
    values: dict[str, object],
    sources: dict[str, str],
    explicit_cli_keys: set[str],
    explicit_cli_options: set[str] | None,
) -> None:
    """Resolve run mode and fill only values not explicitly set by the user."""
    options = explicit_cli_options or set()
    if "--smoke-test" in options and "--no-smoke-test" in options:
        raise ValueError("--smoke-test 与 --no-smoke-test 不能同时使用；请改用 --run-mode")
    if "--full-run" in options and "--no-full-run" in options:
        raise ValueError("--full-run 与 --no-full-run 不能同时使用；请改用 --run-mode")

    run_mode = str(values.get("run_mode", "") or "")
    if not run_mode:
        if "--smoke-test" in options:
            run_mode = "smoke"
        elif "--full-run" in options:
            run_mode = "full"
        elif "--no-smoke-test" in options or "--no-full-run" in options:
            run_mode = "normal"
        elif bool(values.get("smoke_test", False)):
            run_mode = "smoke"
        elif bool(values.get("full_run", False)):
            run_mode = "full"
        else:
            run_mode = "normal"
    values["run_mode"] = run_mode
    sources["run_mode"] = "cli" if "run_mode" in explicit_cli_keys else "run_mode"
    for key, value in (("smoke_test", run_mode == "smoke"), ("full_run", run_mode == "full")):
        if key not in explicit_cli_keys:
            values[key] = value
            sources[key] = "run_mode"

    if run_mode == "smoke":
        _reject_mode_conflicts(
            values,
            explicit_cli_keys,
            mode="smoke",
        )
        _set_mode_default(values, sources, explicit_cli_keys, "limit", 1)
        _set_mode_default(values, sources, explicit_cli_keys, "max_templates_per_field", 1)
        _set_mode_default(values, sources, explicit_cli_keys, "max_concurrent_simulations", 1)
        _set_mode_default(values, sources, explicit_cli_keys, "max_concurrent_creates", 1)
        _set_mode_default(
            values,
            sources,
            explicit_cli_keys,
            "simulation_max_pending_cycles",
            SMOKE_TEST_MAX_PENDING_CYCLES,
        )
        _set_mode_default(
            values,
            sources,
            explicit_cli_keys,
            "simulation_max_queue_seconds",
            SMOKE_TEST_MAX_QUEUE_SECONDS,
        )
        return

    if run_mode == "full":
        _reject_mode_conflicts(
            values,
            explicit_cli_keys,
            mode="full",
        )
        for key in (
            "limit",
            "offset",
            "max_templates_per_field",
            "max_templates_per_family",
            "top_fields_by_feedback",
        ):
            _set_mode_default(values, sources, explicit_cli_keys, key, 0)
        if (
            "max_total_simulations" not in explicit_cli_keys
            and _as_number(values.get("max_total_simulations", 0)) <= 0
        ):
            _set_mode_default(
                values,
                sources,
                explicit_cli_keys,
                "max_total_simulations",
                FULL_RUN_MAX_TOTAL_SIMULATIONS,
            )


def _set_mode_default(
    values: dict[str, object],
    sources: dict[str, str],
    explicit_cli_keys: set[str],
    key: str,
    value: object,
) -> None:
    """Set a mode default only when the CLI did not explicitly provide it."""
    if key not in explicit_cli_keys:
        values[key] = value
        sources[key] = "run_mode"


def _reject_mode_conflicts(
    values: dict[str, object],
    explicit_cli_keys: set[str],
    *,
    mode: str,
) -> None:
    """Reject explicit values that contradict a mode's hard safety contract."""
    if mode == "smoke":
        exact_values = {
            "limit": 1,
            "max_templates_per_field": 1,
            "max_concurrent_simulations": 1,
            "max_concurrent_creates": 1,
        }
        conflicts = [
            key
            for key, expected in exact_values.items()
            if key in explicit_cli_keys and values.get(key) != expected
        ]
        bounded_values = {
            "simulation_max_pending_cycles": SMOKE_TEST_MAX_PENDING_CYCLES,
            "simulation_max_queue_seconds": SMOKE_TEST_MAX_QUEUE_SECONDS,
        }
        conflicts.extend(
            key
            for key, maximum in bounded_values.items()
            if key in explicit_cli_keys and _as_number(values.get(key, 0)) > maximum
        )
    elif mode == "full":
        conflicts = [
            key
            for key in (
                "limit",
                "offset",
                "max_templates_per_field",
                "max_templates_per_family",
                "top_fields_by_feedback",
            )
            if key in explicit_cli_keys and values.get(key) != 0
        ]
    else:
        return
    if conflicts:
        joined = ", ".join(sorted(conflicts))
        raise ValueError(
            f"--run-mode {mode} conflicts with explicit options: {joined}; "
            "remove those options or use --run-mode normal"
        )


def _optional_string(value: object) -> str | None:
    """Normalize a parser value to the date resolver's narrow input type."""
    return value if isinstance(value, str) else None


def _as_number(value: object) -> float:
    """Normalize a resolved numeric value for mode-bound checks."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value or 0))
    except (TypeError, ValueError):
        return 0.0
