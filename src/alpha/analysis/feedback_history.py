"""Historical feedback state and settings-budget selection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from ..config.constants import FEEDBACK_STAGE_RESIMULATE
from ..config.models import DatasetExpressionPolicy
from ..models.domain import FieldTestResult
from ..models.domain_types import FieldFeedbackSummary
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from ..runtime.contexts import HistoricalRunState
from .feedback_run_index import (
    is_indexed_run_current,
    load_feedback_run_index,
    load_summary_run_config,
    resolve_feedback_layout,
    run_config_scope_key,
    run_summary_key,
)
from .feedback_stats import compile_field_feedback, compile_global_failed_check_counts
from .field_stats import current_submittable_count
from .result_identity import attempted_template_keys, merge_latest_results_by_identity
from .result_provenance import enrich_results_provenance
from .results_loader import load_existing_results
from .template_stats import compile_template_stats


def _load_dataset_run_results(
    feedback_output_path: str,
    *,
    current_output_path: str,
    use_run_index: bool = True,
) -> list[FieldTestResult]:
    """Discover existing sibling run summaries when initializing dataset feedback."""
    layout = resolve_feedback_layout(feedback_output_path)
    if layout is None:
        return []
    _, scope_key, runs_root = layout
    if not runs_root.is_dir():
        return []
    current_path = Path(current_output_path).resolve()
    processed_runs = (
        load_feedback_run_index(feedback_output_path)
        if use_run_index and Path(feedback_output_path).exists()
        else {}
    )
    discovered: list[FieldTestResult] = []
    for summary_path in sorted(runs_root.glob("*/summary.json")):
        if summary_path.resolve() == current_path:
            continue
        run_key = run_summary_key(summary_path, runs_root)
        if is_indexed_run_current(
            processed_runs.get(run_key),
            summary_path,
            scope_key=scope_key,
        ):
            continue
        run_config = load_summary_run_config(summary_path)
        if scope_key and run_config_scope_key(run_config) != scope_key:
            continue
        results = load_existing_results(
            str(summary_path),
            repair_corrupt_summary=False,
        )
        observed_at = (
            datetime.fromtimestamp(summary_path.stat().st_mtime, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        enrich_results_provenance(
            results,
            output_path=str(summary_path),
            run_config=run_config,
            observed_at=observed_at,
        )
        discovered.extend(results)
    return discovered


def build_historical_run_state(
    output_path: str,
    feedback_output_path: str,
    *,
    repair_corrupt_summary: bool = True,
) -> HistoricalRunState:
    """加载历史结果并构建续跑与反馈所需的状态对象。"""
    existing_results = load_existing_results(
        output_path,
        repair_corrupt_summary=repair_corrupt_summary,
    )
    feedback_results = (
        existing_results
        if feedback_output_path == output_path
        else load_existing_results(
            feedback_output_path,
            repair_corrupt_summary=repair_corrupt_summary,
        )
    )
    discovered_run_results = _load_dataset_run_results(
        feedback_output_path,
        current_output_path=output_path,
        use_run_index=bool(feedback_results),
    )
    feedback_results = merge_latest_results_by_identity(
        feedback_results,
        discovered_run_results,
        existing_results,
    )
    attempted_keys = attempted_template_keys(feedback_results)
    template_stats = compile_template_stats(feedback_results)
    field_feedback = compile_field_feedback(feedback_results)
    global_failed_check_counts = compile_global_failed_check_counts(feedback_results)
    return HistoricalRunState(
        existing_results=existing_results,
        feedback_results=feedback_results,
        attempted_keys=attempted_keys,
        template_stats=template_stats,
        field_feedback=field_feedback,
        global_failed_check_counts=global_failed_check_counts,
    )


def rebuild_historical_run_state(
    state: HistoricalRunState,
    existing_results: list[FieldTestResult],
) -> HistoricalRunState:
    """Recompute derived history after in-memory result reconciliation."""
    feedback_results = merge_latest_results_by_identity(state.feedback_results, existing_results)
    template_stats = compile_template_stats(feedback_results)
    return replace(
        state,
        existing_results=existing_results,
        feedback_results=feedback_results,
        attempted_keys=attempted_template_keys(feedback_results),
        template_stats=template_stats,
        field_feedback=compile_field_feedback(feedback_results),
        global_failed_check_counts=compile_global_failed_check_counts(feedback_results),
    )


def choose_settings_variant_budget(
    field_feedback: FieldFeedbackSummary | None,
    *,
    expression_policy: DatasetExpressionPolicy | None = None,
    dataset_id: str = "",
) -> int:
    """根据反馈阶段分配 settings 变体预算。"""
    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    stage = resolve_feedback_stage(field_feedback, policy.feedback_loop_policy)
    if stage == FEEDBACK_STAGE_RESIMULATE:
        return policy.feedback_loop_policy.resimulate.settings_variant_budget
    return policy.feedback_loop_policy.generate.settings_variant_budget


def should_stop_after_submittable(
    stop_threshold: int,
    results: Sequence[FieldTestResult],
    *,
    baseline_count: int = 0,
) -> bool:
    """判断本次启动后新增的可提交结果是否达到停止阈值。"""
    if stop_threshold <= 0:
        return False
    current_count = max(0, current_submittable_count(results) - baseline_count)
    return bool(current_count >= stop_threshold)
