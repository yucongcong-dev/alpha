"""CLI configuration precedence and runtime-mode normalization."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from ..config._constants_thresholds import (
    FULL_RUN_MAX_NEW_SIMULATIONS,
    SMOKE_TEST_MAX_PENDING_CYCLES,
    SMOKE_TEST_MAX_QUEUE_SECONDS,
)
from ..config.profiles import get_dataset_profile
from ..config.settings_spec import dataset_profile_keys, yaml_default_settings
from ..config.simulation_dates import resolve_simulation_dates
from ..config.strategy_profiles import (
    get_strategy_profile_runtime_defaults,
    normalize_strategy_profile,
)
from ..config.yaml import get_yaml_config, set_active_config_path
from ..config.yaml_sources import validate_explicit_yaml_file
from ..models.runtime_config import RunMode

DATASET_PROFILE_KEYS = dataset_profile_keys()
PARSER_DEFAULT_SOURCE = "parser_default"
CLI_SOURCE = "cli"
GLOBAL_YAML_SOURCE = "global_yaml"
DATE_RESOLUTION_SOURCE = "date_resolution"
DATASET_PROFILE_SOURCE = "dataset_profile"
STRATEGY_PROFILE_SOURCE = "strategy_profile"
RUN_MODE_SOURCE = "run_mode"


@dataclass(frozen=True, slots=True)
class ResolvedConfigLayer:
    """One named layer of configuration values applied during CLI resolution."""

    source: str
    values: dict[str, object]


@dataclass(frozen=True, slots=True)
class ConfigLayerDefinition:
    """声明一个按固定优先级执行的配置层。"""

    source: str
    resolve: Callable[[], ResolvedConfigLayer]


_SENSITIVE_CONFIG_KEYS = frozenset({"password", "authorization", "token", "secret"})


@dataclass(slots=True)
class _ConfigResolutionState:
    """Mutable resolution state used only inside the CLI boundary."""

    values: dict[str, object]
    sources: dict[str, str]
    source_chains: dict[str, list[str]]

    @classmethod
    def from_args(
        cls,
        args: argparse.Namespace,
        *,
        explicit_cli_keys: set[str],
    ) -> _ConfigResolutionState:
        values = {key: value for key, value in vars(args).items() if not key.startswith("_")}
        sources = dict.fromkeys(values, PARSER_DEFAULT_SOURCE)
        source_chains = {key: [PARSER_DEFAULT_SOURCE] for key in values}
        state = cls(values=values, sources=sources, source_chains=source_chains)
        state.apply(
            ResolvedConfigLayer(
                source=CLI_SOURCE,
                values={key: values[key] for key in explicit_cli_keys if key in values},
            )
        )
        return state

    def apply(self, layer: ResolvedConfigLayer) -> None:
        """Apply a resolved layer and retain its provenance without storing values twice."""
        for key, value in layer.values.items():
            if key not in self.values:
                continue
            self.values[key] = value
            chain = self.source_chains[key]
            if not chain or chain[-1] != layer.source:
                chain.append(layer.source)
            if self.sources.get(key) != CLI_SOURCE or layer.source == CLI_SOURCE:
                self.sources[key] = layer.source


@dataclass(frozen=True, slots=True)
class ResolvedCliConfig:
    """One completed CLI snapshot, its final sources, and full source chains."""

    values: dict[str, object]
    sources: dict[str, str]
    source_chains: dict[str, tuple[str, ...]]
    report: dict[str, dict[str, object]]

    def apply_to(self, args: argparse.Namespace) -> argparse.Namespace:
        """Apply the completed snapshot once at the CLI boundary."""
        for key, value in self.values.items():
            setattr(args, key, value)
        args._config_sources = dict(self.sources)
        args._config_source_chains = dict(self.source_chains)
        args._config_report = dict(self.report)
        return args


def resolve_cli_args(
    args: argparse.Namespace,
    *,
    parser_defaults: dict[str, object],
    explicit_cli_keys: set[str],
) -> argparse.Namespace:
    """Resolve every configuration layer once, then apply one final snapshot."""
    if "config" in explicit_cli_keys:
        validate_explicit_yaml_file(args.config)
    set_active_config_path(args.config if args.config else "")
    resolved = _resolve_settings(
        args,
        yaml_config=get_yaml_config(),
        parser_defaults=parser_defaults,
        explicit_cli_keys=explicit_cli_keys,
    )
    args._explicit_cli_keys = frozenset(explicit_cli_keys)
    return resolved.apply_to(args)


def _resolve_settings(
    args: argparse.Namespace,
    *,
    yaml_config: dict[str, object] | None,
    parser_defaults: dict[str, object],
    explicit_cli_keys: set[str],
) -> ResolvedCliConfig:
    """Resolve the declared configuration layer pipeline in precedence order."""
    state = _ConfigResolutionState.from_args(args, explicit_cli_keys=explicit_cli_keys)
    layers = (
        ConfigLayerDefinition(
            GLOBAL_YAML_SOURCE,
            lambda: _global_yaml_layer(state, yaml_config, explicit_cli_keys),
        ),
        ConfigLayerDefinition(
            DATE_RESOLUTION_SOURCE,
            lambda: _date_resolution_layer(state, yaml_config),
        ),
        ConfigLayerDefinition(
            DATASET_PROFILE_SOURCE,
            lambda: _dataset_profile_layer(
                state,
                yaml_config,
                parser_defaults,
                explicit_cli_keys,
            ),
        ),
        ConfigLayerDefinition(
            STRATEGY_PROFILE_SOURCE,
            lambda: _strategy_profile_layer(state, yaml_config, explicit_cli_keys),
        ),
        ConfigLayerDefinition(
            RUN_MODE_SOURCE,
            lambda: _run_mode_layer(state, explicit_cli_keys),
        ),
    )
    for layer in layers:
        resolved_layer = layer.resolve()
        if resolved_layer.source != layer.source:
            raise ValueError(
                f"configuration layer source mismatch: {layer.source!r} != "
                f"{resolved_layer.source!r}"
            )
        state.apply(resolved_layer)
    source_chains = {key: tuple(chain) for key, chain in state.source_chains.items()}
    return ResolvedCliConfig(
        values=state.values,
        sources=state.sources,
        source_chains=source_chains,
        report=build_config_source_report(state.values, state.sources, source_chains),
    )


def build_config_source_report(
    values: dict[str, object],
    sources: dict[str, str],
    source_chains: dict[str, tuple[str, ...]],
) -> dict[str, dict[str, object]]:
    """Build a final-value/provenance report with sensitive values redacted."""
    report: dict[str, dict[str, object]] = {}
    for key, value in values.items():
        display_value = "<redacted>" if key.casefold() in _SENSITIVE_CONFIG_KEYS else value
        report[key] = {
            "value": display_value,
            "source": sources.get(key, PARSER_DEFAULT_SOURCE),
            "chain": list(source_chains.get(key, ())),
        }
    return report


def _global_yaml_layer(
    state: _ConfigResolutionState,
    yaml_config: dict[str, object] | None,
    explicit_cli_keys: set[str],
) -> ResolvedConfigLayer:
    """Return global YAML values below every explicit CLI value."""
    global_config = (yaml_config or {}).get("global", {})
    if not isinstance(global_config, dict):
        return ResolvedConfigLayer(GLOBAL_YAML_SOURCE, {})

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

    updates: dict[str, object] = {}
    for spec in yaml_default_settings():
        if spec.dest in explicit_cli_keys or spec.yaml is None:
            continue
        value = lookup(spec.yaml)
        if value is not missing and spec.dest in state.values:
            updates[spec.dest] = value
    return ResolvedConfigLayer(GLOBAL_YAML_SOURCE, updates)


def _date_resolution_layer(
    state: _ConfigResolutionState,
    yaml_config: dict[str, object] | None,
) -> ResolvedConfigLayer:
    """Return normalized start/end dates after global simulation values are selected."""
    global_config = (yaml_config or {}).get("global", {})
    simulation_config = (
        global_config.get("simulation", {}) if isinstance(global_config, dict) else None
    )
    start_date, end_date = resolve_simulation_dates(
        start_date=_optional_string(state.values.get("start_date")),
        end_date=_optional_string(state.values.get("end_date")),
        simulation_config=simulation_config if isinstance(simulation_config, dict) else None,
    )
    updates: dict[str, object] = {
        key: value
        for key, value in (("start_date", start_date), ("end_date", end_date))
        if state.values.get(key) != value
    }
    return ResolvedConfigLayer(DATE_RESOLUTION_SOURCE, updates)


def _dataset_profile_layer(
    state: _ConfigResolutionState,
    yaml_config: dict[str, object] | None,
    parser_defaults: dict[str, object],
    explicit_cli_keys: set[str],
) -> ResolvedConfigLayer:
    """Return dataset-specific values that outrank global YAML values."""
    dataset_id = str(state.values.get("dataset_id", "") or "")
    profile_dict = cast(dict[str, object], get_dataset_profile(dataset_id, yaml_config))
    yaml_profiles = (yaml_config or {}).get("dataset_profiles", {})
    yaml_dataset_cfg = yaml_profiles.get(dataset_id, {}) if isinstance(yaml_profiles, dict) else {}
    updates: dict[str, object] = {}
    for key in DATASET_PROFILE_KEYS:
        if key in explicit_cli_keys or key not in profile_dict or key not in state.values:
            continue
        if key in yaml_dataset_cfg or state.values.get(key) == parser_defaults.get(key):
            updates[key] = profile_dict[key]
    return ResolvedConfigLayer(DATASET_PROFILE_SOURCE, updates)


def _strategy_profile_layer(
    state: _ConfigResolutionState,
    yaml_config: dict[str, object] | None,
    explicit_cli_keys: set[str],
) -> ResolvedConfigLayer:
    """Return strategy-profile defaults below explicit CLI values."""
    profile = normalize_strategy_profile(state.values.get("strategy_profile", "explore"))
    updates: dict[str, object] = {}
    if state.values.get("strategy_profile") != profile:
        updates["strategy_profile"] = profile
    updates.update(
        {
            key: value
            for key, value in get_strategy_profile_runtime_defaults(profile, yaml_config).items()
            if key not in explicit_cli_keys and key in state.values
        }
    )
    return ResolvedConfigLayer(STRATEGY_PROFILE_SOURCE, updates)


def _run_mode_layer(
    state: _ConfigResolutionState,
    explicit_cli_keys: set[str],
) -> ResolvedConfigLayer:
    """Return mode defaults after rejecting contradictory explicit options."""
    run_mode = RunMode.from_value(_resolve_run_mode(state.values))
    updates: dict[str, object] = {"run_mode": run_mode}

    if run_mode is RunMode.SMOKE:
        _reject_mode_conflicts(state.values, explicit_cli_keys, mode="smoke")
        _add_mode_defaults(
            updates,
            explicit_cli_keys,
            limit=1,
            max_templates_per_field=1,
            max_concurrent_simulations=1,
            max_concurrent_creates=1,
            simulation_max_pending_cycles=SMOKE_TEST_MAX_PENDING_CYCLES,
            simulation_max_queue_seconds=SMOKE_TEST_MAX_QUEUE_SECONDS,
        )
    elif run_mode is RunMode.FULL:
        _reject_mode_conflicts(state.values, explicit_cli_keys, mode="full")
        _add_mode_defaults(
            updates,
            explicit_cli_keys,
            limit=0,
            offset=0,
            max_templates_per_field=0,
            max_templates_per_family=0,
            top_fields_by_feedback=0,
        )
        if (
            "max_new_simulations" not in explicit_cli_keys
            and _as_number(state.values.get("max_new_simulations", 0)) <= 0
        ):
            updates["max_new_simulations"] = FULL_RUN_MAX_NEW_SIMULATIONS
    return ResolvedConfigLayer(RUN_MODE_SOURCE, updates)


def _resolve_run_mode(values: dict[str, object]) -> str:
    """Resolve the canonical mode from CLI or YAML configuration."""
    return str(values.get("run_mode", "normal") or "normal")


def _add_mode_defaults(
    updates: dict[str, object],
    explicit_cli_keys: set[str],
    **defaults: object,
) -> None:
    """Add mode-owned defaults only for values not explicitly supplied by the user."""
    updates.update({key: value for key, value in defaults.items() if key not in explicit_cli_keys})


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
