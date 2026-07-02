"""CLI 过滤器与日志工具

从 parser 模块提取出的独立过滤器加载和日志设置函数。
"""

from __future__ import annotations

import logging
import os

from ..models.io_types import RunFilters, RunPaths

logger = logging.getLogger(__name__)


def load_line_set(path: str) -> set[str]:
    """从文本文件加载非空行作为集合。

    用于加载包含字段 ID 或模板名称的过滤器文件。

    Args:
        path: 文本文件路径。

    Returns:
        非空行的集合。文件不存在或为空时返回空集合。
    """
    if not path or not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as handle:
            return {line.strip() for line in handle if line.strip()}
    except Exception:
        return set()


def load_run_filters(run_paths: RunPaths) -> RunFilters:
    """加载运行过滤器，包括字段和模板的包含/排除列表。

    Args:
        run_paths: 运行路径对象。

    Returns:
        包含过滤规则的 RunFilters 对象。
    """
    exclude_fields = load_line_set(
        run_paths.exclude_fields_file if hasattr(run_paths, "exclude_fields_file") else ""
    )
    return RunFilters(
        region_filter=None,
        delay_filter=None,
        min_sharpe=None,
        max_turnover=None,
        exclude_fields=exclude_fields,
    )


def load_run_filters_extended(run_paths: RunPaths) -> RunFilters:
    """加载扩展的运行过滤器（含 include 列表）。

    Args:
        run_paths: 运行路径对象。

    Returns:
        包含完整过滤规则的 RunFilters 对象。
    """
    return RunFilters(
        region_filter=None,
        delay_filter=None,
        min_sharpe=None,
        max_turnover=None,
        include_fields=load_line_set(
            run_paths.include_fields_file if hasattr(run_paths, "include_fields_file") else ""
        ),
        exclude_fields=load_line_set(
            run_paths.exclude_fields_file if hasattr(run_paths, "exclude_fields_file") else ""
        ),
        include_templates=load_line_set(
            run_paths.include_templates_file
            if hasattr(run_paths, "include_templates_file")
            else "",
        ),
        exclude_templates=load_line_set(
            run_paths.exclude_templates_file
            if hasattr(run_paths, "exclude_templates_file")
            else "",
        ),
    )


def setup_runtime_logging(log_path: str) -> None:
    """设置运行时日志，同时输出到控制台（coloredlogs）和文件。

    Args:
        log_path: 日志文件绝对路径。为空则仅输出到控制台。
    """
    import coloredlogs

    root = logging.getLogger()

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    coloredlogs.install(
        level="INFO",
        fmt="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    if log_path:
        log_dir = os.path.dirname(os.path.abspath(log_path))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        plain_fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%H:%M:%S"
        )
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(plain_fmt)
        root.addHandler(file_handler)

    root.info(f"logging to {log_path}" if log_path else "logging to console only")
