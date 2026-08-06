"""Shared TemplateBuildOptions fixtures for focused unit tests."""

from __future__ import annotations

from dataclasses import replace

from alpha.models.runtime_options import TemplateBuildOptions

_DEFAULT_OPTIONS = TemplateBuildOptions(
    region="USA",
    universe="TOP3000",
    instrument_type="EQUITY",
    delay=1,
    decay=4,
    neutralization="SUBINDUSTRY",
    truncation=0.08,
    pasteurization="ON",
    unit_handling="VERIFY",
    nan_handling="OFF",
    language="FASTEXPR",
)


def template_build_options(**overrides: object) -> TemplateBuildOptions:
    """Return canonical template options with test-specific overrides."""
    return replace(_DEFAULT_OPTIONS, **overrides)
