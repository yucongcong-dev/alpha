"""Simulation polling stage and retry boundary."""

from __future__ import annotations

from collections.abc import Callable
import logging

from ..api.api_types import SimulationPayload
from ..api.client import BrainClient, retry_operation
from ..config.constants import (
    API_KEY_PROGRESS,
    API_KEY_STATE,
    API_KEY_STATUS,
    SIMULATION_RETRY_WAIT,
    STATUS_SKIPPED,
)
from ..exceptions import BrainStopRequested
from ..models.domain import FieldTestContext, FieldTestResult
from ..models.runtime_config import SimulationStageConfig
from ..models.runtime_protocols import SimulationStageArgs
from ..utils.helpers import first_non_empty
from .simulation_parsing import extract_alpha_id, summarize_failure
from .simulation_results import handle_stage_error

logger = logging.getLogger(__name__)


def poll_simulation_with_retry(
    client: BrainClient,
    simulation_location: str,
    retries: int,
    *,
    max_polls: int,
    max_wait_seconds: float,
    max_pending_cycles: int,
    max_queue_seconds: float,
    should_abort: Callable[[], bool] | None = None,
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
            should_abort=should_abort,
        ),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
        should_abort=should_abort,
    )


def run_simulation_poll_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: SimulationStageArgs,
    *,
    simulation_location: str,
    simulation_id: str,
    should_abort: Callable[[], bool] | None = None,
) -> FieldTestResult | tuple[str, SimulationPayload]:
    try:
        config = SimulationStageConfig.from_stage_args(args)
        simulation_result = poll_simulation_with_retry(
            client,
            simulation_location,
            config.simulation_poll_retries,
            max_polls=config.simulation_max_polls,
            max_wait_seconds=float(config.simulation_max_wait_seconds),
            max_pending_cycles=config.simulation_max_pending_cycles,
            max_queue_seconds=float(config.simulation_max_queue_seconds),
            should_abort=should_abort,
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
    except BrainStopRequested as exc:
        return ctx.failure(
            failed_stage="stopped",
            message=str(exc),
            simulation_id=simulation_id,
            status=STATUS_SKIPPED,
        )
    except Exception as exc:
        return handle_stage_error(
            ctx,
            "simulation",
            exc,
            simulation_id=simulation_id,
        )
