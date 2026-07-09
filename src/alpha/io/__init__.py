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

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .common import (
        BLACKLISTS_DIR,
        CACHE_DIR,
        DATA_DIR,
        PROJECT_ROOT,
        RESULTS_DIR,
        SCRIPT_DIR,
        TEMPLATES_DIR,
    )
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

_EXPORT_MAP: ExportMap = {
    "BLACKLISTS_DIR": (".common", "BLACKLISTS_DIR"),
    "CACHE_DIR": (".common", "CACHE_DIR"),
    "DATA_DIR": (".common", "DATA_DIR"),
    "PROJECT_ROOT": (".common", "PROJECT_ROOT"),
    "RESULTS_DIR": (".common", "RESULTS_DIR"),
    "SCRIPT_DIR": (".common", "SCRIPT_DIR"),
    "TEMPLATES_DIR": (".common", "TEMPLATES_DIR"),
    "build_dataset_scoped_paths": (".output_paths", "build_dataset_scoped_paths"),
    "build_output_sidecar_paths": (".output_paths", "build_output_sidecar_paths"),
    "cleanup_legacy_sidecar_files": (".output_paths", "cleanup_legacy_sidecar_files"),
    "resolve_cli_path": (".output_paths", "resolve_cli_path"),
    "dump_results": (".results_store", "dump_results"),
    "dump_results_incremental": (".results_store", "dump_results_incremental"),
    "initialize_results_journal": (".results_store", "initialize_results_journal"),
    "load_results_rows_from_journal": (".results_store", "load_results_rows_from_journal"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str) -> object:
    return resolve_export(
        name=name,
        export_map=_EXPORT_MAP,
        package=__package__ or "",
        namespace=__name__,
        target_globals=globals(),
    )


def __dir__() -> list[str]:
    return facade_dir(globals(), _EXPORT_MAP)
