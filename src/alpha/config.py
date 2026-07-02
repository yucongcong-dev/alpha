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

from dataclasses import replace
from typing import Any

from .config_models import (
    DatasetExpressionPolicy,
    FeedbackLoopPolicy,
    FeedbackPhasePolicy,
    FieldTransformSpec,
    FieldTransformStage,
)
from .config_defaults import apply_yaml_global_defaults as apply_yaml_global_defaults
from .config_profiles import (
    DATASET_PROFILES as DATASET_PROFILES,
    DEFAULT_PROFILE as DEFAULT_PROFILE,
    get_dataset_profile as get_dataset_profile,
)
from .config_yaml import (
    _config_file_signature as _config_file_signature,
    _resolve_yaml_path as _resolve_yaml_path,
    get_yaml_config,
    load_yaml_config as load_yaml_config,
)

# ============================================================================
# YAML 配置文件支持
# ============================================================================


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

SUBMIT_MAX_TURNOVER: float = 0.70
"""提交要求的最高 Turnover（70%）。换手率过高意味着交易过于频繁，交易成本侵蚀收益。"""

SUBMIT_MAX_WEIGHT: float = 0.10
"""提交要求的单股最大权重上限（10%）。防止权重过度集中在少数股票上。"""

# ============================================================================
# 表达式生成器配置
# ============================================================================

BACKFILL_WINDOW: int = 240
"""ts_backfill 默认时间窗口（天）。更大的窗口能捕捉更多历史数据，提升信号稳定性。"""


def _tuple_tuple_int(value: Any, width: int) -> tuple[tuple[int, ...], ...]:
    """把 YAML 中的二维数值列表转换为 tuple[tuple[int, ...], ...]。"""
    if not isinstance(value, (list, tuple)):
        return ()
    rows: list[tuple[int, ...]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != width:
            continue
        try:
            rows.append(tuple(int(part) for part in item))
        except (TypeError, ValueError):
            continue
    return tuple(rows)


def _tuple_tuple_str_int(value: Any) -> tuple[tuple[str, str, int], ...]:
    """把 YAML 中的模板规格列表转换为 tuple[str, str, int] 序列。"""
    if not isinstance(value, (list, tuple)):
        return ()
    rows: list[tuple[str, str, int]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            continue
        name, expression, priority = item
        if not isinstance(name, str) or not isinstance(expression, str):
            continue
        try:
            rows.append((name, expression, int(priority)))
        except (TypeError, ValueError):
            continue
    return tuple(rows)


def _coerce_field_transform_stage(value: Any) -> FieldTransformStage | None:
    """把 YAML stage 条目转换为 FieldTransformStage。"""
    if not isinstance(value, dict):
        return None
    kind = str(value.get("kind", "")).strip()
    if not kind:
        return None
    try:
        window = int(value.get("window", 0) or 0)
    except (TypeError, ValueError):
        window = 0
    std_value = value.get("std")
    try:
        std = float(std_value) if std_value is not None else None
    except (TypeError, ValueError):
        std = None
    return FieldTransformStage(kind=kind, window=window, std=std)


def _coerce_field_transform_spec(value: Any) -> FieldTransformSpec | None:
    """把 YAML transform 配置转换为 FieldTransformSpec。"""
    if not isinstance(value, dict):
        return None
    stages_raw = value.get("stages", ())
    stages: list[FieldTransformStage] = []
    if isinstance(stages_raw, (list, tuple)):
        for item in stages_raw:
            stage = _coerce_field_transform_stage(item)
            if stage is not None:
                stages.append(stage)
    try:
        backfill_window = int(value.get("backfill_window", 0) or 0)
    except (TypeError, ValueError):
        backfill_window = 0
    winsorize_value = value.get("winsorize_std")
    try:
        winsorize_std = float(winsorize_value) if winsorize_value is not None else None
    except (TypeError, ValueError):
        winsorize_std = None
    return FieldTransformSpec(
        stages=tuple(stages),
        backfill_window=backfill_window,
        winsorize_std=winsorize_std,
    )


def _coerce_feedback_phase_policy(value: Any) -> FeedbackPhasePolicy | None:
    """把 YAML feedback phase 配置转换为 FeedbackPhasePolicy。"""
    if not isinstance(value, dict):
        return None
    preferred_raw = value.get("preferred_template_stages", ())
    preferred_template_stages = ()
    if isinstance(preferred_raw, (list, tuple)):
        preferred_template_stages = tuple(str(item) for item in preferred_raw if str(item).strip())
    try:
        min_attempted_templates = int(value.get("min_attempted_templates", 0) or 0)
    except (TypeError, ValueError):
        min_attempted_templates = 0
    try:
        min_best_score = float(value.get("min_best_score", STATS_DEFAULT_SCORE))
    except (TypeError, ValueError):
        min_best_score = STATS_DEFAULT_SCORE
    try:
        settings_variant_budget = int(value.get("settings_variant_budget", 3) or 3)
    except (TypeError, ValueError):
        settings_variant_budget = 3
    return FeedbackPhasePolicy(
        min_attempted_templates=min_attempted_templates,
        min_best_score=min_best_score,
        settings_variant_budget=settings_variant_budget,
        enable_template_pruning=bool(value.get("enable_template_pruning", False)),
        enable_resimulation_mutations=bool(value.get("enable_resimulation_mutations", False)),
        preferred_template_stages=preferred_template_stages,
    )


def _coerce_feedback_loop_policy(value: Any) -> FeedbackLoopPolicy | None:
    """把 YAML feedback loop 配置转换为 FeedbackLoopPolicy。"""
    if not isinstance(value, dict):
        return None
    generate = _coerce_feedback_phase_policy(value.get("generate"))
    prune = _coerce_feedback_phase_policy(value.get("prune"))
    resimulate = _coerce_feedback_phase_policy(value.get("resimulate"))
    if generate is None and prune is None and resimulate is None:
        return None
    return FeedbackLoopPolicy(
        generate=generate or FeedbackPhasePolicy(),
        prune=prune or FeedbackPhasePolicy(),
        resimulate=resimulate or FeedbackPhasePolicy(),
    )


def _policy_config_for_dataset(
    dataset_id: str,
    *,
    use_curated_heuristics: bool | None = None,
    yaml_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """读取数据集表达式策略的 YAML 覆盖项。

    支持三级声明式合并：
    1. expression_policies.__default__
    2. expression_policies.__curated__（仅 curated 数据集）
    3. expression_policies.<dataset_id>
    """
    config = yaml_config or get_yaml_config()
    section = config.get("expression_policies", {})
    if not isinstance(section, dict):
        return {}
    replace_list_keys = {"stages", "preferred_template_stages"}

    def merge_values(base: Any, override: Any, *, key: str = "") -> Any:
        if isinstance(base, dict) and isinstance(override, dict):
            merged_dict = dict(base)
            for child_key, value in override.items():
                merged_dict[child_key] = merge_values(
                    merged_dict.get(child_key),
                    value,
                    key=child_key,
                )
            return merged_dict
        if isinstance(base, list) and isinstance(override, list):
            if key in replace_list_keys:
                return list(override)
            return [*base, *override]
        if isinstance(base, tuple) and isinstance(override, tuple):
            if key in replace_list_keys:
                return tuple(override)
            return (*base, *override)
        return override

    merged: dict[str, Any] = {}
    default_cfg = section.get("__default__", {})
    if isinstance(default_cfg, dict):
        merged = merge_values(merged, default_cfg)
    if use_curated_heuristics:
        curated_cfg = section.get("__curated__", {})
        if isinstance(curated_cfg, dict):
            merged = merge_values(merged, curated_cfg)
    dataset_cfg = section.get(dataset_id, {})
    if isinstance(dataset_cfg, dict):
        merged = merge_values(merged, dataset_cfg)
    return merged


def _apply_yaml_expression_policy_overrides(
    policy: DatasetExpressionPolicy,
    *,
    dataset_id: str,
    use_curated_heuristics: bool | None = None,
    yaml_config: dict[str, Any] | None = None,
) -> DatasetExpressionPolicy:
    """把 settings.yaml 中的 expression_policies 覆盖项应用到策略对象。"""
    overrides = _policy_config_for_dataset(
        dataset_id,
        use_curated_heuristics=use_curated_heuristics,
        yaml_config=yaml_config,
    )
    if not overrides:
        return policy

    update_map: dict[str, Any] = {}
    set_fields = {
        "disabled_templates",
        "protected_templates",
        "positive_raw_fields",
        "negative_raw_fields",
        "overtested_weak_fields",
        "always_keep_families",
        "slow_template_names",
        "concentrated_weak_families",
        "concentrated_weak_names",
        "low_sharpe_weak_ratio_families",
        "weak_mean_spread_fields",
        "broken_zscore_spread_fields",
        "weak_ratio_standalone_fields",
        "event_allowed_template_families",
    }
    tuple_fields = {
        "blacklisted_template_name_substrings",
        "slow_template_prefixes",
        "concentrated_weak_prefixes",
        "low_sharpe_weak_ratio_prefixes",
        "event_field_prefixes",
        "event_allowed_template_stages",
        "event_allowed_template_prefixes",
    }
    dict_tuple_fields = {"ratio_partner_candidates", "ratio_keywords"}
    dict_int_fields = {
        "template_priority_penalties",
        "preferred_partner_score_bonuses",
        "preferred_field_order",
    }
    tuple_pair_fields = {"high_conviction_ratio_pairs"}
    tuple_window3_fields = {"matrix_delta_over_std_windows", "ratio_delta_over_std_windows"}
    tuple_window2_fields = {"ratio_delta_rank_windows"}
    template_spec_fields = {
        "matrix_diversified_template_specs",
        "ratio_diversified_template_specs",
        "ratio_legacy_template_specs",
    }
    transform_fields = {
        "default_field_transform",
        "matrix_field_transform",
        "vector_field_transform",
        "ratio_numerator_transform",
        "ratio_denominator_transform",
    }

    for key, value in overrides.items():
        if not hasattr(policy, key):
            continue
        if key in set_fields and isinstance(value, (list, tuple, set)):
            update_map[key] = {str(item) for item in value}
        elif key in tuple_fields and isinstance(value, (list, tuple)):
            update_map[key] = tuple(str(item) for item in value)
        elif key in dict_tuple_fields and isinstance(value, dict):
            update_map[key] = {
                str(name): tuple(str(item) for item in items)
                for name, items in value.items()
                if isinstance(items, (list, tuple))
            }
        elif key in dict_int_fields and isinstance(value, dict):
            coerced: dict[Any, int] = {}
            for name, score in value.items():
                try:
                    coerced[name] = int(score)
                except (TypeError, ValueError):
                    continue
            update_map[key] = coerced
        elif key == "template_prefix_penalties":
            coerced_prefix_penalties: dict[tuple[str, ...], int] = {}
            if isinstance(value, dict):
                for prefixes, score in value.items():
                    if isinstance(prefixes, str):
                        parsed_prefixes = tuple(
                            part.strip() for part in prefixes.split("|") if part.strip()
                        )
                    elif isinstance(prefixes, (list, tuple)):
                        parsed_prefixes = tuple(str(part).strip() for part in prefixes if str(part).strip())
                    else:
                        continue
                    if not parsed_prefixes:
                        continue
                    try:
                        coerced_prefix_penalties[parsed_prefixes] = int(score)
                    except (TypeError, ValueError):
                        continue
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    prefixes = item.get("prefixes", ())
                    penalty = item.get("penalty")
                    if isinstance(prefixes, str):
                        parsed_prefixes = tuple(
                            part.strip() for part in prefixes.split("|") if part.strip()
                        )
                    elif isinstance(prefixes, (list, tuple)):
                        parsed_prefixes = tuple(str(part).strip() for part in prefixes if str(part).strip())
                    else:
                        continue
                    if not parsed_prefixes:
                        continue
                    try:
                        coerced_prefix_penalties[parsed_prefixes] = int(penalty)
                    except (TypeError, ValueError):
                        continue
            update_map[key] = coerced_prefix_penalties
        elif key in tuple_pair_fields and isinstance(value, (list, tuple)):
            update_map[key] = {
                (str(item[0]), str(item[1]))
                for item in value
                if isinstance(item, (list, tuple)) and len(item) == 2
            }
        elif key in tuple_window3_fields:
            update_map[key] = _tuple_tuple_int(value, 3)
        elif key in tuple_window2_fields:
            update_map[key] = _tuple_tuple_int(value, 2)
        elif key in template_spec_fields:
            update_map[key] = _tuple_tuple_str_int(value)
        elif key in transform_fields:
            transform = _coerce_field_transform_spec(value)
            if transform is not None:
                update_map[key] = transform
        elif key == "feedback_loop_policy":
            loop_policy = _coerce_feedback_loop_policy(value)
            if loop_policy is not None:
                update_map[key] = loop_policy
        else:
            update_map[key] = value

    return replace(policy, **update_map)


def _base_curated_expression_policy(
    dataset_id: str,
    *,
    default_transform: FieldTransformSpec,
    matrix_transform: FieldTransformSpec,
    vector_transform: FieldTransformSpec,
    ratio_transform: FieldTransformSpec,
    feedback_loop_policy: FeedbackLoopPolicy,
) -> DatasetExpressionPolicy:
    """构建通用 curated policy，再由 YAML 注入数据集差异。"""
    return DatasetExpressionPolicy(
        dataset_id=dataset_id,
        use_curated_heuristics=True,
        partner_limit=4,
        matrix_delta_over_std_windows=DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS,
        matrix_diversified_template_specs=DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS,
        ratio_delta_rank_windows=DEFAULT_RATIO_DELTA_RANK_WINDOWS,
        ratio_delta_over_std_windows=DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS,
        ratio_diversified_template_specs=DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS,
        ratio_legacy_template_specs=RATIO_LEGACY_TEMPLATE_SPECS,
        positive_raw_fields=set(POSITIVE_RAW_FIELDS),
        negative_raw_fields=set(NEGATIVE_RAW_FIELDS),
        ratio_partner_candidates=dict(RATIO_PARTNER_CANDIDATES),
        ratio_keywords=dict(RATIO_KEYWORDS),
        preferred_partner_score_bonuses=dict(DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES),
        default_field_transform=default_transform,
        matrix_field_transform=matrix_transform,
        vector_field_transform=vector_transform,
        ratio_numerator_transform=ratio_transform,
        ratio_denominator_transform=ratio_transform,
        feedback_loop_policy=feedback_loop_policy,
    )


# ============================================================================
# 模拟预检 fallback 阈值
# ============================================================================

PRECHECK_FALLBACK_MIN_SHARPE: float = 1.25
"""precheck_simulation_metrics 的最小 Sharpe fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MIN_FITNESS: float = 1.00
"""precheck_simulation_metrics 的最小 Fitness fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MIN_TURNOVER: float = 0.01
"""precheck_simulation_metrics 的最小 Turnover fallback（当 CLI 未提供时）"""

PRECHECK_FALLBACK_MAX_TURNOVER: float = 0.70
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

TEMPLATE_STAGE_FIRST_ORDER: str = "first_order"
TEMPLATE_STAGE_GROUP_SECOND_ORDER: str = "group_second_order"
TEMPLATE_STAGE_EVENT_CONDITIONED: str = "event_conditioned"

FEEDBACK_STAGE_GENERATE: str = "generate"
FEEDBACK_STAGE_PRUNE: str = "prune"
FEEDBACK_STAGE_RESIMULATE: str = "resimulate"


# ============================================================================
# 数据字段分类配置
# ============================================================================

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

ALLOWED_EXTERNAL_RATIO_PARTNERS: set[str] = {"cap"}
"""允许在当前 dataset 字段缓存之外直接生成的跨数据基础字段。"""

DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES: dict[str, int] = {
    "assets": 15,
    "equity": 15,
    "debt": 15,
    "liabilities": 15,
    "cash": 15,
    "enterprise_value": 15,
    "cap": 15,
}
"""通用 partner discovery 额外加分项。"""

DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS: tuple[tuple[int, int, int], ...] = (
    (5, 20, 176),
    (15, 40, 172),
    (10, 60, 170),
    (20, 60, 174),
    (25, 90, 168),
    (30, 120, 166),
)
"""非 fundamental6 数据集的 matrix delta/std 模板窗口。"""

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
"""非 fundamental6 数据集的额外 matrix diversified 模板。"""

DEFAULT_RATIO_DELTA_RANK_WINDOWS: tuple[tuple[int, int], ...] = (
    (3, 188),
    (5, 184),
    (10, 176),
)
"""非 fundamental6 数据集的 ratio delta-rank 窗口。"""

DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS: tuple[tuple[int, int, int], ...] = (
    (5, 20, 180),
    (15, 40, 176),
    (10, 60, 174),
    (20, 60, 178),
    (25, 90, 172),
    (30, 120, 170),
)
"""非 fundamental6 数据集的 ratio delta/std 窗口。"""

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
"""非 fundamental6 数据集的 ratio diversified 模板。"""

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
"""所有数据集通用的 ratio legacy 模板。"""

def get_dataset_expression_policy(
    dataset_id: str,
    *,
    use_curated_heuristics: bool | None = None,
) -> DatasetExpressionPolicy:
    """返回数据集表达式策略。

    expressions.py 只消费该策略对象，不再直接硬编码 fundamental6 细节。
    """
    default_transform = FieldTransformSpec()
    matrix_transform = FieldTransformSpec(
        stages=(FieldTransformStage(kind="backfill", window=BACKFILL_WINDOW),),
        backfill_window=BACKFILL_WINDOW,
    )
    vector_transform = FieldTransformSpec(
        stages=(FieldTransformStage(kind="backfill", window=BACKFILL_WINDOW),),
        backfill_window=BACKFILL_WINDOW,
    )
    ratio_transform = FieldTransformSpec(
        stages=(FieldTransformStage(kind="backfill", window=BACKFILL_WINDOW),),
        backfill_window=BACKFILL_WINDOW,
    )
    default_feedback_loop_policy = FeedbackLoopPolicy(
        generate=FeedbackPhasePolicy(
            min_attempted_templates=0,
            min_best_score=STATS_DEFAULT_SCORE,
            settings_variant_budget=1,
        ),
        prune=FeedbackPhasePolicy(
            min_attempted_templates=2,
            min_best_score=STATS_DEFAULT_SCORE,
            settings_variant_budget=2,
            enable_template_pruning=True,
        ),
        resimulate=FeedbackPhasePolicy(
            min_attempted_templates=3,
            min_best_score=FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
            settings_variant_budget=3,
            enable_template_pruning=True,
            enable_resimulation_mutations=True,
            preferred_template_stages=(
                TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                TEMPLATE_STAGE_EVENT_CONDITIONED,
            ),
        ),
    )

    if use_curated_heuristics is None:
        use_curated_heuristics = dataset_id == "fundamental6"

    if not use_curated_heuristics:
        return _apply_yaml_expression_policy_overrides(
            DatasetExpressionPolicy(
                dataset_id=dataset_id,
                use_curated_heuristics=False,
                partner_limit=4,
                matrix_delta_over_std_windows=DEFAULT_MATRIX_DELTA_OVER_STD_WINDOWS,
                matrix_diversified_template_specs=DEFAULT_MATRIX_DIVERSIFIED_TEMPLATE_SPECS,
                ratio_delta_rank_windows=DEFAULT_RATIO_DELTA_RANK_WINDOWS,
                ratio_delta_over_std_windows=DEFAULT_RATIO_DELTA_OVER_STD_WINDOWS,
                ratio_diversified_template_specs=DEFAULT_RATIO_DIVERSIFIED_TEMPLATE_SPECS,
                ratio_legacy_template_specs=RATIO_LEGACY_TEMPLATE_SPECS,
                ratio_partner_candidates=dict(RATIO_PARTNER_CANDIDATES),
                ratio_keywords=dict(RATIO_KEYWORDS),
                preferred_partner_score_bonuses=dict(DEFAULT_PREFERRED_PARTNER_SCORE_BONUSES),
                default_field_transform=default_transform,
                matrix_field_transform=matrix_transform,
                vector_field_transform=vector_transform,
                ratio_numerator_transform=ratio_transform,
                ratio_denominator_transform=ratio_transform,
                feedback_loop_policy=default_feedback_loop_policy,
            ),
            dataset_id=dataset_id,
            use_curated_heuristics=False,
        )

    return _apply_yaml_expression_policy_overrides(
        _base_curated_expression_policy(
            dataset_id,
            default_transform=default_transform,
            matrix_transform=matrix_transform,
            vector_transform=vector_transform,
            ratio_transform=ratio_transform,
            feedback_loop_policy=default_feedback_loop_policy,
        ),
        dataset_id=dataset_id,
        use_curated_heuristics=True,
    )


def resolve_feedback_stage(
    field_feedback: dict[str, Any] | None,
    loop_policy: FeedbackLoopPolicy,
) -> str:
    """根据历史反馈判断字段当前处于 generate / prune / resimulate 哪一阶段。"""
    if not field_feedback:
        return FEEDBACK_STAGE_GENERATE
    attempted = int(field_feedback.get(STAT_FIELD_ATTEMPTED_TEMPLATES, 0))
    best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))
    if (
        attempted >= loop_policy.resimulate.min_attempted_templates
        and best_score >= loop_policy.resimulate.min_best_score
    ):
        return FEEDBACK_STAGE_RESIMULATE
    if (
        attempted >= loop_policy.prune.min_attempted_templates
        and best_score >= loop_policy.prune.min_best_score
    ):
        return FEEDBACK_STAGE_PRUNE
    return FEEDBACK_STAGE_GENERATE


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
