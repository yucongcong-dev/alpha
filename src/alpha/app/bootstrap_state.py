"""Bootstrap execution-state and result-journal initialization."""

from __future__ import annotations

from ..analysis.results_persistence import dump_results_incremental
from ..io.results_store import ensure_results_journal
from ..models.runtime_protocols import RunConfig
from ..runtime.contexts import HistoricalRunState
from ..runtime.state import ExecutionState


def create_execution_state(
    *,
    historical_state: HistoricalRunState,
) -> ExecutionState:
    """Build in-memory execution state without writing runtime artifacts."""
    return ExecutionState.create(
        initial_results=historical_state.existing_results,
        attempted_keys=historical_state.attempted_keys,
        template_stats=historical_state.template_stats,
    )


def build_execution_state(
    *,
    dataset_id: str,
    output_file: str,
    historical_state: HistoricalRunState,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_fingerprint: str,
    run_config: RunConfig,
) -> ExecutionState:
    """Restore execution state and initialize its incremental result journal."""
    execution_state = create_execution_state(
        historical_state=historical_state,
    )
    result_ledger = execution_state.result_ledger
    result_ledger.persisted_result_count = ensure_results_journal(
        output_file,
        result_ledger.results,
    )
    metrics = result_ledger.metrics
    result_ledger.persisted_result_count = dump_results_incremental(
        output_file,
        dataset_id,
        [],
        persisted_result_count=result_ledger.persisted_result_count,
        tested=len(result_ledger.results),
        unique_fields_tested=len(metrics.unique_field_ids),
        submittable_count=metrics.submittable_count,
        error_count=metrics.error_count,
        queue_timeout_count=metrics.queue_timeout_count,
        pending_check_count=metrics.pending_check_count,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_fingerprint=run_fingerprint,
        run_config=run_config,
        template_stats=execution_state.template_stats,
    )
    return execution_state
