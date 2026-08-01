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
from typing import Any

from .._facade import ExportMap, facade_dir, resolve_export
from ..models.domain import FieldTestResult
from ..models.domain_serializers import serialize_field_test_result
from .file_lock import exclusive_file_lock
from .output_paths import build_output_sidecar_paths

logger = logging.getLogger(__name__)

JOURNAL_SCHEMA_VERSION = 2
SUPPORTED_JOURNAL_SCHEMA_VERSIONS = frozenset({1, JOURNAL_SCHEMA_VERSION})
JOURNAL_SCHEMA_FIELD = "_journal_schema_version"
JOURNAL_CHECKSUM_FIELD = "_journal_checksum"


@contextmanager
def _exclusive_journal_lock(journal_path: str) -> Iterator[None]:
    """Serialize journal replacement/appends across threads and POSIX processes."""
    with exclusive_file_lock(f"{journal_path}.lock"):
        yield


@contextmanager
def exclusive_results_transaction(output_path: str) -> Iterator[None]:
    """Lock a complete read-merge-write transaction for one result snapshot."""
    with exclusive_file_lock(f"{output_path}.transaction.lock"):
        yield


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
    if version is not None and version not in SUPPORTED_JOURNAL_SCHEMA_VERSIONS:
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
    # On Windows os.open on a directory raises PermissionError so directory-level
    # fsync is a no-op; per-file os.fsync is sufficient for crash-safety.
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


def _append_results_journal(
    journal_path: str,
    results: list[FieldTestResult],
    *,
    expected_row_count: int | None = None,
) -> int:
    """把新增结果追加到 journal。"""
    if not results:
        return expected_row_count or 0
    directory = os.path.dirname(os.path.abspath(journal_path)) or "."
    os.makedirs(directory, exist_ok=True)
    payload = _serialize_journal_batch(results)
    with _exclusive_journal_lock(journal_path):
        if expected_row_count is not None:
            existing_rows = load_results_rows_from_journal(journal_path)
            existing_count = len(existing_rows)
            retry_count = expected_row_count + len(results)
            if existing_count == retry_count:
                expected_rows = [_journal_row_payload(result) for result in results]
                if existing_rows[-len(expected_rows) :] != expected_rows:
                    raise RuntimeError(
                        "results journal advanced with different rows; refusing duplicate append"
                    )
                return existing_count
            if existing_count != expected_row_count:
                raise RuntimeError(
                    "results journal row count does not match persisted result count "
                    f"({existing_count} != {expected_row_count})"
                )
        with open(journal_path, "a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return (expected_row_count or 0) + len(results)


_COMPAT_EXPORTS: ExportMap = {
    "dump_results": ("..analysis.results_persistence", "dump_results"),
    "dump_results_incremental": ("..analysis.results_persistence", "dump_results_incremental"),
}


def __getattr__(name: str) -> object:
    return resolve_export(
        name=name,
        export_map=_COMPAT_EXPORTS,
        package=__package__ or "",
        namespace=__name__,
        target_globals=globals(),
    )


def __dir__() -> list[str]:
    return facade_dir(globals(), _COMPAT_EXPORTS)
