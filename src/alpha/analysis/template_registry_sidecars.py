"""Template-registry sidecar persistence helpers."""

from __future__ import annotations

from typing import Any

from ..io.common import atomic_write_json
from ..io.output_paths import build_output_sidecar_paths
from .template_registry_rules import compile_template_registry_summary


def persist_template_registry_summary(
    output_path: str,
    *,
    summary_rows: list[dict[str, Any]] | None = None,
    template_stats: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Persist template-registry summary sidecar from rows or stats."""
    if summary_rows is None:
        summary_rows = compile_template_registry_summary(template_stats or {})
    sidecar_paths = build_output_sidecar_paths(output_path)
    atomic_write_json(sidecar_paths["template_registry"], summary_rows)


def sync_template_registry_sidecars(
    output_path: str,
    *,
    summary_rows: list[dict[str, Any]] | None = None,
    template_stats: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Persist the report-only template registry summary sidecar."""
    persist_template_registry_summary(
        output_path,
        summary_rows=summary_rows,
        template_stats=template_stats,
    )


__all__ = [
    "persist_template_registry_summary",
    "sync_template_registry_sidecars",
]
