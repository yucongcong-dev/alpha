"""Historical feedback state and near-pass candidate selection."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    FEEDBACK_STAGE_PRUNE,
    FEEDBACK_STAGE_RESIMULATE,
    NEARPASS_DEFAULT_LIMIT,
    NEARPASS_PENALTY_CONCENTRATED_WEIGHT,
    NEARPASS_PENALTY_CONCENTRATED_WEIGHT_EXTRA,
    NEARPASS_PENALTY_CONCENTRATED_WEIGHT_GAP_THRESHOLD,
    NEARPASS_PENALTY_LOW_SUB_UNIVERSE_SHARPE,
    NEARPASS_PENALTY_LOW_TURNOVER,
)
from ..config.models import DatasetExpressionPolicy
from ..models.domain import FailedCheck, FieldFeedbackSummary, FieldTestResult, NearPassCandidate
from ..models.runtime_protocols import StopAfterSubmittableArgs
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from ..runtime import HistoricalRunState
from .failed_checks import failed_check_gap, score_failed_checks
from .feedback_stats import compile_field_feedback, compile_global_failed_check_counts
from .field_stats import current_submittable_count
from .result_identity import attempted_template_keys
from .results_loader import load_existing_results
from .template_registry_rules import (
    compile_template_family_registry,
    merge_registry_recommendations_into_template_stats,
)
from .template_registry_store import (
    build_template_registry_index,
    load_registry_overrides,
    load_persisted_template_registry,
)
from .template_stats import compile_template_stats


def build_historical_run_state(output_path: str, feedback_output_path: str) -> HistoricalRunState:
    """加载历史结果并构建续跑与反馈所需的状态对象。"""
    existing_results = load_existing_results(output_path)
    attempted_keys = attempted_template_keys(existing_results)
    template_stats = compile_template_stats(existing_results)
    persisted_template_registry_rows = load_persisted_template_registry(output_path)
    registry_overrides = load_registry_overrides(output_path)
    template_stats = merge_registry_recommendations_into_template_stats(
        template_stats,
        persisted_template_registry_rows,
    )
    template_registry = build_template_registry_index(persisted_template_registry_rows)
    template_family_registry = compile_template_family_registry(template_stats)
    feedback_results = (
        existing_results
        if feedback_output_path == output_path
        else load_existing_results(feedback_output_path)
    )
    field_feedback = compile_field_feedback(feedback_results)
    global_failed_check_counts = compile_global_failed_check_counts(feedback_results)
    return HistoricalRunState(
        existing_results=existing_results,
        attempted_keys=attempted_keys,
        template_stats=template_stats,
        template_registry=template_registry,
        template_family_registry=template_family_registry,
        template_registry_overrides=registry_overrides,
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
    if stage == FEEDBACK_STAGE_RESIMULATE:
        return policy.feedback_loop_policy.resimulate.settings_variant_budget
    if stage == FEEDBACK_STAGE_PRUNE:
        return policy.feedback_loop_policy.prune.settings_variant_budget
    return policy.feedback_loop_policy.generate.settings_variant_budget


def _nearpass_penalty(failed_checks: Sequence[FailedCheck] | None) -> float:
    """对明显不适合继续 refine 的失败模式施加惩罚。"""
    penalty = 0.0
    for check in failed_checks or []:
        name = str(check.get("name", "")).strip()
        gap = failed_check_gap(check)
        if name == CHECK_CONCENTRATED_WEIGHT:
            penalty += NEARPASS_PENALTY_CONCENTRATED_WEIGHT
            if isinstance(gap, (int, float)) and gap >= NEARPASS_PENALTY_CONCENTRATED_WEIGHT_GAP_THRESHOLD:
                penalty += NEARPASS_PENALTY_CONCENTRATED_WEIGHT_EXTRA
        elif name == CHECK_LOW_TURNOVER:
            penalty += NEARPASS_PENALTY_LOW_TURNOVER
        elif name == CHECK_LOW_SUB_UNIVERSE_SHARPE:
            penalty += NEARPASS_PENALTY_LOW_SUB_UNIVERSE_SHARPE
    return penalty


def select_nearpass_candidates(
    field_id: str,
    prior_results: Sequence[FieldTestResult],
    *,
    dataset_id: str = "",
    expression_policy: DatasetExpressionPolicy | None = None,
    limit: int = NEARPASS_DEFAULT_LIMIT,
) -> list[NearPassCandidate]:
    """为单个字段挑选最值得进入 stage-3 refine 的近门槛候选。"""
    if limit <= 0:
        return []
    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    min_score = policy.feedback_loop_policy.resimulate.min_best_score
    best_by_key: dict[tuple[str, str], NearPassCandidate] = {}
    rank_by_key: dict[tuple[str, str], tuple[float, int, str]] = {}
    for result in prior_results:
        if result.field_id != field_id or result.submittable:
            continue
        if result.status != "simulated" or not result.failed_checks:
            continue
        score = score_failed_checks(result.failed_checks)
        if score < min_score:
            continue
        key = (result.template_name, result.expression)
        candidate = NearPassCandidate(
            field_id=result.field_id,
            field_name=result.field_name,
            template_name=result.template_name,
            expression=result.expression,
            template_family=result.template_family,
            template_stage=result.template_stage,
            score=score,
            failed_checks=list(result.failed_checks),
        )
        rank = (
            score - _nearpass_penalty(result.failed_checks),
            -len(result.failed_checks or []),
            result.template_name,
        )
        current_rank = rank_by_key.get(key)
        if current_rank is None or rank > current_rank:
            best_by_key[key] = candidate
            rank_by_key[key] = rank
    ordered_keys = sorted(rank_by_key, key=lambda k: rank_by_key[k], reverse=True)
    return [best_by_key[key] for key in ordered_keys[:limit]]


def should_stop_after_submittable(
    args: StopAfterSubmittableArgs,
    results: Sequence[FieldTestResult],
) -> bool:
    """判断当前运行是否已达到要求的可提交数量上限。"""
    stop_threshold = cast(int, args.stop_after_submittable)
    if stop_threshold <= 0:
        return False
    current_count = current_submittable_count(results)
    return bool(current_count >= stop_threshold)
