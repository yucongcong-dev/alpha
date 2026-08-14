"""Incremental run discovery index for dataset feedback snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..io.common import atomic_write_json
from ..io.output_paths import build_fields_cache_scope_key

RUN_INDEX_SCHEMA_VERSION = 3


def resolve_feedback_layout(feedback_output_path: str) -> tuple[Path, str, Path] | None:
    """Return feedback root, optional scope key and sibling runs directory."""
    feedback_path = Path(feedback_output_path)
    if feedback_path.parent.name == "feedback":
        feedback_root = feedback_path.parent
        scope_key = ""
    elif feedback_path.parent.parent.name == "feedback":
        feedback_root = feedback_path.parent.parent
        scope_key = feedback_path.parent.name
    else:
        return None
    return feedback_root, scope_key, feedback_root.parent / "runs"


def feedback_run_index_path(feedback_output_path: str) -> Path:
    return Path(feedback_output_path).parent / "run_index.json"


def load_summary_run_config(summary_path: Path) -> dict[str, object]:
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    run_config = payload.get("run_config", {}) if isinstance(payload, dict) else {}
    return run_config if isinstance(run_config, dict) else {}


def run_config_scope_key(run_config: dict[str, object]) -> str:
    dataset = run_config.get("dataset", {})
    if not isinstance(dataset, dict):
        return ""
    delay = dataset.get("delay")
    return build_fields_cache_scope_key(
        region=str(dataset.get("region", "")),
        universe=str(dataset.get("universe", "")),
        instrument_type=str(dataset.get("instrument_type", "")),
        delay=int(delay) if delay is not None else None,
    )


def load_feedback_run_index(feedback_output_path: str) -> dict[str, dict[str, object]]:
    index_path = feedback_run_index_path(feedback_output_path)
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema_version") != RUN_INDEX_SCHEMA_VERSION:
        return {}
    entries = payload.get("runs", {})
    if not isinstance(entries, dict):
        return {}
    return {str(key): value for key, value in entries.items() if isinstance(value, dict)}


def feedback_run_index_is_current(feedback_output_path: str, runs_root: Path) -> bool:
    """Return whether indexed summary-file signatures still match the runs tree."""
    index_path = feedback_run_index_path(feedback_output_path)
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or payload.get("schema_version") != RUN_INDEX_SCHEMA_VERSION:
        return False
    snapshot = payload.get("runs_snapshot")
    if not isinstance(snapshot, dict):
        return False
    current_snapshot: dict[str, dict[str, int]] = {}
    if runs_root.is_dir():
        for summary_path in sorted(runs_root.glob("*/summary.json")):
            try:
                mtime_ns, size = run_summary_signature(summary_path)
            except OSError:
                return False
            current_snapshot[run_summary_key(summary_path, runs_root)] = {
                "mtime_ns": mtime_ns,
                "size": size,
            }
    return snapshot == current_snapshot


def run_summary_key(summary_path: Path, runs_root: Path) -> str:
    return summary_path.relative_to(runs_root).as_posix()


def run_summary_signature(summary_path: Path) -> tuple[int, int]:
    stat = summary_path.stat()
    return stat.st_mtime_ns, stat.st_size


def is_indexed_run_current(
    entry: dict[str, object] | None,
    summary_path: Path,
    *,
    scope_key: str,
) -> bool:
    if not entry or str(entry.get("scope_key", "")) != scope_key:
        return False
    mtime_ns, size = run_summary_signature(summary_path)
    return entry.get("mtime_ns") == mtime_ns and entry.get("size") == size


def persist_feedback_run_index(feedback_output_path: str) -> None:
    """Refresh the index, reading run JSON only for new or changed summaries."""
    layout = resolve_feedback_layout(feedback_output_path)
    if layout is None:
        return
    _, scope_key, runs_root = layout
    previous = load_feedback_run_index(feedback_output_path)
    entries: dict[str, dict[str, Any]] = {}
    runs_snapshot: dict[str, dict[str, int]] = {}
    if runs_root.is_dir():
        for summary_path in sorted(runs_root.glob("*/summary.json")):
            key = run_summary_key(summary_path, runs_root)
            mtime_ns, size = run_summary_signature(summary_path)
            runs_snapshot[key] = {"mtime_ns": mtime_ns, "size": size}
            prior = previous.get(key)
            if is_indexed_run_current(prior, summary_path, scope_key=scope_key):
                entries[key] = dict(prior or {})
                continue
            run_scope_key = run_config_scope_key(load_summary_run_config(summary_path))
            if scope_key and run_scope_key != scope_key:
                continue
            entries[key] = {
                "mtime_ns": mtime_ns,
                "size": size,
                "scope_key": run_scope_key,
            }
    atomic_write_json(
        str(feedback_run_index_path(feedback_output_path)),
        {
            "schema_version": RUN_INDEX_SCHEMA_VERSION,
            "runs_snapshot": runs_snapshot,
            "runs": entries,
        },
    )
