"""
输入输出包

负责凭证管理和结果持久化输出。

子模块：
    - credentials: 凭证管理
    - credentials_crypto: 凭证加密
    - common: IO 基础公共工具
    - output_paths: 输出路径解析
    - results_store: 结果持久化与 journal 写入
"""

from __future__ import annotations

from .common import CACHE_DIR, DATA_DIR, PROJECT_ROOT, RESULTS_DIR, SCRIPT_DIR
from .output_paths import (
    build_dataset_scoped_paths,
    build_output_sidecar_paths,
    cleanup_legacy_sidecar_files,
    resolve_cli_path,
)
from .results_store import (
    dump_results,
    dump_results_incremental,
    initialize_results_journal,
    load_results_rows_from_journal,
)

__all__ = [
    "CACHE_DIR",
    "DATA_DIR",
    "PROJECT_ROOT",
    "RESULTS_DIR",
    "SCRIPT_DIR",
    "build_dataset_scoped_paths",
    "build_output_sidecar_paths",
    "cleanup_legacy_sidecar_files",
    "dump_results",
    "dump_results_incremental",
    "initialize_results_journal",
    "load_results_rows_from_journal",
    "resolve_cli_path",
]
