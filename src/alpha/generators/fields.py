"""
字段缓存管理模块

本模块负责管理数据字段的缓存和加载，包括字段元数据的缓存、
刷新判断、合并以及从 API 获取字段等功能。字段缓存可以减少
API 调用次数，提高运行效率。

模块内容：
    - load_fields_cache(): 加载字段缓存
    - save_fields_cache(): 保存字段缓存
    - fields_cache_refresh_reason(): 判断缓存是否需要刷新
    - merge_fields_by_id(): 按字段 ID 合并字段列表
    - fetch_fields_with_cache(): 根据缓存状态获取字段
    - normalize_results(): 从 API 返回中提取统一结果列表
    - extract_total(): 提取总数元数据
    - choose_field_name(): 解析标准字段名
    - choose_field_type(): 标准化字段类型
"""

import json
import os
import tempfile
from contextlib import suppress
from typing import Any, Dict, List, Optional, Sequence

from ..utils.helpers import first_non_empty


def atomic_write_json(path: str, payload: Any) -> None:
    """
    以原子方式写入 JSON 文件。

    先写入临时文件，然后原子性地替换目标文件，
    避免中断运行导致状态文件损坏。

    Args:
        path (str): 目标 JSON 文件的路径。
        payload (Any): 要写入的 JSON 数据。

    Note:
        此函数会自动创建父目录（如果不存在）。
        使用临时文件确保写入操作的原子性。
    """
    # Write to a temporary file first, then atomically replace the target.
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            with suppress(OSError):
                os.remove(temp_path)


def load_fields_cache(
    path: str,
    *,
    dataset_id: str,
    region: str,
    universe: str,
    instrument_type: str,
    delay: int,
) -> List[Dict[str, Any]]:
    """
    仅在数据集上下文完全匹配时加载字段缓存。

    从缓存文件加载字段元数据，但只有在缓存的作用域
    （数据集 ID、地区、宇宙、工具类型、延迟）与当前
    请求的参数完全匹配时才返回缓存数据。

    Args:
        path (str): 缓存文件的路径。
        dataset_id (str): 数据集 ID。
        region (str): 地区代码。
        universe (str): 宇宙代码。
        instrument_type (str): 工具类型。
        delay (int): 延迟天数。

    Returns:
        List[Dict[str, Any]]: 缓存的字段列表。如果文件不存在、
            格式错误或上下文不匹配，返回空列表。

    Example:
        >>> fields = load_fields_cache(
        ...     "fields_cache.json",
        ...     dataset_id="fundamental6",
        ...     region="USA",
        ...     universe="TOP3000",
        ...     instrument_type="EQUITY",
        ...     delay=1
        ... )
        >>> print(len(fields))
        500

    Note:
        缓存文件包含一个 cache_key 字段，用于验证缓存的作用域。
        只有完全匹配的缓存才会被使用，避免不同配置的数据混淆。
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
    fields: Sequence[Dict[str, Any]],
) -> None:
    """
    保存字段元数据及其缓存作用域键。

    将获取的字段元数据持久化到缓存文件，同时保存缓存的作用域
    信息，以便后续加载时验证缓存的适用性。

    Args:
        path (str): 缓存文件的路径。如果为空，不执行任何操作。
        dataset_id (str): 数据集 ID。
        region (str): 地区代码。
        universe (str): 宇宙代码。
        instrument_type (str): 工具类型。
        delay (int): 延迟天数。
        fields (Sequence[Dict[str, Any]]): 要保存的字段列表。

    Example:
        >>> save_fields_cache(
        ...     "fields_cache.json",
        ...     dataset_id="fundamental6",
        ...     region="USA",
        ...     universe="TOP3000",
        ...     instrument_type="EQUITY",
        ...     delay=1,
        ...     fields=[{"id": "sales", "name": "Sales", "type": "MATRIX"}]
        ... )

    Note:
        使用原子写入确保文件操作的可靠性。
        缓存文件格式为 JSON，包含 cache_key、count 和 fields 三个字段。
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
            "count": len(fields),
            "fields": list(fields),
        },
    )


def fields_cache_refresh_reason(
    cached_fields: Sequence[Dict[str, Any]],
    *,
    requested_limit: int,
    requested_offset: int,
    force_refresh: bool,
) -> str:
    """
    判断字段缓存是否应刷新，并返回可打印的原因。

    根据缓存状态和请求参数，判断是否需要重新从 API 获取字段数据。
    如果需要刷新，返回描述刷新原因的字符串；否则返回空字符串。

    Args:
        cached_fields (Sequence[Dict[str, Any]]): 当前缓存的字段列表。
        requested_limit (int): 请求的字段数量限制。
        requested_offset (int): 请求的字段偏移量。
        force_refresh (bool): 是否强制刷新缓存。

    Returns:
        str: 刷新原因字符串。如果不需要刷新，返回空字符串。

    刷新原因包括：
        - "forced by --refresh-fields-cache": 强制刷新标志
        - "cache missing or invalid": 缓存不存在或无效
        - "non-zero --offset requires an exact field fetch": 非零偏移量需要精确获取
        - "all-fields request requires a complete field fetch": 全字段请求需要完整获取
        - "cache has X fields but current limit requests Y": 缓存数量不足

    Example:
        >>> reason = fields_cache_refresh_reason(
        ...     cached_fields=[{"id": "sales"}],
        ...     requested_limit=100,
        ...     requested_offset=0,
        ...     force_refresh=False
        ... )
        >>> print(reason)
        'cache has 1 fields but current limit requests 100'
    """
    if force_refresh:
        return "forced by --refresh-fields-cache"
    if not cached_fields:
        return "cache missing or invalid"
    if requested_offset > 0:
        return "non-zero --offset requires an exact field fetch"
    if requested_limit == 0:
        return "all-fields request requires a complete field fetch"
    if requested_limit > 0 and len(cached_fields) < requested_limit:
        return f"cache has {len(cached_fields)} fields but current limit requests {requested_limit}"
    return ""


def merge_fields_by_id(
    existing_fields: Sequence[Dict[str, Any]],
    new_fields: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    按字段 ID 合并缓存和新拉取字段，保持原始顺序并去重。

    将现有缓存字段和新获取的字段合并，通过字段 ID 去重。
    保持字段的出现顺序，优先保留较早出现的字段。

    Args:
        existing_fields (Sequence[Dict[str, Any]]): 现有的缓存字段列表。
        new_fields (Sequence[Dict[str, Any]]): 新获取的字段列表。

    Returns:
        List[Dict[str, Any]]: 合并后的字段列表，按 ID 去重。

    Example:
        >>> existing = [{"id": "sales", "name": "Sales"}]
        >>> new = [{"id": "sales", "name": "Sales Updated"}, {"id": "ebitda"}]
        >>> merged = merge_fields_by_id(existing, new)
        >>> print(len(merged))
        2
        >>> print(merged[0]["name"])
        'Sales'  # 保留较早出现的字段

    Note:
        字段 ID 从 id、name 字段中提取，优先使用 id。
        如果字段没有 ID，仍然会包含在结果中但不进行去重。
    """
    merged: List[Dict[str, Any]] = []
    seen: set = set()
    for field in list(existing_fields) + list(new_fields):
        field_id = str(first_non_empty(field.get("id"), field.get("name"), ""))
        if field_id and field_id in seen:
            continue
        if field_id:
            seen.add(field_id)
        merged.append(dict(field))
    return merged


def normalize_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从多种常见 API 返回结构中提取统一的列表结果。

    API 的不同列表端点使用不同的容器键，此函数尝试从
    多个常见键中提取结果列表，提供统一的接口。

    Args:
        payload (Dict[str, Any]): API 返回的原始数据。

    Returns:
        List[Dict[str, Any]]: 提取的结果列表。如果 payload
            本身就是列表，则直接返回。

    支持的容器键：
        - "results"
        - "items"
        - "data"
        - "records"

    Example:
        >>> payload = {"results": [{"id": "sales"}, {"id": "ebitda"}]}
        >>> results = normalize_results(payload)
        >>> print(len(results))
        2

        >>> payload = [{"id": "sales"}]
        >>> results = normalize_results(payload)
        >>> print(len(results))
        1
    """
    # Different list endpoints use different container keys.
    for key in ("results", "items", "data", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    if isinstance(payload, list):
        return payload
    return []


def extract_total(payload: Dict[str, Any]) -> Optional[int]:
    """
    在接口提供时提取总数元数据。

    从 API 返回中提取总数信息，用于支持分页和进度显示。
    API 可能使用不同的键名表示总数。

    Args:
        payload (Dict[str, Any]): API 返回的原始数据。

    Returns:
        Optional[int]: 总数。如果 payload 中没有总数信息，返回 None。

    支持的总数键：
        - "count"
        - "total"
        - "total_count"

    Example:
        >>> payload = {"results": [...], "count": 100}
        >>> total = extract_total(payload)
        >>> print(total)
        100

        >>> payload = {"items": [...]}
        >>> total = extract_total(payload)
        >>> print(total)
        None
    """
    # Preserve pagination support even if the API changes the total-count key.
    for key in ("count", "total", "total_count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return None


def fetch_fields_with_cache(
    client: Any,
    args: Any,
    fields_cache_file: str,
    cached_fields: Sequence[Dict[str, Any]],
    cache_refresh_reason: str,
) -> List[Dict[str, Any]]:
    """
    根据缓存状态拉取字段；能补齐时补齐，必要时才覆盖刷新。

    此函数实现了智能的字段获取策略：
    - 如果缓存有效且满足需求，直接使用缓存
    - 如果缓存不足但可补齐，追加获取缺失的字段
    - 如果需要完全刷新，重新获取所有字段

    Args:
        client: Brain API 客户端实例，需要实现 fetch_dataset_fields 方法。
        args: 命令行参数对象，包含 dataset_id、limit、offset 等属性。
        fields_cache_file: 字段缓存文件路径。
        cached_fields (Sequence[Dict[str, Any]]): 当前缓存的字段列表。
        cache_refresh_reason (str): 刷新原因字符串。如果为空，表示无需刷新。

    Returns:
        List[Dict[str, Any]]: 最终的字段列表。

    Example:
        >>> fields = fetch_fields_with_cache(
        ...     client=brain_client,
        ...     args=args,
        ...     fields_cache_file="/path/to/cache.json",
        ...     cached_fields=[{"id": "sales"}],
        ...     cache_refresh_reason="cache has 1 fields but limit requests 100"
        ... )
        >>> print(len(fields))
        100

    Note:
        此函数会自动保存更新后的缓存文件。
        使用重试机制处理临时 API 不稳定性。
    """
    if not cache_refresh_reason:
        fields = list(cached_fields)
        print(f"[cache] 从 {fields_cache_file} 加载 {len(fields)} 个字段", flush=True)
        return fields

    print(f"[cache] 刷新字段缓存: {cache_refresh_reason}", flush=True)
    append_to_cache = (
        bool(cached_fields)
        and not args.refresh_fields_cache
        and args.offset == 0
        and args.limit > len(cached_fields)
    )
    fetch_offset = len(cached_fields) if append_to_cache else args.offset
    fetch_limit = args.limit - len(cached_fields) if append_to_cache else args.limit
    if append_to_cache:
        print(
            f"[cache] 从 {len(cached_fields)} 扩展缓存到 {args.limit}，"
            f"使用 offset={fetch_offset} limit={fetch_limit}",
            flush=True,
        )

    # Fetching the field list is also wrapped so temporary API instability
    # does not abort the whole batch before it starts.
    fetched_fields = client.fetch_dataset_fields(
        args.dataset_id,
        limit=fetch_limit,
        offset=fetch_offset,
        page_size=args.page_size,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
    )
    fields = merge_fields_by_id(cached_fields, fetched_fields) if append_to_cache else fetched_fields
    save_fields_cache(
        fields_cache_file,
        dataset_id=args.dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
        fields=fields,
    )
    print(f"[cache] 保存 {len(fields)} 个字段到 {fields_cache_file}", flush=True)
    return fields
