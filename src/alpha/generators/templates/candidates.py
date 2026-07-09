"""
模板候选对象构造工具。

本模块集中处理 TemplateCandidate 的 metadata 补齐、旧三元组兼容转换
和模板规格渲染，避免 expressions.py 同时承担候选对象工厂职责。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ...config import (
    TEMPLATE_STAGE_EVENT_CONDITIONED,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
)
from ...models.domain import TemplateCandidate
from ...models.domain_types import TemplateMetadata
from .classification import classify_expression_family, classify_template_stage
from .metadata import TemplateMetadataMap, _template_key

TemplateSpec = tuple[str, str, int]
"""配置模板规格：(name_template, expression_template, priority)。"""


def _candidate_metadata(
    *,
    family: str = "",
    layer: str = "",
    stage: str = "",
    requires_partner_field: bool | None = None,
) -> dict[str, object]:
    """构造候选模板的运行时元数据。"""
    metadata: dict[str, object] = {}
    if family:
        metadata["family"] = family
    if layer:
        metadata["layer"] = layer
    if stage:
        metadata["stage"] = stage
    if requires_partner_field is not None:
        metadata["requires_partner_field"] = requires_partner_field
    return metadata


def _enrich_candidate_metadata(
    name: str,
    expression: str,
    metadata: TemplateMetadata | None = None,
) -> dict[str, object]:
    """补齐 family/stage/layer 等运行时元数据。"""
    enriched = dict(metadata or {})
    if not enriched.get("family"):
        enriched["family"] = classify_expression_family(name, expression, enriched)
    if not enriched.get("stage"):
        enriched["stage"] = classify_template_stage(name, expression, enriched)
    if not enriched.get("layer"):
        enriched["layer"] = (
            "group"
            if enriched["stage"] == TEMPLATE_STAGE_GROUP_SECOND_ORDER
            else "event"
            if enriched["stage"] == TEMPLATE_STAGE_EVENT_CONDITIONED
            else "first_order"
        )
    return enriched


def _make_template_candidate(
    name: str,
    expression: str,
    priority: int,
    *,
    metadata: TemplateMetadata | None = None,
) -> TemplateCandidate:
    """创建统一模板候选对象。"""
    return TemplateCandidate(
        name=name,
        expression=expression,
        priority=priority,
        metadata=_enrich_candidate_metadata(name, expression, metadata),
    )


def _coerce_template_candidate(
    template: TemplateCandidate | tuple[str, str, int],
    *,
    metadata_by_key: TemplateMetadataMap | None = None,
) -> TemplateCandidate:
    """兼容旧三元组模板输入，统一转换为 TemplateCandidate。"""
    if isinstance(template, TemplateCandidate):
        return template
    name, expression, priority = template
    metadata = (metadata_by_key or {}).get(_template_key(name, expression), {})
    return _make_template_candidate(name, expression, priority, metadata=metadata)


def _render_template_specs(
    specs: Sequence[TemplateSpec],
    *,
    metadata: TemplateMetadata | None = None,
    **placeholders: Any,
) -> list[TemplateCandidate]:
    """将配置中的模板规格渲染为结构化模板候选。"""
    rendered: list[TemplateCandidate] = []
    for name_template, expr_template, priority in specs:
        rendered.append(
            _make_template_candidate(
                name_template.format(**placeholders),
                expr_template.format(**placeholders),
                priority,
                metadata=metadata,
            )
        )
    return rendered
