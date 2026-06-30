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

from __future__ import annotations

from contextlib import suppress
import json
import logging
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any

# 分析函数统一从 stats 模块导入（避免重复定义）
from ..analysis.stats import (
    compile_failed_check_leaderboard,
    compile_field_performance_summary,
    compile_near_pass_summary,
    compile_optimization_hints,
    compile_template_performance_summary,
    is_queue_timeout_result,
    load_existing_results,
)
from ..config import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    DEFAULT_DATASET_ID,
    DatasetExpressionPolicy,
    get_dataset_expression_policy,
)
from ..models.base import FieldTestResult

logger = logging.getLogger(__name__)


def _load_results_rows_from_journal(journal_path: str) -> list[dict[str, Any]]:
    """从 results journal 读取原始结果字典行。"""
    if not os.path.exists(journal_path):
        return []
    rows: list[dict[str, Any]] = []
    with open(journal_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def load_blacklisted_template_names(dataset_id: str, *, data_dir: str = "") -> set[str]:
    """读取当前数据集已存在的黑名单模板名集合。"""
    blacklist_path = _resolve_blacklist_path(dataset_id, data_dir=data_dir)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        else:
            return set()
    except (json.JSONDecodeError, OSError):
        return set()
    if not isinstance(payload, dict):
        return set()
    entries = payload.get("blacklisted_templates", [])
    if not isinstance(entries, list):
        return set()
    return {
        str(item.get("name"))
        for item in entries
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }

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
    if not path:
        return
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            with suppress(OSError):
                os.remove(temp_path)


# ============================================================================
# CLI 路径解析函数
# ============================================================================


def resolve_cli_path(path: str, *, base_dir: str | None = None) -> str:
    """
    将 CLI 文件路径解析为相对于指定基准目录的绝对路径。

    如果路径是相对路径，将其转换为相对于指定基准目录的绝对路径；
    如果已经是绝对路径，直接返回。

    Args:
        path: CLI 参数提供的文件路径（可能为相对或绝对路径）。
        base_dir: 解析相对路径时使用的基准目录。留空时使用当前工作目录。

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
        - 相对路径默认相对于当前工作目录解析
        - 绝对路径直接返回
    """
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        base_path = Path(base_dir).expanduser() if base_dir else Path.cwd()
        candidate = base_path / candidate
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


def build_dataset_scoped_paths(
    dataset_id: str,
    *,
    region: str = "",
    universe: str = "",
    instrument_type: str = "",
    delay: int | None = None,
) -> dict[str, str]:
    """
    根据 dataset_id 派生默认缓存、结果与模板库路径。

    根据数据集标识符和运行上下文生成默认的文件路径，
    包括模板库文件、字段缓存文件和结果输出文件。

    Args:
        dataset_id: 数据集标识符字符串。
        region: 地区代码。
        universe: 股票池代码。
        instrument_type: 标的类型。
        delay: 延迟天数。

    Returns:
        dict[str, str]: 包含以下键的路径字典：
            - template_library_file: 模板库文件路径
            - fields_cache_file: 字段缓存文件路径
            - output: 结果输出文件路径

    Example:
        >>> paths = build_dataset_scoped_paths("fundamental6")
        >>> print(paths["fields_cache_file"])
        /path/to/project_root/cache/fields/fundamental6/fields.json

        >>> paths = build_dataset_scoped_paths("my_dataset")
        >>> print(paths["output"])
        /path/to/project_root/results/my_dataset/test_results.json

    Note:
        - 所有路径都相对于 PROJECT_ROOT
        - 文件名使用 sanitize_dataset_id_for_filename 安全化
        - 基础模板文件留在 data/worldquant_template_library.json
        - 专属模板路径格式：data/templates/{dataset}/library.json
        - 专属黑名单路径格式：data/blacklists/{dataset}/blacklist.json
        - 字段缓存路径格式：cache/fields/{dataset}/{region}/{universe}/{instrument}/{delay}/fields.json
        - 结果文件路径格式：results/{sanitized}/test_results.json
    """
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    cache_parts = [CACHE_DIR / "fields" / dataset_key]
    if region:
        cache_parts.append(sanitize_dataset_id_for_filename(region))
    if universe:
        cache_parts.append(sanitize_dataset_id_for_filename(universe))
    if instrument_type:
        cache_parts.append(sanitize_dataset_id_for_filename(instrument_type))
    if delay is not None:
        cache_parts.append(f"delay{int(delay)}")
    fields_cache_path = Path(*cache_parts) / "fields.json"
    return {
        "template_library_file": str(DATA_DIR / "templates" / dataset_key / "library.json"),
        "fields_cache_file": str(fields_cache_path),
        "output": str(RESULTS_DIR / dataset_key / "test_results.json"),
    }


# ============================================================================
# 边车文件路径构建函数
# ============================================================================


def build_output_sidecar_paths(output_path: str) -> dict[str, str]:
    """
    生成主结果文件旁边的精简分析与日志路径。

    根据主结果文件路径，生成配套的分析文件和运行日志文件路径。

    Args:
        output_path: 主结果文件的绝对路径。

    Returns:
        dict[str, str]: 包含以下键的路径字典：
            - analysis: 分析文件路径（{basename}_analysis.json）
            - run_log: 运行日志文件路径（{basename}_{date}.log）

    Example:
        >>> paths = build_output_sidecar_paths("/path/to/results.json")
        >>> print(paths["analysis"])
        /path/to/results_analysis.json
        >>> # run_log 包含日期，如 results_2024-01-01.log

    Note:
        - 分析文件名在主文件名后添加 _analysis
        - 日志文件名包含日期（YYYY-MM-DD 格式）
        - 所有边车文件都在同一目录下
    """
    output = Path(output_path)
    base_dir = output.parent
    base_name = output.stem or "results"
    if not output.suffix:
        base_name = output.name or "results"
    log_date = time.strftime("%Y-%m-%d")
    return {
        "analysis": str(base_dir / f"{base_name}_analysis.json"),
        "results_journal": str(base_dir / f"{base_name}_results.jsonl"),
        "run_log": str(base_dir / f"{base_name}_{log_date}.log"),
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
                logger.info("[cleanup] removed legacy sidecar file %s", legacy_path)
        except FileNotFoundError:
            continue


# ============================================================================
# 结果保存函数
# ============================================================================


def dump_results(
    path: str,
    dataset_id: str,
    results: list[FieldTestResult],
    *,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict[str, Any] | None = None,
    auto_update_template_blacklist: bool = False,
    include_analysis: bool = True,
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
        auto_update_template_blacklist: 是否根据运行结果自动写入模板黑名单。
            默认为 False，避免普通运行修改仓库中受 Git 跟踪的 data/ 文件。
        include_analysis: 是否同步重建分析边车文件。中间过程可关闭以减少
            每条结果都全量分析的开销；最终收尾时应开启。

    Example:
        >>> dump_results(
        ...     "/path/to/results.json",
        ...     "fundamental6",
        ...     results,
        ...     settings_fingerprint="abc123",
        ...     template_library_fingerprint="def456",
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

    # 单次遍历构建所有需要的数据（性能优化）
    results_dicts = []
    submittable_results = []
    submitted_results = []
    failed_checks_summary = []
    field_ids = set()
    submittable_count = 0
    submitted_count = 0
    error_count = 0
    queue_timeout_count = 0

    for result in results:
        d = result.to_dict()
        results_dicts.append(d)
        field_ids.add(result.field_id)

        if result.submittable:
            submittable_count += 1
            submittable_results.append(d)
        if result.submitted:
            submitted_count += 1
            submitted_results.append(d)
        if result.status == "error":
            error_count += 1
        if is_queue_timeout_result(result):
            queue_timeout_count += 1
        if result.failed_checks:
            failed_checks_summary.append(
                {
                    "field_id": result.field_id,
                    "template_name": result.template_name,
                    "expression": result.expression,
                    "failed_checks": result.failed_checks,
                }
            )
    summary = {
        "dataset_id": dataset_id,
        "run_config": run_config or {},
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "tested": len(results),
        "unique_fields_tested": len(field_ids),
        "submittable": submittable_count,
        "submitted": submitted_count,
        "errors": error_count,
        "queue_timeouts": queue_timeout_count,
        "results_embedded": True,
        "results_journal": sidecar_paths["results_journal"],
        "results": results_dicts,
    }
    atomic_write_json(path, summary)
    initialize_results_journal(path, results)
    if include_analysis:
        template_performance_summary = compile_template_performance_summary(results)
        field_performance_summary = compile_field_performance_summary(results)
        failed_check_leaderboard = compile_failed_check_leaderboard(results)
        near_pass_summary = compile_near_pass_summary(results)
        optimization_hints = compile_optimization_hints(
            failed_check_leaderboard,
            near_pass_summary,
        )
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
        atomic_write_json(sidecar_paths["analysis"], analysis)
    cleanup_legacy_sidecar_files(path)
    logger.info(
        "[done] wrote results to %s (tested=%d, submittable=%d)",
        path,
        len(results),
        submittable_count,
    )
    if include_analysis:
        logger.debug(
            "[done] wrote analysis to %s",
            sidecar_paths["analysis"],
        )

    if auto_update_template_blacklist:
        auto_update_blacklist(results, dataset_id)


def initialize_results_journal(output_path: str, results: list[FieldTestResult]) -> int:
    """用当前完整结果列表重建 journal，供运行中增量追加使用。"""
    sidecar_paths = build_output_sidecar_paths(output_path)
    journal_path = sidecar_paths["results_journal"]
    directory = os.path.dirname(os.path.abspath(journal_path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".jsonl", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for result in results:
                handle.write(json.dumps(result.to_dict(), ensure_ascii=False))
                handle.write("\n")
        os.replace(temp_path, journal_path)
    finally:
        if os.path.exists(temp_path):
            with suppress(OSError):
                os.remove(temp_path)
    return len(results)


def _append_results_journal(journal_path: str, results: list[FieldTestResult]) -> None:
    """把新增结果追加到 journal。"""
    if not results:
        return
    directory = os.path.dirname(os.path.abspath(journal_path)) or "."
    os.makedirs(directory, exist_ok=True)
    with open(journal_path, "a", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result.to_dict(), ensure_ascii=False))
            handle.write("\n")


def dump_results_incremental(
    path: str,
    dataset_id: str,
    new_results: list[FieldTestResult],
    *,
    persisted_result_count: int,
    tested: int,
    unique_fields_tested: int,
    submittable_count: int,
    submitted_count: int,
    error_count: int,
    queue_timeout_count: int,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict[str, Any] | None = None,
) -> int:
    """仅把新增结果追加到 journal，并写轻量 summary。"""
    sidecar_paths = build_output_sidecar_paths(path)
    if new_results:
        _append_results_journal(sidecar_paths["results_journal"], new_results)
    summary = {
        "dataset_id": dataset_id,
        "run_config": run_config or {},
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "tested": tested,
        "unique_fields_tested": unique_fields_tested,
        "submittable": submittable_count,
        "submitted": submitted_count,
        "errors": error_count,
        "queue_timeouts": queue_timeout_count,
        "results_embedded": False,
        "results_journal": sidecar_paths["results_journal"],
    }
    atomic_write_json(path, summary)
    cleanup_legacy_sidecar_files(path)
    logger.info(
        "[done] wrote incremental results to %s (tested=%d, submittable=%d, appended=%d)",
        path,
        tested,
        submittable_count,
        len(new_results),
    )
    return persisted_result_count + len(new_results)


# ============================================================================
# 模板黑名单自动更新
# ============================================================================

_BLACKLIST_PATH_CACHE: dict[str, str] = {}


def _resolve_blacklist_path(dataset_id: str, *, data_dir: str = "") -> str:
    """按数据集解析黑名单文件路径：blacklists/{dataset_id}/blacklist.json。"""
    global _BLACKLIST_PATH_CACHE
    cache_key = f"{dataset_id}|{data_dir}" if data_dir else dataset_id
    if cache_key in _BLACKLIST_PATH_CACHE:
        return _BLACKLIST_PATH_CACHE[cache_key]
    base = Path(data_dir) if data_dir else DATA_DIR
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    resolved = str(base / "blacklists" / dataset_key / "blacklist.json")
    _BLACKLIST_PATH_CACHE[cache_key] = resolved
    return resolved


def _build_default_blacklist(dataset_id: str) -> dict[str, Any]:
    """构建单个数据集的黑名单骨架结构。"""
    return {
        "_version": "v2",
        "_comment": f"Template blacklist for {dataset_id} — auto-populated from test results.",
        "_created": time.strftime("%Y-%m-%d"),
        "_updated": time.strftime("%Y-%m-%d"),
        "dataset_id": dataset_id,
        "blacklisted_templates": [],
        "auto_avoid_rules": [],
    }


def ensure_template_blacklist_file(dataset_id: str, *, data_dir: str = "") -> str:
    """
    确保 dataset 专属模板黑名单文件存在，不存在时创建空骨架。

    Args:
        dataset_id: 数据集 ID，如 fundamental6。
        data_dir: 可选数据目录，测试或自定义部署时使用。

    Returns:
        str: 黑名单文件路径。
    """
    blacklist_path = _resolve_blacklist_path(dataset_id, data_dir=data_dir)
    if os.path.isfile(blacklist_path):
        return blacklist_path

    atomic_write_json(blacklist_path, _build_default_blacklist(dataset_id))
    logger.info("[blacklist] created dataset blacklist file: %s", blacklist_path)
    return blacklist_path


def _update_blacklist_runtime_stats_with_result(
    stats: dict[str, dict[str, Any]],
    result: FieldTestResult,
) -> dict[str, Any] | None:
    """把单条结果增量合并到模板黑名单聚合状态中。"""
    from ..analysis.stats import is_informative_result

    if not is_informative_result(result):
        return None
    template_name = result.template_name
    summary = stats.setdefault(
        template_name,
        {
            "template_name": template_name,
            "field_type": result.field_type,
            "template_family": result.template_family,
            "template_stage": result.template_stage,
            "fields_tested": [],
            "_field_names_seen": set(),
            "submittable": 0,
            "low_sharpe": 0,
            "low_fitness": 0,
            "concentrated_weight": 0,
            "sharpe_sum": 0.0,
            "sharpe_count": 0,
            "fitness_sum": 0.0,
            "fitness_count": 0,
        },
    )
    field_name = str(result.field_name or "")
    if field_name and field_name not in summary["_field_names_seen"]:
        summary["_field_names_seen"].add(field_name)
        summary["fields_tested"].append(field_name)
    if result.submittable:
        summary["submittable"] += 1
    for check in result.failed_checks or []:
        name = str(check.get("name", ""))
        value = check.get("value")
        if name == CHECK_LOW_SHARPE:
            summary["low_sharpe"] += 1
            if isinstance(value, (int, float)):
                summary["sharpe_sum"] += float(value)
                summary["sharpe_count"] += 1
        elif name == CHECK_LOW_FITNESS:
            summary["low_fitness"] += 1
            if isinstance(value, (int, float)):
                summary["fitness_sum"] += float(value)
                summary["fitness_count"] += 1
        elif name == CHECK_CONCENTRATED_WEIGHT:
            summary["concentrated_weight"] += 1
    return summary


def build_blacklist_runtime_stats(results: list[FieldTestResult]) -> dict[str, dict[str, Any]]:
    """从完整结果列表构建黑名单增量聚合状态。"""
    stats: dict[str, dict[str, Any]] = {}
    for result in results:
        _update_blacklist_runtime_stats_with_result(stats, result)
    return stats


def _build_blacklist_entry_from_runtime_summary(
    summary: dict[str, Any],
    *,
    dataset_id: str,
    policy: DatasetExpressionPolicy,
    min_fields_tested: int,
    min_fail_checks: int,
) -> dict[str, Any] | None:
    """按增量聚合状态判断某模板是否应进入黑名单。"""
    template_name = str(summary.get("template_name", "")).strip()
    if not template_name or template_name in policy.protected_templates:
        return None
    fields_tested = list(summary.get("fields_tested", []))
    if len(fields_tested) < min_fields_tested:
        return None
    if int(summary.get("submittable", 0)) > 0:
        return None
    low_sharpe_count = int(summary.get("low_sharpe", 0))
    low_fitness_count = int(summary.get("low_fitness", 0))
    concentrated_count = int(summary.get("concentrated_weight", 0))
    total_fails = low_sharpe_count + low_fitness_count
    if total_fails < min_fail_checks:
        return None
    sharpe_count = int(summary.get("sharpe_count", 0))
    fitness_count = int(summary.get("fitness_count", 0))
    avg_sharpe = (
        round(float(summary.get("sharpe_sum", 0.0)) / sharpe_count, 3)
        if sharpe_count > 0
        else None
    )
    avg_fitness = (
        round(float(summary.get("fitness_sum", 0.0)) / fitness_count, 3)
        if fitness_count > 0
        else None
    )
    if (
        policy.blacklist_min_fields_for_nearpass > 0
        and len(fields_tested) < policy.blacklist_min_fields_for_nearpass
        and (
            (
                avg_sharpe is not None
                and avg_sharpe >= policy.blacklist_protected_min_avg_sharpe
            )
            or (
                avg_fitness is not None
                and avg_fitness >= policy.blacklist_protected_min_avg_fitness
            )
        )
    ):
        return None
    reason_parts = [f"{len(fields_tested)}个字段测试均不通过"]
    if avg_sharpe is not None:
        reason_parts.append(f"平均 Sharpe {avg_sharpe:.3f}")
    if avg_fitness is not None:
        reason_parts.append(f"平均 Fitness {avg_fitness:.3f}")
    from datetime import datetime

    entry: dict[str, Any] = {
        "name": template_name,
        "dataset_id": dataset_id,
        "source": "auto_detected",
        "field_type": str(summary.get("field_type", "")),
        "template_family": str(summary.get("template_family", "")),
        "template_stage": str(summary.get("template_stage", "")),
        "reason": "。".join(reason_parts) + "。",
        "fields_tested": fields_tested,
        "low_sharpe": low_sharpe_count,
        "low_fitness": low_fitness_count,
        "date_blacklisted": datetime.now().strftime("%Y-%m-%d"),
    }
    if avg_sharpe is not None:
        entry["avg_sharpe"] = avg_sharpe
    if avg_fitness is not None:
        entry["avg_fitness"] = avg_fitness
    if concentrated_count:
        entry["concentrated_weight"] = concentrated_count
    return entry


def auto_update_blacklist(
    results: list[FieldTestResult],
    dataset_id: str,
    *,
    data_dir: str = "",
    min_fields_tested: int = 2,
    min_fail_checks: int = 2,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> None:
    """
    根据测试结果自动更新 template_blacklist.json 中的失败模板记录。

    每次 dump_results 时调用。分析当前结果中按模板名聚合的质量反馈，
    将一致不合格的模板追加到对应数据集的黑名单中，供后续运行跳过。

    自动黑名单的条件（全部满足才加入）：
        - 模板在至少 min_fields_tested 个不同字段上测试过
        - 无任何 submittable=True 的结果（全败）
        - 失败检查 (LOW_SHARPE / LOW_FITNESS) 累计 >= min_fail_checks

    Args:
        results: 当前运行的全部测试结果。
        dataset_id: 数据集标识符（如 "fundamental6"）。
        data_dir: 数据目录路径（默认使用内置 DATA_DIR）。
        min_fields_tested: 最少测试字段数阈值。
        min_fail_checks: 最少失败检查次数阈值。
    """
    if not dataset_id or not results:
        return
    from datetime import datetime

    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    runtime_stats = build_blacklist_runtime_stats(results)
    new_entries: list[dict[str, Any]] = []
    for summary in runtime_stats.values():
        entry = _build_blacklist_entry_from_runtime_summary(
            summary,
            dataset_id=dataset_id,
            policy=policy,
            min_fields_tested=min_fields_tested,
            min_fail_checks=min_fail_checks,
        )
        if entry is not None:
            new_entries.append(entry)

    if not new_entries:
        return

    # 4. 加载或创建数据集专属黑名单文件
    blacklist_path = _resolve_blacklist_path(dataset_id, data_dir=data_dir)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as fh:
                bl_data = json.load(fh)
        else:
            bl_data = _build_default_blacklist(dataset_id)
    except (json.JSONDecodeError, OSError):
        bl_data = _build_default_blacklist(dataset_id)

    # 确保数据结构完整
    if not isinstance(bl_data, dict):
        bl_data = _build_default_blacklist(dataset_id)
    bl_data.setdefault("dataset_id", dataset_id)
    bl_data.setdefault("blacklisted_templates", [])
    bl_data.setdefault("auto_avoid_rules", [])

    # 5. 合并新条目（去重：同名模板已存在则跳过）
    existing_names = {
        item["name"]
        for item in bl_data["blacklisted_templates"]
        if isinstance(item, dict) and item.get("name")
    }
    added = 0
    for entry in new_entries:
        if entry["name"] not in existing_names:
            bl_data["blacklisted_templates"].append(entry)
            existing_names.add(entry["name"])
            added += 1

    if added == 0:
        return

    # 6. 更新时间戳并写回
    bl_data["_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    atomic_write_json(blacklist_path, bl_data)
    # 同进程续跑时需要立刻看到新黑名单，而不是等下次启动再生效。
    from ..generators.expressions import invalidate_blacklist_cache

    invalidate_blacklist_cache(dataset_id)
    logger.info(
        "[blacklist] auto-updated %s: added %d new entries (total=%d)",
        blacklist_path,
        added,
        len(bl_data["blacklisted_templates"]),
    )


def auto_update_blacklist_incremental(
    runtime_stats: dict[str, dict[str, Any]],
    blacklisted_template_names: set[str],
    result: FieldTestResult,
    dataset_id: str,
    *,
    data_dir: str = "",
    min_fields_tested: int = 2,
    min_fail_checks: int = 2,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> bool:
    """仅对本次变化的模板尝试增量写入黑名单。"""
    from datetime import datetime

    if not dataset_id:
        return False
    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    summary = _update_blacklist_runtime_stats_with_result(runtime_stats, result)
    if summary is None:
        return False
    template_name = str(summary.get("template_name", "")).strip()
    if not template_name or template_name in blacklisted_template_names:
        return False
    entry = _build_blacklist_entry_from_runtime_summary(
        summary,
        dataset_id=dataset_id,
        policy=policy,
        min_fields_tested=min_fields_tested,
        min_fail_checks=min_fail_checks,
    )
    if entry is None:
        return False
    blacklist_path = _resolve_blacklist_path(dataset_id, data_dir=data_dir)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as fh:
                bl_data = json.load(fh)
        else:
            bl_data = _build_default_blacklist(dataset_id)
    except (json.JSONDecodeError, OSError):
        bl_data = _build_default_blacklist(dataset_id)
    if not isinstance(bl_data, dict):
        bl_data = _build_default_blacklist(dataset_id)
    bl_data.setdefault("dataset_id", dataset_id)
    bl_data.setdefault("blacklisted_templates", [])
    bl_data.setdefault("auto_avoid_rules", [])
    existing_names = {
        item["name"]
        for item in bl_data["blacklisted_templates"]
        if isinstance(item, dict) and item.get("name")
    }
    if entry["name"] in existing_names:
        blacklisted_template_names.add(entry["name"])
        return False
    bl_data["blacklisted_templates"].append(entry)
    bl_data["_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    atomic_write_json(blacklist_path, bl_data)
    from ..generators.expressions import invalidate_blacklist_cache

    invalidate_blacklist_cache(dataset_id)
    blacklisted_template_names.add(entry["name"])
    logger.info(
        "[blacklist] incrementally added %s to %s (total=%d)",
        entry["name"],
        blacklist_path,
        len(bl_data["blacklisted_templates"]),
    )
    return True


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
        with open(output_path, encoding="utf-8") as handle:
            summary = json.load(handle)
    except Exception as exc:
        logger.warning("[analysis] skipped sync; failed to read main results: %s", exc)
        return
    if not isinstance(summary, dict):
        logger.warning(
            "[analysis] skipped sync; unexpected main results JSON type: %s",
            type(summary).__name__,
        )
        return

    should_rebuild = not os.path.exists(sidecar_paths["analysis"])
    if not should_rebuild:
        try:
            with open(sidecar_paths["analysis"], encoding="utf-8") as handle:
                analysis = json.load(handle)
            if not isinstance(analysis, dict):
                should_rebuild = True
            else:
                should_rebuild = (
                    analysis.get("tested") != summary.get("tested")
                    or analysis.get("settings_fingerprint") != summary.get("settings_fingerprint")
                    or analysis.get("template_library_fingerprint")
                    != summary.get("template_library_fingerprint")
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
    logger.info("[analysis] rebuilt analysis from main results: %s", sidecar_paths["analysis"])
