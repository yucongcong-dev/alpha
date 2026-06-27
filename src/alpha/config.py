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

SUBMIT_MIN_FITNESS: float = 0.50
"""提交要求的最低 Fitness 值（放宽）。Fitness = Sharpe × Turnover 惩罚调整，综合衡量风险调整后收益。"""

SUBMIT_MIN_SHARPE: float = 0.85
"""提交要求的最低 Sharpe 值（放宽）。衡量单位风险带来的超额收益。"""

SUBMIT_MIN_TURNOVER: float = 0.005
"""提交要求的最低 Turnover（0.5%）。换手率过低意味着信号过于稳定，缺乏交易机会。"""

SUBMIT_MAX_TURNOVER: float = 0.75
"""提交要求的最高 Turnover（75%）。换手率过高意味着交易过于频繁，交易成本侵蚀收益。"""

SUBMIT_MAX_WEIGHT: float = 0.13
"""提交要求的单股最大权重上限（13%）。防止权重过度集中在少数股票上。"""

# ============================================================================
# 表达式生成器配置
# ============================================================================

BACKFILL_WINDOW: int = 240
"""ts_backfill 默认时间窗口（天）。更大的窗口能捕捉更多历史数据，提升信号稳定性。"""


# ============================================================================
# 模拟预检 fallback 阈值
# ============================================================================

PRECHECK_FALLBACK_MIN_SHARPE: float = 0.85
"""precheck_simulation_metrics 的最小 Sharpe fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MIN_FITNESS: float = 0.50
"""precheck_simulation_metrics 的最小 Fitness fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MIN_TURNOVER: float = 0.005
"""precheck_simulation_metrics 的最小 Turnover fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MAX_TURNOVER: float = 0.75
"""precheck_simulation_metrics 的最大 Turnover fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MAX_WEIGHT: float = 0.13
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

POLLING_NO_RETRY_AFTER_WAIT: float = 3.0
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

POLLING_RETRY_BUFFER: float = 1.0
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
    "liabilities": ("assets", "equity", "fnd6_mkvalt", "fnd6_mkvaltq", "cap", "liabilities_curr"),
    "liabilities_curr": ("assets", "equity", "fnd6_mkvalt", "fnd6_mkvaltq"),
    "cash": ("assets", "debt", "liabilities"),
    "cash_st": ("assets", "debt_st"),
    "cashflow": ("assets", "enterprise_value"),
    "cashflow_op": ("assets", "debt", "enterprise_value"),
    "capex": ("assets", "cashflow_op"),
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
    "cashflow": ("assets", "enterprise_value", "debt"),
    "cashflow_op": ("assets", "enterprise_value", "debt"),
    "capex": ("cashflow_op", "assets", "enterprise_value"),
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
