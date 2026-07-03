"""
Expression generator compatibility facade.

表达式生成兼容门面。

Historically, callers imported classification helpers, priority utilities,
variation builders, and candidate construction from this module. The concrete
implementation now lives in focused modules under ``alpha.generators`` and
``alpha.generators.templates``; this file keeps the old import path stable.

历史上调用方会从本模块导入分类、优先级、变体构建和候选构建函数。现在真实
实现已经拆到更聚焦的模块中；本文件只负责保持旧导入路径兼容。

.. deprecated:: 1.0.0
    This module is a compatibility facade. Import from specific modules instead:
    ``alpha.generators.expression_builder``, ``alpha.generators.matrix_templates``,
    ``alpha.generators.ratio_templates``, ``alpha.generators.templates.classification``,
    ``alpha.generators.templates.metadata``, ``alpha.generators.templates.priority``,
    ``alpha.generators.templates.refine``, ``alpha.generators.templates.variations``.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "alpha.generators.expressions is deprecated. Import from specific modules instead: "
    "alpha.generators.expression_builder, alpha.generators.matrix_templates, "
    "alpha.generators.ratio_templates, alpha.generators.templates.classification, "
    "alpha.generators.templates.metadata, alpha.generators.templates.priority, "
    "alpha.generators.templates.refine, alpha.generators.templates.variations.",
    DeprecationWarning,
    stacklevel=2,
)

from ..policy.template_blacklist import (
    invalidate_blacklist_cache as invalidate_blacklist_cache,
)
from .expression_builder import (
    _blacklist_match_reason,
    _event_template_allowed,
    _is_blacklisted_template,
    _is_event_field,
    _load_default_avoid_rules,
    _policy_template_priority_adjustment,
    build_expression_candidates,
    limit_templates,
    sort_templates_by_priority,
)
from .ratio_templates import build_high_conviction_ratio_templates
from .templates.classification import (
    classify_expression_family,
    classify_template_stage,
    is_legacy_family,
)
from .templates.metadata import (
    TemplateMetadataMap,
    build_template_metadata_index,
    get_template_metadata,
)
from .templates.partner_fields import (
    discover_partner_fields,
    score_partner_candidate,
    tokenize_field_name,
)
from .templates.priority import (
    adaptive_template_priority_adjustment,
    apply_adaptive_priority,
    apply_similarity_penalty,
    cap_templates_per_family,
    dominant_failed_check_names,
    merge_failed_check_counts,
)
from .templates.refine import build_refine_templates
from .templates.variations import (
    build_bucket_group_templates,
    build_feedback_mutations,
    build_historical_reuse_templates,
    build_trade_when_templates,
    invert_expression,
)

__all__ = [
    "TemplateMetadataMap",
    "_blacklist_match_reason",
    "_event_template_allowed",
    "_is_blacklisted_template",
    "_is_event_field",
    "_load_default_avoid_rules",
    "_policy_template_priority_adjustment",
    "adaptive_template_priority_adjustment",
    "apply_adaptive_priority",
    "apply_similarity_penalty",
    "build_bucket_group_templates",
    "build_expression_candidates",
    "build_feedback_mutations",
    "build_high_conviction_ratio_templates",
    "build_historical_reuse_templates",
    "build_refine_templates",
    "build_template_metadata_index",
    "build_trade_when_templates",
    "cap_templates_per_family",
    "classify_expression_family",
    "classify_template_stage",
    "discover_partner_fields",
    "dominant_failed_check_names",
    "get_template_metadata",
    "invalidate_blacklist_cache",
    "invert_expression",
    "is_legacy_family",
    "limit_templates",
    "merge_failed_check_counts",
    "score_partner_candidate",
    "sort_templates_by_priority",
    "tokenize_field_name",
]
