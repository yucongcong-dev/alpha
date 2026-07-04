"""
字段缓存管理模块

本模块负责管理数据字段的缓存和加载，包括字段元数据的缓存、
首次全量拉取以及从 API 获取字段等功能。字段缓存可以减少
API 调用次数，提高运行效率。

模块内容：
    - load_fields_cache(): 加载字段缓存
    - save_fields_cache(): 保存字段缓存
    - fetch_fields_with_cache(): 根据缓存状态获取字段
    - choose_field_name() (→ utils.helpers): 解析标准字段名
    - choose_field_type() (→ utils.helpers): 标准化字段类型
"""

from __future__ import annotations

from collections.abc import Sequence
import json
import logging
import os
import time
from typing import Any, Protocol

from ..config.constants import FIELDS_CACHE_TTL_HOURS, SENTINEL_UNKNOWN
from ..io.common import atomic_write_json
from ..models.runtime import FieldFetchOptions, TemplateField

logger = logging.getLogger(__name__)


def choose_field_name(field: dict[str, Any] | TemplateField) -> str:
    if isinstance(field, TemplateField):
        return field.field_name
    for key in ("id", "name", "mnemonic", "field"):
        value = field.get(key)
        if value is not None and value != "":
            return str(value)
    return "None"


def choose_field_type(field: dict[str, Any] | TemplateField) -> str:
    if isinstance(field, TemplateField):
        return field.field_type
    for key in ("type", "fieldType", "category"):
        value = field.get(key)
        if value is not None and value != "":
            return str(value).upper()
    return str(SENTINEL_UNKNOWN).upper()


class DatasetFieldClient(Protocol):
    """字段拉取客户端最小协议。"""

    def fetch_dataset_fields(
        self,
        dataset_id: str,
        *,
        limit: int,
        offset: int,
        page_size: int,
        region: str,
        universe: str,
        instrument_type: str,
        delay: int,
    ) -> list[dict[str, object]]: ...


def load_fields_cache(
    path: str,
    *,
    dataset_id: str,
    region: str,
    universe: str,
    instrument_type: str,
    delay: int,
    cache_ttl_hours: int = FIELDS_CACHE_TTL_HOURS,
) -> list[TemplateField]:
    """
    仅在数据集上下文完全匹配且缓存未过期时加载字段缓存。

    从缓存文件加载字段元数据，但只有在缓存的作用域
    （数据集 ID、地区、宇宙、工具类型、延迟）与当前
    请求的参数完全匹配，且缓存未超过 TTL 时才返回缓存数据。

    Args:
        path (str): 缓存文件的路径。
        dataset_id (str): 数据集 ID。
        region (str): 地区代码。
        universe (str): 宇宙代码。
        instrument_type (str): 工具类型。
        delay (int): 延迟天数。
        cache_ttl_hours (int): 缓存有效期（小时），超过后视为过期重新拉取。

    Returns:
        list[TemplateField]: 缓存的字段列表。如果文件不存在、
            格式错误、上下文不匹配或缓存过期，返回空列表。

    Note:
        缓存文件包含 cache_key 和 cached_at 字段，分别用于
        验证缓存作用域和检查过期时间。
    """
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []

    # --- TTL 过期检查 ---
    cached_at = payload.get("cached_at")
    if isinstance(cached_at, (int, float)) and cache_ttl_hours > 0:
        age_seconds = time.time() - float(cached_at)
        if age_seconds > cache_ttl_hours * 3600:
            logger.info(
                "[cache] 缓存已过期 (%.1fh > %dh)，将重新拉取字段",
                age_seconds / 3600,
                cache_ttl_hours,
            )
            return []

    cache_key = payload.get("cache_key", {})
    expected_key = {
        "dataset_id": dataset_id,
        "region": region,
        "universe": universe,
        "instrument_type": instrument_type,
        "delay": delay,
    }
    if cache_key != expected_key:
        return []
    rows = payload.get("fields")
    return rows if isinstance(rows, list) else []


def save_fields_cache(
    path: str,
    *,
    dataset_id: str,
    region: str,
    universe: str,
    instrument_type: str,
    delay: int,
    fields: Sequence[TemplateField],
) -> None:
    """
    保存字段元数据及其缓存作用域键，包含缓存时间戳用于 TTL 检查。

    将获取的字段元数据持久化到缓存文件，同时保存缓存的作用域
    信息和缓存时间戳，以便后续加载时验证缓存的适用性和新鲜度。

    Args:
        path (str): 缓存文件的路径。如果为空，不执行任何操作。
        dataset_id (str): 数据集 ID。
        region (str): 地区代码。
        universe (str): 宇宙代码。
        instrument_type (str): 工具类型。
        delay (int): 延迟天数。
        fields (Sequence[TemplateField]): 要保存的字段列表。

    Note:
        使用原子写入确保文件操作的可靠性。
        缓存文件格式为 JSON，包含 cache_key、cached_at、count 和 fields 四个字段。
    """
    if not path:
        return
    atomic_write_json(
        path,
        {
            "cache_key": {
                "dataset_id": dataset_id,
                "region": region,
                "universe": universe,
                "instrument_type": instrument_type,
                "delay": delay,
            },
            "cached_at": time.time(),
            "count": len(fields),
            "fields": [f.to_dict() if hasattr(f, "to_dict") else f for f in fields],
        },
    )


def fetch_fields_with_cache(
    client: DatasetFieldClient,
    options: FieldFetchOptions,
    fields_cache_file: str,
    cached_fields: Sequence[TemplateField],
) -> list[TemplateField]:
    """
    根据缓存状态获取字段；首次默认拉取并缓存当前上下文下的全量字段。

    此函数实现了简化后的字段获取策略：
    - 如果缓存有效且满足当前上下文，直接使用缓存
    - 如果缓存不存在或无效，首次拉取当前上下文下的全量字段并缓存

    Args:
        client: Brain API 客户端实例，需要实现 fetch_dataset_fields 方法。
        options: 字段拉取所需的窄配置对象。
        fields_cache_file: 字段缓存文件路径。
        cached_fields (Sequence[Dict[str, Any]]): 当前缓存的字段列表。

    Returns:
        List[Dict[str, Any]]: 当前上下文下的完整字段列表。

    Example:
        >>> fields = fetch_fields_with_cache(
        ...     client=brain_client,
        ...     options=options,
        ...     fields_cache_file="/path/to/cache.json",
        ...     cached_fields=[{"id": "sales"}],
        ... )
        >>> print(len(fields)) >= 100
        True

    Note:
        此函数会自动保存更新后的缓存文件，并保持缓存为全量字段列表。
        使用重试机制处理临时 API 不稳定性。
    """
    if cached_fields:
        fields = list(cached_fields)
        logger.info("[cache] 从 %s 加载 %d 个字段", os.path.basename(fields_cache_file), len(fields))
        return fields

    logger.info("[cache] 未命中有效缓存，首次拉取当前上下文下的全量字段")

    # Fetching the field list is also wrapped so temporary API instability
    # does not abort the whole batch before it starts.
    fetched_fields = client.fetch_dataset_fields(
        options.dataset_id,
        limit=0,
        offset=0,
        page_size=options.page_size,
        region=options.region,
        universe=options.universe,
        instrument_type=options.instrument_type,
        delay=options.delay,
    )
    fields = [TemplateField.from_dict(f) if isinstance(f, dict) else f for f in fetched_fields]
    save_fields_cache(
        fields_cache_file,
        dataset_id=options.dataset_id,
        region=options.region,
        universe=options.universe,
        instrument_type=options.instrument_type,
        delay=options.delay,
        fields=fields,
    )
    logger.info("[cache] 保存 %d 个字段到 %s", len(fields), os.path.basename(fields_cache_file))
    return fields
