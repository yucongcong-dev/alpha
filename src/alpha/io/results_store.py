"""
结果持久化与 journal 写入实现。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
import hashlib
import json
import logging
import os
import tempfile
import threading
from typing import Any

from ..models.domain import FieldTestResult
from ..models.domain_serializers import serialize_field_test_result
from .common import atomic_write_json
from .output_paths import build_output_sidecar_paths, cleanup_legacy_sidecar_files

logger = logging.getLogger(__name__)

JOURNAL_SCHEMA_VERSION = 1
JOURNAL_SCHEMA_FIELD = "_journal_schema_version"
JOURNAL_CHECKSUM_FIELD = "_journal_checksum"

_JOURNAL_LOCKS_GUARD = threading.Lock()
_JOURNAL_LOCKS: dict[str, threading.Lock] = {}


def _journal_thread_lock(journal_path: str) -> threading.Lock:
    canonical_path = os.path.abspath(journal_path)
    with _JOURNAL_LOCKS_GUARD:
        return _JOURNAL_LOCKS.setdefault(canonical_path, threading.Lock())


@contextmanager
def _exclusive_journal_lock(journal_path: str) -> Iterator[None]:
    """Serialize journal replacement/appends across threads and POSIX processes."""
    directory = os.path.dirname(os.path.abspath(journal_path)) or "."
    os.makedirs(directory, exist_ok=True)
    lock_path = f"{journal_path}.lock"
    thread_lock = _journal_thread_lock(journal_path)
    with thread_lock, open(lock_path, "a+b") as lock_handle:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - Windows fallback uses the thread lock.
            yield
            return
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _journal_row_payload(result: FieldTestResult) -> dict[str, Any]:
    row = dict(serialize_field_test_result(result))
    row[JOURNAL_SCHEMA_FIELD] = JOURNAL_SCHEMA_VERSION
    checksum_source = json.dumps(
        row,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    row[JOURNAL_CHECKSUM_FIELD] = hashlib.sha256(checksum_source).hexdigest()
    return row


def _validate_journal_row(row: dict[str, Any], journal_path: str, line_number: int) -> None:
    version = row.get(JOURNAL_SCHEMA_FIELD)
    if version is not None and version != JOURNAL_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported results journal schema version {version!r} "
            f"at {journal_path}:{line_number}"
        )
    checksum = row.get(JOURNAL_CHECKSUM_FIELD)
    if checksum is None:
        return
    checksum_row = dict(row)
    checksum_row.pop(JOURNAL_CHECKSUM_FIELD, None)
    checksum_source = json.dumps(
        checksum_row,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected = hashlib.sha256(checksum_source).hexdigest()
    if checksum != expected:
        raise ValueError(f"results journal checksum mismatch at {journal_path}:{line_number}")


def _serialize_journal_batch(results: list[FieldTestResult]) -> str:
    return "".join(
        f"{json.dumps(_journal_row_payload(result), ensure_ascii=False)}\n" for result in results
    )


def _fsync_directory(directory: str) -> None:
    """Persist a replace operation where directory fsync is supported."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        directory_fd = os.open(directory, flags)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def load_results_rows_from_journal(journal_path: str) -> list[dict[str, Any]]:
    """从 results journal 读取原始结果字典行。"""
    if not os.path.exists(journal_path):
        return []
    rows: list[dict[str, Any]] = []
    with open(journal_path, encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                if not raw_line.endswith("\n"):
                    logger.warning(
                        "[recovery] ignored incomplete trailing journal row %s:%d",
                        journal_path,
                        line_number,
                    )
                    break
                raise
            if isinstance(row, dict):
                _validate_journal_row(row, journal_path, line_number)
                rows.append(row)
    return rows


def initialize_results_journal(output_path: str, results: list[FieldTestResult]) -> int:
    """用当前完整结果列表重建 journal，供运行中增量追加使用。"""
    sidecar_paths = build_output_sidecar_paths(output_path)
    journal_path = sidecar_paths["results_journal"]
    directory = os.path.dirname(os.path.abspath(journal_path)) or "."
    os.makedirs(directory, exist_ok=True)
    with _exclusive_journal_lock(journal_path):
        fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".jsonl", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(_serialize_journal_batch(results))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, journal_path)
            _fsync_directory(directory)
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
    payload = _serialize_journal_batch(results)
    with _exclusive_journal_lock(journal_path), open(journal_path, "a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def dump_results(
    path: str,
    dataset_id: str,
    results: list[FieldTestResult],
    *,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: dict[str, Any] | None = None,
    include_analysis: bool = True,
) -> None:
    """持久化完整运行结果，并按需同步分析边车文件。"""
    sidecar_paths = build_output_sidecar_paths(path)
    from ..analysis.report_builder import build_analysis_payload, build_results_summary_payload
    from ..analysis.template_registry_sidecars import sync_template_registry_sidecars
    from ..analysis.template_stats import compile_template_stats

    summary, analysis_inputs = build_results_summary_payload(
        dataset_id,
        results,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
        results_journal_path=sidecar_paths["results_journal"],
    )
    summary["results_embedded"] = False
    summary.pop("results", None)
    template_stats = compile_template_stats(results)
    initialize_results_journal(path, results)
    atomic_write_json(path, summary)
    sync_template_registry_sidecars(path, template_stats=template_stats)
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
    template_registry_summary: list[dict[str, Any]] | None = None,
    template_stats: dict[str, dict[str, Any]] | None = None,
    policy_evaluation: dict[str, Any] | None = None,
) -> int:
    """仅把新增结果追加到 journal，并写轻量 summary。"""
    sidecar_paths = build_output_sidecar_paths(path)
    from ..analysis.template_registry_sidecars import (
        ensure_template_registry_overrides_sidecar,
        persist_template_registry_summary,
    )

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
        "policy_evaluation": policy_evaluation
        or {
            "evaluation_unit": "field",
            "confidence_level": 0.95,
            "minimum_fields_per_arm": 20,
            "groups": [],
            "comparisons": [],
        },
        "results_embedded": False,
        "results_journal": sidecar_paths["results_journal"],
    }
    atomic_write_json(path, summary)
    if template_registry_summary is not None or template_stats is not None:
        persist_template_registry_summary(
            path,
            summary_rows=template_registry_summary,
            template_stats=template_stats,
        )
    ensure_template_registry_overrides_sidecar(path)
    cleanup_legacy_sidecar_files(path)
    logger.info(
        "[done] wrote incremental results to %s (tested=%d, submittable=%d, appended=%d)",
        path,
        tested,
        submittable_count,
        len(new_results),
    )
    return persisted_result_count + len(new_results)
