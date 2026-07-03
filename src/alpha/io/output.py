"""
结果输出兼容导出层。

.. deprecated:: 1.0.0
    This module is a compatibility facade. Import from specific modules instead:
    ``alpha.io.results_store``, ``alpha.io.output_paths``, ``alpha.io.analysis_sync``,
    ``alpha.io.common``, ``alpha.policy.blacklist``.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "alpha.io.output is deprecated. Import from specific modules instead: "
    "alpha.io.results_store, alpha.io.output_paths, alpha.io.analysis_sync, "
    "alpha.io.common, alpha.policy.blacklist.",
    DeprecationWarning,
    stacklevel=2,
)

from ..io.common import CACHE_DIR, DATA_DIR, PROJECT_ROOT, RESULTS_DIR, SCRIPT_DIR
from ..policy.blacklist import (
    auto_update_blacklist,
    auto_update_blacklist_incremental,
    build_blacklist_runtime_stats,
    ensure_template_blacklist_file,
    invalidate_blacklist_path_cache,
    load_blacklisted_template_names,
)
from .analysis_sync import ensure_analysis_synced as _ensure_analysis_synced
from .output_paths import (
    build_dataset_scoped_paths,
    build_output_sidecar_paths,
    cleanup_legacy_sidecar_files,
    resolve_cli_path,
)
from .results_store import (
    dump_results as _dump_results,
)
from .results_store import (
    dump_results_incremental,
    initialize_results_journal,
)
from .results_store import (
    load_results_rows_from_journal as _load_results_rows_from_journal,
)


def dump_results(*args, **kwargs):
    """兼容包装：保留对 alpha.io.output.auto_update_blacklist monkeypatch 的可见性。"""
    kwargs.setdefault("auto_update_blacklist_fn", auto_update_blacklist)
    return _dump_results(*args, **kwargs)


def ensure_analysis_synced(output_path: str) -> None:
    """兼容包装：重建分析时复用当前模块导出的 dump_results。"""
    _ensure_analysis_synced(output_path, dump_results_fn=dump_results)


__all__ = [
    "CACHE_DIR",
    "DATA_DIR",
    "PROJECT_ROOT",
    "RESULTS_DIR",
    "SCRIPT_DIR",
    "_load_results_rows_from_journal",
    "auto_update_blacklist",
    "auto_update_blacklist_incremental",
    "build_blacklist_runtime_stats",
    "build_dataset_scoped_paths",
    "build_output_sidecar_paths",
    "cleanup_legacy_sidecar_files",
    "dump_results",
    "dump_results_incremental",
    "ensure_analysis_synced",
    "ensure_template_blacklist_file",
    "initialize_results_journal",
    "invalidate_blacklist_path_cache",
    "load_blacklisted_template_names",
    "resolve_cli_path",
]
