"""
simulation 阶段函数与本地预检辅助模块。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..api.api_types import SimulationPayload
from ..api.client import BrainClient, retry_operation
from ..api.timing import wait_seconds
from ..config.constants import (
    API_KEY_FAILED,
    API_KEY_PROGRESS,
    API_KEY_STATE,
    API_KEY_STATUS,
    SIMULATION_RETRY_WAIT,

)

from ..generators.payload import build_simulation_payload
from ..models.domain import (
    FailedCheck,
    FieldTestContext,
    FieldTestResult,
    SettingsVariant,
)
from ..models.domain_parsers import parse_failed_check
from ..models.runtime import SimulationStageConfig
from ..models.runtime_protocols import SemaphoreLike, SimulationStageArgs
from ..utils.helpers import first_non_empty
from .simulation_parsing import (
    extract_alpha_id,
    extract_checks,
    extract_failed_checks,

    is_submittable_from_checks,
    summarize_failure,
)
from .simulation_precheck import PrecheckConfig, precheck_simulation_metrics
from .simulation_results import handle_stage_error

logger = logging.getLogger(__name__)

_SIM_ID_REGEX: re.Pattern[str] = re.compile(r"/simulations/([^/]+)", re.IGNORECASE)


def _int_arg(args: object, name: str, default: int = 0) -> int:
    try:
        return int(getattr(args, name, default) or default)
    except (TypeError, ValueError):
        return default



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
) -> tuple[bool | None, str, list[FailedCheck]]:
    alpha_detail = retry_operation(
        "checksubmit",
        retries,
        lambda: client.get_alpha_detail(alpha_id),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )
    checks = extract_checks(alpha_detail)
    submittable = is_submittable_from_checks([parse_failed_check(c) for c in checks if isinstance(c, dict)])
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


def run_simulation_create_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: SimulationStageArgs,
    *,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: SemaphoreLike | None = None,
) -> FieldTestResult | tuple[str, str]:
    try:
        config = SimulationStageConfig.from_args(args)
        payload = build_simulation_payload(args, ctx.expression)
        if simulation_settings is not None:
            payload["settings"] = simulation_settings.to_dict()
        if create_semaphore is not None:
            logger.info(
                "[simulation] waiting for create slot field=%s template=%s",
                ctx.field_id,
                ctx.template_name,
            )
            _ = create_semaphore.acquire()
        try:
            simulation_location, simulation_id = create_simulation_with_retry(
                client,
                payload,
                config.simulation_create_retries,
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
        config = SimulationStageConfig.from_args(args)
        simulation_result = poll_simulation_with_retry(
            client,
            simulation_location,
            config.simulation_poll_retries,
            max_polls=config.simulation_max_polls,
            max_wait_seconds=float(config.simulation_max_wait_seconds),
            max_pending_cycles=config.simulation_max_pending_cycles,
            max_queue_seconds=float(config.simulation_max_queue_seconds),
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
) -> FieldTestResult | tuple[bool | None, str, list[FailedCheck]]:
    if simulation_result:
        precheck_config = PrecheckConfig.from_args(args)
        passed, reason, precheck_failed_checks = precheck_simulation_metrics(
            simulation_result,
            min_sharpe=precheck_config.min_sharpe,
            min_fitness=precheck_config.min_fitness,
            min_turnover=precheck_config.min_turnover,
            max_turnover=precheck_config.max_turnover,
            max_weight=precheck_config.max_weight,
        )
        if not passed:
            logger.info(
                "[checksubmit-precheck] alpha_id=%s simulation_id=%s precheck_failed=%s",
                alpha_id,
                simulation_id,
                reason,
            )
            return False, f"precheck_failed: {reason}", [parse_failed_check(check) for check in precheck_failed_checks]

    try:
        return checksubmit_with_retry(
            client,
            alpha_id,
            _int_arg(args, "check_submit_retries"),
        )
    except Exception as exc:
        return handle_stage_error(
            ctx,
            "checksubmit",
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
]
