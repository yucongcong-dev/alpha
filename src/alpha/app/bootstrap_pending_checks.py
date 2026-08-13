"""Persist startup reconciliation for unresolved submission checks."""

from __future__ import annotations

from dataclasses import replace
import logging

from ..analysis.feedback_history import rebuild_historical_run_state
from ..analysis.feedback_run_index import persist_feedback_run_index
from ..analysis.result_identity import result_identity
from ..analysis.results_persistence import dump_results
from ..api.client import BrainClient
from ..core.pending_check_refresh import refresh_pending_check_results
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
) -> None:
    """Persist startup reconciliation before later bootstrap stages may return early."""
    with exclusive_results_transaction(output_file):
        dump_results(
            output_file,
            dataset_id,
            results,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            run_fingerprint=run_fingerprint,
            run_config=run_config,
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
) -> HistoricalRunState:
    """Refresh pending checks and persist every historical view that changed."""
    existing_results = historical_state.existing_results
    feedback_results = historical_state.feedback_results
    refreshed_feedback_results, refreshed_count = refresh_pending_check_results(
        client,
        feedback_results,
        retries=retries,
    )
    if refreshed_feedback_results == feedback_results:
        return historical_state

    refreshed_by_identity = {
        result_identity(result): result for result in refreshed_feedback_results
    }
    refreshed_existing_results = [
        refreshed_by_identity.get(result_identity(result), result) for result in existing_results
    ]
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
        )
    if feedback_output and feedback_output != output_file:
        persist_reconciled_historical_results(
            output_file=feedback_output,
            dataset_id=dataset_id,
            results=refreshed_feedback_results,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            run_config=run_config,
            run_fingerprint=run_fingerprint,
        )
        persist_feedback_run_index(feedback_output)
    if refreshed_count:
        logger.info(
            "[check-submission-resume] refreshed %d historical pending results",
            refreshed_count,
        )
    return refreshed_state
