"""Bootstrap path resolution and runtime output preparation."""

from __future__ import annotations

import logging

from ..io.common import resolve_datasets_root
from ..models.io_types import RunPaths
from ..models.runtime_options import BootstrapPathOptions, RunConfigSnapshotOptions
from ..models.runtime_protocols import RunConfig
from .bootstrap_types import BootstrapPaths, RuntimeOutputServices

logger = logging.getLogger(__name__)


def run_path_value(run_paths: RunPaths | None, attr: str) -> str:
    """从 RunPaths 读取路径属性。"""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def resolve_bootstrap_paths(
    path_options: BootstrapPathOptions,
    run_paths: RunPaths | None,
) -> BootstrapPaths:
    """Resolve all runtime-sensitive paths up front."""
    output_file = run_path_value(run_paths, "output") or path_options.output
    return BootstrapPaths(
        output_file=output_file,
        log_file=run_path_value(run_paths, "log_file"),
        datasets_root=run_path_value(run_paths, "datasets_root") or str(resolve_datasets_root()),
        template_library_file=(
            run_path_value(run_paths, "template_library_file") or path_options.template_library_file
        ),
        fields_cache_file=run_path_value(run_paths, "fields_cache_file")
        or path_options.fields_cache_file,
        feedback_output=run_path_value(run_paths, "feedback_output") or output_file,
        creds_file=run_path_value(run_paths, "creds_file") or path_options.creds_file,
        creds_key_file=run_path_value(run_paths, "creds_key_file") or path_options.creds_key_file,
    )


def build_effective_run_paths(
    path_options: BootstrapPathOptions,
    paths: BootstrapPaths,
    run_paths: RunPaths | None,
) -> RunPaths:
    """Build a minimal RunPaths snapshot even when the caller did not normalize paths."""
    if run_paths is not None:
        return run_paths
    return RunPaths(
        results_dir="",
        log_file=paths.log_file,
        state_file="",
        checkpoint_file="",
        datasets_root=paths.datasets_root,
        fields_cache_file=paths.fields_cache_file,
        template_library_file=paths.template_library_file,
        output=paths.output_file,
        feedback_output=paths.feedback_output,
        creds_file=paths.creds_file,
        creds_key_file=paths.creds_key_file,
        include_fields_file=path_options.include_fields_file,
        exclude_fields_file=path_options.exclude_fields_file,
        include_templates_file=path_options.include_templates_file,
        exclude_templates_file=path_options.exclude_templates_file,
    )


def prepare_runtime_outputs(
    run_config_options: RunConfigSnapshotOptions,
    path_options: BootstrapPathOptions,
    run_paths: RunPaths | None,
    paths: BootstrapPaths,
    *,
    services: RuntimeOutputServices,
) -> RunConfig:
    """Prepare logging/output side effects and capture the embedded run config."""
    effective_run_paths = build_effective_run_paths(path_options, paths, run_paths)
    services.cleanup_legacy_sidecar_files(paths.output_file, verbose=True)
    services.ensure_analysis_synced(paths.output_file)
    run_config = services.build_run_config_snapshot(run_config_options, effective_run_paths)
    logger.info("[config] 运行配置将嵌入主结果文件")
    return run_config
