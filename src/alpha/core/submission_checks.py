"""Check Submission stage and retry boundary."""

from __future__ import annotations

from collections.abc import Callable
import logging

from ..api.api_types import SimulationPayload
from ..api.client import BrainClient, retry_operation
from ..api.timing import wait_seconds
from ..config.runtime_values import resolve_http_runtime_config
from ..config.static_config import get_static_config
from ..exceptions import BrainAPIError, BrainHTTPError, BrainStopRequested
from ..models.domain import FailedCheck, FieldTestContext, FieldTestResult
from ..models.domain_parsers import parse_failed_check
from ..models.runtime_config import SimulationStageConfig
from ..models.submission_check import SubmissionCheckOutcome
from .simulation_parsing import (
    extract_checks,
    extract_failed_checks,
    extract_pending_checks,
    is_submittable_from_checks,
)
from .simulation_precheck import precheck_simulation_metrics
from .simulation_results import handle_stage_error

logger = logging.getLogger(__name__)

_CHECK_SUBMISSION_TRANSPORT_RETRIES = 2


def _read_submission_check_outcome_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
    *,
    fetch_checks: Callable[[str], SimulationPayload],
    operation_name: str,
    should_abort: Callable[[], bool] | None = None,
) -> SubmissionCheckOutcome:
    """Fetch one submission-check state, retrying only unavailable responses."""
    attempts = max(1, int(retries or 0))
    retry_wait = resolve_http_runtime_config(client).simulation_retry_wait
    last_result = SubmissionCheckOutcome.from_observation(
        None,
        "checks unavailable",
    )
    for attempt in range(1, attempts + 1):
        try:
            submission_check = retry_operation(
                operation_name,
                _CHECK_SUBMISSION_TRANSPORT_RETRIES,
                lambda: fetch_checks(alpha_id),
                retry_wait_seconds=retry_wait,
                should_abort=should_abort,
            )
        except BrainStopRequested:
            raise
        except BrainHTTPError as exc:
            if exc.is_permanent_client_error:
                raise
            last_result = SubmissionCheckOutcome.from_observation(
                None,
                "checks unavailable",
            )
            logger.warning(
                "[check-submission] alpha_id=%s attempt=%d/%d unavailable http_status=%d: %s",
                alpha_id,
                attempt,
                attempts,
                exc.status,
                exc,
            )
            if attempt < attempts:
                wait_seconds(
                    retry_wait,
                    f"waiting for submission checks for alpha {alpha_id}",
                    verbose=False,
                    should_abort=should_abort,
                )
            continue
        except BrainAPIError as exc:
            last_result = SubmissionCheckOutcome.from_observation(
                None,
                "checks unavailable",
            )
            logger.warning(
                "[check-submission] alpha_id=%s attempt=%d/%d unavailable: %s",
                alpha_id,
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                wait_seconds(
                    retry_wait,
                    f"waiting for submission checks for alpha {alpha_id}",
                    verbose=False,
                    should_abort=should_abort,
                )
            continue
        checks = extract_checks(submission_check)
        submittable = is_submittable_from_checks(
            [parse_failed_check(c) for c in checks if isinstance(c, dict)]
        )
        failed_checks = extract_failed_checks(submission_check)
        pending_checks = extract_pending_checks(submission_check)
        unresolved_checks = (
            [*failed_checks, *pending_checks] if submittable is None else failed_checks
        )
        message = (
            "checks unavailable"
            if submittable is None and not unresolved_checks
            else "checks pending"
            if submittable is None
            else "checks passed"
            if submittable
            else "checks failed"
        )
        last_result = SubmissionCheckOutcome.from_observation(
            submittable,
            message,
            unresolved_checks,
        )
        logger.debug(
            "[check-submission] alpha_id=%s attempt=%d/%d submittable=%s message=%s",
            alpha_id,
            attempt,
            attempts,
            submittable,
            message,
        )
        # A semantic PENDING is a valid platform response, not a transport
        # failure.  Repeating the Check Submission endpoint immediately can
        # retrigger the same server-side work; the caller owns its later
        # status-refresh cadence.
        if checks:
            return last_result
        if attempt < attempts:
            wait_seconds(
                retry_wait,
                f"waiting for submission checks for alpha {alpha_id}",
                verbose=False,
                should_abort=should_abort,
            )
    return last_result


def _read_submission_checks_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
    *,
    fetch_checks: Callable[[str], SimulationPayload],
    operation_name: str,
    should_abort: Callable[[], bool] | None = None,
) -> tuple[bool | None, str, list[FailedCheck]]:
    """Compatibility tuple adapter for simulation-stage callers."""

    return _read_submission_check_outcome_with_retry(
        client,
        alpha_id,
        retries,
        fetch_checks=fetch_checks,
        operation_name=operation_name,
        should_abort=should_abort,
    ).as_legacy_tuple()


def check_submission_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
    *,
    should_abort: Callable[[], bool] | None = None,
) -> tuple[bool | None, str, list[FailedCheck]]:
    """Trigger the platform Check Submission action once per semantic response."""

    def fetch_checks(requested_alpha_id: str) -> SimulationPayload:
        return client.check_alpha_submission(requested_alpha_id)

    return _read_submission_checks_with_retry(
        client,
        alpha_id,
        retries,
        fetch_checks=fetch_checks,
        operation_name="check submission",
        should_abort=should_abort,
    )


def read_submission_status_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
    *,
    should_abort: Callable[[], bool] | None = None,
) -> tuple[bool | None, str, list[FailedCheck]]:
    """Read persisted Alpha details without re-triggering Check Submission."""

    def fetch_checks(requested_alpha_id: str) -> SimulationPayload:
        return client.get_alpha_detail(requested_alpha_id)

    return _read_submission_checks_with_retry(
        client,
        alpha_id,
        retries,
        fetch_checks=fetch_checks,
        operation_name="read submission status",
        should_abort=should_abort,
    )


def run_check_submission_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    config: SimulationStageConfig,
    *,
    alpha_id: str,
    simulation_id: str,
    simulation_result: SimulationPayload | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> FieldTestResult | tuple[bool | None, str, list[FailedCheck]]:
    if simulation_result:
        within_local_thresholds, reason, _ = precheck_simulation_metrics(
            simulation_result,
            min_sharpe=config.min_sharpe,
            min_fitness=config.min_fitness,
            min_turnover=config.min_turnover,
            max_turnover=config.max_turnover,
            max_weight=config.max_weight,
        )
        if not within_local_thresholds:
            logger.info(
                "[check-submission-diagnostic] alpha_id=%s simulation_id=%s "
                "local_threshold_miss=%s",
                alpha_id,
                simulation_id,
                reason,
            )

    try:
        return check_submission_with_retry(
            client,
            alpha_id,
            config.check_submission_retries,
            should_abort=should_abort,
        )
    except BrainStopRequested as exc:
        return ctx.failure(
            failed_stage="stopped",
            message=str(exc),
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            status=get_static_config().status_skipped,
        )
    except Exception as exc:
        return handle_stage_error(
            ctx,
            "check_submission",
            exc,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
        )
