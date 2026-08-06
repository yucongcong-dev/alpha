"""High-level result views and persistence orchestration."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from ..io.common import atomic_write_json
from ..io.output_paths import build_output_sidecar_paths, cleanup_legacy_sidecar_files
from ..io.results_store import (
    _append_results_journal,
    exclusive_results_transaction,
    initialize_results_journal,
)
from ..models.domain import FieldTestResult
from .report_builder import build_analysis_payload, build_results_summary_payload
from .template_registry_sidecars import (
    persist_template_registry_summary,
    sync_template_registry_sidecars,
)
from .template_stats import compile_template_stats

logger = logging.getLogger(__name__)


def _portable_journal_reference(output_path: str, journal_path: str) -> str:
    """Store sidecar references relative to their owning summary directory."""
    return os.path.relpath(journal_path, start=Path(output_path).parent)


def dump_results(
    path: str,
    dataset_id: str,
    results: list[FieldTestResult],
    *,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict[str, Any] | None = None,
    include_analysis: bool = True,
) -> None:
    """Persist the authoritative journal and its derived result views."""
    sidecar_paths = build_output_sidecar_paths(path)
    summary, analysis_inputs = build_results_summary_payload(
        dataset_id,
        results,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
        results_journal_path=_portable_journal_reference(path, sidecar_paths["results_journal"]),
    )
    summary["results_embedded"] = False
    summary.pop("results", None)
    template_stats = compile_template_stats(results)
    initialize_results_journal(path, results)
    atomic_write_json(path, summary)
    sync_template_registry_sidecars(path, template_stats=template_stats)
    if include_analysis:
        analysis = build_analysis_payload(results, summary, analysis_inputs)
        atomic_write_json(sidecar_paths["analysis"], analysis)
    cleanup_legacy_sidecar_files(path)
    logger.info(
        "[done] wrote results to %s (tested=%d, submittable=%d)",
        path,
        len(results),
        summary["submittable"],
    )
    if include_analysis:
        logger.debug("[done] wrote analysis to %s", sidecar_paths["analysis"])


def dump_results_incremental(
    path: str,
    dataset_id: str,
    new_results: list[FieldTestResult],
    *,
    persisted_result_count: int,
    tested: int,
    unique_fields_tested: int,
    submittable_count: int,
    error_count: int,
    queue_timeout_count: int,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict[str, Any] | None = None,
    template_registry_summary: list[dict[str, Any]] | None = None,
    template_stats: dict[str, dict[str, Any]] | None = None,
    pending_check_count: int = 0,
) -> int:
    """Append new journal rows and persist lightweight derived views."""
    sidecar_paths = build_output_sidecar_paths(path)
    output_directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(output_directory, exist_ok=True)
    with exclusive_results_transaction(path):
        next_persisted_result_count = persisted_result_count
        if new_results:
            next_persisted_result_count = _append_results_journal(
                sidecar_paths["results_journal"],
                new_results,
                expected_row_count=persisted_result_count,
            )
        summary = {
            "dataset_id": dataset_id,
            "run_config": run_config or {},
            "settings_fingerprint": settings_fingerprint,
            "template_library_fingerprint": template_library_fingerprint,
            "tested": tested,
            "unique_fields_tested": unique_fields_tested,
            "submittable": submittable_count,
            "errors": error_count,
            "queue_timeouts": queue_timeout_count,
            "pending_checks": pending_check_count,
            "results_embedded": False,
            "results_journal": _portable_journal_reference(path, sidecar_paths["results_journal"]),
        }
        atomic_write_json(path, summary)
        if template_registry_summary is not None or template_stats is not None:
            persist_template_registry_summary(
                path,
                summary_rows=template_registry_summary,
                template_stats=template_stats,
            )
        cleanup_legacy_sidecar_files(path)
    logger.info(
        "[done] wrote incremental results to %s (tested=%d, submittable=%d, appended=%d)",
        path,
        tested,
        submittable_count,
        len(new_results),
    )
    return next_persisted_result_count
