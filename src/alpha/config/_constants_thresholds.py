"""质量阈值 + 检查名称 + 统计值 + 哨兵常量。

来源: config/constants_defaults.yaml 的 quality.* / feedback.* / stats.* / sentinel.* 等段。
"""

from __future__ import annotations

from ._constants_core import (
    _yaml_float,
    _yaml_int,
    _yaml_str,
)

# ---- 提交质量阈值 ----
SUBMIT_MIN_FITNESS: float = _yaml_float("quality", "submit", "min_fitness", default=1.00)
SUBMIT_MIN_SHARPE: float = _yaml_float("quality", "submit", "min_sharpe", default=1.25)
SUBMIT_MIN_TURNOVER: float = _yaml_float("quality", "submit", "min_turnover", default=0.01)
SUBMIT_MAX_TURNOVER: float = _yaml_float("quality", "submit", "max_turnover", default=0.70)
SUBMIT_MAX_WEIGHT: float = _yaml_float("quality", "submit", "max_weight", default=0.10)

MAX_FAILED_CHECK_NAMES: int = _yaml_int("failed_check", "max_failed_check_names", default=5)
FAILURE_SUMMARY_MAX_LEN: int = _yaml_int("failed_check", "failure_summary_max_len", default=300)

# ---- 表达式生成 ----
BACKFILL_WINDOW: int = _yaml_int("expression", "backfill_window", default=504)

# ---- Feedback 阈值 ----
FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD: float = _yaml_float(
    "feedback", "mutation_highscore_threshold", default=0.25
)
DELTA_STD_PRIORITY_BOOST: int = _yaml_int("feedback", "delta_std_priority_boost", default=15)

# ---- 检查名称 ----
CHECK_LOW_SHARPE: str = _yaml_str("strings", "check_names", "low_sharpe", default="LOW_SHARPE")
CHECK_LOW_TURNOVER: str = _yaml_str(
    "strings", "check_names", "low_turnover", default="LOW_TURNOVER"
)
CHECK_LOW_FITNESS: str = _yaml_str("strings", "check_names", "low_fitness", default="LOW_FITNESS")
CHECK_LOW_SUB_UNIVERSE_SHARPE: str = _yaml_str(
    "strings", "check_names", "low_sub_universe_sharpe", default="LOW_SUB_UNIVERSE_SHARPE"
)
CHECK_CONCENTRATED_WEIGHT: str = _yaml_str(
    "strings", "check_names", "concentrated_weight", default="CONCENTRATED_WEIGHT"
)
CHECK_HIGH_TURNOVER: str = _yaml_str(
    "strings", "check_names", "high_turnover", default="HIGH_TURNOVER"
)

# ---- 统计值 ----
STATS_DEFAULT_SCORE: float = _yaml_float("stats", "default_score", default=-999.0)
STATS_FAILED_CHECK_DEFAULT_SCORE: float = _yaml_float(
    "stats", "failed_check_default_score", default=-10.0
)
STATS_NEARPASS_SUMMARY_LIMIT: int = _yaml_int("stats", "nearpass_summary_limit", default=50)
STATS_PERFORMANCE_TOP_N: int = _yaml_int("stats", "performance_top_n", default=10)
FIELDS_CACHE_TTL_HOURS: int = _yaml_int("stats", "fields_cache_ttl_hours", default=24)

# ---- 失败检查边界 ----
FAILED_CHECK_EPSILON: float = _yaml_float("failed_check", "epsilon", default=1e-9)
FAILED_CHECK_MAX_EXAMPLE_IDS: int = _yaml_int("failed_check", "max_example_ids", default=5)
OPTIMIZATION_HINT_TOP_N: int = _yaml_int("failed_check", "optimization_hint_top_n", default=3)
# ---- 哨兵值 ----
PREFERRED_FIELD_RANK_SENTINEL: int = _yaml_int("sentinel", "preferred_field_rank", default=999)
DEFAULT_SETTINGS_VARIANT_BUDGET: int = _yaml_int(
    "sentinel", "default_settings_variant_budget", default=3
)

# ---- Smoke test 安全边界 ----
SMOKE_TEST_MAX_PENDING_CYCLES: int = _yaml_int("smoke_test", "max_pending_cycles", default=60)
SMOKE_TEST_MAX_QUEUE_SECONDS: int = _yaml_int("smoke_test", "max_queue_seconds", default=300)

# ---- Full run 安全边界 ----
FULL_RUN_MAX_NEW_SIMULATIONS: int = _yaml_int("full_run", "max_new_simulations", default=500)

# ---- 检查点 ----
CHECKPOINT_RESUME_SAFETY_SECONDS: float = _yaml_float(
    "checkpoint", "resume_safety_seconds", default=30.0
)
CHECKPOINT_PENDING_FUTURES_LIMIT: int = _yaml_int("checkpoint", "pending_futures_limit", default=50)
DRY_RUN_SAMPLE_LIMIT: int = _yaml_int("checkpoint", "dry_run_sample_limit", default=20)

# ---- Settings 变体 decay 策略 ----
SETTINGS_VARIANT_DECAY_FAST: int = _yaml_int("settings_variant", "decay_fast", default=2)
SETTINGS_VARIANT_DECAY_SLOW: int = _yaml_int("settings_variant", "decay_slow", default=6)

# ---- Mutation 阈值 ----
# ---- 字段优先级阈值 ----
FIELD_PRIORITY_ATTEMPTED_HIGH: int = _yaml_int("field", "priority", "attempted_high", default=8)
FIELD_PRIORITY_SCORE_HIGH: float = _yaml_float("field", "priority", "score_high", default=0.70)
FIELD_PRIORITY_ATTEMPTED_LOW: int = _yaml_int("field", "priority", "attempted_low", default=5)
FIELD_PRIORITY_SCORE_LOW: float = _yaml_float("field", "priority", "score_low", default=0.40)

# ---- DEFAULT_PROFILE 回退值 ----
DEFAULT_MIN_REQUEST_INTERVAL: float = _yaml_float(
    "default_profile", "min_request_interval", default=2.0
)
DEFAULT_SLEEP_BETWEEN_FIELDS: float = _yaml_float(
    "default_profile", "sleep_between_fields", default=5.0
)
DEFAULT_MAX_CONCURRENT_SIMULATIONS: int = _yaml_int(
    "default_profile", "max_concurrent_simulations", default=1
)
DEFAULT_MAX_CONCURRENT_CREATES: int = _yaml_int(
    "default_profile", "max_concurrent_creates", default=1
)
DEFAULT_MAX_TEMPLATES_PER_FIELD: int = _yaml_int(
    "default_profile", "max_templates_per_field", default=12
)
DEFAULT_FIELD_TEMPLATE_BATCH_SIZE: int = _yaml_int(
    "default_profile", "field_template_batch_size", default=2
)
DEFAULT_SIMULATION_MAX_WAIT_SECONDS: int = _yaml_int(
    "default_profile", "simulation_max_wait_seconds", default=900
)
DEFAULT_SIMULATION_MAX_QUEUE_SECONDS: int = _yaml_int(
    "default_profile", "simulation_max_queue_seconds", default=600
)
DEFAULT_QUEUE_BUSY_COOLDOWN_SECONDS: int = _yaml_int(
    "default_profile", "queue_busy_cooldown_seconds", default=120
)

# ---- 默认数据集 ID ----
DEFAULT_DATASET_ID: str = _yaml_str("simulation", "default_dataset_id", default="model51")

# ---- 模拟默认值 ----
TRUNCATION_WEB_DEFAULT: float = _yaml_float("simulation", "truncation", "web_default", default=0.08)
TRUNCATION_TIGHTER_MAX: float = _yaml_float("simulation", "truncation", "tighter_max", default=0.05)
# ---- 伙伴字段配对 ----
PARTNER_SELF_MATCH_PENALTY: int = _yaml_int("partner", "self_match_penalty", default=-10000)
PARTNER_PREFERRED_BASE_SCORE: int = _yaml_int("partner", "preferred_base_score", default=180)
PARTNER_RANK_MAX_SCORE: int = _yaml_int("partner", "rank_max_score", default=30)
PARTNER_RANK_STEP_PENALTY: int = _yaml_int("partner", "rank_step_penalty", default=5)
PARTNER_KEYWORD_MATCH_SCORE: int = _yaml_int("partner", "keyword_match_score", default=100)
PARTNER_REVERSE_KEYWORD_SCORE: int = _yaml_int("partner", "reverse_keyword_score", default=80)
PARTNER_SHARED_TOKEN_WEIGHT: int = _yaml_int("partner", "shared_token_weight", default=10)
PARTNER_SUBSTRING_SCORE: int = _yaml_int("partner", "substring_score", default=5)
