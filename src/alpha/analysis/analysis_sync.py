"""分析边车文件同步实现。

本模块负责确保 analysis 派生文件与主结果文件一致。
从 io 包迁入 analysis 包，因为其核心职责是分析结果重建，
而非底层文件 I/O。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ..io.common import atomic_write_json
from ..io.output_paths import build_output_sidecar_paths
from .report_builder import build_analysis_payload, build_results_summary_payload
from .results_loader import load_existing_results
from .template_registry_sidecars import sync_template_registry_sidecars
from .template_stats import compile_template_stats

logger = logging.getLogger(__name__)


def ensure_analysis_synced(output_path: str) -> None:
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
    should_rebuild = should_rebuild or not os.path.exists(sidecar_paths["template_registry"])
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
    derived_summary, analysis_inputs = build_results_summary_payload(
        str(summary.get("dataset_id", "unknown") or "unknown"),
        results,
        settings_fingerprint=str(summary.get("settings_fingerprint", "")),
        template_library_fingerprint=str(summary.get("template_library_fingerprint", "")),
        run_config=summary.get("run_config") if isinstance(summary.get("run_config"), dict) else {},
        results_journal_path=os.path.relpath(
            sidecar_paths["results_journal"], start=Path(output_path).parent
        ),
    )
    analysis = build_analysis_payload(results, derived_summary, analysis_inputs)
    atomic_write_json(sidecar_paths["analysis"], analysis)
    sync_template_registry_sidecars(
        output_path,
        template_stats=compile_template_stats(results),
    )
    logger.info("[analysis] rebuilt analysis from main results: %s", sidecar_paths["analysis"])
