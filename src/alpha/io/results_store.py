"""
结果持久化与 journal 写入实现。
"""

from __future__ import annotations

from contextlib import suppress
import json
import logging
import os
import tempfile
from typing import Any, Callable

from ..analysis.report_builder import build_analysis_payload, build_results_summary_payload
from ..models.base import FieldTestResult
from .common import atomic_write_json
from .output_paths import build_output_sidecar_paths, cleanup_legacy_sidecar_files

logger = logging.getLogger(__name__)

BlacklistUpdater = Callable[[list[FieldTestResult], str], None]


def load_results_rows_from_journal(journal_path: str) -> list[dict[str, Any]]:
    """从 results journal 读取原始结果字典行。"""
    if not os.path.exists(journal_path):
        return []
    rows: list[dict[str, Any]] = []
    with open(journal_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def initialize_results_journal(output_path: str, results: list[FieldTestResult]) -> int:
    """用当前完整结果列表重建 journal，供运行中增量追加使用。"""
    sidecar_paths = build_output_sidecar_paths(output_path)
    journal_path = sidecar_paths["results_journal"]
    directory = os.path.dirname(os.path.abspath(journal_path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".jsonl", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for result in results:
                handle.write(json.dumps(result.to_dict(), ensure_ascii=False))
                handle.write("\n")
        os.replace(temp_path, journal_path)
    finally:
        if os.path.exists(temp_path):
            with suppress(OSError):
                os.remove(temp_path)
    return len(results)


def _append_results_journal(journal_path: str, results: list[FieldTestResult]) -> None:
    """把新增结果追加到 journal。"""
    if not results:
        return
    directory = os.path.dirname(os.path.abspath(journal_path)) or "."
    os.makedirs(directory, exist_ok=True)
    with open(journal_path, "a", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result.to_dict(), ensure_ascii=False))
            handle.write("\n")


def dump_results(
    path: str,
    dataset_id: str,
    results: list[FieldTestResult],
    *,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict[str, Any] | None = None,
    auto_update_template_blacklist: bool = False,
    include_analysis: bool = True,
    auto_update_blacklist_fn: BlacklistUpdater | None = None,
) -> None:
    """持久化完整运行结果，并按需同步分析边车文件。"""
    sidecar_paths = build_output_sidecar_paths(path)
    summary, analysis_inputs = build_results_summary_payload(
        dataset_id,
        results,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
        results_journal_path=sidecar_paths["results_journal"],
    )
    summary["results_embedded"] = True
    atomic_write_json(path, summary)
    initialize_results_journal(path, results)
    if include_analysis:
        analysis = build_analysis_payload(results, summary, analysis_inputs)
        atomic_write_json(sidecar_paths["analysis"], analysis)
    cleanup_legacy_sidecar_files(path)
    logger.info(
        "[done] wrote results to %s (tested=%d, submittable=%d)",
        path,
        len(results),
        summary["submittable"],
    )
    if include_analysis:
        logger.debug("[done] wrote analysis to %s", sidecar_paths["analysis"])
    if auto_update_template_blacklist and auto_update_blacklist_fn is not None:
        auto_update_blacklist_fn(results, dataset_id)


def dump_results_incremental(
    path: str,
    dataset_id: str,
    new_results: list[FieldTestResult],
    *,
    persisted_result_count: int,
    tested: int,
    unique_fields_tested: int,
    submittable_count: int,
    submitted_count: int,
    error_count: int,
    queue_timeout_count: int,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict[str, Any] | None = None,
) -> int:
    """仅把新增结果追加到 journal，并写轻量 summary。"""
    sidecar_paths = build_output_sidecar_paths(path)
    if new_results:
        _append_results_journal(sidecar_paths["results_journal"], new_results)
    summary = {
        "dataset_id": dataset_id,
        "run_config": run_config or {},
        "settings_fingerprint": settings_fingerprint,
        "template_library_fingerprint": template_library_fingerprint,
        "tested": tested,
        "unique_fields_tested": unique_fields_tested,
        "submittable": submittable_count,
        "submitted": submitted_count,
        "errors": error_count,
        "queue_timeouts": queue_timeout_count,
        "results_embedded": False,
        "results_journal": sidecar_paths["results_journal"],
    }
    atomic_write_json(path, summary)
    cleanup_legacy_sidecar_files(path)
    logger.info(
        "[done] wrote incremental results to %s (tested=%d, submittable=%d, appended=%d)",
        path,
        tested,
        submittable_count,
        len(new_results),
    )
    return persisted_result_count + len(new_results)

