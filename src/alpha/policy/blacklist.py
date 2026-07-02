"""
模板黑名单策略模块。

本模块负责：
- 黑名单文件路径与骨架管理
- 模板失败聚合
- 黑名单判定与增量更新
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from ..config import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    DatasetExpressionPolicy,
    get_dataset_expression_policy,
)
from ..io.common import (
    atomic_write_json,
    resolve_runtime_data_dir,
    sanitize_dataset_id_for_filename,
)
from ..models.base import FieldTestResult

logger = logging.getLogger(__name__)

_BLACKLIST_PATH_CACHE: dict[str, str] = {}


def _resolve_blacklist_path(dataset_id: str, *, data_dir: str = "") -> str:
    """按数据集解析统一黑名单路径：data/blacklists/{dataset_id}/blacklist.json。"""
    cache_key = f"{dataset_id}|{data_dir}" if data_dir else dataset_id
    if cache_key in _BLACKLIST_PATH_CACHE:
        return _BLACKLIST_PATH_CACHE[cache_key]
    base = resolve_runtime_data_dir(data_dir)
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    resolved = str(base / "blacklists" / dataset_key / "blacklist.json")
    _BLACKLIST_PATH_CACHE[cache_key] = resolved
    return resolved

def _build_default_blacklist(dataset_id: str) -> dict[str, Any]:
    """构建单个数据集的黑名单骨架结构。"""
    return {
        "_version": "v2",
        "_comment": f"Template blacklist for {dataset_id} — auto-populated from test results.",
        "_created": time.strftime("%Y-%m-%d"),
        "_updated": time.strftime("%Y-%m-%d"),
        "dataset_id": dataset_id,
        "blacklisted_templates": [],
        "auto_avoid_rules": [],
    }


def load_blacklisted_template_names(dataset_id: str, *, data_dir: str = "") -> set[str]:
    """读取当前数据集统一黑名单中的模板名集合。"""
    blacklist_path = _resolve_blacklist_path(dataset_id, data_dir=data_dir)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        else:
            return set()
    except (json.JSONDecodeError, OSError):
        return set()
    if not isinstance(payload, dict):
        return set()
    entries = payload.get("blacklisted_templates", [])
    if not isinstance(entries, list):
        return set()
    return {
        str(item.get("name"))
        for item in entries
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }


def ensure_template_blacklist_file(dataset_id: str, *, data_dir: str = "") -> str:
    """确保 dataset 专属统一模板黑名单文件存在。"""
    blacklist_path = _resolve_blacklist_path(dataset_id, data_dir=data_dir)
    if os.path.isfile(blacklist_path):
        return blacklist_path
    atomic_write_json(blacklist_path, _build_default_blacklist(dataset_id))
    logger.info("[blacklist] created dataset blacklist file: %s", blacklist_path)
    return blacklist_path


def _update_blacklist_runtime_stats_with_result(
    stats: dict[str, dict[str, Any]],
    result: FieldTestResult,
) -> dict[str, Any] | None:
    """把单条结果增量合并到模板黑名单聚合状态中。"""
    from ..analysis.stats import is_informative_result

    if not is_informative_result(result):
        return None
    template_name = result.template_name
    summary = stats.setdefault(
        template_name,
        {
            "template_name": template_name,
            "field_type": result.field_type,
            "template_family": result.template_family,
            "template_stage": result.template_stage,
            "fields_tested": [],
            "_field_names_seen": set(),
            "submittable": 0,
            "low_sharpe": 0,
            "low_fitness": 0,
            "concentrated_weight": 0,
            "sharpe_sum": 0.0,
            "sharpe_count": 0,
            "fitness_sum": 0.0,
            "fitness_count": 0,
        },
    )
    field_name = str(result.field_name or "")
    if field_name and field_name not in summary["_field_names_seen"]:
        summary["_field_names_seen"].add(field_name)
        summary["fields_tested"].append(field_name)
    if result.submittable:
        summary["submittable"] += 1
    for check in result.failed_checks or []:
        name = str(check.get("name", ""))
        value = check.get("value")
        if name == CHECK_LOW_SHARPE:
            summary["low_sharpe"] += 1
            if isinstance(value, (int, float)):
                summary["sharpe_sum"] += float(value)
                summary["sharpe_count"] += 1
        elif name == CHECK_LOW_FITNESS:
            summary["low_fitness"] += 1
            if isinstance(value, (int, float)):
                summary["fitness_sum"] += float(value)
                summary["fitness_count"] += 1
        elif name == CHECK_CONCENTRATED_WEIGHT:
            summary["concentrated_weight"] += 1
    return summary


def build_blacklist_runtime_stats(results: list[FieldTestResult]) -> dict[str, dict[str, Any]]:
    """从完整结果列表构建黑名单增量聚合状态。"""
    stats: dict[str, dict[str, Any]] = {}
    for result in results:
        _update_blacklist_runtime_stats_with_result(stats, result)
    return stats


def _build_blacklist_entry_from_runtime_summary(
    summary: dict[str, Any],
    *,
    dataset_id: str,
    policy: DatasetExpressionPolicy,
    min_fields_tested: int,
    min_fail_checks: int,
) -> dict[str, Any] | None:
    """按增量聚合状态判断某模板是否应进入黑名单。"""
    template_name = str(summary.get("template_name", "")).strip()
    if not template_name or template_name in policy.protected_templates:
        return None
    fields_tested = list(summary.get("fields_tested", []))
    if len(fields_tested) < min_fields_tested:
        return None
    if int(summary.get("submittable", 0)) > 0:
        return None
    low_sharpe_count = int(summary.get("low_sharpe", 0))
    low_fitness_count = int(summary.get("low_fitness", 0))
    concentrated_count = int(summary.get("concentrated_weight", 0))
    total_fails = low_sharpe_count + low_fitness_count
    if total_fails < min_fail_checks:
        return None
    sharpe_count = int(summary.get("sharpe_count", 0))
    fitness_count = int(summary.get("fitness_count", 0))
    avg_sharpe = (
        round(float(summary.get("sharpe_sum", 0.0)) / sharpe_count, 3)
        if sharpe_count > 0
        else None
    )
    avg_fitness = (
        round(float(summary.get("fitness_sum", 0.0)) / fitness_count, 3)
        if fitness_count > 0
        else None
    )
    if (
        policy.blacklist_min_fields_for_nearpass > 0
        and len(fields_tested) < policy.blacklist_min_fields_for_nearpass
        and (
            (
                avg_sharpe is not None
                and avg_sharpe >= policy.blacklist_protected_min_avg_sharpe
            )
            or (
                avg_fitness is not None
                and avg_fitness >= policy.blacklist_protected_min_avg_fitness
            )
        )
    ):
        return None
    reason_parts = [f"{len(fields_tested)}个字段测试均不通过"]
    if avg_sharpe is not None:
        reason_parts.append(f"平均 Sharpe {avg_sharpe:.3f}")
    if avg_fitness is not None:
        reason_parts.append(f"平均 Fitness {avg_fitness:.3f}")
    from datetime import datetime

    entry: dict[str, Any] = {
        "name": template_name,
        "dataset_id": dataset_id,
        "source": "auto_detected",
        "field_type": str(summary.get("field_type", "")),
        "template_family": str(summary.get("template_family", "")),
        "template_stage": str(summary.get("template_stage", "")),
        "reason": "。".join(reason_parts) + "。",
        "fields_tested": fields_tested,
        "low_sharpe": low_sharpe_count,
        "low_fitness": low_fitness_count,
        "date_blacklisted": datetime.now().strftime("%Y-%m-%d"),
    }
    if avg_sharpe is not None:
        entry["avg_sharpe"] = avg_sharpe
    if avg_fitness is not None:
        entry["avg_fitness"] = avg_fitness
    if concentrated_count:
        entry["concentrated_weight"] = concentrated_count
    return entry


def auto_update_blacklist(
    results: list[FieldTestResult],
    dataset_id: str,
    *,
    data_dir: str = "",
    min_fields_tested: int = 2,
    min_fail_checks: int = 2,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> None:
    """根据测试结果自动更新模板黑名单。"""
    if not dataset_id or not results:
        return
    from datetime import datetime

    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    runtime_stats = build_blacklist_runtime_stats(results)
    new_entries: list[dict[str, Any]] = []
    for summary in runtime_stats.values():
        entry = _build_blacklist_entry_from_runtime_summary(
            summary,
            dataset_id=dataset_id,
            policy=policy,
            min_fields_tested=min_fields_tested,
            min_fail_checks=min_fail_checks,
        )
        if entry is not None:
            new_entries.append(entry)

    if not new_entries:
        return

    blacklist_path = _resolve_blacklist_path(dataset_id, data_dir=data_dir)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as fh:
                bl_data = json.load(fh)
        else:
            bl_data = _build_default_blacklist(dataset_id)
    except (json.JSONDecodeError, OSError):
        bl_data = _build_default_blacklist(dataset_id)

    if not isinstance(bl_data, dict):
        bl_data = _build_default_blacklist(dataset_id)
    bl_data.setdefault("dataset_id", dataset_id)
    bl_data.setdefault("blacklisted_templates", [])
    bl_data.setdefault("auto_avoid_rules", [])

    existing_names = {
        item["name"]
        for item in bl_data["blacklisted_templates"]
        if isinstance(item, dict) and item.get("name")
    }
    added = 0
    for entry in new_entries:
        if entry["name"] not in existing_names:
            bl_data["blacklisted_templates"].append(entry)
            existing_names.add(entry["name"])
            added += 1

    if added == 0:
        return

    bl_data["_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    atomic_write_json(blacklist_path, bl_data)
    from ..generators.expressions import invalidate_blacklist_cache

    invalidate_blacklist_cache(dataset_id)
    logger.info(
        "[blacklist] auto-updated %s: added %d new entries (total=%d)",
        blacklist_path,
        added,
        len(bl_data["blacklisted_templates"]),
    )


def auto_update_blacklist_incremental(
    runtime_stats: dict[str, dict[str, Any]],
    blacklisted_template_names: set[str],
    result: FieldTestResult,
    dataset_id: str,
    *,
    data_dir: str = "",
    min_fields_tested: int = 2,
    min_fail_checks: int = 2,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> bool:
    """仅对本次变化的模板尝试增量写入黑名单。"""
    if not dataset_id:
        return False
    from datetime import datetime

    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    summary = _update_blacklist_runtime_stats_with_result(runtime_stats, result)
    if summary is None:
        return False
    template_name = str(summary.get("template_name", "")).strip()
    if not template_name or template_name in blacklisted_template_names:
        return False
    entry = _build_blacklist_entry_from_runtime_summary(
        summary,
        dataset_id=dataset_id,
        policy=policy,
        min_fields_tested=min_fields_tested,
        min_fail_checks=min_fail_checks,
    )
    if entry is None:
        return False
    blacklist_path = _resolve_blacklist_path(dataset_id, data_dir=data_dir)
    try:
        if os.path.isfile(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as fh:
                bl_data = json.load(fh)
        else:
            bl_data = _build_default_blacklist(dataset_id)
    except (json.JSONDecodeError, OSError):
        bl_data = _build_default_blacklist(dataset_id)
    if not isinstance(bl_data, dict):
        bl_data = _build_default_blacklist(dataset_id)
    bl_data.setdefault("dataset_id", dataset_id)
    bl_data.setdefault("blacklisted_templates", [])
    bl_data.setdefault("auto_avoid_rules", [])
    existing_names = {
        item["name"]
        for item in bl_data["blacklisted_templates"]
        if isinstance(item, dict) and item.get("name")
    }
    if entry["name"] in existing_names:
        blacklisted_template_names.add(entry["name"])
        return False
    bl_data["blacklisted_templates"].append(entry)
    bl_data["_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    atomic_write_json(blacklist_path, bl_data)
    from ..generators.expressions import invalidate_blacklist_cache

    invalidate_blacklist_cache(dataset_id)
    blacklisted_template_names.add(entry["name"])
    logger.info(
        "[blacklist] incrementally added %s to %s (total=%d)",
        entry["name"],
        blacklist_path,
        len(bl_data["blacklisted_templates"]),
    )
    return True
