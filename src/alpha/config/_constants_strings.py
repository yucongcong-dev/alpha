"""字符串常量 — 检查名称、API key、状态、字段统计、模板 stage 等。

来源: config/constants_defaults.yaml 的 strings.* / misc.* / sentinel.* 段。
"""

from __future__ import annotations

from ._constants_core import _yaml_int, _yaml_str

# ---- 日期格式 ----
DATE_FORMAT_ISO: str = _yaml_str("misc", "date_format_iso", default="%Y-%m-%d")
DATE_FORMAT_ISO_MINUTES: str = _yaml_str("misc", "date_format_iso_minutes", default="%Y-%m-%d %H:%M")

# ---- 杂项 ----
BLACKLIST_SCHEMA_VERSION: str = _yaml_str("misc", "blacklist_schema_version", default="v2")
MONTHS_PER_YEAR: int = _yaml_int("misc", "months_per_year", default=12)
PAYLOAD_TEXT_TRUNCATION_LIMIT: int = _yaml_int("misc", "payload_text_truncation_limit", default=500)
STABLE_FINGERPRINT_HEX_LEN: int = _yaml_int("misc", "stable_fingerprint_hex_len", default=16)

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

# ---- 哨兵/未知值 ----
SENTINEL_UNKNOWN: str = _yaml_str("sentinel", "unknown", default="UNKNOWN")
SENTINEL_UNKNOWN_CHECK: str = _yaml_str("sentinel", "unknown_check", default="UNKNOWN")
SENTINEL_UNKNOWN_STATUS: str = _yaml_str("sentinel", "unknown_status", default="unknown")
UNKNOWN_FAMILY: str = _yaml_str("sentinel", "unknown_family", default="other")

# ---- 模拟参数字符串 ----
NEUTRALIZATION_NONE: str = _yaml_str("simulation", "neutralization", "none", default="NONE")
NEUTRALIZATION_INDUSTRY: str = _yaml_str("simulation", "neutralization", "industry", default="INDUSTRY")
NEUTRALIZATION_MARKET: str = _yaml_str("simulation", "neutralization", "market", default="MARKET")
NEUTRALIZATION_SUBINDUSTRY: str = _yaml_str("simulation", "neutralization", "subindustry", default="SUBINDUSTRY")
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
