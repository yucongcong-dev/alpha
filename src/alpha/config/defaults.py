"""
YAML global 默认值合并。

本模块负责把合并 YAML 配置中的 global 配置应用到 argparse namespace。
"""

from __future__ import annotations

from typing import Any, Protocol


class DefaultsTarget(Protocol):
    """支持按属性读写的配置承载对象。"""

    def __getattr__(self, name: str) -> object: ...

    def __setattr__(self, name: str, value: object) -> None: ...


def _assign_if_supported(
    target: DefaultsTarget,
    key: str,
    value: object,
    explicit_cli_keys: set[str],
) -> None:
    """仅在目标对象支持该属性且 CLI 未显式传参时写入值。"""
    if key in explicit_cli_keys or not hasattr(target, key):
        return
    setattr(target, key, value)


def apply_yaml_global_defaults(
    args: DefaultsTarget,
    yaml_config: dict[str, Any] | None = None,
    explicit_cli_keys: set[str] | None = None,
) -> None:
    """将 YAML global 默认值应用到 argparse namespace 上（CLI 未显式传参时）。"""
    if not yaml_config:
        return
    explicit_cli_keys = explicit_cli_keys or set()

    global_cfg = yaml_config.get("global", {})
    if not isinstance(global_cfg, dict):
        return

    sim_key_map = {
        "instrumentType": "instrument_type",
        "unitHandling": "unit_handling",
        "nanHandling": "nan_handling",
        "maxTrade": "max_trade",
        "startDate": "start_date",
        "endDate": "end_date",
    }
    sim_section = global_cfg.get("simulation", {})
    if isinstance(sim_section, dict):
        for yaml_key, arg_key in sim_key_map.items():
            if yaml_key in sim_section:
                _assign_if_supported(args, arg_key, sim_section[yaml_key], explicit_cli_keys)

    _merge_section(args, sim_section, {
        "region", "universe", "delay", "decay", "neutralization",
        "truncation", "pasteurization", "language",
    }, explicit_cli_keys)

    _merge_section(args, global_cfg.get("limits", {}), {
        "limit", "offset", "page_size", "sleep_between_fields",
        "max_templates_per_field", "max_templates_per_family", "field_template_batch_size",
        "legacy_similarity_penalty", "disable_legacy_after",
    }, explicit_cli_keys)

    _merge_section(args, global_cfg.get("concurrency", {}), {
        "max_concurrent_simulations",
        "max_concurrent_creates",
    }, explicit_cli_keys)

    _merge_section(args, global_cfg.get("retries", {}), {
        "simulation_create_retries", "simulation_poll_retries",
        "simulation_max_polls", "simulation_max_wait_seconds",
        "simulation_max_pending_cycles", "simulation_max_queue_seconds",
        "queue_busy_cooldown_seconds", "field_queue_busy_skip_after",
        "check_submit_retries",
        "rate_limit_max_retries", "login_retries", "min_request_interval",
    }, explicit_cli_keys)

    _merge_section(args, global_cfg.get("filters", {}), {
        "template_disable_after", "top_fields_by_feedback",
        "stop_after_submittable",
    }, explicit_cli_keys)

    _merge_section(args, global_cfg.get("quality", {}), {
        "min_sharpe", "min_fitness", "min_turnover",
        "max_turnover", "max_weight",
    }, explicit_cli_keys)

    _merge_section(args, global_cfg.get("expression", {}), {
        "backfill_window",
    }, explicit_cli_keys)

    _merge_section(args, global_cfg.get("runtime", {}), {
        "auto_update_blacklist", "smoke_test", "dry_run_plan", "full_run",
        "verbose", "quiet",
    }, explicit_cli_keys)


def _merge_section(
    args: DefaultsTarget,
    section: Any,
    keys: set[str],
    explicit_cli_keys: set[str] | None = None,
) -> None:
    """将 YAML section 中的值合并到 args（仅当 key 在 section 中存在时）。"""
    if not isinstance(section, dict):
        return
    explicit_cli_keys = explicit_cli_keys or set()
    for key in keys:
        if key in section:
            _assign_if_supported(args, key, section[key], explicit_cli_keys)
