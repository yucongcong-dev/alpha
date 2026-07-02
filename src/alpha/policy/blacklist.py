"""模板黑名单兼容导出层。"""

from __future__ import annotations

from .blacklist_runtime import (
    auto_update_blacklist,
    auto_update_blacklist_incremental,
    build_blacklist_runtime_stats,
)
from .blacklist_store import (
    _BLACKLIST_PATH_CACHE,
    ensure_template_blacklist_file,
    load_blacklisted_template_names,
)

__all__ = [
    "_BLACKLIST_PATH_CACHE",
    "auto_update_blacklist",
    "auto_update_blacklist_incremental",
    "build_blacklist_runtime_stats",
    "ensure_template_blacklist_file",
    "load_blacklisted_template_names",
]

