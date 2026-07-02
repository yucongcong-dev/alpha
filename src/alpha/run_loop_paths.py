"""Run-loop path and output option helpers."""

from __future__ import annotations

from .models.io_types import RunPaths
from .models.runtime import ResultWriteArgs, ResultWriteOptions


def run_path_value(run_paths: object | None, attr: str) -> str:
    """Read a path from RunPaths or a legacy attr-style object."""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def resolve_result_write_options(
    args: ResultWriteArgs,
    run_paths: RunPaths | object | None,
) -> ResultWriteOptions:
    """Prefer run_paths output over raw args output to avoid legacy mutation coupling."""
    options = ResultWriteOptions.from_args(args)
    output_path = run_path_value(run_paths, "output") or options.output_path
    return ResultWriteOptions(
        dataset_id=options.dataset_id,
        output_path=output_path,
        auto_update_blacklist=options.auto_update_blacklist,
    )
