"""
bootstrap 执行态与历史结果装配辅助模块。
"""

from __future__ import annotations

from ..analysis.results_persistence import dump_results_incremental
from ..io.results_store import initialize_results_journal
from ..models.runtime_protocols import RunConfig
from ..policy.blacklist_context import set_active_datasets_root
from ..policy.blacklist_runtime_stats import build_blacklist_runtime_stats
from ..policy.blacklist_store import load_blacklisted_template_keys
from ..policy.evaluation import summarize_policy_evaluation
from ..runtime.contexts import HistoricalRunState
from ..runtime.state import ExecutionState


def create_execution_state(
    *,
    dataset_id: str,
    historical_state: HistoricalRunState,
    datasets_root: str = "",
) -> ExecutionState:
    """Build in-memory execution state without writing runtime artifacts."""
    set_active_datasets_root(datasets_root)
    execution_state = ExecutionState(
        results=list(historical_state.existing_results),
        attempted_keys=set(historical_state.attempted_keys),
        template_stats=dict(historical_state.template_stats),
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )
    execution_state.submittable_baseline_count = execution_state.metrics.submittable_count
    execution_state.blacklist_runtime_stats = build_blacklist_runtime_stats(execution_state.results)
    execution_state.blacklisted_template_keys = load_blacklisted_template_keys(dataset_id)
    return execution_state


def build_execution_state(
    *,
    dataset_id: str,
    output_file: str,
    historical_state: HistoricalRunState,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: RunConfig,
    datasets_root: str = "",
) -> ExecutionState:
    """根据历史结果恢复 execution_state，并初始化 journal / sidecar 计数。"""
    execution_state = create_execution_state(
        dataset_id=dataset_id,
        historical_state=historical_state,
        datasets_root=datasets_root,
    )
    execution_state.persisted_result_count = initialize_results_journal(
        output_file,
        execution_state.results,
    )
    metrics = execution_state.metrics
    execution_state.persisted_result_count = dump_results_incremental(
        output_file,
        dataset_id,
        [],
        persisted_result_count=execution_state.persisted_result_count,
        tested=len(execution_state.results),
        unique_fields_tested=len(metrics.unique_field_ids),
        submittable_count=metrics.submittable_count,
        submitted_count=metrics.submitted_count,
        error_count=metrics.error_count,
        queue_timeout_count=metrics.queue_timeout_count,
        pending_check_count=metrics.pending_check_count,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
        template_stats=execution_state.template_stats,
        policy_evaluation=summarize_policy_evaluation(execution_state.results),
    )
    return execution_state
