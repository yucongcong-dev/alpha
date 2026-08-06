"""Shared builders for run-loop round behavior tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Semaphore
from unittest.mock import MagicMock

from alpha.app.run_loop_rounds import ScheduleRoundContext
from alpha.app.run_loop_seed_phase import SeedPhaseState
from alpha.models.domain import TemplateField
from alpha.models.io_types import RunFilters
from alpha.runtime.concurrency import RuntimeConcurrencyState
from alpha.runtime.contexts import FutureCompletionContext, HistoricalRunState, TemplateBuildContext
from alpha.runtime.state import ExecutionState, InitializedRunContext
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
    run_ctx = InitializedRunContext(
        client_factory=None,
        template_library={},
        filters=RunFilters(),
        expression_policy=None,
        use_dataset_heuristics=False,
        template_library_fingerprint="tpl-fp",
        settings_fingerprint="settings-fp",
        historical_state=HistoricalRunState(),
        fields=fields,
        execution_state=execution_state,
        runtime_state=runtime_state,
        create_semaphore=Semaphore(1),
        run_config={},
    )
    return ScheduleRoundContext(
        simulation_config=build_simulation_stage_config(),
        run_ctx=run_ctx,
        executor=ThreadPoolExecutor(max_workers=1),
        template_build_ctx=MagicMock(spec=TemplateBuildContext),
        fields=fields,
        completion_ctx=FutureCompletionContext(),
        state_file=state_file,
        field_template_batch_size=field_template_batch_size,
        seed_phase=SeedPhaseState.create(
            fields,
            enabled=seed_phase_enabled,
            resolved_field_ids=seed_resolved_field_ids,
        ),
    )
