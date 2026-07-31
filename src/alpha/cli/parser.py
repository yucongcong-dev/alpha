"""CLI parsing boundary and legacy exports for moved helpers."""

from __future__ import annotations

import argparse
import sys

from ..config.application import ApplicationConfig
from ..models.io_types import RunPaths
from .arg_resolution import resolve_cli_args

# 过滤器/日志函数已提取到 cli.filters，此处保留重导出以兼容
from .filters import (  # noqa: F401
    load_line_set,
    load_run_filters,
    load_run_filters_extended,
    setup_runtime_logging,
)
from .parser_schema import (
    build_parser,
    collect_explicit_cli_keys,
    collect_parser_defaults,
)
from .path_resolution import normalize_args_paths as _normalize_args_paths
from .run_config import build_run_config_snapshot  # noqa: F401

# ============================================================================
# 命令行参数解析函数
# ============================================================================


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments and apply YAML/profile/run-mode overrides."""
    parser = build_parser()

    parser_defaults = collect_parser_defaults(parser)
    explicit_cli_keys = collect_explicit_cli_keys(parser, sys.argv[1:])
    args = parser.parse_args()
    return resolve_cli_args(
        args,
        parser_defaults=parser_defaults,
        explicit_cli_keys=explicit_cli_keys,
    )


def parse_application_config() -> ApplicationConfig:
    """Parse CLI input and cross the boundary into immutable runtime config."""
    args = parse_args()
    run_paths = _normalize_args_paths(args)
    return ApplicationConfig.from_args(args, run_paths)


# ============================================================================
# 路径标准化函数
# ============================================================================


def normalize_args_paths(args: argparse.Namespace) -> RunPaths:
    """兼容导出：归一化运行路径，但不修改 args。"""
    return _normalize_args_paths(args)


# 运行配置快照函数已提取到 cli/run_config.py
# 通过顶部的 from .run_config import build_run_config_snapshot 提供重导出兼容

# 过滤器函数和日志设置已提取到 cli/filters.py
# 通过顶部的 from .filters import ... 提供重导出兼容
