"""Field family and preferred-rank helpers for bootstrap selection."""

from __future__ import annotations

import re

from ..config.static_config import get_static_config

_FIELD_ALL_SUFFIX = re.compile(r"_all$")
_FIELD_WINDOW_TOKEN = re.compile(r"_(?:last_)?\d+(?:_days?)?(?=_|$)")
_FIELD_TRAILING_WINDOW = re.compile(r"(?:_last)?_(\d+)(?:_days?)?(?:_|$)")
_PREFERRED_FIELD_WINDOWS = (30, 60, 90, 20, 120, 180, 10, 150, 270, 360, 720, 1080)


def infer_field_family(field_name: str) -> str:
    """Collapse repeated tenor/window variants into a stable semantic family."""
    normalized = field_name.strip().lower()
    family = _FIELD_ALL_SUFFIX.sub("", normalized)
    family = _FIELD_WINDOW_TOKEN.sub("", family)
    return family or normalized


def preferred_field_rank(field_name: str, preferred_order: dict[str, int]) -> int:
    """Resolve exact and semantic aliases in preferred field ordering."""
    normalized = field_name.strip().lower()
    exact = preferred_order.get(normalized)
    if exact is not None:
        return exact
    semantic_matches = [
        rank
        for label, rank in preferred_order.items()
        if str(label).strip().lower() in normalized.split("_")
    ]
    return (
        min(semantic_matches)
        if semantic_matches
        else get_static_config().preferred_field_rank_sentinel
    )


def field_window_rank(field_name: str) -> int:
    """Rank common tenor suffixes so preferred windows sort first."""
    match = _FIELD_TRAILING_WINDOW.search(field_name.strip().lower())
    if match is None:
        return 0
    window = int(match.group(1))
    try:
        return _PREFERRED_FIELD_WINDOWS.index(window) + 1
    except ValueError:
        return len(_PREFERRED_FIELD_WINDOWS) + 1
