"""
simulation 阶段函数与本地预检辅助模块。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from ..api.api_types import CheckResultDict, SimulationPayload
from ..api.client import BrainClient, retry_operation
from ..config import (
    API_KEY_FAILED,
    API_KEY_PROGRESS,
    API_KEY_STATE,
    API_KEY_STATUS,
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_TURNOVER,
    PRECHECK_FALLBACK_MAX_TURNOVER,
    PRECHECK_FALLBACK_MAX_WEIGHT,
    PRECHECK_FALLBACK_MIN_FITNESS,
    PRECHECK_FALLBACK_MIN_SHARPE,
    PRECHECK_FALLBACK_MIN_TURNOVER,
    SIMULATION_RETRY_WAIT,
    STATUS_SIMULATED,
    STATUS_SUBMITTED,
    get_submit_max_turnover,
    get_submit_max_weight,
    get_submit_min_fitness,
    get_submit_min_sharpe,
    get_submit_min_turnover,
)
from ..generators.settings import build_simulation_payload
from ..models.base import (
    FieldTestContext,
    FieldTestResult,
    SemaphoreLike,
    SettingsVariant,
    SimulationStageArgs,
)
from ..utils.helpers import first_non_empty
from .simulation_parsing import (
    extract_alpha_id,
    extract_checks,
    extract_failed_checks,
    is_submittable_from_checks,
    summarize_failure,
)
from .simulation_results import handle_stage_error

logger = logging.getLogger(__name__)

_SIM_ID_REGEX: re.Pattern[str] = re.compile(r"/simulations/([^/]+)", re.IGNORECASE)
_RESULT_FAIL: str = "FAIL"
_KEY_CONCENTRATED_WEIGHT: str = "concentratedWeight"
_KEY_FITNESS: str = "fitness"
_KEY_IS: str = "is"
_KEY_LIMIT: str = "limit"
_KEY_MAX_WEIGHT: str = "maxWeight"
_KEY_MAX_WEIGHT_ALT: str = "max_weight"
_KEY_NAME: str = "name"
_KEY_RESULT: str = "result"
_KEY_SHARPE: str = "sharpe"
_KEY_TURNOVER: str = "turnover"
_KEY_VALUE: str = "value"


@dataclass
class PrecheckConfig:
    min_sharpe: float = PRECHECK_FALLBACK_MIN_SHARPE
    min_fitness: float = PRECHECK_FALLBACK_MIN_FITNESS
    min_turnover: float = PRECHECK_FALLBACK_MIN_TURNOVER
    max_turnover: float = PRECHECK_FALLBACK_MAX_TURNOVER
    max_weight: float = PRECHECK_FALLBACK_MAX_WEIGHT

    @classmethod
    def from_args(cls, args: SimulationStageArgs) -> PrecheckConfig:
        return cls(
            min_sharpe=getattr(args, "min_sharpe", cls.min_sharpe),
            min_fitness=getattr(args, "min_fitness", cls.min_fitness),
            min_turnover=getattr(args, "min_turnover", cls.min_turnover),
            max_turnover=getattr(args, "max_turnover", cls.max_turnover),
            max_weight=getattr(args, "max_weight", cls.max_weight),
        )


def precheck_simulation_metrics(
    simulation_result: SimulationPayload,
    *,
    min_sharpe: float = get_submit_min_sharpe(),
    min_fitness: float = get_submit_min_fitness(),
    min_turnover: float = get_submit_min_turnover(),
    max_turnover: float = get_submit_max_turnover(),
    max_weight: float = get_submit_max_weight(),
) -> tuple[bool, str, list[CheckResultDict]]:
    is_section = simulation_result.get(_KEY_IS)
    if not isinstance(is_section, dict):
        return True, "", []

    sharpe = is_section.get(_KEY_SHARPE)
    fitness = is_section.get(_KEY_FITNESS)
    turnover = is_section.get(_KEY_TURNOVER)
    max_stock_weight = (
        is_section.get(_KEY_MAX_WEIGHT)
        or is_section.get(_KEY_MAX_WEIGHT_ALT)
        or is_section.get(_KEY_CONCENTRATED_WEIGHT)
    )

    failures: list[CheckResultDict] = []

    def _add_failure(check_name: str, v: int | float, limit: float) -> None:
        failures.append(
            {
                _KEY_NAME: check_name,
                _KEY_RESULT: _RESULT_FAIL,
                _KEY_VALUE: float(v),
                _KEY_LIMIT: limit,
            }
        )

    if isinstance(sharpe, (int, float)) and sharpe < min_sharpe:
        _add_failure(CHECK_LOW_SHARPE, sharpe, min_sharpe)
    if isinstance(fitness, (int, float)) and fitness < min_fitness:
        _add_failure(CHECK_LOW_FITNESS, fitness, min_fitness)
    if isinstance(turnover, (int, float)):
        if turnover < min_turnover:
            _add_failure(CHECK_LOW_TURNOVER, turnover, min_turnover)
        elif turnover > max_turnover:
            _add_failure(CHECK_HIGH_TURNOVER, turnover, max_turnover)
    if isinstance(max_stock_weight, (int, float)) and max_stock_weight > max_weight:
        _add_failure(CHECK_CONCENTRATED_WEIGHT, max_stock_weight, max_weight)

    if not failures:
        return True, "", []

    reason_parts = [
        f"{f[_KEY_NAME].lower()}: {f[_KEY_VALUE]:.4f} vs limit {f[_KEY_LIMIT]}" for f in failures
    ]
    return False, "; ".join(reason_parts), failures


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
) -> tuple[bool | None, str, list[CheckResultDict]]:
    alpha_detail = retry_operation(
        "checksubmit",
        retries,
        lambda: client.get_alpha_detail(alpha_id),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )
    checks = extract_checks(alpha_detail)
    submittable = is_submittable_from_checks(checks)
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
        return checksubmit_with_retry(client, alpha_id, args.check_submit_retries)
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
