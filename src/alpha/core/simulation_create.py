"""Simulation creation stage and retry boundary."""

from __future__ import annotations

import logging
import re
from typing import Any

from ..api.api_types import SimulationPayload
from ..api.client import BrainClient, retry_operation
from ..config._constants_strings import STATUS_SKIPPED
from ..config.runtime_values import resolve_http_runtime_config
from ..exceptions import BrainStopRequested
from ..generators.payload import build_simulation_payload
from ..models.domain import FieldTestContext, FieldTestResult, SettingsVariant
from ..models.domain_serializers import serialize_settings_variant
from ..models.runtime_config import SimulationStageConfig
from ..models.runtime_protocols import SemaphoreLike
from .simulation_results import handle_stage_error

logger = logging.getLogger(__name__)

_SIM_ID_REGEX: re.Pattern[str] = re.compile(r"/simulations/([^/]+)", re.IGNORECASE)


def _serialize_settings_overrides(
    simulation_settings: SettingsVariant | None,
) -> dict[str, Any]:
    """Serialize the optional settings variant used for this simulation."""
    if simulation_settings is None:
        return {}
    return serialize_settings_variant(simulation_settings)


def create_simulation_with_retry(
    client: BrainClient,
    payload: SimulationPayload,
    retries: int,
    *,
    should_abort: Any | None = None,
) -> tuple[str, str]:
    simulation_location = retry_operation(
        "create simulation",
        retries,
        lambda: client.create_simulation(payload),
        retry_wait_seconds=resolve_http_runtime_config(client).simulation_retry_wait,
        should_abort=should_abort,
    )
    simulation_id_match = re.search(_SIM_ID_REGEX, simulation_location)
    simulation_id = simulation_id_match.group(1) if simulation_id_match else simulation_location
    logger.debug(
        "[simulation] created simulation_id=%s location=%s",
        simulation_id,
        simulation_location,
    )
    return simulation_location, simulation_id


def run_simulation_create_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    config: SimulationStageConfig,
    *,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: SemaphoreLike | None = None,
    should_abort: Any | None = None,
) -> FieldTestResult | tuple[str, str]:
    try:
        if should_abort is not None and should_abort():
            raise BrainStopRequested("simulation create aborted because stop was requested")
        payload = build_simulation_payload(config, ctx.expression)
        if simulation_settings is not None:
            payload["settings"].update(_serialize_settings_overrides(simulation_settings))
        ctx.settings = dict(payload["settings"])
        create_slot_acquired = False
        if create_semaphore is not None:
            logger.info(
                "[simulation] waiting for create slot field=%s template=%s",
                ctx.field_id,
                ctx.template_name,
            )
            while not create_slot_acquired:
                if should_abort is not None and should_abort():
                    raise BrainStopRequested(
                        "simulation create aborted while waiting for a create slot"
                    )
                create_slot_acquired = create_semaphore.acquire(timeout=0.1)
        try:
            if should_abort is not None and should_abort():
                raise BrainStopRequested("simulation create aborted because stop was requested")
            simulation_location, simulation_id = create_simulation_with_retry(
                client,
                payload,
                config.simulation_create_retries,
                should_abort=should_abort,
            )
        finally:
            if create_semaphore is not None and create_slot_acquired:
                create_semaphore.release()
        return simulation_location, simulation_id
    except BrainStopRequested as exc:
        return ctx.failure(
            failed_stage="stopped",
            message=str(exc),
            status=STATUS_SKIPPED,
        )
    except Exception as exc:
        return handle_stage_error(ctx, "simulation", exc)
