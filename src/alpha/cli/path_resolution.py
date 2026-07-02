"""
CLI 运行路径归一化与应用辅助模块。
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from ..io.output_paths import (
    build_dataset_scoped_paths,
    build_output_sidecar_paths,
    resolve_cli_path,
)
from ..models.io_types import RunPaths
from .constants import DEFAULT_CREDS_FILE, DEFAULT_CREDS_KEY_FILE


def normalize_args_paths(args: argparse.Namespace) -> RunPaths:
    """按 dataset 上下文解析运行文件路径，但不修改 args 本身。"""
    scoped_paths = build_dataset_scoped_paths(
        args.dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
    )

    template_library_file = (
        resolve_cli_path(args.template_library_file, base_dir=os.getcwd())
        or scoped_paths["template_library_file"]
    )
    fields_cache_file = (
        resolve_cli_path(args.fields_cache_file, base_dir=os.getcwd())
        or scoped_paths["fields_cache_file"]
    )
    output_file = resolve_cli_path(args.output, base_dir=os.getcwd()) or scoped_paths["output"]
    feedback_output = resolve_cli_path(args.feedback_output, base_dir=os.getcwd()) or output_file
    creds_file = resolve_cli_path(args.creds_file, base_dir=os.getcwd()) or DEFAULT_CREDS_FILE
    creds_key_file = (
        resolve_cli_path(args.creds_key_file, base_dir=os.getcwd()) or DEFAULT_CREDS_KEY_FILE
    )
    include_fields_file = resolve_cli_path(args.include_fields_file, base_dir=os.getcwd())
    exclude_fields_file = resolve_cli_path(args.exclude_fields_file, base_dir=os.getcwd())
    include_templates_file = resolve_cli_path(args.include_templates_file, base_dir=os.getcwd())
    exclude_templates_file = resolve_cli_path(args.exclude_templates_file, base_dir=os.getcwd())

    sidecar_paths = build_output_sidecar_paths(output_file)
    log_file = resolve_cli_path(args.log_file, base_dir=os.getcwd()) or sidecar_paths["run_log"]
    results_dir = str(Path(output_file).parent)
    output_stem = Path(output_file).stem
    output_dir = Path(output_file).parent
    state_file = str(output_dir / f"{output_stem}_state.json")
    checkpoint_file = str(output_dir / f"{output_stem}_checkpoint.json")

    return RunPaths(
        results_dir=results_dir,
        log_file=log_file,
        state_file=state_file,
        checkpoint_file=checkpoint_file,
        fields_cache_file=fields_cache_file,
        template_library_file=template_library_file,
        output=output_file,
        feedback_output=feedback_output,
        creds_file=creds_file,
        creds_key_file=creds_key_file,
        include_fields_file=include_fields_file,
        exclude_fields_file=exclude_fields_file,
        include_templates_file=include_templates_file,
        exclude_templates_file=exclude_templates_file,
    )


def apply_run_paths(args: argparse.Namespace, run_paths: RunPaths) -> None:
    """把归一化后的关键路径显式同步回 args，供旧调用链兼容使用。"""
    args.output = run_paths.output
    args.log_file = run_paths.log_file
    args.state_file = run_paths.state_file
    args.checkpoint_file = run_paths.checkpoint_file
    args.fields_cache_file = run_paths.fields_cache_file
    args.template_library_file = run_paths.template_library_file
    args.feedback_output = run_paths.feedback_output
    args.creds_file = run_paths.creds_file
    args.creds_key_file = run_paths.creds_key_file
    args.include_fields_file = run_paths.include_fields_file
    args.exclude_fields_file = run_paths.exclude_fields_file
    args.include_templates_file = run_paths.include_templates_file
    args.exclude_templates_file = run_paths.exclude_templates_file
