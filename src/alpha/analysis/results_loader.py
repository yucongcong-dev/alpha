"""历史结果加载与 journal 恢复。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any

from ..config.constants import (
    API_KEY_MESSAGE,
    API_KEY_STATUS,
    SENTINEL_UNKNOWN,
    SENTINEL_UNKNOWN_STATUS,
    STAT_FIELD_FIELD_ID,
    STAT_FIELD_FIELD_NAME,
    STAT_FIELD_FIELD_TYPE,
    STAT_FIELD_SUBMITTABLE,
    STAT_FIELD_SUBMITTED,
    STAT_FIELD_TEMPLATE_NAME,
)
from ..models.domain import FieldTestResult, ResultRow

logger = logging.getLogger(__name__)


def _default_results_journal_path(path: str) -> str:
    """为主结果文件派生默认 journal 路径。"""
    output = Path(path)
    base_name = output.stem or output.name or "results"
    return str(output.parent / f"{base_name}_results.jsonl")


def _load_results_rows_from_journal(journal_path: str) -> list[ResultRow]:
    """从结果 journal 读取原始结果行。"""
    rows: list[ResultRow] = []
    with open(journal_path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _rows_to_results(rows: list[Any]) -> list[FieldTestResult]:
    """把原始结果字典列表转换为 FieldTestResult 列表。"""
    results: list[FieldTestResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            results.append(
                FieldTestResult(
                    field_id=str(row.get(STAT_FIELD_FIELD_ID, SENTINEL_UNKNOWN)),
                    field_type=str(row.get(STAT_FIELD_FIELD_TYPE, SENTINEL_UNKNOWN)),
                    field_name=str(row.get(STAT_FIELD_FIELD_NAME, SENTINEL_UNKNOWN)),
                    template_name=str(row.get(STAT_FIELD_TEMPLATE_NAME, "")),
                    template_family=str(row.get("template_family", "")),
                    template_stage=str(row.get("template_stage", "")),
                    simulation_id=row.get("simulation_id"),
                    alpha_id=row.get("alpha_id"),
                    status=str(row.get(API_KEY_STATUS, SENTINEL_UNKNOWN_STATUS)),
                    submittable=row.get(STAT_FIELD_SUBMITTABLE),
                    submitted=bool(row.get(STAT_FIELD_SUBMITTED, False)),
                    message=str(row.get(API_KEY_MESSAGE, "")),
                    expression=str(row.get("expression", "")),
                    settings_fingerprint=str(row.get("settings_fingerprint", "")),
                    template_library_fingerprint=str(row.get("template_library_fingerprint", "")),
                    failed_stage=row.get("failed_stage"),
                    failed_checks=row.get("failed_checks"),
                    self_correlation_pending_since=float(
                        row.get("self_correlation_pending_since", 0.0) or 0.0
                    ),
                    self_correlation_last_recheck_at=float(
                        row.get("self_correlation_last_recheck_at", 0.0) or 0.0
                    ),
                    self_correlation_recheck_count=int(
                        row.get("self_correlation_recheck_count", 0) or 0
                    ),
                )
            )
        except Exception:
            continue
    return results


def _recover_results_from_journal(path: str) -> list[FieldTestResult]:
    """从默认 journal 恢复结果，失败时返回空列表。"""
    journal_path = _default_results_journal_path(path)
    if not os.path.exists(journal_path):
        return []
    try:
        rows = _load_results_rows_from_journal(journal_path)
    except Exception as exc:
        logger.warning("[recovery] failed to read orphaned results journal %s: %s", journal_path, exc)
        return []
    return _rows_to_results(rows)


def load_existing_results(path: str) -> list[FieldTestResult]:
    """加载历史运行结果，以便续跑和复用反馈信息。"""
    if not path:
        return []
    if not os.path.exists(path):
        return _recover_results_from_journal(path)

    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        now = int(time.time())
        backup_path = f"{path}.corrupted.{now}"
        try:
            os.rename(path, backup_path)
            logger.warning(
                "[recovery] renamed corrupted result file %s -> %s (error: %s)",
                path,
                backup_path,
                exc,
            )
        except OSError:
            logger.warning("[recovery] failed to rename corrupted result file %s: %s", path, exc)
        return _recover_results_from_journal(path)

    if not isinstance(payload, dict):
        now = int(time.time())
        backup_path = f"{path}.invalid.{now}"
        try:
            os.rename(path, backup_path)
            logger.warning(
                "[recovery] renamed invalid result file %s -> %s (unexpected JSON type: %s)",
                path,
                backup_path,
                type(payload).__name__,
            )
        except OSError:
            logger.warning(
                "[recovery] failed to rename invalid result file %s (unexpected JSON type: %s)",
                path,
                type(payload).__name__,
            )
        return _recover_results_from_journal(path)

    rows: list[Any] | None = None
    if payload.get("results_embedded", True):
        payload_rows = payload.get("results")
        if isinstance(payload_rows, list):
            rows = payload_rows

    if rows is None:
        journal_path_value = payload.get("results_journal")
        journal_path = (
            str(journal_path_value)
            if isinstance(journal_path_value, str) and journal_path_value
            else _default_results_journal_path(path)
        )
        try:
            rows = _load_results_rows_from_journal(journal_path)
        except Exception as exc:
            logger.warning("[recovery] failed to read results journal %s: %s", journal_path, exc)
            return []
    return _rows_to_results(rows)
