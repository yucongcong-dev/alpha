"""Field loading and diagnostics for live bootstrap."""

from __future__ import annotations

import logging

from ..api.client import BrainClient
from ..models.domain import TemplateField
from ..models.runtime_options import FieldFetchOptions, FieldSelectionOptions
from .bootstrap_fields import resolve_field_selection
from .bootstrap_types import BootstrapPaths, FieldLoadingServices

logger = logging.getLogger(__name__)


def log_field_selection_stats(
    *,
    dataset_id: str,
    selection_options: FieldSelectionOptions,
    field_stats: dict[str, int],
    fields: list[TemplateField],
) -> None:
    """Emit field-filtering and ranking diagnostics."""
    top_fields_by_feedback, offset, limit = resolve_field_selection(selection_options)
    if field_stats["prefiltered_count"] > 0:
        logger.info(
            "[filter] 排序前因 include/exclude 规则过滤 %d 个字段",
            field_stats["prefiltered_count"],
        )
    metadata_filtered_count = (
        field_stats["low_coverage_count"]
        + field_stats["low_date_coverage_count"]
        + field_stats["low_alpha_count"]
        + field_stats["low_user_count"]
        + field_stats.get("high_alpha_count", 0)
        + field_stats.get("high_user_count", 0)
    )
    if metadata_filtered_count > 0:
        logger.info(
            "[filter] 排序前因官网字段指标过滤 %d 个字段 (coverage=%d, dateCoverage=%d, alphaCount=%d, userCount=%d, crowdedAlpha=%d, crowdedUser=%d)",
            metadata_filtered_count,
            field_stats["low_coverage_count"],
            field_stats["low_date_coverage_count"],
            field_stats["low_alpha_count"],
            field_stats["low_user_count"],
            field_stats.get("high_alpha_count", 0),
            field_stats.get("high_user_count", 0),
        )
    metadata_unknown_count = (
        field_stats.get("unknown_coverage_count", 0)
        + field_stats.get("unknown_date_coverage_count", 0)
        + field_stats.get("unknown_alpha_count", 0)
        + field_stats.get("unknown_user_count", 0)
    )
    if metadata_unknown_count > 0:
        logger.warning(
            "[filter] 官网字段指标缺失 %d 项，将保留字段但降低排序分数 "
            "(coverage=%d, dateCoverage=%d, alphaCount=%d, userCount=%d)",
            metadata_unknown_count,
            field_stats.get("unknown_coverage_count", 0),
            field_stats.get("unknown_date_coverage_count", 0),
            field_stats.get("unknown_alpha_count", 0),
            field_stats.get("unknown_user_count", 0),
        )
    if not fields:
        logger.error("[error] 数据集 %s 在字段过滤后没有可运行字段", dataset_id)
        return
    if top_fields_by_feedback > 0:
        logger.info("[focus] 限制运行到按反馈排序的前 %d 个字段", len(fields))
    logger.info(
        "[data] 当前上下文缓存共 %d 个字段，过滤后共 %d 个字段，优先级排序后共 %d 个字段，本次按 offset=%d limit=%d 取 %d 个字段",
        field_stats["cached_field_count"],
        field_stats["filtered_field_count"],
        field_stats["ranked_field_count"],
        offset,
        limit,
        len(fields),
    )
    logger.info("[data] 从数据集 %s 获取 %d 个字段", dataset_id, len(fields))


def load_bootstrap_fields(
    *,
    dataset_id: str,
    bootstrap_client: BrainClient,
    paths: BootstrapPaths,
    field_fetch_options: FieldFetchOptions,
    services: FieldLoadingServices,
) -> list[TemplateField]:
    """Load cached fields and refresh from the upstream source when needed."""
    cached_fields = services.load_fields_cache(
        paths.fields_cache_file,
        dataset_id=dataset_id,
        region=field_fetch_options.region,
        universe=field_fetch_options.universe,
        instrument_type=field_fetch_options.instrument_type,
        delay=field_fetch_options.delay,
    )
    return services.fetch_fields_with_cache(
        bootstrap_client,
        field_fetch_options,
        paths.fields_cache_file,
        cached_fields,
    )
