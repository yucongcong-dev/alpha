"""Stable fingerprint helpers for settings, templates, and result identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..config.constants import STABLE_FINGERPRINT_HEX_LEN


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses
        return dataclasses.asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def stable_fingerprint(payload: Any) -> str:
    """
    为配置、模板或结果标识生成稳定的短哈希。

    Generate a stable short hash for config, template, or result identity.
    """
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:STABLE_FINGERPRINT_HEX_LEN]
