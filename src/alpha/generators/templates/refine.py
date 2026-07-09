"""
Near-pass 精修模板生成。

本模块围绕已接近提交门槛的候选表达式生成局部变体，用于 stage-3
精修阶段。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import re

from ...config import (
    GROUP_NAME_INDUSTRY,
    GROUP_NAME_SUBINDUSTRY,
    REFINE_PRIORITY_BACKFILL_DELTA,
    REFINE_PRIORITY_BASE,
    REFINE_PRIORITY_DECAY_DELTA,
    REFINE_PRIORITY_STEP,
    REFINE_PRIORITY_SUBINDUSTRY_DELTA,
    REFINE_PRIORITY_TRADE_WHEN_DELTA,
    REFINE_PRIORITY_TSRANK_DELTA,
    TEMPLATE_STAGE_EVENT_CONDITIONED,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
    DatasetExpressionPolicy,
)
from ...models.domain import NearPassCandidate, TemplateCandidate
from ...models.domain_types import TemplateMetadata
from .candidates import _candidate_metadata, _make_template_candidate
from .variation_common import is_blacklisted_template as _is_blacklisted_template



def _make_window_replacer(replacement: int) -> Callable[[re.Match[str]], str]:
    """构建时间窗替换回调，显式绑定 replacement 避免循环闭包问题。"""
    def replacer(m: re.Match[str]) -> str:
        return f"{m.group(1)}{replacement}{m.group(3)}"

    return replacer


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
            _make_window_replacer(target),
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
    seen_names: set[str] = set()
    seen_expressions: set[str] = set()

    def add_candidate(
        name: str,
        expression: str,
        priority: int,
        *,
        family: str = "",
        stage: str = "",
        layer: str = "",
        extra_metadata: TemplateMetadata | None = None,
    ) -> None:
        if name in seen_names or expression in seen_expressions:
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
        seen_names.add(name)
        seen_expressions.add(expression)
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
        base_priority = REFINE_PRIORITY_BASE - (index - 1) * REFINE_PRIORITY_STEP
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
        if GROUP_NAME_SUBINDUSTRY in lower_expr:
            add_candidate(
                f"refine_industry_{index}_{candidate.template_name}",
                re.sub(rf"\b{GROUP_NAME_SUBINDUSTRY}\b", GROUP_NAME_INDUSTRY, candidate.expression, count=1),
                base_priority + REFINE_PRIORITY_SUBINDUSTRY_DELTA,
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
                base_priority + REFINE_PRIORITY_TSRANK_DELTA,
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
                base_priority + REFINE_PRIORITY_BACKFILL_DELTA,
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
                base_priority + REFINE_PRIORITY_TRADE_WHEN_DELTA,
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
                base_priority + REFINE_PRIORITY_DECAY_DELTA,
                family="neutralize_decay",
                stage=stage,
                layer=layer,
                extra_metadata={
                    "refine_failed_checks": list(candidate.failed_checks),
                    "refine_score": candidate.score,
                },
            )

    return templates
