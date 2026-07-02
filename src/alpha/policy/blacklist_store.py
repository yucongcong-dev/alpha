"""
黑名单文件存取与缓存失效。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from ..io.common import atomic_write_json, resolve_runtime_data_dir, sanitize_dataset_id_for_filename

logger = logging.getLogger(__name__)

_BLACKLIST_PATH_CACHE: dict[str, str] = {}


def resolve_blacklist_path(dataset_id: str, *, data_dir: str = "") -> str:
    """按数据集解析统一黑名单路径。"""
    cache_key = f"{dataset_id}|{data_dir}" if data_dir else dataset_id
    if cache_key in _BLACKLIST_PATH_CACHE:
        return _BLACKLIST_PATH_CACHE[cache_key]
    base = resolve_runtime_data_dir(data_dir)
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    resolved = str(base / "blacklists" / dataset_key / "blacklist.json")
    _BLACKLIST_PATH_CACHE[cache_key] = resolved
    return resolved


def build_default_blacklist(dataset_id: str) -> dict[str, Any]:
    return {
        "_version": "v2",
        "_comment": f"Template blacklist for {dataset_id} — auto-populated from test results.",
        "_created": time.strftime("%Y-%m-%d"),
        "_updated": time.strftime("%Y-%m-%d"),
        "dataset_id": dataset_id,
        "blacklisted_templates": [],
        "auto_avoid_rules": [],
    }


def read_blacklist_payload(dataset_id: str, *, data_dir: str = "") -> dict[str, Any]:
    blacklist_path = resolve_blacklist_path(dataset_id, data_dir=data_dir)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        else:
            payload = build_default_blacklist(dataset_id)
    except (json.JSONDecodeError, OSError):
        payload = build_default_blacklist(dataset_id)
    if not isinstance(payload, dict):
        payload = build_default_blacklist(dataset_id)
    payload.setdefault("dataset_id", dataset_id)
    payload.setdefault("blacklisted_templates", [])
    payload.setdefault("auto_avoid_rules", [])
    return payload


def write_blacklist_payload(dataset_id: str, payload: dict[str, Any], *, data_dir: str = "") -> str:
    blacklist_path = resolve_blacklist_path(dataset_id, data_dir=data_dir)
    atomic_write_json(blacklist_path, payload)
    return blacklist_path


def invalidate_blacklist_runtime_cache(dataset_id: str) -> None:
    from ..generators.expressions import invalidate_blacklist_cache

    invalidate_blacklist_cache(dataset_id)


def load_blacklisted_template_names(dataset_id: str, *, data_dir: str = "") -> set[str]:
    payload = read_blacklist_payload(dataset_id, data_dir=data_dir)
    entries = payload.get("blacklisted_templates", [])
    if not isinstance(entries, list):
        return set()
    return {
        str(item.get("name"))
        for item in entries
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }


def ensure_template_blacklist_file(dataset_id: str, *, data_dir: str = "") -> str:
    blacklist_path = resolve_blacklist_path(dataset_id, data_dir=data_dir)
    if os.path.isfile(blacklist_path):
        return blacklist_path
    write_blacklist_payload(dataset_id, build_default_blacklist(dataset_id), data_dir=data_dir)
    logger.info("[blacklist] created dataset blacklist file: %s", blacklist_path)
    return blacklist_path
