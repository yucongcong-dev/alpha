"""Stable fingerprint helpers for settings, templates, and result identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..config.constants import STABLE_FINGERPRINT_HEX_LEN


def stable_fingerprint(payload: Any) -> str:
    """
    为配置、模板或结果标识生成稳定的短哈希。

    Generate a stable short hash for config, template, or result identity.
    """
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:STABLE_FINGERPRINT_HEX_LEN]
