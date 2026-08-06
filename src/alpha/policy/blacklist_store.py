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

from ..config.constants import BLACKLIST_SCHEMA_VERSION, DATE_FORMAT_ISO
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

_BLACKLIST_PATH_CACHE: dict[str, str] = {}


def _resolve_datasets_root(datasets_root: str = "") -> str:
    """Resolve the canonical datasets root from an explicit root or active context."""
    if not datasets_root:
        return str(get_active_datasets_root())
    return str(Path(datasets_root).expanduser().resolve())


def resolve_blacklist_path(dataset_id: str, *, datasets_root: str = "") -> str:
    """按数据集解析统一黑名单路径。"""
    cache_key = f"{dataset_id}|{datasets_root}" if datasets_root else dataset_id
    if cache_key in _BLACKLIST_PATH_CACHE:
        return _BLACKLIST_PATH_CACHE[cache_key]
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    resolved_path = Path(_resolve_datasets_root(datasets_root)) / dataset_key / "blacklist.json"
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
    cache_key = f"{dataset_id}|{datasets_root}" if datasets_root else dataset_id
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
        payload = build_default_blacklist(dataset_id)
    normalized = dict(payload)
    normalized.setdefault("_version", BLACKLIST_SCHEMA_VERSION)
    normalized.setdefault("dataset_id", dataset_id)
    normalized.setdefault("_created", time.strftime(DATE_FORMAT_ISO))
    normalized.setdefault("_updated", time.strftime(DATE_FORMAT_ISO))
    normalized.setdefault("_comment", build_default_blacklist(dataset_id)["_comment"])

    learned_templates = normalized.get(LEARNED_BLACKLIST_KEY)
    if not isinstance(learned_templates, list):
        legacy_entries = normalized.get("blacklisted_templates", [])
        learned_templates = legacy_entries if isinstance(legacy_entries, list) else []
    expression_rules = normalized.get(PATTERN_RULES_KEY)
    if not isinstance(expression_rules, list):
        legacy_rules = normalized.get("auto_avoid_rules", [])
        expression_rules = legacy_rules if isinstance(legacy_rules, list) else []

    normalized[LEARNED_BLACKLIST_KEY] = learned_templates
    normalized[PATTERN_RULES_KEY] = expression_rules
    normalized.pop("blacklisted_templates", None)
    normalized.pop("auto_avoid_rules", None)
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
