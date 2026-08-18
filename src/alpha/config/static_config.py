"""Resolved static configuration constants.

These values were previously evaluated at import time by ``alpha.config._constants_*``
modules.  They are now assembled lazily into one frozen snapshot so that importing
this package has no YAML side effect and callers always read the currently bound
configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from ._constants_core import (
    _yaml_dict,
    _yaml_dict_tuple,
    _yaml_float,
    _yaml_int,
    _yaml_set,
    _yaml_str,
    _yaml_tuple_int2,
    _yaml_tuple_int3,
    _yaml_tuple_str_int,
)
from .yaml import get_yaml_config_version

# ---- Template fallback tables kept for wrong-shape YAML values ----
_RATIO_PARTNER_CANDIDATES_DEFAULT: dict[str, tuple[str, ...]] = {
    "debt": ("cap", "assets", "equity", "enterprise_value"),
    "debt_lt": ("cap", "assets", "equity", "enterprise_value"),
    "debt_st": ("assets", "cash", "cash_st"),
    "assets_curr": ("cash_st", "debt_st", "liabilities_curr"),
    "liabilities": ("assets", "equity", "cap", "liabilities_curr"),
    "liabilities_curr": ("assets", "equity", "cap"),
    "cash": ("assets", "debt", "liabilities"),
    "cash_st": ("assets_curr", "assets", "debt_st", "liabilities_curr"),
    "cashflow": ("assets", "enterprise_value", "debt"),
    "cashflow_op": ("cap", "assets", "debt", "enterprise_value"),
    "cashflow_invst": ("assets", "enterprise_value", "capex"),
    "cashflow_fin": ("assets", "debt", "equity"),
    "capex": ("assets", "cashflow_op", "cashflow_invst", "enterprise_value"),
    "cogs": ("assets", "cash", "enterprise_value"),
    "current_ratio": ("cash_st", "debt_st", "liabilities_curr"),
    "income": ("assets", "sales", "revenue", "enterprise_value"),
    "ebit": ("assets", "sales", "revenue", "enterprise_value"),
    "ebitda": ("assets", "sales", "revenue", "enterprise_value"),
    "revenue": ("assets", "enterprise_value"),
    "sales": ("assets", "enterprise_value"),
    "equity": ("assets", "debt", "enterprise_value"),
    "enterprise_value": ("assets", "ebitda", "ebit", "cashflow_op"),
}

_RATIO_KEYWORDS_DEFAULT: dict[str, tuple[str, ...]] = {
    "debt": ("cap", "assets", "equity", "enterprise_value", "liabilities"),
    "liabilities": ("assets", "equity", "cap", "enterprise_value"),
    "cash": ("debt", "liabilities", "assets", "enterprise_value"),
    "cash_st": ("assets_curr", "assets", "debt_st", "liabilities_curr"),
    "cashflow": ("assets", "enterprise_value", "debt"),
    "cashflow_op": ("cap", "assets", "enterprise_value", "debt"),
    "cashflow_invst": ("assets", "enterprise_value", "capex"),
    "cashflow_fin": ("assets", "debt", "equity"),
    "capex": ("cashflow_op", "assets", "enterprise_value", "cashflow_invst"),
    "cogs": ("assets", "cash", "enterprise_value"),
    "income": ("assets", "enterprise_value", "sales", "revenue"),
    "ebit": ("assets", "enterprise_value", "sales", "revenue"),
    "ebitda": ("assets", "enterprise_value", "sales", "revenue"),
    "revenue": ("assets", "enterprise_value"),
    "sales": ("assets", "enterprise_value"),
    "equity": ("assets", "enterprise_value", "debt"),
    "enterprise_value": ("assets", "ebitda", "ebit", "cashflow_op"),
    "assets": ("debt", "liabilities", "equity", "cash", "enterprise_value"),
}

_POSITIVE_RAW_FIELDS_DEFAULT: set[str] = {
    "assets",
    "assets_curr",
    "bookvalue_ps",
    "cash",
    "cash_st",
    "cashflow",
    "cashflow_op",
    "current_ratio",
    "ebit",
    "ebitda",
    "enterprise_value",
    "eps",
    "equity",
}

_NEGATIVE_RAW_FIELDS_DEFAULT: set[str] = {
    "cogs",
    "debt",
    "debt_lt",
    "debt_st",
    "liabilities",
}

_ALLOWED_EXTERNAL_RATIO_PARTNERS_DEFAULT: set[str] = {"cap"}

_DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES_DEFAULT: dict[str, int] = {
    "assets": 15,
    "equity": 15,
    "debt": 15,
    "liabilities": 15,
    "cash": 15,
    "enterprise_value": 15,
    "cap": 15,
}

_DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS_DEFAULT: tuple[tuple[int, int, int], ...] = (
    (5, 20, 176),
    (15, 40, 172),
    (10, 60, 170),
    (20, 60, 174),
    (25, 90, 168),
    (30, 120, 166),
)

_DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS_DEFAULT: tuple[tuple[str, str, int], ...] = (
    (
        "group_delta_over_std_industry_20_60",
        "group_rank(ts_delta(ts_backfill({field}, {backfill_window}), 20) / ts_std_dev(ts_backfill({field}, {backfill_window}), 60), industry)",
        166,
    ),
    (
        "group_short_long_mean_spread_subindustry_20_{backfill_window}",
        "group_rank(ts_mean(ts_backfill({field}, {backfill_window}), 20) - ts_mean(ts_backfill({field}, {backfill_window}), {backfill_window}), subindustry)",
        164,
    ),
    (
        "group_zscore_subindustry_60",
        "group_rank(ts_zscore(ts_backfill({field}, {backfill_window}), 60), subindustry)",
        161,
    ),
    (
        "rank_mean_spread_over_std_20_{backfill_window}_60",
        "rank((ts_mean(ts_backfill({field}, {backfill_window}), 20) - ts_mean(ts_backfill({field}, {backfill_window}), {backfill_window})) / ts_std_dev(ts_backfill({field}, {backfill_window}), 60))",
        158,
    ),
    (
        "rank_zscore_spread_20_{backfill_window}",
        "rank(ts_zscore(ts_backfill({field}, {backfill_window}), 20) - ts_zscore(ts_backfill({field}, {backfill_window}), {backfill_window}))",
        154,
    ),
    (
        "group_rank_delta_of_rank_20",
        "group_rank(ts_delta(rank(ts_backfill({field}, {backfill_window})), 20), subindustry)",
        150,
    ),
)

_DEFAULT_RATIO_DELTA_RANK_WINDOWS_DEFAULT: tuple[tuple[int, int], ...] = (
    (3, 188),
    (5, 184),
    (10, 176),
)

_DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS_DEFAULT: tuple[tuple[int, int, int], ...] = (
    (5, 20, 180),
    (15, 40, 176),
    (10, 60, 174),
    (20, 60, 178),
    (25, 90, 172),
    (30, 120, 170),
)

_DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS_DEFAULT: tuple[tuple[str, str, int], ...] = (
    (
        "group_ratio_zscore_{ratio_label}",
        "group_rank(ts_zscore(ts_backfill({ratio_expr}, {backfill_window}), 60), subindustry)",
        160,
    ),
    (
        "ratio_mean_spread_over_std_{ratio_label}",
        "rank((ts_mean(ts_backfill({ratio_expr}, {backfill_window}), 20) - ts_mean(ts_backfill({ratio_expr}, {backfill_window}), {backfill_window})) / ts_std_dev(ts_backfill({ratio_expr}, {backfill_window}), 60))",
        156,
    ),
    (
        "ratio_zscore_spread_{ratio_label}",
        "rank(ts_zscore(ts_backfill({ratio_expr}, {backfill_window}), 20) - ts_zscore(ts_backfill({ratio_expr}, {backfill_window}), {backfill_window}))",
        152,
    ),
)

_RATIO_LEGACY_TEMPLATE_SPECS_DEFAULT: tuple[tuple[str, str, int], ...] = (
    ("raw_ratio_{ratio_label}", "{ratio_expr}", 154),
    ("group_rank_ratio_{ratio_label}", "group_rank({ratio_expr}, subindustry)", 152),
    ("ratio_{ratio_label}", "rank({ratio_expr})", 148),
    (
        "decay_ratio_{ratio_label}",
        "rank(ts_decay_linear(ts_backfill({ratio_expr}, {backfill_window}), 63))",
        126,
    ),
)


@dataclass(frozen=True, slots=True)
class StaticConfig:
    """Immutable resolved snapshot of every static configuration value."""

    api_base: str
    auth_url: str
    data_fields_url: str
    simulations_url: str
    alphas_url: str
    default_rate_limit_max_retries: int
    default_headers: dict[str, str]
    version_header: dict[str, str]
    sim_accept_header: dict[str, str]

    date_format_iso: str
    blacklist_schema_version: str
    months_per_year: int
    payload_text_truncation_limit: int
    api_key_detail: str
    api_key_error: str
    api_key_message: str
    api_key_status: str
    api_key_progress: str
    api_key_state: str
    status_simulated: str
    status_error: str
    status_skipped: str
    stat_field_attempted: str
    stat_field_submittable: str
    stat_field_errors: str
    stat_field_simulated: str
    stat_field_queue_timeouts: str
    stat_field_low_sharpe: str
    stat_field_low_fitness: str
    stat_field_concentrated_weight: str
    stat_field_low_sub_universe_sharpe: str
    stat_field_failed_check_counts: str
    stat_field_top_failed_checks: str
    stat_field_template_name: str
    stat_field_field_id: str
    stat_field_field_name: str
    stat_field_field_type: str
    stat_field_attempted_templates: str
    template_stage_first_order: str
    template_stage_group_second_order: str
    template_stage_event_conditioned: str
    feedback_stage_generate: str
    feedback_stage_resimulate: str
    sentinel_unknown: str
    sentinel_unknown_check: str
    sentinel_unknown_status: str
    unknown_family: str
    neutralization_none: str
    neutralization_industry: str
    neutralization_market: str
    group_name_subindustry: str
    sim_state_pending: str
    sim_state_running: str
    sim_state_queued: str
    sim_state_completed: str
    sim_state_failed: str
    sim_state_error: str
    sim_state_cancelled: str
    sim_active_states: frozenset[str]
    sim_terminal_states: frozenset[str]

    submit_min_fitness: float
    submit_min_sharpe: float
    submit_min_turnover: float
    submit_max_turnover: float
    submit_max_weight: float
    max_failed_check_names: int
    failure_summary_max_len: int
    backfill_window: int
    feedback_mutation_highscore_threshold: float
    delta_std_priority_boost: int
    check_low_sharpe: str
    check_low_turnover: str
    check_low_fitness: str
    check_low_sub_universe_sharpe: str
    check_concentrated_weight: str
    check_high_turnover: str
    stats_default_score: float
    stats_failed_check_default_score: float
    stats_nearpass_summary_limit: int
    stats_performance_top_n: int
    fields_cache_ttl_hours: int
    failed_check_epsilon: float
    failed_check_max_example_ids: int
    optimization_hint_top_n: int
    preferred_field_rank_sentinel: int
    default_settings_variant_budget: int
    smoke_test_max_pending_cycles: int
    smoke_test_max_queue_seconds: int
    full_run_max_new_simulations: int
    checkpoint_resume_safety_seconds: float
    checkpoint_pending_futures_limit: int
    dry_run_sample_limit: int
    settings_variant_decay_fast: int
    settings_variant_decay_slow: int
    field_priority_attempted_high: int
    field_priority_score_high: float
    field_priority_attempted_low: int
    field_priority_score_low: float
    default_min_request_interval: float
    default_sleep_between_fields: float
    default_max_concurrent_simulations: int
    default_max_concurrent_creates: int
    default_max_templates_per_field: int
    default_field_template_batch_size: int
    default_simulation_max_wait_seconds: int
    default_simulation_max_queue_seconds: int
    default_queue_busy_cooldown_seconds: int
    default_dataset_id: str
    truncation_web_default: float
    truncation_tighter_max: float
    partner_self_match_penalty: int
    partner_preferred_base_score: int
    partner_rank_max_score: int
    partner_rank_step_penalty: int
    partner_keyword_match_score: int
    partner_reverse_keyword_score: int
    partner_shared_token_weight: int
    partner_substring_score: int

    similarity_penalty_offset_legacy_level: int
    similarity_penalty_offset_legacy_group_level: int
    similarity_penalty_offset_legacy_ratio: int
    similarity_penalty_offset_legacy_neg_ratio: int
    similarity_penalty_offset_group_ratio_level: int
    legacy_matrix_raw_field_priority: int
    legacy_matrix_group_rank_subindustry_priority: int
    legacy_matrix_group_rank_industry_priority: int
    legacy_matrix_rank_raw_field_priority: int
    legacy_matrix_neg_positive_raw_priority: int
    legacy_matrix_neg_negative_raw_priority: int
    legacy_matrix_neg_default_priority: int
    ratio_partner_candidates: dict[str, tuple[str, ...]]
    ratio_keywords: dict[str, tuple[str, ...]]
    positive_raw_fields: set[str]
    negative_raw_fields: set[str]
    allowed_external_ratio_partners: set[str]
    default_preferred_partner_score_bonuses: dict[str, int]
    default_matrix_delta_over_std_windows: tuple[tuple[int, int, int], ...]
    default_matrix_diversified_template_specs: tuple[tuple[str, str, int], ...]
    default_ratio_delta_rank_windows: tuple[tuple[int, int], ...]
    default_ratio_delta_over_std_windows: tuple[tuple[int, int, int], ...]
    default_ratio_diversified_template_specs: tuple[tuple[str, str, int], ...]
    ratio_legacy_template_specs: tuple[tuple[str, str, int], ...]

    @classmethod
    def _build(cls) -> StaticConfig:
        api_base = _yaml_str("api", "base_url", default="https://api.worldquantbrain.com")
        sim_state_pending = _yaml_str("simulation", "states", "pending", default="PENDING")
        sim_state_running = _yaml_str("simulation", "states", "running", default="RUNNING")
        sim_state_queued = _yaml_str("simulation", "states", "queued", default="QUEUED")
        sim_state_completed = _yaml_str("simulation", "states", "completed", default="COMPLETED")
        sim_state_failed = _yaml_str("simulation", "states", "failed", default="FAILED")
        sim_state_error = _yaml_str("simulation", "states", "error", default="ERROR")
        sim_state_cancelled = _yaml_str("simulation", "states", "cancelled", default="CANCELLED")

        return cls(
            api_base=api_base,
            auth_url=_yaml_str("api", "auth_url", default=f"{api_base}/authentication").replace(
                "{base}", api_base
            ),
            data_fields_url=_yaml_str(
                "api", "data_fields_url", default=f"{api_base}/data-fields"
            ).replace("{base}", api_base),
            simulations_url=_yaml_str(
                "api", "simulations_url", default=f"{api_base}/simulations"
            ).replace("{base}", api_base),
            alphas_url=_yaml_str("api", "alphas_url", default=f"{api_base}/alphas").replace(
                "{base}", api_base
            ),
            default_rate_limit_max_retries=_yaml_int(
                "api", "default_rate_limit_max_retries", default=3
            ),
            default_headers=_yaml_dict(
                "api",
                "headers",
                "default",
                default={"Accept": "application/json", "Content-Type": "application/json"},
            ),
            version_header=_yaml_dict(
                "api",
                "headers",
                "version",
                default={"Accept": "application/json;version=2.0"},
            ),
            sim_accept_header=_yaml_dict(
                "api",
                "headers",
                "simulation",
                default={"Accept": "application/json;version=3.0"},
            ),
            date_format_iso=_yaml_str("misc", "date_format_iso", default="%Y-%m-%d"),
            blacklist_schema_version=_yaml_str("misc", "blacklist_schema_version", default="v2"),
            months_per_year=_yaml_int("misc", "months_per_year", default=12),
            payload_text_truncation_limit=_yaml_int(
                "misc", "payload_text_truncation_limit", default=500
            ),
            api_key_detail=_yaml_str("strings", "api_keys", "detail", default="detail"),
            api_key_error=_yaml_str("strings", "api_keys", "error", default="error"),
            api_key_message=_yaml_str("strings", "api_keys", "message", default="message"),
            api_key_status=_yaml_str("strings", "api_keys", "status", default="status"),
            api_key_progress=_yaml_str("strings", "api_keys", "progress", default="progress"),
            api_key_state=_yaml_str("strings", "api_keys", "state", default="state"),
            status_simulated=_yaml_str("strings", "status", "simulated", default="simulated"),
            status_error=_yaml_str("strings", "status", "error", default="error"),
            status_skipped=_yaml_str("strings", "status", "skipped", default="skipped"),
            stat_field_attempted=_yaml_str(
                "strings", "stat_fields", "attempted", default="attempted"
            ),
            stat_field_submittable=_yaml_str(
                "strings", "stat_fields", "submittable", default="submittable"
            ),
            stat_field_errors=_yaml_str("strings", "stat_fields", "errors", default="errors"),
            stat_field_simulated=_yaml_str(
                "strings", "stat_fields", "simulated", default="simulated"
            ),
            stat_field_queue_timeouts=_yaml_str(
                "strings", "stat_fields", "queue_timeouts", default="queue_timeouts"
            ),
            stat_field_low_sharpe=_yaml_str(
                "strings", "stat_fields", "low_sharpe", default="low_sharpe"
            ),
            stat_field_low_fitness=_yaml_str(
                "strings", "stat_fields", "low_fitness", default="low_fitness"
            ),
            stat_field_concentrated_weight=_yaml_str(
                "strings",
                "stat_fields",
                "concentrated_weight",
                default="concentrated_weight",
            ),
            stat_field_low_sub_universe_sharpe=_yaml_str(
                "strings",
                "stat_fields",
                "low_sub_universe_sharpe",
                default="low_sub_universe_sharpe",
            ),
            stat_field_failed_check_counts=_yaml_str(
                "strings", "stat_fields", "failed_check_counts", default="failed_check_counts"
            ),
            stat_field_top_failed_checks=_yaml_str(
                "strings", "stat_fields", "top_failed_checks", default="top_failed_checks"
            ),
            stat_field_template_name=_yaml_str(
                "strings", "stat_fields", "template_name", default="template_name"
            ),
            stat_field_field_id=_yaml_str("strings", "stat_fields", "field_id", default="field_id"),
            stat_field_field_name=_yaml_str(
                "strings", "stat_fields", "field_name", default="field_name"
            ),
            stat_field_field_type=_yaml_str(
                "strings", "stat_fields", "field_type", default="field_type"
            ),
            stat_field_attempted_templates=_yaml_str(
                "strings",
                "stat_fields",
                "attempted_templates",
                default="attempted_templates",
            ),
            template_stage_first_order=_yaml_str(
                "strings", "template_stages", "first_order", default="first_order"
            ),
            template_stage_group_second_order=_yaml_str(
                "strings",
                "template_stages",
                "group_second_order",
                default="group_second_order",
            ),
            template_stage_event_conditioned=_yaml_str(
                "strings",
                "template_stages",
                "event_conditioned",
                default="event_conditioned",
            ),
            feedback_stage_generate=_yaml_str(
                "strings", "feedback_stages", "generate", default="generate"
            ),
            feedback_stage_resimulate=_yaml_str(
                "strings", "feedback_stages", "resimulate", default="resimulate"
            ),
            sentinel_unknown=_yaml_str("sentinel", "unknown", default="UNKNOWN"),
            sentinel_unknown_check=_yaml_str("sentinel", "unknown_check", default="UNKNOWN"),
            sentinel_unknown_status=_yaml_str("sentinel", "unknown_status", default="unknown"),
            unknown_family=_yaml_str("sentinel", "unknown_family", default="other"),
            neutralization_none=_yaml_str("simulation", "neutralization", "none", default="NONE"),
            neutralization_industry=_yaml_str(
                "simulation", "neutralization", "industry", default="INDUSTRY"
            ),
            neutralization_market=_yaml_str(
                "simulation", "neutralization", "market", default="MARKET"
            ),
            group_name_subindustry=_yaml_str(
                "simulation", "group_names", "subindustry", default="subindustry"
            ),
            sim_state_pending=sim_state_pending,
            sim_state_running=sim_state_running,
            sim_state_queued=sim_state_queued,
            sim_state_completed=sim_state_completed,
            sim_state_failed=sim_state_failed,
            sim_state_error=sim_state_error,
            sim_state_cancelled=sim_state_cancelled,
            sim_active_states=frozenset({sim_state_pending, sim_state_running, sim_state_queued}),
            sim_terminal_states=frozenset(
                {
                    sim_state_completed,
                    sim_state_failed,
                    sim_state_error,
                    sim_state_cancelled,
                }
            ),
            submit_min_fitness=_yaml_float("quality", "submit", "min_fitness", default=1.00),
            submit_min_sharpe=_yaml_float("quality", "submit", "min_sharpe", default=1.25),
            submit_min_turnover=_yaml_float("quality", "submit", "min_turnover", default=0.01),
            submit_max_turnover=_yaml_float("quality", "submit", "max_turnover", default=0.70),
            submit_max_weight=_yaml_float("quality", "submit", "max_weight", default=0.10),
            max_failed_check_names=_yaml_int("failed_check", "max_failed_check_names", default=5),
            failure_summary_max_len=_yaml_int(
                "failed_check", "failure_summary_max_len", default=300
            ),
            backfill_window=_yaml_int("expression", "backfill_window", default=504),
            feedback_mutation_highscore_threshold=_yaml_float(
                "feedback", "mutation_highscore_threshold", default=0.25
            ),
            delta_std_priority_boost=_yaml_int("feedback", "delta_std_priority_boost", default=15),
            check_low_sharpe=_yaml_str(
                "strings", "check_names", "low_sharpe", default="LOW_SHARPE"
            ),
            check_low_turnover=_yaml_str(
                "strings", "check_names", "low_turnover", default="LOW_TURNOVER"
            ),
            check_low_fitness=_yaml_str(
                "strings", "check_names", "low_fitness", default="LOW_FITNESS"
            ),
            check_low_sub_universe_sharpe=_yaml_str(
                "strings",
                "check_names",
                "low_sub_universe_sharpe",
                default="LOW_SUB_UNIVERSE_SHARPE",
            ),
            check_concentrated_weight=_yaml_str(
                "strings",
                "check_names",
                "concentrated_weight",
                default="CONCENTRATED_WEIGHT",
            ),
            check_high_turnover=_yaml_str(
                "strings", "check_names", "high_turnover", default="HIGH_TURNOVER"
            ),
            stats_default_score=_yaml_float("stats", "default_score", default=-999.0),
            stats_failed_check_default_score=_yaml_float(
                "stats", "failed_check_default_score", default=-10.0
            ),
            stats_nearpass_summary_limit=_yaml_int("stats", "nearpass_summary_limit", default=50),
            stats_performance_top_n=_yaml_int("stats", "performance_top_n", default=10),
            fields_cache_ttl_hours=_yaml_int("stats", "fields_cache_ttl_hours", default=24),
            failed_check_epsilon=_yaml_float("failed_check", "epsilon", default=1e-9),
            failed_check_max_example_ids=_yaml_int("failed_check", "max_example_ids", default=5),
            optimization_hint_top_n=_yaml_int("failed_check", "optimization_hint_top_n", default=3),
            preferred_field_rank_sentinel=_yaml_int(
                "sentinel", "preferred_field_rank", default=999
            ),
            default_settings_variant_budget=_yaml_int(
                "sentinel", "default_settings_variant_budget", default=3
            ),
            smoke_test_max_pending_cycles=_yaml_int("smoke_test", "max_pending_cycles", default=60),
            smoke_test_max_queue_seconds=_yaml_int("smoke_test", "max_queue_seconds", default=300),
            full_run_max_new_simulations=_yaml_int("full_run", "max_new_simulations", default=500),
            checkpoint_resume_safety_seconds=_yaml_float(
                "checkpoint", "resume_safety_seconds", default=30.0
            ),
            checkpoint_pending_futures_limit=_yaml_int(
                "checkpoint", "pending_futures_limit", default=50
            ),
            dry_run_sample_limit=_yaml_int("checkpoint", "dry_run_sample_limit", default=20),
            settings_variant_decay_fast=_yaml_int("settings_variant", "decay_fast", default=2),
            settings_variant_decay_slow=_yaml_int("settings_variant", "decay_slow", default=6),
            field_priority_attempted_high=_yaml_int(
                "field", "priority", "attempted_high", default=8
            ),
            field_priority_score_high=_yaml_float("field", "priority", "score_high", default=0.70),
            field_priority_attempted_low=_yaml_int("field", "priority", "attempted_low", default=5),
            field_priority_score_low=_yaml_float("field", "priority", "score_low", default=0.40),
            default_min_request_interval=_yaml_float(
                "default_profile", "min_request_interval", default=2.0
            ),
            default_sleep_between_fields=_yaml_float(
                "default_profile", "sleep_between_fields", default=5.0
            ),
            default_max_concurrent_simulations=_yaml_int(
                "default_profile", "max_concurrent_simulations", default=1
            ),
            default_max_concurrent_creates=_yaml_int(
                "default_profile", "max_concurrent_creates", default=1
            ),
            default_max_templates_per_field=_yaml_int(
                "default_profile", "max_templates_per_field", default=12
            ),
            default_field_template_batch_size=_yaml_int(
                "default_profile", "field_template_batch_size", default=2
            ),
            default_simulation_max_wait_seconds=_yaml_int(
                "default_profile", "simulation_max_wait_seconds", default=900
            ),
            default_simulation_max_queue_seconds=_yaml_int(
                "default_profile", "simulation_max_queue_seconds", default=600
            ),
            default_queue_busy_cooldown_seconds=_yaml_int(
                "default_profile", "queue_busy_cooldown_seconds", default=120
            ),
            default_dataset_id=_yaml_str("simulation", "default_dataset_id", default="model51"),
            truncation_web_default=_yaml_float(
                "simulation", "truncation", "web_default", default=0.08
            ),
            truncation_tighter_max=_yaml_float(
                "simulation", "truncation", "tighter_max", default=0.05
            ),
            partner_self_match_penalty=_yaml_int("partner", "self_match_penalty", default=-10000),
            partner_preferred_base_score=_yaml_int("partner", "preferred_base_score", default=180),
            partner_rank_max_score=_yaml_int("partner", "rank_max_score", default=30),
            partner_rank_step_penalty=_yaml_int("partner", "rank_step_penalty", default=5),
            partner_keyword_match_score=_yaml_int("partner", "keyword_match_score", default=100),
            partner_reverse_keyword_score=_yaml_int("partner", "reverse_keyword_score", default=80),
            partner_shared_token_weight=_yaml_int("partner", "shared_token_weight", default=10),
            partner_substring_score=_yaml_int("partner", "substring_score", default=5),
            similarity_penalty_offset_legacy_level=_yaml_int(
                "templates", "similarity_penalty_offset", "legacy_level", default=0
            ),
            similarity_penalty_offset_legacy_group_level=_yaml_int(
                "templates", "similarity_penalty_offset", "legacy_group_level", default=6
            ),
            similarity_penalty_offset_legacy_ratio=_yaml_int(
                "templates", "similarity_penalty_offset", "legacy_ratio", default=10
            ),
            similarity_penalty_offset_legacy_neg_ratio=_yaml_int(
                "templates", "similarity_penalty_offset", "legacy_neg_ratio", default=8
            ),
            similarity_penalty_offset_group_ratio_level=_yaml_int(
                "templates", "similarity_penalty_offset", "group_ratio_level", default=14
            ),
            legacy_matrix_raw_field_priority=_yaml_int(
                "templates", "legacy_matrix", "raw_field", default=145
            ),
            legacy_matrix_group_rank_subindustry_priority=_yaml_int(
                "templates", "legacy_matrix", "group_rank_subindustry", default=143
            ),
            legacy_matrix_group_rank_industry_priority=_yaml_int(
                "templates", "legacy_matrix", "group_rank_industry", default=141
            ),
            legacy_matrix_rank_raw_field_priority=_yaml_int(
                "templates", "legacy_matrix", "rank_raw_field", default=118
            ),
            legacy_matrix_neg_positive_raw_priority=_yaml_int(
                "templates", "legacy_matrix", "neg_positive_raw", default=132
            ),
            legacy_matrix_neg_negative_raw_priority=_yaml_int(
                "templates", "legacy_matrix", "neg_negative_raw", default=144
            ),
            legacy_matrix_neg_default_priority=_yaml_int(
                "templates", "legacy_matrix", "neg_default", default=128
            ),
            ratio_partner_candidates=_yaml_dict_tuple("ratio", "partner_candidates")
            or _RATIO_PARTNER_CANDIDATES_DEFAULT,
            ratio_keywords=_yaml_dict_tuple("ratio", "keywords") or _RATIO_KEYWORDS_DEFAULT,
            positive_raw_fields=_yaml_set("ratio", "positive_raw_fields")
            or _POSITIVE_RAW_FIELDS_DEFAULT,
            negative_raw_fields=_yaml_set("ratio", "negative_raw_fields")
            or _NEGATIVE_RAW_FIELDS_DEFAULT,
            allowed_external_ratio_partners=_yaml_set("ratio", "allowed_external_partners")
            or _ALLOWED_EXTERNAL_RATIO_PARTNERS_DEFAULT,
            default_preferred_partner_score_bonuses=_yaml_dict(
                "ratio", "preferred_partner_score_bonuses"
            )
            or _DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES_DEFAULT,
            default_matrix_delta_over_std_windows=_yaml_tuple_int3(
                "ratio", "default_matrix_delta_over_std_windows"
            )
            or _DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS_DEFAULT,
            default_matrix_diversified_template_specs=_yaml_tuple_str_int(
                "ratio", "default_matrix_diversified_template_specs"
            )
            or _DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS_DEFAULT,
            default_ratio_delta_rank_windows=_yaml_tuple_int2(
                "ratio", "default_ratio_delta_rank_windows"
            )
            or _DEFAULT_RATIO_DELTA_RANK_WINDOWS_DEFAULT,
            default_ratio_delta_over_std_windows=_yaml_tuple_int3(
                "ratio", "default_ratio_delta_over_std_windows"
            )
            or _DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS_DEFAULT,
            default_ratio_diversified_template_specs=_yaml_tuple_str_int(
                "ratio", "default_ratio_diversified_template_specs"
            )
            or _DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS_DEFAULT,
            ratio_legacy_template_specs=_yaml_tuple_str_int("ratio", "legacy_template_specs")
            or _RATIO_LEGACY_TEMPLATE_SPECS_DEFAULT,
        )


_constants_lock = Lock()
_constants_cache: StaticConfig | None = None
_constants_source: object = None


def get_static_config() -> StaticConfig:
    """Return the resolved static configuration snapshot, cached per YAML source."""
    global _constants_cache, _constants_source
    active_source = get_yaml_config_version()
    with _constants_lock:
        if _constants_cache is None or _constants_source != active_source:
            _constants_cache = StaticConfig._build()
            _constants_source = active_source
        return _constants_cache


def clear_static_config_cache() -> None:
    """Force the next ``get_static_config()`` call to rebuild from YAML."""
    global _constants_cache, _constants_source
    with _constants_lock:
        _constants_cache = None
        _constants_source = None


__all__ = ["StaticConfig", "clear_static_config_cache", "get_static_config"]
