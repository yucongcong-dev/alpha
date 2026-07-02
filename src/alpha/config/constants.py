"""
静态配置常量。

本模块只承载不依赖 YAML 运行态的常量定义，避免 config 包入口继续膨胀。
"""

from __future__ import annotations

API_BASE: str = "https://api.worldquantbrain.com"
AUTH_URL: str = f"{API_BASE}/authentication"
DATA_FIELDS_URL: str = f"{API_BASE}/data-fields"
SIMULATIONS_URL: str = f"{API_BASE}/simulations"
ALPHAS_URL: str = f"{API_BASE}/alphas"

DEFAULT_DATASET_ID: str = "model51"
DEFAULT_HEADERS: dict = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}
VERSION_HEADER: dict[str, str] = {"Accept": "application/json;version=2.0"}
SIM_ACCEPT_HEADER: dict[str, str] = {"Accept": "application/json;version=3.0"}
DEFAULT_RATE_LIMIT_MAX_RETRIES: int = 3

SUBMIT_MIN_FITNESS: float = 1.00
SUBMIT_MIN_SHARPE: float = 1.25
SUBMIT_MIN_TURNOVER: float = 0.01
SUBMIT_MAX_TURNOVER: float = 0.70
SUBMIT_MAX_WEIGHT: float = 0.10

BACKFILL_WINDOW: int = 504  # 与 YAML global.expression.backfill_window 保持一致，daily 数据 >= 2y

PRECHECK_FALLBACK_MIN_SHARPE: float = 1.25
PRECHECK_FALLBACK_MIN_FITNESS: float = 1.00
PRECHECK_FALLBACK_MIN_TURNOVER: float = 0.01
PRECHECK_FALLBACK_MAX_TURNOVER: float = 0.70
PRECHECK_FALLBACK_MAX_WEIGHT: float = 0.10
MAX_FAILED_CHECK_NAMES: int = 5
FAILURE_SUMMARY_MAX_LEN: int = 300

SETTINGS_VARIANT_BUDGET_HIGH: float = 0.35
SETTINGS_VARIANT_BUDGET_MID: float = 0.10
FEEDBACK_MUTATION_NEARPASS_THRESHOLD: float = 0.08
FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD: float = 0.25
FEEDBACK_TEMPLATE_MIN_PRIORITY: int = 105
DELTA_STD_PRIORITY_BOOST: int = 15

CHECK_LOW_SHARPE: str = "LOW_SHARPE"
CHECK_LOW_TURNOVER: str = "LOW_TURNOVER"
CHECK_LOW_FITNESS: str = "LOW_FITNESS"
CHECK_LOW_SUB_UNIVERSE_SHARPE: str = "LOW_SUB_UNIVERSE_SHARPE"
CHECK_CONCENTRATED_WEIGHT: str = "CONCENTRATED_WEIGHT"
CHECK_HIGH_TURNOVER: str = "HIGH_TURNOVER"

SETTINGS_NEARPASS_THRESHOLD: float = 0.45
SETTINGS_CLOSE_THRESHOLD: float = 0.65
EXPR_NEARPASS_BOOST_THRESHOLD: float = 0.50
EXPR_ITER_BOOST_THRESHOLD: float = 0.20
EXPR_RATIO_PENALTY_THRESHOLD: float = 0.30
EXPR_MUTATION_EXTEND_THRESHOLD: float = 0.15

HTTP_REQUEST_TIMEOUT: float = 90.0
RATE_LIMIT_DEFAULT_WAIT: float = 10.0
POLLING_DEFAULT_WAIT: float = 5.0
POLLING_NO_RETRY_AFTER_WAIT: float = 1.5
SERVER_ERROR_BACKOFF_MAX: float = 30.0
SERVER_ERROR_BACKOFF_STEP: float = 3.0
RETRY_OPERATION_DEFAULT_WAIT: float = 2.0
LOGIN_RETRY_WAIT: float = 3.0
SIMULATION_RETRY_WAIT: float = 3.0
POLLING_RETRY_BUFFER: float = 0.5

# 模拟默认时间窗口 —— 仅当 YAML simulation 未指定 startDate/endDate 时使用
# 实际运行时优先用 YAML global.simulation.testPeriodYears/Months 动态计算
SIMULATION_DEFAULT_START_DATE: str = "2020-01-01"
SIMULATION_DEFAULT_END_DATE: str = "2025-12-31"

STATS_DEFAULT_SCORE: float = -999.0
STATS_FAILED_CHECK_DEFAULT_SCORE: float = -10.0
STATS_NEARPASS_SUMMARY_LIMIT: int = 50  # 从 20 上调，减少信息丢失
STATS_PERFORMANCE_TOP_N: int = 10
FIELDS_CACHE_TTL_HOURS: int = 24  # 字段缓存过期时间，到期后自动重新拉取最新字段元数据

SENTINEL_UNKNOWN: str = "UNKNOWN"
SENTINEL_UNKNOWN_CHECK: str = "UNKNOWN"
SENTINEL_UNKNOWN_STATUS: str = "unknown"

API_KEY_DETAIL: str = "detail"
API_KEY_ERROR: str = "error"
API_KEY_MESSAGE: str = "message"
API_KEY_STATUS: str = "status"
API_KEY_FAILED: str = "failed"
API_KEY_PROGRESS: str = "progress"
API_KEY_STATE: str = "state"

STATUS_SUBMITTED: str = "submitted"
STATUS_SIMULATED: str = "simulated"
STATUS_ERROR: str = "error"

STAT_FIELD_ATTEMPTED: str = "attempted"
STAT_FIELD_SUBMITTABLE: str = "submittable"
STAT_FIELD_SUBMITTED: str = "submitted"
STAT_FIELD_ERRORS: str = "errors"
STAT_FIELD_SIMULATED: str = "simulated"
STAT_FIELD_QUEUE_TIMEOUTS: str = "queue_timeouts"
STAT_FIELD_LOW_SHARPE: str = "low_sharpe"
STAT_FIELD_LOW_FITNESS: str = "low_fitness"
STAT_FIELD_CONCENTRATED_WEIGHT: str = "concentrated_weight"
STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE: str = "low_sub_universe_sharpe"
STAT_FIELD_FAILED_CHECK_COUNTS: str = "failed_check_counts"
STAT_FIELD_TOP_FAILED_CHECKS: str = "top_failed_checks"
STAT_FIELD_TEMPLATE_NAME: str = "template_name"
STAT_FIELD_FIELD_ID: str = "field_id"
STAT_FIELD_FIELD_NAME: str = "field_name"
STAT_FIELD_FIELD_TYPE: str = "field_type"
STAT_FIELD_ATTEMPTED_TEMPLATES: str = "attempted_templates"

UNKNOWN_FAMILY: str = "other"
TEMPLATE_STAGE_FIRST_ORDER: str = "first_order"
TEMPLATE_STAGE_GROUP_SECOND_ORDER: str = "group_second_order"
TEMPLATE_STAGE_EVENT_CONDITIONED: str = "event_conditioned"

FEEDBACK_STAGE_GENERATE: str = "generate"
FEEDBACK_STAGE_PRUNE: str = "prune"
FEEDBACK_STAGE_RESIMULATE: str = "resimulate"

RATIO_PARTNER_CANDIDATES: dict[str, tuple[str, ...]] = {
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

RATIO_KEYWORDS: dict[str, tuple[str, ...]] = {
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

POSITIVE_RAW_FIELDS: set[str] = {
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

NEGATIVE_RAW_FIELDS: set[str] = {
    "cogs",
    "debt",
    "debt_lt",
    "debt_st",
    "liabilities",
}

ALLOWED_EXTERNAL_RATIO_PARTNERS: set[str] = {"cap"}

DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES: dict[str, int] = {
    "assets": 15,
    "equity": 15,
    "debt": 15,
    "liabilities": 15,
    "cash": 15,
    "enterprise_value": 15,
    "cap": 15,
}

DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS: tuple[tuple[int, int, int], ...] = (
    (5, 20, 176),
    (15, 40, 172),
    (10, 60, 170),
    (20, 60, 174),
    (25, 90, 168),
    (30, 120, 166),
)

DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = (
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

DEFAULT_RATIO_DELTA_RANK_WINDOWS: tuple[tuple[int, int], ...] = (
    (3, 188),
    (5, 184),
    (10, 176),
)

DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS: tuple[tuple[int, int, int], ...] = (
    (5, 20, 180),
    (15, 40, 176),
    (10, 60, 174),
    (20, 60, 178),
    (25, 90, 172),
    (30, 120, 170),
)

DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = (
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

RATIO_LEGACY_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = (
    ("raw_ratio_{ratio_label}", "{ratio_expr}", 154),
    (
        "group_rank_ratio_{ratio_label}",
        "group_rank({ratio_expr}, subindustry)",
        152,
    ),
    ("ratio_{ratio_label}", "rank({ratio_expr})", 148),
    (
        "decay_ratio_{ratio_label}",
        "rank(ts_decay_linear(ts_backfill({ratio_expr}, {backfill_window}), 63))",
        126,
    ),
)
