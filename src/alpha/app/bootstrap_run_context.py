"""Runtime concurrency and initialized context assembly for bootstrap."""

from __future__ import annotations

import logging
import threading

from ..models.runtime_protocols import ClientFactoryLike, RuntimeConcurrencyArgs
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.state import InitializedRunContext
from .bootstrap_types import PreparedBootstrapResources, RuntimeConcurrencyResources

logger = logging.getLogger(__name__)


def build_runtime_concurrency(
    args: RuntimeConcurrencyArgs,
) -> RuntimeConcurrencyResources:
    """Build runtime concurrency state and semaphore from narrow concurrency args."""
    max_workers = max(1, int(args.max_concurrent_simulations or 0))
    runtime_state = RuntimeConcurrencyState(
        max_workers=max_workers,
        runtime_max_workers=max_workers,
    )
    max_create_workers = max(1, int(args.max_concurrent_creates or 0))
    create_semaphore = threading.Semaphore(max_create_workers)
    logger.info("[config] max_concurrent_simulations=%d", max_workers)
    logger.info("[config] max_concurrent_creates=%d", max_create_workers)
    logger.info("[config] simulation_max_pending_cycles=%d", args.simulation_max_pending_cycles)
    return RuntimeConcurrencyResources(
        runtime_state=runtime_state,
        create_semaphore=create_semaphore,
    )


def assemble_initialized_run_context(
    *,
    client_factory: ClientFactoryLike,
    prepared: PreparedBootstrapResources,
    execution_state,
    runtime_state: RuntimeConcurrencyState,
    create_semaphore: threading.Semaphore,
) -> InitializedRunContext:
    """Assemble the final initialized run context from prepared bootstrap parts."""
    return InitializedRunContext(
        client_factory=client_factory,
        template_library=prepared.template_library,
        filters=prepared.filters,
        expression_policy=prepared.expression_policy,
        use_dataset_heuristics=prepared.use_dataset_heuristics,
        template_library_fingerprint=prepared.template_library_fingerprint,
        settings_fingerprint=prepared.settings_fingerprint,
        historical_state=prepared.historical_state,
        fields=prepared.fields,
        execution_state=execution_state,
        runtime_state=runtime_state,
        create_semaphore=create_semaphore,
        run_config=prepared.run_config,
    )
