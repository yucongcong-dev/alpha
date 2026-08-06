"""Bootstrap path resolution and runtime output preparation."""

from __future__ import annotations

import logging

from ..analysis.analysis_sync import ensure_analysis_synced
from ..cli.run_config import build_run_config_snapshot
from ..config.application import ApplicationConfig
from ..io.output_paths import cleanup_legacy_sidecar_files
from ..models.runtime_protocols import RunConfig

logger = logging.getLogger(__name__)


def prepare_runtime_outputs(config: ApplicationConfig) -> RunConfig:
    """Prepare logging/output side effects and capture the embedded run config."""
    paths = config.paths
    cleanup_legacy_sidecar_files(paths.output, verbose=True)
    ensure_analysis_synced(paths.output)
    run_config = build_run_config_snapshot(config, paths)
    logger.info("[config] 运行配置将嵌入主结果文件")
    return run_config
