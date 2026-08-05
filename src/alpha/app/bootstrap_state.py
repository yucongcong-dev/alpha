"""
bootstrap 执行态与历史结果装配辅助模块。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import logging
import time
from typing import cast

from ..analysis.results_persistence import dump_results, dump_results_incremental
from ..api.client import BrainClient
from ..config.constants import STATUS_ERROR
from ..core.submission_checks import check_submission_with_retry
from ..exceptions import BrainHTTPError, BrainStopRequested
from ..io.results_store import exclusive_results_transaction, initialize_results_journal
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks
from ..models.runtime_protocols import ClientFactoryLike, RunConfig
from ..policy.blacklist_context import set_active_datasets_root
from ..policy.blacklist_runtime_stats import build_blacklist_runtime_stats
from ..policy.blacklist_store import load_blacklisted_template_keys
from ..runtime.contexts import HistoricalRunState
from ..runtime.state import ExecutionState

logger = logging.getLogger(__name__)

DEFAULT_PENDING_CHECK_REFRESH_LIMIT = 20
DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS = 30.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_execution_state(
    *,
    dataset_id: str,
    historical_state: HistoricalRunState,
    datasets_root: str = "",
) -> ExecutionState:
    """Build in-memory execution state without writing runtime artifacts."""
    set_active_datasets_root(datasets_root)
    execution_state = ExecutionState.create(
        initial_results=historical_state.existing_results,
        attempted_keys=historical_state.attempted_keys,
        template_stats=historical_state.template_stats,
    )
    result_ledger = execution_state.result_ledger
    # Rewrite journal from the complete in-memory result set then atomically switch
    # to incremental mode so subsequent appends are always relative to a known base.
    result_ledger.submittable_baseline_count = result_ledger.metrics.submittable_count
    execution_state.blacklist_runtime_stats = build_blacklist_runtime_stats(result_ledger.results)
    execution_state.blacklisted_template_keys = load_blacklisted_template_keys(dataset_id)
    return execution_state


def build_execution_state(
    *,
    dataset_id: str,
    output_file: str,
    historical_state: HistoricalRunState,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: RunConfig,
    datasets_root: str = "",
) -> ExecutionState:
    """根据历史结果恢复 execution_state，并初始化 journal / sidecar 计数。"""
    execution_state = create_execution_state(
        dataset_id=dataset_id,
        historical_state=historical_state,
        datasets_root=datasets_root,
    )
    result_ledger = execution_state.result_ledger
    # Rewrite journal from the complete in-memory result set then atomically switch
    # to incremental mode so subsequent appends are always relative to a known base.
    result_ledger.persisted_result_count = initialize_results_journal(
        output_file,
        result_ledger.results,
    )
    metrics = result_ledger.metrics
    result_ledger.persisted_result_count = dump_results_incremental(
        output_file,
        dataset_id,
        [],
        persisted_result_count=result_ledger.persisted_result_count,
        tested=len(result_ledger.results),
        unique_fields_tested=len(metrics.unique_field_ids),
        submittable_count=metrics.submittable_count,
        submitted_count=metrics.submitted_count,
        error_count=metrics.error_count,
        queue_timeout_count=metrics.queue_timeout_count,
        pending_check_count=metrics.pending_check_count,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
        template_stats=execution_state.template_stats,
    )
    return execution_state


def persist_reconciled_historical_results(
    *,
    output_file: str,
    dataset_id: str,
    results: list[FieldTestResult],
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: RunConfig,
) -> None:
    """Persist startup reconciliation before later bootstrap stages may return early."""
    with exclusive_results_transaction(output_file):
        dump_results(
            output_file,
            dataset_id,
            results,
            settings_fingerprint=settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            run_config=run_config,
        )


def refresh_pending_check_results(
    client: BrainClient | ClientFactoryLike,
    results: list[FieldTestResult],
    *,
    retries: int,
    refresh_limit: int = DEFAULT_PENDING_CHECK_REFRESH_LIMIT,
    max_refresh_seconds: float = DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS,
    max_workers: int = 1,
) -> tuple[list[FieldTestResult], int]:
    """Resolve historical PENDING checks without recreating their simulations."""
    refreshed_results = list(results)
    refreshed_count = 0
    attempted_count = 0
    started_at = time.monotonic()
    deadline = started_at + max_refresh_seconds if max_refresh_seconds > 0 else None

    def _deadline_reached() -> bool:
        return deadline is not None and time.monotonic() >= deadline

    pending_results = [
        (index, result)
        for index, result in enumerate(results)
        if has_pending_checks(result) and result.alpha_id
    ]
    pending_results.sort(
        key=lambda item: (
            item[1].updated_at or item[1].created_at,
            item[0],
        )
    )
    if not pending_results:
        return refreshed_results, refreshed_count

    def _refresh_one(result: FieldTestResult) -> tuple[FieldTestResult, bool]:
        alpha_id = result.alpha_id
        if not alpha_id:
            return result, False
        checked_at = _utc_now_iso()
        get_client = getattr(client, "get_client", None)
        active_client = cast(BrainClient, get_client() if callable(get_client) else client)
        try:
            submittable, message, failed_checks = check_submission_with_retry(
                active_client,
                alpha_id,
                retries,
                should_abort=_deadline_reached if deadline is not None else None,
            )
        except BrainStopRequested:
            logger.info(
                "[check-submission-resume] startup deadline reached alpha_id=%s "
                "field=%s template=%s",
                alpha_id,
                result.field_id,
                result.template_name,
            )
            return result, False
        except BrainHTTPError as exc:
            if not exc.is_permanent_client_error:
                raise
            refreshed = replace(
                result,
                status=STATUS_ERROR,
                submittable=False,
                message=f"permanent check submission error: {exc}",
                failed_stage="check_submission",
                failed_checks=[],
                updated_at=checked_at,
            )
            logger.warning(
                "[check-submission-resume] terminal HTTP error alpha_id=%s "
                "field=%s template=%s status=%d",
                alpha_id,
                result.field_id,
                result.template_name,
                exc.status,
            )
            return refreshed, True
        except Exception as exc:
            logger.warning(
                "[check-submission-resume] failed alpha_id=%s field=%s template=%s: %s",
                alpha_id,
                result.field_id,
                result.template_name,
                exc,
            )
            return replace(result, updated_at=checked_at), False
        refreshed = replace(
            result,
            submittable=submittable,
            message=message,
            failed_stage=None,
            failed_checks=failed_checks,
            updated_at=checked_at,
        )
        if submittable is None:
            logger.info(
                "[check-submission-resume] still pending alpha_id=%s field=%s template=%s",
                alpha_id,
                result.field_id,
                result.template_name,
            )
            return refreshed, False
        logger.info(
            "[check-submission-resume] resolved alpha_id=%s field=%s template=%s submittable=%s",
            alpha_id,
            result.field_id,
            result.template_name,
            submittable,
        )
        return refreshed, True

    selected_pending = pending_results
    if refresh_limit > 0:
        selected_pending = selected_pending[:refresh_limit]
    worker_count = min(len(selected_pending), max(1, int(max_workers or 1)))
    cursor = 0
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        while cursor < len(selected_pending):
            if _deadline_reached():
                break
            batch = selected_pending[cursor : cursor + worker_count]
            futures = [executor.submit(_refresh_one, result) for _index, result in batch]
            for (index, _result), future in zip(batch, futures, strict=True):
                refreshed, resolved = future.result()
                refreshed_results[index] = refreshed
                refreshed_count += int(resolved)
                attempted_count += 1
            cursor += len(batch)
    deferred_count = len(pending_results) - attempted_count
    if deferred_count:
        logger.info(
            "[check-submission-resume] deferred %d pending results after startup budget "
            "limit=%d max_seconds=%.1f",
            deferred_count,
            refresh_limit,
            max_refresh_seconds,
        )
    return refreshed_results, refreshed_count
