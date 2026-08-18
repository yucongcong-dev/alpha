"""Bounded refresh of unresolved Check Submission results."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import logging
import math
import time
from typing import cast

from ..api.client import BrainClient
from ..api.timing import wait_seconds
from ..config.static_config import get_static_config
from ..exceptions import BrainHTTPError, BrainStopRequested
from ..models.domain import FieldTestResult
from ..models.result_predicates import needs_submission_check_refresh
from ..models.runtime_protocols import ClientFactoryLike
from ..models.submission_check import SubmissionCheckOutcome, SubmissionCheckState
from .submission_checks import read_submission_status_with_retry

logger = logging.getLogger(__name__)

DEFAULT_PENDING_CHECK_REFRESH_LIMIT = 20
DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS = 30.0
DEFAULT_PENDING_CHECK_BACKOFF_SECONDS = 3.0
MAX_PENDING_CHECK_BACKOFF_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class PendingCheckRefreshOptions:
    """One bounded refresh budget shared by all pending-check callers."""

    retries: int
    refresh_limit: int = DEFAULT_PENDING_CHECK_REFRESH_LIMIT
    max_refresh_seconds: float = DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS
    max_workers: int = 1
    repeat_until_terminal: bool = False

    def __post_init__(self) -> None:
        if self.refresh_limit < 0:
            raise ValueError("refresh_limit cannot be negative")
        if not math.isfinite(self.max_refresh_seconds) or self.max_refresh_seconds <= 0:
            raise ValueError("max_refresh_seconds must be positive")
        if self.max_workers <= 0:
            raise ValueError("max_workers must be positive")


@dataclass(frozen=True, slots=True)
class PendingCheckRefreshResult:
    """Structured result of one bounded pending-check reconciliation."""

    results: list[FieldTestResult]
    resolved_count: int
    attempted_alpha_ids: frozenset[str] = frozenset()
    deferred_count: int = 0


class PendingCheckService:
    """Own Alpha-ID deduplication and bounded Submission Check refreshes."""

    def __init__(
        self,
        client: BrainClient | ClientFactoryLike,
        options: PendingCheckRefreshOptions,
    ) -> None:
        self._client = client
        self._options = options

    @staticmethod
    def select_candidates(*result_groups: list[FieldTestResult]) -> list[FieldTestResult]:
        """Select one latest refresh representative for each Alpha ID."""

        return select_submission_check_refresh_candidates(*result_groups)

    @staticmethod
    def project(
        results: list[FieldTestResult],
        refreshed_results: list[FieldTestResult],
    ) -> list[FieldTestResult]:
        """Project a single Alpha-ID observation onto a persisted view."""

        return project_submission_check_refresh(results, refreshed_results)

    def refresh(self, results: list[FieldTestResult]) -> PendingCheckRefreshResult:
        """Refresh existing Alpha IDs without creating new simulations."""
        # Normalize legacy mixed rows first, then issue at most one GET per
        # Alpha ID.  The returned view is projected back onto every original
        # row so deduplication never drops run/feedback metadata.
        terminalized_results = [_terminalize_failed_pending_result(result) for result in results]
        candidates = select_submission_check_refresh_candidates(terminalized_results)
        refreshed = _refresh_pending_check_results_impl(
            self._client,
            candidates,
            options=self._options,
        )
        projected = project_submission_check_refresh(terminalized_results, refreshed.results)
        terminalized_count = sum(
            original != normalized
            for original, normalized in zip(results, terminalized_results, strict=True)
        )
        return replace(
            refreshed,
            results=projected,
            resolved_count=refreshed.resolved_count + terminalized_count,
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _terminalize_failed_pending_result(result: FieldTestResult) -> FieldTestResult:
    """Close legacy mixed FAIL/PENDING results without another platform request."""
    outcome = SubmissionCheckOutcome.from_result(result)
    if result.status != "simulated" or outcome.state is not SubmissionCheckState.FAILED:
        return result
    checks = list(result.failed_checks or [])
    check_results = {str(check.result or "").upper() for check in checks}
    if "FAIL" not in check_results or "PENDING" not in check_results:
        return result
    return replace(
        result,
        submittable=False,
        message="checks failed",
        failed_checks=[check for check in checks if str(check.result or "").upper() == "FAIL"],
        updated_at=_utc_now_iso(),
    )


def _ordered_pending_check_results(
    results: list[FieldTestResult],
) -> list[tuple[int, FieldTestResult]]:
    pending_results = [
        (index, result)
        for index, result in enumerate(results)
        if needs_submission_check_refresh(result) and result.alpha_id
    ]
    pending_results.sort(key=lambda item: (item[1].updated_at or item[1].created_at, item[0]))
    return pending_results


def _candidate_preference(result: FieldTestResult) -> tuple[float, int]:
    """Prefer the newest persisted observation when alpha IDs overlap."""
    timestamps: list[float] = []
    for value in (result.updated_at, result.created_at):
        if not value:
            continue
        try:
            timestamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except ValueError:
            continue
    return (max(timestamps, default=0.0), max(1, int(result.revision or 1)))


def select_submission_check_refresh_candidates(
    *result_groups: list[FieldTestResult],
) -> list[FieldTestResult]:
    """Return one refresh target per Alpha ID across all persisted views.

    The same Alpha can appear in the current-run and feedback journals.  The
    refresh operation is keyed by Alpha ID, so choosing one representative
    avoids duplicate GETs while preserving each view's own result metadata.
    """
    candidates: dict[str, FieldTestResult] = {}
    for results in result_groups:
        for result in results:
            alpha_id = result.alpha_id
            if not alpha_id or not needs_submission_check_refresh(result):
                continue
            current = candidates.get(alpha_id)
            if current is None or _candidate_preference(result) > _candidate_preference(current):
                candidates[alpha_id] = result
    return list(candidates.values())


def _apply_submission_check_observation(
    original: FieldTestResult,
    refreshed: FieldTestResult,
) -> FieldTestResult:
    """Copy only check-observation fields into a view's original result row."""
    return replace(
        original,
        status=refreshed.status,
        submittable=refreshed.submittable,
        message=refreshed.message,
        updated_at=refreshed.updated_at,
        failed_stage=refreshed.failed_stage,
        failed_checks=refreshed.failed_checks,
        error_type=refreshed.error_type,
    )


def project_submission_check_refresh(
    results: list[FieldTestResult],
    refreshed_results: list[FieldTestResult],
) -> list[FieldTestResult]:
    """Project refreshed check observations back onto one persisted view."""
    refreshed_by_alpha_id = {
        result.alpha_id: result for result in refreshed_results if result.alpha_id
    }
    projected: list[FieldTestResult] = []
    for result in results:
        refreshed = (
            refreshed_by_alpha_id.get(result.alpha_id)
            if result.alpha_id and needs_submission_check_refresh(result)
            else None
        )
        projected.append(
            _apply_submission_check_observation(result, refreshed)
            if refreshed is not None
            else result
        )
    return projected


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
            submittable, message, failed_checks = read_submission_status_with_retry(
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
            status=get_static_config().status_error,
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

    outcome = SubmissionCheckOutcome.from_observation(
        submittable,
        message,
        failed_checks,
        checked_at=checked_at,
    )
    refreshed = replace(
        result,
        submittable=outcome.submittable,
        message=outcome.message,
        failed_stage=None,
        failed_checks=list(outcome.failed_checks),
        updated_at=checked_at,
    )
    if outcome.needs_refresh:
        logger.info(
            "[check-submission-resume] state=%s alpha_id=%s field=%s template=%s",
            outcome.state.value,
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
        outcome.submittable,
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
) -> tuple[int, set[int]]:
    worker_count = min(len(selected_pending), max(1, int(max_workers or 1)))

    def deadline_reached() -> bool:
        return deadline is not None and time.monotonic() >= deadline

    should_abort = deadline_reached if deadline is not None else None
    refreshed_count = 0
    attempted_indexes: set[int] = set()
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
                attempted_indexes.add(index)
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
    return refreshed_count, attempted_indexes


def _refresh_pending_check_results_impl(
    client: BrainClient | ClientFactoryLike,
    results: list[FieldTestResult],
    *,
    options: PendingCheckRefreshOptions,
) -> PendingCheckRefreshResult:
    """Resolve historical PENDING checks without recreating their simulations.

    Live-run bootstrap/finalize calls intentionally make one bounded pass.  The
    dedicated ``check-submissions`` command sets ``repeat_until_terminal`` so
    unresolved rows are revisited with an exponential backoff until the shared
    deadline is reached.
    """
    refresh_limit = options.refresh_limit
    max_refresh_seconds = options.max_refresh_seconds
    max_workers = options.max_workers
    retries = options.retries
    repeat_until_terminal = options.repeat_until_terminal
    refreshed_results = [_terminalize_failed_pending_result(result) for result in results]
    terminalized_count = sum(
        original != refreshed
        for original, refreshed in zip(results, refreshed_results, strict=True)
    )
    if terminalized_count:
        logger.info(
            "[check-submission-resume] locally terminalized %d results with explicit failed checks",
            terminalized_count,
        )
    deadline = time.monotonic() + max_refresh_seconds
    pending_results = _ordered_pending_check_results(refreshed_results)
    if not pending_results:
        return PendingCheckRefreshResult(
            results=refreshed_results,
            resolved_count=terminalized_count,
            deferred_count=0,
        )

    selected_pending = pending_results[:refresh_limit] if refresh_limit > 0 else pending_results
    selected_indexes = tuple(index for index, _result in selected_pending)
    refreshed_count = 0
    attempted_indexes: set[int] = set()
    cycle = 0
    while True:
        current_pending = [
            (index, refreshed_results[index])
            for index in selected_indexes
            if needs_submission_check_refresh(refreshed_results[index])
            and refreshed_results[index].alpha_id
        ]
        if not current_pending or time.monotonic() >= deadline:
            break
        resolved_count, attempted_batch = _apply_pending_check_refreshes(
            client,
            current_pending,
            refreshed_results,
            retries=retries,
            max_workers=max_workers,
            deadline=deadline,
        )
        refreshed_count += resolved_count
        attempted_indexes.update(attempted_batch)
        if not repeat_until_terminal or len(attempted_batch) < len(current_pending):
            break
        if not any(
            needs_submission_check_refresh(refreshed_results[index]) for index in selected_indexes
        ):
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
    attempted_alpha_ids = frozenset(
        cast(str, refreshed_results[index].alpha_id)
        for index in attempted_indexes
        if refreshed_results[index].alpha_id
    )
    return PendingCheckRefreshResult(
        results=refreshed_results,
        resolved_count=refreshed_count + terminalized_count,
        attempted_alpha_ids=attempted_alpha_ids,
        deferred_count=deferred_count,
    )


__all__ = [
    "DEFAULT_PENDING_CHECK_BACKOFF_SECONDS",
    "DEFAULT_PENDING_CHECK_REFRESH_LIMIT",
    "DEFAULT_PENDING_CHECK_REFRESH_MAX_SECONDS",
    "MAX_PENDING_CHECK_BACKOFF_SECONDS",
    "PendingCheckRefreshOptions",
    "PendingCheckRefreshResult",
    "PendingCheckService",
    "project_submission_check_refresh",
    "select_submission_check_refresh_candidates",
]
