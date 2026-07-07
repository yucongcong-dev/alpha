"""
黑名单文件存取与缓存失效。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import cast

from ..config.constants import BLACKLIST_SCHEMA_VERSION, DATE_FORMAT_ISO
from ..io.common import (
    atomic_write_json,
    resolve_blacklists_dir,
    sanitize_dataset_id_for_filename,
)
from .template_blacklist import invalidate_blacklist_cache
from .types import BlacklistPayload, LEARNED_BLACKLIST_KEY, PATTERN_RULES_KEY

logger = logging.getLogger(__name__)

_BLACKLIST_PATH_CACHE: dict[str, str] = {}


def _resolve_blacklist_root(data_dir: str = "") -> str:
    """Resolve the canonical blacklist root from an optional runtime root override."""
    if not data_dir:
        return str(resolve_blacklists_dir())
    candidate = os.path.abspath(data_dir)
    if os.path.basename(candidate.rstrip(os.sep)) == "blacklists":
        return candidate
    return os.path.join(candidate, "blacklists")


def resolve_blacklist_path(dataset_id: str, *, data_dir: str = "") -> str:
    """按数据集解析统一黑名单路径。"""
    cache_key = f"{dataset_id}|{data_dir}" if data_dir else dataset_id
    if cache_key in _BLACKLIST_PATH_CACHE:
        return _BLACKLIST_PATH_CACHE[cache_key]
    base = _resolve_blacklist_root(data_dir)
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    resolved = os.path.join(base, dataset_key, "blacklist.json")
    _BLACKLIST_PATH_CACHE[cache_key] = resolved
    return resolved


def invalidate_blacklist_path_cache(dataset_id: str = "", *, data_dir: str = "") -> None:
    """Invalidate cached blacklist path lookups."""
    if not dataset_id:
        _BLACKLIST_PATH_CACHE.clear()
        return
    cache_key = f"{dataset_id}|{data_dir}" if data_dir else dataset_id
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


def read_blacklist_payload(dataset_id: str, *, data_dir: str = "") -> BlacklistPayload:
    blacklist_path = resolve_blacklist_path(dataset_id, data_dir=data_dir)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, encoding="utf-8") as fh:
                payload = json.load(fh)
        else:
            payload = build_default_blacklist(dataset_id)
    except (json.JSONDecodeError, OSError):
        payload = build_default_blacklist(dataset_id)
    return normalize_blacklist_payload(payload, dataset_id)


def write_blacklist_payload(
    dataset_id: str,
    payload: BlacklistPayload,
    *,
    data_dir: str = "",
) -> str:
    blacklist_path = resolve_blacklist_path(dataset_id, data_dir=data_dir)
    atomic_write_json(blacklist_path, normalize_blacklist_payload(payload, dataset_id))
    return blacklist_path


def invalidate_blacklist_runtime_cache(dataset_id: str) -> None:

    invalidate_blacklist_cache(dataset_id)


def load_blacklisted_template_names(dataset_id: str, *, data_dir: str = "") -> set[str]:
    payload = read_blacklist_payload(dataset_id, data_dir=data_dir)
    entries = payload.get(LEARNED_BLACKLIST_KEY, [])
    if not isinstance(entries, list):
        return set()
    return {
        str(item.get("name"))
        for item in entries
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }


def summarize_blacklist_payload(payload: BlacklistPayload) -> tuple[int, int]:
    """Return learned-entry count and rule count for startup diagnostics."""
    learned = payload.get(LEARNED_BLACKLIST_KEY, [])
    rules = payload.get(PATTERN_RULES_KEY, [])
    learned_count = len(learned) if isinstance(learned, list) else 0
    rule_count = len(rules) if isinstance(rules, list) else 0
    return learned_count, rule_count


def ensure_template_blacklist_file(dataset_id: str, *, data_dir: str = "") -> str:
    blacklist_path = resolve_blacklist_path(dataset_id, data_dir=data_dir)
    if os.path.isfile(blacklist_path):
        return blacklist_path
    write_blacklist_payload(dataset_id, build_default_blacklist(dataset_id), data_dir=data_dir)
    logger.info("[blacklist] created dataset blacklist file: %s", blacklist_path)
    return blacklist_path
