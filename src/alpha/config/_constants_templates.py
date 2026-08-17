"""模板优先级 + 比率生成配置 + Legacy Matrix 参数。

来源: config/templates.yaml 的 templates.* / ratio.* / partner.* 段。
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

# ---- Similarity 惩罚 ----
SIMILARITY_PENALTY_OFFSET_LEGACY_LEVEL: int = _yaml_int(
    "templates", "similarity_penalty_offset", "legacy_level", default=0
)
SIMILARITY_PENALTY_OFFSET_LEGACY_GROUP_LEVEL: int = _yaml_int(
    "templates", "similarity_penalty_offset", "legacy_group_level", default=6
)
SIMILARITY_PENALTY_OFFSET_LEGACY_RATIO: int = _yaml_int(
    "templates", "similarity_penalty_offset", "legacy_ratio", default=10
)
SIMILARITY_PENALTY_OFFSET_LEGACY_NEG_RATIO: int = _yaml_int(
    "templates", "similarity_penalty_offset", "legacy_neg_ratio", default=8
)
SIMILARITY_PENALTY_OFFSET_GROUP_RATIO_LEVEL: int = _yaml_int(
    "templates", "similarity_penalty_offset", "group_ratio_level", default=14
)

# ---- Legacy Matrix 模板优先级 ----
LEGACY_MATRIX_RAW_FIELD_PRIORITY: int = _yaml_int(
    "templates", "legacy_matrix", "raw_field", default=145
)
LEGACY_MATRIX_GROUP_RANK_SUBINDUSTRY_PRIORITY: int = _yaml_int(
    "templates", "legacy_matrix", "group_rank_subindustry", default=143
)
LEGACY_MATRIX_GROUP_RANK_INDUSTRY_PRIORITY: int = _yaml_int(
    "templates", "legacy_matrix", "group_rank_industry", default=141
)
LEGACY_MATRIX_RANK_RAW_FIELD_PRIORITY: int = _yaml_int(
    "templates", "legacy_matrix", "rank_raw_field", default=118
)
LEGACY_MATRIX_NEG_POSITIVE_RAW_PRIORITY: int = _yaml_int(
    "templates", "legacy_matrix", "neg_positive_raw", default=132
)
LEGACY_MATRIX_NEG_NEGATIVE_RAW_PRIORITY: int = _yaml_int(
    "templates", "legacy_matrix", "neg_negative_raw", default=144
)
LEGACY_MATRIX_NEG_DEFAULT_PRIORITY: int = _yaml_int(
    "templates", "legacy_matrix", "neg_default", default=128
)

# ---- Ratio 数据 ----
RATIO_PARTNER_CANDIDATES: dict[str, tuple[str, ...]] = _yaml_dict_tuple(
    "ratio", "partner_candidates"
) or {
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

NEGATIVE_RAW_FIELDS: set[str] = _yaml_set("ratio", "negative_raw_fields") or {
    "cogs",
    "debt",
    "debt_lt",
    "debt_st",
    "liabilities",
}

ALLOWED_EXTERNAL_RATIO_PARTNERS: set[str] = _yaml_set("ratio", "allowed_external_partners") or {
    "cap"
}

DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES: dict[str, int] = _yaml_dict(
    "ratio", "preferred_partner_score_bonuses"
) or {
    "assets": 15,
    "equity": 15,
    "debt": 15,
    "liabilities": 15,
    "cash": 15,
    "enterprise_value": 15,
    "cap": 15,
}

DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS: tuple[tuple[int, int, int], ...] = _yaml_tuple_int3(
    "ratio", "default_matrix_delta_over_std_windows"
) or (
    (5, 20, 176),
    (15, 40, 172),
    (10, 60, 170),
    (20, 60, 174),
    (25, 90, 168),
    (30, 120, 166),
)

DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = _yaml_tuple_str_int(
    "ratio", "default_matrix_diversified_template_specs"
) or (
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

DEFAULT_RATIO_DELTA_RANK_WINDOWS: tuple[tuple[int, int], ...] = _yaml_tuple_int2(
    "ratio", "default_ratio_delta_rank_windows"
) or ((3, 188), (5, 184), (10, 176))

DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS: tuple[tuple[int, int, int], ...] = _yaml_tuple_int3(
    "ratio", "default_ratio_delta_over_std_windows"
) or (
    (5, 20, 180),
    (15, 40, 176),
    (10, 60, 174),
    (20, 60, 178),
    (25, 90, 172),
    (30, 120, 170),
)

DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = _yaml_tuple_str_int(
    "ratio", "default_ratio_diversified_template_specs"
) or (
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

RATIO_LEGACY_TEMPLATE_SPECS: tuple[tuple[str, str, int], ...] = _yaml_tuple_str_int(
    "ratio", "legacy_template_specs"
) or (
    ("raw_ratio_{ratio_label}", "{ratio_expr}", 154),
    ("group_rank_ratio_{ratio_label}", "group_rank({ratio_expr}, subindustry)", 152),
    ("ratio_{ratio_label}", "rank({ratio_expr})", 148),
    (
        "decay_ratio_{ratio_label}",
        "rank(ts_decay_linear(ts_backfill({ratio_expr}, {backfill_window}), 63))",
        126,
    ),
)
