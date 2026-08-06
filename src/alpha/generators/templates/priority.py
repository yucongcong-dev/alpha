"""
模板优先级与剪枝策略。

本模块负责静态相似度惩罚和 family 级数量限制。模板的主要顺序由
template.json 中的显式 priority 决定。
"""

from __future__ import annotations

from collections.abc import Sequence

from ...config._constants_templates import (
    SIMILARITY_PENALTY_OFFSET_GROUP_RATIO_LEVEL,
    SIMILARITY_PENALTY_OFFSET_LEGACY_GROUP_LEVEL,
    SIMILARITY_PENALTY_OFFSET_LEGACY_LEVEL,
    SIMILARITY_PENALTY_OFFSET_LEGACY_NEG_RATIO,
    SIMILARITY_PENALTY_OFFSET_LEGACY_RATIO,
)
from ...models.domain import TemplateCandidate
from .candidates import _coerce_template_candidate, _make_template_candidate
from .classification import classify_expression_family
from .metadata import TemplateMetadataMap

_SIMILARITY_PENALTY_OFFSETS: dict[str, int] = {
    "legacy_level": SIMILARITY_PENALTY_OFFSET_LEGACY_LEVEL,
    "legacy_group_level": SIMILARITY_PENALTY_OFFSET_LEGACY_GROUP_LEVEL,
    "legacy_ratio": SIMILARITY_PENALTY_OFFSET_LEGACY_RATIO,
    "legacy_neg_ratio": SIMILARITY_PENALTY_OFFSET_LEGACY_NEG_RATIO,
    "group_ratio_level": SIMILARITY_PENALTY_OFFSET_GROUP_RATIO_LEVEL,
}
"""家族名到相似度惩罚减免值的映射。"""


def apply_similarity_penalty(
    templates: Sequence[TemplateCandidate | tuple[str, str, int]],
    legacy_similarity_penalty: int,
    *,
    metadata_by_key: TemplateMetadataMap | None = None,
) -> list[TemplateCandidate]:
    """
    对 legacy 形态模板施加相似度惩罚，让多样化候选优先运行。

    Args:
        templates: 模板候选列表。
        legacy_similarity_penalty: legacy 家族基础惩罚分数。
        metadata_by_key: 可选模板元数据索引。

    Returns:
        list[TemplateCandidate]: 应用惩罚后的模板候选。
    """
    penalized: list[TemplateCandidate] = []
    for raw_template in templates:
        template = _coerce_template_candidate(raw_template, metadata_by_key=metadata_by_key)
        family = classify_expression_family(
            template.name,
            template.expression,
            template.metadata,
        )
        offset = _SIMILARITY_PENALTY_OFFSETS.get(family)
        penalty = max(legacy_similarity_penalty - offset, 0) if offset is not None else 0
        penalized.append(
            _make_template_candidate(
                template.name,
                template.expression,
                template.priority - penalty,
                metadata=template.metadata,
            )
        )
    return penalized


def cap_templates_per_family(
    templates: Sequence[TemplateCandidate | tuple[str, str, int]],
    max_templates_per_family: int,
    *,
    metadata_by_key: TemplateMetadataMap | None = None,
) -> list[TemplateCandidate]:
    """
    限制每个结构家族仅保留前 N 个候选模板。

    Args:
        templates: 已排序的模板候选列表。
        max_templates_per_family: 每个家族的模板数量上限，<=0 表示不限制。
        metadata_by_key: 可选模板元数据索引。

    Returns:
        list[TemplateCandidate]: family 限制后的模板候选。
    """
    if max_templates_per_family <= 0:
        return [
            _coerce_template_candidate(template, metadata_by_key=metadata_by_key)
            for template in templates
        ]
    kept: list[TemplateCandidate] = []
    family_counts: dict[str, int] = {}
    for raw_template in templates:
        template = _coerce_template_candidate(raw_template, metadata_by_key=metadata_by_key)
        family = classify_expression_family(
            template.name,
            template.expression,
            template.metadata,
        )
        used = family_counts.get(family, 0)
        if used >= max_templates_per_family:
            continue
        kept.append(template)
        family_counts[family] = used + 1
    return kept
