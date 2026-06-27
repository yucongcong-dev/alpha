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

from typing import Dict, List, Tuple

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

VERSION_HEADER: Dict[str, str] = {"Accept": "application/json;version=2.0"}
"""数据字段查询专用的 Accept 请求头，包含版本信息"""

SIM_ACCEPT_HEADER: Dict[str, str] = {"Accept": "application/json;version=3.0"}
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

SUBMIT_MAX_SELF_CORRELATION: float = 0.75
"""提交要求的最大自相关性。与已提交 Alpha 相关性超过此值会被拒绝。"""


# ============================================================================
# 表达式生成器配置
# ============================================================================

BACKFILL_WINDOW: int = 240
"""ts_backfill 默认时间窗口（天）。更大的窗口能捕捉更多历史数据，提升信号稳定性。"""


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

DELTA_STD_MIN_WINDOWS: int = 6
"""delta/std 比率模板的最小窗口变体数量"""


# ============================================================================
# 数据字段分类配置
# ============================================================================

RATIO_KEYWORDS_IN_NAME: List[str] = [
    "ratio",
    "margin",
    "yield",
    "return",
    "turnover",
]
"""
比率类型字段的识别关键词列表

当字段名称包含这些关键词时，系统可以判断该字段可能已经是比率类型，
从而在构建新的 Alpha 表达式时避免不必要的比率计算。
"""

RATIO_PARTNER_CANDIDATES: Dict[str, Tuple[str, ...]] = {
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

RATIO_KEYWORDS: Dict[str, Tuple[str, ...]] = {
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
