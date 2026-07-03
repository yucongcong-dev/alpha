"""模板优先级 + 比率生成配置 + Legacy Matrix 参数。

来源: config/constants_defaults.yaml 的 templates.* / ratio.* 段。
"""

from __future__ import annotations

from ._constants_core import (
    _yaml_dict,
    _yaml_dict_tuple,
    _yaml_int,
    _yaml_set,
    _yaml_tuple_int2,
    _yaml_tuple_int3,
    _yaml_tuple_str_int,
)

# ---- 模板禁用阈值 ----
TEMPLATE_DISABLE_MIN_SIMULATED: int = _yaml_int("templates", "disable", "min_simulated", default=3)
TEMPLATE_DISABLE_MIN_LOW_SHARPE: int = _yaml_int("templates", "disable", "min_low_sharpe", default=3)
TEMPLATE_DISABLE_MIN_LOW_FITNESS: int = _yaml_int("templates", "disable", "min_low_fitness", default=3)
TEMPLATE_DISABLE_MIN_CONCENTRATED_WEIGHT: int = _yaml_int("templates", "disable", "min_concentrated_weight", default=2)

# ---- 模板优先级调整辅助 ----
def _pa(key: str, default: int) -> int:
    return _yaml_int("templates", "priority_adj", key, default=default)

# ---- Similarity 惩罚 ----
SIMILARITY_PENALTY_OFFSET_LEGACY_LEVEL: int = _yaml_int("templates", "similarity_penalty_offset", "legacy_level", default=0)
SIMILARITY_PENALTY_OFFSET_LEGACY_GROUP_LEVEL: int = _yaml_int("templates", "similarity_penalty_offset", "legacy_group_level", default=6)
SIMILARITY_PENALTY_OFFSET_LEGACY_RATIO: int = _yaml_int("templates", "similarity_penalty_offset", "legacy_ratio", default=10)
SIMILARITY_PENALTY_OFFSET_LEGACY_NEG_RATIO: int = _yaml_int("templates", "similarity_penalty_offset", "legacy_neg_ratio", default=8)
SIMILARITY_PENALTY_OFFSET_GROUP_RATIO_LEVEL: int = _yaml_int("templates", "similarity_penalty_offset", "group_ratio_level", default=14)

# ---- 模板优先级调整 ----
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

# ---- Near-pass 精修优先级 ----
REFINE_PRIORITY_BASE: int = _yaml_int("templates", "refine_priority", "base", default=260)
REFINE_PRIORITY_STEP: int = _yaml_int("templates", "refine_priority", "step", default=12)
REFINE_PRIORITY_SUBINDUSTRY_DELTA: int = _yaml_int("templates", "refine_priority", "subindustry_delta", default=-2)
REFINE_PRIORITY_ZSCORE_DELTA: int = _yaml_int("templates", "refine_priority", "zscore_delta", default=-3)
REFINE_PRIORITY_TSRANK_DELTA: int = _yaml_int("templates", "refine_priority", "tsrank_delta", default=-4)
REFINE_PRIORITY_BACKFILL_DELTA: int = _yaml_int("templates", "refine_priority", "backfill_delta", default=-5)
REFINE_PRIORITY_TRADE_WHEN_DELTA: int = _yaml_int("templates", "refine_priority", "trade_when_delta", default=-6)
REFINE_PRIORITY_DECAY_DELTA: int = _yaml_int("templates", "refine_priority", "decay_delta", default=-7)

# ---- Legacy Matrix 模板优先级 ----
LEGACY_MATRIX_RAW_FIELD_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "raw_field", default=145)
LEGACY_MATRIX_GROUP_RANK_SUBINDUSTRY_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "group_rank_subindustry", default=143)
LEGACY_MATRIX_GROUP_RANK_INDUSTRY_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "group_rank_industry", default=141)
LEGACY_MATRIX_RANK_RAW_FIELD_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "rank_raw_field", default=118)
LEGACY_MATRIX_NEG_POSITIVE_RAW_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "neg_positive_raw", default=132)
LEGACY_MATRIX_NEG_NEGATIVE_RAW_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "neg_negative_raw", default=144)
LEGACY_MATRIX_NEG_DEFAULT_PRIORITY: int = _yaml_int("templates", "legacy_matrix", "neg_default", default=128)

# ---- Ratio 数据 ----
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
