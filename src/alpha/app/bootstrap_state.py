"""
bootstrap 执行态与历史结果装配辅助模块。
"""

from __future__ import annotations

from typing import Any, cast

from ..analysis.result_identity import is_queue_timeout_result
from ..config.constants import STATUS_ERROR
from ..io.results_store import dump_results_incremental, initialize_results_journal
from ..models.runtime import ExecutionState
from ..policy import build_blacklist_runtime_stats, load_blacklisted_template_names


def populate_execution_metrics(execution_state: ExecutionState) -> None:
    """根据当前结果列表回填增量持久化所需的轻量计数。"""
    execution_state.unique_field_ids = {result.field_id for result in execution_state.results}
    execution_state.submittable_count = sum(
        1 for result in execution_state.results if result.submittable
    )
    execution_state.submitted_count = sum(1 for result in execution_state.results if result.submitted)
    execution_state.error_count = sum(1 for result in execution_state.results if result.status == STATUS_ERROR)
    execution_state.queue_timeout_count = sum(
        1 for result in execution_state.results if is_queue_timeout_result(result)
    )


def build_execution_state(
    *,
    dataset_id: str,
    output_file: str,
    historical_state,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict,
) -> ExecutionState:
    """根据历史结果恢复 execution_state，并初始化 journal / sidecar 计数。"""
    execution_state = ExecutionState(
        results=list(historical_state.existing_results),
        attempted_keys=set(historical_state.attempted_keys),
        template_stats=dict(historical_state.template_stats),
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )
    populate_execution_metrics(execution_state)
    execution_state.persisted_result_count = initialize_results_journal(
        output_file,
        execution_state.results,
    )
    execution_state.blacklist_runtime_stats = cast(
        dict[str, dict[str, Any]],
        build_blacklist_runtime_stats(execution_state.results),
    )
    execution_state.blacklisted_template_names = load_blacklisted_template_names(dataset_id)
    execution_state.persisted_result_count = dump_results_incremental(
        output_file,
        dataset_id,
        [],
        persisted_result_count=execution_state.persisted_result_count,
        tested=len(execution_state.results),
        unique_fields_tested=len(execution_state.unique_field_ids),
        submittable_count=execution_state.submittable_count,
        submitted_count=execution_state.submitted_count,
        error_count=execution_state.error_count,
        queue_timeout_count=execution_state.queue_timeout_count,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
    )
    return execution_state
