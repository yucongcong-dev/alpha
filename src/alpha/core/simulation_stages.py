"""
simulation 阶段函数与本地预检辅助模块。
"""

from __future__ import annotations

import logging
import re

from ..api.api_types import CheckResultDict, SimulationPayload
from ..api.client import BrainClient, retry_operation
from ..api.timing import wait_seconds
from ..config.constants import (
    API_KEY_FAILED,
    API_KEY_PROGRESS,
    API_KEY_STATE,
    API_KEY_STATUS,
    SIMULATION_RETRY_WAIT,
    STATUS_SIMULATED,
    STATUS_SUBMITTED,
)
from ..config.getters import get_polling_default_wait
from ..generators.payload import build_simulation_payload
from ..models.domain import (
    FailedCheck,
    FieldTestContext,
    FieldTestResult,
    SettingsVariant,
)
from ..models.runtime import (
    SemaphoreLike,
    SimulationStageArgs,
)
from ..utils.helpers import first_non_empty
from .simulation_parsing import (
    extract_alpha_id,
    extract_checks,
    extract_failed_checks,
    extract_pending_checks,
    is_submittable_from_checks,
    summarize_failure,
)
from .simulation_precheck import PrecheckConfig, precheck_simulation_metrics
from .simulation_results import handle_stage_error

logger = logging.getLogger(__name__)

_SIM_ID_REGEX: re.Pattern[str] = re.compile(r"/simulations/([^/]+)", re.IGNORECASE)
_CHECK_SELF_CORRELATION: str = "SELF_CORRELATION"


def _pending_self_correlation_checks(alpha_payload: SimulationPayload) -> list[CheckResultDict]:
    return [
        check
        for check in extract_pending_checks(alpha_payload)
        if str(check.get("name", "")).upper() == _CHECK_SELF_CORRELATION
    ]


def _resolve_self_correlation_checks(
    client: BrainClient,
    alpha_id: str,
    retries: int,
    *,
    max_polls: int,
    poll_seconds: float,
    alpha_detail: SimulationPayload,
) -> SimulationPayload:
    remaining_polls = max(max_polls, 0)
    latest_payload = alpha_detail
    pending_checks = _pending_self_correlation_checks(latest_payload)
    while pending_checks and remaining_polls > 0:
        logger.info(
            "[checksubmit] alpha_id=%s self-correlation pending; remaining_polls=%d",
            alpha_id,
            remaining_polls,
        )
        wait_seconds(max(poll_seconds, 0.0), "self correlation pending")
        latest_payload = retry_operation(
            "checksubmit self correlation",
            retries,
            lambda: client.get_alpha_detail(alpha_id),
            retry_wait_seconds=SIMULATION_RETRY_WAIT,
        )
        pending_checks = _pending_self_correlation_checks(latest_payload)
        remaining_polls -= 1
    return latest_payload


def create_simulation_with_retry(
    client: BrainClient, payload: SimulationPayload, retries: int
) -> tuple[str, str]:
    simulation_location = retry_operation(
        "create simulation",
        retries,
        lambda: client.create_simulation(payload),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )
    simulation_id_match = re.search(_SIM_ID_REGEX, simulation_location)
    simulation_id = simulation_id_match.group(1) if simulation_id_match else simulation_location
    logger.debug(
        "[simulation] created simulation_id=%s location=%s",
        simulation_id,
        simulation_location,
    )
    return simulation_location, simulation_id


def poll_simulation_with_retry(
    client: BrainClient,
    simulation_location: str,
    retries: int,
    *,
    max_polls: int,
    max_wait_seconds: float,
    max_pending_cycles: int,
    max_queue_seconds: float,
) -> SimulationPayload:
    return retry_operation(
        "poll simulation",
        retries,
        lambda: client.poll_simulation(
            simulation_location,
            max_polls=max_polls,
            max_wait_seconds=max_wait_seconds,
            max_pending_cycles=max_pending_cycles,
            max_queue_seconds=max_queue_seconds,
        ),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )


def checksubmit_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
    *,
    self_correlation_max_polls: int = 0,
    self_correlation_poll_seconds: float | None = None,
) -> tuple[bool | None, str, list[CheckResultDict]]:
    alpha_detail = retry_operation(
        "checksubmit",
        retries,
        lambda: client.get_alpha_detail(alpha_id),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )
    alpha_detail = _resolve_self_correlation_checks(
        client,
        alpha_id,
        retries,
        max_polls=self_correlation_max_polls,
        poll_seconds=(
            get_polling_default_wait()
            if self_correlation_poll_seconds is None
            else self_correlation_poll_seconds
        ),
        alpha_detail=alpha_detail,
    )
    checks = extract_checks(alpha_detail)
    pending_self_corr = _pending_self_correlation_checks(alpha_detail)
    if pending_self_corr:
        logger.info(
            "[checksubmit] alpha_id=%s self-correlation still pending after polling; deferring candidate",
            alpha_id,
        )
        return None, "self correlation pending", pending_self_corr
    submittable = is_submittable_from_checks(
        [FailedCheck.from_dict(c) for c in checks]
    )
    failed_checks = extract_failed_checks(alpha_detail)
    message = (
        "checks unavailable"
        if submittable is None
        else "checks passed"
        if submittable
        else "checks failed"
    )
    logger.debug(
        "[checksubmit] alpha_id=%s submittable=%s message=%s",
        alpha_id,
        submittable,
        message,
    )
    return submittable, message, failed_checks


def submit_with_retry(client: BrainClient, alpha_id: str, retries: int) -> str:
    submit_result = retry_operation(
        "submit",
        retries,
        lambda: client.submit_alpha(alpha_id),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )
    if submit_result.get(API_KEY_STATUS) == API_KEY_FAILED:
        return summarize_failure(submit_result)
    return STATUS_SUBMITTED


def run_simulation_create_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: SimulationStageArgs,
    *,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: SemaphoreLike | None = None,
) -> FieldTestResult | tuple[str, str]:
    try:
        payload = build_simulation_payload(args, ctx.expression)
        if simulation_settings is not None:
            payload["settings"] = dict(simulation_settings)
        if create_semaphore is not None:
            logger.info(
                "[simulation] waiting for create slot field=%s template=%s",
                ctx.field_id,
                ctx.template_name,
            )
            _ = create_semaphore.acquire()
        try:
            create_retries: int = args.simulation_create_retries
            simulation_location, simulation_id = create_simulation_with_retry(
                client,
                payload,
                create_retries,
            )
        finally:
            if create_semaphore is not None:
                create_semaphore.release()
        return simulation_location, simulation_id
    except Exception as exc:
        return handle_stage_error(ctx, "simulation", exc)


def run_simulation_poll_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: SimulationStageArgs,
    *,
    simulation_location: str,
    simulation_id: str,
) -> FieldTestResult | tuple[str, SimulationPayload]:
    try:
        simulation_result = poll_simulation_with_retry(
            client,
            simulation_location,
            args.simulation_poll_retries,
            max_polls=args.simulation_max_polls,
            max_wait_seconds=args.simulation_max_wait_seconds,
            max_pending_cycles=args.simulation_max_pending_cycles,
            max_queue_seconds=args.simulation_max_queue_seconds,
        )
        progress = first_non_empty(
            simulation_result.get(API_KEY_PROGRESS),
            simulation_result.get(API_KEY_STATUS),
            simulation_result.get(API_KEY_STATE),
        )
        logger.info(
            "[simulation] completed simulation_id=%s simulation_location=%s progress=%s",
            simulation_id,
            simulation_location,
            progress,
        )
        alpha_id = extract_alpha_id(simulation_result)
        if not alpha_id:
            return ctx.failure(
                failed_stage="simulation",
                message=summarize_failure(simulation_result),
                simulation_id=simulation_id,
                status="simulation_failed",
            )
        return alpha_id, simulation_result
    except Exception as exc:
        return handle_stage_error(
            ctx,
            "simulation",
            exc,
            simulation_id=simulation_id,
        )


def run_checksubmit_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: SimulationStageArgs,
    *,
    alpha_id: str,
    simulation_id: str,
    simulation_result: SimulationPayload | None = None,
) -> FieldTestResult | tuple[bool | None, str, list[CheckResultDict]]:
    if simulation_result:
        config = PrecheckConfig.from_args(args)
        passed, reason, precheck_failed_checks = precheck_simulation_metrics(
            simulation_result,
            min_sharpe=config.min_sharpe,
            min_fitness=config.min_fitness,
            min_turnover=config.min_turnover,
            max_turnover=config.max_turnover,
            max_weight=config.max_weight,
        )
        if not passed:
            logger.info(
                "[checksubmit-precheck] alpha_id=%s simulation_id=%s precheck_failed=%s",
                alpha_id,
                simulation_id,
                reason,
            )
            return False, f"precheck_failed: {reason}", precheck_failed_checks

    try:
        return checksubmit_with_retry(
            client,
            alpha_id,
            args.check_submit_retries,
            self_correlation_max_polls=int(getattr(args, "self_correlation_max_polls", 0) or 0),
            self_correlation_poll_seconds=float(
                getattr(args, "self_correlation_poll_seconds", get_polling_default_wait())
                or get_polling_default_wait()
            ),
        )
    except Exception as exc:
        return handle_stage_error(
            ctx,
            "checksubmit",
            exc,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
        )


def run_submit_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: SimulationStageArgs,
    *,
    alpha_id: str,
    simulation_id: str,
    simulation_location: str,
    submittable: bool | None,
) -> FieldTestResult | tuple[bool, str, str]:
    should_submit: bool = args.submit
    if not (should_submit and submittable):
        return False, STATUS_SIMULATED, ""
    try:
        logger.info(
            "[submit] eligible alpha_id=%s simulation_id=%s simulation_location=%s",
            alpha_id,
            simulation_id,
            simulation_location,
        )
        message = submit_with_retry(client, alpha_id, args.submit_retries)
        return True, STATUS_SUBMITTED, message
    except Exception as exc:
        return handle_stage_error(
            ctx,
            "submit",
            exc,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
        )


__all__ = [
    "PrecheckConfig",
    "checksubmit_with_retry",
    "create_simulation_with_retry",
    "poll_simulation_with_retry",
    "precheck_simulation_metrics",
    "run_checksubmit_stage",
    "run_simulation_create_stage",
    "run_simulation_poll_stage",
    "run_submit_stage",
    "submit_with_retry",
]
