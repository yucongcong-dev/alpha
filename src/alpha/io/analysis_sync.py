"""
分析边车文件同步实现。
"""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
import os

from ..analysis.stats import load_existing_results
from ..config.constants import DEFAULT_DATASET_ID
from .output_paths import build_output_sidecar_paths
from .results_store import dump_results as dump_results_store

logger = logging.getLogger(__name__)

DumpResultsFn = Callable[..., None]


def ensure_analysis_synced(
    output_path: str,
    *,
    dump_results_fn: DumpResultsFn = dump_results_store,
) -> None:
    """确保 analysis 派生文件与主结果文件一致。"""
    if not output_path or not os.path.exists(output_path):
        return
    sidecar_paths = build_output_sidecar_paths(output_path)
    try:
        with open(output_path, encoding="utf-8") as handle:
            summary = json.load(handle)
    except Exception as exc:
        logger.warning("[analysis] skipped sync; failed to read main results: %s", exc)
        return
    if not isinstance(summary, dict):
        logger.warning(
            "[analysis] skipped sync; unexpected main results JSON type: %s",
            type(summary).__name__,
        )
        return

    should_rebuild = not os.path.exists(sidecar_paths["analysis"])
    if not should_rebuild:
        try:
            with open(sidecar_paths["analysis"], encoding="utf-8") as handle:
                analysis = json.load(handle)
            if not isinstance(analysis, dict):
                should_rebuild = True
            else:
                should_rebuild = (
                    analysis.get("tested") != summary.get("tested")
                    or analysis.get("settings_fingerprint") != summary.get("settings_fingerprint")
                    or analysis.get("template_library_fingerprint")
                    != summary.get("template_library_fingerprint")
                )
        except Exception:
            should_rebuild = True

    if not should_rebuild:
        return

    results = load_existing_results(output_path)
    dump_results_fn(
        output_path,
        str(summary.get("dataset_id", DEFAULT_DATASET_ID)),
        results,
        settings_fingerprint=str(summary.get("settings_fingerprint", "")),
        template_library_fingerprint=str(summary.get("template_library_fingerprint", "")),
        run_config=summary.get("run_config") if isinstance(summary.get("run_config"), dict) else {},
    )
    logger.info("[analysis] rebuilt analysis from main results: %s", sidecar_paths["analysis"])
