"""失败检查评分、排行榜、near-pass 汇总与优化建议。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    SENTINEL_UNKNOWN_CHECK,
    STATS_DEFAULT_SCORE,
    STATS_FAILED_CHECK_DEFAULT_SCORE,
    STATS_NEARPASS_SUMMARY_LIMIT,
)
from ..models.domain import FailedCheck, FieldTestResult, ResultRow
from .result_identity import is_queue_timeout_result


def score_failed_checks(failed_checks: Sequence[FailedCheck] | None) -> float:
    """根据失败检查项估计一个 Alpha 距离可提交状态还有多近。"""
    checks = list(failed_checks or [])
    if not checks:
        return STATS_FAILED_CHECK_DEFAULT_SCORE

    score = 0.0
    counted = 0
    for check in checks:
        closeness = failed_check_closeness(check)
        if closeness is None:
            continue
        counted += 1
        score += closeness
    if counted == 0:
        return STATS_FAILED_CHECK_DEFAULT_SCORE
    return score / counted


def failed_check_closeness(check: FailedCheck) -> float | None:
    """计算单个失败检查离通过阈值有多近，返回 0-1 左右的分数。"""
    value = check.get("value")
    limit = check.get("limit")
    if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)):
        return None
    gap = failed_check_gap(check)
    scale = max(abs(limit), 1e-9)
    if gap is None:
        return None
    return max(0.0, 1.0 - (gap / scale))


def failed_check_gap(check: FailedCheck) -> float | None:
    """计算失败检查到阈值的原始差距，正数表示还差多少。"""
    name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
    value = check.get("value")
    limit = check.get("limit")
    if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)):
        return None
    if name.startswith("LOW_"):
        return limit - value
    return value - limit


def summarize_failed_check(check: FailedCheck) -> ResultRow:
    """把失败检查转换成适合分析排序的紧凑结构。"""
    return {
        "name": check.get("name"),
        "value": check.get("value"),
        "limit": check.get("limit"),
        "gap": failed_check_gap(check),
        "closeness": failed_check_closeness(check),
    }


def compile_failed_check_leaderboard(results: Sequence[FieldTestResult]) -> list[dict[str, Any]]:
    """统计失败检查排行榜，帮助判断整体策略主要卡在哪里。"""
    grouped: dict[str, dict[str, Any]] = {}
    for result in results:
        if is_queue_timeout_result(result):
            continue
        for check in result.failed_checks or []:
            name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
            row = grouped.setdefault(
                name,
                {
                    "name": name,
                    "count": 0,
                    "values": [],
                    "limits": [],
                    "gaps": [],
                    "closeness_scores": [],
                    "example_alpha_ids": [],
                },
            )
            row["count"] += 1
            value = check.get("value")
            limit = check.get("limit")
            gap = failed_check_gap(check)
            closeness = failed_check_closeness(check)
            if isinstance(value, (int, float)):
                row["values"].append(value)
            if isinstance(limit, (int, float)):
                row["limits"].append(limit)
            if gap is not None:
                row["gaps"].append(gap)
            if closeness is not None:
                row["closeness_scores"].append(closeness)
            if (
                result.alpha_id
                and result.alpha_id not in row["example_alpha_ids"]
                and len(row["example_alpha_ids"]) < 5
            ):
                row["example_alpha_ids"].append(result.alpha_id)

    leaderboard: list[dict[str, Any]] = []
    for row in grouped.values():
        values = row.pop("values")
        limits = row.pop("limits")
        gaps = row.pop("gaps")
        closeness_scores = row.pop("closeness_scores")
        row["avg_value"] = sum(values) / len(values) if values else None
        row["avg_limit"] = sum(limits) / len(limits) if limits else None
        row["avg_gap"] = sum(gaps) / len(gaps) if gaps else None
        row["avg_closeness"] = (
            sum(closeness_scores) / len(closeness_scores) if closeness_scores else None
        )
        leaderboard.append(row)
    return sorted(
        leaderboard,
        key=lambda row: (
            -row["count"],
            -(row["avg_closeness"] or STATS_DEFAULT_SCORE),
            row["name"],
        ),
    )


def compile_near_pass_summary(
    results: Sequence[FieldTestResult], limit: int = STATS_NEARPASS_SUMMARY_LIMIT
) -> list[dict[str, Any]]:
    """列出最接近通过检查的 Alpha，用于指导下一轮变体搜索。"""
    rows: list[dict[str, Any]] = []
    for result in results:
        if result.status != "simulated" or result.submittable or not result.failed_checks:
            continue
        if is_queue_timeout_result(result):
            continue
        score = score_failed_checks(result.failed_checks)
        rows.append(
            {
                "score": score,
                "field_id": result.field_id,
                "field_name": result.field_name,
                "field_type": result.field_type,
                "template_name": result.template_name,
                "alpha_id": result.alpha_id,
                "expression": result.expression,
                "message": result.message,
                "failed_checks": [
                    summarize_failed_check(check) for check in result.failed_checks or []
                ],
            }
        )
    return sorted(rows, key=lambda row: (-row["score"], row["field_id"], row["template_name"]))[
        :limit
    ]


def compile_optimization_hints(
    failed_check_leaderboard: Sequence[dict[str, Any]],
    near_pass_summary: Sequence[dict[str, Any]],
) -> list[str]:
    """根据失败分布生成下一轮搜索建议。"""
    dominant_names = {str(row.get("name")) for row in failed_check_leaderboard[:3]}
    hints: list[str] = []
    if not failed_check_leaderboard:
        return ["还没有失败检查记录；先运行更广泛的探索样本。"]
    if CHECK_LOW_SHARPE in dominant_names or CHECK_LOW_SUB_UNIVERSE_SHARPE in dominant_names:
        hints.append("夏普比率是主要阻碍；优先使用组中性化、zscore/spread 和较少原始级别式的模板。")
    if CHECK_LOW_FITNESS in dominant_names:
        hints.append("适应性较弱；优先使用能同时提升夏普和换手率的表达式，而不是仅平滑级别。")
    if CHECK_LOW_TURNOVER in dominant_names:
        hints.append("换手率过低；尝试更短的 delta 窗口、rank-then-delta 变体或更低的衰减。")
    if CHECK_HIGH_TURNOVER in dominant_names:
        hints.append("换手率过高；尝试更长的窗口、更高的衰减或更平滑的 ts_mean/ts_decay 结构。")
    if CHECK_CONCENTRATED_WEIGHT in dominant_names:
        hints.append(
            "权重集中度过高；优先使用 group_rank/group_zscore 变体，避免原始比率或稀疏级别信号。"
        )
    if near_pass_summary:
        best = near_pass_summary[0]
        hints.append(
            f"最佳接近通过候选：字段={best['field_id']} 模板={best['template_name']} 分数={best['score']:.3f}；优先对此表达式进行局部变体。"
        )
    return hints
