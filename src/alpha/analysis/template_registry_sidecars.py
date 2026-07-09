"""Template-registry sidecar persistence helpers."""

from __future__ import annotations

import os
from typing import Any

from ..io.common import atomic_write_json
from ..io.output_paths import build_output_sidecar_paths
from .template_registry_rules import compile_template_registry_summary
from .template_registry_store import load_registry_overrides


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


def ensure_template_registry_overrides_sidecar(output_path: str) -> None:
    """Ensure the manual override sidecar exists with normalized payload."""
    sidecar_paths = build_output_sidecar_paths(output_path)
    override_path = sidecar_paths["template_registry_overrides"]
    if os.path.exists(override_path):
        return
    atomic_write_json(override_path, load_registry_overrides(output_path))


def sync_template_registry_sidecars(
    output_path: str,
    *,
    summary_rows: list[dict[str, Any]] | None = None,
    template_stats: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Persist summary sidecar and ensure overrides sidecar exists."""
    persist_template_registry_summary(
        output_path,
        summary_rows=summary_rows,
        template_stats=template_stats,
    )
    ensure_template_registry_overrides_sidecar(output_path)


__all__ = [
    "ensure_template_registry_overrides_sidecar",
    "persist_template_registry_summary",
    "sync_template_registry_sidecars",
]
