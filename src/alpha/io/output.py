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

import json
import logging
import os
import re
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..config import DEFAULT_DATASET_ID
from ..models.base import FieldTestResult

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

logger = logging.getLogger(__name__)

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
                logger.info("[cleanup] removed legacy sidecar file %s", legacy_path)
        except FileNotFoundError:
            continue


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
    logger.info("[done] wrote results to %s", path)
    logger.info("[done] wrote analysis to %s", sidecar_paths['analysis'])


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

    should_rebuild = not os.path.exists(sidecar_paths["analysis"])
    if not should_rebuild:
        try:
            with open(sidecar_paths["analysis"], encoding="utf-8") as handle:
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
    logger.info("[analysis] rebuilt analysis from main results: %s", sidecar_paths['analysis'])
