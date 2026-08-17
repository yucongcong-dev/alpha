"""Persist startup reconciliation for unresolved submission checks."""

from __future__ import annotations

from dataclasses import replace
import logging

from ..analysis.feedback_history import rebuild_historical_run_state
from ..analysis.feedback_run_index import persist_feedback_run_index
from ..analysis.results_persistence import dump_results
from ..api.client import BrainClient
from ..core.pending_check_refresh import (
    DEFAULT_PENDING_CHECK_REFRESH_LIMIT,
    DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS,
    refresh_pending_check_results,
)
from ..io.results_store import exclusive_results_transaction
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks
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
    refresh_limit: int | None = None,
    max_refresh_seconds: float | None = None,
    max_workers: int | None = None,
    repeat_until_terminal: bool = False,
) -> HistoricalRunState:
    """Refresh pending checks and persist every historical view that changed."""
    existing_results = historical_state.existing_results
    feedback_results = historical_state.feedback_results
    feedback_pending_alpha_ids = {
        result.alpha_id
        for result in feedback_results
        if has_pending_checks(result) and result.alpha_id
    }
    extra_existing_pending_results = [
        result
        for result in existing_results
        if has_pending_checks(result)
        and result.alpha_id
        and result.alpha_id not in feedback_pending_alpha_ids
    ]
    refresh_input_results = [*feedback_results, *extra_existing_pending_results]
    if (
        refresh_limit is None
        and max_refresh_seconds is None
        and max_workers is None
        and not repeat_until_terminal
    ):
        refreshed_feedback_results, refreshed_count = refresh_pending_check_results(
            client,
            refresh_input_results,
            retries=retries,
        )
    else:
        refreshed_feedback_results, refreshed_count = refresh_pending_check_results(
            client,
            refresh_input_results,
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
        )
    refreshed_all_results = refreshed_feedback_results
    refreshed_feedback_results = refreshed_all_results[: len(feedback_results)]
    refreshed_by_alpha_id = {
        result.alpha_id: result for result in refreshed_feedback_results if result.alpha_id
    }
    refreshed_by_alpha_id.update(
        {
            result.alpha_id: result
            for result in refreshed_all_results[len(feedback_results) :]
            if result.alpha_id
        }
    )
    refreshed_existing_results = [
        refreshed_by_alpha_id.get(result.alpha_id, result)
        if has_pending_checks(result) and result.alpha_id
        else result
        for result in existing_results
    ]
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
        )
        persist_feedback_run_index(feedback_output)
    if refreshed_count:
        logger.info(
            "[check-submission-resume] refreshed %d historical pending results",
            refreshed_count,
        )
    return refreshed_state
