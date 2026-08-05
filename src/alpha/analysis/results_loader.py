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
from ..io.output_paths import build_output_sidecar_paths
from ..io.results_store import load_results_rows_from_journal
from ..models.domain import FieldTestResult, ResultRow
from ..models.domain_parsers import parse_failed_check

logger = logging.getLogger(__name__)


def _default_results_journal_path(path: str) -> str:
    """为主结果文件派生默认 journal 路径。"""
    return build_output_sidecar_paths(path)["results_journal"]


def _resolve_results_journal_path(summary_path: str, reference: object) -> str:
    """Resolve portable references and recover legacy absolute paths after moves."""
    summary = Path(summary_path)
    candidates: list[Path] = []
    if isinstance(reference, str) and reference:
        referenced = Path(reference).expanduser()
        if referenced.is_absolute():
            candidates.extend((referenced, summary.parent / referenced.name))
        else:
            candidates.append(summary.parent / referenced)
    candidates.append(Path(_default_results_journal_path(summary_path)))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


def _load_results_rows_from_journal(journal_path: str) -> list[ResultRow]:
    """从结果 journal 读取原始结果行。"""
    return load_results_rows_from_journal(journal_path)


def _rows_to_results(rows: list[Any], *, source: str) -> list[FieldTestResult]:
    """把原始结果字典列表转换为 FieldTestResult 列表。"""
    results: list[FieldTestResult] = []
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(
                f"invalid result row at {source}:{row_number}; "
                f"expected object, got {type(row).__name__}"
            )
        try:
            results.append(
                FieldTestResult(
                    field_id=str(row.get(STAT_FIELD_FIELD_ID, SENTINEL_UNKNOWN)),
                    field_type=str(row.get(STAT_FIELD_FIELD_TYPE, SENTINEL_UNKNOWN)),
                    field_name=str(row.get(STAT_FIELD_FIELD_NAME, SENTINEL_UNKNOWN)),
                    template_name=str(row.get(STAT_FIELD_TEMPLATE_NAME, "")),
                    template_family=str(row.get("template_family", "")),
                    template_stage=str(row.get("template_stage", "")),
                    template_role=str(row.get("template_role", "")),
                    template_activation_scope=str(row.get("template_activation_scope", "")),
                    policy_version=str(row.get("policy_version", "")),
                    simulation_id=row.get("simulation_id"),
                    alpha_id=row.get("alpha_id"),
                    status=str(row.get(API_KEY_STATUS, SENTINEL_UNKNOWN_STATUS)),
                    submittable=row.get(STAT_FIELD_SUBMITTABLE),
                    submitted=bool(row.get(STAT_FIELD_SUBMITTED, False)),
                    message=str(row.get(API_KEY_MESSAGE, "")),
                    expression=str(row.get("expression", "")),
                    settings_fingerprint=str(row.get("settings_fingerprint", "")),
                    template_library_fingerprint=str(row.get("template_library_fingerprint", "")),
                    settings=dict(row.get("settings", {}))
                    if isinstance(row.get("settings"), dict)
                    else {},
                    metrics=dict(row.get("metrics", {}))
                    if isinstance(row.get("metrics"), dict)
                    else {},
                    region=str(row.get("region", "")),
                    universe=str(row.get("universe", "")),
                    instrument_type=str(row.get("instrument_type", "")),
                    delay=int(row["delay"]) if row.get("delay") is not None else None,
                    run_name=str(row.get("run_name", "")),
                    source_summary=str(row.get("source_summary", "")),
                    created_at=str(row.get("created_at", "")),
                    updated_at=str(row.get("updated_at", "")),
                    revision=max(1, int(row.get("revision", 1) or 1)),
                    failed_stage=row.get("failed_stage"),
                    failed_checks=[
                        parse_failed_check(check)
                        for check in row.get("failed_checks", [])
                        if isinstance(check, dict)
                    ]
                    if isinstance(row.get("failed_checks"), list)
                    else None,
                )
            )
        except Exception as exc:
            raise ValueError(f"invalid result row at {source}:{row_number}: {exc}") from exc
    return results


def _recover_results_from_journal(path: str) -> list[FieldTestResult]:
    """从默认 journal 恢复结果，损坏时明确失败以免重复运行。"""
    journal_path = _default_results_journal_path(path)
    if not os.path.exists(journal_path):
        return []
    try:
        rows = _load_results_rows_from_journal(journal_path)
        return _rows_to_results(rows, source=journal_path)
    except Exception as exc:
        raise ValueError(f"failed to recover results journal {journal_path}: {exc}") from exc


def load_existing_results(
    path: str,
    *,
    repair_corrupt_summary: bool = True,
) -> list[FieldTestResult]:
    """加载历史运行结果，以便续跑和复用反馈信息。

    ``repair_corrupt_summary=False`` is used by read-only planning so inspecting
    a plan never renames user files.  Journal recovery remains available in
    either mode.
    """
    if not path:
        return []
    if not os.path.exists(path):
        return _recover_results_from_journal(path)

    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        if repair_corrupt_summary:
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
                logger.warning(
                    "[recovery] failed to rename corrupted result file %s: %s", path, exc
                )
        else:
            logger.warning(
                "[recovery] read-only load ignored corrupted result file %s: %s",
                path,
                exc,
            )
        return _recover_results_from_journal(path)

    if not isinstance(payload, dict):
        if repair_corrupt_summary:
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
        else:
            logger.warning(
                "[recovery] read-only load ignored invalid result file %s (unexpected JSON type: %s)",
                path,
                type(payload).__name__,
            )
        return _recover_results_from_journal(path)

    journal_path = _resolve_results_journal_path(path, payload.get("results_journal"))
    if os.path.exists(journal_path):
        try:
            rows = _load_results_rows_from_journal(journal_path)
            return _rows_to_results(rows, source=journal_path)
        except Exception as exc:
            logger.warning("[recovery] failed to read results journal %s: %s", journal_path, exc)
    if payload.get("results_embedded", True):
        payload_rows = payload.get("results")
        if isinstance(payload_rows, list):
            return _rows_to_results(payload_rows, source=f"{path}:results")
    return []
