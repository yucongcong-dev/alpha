"""
配置常量模块

本模块定义了 Brain API 相关的配置常量，包括 API 端点、请求头、
数据字段配置以及辅助函数。

模块内容：
    - API 端点常量
    - 默认配置常量
    - 数据字段分类
    - 辅助判断函数
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# ============================================================================
# YAML 配置文件支持
# ============================================================================

# 默认 YAML 配置文件查找路径（按优先级）
_YAML_SEARCH_PATHS: list[str] = [
    "settings.yaml",                          # 当前工作目录
    "config/settings.yaml",                   # config 子目录
]

# 可通过环境变量指定配置文件路径
_ENV_CONFIG_PATH: str = "ALPHA_CONFIG_FILE"


def _resolve_yaml_path() -> Optional[str]:
    """按优先级查找 YAML 配置文件路径。

    优先级：
        1. 环境变量 ALPHA_CONFIG_FILE
        2. 当前目录 settings.yaml
        3. config/settings.yaml
        4. 项目根目录 settings.yaml（相对于 src/alpha/config.py）

    Returns:
        str or None: 找到的配置文件绝对路径，未找到返回 None。
    """
    # 1. 环境变量
    env_path = os.environ.get(_ENV_CONFIG_PATH)
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    # 2. 工作目录下的 settings.yaml
    for rel in _YAML_SEARCH_PATHS:
        if os.path.isfile(rel):
            return os.path.abspath(rel)

    # 3. 项目根目录 (相对于此文件位置)
    project_root = Path(__file__).resolve().parent.parent.parent
    candidate = project_root / "settings.yaml"
    if candidate.is_file():
        return str(candidate)

    return None


def load_yaml_config(config_path: str = "") -> dict[str, Any]:
    """从 YAML 文件加载运行配置。

    Args:
        config_path: YAML 配置文件路径。为空时自动搜索。

    Returns:
        dict: 解析后的配置字典。文件不存在或解析失败返回空字典。
    """
    try:
        import yaml
    except ImportError:
        return {}

    path = config_path if config_path else _resolve_yaml_path()
    if not path or not os.path.isfile(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            return data
    except (yaml.YAMLError, UnicodeDecodeError, OSError):
        pass

    return {}


# ============================================================================
# API 端点配置
# ============================================================================

API_BASE: str = "https://api.worldquantbrain.com"
"""Brain API 的基础 URL 地址"""

AUTH_URL: str = f"{API_BASE}/authentication"
"""用户认证端点 URL"""

DATA_FIELDS_URL: str = f"{API_BASE}/data-fields"
"""数据字段查询端点 URL"""

SIMULATIONS_URL: str = f"{API_BASE}/simulations"
"""模拟计算端点 URL"""

ALPHAS_URL: str = f"{API_BASE}/alphas"
"""Alpha 表达式端点 URL"""


# ============================================================================
# 默认配置常量
# ============================================================================

DEFAULT_DATASET_ID: str = "fundamental6"
"""默认使用的数据集 ID，默认为 fundamental6"""

DEFAULT_HEADERS: dict = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}
"""默认 HTTP 请求头配置，包含 JSON 内容类型"""

VERSION_HEADER: dict[str, str] = {"Accept": "application/json;version=2.0"}
"""数据字段查询专用的 Accept 请求头，包含版本信息"""

SIM_ACCEPT_HEADER: dict[str, str] = {"Accept": "application/json;version=3.0"}
"""模拟计算专用的 Accept 请求头，包含版本信息"""

DEFAULT_RATE_LIMIT_MAX_RETRIES: int = 3
"""遇到速率限制时的默认最大重试次数"""


# ============================================================================
# Alpha 提交质量标准常量 (USA TOP3000, delay=1)
# ============================================================================

SUBMIT_MIN_FITNESS: float = 1.00
"""提交要求的最低 Fitness 值（与 Brain 2026-06-29 的 Delay=1 用户门槛一致）。"""

SUBMIT_MIN_SHARPE: float = 1.25
"""提交要求的最低 Sharpe 值（与 Brain 2026-06-29 的 Delay=1 用户门槛一致）。"""

SUBMIT_MIN_TURNOVER: float = 0.01
"""提交要求的最低 Turnover（1%）。换手率过低意味着信号过于稳定，缺乏交易机会。"""

SUBMIT_MAX_TURNOVER: float = 0.75
"""提交要求的最高 Turnover（75%）。换手率过高意味着交易过于频繁，交易成本侵蚀收益。"""

SUBMIT_MAX_WEIGHT: float = 0.10
"""提交要求的单股最大权重上限（10%）。防止权重过度集中在少数股票上。"""

# ============================================================================
# 表达式生成器配置
# ============================================================================

BACKFILL_WINDOW: int = 240
"""ts_backfill 默认时间窗口（天）。更大的窗口能捕捉更多历史数据，提升信号稳定性。"""


# ============================================================================
# 模拟预检 fallback 阈值
# ============================================================================

PRECHECK_FALLBACK_MIN_SHARPE: float = 1.25
"""precheck_simulation_metrics 的最小 Sharpe fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MIN_FITNESS: float = 1.00
"""precheck_simulation_metrics 的最小 Fitness fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MIN_TURNOVER: float = 0.01
"""precheck_simulation_metrics 的最小 Turnover fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MAX_TURNOVER: float = 0.75
"""precheck_simulation_metrics 的最大 Turnover fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MAX_WEIGHT: float = 0.10
"""precheck_simulation_metrics 的单股最大权重 fallback（当 CLI 未提供时）"""

MAX_FAILED_CHECK_NAMES: int = 5
"""summarize_failure 中最多展示的失败检查项名称数量"""

FAILURE_SUMMARY_MAX_LEN: int = 300
"""summarize_failure 中截断原始 payload JSON 的最大字符数"""


# ============================================================================
# 反馈优化阈值常量
# ============================================================================

SETTINGS_VARIANT_BUDGET_HIGH: float = 0.35
"""settings 变体预算高分阈值：best_score >= 此值时分配 3 个变体预算（降低以激进取策略）"""

SETTINGS_VARIANT_BUDGET_MID: float = 0.10
"""settings 变体预算中分阈值：best_score >= 此值时分配 2 个变体预算（降低以覆盖更多候选）"""

FEEDBACK_MUTATION_NEARPASS_THRESHOLD: float = 0.08
"""反馈变异生成 - 接近通过阈值：best_score >= 此值时生成额外的 delta/zscore 背景变异（降低以扩大探索）"""

FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD: float = 0.25
"""反馈变异生成 - 高分阈值：best_score >= 此值时生成 delta/decay 最佳表达式变体（降低以提早激活）"""

FEEDBACK_TEMPLATE_MIN_PRIORITY: int = 105
"""反馈剪枝最低优先级：仅保留 priority >= 此值的模板候选（降低以保留更多候选）"""

# ============================================================================
# Delta/Std 模板优化配置
# ============================================================================

DELTA_STD_PRIORITY_BOOST: int = 15
"""delta/std 类模板额外优先级加成。历史数据显示 delta_over_std 模板 Sharpe 显著优于均值。"""

# ============================================================================
# 检查项名称常量（避免字符串硬编码）
# ============================================================================

CHECK_LOW_SHARPE: str = "LOW_SHARPE"
"""夏普比率未达标检查项名称"""

CHECK_LOW_TURNOVER: str = "LOW_TURNOVER"
"""换手率过低检查项名称"""

CHECK_LOW_FITNESS: str = "LOW_FITNESS"
"""综合适应性未达标检查项名称"""

CHECK_LOW_SUB_UNIVERSE_SHARPE: str = "LOW_SUB_UNIVERSE_SHARPE"
"""子宇宙夏普比率未达标检查项名称"""

CHECK_CONCENTRATED_WEIGHT: str = "CONCENTRATED_WEIGHT"
"""权重集中度检查项名称"""

CHECK_HIGH_TURNOVER: str = "HIGH_TURNOVER"
"""换手率过高检查项名称"""


# ============================================================================
# Settings 变体生成阈值
# ============================================================================

SETTINGS_NEARPASS_THRESHOLD: float = 0.45
"""settings 变体生成 - 接近通过阈值：best_score >= 此值时生成 MARKET 中性化变体"""

SETTINGS_CLOSE_THRESHOLD: float = 0.65
"""settings 变体生成 - 接近成功阈值：best_score >= 此值时生成更多微调变体"""


# ============================================================================
# 表达式自适应优先级调整阈值
# ============================================================================

EXPR_NEARPASS_BOOST_THRESHOLD: float = 0.50
"""表达式调整 - 高分阈值：best_score >= 此值时 nearpass 模板大幅加分"""

EXPR_ITER_BOOST_THRESHOLD: float = 0.20
"""表达式调整 - 中等阈值：best_score >= 此值时 iter 模板适度加分"""

EXPR_RATIO_PENALTY_THRESHOLD: float = 0.30
"""表达式调整 - 比率惩罚阈值：best_score >= 此值时 ratio 家族被惩罚，避免浪费队列"""

EXPR_MUTATION_EXTEND_THRESHOLD: float = 0.15
"""表达式变异 - 扩展阈值：best_score >= 此值时生成额外 nearpass 变异候选"""


# ============================================================================
# HTTP 客户端超时与重试参数
# ============================================================================

HTTP_REQUEST_TIMEOUT: float = 90.0
"""HTTP 请求默认超时时间（秒）"""

RATE_LIMIT_DEFAULT_WAIT: float = 10.0
"""速率限制默认等待时间（秒）"""

POLLING_DEFAULT_WAIT: float = 5.0
"""模拟轮询默认等待间隔（秒）"""

POLLING_NO_RETRY_AFTER_WAIT: float = 1.5
"""无 Retry-After 头时的轮询等待间隔（秒）"""

SERVER_ERROR_BACKOFF_MAX: float = 30.0
"""服务器错误退避策略最大等待时间（秒）"""

SERVER_ERROR_BACKOFF_STEP: float = 3.0
"""服务器错误退避策略步长（秒/attempt）"""

RETRY_OPERATION_DEFAULT_WAIT: float = 2.0
"""重试操作默认等待间隔（秒）"""

LOGIN_RETRY_WAIT: float = 3.0
"""登录重试等待间隔（秒）"""

SIMULATION_RETRY_WAIT: float = 3.0
"""模拟各阶段重试等待间隔（秒），略高于默认值以应对 API 排队"""

POLLING_RETRY_BUFFER: float = 0.5
"""轮询重试缓冲时间（秒），附加在 Retry-After 值上"""


# ============================================================================
# 模拟默认参数
# ============================================================================

SIMULATION_DEFAULT_START_DATE: str = "2019-01-01"
"""模拟默认开始日期"""

SIMULATION_DEFAULT_END_DATE: str = "2023-12-31"
"""模拟默认结束日期"""


# ============================================================================
# Stats 分析哨兵值
# ============================================================================

STATS_DEFAULT_SCORE: float = -999.0
"""stats 分析中 best_score / field_priority 的默认哨兵值"""

STATS_FAILED_CHECK_DEFAULT_SCORE: float = -10.0
"""stats 分析中失败检查的默认评分"""

STATS_NEARPASS_SUMMARY_LIMIT: int = 20
"""compile_near_pass_summary 默认返回的候选数量上限"""

STATS_PERFORMANCE_TOP_N: int = 10
"""compile_template_performance_summary / compile_field_performance_summary 默认截断数量"""


# ============================================================================
# 通用哨兵值与 API 响应键名常量
# ============================================================================

SENTINEL_UNKNOWN: str = "UNKNOWN"
"""当字段 id/name/type 等无法解析时使用的哨兵值"""

SENTINEL_UNKNOWN_CHECK: str = "UNKNOWN"
"""当检查项 name 无法解析时使用的哨兵值"""

SENTINEL_UNKNOWN_STATUS: str = "unknown"
"""当结果 status 无法解析时使用的哨兵值"""

API_KEY_DETAIL: str = "detail"
API_KEY_ERROR: str = "error"
API_KEY_MESSAGE: str = "message"
API_KEY_STATUS: str = "status"
API_KEY_FAILED: str = "failed"
API_KEY_PROGRESS: str = "progress"
API_KEY_STATE: str = "state"

STATUS_SUBMITTED: str = "submitted"
"""submit 成功状态字符串"""

STATUS_SIMULATED: str = "simulated"
"""模拟成功但未提交状态字符串"""

STATUS_ERROR: str = "error"
"""错误状态字符串"""

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

# ============================================================================
# 表达式家族分类常量
# ============================================================================

UNKNOWN_FAMILY: str = "other"
"""classify_expression_family 中无法匹配任何已知模式时的默认家族名"""


# ============================================================================
# 数据字段分类配置
# ============================================================================

RATIO_PARTNER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "debt": ("cap", "fnd6_mkvalt", "fnd6_mkvaltq", "assets", "equity", "enterprise_value"),
    "debt_lt": ("fnd6_mkvalt", "fnd6_mkvaltq", "assets", "equity", "enterprise_value"),
    "debt_st": ("assets", "cash", "cash_st", "fnd6_mkvalt"),
    "assets_curr": ("cash_st", "debt_st", "liabilities_curr"),
    "liabilities": ("assets", "equity", "fnd6_mkvalt", "fnd6_mkvaltq", "cap", "liabilities_curr"),
    "liabilities_curr": ("assets", "equity", "fnd6_mkvalt", "fnd6_mkvaltq"),
    "cash": ("assets", "debt", "liabilities"),
    "cash_st": ("assets_curr", "assets", "debt_st"),
    "cashflow": ("assets", "enterprise_value", "fnd6_mkvalt", "fnd6_mkvaltq"),
    "cashflow_op": ("fnd6_mkvalt", "fnd6_mkvaltq", "assets", "debt", "enterprise_value"),
    "cashflow_invst": ("assets", "enterprise_value", "capex"),
    "cashflow_fin": ("assets", "debt", "equity"),
    "capex": ("assets", "cashflow_op", "enterprise_value"),
    "cogs": ("assets", "cash", "fnd6_mkvalt", "fnd6_mkvaltq"),
    "current_ratio": ("cash_st", "debt_st", "liabilities_curr"),
    "ebit": ("assets", "enterprise_value"),
    "ebitda": ("assets", "enterprise_value"),
    "equity": ("assets", "enterprise_value"),
    "enterprise_value": ("assets", "ebitda", "cashflow_op"),
}
"""
比率型 Alpha 的候选配对字段映射

这些映射关系用于在构建比率型 Alpha 表达式时，为特定字段推荐
最合适的配对字段作为分母。例如，debt（债务）字段通常与
cap（市值）、assets（资产）等字段组合构建比率。
"""

RATIO_KEYWORDS: dict[str, tuple[str, ...]] = {
    "debt": ("cap", "assets", "equity", "enterprise_value", "liabilities"),
    "liabilities": ("assets", "equity", "cap", "enterprise_value"),
    "cash": ("debt", "liabilities", "assets", "enterprise_value"),
    "cash_st": ("assets_curr", "assets", "debt_st", "liabilities_curr"),
    "cashflow": ("assets", "enterprise_value", "debt"),
    "cashflow_op": ("assets", "enterprise_value", "debt", "fnd6_mkvalt", "fnd6_mkvaltq"),
    "cashflow_invst": ("assets", "enterprise_value", "capex"),
    "cashflow_fin": ("assets", "debt", "equity"),
    "capex": ("cashflow_op", "assets", "enterprise_value", "cashflow_invst"),
    "cogs": ("assets", "cash", "enterprise_value"),
    "ebit": ("assets", "enterprise_value", "sales", "revenue"),
    "ebitda": ("assets", "enterprise_value", "sales", "revenue"),
    "equity": ("assets", "enterprise_value", "debt"),
    "enterprise_value": ("assets", "ebitda", "ebit", "cashflow_op"),
    "assets": ("debt", "liabilities", "equity", "cash", "enterprise_value"),
}
"""
字段的关键词关联映射

用于在字段名称中查找关键词时，推荐相关的配对字段。
"""

POSITIVE_RAW_FIELDS: set = {
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
"""
预期为正值的原始字段集合

这些字段在正常情况下应该为正值。在构建 Alpha 表达式时，
对这些字段进行对数变换或其他数学运算时不需要额外处理负值。
"""

NEGATIVE_RAW_FIELDS: set = {
    "cogs",
    "debt",
    "debt_lt",
    "debt_st",
    "liabilities",
}
"""
预期为负值的原始字段集合

这些字段在正常情况下为负值（如成本、负债等）。
在构建 Alpha 表达式时可能需要特殊处理。
"""


# ============================================================================
# 数据集自适应配置 (Dataset Profiles)
# ============================================================================
# 每个数据集有不同的字段数、Value Score、限流风险，应有不同的运行参数。
# 键名为 dataset_id，未匹配的数据集使用 DEFAULT_PROFILE。
#
# 字段说明:
#   min_request_interval:       API 请求最小间隔（秒），字段多应增大
#   sleep_between_fields:       字段间休眠（秒）
#   max_concurrent_simulations: 最大并发模拟数
#   max_templates_per_field:    每字段最大模板数（0=全部）
#   simulation_max_wait_seconds:单个模拟最大等待时间（秒）
#   simulation_max_queue_seconds:模拟排队最大等待时间（秒）
#   queue_busy_cooldown_seconds: 队列繁忙冷却时间（秒）
#   template_disable_after:     模板禁用阈值（0=不自动剪枝）

from typing import Any

DATASET_PROFILES: dict[str, dict[str, Any]] = {}
"""数据集专属配置已迁移至 settings.yaml (dataset_profiles 段)。
此处保留空字典以确保向后兼容，代码仅从 YAML 读取。
如需添加/修改数据集参数，请编辑 settings.yaml 而非此文件。"""

# 默认配置（未在 settings.yaml dataset_profiles 中匹配时使用）
DEFAULT_PROFILE: dict[str, Any] = {
    "min_request_interval": 2.0,
    "sleep_between_fields": 5.0,
    "max_concurrent_simulations": 1,
    "max_templates_per_field": 12,
    "simulation_max_wait_seconds": 900,
    "simulation_max_queue_seconds": 600,
    "queue_busy_cooldown_seconds": 120,
    "template_disable_after": 12,
}


def get_dataset_profile(dataset_id: str, yaml_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """返回指定数据集的运行参数配置。

    优先级：YAML dataset_profiles > DEFAULT_PROFILE
    所有数据集专属参数统一在 settings.yaml 的 dataset_profiles 段维护。

    Args:
        dataset_id: 数据集 ID，如 "model51", "pv1", "fundamental6"。
        yaml_config: 从 YAML 加载的配置字典（可选）。

    Returns:
        dict: 该数据集的参数配置；未匹配时返回默认配置。
    """
    profile = dict(DEFAULT_PROFILE)

    # 从 YAML 读取数据集专属配置（唯一来源）
    if yaml_config:
        yaml_profiles = yaml_config.get("dataset_profiles", {})
        if isinstance(yaml_profiles, dict):
            yaml_profile = yaml_profiles.get(dataset_id)
            if isinstance(yaml_profile, dict):
                profile.update(yaml_profile)

    return profile


def get_yaml_config(config_path: str = "") -> dict[str, Any]:
    """获取 YAML 配置（带缓存）。

    仅在首次调用时加载文件，之后返回缓存。

    Args:
        config_path: YAML 配置文件路径。为空时自动搜索。

    Returns:
        dict: 解析后的配置字典。
    """
    cache_attr = "_yaml_config_cache"
    cache_key = os.path.abspath(config_path) if config_path else "__auto__"
    cache = getattr(get_yaml_config, cache_attr, {})  # type: ignore[attr-defined]
    if cache_key in cache:
        return cache[cache_key]
    data = load_yaml_config(config_path)
    cache[cache_key] = data
    setattr(get_yaml_config, cache_attr, cache)
    return data


def apply_yaml_global_defaults(
    args: Any,
    yaml_config: dict[str, Any] | None = None,
    explicit_cli_keys: set[str] | None = None,
) -> None:
    """将 YAML global 默认值应用到 argparse namespace 上（CLI 未显式传参时）。

    仅当 argparse 值仍然是代码默认值时才会被 YAML 值覆盖。
    此函数在 parser.parse_args 之后调用，确保 CLI > YAML > 代码默认的优先级。

    覆盖所有 YAML global section，包括:
        dataset, simulation, limits, concurrency, retries,
        filters, quality, expression, runtime

    Args:
        args: argparse.Namespace 对象。
        yaml_config: YAML 配置字典。
    """
    if not yaml_config:
        return
    explicit_cli_keys = explicit_cli_keys or set()

    global_cfg = yaml_config.get("global", {})
    if not isinstance(global_cfg, dict):
        return

    # simulation settings —— YAML key 现在是 Brain API camelCase，需映射到 args snake_case
    _SIM_KEY_MAP = {
        "instrumentType": "instrument_type",
        "unitHandling": "unit_handling",
        "nanHandling": "nan_handling",
        "startDate": "start_date",
        "endDate": "end_date",
    }
    sim_section = global_cfg.get("simulation", {})
    if isinstance(sim_section, dict):
        for yaml_key, arg_key in _SIM_KEY_MAP.items():
            if yaml_key in sim_section and hasattr(args, arg_key) and arg_key not in explicit_cli_keys:
                setattr(args, arg_key, sim_section[yaml_key])
    # 不需要映射的 key (region, universe, delay, decay, neutralization, truncation,
    # pasteurization, language) — YAML key == args attr
    _merge_section(args, sim_section, {
        "region", "universe", "delay", "decay", "neutralization",
        "truncation", "pasteurization", "language",
    }, explicit_cli_keys)

    # limits (字段筛选)
    _merge_section(args, global_cfg.get("limits", {}), {
        "limit", "offset", "page_size", "sleep_between_fields",
        "max_templates_per_field", "max_templates_per_family",
        "legacy_similarity_penalty", "disable_legacy_after",
    }, explicit_cli_keys)

    # concurrency (并发)
    _merge_section(args, global_cfg.get("concurrency", {}), {
        "max_concurrent_simulations",
        "max_concurrent_creates",
    }, explicit_cli_keys)

    # retries (重试和超时)
    _merge_section(args, global_cfg.get("retries", {}), {
        "simulation_create_retries", "simulation_poll_retries",
        "simulation_max_polls", "simulation_max_wait_seconds",
        "simulation_max_pending_cycles", "simulation_max_queue_seconds",
        "queue_busy_cooldown_seconds", "field_queue_busy_skip_after",
        "check_submit_retries", "submit_retries",
        "rate_limit_max_retries", "login_retries", "min_request_interval",
    }, explicit_cli_keys)

    # filters
    _merge_section(args, global_cfg.get("filters", {}), {
        "template_disable_after", "top_fields_by_feedback",
        "stop_after_submittable",
    }, explicit_cli_keys)

    # quality (质量阈值)
    _merge_section(args, global_cfg.get("quality", {}), {
        "min_sharpe", "min_fitness", "min_turnover",
        "max_turnover", "max_weight",
    }, explicit_cli_keys)

    # expression (表达式生成)
    _merge_section(args, global_cfg.get("expression", {}), {
        "backfill_window",
    }, explicit_cli_keys)

    # runtime (运行时开关)
    _merge_section(args, global_cfg.get("runtime", {}), {
        "submit", "auto_update_blacklist", "smoke_test", "dry_run_plan", "full_run",
        "verbose", "quiet",
    }, explicit_cli_keys)


def _merge_section(
    args: Any,
    section: dict[str, Any],
    keys: set[str],
    explicit_cli_keys: set[str] | None = None,
) -> None:
    """将 YAML section 中的值合并到 args（仅当 key 在 section 中存在时）。"""
    if not isinstance(section, dict):
        return
    explicit_cli_keys = explicit_cli_keys or set()
    for key in keys:
        if key in section and hasattr(args, key) and key not in explicit_cli_keys:
            setattr(args, key, section[key])


# ============================================================================
# YAML 驱动的 getter 函数 (用于模块级别常量替代)
# ============================================================================
# 这些函数允许运行时模块动态读取 YAML 配置，而非硬编码常量。
# 用法: 将 from ..config import CONSTANT 替换为 from ..config import get_CONSTANT()
# 未配置 YAML 时回退到模块级别的代码默认值。


def _yaml_global_section(section: str) -> dict[str, Any]:
    """获取 YAML global 下的指定 section（如果已加载）。

    Args:
        section: section 名称，如 "http", "feedback"。

    Returns:
        dict: section 字典，未找到时返回空字典。
    """
    yaml_cfg = get_yaml_config()
    if not yaml_cfg:
        return {}
    global_cfg = yaml_cfg.get("global", {})
    if not isinstance(global_cfg, dict):
        return {}
    sect = global_cfg.get(section, {})
    return sect if isinstance(sect, dict) else {}


def _yaml_get(section: str, key: str, default: Any) -> Any:
    """从 YAML global.<section>.<key> 读取值，无则返回 default。

    Args:
        section: section 名称。
        key: 键名。
        default: 代码默认值。

    Returns:
        配置值。
    """
    sect = _yaml_global_section(section)
    return sect.get(key, default)


def get_http_request_timeout() -> float:
    """HTTP 请求超时时间（秒）。"""
    return float(_yaml_get("http", "request_timeout", HTTP_REQUEST_TIMEOUT))


def get_rate_limit_default_wait() -> float:
    """速率限制默认等待时间（秒）。"""
    return float(_yaml_get("http", "rate_limit_default_wait", RATE_LIMIT_DEFAULT_WAIT))


def get_polling_default_wait() -> float:
    """轮询默认等待间隔（秒）。"""
    return float(_yaml_get("http", "polling_default_wait", POLLING_DEFAULT_WAIT))


def get_polling_no_retry_after_wait() -> float:
    """无 Retry-After 头时的轮询等待间隔（秒）。"""
    return float(_yaml_get("http", "polling_no_retry_after_wait", POLLING_NO_RETRY_AFTER_WAIT))


def get_server_error_backoff_max() -> float:
    """服务器错误退避最大等待（秒）。"""
    return float(_yaml_get("http", "server_error_backoff_max", SERVER_ERROR_BACKOFF_MAX))


def get_server_error_backoff_step() -> float:
    """服务器错误退避步长（秒/次）。"""
    return float(_yaml_get("http", "server_error_backoff_step", SERVER_ERROR_BACKOFF_STEP))


def get_retry_operation_default_wait() -> float:
    """重试操作默认等待（秒）。"""
    return float(_yaml_get("http", "retry_operation_default_wait", RETRY_OPERATION_DEFAULT_WAIT))


def get_login_retry_wait() -> float:
    """登录重试等待（秒）。"""
    return float(_yaml_get("http", "login_retry_wait", LOGIN_RETRY_WAIT))


def get_simulation_retry_wait() -> float:
    """模拟重试等待（秒）。"""
    return float(_yaml_get("http", "simulation_retry_wait", SIMULATION_RETRY_WAIT))


def get_polling_retry_buffer() -> float:
    """轮询重试缓冲（秒）。"""
    return float(_yaml_get("http", "polling_retry_buffer", POLLING_RETRY_BUFFER))


def get_settings_variant_budget_high() -> float:
    """settings 变体预算高分阈值。"""
    return float(_yaml_get("feedback", "settings_variant_budget_high", SETTINGS_VARIANT_BUDGET_HIGH))


def get_settings_variant_budget_mid() -> float:
    """settings 变体预算中分阈值。"""
    return float(_yaml_get("feedback", "settings_variant_budget_mid", SETTINGS_VARIANT_BUDGET_MID))


def get_feedback_mutation_nearpass_threshold() -> float:
    """反馈变异 - 接近通过阈值。"""
    return float(_yaml_get("feedback", "feedback_mutation_nearpass_threshold", FEEDBACK_MUTATION_NEARPASS_THRESHOLD))


def get_feedback_mutation_highscore_threshold() -> float:
    """反馈变异 - 高分阈值。"""
    return float(_yaml_get("feedback", "feedback_mutation_highscore_threshold", FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD))


def get_feedback_template_min_priority() -> int:
    """反馈剪枝最低优先级。"""
    return int(_yaml_get("feedback", "feedback_template_min_priority", FEEDBACK_TEMPLATE_MIN_PRIORITY))


def get_delta_std_priority_boost() -> int:
    """delta/std 模板优先级加成。"""
    return int(_yaml_get("feedback", "delta_std_priority_boost", DELTA_STD_PRIORITY_BOOST))


def get_settings_nearpass_threshold() -> float:
    """settings nearpass 阈值。"""
    return float(_yaml_get("feedback", "settings_nearpass_threshold", SETTINGS_NEARPASS_THRESHOLD))


def get_settings_close_threshold() -> float:
    """settings close 阈值。"""
    return float(_yaml_get("feedback", "settings_close_threshold", SETTINGS_CLOSE_THRESHOLD))


def get_expr_nearpass_boost_threshold() -> float:
    """表达式 nearpass 大幅加分阈值。"""
    return float(_yaml_get("feedback", "expr_nearpass_boost_threshold", EXPR_NEARPASS_BOOST_THRESHOLD))


def get_expr_iter_boost_threshold() -> float:
    """表达式 iter 加分阈值。"""
    return float(_yaml_get("feedback", "expr_iter_boost_threshold", EXPR_ITER_BOOST_THRESHOLD))


def get_expr_ratio_penalty_threshold() -> float:
    """表达式 ratio 惩罚阈值。"""
    return float(_yaml_get("feedback", "expr_ratio_penalty_threshold", EXPR_RATIO_PENALTY_THRESHOLD))


def get_expr_mutation_extend_threshold() -> float:
    """表达式变异扩展阈值。"""
    return float(_yaml_get("feedback", "expr_mutation_extend_threshold", EXPR_MUTATION_EXTEND_THRESHOLD))


def get_backfill_window() -> int:
    """ts_backfill 时间窗口（天）。"""
    return int(_yaml_get("expression", "backfill_window", BACKFILL_WINDOW))


def get_simulation_default_start_date() -> str:
    """模拟默认开始日期。"""
    return str(_yaml_get("simulation", "start_date", SIMULATION_DEFAULT_START_DATE))


def get_simulation_default_end_date() -> str:
    """模拟默认结束日期。"""
    return str(_yaml_get("simulation", "end_date", SIMULATION_DEFAULT_END_DATE))


def get_precheck_fallback_min_sharpe() -> float:
    """预检 fallback Sharpe。"""
    return float(_yaml_get("quality", "min_sharpe", PRECHECK_FALLBACK_MIN_SHARPE))


def get_precheck_fallback_min_fitness() -> float:
    """预检 fallback Fitness。"""
    return float(_yaml_get("quality", "min_fitness", PRECHECK_FALLBACK_MIN_FITNESS))


def get_precheck_fallback_min_turnover() -> float:
    """预检 fallback 最小 Turnover。"""
    return float(_yaml_get("quality", "min_turnover", PRECHECK_FALLBACK_MIN_TURNOVER))


def get_precheck_fallback_max_turnover() -> float:
    """预检 fallback 最大 Turnover。"""
    return float(_yaml_get("quality", "max_turnover", PRECHECK_FALLBACK_MAX_TURNOVER))


def get_precheck_fallback_max_weight() -> float:
    """预检 fallback 最大权重。"""
    return float(_yaml_get("quality", "max_weight", PRECHECK_FALLBACK_MAX_WEIGHT))


def get_submit_min_sharpe() -> float:
    """提交最小 Sharpe。"""
    return float(_yaml_get("quality", "min_sharpe", SUBMIT_MIN_SHARPE))


def get_submit_min_fitness() -> float:
    """提交最小 Fitness。"""
    return float(_yaml_get("quality", "min_fitness", SUBMIT_MIN_FITNESS))


def get_submit_min_turnover() -> float:
    """提交最小 Turnover。"""
    return float(_yaml_get("quality", "min_turnover", SUBMIT_MIN_TURNOVER))


def get_submit_max_turnover() -> float:
    """提交最大 Turnover。"""
    return float(_yaml_get("quality", "max_turnover", SUBMIT_MAX_TURNOVER))


def get_submit_max_weight() -> float:
    """提交最大权重。"""
    return float(_yaml_get("quality", "max_weight", SUBMIT_MAX_WEIGHT))


# ============================================================================
# 辅助函数
# ============================================================================


def use_fundamental6_heuristics(dataset_id: str = "fundamental6") -> bool:
    """
    判断是否应该使用 fundamental6 数据集的启发式规则。

    启发式规则包括针对 fundamental6 数据集的特定优化，
    如字段配对发现、相似度惩罚等。

    Args:
        dataset_id (str): 数据集 ID。默认为 "fundamental6"。

    Returns:
        bool: 如果数据集为 fundamental6 或包含 fundamental6 关键词，返回 True；
              否则返回 False。

    Example:
        >>> if use_fundamental6_heuristics("fundamental6"):
        ...     print("使用 fundamental6 启发式规则")

    Note:
        - fundamental6 是主要的数据集，有丰富的历史优化经验
        - 其他数据集可能没有相同的启发式规则支持
    """
    return dataset_id == "fundamental6" or "fundamental6" in dataset_id.lower()
