# -*- coding: utf-8 -*-
"""
结果输出模块

本模块负责测试结果的持久化输出，包括结果文件保存、
分析文件同步、路径处理和旧版文件清理等操作。

模块内容：
    - 结果保存函数
    - 分析文件同步函数
    - CLI 路径解析函数
    - 文件名安全化函数
    - 数据集范围路径构建函数
    - 边车文件路径构建函数
    - 旧版边车文件清理函数
"""

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..config import DEFAULT_DATASET_ID
from ..exceptions import BrainAPIError
from ..models.base import FieldTestResult


# ============================================================================
# 常量定义
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
"""脚本目录的绝对路径"""

PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
"""项目根目录的绝对路径（alpha/ 目录）"""

CACHE_DIR = PROJECT_ROOT / "cache"
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data"
"""数据文件目录"""


# ============================================================================
# 辅助函数
# ============================================================================

def stable_fingerprint(payload: Any) -> str:
    """
    为配置、模板或结果标识生成稳定的短哈希。

    将任意数据结构转换为 JSON 字符串，然后生成 SHA256 哈希，
    取前 16 个字符作为指纹。

    Args:
        payload: 要生成指纹的数据对象。

    Returns:
        str: 16 字符的哈希指纹字符串。

    Example:
        >>> fingerprint = stable_fingerprint({"key": "value"})
        >>> print(len(fingerprint))
        16

        >>> fingerprint1 = stable_fingerprint({"a": 1, "b": 2})
        >>> fingerprint2 = stable_fingerprint({"b": 2, "a": 1})
        >>> print(fingerprint1 == fingerprint2)
        True

    Note:
        - 使用 sort_keys=True 确保 JSON 键顺序一致
        - 使用紧凑分隔符确保相同数据产生相同哈希
        - 哈希长度为 16 字符（SHA256 的前 64 位）
    """
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def atomic_write_json(path: str, payload: Any) -> None:
    """
    以原子方式写入 JSON，避免中断运行破坏状态文件。

    先写入临时文件，然后原子性地替换目标文件，
    确保写入过程不会因中断而破坏现有文件。

    Args:
        path: 目标文件的绝对路径。
        payload: 要写入的 JSON 数据对象。

    Example:
        >>> atomic_write_json("/path/to/file.json", {"key": "value"})
        >>> # 文件已安全写入

    Note:
        - 使用 tempfile.mkstemp 创建临时文件
        - 使用 os.replace 进行原子替换
        - 确保临时文件在异常时被清理
        - 使用 UTF-8 编码和美观格式化（indent=2）
    """
    # 先写入临时文件，然后原子性地替换目标文件
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# ============================================================================
# CLI 路径解析函数
# ============================================================================

def resolve_cli_path(path: str) -> str:
    """
    将 CLI 文件路径解析为相对于脚本目录的绝对路径。

    如果路径是相对路径，将其转换为相对于脚本目录的绝对路径；
    如果已经是绝对路径，直接返回。

    Args:
        path: CLI 参数提供的文件路径（可能为相对或绝对路径）。

    Returns:
        str: 解析后的绝对路径字符串。
        如果输入为空字符串，返回空字符串。

    Example:
        >>> path = resolve_cli_path("config.json")
        >>> # 返回 /path/to/script_dir/config.json

        >>> path = resolve_cli_path("/absolute/path/file.json")
        >>> print(path)
        /absolute/path/file.json

        >>> path = resolve_cli_path("")
        >>> print(path)
        ''

    Note:
        - 使用 Path.expanduser() 处理用户目录符号（~）
        - 相对路径会相对于 SCRIPT_DIR 解析
        - 绝对路径直接返回
    """
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = SCRIPT_DIR / candidate
    return str(candidate.resolve())


# ============================================================================
# 文件名安全化函数
# ============================================================================

def sanitize_dataset_id_for_filename(dataset_id: str) -> str:
    """
    将 dataset_id 转成适合文件名的安全片段。

    移除文件名中的非法字符，替换为下划线，
    确保生成的文件名安全可用。

    Args:
        dataset_id: 数据集标识符字符串。

    Returns:
        str: 安全的文件名片段。
        如果输入为空或处理后为空，返回 DEFAULT_DATASET_ID。

    Example:
        >>> sanitize_dataset_id_for_filename("fundamental6")
        'fundamental6'

        >>> sanitize_dataset_id_for_filename("my/dataset@123")
        'my_dataset_123'

        >>> sanitize_dataset_id_for_filename("")
        'fundamental6'

    Note:
        - 只保留字母、数字、点号、下划线和连字符
        - 其他字符替换为下划线
        - 空结果使用 DEFAULT_DATASET_ID 作为默认值
    """
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", dataset_id.strip())
    return sanitized or DEFAULT_DATASET_ID


# ============================================================================
# 数据集范围路径构建函数
# ============================================================================

def build_dataset_scoped_paths(dataset_id: str) -> Dict[str, str]:
    """
    根据 dataset_id 派生默认缓存、结果与模板库路径。

    根据数据集标识符生成默认的文件路径，
    包括模板库文件、字段缓存文件和结果输出文件。

    Args:
        dataset_id: 数据集标识符字符串。

    Returns:
        Dict[str, str]: 包含以下键的路径字典：
            - template_library_file: 模板库文件路径
            - fields_cache_file: 字段缓存文件路径
            - output: 结果输出文件路径

    Example:
        >>> paths = build_dataset_scoped_paths("fundamental6")
        >>> print(paths["fields_cache_file"])
        /path/to/script_dir/fundamental6_fields_cache.json

        >>> paths = build_dataset_scoped_paths("my_dataset")
        >>> print(paths["output"])
        /path/to/script_dir/my_dataset_test_results.json

    Note:
        - 所有路径都相对于 SCRIPT_DIR
        - 文件名使用 sanitize_dataset_id_for_filename 安全化
        - 模板库文件名格式：worldquant_template_library_{sanitized}.json
        - 字段缓存文件名格式：{sanitized}_fields_cache.json
        - 结果文件名格式：{sanitized}_test_results.json
    """
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    return {
        "template_library_file": str(DATA_DIR / f"worldquant_template_library_{dataset_key}.json"),
        "fields_cache_file": str(CACHE_DIR / f"{dataset_key}_fields_cache.json"),
        "output": str(RESULTS_DIR / f"{dataset_key}_test_results.json"),
    }


# ============================================================================
# 边车文件路径构建函数
# ============================================================================

def build_output_sidecar_paths(output_path: str) -> Dict[str, str]:
    """
    生成主结果文件旁边的精简分析与日志路径。

    根据主结果文件路径，生成配套的分析文件和运行日志文件路径。

    Args:
        output_path: 主结果文件的绝对路径。

    Returns:
        Dict[str, str]: 包含以下键的路径字典：
            - analysis: 分析文件路径（{basename}_analysis.json）
            - run_log: 运行日志文件路径（{basename}_{date}_run.log）

    Example:
        >>> paths = build_output_sidecar_paths("/path/to/results.json")
        >>> print(paths["analysis"])
        /path/to/results_analysis.json
        >>> # run_log 包含日期，如 results_2024-01-01_run.log

    Note:
        - 分析文件名在主文件名后添加 _analysis
        - 日志文件名包含日期（YYYY-MM-DD 格式）
        - 所有边车文件都在同一目录下
    """
    output = Path(output_path)
    base_dir = output.parent
    base_name = output.stem
    log_date = time.strftime("%Y-%m-%d")
    return {
        "analysis": str(base_dir / f"{base_name}_analysis.json"),
        "run_log": str(base_dir / f"{base_name}_{log_date}_run.log"),
    }


# ============================================================================
# 旧版边车文件清理函数
# ============================================================================

def cleanup_legacy_sidecar_files(output_path: str, *, verbose: bool = False) -> None:
    """
    删除旧版分散 summary 文件，避免目录里反复出现过时输出。

    清理旧版本的边车文件，确保目录中只有当前版本的输出文件。

    Args:
        output_path: 主结果文件的绝对路径。
        verbose: 是否打印清理日志。默认为 False。

    Example:
        >>> cleanup_legacy_sidecar_files("/path/to/results.json")
        >>> # 删除所有旧版边车文件

        >>> cleanup_legacy_sidecar_files("/path/to/results.json", verbose=True)
        >>> # 删除并打印清理日志

    Note:
        - 删除的文件后缀包括：
          - _submittable.json
          - _submitted.json
          - _failed_checks_summary.json
          - _template_performance_summary.json
          - _field_performance_summary.json
          - _run_config.json
        - 使用 FileNotFoundError 异常处理已删除的文件
        - verbose=True 时打印每个删除的文件路径
    """
    output = Path(output_path)
    base_dir = output.parent
    base_name = output.stem
    legacy_suffixes = (
        "_submittable.json",
        "_submitted.json",
        "_failed_checks_summary.json",
        "_template_performance_summary.json",
        "_field_performance_summary.json",
        "_run_config.json",
    )
    for suffix in legacy_suffixes:
        legacy_path = base_dir / f"{base_name}{suffix}"
        try:
            legacy_path.unlink()
            if verbose:
                print(f"[cleanup] removed legacy sidecar file {legacy_path}", flush=True)
        except FileNotFoundError:
            continue


# ============================================================================
# 结果加载函数
# ============================================================================

def load_existing_results(path: str) -> List[FieldTestResult]:
    """
    加载历史运行结果，以便续跑和复用反馈信息。

    从 JSON 文件中加载历史测试结果，用于续跑和学习历史反馈。

    Args:
        path: 结果文件的绝对路径。

    Returns:
        List[FieldTestResult]: 历史测试结果列表。
        如果文件不存在或内容无效，返回空列表。

    Raises:
        BrainAPIError: 当文件读取失败时抛出。

    Example:
        >>> results = load_existing_results("/path/to/results.json")
        >>> print(len(results))
        100

        >>> results = load_existing_results("/path/to/nonexistent.json")
        >>> print(results)
        []

    Note:
        - 从 results 字段中提取结果列表
        - 每个结果转换为 FieldTestResult 对象
        - 无效的结果项会被跳过
        - 文件不存在时返回空列表
    """
    if not path or not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:  # noqa: BLE001
        raise BrainAPIError(f"Failed to read existing results file {path}: {exc}") from exc

    rows = payload.get("results")
    if not isinstance(rows, list):
        return []

    results: List[FieldTestResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            results.append(
                FieldTestResult(
                    field_id=str(row.get("field_id", "UNKNOWN")),
                    field_type=str(row.get("field_type", "UNKNOWN")),
                    field_name=str(row.get("field_name", "UNKNOWN")),
                    template_name=str(row.get("template_name", "")),
                    simulation_id=row.get("simulation_id"),
                    alpha_id=row.get("alpha_id"),
                    status=str(row.get("status", "unknown")),
                    submittable=row.get("submittable"),
                    submitted=bool(row.get("submitted", False)),
                    message=str(row.get("message", "")),
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


# ============================================================================
# 分析函数（用于结果汇总）
# ============================================================================

def is_queue_timeout_result(result: FieldTestResult) -> bool:
    """
    判断结果是否只是平台队列超时，而非 Alpha 质量反馈。

    检查结果是否因队列超时导致失败，而不是因为 Alpha 本身质量问题。

    Args:
        result: FieldTestResult 对象。

    Returns:
        bool: 如果是队列超时返回 True，否则返回 False。

    Example:
        >>> result = FieldTestResult(
        ...     field_id="sales", failed_stage="simulate",
        ...     message="Simulation exceeded queue budget"
        ... )
        >>> is_queue_timeout_result(result)
        True

        >>> result = FieldTestResult(
        ...     field_id="sales", failed_stage="simulate",
        ...     message="LOW_SHARPE"
        ... )
        >>> is_queue_timeout_result(result)
        False

    Note:
        - 必须满足：failed_stage == "simulate"
        - 且消息中包含 "queue budget"、"queued too long" 或 "stayed queued too long"
    """
    message = str(result.message or "").lower()
    return result.failed_stage == "simulate" and (
        "queue budget" in message
        or "queued too long" in message
        or "stayed queued too long" in message
    )


def compile_template_performance_summary(results: Sequence[FieldTestResult]) -> List[Dict[str, Any]]:
    """
    构建适合写入 JSON 的模板层表现汇总。

    按模板名称聚合测试结果，生成模板级别的性能统计。

    Args:
        results: 测试结果序列。

    Returns:
        List[Dict[str, Any]]: 模板性能汇总列表，每个元素包含：
            - template_name: 模板名称
            - attempted: 尝试次数
            - submittable: 可提交次数
            - submitted: 提交次数
            - errors: 错误次数
            - queue_timeouts: 队列超时次数
            - failed_check_counts: 失败检查计数字典
            - top_failed_checks: 前 10 个失败检查项

    Example:
        >>> summary = compile_template_performance_summary(results)
        >>> print(summary[0]["template_name"])
        ts_mean_20

    Note:
        - 队列超时结果不计入 attempted
        - 按 submittable、submitted、attempted、template_name 排序
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for result in results:
        summary = grouped.setdefault(
            result.template_name,
            {
                "template_name": result.template_name,
                "attempted": 0,
                "submittable": 0,
                "submitted": 0,
                "errors": 0,
                "queue_timeouts": 0,
                "failed_check_counts": {},
            },
        )
        if is_queue_timeout_result(result):
            summary["queue_timeouts"] += 1
            continue
        summary["attempted"] += 1
        if result.submittable:
            summary["submittable"] += 1
        if result.submitted:
            summary["submitted"] += 1
        if result.status == "error":
            summary["errors"] += 1
        for check in result.failed_checks or []:
            name = str(check.get("name", "UNKNOWN"))
            summary["failed_check_counts"][name] = summary["failed_check_counts"].get(name, 0) + 1

    rows = list(grouped.values())
    for row in rows:
        counts = row["failed_check_counts"]
        row["top_failed_checks"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    return sorted(rows, key=lambda row: (-row["submittable"], -row["submitted"], -row["attempted"], row["template_name"]))


def compile_field_performance_summary(results: Sequence[FieldTestResult]) -> List[Dict[str, Any]]:
    """
    构建适合写入 JSON 的字段层表现汇总。

    按字段 ID 聚合测试结果，生成字段级别的性能统计。

    Args:
        results: 测试结果序列。

    Returns:
        List[Dict[str, Any]]: 字段性能汇总列表，每个元素包含：
            - field_id: 字段 ID
            - field_name: 字段名称
            - field_type: 字段类型
            - attempted_templates: 尝试模板数
            - submittable: 可提交次数
            - submitted: 提交次数
            - errors: 错误次数
            - queue_timeouts: 队列超时次数
            - failed_check_counts: 失败检查计数字典
            - top_failed_checks: 前 10 个失败检查项

    Example:
        >>> summary = compile_field_performance_summary(results)
        >>> print(summary[0]["field_id"])
        sales

    Note:
        - 队列超时结果不计入 attempted_templates
        - 按 submittable、submitted、attempted_templates、field_id 排序
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for result in results:
        summary = grouped.setdefault(
            result.field_id,
            {
                "field_id": result.field_id,
                "field_name": result.field_name,
                "field_type": result.field_type,
                "attempted_templates": 0,
                "submittable": 0,
                "submitted": 0,
                "errors": 0,
                "queue_timeouts": 0,
                "failed_check_counts": {},
            },
        )
        if is_queue_timeout_result(result):
            summary["queue_timeouts"] += 1
            continue
        summary["attempted_templates"] += 1
        if result.submittable:
            summary["submittable"] += 1
        if result.submitted:
            summary["submitted"] += 1
        if result.status == "error":
            summary["errors"] += 1
        for check in result.failed_checks or []:
            name = str(check.get("name", "UNKNOWN"))
            summary["failed_check_counts"][name] = summary["failed_check_counts"].get(name, 0) + 1

    rows = list(grouped.values())
    for row in rows:
        counts = row["failed_check_counts"]
        row["top_failed_checks"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    return sorted(rows, key=lambda row: (-row["submittable"], -row["submitted"], -row["attempted_templates"], row["field_id"]))


def score_failed_checks(failed_checks: Optional[Sequence[Dict[str, Any]]]) -> float:
    """
    根据失败检查项估计一个 Alpha 距离可提交状态还有多近。

    计算失败检查项的接近度分数，分数越高表示越接近可提交状态。

    Args:
        failed_checks: 失败检查项序列。

    Returns:
        float: 接近度分数（-10.0 到正数）。
        -10.0 表示无法计算或没有检查项。
        更高的分数表示更接近可提交状态。

    Example:
        >>> checks = [{"name": "LOW_SHARPE", "value": 0.95, "limit": 1.0}]
        >>> score_failed_checks(checks)
        0.95

        >>> score_failed_checks([])
        -10.0

    Note:
        - 对 LOW_ 类型检查项计算 value/limit
        - 对 CONCENTRATED_WEIGHT 计算接近度
        - 返回平均值
    """
    checks = list(failed_checks or [])
    if not checks:
        return -10.0

    score = 0.0
    counted = 0
    for check in checks:
        name = str(check.get("name", "UNKNOWN"))
        value = check.get("value")
        limit = check.get("limit")
        if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)):
            continue
        counted += 1
        if name.startswith("LOW_") and limit != 0:
            score += value / limit
        elif name == "CONCENTRATED_WEIGHT":
            score += max(0.0, 1.0 - ((value - limit) / max(abs(limit), 1e-9)))
    if counted == 0:
        return -10.0
    return score / counted


def failed_check_closeness(check: Dict[str, Any]) -> Optional[float]:
    """
    计算单个失败检查离通过阈值有多近，返回 0-1 左右的分数。

    Args:
        check: 单个失败检查项字典。

    Returns:
        Optional[float]: 接近度分数（0-1 范围）。
        如果无法计算返回 None。

    Example:
        >>> check = {"name": "LOW_SHARPE", "value": 0.9, "limit": 1.0}
        >>> failed_check_closeness(check)
        0.9

    Note:
        - LOW_ 类型检查项返回 value/limit
        - 其他类型返回 limit/value
    """
    name = str(check.get("name", "UNKNOWN"))
    value = check.get("value")
    limit = check.get("limit")
    if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)) or limit == 0:
        return None
    if name.startswith("LOW_"):
        return value / limit
    if value == 0:
        return None
    return limit / value


def failed_check_gap(check: Dict[str, Any]) -> Optional[float]:
    """
    计算失败检查到阈值的原始差距，正数表示还差多少。

    Args:
        check: 单个失败检查项字典。

    Returns:
        Optional[float]: 差距值。
        正数表示还差多少才能通过。
        如果无法计算返回 None。

    Example:
        >>> check = {"name": "LOW_SHARPE", "value": 0.9, "limit": 1.0}
        >>> failed_check_gap(check)
        0.1

    Note:
        - LOW_ 类型检查项返回 limit - value
        - 其他类型返回 value - limit
    """
    name = str(check.get("name", "UNKNOWN"))
    value = check.get("value")
    limit = check.get("limit")
    if not isinstance(value, (int, float)) or not isinstance(limit, (int, float)):
        return None
    if name.startswith("LOW_"):
        return limit - value
    return value - limit


def summarize_failed_check(check: Dict[str, Any]) -> Dict[str, Any]:
    """
    把失败检查转换成适合分析排序的紧凑结构。

    Args:
        check: 单个失败检查项字典。

    Returns:
        Dict[str, Any]: 紧凑的检查项摘要，包含：
            - name: 检查项名称
            - value: 实际值
            - limit: 阈值
            - gap: 差距
            - closeness: 接近度

    Example:
        >>> check = {"name": "LOW_SHARPE", "value": 0.9, "limit": 1.0}
        >>> summarize_failed_check(check)
        {'name': 'LOW_SHARPE', 'value': 0.9, 'limit': 1.0, 'gap': 0.1, 'closeness': 0.9}
    """
    return {
        "name": check.get("name"),
        "value": check.get("value"),
        "limit": check.get("limit"),
        "gap": failed_check_gap(check),
        "closeness": failed_check_closeness(check),
    }


def compile_failed_check_leaderboard(results: Sequence[FieldTestResult]) -> List[Dict[str, Any]]:
    """
    统计失败检查排行榜，帮助判断整体策略主要卡在哪里。

    按失败检查项名称聚合，生成排行榜统计。

    Args:
        results: 测试结果序列。

    Returns:
        List[Dict[str, Any]]: 失败检查排行榜，每个元素包含：
            - name: 检查项名称
            - count: 出现次数
            - avg_value: 平均实际值
            - avg_limit: 平均阈值
            - avg_gap: 平均差距
            - avg_closeness: 平均接近度
            - example_alpha_ids: 示例 Alpha ID（最多 5 个）

    Example:
        >>> leaderboard = compile_failed_check_leaderboard(results)
        >>> print(leaderboard[0]["name"])
        LOW_SHARPE

    Note:
        - 队列超时结果不计入统计
        - 按 count、avg_closeness、name 排序
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    for result in results:
        if is_queue_timeout_result(result):
            continue
        for check in result.failed_checks or []:
            name = str(check.get("name", "UNKNOWN"))
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
            if result.alpha_id and result.alpha_id not in row["example_alpha_ids"] and len(row["example_alpha_ids"]) < 5:
                row["example_alpha_ids"].append(result.alpha_id)

    leaderboard: List[Dict[str, Any]] = []
    for row in grouped.values():
        values = row.pop("values")
        limits = row.pop("limits")
        gaps = row.pop("gaps")
        closeness_scores = row.pop("closeness_scores")
        row["avg_value"] = sum(values) / len(values) if values else None
        row["avg_limit"] = sum(limits) / len(limits) if limits else None
        row["avg_gap"] = sum(gaps) / len(gaps) if gaps else None
        row["avg_closeness"] = sum(closeness_scores) / len(closeness_scores) if closeness_scores else None
        leaderboard.append(row)
    return sorted(leaderboard, key=lambda row: (-row["count"], -(row["avg_closeness"] or -999.0), row["name"]))


def compile_near_pass_summary(results: Sequence[FieldTestResult], limit: int = 20) -> List[Dict[str, Any]]:
    """
    列出最接近通过检查的 Alpha，用于指导下一轮变体搜索。

    找出最接近可提交状态的 Alpha，按接近度分数排序。

    Args:
        results: 测试结果序列。
        limit: 返回结果数量限制。默认为 20。

    Returns:
        List[Dict[str, Any]]: 接近通过汇总列表，每个元素包含：
            - score: 接近度分数
            - field_id: 字段 ID
            - field_name: 字段名称
            - field_type: 字段类型
            - template_name: 模板名称
            - alpha_id: Alpha ID
            - expression: Alpha 表达式
            - message: 结果消息
            - failed_checks: 失败检查摘要列表

    Example:
        >>> near_pass = compile_near_pass_summary(results)
        >>> print(near_pass[0]["score"])
        0.95

    Note:
        - 只包含模拟成功但未可提交的结果
        - 队列超时结果不计入
        - 按 score、field_id、template_name 排序
    """
    rows: List[Dict[str, Any]] = []
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
                "failed_checks": [summarize_failed_check(check) for check in result.failed_checks or []],
            }
        )
    return sorted(rows, key=lambda row: (-row["score"], row["field_id"], row["template_name"]))[:limit]


def compile_optimization_hints(
    failed_check_leaderboard: Sequence[Dict[str, Any]],
    near_pass_summary: Sequence[Dict[str, Any]],
) -> List[str]:
    """
    根据失败分布生成下一轮搜索建议。

    根据失败检查排行榜和接近通过汇总，生成优化建议。

    Args:
        failed_check_leaderboard: 失败检查排行榜。
        near_pass_summary: 接近通过汇总。

    Returns:
        List[str]: 优化建议字符串列表。

    Example:
        >>> hints = compile_optimization_hints(leaderboard, near_pass)
        >>> print(hints[0])
        'Sharpe is the dominant blocker; prioritize group-neutralized...'

    Note:
        - 根据前 3 个主要失败检查项生成建议
        - 包含 Sharpe、Fitness、Turnover 等常见问题建议
        - 包含最佳接近通过候选的建议
    """
    dominant_names = {str(row.get("name")) for row in failed_check_leaderboard[:3]}
    hints: List[str] = []
    if not failed_check_leaderboard:
        return ["No failed checks recorded yet; run a wider exploration sample first."]
    if "LOW_SHARPE" in dominant_names or "LOW_SUB_UNIVERSE_SHARPE" in dominant_names:
        hints.append("Sharpe is the dominant blocker; prioritize group-neutralized, zscore/spread, and less raw level-like templates.")
    if "LOW_FITNESS" in dominant_names:
        hints.append("Fitness is weak; prioritize expressions that improve both Sharpe and turnover instead of only smoothing levels.")
    if "LOW_TURNOVER" in dominant_names:
        hints.append("Turnover is too low; try shorter delta windows, rank-then-delta variants, or lower decay.")
    if "HIGH_TURNOVER" in dominant_names:
        hints.append("Turnover is too high; try longer windows, higher decay, or smoother ts_mean/ts_decay structures.")
    if "CONCENTRATED_WEIGHT" in dominant_names:
        hints.append("Weight concentration is high; prefer group_rank/group_zscore variants and avoid raw ratios or sparse level signals.")
    if near_pass_summary:
        best = near_pass_summary[0]
        hints.append(
            f"Best near-pass candidate: field={best['field_id']} template={best['template_name']} score={best['score']:.3f}; prioritize local variants of this expression."
        )
    return hints


# ============================================================================
# 结果保存函数
# ============================================================================

def dump_results(
    path: str,
    dataset_id: str,
    results: List[FieldTestResult],
    *,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    持久化完整运行结果，并写入一个统一分析文件。

    将测试结果保存到主结果文件和配套的分析文件中，
    包含完整的统计信息和分析摘要。

    Args:
        path: 主结果文件的绝对路径。
        dataset_id: 数据集标识符。
        results: 测试结果列表。
        settings_fingerprint: 设置配置指纹。
        template_library_fingerprint: 模板库指纹。
        run_config: 运行配置字典。默认为 None。

    Example:
        >>> dump_results(
        ...     "/path/to/results.json",
        ...     "fundamental6",
        ...     results,
        ...     settings_fingerprint="abc123",
        ...     template_library_fingerprint="def456"
        ... )
        >>> # 文件已保存

    Note:
        - 主结果文件包含完整结果列表和基本统计
        - 分析文件包含各种汇总统计和优化建议
        - 自动清理旧版边车文件
        - 使用原子写入确保数据安全
    """
    # 原始结果保存在主文件中用于续跑/去重
    # 分析保存在配套文件中使目录易于理解
    sidecar_paths = build_output_sidecar_paths(path)
    submittable_results = [result.__dict__ for result in results if result.submittable]
    submitted_results = [result.__dict__ for result in results if result.submitted]
    failed_checks_summary = [
        {
            "field_id": result.field_id,
            "template_name": result.template_name,
            "expression": result.expression,
            "failed_checks": result.failed_checks or [],
        }
        for result in results
        if result.failed_checks
    ]
    template_performance_summary = compile_template_performance_summary(results)
    field_performance_summary = compile_field_performance_summary(results)
    failed_check_leaderboard = compile_failed_check_leaderboard(results)
    near_pass_summary = compile_near_pass_summary(results)
    optimization_hints = compile_optimization_hints(failed_check_leaderboard, near_pass_summary)
    summary = {
        "dataset_id": dataset_id,
        "run_config": run_config or {},
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "tested": len(results),
        "unique_fields_tested": len({result.field_id for result in results}),
        "submittable": sum(1 for result in results if result.submittable),
        "submitted": sum(1 for result in results if result.submitted),
        "errors": sum(1 for result in results if result.status == "error"),
        "queue_timeouts": sum(1 for result in results if is_queue_timeout_result(result)),
        "results": [result.__dict__ for result in results],
    }
    analysis = {
        "dataset_id": dataset_id,
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "tested": summary["tested"],
        "unique_fields_tested": summary["unique_fields_tested"],
        "submittable_count": summary["submittable"],
        "submitted_count": summary["submitted"],
        "error_count": summary["errors"],
        "queue_timeout_count": summary["queue_timeouts"],
        "submittable": submittable_results,
        "submitted": submitted_results,
        "failed_checks_summary": failed_checks_summary,
        "failed_check_leaderboard": failed_check_leaderboard,
        "near_pass_summary": near_pass_summary,
        "optimization_hints": optimization_hints,
        "template_performance_summary": template_performance_summary,
        "field_performance_summary": field_performance_summary,
    }
    atomic_write_json(path, summary)
    atomic_write_json(sidecar_paths["analysis"], analysis)
    cleanup_legacy_sidecar_files(path)
    print(f"[done] wrote results to {path}", flush=True)
    print(f"[done] wrote analysis to {sidecar_paths['analysis']}", flush=True)


# ============================================================================
# 分析文件同步函数
# ============================================================================

def ensure_analysis_synced(output_path: str) -> None:
    """
    确保 analysis 派生文件与主结果文件一致。

    检查分析文件是否与主结果文件同步，
    如果不同步则重新生成分析文件。

    Args:
        output_path: 主结果文件的绝对路径。

    Example:
        >>> ensure_analysis_synced("/path/to/results.json")
        >>> # 分析文件已同步

        >>> # 如果分析文件不存在或内容不一致
        >>> ensure_analysis_synced("/path/to/results.json")
        >>> # 重新生成分析文件并打印日志

    Note:
        - 如果主结果文件不存在，直接返回
        - 比较 tested、settings_fingerprint、template_library_fingerprint
        - 如果不同步，重新构建分析文件
    """
    if not output_path or not os.path.exists(output_path):
        return
    sidecar_paths = build_output_sidecar_paths(output_path)
    try:
        with open(output_path, "r", encoding="utf-8") as handle:
            summary = json.load(handle)
    except Exception as exc:  # noqa: BLE001
        print(f"[analysis] skipped sync; failed to read main results: {exc}", flush=True)
        return

    should_rebuild = not os.path.exists(sidecar_paths["analysis"])
    if not should_rebuild:
        try:
            with open(sidecar_paths["analysis"], "r", encoding="utf-8") as handle:
                analysis = json.load(handle)
            should_rebuild = (
                analysis.get("tested") != summary.get("tested")
                or analysis.get("settings_fingerprint") != summary.get("settings_fingerprint")
                or analysis.get("template_library_fingerprint") != summary.get("template_library_fingerprint")
            )
        except Exception:
            should_rebuild = True

    if not should_rebuild:
        return

    results = load_existing_results(output_path)
    dump_results(
        output_path,
        str(summary.get("dataset_id", DEFAULT_DATASET_ID)),
        results,
        settings_fingerprint=str(summary.get("settings_fingerprint", "")),
        template_library_fingerprint=str(summary.get("template_library_fingerprint", "")),
        run_config=summary.get("run_config") if isinstance(summary.get("run_config"), dict) else {},
    )
    print(f"[analysis] rebuilt analysis from main results: {sidecar_paths['analysis']}", flush=True)