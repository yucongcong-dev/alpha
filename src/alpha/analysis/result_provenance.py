"""Result scope and provenance enrichment helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models.domain import FieldTestResult
from ..utils.helpers import utc_now_iso


def portable_source_summary(output_path: str) -> str:
    """Prefer a dataset-relative run reference over a machine-specific path."""
    output = Path(output_path)
    if output.parent.parent.name == "runs":
        return (Path("runs") / output.parent.name / output.name).as_posix()
    return output.name


def _dataset_scope(run_config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run_config, dict):
        return {}
    dataset = run_config.get("dataset", {})
    return dataset if isinstance(dataset, dict) else {}


def _run_name(run_config: dict[str, Any] | None, output_path: str) -> str:
    if isinstance(run_config, dict):
        run = run_config.get("run", {})
        if isinstance(run, dict) and run.get("name"):
            return str(run["name"])
    output = Path(output_path)
    return output.parent.name if output.parent.parent.name == "runs" else ""


def enrich_results_provenance(
    results: list[FieldTestResult],
    *,
    output_path: str,
    run_config: dict[str, Any] | None = None,
    observed_at: str | None = None,
) -> None:
    """Fill missing scope/source fields without rewriting historical provenance."""
    timestamp = observed_at or utc_now_iso()
    scope = _dataset_scope(run_config)
    source_summary = portable_source_summary(output_path)
    run_name = _run_name(run_config, output_path)
    for result in results:
        if not result.region:
            result.region = str(scope.get("region", ""))
        if not result.universe:
            result.universe = str(scope.get("universe", ""))
        if not result.instrument_type:
            result.instrument_type = str(scope.get("instrument_type", ""))
        if result.delay is None and scope.get("delay") is not None:
            result.delay = int(scope["delay"])
        if not result.run_name:
            result.run_name = run_name
        if not result.source_summary:
            result.source_summary = source_summary
        if not result.created_at:
            result.created_at = timestamp
        if not result.updated_at:
            result.updated_at = timestamp
        result.revision = max(1, int(result.revision or 1))
