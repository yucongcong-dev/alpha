"""
结果分析统计模块

本模块负责分析和统计字段测试结果，包括加载历史结果、
统计模板和字段性能、分析失败检查、生成优化建议等。

模块内容：
    - load_existing_results(path) -> list[FieldTestResult]: 加载历史运行结果
    - result_identity(result) -> tuple[str, str, str, str]: 生成结果去重键
    - is_queue_timeout_result(result) -> bool: 判断是否为队列超时结果
    - is_informative_result(result) -> bool: 判断是否为有效反馈结果
    - attempted_template_keys(results) -> set: 收集已尝试的模板键集合
    - compile_template_stats(results) -> dict[str, dict[str, int]]: 编译模板统计
    - historical_template_priority_bonus(template_name, template_stats, multiplier) -> int: 历史优先级奖励
    - compile_template_performance_summary(results) -> list[Dict]: 模板性能汇总
    - compile_field_performance_summary(results) -> list[Dict]: 字段性能汇总
    - score_failed_checks(failed_checks) -> float: 失败检查评分
    - failed_check_closeness(check) ->  | Nonefloat]: 失败检查接近度
    - failed_check_gap(check) ->  | Nonefloat]: 失败检查差距
    - summarize_failed_check(check) -> Dict: 失败检查摘要
    - compile_failed_check_leaderboard(results) -> list[Dict]: 失败检查排行榜
    - compile_near_pass_summary(results, limit) -> list[Dict]: 接近通过结果汇总
    - compile_optimization_hints(dataset_id, results, ...) -> Dict: 编译优化建议
    - compile_field_feedback(results) -> dict[str, Dict]: 字段反馈汇总
    - compile_global_failed_check_counts(results) -> dict[str, int]: 全局失败检查计数
    - dominant_failed_check_names(counts, limit) -> set: 主导失败检查名称
    - merge_failed_check_counts(*count_maps) -> Dict: 合并失败检查计数
    - field_priority(field_id, field_feedback) -> float: 字段优先级分数
    - current_submittable_count(results) -> int: 当前可提交数量计数
"""

from __future__ import annotations

from collections.abc import Sequence
import json
import logging
import os
from pathlib import Path
import time
from typing import Any

from ..config import (
    API_KEY_MESSAGE,
    API_KEY_STATUS,
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    SENTINEL_UNKNOWN,
    SENTINEL_UNKNOWN_CHECK,
    SENTINEL_UNKNOWN_STATUS,
    STAT_FIELD_ATTEMPTED,
    STAT_FIELD_ATTEMPTED_TEMPLATES,
    STAT_FIELD_CONCENTRATED_WEIGHT,
    STAT_FIELD_ERRORS,
    STAT_FIELD_FAILED_CHECK_COUNTS,
    STAT_FIELD_FIELD_ID,
    STAT_FIELD_FIELD_NAME,
    STAT_FIELD_FIELD_TYPE,
    STAT_FIELD_LOW_FITNESS,
    STAT_FIELD_LOW_SHARPE,
    STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE,
    STAT_FIELD_QUEUE_TIMEOUTS,
    STAT_FIELD_SIMULATED,
    STAT_FIELD_SUBMITTABLE,
    STAT_FIELD_SUBMITTED,
    STAT_FIELD_TEMPLATE_NAME,
    STAT_FIELD_TOP_FAILED_CHECKS,
    STATS_DEFAULT_SCORE,
    STATS_FAILED_CHECK_DEFAULT_SCORE,
    STATS_NEARPASS_SUMMARY_LIMIT,
    STATS_PERFORMANCE_TOP_N,
    STATUS_ERROR,
    STATUS_SIMULATED,
    STATUS_SUBMITTED,
)
from ..exceptions import BrainAPIError
from ..models.base import FieldTestResult

logger = logging.getLogger(__name__)


def _default_results_journal_path(path: str) -> str:
    """为主结果文件派生默认 journal 路径。"""
    output = Path(path)
    base_name = output.stem or output.name or "results"
    return str(output.parent / f"{base_name}_results.jsonl")


def load_existing_results(path: str) -> list[FieldTestResult]:
    """
    加载历史运行结果，以便续跑和复用反馈信息。

    从 JSON 文件中读取之前运行的结果数据，并将其转换为
    FieldTestResult 对象列表。如果文件不存在或读取失败，
    返回空列表。

    Args:
        path (str): 结果 JSON 文件的路径。如果路径为空或文件不存在，
            将返回空列表。

    Returns:
        list[FieldTestResult]: 加载的历史结果列表。每个结果包含
            字段信息、模板名称、模拟状态、失败检查等详细信息。

    Notes:
        - 返回一个 FieldTestResult 对象列表
        - 如果文件不存在，则返回空列表
        - 文件损坏时自动重命名备份并从空结果重新开始

    Example:
        >>> results = load_existing_results("results.json")
        >>> print(len(results))
        100
        >>> # 文件不存在时返回空列表
        >>> results = load_existing_results("")
        >>> print(len(results))
        0

    Note:
        结果文件格式必须是 JSON，包含一个 "results" 字段，
        该字段是一个包含多个结果对象的列表。每个结果对象
        至少应包含 field_id、field_type、field_name 等字段。
    """
    if not path or not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        # 文件损坏时重命名备份，从空结果重新开始
        now = int(time.time())
        backup_path = f"{path}.corrupted.{now}"
        try:
            os.rename(path, backup_path)
            logger.warning(
                "[recovery] renamed corrupted result file %s -> %s (error: %s)",
                path, backup_path, exc,
            )
        except OSError:
            logger.warning(
                "[recovery] failed to rename corrupted result file %s: %s", path, exc
            )
        return []

    rows: list[Any] | None = None
    if payload.get("results_embedded", True):
        payload_rows = payload.get("results")
        if isinstance(payload_rows, list):
            rows = payload_rows

    if rows is None:
        journal_path_value = payload.get("results_journal")
        journal_path = (
            str(journal_path_value)
            if isinstance(journal_path_value, str) and journal_path_value
            else _default_results_journal_path(path)
        )
        if not os.path.exists(journal_path):
            return []
        rows = []
        try:
            with open(journal_path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
        except Exception as exc:
            logger.warning("[recovery] failed to read results journal %s: %s", journal_path, exc)
            return []

    results: list[FieldTestResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            results.append(
                FieldTestResult(
                    field_id=str(row.get(STAT_FIELD_FIELD_ID, SENTINEL_UNKNOWN)),
                    field_type=str(row.get(STAT_FIELD_FIELD_TYPE, SENTINEL_UNKNOWN)),
                    field_name=str(row.get(STAT_FIELD_FIELD_NAME, SENTINEL_UNKNOWN)),
                    template_name=str(row.get(STAT_FIELD_TEMPLATE_NAME, "")),
                    template_family=str(row.get("template_family", "")),
                    template_stage=str(row.get("template_stage", "")),
                    simulation_id=row.get("simulation_id"),
                    alpha_id=row.get("alpha_id"),
                    status=str(row.get(API_KEY_STATUS, SENTINEL_UNKNOWN_STATUS)),
                    submittable=row.get(STAT_FIELD_SUBMITTABLE),
                    submitted=bool(row.get(STAT_FIELD_SUBMITTED, False)),
                    message=str(row.get(API_KEY_MESSAGE, "")),
                    expression=str(row.get("expression", "")),
                    settings_fingerprint=str(row.get("settings_fingerprint", "")),
                    template_library_fingerprint=str(row.get("template_library_fingerprint", "")),
                    failed_stage=row.get("failed_stage"),
                    failed_checks=row.get("failed_checks"),
                )
            )
        except Exception:
            continue
    return results


def result_identity(result: FieldTestResult) -> tuple[str, str, str, str]:
    """
    返回单次字段-模板-settings 尝试的稳定去重键。

    生成一个用于唯一标识某个特定尝试的键，包含字段 ID、模板名称、
    表达式和设置指纹。用于在续跑时避免重复处理相同的组合。

    Args:
        result (FieldTestResult): 字段测试结果对象。

    Returns:
        tuple[str, str, str, str]: 包含四个字符串元素的元组：
            - field_id: 字段的唯一标识符
            - template_name: 模板名称
            - expression: Alpha 表达式
            - settings_fingerprint: 设置参数的指纹

    Example:
        >>> key = result_identity(result)
        >>> print(key)
        ('fnd6_sales', 'ts_mean_20', 'rank(ts_mean(sales, 20))', 'abc123')

    Note:
        该键用于去重，确保续跑时不会重复处理已经尝试过的组合。
    """
    return (
        result.field_id,
        result.template_name,
        result.expression,
        result.settings_fingerprint,
    )


def is_queue_timeout_result(result: FieldTestResult) -> bool:
    """
    判断结果是否只是平台队列超时，而非 Alpha 质量反馈。

    队列超时结果表示模拟任务因服务器繁忙而未能完成，
    这类结果不提供 Alpha 质量的真实反馈，不应参与质量学习。

    Args:
        result (FieldTestResult): 字段测试结果对象。

    Returns:
        bool: 如果是队列超时结果返回 True，否则返回 False。

    判断条件：
        - failed_stage 为 "simulation"
        - 消息中包含 "queue budget"、"queued too long" 或
          "stayed queued too long" 等关键词

    Example:
        >>> if is_queue_timeout_result(result):
        ...     print("这是队列超时，不参与质量学习")
    """
    message = str(result.message or "").lower()
    return result.failed_stage == "simulation" and (
        "queue budget" in message
        or "queued too long" in message
        or "stayed queued too long" in message
    )


def is_informative_result(result: FieldTestResult) -> bool:
    """
    判断结果是否应参与模板/字段质量学习。

    有效反馈结果是指提供了 Alpha 质量真实反馈的结果，
    不包括队列超时等平台问题导致的结果。

    Args:
        result (FieldTestResult): 字段测试结果对象。

    Returns:
        bool: 如果是有效反馈结果返回 True，否则返回 False。

    Example:
        >>> if is_informative_result(result):
        ...     # 将结果用于模板/字段质量统计
        ...     update_stats(result)
    """
    return not is_queue_timeout_result(result)


def attempted_template_keys(results: Sequence[FieldTestResult]) -> set[tuple[str, str, str, str]]:
    """
    收集已经持久化记录过的模板尝试键集合。

    从结果列表中提取所有有效反馈结果的去重键，
    用于在续跑时避免重复处理。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。

    Returns:
        set[tuple[str, str, str, str]]: 已尝试的模板键集合，
            每个键是一个四元组 (field_id, template_name, expression, settings_fingerprint)。

    Example:
        >>> keys = attempted_template_keys(results)
        >>> print(len(keys))
        50
        >>> # 检查某个组合是否已尝试
        >>> if ("field1", "template1", "expr1", "settings1") in keys:
        ...     print("已尝试过")
    """
    return {result_identity(result) for result in results if is_informative_result(result)}


def compile_template_stats(results: Sequence[FieldTestResult]) -> dict[str, dict[str, int]]:
    """
    按模板名聚合历史上的粗粒度统计信息。

    统计每个模板的尝试次数、成功次数、失败次数、队列超时次数等，
    用于优先级计算和模板剪枝。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。

    Returns:
        dict[str, dict[str, int]]: 模板统计字典，键为模板名称，
            值为包含以下统计字段的字典：
            - attempted: 尝试次数（不含队列超时）
            - submittable: 可提交次数
            - submitted: 已提交次数
            - errors: 错误次数
            - simulated: 模拟成功次数
            - queue_timeouts: 队列超时次数
            - low_sharpe: 低夏普比率失败次数
            - low_fitness: 低适应性失败次数
            - concentrated_weight: 权重集中失败次数
            - low_sub_universe_sharpe: 低子宇宙夏普比率次数

    Example:
        >>> stats = compile_template_stats(results)
        >>> print(stats["ts_mean_20"])
        {'attempted': 10, 'submittable': 3, 'errors': 1, ...}
    """
    stats: dict[str, dict[str, int]] = {}
    for result in results:
        update_template_stats_with_result(stats, result)
    return stats


def update_template_stats_with_result(
    stats: dict[str, dict[str, int]],
    result: FieldTestResult,
) -> dict[str, dict[str, int]]:
    """将单条结果增量合并到模板统计中。"""
    stat = stats.setdefault(
        result.template_name,
        {
            STAT_FIELD_ATTEMPTED: 0,
            STAT_FIELD_SUBMITTABLE: 0,
            STAT_FIELD_SUBMITTED: 0,
            STAT_FIELD_ERRORS: 0,
            STAT_FIELD_SIMULATED: 0,
            STAT_FIELD_QUEUE_TIMEOUTS: 0,
            STAT_FIELD_LOW_SHARPE: 0,
            STAT_FIELD_LOW_FITNESS: 0,
            STAT_FIELD_CONCENTRATED_WEIGHT: 0,
            STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE: 0,
        },
    )
    if result.template_family and "template_family" not in stat:
        stat["template_family"] = result.template_family
    if is_queue_timeout_result(result):
        stat[STAT_FIELD_QUEUE_TIMEOUTS] += 1
        return stats
    stat[STAT_FIELD_ATTEMPTED] += 1
    if result.submittable:
        stat[STAT_FIELD_SUBMITTABLE] += 1
    if result.submitted:
        stat[STAT_FIELD_SUBMITTED] += 1
    if result.status in {STATUS_SIMULATED, STATUS_SUBMITTED}:
        stat[STAT_FIELD_SIMULATED] += 1
    if result.status == STATUS_ERROR:
        stat[STAT_FIELD_ERRORS] += 1
    failed_check_names = {str(check.get("name", "")) for check in result.failed_checks or []}
    if CHECK_LOW_SHARPE in failed_check_names:
        stat[STAT_FIELD_LOW_SHARPE] += 1
    if CHECK_LOW_FITNESS in failed_check_names:
        stat[STAT_FIELD_LOW_FITNESS] += 1
    if CHECK_CONCENTRATED_WEIGHT in failed_check_names:
        stat[STAT_FIELD_CONCENTRATED_WEIGHT] += 1
    if CHECK_LOW_SUB_UNIVERSE_SHARPE in failed_check_names:
        stat[STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE] += 1
    return stats


def historical_template_priority_bonus(
    template_name: str,
    template_stats: dict[str, dict[str, int]],
    multiplier: int = 1,
) -> int:
    """
    为历史上模拟成功或通过检查的模板提供优先级奖励。

    根据模板的历史表现，给予不同的优先级奖励分数。
    表现好的模板（有可提交结果）获得高奖励，
    表现差的模板（多次错误）获得惩罚。

    Args:
        template_name (str): 模板名称。
        template_stats (dict[str, dict[str, int]]): 模板统计字典。
        multiplier (int): 奖励倍数，默认为 1。

    Returns:
        int: 优先级奖励分数，范围从 -20 到 200。

    奖励规则：
        - 有可提交结果: +200
        - 有模拟成功但无可提交: 40 + min(simulated, 5) * 8
          - 如果模拟成功 >= 3 且低夏普/低适应性 >= 3: -90
          - 如果权重集中 >= 2: -60
        - 错误 >= 3 且模拟成功 == 0: -20
        - 无统计信息: 0

    Example:
        >>> bonus = historical_template_priority_bonus("ts_mean_20", stats)
        >>> print(bonus)
        200
    """
    stat = template_stats.get(template_name)
    if not stat:
        return 0
    if stat[STAT_FIELD_SUBMITTABLE] > 0:
        return 200 * multiplier
    if stat[STAT_FIELD_SIMULATED] > 0:
        bonus = 40 + min(stat[STAT_FIELD_SIMULATED], 5) * 8
        if stat.get(STAT_FIELD_SUBMITTABLE, 0) == 0 and stat.get(STAT_FIELD_SIMULATED, 0) >= 3:
            if stat.get(STAT_FIELD_LOW_SHARPE, 0) >= 3 and stat.get(STAT_FIELD_LOW_FITNESS, 0) >= 3:
                bonus -= 90
            if stat.get(STAT_FIELD_CONCENTRATED_WEIGHT, 0) >= 2:
                bonus -= 60
        return bonus * multiplier
    if stat[STAT_FIELD_ERRORS] >= 3 and stat[STAT_FIELD_SIMULATED] == 0:
        return -20 * multiplier
    return 0


def compile_template_performance_summary(
    results: Sequence[FieldTestResult],
) -> list[dict[str, Any]]:
    """
    构建适合写入 JSON 的模板层表现汇总。

    按模板名称聚合结果，生成包含尝试次数、成功次数、
    失败检查统计等的汇总列表，用于分析和报告。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。

    Returns:
        list[dict[str, Any]]: 模板性能汇总列表，每个字典包含：
            - template_name: 模板名称
            - attempted: 尝试次数（不含队列超时）
            - submittable: 可提交次数
            - submitted: 已提交次数
            - errors: 错误次数
            - queue_timeouts: 队列超时次数
            - failed_check_counts: 失败检查计数字典
            - top_failed_checks: 前10个失败检查列表

    排序规则：
        按可提交次数（降序）、已提交次数（降序）、尝试次数（降序）、
        模板名称（升序）排序。

    Example:
        >>> summary = compile_template_performance_summary(results)
        >>> print(summary[0])
        {'template_name': 'ts_mean_20', 'attempted': 10, ...}
    """
    grouped: dict[str, dict[str, Any]] = {}
    for result in results:
        summary = grouped.setdefault(
            result.template_name,
            {
                STAT_FIELD_TEMPLATE_NAME: result.template_name,
                STAT_FIELD_ATTEMPTED: 0,
                STAT_FIELD_SUBMITTABLE: 0,
                STAT_FIELD_SUBMITTED: 0,
                STAT_FIELD_ERRORS: 0,
                STAT_FIELD_QUEUE_TIMEOUTS: 0,
                STAT_FIELD_FAILED_CHECK_COUNTS: {},
            },
        )
        if is_queue_timeout_result(result):
            summary[STAT_FIELD_QUEUE_TIMEOUTS] += 1
            continue
        summary[STAT_FIELD_ATTEMPTED] += 1
        if result.submittable:
            summary[STAT_FIELD_SUBMITTABLE] += 1
        if result.submitted:
            summary[STAT_FIELD_SUBMITTED] += 1
        if result.status == STATUS_ERROR:
            summary[STAT_FIELD_ERRORS] += 1
        for check in result.failed_checks or []:
            name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
            summary[STAT_FIELD_FAILED_CHECK_COUNTS][name] = (
                summary[STAT_FIELD_FAILED_CHECK_COUNTS].get(name, 0) + 1
            )

    rows = list(grouped.values())
    for row in rows:
        counts = row[STAT_FIELD_FAILED_CHECK_COUNTS]
        row[STAT_FIELD_TOP_FAILED_CHECKS] = sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:STATS_PERFORMANCE_TOP_N]
    return sorted(
        rows,
        key=lambda row: (
            -row[STAT_FIELD_SUBMITTABLE],
            -row[STAT_FIELD_SUBMITTED],
            -row[STAT_FIELD_ATTEMPTED],
            row[STAT_FIELD_TEMPLATE_NAME],
        ),
    )


def compile_field_performance_summary(results: Sequence[FieldTestResult]) -> list[dict[str, Any]]:
    """
    构建适合写入 JSON 的字段层表现汇总。

    按字段 ID 聚合结果，生成包含尝试模板次数、成功次数、
    失败检查统计等的汇总列表，用于分析和报告。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。

    Returns:
        list[dict[str, Any]]: 字段性能汇总列表，每个字典包含：
            - field_id: 字段 ID
            - field_name: 字段名称
            - field_type: 字段类型
            - attempted_templates: 尝试的模板次数
            - submittable: 可提交次数
            - submitted: 已提交次数
            - errors: 错误次数
            - queue_timeouts: 队列超时次数
            - failed_check_counts: 失败检查计数字典
            - top_failed_checks: 前10个失败检查列表

    排序规则：
        按可提交次数（降序）、已提交次数（降序）、尝试模板次数（降序）、
        字段 ID（升序）排序。

    Example:
        >>> summary = compile_field_performance_summary(results)
        >>> print(summary[0])
        {'field_id': 'fnd6_sales', 'field_name': 'sales', ...}
    """
    grouped: dict[str, dict[str, Any]] = {}
    for result in results:
        summary = grouped.setdefault(
            result.field_id,
            {
                STAT_FIELD_FIELD_ID: result.field_id,
                STAT_FIELD_FIELD_NAME: result.field_name,
                STAT_FIELD_FIELD_TYPE: result.field_type,
                STAT_FIELD_ATTEMPTED_TEMPLATES: 0,
                STAT_FIELD_SUBMITTABLE: 0,
                STAT_FIELD_SUBMITTED: 0,
                STAT_FIELD_ERRORS: 0,
                STAT_FIELD_QUEUE_TIMEOUTS: 0,
                STAT_FIELD_FAILED_CHECK_COUNTS: {},
            },
        )
        if is_queue_timeout_result(result):
            summary[STAT_FIELD_QUEUE_TIMEOUTS] += 1
            continue
        summary[STAT_FIELD_ATTEMPTED_TEMPLATES] += 1
        if result.submittable:
            summary[STAT_FIELD_SUBMITTABLE] += 1
        if result.submitted:
            summary[STAT_FIELD_SUBMITTED] += 1
        if result.status == STATUS_ERROR:
            summary[STAT_FIELD_ERRORS] += 1
        for check in result.failed_checks or []:
            name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
            summary[STAT_FIELD_FAILED_CHECK_COUNTS][name] = (
                summary[STAT_FIELD_FAILED_CHECK_COUNTS].get(name, 0) + 1
            )

    rows = list(grouped.values())
    for row in rows:
        counts = row[STAT_FIELD_FAILED_CHECK_COUNTS]
        row[STAT_FIELD_TOP_FAILED_CHECKS] = sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:STATS_PERFORMANCE_TOP_N]
    return sorted(
        rows,
        key=lambda row: (
            -row[STAT_FIELD_SUBMITTABLE],
            -row[STAT_FIELD_SUBMITTED],
            -row[STAT_FIELD_ATTEMPTED_TEMPLATES],
            row[STAT_FIELD_FIELD_ID],
        ),
    )


def score_failed_checks(failed_checks: Sequence[dict[str, Any]] | None) -> float:
    """
    根据失败检查项估计一个 Alpha 距离可提交状态还有多近。

    计算一个分数，表示 Alpha 表达式离通过检查的接近程度。
    分数越高表示越接近通过，用于优先处理接近成功的候选。

    Args:
        failed_checks (Sequence[dict[str, Any]] | None): 失败检查项序列，
            每个检查项包含 name、value、limit 等字段。

    Returns:
        float: 接近分数，范围通常在 -10.0 到 1.0 左右。
            - 分数越高表示越接近通过
            - 如果没有有效检查项，返回 -10.0

    计算规则：
        - 使用统一“closeness”分数衡量离阈值有多近
        - 对负阈值（如部分 LOW_SUB_UNIVERSE_SHARPE）也保持可比较
        - 最终分数为所有检查项 closeness 的平均值

    Example:
        >>> failed_checks = [{"name": "LOW_SHARPE", "value": 0.9, "limit": 1.0}]
        >>> score = score_failed_checks(failed_checks)
        >>> print(score)
        0.9
    """
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


def failed_check_closeness(check: dict[str, Any]) -> float | None:
    """
    计算单个失败检查离通过阈值有多近，返回 0-1 左右的分数。

    计算失败检查项的接近度，分数越接近 1 表示越接近通过。

    Args:
        check (dict[str, Any]): 失败检查项字典，包含 name、value、limit。

    Returns:
         | Nonefloat]: 接近度分数，范围通常在 0.0 到 1.0。
            - 如果无法计算，返回 None

    计算规则：
        - 统一按 gap / |limit| 归一化，避免负阈值时排序失真
        - gap 越小，closeness 越接近 1
        - 明显离阈值很远时可降到 0

    Example:
        >>> check = {"name": "LOW_SHARPE", "value": 0.9, "limit": 1.0}
        >>> closeness = failed_check_closeness(check)
        >>> print(closeness)
        0.9
    """
    name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
    value = check.get("value")
    limit = check.get("limit")
    if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)):
        return None
    gap = failed_check_gap(check)
    scale = max(abs(limit), 1e-9)
    if gap is None:
        return None
    return max(0.0, 1.0 - (gap / scale))


def failed_check_gap(check: dict[str, Any]) -> float | None:
    """
    计算失败检查到阈值的原始差距，正数表示还差多少。

    计算失败检查项与通过阈值之间的绝对差距，
    用于了解还需要提升多少才能通过。

    Args:
        check (dict[str, Any]): 失败检查项字典，包含 name、value、limit。

    Returns:
         | Nonefloat]: 差距值，正数表示还差多少才能通过。
            - 如果无法计算，返回 None

    计算规则：
        - 对于 LOW_ 开头的检查: limit - value（需要提升的量）
        - 对于其他检查: value - limit（需要减少的量）

    Example:
        >>> check = {"name": "LOW_SHARPE", "value": 0.9, "limit": 1.0}
        >>> gap = failed_check_gap(check)
        >>> print(gap)
        0.1  # 还需要提升 0.1 才能通过
    """
    name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
    value = check.get("value")
    limit = check.get("limit")
    if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)):
        return None
    if name.startswith("LOW_"):
        return limit - value
    return value - limit


def summarize_failed_check(check: dict[str, Any]) -> dict[str, Any]:
    """
    把失败检查转换成适合分析排序的紧凑结构。

    将失败检查项转换为包含接近度和差距的摘要字典，
    便于分析和比较。

    Args:
        check (dict[str, Any]): 失败检查项字典。

    Returns:
        dict[str, Any]: 失败检查摘要，包含：
            - name: 检查项名称
            - value: 当前值
            - limit: 阈值
            - gap: 到阈值的差距
            - closeness: 接近度分数

    Example:
        >>> summary = summarize_failed_check(
        ...     {"name": "LOW_SHARPE", "value": 0.9, "limit": 1.0}
        ... )
        >>> print(summary)
        {'name': 'LOW_SHARPE', 'value': 0.9, 'limit': 1.0, 'gap': 0.1, 'closeness': 0.9}
    """
    return {
        "name": check.get("name"),
        "value": check.get("value"),
        "limit": check.get("limit"),
        "gap": failed_check_gap(check),
        "closeness": failed_check_closeness(check),
    }


def compile_failed_check_leaderboard(results: Sequence[FieldTestResult]) -> list[dict[str, Any]]:
    """
    统计失败检查排行榜，帮助判断整体策略主要卡在哪里。

    按失败检查名称聚合统计，生成包含出现次数、平均值、
    平均差距等的排行榜，用于诊断整体问题。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。

    Returns:
        list[dict[str, Any]]: 失败检查排行榜列表，每个字典包含：
            - name: 检查项名称
            - count: 出现次数
            - avg_value: 平均当前值
            - avg_limit: 平均阈值
            - avg_gap: 平均差距
            - avg_closeness: 平均接近度
            - example_alpha_ids: 示例 Alpha ID 列表（最多5个）

    排序规则：
        按出现次数（降序）、平均接近度（降序）、名称（升序）排序。

    Example:
        >>> leaderboard = compile_failed_check_leaderboard(results)
        >>> print(leaderboard[0])
        {'name': 'LOW_SHARPE', 'count': 50, 'avg_closeness': 0.85, ...}
    """
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
    """
    列出最接近通过检查的 Alpha，用于指导下一轮变体搜索。

    从结果中筛选出模拟成功但未通过检查的 Alpha，
    按接近分数排序，用于指导下一轮的优化方向。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。
        limit (int): 返回的最大数量，默认为 20。

    Returns:
        list[dict[str, Any]]: 接近通过的结果列表，每个字典包含：
            - score: 接近分数
            - field_id: 字段 ID
            - field_name: 字段名称
            - field_type: 字段类型
            - template_name: 模板名称
            - alpha_id: Alpha ID
            - expression: Alpha 表达式
            - message: 结果消息
            - failed_checks: 失败检查摘要列表

    排序规则：
        按接近分数（降序）、字段 ID（升序）、模板名称（升序）排序。

    Example:
        >>> near_pass = compile_near_pass_summary(results, limit=10)
        >>> print(near_pass[0])
        {'score': 0.95, 'field_name': 'sales', 'template_name': 'ts_mean_20', ...}
    """
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
    """
    根据失败分布生成下一轮搜索建议。

    分析失败检查排行榜和接近通过结果，生成优化建议，
    帮助指导下一轮的搜索策略。

    Args:
        failed_check_leaderboard (Sequence[dict[str, Any]]): 失败检查排行榜。
        near_pass_summary (Sequence[dict[str, Any]]): 接近通过结果汇总。

    Returns:
        list[str]: 优化建议列表，每条建议是一个字符串。

    建议规则：
        - 根据主导失败检查类型生成建议：
            - LOW_SHARPE/LOW_SUB_UNIVERSE_SHARPE: 优先使用 group-neutralized、zscore/spread 模板
            - LOW_FITNESS: 优先提升夏普和换手率的表达式
            - LOW_TURNOVER: 尝试更短的 delta 窗口、rank-then-delta 变体
            - HIGH_TURNOVER: 尝试更长的窗口、更高的衰减、更平滑的结构
            - CONCENTRATED_WEIGHT: 使用 group_rank/group_zscore 变体，避免原始比率
        - 根据最佳接近通过结果生成具体建议

    Example:
        >>> hints = compile_optimization_hints(leaderboard, near_pass)
        >>> print(hints)
        ['Sharpe is the dominant blocker; prioritize group-neutralized...', ...]
    """
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


def compile_field_feedback(results: Sequence[FieldTestResult]) -> dict[str, dict[str, Any]]:
    """
    将历史接近通过的结果转为按字段组织的优化反馈。

    按字段 ID 聚合结果，生成包含最佳分数、最佳表达式、
    失败检查统计等的反馈字典，用于指导后续优化。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。

    Returns:
        dict[str, dict[str, Any]]: 字段反馈字典，键为字段 ID，
            值为包含以下字段的字典：
            - field_name: 字段名称
            - best_score: 最佳接近分数
            - best_expression: 最佳表达式
            - best_template_name: 最佳模板名称
            - failed_check_counts: 失败检查计数字典

    Example:
        >>> feedback = compile_field_feedback(results)
        >>> print(feedback["fnd6_sales"])
        {'field_name': 'sales', 'best_score': 0.85, ...}
    """
    feedback: dict[str, dict[str, Any]] = {}
    for result in results:
        update_field_feedback_with_result(feedback, result)
    return feedback


def update_field_feedback_with_result(
    feedback: dict[str, dict[str, Any]],
    result: FieldTestResult,
) -> dict[str, dict[str, Any]]:
    """将单条结果增量合并到字段反馈画像中。"""
    summary = feedback.setdefault(
        result.field_id,
        {
            STAT_FIELD_FIELD_NAME: result.field_name,
            "best_score": STATS_DEFAULT_SCORE,
            "best_expression": "",
            "best_template_name": "",
            "best_template_family": "",
            "best_template_stage": "",
            STAT_FIELD_ATTEMPTED_TEMPLATES: 0,
            STAT_FIELD_FAILED_CHECK_COUNTS: {},
        },
    )
    summary[STAT_FIELD_ATTEMPTED_TEMPLATES] = (
        int(summary.get(STAT_FIELD_ATTEMPTED_TEMPLATES, 0)) + 1
    )
    for check in result.failed_checks or []:
        name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
        summary[STAT_FIELD_FAILED_CHECK_COUNTS][name] = (
            summary[STAT_FIELD_FAILED_CHECK_COUNTS].get(name, 0) + 1
        )
    if result.status != STATUS_SIMULATED or not result.failed_checks:
        return feedback
    score = score_failed_checks(result.failed_checks)
    if score > summary["best_score"]:
        summary["best_score"] = score
        summary["best_expression"] = result.expression
        summary["best_template_name"] = result.template_name
        summary["best_template_family"] = result.template_family
        summary["best_template_stage"] = result.template_stage
    return feedback


def compile_global_failed_check_counts(results: Sequence[FieldTestResult]) -> dict[str, int]:
    """
    汇总所有历史结果中的失败检查计数，作为全局搜索方向。

    统计所有结果中各失败检查类型的出现次数，
    用于指导全局搜索策略和剪枝。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。

    Returns:
        dict[str, int]: 全局失败检查计数字典，键为检查名称，
            值为出现次数。

    Example:
        >>> counts = compile_global_failed_check_counts(results)
        >>> print(counts)
        {'LOW_SHARPE': 50, 'LOW_FITNESS': 30, ...}
    """
    counts: dict[str, int] = {}
    for result in results:
        update_global_failed_check_counts_with_result(counts, result)
    return counts


def update_global_failed_check_counts_with_result(
    counts: dict[str, int],
    result: FieldTestResult,
) -> dict[str, int]:
    """将单条结果增量合并到全局失败检查计数中。"""
    if is_queue_timeout_result(result):
        return counts
    for check in result.failed_checks or []:
        name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
        counts[name] = counts.get(name, 0) + 1
    return counts


def dominant_failed_check_names(counts: dict[str, int], limit: int = 4) -> set[str]:
    """
    返回失败检查计数最高的若干名称。

    从失败检查计数中提取出现次数最高的若干检查名称，
    用于识别主要问题。

    Args:
        counts (dict[str, int]): 失败检查计数字典。
        limit (int): 返回的最大数量，默认为 4。

    Returns:
        set[str]: 主导失败检查名称集合。

    Example:
        >>> dominant = dominant_failed_check_names(counts, limit=3)
        >>> print(dominant)
        {'LOW_SHARPE', 'LOW_FITNESS', 'CONCENTRATED_WEIGHT'}
    """
    return {
        name
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        if count > 0
    }


def merge_failed_check_counts(*count_maps: dict[str, Any]) -> dict[str, int]:
    """
    合并多个失败检查计数字典。

    将多个计数字典合并为一个，用于汇总不同来源的统计。

    Args:
        *count_maps: 可变数量的计数字典参数。

    Returns:
        dict[str, int]: 合并后的计数字典。

    Example:
        >>> merged = merge_failed_check_counts(counts1, counts2)
        >>> print(merged)
        {'LOW_SHARPE': 80, 'LOW_FITNESS': 60, ...}
    """
    merged: dict[str, int] = {}
    for count_map in count_maps:
        for name, count in count_map.items():
            if not isinstance(count, int):
                continue
            merged[str(name)] = merged.get(str(name), 0) + count
    return merged


def field_priority(field_id: str, field_feedback: dict[str, dict[str, Any]]) -> float:
    """
    返回字段在续跑排序中使用的历史优先级分数。

    根据字段的历史反馈，返回优先级分数用于排序。
    分数越高表示字段越值得优先处理。

    Args:
        field_id (str): 字段 ID。
        field_feedback (dict[str, dict[str, Any]]): 字段反馈字典。

    Returns:
        float: 优先级分数，范围为历史最佳接近分数。
            如果字段无反馈，返回 -999.0。

    Example:
        >>> priority = field_priority("fnd6_sales", feedback)
        >>> print(priority)
        0.85
    """
    summary = field_feedback.get(field_id)
    if not summary:
        return STATS_DEFAULT_SCORE
    best_score = float(summary.get("best_score", STATS_DEFAULT_SCORE))
    attempted_templates = int(summary.get(STAT_FIELD_ATTEMPTED_TEMPLATES, 0))
    # 对已经尝试很多次但依然没有接近门槛的字段，让位给未探索字段。
    if attempted_templates >= 8 and best_score < 0.70:
        return STATS_DEFAULT_SCORE - float(attempted_templates)
    if attempted_templates >= 5 and best_score < 0.40:
        return STATS_DEFAULT_SCORE - float(attempted_templates)
    return best_score


def current_submittable_count(results: Sequence[FieldTestResult]) -> int:
    """
    统计当前结果集中已经可提交的 Alpha 数量。

    统计可提交的结果数量，用于判断是否达到目标。

    Args:
        results (Sequence[FieldTestResult]): 结果序列。

    Returns:
        int: 可提交的结果数量。

    Example:
        >>> count = current_submittable_count(results)
        >>> print(count)
        5
    """
    return sum(1 for result in results if result.submittable)
