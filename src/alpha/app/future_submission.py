"""Submit new and resumable simulation workers for the run loop."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import dataclasses
import logging
import time

from ..core.simulation import resume_field_test_in_worker, run_field_test_in_worker
from ..generators.payload import build_simulation_payload
from ..models.domain import FieldTestResult, SettingsVariant, TemplateField
from ..models.domain_serializers import serialize_settings_variant
from ..models.runtime_config import SimulationStageConfig
from ..runtime.contexts import PendingFutureContext, SimulationExecutionResources
from ..runtime.state import ExecutionState

logger = logging.getLogger(__name__)


def cancel_unstarted_futures(execution_state: ExecutionState) -> int:
    """Cancel futures that have not started and remove their non-resumable metadata."""
    return execution_state.future_queue.cancel_unstarted()


def wait_for_inflight_simulation_metadata(
    execution_state: ExecutionState,
    *,
    timeout_seconds: float | None = None,
) -> int:
    """Wait for running create requests to publish metadata or finish without creating."""
    deadline = None if timeout_seconds is None else time.monotonic() + max(0.0, timeout_seconds)
    while True:
        unresolved = [
            (future, context)
            for future, context in execution_state.future_queue.pending_futures.items()
            if future.running() and not future.done() and not context.simulation_location
        ]
        if not unresolved:
            return 0
        if deadline is None:
            time.sleep(0.05)
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return len(unresolved)
        time.sleep(min(0.05, remaining))


def submit_template_future(
    *,
    executor: ThreadPoolExecutor,
    execution_resources: SimulationExecutionResources,
    execution_state: ExecutionState,
    simulation_config: SimulationStageConfig,
    field: TemplateField,
    field_id: str,
    field_name: str,
    field_type: str,
    template_name: str,
    template_family: str,
    template_stage: str,
    template_role: str,
    template_activation_scope: str,
    policy_version: str = "",
    expression: str,
    settings_variant: SettingsVariant,
    variant_fingerprint: str,
) -> None:
    """Submit one simulation future and register its pending metadata."""
    field_with_template = dataclasses.replace(
        field,
        metadata={
            **field.metadata,
            "template_family": template_family,
            "template_stage": template_stage,
            "template_role": template_role,
            "template_activation_scope": template_activation_scope,
            "policy_version": policy_version,
        },
    )
    effective_payload = build_simulation_payload(simulation_config, expression)
    effective_payload["settings"].update(serialize_settings_variant(settings_variant))
    pending_context = PendingFutureContext(
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        template_name=template_name,
        template_family=template_family,
        template_stage=template_stage,
        template_role=template_role,
        template_activation_scope=template_activation_scope,
        policy_version=policy_version,
        expression=expression,
        settings_fingerprint=variant_fingerprint,
        settings=dict(effective_payload["settings"]),
    )

    def _record_simulation_created(simulation_location: str, simulation_id: str) -> None:
        pending_context.simulation_location = simulation_location
        pending_context.simulation_id = simulation_id

    future = executor.submit(
        run_field_test_in_worker,
        execution_resources.client_factory,
        simulation_config,
        field_with_template,
        template_name,
        expression,
        variant_fingerprint,
        execution_resources.template_library_fingerprint,
        settings_variant,
        execution_resources.create_semaphore,
        execution_state.future_queue.abort_workers.is_set,
        _record_simulation_created,
    )
    execution_state.last_submission_at = time.monotonic()
    typed_future: Future[FieldTestResult] = future
    execution_state.future_queue.register(typed_future, pending_context)


def submit_resumable_futures(
    *,
    executor: ThreadPoolExecutor,
    execution_resources: SimulationExecutionResources,
    execution_state: ExecutionState,
    simulation_config: SimulationStageConfig,
) -> int:
    """Submit restored remote simulations for polling before scheduling new work."""
    pending_contexts = execution_state.future_queue.take_resumable_batch()
    scheduled_count = 0
    try:
        for pending_context in pending_contexts:
            future = executor.submit(
                resume_field_test_in_worker,
                execution_resources.client_factory,
                simulation_config,
                pending_context,
                execution_resources.template_library_fingerprint,
                execution_state.future_queue.abort_workers.is_set,
            )
            typed_future: Future[FieldTestResult] = future
            execution_state.future_queue.register(typed_future, pending_context)
            scheduled_count += 1
    except Exception:
        execution_state.future_queue.restore_resumable_batch(pending_contexts[scheduled_count:])
        raise
    if pending_contexts:
        logger.info(
            "[resume] scheduled %d simulations for continued polling", len(pending_contexts)
        )
    return len(pending_contexts)
