"""
静态配置常量。

本模块承载所有代码常量定义，优先级为:
  settings.yaml > expression_policies.yaml > dataset_profiles.yaml > constants_defaults.yaml > 代码内默认值

即: 修改任意 YAML 文件后重启即可生效，无需改动代码。

当某个常量在 YAML 中缺失（回退到代码默认值）时，会通过 logging 输出 WARNING，
提示开发者将该常量添加到 constants_defaults.yaml 中。
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger("alpha.config.constants")

# ---------------------------------------------------------------------------
# YAML 加载辅助 — 直接调用 yaml.py 的 get_yaml_config()，复用其签名缓存
#
# 自身不做额外缓存，确保 YAML 文件变化后自动刷新。
# 路径优先级: global.<keys> (settings.yaml 覆盖) > <keys> (constants_defaults) > 代码默认值
# ---------------------------------------------------------------------------

# 记录已警告过的缺失 key，避免重复日志
_MISSING_KEY_WARNED: set[str] = set()


def _resolve_yaml_key(yaml_data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """在 yaml_data 中沿 keys 路径导航，返回最终值或 None（表示未找到）。"""
    node: Any = yaml_data
    for key in keys:
        if isinstance(node, dict):
            node = node.get(key)
            if node is None:
                return None
        else:
            return None
    return node


def _yaml_val(*keys: str, default: Any = None, cast: type = str) -> Any:
    """从完整合并 YAML 配置中读取嵌套值。

    查找顺序：
      1. global.<keys> — settings.yaml 中的用户覆盖（高优先级）
      2. <keys> — constants_defaults.yaml 中的基础默认值
      3. 代码内 default

    cast=None 表示不做类型转换，直接返回 YAML 原始值。
    """
    from .yaml import get_yaml_config

    yaml_data = get_yaml_config()
    key_path = ".".join(keys)

    # 1. 优先查找 global.* 路径（settings.yaml 用户覆盖，消除路径分裂问题）
    node = _resolve_yaml_key(yaml_data, ("global",) + keys)

    # 2. 回退到扁平路径（constants_defaults.yaml 基础默认值）
    if node is None:
        node = _resolve_yaml_key(yaml_data, keys)

    if node is None:
        if key_path not in _MISSING_KEY_WARNED:
            _MISSING_KEY_WARNED.add(key_path)
            _log.warning(
                "YAML 配置 key '%s' 未找到，使用代码默认值。"
                "建议在 constants_defaults.yaml 中添加此项。",
                key_path,
            )
        return default

    if cast is None:
        return node

    try:
        if cast is bool:
            return bool(node)
        return cast(node)
    except (TypeError, ValueError):
        if key_path not in _MISSING_KEY_WARNED:
            _MISSING_KEY_WARNED.add(key_path)
            _log.warning(
                "配置 key '%s' 值类型转换失败 (cast=%s, got=%r)，使用默认值。",
                key_path,
                cast.__name__,
                type(node).__name__,
            )
        return default


def _yaml_int(*keys: str, default: int = 0) -> int:
    return _yaml_val(*keys, default=default, cast=int)


def _yaml_float(*keys: str, default: float = 0.0) -> float:
    return _yaml_val(*keys, default=default, cast=float)


def _yaml_str(*keys: str, default: str = "") -> str:
    return _yaml_val(*keys, default=default, cast=str)


def _yaml_dict(*keys: str, default: dict | None = None) -> dict:
    result = _yaml_val(*keys, default=default, cast=None)
    return result if isinstance(result, dict) else (default or {})


def _yaml_list(*keys: str, default: list | None = None) -> list:
    result = _yaml_val(*keys, default=default, cast=None)
    return result if isinstance(result, (list, tuple)) else (default or [])


def _yaml_set(*keys: str, default: set | None = None) -> set:
    result = _yaml_val(*keys, default=default, cast=None)
    if isinstance(result, (list, tuple)):
        return set(result)
    return default or set()


def _yaml_tuple_str_int(*keys: str) -> tuple[tuple[str, str, int], ...]:
    """从 YAML [[name, expr, priority], ...] 读取 tuple[tuple[str, str, int], ...]。"""
    result = _yaml_val(*keys, default=None, cast=None)
    if not isinstance(result, (list, tuple)):
        return ()
    rows: list[tuple[str, str, int]] = []
    for item in result:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            try:
                rows.append((str(item[0]), str(item[1]), int(item[2])))
            except (TypeError, ValueError):
                continue
    return tuple(rows)


def _yaml_tuple_int2(*keys: str) -> tuple[tuple[int, int], ...]:
    """从 YAML [[a, b], ...] 读取 tuple[tuple[int, int], ...]。"""
    result = _yaml_val(*keys, default=None, cast=None)
    if not isinstance(result, (list, tuple)):
        return ()
    rows: list[tuple[int, int]] = []
    for item in result:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                rows.append((int(item[0]), int(item[1])))
            except (TypeError, ValueError):
                continue
    return tuple(rows)


def _yaml_tuple_int3(*keys: str) -> tuple[tuple[int, int, int], ...]:
    """从 YAML [[a, b, c], ...] 读取 tuple[tuple[int, int, int], ...]。"""
    result = _yaml_val(*keys, default=None, cast=None)
    if not isinstance(result, (list, tuple)):
        return ()
    rows: list[tuple[int, int, int]] = []
    for item in result:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            try:
                rows.append((int(item[0]), int(item[1]), int(item[2])))
            except (TypeError, ValueError):
                continue
    return tuple(rows)


def _yaml_dict_tuple(*keys: str) -> dict[str, tuple[str, ...]]:
    """从 YAML {key: [v1, v2, ...]} 读取 dict[str, tuple[str, ...]]。"""
    result = _yaml_val(*keys, default=None, cast=None)
    if not isinstance(result, dict):
        return {}
    return {
        str(k): tuple(str(v) for v in val)
        for k, val in result.items()
        if isinstance(val, (list, tuple))
    }


# ===========================================================================
# 常量定义 (YAML 优先，代码回退)
# ===========================================================================

# ---- API 端点 ----
_API_BASE = _yaml_str("api", "base_url", default="https://api.worldquantbrain.com")
API_BASE: str = _API_BASE
AUTH_URL: str = _yaml_str("api", "auth_url", default=f"{API_BASE}/authentication").replace("{base}", API_BASE)
DATA_FIELDS_URL: str = _yaml_str("api", "data_fields_url", default=f"{API_BASE}/data-fields").replace("{base}", API_BASE)
SIMULATIONS_URL: str = _yaml_str("api", "simulations_url", default=f"{API_BASE}/simulations").replace("{base}", API_BASE)
ALPHAS_URL: str = _yaml_str("api", "alphas_url", default=f"{API_BASE}/alphas").replace("{base}", API_BASE)
DEFAULT_RATE_LIMIT_MAX_RETRIES: int = _yaml_int("api", "default_rate_limit_max_retries", default=3)

DEFAULT_DATASET_ID: str = _yaml_str("simulation", "default_dataset_id", default="model51")

DEFAULT_HEADERS: dict = _yaml_dict("api", "headers", "default", default={
    "Accept": "application/json",
    "Content-Type": "application/json",
})
VERSION_HEADER: dict[str, str] = _yaml_dict("api", "headers", "version", default={"Accept": "application/json;version=2.0"})
SIM_ACCEPT_HEADER: dict[str, str] = _yaml_dict("api", "headers", "simulation", default={"Accept": "application/json;version=3.0"})

# ---- 提交质量阈值 ----
SUBMIT_MIN_FITNESS: float = _yaml_float("quality", "submit", "min_fitness", default=1.00)
SUBMIT_MIN_SHARPE: float = _yaml_float("quality", "submit", "min_sharpe", default=1.25)
SUBMIT_MIN_TURNOVER: float = _yaml_float("quality", "submit", "min_turnover", default=0.01)
SUBMIT_MAX_TURNOVER: float = _yaml_float("quality", "submit", "max_turnover", default=0.70)
SUBMIT_MAX_WEIGHT: float = _yaml_float("quality", "submit", "max_weight", default=0.10)

# ---- 预检回退质量阈值 ----
PRECHECK_FALLBACK_MIN_SHARPE: float = _yaml_float("quality", "precheck", "min_sharpe", default=1.25)
PRECHECK_FALLBACK_MIN_FITNESS: float = _yaml_float("quality", "precheck", "min_fitness", default=1.00)
PRECHECK_FALLBACK_MIN_TURNOVER: float = _yaml_float("quality", "precheck", "min_turnover", default=0.01)
PRECHECK_FALLBACK_MAX_TURNOVER: float = _yaml_float("quality", "precheck", "max_turnover", default=0.70)
PRECHECK_FALLBACK_MAX_WEIGHT: float = _yaml_float("quality", "precheck", "max_weight", default=0.10)
MAX_FAILED_CHECK_NAMES: int = _yaml_int("failed_check", "max_failed_check_names", default=5)
FAILURE_SUMMARY_MAX_LEN: int = _yaml_int("failed_check", "failure_summary_max_len", default=300)

# ---- 表达式生成 ----
BACKFILL_WINDOW: int = _yaml_int("expression", "backfill_window", default=504)

# ---- Feedback 阈值 ----
SETTINGS_VARIANT_BUDGET_HIGH: float = _yaml_float("feedback", "settings_variant_budget_high", default=0.35)
SETTINGS_VARIANT_BUDGET_MID: float = _yaml_float("feedback", "settings_variant_budget_mid", default=0.10)
FEEDBACK_MUTATION_NEARPASS_THRESHOLD: float = _yaml_float("feedback", "mutation_nearpass_threshold", default=0.08)
FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD: float = _yaml_float("feedback", "mutation_highscore_threshold", default=0.25)
FEEDBACK_TEMPLATE_MIN_PRIORITY: int = _yaml_int("feedback", "template_min_priority", default=105)
DELTA_STD_PRIORITY_BOOST: int = _yaml_int("feedback", "delta_std_priority_boost", default=15)

SETTINGS_NEARPASS_THRESHOLD: float = _yaml_float("feedback", "settings_nearpass_threshold", default=0.45)
SETTINGS_CLOSE_THRESHOLD: float = _yaml_float("feedback", "settings_close_threshold", default=0.65)
EXPR_NEARPASS_BOOST_THRESHOLD: float = _yaml_float("feedback", "expr_nearpass_boost_threshold", default=0.50)
EXPR_ITER_BOOST_THRESHOLD: float = _yaml_float("feedback", "expr_iter_boost_threshold", default=0.20)
EXPR_RATIO_PENALTY_THRESHOLD: float = _yaml_float("feedback", "expr_ratio_penalty_threshold", default=0.30)
EXPR_MUTATION_EXTEND_THRESHOLD: float = _yaml_float("feedback", "expr_mutation_extend_threshold", default=0.15)

# ---- HTTP 客户端超时 ----
HTTP_REQUEST_TIMEOUT: float = _yaml_float("http", "request_timeout", default=90.0)
RATE_LIMIT_DEFAULT_WAIT: float = _yaml_float("http", "rate_limit_default_wait", default=10.0)
POLLING_DEFAULT_WAIT: float = _yaml_float("http", "polling_default_wait", default=5.0)
POLLING_NO_RETRY_AFTER_WAIT: float = _yaml_float("http", "polling_no_retry_after_wait", default=1.5)
SERVER_ERROR_BACKOFF_MAX: float = _yaml_float("http", "server_error_backoff_max", default=30.0)
SERVER_ERROR_BACKOFF_STEP: float = _yaml_float("http", "server_error_backoff_step", default=3.0)
RETRY_OPERATION_DEFAULT_WAIT: float = _yaml_float("http", "retry_operation_default_wait", default=2.0)
LOGIN_RETRY_WAIT: float = _yaml_float("http", "login_retry_wait", default=3.0)
SIMULATION_RETRY_WAIT: float = _yaml_float("http", "simulation_retry_wait", default=3.0)
POLLING_RETRY_BUFFER: float = _yaml_float("http", "polling_retry_buffer", default=0.5)

# ---- 模拟默认值 ----
SIMULATION_DEFAULT_START_DATE: str = _yaml_str("simulation", "default_start_date", default="2020-01-01")
SIMULATION_DEFAULT_END_DATE: str = _yaml_str("simulation", "default_end_date", default="2025-12-31")

# ---- 模板禁用阈值 ----
TEMPLATE_DISABLE_MIN_SIMULATED: int = _yaml_int("templates", "disable", "min_simulated", default=3)
TEMPLATE_DISABLE_MIN_LOW_SHARPE: int = _yaml_int("templates", "disable", "min_low_sharpe", default=3)
TEMPLATE_DISABLE_MIN_LOW_FITNESS: int = _yaml_int("templates", "disable", "min_low_fitness", default=3)
TEMPLATE_DISABLE_MIN_CONCENTRATED_WEIGHT: int = _yaml_int("templates", "disable", "min_concentrated_weight", default=2)

# ---- Near-pass 惩罚权重 ----
NEARPASS_PENALTY_CONCENTRATED_WEIGHT: float = _yaml_float("nearpass", "penalty_concentrated_weight", default=0.35)
NEARPASS_PENALTY_CONCENTRATED_WEIGHT_GAP_THRESHOLD: float = _yaml_float("nearpass", "penalty_concentrated_weight_gap_threshold", default=0.20)
NEARPASS_PENALTY_CONCENTRATED_WEIGHT_EXTRA: float = _yaml_float("nearpass", "penalty_concentrated_weight_extra", default=0.55)
NEARPASS_PENALTY_LOW_TURNOVER: float = _yaml_float("nearpass", "penalty_low_turnover", default=0.10)
NEARPASS_PENALTY_LOW_SUB_UNIVERSE_SHARPE: float = _yaml_float("nearpass", "penalty_low_sub_universe_sharpe", default=0.05)
NEARPASS_DEFAULT_LIMIT: int = _yaml_int("nearpass", "default_limit", default=3)

# ---- 字段优先级阈值 ----
FIELD_PRIORITY_ATTEMPTED_HIGH: int = _yaml_int("field", "priority", "attempted_high", default=8)
FIELD_PRIORITY_SCORE_HIGH: float = _yaml_float("field", "priority", "score_high", default=0.70)
FIELD_PRIORITY_ATTEMPTED_LOW: int = _yaml_int("field", "priority", "attempted_low", default=5)
FIELD_PRIORITY_SCORE_LOW: float = _yaml_float("field", "priority", "score_low", default=0.40)

# ---- 检查名称 ----
CHECK_LOW_SHARPE: str = _yaml_str("strings", "check_names", "low_sharpe", default="LOW_SHARPE")
CHECK_LOW_TURNOVER: str = _yaml_str("strings", "check_names", "low_turnover", default="LOW_TURNOVER")
CHECK_LOW_FITNESS: str = _yaml_str("strings", "check_names", "low_fitness", default="LOW_FITNESS")
CHECK_LOW_SUB_UNIVERSE_SHARPE: str = _yaml_str("strings", "check_names", "low_sub_universe_sharpe", default="LOW_SUB_UNIVERSE_SHARPE")
CHECK_CONCENTRATED_WEIGHT: str = _yaml_str("strings", "check_names", "concentrated_weight", default="CONCENTRATED_WEIGHT")
CHECK_HIGH_TURNOVER: str = _yaml_str("strings", "check_names", "high_turnover", default="HIGH_TURNOVER")

# ---- 统计值 ----
STATS_DEFAULT_SCORE: float = _yaml_float("stats", "default_score", default=-999.0)
STATS_FAILED_CHECK_DEFAULT_SCORE: float = _yaml_float("stats", "failed_check_default_score", default=-10.0)
STATS_NEARPASS_SUMMARY_LIMIT: int = _yaml_int("stats", "nearpass_summary_limit", default=50)
STATS_PERFORMANCE_TOP_N: int = _yaml_int("stats", "performance_top_n", default=10)
FIELDS_CACHE_TTL_HOURS: int = _yaml_int("stats", "fields_cache_ttl_hours", default=24)

# ---- 失败检查边界 ----
FAILED_CHECK_EPSILON: float = _yaml_float("failed_check", "epsilon", default=1e-9)
FAILED_CHECK_MAX_EXAMPLE_IDS: int = _yaml_int("failed_check", "max_example_ids", default=5)
OPTIMIZATION_HINT_TOP_N: int = _yaml_int("failed_check", "optimization_hint_top_n", default=3)
DOMINANT_FAILED_CHECK_LIMIT: int = _yaml_int("failed_check", "dominant_check_limit", default=4)

# ---- 模板优先级调整 ----
def _pa(key: str, default: int) -> int:
    return _yaml_int("templates", "priority_adj", key, default=default)

SIMILARITY_PENALTY_OFFSET_LEGACY_LEVEL: int = _yaml_int("templates", "similarity_penalty_offset", "legacy_level", default=0)
SIMILARITY_PENALTY_OFFSET_LEGACY_GROUP_LEVEL: int = _yaml_int("templates", "similarity_penalty_offset", "legacy_group_level", default=6)
SIMILARITY_PENALTY_OFFSET_LEGACY_RATIO: int = _yaml_int("templates", "similarity_penalty_offset", "legacy_ratio", default=10)
SIMILARITY_PENALTY_OFFSET_LEGACY_NEG_RATIO: int = _yaml_int("templates", "similarity_penalty_offset", "legacy_neg_ratio", default=8)
SIMILARITY_PENALTY_OFFSET_GROUP_RATIO_LEVEL: int = _yaml_int("templates", "similarity_penalty_offset", "group_ratio_level", default=14)

PRIORITY_ADJ_GROUP_LOW_SHARPE: int = _pa("group_low_sharpe", 28)
PRIORITY_ADJ_SIGNAL_LOW_SHARPE: int = _pa("signal_low_sharpe", 18)
PRIORITY_ADJ_LEGACY_LOW_SHARPE: int = _pa("legacy_low_sharpe", -35)
PRIORITY_ADJ_DELTA_LOW_FITNESS: int = _pa("delta_low_fitness", 22)
PRIORITY_ADJ_LEGACY_BASIC_LOW_FITNESS: int = _pa("legacy_basic_low_fitness", -25)
PRIORITY_ADJ_VOL_SCALED_LOW_FITNESS: int = _pa("vol_scaled_low_fitness", -18)
PRIORITY_ADJ_DELTA_LOW_TURNOVER: int = _pa("delta_low_turnover", 30)
PRIORITY_ADJ_LEGACY_MEAN_SPREAD_LOW_TURNOVER: int = _pa("legacy_mean_spread_low_turnover", -18)
PRIORITY_ADJ_STABLE_HIGH_TURNOVER: int = _pa("stable_high_turnover", 20)
PRIORITY_ADJ_DELTA_HIGH_TURNOVER: int = _pa("delta_high_turnover", -20)
PRIORITY_ADJ_GROUP_CONCENTRATED: int = _pa("group_concentrated", 24)
PRIORITY_ADJ_VOL_SCALED_CONCENTRATED: int = _pa("vol_scaled_concentrated", -30)
PRIORITY_ADJ_LEGACY_RATIO_CONCENTRATED: int = _pa("legacy_ratio_concentrated", -30)
PRIORITY_ADJ_HIGH_TURNOVER_CONCENTRATED_RANK_SPREAD: int = _pa("high_turnover_concentrated_rank_spread", -50)
PRIORITY_ADJ_HIGH_TURNOVER_CONCENTRATED_ZSCORE_SPREAD: int = _pa("high_turnover_concentrated_zscore_spread", -45)
PRIORITY_ADJ_NEARPASS_BOOST: int = _pa("nearpass_boost", 40)
PRIORITY_ADJ_ITER_BOOST: int = _pa("iter_boost", 18)
PRIORITY_ADJ_LEGACY_RATIO_PENALTY: int = _pa("legacy_ratio_penalty", -40)
PRIORITY_ADJ_NEARPASS_GROUP_RANK_DELTA: int = _pa("nearpass_group_rank_delta", 20)
PRIORITY_ADJ_VOL_SCALED_DELTA_BASE: int = _pa("vol_scaled_delta_base", -28)
PRIORITY_ADJ_VOL_SCALED_DELTA_CONCENTRATED: int = _pa("vol_scaled_delta_concentrated", -18)
PRIORITY_ADJ_VOL_SCALED_DELTA_NEARPASS: int = _pa("vol_scaled_delta_nearpass", -8)
PRIORITY_ADJ_ACCOUNT_TEMPLATES: int = _pa("account_templates", 22)

# ---- 模板历史评分 ----
TEMPLATE_HISTORY_SUBMITTABLE_BONUS: int = _yaml_int("templates", "history", "submittable_bonus", default=200)
TEMPLATE_HISTORY_SIMULATED_BASE: int = _yaml_int("templates", "history", "simulated_base", default=40)
TEMPLATE_HISTORY_SIMULATED_CAP: int = _yaml_int("templates", "history", "simulated_cap", default=5)
TEMPLATE_HISTORY_SIMULATED_STEP: int = _yaml_int("templates", "history", "simulated_step", default=8)
TEMPLATE_HISTORY_LOW_PERF_PENALTY: int = _yaml_int("templates", "history", "low_perf_penalty", default=-90)
TEMPLATE_HISTORY_CONCENTRATED_PENALTY: int = _yaml_int("templates", "history", "concentrated_penalty", default=-60)
TEMPLATE_HISTORY_ERROR_PENALTY: int = _yaml_int("templates", "history", "error_penalty", default=-20)

# ---- Mutation 阈值 ----
MUTATION_DOMINANT_CHECK_LIMIT: int = _yaml_int("mutation", "dominant_check_limit", default=3)
MUTATION_ACCOUNT_EXTEND_THRESHOLD: float = _yaml_float("mutation", "account_extend_threshold", default=0.45)

# ---- 参数回退默认值 ----
TRUNCATION_WEB_DEFAULT: float = _yaml_float("simulation", "truncation", "web_default", default=0.08)
TRUNCATION_TIGHTER_MAX: float = _yaml_float("simulation", "truncation", "tighter_max", default=0.05)

# ---- DEFAULT_PROFILE 回退值 ----
DEFAULT_MIN_REQUEST_INTERVAL: float = _yaml_float("default_profile", "min_request_interval", default=2.0)
DEFAULT_SLEEP_BETWEEN_FIELDS: float = _yaml_float("default_profile", "sleep_between_fields", default=5.0)
DEFAULT_MAX_CONCURRENT_SIMULATIONS: int = _yaml_int("default_profile", "max_concurrent_simulations", default=1)
DEFAULT_MAX_CONCURRENT_CREATES: int = _yaml_int("default_profile", "max_concurrent_creates", default=1)
DEFAULT_MAX_TEMPLATES_PER_FIELD: int = _yaml_int("default_profile", "max_templates_per_field", default=12)
DEFAULT_FIELD_TEMPLATE_BATCH_SIZE: int = _yaml_int("default_profile", "field_template_batch_size", default=2)
DEFAULT_SIMULATION_MAX_WAIT_SECONDS: int = _yaml_int("default_profile", "simulation_max_wait_seconds", default=900)
DEFAULT_SIMULATION_MAX_QUEUE_SECONDS: int = _yaml_int("default_profile", "simulation_max_queue_seconds", default=600)
DEFAULT_QUEUE_BUSY_COOLDOWN_SECONDS: int = _yaml_int("default_profile", "queue_busy_cooldown_seconds", default=120)
DEFAULT_TEMPLATE_DISABLE_AFTER: int = _yaml_int("default_profile", "template_disable_after", default=12)

# ---- 哨兵值 ----
PREFERRED_FIELD_RANK_SENTINEL: int = _yaml_int("sentinel", "preferred_field_rank", default=999)
DEFAULT_SETTINGS_VARIANT_BUDGET: int = _yaml_int("sentinel", "default_settings_variant_budget", default=3)

# ---- Smoke test 安全边界 ----
SMOKE_TEST_MAX_PENDING_CYCLES: int = _yaml_int("smoke_test", "max_pending_cycles", default=60)
SMOKE_TEST_MAX_QUEUE_SECONDS: int = _yaml_int("smoke_test", "max_queue_seconds", default=300)

# ---- 伙伴字段配对评分权重 ----
PARTNER_SELF_MATCH_PENALTY: int = _yaml_int("partner", "self_match_penalty", default=-10000)
PARTNER_PREFERRED_BASE_SCORE: int = _yaml_int("partner", "preferred_base_score", default=180)
PARTNER_RANK_MAX_SCORE: int = _yaml_int("partner", "rank_max_score", default=30)
PARTNER_RANK_STEP_PENALTY: int = _yaml_int("partner", "rank_step_penalty", default=5)
PARTNER_KEYWORD_MATCH_SCORE: int = _yaml_int("partner", "keyword_match_score", default=100)
PARTNER_REVERSE_KEYWORD_SCORE: int = _yaml_int("partner", "reverse_keyword_score", default=80)
PARTNER_SHARED_TOKEN_WEIGHT: int = _yaml_int("partner", "shared_token_weight", default=10)
PARTNER_SUBSTRING_SCORE: int = _yaml_int("partner", "substring_score", default=5)

# ---- 日期格式 ----
DATE_FORMAT_ISO: str = _yaml_str("misc", "date_format_iso", default="%Y-%m-%d")
DATE_FORMAT_ISO_MINUTES: str = _yaml_str("misc", "date_format_iso_minutes", default="%Y-%m-%d %H:%M")

# ---- 杂项 ----
BLACKLIST_SCHEMA_VERSION: str = _yaml_str("misc", "blacklist_schema_version", default="v2")
MONTHS_PER_YEAR: int = _yaml_int("misc", "months_per_year", default=12)
PAYLOAD_TEXT_TRUNCATION_LIMIT: int = _yaml_int("misc", "payload_text_truncation_limit", default=500)
STABLE_FINGERPRINT_HEX_LEN: int = _yaml_int("misc", "stable_fingerprint_hex_len", default=16)

# ---- 中性化策略 ----
NEUTRALIZATION_NONE: str = _yaml_str("simulation", "neutralization", "none", default="NONE")
NEUTRALIZATION_INDUSTRY: str = _yaml_str("simulation", "neutralization", "industry", default="INDUSTRY")
NEUTRALIZATION_MARKET: str = _yaml_str("simulation", "neutralization", "market", default="MARKET")
NEUTRALIZATION_SUBINDUSTRY: str = _yaml_str("simulation", "neutralization", "subindustry", default="SUBINDUSTRY")

# ---- Brain 分组名称 ----
GROUP_NAME_SUBINDUSTRY: str = _yaml_str("simulation", "group_names", "subindustry", default="subindustry")
GROUP_NAME_INDUSTRY: str = _yaml_str("simulation", "group_names", "industry", default="industry")

# ---- Simulation 状态字符串 ----
SIM_STATE_PENDING: str = _yaml_str("simulation", "states", "pending", default="PENDING")
SIM_STATE_RUNNING: str = _yaml_str("simulation", "states", "running", default="RUNNING")
SIM_STATE_QUEUED: str = _yaml_str("simulation", "states", "queued", default="QUEUED")
SIM_STATE_COMPLETED: str = _yaml_str("simulation", "states", "completed", default="COMPLETED")
SIM_STATE_FAILED: str = _yaml_str("simulation", "states", "failed", default="FAILED")
SIM_STATE_ERROR: str = _yaml_str("simulation", "states", "error", default="ERROR")
SIM_STATE_CANCELLED: str = _yaml_str("simulation", "states", "cancelled", default="CANCELLED")
SIM_ACTIVE_STATES: frozenset[str] = frozenset({SIM_STATE_PENDING, SIM_STATE_RUNNING, SIM_STATE_QUEUED})
SIM_TERMINAL_STATES: frozenset[str] = frozenset({SIM_STATE_COMPLETED, SIM_STATE_FAILED, SIM_STATE_ERROR, SIM_STATE_CANCELLED})

# ---- 检查点 ----
CHECKPOINT_RESUME_SAFETY_SECONDS: float = _yaml_float("checkpoint", "resume_safety_seconds", default=30.0)
CHECKPOINT_PENDING_FUTURES_LIMIT: int = _yaml_int("checkpoint", "pending_futures_limit", default=50)
DRY_RUN_SAMPLE_LIMIT: int = _yaml_int("checkpoint", "dry_run_sample_limit", default=20)

# ---- Settings 变体 decay 策略 ----
SETTINGS_VARIANT_DECAY_FAST: int = _yaml_int("settings_variant", "decay_fast", default=2)
SETTINGS_VARIANT_DECAY_SLOW: int = _yaml_int("settings_variant", "decay_slow", default=6)

# ---- Near-pass 精修优先级 ----
REFINE_PRIORITY_BASE: int = _yaml_int("templates", "refine_priority", "base", default=260)
REFINE_PRIORITY_STEP: int = _yaml_int("templates", "refine_priority", "step", default=12)
REFINE_PRIORITY_SUBINDUSTRY_DELTA: int = _yaml_int("templates", "refine_priority", "subindustry_delta", default=-2)
REFINE_PRIORITY_ZSCORE_DELTA: int = _yaml_int("templates", "refine_priority", "zscore_delta", default=-3)
REFINE_PRIORITY_TSRANK_DELTA: int = _yaml_int("templates", "refine_priority", "tsrank_delta", default=-4)
REFINE_PRIORITY_BACKFILL_DELTA: int = _yaml_int("templates", "refine_priority", "backfill_delta", default=-5)
REFINE_PRIORITY_TRADE_WHEN_DELTA: int = _yaml_int("templates", "refine_priority", "trade_when_delta", default=-6)
REFINE_PRIORITY_DECAY_DELTA: int = _yaml_int("templates", "refine_priority", "decay_delta", default=-7)

# ---- 哨兵/未知值 ----
SENTINEL_UNKNOWN: str = _yaml_str("sentinel", "unknown", default="UNKNOWN")
SENTINEL_UNKNOWN_CHECK: str = _yaml_str("sentinel", "unknown_check", default="UNKNOWN")
SENTINEL_UNKNOWN_STATUS: str = _yaml_str("sentinel", "unknown_status", default="unknown")
UNKNOWN_FAMILY: str = _yaml_str("sentinel", "unknown_family", default="other")

# ---- API key 字符串 ----
API_KEY_DETAIL: str = _yaml_str("strings", "api_keys", "detail", default="detail")
API_KEY_ERROR: str = _yaml_str("strings", "api_keys", "error", default="error")
API_KEY_MESSAGE: str = _yaml_str("strings", "api_keys", "message", default="message")
API_KEY_STATUS: str = _yaml_str("strings", "api_keys", "status", default="status")
API_KEY_FAILED: str = _yaml_str("strings", "api_keys", "failed", default="failed")
API_KEY_PROGRESS: str = _yaml_str("strings", "api_keys", "progress", default="progress")
API_KEY_STATE: str = _yaml_str("strings", "api_keys", "state", default="state")

# ---- 状态字符串 ----
STATUS_SUBMITTED: str = _yaml_str("strings", "status", "submitted", default="submitted")
STATUS_SIMULATED: str = _yaml_str("strings", "status", "simulated", default="simulated")
STATUS_ERROR: str = _yaml_str("strings", "status", "error", default="error")

# ---- 字段统计键名 ----
STAT_FIELD_ATTEMPTED: str = _yaml_str("strings", "stat_fields", "attempted", default="attempted")
STAT_FIELD_SUBMITTABLE: str = _yaml_str("strings", "stat_fields", "submittable", default="submittable")
STAT_FIELD_SUBMITTED: str = _yaml_str("strings", "stat_fields", "submitted", default="submitted")
STAT_FIELD_ERRORS: str = _yaml_str("strings", "stat_fields", "errors", default="errors")
STAT_FIELD_SIMULATED: str = _yaml_str("strings", "stat_fields", "simulated", default="simulated")
STAT_FIELD_QUEUE_TIMEOUTS: str = _yaml_str("strings", "stat_fields", "queue_timeouts", default="queue_timeouts")
STAT_FIELD_LOW_SHARPE: str = _yaml_str("strings", "stat_fields", "low_sharpe", default="low_sharpe")
STAT_FIELD_LOW_FITNESS: str = _yaml_str("strings", "stat_fields", "low_fitness", default="low_fitness")
STAT_FIELD_CONCENTRATED_WEIGHT: str = _yaml_str("strings", "stat_fields", "concentrated_weight", default="concentrated_weight")
STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE: str = _yaml_str("strings", "stat_fields", "low_sub_universe_sharpe", default="low_sub_universe_sharpe")
STAT_FIELD_FAILED_CHECK_COUNTS: str = _yaml_str("strings", "stat_fields", "failed_check_counts", default="failed_check_counts")
STAT_FIELD_TOP_FAILED_CHECKS: str = _yaml_str("strings", "stat_fields", "top_failed_checks", default="top_failed_checks")
STAT_FIELD_TEMPLATE_NAME: str = _yaml_str("strings", "stat_fields", "template_name", default="template_name")
STAT_FIELD_FIELD_ID: str = _yaml_str("strings", "stat_fields", "field_id", default="field_id")
STAT_FIELD_FIELD_NAME: str = _yaml_str("strings", "stat_fields", "field_name", default="field_name")
STAT_FIELD_FIELD_TYPE: str = _yaml_str("strings", "stat_fields", "field_type", default="field_type")
STAT_FIELD_ATTEMPTED_TEMPLATES: str = _yaml_str("strings", "stat_fields", "attempted_templates", default="attempted_templates")

# ---- 模板 stage 名称 ----
TEMPLATE_STAGE_FIRST_ORDER: str = _yaml_str("strings", "template_stages", "first_order", default="first_order")
TEMPLATE_STAGE_GROUP_SECOND_ORDER: str = _yaml_str("strings", "template_stages", "group_second_order", default="group_second_order")
TEMPLATE_STAGE_EVENT_CONDITIONED: str = _yaml_str("strings", "template_stages", "event_conditioned", default="event_conditioned")

# ---- Feedback stage 名称 ----
FEEDBACK_STAGE_GENERATE: str = _yaml_str("strings", "feedback_stages", "generate", default="generate")
FEEDBACK_STAGE_PRUNE: str = _yaml_str("strings", "feedback_stages", "prune", default="prune")
FEEDBACK_STAGE_RESIMULATE: str = _yaml_str("strings", "feedback_stages", "resimulate", default="resimulate")

# ---- Ratio 数据 (YAML 可选覆盖) ----
RATIO_PARTNER_CANDIDATES: dict[str, tuple[str, ...]] = _yaml_dict_tuple("ratio", "partner_candidates") or {
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

RATIO_KEYWORDS: dict[str, tuple[str, ...]] = _yaml_dict_tuple("ratio", "keywords") or {
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

POSITIVE_RAW_FIELDS: set[str] = _yaml_set("ratio", "positive_raw_fields") or {
    "assets", "assets_curr", "bookvalue_ps", "cash", "cash_st",
    "cashflow", "cashflow_op", "current_ratio", "ebit", "ebitda",
    "enterprise_value", "eps", "equity",
}

NEGATIVE_RAW_FIELDS: set[str] = _yaml_set("ratio", "negative_raw_fields") or {
    "cogs", "debt", "debt_lt", "debt_st", "liabilities",
}

ALLOWED_EXTERNAL_RATIO_PARTNERS: set[str] = _yaml_set("ratio", "allowed_external_partners") or {"cap"}

DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES: dict[str, int] = _yaml_dict("ratio", "preferred_partner_score_bonuses") or {
    "assets": 15, "equity": 15, "debt": 15, "liabilities": 15,
    "cash": 15, "enterprise_value": 15, "cap": 15,
}

DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS: tuple[tuple[int, int, int], ...] = (
    _yaml_tuple_int3("ratio", "default_matrix_delta_over_std_windows")
    or (
        (5, 20, 176), (15, 40, 172), (10, 60, 170),
        (20, 60, 174), (25, 90, 168), (30, 120, 166),
    )
)

DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = (
    _yaml_tuple_str_int("ratio", "default_matrix_diversified_template_specs")
    or (
        ("group_delta_over_std_industry_20_60",
         "group_rank(ts_delta(ts_backfill({field}, {backfill_window}), 20) / ts_std_dev(ts_backfill({field}, {backfill_window}), 60), industry)", 166),
        ("group_short_long_mean_spread_subindustry_20_{backfill_window}",
         "group_rank(ts_mean(ts_backfill({field}, {backfill_window}), 20) - ts_mean(ts_backfill({field}, {backfill_window}), {backfill_window}), subindustry)", 164),
        ("group_zscore_subindustry_60",
         "group_rank(ts_zscore(ts_backfill({field}, {backfill_window}), 60), subindustry)", 161),
        ("rank_mean_spread_over_std_20_{backfill_window}_60",
         "rank((ts_mean(ts_backfill({field}, {backfill_window}), 20) - ts_mean(ts_backfill({field}, {backfill_window}), {backfill_window})) / ts_std_dev(ts_backfill({field}, {backfill_window}), 60))", 158),
        ("rank_zscore_spread_20_{backfill_window}",
         "rank(ts_zscore(ts_backfill({field}, {backfill_window}), 20) - ts_zscore(ts_backfill({field}, {backfill_window}), {backfill_window}))", 154),
        ("group_rank_delta_of_rank_20",
         "group_rank(ts_delta(rank(ts_backfill({field}, {backfill_window})), 20), subindustry)", 150),
    )
)

DEFAULT_RATIO_DELTA_RANK_WINDOWS: tuple[tuple[int, int], ...] = (
    _yaml_tuple_int2("ratio", "default_ratio_delta_rank_windows")
    or ((3, 188), (5, 184), (10, 176))
)

DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS: tuple[tuple[int, int, int], ...] = (
    _yaml_tuple_int3("ratio", "default_ratio_delta_over_std_windows")
    or (
        (5, 20, 180), (15, 40, 176), (10, 60, 174),
        (20, 60, 178), (25, 90, 172), (30, 120, 170),
    )
)

DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = (
    _yaml_tuple_str_int("ratio", "default_ratio_diversified_template_specs")
    or (
        ("group_ratio_zscore_{ratio_label}",
         "group_rank(ts_zscore(ts_backfill({ratio_expr}, {backfill_window}), 60), subindustry)", 160),
        ("ratio_mean_spread_over_std_{ratio_label}",
         "rank((ts_mean(ts_backfill({ratio_expr}, {backfill_window}), 20) - ts_mean(ts_backfill({ratio_expr}, {backfill_window}), {backfill_window})) / ts_std_dev(ts_backfill({ratio_expr}, {backfill_window}), 60))", 156),
        ("ratio_zscore_spread_{ratio_label}",
         "rank(ts_zscore(ts_backfill({ratio_expr}, {backfill_window}), 20) - ts_zscore(ts_backfill({ratio_expr}, {backfill_window}), {backfill_window}))", 152),
    )
)

RATIO_LEGACY_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = (
    _yaml_tuple_str_int("ratio", "legacy_template_specs")
    or (
        ("raw_ratio_{ratio_label}", "{ratio_expr}", 154),
        ("group_rank_ratio_{ratio_label}", "group_rank({ratio_expr}, subindustry)", 152),
        ("ratio_{ratio_label}", "rank({ratio_expr})", 148),
        ("decay_ratio_{ratio_label}",
         "rank(ts_decay_linear(ts_backfill({ratio_expr}, {backfill_window}), 63))", 126),
    )
)

# ---- Legacy Matrix 模板优先级 (generators/matrix_templates) ----
LEGACY_MATRIX_RAW_FIELD_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "raw_field", default=145)
LEGACY_MATRIX_GROUP_RANK_SUBINDUSTRY_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "group_rank_subindustry", default=143)
LEGACY_MATRIX_GROUP_RANK_INDUSTRY_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "group_rank_industry", default=141)
LEGACY_MATRIX_RANK_RAW_FIELD_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "rank_raw_field", default=118)
LEGACY_MATRIX_NEG_POSITIVE_RAW_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "neg_positive_raw", default=132)
LEGACY_MATRIX_NEG_NEGATIVE_RAW_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "neg_negative_raw", default=144)
LEGACY_MATRIX_NEG_DEFAULT_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "neg_default", default=128)

# ---- 文件系统路径约定 (来自 YAML paths 段) ----
CREDENTIALS_DIR: str = _yaml_str("paths", "credentials_dir", default=".credentials")
CACHE_DIR: str = _yaml_str("paths", "cache_dir", default="cache")
RESULTS_DIR: str = _yaml_str("paths", "results_dir", default="results")
DATA_DIR: str = _yaml_str("paths", "data_dir", default="data")
CREDENTIALS_FILENAME: str = _yaml_str("paths", "credentials_filename", default="worldquant_brain_credentials.json")
CREDENTIALS_KEY_FILENAME: str = _yaml_str("paths", "credentials_key_filename", default="worldquant_brain_credentials.key")
ANALYSIS_SUFFIX: str = _yaml_str("paths", "analysis_suffix", default="_analysis.json")
RESULTS_JOURNAL_SUFFIX: str = _yaml_str("paths", "results_journal_suffix", default="_results.jsonl")
STATE_SUFFIX: str = _yaml_str("paths", "state_suffix", default="_state.json")
CHECKPOINT_SUFFIX: str = _yaml_str("paths", "checkpoint_suffix", default="_checkpoint.json")
