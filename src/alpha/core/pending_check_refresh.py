"""Bounded refresh of unresolved Check Submission results."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import logging
import math
import time
from typing import cast

from ..api.client import BrainClient
from ..api.timing import wait_seconds
from ..config._constants_strings import STATUS_ERROR
from ..exceptions import BrainHTTPError, BrainStopRequested
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks
from ..models.runtime_protocols import ClientFactoryLike
from .submission_checks import check_submission_with_retry

logger = logging.getLogger(__name__)

DEFAULT_PENDING_CHECK_REFRESH_LIMIT = 20
DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS = 30.0
DEFAULT_PENDING_CHECK_BACKOFF_SECONDS = 3.0
MAX_PENDING_CHECK_BACKOFF_SECONDS = 60.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ordered_pending_check_results(
    results: list[FieldTestResult],
) -> list[tuple[int, FieldTestResult]]:
    pending_results = [
        (index, result)
        for index, result in enumerate(results)
        if has_pending_checks(result) and result.alpha_id
    ]
    pending_results.sort(key=lambda item: (item[1].updated_at or item[1].created_at, item[0]))
    return pending_results


@contextmanager
def _refresh_client(
    client: BrainClient | ClientFactoryLike,
    *,
    request_deadline: float | None,
) -> Iterator[BrainClient]:
    get_client = getattr(client, "get_client", None)
    if callable(get_client):
        yield cast(BrainClient, get_client(request_deadline=request_deadline))
        return

    refresh_client = cast(BrainClient, client)
    if not hasattr(refresh_client, "request_deadline"):
        yield refresh_client
        return
    previous_deadline = refresh_client.request_deadline
    refresh_client.request_deadline = request_deadline
    try:
        yield refresh_client
    finally:
        refresh_client.request_deadline = previous_deadline


def _refresh_pending_check_result(
    client: BrainClient | ClientFactoryLike,
    result: FieldTestResult,
    *,
    retries: int,
    should_abort: Callable[[], bool] | None,
    request_deadline: float | None,
) -> tuple[FieldTestResult, bool]:
    alpha_id = result.alpha_id
    if not alpha_id:
        return result, False
    checked_at = _utc_now_iso()
    try:
        with _refresh_client(client, request_deadline=request_deadline) as refresh_client:
            submittable, message, failed_checks = check_submission_with_retry(
                refresh_client,
                alpha_id,
                retries,
                should_abort=should_abort,
            )
    except BrainStopRequested:
        logger.info(
            "[check-submission-resume] startup deadline reached alpha_id=%s field=%s template=%s",
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


def _apply_pending_check_refreshes(
    client: BrainClient | ClientFactoryLike,
    selected_pending: list[tuple[int, FieldTestResult]],
    refreshed_results: list[FieldTestResult],
    *,
    retries: int,
    max_workers: int,
    deadline: float | None,
) -> tuple[int, int]:
    worker_count = min(len(selected_pending), max(1, int(max_workers or 1)))

    def deadline_reached() -> bool:
        return deadline is not None and time.monotonic() >= deadline

    should_abort = deadline_reached if deadline is not None else None
    refreshed_count = 0
    attempted_count = 0
    cursor = 0
    executor = ThreadPoolExecutor(max_workers=worker_count)
    try:
        while cursor < len(selected_pending):
            if deadline_reached():
                break
            batch = selected_pending[cursor : cursor + worker_count]
            futures = [
                executor.submit(
                    _refresh_pending_check_result,
                    client,
                    result,
                    retries=retries,
                    should_abort=should_abort,
                    request_deadline=deadline,
                )
                for _index, result in batch
            ]
            remaining_seconds = None if deadline is None else max(0.0, deadline - time.monotonic())
            done, not_done = wait(futures, timeout=remaining_seconds)
            done_set = set(done)
            for (index, _result), future in zip(batch, futures, strict=True):
                if future not in done_set:
                    continue
                refreshed, resolved = future.result()
                refreshed_results[index] = refreshed
                refreshed_count += int(resolved)
                attempted_count += 1
            if not_done:
                for future in not_done:
                    future.cancel()
                break
            cursor += len(batch)
    finally:
        # A timed-out refresh task still owns a client until its deadline/abort
        # path returns. Do not let bootstrap/finalize close that client underneath
        # a live worker.
        executor.shutdown(wait=True, cancel_futures=True)
    return refreshed_count, attempted_count


def refresh_pending_check_results(
    client: BrainClient | ClientFactoryLike,
    results: list[FieldTestResult],
    *,
    retries: int,
    refresh_limit: int = DEFAULT_PENDING_CHECK_REFRESH_LIMIT,
    max_refresh_seconds: float = DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS,
    max_workers: int = 1,
    repeat_until_terminal: bool = False,
) -> tuple[list[FieldTestResult], int]:
    """Resolve historical PENDING checks without recreating their simulations.

    Live-run bootstrap/finalize calls intentionally make one bounded pass.  The
    dedicated ``check-submissions`` command sets ``repeat_until_terminal`` so
    unresolved rows are revisited with an exponential backoff until the shared
    deadline is reached.
    """
    if refresh_limit < 0:
        raise ValueError("refresh_limit cannot be negative")
    if not math.isfinite(max_refresh_seconds) or max_refresh_seconds <= 0:
        raise ValueError("max_refresh_seconds must be positive")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive")
    refreshed_results = list(results)
    deadline = time.monotonic() + max_refresh_seconds
    pending_results = _ordered_pending_check_results(results)
    if not pending_results:
        return refreshed_results, 0

    selected_pending = pending_results[:refresh_limit] if refresh_limit > 0 else pending_results
    selected_indexes = tuple(index for index, _result in selected_pending)
    refreshed_count = 0
    attempted_indexes: set[int] = set()
    cycle = 0
    while True:
        current_pending = [
            (index, refreshed_results[index])
            for index in selected_indexes
            if has_pending_checks(refreshed_results[index]) and refreshed_results[index].alpha_id
        ]
        if not current_pending or time.monotonic() >= deadline:
            break
        resolved_count, attempted_count = _apply_pending_check_refreshes(
            client,
            current_pending,
            refreshed_results,
            retries=retries,
            max_workers=max_workers,
            deadline=deadline,
        )
        refreshed_count += resolved_count
        attempted_indexes.update(index for index, _result in current_pending[:attempted_count])
        if not repeat_until_terminal or attempted_count < len(current_pending):
            break
        if not any(has_pending_checks(refreshed_results[index]) for index in selected_indexes):
            break

        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            break
        backoff_seconds = min(
            DEFAULT_PENDING_CHECK_BACKOFF_SECONDS * (2**cycle),
            MAX_PENDING_CHECK_BACKOFF_SECONDS,
            remaining_seconds,
        )
        cycle += 1
        try:
            wait_seconds(
                backoff_seconds,
                "waiting before the next pending submission-check refresh",
                should_abort=lambda: time.monotonic() >= deadline,
            )
        except BrainStopRequested:
            break

    deferred_count = len(pending_results) - len(attempted_indexes)
    if deferred_count:
        logger.info(
            "[check-submission-resume] deferred %d pending results after refresh budget "
            "limit=%d max_seconds=%.1f",
            deferred_count,
            refresh_limit,
            max_refresh_seconds,
        )
    return refreshed_results, refreshed_count
