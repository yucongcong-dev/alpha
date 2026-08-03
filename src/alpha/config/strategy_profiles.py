"""Named strategy profile boundaries."""

from __future__ import annotations

STRATEGY_PROFILE_EXPLORE = "explore"
STRATEGY_PROFILE_REFINE = "refine"
STRATEGY_PROFILE_SUBMIT_FOCUSED = "submit-focused"
DEFAULT_STRATEGY_PROFILE = STRATEGY_PROFILE_EXPLORE

STRATEGY_PROFILE_CHOICES = (
    STRATEGY_PROFILE_EXPLORE,
    STRATEGY_PROFILE_REFINE,
    STRATEGY_PROFILE_SUBMIT_FOCUSED,
)


def normalize_strategy_profile(value: object) -> str:
    """Return a supported strategy profile name."""
    profile = str(value or DEFAULT_STRATEGY_PROFILE).strip().lower()
    if profile not in STRATEGY_PROFILE_CHOICES:
        allowed = ", ".join(STRATEGY_PROFILE_CHOICES)
        raise ValueError(f"unsupported strategy_profile: {profile!r}; expected one of {allowed}")
    return profile
