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

import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any

from ..analysis.report_builder import (
    build_analysis_payload,
    build_results_summary_payload,
)
from ..analysis.stats import load_existing_results
from ..config import DEFAULT_DATASET_ID
from ..io.common import (
    CACHE_DIR as _COMMON_CACHE_DIR,
    DATA_DIR as _COMMON_DATA_DIR,
    PROJECT_ROOT as _COMMON_PROJECT_ROOT,
    RESULTS_DIR as _COMMON_RESULTS_DIR,
    SCRIPT_DIR as _COMMON_SCRIPT_DIR,
    atomic_write_json,
    sanitize_dataset_id_for_filename,
)
from ..models.base import FieldTestResult
from ..policy.blacklist import (
    _BLACKLIST_PATH_CACHE,
    auto_update_blacklist,
    auto_update_blacklist_incremental,
    build_blacklist_runtime_stats,
    ensure_template_blacklist_file,
    load_blacklisted_template_names as _load_blacklisted_template_names,
)

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
    """兼容导出：读取当前数据集已存在的黑名单模板名集合。"""
    return _load_blacklisted_template_names(dataset_id, data_dir=data_dir)

# ============================================================================
# 常量定义
# ============================================================================

SCRIPT_DIR = _COMMON_SCRIPT_DIR
"""脚本目录的绝对路径"""

PROJECT_ROOT = _COMMON_PROJECT_ROOT
"""项目根目录的绝对路径（alpha/ 目录）"""

CACHE_DIR = _COMMON_CACHE_DIR
RESULTS_DIR = _COMMON_RESULTS_DIR
DATA_DIR = _COMMON_DATA_DIR
"""数据文件目录"""


# ============================================================================
# 辅助函数
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
        - 基础模板文件位于 data/templates/base/library.json
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
    sidecar_paths = build_output_sidecar_paths(path)
    summary, analysis_inputs = build_results_summary_payload(
        dataset_id,
        results,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
        results_journal_path=sidecar_paths["results_journal"],
    )
    summary["results_embedded"] = True
    atomic_write_json(path, summary)
    initialize_results_journal(path, results)
    if include_analysis:
        analysis = build_analysis_payload(results, summary, analysis_inputs)
        atomic_write_json(sidecar_paths["analysis"], analysis)
    cleanup_legacy_sidecar_files(path)
    logger.info(
        "[done] wrote results to %s (tested=%d, submittable=%d)",
        path,
        len(results),
        summary["submittable"],
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
