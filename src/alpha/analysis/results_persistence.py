"""High-level result views and persistence orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import logging
import os
from pathlib import Path
from typing import Any

from ..io.common import atomic_write_json
from ..io.output_paths import (
    build_output_sidecar_paths,
    cleanup_legacy_sidecar_files,
    is_feedback_output_path,
)
from ..io.results_store import (
    _append_results_journal,
    ensure_results_journal,
    exclusive_results_transaction,
    initialize_results_journal,
)
from ..models.domain import FieldTestResult
from .report_builder import build_analysis_payload, build_results_summary_payload
from .template_registry_rules import compile_template_registry_summary
from .template_registry_sidecars import (
    persist_template_registry_summary,
    sync_template_registry_sidecars,
)
from .template_stats import compile_template_stats

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ResultPersistenceContext:
    """Identity and destination shared by every write of one result view."""

    output_path: str
    dataset_id: str
    settings_fingerprint: str
    template_library_fingerprint: str
    run_fingerprint: str = ""
    run_config: dict[str, Any] = field(default_factory=dict)
    metadata_scope: str | None = None

    def for_output(
        self,
        output_path: str,
        *,
        metadata_scope: str | None = None,
    ) -> ResultPersistenceContext:
        """Reuse run identity while targeting another persisted view."""

        return replace(
            self,
            output_path=output_path,
            metadata_scope=metadata_scope,
        )

    @property
    def resolved_metadata_scope(self) -> str:
        return self.metadata_scope or (
            "feedback" if is_feedback_output_path(self.output_path) else "run"
        )


@dataclass(frozen=True, slots=True)
class IncrementalResultSnapshot:
    """Counters that must be written atomically with one journal append."""

    persisted_result_count: int
    tested: int
    unique_fields_tested: int
    submittable_count: int
    error_count: int
    queue_timeout_count: int
    pending_check_count: int = 0


def _portable_journal_reference(output_path: str, journal_path: str) -> str:
    """Store sidecar references relative to their owning summary directory."""
    return os.path.relpath(journal_path, start=Path(output_path).parent)


def persist_results(
    context: ResultPersistenceContext,
    results: list[FieldTestResult],
    *,
    include_analysis: bool = True,
    rebuild_journal: bool = True,
    include_embedded_results: bool = False,
) -> None:
    """Persist the authoritative journal and its derived result views."""
    path = context.output_path
    sidecar_paths = build_output_sidecar_paths(path)
    summary, analysis_inputs = build_results_summary_payload(
        context.dataset_id,
        results,
        settings_fingerprint=context.settings_fingerprint,
        template_library_fingerprint=context.template_library_fingerprint,
        run_fingerprint=context.run_fingerprint,
        run_config=context.run_config,
        results_journal_path=_portable_journal_reference(path, sidecar_paths["results_journal"]),
        include_embedded_results=include_embedded_results,
    )
    summary["results_embedded"] = include_embedded_results
    summary["metadata_scope"] = context.resolved_metadata_scope
    template_stats = compile_template_stats(results)
    template_registry_summary = compile_template_registry_summary(template_stats)
    if rebuild_journal:
        initialize_results_journal(path, results)
    else:
        ensure_results_journal(path, results)
    atomic_write_json(path, summary)
    sync_template_registry_sidecars(
        path,
        summary_rows=template_registry_summary,
        template_stats=template_stats,
    )
    if include_analysis:
        analysis = build_analysis_payload(
            results,
            summary,
            analysis_inputs,
            template_stats=template_stats,
            template_registry_summary=template_registry_summary,
        )
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


def persist_results_incremental(
    context: ResultPersistenceContext,
    new_results: list[FieldTestResult],
    *,
    snapshot: IncrementalResultSnapshot,
    template_registry_summary: list[dict[str, Any]] | None = None,
    template_stats: dict[str, dict[str, Any]] | None = None,
) -> int:
    """Append new journal rows and persist lightweight derived views."""
    path = context.output_path
    sidecar_paths = build_output_sidecar_paths(path)
    output_directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(output_directory, exist_ok=True)
    with exclusive_results_transaction(path):
        next_persisted_result_count = snapshot.persisted_result_count
        if new_results:
            next_persisted_result_count = _append_results_journal(
                sidecar_paths["results_journal"],
                new_results,
                expected_row_count=snapshot.persisted_result_count,
            )
        summary = {
            "dataset_id": context.dataset_id,
            "run_config": context.run_config,
            "settings_fingerprint": context.settings_fingerprint,
            "template_library_fingerprint": context.template_library_fingerprint,
            "run_fingerprint": context.run_fingerprint,
            "tested": snapshot.tested,
            "unique_fields_tested": snapshot.unique_fields_tested,
            "submittable": snapshot.submittable_count,
            "errors": snapshot.error_count,
            "queue_timeouts": snapshot.queue_timeout_count,
            "pending_checks": snapshot.pending_check_count,
            "results_embedded": False,
            "metadata_scope": context.resolved_metadata_scope,
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
        snapshot.tested,
        snapshot.submittable_count,
        len(new_results),
    )
    return next_persisted_result_count


__all__ = [
    "IncrementalResultSnapshot",
    "ResultPersistenceContext",
    "persist_results",
    "persist_results_incremental",
]
