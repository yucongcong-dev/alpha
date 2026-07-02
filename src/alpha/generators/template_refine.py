"""
Near-pass 精修模板生成。

本模块围绕已接近提交门槛的候选表达式生成局部变体，用于 stage-3
精修阶段。
"""

from __future__ import annotations

from collections.abc import Sequence
import re
from typing import Any

from ..config import (
    TEMPLATE_STAGE_EVENT_CONDITIONED,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
    DatasetExpressionPolicy,
)
from ..models.base import NearPassCandidate, TemplateCandidate
from ..policy.template_blacklist import blacklist_match_reason as _policy_blacklist_match_reason
from .template_candidates import _candidate_metadata, _make_template_candidate
from .template_classification import classify_expression_family, classify_template_stage


def _is_blacklisted_template(
    template_name: str,
    expression: str = "",
    *,
    template_metadata: dict[str, Any] | None = None,
    dataset_id: str = "",
    policy: DatasetExpressionPolicy | None = None,
) -> bool:
    """检查精修模板是否被当前策略或数据集黑名单拦截。"""
    effective_dataset_id = policy.dataset_id if policy is not None else dataset_id
    protected_templates = policy.protected_templates if policy is not None else set()
    blocked_name_substrings = (
        policy.blacklisted_template_name_substrings if policy is not None else ()
    )
    current_family = classify_expression_family(template_name, expression, template_metadata)
    current_stage = classify_template_stage(template_name, expression, template_metadata)
    return (
        _policy_blacklist_match_reason(
            template_name,
            expression,
            dataset_id=effective_dataset_id,
            current_family=current_family,
            current_stage=current_stage,
            has_runtime_context=bool(template_metadata or expression),
            protected_templates=set(protected_templates),
            blocked_name_substrings=tuple(blocked_name_substrings),
        )
        is not None
    )


def _replace_window_variants(
    expression: str,
    pattern: str,
    replacements: Sequence[tuple[str, int]],
    *,
    limit: int = 1,
) -> list[tuple[str, str]]:
    """对表达式里的时间窗做有限个局部替换。"""
    compiled = re.compile(pattern)
    matched = compiled.search(expression)
    if not matched:
        return []
    variants: list[tuple[str, str]] = []
    seen: set[str] = set()
    for suffix, target in replacements:
        candidate = compiled.sub(
            lambda m: f"{m.group(1)}{target}{m.group(3)}",
            expression,
            count=limit,
        )
        if candidate == expression or candidate in seen:
            continue
        seen.add(candidate)
        variants.append((suffix, candidate))
    return variants


def build_refine_templates(
    field_name: str,
    nearpass_candidates: Sequence[NearPassCandidate],
    *,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> list[TemplateCandidate]:
    """围绕近门槛候选构建 stage-3 精修模板。"""
    templates: list[TemplateCandidate] = []
    seen: set[tuple[str, str]] = set()

    def add_candidate(
        name: str,
        expression: str,
        priority: int,
        *,
        family: str = "",
        stage: str = "",
        layer: str = "",
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        key = (name, expression)
        if key in seen:
            return
        metadata = {
            **_candidate_metadata(
                family=family,
                stage=stage,
                layer=layer,
            ),
            **(extra_metadata or {}),
        }
        if _is_blacklisted_template(
            name,
            expression,
            template_metadata=metadata or None,
            policy=expression_policy,
        ):
            return
        seen.add(key)
        templates.append(
            _make_template_candidate(
                name,
                expression,
                priority,
                metadata=metadata or None,
            )
        )

    for index, candidate in enumerate(nearpass_candidates, start=1):
        lower_template_name = candidate.template_name.lower()
        if lower_template_name.startswith("refine_"):
            continue
        base_priority = 260 - (index - 1) * 12
        family = candidate.template_family
        stage = candidate.template_stage
        layer = (
            "event"
            if stage == TEMPLATE_STAGE_EVENT_CONDITIONED
            else "group"
            if stage == TEMPLATE_STAGE_GROUP_SECOND_ORDER
            else "first_order"
        )
        add_candidate(
            f"refine_exact_{index}_{candidate.template_name}",
            candidate.expression,
            base_priority,
            family=family,
            stage=stage,
            layer=layer,
            extra_metadata={
                "refine_failed_checks": list(candidate.failed_checks),
                "refine_score": candidate.score,
            },
        )

        lower_expr = candidate.expression.lower()
        if "subindustry" in lower_expr:
            add_candidate(
                f"refine_industry_{index}_{candidate.template_name}",
                re.sub(r"\bsubindustry\b", "industry", candidate.expression, count=1),
                base_priority - 2,
                family=family,
                stage=stage,
                layer=layer,
                extra_metadata={
                    "refine_failed_checks": list(candidate.failed_checks),
                    "refine_score": candidate.score,
                },
            )

        for suffix, expr in _replace_window_variants(
            candidate.expression,
            r"(ts_zscore\(.*,\s*)(60|63|66)(\s*\))",
            (("63", 63), ("126", 126), ("200", 200)),
        ):
            add_candidate(
                f"refine_zscore_{suffix}_{index}_{candidate.template_name}",
                expr,
                base_priority - 3,
                family=family or "group_zscore",
                stage=stage,
                layer=layer,
                extra_metadata={
                    "refine_failed_checks": list(candidate.failed_checks),
                    "refine_score": candidate.score,
                },
            )

        for suffix, expr in _replace_window_variants(
            candidate.expression,
            r"(ts_rank\(.*,\s*)(60|63|126)(\s*\))",
            (("126", 126), ("200", 200)),
        ):
            add_candidate(
                f"refine_tsrank_{suffix}_{index}_{candidate.template_name}",
                expr,
                base_priority - 4,
                family=family or "ts_rank",
                stage=stage,
                layer=layer,
                extra_metadata={
                    "refine_failed_checks": list(candidate.failed_checks),
                    "refine_score": candidate.score,
                },
            )

        for suffix, expr in _replace_window_variants(
            candidate.expression,
            r"(ts_backfill\(.*,\s*)(240|252|504)(\s*\))",
            (("504", 504),),
        ):
            add_candidate(
                f"refine_backfill_{suffix}_{index}_{candidate.template_name}",
                expr,
                base_priority - 5,
                family=family,
                stage=stage,
                layer=layer,
                extra_metadata={
                    "refine_failed_checks": list(candidate.failed_checks),
                    "refine_score": candidate.score,
                },
            )

        if "group_rank(" in lower_expr or "group_neutralize(" in lower_expr:
            add_candidate(
                f"refine_trade_when_volume_{index}_{candidate.template_name}",
                f"trade_when(ts_mean(volume, 10) > ts_mean(volume, 60), {candidate.expression}, -1)",
                base_priority - 6,
                family="event_trade_when",
                stage=TEMPLATE_STAGE_EVENT_CONDITIONED,
                layer="event",
                extra_metadata={
                    "refine_failed_checks": list(candidate.failed_checks),
                    "refine_score": candidate.score,
                },
            )

        if "ts_decay_linear(" not in lower_expr:
            add_candidate(
                f"refine_decay_{index}_{candidate.template_name}",
                f"ts_decay_linear({candidate.expression}, 6)",
                base_priority - 7,
                family="neutralize_decay",
                stage=stage,
                layer=layer,
                extra_metadata={
                    "refine_failed_checks": list(candidate.failed_checks),
                    "refine_score": candidate.score,
                },
            )

    return templates
