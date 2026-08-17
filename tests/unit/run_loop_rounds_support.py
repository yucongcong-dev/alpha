"""Shared builders for run-loop round behavior tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from alpha.app.run_loop_rounds import ScheduleDependencies, ScheduleRoundContext, ScheduleRuntime
from alpha.app.run_loop_seed_phase import SeedPhaseState
from alpha.models.domain import TemplateField
from alpha.models.io_types import RunFilters
from alpha.models.runtime_options import SchedulerControlOptions
from alpha.runtime.concurrency import RuntimeConcurrencyState
from alpha.runtime.contexts import (
    FutureCompletionContext,
    HistoricalRunState,
    SimulationExecutionResources,
    TemplateBuildContext,
    TemplateFeedbackContext,
    TemplateSourceContext,
)
from alpha.runtime.state import ExecutionState
from tests.unit.simulation_config_support import build_simulation_stage_config


def build_round_context(
    *,
    field_template_batch_size: int,
    state_file: str = "state.json",
    field_ids: tuple[str, ...] = ("f1",),
    seed_phase_enabled: bool = False,
    seed_resolved_field_ids: set[str] | None = None,
) -> ScheduleRoundContext:
    fields = [TemplateField(field_id, field_id, "MATRIX") for field_id in field_ids]
    execution_state = ExecutionState.create()
    runtime_state = RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1)
    execution_resources = SimulationExecutionResources(
        client_factory=None,
        template_library_fingerprint="tpl-fp",
        create_semaphore=MagicMock(),
    )
    template_build_ctx = TemplateBuildContext(
        source=TemplateSourceContext(options=MagicMock()),
        feedback=TemplateFeedbackContext(),
    )
    completion_ctx = FutureCompletionContext(
        settings_fingerprint="settings-fp",
        template_library_fingerprint="tpl-fp",
        run_fingerprint="run-fp",
    )
    return ScheduleRoundContext(
        dependencies=ScheduleDependencies(
            simulation_config=build_simulation_stage_config(),
            execution_resources=execution_resources,
            filters=RunFilters(),
            historical_state=HistoricalRunState(),
            template_build_ctx=template_build_ctx,
            completion_ctx=completion_ctx,
            state_file=state_file,
            scheduler_options=SchedulerControlOptions(),
        ),
        runtime=ScheduleRuntime(
            execution_state=execution_state,
            runtime_state=runtime_state,
            executor=ThreadPoolExecutor(max_workers=1),
            field_template_batch_size=field_template_batch_size,
            seed_phase=SeedPhaseState.create(
                fields,
                enabled=seed_phase_enabled,
                resolved_field_ids=seed_resolved_field_ids,
            ),
        ),
        fields=fields,
    )
