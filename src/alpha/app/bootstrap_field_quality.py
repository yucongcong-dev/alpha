"""Field metadata, runtime tags, and quality-filter helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config.constants import SENTINEL_UNKNOWN
from ..config.models import DatasetExpressionPolicy
from ..generators.fields import choose_field_name
from ..models.domain import TemplateField
from ..utils.helpers import first_non_empty, is_event_field_name


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_runtime_field_tags(
    field_name: str,
    *,
    dataset_id: str,
    coverage: float,
) -> tuple[str, ...]:
    dataset_key = dataset_id.strip().lower()
    tags: list[str] = []
    if dataset_key == "model16":
        if field_name.startswith("fscore_bfl_"):
            tags.extend(["model16_sparse_bfl", "model16_sparse_score", "model16_fscore_family"])
        elif field_name.startswith("fscore_"):
            tags.extend(["model16_sparse_fscore", "model16_sparse_score", "model16_fscore_family"])
        elif field_name.endswith("_derivative"):
            tags.extend(["model16_dense_derivative", "model16_dense_score"])
    if coverage >= 0.95:
        tags.append("high_coverage")
    elif coverage <= 0.50:
        tags.append("sparse_coverage")
    return tuple(tags)


@dataclass(frozen=True)
class FieldMetadataValues:
    coverage: float | None
    date_coverage: float | None
    alpha_count: int | None
    user_count: int | None

    @property
    def coverage_for_tags(self) -> float:
        return self.coverage or 0.0


@dataclass(frozen=True)
class FieldQualityThresholds:
    min_coverage: float
    min_date_coverage: float
    min_alpha_count: int
    min_user_count: int
    max_alpha_count: int
    max_user_count: int


def _attach_runtime_metadata(
    field: TemplateField,
    *,
    runtime_field_tags: tuple[str, ...],
) -> TemplateField:
    if not runtime_field_tags:
        return field
    metadata = dict(field.metadata)
    metadata["runtime_field_tags"] = list(runtime_field_tags)
    return TemplateField(
        field_id=field.field_id,
        field_name=field.field_name,
        field_type=field.field_type,
        metadata=metadata,
    )


def field_identity(field: TemplateField | dict[str, Any]) -> tuple[str, str]:
    return (
        str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
        choose_field_name(field),
    )


def field_with_runtime_metadata(
    field: TemplateField | dict[str, Any],
    *,
    expression_policy: DatasetExpressionPolicy,
    coverage: float,
) -> TemplateField | dict[str, Any]:
    field_name = choose_field_name(field)
    runtime_field_tags = _infer_runtime_field_tags(
        field_name,
        dataset_id=expression_policy.dataset_id,
        coverage=coverage,
    )
    if isinstance(field, TemplateField):
        return _attach_runtime_metadata(field, runtime_field_tags=runtime_field_tags)
    field_copy = dict(field)
    if runtime_field_tags:
        field_copy["runtime_field_tags"] = list(runtime_field_tags)
    return field_copy


def base_field_stats(cached_field_count: int) -> dict[str, int]:
    return {
        "cached_field_count": cached_field_count,
        "filtered_field_count": 0,
        "ranked_field_count": 0,
        "prefiltered_count": 0,
        "low_coverage_count": 0,
        "low_date_coverage_count": 0,
        "low_alpha_count": 0,
        "low_user_count": 0,
        "high_alpha_count": 0,
        "high_user_count": 0,
        "unknown_coverage_count": 0,
        "unknown_date_coverage_count": 0,
        "unknown_alpha_count": 0,
        "unknown_user_count": 0,
        "selected_family_count": 0,
        "selected_unexplored_count": 0,
    }


def metadata_values(field: TemplateField | dict[str, Any]) -> FieldMetadataValues:
    return FieldMetadataValues(
        coverage=_optional_float(field.get("coverage")),
        date_coverage=_optional_float(field.get("dateCoverage")),
        alpha_count=_optional_int(field.get("alphaCount")),
        user_count=_optional_int(field.get("userCount")),
    )


def quality_thresholds(
    field_name: str,
    expression_policy: DatasetExpressionPolicy,
) -> FieldQualityThresholds:
    is_event_field = is_event_field_name(field_name, expression_policy.event_field_prefixes)
    return FieldQualityThresholds(
        min_coverage=(
            expression_policy.event_field_min_coverage
            if is_event_field and expression_policy.event_field_min_coverage > 0
            else expression_policy.field_min_coverage
        ),
        min_date_coverage=(
            expression_policy.event_field_min_date_coverage
            if is_event_field and expression_policy.event_field_min_date_coverage > 0
            else expression_policy.field_min_date_coverage
        ),
        min_alpha_count=(
            expression_policy.event_field_min_alpha_count
            if is_event_field and expression_policy.event_field_min_alpha_count > 0
            else expression_policy.field_min_alpha_count
        ),
        min_user_count=(
            expression_policy.event_field_min_user_count
            if is_event_field and expression_policy.event_field_min_user_count > 0
            else expression_policy.field_min_user_count
        ),
        max_alpha_count=expression_policy.field_max_alpha_count,
        max_user_count=expression_policy.field_max_user_count,
    )


def passes_quality_filters(
    values: FieldMetadataValues,
    thresholds: FieldQualityThresholds,
    stats: dict[str, int],
) -> bool:
    if values.coverage is None:
        stats["unknown_coverage_count"] += 1
    elif values.coverage < thresholds.min_coverage:
        stats["low_coverage_count"] += 1
        return False
    if values.date_coverage is None:
        stats["unknown_date_coverage_count"] += 1
    elif values.date_coverage < thresholds.min_date_coverage:
        stats["low_date_coverage_count"] += 1
        return False
    if values.alpha_count is None:
        stats["unknown_alpha_count"] += 1
    elif values.alpha_count < thresholds.min_alpha_count:
        stats["low_alpha_count"] += 1
        return False
    if values.user_count is None:
        stats["unknown_user_count"] += 1
    elif values.user_count < thresholds.min_user_count:
        stats["low_user_count"] += 1
        return False
    if (
        thresholds.max_alpha_count > 0
        and values.alpha_count is not None
        and values.alpha_count > thresholds.max_alpha_count
    ):
        stats["high_alpha_count"] += 1
        return False
    if (
        thresholds.max_user_count > 0
        and values.user_count is not None
        and values.user_count > thresholds.max_user_count
    ):
        stats["high_user_count"] += 1
        return False
    return True
