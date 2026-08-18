"""
结果输出相关的路径与边车文件辅助函数。
"""

from __future__ import annotations

import logging
from pathlib import Path
import time

from ..config.static_config import get_static_config
from ..io.common import (
    DATASETS_DIR,
    sanitize_dataset_id_for_filename,
)

logger = logging.getLogger(__name__)


def build_fields_cache_scope_key(
    *,
    region: str = "",
    universe: str = "",
    instrument_type: str = "",
    delay: int | None = None,
) -> str:
    """Build a short, readable scope key for field-cache directories."""
    parts: list[str] = []
    if region:
        parts.append(sanitize_dataset_id_for_filename(region).lower())
    if universe:
        parts.append(sanitize_dataset_id_for_filename(universe).lower())
    if instrument_type:
        parts.append(sanitize_dataset_id_for_filename(instrument_type).lower())
    if delay is not None:
        parts.append(f"d{int(delay)}")
    return "_".join(parts) or "default"


def resolve_cli_path(path: str, *, base_dir: str | None = None) -> str:
    """将 CLI 路径解析为绝对路径。"""
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        base_path = Path(base_dir).expanduser() if base_dir else Path.cwd()
        candidate = base_path / candidate
    return str(candidate.resolve())


def build_dataset_scoped_paths(
    dataset_id: str,
    *,
    region: str = "",
    universe: str = "",
    instrument_type: str = "",
    delay: int | None = None,
    run_name: str = "default",
) -> dict[str, str]:
    """根据 dataset_id 派生模板、策略、缓存与运行目录路径。"""
    dataset_key = sanitize_dataset_id_for_filename(dataset_id)
    run_key = sanitize_dataset_id_for_filename(run_name or "default")
    dataset_root = DATASETS_DIR / dataset_key
    cache_scope_key = build_fields_cache_scope_key(
        region=region,
        universe=universe,
        instrument_type=instrument_type,
        delay=delay,
    )
    fields_cache_path = dataset_root / "cache" / f"{cache_scope_key}.json"
    run_dir = dataset_root / "runs" / run_key
    return {
        "dataset_root": str(dataset_root),
        "template_library_file": str(dataset_root / "template.json"),
        "datasets_root": str(DATASETS_DIR),
        "fields_cache_file": str(fields_cache_path),
        "feedback_output": str(dataset_root / "feedback" / cache_scope_key / "summary.json"),
        "run_dir": str(run_dir),
        "output": str(run_dir / "summary.json"),
    }


def build_output_sidecar_paths(output_path: str) -> dict[str, str]:
    """根据主结果文件路径生成配套边车文件路径。"""
    output = Path(output_path)
    base_dir = output.parent
    if output.name.lower() == "summary.json":
        return {
            "analysis": str(base_dir / "analysis.json"),
            "template_registry": str(base_dir / "template_registry.json"),
            "results_journal": str(base_dir / "results.jsonl"),
            "run_log": str(base_dir / "run.log"),
        }
    base_name = output.stem or "results"
    if not output.suffix:
        base_name = output.name or "results"
    log_date = time.strftime(get_static_config().date_format_iso)
    return {
        "analysis": str(base_dir / f"{base_name}_analysis.json"),
        "template_registry": str(base_dir / f"{base_name}_template_registry.json"),
        "results_journal": str(base_dir / f"{base_name}_results.jsonl"),
        "run_log": str(base_dir / f"{base_name}_{log_date}.log"),
    }


def is_feedback_output_path(output_path: str) -> bool:
    """Return whether a summary path belongs to the dataset feedback cache."""
    output = Path(output_path)
    return output.parent.name == "feedback" or output.parent.parent.name == "feedback"


def cleanup_legacy_sidecar_files(output_path: str, *, verbose: bool = False) -> None:
    """删除旧版分散 summary 文件，避免保留过时输出。"""
    output = Path(output_path)
    base_dir = output.parent
    base_name = output.stem
    legacy_suffixes = (
        "_submittable.json",
        "_submitted.json",
        "_failed_checks_summary.json",
        "_template_performance_summary.json",
        "_field_performance_summary.json",
        "_run_config.json",
    )
    for suffix in legacy_suffixes:
        legacy_path = base_dir / f"{base_name}{suffix}"
        try:
            legacy_path.unlink()
            if verbose:
                logger.info("[cleanup] removed legacy sidecar file %s", legacy_path)
        except FileNotFoundError:
            continue
