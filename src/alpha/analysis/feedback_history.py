"""Historical feedback state and settings-budget selection."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import logging
from pathlib import Path

from ..config.models import DatasetExpressionPolicy
from ..config.static_config import get_static_config
from ..models.domain import FieldTestResult
from ..models.domain_types import FieldFeedbackMap, FieldFeedbackSummary
from ..models.runtime_protocols import TemplateStats
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from ..runtime.contexts import HistoricalRunState
from .feedback_run_index import (
    feedback_run_index_is_current,
    is_indexed_run_current,
    load_feedback_run_index,
    load_summary_run_config,
    resolve_feedback_layout,
    run_config_scope_key,
    run_summary_key,
)
from .feedback_stats import compile_field_feedback, compile_global_failed_check_counts
from .result_identity import attempted_template_keys, merge_latest_results_by_identity
from .result_provenance import enrich_results_provenance
from .results_loader import load_existing_results
from .template_stats import compile_template_stats

logger = logging.getLogger(__name__)


def _derive_historical_feedback_state(
    feedback_results: list[FieldTestResult],
) -> tuple[
    set[tuple[str, str, str, str]],
    TemplateStats,
    FieldFeedbackMap,
    dict[str, int],
]:
    """Build the feedback-derived state shared by initial load and refresh."""
    return (
        attempted_template_keys(feedback_results),
        compile_template_stats(feedback_results),
        compile_field_feedback(feedback_results),
        compile_global_failed_check_counts(feedback_results),
    )


def _load_rebuildable_feedback_results(
    feedback_output_path: str,
    *,
    repair_corrupt_summary: bool,
) -> list[FieldTestResult]:
    """Load the aggregate feedback cache, rebuilding from runs when it is unusable."""
    try:
        return load_existing_results(
            feedback_output_path,
            repair_corrupt_summary=repair_corrupt_summary,
        )
    except ValueError as exc:
        logger.warning(
            "[feedback] ignored unusable aggregate %s; rebuilding from run summaries: %s",
            feedback_output_path,
            exc,
        )
        return []


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
    if (
        use_run_index
        and processed_runs
        and feedback_run_index_is_current(
            feedback_output_path,
            runs_root,
        )
    ):
        return []
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
        else _load_rebuildable_feedback_results(
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
    (
        attempted_keys,
        template_stats,
        field_feedback,
        global_failed_check_counts,
    ) = _derive_historical_feedback_state(feedback_results)
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
    (
        attempted_keys,
        template_stats,
        field_feedback,
        global_failed_check_counts,
    ) = _derive_historical_feedback_state(feedback_results)
    return replace(
        state,
        existing_results=existing_results,
        feedback_results=feedback_results,
        attempted_keys=attempted_keys,
        template_stats=template_stats,
        field_feedback=field_feedback,
        global_failed_check_counts=global_failed_check_counts,
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
    if stage == get_static_config().feedback_stage_resimulate:
        return policy.feedback_loop_policy.resimulate.settings_variant_budget
    return policy.feedback_loop_policy.generate.settings_variant_budget
