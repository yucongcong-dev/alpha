"""Persist startup reconciliation for unresolved submission checks."""

from __future__ import annotations

from dataclasses import replace
import logging

from ..analysis.feedback_history import rebuild_historical_run_state
from ..analysis.feedback_run_index import persist_feedback_run_index
from ..analysis.results_persistence import ResultPersistenceContext, persist_results
from ..api.client import BrainClient
from ..core.pending_check_refresh import (
    DEFAULT_PENDING_CHECK_REFRESH_LIMIT,
    DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS,
    PendingCheckRefreshOptions,
    PendingCheckService,
    project_submission_check_refresh,
    select_submission_check_refresh_candidates,
)
from ..io.results_store import exclusive_results_transaction
from ..models.domain import FieldTestResult
from ..models.runtime_protocols import ClientFactoryLike, RunConfig
from ..runtime.contexts import HistoricalRunState

logger = logging.getLogger(__name__)


def persist_reconciled_historical_results(
    *,
    output_file: str,
    dataset_id: str,
    results: list[FieldTestResult],
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: RunConfig,
    run_fingerprint: str = "",
    metadata_scope: str = "run",
) -> None:
    """Persist startup reconciliation before later bootstrap stages may return early."""
    with exclusive_results_transaction(output_file):
        persist_results(
            ResultPersistenceContext(
                output_path=output_file,
                dataset_id=dataset_id,
                settings_fingerprint=settings_fingerprint,
                template_library_fingerprint=template_library_fingerprint,
                run_fingerprint=run_fingerprint,
                run_config=run_config,
                metadata_scope=metadata_scope,
            ),
            results,
        )


def reconcile_pending_check_results(
    client: BrainClient | ClientFactoryLike,
    historical_state: HistoricalRunState,
    *,
    retries: int,
    output_file: str,
    feedback_output: str,
    dataset_id: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: RunConfig,
    run_fingerprint: str = "",
    refresh_limit: int | None = None,
    max_refresh_seconds: float | None = None,
    max_workers: int | None = None,
    repeat_until_terminal: bool = False,
) -> HistoricalRunState:
    """Refresh pending checks and persist every historical view that changed."""
    existing_results = historical_state.existing_results
    feedback_results = historical_state.feedback_results
    refresh_input_results = select_submission_check_refresh_candidates(
        feedback_results,
        existing_results,
    )
    refresh_result = PendingCheckService(
        client,
        PendingCheckRefreshOptions(
            retries=retries,
            refresh_limit=(
                DEFAULT_PENDING_CHECK_REFRESH_LIMIT if refresh_limit is None else refresh_limit
            ),
            max_refresh_seconds=(
                DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS
                if max_refresh_seconds is None
                else max_refresh_seconds
            ),
            max_workers=1 if max_workers is None else max_workers,
            repeat_until_terminal=repeat_until_terminal,
        ),
    ).refresh(refresh_input_results)
    refreshed_candidates = refresh_result.results
    refreshed_count = refresh_result.resolved_count
    refreshed_feedback_results = project_submission_check_refresh(
        feedback_results,
        refreshed_candidates,
    )
    refreshed_existing_results = project_submission_check_refresh(
        existing_results,
        refreshed_candidates,
    )
    if (
        refreshed_feedback_results == feedback_results
        and refreshed_existing_results == existing_results
    ):
        return historical_state

    refreshed_state = rebuild_historical_run_state(
        replace(
            historical_state,
            feedback_results=refreshed_feedback_results,
        ),
        refreshed_existing_results,
    )
    if refreshed_existing_results != existing_results:
        persist_reconciled_historical_results(
            output_file=output_file,
            dataset_id=dataset_id,
            results=refreshed_existing_results,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            run_config=run_config,
            run_fingerprint=run_fingerprint,
            metadata_scope="run",
        )
    if (
        feedback_output
        and feedback_output != output_file
        and refreshed_state.feedback_results != feedback_results
    ):
        persist_reconciled_historical_results(
            output_file=feedback_output,
            dataset_id=dataset_id,
            results=refreshed_state.feedback_results,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            run_config=run_config,
            run_fingerprint=run_fingerprint,
            metadata_scope="feedback",
        )
        persist_feedback_run_index(feedback_output)
    if refreshed_count:
        logger.info(
            "[check-submission-resume] refreshed %d historical pending results",
            refreshed_count,
        )
    return refreshed_state
