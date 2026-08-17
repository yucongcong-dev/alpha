"""
黑名单文件存取与缓存失效。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import time
from typing import cast

from ..config._constants_strings import (
    BLACKLIST_SCHEMA_VERSION,
    DATE_FORMAT_ISO,
)
from ..io.common import (
    atomic_write_json,
    sanitize_dataset_id_for_filename,
)
from ..io.file_lock import exclusive_file_lock
from .blacklist_context import get_active_datasets_root
from .types import (
    LEARNED_BLACKLIST_KEY,
    PATTERN_RULES_KEY,
    BlacklistPayload,
)

logger = logging.getLogger(__name__)

_BLACKLIST_PATH_CACHE: dict[tuple[str, str], str] = {}


def _resolve_datasets_root(datasets_root: str = "") -> str:
    """Resolve the canonical datasets root from an explicit root or active context."""
    if not datasets_root:
        return str(get_active_datasets_root())
    return str(Path(datasets_root).expanduser().resolve())


def _blacklist_cache_key(dataset_id: str, datasets_root: str = "") -> tuple[str, str]:
    """Bind cached paths to both the dataset and its resolved workspace root."""
    return dataset_id, _resolve_datasets_root(datasets_root)


def resolve_blacklist_path(dataset_id: str, *, datasets_root: str = "") -> str:
    """按数据集解析统一黑名单路径。"""
    cache_key = _blacklist_cache_key(dataset_id, datasets_root)
    if cache_key in _BLACKLIST_PATH_CACHE:
        return _BLACKLIST_PATH_CACHE[cache_key]
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    resolved_path = Path(cache_key[1]) / dataset_key / "blacklist.json"
    resolved = str(resolved_path)
    _BLACKLIST_PATH_CACHE[cache_key] = resolved
    return resolved


@contextmanager
def exclusive_blacklist_transaction(
    dataset_id: str,
    *,
    datasets_root: str = "",
) -> Iterator[None]:
    """Serialize all blacklist read-merge-write operations for one dataset."""
    blacklist_path = Path(resolve_blacklist_path(dataset_id, datasets_root=datasets_root))
    lock_path = blacklist_path.parent / ".blacklist.transaction.lock"
    with exclusive_file_lock(str(lock_path)):
        yield


def invalidate_blacklist_path_cache(dataset_id: str = "", *, datasets_root: str = "") -> None:
    """Invalidate cached blacklist path lookups."""
    if not dataset_id:
        _BLACKLIST_PATH_CACHE.clear()
        return
    if datasets_root:
        _BLACKLIST_PATH_CACHE.pop(_blacklist_cache_key(dataset_id, datasets_root), None)
        return
    for cache_key in [key for key in _BLACKLIST_PATH_CACHE if key[0] == dataset_id]:
        _BLACKLIST_PATH_CACHE.pop(cache_key, None)


def build_default_blacklist(dataset_id: str) -> BlacklistPayload:
    return {
        "_version": BLACKLIST_SCHEMA_VERSION,
        "_comment": (
            f"Template blacklist for {dataset_id}. "
            "learned_templates stores dataset-specific learned exclusions; "
            "expression_rules stores explicit expression pattern blocks."
        ),
        "_created": time.strftime(DATE_FORMAT_ISO),
        "_updated": time.strftime(DATE_FORMAT_ISO),
        "dataset_id": dataset_id,
        LEARNED_BLACKLIST_KEY: [],
        PATTERN_RULES_KEY: [],
    }


def normalize_blacklist_payload(
    payload: object,
    dataset_id: str,
) -> BlacklistPayload:
    """Normalize blacklist payload to the canonical top-level schema."""
    if not isinstance(payload, dict):
        return build_default_blacklist(dataset_id)
    defaults = build_default_blacklist(dataset_id)
    learned_templates = payload.get(LEARNED_BLACKLIST_KEY)
    expression_rules = payload.get(PATTERN_RULES_KEY)
    normalized = {
        "_version": payload.get("_version", defaults["_version"]),
        "_comment": payload.get("_comment", defaults["_comment"]),
        "_created": payload.get("_created", defaults["_created"]),
        "_updated": payload.get("_updated", defaults["_updated"]),
        "dataset_id": payload.get("dataset_id", dataset_id),
        LEARNED_BLACKLIST_KEY: learned_templates if isinstance(learned_templates, list) else [],
        PATTERN_RULES_KEY: expression_rules if isinstance(expression_rules, list) else [],
    }
    return cast(BlacklistPayload, normalized)


def read_blacklist_payload(dataset_id: str, *, datasets_root: str = "") -> BlacklistPayload:
    blacklist_path = resolve_blacklist_path(dataset_id, datasets_root=datasets_root)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, encoding="utf-8") as fh:
                payload = json.load(fh)
        else:
            payload = build_default_blacklist(dataset_id)
    except (json.JSONDecodeError, OSError):
        logger.warning("[blacklist] failed to read %s; using empty default payload", blacklist_path)
        payload = build_default_blacklist(dataset_id)
    normalized = normalize_blacklist_payload(payload, dataset_id)
    if not isinstance(payload, dict):
        logger.warning("[blacklist] invalid payload shape in %s; expected object", blacklist_path)
    return normalized


def write_blacklist_payload(
    dataset_id: str,
    payload: BlacklistPayload,
    *,
    datasets_root: str = "",
) -> str:
    blacklist_path = resolve_blacklist_path(dataset_id, datasets_root=datasets_root)
    atomic_write_json(blacklist_path, normalize_blacklist_payload(payload, dataset_id))
    return blacklist_path


def summarize_blacklist_payload(payload: BlacklistPayload) -> tuple[int, int]:
    """Return learned-entry count and rule count for startup diagnostics."""
    learned = payload.get(LEARNED_BLACKLIST_KEY, [])
    rules = payload.get(PATTERN_RULES_KEY, [])
    learned_count = len(learned) if isinstance(learned, list) else 0
    rule_count = len(rules) if isinstance(rules, list) else 0
    return learned_count, rule_count


def ensure_template_blacklist_file(dataset_id: str, *, datasets_root: str = "") -> str:
    blacklist_path = resolve_blacklist_path(dataset_id, datasets_root=datasets_root)
    with exclusive_blacklist_transaction(dataset_id, datasets_root=datasets_root):
        if os.path.isfile(blacklist_path):
            return blacklist_path
        write_blacklist_payload(
            dataset_id, build_default_blacklist(dataset_id), datasets_root=datasets_root
        )
    logger.info("[blacklist] created dataset blacklist file: %s", blacklist_path)
    return blacklist_path
