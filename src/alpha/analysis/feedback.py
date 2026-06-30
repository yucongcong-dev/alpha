"""
历史迭代优化模块

本模块负责管理历史运行状态、基于反馈的迭代优化、
模板和字段的剪枝策略等。通过学习历史结果，
指导后续的搜索方向和优化策略。

模块内容：
    - classify_expression_family(template_name, expression) -> str: 表达式家族分类（委托 expressions 模块）
    - is_legacy_family(template_name, expression) -> bool: 判断是否为 legacy 家族（委托 expressions 模块）
    - build_historical_run_state(output_path, feedback_output_path) -> HistoricalRunState: 构建历史运行状态
    - choose_settings_variant_budget(field_feedback) -> int: 设置变体预算决策
    - should_stop_after_submittable(args, results) -> bool: 判断是否达到提交目标
    - is_template_disabled(template_name, disabled_templates) -> bool: 判断模板是否应禁用
    - is_legacy_family_disabled(template_name, expression, disabled_legacy_families) -> bool: 判断 legacy 家族是否禁用
    - should_keep_template_for_feedback(template_name, expression, ...) -> bool: 判断模板是否应保留
    - should_skip_field_template_family(field_id, template_name, ...) -> bool: 判断字段-模板组合是否应跳过
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from ..config import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    DatasetExpressionPolicy,
    FEEDBACK_TEMPLATE_MIN_PRIORITY,
    get_dataset_expression_policy,
)

# 从 expressions 模块导入分类函数（唯一源）
from ..generators.expressions import (
    _is_blacklisted_template,
    classify_expression_family,
    dominant_failed_check_names,
    is_legacy_family,
)
from ..models.base import FieldTestResult, HistoricalRunState

# 从 analysis 模块导入分析函数
from .stats import (
    attempted_template_keys,
    compile_field_feedback,
    compile_global_failed_check_counts,
    compile_template_stats,
    current_submittable_count,
    load_existing_results,
)

# ============================================================================
# 历史状态构建函数
# ============================================================================


def build_historical_run_state(output_path: str, feedback_output_path: str) -> HistoricalRunState:
    """
    加载历史结果并构建续跑与反馈所需的状态对象。

    从文件中加载历史运行结果，并派生出用于续跑和优化的状态信息，
    包括已尝试的组合键、模板统计、字段反馈、全局失败检查计数等。

    Args:
        output_path (str): 结果输出文件路径。
        feedback_output_path (str): 反馈输出文件路径。如果与 output_path 相同，
            使用同一个结果文件；否则加载单独的反馈文件。

    Returns:
        HistoricalRunState: 历史运行状态对象，包含：
            - existing_results: 已存在的历史结果列表
            - attempted_keys: 已尝试的组合键集合
            - template_stats: 模板统计字典
            - field_feedback: 字段反馈字典
            - global_failed_check_counts: 全局失败检查计数

    Example:
        >>> state = build_historical_run_state("results.json", "feedback.json")
        >>> print(len(state.existing_results))
        100
        >>> print(state.template_stats["ts_mean_20"])
        {'attempted': 10, 'submittable': 3, ...}
    """
    existing_results = load_existing_results(output_path)
    attempted_keys = attempted_template_keys(existing_results)
    template_stats = compile_template_stats(existing_results)
    feedback_results = (
        existing_results
        if feedback_output_path == output_path
        else load_existing_results(feedback_output_path)
    )
    field_feedback = compile_field_feedback(feedback_results)
    global_failed_check_counts = compile_global_failed_check_counts(feedback_results)
    return HistoricalRunState(
        existing_results=existing_results,
        attempted_keys=attempted_keys,
        template_stats=template_stats,
        field_feedback=field_feedback,
        global_failed_check_counts=global_failed_check_counts,
    )


def choose_settings_variant_budget(field_feedback: dict[str, Any] | None) -> int:
    """
    固定返回 3 组 settings 变体（精简后只有 3 组 always 变体）。

    参照网站已通过 alpha 的 settings 规律，不再需要评分驱动的预算决策。
    每个表达式固定尝试 decay=0/5/7, truncation=0.05/0.08, SUBINDUSTRY 的 3 组变体。

    Args:
        field_feedback (dict[str, Any] | None): 字段反馈字典（未使用，保留兼容）。

    Returns:
        int: 固定返回 3。
    """
    return 3


def should_stop_after_submittable(
    args: argparse.Namespace, results: Sequence[FieldTestResult]
) -> bool:
    """
    判断当前运行是否已达到要求的可提交数量上限。

    检查是否达到了用户设定的可提交 Alpha 数量目标，
    用于提前终止运行。

    Args:
        args (argparse.Namespace): 命令行参数对象，必须包含
            stop_after_submittable 字段（int 类型）。
        results (Sequence[FieldTestResult]): 当前运行结果序列。

    Returns:
        bool: 如果已达到目标返回 True，否则返回 False。

    判断条件：
        - args.stop_after_submittable > 0
        - current_submittable_count(results) >= args.stop_after_submittable

    Example:
        >>> # 设置目标为 5 个可提交 Alpha
        >>> args.stop_after_submittable = 5
        >>> if should_stop_after_submittable(args, results):
        ...     print("已达到目标，停止运行")
    """
    stop_threshold = args.stop_after_submittable
    if stop_threshold <= 0:
        return False
    current_count = current_submittable_count(results)
    return bool(current_count >= stop_threshold)


# ============================================================================
# 模板禁用判断函数
# ============================================================================


def is_template_disabled(
    template_name: str,
    template_stats: dict[str, dict[str, int]],
    disable_after: int,
) -> bool:
    """
    禁用历史尝试足够多但从未产生可提交结果的模板。

    当模板尝试次数达到阈值但仍无成功结果时，将其禁用
    以节省后续的队列预算。

    Args:
        template_name (str): 模板名称。
        template_stats (dict[str, dict[str, int]]): 模板统计字典，
            包含 attempted、submittable、simulated、low_sharpe 等字段。
        disable_after (int): 禁用阈值，尝试次数超过此值且无成功时禁用。
            如果 <= 0，不启用禁用逻辑。

    Returns:
        bool: 如果应该禁用返回 True，否则返回 False。

    禁用条件：
        - disable_after <= 0: 不禁用
        - 无统计信息: 不禁用
        - 模拟成功 >= 3 且无可提交且满足以下条件之一:
            - mean_spread 模板且低夏普/低适应性 >= 3
            - 权重集中 >= 2
        - 尝试次数 >= disable_after 且无可提交: 禁用

    Example:
        >>> if is_template_disabled("ts_mean_20", stats, disable_after=10):
        ...     print("该模板应被禁用")
    """
    if disable_after <= 0:
        return False
    stat = template_stats.get(template_name)
    if not stat:
        return False
    if (
        stat.get("simulated", 0) >= 3
        and stat.get("submittable", 0) == 0
        and (
            (
                "mean_spread" in template_name
                and stat.get("low_sharpe", 0) >= 3
                and stat.get("low_fitness", 0) >= 3
            )
            or stat.get("concentrated_weight", 0) >= 2
        )
    ):
        return True
    return stat["attempted"] >= disable_after and stat["submittable"] == 0


def is_legacy_family_disabled(
    template_name: str,
    expression: str,
    template_stats: dict[str, dict[str, int]],
    disable_after: int,
    *,
    template_metadata: dict[str, Any] | None = None,
) -> bool:
    """
    当整个 legacy 家族消耗过多预算却没有收益时进行禁用。

    当 legacy 家族的模板总体尝试次数过多但无成功结果时，
    禁用整个家族以节省队列预算。

    Args:
        template_name (str): 模板名称。
        expression (str): Alpha 表达式。
        template_stats (Dict[str, Dict[str, int]]): 模板统计字典。
        disable_after (int): 禁用阈值。如果 <= 0，不启用禁用逻辑。

    Returns:
        bool: 如果应该禁用 legacy 家族返回 True，否则返回 False。

    禁用条件：
        - disable_after <= 0: 不禁用
        - 不属于 legacy 家族: 不禁用
        - 所有 legacy 家族模板的尝试次数总和 >= disable_after
        - 所有 legacy 家族模板的可提交次数总和 == 0

    Example:
        >>> if is_legacy_family_disabled("raw_field", "sales", stats, disable_after=20):
        ...     print("legacy 家族应被禁用")
    """
    if disable_after <= 0 or not is_legacy_family(template_name, expression, template_metadata):
        return False
    attempted = 0
    submittable = 0
    for prior_template_name, stat in template_stats.items():
        prior_metadata = {}
        prior_family = stat.get("template_family")
        if isinstance(prior_family, str) and prior_family.strip():
            prior_metadata = {"family": prior_family}
        if not is_legacy_family(prior_template_name, "", prior_metadata):
            continue
        attempted += int(stat.get("attempted", 0))
        submittable += int(stat.get("submittable", 0))
    return attempted >= disable_after and submittable == 0


def _is_high_conviction_ratio(expression: str, policy: DatasetExpressionPolicy) -> bool:
    """识别策略中值得继续探索的高经济含义比值方向。"""
    lower_expr = expression.lower()
    return any(f"{left}/{right}" in lower_expr for left, right in policy.high_conviction_ratio_pairs)

# ============================================================================
# 模板保留判断函数
# ============================================================================


def should_keep_template_for_feedback(
    template_name: str,
    expression: str,
    priority: int,
    field_feedback: dict[str, Any] | None,
    *,
    dataset_id: str = "",
    expression_policy: DatasetExpressionPolicy | None = None,
    template_metadata: dict[str, Any] | None = None,
) -> bool:
    """
    在字段反馈足够后剪掉低信号、低价值的模板。

    当有足够的历史反馈时，根据失败检查的类型剪掉
    表现不佳的模板，保留有潜力的模板。

    Args:
        template_name (str): 模板名称。
        expression (str): Alpha 表达式。
        priority (int): 模板的当前优先级分数。
        field_feedback (dict[str, Any] | None): 字段反馈字典。

    Returns:
        bool: 如果应该保留模板返回 True，否则返回 False。

    保留规则：
        - 无反馈时: 保留所有模板
        - 属于 always_keep_families: 保留（如 group_rank_delta、group_zscore 等）
        - 以 iter_ 开头: 保留
        - 主导失败为 LOW_TURNOVER: 剪掉慢模板（ts_mean、backfill、sum 等）
        - 主导失败为权重集中/低子宇宙夏普: 剪掉 legacy 家族和比率模板
        - 其他情况: 仅保留优先级 >= 120 的模板

    Example:
        >>> if should_keep_template_for_feedback("ts_mean_20", "...", 100, feedback):
        ...     print("保留该模板")
    """
    # Once we have evidence about a field, aggressively cut low-signal and
    # low-turnover structures so queue budget stays on templates that can
    # actually move Sharpe/fitness.
    if not field_feedback:
        return True
    policy = expression_policy or get_dataset_expression_policy(dataset_id)

    dominant_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = dominant_failed_check_names(dominant_counts, limit=4)
    family = classify_expression_family(template_name, expression, template_metadata)
    lower_name = template_name.lower()
    lower_expr = expression.lower()

    if family in policy.always_keep_families:
        return True
    if lower_name.startswith("iter_"):
        return True
    if template_name in policy.protected_templates:
        return True
    protected_ratio = _is_high_conviction_ratio(expression, policy)

    # Historical results show these shapes are repeatedly too slow.
    if CHECK_LOW_TURNOVER in dominant_names:
        if lower_name.startswith(policy.slow_template_prefixes):
            return False
        if lower_name in policy.slow_template_names:
            return False
        if "ts_mean(" in lower_expr and "-" not in lower_expr and "/" not in lower_expr:
            return False
        if (
            "ts_backfill(" in lower_expr
            and "ts_delta" not in lower_expr
            and "ts_zscore" not in lower_expr
        ):
            return False

    # These shapes have repeatedly concentrated or broken sub-universe quality.
    if (
        CHECK_LOW_SUB_UNIVERSE_SHARPE in dominant_names
        or CHECK_CONCENTRATED_WEIGHT in dominant_names
    ):
        if family in policy.concentrated_weak_families and not protected_ratio:
            return False
        if lower_name.startswith(policy.concentrated_weak_prefixes) and not protected_ratio:
            return False
        if lower_name in policy.concentrated_weak_names:
            return False

    # Ratio-based templates consistently waste queue budget on fundamental6.
    # Once we have even 2+ simulated results showing LOW_SHARPE, cut all ratio families.
    field_low_sharpe = int(dominant_counts.get(CHECK_LOW_SHARPE, 0))
    if (
        field_low_sharpe >= policy.low_sharpe_ratio_fail_threshold
        and family in policy.low_sharpe_weak_ratio_families
        and not protected_ratio
    ):
        return False
    if (
        lower_name.startswith(policy.low_sharpe_weak_ratio_prefixes)
        and field_low_sharpe >= policy.low_sharpe_ratio_fail_threshold
        and not protected_ratio
    ):
        return False

    # Spread-type templates with severe HIGH_TURNOVER + CONCENTRATED_WEIGHT are doomed.
    if (
        CHECK_HIGH_TURNOVER in dominant_names
        and CHECK_CONCENTRATED_WEIGHT in dominant_names
        and family in {"rank_spread", "mean_spread"}
        and "zscore" in lower_name
        and "spread" in lower_name
    ):
        return False

    # In focused mode, keep only reasonably strong candidates.
    return priority >= FEEDBACK_TEMPLATE_MIN_PRIORITY


def should_skip_field_template_family(
    field_name: str,
    template_name: str,
    expression: str,
    *,
    use_dataset_heuristics: bool | None = None,
    dataset_id: str = "",
    expression_policy: DatasetExpressionPolicy | None = None,
    template_metadata: dict[str, Any] | None = None,
) -> bool:
    """
    对已经证明偏弱的字段-模板家族组合做先验剪枝。

    根据数据集的启发式规则，对特定的字段-模板组合进行剪枝，
    避免浪费队列预算在已知效果不佳的组合上。

    Args:
        field_name (str): 字段名称。
        template_name (str): 模板名称。
        expression (str): Alpha 表达式。
        use_dataset_heuristics (bool): 是否启用数据集启发式规则。
        dataset_id (str): 数据集 ID，用于按数据集过滤黑名单。

    Returns:
        bool: 如果应该跳过返回 True，否则返回 False。

    剪枝规则：
        - 不启用启发式规则: 不跳过
        - 特定字段在 mean_spread/rank_spread 家族: 跳过
          （如 assets、assets_curr、cash 等在 mean_spread 家族效果不佳）
        - 特定字段在 zscore_time/group_zscore 家族: 跳过
          （如 assets、assets_curr 在 zscore 家族效果不佳）

    Example:
        >>> if should_skip_field_template_family(
        ...     "assets", "mean_spread_5_20", "...", use_dataset_heuristics=True,
        ...     dataset_id="fundamental6"
        ... ):
        ...     print("跳过此字段-模板组合")
    """
    policy = expression_policy or get_dataset_expression_policy(
        dataset_id,
        use_curated_heuristics=use_dataset_heuristics,
    )
    if not policy.use_curated_heuristics:
        return False

    # v5: 检查黑名单 — 已淘汰模板立即跳过（按 dataset 分层）
    if _is_blacklisted_template(template_name, expression, policy=policy):
        return True

    family = classify_expression_family(template_name, expression, template_metadata)

    if field_name in policy.weak_mean_spread_fields and family in {
        "group_mean_spread",
        "mean_spread",
        "rank_spread",
    }:
        return True
    return (
        field_name in policy.broken_zscore_spread_fields
        and "zscore" in template_name.lower()
        and "spread" in template_name.lower()
    ) or (
        field_name in policy.weak_ratio_standalone_fields
        and family in {"legacy_ratio", "legacy_neg_ratio", "group_ratio_level"}
    )
