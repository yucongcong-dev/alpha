"""Check Submission stage and retry boundary."""

from __future__ import annotations

from collections.abc import Callable
import logging

from ..api.api_types import SimulationPayload
from ..api.client import BrainClient, retry_operation
from ..api.timing import wait_seconds
from ..config.constants import SIMULATION_RETRY_WAIT, STATUS_SKIPPED
from ..exceptions import BrainAPIError, BrainHTTPError, BrainStopRequested
from ..models.domain import FailedCheck, FieldTestContext, FieldTestResult
from ..models.domain_parsers import parse_failed_check
from ..models.runtime_config import SimulationStageConfig
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


def check_submission_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
    *,
    should_abort: Callable[[], bool] | None = None,
) -> tuple[bool | None, str, list[FailedCheck]]:
    attempts = max(1, int(retries or 0))
    last_result: tuple[bool | None, str, list[FailedCheck]] = (
        None,
        "checks unavailable",
        [],
    )
    for attempt in range(1, attempts + 1):
        try:
            submission_check = retry_operation(
                "check submission",
                _CHECK_SUBMISSION_TRANSPORT_RETRIES,
                lambda: client.check_alpha_submission(alpha_id),
                retry_wait_seconds=SIMULATION_RETRY_WAIT,
                should_abort=should_abort,
            )
        except BrainStopRequested:
            raise
        except BrainHTTPError as exc:
            if exc.is_permanent_client_error:
                raise
            last_result = None, "checks unavailable", []
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
                    SIMULATION_RETRY_WAIT,
                    f"waiting for submission checks for alpha {alpha_id}",
                    verbose=False,
                    should_abort=should_abort,
                )
            continue
        except BrainAPIError as exc:
            last_result = None, "checks unavailable", []
            logger.warning(
                "[check-submission] alpha_id=%s attempt=%d/%d unavailable: %s",
                alpha_id,
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                wait_seconds(
                    SIMULATION_RETRY_WAIT,
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
        last_result = submittable, message, unresolved_checks
        logger.debug(
            "[check-submission] alpha_id=%s attempt=%d/%d submittable=%s message=%s",
            alpha_id,
            attempt,
            attempts,
            submittable,
            message,
        )
        if submittable is not None:
            return last_result
        if attempt < attempts:
            wait_seconds(
                SIMULATION_RETRY_WAIT,
                f"waiting for submission checks for alpha {alpha_id}",
                verbose=False,
                should_abort=should_abort,
            )
    return last_result


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
        passed, reason, _ = precheck_simulation_metrics(
            simulation_result,
            min_sharpe=config.min_sharpe,
            min_fitness=config.min_fitness,
            min_turnover=config.min_turnover,
            max_turnover=config.max_turnover,
            max_weight=config.max_weight,
        )
        if not passed:
            logger.info(
                "[check-submission-precheck] alpha_id=%s simulation_id=%s precheck_failed=%s",
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
            status=STATUS_SKIPPED,
        )
    except Exception as exc:
        return handle_stage_error(
            ctx,
            "check_submission",
            exc,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
        )
